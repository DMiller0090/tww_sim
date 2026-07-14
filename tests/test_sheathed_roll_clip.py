"""Sheathed roll-stab CLIP regression (kaze r11; sessions 39-41).

Milestone: route a NOT-DRAWN (sheathed) anchor's ROLL verdict to a from-rest roll-stab clip at the
kaze roll seam. Session 38 made `kaze_r11_rollstab_sheathed@twwgz` REST BIT-EXACT; session 39 SOLVED
a from-rest genuine clip (found in the sim, warm-started from the same-seam idle13 recipe) and it
passes the OFFLINE ship gate 0-ULP -- but the LIVE delivery does NOT clip.

Recipe (pure sim, from the anchor seed only -- no calibration): A_proj=-500, draw_at=3, a K=2 crawl
+ arc + 2 fines. The offline gate is bit-exact and genuine; see `harness/rollstab/deliver.py`.

ROOT CAUSE (session 42, RAM-CONFIRMED -- this overturns session 41's "band walk-speed" story, which
was itself a correction of #31/#32): the live miss is a make_dtm DELIVERY DROP, NOT a Link-physics or
stick-decode gap. Reading `g_mDoCPd_cpadInfo[0].mMainStickValue` (@JP 0x80398310 -- the RAW SI-delivered
pad the game actually polls, BEFORE setStickData latches it) directly, per game frame, proved:
  * The decomp physics + decode are FAITHFUL. Every function in the row-18 path (setStickData 10569,
    setNormalSpeedF 2301, setSpeedAndAngleNormal 2751, setBlendMoveAnime m3598, the 0.3/0.7 toe
    recursion 2399-2484) matches the sim line-for-line; PADRead->PADClamp->CStick::update is stateless.
  * The stick decode is faithful even for Y>=192 when ISOLATED: a 1-frame (96,192) after plain cruise
    delivers cpad_val=0.9605 (== the sim) and dips. So there is NO band-walk-speed gap to model.
  * But in the SHIP, the band fine at fed-index 16 (acted row 18) is NEVER RECEIVED: the game polls its
    FULL neighbour (cpad_val=1.0, px=-0.32) instead. This is make_dtm's poll-cadence: the pipeline
    default `make_dtm(polls=4, seed=1)` drops a 1-frame partial fine that is CLUSTERED after other
    partials (the arc + earlier fines induce a sub-frame phase slip). A distinctive px=0 marker at
    fed-16 ALSO drops (positional, not value-specific); an all-full ramp delivers every frame cleanly.
  * That single dropped dip is the ENTIRE 1.9125u miss (offline: forcing the row-18 stick to full
    shifts along-track by exactly -1.91248u -> live old_z 306.116 == sim 308.028 minus that).

THE FIX (session 42, characterized live -- not yet shipped): `make_dtm(seed=0)` DELIVERS the dropped
band at the SAME timing (roll row unchanged); `polls=8` delivers but at 2x timing (breaks the plan's
discrete B/A). seed=0 alone still leaves a ~0.6u residual because it shifts the leading-poll layout the
from-rest prefix (rest_noops, session 38) was calibrated to -- so the clean fix is `seed=0` PLUS
re-deriving rest_noops for the seed-0 layout, then re-verify REST BIT-EXACT and the session-39 hit
should clip. Diagnostic tool: `harness.rollstab.capture_decode.delivery_sweep` (`... capture_decode
sweep`) -- reports which fines the game receives per (polls,seed) + roll-row + OOB clip. The
`fine_family` band-exclusion (solver.py, session 41) is NOT the fix (it removes usable density); it
should be REMOVED once make_dtm delivers band fines faithfully.

The live golden is IMMUTABLE (`fixtures/sheathed_roll_ship_jitterproof.json`, game_frame-tagged so
run_dtm poll jitter cannot misalign it) -- never edit it to make the sim pass. It records the BUGGY
seed=1 delivery (band dropped); the sim (which acts every authored frame) correctly does NOT match it
until make_dtm delivers every frame.
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


@pytest.mark.xfail(strict=True, reason="make_dtm DELIVERY DROP (RAM-confirmed, session 42), NOT a sim "
                                       "gap: the pipeline default make_dtm(polls=4, seed=1) drops the "
                                       "clustered 1-frame band fine at row 18 -- the game polls its full "
                                       "neighbour (cpad_val 1.0 not 0.9605), so live holds speedF 17 "
                                       "where the sim (correctly acting the delivered band) dips to "
                                       "15.091 -> a 1.9u along-track lag frozen through the roll. The "
                                       "sim/decomp are faithful; the golden records the buggy delivery. "
                                       "Fix: make_dtm seed=0 + re-derive rest_noops (see module "
                                       "docstring); validate with capture_decode.delivery_sweep.")
def test_sheathed_ship_delivery():
    """RED (the make_dtm delivery bug, session 42): replay the sheathed hit's stream from rest and
    compare the along-track z to the jitter-immune live golden, game_frame-aligned (sim row i <-> live
    gf = liveMOVE + 2*(i - simMOVE); the emulator counter ticks twice per game frame). z is robust to
    a ±1 misalignment (that would show as a ~17u step, not the 1.9u we see). Bit-exact through row 17,
    then at row 18 the sim dips speedF (it acts the band fine make_dtm authored) while the console held
    17 (that fine was DROPPED in delivery -- polls=4/seed=1 phase slip). This test flips GREEN when
    make_dtm delivers every authored frame (seed=0 + rest_noops re-derived) so live == the sim, which
    is the objective (pure-sim -> DTM that reproduces it). NOT a sim/physics change (RAM-confirmed)."""
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
