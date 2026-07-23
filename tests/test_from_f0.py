"""The Courtyard from-f0 coupled replay, live-gated against the locked RAM capture -- 0-ULP.

`harness/tetrapush/from_f0` wires BOTH gated plow laws (`link_plow` = Link's full-depth recoil,
`tetra_plow` = Tetra's full-depth push) into a closed-loop `LandState` replay driven by the real DTM
controller bytes. This gate proves the coupling is bit-exact where the sim's proc physics are modelled.

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`, Dereck's hard rule, session 24): every sim-vs-console
assertion in this file is `_bits(sim) == _bits(live)` (0 ULP) or it is deleted. There are NO
`err < eps` position/plow tolerances -- a ~5-56 ULP/step position residual hid under "within capture
precision" gates for ~15 sessions until the multi-cycle plow amplifier (~1.35x/contact-frame) blew it
up to a 93-u closed-loop drift. So:
  * The DYNAMICS (proc, speedF, facing, lean, csangle, the wired-camera attn.y, setcol centre) are
    genuinely bit-exact and asserted `_bits == _bits` here.
  * The POSITION bar is the two one-step-from-EXACT-state gates
    (`test_onestep_pos_bit_exact_from_exact_state` for Link, `test_tetra_push_bit_exact_from_exact_state`
    for Tetra). Both are HARD PASSES on f2..f43 as of session 27 (bug #1 closed): stepping once from
    the exact captured state with the CONSOLE push (`cc_push_pair` on the model's EXEC centre)
    reproduces the DETERMINISTIC per-op capture (`courtyard_push_perop.json`, `posMove` breakpoint,
    proven == the cyl fixture 0-ULP f0..43) BIT-FOR-BIT. f1 is the seed-frame boundary (f0's exec
    centre is not offline-reconstructable) and is not asserted.
  * SESSION-27 FINDING: the session-24 "two bugs" collapsed to ONE. Bug #1 was the push/recoil law
    computed the DERIVED full-depth-from-SETTLED way (`full_depth_push`, ~1e-5 u off) instead of the
    console's half-depth-from-EXEC `co_move_pair`. Fixing it made Link's position 0-ULP too -- so the
    "roll-entry foot term" (bug #2) was that same recoil error measured through Link's pos (larger at
    roll entry, where the geometry ramps), NOT a separate foot-term bug. Link's foot term was exact
    all along (recoil is independently pinned to Tetra's deterministic ΔTetra, so no compensating
    error is possible).
  * A handful of non-fidelity checks survive, each explicitly relabelled: the FreeRun-vs-replay API
    contract and the wired-camera / pad-decode gates.

The fixtures are the locked live capture, all from slot 2 and IMMUTABLE: `courtyard_push_cyl.json`
(per-frame Link Co centre + csangle + both actors' positions, single-stepped); `courtyard_push_dtm.json`
(raw controller bytes); `courtyard_push_seed.json` (the state-2 seed's HIDDEN mNormalSpeed, a
deterministic single read); `courtyard_push_setcol.json` (the session-14 setCollision breakpoint reads,
deterministic). The gated range (f<=23 / f<=43) is BEFORE the cyc2 f44 double-read.

The TRUE f0 seed (state 2) is CLOSED for the DYNAMICS (session 12, `test_true_f0_seed_bit_exact`):
seeded at f0 with the measured mNormalSpeed, the replay's every speedF/proc is bit-exact from the first
stepped frame (the gap was seeding `nspeed = speedF` when at f0 speedF LAGS mNormalSpeed a frame). The
whole from-f0 chain -- roll-entry-seeded AND state-2-seeded -- is dynamics-bit-exact through cycle 2's
roll; position is the open 0-ULP gap gated below.
"""
import json
import os
import struct

import pytest

