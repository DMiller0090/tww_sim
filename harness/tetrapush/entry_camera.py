"""THE CAMERA IS A FREE INPUT CHANNEL INSIDE THE ENTRY PLAN (session 95).

THE PRICE, FIRST, because razor rule 13 says a lever is priced in the objective's own currency before
any candidate is bought. The entry plan runs AFTER the escape atom -- log rows 78.. of
`fixtures/courtyard_entry_s86_console.json` -- and every one of those console frames carries
``substickX == 128``. The C-stick channel there is IDLE: the atom has already fired, so nothing
downstream needs the camera frozen, and a slew inside the entry plan cannot cost a frame. What IS
bounded is the REACH: from the arrival, a held C-stick byte moves csangle **-716..+714 BAM by the 4th
entry frame** (`cam_trail`, over the DELIVERED bytes 1..254), with a 1-frame delay and a fine ladder in
between (byte 96/160 is -5/+4 BAM at frame 4).

WHY THIS IS NOT THE AXIS SESSION 83 CLOSED. s83 priced the camera on the AIM side and was right there:
the roll's schedule is quantized to the console sine cell, the aim alphabet already reaches both cells
of the window it was measured against, and a slew can only re-index which stick byte lands in a cell
(`history/entry-search-s81-camera-lever.md`). This is the WALK side, and s83 priced that against the
WRONG GRID: it counted 3612 of 4096 direction cells reachable at the frozen camera, over the whole
stick grid at ``msd_min=0``. The fan cannot use that grid -- it keeps only endpoints at the speedF 17
cap, so its alphabet is the **cap-magnitude** one, 2280 decoded angles reaching **1736 of 4096 cells,
42.4%**. A camera offset slides that 42% subset across the circle: 6.3% of the alphabet changes cell per
BAM, the union over the reachable slew is all 4096, and two cameras 16 BAM apart command a fully
different set of world directions. So a different camera is a **different discrete entry set**, which
is exactly what session 94 ran out of (2.4x the candidates, a bit-identical argmin).

Measured at cell 2553 on one bounded 157k-candidate fan (`_notes/s95_cam_probe.py`), closest approach
to the residual zero: frozen **1.49e-3**, +100 BAM 9.9e-5, +200 BAM **2.9e-5**, +700 BAM 6.0e-5 --
against **3.29e-4** from session 94's exhausted 3.2M-candidate stride-1 pass at the frozen camera.

WHAT A CAMERA DRAW IS, so the count stays honest. A held byte's TRAIL is the csangle per frame; two
bytes with the same trail over the plan's frames are ONE draw, not two (`camera_alphabet` dedupes on
the trail, the same discipline `clip-lottery-draws.md` imposes on aims and held sticks). And the trail
must be the DELIVERED one: `dtm_make.cal` clamps a C-stick 255 to 254 and 0 to 1 exactly as it does the
main stick (`[[octagon-clamp-decode-bug]]`), so the alphabet is built on bytes 1..254.

    python -m harness.tetrapush.entry_camera reach [frames]
    python -m harness.tetrapush.entry_camera alphabet [frames]
    python -m harness.tetrapush.entry_camera cells            # the walk-side grid, per camera
    python -m harness.tetrapush.entry_camera hull [bytes]     # does a camera MOVE the reachable cloud?
    python -m harness.tetrapush.entry_camera probe [cell] [bytes] [frames]
    python -m harness.tetrapush.entry_camera search [cell] [bytes] [frames] [s1,j1,s2,j2max,nbase] [thr]
        # bytes: `128,160` | `all` (82 held trails) | `span:N` | `seg:STEP` (the segmented alphabet)
        #      | `walk:STEP` <- USE THIS: one aimable camera per distinct walk trail (`walk_cameras`)
"""
import json
import math
import os
import sys
import time
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import entry_search as ES
from harness.tetrapush import two_roll as TR

TRAIL_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_cam_trails_s95.json')

#: The C-stick byte the console-delivered entry plan holds on every frame -- a neutral C-stick, which
#: is what froze the camera at `entry_search.CSANGLE`.
NEUTRAL = 128

#: Frames of trail a frame-floor pass needs: the plan's own frames plus the A-press and the roll entry.
TRAIL_FRAMES = 10

_TRAILS = {}


def delivered_byte(b):
    """A C-stick byte as a DTM actually delivers it -- `tools/dtm_make.cal`, which clamps both sticks."""
    return {255: 254, 0: 1}.get(int(b), int(b))


def deliverable_bytes(step=1):
    """The C-stick alphabet that survives delivery: 1..254 (0 and 255 are aliases of 1 and 254)."""
    return sorted({delivered_byte(b) for b in range(0, 256, step)})


def label(subx):
    """A camera's identity for a report: the held byte, or the per-frame sequence that draws it."""
    seq = as_seq(subx)
    return str(seq[0]) if len(seq) == 1 else ','.join(str(b) for b in seq)


def as_seq(subx):
    """A camera input as the per-frame DELIVERED byte sequence -- a scalar byte is the held case."""
    return ([delivered_byte(subx)] if isinstance(subx, (int, float))
            else [delivered_byte(x) for x in subx])


