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

The three fixtures are the locked live capture: `courtyard_push_cyl.json` supplies the per-frame Link
Co centre + csangle + both actors' live positions; `courtyard_push_dtm.json` supplies the raw
controller bytes; `courtyard_push_seed.json` supplies the state-2 seed's HIDDEN mNormalSpeed (a
deterministic single read, no single-step jitter). All are captured from slot 2 and IMMUTABLE. The
gated range (f<=23 / f<=43) is BEFORE the cyc2 f44 double-read, so no dedup is needed there.

The TRUE f0 seed (state 2) is CLOSED (session 12, `test_true_f0_seed_bit_exact`): seeded at f0 with the
measured mNormalSpeed, the replay is bit-exact from the first stepped frame. The gap was that at f0
speedF LAGS mNormalSpeed a frame and the replay seeded `nspeed = speedF`; the fix seeds nspeed from the
live mNormalSpeed (mDirection + the attention state already match the sim defaults at f0). The whole
from-f0 chain -- roll-entry-seeded AND state-2-seeded -- is now bit-exact through cycle 2's roll.
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
_SEED = os.path.join(_ROOT, 'fixtures', 'courtyard_push_seed.json')

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


@pytest.fixture(scope='module')
def seed():
    if not os.path.exists(_SEED):
        return None
    return json.load(open(_SEED))


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


def test_true_f0_seed_bit_exact(fix, seed):
    """THE true f0 seed (session 12): seeded at STATE 2 itself (f0, proc MOVE) with the live-measured
    mNormalSpeed (`courtyard_push_seed.json` link.nspeed), the from-f0 replay is bit-exact from the
    FIRST stepped frame -- f1..f44 every Link speedF 0-ULP, every proc matching live, Link pos within
    the injected-cyl capture precision (<1e-3 u). This closes the last from-f0 gap.

    Root cause (session 12, live-probed `_notes/tetrapush-seed_probe.py`): at f0 Link is mid-transition
    out of the prior cycle's untarget, where speedF LAGS mNormalSpeed a frame (speedF -24.574,
    mNormalSpeed -24.982). The replay seeded `nspeed = speedF`, so f1 (a MOVE backslide) could only
    decay it (-24.572) instead of letting speedF catch up to the already-set nspeed (-24.980). Seeding
    `nspeed` from the live mNormalSpeed is the whole fix; f1 then reads -24.980 bit-exact and the +18
    re-target flip (f2) + cyc1 roll (f3) + the whole cyc1->cyc2 chain follow. mDirection (DIR_NONE at
    f0) and the attention state (no lock at f0) already match the sim defaults -- no other seed field
    is needed (both confirmed live)."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present (run: "
                    "python -m harness.tetrapush.capture_push seed)")
    cyl_frames, dtm_frames = fix
    rows = replay(cyl_frames, _input_at(dtm_frames), 0, upto=45,
                  seed_nspeed=seed['link']['nspeed'])
    assert len(rows) >= 40, "expected the full f0->cyc2-roll chain, got %d" % len(rows)
    by_f = {d['f']: d for d in rows}
    # f0-seed landmarks: the MOVE backslide catches up to nspeed (f1 -24.980, not a fresh decay to
    # -24.572), the +18 re-target flip (f2), cyc1's roll (f3).
    assert by_f[1]['speedF'] < -24.9, "f1 backslide must catch up to ~-24.98 (the nspeed seed)"
    assert by_f[2]['speedF'] > 18.0, "f2 the +18 re-target flip"
    assert by_f[3]['sim_proc'] == _FRONT_ROLL, "cyc1 roll trigger (f3)"
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


_SETCOL = os.path.join(_ROOT, 'fixtures', 'courtyard_push_setcol.json')


@pytest.fixture(scope='module')
def setcol():
    if not os.path.exists(_SETCOL):
        pytest.skip("setCollision breakpoint fixture not present (session-14 probe)")
    return json.load(open(_SETCOL))['frames']


def test_settled_center_law_half_depth(fix, setcol):
    """The mCyl TIMING law (session 14, breakpoint-pinned): the pause-boundary mCyl the gated plow
    laws consume equals setCollision's execute-pass midpoint PLUS the scene CC pass's immediate
    half-depth SetPosCorrect write away from Tetra (the plain decomp 50/50 rank split). Gate:
    `_cc_settled_center(cyl_exec(k), tetra(k))` reproduces the capture's `link.cyl` on every probed
    frame to capture precision. This is also the closure of the session-9 "2x doubling" sub-puzzle:
    full-depth-from-the-settled-centre == half-depth-from-the-exec-centre, same numbers."""
    from harness.tetrapush.from_f0 import _cc_settled_center
    cyl_frames, _ = fix
    for r in setcol:
        k = r['f']
        fx = cyl_frames[k]['link']['cyl']
        t = cyl_frames[k]['tetra']['pos']
        sx, sz = _cc_settled_center((r['cyl_exec'][0], r['cyl_exec'][2]), (t[0], t[2]))
        d = math.hypot(sx - fx[0], sz - fx[-1])
        assert d < 2e-4, "frame %d: settled centre off %.6f u" % (k, d)


def test_setcollision_is_execute_time_midpoint(setcol):
    """setCollision's write IS the plain root/neck nodeMtx midpoint at call time (execute-pass
    matrices, post-posMove pre-CC-push base) -- read at the JP 0x8011a670 breakpoint, <=6.1e-5 u on
    every probed frame (proc-7, the roll entry, and the roll bodies). The draw-pass matrices the
    session-13 offline fits compared against are a DIFFERENT base -- never use pause-boundary
    nodeMtx as the setCollision source."""
    for r in setcol:
        mx = 0.5 * (r['root'][0] + r['neck'][0])
        mz = 0.5 * (r['root'][2] + r['neck'][2])
        d = math.hypot(mx - r['cyl_exec'][0], mz - r['cyl_exec'][2])
        assert d < 1e-4, "frame %d: exec midpoint off %.6f u" % (r['f'], d)


def test_computed_centers_track_on_settled_roll_frames(fix, seed):
    """The self-contained centre pipeline (FK exec midpoint + the half-depth settled-centre law),
    diagnosed OPEN-LOOP (diag mode: pushes stay injected, so the trajectory is the gated bit-exact
    one; the computed centre is compared per frame). On the settled single-anim roll frames the
    computed centre matches the capture to <2e-3 u -- the law + FK are right; what remains open for
    the fully-computed closed loop are the enumerated pose gaps (f0-seed warmup f1/f3, the proc-9
    ATN blend f19-21 and its post-untarget morf decay f22-26, small blend residue elsewhere)."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    cyl_frames, dtm_frames = fix
    rows = replay(cyl_frames, _input_at(dtm_frames), 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers='diag')
    by_f = {d['f']: d for d in rows}
    settled = [5, 7, 8, 9, 10, 11, 12, 13, 17, 18, 39, 40, 41, 42, 43]
    for k in settled:
        r = by_f[k]
        fx = cyl_frames[k]['link']['cyl']
        d = math.hypot(r['sim_cyl'][0] - fx[0], r['sim_cyl'][1] - fx[-1])
        assert d < 2e-3, "settled frame %d: computed centre off %.5f u" % (k, d)
    # and the diag run must not perturb the gated replay: procs + speedF stay live-exact
    for d in rows:
        assert d['sim_proc'] == d['live_proc'], "diag mode changed the trajectory (f%d)" % d['f']
        assert d['speedF'] == d['live_speedF'], "diag mode changed speedF (f%d)" % d['f']
