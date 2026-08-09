"""**The gate for the herd-roll fan kernel** (session 127) -- written BEFORE the port, and failing.

The perf work's whole risk is stated in one sentence in the s126 handoff: *a port that changes which
endpoints exist is not a speedup.* A roll kernel that reproduces a trajectory but drops the exit
csangle looks 0-ULP on one roll and corrupts every chain of two, because the next junction's aim
alphabet is placed against that value; one that drops `talk_unsafe` plans an A-press that talks to
Tetra and kills the run; one that drops `ok`/`roll_speedF` silently changes which aims arm at all.

So the contract gated here is the WHOLE record, not the endpoint: every field `two_roll.roll_segment`
returns plus the Link/Tetra state the search reads off the run afterwards, compared with `==` and
never a tolerance (`[[zero-ulp-tests-only]]`).

Seeds are real: `fixtures/courtyard_roll_kernel_nodes.json` holds four `junction_beam` endpoints off a
banked cycle-2 node and two cycle TERMINALS, each as its delivered input log (a node IS its log --
`beam_io`). Both kinds are needed and they are not interchangeable: at a junction endpoint Link has
turned away and the whole fan is talk-SAFE, while at a terminal he ends facing her at contact range and
the whole circle TALKS (measured 143/143), which is the only place the refusal branch can be gated.
"""
import json
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import roll_kernel as RK                # noqa: E402
from harness.tetrapush import seeds as SD                      # noqa: E402
from harness.tetrapush import two_roll as T                    # noqa: E402

FIXTURE = os.path.join(_REPO, 'fixtures', 'courtyard_roll_kernel_nodes.json')

#: (l_window, target_cs offset from the node's own csangle). None = `extend_cycle`'s SCREEN pass
#: (where the aim fan is cut); the slews are its second pass, which chooses the camera target.
CONFIGS = [((5, 8), None), ((5, 8), 1536), ((4, 9), -1536), ((6, 8), None)]


def _env():
    return SD.load_env()


def _fixture():
    if not os.path.exists(FIXTURE):
        pytest.skip('roll-kernel seeds missing: %s' % FIXTURE)
    with open(FIXTURE) as fh:
        return json.load(fh)


def _rebuild(env, nd):
    """A seed node, rebuilt from its input log on a fresh wired `FreeRun` -- the search's own node."""
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for d in nd['log']:
        run.step(d)
    assert int(run.csangle) == int(nd['csangle']), 'seed rebuilt to a different camera'
    return run


@pytest.fixture(scope='module')
def nodes():
    env = _env()
    rec = _fixture()
    return env, rec, [_rebuild(env, nd) for nd in rec['nodes']]


@pytest.fixture(scope='module', params=[True, False], ids=['native_look', 'python_look'])
def twins(request, nodes):
    """One twin per seed, built from the node's log + its wired camera trace.

    Parameterized over BOTH engines on purpose: `native_look` (session 128) runs her look model and
    Link's neck inside the C step at 6.8x, and the claim that it is the same simulation should be
    gated where it is used -- against `two_roll.roll_segment` on the whole record -- and not only in
    its own unit gate."""
    env, rec, runs = nodes
    out = []
    for nd in rec['nodes']:
        cs = RK.wired_csangle_trace(env, nd['log'])
        out.append(RK.self_eye_twin(env, nd['log'], cs, native_look=request.param))
    return out


def _state(run):
    return (run.link.pos_x, run.link.pos_z, int(run.link.facing), int(run.link.travel),
            run.link.speedF, int(run.link.state), run.tx, run.tz)


def test_the_twin_is_the_node(nodes, twins):
    """**Before any fan runs off it.** A self-eye twin carries no camera, so it is driven by an
    injected trace, and an off-by-one there is silent -- the run still looks like a run. Gate it at
    the seed instead of discovering it as a mismatched endpoint 20 frames later."""
    _env_, _rec, runs = nodes
    for run, fast in zip(runs, twins):
        assert _state(fast) == _state(run)


# ------------------------------------------------------------------ the seeds are what they claim

