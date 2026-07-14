"""Sheathed roll-stab CLIP regression (kaze r11; session 39).

Milestone: route a NOT-DRAWN (sheathed) anchor's ROLL verdict to a from-rest roll-stab clip at the
kaze roll seam. Session 38 made `kaze_r11_rollstab_sheathed@twwgz` REST BIT-EXACT; session 39 SOLVED
a from-rest genuine clip (found in the sim, warm-started from the same-seam idle13 recipe) and it
passes the OFFLINE ship gate 0-ULP -- but the LIVE delivery is BLOCKED by a sim MOVE-turn residual.

Recipe (pure sim, from the anchor seed only -- no calibration): A_proj=-500, draw_at=3, a K=2 crawl
+ arc + 2 fines. The offline gate is bit-exact and genuine; see `harness/rollstab/deliver.py`.

THE LIVE BLOCKER (session 39, root-caused by per-frame sim-vs-live diff, fixture
`fixtures/sheathed_roll_ship_live.json`): rows 0-17 of the ship stream (crawl, draw B-edge, arc,
fines) deliver BIT-EXACT live -- so delivery alignment / rest_noops are correct. At ROW 18 (an aim
frame after the row-16 fine settles) the SIM's shape_angle OVERSHOOTS to 33367 while live holds 33295;
that phantom one-frame turn dips speedF to 15.05 vs live's 17.0 cap -> a ~1.9u along-track lag that
freezes for the rest of the roll -> `old` lands off the f32 razor -> no live clip. Discriminator ruled
it a two-angle/MOVE-turn SETTLE residual, NOT an input-delay/buffering shift (live does not lead the
sim by a frame). It afflicts the drawn idle13 hit identically. This is the Phase-R MOVE-turn frontier.

The live golden is IMMUTABLE -- never edit the fixture to make the sim pass; the fault is the sim
turn model. `test_sheathed_offline_clip_bitexact` (GREEN) guards the solve; the xfail RED test flips
GREEN when the sim reproduces the row-18 facing settle live.
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FX = os.path.join(os.path.dirname(_HERE), 'fixtures', 'sheathed_roll_ship_live.json')

try:
    from harness.rollstab import solver as SV
    from harness.rollstab import geometry as G
    from tww_sim.core.fp import f32 as _f
    _HAVE = os.path.exists(_FX)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / sheathed ship fixture unavailable")

ANCHOR = 'kaze_r11_rollstab_sheathed@twwgz'
A_PROJ = -500.0
DRAW_AT = 3
MOVES = ((9, (73, 254), 2), (10, (99, 183)), (4, (96, 192)), (6, (98, 188)))
START = ((77, 249), (98, 191))
MARGIN_Z = 0.0002


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _run():
    return SV.run(ANCHOR, MOVES, A_proj=A_PROJ, start=START, draw_at=DRAW_AT)


def test_sheathed_offline_clip_bitexact():
    """The SOLVE is real: the from-rest sheathed run fires a genuine, wall-clear roll-stab CUT at the
    17-cap (full 49.22 lunge) toward the seam facing, and the exact `old` is sliver-robust. Pure sim,
    from the anchor seed only (session 39)."""
    r = _run()
    assert r is not None and r.get('fired'), "sheathed roll-stab CUT did not fire from rest"
    assert r['facing'] == G.F
    assert r['spF_at_A'] == 17.0, "walk not at cap at the A press -> shrunken lunge"
    assert r['genuine'] and r['clear'], "not a genuine, wall-clear clip"
    assert abs(r['disp'] - 49.2202) < 1e-3
    # sliver robustness (deliver.py gate): pred_genuine holds at old_z +- MARGIN_Z
    assert G.pred_genuine((r['old'][0], _f(r['old'][1] + MARGIN_Z)))
    assert G.pred_genuine((r['old'][0], _f(r['old'][1] - MARGIN_Z)))


@pytest.mark.xfail(strict=True, reason="sim MOVE-turn facing overshoot at ship row 18 (Phase-R); "
                                       "blocks the live sheathed roll-stab clip -- session 39")
def test_sheathed_ship_matches_live():
    """Live-golden regression: the sim's from-rest replay of the ship stream must match the live
    trace BIT-EXACT on every row (pos + shape + travel). It currently diverges at row 18 (the sim
    facing overshoot); this flips GREEN when the sim turn model reproduces the row-18 settle live."""
    fx = json.load(open(_FX))
    assert fx['anchor'] == ANCHOR
    r = _run()
    stream = [tuple(x) for x in r['stream']]
    assert [list(x) for x in stream] == fx['stream'], "recipe stream drifted from the captured fixture"
    # replay from rest, compare to the live rows (live frame r+1 <-> sim row r, baked into the fixture)
    from harness.rollstab import rest as C
    s = C.rest_state(ANCHOR)
    bad = []
    for row in fx['rows']:
        s.step(*row['input'][:2], buttons=row['input'][2])
        lv = row['live']
        if lv is None:
            continue
        if not (_bits(s.pos_x) == _bits(lv['pos_x']) and _bits(s.pos_z) == _bits(lv['pos_z'])
                and (s.facing & 0xFFFF) == lv['shape'] and (s.travel & 0xFFFF) == lv['travel']):
            bad.append(row['row'])
    assert not bad, "sheathed ship stream diverged from live at rows %s" % bad
