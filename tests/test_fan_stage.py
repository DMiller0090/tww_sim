"""**The gate for the kernels INSIDE the herd search's roll stage** (sessions 129-130) -- written
before the wiring, and failing.

Two kernels now, one per half of the stage: `roll_kernel`'s fan under R1 (the aim screen, s129) and
its `SharedBody` under R2 (the camera-target pass, s130). ``env`` turns both on, so each is ALSO
run alone here -- otherwise two ports could cancel, and a failure would not name its half.

`roll_kernel` is already gated against `two_roll.roll_segment` on the whole record
(`tests/test_roll_kernel.py`). What is NOT gated by that, and is the entire risk of putting it in
`full_herd.roll_candidates`, is the WIRING: which L window a shared camera trace belongs to, whether
the twin is at the node's state at all, and whether the screen's prunes and its `aim_keep` ORDER
survive being driven off records instead of off live runs. A stage that keeps a different three aims
is not a speedup, and it would be invisible in a roll-level comparison.

So the contract here is the STAGE's own output: `roll_candidates` with the fan must return what
`roll_candidates` without it returns -- the same candidates, in the same order, at the same knobs,
with the endpoints `==` and never a tolerance (`[[zero-ulp-tests-only]]`). The fan-off path is the
shipped one, untouched, so this compares two implementations rather than a port against a
hand-copied expectation.

The twin's soundness is gated FIRST and separately, because `roll_kernel.wired_csangle_trace`
rebuilds a node by replaying its log from f0 onto a fresh `FreeRun` and everything downstream
assumes that reaches the node's own state. That is a claim about the search's node representation
(a node IS its log), not about the kernel, and it has never been checked past the camera value.

Seeds are the states the stage is actually RUN on, and picking them was a measurement. The
roll-kernel fixture's four banked `junction_beam` endpoints are the wrong population for a stage
gate: off every one of them `roll_candidates` returns NOTHING at any thinning, because from ~40-70 u
behind Tetra a ~205 u `FRONT_ROLL` ends 231-253 u away and `two_roll.alive` prunes the whole fan on
``followed``. Comparing two implementations that both return ``[]`` proves nothing, so the firing
seed here is `full_herd.cycle1_nodes`' own **prologue node** -- state 2 plus ``nflip`` L-held flip
frames -- which is where the search's first roll stage really runs, costs three steps to build, and
returns candidates. The fixture's cycle TERMINALS are still used, for the branch only they reach:
the whole circle TALKS (143 of 143, s127) and the stage must come back empty by the same route,
having built the same twin, rather than by never running.

**And the fan cannot be thinned for speed.** `cycle1_nodes` ships ``half_window=0x2000``, ``step=4``
and three L windows. ``step=8`` halves the fan to 72 aims and still fires -- the same 5 candidates
as step 4 -- while ``step=16`` returns NOTHING. What survives this screen is razor-thin
(`cycle1_nodes`' own docstring reports three surviving (aim, window) pairs at the shipped step, all
the SAME aim), so a coarser fan does not sample a smaller version of the problem, it samples none of
it. Hence `GATE_STEP` = 8 and not something cheaper.
"""
import json
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import full_herd as F                   # noqa: E402
from harness.tetrapush import roll_kernel as RK                # noqa: E402
from harness.tetrapush import search as S_                     # noqa: E402
from harness.tetrapush import seeds as SD                      # noqa: E402
from harness.tetrapush import two_roll as T                    # noqa: E402
from harness.tetrapush.reposition import HerdLine              # noqa: E402
from harness.tetrapush.steered_reposition import _bearing      # noqa: E402

FIXTURE = os.path.join(_REPO, 'fixtures', 'courtyard_roll_kernel_nodes.json')

# cycle 1's own knobs -- see "the fan cannot be thinned for speed" in the module docstring
GATE_HALF = 0x2000
GATE_STEP = 8
GATE_LW = ((5, 8), (4, 7), (6, 9))


def _env():
    return SD.load_env()


def _fixture():
    if not os.path.exists(FIXTURE):
        pytest.skip('roll-kernel seeds missing: %s' % FIXTURE)
    with open(FIXTURE) as fh:
        return json.load(fh)


def _state(run):
    """Everything the search reads off a post-roll endpoint, as a comparable tuple."""
    return (run.link.pos_x, run.link.pos_z, int(run.link.facing), int(run.link.travel),
            run.link.speedF, int(run.link.state), run.tx, run.tz, int(run.csangle),
            bool(run._follow_warned))


def _rebuild(env, log):
    """A node rebuilt from its input log on a fresh wired `FreeRun` -- the search's own node, and
    the thing `wired_csangle_trace` assumes it can reconstruct."""
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for d in log:
        run.step(d)
    return run


