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

**And the total is only half a candidate (session 110, the joint keep).** Session 109 measured that
delivery is TWO predicates: the landing owes the razor its dust, and Link's ARRIVAL owes the clip its
leverage -- the stations sit ~130-165 u up-herd of the landing, so a plan whose walk hull misses them
reads leverage 0 whatever it lands, and a row's ``plan_cost`` is a price measured at SOMEBODY'S
arrival (the s104 hunts gridded the console's own 2-frame cloud). Quoting it for a plan that arrives
elsewhere imports the other half from a different plan -- which is exactly how the s107 winner scored
100 and delivered nothing (`knowledge/strategy/delivery-is-two-predicates.md`). So the keep prices
the station gap beside the landing miss, in the same frame currency: `arrival_frames`, the shortfall
past what the row's own walk budget already reaches, at the walk cap. It is payable because the atom
now has a TAIL (`away_walk.escape_atom`'s ``exit_run``): past ``freeze_f`` Tetra takes no more push,
so exit-hold frames move the arrival and nothing else, at the same price as an entry-walk frame.

**And for eight sessions the arrival half was priced with two of its three axes missing** (session
119). The tail has a BEARING (`exit_arc`, built session 110) and a tail runs along it at the cap, so
the bearing decides where the arrival lands; but no caller above `atom_cloud` could pass one, so
`cloud_landing` / `cloud_probe` / `full_herd.extend_cycle` all enumerated the standing pair and every
cut since chose endpoints on that basis -- until session 118 swept the axis by hand at 14 endpoints an
earlier rank had already fixed and measured 3 frames in it. Worse, `predict_bound`'s ``throw`` was a
``.get(..., 0.0)``, and the fan the joint SCREEN was actually handed (``s107_fan.json``, measured
before the throw existed) carries it on 0 of 178 members -- so the screen placed Link's arrival at the
roll TERMINAL, which session 118 measured to be about HALF the real gap. Both are now plumbed and the
second is a refusal: the arc is an ``exit_step``/``exit_half`` spec resolved per endpoint (`_arc`),
and a throw-less fan cannot price an arrival at all.
"""
# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
import json
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

#: The atom tail lengths a joint keep enumerates (`away_walk.escape_atom`'s ``exit_run``) -- priced off
#: ONE rollout each (`away_walk.tail_variant`), and capped anyway by the 230 u follow bar.
EXIT_RUNS = (0, 1, 2, 3, 4, 5, 6)

#: The exit arc session 118 priced, as `exit_arc`'s ``(step, half)`` -- 26 bearings, ~13x the standing
#: pair per endpoint. `exit_arc`'s own defaults stay where session 110 put them; see `_arc`.
ARC_STEP = 0x800
ARC_HALF = 0x3000

#: The hunts whose LIVE stations priced the rows (session 104) -- the only places a plan can fire the
#: clip from. Gitignored like `entry_fan.FAN_CACHE`: a missing dump leaves the term UNAVAILABLE, not free.
HUNTS = ('s104/cost21_hunt_t15_f2.json', 's104/cost21_hunt_t14_f2.json')

#: The walk those hunts spent, which every row's ``plan_cost`` already pays for -- so `FREE_REACH` is
#: what a station may cost nothing. `station_map` re-checks it against the dumps (see `arrival_frames`).
WALK_FRAMES = 2
WALK_CAP = AW.WALK_CAP
FREE_REACH = WALK_CAP * WALK_FRAMES


def station_map(rows, *, hunts=HUNTS, gen=None, tol=0.05, quantum=4.0):
    """``{row idx: [(x, z), ...]}`` -- the LIVE stations each row's `plan_cost` was measured at.

    The rows ARE the hunts' hits (session 104 swept Tetra's placement and kept the ones carrying live
    walkable dust), so the join is on the placement coordinate, ``tol`` u exact-enough to be an
    identity and not a nearest-match. Stations are deduped onto a ``quantum`` grid because this feeds
    a RANK that runs per atom variant: the gap it prices is tens of units and the reduction costs it
    nothing, while the honest claim about an arrival is always `entry_reach.hull_scan`, never this
    distance (`[[banded-proxy-needs-its-newton]]`).

    A row with no hunted station is simply ABSENT from the map, and the keep must then treat it as
    UNMEASURED rather than free -- the `full_herd.extend_cycle` ``cloud_cap`` lesson: an unprobed
    candidate keeps an infinite bound, it never inherits a default.

    Raises if a dump's own walk budget is not `WALK_FRAMES`, since `FREE_REACH` -- what the arrival
    term credits for free -- is derived from it."""
    gen = gen or os.path.join(_d, '_generated')
    out, seen = {}, {}
    for name in hunts:
        path = os.path.join(gen, *name.split('/'))
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            d = json.load(fh)
        for c in d['cells']:
            if int(c.get('frames', WALK_FRAMES)) != WALK_FRAMES:
                raise ValueError("%s cell %s was hunted at a %d-frame walk, not %d -- FREE_REACH is"
                                 " derived from that budget, so re-derive it before using this dump"
                                 % (name, c.get('cell'), int(c['frames']), WALK_FRAMES))
            for h in c['hits']:
                hx, hz = h['tetra']
                for r in rows:
                    if abs(r['x'] - hx) > tol or abs(r['z'] - hz) > tol:
                        continue
                    if math.hypot(r['x'] - hx, r['z'] - hz) >= tol:
                        continue
                    idx = r['idx']
                    keys = seen.setdefault(idx, set())
                    pts = out.setdefault(idx, [])
                    for q in h['live_at']:
                        k = (round(q[0] / quantum), round(q[1] / quantum))
                        if k not in keys:
                            keys.add(k)
                            pts.append((float(q[0]), float(q[1])))
    return out


def station_gap(link_end, stations):
    """Link's distance to the nearest of a row's stations -- None on an empty/absent station set, so a
    caller cannot silently read "unmeasured" as "zero"."""
    if not stations or link_end is None:
        return None
    lx, lz = link_end
    return min(math.hypot(lx - q[0], lz - q[1]) for q in stations)


def arrival_frames(d_station, *, reach=FREE_REACH, cap=WALK_CAP):
    """**The frames an ARRIVAL still owes** -- `objective.remaining_frames`' twin for the other half of
    the delivery predicate (session 110).

    The landing's miss is priced at the plow ceiling; the arrival's station gap is priced at the walk
    cap, credited with ``reach`` -- the travel the row's own `plan_cost` already bought (`WALK_FRAMES`
    at the cap). They are the same currency because the frames that close a station gap are ordinary
    plan frames wherever they sit: the atom's exit-hold tail and the entry plan's walk cost one frame
    each (`knowledge/strategy/delivery-is-two-predicates.md`).

    OPTIMISTIC by construction, and in exactly the way `objective.plan_bound`'s ``h`` is: it prices a
    straight line at the cap, while the reachable set is a FAN pointed along Link's facing, not a disc
    -- so a gap this reads as payable can still refuse. It sizes the cut; `entry_reach.hull_scan` at
    the candidate's own arrival makes the claim."""
    if d_station is None:
        return float('inf')                  # unmeasured is not free -- see `station_map`
    return max(0.0, float(d_station) - float(reach)) / float(cap)


