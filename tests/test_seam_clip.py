"""Offline regression for the seam-clip model (tww_sim.core.collision + harness.collision.seam_model).

Guards the two things that must not drift:
  1. Bit-exact reproduction of the live-captured LineCheck: for every triangle the game tested on the
     row-1 clip line (ganonl_seam_capture.json), the port's cross_lin_tri hit/miss matches the game's
     recorded return, using the game's STORED plane.
  2. The known GanonL row-1 displacement clips (collision leaves Link at the target).
"""
import json
import os

from tww_sim.core.collision import Tri, Plane, cross_lin_tri
from harness.collision.seam_model import predict_clip

_CAP = os.path.join(os.path.dirname(__file__), "..", "harness", "collision",
                    "ganonl_seam_capture.json")


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
