"""THE HERD PRICE OF A PLACEMENT (session 105) -- the accounting, the screen, and the two negatives.

Gates `harness/tetrapush/herd_price.py` and the `entry_fan.base_core` seed fix, plus the structural
findings in knowledge/strategy/herd-price-of-a-placement.md. Everything here reads TRACKED fixtures
only (`courtyard_plan_s73_console.json`, `courtyard_walk_budget_s104.json`) -- the wider 211/56
placement populations live in gitignored `_generated/`, so the pinned rows are what a gate can hold.
"""
import math
import warnings

import pytest

from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES
from harness.tetrapush import herd_price as HP
from harness.tetrapush import objective as O
from harness.tetrapush import seeds as SD

pytestmark = pytest.mark.filterwarnings("ignore")

BANKED_TOTAL = 101          # arrival 78 + the delivered clip's plan_cost 23
DELIVERED_PLAN_COST = 23


@pytest.fixture(scope="module")
def env():
    return SD.load_env()


@pytest.fixture(scope="module")
def seed():
    return ES.console_seed()


@pytest.fixture(scope="module")
def arrival_run():
    """The console log replayed on the wired 0-ULP FreeRun -- Link AT the arrival."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run, _ = ES.continue_walk([])
    return run


# --------------------------------------------------------------------------- the accounting

def test_the_arrival_is_the_whole_log_not_the_frame_she_freezes_on(seed):
    """`plan_cost` counts from the ARRIVAL, and the fan replays the whole log to get there."""
    assert seed['n_scored'] == 75            # where TETRA stops
    assert seed['n_last'] == 78              # where the walk fan starts
    assert len(seed['log']) == 78
    assert HP.arrival_frames(seed) == 78
    assert HP.atom_tail(seed) == 3


def test_the_delivered_plans_own_addends_sum_to_the_arrival():
    """herd 71 + escape atom 7 == the 78-frame log, so the banked deliverable is 78 + 23 = 101."""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'fixtures', 'courtyard_plan_s73_console.json')
    plan = json.load(open(p))['plan']
    assert plan['herd_frames'] + plan['atom_frames'] == 78
    assert plan['scored_frames'] == plan['herd_frames'] + plan['freeze_f'] == 75
    assert HP.total_frames(78, DELIVERED_PLAN_COST) == BANKED_TOTAL


def test_the_sustained_rate_is_the_delivered_plans_own(env, seed):
    """939.4737 u in 75 frames = 12.5263 u/f -- 96.4% of the ceiling, so the ceiling is a fair
    asymptote and this is what a real plan achieved."""
    t2 = env['cyl'][0]['tetra']['pos']
    r = HP.sustained_rate((t2[0], t2[2]), seed)
    assert r == pytest.approx(12.5263, abs=1e-4)
    assert 0.960 < r / O.PUSH_CEILING < 0.968


# --------------------------------------------------------------------------- the trajectory price

def test_the_console_placement_is_its_own_frame_at_zero_miss(env, seed):
    """The control for `trajectory_price`: the placement the delivered plan lands on must project
    onto its own curve at the frame it stops, with no lateral miss."""
    traj = HP.console_trajectory(env, seed['log'])
    k, lat = HP.project_on_trajectory(traj, seed['tetra'])
    assert k == pytest.approx(75.0, abs=1e-9)
    assert lat == pytest.approx(0.0, abs=1e-9)


def test_she_is_frozen_from_the_scored_frame_on(env, seed):
    """Frames 76-78 are Link's escape, not more herding -- which is what makes the atom tail a
    constant that every candidate pays rather than a term that varies with the placement."""
    traj = HP.console_trajectory(env, seed['log'])
    tail = [(x, z) for n, x, z in traj if n >= seed['n_scored']]
    assert all(p == tail[0] for p in tail)


# --------------------------------------------------------------------------- the screen

def test_link_co_centre_leads_his_feet_at_the_arrival(arrival_run):
    """The screen has to run on the exec Co centre: it leads the feet by 21.253 u here, which is
    more than the thing being screened for."""
    lk = arrival_run.link
    cx, cz = HP.link_co_centre(arrival_run)
    assert math.hypot(cx - lk.pos_x, cz - lk.pos_z) == pytest.approx(21.253, abs=1e-3)


def test_the_console_placement_clears_the_arrival_screen(arrival_run, seed):
    assert HP.contact_at_arrival(HP.link_co_centre(arrival_run), seed['tetra']) == 0.0


def test_every_pinned_walk_budget_row_clears_the_arrival_screen(arrival_run):
    """The s104 fixture's 14 verified rows are all statically occupiable at the console arrival, so
    the screen costs the verified set nothing -- it trims the wider population, from the cheap end."""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'fixtures', 'courtyard_walk_budget_s104.json')
    centre = HP.link_co_centre(arrival_run)
    rows = [r for rung in json.load(open(p))['rungs'] for r in rung['rows']]
    assert len(rows) == 14
    assert all(HP.contact_at_arrival(centre, r['tetra']) == 0.0 for r in rows)


def test_a_placement_inside_the_co_cylinder_is_caught(arrival_run):
    """The screen's positive control: put her ON Link's Co centre and it must report depth."""
    centre = HP.link_co_centre(arrival_run)
    assert HP.contact_at_arrival(centre, centre) > 0.0


# ------------------------------------------------------ depth and frames select disjoint placements

def test_the_verified_rows_are_the_expensive_ones(env, seed):
    """The 14 rows s104 verified are the DEEPEST, and depth is anti-correlated with frames here: not
    one of them beats the banked 101 under the trajectory price, because they sit 23-48 u off the
    delivered curve. This is the reason the verification effort has to be re-pointed."""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'fixtures', 'courtyard_walk_budget_s104.json')
    traj = HP.console_trajectory(env, seed['log'])
    worst_lat = 0.0
    for rung in json.load(open(p))['rungs']:
        for r in rung['rows']:
            frames, _k, lat = HP.trajectory_price(traj, seed, r['tetra'])
            assert frames + rung['plan_cost'] > BANKED_TOTAL
            worst_lat = max(worst_lat, lat)
    assert worst_lat > 20.0          # off the curve, which is where the two prices disagree


# --------------------------------------------------------------------------- the base_core seed fix

def test_base_core_replays_its_seeds_own_log(seed):
    """The session-105 fix. `base_core` used to read ``seed['log']`` for the HOLD but replay
    `console_seed`'s log regardless, so every cloud `entry_reach.walk_clouds` measured with a
    ``seed=`` was the CONSOLE arrival's, silently. A truncated seed must now arrive somewhere else."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _core_a, run_a = EF.base_core(0)
        short = dict(seed, log=seed['log'][:60])
        _core_b, run_b = EF.base_core(0, seed=short)
    assert (run_a.link.pos_x, run_a.link.pos_z) == (seed['link'][0], seed['link'][1])
    assert math.hypot(run_b.link.pos_x - run_a.link.pos_x,
                      run_b.link.pos_z - run_a.link.pos_z) > 1.0


