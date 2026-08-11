"""The roll's ``b_trig`` CUT arm in C == the Python procs, 0 ULP -- the clip roll on the native step.

`_anmc._proc_roll` used to omit the ``b_trig`` arm, so `LandCore.step_courtyard` had NO cut at all: a
mid-roll B was ignored and the roll ran to its ordinary exit, which is why `clip_roll.fire` required a
Python-path run. Session 150 ported the whole arm -- the b_trig exit, `_cut_init`, `_proc_cut`, and the
ANM_CUT joint-0 root translate (`m3700`) that IS the thrust's 23.22 u lunge.

Three layers, cheapest first, because a leaf that is right makes a frame diff readable:

  * `CutAnimData.m3700_at` == `_CutMixin._cut_m3700_at` over every frame the ctrl can reach;
  * the CLIP ROLL fired through `clip_roll.fire` on both engines, row for row (proc, facing, speedF,
    both actors' positions) -- walled and unwalled;
  * and the cases the C core does NOT model raise instead of mis-stepping.

Per `[[zero-ulp-tests-only]]` every float is compared as `_bits`. Nothing here searches: the roll's
input stream is `clip_roll.clip_stream`, and the state it fires from is a banked herd log.
"""
import json
import os
import struct
import warnings

import pytest

from harness.tetrapush import clip_roll as CR
from harness.tetrapush import seeds as SD
from tww_sim.land.constants import CUT_A, CUT_F

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LADDER = os.path.join(_REPO, 'fixtures', 'courtyard_candidate_ladder.json')


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', float(v)))[0]


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


@pytest.fixture(scope='module')
def herd_log():
    with open(LADDER) as fh:
        return next(c for c in json.load(fh)['candidates'] if c['rank'] == 5)['log']


def _at_herd_end(env, log, native, walls=False):
    run = SD.make_freerun(env, native=native, walls=walls)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in log:
            run.step(d)
    return run


def test_native_m3700_is_the_python_keyframe_eval(env):
    """The root-translate track, frame for frame: the lunge is a J3D keyframe eval and the C copy has
    to agree on every frame the CUT ctrl can land on (CUT_START..CUT_END at CUT_RATE, plus the
    sub-steps a clamp can produce)."""
    from harness.tetrapush.from_f0 import _cut_anim_core
    from tww_sim.land.state import LandState
    core = _cut_anim_core()
    ref = LandState(use_anim=False, native=False)
    n = 0
    for ct in (CUT_F, CUT_A):
        f = LandState.CUT_START
        while f < LandState.CUT_END:
            got = core.m3700_at(ct, f)
            want = ref._cut_m3700_at(ct, f)
            for ax in range(3):
                assert _bits(got[ax]) == _bits(want[ax]), (
                    'cut %#x frame %r axis %d: native %r vs python %r' % (ct, f, ax, got[ax], want[ax]))
            n += 1
            f = round(f + 0.1, 4)
    assert n >= 250, 'only %d frames sampled' % n
    # the lunge is real, not a zero track: joint 0 must actually translate across the thrust
    a = core.m3700_at(CUT_F, LandState.CUT_START)
    b = core.m3700_at(CUT_F, 12.0)
    assert abs(b[2] - a[2]) > 5.0, 'the CUT_F root translate should carry Link forward: %r %r' % (a, b)


#: What a clip-roll row exposes, all of it. `test_freerun_native`'s lesson: a field nobody listed is
#: a field a bug hides in, and the cut writes proc/facing/speedF/pos on top of the coupled push.
def _rows_match(a, b):
    bad = []
    for i, (ra, rb) in enumerate(zip(a, b)):
        for key in ('frame', 'proc', 'facing'):
            if ra[key] != rb[key]:
                bad.append('row %d %s: %r vs %r' % (i, key, ra[key], rb[key]))
        if _bits(ra['speedF']) != _bits(rb['speedF']):
            bad.append('row %d speedF: %r vs %r' % (i, ra['speedF'], rb['speedF']))
        for key in ('pos', 'tetra'):
            for ax in (0, 1):
                if _bits(ra[key][ax]) != _bits(rb[key][ax]):
                    bad.append('row %d %s[%d]: %r vs %r (%d ULP)'
                               % (i, key, ax, ra[key][ax], rb[key][ax],
                                  _bits(rb[key][ax]) - _bits(ra[key][ax])))
    assert len(a) == len(b), 'row counts differ: %d vs %d' % (len(a), len(b))
    return bad


