"""**THE RAZOR IS A POSITIVE RESIDUAL INTERVAL, AND IT DOES NOT CONTAIN ZERO** (s158).

Every instrument in this work aims at ``resid = 0``: the sweep reports ``best_resid_in_contact`` as its
closest approach, `entry_search.zero_the_resid` / `locus_scan` / `configuration_band` march the residual's
zero, `entry_dust` measures density along it, `cut_contact.target_ring` bisects for it, and s157's ``gap``
prices a herd as the radial distance to it. Measured at full fidelity, **no clip is there**.

At a fixed configuration, sweeping HER WALK-END POSITION over her own plane and reading ``genuine`` off
the native sim:

  * the genuine placements occupy a NARROW POSITIVE interval of ``resid`` that EXCLUDES zero -- the
    console's own clip [+5.796e-05, +9.918e-05], s154's accepted 101 [+1.628e-04, +1.967e-04];
  * inside that interval ``resid`` is **SUFFICIENT**: every row whose residual lands in it is genuine
    (510/510, 301/301, and in every one of the 20+ configurations `band_depends` measured);
  * the interval is a property of the (cell, thrust) CONFIGURATION -- unmoved by the lean over +-8 and
    by the entry over ~0.05 u, and not a seam constant: cell 2545 sits 3x further from zero than
    cell 2552, and cell 2551 lands at [+1.66e-05, +4.42e-05].

That is why s155's "every near-razor row is refused by the barrier" and s156's "one f32 ULP either side
is ``wall_hit``" look like fine structure and are not: a row at ``|resid| = 3e-06`` is not NEAR the
razor, it is a few residual-quanta short of it, on the side where the cut ray passes the wrong side of
the seam vertex and aims through the wall. The barren sweep drove its rows to zero, which is the one
place a clip cannot be.

**HER POSITION REACHES THE RESIDUAL THROUGH A QUANTIZED CHANNEL.** Over a 160801-placement scan her plane
returns only ~1900-4700 DISTINCT residual values (86 placements each), and the genuine ones take 4 and 7
distinct values respectively -- so a band is a handful of reachable rungs, not a continuum, and a search
that lands between two rungs cannot be nudged onto one by moving her a ULP.

**HONEST LIMITS.** ``sufficient`` is MEASURED per call and returned, never assumed -- check it before
using `in_band` as a verdict. ``genuine == 0`` means "no genuine placement in THIS window", which is a
statement about the window (move the entry 0.2 u and the same scan returns nothing while the band is
unchanged), so quote ``tested`` with it. And the band is read at ONE entry: it is stable over the ~0.05 u
neighbourhood measured and is not claimed beyond it.
"""
import math
import struct

from harness.tetrapush import entry_search as ES

#: Her plane, scanned around a reference placement. Sized by measurement, not taste: this returns the
#: same interval as a scan 2.5x wider and one 2x finer, at ~0.5 s (`_notes/s158_band_depends.py`).
SCAN_HALF = 0.02
SCAN_STEP = 2.5e-4

#: `terminal.CO_R_SUM` -- Link's Co radius plus hers, the cyl-cyl contact distance. Stated as the two
#: radii so this module carries no import cycle, the same way `cut_contact` does it.
CO_R_SUM = ES.LINK_CO_R + ES.TETRA_CO_R


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def band_rows(ctx, resid, entry, tetra, *, half=SCAN_HALF, step=SCAN_STEP):
    """``(genuine, resid, overlap)`` for a square of HER walk-end placements around ``tetra``.

    Full fidelity -- ``placed_step = 0``, so her plow runs and ``old`` is the row's own. This is the
    difference from `cut_contact.cut_slice`, which pins ``old`` at the brace and is therefore ~1e-02 off
    a real row's residual: 300 band-widths, enough that the slice reports ``genuine = False`` on the very
    placement that delivered."""
    n = int(2.0 * half / step) + 1
    pts = [(tetra[0] - half + i * step, tetra[1] - half + j * step)
           for i in range(n) for j in range(n)]
    rows = ctx.sweep_par([(p[0], p[1], entry[0], entry[1]) for p in pts], 0, extra=True)
    return [(bool(o[0]), resid(o), CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13]))
            for o in rows]


def genuine_band(facing, lean, thrust, entry, tetra, *, half=SCAN_HALF, step=SCAN_STEP,
                 nspeed=None, ctx=None, sch=None, resid=None):
    """**THE INTERVAL OF ``resid`` ON WHICH THIS CONFIGURATION CLIPS.**

    Scans her plane, keeps the genuine placements, and reports the interval they span together with the
    check that makes it usable: whether EVERY row inside the interval is genuine (``sufficient``). A
    caller that skips that check is asserting the thing this function exists to measure.

    Returns ``dict(lo, hi, width, values, genuine, tested, sufficient, overlap, contains_zero,
    entry, tetra)``; ``lo``/``hi``/``width`` are ``None`` when the window holds no genuine placement --
    which is a statement about the WINDOW, so ``tested`` comes back either way."""
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
    rows = band_rows(ctx, resid, entry, tetra, half=half, step=step)
    g = [r for r in rows if r[0]]
    out = dict(tested=len(rows), genuine=len(g), entry=[entry[0], entry[1]],
               tetra=[tetra[0], tetra[1]], lo=None, hi=None, width=None, values=0,
               sufficient=None, overlap=None, contains_zero=None)
    if not g:
        return out
    vals = sorted({r[1] for r in g})
    lo, hi = vals[0], vals[-1]
    inband = sum(1 for r in rows if lo <= r[1] <= hi)
    out.update(lo=lo, hi=hi, width=hi - lo, values=len(vals),
               sufficient=bool(inband == len(g)), contains_zero=bool(lo <= 0.0 <= hi),
               overlap=[min(r[2] for r in g), max(r[2] for r in g)])
    return out


def in_band(band, resid_value):
    """Is this row's residual inside the measured interval? ``False`` when the band is empty.

    Only a verdict where ``band['sufficient']`` is True -- otherwise it is a necessary condition."""
    return bool(band.get('lo') is not None and band['lo'] <= resid_value <= band['hi'])


def band_distance(band, resid_value):
    """**HOW FAR A ROW IS FROM CLIPPING, in the residual's own units** -- signed, 0 inside the band.

    Negative means the row is SHORT of the band (the side the whole barren sweep optimised toward, since
    that is the side ``resid = 0`` is on); positive means past it. This replaces ``|resid|`` as the
    ranking key: the sweep's own best rows scored 3e-06 by that measure and were a full band-width and
    more from any clip."""
    if band.get('lo') is None:
        return None
    if resid_value < band['lo']:
        return resid_value - band['lo']
    if resid_value > band['hi']:
        return resid_value - band['hi']
    return 0.0


def zero_is_outside(band):
    """The headline, as a predicate: does this configuration refuse ``resid = 0``?

    True for every configuration measured so far, which is why every zero-seeking tool in this work
    aims a few residual quanta short of the target."""
    return bool(band.get('lo') is not None and not band['contains_zero'])
