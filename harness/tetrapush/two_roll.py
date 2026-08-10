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
  * A ROLL IS A ZERO-BRANCH SEGMENT FOR THE MAIN STICK -- MEASURED, session 41. Facing is LOCKED for
    its ~16 frames and the main stick is *completely inert* there: replaying the recorded roll with
    the mid-roll stick pegged to (255,128) / (0,128) / (128,255) / (128,0) / (1,1) / the aim itself
    all reproduce the recorded roll **0-ULP**, position and facing (`roll_is_stick_inert`). The
    roll's frames do two jobs, both COMPUTED, not searched: a C-stick slew (`slew_substick`) that
    walks csangle to the value the NEXT turnaround needs, and the mid-roll L PULSE (``l_window``)
    that sets the untarget tier. **This overturns the s40 reading that "a held stick steers the
    roll"** -- that divergence was the aim-generation bug below, not in-roll steering.
  * BRANCHING HAPPENS ONLY AT THE JUNCTIONS: the roll FACING (swept over every reachable stick byte
    pair -- `roll_facing_fan`), the turnaround target csangle, the L pulse window, and the flip
    stick/magnitude.

CONTAINMENT: THE SEARCH SPACE MUST CONTAIN THE HUMAN (Dereck's steer, session 41)
---------------------------------------------------------------------------------
A sanity check any search here must pass: **the human's recorded inputs must be a SUBSET of what the
parameterization can emit** -- not hardcoded in, but reachable because the knobs intrinsically span
the controller. Session 40's fan failed this and that failure WAS the blocker:

  * The fan inverted world bearings through `stick_for_bearing`, which only ever emits
    MAXIMAL-RADIUS (octagon-boundary) bytes. The human's A-press byte pair (181,236) is an INTERIOR
    pair -- same decoded magnitude (mStickDistance saturates at 1.0 well inside the boundary), so it
    is physically equivalent, but it is not in that image. Deduping the fan by those emitted BYTES
    then reached only **544 of the 2280** distinct aims the byte grid actually realizes.
  * Worse, the fan's world bearings were built at the LIVE csangle, but a delivered stick is acted
    the NEXT frame against the csangle committed then -- so every commanded facing landed off by one
    frame of camera slew (76 BAM at the state-2 roll entry).

The fix is structural: **the fan's atom is the stick BYTE PAIR, not a world bearing**
(`reachable_stick_fan`). A byte pair's decoded angle is csangle-INDEPENDENT; the world facing it
achieves is `decoded + 0x8000 + csangle_at_act`, read back from the run. Containment is then true by
construction -- the human's bytes are grid members -- and `contains_human` gates it.

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
from harness.tetrapush.reposition import (AXIS_HERD, AXIS_PAIR, HerdLine, on_line_ok, ESS_DOWN)
from harness.tetrapush.steered_reposition import _s16, _bearing
from tww_sim.core.mathlib import main_stick_decode
from tww_sim.land.land import FRONT_ROLL, LandState
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

_FAN_CACHE = {}


def reachable_stick_fan(msd_min=1.0, strict=False):
    """**The controller's true aim alphabet**: every distinct main-stick aim the pad can physically
    deliver at magnitude >= ``msd_min`` (> it, with ``strict``), enumerated from the FULL 256x256
    byte grid and deduped by the DECODED stick angle (the only thing the physics reads --
    `main_stick_decode`).

    Returns ``[(stick_angle_s16, (sx, sy))]`` sorted by angle. The decoded angle is
    csangle-INDEPENDENT, so this set is computed once and reused at every camera state; the world
    facing a member achieves is `stick_angle + 0x8000 + csangle_at_act`.

    This replaces inverting world bearings through `stick_for_bearing`, whose image is only the
    maximal-radius octagon-boundary bytes -- 544 of these 2280 aims (see the module docstring).

    For a ROLL aim call `roll_aim_fan` instead: an angle's first-in-grid-order representative is
    often too shallow to dispatch a roll at all."""
    key = (float(msd_min), bool(strict))
    if key in _FAN_CACHE:
        return _FAN_CACHE[key]
    seen = {}
    for sx in range(256):
        for sy in range(256):
            ang, msd = main_stick_decode(sx, sy)
            if ang is None:                    # dead-centre: no aim, only the neutral member
                continue
            if (msd > key[0] if strict else msd >= key[0]) and ang not in seen:
                seen[ang] = (sx, sy)
    _FAN_CACHE[key] = sorted(seen.items())
    return _FAN_CACHE[key]


def roll_aim_fan():
    """The aims that actually **dispatch a roll**: `reachable_stick_fan` under the game's own ATTACK
    gate, ``msd > LandState.ATTACK_MSD_MIN`` (strict, `setDoStatusBasic` 2220).

    This is not a narrowing of the alphabet, it is the alphabet's real membership test, and session
    88 paid a console delivery to learn it. Deduping the byte grid by decoded angle keeps the FIRST
    pair in grid order, which is typically a shallow interior one -- e.g. angle 28732 is represented
    by (154, 170) at msd 0.540, while the human delivers (181, 236) at msd 1.0 for the same angle.
    A shallow representative aims the roll correctly in a sim whose only gate is the 0.05 locomotion
    floor, and on console the same press SHEATHES THE SWORD and Link keeps walking. Every angle a
    shallow pair reaches is still reachable here -- by a deeper member of its own class -- so the
    containment `contains_human` asserts is untouched (that check is on the angle, over ALL delivered
    bytes, and keeps the unrestricted fan)."""
    return reachable_stick_fan(msd_min=float(LandState.ATTACK_MSD_MIN), strict=True)


def world_facing(stick_angle, csangle):
    """The world walk target a decoded stick angle commands under ``csangle`` (state.py
    `_set_stick_data`: ``m34E8 = (stick_angle + 0x8000) + csangle``)."""
    return (int(stick_angle) + 0x8000 + int(csangle)) & 0xFFFF


def roll_facing_fan(run, center, half_window, step=1, msd_min=1.0):
    """Every REACHABLE roll facing within ``center +- half_window``, drawn from the controller's own
    aim alphabet (`reachable_stick_fan`) rather than from a nominal bearing grid.

    ``center``/``half_window`` are WORLD bearings; each alphabet member is placed with
    `world_facing` at the run's live csangle. ``step`` thins the returned fan (keep every ``step``-th
    member) -- it is a budget knob, never a resolution limit, since the alphabet is already exactly
    the reachable set. Returns ``[(want_bam, (sx, sy))]``.

    NOTE ``want_bam`` is NOMINAL at the LIVE csangle: the delivered stick is acted the next frame
    against the csangle committed then, so the ACHIEVED facing differs by one frame of camera slew
    (76 BAM at the state-2 roll entry). Callers read the achieved facing back off the run."""
    cs = int(run.csangle)
    half = int(half_window)
    out = []
    for ang, b in reachable_stick_fan(msd_min):
        want = world_facing(ang, cs)
        if abs(_s16(want - int(center))) <= half:
            out.append((want, b))
    out.sort(key=lambda t: _s16(t[0] - int(center)))
    return out[::max(1, int(step))]


# --------------------------------------------------------------------------- segments

def roll_stream(aim_bytes, *, hold=1, a_hold=2, l_window=(5, 8), post_l=ESS_DOWN, post=None):
    """The roll segment's DELIVERED main-stick + button stream as a pure function of the knobs --
    ``k -> dict(stickX, stickY, buttons, triggerL)``, k = 0 at the A-press delivery.

    THREE stick phases, split at the two events that actually matter: the aim release and the end of
    the L pulse (the human moves his stick at exactly those boundaries in both recorded cycles).

    Knobs, each spanning the controller so the human's own stream is a member (`contains_human`):
      * ``aim_bytes`` -- the fan member (`reachable_stick_fan`); the roll's facing.
      * ``hold``      -- frames the aim is held, A-frame inclusive. The mid-roll main stick is INERT
                         (`roll_is_stick_inert`), so this only matters across the EBS exit.
      * ``a_hold``    -- frames A is held (the human holds 2).
      * ``l_window``  -- ``[lo, hi)`` mid-roll L PULSE, the untarget-tier lever. NOT a hold: a held L
                         keeps the lock live so `setShapeAngleToAtnActor` re-aims facing every frame.
      * ``post_l``    -- the stick from ``hold`` until the L pulse ends.
      * ``post``      -- the stick after the L pulse (defaults to ``post_l``). This is the one that
                         drives the post-exit EBS, so it is a real knob -- recorded cycle 2 changes
                         stick here ((128,110) -> (111,111)) and cycle 1 does not."""
    lo, hi = l_window
    post = post_l if post is None else post

    def f(k):
        if k < int(hold):
            sx, sy = aim_bytes
        elif k < int(hi):
            sx, sy = post_l
        else:
            sx, sy = post
        buttons = S.PAD_A if k < int(a_hold) else 0
        triggerL = 0
        if lo <= k < hi:
            buttons |= S.PAD_L
            triggerL = 255
        return dict(stickX=sx, stickY=sy, buttons=buttons, triggerL=triggerL)
    return f


def roll_segment(run, aim_bytes, *, target_cs=None, l_window=(5, 8), hold=1, a_hold=2,
                 post=ESS_DOWN, log=None):
    """Fire the A-roll aimed by ``aim_bytes`` and ride it to its EBS exit. The main stick is inert
    for the roll's duration (measured, s41), so the only live channels are the L pulse and the
    C-stick, which is the COMPUTED slew toward ``target_cs`` -- csangle pre-positioned for the next
    turnaround, the camera-adjustment/instant-turnaround setup the cycle depends on.

    Returns ``dict(ok, talk_unsafe, roll_speedF, roll_facing, frames, exit_cs, entry)``; ``ok`` is
    False if the A-press would TALK or no roll ever fired.

    ``entry`` (session 145) is the state on the frame the FRONT_ROLL first appears -- Link's and
    Tetra's positions, the roll's achieved facing, its body lean and its momentum. That frame is
    exactly what `terminal`/`handoff` call the roll ENTRY (``entry = brace - runway*m``, the
    post-roll-entry-frame position), so it is the coordinate the razor is read at, and until it was
    reported the terminal question could only be asked of a whole banked log after the fact
    (`_notes/s143_rolls.py`) and never of an aim the sweep is deciding on. None if no roll fired."""
    stream = roll_stream(aim_bytes, hold=hold, a_hold=a_hold, l_window=l_window, post=post)

    def _step(d):
        if log is not None:
            log.append(dict(d))
        run.step(d)

    d = dict(stream(0), substickX=slew_substick(run.csangle, target_cs), substickY=0)
    if S.a_press_is_talk(run, d):
        return dict(ok=False, talk_unsafe=True, roll_speedF=None, roll_facing=None, frames=0,
                    exit_cs=run.csangle, entry=None)
    _step(d)
    frames = 1
    roll_speedF = roll_facing = entry = None
    seen = False
    for k in range(1, MAX_ROLL_FRAMES + 1):
        _step(dict(stream(k), substickX=slew_substick(run.csangle, target_cs), substickY=0))
        frames += 1
        if run.link.state == FRONT_ROLL:
            seen = True
            if roll_speedF is None:
                roll_speedF, roll_facing = run.link.speedF, run.link.facing
                entry = dict(k=k, link=(run.link.pos_x, run.link.pos_z), tetra=(run.tx, run.tz),
                             facing=int(run.link.facing) & 0xFFFF,
                             lean=int(run.link.m351C) & 0xFFFF, nspeed=float(run.link.nspeed))
        elif seen and run.link.state == 6:
            break
    return dict(ok=seen, talk_unsafe=False, roll_speedF=roll_speedF, roll_facing=roll_facing,
                frames=frames, exit_cs=run.csangle, entry=entry)


# --------------------------------------------------------------------------- containment / fidelity

def _recorded_rolls(env, upto=45):
    """The recorded window's roll segments as ``[(a_frame, entry_frame, exit_frame)]`` -- ``a_frame``
    is the DTM index whose A-press fires the roll (delay-1, so it acts at ``entry_frame``)."""
    rows = S.rollout_recorded(env, upto=upto)['rows']
    proc = {r['f']: r['proc'] for r in rows}
    out, f = [], min(proc)
    while f <= max(proc):
        if proc.get(f) == FRONT_ROLL and proc.get(f - 1) != FRONT_ROLL:
            e = f
            while proc.get(e + 1) == FRONT_ROLL:
                e += 1
            out.append((f - 1, f, e))
            f = e
        f += 1
    return out


def contains_human(env, upto=45):
    """**The containment sanity check** (Dereck's steer): every main-stick byte pair the human
    delivers in the recorded window must be a member of the search's own aim alphabet, and his roll
    segments' streams must be emittable by `roll_stream` at some knob setting.

    Not a hardcode -- `reachable_stick_fan` enumerates the full byte grid, so membership holds by
    construction; this asserts we did not narrow it. Returns
    ``dict(ok, aims_total, aims_missing, rolls)``."""
    dtm = seeds.dtm_input_at(env)
    fan = reachable_stick_fan(msd_min=0.0)
    # Membership is on the decoded ANGLE -- that is the aim the physics reads; magnitude (msd) is a
    # separate, continuously-swept knob, so two byte pairs with the same angle are the same fan atom.
    angles = {a for a, _b in fan}

    missing = []
    for k in range(upto):
        d = dtm(k)
        b = (int(d.get('stickX', 128)), int(d.get('stickY', 128)))
        ang, _msd = main_stick_decode(*b)
        if ang is None:                        # dead-centre stick: no aim to contain
            continue
        if ang not in angles:
            missing.append((k, b))

    rolls = []
    for (a_f, entry, exit_f) in _recorded_rolls(env, upto=upto):
        n = exit_f - a_f + 1
        delivered = [dtm(a_f + j) for j in range(n)]
        aim = (int(delivered[0].get('stickX', 128)), int(delivered[0].get('stickY', 128)))
        knobs = _fit_roll_knobs(delivered, aim)
        emitted = roll_stream(aim, **knobs) if knobs else None
        ok = knobs is not None and all(
            _same_main(emitted(j), delivered[j]) for j in range(n))
        rolls.append(dict(a_frame=a_f, entry=entry, exit=exit_f, aim=aim, knobs=knobs, ok=ok))

    return dict(ok=not missing and all(r['ok'] for r in rolls),
                aims_total=len(angles), aims_missing=missing, rolls=rolls)


def _same_main(emitted, delivered):
    """Do two inputs agree on every channel `roll_stream` owns? (The C-stick is deliberately NOT
    compared -- it is the computed camera-steer channel, free to differ from the human's.)"""
    return (int(emitted['stickX']) == int(delivered.get('stickX', 128))
            and int(emitted['stickY']) == int(delivered.get('stickY', 128))
            and int(emitted['buttons']) & (S.PAD_A | S.PAD_L)
            == int(delivered.get('buttons', 0)) & (S.PAD_A | S.PAD_L)
            and bool(emitted['triggerL']) == bool(delivered.get('triggerL', 0)))


def _fit_roll_knobs(delivered, aim):
    """Read the `roll_stream` knobs straight off a delivered stream (the inverse of the generator):
    how long the aim/A were held, the L pulse span, and the post stick. Returns None if the stream
    is not of that shape (i.e. the parameterization genuinely cannot express it)."""
    n = len(delivered)

    def main(j):
        return (int(delivered[j].get('stickX', 128)), int(delivered[j].get('stickY', 128)))

    def btn(j):
        return int(delivered[j].get('buttons', 0))
    hold = next((j for j in range(n) if main(j) != aim), n)
    a_hold = next((j for j in range(n) if not btn(j) & S.PAD_A), n)
    ls = [j for j in range(n) if btn(j) & S.PAD_L]
    l_window = (ls[0], ls[-1] + 1) if ls else (0, 0)
    if ls and len(ls) != l_window[1] - l_window[0]:
        return None                                    # not a single contiguous pulse
    hi = l_window[1]
    mid = range(hold, min(hi, n))                      # aim released .. L pulse ends
    tail = range(max(hold, hi), n)                     # after the L pulse
    post_l = main(mid[0]) if len(mid) else ESS_DOWN
    post = main(tail[0]) if len(tail) else post_l
    if any(main(j) != post_l for j in mid) or any(main(j) != post for j in tail):
        return None                       # a stick change somewhere other than the phase boundaries
    return dict(hold=hold, a_hold=a_hold, l_window=l_window, post_l=post_l, post=post)


def reproduces_recorded_roll(env, which=0, upto=45):
    """**The fidelity gate** (session 41, closing the s40 blocker): replay the recorded window to the
    human's own roll entry, then drive `roll_segment`'s own generated stream (fan-derived aim bytes
    at his fitted knobs, recorded C-stick) and require the roll to come out **0-ULP** -- both actors'
    positions and Link's facing, every frame to the roll's exit.

    ``which`` selects the recorded roll. Returns ``dict(ok, first_diverge, frames, knobs, ...)``."""
    dtm = seeds.dtm_input_at(env)
    a_f, entry, exit_f = _recorded_rolls(env, upto=upto)[which]
    n = exit_f - a_f + 1
    aim = (int(dtm(a_f).get('stickX', 128)), int(dtm(a_f).get('stickY', 128)))
    knobs = _fit_roll_knobs([dtm(a_f + j) for j in range(n)], aim)

    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, a_f):
        base.step(dtm(k))

    # The aim comes from the FAN, not from the human's bytes: pick the alphabet member whose decoded
    # angle matches his, so this exercises the generator, not a replay of his controller.
    want_ang, _ = main_stick_decode(*aim)
    gen = next((b for a, b in roll_aim_fan() if a == want_ang), aim)

    def trace(fn):
        r = base.clone()
        rows = []
        for k in range(n):
            r.step(fn(k))
            rows.append((r.link.state, r.link.facing, r.link.pos_x, r.link.pos_z, r.tx, r.tz))
        return rows

    stream = roll_stream(gen, **knobs)

    def gen_input(k):
        d = dict(stream(k))
        rd = dtm(a_f + k)
        d['substickX'] = rd.get('substickX', 128)
        d['substickY'] = rd.get('substickY', 128)
        return d

    rec = trace(lambda k: dtm(a_f + k))
    got = trace(gen_input)
    first = next((k for k, (x, y) in enumerate(zip(rec, got)) if x != y), None)
    return dict(ok=first is None, first_diverge=first, frames=n, knobs=knobs,
                aim_human=aim, aim_generated=gen, entry=entry, exit=exit_f,
                facing=got[-1][1], facing_rec=rec[-1][1])


