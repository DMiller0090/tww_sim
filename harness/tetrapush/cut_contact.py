"""**THE CUT FRAME HAS ONE FREE VARIABLE, AND IT IS NOT THE ENTRY -- IT IS WHERE TETRA STANDS** (s157).

Session 156 measured that 97% of the barren sweep's evaluations were out of contact at the cut and asked
the next session to prune them before paying for the roll, predicting the cut step's position as
``entry + sum(dx, dz)``. That arithmetic is not the roll -- it runs 255 u past where Link actually ends
up, because the roll is wall-corrected -- and the prefilter it was meant to build **cannot exist**. Both
findings are measurements, and both are gated:

  * **INSIDE THE REACHABLE ENTRY BOX AN UNTOUCHED ROLL HAS NO FREEDOM LEFT.** Every entry a plan can
    reach (`entry_search.reach_radius`, 94 u) drives the roll into the same courtyard wall, and the wall
    absorbs the difference: over that box the cut frame's ``old``, its Co centre, its ``new`` and its
    residual come back BIT-IDENTICAL, one distinct value each for 169 entries -- while the same probe at
    radius 150 u returns 30. So out of contact THE ENTRY DOES NOTHING; everything it buys the search, it
    buys through Tetra. `braced_row` is that one row, from one sweep; `braced_invariance` is the
    measurement it stands on.
  * **CONTACT IS COMMON; CONSEQUENCE IS RARE.** On a real item's own candidates, 99.3% of rows plow Tetra
    23-68 u and only **2.2%** end with any different cut-frame state at all, because the brace eats
    Link's half of the ejection and CrrPos returns him to the same point. A prefilter would have to
    predict the 2.2%, not the contact -- and the necessary geometric condition (Tetra anywhere near the
    swept no-Tetra path, inflated by her own plow) keeps 94-100% of rows, which prunes nothing. The
    saving is real (97.8% of rows ARE one constant) but it is not reachable through geometry.

**WHAT REPLACES IT.** With ``old`` pinned by the brace, the razor is a function of ONE 2-D variable:
Tetra's position on the contact frame. `ShoveCtx` already takes that variable -- ``placed_step`` puts her
anywhere in the schedule -- so `cut_slice` places her ON the contact step and reads the razor straight
off the native sim, bit-exact, ~66 us a point and entry-invariant, no fan anywhere. `target_ring` turns
that into the thing a search can aim at: per bearing off the braced Co centre, the distance at which the
cut ray crosses the seam vertex, with the genuine verdict measured on the f32 lattice around it.

**HONEST LIMITS.** The slice pins ``old`` at the braced value, and a real plan's ``old`` is not exactly
that: s154's accepted 101 sits 0.0127 u off it (an earlier frame's push), which moves its residual by
~1e-02 -- a hundred times the razor's own width. So a ring bearing/distance is an AIM, good to ~0.1 u,
and the last 1e-04 is what the entry lattice is for (`entry_dust`). Read the ring as where to put her,
never as a plan.
"""
import math
import struct

from harness.tetrapush import entry_search as ES
from tww_sim.core.fp import f32

#: Link Co radius + Tetra Co radius: the cyl-cyl contact distance `_shovec._run` tests. Stated as the
#: two radii so this module carries no import cycle through `terminal`.
CO_R_SUM = ES.LINK_CO_R + ES.TETRA_CO_R

#: Where to park Tetra for a reference roll she cannot touch -- far enough to never contact, close
#: enough to stay in the courtyard's own collision neighbourhood.
FAR_TETRA = (2000.0, 2000.0)


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def _build(facing, lean, thrust, nspeed, ctx, sch, resid):
    return (ctx, sch, resid) if ctx is not None else ES.build_fast(facing, lean, thrust,
                                                                   nspeed=nspeed)


def braced_row(facing, lean, thrust, *, nspeed=None, entry=None, ctx=None, sch=None, resid=None,
               tetra=FAR_TETRA):
    """The row an UNTOUCHED roll returns, from one sweep -- the same row for every reachable entry.

    Returns ``dict(row, co, old, new, push, resid, genuine, overlap, entry, tetra_far)``. ``row`` is the
    `ShoveCtx.sweep_par(extra=True)` tuple itself, so a caller can hand it to whatever reads a swept row;
    ``co`` is the Co centre on the CONTACT step (``cut_step - 1``, the pair whose push the cut frame
    consumes) and is the origin `target_ring` measures Tetra from.

    Valid for any entry inside `braced_invariance`'s box -- pass ``entry`` only to move the reference
    itself. ``ctx``/``sch``/``resid`` take a pool's build so a caller does not compile the world twice."""
    ctx, sch, resid = _build(facing, lean, thrust, nspeed, ctx, sch, resid)
    e = (sch['link_x0'], sch['link_z0']) if entry is None else (f32(entry[0]), f32(entry[1]))
    o = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1])], 0, extra=True)[0]
    return dict(row=o, co=(o[10], o[11]), old=(o[1], o[2]), new=(o[3], o[4]), push=(o[5], o[6]),
                resid=resid(o), genuine=bool(o[0]), tetra_far=list(tetra), entry=list(e),
                overlap=CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13]))