def cam_trail(subx, frames=TRAIL_FRAMES, seed=None, env=None, cache=True):
    """The csangle Link's physics DECODES against on each entry-plan frame, under C-stick ``subx``.

    Index 0 is the first frame after the arrival. Measured on the WIRED camera (`entry_search.
    continue_walk` integrates `LandCamera`), never modelled here -- the fan then injects these values
    and `tests/test_entry_camera.py` gates the two against each other 0-ULP.

    It is a pure function of the input: the yaw target moves only with C-stick X and Link's motion moves
    only the camera CENTRE (`knowledge/mechanics/land-camera.md`), so one trail serves every held main
    stick in the fan -- gated, not assumed.

    ``subx`` is a byte (held for the whole plan) or a SEQUENCE of bytes, one per frame, short sequences
    holding their last value. The sequence form is the axis's own extension: the C-stick is idle every
    frame, not just uniformly, so the reachable trails are every camera PATH and not the 82 ramps a
    single held byte draws."""
    seq = as_seq(subx)
    key = (tuple(seq), int(frames))
    if cache and key in _TRAILS:
        return _TRAILS[key]
    seed = seed or ES.console_seed()
    base = dict(seed['log'][-1], buttons=0, substickY=0)
    holds = [dict(base, substickX=seq[min(k, len(seq) - 1)]) for k in range(int(frames))]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        _run, rows = ES.continue_walk(holds, env=env)
    trail = tuple(int(r['csangle']) & 0xFFFF for r in rows)
    if cache:
        _TRAILS[key] = trail
    return trail


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def trail_offsets(trail):
    """A trail as BAM off the frozen camera, which is the only part that changes any physics."""
    return tuple(_s16(cs - ES.CSANGLE) for cs in trail)


def camera_alphabet(frames=TRAIL_FRAMES, step=1, seed=None, env=None, path=TRAIL_FIXTURE,
                    refresh=False):
    """The camera's real alphabet: ``[(subx, trail)]``, one entry per DISTINCT trail.

    Deduped because two bytes that deliver the same csangle sequence are the same draw -- counting
    them separately is how the aim axis priced at 8x (`clip-lottery-draws.md`). The representative is
    the byte NEAREST NEUTRAL of its class, so a plan asks for the smallest C-stick that buys the
    camera it wants.

    Cached to `TRAIL_FIXTURE`, keyed by the frame count and the stride it was measured at."""
    if not refresh and path and os.path.exists(path):
        d = json.load(open(path))
        if d.get('frames') == int(frames) and d.get('step') == int(step) \
                and d.get('csangle') == ES.CSANGLE:
            return [(int(b), tuple(t)) for b, t in d['alphabet']]
    by = {}
    for b in deliverable_bytes(step):
        t = cam_trail(b, frames, seed=seed, env=env)
        cur = by.get(t)
        if cur is None or abs(b - NEUTRAL) < abs(cur - NEUTRAL):
            by[t] = b
    out = sorted(((b, t) for t, b in by.items()), key=lambda bt: bt[0])
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(dict(source='harness/tetrapush/entry_camera.camera_alphabet, session 95',
                       note="A MODEL OUTPUT, not a console capture. THE CSANGLE TRAIL a held C-stick"
                            " byte delivers on each entry-plan frame, measured on the wired"
                            " LandCamera from the console-confirmed arrival. Deduped on the trail:"
                            " two bytes with one trail are ONE camera draw. Bytes are the DELIVERED"
                            " ones (dtm_make.cal clamps 0/255).",
                       frames=int(frames), step=int(step), csangle=ES.CSANGLE,
                       neutral=NEUTRAL,
                       alphabet=[[b, list(t)] for b, t in out]), open(path, 'w'), indent=1)
    return out


def segmented_alphabet(cells, frames=4, step=16, switch=None, seed=None, env=None):
    """Camera draws from a C-stick that CHANGES mid-plan: ``[(seq, trail)]`` for ``seq = [b1]*k + [b2]``.

    A held byte draws one ramp, and the 82 of them are the whole axis only because the C-stick was
    assumed constant. It is idle on EVERY entry frame, so any path is deliverable, and a switch at
    frame k reaches trails no ramp does -- the same reach, a different route through it.

    Deduped on the trail as `camera_alphabet` is, and filtered to the paths that keep ``cells``
    aimable, because a camera that cannot aim the scope is not a draw for it (`aim_at`)."""
    want = [int(c) for c in ([cells] if isinstance(cells, int) else cells)]
    switch = list(range(1, int(frames))) if switch is None else list(switch)
    bytes_ = deliverable_bytes(step)
    seen, out = {}, []
    for b1 in bytes_:
        for k in switch:
            for b2 in bytes_:
                seq = [b1] * k + [b2]
                t = cam_trail(seq, max(TRAIL_FRAMES, frames + 2), seed=seed, env=env)
                if t in seen:
                    continue
                seen[t] = seq
                if any(aim_at(c, seq, frames) is not None for c in want):
                    out.append((seq, t))
    return out


#: How many C-stick BYTES the walk-side trail carries -- MEASURED, see `walk_channel`.
WALK_CHANNEL = 2


