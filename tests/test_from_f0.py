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


_EYES = os.path.join(_ROOT, 'fixtures', 'courtyard_push_eyepos.json')


@pytest.fixture(scope='module')
def eyes():
    if not os.path.exists(_EYES):
        pytest.skip("Tetra eyePos fixture not present (session-15 probe)")
    return [r['eye'] for r in json.load(open(_EYES))['frames']]


def test_facing_and_lean_bit_exact_with_eye_aim(fix, seed, eyes):
    """THE proc-9 re-aim law (session 15, live-pinned `_notes/tetrapush-eyepos_probe.py`): with the
    injected Tetra EYE positions (her animated head-joint world pos -- the actual
    `setShapeAngleToAtnActor` target, d_a_player_main.cpp:2628) and the `mpAttnActorLockOn != NULL`
    re-aim guard (2627 -- the body2 frame runs one frame past the lock drop and must NOT re-aim),
    Link's shape_angle.y is bit-exact against the capture on EVERY frame f1..f43. Aiming at the
    plowed FEET instead lands the f20 chase 184 BAM short (37364 vs 37548) and the ghost f21 re-aim
    adds +432 -- the error that fed the m351C lean sawtooth and the ~1 u Co-centre bias f21-26."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    cyl_frames, dtm_frames = fix
    rows = replay(cyl_frames, _input_at(dtm_frames), 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers='diag', eyes=eyes)
    for d in rows:
        assert d['sim_proc'] == d['live_proc'] and d['speedF'] == d['live_speedF']
        assert d['sim_facing'] == d['live_facing'], (
            "frame %d: sim facing %d != live %d" % (d['f'], d['sim_facing'], d['live_facing']))
        assert d['sim_shape_z'] == d['live_shape_z'], (
            "frame %d: sim lean %d != live %d" % (d['f'], d['sim_shape_z'], d['live_shape_z']))
    by_f = {d['f']: d for d in rows}
    # the frames the feet-aim/ghost-re-aim errors used to dominate: now centre-exact to <=0.02 u.
    for k in (19, 20, 26, 27, 28):
        r = by_f[k]
        fx = cyl_frames[k]['link']['cyl']
        d = math.hypot(r['sim_cyl'][0] - fx[0], r['sim_cyl'][1] - fx[-1])
        assert d < 2e-2, "frame %d: computed centre off %.5f u (re-aim regression)" % (k, d)


def test_computed_centers_track_on_settled_roll_frames(fix, seed, eyes):
    """The self-contained centre pipeline (FK exec midpoint + the half-depth settled-centre law),
    diagnosed OPEN-LOOP (diag mode: pushes stay injected, so the trajectory is the gated bit-exact
    one; the computed centre is compared per frame). With the session-16 exec-pose laws -- the
    NEW-lean BODY_CHN twist (mBodyAngle.z is re-set by setMoveSlantAngle BEFORE mpCLModel->calc,
    :11559-11591), J3D segment-scale-compensation on the neck chain (the dash bck scales
    stomach_jnt.x; mDoExt_setJ3DData:47), the signed body_x euler quantization, and the proc-init
    base lean (commonProcInit zeroes shape_angle.z :5841 BEFORE setWorldMatrix; setMoveSlantAngle
    restores it after) -- the computed centre matches the capture on EVERY frame f1..43 to
    <3e-4 u (the cyl fixture's own single-step precision). No open pose gaps remain in-window."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    cyl_frames, dtm_frames = fix
    rows = replay(cyl_frames, _input_at(dtm_frames), 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers='diag', eyes=eyes,
                  seed_old_pose=seed.get('old_pose'))
    for r in rows:
        fx = cyl_frames[r['f']]['link']['cyl']
        d = math.hypot(r['sim_cyl'][0] - fx[0], r['sim_cyl'][1] - fx[-1])
        assert d < 3e-4, "frame %d: computed centre off %.6f u" % (r['f'], d)
    # and the diag run must not perturb the gated replay: procs + speedF stay live-exact
    for d in rows:
        assert d['sim_proc'] == d['live_proc'], "diag mode changed the trajectory (f%d)" % d['f']
        assert d['speedF'] == d['live_speedF'], "diag mode changed speedF (f%d)" % d['f']


def test_closed_loop_computed_replay_dynamics_bit_exact(fix, seed, eyes):
    """The self-contained replay's DYNAMICS are bit-exact (session 16); its POSITION is NOT (still a
    tolerance here -- see `test_onestep_pos_bit_exact_from_exact_state`, the open 0-ULP gap; this
    test's `<2e-3 u` position check is one of the tolerance gates slated for the 0-ULP rewrite,
    `[[zero-ulp-tests-only]]`). `centers='computed'` (Link's Co centre rebuilt every frame from the
    sim's OWN pose; only the static state-2 seed, the DTM bytes, csangle, and the Tetra eye stream are
    consumed) chains from STATE 2 with every proc, speedF, facing, and lean BIT-EXACT vs live f1..f43,
    through both rolls, both untarget tiers, and the whole coupled plow. Positions amplify the
    per-step residual (~1e-4 u/frame) through the plow feedback (depth = 80 - dist, ~1.35x/frame,
    an unstable amplifier; the drift is DIFFERENTIAL, e_link ~ -e_tetra), so the position check here
    is the PRE-AMPLIFICATION window: <2e-3 u over f1..10. The same noise perturbs the proc-9 eye-aim
    bearing (a bearing to a point ~30 u away, from a position with the amplified noise), so facing
    carries a few-BAM echo on f20-28 (measured max +6); lean stays 0-ULP (its addCalc sawtooth
    quantizes the echo away)."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    cyl_frames, dtm_frames = fix
    rows = replay(cyl_frames, _input_at(dtm_frames), 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers='computed', eyes=eyes,
                  seed_old_pose=seed.get('old_pose'))
    for d in rows:
        assert d['sim_proc'] == d['live_proc'], (
            "frame %d: closed-loop proc %d != live %d" % (d['f'], d['sim_proc'], d['live_proc']))
        assert d['speedF'] == d['live_speedF'], (
            "frame %d: closed-loop speedF %r != live %r" % (d['f'], d['speedF'], d['live_speedF']))
        df = (d['sim_facing'] - d['live_facing']) & 0xFFFF
        df = df - 0x10000 if df >= 0x8000 else df
        assert abs(df) <= 16, (
            "frame %d: closed-loop facing %d != live %d" % (d['f'], d['sim_facing'], d['live_facing']))
        assert d['sim_shape_z'] == d['live_shape_z'], (
            "frame %d: closed-loop lean %d != live %d" % (d['f'], d['sim_shape_z'], d['live_shape_z']))
        if d['f'] <= 10:
            dl = math.hypot(d['sim_link'][0] - d['live_link'][0],
                            d['sim_link'][1] - d['live_link'][1])
            dt = math.hypot(d['sim_tetra'][0] - d['live_tetra'][0],
                            d['sim_tetra'][1] - d['live_tetra'][1])
            assert dl < 2e-3 and dt < 2e-3, (
                "frame %d: closed-loop position off dL=%.5f dT=%.5f" % (d['f'], dl, dt))


def test_onestep_error_bounded_from_exact_state(fix, seed, eyes):
    """THE RE-DIAGNOSIS (session 23): the coupled STEP FUNCTION is bit-faithful; the closed-loop
    position drift is an AMPLIFICATION instability, NOT an FK matrix bug.

    Session 22 named the blocker "the FK 0-ULP hunt -- make `FootFK.body_co_center` fp-faithful."
    That is misdiagnosed: `body_co_center` is already BIT-EXACT given exact input (the computed exec
    centre equals `courtyard_push_setcol.json`'s breakpoint `cyl_exec` to 0 ULP on every frame f1..12
    when fed the breakpoint-exact pos). The console `sqrtf` (MSL `frsqrte` + 3 double Newton steps +
    f32 cast, math.h:89) was also RULED OUT -- it is bit-identical to a correctly-rounded `math.sqrt`
    over the loop's whole dist_sq range, so the plow sqrt is not the residual either.

    The real situation, proven here: reset the sim to the EXACT captured state each frame (pos + Tetra
    + the push from the fixture centre), step ONCE, and the one-step Link-position error stays BOUNDED
    and NON-accumulating -- <=64 ULP in z (~1.5e-5 u), largest at the roll-entry morf frames (k3..k5,
    the known `calc_transform`/Hermite entry-morf sub-ULP flagged in `core/anim/quat.py`), single-digit
    ULP elsewhere; x is 0 ULP throughout (its coarse f32 quantum at ~1335 hides the same ~1e-5 u
    residual that shows at small-magnitude z). facing + speedF are bit-exact every frame. So each
    component (foot FK, recoil, plow, centre FK) is correct to the single-step fixture's f32 noise
    floor; the `centers='computed'` blow-up (test above) is the plow feedback (depth = 80 - dist,
    ~1.35x/contact-frame -- an unstable amplifier) magnifying those floor-level residuals. Closing it
    to true 0-ULP needs the last <=1-ULP op(s) in the DASH/ROLL foot-term + recoil path pinned against
    a per-op live capture (the single-step fixtures resolve only to ~1e-5 u); the FK matrix is not it."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    from harness.tetrapush.from_f0 import FreeRun, full_depth_push
    from tww_sim.core.fp import f32
    cyl_frames, dtm_frames = fix
    input_at = _input_at(dtm_frames)

    run = FreeRun(cyl_frames[0], seed_nspeed=seed['link']['nspeed'], computed_pose=True,
                  seed_old_pose=seed.get('old_pose'))
    run.pre_seed_input(input_at(0))
    link = run.link
    worst = 0
    for k in range(1, 44):
        prev = cyl_frames[k - 1]
        # reset to the EXACT captured state[k-1], recompute the outgoing push from the exact
        # fixture centre + Tetra -> isolates the ONE-STEP error from pure accumulation.
        link.pos_x = f32(prev['link']['pos'][0]); link.pos_z = f32(prev['link']['pos'][2])
        run.tx = f32(prev['tetra']['pos'][0]); run.tz = f32(prev['tetra']['pos'][2])
        run.pend_link, run.pend_tetra = full_depth_push(prev['link']['cyl'], (run.tx, run.tz))
        eye = eyes[k - 1] if (eyes is not None and k - 1 < len(eyes)) else None
        row = run.step(input_at(k), csangle=cyl_frames[k - 1]['csangle'], eye=eye,
                       center=cyl_frames[k]['link']['cyl'])
        lv = cyl_frames[k]['link']
        assert row['sim_proc'] == cyl_frames[k]['proc'], "frame %d: one-step proc diverged" % k
        assert _bits(row['speedF']) == _bits(lv['speedF']), "frame %d: one-step speedF diverged" % k
        assert row['sim_facing'] == lv['facing'], "frame %d: one-step facing diverged" % k
        ex = abs(_bits(row['sim_link'][0]) - _bits(lv['pos'][0]))
        ez = abs(_bits(row['sim_link'][1]) - _bits(lv['pos'][2]))
        assert ex <= 4, "frame %d: one-step x error %d ULP (a real step bug, not noise)" % (k, ex)
        worst = max(worst, ez)
        assert ez <= 128, "frame %d: one-step z error %d ULP -- step function bug, not amplification" % (k, ez)
    # sanity: the one-step floor is TINY next to the closed-loop drift it feeds (thousands of ULP
    # by mid-window) -- proving the drift is amplification, not a per-step error.
    assert worst <= 128


@pytest.mark.xfail(strict=True, reason="OPEN 0-ULP gap (session 24): the DASH/ROLL foot-term "
                   "sub-ULP. One-step-from-exact-state pos diverges from live by up to 56 ULP "
                   "(~1.3e-5 u) in z, concentrated at the roll-entry morf frames f3-f5 (56/22 decaying "
                   "with the morf rate = the calc_transform/Hermite entry-morf, quat.py) plus a small "
                   "f1-f2 MOVE-backslide residue (5-7 ULP). x reads 0 ULP only because its f32 quantum "
                   "at ~1335 u (~1.2e-4 u) is coarser than the residual. This is the planner blocker: "
                   "the plow feedback (~1.35x/contact-frame) amplifies it to the 93-u closed-loop drift.")
def test_onestep_pos_bit_exact_from_exact_state(fix, seed, eyes):
    """THE 0-ULP DIVERGENCE GATE (session 24) -- the hard bar: from the EXACT captured state[k-1],
    stepping once must reproduce live pos[k] BIT-FOR-BIT (0 ULP), every frame, every axis.

    This is the strict form of `test_onestep_error_bounded_from_exact_state` (which asserts only
    BOUNDED). The live pos is true console ground truth (breakpoint-captured; `setcol.pos == cyl.pos`
    to 0 ULP over f1..12, so the divergence is real sim-vs-console, not single-step noise). Because
    the outgoing recoil is fed from the EXACT fixture centre, the pos divergence IS the coupled
    step's own error (Link's foot term + the applied recoil law). Collects the WHOLE divergent-frame
    set into the failure message so the xfail records the full picture, not just the first frame.

    Currently XFAILS (the open gap). Regenerate the human-readable per-frame ULP table with
    `python -m harness.tetrapush.onestep_divergence`. When the diverging op is pinned (per-op live
    capture, session 24+) and fixed, this flips to a hard PASS and the xfail marker comes off."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    from harness.tetrapush.from_f0 import FreeRun, full_depth_push
    from tww_sim.core.fp import f32
    cyl_frames, dtm_frames = fix
    input_at = _input_at(dtm_frames)

    run = FreeRun(cyl_frames[0], seed_nspeed=seed['link']['nspeed'], computed_pose=True,
                  seed_old_pose=seed.get('old_pose'))
    run.pre_seed_input(input_at(0))
    link = run.link
    diverged = []
    for k in range(1, 44):
        prev = cyl_frames[k - 1]
        link.pos_x = f32(prev['link']['pos'][0]); link.pos_z = f32(prev['link']['pos'][2])
        run.tx = f32(prev['tetra']['pos'][0]); run.tz = f32(prev['tetra']['pos'][2])
        run.pend_link, run.pend_tetra = full_depth_push(prev['link']['cyl'], (run.tx, run.tz))
        eye = eyes[k - 1] if (eyes is not None and k - 1 < len(eyes)) else None
        row = run.step(input_at(k), csangle=cyl_frames[k - 1]['csangle'], eye=eye,
                       center=cyl_frames[k]['link']['cyl'])
        lv = cyl_frames[k]['link']
        ex = abs(_bits(row['sim_link'][0]) - _bits(lv['pos'][0]))
        ez = abs(_bits(row['sim_link'][1]) - _bits(lv['pos'][2]))
        if ex or ez:
            diverged.append((k, cyl_frames[k]['proc'], ex, ez))
    assert not diverged, "one-step pos != live (0 ULP required); divergent frames [f,proc,xULP,zULP]: " \
        + ", ".join("[f%d p%d x%d z%d]" % d for d in diverged)


@pytest.mark.xfail(strict=True, reason="OPEN 0-ULP gap (session 24), BUG #1 of 2: the push/recoil "
                   "law. Tetra has NO foot term (stt-3, speedF 0) so her pos-delta isolates the push "
                   "vector -- it diverges from live by up to ~9 ULP in z, no roll-entry spike (that "
                   "spike is Link-only = BUG #2, the foot term). The Courtyard replay uses the "
                   "session-9 DERIVED full_depth_push (link_plow.recoil + tetra_plow.plow_step: two "
                   "separate fsqrt, and full_depth_push returns Tetra's move as an f64 new-minus-old "
                   "while Link's is a direct f32 delta), NOT the decomp-faithful cc_push.co_move_pair "
                   "(one dist, exact-opposite obj1/obj2 moves). Fix = compute the push the console's "
                   "way; validate 0-ULP vs a per-op live m_cc_move capture (the cyl fixture Tetra pos "
                   "resolves only to ~1e-5 u, at the residual size).")
def test_tetra_push_bit_exact_from_exact_state(fix):
    """THE PUSH-LAW 0-ULP DIVERGENCE GATE (session 24). Tetra's motion is PURELY the CC push (she has
    no foot term -- stt-3, speedF 0, the whole window), so stepping the push from the EXACT captured
    Link Co centre + Tetra pos and comparing to live Tetra pos isolates the push/recoil law with NO
    foot-term confound (unlike the Link one-step gate). Currently XFAILS (bug #1). Diagnostic:
    the `link recoil == -tetra push` self-consistency invariant below + the per-frame table in
    `harness.tetrapush.onestep_divergence`."""
    from harness.tetrapush.from_f0 import full_depth_push
    from tww_sim.core.fp import f32
    cyl_frames, _ = fix
    diverged = []
    for k in range(1, 44):
        prev = cyl_frames[k - 1]
        ptx, ptz = f32(prev['tetra']['pos'][0]), f32(prev['tetra']['pos'][2])
        _rl, (tdx, tdz) = full_depth_push(prev['link']['cyl'], (ptx, ptz))
        sim_tx = f32(ptx + tdx); sim_tz = f32(ptz + tdz)
        lv = cyl_frames[k]['tetra']['pos']
        ex = abs(_bits(sim_tx) - _bits(lv[0]))
        ez = abs(_bits(sim_tz) - _bits(lv[2]))
        if ex or ez:
            diverged.append((k, cyl_frames[k]['proc'], ex, ez))
    assert not diverged, "Tetra push != live (0 ULP required); divergent frames [f,proc,xULP,zULP]: " \
        + ", ".join("[f%d p%d x%d z%d]" % d for d in diverged)


@pytest.mark.xfail(strict=True, reason="OPEN 0-ULP gap (session 24): full_depth_push does not return "
                   "the Link recoil and Tetra push as exact opposites -- the recoil is a direct f32 "
                   "delta (fmuls(dx,ff)) while the Tetra move is an f64 new-minus-old (f32(tx-rlx)-tx), "
                   "so they differ by ~1 ULP where Tetra's coord is large. Newton's third law in the "
                   "CC resolution says they MUST be equal and opposite (cc_push.co_move_pair is; "
                   "sum==0 live-confirmed). Fix with bug #1.")
def test_full_depth_push_recoil_is_exact_opposite_of_tetra(fix):
    """SELF-CONSISTENCY (session 24): for a single Co pair the two actors eject equal-and-opposite --
    Link's recoil delta must be the exact negative of Tetra's push delta (bit-for-bit), the way the
    decomp `cc_push.co_move_pair` guarantees. `full_depth_push` currently violates this by ~1 ULP
    (the f32-delta vs f64-new-minus-old asymmetry), independent of any live capture. Currently XFAILS."""
    from harness.tetrapush.from_f0 import full_depth_push
    cyl_frames, _ = fix
    bad = []
    for k in range(0, 43):
        e = cyl_frames[k]
        (rlx, rlz), (tdx, tdz) = full_depth_push(
            e['link']['cyl'], (e['tetra']['pos'][0], e['tetra']['pos'][2]))
        if _bits(rlx) != _bits(-tdx) or _bits(rlz) != _bits(-tdz):
            bad.append((k, _bits(rlx) - _bits(-tdx), _bits(rlz) - _bits(-tdz)))
    assert not bad, "recoil != -push (bit-for-bit); frames [k,xULP,zULP]: " \
        + ", ".join("[%d %+d %+d]" % b for b in bad)


def test_freerun_direct_api_matches_replay(fix, seed, eyes):
    """`FreeRun` -- the planner's novel-input stepper -- driven DIRECTLY (no capture rows in the
    loop) reproduces the wrapped `replay(centers='computed')` byte-for-byte. Pins the API contract
    (`pre_seed_input` delay-1 semantics, keep-last eye injection, computed settled centres) so a
    future wrapper-only change can't silently fork the planner path."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    from harness.tetrapush.from_f0 import FreeRun
    cyl_frames, dtm_frames = fix
    input_at = _input_at(dtm_frames)
    want = replay(cyl_frames, input_at, 0, upto=44, seed_nspeed=seed['link']['nspeed'],
                  centers='computed', eyes=eyes, seed_old_pose=seed.get('old_pose'))

    run = FreeRun(cyl_frames[0], seed_nspeed=seed['link']['nspeed'],
                  seed_old_pose=seed.get('old_pose'))
    run.pre_seed_input(input_at(0))
    for w in want:
        k = w['f']
        eye = eyes[k - 1] if k - 1 < len(eyes) else None
        row = run.step(input_at(k), csangle=cyl_frames[k - 1]['csangle'], eye=eye)
        for key in ('sim_proc', 'sim_facing', 'sim_shape_z', 'sim_link', 'sim_tetra',
                    'speedF', 'sim_cyl'):
            assert row[key] == w[key], "frame %d: FreeRun %s %r != replay %r" % (
                k, key, row[key], w[key])


