"""**THE GENUINE-DUST DENSITY OF A CONFIGURATION, PER ENTRY THE SEARCH CAN ACTUALLY REACH** (s156).

Session 155 measured that every near-razor row of the barren sweep is refused at the barrier -- the swept
lunge path hits the wall -- and that `resid` cannot see it. This is the coordinate that can: the roll
ENTRY is an f32 pair (`ShoveCtx._run` starts from ``f32(link_x0), f32(link_z0)``), so the entries a search
can reach near the razor form a LATTICE with a one-ULP pitch, and the only honest denominator for "can
this configuration clip" is lattice points TESTED.

That denominator is what the older probes lack, and it is why their negatives were not evidence:

  * `entry_search.configuration_band` sweeps +-0.006 u across the locus in 1201 samples -- 1e-05 u apart,
    so ~12 consecutive samples collapse onto the SAME f32 entry, and at a steep configuration the whole
    sweep spans a single lattice rung;
  * `entry_search.locus_scan` sweeps +-0.02 u in 2001 -- the same defect. Its "0 live" at
    ``|d resid / d entry| = 31`` is one lattice rung's worth of evidence, not a barren configuration.

`dust_density` marches the residual zero exactly as `locus_scan` does (re-projecting at every station,
because the curve bends) and at each station tests the true f32 lattice neighbourhood, bit-stepped. What
comes back is comparable ACROSS configurations and converts straight into "this configuration needs N
times more candidates than the one that delivered".

**WHAT IT FOUND (s156, at s154's accepted-101 Tetra, lean and thrust):** the dust lives in a couple of
16-BAM sine CELLS and nowhere else. Over a 300 u march, cell 2551 carries 763 genuine of 4617 lattice
entries (1 in 6) and cell 2545 228 of 5265, while cell 2548 reads 0 of 4698 and cell 2544 0 of 4617.
The live set barely moves as the herd plows Tetra 45 u further down the line, and the density at a fixed
live cell is a flat 4-6% at every Tetra where contact exists at all -- so the axis that decides whether
ANY entry can clip is the roll FACING, not the herd depth and not the entry density.

**HONEST LIMITS.** ``genuine`` counts sweep-level acceptances, which are PREDICTIONS -- `overnight.accept`
(a real A-press through `entry_search.confirm_entry`, then the walled `cross_engine.agree`) is what makes
one a plan, and about one aim in eight brakes on the entry frame. ``density`` is per lattice point tested
NEAR THE LOCUS, never per entry in the plane. And the march is finite: ``genuine == 0`` means "none in
this arc at this resolution", which is why ``tested`` is returned beside it and belongs in any quote.
Outside contact the razor's residual is a dead constant (`zero_the_resid`: a grad that stays ~0 means the
pushed actor is out of Co range on the cut frame), so those configurations come back ``reason='no
leverage'`` with ``tested = 0`` rather than a fabricated zero density.
"""
import math
import struct

from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_search as ES


def entry_ulp(v):
    """One f32 ULP at ``v`` -- the entry lattice's own pitch, bit-derived rather than assumed."""
    b = struct.unpack('<I', struct.pack('<f', v))[0]
    a = struct.unpack('<f', struct.pack('<I', b))[0]
    return abs(struct.unpack('<f', struct.pack('<I', b + 1))[0] - a)


def lattice_step(v, n):
    """``v`` advanced ``n`` f32 lattice steps toward +infinity (negative ``n`` the other way).

    Stepping the BIT PATTERN, not adding ``n * ulp``: a diagonal offset of a fraction of an ULP rounds
    back onto the same float, so an "n-step walk" built by arithmetic silently re-tests one entry."""
    b = struct.unpack('<I', struct.pack('<f', v))[0]
    return struct.unpack('<f', struct.pack('<I', (b - n) if v < 0 else (b + n)))[0]


