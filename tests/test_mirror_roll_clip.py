"""Phase-5 "generalization works" proof: a NOVEL kaze r11 seam solved by the GENERALIZED roll solver.

Target = the MIRROR-ROLL corner S=(9069.9043, -265.9138), interior 109.4 (a genuinely distinct seam
from the proven roll seam at +259, mirrored across z; walls 355 x 357), reached by a FRESH live-minted
anchor `kaze_r11_rollstab_mirror@twwgz`. This is the first exercise of the SeamGeo-generalized solver on
a seam it was never hardcoded to. (The distinct 97deg corner S=(13539.24,493.36) Dereck first picked was
ruled out by a dedicated search -- no CrrPos-missing gap at any displacement; see the dead-end ledger.)

Session 50 status: the anchor is REST BIT-EXACT (golden below) and the seam is geometrically feasible
(74 f32 dust hits ~ the proven seam's 95). Two real Phase-5 solver gaps were fixed to reach here:
`solver.run` aimed the approach at the hardcoded `geometry.F` (walked a novel seam the wrong way) -> now
aims `seam.F`; and the hardcoded A_projs are anchor-DISTANCE specific -> `solver._derive_a_projs` brackets
the reach band per anchor. The LIVE CLIP itself is NOT yet delivered -- the cold search hits the same
octagon-clamp reachable-lattice DENSITY WALL as the sheathed roll (dead-ends #29/#32); it needs the
walkstab-style K=3-byte densifier or a focused warm-start recipe. `test_mirror_clip_delivered` is RED
(strict-xfail) until then.

Goldens are live-captured, never edited to make the sim pass (SESSION_PROMPT hard rule).
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOLD = os.path.join(os.path.dirname(_HERE), 'fixtures', 'mirror_roll_rest_golden.json')

try:
    from harness.rollstab import rest as C
    _HAVE = C.rest_state is not None and os.path.exists(_GOLD)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / mirror golden unavailable")

ANCHOR = 'kaze_r11_rollstab_mirror@twwgz'


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def test_mirror_rest_bitexact():
    """The fresh live-minted novel-seam anchor is REST BIT-EXACT (0 ULP) from rest through the walk
    approach into the corner -- the precondition for any solved clip to deliver 0-ULP. Delivered with
    C-down every frame + seed=0 (noops = rest_noops(1) + (1-seed) = 2). Straight into-corner walk
    (the anchor faces the corner, so straight == the aim). Index-aligned vs the live golden."""
    golden = json.load(open(_GOLD))
    assert golden['anchor'] == ANCHOR and golden.get('seed') == 0
    sx0, sy0 = golden['straight']
    stream = [(sx0, sy0)] * (golden['NPREF'] + golden['NCRUISE'])
    s = C.rest_state(ANCHOR, dtm_seed=0)
    frames = golden['frames']
    matched, bad = 0, []
    for k, (sx, sy) in enumerate(stream):
        s.step(sx, sy)
        if k >= len(frames):
            break
        lf = frames[k]
        st = s._foot.st
        matched += 1
        if not (_bits(s.pos_x) == _bits(lf['pos_x']) and _bits(s.pos_z) == _bits(lf['pos_z'])
                and _bits(st.fc0.frame) == _bits(lf['d_frame'])
                and _bits(st.fc1.frame) == _bits(lf['w_frame'])
                and _bits(s._foot.prev_f312) == _bits(lf['m359C'])):
            bad.append(k)
    assert matched >= 24, "too few rows matched (%d)" % matched
    assert not bad, "mirror from-rest diverged at rows %s" % bad


@pytest.mark.xfail(strict=True, reason="novel-seam live clip not yet delivered: cold search hits the "
                                       "octagon-clamp reachable-lattice density wall (dead-ends #29/#32); "
                                       "needs the K=3-byte densifier / a focused recipe, then a live DTM")
def test_mirror_clip_delivered():
    """RED until the mirror-seam roll-stab clip is delivered LIVE 0-ULP (the Phase-5 proof). Flips
    GREEN when a genuine wall-faithful hit ships via a clean DTM and reproduces bit-for-bit live."""
    p = os.path.join(os.path.dirname(_HERE), 'fixtures', 'mirror_roll_ship_golden.json')
    assert os.path.exists(p), "no shipped mirror clip golden yet"
