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
"""THE OBJECTIVE the Courtyard push is solved against, as executable predicates (session 60).

Dereck's steer this session replaced the plan the s44-s51 endgame was built for. The old design
placed Tetra, then spent ~160 further frames decelerating Link to a near-rest arrival and walking
him to a FIXED clip entry (`full_herd.walk_to_entry` / `place_on_thread` / `decel_place` /
`homing_place` / `arrival_quality`). The new one is narrower and much tighter:

  1. **The only goal of the push is getting Tetra onto a viable known clip coord.** Link's roll
     position/angle for the recorded solution is a SEPARATE search, run afterwards -- so no frame
     of this plan may be spent positioning Link for the clip.
  2. **This is a TAS: frames are the objective.** Maximum acceptable timeloss versus an all-out
     push is `TIMELOSS_BUDGET` frames, `TIMELOSS_PREFERRED` preferred.
  3. **The terminal keeps its speed.** At the placement frame Link must still be MOVING, so a
     1-frame 180 turnaround (`reposition.turnaround`) carries him away from Tetra with speed to
     spare, ready to set up the roll. This is what retires the near-rest arrival gate: the
     deceleration `arrival_quality` demanded costs exactly the frames rule 2 refuses.
  4. **Neither actor touches a wall during the herd.** Wall collision is deliberately NOT modelled
     in the Courtyard `FreeRun` (it is expensive, and the herd has no business near a wall), so
     instead of building `WallCorrect` the search must stay in the region where its absence cannot
     matter. Contact DOES happen later, at the clip -- that belongs to the recorded solution list,
     not here.

Rule 4 is the one this module exists to make un-forgettable. Session 60 measured node 1's locked
plan and found the sim walks Link 32 u THROUGH the courtyard's back wall (poly 1950/1953, plane
z = -990.2557) from plan frame 84 on, while the console has him braced at exactly `LINK_WALL_R`
standoff -- a silent infidelity worth 53-75 u of Link divergence at every open console sample, and
one no amount of FP work would ever have closed. `wall_margin` turns that into a prune.

Likewise `in_regime`: past `FOLLOW_ENGAGE_DIST` the live Tetra enters the stt-4 FOLLOW state the
plow model does not cover. An all-out push holds Link 40-85 u behind her so it never binds, but it
is a MODEL boundary, not a stylistic preference, so it is gated rather than assumed.

Every threshold here is derived or decomp-cited -- the wall radii from the collision model, the
ceiling from the measured CC split law (`steered_search.push_ceiling`), the follow distance from
`npc_zl1`. The two numbers that are Dereck's spec rather than the game's are the timeloss budget
and the positive-speed terminal, and they are labelled as such.

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.objective {bar|score|walls}``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush.reposition import HerdLine
from harness.tetrapush.steered_search import ROLL_SPEED_CAP
from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST
from tww_sim.core.npc_zl1 import WALL_R as TETRA_WALL_R
from tww_sim.land.walls import WALL_R as LINK_WALL_R, load_ordered_mesh


# --------------------------------------------------------------------------- the bar

# The SUSTAINED-herd ceiling (`steered_search.push_ceiling`, human 98.2% of it). A STEADY STATE, never
# a per-frame law -- single frames reach 18.84 u: knowledge/mechanics/actor-push.md#how-far.
PUSH_CEILING = ROLL_SPEED_CAP / 2.0

# DERECK'S SPEC (session 60), not a measured quantity: how many frames a placement-precise plan may
# cost over an all-out push that ignores where exactly she lands.
TIMELOSS_BUDGET = 2
TIMELOSS_PREFERRED = 1


def frame_floor(env, placements=None, hl=None):
    """The all-out-push FRAME FLOOR: the fewest frames in which any plan could put Tetra on a
    genuine coord, i.e. the distance to the NEAREST one divided by `PUSH_CEILING`.

    This is an estimate, not a plan -- it assumes contact and perfect down-herd alignment on every
    frame, which the human very nearly achieves (95% contact, 0.996 alignment), so it is a tight one.
    It is also ASYMPTOTIC rather than a hard floor: `PUSH_CEILING` is a steady-state rate that a
    finite window can beat, so a 73-frame plan is not proven impossible in 72. Dereck's budget is a
    spec, so this only affects how the bar is DESCRIBED, never what is accepted.
    Returns ``dict(frames, frames_int, coord, dist, budget, preferred)`` where ``frames_int``
    is the integer floor (a plan is a whole number of frames) and ``budget`` is the worst plan
    length this objective accepts.
    """
    t0 = env['cyl'][0]['tetra']['pos']
    rows = placements if placements is not None else seeds.load_placements()[0]
    best = min(rows, key=lambda p: math.hypot(p['x'] - t0[0], p['z'] - t0[2]))
    dist = math.hypot(best['x'] - t0[0], best['z'] - t0[2])
    frames = dist / PUSH_CEILING
    n = int(math.ceil(frames))
    return dict(frames=frames, frames_int=n, coord=best, dist=dist,
                budget=n + TIMELOSS_BUDGET, preferred=n + TIMELOSS_PREFERRED)


def remaining_frames(placement_dist):
    """The fewest FURTHER frames in which a plan could still put Tetra on the coord she is
    ``placement_dist`` u from: the distance over the SUSTAINED `PUSH_CEILING`.

    A lower bound at the steady state, not a hard one -- see `PUSH_CEILING`: the pose swing lets a
    short window beat the split-law rate by ~0.3-0.6 u/frame, so over ~25 frames this can read ~1
    frame pessimistic. It is exact in the only place it has to be: `placement_dist == 0`."""
    return placement_dist / PUSH_CEILING


def plan_bound(frames, placement_dist):
    """**The frame-minimal rank**, ``f = g + h``: frames already spent (exact) plus
    `remaining_frames` (the steady-state estimate of what is left).

    Ranking a beam on it, ascending, is frame-minimal by construction. What it counts that a herd
    RATE does not: the distance to the coord is a DISTANCE, so lateral drift costs frames here, while
    `u/frame` measures only the down-herd projection. That difference is the s43-s51 endgame's whole
    problem -- the rate-ranked chain left Tetra 28 u off the thread laterally, and no terminal could
    pay for it inside the budget.

    As a PRUNE (`full_herd._budget_cut`) it is admissible at the steady state but not proven, since
    ``h`` inherits `PUSH_CEILING`'s finite-window slack; a plan beating the bound by a frame is a
    real possibility, so cut on ``budget`` plus a frame if that ever matters. It is a rank first."""
    return frames + remaining_frames(placement_dist)


# --------------------------------------------------------------------------- rule 4: the walls

# The game's wall classification (`cBgW_CheckB*`; the |ny| < 0.03 threshold used before 2026-07-15
# was wrong, and produced phantom clips -- see `[[seam-locator-coplanar-hardening]]`).
_WALL_NY_LO, _WALL_NY_HI = -0.8, 0.5
_BODY_Y = 60.0                  # inside every ground wall-cylinder height (30.1 / 89.9 / 125.0)

_MESH_CACHE = {}

# The grid the fast path's BRACKET lives on (`_cell_distance`; any size is exact, so this only trades
# cell-warming against how often the bracket decides -- 32 u decides both sides at the 35/50 u radii).
_CELL = 32.0
_CELL_REACH = _CELL * 0.7071067811865476        # half the cell diagonal


class _Walls(object):
    """The relevant wall tris plus their XZ bounding boxes and the memoised cell-centre distances.

    The box is a broad phase: a search calls `clear_of_walls` once per actor per frame, and the
    honest answer needs every tri, but a tri whose BOX is already farther than the radius cannot
    violate it. In the courtyard the herd runs hundreds of units from anything, so the box test
    rejects nearly all 177 tris on four comparisons.

    `cells` is the second phase, and the one that makes the predicate affordable per frame: the
    exact distance from each visited grid cell's CENTRE, which brackets every point in that cell."""

    __slots__ = ('tris', 'boxes', 'cells')

    def __init__(self, tris):
        self.tris = tris
        self.boxes = [(min(t.v0[0], t.v1[0], t.v2[0]), max(t.v0[0], t.v1[0], t.v2[0]),
                       min(t.v0[2], t.v1[2], t.v2[2]), max(t.v0[2], t.v1[2], t.v2[2]))
                      for t in tris]
        self.cells = {}

    def __len__(self):
        return len(self.tris)

    def __iter__(self):
        return iter(self.tris)


