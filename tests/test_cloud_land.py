"""THE ENUMERATED-CLOUD LANDING KEEP (session 107) -- gates `harness/tetrapush/cloud_land.py`.

Session 106 measured that the last-cycle keep (`full_herd.escape_probe`) ranks against
`objective.placement_thread`'s FIT, which a 2D row cloud makes meaningless, so every beam it cut was
landing-blind. `cloud_land` replaces the predictor with the enumeration. What has to be gated is not
the floor it finds (that is a measurement, and it moves) but the three things a keep can be WRONG
about: that the enumerated grid CONTAINS the shipped probe's own variant, that the rank is in the
objective's frame currency rather than in units, and that a non-firing endpoint cannot end a plan.

Every assertion here is exact -- pinned arithmetic or an identity -- never a tolerance
(`[[zero-ulp-tests-only]]`). The enumeration is ~28 s at the shipped resolution, so the tests that
need a real rollout run a THINNED grid (one rotate, coarse flip) and say so; the full-resolution
sweep belongs to a solve, not to a gate.
"""
import math
import warnings

import pytest

from harness.tetrapush import away_walk as AW
from harness.tetrapush import cloud_land as CL
from harness.tetrapush import full_herd as FH
from harness.tetrapush import objective as O
from harness.tetrapush import seeds as SD
from harness.tetrapush.reposition import HerdLine

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def env():
    return SD.load_env()


@pytest.fixture(scope="module")
def hl(env):
    return HerdLine.from_env(env)


@pytest.fixture(scope="module")
def arrival(env, hl):
    """A synthetic hot arrival -- the cheap, tracked-fixture-free endpoint every terminal test uses."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return FH.synthetic_hot_arrival(env, hl, coord_idx=287, d_short=0.0, feet=64.0)


def _rows():
    """Three synthetic rows with DIFFERENT plan_cost, enough to pin the row choice's arithmetic."""
    return [dict(idx=0, x=0.0, z=0.0, plan_cost=23),
            dict(idx=1, x=10.0, z=0.0, plan_cost=20),
            dict(idx=2, x=100.0, z=0.0, plan_cost=19)]


# --------------------------------------------------------------- the grid contains the reference

def test_the_enumerated_grid_contains_the_shipped_probes_own_variant(arrival, hl):
    """`[[search-space-contains-human]]`: a keep that enumerates must contain what the ranked probe
    picks, or the two measures are not comparable on the same endpoint. Run BOTH at the same thinned
    resolution and assert the probe's chosen knobs are a member of the cloud."""
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2])
    cloud = CL.atom_cloud(arrival['run'], hl, **kw)
    assert cloud, "the thinned grid produced no variants at all"
    picked = AW.probe(arrival['run'], hl, flip_step=AW.FLIP_SPAN,
                      rotate_offs=AW.ROTATE_OFFS[1:2])
    assert picked is not None
    keys = ('turnaround_first', 'rotate_side', 'rotate_off', 'flip_bearing', 'exit_bearing')
    want = tuple(picked['knobs'][k] for k in keys)
    have = {tuple(r['knobs'][k] for k in keys) for r in cloud}
    assert want in have, "probe's variant %r is not in the enumerated cloud" % (want,)


def test_the_grid_is_the_full_cross_product_of_its_knobs(arrival, hl):
    """The enumeration's SIZE is the product of its knob axes (flip x rotate x turnaround x side x
    exit), so a silently-dropped axis shows up here rather than as a quietly smaller search."""
    rots = AW.ROTATE_OFFS[1:2]
    flips = AW.flip_arc(hl, step=AW.FLIP_SPAN)
    cloud = CL.atom_cloud(arrival['run'], hl, flip_step=AW.FLIP_SPAN, rotate_offs=rots)
    assert len(cloud) == len(flips) * len(rots) * 2 * 2 * 2


# ------------------------------------------------------------------- the row choice and the rank

def test_the_cheapest_row_wins_not_the_nearest_one():
    """The rows are 19-23 frames apart (session 104), so `_nearest_row` ranks in FRAMES: a row 10 u
    away at cost 20 must beat one 0 u away at cost 23, because 10 u is ~0.8 frames at the ceiling."""
    rows = _rows()
    miss, row = CL._nearest_row(0.0, 0.0, rows)
    assert row['idx'] == 1 and miss == 10.0
    # ...and the arithmetic that decided it, exactly
    assert 20 + O.remaining_frames(10.0) < 23 + O.remaining_frames(0.0)


def test_a_far_cheap_row_does_not_win_when_the_distance_outweighs_it():
    """The same rule in the other direction -- 100 u is ~8 frames, which no 4-frame cost gap buys."""
    _miss, row = CL._nearest_row(0.0, 0.0, [_rows()[0], _rows()[2]])
    assert row['idx'] == 0


def test_the_bound_reduces_to_the_exact_total_on_the_row():
    """`cloud_bound` is `objective.plan_bound`'s shape applied to the whole candidate, so a landing
    ON a row must be priced at exactly herd + atom + plan_cost -- no residual term."""
    assert O.remaining_frames(0.0) == 0.0
    frames, n_atom, cost = 71, 7, 23
    assert frames + n_atom + cost + O.remaining_frames(0.0) == 101


def test_the_rank_is_in_frames_so_a_fast_wide_atom_can_beat_a_slow_exact_one():
    """Session 106's exchange rate, pinned as arithmetic: 5.93 u on a 2-frame atom against 0.299 u on
    a 16-frame one. A miss-only rank prefers the slow variant; the frame rank must prefer the fast
    one, since 5.6 u of landing is worth ~0.45 frames and the atoms differ by 14."""
    fast = 75 + 2 + 20 + O.remaining_frames(5.93)
    slow = 75 + 16 + 20 + O.remaining_frames(0.299)
    assert fast < slow
    assert 5.93 > 0.299                      # the miss rank would invert it


# ------------------------------------------------------------------------- rule 3 and the contract

def test_a_non_firing_endpoint_cannot_end_a_plan(arrival, hl):
    """Rule 3 (`away_walk.fires`) stays the acceptance: no firing variant -> fires False, an infinite
    bound so the endpoint sorts LAST, and no in-band claim. Uses the thinned grid; the synthetic hot
    arrival is a known non-firer, and if it ever starts firing this reads the firing branch instead."""
    res = CL.cloud_landing(arrival['run'], arrival['frames'], hl, _rows(),
                           flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2])
    assert res['n_variants'] > 0
    if res['n_firing'] == 0:
        assert res['fires'] is False
        assert res['bound'] == float('inf')
        assert res['best'] is None and res['in_band'] is None and res['front'] == []
    else:
        assert res['fires'] is True and math.isfinite(res['bound'])
        assert res['best']['bound'] == res['bound']


def test_cloud_probe_answers_escape_probes_contract(arrival, hl):
    """The two keeps must be swappable in beam code, so `cloud_probe` carries `escape_probe`'s
    load-bearing keys -- ``fires`` (rule 3) and ``bound`` (the sort key)."""
    res = CL.cloud_probe(arrival['run'], arrival['frames'], hl, _rows(),
                         flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2])
    for k in ('fires', 'bound', 'miss', 'frames'):
        assert k in res
    assert res['frames'] == arrival['frames']
    assert isinstance(res['fires'], bool)


# -------------------------------------------------- the fan is a SET, and the predictor's currency

def test_the_residual_fan_of_a_non_firing_endpoint_is_EMPTY_not_a_default(arrival, hl):
    """A fan is measured, so an endpoint with no firing variant contributes NOTHING. The failure this
    forbids is the one session 106 diagnosed: representing a fan by a stand-in point."""
    fan = CL.residual_fan([arrival], hl, flip_step=AW.FLIP_SPAN,
                          rotate_offs=AW.ROTATE_OFFS[1:2])
    assert isinstance(fan, list)
    for m in fan:
        assert set(m) == {'along', 'lat', 'n_atom'}


