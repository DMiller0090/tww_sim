"""**WHERE A CLIP IS POSSIBLE AT ALL** -- the admitting set over configuration space, enumerated (s159).

This pipeline has always run one way: enumerate plans, evaluate ``genuine``. `razor_band.admits` inverted
it at 16 ms a configuration, and this module turns that into a MAP -- the first statement in this work of
WHERE a clip is possible, as opposed to which plans happened to find one. Three measurements make it an
enumeration rather than a sampled grid whose resolution has to be argued:

**1. THE LEAN HAS CELLS, THE WAY THE AIM DOES.** `entry_search.aim_cell` is the load-bearing atom of this
work's cost model: two facings in one sine-table cell bake a BIT-IDENTICAL schedule and are ONE draw. The
same is true one axis over. Fingerprinting the baked schedule across the 1042 leans a fan reaches
(`entry_lean.census`, contiguous -775..+266) returns **129 distinct schedules** in 129 contiguous runs, 1
to 32 BAM wide, and the partition is bit-identical at every (cell, thrust) measured. So the configuration
space is 45 cells x 3 thrusts x **129 lean classes = 17415 configurations**, exactly -- and the handoff's
warning that "a lean sweep coarser than ~180 BAM reports FALSE zeros" stops applying, because nothing is
being sampled.

**2. ``resid = 0`` IS A CURVE, AND EVERY VERDICT BEFORE THIS ONE WAS READ AT ONE POINT OF IT.** The
residual is a scalar on her 2-D start plane, so its zero is a CURVE, and it runs the length of a contact
region ~+-80 u across. At the console's own configuration the curve is 116 u long and **51 of its 188
stations admit -- 27%**. A single-station screen therefore MISSES an admitting configuration about three
times in four, so this walks the curve (predictor along the tangent, Newton corrector back onto it) and
ladders at every station. That is also why s158's widest negative -- a +-2 u plane, 7.1 M placements -- is
a statement about 4 u of a curve that is tens of u long, and `screen` quotes the arc it covered for
exactly that reason.

**3. THE CORRECTOR STOPS ON THE RESIDUAL'S OWN QUANTUM.** ``resid`` is quantized (s158: 86 placements
share one value and a band spans 7 of them, so the quantum is ~4e-6), so a Newton with an absolute 1e-8
tolerance can never converge -- the first version of the walk rejected every station after its seed and
reported a 116 u curve as 1 u long. `CORRECT_TOL` is a fifth of the ladder's own span instead, because a
station only has to land inside the range the ladder then sweeps.

**HONEST LIMITS.** A negative is a statement about the arc walked and the ray set the seeds came from,
both returned. The walk follows the curve COMPONENT it was seeded on; `her_seeds` finds one seed per
crossing of its ray fan, so a component that crosses no ray is not walked. And the screen is read at ONE
entry: measured at the console's configuration, re-locating her per entry takes a +-0.8 u entry plane from
s158's 8.7% (her seed pinned) to **69.6%**, so the entry is a weak axis rather than a free one, and the
duty cycle is a measured caveat and not an assumption.

usage:
    python -m harness.tetrapush.admit_map gate            # the rediscovery gate: both known clips
    python -m harness.tetrapush.admit_map one <facing> <lean> <thrust>
    python -m harness.tetrapush.admit_map map [out.jsonl] [arc] [step]
"""
import json
import math
import os
import struct
import sys
import time

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
# <<< repo bootstrap

from harness.tetrapush import cut_contact as CC
from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_band as RB

#: `entry_lean.LEAN_FIXTURE`'s census: the leans a bounded fan ARRIVES on, which is the reachable set
#: and not a swept range (knowledge/model/lean-cells.md).
LEAN_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_lean_bands_s94.json')

#: The corrector's target: an absolute tolerance under the residual's ~4e-06 quantum can never be met
#: (module docstring point 3; knowledge/model/razor-zero-curve.md).
CORRECT_TOL = RB.LADDER_RESID / 5.0

#: The station ladder, at s158's rung density. Asymmetric because every measured band is strictly
#: POSITIVE and the widest hi is +2.2e-04; the negative side only checks the station straddles zero.
RUNG_LO, RUNG_HI, RUNG_STEP = 1.0e-4, 5.0e-4, 2.5e-6

