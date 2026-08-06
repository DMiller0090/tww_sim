"""**The last cycle's endpoint keep, ranked on the ENUMERATED atom cloud landing** (session 107).

Sessions 67-72 built the last-cycle keep as `full_herd.escape_probe`: run `away_walk.probe`, read the
best variant's residual, and rank the endpoint by `aim.landing_miss` -- the residual measured against
`objective.placement_thread`'s FIT. That is the right SHAPE and the wrong MEASURE once the target set
stopped being a thread. Session 105 established that the frame-minimal target set is a ~170 u-wide 2D
CLOUD of rows (`_generated/tetra_placements.tsv` screened by `herd_price`), and a fit through a cloud
is fiction: session 106 measured that `escape_probe`'s ``miss`` and the landing an endpoint actually
reaches disagree so badly that every beam ranked by it is landing-BLIND, so the ~6 u floor it reported
was a property of the CUT rather than of the survivor population.

So measure the landing honestly and rank on THAT. There is no cheap predictor here and one is not
needed: the atom is 4-5 inputs, its knob grid is finite (`away_walk.flip_arc` x `ROTATE_OFFS` x
turnaround x side x exit bearing), and enumerating the whole grid at one endpoint costs ~20-30 s. That
is a last-cycle terminal budget (the same order `escape_keep`'s swept form already costs, ~30 s per
survivor at ``escape_flip=0x400``), so the keep can afford to be exact.

**What "ranked on the landing" has to mean, in the objective's currency, not in units.** A landing is
bought WITH frames -- the same arrival reaches 0.299 u on a 16-frame atom and 5.93 u on a 2-frame one
(session 106) -- so a miss-only rank spends 14 frames on 5.6 u against a `objective.PLACEMENT_BAND` of
1.0 and a 2-frame `objective.TIMELOSS_BUDGET`. `cloud_bound` is therefore `objective.plan_bound`'s
shape applied to the TOTAL: the frames the whole candidate spends (herd + the atom's own log + the
row's `plan_cost`) plus what the remaining miss would cost at `objective.PUSH_CEILING`. It reduces to
the exact total when the landing is on the row, and it prices a 6 u miss at ~0.5 frames -- which is
the honest exchange rate, and the reason a fast wide atom can legitimately out-rank a slow exact one.

The row's own ``plan_cost`` is part of the total because the rows are NOT interchangeable: session 104
priced them 19-23 frames apart, so a landing 6 u from a cheap row can beat one 1 u from an expensive
one. This is the one place the whole plan's arithmetic is visible at once, so it is where the
comparison belongs.
"""
# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
import math

from harness.tetrapush import away_walk as AW
from harness.tetrapush import objective as O
from harness.tetrapush import seeds as SD

#: The flip-bearing resolution: the landing is piecewise constant in it (plateaus 10-25 deg wide, and a
#: 0x40 pass found nothing between them), so 0x400 resolves every plateau -- `away_walk.probe`.
FLIP_STEP = 0x400

#: The rotate offsets, `away_walk.ROTATE_OFFS` verbatim -- linked, not restated, so a change there
#: reaches this keep.
ROTATE_OFFS = AW.ROTATE_OFFS