def braced_invariance(facing, lean, thrust, centre, *, radius=None, n=13, nspeed=None,
                      tetra=FAR_TETRA):
    """**THE MEASUREMENT `braced_row` STANDS ON**: how many DISTINCT untouched rows an entry box
    produces. One is the claim, and it is why a slice may pin ``old`` and vary only Tetra.

    Sweeps an ``n x n`` grid of entries at ``+-radius`` (default `entry_search.reach_radius`) with Tetra
    parked out of reach and counts DISTINCT BIT PATTERNS, never a tolerance. Returns ``dict(entries,
    radius, distinct_old, distinct_co, distinct_new, distinct_resid, invariant, genuine)``."""
    radius = ES.reach_radius() if radius is None else float(radius)
    ctx, sch, resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
    step = 2.0 * radius / (n - 1)
    ents = [(centre[0] - radius + i * step, centre[1] - radius + j * step)
            for i in range(n) for j in range(n)]
    rows = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1]) for e in ents], 0, extra=True)
    old = {(_bits(o[1]), _bits(o[2])) for o in rows}
    co = {(_bits(o[10]), _bits(o[11])) for o in rows}
    new = {(_bits(o[3]), _bits(o[4])) for o in rows}
    res = {_bits(resid(o)) for o in rows}
    return dict(entries=len(ents), radius=radius, distinct_old=len(old), distinct_co=len(co),
                distinct_new=len(new), distinct_resid=len(res),
                invariant=bool(len(old) == len(co) == len(new) == len(res) == 1),
                genuine=sum(1 for o in rows if o[0]))


# ------------------------------------------------- the razor as a function of where Tetra stands

def cut_slice(facing, lean, thrust, tetras, *, nspeed=None, entry=None, ctx=None, sch=None,
              resid=None):
    """Place Tetra ON the contact step and read the razor -- the map the search aims at.

    ``tetras`` is an iterable of her (x, z) on step ``cut_step - 1``. Everything before that step is the
    untouched roll, so Link arrives braced and ``old`` is the constant `braced_row` reports; the only
    input left is her position, which is exactly the CC pair the cut frame's push comes from.

    Returns one ``dict(tetra, dist, push, resid, genuine, overlap, new)`` per placement, in order.
    ``dist`` is her distance from the braced Co centre -- contact needs it under `CO_R_SUM`."""
    ctx, sch, resid = _build(facing, lean, thrust, nspeed, ctx, sch, resid)
    e = (sch['link_x0'], sch['link_z0']) if entry is None else (f32(entry[0]), f32(entry[1]))
    pts = [(t[0], t[1], e[0], e[1]) for t in tetras]
    rows = ctx.sweep_par(pts, sch['cut_step'] - 1, extra=True)
    out = []
    for t, o in zip(pts, rows):
        d = math.hypot(o[10] - o[12], o[11] - o[13])
        out.append(dict(tetra=(o[12], o[13]), dist=d, push=(o[5], o[6]), resid=resid(o),
                        genuine=bool(o[0]), overlap=CO_R_SUM - d, new=(o[3], o[4])))
    return out


def ring_point(co, bearing, dist):
    """Tetra's placement at ``dist`` from the braced Co centre along a BAM ``bearing`` -- the ring's
    own coordinate, so a caller reports a target the same way twice."""
    from tww_sim.core import mathlib as ML
    b = int(bearing) & 0xFFFF
    return (co[0] + dist * ML.cM_ssin_s16(b), co[1] + dist * ML.cM_scos_s16(b))


#: A refined crossing whose own residual is above this is a JUMP, not a zero (knowledge/model/braced-cut-
#: frame.md); 48 halvings of the scan step land far under it, so this size is a straddled discontinuity.
JUMP_RESID = 1e-3


