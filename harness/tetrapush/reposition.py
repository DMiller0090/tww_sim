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
"""The FRAME-MINIMAL reposition optimizer for the Courtyard Tetra push (session 33+).

Objective (`[[tetrapush-frame-minimal]]`): the OPTIMAL, better-than-human input sequence from
state 2 that herds Tetra onto a genuine `tetra_placements` coord in the FEWEST total frames --
BEATING the recorded human (~12.4 u/frame), pushing toward the sustained deep-overlap +26-roll
ceiling by compressing the inter-roll overhead. The recorded 2-cycle human window is the
feasibility ORACLE, not the target.

Built on the 0-ULP `from_f0.FreeRun` (fidelity is `test_from_f0`'s) + the `search` primitives.
This module adds the two Dereck steers (session 33) as first-class levers/constraints:

  * STEER #1 -- PRUNE "past Tetra". A straight roll (facing locked at `_roll_init`) is a pursuit
    only while Link stays BEHIND Tetra on the herd line; if Link OVERTAKES her (crosses to the
    corner side) the roll shoves her sideways/backward and the herd freezes -- those obviously
    fail. `HerdLine.lead` measures Link's signed along-herd position relative to Tetra (negative =
    behind = good); `on_line_ok` prunes any frame where Link is past her (or too far off-line).
    The recorded human stays 40-85 u behind her EVERY frame (`verify` CLI).

  * STEER #2/#3 -- RETAIN -25.7. The human's untarget backslide holds only -25.45 because the roll
    exits into a 2-frame proc-9 ATN_ACTOR tier: body1 flips +26 -> -25.727, body2 adds the +0.275
    ATN accel term (`ATN_SPD * msd(0.0556) * cos`) -> -25.454. RELEASING the mid-roll lock-L one
    frame EARLIER drops the actor-lock one dispatch-frame sooner, so the roll exits into proc-9 for
    ONLY body1 (the -25.727 flip) and goes straight to MOVE -- the backslide then inherits -25.727
    and decays only ~0.011/frame. `l_release_early` is the macro transform; the L-release frame is
    a per-cycle search variable. (A truly-neutral stick does NOT help: proc-6 MOVE with a neutral
    stick brakes to 0 in ~5 frames; the human's slight held stick is what sustains the EBS glide.)

THE FRAME-MINIMAL CYCLE from primitives (roll-to-roll PERIOD a search variable):
  re-target proc-7 +18 flip (L held, Tetra out of the +-90 deg cone) -> A-roll +26 aimed ALONG the
  herd line (Link on-line behind Tetra -> self-stabilising pursuit) -> hold L late, release 1 frame
  early -> 1-frame untarget tier -> -25.727 MOVE backslide (the free reposition) -> repeat. The
  search sweeps per cycle (aim, L-release frame, reposition length), chained via `FreeRun.clone`,
  pruned by talk-safety (`search.a_press_is_talk`) + regime (`_follow_warned`) + on-line-behind.

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.reposition {verify|retain|chain}``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import primitives as P
from harness.tetrapush import search as S
from tww_sim.land.land import FRONT_ROLL
from tww_sim.land.plan_land._primitives import stick_for_bearing


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


# ESS-down (the reference turnaround stick); diagonals work too with a matching diagonal csangle
# (Dereck: same facing-snap principle at any angle -- see `turnaround`).
ESS_DOWN = (128, 110)


# --------------------------------------------------------------------------- herd-line geometry

class HerdLine:
    """The push axis: the line from Tetra's state-2 start toward the genuine-coord cluster
    centroid (the direction the plan must herd her). `down` is the unit down-herd vector (toward
    the cluster / corner), `perp` its +90 deg lateral. All projections are relative to Tetra's
    start so `along` grows as she is herded and `lead` reads Link's position relative to her."""

    def __init__(self, origin, down):
        self.ox, self.oz = float(origin[0]), float(origin[-1])
        n = math.hypot(down[0], down[1])
        self.dx, self.dz = down[0] / n, down[1] / n
        self.px, self.pz = -self.dz, self.dx           # +90 deg (lateral)

    @classmethod
    def from_env(cls, env):
        """Herd toward the genuine-coord centroid from Tetra's state-2 start (feasibility.py:
        the cluster is ~967 u @ -161.5 deg; the recorded herd matches to 0.2 deg)."""
        t0 = env['cyl'][0]['tetra']['pos']
        placements, _ = seeds.load_placements()
        cx = sum(p['x'] for p in placements) / len(placements)
        cz = sum(p['z'] for p in placements) / len(placements)
        return cls((t0[0], t0[2]), (cx - t0[0], cz - t0[2]))

    def along(self, x, z):
        """Down-herd distance of a point from Tetra's start (+ = toward the cluster)."""
        return (x - self.ox) * self.dx + (z - self.oz) * self.dz

    def lateral(self, x, z):
        return (x - self.ox) * self.px + (z - self.oz) * self.pz

    def lead(self, lx, lz, tx, tz):
        """Link's signed along-herd position relative to Tetra: (Link - Tetra) . down.
        NEGATIVE = Link is up-herd (BEHIND) Tetra = the valid pursuit side; POSITIVE = Link has
        OVERTAKEN her (past her, corner-side) -> the roll shoves her sideways, herd freezes."""
        return (lx - tx) * self.dx + (lz - tz) * self.dz

    def bearing_bam(self):
        """The down-herd direction as a BAM world angle (0 == +z, 0x4000 == +x)."""
        return int(math.atan2(self.dx, self.dz) / (2.0 * math.pi) * 65536.0) & 0xFFFF