#: The curve walk. 1 u stations because the admitting stretches measured at both clipping configurations
#: carry gaps up to 4 stations wide; `ARC` bounds the walk each way and is quoted in every verdict.
STATION_STEP, ARC = 1.0, 25.0

#: `her_seeds`: rays out of the braced Co centre. Her own start sits 53 u (s154) and 92 u (console) from
#: it, and the plow moves her, so the far end runs past `cut_contact.CO_R_SUM` = 80.
SEED_BEARINGS, SEED_MAX, SEED_STEP = 16, 140.0, 1.0

_LEAN_RUNS = None


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def _fp(v):
    """A bit-exact fingerprint of anything a baked schedule carries."""
    if isinstance(v, float):
        return _bits(v)
    if isinstance(v, (list, tuple)):
        return tuple(_fp(x) for x in v)
    if isinstance(v, dict):
        return tuple((k, _fp(v[k])) for k in sorted(v))
    return v


def schedule_fingerprint(sch):
    """The bit pattern of a whole baked schedule -- the test `lean_runs` is built on.

    Two configurations that agree here are ONE draw, exactly as two facings in an `aim_cell` are."""
    return tuple((k, _fp(sch[k])) for k in sorted(sch))


def reachable_leans():
    """The signed leans a bounded fan reaches, ascending -- read off the banked census, never swept.

    1040 values spanning -775..+266 with only -1 and +1 absent (`lean_at_roll`'s decay branch cannot
    land there), so the axis is dense and its hull is what `lean_runs` partitions."""
    with open(LEAN_FIXTURE) as fh:
        hist = json.load(fh)['census']['hist']
    return sorted((int(k) - 65536 if int(k) > 32768 else int(k)) for k in hist)


def lean_runs(facing=None, thrust=None, leans=None):
    """**THE LEAN'S OWN CELLS**: ``[(lo, hi)]``, the contiguous runs of lean that bake ONE schedule.

    Derived by fingerprinting, not tabulated. Measured 129 runs of width 1..32 over the reachable hull,
    with an IDENTICAL partition at cells 2525/2545/2552/2554/2581 and thrusts 13/14/15 -- so it is a
    property of the lean and the default is cached for the whole map. Pass ``facing``/``thrust`` to
    re-derive it somewhere else, which is what the gate does."""
    global _LEAN_RUNS
    if facing is None and thrust is None and leans is None and _LEAN_RUNS is not None:
        return _LEAN_RUNS
    f = ES.TAB_FACING if facing is None else facing
    t = ES.THRUSTS[-1] if thrust is None else thrust
    if leans is None:
        ls = reachable_leans()
        leans = range(ls[0], ls[-1] + 1)
    runs, prev = [], None
    for ln in leans:
        fp = schedule_fingerprint(ES.fast_schedule(f, ln & 0xFFFF, t, ES.TAB_ENTRY))
        if runs and prev == fp and runs[-1][1] == ln - 1:
            runs[-1][1] = ln
        else:
            runs.append([ln, ln])
        prev = fp
    out = [(a, b) for a, b in runs]
    if facing is None and thrust is None:
        _LEAN_RUNS = out
    return out


def lean_classes():
    """One representative lean per class -- the map's lean axis, 129 values."""
    return [a for a, _b in lean_runs()]


def lean_cell(lean):
    """The index of the lean class a lean falls in, or ``None`` outside the reachable hull."""
    ln = int(lean) & 0xFFFF
    ln = ln - 65536 if ln > 32768 else ln
    for i, (a, b) in enumerate(lean_runs()):
        if a <= ln <= b:
            return i
    return None


# ------------------------------------------------------------------ the razor, in her start coordinates

def resid_grad(ctx, resid, entry, p, h=1e-3):
    """``(gx, gz, mag, resid, row)`` of the razor residual w.r.t. HER START position, one sweep.

    ``mag == 0`` is the diagnostic that she is OUT OF Co RANGE on the cut frame: the razor stops
    depending on her at all, so there is no descent direction and a Newton cannot start from there
    (the same reading `entry_search.zero_the_resid` gives for the entry)."""
    pts = [(p[0] + h, p[1]), (p[0] - h, p[1]), (p[0], p[1] + h), (p[0], p[1] - h), p]
    o = ctx.sweep_par([(q[0], q[1], entry[0], entry[1]) for q in pts], 0, extra=True)
    r = [resid(x) for x in o]
    gx, gz = (r[0] - r[1]) / (2.0 * h), (r[2] - r[3]) / (2.0 * h)
    return gx, gz, math.hypot(gx, gz), r[4], o[4]


