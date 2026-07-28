"""THE WAIT-STOP GATE: what does the game pose while Link is STOPPED, and does the sim pose it?

Session 58 handed over "the sim stops posing across the WAIT stop": Link stops into proc 4 at plan
frames 76-77, `FootSpeedF.step` early-returned at |mNormalSpeed| <= 0.001, and so the re-walk at 78
measured its `f31_2` off a toe stream still holding the WALKING poses from 74/75 -- a stride (2.617)
where the console takes a standing drift (0.379).

The fix was NOT "pose the WAITS idle blend". `fixtures/courtyard_node1_wait_s59.json` (LOCKED, live)
reads the under-body anim state at the halt and says what actually runs: at 76/77 `m34C3 == 0` (a
SINGLE anim, not a blend) on arc entry 285 = `waitatob.bck`, with the frame controller at
end/rate/start = 12/0.6/0.0. Those three are `mMove.field_0x10/0x68/0x6C`, which appear together in
exactly one place -- procWait_init's `checkRestHPAnime()` arm (d_a_player_main.cpp:6072),
`setSingleMoveAnime(ANM_WAITATOB, field_0x68, field_0x6C, field_0x10, field_0x70)`. Link is on his
last hearts here, so the WAIT stop plays the low-life "wait A->B" transition. Because a single
leaves `m34C3` at 0, it also resets the RE-WALK: `setMoveAnime` takes `f31 = 0` when m34C3 == 0, so
the WAITS/WALK blend at 78 restarts at frame 0 rather than carrying the phase.

Why this file exists rather than only `test_node1_console.py`: the endpoint moves for a dozen
reasons, the anim registers move for one. Score a WAIT-pose candidate here (offline, 0.2 s) before
spending a live run. Same discipline as `test_foot_draw_base.py`.

Truth page: `knowledge/model/wait-stop-pose.md`.
"""
import json
import os
import struct

import pytest

from harness.tetrapush import seeds


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_node1_wait_s59.json')))
LOG = json.load(open(_fx('courtyard_node1_console.json')))['log']
SAMPLES = {s['n']: s for s in FIX['samples']}

# `m_anm_heap_under[0].mIdx` (player +0x2F04) is the LkAnm.arc file index; these two are the whole
# window's under-body MOVE0. MOVE1's index lives at +0x2F14, NOT at the header's array spacing.
ARC_IDX = {294: 'waits', 285: 'waitatob'}


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulp(a, b):
    return abs(_bits(a) - _bits(b))


@pytest.fixture(scope="module")
def rollout():
    """Replay the locked plan once, snapshotting the under-body anim state + the drawn toe pose."""
    run = seeds.make_freerun(seeds.load_env())
    run.pre_seed_input(seeds.dtm_input_at(seeds.load_env())(0))
    snaps = {}
    for i, d in enumerate(LOG[:max(SAMPLES)]):
        run.step(d)
        L, F = run.link, run.link._foot
        st = F.st
        snaps[i + 1] = dict(
            proc=int(L.state), facing=int(L.facing) & 0xFFFF, speedF=float(L.speedF),
            nspeed=float(L.nspeed), msd=float(L.msd),
            m34C3=int(st.m34C3), move0=st.move0, move1=st.move1, ratio=float(st.ratio),
            m3598=float(st.m3598), m359C=float(F.prev_f312), m35B4=float(F.m35B4),
            fc0=dict(attr=int(st.fc0.attribute), end=float(st.fc0.end),
                     rate=float(st.fc0.rate), frame=float(st.fc0.frame)),
            fc1=dict(attr=int(st.fc1.attribute), end=float(st.fc1.end),
                     rate=float(st.fc1.rate), frame=float(st.fc1.frame)),
            t1=tuple(F.t1))
    return snaps


