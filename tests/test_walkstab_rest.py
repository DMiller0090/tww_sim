"""From-rest regression for the WALK-stab anchor (kaze r11, item-in-hand/sword-sheathed idle;
session 29, 2026-07-13). Live golden: a short straight walk played by a clean DTM with C-down held
(the free-cam pin), per-frame pos/facing/m359C -- tests/golden/walkstab_rest.json.

WHAT THIS LOCKS (the walk-stab feasibility finding):
  * With the C-down camera pin (substickY=0), the from-rest sim (rest.rest_state) is BIT-EXACT in
    FACING every frame -- the auto-cam would otherwise swing csangle and drift facing (session 28).
  * The only from-rest residual is the walk-entry foot toe-stream (m359C / f312, the known Phase-R /
    session-25 gap): a CONSTANT ~0.0024u position error, and it is a speedF (magnitude) error so it
    lies ALONG the travel direction -- its PERPENDICULAR component (~3.7e-5u) is 16x inside the
    walk-stab seam's ~6e-4u perp razor. So the razor quantity `rho` is preserved and a pure-sim
    one-shot is feasible; the along error is absorbed by the wide disp window + B-timing.

The perp-residual bound is GREEN (the feasibility). The full-position bit-exactness is xfail: the
along-track foot toe-stream is the open Phase-R residual (jointBeforeCB MOMI body-lean / walk-entry
oldframe-morf). Live golden -- NEVER edit the fixture to make the sim pass (tests/dolphin/README.md).
"""
import json
import math
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOLD = os.path.join(_HERE, 'golden')

try:
    from harness.rollstab import rest as C
    from harness.rollstab import walkstab as W
    _HAVE = C.rest_state is not None
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / anim data unavailable")

ANCHOR = 'kaze_r11_walkstab@twwgz'
RAZOR = 6e-4        # the seam's perp offset window (gap_search.characterize)


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _gold():
    return json.load(open(os.path.join(_GOLD, 'walkstab_rest.json')))


def _replay():
    """Seed rest_state, replay the golden's straight walk with C-down; yield (k, sim, live)."""
    g = _gold()
    assert g['anchor'] == ANCHOR
    stream = [tuple(g['walk_stick'])] * g['nwalk']
    s = C.rest_state(ANCHOR)
    for k, (sx, sy) in enumerate(stream):
        s.step(sx, sy, csx=128, csy=W.CDOWN)
        if k >= len(g['frames']):
            break
        yield k, s, g['frames'][k]


def test_walkstab_facing_bitexact_under_cdown():
    """FEASIBILITY: facing is 0-ULP every frame under the C-down camera pin."""
    bad = [k for k, s, lf in _replay() if (int(s.facing) & 0xFFFF) != (lf['facing'] & 0xFFFF)]
    assert not bad, "facing diverged at frames %s (C-down should pin the camera)" % bad


def test_walkstab_perp_residual_inside_razor():
    """FEASIBILITY: the from-rest position residual's PERPENDICULAR component (the razor quantity)
    stays well inside the seam's ~6e-4u offset window, every frame."""
    worst = 0.0
    for k, s, lf in _replay():
        a = (lf['facing'] & 0xFFFF) / 65536.0 * 2 * math.pi
        dsin, dcos = math.sin(a), math.cos(a)
        ex, ez = s.pos_x - lf['pos_x'], s.pos_z - lf['pos_z']
        d_perp = ex * (-dcos) + ez * dsin
        worst = max(worst, abs(d_perp))
    assert worst < RAZOR / 3.0, "perp residual %.2e u >= razor/3 (%.2e)" % (worst, RAZOR / 3.0)


@pytest.mark.xfail(reason="walk-entry foot toe-stream (m359C/f312) residual -- open Phase-R gap; "
                          "along-track so harmless to the clip (see test above)", strict=True)
def test_walkstab_full_position_bitexact():
    """The FULL position is NOT yet bit-exact from rest: the fast-walk foot toe-stream drifts
    ~0.0024u (along-track). Closing it is the Phase-R jointBeforeCB body-lean work."""
    bad = [k for k, s, lf in _replay()
           if not (_bits(s.pos_x) == _bits(lf['pos_x']) and _bits(s.pos_z) == _bits(lf['pos_z']))]
    assert not bad, "position diverged at frames %s" % bad