def zero_bearing(facing, lean, thrust, bearing, *, lo=1.0, hi=None, scan=0.25, iters=48,
                 nspeed=None, ctx=None, sch=None, resid=None, braced=None):
    """Every distance along one bearing at which the cut ray crosses the seam vertex (``resid = 0``).

    SCANS the contact band first and only then bisects, because a sign change is not always a zero: deep
    inside the overlap the residual STEPS, and a blind bisection between the band's two ends converges on
    a discontinuity and reports it as a target (measured -- it returned dist 34.93 at resid +20.5). Each
    refined crossing is kept only if its own residual lands under `JUMP_RESID`.

    Returns ``dict(bearing, crossings, dist, resid, genuine, bracketed, scanned, jumps)`` -- ``dist`` is
    the OUTERMOST crossing, the grazing one the console's own row sits on, and ``crossings`` is all of
    them, outermost first."""
    ctx, sch, resid = _build(facing, lean, thrust, nspeed, ctx, sch, resid)
    br = braced_row(facing, lean, thrust, ctx=ctx, sch=sch, resid=resid) if braced is None else braced
    hi = CO_R_SUM if hi is None else float(hi)
    n = max(2, int((hi - float(lo)) / float(scan)) + 1)
    ds = [float(lo) + i * (hi - float(lo)) / (n - 1) for i in range(n)]
    rs = [r['resid'] for r in cut_slice(facing, lean, thrust,
                                        [ring_point(br['co'], bearing, d) for d in ds],
                                        ctx=ctx, sch=sch, resid=resid)]
    out = dict(bearing=int(bearing) & 0xFFFF, scanned=n, crossings=[], jumps=0)
    for i in range(n - 1):
        if (rs[i] < 0.0) == (rs[i + 1] < 0.0):
            continue
        a, ra, b = ds[i], rs[i], ds[i + 1]
        for _ in range(int(iters)):
            m = 0.5 * (a + b)
            rm = cut_slice(facing, lean, thrust, [ring_point(br['co'], bearing, m)],
                           ctx=ctx, sch=sch, resid=resid)[0]['resid']
            if (rm < 0.0) == (ra < 0.0):
                a, ra = m, rm
            else:
                b = m
        row = cut_slice(facing, lean, thrust, [ring_point(br['co'], bearing, 0.5 * (a + b))],
                        ctx=ctx, sch=sch, resid=resid)[0]
        if abs(row['resid']) > JUMP_RESID:
            out['jumps'] += 1
            continue
        out['crossings'].append(dict(dist=0.5 * (a + b), resid=row['resid'],
                                     genuine=row['genuine'], tetra=list(row['tetra']),
                                     overlap=row['overlap'], push=list(row['push'])))
    out['crossings'].sort(key=lambda c: -c['dist'])
    top = out['crossings'][0] if out['crossings'] else None
    out.update(bracketed=bool(top), dist=(top and top['dist']), resid=(top and top['resid']),
               genuine=bool(top and top['genuine']))
    return out


def target_ring(facing, lean, thrust, *, step=64, nspeed=None, ctx=None, sch=None, resid=None,
                braced=None, lattice=0, **kw):
    """**THE AIM.** Where Tetra has to stand on the contact frame, bearing by bearing.

    Sweeps BAM bearings in ``step`` increments around the braced Co centre and bisects each for the
    residual's zero (`zero_bearing`). With ``lattice > 0`` each ring point is then re-tested over the
    ``(2*lattice+1)`` f32 placements either side of it -- her position is an f32 pair like the entry,
    so a scan finer than her own ULP re-tests one point (the s156 lesson, in the new coordinate).

    Returns ``dict(braced, points, live, bearings, genuine)`` -- ``points`` the bracketed ring, ``live``
    the subset with a genuine placement on the lattice."""
    from harness.tetrapush import entry_dust as ED
    ctx, sch, resid = _build(facing, lean, thrust, nspeed, ctx, sch, resid)
    br = braced_row(facing, lean, thrust, ctx=ctx, sch=sch, resid=resid) if braced is None else braced
    pts, live = [], []
    for b in range(0, 0x10000, int(step)):
        z = zero_bearing(facing, lean, thrust, b, ctx=ctx, sch=sch, resid=resid, braced=br,
                         nspeed=nspeed, **kw)
        if not z['bracketed']:
            continue
        if lattice:
            p = ring_point(br['co'], b, z['dist'])
            cand = [(ED.lattice_step(p[0], i), ED.lattice_step(p[1], j))
                    for i in range(-lattice, lattice + 1) for j in range(-lattice, lattice + 1)]
            rows = cut_slice(facing, lean, thrust, cand, ctx=ctx, sch=sch, resid=resid)
            g = [r for r in rows if r['genuine']]
            z['tested'] = len(rows)
            z['lattice_genuine'] = len(g)
            z['genuine_at'] = [list(r['tetra']) for r in g[:4]]
            z['best_resid'] = min(abs(r['resid']) for r in rows)
        pts.append(z)
        if z['genuine'] or z.get('lattice_genuine'):
            live.append(z)
    return dict(braced=dict((k, br[k]) for k in ('co', 'old', 'resid', 'genuine')),
                points=pts, live=live, bearings=0x10000 // int(step),
                genuine=sum(1 for p in pts if p['genuine'] or p.get('lattice_genuine')))