class _FakeHL(object):
    """A `reposition.HerdLine` whose herd axis IS (x, z) -- so a fan test can pin arithmetic without
    a rollout, and the projection cannot quietly do the work the assertion is about."""

    def along(self, x, z):
        return x

    def lateral(self, x, z):
        return z


def _fake_run(x=0.0, z=0.0):
    class _Link(object):
        pos_x, pos_z = x, z

    class _Run(object):
        link = _Link()
    return _Run()


def _fake_cloud(made):
    """`atom_cloud`'s output shape for ``made`` = [(resid_along, resid_lat, n_atom, link_end)]."""
    def _cloud(run0, hl, **kw):
        return [dict(resid_along=a, resid_lat=l, log=[0] * n, link_end=le)
                for (a, l, n, le) in made]
    return _cloud


def test_the_fan_dedups_on_its_quantum_and_orders_by_frames():
    """The table stays small by griding, and cheap atoms come first so a truncated fan degrades toward
    the fast ones the objective prefers. Pinned on a hand-built cloud, no rollout."""
    made = [(1.00, 20.0, 7, (50.0, 3.0)), (1.20, 20.0, 7, (50.0, 3.0)),
            (5.00, 30.0, 2, (60.0, 4.0))]
    real_cloud, real_fires = CL.atom_cloud, AW.fires
    try:
        CL.atom_cloud = _fake_cloud(made)
        AW.fires = lambda r: True
        fan = CL.residual_fan([{'run': _fake_run()}], _FakeHL(), quantum=1.0)
    finally:
        CL.atom_cloud, AW.fires = real_cloud, real_fires
    assert len(fan) == 2, "1.00 and 1.20 are the same 1.0 u cell and must dedup"
    assert [m['n_atom'] for m in fan] == [2, 7]


def test_every_fan_member_carries_its_own_THROW_and_the_dedup_respects_it():
    """The throw is Link's own displacement over the variant (session 114's rigid quantity), and it is
    what `predict_bound` prices the ARRIVAL from. Two variants that land Tetra identically but throw
    Link 10 u apart are DIFFERENT candidates, so the dedup key must keep both -- averaging them is the
    failure `_notes/s114_throw_map.py` names (a class spans up to 15 x 48 u)."""
    made = [(1.0, 20.0, 4, (50.0, 3.0)), (1.0, 20.0, 4, (60.0, 3.0))]
    real_cloud, real_fires = CL.atom_cloud, AW.fires
    try:
        CL.atom_cloud = _fake_cloud(made)
        AW.fires = lambda r: True
        fan = CL.residual_fan([{'run': _fake_run(x=5.0, z=1.0)}], _FakeHL(), quantum=1.0)
    finally:
        CL.atom_cloud, AW.fires = real_cloud, real_fires
    assert len(fan) == 2, "the same landing at two throws is two candidates, not one"
    # the throw is the DISPLACEMENT from Link's own start, not the end position
    assert sorted(m['throw_along'] for m in fan) == [45.0, 55.0]
    assert all(m['throw_lat'] == 2.0 for m in fan)


def test_the_predictor_and_the_enumeration_price_in_THE_SAME_currency():
    """The predictor is only worth something if its number is comparable to the exact one, so the
    formula is pinned: frames + the atom's log + the row's plan_cost + the miss at the ceiling."""
    rows = [dict(idx=7, along=900.0, lat=0.0, plan_cost=20)]
    fan = [dict(along=10.0, lat=0.0, n_atom=3)]
    got = CL.predict_bound(880.0, 0.0, 75, fan, rows)
    assert got['row_idx'] == 7 and got['n_atom'] == 3
    assert got['miss'] == 10.0                      # 880 + 10 = 890, the row is at 900
    assert got['total'] == 75 + 3 + 20
    assert got['bound'] == 98.0 + O.remaining_frames(10.0)


def test_the_predictor_lands_exactly_when_the_fan_reaches_the_row():
    """A fan member that puts Tetra ON a row must price at the exact total -- no residual term."""
    rows = [dict(idx=1, along=900.0, lat=5.0, plan_cost=21)]
    fan = [dict(along=20.0, lat=5.0, n_atom=2)]
    got = CL.predict_bound(880.0, 0.0, 74, fan, rows)
    assert got['miss'] == 0.0 and got['bound'] == got['total'] == 97.0


def test_raw_genuine_coords_are_converted_exactly_and_priced_rows_pass_through(hl):
    """The two row sources disagree about their columns and the raw one would have crashed the
    predictor: `seeds.load_placements` carries only idx/x/z. The conversion must be the SAME projection
    the priced rows were built with -- exact, not close -- and a priced row must pass through untouched."""
    raw = SD.load_placements()[0][:5]
    assert all('along' not in r and 'plan_cost' not in r for r in raw), \
        "the raw set grew columns; re-derive what this test is protecting"
    got = CL.herd_rows(raw, hl)
    for r, g in zip(raw, got):
        assert g['along'] == hl.along(r['x'], r['z'])       # exact, no tolerance
        assert g['lat'] == hl.lateral(r['x'], r['z'])
        assert g['plan_cost'] == 0.0                        # not recoverable from a raw row
    priced = [dict(idx=3, x=1.0, z=2.0, along=900.0, lat=1.0, plan_cost=21)]
    assert CL.herd_rows(priced, hl)[0] is priced[0], "a priced row must pass through, not be copied"


def test_the_predictor_prices_the_ARRIVAL_only_when_asked_and_is_otherwise_UNCHANGED():
    """The joint branch is opt-in and the landing-only number must not move under it -- otherwise every
    beam cut before session 115 becomes incomparable with one cut after. Same fan, same rows, one call
    with the stations and one without."""
    rows = [dict(idx=7, along=900.0, lat=0.0, plan_cost=20)]
    fan = [dict(along=10.0, lat=0.0, n_atom=3, throw_along=50.0, throw_lat=0.0)]
    plain = CL.predict_bound(880.0, 0.0, 75, fan, rows)
    assert plain['d_station'] is None and plain['arr_frames'] is None
    # link 700 + throw 50 = 750, the station at 900 -> a 150 u gap, credited FREE_REACH, at the cap
    joint = CL.predict_bound(880.0, 0.0, 75, fan, rows, link=(700.0, 0.0),
                             stations={7: [(900.0, 0.0)]})
    assert joint['d_station'] == 150.0
    assert joint['arr_frames'] == (150.0 - CL.FREE_REACH) / CL.WALK_CAP
    assert joint['bound'] == plain['bound'] + joint['arr_frames']
    assert joint['miss'] == plain['miss'] and joint['total'] == plain['total']
    # and an arrival inside the walk the row already pays for adds exactly nothing
    free = CL.predict_bound(880.0, 0.0, 75, fan, rows, link=(880.0, 0.0),
                            stations={7: [(900.0, 0.0)]})
    assert free['d_station'] == 30.0 and free['arr_frames'] == 0.0
    assert free['bound'] == plain['bound']


