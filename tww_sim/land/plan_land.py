#!/usr/bin/env python3
"""plan_land.py - LAND input planner: init LandState + world target (x, z) -> input seq.

The north-star `superswim-land-route-planner-goal`: given a `LandState` and a target world
position (x, z) as an arbitrary float, produce a controller stick sequence that walks/steers
Link there. The bit-exact forward model is `superswim.land.LandState.step` (walk/ATN/roll/turns,
speedF-driven position); this is the search/planning layer on top of it.

STATUS: milestone 1 -- straight-walk reach, BOTH live-confirmed bit-exact on the open +z corridor:
  * `reach_straight` -- aim a full-deflection stick at the live bearing each frame, then release to
    coast to rest; sweep the release frame for the min resting distance. ~0.23u stop (full+neutral
    only, bit-exact live: SIM-vs-LIVE 0.0003u).
  * `reach_precise` -- a proportional-speed glide that stays in motion into a crawl, then a
    truncation search picks the release; ~0.10u stop (the smooth-walk floor), bit-exact live (0.0015u).
Milestone 2 (C-stick curved reach), the land A* (mirror `plan.py`), roll/turn tech, tap-inch (sub-0.1u
stops) and basin scoring are follow-ups. v1 targets OPEN GROUND -- wall/pillar collision is unported.

LIVE-FAITHFUL STICKS (hard-won): full deflection (255/1) and neutral (128,128) are bit-exact; a genuine
partial magnitude (msd 0.3-0.7) is bit-exact; but the sim's msd = min(hypot/54, 1) CAPS, so near-full
raw sticks (e.g. 128,197) read 1.0 in the sim while live PADClamp gives ~0.96 -- NEVER emit that
ambiguous cap-boundary cell. `stick_for_bearing` emits the true corner for msd>=1 and msd*54 below it.

COORDINATES (from land.py's position integration -- the single source of truth):
    pos_x += speedF * sin(travel);  pos_z += speedF * cos(travel)   (travel = s16 current.angle.y)
so travel is an s16 angle measured FROM +z TOWARD +x. The world bearing to a target displacement
(dx, dz) is therefore `atan2(dx, dz)` -> s16 (see `world_angle_s16`). To WALK toward a world
bearing theta we want the walk want-target `m34E8 == theta`; since `m34E8 = m34DC(stick) + csangle`
and `m34DC = stickAngle + 0x8000`, the inverse full-deflection stick is `stick_for_bearing`.
"""
from __future__ import annotations
import heapq
import math

from ..core.mathlib import deg_to_s16, s16_signed, ARROW_STICK_DEADZONE
from .land import LandState, WAIT, FREE_WAIT

# Dead-zoned deflection magnitude (per axis) before the 15-unit dead zone is added back per axis (see
# stick_for_bearing). _STICK_R + DZ == 127 -> cardinals hit the full corners (255/1). See land-movement.md.
_STICK_R = 112.0
NEUTRAL = (128, 128)


def world_angle_s16(dx, dz):
    """World bearing of a displacement (dx, dz) as an s16 travel angle (0 = +z, 0x4000 = +x).
    Matches land.py's `pos_x += d*sin(travel); pos_z += d*cos(travel)`."""
    return deg_to_s16(math.degrees(math.atan2(dx, dz)) % 360.0)


def dist2d(state, tx, tz):
    return math.hypot(tx - state.pos_x, tz - state.pos_z)


