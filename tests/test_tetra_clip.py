"""Offline regression for the Tetra Co-push model + clip pipeline.

Guards:
  1. cyl-cyl overlap depth (cM3d_Cross_CylCyl) + weight split (cCcS::SetPosCorrect) — the pure math,
     incl. the live-confirmed Type2/weight-140 Tetra share (0.538) and Link's push direction.
  2. The pipeline on the live (-1727,-990) anchor: a roll/thrust at 49.22u does NOT clip alone, but a
     Tetra placed behind Link with a small overlap DOES — and the minimum overlap is ~0.68u
     (the ~0.37u nudge the corner needs, at the 0.538 share).

Decomp-grounded (see tww_sim/core/cc_push.py); Tetra params live-confirmed on GZLJ01.
"""
import json
import math
import os
import struct

from tww_sim.core.cc_push import (co_push_link, cyl_cyl_cross_len, weight_type,
                                   WEIGHT_LINK, WEIGHT_TETRA_V5, WEIGHT_TETRA_DEFAULT)
from tww_sim.core.collision import Tri, Plane
from harness.collision.gap_search import settle
from harness.collision.tetra_clip import clip_with_push, solve_min_overlap


def _fh(s):
    return struct.unpack(">f", struct.pack(">I", int(s, 16)))[0]


def _load_anchor():
    g = json.load(open(os.path.join(os.path.dirname(__file__), "golden", "hyrule_seam_1727_ram.json")))
    tris = [Tri([_fh(x) for x in t["v"][0]], [_fh(x) for x in t["v"][1]], [_fh(x) for x in t["v"][2]],
                plane=Plane(*[_fh(x) for x in t["n"]], _fh(t["D"]))) for t in g["tris"]]
    link_y = _fh(g["seam_v_hex"][1])
    old = (_fh(g["old_hex"][0]), _fh(g["old_hex"][1]))
    return tris, link_y, old


# ---- the pure math ---------------------------------------------------------

def test_weight_types():
    assert weight_type(0xFF) == 0 and weight_type(0xFE) == 1 and weight_type(120) == 2


def test_overlap_depth_and_gates():
    # centers 99.6 apart, both R=50 -> overlap 0.4
    hit, cl = cyl_cyl_cross_len((0.0, 0.0, 0.0), 50, 81.25, (-99.6, 0.0, 0.0), 50, 140)
    assert hit and abs(cl - 0.4) < 1e-4
    # XZ miss (dist > sum of radii)
    hit, cl = cyl_cyl_cross_len((0.0, 0.0, 0.0), 50, 81.25, (-101.0, 0.0, 0.0), 50, 140)
    assert not hit and cl == 0.0
    # Y ranges don't overlap (Link far above Tetra's top)
    hit, cl = cyl_cyl_cross_len((0.0, 300.0, 0.0), 50, 81.25, (-99.6, 0.0, 0.0), 50, 140)
    assert not hit


def test_push_split_type2_share_and_direction():
    # Tetra Type2(140) vs Link Type2(120): Link takes 140/260 of the depth, away from Tetra (+x here).
    link = (0.0, 0.0, 0.0)
    tetra = (-99.6, 0.0, 0.0)          # Tetra at -x -> push toward +x
    px, py, pz = co_push_link(link, 50, 81.25, tetra, 50, 140, other_w=WEIGHT_TETRA_V5)
    assert py == 0.0 and abs(pz) < 1e-6
    assert px > 0.0                                   # away from Tetra
    assert abs(px - 0.4 * 140.0 / 260.0) < 1e-4       # 0.538 * depth
    # Immovable Type0 Tetra would instead give Link the FULL depth
    px0, _, _ = co_push_link(link, 50, 81.25, tetra, 50, 140, other_w=WEIGHT_TETRA_DEFAULT)
    assert abs(px0 - 0.4) < 1e-4


def test_push_deadzone():
    # overlap 0.005u < 1/125 deadzone -> no push
    p = co_push_link((0.0, 0.0, 0.0), 50, 81.25, (-99.995, 0.0, 0.0), 50, 140, other_w=WEIGHT_TETRA_V5)
    assert p == (0.0, 0.0, 0.0)


# ---- the pipeline on the live anchor --------------------------------------

def test_tetra_push_closes_the_1727_clip():
    """Roll/thrust 49.22u alone is blocked at the (-1727,-990) corner; a Tetra nudge clips it."""
    tris, link_y, old = _load_anchor()
    settled = settle(tris, old, link_y)
    # direction toward the live clip point; roll gives 49.22u (just short of the corner minimum)
    new_live = (-1727.34228515625, -990.6356201171875)
    dx, dz = new_live[0] - settled[0], new_live[1] - settled[2]
    dm = math.hypot(dx, dz); dhx, dhz = dx / dm, dz / dm
    thrust = (dhx * 49.22, dhz * 49.22)

    base = clip_with_push((settled[0], settled[2]), link_y, thrust, (settled[0] - 1e6, settled[2]), tris)
    assert not base["clipped"], "roll+thrust 49.22u should NOT clip without Tetra"

    sol = solve_min_overlap((settled[0], settled[2]), link_y, thrust, tris, max_overlap=8.0, step=0.01)
    assert sol is not None, "Tetra push should make it clip within 8u overlap"
    assert 0.4 < sol["overlap"] < 1.2, f"min overlap {sol['overlap']} off the ~0.68u expectation"
    # the push Link actually gets is the ~0.37u the corner was missing (0.538 * overlap)
    push_mag = math.hypot(*sol["push"])
    assert 0.30 < push_mag < 0.45, f"push {push_mag} off the ~0.37u nudge"
