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


# --------------------------------------------------------------- the fleet fan

def _fan_chunk(base, part, rows, jmax, tx, tz, nthreads, label):
    """Run one chunk of held sticks off ``base`` for ``jmax`` frames on the fleet, collecting each
    core's hits in the reference's write order. ``rows`` = the per-core schedule row (one frame, the
    held input); ``label(i, j)`` -> the plan value stored for core ``i`` at step ``j``. Returns
    ``(writes, cores)`` -- ``cores`` are the post-run junction states (`fleet_fan2` re-fans them)."""
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
            if j >= 1 and c.speedF == 17.0:
                writes[i].append(((c.pos_x, c.pos_z, int(c.m351C) & 0xFFFF), label(i, j)))
    return writes, cores, alive


def iter_fan(seed=None, env=None, base_frames=(3, 4), stride=2, jmax=8, chunk=CHUNK,
             nthreads=0, progress=False, csangle=ES.CSANGLE):
    """`entry_search.walk_fan` on the native fleet, as a STREAM of ``(key, plan)`` in the reference's
    own write order -- so `dict(iter_fan(...))` reproduces it exactly, and a million-candidate pass
    can be evaluated batch-by-batch instead of materialised.

    One held stick per core, `run_par(1)` per frame (the schedule is a single constant row, so
    re-running frame 0 IS the hold), and the two reference prunes read off the C fields."""
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
                lambda i, j, _n0=n0, _p=part: (_n0, _p[i][0], _p[i][1], j))
            for w in writes:
                for kv in w:
                    n += 1
                    yield kv
        if progress:
            print("  fleet fan from n0=%d: %d hits streamed" % (n0, n))


def fleet_fan(seed=None, env=None, base_frames=(3, 4), stride=2, jmax=8, chunk=CHUNK,
              nthreads=0, progress=False, csangle=ES.CSANGLE):
    """The `iter_fan` stream collapsed to `walk_fan`'s dict (last writer wins). Gated key AND value
    bit-for-bit against the Python reference, at full resolution against the cached s80 pass."""
    return dict(iter_fan(seed=seed, env=env, base_frames=base_frames, stride=stride, jmax=jmax,
                         chunk=chunk, nthreads=nthreads, progress=progress, csangle=csangle))