def test_the_seeds_carry_both_branches(nodes):
    """A junction endpoint's fan is talk-safe and a terminal's is not -- if that ever flips, the gate
    below stops testing the branch it thinks it tests."""
    _env_, rec, runs = nodes
    kinds = {}
    for nd, run in zip(rec['nodes'], runs):
        kinds.setdefault(nd['kind'], []).append((nd, run))
    assert set(kinds) == {'junction', 'terminal'}
    for nd, run in kinds['junction']:
        assert nd['aims_safe'] and not nd['aims_unsafe']
        assert RK.talk_screen(run, [a for _w, a in nd['aims_safe']]) == \
            [False] * len(nd['aims_safe'])
    for nd, run in kinds['terminal']:
        assert nd['aims_unsafe'] and not nd['aims_safe']
        assert RK.talk_screen(run, [a for _w, a in nd['aims_unsafe']]) == \
            [True] * len(nd['aims_unsafe'])


def test_the_refusal_record_is_the_segments_own(nodes):
    """`roll_segment` returns without stepping when the A-press talks; `refused_record` must be that
    record exactly, since the kernel returns it instead of running physics."""
    _env_, rec, runs = nodes
    for nd, run in zip(rec['nodes'], runs):
        if nd['kind'] != 'terminal':
            continue
        aims = [a for _w, a in nd['aims_unsafe']]
        assert RK.reference_fan(run, aims) == [RK.refused_record(run)] * len(aims)


# ------------------------------------------------------- the invariance the fan API is built on

def test_the_camera_through_a_roll_is_a_node_property_not_an_aim_one(nodes):
    """**The economy, gated at its root.** The fan pays for ONE camera because the csangle sequence a
    roll segment commits does not depend on the aim -- bit-identical across the fan, at every C-stick
    mode. If this ever fails, `roll_fan` is not merely slow, it is wrong, and this names why rather
    than leaving a mismatched endpoint to be re-derived."""
    _env_, rec, runs = nodes
    for nd, run in zip(rec['nodes'], runs):
        if nd['kind'] != 'junction':
            continue
        aims = [a for _w, a in nd['aims_safe']]
        for lw, off in CONFIGS:
            tcs = None if off is None else (int(nd['csangle']) + off) & 0xFFFF
            ref = RK.camera_trace(run, aims[0], l_window=lw, target_cs=tcs)['csangle']
            for aim in aims[1:]:
                got = RK.camera_trace(run, aim, l_window=lw, target_cs=tcs)['csangle']
                assert got == ref, ('csangle depends on the aim at l_window=%s target_cs=%s'
                                    % (lw, tcs))


def test_the_camera_target_does_move_the_camera(nodes):
    """The other half of that claim, and the reason it is a lever rather than a dead camera: the
    C-stick target DOES change the sequence. A trace shared across a fan is only legitimate because
    the aim is inert, not because nothing moves it."""
    _env_, rec, runs = nodes
    nd, run = next((nd, r) for nd, r in zip(rec['nodes'], runs) if nd['kind'] == 'junction')
    aim = nd['aims_safe'][0][1]
    base = RK.camera_trace(run, aim, target_cs=None)['csangle']
    moved = [RK.camera_trace(run, aim, target_cs=(int(nd['csangle']) + off) & 0xFFFF)['csangle']
             for off in (1536, -1536, 6000)]
    assert any(m != base for m in moved), 'no C-stick target moved csangle -- the camera is inert'


# ---------------------------------------------------------------------------- the kernel itself

@pytest.mark.parametrize('ci', range(len(CONFIGS)))
def test_the_kernel_fan_is_the_reference_fan_bit_for_bit(nodes, twins, ci):
    """**The gate.** Every field of every record, every aim, every seed -- `==`, not approximately.

    Parametrised per config so a failure names the l_window/camera-target it happened at instead of
    stopping at the first one."""
    _env_, rec, runs = nodes
    lw, off = CONFIGS[ci]
    for nd, run, fast in zip(rec['nodes'], runs, twins):
        aims = [a for _w, a in nd['aims_safe'] + nd['aims_unsafe']]
        tcs = None if off is None else (int(nd['csangle']) + off) & 0xFFFF
        ref = RK.reference_fan(run, aims, l_window=lw, target_cs=tcs)
        got = RK.roll_fan(run, aims, l_window=lw, target_cs=tcs, fast=fast)
        assert len(got) == len(ref)
        for i, (a, b) in enumerate(zip(ref, got)):
            assert a == b, ('aim %s (%d of %d) diverges at l_window=%s target_cs=%s:\n  ref %r\n'
                            '  got %r' % (aims[i], i, len(aims), lw, tcs, a, b))


