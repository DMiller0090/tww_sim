"""**The gate for the camera driven from the C core** (session 131) -- the last thing keeping a
fully-wired run in Python.

Until now a `FreeRun` could have the native step OR a `LandCamera`, never both, so everything the
search steps with a camera -- the junction, `full_herd.junction_quality`'s glides, the roll exit
tails -- ran on the Python engine. `LandCore.attn_y` supplies the one camera argument a native run
could not (`setAttentionPos`'s ``f32(92.5 + baseTR[1][3])``) and `from_f0.FreeRun._run_camera` is
now the single expression both step paths call.

Three separate claims, because they can fail independently and a merged one would not say which:

  1. **the export IS the wired base row** -- `attn_y` off the core equals the wired `FootFK`'s
     ``base[1][3]`` term every frame. Measured in the courtyard regime that row is Link's constant
     world Y (flat floor, no m35C4 walk lift, no m35B8 decay), so this gate is deliberately about
     the ROW and not about the number: it is what keeps the camera reading the engine that drew the
     frame, rather than a Python cache that would silently go stale if Y ever moved.
  2. **the run is the wired run** -- every published field 0-ULP over a long window, `==` and never
     a tolerance (`[[zero-ulp-tests-only]]`).
  3. **the STAGE is the same stage** -- `roll_candidates` off a native-camera node returns what it
     returns off a wired one. A run-level equality would not catch a wiring error that changed
     which candidates survive, which is the whole risk of moving the search's engine.

Every comparison here is counted for non-vacuity before it is believed (the s130 lesson: a green
comparison is not evidence until you count what it compared -- `junction_quality` once matched
native-to-wired 250 of 250 by returning two `None`s). The window fixture asserts it exercises four
procs, a moving camera and an engaged attention lock; the stage fixture asserts it produced
candidates at all.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import full_herd as F                   # noqa: E402
from harness.tetrapush import search as S_                     # noqa: E402
from harness.tetrapush import seeds as SD                      # noqa: E402
from harness.tetrapush import two_roll as T                    # noqa: E402
from harness.tetrapush.reposition import HerdLine              # noqa: E402
from harness.tetrapush.steered_reposition import _bearing      # noqa: E402
from tww_sim.core.fp import f32, fadds                         # noqa: E402

# the stage knobs, as `tests/test_fan_stage.py` argues them: the fan cannot be thinned for speed
GATE_HALF = 0x2000
GATE_STEP = 8
GATE_LW = ((5, 8), (4, 7), (6, 9))

# what a step publishes -- physics, the camera, and both look models
FIELDS = ('sim_proc', 'sim_facing', 'sim_shape_z', 'sim_link', 'sim_tetra', 'speedF',
          'sim_csangle', 'sim_attn_y', 'sim_eye', 'sim_tattn', 'sim_m3564')


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


def _drive(run, env, hook=None):
    """The herd shape, on one run: the recorded DTM window, an L-held flip, a roll, and the glide.

    Not the recorded window alone -- it never leaves proc 6/9 and the camera barely moves there, so
    a run that froze its csangle after the roll would pass. The roll is where the C-stick is live
    and where `junction_quality` and the exit tails do their stepping."""
    dtm = SD.dtm_input_at(env)
    rows = []

    def step(d):
        rows.append(run.step(d))
        if hook is not None:
            hook(run, rows[-1])

    for k in range(1, 46):
        step(dtm(k))
    hold = T._inp(_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz)),
                  run.csangle, 1.0, buttons=S_.PAD_L, triggerL=255)
    for _ in range(14):
        step(hold)
    aim = _bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
    stream = T.roll_stream((aim, 1.0), hold=1, a_hold=2, l_window=(5, 8), post=(128, 60))
    for k in range(T.MAX_ROLL_FRAMES + 1):
        step(dict(stream(k), substickX=T.CSTICK_NEUTRAL, substickY=0))
    for _ in range(6):
        step(dict(stickX=128, stickY=60, buttons=0, triggerL=0,
                  substickX=T.CSTICK_NEUTRAL, substickY=0))
    return rows


@pytest.fixture(scope='module')
def window(env):
    """Both runs over the same window, plus the wired run's per-frame base row for claim 1."""
    dtm = SD.dtm_input_at(env)
    wired = SD.make_freerun(env)
    wired.pre_seed_input(dtm(0))
    base_rows = []
    wired_rows = _drive(wired, env,
                        hook=lambda r, _row: base_rows.append(r.link._foot.ff.base[1][3]))
    native = SD.make_freerun(env, native=True)
    native.pre_seed_input(dtm(0))
    core_attn = []
    native_rows = _drive(native, env, hook=lambda r, _row: core_attn.append(r._core.attn_y))
    return dict(wired=wired, native=native, wired_rows=wired_rows, native_rows=native_rows,
                base_rows=base_rows, core_attn=core_attn)