def walk_channel(frames=4, step=32, seed=None, env=None, sample=400):
    """The smallest byte prefix that DECIDES the ``frames``-frame walk trail -- measured, not assumed.

    Session 95 enumerated cameras as C-stick PATHS and read the walk supply off the path count, which
    over-counts badly: a second switch point multiplies the paths 8x and the `fan_steps` trails 7.7x
    while leaving the distinct 4-frame walk trails **bit-identical** (64 -> 64 at byte stride 32,
    196 -> 196 at stride 16). The reason is this: the walk trail is a function of the first
    `WALK_CHANNEL` bytes, so the walk supply is (deliverable bytes)^2 and NOT (bytes)^frames.

    It is also the mechanism behind the session-95 dedup observation that had no explanation -- 41 of 49
    walk groups reported a bit-identical draw set because those cameras differ only in bytes the walk
    cannot see -- and behind the lever `walk_cameras` spends: if the walk cannot see the later bytes but
    the AIM frame can (`aim_frame`), then the two are INDEPENDENT knobs on one channel."""
    import itertools
    b = deliverable_bytes(step)
    seqs = [list(s) for s in itertools.product(b, repeat=int(frames))][:int(sample)]
    for k in range(1, int(frames) + 1):
        if all(cam_trail(s, TRAIL_FRAMES, seed=seed, env=env)[:frames]
               == cam_trail(s[:k], TRAIL_FRAMES, seed=seed, env=env)[:frames] for s in seqs):
            return k
    return None


def walk_cameras(cells, frames=4, step=16, tail_step=32, seed=None, env=None):
    """One AIMABLE camera per DISTINCT walk trail -- ``[(seq, trail)]``, the axis's real supply.

    This is the axis session 95 measured, spent the way `walk_channel` says it is shaped. Two facts
    compose into a lever:

    - the walk trail is decided by the first `WALK_CHANNEL` bytes, so enumerating C-stick paths past
      that buys **no** new walk cloud -- session 95's segmented alphabets were paying for aim variants
      it then deduped away;
    - a later byte moves the trail at `aim_frame` while leaving the walk trail bit-identical, and that
      index is what decides whether the scope is aimable at all.

    So aimability is a FREE knob, and the 18 of 82 held cameras session 95 had to skip as "not aimable"
    were not a bound on the axis -- they were an artifact of enumerating held bytes, where one byte has
    to serve both jobs. Here the walk pair is chosen first and a TAIL byte is then searched for one that
    keeps ``cells`` aimable, nearest-neutral first, so a walk trail is only dropped when NO tail rescues
    it. What is dropped is returned as well, never swallowed (`cell_scope`'s discipline)."""
    want = [int(c) for c in ([cells] if isinstance(cells, int) else cells)]
    need = max(TRAIL_FRAMES, int(frames) + 2)
    tails = sorted(deliverable_bytes(tail_step), key=lambda x: abs(x - NEUTRAL))
    keep, dead = {}, {}
    for b0 in deliverable_bytes(step):
        for b1 in deliverable_bytes(step):
            walk = cam_trail([b0, b1], need, seed=seed, env=env)[:int(frames)]
            if walk in keep:
                continue
            for t in tails:
                seq = [b0, b1, t]
                if all(aim_at(c, seq, frames) is not None for c in want):
                    keep[walk] = seq
                    dead.pop(walk, None)
                    break
            else:
                dead.setdefault(walk, [b0, b1])
    return (sorted(([b for b in seq], cam_trail(seq, need, seed=seed, env=env))
                   for seq in keep.values()),
            sorted(dead.values()))


def fan_steps(**shape):
    """How many frames a fan of this SHAPE actually steps from the arrival.

    Not the plan's frame cap: `entry_fan` records the endpoint after ``j + 1`` steps for a plan of ``j``
    delivered frames, and the second segment runs to ``j2max``. So the camera values that can reach a
    candidate run to ``max(base_frames) + max(j1) + j2max + 1``, and a camera is only equivalent to
    another over THAT prefix."""
    return (max(shape.get('base_frames', (3, 4))) + max(shape.get('j1', (2, 4, 6)))
            + int(shape.get('j2max', 6)) + 1)


def dedupe_cameras(subxs, steps, seed=None, env=None):
    """Collapse a camera list onto the trails a fan can TELL APART -- ``[(subx, trail_prefix)]``.

    The measurement that forced this (session 95): a segmented alphabet of 137 cameras carried only 49
    distinct 4-frame walk trails, and 41 of those 49 groups reported a bit-identical draw set -- the
    other cameras differed only in the AIM frame, which re-aims the same walk cloud rather than drawing
    a new one. Deduping on the STEPPED prefix took the axis from 0.077 to ~0.157 draws per second.

    Eight of the 49 groups did NOT agree, which is exactly why the key is `fan_steps` and not the plan's
    frame cap: the fan steps past the cap, so a camera value after the last walk frame still reaches
    some candidates. Group on what the fan steps and the equivalence is real.

    ``steps`` IS the budget decision, and the two useful values are far apart (session 96 measured
    both). At `fan_steps` this is lossless and collapses **nothing** on either segmented alphabet
    (0 of 137, 0 of 440) -- the fan tells every trail apart, so the "2x cheaper" reading of session 95
    was never what this function returned. At the plan's own ``frames`` it collapses hard and keeps 79%
    of the draws for 39% of the clock, rate-positive by 2x, because the cameras it merges differ only in
    bytes the WALK cannot see (`walk_channel`)."""
    seen, out = set(), []
    for s in subxs:
        t = cam_trail(s, max(TRAIL_FRAMES, int(steps)), seed=seed, env=env)[:int(steps)]
        if t in seen:
            continue
        seen.add(t)
        out.append((s, t))
    return out