def test_the_pruning_fields_are_actually_exercised(nodes, twins):
    """A record field only counts as gated if the seeds produce BOTH values of it. `talk_unsafe` and
    `followed` are prune inputs (`two_roll.alive` reads the second through `metrics`), so check the
    fan actually contains rolls on each side rather than trusting an equality over a constant."""
    _env_, rec, runs = nodes
    seen = {'talk_unsafe': set(), 'followed': set(), 'ok': set()}
    for nd, run, fast in zip(rec['nodes'], runs, twins):
        aims = [a for _w, a in nd['aims_safe'] + nd['aims_unsafe']]
        for r in RK.roll_fan(run, aims, fast=fast):
            for key in seen:
                seen[key].add(bool(r[key]))
    for key, vals in seen.items():
        assert vals == {True, False}, '%s is %s across every seed -- the field is untested' % (
            key, vals)


def test_the_kernel_leaves_its_seeds_untouched(nodes, twins):
    """A fan is evaluated off ONE node and every record must come from that node's state -- a kernel
    that steps a seed instead of a clone reads the first aim's endpoint as the second's, which is the
    kind of bug a per-record comparison passes and a chain does not. Both seeds are checked: the
    wired node (the talk screen and the camera trace touch it) and the twin (the fan clones it)."""
    _env_, rec, runs = nodes
    i = next(i for i, nd in enumerate(rec['nodes']) if nd['kind'] == 'junction')
    nd, run, fast = rec['nodes'][i], runs[i], twins[i]
    aims = [a for _w, a in nd['aims_safe']]
    before = (_state(run), int(run.csangle), _state(fast), int(fast.csangle))
    RK.roll_fan(run, aims, fast=fast)
    assert (_state(run), int(run.csangle), _state(fast), int(fast.csangle)) == before


def test_the_fan_order_is_the_aim_order(nodes, twins):
    """Records come back keyed by position, so a kernel that groups aims internally (by talk screen,
    by segment length, by anything) still owes the caller the original order."""
    _env_, rec, runs = nodes
    i = next(i for i, nd in enumerate(rec['nodes']) if nd['kind'] == 'junction')
    nd, run, fast = rec['nodes'][i], runs[i], twins[i]
    aims = [a for _w, a in nd['aims_safe']]
    full = RK.roll_fan(run, aims, fast=fast)
    rev = RK.roll_fan(run, aims[::-1], fast=fast)
    assert rev == full[::-1]


def test_a_fan_with_no_live_aim_needs_no_camera(nodes, twins):
    """A cycle terminal's whole circle talks, so there is no aim to trace the camera with. The fan
    must return the refusals rather than trace off an aim that never fires."""
    _env_, rec, runs = nodes
    i = next(i for i, nd in enumerate(rec['nodes']) if nd['kind'] == 'terminal')
    nd, run, fast = rec['nodes'][i], runs[i], twins[i]
    aims = [a for _w, a in nd['aims_unsafe']]
    assert RK.roll_fan(run, aims, fast=fast) == [RK.refused_record(run)] * len(aims)


def test_the_slow_path_is_not_a_silent_fallback(nodes):
    """Without a twin the kernel refuses. A kernel that quietly ran the reference instead would be
    the reference sometimes and the port other times, which is exactly the failure the gate exists
    to prevent."""
    _env_, rec, runs = nodes
    i = next(i for i, nd in enumerate(rec['nodes']) if nd['kind'] == 'junction')
    with pytest.raises(ValueError):
        RK.roll_fan(runs[i], [a for _w, a in rec['nodes'][i]['aims_safe']])
