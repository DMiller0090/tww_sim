"""**The coupled courtyard rollout, running in C** (session 127) -- 0-ULP against the wired engine.

The search's forward model was the wired Python `FreeRun` at 2431 steps/s while the same frame runs
in C at 106294, and the reason was one number: Tetra's proc-9 re-aim eye. `_step_native` was already
the wired physics when csangle AND the eye were injected, but the eye is her `Zl1Look` output, which
needs Link's exec-pass mHeadTopPos.y, which needed his Python pose FK -- so nothing could be skipped.
Falling back to her feet is not an option: it moves the re-aim 180 BAM and a banked node log 123 u.

`LandCore.head_top_exec` / `head_mtx_exec` (gated in `test_native_head_top.py`) hand the neck and her
look model those pose values straight out of the C engine, so `make_freerun_self_eye` runs the whole
coupled frame natively and generates its own eye. This gate is the claim: it is the wired run, on
Link, on Tetra, on the eye and on the neck's m3564, over the recorded window -- `==`, never a
tolerance (`[[zero-ulp-tests-only]]`).

csangle stays injected, deliberately. Through a roll it is a per-node constant across a whole aim fan
(measured, `tests/test_roll_kernel.py`), so a fan pays for one camera; everywhere else it is the
caller's to supply.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import seeds as SD                        # noqa: E402

pytest.importorskip('tww_sim.core.anim._anmc', reason='native accelerator not built')

#: The whole recorded window (both roll bodies, the untarget proc-9 tier, the MOVE backslide).
UPTO = 45


def _pair():
    env = SD.load_env()
    at = SD.dtm_input_at(env)
    wired = SD.make_freerun(env)
    wired.pre_seed_input(at(0))
    fast = SD.make_freerun_self_eye(env)
    fast.pre_seed_input(at(0))
    return env, at, wired, fast


def _state(run):
    return (run.link.pos_x, run.link.pos_z, int(run.link.facing), int(run.link.travel),
            run.link.speedF, int(run.link.state), run.tx, run.tz)


def test_the_self_eye_run_is_the_wired_run(recwarn):
    """Frame by frame over the recorded window: physics, the eye, and the neck."""
    env, at, wired, fast = _pair()
    cs = None
    for k in range(1, UPTO):
        wired.step(at(k))
        fast.step(at(k), csangle=cs)
        cs = int(wired.csangle)                  # the camera is the caller's; everything else is C
        assert _state(fast) == _state(wired), 'physics diverged at frame %d' % k
        assert tuple(fast._eye_next) == tuple(wired._eye_next), 'eye diverged at frame %d' % k
        assert (fast.neck.x, fast.neck.y, fast.neck.z) == \
               (wired.neck.x, wired.neck.y, wired.neck.z), 'm3564 diverged at frame %d' % k


def test_the_eye_is_generated_not_injected(recwarn):
    """The mode's whole point: with her look model wired the eye is computed inside the step, and an
    injected one is refused rather than silently ignored."""
    env, at, _wired, fast = _pair()
    with pytest.raises(ValueError):
        fast.step(at(1), eye=(0.0, 0.0, 0.0))


def test_the_feet_fallback_would_not_have_done(recwarn):
    """Why the eye chain is worth its cost, pinned as a number rather than asserted: the stripped
    native run (no zl1 -- the eye falls back to her feet) leaves the wired trajectory inside this
    window. If this ever stops diverging, the eye stopped mattering and the chain is dead weight."""
    env, at, wired, fast = _pair()
    stripped = SD.make_freerun_native(env)
    stripped.pre_seed_input(at(0))
    cs = None
    diverged = None
    for k in range(1, UPTO):
        wired.step(at(k))
        stripped.step(at(k), csangle=cs)
        cs = int(wired.csangle)
        if diverged is None and _state(stripped) != _state(wired):
            diverged = k
    assert diverged is not None, 'the feet fallback matched the wired run -- the eye is inert here'


def test_a_clone_of_a_self_eye_run_is_the_run(recwarn):
    """The roll fan branches ONE node into a whole aim fan by cloning, so the clone owes bit-identity
    on all three pieces -- the C core, her look model, and the neck (each clones separately)."""
    env, at, _wired, fast = _pair()
    cs = 39000
    for k in range(1, 12):
        fast.step(at(k), csangle=cs)
    twin = fast.clone()
    for k in range(12, 24):
        fast.step(at(k), csangle=cs)
        twin.step(at(k), csangle=cs)
        assert _state(twin) == _state(fast), 'clone diverged at frame %d' % k
        assert tuple(twin._eye_next) == tuple(fast._eye_next)
        assert (twin.neck.x, twin.neck.y, twin.neck.z) == (fast.neck.x, fast.neck.y, fast.neck.z)