def roll_is_stick_inert(env, sticks=None, upto=18):
    """**The measured fact the cycle design rests on**: during a FRONT_ROLL the main stick is inert.
    Replays the recorded first roll from the human's own entry with the mid-roll stick pegged to each
    of ``sticks`` and reports whether every variant reproduces the recorded roll 0-ULP.

    Returns ``dict(ok, variants)`` with per-stick ``(first_diverging_k, end_facing)``."""
    sticks = sticks or [(128, 110), (255, 128), (0, 128), (128, 255), (128, 0), (255, 255), (1, 1)]
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    base.step(dtm(1))
    aim = (int(dtm(2).get('stickX', 128)), int(dtm(2).get('stickY', 128)))

    def run_stream(fn):
        r = base.clone()
        rows = []
        for k in range(upto):
            r.step(fn(k))
            rows.append((r.link.state, r.link.facing, r.link.pos_x, r.link.pos_z, r.tx, r.tz))
        return rows

    rec = run_stream(lambda k: dtm(2 + k))
    variants = {}
    for s in sticks:
        stream = roll_stream(aim, hold=1, a_hold=2, l_window=(5, 8), post=s)

        def fn(k, _s=stream):
            d = dict(_s(k))
            rd = dtm(2 + k)
            d['substickX'] = rd.get('substickX', 128)
            d['substickY'] = rd.get('substickY', 128)
            return d
        rows = run_stream(fn)
        first = next((k for k, (a, b) in enumerate(zip(rec, rows)) if a != b), None)
        variants[s] = (first, rows[-1][1])
    return dict(ok=all(v[0] is None for v in variants.values()), variants=variants,
                rec_facing=rec[-1][1])


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


