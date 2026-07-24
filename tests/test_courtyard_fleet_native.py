"""CourtyardFleet OpenMP prange fan-out -- parallel == sequential, BIT-IDENTICAL (Stage 4).

Stage 4 of the courtyard native-step port (`_notes/native-courtyard-step-PROGRESS.md`): the whole
coupled Courtyard frame runs as a `noexcept nogil` core (`LandCore._step_courtyard_nogil`), and
`_anmc.CourtyardFleet` fans that core across the search frontier with OpenMP `prange` (GIL released).

Each branch's step is an independent deterministic C computation on its own C state (its own
`PoseEngine` clone; the keyframe `AnimData` is shared read-only), so parallelism CANNOT change any
result. Per the `[[zero-ulp-tests-only]]` hard rule this is asserted `_bits`-exactly, no tolerance:
a fleet of independent seeds/input-streams stepped by `run_par` (at several thread counts) must be
BIT-IDENTICAL, field by field, to the same fleet stepped by `run_seq`. A separate check ties the
fleet driver to the already-Python-0-ULP-gated path: a fleet core stepped through `run_seq` matches
an independent core driven by the public `step_courtyard` (which `tests/test_step_courtyard_native.py`
gates against the live-0-ULP `from_f0.FreeRun`)."""
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


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _sa(inp):
    if isinstance(inp, dict):
        return (int(inp['stickX']), int(inp['stickY']),
                int(inp.get('buttons', 0)), int(inp.get('triggerL', 0)))
    t = tuple(inp)
    return (int(t[0]), int(t[1]), int(t[2]) if len(t) > 2 else 0,
            int(t[3]) if len(t) > 3 else 0)


def _seed_push(perop):
    t0 = perop[0]['entry']['tetra']['pos']
    t1 = perop[1]['entry']['tetra']['pos']
    return (t1[0] - t0[0], t1[2] - t0[2])


@pytest.fixture(scope='module')
def env():
    for p in (_CYL, _DTM, _SEED, _PEROP):
        if not os.path.exists(p):
            pytest.skip("Courtyard capture fixtures not present (need a live slot-2 capture)")
    cyl = json.load(open(_CYL))['frames']
    dtm = json.load(open(_DTM))['frames']
    seed = json.load(open(_SEED))
    perop = json.load(open(_PEROP))['rows']
    return dict(cyl=cyl, dtm=dtm, seed=seed, perop=perop)


def _build_core(env):
    """A native courtyard LandCore seeded to the state-2 f0 anchor (== test_step_courtyard_native's
    `_build_native`), with its delay-1 input buffer pre-seeded from the DTM window's f0 input."""
    from harness.tetrapush.from_f0 import FreeRun
    from tww_sim.core.anim import _anmc as N
    from tww_sim.core.anim.anim_state import (ANIM_ORDER, NATIVE_META_MAX,
                                              NATIVE_META_ATTR, NATIVE_HIO)
    from tww_sim.land.state import _LAND_CONSTS
    run = FreeRun(env['cyl'][0], seed_nspeed=env['seed']['link']['nspeed'], computed_pose=True,
                  seed_old_pose=env['seed'].get('old_pose'), seed_push=_seed_push(env['perop']))
    run.pre_seed_input(env['dtm'][0]['inp'])
    link = run.link
    N.land_init_consts(_LAND_CONSTS)
    N.init_anim_consts(NATIVE_META_MAX, NATIVE_META_ATTR, NATIVE_HIO)
    code2idx = [link._foot.ff._anim_idx[name] for name in ANIM_ORDER]
    pe = link._foot.ff._pose_engine.clone_state()
    pe.seed_from_foot(link._foot, code2idx)
    core = N.LandCore()
    core.setup(pe, link.pos_x, link.pos_z, link.facing, link.travel, link.csangle,
               link.state, link.nspeed, link.speedF, float(link._cam.scale))
    core.seed_courtyard(pe, link.pos_y, link.m351C, int(link._atn.state), run.tx, run.tz,
                        run.pend_link[0], run.pend_link[1], run.pend_tetra[0], run.pend_tetra[1])
    core.pre_seed_courtyard(*_sa(env['dtm'][0]['inp']))
    return core


