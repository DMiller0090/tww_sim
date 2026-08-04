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

WHAT A CANDIDATE PROMISES, and the three prunes that make the promise true. An endpoint here is a
claim that Link ROLLS from it, so the keep-test owes every condition the A dispatch has: inside the
230 u follow bar (else Tetra is not a constant any more), at the speedF the schedule was baked at,
and in a proc the A-press can actually roll from (`_is_rollable`, session 85 -- the one that was
missing, and the reason 3 of session 84's 23 draws replayed as a turn). See
`knowledge/strategy/search-prune-the-dispatch.md`.

The SCORING half -- bands, `stream_search`, and the whole draw-counting vocabulary -- moved to
`entry_score` in session 85 and is re-exported here name for name.

    python -m harness.tetrapush.entry_fan gate            # the fan-equality gate vs the cached pass
    python -m harness.tetrapush.entry_fan fan [stride jmax nbase]
    python -m harness.tetrapush.entry_fan fan2 [s1_stride j1 s2_stride j2max]
    python -m harness.tetrapush.entry_fan search1 [jmax nbase stride [uncapped]]
    python -m harness.tetrapush.entry_fan search2 [s1_stride j1 s2_stride j2max nbase [cells]]
    python -m harness.tetrapush.entry_fan confirm <hits json | tag> [xengine]  # the A-press replay
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
from tww_sim.land.constants import ROLL_FROM
from tww_sim.land.plan_land._primitives import main_stick_decode
from harness.tetrapush import entry_search as ES
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


def delivered(sx, sy):
    """A byte pair as a DTM actually DELIVERS it: `dtm_make.cal` clamps the extremes by one
    (255 -> 254, 0 -> 1, everything else through), the `getMainStickValue` calibration."""
    c = {255: 254, 0: 1}
    return (c.get(int(sx), int(sx)), c.get(int(sy), int(sy)))


def survives_delivery(sx, sy):
    """Would this byte pair reach the console as the physics the search scored it at?

    The rewrite is not automatically fatal -- what matters is the DECODE, and the dead zone plus the
    octagon clamp mean a clamped extreme very often lands in the same class. So this is an equality on
    `(angle, msd)`, not a test for a 0 or a 255 (`[[octagon-clamp-decode-bug]]`: a plan must sim the
    DELIVERED bytes, and the s60 tread error came from simming the raw ones).

    `stick_alphabet` avoids the question entirely by preferring an interior representative; the AIM
    bytes come from `entry_search.aim_cells`, which has no such preference and has simply been lucky
    so far (all 20 of session 84's confirmed hits are interior). `confirm_hits` checks it now instead
    of relying on that."""
    return _decoded(sx, sy) == _decoded(*delivered(sx, sy))


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

def _is_rollable(c):
    """Can the A-press that follows THIS endpoint fire the roll? (session 85)

    A fan candidate is a promise that Link rolls from the endpoint, and until now the fan checked
    only where he is standing and how fast. The A dispatch has a third condition:
    `checkNextActionFromButton` fires the ATTACK roll only from `land.ROLL_FROM` -- MOVE or ATN_MOVE
    -- and the endpoint's ``state`` IS the proc the A frame dispatches, because the aim is delivered
    on the endpoint frame and acted on the next one (`INPUT_DELAY`).

    Session 84's three unconfirmed draws are exactly this: all three read ``procs [24, 24, 6, 6, 6]``
    from `entry_search.confirm_entry`, proc 24 being `MOVE_TURN`, so the prefix left Link mid-turn and
    the A-press kept turning. The prune reads the same public C field the speedF prune does; it is
    `state.py`'s own dispatch condition, not a threshold anyone chose."""
    return (int(c.state) & 0xFF) in ROLL_FROM


def _fan_chunk(base, part, rows, jmax, tx, tz, nthreads, label, cap=ES.WALK_CAP, rollable=False,
               cs_seq=None):
    """Run one chunk of held sticks off ``base`` for ``jmax`` frames on the fleet, collecting each
    core's hits in the reference's write order. ``rows`` = the per-core schedule row (one frame, the
    held input); ``label(i, j)`` -> the plan value stored for core ``i`` at step ``j``. ``cap`` is
    `entry_search.walk_fan`'s speed prune, ``None`` to keep sub-cap endpoints (the key then carries
    speedF). Returns ``(writes, cores, alive)`` -- ``cores`` are the post-run junction states.

    ``rollable`` is the THIRD prune, and it is the one session 84's failures asked for: an endpoint is
    only a candidate if the A-press that follows it actually rolls. See `_is_rollable`.

    ``cs_seq`` makes the CAMERA a per-frame input instead of the constant in ``rows`` (session 95):
    step ``j`` runs at ``cs_seq[j]``, which is what a C-stick held through the entry plan actually
    delivers (`entry_camera.cam_trail` -- gated 0-ULP against the wired camera). The caller slices it
    so index 0 is this chunk's FIRST stepped frame. A short sequence is an error rather than a clamp:
    clamping would hold the camera where the real one keeps ramping."""
    cores = [base.clone(base.pe.clone_state()) for _ in part]
    fleet = N.CourtyardFleet(cores, 1)
    fleet.set_schedule([[r] for r in rows])
    if cs_seq is not None and len(cs_seq) < jmax + 1:
        raise ValueError("cs_seq covers %d frames, the chunk steps %d" % (len(cs_seq), jmax + 1))
    writes = [[] for _ in part]
    alive = [True] * len(part)
    for j in range(jmax + 1):
        if cs_seq is not None:
            fleet.set_schedule([[tuple(r[:4]) + (int(cs_seq[j]),)] for r in rows])
        fleet.run_par(1, nthreads)
        for i, c in enumerate(cores):
            if not alive[i]:
                continue
            if math.hypot(c.pos_x - tx, c.pos_z - tz) > ES.FOLLOW_BAR:
                alive[i] = False              # she is moving from here on: the branch is dead
                continue
            if j < 1 or (cap is not None and c.speedF != cap):
                continue
            if rollable and not _is_rollable(c):
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
              cap=ES.WALK_CAP, rollable=True, hold=None, cs_trail=None):
    """TWO-SEGMENT holds: stick S1 for j1 frames, then S2 for j2 -- the lever left once stride 1 x 7
    bases has saturated the one-segment fan (measured, `_notes/s81_saturation.py`).

    The junction states are the first segment's own cores after j1 frames (no re-simulation), so the
    cost is the second segment only: ``|S1| x |j1| x |S2| x j2max`` frames. Keys are the same
    ``(endpoint, m351C)``; the plan is ``(n0, sx1, sy1, j1, sx2, sy2, j2)``, a 7-tuple -- which is
    what tells `confirm_entry` it is a two-segment plan. A junction off the speedF 17 cap or past the
    follow bar is not a junction and is dropped whole.

    BOTH segments run the DECODED alphabet (`stick_alphabet`), not the byte grid: duplicate bytes
    re-walk an identical prefix and re-fan an identical junction, which at ``s2_stride=1`` is 5.75x
    of the pass (session 84). Same keys, 5.75x fewer frames.

    ``rollable`` (on by default, session 85) drops endpoints the A-press cannot roll from --
    `_is_rollable`. It is a candidate filter and not a fleet saving: the frames are already stepped
    when it reads the proc.

    ``hold``/``cs_trail`` are the CAMERA axis (session 95, `entry_camera`): ``hold`` carries the
    entry plan's C-stick byte into the WIRED base replay, and ``cs_trail`` is the csangle that byte
    delivers per frame, counted from the arrival, injected into every fleet step. A slewing hold
    WITHOUT a trail is refused -- it would run the base at one camera and the fan at another, which
    is nothing a controller can deliver. With ``cs_trail`` the ``csangle`` argument is unused."""
    seed = seed or ES.console_seed()
    hold = dict(hold or dict(seed['log'][-1], buttons=0))
    if cs_trail is None and int(hold.get('substickX', 128)) != 128:
        raise ValueError("a C-stick hold of %s slews the base camera but not the fan's -- pass the"
                         " matching cs_trail (entry_camera.cam_trail)" % hold.get('substickX'))
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
                if cs_trail is not None:
                    # this step's absolute index from the arrival is n0 + (j - 1)
                    fl.set_schedule([[(sx1, sy1, 0, trg, int(cs_trail[n0 + j - 1]))]])
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
                        (_n, sx1, sy1, _j, _p[i][0], _p[i][1], jj), cap=cap, rollable=rollable,
                        cs_seq=None if cs_trail is None else cs_trail[n0 + j:])
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


