"""WHICH THRUSTS THIS CORNER CAN CLIP AT ALL -- the depth-at-the-razor law (session 100).

Session 99 found the frame-minimal objective had never charged for the B thrust (`entry_fan.plan_frames`
counts WALK HOLDS only) and that `procFrontRoll`'s cut gate makes **thrust 13** the floor, so the
delivered clip presses B two frames late. Its handoff named the Tetra placement as the route to those
frames, on the reasoning that the reachable hull depends on Link's facing while HER placement moves the
residual locus relative to it. Measured, the placement is not the lever and the frames are not both
there -- and both facts come out of one scalar law.

THE LAW. `genuine` needs the post-CrrPos cut endpoint BEHIND a wall plane, so write the penetration as

    depth  =  -min(planeA(pred), planeB(pred))          `sweep_par` slots 8/9, `depth_of`

and note what `resid ~ 0` does to it. **S is the corner VERTEX, which lies on BOTH wall planes**, so a
razor solution -- the cut segment pointing at S -- forces `pred` onto the ``old -> S`` ray and leaves

    depth  ~  |base + push|  -  |S - old|               (up to the ray/normal projection)

where `base` (the roll step plus the cut root translate) is a constant per facing. So the depth at the
razor is decided by HOW CLOSE THE ROLL BRACES and HOW MUCH PUSH SURVIVES to the cut frame -- which is
session 99's "brace + the 49.74 u lunge pin the cut start to a 0.65 u pocket", stated as a quantity a
search can rank instead of a bound on the exit angle.

WHAT THAT MEASURES (delivered cell 2552, every in-hull razor solution Newtoned from the whole hull at
0.5 u, 4 and 5 walk frames -- 48 / 45 / 35 solutions):

    thrust 15  cost 23  old (-1692.314331, -955.076111)  |S-old| 49.3812  depth +0.2531..+0.2535
    thrust 14  cost 22  old (-1692.314697, -955.041870)  |S-old| 49.4053  depth +0.2065..+0.2074
    thrust 13  cost 21  old (-1692.317749, -954.737122)  |S-old| 49.6209  depth -0.1868..-0.3464

**HOW TIGHTLY `old` IS PINNED IS ITSELF THE MECHANISM.** At thrust 15 it is BIT-IDENTICAL at every one of
the 48 solutions -- CrrPos has finished sliding Link into the corner by the cut frame, so the entry does
not move it at all. Two frames earlier he is still moving: thrust 14's solutions spread over 4e-4 u of z,
thrust 13's over ~0.07 u with one `old` each. The floor thrust cuts BEFORE the brace, and the lunge is a
constant.

Over the whole 45-cell aim window at the frame floor, thrust 13 reads depth < 0 at **all 25 cells that
have a razor solution at all** (-0.472..-0.133) while thrust 14 admits at 23 of 25. So of the two frames,
**one is refused by the corner's geometry and one is legal at thrust 14** (`plan_cost` 22 against the
delivered 23). Because thrust 13's `old` is not pinned, that negative does rest on how finely the razor
curve was sampled -- so it carries its own resolution control: over grid steps 2.0 / 1.0 / 0.5 / 0.25 the
best depth moves inside **0.008 u** and does not trend toward zero (-0.1949 / -0.1901 / -0.1868 / -0.1898)
against a **0.19 u** shortfall.

WHAT IT IS AND IS NOT. ``depth <= 0`` is a PROOF that a configuration cannot clip: the endpoint is on
the near side of both planes and no razor, camera, lean or candidate volume moves it. ``depth > 0`` is
only an ADMISSION -- dust still has to exist and a plan still has to land on it (`entry_reach.hull_scan`,
then `entry_search.confirm_entry`). It is NOT a density model: measured against session 99's live-station
counts the two do not even correlate (cell 2549 at thrust 15 reads depth +0.513 with 0 live stations,
cell 2553 at thrust 14 reads +0.127 with 918), so read it as a gate and never as a rate.

AND THE PLACEMENT CANNOT PAY. Over a +-3 u grid of Tetra placements the thrust-13 depth moves 0.015 u
per u (-0.157..-0.217), because she is PLOWED as the roll sweeps past: her cut-frame overlap is set by
the roll's own geometry, not by where she started. Closing 0.19-0.44 u would take ~12-29 u of placement,
which is 4-10 herd frames against a 2-frame prize and outside `objective.placement_thread`'s ~10 u
lateral window entirely.

    python -m harness.tetrapush.razor_depth screen [cell] [thrust] [lean] [frames]
    python -m harness.tetrapush.razor_depth map [step]          # the whole aim window x thrust
"""
import json
import math
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

from harness.rollstab import geometry_tetra as GT
from harness.tetrapush import entry_reach as ER
from harness.tetrapush import entry_search as ES

