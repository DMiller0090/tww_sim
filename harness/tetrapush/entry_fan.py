"""THE ENTRY SEARCH'S FAN, ON THE NATIVE FLEET (session 81).

`entry_search.walk_fan` is the reference: clone the wired Python `FreeRun` at a base node, hold one
stick for j frames, keep every distinct ``(walk endpoint, m351C)`` that is still at the speedF 17 cap
and inside the 230 u follow bar. It is also the whole search budget -- 43596 candidates cost 1444 s
of fan against 11 s of eval (session 80), at ~3.5k Python steps/s. `CourtyardFleet.run_par` steps the
same coupled frame in C at ~1M steps/s, so this module moves the fan there.

WHY IT NEEDS A GRAFT (measured, `_notes/s81_native_probe.py`). The fleet only drives the STRIPPED
config (`seeds.make_freerun_native`: no wired camera / zl1 look / neck, csangle injected), and that
config does NOT reproduce the WIRED replay of the console log -- it diverges at log frame 19 on
`facing`, because the proc-9 re-aim falls back to Tetra's FEET where the wired run has her modeled
eyePos. So the fan cannot be run natively from f0: the base state must come from the wired Python
replay and be TRANSPLANTED into a `LandCore`.

`FreeRun._build_core` already builds a core from a Python `LandState`, but `LandCore.setup` resets
the mid-walk physics scalars (`m34dc`/`target`/`msd`/`direction`/`roll_frame`/`_l_prev` -> facing or
0), which is right for the f0 seed and wrong here. Everything it drops is a `cdef public` field, so
`graft` restores it with plain setters -- no pyx change. The three private ones it CANNOT reach are
inert at this base by measurement, and each is gated: the attention machine's fade timer and its own
prev-L (the lock reads NONE and the fan's held input has buttons 0 / triggerL 0, so no L edge ever
fires), and the C-up subjectivity counters (never armed). The camera privates (`_cam_yaw` and
friends) are walk-step-only -- `step_courtyard` writes `csangle` from the injection every frame.

The graft's licence is the FAN EQUALITY GATE, not the argument above: `fleet_fan` must reproduce
`entry_search.walk_fan` as a dict, key AND value, bit-for-bit (`tests/test_entry_fan.py`, and at full
resolution against the cached s80 pass `_generated/s80/fan_s1_j12_b7.json`). Write order is therefore
part of the contract -- the reference collapses ~5.5M writes onto 43596 keys and the LAST writer wins,
so this module buffers each core's hits and applies them stick-major / j-inner exactly as the
reference loop does.

WHAT THE THROUGHPUT BUYS. One-segment holds are EXHAUSTED: stride 1 IS every stick byte pair, 7 base
frames saturate, and jmax past 12 adds nothing. The lever the fan can still be widened by is a SECOND
SEGMENT -- hold S1 for j1 frames, then S2 for j2 -- which `fleet_fan2` runs by keeping the junction
cores of the first segment alive and re-fanning each one. See `knowledge/strategy/clip-entry-search.md`.

    python -m harness.tetrapush.entry_fan gate            # the fan-equality gate vs the cached pass
    python -m harness.tetrapush.entry_fan fan [stride jmax nbase]
    python -m harness.tetrapush.entry_fan fan2 [s1_stride j1 s2_stride j2max]
    python -m harness.tetrapush.entry_fan search1 [jmax nbase stride [uncapped]]
    python -m harness.tetrapush.entry_fan search2 [s1_stride j1 s2_stride j2max nbase]
    python -m harness.tetrapush.entry_fan confirm <hits json | tag>   # the A-press replay
"""
import json
import math
import os
import struct
import sys
import time
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.core.anim import _anmc as N
from tww_sim.land.plan_land._primitives import main_stick_decode
from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_search as ES
from harness.tetrapush import seeds as SD
from harness.tetrapush.from_f0 import _step_args

#: The mid-walk physics scalars `LandCore.setup` resets and the graft must restore. All `cdef public`
#: on the core and identically named on `LandState`, so the copy is a name-for-name loop.
CARRY = ('m34E6', 'm34dc', 'm34ea', 'm34de', 'target', 'turn_target', 'turn_shape_scale',
         'turn_shape_max', 'turn_shape_min', 'direction', 'msd', 'max_nspeed', 'roll_frame',
         '_roll_entered', '_l_prev', '_subj_arm', '_subj_ended')

#: Cores per fleet batch. Each carries its own `PoseEngine` state-copy, so this bounds the live
#: memory; the step is ~1M/s either way (OpenMP `prange` over a static schedule).
CHUNK = 8192

FAN_CACHE = os.path.join(_rb, '_generated', 's80', 'fan_s1_j12_b7.json')


# ------------------------------------------------------------------- the graft

def graft(run):
    """A native `LandCore` at a WIRED Python `FreeRun`'s current MID-WALK coupled state.

    `run._build_core()` does the pose half (a `clone_state` engine + `seed_from_foot`, both mid-walk
    faithful) and the courtyard half (pos_y, the m351C lean, the AttentionLock state, Tetra's feet,
    the CC push pair); this adds the physics scalars `setup` zeroed and the delay-1 controller
    buffer, which at ``input_delay=1`` is the single pending `_inbuf` entry.

    Gated 0-ULP against the wired Python run it is grafted from (`tests/test_entry_fan.py`)."""
    core = run._build_core()
    lk = run.link
    for name in CARRY:
        setattr(core, name, getattr(lk, name))
    core.pre_seed_courtyard(*_step_args(lk._inbuf[0])[:4])
    return core