def test_the_arrival_term_moves_the_PREDICTORS_row_choice_too():
    """`_joint_row`'s finding at the screen: the row a landing is priced against changes once the
    arrival is in the sum, so the cheap predictor must make the same choice the enumeration does or the
    cut and the keep are aimed at different candidates."""
    rows = [dict(idx=0, along=890.0, lat=0.0, plan_cost=21),
            dict(idx=1, along=910.0, lat=0.0, plan_cost=21)]
    fan = [dict(along=0.0, lat=0.0, n_atom=3, throw_along=0.0, throw_lat=0.0)]
    stations = {0: [(700.0, 0.0)], 1: [(890.0, 0.0)]}
    assert CL.predict_bound(890.0, 0.0, 70, fan, rows)['row_idx'] == 0          # landing alone
    joint = CL.predict_bound(890.0, 0.0, 70, fan, rows, link=(890.0, 0.0), stations=stations)
    assert joint['row_idx'] == 1, "20 u of landing is cheaper than 190 u of walking"
    assert joint['miss'] == 20.0 and joint['d_station'] == 0.0 and joint['arr_frames'] == 0.0


def test_the_predictor_SKIPS_an_unmeasured_row_only_in_the_joint_branch():
    """A row with no hunted station is unmeasured, and unmeasured is not free (`station_map`). The
    landing-only branch has no arrival to be wrong about, so it must still score it."""
    rows = [dict(idx=0, along=900.0, lat=0.0, plan_cost=19),
            dict(idx=1, along=901.0, lat=0.0, plan_cost=21)]
    fan = [dict(along=0.0, lat=0.0, n_atom=2, throw_along=0.0, throw_lat=0.0)]
    assert CL.predict_bound(900.0, 0.0, 70, fan, rows)['row_idx'] == 0
    joint = CL.predict_bound(900.0, 0.0, 70, fan, rows, link=(900.0, 0.0),
                             stations={1: [(900.0, 0.0)]})
    assert joint['row_idx'] == 1, "the cheap row has no station and may not win by lacking evidence"
    assert CL.predict_bound(900.0, 0.0, 70, fan, rows, link=(0.0, 0.0), stations={}) is not None, \
        "an EMPTY station map is not a joint request -- it falls back to the landing branch"


def test_the_stations_project_into_herd_coordinates_with_the_SAME_projection_as_the_rows(hl):
    """`herd_stations` exists only so the screen projects once instead of per aim, and it must be the
    projection `herd_rows` uses or the two sides of a station gap are measured in different frames.
    It has no arithmetic of its own, so the gate is an identity on every point -- exact, no tolerance.

    (The distance a rotation carries is preserved only to the last ULP or two, which is why the gate is
    the projection and not the gap: `objective.PLACEMENT_BAND` is 1.0 u, so 1e-13 is not the risk here
    -- using the WRONG frame, which is a ~1000 u error, is.)"""
    pts = {3: [(-1500.0, -300.0), (-1400.0, -250.0)]}
    got = CL.herd_stations(pts, hl)
    assert got[3] == [(hl.along(-1500.0, -300.0), hl.lateral(-1500.0, -300.0)),
                      (hl.along(-1400.0, -250.0), hl.lateral(-1400.0, -250.0))]
    row = CL.herd_rows([dict(idx=3, x=-1500.0, z=-300.0)], hl)[0]
    assert (row['along'], row['lat']) == got[3][0], "rows and stations must share one frame"
    assert CL.herd_stations(None, hl) == {}


def test_the_predictor_has_nothing_to_say_on_an_empty_fan():
    assert CL.predict_bound(880.0, 0.0, 75, [], [dict(idx=0, along=900.0, lat=0.0)]) is None


def test_the_keep_is_wired_OFF_by_default_and_costs_nothing_when_off():
    """`full_herd.extend_cycle`'s new keep must be inert unless asked for: default False, and the
    enumeration imported INSIDE the guarded branch so a default beam never pays for the module."""
    import inspect
    sig = inspect.signature(FH.extend_cycle)
    for k in ('cloud_keep', 'cloud_flip', 'cloud_rots', 'cloud_cap'):
        assert k in sig.parameters
    assert sig.parameters['cloud_keep'].default is False
    assert sig.parameters['cloud_cap'].default is None, "an unasked-for cap is a silent truncation"
    src = inspect.getsource(FH.extend_cycle)
    assert 'if cloud_keep and out:' in src, "the keep is not wired at all"
    assert src.index('if cloud_keep and out:') < src.index('_CL()'), \
        "the enumeration is reached before the cloud_keep guard"
    # `cloud_land` must be reachable ONLY through the deferred accessor -- never a module-scope import,
    # so a default beam never pays for it (and the away_walk <-> full_herd cycle stays unbroken)
    import ast
    tree = ast.parse(inspect.getsource(FH))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top for a in n.names} | {n.module for n in top
                                                     if isinstance(n, ast.ImportFrom) and n.module}
    assert not any('cloud_land' in (nm or '') for nm in names)
    assert 'from harness.tetrapush import cloud_land' in inspect.getsource(FH._CL)


def test_the_predictor_is_wired_into_the_per_aim_sweep_and_is_inert_without_a_fan():
    """The axis with authority over WHICH endpoints exist is `roll_probe`'s per-aim sweep, so the cheap
    predictor is wired there -- guarded, defaulting off, and reached only when a caller supplies BOTH a
    measured fan and the rows (a fan without rows, or rows without a fan, must not half-fire)."""
    import inspect
    sig = inspect.signature(FH.roll_probe)
    assert sig.parameters['fan'].default is None and sig.parameters['rows'].default is None
    src = inspect.getsource(FH.roll_probe)
    assert 'if fan and rows:' in src, "the predictor is not guarded on having both inputs"
    # the rows are converted to herd coords ONCE, not per aim (the sweep fires thousands)
    assert src.count('_CL().herd_rows') == 1 and 'if (fan and rows) else None' in src


def test_the_ARRIVAL_half_reaches_the_per_aim_screen_and_stays_opt_in():
    """Session 115: the keep priced the arrival at the SURVIVORS while the screen that decides which
    endpoints exist priced only the landing, and the two halves are anti-correlated across the beam. So
    the stations have to reach `roll_probe` -- projected once, not per aim -- and `extend_cycle` must
    hand its own map through. Opt-in: without stations the screen is byte-for-byte the old one."""
    import inspect
    sig = inspect.signature(FH.roll_probe)
    assert 'stations' in sig.parameters and sig.parameters['stations'].default is None
    src = inspect.getsource(FH.roll_probe)
    assert src.count('_CL().herd_stations') == 1, "the stations are projected per aim"
    assert 'if (fan and rows and stations) else None' in src
    assert 'stations=hstat' in src and 'link=' in src, "the arrival is not handed to the predictor"
    ext = inspect.getsource(FH.extend_cycle)
    assert 'stations=cloud_stations' in ext, "extend_cycle keeps its station map from the screen"


def test_the_separation_is_REPORTED_by_the_screen_and_is_exactly_minus_lead():
    """The separation rides along free (the metrics already carry ``lead``) and is reported, never
    ranked on -- session 115 measured that buying depth at the endpoint kills the atom outright, so an
    endpoint keep that maximised it would select for states that cannot fire."""
    import inspect
    src = inspect.getsource(FH.roll_probe)
    assert "sep = -m['lead']" in src, "the separation is not the metrics' own lead"
    assert "sep=sep" in src and "sep_max" in src and "cloud_sep" in src
    # and it is not a rank or a keep anywhere in the stage
    ext = inspect.getsource(FH.extend_cycle)
    assert "sep_keep" not in ext and "t[0]['sep_max']" not in ext


def test_the_in_band_field_is_the_only_solved_claim():
    """``in_band`` answers "is the plan solved here" and the RANK does not, so they are separate
    fields: `objective.PLACEMENT_BAND` is 1.0 u and a 5.93 u best-bound landing is not a solve."""
    assert O.PLACEMENT_BAND == 1.0
    assert 5.93 > O.PLACEMENT_BAND


# ------------------------------------------------------- the JOINT keep: the arrival half (s110)

