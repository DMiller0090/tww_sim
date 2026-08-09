"""**The look pair inside the C step** (session 128) -- 0-ULP against the Python models.

s127 put the coupled courtyard frame in C and left two models in Python because they are what
generates the proc-9 re-aim eye: Tetra's `Zl1Look` (her whole execute frame -- optn_1 timers, the
JntCtrl look chase, the McaMorf advance, and the 7-concat J3D eye chain) and Link's `NeckLook`
(m3564). Measured this session, they are **91% of the coupled step** -- her 77.5%, the neck 13.4%,
the C core itself only 9.1% -- so porting them is the entire remaining win and nothing else in the
frame is worth looking at.

This gate is the claim that the port changed the SPEED and not the ANSWER. It compares two whole
runs -- `make_freerun_self_eye` (C physics, Python look pair) against `make_freerun_native_look`
(everything in C) -- frame by frame, `==` and never a tolerance (`[[zero-ulp-tests-only]]`).

WHAT IT COMPARES, and why it is not just the eye: the eye is one output of a state machine with a
long memory. Her morf's per-joint OLD-POSE STORE is rewritten every frame and only reaches the eye
through the NEXT blend, so a wrong store is silent for a frame and then diverges; the timers decide
an anim switch a hundred frames later. So the snapshot is the whole hidden state -- the joint chase
angles and their targets, every timer, the McaMorf ctrl, the old-pose store, and the neck's m3564.

TWO WINDOWS, because the recorded one does not exercise her:
  * the **recorded DTM window**, the faithful regime, where `f84d == 1` on all 45 frames (she looks
    at him every frame) and the look-around anim never fires;
  * a **long run**, because `f7b8` is seeded at 116 -- the ANM_LOOK switch, the morf blend it starts,
    the wrap flag `f7c3`, and the `cLib_getRndValue` re-seed horizon are ALL past the end of the
    recorded movie. `test_the_long_window_actually_exercises_her` asserts that coverage, so none of
    these fields is being compared against a constant.

`tests/test_freerun_self_eye.py` stays the CONTRACT and is untouched: it pins the Python-look run to
the wired one, and this gate pins the native one to that.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import seeds as SD                        # noqa: E402

pytest.importorskip('tww_sim.core.anim._anmc', reason='native accelerator not built')

#: The recorded window (both roll bodies, the proc-9 tier, the MOVE backslide).
UPTO = 45
#: Long enough to cross the f0 look timer (f7b8 = 116) AND complete a look cycle past it.
LONG = 260
#: An arbitrary but fixed injected camera -- the look chain is the subject, not the camera.
CS = 39000


def _zl1_snap_py(zl1):
    """The Python `Zl1Look`'s full hidden state, in the shape `LandCore.zl1_snapshot` returns."""
    m = zl1.morf
    return dict(
        eye=tuple(zl1.eye),
        angles=tuple(tuple(a) for a in zl1.jnt.angles),
        targets=(zl1.jnt.f2c, zl1.jnt.f2e, zl1.jnt.f30, zl1.jnt.f32),
        trn=bool(zl1.jnt.trn), turn_step=int(zl1.jnt.turn_step),
        cur_anm=int(zl1.cur_anm), f84d=int(zl1.f84d), f7b8=int(zl1.f7b8),
        f7ba=int(zl1.f7ba), f7bc=int(zl1.f7bc), f7c3=int(zl1.f7c3),
        m_frame=zl1.m_frame, f83c=int(zl1.f83c), f83e=int(zl1.f83e),
        counter=int(zl1.counter), rng_horizon=bool(zl1.rng_horizon),
        angle_y=int(zl1.angle_y), head_org=tuple(zl1.head_org),
        frame=m.frame, cur_morf=m.cur_morf, prev_morf=m.prev_morf, morf_step=m.morf_step,
        end=int(m.end), loop=int(m.loop), rate=m.rate, attr=int(m.attr),
        old_quat=tuple(tuple(m.old_quat[j]) for j in sorted(m.old_quat)),
        old_trans=tuple(tuple(m.old_trans[j]) for j in sorted(m.old_trans)),
    )


