"""SCORING A FAN STREAM: the configurations, the acceptance bands, and how a pass is COUNTED.

Split out of `entry_fan` in session 85 at the seam that module named -- the fan produces candidates,
this scores them. `entry_fan` re-exports every public name here, so `entry_fan.stream_search` and the
rest keep working.

WHAT THIS MODULE IS REALLY ABOUT, and it is not the arithmetic: every headline number a pass prints
has been wrong at least once, always by counting COPIES as discoveries. s81 scored candidates against
a lean-0 band when the band is a jagged function of the lean; s83's camera priced at 8.00x because 48
near-misses were three candidates counted sixteen times; s84's 118 genuine scorings were 23 draws,
one entry reached by 95 prefixes. `draw_key` / `dedupe_near` / `hit_draws` / `distinct_near` exist so
the same mistake cannot be made a fourth time at a fourth level, and `lottery` prices a population at
each draw's OWN band. Read `knowledge/strategy/clip-lottery-draws.md` before trusting a count.
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

from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_search as ES
from tww_sim.land.land import LandState

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
    one cell are the same draw, and counting them separately is what let the camera price at 8x.

    **THE CACHE KEY IS PART OF THE MODEL, and session 89 paid 5000 s to learn it.** This file is the
    only thing the pass consults for "which (facing, thrust) is worth spending candidates on" and for
    the aim bytes that reach each one -- so every input to `aim_cells` has to be in the key or a pass
    silently re-runs the old alphabet. Session 88 gated the aim alphabet on the 0.75 ATTACK threshold
    and the s89 re-run came back BIT-IDENTICAL to the pass before it, because the key validated
    `cells`/`csangle`/`thrusts` and not the gate: 2 of the 3 cached configurations carried aim
    `[95,168]`, msd 0.5705 -- the exact aim of the delivery that sheathed the sword. `msd_min` is in
    the key now. A cache written before either change is refused rather than silently re-used."""
    msd_min = float(LandState.ATTACK_MSD_MIN)
    if not refresh and path and os.path.exists(path):
        d = json.load(open(path))
        if (d.get('cells') and d['csangle'] == csangle and tuple(d['thrusts']) == tuple(thrusts)
                and d.get('msd_min') == msd_min):
            return d['quals']
    seed = seed or ES.console_seed()
    quals = [q for q in ES.qualify(seed['tetra'], ref_entry(seed), thrusts=thrusts,
                                   csangle=csangle) if q['productive']]
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(dict(csangle=csangle, thrusts=list(thrusts), cells=True, msd_min=msd_min,
                       quals=quals), open(path, 'w'))
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
            try:
                raw = json.load(open(path))
            except ValueError as e:
                # a pure memo, so a damaged cache costs a re-measure and never an answer (see `save`)
                warnings.warn("BandTable: ignoring an unreadable cache at %s (%s)" % (path, e))
                raw = {}
            for k, v in raw.items():
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
        """ATOMICALLY -- write beside the cache and rename over it.

        `stream_search` saves every batch, so a long pass rewrites this file dozens of times, and a
        plain `json.dump` onto the live path leaves it truncated for the whole write. Two ways that
        bit: killing a pass mid-save poisoned the cache for every later run, and a second pass
        starting while the first was running read a torn one and died in `json.load`. `os.replace` is
        atomic on the same volume, so a reader now sees either the old table or the new one. Two
        passes still overwrite each other's measurements -- harmless, it is a memo."""
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = '%s.%d.tmp' % (self.path, os.getpid())
        with open(tmp, 'w') as fh:
            json.dump({'%d,%d,%d,%d' % k: v for k, v in self.tab.items()}, fh)
        os.replace(tmp, self.path)


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
        # DEDUPED: a running pass must report the quantity it is judged on (these differed 2.3x)
        trace.append(dict(families=len(fams), candidates=n_uniq, near=len(dedupe_near(near)),
                          genuine=len(hit_draws([h for h in hits if h['walkable']])),
                          seconds=time.time() - t0))

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
                      % (n_uniq, n_raw, n_eval, n_dead, t['genuine'], t['near'], t['families'],
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
                families=sorted(fams), near_families=near_families(near),
                configurations=[dict(facing=q['facing'], thrust=q['thrust'], lo=q['lo'],
                                     hi=q['hi'], width=q['width']) for q in quals])