def test_the_default_seed_path_is_bit_identical(seed):
    """...and the fix is inert at the default, because the log it now passes IS the one that was
    being replayed. 0-ULP, never a tolerance (`[[zero-ulp-tests-only]]`)."""
    import struct
    hold = dict(seed['log'][-1], buttons=0)

    def sig(run):
        lk = run.link
        return (struct.pack('<f', lk.pos_x), struct.pack('<f', lk.pos_z), lk.facing & 0xFFFF,
                struct.pack('<f', lk.speedF), lk.state & 0xFF, run.csangle & 0xFFFF,
                struct.pack('<f', run.tx), struct.pack('<f', run.tz))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for n0 in (0, 2):
            a, _ = ES.continue_walk([hold] * n0)
            b, _ = ES.continue_walk([hold] * n0, log=seed['log'])
            assert sig(a) == sig(b)


# --------------------------------------------------------------------------- the herd is quantized

def test_the_delivered_herd_cannot_be_truncated_before_its_last_roll_exits(env, seed):
    """The escape needs the state the last roll's exit leaves, so the herd's frame count is quantized
    by its cycle structure: "70.6 herd frames" is not a plan this herd can express.

    A CHEAP form of the session-105 measurement -- that one ran the full 672-variant knob grid at
    every k in 62..78 and found 0 firing before frame 71. This runs the shipped default grid (8
    variants) at one k on each side, which is enough to catch a regression in either direction: k=70
    must stay dead and k=71 must stay alive (the control -- a pass where nothing fires anywhere
    proves nothing about the herd)."""
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env)
    fired = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k in (70, 71):
            run = SD.make_freerun(env)
            run.pre_seed_input(SD.dtm_input_at(env)(0))
            for inp in seed['log'][:k]:
                run.step(inp)
            res = AW.probe(run, hl, csangle='live')
            fired[k] = bool(res is not None and AW.fires(res))
    assert fired[71], "the control failed: nothing fires at the herd's own end"
    assert not fired[70], "a truncated herd now fires -- the quantization claim needs re-measuring"
