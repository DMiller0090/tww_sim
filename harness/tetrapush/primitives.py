# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""Phase-1 PRIMITIVE CHARACTERIZATION for the Tetra-push planner (session 22).

Extracts, from the validated self-contained `FreeRun` DTM window, the reusable structure of the
hand-performed push cycle:

  * `window_records`   -- the instrumented rollout: per frame, proc/speedF/facing/travel, feet,
                          the EXEC Co centre and its LOCAL (facing-frame) offset, the applied
                          recoil/plow, and the contact depth. The raw material for everything below.
  * `find_cycles`      -- the cycle spans (re-target frame -> frame before the next re-target).
  * `cycle_template`   -- the per-frame RIGID template of one cycle in the AIM frame: foot motion
                          (along, side), facing offset from the aim, and the exec-centre local
                          offset. The tier-0 geometric stepper consumes this.
  * `input_macro`      -- the cycle's raw-input pattern with stick bytes abstracted to (angle
                          offset from the aim, msd): `macro_inputs` re-aims it to any world angle
                          theta via `stick_for_bearing` (the clamp-aware inverse), which is how a
                          "cycle at aim theta" becomes REAL controller bytes for a FreeRun/tier-2
                          confirm.

The decomposition rests on measured/decomp facts: the roll's facing is LOCKED at the stick target
(the aim), its speedF is plow-independent (recoil is position-only), and the exec-centre offset is
pose-driven and position-independent (the stored FK pose is local). The aim-CHASE frames (the
proc-7/9 re-target and untarget re-aim) do depend on the Tetra bearing; the template freezes their
relative pattern (v1) and tier-2 re-simulates exactly, so the approximation only costs tier-0
ranking accuracy, never correctness of a confirmed plan.

