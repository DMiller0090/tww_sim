"""Native LandCore.step_courtyard vs the Python from-f0 FreeRun -- 0-ULP over the DTM window.

Stage 1 of the courtyard native-step port (`_notes/native-courtyard-step-PROGRESS.md`): the whole
Courtyard per-frame PHYSICS -- the dAttention_c hold-mode lock machine, the actor-lock targeting
procs 8/9 (re-aim + DIR_BACKWARD negation), the locked-actor `checkNextMode`/`setBlendAtnMoveAnime`
gates, the A-roll trigger, and the posMove CC-push consume -- moved into `_anmc.LandCore`, with
speedF from the fused C `PoseEngine` seeded off the Python `FootSpeedF` (`PoseEngine.seed_from_foot`,
the seeding bridge). Per the `[[zero-ulp-tests-only]]` hard rule every field is asserted
`_bits == _bits` against the already-live-0-ULP Python oracle (`harness/tetrapush/from_f0.FreeRun`,
gated by `tests/test_from_f0.py`).

SCOPE (Stage 1): the coupled push is INJECTED per frame (the Python model's exec-centre CC push),
along with csangle, the Tetra feet, and the proc-9 eye -- exactly as the closed-loop oracle consumes
them. The native step reproduces proc / facing / travel / nspeed / speedF / pos_x / pos_z / lean AND
the native pose-engine speedF bit-for-bit. Closing the loop natively (the exec centre + cc_push +
Tetra track in C) is Stage 2; until then the injected push keeps the physics gate honest.
"""
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


def _sa(inp):
    """Raw controller dict/tuple -> (sx, sy, buttons, triggerL)."""
    if isinstance(inp, dict):
        return (int(inp['stickX']), int(inp['stickY']),
                int(inp.get('buttons', 0)), int(inp.get('triggerL', 0)))
    t = tuple(inp)
    return (int(t[0]), int(t[1]), int(t[2]) if len(t) > 2 else 0,
            int(t[3]) if len(t) > 3 else 0)


def _build_native(run):
    """Seed a native `LandCore.step_courtyard` engine to bit-match the Python `FreeRun` `run` at f0.
    Returns the LandCore. This is the seeding bridge Stage 3 will fold into FreeRun itself."""
    from tww_sim.core.anim import _anmc as N
    from tww_sim.core.anim.anim_state import (ANIM_ORDER, NATIVE_META_MAX,
                                              NATIVE_META_ATTR, NATIVE_HIO)
    from tww_sim.land.state import _LAND_CONSTS
    link = run.link
    N.land_init_consts(_LAND_CONSTS)
    N.init_anim_consts(NATIVE_META_MAX, NATIVE_META_ATTR, NATIVE_HIO)
    code2idx = [link._foot.ff._anim_idx[name] for name in ANIM_ORDER]
    pe = link._foot.ff._pose_engine.clone_state()   # fresh engine sharing the immutable AnimData
    pe.seed_from_foot(link._foot, code2idx)
    core = N.LandCore()
    core.setup(pe, link.pos_x, link.pos_z, link.facing, link.travel, link.csangle,
               link.state, link.nspeed, link.speedF, float(link._cam.scale))
    core.seed_courtyard(pe, link.pos_y, link.m351C, int(link._atn.state), run.tx, run.tz)
    return core


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


def test_step_courtyard_native_bit_exact(env):
    """The whole from-f0 window f1..f43: the native `LandCore.step_courtyard` reproduces the Python
    `FreeRun` (the closed-loop `centers='computed'` config) BIT-FOR-BIT on proc, facing, travel,
    nspeed, speedF, pos_x, pos_z, and the m351C lean -- and its returned native pose-engine speedF
    equals the Python speedF too (the seeding bridge is exact). The CC push, csangle, Tetra feet, and
    proc-9 eye are injected from the Python model (Stage 1; the native coupling is Stage 2)."""
    from harness.tetrapush.from_f0 import FreeRun
    cyl, dtm, seed, perop, eyes = (env['cyl'], env['dtm'], env['seed'],
                                   env['perop'], env['eyes'])
    run = FreeRun(cyl[0], seed_nspeed=seed['link']['nspeed'], computed_pose=True,
                  seed_old_pose=seed.get('old_pose'), seed_push=_seed_push(perop))
    run.pre_seed_input(dtm[0]['inp'])
    core = _build_native(run)
    core.pre_seed_courtyard(*_sa(dtm[0]['inp']))

    link = run.link
    diverged = []
    for k in range(1, 44):
        pend_link = run.pend_link          # incoming CC recoil for THIS frame (posMove consume)
        tx, tz = run.tx, run.tz            # Tetra feet: cone gate + proc-9 fallback + tracked point
        eye = eyes[k - 1] if k - 1 < len(eyes) else None
        csang = cyl[k - 1]['csangle']
        inp = dtm[k]['inp']
        # Python oracle step (already live-0-ULP; see tests/test_from_f0.py)
        row = run.step(inp, csangle=csang, eye=eye)
        # native step: identical injected push / csangle / Tetra feet / eye
        isx, isy, ibtn, itr = _sa(inp)
        ex, ez = (eye[0], eye[-1]) if eye is not None else (0.0, 0.0)
        sfn = core.step_courtyard(isx, isy, ibtn, itr, int(csang) & 0xFFFF,
                                  float(tx), float(tz), float(ex), float(ez),
                                  1 if eye is not None else 0,
                                  float(pend_link[0]), float(pend_link[1]),
                                  0.0, 0)          # native speedF drives position (no inject)
        checks = (
            ('proc', int(core.state), int(row['sim_proc'])),
            ('facing', int(core.facing), int(row['sim_facing'])),
            ('travel', int(core.travel), int(link.travel)),
            ('nspeed', _bits(core.nspeed), _bits(link.nspeed)),
            ('speedF', _bits(core.speedF), _bits(row['speedF'])),
            ('speedF_native', _bits(sfn), _bits(row['speedF'])),
            ('pos_x', _bits(core.pos_x), _bits(row['sim_link'][0])),
            ('pos_z', _bits(core.pos_z), _bits(row['sim_link'][1])),
            ('lean', int(core.court_shape_z), int(row['sim_shape_z'])),
        )
        for name, a, b in checks:
            if a != b:
                diverged.append("f%d %s native=%r py=%r" % (k, name, a, b))
    assert not diverged, "native step_courtyard != Python FreeRun (0 ULP required): " \
        + "; ".join(diverged[:20])