def courtyard_walls(path=None):
    """The Hyrule wall triangles that a herding actor could touch: wall-classified, spanning the
    floor's body band. Cached -- the mesh is 3162 tris and the predicates run per frame."""
    if path is None:
        path = os.path.join(_d, 'fixtures', 'hyrule_tetra_walls_ordered.json')
    if path not in _MESH_CACHE:
        out = []
        for tri in load_ordered_mesh(path):
            if not (_WALL_NY_LO <= tri.pla.ny < _WALL_NY_HI):
                continue
            ys = (tri.v0[1], tri.v1[1], tri.v2[1])
            if min(ys) <= _BODY_Y <= max(ys):
                out.append(tri)
        _MESH_CACHE[path] = _Walls(out)
    return _MESH_CACHE[path]


def _box_gap(px, pz, box):
    """Lower bound on the distance from a point to anything inside an XZ box (0 if inside)."""
    dx = box[0] - px if px < box[0] else (px - box[1] if px > box[1] else 0.0)
    dz = box[2] - pz if pz < box[2] else (pz - box[3] if pz > box[3] else 0.0)
    return math.hypot(dx, dz)


def _cell_distance(walls, x, z):
    """The exact wall distance from the CENTRE of the grid cell holding ``(x, z)``, memoised.

    Every point in that cell lies within `_CELL_REACH` of the centre, so this one number brackets
    the point's own distance from both sides -- which is what lets `clear_of_walls` answer most
    frames without touching a triangle, while staying EXACT rather than conservative."""
    key = (int(math.floor(x / _CELL)), int(math.floor(z / _CELL)))
    d = walls.cells.get(key)
    if d is None:
        d = walls.cells[key] = _exact_distance(walls, (key[0] + 0.5) * _CELL,
                                              (key[1] + 0.5) * _CELL)
    return d