@pytest.mark.parametrize('walls', [False, True], ids=['unwalled', 'walled'])
@pytest.mark.parametrize('cut_step', [15, 17])
def test_the_clip_roll_fires_identically_on_both_engines(env, herd_log, walls, cut_step):
    """`clip_roll.fire` on the native step == on the Python step, row for row.

    ``cut_step`` spans `entry_search.cut_step_window`'s admissible range, so both the earliest and the
    latest deliverable thrust are covered rather than one arbitrary one."""
    py = _at_herd_end(env, herd_log, native=False, walls=walls)
    nat = _at_herd_end(env, herd_log, native=True, walls=walls)
    aim = CR.aim_bytes_for(py.link.facing, py.csangle)['bytes']
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        rp = CR.fire(py, aim, cut_step)
        rn = CR.fire(nat, aim, cut_step)
    assert rp['ok'], 'the Python reference never cut -- the bed is wrong, not the port: %r' % rp
    assert rn['ok'] is rp['ok']
    assert rn['cut_type'] == rp['cut_type'] == CUT_F
    assert (rn['entry_frame'], rn['cut_frame'], rn['frames']) == \
           (rp['entry_frame'], rp['cut_frame'], rp['frames'])
    assert rp['frames'] == CR.roll_frames(cut_step), (
        'the roll should cost cut_step + 2 frames: %r' % rp['frames'])
    bad = _rows_match(rp['rows'], rn['rows'])
    assert not bad, '\n'.join(bad[:10])


@pytest.mark.parametrize('native', [True, False], ids=['native', 'python'])
def test_the_cut_frame_is_speedf_plus_the_root_translate(env, herd_log, native):
    """The lunge, RECONSTRUCTED from first principles on the dispatch frame, 0 ULP.

    ``pos = ((pre + speedF*dir(travel)) + the CC recoil) + rotate(m3700, shape_angle.y)`` with
    m3700_prev == 0 (procCut*_init zeroes it), which is why the entry frame stacks the WHOLE root
    translate. Asserting this rather than "the step is big" is what distinguishes a real cut from a
    roll frame that happens to move: without the ported arm the C step ignored the B entirely, and an
    engine-vs-engine diff would have passed by being equally wrong on both sides.

    Run on BOTH engines, so the reconstruction is a statement about the model and not about C."""
    from tww_sim.core import mathlib as S
    from tww_sim.core.fp import f32
    from tww_sim.land.constants import _cM_ssin_s16
    from tww_sim.land.state import LandState
    from harness.tetrapush.from_f0 import _cut_anim_core
    run = _at_herd_end(env, herd_log, native=native)
    aim = CR.aim_bytes_for(run.link.facing, run.csangle)['bytes']
    stream = CR.clip_stream(aim, 15)
    acted = CR.b_index(15) + 1          # input_delay=1: the B fires the frame AFTER it is polled
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for k, d in enumerate(stream):
            if k == acted:
                pre = (run.link.pos_x, run.link.pos_z)
                pend = run.pend_link
                travel = run.link.travel
                assert run.link.state == 30, 'the B must land mid-ROLL to dispatch a cut'
            run.step(d)
            if k == acted:
                break
    assert run.link.state == CUT_F, 'the mid-roll B must dispatch CUT_F, got proc %r' % run.link.state
    m3700 = _cut_anim_core().m3700_at(CUT_F, LandState.CUT_START)
    s, c = _cM_ssin_s16(run.link.facing), S.cM_scos_s16(run.link.facing)
    add_x = f32(f32(m3700[2] * s) + f32(m3700[0] * c))
    add_z = f32(f32(m3700[2] * c) - f32(m3700[0] * s))
    sf = run.link.speedF
    want_x = f32(f32(f32(pre[0] + f32(sf * _cM_ssin_s16(travel))) + pend[0]) + add_x)
    want_z = f32(f32(f32(pre[1] + f32(sf * S.cM_scos_s16(travel))) + pend[1]) + add_z)
    assert _bits(run.link.pos_x) == _bits(want_x), (
        'cut-frame x: got %r, foot+lunge says %r' % (run.link.pos_x, want_x))
    assert _bits(run.link.pos_z) == _bits(want_z), (
        'cut-frame z: got %r, foot+lunge says %r' % (run.link.pos_z, want_z))
    assert (add_x ** 2 + add_z ** 2) ** 0.5 > 20.0, (
        'the ANM_CUT root translate is the thrust; a near-zero one means the track was not read: %r'
        % ((add_x, add_z),))