def _stations():
    """Two rows, and the stations each was hunted at -- the map `station_map` builds from the dumps."""
    return {0: [(0.0, 0.0)], 1: [(200.0, 0.0)]}


def test_the_arrival_term_is_free_inside_the_walk_the_row_ALREADY_pays_for():
    """A row's `plan_cost` buys `WALK_FRAMES` at the cap, so a station inside that reach costs the plan
    nothing extra and only the SHORTFALL is charged. Pinned as arithmetic: the credit is the reach, the
    rate is the cap, and one cap-length past it is exactly one frame."""
    assert CL.FREE_REACH == CL.WALK_CAP * CL.WALK_FRAMES == 34.0
    assert CL.arrival_frames(0.0) == 0.0 and CL.arrival_frames(CL.FREE_REACH) == 0.0
    assert CL.arrival_frames(CL.FREE_REACH + CL.WALK_CAP) == 1.0
    assert CL.arrival_frames(128.2) == (128.2 - 34.0) / 17.0     # the s107 winner's own gap


def test_an_UNMEASURED_arrival_is_infinite_and_never_free():
    """The `cloud_cap` lesson, one level down: a candidate nothing measured must sort LAST, because a
    zero here would let an unhunted row win the joint rank by having no evidence against it."""
    assert CL.arrival_frames(None) == float('inf')
    assert CL.station_gap((0.0, 0.0), None) is None and CL.station_gap((0.0, 0.0), []) is None
    assert CL.station_gap((3.0, 4.0), [(0.0, 0.0), (100.0, 0.0)]) == 5.0


def test_the_ROW_CHOICE_moves_under_the_arrival_term():
    """The reason this is a separate function and not a flag on `_nearest_row`: the joint rank changes
    WHICH row a landing is priced against. Here the near row's stations sit 200 u behind Link and the
    far one's are under his feet, and 20 u of landing (~1.5 frames) is cheaper than 166 u of walking
    (~9.8) -- so the far row wins, and the landing-only rank picks the other one."""
    rows = [dict(idx=0, x=6.0, z=0.0, plan_cost=21), dict(idx=1, x=20.0, z=0.0, plan_cost=21)]
    link = (200.0, 0.0)
    assert CL._nearest_row(0.0, 0.0, rows)[1]['idx'] == 0            # landing alone
    miss, row, d_st, af, n = CL._joint_row(0.0, 0.0, link, rows, _stations())
    assert row['idx'] == 1 and miss == 20.0 and d_st == 0.0 and af == 0.0 and n == 2
    assert 21 + O.remaining_frames(20.0) < 21 + O.remaining_frames(6.0) + CL.arrival_frames(200.0)


def test_a_row_with_no_hunted_station_is_SKIPPED_not_scored_free():
    """A row absent from the map is unmeasured, and an unmeasured row must not win by default -- it is
    dropped from the joint rank, and ``n_rows`` says how many were actually eligible."""
    rows = [dict(idx=0, x=0.0, z=0.0, plan_cost=21), dict(idx=1, x=20.0, z=0.0, plan_cost=21)]
    miss, row, _d, _af, n = CL._joint_row(0.0, 0.0, (0.0, 0.0), rows, {1: [(0.0, 0.0)]})
    assert row['idx'] == 1 and miss == 20.0 and n == 1
    assert CL._joint_row(0.0, 0.0, (0.0, 0.0), rows, {})[1] is None


def test_station_map_REFUSES_a_dump_hunted_at_another_walk_budget(tmp_path):
    """`FREE_REACH` -- what the arrival term credits for nothing -- is derived from the walk the hunts
    themselves spent, so a dump at a different budget silently invalidates it. It raises instead."""
    import json
    import os
    d = tmp_path / 's104'
    d.mkdir()
    row = dict(idx=0, x=1.0, z=2.0)
    hit = dict(tetra=[1.0, 2.0], live_at=[[10.0, 20.0]])
    (d / 'h.json').write_text(json.dumps(dict(cells=[dict(cell=1, frames=CL.WALK_FRAMES,
                                                          hits=[hit])])))
    got = CL.station_map([row], hunts=('s104/h.json',), gen=str(tmp_path))
    assert got == {0: [(10.0, 20.0)]}
    (d / 'h.json').write_text(json.dumps(dict(cells=[dict(cell=1, frames=CL.WALK_FRAMES + 1,
                                                          hits=[hit])])))
    with pytest.raises(ValueError):
        CL.station_map([row], hunts=('s104/h.json',), gen=str(tmp_path))
    assert CL.station_map([row], hunts=('s104/missing.json',), gen=str(tmp_path)) == {}


def test_the_tail_axis_widens_the_grid_and_is_priced_from_ONE_rollout(arrival, hl):
    """``exit_runs`` crosses the knob grid with `away_walk.escape_atom`'s tail, and each member must be
    the rollout it claims to be -- so every record is re-derived here against a fresh atom at its own
    ``exit_run``, bit-exactly. A tail the follow bar cut short is absent, so the grid is bounded ABOVE
    by the cross product rather than equal to it."""
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2])
    base = CL.atom_cloud(arrival['run'], hl, **kw)
    grid = CL.atom_cloud(arrival['run'], hl, exit_runs=(0, 1, 2), **kw)
    assert {r['knobs']['exit_run'] for r in base} == {0}
    assert len(base) <= len(grid) <= 3 * len(base)
    assert {r['knobs']['exit_run'] for r in grid} <= {0, 1, 2}
    for r in grid[:6] + grid[-6:]:
        k = r['knobs']
        fresh = AW.escape_atom(arrival['run'], hl, turnaround_first=k['turnaround_first'],
                               rotate_side=k['rotate_side'], rotate_off=k['rotate_off'],
                               flip_bearing=k['flip_bearing'], exit_bearing=k['exit_bearing'],
                               csangle=int(arrival['run'].csangle), exit_run=k['exit_run'])
        assert r['link_end'] == fresh['link_end'] and r['tetra_end'] == fresh['tetra_end']
        assert len(r['log']) == len(fresh['log'])


def test_JOINT_is_a_stricter_claim_than_IN_BAND_and_is_reported_separately():
    """``in_band`` is the landing half and sessions 107-109 mistook it for a solve. ``joint`` is the
    conjunction -- inside the band AND owing no arrival frames -- so it is a SUBSET, and a candidate
    that owes nothing has a bound equal to its own total."""
    rows = [dict(idx=0, x=0.0, z=0.0, plan_cost=21)]
    stations = {0: [(0.0, 0.0)]}
    near = CL._joint_row(0.0, 0.0, (10.0, 0.0), rows, stations)
    far = CL._joint_row(0.0, 0.0, (300.0, 0.0), rows, stations)
    assert near[0] <= O.PLACEMENT_BAND and near[3] == 0.0        # in band, owes nothing -> joint
    assert far[0] <= O.PLACEMENT_BAND and far[3] > 0.0           # in band, owes 15.6 f -> NOT joint
    assert 73 + 6 + 21 + O.remaining_frames(near[0]) + near[3] == 100.0


def test_the_joint_keep_is_wired_and_defaults_to_the_landing_half_alone():
    """Additive or it changes every banked number: without a station map the keep is exactly the
    session-107 one, and `extend_cycle` reaches the new axes only through explicit arguments."""
    import inspect
    sig = inspect.signature(FH.extend_cycle)
    for k in ('cloud_stations', 'cloud_exit_runs'):
        assert k in sig.parameters and sig.parameters[k].default is None
    for k, want in (('stations', None), ('exit_runs', (0,))):
        assert inspect.signature(CL.cloud_landing).parameters[k].default == want
    src = inspect.getsource(CL.cloud_landing)
    assert 'if stations:' in src and '_joint_row' in src, "the joint branch is not guarded"