def dust_density(tetra, facing, thrust, lean, ref_entry, *, span=150.0, step=3.0, k=4,
                 nspeed=None, keep=12):
    """Genuine dust per REACHABLE f32 entry on one configuration's locus.

    Marches the residual zero from ``ref_entry`` out to ``+-span`` in ``step`` u stations, and at each one
    tests the ``(2k+1)^2`` f32 lattice entries around it. Returns ``dict(density, genuine, tested,
    stations, grad, dust, drops, reason)``; ``dust`` keeps up to ``keep`` genuine entries so a caller can
    aim at one instead of re-deriving it.

    Argument order follows `entry_search.locus_scan` -- ``(tetra, facing, thrust, lean, ref_entry)`` --
    on purpose; the two are asked side by side and a swapped thrust/lean is silent."""
    ctx, sch, resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
    g0 = ES.entry_gradient(tetra, ref_entry, facing=facing, m351c=lean, thrust=thrust, nspeed=nspeed)
    p, r, grad = ES.zero_the_resid(tetra, facing, thrust, lean, ref_entry, nspeed=nspeed)
    out = dict(facing=int(facing) & 0xFFFF, cell=ES.aim_cell(facing), lean=int(lean) & 0xFFFF,
               thrust=int(thrust), tetra=list(tetra), ref_entry=list(ref_entry),
               grad=g0['grad'], resid_step=g0['grad'] * entry_ulp(ref_entry[0]),
               zero_resid=r, zero_entry=list(p))
    if grad < 1e-3 or abs(r) > 1e-3:
        out.update(stations=0, tested=0, genuine=0, density=0.0, dust=[],
                   drops=dict(no_leverage=int(grad < 1e-3), no_zero=int(grad >= 1e-3)),
                   reason='no leverage at the seed' if grad < 1e-3 else 'resid will not zero')
        return out
    gg = ES.entry_gradient(tetra, p, facing=facing, m351c=lean, thrust=thrust, nspeed=nspeed)
    tx, tz = -gg['gz'] / gg['grad'], gg['gx'] / gg['grad']          # ALONG the locus, not across it
    pts, meta = [], []
    drops = dict(no_leverage=0, no_zero=0)
    stations = 0
    s = -span
    while s <= span:
        q = (p[0] + s * tx, p[1] + s * tz)
        s += step
        q, r2, g2 = ES.zero_the_resid(tetra, facing, thrust, lean, q, nspeed=nspeed)
        if g2 < 1e-3 or abs(r2) > 1e-3:
            drops['no_leverage' if g2 < 1e-3 else 'no_zero'] += 1
            continue
        stations += 1
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                pts.append((tetra[0], tetra[1], lattice_step(q[0], i), lattice_step(q[1], j)))
                meta.append(stations - 1)
    dust, ngen = [], 0
    if pts:
        for (_px, _pz, ex, ez), o, st in zip(pts, ctx.sweep_par(pts, 0), meta):
            if o[0]:
                ngen += 1
                if len(dust) < keep:
                    dust.append(dict(entry=[ex, ez], resid=resid(o), station=st,
                                     walkable=bool(TA.is_walkable(ex, ez))))
    out.update(stations=stations, tested=len(pts), genuine=ngen,
               density=(ngen / len(pts) if pts else 0.0), dust=dust, drops=drops, reason='')
    return out


def cell_dust(tetra, thrust, lean, ref_entry, cells, *, walk=None, span=150.0, step=3.0, k=4,
              nspeed=None, keep=4, progress=None):
    """`dust_density` per aim CELL -- the unit the search actually enumerates.

    ``cells`` is an iterable of either raw cell indices (``facing >> 4``) or ``(cell, facing)`` pairs;
    a bare cell is probed at its own canonical facing ``cell << 4``. A CELL IS ONE RAZOR DRAW at any
    camera (every term a facing reaches goes through ``jmaTable[angle >> 4]``, gated by
    `test_the_aim_alphabet_resolves_to_the_sine_table_cell`), so one probe per cell prices every facing
    and every aim byte inside it -- measured, not assumed, by
    `test_two_facings_in_one_cell_measure_the_same_dust`.

    ``walk`` is the WALK ENDPOINT, and passing it is the faithful call: the aim moves the roll entry a
    whole 26 u step (`entry_search.roll_entry`), so each cell reaches its OWN entry off the same
    endpoint, and seeding every cell from one ``ref_entry`` prices them at a point their own aim does not
    reach. It changes which ARC of each locus gets marched -- the live/dead verdict is robust to it
    (`test_the_live_dead_verdict_survives_reseeding_the_march`) but the counts are not, so a quoted
    density belongs with the seed it was measured from.

    Returns ``{cell: dust_density(...)}``, so a caller can drop every cell whose ``genuine`` is 0 before
    spending a fan on it. ``progress`` is an optional ``(cell, result) -> None`` callback."""
    out = {}
    for it in cells:
        cell, facing = it if isinstance(it, (tuple, list)) else (it, int(it) << 4)
        ref = ref_entry if walk is None else ES.roll_entry(walk, facing, nspeed)
        d = dust_density(tetra, facing, thrust, lean, ref, span=span, step=step, k=k,
                         nspeed=nspeed, keep=keep)
        out[int(cell)] = d
        if progress is not None:
            progress(int(cell), d)
    return out


def live_cells(cd, *, min_genuine=1):
    """The cells of a `cell_dust` result that carry dust, richest first: ``[(cell, density), ...]``."""
    return sorted(((c, d['density']) for c, d in cd.items() if d['genuine'] >= min_genuine),
                  key=lambda t: -t[1])


def needed_multiplier(cd, reference):
    """How many times more candidates a cell needs than ``reference``'s density, per cell.

    ``None`` where the cell measured no dust at all -- an unbounded multiplier is not a number, and
    reporting one as ``inf`` invites it into a rank. Cells with ``tested == 0`` (no leverage) are
    omitted entirely: they were never sampled, which is a different statement from sparse."""
    return dict((c, (None if not d['genuine'] else reference / d['density']))
                for c, d in cd.items() if d['tested'])
