"""THE CO-CENTRE SEAM, SETTLED ON CONSOLE -- AND IT WAS AN ANIM FRAME, NOT A CENTRE.

Session 89 found two implementations of Link's body Co centre disagreeing by 1-2 ULP with nothing
gating them against each other, and could not say which was right: both console captures in hand fell
on candidates where the two AGREE, so neither discriminated. It named the experiment instead --
deliver a BLOCKED candidate, where `body_cyl` predicts a 49.8582 u lunge out through the seam and
`foot_fk` predicts 0.1534 u and no clip, 49.9665 u apart.

Session 90 delivered it. The console landed on `body_cyl`, to the bit, on three samples and both
actors. But the root cause is one level under the seam and it is not a centre at all: the two ports
were sampling the `rollf` anim at two different **f32 frames**.

    FrameCtrl.set stored the Python double 1.1 that enter_roll passes, where J3DFrameCtrl::mRate is
    f32. At roll frame 2.2 -> 3.3 the true f32 sum is an EXACT TIE, so the double's head start broke
    it DOWN to 3.299999952316284 where the hardware rounds half-to-even UP to 3.3000001907348633 --
    which is what LandState.roll_frame, accumulating from an f32 ROLL_RATE, already had.

One ULP of anim frame -> 3 ULP of root translate -> 1 ULP of Co centre -> 1 ULP of Tetra -> the clip
verdict. Neither port was wrong; they were being asked different questions. With `FrameCtrl` f32 at
its own boundary they agree bit-for-bit, the DEFAULT composite reproduces the capture 0-ULP, and all
four cross-engine rejections deliver.

`fixtures/courtyard_centre_seam_s90_console.json` is an IMMUTABLE console capture -- for a fixed
input log the console never moves, so a failure here is the sim's. Offline (replays the locked log).
"""
import json
import os
import struct
import warnings

import pytest

from harness.tetrapush import cross_engine as XE
from harness.tetrapush import entry_search as ES
from harness.tetrapush import from_f0 as F0
from tww_sim.core import fp
from tww_sim.core.anim import anim_state, body_cyl, foot_fk
from tww_sim.land.land import FRONT_ROLL, LandState


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures',
                        name)


CON = json.load(open(_fx('courtyard_centre_seam_s90_console.json')))


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope="module")
def seed():
    return ES.console_seed()


@pytest.fixture(scope="module")
def rollout(seed):
    """The candidate's composite on the DEFAULT engine -- no port swapping anywhere in this file."""
    log, ix = XE.composite_log(CON['candidate'], seed)
    assert log == CON['log'], "the composite no longer builds the log the console was given"
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return {r['i']: r for r in XE.composite_rollout(log)}, ix


# ------------------------------------------------------------------ the console, which decides

def test_the_console_capture_is_reproduced_0_ulp_on_both_actors(rollout):
    """THE GATE. Three samples off one blocked candidate, read at the PauseMovie halt, and the plain
    engine has to reproduce every one on Link AND Tetra with no tolerance anywhere."""
    rows, _ix = rollout
    for s in CON['samples']:
        m, lk, te = rows[s['i']], s['link'], s['tetra']
        assert _bits(lk['x']) == _bits(m['link_x']), s['n']
        assert _bits(lk['z']) == _bits(m['link_z']), s['n']
        assert lk['facing'] == m['facing'] and lk['proc'] == m['proc'], s['n']
        assert _bits(lk['speedF']) == _bits(m['speedF']), s['n']
        assert _bits(te['x']) == _bits(m['tetra_x']), s['n']
        assert _bits(te['z']) == _bits(m['tetra_z']), s['n']


def test_the_samples_actually_discriminated(rollout):
    """That the capture SETTLED anything is a property of the samples, not of the conclusion. Each one
    had to be a frame where the two ports predicted different numbers -- otherwise three 0-ULP reads
    prove only that the log replays. The cut frame carries the whole verdict (49.97 u apart, so the
    console could not land between them); the other two discriminate at 1 ULP before any drift."""
    cut = CON['plan']['cut_i']
    assert any(s['i'] == cut for s in CON['samples']), "the decisive frame must be in the capture"
    for s in CON['samples']:
        a, b = s['pre_fix']['footfk'], s['pre_fix']['body_cyl']
        assert any(_bits(a[k]) != _bits(b[k]) for k in a), s['n']
    assert CON['the_split']['separation'] > XE.CLIP_LUNGE_MIN
    assert CON['the_split']['pre_fix_moved']['footfk'] < 1.0
    assert CON['the_split']['pre_fix_moved']['body_cyl'] == pytest.approx(
        CON['prediction']['lunge'], abs=1e-4)
    assert CON['the_split']['console_moved_off_old'] == pytest.approx(
        CON['prediction']['lunge'], abs=1e-4)


# ------------------------------------------------------------------------- the root cause, pinned

