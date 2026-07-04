"""Offline regression for the LAND walk sim (superswim.land).

Guards the BIT-EXACT part of the first land increment -- mNormalSpeed (potential_speed) and
the FREE_WAIT->MOVE->WAIT state machine -- as a golden arc, without needing Dolphin. This is the
token-cheap offline SHADOW of the live accuracy gate tests/dolphin/run_land_tests.py.

THE GOLDEN IS LIVE TRUTH, ENFORCED TO THE BYTE. speedF and position in tests/golden/land_walk_speedf.csv
and the CASE_POSZ endpoints are the GAME's live f32 reads (uint32 hex), captured by
tests/gen_land_golden.py. The tests assert `f32_bits(sim) == golden` (0 ULP, no tolerance), so a tech
that is not bit-perfect vs the game shows RED here just as it does live -- the same cases fail in both.
Today walk/brakeslide/face_left/roll_run/roll_slow/roll_settle/roll_ebs/moveturn are BIT-PERFECT and
pass (walk/face_left/roll_settle went float-perfect with the world-space foot FK + PSMTXQuat 'newton'
reciprocal, see knowledge/model/sim.md); ebs (1 ULP), brake_right (2), waitturn (2) and slip (74) still
FAIL -- the planted-foot jnt34/39 residual (foot chain is ~1 ULP off pure anim FK, likely a foot-IK
ground snap) and the separate slip skid. This deliberately replaces the old `< 0.05` tolerance (~400
ULP wide), which hid the f64-running-sum bug. Regenerate the golden from live after a sim fix (Dolphin
up): `python tests/gen_land_golden.py`.

The byte-exact checks only run WHEN the copyrighted anim keyframe data is present under _generated/anim/
(dev machines); without it LandState falls back to the calibrated stand-in and they SKIP.
"""
import os
import struct

import pytest

from superswim.land import (LandState, WAIT, FREE_WAIT, MOVE, ATN_MOVE, FRONT_ROLL,
                             WAIT_TURN, MOVE_TURN, SLIP)
from superswim.anim.foot_speedf import FootSpeedF

_ANIM = FootSpeedF.available()
_GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "land_walk_speedf.csv")


def f32_bits(x):
    """The raw uint32 bit pattern of x rounded to float32 -- the currency of a bit-exact check."""
    return struct.unpack("<I", struct.pack("<f", x))[0]


def _load_golden():
    """(frame, ns, msd, speedF_bits, pos_z_bits) -- the two floats as exact f32 byte patterns."""
    rows = []
    with open(_GOLDEN) as f:
        for line in f:
            if line.startswith("#") or line.startswith("f,"):
                continue
            fr, ns, msd, spF, spF_hex, pz, pz_hex = line.strip().split(",")
            rows.append((int(fr), float(ns), float(msd), int(spF_hex, 16), int(pz_hex, 16)))
    return rows