def test_the_window_exercises_what_it_claims_to(window):
    """**Counted before anything is believed.** Every equality below is only worth the population
    it ran over, and three of the four things under test here are silent when idle: a camera that
    never moves, a lock that never engages, a roll that never fires."""
    rows = window['wired_rows']
    procs = {r['sim_proc'] for r in rows}
    locked = sum(1 for r in rows if r['sim_cam_in'][1]['truth'])
    assert len(rows) >= 90
    assert {6, 7, 9, T.FRONT_ROLL} <= procs, 'window never reached %r' % sorted(procs)
    assert len({r['sim_csangle'] for r in rows}) >= 20, 'the camera barely moved'
    assert locked >= 10, 'the attention lock never engaged (%d frames)' % locked


def test_attn_y_is_the_engines_own_base_row(window):
    """**Claim 1**: what the core exports IS `setAttentionPos` on the base row the frame drew at.

    Compared against the WIRED `FootFK`'s own row rather than against a recomputation, so this
    fails if the C engine's base ever stops tracking the Python one -- which is the failure the
    export exists to prevent."""
    base, core = window['base_rows'], window['core_attn']
    assert len(base) == len(core) > 0
    for k, (b, c) in enumerate(zip(base, core)):
        assert c == float(fadds(f32(92.5), f32(b))), 'attn_y differs at frame %d' % k


def test_the_native_camera_run_is_the_wired_run(window):
    """**Claim 2**: 0-ULP on every published field, frame by frame.

    Includes `sim_attn_y` and `sim_csangle` (the camera), `sim_eye` / `sim_tattn` (her look) and
    `sim_m3564` (his neck) -- the whole coupled frame, not just the positions, because the camera
    reads the pose and her eye arms the next frame's re-aim."""
    for k, (w, n) in enumerate(zip(window['wired_rows'], window['native_rows'])):
        for f in FIELDS:
            assert w.get(f) == n.get(f), 'frame %d field %s: wired %r != native %r' \
                                         % (k, f, w.get(f), n.get(f))


def test_the_endpoints_match(window):
    """The state the search actually carries forward, off the runs themselves."""
    w, n = window['wired'], window['native']
    assert (w.link.pos_x, w.link.pos_z, int(w.link.facing), int(w.link.travel), w.link.speedF,
            int(w.link.state), w.tx, w.tz, int(w.csangle)) == \
           (n.link.pos_x, n.link.pos_z, int(n.link.facing), int(n.link.travel), n.link.speedF,
            int(n.link.state), n.tx, n.tz, int(n.csangle))


def test_a_clone_of_a_native_camera_run_is_bit_identical(env):
    """The beam branches by cloning, and `roll_kernel.SharedBody` clones a camera run per frame.

    A clone that shared the camera object (or dropped it) would diverge only once the two branches
    delivered different C-stick bytes -- silent for as long as they agree."""
    dtm = SD.dtm_input_at(env)
    run = SD.make_freerun(env, native=True)
    run.pre_seed_input(dtm(0))
    for k in range(1, 20):
        run.step(dtm(k))
    a, b = run.clone(), run.clone()
    tail = [dtm(k) for k in range(20, 46)]
    ra = [a.step(d) for d in tail]
    rb = [b.step(d) for d in tail]
    for k, (x, y) in enumerate(zip(ra, rb)):
        for f in FIELDS:
            assert x.get(f) == y.get(f), 'clone diverged at frame %d field %s' % (k, f)
    assert int(a.csangle) == int(b.csangle)


def test_the_camera_still_steps_when_the_row_is_skipped(env):
    """``record=False`` skips the ROW, never the camera -- on the native path.

    The camera is state: the csangle it commits is what the next frame's physics reads. The wired
    path runs its sub-models after the row and so cannot offer this, and now says so (below)
    instead of silently freezing them."""
    dtm = SD.dtm_input_at(env)
    a = SD.make_freerun(env, native=True)
    b = SD.make_freerun(env, native=True)
    a.pre_seed_input(dtm(0))
    b.pre_seed_input(dtm(0))
    for k in range(1, 30):
        a.step(dtm(k))
        assert b.step(dtm(k), record=False) is None
    assert int(a.csangle) == int(b.csangle)
    assert (a.link.pos_x, a.link.pos_z, a.tx, a.tz) == (b.link.pos_x, b.link.pos_z, b.tx, b.tz)


def test_the_wired_path_refuses_record_false_with_sub_models(env):
    """The trap the guard replaces: on the wired path those three models run AFTER the row."""
    dtm = SD.dtm_input_at(env)
    run = SD.make_freerun(env)
    run.pre_seed_input(dtm(0))
    with pytest.raises(ValueError):
        run.step(dtm(1), record=False)


def test_csangle_injection_and_a_wired_camera_stay_exclusive(env):
    """A run that both injects csangle and commits its own would take whichever ran last."""
    dtm = SD.dtm_input_at(env)
    run = SD.make_freerun(env, native=True)
    run.pre_seed_input(dtm(0))
    with pytest.raises(ValueError):
        run.step(dtm(1), csangle=0x4000)


# ------------------------------------------------- the state a field-holder cannot answer for

