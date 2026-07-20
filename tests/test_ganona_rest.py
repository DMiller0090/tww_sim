"""The GanonA r0 TAS corner seam_0255_0256 (S=(615.5078, 948.859436035, -2383.9854), Dereck's
named target) -- the Phase G FLOORS-MODE REST gate: the from-rest walk on the micro-incline
corridor must be bit-exact INCLUDING pos_y following the floor.

GREEN as of session 66: the corridor PROC_STONE (ledger #52) is AVOIDED, never touched -- the
geo fixture declares aim_deg=186.5 (the stone sits 16u off the interior-bisector line but
77.8u off this one; the minted rest track clears it by 124.6u) -- and the anchor re-minted at
the cam-screened frozen pan target 25951 (csangle 21121 frozen through the whole approach; the
default aim target's cam leash CREEPS on this corridor and breaks the stick decode). The last
two ground terms were then modeled decomp-first: setStepsOffset's m35C4 walk base-Y lift
(0.7 * per-frame downhill dy rides the draw base, d_a_player_main.cpp:9524/:9561) and
footBgCheck's non-plant field_0x030 CLOTCH leg lift (0.3f * ground clearance, :8816, consumed
by jointBeforeCB :276/:282). Golden = the live clean-DTM capture, 28/28 rows 0-ULP incl.
m359C + pos_y. Goldens are live-captured, never edited to make the sim pass (SESSION_PROMPT
hard rule).
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(os.path.dirname(_HERE), 'fixtures')
_GOLD = os.path.join(_FIX, 'seam255_rest_golden.json')
_FLOORS = os.path.join(_FIX, 'ganona_r0_floors.json')

try:
    from harness.rollstab import rest as C
    _HAVE = C.rest_state is not None and os.path.exists(_FLOORS)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / GanonA floors mesh unavailable")

ANCHOR = 'ganona_r0_rollstab_seam255@twwgz'


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def test_seam255_rest_bitexact():
    """Floors-mode from-rest 0-ULP on the GanonA incline corridor, pos_y included."""
    assert os.path.exists(_GOLD), "REST golden not shipped (stone prop, ledger #52)"
    golden = json.load(open(_GOLD))
    assert golden['anchor'] == ANCHOR and golden.get('seed') == 0
    stream = ([tuple(golden['straight'])] * golden['NPREF']
              + [tuple(golden['aim'])] * golden['NCRUISE'])
    s = C.rest_state(ANCHOR, dtm_seed=0, floors=_FLOORS)
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
        if lf.get('pos_y') is not None:
            ok = ok and _bits(s.pos_y) == _bits(lf['pos_y'])
        if not ok:
            bad.append(k)
    assert matched >= 24, "too few rows matched (%d)" % matched
    assert not bad, "seam255 floors-mode from-rest diverged at rows %s" % bad