def base_core(n0, seed=None, env=None, hold=None):
    """The fan's base state for ``n0`` extra held frames, as a native core: replay the
    console-confirmed log on the wired Python run, hold ``n0`` frames, graft. Returns
    ``(core, run)`` -- the run is kept so a caller can diff against the Python reference."""
    seed = seed or ES.console_seed()
    hold = hold or dict(seed['log'][-1], buttons=0)
    run, _ = ES.continue_walk([hold] * n0, env=env)
    return graft(run), run


def stick_grid(stride):
    """The fan's stick alphabet, in the reference's own iteration order (sx outer, sy inner)."""
    return [(sx, sy) for sx in range(0, 256, stride) for sy in range(0, 256, stride)]


def _decoded(sx, sy):
    """What the physics actually reads from a held byte pair: ``(mMainStickAngle, mStickDistance)``,
    the magnitude at its exact f32 bits so the key is an equality and never a tolerance."""
    a, m = main_stick_decode(sx, sy)
    return (a if a is None else int(a) & 0xFFFF, struct.pack('<f', float(m)))


def stick_alphabet(stride=1):
    """The byte grid COLLAPSED onto what the physics reads -- the same trap `clip-lottery-draws.md`
    documents for aims, applied to the fan's own held stick (session 84).

    A held stick reaches the walk through `main_stick_decode` alone, so two byte pairs with the same
    ``(angle, msd)`` bake a bit-identical walk: same endpoint, same lean, same speedF, forever
    (gated, `tests/test_entry_fan.py`). The octagon clamp and the dead zone make that common rather
    than rare -- the full stride-1 grid is 65536 byte pairs and **11405 draws**, one class holding
    1944 members -- so a fan enumerating bytes spends 5.75 frames of fleet per frame of new physics.
    At the second segment, which IS the per-family price of a two-segment pass, that is the whole
    difference between 1.15 s and 0.20 s per prefix family.

    The representative is the first member in grid order that avoids the 0/255 extremes, because
    `dtm_make` delivers those as 1/254 (`[[octagon-clamp-decode-bug]]`) -- every member of a class is
    the same physics, so the search may as well carry the one that survives delivery unchanged.

    NOT used by `iter_fan`: the one-segment fan is gated key AND value against the Python reference,
    which enumerates bytes and lets the LAST duplicate win, so collapsing it would change the plans
    it reports. Two-segment passes have no such contract."""
    out, seen = [], set()
    for p in stick_grid(stride):
        k = _decoded(*p)
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    interior = {}
    for p in stick_grid(stride):
        k = _decoded(*p)
        if k not in interior and 0 < p[0] < 255 and 0 < p[1] < 255:
            interior[k] = p
    return [interior.get(_decoded(*p), p) for p in out]


# --------------------------------------------------------------- the fleet fan

def _fan_chunk(base, part, rows, jmax, tx, tz, nthreads, label, cap=ES.WALK_CAP):
    """Run one chunk of held sticks off ``base`` for ``jmax`` frames on the fleet, collecting each
    core's hits in the reference's write order. ``rows`` = the per-core schedule row (one frame, the
    held input); ``label(i, j)`` -> the plan value stored for core ``i`` at step ``j``. ``cap`` is
    `entry_search.walk_fan`'s speed prune, ``None`` to keep sub-cap endpoints (the key then carries
    speedF). Returns ``(writes, cores, alive)`` -- ``cores`` are the post-run junction states."""
    cores = [base.clone(base.pe.clone_state()) for _ in part]
    fleet = N.CourtyardFleet(cores, 1)
    fleet.set_schedule([[r] for r in rows])
    writes = [[] for _ in part]
    alive = [True] * len(part)
    for j in range(jmax + 1):
        fleet.run_par(1, nthreads)
        for i, c in enumerate(cores):
            if not alive[i]:
                continue
            if math.hypot(c.pos_x - tx, c.pos_z - tz) > ES.FOLLOW_BAR:
                alive[i] = False              # she is moving from here on: the branch is dead
                continue
            if j < 1 or (cap is not None and c.speedF != cap):
                continue
            key = (c.pos_x, c.pos_z, int(c.m351C) & 0xFFFF)
            writes[i].append((key if cap is not None else key + (c.speedF,), label(i, j)))
    return writes, cores, alive


def iter_fan(seed=None, env=None, base_frames=(3, 4), stride=2, jmax=8, chunk=CHUNK,
             nthreads=0, progress=False, csangle=ES.CSANGLE, cap=ES.WALK_CAP):
    """`entry_search.walk_fan` on the native fleet, as a STREAM of ``(key, plan)`` in the reference's
    own write order -- so `dict(iter_fan(...))` reproduces it exactly, and a million-candidate pass
    can be evaluated batch-by-batch instead of materialised.

    One held stick per core, `run_par(1)` per frame (the schedule is a single constant row, so
    re-running frame 0 IS the hold), and the reference prunes read off the C fields. ``cap=None``
    drops the speedF-17 one and keys the sub-cap endpoints by their own speed."""
    seed = seed or ES.console_seed()
    hold = dict(seed['log'][-1], buttons=0)
    trg = int(hold.get('triggerL', 0))
    tx, tz = seed['tetra']
    sticks = stick_grid(stride)
    n = 0
    for n0 in base_frames:
        base, _run = base_core(n0, seed=seed, env=env, hold=hold)
        for c0 in range(0, len(sticks), chunk):
            part = sticks[c0:c0 + chunk]
            rows = [(sx, sy, 0, trg, csangle) for (sx, sy) in part]
            writes, _cores, _alive = _fan_chunk(
                base, part, rows, jmax, tx, tz, nthreads,
                lambda i, j, _n0=n0, _p=part: (_n0, _p[i][0], _p[i][1], j), cap=cap)
            for w in writes:
                for kv in w:
                    n += 1
                    yield kv
        if progress:
            print("  fleet fan from n0=%d: %d hits streamed" % (n0, n))


