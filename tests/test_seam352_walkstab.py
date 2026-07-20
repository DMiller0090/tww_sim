"""seam_0352_0353 (kaze r11, S=(9344.82,-373.61), interior 155.4) -- the WALK-stab novel-anchor
tier, session 72. This locks what IS done and flags what is NOT:

  * GREEN -- the from-rest WALK is BIT-EXACT (0-ULP) for a FRESHLY-MINTED novel walk-stab anchor,
    28/28 rows including the seam wall-SLIDE (the verification walk reaches the corner wall at
    d2S ~34 and slides; the gate sim runs WITH the seam walls, so it matches live -- the
    walls-aware REST gate, session 72). This proves the novel-anchor mint (mint.mint_walkstab, the
    sub-580u pan mint + the check_runway guard) + the from-rest model generalize to a novel corner:
    the earlier "camera-dirty corridor" alarm was a false positive (a pan/settle transient, NOT a
    wall collision -- the arm converges cleanly to nominal and csangle holds).

  * xfail -- the live 0-ULP CLIP is NOT yet delivered. The seam is feasibility-CONFIRMED (the shared
    seam_feasibility detector finds genuine walk-cap dust), but on the BIT-EXACT (seed=0, noops=2)
    trajectory the auto-graze steering floors the cut-ray perp at ~0.0016 (~16x the ~1e-4 f32 razor):
    the start-crawl perp perturbation washes out over the ~16-frame walk, and the along nudge (c4)
    moves d2S at FIXED facing (does not touch perp). Threading the razor needs a finer WALK-reachable
    perp knob on the true trajectory (a mid-walk partial-mag dip near the cut, or the bearing-arc
    knob) -- see the session-72 handoff. The seed=1 perp-0.000025 hits are on a 1-frame-off
    (non-deliverable) trajectory (proven by a per-frame delivery diff).

Live-captured golden -- NEVER edit the fixture to make the sim pass (tests/dolphin/README.md).
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(os.path.dirname(_HERE), 'fixtures')
_GOLD = os.path.join(_FIX, 'seam352_rest_golden.json')
_GEO = os.path.join(_FIX, 'kaze_r11_seam352_geo.json')

try:
    from harness.rollstab import rest as C
    from harness.rollstab.seamgeo import SeamGeo
    from harness.rollstab.geometry import load_seed
    _HAVE = C.rest_state is not None and os.path.exists(_GEO)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness unavailable")

ANCHOR = 'kaze_r11_walkstab_seam352@twwgz'


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _seam():
    return SeamGeo(json.load(open(_GEO)), load_seed(ANCHOR)['csangle'] & 0xFFFF)


def test_seam352_rest_bitexact():
    """From-rest walk-stab walk 0-ULP vs live, WITH the seam walls (the walk slides the corner
    wall) -- the novel-anchor mint + from-rest model generalize (session 72)."""
    assert os.path.exists(_GOLD), "seam352 REST golden not shipped"
    golden = json.load(open(_GOLD))
    assert golden['anchor'] == ANCHOR and golden.get('seed') == 0
    sg = _seam()
    stream = ([tuple(golden['straight'])] * golden['NPREF']
              + [tuple(golden['aim'])] * golden['NCRUISE'])
    s = C.rest_state(ANCHOR, dtm_seed=0, walls=sg.TRIS)
    frames = golden['frames']
    matched, bad = 0, []
    for k, (sx, sy) in enumerate(stream):
        s.step(sx, sy)
        if k >= len(frames):
            break
        lf = frames[k]
        st = s._foot.st
        matched += 1
        ok = (_bits(s.pos_x) == _bits(lf['pos_x']) and _bits(s.pos_z) == _bits(lf['pos_z'])
              and _bits(st.fc0.frame) == _bits(lf['d_frame'])
              and _bits(st.fc1.frame) == _bits(lf['w_frame'])
              and _bits(s._foot.prev_f312) == _bits(lf['m359C']))
        if not ok:
            bad.append(k)
    assert matched >= 24, "too few rows matched (%d)" % matched
    assert not bad, "seam352 walls-aware from-rest diverged at rows %s" % bad


@pytest.mark.xfail(reason="seam352 clip not delivered: auto-graze perp floors ~0.0016 (16x razor) "
                          "on the bit-exact trajectory; needs a finer walk-reachable perp knob "
                          "(session-72 handoff)", strict=True)
def test_seam352_clip_delivered():
    """RED until the walk-stab clip is delivered live 0-ULP (a ship golden is written)."""
    assert os.path.exists(os.path.join(_FIX, 'seam352_walkstab_ship_golden.json')), \
        "seam352 clip not delivered yet"