def iter_fan2(seed=None, env=None, base_frames=(3, 4), s1_stride=16, j1=(2, 4, 6),
              s2_stride=1, j2max=6, chunk=CHUNK, nthreads=0, progress=False, csangle=ES.CSANGLE):
    """TWO-SEGMENT holds: stick S1 for j1 frames, then S2 for j2 -- the lever left once stride 1 x 7
    bases has saturated the one-segment fan (measured, `_notes/s81_saturation.py`).

    The junction states are the first segment's own cores after j1 frames (no re-simulation), so the
    cost is the second segment only: ``|S1| x |j1| x |S2| x j2max`` frames. Keys are the same
    ``(endpoint, m351C)``; the plan is ``(n0, sx1, sy1, j1, sx2, sy2, j2)``, a 7-tuple -- which is
    what tells `confirm_entry` it is a two-segment plan. A junction off the speedF 17 cap or past the
    follow bar is not a junction and is dropped whole."""
    seed = seed or ES.console_seed()
    hold = dict(seed['log'][-1], buttons=0)
    trg = int(hold.get('triggerL', 0))
    tx, tz = seed['tetra']
    s1, s2 = stick_grid(s1_stride), stick_grid(s2_stride)
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
                if j in j1 and c.speedF == 17.0 \
                        and math.hypot(c.pos_x - tx, c.pos_z - tz) <= ES.FOLLOW_BAR:
                    jun[j] = c.clone(c.pe.clone_state())
            for j, jc in jun.items():
                for c0 in range(0, len(s2), chunk):
                    part = s2[c0:c0 + chunk]
                    rows = [(sx, sy, 0, trg, csangle) for (sx, sy) in part]
                    writes, _cores, _alive = _fan_chunk(
                        jc, part, rows, j2max, tx, tz, nthreads,
                        lambda i, jj, _n=n0, _p=part, _j=j:
                        (_n, sx1, sy1, _j, _p[i][0], _p[i][1], jj))
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
    ULP odds; the ones worth spending candidates on are the ones with real width."""
    if not refresh and path and os.path.exists(path):
        d = json.load(open(path))
        if d['csangle'] == csangle and tuple(d['thrusts']) == tuple(thrusts):
            return d['quals']
    seed = seed or ES.console_seed()
    quals = [q for q in ES.qualify(seed['tetra'], ref_entry(seed), thrusts=thrusts,
                                   csangle=csangle) if q['productive']]
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(dict(csangle=csangle, thrusts=list(thrusts), quals=quals), open(path, 'w'))
    return quals


class BandTable:
    """``(facing, thrust, m351C) -> band``, measured on demand and cached to disk.

    THE CORRECTION THIS EXISTS FOR (session 81). s80 fixed "the fixture window is a union over
    configurations" by measuring a band per (facing, thrust) -- at ``lean=0``. But the band is a
    property of the LEAN too, and it is jagged in it: measured at facing 40820 / thrust 15, 448 of
    556 finely-sampled leans admit something genuine, yet only about 40% of those have a real
    3.2e-5-wide interval; the rest are a single f32 `resid` value or nothing at all. The fan's
    candidates carry ~2000 distinct entry leans (the walk's own turn history), so scoring them all
    against the lean-0 band ranks candidates that cannot clip at ANY entry as near-misses -- which is
    most of what a "near-zero, 0 genuine" pass was counting.

    A band costs ~14 ms (`entry_gradient` is analytic + cached), so a fan's worth of leans is a
    one-off minute and free afterwards."""

    def __init__(self, seed=None, path=BAND_CACHE, ref=None):
        self.seed = seed or ES.console_seed()
        self.ref = ref or ref_entry(self.seed)
        self.path = path
        self.tab = {}
        self.n_measured = 0
        if path and os.path.exists(path):
            for k, v in json.load(open(path)).items():
                self.tab[tuple(int(x) for x in k.split(','))] = v

    def get(self, facing, thrust, lean):
        key = (int(facing) & 0xFFFF, int(thrust), int(lean) & 0xFFFF)
        b = self.tab.get(key)
        if b is None:
            b = ES.configuration_band(self.seed['tetra'], key[0], key[1], key[2], self.ref)
            self.tab[key] = b
            self.n_measured += 1
        return b

    def usable(self, facing, thrust, lean, min_width=MIN_BAND):
        b = self.get(facing, thrust, lean)
        return b if (b['productive'] and b['width'] >= min_width) else None

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        json.dump({'%d,%d,%d' % k: v for k, v in self.tab.items()}, open(self.path, 'w'))


def stream_search(pairs, seed=None, quals=None, batch=250000, keep=40, near_gap=5e-3,
                  progress=False, bands=None, min_width=MIN_BAND):
    """Score a fan STREAM against the productive configurations, batch by batch.

    Deduping is on the packed key (a 2M-candidate pass is ~100 MB of key set, where the dict of
    key -> plan is not), and each batch is grouped by the roll-entry lean so one ctx serves a whole
    group -- the same structure `entry_search.search` uses, just bounded in memory.

    The ranking is `window_gap` against the band of the candidate's OWN (facing, thrust, m351C) --
    see `BandTable` for why the lean belongs in that key and what counting it wrong did to the
    near-miss statistic. A (configuration, lean) with no usable band is DEAD: no entry clips it, so
    its candidates are skipped and reported separately rather than ranked as near-misses.

    Returns the genuine hits plus the near-miss population, which is what sizes the lottery:
    expected hits ~ (near-miss density in resid) x (band width)."""
    seed = seed or ES.console_seed()
    quals = quals if quals is not None else qualified(seed)
    bands = bands if bands is not None else BandTable(seed)
    tx, tz = seed['tetra']
    seen = set()
    hits, near = [], []
    n_raw = n_uniq = n_eval = n_dead = 0
    t0 = time.time()
    buf = []

    def flush(buf):
        nonlocal n_eval, n_dead
        by_lean = {}
        for k, plan in buf:
            by_lean.setdefault(ES.lean_at_roll(k[2]), []).append((k, plan))
        for q in quals:
            fac, thrust = q['facing'], q['thrust']
            for lean, group in by_lean.items():
                band = bands.usable(fac, thrust, lean, min_width)
                if band is None:
                    n_dead += len(group)          # nothing genuine at this lean, at any entry
                    continue
                ctx, sch, resid = ES.build_fast(fac, lean, thrust)
                ents = [ES.roll_entry((k[0], k[1]), fac) for k, _ in group]
                rows = ctx.sweep_par([(tx, tz, e[0], e[1]) for e in ents], 0)
                n_eval += len(rows)
                for (k, plan), e, o in zip(group, ents, rows):
                    r = resid(o)
                    g = ES.window_gap(r, band)
                    if o[0]:
                        hits.append(dict(entry=[e[0], e[1]], walk=[k[0], k[1]], m351C_walk=k[2],
                                         m351C=lean, facing=fac, aim=q['aim'], thrust=thrust,
                                         b_step=thrust + 2, resid=r, gap=g, push=[o[5], o[6]],
                                         band=[band['lo'], band['hi']], plan=list(plan),
                                         walkable=bool(TA.is_walkable(k[0], k[1])
                                                       and TA.is_walkable(e[0], e[1]))))
                    elif g < near_gap:
                        near.append(g)

    for k, plan in pairs:
        n_raw += 1
        p = struct.pack('<ddI', k[0], k[1], k[2])
        if p in seen:
            continue
        seen.add(p)
        n_uniq += 1
        buf.append((k, plan))
        if len(buf) >= batch:
            flush(buf)
            buf = []
            bands.save()
            if progress:
                print("  %d unique of %d streamed, %d live evals (%d dead-lean), %d genuine,"
                      " %d near  [%.0fs]" % (n_uniq, n_raw, n_eval, n_dead, len(hits), len(near),
                                             time.time() - t0))
    if buf:
        flush(buf)
    bands.save()
    near.sort()
    walkable = [h for h in hits if h['walkable']]
    # frame-minimal first: the plan's total delivered frames (n0 + every segment's hold), then resid
    walkable.sort(key=lambda h: (h['plan'][0] + sum(h['plan'][3::3]), abs(h['resid'])))
    widths = [b['width'] for b in (bands.usable(q['facing'], q['thrust'], 0) for q in quals) if b]
    return dict(hits=walkable, n_hits_raw=len(hits), n_candidates=n_uniq, n_streamed=n_raw,
                n_evaluations=n_eval, n_dead_lean=n_dead, n_configurations=len(quals),
                n_bands_measured=bands.n_measured, n_near=len(near),
                near=near[:keep], near_gap=near_gap, seconds=time.time() - t0,
                expected_hits=_expected_hits(near, widths, near_gap),
                configurations=[dict(facing=q['facing'], thrust=q['thrust'], lo=q['lo'],
                                     hi=q['hi'], width=q['width']) for q in quals])


def _expected_hits(near, widths, near_gap):
    """The lottery, sized off the pass's OWN near-miss population: a candidate's resid is locally
    uniform near the band, so ``E[hits] = (near-miss count / 2 x near_gap) x mean band width``. This
    is the number that says whether a pass was too small -- s80's widest was 0.23, and that estimate
    was itself optimistic because the near-misses it counted included dead-lean candidates."""
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
    print("\n%s: %d unique candidates of %d streamed, %d evaluations against %d configurations"
          " [%.0f s]" % (tag, r['n_candidates'], r['n_streamed'], r['n_evaluations'],
                         r['n_configurations'], r['seconds']))
    print("  dead-lean (no band at ANY entry): %d of %d draws   bands measured %d"
          % (r['n_dead_lean'], r['n_dead_lean'] + r['n_evaluations'], r['n_bands_measured']))
    print("  near-miss (gap < %g): %d      GENUINE: %d      E[hits] this pass %.2f"
          % (r['near_gap'], r['n_near'], len(r['hits']), r['expected_hits']))
    print("  best gaps: %s" % ["%.3e" % g for g in r['near'][:8]])
    for h in r['hits'][:25]:
        print("  plan %s  facing %5d thrust %2d  entry (%r,%r) m351C %5d  resid %+.3e"
              % (h['plan'], h['facing'], h['thrust'], h['entry'][0], h['entry'][1],
                 h['m351C'], h['resid']))
    out = os.path.join(_rb, '_generated', 's81', 'hits_%s.json' % tag)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(tag=tag, extra=extra or {}, **r), open(out, 'w'), indent=1)
    print("wrote %s" % out)


def _cmd_search1(argv):
    """The one-segment pass at its measured saturation (7 bases, jmax 36, stride 1)."""
    warnings.simplefilter('ignore')
    jmax = int(argv[0]) if argv else 36
    r = stream_search(iter_fan(base_frames=tuple(range(7)), stride=1, jmax=jmax, progress=True),
                      progress=True)
    _report(r, 'seg1_j%d' % jmax, dict(jmax=jmax, bases=7, stride=1))


def _cmd_search2(argv):
    """The two-segment pass: S1 x j1 junctions, each re-fanned with a stride-1 S2."""
    warnings.simplefilter('ignore')
    s1_stride = int(argv[0]) if argv else 32
    j1 = tuple(int(x) for x in argv[1].split(',')) if len(argv) > 1 else (2, 4, 6)
    s2_stride = int(argv[2]) if len(argv) > 2 else 1
    j2max = int(argv[3]) if len(argv) > 3 else 6
    nbase = int(argv[4]) if len(argv) > 4 else 2
    kw = dict(base_frames=tuple(range(nbase)), s1_stride=s1_stride, j1=j1,
              s2_stride=s2_stride, j2max=j2max)
    r = stream_search(iter_fan2(progress=True, **kw), progress=True)
    _report(r, 'seg2_a%d_j%s_s%d_j%d_b%d'
            % (s1_stride, '-'.join(str(j) for j in j1), s2_stride, j2max, nbase),
            dict(kw, j1=list(j1), base_frames=list(kw['base_frames'])))


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
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