def fleet_fan(seed=None, env=None, base_frames=(3, 4), stride=2, jmax=8, chunk=CHUNK,
              nthreads=0, progress=False, csangle=ES.CSANGLE, cap=ES.WALK_CAP):
    """The `iter_fan` stream collapsed to `walk_fan`'s dict (last writer wins). Gated key AND value
    bit-for-bit against the Python reference, at full resolution against the cached s80 pass."""
    return dict(iter_fan(seed=seed, env=env, base_frames=base_frames, stride=stride, jmax=jmax,
                         chunk=chunk, nthreads=nthreads, progress=progress, csangle=csangle,
                         cap=cap))


def iter_fan2(seed=None, env=None, base_frames=(3, 4), s1_stride=16, j1=(2, 4, 6),
              s2_stride=1, j2max=6, chunk=CHUNK, nthreads=0, progress=False, csangle=ES.CSANGLE,
              cap=ES.WALK_CAP):
    """TWO-SEGMENT holds: stick S1 for j1 frames, then S2 for j2 -- the lever left once stride 1 x 7
    bases has saturated the one-segment fan (measured, `_notes/s81_saturation.py`).

    The junction states are the first segment's own cores after j1 frames (no re-simulation), so the
    cost is the second segment only: ``|S1| x |j1| x |S2| x j2max`` frames. Keys are the same
    ``(endpoint, m351C)``; the plan is ``(n0, sx1, sy1, j1, sx2, sy2, j2)``, a 7-tuple -- which is
    what tells `confirm_entry` it is a two-segment plan. A junction off the speedF 17 cap or past the
    follow bar is not a junction and is dropped whole.

    BOTH segments run the DECODED alphabet (`stick_alphabet`), not the byte grid: duplicate bytes
    re-walk an identical prefix and re-fan an identical junction, which at ``s2_stride=1`` is 5.75x
    of the pass (session 84). Same keys, 5.75x fewer frames."""
    seed = seed or ES.console_seed()
    hold = dict(seed['log'][-1], buttons=0)
    trg = int(hold.get('triggerL', 0))
    tx, tz = seed['tetra']
    s1, s2 = stick_alphabet(s1_stride), stick_alphabet(s2_stride)
    t0, n = time.time(), 0
    for n0 in base_frames:
        base, _run = base_core(n0, seed=seed, env=env, hold=hold)
        for a, (sx1, sy1) in enumerate(s1):
            jun = {}
            c = base.clone(base.pe.clone_state())
            fl = N.CourtyardFleet([c], 1)
            fl.set_schedule([[(sx1, sy1, 0, trg, csangle)]])
            for j in range(1, max(j1) + 1):
                fl.run_par(1, nthreads)
                if j in j1 and (cap is None or c.speedF == cap) \
                        and math.hypot(c.pos_x - tx, c.pos_z - tz) <= ES.FOLLOW_BAR:
                    jun[j] = c.clone(c.pe.clone_state())
            for j, jc in jun.items():
                for c0 in range(0, len(s2), chunk):
                    part = s2[c0:c0 + chunk]
                    rows = [(sx, sy, 0, trg, csangle) for (sx, sy) in part]
                    writes, _cores, _alive = _fan_chunk(
                        jc, part, rows, j2max, tx, tz, nthreads,
                        lambda i, jj, _n=n0, _p=part, _j=j:
                        (_n, sx1, sy1, _j, _p[i][0], _p[i][1], jj), cap=cap)
                    for w in writes:
                        for kv in w:
                            n += 1
                            yield kv
            if progress and (a + 1) % 8 == 0:
                print("  n0=%d  S1 %d/%d: %d hits streamed  [%.0fs]"
                      % (n0, a + 1, len(s1), n, time.time() - t0))


def fleet_fan2(**kw):
    """`iter_fan2` collapsed to a dict -- only for passes small enough to materialise."""
    return dict(iter_fan2(**kw))


# --------------------------------------------------------- the streaming eval

QUAL_CACHE = os.path.join(_rb, '_generated', 's81', 'qualified.json')
BAND_CACHE = os.path.join(_rb, '_generated', 's81', 'bands.json')

#: A band narrower than this is a single f32 `resid` value, not an interval -- a ULP-odds lottery
#: ticket. Candidates are still counted against it but it is not what a pass is aimed at.
MIN_BAND = 1e-6

#: |resid| below which a draw owes its configuration a band measurement -- three orders of margin on
#: the ~1.2e-4 the bands sit within, and what keeps `BandTable` off the hot path.
BAND_PROBE = 5e-3


def _f32_bits(v):
    """A momentum's f32 bit pattern -- the band key has to be exact and a float is not a dict key
    you want to round."""
    return struct.unpack('<I', struct.pack('<f', v))[0]


def ref_entry(seed=None):
    """The locus point every band is Newton-zeroed from: the usable genuine entry nearest Link's
    console endpoint."""
    seed = seed or ES.console_seed()
    return tuple(min((h for h in ES.load_locus()['hits'] if h['follow_ok']),
                     key=lambda h: math.hypot(h['entry'][0] - seed['link'][0],
                                              h['entry'][1] - seed['link'][1]))['entry'])