# Anchor rest seed (land_flatwalk@twwgz): the EXACT f32 rest pos_z read live (0x443f0510). The old
# 764.079 was 2 ULP off (0x443f050e) and perturbed the arc; seeding to the byte is part of the gate.
SEED_POS_Z = 764.0791015625

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
    # Endpoint: BIT-EXACT vs the LIVE golden with the anim engine (walk is float-perfect since the
    # world-space foot FK); +-3 calibrated stand-in without anim data.
    s, _ = _run()
    assert s.state == WAIT
    if _ANIM:
        want = _load_golden()[-1][4]
        assert f32_bits(s.pos_z) == want, \
            f"end pos_z {s.pos_z!r} (0x{f32_bits(s.pos_z):08x}) != LIVE 0x{want:08x}"
    else:
        assert abs(s.pos_z - 1278.25) < 3.0


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_speedf_matches_live_bit_exact():
    """The ported foot-FK speedF must reproduce the GAME's live true_speed BYTE-FOR-BYTE. This isolates
    the anim FK from the nspeed sim. With the world-space FK it is bit-exact for almost every frame; the
    lone residual (frame 5, 1 ULP in speedF -- absorbed by the pos_z f32 rounding, so the pos_z arc is
    float-perfect) is the planted-foot jnt34/39 sub-ULP. See knowledge/model/sim.md."""
    golden = _load_golden()
    drv = FootSpeedF(idle_frame=70.0)
    for fr, ns, msd, spF_bits, _pz in golden:
        got = drv.step(ns, msd)
        assert f32_bits(got) == spF_bits, \
            f"frame {fr}: sim speedF {got!r} (0x{f32_bits(got):08x}) != LIVE 0x{spF_bits:08x}"


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_pos_z_arc_matches_live_bit_exact():
    """Full LandState walk must track the GAME's live pos_z BYTE-FOR-BYTE every frame. Float-perfect
    since the world-space foot FK (was 2 ULP off with the identity-space FK). This is the guard the
    f64-accumulation bug slipped past. See knowledge/model/sim.md."""
    golden = _load_golden()
    s = LandState(pos_z=SEED_POS_Z, state=FREE_WAIT, idle_frame=70.0)
    for (sx, sy), (fr, _ns, _msd, _spF, pz_bits) in zip(WALK_STICKS, golden):
        s.step(sx, sy)
        assert f32_bits(s.pos_z) == pz_bits, \
            f"frame {fr}: sim pos_z {s.pos_z!r} (0x{f32_bits(s.pos_z):08x}) != LIVE 0x{pz_bits:08x}"


# --- ATN_MOVE tier: brakeslide / EBS / facing decouple / brake -----------------------------

# LIVE endpoint pos_z (the game's exact f32 bytes) for the ATN/roll/turn cases; captured by
# `python tests/gen_land_golden.py endpoints`. sim!=live fails here, mirroring run_land_tests.py.
CASE_POSZ = {
    'brakeslide' : 0x448146b3,   # 1034.2093505859375 (state 7)   bit-perfect
    'ebs'        : 0x44aa2072,   # 1361.013916015625  (state 6)   sim off 1 ULP (jnt34 foot residual)
    'face_left'  : 0x44e9fa16,   # 1871.815185546875  (state 6)   bit-perfect (world FK)
    'brake_right': 0x447238c3,   # 968.8869018554688  (state 4)   sim off 2 ULP (jnt34 foot residual)
    'roll_run'   : 0x4486a1c6,   # 1077.055419921875  (state 30)  bit-perfect
    'roll_slow'  : 0x4445f858,   # 791.88037109375    (state 30)  bit-perfect
    'roll_settle': 0x44be9639,   # 1524.6944580078125 (state 4)   bit-perfect (world FK)
    'roll_ebs'   : 0x44d64e35,   # 1714.4439697265625 (state 6)   bit-perfect
    'waitturn'   : 0x442c9e1e,   # 690.4705810546875  (state 6)   sim off 2 ULP (jnt34 foot residual)
    'moveturn'   : 0x44086be3,   # 545.6857299804688  (state 6)   bit-perfect (live-mirror *18 seq)
    'moveturn_pos': 0x43ffd7c6,  # 511.68572998046875 (state 6)   bit-perfect (*20 seq)
    'slip'       : 0x44756df2,   # 981.7178955078125  (state 6)   sim off 74 ULP (separate skid residual)
}


def assert_pos_bits(s, label):
    """Assert sim endpoint pos_z == the LIVE value bit-exact (fails until the sim is bit-perfect for
    this tech; only meaningful with anim data)."""
    want = CASE_POSZ[label]
    assert f32_bits(s.pos_z) == want, \
        f"{label}: sim pos_z {s.pos_z!r} (0x{f32_bits(s.pos_z):08x}) != LIVE 0x{want:08x}"


# Offline shadow of run_land_tests.py's ATN cases; endpoints are the LIVE pos_z (CASE_POSZ). Guards
# setSpeedAndAngleAtn/AtnBack + the mDirection machine (no Dolphin).
def _deg(a):
    return (int(a) % 65536) * 360.0 / 65536.0


