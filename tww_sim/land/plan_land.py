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
import struct
from collections import deque

from ..core.mathlib import deg_to_s16, s16_signed, ARROW_STICK_DEADZONE
from .land import LandState, WAIT, FREE_WAIT, MOVE, FRONT_ROLL

# Dead-zoned deflection magnitude (per axis) before the 15-unit dead zone is added back per axis (see
# stick_for_bearing). _STICK_R + DZ == 127 -> cardinals hit the full corners (255/1). See land-movement.md.
_STICK_R = 112.0
NEUTRAL = (128, 128)


def _f32_bits(x):
    """The float32 bit pattern of `x` -- for bit-exact (0-ULP) freeze-position equality checks."""
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


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


# Fewest-frame bit-exact freeze -- the START crawl (`reach_freeze(min_frames=True)`): from-rest fine crawl
# + full cruise + C-up, ~+7 over the full-up floor. Model + delta-prediction filter: land-planner.md.

_FREEZE_PRED_BAND = 0.5          # predicted |freeze - T| under this -> exact-check (coast model err <=~0.3u)
_FREEZE_CAP_SCAN = 16            # frames to reach the 17u cap from the slowest start crawl


def _freeze_coast_model(seed, stick_full, ncruise=260):
    """Build the freeze predictor from a STEADY full-speed reference cruise off `seed`: the coast table
    (sorted `anim_fc0` -> freeze coast) plus the per-frame pos rate (+17), the fc0 rate (+2.3), and the
    fc0 wrap (`anim_fc0` loops at the walk anim's frameMax ~32). One cheap cruise, reused across every
    candidate. The cruise must be seeded PAST the accel ramp (the from-rest idle/accel frames run a
    different anim phase, fc0 ~70 -> they'd corrupt the steady-walk table + wrap). See land-planner.md."""
    s = seed.clone()
    cap = float(LandState.MAX_NSPEED)
    prev = False
    for _ in range(_FREEZE_CAP_SCAN):        # cruise to the steady 17u cap first
        at_cap = (s.nspeed == cap)
        if at_cap and prev:
            break
        prev = at_cap
        s.step(*stick_full)
    fcs, coasts, poss = [], [], []
    for _ in range(ncruise):
        fcs.append(s.anim_fc0)
        coasts.append(_freeze_pos(s).pos_z - s.pos_z)
        poss.append(s.pos_z)
        s.step(*stick_full)
    pos_rate = sorted(poss[i + 1] - poss[i] for i in range(len(poss) - 1))[len(poss) // 2]
    # fc0 advances +fc0_rate/frame then wraps at frameMax; read both from consecutive deltas.
    ups = [fcs[i + 1] - fcs[i] for i in range(len(fcs) - 1) if fcs[i + 1] >= fcs[i]]
    fc0_rate = sorted(ups)[len(ups) // 2]
    fc0_max = max(fcs) + fc0_rate            # a wrap resets to ~0, so max+one step ~= frameMax
    for i in range(len(fcs) - 1):            # refine from an observed wrap: max = prev + rate - next
        if fcs[i + 1] < fcs[i]:
            fc0_max = fcs[i] + fc0_rate - fcs[i + 1]
            break
    order = sorted(range(len(fcs)), key=lambda i: fcs[i])
    return ([fcs[i] for i in order], [coasts[i] for i in order], pos_rate, fc0_rate, fc0_max)


def _freeze_coast_of(model, fc0):
    """Nearest-neighbour freeze coast for a phase `fc0` (wrap-aware) from the reference model."""
    import bisect as _bisect
    fc0s, coasts, _, _, fc0_max = model
    fc0 %= fc0_max
    i = _bisect.bisect_left(fc0s, fc0)
    best_d, best_c = 1e18, coasts[0]
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(fc0s):
            d = abs(fc0s[j] - fc0)
            if d < best_d:
                best_d, best_c = d, coasts[j]
    for fj, cj in ((fc0s[0] + fc0_max, coasts[0]), (fc0s[-1] - fc0_max, coasts[-1])):
        if abs(fj - fc0) < best_d:
            best_d, best_c = abs(fj - fc0), cj
    return best_c


def _freeze_start_lattice(seed, tx, tz):
    """The from-rest start-crawl stick lattice aimed at the target bearing, FAST->slow (so the DFS's
    first exact hit is the fewest-frame plan): the full corner, then every distinct live-valid partial
    down to the movement gate (msd 0.52..0.889 -> stick Y 171..191 on-axis). msd>0.5 is required to
    move from a standstill; the (0.889, 1) band is skipped (live-divergent). See land-planner.md."""
    th = world_angle_s16(tx - seed.pos_x, tz - seed.pos_z)
    full = stick_for_bearing(th, seed.csangle, 1.0)
    out = [full]
    seen = {full}
    for j in range(889, 519, -1):            # msd 0.889 -> 0.520, fast->slow
        stick = stick_for_bearing(th, seed.csangle, j / 1000.0)
        if stick not in seen:
            seen.add(stick)
            out.append(stick)
    return full, out


def _freeze_cap_state(state, stick_full, cap_scan=_FREEZE_CAP_SCAN):
    """Cruise `state` (end of start crawl) full-forward until nspeed is at the cap for 2 frames; return
    (cap_clone, pos_cap, fc0_cap). The cap frame is where the +17/+2.3 rates hold, so the freeze is
    predictable from there. `state` untouched (works on a clone)."""
    s = state.clone()
    cap = float(LandState.MAX_NSPEED)
    prev = False
    for _ in range(cap_scan):
        at_cap = (s.nspeed == cap)
        if at_cap and prev:
            break
        prev = at_cap
        s.step(*stick_full)
    return s, s.pos_z, s.anim_fc0


def _freeze_predict(model, pos_cap, fc0_cap, T):
    """Min predicted |freeze - T| over the full cruise from a characterized cap state, and the cruise
    offset m (frames past cap) achieving it. freeze(m) ~= pos_cap + 17m + coast(fc0_cap + 2.3m)."""
    _, _, pos_rate, fc0_rate, _ = model
    best_e, best_m, m = 1e18, 0, 0
    while pos_cap + pos_rate * m <= T + 2.0:
        e = abs(pos_cap + pos_rate * m + _freeze_coast_of(model, fc0_cap + fc0_rate * m) - T)
        if e < best_e:
            best_e, best_m = e, m
        m += 1
    return best_e, best_m


def _freeze_exact_from_cap(cap_state, stick_full, m_hint, T):
    """From the characterized cap state, cruise to the freeze frame and bit-check the predicted window
    (the +-0.3u coast model can be off by a frame near a coast sawtooth jump). Returns the winning cap
    state clone (positioned so `_freeze_pos` is bit-exact at T) or None."""
    TB = _f32_bits(T)
    lo = max(0, m_hint - 2)
    s = cap_state.clone()
    for _ in range(lo):
        s.step(*stick_full)
    for _ in range(lo, m_hint + 3):
        if _f32_bits(_freeze_pos(s).pos_z) == TB:
            return s.clone()
        s.step(*stick_full)
    return None


def _reach_freeze_min(seed, tx, tz, kmax=5, max_frames=4000):
    """Fewest-frame bit-exact C-up freeze via the START crawl (see the block comment above). Grows the
    start window k=2..kmax; per k, DFS the crawl sticks FAST->slow (first exact hit = fewest frames),
    reusing the clone at each depth so a start PREFIX is never re-simulated. Each leaf is characterized
    cheaply (cruise to the cap) and the analytic predictor skips leaves that can't land T. Returns the
    plan dict (same shape as reach_freeze) on a bit-exact hit, else None (caller falls back to robust)."""
    full, lattice = _freeze_start_lattice(seed, tx, tz)
    model = _freeze_coast_model(seed, full)
    TB = _f32_bits(tz)
    root = seed.clone()

    def search(k):
        def rec(state, seq):
            if len(seq) == k:
                cap_s, pos_cap, fc0_cap = _freeze_cap_state(state, full)
                e, m = _freeze_predict(model, pos_cap, fc0_cap, tz)
                if e > _FREEZE_PRED_BAND:
                    return None
                hit = _freeze_exact_from_cap(cap_s, full, m, tz)
                return (seq, hit) if hit is not None else None
            for stick in lattice:
                child = state.clone()
                child.step(*stick)
                got = rec(child, seq + [stick])
                if got:
                    return got
            return None
        return rec(root.clone(), [])

    for k in range(2, kmax + 1):
        got = search(k)
        if got is None:
            continue
        start_seq, hit_cap = got
        # Rebuild the authoritative plan by re-simulating start + full cruise to the bit-exact freeze.
        s = seed.clone()
        seq = []
        for stick in start_seq:
            s.step(*stick)
            seq.append(stick)
        for _ in range(max_frames):
            e = _freeze_pos(s)
            if _f32_bits(e.pos_z) == TB:
                seq = list(seq) + [NEUTRAL] * FREEZE_LATENCY
                return {'seq': seq, 'freeze_dist': dist2d(e, tx, tz),
                        'freeze_pos': (e.pos_x, e.pos_z), 'end': e, 'n_frames': len(seq),
                        'start_frames': len(start_seq)}
            s.step(*full)
            seq.append(full)
        return None
    return None


# Fewest-frame bit-exact freeze via a ROLL approach (`reach_freeze(roll=True)`): start crawl + rolls (26
# u/frame) + walk tail + C-up; ~15-30 frames below the walk floor. Model + the analytic solve: land-planner.md.
_ROLL_RMAX = 30                 # walk-tail scan depth after the last roll (the fine freeze straddle)
_ROLL_PC_BAND = 0.02            # predicted |freeze - tz| (via pos_cap) -> bit-confirm (>> 1-ULP wobble)
_ROLL_PC_MARGIN = 0.05          # pos_cap prune safety margin (>> the ~1-ULP pos_cap-vs-δ wobble)


def _roll_accel(s, full, stream=None):
    """Full-forward until nspeed holds the run cap for 2 frames (post-accel MOVE cruise)."""
    prev = False
    for _ in range(16):
        at = (s.nspeed == float(LandState.MAX_NSPEED))
        if at and prev:
            return
        prev = at
        s.step(*full)
        if stream is not None:
            stream.append((full[0], full[1], 0))


def _roll_pos_cap(state, full):
    """Position at the run cap from `state` (clone) -- the leaf's freeze offset δ equals this pos-at-cap
    offset to ~1 ULP (the whole post-roll downstream is history-independent), so it is the cheap
    (~5-step) predictor + a clean monotone scalar to prune the start-crawl DFS on. `state` untouched."""
    s = state.clone()
    _roll_accel(s, full)
    return s.pos_z


def _roll_cycle(s, full, stream=None):
    """One chained forward roll: press A (0x100) from a MOVE frame, hold full through the roll until it
    exits back to MOVE. A re-rolls only from MOVE and carries the 2-frame input delay, so a cycle is
    ~19 frames (+486.5u at the run cap); the roll's setSingleMoveAnime leaves m34C3==0, so the walk
    blend re-inits its frame ctrl to 0 on exit -- the canonical-phase RESET that makes the freeze
    analytic (land-movement.md Roll section)."""
    s.step(full[0], full[1], buttons=0x100)
    if stream is not None:
        stream.append((full[0], full[1], 0x100))
    entered = False
    for _ in range(40):
        if s.state == FRONT_ROLL:
            entered = True
        if entered and s.state == MOVE:
            return
        s.step(*full)
        if stream is not None:
            stream.append((full[0], full[1], 0))


# The chained-roll speed cap: clamp(speedF*1.5 + 0.5) with speedF at the walk cap = 0.5 + 17*1.5 = 26.
_ROLL_CAP = float(LandState.ROLL_ADD + LandState.MAX_NSPEED * LandState.ROLL_SPD)


def _roll_tune_cycle(s, full, holds, stream=None):
    """One partial-speed 'tuning' roll (the densifier): hold each partial FORWARD stick in `holds` first
    -- decaying speedF below the walk cap 17 so the re-roll clamps to an intermediate mNormalSpeed (< 26)
    -- then press A and hold full through the roll to the MOVE exit (like `_roll_cycle`, with the pre-roll
    partial shave). Post-roll `anim_fc0 == 0` holds (the roll still resets the walk anim), so the freeze
    stays analytic; the shorter roll distance is the extra coarse-grid point. See land-planner.md."""
    for st in holds:
        s.step(*st)
        if stream is not None:
            stream.append((st[0], st[1], 0))
    _roll_cycle(s, full, stream)


def _roll_tuning_catalog(seed, full, th, csangle, roll_speed_min):
    """Distinct partial-speed tuning-roll recipes whose roll mNormalSpeed lands in [roll_speed_min,
    _ROLL_CAP) -- the densifier lattice, cheapest-frames per distinct speed. Each recipe is a `holds`
    tuple of live-valid partial FORWARD sticks (msd 0.52..0.889, aimed at the target bearing) pressed
    before the roll's A. Built from a reference post-accel cruise (identical after any full roll -- the
    roll's anim reset makes it history-independent). Returns [] when the range excludes all partials
    (`roll_speed_min` >= the 26 cap) so the caller's full-only path is byte-for-byte preserved."""
    if roll_speed_min >= _ROLL_CAP - 1e-6:
        return []
    ref = seed.clone()
    _roll_accel(ref, full)
    alph, seen_st = [], set()               # partial forward stick alphabet (dedup, live-valid msd)
    for j in range(520, 890):
        st = stick_for_bearing(th, csangle, j / 1000.0)
        if st not in seen_st:
            seen_st.add(st)
            alph.append(st)
    best = {}                               # speed f32 bits -> (nholds, holds tuple)
    for h in range(1, 7):
        for st in alph:
            c = ref.clone()
            for _ in range(h):
                c.step(*st)
            c.step(full[0], full[1], buttons=0x100)
            sp = None
            for _ in range(40):
                if c.state == FRONT_ROLL:
                    sp = c.nspeed
                    break
                c.step(*full)
            if sp is not None and roll_speed_min <= sp < _ROLL_CAP:
                key = _f32_bits(sp)
                if key not in best or h < best[key][0]:
                    best[key] = (h, tuple([st] * h))
    return [v[1] for v in best.values()]


def _reach_freeze_roll(seed, tx, tz, kmax=5, max_frames=4000, roll_speed_min=26.0):
    """Fewest-frame bit-exact C-up freeze via a ROLL approach (see the block comment above). Grows the
    start window k=2..kmax; per k, DFS the from-rest crawl sticks with a **pos_cap prune**: the needed
    pos_cap for each roll config (nr_full full rolls + optional tuning roll + r walk-tail) is
    `ref_pc + (tz - freeze_ref(config))` (history-independent, computed once), and a subtree is skipped
    when its reachable pos_cap range (all-full completion -> max, all-slow -> min) misses every needed
    value. Each surviving leaf's pos_cap (~5-step accel-to-cap) predicts its freeze to ~1 ULP; predicted
    matches get an exact bit-confirm; objective = fewest TOTAL frames (running-best prune over k).
    Returns a plan dict whose `seq` frames are (sx, sy, buttons) 3-tuples (A=0x100 on each roll's press
    frame), else None (caller falls back).

    `roll_speed_min` (default 26.0 = the cap = FULL rolls only, the frame-optimal but sparse grid) is the
    DENSIFIER knob: lowering it admits partial-speed tuning rolls with mNormalSpeed in [roll_speed_min,
    26] as the LAST roll, adding frame-neutral..cheap coarse-grid points so more targets hit the exact
    float at a SHALLOWER start crawl (faster solve). Wider range (lower min) = denser grid = faster/
    lower-k solve, at the cost of a few frames (partial rolls cover less than 26); narrow (=26) preserves
    the full-only fewest-frame plan exactly. See land-planner.md (ROLL densifier).

    ON-AXIS / +z, seed AT REST (the crawl's low speeds are the free fine grid). Because the sim is 0-ULP
    vs live when seeded from the anchor, the returned plan freezes bit-exact on console -- provided the
    caller seeds `seed` from the LIVE anchor (a 2-ULP seed-pos mismatch shifts the freeze by 1 ULP)."""
    if abs(tx - seed.pos_x) > 1e-6:
        return None                         # on-axis only (off-axis needs the octagon clamp)
    full, lattice = _freeze_start_lattice(seed, tx, tz)
    slow = lattice[-1]                       # slowest live-valid start frame (min pos_cap completion)
    TB = _f32_bits(tz)
    ref_pc = _roll_pos_cap(seed, full)       # reference pos-at-cap (delta baseline)
    th = world_angle_s16(tx - seed.pos_x, tz - seed.pos_z)
    catalog = [None] + _roll_tuning_catalog(seed, full, th, seed.csangle, roll_speed_min)

    def ref_after(nr_full, tune):            # reference (no start crawl): accel + full rolls + tune roll
        s = seed.clone()
        _roll_accel(s, full)
        for _ in range(nr_full):
            _roll_cycle(s, full)
        if tune is not None:
            _roll_tune_cycle(s, full, tune)
        return s

    ref_freeze10 = _freeze_pos(ref_after(1, None)).pos_z
    roll_dz = _freeze_pos(ref_after(2, None)).pos_z - ref_freeze10
    nr_lo = max(0, int((tz - ref_freeze10) / roll_dz) - 1)   # tuning rolls shorten -> widen the low end
    nr_hi = nr_lo + 3
    # history-independent downstream, computed ONCE: needed pos_cap = ref_pc + (tz - freeze_ref(config)).
    needed = []                              # (target pos_cap, nr_full, tune, r, nonstart_frames)
    seen_fr = set()
    for nr_full in range(nr_hi, nr_lo - 1, -1):
        for tune in catalog:
            s0 = seed.clone(); stream0 = []
            _roll_accel(s0, full, stream0)
            for _ in range(nr_full):
                _roll_cycle(s0, full, stream0)
            if tune is not None:
                _roll_tune_cycle(s0, full, tune, stream0)
            if s0.state != MOVE:
                continue
            base = len(stream0)
            t = s0.clone()
            for r in range(_ROLL_RMAX):
                if t.state == MOVE:
                    fr = _freeze_pos(t).pos_z
                    if _f32_bits(fr) not in seen_fr:         # dedup identical freeze_ref
                        seen_fr.add(_f32_bits(fr))
                        needed.append((ref_pc + (tz - fr), nr_full, tune, r, base + r))
                t.step(*full)
    if not needed:
        return None
    needed.sort(key=lambda e: e[4])          # fewest non-start frames first
    # A start crawl only pushes the freeze FORWARD (delta >= 0, bounded ~MAXD); keep only configs whose
    # needed pos_cap lands in [ref_pc, ref_pc+MAXD] so the leaf prune stays tight (land-planner.md).
    MAXD = 12.0 * kmax                       # generous bound on the start-crawl forward delta (obs ~7u/fr)
    needed = [e for e in needed
              if (ref_pc - _ROLL_PC_MARGIN) <= e[0] <= (ref_pc + MAXD + _ROLL_PC_MARGIN)]
    if not needed:
        return None
    p_lo = ref_pc - _ROLL_PC_MARGIN
    p_hi = max(e[0] for e in needed) + _ROLL_PC_MARGIN

    def confirm(start_seq, nr_full, tune, r):
        s = seed.clone()
        stream = []
        for st in start_seq:
            s.step(*st); stream.append((st[0], st[1], 0))
        _roll_accel(s, full, stream)
        for _ in range(nr_full):
            _roll_cycle(s, full, stream)
        if tune is not None:
            _roll_tune_cycle(s, full, tune, stream)
        for _ in range(r):
            s.step(*full); stream.append((full[0], full[1], 0))
        if s.state != MOVE:
            return None
        e = _freeze_pos(s)
        return (stream, e) if _f32_bits(e.pos_z) == TB else None

    import bisect as _bisect
    needed_full = [e for e in needed if e[2] is None]      # full-roll configs (fewest-frame at any k)
    needed_tune = [e for e in needed if e[2] is not None]  # partial-tuning-roll configs (the densifier)

    def _prune(state, rem):                  # True -> subtree's reachable pos_cap misses [p_lo, p_hi]
        hf = state.clone()                   # all-full completion (fastest to cap -> MIN pos_cap, delta~0)
        for _ in range(rem):
            hf.step(*full)
        sf = state.clone()                   # all-slow completion (banks low-speed distance -> MAX pos_cap)
        for _ in range(rem):
            sf.step(*slow)
        lo_r, hi_r = sorted((_roll_pos_cap(hf, full), _roll_pos_cap(sf, full)))
        return hi_r < p_lo or lo_r > p_hi

    def _full_first_hit(k):
        """Fast first-hit DFS over FULL configs -- a full config is the fewest-frame at any k, so its
        first bit-exact hit at depth k is optimal there (the committed full-only behavior, ~seconds)."""
        def rec(state, seq):
            rem = k - len(seq)
            if rem > 0 and _prune(state, rem):
                return None
            if len(seq) == k:
                pc = _roll_pos_cap(state, full)
                for p, nr_full, tune, r, cf in needed_full:
                    if abs(pc - p) <= _ROLL_PC_BAND:
                        got = confirm(seq, nr_full, tune, r)
                        if got is not None:
                            return (seq, nr_full, tune, r, got)
                return None
            for stick in lattice:
                child = state.clone(); child.step(*stick)
                got = rec(child, seq + [stick])
                if got:
                    return got
            return None
        return rec(seed.clone(), [])

    def _tune_config_first(k):
        """Reached only when no full config hits at this k (the densifier's point). Enumerate the depth-k
        leaves surviving the prune, then match CONFIG-FIRST (fewest-frames-ordered, bisect on leaf pos_cap)
        -- the fewest-frame TUNING config any leaf hits (first-hit-per-leaf can't: a costlier tuning config
        could match an earlier leaf). Fast: only runs at LOW k where full missed (small leaf set)."""
        if not needed_tune:
            return None
        leaves = []
        def rec(state, seq):
            rem = k - len(seq)
            if rem > 0 and _prune(state, rem):
                return
            if len(seq) == k:
                leaves.append((_roll_pos_cap(state, full), list(seq)))
                return
            for stick in lattice:
                child = state.clone(); child.step(*stick)
                rec(child, seq + [stick])
        rec(seed.clone(), [])
        if not leaves:
            return None
        leaves.sort(key=lambda L: L[0])
        keys = [L[0] for L in leaves]
        for p, nr_full, tune, r, cf in needed_tune:
            i = _bisect.bisect_left(keys, p - _ROLL_PC_BAND)
            while i < len(leaves) and keys[i] <= p + _ROLL_PC_BAND:
                got = confirm(leaves[i][1], nr_full, tune, r)
                if got is not None:
                    return (leaves[i][1], nr_full, tune, r, got)
                i += 1
        return None

    def search(k):
        return _full_first_hit(k) or _tune_config_first(k)

    for k in range(2, kmax + 1):
        got = search(k)
        if got is None:
            continue
        start_seq, nr_full, tune, r, (stream, e) = got
        seq = list(stream) + [(NEUTRAL[0], NEUTRAL[1], 0)] * FREEZE_LATENCY
        return {'seq': seq, 'freeze_dist': dist2d(e, tx, tz), 'freeze_pos': (e.pos_x, e.pos_z),
                'end': e, 'n_frames': len(seq), 'start_frames': len(start_seq),
                'rolls': nr_full + (1 if tune is not None else 0), 'tail': r, 'tuned': tune is not None}
    return None


def reach_freeze(seed, tx, tz, coarse_gap=60.0, max_frames=4000, drill_back=8, beam_width=96,
                 min_frames=False, kmax=5, roll=False, roll_speed_min=26.0):
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

    `min_frames=True` selects the FEWEST-FRAME bit-exact variant instead (`_reach_freeze_min`): a from-
    rest START crawl + full cruise, ~+7 over the pure full-up floor vs this robust approach's +19..32.
    It requires the seed AT REST (the crawl's low speeds are the free fine grid) and returns 0-ULP
    (exact float), so its plan is bit-exact live. Slower to SOLVE (an unlucky target needs a k=5 start,
    tens of seconds) and on-axis only; if no exact hit is found up to `kmax` it falls back to the robust
    phases below. See the START-crawl block comment above and land-planner.md.

    `roll=True` selects the FEWEST-FRAME analytic ROLL-approach variant (`_reach_freeze_roll`): a from-rest
    start crawl + full cruise + chained forward rolls (26 u/frame) + a short walk tail + C-up. Rolls cover
    ~25.6 vs 17 u/frame, so it rests ~15-30 frames BELOW the pure full-up walk floor, and the roll's anim
    reset makes the per-leaf freeze prediction exact (fast, per-call guided DFS -- no precomputed table).
    Its `seq` frames are (sx, sy, buttons) 3-tuples (A=0x100 on each roll's press frame). On-axis / +z, seed
    AT REST; 0-ULP live when `seed` is seeded from the live anchor. Falls back to min_frames/robust if no
    exact hit up to `kmax`. See land-planner.md.

    `roll_speed_min` (with `roll=True`, default 26.0 = the cap = FULL rolls only) is the DENSIFIER knob:
    lower it (e.g. 20, 15) to admit partial-speed tuning rolls (mNormalSpeed in [roll_speed_min, 26]) as
    the last roll, densifying the coarse grid so hard exact targets hit at a SHALLOWER start crawl (faster
    solve) -- trading a few frames for solve speed. 26.0 preserves the frame-optimal full-only plan.
    """
    if roll:
        got = _reach_freeze_roll(seed, tx, tz, kmax=kmax, max_frames=max_frames,
                                 roll_speed_min=roll_speed_min)
        if got is not None:
            return got
        # no exact roll hit within kmax -> fall through to the walk start-crawl / robust approach.
    if min_frames:
        got = _reach_freeze_min(seed, tx, tz, kmax=kmax, max_frames=max_frames)
        if got is not None:
            return got
        # no exact hit within kmax -> fall through to the robust (always-succeeds) approach.

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
    run-length collapsed as 'sx,sy xN'. Roll plans carry a 3rd button element -- 'sx,sy+A' for the
    A-press (roll) frames (buttons & 0x100)."""
    out = []
    for st in seq:
        tok = f"{st[0]},{st[1]}"
        if len(st) > 2 and st[2] & 0x100:
            tok += "+A"
        if out and out[-1][0] == tok:
            out[-1][1] += 1
        else:
            out.append([tok, 1])
    return " ".join(t if n == 1 else f"{t} x{n}" for t, n in out)