def newton_to_zero(ctx, resid, entry, p, iters=10, tol=CORRECT_TOL):
    """Walk her onto ``resid = 0``. ``(p, resid, mag, ok)``; ``ok`` False when the gradient dies or the
    residual never gets inside ``tol``.

    Keeps the BEST point seen rather than the last: past the residual's quantum a Newton step stops
    improving and starts oscillating, and the best point is the one the ladder wants."""
    best = None
    for _ in range(iters):
        gx, gz, mag, r, _o = resid_grad(ctx, resid, entry, p)
        if mag <= 0.0:
            return p, r, mag, False
        if best is None or abs(r) < abs(best[1]):
            best = (p, r, mag)
        if abs(r) < tol:
            return p, r, mag, True
        q = (p[0] - r * gx / (mag * mag), p[1] - r * gz / (mag * mag))
        if q == p:
            break
        p = q
    return best[0], best[1], best[2], bool(abs(best[1]) < tol)


def station_band(ctx, resid, entry, p, gx, gz, mag, r0, *, lo=RUNG_LO, hi=RUNG_HI, step=RUNG_STEP):
    """**DOES THE RAZOR ADMIT A CLIP AT THIS STATION?** One batched ladder along the gradient.

    Since ``genuine`` is exactly ``resid in band`` at a configuration (`razor_band`), marching her along
    the residual's own gradient visits every residual level in the range, so a ladder finer than a band
    cannot step over one. Returns ``dict(genuine, tested, lo, hi)``.

    Cheaper than `razor_band.admits` by the whole locating sweep, because the caller is already ON the
    curve -- which is what makes a per-station screen affordable."""
    ux, uz = gx / mag, gz / mag
    n = int((lo + hi) / step) + 1
    ts = [(-lo + i * step - r0) / mag for i in range(n)]
    rows = ctx.sweep_par([(p[0] + t * ux, p[1] + t * uz, entry[0], entry[1]) for t in ts], 0,
                         extra=True)
    g = [resid(o) for o in rows if o[0]]
    return dict(genuine=len(g), tested=n, lo=(min(g) if g else None), hi=(max(g) if g else None))


def her_seeds(ctx, resid, entry, co, *, bearings=SEED_BEARINGS, rmax=SEED_MAX, rstep=SEED_STEP):
    """One seed per crossing of ``resid = 0`` on a ray fan out of the braced Co centre.

    NOT `entry_search.curve_seeds`, which seeds the same curve in the ENTRY plane -- this one works in
    HER plane, the variable s157 showed the cut frame really has.

    A 2-D grid of her plane costs 0.1-0.3 s and would dominate the map; a ray fan finds the same curve
    for a few ms, because the curve runs ACROSS the contact region rather than along a ray. Rows out of
    contact are dropped first -- their residual is the braced constant and its sign means nothing.

    **A SIGN CHANGE IS NOT ALWAYS A ZERO.** Deep inside the overlap the residual STEPS, and a bracket
    across a discontinuity bisects to a point whose own residual is tens - measured 68.4 at one, against
    a local slope of 24 per u. `cut_contact.zero_bearing` hit the same thing one coordinate over and
    solved it by re-testing the refined crossing. Here the arbiter is the Newton itself: every bracket is
    corrected onto the curve and kept ONLY if it converges, so what comes back is already a station and
    a jump is dropped rather than walked.

    Returns ``[(x, z)]``, each on the curve to `CORRECT_TOL`. A component crossing no ray is not found,
    which is why `screen` returns ``bearings``."""
    from tww_sim.core import mathlib as ML
    n = int(rmax / rstep) + 1
    out = []
    for k in range(bearings):
        b = int(round(k * 65536.0 / bearings)) & 0xFFFF
        sx, sz = ML.cM_ssin_s16(b), ML.cM_scos_s16(b)
        pts = [(co[0] + i * rstep * sx, co[1] + i * rstep * sz) for i in range(n)]
        rows = ctx.sweep_par([(p[0], p[1], entry[0], entry[1]) for p in pts], 0, extra=True)
        rs = [resid(o) for o in rows]
        live = [i for i, o in enumerate(rows)
                if CC.CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13]) > 0.0]
        ls = set(live)
        for i in live:
            if (i + 1) in ls and (rs[i] < 0.0) != (rs[i + 1] < 0.0):
                mid = (0.5 * (pts[i][0] + pts[i + 1][0]), 0.5 * (pts[i][1] + pts[i + 1][1]))
                p, _r, _m, ok = newton_to_zero(ctx, resid, entry, mid)
                if ok:
                    out.append(p)
    return out


