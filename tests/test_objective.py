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

def test_turnaround_ready_accepts_a_moving_ebs_and_rejects_rest():
    """Dereck's terminal: Link must still be MOVING at the placement so the 1-frame 180 carries him
    away from Tetra. An EBS backslide has a large NEGATIVE speedF with the facing 0x8000 from
    travel -- just as much "moving" as a forward walk -- so the test is on the ground-velocity
    magnitude and on which way it points after the snap, never on the sign of `speedF`."""
    # Link at the origin, Tetra 100 u in +z. Facing +z (0) while backsliding = travelling -z, so a
    # 180 turns him to +z -- straight INTO her: not ready.
    into = O.turnaround_ready(-25.7, 0x0000, 0.0, 0.0, 0.0, 100.0)
    assert into['speed'] == pytest.approx(25.7) and into['away'] < 0.0 and not into['ready']
    # Facing -z while backsliding = travelling +z (toward her); the 180 sends him away: ready.
    away = O.turnaround_ready(-25.7, 0x8000, 0.0, 0.0, 0.0, 100.0)
    assert away['away'] == pytest.approx(25.7, abs=1e-3) and away['ready']
    # At rest nothing is ready, whatever the facing -- this is the near-rest arrival the s44-s51
    # endgame was built around, and the rule that retires it.
    assert not O.turnaround_ready(0.0, 0x8000, 0.0, 0.0, 0.0, 100.0)['ready']


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