# --------------------------------------------------------------------------- the junction (inter-roll)

_ESS_FAN_CACHE = {}


def ess_fan(msd_max=0.10):
    """**The junction's low-magnitude stick alphabet**: every distinct decoded angle the pad can
    deliver at ESS magnitude (0 < msd <= ``msd_max``), enumerated from the byte grid like
    `reachable_stick_fan` -- 64 angles at the 0.10 cap, ~1024 BAM apart. The ESS glide sticks are
    what steer the untarget backslide (facing/travel chase) while sustaining it (a truly-neutral
    stick brakes to 0 in ~5 frames); the human's junction sticks (128,110)/(111,111)/(110,128) all
    decode inside this set. A coarse 8-direction compass here is exactly the s40-style narrowing
    the containment steer forbids -- the swing want-angle is csangle-relative and fine-grained.

    Returns ``[(angle_s16, (sx, sy))]`` sorted by angle (smallest-msd representative per angle)."""
    key = float(msd_max)
    if key in _ESS_FAN_CACHE:
        return _ESS_FAN_CACHE[key]
    seen = {}
    for sx in range(88, 169):
        for sy in range(88, 169):
            ang, msd = main_stick_decode(sx, sy)
            if ang is None or msd > key:
                continue
            if ang not in seen or msd < seen[ang][1]:
                seen[ang] = ((sx, sy), msd)
    _ESS_FAN_CACHE[key] = sorted((a, b) for a, (b, _m) in seen.items())
    return _ESS_FAN_CACHE[key]


