#!/usr/bin/env python3
"""plan_land.py - LAND input planner: init LandState + world target (x, z) -> input seq.

The north-star `superswim-land-route-planner-goal`: given a `LandState` and a target world
position (x, z) as an arbitrary float, produce a controller stick sequence that walks/steers
Link there. The bit-exact forward model is `superswim.land.LandState.step` (walk/ATN/roll/turns,
speedF-driven position); this is the search/planning layer on top of it.

STATUS: milestone 1 -- straight-walk reach on the open +z corridor:
  * `reach_straight` -- aim a full-deflection stick at the live bearing each frame, then release to
    coast to rest; sweep the release frame for the min resting distance. Live-confirmed bit-exact
    (SIM-vs-LIVE 0.0003u). NOTE: the rest is target-SENSITIVE (the 17u full-speed step + fixed ~49u
    coast lands rest on a coarse lattice) -- 0.1-9u depending on target, not a uniform floor.
  * `reach_precise` -- a proportional-speed glide into a crawl, then a truncation search picks the
    release. Also target-sensitive (0.1-9u); the old "0.10u floor" held only near favourable targets.
  * `reach_freeze` -- ROBUST float-perfect stop via the C-up speed cancel: cruise -> sustained
    msd-0.5 crawl -> dedup drill. Rests within a few ULP (< 0.001u) of ANY on-axis target, all sticks
    live-valid. This is the sub-0.1u tech (supersedes reach_straight/precise for exact stops). The
    approach physics (why you must arrive slow, the msd-0.5 crawl floor) is in land-movement.md.
Milestone 2 (C-stick curved reach), the land A* (mirror `plan.py`), roll/turn tech, off-axis freeze
(needs the octagon clamp) and basin scoring are follow-ups. v1 targets OPEN GROUND -- collision unported.

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
from collections import deque

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


def _coast_to_rest(state, tx, tz, coast_max=48):
    """Feed neutral from a CLONE of `state` until Link comes to rest (or `coast_max`), leaving the
    source untouched. Mid-walk clone is bit-exact, so the coast is identical to re-simulating the
    whole prefix. Returns (resting_dist, coast_frames, end_state)."""
    c = state.clone()
    n = 0
    for _ in range(coast_max):
        c.step(*NEUTRAL)
        n += 1
        if c.state in (WAIT, FREE_WAIT) and abs(c.nspeed) < 1e-6:
            break
    return dist2d(c, tx, tz), n, c


def reach_straight(seed, tx, tz, max_walk=240, coast_max=48):
    """STRAIGHT-WALK reach: return the input sequence whose RESTING position is closest to the
    target (tx, tz). Walk the live-bearing full-deflection glide ONCE; at each release frame clone
    the walk state and coast that clone to rest, keeping the minimum resting distance. Because the
    walk is one deterministic trajectory and clone() is bit-exact mid-walk, this is identical to the
    old per-release re-simulation but O(n) instead of O(n^2) in walk steps.

    Returns dict: seq, resting_dist, n_walk, end (LandState), n_frames.
    """
    walk = seed.clone()
    walk_seq = []
    best = None
    for n in range(1, max_walk + 1):
        th = world_angle_s16(tx - walk.pos_x, tz - walk.pos_z)
        sx, sy = stick_for_bearing(th, walk.csangle)
        walk.step(sx, sy)
        walk_seq.append((sx, sy))
        d, coast_n, end = _coast_to_rest(walk, tx, tz, coast_max)
        if best is None or d < best[0]:
            best = (d, n, coast_n, end)
        # Resting distance is unimodal up to the first overshoot; past it the live-bearing re-aim
        # orbits/reverses back (messy). Stop at the FIRST local minimum -- the clean straight reach.
        elif n > best[1] + 8 and d > best[0] + 5.0:
            break
    d, n_walk, coast_n, end = best
    seq = list(walk_seq[:n_walk]) + [NEUTRAL] * coast_n
    return {'seq': seq, 'resting_dist': d, 'n_walk': n_walk, 'end': end, 'n_frames': len(seq)}


# The C-up speed cancel locks position FREEZE_LATENCY frames after the neutral+C-up input (2-frame
# latency + 1 cLib decel, then link_state->1); the sim reads it with zero new code. land-movement.md.
FREEZE_LATENCY = 3
_CUT_SPAN = 60          # Phase-C / freeze sweep window: the last _CUT_SPAN+1 crawl frames near arrival


def _live_valid_msd(msd):
    """Snap msd out of the live-divergent band (0.889, 1): those map to stick Y in [192,254], where
    the sim's /54 magnitude over-reads live PADClamp -- to the nearest live-valid magnitude (a <=0.889
    partial, or 1.0 = the true full corner). See land-movement.md "Live-valid stick magnitudes"."""
    if msd <= 0.889:
        return msd
    return 1.0 if msd >= 0.9445 else 0.889


def _glide(seed, tx, tz, k, min_crawl, turnback, max_frames, clamp_msd=False):
    """Proportional-speed glide toward (tx, tz): aim the live bearing each frame, scaling the stick
    magnitude so the target speed tracks k*remaining -- Link stays in MOTION into a crawl (~min_crawl
    u/frame) and feeds PAST the target (the 2-frame latency overshoots). Speed cap = 17*msd^2, so
    msd = sqrt(target_speed/17), floored at the movement gate and capped at 1. `clamp_msd` keeps every
    emitted stick live-valid (snaps out of the Y192-254 band) for plans that must run on console.
    Snapshots a clone each frame into a rolling buffer (the last _CUT_SPAN+1 frames straddling closest
    approach -- bounds memory for any walk length; mid-walk clone is bit-exact). Returns (walk, snaps)."""
    s = seed.clone()
    walk = []
    snaps = deque([s.clone()], maxlen=_CUT_SPAN + 1)   # snaps[i] = state after applying walk[:i]
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
        if clamp_msd:
            msd = _live_valid_msd(msd)
        th = world_angle_s16(tx - s.pos_x, tz - s.pos_z)
        stick = stick_for_bearing(th, s.csangle, msd)
        s.step(*stick)
        walk.append(stick)
        snaps.append(s.clone())
    return walk, snaps


def reach_precise(seed, tx, tz, eps=0.05, k=0.5, min_crawl=0.043, turnback=1.0,
                  max_frames=4000):
    """PRECISE reach: rest within ~eps of (tx, tz) (sub-unit), where whole-frame full-speed
    `reach_straight` is limited to ~15u release granularity. A proportional-speed feedback
    controller (the exact sim IS the model) glides into a crawl, then a truncation search picks the
    release: cut the glide at each candidate frame + coast to rest, keep the min-distance rest.

    Why not brake to a stop then creep: from a STANDSTILL the walk needs msd > 0.5 to move at all
    (the setSpeedAndAngleNormal speed-scale gate 0.5 - 0.5*|v|/max), so a slow crawl can't be
    RESTARTED from rest -- it must be sustained by never fully stopping. And a full-speed neutral
    release coasts ~49u (the whole 17->0 decel arc). Rests ~0.10u from target (the smooth-walk floor);
    sub-0.1u needs the C-up freeze (`reach_freeze`) or tap-inch hops.

    Returns dict: seq, resting_dist, end (LandState), n_frames.
    """
    walk, snaps = _glide(seed, tx, tz, k, min_crawl, turnback, max_frames)
    # Truncation search -- the crawl tail advances ~min_crawl u/frame, so cutting the walk at the
    # right frame + coasting lands within a crawl step. Clone each buffered snapshot and coast; keep
    # the min. O(n) (no prefix re-sim), identical to the old re-sim since clone is bit-exact.
    cut_base = len(walk) - (len(snaps) - 1)     # rolling buffer's leftmost snapshot's cut index
    best = None
    for off, snap in enumerate(snaps):
        t = snap.clone()
        coast = 0
        for _ in range(30):
            if t.state in (WAIT, FREE_WAIT) and abs(t.nspeed) < 1e-6:
                break
            t.step(*NEUTRAL)
            coast += 1
        d = dist2d(t, tx, tz)
        if best is None or d < best[0]:
            best = (d, cut_base + off, coast, t)
    d, cut, coast, t = best
    seq = list(walk[:cut]) + [NEUTRAL] * coast
    return {'seq': seq, 'resting_dist': d, 'end': t, 'n_frames': len(seq)}


def _freeze_pos(state):
    """The FLOAT-PERFECT freeze position if the C-up speed cancel is issued from a mid-walk `state`:
    the sim position FREEZE_LATENCY neutral frames on (clone -> 3 neutrals -> read pos), where the
    real cancel locks link_state. Leaves `state` untouched. See knowledge/mechanics/land-movement.md."""
    c = state.clone()
    for _ in range(FREEZE_LATENCY):
        c.step(*NEUTRAL)
    return c


# The min STABLE crawl: msd 0.5 sustains nspeed~4.25 -> ~1u/frame while moving; below 0.5 the walk
# collapses to rest (movement gate), so Phase 1 cruises first. Why ~1u is the floor: land-movement.md.
MSD_CRAWL = 0.5


def _ulp32(x):
    """The float32 ULP near |x| (positions are f32). Sizes the drill's dedup bucket and early-exit
    floor without assuming a fixed corridor magnitude."""
    if x == 0.0:
        return 2.0 ** -149
    _, e = math.frexp(abs(x))          # 2**(e-1) <= |x| < 2**e  ->  unbiased exponent = e-1
    return 2.0 ** (e - 24)             # ulp = 2**(exp-23) = 2**((e-1)-23)


def _drill_candidates(state, tx, tz):
    """The fine input lattice at a slow near-target state: NEUTRAL (keep decelerating) plus EVERY
    distinct live-valid integer walk stick aimed at the live bearing. The magnitude is scanned finely
    (1/1000) so no distinct integer cell is skipped; the (0.889, 1) band (stick Y in 192-254) is
    excluded -- the sim's /54 magnitude over-reads live PADClamp there (land-movement.md)."""
    th = world_angle_s16(tx - state.pos_x, tz - state.pos_z)
    out = [NEUTRAL]
    seen = {NEUTRAL}
    for j in range(2, 1001):
        msd = j / 1000.0
        if 0.889 < msd < 1.0:
            continue
        stick = stick_for_bearing(th, state.csangle, min(msd, 1.0))
        if stick not in seen:
            seen.add(stick)
            out.append(stick)
    return out


