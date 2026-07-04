#!/usr/bin/env python3
"""Regenerate the OFFLINE land golden(s) at FULL float32 precision from the sim.

The offline land position tests (tests/test_land.py) are a BIT-EXACT snapshot of the sim's f32
output -- they pin the exact `pos_z` / `speedF` bytes so any change to the floating-point math
(the f32-vs-f64 position accumulation, an FMA re-ordering in the anim FK, a cos-table change, an
imprecise seed) moves the bits and fails the test. This is the guard the old `< 0.05` tolerance
lacked: 0.05 at a ~1000-unit magnitude is ~400 float32 ULP wide, so a ~2 ULP accumulation error
(the f64-sum bug) slid straight through. The golden values here are decomp-faithful f32
(the game stores pos.{x,z} as f32 cXyz and re-rounds every frame); sim-vs-LIVE faithfulness (the
open <=~2 ULP residual) is tracked separately by tests/dolphin/run_land_tests.py.

Run this ONLY after a DELIBERATE fp change, and commit the regenerated golden:
    python tests/gen_land_golden.py            > tests/golden/land_walk_speedf.csv
    python tests/gen_land_golden.py endpoints          # prints the ATN/roll/turn hex constants to
                                                       # paste into test_land.py CASE_POSZ

Needs the copyrighted anim keyframe data under _generated/anim/ (dev machines). Without it the sim
falls back to a calibrated stand-in and these snapshots are meaningless -- the tests SKIP instead.
"""
import os
import struct
import sys

# >>> repo bootstrap: locate superswim/ package
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from superswim.land import LandState, FREE_WAIT

# Exact f32 anchor seed (land_flatwalk@twwgz rest pos_z, read live: 0x443f0510). The old 764.079 was
# 2 ULP off (0x443f050e) -- seeding imprecisely is itself a float-accuracy bug the snapshot now pins.
SEED_POS_Z = 764.0791015625
IDLE_FRAME = 70.0

WALK_STICKS = [(128, 255)] * 30 + [(128, 128)] * 20

_UP = [(128, 255, 0, 0)]
_LDN = [(128, 0, 0x40, 255)]        # L-target + full down, 1 frame
_A = [(128, 255, 0x100, 0)]         # A + up, 1 frame
_DN = [(128, 0, 0, 0)]              # full-down, no L, 1 frame

# ATN / roll / turn endpoint sequences (mirror tests/test_land.py::_run_atn / _run_turn).
CASE_SEQS = {
    "brakeslide":  _UP * 10 + _LDN + [(128, 110, 0x40, 255)] * 10,
    "ebs":         _UP * 10 + _LDN + [(128, 110, 0, 0)] * 30,
    "face_left":   _UP * 10 + _LDN + [(128, 110, 0, 0)] + [(110, 128, 0, 0)] * 60,
    "brake_right": _UP * 10 + _LDN + [(128, 110, 0, 0)] + [(146, 128, 0, 0)] * 60,
    "roll_run":    _UP * 15 + _A + [(128, 128, 0, 0)] * 5,
    "roll_slow":   _UP * 2 + _A + [(128, 128, 0, 0)] * 5,
    "roll_settle": _UP * 15 + _A + [(128, 128, 0, 0)] * 40,
    "roll_ebs":    _UP * 15 + _A + [(128, 0, 0x40, 255)] * 17 + [(128, 110, 0, 0)] * 14,
    "waitturn":    _DN * 15,
    "moveturn":    [(128, 255, 0, 0)] + _DN * 18,
    "moveturn_pos": [(128, 255, 0, 0)] + _DN * 20,   # test_moveturn_position_bit_exact's longer seq
    "slip":        [(128, 255, 0, 0)] * 15 + _DN * 30,
}


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def _fresh():
    return LandState(pos_z=SEED_POS_Z, facing=0, travel=0, csangle=0, state=FREE_WAIT,
                     nspeed=0.0, idle_frame=IDLE_FRAME)


def emit_walk_csv():
    s = LandState(pos_z=SEED_POS_Z, state=FREE_WAIT, idle_frame=IDLE_FRAME)
    print("# land_flatwalk@twwgz walk_run golden (FULL float32 precision, SIM snapshot).")
    print(f"# seed_pos_z={SEED_POS_Z!r} (0x{f32_bits(SEED_POS_Z):08x}) idle_frame={IDLE_FRAME:.3f}"
          "  seq=30 up + 20 neutral (free cam)")
    print("# SIM.pos_z / SIM.speedF exact f32 bytes -- a BIT-EXACT regression lock (any fp-math change")
    print("# moves the bits). Live-faithful to <=2 ULP at the endpoint (open residual, tracked by")
    print("# tests/dolphin/run_land_tests.py). Regenerate: python tests/gen_land_golden.py > this file")
    print("f,ns,msd,speedF,speedF_hex,pos_z,pos_z_hex")
    for i, (sx, sy) in enumerate(WALK_STICKS, 1):
        s.step(sx, sy)
        print(f"{i},{s.nspeed:g},{s.msd:g},{s.speedF!r},0x{f32_bits(s.speedF):08x},"
              f"{s.pos_z!r},0x{f32_bits(s.pos_z):08x}")


def emit_endpoints():
    print("# Paste into tests/test_land.py::CASE_POSZ (label -> exact f32 pos_z bits).")
    print("CASE_POSZ = {")
    for label, seq in CASE_SEQS.items():
        s = _fresh()
        for (sx, sy, btn, tl) in seq:
            s.step(sx, sy, buttons=btn, triggerL=tl)
        print(f"    {label!r:14s}: 0x{f32_bits(s.pos_z):08x},   # {s.pos_z!r} (state {s.state})")
    print("}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "endpoints":
        emit_endpoints()
    else:
        emit_walk_csv()
