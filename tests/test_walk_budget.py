"""THE WALK ADDEND OF `plan_cost` -- the floor that was inherited rather than measured (session 104).

`entry_fan.plan_cost` is ``plan_frames + thrust + 4``. Sessions 100-103 read the standing ask for
`plan_cost` 21 as a THRUST and closed it against an animation constant
(`knowledge/mechanics/cut-frame-co-swing.md`); the walk addend had never been taken below the delivered
clip's own 4. These gates pin what session 104 measured on it, so no later pass re-inherits the floor:

  1. the ARITHMETIC of the two addends, and that walk 2 + thrust 15 is the asked-for 21;
  2. `MEASURE_FAN` cannot EXPRESS a 2-frame plan (its ``j1`` starts at 2) while `iter_fan2` can -- the
     artifact that kept the floor at 4;
  3. the s93 hull is CONTAINED in the widened one, so every `outside the hull` prune against s93 was
     over-tight in the safe direction only;
  4. the 2-frame cloud is bounded by PHYSICS, not by the stick alphabet;
  5. HER PLACEMENT IS THE SWITCH: the same 2-frame cloud reads zero leverage with her frozen at the
     console placement and hundreds of points of leverage at a productive one -- the scope error that
     made the first short-walk pass read as a negative;
  6. the verified `plan_cost` 21 AND 20 stations are re-derived from their coordinates alone and must
     still be genuine by BOTH predicates, in the fine 2-frame cloud, walkable, placeable, over the floor;
  7. the LADDER's shape: 21 and 20 carry dust, 19 does not -- which is the `cut_frame_swing` ordering
     showing up on the walk addend, and the reason the two addends are not interchangeable in physics
     even though `plan_cost` cannot tell them apart.

Exact/0-ULP against pinned MODEL outputs throughout, no tolerances (`[[zero-ulp-tests-only]]`); the
pinned values live in `fixtures/courtyard_{walk_hull,walk_budget}_s104.json` and are compared by ``_bits``
where they are floats, never by ``pytest.approx``.
"""
import json
import math
import os

import pytest

from harness.rollstab import geometry_tetra as GT
from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_reach as ER
from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_depth as RD
from tww_sim.core.fp import f32

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(os.path.dirname(_HERE), 'fixtures')

WALK_HULL = os.path.join(_FIX, 'courtyard_walk_hull_s104.json')
LADDER = os.path.join(_FIX, 'courtyard_walk_budget_s104.json')

#: The only plan shape whose length is 2 -- no base hold, a 1-frame first segment, a 1-frame second.
TWO_FRAME = dict(base_frames=(0,), j1=(1,), j2max=1)


def _bits(x):
    import struct
    return struct.pack('<f', f32(x))


@pytest.fixture(scope='module')
def hulls():
    d = json.load(open(WALK_HULL))
    return {int(k): v for k, v in d['hulls'].items()}, d


@pytest.fixture(scope='module')
def ladder():
    return json.load(open(LADDER))


def _rung(ladder, plan_cost):
    return next(r for r in ladder['rungs'] if r['plan_cost'] == plan_cost)


# --------------------------------------------------------------------------- 1. the arithmetic

def test_plan_cost_is_walk_plus_thrust_plus_four():
    """The delivered clip's own decomposition, and the two routes to the asked-for 21."""
    plan = (0, 208, 110, 2, 169, 192, 2)          # the console-delivered plan: 0 + 2 + 2 = 4 frames
    assert EF.plan_frames(plan) == 4
    assert EF.plan_cost(plan, 15) == 23           # the banked deliverable
    assert EF.plan_cost(plan, 13) == 21           # the THRUST route -- refused by cut_frame_swing
    two = (0, 208, 110, 1, 169, 192, 1)           # 0 + 1 + 1 = 2 frames
    assert EF.plan_frames(two) == 2
    assert EF.plan_cost(two, 15) == 21            # the WALK route, at the DELIVERED thrust
    assert EF.plan_cost(two, 14) == 20
    # the addends are interchangeable in the cost and are NOT interchangeable in the physics: that is
    # the whole finding, so pin that the cost cannot tell them apart
    assert EF.plan_cost(plan, 13) == EF.plan_cost(two, 15)


def test_thrust_floor_is_below_the_delivered_thrust():
    assert EF.THRUST_FLOOR == 13
    assert EF.plan_cost((0, 0, 0, 1, 0, 0, 1), EF.THRUST_FLOOR) == 19


# ------------------------------------------------- 2. the alphabet artifact that kept the floor at 4

def test_measure_fan_cannot_express_a_two_frame_plan():
    """`plan_frames` is base + j1 + j2 with j2 >= 1, so MEASURE_FAN's j1 floors the plan at 3 frames.

    This is why `entry_reach.FLOOR_FRAMES = 4` was never challenged: asking the pinned measurement for
    budget 2 returns nothing, which reads as `no such plan` and is an artifact of the alphabet."""
    assert min(ER.MEASURE_FAN['j1']) == 2
    assert min(ER.MEASURE_FAN['base_frames']) == 0
    shortest = min(ER.MEASURE_FAN['base_frames']) + min(ER.MEASURE_FAN['j1']) + 1
    assert shortest == 3
    # and the shape that DOES express it is a legal argument to the fan
    assert min(TWO_FRAME['j1']) == 1
    assert min(TWO_FRAME['base_frames']) + min(TWO_FRAME['j1']) + 1 == 2


