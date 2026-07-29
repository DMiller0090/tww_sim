# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""The away-walk escape atom (session 65): the herd's terminal reversal, gated on the
synthetic hot terminal (`synthetic_hot_arrival`, coord 287). See `harness/tetrapush/away_walk.py`
for the mechanics; these pin the measured behaviour so a model change that moves the escape
names itself.
"""
import warnings

import pytest

from harness.tetrapush import seeds
from harness.tetrapush import full_herd as FH
from harness.tetrapush import away_walk as AW
from harness.tetrapush.reposition import HerdLine

warnings.simplefilter('ignore')


@pytest.fixture(scope='module')
def bed():
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    node = FH.synthetic_hot_arrival(env, hl, coord_idx=287, d_short=0.0, feet=64.0)
    return node['run'], hl


@pytest.fixture(scope='module')
def best(bed):
    run, hl = bed
    return AW.probe(run, hl, csangles=(16384, 24576, 32768))


def test_the_slam_turn_reverses_motion_and_freezes_tetra_immediately(best):
    """The escape's whole point: the slam-turn reverses Link's ground motion in one acted frame,
    which stops the contact push the same frame -- Tetra's residual is ONE pipeline push
    (~13.5 u), not the 27-80 u any brake-through escape leaves."""
    assert best['reversed_f'] is not None and best['reversed_f'] <= 3
    assert best['freeze_f'] == 1
    assert best['resid'] < 15.0
    # frozen means frozen: her displacement never grows after the freeze
    tres = [r['tres'] for r in best['rows']]
    assert max(tres) == pytest.approx(tres[0], abs=1e-6)


def test_the_escape_respects_dereck_s_rules(best):
    """No A press anywhere (the atom never emits one), no L acting with Tetra in the front cone,
    no lock acquired, and the follow shell (dist <= 230) never trips."""
    assert best['l_ok'] is True
    assert best['followed'] is False
    assert all(not (d['buttons'] & 0x100) for d in best['log'])


def test_the_escape_delivers_link_into_the_entry_region(best):
    """Herding complete -> the atom carries Link to the roll-from region
    (`seeds.ENTRY_ROLL_POS`), where the Link-only 2D planners (`walk_to_entry` /
    `plan_land.reach_precise`) take over. On the bed the closest approach is ~13 u."""
    assert min(r['d_e'] for r in best['rows']) < 20.0


def test_the_measured_dip_floor_is_pinned(best):
    """Dereck's s65 bar: > `DIP_BUDGET` (1) post-separation frames under 17 u = unoptimal,
    expected 0. THE MODEL CANNOT REACH 0 from the hot terminal (every reversal primitive
    crosses the slow zone -- away_walk.py docstring). This pins the measured compliant floor
    as a CEILING so a model regression names itself; if a change ever takes it to <=
    `DIP_BUDGET`, the objective's terminal rule should be wired to the atom and this
    expectation updated -- that is an improvement, not a failure of the model."""
    assert len(best['dips']) <= 14