def run_junction(run, phases, *, log=None):
    """Execute a junction as a generic PHASE LIST ``[(n_frames, (sx, sy), l_held)]`` -- the
    inter-roll reposition's atom. No A is ever pressed here (the roll segment owns the A press), the
    C-stick stays neutral (csangle frozen -- roll 1's slew owns the camera). Returns frames run."""
    frames = 0
    for (n, (sx, sy), l) in phases:
        for _ in range(int(n)):
            d = dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                     triggerL=255 if l else 0, substickX=CSTICK_NEUTRAL, substickY=0)
            if log is not None:
                log.append(dict(d))
            run.step(d)
            frames += 1
    return frames


def _fit_phases(delivered):
    """Compress a delivered input stream into the junction's phase list: consecutive frames with the
    same (main stick, L) collapse into one ``(n, stick, l)`` phase. Total -- ANY stream with no
    A-press fits, so junction containment holds by construction; this is the reader."""
    phases = []
    for d in delivered:
        s = (int(d.get('stickX', 128)), int(d.get('stickY', 128)))
        l = 1 if (int(d.get('buttons', 0)) & S.PAD_L) or d.get('triggerL', 0) else 0
        if phases and phases[-1][1] == s and phases[-1][2] == l:
            phases[-1][0] += 1
        else:
            phases.append([1, s, l])
    return [tuple(p) for p in phases]


def junction_variants(toward_bytes, *, nflips=(0, 1, 2), swing_msd=0.10, swing_step=1,
                      n_swings=(2, 3, 4, 5), n_rets=(0, 1, 2), pres=(0, 1)):
    """The junction families the chain search sweeps, ordered SHORTEST FIRST (so the state-dedup in
    `cycle2_chain` keeps the fewest-frame representative of a converged endpoint):

      * TURNAROUND (frame-minimal, s33/s39): 1 ESS-down frame (the instant facing snap -- fires only
        when csangle sits in the snap window, which roll 1's ``target_cs`` slew pre-positions), then
        ``nflip`` L-held frames stick-toward-Tetra (the proc-7 DIR_BACKWARD flip).
      * SWING (the human's own shape): ``n_swing`` ESS frames dragging the MOVE facing chase around
        (no L), then ``n_ret`` L-held ESS frames (re-target; Tetra now out of the +-90 cone), then an
        optional 1-frame full-stick pre-aim with L (the human's f27). The swing stick sweeps the
        FULL low-magnitude alphabet (`ess_fan`, ``swing_step`` thins it -- a budget knob, never a
        resolution limit); the ret stick reuses the swing stick.

    Members are generic phase lists, so the searched set is a budgeted subfamily of everything
    `_fit_phases` can read back -- the human's junction is emittable by the FAMILY by construction
    (`reproduces_recorded_chain` gates the whole window)."""
    out = []
    for nf in nflips:
        ph = [(1, ESS_DOWN, 0)]
        if nf:
            ph.append((nf, toward_bytes, 1))
        out.append(dict(kind='turnaround', phases=ph))
    fan = ess_fan(swing_msd)[::max(1, int(swing_step))]
    for (_ang, sd) in fan:
        for ns in n_swings:
            for nr in n_rets:
                for pre in pres:
                    ph = [(ns, sd, 0)]
                    if nr:
                        ph.append((nr, sd, 1))
                    if pre:
                        ph.append((1, toward_bytes, 1))
                    out.append(dict(kind='swing', phases=ph))
    out.sort(key=lambda v: sum(p[0] for p in v['phases']))
    return out


