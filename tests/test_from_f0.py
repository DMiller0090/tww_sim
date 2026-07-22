"""The Courtyard from-f0 coupled replay, live-gated against the locked RAM capture.

`harness/tetrapush/from_f0` wires BOTH gated plow laws (`link_plow` = Link's full-depth recoil,
`tetra_plow` = Tetra's full-depth push) into a closed-loop `LandState` replay driven by the real DTM
controller bytes, with Link's animated mCyl Co centre + csangle injected per frame from the capture.
This gate proves the coupling is bit-exact where the sim's proc physics are already modelled:

  * Seeded at the FIRST roll entry, cycle 1 -- the FRONT_ROLL, the 2-frame ATN_ACTOR untarget tier
    (the -25.727 flip + the -25.452 body2), and the following MOVE backslide -- reproduces the live
    Link speedF 0-ULP every frame, and his position within the injected-cyl single-step capture
    precision (<1e-3 u). This is the full-depth CC coupling running through the whole cycle.
  * Tetra's full-depth plow, composed from state 2 (f0) with the injected centres, reproduces her
    WHOLE trajectory to within a handful of ULP over the plow window (both cycles) -- 0-ULP.

The two fixtures are the locked live capture: `courtyard_push_cyl.json` supplies the per-frame Link Co
centre + csangle + both actors' live positions; `courtyard_push_dtm.json` supplies the raw controller
bytes. Both are single-stepped from slot 2 and IMMUTABLE. The gated range (f<=23 / f<=43) is BEFORE
the cyc2 f44 double-read, so no dedup is needed there.

OPEN (not gated -- the next frontier): the backslide->roll-setup (the MOVE->ATN_MOVE re-target that
flips speedF ~-25 -> +18 just before each roll) is 1 frame late, so cycle 2 does not yet chain and the
true f0 seed (which also needs the previous cycle's attention-RELEASE residual) is not yet bit-exact.
See harness/tetrapush/README.md "## Plan / status".
"""
import json
import math
import os
import struct

import pytest

from harness.tetrapush.from_f0 import replay

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CYL = os.path.join(_ROOT, 'fixtures', 'courtyard_push_cyl.json')
_DTM = os.path.join(_ROOT, 'fixtures', 'courtyard_push_dtm.json')

_FRONT_ROLL = 30


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope='module')
def fix():
    if not (os.path.exists(_CYL) and os.path.exists(_DTM)):
        pytest.skip("Courtyard capture fixtures not present (need a live slot-2 capture)")
    cyl = json.load(open(_CYL))
    dtm = json.load(open(_DTM))
    return cyl['frames'], dtm['frames']


def _dedup(frames):
    """Drop the single-step DOUBLE-READ frames (cyc2 f44==f45 -- the capture re-sampling one game
    frame; bit-identical in BOTH Link's Co centre and Tetra's pos). Matches test_{link,tetra}_plow."""
    out = [frames[0]]
    for f in frames[1:]:
        p = out[-1]
        if f['link']['cyl'] == p['link']['cyl'] and f['tetra']['pos'] == p['tetra']['pos']:
            continue
        out.append(f)
    return out


def _input_at(dtm_frames):
    return lambda k: dtm_frames[k]['inp']


def test_cyc1_rollentry_speedF_bit_exact(fix):
    """Seeded at the first roll entry, EVERY Link speedF through cycle 1 (the roll, the 2-frame
    untarget tier, the backslide, f4..f23) is bit-identical to live -- the pure-sim proc physics under
    the full-depth CC coupling, 0-ULP (no injection touches speedF)."""
    cyl_frames, dtm_frames = fix
    entry = next(i for i, f in enumerate(cyl_frames) if f['proc'] == _FRONT_ROLL)
    rows = replay(cyl_frames, _input_at(dtm_frames), entry, upto=24)
    assert len(rows) >= 18, "expected the full cyc1 roll+untarget+backslide, got %d" % len(rows)
    for d in rows:
        assert _bits(d['speedF']) == _bits(d['live_speedF']), (
            "frame %d: sim speedF %.9f != live %.9f (not 0-ULP)" % (
                d['f'], d['speedF'], d['live_speedF']))


def test_cyc1_rollentry_untarget_flip(fix):
    """The headline: under the full-depth coupling, the roll exits into the 2-frame ATN_ACTOR tier and
    speedF flips 26 -> the live values BIT-EXACT -- flip (f20) -25.727313995361328, body2 (f21)
    -25.452238082885742. (Same values as `test_tetra_untarget`'s tier test, now from the coupled
    roll-entry replay rather than a bare seed.)"""
    cyl_frames, dtm_frames = fix
    entry = next(i for i, f in enumerate(cyl_frames) if f['proc'] == _FRONT_ROLL)
    rows = replay(cyl_frames, _input_at(dtm_frames), entry, upto=24)
    by_f = {d['f']: d for d in rows}
    flip = by_f[entry + 17]        # cyc1 untarget flip frame (f20 when entry==3): proc 9, -25.727
    body2 = by_f[entry + 18]       # the 2nd ATN_ACTOR body frame (f21): live_proc reads 6 (checkNextMode
                                   # set the NEXT proc early) but a proc-9 body ran -> the -25.452 ATN step
    assert flip['live_proc'] == 9, "expected the proc-9 untarget flip at f20"
    assert _bits(flip['speedF']) == _bits(flip['live_speedF']), "untarget flip not 0-ULP"
    assert _bits(body2['speedF']) == _bits(body2['live_speedF']), "untarget body2 not 0-ULP"
    assert flip['speedF'] < -25.7 and body2['speedF'] < -25.4, "the hot ATN-tier flip did not land"