@pytest.fixture(scope='module')
def env():
    return _env()


@pytest.fixture(scope='module')
def hl(env):
    return HerdLine.from_env(env)


@pytest.fixture(scope='module')
def box(env, hl):
    return F.pursuit_box(env, hl)


@pytest.fixture(scope='module')
def nodes(env):
    """The fixture's seeds as SEARCH nodes -- the dict shape `roll_candidates` consumes.

    ``jv`` is synthesised (the fixture banks logs, not junction variants); it only reaches the
    candidate's ``knobs``, and both implementations under test are handed the same one."""
    rec = _fixture()
    out = []
    for nd in rec['nodes']:
        run = _rebuild(env, nd['log'])
        out.append(dict(run=run, log=list(nd['log']), frames=int(nd['frames']),
                        jf=int(nd['jf']), jv=dict(kind=nd['kind'], phases=()),
                        kind=nd['kind'], banked_cs=int(nd['csangle']),
                        banked_link=tuple(nd['link'])))
    return out


@pytest.fixture(scope='module')
def prologue(env):
    """**Cycle 1's prologue node, built exactly as `cycle1_nodes` builds it** -- state 2 plus one
    L-held proc-7 flip frame, handed to the roll stage as a pseudo junction endpoint.

    This is where the search's first roll stage really runs, so it is the seed that makes the
    comparison mean something. ``nflip`` is 1 because that is the one that FIRES: measured at the
    knobs above, nflip 1 returns 5 candidates and nflip 2 and 3 return none.

    It also carries the stage's ``fan_center``, which here is the bearing to Tetra and NOT the herd
    bearing -- sweeping the wrong fan would leave both paths agreeing about a fan the search never
    sweeps, so it is taken from where the shipped stage takes it."""
    dtm = SD.dtm_input_at(env)
    run = SD.make_freerun(env)
    run.pre_seed_input(dtm(0))
    log = []
    fb = _bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
    d = T._inp(fb, run.csangle, 1.0, buttons=S_.PAD_L, triggerL=255)
    log.append(dict(d))
    run.step(d)
    return dict(run=run, log=log, frames=1, jf=1, jv=dict(kind='prologue', phases=[]),
                center=_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz)))


@pytest.fixture(scope='module')
def stage(env, hl, box, prologue):
    """The stage run both ways at the shipped keeps, once (it is the expensive fixture)."""
    return _both(prologue, hl, box, env)


@pytest.fixture(scope='module')
def stage_keep1(env, hl, box, prologue):
    """The stage run both ways with both keeps squeezed to one -- see the order gate.

    ``require_quality`` is off here, and that is not a convenience: at the shipped keeps the
    top-ranked aim's WHOLE camera-target family fails `junction_quality` (`cycle1_nodes`' docstring
    reports the same thing at ``step=4``), so an ``aim_keep=1`` cut that also demanded continuability
    would empty the stage and gate nothing. Turning it off leaves the single screen winner visible,
    which is the object under test."""
    return _both(prologue, hl, box, env, aim_keep=1, tcs_keep=1, require_quality=False)


# --------------------------------------------------------------------------- the twin's premise

def test_a_node_replayed_from_its_log_is_the_node(env, nodes):
    """**A node IS its log** -- gated against the BANKED node, not against a second replay.

    `wired_csangle_trace` replays a node's log from f0 on a fresh wired run to recover the camera
    the fan needs, and `self_eye_twin` replays it again on the native engine. Both rest on the
    replay landing on the node's own state. Comparing two replays of the same log would only gate
    determinism; what has to hold is that the log reconstructs the state the SEARCH had when
    `junction_beam` produced the node, so the reference is the Link position and csangle the fixture
    banked from that run (`[[zero-ulp-tests-only]]` -- `==`, and the position is not rounded)."""
    for nd in nodes:
        run = nd['run']
        assert (run.link.pos_x, run.link.pos_z) == nd['banked_link'], \
            'node %s does not replay to the state it was banked at' % nd['kind']
        assert int(run.csangle) == nd['banked_cs']


def test_the_twin_is_at_the_nodes_state(env, nodes):
    """The fan clones the twin, so a twin one frame off (or at the wrong camera) would make every
    record in the stage exact about a state the search never reaches. The camera injection is
    off-by-one BY CONSTRUCTION (`self_eye_twin`'s doc), which is exactly the kind of error that
    still looks plausible, so the twin is compared to the wired node itself."""
    for nd in nodes:
        cs = RK.wired_csangle_trace(env, nd['log'])
        twin = RK.self_eye_twin(env, nd['log'], cs)
        assert (twin.link.pos_x, twin.link.pos_z, int(twin.link.facing), int(twin.link.travel),
                twin.link.speedF, int(twin.link.state), twin.tx, twin.tz) == \
               (nd['run'].link.pos_x, nd['run'].link.pos_z, int(nd['run'].link.facing),
                int(nd['run'].link.travel), nd['run'].link.speedF, int(nd['run'].link.state),
                nd['run'].tx, nd['run'].tz)


