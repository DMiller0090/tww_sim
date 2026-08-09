"""The Courtyard push OBJECTIVE, gated (session 60).

`harness/tetrapush/objective.py` turns Dereck's session-60 steer into predicates a search can prune
on. These tests pin the parts that a future session could otherwise quietly re-interpret: what the
frame bar IS, that the wall-clearance metric agrees with the CONSOLE's own brace point, that the
placement the objective demands is reachable without wall collision at all, and that node 1's
locked plan violates three of the rules (so nobody re-adopts it as a starting point by accident).

Offline, no Dolphin: everything runs off the locked fixtures and the 0-ULP `FreeRun`.
"""
import json
import math
import os
import warnings

import pytest

from harness.tetrapush import objective as O
from harness.tetrapush import seeds

_FX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures')


@pytest.fixture(scope="module")
def env():
    return seeds.load_env()


@pytest.fixture(scope="module")
def walls():
    return O.courtyard_walls()


def _arrivals(env):
    """The two REAL arrivals of `fixtures/courtyard_arrivals_s75.json`, replayed from their delivered
    input logs (`beam_io`: a state's identity IS its log, and a replay is bit-exact) and asserted
    against the state the fixture records, so these are those arrivals and not near ones.

    Cached because both gates below want them and a replay is ~30 ms."""
    if not _ARRIVALS:
        with open(os.path.join(_FX, 'courtyard_arrivals_s75.json')) as fh:
            rec = json.load(fh)
        for key, a in rec['arrivals'].items():
            run = seeds.make_freerun(env)
            run.pre_seed_input(seeds.dtm_input_at(env)(0))
            for d in a['log']:
                run.step(d)
            st = a['arrival']
            assert (run.link.pos_x, run.link.pos_z) == tuple(st['link'])   # 0-ULP or not the state
            assert (run.tx, run.tz) == tuple(st['tetra'])
            assert run.link.speedF == st['speedF'] and len(a['log']) == a['frames']
            _ARRIVALS[key] = dict(run=run, rec=a)
    return _ARRIVALS


_ARRIVALS = {}


# --------------------------------------------------------------------------- the bar

def test_the_frame_floor_is_the_nearest_coord_over_the_measured_split_law_ceiling(env):
    """The bar is DERIVED, not chosen: the herd ceiling is the CC split law's `|speedF|/2` at the
    roll cap (`steered_search.push_ceiling` measures the human realising 98.2% of it), and the floor
    is the nearest genuine coord divided by it. If either input moves, the bar moves with it."""
    f = O.frame_floor(env)
    t0 = env['cyl'][0]['tetra']['pos']
    rows, _ = seeds.load_placements()

    assert O.PUSH_CEILING == 26.0 / 2.0, "the ceiling is the roll cap halved by the 50/50 split"
    nearest = min(math.hypot(p['x'] - t0[0], p['z'] - t0[2]) for p in rows)
    assert f['dist'] == pytest.approx(nearest), "the floor must use the NEAREST coord"
    assert f['frames'] == pytest.approx(f['dist'] / O.PUSH_CEILING)
    assert f['frames_int'] == math.ceil(f['frames'])
    # A plan is a whole number of frames, and 72 * 13.0 does not cover the distance.
    assert f['frames_int'] * O.PUSH_CEILING >= f['dist'] > (f['frames_int'] - 1) * O.PUSH_CEILING
    assert f['budget'] == f['frames_int'] + O.TIMELOSS_BUDGET
    assert f['preferred'] == f['frames_int'] + O.TIMELOSS_PREFERRED


def test_the_budget_is_dereck_s_two_frame_spec(env):
    """Pinned because it is the one number here that is a DECISION, not a measurement: a
    placement-precise plan may cost at most 2 frames over an all-out push (1 preferred)."""
    assert (O.TIMELOSS_BUDGET, O.TIMELOSS_PREFERRED) == (2, 1)
    f = O.frame_floor(env)
    assert (f['frames_int'], f['preferred'], f['budget']) == (73, 74, 75)


def test_rule_2_is_about_the_total_and_the_herd_is_no_longer_all_of_it(env):
    """**Dereck's steer, session 135: "more than 75 herd frames is acceptable if it saves time
    overall."**

    Session 60's budget was written when the plan WAS the herd -- push her onto a coord and stop --
    so herd frames and plan frames were the same number and `TIMELOSS_BUDGET` was a total. Sessions
    123 and 125 replaced the ending: no walk-away, and the razor on Link, so a plan costs herd frames
    plus the gap Link must still close plus the cut (`handoff.endpoint`'s ``bound``). At the walk cap
    a frame buys ~17 u of that gap, so a longer herd that lands her better can be a shorter PLAN.

    Gated on both sides, because the risk here is a rule that quietly stops binding: with no measured
    ``total`` the verdict is exactly the pre-s135 one, and with one the budget clause is the total's."""
    rows = [dict(sim_link=(-1900.0, -1000.0), sim_tetra=(-2100.0, -1050.0), speedF=20.0)]
    base = dict(complete=True, within_budget=False, wall_ok=True, regime_ok=True, terminal_ok=True)
    assert not O.verdict(dict(base, total=None, beats_incumbent=False))
    assert not O.verdict(dict(base, total=float(O.TOTAL_INCUMBENT), beats_incumbent=False))
    assert O.verdict(dict(base, total=100.06, beats_incumbent=True))
    assert O.verdict(dict(base, within_budget=True, total=None, beats_incumbent=False))
    # ...and the other four rules still veto whatever the total says
    for veto in ('complete', 'wall_ok', 'regime_ok', 'terminal_ok'):
        assert not O.verdict(dict(base, total=90.0, beats_incumbent=True, **{veto: False})), veto
    # the column is only ever what the caller measured: `score_plan` does not invent one
    sc = O.score_plan(env, rows)
    assert sc['total'] is None and sc['beats_incumbent'] is False
    sc = O.score_plan(env, rows, total=100.06)
    assert sc['total'] == 100.06 and sc['beats_incumbent'] is True
    assert O.TOTAL_INCUMBENT == 101, 'the banked console plan is the number to beat'


