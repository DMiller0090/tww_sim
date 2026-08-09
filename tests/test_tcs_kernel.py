"""**The gate for the SHARED ROLL BODY** -- R2's kernel (session 130).

`full_herd.roll_candidates`' R2 re-runs one aim's roll under ~25 camera targets. `roll_kernel`'s
`SharedBody` steps that roll ONCE and re-runs only the exit tail per target, so the contract it owes
is exactly `two_roll.roll_segment`'s: the same dict, the same endpoint run, the same delivered log,
for EVERY target on the real grid -- `==`, never a tolerance (`[[zero-ulp-tests-only]]`).

Three separate claims hold it up, and each is gated on its own rather than folded into the record
comparison, because each could be wrong in a way the others would hide:

  1. **the branch frame is where the tail starts.** The shared body stops at the first frame after
     the `FRONT_ROLL` block; that this IS where a camera target first changes the physics is
     measured here, not assumed (the s129 handoff asked for exactly this, and
     `full_herd.target_cs_is_exit_only` only ever checked two offsets and six fields).
  2. **one body's camera arguments serve the whole family.** `camera_walks` walks every target's
     camera over the arguments the FROZEN body produced -- including frames where the per-target
     physics has already diverged. Gated against each target's own wired run, per frame.
  3. **the prefix tree is the straight walk.** Targets that have delivered the same C-stick bytes
     share a camera object; a missing `clone` there would corrupt one member and not the other.

Seeds are cycle 1's own prologue node (state 2 + one L-held flip frame) -- where the stage really
runs, and the seed `tests/test_fan_stage.py` had to go looking for -- plus the banked junction
endpoints from the roll-kernel fixture, which is where a real 55-frame node log meets the branch.
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
from harness.tetrapush.from_f0 import cam_pad                  # noqa: E402
from harness.tetrapush.reposition import ESS_DOWN              # noqa: E402
from harness.tetrapush.steered_reposition import _bearing      # noqa: E402

FIXTURE = os.path.join(_REPO, 'fixtures', 'courtyard_roll_kernel_nodes.json')
LWS = ((5, 8), (4, 7))


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


@pytest.fixture(scope='module')
def prologue(env):
    """Cycle 1's prologue node, built as `full_herd.cycle1_nodes` builds it."""
    dtm = SD.dtm_input_at(env)
    run = SD.make_freerun(env)
    run.pre_seed_input(dtm(0))
    d = T._inp(_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz)),
               run.csangle, 1.0, buttons=S_.PAD_L, triggerL=255)
    run.step(d)
    return dict(run=run, log=[dict(d)], frames=1,
                center=_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz)))