def near_families(near):
    """Which prefix families produced draws, and how many each -- ``[[family, count], ...]``.

    Small (at most one row per family), and it is what makes the saturation question answerable from
    ONE pass instead of two. `clip-lottery-draws.md`'s honest test is two whole-circle alphabets
    compared on draws per family, which costs a second pass; but a fine alphabet CONTAINS every
    coarser one, so a stride-4 sub-pass's rate can be read straight out of a stride-2 pass's own
    family list -- see `subgrid_rate`."""
    c = {}
    for _g, i in near:
        f = family_of_plan(i['plan'])
        c[f] = c.get(f, 0) + 1
    return [[list(f), n] for f, n in sorted(c.items())]


def subgrid_rate(result, stride):
    """What a COARSER whole-circle pass would have returned, computed from a finer one's own output.

    A stride-2 alphabet contains every stride-4 stick, so the sub-pass is just the families whose S1
    bytes are on the coarse grid. Returns dict(stride, families, draws, per_family) -- and comparing
    two of these against the pass's own numbers is the two-alphabet test with no second pass.

    THE CAVEAT THAT MAKES IT AN ESTIMATE AND NOT A MEASUREMENT: the alphabet is the DECODED grid
    (`entry_fan.stick_alphabet`), so a coarse stride's representative for a decode class can be a
    different byte pair than the fine one's, and a real coarse pass would draw that class from its own
    representative. The physics is identical for the class (that is what `stick_alphabet` gates), so
    the endpoints match; what can differ is which family a draw is ATTRIBUTED to. Read it as the
    coarse pass's rate to within that attribution, not as its bit-exact reproduction."""
    fams = [tuple(f) for f in result.get('families', [])]
    keep = {f for f in fams if f[1] % stride == 0 and f[2] % stride == 0}
    draws = sum(n for f, n in result.get('near_families', [])
                if tuple(f) in keep)
    return dict(stride=stride, families=len(keep), draws=draws,
                per_family=(draws / len(keep)) if keep else None)


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


def rescore(hits, seed=None, progress=False):
    """Re-run a pass's hits through a FRESH `ShoveCtx` and report the verdict now.

    A hit is a claim about the engine that scored it, so when the engine moves the claim has to be
    re-asked -- which is cheap (one sweep per hit) next to re-searching, and is the only honest way
    to keep an old pass's output. Session 87 is the case it was written for: the baked Co centre was
    missing the `body_chn` twist (`body_cyl.co_leans`), a term that scales with the roll's turn lean,
    so the correction is a FUNCTION of the candidate and cannot be reasoned about hit by hit.

    Returns one row per hit: ``hit``, ``genuine``, ``resid``, ``push``, plus ``was`` (the recorded
    resid) and ``kept``. Note what this does NOT tell you: the hits are the old engine's, so a
    survivor rate is a lower bound on the axis, never a re-measurement of it -- the fixed engine can
    make genuine a candidate the old one discarded. Re-run the pass for that."""
    seed = seed or ES.console_seed()
    tx, tz = seed['tetra']
    pool = ES.CtxPool()
    # group by configuration so the pool re-schedules instead of recompiling the courtyard
    order = sorted(range(len(hits)),
                   key=lambda i: (hits[i]['facing'], hits[i]['thrust'], hits[i]['m351C'],
                                  hits[i].get('nspeed') or 0.0))
    out = [None] * len(hits)
    for n, i in enumerate(order):
        h = hits[i]
        ctx, _sch, resid = pool.get(h['facing'], h['m351C'], h['thrust'], nspeed=h.get('nspeed'))
        o = ctx.sweep_par([(tx, tz, h['entry'][0], h['entry'][1])], 0)[0]
        out[i] = dict(hit=h, genuine=bool(o[0]), resid=resid(o), push=[o[5], o[6]],
                      was=h.get('resid'), kept=bool(o[0]))
        if progress and (n + 1) % 10 == 0:
            print("  re-scored %d/%d" % (n + 1, len(hits)))
    return out


