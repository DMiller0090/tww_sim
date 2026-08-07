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


def test_the_fan_dedups_on_its_quantum_and_orders_by_frames():
    """The table stays small by griding, and cheap atoms come first so a truncated fan degrades toward
    the fast ones the objective prefers. Pinned on a hand-built cloud, no rollout."""
    made = [dict(along=1.00, lat=20.0, n_atom=7), dict(along=1.20, lat=20.0, n_atom=7),
            dict(along=5.00, lat=30.0, n_atom=2)]

    class _Fake:
        pass

    def _cloud(run0, hl, **kw):
        out = []
        for m in made:
            out.append(dict(resid_along=m['along'], resid_lat=m['lat'],
                            log=[0] * m['n_atom'], _fires=True))
        return out

    real_cloud, real_fires = CL.atom_cloud, AW.fires
    try:
        CL.atom_cloud = _cloud
        AW.fires = lambda r: True
        fan = CL.residual_fan([{'run': _Fake()}], None, quantum=1.0)
    finally:
        CL.atom_cloud, AW.fires = real_cloud, real_fires
    assert len(fan) == 2, "1.00 and 1.20 are the same 1.0 u cell and must dedup"
    assert [m['n_atom'] for m in fan] == [2, 7]


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
