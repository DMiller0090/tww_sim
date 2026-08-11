"""FreeRun native-step mode (Stage 3) vs the Python FreeRun -- 0-ULP over the DTM window + clone.

Stage 3 of the courtyard native-step port (`_notes/native-courtyard-step-PROGRESS.md`): wire
`harness/tetrapush/from_f0.FreeRun(native_step=True)` to drive `LandCore.step_courtyard(native_push=1)`
directly (dropping the Python `LandState.step` + Python push for the search fast path), syncing the
public state the search reads (`run.link.pos_x/pos_z/facing/travel/speedF/state`, `run.tx/tz`).

Per `[[zero-ulp-tests-only]]` every field is asserted `_bits`-equal, no tolerance. Two gates:
  * `test_freerun_native_matches_python`: native-mode `FreeRun.step` == Python-mode `FreeRun.step`
    bit-for-bit on Link pos/facing/travel/speedF/proc + Tetra XZ over f1..f43, driven identically
    (same inputs + injected csangle). Run BOTH with an injected proc-9 eye (== the full computed
    oracle, the strongest gate: native FreeRun == core.step_courtyard == the live-0-ULP Python
    FreeRun), AND with eye=None (the STRIPPED search config -- feet-aim fallback -- native-stripped
    == python-stripped).
  * `test_freerun_native_clone_bit_identical`: a `FreeRun.clone()` of a native run, stepped with the
    SAME inputs as its parent, stays bit-identical (the beam search relies on clone)."""
import json
import os
import struct

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIX = os.path.join(_ROOT, 'fixtures')
_CYL = os.path.join(_FIX, 'courtyard_push_cyl.json')
_DTM = os.path.join(_FIX, 'courtyard_push_dtm.json')
_SEED = os.path.join(_FIX, 'courtyard_push_seed.json')
_PEROP = os.path.join(_FIX, 'courtyard_push_perop.json')
_EYES = os.path.join(_FIX, 'courtyard_push_eyepos.json')


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope='module')
def env():
    for p in (_CYL, _DTM, _SEED, _PEROP, _EYES):
        if not os.path.exists(p):
            pytest.skip("Courtyard capture fixtures not present (need a live slot-2 capture)")
    cyl = json.load(open(_CYL))['frames']
    dtm = json.load(open(_DTM))['frames']
    seed = json.load(open(_SEED))
    perop = json.load(open(_PEROP))['rows']
    eyes = [r['eye'] for r in json.load(open(_EYES))['frames']]
    return dict(cyl=cyl, dtm=dtm, seed=seed, perop=perop, eyes=eyes)


def _seed_push(perop):
    t0 = perop[0]['entry']['tetra']['pos']
    t1 = perop[1]['entry']['tetra']['pos']
    return (t1[0] - t0[0], t1[2] - t0[2])


def _mk_run(env, native):
    from harness.tetrapush.from_f0 import FreeRun
    run = FreeRun(env['cyl'][0], seed_nspeed=env['seed']['link']['nspeed'], computed_pose=True,
                  seed_old_pose=env['seed'].get('old_pose'), seed_push=_seed_push(env['perop']),
                  native_step=native)
    run.pre_seed_input(env['dtm'][0]['inp'])
    return run


def _drive(env, run, k, inject_eye):
    """One driven step at game-frame k on `run` (native or Python), injected csangle/eye as the
    existing Stage-1/2 gate does. Returns the row dict."""
    cyl, dtm, eyes = env['cyl'], env['dtm'], env['eyes']
    eye = (eyes[k - 1] if (inject_eye and k - 1 < len(eyes)) else None)
    csang = cyl[k - 1]['csangle']
    return run.step(dtm[k]['inp'], csangle=csang, eye=eye)


@pytest.mark.parametrize('inject_eye', [True, False],
                         ids=['eye-injected(full-oracle)', 'eye-none(stripped-search)'])