def clear_of_walls(x, z, r, walls=None):
    """Is the point at least ``r`` from every wall edge? The per-frame search predicate -- EXACT,
    but decided by the cell bracket (`_cell_distance`) wherever that suffices, and by the bounding
    boxes when it does not, so the common (wide-open) case costs a dict lookup rather than 177
    triangles. Identical answers to ``wall_distance(x, z) >= r``, gated."""
    walls = courtyard_walls() if walls is None else walls
    dc = _cell_distance(walls, x, z)
    if dc - _CELL_REACH >= r:                   # the whole cell clears the radius
        return True
    if dc + _CELL_REACH < r:                    # no point in the cell can clear it
        return False
    tris, boxes = walls.tris, walls.boxes
    for i, t in enumerate(tris):
        if _box_gap(x, z, boxes[i]) >= r:
            continue
        if min(_edge_dist(x, z, t.v0, t.v1), _edge_dist(x, z, t.v1, t.v2),
               _edge_dist(x, z, t.v2, t.v0)) < r:
            return False
    return True


def frame_is_wall_free(lx, lz, tx, tz, walls=None):
    """The prune a search wires in beside its `_follow_warned` check: neither actor inside its own
    wall cylinder, so the unmodelled `WallCorrect` cannot be acting on this frame."""
    walls = courtyard_walls() if walls is None else walls
    return (clear_of_walls(lx, lz, LINK_WALL_R, walls)
            and clear_of_walls(tx, tz, TETRA_WALL_R, walls))


def _edge_dist(px, pz, a, b):
    dx, dz = b[0] - a[0], b[2] - a[2]
    L2 = dx * dx + dz * dz
    if L2 == 0.0:
        return math.hypot(px - a[0], pz - a[2])
    t = (px - a[0]) * dx + (pz - a[2]) * dz
    t = 0.0 if t < 0.0 else (L2 if t > L2 else t)
    t /= L2
    return math.hypot(px - (a[0] + t * dx), pz - (a[2] + t * dz))


def _exact_distance(walls, x, z):
    """The measurement, over every triangle: XZ distance to the nearest wall edge."""
    best = float('inf')
    for t in walls.tris:
        d = min(_edge_dist(x, z, t.v0, t.v1), _edge_dist(x, z, t.v1, t.v2),
                _edge_dist(x, z, t.v2, t.v0))
        if d < best:
            best = d
    return best