def reach(frames=4, **kw):
    """How far the camera can be slewed by frame ``frames`` of the entry plan, in BAM off frozen.

    Returns dict(lo, hi, n_distinct, per_byte) -- the bound every camera claim is argued inside."""
    alpha = camera_alphabet(**kw)
    offs = {}
    for b, t in alpha:
        if len(t) < frames:
            raise ValueError("trail covers %d frames, asked for %d" % (len(t), frames))
        offs[b] = _s16(t[frames - 1] - ES.CSANGLE)
    return dict(frames=int(frames), lo=min(offs.values()), hi=max(offs.values()),
                n_distinct=len(set(offs.values())), per_byte=offs)


# ---------------------------------------------------- the aim side: the camera moves the alphabet too

def plan_frames(plan):
    """A plan's WALK frames -- its base hold plus every segment's length, the ``n`` `aim_frame` wants.

    `entry_fan`'s plans are ``(n0, sx, sy, j)`` or ``(n0, sx1, sy1, j1, sx2, sy2, j2)``, and a pass's
    frame CAP is an upper bound on this, not the value: one pass carries plans of several lengths."""
    return int(plan[0]) + sum(int(j) for j in plan[3::3])


def aim_frame(frames):
    """Which trail index the ROLL'S FACING latches against, for a plan of ``frames`` walk frames.

    MEASURED, not reasoned (`_notes/s95_aim_frame.py`, and the `roll_fidelity` rule: fire the roll and
    read the facing back). The A-press sits on trail index ``frames`` -- `entry_search.confirm_entry`
    builds the plan's holds then the aim frame -- and the target is computed when the input is ACTED,
    one frame later, so the facing is ``decoded_aim + 0x8000 + trail[frames + 1]``. Unanimous over four
    cameras spanning -1619..+1420 BAM, where the neighbouring indices are 90-460 BAM wrong.

    This is why a camera is not free on the aim side even though it costs no frame: the camera is still
    RAMPING at the dispatch, so a hard slew moves the whole aim alphabet -- at subx 249 the same bytes
    that reach cell 2551 frozen roll into cell 2640."""
    return int(frames) + 1


def aim_at(cell, subx, frames=4):
    """The aim bytes that reach ``cell`` at the camera THIS plan arrives with, or None.

    None is a real verdict and not a gap in the alphabet: it is `entry_score.cell_scope`'s "not aimable
    at this camera" one camera at a time, and it is what bounds the axis -- of 82 camera draws, cell
    2553 is aimable at **64**."""
    cs = cam_trail(subx)[aim_frame(frames)]
    for f, byts, sib in ES.aim_cells(cs):
        if ES.aim_cell(f) == int(cell):
            return dict(facing=f, aim=list(byts), siblings=sib, csangle=cs)
    return None


def aimable_cameras(cell, subxs=None, frames=4):
    """The cameras that keep ``cell`` aimable -- ``[(subx, aim_at(...))]``. The pass's real scope."""
    subxs = [b for b, _t in camera_alphabet()] if subxs is None else list(subxs)
    out = []
    for b in subxs:
        a = aim_at(cell, b, frames)
        if a is not None:
            out.append((delivered_byte(b), a))
    return out


# ------------------------------------------------- the walk side: which directions a camera commands

def walk_alphabet(msd_min=1.0):
    """The decoded stick angles a fan candidate can hold: the CAP-magnitude ones.

    The fan keeps only endpoints at ``speedF == WALK_CAP``, and a held stick walks at ``msd`` of the
    cap, so a sub-cap stick cannot produce one -- gated in `tests/test_entry_camera.py` against a real
    fan rather than argued from the speed law."""
    return [a for a, _b in TR.reachable_stick_fan(msd_min=msd_min)]


def walk_cells(csangle=None, angles=None):
    """The sine-table cells the walk alphabet commands at this camera -- the set the entry cloud is
    drawn from. ``cM_ssin_s16`` reads ``jmaTable[angle >> 4]``, so the CELL is the atom here exactly as
    it is for the aim (`entry_search.aim_cell`)."""
    cs = ES.CSANGLE if csangle is None else int(csangle)
    return {((a + 0x8000 + cs) & 0xFFFF) >> 4 for a in (angles or walk_alphabet())}


def cell_census(offsets=None, angles=None):
    """What a camera slew does to the walk grid: per offset, the cell count, how many cells it moves
    off the frozen set, and the running union. The honest form of "the camera re-draws the cloud"."""
    angles = angles or walk_alphabet()
    frozen = walk_cells(ES.CSANGLE, angles)
    offsets = list(range(-16, 17)) if offsets is None else list(offsets)
    union, rows = set(frozen), []
    for d in offsets:
        c = walk_cells(ES.CSANGLE + d, angles)
        union |= c
        rows.append(dict(off=d, n_cells=len(c), n_new_vs_frozen=len(c - frozen),
                         n_union=len(union)))
    return dict(n_alphabet=len(angles), n_frozen=len(frozen), rows=rows,
                n_union=len(union), union_ratio=len(union) / float(len(frozen)))


# ------------------------------------------------------------------ the fan, at a commanded camera

