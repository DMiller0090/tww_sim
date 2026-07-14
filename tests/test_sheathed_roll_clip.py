"""Sheathed roll-stab CLIP regression (kaze r11; sessions 39-41).

Milestone: route a NOT-DRAWN (sheathed) anchor's ROLL verdict to a from-rest roll-stab clip at the
kaze roll seam. Session 38 made `kaze_r11_rollstab_sheathed@twwgz` REST BIT-EXACT; session 39 SOLVED
a from-rest genuine clip (found in the sim, warm-started from the same-seam idle13 recipe) and it
passes the OFFLINE ship gate 0-ULP -- but the LIVE delivery does NOT clip.

Recipe (pure sim, from the anchor seed only -- no calibration): A_proj=-500, draw_at=3, a K=2 crawl
+ arc + 2 fines. The offline gate is bit-exact and genuine; see `harness/rollstab/deliver.py`.

ROOT CAUSE (session 41, RE-ROOT-CAUSED jitter-immune -- overturns BOTH dead-end #31 (MOVE-turn
overshoot) AND #32 (band-decode "holds prior"), which were ±1-frame misreads of run_dtm's jittery
per-frame log): the live miss is a ONE-FRAME along-track (speedF) deficit, NOT a facing/decode error.
At ship row 18 the acted stick is the fine (96,192), a PARTIAL-magnitude "band" stick (decoded
msd 0.9605, in the (0.889,1.0) PADClamp band the KB bans -- precise-stop.md "never emit Y 192-254").
At the speed cap the sim reduces the walk-speed target to msd^2*max = 15.68 (setNormalSpeedF,
d_a_player_main.cpp:2306) and dips speedF 17->15.091 for that frame; the CONSOLE does NOT dip for a
1-frame band stick at cap (it holds 17.0). That one frame's ~1.9u deficit FREEZES through the roll ->
`old` lands 1.9u short -> off the f32 razor -> no clip. Proven:
  * the DECODE is faithful even for band 1-frame transients (deterministic stopped-position probe,
    session 41: (96,192) live stopped pos == the sim's raw-decode prediction, 0 ULP);
  * the divergence is purely ALONG-TRACK (z/speed): perp x matches to 0.02u, and gf-aligned z vs the
    jitter-immune golden is bit-exact rows 0-17, diverging only at row 18's speed (below);
  * mStickDistance IS the divergence: setStickData (d_a_player_main.cpp:10569) sets it from
    `g_mDoCPd_cpadInfo[0].mMainStickValue`; for a band magnitude the console's effective walk-speed
    differs from the sim's `min(hypot(clamped)/54, 1)` -> msd^2 model (precise-stop.md's held example
    (128,196): console 15.76 vs sim 16.38). THE SIM IS NOT MODELING THE CONSOLE'S BAND WALK-SPEED.

NEXT SESSION (Dereck's directive: model what the sim isn't modeling): resolve `test_sheathed_band_
speed_at_cap` (below, RED) by modeling the console's band-magnitude walk speed to f32 -- decomp-first
from setStickData / mMainStickValue near the cap (JUTGamePad::CStick::update value, PADClamp), then
live-confirm. Once faithful, the solver can USE band sticks again (restoring the near-full-magnitude
fine-perp density the band-free search lacks -- session 40 stalled at 0.0013u from the dust), re-solve,
and deliver. The `fine_family` band-exclusion (solver.py, session 41) is the interim workaround.

The live golden is IMMUTABLE (`fixtures/sheathed_roll_ship_jitterproof.json`, game_frame-tagged so
run_dtm poll jitter cannot misalign it) -- never edit it to make the sim pass.
"""
import json
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FX = os.path.join(os.path.dirname(_HERE), 'fixtures', 'sheathed_roll_ship_jitterproof.json')

try:
    from harness.rollstab import solver as SV
    from harness.rollstab import geometry as G
    from harness.rollstab import rest as C
    from tww_sim.core.fp import f32 as _f
    _HAVE = os.path.exists(_FX)
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / sheathed jitterproof golden unavailable")

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


@pytest.mark.xfail(strict=True, reason="the sim is not modeling the console's BAND-magnitude walk "
                                       "speed: a 1-frame band stick (96,192) at cap makes the sim dip "
                                       "speedF to msd^2*max (17->15.091) but the console holds 17.0, so "
                                       "the sim's along-track z lags 1.9u from row 18 through the roll. "
                                       "Resolve by modeling mStickDistance/walk-speed near the cap to "
                                       "f32 (decomp: setStickData/mMainStickValue). Session 41.")
def test_sheathed_band_speed_at_cap():
    """RED (the discrepancy to model next session): replay the sheathed hit's stream from rest and
    compare the along-track z to the jitter-immune live golden, game_frame-aligned (sim row i <-> live
    gf = liveMOVE + 2*(i - simMOVE); the emulator counter ticks twice per game frame). z is robust to
    a ±1 misalignment (that would show as a ~17u step, not the 1.9u we see), so this isolates the real
    physics gap: everything is bit-exact through row 17, then at row 18 (the band fine (96,192) at cap)
    the sim dips speedF while the console does not -> a frozen ~1.9u along-track lag -> `old` off the
    razor. Flip GREEN by modeling the console's band walk-speed to f32 (see the module docstring)."""
    g = json.load(open(_FX))
    live = {r['gf']: r for r in g['rows']}
    r = _run()
    stream = [tuple(x) for x in r['stream']]
    s = C.rest_state(ANCHOR)
    sim = []
    for sx, sy, b in stream:
        s.step(sx, sy, buttons=b)
        sim.append((s.state & 0xFF, s.pos_x, s.pos_z))
    sim_move = next(i for i, x in enumerate(sim) if x[0] == 6)          # first MOVE proc
    live_move = next(rr['gf'] for rr in g['rows'] if rr['proc'] == 6)
    bad = []
    for i, (st, px, pz) in enumerate(sim):
        gf = live_move + 2 * (i - sim_move)
        lv = live.get(gf)
        if lv is None:
            continue
        if not (_bits(pz) == _bits(lv['z']) and _bits(px) == _bits(lv['x'])):
            bad.append((i, gf, round(pz - lv['z'], 4)))
    assert not bad, "sim along-track diverged from live (band walk-speed not modeled) at %s" % bad