def qualified(seed=None, csangle=ES.CSANGLE, thrusts=ES.THRUSTS, path=QUAL_CACHE, refresh=False):
    """The productive (facing, thrust) configurations at this camera, with each one's OWN acceptance
    band -- `entry_search.qualify` filtered, cached to json (4 s to recompute since `entry_gradient`
    went analytic + cached).

    Note what a zero-width band means: every genuine sample along the locus read the SAME `resid`, so
    the target is one f32 value rather than an interval. Those configurations are lottery tickets at
    ULP odds; the ones worth spending candidates on are the ones with real width.

    One configuration per sine-table CELL since session 83 (`entry_search.aim_cells`) -- aims inside
    one cell are the same draw, and counting them separately is what let the camera price at 8x. A
    cache written before that is refused rather than silently re-used."""
    if not refresh and path and os.path.exists(path):
        d = json.load(open(path))
        if d.get('cells') and d['csangle'] == csangle and tuple(d['thrusts']) == tuple(thrusts):
            return d['quals']
    seed = seed or ES.console_seed()
    quals = [q for q in ES.qualify(seed['tetra'], ref_entry(seed), thrusts=thrusts,
                                   csangle=csangle) if q['productive']]
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(dict(csangle=csangle, thrusts=list(thrusts), cells=True, quals=quals),
                  open(path, 'w'))
    return quals


class BandTable:
    """``(facing, thrust, m351C, nspeed) -> band``, measured on demand and cached to disk.

    THE CORRECTION THIS EXISTS FOR (session 81). s80 fixed "the fixture window is a union over
    configurations" by measuring a band per (facing, thrust) -- at ``lean=0``. But the band is a
    property of the LEAN too, and it is jagged in it: measured at facing 40820 / thrust 15, 448 of
    556 finely-sampled leans admit something genuine, yet only about 40% of those have a real
    3.2e-5-wide interval; the rest are a single f32 `resid` value or nothing at all. The fan's
    candidates carry ~2000 distinct entry leans (the walk's own turn history), so scoring them all
    against the lean-0 band ranks candidates that cannot clip at ANY entry as near-misses -- which is
    most of what a "near-zero, 0 genuine" pass was counting.

    A band costs ~14 ms (`entry_gradient` is analytic + cached), so a fan's worth of leans is a
    one-off minute and free afterwards -- but only while the key is coarse enough to be REUSED. The
    momentum joined the key in session 82 (`entry_search.roll_nspeed`: a sub-cap walk rolls slower and
    bakes a different schedule), and an uncapped fan carries nearly one nspeed per candidate, so a
    table keyed that finely serves each entry once. That is why `stream_search` measures bands only
    for the near-zero tail instead of eagerly per group."""

    def __init__(self, seed=None, path=BAND_CACHE, ref=None):
        self.seed = seed or ES.console_seed()
        self.ref = ref or ref_entry(self.seed)
        self.path = path
        self.tab = {}
        self.n_measured = 0
        if path and os.path.exists(path):
            for k, v in json.load(open(path)).items():
                p = tuple(int(x) for x in k.split(','))
                # a 3-field key predates the momentum axis: it was measured at the walk cap
                self.tab[p if len(p) > 3 else p + (_f32_bits(ES.ROLL_NSPEED),)] = v

    def get(self, facing, thrust, lean, nspeed=None):
        nsp = ES.ROLL_NSPEED if nspeed is None else nspeed
        key = (int(facing) & 0xFFFF, int(thrust), int(lean) & 0xFFFF, _f32_bits(nsp))
        b = self.tab.get(key)
        if b is None:
            b = ES.configuration_band(self.seed['tetra'], key[0], key[1], key[2], self.ref,
                                      nspeed=nsp)
            self.tab[key] = b
            self.n_measured += 1
        return b

    def usable(self, facing, thrust, lean, nspeed=None, min_width=MIN_BAND):
        b = self.get(facing, thrust, lean, nspeed)
        return b if (b['productive'] and b['width'] >= min_width) else None

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        json.dump({'%d,%d,%d,%d' % k: v for k, v in self.tab.items()}, open(self.path, 'w'))


def family_of_plan(plan):
    """A two-segment plan's PREFIX family ``(n0, sx1, sy1, j1)`` -- the unit a wide pass is priced
    in. A one-segment plan has no prefix, so it is its own family.

    Session 83 measured that the near-misses of a pass scale with the number of FAMILIES, not with
    its candidate count: the last segment's byte alphabet is already exhaustive at stride 1, so what
    moves a candidate's sub-cell residual offset is the prefix that placed the junction."""
    p = tuple(plan)
    return p[:4] if len(p) > 4 else p