#: The FRAME the plow regime is asserted in -- the herd line, or the pair's own push axis
#: (`pair_line`). knowledge/strategy/the-crossing-costs-the-arming-posture.md
AXIS_HERD = 'herd'
AXIS_PAIR = 'pair'


def pair_line(lx, lz, tx, tz):
    """**The pair's own push axis, as a `HerdLine`**: origin at Tetra, ``down`` the unit vector from
    Link toward her -- the direction he is actually pushing, whatever the herd wants.

    This is the object a regime predicate means by ``AXIS_PAIR``, and it is what the gate compares
    the fast collapsed forms against (`tests/test_free_axis.py`): in this frame ``lead`` is exactly
    minus the separation, the lateral offset between the two is zero and the bearing from Link to her
    IS the axis bearing, so a box read off the human collapses to his measured SEPARATION band alone.
    That collapse is why the hot paths do not build this object per frame."""
    return HerdLine((tx, tz), (tx - lx, tz - lz))


def on_line_ok(lx, lz, tx, tz, hl, *, min_behind=2.0, max_lateral=60.0):
    """The steer-#1 prune predicate for one frame: Link must stay BEHIND Tetra on the herd line
    (``lead <= -min_behind``, i.e. never overtake her) and roughly ON the line (|lateral offset
    from Tetra| <= ``max_lateral``). Returns True if the frame is acceptable."""
    if hl.lead(lx, lz, tx, tz) > -min_behind:
        return False
    lat = hl.lateral(lx, lz) - hl.lateral(tx, tz)
    return abs(lat) <= max_lateral


# --------------------------------------------------------------------------- the -25.7 macro lever

def _macro_roll_l_frames(env, macro, aim):
    """Run the macro once and return the relative-frame indices j whose delivered input holds L
    (button 0x40 or analog triggerL) WHILE Link is in FRONT_ROLL -- the mid-roll lock-on re-pulse
    (NOT the cycle-boundary re-target L). These are the frames `l_release_early` strips."""
    run = seeds.make_freerun(env)
    run.pre_seed_input(S._frame_input(macro[0], aim, run.csangle))
    out = []
    for j in range(1, len(macro)):
        m = macro[j]
        held = (m['buttons'] & 0x40) or m['triggerL']
        row = run.step(S._frame_input(m, aim, run.csangle))
        if held and row['sim_proc'] == FRONT_ROLL:
            out.append(j)
    return out


