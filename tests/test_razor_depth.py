"""THE DEPTH AT THE RAZOR: which thrusts this corner can clip at all (session 100).

Session 99 found the frame-minimal objective never charged for the B thrust and that the decomp gate
makes thrust 13 the floor -- two frames the delivered clip leaves on the table -- and its handoff named
the TETRA PLACEMENT as the route to them. These gates pin what the measurement found instead:

  * `resid ~ 0` forces the cut endpoint onto the `old -> S` ray (S is the corner VERTEX, on both wall
    planes), so the penetration past the plane is pinned by how close the roll braces and how much push
    survives to the cut -- and ``depth <= 0`` makes `genuine` impossible;
  * from the FRAME-FLOOR HULL that penetration is +0.2533 / +0.2074 / **-0.1868** u at thrust 15 / 14 / 13,
    so thrust 14 (`plan_cost` 22 against the delivered 23) is a frame available with nothing else changed;
  * at the scale a herd tolerates (+-3 u) the placement is inert -- 0.015 u of depth per u -- because Tetra
    is PLOWED as the roll sweeps past, so her cut-frame overlap is the roll's geometry and not her seed.

**THE HULL IS PART OF EVERY NEGATIVE HERE AND THE NAMES SAY SO.** It sits ~239 u from the corner brace and
a `cut_step` N roll travels 26N u, so out of it Link always reaches the wall early and slides. Remove it and
entries ~390 u out cut as he ARRIVES and go through the plane -- pinned by
`test_the_arrive_exactly_family_reaches_through_the_plane_at_cut_step_15`, which is the gate that keeps this
file honest about what it did and did not measure (`knowledge/history/thrust-13-refused-by-geometry.md`).

Values are exact pinned model outputs (`[[zero-ulp-tests-only]]`): every depth/old/push assertion below
re-sweeps a PINNED ENTRY, which is deterministic, rather than trusting a Newton path.
"""
import json
import os
import warnings

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

from harness.tetrapush import entry_reach as ER            # noqa: E402
from harness.tetrapush import entry_search as ES           # noqa: E402
from harness.tetrapush import razor_depth as RD            # noqa: E402

warnings.simplefilter('ignore')

#: The delivered clip's cell/facing, and the lean every cross-thrust comparison is measured at.
FACING = 40841
LEAN = RD.DELIVERED_LEAN

#: The deepest razor solution per thrust at the delivered cell, 4 walk frames -- ENTRY pinned, so the
#: sweep that reads `old`/`depth`/`push` off it is deterministic and the assertions can be exact.
PINNED = {
    15: dict(entry=(-1529.6196515725367, -779.7578481252098),
             old=(-1692.3143310546875, -955.0761108398438), depth=0.2532958984375,
             push=(-0.5970568060874939, -0.13828444480895996)),
    14: dict(entry=(-1538.8150807879886, -792.096172523697),
             old=(-1692.314697265625, -955.0418701171875), depth=0.2073974609375,
             push=(-0.5514636635780334, -0.12664394080638885)),
    13: dict(entry=(-1540.24041174055, -792.6615159765829),
             old=(-1692.3177490234375, -954.7371215820312), depth=-0.186767578125,
             push=(-0.15926744043827057, -0.030567355453968048)),
}

#: The four configurations session 99 MEASURED live stations at -- the screen's no-false-negative set.
S99_LIVE = ((2552, 15), (2552, 14), (2553, 14), (2549, 14))


def _tetra():
    return ES.console_seed()['tetra']


def _cells():
    return {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}


def _row_at(entry, facing, thrust, lean=LEAN, tetra=None):
    tetra = _tetra() if tetra is None else tetra
    ctx, sch, resid = ES.build_fast(facing, lean, thrust)
    return ctx.sweep_par([(tetra[0], tetra[1], entry[0], entry[1])], 0)[0]


# ------------------------------------------------------------------ the law, at pinned entries