def stream_search(pairs, seed=None, quals=None, batch=250000, keep=40, near_gap=5e-3,
                  progress=False, bands=None, min_width=MIN_BAND, probe=BAND_PROBE,
                  family_of=None, dedup_scope='global'):
    """Score a fan STREAM against the productive configurations, batch by batch.

    Deduping is on the packed key (a 2M-candidate pass is ~100 MB of key set, where the dict of
    key -> plan is not), and each batch is grouped by the ROLL -- (entry lean, entry momentum), the
    two things that pick the baked schedule -- so one re-scheduled ctx serves a whole group.

    WHERE THE BAND SITS NOW. s81 looked one up per group and SKIPPED the dead ones: a configuration
    with nothing genuine anywhere along its residual zero cannot be clipped from any entry, so those
    candidates were free to drop. That inverts once the momentum joins the key (session 82): a band
    costs ~14 ms against ~0.2 ms to evaluate a whole group, and an uncapped fan carries nearly one
    momentum per candidate, so measuring a band to save an evaluation costs 70x what it saves. So
    every draw is now EVALUATED -- `genuine` is ground truth and needs no band at all -- and a band is
    measured only for the near-zero tail (|resid| < ``probe``), which is the only population the
    ranking and the lottery estimate are about. A tail draw whose configuration has no usable band is
    counted DEAD rather than as a near-miss: that is the s81 correction, kept.

    Returns the genuine hits plus the near-miss population, which is what sizes the lottery
    (`lottery`, at each near-miss's own band) and is reported WITH ITS IDENTITY (`distinct_near`).

    ``family_of`` (a plan -> family key, e.g. `family_of_plan`) turns the pass into a PRICED one: it
    counts the prefix families the stream spent and records a ``trace`` of (families, candidates,
    near) at every batch. That marginal rate -- near-misses per FAMILY -- is what says whether a
    wide pass is still buying draws or has saturated, and a saturating one should be stopped rather
    than bought more stride (session 84).

    ``dedup_scope='family'`` is what lets a pass be as wide as the clock allows. The global key set
    is the pass's memory (~200 B a candidate, so a 10M-candidate pass is the whole machine), and
    once `stick_alphabet` made the fan 5.75x cheaper that ceiling arrived long before the time did.
    A fan streams family-major and nearly all its repeats are WITHIN one family, so resetting the
    key set at each family boundary bounds memory at one family and re-evaluates only the few
    endpoints two prefixes genuinely share -- and evaluation is a percent of the pass, not its cost.
    Nothing double-counts: the near-misses carry their identity and are deduped on the full draw key
    before anything is reported, so `n_near`, `near` and `lottery` read the same either way."""
    seed = seed or ES.console_seed()
    quals = quals if quals is not None else qualified(seed)
    bands = bands if bands is not None else BandTable(seed)
    pool = ES.CtxPool()
    tx, tz = seed['tetra']
    seen = set()
    fams = set()
    trace = []
    hits, near = [], []
    n_raw = n_uniq = n_eval = n_dead = 0
    t0 = time.time()
    buf = []

    def flush(buf):
        nonlocal n_eval, n_dead
        by_roll = {}
        for k, plan in buf:
            by_roll.setdefault((ES.lean_at_roll(k[2]), ES.candidate_nspeed(k)), []).append((k, plan))
        for q in quals:
            fac, thrust = q['facing'], q['thrust']
            for (lean, nsp), group in by_roll.items():
                ctx, sch, resid = pool.get(fac, lean, thrust, nspeed=nsp)
                ents = [ES.roll_entry((k[0], k[1]), fac, nsp) for k, _ in group]
                rows = ctx.sweep_par([(tx, tz, e[0], e[1]) for e in ents], 0)
                n_eval += len(rows)
                for (k, plan), e, o in zip(group, ents, rows):
                    r = resid(o)
                    if not o[0] and abs(r) >= probe:
                        continue                  # too far out to be a near-miss OR to owe a band
                    band = bands.usable(fac, thrust, lean, nsp, min_width)
                    if o[0]:
                        # `genuine` is ground truth. It is reported whatever the band says -- a band
                        # is a measurement of the neighbourhood and never a veto on a real hit.
                        hits.append(dict(entry=[e[0], e[1]], walk=[k[0], k[1]], m351C_walk=k[2],
                                         m351C=lean, facing=fac, aim=q['aim'], thrust=thrust,
                                         b_step=thrust + 2, resid=r, push=[o[5], o[6]], nspeed=nsp,
                                         gap=(ES.window_gap(r, band) if band else None),
                                         band=([band['lo'], band['hi']] if band else None),
                                         plan=list(plan),
                                         walkable=bool(TA.is_walkable(k[0], k[1])
                                                       and TA.is_walkable(e[0], e[1]))))
                    elif band is None:
                        n_dead += 1               # nothing genuine here, at any entry
                    elif ES.window_gap(r, band) < near_gap:
                        # WITH ITS IDENTITY, so the count can be audited (`distinct_near`)
                        near.append((ES.window_gap(r, band),
                                     dict(walk=[k[0], k[1]], entry=[e[0], e[1]], m351C=lean,
                                          facing=fac, thrust=thrust, nspeed=nsp, resid=r,
                                          width=band['width'], plan=list(plan))))

    def mark():
        trace.append(dict(families=len(fams), candidates=n_uniq, near=len(near),
                          genuine=len(hits), seconds=time.time() - t0))

    cur_fam = None
    for k, plan in pairs:
        n_raw += 1
        if family_of is not None:
            fam = family_of(plan)
            fams.add(fam)
            if dedup_scope == 'family' and fam != cur_fam:
                cur_fam, seen = fam, set()
        p = struct.pack('<ddI', k[0], k[1], k[2]) + (struct.pack('<f', k[3]) if len(k) > 3 else b'')
        if p in seen:
            continue
        seen.add(p)
        n_uniq += 1
        buf.append((k, plan))
        if len(buf) >= batch:
            flush(buf)
            buf = []
            bands.save()
            mark()
            if progress:
                t = trace[-1]
                d = _marginal(trace)
                print("  %d unique of %d streamed, %d evals, %d dead-tail, %d genuine,"
                      " %d near  [%d families, %.4f near/family, marginal %s]  [%.0fs]"
                      % (n_uniq, n_raw, n_eval, n_dead, len(hits), len(near), t['families'],
                         (t['near'] / t['families']) if t['families'] else 0.0,
                         ("%.4f" % d) if d is not None else "-", t['seconds']))
    if buf:
        flush(buf)
    bands.save()
    mark()
    near = dedupe_near(near)
    near.sort(key=lambda gi: gi[0])
    gaps = [g for g, _ in near]
    walkable = [h for h in hits if h['walkable']]
    # frame-minimal first: the plan's total delivered frames (n0 + every segment's hold), then resid
    walkable.sort(key=lambda h: (h['plan'][0] + sum(h['plan'][3::3]), abs(h['resid'])))
    widths = [b['width'] for b in (bands.usable(q['facing'], q['thrust'], 0) for q in quals) if b]
    return dict(hits=walkable, n_hits_raw=len(hits), n_hit_draws=len(hit_draws(walkable)),
                n_candidates=n_uniq, n_streamed=n_raw,
                n_evaluations=n_eval, n_dead_lean=n_dead, n_configurations=len(quals),
                n_bands_measured=bands.n_measured, n_near=len(near),
                near=gaps[:keep], near_gap=near_gap, seconds=time.time() - t0,
                expected_hits=lottery(near, near_gap),
                expected_hits_lean0=_expected_hits(gaps, widths, near_gap),
                near_detail=[dict(gap=g, **i) for g, i in near[:keep]],
                n_near_candidates=distinct_near(near),
                n_families=len(fams), trace=trace, dedup_scope=dedup_scope,
                near_per_family=((len(near) / len(fams)) if fams else None),
                marginal_near_per_family=_marginal(trace),
                configurations=[dict(facing=q['facing'], thrust=q['thrust'], lo=q['lo'],
                                     hi=q['hi'], width=q['width']) for q in quals])


