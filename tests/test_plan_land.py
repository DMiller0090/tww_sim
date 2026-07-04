"""Offline regression for the LAND input planner (superswim.plan_land) -- milestone 1.

Guards the geometry primitives (world bearing <-> full-deflection stick inverse) and the
STRAIGHT-WALK reach: given an init LandState + a world target (x, z), the produced input seq
brings Link to REST within tolerance of the target. Position is bit-exact with the ported foot
anim engine present (tight pins gated on it, like test_land.py); the loose reach bound always runs.

Anchor seed = land_flatwalk@twwgz (flat wall-free room, Link idle at pos_z 764.079, facing +z,
csangle 0) -- the same rest seed the live land tests use.
"""
import math

import pytest

from superswim.land import LandState, FREE_WAIT, WAIT
from superswim.plan_land import (world_angle_s16, stick_for_bearing, dist2d, reach_straight,
                                 reach_precise)
from superswim.sim import _deadzone
import math
from superswim.anim.foot_speedf import FootSpeedF

_ANIM = FootSpeedF.available()

SEED = dict(pos_z=764.079, pos_x=0.0, facing=0, travel=0, csangle=0, state=FREE_WAIT,
            nspeed=0.0, idle_frame=70.0)


def _seed():
    return LandState(**SEED)


# --- geometry primitives (no sim, no anim dep) ---------------------------------------------

def test_world_angle_s16_cardinals():
    # travel is s16 measured FROM +z TOWARD +x: 0 = +z, 0x4000 = +x, 0x8000 = -z, 0xC000 = -x.
    assert world_angle_s16(0, 100) == 0
    assert world_angle_s16(100, 0) == 0x4000
    assert world_angle_s16(0, -100) == 0x8000
    assert world_angle_s16(-100, 0) == 0xC000


def test_stick_for_bearing_cardinals():
    # With a frozen camera (csangle 0) the inverse-stick points the walk at the world bearing:
    # +z = full up, +x = full left, -z = full down (matches the anchor's facing/camera).
    assert stick_for_bearing(world_angle_s16(0, 100), 0) == (128, 255)
    assert stick_for_bearing(world_angle_s16(100, 0), 0) == (1, 128)
    assert stick_for_bearing(world_angle_s16(0, -100), 0) == (128, 1)


def test_stick_for_bearing_roundtrips_through_sim():
    # Feed the inverse-stick into the real stick layer and confirm the walk want-target m34E8
    # lands on the requested bearing (within one dead-zoned-stick quantum).
    for bearing_deg in (0, 30, 90, 150, 210, 300):
        th = int(round(bearing_deg / 360.0 * 65536.0)) & 0xFFFF
        sx, sy = stick_for_bearing(th, 0)
        s = _seed()
        s._set_stick_data(sx, sy)
        err = abs(((s.target - th + 32768) % 65536) - 32768)
        # dead-zone-corrected inverse -> bearing preserved to integer-stick rounding (~1 deg = 182 s16)
        assert err < 200, f"bearing {bearing_deg}: m34E8 {s.target} vs {th} (err {err})"


# --- straight-walk reach (bit-exact position gated on anim data) ----------------------------

def _reach_bound():
    # Whole-frame release granularity limits how close a walk-then-coast can rest to a target;
    # ~15u covers every probed case with the anim engine, looser without it.
    return 15.0 if _ANIM else 20.0


def test_reach_straight_ahead():
    # Target dead ahead (+z): pure full-up walk then coast to rest near it.
    s = _seed()
    r = reach_straight(s, 0.0, 1200.0)
    assert r['end'].state in (WAIT, FREE_WAIT)
    assert r['resting_dist'] < _reach_bound()
    assert abs(r['end'].pos_x) < 1.0                       # no lateral drift on a straight walk


def test_reach_far_straight_is_sub_unit():
    # A far straight target gives fine release positioning -> sub-unit resting distance.
    s = _seed()
    r = reach_straight(s, 0.0, 2000.0)
    assert r['end'].state in (WAIT, FREE_WAIT)
    if _ANIM:
        assert r['resting_dist'] < 1.0
    else:
        assert r['resting_dist'] < 5.0


@pytest.mark.parametrize("tx,tz", [(300.0, 1400.0), (600.0, 1400.0)])
def test_reach_angled_target(tx, tz):
    # Off-axis target: the live-bearing re-aim curves the main stick to home in (no orbit) and
    # rests within tolerance. Both axes land near the target.
    s = _seed()
    r = reach_straight(s, tx, tz)
    assert r['end'].state in (WAIT, FREE_WAIT)
    assert r['resting_dist'] < _reach_bound()
    assert dist2d(r['end'], tx, tz) == pytest.approx(r['resting_dist'])