# --------------------------------------------------------------------------- the stage itself

def _both(node, hl, box, env, **kw):
    kw.setdefault('half_window', GATE_HALF)
    kw.setdefault('step', GATE_STEP)
    kw.setdefault('l_windows', GATE_LW)
    if 'center' in node:
        kw.setdefault('fan_center', node['center'])
    ref = F.roll_candidates(node, hl, box, shared_body=False, **kw)
    fan = F.roll_candidates(node, hl, box, env=env, **kw)
    return ref, fan


def _cands(cs):
    return [(c['frames'], tuple(sorted(c['knobs'].items(), key=lambda t: t[0])),
             _state(c['run']), c['quality'], tuple(sorted(c['m'].items(), key=lambda t: t[0])))
            for c in cs]


@pytest.mark.slow
def test_the_stage_is_the_same_stage(stage):
    """The whole point: same candidates, same order, same knobs, same endpoints, `==`."""
    ref, fan = stage
    assert ref, 'the prologue produced no candidate -- the comparison would be vacuous'
    assert _cands(fan) == _cands(ref)


@pytest.mark.slow
def test_the_stage_agrees_on_the_banked_nodes_too(env, hl, box, nodes):
    """The banked seeds run through the whole stage BY THE SAME ROUTE, coarsely.

    They return nothing (see the module doc and the gate below), so this is not where the equality
    is earned -- it is where the wiring meets a real 55-frame node log instead of a one-frame
    prologue, which is what `roll_kernel.node_twin`'s reconstruction check exists for. A truncated or
    re-based log raises there rather than fanning a wrong state."""
    for nd in nodes:
        ref, fan = _both(nd, hl, box, env, step=32)
        assert _cands(fan) == _cands(ref), 'stage differs at %s jf %d' % (nd['kind'], nd['jf'])


def test_the_whole_circle_talks_at_a_cycle_terminal(env, hl, box, nodes):
    """A cycle TERMINAL refuses every aim (s127, 143 of 143). Both paths must come back empty --
    and the fan must do it having built the twin and screened, not by skipping the node."""
    seen = 0
    for nd in nodes:
        if nd['kind'] != 'terminal':
            continue
        ref, fan = _both(nd, hl, box, env, step=32)
        assert ref == [] and fan == []
        talks = RK.talk_screen(nd['run'],
                               [a for _w, a in T.roll_facing_fan(nd['run'], hl.bearing_bam(),
                                                                 GATE_HALF, 32)])
        assert talks and all(talks), 'this terminal does not refuse its whole fan'
        seen += 1
    assert seen, 'no terminal seed in the fixture -- the refusal branch is untested'


def test_the_banked_junction_endpoints_are_empty_because_the_roll_outruns_her(env, hl, nodes):
    """**Why the stage gate is seeded on a prologue and not on these** -- pinned, because it is a
    fact about the LAST cycle's population and not a property of the gate.

    From a banked cycle-2 junction endpoint Link sits ~40-70 u behind Tetra and a `FRONT_ROLL` is
    ~205 u, so the roll ends 231-253 u away, `FreeRun` warns past `FOLLOW_ENGAGE_DIST` and
    `two_roll.alive` prunes on ``followed``. The aims that do stay inside it (4 of 83 at the shipped
    step on the first seed) die on ``lead`` instead -- they end AHEAD of her. Either way the fan
    empties, at every thinning, which is the s126 crossing/runway trade seen from one cycle down: if
    it ever stops being true the reason is worth looking at, not a silently gained seed."""
    jn = [n for n in nodes if n['kind'] == 'junction']
    assert jn
    for nd in jn:
        aims = [a for _w, a in T.roll_facing_fan(nd['run'], hl.bearing_bam(), 0x2800, 32)]
        twin = RK.node_twin(env, nd['log'], check=nd['run'])
        recs = RK.roll_fan(nd['run'], aims, l_window=(5, 8), fast=twin)
        live = [r for r in recs if r['ok'] and not r['talk_unsafe']]
        assert live, 'these endpoints do roll -- the emptiness is not a refusal'
        ms = [T.metrics(RK.RecordRun(r), hl, nd['frames'] + r['frames']) for r in live]
        assert not any(T.alive(m) for m in ms), 'a roll off this endpoint survives the herd prune'
        assert sum(m['followed'] for m in ms) > len(ms) // 2, \
            'the endpoints no longer empty MAINLY on the follow prune'


