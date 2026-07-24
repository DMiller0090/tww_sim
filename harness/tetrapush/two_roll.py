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
"""TWO CHAINED ROLLS, better than the human -- the frame-minimal proof target (session 40).

Dereck's bar for this stage: do not chase an 80-frame plan. **Chain TWO rolls at a down-herd rate
above the recorded human's, from state 2**, in the full realizable sim. The human's recorded 2-roll
window is the number to beat: 561.3 u over 44 frames = **12.76 u/frame**.

THE CYCLE (Dereck's s39 design; branching structure is the point)
-----------------------------------------------------------------
  * A ROLL IS A ZERO-BRANCH SEGMENT. Facing is LOCKED for its ~16 frames, so nothing about Link's
    physics is steerable there and branching inside it is pure waste. Its frames do two jobs, both
    COMPUTED, not searched: a C-stick slew (`slew_substick`) that walks csangle to the value the
    NEXT turnaround needs, and L held (released at ``release_at``) for the EBS retention.
  * BRANCHING HAPPENS ONLY AT THE JUNCTIONS: the roll FACING (swept over every reachable halfword
    in a window -- `roll_facing_fan`), the turnaround target csangle, the L-release frame, and the
    flip stick/magnitude.
  * The roll facing is genuinely free because facing = decode(stick, csangle) and csangle is
    C-stick-controllable; `roll_facing_fan` enumerates target halfwords at 1-BAM step and DEDUPES BY
    THE ACHIEVED facing, so the fan is exactly the reachable set, not a guess at it.

WHY THIS RUNS IN THE PYTHON SIM AND NOT THE NATIVE FLEET
--------------------------------------------------------
The native fleet is ~200-260k steps/s vs Python's ~3.2k, but `CourtyardFleet._step_core_frame`
passes ``has_eye=0``, so the native lock aims at Tetra's FEET, not her eyePos -- the -102 BAM
roll-entry error s38 pinned, which compounds to 69 u of Tetra divergence over one 16-frame roll
(overshoot instead of pursuit). Closing it needs `npc_zl1_look` ported to C. At a 2-roll horizon we
do not need to: ~50 frames/candidate is ~16 ms in Python, so ~10k candidates is ~2.5 minutes -- the
whole sweep fits, on the sim whose rolls are CORRECT. (The native path + the eyePos port is what a
longer-horizon search will need.)

PRUNING is aggressive, per Dereck: talk-unsafe A-presses (`search.a_press_is_talk`), Link overtaking
Tetra or drifting off the herd line (`reposition.HerdLine`), leaving the stt-3 plow regime, a roll
that never fires, and a turnaround that fails to snap.

Pure stdlib, no Dolphin. CLI:
``python -m harness.tetrapush.two_roll {human | fan | chain}``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush import primitives as P
from harness.tetrapush.reposition import HerdLine, on_line_ok, ESS_DOWN
from harness.tetrapush.steered_reposition import _s16, _bearing
from tww_sim.land.land import FRONT_ROLL
from tww_sim.land.plan_land._primitives import stick_for_bearing

CSTICK_NEUTRAL = 128
CS_DEADBAND = 300
CONTACT_RADIUS = 80.0
MAX_ROLL_FRAMES = 30


def _inp(bearing, csangle, msd, *, buttons=0, triggerL=0, subx=CSTICK_NEUTRAL):
    sx, sy = stick_for_bearing(int(bearing) & 0xFFFF, int(csangle), msd=min(msd, 1.0))
    return dict(stickX=sx, stickY=sy, buttons=buttons, triggerL=triggerL,
                substickX=subx, substickY=0)


def slew_substick(live_cs, target_cs):
    """The COMPUTED C-stick byte for one roll frame: peg toward ``target_cs``, neutral once inside
    the deadband (neutral FREEZES csangle -- `steered_reposition.camera_authority`). This is the
    roll's only degree of freedom and it is not searched."""
    if target_cs is None:
        return CSTICK_NEUTRAL
    gap = _s16(int(target_cs) - int(live_cs))
    return 255 if gap > CS_DEADBAND else 0 if gap < -CS_DEADBAND else CSTICK_NEUTRAL


# --------------------------------------------------------------------------- the human baseline

def human_baseline(env, hl=None, upto=45):
    """The number to beat: the recorded 2-roll window's down-herd rate from state 2."""
    hl = HerdLine.from_env(env) if hl is None else hl
    rows = S.rollout_recorded(env, upto=upto)['rows']
    herd = hl.along(rows[-1]['tetra'][0], rows[-1]['tetra'][1])
    return dict(herd=herd, frames=len(rows), per_frame=herd / len(rows), rolls=sum(
        1 for r in rows if r['proc'] == FRONT_ROLL))


# --------------------------------------------------------------------------- the reachable fan