def draw_key(ident):
    """A near-miss's DRAW: the walk endpoint and lean that the delivered input decides, plus the
    configuration it was scored at. Two configurations off one endpoint are two draws -- you choose
    which aim to press -- but the same draw reached by two prefixes is one."""
    return (ident['walk'][0], ident['walk'][1], ident['m351C'],
            ident['facing'], ident['thrust'], struct.pack('<f', float(ident['nspeed'])))


def hit_draws(hits):
    """One representative HIT per draw, frame-minimal first -- the honest count of what a pass found.

    A genuine hit is a draw exactly like a near-miss is, and the same prefixes-collide arithmetic
    applies: the s84 wide pass returned 118 genuine scorings that are **23 draws at 20 entries**, one
    of them reached by 95 different prefixes. Reporting 118 would be counting deliveries as
    discoveries. The extra prefixes are worth keeping -- they are alternative ways to deliver the
    same entry, and `confirm_entry` may reject some of them -- but the representative is the
    frame-minimal one, because frames are the objective (`[[tetrapush-frame-minimal]]`)."""
    best = {}
    for h in hits:
        k = draw_key(h)
        f = h['plan'][0] + sum(h['plan'][3::3])
        if k not in best or (f, abs(h['resid'])) < best[k][0]:
            best[k] = ((f, abs(h['resid'])), h)
    return [h for _f, h in sorted(best.values(), key=lambda t: t[0])]


def dedupe_near(near):
    """One row per draw, keeping the tightest gap. Required once the candidate key set is scoped per
    family (`stream_search`), and harmless when it is global -- so the pass's reported numbers do
    not depend on how its memory was budgeted."""
    best = {}
    for g, i in near:
        k = draw_key(i)
        if k not in best or g < best[k][0]:
            best[k] = (g, i)
    return list(best.values())


def lottery(near, near_gap):
    """E[hits] over a near-miss population, at each near-miss's OWN band.

    Every one of them is a draw whose residual is locally uniform across a ``2 x near_gap`` window,
    so it lands inside its band with probability ``width / (2 x near_gap)`` and the expectation is
    the sum. The width has to be the one that near-miss was scored against: the band is a jagged
    function of the entry LEAN (`BandTable`), and pricing a whole pass at the lean-0 widths -- what
    `_expected_hits` did through s83 -- prices draws at a band none of them is standing in."""
    return sum(i['width'] for _g, i in near) / (2.0 * near_gap)


def distinct_near(near):
    """How many DISTINCT draws a near-miss population actually is.

    A candidate is its walk endpoint and its entry lean -- everything the delivered input decides.
    The same one scored against several configurations is several near-misses (you get to pick which
    aim you press) but ONE draw of the walk, and s83's 8.00x camera multiplier was exactly that
    confusion at a different level: 48 near-misses that were 3 candidates counted sixteen times.
    Reporting both numbers is what makes a copy visible without re-running the pass."""
    return len({(i['walk'][0], i['walk'][1], i['m351C']) for _g, i in near})


def _marginal(trace, back=4):
    """Near-misses per family over the LAST few batches.

    The cumulative rate is dominated by the pass's early families and keeps looking healthy long
    after an axis stops paying, so this is the one to watch WHILE a pass runs. ``None`` until there
    are two marks with families between them (a pass run without ``family_of`` never gets one).

    NOT a saturation verdict on its own, and specifically not at the end of a pass: the stick grid
    is enumerated x-major, so a sweep crosses the productive direction band ONCE and its marginal
    rate is zero at the start, high in the middle and zero again at the finish. The honest test is
    two whole-circle alphabets compared on draws per family (`knowledge/strategy/
    clip-lottery-draws.md`)."""
    if len(trace) < 2:
        return None
    a, b = trace[max(0, len(trace) - 1 - back)], trace[-1]
    df = b['families'] - a['families']
    return ((b['near'] - a['near']) / df) if df > 0 else None


def _expected_hits(near, widths, near_gap):
    """The SUPERSEDED lottery estimate, kept so a pass stays comparable to the ones before it.

    Same model as the live one -- a candidate's resid is locally uniform near the band, so
    ``E[hits] = (near-miss count / 2 x near_gap) x band width`` -- but it takes the width from each
    CONFIGURATION at lean 0, where the near-misses are at their own leans and the band is a jagged
    function of the lean (`BandTable`). `stream_search` now sums each near-miss's OWN measured width
    instead; this one is reported beside it as ``expected_hits_lean0``."""
    if not near or not widths:
        return 0.0
    return (len(near) / (2.0 * near_gap)) * (sum(widths) / len(widths))


# ------------------------------------------------------------------- the gate

def load_cached_fan(path=FAN_CACHE):
    """The session-80 reference pass, as `walk_fan` returned it (stride 1, jmax 12, 7 bases)."""
    return {tuple(k): tuple(v) for k, v in json.load(open(path))}