def stick_for_bearing(theta_s16, csangle=0, msd=1.0):
    """Inverse of the walk want-target: an (sx, sy) whose camera-relative walk target
    `m34E8 = m34DC + csangle` equals the world bearing `theta_s16`. With a frozen camera
    (csangle held) this points the walk at world angle theta (see land.py `_set_stick_data`).

    `msd` (0..1) sets the target mStickDistance = min(hypot(dz)/54, 1): 1.0 = full deflection
    (walk cap 17); a small msd creeps (the speed cap is msd*(17*msd) = 17*msd^2, so msd~0.06 is
    ~0.06 u/frame) -- used by `reach_precise` for the sub-unit final approach. The dead-zoned
    magnitude is msd*54; the dead zone (15) is added back per axis so `_deadzone` recovers it."""
    m34dc = (int(theta_s16) - int(csangle)) & 0xFFFF          # m34E8 = m34dc + csangle
    stick_s16 = (m34dc - 0x8000) & 0xFFFF                     # m34dc = stickAngle + 0x8000
    phi = math.radians(stick_s16 / 65536.0 * 360.0)          # stick_angle_deg convention
    # Dead-zoned magnitude for a target mStickDistance: full (msd>=1) -> the true corner (255/1);
    # partial (msd<1) -> msd*54. LIVE-VALID only for Y<=191 or 255 (sim /54 over-reads Y192-254; land-movement.md).
    if msd >= 1.0:
        r = _STICK_R
    else:
        r = min(max(msd, 0.0), 1.0) * 54.0
    ax = r * math.sin(phi)                                   # desired dead-zoned x  (_deadzone(sx))
    ay = -r * math.cos(phi)                                  # desired dead-zoned y  (_deadzone(sy))
    # Add the dead zone back per axis so _deadzone recovers (ax, ay) and the bearing is preserved.
    # Snap the near-zero axis to center (a cardinal bearing -> sin/cos 180 is ~1e-14, not 0).
    dz = ARROW_STICK_DEADZONE
    sx = 128.0 + (math.copysign(abs(ax) + dz, ax) if abs(ax) > 1e-6 else 0.0)
    sy = 128.0 + (math.copysign(abs(ay) + dz, ay) if abs(ay) > 1e-6 else 0.0)
    return (max(0, min(255, int(round(sx)))), max(0, min(255, int(round(sy)))))


def _walk_then_coast(seed, tx, tz, n_walk, coast_max=48):
    """Simulate from `seed` (a REST state -- clone() only preserves rest anim): walk `n_walk`
    frames aiming a full-deflection stick at the LIVE bearing to (tx, tz) each frame, then feed
    neutral until Link comes to rest (or `coast_max`). Returns (resting_dist, seq, end_state)."""
    s = seed.clone()
    seq = []
    for _ in range(n_walk):
        th = world_angle_s16(tx - s.pos_x, tz - s.pos_z)
        sx, sy = stick_for_bearing(th, s.csangle)
        s.step(sx, sy)
        seq.append((sx, sy))
    for _ in range(coast_max):
        s.step(*NEUTRAL)
        seq.append(NEUTRAL)
        if s.state in (WAIT, FREE_WAIT) and abs(s.nspeed) < 1e-6:
            break
    return dist2d(s, tx, tz), seq, s


def reach_straight(seed, tx, tz, max_walk=240):
    """STRAIGHT-WALK reach: return the input sequence whose RESTING position is closest to the
    target (tx, tz). Sweeps the release frame `n_walk` (walk-then-coast) and keeps the minimum
    resting distance -- each trial re-simulates from the rest `seed`, so the ported foot-anim
    engine is seeded cleanly every time (clone() can't carry mid-walk anim state).

    Returns dict: seq, resting_dist, n_walk, end (LandState), n_frames.
    """
    best = None
    for n in range(1, max_walk + 1):
        d, seq, end = _walk_then_coast(seed, tx, tz, n)
        if best is None or d < best['resting_dist']:
            best = {'seq': seq, 'resting_dist': d, 'n_walk': n, 'end': end,
                    'n_frames': len(seq)}
        # Resting distance is unimodal up to the first overshoot; past it the live-bearing re-aim
        # orbits/reverses back (messy). Stop at the FIRST local minimum -- the clean straight reach.
        elif n > best['n_walk'] + 8 and d > best['resting_dist'] + 5.0:
            break
    return best