def test_the_push_ceiling_is_a_sustained_rate_not_a_per_frame_law(env):
    """**Session 61, measured off the human's own recording**: `PUSH_CEILING` (13.0 u/frame) is the
    STEADY STATE of the CC split, and single frames beat it badly.

    The push depth is measured to Link's ANIMATED exec Co-centre, which moves by the foot term plus
    the pose swing that leads/trails his feet 6-28 u -- so his 4th recorded frame advances Tetra
    ~18.8 u, nearly 1.5x the "ceiling", while his 44-frame mean sits at 12.758 because the swing
    cancels over a long window. Pinned because a future session reading 13.0 as a per-frame law
    would treat a search cycle that legitimately sustains 13.3 as a bug and "fix" the physics."""
    from harness.tetrapush import search as S
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    rows = S.rollout_recorded(env, upto=45)['rows']
    t0 = env['cyl'][0]['tetra']['pos']

    prev, worst, mean = (t0[0], t0[2]), 0.0, None
    for r in rows:
        t = r['tetra']
        worst = max(worst, hl.along(t[0], t[1]) - hl.along(prev[0], prev[1]))
        prev = t
    mean = hl.along(prev[0], prev[1]) / len(rows)

    assert worst > O.PUSH_CEILING * 1.4, \
        "no recorded frame beats the ceiling -- re-derive before trusting `plan_bound`'s h"
    assert mean == pytest.approx(12.758, abs=0.01), "the human's sustained rate moved"
    assert mean < O.PUSH_CEILING, "the SUSTAINED rate must still sit under the split-law ceiling"


def test_the_plan_bound_is_frames_plus_the_steady_state_remainder():
    """`plan_bound` is the search's rank and the budget cut's test, so its shape is pinned: exact
    frames spent plus distance over the sustained ceiling, and EXACT (== frames) once Tetra is on the
    coord. It counts a lateral miss as cost, which is the whole reason it replaced the herd rate."""
    assert O.plan_bound(40, 0.0) == 40
    assert O.plan_bound(40, O.PUSH_CEILING) == 41
    assert O.remaining_frames(130.0) == pytest.approx(10.0)
    # 100 u down-herd and 100 u down-herd-plus-lateral are NOT the same cost (a rate says they are)
    assert O.plan_bound(40, math.hypot(100.0, 28.0)) > O.plan_bound(40, 100.0)


# ------------------------------------------------- the lateral half of what a finish costs (s62)

def test_thread_frames_prices_lateral_apart_from_along(env):
    """**The correction `plan_bound` needed** (session 62): along and lateral are bought on the SAME
    frames, so a finish costs the max of the two -- but at very different rates, `PUSH_CEILING` 13.0
    against a measured `LATERAL_RATE` of ~3, so a unit of lateral is ~4x dearer.

    Pinned as a shape, not as floats: on the thread the cost is zero; pure along is the along rate;
    the same number of units of LATERAL costs strictly more; and two axes together cost the max, not
    the sum (one push moves both)."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl)
    lo, hi = th['along_lo'], th['along_hi']
    mid = 0.5 * (lo + hi)

    assert O.thread_frames(mid, th['lat_at'](mid), th) == pytest.approx(0.0, abs=1e-6)
    # pure along, from behind the near end -- the along rate, and nothing else
    assert O.thread_frames(lo - 26.0, th['lat_at'](lo), th) == \
        pytest.approx(26.0 / O.PUSH_CEILING, abs=0.02)
    # the SAME 26 u, but lateral: strictly dearer, by the ratio of the two rates
    pure_lat = O.thread_frames(mid, th['lat_at'](mid) + 26.0, th)
    assert pure_lat > 26.0 / O.PUSH_CEILING * 3.0
    # both at once costs the max of the two, never their sum
    both = O.thread_frames(lo - 26.0, th['lat_at'](lo) + 26.0, th)
    assert both < 26.0 / O.PUSH_CEILING + pure_lat


def test_thread_frames_is_minimised_over_where_on_the_thread_she_lands(env):
    """The target is a 47.6 u SEGMENT, so a plan chooses WHERE on it to stop, and the two ends want
    different laterals -- which is the whole session-61 arithmetic. From the s62 endpoint (along
    907.9, lat -2.44) the far end is +76 u of along away and the near end +30 u plus 10.4 u of
    lateral, and the search must find whichever is cheaper rather than aiming at a fixed point."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl)
    h = O.thread_frames(907.9, -2.44, th)
    at_near = max(abs(937.5 - 907.9) / O.PUSH_CEILING,
                  abs(th['lat_at'](937.5) - (-2.44)) / O.LATERAL_RATE)
    at_far = max(abs(984.1 - 907.9) / O.PUSH_CEILING,
                 abs(th['lat_at'](984.1) - (-2.44)) / O.LATERAL_RATE)
    assert h <= min(at_near, at_far) + 1e-9, "the minimum must beat aiming at either fixed end"
    # ... and it is a genuine interior minimum here, not just the better endpoint
    assert h < min(at_near, at_far) - 0.05


