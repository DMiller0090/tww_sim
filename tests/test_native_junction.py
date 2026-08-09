"""The junction stage's session-133 cuts, each gated against the path it replaces.

The junction is **98% of a chained cycle** once the roll stage is native (measured: a cycle off one
banked cycle-2 parent is 20.0 s of `junction_beam` against 0.4 s of `roll_candidates`), so all three
cuts here land on the same stage:

  * `beam_io.rebuild_beam(native=)` -- the nodes a banked beam is re-opened as. Wired 411 us a
    step, native 120.
  * `full_herd._expand` / `FreeRun.fork_pending` -- one frame per NODE per generation instead of one
    per child.
  * `two_roll.junction_gates`' arming probe -- stepped with the camera detached, since a probe has
    no next frame to read the csangle it would commit.

Every gate compares against the slow path field for field, `==` and never a tolerance
(`[[zero-ulp-tests-only]]`), and the counts are asserted beside the equality: a fast path that
silently fell back to the reference would pass an equality gate by being it (s130).
"""
import os

import pytest

from harness.tetrapush import beam_io as BIO
from harness.tetrapush import full_herd as F
from harness.tetrapush import search as S
from harness.tetrapush import seeds as SD
from harness.tetrapush import two_roll as T
from harness.tetrapush.from_f0 import FreeRun
from harness.tetrapush.reposition import HerdLine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEAM = os.path.join(_ROOT, '_generated', 's106', 's107_rechain_c2_beam.json')

# The cheapest NON-VACUOUS cut off this parent (6 endpoints, ~0.3 s). It must be FIVE generations --
# the arming pattern needs L two junction frames back, so 2-4 return an EMPTY beam every gate passes.
JN = dict(max_frames=5, beam=4, ess_step=1, aim_step=64, keep=6, per_state=4, aim_share=True)

pytestmark = pytest.mark.skipif(not os.path.exists(BEAM), reason='banked cycle-2 beam not present')


def _slow_expand(run, letters):
    out = []
    for d in letters:
        r = run.clone()
        r.step(d)
        out.append(r)
    return out


def _key(ends):
    return [(e['jf'], e['frames'], e['run'].link.pos_x, e['run'].link.pos_z,
             int(e['run'].link.facing), int(e['run'].link.travel), e['run'].link.speedF,
             int(e['run'].link.state), e['run'].tx, e['run'].tz, int(e['run'].csangle),
             tuple(sorted(e['m'].items())),
             tuple(sorted(d.items()) for d in e['log'][-e['jf']:]))
            for e in ends]


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


@pytest.fixture(scope='module')
def rec():
    return BIO.load_beams(BEAM)


def _node(env, rec, native):
    hl = HerdLine.from_env(env)
    nd = rec['cycles'][-1][0]
    run = SD.make_freerun(env, native=native)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for d in nd['log']:
        run.step(d)
    return dict(run=run, log=list(nd['log']), frames=nd['frames'],
                m=T.metrics(run, hl, nd['frames']))


def _beam(env, node, expand=None):
    hl = HerdLine.from_env(env)
    box = F.pursuit_box(env, hl)
    real = F._expand
    if expand is not None:
        F._expand = expand
    try:
        return F.junction_beam(node, hl, box, **JN)
    finally:
        F._expand = real


def test_a_rebuilt_node_is_the_same_node_on_either_engine(env, rec):
    """`rebuild_beam(native=True)` re-opens the banked beam on the C step. If the two engines
    disagreed at the node, every measurement taken downstream would be about a different state."""
    w = BIO.rebuild_beam(env, rec, native=False)
    n = BIO.rebuild_beam(env, rec, native=True)
    assert len(w) == len(n) > 0
    assert all(a['run'].native_step is False and b['run'].native_step is True
               for a, b in zip(w, n))
    for a, b in zip(w, n):
        assert (a['run'].link.pos_x, a['run'].link.pos_z, int(a['run'].link.facing),
                int(a['run'].link.travel), a['run'].link.speedF, int(a['run'].link.state),
                a['run'].tx, a['run'].tz, int(a['run'].csangle), sorted(a['m'].items())) \
            == (b['run'].link.pos_x, b['run'].link.pos_z, int(b['run'].link.facing),
                int(b['run'].link.travel), b['run'].link.speedF, int(b['run'].link.state),
                b['run'].tx, b['run'].tz, int(b['run'].csangle), sorted(b['m'].items()))


def test_the_shared_frame_returns_the_same_beam(env, rec):
    """The cut itself: `_expand` forks one frame per node where the loop stepped one per child."""
    fast = _beam(env, _node(env, rec, True))
    slow = _beam(env, _node(env, rec, True), expand=_slow_expand)
    assert len(fast) > 0
    assert _key(fast) == _key(slow)


def _count_steps(fn):
    n = [0]
    _step = FreeRun.step

    def counted(self, *a, **kw):
        n[0] += 1
        return _step(self, *a, **kw)

    FreeRun.step = counted
    try:
        fn()
    finally:
        FreeRun.step = _step
    return n[0]