def reach_freeze(seed, tx, tz, coarse_gap=60.0, max_frames=4000, drill_back=8, beam_width=96):
    """FLOAT-PERFECT reach via the C-up speed cancel: place the FROZEN float within a ULP or two of
    (tx, tz). Issue the cancel (one half-L frame, then neutral stick + C-stick full up) mid-motion and
    Link's position locks FREEZE_LATENCY frames later -- which the sim reads with zero new code
    (`_freeze_pos`). Because the freeze truncates the ~49u decel coast to a hard lock, a slow approach
    can place the frozen float almost anywhere.

    THREE phases, each O(1)-per-candidate on the bit-exact mid-walk clone:
      1. cruise full-speed until the freeze is within `coarse_gap` of the target;
      2. a sustained msd-0.5 crawl (`MSD_CRAWL`, the min STABLE crawl ~1u/frame), snapshotting each
         frame until the freeze crosses the target. This gives a uniform fine straddle for ANY target
         -- unlike a proportional glide, which overshoots-at-speed on short trips and stalls to a dead
         stop on long ones (the freeze coast scales with speed, so you must arrive SLOW to arrive fine);
      3. a dedup-by-freeze-position beam drill from `drill_back` crawl frames before the crossing:
         branch over `_drill_candidates` (neutral + the live-valid integer sticks), evaluate a freeze
         after each, and keep a frontier deduped by quantized freeze position and capped to those
         nearest the target. This fills the ~1u crawl step down to the float floor.

    Robust on the open +z corridor: every target rests within ~1-4 ULP (< 0.0006u), all sticks
    live-valid (msd<=0.889 or the full corner), and the whole seq re-simulates to the reported freeze.

    SCOPE: on-axis / +z corridor (like milestone 1). An OFF-AXIS target's crawl emits full-deflection
    DIAGONAL sticks that need the octagon clamp -- the separate open decode issue (see the
    advancewith-off-axis lesson) -- so off-axis freeze plans are not yet live-valid.

    The approach + cancel hold a FROZEN camera (centered C-stick) so csangle stays put. Returns dict:
    seq (approach prefix + the FREEZE_LATENCY cancel tail), freeze_dist, freeze_pos (x, z), end
    (LandState frozen), n_frames. Mechanics: knowledge/mechanics/land-movement.md; model:
    knowledge/model/land-planner.md.
    """
    dx, dz = tx - seed.pos_x, tz - seed.pos_z
    norm = math.hypot(dx, dz)
    ux, uz = (dx / norm, dz / norm) if norm > 1e-9 else (0.0, 1.0)

    def proj(px, pz):                  # signed distance along the approach dir PAST the target
        return (px - tx) * ux + (pz - tz) * uz

    def fdist(state):
        e = _freeze_pos(state)
        return math.hypot(tx - e.pos_x, tz - e.pos_z), e

    # Phase 1 -- cruise full-speed until the freeze is within coarse_gap of the target.
    s = seed.clone()
    pre = []
    while len(pre) < max_frames:
        _, e = fdist(s)
        if proj(e.pos_x, e.pos_z) >= -coarse_gap:
            break
        th = world_angle_s16(tx - s.pos_x, tz - s.pos_z)
        stick = stick_for_bearing(th, s.csangle, 1.0)
        s.step(*stick)
        pre.append(stick)

    # Phase 2 -- sustained msd-0.5 crawl; snapshot each frame until the freeze crosses the target.
    snaps = [(s.clone(), list(pre))]
    while len(pre) < max_frames:
        th = world_angle_s16(tx - s.pos_x, tz - s.pos_z)
        stick = stick_for_bearing(th, s.csangle, MSD_CRAWL)
        s.step(*stick)
        pre.append(stick)
        snaps.append((s.clone(), list(pre)))
        _, e = fdist(s)
        if proj(e.pos_x, e.pos_z) > 0.0:
            break

    # closest freeze over the crawl, and the last snapshot still SHORT of the target (drill seed).
    best = None
    ci = 0
    for i, (st, p) in enumerate(snaps):
        d, e = fdist(st)
        if best is None or d < best[0]:
            best = (d, e, p)
        if proj(e.pos_x, e.pos_z) <= 0.0:
            ci = i

    # Phase 3 -- dedup-by-freeze-position beam drill from drill_back crawl frames before the crossing.
    ulp = _ulp32(tz)
    bucket = ulp * 0.25                # ~1/4 ULP: dedups true duplicates, keeps distinct freezes apart
    start = max(0, ci - drill_back)
    st0, p0 = snaps[start]
    _, e0 = fdist(st0)
    frontier = {round(proj(e0.pos_x, e0.pos_z) / bucket): (st0, p0)}
    for _ in range(drill_back + 8):
        nxt = {}
        for st, p in frontier.values():
            for stick in _drill_candidates(st, tx, tz):
                c = st.clone()
                c.step(*stick)
                d, e = fdist(c)
                if d < best[0]:
                    best = (d, e, p + [stick])
                pj = proj(e.pos_x, e.pos_z)
                if pj <= 0.02:         # keep the still-short-of-target frontier
                    key = round(pj / bucket)
                    if key not in nxt:
                        nxt[key] = (c, p + [stick])
        if not nxt:
            break
        if len(nxt) > beam_width:      # cap to the freezes nearest the target (key ~ proj/bucket)
            nxt = dict(sorted(nxt.items(), key=lambda kv: abs(kv[0]))[:beam_width])
        frontier = nxt
        if best[0] <= ulp * 1.01:      # hit the float floor -- no point drilling finer
            break

    d, end, prefix = best
    seq = list(prefix) + [NEUTRAL] * FREEZE_LATENCY
    return {'seq': seq, 'freeze_dist': d, 'freeze_pos': (end.pos_x, end.pos_z),
            'end': end, 'n_frames': len(seq)}


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