def atom_cloud(run0, hl, *, flip_step=FLIP_STEP, rotate_offs=None, max_frames=18, csangle='live'):
    """Every atom variant `away_walk.probe` sweeps, with the RANK REMOVED -- the full knob grid as a
    list of results, each carrying its ``knobs``.

    This is `away_walk.probe`'s own loop minus its ``best`` reduction, and it is deliberately a
    separate function rather than a flag on it: `probe` returns ONE variant because its callers rank
    endpoints, while a landing keep needs the whole grid to read a (miss, total) front off. The
    acceptance is not applied here either -- `away_walk.fires` is the filter and stays the caller's,
    so a census of what refused is always available (`away_walk.fires_census`).

    Runs every variant at the arrival's OWN camera (``csangle='live'``, session 73's honest default):
    the atom's C-stick is neutral, so this is what a plain replay delivers, and no variant is billed
    for a camera state nothing in the plan paid for."""
    from tww_sim.land.plan_land._primitives import world_angle_s16
    ex, ez = SD.ENTRY_ROLL_POS
    b_entry = world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    if csangle == 'live':
        cs = int(run0.csangle)
    elif csangle == 'snap':
        cs = AW.snap_csangle(run0)
    else:
        cs = int(csangle)
    rots = ROTATE_OFFS if rotate_offs is None else tuple(rotate_offs)
    out = []
    for flip in AW.flip_arc(hl, step=int(flip_step)):
        for ro in rots:
            for ta in (False, True):
                for side in (1, -1):
                    for exit_b in (b_entry, up_herd):
                        r = AW.escape_atom(run0, hl, turnaround_first=ta, rotate_side=side,
                                           rotate_off=ro, flip_bearing=flip, exit_bearing=exit_b,
                                           csangle=cs, max_frames=max_frames)
                        if r is None:
                            continue
                        r['knobs'] = dict(turnaround_first=ta, rotate_side=side, rotate_off=ro,
                                          flip_bearing=flip, exit_bearing=exit_b)
                        out.append(r)
    return out


def _nearest_row(tx, tz, rows):
    """The cheapest-TOTAL row for a landing, not merely the nearest one.

    Nearest-by-distance is what session 106's scorer used and it is a tie-break, not the measure: the
    rows carry ``plan_cost`` 19-23 (session 104), so a row 6 u away at cost 20 finishes sooner than one
    2 u away at cost 23. Ranks by ``plan_cost + remaining_frames(miss)`` -- the same currency
    `cloud_bound` totals in -- with the raw miss as the tie-break."""
    best = None
    for p in rows:
        d = math.hypot(p['x'] - tx, p['z'] - tz)
        k = (float(p.get('plan_cost', 0)) + O.remaining_frames(d), d)
        if best is None or k < best[0]:
            best = (k, d, p)
    return (best[1], best[2]) if best else (float('inf'), None)


def cloud_landing(run0, frames, hl, rows, *, band=None, flip_step=FLIP_STEP, rotate_offs=None,
                  max_frames=18, csangle='live', front=True):
    """**Enumerate the atom grid at one herd endpoint and price every firing variant as a WHOLE
    candidate.** The last-cycle keep's measure; `full_herd.escape_probe`'s replacement on a cloud
    target set.

    A candidate's frames are ``frames + len(atom log) + row.plan_cost``, and every term matters:
    ``frames`` is the herd, the atom's LOG (not its ``freeze_f``) is what a delivery replays -- session
    105's off-by-three, the banked 101 -- and the row's cost is the entry-plus-thrust it implies. The
    rank is `cloud_bound`: that total plus the remaining miss at `objective.PUSH_CEILING`.

    Returns ``dict(fires, n_variants, n_firing, bound, best, in_band, front)``:
      * ``best`` -- the minimum-``bound`` variant, as ``dict(miss, total, bound, row_idx, row_cost,
        n_atom, freeze_f, resid, tetra_end, knobs)``.
      * ``in_band`` -- the cheapest-TOTAL variant landing inside ``band`` (default
        `objective.PLACEMENT_BAND`), or None. This is the only field that answers "is the plan
        solved here", so it is reported separately from the rank rather than inferred from it.
      * ``front`` -- the (total, miss) Pareto front, so a caller can see the exchange rate this
        endpoint offers instead of only the point the rank picked.
    A non-firing endpoint reads ``fires=False`` with an infinite bound, so it sorts last: it cannot end
    a plan (rule 3, `away_walk.fires`)."""
    bd = O.PLACEMENT_BAND if band is None else float(band)
    variants = atom_cloud(run0, hl, flip_step=flip_step, rotate_offs=rotate_offs,
                          max_frames=max_frames, csangle=csangle)
    firing = [r for r in variants if AW.fires(r)]
    base = dict(n_variants=len(variants), n_firing=len(firing))
    if not firing:
        return dict(base, fires=False, bound=float('inf'), best=None, in_band=None, front=[])

    scored = []
    for r in firing:
        tx, tz = r['run'].tx, r['run'].tz
        miss, row = _nearest_row(tx, tz, rows)
        n_atom = len(r['log'])
        total = frames + n_atom + float(row.get('plan_cost', 0))
        scored.append(dict(miss=miss, total=total,
                           bound=total + O.remaining_frames(miss),
                           row_idx=row.get('idx'), row_cost=row.get('plan_cost'),
                           n_atom=n_atom, freeze_f=r['freeze_f'],
                           resid=(r['resid_along'], r['resid_lat']),
                           tetra_end=(tx, tz), knobs=dict(r['knobs'])))
    scored.sort(key=lambda s: (s['bound'], s['miss']))
    best = scored[0]
    inb = [s for s in scored if s['miss'] <= bd]
    inb.sort(key=lambda s: (s['total'], s['miss']))
    pf = []
    if front:
        for s in sorted(scored, key=lambda s: (s['total'], s['miss'])):
            if not pf or s['miss'] < pf[-1]['miss']:
                pf.append(s)
    return dict(base, fires=True, bound=best['bound'], best=best,
                in_band=(inb[0] if inb else None), front=pf)