def test_the_exec_centre_is_the_frame_the_run_last_stepped(env):
    """`FreeRun.co_center` off either engine, 0-ULP per frame.

    A native run's `LandState` is a field-holder: its `_foot` still carries the f0 SEED pose, so
    `_computed_center(run.link)` answers for a frame the run left long ago -- silently, and only in
    the low digits of the plow depth everything downstream measures. `co_center` asks whichever
    engine posed the frame, and every run-level caller now goes through it."""
    dtm = SD.dtm_input_at(env)
    a, b = SD.make_freerun(env), SD.make_freerun(env, native=True)
    a.pre_seed_input(dtm(0))
    b.pre_seed_input(dtm(0))
    seen = set()
    for k in range(1, 46):
        a.step(dtm(k))
        b.step(dtm(k))
        ca, cb = a.co_center(), b.co_center()
        assert ca == cb, 'exec centre differs at frame %d: %r != %r' % (k, ca, cb)
        seen.add(ca)
    assert len(seen) >= 30, 'the centre barely moved -- the comparison is near-vacuous'


def test_place_link_pokes_both_engines_identically(env):
    """The teleport recipe (`place_link`) has to reach the engine that will step next.

    Written directly, `run.link.pos_x = ...` is a no-op on a native run and the recomputed push
    would come off the seed pose -- so a bed built that way would step from somewhere else
    entirely, without raising."""
    dtm = SD.dtm_input_at(env)
    out = []
    for native in (False, True):
        r = SD.make_freerun(env, native=native)
        r.pre_seed_input(dtm(0))
        for k in range(1, 20):
            r.step(dtm(k))
        cx = r.place_link(r.link.pos_x - 5.0, r.link.pos_z + 3.0, tetra=(r.tx + 1.5, r.tz - 2.5))
        moved = (r.link.pos_x, r.link.pos_z, r.tx, r.tz)
        r.step(dtm(20))
        out.append((cx, moved, r.link.pos_x, r.link.pos_z, r.tx, r.tz, int(r.csangle)))
    assert out[0] == out[1]


# --------------------------------------------------------------------------- the stage itself

def _prologue(env, native):
    """Cycle 1's prologue node, built as `cycle1_nodes` builds it (see `tests/test_fan_stage.py`)."""
    dtm = SD.dtm_input_at(env)
    run = SD.make_freerun(env, native=native)
    run.pre_seed_input(dtm(0))
    fb = _bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
    d = T._inp(fb, run.csangle, 1.0, buttons=S_.PAD_L, triggerL=255)
    run.step(d)
    return dict(run=run, log=[dict(d)], frames=1, jf=1, jv=dict(kind='prologue', phases=[]),
                center=_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz)))


def _cands(cs):
    return [(c['frames'], tuple(sorted(c['knobs'].items(), key=lambda t: t[0])),
             (c['run'].link.pos_x, c['run'].link.pos_z, int(c['run'].link.facing),
              int(c['run'].link.travel), c['run'].link.speedF, int(c['run'].link.state),
              c['run'].tx, c['run'].tz, int(c['run'].csangle), bool(c['run']._follow_warned)),
             c['quality'], tuple(sorted(c['m'].items(), key=lambda t: t[0])))
            for c in cs]


@pytest.fixture(scope='module')
def stage(env):
    """The shipped stage off both engines, at `test_fan_stage`'s knobs (the expensive fixture)."""
    hl = HerdLine.from_env(env)
    box = F.pursuit_box(env, hl)
    kw = dict(half_window=GATE_HALF, step=GATE_STEP, l_windows=GATE_LW, env=env)
    out = []
    for native in (False, True):
        node = _prologue(env, native)
        out.append(F.roll_candidates(node, hl, box, fan_center=node['center'], **kw))
    return out


def test_the_stage_is_the_same_stage(stage):
    """**Claim 3**: the search does not change. Same candidates, same order, same endpoints."""
    ref, nat = stage
    assert ref, 'the prologue produced no candidate -- the comparison would be vacuous'
    assert _cands(nat) == _cands(ref)


def test_the_stage_ran_entirely_on_the_native_engine(env, monkeypatch):
    """**And it ran there for real.** The port is worth nothing if the stage quietly fell back to
    the Python step -- and the equality above would still pass if it had, since the fallback IS the
    reference. Counted the way `_notes/s131_stage_bench.py` counts it: zero wired steps."""
    from harness.tetrapush.from_f0 import FreeRun
    hl = HerdLine.from_env(env)
    box = F.pursuit_box(env, hl)
    node = _prologue(env, True)
    seen = dict(wired=0, native=0)
    orig = FreeRun.step

    def counted(self, *a, **kw):
        seen['native' if self._core is not None else 'wired'] += 1
        return orig(self, *a, **kw)

    monkeypatch.setattr(FreeRun, 'step', counted)
    out = F.roll_candidates(node, hl, box, fan_center=node['center'], half_window=GATE_HALF,
                            step=GATE_STEP, l_windows=GATE_LW, env=env)
    assert out, 'vacuous: the stage returned no candidates'
    assert seen['native'] > 1000, 'the stage barely stepped (%r)' % seen
    assert seen['wired'] == 0, 'the stage still took %d wired steps' % seen['wired']