def _state(run):
    """The coupled physics both runs must agree on before their look state can mean anything."""
    return (run.link.pos_x, run.link.pos_z, int(run.link.facing), int(run.link.travel),
            run.link.speedF, int(run.link.state), run.tx, run.tz)


def _pair(env=None):
    env = SD.load_env() if env is None else env
    at = SD.dtm_input_at(env)
    py = SD.make_freerun_self_eye(env)
    py.pre_seed_input(at(0))
    nat = SD.make_freerun_native_look(env)
    nat.pre_seed_input(at(0))
    return env, at, py, nat


def _step_both(py, nat, inp):
    py.step(inp, csangle=CS)
    nat.step(inp, csangle=CS)


def test_the_native_look_chain_is_the_python_one_over_the_recorded_window(recwarn):
    """The faithful regime, frame by frame: physics, the eye, the neck, and her whole hidden state."""
    _env, at, py, nat = _pair()
    for k in range(1, UPTO):
        _step_both(py, nat, at(k))
        assert _state(nat) == _state(py), 'physics diverged at frame %d' % k
        assert nat._core.zl1_snapshot() == _zl1_snap_py(py.zl1), 'zl1 state diverged at frame %d' % k
        assert nat._core.neck_snapshot() == (py.neck.x, py.neck.y, py.neck.z), \
            'm3564 diverged at frame %d' % k


def test_the_native_look_chain_is_the_python_one_past_the_recorded_window(recwarn):
    """The long window -- where the anim switch, the morf blend and the timer re-seed live. The
    inputs cycle the recorded movie; faithfulness to the console is not the subject here (both
    engines compute the same thing), reproducing it bit-for-bit is."""
    _env, at, py, nat = _pair()
    for k in range(1, LONG):
        _step_both(py, nat, at(k % 40))
        assert _state(nat) == _state(py), 'physics diverged at frame %d' % k
        assert nat._core.zl1_snapshot() == _zl1_snap_py(py.zl1), 'zl1 state diverged at frame %d' % k
        assert nat._core.neck_snapshot() == (py.neck.x, py.neck.y, py.neck.z), \
            'm3564 diverged at frame %d' % k


def test_the_long_window_actually_exercises_her(recwarn):
    """No field above is being checked against a constant: over the long window she must switch
    anims, run a morf, raise the wrap flag, and reach the RNG horizon -- and the neck must both
    select a look target and fail to."""
    _env, at, py, nat = _pair()
    seen = dict(anm=set(), morf=False, wrap=set(), horizon=False, f84d=set(),
                neck_look=set(), m3564=set())
    for k in range(1, LONG):
        _step_both(py, nat, at(k % 40))
        s = nat._core.zl1_snapshot()
        seen['anm'].add(s['cur_anm'])
        seen['f84d'].add(s['f84d'])
        seen['wrap'].add(s['f7c3'])
        seen['morf'] = seen['morf'] or s['cur_morf'] < 1.0
        seen['horizon'] = seen['horizon'] or s['rng_horizon']
        seen['m3564'].add(nat._core.neck_snapshot())
        seen['neck_look'].add(py.neck.select_look_pos(
            (py.link.pos_x, py.link.pos_y, py.link.pos_z), py._eye_next,
            int(py._core.m34de), py._core._atn_state in (1, 2),
            bool(py._core._atn_list_present)) is not None)
    assert len(seen['anm']) == 2, 'the look-around anim never fired: %r' % (seen['anm'],)
    assert seen['morf'], 'the morf blend never ran -- the quat-lerp pose path is untested'
    assert seen['wrap'] == {0, 1}, 'the anim-wrap flag never toggled: %r' % (seen['wrap'],)
    assert seen['horizon'], 'the RNG horizon was never reached'
    assert seen['f84d'] == {0, 1}, 'her look mode never left the player chase: %r' % (seen['f84d'],)
    assert len(seen['m3564']) > 1, 'm3564 never moved -- the neck is being compared to a constant'
    assert seen['neck_look'] == {True, False}, \
        'the neck look-pos selection never took both branches: %r' % (seen['neck_look'],)