# --------------------------------------------------------------- the exit bearing (session 118)

def test_the_exit_arc_strictly_contains_the_standing_pair_the_grid_defaults_to(arrival, hl):
    """The arc's own positive control has to be a MEMBER of the arc, not a remembered number.

    `atom_cloud` defaults to the standing PAIR (the live entry bearing and the herd up-bearing) and
    `exit_arc` sweeps about both centres, so the pair is inside the arc by construction -- which is
    what lets one call price the swept axis and its control together and attribute the difference to
    the sweep (`[[search-space-contains-human]]`)."""
    from tww_sim.land.plan_land._primitives import world_angle_s16
    run = arrival['run']
    ex, ez = SD.ENTRY_ROLL_POS
    pair = {world_angle_s16(ex - run.link.pos_x, ez - run.link.pos_z),
            (hl.bearing_bam() + 0x8000) & 0xFFFF}
    assert set(CL.exit_arc(run, hl, step=0)) == pair, "a zero step must be the pair verbatim"
    arc = set(CL.exit_arc(run, hl, step=0x800, half=0x2000))
    assert pair <= arc and len(arc) > len(pair)
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2])
    assert {r['knobs']['exit_bearing'] for r in CL.atom_cloud(run, hl, **kw)} <= pair


def test_the_exit_arc_reaches_arrivals_the_standing_pair_cannot(arrival, hl):
    """**The axis the enumeration owns and had never turned** (session 118).

    The exit stick is held past the handoff, so the bearing it holds decides WHERE the arrival lands;
    the standing pair is two directions and not a steering axis. Measured on the swept session-111
    cycle-3 beam, that is the whole arrival bill: the pair's best in-band station gap is 160-176 u and
    the arc's is 9.9-12.0 u at the same states, taking the delivered figure from 106.45 to 103.45 and
    producing the beam's first ``joint`` records.

    Gated as the INEQUALITY rather than the measurement (which moves): over the same thinned grid and
    the same tails, the arc must strictly out-reach its own pair, and every arc member must be a real
    rollout at its own bearing. The claim is about where the enumeration can PUT Link, so it is read
    over the whole grid -- the synthetic fixture arrival fires nothing (`away_walk.fires` is a
    property of a real terminal's depth), and the frame figures above come from the real beam."""
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2], exit_runs=(0, 2, 4))
    run = arrival['run']
    arc = CL.exit_arc(run, hl, step=0x1000, half=0x2000)
    pair = CL.exit_arc(run, hl, step=0)
    # far enough that the FRAME term is live for both lanes -- inside `FREE_REACH` every gap prices
    # at 0.0 and the comparison would be about nothing
    station = [(run.link.pos_x - 280.0, run.link.pos_z + 80.0)]

    def reach(bearings):
        v = CL.atom_cloud(run, hl, exit_bearings=bearings, **kw)
        return min((CL.station_gap(r['link_end'], station) for r in v), default=None), v

    g_pair, v_pair = reach(pair)
    g_arc, v_arc = reach(arc)
    assert g_pair is not None and g_arc is not None, "the fixture arrival must enumerate on both"
    assert g_pair > CL.FREE_REACH, "the station must be out of free reach or nothing is compared"
    assert g_arc < g_pair, "the arc must reach an arrival the pair cannot"
    assert CL.arrival_frames(g_arc) < CL.arrival_frames(g_pair)
    assert {r['knobs']['exit_bearing'] for r in v_pair} <= {r['knobs']['exit_bearing'] for r in v_arc}
    r = min(v_arc, key=lambda r: CL.station_gap(r['link_end'], station))
    k = r['knobs']
    fresh = AW.escape_atom(run, hl, turnaround_first=k['turnaround_first'],
                           rotate_side=k['rotate_side'], rotate_off=k['rotate_off'],
                           flip_bearing=k['flip_bearing'], exit_bearing=k['exit_bearing'],
                           csangle=int(run.csangle), exit_run=k['exit_run'])
    assert r['link_end'] == fresh['link_end'] and r['tetra_end'] == fresh['tetra_end']


def test_a_longer_tail_can_move_the_arrival_FURTHER_from_the_station(arrival, hl):
    """**The tail is not monotone in the station gap, so `EXIT_RUNS`' longest member is not its best**
    (session 118).

    A tail runs at the walk cap along the exit-hold bearing, and Link's heading chases it rather than
    snapping to it, so the path is a CURVE. Traced at the session-117 beam's cheapest settled in-band
    state out to the 230 u follow bar, ``d_station`` is minimised at tail **0** (146.4 u) and rises to
    227.2 u by tail 20 -- the exit hold was running 58 deg off the bearing to its own station.

    So a keep may not read "the gap is payable at the cap" as "more tail is closer". Gated as
    non-monotonicity over the enumerated grid: some tail on some knob combo is FURTHER from a station
    than a shorter one (the fixture arrival fires nothing, so this reads the rollouts, not the
    acceptance -- see the arc gate above)."""
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2], exit_runs=(0, 1, 2, 3, 4))
    station = [(arrival['run'].link.pos_x - 140.0, arrival['run'].link.pos_z + 40.0)]
    by_knob = {}
    for r in CL.atom_cloud(arrival['run'], hl, **kw):
        k = tuple(sorted((a, b) for a, b in r['knobs'].items() if a != 'exit_run'))
        by_knob.setdefault(k, {})[r['knobs']['exit_run']] = CL.station_gap(r['link_end'], station)
    curves = [v for v in by_knob.values() if len(v) >= 3]
    assert curves, "the fixture must produce at least one multi-tail family"
    worse = [v for v in curves if max(v.values()) > v[min(v)] + 1e-9]
    assert worse, "no tail anywhere moved an arrival further from the station -- re-read the trace"
    assert any(min(v, key=lambda t: v[t]) != max(v) for v in curves), \
        "the cheapest tail is always the longest one, so the gap would be monotone after all"


# ------------------------------------------------- the arc reaches the CUT (session 119)

def test_the_keep_can_ASK_for_the_arc_and_still_defaults_to_the_standing_pair(arrival, hl):
    """The plumbing session 118 said was missing: `cloud_landing` -- and so `cloud_probe` and
    `full_herd.extend_cycle` above it -- could not pass an exit bearing at all, which is why the arc
    built in session 110 had never entered an enumeration that decides anything.

    Two identities, no tolerance: with ``exit_step`` the keep enumerates EXACTLY the grid an explicit
    `atom_cloud` at the same arc does, and without it EXACTLY the standing-pair grid it always did
    (so every banked number survives the change)."""
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2], exit_runs=(0, 2))
    run, rows = arrival['run'], _rows()
    pair = CL.cloud_landing(run, 70, hl, rows, **kw)
    assert pair['n_variants'] == len(CL.atom_cloud(run, hl, **kw))
    arc = CL.cloud_landing(run, 70, hl, rows, exit_step=0x1000, exit_half=0x2000, **kw)
    assert arc['n_variants'] == len(CL.atom_cloud(
        run, hl, exit_bearings=CL.exit_arc(run, hl, step=0x1000, half=0x2000), **kw))
    assert arc['n_variants'] > pair['n_variants'], "the arc must widen the grid it is handed to"
    # ...and an explicit zero step is the pair verbatim, so the control is expressible as a member
    assert CL.cloud_landing(run, 70, hl, rows, exit_step=0, **kw)['n_variants'] == pair['n_variants']


