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


@pytest.mark.slow
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

@pytest.mark.slow
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


@pytest.mark.slow
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


@pytest.mark.slow
def test_the_screen_has_no_false_negative_on_the_session_99_live_configurations():
    """The control every negative here is argued against (`[[search-space-contains-human]]`): the four
    configurations session 99 measured live walkable stations at must all ADMIT. A screen that refused
    one of them would be refusing the delivered clip's own family."""
    tetra, hulls = _tetra(), ER.load()
    cells = _cells()
    for cell, thrust in S99_LIVE:
        r = RD.screen(tetra, cells[cell], thrust, lean=LEAN, frames=4, hulls=hulls, step=2.0)
        assert r['admits'], (cell, thrust, r)


@pytest.mark.slow
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


@pytest.mark.slow
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


@pytest.mark.slow
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


def test_the_arrive_exactly_family_reaches_through_the_plane_only_from_inside_the_wall():
    """THE GATE THAT KEEPS THE REST OF THIS FILE HONEST -- and the session-101 correction that keeps IT
    honest.

    Every hull-scoped negative above is measured over `entry_reach`'s hull, which sits ~239 u from the
    corner brace; a `cut_step` N roll travels 26N u, so out of that hull Link reaches the wall around step 9
    whatever the thrust and CrrPos then SLIDES him along it. From ~390 u out the cut fires as he ARRIVES
    instead, and session 100 measured the endpoint going THROUGH the plane there -- which is why the file
    keeps this configuration pinned.

    **But the placement it needs is 3.54 u BEHIND wall B.** She cannot stand there: her BG wall radius is
    50 u, all 288 live-validated genuine coords sit at >= 56.98 u off both planes, and the engine never
    checks a seed (`placed_step` writes her position with no motion, so her CrrPos has no sweep to test).
    The +0.0399 is a graze taken from inside the wall. Both halves are asserted here, because the depth is
    real and the configuration is not."""
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
    # that entry is outside the hull every hull-scoped negative was argued over
    assert not ER.contains(ER.entry_hull(FACING, 4, None, ER.load()), ARRIVE['entry'], 0.0)
    # still short of barrier clearance, so it is not a clip even before placeability
    assert depth < GENUINE_DEPTH_FLOOR and not row[0], (depth, bool(row[0]))
    # ...and the placement is not one a herd can deliver: 3.54 u behind wall B
    assert not RD.placeable(tetra)
    assert RD.GT.wB.pla.func(RD.GT.p32(*tetra)) < 0.0
    assert abs(RD.GT.wB.pla.func(RD.GT.p32(*tetra)) + 3.5406) < 1e-3


def test_a_placement_is_a_position_she_can_stand_in():
    """THE CLAUSE THE ENGINE LEAVES TO THE CALLER, and it is load-bearing (session 101).

    `_shovec` seeds Tetra by writing her position at `placed_step` with no motion, so her own CrrPos sees no
    sweep to line-check and WallCorrect's offset segment misses a point already behind the plane. A seed
    inside the wall therefore STAYS inside the wall and pushes Link perfectly happily -- from a bearing no
    reachable spot offers, which is exactly how session 100's arrive-exactly hit read +0.0399.

    The bar is her BG wall radius (`npc_zl1.WALL_R` = 50 u, where CrrPos would leave her); the 288
    live-validated genuine coords are the empirical check on it and clear it by 7 u."""
    import math
    lines = [l.split() for l in open(os.path.join(_ROOT, '_generated', 'tetra_placements.tsv'))
             if l.strip() and not l.startswith('#')][1:]
    clear = [min(RD.GT.wA.pla.func(RD.GT.p32(float(f[1]), float(f[2]))),
                 RD.GT.wB.pla.func(RD.GT.p32(float(f[1]), float(f[2])))) for f in lines]
    assert len(clear) == 288
    assert min(clear) > RD.TETRA_WALL_MIN, min(clear)          # every live coord is standable
    assert abs(min(clear) - 56.984) < 1e-2, min(clear)
    assert all(RD.placeable((float(f[1]), float(f[2]))) for f in lines)
    # her console read is placeable; 100 u in -z of it is not, and that is the s100 hit's placement
    t0 = _tetra()
    assert RD.placeable(t0)
    assert not RD.placeable((t0[0], t0[1] - 100.0))
    # and the engine does not enforce it -- the unplaceable seed still returns a pushed, deeper row
    row = _row_at(ARRIVE['entry'], FACING, 13, tetra=(t0[0], t0[1] - 100.0))
    assert math.hypot(row[5], row[6]) > 0.4 and RD.depth_of(row) > 0.0


