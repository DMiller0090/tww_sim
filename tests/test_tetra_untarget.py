"""Untarget-brakeslide (ATN_ACTOR proc 9) validation against the REAL any% TAS Courtyard push.

Seeds a LandState at each push roll entry (constant-momentum roll -- no foot-warming needed) and
replays the EXACT raw controller bytes extracted from the recorded movie GZLJ01.s02.dtm
(fixtures/courtyard_push_dtm.json, baked by harness/tetrapush/dtm_inputs.py). Asserts the sim
reproduces the untarget brakeslide -- the roll exits into ATN_ACTOR_MOVE (proc 9) and speedF FLIPS
26 -> the live value -- BIT-EXACT against the session-2 live capture, for BOTH push cycles:

    cycle 1 flip = -25.727313995361328   (captured proc-9 body frame)
    cycle 2 flip = -25.742912292480469

These flip magnitudes are the session-2 model's payload and are jitter-SAFE (settled scalar reads).
The EXACT frame of the flip / the proc-9 init frame are +-1 jitter-ambiguous in the single-stepped
capture ([[run-dtm-1frame-jitter]]) and are deliberately NOT asserted here -- pin those with a
jitter-free capture. The lock is driven target_present=True from the roll entry (the only L in the
window is the intended mid-roll re-pulse; the initial directional L is before the seed), so the
AttentionLock RELEASE fade -- not an oracle -- is what keeps the actor lock alive to the roll exit.

Purely additive: with no driven lock every land golden is byte-identical (tests/test_atn_actor.py).
"""
import json
import os
import struct

import pytest

from tww_sim.land.land import LandState, MOVE

_FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'fixtures', 'courtyard_push_dtm.json')


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope='module')
def push():
    return json.load(open(_FIX))


def _roll_entries(frames):
    """Game-frame indices where a FRONT_ROLL (proc 30) begins (a roll cycle's entry)."""
    out = []
    for i, f in enumerate(frames):
        p = f.get('live', {}).get('proc')
        if p == 30 and (i == 0 or frames[i - 1].get('live', {}).get('proc') != 30):
            out.append(i)
    return out


def _replay_from_roll(frames, entry, nsteps):
    """Seed a LandState mid-roll at `entry` (speedF pinned 26, couple_replay convention) and replay
    the fixture's raw DTM inputs for `nsteps` frames with Tetra as the driven lock-on actor. Returns
    the per-frame [(frame, dispatch_proc, speedF, nspeed)] trajectory."""
    e = frames[entry]['live']
    link = LandState(pos_x=e['pos'][0], pos_z=e['pos'][2], pos_y=e['pos'][1], facing=e['facing'],
                     travel=e['travel'], csangle=39432, state=30, nspeed=26.0, speedF=26.0,
                     use_anim=True, native=False, sword_drawn=True)
    link._roll_m3570 = False          # seeded mid-roll: grinds, no bonk (couple_replay convention)
    link._roll_entered = True         # `entry` IS the roll-entry frame: hold the anim ctrl this step
    # Bare non-coupled replay (no CC plow): sim-Link's rolled position diverges ~100u so the real
    # chaseAttention cone can't be computed -- inject the acquisition that happened live (see README Gap 2).
    link._atn_force_present = True
    # 2-frame controller-latency buffer, pre-seeded with the two frames delivered before `entry`.
    link._inbuf = []
    for k in (entry - 2, entry - 1):
        ip = frames[k]['inp']
        link._inbuf.append((ip['stickX'], ip['stickY'], ip['buttons'], ip['triggerL'], 128, 128))
    traj = []
    for i in range(entry, min(entry + nsteps, len(frames))):
        f = frames[i]
        ip = f['inp']
        t = f.get('tetra', {}).get('pos')
        link._atn_actor_pos = (t[0], t[2]) if t else None   # Tetra XZ = the lock-on actor (present)
        disp = link.state
        link.step(ip['stickX'], ip['stickY'], ip['buttons'], ip['triggerL'], 128, 128)
        traj.append((i, disp, link.speedF, link.nspeed))
    return traj


def test_fixture_alignment(push):
    """The baked fixture is the state-2 push, frame-aligned to the live capture."""
    assert push['F0'] == 44974
    assert push['seed']['proc'] == 6                               # state 2 = MOVE backslide
    assert abs(push['seed']['link']['speedF'] - (-24.574)) < 0.01   # hot EBS entry (below the roll)
    assert len(_roll_entries(push['frames'])) == 2                 # two push cycles