def l_release_early(env, macro, aim, n=1):
    """A copy of ``macro`` with L (button 0x40 + analog triggerL) stripped from the LAST ``n``
    mid-roll lock frames -- releasing the attention lock ``n`` dispatch-frames earlier. n=1
    shortens the untarget tier to its single body1 frame so the MOVE backslide retains -25.727
    (steer #2/#3; verified `retain` CLI + gated `test_reposition.py`). n=0 returns an unchanged
    copy. The cycle-boundary re-target L (j0-1, and the next cycle's) is never touched."""
    strip = set(_macro_roll_l_frames(env, macro, aim)[-n:]) if n > 0 else set()
    out = []
    for j, m in enumerate(macro):
        c = dict(m)
        if j in strip:
            c['buttons'] = m['buttons'] & ~0x40
            c['triggerL'] = 0
        out.append(c)
    return out


# --------------------------------------------------------------------------- instrumented rollout

def rollout_metrics(env, res, hl):
    """From a `search.rollout`/`rollout_recorded` result, compute the frame-minimal figures of
    merit against the herd line ``hl``: total Tetra herd (down-herd, u), total frames, herd per
    frame, the worst (most positive) Link lead (steer-#1: > 0 means Link overtook Tetra somewhere),
    and whether every frame is on-line-behind."""
    rows = res['rows']
    if not rows:
        return dict(herd=0.0, frames=0, per_frame=0.0, worst_lead=None, on_line=False)
    t0 = env['cyl'][0]['tetra']['pos']
    worst_lead = -1e9
    on_line = True
    for row in rows:
        lx, lz = row['link']
        tx, tz = row['tetra']
        worst_lead = max(worst_lead, hl.lead(lx, lz, tx, tz))
        if not on_line_ok(lx, lz, tx, tz, hl):
            on_line = False
    tx, tz = rows[-1]['tetra']
    herd = hl.along(tx, tz)                          # down-herd distance from Tetra's start
    frames = len(rows)
    return dict(herd=herd, frames=frames, per_frame=herd / frames if frames else 0.0,
                worst_lead=worst_lead, on_line=on_line)


# --------------------------------------------------------------------------- the 1-frame turnaround

def turnaround(run, csangle, ess=ESS_DOWN):
    """The 1-frame INSTANT 180 turnaround (Dereck, session 33; `move.py:109-116`). In the untarget
    EBS facing sits ~exactly 0x8000 from travel; holding ESS ``ess`` with a PRECISE ``csangle`` sets
    the stick want-angle so the facing chase steps across travel -> ``temp*temp2 <= 0`` -> ``facing =
    travel`` in ONE frame, with the speed preserved (cos(target-travel) ~ 1, the -25.727 held). The
    csangle must land in the snap window (wide, ~14k BAM, but off it you get a MOVE_TURN reversal
    instead). Diagonals work too with a matching diagonal csangle. Injects ``csangle`` (camera-less
    run). Returns the facing delta this frame (a real turnaround is > ~0x4000)."""
    f0 = run.link.facing
    run.step(dict(stickX=ess[0], stickY=ess[1], buttons=0, triggerL=0, substickX=128, substickY=128),
             csangle=csangle)
    return abs(_s16(run.link.facing - f0))


