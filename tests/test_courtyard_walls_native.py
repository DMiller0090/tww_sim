"""The WALLED courtyard step in C == the walled Python step, 0 ULP -- and it lands on the CONSOLE pin.

Session 150 ported both actors' `dBgS_Acch::CrrPos` into `LandCore.step_courtyard`, which is what the
terminal phase needs: the clip happens with Tetra wedged in the corner, and a braced Tetra HOLDS
instead of recoiling out of the push. Before the port the phase had to be stepped in Python at ~730
clone+steps/s against the native ~9400 -- a 13x tax on the search that matters most -- and assigning
the mesh to a native run was a silent no-op (`seeds.wall_for_terminal` refused it for that reason).

What is gated here, in the order that makes the answer trustworthy:

  * the walled NATIVE run is the walled PYTHON run bit-for-bit, both actors, frame by frame;
  * turning the port on did not move the UNWALLED native run by a bit (it is the reference every
    other native gate is built on);
  * and the braced Tetra lands on the value the CONSOLE locked -- read out of
    `fixtures/courtyard_clip_s86_console.json`, never restated here.

The rollout is a banked log (`fixtures/courtyard_candidate_ladder.json` rung 5) replayed, then neutral
input: no search runs at test time.
"""
import json
import os
import struct
import warnings

import pytest

from harness.tetrapush import seeds as SD

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLE = os.path.join(_REPO, 'fixtures', 'courtyard_clip_s86_console.json')
LADDER = os.path.join(_REPO, 'fixtures', 'courtyard_candidate_ladder.json')
NEUTRAL = dict(stickX=128, stickY=128, buttons=0, triggerL=0, substickX=128, substickY=0)


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', float(v)))[0]


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


@pytest.fixture(scope='module')
def herd_log():
    with open(LADDER) as fh:
        return next(c for c in json.load(fh)['candidates'] if c['rank'] == 5)['log']


def _at_herd_end(env, log, native, walls):
    run = SD.make_freerun(env, native=native, walls=walls)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in log:
            run.step(d)
    return run


#: Every field of the coupled state a caller can SEE -- exhaustive, because a field nobody listed
#: hides a bug for sessions, and four of these are ones only the wall pass writes.
_FLOATS = ('pos_x', 'pos_z', 'speedF', 'nspeed')
_EXACT = ('state', 'facing', 'travel', 'm351C', '_draw_lean',
          'wall_hit', 'line_hit', 'wall_cir_hit', 'wall_angle')


def _assert_same(py, nat, k):
    for name in _FLOATS:
        a, b = getattr(py.link, name), getattr(nat.link, name)
        assert _bits(a) == _bits(b), ('f%d %s: python %r vs native %r (%d ULP)'
                                      % (k, name, a, b, _bits(b) - _bits(a)))
    for name in _EXACT:
        a, b = getattr(py.link, name), getattr(nat.link, name)
        if isinstance(a, (list, tuple)):
            a, b = tuple(a), tuple(b)
        assert a == b, 'f%d %s: python %r vs native %r' % (k, name, a, b)
    assert _bits(py.tx) == _bits(nat.tx), 'f%d Tetra x: %r vs %r' % (k, py.tx, nat.tx)
    assert _bits(py.tz) == _bits(nat.tz), 'f%d Tetra z: %r vs %r' % (k, py.tz, nat.tz)


@pytest.mark.parametrize('walls', [False, True], ids=['unwalled', 'walled'])
def test_native_courtyard_step_matches_python(env, herd_log, walls):
    """Herd end + 24 neutral frames (which is where her handover carries her into the wall).

    The `unwalled` arm is the regression half: the port added branches to the hot frame, and none of
    them may move a run that has no mesh."""
    py = _at_herd_end(env, herd_log, native=False, walls=walls)
    nat = _at_herd_end(env, herd_log, native=True, walls=walls)
    _assert_same(py, nat, 0)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for k in range(1, 25):
            py.step(NEUTRAL)
            nat.step(NEUTRAL)
            _assert_same(py, nat, k)


