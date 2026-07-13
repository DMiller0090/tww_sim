"""From-rest regression for the SHEATHED roll-stab anchor (kaze r11, session 36; re-root-caused s37).

The sheathed-roll milestone (session 35 wired the mid-walk draw into the ROLL solver) needs a
SHEATHED anchor at the kaze roll seam that is REST BIT-EXACT so a solved from-rest clip delivers
0-ULP. Session 36 minted one (`kaze_r11_rollstab_sheathed@twwgz`, equip-only change off idle13 via
an idle A-press, `mEquipItem` 0x100) and captured its live verification calib
(`fixtures/sheathed_rest_calib.json`, the same [straight]*NPREF + [aim]*NCRUISE walk `rest.py`
plays).

STATUS (root cause CORRECTED session 37 -- see dead-end #30 + the s37 handoff): the from-rest sim
is NOT yet bit-exact for this anchor. The session-36 story ("sheathed proc-transitions to MOVE one
frame LATER than idle13") was a `run_dtm` row-0 POLL-JITTER artifact -- a jitter-proof measurement
(emulator-frame-aligned, `harness.rollstab.capture_walkentry`) shows BOTH anchors reach proc-MOVE at
the SAME game-frame (gf6) and the big walk step at gf8. The REAL divergence is the walk-entry foot
TOE-STREAM (`posMoveFromFootPos`/`f312`): at the sheathed idle phase (d~52.8) the sim's first-move
toe delta is ~0.034 while live is ~0.060, and the decomp-faithful 0.05 speedF clamp
(`_py_foot_compose`) then zeros the sim but keeps live -- opposite sides of the razor -- accumulating
~0.8u over the m3598>0 blend frames. It is PHASE-driven, NOT equip: forcing `sword_drawn`/`model_draw`
moves it ~0.003u; idle13 (d~30.8, drawn) is bit-exact. This is the walk-entry foot-FK frontier
(dead-end #25/#28). GROUND TRUTH for the fix: jitter-proof, foot-pose-rich goldens
`fixtures/sheathed_walkentry_golden.json` (RED) + `fixtures/idle13_walkentry_golden.json` (the
bit-exact reference), aligned by game_frame with raw mFootData toe/heel + plant per frame.

This test flags RED (strict xfail) until the sheathed walk-entry is modelled from rest. Flip it to a
plain assert when it goes bit-exact. Live golden -- NEVER edit the fixture to make the sim pass.
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(os.path.dirname(_HERE), 'fixtures', 'sheathed_rest_calib.json')

try:
    from harness.rollstab import rest as C
    _HAVE = C.rest_state is not None and os.path.exists(_FIX)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / sheathed calib unavailable")

ANCHOR = 'kaze_r11_rollstab_sheathed@twwgz'


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _replay():
    """Seed rest_state (sheathed => model_draw auto-ON, no B => no draw), replay the calib's
    verification walk ([straight]*NPREF + [aim]*NCRUISE); yield (k, sim, live)."""
    calib = json.load(open(_FIX))
    assert calib['anchor'] == ANCHOR
    _, straight, aim = C.sticks_of(ANCHOR)
    stream = [straight] * C.NPREF + [aim] * C.NCRUISE
    s = C.rest_state(ANCHOR)
    for k, (sx, sy) in enumerate(stream):
        s.step(sx, sy)
        if k >= len(calib['frames']):
            break
        yield k, s, calib['frames'][k]


@pytest.mark.xfail(strict=True, reason="sheathed walk-entry not yet modelled from rest: the toe-stream "
                   "f312 is ~0.034 vs live ~0.060 at the first walk frame -> the 0.05 speedF clamp flips "
                   "(walk-entry foot-FK residual, phase-driven; session 37 root-cause, dead-end #30)")
def test_sheathed_full_position_bitexact():
    """The sheathed from-rest walk must be BIT-EXACT (0 ULP) every row before its solver hits are
    trusted (the acceptance is f32 dust; dead-end #28). Currently RED -- see the module docstring."""
    bad = [k for k, s, lf in _replay()
           if not (_bits(s.pos_x) == _bits(lf['pos_x']) and _bits(s.pos_z) == _bits(lf['pos_z']))]
    assert not bad, "position diverged at rows %s" % bad