def _schedules(env, n, nframes):
    """One distinct deterministic input stream per fleet member: the DTM window's buttons/triggerL/
    csangle, with the stick perturbed by a per-core offset (clamped) so each branch diverges into a
    different trajectory -- the search frontier the fleet models. Frame f = (sx,sy,buttons,triggerL,
    csangle)."""
    cyl, dtm = env['cyl'], env['dtm']
    scheds = []
    for j in range(n):
        dx = (j % 7) - 3
        dy = ((j // 7) % 7) - 3
        row = []
        for f in range(nframes):
            k = 1 + (f % 43)                      # cycle the DTM window (f1..f43)
            sx, sy, btn, tr = _sa(dtm[k]['inp'])
            sx = max(0, min(255, sx + dx))
            sy = max(0, min(255, sy + dy))
            csang = int(cyl[k - 1]['csangle']) & 0xFFFF
            row.append((sx, sy, btn, tr, csang))
        scheds.append(row)
    return scheds


def _snapshot(core):
    return (_bits(core.pos_x), _bits(core.pos_z), int(core.facing), int(core.travel),
            _bits(core.speedF), int(core.state), _bits(core._tetra_x), _bits(core._tetra_z),
            int(core.court_shape_z))


_FIELDS = ('pos_x', 'pos_z', 'facing', 'travel', 'speedF', 'state', 'tetra_x', 'tetra_z', 'lean')


def _run_fleet(env, n, nframes, scheds, parallel, nthreads=0):
    """Build a fresh fleet (identical seeds), attach `scheds`, step it seq or par; return per-core
    field snapshots. Keeping the core list alive lets us read each core's final C state directly."""
    from tww_sim.core.anim import _anmc as N
    cores = [_build_core(env) for _ in range(n)]
    fleet = N.CourtyardFleet(cores, 1)             # native_push=1 (fully-native coupled loop)
    fleet.set_schedule(scheds)
    if parallel:
        fleet.run_par(nframes, nthreads)
    else:
        fleet.run_seq(nframes)
    return [_snapshot(c) for c in cores]


@pytest.mark.parametrize('nthreads', [1, 2, 4, 8, 10])
def test_fleet_par_equals_seq(env, nthreads):
    """`run_par` at each thread count is BIT-IDENTICAL, per core and per field, to `run_seq` over a
    fleet of independent seeds/input-streams. 0 ULP -- the OpenMP fan-out preserves the exact result
    because the branches share no mutable state (each core owns its PoseEngine; AnimData is read-only)."""
    n, nframes = 96, 60
    scheds = _schedules(env, n, nframes)
    seq = _run_fleet(env, n, nframes, scheds, parallel=False)
    par = _run_fleet(env, n, nframes, scheds, parallel=True, nthreads=nthreads)
    diverged = []
    for i in range(n):
        for fi, name in enumerate(_FIELDS):
            if seq[i][fi] != par[i][fi]:
                diverged.append("core%d %s seq=%r par(%dT)=%r"
                                % (i, name, seq[i][fi], nthreads, par[i][fi]))
    assert not diverged, "parallel fleet != sequential (0 ULP required): " + "; ".join(diverged[:20])


def test_fleet_seq_matches_direct_step_courtyard(env):
    """The fleet driver feeds inputs bit-exactly: a core stepped through `CourtyardFleet.run_seq`
    matches an independent core driven frame-by-frame through the public `step_courtyard` (native_push
    =1, eye=None) -- which `tests/test_step_courtyard_native.py` gates 0-ULP vs the live `FreeRun`.
    So fleet == step_courtyard == the Python oracle, transitively."""
    from tww_sim.core.anim import _anmc as N
    n, nframes = 8, 43
    scheds = _schedules(env, n, nframes)

    fleet_cores = [_build_core(env) for _ in range(n)]
    fleet = N.CourtyardFleet(fleet_cores, 1)
    fleet.set_schedule(scheds)
    fleet.run_seq(nframes)

    diverged = []
    for j in range(n):
        core = _build_core(env)
        for f in range(nframes):
            sx, sy, btn, tr, csang = scheds[j][f]
            core.step_courtyard(sx, sy, btn, tr, csang & 0xFFFF,
                                0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0, 1)
        a, b = _snapshot(fleet_cores[j]), _snapshot(core)
        for fi, name in enumerate(_FIELDS):
            if a[fi] != b[fi]:
                diverged.append("core%d %s fleet=%r direct=%r" % (j, name, a[fi], b[fi]))
    assert not diverged, "fleet run_seq != direct step_courtyard (0 ULP required): " \
        + "; ".join(diverged[:20])
