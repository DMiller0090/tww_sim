"""Walk-stab seam-clip: solver/acceptance gates + the live-delivery status (session 31).

WHAT THIS LOCKS:
  * GREEN -- `build_stream` is DELIVERY-FAITHFUL: the per-byte fine nudge is applied to the raw
    authored byte, clamped to [0,255], then run through dtm_make's calibration, so every stick the
    solver tests is one a clean DTM can actually deliver (bytes in [1,254]). The session-30 code
    nudged a post-calibration byte, which could overflow 255 (a non-deliverable stick).
  * GREEN -- the acceptance geometry: the genuine seam-clip sliver confirmed pure-geometry near
    old=(9011.117,1352.468) IS classified genuine, and stepping ~2.2e-4u off it perpendicular is
    blocked (the f32 razor). This is the target the walk must land `old` on.
  * RED (xfail) -- the LIVE clip is not yet re-delivered. The session-30 "walk-entry foot residual"
    was root-caused (session 31) to the wrong anim set (sword-drawn WALKS/DASHS vs the item-holding
    base WALK/DASH) and FIXED -- the from-rest walk is now 0-ULP (tests/test_walkstab_rest.py), and a
    turning walk is 0-ULP live through the pre-wall frames. So any genuine OFFLINE clip is now a true
    one-shot. The remaining work is purely SEARCH: the session-30 hit no longer clips (the fix shifts
    `old` ~2-3 f32 columns off its sliver), and a deliverable N<=12 hit must be re-found with a fast
    search (see the session-31 handoff). Flips to PASS when a committed hit is delivered live.
"""
import math
import struct

import pytest

try:
    from harness.rollstab import walkstab as W
    from harness.rollstab import rest as C
    from tww_sim.core.fp import f32 as _f
    _HAVE = C.rest_state is not None
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / anim data unavailable")

# Confirmed pure-geometry genuine sliver (session 30/31; ~2.2e-4u wide, flanked by CrrPos-blocked).
# old->new is the exact CUT_F lunge at the walk facing -- the real target the walk must reach.
SLIVER_OLD = (9011.1171875, 1352.4676513671875)
SLIVER_NEW = (9031.6611328125, 1387.0457763671875)


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def test_walkstab_build_stream_deliverable():
    """Every stick build_stream emits -- with or without a fine nudge -- is DELIVERABLE (a clean DTM
    delivers bytes in [1,254]; dtm_make maps 0->1, 255->254). A nudge must never yield a byte a DTM
    cannot produce."""
    bad = []
    for fdx in (-8, -4, 0, 4, 8):
        for fdz in (-8, -4, 0, 4, 8):
            sticks = W.build_stream(5560, (0.52, 0.68, 0.52), 760, 5, 3, 7, fdx, fdz)
            for (bx, by) in sticks:
                if not (1 <= bx <= 254 and 1 <= by <= 254):
                    bad.append((fdx, fdz, bx, by))
    assert not bad, "build_stream emitted non-deliverable bytes: %s" % bad[:5]


def test_walkstab_genuine_sliver_present():
    """The acceptance geometry: the confirmed sliver is genuine, and a ~2.2e-4u perpendicular step
    off it is blocked (the f32 razor the search must thread)."""
    ok, why = W.genuine_clip(SLIVER_OLD, SLIVER_NEW)
    assert ok, "the confirmed genuine sliver is not genuine (why=%s)" % why
    # step perpendicular to the lunge until it stops clipping -> a razor, not a plateau
    lunge = (SLIVER_NEW[0] - SLIVER_OLD[0], SLIVER_NEW[1] - SLIVER_OLD[1])
    a = math.atan2(lunge[0], lunge[1])
    pdx, pdz = -math.cos(a), math.sin(a)
    far = (_f(SLIVER_OLD[0] + _f(0.001 * pdx)), _f(SLIVER_OLD[1] + _f(0.001 * pdz)))
    farn = (_f(far[0] + _f(lunge[0])), _f(far[1] + _f(lunge[1])))
    assert not W.genuine_clip(far, farn)[0], "0.001u off perpendicular still clips -- not a razor"


def test_walkstab_sim_reproduces_sliver_is_geometry_only():
    """Guard: the sliver classification is pure geometry (independent of the sim), so it stays valid
    as the from-rest sim / solver evolve. `new` == f32(old + lunge) bit-for-bit."""
    lunge = (_f(SLIVER_NEW[0] - SLIVER_OLD[0]), _f(SLIVER_NEW[1] - SLIVER_OLD[1]))
    recon = (_f(SLIVER_OLD[0] + lunge[0]), _f(SLIVER_OLD[1] + lunge[1]))
    assert _bits(recon[0]) == _bits(SLIVER_NEW[0]) and _bits(recon[1]) == _bits(SLIVER_NEW[1])


@pytest.mark.xfail(reason="live clip not yet re-delivered: the from-rest sim is 0-ULP (sword fix, "
                          "session 31) so any genuine offline clip is a true one-shot, but a "
                          "DELIVERABLE N<=12 hit must be re-found via a fast search (the session-30 "
                          "hit no longer clips). Flips to PASS when a committed hit lands live.",
                   strict=True)
def test_walkstab_live_delivery_clips():
    """Placeholder for the delivered clip: assert a committed deliverable hit clips 0-ULP live.
    XFAIL until the fast search finds one and it is delivered + captured as a golden."""
    import os
    import json
    hits = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        '_generated', 'walkstab_hits.json')
    assert os.path.exists(hits), "no committed deliverable walk-stab hit yet"
    hit = json.load(open(hits))[0]
    # a real (committed) hit would be validated against its live golden here.
    assert hit.get('delivered') is True, "hit not yet live-delivered"