def frame_min_reroll(run, hl, *, csangle, aim=None, nflip=2, release_at=15.0, max_roll=24,
                     csangle_roll=None):
    """One FRAME-MINIMAL inter-roll reposition + re-roll from a post-untarget EBS (`run` camera-less,
    csangle injected). The cycle Dereck specified:

      1. `turnaround` (1 frame): face AWAY from Tetra (up-herd), -25.727 preserved.
      2. proc-7 flip (``nflip`` frames): hold L + stick toward Tetra (down-herd). Facing is away so
         Tetra is OUT of the cone -> L re-targets (no actor lock) and the DIR_BACKWARD negation flips
         the -25.7 backslide to ~+23 (positive pre-roll speed) -- the "1 frame > +17".
      3. A-roll: A + stick toward Tetra. Facing is still away at the A press -> TALK-SAFE; the roll
         snaps facing toward Tetra and fires at clamp(+23*1.5+0.5)=26 (a full roll, not the +5 graze).
      4. roll body: hold L (re-acquires the lock mid-roll, facing now toward Tetra) and RELEASE it one
         frame before the anim completes (``release_at`` = the roll-frame to drop L) -> a 1-frame
         untarget tier -> the next -25.727 EBS.

    The roll aims at the LIVE Tetra bearing each frame (down-herd pursuit). ``csangle_roll`` overrides
    the injected csangle once the roll starts (the camera can be re-pointed for the next turnaround).
    Advances ``run``; returns a dict: ``turned`` (turnaround snap BAM), ``preroll_speedF``,
    ``roll_speedF``, ``talk_unsafe``, ``rolled``, ``rows`` (per frame), ``min_dist``/``max_dist``,
    ``worst_lead`` (steer-#1: > 0 == Link overtook Tetra), ``ended_ebs`` (back at a MOVE EBS)."""
    # Aim the roll ALONG the herd line (session 32: aiming at Tetra's INSTANT position makes the
    # straight roll cross her path and overshoot). `aim` defaults to the herd-line down-bearing.
    aim = hl.bearing_bam() if aim is None else (int(aim) & 0xFFFF)

    def down():
        return aim

    rows = []
    talk_unsafe = False
    min_dist = max_dist = worst_lead = None

    def _log():
        nonlocal min_dist, max_dist, worst_lead
        lx, lz = run.link.pos_x, run.link.pos_z
        d = math.hypot(lx - run.tx, lz - run.tz)
        lead = hl.lead(lx, lz, run.tx, run.tz)
        rows.append(dict(proc=run.link.state, speedF=run.link.speedF, facing=run.link.facing,
                         link=(lx, lz), tetra=(run.tx, run.tz), dist=d, lead=lead))
        min_dist = d if min_dist is None else min(min_dist, d)
        max_dist = d if max_dist is None else max(max_dist, d)
        worst_lead = lead if worst_lead is None else max(worst_lead, lead)

    # 1) turnaround
    turned = turnaround(run, csangle)
    _log()
    # 2) proc-7 flip (L held, stick toward Tetra)
    for _ in range(nflip):
        sx, sy = stick_for_bearing(down(), csangle, msd=1.0)
        run.step(dict(stickX=sx, stickY=sy, buttons=0x40, triggerL=255, substickX=128, substickY=128),
                 csangle=csangle)
        _log()
    preroll_speedF = run.link.speedF
    # 3) A-roll toward Tetra (turnaround-roll): check talk at the press (facing away -> safe)
    sx, sy = stick_for_bearing(down(), csangle, msd=1.0)
    d_roll = dict(stickX=sx, stickY=sy, buttons=0x100, triggerL=0, substickX=128, substickY=128)
    if S.a_press_is_talk(run, d_roll):
        talk_unsafe = True
    run.step(d_roll, csangle=csangle)
    _log()
    roll_speedF = run.link.speedF if run.link.state == FRONT_ROLL else None
    cs = csangle if csangle_roll is None else csangle_roll
    # 4) roll body: hold L (re-acquire the lock), release `release_at` frames in to end the tier early
    seen_roll = run.link.state == FRONT_ROLL
    ended_ebs = False
    for _ in range(max_roll):
        sx, sy = stick_for_bearing(down(), cs, msd=1.0)
        in_roll = run.link.state == FRONT_ROLL
        rf = getattr(run.link, 'roll_frame', 0.0)
        hold_L = in_roll and rf < release_at            # release L `release_at` into the roll
        btn = 0x40 if hold_L else 0
        trg = 255 if hold_L else 0
        run.step(dict(stickX=sx, stickY=sy, buttons=btn, triggerL=trg, substickX=128, substickY=128),
                 csangle=cs)
        _log()
        if run.link.state == FRONT_ROLL:
            seen_roll = True
        elif seen_roll and run.link.state == 6:         # back to MOVE EBS
            ended_ebs = True
            break
    return dict(turned=turned, preroll_speedF=preroll_speedF, roll_speedF=roll_speedF,
                talk_unsafe=talk_unsafe, rolled=roll_speedF is not None, rows=rows,
                min_dist=min_dist, max_dist=max_dist, worst_lead=worst_lead, ended_ebs=ended_ebs)