def test_the_arc_is_resolved_PER_ENDPOINT_so_a_bearing_LIST_could_not_be_plumbed(hl):
    """Why the plumbed knob is a ``(step, half)`` SPEC and not the bearing list `atom_cloud` takes.

    `exit_arc`'s centres are the live entry bearing -- measured from Link's OWN position -- and the
    herd up-bearing, so one list hoisted to a beam sweeps a different axis at every endpoint and does
    not contain either one's own control. Pinned on two positions far enough apart to name different
    directions: the sets differ, and each still contains its own pair."""
    near, far = _fake_run(x=0.0, z=0.0), _fake_run(x=600.0, z=600.0)
    a_near = set(CL._arc(near, hl, 0x1000, 0x2000))
    a_far = set(CL._arc(far, hl, 0x1000, 0x2000))
    assert a_near != a_far, "the arc does not depend on the endpoint -- re-read `exit_arc`"
    assert set(CL.exit_arc(near, hl, step=0)) <= a_near
    assert set(CL.exit_arc(far, hl, step=0)) <= a_far
    assert CL._arc(near, hl, None, None) is None, "no step asked for is the pair, not an empty sweep"


def test_the_fan_carries_the_arc_so_the_SCREEN_sees_the_axis_the_keep_does(arrival, hl):
    """The screen's half of the same fix. `full_herd.roll_probe` never enumerates -- it prices
    `predict_bound` over a measured fan -- so the arc reaches the cut that decides which endpoints
    EXIST only if the fan was measured along it. A fan built at the standing pair prices every
    arrival as though the plan could leave along one of two directions.

    The fixture arrival fires nothing (`away_walk.fires` is a property of a real terminal's depth), so
    the acceptance is stubbed and the claim is read off the enumerated rollouts -- the same shape the
    session-118 gates use."""
    kw = dict(flip_step=AW.FLIP_SPAN, rotate_offs=AW.ROTATE_OFFS[1:2], exit_runs=(0, 2))
    real_fires = AW.fires
    try:
        AW.fires = lambda r: True
        pair = CL.residual_fan([arrival], hl, **kw)
        arc = CL.residual_fan([arrival], hl, exit_step=0x1000, exit_half=0x2000, **kw)
    finally:
        AW.fires = real_fires
    assert pair and arc, "both lanes must measure something or nothing is compared"
    assert all('throw_along' in m and 'throw_lat' in m for m in arc)
    throws = {(round(m['throw_along'], 6), round(m['throw_lat'], 6)) for m in arc}
    assert throws > {(round(m['throw_along'], 6), round(m['throw_lat'], 6)) for m in pair}, \
        "the arc adds no throw the pair did not already have, so the screen would see the same axis"


def test_a_fan_with_NO_THROW_is_refused_by_the_arrival_branch_and_scored_by_the_landing_one():
    """**The silent zero the joint screen actually ran on** (session 119).

    `predict_bound` read ``m.get('throw_along', 0.0)``, and the fan every joint cut since session 115
    was handed (``s107_fan.json``, measured in session 107 before the throw existed) carries the column
    on 0 of its 178 members -- so the screen placed Link's arrival at the roll TERMINAL. That is not a
    conservative default: session 118 measured the terminal gap at 67.6-106.7 u against the same
    candidates' post-atom 159.5-176.3, so the atom roughly doubles what was being priced.

    Unmeasured is not free is the module's oldest rule (`station_map`, `arrival_frames`); this puts the
    fan under it. The landing-only branch has no arrival to be wrong about and must still score."""
    rows = [dict(idx=7, along=900.0, lat=0.0, plan_cost=20)]
    throwless = [dict(along=10.0, lat=0.0, n_atom=3)]
    assert CL.predict_bound(880.0, 0.0, 75, throwless, rows)['miss'] == 10.0
    with pytest.raises(ValueError):
        CL.predict_bound(880.0, 0.0, 75, throwless, rows, link=(700.0, 0.0),
                         stations={7: [(900.0, 0.0)]})
    # one member missing it is enough -- a partly-measured fan is not a measured one
    half = [dict(along=10.0, lat=0.0, n_atom=3, throw_along=50.0, throw_lat=0.0),
            dict(along=10.0, lat=0.0, n_atom=4)]
    with pytest.raises(ValueError):
        CL.predict_bound(880.0, 0.0, 75, half, rows, link=(700.0, 0.0),
                         stations={7: [(900.0, 0.0)]})
    assert CL.predict_bound(880.0, 0.0, 75, half[:1], rows, link=(700.0, 0.0),
                            stations={7: [(900.0, 0.0)]})['d_station'] == 150.0


def test_the_predictor_PRUNES_by_its_own_arithmetic_without_changing_its_answer():
    """The prune that makes a real fan affordable (session 119), and the two ways it could be wrong.

    A member costs ``n_atom`` frames whatever it lands and both remaining terms are >= 0, so its best
    conceivable bound is ``frames + n_atom + min(plan_cost)``; once an incumbent beats that, its row
    loop is skipped. Necessary because the fan is no longer session 107's 178 members -- with the
    throw, the tail and the arc it is 75627, and the unpruned pass costs ~10 s per aim.

    Gated as an IDENTITY, not a speedup. It must (a) skip a member that cannot win even landing
    perfectly, and (b) still find a winner that is expensive in frames when nothing cheap comes close
    -- an over-eager prune passes the first and fails the second."""
    rows = [dict(idx=0, along=900.0, lat=0.0, plan_cost=20)]
    st = {0: [(900.0, 0.0)]}
    # (a) the cheap member misses by 1 u; the dear one lands EXACTLY, and still may not win
    fan = [dict(along=19.0, lat=0.0, n_atom=3, throw_along=100.0, throw_lat=0.0),
           dict(along=20.0, lat=0.0, n_atom=9, throw_along=100.0, throw_lat=0.0)]
    got = CL.predict_bound(880.0, 0.0, 70, fan, rows, link=(800.0, 0.0), stations=st)
    assert got['n_atom'] == 3 and got['miss'] == 1.0
    assert got['bound'] == 70 + 3 + 20 + O.remaining_frames(1.0)
    # (b) same pair, but now the cheap member is hopeless -- the dear one must still be found
    fan[0] = dict(along=-200.0, lat=0.0, n_atom=3, throw_along=100.0, throw_lat=0.0)
    got = CL.predict_bound(880.0, 0.0, 70, fan, rows, link=(800.0, 0.0), stations=st)
    assert got['n_atom'] == 9 and got['miss'] == 0.0 and got['bound'] == 99.0
    # and the answer cannot depend on the order the fan is scanned in, which an exact prune guarantees
    assert CL.predict_bound(880.0, 0.0, 70, fan[::-1], rows, link=(800.0, 0.0),
                            stations=st)['bound'] == got['bound']


def test_the_prune_takes_its_FLOOR_from_the_rows_it_may_actually_quote():
    """The floor is ``min(plan_cost)`` over the rows in play, and in the joint branch an UNMEASURED row
    is skipped -- so it may not lower the floor either.

    A floor that is too LOW only prunes less, so it cannot be wrong about an answer; the failure that
    would bite is a floor that quotes a row the branch never scores. Gated as the identity that means
    exactly that: with a cheap unstationed row present, the joint answer must equal the answer with
    that row deleted outright -- the ineligible row may change neither the winner nor the pruning."""
    dear = dict(idx=1, along=900.0, lat=0.0, plan_cost=25)
    rows = [dict(idx=0, along=880.0, lat=0.0, plan_cost=10), dear]     # idx 0 cheap and UNMEASURED
    fan = [dict(along=-200.0, lat=0.0, n_atom=2, throw_along=0.0, throw_lat=0.0),
           dict(along=20.0, lat=0.0, n_atom=8, throw_along=0.0, throw_lat=0.0)]
    st = {1: [(880.0, 0.0)]}
    got = CL.predict_bound(880.0, 0.0, 70, fan, rows, link=(880.0, 0.0), stations=st)
    alone = CL.predict_bound(880.0, 0.0, 70, fan, [dear], link=(880.0, 0.0), stations=st)
    assert got == alone, "an ineligible row moved the joint answer"
    assert got['row_idx'] == 1 and got['n_atom'] == 8 and got['miss'] == 0.0
    assert got['bound'] == 70 + 8 + 25 and got['arr_frames'] == 0.0   # the dear member still wins
    # the landing-only branch may quote the cheap row, so it is scored there and only there
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows)['row_idx'] == 0
    # ...and no eligible row at all is None, never a bound off an empty minimum
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows, link=(0.0, 0.0), stations={9: [(0.0, 0.0)]}) \
        is None