from harness.tetrapush.from_f0 import replay

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CYL = os.path.join(_ROOT, 'fixtures', 'courtyard_push_cyl.json')
_DTM = os.path.join(_ROOT, 'fixtures', 'courtyard_push_dtm.json')
_SEED = os.path.join(_ROOT, 'fixtures', 'courtyard_push_seed.json')
_PEROP = os.path.join(_ROOT, 'fixtures', 'courtyard_push_perop.json')

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


@pytest.fixture(scope='module')
def seed():
    if not os.path.exists(_SEED):
        return None
    return json.load(open(_SEED))


@pytest.fixture(scope='module')
def perop():
    """The session-26 DETERMINISTIC per-op capture (`_notes/tetrapush-perop_probe.py`): both actors'
    positions read at the JP `posMove` (0x80106514) breakpoint, one hit per game frame f0..f43 (the
    breakpoint pins the frame count -- immune to any single-step edge jitter). This is the deterministic
    position ground truth `[[zero-ulp-tests-only]]` requires."""
    if not os.path.exists(_PEROP):
        return None
    return json.load(open(_PEROP))['rows']


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


def test_chained_replay_through_cyc2_roll_bit_exact(fix):
    """THE full chained replay (session 11): seeded at the first roll entry, the sim runs UNBROKEN
    through cycle 1 AND the backslide->roll-setup transition AND cycle 2's roll -- f4..f44 -- with
    every Link speedF 0-ULP and every proc matching live. This closes the backslide->roll-setup
    blocker: the +18 re-target flip lands on the right frame (f28, -25.15 -> +18.574) and cycle 2's
    roll triggers on the right frame (f29), because the DTM-driven replay runs at input_delay=1 (the
    DTM stream IS the polled pad, one pipeline stage in -- live-probed s11: m34E8/roll/soft-L all land
    1 frame after the DTM).

    DYNAMICS ONLY (0-ULP): proc + speedF. Position is NOT asserted here -- its 0-ULP bar is
    `test_onestep_pos_bit_exact_from_exact_state` (the position residual, the 2 open bugs). Gated range
    stops at f44 -- BEFORE the cyl fixture's single-step-jittered cyc2 untarget (f45+, a known capture
    corruption, session 8; the DTM fixture has the clean -25.74 flip there)."""
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


def test_true_f0_seed_bit_exact(fix, seed):
    """THE true f0 seed (session 12): seeded at STATE 2 itself (f0, proc MOVE) with the live-measured
    mNormalSpeed (`courtyard_push_seed.json` link.nspeed), the from-f0 replay's DYNAMICS are bit-exact
    from the FIRST stepped frame -- f1..f44 every Link speedF 0-ULP, every proc matching live. This
    closes the last from-f0 dynamics gap (position's 0-ULP bar is the divergence gate below).

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


_SETCOL = os.path.join(_ROOT, 'fixtures', 'courtyard_push_setcol.json')


@pytest.fixture(scope='module')
def setcol():
    if not os.path.exists(_SETCOL):
        pytest.skip("setCollision breakpoint fixture not present (session-14 probe)")
    return json.load(open(_SETCOL))['frames']


def test_settled_center_law_half_depth(fix, setcol):
    """The mCyl TIMING law (session 14, breakpoint-pinned) -- 0-ULP vs the DETERMINISTIC setcol
    capture. The pause-boundary mCyl the gated plow laws consume equals setCollision's execute-pass
    midpoint PLUS the scene CC pass's immediate half-depth SetPosCorrect write away from Tetra (the
    plain decomp 50/50 rank split). `_cc_settled_center(cyl_exec(k), tetra(k))` reproduces the
    capture's `link.cyl` BIT-FOR-BIT on every setcol-probed frame (f1..12, where the deterministic
    breakpoint `cyl` equals the settled centre exactly). Also the closure of the session-9 "2x
    doubling" sub-puzzle: full-depth-from-the-settled-centre == half-depth-from-the-exec-centre."""
    from harness.tetrapush.from_f0 import _cc_settled_center
    cyl_frames, _ = fix
    for r in setcol:
        k = r['f']
        fx = cyl_frames[k]['link']['cyl']
        t = cyl_frames[k]['tetra']['pos']
        sx, sz = _cc_settled_center((r['cyl_exec'][0], r['cyl_exec'][2]), (t[0], t[2]))
        assert _bits(sx) == _bits(fx[0]) and _bits(sz) == _bits(fx[-1]), (
            "frame %d: settled centre (%r, %r) != live (%r, %r) -- not 0-ULP" % (
                k, sx, sz, fx[0], fx[-1]))


