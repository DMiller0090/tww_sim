"""Sheathed roll-stab CLIP regression (kaze r11; session 39).

Milestone: route a NOT-DRAWN (sheathed) anchor's ROLL verdict to a from-rest roll-stab clip at the
kaze roll seam. Session 38 made `kaze_r11_rollstab_sheathed@twwgz` REST BIT-EXACT; session 39 SOLVED
a from-rest genuine clip (found in the sim, warm-started from the same-seam idle13 recipe) and it
passes the OFFLINE ship gate 0-ULP -- but the LIVE delivery is BLOCKED by a sim MOVE-turn residual.

Recipe (pure sim, from the anchor seed only -- no calibration): A_proj=-500, draw_at=3, a K=2 crawl
+ arc + 2 fines. The offline gate is bit-exact and genuine; see `harness/rollstab/deliver.py`.

THE LIVE BLOCKER (session 40 RE-ROOT-CAUSED, jitter-immune, overturns the session-39 "MOVE-turn
settle" story -- fixture `fixtures/sheathed_roll_ship_jitterproof.json`, game_frame-tagged so run_dtm
poll jitter cannot misalign it): rows 0-17 deliver bit-exact live. At ROW 18 the acted stick is the
fine (96,192), whose decoded msd is 0.9605 -- IN the (0.889,1.0) PADClamp band the freeze planner
already excludes (see precise-stop.md). The sim decodes that 1-frame stick to its raw value
(target 33367, msd 0.9605) and turns; but LIVE decodes a 1-FRAME TRANSIENT band stick to ~aim
(target 33295, msd 1.0 -- it holds the prior value) so live does NOT turn. (HELD 8 frames, (96,192)
decodes live to its true 0.9605 -- so it is a transient/input-layer effect, not the closed-form
decode, which is bit-exact live.) The two-angle chase is FAITHFUL (it follows target; target diverges
because the transient-band decode diverges). Non-band 1-frame fines ((98,188), (99,183)) register
correctly live. NOT the two-angle/MOVE-turn settle residual (dead-end #31 corrected).

CONSEQUENCE (for THIS hit, not the clip): the session-39 winning hit's genuine landing depends on the
sim treating that transient band stick as a real perp nudge, which live reads as ~aim -- so the sim
must be made band-FAITHFUL before its hits are trustworthy, and a new band-faithful solve is what
delivers. The pure live-valid lattices tried reached ~0.0013u from the f32 dust (0 genuine over ~60k
runs) -- that bounds the SHAPES tried, not the clip; a richer alphabet / faithful band model is the
untried lever. See README ## Status (session 40) + dead-end #32 for the open approaches.

The live golden is IMMUTABLE -- never edit the fixture to make the sim pass. `test_sheathed_offline_
clip_bitexact` (GREEN) guards the solve; the xfail RED test flips GREEN once the sim models the
transient-band input-layer decode to f32 (and a band-faithful hit is re-solved).
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


@pytest.mark.xfail(strict=True, reason="transient (0.889,1.0)-band stick (96,192) at ship row 18 "
                                       "decodes live to ~aim, not its raw msd; sim decodes it raw -> "
                                       "row-18 divergence (session 40, jitter-immune; dead-end #31)")
def test_sheathed_ship_matches_live():
    """Live-golden regression: the sim's from-rest replay of the ship stream must match the live
    trace BIT-EXACT on every row (pos + shape + travel). It diverges at row 18 -- the acted stick
    there is the band fine (96,192), which the sim decodes raw but live (1-frame transient) reads as
    ~aim. Flips GREEN only if the sim models the transient-band input-layer decode to f32."""
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