def test_a_neutral_b_out_of_a_roll_is_the_side_slash_not_the_thrust(env, herd_log):
    """`_roll_exit`'s aim: pushed + unlocked takes the stick target, otherwise shape_angle.y. Both
    engines must pick the same one, since it is what rotates the whole cut tail."""
    py = _at_herd_end(env, herd_log, native=False)
    nat = _at_herd_end(env, herd_log, native=True)
    aim = CR.aim_bytes_for(py.link.facing, py.csangle)['bytes']
    kw = dict(hold=1, a_hold=2, tail=2)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        rp = CR.fire(py, aim, 15, **kw)
        rn = CR.fire(nat, aim, 15, **kw)
    assert py.link.cut_target == nat.link.cut_target
    assert not _rows_match(rp['rows'], rn['rows'])


def test_the_native_step_refuses_what_it_cannot_model(env, herd_log):
    """A roll BONK and a sidle-preempted A press are unported; `wall_check` must RAISE on either.

    A flag that only a caller might notice is the defect this whole session removed, so the refusal
    is gated directly on the core rather than inferred from a run that happened not to hit it."""
    nat = _at_herd_end(env, herd_log, native=True, walls=True)
    core = nat._core
    core.wall_check()                          # clean -> silent
    core.bonk_unmodelled = True
    with pytest.raises(RuntimeError) as ei:
        core.wall_check()
    assert 'procFrontRollCrash' in str(ei.value)
    core.bonk_unmodelled = False
    core.sidle_unmodelled = True
    with pytest.raises(RuntimeError) as ei:
        core.wall_check()
    assert 'SIDLE' in str(ei.value)
    core.sidle_unmodelled = False
    core.wall_check()


def test_a_cloned_native_run_cuts_bit_identically(env, herd_log):
    """The beam branches by `clone()`; the cut state (ctrl frame, latched aim, the m3700 store) has to
    come with it or a branched thrust lunges off the parent's previous frame."""
    nat = _at_herd_end(env, herd_log, native=True, walls=True)
    aim = CR.aim_bytes_for(nat.link.facing, nat.csangle)['bytes']
    stream = CR.clip_stream(aim, 15)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in stream[:14]:                  # mid-roll, before the B
            nat.step(d)
        child = nat.clone()
        for d in stream[14:]:
            nat.step(d)
            child.step(d)
    assert nat.link.state == child.link.state == CUT_F
    for name in ('pos_x', 'pos_z', 'speedF', 'nspeed', 'cut_frame'):
        a, b = getattr(nat.link, name), getattr(child.link, name)
        assert _bits(a) == _bits(b), '%s: parent %r vs clone %r' % (name, a, b)
    assert _bits(nat.tx) == _bits(child.tx) and _bits(nat.tz) == _bits(child.tz)
    assert nat.link.cut_target == child.link.cut_target
