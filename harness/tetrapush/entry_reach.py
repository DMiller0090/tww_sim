"""WHAT A PLAN OF N WALK FRAMES CAN ACTUALLY REACH -- the set every entry-search negative and every
qualification is implicitly argued over.

THE ERROR THIS MODULE EXISTS FOR (session 93). `entry_search.reach_radius` is a RADIUS: four frames at
the walk cap plus the roll's own entry step, 94 u, used by `curve_seeds` as a square box around
`ref_entry`. It is a generous over-approximation and it was never meant as anything else -- but the
whole session-92 productive set was measured inside it, so "cell 2562 carries genuine dust at a walkable
entry" quietly became "a plan can clip at cell 2562". Those are different claims. Link enters the window
at the speedF 17 cap on a fixed heading; four held-stick frames can only turn him so far, so the real
reachable set is a small curved cloud, not a 94 u box, and the second lobe's stations sit outside it.

Measured: a 4-frame pass at the whole aimable second lobe (779130 candidates, 7.0 M evaluations) returns
0 genuine, 0 near, 0 dead-tail, and the closest any candidate comes to a right cell's residual zero is
0.354 rising to 1.873 with the facing offset -- 71x to 375x outside `BAND_PROBE`, at a `grad == 0`
entry. Not a sampling gap. See `knowledge/strategy/clip-exit-angle.md`.

WHY A CONVEX HULL, and why that is the honest shape for a NEGATIVE. The true reachable set is neither
convex nor known in closed form; the fan samples it. A hull of those samples is a SUPERSET of the
sampled set and, since the fan's stick alphabet is coarse, an approximation of the true one -- so
``outside the hull`` is the conservative direction and is the only verdict this module returns as fact.
``inside the hull`` is NOT a claim that a plan reaches the point: that owes a real fan and a
`confirm_entry`. This is the razor-rule-12 discipline applied to the reachability claim itself -- one
side of the test is a proof and the other is a hint, so only the proving side is used to prune.

THE ENTRY IS THE WALK ENDPOINT PLUS THE ROLL STEP, and that factorisation is what makes one hull serve
every configuration: `entry_search.roll_entry` adds a 26 u step along the ROLL FACING, so the entry
cloud is the walk cloud translated by a facing-dependent vector. Store the facing-independent walk
hull once and translate the query instead (`reachable`).

    python -m harness.tetrapush.entry_reach hull [frames]     # measure + write the fixture
    python -m harness.tetrapush.entry_reach check             # the s92 stations against it
"""
import json
import os
import sys
import time
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import entry_search as ES

HULL_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_walk_hull_s93.json')

#: The delivered clip's plan length, and so the budget every claim about "at the frame floor" means.
FLOOR_FRAMES = 4


def hull(points):
    """The 2D convex hull, counter-clockwise, by Andrew's monotone chain. Pure stdlib on purpose --
    the harness has no scipy dependency and this is thirty lines."""
    pts = sorted(set((float(x), float(z)) for x, z in points))
    if len(pts) <= 2:
        return list(pts)

    def half(ps):
        out = []
        for p in ps:
            while len(out) >= 2 and _cross(out[-2], out[-1], p) <= 0.0:
                out.pop()
            out.append(p)
        return out

    lower, upper = half(pts), half(reversed(pts))
    return lower[:-1] + upper[:-1]


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def contains(poly, p, margin=0.0):
    """Is ``p`` inside this counter-clockwise convex polygon, allowing ``margin`` u of slack?

    ``margin`` exists because the hull is measured off a COARSE fan, so a point just outside it may
    well be reachable by a stick the alphabet skipped. A negative should be argued at a margin wide
    enough that no plausible refinement of the fan changes it -- so the caller states its slack rather
    than trusting an exact edge test."""
    if len(poly) < 3:
        return False
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ex, ez = b[0] - a[0], b[1] - a[1]
        n = (ex * ex + ez * ez) ** 0.5
        if n == 0.0:
            continue
        # signed distance to the edge line, positive inside for a CCW polygon
        if (_cross(a, b, p) / n) < -margin:
            return False
    return True


def walk_clouds(budgets=(FLOOR_FRAMES,), seed=None, env=None, base_frames=(0, 1, 2, 3),
                s1_stride=8, j1=(2, 3, 4), s2_stride=8, j2max=6, progress=False):
    """Every WALK ENDPOINT a two-segment plan reaches, bucketed by plan length -- ``{budget: [(x, z)]}``
    cumulative, so ``clouds[5]`` holds everything a 5-frame plan can do including the shorter ones.

    ONE fan serves every budget (the plan length is a property of the candidate, not of the pass), which
    matters because the fan is the whole cost here: re-running it per budget was three passes for one
    measurement.

    The shape is deliberately coarse and WIDE rather than fine and narrow: this measures the cloud's
    extent, and a stride the search would never run is fine for that, while a truncated ``j1`` or
    ``base_frames`` would clip the cloud itself. The candidates carry the fan's own prunes -- the speedF
    cap, the 230 u follow bar, a proc the A-press can roll from -- and nothing else."""
    from harness.tetrapush import entry_fan as EF          # deferred: entry_fan imports the scoring
    t0 = time.time()
    budgets = sorted(int(b) for b in budgets)
    out = {b: [] for b in budgets}
    for k, plan in EF.iter_fan2(seed=seed, env=env, base_frames=base_frames, s1_stride=s1_stride,
                               j1=j1, s2_stride=s2_stride, j2max=j2max, progress=progress):
        f = EF.plan_frames(plan)
        for b in budgets:
            if f <= b:
                out[b].append((k[0], k[1]))
    if progress:
        print("  walk clouds %s: %s endpoints  [%.0fs]"
              % (budgets, [len(out[b]) for b in budgets], time.time() - t0))
    return out