def plan_frames(plan):
    """A plan's total DELIVERED walk frames: the base hold plus every segment's own hold. The
    objective's unit, and what `stream_search` ranks its hits by."""
    return plan[0] + sum(plan[3::3])


def capped(pairs, frames=None):
    """A fan stream with plans over ``frames`` walk frames dropped -- the objective as a PRUNE.

    `iter_fan2`'s shape arguments bound the fan but not the plan length (``j1=1,2 j2max=3 nbase=2``
    spans 2 to 6 frames), and a plan longer than the delivered floor is worth nothing whatever it
    clips: Dereck's constraint is that the herd loses ZERO frames (`[[tetrapush-frame-minimal]]`).
    Dropping them here saves the evaluation rather than sorting them to the bottom afterwards.

    Order-preserving, so a family-major stream stays family-major and `dedup_scope='family'` still
    bounds memory at one family."""
    if frames is None:
        return pairs
    return ((k, p) for k, p in pairs if plan_frames(p) <= frames)


# --------------------------------------------------------- the streaming eval
# It lives in `entry_score` since session 85 (this module was 880 lines and fan-vs-scoring is the
# clean seam). Re-exported name for name, so every caller and every gate keeps its import path.

from harness.tetrapush.entry_score import (          # noqa: E402,F401
    QUAL_CACHE, BAND_CACHE, WINDOW_FIXTURE, MIN_BAND, BAND_PROBE, BandTable, ref_entry, qualified,
    facing_window, parse_cell_spec, cell_scope, select_quals,
    family_of_plan, stream_search, draw_key, hit_draws, dedupe_near, lottery, distinct_near,
    near_families, subgrid_rate, confirm_hits, rescore, _f32_bits, _marginal, _expected_hits)


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
    print("  near-zero draws at a DEAD configuration (no band the ladder could find): %d   bands"
          " measured %d, of which %d past the global ref and %d needed the strong form"
          % (r['n_dead_lean'], r['n_bands_measured'], r.get('n_bands_escalated', -1),
             r.get('n_bands_strong', -1)))
    print("  near-miss (gap < %g): %d  (%d DISTINCT candidates)   E[hits] this pass %.3f"
          "  (%.3f at the lean-0 widths, the pre-s84 estimate)"
          % (r['near_gap'], r['n_near'], r.get('n_near_candidates', -1), r['expected_hits'],
             r.get('expected_hits_lean0', float('nan'))))
    print("  GENUINE: %d DISTINCT DRAWS, from %d walkable scorings of %d"
          % (r.get('n_hit_draws', -1), len(r['hits']), r['n_hits_raw']))
    if r.get('near_families'):
        # the saturation test; NOT the tail marginal (x-major grid). knowledge/strategy/
        # clip-lottery-draws.md#when-the-fine-knob-is-saturated-widen-the-prefix
        print("  draws/family by SUB-GRID (the coarser pass contained in this one):")
        for s in (2, 4, 8, 16):
            g = subgrid_rate(r, s)
            if g['families']:
                print("     stride %2d: %5d families -> %4d draws   %.4f/family"
                      % (s, g['families'], g['draws'], g['per_family']))
    if r.get('n_families'):
        print("  prefix families %d   near/family %.4f (cumulative)   %s (marginal, last batches)"
              % (r['n_families'], r['near_per_family'],
                 ("%.4f" % r['marginal_near_per_family'])
                 if r['marginal_near_per_family'] is not None else "-"))
    print("  best gaps: %s" % ["%.3e" % g for g in r['near'][:8]])
    for h in hit_draws(r['hits'])[:25]:
        # the CELL is printed beside the facing because it is the exit-angle atom and the objective's
        # own unit -- rightmost cell wins, but only at the frame floor (clip-exit-angle.md)
        print("  plan %s  frames %d  cell %4d facing %5d thrust %2d  entry (%r,%r) m351C %5d"
              "  resid %+.3e"
              % (h['plan'], plan_frames(h['plan']), ES.aim_cell(h['facing']),
                 h['facing'], h['thrust'], h['entry'][0], h['entry'][1], h['m351C'], h['resid']))
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
    carries near/family cumulative AND marginal, and the marginal rate is the stop signal.

    Two trailing ``name=value`` tokens SCOPE the pass, and both are the objective written as a prune:

    ``cells=`` the configurations (`entry_score.parse_cell_spec`): ``lobe2``, ``right``,
    ``2561,2562``, ``2564-2570``, or a mix. Session 92's productive set is 40 configurations where
    every pass before it ran 6, and evaluation is per candidate per configuration -- so a wide pass at
    the whole set is most of a day, while the cells the objective wants
    (`knowledge/strategy/clip-exit-angle.md`: as far to Link's right as the seam allows) are a few.

    ``frames=`` the plan-length cap. ``j1``/``j2max``/``nbase`` bound the fan's shape but not its
    plan LENGTH -- ``j1=1,2 j2max=3 nbase=2`` spans 2 to 6 frames -- and a plan over the floor is
    worth nothing here whatever it clips (`[[tetrapush-frame-minimal]]`: the herd must lose ZERO
    frames, so session 91's own note is "do not bring him a 5-frame plan"). Capping the stream drops
    those before they are evaluated instead of ranking them afterwards.

    ``leans=`` the ENTRY-LEAN scope (`entry_lean.parse_lean_spec`): ``paying:2553``, ``top8``, or a
    lean list. ``thrusts=`` narrows the same way inside a cell. Both are cost knobs and weak ones on a
    frame-floor pass -- the FAN generation dominates it and a lean filter runs downstream of the
    stepping, so they save evaluation only; they pay when the configuration count is large. Neither is a
    claim about what it drops: the delivered console clip's own lean has zero band width (`entry_lean`).

    All default to off, which is every pass through session 91."""
    # deferred: `entry_lean` sits ABOVE this module (its census drives `iter_fan2`), so the CLI reaches
    # up rather than the fan reaching sideways
    from harness.tetrapush import entry_lean as EL
    warnings.simplefilter('ignore')
    pos = [a for a in argv if '=' not in a]
    opt = dict(a.split('=', 1) for a in argv if '=' in a)
    s1_stride = int(pos[0]) if pos else 32
    j1 = tuple(int(x) for x in pos[1].split(',')) if len(pos) > 1 else (2, 4, 6)
    s2_stride = int(pos[2]) if len(pos) > 2 else 1
    j2max = int(pos[3]) if len(pos) > 3 else 6
    nbase = int(pos[4]) if len(pos) > 4 else 2
    spec = opt.get('cells')
    frames = int(opt['frames']) if 'frames' in opt else None
    thrusts = tuple(int(x) for x in opt['thrusts'].split(',')) if 'thrusts' in opt else None
    leans = EL.parse_lean_spec(opt['leans']) if 'leans' in opt else None
    kw = dict(base_frames=tuple(range(nbase)), s1_stride=s1_stride, j1=j1,
              s2_stride=s2_stride, j2max=j2max)
    quals = qualified()
    if spec is not None or thrusts is not None:
        cells = parse_cell_spec(spec) if spec is not None else None
        if cells is not None:
            sc = cell_scope(quals, cells)
        quals = select_quals(quals, cells=cells, thrusts=thrusts)
        print("scope cells=%r thrusts=%r -> %d of %d configurations at cells %s"
              % (spec, thrusts, len(quals), len(qualified()),
                 sorted({ES.aim_cell(q['facing']) for q in quals})))
        if cells is not None and sc['not_aimable']:
            print("  NOT AIMABLE at csangle %d (the camera lever, not a barren cell): %s"
                  % (ES.CSANGLE, sc['not_aimable']))
        if cells is not None and sc['barren']:
            print("  qualified and barren: %s" % (sc['barren'],))
    if leans:
        print("lean scope %r -> %d entry leans %s"
              % (opt['leans'], len(leans), list(leans[:12]) + (['...'] if len(leans) > 12 else [])))
    print("S1 alphabet %d draws (of %d byte pairs at stride %d), S2 %d (of %d at stride %d)%s"
          % (len(stick_alphabet(s1_stride)), len(stick_grid(s1_stride)), s1_stride,
             len(stick_alphabet(s2_stride)), len(stick_grid(s2_stride)), s2_stride,
             ("   plans capped at %d frames" % frames) if frames else ""))
    stream = EL.select_by_lean(capped(iter_fan2(progress=True, **kw), frames), leans)
    r = stream_search(stream, quals=quals, progress=True,
                      family_of=family_of_plan, dedup_scope='family')
    _report(r, 'seg2_a%d_j%s_s%d_j%d_b%d%s%s%s%s'
            % (s1_stride, '-'.join(str(j) for j in j1), s2_stride, j2max, nbase,
               ('_c%s' % spec.replace(',', '.')) if spec else '',
               ('_f%d' % frames) if frames else '',
               ('_t%s' % '.'.join(str(t) for t in thrusts)) if thrusts else '',
               ('_l%s' % opt['leans'].replace(',', '.').replace(':', '')) if leans else ''),
            dict(kw, j1=list(j1), base_frames=list(kw['base_frames']), cell_spec=spec,
                 cells=list(parse_cell_spec(spec)) if spec else None, max_frames=frames,
                 thrusts=list(thrusts) if thrusts else None,
                 lean_spec=opt.get('leans'), leans=list(leans) if leans else None))



def _cmd_confirm(argv):
    """Replay every hit in a pass's json with a real A-press and report what survives.

    ``xengine`` adds the cross-engine filter (`cross_engine.agree`) to the same loop, which is where
    session 88 learned it belongs -- see `entry_score.confirm_hits`. The three filters are
    independent and each has rejected candidates the other two passed."""
    warnings.simplefilter('ignore')
    if not argv:
        raise SystemExit("usage: confirm <hits json> [all] [xengine]   (written by search1/search2)")
    tag = argv[0][len('hits_'):] if argv[0].startswith('hits_') else argv[0]
    path = argv[0] if os.path.exists(argv[0]) \
        else os.path.join(_rb, '_generated', 's81', 'hits_%s.json' % tag.replace('.json', ''))
    r = json.load(open(path))
    xe = 'xengine' in argv
    # one replay per DRAW by default -- the extra prefixes are alternative deliveries of an entry
    # already confirmed, and a pass can carry a hundred of them. `all` replays every one.
    hits = r['hits'] if 'all' in argv else hit_draws(r['hits'])
    print("%s: %d hits to confirm (%d walkable scorings collapse to %d draws)%s"
          % (os.path.basename(path), len(hits), len(r['hits']), len(hit_draws(r['hits'])),
             "   [+ cross-engine]" if xe else ""))
    rows = confirm_hits(hits, progress=True, cross_engine=xe)
    ok = [x for x in rows if x['confirm']['all_ok']]
    nd = [x for x in ok if not x['deliverable']]
    print("\nCONFIRMED %d of %d   (of which %d would be REWRITTEN by dtm_make and are not"
          " deliverable as scored)" % (len(ok), len(rows), len(nd)))
    for x in ok:
        h, m = x['hit'], x['confirm']['measured']
        print("  plan %s  aim %s  facing %d thrust %d  entry (%r,%r)  resid %+.3e  frames %d%s%s"
              % (h['plan'], h['aim'], h['facing'], h['thrust'], m['entry'][0], m['entry'][1],
                 h['resid'], h['plan'][0] + sum(h['plan'][3::3]),
                 "" if x['deliverable'] else "   [NOT DTM-DELIVERABLE]",
                 "" if not xe or x['agrees'] else
                 "   [%s]" % ("COMPOSITE BLOCKS THE LUNGE" if x['blocked'] else "CROSS-ENGINE DIFF")))
    if xe:
        good = [x for x in ok if x['deliverable'] and x['agrees']]
        print("\nDELIVERABLE (confirmed + DTM-clean + both engines agree): %d of %d"
              % (len(good), len(rows)))
        if good:
            print("frame floor among the deliverable: %d"
                  % min(x['hit']['plan'][0] + sum(x['hit']['plan'][3::3]) for x in good))
    out = path.replace('.json', '_confirmed.json')
    json.dump(rows, open(out, 'w'), indent=1)
    print("wrote %s" % out)


def _cmd_rescore(argv):
    """Ask a finished pass's hits again, on the engine as it stands now."""
    warnings.simplefilter('ignore')
    if not argv:
        raise SystemExit("usage: rescore <hits json | confirmed json>")
    path = argv[0] if os.path.exists(argv[0]) \
        else os.path.join(_rb, '_generated', 's81', argv[0])
    r = json.load(open(path))
    hits = [x['hit'] for x in r] if isinstance(r, list) else r['hits']
    rows = rescore(hits, progress=True)
    kept = [x for x in rows if x['kept']]
    print("\nKEPT %d of %d" % (len(kept), len(rows)))
    for x in sorted(kept, key=lambda x: (x['hit']['plan'][0] + sum(x['hit']['plan'][3::3]),
                                         abs(x['resid']))):
        h = x['hit']
        print("  plan %s  aim %s  facing %d thrust %d  m351C %d  resid %+.4e (was %+.4e)"
              "  frames %d" % (h['plan'], h['aim'], h['facing'], h['thrust'], h['m351C'],
                               x['resid'], x['was'], h['plan'][0] + sum(h['plan'][3::3])))
    out = path.replace('.json', '_rescored.json')
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
    elif cmd == 'rescore':
        _cmd_rescore(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