def exit_arc(run0, hl, *, step=0x800, half=0x2000):
    """The exit-hold bearings a tail can run along -- `away_walk.flip_arc`'s counterpart for the OTHER
    end of the atom (session 110).

    The grid's standing pair is the live entry bearing and the herd's up-bearing, which is the right
    direction and not a steering axis: a tail runs along it at the cap, so the bearing decides WHERE
    the arrival lands, and a row's stations are a few points at a specific lateral offset. Sweeping an
    arc about both is what lets the tail aim at them. It also touches the LANDING, since the exit
    stick is already held while the conversion frames are still plowing her -- so this is a joint
    knob, not an arrival-only one, and it is priced by the same enumeration as the rest.

    Expensive on the full grid (an arc of n bearings is n/2 x the rollouts), so the pattern is the
    module's own: the default pair sizes the search, and a focused pass sweeps the arc at the few
    endpoints worth refining."""
    from tww_sim.land.plan_land._primitives import world_angle_s16
    ex, ez = SD.ENTRY_ROLL_POS
    centres = [world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z),
               (hl.bearing_bam() + 0x8000) & 0xFFFF]
    out = set(centres)
    if step:
        n = int(half) // int(step)
        for c in centres:
            for i in range(-n, n + 1):
                out.add((c + i * int(step)) & 0xFFFF)
    return sorted(out)