def residual_fan(endpoints, hl, *, flip_step=FLIP_STEP, rotate_offs=None, max_frames=18,
                 quantum=1.0):
    """**The atom's residual as the SET it is, measured once** -- the cheap predictor's table.

    Session 106's decisive measurement is that the escape's residual is not a point but a 2D FAN: over
    1345 firing variants at real endpoints it spans along -31..+23 and lateral **+13.8..+52**, never
    below +13.8 (the atom always pushes her lateral-positive). Every keep that shifted a target by "the"
    residual therefore shifted it by one arbitrary member -- which is why `aim.handoff_rows` measured
    out in session 106 round 2-3, dropping all 33 survivors under a budget and then filling the beam
    with worse-converting endpoints. A fan cannot be represented by its own member.

    So represent it as a set. Each member is ``dict(along, lat, n_atom)`` -- the offset the atom adds to
    Tetra, and the frames it costs to add it -- deduped on a ``quantum`` u grid so the table stays small
    (the landing is piecewise constant in the flip bearing, so the grid loses nothing the enumeration
    resolves). The atom's LOG length is the frame cost, not ``freeze_f``: a delivery replays the log
    (session 105's off-by-three, the banked 101).

    Measured at the ``endpoints`` the caller passes, and that dependence is REAL, not incidental: the
    residual's lateral tracks Link's offset from Tetra at -0.53 u per u (`away_walk.probe`), so a fan
    measured at unlike states predicts badly. Measure it on the band being searched, and confirm the
    prediction by enumeration at the survivors (`cloud_landing`) before quoting a landing -- the
    predictor sizes the CUT, the enumeration makes the CLAIM (`[[banded-proxy-needs-its-newton]]`)."""
    seen, out = set(), []
    for ep in endpoints:
        run0 = ep['run'] if isinstance(ep, dict) else ep
        for r in atom_cloud(run0, hl, flip_step=flip_step, rotate_offs=rotate_offs,
                            max_frames=max_frames):
            if not AW.fires(r):
                continue
            n_atom = len(r['log'])
            key = (round(r['resid_along'] / quantum), round(r['resid_lat'] / quantum), n_atom)
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(along=r['resid_along'], lat=r['resid_lat'], n_atom=n_atom))
    out.sort(key=lambda m: (m['n_atom'], m['lat'], m['along']))
    return out