def test_extend_cycle_hands_the_arc_to_the_keep_and_is_unchanged_without_it():
    """Additive at the top of the chain too: the axes exist, default to the standing pair, and the
    keep passes them on. Without them a cut is byte-for-byte the session-118 one."""
    import inspect
    sig = inspect.signature(FH.extend_cycle)
    for k in ('cloud_exit_step', 'cloud_exit_half'):
        assert k in sig.parameters and sig.parameters[k].default is None
    src = inspect.getsource(FH.extend_cycle)
    assert 'exit_step=cloud_exit_step' in src and 'exit_half=cloud_exit_half' in src
    for fn in (CL.cloud_landing, CL.residual_fan):
        p = inspect.signature(fn).parameters
        assert p['exit_step'].default is None and p['exit_half'].default is None
    # the SCREEN's arc arrives through the fan, never through a bearing argument of its own
    assert 'exit_step' not in inspect.signature(FH.roll_probe).parameters


# ------------------------------------------- the REDUCTION: what the screen's minimum is taken over

def test_the_cheapest_atom_owns_the_global_minimum_and_hides_a_LATE_paying_knob():
    """**The session-119 wall, as an executable gate rather than a remembered measurement.**

    `predict_bound` charges ``n_atom`` 1:1 in frames and the miss it buys at `objective.PUSH_CEILING`,
    so a short atom landing far out beats a long one landing on the row. Measured over the cycle-3
    beam, the minimum sat on an ``n_atom`` = 3 member at **64 of 64** endpoints, out of 3 such members
    in a fan of 75627 -- so ~3 members decided every answer, and a knob whose frames land at the END of
    the atom (the exit arc, which differentiates members only from length 6 up) moved the bound +0.000
    at all 64.

    Both halves are gated here on one fan: improving the LONG members alone must leave the global
    minimum bit-identical, while ``atom_min`` -- the same minimum taken over the lengths that can carry
    the knob -- must move by exactly what was improved. A screen that cannot express the second cannot
    see any late-paying axis, whatever table it is handed."""
    rows = [dict(idx=0, along=900.0, lat=0.0, plan_cost=20)]
    short = dict(along=0.0, lat=0.0, n_atom=3)                 # lands 20 u out, 3 frames
    long_ = dict(along=19.0, lat=0.0, n_atom=9)                # lands 1 u out, 9 frames
    base = CL.predict_bound(880.0, 0.0, 70, [short, long_], rows)
    assert base['n_atom'] == 3 and base['bound'] == 70 + 3 + 20 + O.remaining_frames(20.0)
    better = dict(along=20.0, lat=0.0, n_atom=9)               # the late knob: the long member LANDS
    after = CL.predict_bound(880.0, 0.0, 70, [short, long_, better], rows)
    assert after['bound'] == base['bound'], "a late-paying knob must be invisible to the global min"
    assert after['n_atom'] == 3 and after['resid'] == base['resid']
    lb = CL.predict_bound(880.0, 0.0, 70, [short, long_], rows, atom_min=6)
    la = CL.predict_bound(880.0, 0.0, 70, [short, long_, better], rows, atom_min=6)
    assert lb['bound'] == 70 + 9 + 20 + O.remaining_frames(1.0)
    assert la['bound'] == 99.0 and la['miss'] == 0.0           # exactly the frames it now pays
    assert la['bound'] < lb['bound'], "the long-atom reduction did not see the knob either"


def test_by_atom_is_the_SAME_minimum_taken_per_LENGTH_and_still_exact():
    """``by_atom`` reports the whole vector instead of one record, which is what makes the argmin's
    position on the charged axis legible -- the diagnostic session 119 needed and did not have.

    Three identities, because a per-length reduction can go wrong in three ways: the vector's own
    minimum must BE the global answer (nothing invented, nothing lost), each entry must equal what the
    same call returns on a fan filtered to that length alone (the per-length prune may not leak an
    incumbent across classes), and it must be order-independent, which an exact prune guarantees."""
    rows = [dict(idx=0, along=900.0, lat=0.0, plan_cost=20),
            dict(idx=1, along=930.0, lat=6.0, plan_cost=19)]
    fan = [dict(along=a, lat=l, n_atom=k)
           for k, a, l in ((3, 0.0, 0.0), (3, 12.0, 3.0), (5, 19.0, 0.0), (5, 22.0, -1.0),
                           (9, 20.0, 0.0), (9, 51.0, 6.0), (12, 20.5, 0.5))]
    per = CL.predict_bound(880.0, 0.0, 70, fan, rows, by_atom=True)
    glob = CL.predict_bound(880.0, 0.0, 70, fan, rows)
    assert sorted(per) == [3, 5, 9, 12]
    assert min(per.values(), key=lambda v: v['bound']) == glob
    for k in per:
        alone = CL.predict_bound(880.0, 0.0, 70, [m for m in fan if m['n_atom'] == k], rows)
        assert per[k] == alone, "the per-length record is not the length's own minimum"
    assert CL.predict_bound(880.0, 0.0, 70, fan[::-1], rows, by_atom=True) == per
    # an empty fan has nothing to say in either shape; no eligible ROW is None in both
    assert CL.predict_bound(880.0, 0.0, 70, [], rows, by_atom=True) == {}
    thrown = [dict(m, throw_along=40.0, throw_lat=0.0) for m in fan]
    assert CL.predict_bound(880.0, 0.0, 70, thrown, rows, by_atom=True, link=(0.0, 0.0),
                            stations={9: [(0.0, 0.0)]}) is None


def test_atom_min_admits_exactly_the_lengths_it_says_and_refuses_to_default():
    """``atom_min`` is the screen's cheap form of the same reduction, so it must be the vector's
    minimum over the lengths it admits and nothing else -- including the case where it admits none,
    which is None (no candidate at that length) and never the global answer quietly returned."""
    rows = [dict(idx=0, along=900.0, lat=0.0, plan_cost=20)]
    fan = [dict(along=0.0, lat=0.0, n_atom=3), dict(along=19.0, lat=0.0, n_atom=5),
           dict(along=20.0, lat=0.0, n_atom=9)]
    per = CL.predict_bound(880.0, 0.0, 70, fan, rows, by_atom=True)
    for k in (3, 4, 5, 6, 9):
        got = CL.predict_bound(880.0, 0.0, 70, fan, rows, atom_min=k)
        want = min((v for kk, v in per.items() if kk >= k), key=lambda v: v['bound'])
        assert got == want, "atom_min %d is not the minimum over the lengths it admits" % k
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows, atom_min=10) is None
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows, atom_min=3) == \
        CL.predict_bound(880.0, 0.0, 70, fan, rows)


# ----------------------------------------------- the DELIVERED figure, and the share that ranks it