#: The delivered clip's lean, and the one every cross-thrust comparison here is measured at.
DELIVERED_LEAN = 64761

#: Newton solves per configuration. The cost is entirely here; seeds are taken in |resid| order so the
#: cap spends itself on the points nearest the curve rather than on a corner of the box.
SOLVE_CAP = 400

#: Solutions closer than this are the same solution reached twice (the curve is marched, not sampled).
SOLUTION_SEP = 0.25


def depth_of(row):
    """The cut endpoint's penetration PAST the nearer wall plane, from a `ShoveCtx.sweep_par` row.

    Slots 8/9 are the two plane functions at `pred`, the PRE-CrrPos endpoint. Positive means the lunge
    gets through; `genuine`'s third clause is this test on the POST-CrrPos endpoint, and the two agree
    whenever the segment is unblocked -- which is the only case where `genuine` can be true anyway
    (gated: `tests/test_razor_depth.py::test_genuine_implies_a_through_going_endpoint`)."""
    return -min(row[8], row[9])


def hull_points(poly, step=1.0):
    """The grid of a polygon's interior, at ``step`` u. Shared by the field and the screen so a negative
    and the seeds it was argued from are the same population."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    pts, x = [], min(xs)
    while x <= max(xs):
        z = min(zs)
        while z <= max(zs):
            if ER.contains(poly, (x, z), 0.0):
                pts.append((x, z))
            z += step
        x += step
    return pts


def razor_solutions(tetra, facing, thrust, lean=DELIVERED_LEAN, frames=ER.FLOOR_FRAMES, hulls=None,
                    step=1.0, nspeed=None, cap=SOLVE_CAP, sep=SOLUTION_SEP):
    """Every in-hull entry where the razor can be zeroed, with its `old`, depth and genuine flag.

    Seeded from the WHOLE hull rather than from `entry_reach.hull_seeds`, and that difference is the
    point: `hull_seeds` takes strongest-leverage points deduped at 6 u, so a claim argued from its
    marches is a claim about the branches those seeds happened to find. Here every in-hull point with
    leverage is a candidate seed, taken in |resid| order.

    Returns a list of ``dict(entry, old, resid, depth, push, genuine, s_dist)``, ``s_dist`` being
    ``|S - old|`` -- the other half of the law."""
    hulls = ER.load() if hulls is None else hulls
    poly = ER.entry_hull(facing, frames, nspeed, hulls)
    pts = hull_points(poly, step)
    ctx, sch, resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
    d = 0.01                                     # `entry_gradient`'s probe, so `grad` is comparable

    def sweep(ps):
        return ctx.sweep_par([(tetra[0], tetra[1], p[0], p[1]) for p in ps], 0)
    r0 = sweep(pts)
    rx = [resid(o) for o in sweep([(p[0] + d, p[1]) for p in pts])]
    rz = [resid(o) for o in sweep([(p[0], p[1] + d) for p in pts])]
    seeds = []
    for i, p in enumerate(pts):
        r = resid(r0[i])
        g = (((rx[i] - r) / d) ** 2 + ((rz[i] - r) / d) ** 2) ** 0.5
        if g >= ER.LEVERAGE_MIN:
            seeds.append((abs(r), p))
    seeds.sort()
    out, seen = [], []
    for _, p0 in seeds[:cap]:
        p, rr, gr = ES.zero_the_resid(tetra, facing, thrust, lean, p0, nspeed=nspeed)
        if gr < ER.LEVERAGE_MIN or abs(rr) > 1e-3 or not ER.contains(poly, p, 0.0):
            continue
        if any(math.hypot(p[0] - q[0], p[1] - q[1]) < sep for q in seen):
            continue
        seen.append(p)
        o = ctx.sweep_par([(tetra[0], tetra[1], p[0], p[1])], 0)[0]
        old = (o[1], o[2])
        out.append(dict(entry=[p[0], p[1]], old=[old[0], old[1]], resid=resid(o), depth=depth_of(o),
                        push=[o[5], o[6]], genuine=bool(o[0]),
                        s_dist=math.hypot(GT.S[0] - old[0], GT.S[1] - old[1])))
    return out


def screen(tetra, facing, thrust, lean=DELIVERED_LEAN, frames=ER.FLOOR_FRAMES, **kw):
    """CAN THIS CONFIGURATION CLIP AT ALL? -- one call, ~5 s, where a dust hunt is hours.

    ``admits`` False is the proof direction (no razor solution's endpoint gets through a plane, so
    `genuine` is impossible at this facing/thrust/lean/budget); True only means the geometry allows it.
    ``reason`` names which of the two ways ``admits`` can be False it is, because "no razor solution at
    all" is session 93's second-lobe result and not a statement about the thrust."""
    sols = razor_solutions(tetra, facing, thrust, lean=lean, frames=frames, **kw)
    if not sols:
        return dict(admits=False, reason='no razor solution inside the reachable hull', n=0,
                    facing=facing, thrust=thrust, lean=lean, frames=frames)
    ds = sorted(s['depth'] for s in sols)
    sd = sorted(s['s_dist'] for s in sols)
    olds = {(s['old'][0], s['old'][1]) for s in sols}
    return dict(admits=ds[-1] > 0.0, reason='' if ds[-1] > 0.0 else
                'the lunge lands %.4f u short of the nearer wall plane at every razor solution' % -ds[-1],
                n=len(sols), n_genuine=sum(1 for s in sols if s['genuine']),
                depth=[ds[0], ds[-1]], s_dist=[sd[0], sd[-1]], n_distinct_old=len(olds),
                old=sorted(olds)[0], facing=facing, thrust=thrust, lean=lean, frames=frames,
                best=max(sols, key=lambda s: s['depth']))