def roll_facing_fan(run, center, half_window, step=1):
    """Every REACHABLE roll facing within ``center +- half_window``. Sweeps target halfwords at
    ``step`` BAM, inverts each through `stick_for_bearing` at the live csangle, and dedupes by the
    resulting stick BYTES -- so the fan is the achievable set (the byte grid + octagon clamp make
    many targets collapse onto one), not a nominal grid. Returns ``[(want_bam, (sx, sy))]``."""
    seen = {}
    a = -int(half_window)
    while a <= int(half_window):
        want = (int(center) + a) & 0xFFFF
        sx, sy = stick_for_bearing(want, int(run.csangle), msd=1.0)
        if (sx, sy) not in seen:
            seen[(sx, sy)] = want
        a += int(step)
    return [(w, b) for b, w in seen.items()]


# --------------------------------------------------------------------------- segments

def roll_segment(run, roll_bam, *, target_cs, l_window, log=None):
    """Fire the A-roll at ``roll_bam`` and ride it to its EBS exit -- ZERO branching. The stick holds
    the aim; L is held until roll-frame ``release_at`` (the -25.727 lever); the C-stick is the
    COMPUTED slew toward ``target_cs`` so csangle is pre-positioned for the next turnaround.

    Returns ``dict(ok, talk_unsafe, roll_speedF, frames, exit_cs)``; ``ok`` is False if the A-press
    would TALK or no roll ever fired."""
    def _step(d):
        if log is not None:
            log.append(dict(d))
        run.step(d)

    d = _inp(roll_bam, run.csangle, 1.0, buttons=S.PAD_A,
             subx=slew_substick(run.csangle, target_cs))
    if S.a_press_is_talk(run, d):
        return dict(ok=False, talk_unsafe=True, roll_speedF=None, frames=0, exit_cs=run.csangle)
    _step(d)
    frames = 1
    roll_speedF = run.link.speedF if run.link.state == FRONT_ROLL else None
    seen = run.link.state == FRONT_ROLL
    lo, hi = l_window
    j = 0
    for _ in range(MAX_ROLL_FRAMES):
        in_roll = run.link.state == FRONT_ROLL
        # L is a mid-roll PULSE, not a hold: a held L keeps the lock live so
        # `setShapeAngleToAtnActor` re-aims facing every frame (the roll stops being facing-locked).
        hold_L = in_roll and lo <= j < hi
        j += 1
        # A held stick STEERS the roll (s40 per-frame diff); the human holds ESS-neutral.
        _step(dict(stickX=ESS_DOWN[0], stickY=ESS_DOWN[1],
                   buttons=S.PAD_L if hold_L else 0, triggerL=255 if hold_L else 0,
                   substickX=slew_substick(run.csangle, target_cs), substickY=0))
        frames += 1
        if run.link.state == FRONT_ROLL:
            seen = True
            if roll_speedF is None:
                roll_speedF = run.link.speedF
        elif seen and run.link.state == 6:
            break
    return dict(ok=seen, talk_unsafe=False, roll_speedF=roll_speedF, frames=frames,
                exit_cs=run.csangle)


def turnaround_and_flip(run, hl, *, nflip, flip_bam, flip_msd, ess=ESS_DOWN, log=None):
    """The junction: one ESS frame (the instant turnaround the roll's csangle slew set up), then
    ``nflip`` L-held proc-7 frames that flip the backslide to a POSITIVE pre-roll speed.

    Returns ``dict(turned, preroll, frames)``; ``turned`` is the facing snap in BAM (a real
    turnaround is > 0x4000)."""
    def _step(d):
        if log is not None:
            log.append(dict(d))
        run.step(d)

    f0 = run.link.facing
    _step(dict(stickX=ess[0], stickY=ess[1], buttons=0, triggerL=0,
               substickX=CSTICK_NEUTRAL, substickY=0))
    turned = abs(_s16(run.link.facing - f0))
    for _ in range(int(nflip)):
        _step(_inp(flip_bam, run.csangle, flip_msd, buttons=S.PAD_L, triggerL=255,
                   subx=CSTICK_NEUTRAL))
    return dict(turned=turned, preroll=run.link.speedF, frames=1 + int(nflip))


# --------------------------------------------------------------------------- metrics / pruning

def metrics(run, hl, frames):
    lx, lz = run.link.pos_x, run.link.pos_z
    return dict(herd=hl.along(run.tx, run.tz), frames=frames,
                per_frame=hl.along(run.tx, run.tz) / frames if frames else 0.0,
                lead=hl.lead(lx, lz, run.tx, run.tz),
                lat=hl.lateral(lx, lz) - hl.lateral(run.tx, run.tz),
                dist=math.hypot(lx - run.tx, lz - run.tz),
                followed=run._follow_warned)