def fan_cam(subx, seed=None, env=None, frames=None, **kw):
    """`entry_fan.iter_fan2` with the C-stick held at ``subx`` -- the trail carried into the wired base
    replay AND injected into every fleet step, so the whole plan runs at a camera a controller can
    actually deliver.

    ``frames`` caps the plan length (`entry_fan.capped`), which is what makes a pass frame-floor.

    ``subx`` may be a per-frame SEQUENCE (`segmented_alphabet`). The fan's base frames are one held
    input, so a sequence that changes inside the base is refused rather than approximated -- the base
    replay would deliver a C-stick the plan does not ask for."""
    from harness.tetrapush import entry_fan as EF
    seed = seed or ES.console_seed()
    seq = as_seq(subx)
    for n0 in kw.get('base_frames', (3, 4)):
        if set(seq[:n0]) - {seq[0]}:
            raise ValueError("the C-stick changes inside the %d base frames (%s) -- the fan holds one"
                             " input there" % (n0, seq[:n0]))
    need = int(kw.get('j2max', 6)) + max(kw.get('j1', (2, 4, 6))) + max(kw.get('base_frames', (3, 4)))
    trail = cam_trail(seq, max(TRAIL_FRAMES, need + 2), seed=seed, env=env)
    hold = dict(seed['log'][-1], buttons=0, substickX=seq[0], substickY=0)
    stream = EF.iter_fan2(seed=seed, env=env, hold=hold, cs_trail=trail, **kw)
    return EF.capped(stream, frames)


PROBE_FAN = dict(base_frames=(0, 1), s1_stride=16, j1=(2,), s2_stride=4, j2max=2)


def probe(cells, subxs=(NEUTRAL,), frames=4, quals=None, seed=None, env=None, fan=None,
          progress=False):
    """CLOSEST APPROACH per camera: the smallest ``|resid|`` a bounded fan reaches at each
    configuration, and where.

    This is the measurement a camera pass must be justified by, for the reason `_notes/
    s93_reach_probe.py` exists: `stream_search` drops everything past `BAND_PROBE`, so a pass can
    never say whether it missed by a ULP or by twenty units. Here the miss is the number."""
    from harness.tetrapush import entry_fan as EF
    seed = seed or ES.console_seed()
    tetra = seed['tetra']
    want = set(int(c) for c in ([cells] if isinstance(cells, int) else cells))
    quals = quals if quals is not None else EF.qualified(seed)
    cfgs = sorted((q for q in quals if ES.aim_cell(q['facing']) in want),
                  key=lambda q: (ES.aim_cell(q['facing']), q['thrust']))
    if not cfgs:
        raise ValueError("no productive configuration at cells %s" % sorted(want))
    shape = dict(PROBE_FAN, **(fan or {}))
    pool = ES.CtxPool()
    rows = []
    for subx in subxs:
        t0 = time.time()
        cand = {}
        for k, _plan in fan_cam(subx, seed=seed, env=env, frames=frames, **shape):
            cand.setdefault((ES.lean_at_roll(k[2]), ES.candidate_nspeed(k)), []).append(k)
        n = sum(len(v) for v in cand.values())
        for q in cfgs:
            fac, thrust = q['facing'], q['thrust']
            best, n_probe = None, 0
            for (lean, nsp), keys in cand.items():
                ctx, _sch, resid = pool.get(fac, lean, thrust, nspeed=nsp)
                ents = [ES.roll_entry((k[0], k[1]), fac, nsp) for k in keys]
                out = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1]) for e in ents], 0)
                for e, o in zip(ents, out):
                    r = resid(o)
                    n_probe += abs(r) < EF.BAND_PROBE
                    if best is None or abs(r) < abs(best[0]):
                        best = (r, e, lean, nsp, bool(o[0]))
            aim = aim_at(ES.aim_cell(fac), subx, frames)
            rows.append(dict(cell=ES.aim_cell(fac), facing=fac, thrust=thrust,
                             subx=as_seq(subx), aimable=aim is not None,
                             aim=(aim or {}).get('aim'),
                             offsets=list(trail_offsets(cam_trail(subx))[:frames]),
                             n_candidates=n, min_abs_resid=abs(best[0]), resid=best[0],
                             entry=list(best[1]), lean=best[2], nspeed=best[3],
                             genuine=best[4], n_inside_probe=n_probe, seconds=time.time() - t0))
            if progress:
                r = rows[-1]
                print("  subx %-9s (%+5d BAM @f%d) cell %d thr %2d: %7d cand  min |resid| %11.5g"
                      "  n<probe %4d%s%s  [%.0fs]"
                      % (label(r['subx']), r['offsets'][-1], frames, r['cell'], r['thrust'],
                         r['n_candidates'], r['min_abs_resid'], r['n_inside_probe'],
                         '  GENUINE' if r['genuine'] else '',
                         '' if r['aimable'] else '  NOT AIMABLE at its dispatch camera',
                         r['seconds']))
    return rows


