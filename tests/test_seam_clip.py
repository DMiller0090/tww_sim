"""Offline regression for the seam-clip model (tww_sim.core.collision + harness.collision.seam_model).

Guards the two things that must not drift:
  1. Bit-exact reproduction of the live-captured LineCheck: for every triangle the game tested on the
     row-1 clip line (ganonl_seam_capture.json), the port's cross_lin_tri hit/miss matches the game's
     recorded return, using the game's STORED plane.
  2. The known GanonL row-1 displacement clips (collision leaves Link at the target).
"""
import json
import os

import struct

from tww_sim.core.collision import Tri, Plane, cross_lin_tri, calc_pla
from harness.collision.seam_model import predict_clip

_CAP = os.path.join(os.path.dirname(__file__), "..", "harness", "collision",
                    "ganonl_seam_capture.json")


def _bits(x):
    return struct.unpack(">I", struct.pack(">f", x))[0]


_GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "calc_pla_ram.json")


def _f_from_hex(s):
    return struct.unpack(">f", struct.pack(">I", int(s, 16)))[0]


def test_calc_pla_bit_exact_vs_ram():
    """calc_pla (frsqrte-based cM3d_CalcPla port) must reproduce the game's RAM-stored planes
    bit-for-bit — this is what lets the sim run faithfully on synthetic geometry."""
    data = json.load(open(_CAP))
    for t in data[:4]:
        p = calc_pla(t["A"], t["B"], t["C"])
        for got, want in [(p.nx, t["n"][0]), (p.ny, t["n"][1]), (p.nz, t["n"][2]), (p.d, t["D"])]:
            assert _bits(got) == _bits(want), f"tri n={t['n']}: {got!r} != {want!r}"


def test_calc_pla_golden_ram_planes():
    """Full-precision RAM golden (Hyrule, hex-encoded f32) covering the Force25Bit-sensitive
    triangles — the ones that were 1-2 ULP off before the exact PSVECCrossProduct lanes, fused
    Newton fnmsubs, and the 25-bit frC round in VECMag. calc_pla is bit-exact on all 4506 Hyrule
    tris; these 10 are the permanent offline guard (poly 4/20/37/72/127/128 exercise the 25-bit
    path, 0/1/2/5 are the always-exact cases)."""
    for t in json.load(open(_GOLDEN)):
        A = [_f_from_hex(h) for h in t["A"]]
        B = [_f_from_hex(h) for h in t["B"]]
        C = [_f_from_hex(h) for h in t["C"]]
        p = calc_pla(A, B, C)
        want = [int(t["n"][0], 16), int(t["n"][1], 16), int(t["n"][2], 16), int(t["D"], 16)]
        got = [_bits(p.nx), _bits(p.ny), _bits(p.nz), _bits(p.d)]
        assert got == want, f"poly {t['poly']}: got {[hex(g) for g in got]} != {[hex(w) for w in want]}"


def test_linecheck_matches_captured_game_returns():
    data = json.load(open(_CAP))
    checked = 0
    for d in data:
        if not d.get("A"):
            continue
        tri = Tri(d["A"], d["B"], d["C"], plane=Plane(*d["n"], d["D"]))
        hit, _ = cross_lin_tri(tuple(d["ls"]), tuple(d["le"]), tri, a=True, b=False)
        assert hit == bool(d["ret"]), f"tri n={d['n']}: port hit={hit}, game ret={d['ret']}"
        checked += 1
    assert checked >= 9   # the 4 seam walls + roof/other tris the game line-checked


def test_row1_clips():
    clipped, info = predict_clip((-817.6296387, -37307.21875), (-855.1299438, -37343.96094))
    assert clipped, info
    assert not info["line_hit"] and not info["wall_hit"], info


def test_short_displacement_blocks():
    # Under the 35 u cylinder radius toward the wall: WallCorrect must push back (no clip).
    clipped, info = predict_clip((-817.6296387, -37307.21875), (-830.0, -37320.0))
    assert not clipped, info
