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
"""The exact aim-per-cycle SEARCH for the Courtyard Tetra push (session 30+).

The forward model (`from_f0.FreeRun`) is bit-exact from state 2 (0-ULP f1..f43, dynamics AND
position -- session 29), so the search uses it DIRECTLY as the evaluator: there is no rigid-template
approximation (the removed session-22 `tier0.py` was that, and it sat on a drifting model). Every
candidate is a real FreeRun rollout, so the chaotic ~1.35x/contact-frame plow amplification is a
non-issue -- the model IS the ground truth.

A push CYCLE is the repeatable 26-frame unit the hand-performed push uses (roll-to-roll period:
cycle 1 rolls at f3, cycle 2 at f29): a MOVE backslide -> proc-7 re-target (+18 flip) -> FRONT_ROLL
(~15 frames, facing LOCKED at the roll aim, plowing Tetra along it) -> the 2-frame ATN_ACTOR untarget
tier (speedF flips to ~-25.7) -> MOVE backslide. Its raw-input pattern is `primitives.input_macro`
of the recorded cycle; `_frame_input` re-aims one frame to a nominal world angle theta via the
clamp-aware `stick_for_bearing` inverse, C-stick pinned DOWN (the manualCamera hold -- novel plans
do not steer the camera).

THE AIM IS A NOMINAL KNOB, NOT A GUARANTEE. With the C-stick pinned, csangle evolves deterministically
via the wired `LandCamera` -- DIFFERENTLY from the recorded window (which moved the C-stick), and the
stick byte grid quantizes the achievable want-angles -- so the achieved roll aim differs from the
commanded theta by a few BAM. The search therefore RANKS BY THE ACHIEVED LANDING read back from
FreeRun, never by the commanded aim: a plan is defined by its raw bytes and FreeRun gives its exact
outcome. (This is why the self-consistency gate feeds the RECORDED C-stick -- only then does a
re-aimed cycle reproduce the recorded window 0-ULP; see `tests/test_search.py`.)

CYCLE CHAINING -- RE-DIAGNOSED (session 31). The session-30 story ("chaining needs C-stick camera
management") was WRONG about the lever. The re-aimed macro's failure to chain is NOT the C-stick: the
recorded window's csangle barely moves (~28 BAM over f20..28), and feeding the recorded C-stick only
"fixes" chaining as a byte-quantization artifact (the ~655 BAM csangle offset perturbs a razor-margin
cone gate). The REAL chaining gate is the inter-roll MOVE-backslide facing turn: the next re-target's
held L re-acquires the attention lock (-> proc-9 slide, no roll, drift out of regime) UNLESS Tetra has
exited the +-0x4000 (90 deg) front cone by the L-pulse frame. The recorded run clears it by ~2600 BAM;
the pinned macro misses by ~145 BAM (chaotic sensitivity -- the session-22 finding).

THE FRAME-MINIMAL PATH (Dereck, session 31 -- `[[tetrapush-frame-minimal]]`). This is a speedrun:
minimize total frames, not just "reach a coord". Two facts reframe chaining:
  * The roll is an A-roll (`a_pressed`, PAD 0x100), and `_roll_init` snaps `facing = target` (the stick
    world-target). So a TURNAROUND-ROLL -- face away from Tetra, then A + stick-toward-Tetra -- rolls
    THROUGH her in one frame WITHOUT the attention lock or the cone gate (it also dodges the console
    talk cone, `[[turnaround-roll-tech]]`). It fires only from a GROUNDED proc (MOVE/ATN_MOVE), NOT the
    proc-9 untarget slide (`state.py` grounded set), so it is available ~2 frames after the untarget
    tier drops back to MOVE. Dereck's proposed optimal chain: roll through Tetra -> mid-roll L for the
    -25.7 EBS -> the EBS backslide REPOSITIONS Link back NE (behind Tetra along the herd bearing) ->
    A-turnaround-roll SW through her again. The EBS backslide is the reposition, not dead time.
  * Tetra is stt-3 (she does NOT self-locomote; she waits where the last plow left her, until dist >
    FOLLOW_ENGAGE_DIST 230 flips her to stt-4). So chaining has no time pressure from HER -- the only
    cost is FRAMES, so minimize the inter-roll gap.
DEEP vs GRAZE is the crux (see `turnaround` CLI). An immediate A-roll GRAZES (min_ovl ~66, snowplows
Tetra ahead, cyc2 adds only ~64 u) and NO roll aim fixes it (swept at reposition 0, min_ovl bottoms at
~66 regardless): at dist ~59 Link and Tetra CO-MOVE SW at ~equal speed through the roll, so the gap
never closes. Depth is a POSITIONING problem, not an aim problem. The recorded human cyc2 plows DEEP
(min_ovl ~40, +185 u) because its ~8-frame CURVED backslide (facing turns 37548->16140 WHILE backing
up) lands Link NE of Tetra at a cut-THROUGH approach before the roll.

THE FRAME-MINIMAL LEVER (Dereck, session 31): the human's ~8-frame face-away turn is the suboptimal
part. The roll snaps `facing = target = decode(stick) + 0x8000 + csangle`, and csangle is a per-frame
input, so PRECISE CAMERA control reorients Link ~180 deg in ONE frame -- collapsing the ~8-frame
reposition-turn to ~1. So the search knob is the MINIMAL (camera-assisted) reposition that places Link
NE of Tetra for the deepest through-roll, chained -- with total FRAMES the objective. The recorded
2-cycle human playback (f0..44) is the feasibility ORACLE for this, not the target.

The deliverable (README `## Plan / status`): the FRAME-MINIMAL input sequence from state 2 that lands
Tetra on a genuine `tetra_placements.tsv` coord AND arranges the matching final roll entry. This module
builds the exact search FOUNDATION (rollout, clone, reachability, the beam scaffold); the frame-minimal
turnaround-roll chain, then the exact placement (walk-push nudge endgame) + the entry walk-in, follow.

Pure stdlib, no Dolphin. CLI:
``python -m harness.tetrapush.search {selfcheck|reach|sweep|chain|herd|turnaround}``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import primitives as P
from harness.tetrapush.from_f0 import FreeRun
from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST
from tww_sim.land.land import FRONT_ROLL

# roll-to-roll period of the hand-performed push (cycle 1 rolls at f3, cycle 2 at f29).
CYCLE_PERIOD = 26
# the roll's frame offset within a cycle (the re-target is j0..j1, the FRONT_ROLL enters at j2).
ROLL_OFFSET = 2
# C-stick pinned DOWN: (128, 0) is the manualCamera hold (substickX neutral -> csangle yaw target
# frozen; substickY down -> m144 == 0 keeps mode 12). Novel plans never steer the camera.
CSTICK_DOWN = (128, 0)


def canonical_cycle(env, recs=None):
    """The repeatable push-cycle macro (26 raw-input frames) + its recorded roll aim. Taken from
    the recorded window's first cycle (`find_cycles` span 0 = the complete unit starting at the
    re-target f1); trimmed to CYCLE_PERIOD so a stitched chain rolls exactly every 26 frames.

    Returns ``(macro, recorded_aim)`` where ``macro`` is the `primitives.input_macro` list
    (per relative frame j: ``buttons``, ``triggerL``, ``stick`` = None|(rel_bam, msd))."""
    recs = recs if recs is not None else P.window_records(env)
    spans = P.find_cycles(recs)
    sp = spans[0]
    macro = P.input_macro(env, sp, recs)[:CYCLE_PERIOD]
    aim, _ = P.cycle_template(recs, sp)
    return macro, aim


def lockless_macro(macro):
    """A copy of ``macro`` with L stripped (button 0x40 + analog triggerL removed) from every frame
    -- the lockless roll-herd variant. It rolls every cycle without engaging the attention lock, but
    plows WEAKLY (~77 u vs the locked resonance's 324 u: without the lock the roll facing is not
    pinned to the aim, so it grazes Tetra) and still does not chain past cycle 1 (see the module
    docstring / `chain`). Kept as a probe for the chaining work."""
    out = []
    for m in macro:
        c = dict(m)
        c['buttons'] = m['buttons'] & ~0x40
        c['triggerL'] = 0
        out.append(c)
    return out


def _frame_input(m, aim_bam, csangle, cstick=CSTICK_DOWN):
    """Realize one macro frame at nominal world aim ``aim_bam`` under a (live) ``csangle`` -- the
    raw-input dict FreeRun.step consumes. The main-stick bytes come from the clamp-aware
    `stick_for_bearing` inverse (`macro['stick']` = (rel-from-aim, msd)); C-stick is ``cstick``."""
    from tww_sim.land.plan_land._primitives import stick_for_bearing
    if m['stick'] is None:
        sx, sy = 128, 128
    else:
        rel, msd = m['stick']
        sx, sy = stick_for_bearing((aim_bam + rel) & 0xFFFF, csangle, msd=min(msd, 1.0))
    return dict(stickX=sx, stickY=sy, buttons=m['buttons'], triggerL=m['triggerL'],
                substickX=cstick[0], substickY=cstick[1])


def step_one_cycle(run, macro, aim, *, cstick=CSTICK_DOWN, csangle_fn=None, base_gidx=0,
                   start_j=0):
    """Step ONE push cycle at nominal aim ``aim`` on an already-seeded ``run`` (the beam-search
    primitive: clone a node's run, then step one more cycle). ``start_j`` = 1 only for cycle 0
    (its ``macro[0]`` was pre-seeded); ``base_gidx`` = the global frame index of this cycle's j=0
    (for ``csangle_fn``, the validation override). Advances ``run`` in place; returns a dict:
    ``rows`` (per frame), ``roll_facing`` (the ACHIEVED aim = the roll's locked facing), ``roll_f``,
    ``followed`` (left the plow regime this cycle), ``max_dist``/``min_dist``, ``tetra``, ``link``."""
    def _cs(gidx):
        return run.csangle if csangle_fn is None else csangle_fn(gidx)

    def _ct(gidx):
        return cstick(gidx) if callable(cstick) else cstick
    rows = []
    roll_facing = roll_f = None
    followed = False
    max_dist = min_dist = None
    for j in range(start_j, CYCLE_PERIOD):
        gidx = base_gidx + j
        d = _frame_input(macro[j], aim, _cs(gidx), _ct(gidx))
        row = run.step(d)
        dist = math.hypot(row['sim_link'][0] - row['sim_tetra'][0],
                          row['sim_link'][1] - row['sim_tetra'][1])
        rows.append(dict(f=gidx, proc=row['sim_proc'], speedF=row['speedF'],
                         facing=row['sim_facing'], link=row['sim_link'],
                         tetra=row['sim_tetra'], csangle=run.csangle, dist=dist, inp=d))
        max_dist = dist if max_dist is None else max(max_dist, dist)
        min_dist = dist if min_dist is None else min(min_dist, dist)
        if run._follow_warned:
            followed = True
        if row['sim_proc'] == FRONT_ROLL and roll_facing is None:
            roll_facing, roll_f = row['sim_facing'], gidx
    return dict(rows=rows, roll_facing=roll_facing, roll_f=roll_f, followed=followed,
                max_dist=max_dist, min_dist=min_dist,
                tetra=(run.tx, run.tz), link=(run.link.pos_x, run.link.pos_z))


def rollout(env, aims, *, cstick_stream=None, csangle_at=None, recs=None, run=None, macro=None,
            stop_on_follow=True):
    """Run FreeRun from state 2 through ``len(aims)`` push cycles, cycle ``ci`` re-aimed to
    ``aims[ci]``. C-stick pinned DOWN unless ``cstick_stream`` (a callable ``k -> (subX, subY)``,
    the recorded-C-stick validation path) is given. Each frame's main stick uses the LIVE csangle
    (1-frame stale -- the input is buffered delay-1; harmless, the search reads achieved values).

    ``csangle_at`` (validation only) -- a callable ``gidx -> csangle`` overriding the live value
    for input generation: the input delivered at frame ``gidx`` is ACTED at frame ``gidx + 1``,
    which reads the csangle committed at frame ``gidx``, so pass ``gidx -> live_csangle[gidx]`` to
    remove the 1-frame staleness and get a bit-exact round-trip vs the recorded window.

    Returns ``dict(rows, run, cycles, tetra, link, facing, max_dist, min_dist, followed)``:
      * ``rows``    -- per acted frame: ``f``, ``proc``, ``speedF``, ``facing``, ``link`` (x, z),
                       ``tetra`` (x, z), ``csangle``, ``dist`` (Link<->Tetra), ``inp`` (delivered).
      * ``cycles``  -- per cycle: ``aim`` (commanded), ``roll_facing`` (ACHIEVED aim), ``roll_f``,
                       ``tetra_end`` (x, z), ``link_end`` (x, z).
      * ``tetra`` / ``link`` / ``facing`` -- the terminal Tetra XZ / Link XZ / Link facing.
      * ``max_dist`` / ``min_dist`` -- Link<->Tetra feet-distance extremes (the plow-regime bound).
      * ``followed`` -- True if the run ever left the stt-3 plow regime (> FOLLOW_ENGAGE_DIST): the
                        model is unfaithful past there, so a plan MUST keep this False.
    """
    recs = recs if recs is not None else P.window_records(env)
    if macro is None:
        macro, _ = canonical_cycle(env, recs)
    if run is None:
        run = seeds.make_freerun(env)

    cstick = CSTICK_DOWN if cstick_stream is None else cstick_stream

    # d_0 (delivered at frame 0, acted at frame 1) -- pre-seed the delay-1 buffer.
    cs0 = run.csangle if csangle_at is None else csangle_at(0)
    ct0 = cstick(0) if callable(cstick) else cstick
    run.pre_seed_input(_frame_input(macro[0], aims[0], cs0, ct0))

    rows = []
    cycles = []
    max_dist = min_dist = None
    followed = False
    for ci, aim in enumerate(aims):
        res = step_one_cycle(run, macro, aim, cstick=cstick, csangle_fn=csangle_at,
                             base_gidx=ci * CYCLE_PERIOD, start_j=1 if ci == 0 else 0)
        rows.extend(res['rows'])
        cycles.append(dict(aim=int(aim) & 0xFFFF, roll_facing=res['roll_facing'],
                           roll_f=res['roll_f'], tetra_end=res['tetra'], link_end=res['link']))
        if res['max_dist'] is not None:
            max_dist = res['max_dist'] if max_dist is None else max(max_dist, res['max_dist'])
            min_dist = res['min_dist'] if min_dist is None else min(min_dist, res['min_dist'])
        if res['followed']:
            followed = True
        if stop_on_follow and followed:
            break
    return dict(rows=rows, run=run, cycles=cycles,
                tetra=(run.tx, run.tz), link=(run.link.pos_x, run.link.pos_z),
                facing=run.link.facing, max_dist=max_dist, min_dist=min_dist, followed=followed)


def rollout_recorded(env, upto=44, recs=None):
    """The harness-validation path: replay the RECORDED delivered inputs (raw DTM bytes, incl. the
    recorded C-stick) frame by frame through a fresh FreeRun. Returns the same shape as `rollout`.
    Feeds the exact recorded bytes so it MUST reproduce the recorded window 0-ULP (the gate)."""
    dtm = seeds.dtm_input_at(env)
    run = seeds.make_freerun(env)
    run.pre_seed_input(dtm(0))
    rows = []
    max_dist = min_dist = None
    followed = False
    for k in range(1, upto):
        row = run.step(dtm(k))
        dist = math.hypot(row['sim_link'][0] - row['sim_tetra'][0],
                          row['sim_link'][1] - row['sim_tetra'][1])
        rows.append(dict(f=k, proc=row['sim_proc'], speedF=row['speedF'],
                         facing=row['sim_facing'], link=row['sim_link'],
                         tetra=row['sim_tetra'], csangle=run.csangle, dist=dist, inp=dtm(k)))
        max_dist = dist if max_dist is None else max(max_dist, dist)
        min_dist = dist if min_dist is None else min(min_dist, dist)
        if run._follow_warned:
            followed = True
    return dict(rows=rows, run=run, cycles=None,
                tetra=(run.tx, run.tz), link=(run.link.pos_x, run.link.pos_z),
                facing=run.link.facing, max_dist=max_dist, min_dist=min_dist, followed=followed)


# --------------------------------------------------------------------------- reachability

def _bearing_deg(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def nearest_placement(placements, tx, tz):
    """(row, distance) of the genuine coord nearest (tx, tz)."""
    best, bd = None, float('inf')
    for p in placements:
        d = math.hypot(p['x'] - tx, p['z'] - tz)
        if d < bd:
            best, bd = p, d
    return best, bd


def _dir_bam(dx, dz):
    """World direction of an (x, z) vector as a BAM angle (0 == +z, 0x4000 == +x; the game's
    convention: state.py x += d*sin, z += d*cos)."""
    return int(math.atan2(dx, dz) / (2.0 * math.pi) * 65536.0) & 0xFFFF


# --------------------------------------------------------------------------- beam search

def _cycle_children(seed_run, parent_run, macro, *, is_root, base_gidx, cone_half, step):
    """The distinct achievable next-cycle outcomes from a beam node. The roll must pass THROUGH
    Tetra to plow her, so the productive roll aim tracks the current Link->Tetra bearing (the
    recorded cycles roll ~+700 BAM off it); centre the commanded-aim cone there. Sweep the cone at
    ``step`` BAM, clone+step ONE cycle each (`FreeRun.clone` is ~0.025 ms), DEDUP by the ACHIEVED
    roll aim (byte quantization collapses many commanded aims onto each achievable one), and drop
    follow-breakers (left the plow regime) and rolless cycles. Returns list of
    ``(cmd_aim, run_after, res)``."""
    ref = parent_run
    center = _dir_bam(ref.tx - ref.link.pos_x, ref.tz - ref.link.pos_z)
    by_achieved = {}
    a = center - cone_half
    while a <= center + cone_half:
        aim = a & 0xFFFF
        c = seed_run.clone() if is_root else parent_run.clone()
        if is_root:
            c.pre_seed_input(_frame_input(macro[0], aim, c.csangle, CSTICK_DOWN))
            res = step_one_cycle(c, macro, aim, base_gidx=0, start_j=1)
        else:
            res = step_one_cycle(c, macro, aim, base_gidx=base_gidx, start_j=0)
        ach = res['roll_facing']
        if ach is not None and not res['followed'] and ach not in by_achieved:
            by_achieved[ach] = (aim, c, res)
        a += step
    return list(by_achieved.values())


def beam_search(env, *, n_cycles=4, beam=24, cone_half=2400, step=48, recs=None, verbose=False):
    """Beam search over per-cycle roll aims that herds Tetra toward the genuine `tetra_placements`
    band, ranked by nearest-genuine-coord distance, EACH candidate a real FreeRun rollout (no
    approximation) pruned by the stt-3 plow-regime guard. This is the COARSE search -- push cycles
    get Tetra onto the band; the exact placement (walk-push nudge) + the entry walk-in are the next
    increment. Returns ``(best_node, beam_nodes)``; a node is ``dict(aims, run, dist, coord,
    max_dist, followed)`` -- ``aims`` the commanded per-cycle aims, ``run`` the terminal FreeRun,
    ``dist`` Tetra's distance to ``coord`` (the nearest genuine coord), ``max_dist`` the worst
    Link<->Tetra separation over the whole plan (< FOLLOW_ENGAGE_DIST == stayed in regime)."""
    recs = recs if recs is not None else P.window_records(env)
    macro, _ = canonical_cycle(env, recs)
    placements, _ = seeds.load_placements()
    seed_run = seeds.make_freerun(env)

    def _mk(aims, run, res, prev_max):
        p, d = nearest_placement(placements, run.tx, run.tz)
        return dict(aims=aims, run=run, dist=d, coord=p,
                    max_dist=max(prev_max, res['max_dist']), followed=res['followed'])

    nodes = [_mk([aim], run, res, 0.0) for aim, run, res in _cycle_children(
        seed_run, seed_run, macro, is_root=True, base_gidx=0, cone_half=cone_half, step=step)]
    nodes.sort(key=lambda n: n['dist'])
    nodes = nodes[:beam]
    best = nodes[0] if nodes else None
    if verbose and best:
        print("cycle 1: %d nodes, best %.1f u from coord #%d (Tetra %.1f,%.1f)"
              % (len(nodes), best['dist'], best['coord']['idx'], best['run'].tx, best['run'].tz))

    for level in range(1, n_cycles):
        nxt = []
        for node in nodes:
            for aim, run, res in _cycle_children(seed_run, node['run'], macro, is_root=False,
                                                 base_gidx=level * CYCLE_PERIOD,
                                                 cone_half=cone_half, step=step):
                nxt.append(_mk(node['aims'] + [aim], run, res, node['max_dist']))
        if not nxt:
            if verbose:
                print("cycle %d: beam EMPTY -- no in-regime rolling child (cycle chaining blocked; "
                      "see the module docstring). Best stays at %d cycle(s)."
                      % (level + 1, len(best['aims']) if best else 0))
            break
        nxt.sort(key=lambda n: n['dist'])
        nodes = nxt[:beam]
        if nodes and (best is None or nodes[0]['dist'] < best['dist']):
            best = nodes[0]
        if verbose and nodes:
            b = nodes[0]
            print("cycle %d: %d nodes, best %.1f u from coord #%d (Tetra %.1f,%.1f) maxdist %.0f"
                  % (level + 1, len(nodes), b['dist'], b['coord']['idx'],
                     b['run'].tx, b['run'].tz, b['max_dist']))
    return best, nodes


def reach_one_cycle(env, aims_bam, recs=None, macro=None):
    """Sweep a single cycle's aim from state 2 over ``aims_bam`` (a list of nominal BAM angles);
    return one dict per aim: ``aim`` (commanded), ``roll_facing`` (achieved), ``tetra`` (landing
    x, z), ``link``, ``dist_end``, ``max_dist``, ``followed``. The per-cycle reach map."""
    recs = recs if recs is not None else P.window_records(env)
    if macro is None:
        macro, _ = canonical_cycle(env, recs)
    out = []
    for a in aims_bam:
        r = rollout(env, [a], recs=recs, macro=macro, stop_on_follow=False)
        c = r['cycles'][0]
        out.append(dict(aim=int(a) & 0xFFFF, roll_facing=c['roll_facing'],
                        tetra=r['tetra'], link=r['link'],
                        dist_end=r['min_dist'], max_dist=r['max_dist'], followed=r['followed']))
    return out


# --------------------------------------------------------------------------- CLI

def _cmd_selfcheck(env):
    import struct

    def bits(x):
        return struct.unpack('<I', struct.pack('<f', float(x)))[0]

    recs = P.window_records(env)
    by_f = {r['f']: r for r in recs}

    # (1) recorded-input replay reproduces the recorded window 0-ULP.
    rec = rollout_recorded(env, upto=44, recs=recs)
    worst = 0
    for row in rec['rows']:
        r = by_f[row['f']]
        worst = max(worst,
                    abs(bits(row['link'][0]) - bits(r['feet'][0])),
                    abs(bits(row['link'][1]) - bits(r['feet'][1])),
                    abs(bits(row['tetra'][0]) - bits(r['tetra'][0])),
                    abs(bits(row['tetra'][1]) - bits(r['tetra'][1])))
    print("recorded-input replay vs window: worst %d ULP (0 == bit-exact)" % worst)

    # (2) canonical macro re-aimed to the recorded aim WITH recorded C-stick + frame-aligned
    #     csangle reproduces cycle 1 bit-for-bit (validates the macro re-aim + stick_for_bearing).
    macro, aim1 = canonical_cycle(env, recs)
    dtm = seeds.dtm_input_at(env)
    cs_stream = lambda g: (dtm(g).get('substickX', 128), dtm(g).get('substickY', 128))
    cs_live = lambda g: (by_f[g]['csangle'] if g in by_f else env['cyl'][g]['csangle'])
    r1 = rollout(env, [aim1], recs=recs, macro=macro, cstick_stream=cs_stream,
                 csangle_at=cs_live, stop_on_follow=False)
    worst1 = 0
    for row in r1['rows']:
        if row['f'] in by_f:
            r = by_f[row['f']]
            worst1 = max(worst1,
                         abs(bits(row['link'][0]) - bits(r['feet'][0])),
                         abs(bits(row['link'][1]) - bits(r['feet'][1])),
                         abs(bits(row['tetra'][0]) - bits(r['tetra'][0])),
                         abs(bits(row['tetra'][1]) - bits(r['tetra'][1])))
    print("macro@aim1 + recorded C-stick vs cycle 1: worst %d ULP over f1..%d"
          % (worst1, CYCLE_PERIOD - 1))

    # (3) pinned-C-stick rollout: a clean cycle staying in the plow regime.
    rp = rollout(env, [aim1], recs=recs, macro=macro, stop_on_follow=False)
    procs = [row['proc'] for row in rp['rows']]
    print("pinned-C-stick rollout: procs %s" % procs)
    print("  achieved roll aim %s (commanded %d), Tetra %.3f,%.3f  max Link<->Tetra %.1f u  followed=%s"
          % (rp['cycles'][0]['roll_facing'], aim1, rp['tetra'][0], rp['tetra'][1],
             rp['max_dist'], rp['followed']))


def _cmd_reach(env):
    recs = P.window_records(env)
    macro, aim1 = canonical_cycle(env, recs)
    placements, _ = seeds.load_placements()
    t0 = env['cyl'][0]['tetra']['pos']
    # sweep aim over a window around the recorded aim
    aims = [(aim1 - 4000 + i * 200) & 0xFFFF for i in range(41)]
    rows = reach_one_cycle(env, aims, recs=recs, macro=macro)
    print("single-cycle reach from state 2 (Tetra start %.1f,%.1f); recorded aim %d:"
          % (t0[0], t0[2], aim1))
    print("  cmd_aim  achieved  tetra_x    tetra_z    herd_u  bearing  maxdist  follow")
    for r in rows:
        dx, dz = r['tetra'][0] - t0[0], r['tetra'][1] - t0[2]
        print("  %6d   %6s   %9.3f  %9.3f  %6.1f  %+7.1f  %6.1f  %s" % (
            r['aim'], r['roll_facing'], r['tetra'][0], r['tetra'][1],
            math.hypot(dx, dz), _bearing_deg(dx, dz), r['max_dist'],
            "Y" if r['followed'] else "."))


def _cmd_sweep(env, kw):
    import time
    import warnings
    warnings.simplefilter('ignore')
    t0 = time.perf_counter()
    best, nodes = beam_search(
        env, n_cycles=int(kw.get('cycles', 4)), beam=int(kw.get('beam', 24)),
        cone_half=int(kw.get('cone', 2400)), step=int(kw.get('step', 48)), verbose=True)
    dt = time.perf_counter() - t0
    print("\n(%.1f s)" % dt)
    if best is None:
        print("NO in-regime candidate found")
        return
    c = best['coord']
    print("\nBEST coarse plan: %d cycles, commanded aims %s" % (len(best['aims']), best['aims']))
    print("  Tetra landed (%.4f, %.4f) -- %.2f u from genuine coord #%d (%.6f, %.6f)"
          % (best['run'].tx, best['run'].tz, best['dist'], c['idx'], c['x'], c['z']))
    print("  Link terminal (%.2f, %.2f) facing %d;  worst Link<->Tetra %.1f u (regime bound %.0f)"
          % (best['run'].link.pos_x, best['run'].link.pos_z, best['run'].link.facing,
             best['max_dist'], FOLLOW_ENGAGE_DIST))
    print("  (coarse landing; exact placement = walk-push nudge endgame + entry walk-in, next.)")


def _cmd_chain(env):
    """Reproduce the cycle-chaining blocker: run 3 cycles at the recorded aim, once with the
    recorded macro (attention lock) and once lockless, and show that neither chains under a pinned
    C-stick (the recorded macro re-locks -> proc-9 slide, no roll; lockless rolls but weakly)."""
    import warnings
    warnings.simplefilter('ignore')
    recs = P.window_records(env)
    macro, aim1 = canonical_cycle(env, recs)
    t0 = env['cyl'][0]['tetra']['pos']
    for tag, mac in (("recorded macro (attention lock)", macro),
                     ("lockless (no L)", lockless_macro(macro))):
        r = rollout(env, [aim1, aim1, aim1], recs=recs, macro=mac, stop_on_follow=False)
        print("\n%s -- 3x recorded aim %d (pinned C-stick):" % (tag, aim1))
        for ci, c in enumerate(r['cycles']):
            te = c['tetra_end']
            print("  cycle %d: achieved roll %s, Tetra (%.1f, %.1f), herd %.1f u"
                  % (ci + 1, c['roll_facing'], te[0], te[1],
                     math.hypot(te[0] - t0[0], te[1] - t0[2])))
        n_roll = sum(1 for row in r['rows'] if row['proc'] == FRONT_ROLL)
        print("  roll frames total %d;  followed=%s;  max Link<->Tetra %.0f u"
              % (n_roll, r['followed'], r['max_dist'] or 0))
    print("\nBLOCKER: only cycle 1 rolls-and-plows; chaining needs attention/camera (C-stick) "
          "management between cycles (module docstring).")


def _cmd_herd(env):
    """The per-frame HERD diagnostic (Dereck's 'is the human cadence optimal?' question): run the
    resonance cycle and show WHERE Tetra actually moves. The finding -- she is shoved ~10-18 u EVERY
    frame Link's Co-cyl overlaps her (dist < 80), during the roll AND the backslide alike; the herd
    is a CONTINUOUS overlap-push, not discrete roll-plows. So the search objective is sustaining (and
    deepening) overlap while driving forward, with the cadence a FREE parameter -- see the module /
    README `## Plan / status`."""
    import warnings
    warnings.simplefilter('ignore')
    recs = P.window_records(env)
    macro, aim1 = canonical_cycle(env, recs)
    t0 = env['cyl'][0]['tetra']['pos']
    r = rollout(env, [aim1], recs=recs, macro=macro, stop_on_follow=False)
    print("resonance cycle @ recorded aim %d (pinned C-stick), per frame:" % aim1)
    print("  f proc  L<->T(overlap<80)  Tetra-herd  dHerd/frame")
    prev = 0.0
    for row in r['rows']:
        lx, lz = row['link']
        tx, tz = row['tetra']
        d = math.hypot(lx - tx, lz - tz)
        herd = math.hypot(tx - t0[0], tz - t0[2])
        print("  %2d %3d   %5.1f %s        %7.1f    %+6.1f"
              % (row['f'], row['proc'], d, "OVL" if d < 80 else "   ", herd, herd - prev))
        prev = herd
    print("\nTetra is plowed every OVL frame (roll AND backslide) -- continuous overlap-push, not "
          "discrete roll-plows. Objective = sustain/deepen overlap + forward drive.")


def cyc1_to_untarget(env, *, aim=None, recs=None, macro=None):
    """Run cycle 1 (recorded macro re-aimed to ``aim``, pinned C-stick) from state 2 and STOP on the
    first MOVE (proc 6) frame after the proc-9 untarget tier -- i.e. the earliest GROUNDED frame from
    which an A-turnaround-roll can fire (the proc-9 slide is not in `state.py`'s grounded set). Returns
    ``(run, aim)``; ``run`` is left at that frame."""
    recs = recs if recs is not None else P.window_records(env)
    if macro is None:
        macro, a1 = canonical_cycle(env, recs)
    else:
        _, a1 = canonical_cycle(env, recs)
    aim = a1 if aim is None else (int(aim) & 0xFFFF)
    run = seeds.make_freerun(env)
    run.pre_seed_input(_frame_input(macro[0], aim, run.csangle))
    seen9 = False
    for j in range(1, CYCLE_PERIOD):
        row = run.step(_frame_input(macro[j], aim, run.csangle))
        if row['sim_proc'] == 9:
            seen9 = True
        elif seen9 and row['sim_proc'] == 6:
            break
    return run, aim


def turnaround_reroll(run, *, reposition=0, aim_at_tetra=True, aim=None, max_frames=24):
    """From a GROUNDED post-untarget ``run``, optionally coast ``reposition`` EBS-backslide frames
    (main stick along the current facing, no L -- the -25.7 slide that repositions Link NE of Tetra),
    then fire an A-turnaround-roll: A (PAD 0x100) held 2 frames (delay-1 safe) + full stick toward
    Tetra (or fixed world ``aim``). `_roll_init` snaps facing to that target, so Link rolls THROUGH
    Tetra without the attention lock. Advances a CLONE (leaves ``run`` untouched); returns a dict:
    ``rolled``, ``min_ovl`` (tightest Link<->Tetra during the roll -- overlap DEPTH, < 80 == contact),
    ``roll_frames``, ``tetra`` (x, z), ``run`` (the advanced clone)."""
    from tww_sim.land.plan_land._primitives import stick_for_bearing
    r = run.clone()
    for _ in range(reposition):
        sx, sy = stick_for_bearing(r.link.facing, r.csangle, msd=0.3)
        r.step(dict(stickX=sx, stickY=sy, buttons=0, triggerL=0, substickX=128, substickY=0))
    rolled = False
    min_ovl = None
    roll_frames = 0
    for k in range(max_frames):
        b = _dir_bam(r.tx - r.link.pos_x, r.tz - r.link.pos_z) if aim_at_tetra \
            else (int(aim) & 0xFFFF)
        sx, sy = stick_for_bearing(b, r.csangle, msd=1.0)
        btn = 0x100 if k < 2 else 0                      # A on the first two delivered frames
        row = r.step(dict(stickX=sx, stickY=sy, buttons=btn, triggerL=0,
                          substickX=128, substickY=0))
        if row['sim_proc'] == FRONT_ROLL:
            rolled = True
            roll_frames += 1
            d = math.hypot(row['sim_link'][0] - row['sim_tetra'][0],
                           row['sim_link'][1] - row['sim_tetra'][1])
            min_ovl = d if min_ovl is None else min(min_ovl, d)
        elif rolled:
            break                                        # roll ended
    return dict(rolled=rolled, min_ovl=min_ovl, roll_frames=roll_frames,
                tetra=(r.tx, r.tz), run=r)


def _cmd_turnaround(env):
    """Reproduce the session-31 turnaround-roll finding (Dereck's frame-minimal chain guess). Run
    cyc1 to the untarget, then fire an A-turnaround-roll toward Tetra after `reposition` EBS frames,
    sweeping `reposition`. Shows: the A-roll DOES fire from the grounded post-untarget MOVE (no lock,
    no cone gate), but an immediate re-roll GRAZES (min_ovl ~65-85) -- Link snowplows Tetra ahead --
    whereas the recorded human cyc2 plows DEEP (min_ovl ~40) after its ~8-frame backslide slides Link
    NE of Tetra. The frame-minimal knob = fewest reposition frames for the deepest through-roll."""
    import warnings
    warnings.simplefilter('ignore')
    recs = P.window_records(env)
    macro, aim1 = canonical_cycle(env, recs)
    t0 = env['cyl'][0]['tetra']['pos']
    run, _ = cyc1_to_untarget(env, aim=aim1, recs=recs, macro=macro)
    d0 = math.hypot(run.link.pos_x - run.tx, run.link.pos_z - run.tz)
    print("cyc1 -> untarget: proc=%d facing=%d speedF=%.2f Tetra(%.1f,%.1f) dist=%.1f herd=%.1f"
          % (run.link.state, run.link.facing, run.link.speedF, run.tx, run.tz, d0,
             math.hypot(run.tx - t0[0], run.tz - t0[2])))
    print("\nA-turnaround-roll toward Tetra after N EBS-backslide reposition frames:")
    print("  repos  rolled  roll_f  min_ovl  Tetra_end        herd    +cyc2")
    herd0 = math.hypot(run.tx - t0[0], run.tz - t0[2])
    for repos in range(0, 11):
        res = turnaround_reroll(run, reposition=repos)
        te = res['tetra']
        herd = math.hypot(te[0] - t0[0], te[1] - t0[2])
        print("  %3d    %s      %3d    %s  (%.1f,%.1f)  %6.1f  %+6.1f" % (
            repos, "Y" if res['rolled'] else ".", res['roll_frames'],
            ("%5.1f" % res['min_ovl']) if res['min_ovl'] is not None else "  -  ",
            te[0], te[1], herd, herd - herd0))
    # the recorded human cyc2 (f29..44) DEEP-overlap reference (the oracle Dereck pointed to)
    rec = rollout_recorded(env, upto=45, recs=recs)
    c2 = [row for row in rec['rows'] if 29 <= row['f'] <= 44 and row['proc'] == FRONT_ROLL]
    if c2:
        print("\n  human oracle cyc2 roll (f29..44): min_ovl %.1f u over %d roll frames "
              "(DEEP -- the backslide first put Link NE of Tetra)"
              % (min(r['dist'] for r in c2), len(c2)))
    print("\nThe A-roll fires from the grounded post-untarget MOVE (no lock / no cone gate); depth "
          "(herd-per-frame) is the search knob -- see the module docstring / `[[tetrapush-frame-minimal]]`.")


def main(argv):
    env = seeds.load_env()
    cmd = argv[0] if argv else 'selfcheck'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'selfcheck':
        _cmd_selfcheck(env)
    elif cmd == 'reach':
        _cmd_reach(env)
    elif cmd == 'sweep':
        _cmd_sweep(env, kw)
    elif cmd == 'chain':
        _cmd_chain(env)
    elif cmd == 'herd':
        _cmd_herd(env)
    elif cmd == 'turnaround':
        _cmd_turnaround(env)
    else:
        print("usage: python -m harness.tetrapush.search {selfcheck|reach|sweep [cycles=N beam=N "
              "cone=BAM step=BAM]|chain|herd|turnaround}")


if __name__ == '__main__':
    main(sys.argv[1:])