def wall_distance(x, z, walls=None):
    """XZ distance from a point to the nearest courtyard wall edge (u) -- the MEASUREMENT (never
    bracketed or cached), used for reporting and as `clear_of_walls`' reference in the gate."""
    return _exact_distance(courtyard_walls() if walls is None else walls, x, z)


def wall_margin(lx, lz, tx, tz, walls=None):
    """How much room the frame has before the UNMODELLED wall collision would start acting.

    Returns ``dict(link, tetra, margin)``: each actor's clearance beyond its own wall-cylinder
    radius (`LINK_WALL_R` 35, `TETRA_WALL_R` 50 -- the radii `WallCorrect` braces them at), and the
    binding minimum. ``margin > 0`` means the frame is in the region where the model's silence
    about walls is harmless; ``margin <= 0`` means the sim is producing a trajectory the console
    would not.
    """
    walls = courtyard_walls() if walls is None else walls
    dl = wall_distance(lx, lz, walls) - LINK_WALL_R
    dt = wall_distance(tx, tz, walls) - TETRA_WALL_R
    return dict(link=dl, tetra=dt, margin=min(dl, dt))


# --------------------------------------------------------------------------- rule 4b: the regime

def in_regime(lx, lz, tx, tz, ly=None, ty=None):
    """True while Tetra stays in the stt-3 plow regime the model covers.

    `Zl1FollowState` engages on 3D distance (`fopAcM_searchActorDistance2` is `abs2`), but the
    courtyard floor is flat so the Y term is zero unless callers pass one."""
    d2 = (lx - tx) ** 2 + (lz - tz) ** 2
    if ly is not None and ty is not None:
        d2 += (ly - ty) ** 2
    return math.sqrt(d2) <= FOLLOW_ENGAGE_DIST


# --------------------------------------------------------------------------- rule 3: the terminal

def turnaround_ready(speedF, facing, lx, lz, tx, tz):
    """Dereck's terminal condition: at the placement frame Link must still be MOVING, so that a
    1-frame 180 (`reposition.turnaround` -- a facing snap that PRESERVES speed) leaves him walking
    away from Tetra rather than starting from rest.

    `speedF` is signed against `shape_angle.y`: an EBS backslide carries a large NEGATIVE speedF
    with the facing 0x8000 from travel, and is just as much "moving" as a positive walk -- so the
    test is on the ground-velocity MAGNITUDE, and on which way that velocity points after the snap.

    Returns ``dict(speed, travel_bam, away, ready)``: the speed magnitude, the direction Link is
    actually travelling, the component of that travel directly away from Tetra AFTER the 180, and
    whether both conditions hold.
    """
    speed = abs(float(speedF))
    # Travel = facing, or facing + 0x8000 when speedF is negative (the DIR_BACKWARD convention the
    # ATN procs set up: `current.angle.y += 0x8000; mNormalSpeed *= -1`).
    travel = (int(facing) + (0x8000 if speedF < 0 else 0)) & 0xFFFF
    # A 180 turnaround snaps the facing across travel; the resulting motion is the reverse.
    after = (travel + 0x8000) & 0xFFFF
    ang = after / 65536.0 * 2.0 * math.pi
    vx, vz = math.sin(ang) * speed, math.cos(ang) * speed
    d = math.hypot(lx - tx, lz - tz)
    away = (vx * (lx - tx) + vz * (lz - tz)) / d if d > 1e-9 else 0.0
    return dict(speed=speed, travel_bam=travel, away=away, ready=speed > 0.0 and away > 0.0)


# --------------------------------------------------------------------------- the whole score

#: Placement tolerance: the 288 coords are a dense SAMPLING (0.166 u apart) of a CONTINUOUS clippable
#: thread, so landing between two samples clips too -- this is the sampling's slack, not a fudge.
PLACEMENT_BAND = 1.0