def search(cells, subxs=(NEUTRAL,), frames=4, seed=None, env=None, fan=None, quals=None,
           thrusts=None, group_steps=None, progress=False, **kw):
    """A SCORED frame-floor pass per camera, aggregated -- `entry_fan.stream_search` under each trail.

    Every hit and near-miss carries the ``subx`` that produced it, because a camera hit is only
    reproducible with the C-stick that slewed there (`entry_search.confirm_entry` reads the same
    field). Per-camera results are kept whole so the rate can be read per DRAW of the camera axis
    rather than pooled -- `strategy/clip-search-budget.md`: a family is a budget unit only inside one
    plan shape, and a camera is a different shape.

    A camera that cannot AIM at the scope is skipped rather than scored: the residual is a property of
    the facing cell and so camera-independent, but the bytes that reach that cell are not (`aim_at`),
    and scoring a cell no A-press can deliver at this camera would be the "not aimable" half of
    `cell_scope` counted as candidates. The skipped cameras are reported, never swallowed.

    ``group_steps`` is the camera-dedup key in frames, defaulting to the lossless `fan_steps`. Pass
    ``WALK_CHANNEL`` (session 96's measured rate-positive setting) to merge cameras the WALK cannot tell
    apart; the pass reports which key it ran under, since a pass's own dedup key is part of its result
    exactly as its cell scope is."""
    from harness.tetrapush import entry_fan as EF
    seed = seed or ES.console_seed()
    quals = quals if quals is not None else EF.qualified(seed)
    want = EF.parse_cell_spec(cells) if isinstance(cells, str) else cells
    sel = EF.select_quals(quals, cells=want, thrusts=thrusts)
    scope = EF.cell_scope(quals, want)
    shape = dict(PROBE_FAN, **(fan or {}))
    # cameras a fan of this shape cannot tell apart are ONE pass, not two (`dedupe_cameras`)
    gsteps = fan_steps(**shape) if group_steps is None else int(group_steps)
    kept = dedupe_cameras(subxs, gsteps, seed=seed, env=env)
    n_collapsed = len(list(subxs)) - len(kept)
    out, skipped = [], []
    for subx, _trail in kept:
        b = as_seq(subx)
        aims = {int(c): aim_at(c, b, frames) for c in {ES.aim_cell(q['facing']) for q in sel}}
        live = [q for q in sel if aims.get(ES.aim_cell(q['facing'])) is not None]
        if not live:
            skipped.append(b)
            if progress:
                print("subx %3d: cell(s) %s not aimable at its dispatch camera -- skipped"
                      % (b, sorted(aims)))
            continue
        t0 = time.time()
        res = EF.stream_search(fan_cam(subx, seed=seed, env=env, frames=frames, **shape),
                               seed=seed, quals=live, family_of=EF.family_of_plan,
                               dedup_scope='family', progress=progress, **kw)
        # the aim belongs to the candidate's own plan length, NOT the pass's cap: the facing latches
        # against `trail[n + 1]`, and a slewing camera reads a different csangle at each n
        for h in res['hits']:
            n = plan_frames(h['plan'])
            a = aim_at(ES.aim_cell(h['facing']), b, n)
            h.update(substickX=b, plan_frames=n, aim=(a or {}).get('aim'),
                     aim_siblings=(a or {}).get('siblings'), aim_csangle=(a or {}).get('csangle'),
                     aim_deliverable=a is not None)
        for nd in res.get('near_detail', []):
            nd['substickX'] = b
            nd['plan_frames'] = plan_frames(nd['plan']) if nd.get('plan') else None
        res.update(substickX=b, offsets=list(trail_offsets(cam_trail(b))[:frames]),
                   aim_csangle_off=_s16(cam_trail(b)[aim_frame(frames)] - ES.CSANGLE),
                   n_configurations_aimable=len(live), cell_scope=scope, frames=frames,
                   thrusts=(None if thrusts is None else sorted(int(t) for t in thrusts)),
                   group_steps=gsteps, wall_seconds=time.time() - t0)
        out.append(res)
        if progress:
            print("subx %-9s (walk %+5d BAM, aim %+5d): %d cand / %d fam -> %d genuine, %d near,"
                  " E[hits] %.3f  [%.0fs]"
                  % (label(b), res['offsets'][-1], res['aim_csangle_off'], res['n_candidates'],
                     res['n_families'], res['n_hit_draws'], res['n_near'], res['expected_hits'],
                     res['wall_seconds']))
    if skipped and progress:
        print("%d of %d cameras skipped: the scope is not aimable at their dispatch csangle"
              % (len(skipped), len(list(subxs))))
    if n_collapsed and progress:
        print("%d cameras collapsed: their trails agree over the %d frames this pass groups on"
              % (n_collapsed, gsteps))
    for r in out:
        r['n_cameras_skipped'] = len(skipped)
        r['cameras_skipped'] = skipped
        r['n_cameras_collapsed'] = n_collapsed
    return out


def hull_shift(subxs, frames=4, fan=None, seed=None, env=None, stations=None, margin=1.0):
    """Does a camera move the reachable CLOUD, or only its fine structure?

    Session 93 closed the second lobe by measuring the walk hull and finding its stations outside
    (`entry_reach`). That negative was argued at ONE camera, so it owes this check -- and the two
    answers are different claims: the camera re-indexes which points inside the cloud a plan can land
    on (that is the axis), while the cloud's EXTENT is set by Link's heading, the speed cap and the turn
    rate, which no camera changes.

    Returns per camera the hull's bbox and area, plus -- for any ``stations`` given as
    ``[(x, z, facing)]`` -- whether the union hull reaches them. Use the union, never one camera: a
    negative has to be argued over the whole axis (`razor rule 12`)."""
    from harness.tetrapush import entry_reach as ER
    shape = dict(PROBE_FAN, **(fan or {}))
    rows, allpts = [], []
    for subx in subxs:
        pts = [(k[0], k[1]) for k, _p in fan_cam(subx, seed=seed, env=env, frames=frames, **shape)]
        allpts += pts
        h = ER.hull(pts)
        xs, zs = [p[0] for p in pts], [p[1] for p in pts]
        rows.append(dict(subx=as_seq(subx), n=len(pts), hull=[list(p) for p in h],
                         bbox=[min(xs), min(zs), max(xs), max(zs)], area=_poly_area(h)))
    union = ER.hull(allpts)
    out = dict(frames=frames, rows=rows, union_hull=[list(p) for p in union],
               union_area=_poly_area(union), n_points=len(allpts))
    if stations:
        got = []
        for x, z, facing in stations:
            ox, oz = ES.roll_entry((0.0, 0.0), facing)
            got.append(dict(station=[x, z], facing=facing,
                            in_union=ER.contains(union, (x - ox, z - oz), margin)))
        out['stations'] = got
    return out