def test_floor_frames_is_the_delivered_plan_length_not_a_bound():
    """The constant is named `FLOOR_FRAMES` and documents itself as the delivered clip's plan length.

    Pinned so the distinction stays visible: 4 is what the console clip spent, and session 104 measured
    genuine dust at 2."""
    assert ER.FLOOR_FRAMES == 4
    assert EF.plan_frames((0, 208, 110, 2, 169, 192, 2)) == ER.FLOOR_FRAMES


@pytest.mark.slow
def test_iter_fan2_really_yields_two_frame_plans():
    """The fan, run on the two-frame shape, produces plans of length exactly 2 (slow: a real fan pass)."""
    n = 0
    for _k, plan in EF.iter_fan2(s1_stride=64, s2_stride=64, **TWO_FRAME):
        assert EF.plan_frames(plan) == 2
        assert EF.plan_cost(plan, 15) == 21
        n += 1
    assert n > 0


# --------------------------------------------------- 3. the s93 hull was over-tight, in one direction

def test_widened_hull_contains_every_pinned_s93_vertex(hulls):
    """A wider alphabet can only ADD endpoints, so containment -- not equality -- is the control.

    The consequence is the point: `outside the hull` was the only side used as a claim, so an over-tight
    hull made negatives too early and never too late."""
    wide, meta = hulls
    pinned = json.load(open(os.path.join(_FIX, 'courtyard_walk_hull_s93.json')))['hulls']['4']
    poly = [tuple(p) for p in wide[4]['hull']]
    outside = [p for p in pinned['hull'] if not ER.contains(poly, tuple(p), 1e-6)]
    assert outside == []
    assert wide[4]['n_endpoints'] > pinned['n_endpoints'] == meta['s93_n_endpoints_4']


def test_short_budgets_exist_and_nest(hulls):
    wide, _ = hulls
    assert sorted(wide) == [2, 3, 4]
    for b in (2, 3, 4):
        assert wide[b]['n_endpoints'] > 0
    # cumulative by construction (`walk_clouds`), so the clouds must nest
    for small, big in ((2, 3), (3, 4)):
        poly = [tuple(p) for p in wide[big]['hull']]
        assert all(ER.contains(poly, tuple(p), 1e-6) for p in wide[small]['hull'])


# ------------------------------------- 4. the 2-frame cloud is bounded by physics, not by the alphabet

def test_two_frame_cloud_is_alphabet_saturated(hulls):
    """5.75x the sticks buys under 5% of area, so refining the alphabet is not a lever on this budget."""
    _wide, meta = hulls
    tf = meta['two_frame']
    a8, a2 = tf['8']['area'], tf['2']['area']
    assert tf['2']['n_endpoints'] > 10 * tf['8']['n_endpoints']      # 5.75x alphabet, both segments
    assert a2 > a8                                                  # finer can only add
    assert (a2 - a8) / a8 < 0.05                                    # and it adds under 5%


# ------------------------------------------------------------- 5. her placement is the swept axis

def test_frozen_placement_reads_a_false_negative_on_the_short_cloud(hulls):
    """THE SCOPE ERROR, pinned as a number.

    `hull_scan`/`hull_field` grid LINK'S ENTRY at ONE placement for the pushed actor. Over the 2-frame
    cloud, at her console placement she is out of Co range on the cut frame from ~40 u away, so the
    field is a no-push plateau and the scan reports `no leverage` -- which is a statement about her
    placement, not about the frame budget. At a productive placement the same cloud is mostly leverage."""
    wide, _ = hulls
    facing = {c: f for f, _b, _s in ES.aim_cells() for c in [ES.aim_cell(f)]}[2552]
    frozen = ES.console_seed()['tetra']
    productive = (-1656.3126886151, -883.2556233293)

    a = ER.hull_field(frozen, facing, 15, RD.DELIVERED_LEAN, frames=2, hulls=wide, step=1.5)
    b = ER.hull_field(productive, facing, 15, RD.DELIVERED_LEAN, frames=2, hulls=wide, step=1.5)
    assert len(a['pts']) == len(b['pts']) > 0        # the SAME cloud, the same grid
    assert a['n_leverage'] == 0                      # ... and it reads barren with her frozen
    assert b['n_leverage'] > 0                       # ... and productive when she moves
    assert abs(b['abs_min']) < abs(a['abs_min']) / 10.0


# ------------------------------------------------------- 6. the verified plan_cost 21 stations survive