def placement_thread(hl, placements=None):
    """**What the target actually IS, in the herd frame** (session 61, measured -- and it is not a
    cluster).

    The 288 genuine coords are a nearly straight **47.6 u SEGMENT** (no sample deviates more than
    1.9 u from the chord) whose axis sits **12.2 deg off the herd axis**. In `HerdLine` coordinates
    that makes them a LINE, not a point: lateral rises ~0.219 u per u of along, across along
    937.5..984.1 and lateral -2.3..+7.9.

    Two consequences that decide how a plan must be built, neither of them obvious from "land Tetra
    on a viable coord":

      * **The along direction is slack and the lateral is razor.** A push down the herd axis gives
        Tetra ~46 u of freedom in WHERE along the thread she stops -- ~3.6 frames of pushing -- so
        the terminal does not have to hit a point. But her lateral offset has to be inside a ~10 u
        window, and `lat_at` says which along matches which lateral. Pushing her further down-herd
        does not fix a lateral miss; it only trades one for the other at 0.219 u per u.
      * **Therefore a lateral offset outside that window can never be placed, at any along.** The
        s43-s51 rate-ranked chain left her at lateral ~+36 -- ~28 u outside it -- which is why the
        endgame needed a whole reposition phase, and why `plan_bound` (which counts lateral as the
        frames it costs) is the rank rather than a herd rate.

    Returns ``dict(along_lo, along_hi, lat_lo, lat_hi, slope, intercept, length, deg_off_axis,
    max_chord_dev)`` plus ``lat_at(along)`` -- the thread's own lateral at a given along."""
    rows = placements if placements is not None else seeds.load_placements()[0]
    pts = [(hl.along(p['x'], p['z']), hl.lateral(p['x'], p['z'])) for p in rows]
    a0, a1 = min(p[0] for p in pts), max(p[0] for p in pts)
    l0, l1 = min(p[1] for p in pts), max(p[1] for p in pts)
    # the chord through the extreme samples (the set is straight to ~1.9 u, asserted by the gate)
    lo = min(pts, key=lambda p: p[0])
    hi = max(pts, key=lambda p: p[0])
    slope = (hi[1] - lo[1]) / (hi[0] - lo[0])
    intercept = lo[1] - slope * lo[0]
    ax, az = rows[-1]['x'] - rows[0]['x'], rows[-1]['z'] - rows[0]['z']
    length = math.hypot(ax, az)
    cos = abs((ax / length) * hl.dx + (az / length) * hl.dz)
    dev = max(abs(p[1] - (slope * p[0] + intercept)) for p in pts) * math.cos(math.atan(slope))
    return dict(along_lo=a0, along_hi=a1, lat_lo=l0, lat_hi=l1, slope=slope, intercept=intercept,
                length=length, deg_off_axis=math.degrees(math.acos(min(1.0, cos))),
                max_chord_dev=dev, lat_at=lambda a: slope * a + intercept)