def _poly_area(poly):
    """Shoelace -- the cloud's size, so "the camera moves the cloud" is a number and not an impression."""
    if len(poly) < 3:
        return 0.0
    s = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
            for i in range(len(poly)))
    return abs(s) / 2.0


def summarize(passes):
    """The camera axis priced as DRAWS, deduped ACROSS cameras -- the only honest total.

    `stream_search` dedupes inside one pass, and summing its `expected_hits` over cameras would count
    the overlap twice: neighbouring cameras command ~94% of the same directions, so they reach many of
    the SAME entries, and one entry at two cameras is one draw of the same lottery. Measured here, 243
    reported near-misses are **80 distinct draws** -- so the pooled figure is 3x the real one, which is
    the same "counting copies as discoveries" this search has paid for three times
    (`strategy/clip-lottery-draws.md`). Both are returned; ``expected_hits`` is the deduped one."""
    from harness.tetrapush import entry_fan as EF
    near = [(nd['gap'], {k: v for k, v in nd.items() if k != 'gap'})
            for p in passes for nd in p.get('near_detail', [])]
    ded = EF.dedupe_near(near)
    gap = passes[0].get('near_gap', 5e-3) if passes else 5e-3
    secs = sum(p['wall_seconds'] for p in passes)
    return dict(n_cameras=len(passes), n_genuine=sum(p['n_hit_draws'] for p in passes),
                n_near_reported=len(near), n_near=len(ded),
                expected_hits=EF.lottery(ded, gap),
                expected_hits_pooled=sum(p['expected_hits'] for p in passes),
                near_per_camera=(len(ded) / float(len(passes)) if passes else 0.0),
                seconds=secs, seconds_per_camera=(secs / float(len(passes)) if passes else 0.0),
                near_per_second=(len(ded) / secs if secs else 0.0),
                best_gap=min([g for g, _i in ded] or [None]))


# --------------------------------------------------------------------------- CLI