def test_setcollision_is_execute_time_midpoint(setcol):
    """setCollision's write IS the plain root/neck nodeMtx midpoint at call time (execute-pass
    matrices, post-posMove pre-CC-push base) -- read at the JP 0x8011a670 breakpoint, BIT-FOR-BIT
    (0 ULP) on every probed frame f1..12 (proc-7, the roll entry, and the roll bodies): the midpoint
    `0.5*(root+neck)` equals the freshly-written `cyl_exec` exactly. The draw-pass matrices the
    session-13 offline fits compared against are a DIFFERENT base -- never use pause-boundary nodeMtx
    as the setCollision source. Deterministic capture -> a legit 0-ULP gate."""
    for r in setcol:
        mx = 0.5 * (r['root'][0] + r['neck'][0])
        mz = 0.5 * (r['root'][2] + r['neck'][2])
        assert _bits(mx) == _bits(r['cyl_exec'][0]) and _bits(mz) == _bits(r['cyl_exec'][2]), (
            "frame %d: exec midpoint (%r, %r) != cyl_exec (%r, %r) -- not 0-ULP" % (
                r['f'], mx, mz, r['cyl_exec'][0], r['cyl_exec'][2]))


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


def test_closed_loop_computed_replay_dynamics_bit_exact(fix, seed, eyes):
    """The self-contained replay's DYNAMICS are bit-exact (session 16), asserted 0-ULP here.
    `centers='computed'` (Link's Co centre rebuilt every frame from the sim's OWN pose; only the
    static state-2 seed, the DTM bytes, csangle, and the Tetra eye stream are consumed) chains from
    STATE 2 with every proc 0-ULP-matching live and every speedF + lean BIT-FOR-BIT vs live f1..f43,
    through both rolls, both untarget tiers, and the whole coupled plow.

    POSITION and FACING are NOT asserted here (per `[[zero-ulp-tests-only]]`): the closed loop drifts
    off the SEED-frame boundary. With bug #1 fixed (session 27) the per-frame push is 0-ULP f2..f43,
    so the ~93-u drift the session-24 xfails cited COLLAPSED to ~4 u -- what remains is the single f1
    seed-frame push (from f0's exec centre, not offline-reconstructable, ~9 ULP) amplified through the
    plow feedback (depth = 80 - dist, ~1.35x/contact-frame; the drift is DIFFERENTIAL, e_link ~
    -e_tetra), which also perturbs the proc-9 eye-aim bearing so facing carries a few-BAM echo. The
    per-step 0-ULP bar (which the closed loop's drift is DOWNSTREAM of) is
    `test_onestep_pos_bit_exact_from_exact_state` -- a HARD PASS on f2..f43. Closing the closed loop
    to 0-ULP would need f0's exec centre (one deterministic `setCollision`-breakpoint read at the
    seed frame); the LAW is already 0-ULP (`test_facing_and_lean_bit_exact_with_eye_aim`, diag)."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    cyl_frames, dtm_frames = fix
    rows = replay(cyl_frames, _input_at(dtm_frames), 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers='computed', eyes=eyes,
                  seed_old_pose=seed.get('old_pose'))
    for d in rows:
        assert d['sim_proc'] == d['live_proc'], (
            "frame %d: closed-loop proc %d != live %d" % (d['f'], d['sim_proc'], d['live_proc']))
        assert _bits(d['speedF']) == _bits(d['live_speedF']), (
            "frame %d: closed-loop speedF %r != live %r (not 0-ULP)" % (
                d['f'], d['speedF'], d['live_speedF']))
        assert d['sim_shape_z'] == d['live_shape_z'], (
            "frame %d: closed-loop lean %d != live %d" % (d['f'], d['sim_shape_z'], d['live_shape_z']))


def _onestep_console_push(cyl_frames, dtm_frames, seed, eyes):
    """Shared driver for the two one-step-from-EXACT-state 0-ULP gates (session 27). Each frame: reset
    the sim to the EXACT captured state[k-1] (pos + Tetra), feed the CONSOLE push
    (`cc_push_pair` on the MODEL's computed EXEC centre at k-1 -- the decomp 50/50 half-depth split),
    step ONCE, and yield the sim's resulting pos[k]. This isolates the coupled step's OWN error from
    accumulation. The model's exec centre is bit-exact given the exact pos (== `courtyard_push_setcol.
    json`'s breakpoint `cyl_exec`, 0 ULP f1..12), so the push it feeds is console-exact.

    f1 (k==1) is the SEED-frame boundary: its incoming push comes from f0's exec centre, which the
    seed frame does not carry (`from_f0._seed_pose_f0` -- no f-1 lean/morf), so it falls back to
    `full_depth_push` on the settled seed centre. It is flagged `seed_frame=True` and NOT asserted by
    the callers (the sole non-0-ULP frame; ~9 ULP z). Every other frame f2..f43 (42 consecutive) is
    driven by the model's own exec centre and yields 0-ULP.

    Yields ``{k, proc, seed_frame, sim_link, sim_tetra}``."""
    from harness.tetrapush.from_f0 import (FreeRun, cc_push_pair, full_depth_push,
                                           _computed_center)
    from tww_sim.core.fp import f32
    input_at = _input_at(dtm_frames)
    run = FreeRun(cyl_frames[0], seed_nspeed=seed['link']['nspeed'], computed_pose=True,
                  seed_old_pose=seed.get('old_pose'))
    run.pre_seed_input(input_at(0))
    link = run.link
    for k in range(1, 44):
        prev = cyl_frames[k - 1]
        link.pos_x = f32(prev['link']['pos'][0]); link.pos_z = f32(prev['link']['pos'][2])
        link.pos_y = f32(prev['link']['pos'][1])
        run.tx = f32(prev['tetra']['pos'][0]); run.tz = f32(prev['tetra']['pos'][2])
        seed_frame = (k == 1)
        if seed_frame:
            run.pend_link, run.pend_tetra = full_depth_push(
                cyl_frames[0]['link']['cyl'], (run.tx, run.tz))
        else:
            # exec centre at k-1 from the model (pose at k-1, exact pos just reset). init frame =
            # whether k-1 dispatched a proc *_init (commonProcInit zeroes the base lean).
            init_km1 = prev['proc'] != cyl_frames[k - 2]['proc']
            cx = _computed_center(link, init_frame=init_km1)
            run.pend_link, run.pend_tetra = cc_push_pair(cx, (run.tx, run.tz))
        eye = eyes[k - 1] if (eyes is not None and k - 1 < len(eyes)) else None
        # NO center= : the OUTGOING push is recomputed by the model (irrelevant -- overwritten next
        # iteration); only the INCOMING pend we set above is consumed this step.
        row = run.step(input_at(k), csangle=cyl_frames[k - 1]['csangle'], eye=eye)
        yield dict(k=k, proc=cyl_frames[k]['proc'], seed_frame=seed_frame,
                   sim_link=row['sim_link'], sim_tetra=row['sim_tetra'])


def _perop_pos(perop):
    """Deterministic per-op positions keyed by frame idx: ``{k: {'link':(x,y,z), 'tetra':(x,y,z)}}``."""
    return {r['idx']: dict(link=r['entry']['pos'], tetra=r['entry']['tetra']['pos'])
            for r in perop if r.get('entry')}


def test_perop_confirms_cyl_positions_are_deterministic(fix, perop):
    """DETERMINISM PROOF (session 26): the per-op `posMove`-breakpoint capture and the single-stepped
    cyl fixture are two INDEPENDENT live captures (different stepping paths), yet both actors' positions
    agree BIT-FOR-BIT (0 ULP) at every game frame f0..f43. So the cyl POSITIONS are exact deterministic
    ground truth over the WHOLE window (not just the setcol-confirmed f1..12) -- the "single-step ~1e-5 u
    noise floor" that the session-24 xfails cited does NOT apply to this held-stick push window, and the
    ~5-56 ULP one-step divergence is a REAL sim-vs-console residual (bugs #1/#2), not fixture noise. This
    makes the per-op fixture the deterministic position bar the two open bugs are gated against."""
    if perop is None:
        pytest.skip("per-op capture fixture not present (need a live slot-2 breakpoint capture)")
    cyl_frames, _ = fix
    bad = []
    for r in perop:
        e = r.get('entry')
        if e is None:
            continue
        k = r['idx']
        if k >= len(cyl_frames):
            break
        lc, tc = cyl_frames[k]['link']['pos'], cyl_frames[k]['tetra']['pos']
        lp, tp = e['pos'], e['tetra']['pos']
        for lbl, a, b in (('Lx', lp[0], lc[0]), ('Lz', lp[2], lc[2]),
                          ('Tx', tp[0], tc[0]), ('Tz', tp[2], tc[2])):
            if _bits(a) != _bits(b):
                bad.append("f%d %s %+d ULP" % (k, lbl, _bits(a) - _bits(b)))
    assert not bad, "per-op breakpoint capture disagrees with the cyl fixture: " + ", ".join(bad)


def test_onestep_pos_bit_exact_from_exact_state(fix, seed, eyes, perop):
    """THE 0-ULP DIVERGENCE GATE (session 24; FLIPPED to a HARD PASS session 27 -- bug #1 closed):
    from the EXACT captured state[k-1], stepping once with the CONSOLE push (`cc_push_pair` on the
    model's own EXEC centre) reproduces the DETERMINISTIC per-op pos[k] BIT-FOR-BIT (0 ULP) on every
    frame the model can compute the incoming exec centre -- f2..f43 (42 consecutive frames), Link's
    full coupled position (foot term + recoil).

    Target = `courtyard_push_perop.json` (the `posMove`-breakpoint capture, proven == the cyl fixture
    0-ULP f0..43 by `test_perop_confirms_cyl_positions_are_deterministic`) -- a DETERMINISTIC bar per
    `[[zero-ulp-tests-only]]`, not the single-stepped fixture.

    Session-27 finding -- ONE bug, not two: the session-24 xfail blamed a "DASH/ROLL foot-term
    sub-ULP" (a supposed bug #2, the f3-5 spike). It was misdiagnosed. The spike was the RECOIL error
    (bug #1: the push was the DERIVED full-depth-from-SETTLED `full_depth_push`, ~1e-5 u off, larger
    at roll entry where the geometry ramps) measured THROUGH Link's position. Feeding the console
    push (`cc_push_pair` on the exec centre) makes Link's one-step position 0-ULP -- his foot term
    was exact all along (the recoil is independently pinned to Tetra's deterministic ΔTetra, so no
    compensating error is possible). f1 is the seed-frame boundary (f0's exec centre is not
    offline-reconstructable) and is not asserted. Per-frame ULP table:
    `python -m harness.tetrapush.onestep_divergence`."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    if perop is None:
        pytest.skip("per-op deterministic capture not present")
    cyl_frames, dtm_frames = fix
    pos = _perop_pos(perop)
    diverged = []
    checked = 0
    for r in _onestep_console_push(cyl_frames, dtm_frames, seed, eyes):
        if r['seed_frame'] or r['k'] not in pos:
            continue
        lv = pos[r['k']]['link']
        ex = abs(_bits(r['sim_link'][0]) - _bits(lv[0]))
        ez = abs(_bits(r['sim_link'][1]) - _bits(lv[2]))
        checked += 1
        if ex or ez:
            diverged.append((r['k'], r['proc'], ex, ez))
    assert checked >= 40, "expected f2..f43 covered, got %d" % checked
    assert not diverged, "one-step Link pos != deterministic (0 ULP required); frames [f,proc,xULP,zULP]: " \
        + ", ".join("[f%d p%d x%d z%d]" % d for d in diverged)


def test_tetra_push_bit_exact_from_exact_state(fix, seed, eyes, perop):
    """THE PUSH-LAW 0-ULP DIVERGENCE GATE (session 24; FLIPPED to a HARD PASS session 27 -- bug #1
    closed). Tetra's motion is PURELY the CC push (no foot term -- stt-3, speedF 0, the whole
    window), so her one-step position isolates the push/recoil law with NO foot-term confound. From
    the EXACT captured state[k-1], the console push (`cc_push_pair` on the model's EXEC centre)
    reproduces the DETERMINISTIC per-op Tetra pos[k] BIT-FOR-BIT on f2..f43.

    This is the model-driven twin of `test_tetra_plow.py::test_console_push_bit_exact_vs_deterministic`
    (which uses the setcol breakpoint exec centre directly, covering f1..12). Here the model's own
    computed exec centre carries it to f43 -- proving the model reproduces the exec centre 0-ULP
    beyond the setcol range. f1 is the seed-frame boundary (not asserted). The recoil == -push
    Newton invariant is `test_full_depth_push_recoil_is_exact_opposite_of_tetra` (a pure-code check
    on the seed-fallback `full_depth_push`)."""
    if seed is None:
        pytest.skip("state-2 seed fixture not present")
    if perop is None:
        pytest.skip("per-op deterministic capture not present")
    cyl_frames, dtm_frames = fix
    pos = _perop_pos(perop)
    diverged = []
    checked = 0
    for r in _onestep_console_push(cyl_frames, dtm_frames, seed, eyes):
        if r['seed_frame'] or r['k'] not in pos:
            continue
        lv = pos[r['k']]['tetra']
        ex = abs(_bits(r['sim_tetra'][0]) - _bits(lv[0]))
        ez = abs(_bits(r['sim_tetra'][1]) - _bits(lv[2]))
        checked += 1
        if ex or ez:
            diverged.append((r['k'], r['proc'], ex, ez))
    assert checked >= 40, "expected f2..f43 covered, got %d" % checked
    assert not diverged, "one-step Tetra push != deterministic (0 ULP required); frames [f,proc,xULP,zULP]: " \
        + ", ".join("[f%d p%d x%d z%d]" % d for d in diverged)


def test_full_depth_push_recoil_is_exact_opposite_of_tetra(fix):
    """SELF-CONSISTENCY (session 24; CLOSED session 26, offline -- bug #1's Newton's-3rd-law part):
    for a single same-rank Co pair the two actors eject equal-and-opposite -- Link's recoil delta is
    the exact negative of Tetra's push delta (bit-for-bit), the way the decomp `cc_push.co_move_pair`
    guarantees (vec1/vec2 sum to 0, live-confirmed). `full_depth_push` used to violate this by ~1 ULP
    (a direct f32 recoil delta vs an f64 new-minus-old Tetra move); it now returns Tetra's push as the
    exact f32 sign flip `-recoil` off the SAME dist/pushFactor, so the invariant holds with no live
    capture. This is a PURE-CODE 0-ULP gate (no fixture-precision dependence). `full_depth_push` is
    now the SEED-frame (f0->f1) fallback only (session 27); the console push law that closed bug #1's
    exec-vs-settled gap is `cc_push_pair` (`test_tetra_push_bit_exact_from_exact_state`, now a hard
    pass). The invariant still matters: the seed-frame push must eject equal-and-opposite too."""
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