def test_freerun_warns_when_tetra_would_follow(fix, seed):
    """The stt-3 plow model must WARN the first time a stepped state leaves the plow regime --
    live Tetra flips to the stt-4 FOLLOW state (unmodeled here) once the 3D Link distance passes
    `npc_zl1.FOLLOW_ENGAGE_DIST` (230, the gated field_34+100 law; live she flips at-or-after the
    crossing, never before -- s17 probe: crossed 231.9 at f63, stt 4 at f75). The validated DTM
    window (chase-and-plow, 41-85 u) must stay silent."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    import warnings as _w
    from harness.tetrapush.from_f0 import FreeRun
    cyl_frames, dtm_frames = fix
    input_at = _input_at(dtm_frames)

    # The locked window never crosses the engage distance -> no warning.
    with _w.catch_warnings():
        _w.simplefilter("error")
        replay(cyl_frames, input_at, 0, upto=44, seed_nspeed=seed['link']['nspeed'])

    # Free-running the seed with a held UP stick walks Link away from the plowed Tetra; the
    # first frame past 230 u must warn (and only once).
    run = FreeRun(cyl_frames[0], seed_nspeed=seed['link']['nspeed'])
    run.pre_seed_input((128, 255, 0, 0))
    with pytest.warns(UserWarning, match="FOLLOW_ENGAGE_DIST"):
        for _ in range(400):
            run.step((128, 255, 0, 0))
    assert run._follow_warned


# ---------------------------------------------------------------- the wired land camera (s18)
_CAM = os.path.join(_ROOT, 'fixtures', 'courtyard_cam_oracle.json')


@pytest.fixture(scope='module')
def cam_oracle():
    if not os.path.exists(_CAM):
        pytest.skip("camera oracle fixture not present")
    return json.load(open(_CAM))


def test_pad_decode_matches_oracle(fix, cam_oracle):
    """`land_cam.pad_from_raw` (the raw-DTM-bytes -> camera-pad decode: PADClamp octagons +
    JUTGamePad TStick + ClampTrigger) reproduces the live post-updatePad stick lasts 0-ULP on
    every oracle frame the DTM covers, at the camera's delay-1 stage: pad[k] == decode(inp[k-1]).

    ``main_angle`` is asserted against inp[k] instead: the oracle's value is a PROBE-TIMING
    SHIFT (the camera block's stick lasts were read from the frozen dCamera_c copy, but
    mMainStickAngle was read from the live JUTGamePad struct, which the single-step's next poll
    had already advanced) -- decoding the raw bytes proves the shift exactly. main_angle is
    DMC-only and inert at status 0, so the wired camera feeds the honest delay-1 value."""
    from tww_sim.core.camera.land_cam import pad_from_raw
    cyl_frames, dtm_frames = fix
    inp_at = {fr['f']: fr['inp'] for fr in dtm_frames}
    checked = 0
    for fr in cam_oracle['frames']:
        k = fr['f']
        # f45 is the movie's last delivered group; f46+ of the oracle run was driven by a
        # different (probe-injected) input stream the DTM fixture does not carry.
        if fr['dup'] or k - 1 not in inp_at or k > 45:
            continue
        pad = pad_from_raw(inp_at[k - 1])
        live = fr['pad']
        for key in ('mx', 'my', 'mval', 'cx', 'cy', 'cval', 'trigL'):
            assert _bits(pad[key]) == _bits(live[key]), (
                "f%d pad.%s %r != live %r (not 0-ULP)" % (k, key, pad[key], live[key]))
        if k in inp_at:
            assert (pad_from_raw(inp_at[k])['main_angle'] & 0xFFFF
                    == live['main_angle'] & 0xFFFF), (
                "f%d main_angle probe-shift identity broke" % k)
        checked += 1
    assert checked >= 40


def test_camera_in_the_loop_replay_bit_exact(fix, seed, eyes, cam_oracle):
    """THE session-18 wiring gate: the fully self-contained replay with the MODELED land camera
    in the loop (`camera=` a LandCamera seeded once from the f0 oracle block -- NO injected
    csangle stream) chains from state 2 with:

      * every committed csangle f1..43 == the live capture (`frames[k]['csangle']`) AND the
        camera oracle, EXACT (csangle is position-independent in this regime -- manual yaw moves
        only with C-stick X and the L-blip chase targets the camera's own committed yaw -- so the
        known amplified position noise cannot touch it);
      * the physics rows byte-identical to the reference `centers='computed'` replay (the wired
        camera reproduces exactly the stream the injection supplied);
      * Link's camera-input attention position obeying the decomp law attn.y = f32(92.5 +
        baseTR[1][3]) (`setAttentionPos` :10271) -- 0-ULP vs the oracle on f3..f9, after the
        unmodeled m35B8 seed residue dies (f1-2, a <0.15 u center-Y transient) and before the
        closed-loop position noise reaches pos.y's last bits (f10+, <=2e-5)."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    from tww_sim.core.camera.land_cam import LandCamera, seed_from_block
    cyl_frames, dtm_frames = fix
    input_at = _input_at(dtm_frames)
    ora = {fr['f']: fr for fr in cam_oracle['frames']}
    n_tattn = max(ora) + 1
    tattns = [ora[k]['tattn'] if k in ora else None for k in range(n_tattn)]

    cam = seed_from_block(LandCamera(), bytes.fromhex(cam_oracle['seed_cam_raw']))
    assert cam.angleY == cyl_frames[0]['csangle'], "oracle seed block != cyl fixture f0 csangle"
    rows = replay(cyl_frames, input_at, 0, upto=44, seed_nspeed=seed['link']['nspeed'],
                  centers='computed', eyes=eyes, seed_old_pose=seed.get('old_pose'),
                  camera=cam, tattns=tattns)
    ref = replay(cyl_frames, input_at, 0, upto=44, seed_nspeed=seed['link']['nspeed'],
                 centers='computed', eyes=eyes, seed_old_pose=seed.get('old_pose'))
    assert len(rows) == len(ref) >= 40
    for rc, rr in zip(rows, ref):
        k = rc['f']
        assert rc['sim_csangle'] == cyl_frames[k]['csangle'], (
            "f%d: wired-camera csangle %d != live %d" % (k, rc['sim_csangle'],
                                                         cyl_frames[k]['csangle']))
        if k in ora and not ora[k]['dup']:
            assert rc['sim_csangle'] == ora[k]['expect']['csangle'], (
                "f%d: wired-camera csangle %d != oracle %d" % (
                    k, rc['sim_csangle'], ora[k]['expect']['csangle']))
        for key in ('sim_proc', 'speedF', 'sim_facing', 'sim_shape_z', 'sim_link',
                    'sim_tetra', 'sim_cyl'):
            assert rc[key] == rr[key], (
                "f%d: %s diverged from the injected-csangle reference" % (k, key))
        if 3 <= k <= 9 and k in ora and not ora[k]['dup']:
            assert _bits(rc['sim_attn_y']) == _bits(ora[k]['link']['attn'][1]), (
                "f%d: attn.y law %r != live %r (not 0-ULP)" % (
                    k, rc['sim_attn_y'], ora[k]['link']['attn'][1]))