Report CLI: ``python -m harness.tetrapush.primitives`` prints the cycle table, the template
rigidity A/B (cycle 1 vs cycle 2), and the drift diagnostic (sim vs the live capture -- the
session-22 finding: the closed-loop position drift is DIFFERENTIAL, not common-mode; see the
README status box).
"""
import math

from tww_sim.land.land import FRONT_ROLL

from harness.tetrapush import seeds
from harness.tetrapush.from_f0 import full_depth_push
from harness.tetrapush.tetra_plow import plow_depth

_TAU = 2.0 * math.pi


def _rad(bam):
    return (int(bam) & 0xFFFF) / 65536.0 * _TAU


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def to_local(vx, vz, facing_bam):
    """World (x, z) vector -> (along, side) in the facing frame (along = +facing direction,
    side = +90 deg clockwise of facing, i.e. facing's right hand)."""
    a = _rad(facing_bam)
    fx, fz = math.sin(a), math.cos(a)          # forward (state.py: x += d*sin, z += d*cos)
    rx, rz = math.cos(a), -math.sin(a)         # right
    return (vx * fx + vz * fz, vx * rx + vz * rz)


def to_world(along, side, facing_bam):
    a = _rad(facing_bam)
    return (along * math.sin(a) + side * math.cos(a),
            along * math.cos(a) - side * math.sin(a))


def window_records(env, upto=44, tetra_at=None, input_at=None):
    """Run the fully self-contained FreeRun over the DTM window and instrument every frame.

    Returns a list of dicts (f = 1..upto-1): ``proc``, ``speedF``, ``facing``, ``travel``,
    ``feet`` (x, z), ``tetra`` (x, z), ``cyl_exec``, ``cyl`` (settled), ``o_local`` (exec centre
    minus feet, in the facing frame), ``recoil`` (the cc_move applied THIS frame), ``plow`` (the
    Tetra move applied this frame), ``foot_local`` (this frame's foot term = dfeet - recoil, in
    the frame of this frame's TRAVEL... stored as world; the template converts), ``depth`` (the
    outgoing contact depth), ``csangle``."""
    run = seeds.make_freerun(env, tetra_at=tetra_at)
    inp = input_at if input_at is not None else seeds.dtm_input_at(env)
    run.pre_seed_input(inp(0))
    prev_feet = (run.link.pos_x, run.link.pos_z)
    out = []
    for k in range(1, upto):
        pend_link = run.pend_link          # the recoil step() will apply this frame
        pend_tetra = run.pend_tetra
        row = run.step(inp(k))
        feet = row['sim_link']
        dfeet = (feet[0] - prev_feet[0], feet[1] - prev_feet[1])
        foot_world = (dfeet[0] - pend_link[0], dfeet[1] - pend_link[1])
        cx = row['sim_cyl_exec']
        rec = dict(
            f=k, proc=row['sim_proc'], speedF=row['speedF'], facing=row['sim_facing'],
            travel=run.link.travel, feet=feet, tetra=row['sim_tetra'],
            cyl_exec=cx, cyl=row['sim_cyl'],
            o_local=to_local(cx[0] - feet[0], cx[1] - feet[1], row['sim_facing']),
            recoil=pend_link, plow=pend_tetra, foot_world=foot_world,
            depth=plow_depth(row['sim_cyl'], row['sim_tetra']),
            csangle=row.get('sim_csangle'))
        out.append(rec)
        prev_feet = feet
    return out


def find_cycles(records, dtm_env=None):
    """Cycle spans as (start_f, roll_f, end_f): start = the RE-TARGET frame (the proc-7 entry
    whose next-but-one frame rolls -- in the courtyard window the +18 flip lands 1 frame before
    the roll trigger), roll_f = the FRONT_ROLL entry frame, end_f = the frame before the next
    cycle's start (or the last record). Identified purely off the proc stream: a FRONT_ROLL entry
    is a record whose proc is 30 and whose predecessor's isn't."""
    by_f = {r['f']: r for r in records}
    rolls = [r['f'] for r in records
             if r['proc'] == FRONT_ROLL and (r['f'] - 1 not in by_f
                                             or by_f[r['f'] - 1]['proc'] != FRONT_ROLL)]
    spans = []
    for i, rf in enumerate(rolls):
        # walk back to the re-target: the last non-MOVE frame run before the roll (proc 7 tier);
        # state 2's first cycle re-targets 1 frame before the roll.
        start = rf - 1
        while start - 1 in by_f and by_f[start - 1]['proc'] not in (6,):
            start -= 1
        end = (rolls[i + 1] - 2) if i + 1 < len(rolls) else records[-1]['f']
        spans.append((start, rf, end))
    return spans


def cycle_template(records, span):
    """The RIGID per-frame template of one cycle, in the cycle's AIM frame (aim = the locked roll
    facing). Per relative frame j (0 at the cycle's re-target frame): ``proc``, ``speedF``,
    ``facing_rel`` (facing - aim, s16), ``foot_local`` (this frame's foot term in the AIM frame),
    ``o_local`` (the exec-centre offset in the FACING frame -- pose data, reused as-is).

    Returns (aim_bam, [frame dicts])."""
    start, roll_f, end = span
    by_f = {r['f']: r for r in records}
    aim = by_f[roll_f]['facing']
    rows = []
    for f in range(start, end + 1):
        r = by_f[f]
        rows.append(dict(
            j=f - start, proc=r['proc'], speedF=r['speedF'],
            facing_rel=_s16(r['facing'] - aim),
            foot_local=to_local(r['foot_world'][0], r['foot_world'][1], aim),
            o_local=r['o_local']))
    return aim, rows


def input_macro(env, span, records):
    """The cycle's raw-input pattern, stick bytes abstracted for re-aiming: per relative frame j,
    ``buttons``, ``triggerL``, and either ``stick=None`` (neutral/deadzone) or ``(rel_bam, msd)``
    -- the decoded walk want-target's offset from the cycle aim (m34E8 = decode + 0x8000 +
    csangle) and the stick magnitude. `macro_inputs` rebuilds bytes for any aim with
    `stick_for_bearing` (C-stick pinned DOWN, the manualCamera hold -- csangle stays a commanded
    constant in novel plans; the recorded window's own C-stick swings are NOT part of the
    primitive)."""
    from tww_sim.core.mathlib import main_stick_decode
    start, roll_f, end = span
    by_f = {r['f']: r for r in records}
    aim = by_f[roll_f]['facing']
    inp = seeds.dtm_input_at(env)
    out = []
    for f in range(start, end + 1):
        raw = inp(f - 1)   # delay-1: the input ACTED at frame f is the one delivered at f-1
        ang, msd = main_stick_decode(raw['stickX'], raw['stickY'])
        if ang is None:
            stick = None
        else:
            # csangle at the latch: the camera value the physics of frame f read = end of f-1.
            cs = by_f[f - 1]['csangle'] if f - 1 in by_f and by_f[f - 1]['csangle'] is not None \
                else env['cyl'][f - 1]['csangle']
            want = (ang + 0x8000 + cs) & 0xFFFF
            stick = (_s16(want - aim), float(msd))
        out.append(dict(j=f - start, buttons=raw['buttons'], triggerL=raw['triggerL'],
                        stick=stick))
    return out


def macro_inputs(macro, aim_bam, csangle):
    """Realize an abstract cycle macro at world aim ``aim_bam`` under a (held) ``csangle``:
    a list of raw-input dicts (C-stick pinned DOWN -- substick (128, 0) -- the manualCamera
    hold). The stick bytes come from the clamp-aware `stick_for_bearing` inverse."""
    from tww_sim.land.plan_land._primitives import stick_for_bearing
    out = []
    for m in macro:
        if m['stick'] is None:
            sx, sy = 128, 128
        else:
            rel, msd = m['stick']
            sx, sy = stick_for_bearing((aim_bam + rel) & 0xFFFF, csangle, msd=min(msd, 1.0))
        out.append(dict(stickX=sx, stickY=sy, buttons=m['buttons'], triggerL=m['triggerL'],
                        substickX=128, substickY=0))
    return out


def drift_report(env, upto=44):
    """The session-22 drift diagnostic: sim (self-contained) vs the live capture, per frame --
    link/tetra error magnitudes, the differential component |e_link - e_tetra|, and the
    sim-vs-live Link<->Tetra distance. Shows the drift is DIFFERENTIAL (e_link ~ -e_tetra,
    a pair rotation the plow feedback amplifies ~1.35x/contact frame), NOT common-mode."""
    cyl = env['cyl']
    recs = window_records(env, upto=upto)
    out = []
    for r in recs:
        lv = cyl[r['f']]
        le = (r['feet'][0] - lv['link']['pos'][0], r['feet'][1] - lv['link']['pos'][2])
        te = (r['tetra'][0] - lv['tetra']['pos'][0], r['tetra'][1] - lv['tetra']['pos'][2])
        out.append(dict(
            f=r['f'], link_err=math.hypot(*le), tetra_err=math.hypot(*te),
            diff=math.hypot(le[0] - te[0], le[1] - te[1]),
            dist_sim=math.hypot(r['feet'][0] - r['tetra'][0], r['feet'][1] - r['tetra'][1]),
            dist_live=math.hypot(lv['link']['pos'][0] - lv['tetra']['pos'][0],
                                 lv['link']['pos'][2] - lv['tetra']['pos'][2])))
    return out


def main():
    env = seeds.load_env()
    recs = window_records(env)
    spans = find_cycles(recs)
    print("cycles (start, roll, end):", spans)
    for sp in spans:
        aim, tpl = cycle_template(recs, sp)
        n_contact = sum(1 for r in recs if sp[0] <= r['f'] <= sp[2] and r['depth'] > 0)
        print("\ncycle @f%d..%d: aim %d, %d frames, %d contact frames" % (
            sp[0], sp[2], aim, len(tpl), n_contact))
        print("  j proc speedF   facing_rel  foot(along,side)      o(along,side)")
        for t in tpl:
            print("  %2d %3d %8.3f  %6d   (%7.3f,%7.3f)   (%7.3f,%7.3f)" % (
                t['j'], t['proc'], t['speedF'], t['facing_rel'],
                t['foot_local'][0], t['foot_local'][1], t['o_local'][0], t['o_local'][1]))
    if len(spans) >= 2:
        a1, t1 = cycle_template(recs, spans[0])
        a2, t2 = cycle_template(recs, spans[1])
        n = min(len(t1), len(t2))
        print("\nrigidity A/B (cycle1 vs cycle2, %d common frames):" % n)
        wf = max(math.hypot(t1[j]['foot_local'][0] - t2[j]['foot_local'][0],
                            t1[j]['foot_local'][1] - t2[j]['foot_local'][1]) for j in range(n))
        wo = max(math.hypot(t1[j]['o_local'][0] - t2[j]['o_local'][0],
                            t1[j]['o_local'][1] - t2[j]['o_local'][1]) for j in range(n))
        ws = max(abs(t1[j]['speedF'] - t2[j]['speedF']) for j in range(n))
        wa = max(abs(t1[j]['facing_rel'] - t2[j]['facing_rel']) for j in range(n))
        print("  max |dfoot| %.4f u   max |do| %.4f u   max |dspeedF| %.4f   max |dfacing_rel| %d BAM"
              % (wf, wo, ws, wa))
    print("\ndrift diagnostic (sim vs live capture):")
    print("  f  link_err  tetra_err  |differential|  dist_sim  dist_live")
    for d in drift_report(env):
        if d['f'] % 3 == 0 or d['f'] < 4:
            print("  %2d  %8.4f  %8.4f  %10.5f  %8.2f  %8.2f" % (
                d['f'], d['link_err'], d['tetra_err'], d['diff'],
                d['dist_sim'], d['dist_live']))


if __name__ == '__main__':
    main()