def test_cyc1_rollentry_link_pos_within_capture_precision(fix):
    """Link's position through cycle 1 tracks live to within the injected-cyl single-step capture
    precision (<1e-3 u every frame; the residual IS the captured Co centre's own read precision, not a
    model error -- speedF is 0-ULP). This is the full-depth recoil (`link_plow`) closing the loop on
    Link's own path."""
    cyl_frames, dtm_frames = fix
    entry = next(i for i, f in enumerate(cyl_frames) if f['proc'] == _FRONT_ROLL)
    rows = replay(cyl_frames, _input_at(dtm_frames), entry, upto=24)
    for d in rows:
        err = math.hypot(d['sim_link'][0] - d['live_link'][0], d['sim_link'][1] - d['live_link'][1])
        assert err < 1e-3, "frame %d: Link pos off by %.6f u (> capture precision)" % (d['f'], err)


def test_chained_replay_through_cyc2_roll_bit_exact(fix):
    """THE full chained replay (session 11): seeded at the first roll entry, the sim runs UNBROKEN
    through cycle 1 AND the backslide->roll-setup transition AND cycle 2's roll -- f4..f44 -- with
    every Link speedF 0-ULP, every proc matching live, and Link's position within the injected-cyl
    capture precision. This closes the backslide->roll-setup blocker: the +18 re-target flip lands on
    the right frame (f28, -25.15 -> +18.574) and cycle 2's roll triggers on the right frame (f29),
    because the DTM-driven replay runs at input_delay=1 (the DTM stream IS the polled pad, one pipeline
    stage in -- live-probed s11: m34E8/roll/soft-L all land 1 frame after the DTM).

    Gated range stops at f44 -- BEFORE the cyl fixture's single-step-jittered cyc2 untarget (f45+, a
    known capture corruption, session 8; the DTM fixture has the clean -25.74 flip there). The chained
    physics through the second roll is what this proves."""
    cyl_frames, dtm_frames = fix
    entry = next(i for i, f in enumerate(cyl_frames) if f['proc'] == _FRONT_ROLL)
    rows = replay(cyl_frames, _input_at(dtm_frames), entry, upto=45)
    assert len(rows) >= 40, "expected the full cyc1->cyc2-roll chain, got %d" % len(rows)
    # the transition landmarks: proc-7 re-target entry (f26), the +18 flip (f28), cyc2 roll (f29).
    by_f = {d['f']: d for d in rows}
    assert by_f[26]['live_proc'] == 7 and by_f[26]['sim_proc'] == 7, "proc-7 re-target entry (f26)"
    assert by_f[28]['sim_proc'] == 7 and by_f[28]['speedF'] > 18.0, "the +18 re-target flip (f28)"
    assert by_f[29]['sim_proc'] == _FRONT_ROLL, "cyc2 roll trigger (f29)"
    for d in rows:
        assert d['sim_proc'] == d['live_proc'], (
            "frame %d: sim proc %d != live %d" % (d['f'], d['sim_proc'], d['live_proc']))
        assert _bits(d['speedF']) == _bits(d['live_speedF']), (
            "frame %d: sim speedF %.9f != live %.9f (not 0-ULP)" % (
                d['f'], d['speedF'], d['live_speedF']))
        err = math.hypot(d['sim_link'][0] - d['live_link'][0], d['sim_link'][1] - d['live_link'][1])
        assert err < 1e-3, "frame %d: Link pos off by %.6f u (> capture precision)" % (d['f'], err)


def test_tetra_full_depth_from_f0_bit_exact(fix):
    """Tetra's full-depth plow, composed from state 2 (f0) with the injected Co centres, reproduces
    her WHOLE trajectory to within a handful of ULP over the plow window (f1..f43, both cycles). Her
    motion is a deterministic function of Link's centre path -- independent of Link's own sim, so this
    validates from f0 even while the Link-side setup transition is still open."""
    cyl_frames, dtm_frames = fix
    frames = _dedup(cyl_frames)
    rows = replay(frames, _input_at(dtm_frames), 0, upto=44)
    for d in rows:
        err = math.hypot(d['sim_tetra'][0] - d['live_tetra'][0], d['sim_tetra'][1] - d['live_tetra'][1])
        assert abs(d['dtx']) <= 16 and abs(d['dtz']) <= 16, (
            "frame %d: Tetra off by (%d, %d) ULP -- not 0-ULP" % (d['f'], d['dtx'], d['dtz']))
        assert err < 1e-3, "frame %d: Tetra pos off by %.6f u" % (d['f'], err)