def _arc(run0, hl, step, half):
    """The bearings a caller's ``exit_step``/``exit_half`` ask for, or None -- the standing pair
    `atom_cloud` defaults to.

    Resolved PER ENDPOINT, which is why the plumbed knob is an arc SPEC and not the bearing list
    `atom_cloud` takes: `exit_arc`'s centres are the live entry bearing -- measured from Link's own
    position -- and the herd up-bearing, so the same s16 numbers name different directions relative to
    two endpoints, and one list hoisted to a beam would sweep a different axis at each of them (and
    would not contain either one's own control)."""
    if step is None:
        return None
    return exit_arc(run0, hl, step=int(step), half=(ARC_HALF if half is None else int(half)))


def atom_cloud(run0, hl, *, flip_step=FLIP_STEP, rotate_offs=None, max_frames=18, csangle='live',
               exit_runs=(0,), exit_bearings=None):
    """Every atom variant `away_walk.probe` sweeps, with the RANK REMOVED -- the full knob grid as a
    list of results, each carrying its ``knobs``.

    This is `away_walk.probe`'s own loop minus its ``best`` reduction, and it is deliberately a
    separate function rather than a flag on it: `probe` returns ONE variant because its callers rank
    endpoints, while a landing keep needs the whole grid to read a (miss, total) front off. The
    acceptance is not applied here either -- `away_walk.fires` is the filter and stays the caller's,
    so a census of what refused is always available (`away_walk.fires_census`).

    Runs every variant at the arrival's OWN camera (``csangle='live'``, session 73's honest default):
    the atom's C-stick is neutral, so this is what a plain replay delivers, and no variant is billed
    for a camera state nothing in the plan paid for.

    ``exit_runs`` crosses the grid with the atom's TAIL (`away_walk.escape_atom`'s ``exit_run``) -- the
    axis that moves Link's ARRIVAL, which every enumeration before session 110 was blind to because
    the atom always stopped at its handoff. It costs almost nothing: one rollout per knob combo at the
    longest tail, read back as each shorter one (`away_walk.tail_variant`, gated bit-exact against a
    fresh rollout), and a tail the follow bar cut short is simply ABSENT rather than truncated.

    ``exit_bearings`` replaces the standing pair (live entry bearing, herd up-bearing) with an
    explicit set -- `exit_arc` builds one. Unlike the tail it is NOT free: each bearing is its own
    rollout."""
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
    runs = sorted({int(k) for k in exit_runs})
    exits = (b_entry, up_herd) if exit_bearings is None else tuple(exit_bearings)
    out = []
    for flip in AW.flip_arc(hl, step=int(flip_step)):
        for ro in rots:
            for ta in (False, True):
                for side in (1, -1):
                    for exit_b in exits:
                        r = AW.escape_atom(run0, hl, turnaround_first=ta, rotate_side=side,
                                           rotate_off=ro, flip_bearing=flip, exit_bearing=exit_b,
                                           csangle=cs, max_frames=max_frames,
                                           exit_run=max(runs))
                        if r is None:
                            continue
                        knobs = dict(turnaround_first=ta, rotate_side=side, rotate_off=ro,
                                     flip_bearing=flip, exit_bearing=exit_b)
                        for k in runs:
                            v = AW.tail_variant(r, k)
                            if v is None:
                                if k or r['handoff_f'] is not None:
                                    continue
                                # never handed off: no tail exists, but the variant is still a member
                                # of the grid -- a refusal `away_walk.fires_census` has to see
                                v = dict(r)
                            v['knobs'] = dict(knobs, exit_run=k)
                            out.append(v)
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