def thrust_map(tetra, cells=None, thrusts=ES.THRUSTS, lean=DELIVERED_LEAN, frames=ER.FLOOR_FRAMES,
               step=1.0, hulls=None, progress=False):
    """`screen` over the whole aim window x thrust -- the map that answers "is this frame collectable
    ANYWHERE on this corner" with a measurement instead of a budget.

    Costs ~4 s per configuration, so the 45-cell window at three thrusts is ~3 min: cheaper than one
    camera pass of the session 95-98 lotteries, and it is the question those passes were betting on."""
    hulls = ER.load() if hulls is None else hulls
    by_cell = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    keys = sorted(by_cell) if cells is None else [c for c in cells if c in by_cell]
    out = []
    for cell in keys:
        row = dict(cell=cell, facing=by_cell[cell], bam=by_cell[cell] - 40841)
        for thrust in thrusts:
            r = screen(tetra, by_cell[cell], thrust, lean=lean, frames=frames, step=step, hulls=hulls)
            r.pop('best', None)
            row['thr%d' % thrust] = r
        out.append(row)
        if progress:
            print("  cell %d (%+d BAM): %s" % (cell, row['bam'], ' '.join(
                '%d:%s' % (t, 'ADMITS' if row['thr%d' % t]['admits'] else 'no') for t in thrusts)),
                flush=True)
    return out


# --------------------------------------------------------------------------- CLI

def _cmd_screen(argv):
    cell = int(argv[0]) if argv else 2552
    thrust = int(argv[1]) if len(argv) > 1 else 13
    lean = int(argv[2]) if len(argv) > 2 else DELIVERED_LEAN
    frames = int(argv[3]) if len(argv) > 3 else ER.FLOOR_FRAMES
    by_cell = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    t0 = time.time()
    r = screen(ES.console_seed()['tetra'], by_cell[cell], thrust, lean=lean, frames=frames)
    print("cell %d (facing %d) thrust %d lean %d, %d walk frames -- plan_cost %d"
          % (cell, by_cell[cell], thrust, lean, frames, frames + thrust + 4))
    print("  %d razor solutions, %d distinct `old`, %d genuine" % (r['n'], r.get('n_distinct_old', 0),
                                                                   r.get('n_genuine', 0)))
    if r['n']:
        print("  depth %+.4f..%+.4f u | |S-old| %.4f..%.4f | old %.6f %.6f"
              % (r['depth'][0], r['depth'][1], r['s_dist'][0], r['s_dist'][1], r['old'][0],
                 r['old'][1]))
    print("  ADMITS A CLIP" if r['admits'] else "  REFUSED: %s" % r['reason'])
    print("  [%.0f s]" % (time.time() - t0))


def _cmd_map(argv):
    step = float(argv[0]) if argv else 1.0
    t0 = time.time()
    rows = thrust_map(ES.console_seed()['tetra'], step=step, progress=True)
    for thrust in ES.THRUSTS:
        have = [r for r in rows if r['thr%d' % thrust]['n']]
        pos = [r for r in have if r['thr%d' % thrust]['admits']]
        print("thrust %2d (plan_cost %2d): %d of %d cells have a razor solution, %d ADMIT a clip"
              % (thrust, ER.FLOOR_FRAMES + thrust + 4, len(have), len(rows), len(pos)))
    out = os.path.join(_rb, '_generated', 's100', 'razor_depth_map.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(source='harness.tetrapush.razor_depth.thrust_map', rows=rows,
                   seconds=time.time() - t0), open(out, 'w'), indent=1)
    print("wrote %s  [%.0f s]" % (out, time.time() - t0))


def main(argv=None):
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'screen'
    if cmd == 'screen':
        _cmd_screen(argv)
    elif cmd == 'map':
        _cmd_map(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
