"""Offline regression for the FRONT_ROLL body Co cylinder centre (tww_sim.core.anim.body_cyl),
guarded against a LIVE golden captured on GZLJ01 (tests/golden/roll_co_center_live.json).

The golden was captured with Link rolling pinned against a wall, so current.pos and shape_angle.y
are constant and only the rollf pose moves mCyl's centre -- isolating the anim-driven cylinder centre
(daPy_lk_c::setCollision spD0.x/z = 0.5*(root+neck world joint XZ)). The port poses the clean single
rollf frame; it is bit-exact once the roll-entry oldframe-morf transient has settled (frames >~11),
and carries a small decaying residual before that (the morf blends toward the pre-roll pose; not
reproduced here -- see body_cyl.py). We therefore assert:
  * the settled tail (anim_frame >= 12) is bit-exact (< 1 ULP at magnitude ~1700 == < 2e-4);
  * every frame past the entry frame is within the documented morf residual (< 0.30 u), and the
    residual is monotonically non-increasing (the morf decays) -- a real regression (wrong joint,
    wrong FK, wrong facing handling) breaks both.

Requires the copyrighted anim keyframe data under _generated/anim (dev machines); SKIPS without it.
"""
import json
import math
import os

import pytest

from tww_sim.core.anim import body_cyl

_HAVE_ANIM = body_cyl.available()
_GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "roll_co_center_live.json")


def _load():
    with open(_GOLDEN) as f:
        return json.load(f)


@pytest.mark.skipif(not _HAVE_ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_roll_co_center_settled_bit_exact():
    """Once the roll-entry morf has decayed (anim_frame >= 12) the clean-pose port == the game."""
    g = _load()
    px, _py, pz = g["pos"]
    fac = g["shape_angle_y"]
    checked = 0
    for frame, lx, lz in g["frames"]:
        if frame < 12.0:
            continue
        cx, cz = body_cyl.roll_co_center(px, pz, fac, frame)
        err = math.hypot(cx - lx, cz - lz)
        assert err < 2e-4, f"settled frame {frame}: err {err} (expected < 1 ULP)"
        checked += 1
    assert checked >= 2


@pytest.mark.skipif(not _HAVE_ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_roll_co_center_transient_bounded_and_decaying():
    """Past the entry frame the residual (the un-modelled oldframe-morf) stays < 0.30 u and decays."""
    g = _load()
    px, _py, pz = g["pos"]
    fac = g["shape_angle_y"]
    errs = []
    for frame, lx, lz in g["frames"]:
        cx, cz = body_cyl.roll_co_center(px, pz, fac, frame)
        errs.append(math.hypot(cx - lx, cz - lz))
    # entry frame (frame 0.0) is ~fully the old running pose -> large; everything after is small.
    for e in errs[1:]:
        assert e < 0.30, f"post-entry residual {e} exceeds the documented morf bound"
    # the morf decays: each post-entry residual is <= the previous one (allow f32 noise).
    for a, b in zip(errs[1:], errs[2:]):
        assert b <= a + 1e-4, f"residual grew ({a} -> {b}); morf should decay monotonically"


@pytest.mark.skipif(not _HAVE_ANIM, reason="anim keyframe data (_generated/anim) not present")
def test_roll_co_center_leads_the_feet():
    """The whole point: the anim-driven centre is offset well away from the feet (current.pos) --
    the feet-proxy the first tetra_clip pass used is wrong by this much (~10-26 u mid-lunge)."""
    g = _load()
    px, _py, pz = g["pos"]
    fac = g["shape_angle_y"]
    peak = 0.0
    for frame, _lx, _lz in g["frames"]:
        cx, cz = body_cyl.roll_co_center(px, pz, fac, frame)
        peak = max(peak, math.hypot(cx - px, cz - pz))
    assert peak > 10.0, f"expected the roll cyl centre to lead the feet by >10u, got {peak}"