def seed_to_untarget(env, macro=None, aim=None):
    """Run cyc1 from state 2 (the recorded release-early macro re-aimed to ``aim``) and stop at the
    first post-untarget MOVE EBS -- the entry state for the first `frame_min_reroll`. Returns
    ``(run, aim)`` with ``run`` camera-less (csangle injected from here on)."""
    recs = P.window_records(env)
    if macro is None:
        macro, a1 = S.canonical_cycle(env, recs)
        macro = l_release_early(env, macro, a1, n=1)
    else:
        _, a1 = S.canonical_cycle(env, recs)
    aim = a1 if aim is None else (int(aim) & 0xFFFF)
    run = seeds.make_freerun(env)
    run.pre_seed_input(S._frame_input(macro[0], aim, run.csangle))
    seen9 = False
    for j in range(1, S.CYCLE_PERIOD):
        row = run.step(S._frame_input(macro[j], aim, run.csangle))
        if row['sim_proc'] == 9:
            seen9 = True
        elif seen9 and row['sim_proc'] == 6:
            break
    run.camera = None                    # switch to injected-csangle mode for the reposition search
    return run, aim


# --------------------------------------------------------------------------- CLI


def _cmd_verify(env):
    """Steer #1 evidence: the recorded human stays BEHIND Tetra (lead < 0) on the herd line EVERY
    frame, and its per-frame herd. Grounds the past-Tetra prune (`on_line_ok`)."""
    import warnings
    warnings.simplefilter('ignore')
    recs = P.window_records(env)
    hl = HerdLine.from_env(env)
    rec = S.rollout_recorded(env, upto=45, recs=recs)
    print("herd line: down-herd bearing %d BAM (%.1f deg)"
          % (hl.bearing_bam(), math.degrees(math.atan2(hl.dx, hl.dz))))
    m = rollout_metrics(env, rec, hl)
    print("recorded human window: herd %.1f u over %d frames = %.2f u/frame"
          % (m['herd'], m['frames'], m['per_frame']))
    print("  worst Link lead %.1f u (%s; < 0 == always behind Tetra), on_line=%s"
          % (m['worst_lead'], "OVERTOOK" if m['worst_lead'] > 0 else "behind", m['on_line']))
    print("\n  f proc  L<->T  lead(behind<0)  lateral_off")
    for row in rec['rows']:
        lx, lz = row['link']
        tx, tz = row['tetra']
        d = math.hypot(lx - tx, lz - tz)
        lead = hl.lead(lx, lz, tx, tz)
        lat = hl.lateral(lx, lz) - hl.lateral(tx, tz)
        if row['f'] % 2 == 0 or row['f'] < 4:
            print("  %2d %3d  %5.1f  %+7.1f        %+7.1f" % (row['f'], row['proc'], d, lead, lat))


def _cmd_retain(env):
    """Steer #2/#3 evidence: releasing the mid-roll lock-L 1 frame early makes the untarget
    backslide retain -25.727 (vs the human's -25.454). Shows both variants side by side."""
    import warnings
    warnings.simplefilter('ignore')
    recs = P.window_records(env)
    macro, aim1 = S.canonical_cycle(env, recs)
    lf = _macro_roll_l_frames(env, macro, aim1)
    print("mid-roll lock-L frames (j): %s -> release-early strips the last one" % lf)

    def run(mac):
        run = seeds.make_freerun(env)
        run.pre_seed_input(S._frame_input(mac[0], aim1, run.csangle))
        out = []
        for j in range(1, len(mac)):
            row = run.step(S._frame_input(mac[j], aim1, run.csangle))
            out.append((j, row['sim_proc'], row['speedF']))
        return out

    rec = run(macro)
    early = run(l_release_early(env, macro, aim1, n=1))
    print("\n  j proc  human-macro   |  release-L-1-early")
    for i in range(len(rec)):
        if rec[i][0] >= 17:
            print("  %2d  %3d %10.5f  |  %3d %10.5f"
                  % (rec[i][0], rec[i][1], rec[i][2], early[i][1], early[i][2]))