def walk_curve(ctx, resid, entry, seed, *, step=STATION_STEP, arc=ARC, sign=+1, min_step=0.05):
    """Predictor-corrector along ``resid = 0``, yielding ``(p, gx, gz, mag, resid, overlap, s)``.

    The predictor steps ``step`` u along the TANGENT and the corrector Newtons back. On a corrector
    failure the step HALVES rather than the walk ending, so a curve that bends sharply is followed
    instead of being reported short -- the truncation that made the barren item's curve read 8 u long."""
    p, r, mag, ok = newton_to_zero(ctx, resid, entry, seed)
    if not ok:
        return
    s, h = 0.0, float(step)
    while s <= arc:
        gx, gz, mag, r, o = resid_grad(ctx, resid, entry, p)
        if mag <= 0.0:
            return
        yield (p, gx, gz, mag, r, CC.CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13]), s)
        while True:
            tx, tz = -gz / mag, gx / mag
            q, r2, m2, ok = newton_to_zero(
                ctx, resid, entry, (p[0] + sign * h * tx, p[1] + sign * h * tz))
            if ok:
                p, s = q, s + h
                h = min(float(step), h * 2.0)
                break
            h *= 0.5
            if h < min_step:
                return


# ------------------------------------------------------------------------------------- the screen

def screen(facing, lean, thrust, *, entry=None, ctx=None, sch=None, resid=None, nspeed=None,
           step=STATION_STEP, arc=ARC, first_only=False, seed=None, bearings=SEED_BEARINGS):
    """**DOES THIS CONFIGURATION ADMIT A CLIP FOR ANY POSITION OF HERS?**

    Locates the razor's zero curve in her start plane, walks it both ways, and ladders every station.
    Returns ``dict(admits, stations, admitting, arc_neg, arc_pos, components, lo, hi, reason, tested,
    entry, seconds, bearings, step)``.

    ``reason`` names a negative: ``no_curve`` (no crossing of ``resid = 0`` in contact on any ray -- the
    razor is not reachable here at all), or ``no_band`` (the curve was walked and no station admitted,
    over the arc reported). ``first_only`` stops at the first admitting station, which is what a map
    wants and a calibration does not.

    A negative is a statement about the arc walked and the ray fan seeded from, both returned. Read it
    the way s158 asks a zero to be read: with its window quoted."""
    t0 = time.time()
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, int(lean) & 0xFFFF, thrust, nspeed=nspeed)
    e = ((sch['link_x0'], sch['link_z0']) if entry is None else (float(entry[0]), float(entry[1])))
    br = CC.braced_row(facing, lean, thrust, ctx=ctx, sch=sch, resid=resid)
    seeds = [seed] if seed is not None else her_seeds(ctx, resid, e, br['co'], bearings=bearings)
    out = dict(facing=int(facing) & 0xFFFF, cell=ES.aim_cell(facing), lean=int(lean) & 0xFFFF,
               thrust=int(thrust), entry=[e[0], e[1]], components=0, seeds=len(seeds), stations=0,
               admitting=0, arc_neg=0.0, arc_pos=0.0, lo=None, hi=None, admits=False,
               reason='no_curve' if not seeds else '', tested=0, bearings=int(bearings),
               step=float(step), arc=float(arc), co=[br['co'][0], br['co'][1]])
    # A ray fan cuts ONE component several times, so a seed already walked past is not a component:
    # deduping on the seed POINT instead read 7-10 "components" at the console's configuration.
    visited, los, his = [], [], []
    for sd in seeds:
        if any(math.hypot(sd[0] - v[0], sd[1] - v[1]) <= step for v in visited):
            continue
        out['components'] += 1
        for sign in (+1, -1):
            for p, gx, gz, mag, r, _ov, s in walk_curve(ctx, resid, e, sd, step=step, arc=arc,
                                                        sign=sign):
                visited.append(p)
                b = station_band(ctx, resid, e, p, gx, gz, mag, r)
                out['stations'] += 1
                out['tested'] += b['tested']
                if sign > 0:
                    out['arc_pos'] = max(out['arc_pos'], s)
                else:
                    out['arc_neg'] = max(out['arc_neg'], s)
                if b['genuine']:
                    out['admitting'] += 1
                    los.append(b['lo'])
                    his.append(b['hi'])
                    if first_only:
                        out.update(admits=True, lo=min(los), hi=max(his), reason='',
                                   seconds=time.time() - t0)
                        return out
    if out['stations'] and not out['admitting']:
        out['reason'] = 'no_band'
    out.update(admits=bool(los), lo=(min(los) if los else None), hi=(max(his) if his else None),
               seconds=time.time() - t0)
    return out