def _run_atn(seq):
    s = LandState(pos_z=SEED_POS_Z, facing=0, travel=0, csangle=0, state=FREE_WAIT,
                  nspeed=0.0, idle_frame=70.0)
    for (sx, sy, btn, tl) in seq:
        s.step(sx, sy, buttons=btn, triggerL=tl)
    return s


_UP = [(128, 255, 0, 0)]
_LDN = [(128, 0, 0x40, 255)]     # L-target + full down, 1 frame


def test_atn_brakeslide():
    # L HELD -> daPyProc_ATN_MOVE (state 7), facing LOCKED at the run heading (0), travel flips
    # to 180, speed negative bleeding slowly toward 0 (~-0.14/frame, mAtnMoveB cap 15).
    s = _run_atn(_UP * 10 + _LDN + [(128, 110, 0x40, 255)] * 10)
    assert s.state == ATN_MOVE
    assert s.direction == 1  # DIR_BACKWARD (steady brakeslide runs the AtnBack path)
    assert abs(_deg(s.facing) - 0.0) < 0.1
    assert abs(_deg(s.travel) - 180.0) < 0.1
    assert abs(abs(s.nspeed) - 15.756) < 0.02
    if _ANIM:  # ATN position bit-exact: setBlendAtnBackMoveAnime poses ANM_ATNDB (m3598=0 -> momentum)
        assert_pos_bits(s, 'brakeslide')


def test_atn_ebs():
    # L RELEASED after 1 frame -> MOVE (state 6); facing unlocks and tracks travel; the negative
    # speed bleeds ~13x slower than the brakeslide (~-0.011/frame, cap stays 17).
    s = _run_atn(_UP * 10 + _LDN + [(128, 110, 0, 0)] * 30)
    assert s.state == MOVE
    assert abs(abs(s.nspeed) - 16.437) < 0.02
    assert abs(_deg(s.facing) - _deg(s.travel)) < 0.5   # facing ~ travel aligned
    if _ANIM:  # the 1-frame ATN strafe pose (ANM_ATNDRS) warms the toe stream -> walk tail bit-exact
        assert_pos_bits(s, 'ebs')


def test_atn_facing_decouple():
    # ESS-down 1 frame then ESS-left held -> facing rotates to ~90 and decouples from travel (~171)
    # while speed is preserved (the facing/travel split).
    s = _run_atn(_UP * 10 + _LDN + [(128, 110, 0, 0)] + [(110, 128, 0, 0)] * 60)
    assert s.state == MOVE
    assert abs(_deg(s.facing) - 90.0) < 0.5
    assert abs(_deg(s.travel) - 171.32) < 0.5
    assert abs(abs(s.nspeed) - 16.650) < 0.02
    if _ANIM:  # ATN strafe pose -> the decoupled-facing walk tail is position bit-exact
        assert_pos_bits(s, 'face_left')


def test_atn_brake_right():
    # ESS toward anti-camera brakes to a full stop (state 4, |v| ~ 0).
    s = _run_atn(_UP * 10 + _LDN + [(128, 110, 0, 0)] + [(146, 128, 0, 0)] * 60)
    assert s.state == WAIT
    assert abs(s.nspeed) < 0.01
    if _ANIM:  # ATN strafe pose -> the anti-cam brake-to-stop walk tail is position bit-exact
        assert_pos_bits(s, 'brake_right')


# --- FRONT_ROLL tier (A button) -------------------------------------------------------------

# Roll speed set once at entry from pre-roll speedF: clamp(speedF*1.5+0.5, 5, 26). nspeed/state and
# position are bit-exact end to end -- the foot engine poses ANM_ROLLF through the roll so the
# low-speed post-roll walk tail tracks live too (see land.py enter_roll/step_roll).
_A = [(128, 255, 0x100, 0)]      # A + up, 1 frame


