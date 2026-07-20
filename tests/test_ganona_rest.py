"""The GanonA r0 TAS corner seam_0255_0256 (S=(615.5078, 948.859436035, -2383.9854), Dereck's
named target) -- the Phase G FLOORS-MODE REST gate: the from-rest walk on the micro-incline
corridor must be bit-exact INCLUDING pos_y following the floor.

strict-xfail RED until the REST golden ships: the session-65 live gate was BIT-EXACT rows 0-11
(the ground model validated live) but rows 12+ take a CC push around the PROC_STONE skull prop
standing ON the corridor at (569.72, 948.94, -2080.17) (ledger #52). Un-red by consuming the
stone in the base (mint-time setup, the #47/#49 pattern), re-minting, re-running
`python -m harness.rollstab.rest anchor=<a> geo=<g> seed=0 floors=<f> golden=fixtures/
seam255_rest_golden.json`, then REMOVING the xfail marker. Goldens are live-captured, never
edited to make the sim pass (SESSION_PROMPT hard rule).
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


@pytest.mark.xfail(strict=True,
                   reason="GanonA REST golden not yet shipped: the corridor STONE prop must be "
                          "consumed in the base, then re-mint + re-gate (ledger #52, s65 handoff)")
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