def reach_precise(seed, tx, tz, eps=0.05, k=0.5, min_crawl=0.043, turnback=1.0,
                  max_frames=4000):
    """PRECISE reach: rest within ~eps of (tx, tz) (sub-unit), where whole-frame full-speed
    `reach_straight` is limited to ~15u release granularity. A proportional-speed feedback
    controller (the exact sim IS the model): aim a stick at the LIVE bearing each frame, scaling
    the stick MAGNITUDE so Link's target speed tracks `k * remaining_distance` -- he stays in
    MOTION the whole way, bleeding speed smoothly so he is already crawling (~`min_crawl` u/frame)
    when he arrives, then coasts to rest within one crawl step.

    Why not brake to a stop then creep: from a STANDSTILL the walk needs msd > 0.5 to move at all
    (the setSpeedAndAngleNormal speed-scale gate 0.5 - 0.5*|v|/max), so a slow crawl can't be
    RESTARTED from rest -- it must be sustained by never fully stopping. And a full-speed neutral
    release coasts ~49u (the whole 17->0 decel arc), far past any fine release point. Hence the
    stay-in-motion glide. Speed cap = 17*msd^2, so msd = sqrt(target_speed / 17); msd is floored at
    the movement gate (min_crawl -> msd ~ 0.05) and capped at 1.0 (full).

    Simulated ONCE from the REST seed (clone-safe -- no mid-walk clone, foot-anim stays bit-exact).
    Returns dict: seq, resting_dist, end (LandState), n_frames.
    """
    # Phase A/B: glide into a fixed crawl, feeding PAST the target (2-frame latency makes a proportional
    # controller overshoot) -- record the whole glide+crawl and pick the cut below, not the live break.
    s = seed.clone()
    walk = []
    prev = dist2d(s, tx, tz)
    near = False
    while len(walk) < max_frames:
        rem = dist2d(s, tx, tz)
        if rem < turnback:
            near = True
        if near and rem > prev:                    # first turnback after arriving = crawl overshoot;
            break                                  # stop before the controller limit-cycles around it
        prev = rem
        target_speed = min(max(k * rem, min_crawl), float(LandState.MAX_NSPEED))
        msd = min(max(math.sqrt(target_speed / float(LandState.MAX_NSPEED)), 0.051), 1.0)
        th = world_angle_s16(tx - s.pos_x, tz - s.pos_z)
        stick = stick_for_bearing(th, s.csangle, msd)
        s.step(*stick)
        walk.append(stick)

    # Phase C: truncation search -- the crawl tail advances ~min_crawl u/frame, so cutting the walk at
    # the right frame + coasting lands within a crawl step. Re-sim walk[:cut]+coast per cut; keep min.
    def _walk_then_rest(cut):
        t = seed.clone()
        seq = list(walk[:cut])
        for st in seq:
            t.step(*st)
        for _ in range(30):
            if t.state in (WAIT, FREE_WAIT) and abs(t.nspeed) < 1e-6:
                break
            t.step(*NEUTRAL)
            seq.append(NEUTRAL)
        return dist2d(t, tx, tz), seq, t

    best = None
    for cut in range(max(0, len(walk) - 60), len(walk) + 1):
        d, seq, t = _walk_then_rest(cut)
        if best is None or d < best[0]:
            best = (d, seq, t)
    d, seq, t = best
    return {'seq': seq, 'resting_dist': d, 'end': t, 'n_frames': len(seq)}


def seq_string(seq):
    """Compact per-frame stick string (matches the dolphin seq convention): 'sx,sy' per frame,
    run-length collapsed as 'sx,sy xN'."""
    out = []
    for stick in seq:
        tok = f"{stick[0]},{stick[1]}"
        if out and out[-1][0] == tok:
            out[-1][1] += 1
        else:
            out.append([tok, 1])
    return " ".join(t if n == 1 else f"{t} x{n}" for t, n in out)