def screen_space(cells=None, thrusts=None, leans=None, *, entry=None, step=STATION_STEP, arc=ARC,
                 first_only=True, out=None, log=None):
    """The whole map: every (cell, thrust, lean class), through ONE `entry_search.CtxPool`.

    Yields each `screen` verdict and, with ``out``, appends it to a JSONL as it goes -- a map that dies
    at configuration 9000 should still be readable. The pool compiles the courtyard once per
    (cell, thrust) instead of once per configuration, which is 135 builds instead of 17415."""
    cells = ES.aim_cells() if cells is None else cells
    thrusts = ES.THRUSTS if thrusts is None else thrusts
    leans = lean_classes() if leans is None else leans
    pool = ES.CtxPool()
    fh = open(out, 'a') if out else None
    n = adm = 0
    t0 = time.time()
    try:
        for facing, _byts, _sibs in cells:
            for thrust in thrusts:
                for lean in leans:
                    ctx, sch, resid = pool.get(facing, int(lean) & 0xFFFF, thrust)
                    r = screen(facing, lean, thrust, entry=entry, ctx=ctx, sch=sch, resid=resid,
                               step=step, arc=arc, first_only=first_only)
                    r['lean_signed'] = int(lean)
                    n += 1
                    adm += bool(r['admits'])
                    if fh:
                        fh.write(json.dumps(r, default=float) + '\n')
                        fh.flush()
                    yield r
                if log:
                    log('cell %4d thrust %2d done: %d screened, %d admit  (%.0fs)'
                        % (ES.aim_cell(facing), thrust, n, adm, time.time() - t0))
    finally:
        if fh:
            fh.close()


# --------------------------------------------------------------------------------- the CLI + the gate

#: The two rows this work KNOWS clip, with their own entries -- the rediscovery gate
#: (`[[search-must-rediscover-known-answer]]`). Restated here because a gate may not import a probe.
CONSOLE = dict(tag='console own clip', facing=40841, lean=64761, thrust=15,
               tetra=(-1629.101806640625, -893.7962036132812),
               entry=(-1531.178466796875, -781.7215576171875))
ACCEPTED = dict(tag='s154 accepted 101', facing=40727, lean=104, thrust=15,
                tetra=(-1654.9884033203125, -923.457763671875),
                entry=(-1591.7647705078125, -848.5638427734375))


def entry_box(pad=40.0):
    """``(x0, x1, z0, z1)`` -- the roll-entry box the entry map is read over.

    DERIVED FROM THE DATA (`[[search-space-contains-human]]`): the bounding box of the two entries this
    work has actually delivered a clip from, padded. Both are inside it by construction, and so is the
    barren `w10_t15`'s entry at (-1599.90, -862.40), which is what makes the two comparable on one map.
    The pad is well under `entry_search.reach_radius` (94 u), so the box is a sub-region of what a plan
    can reach and not a claim about reachability."""
    xs = (CONSOLE['entry'][0], ACCEPTED['entry'][0])
    zs = (CONSOLE['entry'][1], ACCEPTED['entry'][1])
    return (min(xs) - pad, max(xs) + pad, min(zs) - pad, max(zs) + pad)


