"""The DISTINCT 97-deg corner S=(13539.24, 493.36), interior 97.0, walls 871 x 899 -- Dereck's target.

Session 51 overturned the "infeasible" ruling GEOMETRICALLY: `SeamGeo.pred_genuine` (the exact sim cut)
confirms a genuine razor at a ~90-deg GRAZING aim (facing 16306 at csangle 29883, ~41deg off the interior
bisector; geo `fixtures/kaze_r11_seam97_geo.json`, which now DECLARES `aim_deg=90`). Session 52 minted a
REST-BIT-EXACT anchor there and ran the solver -- 0 wall-faithful hits so far.

Why the search has not delivered yet (the open puzzle for the next session, NOT a proof of impossibility --
`pred_genuine` verifies the clip EXISTS, so this is a search/model gap per Dereck):
  * The verified-genuine dust is confined to <=5.4u in front of wallA (the razor runs ~parallel to wallA,
    which the roll aims nearly along).
  * The walled roll holds Link's center 35u off wallA (WallCorrect wall_r=35, collision.py) -- so the
    grazing roll is pushed ~30u off the razor before the CUT. A 108-sample x all-aims scan of the REACHABLE
    corner mouth (>=35u from BOTH walls) found 0 genuine points.
  * Dereck's steers: (1) a verified clip means the SEARCH must find it, never conclude impossible; (2) on a
    CONCAVE corner (this is one, interior 97) the roll MAY touch/slide along walls -- only a BONK
    (FRONT_ROLL_CRASH) disqualifies. The current `solver.wall_faithful` rejects on ANY `wall_hit`, which is
    too strict for a concave corner -- relaxing it to reject only bonks is the first fix to try. Also OPEN:
    the roll-near-concave-corner wall behaviour is NOT yet verified against live (the walk verification only
    reached ~x13290, before the corner) -- confirm whether live holds Link 35u off wallA or lets him closer.

Goldens are live-captured, never edited to make the sim pass (SESSION_PROMPT hard rule).
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOLD = os.path.join(os.path.dirname(_HERE), 'fixtures', 'seam97_rest_golden.json')
_GEO = os.path.join(os.path.dirname(_HERE), 'fixtures', 'kaze_r11_seam97_geo.json')

try:
    from harness.rollstab import rest as C
    _HAVE = C.rest_state is not None and os.path.exists(_GOLD)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / seam97 golden unavailable")

ANCHOR = 'kaze_r11_rollstab_seam97@twwgz'


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def test_seam97_rest_bitexact_walled():
    """The fresh 97-corner anchor is REST BIT-EXACT (0 ULP) from rest through the walk approach WHEN
    WALLS ARE INCLUDED -- the straight +X approach at z~489 grazes wallA (871) near the corner, so the
    wall-less sim diverges at ~row 24 but the WALLED sim (walls=seam.TRIS) reproduces the live clean-DTM
    every row. This is the precondition for any solved clip to deliver 0-ULP. Delivered C-down every
    frame + seed=0 (noops=2). The anchor rests facing F (16306), so straight == aim. Index-aligned vs
    the live golden. NOTE the mint recipe (session 52): a NOVEL anchor at a FIXED-camera seam must be a
    GENUINELY aligned idle (travel_angle == facing); a teleport-rotated idle inherits the base idle's
    travel_angle and arcs off-course. Recipe: align-walk toward F -> settle to idle -> teleport to rest
    (preserves the aligned idle) -> mint_current."""
    from harness.rollstab.seamgeo import SeamGeo
    from harness.rollstab import geometry as G
    golden = json.load(open(_GOLD))
    assert golden['anchor'] == ANCHOR and golden.get('seed') == 0
    cs = G.load_seed(ANCHOR)['csangle'] & 0xFFFF
    seam = SeamGeo(json.load(open(_GEO)), csangle=cs)      # aim_deg=90 read from the fixture
    assert seam.F == golden['F'] == 16306
    sx0, sy0 = golden['straight']
    stream = [(sx0, sy0)] * (golden['NPREF'] + golden['NCRUISE'])
    s = C.rest_state(ANCHOR, walls=seam.TRIS, dtm_seed=0)
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
    assert matched >= 28, "too few rows matched (%d)" % matched
    assert not bad, "seam97 walled from-rest diverged at rows %s" % bad


_SHIP = os.path.join(os.path.dirname(_HERE), 'fixtures', 'seam97_ship_golden.json')


@pytest.mark.xfail(reason="97-corner clip not yet delivered -- search has not found a wall-faithful "
                          "reachable path to the verified-genuine dust (see module docstring)", strict=True)
def test_seam97_clip_delivered():
    """RED until the 97-corner clip is delivered LIVE 0-ULP. Flip GREEN by producing a
    `fixtures/seam97_ship_golden.json` from a clean-DTM ship (mirror `test_mirror_clip_delivered`)."""
    assert os.path.exists(_SHIP), "no seam97 ship golden yet -- the clip is not delivered"
