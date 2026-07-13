"""From-rest regression for the SHEATHED roll-stab anchor (kaze r11, session 36, 2026-07-13).

The sheathed-roll milestone (session 35 wired the mid-walk draw into the ROLL solver) needs a
SHEATHED anchor at the kaze roll seam that is REST BIT-EXACT so a solved from-rest clip delivers
0-ULP. Session 36 minted one (`kaze_r11_rollstab_sheathed@twwgz`, equip-only change off idle13 via
an idle A-press, `mEquipItem` 0x100) and captured its live verification calib
(`fixtures/sheathed_rest_calib.json`, the same [straight]*NPREF + [aim]*NCRUISE walk `rest.py`
plays).

STATUS: the from-rest sim is NOT yet bit-exact for this anchor -- the sword-DRAWN idle13 IS (its
`test_walkstab_rest`/`rest.py` gates are green), but the sheathed idle takes ONE EXTRA idle frame
before the WAIT->MOVE walk transition (live: 3 idle rows k=0..2, MOVE at k=3; idle13: 2 idle rows,
MOVE at k=2), so the sim's walk starts one frame early and every downstream row is off by ~one walk
step. It is NOT `sword_drawn`/`model_draw` (forcing either changes the ramp by ~0.003u -- ruled out
offline) and NOT a single `REST_NOOPS` shift (that constant holds the idle anim `d_frame` and the
position TOGETHER, but live advances `d_frame` at k=2 while position stays at rest until k=3 -- the
extra frame is a WAIT->MOVE / stick-delivery latency the drawn anchor does not have). Likely the
sheathed idle rests in a non-`waits` arm (the Phase-R risk flagged in the handoff) whose transition
differs by a frame; NOTE the live DTM row-0 alignment is also jittery +-1 idle frame (fast-poll).

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


@pytest.mark.xfail(strict=True, reason="sheathed walk-entry not yet modelled from rest: 1 extra "
                   "idle frame before WAIT->MOVE vs the drawn idle (session 36 root-cause)")
def test_sheathed_full_position_bitexact():
    """The sheathed from-rest walk must be BIT-EXACT (0 ULP) every row before its solver hits are
    trusted (the acceptance is f32 dust; dead-end #28). Currently RED -- see the module docstring."""
    bad = [k for k, s, lf in _replay()
           if not (_bits(s.pos_x) == _bits(lf['pos_x']) and _bits(s.pos_z) == _bits(lf['pos_z']))]
    assert not bad, "position diverged at rows %s" % bad