def entry_map(facing, lean, thrust, *, step=8.0, box=None, nspeed=None, ctx=None, sch=None,
              resid=None, arc=ARC, log=None):
    """**THE ADMITTING ENTRY REGION AT ONE CONFIGURATION** -- the target with coordinates.

    The entry is the one razor axis the WALK picks directly, and the 2x2 cross in
    `knowledge/model/admitting-entry-region.md` measured that it is what separates the console's clip
    from a barren item on its own cell, thrust and lean. So its admitting region IS the planner's
    objective: reach one of these entries.

    Returns ``dict(box, step, tested, admit, hits, seconds)``; ``hits`` is ``[(x, z, lo, hi)]``."""
    box = entry_box() if box is None else box
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, int(lean) & 0xFFFF, thrust, nspeed=nspeed)
    nx = int((box[1] - box[0]) / step) + 1
    nz = int((box[3] - box[2]) / step) + 1
    t0, hits = time.time(), []
    for i in range(nx):
        for j in range(nz):
            e = (box[0] + i * step, box[2] + j * step)
            r = screen(facing, lean, thrust, entry=e, ctx=ctx, sch=sch, resid=resid, arc=arc,
                       first_only=True)
            if r['admits']:
                hits.append((e[0], e[1], r['lo'], r['hi']))
        if log:
            log('x %+9.2f: %4d of %4d admit  (%.0fs)'
                % (box[0] + i * step, len(hits), (i + 1) * nz, time.time() - t0))
    return dict(box=list(box), step=float(step), tested=nx * nz, admit=len(hits), hits=hits,
                cell=ES.aim_cell(facing), thrust=int(thrust), lean=int(lean) & 0xFFFF,
                seconds=time.time() - t0)


def nearest_admitting_entry(facing, lean, thrust, entry, *, rings=12, ring_step=4.0, spokes=16,
                            nspeed=None, ctx=None, sch=None, resid=None, arc=ARC):
    """**HOW FAR THE WALK HAS TO MOVE THE ROLL ENTRY BEFORE THIS CONFIGURATION CLIPS.**

    An expanding ring search out of ``entry``, stopping at the first entry that admits. This is the
    ranking key a barren item actually needs: `razor_band.band_distance` prices a row in the residual's
    units, which is a quantity no planner can steer, while this is in u of Link's walk endpoint.

    Returns ``dict(admits_at_own, dist, entry, tested, seconds, searched_to)``. ``dist`` None means no
    admitting entry inside ``rings * ring_step`` u, which is a statement about that radius."""
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, int(lean) & 0xFFFF, thrust, nspeed=nspeed)
    from tww_sim.core import mathlib as ML
    t0, n = time.time(), 0
    own = screen(facing, lean, thrust, entry=entry, ctx=ctx, sch=sch, resid=resid, arc=arc,
                 first_only=True)
    n += 1
    if own['admits']:
        return dict(admits_at_own=True, dist=0.0, entry=[entry[0], entry[1]], tested=n,
                    seconds=time.time() - t0, searched_to=0.0)
    for k in range(1, int(rings) + 1):
        r = k * float(ring_step)
        for s in range(spokes):
            b = int(round(s * 65536.0 / spokes)) & 0xFFFF
            e = (entry[0] + r * ML.cM_ssin_s16(b), entry[1] + r * ML.cM_scos_s16(b))
            v = screen(facing, lean, thrust, entry=e, ctx=ctx, sch=sch, resid=resid, arc=arc,
                       first_only=True)
            n += 1
            if v['admits']:
                return dict(admits_at_own=False, dist=r, entry=[e[0], e[1]], tested=n,
                            seconds=time.time() - t0, searched_to=r)
    return dict(admits_at_own=False, dist=None, entry=None, tested=n, seconds=time.time() - t0,
                searched_to=float(rings) * float(ring_step))


def gate(verbose=True):
    """**THE SEARCH HAS TO REDISCOVER A KNOWN ANSWER BEFORE ANY ZERO IT REPORTS MEANS ANYTHING.**

    Screens both configurations that are known to clip, from their own entries and with HER SEED FOUND
    BY THE SCREEN -- `her_seeds`, not the banked placement. Returns the two verdicts."""
    got = {}
    for cfg in (CONSOLE, ACCEPTED):
        r = screen(cfg['facing'], cfg['lean'], cfg['thrust'], entry=cfg['entry'])
        got[cfg['tag']] = r
        if verbose:
            print('%-20s cell %4d thrust %2d lean %6d: admits %-5s  %3d of %3d stations, '
                  '%d components, arc -%.0f/+%.0f u, band [%s, %s]  (%.1fs)'
                  % (cfg['tag'], r['cell'], r['thrust'], r['lean'], r['admits'], r['admitting'],
                     r['stations'], r['components'], r['arc_neg'], r['arc_pos'],
                     '%+.4e' % r['lo'] if r['lo'] is not None else 'none',
                     '%+.4e' % r['hi'] if r['hi'] is not None else 'none', r['seconds']))
    return got