def alive(m, *, max_lead=-2.0, max_lat=60.0):
    """Aggressive prune: never overtake Tetra, stay near the herd line, stay in the plow regime."""
    return (not m['followed']) and m['lead'] <= max_lead and abs(m['lat']) <= max_lat


# --------------------------------------------------------------------------- cycle 1 (from state 2)

def cycle1_candidates(env, hl, *, half_window=0x2000, step=1, nflips=(1, 2, 3),
                      flip_msds=(1.0,), release_ats=(14.0, 15.0), target_css=(None,),
                      beam=40, verbose=False):
    """Sweep the FIRST roll from state 2 and keep the best on-line survivors.

    At state 2 Tetra is ~122 deg BEHIND Link (out of the +-90 cone), so L re-targets straight into
    the proc-7 flip -- no turnaround is needed to start. Branches: ``nflip`` x ``flip_msd`` x the
    REACHABLE roll-facing fan x ``release_at`` x the roll's camera target. Returns the surviving
    nodes sorted by down-herd rate, each ``dict(run, log, frames, m, knobs)``."""
    dtm = seeds.dtm_input_at(env)
    out = []
    ntried = ntalk = noff = norol = 0
    for nflip in nflips:
        for fmsd in flip_msds:
            # --- the flip prologue (shared by every roll facing at these knobs) ---
            base = seeds.make_freerun(env)
            base.pre_seed_input(dtm(0))
            blog = []
            fb = _bearing((base.link.pos_x, base.link.pos_z), (base.tx, base.tz))
            for _ in range(nflip):
                d = _inp(fb, base.csangle, fmsd, buttons=S.PAD_L, triggerL=255)
                blog.append(dict(d))
                base.step(d)
            center = _bearing((base.link.pos_x, base.link.pos_z), (base.tx, base.tz))
            fan = roll_facing_fan(base, center, half_window, step)
            if verbose:
                print("  nflip=%d msd=%.2f: preroll %+.2f, %d reachable facings in +-%d BAM"
                      % (nflip, fmsd, base.link.speedF, len(fan), half_window))
            for (want, _bytes) in fan:
                for ra in release_ats:
                    for tcs in target_css:
                        ntried += 1
                        run = base.clone()
                        log = list(blog)
                        r = roll_segment(run, want, target_cs=tcs, release_at=ra, log=log)
                        if r['talk_unsafe']:
                            ntalk += 1
                            continue
                        if not r['ok']:
                            norol += 1
                            continue
                        fr = nflip + r['frames']
                        m = metrics(run, hl, fr)
                        if not alive(m):
                            noff += 1
                            continue
                        out.append(dict(run=run, log=log, frames=fr, m=m,
                                        knobs=dict(nflip=nflip, flip_msd=fmsd, roll_bam=want,
                                                   release_at=ra, target_cs=tcs)))
    out.sort(key=lambda n: -n['m']['per_frame'])
    if verbose:
        print("  tried %d: %d talked, %d never rolled, %d off-line/overtook -> %d survivors"
              % (ntried, ntalk, norol, noff, len(out)))
    return out[:beam]


def _cmd_fan(env, hl, kw):
    import time
    b = human_baseline(env, hl)
    print("HUMAN: %.1f u / %d f = %.3f u/frame\n" % (b['herd'], b['frames'], b['per_frame']))
    t0 = time.perf_counter()
    nodes = cycle1_candidates(env, hl, half_window=int(kw.get('window', 0x2000)),
                              step=int(kw.get('step', 1)), beam=int(kw.get('beam', 20)),
                              verbose=True)
    print("\n(%.1f s)  best cycle-1 candidates:" % (time.perf_counter() - t0))
    print("  roll_bam  nflip msd  rel   frames   herd    u/f    lead    lat   roll_spF")
    for n in nodes[:20]:
        k, m = n['knobs'], n['m']
        print("  %6d     %d  %.2f %4.1f   %3d   %+7.1f %6.2f  %+6.1f %+6.1f"
              % (k['roll_bam'], k['nflip'], k['flip_msd'], k['release_at'], n['frames'],
                 m['herd'], m['per_frame'], m['lead'], m['lat']))


def main(argv):
    import warnings
    warnings.simplefilter('ignore')
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    cmd = argv[0] if argv else 'human'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'fan':
        _cmd_fan(env, hl, kw)
    elif cmd == 'human':
        b = human_baseline(env, hl)
        print("HUMAN 2-roll baseline from state 2: %.1f u over %d frames = %.3f u/frame "
              "(%d roll frames)" % (b['herd'], b['frames'], b['per_frame'], b['rolls']))
        print("  the bar: a 2-roll plan must exceed %.3f u/frame" % b['per_frame'])
    else:
        print("usage: python -m harness.tetrapush.two_roll {human | fan | chain}")


if __name__ == '__main__':
    main(sys.argv[1:])