@pytest.mark.slow
def test_the_depth_floor_is_a_corner_constant_over_the_brace_locus():
    """WHAT THE FLOOR IS A PROPERTY OF. Session 100 read ">= 0.1273" off the four populations that happened
    to have live dust, which cannot distinguish a corner constant from a coincidence of those braces.
    Measured directly in endpoint space instead (`floor_at_brace`), over the locus CrrPos actually parks
    Link on -- planeA pinned at 35 with planeB 35..35.5, and the mirror -- the floor is **0.1154..0.1216
    with no trend in the brace**. So it is the corner's, and a search may screen against the low end."""
    def brace(pa, pb):
        a, b = RD.GT.wA.pla, RD.GT.wB.pla
        det = a.nx * b.nz - a.nz * b.nx
        rx, rz = pa - (a.ny * RD.GT.LINK_Y + a.d), pb - (b.ny * RD.GT.LINK_Y + b.d)
        return ((rx * b.nz - a.nz * rz) / det, (a.nx * rz - rx * b.nx) / det)

    floors = []
    for t in (35.0, 35.1, 35.2, 35.3, 35.4, 35.5):
        for old in (brace(35.0, t), brace(t, 35.0)):
            d, depth = RD.floor_at_brace(old)
            assert d is not None, old
            floors.append(depth)
    assert min(floors) >= 0.1150 and max(floors) <= 0.1220, (min(floors), max(floors))
    assert max(floors) - min(floors) < 0.007, sorted(floors)
    assert RD.DEPTH_FLOOR <= min(floors)                        # the screen never over-admits
    # the two real braces this corner has produced land in the same band
    for old in ((-1692.3129882812, -955.2207031250), (-1692.3143310547, -955.0761108398)):
        _d, depth = RD.floor_at_brace(old)
        assert 0.1150 < depth < 0.1220, (old, depth)


def test_the_clip_is_bought_with_the_pushs_projection():
    """THE LAW, DECOMPOSED (session 101). `|base|` -- the cut frame's roll step plus the cut root translate
    -- is a CONSTANT: the thrust does not enter it and the facing only rotates it. So the whole of a clip's
    penetration is the PUSH's projection onto the `old -> S` ray against the brace distance, and the two
    move together with the frames, which is what makes the thrust a real cost rather than a free draw."""
    # base is thrust-invariant exactly, and facing-invariant to sine-table quantization
    bases = {t: RD.base_reach(FACING, LEAN, t) for t in (13, 14, 15)}
    assert bases[13] == bases[14] == bases[15] == RD.BASE_REACH
    for f in (40400, 40511, 41296):
        assert abs(RD.base_reach(f, LEAN, 13) - RD.BASE_REACH) < 1e-5, f
    # the pinned rows, read through the law
    law = {t: RD.law_of(_row_at(p['entry'], FACING, t)) for t, p in PINNED.items()}
    assert law[13]['push_u'] < law[14]['push_u'] < law[15]['push_u']      # more frames, more push
    assert law[13]['s_dist'] > law[14]['s_dist'] > law[15]['s_dist']      # AND a nearer brace
    # d_ray reproduces the engine's plane depth through the ray/normal projection
    for t, l in law.items():
        assert abs(l['kappa'] * l['d_ray'] - l['depth']) < 0.01, (t, l)
        assert 0.70 < l['kappa'] < 0.72, l['kappa']
    # and the floor, restated as what a configuration must produce
    need = law[13]['s_dist'] + RD.DEPTH_FLOOR / law[13]['kappa'] - RD.BASE_REACH
    assert law[13]['push_u'] < need                                        # thrust 13 is short
    assert law[15]['push_u'] > law[15]['s_dist'] + RD.DEPTH_FLOOR / law[15]['kappa'] - RD.BASE_REACH


