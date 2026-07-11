"""Offline gate for the CC-push COUPLED stepper against a LIVE capture (ROADMAP Phase C).

Replays a locked live capture (`fixtures/hyrule_cc_push.json`, from
`harness/rollstab/capture_cc_push.py` on slot 3) through the coupled Link+Tetra stepper WITHOUT
Dolphin and diffs every frame bit-for-bit. The scenario: Tetra teleported into the corner (WallCorrect
braces her), Link rolls in from far out and CONVERGES into her, and the Co push fires while she is
wall-braced -- the clip's push geometry, staged by teleport.

What this locks in as bit-exact (0 ULP), the wiring + coupled physics:
  * Link's wall-approach FRONT_ROLL, frame by frame (Phase-W corner walls in the stepper);
  * Tetra's teleport-into-corner WallCorrect eject + braced hold (Phase-C BG collision), coupled;
  * the CC push wired at the decomp point in posMove -- Link stays bit-exact right up to the frame the
    push is first consumed, proving the push is applied in the right place and nowhere else.

Open frontier (xfail): once the push fires (here at roll frame ~6), Link's position drifts a few ULP
and compounds, because `body_cyl.roll_co_center` (the push's overlap geometry) carries the FRONT_ROLL
oldframe-morf transient and is bit-exact only after roll frame ~11 (see its live golden
`tests/golden/roll_co_center_live.json` + `knowledge/mechanics/actor-push.md`). Modelling that morf
(SESSION_PROMPT future work) is what closes the push frames; when it lands, the xfail flips to pass.
"""
import json
import os

import pytest

_HERE = os.path.dirname(__file__)
_FIX = os.path.join(_HERE, "..", "fixtures", "hyrule_cc_push.json")
_WALLS = os.path.join(_HERE, "..", "fixtures", "hyrule_tetra_walls_ordered.json")

# The proven bit-exact window (see the fixture / capture): from Tetra's placement (f10) through the
# last frame before the push perturbs Link (f14). Every frame here is 0 ULP for BOTH actors.
PREPUSH_LAST = 14


def _load():
    from tww_sim.land.walls import load_ordered_mesh
    from harness.rollstab.cc_stepper import couple_replay
    fix = json.load(open(_FIX))
    walls = load_ordered_mesh(_WALLS)
    res = couple_replay(fix["frames"], fix["tetra_placed_at"], fix["tetra_placed_xz"],
                        walls, fix["ground_y"])
    return fix, res


def test_fixture_present():
    assert os.path.exists(_FIX), "run: python -m harness.rollstab.capture_cc_push out=... (slot 3)"


@pytest.mark.slow
def test_coupled_prepush_and_brace_bitexact():
    """Link's wall-approach roll AND Tetra's teleport-into-corner brace are bit-exact (0 ULP) every
    frame from placement through the last pre-push frame -- and the push, once it engages, does not
    perturb any earlier frame. Proves the coupled stepper + the push wiring point."""
    _fix, res = _load()
    pre = [r for r in res if r["f"] <= PREPUSH_LAST]
    assert pre, "no pre-push frames in the capture"
    for r in pre:
        assert r["dlx"] == 0 and r["dlz"] == 0, (
            "Link not bit-exact at f%d (pre-push wall-held roll): dlx=%d dlz=%d"
            % (r["f"], r["dlx"], r["dlz"]))
        assert r["dtx"] == 0 and r["dtz"] == 0, (
            "Tetra not bit-exact at f%d (teleport-into-corner brace): dtx=%d dtz=%d"
            % (r["f"], r["dtx"], r["dtz"]))
    # sanity: the placement frame is inside this window and the push engages right after it.
    assert any(r["placed"] for r in pre)


@pytest.mark.slow
@pytest.mark.xfail(strict=True, reason="roll_co_center oldframe-morf residual: the push's overlap "
                   "geometry is bit-exact only after roll frame ~11 (converges here at ~6). Model "
                   "the morf (SESSION_PROMPT future work) to close the push frames.")
def test_coupled_push_frames_bitexact():
    """Link stays bit-exact through the push-active frames too (the full coupled clip physics).
    Currently RED from the roll-frame Co-center morf; flips to pass when the morf is modelled."""
    _fix, res = _load()
    for r in res:
        assert r["dlx"] == 0 and r["dlz"] == 0, (
            "Link diverges at f%d: dlx=%d dlz=%d" % (r["f"], r["dlx"], r["dlz"]))