def test_thread_cost_charges_for_lateral_only_near_the_finish(env):
    """**Why this is the LAST cycle's rank and not the chain's** -- and the answer is the max form's,
    not a policy bolted on top.

    Mid-chain the lateral is free IN THIS MODEL: at the s62 cycle-2 endpoint 39.9 u off the thread
    there are still ~26 frames of along to push, which is more than the ~14 the lateral needs, so the
    max form charges nothing extra and reads identical to the on-thread endpoint. That is the right
    shape for a rank -- ranking a mid-chain beam on the lateral would discard the branch that comes
    back (s61: it oscillates +5.8, -39.9, +8.9).

    It is NOT free in the plan, though, and session 63 measured the difference: that same -39.9
    endpoint cost 21.5 u of sideways push (~1.7 frames) once the last roll and the terminal actually
    corrected it (`objective.push_budget`). Both statements are true and they act in different places
    -- the rank stays as gated here, and the corridor branch is kept instead of ranked
    (`objective.push_corridor`, `full_herd._mixed_beam`).

    At the cycle-3 endpoint, with only ~68 u of along left, the same arithmetic flips: 16.7 u of
    lateral now needs MORE frames than the along does, so it becomes the binding term and the rank
    finally sees it. `plan_bound` never does, at either range."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl)
    near_lat = th['lat_at'](th['along_lo'])

    mid_on = O.thread_cost(46, 590.9, near_lat, th)
    mid_off = O.thread_cost(46, 590.9, near_lat - 39.9, th)
    assert mid_off == pytest.approx(mid_on), \
        "mid-chain, lateral must be free -- there are more along frames left than lateral ones"

    end_on = O.thread_cost(69, 869.2, near_lat, th)
    end_off = O.thread_cost(69, 869.2, 24.61, th)
    assert end_off > end_on + 0.3, "at the endpoint the lateral must become the binding term"
    # and it binds because it is the LATERAL, not because she is further from a point
    assert O.thread_frames(869.2, 24.61, th) > abs(937.568 - 869.2) / O.PUSH_CEILING


def test_thread_cost_floors_the_remainder_at_a_frame_while_rule_3_is_unmet(env):
    """Rule 3 as a FLOOR on the remainder, not a penalty added to it: a frame where Link is not
    still moving cannot BE the placement frame, so at least one more has to follow -- but with three
    frames of herding still to do, being un-ready right now is genuinely free, and charging for it
    would rank on a condition that has not come due."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl)
    mid = 0.5 * (th['along_lo'] + th['along_hi'])
    on_thread = th['lat_at'](mid)
    assert O.thread_cost(70, mid, on_thread, th, ready=True) == pytest.approx(70.0, abs=1e-6)
    assert O.thread_cost(70, mid, on_thread, th, ready=False) == pytest.approx(71.0, abs=1e-6)
    far = O.thread_frames(th['along_lo'] - 40.0, on_thread, th)
    assert far > 1.0, "pick a state whose remainder already exceeds a frame"
    assert O.thread_cost(70, th['along_lo'] - 40.0, on_thread, th, ready=False) == \
        O.thread_cost(70, th['along_lo'] - 40.0, on_thread, th, ready=True)


# ------------------------------------------------------- where the push goes (session 63)