def herd_rows(rows, hl, *, default_cost=0.0):
    """``rows`` guaranteed to carry ``along``/``lat``/``plan_cost``, so `predict_bound` can work in herd
    coordinates without a `HerdLine`.

    It exists because the two row sources in this harness disagree about their columns and one of them
    would have crashed the predictor: a screened/priced set (`herd_price`, `_generated/.../targets.json`)
    carries ``along``/``lat``/``plan_cost``, while the raw genuine-coord set (`seeds.load_placements`)
    carries only ``idx``/``x``/``z``/wall distances. Converting is exact (`HerdLine.along`/`lateral` are
    the same projection the priced rows were built with -- verified equal to their stored values to the
    last digit), but the COST is not recoverable from a raw row, so it defaults and a caller that ranks
    totals should be handing over priced rows. Pass-through when the columns are already present."""
    out = []
    for r in rows:
        if 'along' in r and 'lat' in r and 'plan_cost' in r:
            out.append(r)
            continue
        d = dict(r)
        if 'along' not in d or 'lat' not in d:
            d['along'] = hl.along(r['x'], r['z'])
            d['lat'] = hl.lateral(r['x'], r['z'])
        d.setdefault('plan_cost', default_cost)
        out.append(d)
    return out


def predict_bound(t_along, t_lat, frames, fan, rows):
    """**The cheap predictor `cloud_landing` is the exact confirm of**: the best whole-candidate frame
    bound a herd endpoint could reach, over the residual FAN crossed with the rows.

    Same currency as `cloud_landing`'s ``bound`` -- herd frames + the atom's own log + the row's
    ``plan_cost`` + the remaining miss at `objective.PUSH_CEILING` -- so the two are directly
    comparable, which is the only way to know what the prediction is worth. Costs one pass over
    ``len(fan) * len(rows)`` distances (a few thousand hypots, microseconds) against ~28 s for the
    enumeration, so this is what a per-aim cut inside the last cycle can afford and the enumeration is
    not.

    It is a LOWER bound on the enumerated bound only to the extent the fan is reachable from THIS state
    (see `residual_fan`) -- an optimistic proxy, in the same family as `objective.plan_bound`'s ``h``,
    and it must be Newtoned onto the real thing before it is quoted. Returns ``dict(bound, miss, total,
    row_idx, n_atom, resid)`` for the best pair, or None on an empty fan."""
    best = None
    for m in fan:
        pa, pl = t_along + m['along'], t_lat + m['lat']
        for r in rows:
            d = math.hypot(r['along'] - pa, r['lat'] - pl)
            total = frames + m['n_atom'] + float(r.get('plan_cost', 0))
            b = total + O.remaining_frames(d)
            if best is None or b < best['bound']:
                best = dict(bound=b, miss=d, total=total, row_idx=r.get('idx'),
                            n_atom=m['n_atom'], resid=(m['along'], m['lat']))
    return best


def cloud_probe(run, frames, hl, placements, **kw):
    """`full_herd.escape_probe`'s signature, answered by the enumeration.

    Same call shape (minus the ``thread``, which is the whole point -- there is no fit to measure
    against), same contract: a dict whose ``bound`` a beam can sort ascending, ``fires`` gating rule 3.
    Exists so a keep can be swapped between the two measures without touching the beam code, and so the
    two can be run side by side on the same survivors (which is how the CUT-vs-POPULATION question of
    session 106 gets answered on any future cycle)."""
    res = cloud_landing(run, frames, hl, placements, **kw)
    b = res['best']
    return dict(fires=res['fires'], bound=res['bound'],
                miss=(b['miss'] if b else None), total=(b['total'] if b else None),
                frames=frames, n_variants=res['n_variants'], n_firing=res['n_firing'],
                row_idx=(b['row_idx'] if b else None), n_atom=(b['n_atom'] if b else None),
                resid=(b['resid'] if b else None), knobs=(b['knobs'] if b else None),
                in_band=res['in_band'], front=res['front'])