def test_the_native_brace_lands_on_the_console_locked_pin(env, herd_log):
    """Walled and NATIVE, she pins at the wall plane plus her radius -- the console-locked value.

    The Python twin of this is `test_tetra_walls.py`; what this adds is that the C engine reaches the
    same pin, which is the only reason the terminal phase is allowed to run on it."""
    with open(CONSOLE) as fh:
        con = json.load(fh)
    pin = next(s['tetra']['z'] for s in con['samples']
               if abs(s['tetra']['z'] - con['tetra_wall']['brace_z']) < 1e-3)
    nat = _at_herd_end(env, herd_log, native=True, walls=True)
    unw = _at_herd_end(env, herd_log, native=True, walls=False)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for _ in range(9):                      # her own handover carries her into the wall
            nat.step(NEUTRAL)
            unw.step(NEUTRAL)
    assert _bits(nat.tz) == _bits(pin), (
        'native walled Tetra should pin at the console-locked %r, got %r' % (pin, nat.tz))
    assert unw.tz < pin, (
        'native unwalled Tetra should pass THROUGH the plane (that is the defect the port removes), '
        'got %r' % unw.tz)


def test_a_braced_tetra_holds_where_an_unwalled_one_keeps_going(env, herd_log):
    """BRACING is the mechanic, not merely "a different number": at the plane the wall cancels the
    normal component of her CC recoil, so she stops being carried away from Link and becomes a nearly
    FIXED target -- which is what a 1e-4 u razor wants. She still slides ~1-2 u/frame along the plane
    (the tangential half survives), so what is gated is the collapse, measured against the unwalled
    run stepped on the same inputs rather than against a hand-picked threshold."""
    nat = _at_herd_end(env, herd_log, native=True, walls=True)
    unw = _at_herd_end(env, herd_log, native=True, walls=False)
    walled, free = [], []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for _ in range(12):
            nat.step(NEUTRAL)
            unw.step(NEUTRAL)
            walled.append(nat.tz)
            free.append(unw.tz)
    assert [_bits(v) for v in walled[:3]] == [_bits(v) for v in free[:3]], (
        'while she is clear of the geometry the pass is a strict no-op: %r vs %r'
        % (walled[:3], free[:3]))
    # PINNING, as the console fixture defines it: ONE value held over consecutive frames.
    tail = walled[-6:]
    assert [_bits(v) for v in tail] == [_bits(tail[0])] * len(tail), (
        'braced, her wall-normal coordinate must HOLD frame after frame: %r' % (walled,))
    assert min(free) < min(walled) - 20.0, (
        'the unwalled run must keep being carried past the plane -- that is what bracing prevents: '
        '%r vs %r' % (walled, free))


def test_the_fleet_stays_bit_identical_with_walls_wired(env, herd_log):
    """`CourtyardFleet.run_par` fans `step_courtyard` across OpenMP threads, and the wall pass reads a
    mesh SHARED by every core -- so the parallel run must still equal the sequential one exactly."""
    from tww_sim.core.anim import _anmc as N
    base = _at_herd_end(env, herd_log, native=True, walls=True)
    sched = [(128, 128, 0, 0, int(base.csangle) & 0xFFFF)] * 12
    outs = []
    for parallel in (False, True):
        cores = [base._core.clone(base._core.pe.clone_state()) for _ in range(6)]
        fleet = N.CourtyardFleet(cores, 1)
        fleet.set_schedule([list(sched) for _ in cores])
        (fleet.run_par if parallel else fleet.run_seq)(len(sched))
        outs.append([(c.pos_x, c.pos_z, c._tetra_x, c._tetra_z) for c in cores])
    for i, (a, b) in enumerate(zip(*outs)):
        assert [_bits(v) for v in a] == [_bits(v) for v in b], 'core %d: seq %r vs par %r' % (i, a, b)
    assert outs[0][0] != (0.0, 0.0, 0.0, 0.0)