def _bytes_arg(s, frames=4, cells=(2553,)):
    """``"128,160,192"`` | ``"all"`` (the whole deduped held alphabet) | ``"span:N"`` (N bytes spread
    across it, neutral first) | ``"seg:STEP"`` (the SEGMENTED alphabet at that byte stride) |
    ``"walk:STEP"`` (ONE aimable camera per distinct walk trail -- `walk_cameras`, the shape the axis
    actually has, and the spec to use for a pass)."""
    if str(s).startswith('walk:'):
        step = int(str(s).split(':')[1])
        keep, dead = walk_cameras(cells, frames=frames, step=step)
        if dead:
            print("%d walk trails dropped: no tail byte keeps %s aimable"
                  % (len(dead), sorted(cells)))
        return [seq for seq, _t in keep]
    if str(s).startswith('seg:'):
        step = int(str(s).split(':')[1])
        return [seq for seq, _t in segmented_alphabet(cells, frames=frames, step=step)]
    if s in (None, '', 'all'):
        return [b for b, _t in camera_alphabet()]
    if str(s).startswith('span:'):
        alpha = [b for b, _t in camera_alphabet()]
        n = max(1, int(str(s).split(':')[1]))
        step = max(1, len(alpha) // n)
        out = alpha[::step]
        return ([NEUTRAL] + [b for b in out if b != NEUTRAL])[:n]
    return [int(x) for x in str(s).split(',')]


def _cmd_reach(argv):
    frames = int(argv[0]) if argv else 4
    r = reach(frames)
    print("camera reach at entry frame %d: %+d .. %+d BAM (%.2f .. %.2f deg), %d distinct offsets"
          " over %d deliverable bytes"
          % (frames, r['lo'], r['hi'], r['lo'] * 360.0 / 65536.0, r['hi'] * 360.0 / 65536.0,
             r['n_distinct'], len(r['per_byte'])))
    for b in sorted(r['per_byte'])[::16]:
        print("   subx %3d -> %+6d BAM   trail %s"
              % (b, r['per_byte'][b], list(trail_offsets(cam_trail(b))[:frames])))
    print("PRICE: zero frames -- the console entry plan holds substickX 128 on every frame")


def _cmd_alphabet(argv):
    frames = int(argv[0]) if argv else TRAIL_FRAMES
    alpha = camera_alphabet(frames=frames, refresh=bool(argv[1:] and argv[1] == 'refresh'))
    print("%d deliverable C-stick bytes -> %d DISTINCT camera trails over %d frames"
          % (len(deliverable_bytes()), len(alpha), frames))
    for b, t in alpha[::max(1, len(alpha) // 16)]:
        print("   subx %3d: %s" % (b, list(trail_offsets(t))))


def _cmd_cells(argv):
    offs = [int(x) for x in argv[0].split(',')] if argv else [-256, -64, -16, -4, -1, 1, 4, 16, 64,
                                                              256, 700]
    c = cell_census(offs)
    print("walk alphabet at the cap: %d decoded angles -> %d of 4096 sine cells at the frozen camera"
          " (%.1f%%)" % (c['n_alphabet'], c['n_frozen'], 100.0 * c['n_frozen'] / 4096))
    for r in c['rows']:
        print("   off %+5d: %d cells, %4d of them NOT reachable frozen, union %d"
              % (r['off'], r['n_cells'], r['n_new_vs_frozen'], r['n_union']))
    print("union over the offsets asked for: %d cells (%.2fx the frozen set)"
          % (c['n_union'], c['union_ratio']))


def _cmd_probe(argv):
    warnings.simplefilter('ignore')
    cell = int(argv[0]) if argv else 2553
    frames = int(argv[2]) if len(argv) > 2 else 4
    subxs = _bytes_arg(argv[1] if len(argv) > 1 else 'span:8', frames=frames, cells=(cell,))
    rows = probe([cell], subxs, frames=frames, progress=True)
    out = os.path.join(_rb, '_generated', 's95', 'probe_%d.json' % cell)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(cell=cell, frames=frames, rows=rows), open(out, 'w'), indent=1)
    best = min(rows, key=lambda r: r['min_abs_resid'])
    frozen = [r['min_abs_resid'] for r in rows if r['subx'] == [NEUTRAL]]
    print("best: subx %s thrust %d, |resid| %.5g%s"
          % (label(best['subx']), best['thrust'], best['min_abs_resid'],
             '' if not frozen else ' (frozen reads %.5g)' % min(frozen)))
    print("wrote %s" % out)


def _cmd_search(argv):
    warnings.simplefilter('ignore')
    cells = argv[0] if argv else '2553'
    frames = int(argv[2]) if len(argv) > 2 else 4
    from harness.tetrapush import entry_fan as EF
    want = EF.parse_cell_spec(cells) if isinstance(cells, str) else cells
    subxs = _bytes_arg(argv[1] if len(argv) > 1 else 'span:8', frames=frames, cells=want)
    fan = None
    if len(argv) > 3 and argv[3] != '-':    # s1_stride,j1,s2_stride,j2max,nbase -- j1 as `2|3` for a set
        a = argv[3].split(',')
        fan = dict(s1_stride=int(a[0]), j1=tuple(int(x) for x in a[1].split('|')),
                   s2_stride=int(a[2]), j2max=int(a[3]), base_frames=tuple(range(int(a[4]))))
    # the THRUST scope: session 96 measured cell 2553's thrust-14 configuration at 3.8% of the draws
    # and 4.5% of E[hits] for 24% of the clock, so a pass says which thrusts it bought
    thr = tuple(int(x) for x in argv[4].split(',')) if len(argv) > 4 else None
    passes = search(cells, subxs, frames=frames, fan=fan, thrusts=thr, progress=True)
    s = summarize(passes)
    tag = '%s_%s%s' % (str(cells).replace(',', '_'),
                       (argv[1] if len(argv) > 1 else 'span8').replace(':', ''),
                       '' if thr is None else '_thr%s' % '-'.join(str(t) for t in thr))
    out = os.path.join(_rb, '_generated', 's95', 'search_%s.json' % tag)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(cells=cells, frames=frames, summary=s, passes=passes), open(out, 'w'), indent=1,
              default=list)
    print("%d cameras: %d genuine, %d DISTINCT near of %d reported, E[hits] %.3f (pooled %.3f would"
          " double-count the overlap), best gap %s  [%.0fs]"
          % (s['n_cameras'], s['n_genuine'], s['n_near'], s['n_near_reported'], s['expected_hits'],
             s['expected_hits_pooled'], s['best_gap'], s['seconds']))
    print("wrote %s" % out)


def _cmd_hull(argv):
    warnings.simplefilter('ignore')
    subxs = _bytes_arg(argv[0] if argv else 'span:6')
    frames = int(argv[1]) if len(argv) > 1 else 4
    from harness.tetrapush import entry_fan as EF
    quals = EF.qualified()
    w = EF.facing_window()
    lo, hi = w['lobes'][1]
    st = [(q['entry'][0], q['entry'][1], q['facing']) for q in quals
          if lo <= ES.aim_cell(q['facing']) <= hi]
    res = hull_shift(subxs, frames=frames, stations=st)
    for r in res['rows']:
        print("   subx %-9s %6d endpoints, bbox %s, area %.1f u2"
              % (label(r['subx']) + ':', r['n'], ['%.1f' % v for v in r['bbox']], r['area']))
    print("union over %d cameras: area %.1f u2 (frozen %.1f, %+.1f%%)"
          % (len(res['rows']), res['union_area'],
             res['rows'][0]['area'],
             100.0 * (res['union_area'] / res['rows'][0]['area'] - 1.0)))
    reached = [s for s in res.get('stations', []) if s['in_union']]
    print("second-lobe stations inside the UNION hull at %d frames: %d of %d%s"
          % (frames, len(reached), len(st),
             '' if not reached else ' -- %s' % [s['station'] for s in reached]))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'reach'
    if cmd == 'reach':
        _cmd_reach(argv)
    elif cmd == 'hull':
        _cmd_hull(argv)
    elif cmd == 'alphabet':
        _cmd_alphabet(argv)
    elif cmd == 'cells':
        _cmd_cells(argv)
    elif cmd == 'probe':
        _cmd_probe(argv)
    elif cmd == 'search':
        _cmd_search(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