def test_the_push_budget_splits_a_plan_into_magnitude_and_straightness(env):
    """**The accounting that reframed the s62 blocker**, pinned as an identity on constructed
    geometry: Tetra has no foot term, so her displacement IS the push, and

        push == along + sideways

    exactly, with ``sideways`` the projection excess of a bent path. A straight down-herd path has
    ZERO sideways -- not approximately zero -- which is what makes the number readable as "push that
    did not close the distance"."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine((0.0, 0.0), (0.0, 1.0))            # along = +z, lateral = -x
    assert hl.along(0.0, 10.0) == pytest.approx(10.0)

    straight = [dict(tetra=(0.0, k * O.PUSH_CEILING)) for k in range(1, 9)]
    b = O.push_budget(straight, hl, origin=(0.0, 0.0))
    assert b['push'] == b['along'], "a straight path must spend nothing sideways -- exactly"
    assert b['sideways'] == 0.0 and b['sideways_frames'] == 0.0
    assert b['per_frame'] == pytest.approx(O.PUSH_CEILING) and b['saturation'] == pytest.approx(1.0)

    # a constant-angle path: 12 u of along and 3 u of lateral per frame
    bent = [dict(tetra=(-3.0 * k, 12.0 * k)) for k in range(1, 9)]
    bb = O.push_budget(bent, hl, origin=(0.0, 0.0))
    assert bb['along'] == pytest.approx(96.0)
    assert bb['push'] == pytest.approx(8 * math.hypot(12.0, 3.0))
    assert bb['sideways'] == pytest.approx(bb['push'] - bb['along'], abs=1e-12)
    assert bb['sideways_frames'] == pytest.approx(bb['sideways'] / O.PUSH_CEILING)
    # ... and the same magnitude buys strictly less along than the straight path did
    assert bb['along'] < b['along'] and bb['saturation'] < 1.0

    # without an origin the first frame is unmeasurable: the totals drop it, the RATE does not
    no_origin = O.push_budget(straight, hl)
    assert no_origin['push'] == pytest.approx(b['push'] - O.PUSH_CEILING)
    assert no_origin['per_frame'] == pytest.approx(b['per_frame'])


def test_the_recorded_human_s_push_is_saturated_and_straight(env):
    """**THE session-63 measurement, on the one plan that is ground truth.** The recorded human buys
    12.80 u/frame of push magnitude -- 98.5% of `PUSH_CEILING`, not 100% -- and spends only ~2 u of it
    sideways over 44 frames. Both halves are load-bearing:

      * the magnitude is what it is for anybody. The search's own 73-frame plan buys the SAME
        12.81 u/frame at the same 98.5%, so a shortfall cannot be blamed on being "out of push"
        (which is how s62's terminal diagnostic read it) -- only on direction.
      * therefore a STRAIGHT plan needs ``dist / 12.80``, not ``dist / 13.0``: 73.2 frames rather than
        72.1. That is inside Dereck's accepted 75 but it leaves under 2 frames of slack, which is why
        27 u of sideways (the s61/s62 plan's) is fatal and 2 u (the human's) is not."""
    from harness.tetrapush import search as S
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    rows = S.rollout_recorded(env, upto=45)['rows']
    t0 = env['cyl'][0]['tetra']['pos']
    b = O.push_budget(rows, hl, origin=(t0[0], t0[-1]))
    floor = O.frame_floor(env)

    assert b['per_frame'] == pytest.approx(12.805, abs=0.02), "the human's push magnitude moved"
    assert 0.97 < b['saturation'] < 1.0, \
        "even the human does not reach PUSH_CEILING -- if he now does, the ceiling is wrong"
    assert b['sideways'] < 3.0, "the human's herd is straight: that is why his along rate is 12.758"
    assert b['along'] / (len(rows)) == pytest.approx(12.758, abs=0.01)
    # the frames a straight plan needs, at the magnitude anybody actually achieves
    straight_frames = floor['dist'] / b['per_frame']
    assert straight_frames == pytest.approx(73.2, abs=0.2)
    assert floor['frames'] < straight_frames <= floor['budget'], \
        "a straight plan must be inside Dereck's budget but above the PUSH_CEILING floor"


def test_the_push_corridor_is_the_line_the_frame_floor_assumes(env):
    """`push_corridor` is not a new target -- it is the straight line from Tetra's start to the
    coord `frame_floor` already prices the bar against, expressed in herd coordinates. Pinned so it
    cannot drift into a tuned band: it passes through the origin and through the bar's own coord, and
    it rates the s62 cycle-2 endpoints the way the measurement did."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    cor = O.push_corridor(hl)
    floor = O.frame_floor(env)

    assert cor['lat_at'](0.0) == 0.0, "the corridor starts where Tetra does"
    assert cor['target'][0] == pytest.approx(floor['dist'], abs=0.5), \
        "the corridor's target IS the bar's nearest coord"
    assert cor['offset'](*cor['target']) == pytest.approx(0.0, abs=1e-9)
    assert cor['offset'](500.0, cor['lat_at'](500.0) + 7.0) == pytest.approx(7.0)
    # the two reachable cycle-2 endpoints session 63 measured: the beam's pick is ~6.5x further off
    assert cor['offset'](590.7, -40.49) == pytest.approx(45.5, abs=0.2)
    assert cor['offset'](585.9, -2.02) == pytest.approx(7.0, abs=0.2)
    assert cor['offset'](590.7, -40.49) > 6.0 * cor['offset'](585.9, -2.02)


# --------------------------------------------------------------------------- the walls

def test_the_wall_metric_reproduces_the_console_s_own_brace_point(walls):
    """THE VALIDATION of the whole wall-clearance rule, and it is against console ground truth.

    Walls are deliberately NOT modelled, so the objective instead keeps the plan out of the region
    where their absence shows. That is only trustworthy if `wall_distance` measures the same thing
    the game braces against. Node 1's locked console capture happens to contain two frames where
    Link is pinned on the courtyard back wall (n=100 and n=160, `speedF` ~0.1/0.5, z identical to
    the bit 60 frames apart) -- and this module puts them at `LINK_WALL_R` to within f32 rounding.

    NOT a fidelity gate (`[[zero-ulp-tests-only]]`): `WallCorrect` braces against a wall PLANE and
    the stored position is f32, so a geometric cross-check carries a tolerance by construction. It
    is here to catch the wall set being filtered wrong or the radius being mis-cited."""
    s56 = json.load(open(os.path.join(_FX, 'courtyard_node1_console_s56.json')))
    braced = {s['n']: s for s in s56['samples'] if s['n'] in (100, 160)}
    assert len(braced) == 2, "the fixture no longer carries the two braced rows"
    for n, s in braced.items():
        d = O.wall_distance(s['link']['x'], s['link']['z'], walls)
        assert abs(d - O.LINK_WALL_R) < 1e-3, \
            "n=%d: console braces Link at %.9f, LINK_WALL_R is %.1f" % (n, d, O.LINK_WALL_R)


def test_the_wall_radii_are_the_collision_model_s_own(env):
    """The radii are imported from the two actors' wall cylinders, never restated here."""
    from tww_sim.core.npc_zl1 import WALL_R as ZL1_R
    from tww_sim.land.walls import WALL_R as LINK_R
    assert (O.LINK_WALL_R, O.TETRA_WALL_R) == (LINK_R, ZL1_R) == (35.0, 50.0)


def test_the_target_is_a_segment_across_the_herd_axis_not_a_cluster(env):
    """**Session 61, measured: the placement target's SHAPE, and what it implies for a plan.**

    The 288 genuine coords are a nearly straight 47.6 u segment sitting 12.2 deg off the herd axis,
    which in `HerdLine` coordinates makes them a LINE: lateral falls ~0.216 u per u of along, from
    +7.9 at the near end (along 937.5, coord idx 287) to -2.1 at the far end (along 984.1).

    That is the difference between "hit a point" and "hit a line", and it is the whole reason the
    s43-s51 endgame needed a reposition phase: Tetra has ~46 u of freedom in WHERE along she stops
    (~3.6 frames of pushing), but her lateral has to be inside a ~10 u window, and no amount of
    further down-herd pushing moves a lateral miss into it -- pushing only trades along for lateral
    at 0.216 u per u. Pinned so the next search states its lateral requirement in these numbers."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl)

    assert th['length'] == pytest.approx(47.606, abs=0.01)
    assert th['deg_off_axis'] == pytest.approx(12.16, abs=0.05)
    assert th['max_chord_dev'] < 2.0, "the coord set is no longer a near-straight segment"
    assert (th['along_lo'], th['along_hi']) == pytest.approx((937.535, 984.072), abs=0.01)
    assert (th['lat_lo'], th['lat_hi']) == pytest.approx((-2.270, 7.943), abs=0.01)

    # the ALONG direction is slack: every lateral in the window has an along that matches it
    assert th['lat_at'](th['along_lo']) == pytest.approx(th['lat_hi'], abs=0.02)
    assert th['lat_at'](th['along_hi']) == pytest.approx(th['lat_lo'], abs=0.2)
    # ... and a lateral outside it has none, at any along on the thread (the s44 +36 u case)
    assert not (th['lat_lo'] <= 36.0 <= th['lat_hi'])
    span = [th['lat_at'](a) for a in (th['along_lo'], th['along_hi'])]
    assert max(span) < 36.0 - 20.0, "a +36 u lateral must be far outside the placeable window"


def test_the_along_floor_bounds_the_placement_distance_whatever_the_lateral(env):
    """**The cheapest true test an arrival band can be put to** (session 76): ``along``/``lateral`` is
    an orthonormal frame and the coords start at `placement_thread`'s ``along_lo``, so an arrival short
    of that end is at least its along deficit from EVERY coord, whatever its lateral.

    Worth gating because ``pd_pre`` is JOINT -- a band's floor is a min over its rolls, so a short
    floor never says whether the band ran out of DISTANCE or only of aim -- while this does, off the
    band's along CEILING, a number the same sweep already prints. Sessions 71-75 each paid ~2700 s of
    full-resolution aim sweep to learn a rung was short.

    Pinned as the inequality itself, on the two banked REAL arrivals plus the coord set, so a future
    refactor of `HerdLine`/`placement_thread` that broke the frame (making the "bound" cut off real
    survivors) fails here."""
    from harness.tetrapush.reposition import HerdLine
    from harness.tetrapush import full_herd as FH
    hl = HerdLine.from_env(env)
    rows = seeds.load_placements()[0]
    th = O.placement_thread(hl, rows)

    # the bound holds on real states, and it is a BOUND (never above the true distance)
    for a in _arrivals(env).values():
        run = a['run']
        f = O.along_floor(hl.along(run.tx, run.tz), th)
        assert f['pd_floor'] <= FH._placement_dist(run, rows) + 1e-9, \
            "the along floor cut off a real arrival -- it is not a bound"

    # and it is TIGHT where it must be: straight up-herd of the near end, the floor IS the distance
    near = min(((hl.along(p['x'], p['z']), hl.lateral(p['x'], p['z'])) for p in rows),
               key=lambda p: p[0])
    for back in (1.0, 12.5, 40.0):
        f = O.along_floor(near[0] - back, th)
        true = min(math.hypot(near[0] - back - hl.along(p['x'], p['z']),
                              near[1] - hl.lateral(p['x'], p['z'])) for p in rows)
        assert f['pd_floor'] == pytest.approx(back, abs=1e-9)
        assert true == pytest.approx(back, abs=1e-9), "the near end is no longer the nearest coord"

    # past the near end there is nothing left to bound: the lateral takes over (`thread_frames`)
    assert O.along_floor(th['along_hi'], th)['pd_floor'] == 0.0


def test_the_along_floor_s_ALLOWANCE_is_per_arrival_and_must_not_be_borrowed(env):
    """**The half of `along_floor` that a session can get wrong** (session 76, and session 75 already
    lost a frame rung to the same mistake one level down).

    The screen needs what the escape RECOVERS, and that is a property of the ARRIVAL, not of the
    recipe: ``freeze_f`` is set by the arrival's own `full_herd._centre_feet` (s75) and the escape's
    cumulative plow scales with the frames that buys. The two banked arrivals show the spread at the
    SAME separation -- and it is large enough to flip the verdict on a whole band.

    Measured this session: screening node 0's jf-7 band (along ceiling 908.68) with s75's borrowed
    frz-3 allowance of 22.94 REFUSES it, while its own arrivals' 33.76-36.05 ADMITS it. The band is
    still short -- only 21.08 u of that 33.76 u plow points at the thread -- but it is short for a
    different reason than the ledger said, and a screen that refuses it on a borrowed number would
    have hidden that. So: pass a recovery measured on the arrival being screened."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl, seeds.load_placements()[0])
    arr = _arrivals(env)
    deep, shallow = arr['deep']['rec'], arr['shallow']['rec']

    # the same freeze_f, two arrivals, plow bounds an order apart in what they allow
    shared = ({int(k) for k in deep['per_freeze_f']} & {int(k) for k in shallow['per_freeze_f']})
    assert shared, "the banked pair no longer shares a separation frame -- re-bank the contrast"
    spread = max(abs(deep['per_freeze_f'][str(f)]['plow'] - shallow['per_freeze_f'][str(f)]['plow'])
                 for f in shared)
    assert spread > 10.0, \
        "the per-arrival plow spread collapsed; if it is really portable, say so and simplify"

    # and the screen's verdict flips on it, at one fixed along (node 0's measured jf-7 ceiling)
    ceiling = 908.68
    assert O.along_floor(ceiling, th, recovery=22.94)['ok'] is False       # s75's borrowed row
    assert O.along_floor(ceiling, th, recovery=33.76)['ok'] is True        # the band's own bound
    # the screen is exactly the inequality it claims to be, at the boundary
    f = O.along_floor(ceiling, th, recovery=None)
    edge = f['pd_floor'] - O.PLACEMENT_BAND
    assert O.along_floor(ceiling, th, recovery=edge)['ok'] is True
    assert O.along_floor(ceiling, th, recovery=edge - 1e-9)['ok'] is False
    assert O.along_floor(ceiling, th, recovery=edge)['needs_along'] == pytest.approx(ceiling, abs=1e-9)


def test_score_plan_reports_where_the_endpoint_sits_on_the_thread(env, walls, node1_rows):
    """The `placeable` / `lat_error` half of the score, gated on definition (the numbers themselves
    belong to whatever plan is being scored): `lat_error` is the endpoint's lateral minus the
    thread's own lateral at that along, and `placeable` says whether any along could place her."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    th = O.placement_thread(hl)
    sc = O.score_plan(env, node1_rows, hl=hl, walls=walls)
    tol = sc['band'] / math.cos(math.atan(th['slope']))

    a = min(max(sc['tetra_along'], th['along_lo']), th['along_hi'])
    assert sc['lat_error'] == pytest.approx(sc['tetra_lat'] - th['lat_at'](a))
    assert sc['placeable'] == (th['lat_lo'] - tol <= sc['tetra_lat'] <= th['lat_hi'] + tol)
    # on a coord => on the thread: `complete` cannot be true while `placeable` is false
    assert (not sc['complete']) or sc['placeable']


def test_every_genuine_coord_is_wall_free_for_tetra(walls):
    """The objective is ACHIEVABLE without a wall model: every one of the 288 clip coords clears
    Tetra's own wall cylinder, so she can be placed on one without `WallCorrect` ever acting. The
    wall contact Dereck means happens later, during the clip roll, and belongs to the recorded
    solution list -- not to the push this planner solves."""
    rows, _ = seeds.load_placements()
    worst = min((O.wall_distance(p['x'], p['z'], walls) - O.TETRA_WALL_R, p['idx']) for p in rows)
    assert worst[0] > 0.0, "coord idx %d is inside Tetra's wall cylinder (margin %.3f)" % (
        worst[1], worst[0])


def test_wall_margin_is_the_binding_actor(walls):
    """`wall_margin` reports each actor's own clearance and takes the minimum, so a plan that walks
    LINK into a wall is caught even while Tetra is in open floor (which is exactly node 1's case)."""
    t0 = (-1336.7809, -0.9584)                       # Tetra's start: open floor, far from anything
    # 25 u from the back wall (plane z = -990.2557) -- 10 u inside Link's 35 u cylinder.
    m = O.wall_margin(-1608.0, -965.0, t0[0], t0[1], walls)
    assert m['link'] < 0.0 < m['tetra'], "expected Link inside the wall, Tetra clear"
    assert m['margin'] == m['link']


# --------------------------------------------------------------------------- the regime

@pytest.mark.slow
def test_the_fast_prune_predicate_agrees_exactly_with_the_measured_distance(walls):
    """`clear_of_walls` is what a beam search calls per frame, so it early-rejects on bounding
    boxes -- but it must stay EXACT, not conservative. Checked over the whole room: an
    approximation here would silently admit wall-violating plans, which is the one thing the rule
    exists to stop."""
    import random
    rng = random.Random(7)
    for _ in range(2000):
        x, z = rng.uniform(-1750.0, -1250.0), rng.uniform(-1050.0, 100.0)
        assert O.clear_of_walls(x, z, O.LINK_WALL_R, walls) == \
            (O.wall_distance(x, z, walls) >= O.LINK_WALL_R), "disagreement at (%f, %f)" % (x, z)


def test_in_regime_is_the_follow_engage_distance():
    """The regime bound is `npc_zl1`'s own engage distance, not a search preference: past it the
    live Tetra self-locomotes in stt 4, which the plow model does not implement."""
    from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST as D
    assert O.in_regime(0.0, 0.0, 0.0, D - 0.001)
    assert not O.in_regime(0.0, 0.0, 0.0, D + 0.001)
    # 3D when a Y is supplied (`fopAcM_searchActorDistance2` is `abs2`), flat floor otherwise.
    assert not O.in_regime(0.0, 0.0, 0.0, D - 0.001, ly=0.0, ty=30.0)


# --------------------------------------------------------------------------- the terminal

def test_terminal_moving_is_the_cheap_scalar_half_of_rule_3():
    """Rule 3's per-frame form is deliberately just "moving" (session 65): the s64 measurement
    falsified the old 180-snap predicate (the negation flips travel AND the speed sign so they
    cancel, and it MIRRORS the entry speed), so the beams keep only the scalar a resting Link
    fails -- the conversion has nothing to mirror from rest -- and the EXACT bar is the escape
    atom (`escape_ready`), probed on winners."""
    ebs = O.terminal_moving(-25.7)
    assert ebs['speed'] == pytest.approx(25.7) and ebs['ready'], \
        "an EBS backslide is just as much moving as a forward walk"
    assert O.terminal_moving(26.0)['ready']
    # At rest nothing is ready -- this is the near-rest arrival the s44-s51 endgame was built
    # around, and the rule that retires it.
    assert not O.terminal_moving(0.0)['ready']


def test_escape_ready_is_the_atom_run_for_real_and_fires_off_the_hot_terminal(env):
    """Rule 3 EXACT: `escape_ready` runs the s65 escape atom off the terminal state and reads the
    acceptance off the measurement (`away_walk.fires`) -- l_ok, dips within budget, receding at
    the walk cap -- plus the probed residual the terminal targeting undershoots by. Gated on the
    same synthetic hot terminal the atom's own gates use."""
    from harness.tetrapush import full_herd as FH
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    # ``snap_camera``: the bed carries the camera the last roll pays for (s73) -- at its inherited
    # csangle the atom's L locks in every variant, because no roll ever steered the camera for it
    node = FH.synthetic_hot_arrival(env, hl, coord_idx=287, d_short=0.0, feet=64.0, snap_camera=True)
    term = O.escape_ready(node['run'], hl)
    assert term['ready'], "the atom fires from the hot terminal (the s65 measurement)"
    assert term['l_ok'] and not term['followed']
    assert term['dips'] <= AW.DIP_BUDGET and term['rec17_f'] is not None
    # the residual is the probe's own measurement -- the terminal targeting's undershoot
    assert term['resid'] == pytest.approx(term['atom']['resid'])
    assert 25.0 < term['resid'] < 60.0 and abs(term['resid_lat']) < 10.0
    # and the state the atom cannot fire from reads not-ready with the atom attached or absent
    spent = FH.synthetic_frozen_arrival(env, hl, coord_idx=287, momentum='rest')
    assert not O.escape_ready(spent['run'], hl)['ready'], \
        "a near-rest terminal has no EBS to convert: the exact rule 3 rejects it"


def test_the_recorded_human_window_already_satisfies_the_terminal_rule(env, walls):
    """Sanity that the terminal gate is not accidentally impossible: the human's 2-cycle window
    ends mid-roll at speedF 26 travelling away from Tetra, which passes. (It fails the objective
    overall only because it is a WINDOW -- it has not finished the herd.)"""
    from harness.tetrapush import search as S
    rec = S.rollout_recorded(env, upto=45)
    sc = O.score_plan(env, rec['rows'], walls=walls)
    assert sc['terminal_ok'], "the oracle's own terminal fails the terminal rule"
    assert sc['wall_ok'] and sc['regime_ok'], "the oracle should be wall-free and in regime"
    assert not sc['complete'], "the 2-cycle window does not reach a coord"
    assert not sc['within_budget'], "an unfinished plan must not read as inside the frame budget"


# --------------------------------------------------------------------------- the locked plan

@pytest.fixture(scope="module")
def node1_rows(env):
    """Node 1's locked 241-frame plan replayed on today's model."""
    fix = json.load(open(os.path.join(_FX, 'courtyard_node1_console.json')))
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    with warnings.catch_warnings():          # the FreeRun follow guard fires; that IS the finding
        warnings.simplefilter('ignore')
        return [run.step(d) for d in fix['log']]


def test_the_locked_plan_fails_the_objective_on_three_independent_rules(env, walls, node1_rows):
    """Node 1's plan is the artefact every session since 52 has been measuring against, and under
    the session-60 objective it is not a starting point -- it breaks three rules at once.

    Pinned so that (a) the walls finding cannot be lost again: the sim walks Link straight THROUGH
    the courtyard back wall, which no amount of FP work would ever have closed, and (b) nobody
    re-adopts the plan or its near-rest endgame by accident."""
    sc = O.score_plan(env, node1_rows, walls=walls)
    assert not O.verdict(sc)
    assert not sc['wall_ok'] and sc['wall_margin'] < -1.0, \
        "the locked plan no longer violates the walls -- re-derive the s60 finding"
    assert sc['left_regime_at'] is not None and sc['left_regime_at'] < 100, \
        "the plan should leave the stt-3 regime well before the first open console sample"
    assert not sc['terminal_ok'] and sc['terminal']['speed'] == 0.0, \
        "the plan should end at REST -- the near-rest arrival the new terminal rule retires"
    assert sc['timeloss'] > O.TIMELOSS_BUDGET


def test_replay_and_score_reproduces_the_score_of_the_rows_it_replays(env, walls, node1_rows):
    """`replay_and_score` is what a session quotes: a plan's raw input log in, the verdict out, with
    no search node in between (a node carries its beam's own prunes; this re-derives everything from
    state 2 on the 0-ULP forward model). It must agree exactly with scoring the same rows."""
    fix = json.load(open(os.path.join(_FX, 'courtyard_node1_console.json')))
    direct = O.score_plan(env, node1_rows, walls=walls)
    replayed = O.replay_and_score(env, fix['log'], walls=walls)
    for k in ('frames', 'placement_dist', 'wall_margin', 'wall_margin_at', 'left_regime_at',
              'bound', 'herd', 'complete', 'terminal_ok'):
        assert replayed[k] == direct[k], "replay disagreed on %s" % k


def test_the_locked_plan_leaves_the_regime_before_the_first_open_console_sample(node1_rows):
    """Localisation, kept next to `test_node1_console.py`'s frontier: the regime break is at frame
    83 and the wall break at 84, ~16 frames BEFORE n=100. The gate reads the frontier at 100 only
    because that is the next sample the console measured, not because that is where it opens."""
    first_out = next(i + 1 for i, r in enumerate(node1_rows)
                     if not O.in_regime(r['sim_link'][0], r['sim_link'][1],
                                        r['sim_tetra'][0], r['sim_tetra'][1]))
    first_wall = next(i + 1 for i, r in enumerate(node1_rows)
                      if O.wall_margin(r['sim_link'][0], r['sim_link'][1],
                                       r['sim_tetra'][0], r['sim_tetra'][1])['margin'] <= 0.0)
    assert (first_out, first_wall) == (83, 84), \
        "the two scope breaks moved (regime %d, wall %d) -- re-derive before trusting" % (
            first_out, first_wall)


@pytest.mark.slow
def test_the_shipped_plan_passes_the_whole_objective_from_its_input_log_alone(env):
    """**MILESTONE 2, as a regression gate: the first plan that passes `objective.verdict`**
    (session 73).

    `fixtures/courtyard_plan_s73.json` is a complete state-2 input log -- a 3-cycle herd whose last
    roll steers the camera into the escape's own snap window -- replayed here on a fresh self-contained
    `FreeRun` and scored by the acceptance test itself. Every one of Dereck's four rules: Tetra lands
    **0.4321 u** from genuine coord 274 (inside `PLACEMENT_BAND`), in **75 frames** against a floor of
    73 (timeloss +2, inside `TIMELOSS_BUDGET`), with the escape atom firing for real (rule 3 exact),
    both actors clear of the walls and inside the plow regime.

    Two things it pins beyond the verdict. The log ENDS AT THE ARRIVAL, because `score_plan` probes
    the atom itself -- appending the atom's own frames double-counts and re-probes from a separated
    state (s72 read pd 21.5 u that way on a plan whose real score is sub-unit). And the atom's
    ``cs_bill`` is **0**: the csangle it runs at is the one the plan's own last roll delivered, not a
    commanded one, which is what makes the score a REPLAY rather than a claim (s65-s72 scored every
    atom at a camera state 91-114 deg off live -- see `away_walk.snap_bill`).

    ``atom_kw`` is the fixture's own, because a plan built on a swept atom must be scored against the
    escape it plans (`score_plan`'s docstring): with the default single-flip atom the same log reads
    77 frames and pd 4.48, which is a different escape, not a worse plan."""
    import json
    import os
    from harness.tetrapush import full_herd as FH
    from harness.tetrapush.reposition import HerdLine
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', 'courtyard_plan_s73.json')
    with open(path) as fh:
        rec = json.load(fh)
    hl = HerdLine.from_env(env)
    rows = seeds.load_placements()[0]
    kw = dict(rec['atom_kw'])
    kw['rotate_offs'] = tuple(kw['rotate_offs'])
    kw['thread'] = O.placement_thread(hl, rows)
    sc = O.replay_and_score(env, rec['log'], hl=hl, placements=rows, atom_kw=kw)

    assert O.verdict(sc) is True
    assert sc['complete'] and sc['placement_dist'] <= O.PLACEMENT_BAND
    assert sc['frames'] == rec['scored']['frames']
    assert sc['timeloss'] == rec['scored']['timeloss'] <= O.TIMELOSS_BUDGET
    assert sc['placement_dist'] == pytest.approx(rec['scored']['placement_dist'], abs=1e-9)
    assert sc['terminal_ok'] and sc['wall_ok'] and sc['regime_ok'] and sc['within_budget']
    # the escape runs at the camera the plan itself delivered: nothing commanded, nothing unpaid
    assert sc['terminal']['atom']['cs_bill'] == 0
    assert FH.CO_RADII_BAR - FH._centre_feet(sc['terminal']['atom']['run']) <= 0.0
    # and the herd ends at the SLAM: the scored frame count is the log plus the atom's own separation
    assert sc['frames'] == len(rec['log']) + sc['atom_frames']