#: The fan shape `measure` samples the cloud with, recorded into the fixture -- a hull is only as wide
#: as the alphabet that swept it, so the shape is part of what the negative means.
MEASURE_FAN = dict(base_frames=(0, 1, 2, 3), s1_stride=8, j1=(2, 3, 4), s2_stride=8, j2max=6)


def measure(budgets=(FLOOR_FRAMES,), **kw):
    """`walk_clouds` reduced to a hull per budget, with the provenance a pinned negative owes."""
    shape = dict(MEASURE_FAN, **kw)
    clouds = walk_clouds(budgets=budgets, **shape)
    fan = {k: (list(v) if isinstance(v, tuple) else v)
           for k, v in shape.items() if k != 'progress'}
    out = {}
    for b, cloud in clouds.items():
        if not cloud:
            continue
        h = hull(cloud)
        xs, zs = [p[0] for p in cloud], [p[1] for p in cloud]
        out[b] = dict(frames=b, n_endpoints=len(cloud), hull=[list(p) for p in h],
                      bbox=[min(xs), min(zs), max(xs), max(zs)], fan=fan,
                      reach_radius=ES.reach_radius(b), roll_nspeed=ES.ROLL_NSPEED)
    return out


def load(path=HULL_FIXTURE):
    """The pinned walk hulls, ``{frames: {...}}``. A MODEL output, like the qualification."""
    d = json.load(open(path))
    return {int(k): v for k, v in d['hulls'].items()}


def reachable(station, facing, frames=FLOOR_FRAMES, nspeed=None, hulls=None, margin=1.0):
    """Can a plan of ``frames`` walk frames put the ROLL ENTRY on ``station``?

    The entry is the walk endpoint plus `roll_entry`'s 26 u step along the roll facing, so the test is
    on ``station - roll_step`` against the facing-independent walk hull. Returns True unless the
    translated point is outside the hull by more than ``margin`` -- the asymmetry is the point (see the
    module docstring): only ``False`` is a claim."""
    hulls = hulls if hulls is not None else load()
    h = hulls.get(int(frames))
    if h is None:
        raise ValueError("no measured hull at %d frames (have %s)" % (frames, sorted(hulls)))
    # roll_entry is walk_pos + step(facing, nspeed); invert it by differencing at the origin
    ox, oz = ES.roll_entry((0.0, 0.0), facing, nspeed)
    return contains([tuple(p) for p in h['hull']], (station[0] - ox, station[1] - oz), margin)


def reachable_quals(quals, frames=FLOOR_FRAMES, hulls=None, margin=1.0):
    """The productive set with each configuration told whether its own station is REACHABLE at this
    frame budget -- the filter session 92's 40 configurations were never put through.

    Adds ``reachable`` and leaves everything else alone, so a caller can scope a pass by it or just
    read it. Note what it does NOT do: re-seed. A configuration whose s92 station is unreachable may
    still have another station inside the cloud, and finding that is `curve_seeds` seeded off the hull
    rather than off `reach_radius` -- the real repair, and a bigger job than this filter."""
    hulls = hulls if hulls is not None else load()
    out = []
    for q in quals:
        r = reachable(tuple(q['entry']), q['facing'], frames=frames,
                      nspeed=q.get('nspeed'), hulls=hulls, margin=margin)
        out.append(dict(q, reachable=bool(r)))
    return out


# --------------------------------------------------------------------------- CLI

def _cmd_hull(argv):
    warnings.simplefilter('ignore')
    budgets = [int(x) for x in argv[0].split(',')] if argv else [FLOOR_FRAMES, 5, 6]
    measured = measure(budgets=budgets, progress=True)
    hulls = {}
    for f in sorted(measured):
        m = measured[f]
        hulls[str(f)] = m
        print("frames <= %d: %d endpoints, hull %d vertices, bbox %s  (reach_radius was %.1f u)"
              % (f, m['n_endpoints'], len(m['hull']),
                 ['%.1f' % v for v in m['bbox']], m['reach_radius']))
    json.dump(dict(source='harness/tetrapush/entry_reach.measure, session 93',
                   note="A MODEL OUTPUT, not a console capture. THE CONVEX HULL OF THE WALK"
                        " ENDPOINTS a two-segment plan of <= N frames reaches from the"
                        " console-confirmed base, with the fan's own prunes. It exists because"
                        " `entry_search.reach_radius` is a 94 u BOX and the session-92 qualification"
                        " was measured inside it, which scoped in stations no plan at the frame floor"
                        " can reach. Only OUTSIDE is a claim (see entry_reach's docstring).",
                   hulls=hulls), open(HULL_FIXTURE, 'w'), indent=1)
    print("wrote %s" % HULL_FIXTURE)


def _cmd_check(argv):
    warnings.simplefilter('ignore')
    from harness.tetrapush import entry_score as EC
    quals = json.load(open(os.path.join(_rb, 'fixtures',
                                        'courtyard_qualified_s92.json')))['quals']
    hulls = load()
    for f in sorted(hulls):
        rows = reachable_quals(quals, frames=f, hulls=hulls)
        ok = [r for r in rows if r['reachable']]
        print("<= %d frames: %d of %d configurations have a REACHABLE station; cells %s"
              % (f, len(ok), len(rows), sorted({r['cell'] for r in ok})))
        far = sorted({r['cell'] for r in rows if not r['reachable']})
        print("      unreachable cells: %s" % far)
    w = EC.facing_window()
    print("the delivered clip is cell %d at %s" % (w['delivered']['cell'], w['delivered']['plan']))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'check'
    if cmd == 'hull':
        _cmd_hull(argv)
    elif cmd == 'check':
        _cmd_check(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