def _joint_row(tx, tz, link_end, rows, stations):
    """`_nearest_row` with the ARRIVAL priced too -- the row that finishes soonest for a candidate
    that has to satisfy BOTH halves of the delivery predicate (session 110).

    Same currency and the same shape, one addend wider: ``plan_cost + remaining_frames(miss) +
    arrival_frames(gap to THAT row's stations)``. The row choice genuinely moves under it, which is
    the reason it is a separate function rather than a flag -- a row 6 u from the landing whose
    stations sit 130 u behind Link loses to one 20 u away that his own hull already covers.

    A row absent from ``stations`` is UNMEASURED and is skipped, never scored as free (`station_map`);
    ``n_rows`` reports how many were actually eligible, so a caller can see when the map is the thing
    doing the pruning. Returns ``(miss, row, d_station, arr_frames, n_rows)``."""
    best, n = None, 0
    for p in rows:
        st = stations.get(p.get('idx')) if stations else None
        if not st:
            continue
        n += 1
        d = math.hypot(p['x'] - tx, p['z'] - tz)
        ds = station_gap(link_end, st)
        af = arrival_frames(ds)
        k = (float(p.get('plan_cost', 0)) + O.remaining_frames(d) + af, d)
        if best is None or k < best[0]:
            best = (k, d, p, ds, af)
    if best is None:
        return (float('inf'), None, None, float('inf'), 0)
    return (best[1], best[2], best[3], best[4], n)