def confirm_hits(hits, seed=None, env=None, progress=False, cross_engine=False):
    """`entry_search.confirm_entry` over a pass's hits -- the A-press replay each one owes.

    A swept hit is a PREDICTION: the fan never presses A, it predicts the entry from the walk
    endpoint. The replay has already caught an `INPUT_DELAY` off-by-one and an entry-frame brake, so
    nothing is a result until it comes back `all_ok`. Returns one row per hit, confirmed first.

    Each row also carries ``deliverable``: whether every byte the plan presses reaches the console as
    the physics it was scored at, after `dtm_make`'s extreme-clamp (`entry_fan.survives_delivery`).
    The replay runs the RAW bytes, so a hit can pass every flag here and still evaporate on console --
    the failure mode `[[octagon-clamp-decode-bug]]` cost 60 treads once. The held sticks come from an
    alphabet that already prefers interior representatives; the AIM does not.

    ``cross_engine`` adds the third filter, and session 88 paid for learning it belongs HERE rather
    than in front of a delivery: this replay and the pass that produced the hit run the SAME engine,
    so neither can catch a candidate the composite disagrees with -- 4 of session 88's 19, two of them
    with the composite refusing the lunge `ShoveCtx` scored genuine, and one of those two was the
    frame-minimal survivor a delivery would have gone to. It costs one rollout per confirmed hit
    (~1 s) and no console runs. Rows gain ``cross_engine`` (`cross_engine.agree`) and ``agrees``, and
    the ranking demands it. Off by default: it is a delivery filter, not a scoring one, and
    `test_entry_fan.py`'s ranking contract predates it."""
    from harness.tetrapush import entry_fan as EF
    out = []
    for i, h in enumerate(hits):
        c = ES.confirm_entry(h, seed=seed, env=env)
        pairs = [tuple(h['plan'][k:k + 2]) for k in range(1, len(h['plan']), 3)]
        pairs += [tuple(h['aim'])] if h.get('aim') else []
        deliverable = all(EF.survives_delivery(*p) for p in pairs)
        row = dict(hit=h, confirm=c, deliverable=deliverable)
        out.append(row)
        # Only confirmed, DTM-deliverable hits are worth a rollout: the others cannot be delivered
        # whatever the two engines say about them.
        if cross_engine and c['all_ok'] and deliverable:
            from harness.tetrapush import cross_engine as XE
            row['cross_engine'] = xe = XE.agree(h, seed=seed, env=env)
            row['agrees'] = bool(xe['deliverable'])
            row['blocked'] = XE.blocked(xe)
        elif cross_engine:
            row['cross_engine'], row['agrees'], row['blocked'] = None, False, False
        if progress:
            print("  hit %d/%d plan %s: all_ok %s%s%s  %s"
                  % (i + 1, len(hits), h['plan'], c['all_ok'],
                     "" if deliverable else "  NOT DTM-DELIVERABLE",
                     ("  x-engine %s" % ("agrees" if row['agrees'] else
                                         "BLOCKED" if row['blocked'] else "DIFF"))
                     if cross_engine and row['cross_engine'] else "",
                     "" if c['all_ok'] else [k for k, v in c['ok'].items() if not v]))
    out.sort(key=lambda r: (not (r['confirm']['all_ok'] and r['deliverable']
                                 and (r['agrees'] if cross_engine else True)),
                            r['hit']['plan'][0] + sum(r['hit']['plan'][3::3])))
    return out