def test_the_shared_frame_actually_shares(env, rec):
    """...and it is not the reference wearing its name. Counted, because an equality gate cannot
    tell a fast path from a fallback to the slow one -- the fallback IS the reference (s130)."""
    forked = _count_steps(lambda: _beam(env, _node(env, rec, True)))
    looped = _count_steps(lambda: _beam(env, _node(env, rec, True), expand=_slow_expand))
    assert 0 < forked < looped


def test_expand_on_a_wired_run_is_clone_and_step(env, rec):
    """The wired path is untouched: `_expand` clone-and-steps there, since the delay buffer belongs
    to `LandState`. Gated directly rather than through a beam -- a non-vacuous wired beam is 1.4 s
    of re-running a search stage, which is what `pytest -m slow` is for (below)."""
    node = _node(env, rec, False)
    hl = HerdLine.from_env(env)
    letters = [dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                    substickX=T.CSTICK_NEUTRAL, substickY=0)
               for (sx, sy) in list(F.junction_alphabet(node['run'], hl, ess_step=1,
                                                        aim_step=64))[:4]]
    got = F._expand(node['run'], letters)
    assert len(got) == len(letters) > 0
    for d, r in zip(letters, got):
        want = node['run'].clone()
        want.step(dict(d))
        assert (r.link.pos_x, r.link.pos_z, int(r.link.facing), int(r.link.travel),
                r.link.speedF, int(r.link.state), r.tx, r.tz, int(r.csangle)) \
            == (want.link.pos_x, want.link.pos_z, int(want.link.facing), int(want.link.travel),
                want.link.speedF, int(want.link.state), want.tx, want.tz, int(want.csangle))


def test_the_prune_verdict_is_the_nodes_and_not_the_childs(env, rec):
    """`junction_beam` decides `followed` / `wall` / `outbox` ONCE per node and drops a dead one
    without materialising a child. That is only sound because all three read the shared frame -- so
    gate exactly that: every child's verdict equals the one taken off the shared frame, on BOTH
    engines, over a real alphabet at several states."""
    hl = HerdLine.from_env(env)
    box = F.pursuit_box(env, hl)
    walls = F.O.courtyard_walls()

    def verdict(r):
        return ('followed' if r._follow_warned else
                'wall' if not F.O.frame_is_wall_free(r.link.pos_x, r.link.pos_z, r.tx, r.tz,
                                                     walls) else
                'outbox' if not F.in_pursuit_box(r, hl, box) else None)

    checked = 0
    for native in (True, False):
        node = _node(env, rec, native)
        run = node['run']
        for _gen in range(3):
            letters = [dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                            triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
                       for (sx, sy) in list(F.junction_alphabet(run, hl, ess_step=1,
                                                                aim_step=64))[:8]
                       for l in (0, 1)]
            want = verdict(F._shared_frame(run, letters[0]))
            kids = F._expand(run, letters)
            assert all(verdict(r) == want for r in kids)
            checked += len(kids)
            run = kids[0]
    assert checked > 40


@pytest.mark.slow
def test_a_wired_node_still_walks_the_same_beam(env, rec):
    """The whole-stage form of the gate above: a wired node's beam is the native one's, endpoint
    for endpoint. Marked slow -- it re-runs a search stage on the 411 us step."""
    assert _key(_beam(env, _node(env, rec, False))) == _key(_beam(env, _node(env, rec, True)))


def test_the_arming_probe_is_camera_free_and_says_the_same_thing(env, rec):
    """`junction_gates`' probe reads one field of one frame, so it steps with the camera detached
    and this frame's csangle injected. Gated over a real population of junction states rather than
    one, and the verdicts must agree exactly -- including WHICH failure name."""
    hl = HerdLine.from_env(env)
    node = _node(env, rec, True)
    box = F.pursuit_box(env, hl)
    seen = []
    F.junction_beam(node, hl, box, collect=seen, **JN)
    assert len(seen) > 0
    for e in seen:
        r = e['run']
        with_cam = _gates_with_camera(r, hl, e['frames'])
        assert T.junction_gates(r, hl, e['frames']) == with_cam


def _gates_with_camera(jr, hl, frames, *, min_preroll=17.0):
    """`two_roll.junction_gates` as it read before session 133 -- the probe stepping its camera."""
    from harness.tetrapush.two_roll import _bearing, _s16, alive, metrics, CSTICK_NEUTRAL
    if jr._follow_warned:
        return 'followed'
    m = metrics(jr, hl, frames)
    if not alive(m):
        return 'offline'
    tb = _bearing((jr.link.pos_x, jr.link.pos_z), (jr.tx, jr.tz))
    if abs(_s16(jr.link.facing - tb)) <= 0x4000:
        return 'in_cone'
    if m['dist'] > 100.0:
        return 'lost_contact'
    if abs(jr.link.speedF) < 15.0:
        return 'stalled'
    probe = jr.clone()
    probe.step(dict(stickX=128, stickY=128, buttons=0, triggerL=0,
                    substickX=CSTICK_NEUTRAL, substickY=0))
    if probe.link.speedF < min_preroll:
        return 'unarmed'
    return None