def test_the_frame_ctrl_holds_f32_members_like_the_game_does():
    """The fix, at the boundary that owns it. `J3DFrameCtrl`'s float members are f32, so `set` must
    round whatever a caller hands it -- passing a Python double literal is the bug, and no caller
    should be able to reintroduce it."""
    fc = anim_state.FrameCtrl()
    fc.set(anim_state.EMode_NONE, 0, 19.0, 1.1, 0.0)
    for name in ('start', 'end', 'rate', 'frame', 'loop'):
        v = getattr(fc, name)
        assert v == fp.f32(v), name
    assert fc.rate == fp.f32(1.1) != 1.1


def test_the_double_rate_breaks_the_tie_the_wrong_way():
    """The arithmetic itself, so the diagnosis cannot be lost. 2.2 + 1.1 in f32 lands EXACTLY on the
    midpoint between two representables; round-half-to-even picks the upper one, and only a rate that
    is fractionally small -- a double 1.1 -- misses it."""
    f22 = fp.f32(2.2000000476837158)
    exact_tie = fp.fadds(f22, fp.f32(1.1))
    assert exact_tie == 3.3000001907348633                 # what the hardware (and roll_frame) gives
    assert fp.fadds(f22, 1.1) == 3.299999952316284         # what the double rate gave
    assert _bits(exact_tie) - _bits(fp.fadds(f22, 1.1)) == 1


def test_the_two_accumulators_of_the_anim_frame_agree_every_roll_frame(rollout):
    """The seam as a STATE duplication, which is the reusable lesson. `LandState.roll_frame` and the
    pose driver's `fc0.frame` are two accumulators of one game quantity; they diverged by a ULP for
    nine sessions because nothing compared them. Now something does."""
    rows, ix = rollout
    _log, _ix2 = XE.composite_log(CON['candidate'], ES.console_seed())
    run = _fresh_run()
    n = 0
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, inp in enumerate(_log):
            run.step(inp)
            lk = run.link
            if ix['entry_i'] < i <= ix['b_log'] and (lk.state & 0xFF) == FRONT_ROLL:
                assert _bits(lk._foot.st.fc0.frame) == _bits(lk.roll_frame), i
                n += 1
    assert n >= 10, "the roll must actually have been walked"


def test_the_two_centre_ports_now_agree_bit_for_bit(rollout):
    """What the fix bought, measured on the candidate that exposed the gap: same quantity, two
    routes, and now the same bits on every roll frame. This is the gate `test_body_co_native.py`
    could never be -- that one compares FootFK's native fold against FootFK's own Python loop."""
    _rows, ix = rollout
    log, _ = XE.composite_log(CON['candidate'], ES.console_seed())
    run = _fresh_run()
    n = 0
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, inp in enumerate(log):
            run.step(inp)
            lk = run.link
            if not (ix['entry_i'] < i <= ix['b_log']) or (lk.state & 0xFF) != FRONT_ROLL:
                continue
            bl, tw = body_cyl.co_leans(lk)
            a = F0._computed_center(lk, init_frame=False)
            b = body_cyl.roll_co_center(lk.pos_x, lk.pos_z, lk.facing, lk.roll_frame,
                                        shape_z=bl, body_lean=tw)
            assert _bits(a[0]) == _bits(b[0]) and _bits(a[1]) == _bits(b[1]), i
            n += 1
    assert n >= 10
    assert body_cyl.roll_co_center is not foot_fk.FootFK.body_co_center   # still two routes


def test_the_seam_cost_four_candidates_and_they_are_back(seed):
    """What settling it was worth. The four the filter rejected are the four it now passes, at the
    same frame count -- so the population is 55 of 55 and the objective's answer did not move."""
    src = json.load(open(_fx('courtyard_entry_s87_hits.json')))['rows']
    rej = json.load(open(_fx('courtyard_entry_s89_hits.json')))['rejected']
    assert len(rej) == 4
    for row in rej:
        hit = next(h for h in src if h['plan'] == row['plan'] and h['m351C'] == row['m351C'])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r = XE.agree(hit, seed=seed)
        assert r['deliverable'] and r['worst_ulp'] == 0, row['plan']


def _fresh_run():
    from harness.rollstab import turnaround as TA
    from harness.tetrapush import seeds as SD
    env = SD.load_env()
    run = SD.make_freerun(env)
    run.wire_walls(link=TA.WALLS, tetra=TA.WALLS)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    return run


def test_land_state_roll_rate_is_the_f32_the_frame_ctrl_now_holds():
    """The two constants, tied together so a future edit to one is caught by the other."""
    assert LandState.ROLL_RATE == fp.f32(1.1)
    fc = anim_state.FrameCtrl()
    fc.set(anim_state.EMode_NONE, 0.0, LandState.ROLL_END, 1.1, 0.0)
    assert fc.rate == LandState.ROLL_RATE