def test_the_brace_is_reproducible_at_every_thrust_but_the_push_is_not():
    """WHAT ACTUALLY DIFFERS BETWEEN THE THRUSTS (Dereck, session 101: "it's all the same animations").

    He is right, and the measurement says so three ways: the cut lunge is a CONSTANT at every thrust, the
    roll step is constant, and shifting the entry by whole roll steps puts Link on the **bit-identical**
    brace two frames earlier. So the brace is a property of the ENTRY SET, not of the thrust - which
    retires the "0.24 u of brace" half of the session-100 reading.

    What does not survive the shift is the PUSH. The cut-frame contact is a ~1.2 u graze on an 80 u radius
    sum, and Link's Co-cylinder centre is posed from the model, so it is indexed by the ROLL'S OWN
    ANIMATION FRAME - it swings 1.1..31.3 u off his position over the roll, 2-9 u per frame. Two frames
    earlier the same standing position is not touching her at all, and the push that buys the depth is
    gone. Same animation; a different frame of it."""
    import math
    tetra = _tetra()
    e15, rr, _gr = ES.zero_the_resid(tetra, FACING, 15, LEAN,
                                     (-1529.6196515725367, -779.7578481252098))
    assert abs(rr) < 1e-3
    sch = ES.fast_schedule(FACING, LEAN, 15)
    dx, dz = sch['dx'][0], sch['dz'][0]
    olds, pushes = {}, {}
    for thrust, shift in ((15, 0), (14, 1), (13, 2)):
        entry = (e15[0] + shift * dx, e15[1] + shift * dz)
        row = _row_at(entry, FACING, thrust, tetra=tetra)
        olds[thrust] = (row[1], row[2])
        pushes[thrust] = math.hypot(row[5], row[6])
    # the brace: bit-identical at all three, and it IS the delivered clip's own
    assert olds[13] == olds[14] == olds[15] == PINNED[15]['old']
    # the push: present at the thrust the pose was sampled for, gone two frames earlier
    assert pushes[15] > 0.6 and pushes[14] == 0.0 and pushes[13] == 0.0
    # ...because the Co centre is animation-driven and moves several units per frame
    nr = sch['nroot']
    cen = [(0.5 * (sum(sch['chx'][k][:nr]) + sum(sch['chx'][k][nr:])),
            0.5 * (sum(sch['chz'][k][:nr]) + sum(sch['chz'][k][nr:]))) for k in range(len(sch['chx']))]
    mags = [math.hypot(*c) for c in cen]
    assert min(mags) < 1.2 and max(mags) > 31.0, (min(mags), max(mags))
    step = [math.hypot(cen[k][0] - cen[k - 1][0], cen[k][1] - cen[k - 1][1])
            for k in range(1, len(cen))]
    assert max(step) > 8.0 and sorted(step)[len(step) // 2] > 5.0, (max(step), sorted(step))
    # between the two cut frames in question it moves ~2.8 u, on a 1.2 u overlap
    assert 2.0 < math.hypot(cen[17][0] - cen[15][0], cen[17][1] - cen[15][1]) < 4.0


def test_the_entry_lean_is_spent_before_the_cut_fires():
    """WHY THE LEAN AXIS IS NOT A LEVER AT A LATE CUT, and it is general rather than about this corner.
    `m351C` decays 35% per roll frame (`entry_search.lean_at_roll`), so the delivered lean's -388 draw is
    -1 by roll frame 15 and the pose the Co centre is read off is the same whatever the entry lean was.
    Measured: over +-3000 s16 at the arrive-exactly configuration the depth moves 0.0003 u.

    **ON THE RAZOR, not at a frozen entry.** Changing the lean moves the razor, so holding the entry while
    sweeping it compares off-curve points and reads a spurious 0.03 u of "lean sensitivity" -- the entry has
    to be re-solved per lean, which is what makes the inertness a statement about the lever."""
    from tww_sim.core.mathlib import s16_signed
    lean, draws = LEAN, []
    for _k in range(16):
        draws.append(s16_signed(lean) >> 1)
        lean = ES.lean_at_roll(lean)
    assert draws[0] == -388
    assert abs(draws[15]) <= 1                                   # spent by the cut step of thrust 13
    t0 = _tetra()
    tetra = (t0[0] + ARRIVE['tetra_off'][0], t0[1] + ARRIVE['tetra_off'][1])
    depths = []
    for lv in (-3000, -1500, 0, 1500, 3000):
        lean = lv & 0xFFFF
        p, rr, gr = ES.zero_the_resid(tetra, FACING, 13, lean, ARRIVE['entry'])
        assert abs(rr) < 1e-3, (lv, rr)
        depths.append(RD.depth_of(_row_at(p, FACING, 13, lean=lean, tetra=tetra)))
    assert max(depths) - min(depths) < 1e-3, depths


@pytest.mark.slow
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
def test_no_placeable_configuration_reaches_the_floor_at_thrust_13_at_the_best_cells():
    """THE HULL-FREE VERDICT, with the placement clause enforced (session 101).

    With her constrained to spots she can stand in, the cells that come closest at thrust 13 still miss the
    corner's floor by ~0.14 u -- and the reason is legible in the law: the push that AIMS at the corner is
    the same push that shoves Link off the brace, so buying `push_u` costs `s_dist` faster than it pays.
    The exhaustive 45-cell form is the slow test below."""
    for cell, facing, want in ((2554, 40869, -0.0215), (2553, 40850, -0.0281), (2552, 40841, -0.0392)):
        b = RD.placeable_screen(facing, 13, lean=LEAN)
        assert b is not None, cell
        assert b['depth'] < RD.DEPTH_FLOOR, (cell, b['depth'])
        assert abs(b['depth'] - want) < 0.01, (cell, b['depth'], want)
        assert RD.placeable(b['tetra'])
        # the trade that refuses it: this cell's push is well aimed and its brace pays for it
        assert b['push_u'] > 0.15 and b['s_dist'] > 49.42, b


@pytest.mark.slow
def test_no_placeable_configuration_at_any_aim_cell_reaches_the_floor_at_thrust_13():
    """The exhaustive hull-free, placement-constrained verdict over all 45 cells (~2 min): NONE reaches the
    corner's depth floor at thrust 13. This is the gate that has to flip before the second frame is real --
    and the set it is measured over is named in the name: placeable placements, every aim cell, no hull."""
    cells = sorted({ES.aim_cell(f) for f, _b, _s in ES.aim_cells()})
    by_cell = _cells()
    best = []
    for cell in cells:
        b = RD.placeable_screen(by_cell[cell], 13, lean=LEAN)
        if b:
            assert b['depth'] < RD.DEPTH_FLOOR, (cell, b['depth'])
            best.append((b['depth'], cell))
    assert len(best) >= 40, len(best)
    assert max(best)[0] < 0.0, max(best)               # not one of them even reaches the PLANE
    assert abs(max(best)[0] + 0.0215) < 0.01, max(best)


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