def test_freerun_native_matches_python(env, inject_eye):
    """f1..f43: native-mode FreeRun == Python-mode FreeRun bit-for-bit on Link pos_x/pos_z/facing/
    travel/speedF/proc + Tetra XZ. With `inject_eye` this is the full computed oracle (native FreeRun
    == the live-0-ULP Python FreeRun); with eye=None it is the stripped search config (feet-aim
    fallback), native-stripped == python-stripped."""
    py = _mk_run(env, native=False)
    nt = _mk_run(env, native=True)
    diverged = []
    for k in range(1, 44):
        rp = _drive(env, py, k, inject_eye)
        rn = _drive(env, nt, k, inject_eye)
        checks = (
            ('proc', rn['sim_proc'], rp['sim_proc']),
            ('facing', rn['sim_facing'], rp['sim_facing']),
            ('travel', nt.link.travel, py.link.travel),
            ('speedF', _bits(rn['speedF']), _bits(rp['speedF'])),
            ('pos_x', _bits(rn['sim_link'][0]), _bits(rp['sim_link'][0])),
            ('pos_z', _bits(rn['sim_link'][1]), _bits(rp['sim_link'][1])),
            ('tetra_x', _bits(nt.tx), _bits(py.tx)),
            ('tetra_z', _bits(nt.tz), _bits(py.tz)),
            # The roll's body lean: an allowlist can only catch a field that is ON it
            # (knowledge/strategy/the-lean-is-the-rolls-own-dispatch.md).
            ('m351C', nt.link.m351C, py.link.m351C),
            ('draw_lean', nt.link._draw_lean, py.link._draw_lean),
            # The cut + wall ports write these. Both are INERT over this window, which is the point:
            # listed, a port that leaks into the reference window is caught.
            ('cut_frame', _bits(nt.link.cut_frame), _bits(py.link.cut_frame)),
            ('cut_target', nt.link.cut_target, py.link.cut_target),
            ('wall_hit', nt.link.wall_hit, py.link.wall_hit),
            ('line_hit', nt.link.line_hit, py.link.line_hit),
            ('wall_cir_hit', tuple(nt.link.wall_cir_hit), tuple(py.link.wall_cir_hit)),
            ('wall_angle', tuple(nt.link.wall_angle), tuple(py.link.wall_angle)),
        )
        for name, a, b in checks:
            if a != b:
                diverged.append("f%d %s native=%r py=%r" % (k, name, a, b))
    assert not diverged, "native FreeRun != Python FreeRun (0 ULP required): " \
        + "; ".join(diverged[:20])


def test_freerun_native_clone_bit_identical(env):
    """A native FreeRun cloned mid-window and stepped with the SAME inputs as its parent stays
    bit-identical on Link pos/facing/travel/speedF/proc + Tetra XZ (the beam search relies on this)."""
    run = _mk_run(env, native=True)
    for k in range(1, 12):                         # advance a few cycles, then branch
        _drive(env, run, k, inject_eye=False)
    clone = run.clone()
    diverged = []
    for k in range(12, 44):
        rp = _drive(env, run, k, inject_eye=False)
        rc = _drive(env, clone, k, inject_eye=False)
        checks = (
            ('proc', rc['sim_proc'], rp['sim_proc']),
            ('facing', rc['sim_facing'], rp['sim_facing']),
            ('travel', clone.link.travel, run.link.travel),
            ('speedF', _bits(rc['speedF']), _bits(rp['speedF'])),
            ('pos_x', _bits(rc['sim_link'][0]), _bits(rp['sim_link'][0])),
            ('pos_z', _bits(rc['sim_link'][1]), _bits(rp['sim_link'][1])),
            ('tetra_x', _bits(clone.tx), _bits(run.tx)),
            ('tetra_z', _bits(clone.tz), _bits(run.tz)),
        )
        for name, a, b in checks:
            if a != b:
                diverged.append("f%d %s clone=%r parent=%r" % (k, name, a, b))
    assert not diverged, "cloned native FreeRun != parent (0 ULP required): " \
        + "; ".join(diverged[:20])


def test_native_and_python_agree_across_the_second_lock_cycle(env):
    """The DTM window above ends at f43, one frame INTO the first untarget brakeslide -- so it never
    exercised the second lock-on cycle, where session 57's RELEASE-gate fix lives. Replay node 1's
    locked 241-frame plan (the tier-2 gate's log) in both engines instead: it covers the second
    acquire/release around plan frames 55-70 and everything after it.

    Stripped config (no injected csangle/eye), so this is native-stripped == python-stripped, the
    property the beam search depends on. It would go red if only one of `attention.py` /
    `_anmc.pyx` ever got a lock-machine change again."""
    log = json.load(open(os.path.join(_FIX, 'courtyard_node1_console.json')))['log']
    py = _mk_run(env, native=False)
    nt = _mk_run(env, native=True)
    diverged = []
    for k, inp in enumerate(log):
        rp = py.step(inp)
        rn = nt.step(inp)
        checks = (
            ('proc', rn['sim_proc'], rp['sim_proc']),
            ('facing', rn['sim_facing'], rp['sim_facing']),
            ('speedF', _bits(rn['speedF']), _bits(rp['speedF'])),
            ('pos_x', _bits(rn['sim_link'][0]), _bits(rp['sim_link'][0])),
            ('pos_z', _bits(rn['sim_link'][1]), _bits(rp['sim_link'][1])),
            ('tetra_x', _bits(nt.tx), _bits(py.tx)),
            ('tetra_z', _bits(nt.tz), _bits(py.tz)),
        )
        for name, a, b in checks:
            if a != b:
                diverged.append("plan f%d %s native=%r py=%r" % (k + 1, name, a, b))
    assert not diverged, "native != Python over the node-1 plan (0 ULP required): " \
        + "; ".join(diverged[:20])
