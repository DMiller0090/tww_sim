"""**Link's head-top, exported from the C engine** -- 0-ULP against the Python FK (session 127).

Why this one number gets its own gate: it is the whole reason a coupled courtyard rollout could not
run in C. The native step reproduces the wired one bit-for-bit when csangle and the proc-9 re-aim eye
are injected (measured over whole banked node logs), csangle is free -- it is a per-node constant
across an aim fan -- but the eye is Tetra's, and her `Zl1Look` reads exactly one non-positional thing
from Link: his exec-pass ``mHeadTopPos.y``, which needed his pose FK, the most expensive part of the
Python step. `PoseEngine._head_top` / `LandCore.head_top_exec` close that, and joint 15 was already
being posed with the body-Co extras, so it costs one matrix concat and no extra pose work.

Two gates, because they can fail separately:
  * the module-level `head_top` against `foot_fk.FootFK.head_top` on real posed frames, untwisted and
    with a real neck twist (the twist is applied as TWO quat concats, each skipped when its terms are
    zero -- not the same matrix as one combined rotation, which is exactly the kind of thing a port
    gets wrong and a position-only check misses);
  * `LandCore.head_top_exec` against `from_f0._computed_head_top` frame by frame over a real coupled
    run, which is the call the eye chain will actually make -- including its base/lean conventions
    (zero base lean on a proc-``*_init`` frame) that the standalone comparison cannot reach.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import seeds as SD                        # noqa: E402
from harness.tetrapush import from_f0 as F0                      # noqa: E402
from tww_sim.core.anim import foot_fk as FK                      # noqa: E402

_anmc = pytest.importorskip('tww_sim.core.anim._anmc',
                            reason='native accelerator not built')

#: How many frames of the recorded window to check. The window carries both roll bodies, the proc-9
#: untarget tier and the MOVE backslide -- i.e. every pose regime the herd search rolls through.
UPTO = 40

#: A neck twist with all three terms non-zero, so BOTH quat concats of the jointBeforeCB adjust run.
NECK_TWIST = (0x0400, -0x0180, 0x00C0)


def _wired_run():
    env = SD.load_env()
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    return env, run


def test_the_native_head_top_is_the_python_one(recwarn):
    """The module-level call against `FootFK.head_top`, on the pose of every stepped frame."""
    env, run = _wired_run()
    at = SD.dtm_input_at(env)
    ff = run.link._foot.ff
    checked = 0
    for k in range(1, UPTO):
        run.step(at(k))
        link = run.link
        lean = link._draw_lean
        body_lean = F0._s16(link.m351C) >> 1
        for neck in (None, NECK_TWIST):
            want = ff.head_top(link.pos_x, link.pos_y, link.pos_z, link.facing,
                               lean=lean, body_lean=body_lean, neck=neck)
            lv = int(body_lean) & 0xFFFF
            body_x = -(lv - 0x10000 if lv >= 0x8000 else lv)
            got = _anmc.head_top(link.pos_x, link.pos_y, link.pos_z, link.facing,
                                 int(lean) & 0xFFFF, body_x,
                                 [ff.old_quat[j] for j in FK.HEAD_CHAIN],
                                 [ff.old_trans[j] for j in FK.HEAD_CHAIN],
                                 [ff.old_scale[j] for j in FK.HEAD_CHAIN], neck)
            assert tuple(got) == tuple(want), 'frame %d neck=%s: %r != %r' % (k, neck, got, want)
            checked += 1
    assert checked == 2 * (UPTO - 1)


def test_the_neck_twist_actually_moves_it(recwarn):
    """The twist is a real term, not a no-op the equality above would pass either way."""
    env, run = _wired_run()
    at = SD.dtm_input_at(env)
    for k in range(1, 6):
        run.step(at(k))
    link = run.link
    ff = link._foot.ff
    body_lean = F0._s16(link.m351C) >> 1
    plain = ff.head_top(link.pos_x, link.pos_y, link.pos_z, link.facing,
                        lean=link._draw_lean, body_lean=body_lean, neck=None)
    twisted = ff.head_top(link.pos_x, link.pos_y, link.pos_z, link.facing,
                          lean=link._draw_lean, body_lean=body_lean, neck=NECK_TWIST)
    assert plain != twisted


def test_the_core_exec_head_top_is_the_wired_one(recwarn):
    """**The call the eye chain makes.** A native `FreeRun` and a wired one over the same inputs, with
    csangle and eye injected into the native side (the configuration measured 0-ULP), and the core's
    `head_top_exec` compared to the wired `_computed_head_top` every frame -- untwisted and twisted.

    This is the one that covers the exec-pass conventions: the base takes the DRAW lean, zeroed on a
    proc-``*_init`` frame, and the BODY_CHN twist takes the post-update lean. The init flag is tracked
    HERE, independently (`FreeRun.step` consumes its own and advances `prev_disp`), and asserted
    against the core's -- so the gate pins the flag as well as the value it selects. Getting that
    backwards is not academic: the two conventions differ by 1.4 u in x and 3.4 in z on the very first
    frame, which is 100x the razor's whole acceptance band."""
    env, wired = _wired_run()
    at = SD.dtm_input_at(env)
    nat = SD.make_freerun_native(env)
    nat.pre_seed_input(at(0))
    cs, eye = None, None
    prev = wired.link.state
    seen_init = 0
    for k in range(1, UPTO):
        wired.step(at(k))
        nat.step(at(k), csangle=cs, eye=eye)
        cs, eye = int(wired.csangle), tuple(wired._eye_next)
        init = wired.link.state != prev
        prev = wired.link.state
        seen_init += int(init)
        # the physics must still be the same run, or the pose comparison below is meaningless
        assert (nat.link.pos_x, nat.link.pos_z, int(nat.link.facing), nat.link.state) == \
               (wired.link.pos_x, wired.link.pos_z, int(wired.link.facing), wired.link.state), \
               'native/wired physics diverged at frame %d' % k
        assert bool(nat._core._init_frame) == init, 'proc-init flag differs at frame %d' % k
        for neck in (None, NECK_TWIST):
            want = F0._computed_head_top(wired.link, init_frame=init, neck=neck)
            got = nat._core.head_top_exec(neck)
            assert tuple(got) == tuple(want), 'frame %d neck=%s: %r != %r' % (k, neck, got, want)
            # the MATRIX too: `NeckLook.update` measures the cached previous-frame value of it, so
            # the eye chain needs both and a head_top that agreed by luck would be caught here
            wm = F0._computed_head_mtx(wired.link, init_frame=init, neck=neck)
            gm = nat._core.head_mtx_exec(neck)
            assert [list(r) for r in gm] == [list(r) for r in wm], \
                'frame %d neck=%s head MATRIX: %r != %r' % (k, neck, gm, wm)
    assert seen_init > 0, 'no proc-init frame in the window -- the zero-lean branch went untested'


def test_the_two_lean_conventions_are_distinguishable(recwarn):
    """The proc-init zero-lean rule is a real branch, so a gate that selected the wrong one would be
    caught -- pinned on the frame where the two differ most in the window."""
    env, wired = _wired_run()
    at = SD.dtm_input_at(env)
    worst = 0.0
    prev = wired.link.state
    for k in range(1, UPTO):
        wired.step(at(k))
        if wired.link.state == prev:
            prev = wired.link.state
            continue
        prev = wired.link.state
        a = F0._computed_head_top(wired.link, init_frame=False, neck=None)
        b = F0._computed_head_top(wired.link, init_frame=True, neck=None)
        worst = max(worst, max(abs(x - y) for x, y in zip(a, b)))
    assert worst > 1.0, 'the two lean conventions agree to %.3g u -- the branch is untestable' % worst