def test_the_stop_plays_the_low_life_waitatob_single_not_the_idle_blend(rollout):
    """The BRANCH, stated as the console's own registers. This is the assertion that would catch a
    future 'simplification' back to the WAITS/WALK idle arm: it is a different m34C3, a different
    anim, and a different frame-ctrl end."""
    for n in (76, 77):
        live, sim = SAMPLES[n], rollout[n]
        assert live['link']['proc'] == 4 and sim['proc'] == 4, "n=%d is no longer the WAIT stop" % n
        assert live['under']['m34C3'] == 0, "the console's WAIT stop is no longer a SINGLE anim"
        assert sim['m34C3'] == live['under']['m34C3'], \
            "n=%d: sim m34C3 %d vs console %d -- the WAIT arm diverged" % (
                n, sim['m34C3'], live['under']['m34C3'])
        assert ARC_IDX[live['under']['anm0']] == 'waitatob'
        assert sim['move0'] == 'waitatob', "n=%d poses %s, console poses waitatob" % (n, sim['move0'])
        # end/rate/start == mMove.field_0x10 / 0x68 / 0x6C, the arm's fingerprint. 12 is the HIO
        # OVERRIDE, not waitatob.bck's own frameMax (13) -- a model using the clip's would drift late.
        assert _bits(sim['fc0']['end']) == _bits(live['under']['fc0']['end']) == _bits(12.0)
        assert _bits(sim['fc0']['rate']) == _bits(live['under']['fc0']['rate'])
        assert sim['fc0']['attr'] == live['under']['fc0']['attr'] == 0     # EMode_NONE


def test_the_anim_clocks_track_the_console_bit_exact_across_the_stop(rollout):
    """Every under-body clock, 0-ULP, over the whole walk -> stop -> re-walk band.

    Three things are pinned that a plausible-but-wrong model gets wrong:
      * the single starts at frame 0 and advances 0.6/frame (76 -> 77),
      * MOVE1's controller takes ONE more update on the stop frame -- the actor-execute advance that
        precedes procWait_init's re-pose -- and then FREEZES, because setSingleMoveAnime clears its
        heap index (12798) and the model calc stops advancing a slot it no longer draws,
      * the re-walk at 78 restarts BOTH controllers at 0, because the single left m34C3 == 0 and
        `setMoveAnime`'s phase carry is gated on that.
    """
    for n in sorted(SAMPLES):
        live, sim = SAMPLES[n], rollout[n]
        for slot in ('fc0', 'fc1'):
            for k in ('frame', 'rate'):
                assert _bits(sim[slot][k]) == _bits(live['under'][slot][k]), \
                    "n=%d %s.%s off %d ULP (sim %.9f, console %.9f)" % (
                        n, slot, k, _ulp(sim[slot][k], live['under'][slot][k]),
                        sim[slot][k], live['under'][slot][k])
        assert _bits(sim['ratio']) == _bits(live['under']['ratio1']), "n=%d blend ratio" % n
        assert _bits(sim['m3598']) == _bits(live['link'] and live['foot']['m3598']), "n=%d m3598" % n
    # the three shape facts, read off the fixture so they are claims about the CONSOLE, not the sim
    assert SAMPLES[76]['under']['fc0']['frame'] == 0.0
    assert SAMPLES[77]['under']['fc0']['frame'] == pytest.approx(0.6, abs=1e-6)
    f75, f76, f77 = (SAMPLES[n]['under']['fc1']['frame'] for n in (75, 76, 77))
    assert f76 > f75, "MOVE1 no longer takes its actor-execute advance on the stop frame"
    assert _bits(f76) == _bits(f77), "MOVE1 no longer freezes once the single owns MOVE0"
    assert SAMPLES[78]['under']['fc0']['frame'] == 0.0 and SAMPLES[78]['under']['fc1']['frame'] == 0.0