def reproduces_recorded_chain(env, upto=45):
    """**The whole-window chain fidelity gate**: emit the human's ENTIRE 2-roll window f1..f44 from
    the chain generator's own pieces -- junction phase lists (`_fit_phases`) for the inter-roll
    frames and `roll_stream` at fitted knobs with FAN aim bytes (not his) for both rolls -- and
    require the replay to match feeding the raw DTM **0-ULP**, both actors' positions + Link's
    facing + proc, every frame. This is `reproduces_recorded_roll` lifted to the full chain: the
    search's generators can express the complete recorded plan, junctions included."""
    dtm = seeds.dtm_input_at(env)
    rows = S.rollout_recorded(env, upto=upto)['rows']
    proc = {r['f']: r['proc'] for r in rows}
    rolls = _recorded_rolls(env, upto=upto)

    # Each roll segment's emission span runs from its A frame to its state-6 re-entry (the frame
    # `roll_segment` stops after); the junction owns the frames from there to the next A.
    spans = []
    for (a_f, entry, exit_f) in rolls:
        end = exit_f
        while proc.get(end + 1) is not None and proc.get(end + 1) != 6:
            end += 1
        end += 1                                   # the first MOVE frame back
        spans.append((a_f, end))

    def gen(k):
        for (a_f, end) in spans:
            if a_f <= k <= min(end, upto - 1):
                n = end - a_f + 1
                aim = (int(dtm(a_f).get('stickX', 128)), int(dtm(a_f).get('stickY', 128)))
                knobs = _fit_roll_knobs([dtm(a_f + j) for j in range(min(n, upto - a_f))], aim)
                want_ang, _ = main_stick_decode(*aim)
                fan_aim = next((b for a, b in roll_aim_fan() if a == want_ang), aim)
                return roll_stream(fan_aim, **knobs)(k - a_f)
        # a junction frame: re-emit through the phase reader
        j0 = k
        while j0 > 1 and not any(a <= j0 - 1 <= e for (a, e) in spans):
            j0 -= 1
        nxt = min([a for (a, _e) in spans if a > k], default=upto)
        phases = _fit_phases([dtm(j) for j in range(j0, nxt)])
        i = k - j0
        for (n, sxy, l) in phases:
            if i < n:
                return dict(stickX=sxy[0], stickY=sxy[1], buttons=S.PAD_L if l else 0,
                            triggerL=255 if l else 0)
            i -= n
        raise AssertionError("junction reader fell off at f%d" % k)

    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))

    def trace(fn):
        r = base.clone()
        out = []
        for k in range(1, upto):
            r.step(fn(k))
            out.append((r.link.state, r.link.facing, r.link.pos_x, r.link.pos_z, r.tx, r.tz))
        return out

    def gen_input(k):
        d = dict(gen(k))
        rd = dtm(k)
        d['substickX'] = rd.get('substickX', 128)
        d['substickY'] = rd.get('substickY', 128)
        return d

    rec = trace(lambda k: dtm(k))
    got = trace(gen_input)
    first = next((k + 1 for k, (x, y) in enumerate(zip(rec, got)) if x != y), None)
    return dict(ok=first is None, first_diverge=first, frames=upto - 1, spans=spans)


# --------------------------------------------------------------------------- metrics / pruning

def metrics(run, hl, frames):
    lx, lz = run.link.pos_x, run.link.pos_z
    return dict(herd=hl.along(run.tx, run.tz), frames=frames,
                per_frame=hl.along(run.tx, run.tz) / frames if frames else 0.0,
                lead=hl.lead(lx, lz, run.tx, run.tz),
                lat=hl.lateral(lx, lz) - hl.lateral(run.tx, run.tz),
                dist=math.hypot(lx - run.tx, lz - run.tz),
                followed=run._follow_warned)


def alive(m, *, max_lead=-2.0, max_lat=60.0, axis=AXIS_HERD):
    """Aggressive prune: never overtake Tetra, stay near the herd line, stay in the plow regime.

    ``axis`` (session 135) is the frame the last two clauses are asserted in (`reposition.pair_line`).
    On ``AXIS_PAIR`` they are the SAME two clauses about the pair's own push axis, where ``lead`` is
    minus the separation and the lateral offset is zero -- so "never overtake her" becomes "stay at
    least ``|max_lead|`` u off her" and "stay near the line" is satisfied by construction. Nothing is
    widened; the direction the pair is pushing stops being asserted to be the herd's."""
    if axis == AXIS_PAIR:
        return (not m['followed']) and m['dist'] >= abs(max_lead)
    return (not m['followed']) and m['lead'] <= max_lead and abs(m['lat']) <= max_lat


# --------------------------------------------------------------------------- cycle 1 (from state 2)

