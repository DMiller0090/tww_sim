"""Walk-stab seam-clip: the solver's offline hit + the LIVE-delivery finding (session 30).

WHAT THIS LOCKS:
  * GREEN -- the solver finds a GENUINE offline clip (0-ULP from the seed): the shipped hit's
    old->new clips the kaze r11 slot-3 seam (CrrPos not blocked, old in front of both faces, new
    behind), spF==17, disp in the walk-stab window. Reproduced from rest.rest_state (pure sim).
  * GREEN -- the clean-DTM walk is FACING-bit-exact under the C-down camera pin (the feasibility half).
  * RED (xfail strict) -- the LIVE delivery does NOT clip: the walk-entry foot residual (m359C/f312,
    the open Phase-R gap) has a PERP component (~1.9e-4u for the clipping *turning* walk) that exceeds
    the ~1e-4u perp margin, so `old_live` falls off the razor (dead-end #28). This CORRECTS the
    session-29 feasibility read (measured on a straight walk, ~3.7e-5u perp). When the residual is
    MODELLED (not calibrated), this flips to PASS -- the signal the pure-sim one-shot is unblocked.

Live golden: tests/golden/walkstab_deliver.json (a clean-DTM run; C-down every frame; never
advancewith). NEVER edit the golden to make the sim pass (tests/dolphin/README.md).
"""
import json
import math
import os
import struct

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOLD = os.path.join(_HERE, 'golden', 'walkstab_deliver.json')

try:
    from harness.rollstab import walkstab as W
    from harness.rollstab import rest as C
    _HAVE = os.path.exists(_GOLD) and C.rest_state is not None
except Exception:
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="rollstab harness / walkstab golden unavailable")

# The shipped hit (harness.rollstab.walkstab.solve; _generated/walkstab_hits.json[0]).
HIT = dict(beta=5560, crawl=(0.72, 0.72), off=800, lead=5, dur=3, fframe=6, fdx=-3, fdz=0, N=12)


def _f(x):
    from tww_sim.core.fp import f32
    return f32(x)


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _gold():
    return json.load(open(_GOLD))


def _replay_hit():
    """From-rest sim: walk the hit stream (C-down), fire enter_cut, return (old, new, spF)."""
    sticks = W.build_stream(HIT['beta'], HIT['crawl'], HIT['off'], HIT['lead'], HIT['dur'],
                            HIT['fframe'], HIT['fdx'], HIT['fdz'])
    s = C.rest_state(W.ANCHOR)
    for k in range(HIT['N']):
        s.step(sticks[k][0], sticks[k][1], csx=128, csy=W.CDOWN)
    old = (s.pos_x, s.pos_z)
    spF = s.speedF
    s.enter_cut(W.CUT_F)
    return old, (s.pos_x, s.pos_z), spF


def test_walkstab_offline_clip_genuine():
    """The shipped hit is a genuine 0-ULP seam clip from rest (pure sim, no calibration)."""
    old, new, spF = _replay_hit()
    ok, why = W.genuine_clip(old, new)
    assert ok, "offline hit does not clip (why=%s)" % why
    assert W._pfunc(W.WALLA.pla, new[0], new[1]) < 0, "new not behind wall A"
    assert W._pfunc(W.WALLB.pla, new[0], new[1]) < 0, "new not behind wall B"
    assert spF == 17.0, "speedF %.3f != 17 at the cut" % spF
    disp = math.hypot(new[0] - old[0], new[1] - old[1])
    assert 35.5 <= disp <= 40.35, "disp %.3f outside the walk-stab window" % disp
    # matches the live golden's recorded sim endpoint bit-for-bit
    g = _gold()
    assert _bits(old[0]) == _bits(g['sim_old'][0]) and _bits(old[1]) == _bits(g['sim_old'][1])


def test_walkstab_delivery_facing_bitexact():
    """The clean-DTM walk is FACING-0-ULP vs the from-rest sim every logged frame (C-down pin)."""
    g = _gold()
    sim_rows = g['sim_rows']            # [state, x, z, facing, spF] per sim step
    live = g['frames']
    bad = []
    for k in range(min(len(sim_rows), len(live))):
        if (live[k]['facing'] & 0xFFFF) != (sim_rows[k][3] & 0xFFFF):
            bad.append(k)
    assert not bad, "facing diverged at live frames %s (C-down should pin the camera)" % bad


@pytest.mark.xfail(reason="walk-entry foot residual (m359C/f312, Phase-R): perp component ~1.9e-4u > "
                          "~1e-4u margin for the turning clip walk -> old_live off the razor "
                          "(dead-end #28). Flips to PASS when the residual is MODELLED.", strict=True)
def test_walkstab_live_delivery_clips():
    """LIVE delivery clips: fire the cut from the golden's live `old` (the walk residual moved it).
    Currently BLOCKED -- the pure-sim one-shot needs the walk-entry foot residual closed."""
    g = _gold()
    old_sim, new_sim = g['sim_old'], g['sim_new']
    lunge = (_f(new_sim[0] - old_sim[0]), _f(new_sim[1] - old_sim[1]))
    # the live `old` = the walk frame bit-matching the sim old in x (f11 here), carrying the residual
    live = g['frames']
    old_live = min(((f['pos_x'], f['pos_z']) for f in live),
                   key=lambda p: (p[0] - old_sim[0]) ** 2 + (p[1] - old_sim[1]) ** 2)
    new_live = (_f(old_live[0] + lunge[0]), _f(old_live[1] + lunge[1]))
    ok, why = W.genuine_clip(old_live, new_live)
    assert ok, "live delivery blocked (why=%s); old_live=%r" % (why, old_live)