def score_plan(env, rows, *, hl=None, placements=None, walls=None, band=PLACEMENT_BAND):
    """Score a plan against the whole objective. ``rows`` is a list of per-frame dicts carrying
    ``sim_link``/``sim_tetra``/``sim_facing``/``speedF`` (the `FreeRun.step(record=True)` shape) or
    the ``link``/``tetra`` shape `search.rollout` emits.

    Returns the figures Dereck's rules ask for, plus the verdict on each. Nothing here tunes or
    ranks -- it REPORTS, so a search can prune on the pieces and a session can state where a plan
    stands without re-deriving the bar.

    ``complete`` guards the frame comparison: a plan that has not put Tetra on a coord has not
    finished, so its frame count is not yet comparable to the floor (the recorded 2-cycle window
    would otherwise read as 29 frames UNDER an all-out push simply by stopping early)."""
    hl = HerdLine.from_env(env) if hl is None else hl
    walls = courtyard_walls() if walls is None else walls
    rows_p = placements if placements is not None else seeds.load_placements()[0]
    floor = frame_floor(env, rows_p, hl)

    def _pos(r):
        if 'sim_link' in r:
            return r['sim_link'], r['sim_tetra'], r.get('sim_facing'), r.get('speedF')
        return r['link'], r['tetra'], r.get('facing', r.get('sim_facing')), r.get('speedF')

    worst_margin, worst_at = float('inf'), None
    left_regime = None
    for i, r in enumerate(rows):
        (lx, lz), (tx, tz), _f, _s = _pos(r)
        m = wall_margin(lx, lz, tx, tz, walls)['margin']
        if m < worst_margin:
            worst_margin, worst_at = m, i + 1
        if left_regime is None and not in_regime(lx, lz, tx, tz):
            left_regime = i + 1

    (lx, lz), (tx, tz), facing, speedF = _pos(rows[-1])
    near = min(rows_p, key=lambda p: math.hypot(p['x'] - tx, p['z'] - tz))
    pd = math.hypot(near['x'] - tx, near['z'] - tz)
    term = turnaround_ready(speedF or 0.0, facing or 0, lx, lz, tx, tz)

    # Where the endpoint sits on the target SEGMENT (`placement_thread`): the lateral must be inside
    # its ~10 u window or NO along can place her, however far she is pushed.
    th = placement_thread(hl, rows_p)
    t_along, t_lat = hl.along(tx, tz), hl.lateral(tx, tz)
    lat_tol = band / math.cos(math.atan(th['slope']))

    frames = len(rows)
    timeloss = frames - floor['frames_int']
    complete = pd <= band
    return dict(
        frames=frames, floor=floor['frames_int'], floor_exact=floor['frames'],
        timeloss=timeloss, bound=plan_bound(frames, pd),
        within_budget=complete and timeloss <= TIMELOSS_BUDGET,
        within_preferred=complete and timeloss <= TIMELOSS_PREFERRED,
        herd=hl.along(tx, tz), rate=hl.along(tx, tz) / frames if frames else 0.0,
        placement_dist=pd, placement_idx=near['idx'], complete=complete, band=band,
        tetra_along=t_along, tetra_lat=t_lat,
        lat_error=t_lat - th['lat_at'](min(max(t_along, th['along_lo']), th['along_hi'])),
        placeable=(th['lat_lo'] - lat_tol <= t_lat <= th['lat_hi'] + lat_tol),
        wall_margin=worst_margin, wall_margin_at=worst_at, wall_ok=worst_margin > 0.0,
        left_regime_at=left_regime, regime_ok=left_regime is None,
        terminal=term, terminal_ok=term['ready'],
    )


def replay_and_score(env, log, **kw):
    """**THE ACCEPTANCE TEST, from a plan's raw input log alone.** Replay ``log`` on a fresh
    self-contained `FreeRun` -- the same 0-ULP forward model the console gate is measured against --
    and score every frame of it.

    A search's own node carries its beam's prunes, which are cheap filters; this replays from state 2
    and scores the whole trajectory with the exact metrics, so it is what a session should quote. The
    FreeRun follow warning is suppressed because leaving the regime is one of the things being
    MEASURED (`left_regime_at`), not an exception to raise."""
    import warnings
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in log:
            rows.append(run.step(d))
    return score_plan(env, rows, **kw)


def verdict(sc):
    """The one-line pass/fail: on a coord, inside the frame budget, wall-free, in-regime, and
    leaving Link moving for the 1-frame 180."""
    return (sc['complete'] and sc['within_budget'] and sc['wall_ok']
            and sc['regime_ok'] and sc['terminal_ok'])


# --------------------------------------------------------------------------- CLI

def _cmd_bar(env):
    f = frame_floor(env)
    t0 = env['cyl'][0]['tetra']['pos']
    print("THE BAR (session 60, Dereck's steer)\n")
    print("  Tetra state-2 start        (%.4f, %.4f)" % (t0[0], t0[2]))
    print("  nearest genuine coord      idx %d (%.4f, %.4f), %.3f u away"
          % (f['coord']['idx'], f['coord']['x'], f['coord']['z'], f['dist']))
    print("  sustained herd ceiling     %.2f u/frame  (roll cap %.1f / 2, the CC split law)"
          % (PUSH_CEILING, ROLL_SPEED_CAP))
    print("  ALL-OUT-PUSH FRAME FLOOR   %.2f -> %d frames" % (f['frames'], f['frames_int']))
    print("  accepted (floor + %d)       %d frames" % (TIMELOSS_BUDGET, f['budget']))
    print("  preferred (floor + %d)      %d frames" % (TIMELOSS_PREFERRED, f['preferred']))
    print("\n  the plan must also: land Tetra ON a coord, never let either actor inside its wall")
    print("  radius (Link %.0f / Tetra %.0f -- walls are NOT modelled), keep Link-Tetra <= %.0f u"
          % (LINK_WALL_R, TETRA_WALL_R, FOLLOW_ENGAGE_DIST))
    print("  (the unmodelled stt-4 follow), and leave Link MOVING for the 1-frame 180.")


