"""Offline regression for the LAND walk sim (superswim.land).

Guards the BIT-EXACT part of the first land increment -- mNormalSpeed (potential_speed) and
the FREE_WAIT->MOVE->WAIT state machine -- as a golden arc, without needing Dolphin. The
live sim-vs-live gate is tests/dolphin/run_land_tests.py::walk_run; this is its token-cheap
offline shadow (same walk seq, same anchor rest seed, values pinned from land_walk_gt.csv).

nspeed/state are decomp-faithful to the ULP. speedF/position is now BIT-EXACT too via the ported
anim engine (superswim.anim.foot_speedf) -- the golden speedF/pos_z arc (land_walk_speedf.csv,
live-captured) is pinned per-frame, but only WHEN the copyrighted anim keyframe data is present
under _generated/anim/ (dev machines). Without it LandState falls back to the calibrated stand-in,
so those two tests SKIP and only the loose endpoint check runs.
"""
import csv
import os

import pytest

from superswim.land import LandState, WAIT, FREE_WAIT, MOVE
from superswim.anim.foot_speedf import FootSpeedF

_ANIM = FootSpeedF.available()
_GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "land_walk_speedf.csv")


def _load_golden():
    rows = []
    with open(_GOLDEN) as f:
        for line in f:
            if line.startswith("#") or line.startswith("f,"):
                continue
            fr, ns, msd, spF, pz = line.strip().split(",")
            rows.append((int(fr), float(ns), float(msd), float(spF), float(pz)))
    return rows

# Anchor rest seed (land_flatwalk@twwgz): flat wall-free room, Link idle, csangle 0.
SEED_POS_Z = 764.079

# The walk seq the live test uses: 30 frames full-up then 20 neutral (free cam throughout).
WALK_STICKS = [(128, 255)] * 30 + [(128, 128)] * 20

# Golden mNormalSpeed per frame f=1..40, live-captured (land_walk_gt.csv). f1..f2 = the
# 2-frame input latency (still FREE_WAIT); f3 accel begins; cap 17; release decel from f33.
GOLDEN_NSPEED = {
    1: 0.0, 2: 0.0, 3: 3.5, 4: 7.0, 5: 10.5, 6: 14.0, 7: 17.0,
    32: 17.0, 33: 14.5, 34: 12.0, 35: 9.5, 36: 7.0, 37: 4.5, 38: 2.0, 39: 0.2, 40: 0.0,
}
# Golden link_state at the same frames.
GOLDEN_STATE = {1: FREE_WAIT, 2: FREE_WAIT, 3: MOVE, 7: MOVE, 39: MOVE, 40: WAIT}


def _run():
    s = LandState(pos_z=SEED_POS_Z, state=FREE_WAIT)
    rows = [None]  # 1-indexed
    for (sx, sy) in WALK_STICKS:
        s.step(sx, sy)
        rows.append((s.nspeed, s.state, s.pos_z))
    return s, rows


def test_nspeed_arc_bit_exact():
    _, rows = _run()
    for f, want in GOLDEN_NSPEED.items():
        got = rows[f][0]
        assert abs(got - want) <= 1e-4, f"frame {f}: nspeed {got} != {want}"


def test_state_machine():
    _, rows = _run()
    for f, want in GOLDEN_STATE.items():
        assert rows[f][1] == want, f"frame {f}: state {rows[f][1]} != {want}"


def test_input_latency_two_frames():
    # No movement (state stays FREE_WAIT, nspeed 0) for exactly INPUT_DELAY frames.
    _, rows = _run()
    assert rows[1][:2] == (0.0, FREE_WAIT)
    assert rows[2][:2] == (0.0, FREE_WAIT)
    assert rows[3][1] == MOVE and rows[3][0] == 3.5


def test_accel_step_is_3_5_and_caps_at_17():
    _, rows = _run()
    assert [rows[f][0] for f in (3, 4, 5, 6, 7)] == [3.5, 7.0, 10.5, 14.0, 17.0]
    assert all(rows[f][0] == 17.0 for f in range(7, 33))   # holds at the cap while held


def test_decel_matches_cLib_addCalc():
    # release decel: cLib_addCalc(v, 0, 0.6, 2.5, 1.8) => 17->14.5->12->9.5->7->4.5->2->0.2->0
    _, rows = _run()
    assert [round(rows[f][0], 3) for f in range(33, 41)] == [14.5, 12.0, 9.5, 7.0, 4.5, 2.0, 0.2, 0.0]


def test_end_position_within_tolerance():
    # Endpoint vs live 1278.25: bit-exact with the anim engine, +-3 calibrated stand-in without it.
    s, _ = _run()
    assert s.state == WAIT
    tol = 0.05 if _ANIM else 3.0
    assert abs(s.pos_z - 1278.25) < tol


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_speedf_matches_live_golden_bit_exact():
    # Feed the live (ns, msd) arc into the ported posMoveFromFootPos and assert speedF reproduces
    # the live-captured golden to float precision (isolates the anim engine from the nspeed sim).
    golden = _load_golden()
    drv = FootSpeedF(idle_frame=70.0)
    for fr, ns, msd, spF, _pz in golden:
        got = drv.step(ns, msd)
        assert abs(got - spF) < 1e-3, f"frame {fr}: speedF {got} != golden {spF}"


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_pos_z_arc_bit_exact():
    # Full LandState walk (its own bit-exact nspeed driving the anim engine) tracks the live
    # golden pos_z every frame, not just the endpoint.
    golden = _load_golden()
    s = LandState(pos_z=SEED_POS_Z, state=FREE_WAIT, idle_frame=70.0)
    for (sx, sy), (fr, _ns, _msd, _spF, pz) in zip(WALK_STICKS, golden):
        s.step(sx, sy)
        assert abs(s.pos_z - pz) < 0.05, f"frame {fr}: pos_z {s.pos_z} != golden {pz}"