def _cmd_chain(env, kw):
    """Chain the FRAME-MINIMAL reposition (`frame_min_reroll`) from state 2 and compare u/frame to
    the human. Sweeps csangle for the turnaround snap window; reports per-cycle herd/lead/talk."""
    import warnings
    warnings.simplefilter('ignore')
    hl = HerdLine.from_env(env)
    ncyc = int(kw.get('ncyc', 4))
    nflip = int(kw.get('nflip', 2))
    release_at = float(kw.get('release_at', 15.0))
    t0 = env['cyl'][0]['tetra']['pos']

    # human baseline
    rec = S.rollout_recorded(env, upto=45)
    mh = rollout_metrics(env, rec, hl)
    print("HUMAN baseline: %.1f u / %d frames = %.2f u/frame (worst_lead %.1f)\n"
          % (mh['herd'], mh['frames'], mh['per_frame'], mh['worst_lead']))

    # pick a csangle in the snap window by sweeping the first reroll's turnaround
    run0, aim1 = seed_to_untarget(env)
    cand = None
    for cs in range(0, 65536, 256):
        c = run0.clone()
        if turnaround(c, cs) > 0x4000 and abs(_s16(c.link.facing - c.link.travel)) < 300 \
                and c.link.speedF <= -24.5 and c.link.state == 6:
            cand = cs
            break
    csangle = int(kw.get('csangle', cand if cand is not None else 25000))
    print("using turnaround csangle=%d (snap window auto-detected: %s)\n"
          % (csangle, cand))

    run, _ = seed_to_untarget(env)
    total_frames = 0
    # cyc1 frames (recorded release-early to the untarget) count toward the total:
    macro, _ = S.canonical_cycle(env, None)
    print("cycle  turned  preroll  roll_spF  talk  min/max_dist  worst_lead  herd   frames")
    ok = True
    for ci in range(ncyc):
        res = frame_min_reroll(run, hl, csangle=csangle, nflip=nflip, release_at=release_at)
        total_frames += len(res['rows'])
        herd = hl.along(run.tx, run.tz)
        flag = ""
        if res['talk_unsafe']:
            flag += " TALK"
        if res['worst_lead'] is not None and res['worst_lead'] > 0:
            flag += " OVERTOOK"
        if run._follow_warned:
            flag += " FOLLOWED"
        print("  %2d   %6d  %7.2f  %8s  %-4s  %5.1f/%5.1f   %+7.1f   %6.1f  %d%s"
              % (ci + 2, res['turned'],
                 res['preroll_speedF'] if res['preroll_speedF'] is not None else 0,
                 ("%.2f" % res['roll_speedF']) if res['roll_speedF'] else "-",
                 "no" if not res['talk_unsafe'] else "YES",
                 res['min_dist'] or 0, res['max_dist'] or 0,
                 res['worst_lead'] or 0, herd, len(res['rows']), flag))
        if res['talk_unsafe'] or (res['worst_lead'] or 0) > 0 or run._follow_warned \
                or not res['ended_ebs']:
            ok = False
            break
    fin_herd = hl.along(run.tx, run.tz)
    print("\nframe-minimal chain: Tetra herd %.1f u; reposition cycles ok=%s" % (fin_herd, ok))
    print("  (per-cycle reposition = turnaround 1f + flip %df + roll; vs human ~10 inter-roll frames)"
          % nflip)


def main(argv):
    env = seeds.load_env()
    cmd = argv[0] if argv else 'verify'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'verify':
        _cmd_verify(env)
    elif cmd == 'retain':
        _cmd_retain(env)
    elif cmd == 'chain':
        _cmd_chain(env, kw)
    else:
        print("usage: python -m harness.tetrapush.reposition "
              "{verify|retain|chain [ncyc=N nflip=N release_at=F csangle=N]}")


if __name__ == '__main__':
    main(sys.argv[1:])