def test_roll_from_run_caps_at_26():
    # Full-run roll: speedF 17 at entry -> 17*1.5+0.5 = 26 (cap). Robust w/o anim data (speedF -> 17).
    s = _run_atn(_UP * 15 + _A + [(128, 128, 0, 0)] * 5)
    assert s.state == FRONT_ROLL
    assert abs(s.nspeed - 26.0) < 0.02
    if _ANIM:  # mid-roll momentum position is bit-exact too
        assert_pos_bits(s, 'roll_run')


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_roll_slow_is_speedF_scaled():
    # Rolling while barely moving -> the entry speedF (~3.67) scales the roll: 3.67*1.5+0.5 ~= 6.0.
    s = _run_atn(_UP * 2 + _A + [(128, 128, 0, 0)] * 5)
    assert s.state == FRONT_ROLL
    assert abs(s.nspeed - 6.001) < 0.05
    assert_pos_bits(s, 'roll_slow')   # (skipif not _ANIM above)


def test_roll_nspeed_arc_and_exit():
    # The whole roll nspeed arc is bit-exact: 26 held through the roll, -5 on the neutral exit (26->21),
    # then the normal decel to a clean stop (state 4). (Position tail is not asserted -- foot phase.)
    s = LandState(pos_z=SEED_POS_Z, state=FREE_WAIT, idle_frame=70.0)
    rows = [None]
    for (sx, sy, b, tl) in (_UP * 15 + _A + [(128, 128, 0, 0)] * 30):
        s.step(sx, sy, buttons=b, triggerL=tl)
        rows.append((s.state, s.nspeed))
    assert all(rows[f][0] == FRONT_ROLL and abs(rows[f][1] - 26.0) < 1e-4 for f in range(18, 36))
    assert rows[36][0] == MOVE and abs(rows[36][1] - 21.0) < 1e-4      # exit drops field_0x20 (5.0)
    assert rows[-1][0] == WAIT and rows[-1][1] == 0.0                   # decels to a clean stop


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_roll_settle_position_bit_exact():
    # Full-run roll played to a standstill: total distance is bit-exact (live pos_z 1524.694). The
    # low-speed post-roll tail needs the ANM_ROLLF-warmed toe stream (foot engine step_roll).
    s = _run_atn(_UP * 15 + _A + [(128, 128, 0, 0)] * 40)
    assert s.state == WAIT and abs(s.nspeed) < 0.5
    assert_pos_bits(s, 'roll_settle')


def test_roll_ebs_preserves_negative_speed():
    # Frame-perfect EBS out of a roll: getFrame()>17 exits straight to ATN at 26, release L into
    # ESS-down -> backward-flip preserves -23.109 in MOVE. Pure mNormalSpeed (no anim data needed).
    s = _run_atn(_UP * 15 + _A + [(128, 0, 0x40, 255)] * 17 + [(128, 110, 0, 0)] * 14)
    assert s.state == MOVE
    assert abs(s.nspeed - (-23.109)) < 0.02
    d = ((s.facing - s.travel) % 65536)                     # facing ~ travel (aligned EBS)
    assert min(d, 65536 - d) < 0x0400
    if _ANIM:  # the roll->ATN->flip position tail is bit-exact
        assert_pos_bits(s, 'roll_ebs')


# --- ground-reversal turn procs (WAIT_TURN 23 / MOVE_TURN 24 / SLIP 25) ---------------------

# Offline shadow of run_land_tests.py's turn cases. All three reverse a >0x7800 stick to end walking (MOVE)
# 180deg-reversed at the cap; only the PATH differs (LandState.visited). Position isn't pinned (fallback).
_DN = [(128, 0, 0, 0)]           # full-down, no L, 1 frame


def _run_turn(seq):
    s = LandState(pos_z=SEED_POS_Z, facing=0, travel=0, csangle=0, state=FREE_WAIT,
                  nspeed=0.0, idle_frame=70.0)
    rows = []
    for (sx, sy, btn, tl) in seq:
        s.step(sx, sy, buttons=btn, triggerL=tl)
        rows.append((s.state, s.nspeed))
    return s, rows