def test_ladder_shape(ladder):
    """Every rung is a real 2-frame plan whose cost is its thrust plus 6, and each agrees with
    `plan_cost` computed on an actual two-frame plan tuple."""
    assert {r['plan_cost'] for r in ladder['rungs']} == {21, 20, 19}
    for r in ladder['rungs']:
        assert r['plan_frames'] == 2
        assert EF.plan_cost((0, 0, 0, 1, 0, 0, 1), r['thrust']) == r['plan_cost']
        assert all(row['ok'] for row in r['rows'])
        assert len(r['rows']) == r['n_verified']


def test_the_ladder_stops_where_the_cut_frame_swing_says_it_does(ladder):
    """21 and 20 carry dust; 19 does not.

    This is `mechanics/cut-frame-co-swing.md`'s ordering (-1.2850 at thrust 15, +1.8547 at 14, +8.9252 at
    13) reappearing on the WALK addend -- so `plan_cost` treating the addends as interchangeable is an
    arithmetic fact and not a physical one. Shortening the walk starts the roll earlier without
    re-phasing it, which is exactly why it cannot rescue the floor thrust."""
    assert _rung(ladder, 21)['n_live_placements'] > 0
    assert _rung(ladder, 20)['n_live_placements'] > 0
    assert _rung(ladder, 19)['n_live_placements'] == 0
    assert _rung(ladder, 19)['rows'] == []
    # and the depth ordering follows the swing, not the frame count
    assert _rung(ladder, 21)['deepest'] > _rung(ladder, 20)['deepest'] > RD.DEPTH_FLOOR


def test_herd_delta_is_a_lead_not_a_cost(ladder):
    """Most viable placements sit FARTHER from the corner than the console one, so the walk frames are
    not paid back at the herd. A distance, never a frame count -- the conversion owes the herd search."""
    cons = ladder['console_tetra']
    assert _bits(math.hypot(cons[0] - ladder['corner'][0], cons[1] - ladder['corner'][1])) \
        == _bits(ladder['console_tetra_dist_to_corner'])
    for cost in (21, 20):
        r = _rung(ladder, cost)
        assert r['herd_delta_max'] > 0.0
        assert r['n_less_herd_than_console'] > r['n_live_placements'] / 2


def test_ladder_stations_are_genuine_by_both_predicates_and_reachable(ladder, hulls):
    """Re-derive each verified station from its COORDINATES and require every clause again.

    Nothing is read out of the fixture except the inputs and the expected values: the razor is re-zeroed,
    the cross-sweep re-run, and the endpoint re-tested with `geometry_tetra.genuine_clip` -- the engine's
    independent predicate. Exact bit-equality on the depth, never a tolerance."""
    wide, meta = hulls
    fine2 = [tuple(p) for p in meta['two_frame']['2']['hull']]
    rows = [(rung['thrust'], r) for rung in ladder['rungs'] for r in rung['rows']]
    assert len(rows) > 0
    for thrust, r in rows:
        facing, tetra = r['facing'], tuple(r['tetra'])
        ctx, _sch, _resid = ES.build_fast(facing, RD.DELIVERED_LEAN, thrust)
        row = ctx.sweep_par([(tetra[0], tetra[1], r['entry'][0], r['entry'][1])], 0)[0]

        old, new = (row[1], row[2]), (row[3], row[4])
        assert bool(row[0]) is True, r                        # the engine's own genuine flag
        assert GT.genuine_clip(old, new) is True, r           # ... and the independent predicate
        assert _bits(RD.depth_of(row)) == _bits(r['depth'])   # 0-ULP against the pinned depth
        assert RD.depth_of(row) >= RD.DEPTH_FLOOR
        assert _bits(old[0]) == _bits(r['old'][0]) and _bits(old[1]) == _bits(r['old'][1])
        assert _bits(new[0]) == _bits(r['new'][0]) and _bits(new[1]) == _bits(r['new'][1])

        # the entry is reachable by a TWO-frame walk, on walkable floor, and she can stand where she is
        ox, oz = ES.roll_entry((0.0, 0.0), facing, None)
        assert ER.contains([(p[0] + ox, p[1] + oz) for p in fine2], tuple(r['entry']), 0.0)
        assert TA.is_walkable(r['entry'][0], r['entry'][1])
        assert RD.placeable(tetra)


def test_cost21_beats_the_banked_deliverable_on_depth(ladder):
    """The short-walk route is not a marginal trade: at plan_cost 21 its deepest verified station is
    DEEPER than the console-delivered 4-frame clip, at two fewer frames."""
    deepest = max(r['depth'] for r in _rung(ladder, 21)['rows'])
    assert deepest > RD.DEPTH_FLOOR
    assert deepest > 0.2533          # the delivered thrust-15 4-frame clip's own depth


def test_cost21_endpoints_land_on_the_seam_corner(ladder):
    """Independent corroboration: every endpoint sits within a unit of the known clip corner."""
    for rung in ladder['rungs']:
        for r in rung['rows']:
            assert math.hypot(r['new'][0] - ladder['corner'][0],
                              r['new'][1] - ladder['corner'][1]) < 1.0
