"""Offline regression for the Tetra Co-push model + clip pipeline.

Guards:
  1. cyl-cyl overlap depth (cM3d_Cross_CylCyl) + the dCcS::SetPosCorrect rank-table weight split —
     the pure math, incl. the live-confirmed 0.50 share (Link rank 5 vs Tetra rank 5) and push
     direction, and the immovable (0xFF, rank 10) case that gives Link the full depth.
  2. The pipeline on the live (-1727,-990) anchor: a roll/thrust at 49.22u does NOT clip alone, but a
     Tetra placed behind Link with a small overlap DOES — min overlap ~1.23u (push ~0.615u at the
     0.50 share).

Decomp-grounded (see tww_sim/core/cc_push.py); weights & cylinders live-confirmed on GZLJ01 (2026-07-06).
"""
import json
import math
import os
import struct

from tww_sim.core.cc_push import (co_push_link, cyl_cyl_cross_len, get_rank, push_shares,
                                   WEIGHT_LINK, WEIGHT_TETRA_V5, WEIGHT_TETRA_DEFAULT)
from tww_sim.core.collision import Tri, Plane
from harness.collision.gap_search import settle
from harness.collision.tetra_clip import clip_with_push, solve_min_overlap, LINK_CO_R, TETRA_CO_R


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

def test_get_rank():
    # GetRank thresholds (d_cc_s.cpp:153). Link 120 and Tetra 140 both land on rank 5.
    assert get_rank(120) == 5 and get_rank(140) == 5
    assert get_rank(0xFF) == 10 and get_rank(0xFE) == 9 and get_rank(0x01) == 1 and get_rank(0) == 0
    assert get_rank(0x6D) == 5 and get_rank(0x91) == 6      # boundary


def test_push_shares_rank_table():
    # Link(rank5) vs Tetra-v5(rank5) -> rank_tbl[5][5]=50 -> exact 50/50 (live-confirmed).
    s = push_shares(WEIGHT_LINK, WEIGHT_TETRA_V5)
    assert s is not None and abs(s[0] - 0.5) < 1e-7 and abs(s[1] - 0.5) < 1e-7
    # Immovable Tetra (0xFF, rank10): rank_tbl[5][10]=100 -> Link takes the full depth.
    s2 = push_shares(WEIGHT_LINK, WEIGHT_TETRA_DEFAULT)
    assert abs(s2[0] - 1.0) < 1e-7
    # both immovable -> no correction
    assert push_shares(0xFF, 0xFF) is None


def test_overlap_depth_and_gates():
    # centers 79.6 apart, Link R=30 + Tetra R=50 -> overlap 0.4
    hit, cl = cyl_cyl_cross_len((0.0, 0.0, 0.0), 30, 81.25, (-79.6, 0.0, 0.0), 50, 140)
    assert hit and abs(cl - 0.4) < 1e-4
    # XZ miss (dist > sum of radii = 80)
    hit, cl = cyl_cyl_cross_len((0.0, 0.0, 0.0), 30, 81.25, (-81.0, 0.0, 0.0), 50, 140)
    assert not hit and cl == 0.0
    # Y ranges don't overlap (Link far above Tetra's top)
    hit, cl = cyl_cyl_cross_len((0.0, 300.0, 0.0), 30, 81.25, (-79.6, 0.0, 0.0), 50, 140)
    assert not hit


def test_push_split_share_and_direction():
    # Tetra-v5 vs Link: Link takes 0.50 of the depth, away from Tetra (+x here).
    link = (0.0, 0.0, 0.0)
    tetra = (-79.6, 0.0, 0.0)           # Tetra at -x -> push toward +x
    px, py, pz = co_push_link(link, 30, 81.25, tetra, 50, 140, other_w=WEIGHT_TETRA_V5)
    assert py == 0.0 and abs(pz) < 1e-6
    assert px > 0.0                                   # away from Tetra
    assert abs(px - 0.4 * 0.5) < 1e-4                 # 0.50 * depth
    # Immovable Type0 Tetra (0xFF) instead gives Link the FULL depth
    px0, _, _ = co_push_link(link, 30, 81.25, tetra, 50, 140, other_w=WEIGHT_TETRA_DEFAULT)
    assert abs(px0 - 0.4) < 1e-4


def test_push_deadzone():
    # overlap 5e-6 < cM3d_IsZero (1e-5) -> no push
    p = co_push_link((0.0, 0.0, 0.0), 30, 81.25, (-79.999995, 0.0, 0.0), 50, 140, other_w=WEIGHT_TETRA_V5)
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
    assert 0.9 < sol["overlap"] < 1.6, f"min overlap {sol['overlap']} off the ~1.23u expectation"
    # the push Link actually gets to close the gap (0.50 * overlap)
    push_mag = math.hypot(*sol["push"])
    assert 0.45 < push_mag < 0.75, f"push {push_mag} off the ~0.615u nudge"
    assert abs(push_mag - 0.5 * sol["overlap"]) < 1e-3, "push should be 0.50 * overlap"