def main(argv):
    cmd = argv[0] if argv else 'gate'
    if cmd == 'gate':
        g = gate()
        ok = all(r['admits'] for r in g.values())
        print('REDISCOVERY GATE: %s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1
    if cmd == 'one':
        facing, lean, thrust = int(argv[1]), int(argv[2]), int(argv[3])
        r = screen(facing, lean, thrust)
        print(json.dumps(r, indent=1, default=float))
        return 0
    if cmd == 'leans':
        runs = lean_runs()
        print('%d reachable leans -> %d classes, widths %d..%d'
              % (len(reachable_leans()), len(runs), min(b - a + 1 for a, b in runs),
                 max(b - a + 1 for a, b in runs)))
        print(' '.join('%d..%d' % r for r in runs))
        return 0
    if cmd == 'entrymap':
        specs = [s for s in argv[1:] if ':' in s]
        step = float(next((s for s in argv[1:] if ':' not in s), 8.0))
        out = os.path.join(_rb, '_generated', 'admit_entrymap.jsonl')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if not specs:
            specs = ['%d:%d:%d' % (c['cell'] if 'cell' in c else ES.aim_cell(c['facing']),
                                   c['thrust'], c['lean']) for c in (CONSOLE, ACCEPTED)]
        box = entry_box()
        print('entry box x %.2f..%.2f  z %.2f..%.2f at %.1f u' % (box[0], box[1], box[2], box[3],
                                                                  step))
        with open(out, 'a') as fh:
            for spec in specs:
                c, t, ln = (int(v) for v in spec.split(':'))
                facing = next(f for f, _b, _s in ES.aim_cells() if ES.aim_cell(f) == c)
                own = next((k for k in (CONSOLE, ACCEPTED)
                            if ES.aim_cell(k['facing']) == c and k['thrust'] == t), None)
                if own is not None:
                    g = screen(facing, own['lean'], t, entry=own['entry'], first_only=True)
                    print('  containment: this cell\'s delivered entry admits %s' % g['admits'])
                    if not g['admits']:
                        print('  REFUSING to read a map whose screen cannot find the known clip')
                        return 1
                m = entry_map(facing, ln, t, step=step,
                              log=lambda s: print('    ' + s, flush=True))
                print('  cell %4d thrust %2d lean %6d: **%d of %d entries admit (%.1f%%)**  (%.0fs)'
                      % (m['cell'], m['thrust'], m['lean'], m['admit'], m['tested'],
                         100.0 * m['admit'] / m['tested'], m['seconds']))
                fh.write(json.dumps(m, default=float) + '\n')
                fh.flush()
        return 0
    if cmd == 'map':
        out = argv[1] if len(argv) > 1 else os.path.join(_rb, '_generated', 'admit_map.jsonl')
        arc = float(argv[2]) if len(argv) > 2 else ARC
        step = float(argv[3]) if len(argv) > 3 else STATION_STEP
        os.makedirs(os.path.dirname(out), exist_ok=True)
        g = gate()
        if not all(r['admits'] for r in g.values()):
            print('REDISCOVERY GATE FAILED -- refusing to bank a map whose screen cannot find a '
                  'known clip')
            return 1
        print('gate PASS; mapping 45 cells x %d thrusts x %d lean classes -> %s'
              % (len(ES.THRUSTS), len(lean_classes()), out))
        n = adm = 0
        t0 = time.time()
        for r in screen_space(arc=arc, step=step, out=out, log=lambda s: print('  ' + s, flush=True)):
            n += 1
            adm += bool(r['admits'])
        print('%d configurations screened, %d admit (%.2f%%) in %.0f s'
              % (n, adm, 100.0 * adm / max(1, n), time.time() - t0))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