def cloud_landing(run0, frames, hl, rows, *, band=None, flip_step=FLIP_STEP, rotate_offs=None,
                  max_frames=18, csangle='live', front=True, stations=None, exit_runs=(0,),
                  exit_step=None, exit_half=None):
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
    a plan (rule 3, `away_walk.fires`).

    Pass ``stations`` (`station_map`) to make the keep JOINT (session 110): the row choice and the rank
    then carry `arrival_frames` beside the landing miss, every record gains ``link_end``/``d_station``,
    and a fourth field appears --
      * ``joint`` -- the cheapest-TOTAL variant that pays BOTH halves: inside ``band``, with its row's
        stations already inside the arrival's own walk budget (``arr_frames == 0``, so its bound IS
        its total), AND ``settled`` at `away_walk.WALK_CAP`. The last clause is not a nicety: an
        arrival still mid-backslide fans an EMPTY walk cloud (`entry_fan.iter_fan2` keeps junctions
        only at the cap), so it reaches no station at any distance and cannot be said to owe nothing.
        ``in_band`` answers the landing alone and is what sessions 107-109 mistook for a solve; this
        is the field that means "nothing is owed" (still owing `entry_reach.hull_scan` at the
        arrival, which is the claim -- see `arrival_frames`).
    ``exit_runs`` hands the tail axis through to `atom_cloud`, which is what makes a station gap
    payable at all, and ``exit_step``/``exit_half`` hand through the arc it runs ALONG (`_arc`, added
    session 119). The second is the axis this keep owned and never turned: session 110 built `exit_arc`
    and no enumeration could reach it, because only `atom_cloud` took bearings and every caller above
    it -- this function, `cloud_probe`, `full_herd.extend_cycle` -- passed none. Session 118 swept it
    by hand at 14 already-chosen endpoints and measured the in-band station gap 160 u -> 9.9 u and the
    delivered figure 106.45 -> 103.45, so the axis is worth ~3 frames at fixed endpoints and had never
    entered a cut. Default None = the standing pair, so every banked number is unchanged; `ARC_STEP` /
    `ARC_HALF` is what session 118 priced, and it costs ~13x the pair per endpoint."""
    bd = O.PLACEMENT_BAND if band is None else float(band)
    variants = atom_cloud(run0, hl, flip_step=flip_step, rotate_offs=rotate_offs,
                          max_frames=max_frames, csangle=csangle, exit_runs=exit_runs,
                          exit_bearings=_arc(run0, hl, exit_step, exit_half))
    firing = [r for r in variants if AW.fires(r)]
    base = dict(n_variants=len(variants), n_firing=len(firing))
    if not firing:
        return dict(base, fires=False, bound=float('inf'), best=None, in_band=None, joint=None,
                    front=[])

    scored = []
    for r in firing:
        tx, tz = r['tetra_end']
        le = r['link_end']
        if stations:
            miss, row, d_st, af, _n = _joint_row(tx, tz, le, rows, stations)
            if row is None:
                continue
        else:
            miss, row = _nearest_row(tx, tz, rows)
            d_st, af = None, 0.0
        n_atom = len(r['log'])
        total = frames + n_atom + float(row.get('plan_cost', 0))
        scored.append(dict(miss=miss, total=total,
                           bound=total + O.remaining_frames(miss) + af,
                           row_idx=row.get('idx'), row_cost=row.get('plan_cost'),
                           n_atom=n_atom, freeze_f=r['freeze_f'],
                           resid=(r['resid_along'], r['resid_lat']),
                           tetra_end=(tx, tz), link_end=le, d_station=d_st, arr_frames=af,
                           settled=r.get('settled'), knobs=dict(r['knobs'])))
    if not scored:
        return dict(base, fires=False, bound=float('inf'), best=None, in_band=None, joint=None,
                    front=[])
    scored.sort(key=lambda s: (s['bound'], s['miss']))
    best = scored[0]
    inb = [s for s in scored if s['miss'] <= bd]
    inb.sort(key=lambda s: (s['total'], s['miss']))
    jnt = [s for s in inb if s['arr_frames'] == 0.0 and s['d_station'] is not None and s['settled']]
    pf = []
    if front:
        for s in sorted(scored, key=lambda s: (s['total'], s['miss'])):
            if not pf or s['miss'] < pf[-1]['miss']:
                pf.append(s)
    return dict(base, fires=True, bound=best['bound'], best=best,
                in_band=(inb[0] if inb else None), joint=(jnt[0] if jnt else None), front=pf)


def residual_fan(endpoints, hl, *, flip_step=FLIP_STEP, rotate_offs=None, max_frames=18,
                 quantum=1.0, exit_runs=(0,), exit_step=None, exit_half=None):
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
    predictor sizes the CUT, the enumeration makes the CLAIM (`[[banded-proxy-needs-its-newton]]`).

    **Each member also carries the THROW** -- Link's own displacement over the same variant
    (``throw_along``/``throw_lat``, herd coords) -- which is what lets `predict_bound` price the
    ARRIVAL half beside the landing (session 115). It belongs here for the same reason the residual
    does: session 114 measured the throw to be a rigid property of the (node, log length) class rather
    than a steering channel, so it is a member of a measured SET exactly as the residual is, and it is
    kept per member rather than averaged because at some postures the class spans 15 x 48 u.

    ``exit_runs`` crosses the fan with the atom's tail, whose whole effect is on the throw (past
    ``freeze_f`` Tetra takes no more push, so a tail moves Link and not her). Default ``(0,)`` keeps
    the fan a landing table verbatim; a caller pricing arrivals should pass `EXIT_RUNS`.

    ``exit_step``/``exit_half`` (session 119) cross it with the tail's BEARING (`_arc`), and for the
    arrival half that is the axis with the authority: a tail runs at the cap along the bearing it
    holds, so the throw a member carries is mostly a statement about which direction the exit stick
    was pointing. Without it the fan holds two directions and `predict_bound` prices every arrival as
    if the plan could only leave along one of them -- which is how a cut whose keep can reach the arc
    (`cloud_landing`) still chooses endpoints as though it could not."""
    seen, out = set(), []
    for ep in endpoints:
        run0 = ep['run'] if isinstance(ep, dict) else ep
        la0 = hl.along(run0.link.pos_x, run0.link.pos_z)
        ll0 = hl.lateral(run0.link.pos_x, run0.link.pos_z)
        for r in atom_cloud(run0, hl, flip_step=flip_step, rotate_offs=rotate_offs,
                            max_frames=max_frames, exit_runs=exit_runs,
                            exit_bearings=_arc(run0, hl, exit_step, exit_half)):
            if not AW.fires(r):
                continue
            n_atom = len(r['log'])
            lx, lz = r['link_end']
            ta, tl = hl.along(lx, lz) - la0, hl.lateral(lx, lz) - ll0
            key = (round(r['resid_along'] / quantum), round(r['resid_lat'] / quantum), n_atom,
                   round(ta / quantum), round(tl / quantum))
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(along=r['resid_along'], lat=r['resid_lat'], n_atom=n_atom,
                            throw_along=ta, throw_lat=tl))
    out.sort(key=lambda m: (m['n_atom'], m['lat'], m['along']))
    return out