def test_the_toe_stream_advances_across_the_stop_and_matches_the_console(rollout):
    """The POSE itself, 0-ULP in x/z against the console's `mFootData`.

    Alignment (verified on the known-exact walking frames before any claim): live mFootData at frame
    N is the pose DRAWN at N-1, so it pairs with the sim's stored `t1` after stepping N-1.

    Y is excluded on purpose, exactly as in `test_foot_draw_base.py`: `m35B8` (footBgCheck's
    draw-base Y shift) is unmodeled, and it cannot reach `f31_2` because the draw base is a Y
    rotation. If a future tier needs foot Y, that is the term to port."""
    order = ('rtoe', 'ltoe', 'rheel', 'lheel')
    checked = 0
    for n in sorted(SAMPLES):
        if (n - 1) not in rollout:
            continue
        sim = rollout[n - 1]['t1']
        for i, name in enumerate(order):
            live = SAMPLES[n]['foot'][name]
            for ax, off in (('x', 0), ('z', 2)):
                a, b = sim[i * 3 + off], live[off]
                assert _bits(a) == _bits(b), \
                    "pose drawn at frame %d: %s.%s off %d ULP (sim %.9f, console %.9f)" % (
                        n - 1, name, ax, _ulp(a, b), a, b)
                checked += 1
    assert checked == 5 * 4 * 2, "expected 5 samples x 4 points x 2 axes"

    # ...and it is genuinely ADVANCING while stopped -- the s58 failure mode was a frozen stream.
    assert rollout[75]['t1'] != rollout[76]['t1'] != rollout[77]['t1']


def test_the_foot_composition_state_matches_the_console(rollout):
    """m359C (the 0.3/0.7 smoothed f31_2) and m35B4 (last frame's mStickDistance) 0-ULP too --
    posMoveFromFootPos KEEPS RUNNING through the WAIT, which is why the stop is visible at all.
    m3598 == 0 across it (commonProcInit 5805) is what holds speedF at exactly 0 there.

    The two are read at DIFFERENT alignments, and that is a property of the halt, not of the model:
    a truncate-and-read pause lands after `posMoveFromFootPos` but before the end-of-execute tail at
    :11285-11289. So m359C (written inside posMoveFromFootPos) reads frame N's value, while m35B4 --
    written at :11288 beside `m34DE = shape_angle.y` and `m34EA = m34DC` -- still holds frame N-1's.
    `m34DE` proves it independently below, since facing actually changes at 78."""
    for n in sorted(SAMPLES):
        live, sim = SAMPLES[n]['foot'], rollout[n]
        assert _bits(sim['m359C']) == _bits(live['m359C']), \
            "n=%d m359C off %d ULP" % (n, _ulp(sim['m359C'], live['m359C']))
        if (n - 1) in rollout:                     # tail-block write: console lags a frame
            assert _bits(rollout[n - 1]['m35B4']) == _bits(live['m35B4']), "n=%d m35B4" % n
    for n in (76, 77):
        assert SAMPLES[n]['foot']['m3598'] == 0.0 and rollout[n]['m3598'] == 0.0
        assert SAMPLES[n]['link']['speedF'] == 0.0 and rollout[n]['speedF'] == 0.0
    # The independent check on that alignment: at 78 the console's facing moves 36817 -> 35295, and
    # the m34DE it reports is the OLD one -- same tail block, same one-frame lag as m35B4.
    assert SAMPLES[78]['link']['facing'] == 35295 and SAMPLES[78]['link']['m34DE'] == 36817
    assert rollout[77]['facing'] == SAMPLES[78]['link']['m34DE']


def test_the_healthy_stop_still_takes_the_idle_blend(rollout):
    """The default must not move. `low_life` is a SEEDED input (Link's life is not simulated), and
    every anchor and golden runs healthy -- where procWait_init calls setBlendMoveAnime and the stop
    poses the WAITS/WALK idle blend (m34C3 = 2) instead. Exercised directly so the healthy arm keeps
    a gate of its own rather than only being covered by "the goldens did not move"."""
    from tww_sim.core.anim.foot_speedf import FootSpeedF
    if not FootSpeedF.available():
        pytest.skip("generated anim data absent")
    f = FootSpeedF(native=False, sword=True)
    f.started = True
    f.pose_idle_blend(0.05, 2.4)
    assert f.st.m34C3 == 2 and f.st.move0 == 'waits' and f.st.move1 == 'walks'
    assert f.st.m3598 == 0.0 and f.st.ratio == 0.0
    g = FootSpeedF(native=False, sword=True)
    g.started = True
    g.enter_wait_rest_hp()
    assert g.st.m34C3 == 0 and g.st.move0 == 'waitatob' and g.st.m3598 == 0.0
    assert _bits(g.st.fc0.end) == _bits(12.0) and _bits(g.st.fc0.rate) == _bits(0.6)