def test_the_pinned_razor_entries_reproduce_their_old_depth_and_push_exactly():
    """The measurement this whole verdict rests on, re-derived from the entry alone. Exact, not close:
    `old`, the cut-frame push and the two plane values are engine outputs of a deterministic run."""
    for thrust, p in PINNED.items():
        row = _row_at(p['entry'], FACING, thrust)
        assert (row[1], row[2]) == p['old'], thrust
        assert (row[5], row[6]) == p['push'], thrust
        assert RD.depth_of(row) == p['depth'], thrust


def test_the_pocket_orders_the_thrusts_and_the_floor_thrust_falls_outside_it():
    """THE LAW, AT THE FRAME FLOOR. A razor solution points the cut at S, the corner VERTEX, which lies on
    both wall planes -- so the penetration is ``|base + push| - |S - old|`` and the levers are how close the
    roll braces and how much push survives to the cut frame. Session 99's "0.65 u pocket" restated: out of
    the frame-floor hull, firing at `cut_step` 15 leaves Link 0.24 u short of the brace thrust 15 reaches
    and the push 0.45 u weaker, and the cut lunge is a constant."""
    import math
    d = {}
    for thrust, p in PINNED.items():
        old = _row_at(p['entry'], FACING, thrust)[1:3]
        d[thrust] = dict(s=math.hypot(RD.GT.S[0] - old[0], RD.GT.S[1] - old[1]),
                         depth=p['depth'], push=math.hypot(*p['push']), old_z=old[1])
    # the brace gets deeper into the corner with every extra roll frame, and the razor's push with it
    assert d[13]['s'] > d[14]['s'] > d[15]['s']
    assert d[13]['push'] < d[14]['push'] < d[15]['push']
    # so the penetration is ordered, and only thrust 13 changes SIGN
    assert d[13]['depth'] < 0.0 < d[14]['depth'] < d[15]['depth']
    # the shortfall is a fifth of a unit, not a rounding: 0.24 u of brace plus 0.45 u of push
    assert 0.23 < d[13]['s'] - d[15]['s'] < 0.25
    assert 0.45 < d[15]['push'] - d[13]['push'] < 0.46


def test_the_brace_pin_loosens_as_the_cut_fires_earlier():
    """THE MECHANISM, and it is legible in how tightly `old` is pinned.

    At thrust 15 CrrPos has finished sliding Link into the corner by the cut frame, so `old` is
    **bit-identical** at every in-hull razor solution -- the entry does not move it at all. Two frames
    earlier he is still moving: thrust 14's solutions spread over 4e-4 u of z, thrust 13's over ~0.07 u,
    with essentially one `old` per solution. That is the same fact the depth reports, seen upstream of it:
    the floor thrust cuts before the brace, and the lunge is a constant."""
    tetra = _tetra()
    hulls = ER.load()
    got = {}
    for thrust in (15, 14, 13):
        sols = RD.razor_solutions(tetra, FACING, thrust, lean=LEAN, frames=4, hulls=hulls, step=1.0)
        assert len(sols) >= 15, (thrust, len(sols))
        olds = {(s['old'][0], s['old'][1]) for s in sols}
        zs = sorted(o[1] for o in olds)
        got[thrust] = (len(olds), len(sols), zs[-1] - zs[0])
    # thrust 15: one `old`, exactly -- and it is the pinned literal
    assert got[15][0] == 1, got[15]
    assert got[15][2] == 0.0
    assert sorted({(s['old'][0], s['old'][1]) for s in RD.razor_solutions(
        tetra, FACING, 15, lean=LEAN, frames=4, hulls=hulls, step=1.0)})[0] == PINNED[15]['old']
    # thrust 14: pinned to a ten-thousandth of a unit; thrust 13: not pinned at all
    assert got[14][0] <= 6 and got[14][2] < 5e-4, got[14]
    assert got[13][0] >= got[13][1] - 1 and got[13][2] > 0.04, got[13]


# --------------------------------------------------------------- the screen, and its two directions

