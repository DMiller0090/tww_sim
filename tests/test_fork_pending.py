"""`FreeRun.fork_pending` -- one frame, N children -- against the clone-and-step it replaces.

The whole value of the primitive is that it is EXACT and not an approximation, so every gate here
compares it field by field against the loop it stands in for, `==` and never a tolerance
(`[[zero-ulp-tests-only]]`). The claim it rests on is structural: at `input_delay=1` the delivered
input is written to the delay buffer and nothing in the frame reads it (in `_anmc`'s
`_step_courtyard_nogil` the incoming stick/buttons/trigger appear only in the signature and the
`_cbuf` write), so the frame is a function of the state alone.

That is exactly why the gates below step the children AGAIN afterwards: a fork that got the frame
right but the pending input wrong would be bit-identical on the fork frame and wrong on the next
one, which is the failure this primitive could actually have.
"""
import pytest

from harness.tetrapush import full_herd as F
from harness.tetrapush import search as S
from harness.tetrapush import seeds as SD
from harness.tetrapush import two_roll as T
from harness.tetrapush.reposition import HerdLine


def _state(r):
    """Every field the search reads off a run, raw -- floats compared with `==`."""
    return (r.link.pos_x, r.link.pos_z, int(r.link.facing), int(r.link.travel),
            r.link.speedF, int(r.link.state), r.tx, r.tz, int(r.csangle),
            bool(r._follow_warned), r.pend_link, r.pend_tetra, r.prev_disp)


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


@pytest.fixture(scope='module')
def seeded(env):
    """A native run walked a few frames off the state-2 seed -- a real mid-search state."""
    run = SD.make_freerun(env, native=True)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for k in range(1, 12):
        run.step(SD.dtm_input_at(env)(k))
    return run


def _alphabet(run, env, n=24):
    hl = HerdLine.from_env(env)
    letters = []
    for (sx, sy) in F.junction_alphabet(run, hl, ess_step=1, aim_step=16):
        for l in (0, 1):
            letters.append(dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                                triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL,
                                substickY=0))
    return letters[:n]


def test_fork_is_clone_and_step_bit_for_bit(seeded, env):
    letters = _alphabet(seeded, env)
    forked = seeded.fork_pending(letters)
    assert len(forked) == len(letters)
    for d, got in zip(letters, forked):
        want = seeded.clone()
        want.step(dict(d), record=False)
        assert _state(got) == _state(want)


def test_the_pending_input_survives_the_fork(seeded, env):
    """The fork's real failure mode: a shared frame with the WRONG letter pending is bit-identical
    now and wrong on the next frame, which is the only frame the letter was ever going to move."""
    letters = _alphabet(seeded, env)
    forked = seeded.fork_pending(letters)
    nxt = dict(stickX=128, stickY=128, buttons=0, triggerL=0,
               substickX=T.CSTICK_NEUTRAL, substickY=0)
    for d, got in zip(letters, forked):
        want = seeded.clone()
        want.step(dict(d), record=False)
        want.step(dict(nxt), record=False)
        got.step(dict(nxt), record=False)
        assert _state(got) == _state(want)


def test_the_children_are_not_all_the_same_run(seeded, env):
    """Non-vacuity: the letters must actually tell the children apart one frame later, else the
    gate above would pass on a fork that handed every child the same input (s130's lesson -- count
    a green comparison's distinctness before believing it)."""
    letters = _alphabet(seeded, env)
    forked = seeded.fork_pending(letters)
    assert len(set(_state(r) for r in forked)) == 1          # the frame IS shared
    nxt = dict(stickX=128, stickY=128, buttons=0, triggerL=0,
               substickX=T.CSTICK_NEUTRAL, substickY=0)
    for r in forked:
        r.step(dict(nxt), record=False)
    assert len(set(_state(r) for r in forked)) > 1           # ...and the letters separate them


def test_a_wired_run_refuses(env):
    """The wired step's delay buffer is `LandState`'s, so the primitive says so rather than
    quietly writing half of it."""
    run = SD.make_freerun(env, native=False)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    with pytest.raises(ValueError):
        run.fork_pending([dict(stickX=128, stickY=128, buttons=0, triggerL=0)])


def test_empty_forks_to_nothing(seeded):
    assert seeded.fork_pending([]) == []


def test_set_pending_input_matches_a_fresh_pre_seed(env):
    """`set_pending_input` is `pre_seed_input` mid-run: the two must leave a run in the same state,
    or the fork's children would be seeded differently from a run built the normal way."""
    d = dict(stickX=200, stickY=64, buttons=S.PAD_L, triggerL=255)
    a = SD.make_freerun(env, native=True)
    a.pre_seed_input(d)
    b = SD.make_freerun(env, native=True)
    b.pre_seed_input(dict(stickX=128, stickY=128, buttons=0, triggerL=0))
    b.set_pending_input(d)
    nxt = dict(stickX=128, stickY=128, buttons=0, triggerL=0)
    for _ in range(3):
        a.step(dict(nxt), record=False)
        b.step(dict(nxt), record=False)
    assert _state(a) == _state(b)