def fan_equality(reference, native):
    """Dict-vs-dict, bit-for-bit: shared keys, key-only-in-either, and value disagreements. The
    positions are exact f64 doubles out of both engines, so this is an equality test and never a
    tolerance -- `[[zero-ulp-tests-only]]`."""
    rk, nk = set(reference), set(native)
    diff = [(k, reference[k], native[k]) for k in (rk & nk) if reference[k] != native[k]]
    return dict(n_reference=len(reference), n_native=len(native), n_shared=len(rk & nk),
                only_reference=sorted(rk - nk)[:8], only_native=sorted(nk - rk)[:8],
                n_only_reference=len(rk - nk), n_only_native=len(nk - rk),
                value_diffs=diff[:8], n_value_diffs=len(diff),
                equal=(rk == nk and not diff))


# --------------------------------------------------------------------------- CLI

def _cmd_gate(argv):
    warnings.simplefilter('ignore')
    if not os.path.exists(FAN_CACHE):
        raise SystemExit("no cached reference pass at %s -- run the s80 fan first" % FAN_CACHE)
    ref = load_cached_fan()
    print("cached reference (s80, stride 1 jmax 12, 7 bases): %d candidates" % len(ref))
    t0 = time.time()
    nat = fleet_fan(base_frames=tuple(range(7)), stride=1, jmax=12, progress=True)
    dt = time.time() - t0
    r = fan_equality(ref, nat)
    print("\nnative fleet fan: %d candidates in %.1f s  (reference took 1444 s)" % (len(nat), dt))
    print("  shared %d   only-reference %d   only-native %d   value diffs %d"
          % (r['n_shared'], r['n_only_reference'], r['n_only_native'], r['n_value_diffs']))
    print("  EQUAL (key AND value, bit-for-bit): %s" % r['equal'])
    if not r['equal']:
        print("  only-reference sample: %s" % (r['only_reference'],))
        print("  only-native    sample: %s" % (r['only_native'],))
        print("  value diffs    sample: %s" % (r['value_diffs'],))


def _cmd_fan(argv):
    warnings.simplefilter('ignore')
    stride = int(argv[0]) if argv else 1
    jmax = int(argv[1]) if len(argv) > 1 else 12
    nbase = int(argv[2]) if len(argv) > 2 else 7
    t0 = time.time()
    fan = fleet_fan(base_frames=tuple(range(nbase)), stride=stride, jmax=jmax, progress=True)
    print("FAN %d distinct (endpoint, lean) in %.1f s" % (len(fan), time.time() - t0))
    out = os.path.join(_rb, '_generated', 's81', 'fan_s%d_j%d_b%d.json' % (stride, jmax, nbase))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump([[list(k), list(v)] for k, v in fan.items()], open(out, 'w'))
    print("wrote %s" % out)


def _cmd_fan2(argv):
    warnings.simplefilter('ignore')
    s1_stride = int(argv[0]) if argv else 16
    j1 = tuple(int(x) for x in argv[1].split(',')) if len(argv) > 1 else (2, 4, 6)
    s2_stride = int(argv[2]) if len(argv) > 2 else 1
    j2max = int(argv[3]) if len(argv) > 3 else 6
    nbase = int(argv[4]) if len(argv) > 4 else 2
    t0 = time.time()
    fan = fleet_fan2(base_frames=tuple(range(nbase)), s1_stride=s1_stride, j1=j1,
                     s2_stride=s2_stride, j2max=j2max, progress=True)
    print("FAN2 %d distinct (endpoint, lean) in %.1f s" % (len(fan), time.time() - t0))
    out = os.path.join(_rb, '_generated', 's81',
                       'fan2_a%d_j%s_b%d_s%d_j%d.json'
                       % (s1_stride, '-'.join(str(j) for j in j1), nbase, s2_stride, j2max))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump([[list(k), list(v)] for k, v in fan.items()], open(out, 'w'))
    print("wrote %s" % out)


def _report(r, tag, extra=None):
    print("\n%s: %d candidates (unique per %s) of %d streamed, %d evaluations against %d"
          " configurations [%.0f s]"
          % (tag, r['n_candidates'], r.get('dedup_scope', 'global'), r['n_streamed'],
             r['n_evaluations'], r['n_configurations'], r['seconds']))
    print("  near-zero draws at a DEAD configuration (no band at any entry): %d   bands measured %d"
          % (r['n_dead_lean'], r['n_bands_measured']))
    print("  near-miss (gap < %g): %d  (%d DISTINCT candidates)   E[hits] this pass %.3f"
          "  (%.3f at the lean-0 widths, the pre-s84 estimate)"
          % (r['near_gap'], r['n_near'], r.get('n_near_candidates', -1), r['expected_hits'],
             r.get('expected_hits_lean0', float('nan'))))
    print("  GENUINE: %d DISTINCT DRAWS, from %d walkable scorings of %d"
          % (r.get('n_hit_draws', -1), len(r['hits']), r['n_hits_raw']))
    if r.get('n_families'):
        print("  prefix families %d   near/family %.4f (cumulative)   %s (marginal, last batches)"
              % (r['n_families'], r['near_per_family'],
                 ("%.4f" % r['marginal_near_per_family'])
                 if r['marginal_near_per_family'] is not None else "-"))
    print("  best gaps: %s" % ["%.3e" % g for g in r['near'][:8]])
    for h in hit_draws(r['hits'])[:25]:
        print("  plan %s  facing %5d thrust %2d  entry (%r,%r) m351C %5d  resid %+.3e"
              % (h['plan'], h['facing'], h['thrust'], h['entry'][0], h['entry'][1],
                 h['m351C'], h['resid']))
    out = os.path.join(_rb, '_generated', 's81', 'hits_%s.json' % tag)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(tag=tag, extra=extra or {}, **r), open(out, 'w'), indent=1)
    print("wrote %s" % out)