def cycle1_candidates(env, hl, *, half_window=0x2000, step=1, nflips=(1, 2, 3),
                      flip_msds=(1.0,), l_windows=((5, 8), (4, 7), (6, 9)), target_css=(None,),
                      beam=40, verbose=False):
    """Sweep the FIRST roll from state 2 and keep the best on-line survivors.

    At state 2 Tetra is ~122 deg BEHIND Link (out of the +-90 cone), so L re-targets straight into
    the proc-7 flip -- no turnaround is needed to start. Branches: ``nflip`` x ``flip_msd`` x the
    REACHABLE roll-facing fan x the L pulse window x the roll's camera target. Returns the surviving
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
            for (want, aim_bytes) in fan:
                for lw in l_windows:
                    for tcs in target_css:
                        ntried += 1
                        run = base.clone()
                        log = list(blog)
                        r = roll_segment(run, aim_bytes, target_cs=tcs, l_window=lw, log=log)
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
                                                   aim_bytes=aim_bytes, l_window=lw,
                                                   roll_facing=r['roll_facing'], target_cs=tcs)))
    out.sort(key=lambda n: -n['m']['per_frame'])
    if verbose:
        print("  tried %d: %d talked, %d never rolled, %d off-line/overtook -> %d survivors"
              % (ntried, ntalk, norol, noff, len(out)))
    return out[:beam]


# --------------------------------------------------------------------------- the 2-roll chain

def junction_gates(jr, hl, frames, *, min_preroll=17.0, axis=AXIS_HERD):
    """The hard junction-endpoint gates (stage 1 of the chain): in the plow regime, on-line-behind
    (`alive`), Tetra OUT of Link's +-90 deg facing cone (the precondition for BOTH the talk-safe
    roll-A and the proc-7 re-target flip), still near contact, the EBS glide retained, and
    **ARMED**: a 1-frame probe step must show the proc-7 flip has FIRED (speedF >= ``min_preroll``,
    so a roll-A pressed now inits at the full clamp(spF*1.5+0.5)=26 -- below +17 it fires weak).
    The flip fires when a toward-Tetra stick ACTS inside proc 7, which (delay-1) needs L delivered
    two junction frames back and the toward stick one back -- the human's own f26/f27 pattern; a
    junction whose pending inputs cannot produce it only ever rolls at +5. Mutates nothing (probes
    a clone). Returns the failure name or None.

    ``axis`` is forwarded to `alive` and nothing else here: every other clause is already about the
    PAIR (the cone, the 100 u contact bound, the armed speedF), which is why this gate keeps its
    whole content when the direction is freed -- and why a freed box cannot produce an endpoint 128 u
    away from her."""
    if jr._follow_warned:
        return 'followed'
    m = metrics(jr, hl, frames)
    if not alive(m, axis=axis):
        return 'offline'
    tb = _bearing((jr.link.pos_x, jr.link.pos_z), (jr.tx, jr.tz))
    if abs(_s16(jr.link.facing - tb)) <= 0x4000:
        return 'in_cone'
    if m['dist'] > 100.0:
        return 'lost_contact'
    if abs(jr.link.speedF) < 15.0:
        return 'stalled'
    probe = jr.clone()
    # A probe has no NEXT frame, so it needs no camera (the look pair stays -- her eye steers the
    # re-aim, and so the speedF read below): knowledge/strategy/the-frame-the-alphabet-shares.md
    probe.camera = None
    probe.step(dict(stickX=128, stickY=128, buttons=0, triggerL=0,
                    substickX=CSTICK_NEUTRAL, substickY=0), csangle=int(jr.csangle))
    if probe.link.speedF < min_preroll:
        return 'unarmed'
    return None


def junction_endpoints(run0, base_log, hl, base_frames, *, jn_keep=30, swing_step=1,
                       n_swings=(2, 3, 4, 5, 6), variants=None):
    """**The junction stage** (stage 1 of any chained cycle): from a post-roll node, sweep the
    junction families, apply the hard gates, dedup converged endpoints, and keep ``jn_keep``.

    Shared by the 2-roll chain (`cycle2_chain`) and the N-cycle herd (`full_herd.extend_cycle`) so
    there is ONE junction stage. Returns ``([dict(run, log, jf, jv, m)], dead_counts)``.

    The keep is deliberately MIXED -- half ranked by on-line-ness, half by shortness: each pure
    ranking measurably drops real winners (s42: jf-first keeps flip-starved endpoints, |lat|-first
    drops the only survivors)."""
    tb = _bearing((run0.link.pos_x, run0.link.pos_z), (run0.tx, run0.tz))
    toward = stick_for_bearing(tb, run0.csangle, msd=1.0)
    kept, seen, dead = [], set(), {}
    if variants is None:
        variants = junction_variants(toward, swing_step=swing_step, n_swings=n_swings)
    for jv in variants:
        jr = run0.clone()
        jlog = list(base_log)
        jf = run_junction(jr, jv['phases'], log=jlog)
        why = junction_gates(jr, hl, base_frames + jf)
        if why:
            dead[why] = dead.get(why, 0) + 1
            continue
        # The tag includes the LAST DELIVERED input: same physics state, different pending
        # delay-1 input = a different flip fate at the roll-A -- collapsing them drops plans.
        last = jlog[-1] if jlog else {}
        tag = (round(jr.link.pos_x, 1), round(jr.link.pos_z, 1), jr.link.facing >> 4,
               round(jr.link.speedF, 2), round(jr.tx, 1), round(jr.tz, 1),
               jr.link.state, int(jr.csangle) >> 4,
               last.get('stickX'), last.get('stickY'),
               int(last.get('buttons', 0)) & S.PAD_L, bool(last.get('triggerL')))
        if tag in seen:
            continue
        seen.add(tag)
        kept.append(dict(run=jr, log=jlog, jf=jf, jv=jv, frames=base_frames + jf,
                         m=metrics(jr, hl, base_frames + jf)))
    kept.sort(key=lambda k: (abs(k['m']['lat']), k['jf']))
    half = kept[:jn_keep - jn_keep // 2]
    rest = [k for k in kept if k not in half]
    rest.sort(key=lambda k: (k['jf'], abs(k['m']['lat'])))
    return half + rest[:jn_keep // 2], dead


def cycle2_chain(env, hl, *, nodes=None, c1_beam=8, half_window2=0x2800, step2=12,
                 l_windows2=((4, 7), (5, 8)), target_css=None, min_roll2=20.0,
                 swing_step=1, n_swings=(2, 3, 4, 5, 6), jn_keep=30, beam=40, verbose=False):
    """**The 2-roll chain search**, two-staged so the junction sweep can be FINE while the expensive
    roll-2 rollouts stay budgeted:

      stage 1 -- from each surviving cycle-1 node, sweep the junction families
      (`junction_variants`: the 1-frame ESS turnaround x nflip, and the human-shaped ESS swing over
      the full low-magnitude alphabet), apply the hard gates (`junction_gates`), dedup converged
      endpoints (fewest-frame representative wins), keep the best ``jn_keep`` per node (fewest
      junction frames, then most on-line);

      stage 2 -- from each kept endpoint, sweep the cycle-2 roll (`roll_facing_fan` x the L
      window), prune talk-unsafe / weak-roll (< ``min_roll2``) / off-line / out-of-regime, and rank
      every survivor by the CHAINED down-herd rate.

    ``target_css`` seeds cycle 1's C-stick slew so the turnaround family's csangle snap window is
    reachable (defaults to the herd-line bearing +- 2048 -- cs ~ the roll-1 facing is what the ESS
    turnaround wants). Returns nodes sorted by 2-roll ``per_frame``."""
    if target_css is None:
        # target_cs sets the post-roll EBS travel and its viable band is ~+-300 BAM (s42 box), so
        # the default is a fine 128-BAM grid over the camera's reachable slew band -- derived bounds.
        cs0 = int(seeds.make_freerun(env).csangle)
        target_css = tuple((cs0 + off) & 0xFFFF for off in range(-1536, 1537, 128))
    if nodes is None:
        nodes = cycle1_candidates(env, hl, half_window=0x2000, step=2,
                                  target_css=target_css, beam=c1_beam, verbose=verbose)
    # Dedup cycle-1 exits by state: stage 1 needs entry-state DIVERSITY, not the top-per_frame few
    # (no junction rescues a bad entry state -- the s42 f21 experiment).
    uniq, cseen = [], set()
    for node in nodes:
        r = node['run']
        ct = (round(r.link.pos_x, 1), round(r.link.pos_z, 1), r.link.facing >> 4,
              round(r.link.speedF, 2), round(r.tx, 1), round(r.tz, 1), int(r.csangle) >> 4)
        if ct in cseen:
            continue
        cseen.add(ct)
        uniq.append(node)
    nodes = uniq
    out = []
    ntried = nr_dead = 0
    jn_dead = {}
    for node in nodes:
        run0 = node['run']
        kept, dead = junction_endpoints(run0, node['log'], hl, node['frames'],
                                        jn_keep=jn_keep, swing_step=swing_step, n_swings=n_swings)
        for k_, v_ in dead.items():
            jn_dead[k_] = jn_dead.get(k_, 0) + v_
        if verbose:
            print("  node %s: %d junction endpoints kept (dead: %s)"
                  % (node['knobs'].get('roll_bam'), len(kept),
                     ' '.join('%s=%d' % kv for kv in sorted(jn_dead.items()))))
        for j in kept:
            fan2 = roll_facing_fan(j['run'], hl.bearing_bam(), half_window2, step2)
            for (want, aim2) in fan2:
                for lw in l_windows2:
                    ntried += 1
                    rr = j['run'].clone()
                    rlog = list(j['log'])
                    seg = roll_segment(rr, aim2, l_window=lw, log=rlog)
                    if seg['talk_unsafe'] or not seg['ok'] or seg['roll_speedF'] is None \
                            or seg['roll_speedF'] < min_roll2:
                        nr_dead += 1
                        continue
                    fr = node['frames'] + j['jf'] + seg['frames']
                    m = metrics(rr, hl, fr)
                    if not alive(m):
                        nr_dead += 1
                        continue
                    out.append(dict(run=rr, log=rlog, frames=fr, m=m,
                                    knobs=dict(c1=node['knobs'], junction=j['jv'],
                                               jframes=j['jf'], roll2_bam=want, aim2=aim2,
                                               l_window2=lw, roll2_facing=seg['roll_facing'],
                                               roll2_speedF=seg['roll_speedF'])))
    out.sort(key=lambda n: -n['m']['per_frame'])
    if verbose:
        print("  chain: %d roll-2 rollouts, %d dead -> %d survivors"
              % (ntried, nr_dead, len(out)))
    return out[:beam]


def confirm_chain(env, hl, node):
    """**The winner-confirmation gate**: re-run a chain node's own delivered input log on a FRESH
    self-contained `FreeRun` (no clones, no search state) and require the endpoint to be
    BIT-IDENTICAL to the search's node -- both actors' positions, Link's facing, csangle -- plus
    exactly two full-speed rolls, every grounded A-press talk-safe, and the whole log in the plow
    regime. Returns ``dict(ok, per_frame, frames, rolls, talk_safe, bit_exact)``."""
    run = seeds.make_freerun(env)
    dtm = seeds.dtm_input_at(env)
    run.pre_seed_input(dtm(0))
    rolls = 0
    in_roll = False
    talk_safe = True
    for d in node['log']:
        if S.a_press_is_talk(run, d):
            talk_safe = False
        run.step(d)
        if run.link.state == FRONT_ROLL:
            if not in_roll:
                rolls += 1
            in_roll = True
        else:
            in_roll = False
    ref = node['run']
    bit_exact = (run.link.pos_x == ref.link.pos_x and run.link.pos_z == ref.link.pos_z
                 and run.link.facing == ref.link.facing and run.tx == ref.tx
                 and run.tz == ref.tz and int(run.csangle) == int(ref.csangle))
    frames = len(node['log'])
    herd = hl.along(run.tx, run.tz)
    return dict(ok=bit_exact and rolls == 2 and talk_safe and not run._follow_warned,
                per_frame=herd / frames if frames else 0.0, frames=frames, rolls=rolls,
                talk_safe=talk_safe, bit_exact=bit_exact)


def _cmd_chain(env, hl, kw):
    import time
    b = human_baseline(env, hl)
    print("HUMAN 2-roll bar: %.1f u / %d f = %.3f u/frame\n" % (b['herd'], b['frames'],
                                                                b['per_frame']))
    t0 = time.perf_counter()
    nodes = cycle2_chain(env, hl, c1_beam=int(kw.get('c1', 48)),
                         half_window2=int(kw.get('window', 0x2800)),
                         step2=int(kw.get('step', 8)), swing_step=int(kw.get('swing', 2)),
                         jn_keep=int(kw.get('jkeep', 16)),
                         beam=int(kw.get('beam', 40)), verbose=True)
    print("\n(%.1f s)  best 2-roll chains (bar %.3f u/f):" % (time.perf_counter() - t0,
                                                              b['per_frame']))
    print("   u/f    herd  frames  junction (jf)              roll2_bam spF    lead    lat")
    for n in nodes[:15]:
        k, m = n['knobs'], n['m']
        jd = "%s %s" % (k['junction']['kind'], k['junction']['phases'])
        print("  %6.3f %+7.1f  %3d   %-28s %6d %5.1f  %+6.1f %+6.1f"
              % (m['per_frame'], m['herd'], n['frames'], jd[:28] + " (%d)" % k['jframes'],
                 k['roll2_bam'], k['roll2_speedF'], m['lead'], m['lat']))
    if nodes:
        best = nodes[0]
        verdict = "CLEARS" if best['m']['per_frame'] > b['per_frame'] else "DOES NOT CLEAR"
        print("\n  => best 2-roll rate %.3f u/frame %s the human's %.3f"
              % (best['m']['per_frame'], verdict, b['per_frame']))
        c = confirm_chain(env, hl, best)
        print("  confirm (fresh replay of the winner's own log): bit_exact=%s rolls=%d "
              "talk_safe=%s -> %.3f u/f  %s"
              % (c['bit_exact'], c['rolls'], c['talk_safe'], c['per_frame'],
                 "CONFIRMED" if c['ok'] else "NOT CONFIRMED"))


def _cmd_fan(env, hl, kw):
    import time
    b = human_baseline(env, hl)
    print("HUMAN: %.1f u / %d f = %.3f u/frame\n" % (b['herd'], b['frames'], b['per_frame']))
    t0 = time.perf_counter()
    nodes = cycle1_candidates(env, hl, half_window=int(kw.get('window', 0x2000)),
                              step=int(kw.get('step', 1)), beam=int(kw.get('beam', 20)),
                              verbose=True)
    print("\n(%.1f s)  best cycle-1 candidates:" % (time.perf_counter() - t0))
    print("  roll_bam  facing  nflip msd  L-pulse  frames   herd    u/f    lead    lat")
    for n in nodes[:20]:
        k, m = n['knobs'], n['m']
        print("  %6d  %6s    %d  %.2f  [%d,%d)    %3d   %+7.1f %6.2f  %+6.1f %+6.1f"
              % (k['roll_bam'], k['roll_facing'], k['nflip'], k['flip_msd'],
                 k['l_window'][0], k['l_window'][1], n['frames'],
                 m['herd'], m['per_frame'], m['lead'], m['lat']))


def _cmd_contain(env):
    """The containment sanity check + the measured in-roll stick inertness."""
    r = contains_human(env)
    print("CONTAINMENT -- is the human's own input a member of the search space?\n")
    print("  aim alphabet (`reachable_stick_fan`, full byte grid): %d distinct aims" % r['aims_total'])
    print("  recorded main-stick aims not in the alphabet: %d %s"
          % (len(r['aims_missing']), r['aims_missing'][:5] if r['aims_missing'] else ''))
    print("\n  recorded roll segments, fitted to `roll_stream` knobs:")
    for d in r['rolls']:
        k = d['knobs'] or {}
        print("    A@f%-3d roll f%d-%d  aim %-10s -> hold=%s a_hold=%s L=[%s,%s) post=%s   %s"
              % (d['a_frame'], d['entry'], d['exit'], str(d['aim']), k.get('hold'),
                 k.get('a_hold'), k.get('l_window', ('?', '?'))[0], k.get('l_window', ('?', '?'))[1],
                 k.get('post'), 'EMITTABLE' if d['ok'] else 'NOT EMITTABLE'))
    print("\n  => %s\n" % ('CONTAINED' if r['ok'] else 'NOT CONTAINED -- the search space is too narrow'))

    print("FIDELITY -- does the GENERATED stream reproduce the recorded roll 0-ULP?")
    for w in range(len(r['rolls'])):
        f = reproduces_recorded_roll(env, which=w)
        print("    roll %d (f%d-%d): human aim %s -> generated %s   %d frames, first diverge %s   %s"
              % (w, f['entry'], f['exit'], f['aim_human'], f['aim_generated'], f['frames'],
                 f['first_diverge'], '0-ULP' if f['ok'] else 'DIVERGES'))
    print()

    inert = roll_is_stick_inert(env)
    print("IN-ROLL MAIN-STICK INERTNESS (recorded roll 1, from the human's own entry):")
    for s, (first, fac) in inert['variants'].items():
        print("    mid-roll stick %-10s first diverging frame: %-6s end facing %d (rec %d)"
              % (str(s), first, fac, inert['rec_facing']))
    print("\n  => the main stick is %s during a roll\n"
          % ('INERT (zero-branch segment, 0-ULP)' if inert['ok'] else 'NOT inert'))


def main(argv):
    import warnings
    warnings.simplefilter('ignore')
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    cmd = argv[0] if argv else 'human'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'fan':
        _cmd_fan(env, hl, kw)
    elif cmd == 'chain':
        _cmd_chain(env, hl, kw)
    elif cmd == 'contain':
        _cmd_contain(env)
    elif cmd == 'human':
        b = human_baseline(env, hl)
        print("HUMAN 2-roll baseline from state 2: %.1f u over %d frames = %.3f u/frame "
              "(%d roll frames)" % (b['herd'], b['frames'], b['per_frame'], b['rolls']))
        print("  the bar: a 2-roll plan must exceed %.3f u/frame" % b['per_frame'])
    else:
        print("usage: python -m harness.tetrapush.two_roll {human | contain | fan | chain}")


if __name__ == '__main__':
    main(sys.argv[1:])