def _cmd_walls(env):
    """Where the walls are relative to the herd -- the check that rule 4 is not a real constraint
    on a well-behaved push, only on a plan that overshoots."""
    walls = courtyard_walls()
    hl = HerdLine.from_env(env)
    t0 = env['cyl'][0]['tetra']['pos']
    rows, _ = seeds.load_placements()
    print("courtyard wall tris spanning the body band: %d" % len(walls))
    print("\nTetra start   (%10.4f, %10.4f)  wall dist %8.3f  margin %8.3f"
          % (t0[0], t0[2], wall_distance(t0[0], t0[2], walls),
             wall_distance(t0[0], t0[2], walls) - TETRA_WALL_R))
    ds = [(wall_distance(p['x'], p['z'], walls) - TETRA_WALL_R, p) for p in rows]
    ds.sort(key=lambda r: r[0])
    print("\ngenuine coords, tightest wall margin for Tetra:")
    for m, p in ds[:3]:
        print("   idx %3d (%10.4f, %10.4f)  margin %8.3f" % (p['idx'], p['x'], p['z'], m))
    print("   ... loosest idx %3d margin %8.3f" % (ds[-1][1]['idx'], ds[-1][0]))
    print("\n=> every genuine coord clears Tetra's %.0f u wall cylinder, so the PLACEMENT is"
          % TETRA_WALL_R)
    print("   wall-free too; the contact Dereck means belongs to the clip roll afterwards.")


def _cmd_score(env):
    """Score the two plans that exist: the recorded human window, and node 1's locked plan."""
    import json
    from harness.tetrapush import search as S

    hl = HerdLine.from_env(env)
    walls = courtyard_walls()
    rows_p, _ = seeds.load_placements()

    print("=== the RECORDED HUMAN window (the feasibility oracle, not the target) ===")
    rec = S.rollout_recorded(env, upto=45)
    sc = score_plan(env, rec['rows'], hl=hl, placements=rows_p, walls=walls)
    _print_score(sc)

    p = os.path.join(_d, 'fixtures', 'courtyard_node1_console.json')
    print("\n=== node 1's LOCKED plan, replayed on today's model ===")
    fix = json.load(open(p))
    sc = replay_and_score(env, fix['log'], hl=hl, placements=rows_p, walls=walls)
    _print_score(sc)


def _print_score(sc):
    print("  frames %d (floor %d) -> timeloss %+d   %s"
          % (sc['frames'], sc['floor'], sc['timeloss'],
             "WITHIN BUDGET" if sc['within_budget'] else
             "OVER BUDGET" if sc['complete'] else "n/a -- herd INCOMPLETE"))
    print("  herd %.2f u @ %.3f u/frame   placement %.3f u from coord idx %d"
          % (sc['herd'], sc['rate'], sc['placement_dist'], sc['placement_idx']))
    print("  frame bound %.1f (`plan_bound`: frames + the steady-state remainder)" % sc['bound'])
    print("  Tetra along %.1f lat %+.2f -> %+.2f u off the target thread   placeable %s"
          % (sc['tetra_along'], sc['tetra_lat'], sc['lat_error'], sc['placeable']))
    print("  wall margin %+.3f u (frame %s)   %s"
          % (sc['wall_margin'], sc['wall_margin_at'], "OK" if sc['wall_ok'] else "VIOLATED"))
    print("  regime      %s" % ("in regime throughout" if sc['regime_ok']
                                else "LEFT at frame %d (unmodelled stt-4 follow)"
                                     % sc['left_regime_at']))
    t = sc['terminal']
    print("  terminal    speed %.3f, away-after-180 %+.3f u/frame -> %s"
          % (t['speed'], t['away'], "READY" if t['ready'] else "NOT READY"))
    print("  VERDICT     %s" % ("PASS" if verdict(sc) else "fail"))


def main(argv):
    cmd = argv[0] if argv else 'bar'
    env = seeds.load_env()
    if cmd == 'bar':
        _cmd_bar(env)
    elif cmd == 'walls':
        _cmd_walls(env)
    elif cmd == 'score':
        _cmd_score(env)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