def test_the_delivered_figure_reads_BOTH_records_and_refuses_an_UNSETTLED_one():
    """`delivered` is the field the objective is denominated in, and it is one function because both
    of its clauses are errors that were already paid for (session 118).

    ``in_band`` and ``joint`` are DIFFERENT variants, so reading either alone under-reports -- a node's
    cheapest in-band record can be unsettled while its joint record is settled. And an unsettled
    arrival owes no finite number of frames at all: it fans an empty walk cloud at `away_walk.WALK_CAP`
    and reaches no station at any distance, so it may not be quoted."""
    inb = dict(total=102.0, arr_frames=7.25, settled=False, miss=0.26)
    jnt = dict(total=105.0, arr_frames=0.0, settled=True, miss=0.47)
    assert CL.delivered(dict(in_band=inb, joint=jnt)) == 105.0     # NOT 109.25 off the unsettled one
    assert CL.delivered(dict(in_band=dict(inb, settled=True), joint=jnt)) == 105.0
    assert CL.delivered(dict(in_band=dict(inb, settled=True, arr_frames=1.5), joint=jnt)) == 103.5
    assert CL.delivered(dict(in_band=inb, joint=None)) is None
    assert CL.delivered(dict(in_band=None, joint=None)) is None
    assert CL.delivered(None) is None and CL.delivered({}) is None


def test_the_delivered_SHARE_is_wired_into_the_beam_and_is_OFF_by_default():
    """The keep half of session 120: every other cloud share reads ``cloud['best']``, which is the
    minimum-``bound`` variant and therefore short-atom at 64 of 64 endpoints. A share on the delivered
    field has no such floor, because ``in_band``/``joint`` are min-TOTAL among variants satisfying a
    predicate rather than minima over an unconstrained fan.

    Off by default, for the module's standing reason: a cut run without it is byte-for-byte the
    session-119 one. A node with no settled record is UNMEASURED, so it sorts last and keeps its place
    in the other orders rather than being refused."""
    import inspect
    sig = inspect.signature(FH.extend_cycle)
    assert 'delivered_keep' in sig.parameters and sig.parameters['delivered_keep'].default is False
    src = inspect.getsource(FH.extend_cycle)
    assert 'if delivered_keep:' in src and '_CL().delivered' in src

    def key(c):
        return (CL.delivered(c) is None, CL.delivered(c) or 0.0)

    def settled(t, name):
        return dict(name=name, in_band=None,
                    joint=dict(total=t, arr_frames=0.0, settled=True, miss=0.4))

    clouds = [dict(name='none', in_band=None, joint=None), settled(104.0, 'dear'),
              settled(101.0, 'cheap')]
    assert [c['name'] for c in sorted(clouds, key=key)] == ['cheap', 'dear', 'none']


def test_the_banded_reduction_is_the_predicate_the_KEEP_applies_not_a_trade_against_it():
    """**The rank half of session 120.** ``bound`` trades the miss against frames at
    `objective.PUSH_CEILING`, so a 3-frame atom landing 20 u out out-ranks a 10-frame one on the row;
    `cloud_landing`'s ``in_band``/``joint`` do not trade at all -- they are min-TOTAL among variants
    that SATISFY a predicate. Predicting that quantity means minimising subject to the predicate.

    Gated on the case that separates them: a cheap member out of band and a dear one inside it. The
    unbanded call must keep quoting the cheap member (that is its currency, and it is not wrong about
    it); the banded call must quote the dear one; and with nothing in band at all the answer is None
    -- an endpoint that cannot be predicted to deliver -- never the unbanded minimum returned quietly.
    ``owes_nothing`` adds the arrival clause and is a REFUSAL without the stations to price it."""
    rows = [dict(idx=0, along=900.0, lat=0.0, plan_cost=20)]
    st = {0: [(900.0, 0.0)]}
    fan = [dict(along=0.0, lat=0.0, n_atom=3, throw_along=100.0, throw_lat=0.0),
           dict(along=19.6, lat=0.0, n_atom=9, throw_along=100.0, throw_lat=0.0)]
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows)['n_atom'] == 3
    got = CL.predict_bound(880.0, 0.0, 70, fan, rows, band=O.PLACEMENT_BAND)
    assert got['n_atom'] == 9 and got['miss'] == pytest.approx(0.4, abs=1e-12)
    assert got['bound'] == 70 + 9 + 20 + O.remaining_frames(got['miss'])
    # nothing inside the band is None, and that is a statement, not a missing answer
    far = [dict(along=0.0, lat=0.0, n_atom=3, throw_along=100.0, throw_lat=0.0)]
    assert CL.predict_bound(880.0, 0.0, 70, far, rows, band=O.PLACEMENT_BAND) is None
    assert CL.predict_bound(880.0, 0.0, 70, far, rows) is not None
    # ``owes_nothing`` is a claim about the arrival, so it may not be made without the stations
    with pytest.raises(ValueError):
        CL.predict_bound(880.0, 0.0, 70, fan, rows, band=1.0, owes_nothing=True)
    joint = CL.predict_bound(880.0, 0.0, 70, fan, rows, band=O.PLACEMENT_BAND, link=(800.0, 0.0),
                             stations=st, owes_nothing=True)
    assert joint is not None and joint['arr_frames'] == 0.0
    # ...and it REFUSES the same candidate once its arrival owes something
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows, band=O.PLACEMENT_BAND, link=(0.0, 0.0),
                            stations=st, owes_nothing=True) is None
    assert CL.predict_bound(880.0, 0.0, 70, fan, rows, band=O.PLACEMENT_BAND, link=(0.0, 0.0),
                            stations=st)['arr_frames'] > 0.0


def test_the_band_index_is_exact_and_not_an_approximation_of_the_row_scan():
    """The banded search looks at 9 grid cells instead of every row, which is the only reason it can
    run inside a per-aim screen -- a predicate has no incumbent to prune against, so the unindexed
    scan is the whole fan by the whole row list (~10 s per aim on the shipped fan against ~130 ms).

    A spatial index is exactly the kind of speedup that is allowed to be subtly wrong at the boundary,
    so it is gated as an IDENTITY against the brute-force banded scan over a randomised layout --
    including rows placed deliberately at the cell boundary and at the band's own radius."""
    import random
    rnd = random.Random(4)
    rows = ([dict(idx=i, along=rnd.uniform(-40.0, 40.0), lat=rnd.uniform(-40.0, 40.0),
                  plan_cost=19 + (i % 5)) for i in range(60)]
            + [dict(idx=100 + j, along=float(a), lat=float(l), plan_cost=20)
               for j, (a, l) in enumerate([(0.0, 0.0), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0),
                                           (2.0, 2.0), (0.9999, 0.0)])])
    fan = [dict(along=rnd.uniform(-40.0, 40.0), lat=rnd.uniform(-40.0, 40.0),
                n_atom=3 + (i % 9), throw_along=rnd.uniform(-30.0, 30.0),
                throw_lat=rnd.uniform(-30.0, 30.0)) for i in range(300)]

    def brute(band):
        best = None
        for m in fan:
            pa, pl = m['along'], m['lat']
            for r in rows:
                d = math.hypot(r['along'] - pa, r['lat'] - pl)
                if d > band:
                    continue
                total = 70 + m['n_atom'] + float(r['plan_cost'])
                b = total + O.remaining_frames(d)
                if best is None or b < best['bound']:
                    best = dict(bound=b, miss=d, total=total, row_idx=r['idx'],
                                n_atom=m['n_atom'], resid=(m['along'], m['lat']),
                                d_station=None, arr_frames=None)
        return best

    for band in (0.25, 1.0, 1.0000001, 3.0, 7.5):
        assert CL.predict_bound(0.0, 0.0, 70, fan, rows, band=band) == brute(band), \
            "the indexed banded search disagrees with the row scan at band %s" % band
    assert CL.predict_bound(0.0, 0.0, 70, fan, rows, band=1e-9) is None