def test_the_seed_exercises_both_branches_of_the_screen(env, hl, box, prologue):
    """**What the fan actually reaches** -- asserted rather than assumed (the s128 habit).

    A seed whose fan was all refusals, or all survivors, would make the equality above true without
    the screen ever choosing anything. Counted on `roll_kernel.roll_fan`'s records rather than on 72
    more wired rollouts: the test above is what earns the right to read them, and re-firing the fan
    wired would double the gate's cost to re-establish what it just proved."""
    aims = [a for _w, a in T.roll_facing_fan(prologue['run'], prologue['center'],
                                             GATE_HALF, GATE_STEP)]
    assert len(aims) > 8, 'the fan is too small to screen anything'
    twin = RK.node_twin(env, prologue['log'])
    kept, pruned = 0, 0
    for rec in RK.roll_fan(prologue['run'], aims, l_window=GATE_LW[0], fast=twin):
        rv = RK.RecordRun(rec)
        if rec['ok'] and not rec['talk_unsafe'] and rec['roll_speedF'] is not None \
                and rec['roll_speedF'] >= 20.0 \
                and T.alive(T.metrics(rv, hl, prologue['frames'] + rec['frames'])) \
                and F.frame_in_model(rv, F.O.courtyard_walls()):
            kept += 1
        else:
            pruned += 1
    assert kept and pruned, 'the seed fan is all-survivors or all-pruned (kept %d, pruned %d)' \
                            % (kept, pruned)


@pytest.mark.slow
def test_each_kernel_carries_the_stage_on_its_own(env, hl, box, prologue):
    """**R1 and R2 are separate ports and are gated separately** (session 130).

    ``env`` turns both on at once, so a stage comparison with it would pass if the two kernels'
    errors cancelled -- and, worse, would not say which one moved. R1 is `roll_kernel`'s fan; R2 is
    the shared roll body. Each is run alone against the fully wired stage, and both together
    against it, so a regression names its own half."""
    kw = dict(half_window=GATE_HALF, step=GATE_STEP, l_windows=GATE_LW,
              fan_center=prologue['center'])
    wired = F.roll_candidates(prologue, hl, box, shared_body=False, **kw)
    assert wired, 'the prologue produced no candidate -- the comparison would be vacuous'
    r1_only = F.roll_candidates(prologue, hl, box, env=env, shared_body=False, **kw)
    r2_only = F.roll_candidates(prologue, hl, box, shared_body=True, **kw)
    both = F.roll_candidates(prologue, hl, box, env=env, **kw)
    assert _cands(r1_only) == _cands(wired), 'the fan alone moved the stage'
    assert _cands(r2_only) == _cands(wired), 'the shared body alone moved the stage'
    assert _cands(both) == _cands(wired)


@pytest.mark.slow
def test_the_shared_body_really_runs_on_this_seed(env, hl, box, prologue):
    """The R2 comparison above is only worth something if a shared body actually FORMS here -- an
    aim that talks, or one whose roll never fires, silently falls back to the wired path and the
    equality would then be two names for the same code. Checked on the aims the screen keeps."""
    kw = dict(half_window=GATE_HALF, step=GATE_STEP, l_windows=GATE_LW,
              fan_center=prologue['center'])
    kept = F.roll_candidates(prologue, hl, box, shared_body=False, **kw)
    assert kept
    seen = 0
    for c in kept:
        body = RK.SharedBody(prologue['run'], c['knobs']['aim'],
                             l_window=tuple(c['knobs']['l_window']))
        assert body.ok, 'no shared body for a kept aim %r' % (c['knobs']['aim'],)
        assert 1 < body.branch < c['frames'] - prologue['frames'], \
            'the body shares everything or nothing (branch %d of %d segment frames)' \
            % (body.branch, c['frames'] - prologue['frames'])
        seen += 1
    assert seen


@pytest.mark.slow
def test_the_screen_order_survives_the_fan_being_evaluated_per_l_window(stage_keep1):
    """**The one thing the record comparison cannot catch.** `roll_candidates` sorts its screen with
    a STABLE sort, so ties break by insertion order, and the fan is evaluated per L WINDOW while the
    wired path walks (aim, l_window). Squeezing both keeps to one makes that order decide the whole
    stage output rather than three-of-many."""
    ref, fan = stage_keep1
    assert ref, 'the aim_keep=1 cut emptied the stage -- nothing was ordered'
    assert _cands(fan) == _cands(ref)