@pytest.mark.parametrize("cycle", [0, 1])
def test_untarget_flip_bit_exact(push, cycle):
    """The roll exits into proc 9 and speedF flips to the live value, BIT-EXACT, for each cycle.

    The expected flip is derived from the fixture's OWN live capture (the most-negative captured
    speedF in the cycle's window = the proc-9 body frame), not a hand-copied literal -- so it stays
    honest if the ground truth is re-captured. Because the exact FRAME is +-1 jitter-ambiguous, we
    compare the min speedF over the window, not a per-frame value: the untarget flip is the same
    scalar whichever frame it lands on."""
    frames = push['frames']
    entry = _roll_entries(frames)[cycle]
    win = range(entry, min(entry + 20, len(frames)))
    flip_live = min(frames[i]['live']['speedF'] for i in win)      # captured proc-9 body flip
    assert flip_live < -25.0, "the captured window should contain the untarget brakeslide flip"

    traj = _replay_from_roll(frames, entry, nsteps=20)
    assert traj[0][2] == 26.0                                       # the roll coasts at exactly 26
    assert any(disp == 9 for _, disp, _, _ in traj), "roll must exit into ATN_ACTOR_MOVE (proc 9)"
    flip = min(sp for _, _, sp, _ in traj)         # the untarget brakeslide = the most-negative speedF
    assert _bits(flip) == _bits(flip_live), (
        "cycle %d flip %r (bits %#x) != live %r (bits %#x)"
        % (cycle, flip, _bits(flip), flip_live, _bits(flip_live)))


@pytest.mark.parametrize("cycle", [0, 1])
def test_untarget_2frame_tier(push, cycle):
    """The untarget brakeslide is a 2-frame proc-9 (ATN_ACTOR_MOVE) tier, not 1: body1 = the flip
    (bit-exact, above), body2 = a SECOND setSpeedAndAngleAtnActor frame that decays the -26 by the
    gentle mAtnMove term (~0.26-0.28), and ONLY THEN does MOVE take over (~0.011/frame). Session 5
    RAM+asm PROVED this (the drop frame breaks INSIDE setSpeedAndAngleAtnActor with the ATN param
    family); session 6 modeled the actor-lock lifetime -- the reticle YJ_DELETE anim = 10 frames
    (`FADE_FRAMES`), and the attention's L-input delay is 1 (vs physics INPUT_DELAY=2) -- so proc 9
    runs 2 body frames driven by the REAL AttentionLock, with NO RAM-timeline injection.

    body2 is NOT yet bit-exact from the mid-roll seed (~0.0024 residual: csangle=39432 and
    travel/target are seeded approximately, so the ATN turn-chase cos term is slightly off); its
    ULP-exact value awaits the from-f0 coupled replay. So we assert the STRUCTURE (exactly 2 proc-9
    body frames), that body2 is a proc-9 ATN step (~0.27, distinguishable from the MOVE ~0.011 decel),
    and that it matches the fixture's own body2 within the mid-roll-seed residual."""
    frames = push['frames']
    entry = _roll_entries(frames)[cycle]
    traj = _replay_from_roll(frames, entry, nsteps=22)

    # Exactly two consecutive proc-9 BODY frames (the flip + body2). Before the session-6 lock-lifetime
    # fix (fade 8 + physics-delayed L) the lock dropped a frame early and only ONE body frame ran.
    body9 = [k for k, (_, disp, _, _) in enumerate(traj) if disp == 9]
    assert len(body9) == 2, "proc-9 tier must be 2 body frames, got %d (%r)" % (len(body9), body9)
    assert body9[1] == body9[0] + 1, "the two proc-9 body frames must be consecutive"

    flip = traj[body9[0]][2]
    body2 = traj[body9[1]][2]
    # body2 decays the flip by the gentle mAtnMove term, NOT the MOVE decel -> proves proc 9 (not the
    # MOVE foot path) ran it: a MOVE frame would drop only ~0.011, an ATN body2 drops ~0.27.
    assert 0.20 < (body2 - flip) < 0.35, "body2 must be a proc-9 ATN step, got d=%.5f" % (body2 - flip)

    # Fixture body2 = the frame right after its (argmin) flip -- located BY VALUE so the cycle-2
    # single-step capture +1 shift ([[run-dtm-1frame-jitter]]) doesn't matter (the sim is the clean one).
    win = list(range(entry, min(entry + 22, len(frames))))
    fi = min(win, key=lambda i: frames[i]['live']['speedF'])
    body2_live = frames[fi + 1]['live']['speedF']
    assert abs(body2 - body2_live) < 0.003, (
        "cycle %d body2 %.6f vs fixture %.6f (residual %.5f exceeds the mid-roll-seed budget)"
        % (cycle, body2, body2_live, body2 - body2_live))