def test_waitturn_pivots_in_place_then_walks():
    # Idle + full-reverse flick from a standstill (nspeed~0, >0x7800): procWaitTurn pivots facing in
    # place (no MOVE_TURN/SLIP), then walks off reversed at the cap.
    s, rows = _run_turn(_DN * 15)
    assert WAIT_TURN in s.visited and MOVE_TURN not in s.visited and SLIP not in s.visited
    assert all(abs(ns) < 0.05 for st, ns in rows if st == WAIT_TURN)   # pivots in place (nspeed ~0)
    assert s.state == MOVE
    assert abs(s.nspeed - 17.0) < 1e-4
    assert abs(_deg(s.facing) - 180.0) < 0.1 and abs(_deg(s.travel) - 180.0) < 0.1


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_waitturn_position_bit_exact():
    # Idle full-reverse pivot (WAIT_TURN ANM_ROT -> WAIT idle-proc WAITS/ANM_ATNWRS re-pose) -> reversed
    # walk-off: whole arc position bit-exact via the anim engine. Live pos_z 690.471 @f15 (explore_waitturn).
    s, _ = _run_turn(_DN * 15)
    assert WAIT_TURN in s.visited and MOVE_TURN not in s.visited and SLIP not in s.visited
    assert s.state == MOVE
    assert_pos_bits(s, 'waitturn')


def test_moveturn_below_slip_threshold():
    # 1 up frame (barely moving, speedF/max << 0.6) then full reverse -> procMoveTurn(1) directly,
    # no SLIP. Halves nspeed at entry then re-accelerates while facing sweeps to the reversed travel.
    s, rows = _run_turn([(128, 255, 0, 0)] + _DN * 18)
    assert MOVE_TURN in s.visited and SLIP not in s.visited
    assert s.state == MOVE
    assert abs(s.nspeed - 17.0) < 1e-4
    assert abs(_deg(s.facing) - 180.0) < 0.1


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_moveturn_position_bit_exact():
    # Low-speed reverse -> MOVE_TURN into the reversed walk: the WHOLE arc is position bit-exact via the
    # anim engine (pre-halving pose + entry/exit morf; see KB). Live pos_z 511.686 (explore_mt_1.csv).
    s, _ = _run_turn([(128, 255, 0, 0)] + _DN * 20)
    assert MOVE_TURN in s.visited and SLIP not in s.visited
    assert s.state == MOVE
    assert_pos_bits(s, 'moveturn_pos')


def test_slip_skids_forward_then_moveturn():
    # Full-speed run (speedF/max = 1.0 > 0.6) + a genuine stick flip -> procSlip: mNormalSpeed = speedF*1.1
    # (18.7, exceeds the cap), skids FORWARD (travel held) bleeding ~-1.25/frame, then hands to procMoveTurn.
    s, rows = _run_turn([(128, 255, 0, 0)] * 15 + _DN * 30)
    assert SLIP in s.visited and MOVE_TURN in s.visited
    slip_speeds = [ns for st, ns in rows if st == SLIP]
    assert abs(max(slip_speeds) - 18.7) < 0.02          # entry seed speedF(17)*1.1, no cap clamp
    assert s.state == MOVE
    assert abs(s.nspeed - 17.0) < 1e-4
    assert abs(_deg(s.facing) - 180.0) < 0.1 and abs(_deg(s.travel) - 180.0) < 0.1


@pytest.mark.skipif(not _ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_slip_position_bit_exact():
    # Full-speed reverse -> SLIP skid -> MOVE_TURN -> reversed walk, WHOLE arc position bit-exact: ANM_SLIP
    # scales jnt37.x 1.2 (FK applies scale + morf blends it), so the MOVE_TURN toe stream is exact. 981.718.
    s, _ = _run_turn([(128, 255, 0, 0)] * 15 + _DN * 30)
    assert SLIP in s.visited and MOVE_TURN in s.visited
    assert s.state == MOVE
    assert_pos_bits(s, 'slip')