def herd_stations(stations, hl):
    """`station_map`'s world points in HERD coordinates -- ``{row idx: [(along, lat), ...]}``.

    The projection is a rotation about Tetra's start (`reposition.HerdLine`), so a distance measured
    in either frame is the same number; this exists only so `predict_bound` can work in one frame
    without re-projecting per aim (it runs inside the per-aim screen, tens of thousands of times)."""
    return {k: [(hl.along(x, z), hl.lateral(x, z)) for (x, z) in pts]
            for k, pts in (stations or {}).items()}


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


def predict_bound(t_along, t_lat, frames, fan, rows, *, link=None, stations=None):
    """**The cheap predictor `cloud_landing` is the exact confirm of**: the best whole-candidate frame
    bound a herd endpoint could reach, over the residual FAN crossed with the rows.

    Same currency as `cloud_landing`'s ``bound`` -- herd frames + the atom's own log + the row's
    ``plan_cost`` + the remaining miss at `objective.PUSH_CEILING` -- so the two are directly
    comparable, which is the only way to know what the prediction is worth. Costs one pass over
    ``len(fan) * len(rows)`` distances against ~28 s for the enumeration, so this is what a per-aim cut
    inside the last cycle can afford and the enumeration is not.

    **Pruned by its own arithmetic** (session 119), which is what keeps that true once the fan is a
    real one: a member costs ``n_atom`` frames whatever it lands, and both remaining terms are >= 0, so
    its best conceivable bound is ``frames + n_atom + min(plan_cost)``. Once an incumbent beats that,
    the member cannot be the minimum and its whole row loop is skipped -- exact, never an
    approximation, and it returns the identical record. It matters because the fan is not the 178
    members session 107 measured: with the throw (2 more dedup dimensions), the tail and the arc it is
    **75627**, and the unpruned pass costs ~10 s per aim against **26 ms** pruned. Cheap members first
    is what makes it bite, which is the order `residual_fan` already returns.

    It is a LOWER bound on the enumerated bound only to the extent the fan is reachable from THIS state
    (see `residual_fan`) -- an optimistic proxy, in the same family as `objective.plan_bound`'s ``h``,
    and it must be Newtoned onto the real thing before it is quoted. Returns ``dict(bound, miss, total,
    row_idx, n_atom, resid, d_station, arr_frames)`` for the best pair, or None on an empty fan.

    ``link``/``stations`` (session 115) make the prediction JOINT, and without them this scores exactly
    half a candidate. `cloud_landing` has priced the arrival since session 110, but it runs only at the
    SURVIVORS -- the per-aim screen this feeds (`full_herd.roll_probe`'s ``cloud_bound``) is the cut
    that decides which endpoints exist, and it could see only the landing. Measured on the session-111
    cycle-3 beam, that blindness is not academic: the two halves are anti-correlated across it (node 0
    lands 25.4 u out with the arrival already free, node 3 lands 4.7 u out with its stations 136.8 u
    away), so a landing-only screen keeps exactly the endpoints whose arrival cannot be paid.

    Given Link's herd-coordinate endpoint and `herd_stations`, each fan member's own ``throw`` places
    his arrival (``link + throw``) and `arrival_frames` prices the gap to THAT row's stations, in the
    same currency. A row absent from ``stations`` is UNMEASURED and skipped, never scored as free
    (`station_map`) -- so the two branches genuinely differ in which rows they may quote.

    **A fan member with no throw is REFUSED in that branch, never defaulted to zero** (session 119).
    It read ``m.get('throw_along', 0.0)`` until then, and the fan every joint cut since session 115
    was actually handed -- ``_generated/s106/s107_fan.json``, measured in session 107, before the throw
    existed -- carries the column on **0 of its 178 members**. So the screen placed Link's arrival at
    the roll TERMINAL and called that his arrival, which is not a small error in the direction of
    caution: session 118 measured the terminal gap at 67.6-106.7 u and the same candidates' post-atom
    gap at 159.5-176.3, i.e. the atom roughly DOUBLES what this was pricing. A missing measurement is
    the module's oldest rule (`station_map`, `arrival_frames`) and it applies to the fan too."""
    hst = None if (link is None or not stations) else stations
    if hst is not None and any('throw_along' not in m or 'throw_lat' not in m for m in fan):
        raise ValueError("this fan carries no THROW, so the arrival it prices is Link's roll terminal"
                         " and not his arrival (session 118: the atom roughly doubles the gap)."
                         " Rebuild it with `residual_fan`, which has carried the throw since session"
                         " 115 -- a pre-s115 dump such as s107_fan.json cannot price this half")
    # the prune's floor: the cheapest row a member may be quoted against, which in the joint branch is
    # the cheapest MEASURED one (an unstationed row is skipped below, so it may not lower the floor)
    costs = [float(r.get('plan_cost', 0)) for r in rows
             if hst is None or hst.get(r.get('idx'))]
    if not costs:
        return None
    floor = frames + min(costs)
    best = None
    for m in fan:
        if best is not None and floor + m['n_atom'] >= best['bound']:
            continue                         # cannot be the minimum -- see the docstring's prune
        pa, pl = t_along + m['along'], t_lat + m['lat']
        if hst is not None:
            la = link[0] + m['throw_along']
            ll = link[1] + m['throw_lat']
        for r in rows:
            ds = af = None
            if hst is not None:
                st = hst.get(r.get('idx'))
                if not st:
                    continue                 # unmeasured is not free -- see `station_map`
                ds = min(math.hypot(la - q[0], ll - q[1]) for q in st)
                af = arrival_frames(ds)
            d = math.hypot(r['along'] - pa, r['lat'] - pl)
            total = frames + m['n_atom'] + float(r.get('plan_cost', 0))
            b = total + O.remaining_frames(d) + (af or 0.0)
            if best is None or b < best['bound']:
                best = dict(bound=b, miss=d, total=total, row_idx=r.get('idx'),
                            n_atom=m['n_atom'], resid=(m['along'], m['lat']),
                            d_station=ds, arr_frames=af)
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
                d_station=(b['d_station'] if b else None),
                arr_frames=(b['arr_frames'] if b else None),
                in_band=res['in_band'], joint=res['joint'], front=res['front'])