def test_from_the_frame_floor_hull_the_floor_thrust_cannot_reach_the_plane():
    """The verdict AT THE FRAME FLOOR, which is where a plan at the delivered cost puts the entry: thrust 14
    (`plan_cost` 22) admits a clip, thrust 13 (cost 21) cannot reach the plane from any entry the hull
    holds, and the refusal names its size. Not a claim about the corner -- see the arrive-exactly gate."""
    tetra, hulls = _tetra(), ER.load()
    for thrust in (15, 14):
        r = RD.screen(tetra, FACING, thrust, lean=LEAN, frames=4, hulls=hulls, step=2.0)
        assert r['admits'] and r['depth'][1] > 0.0, (thrust, r)
    r13 = RD.screen(tetra, FACING, 13, lean=LEAN, frames=4, hulls=hulls, step=2.0)
    assert not r13['admits'], r13
    assert r13['n'] > 0                                  # it LOOKED: solutions exist, none get through
    assert 'short of the nearer wall plane' in r13['reason']
    assert -0.35 < r13['depth'][1] < -0.15, r13['depth']


#: Configurations session 99 measured live stations at -- (cell, facing, thrust, lean).
ON_LOCUS = ((2552, 40841, 15, 64761), (2552, 40841, 14, 64761), (2553, 40850, 14, 65151),
            (2551, 40820, 15, 64793))


def test_genuine_implies_a_through_going_endpoint():
    """THE GATE THAT COULD FALSIFY THE VERDICT, so it is the one that must stay green.

    `depth` is read at the PRE-CrrPos endpoint while `genuine` tests the POST-CrrPos one; they agree
    whenever the cut segment is unblocked, which is the only case `genuine` can be true in -- but that is
    an argument, and a screen used to call a thrust impossible owes a measurement
    (`[[infeasible-needs-proof]]`). One genuine row with ``depth <= 0`` retires the whole finding.

    Sampled where the genuine rows are: dense ACROSS the locus at `hull_scan`'s live stations
    (`configuration_band`'s construction), which yields hundreds of them in seconds. A grid cannot do
    this job -- the genuine set is a ~1e-4 u ribbon, and a 0.25 u grid over 7.44 M in-hull entries turned
    up ONE genuine row."""
    tetra = _tetra()
    ngen = 0
    for cell, facing, thrust, lean in ON_LOCUS:
        r = ER.hull_scan(tetra, facing, thrust, lean, frames=4, sep=6.0)
        assert r['live_at'], (cell, thrust, lean)          # the control: dust is where s99 says
        ctx, sch, resid = ES.build_fast(facing, lean, thrust)
        for st in r['live_at'][:6]:
            g = ES.entry_gradient(tetra, st, facing=facing, m351c=lean, thrust=thrust)
            ux, uz = g['gx'] / g['grad'], g['gz'] / g['grad']
            n, half = 2001, 0.02
            pts = [(tetra[0], tetra[1], st[0] + (2.0 * i / (n - 1) - 1.0) * half * ux,
                    st[1] + (2.0 * i / (n - 1) - 1.0) * half * uz) for i in range(n)]
            for o in ctx.sweep_par(pts, 0):
                if o[0]:
                    ngen += 1
                    assert RD.depth_of(o) > 0.0, (cell, thrust, lean, RD.depth_of(o))
    assert ngen >= 50, ngen                               # it had a real population to falsify with


def test_the_screen_has_no_false_negative_on_the_session_99_live_configurations():
    """The control every negative here is argued against (`[[search-space-contains-human]]`): the four
    configurations session 99 measured live walkable stations at must all ADMIT. A screen that refused
    one of them would be refusing the delivered clip's own family."""
    tetra, hulls = _tetra(), ER.load()
    cells = _cells()
    for cell, thrust in S99_LIVE:
        r = RD.screen(tetra, cells[cell], thrust, lean=LEAN, frames=4, hulls=hulls, step=2.0)
        assert r['admits'], (cell, thrust, r)