@pytest.fixture(scope='module')
def aims(prologue):
    """Five aims spread across the stage's own fan -- not one, since the branch frame is a property
    of the roll and a single aim would not show it varying (or staying put)."""
    fan = T.roll_facing_fan(prologue['run'], prologue['center'], 0x2000, 8)
    return [fan[i][1] for i in (0, len(fan) // 3, len(fan) // 2, 2 * len(fan) // 3, len(fan) - 1)]


@pytest.fixture(scope='module')
def grid(prologue):
    return list(F.derived_target_css(prologue['run']))


def _wired(node, aim, lw, tcs):
    """The shipped path: a clone, `roll_segment`, and the log it appends."""
    rr = node['run'].clone()
    log = list(node['log'])
    seg = T.roll_segment(rr, aim, target_cs=tcs, l_window=lw, log=log)
    return seg, rr, log


def _state(run):
    return (run.link.pos_x, run.link.pos_z, int(run.link.facing), int(run.link.travel),
            run.link.speedF, int(run.link.state), run.tx, run.tz, int(run.csangle),
            bool(run._follow_warned))


# --------------------------------------------------------------------------- the contract

def test_the_shared_body_reproduces_every_target(prologue, aims, grid):
    """**The whole point**: the same segment dict, the same endpoint, the same log, per target."""
    seen = 0
    for lw in LWS:
        for aim in aims:
            body = RK.SharedBody(prologue['run'], aim, l_window=lw)
            assert body.ok, 'no shared body for aim %r lw %r' % (aim, lw)
            walk = RK.camera_walks(body, grid)
            for tcs in grid:
                log = list(prologue['log'])
                seg, rr = RK.tcs_segment(body, walk, tcs, log=log)
                wseg, wrun, wlog = _wired(prologue, aim, lw, tcs)
                assert seg == wseg, 'segment differs at aim %r lw %r tcs %d' % (aim, lw, tcs)
                assert _state(rr) == _state(wrun)
                assert log == wlog, 'the delivered log differs at aim %r lw %r tcs %d' \
                                    % (aim, lw, tcs)
                seen += 1
    assert seen == len(LWS) * len(aims) * len(grid)


def test_the_branch_frame_is_where_the_tail_starts(prologue, aims, grid):
    """**Measured, not assumed** -- the s129 handoff's own condition for this port.

    The body branches at the first frame after the `FRONT_ROLL` block. Two things have to hold and
    they are not the same thing:

      * SAFETY -- no frame BEFORE the branch depends on the camera target, for any target on the
        grid. That is what lets the shared frames be shared, and it is the assertion that would
        catch a branch set one frame too late.
      * TIGHTNESS -- somewhere on this population a target diverges AT the branch, so the frame is
        the real boundary and not a cautious guess leaving free frames unshared. Per aim it can be
        later (frame 18-19) or never at all: with the roll ending in proc 6 and Link stopped there
        is nothing left for the camera to steer, which is why this is asserted over the population
        and not per aim.

    The csangle is excluded on purpose: it differs from frame 1, which is the whole point -- the
    camera diverges immediately and the physics does not."""
    earliest, latest_branch, moved = None, 0, 0
    for lw in LWS:
        for aim in aims:
            body = RK.SharedBody(prologue['run'], aim, l_window=lw)
            base = _phys_trace(prologue, aim, lw, None)
            latest_branch = max(latest_branch, body.branch)
            assert 1 < body.branch < len(base), 'the body shares nothing at aim %r lw %r' % (aim,
                                                                                            lw)
            for tcs in grid:
                rows = _phys_trace(prologue, aim, lw, tcs)
                d = next((k for k in range(min(len(rows), len(base))) if rows[k] != base[k]), None)
                if d is None:
                    continue                      # nothing the camera could still steer
                moved += 1
                assert d >= body.branch, \
                    'aim %r lw %r tcs %d diverges at %d, BEFORE the branch %d' % (aim, lw, tcs, d,
                                                                                  body.branch)
                earliest = d if earliest is None else min(earliest, d)
    assert moved, 'no target on the grid ever changed the physics -- nothing was gated'
    assert earliest == latest_branch, \
        'the earliest divergence is %s but the branch is %d' % (earliest, latest_branch)


def _phys_trace(node, aim, lw, tcs):
    rr = node['run'].clone()
    stream = T.roll_stream(aim, hold=1, a_hold=2, l_window=lw, post=ESS_DOWN)
    out = []
    for k in range(T.MAX_ROLL_FRAMES + 1):
        rr.step(dict(stream(k), substickX=T.slew_substick(rr.csangle, tcs), substickY=0))
        out.append((rr.link.pos_x, rr.link.pos_z, int(rr.link.facing), int(rr.link.travel),
                    rr.link.speedF, int(rr.link.state), rr.tx, rr.tz))
    return out


def test_one_bodys_camera_arguments_serve_the_whole_family(prologue, aims, grid):
    """**The economy, gated past the divergence.** The camera is walked over the FROZEN body's
    arguments, and past the branch those arguments are no longer that target's own physics -- so
    this checks the committed csangle per frame, for the whole segment, against each target's own
    wired run. It holds because csangle is position-independent in this regime (`FreeRun`'s class
    doc); if that ever stops being true this is where it surfaces."""
    n = T.MAX_ROLL_FRAMES + 1
    for lw in LWS[:1]:
        for aim in aims:
            body = RK.SharedBody(prologue['run'], aim, l_window=lw)
            args = _full_args(prologue, aim, lw, n)
            for tcs in grid:
                assert _walk_full(prologue, body, args, tcs, n) == _cs_trace(prologue, aim, lw,
                                                                            tcs, n), \
                    'csangle differs at aim %r tcs %d' % (aim, tcs)


def _full_args(node, aim, lw, n):
    rr = node['run'].clone()
    stream = T.roll_stream(aim, hold=1, a_hold=2, l_window=lw, post=ESS_DOWN)
    return [rr.step(dict(stream(k), substickX=T.CSTICK_NEUTRAL,
                         substickY=0))['sim_cam_in'] for k in range(n)]


def _walk_full(node, body, args, tcs, n):
    cam = node['run'].camera.clone()
    cs = int(node['run'].csangle)
    prev = node['run']._prev_raw
    out = []
    for k in range(n):
        sub = T.slew_substick(cs, tcs)
        inp = dict(body.stream(k), substickX=sub, substickY=0)
        cs = int(cam.step(cam_pad(prev), *args[k]))
        out.append(cs)
        prev = inp
    return out


def _cs_trace(node, aim, lw, tcs, n):
    rr = node['run'].clone()
    stream = T.roll_stream(aim, hold=1, a_hold=2, l_window=lw, post=ESS_DOWN)
    out = []
    for k in range(n):
        rr.step(dict(stream(k), substickX=T.slew_substick(rr.csangle, tcs), substickY=0))
        out.append(int(rr.csangle))
    return out


def test_the_prefix_tree_is_the_straight_walk(prologue, aims, grid):
    """Targets that have delivered the same C-stick bytes share a camera object until they split.
    A missing `clone` at a split would corrupt one member and leave the other right, which the
    record comparison would catch only if the corrupted member happened to survive the prune."""
    for aim in aims[:2]:
        body = RK.SharedBody(prologue['run'], aim, l_window=LWS[0])
        walk = RK.camera_walks(body, grid)
        args = _full_args(prologue, aim, LWS[0], T.MAX_ROLL_FRAMES + 1)
        for tcs in grid:
            straight = _walk_full(prologue, body, args, tcs, body.branch)
            assert walk[tcs][1] == straight[-1], 'tree csangle differs at tcs %d' % tcs
        assert len({walk[t][2] for t in grid}) > 1, 'the grid never splits -- the tree is untested'


def test_the_tree_costs_less_than_the_straight_walk(prologue, aims, grid):
    """Counted rather than timed, so it does not move with machine load: the tree must actually
    share something, or it is complexity for nothing."""
    body = RK.SharedBody(prologue['run'], aims[2], l_window=LWS[0])
    walk = RK.camera_walks(body, grid)
    groups = len({walk[t][2] for t in grid})
    assert 1 < groups <= len(grid)
    assert body.branch * groups < body.branch * len(grid)


# --------------------------------------------------------------------------- the refusals

def test_a_talking_aim_has_no_shared_body(env, prologue, grid):
    """A cycle TERMINAL refuses its whole circle (s127, 143 of 143). The talk test does not read
    the C-stick, so it is a property of the aim and not of the camera target -- which is why the
    body can decide it once for the family. Gated on the fixture's terminals."""
    if not os.path.exists(FIXTURE):
        pytest.skip('roll-kernel seeds missing: %s' % FIXTURE)
    with open(FIXTURE) as fh:
        rec = json.load(fh)
    seen = 0
    for nd in rec['nodes']:
        if nd['kind'] != 'terminal':
            continue
        run = SD.make_freerun(env)
        run.pre_seed_input(SD.dtm_input_at(env)(0))
        for d in nd['log']:
            run.step(d)
        aim = T.roll_facing_fan(run, int(nd['csangle']), 0x2000, 64)[0][1]
        body = RK.SharedBody(run, aim, l_window=LWS[0])
        assert body.talk_unsafe and not body.ok
        for tcs in F.derived_target_css(run)[::8]:
            rr = run.clone()
            seg = T.roll_segment(rr, aim, target_cs=tcs, l_window=LWS[0])
            assert seg['talk_unsafe'], 'the wired path does not refuse this aim'
        seen += 1
    assert seen, 'no terminal seed in the fixture -- the refusal branch is untested'


def test_a_run_without_a_camera_has_no_shared_body(env, prologue):
    """The body reads `FreeRun.step`'s ``sim_cam_in``, which only a wired camera produces. A
    csangle-injected run must decline rather than raise deep inside the loop."""
    run = SD.make_freerun_native_look(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    body = RK.SharedBody(run, (149, 204), l_window=LWS[0])
    assert not body.ok