def _cmd_search1(argv):
    """The one-segment pass at its measured saturation (7 bases, jmax 36, stride 1).

    ``uncapped`` drops the speedF-17 prune: 3x the candidates, and each sub-cap walk speed bakes its
    own roll schedule and its own locus (`entry_search.roll_nspeed`)."""
    warnings.simplefilter('ignore')
    jmax = int(argv[0]) if argv else 36
    nbase = int(argv[1]) if len(argv) > 1 else 7
    stride = int(argv[2]) if len(argv) > 2 else 1
    cap = None if 'uncapped' in argv else ES.WALK_CAP
    r = stream_search(iter_fan(base_frames=tuple(range(nbase)), stride=stride, jmax=jmax, cap=cap,
                               progress=True), progress=True)
    _report(r, 'seg1_j%d_b%d_s%d%s' % (jmax, nbase, stride, '_uncapped' if cap is None else ''),
            dict(jmax=jmax, bases=nbase, stride=stride, cap=cap))


def _cmd_search2(argv):
    """The two-segment pass: S1 x j1 junctions, each re-fanned with a stride-1 S2.

    PRICED IN FAMILIES (`family_of_plan`), because that is the unit this axis pays in: the report
    carries near/family cumulative AND marginal, and the marginal rate is the stop signal."""
    warnings.simplefilter('ignore')
    s1_stride = int(argv[0]) if argv else 32
    j1 = tuple(int(x) for x in argv[1].split(',')) if len(argv) > 1 else (2, 4, 6)
    s2_stride = int(argv[2]) if len(argv) > 2 else 1
    j2max = int(argv[3]) if len(argv) > 3 else 6
    nbase = int(argv[4]) if len(argv) > 4 else 2
    kw = dict(base_frames=tuple(range(nbase)), s1_stride=s1_stride, j1=j1,
              s2_stride=s2_stride, j2max=j2max)
    print("S1 alphabet %d draws (of %d byte pairs at stride %d), S2 %d (of %d at stride %d)"
          % (len(stick_alphabet(s1_stride)), len(stick_grid(s1_stride)), s1_stride,
             len(stick_alphabet(s2_stride)), len(stick_grid(s2_stride)), s2_stride))
    r = stream_search(iter_fan2(progress=True, **kw), progress=True, family_of=family_of_plan,
                      dedup_scope='family')
    _report(r, 'seg2_a%d_j%s_s%d_j%d_b%d'
            % (s1_stride, '-'.join(str(j) for j in j1), s2_stride, j2max, nbase),
            dict(kw, j1=list(j1), base_frames=list(kw['base_frames'])))


def confirm_hits(hits, seed=None, env=None, progress=False):
    """`entry_search.confirm_entry` over a pass's hits -- the A-press replay each one owes.

    A swept hit is a PREDICTION: the fan never presses A, it predicts the entry from the walk
    endpoint. The replay has already caught an `INPUT_DELAY` off-by-one and an entry-frame brake, so
    nothing is a result until it comes back `all_ok`. Returns one row per hit, confirmed first."""
    out = []
    for i, h in enumerate(hits):
        c = ES.confirm_entry(h, seed=seed, env=env)
        out.append(dict(hit=h, confirm=c))
        if progress:
            print("  hit %d/%d plan %s: all_ok %s  %s"
                  % (i + 1, len(hits), h['plan'], c['all_ok'],
                     "" if c['all_ok'] else [k for k, v in c['ok'].items() if not v]))
    out.sort(key=lambda r: (not r['confirm']['all_ok'],
                            r['hit']['plan'][0] + sum(r['hit']['plan'][3::3])))
    return out


def _cmd_confirm(argv):
    """Replay every hit in a pass's json with a real A-press and report what survives."""
    warnings.simplefilter('ignore')
    if not argv:
        raise SystemExit("usage: confirm <hits json>   (written by search1/search2)")
    tag = argv[0][len('hits_'):] if argv[0].startswith('hits_') else argv[0]
    path = argv[0] if os.path.exists(argv[0]) \
        else os.path.join(_rb, '_generated', 's81', 'hits_%s.json' % tag.replace('.json', ''))
    r = json.load(open(path))
    # one replay per DRAW by default -- the extra prefixes are alternative deliveries of an entry
    # already confirmed, and a pass can carry a hundred of them. `all` replays every one.
    hits = r['hits'] if 'all' in argv else hit_draws(r['hits'])
    print("%s: %d hits to confirm (%d walkable scorings collapse to %d draws)"
          % (os.path.basename(path), len(hits), len(r['hits']), len(hit_draws(r['hits']))))
    rows = confirm_hits(hits, progress=True)
    ok = [x for x in rows if x['confirm']['all_ok']]
    print("\nCONFIRMED %d of %d" % (len(ok), len(rows)))
    for x in ok:
        h, m = x['hit'], x['confirm']['measured']
        print("  plan %s  aim %s  facing %d thrust %d  entry (%r,%r)  resid %+.3e  frames %d"
              % (h['plan'], h['aim'], h['facing'], h['thrust'], m['entry'][0], m['entry'][1],
                 h['resid'], h['plan'][0] + sum(h['plan'][3::3])))
    out = path.replace('.json', '_confirmed.json')
    json.dump(rows, open(out, 'w'), indent=1)
    print("wrote %s" % out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'gate'
    if cmd == 'gate':
        _cmd_gate(argv)
    elif cmd == 'fan':
        _cmd_fan(argv)
    elif cmd == 'fan2':
        _cmd_fan2(argv)
    elif cmd == 'search1':
        _cmd_search1(argv)
    elif cmd == 'search2':
        _cmd_search2(argv)
    elif cmd == 'confirm':
        _cmd_confirm(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