def test_the_placement_is_inert_at_the_scale_a_herd_tolerates():
    """THE PLACEMENT AT HERD SCALE, measured rather than reasoned -- and note the scale in the name.

    She is PLOWED as the roll sweeps past, so her overlap on the CUT frame is set by the roll's own
    geometry: over +-3 u of placement the thrust-13 depth moves ~0.015 u per u. So no herd-scale nudge pays
    for 0.19 u. It does NOT follow that she is irrelevant -- at ~100 u she moves the entry family
    altogether, which is what the arrive-exactly gate below records."""
    tetra, hulls = _tetra(), ER.load()
    depths = []
    for ox, oz in ((0.0, 0.0), (3.0, 3.0), (-3.0, -3.0), (3.0, -3.0), (-3.0, 3.0)):
        r = RD.screen((tetra[0] + ox, tetra[1] + oz), FACING, 13, lean=LEAN, frames=4, hulls=hulls,
                      step=2.0)
        assert not r['admits'], ((ox, oz), r)
        depths.append(r['depth'][1])
    assert max(depths) - min(depths) < 0.10, depths       # 6 u of Tetra buys under 0.1 u of depth


def test_one_more_walk_frame_does_not_open_thrust_13():
    """The frame counterfactual, because `plan_cost` = plan_frames + thrust + 4 would still make
    thrust 13 at FIVE walk frames (cost 22) worth a frame. The bigger hull reaches 2.3x the entries and
    the best of them is no closer to the plane."""
    tetra, hulls = _tetra(), ER.load()
    four = RD.screen(tetra, FACING, 13, lean=LEAN, frames=4, hulls=hulls, step=1.0)
    five = RD.screen(tetra, FACING, 13, lean=LEAN, frames=5, hulls=hulls, step=1.0)
    assert not four['admits'] and not five['admits'], (four, five)
    assert five['n'] > four['n'] > 0                       # it did look at more entries
    assert five['depth'][1] <= four['depth'][1] + 0.01     # and got no nearer the plane


def test_the_thrust_13_shortfall_is_not_a_grid_ARTEFACT():
    """The negative's own resolution control, since at thrust 13 `old` is NOT pinned and so the verdict
    does rest on how finely the razor curve was sampled.

    Measured over grid steps 2.0 / 1.0 / 0.5 / 0.25 the best depth moves inside **0.008 u** and does not
    trend toward zero (-0.1949 / -0.1901 / -0.1868 / -0.1898) against a **0.19 u** shortfall -- a ~24x
    margin. Refinement is not what stands between this thrust and a clip."""
    tetra, hulls = _tetra(), ER.load()
    best = []
    for step in (2.0, 1.0, 0.5):
        sols = RD.razor_solutions(tetra, FACING, 13, lean=LEAN, frames=4, hulls=hulls, step=step)
        assert sols
        best.append(max(s['depth'] for s in sols))
    assert all(b < 0.0 for b in best), best
    assert max(best) - min(best) < 0.01, best              # converged, not creeping toward 0
    assert -max(best) > 20 * (max(best) - min(best)), best  # the shortfall dwarfs the sensitivity


#: The through-going razor solution at `cut_step` 15, found with the hull REMOVED: Tetra 100 u in -z of her
#: console read, entry ~390 u from the corner brace so the cut fires as Link ARRIVES rather than sliding.
ARRIVE = dict(tetra_off=(0.0, -100.0), entry=(-1422.7771410239, -677.8451682961))

#: The shallowest depth any GENUINE row on this corner has (cell 2553 thrust 14) -- the barrier-clearance
#: bar the arrive-exactly family still has to reach.
GENUINE_DEPTH_FLOOR = 0.1273