def test_chase_acquires_mid_roll_not_at_state2(push):
    """Gap 2 grounded against the LIVE capture: the chaseAttention front-cone gate
    (`_atn_target_present`) is FALSE at state 2 (Tetra ~122 deg behind Link even with L held) and TRUE
    across the roll body (she swings into the +-90 deg front cone), so the lock can only acquire on the
    MID-ROLL L re-pulse -- never at the first held L. Evaluated at each frame's real live pose (Link
    pos+facing, Tetra XZ), so it is independent of any sim trajectory."""
    frames = push['frames']
    probe = LandState(native=False, use_anim=False)

    def present_at(i):
        lv = frames[i]['live']
        t = frames[i]['tetra']['pos']
        probe.pos_x, probe.pos_z = lv['pos'][0], lv['pos'][2]
        probe.facing = lv['facing'] & 0xFFFF
        probe._atn_actor_pos = (t[0], t[2])
        return probe._atn_target_present()

    # state 2 + the two ATN_MOVE frames before the first roll: L is held (f0-1) yet Tetra is behind ->
    # NOT chaseable, so no actor lock (live reads proc 6/7, never 8/9).
    for i in (0, 1, 2):
        assert present_at(i) is False, "frame %d: Tetra is behind Link, must be out of the front cone" % i

    # both roll bodies: Tetra is within the front cone (the acquisition window for the mid-roll L pulse).
    for cyc, entry in enumerate(_roll_entries(frames)):
        acq = [i for i in range(entry, entry + 8) if present_at(i)]
        assert len(acq) >= 6, "cycle %d roll body should be in-cone (chaseable), got %r" % (cyc, acq)


@pytest.mark.parametrize("cycle", [0, 1])
def test_untarget_backslide_unzeroed(push, cycle):
    """The MOVE backslide AFTER the 2-frame proc-9 tier must retain the flipped EBS speed, not
    collapse to 0. Before the started/getOldFrameFlg fix (foot_speedf.step_single_anim + the native
    w_step_single), the roll + proc-9 poses never set the oldFrameFlg (posMoveFromFootPos:2354), so
    the first negative-nspeed MOVE frame hit FootSpeedF.step()'s cold `not started and nspeed<=0`
    rest path and returned speedF=0 (probe: cyc1 f22-25 read 0.0 vs live ~-25.44). The step_atn /
    enter_wait_idle / enter_single paths already set it; step_single_anim now does too.

    With the fix the backslide is pure momentum -- m3598==0 so speedF == mNormalSpeed EXACTLY (a
    structural, seed-independent check) -- and it tracks the live decay within the same mid-roll-seed
    budget body2 carries (ULP-exactness of the magnitude awaits the from-f0 replay)."""
    frames = push['frames']
    entry = _roll_entries(frames)[cycle]
    traj = _replay_from_roll(frames, entry, nsteps=26)

    body9 = [k for k, (_, disp, _, _) in enumerate(traj) if disp == 9]
    assert len(body9) >= 2, "expected the 2-frame proc-9 tier before the backslide"
    b0, b1 = body9[0], body9[1]                    # the FIRST tier (a 26-frame window can re-lock later)
    assert b1 == b0 + 1, "the first proc-9 tier must be 2 consecutive body frames"

    # The clean MOVE backslide = the run of dispatch-MOVE(6) frames right after body2 (it ends when
    # the next L re-pulse re-enters an ATN/roll proc). Take that contiguous run.
    back = []
    for k in range(b1 + 1, len(traj)):
        i, disp, sp, ns = traj[k]
        if disp != MOVE:
            break
        back.append((i, sp, ns))
    assert len(back) >= 4, "expected a run of MOVE backslide frames after the tier, got %d" % len(back)

    # (1) un-zeroed + pure momentum: NOT the cold-path 0, and speedF == mNormalSpeed bit-for-bit.
    for i, sp, ns in back:
        assert abs(sp) > 25.0, (
            "cycle %d backslide f%d collapsed to %r (the cold `not started` path zero)" % (cycle, i, sp))
        assert _bits(sp) == _bits(ns), (
            "cycle %d backslide f%d speedF %r != mNormalSpeed %r (m3598 should be 0 -> pure momentum)"
            % (cycle, i, sp, ns))

    # (2) tracks live within the mid-roll-seed budget. Align by VALUE (cyc2 has the +1 capture shift):
    # live flip = argmin speedF, body2 = flip+1, backslide starts flip+2; compare only clean MOVE frames.
    win = range(entry, min(entry + 26, len(frames)))
    fi = min(win, key=lambda j: frames[j]['live']['speedF'])
    compared = 0
    for n, (i, sp, _ns) in enumerate(back):
        j = fi + 2 + n
        if j >= len(frames) or frames[j]['live']['proc'] != MOVE:
            break
        live_sp = frames[j]['live']['speedF']
        assert abs(sp - live_sp) < 0.003, (
            "cycle %d backslide sim f%d %.6f vs live f%d %.6f (residual %.5f > mid-roll-seed budget)"
            % (cycle, i, sp, j, live_sp, sp - live_sp))
        compared += 1
    assert compared >= 3, "expected to compare >=3 clean backslide frames against live, got %d" % compared