def test_a_clone_of_a_native_look_run_is_the_run(recwarn):
    """The roll fan branches one node into a whole aim fan by cloning, so the C look state owes
    bit-identity across a clone exactly as her Python model does."""
    _env, at, _py, nat = _pair()
    for k in range(1, 12):
        nat.step(at(k), csangle=CS)
    twin = nat.clone()
    for k in range(12, 40):
        nat.step(at(k), csangle=CS)
        twin.step(at(k), csangle=CS)
        assert _state(twin) == _state(nat), 'clone diverged at frame %d' % k
        assert twin._core.zl1_snapshot() == nat._core.zl1_snapshot()
        assert twin._core.neck_snapshot() == nat._core.neck_snapshot()


def test_the_native_look_run_exposes_its_state_live(recwarn):
    """The fully-native run must stay a DROP-IN for every consumer of the Python-look one: reading
    `_eye_next` / `neck` off it gives the value the C engine holds NOW, not the seed it was built
    with. A stale mirror here is the silent kind of wrong -- the run still looks like a run."""
    _env, at, py, nat = _pair()
    seed_eye = tuple(nat.zl1.eye)
    for k in range(1, UPTO):
        _step_both(py, nat, at(k))
        assert tuple(nat._eye_next) == tuple(py._eye_next), 'eye mirror stale at frame %d' % k
        assert (nat.neck.x, nat.neck.y, nat.neck.z) == (py.neck.x, py.neck.y, py.neck.z)
    assert tuple(nat._eye_next) != seed_eye, 'the eye never left its seed value'


def test_the_fleet_carries_the_look_chain_in_parallel(recwarn):
    """The port is nogil C inside `_step_courtyard_nogil`, so `CourtyardFleet.run_par` should carry
    it -- that is the next parallelisation step and worth gating rather than assuming.

    The csangle spread is DELIBERATELY wide. At a 1-BAM spread eight cores land on three distinct
    Link positions, Tetra does not move differently at all, and every eye comes out identical -- a
    fleet gate seeded like that would pass without the look chain running.
    """
    from tww_sim.core.anim import _anmc as N
    env = SD.load_env()
    at = SD.dtm_input_at(env)
    n, nframes = 8, 30

    def build():
        out = []
        for _ in range(n):
            r = SD.make_freerun_native_look(env)
            r.pre_seed_input(at(0))
            out.append(r)
        return out

    schedules = []
    for i in range(n):
        row = []
        for f in range(1, nframes + 1):
            t = at(f % 40)
            row.append((t['stickX'], t['stickY'], t.get('buttons', 0), t.get('triggerL', 0),
                        (CS + i * 2000) & 0xFFFF))
        schedules.append(row)

    def snap(runs):
        return [(r._core.pos_x, r._core.pos_z, int(r._core.facing), r._core._tetra_x,
                 r._core._tetra_z, r._core.look_eye, r._core.neck_snapshot()) for r in runs]

    seq_runs = build()
    for i, r in enumerate(seq_runs):
        for f in range(nframes):
            w = schedules[i][f]
            r._core.step_courtyard(w[0], w[1], w[2], w[3], w[4],
                                   0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0, 1)
    seq = snap(seq_runs)

    par_runs = build()
    fleet = N.CourtyardFleet([r._core for r in par_runs], 1)
    fleet.set_schedule(schedules)
    fleet.run_par(nframes, 0)

    assert len(set(str(s[5]) for s in seq)) == n, \
        'the cores did not diverge -- this would pass without the look chain running'
    assert snap(par_runs) == seq, 'parallel diverged from sequential with the look pair wired'


def test_the_native_look_run_refuses_an_injected_eye(recwarn):
    """Same refusal the Python-look run makes: the eye is generated, so being handed one is a
    caller error rather than something to silently ignore."""
    _env, at, _py, nat = _pair()
    with pytest.raises(ValueError):
        nat.step(at(1), eye=(0.0, 0.0, 0.0))