def test_the_arrive_exactly_family_reaches_through_the_plane_at_cut_step_15():
    """THE GATE THAT KEEPS THE REST OF THIS FILE HONEST (Dereck's re-ask, session 100).

    Every negative above is measured over `entry_reach`'s hull, which sits ~239 u from the corner brace --
    and a `cut_step` N roll travels 26N u, so out of that hull Link reaches the wall around step 9 whatever
    the thrust and CrrPos then SLIDES him along it. The hull holds only the arrive-early-and-slide family,
    and two fewer slide frames IS the 0.19 u shortfall.

    From ~390 u out the cut fires as he ARRIVES, and with Tetra 100 u away the endpoint goes THROUGH: this
    pins that solution so no future session re-reads "thrust 13 is refused at the frame floor" as "thrust 13
    is impossible" (`knowledge/history/thrust-13-refused-by-geometry.md`).

    It also pins what is still missing -- `genuine` needs the swept segment to clear the CrrPos barrier, and
    every genuine row on this corner sits at depth >= `GENUINE_DEPTH_FLOOR`, so this family is ~0.087 u
    short. If a future pass closes that, this assertion flips and the test says so."""
    import math
    t0 = _tetra()
    tetra = (t0[0] + ARRIVE['tetra_off'][0], t0[1] + ARRIVE['tetra_off'][1])
    row = _row_at(ARRIVE['entry'], FACING, 13, tetra=tetra)
    depth = RD.depth_of(row)
    old = (row[1], row[2])
    # the endpoint clears the plane, where every frame-floor entry misses it by 0.19-0.35 u
    assert depth > 0.0, depth
    assert 0.03 < depth < 0.05, depth
    # and it is the ARRIVAL, not a slide: the roll's travel to `old` is ~26 * cut_step
    travel = math.hypot(ARRIVE['entry'][0] - old[0], ARRIVE['entry'][1] - old[1])
    assert 375.0 < travel < 390.0, travel
    assert math.hypot(RD.GT.S[0] - old[0], RD.GT.S[1] - old[1]) < 49.38   # nearer S than thrust 15's brace
    # that entry is outside the hull every negative above was argued over -- which is the whole point
    assert not ER.contains(ER.entry_hull(FACING, 4, None, ER.load()), ARRIVE['entry'], 0.0)
    # still short of barrier clearance, so it is not a clip yet
    assert depth < GENUINE_DEPTH_FLOOR and not row[0], (depth, bool(row[0]))


def test_the_genuine_depth_floor_is_measured_not_assumed():
    """`GENUINE_DEPTH_FLOOR` is the bar the open frame is judged against, so it is measured here rather than
    quoted: at each configuration with known dust, every genuine row's depth is bit-constant across its own
    population, and the shallowest of the four is 0.1273 (cell 2553, thrust 14)."""
    tetra = _tetra()
    floors = []
    for cell, facing, thrust, lean in ON_LOCUS:
        r = ER.hull_scan(tetra, facing, thrust, lean, frames=4, sep=6.0)
        ctx, sch, resid = ES.build_fast(facing, lean, thrust)
        ds = set()
        for st in r['live_at'][:4]:
            g = ES.entry_gradient(tetra, st, facing=facing, m351c=lean, thrust=thrust)
            ux, uz = g['gx'] / g['grad'], g['gz'] / g['grad']
            n, half = 2001, 0.02
            pts = [(tetra[0], tetra[1], st[0] + (2.0 * i / (n - 1) - 1.0) * half * ux,
                    st[1] + (2.0 * i / (n - 1) - 1.0) * half * uz) for i in range(n)]
            ds |= {RD.depth_of(o) for o in ctx.sweep_par(pts, 0) if o[0]}
        assert ds, (cell, thrust)
        assert max(ds) - min(ds) < 1e-3, (cell, thrust, sorted(ds)[:3])   # bit-constant per configuration
        floors.append(min(ds))
    assert abs(min(floors) - GENUINE_DEPTH_FLOOR) < 1e-3, sorted(floors)


@pytest.mark.slow
def test_no_frame_floor_entry_at_any_cell_reaches_the_plane_at_thrust_13():
    """The exhaustive form of the FRAME-FLOOR verdict (~3 min): of the 45 cells the aim alphabet reaches, 25
    have a razor solution inside the hull and NONE of them reaches the plane at thrust 13, while thrust 14
    does at 23 of 25. So at the floor the second frame is not a cell, a camera or a lean away -- it is a
    different entry family (`test_the_arrive_exactly_family_...`)."""
    tetra = _tetra()
    rows = RD.thrust_map(tetra, lean=LEAN, frames=4, step=1.0)
    have13 = [r for r in rows if r['thr13']['n']]
    have14 = [r for r in rows if r['thr14']['n']]
    assert len(have13) >= 20, len(have13)
    assert not any(r['thr13']['admits'] for r in have13)
    assert sum(1 for r in have14 if r['thr14']['admits']) >= 20
