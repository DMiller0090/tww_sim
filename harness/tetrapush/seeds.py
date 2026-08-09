# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""The planner's SEED FACTORY -- build the fully self-contained `FreeRun` (camera + Zl1 look +
NeckLook wired, no per-frame injections) from the locked courtyard fixtures, exactly as the
session-21 gates do (`tests/test_neck_look.py::_neck_rows`), plus the target-set loader
(`_generated/tetra_placements.tsv`) and the DTM input accessor.

Everything here is fixture plumbing, no model content: the forward model is `from_f0.FreeRun`
(every 0-ULP gate on `replay` gates it), the targets are Dereck's 288 genuine coords. The one
seed-shape liberty is `make_freerun(tetra_at=)` -- re-seat Tetra's SEED position (she is a bare
stt-3 XZ plow point; her look model only feeds eyePos/tattn) for clean no-contact template
rollouts (primitives.py). Link's seed is never altered (the pose/nspeed seeds are state-2 truth).
"""
import json
import os

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fx(name):
    return os.path.join(_REPO, 'fixtures', name)


def load_env():
    """Load the locked fixture set the self-contained replay consumes. Returns a dict:
    ``cyl`` (capture frames), ``dtm`` (raw input frames), ``seed`` (state-2 hidden seed),
    ``cam`` (camera oracle), ``look`` (Zl1 look f0 row source), ``m3564`` (NeckLook f0 source),
    ``perop`` (the deterministic per-op capture -- its f0/f1 supply the exact f0->f1 seed push).
    Raises FileNotFoundError with the missing path (the planner needs all of them)."""
    out = {}
    for key, name in (('cyl', 'courtyard_push_cyl.json'), ('dtm', 'courtyard_push_dtm.json'),
                      ('seed', 'courtyard_push_seed.json'), ('cam', 'courtyard_cam_oracle.json'),
                      ('look', 'courtyard_zl1look.json'), ('m3564', 'courtyard_m3564.json'),
                      ('perop', 'courtyard_push_perop.json')):
        p = _fx(name)
        if not os.path.exists(p):
            raise FileNotFoundError("planner fixture missing: %s" % p)
        out[key] = json.load(open(p))
    out['cyl'] = out['cyl']['frames']
    out['dtm'] = out['dtm']['frames']
    out['look'] = out['look']['frames']
    out['perop'] = out['perop']['rows']
    return out


def seed_push_f0(env):
    """The exact DETERMINISTIC f0->f1 Tetra CC push ``(dx, dz)`` for the state-2 seed, from the
    per-op capture: ``ΔTetra = tetra[f1] - tetra[f0]``. Tetra is stt-3 / speedF 0 the whole
    window, so her whole f0->f1 move IS the CC push -- and ``f0 + ΔTetra == f1`` bit-for-bit, so
    this makes `FreeRun`'s seed frame 0-ULP (session 29). It is input-independent (f0 is the fixed
    state-2 seed), so one datum serves every planner sequence. See `from_f0.FreeRun` ``seed_push``."""
    p = env['perop']
    t0 = p[0]['entry']['tetra']['pos']
    t1 = p[1]['entry']['tetra']['pos']
    return (t1[0] - t0[0], t1[2] - t0[2])


def dtm_input_at(env):
    """``input_at(k)`` for the recorded movie window (f0..f45 delivered; f46+ of the fixture is
    the free-run hold)."""
    frames = env['dtm']
    return lambda k: frames[k]['inp']


def make_freerun(env, tetra_at=None):
    """Build the fully self-contained `FreeRun` at the state-2 f0 seed: computed centres, wired
    `LandCamera` (seeded from the oracle block), wired `Zl1Look` (look-fixture f0), wired
    `NeckLook` (m3564-fixture f0) -- the exact session-21 gate configuration. The caller must
    `pre_seed_input` before stepping (delay-1 buffer).

    ``tetra_at`` -- optional (x, z): re-seat Tetra's seed position (clean-rollout mode for
    template extraction; her plow point AND her look model's position both move so the look
    dynamics stay self-consistent). Default = the true state-2 position."""
    from harness.tetrapush.from_f0 import FreeRun
    from tww_sim.core.camera.land_cam import LandCamera, seed_from_block
    from tww_sim.core.npc_zl1_look import Zl1Look
    from tww_sim.land.neck_look import NeckLook

    seed_row = env['cyl'][0]
    if tetra_at is not None:
        seed_row = json.loads(json.dumps(seed_row))          # deep copy, fixture stays locked
        seed_row['tetra']['pos'][0] = float(tetra_at[0])
        seed_row['tetra']['pos'][2] = float(tetra_at[-1])

    cam = seed_from_block(LandCamera(), bytes.fromhex(env['cam']['seed_cam_raw']))
    look0 = env['look'][0]
    if tetra_at is not None:
        look0 = json.loads(json.dumps(look0))
        dx = float(tetra_at[0]) - env['cyl'][0]['tetra']['pos'][0]
        dz = float(tetra_at[-1]) - env['cyl'][0]['tetra']['pos'][2]
        # translate every world-anchored field of her look seed with her (rigid re-seat)
        for key in ('pos', 'eye', 'tattn', 'f74c', 'f758'):
            if key in look0:
                look0[key] = [look0[key][0] + dx, look0[key][1], look0[key][2] + dz]
    zl1 = Zl1Look.seed_from_row(look0)
    m0 = env['m3564']['frames'][0]['m3564'] if 'frames' in env['m3564'] else env['m3564'][0]['m3564']
    neck = NeckLook(x=m0[0], y=m0[1], z=m0[2])
    seed = env['seed']
    # The exact f0->f1 seed push (perop ΔTetra) -> 0-ULP seed frame; None when Tetra is re-seated
    # (`tetra_at`, the recorded push no longer applies) -> FreeRun's settled-centre fallback.
    seed_push = None if tetra_at is not None else seed_push_f0(env)
    return FreeRun(seed_row, seed_nspeed=seed['link']['nspeed'],
                   seed_old_pose=seed.get('old_pose'), computed_pose=True,
                   camera=cam, zl1=zl1, neck=neck, seed_push=seed_push)


def make_freerun_native(env, tetra_at=None):
    """The STRIPPED native-step `FreeRun` -- the search fast path: the whole coupled courtyard frame
    runs in C (`LandCore.step_courtyard`, native_push=1) instead of the Python `LandState.step`, at
    ~8x the Python step (Stage 3). NO wired camera/zl1/neck (the stripped geometry-exact config): the
    caller injects csangle per `step` (or holds it) and the proc-9 eye falls back to Tetra's feet --
    identical positions to a stripped Python `FreeRun` (gated `tests/test_freerun_native.py`, 0-ULP on
    Link pos/facing/travel/speedF/proc + Tetra XZ over the DTM window, incl. a cloned run). Same f0
    seed + seed-push as `make_freerun`; `tetra_at` re-seats Tetra's plow point as there.

    NOTE the perf limiter (Stage 3 bench, this hardware): the native step is ~108k steps/s (vs the
    Python ~10.5k), pose-FK-bound (the bare native walk step is ~137k/s here) -- an 8x search win, not
    the ~1M/s the state-space brute force wants; that needs a per-frame pose-FK rework (phase caching /
    sampling only the needed joints / a nogil OpenMP `prange` fan-out over the BFS frontier), which is
    beyond wiring FreeRun. See `_notes/native-courtyard-step-PROGRESS.md` `## Stage 3 result`."""
    from harness.tetrapush.from_f0 import FreeRun

    seed_row = env['cyl'][0]
    if tetra_at is not None:
        seed_row = json.loads(json.dumps(seed_row))          # deep copy, fixture stays locked
        seed_row['tetra']['pos'][0] = float(tetra_at[0])
        seed_row['tetra']['pos'][2] = float(tetra_at[-1])
    seed = env['seed']
    seed_push = None if tetra_at is not None else seed_push_f0(env)
    return FreeRun(seed_row, seed_nspeed=seed['link']['nspeed'],
                   seed_old_pose=seed.get('old_pose'), computed_pose=True,
                   seed_push=seed_push, native_step=True)


def make_freerun_native_look(env, tetra_at=None):
    """**The whole coupled frame in C** (session 128) -- `make_freerun_self_eye` with her look model
    and Link's neck moved INSIDE the native step instead of driven from Python beside it.

    s127 left those two in Python because they are what generates the proc-9 re-aim eye. Measured at
    the start of s128 they were **91% of the coupled step** (her 77.5%, the neck 13.4%, the C core
    itself 9.1%) -- the entire remaining win, and the reason nothing else in the frame was worth
    porting.

    Identical answer, and that is gated rather than asserted: `tests/test_native_zl1_look.py` diffs
    this run against the self-eye one frame by frame -- physics, the eye, m3564, and her whole hidden
    state including the morf's per-joint old-pose store -- over the recorded window AND over a long
    one that actually fires her look-around anim. Same seed path (it IS `make_freerun_self_eye`, one
    flag on), same csangle injection, same clone semantics. `self.zl1` stays the SEED object; the
    live state is read through `_eye_next` / `neck` / `zl1_snapshot()`."""
    return make_freerun_self_eye(env, tetra_at=tetra_at, native_look=True)


def make_freerun_self_eye(env, tetra_at=None, native_look=False):
    """**The search's fast coupled run** (session 127): the native C step with her look model and
    Link's neck WIRED, so the run generates its own proc-9 re-aim eye instead of being handed one.

    The difference from `make_freerun_native` is what it costs to be faithful. The stripped native run
    falls the eye back to Tetra's FEET, which moves the re-aim 180 BAM and a banked node log by 123 u
    -- it is not the wired run. This one is, 0-ULP on Link, Tetra, the eye and m3564
    (`tests/test_freerun_self_eye.py`), because `LandCore.head_top_exec`/`head_mtx_exec` hand the two
    models the pose values that used to need the Python FK.

    The ONE thing it does not carry is the camera: `csangle` is injected per `step`. That is a feature
    for the roll fan -- through a roll the csangle sequence is a per-node constant, so a fan of aims
    pays for one camera -- and the caller's problem everywhere else.

    ``native_look`` moves the two look models INTO the C frame as well; see
    `make_freerun_native_look`, which is this with the flag on."""
    from harness.tetrapush.from_f0 import FreeRun
    from tww_sim.core.npc_zl1_look import Zl1Look
    from tww_sim.land.neck_look import NeckLook

    seed_row = env['cyl'][0]
    look0 = env['look'][0]
    if tetra_at is not None:
        seed_row = json.loads(json.dumps(seed_row))          # deep copy, fixture stays locked
        seed_row['tetra']['pos'][0] = float(tetra_at[0])
        seed_row['tetra']['pos'][2] = float(tetra_at[-1])
        look0 = json.loads(json.dumps(look0))
        dx = float(tetra_at[0]) - env['cyl'][0]['tetra']['pos'][0]
        dz = float(tetra_at[-1]) - env['cyl'][0]['tetra']['pos'][2]
        for key in ('pos', 'eye', 'tattn', 'f74c', 'f758'):
            if key in look0:
                look0[key] = [look0[key][0] + dx, look0[key][1], look0[key][2] + dz]
    m0 = env['m3564']['frames'][0]['m3564'] if 'frames' in env['m3564'] else env['m3564'][0]['m3564']
    seed = env['seed']
    seed_push = None if tetra_at is not None else seed_push_f0(env)
    return FreeRun(seed_row, seed_nspeed=seed['link']['nspeed'],
                   seed_old_pose=seed.get('old_pose'), computed_pose=True,
                   zl1=Zl1Look.seed_from_row(look0),
                   neck=NeckLook(x=m0[0], y=m0[1], z=m0[2]),
                   seed_push=seed_push, native_step=True, native_look=native_look)


def load_placements(path=None):
    """The 288 genuine Tetra clip coords (`_generated/tetra_placements.tsv`, Dereck 2026-07-21)
    as a list of dicts: ``idx``, ``x``, ``z``, ``dist_wallB``, ``dist_wallA``. The header carries
    the SETUP the list is valid for -- returned as ``(rows, header_lines)``."""
    if path is None:
        path = os.path.join(_REPO, '_generated', 'tetra_placements.tsv')
    rows, header = [], []
    with open(path) as f:
        cols = None
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('#'):
                header.append(ln)
                continue
            parts = ln.split('\t')
            if cols is None:
                cols = parts
                continue
            d = dict(zip(cols, parts))
            rows.append(dict(idx=int(d['idx']), x=float(d['tetra_x']), z=float(d['tetra_z']),
                             dist_wallB=float(d['dist_wallB']), dist_wallA=float(d['dist_wallA'])))
    return rows, header


# The final-approach SETUP the placement list is valid for (the tsv header, parsed once here so
# the planner constraints reference named values, not magic re-parses).
ENTRY_LINK_START = (-1531.94677734375, -787.6950073242188)
ENTRY_ROLL_POS = (-1516.116455078125, -765.1473999023438)
ENTRY_ROLL_FACING = 40835
