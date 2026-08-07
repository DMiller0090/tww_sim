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
