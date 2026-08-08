"""THE CHAIN BACK -- a herd state read in the terminal frame, and what a herd must hand over.

Session 124 solved the terminal configuration: which (Link, Tetra) pair at the roll entry clips. It
did that in the shape where Link WALKS to a chosen spot, so it pinned Link's entry to the brace line
(``entry = brace - runway*m``) and swept where SHE sits. A herd does not choose Link's spot -- it
arrives wherever the last cycle leaves him, off that line in general -- so chaining backwards needs
the coordinate with Link's own lateral offset kept:

    entry = brace - runway*m + side*q            Link at the END of the roll-entry frame
    tetra = entry  + along*m + lat*q             where the herd left HER

``side`` is the axis `terminal.RollFrame` pins to zero, and `pair_coords` is the inverse map, so any
delivered (Link, Tetra) reads as a terminal cell with no world coordinates in the caller.

WHAT A HERD HANDS OVER IS A TETRA, NOT A CELL. The herd parks her; Link is then the only thing still
free. At a FIXED Tetra the two lateral coordinates collapse into one --

    along = (tetra - brace)*m + runway            lat = (tetra - brace)*q - side

-- so moving Link sideways by ``side`` moves the razor coordinate ``lat`` by exactly ``-side``, and
the genuine set at that Tetra is a CURVE of entry points, one solved ``side`` per ``runway``
(`entry_locus`). That curve is the honest statement of what a herd must deliver, in world
coordinates, and `node_gap` measures how far a real herd endpoint sits from it.

METHOD is session 124's and deliberately unchanged -- bracket the residual's SIGN CHANGE on a coarse
grid, bisect every bracket in lockstep, then walk the f32 band -- because the acceptance is ~1e-5..
1.5e-4 u wide and no affordable grid resolves it. The only thing that moves is which actor's lateral
axis carries it: hers in `terminal`, LINK'S here, since Link is what a herd still steers.

    python -m harness.tetrapush.handoff locus [facing] [thrust]
"""
import math
import os
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import entry_search as ES
from harness.tetrapush import terminal as TM

#: The ``side`` bracketing scan. 100x finer than `terminal.LAT_STEP`: the contact corridor is ~1 u
#: wide, so half-unit brackets straddle it whole (`the-razor-is-on-the-pusher-not-the-pushed.md`).
SIDE_SPAN = 70.0
SIDE_STEP = 0.005
#: The f32 band walk on LINK's axis -- 10x `terminal.BAND_HALF`, the acceptance being wider in ``side``.
BAND_HALF = 1.2e-3
BAND_STEP = TM.BAND_STEP

#: The runway rungs `entry_locus` solves on. Outside 190..310 the s124 scan is empty at every along:
#: shorter and the roll reaches the corner before the cut, longer and it never gets there.
RUNWAYS = tuple(range(190, 321, 10))


class PairFrame:
    """One compiled (facing, thrust, lean) read in the 4-coordinate handoff frame.

    Wraps `terminal.RollFrame` -- same `ShoveCtx`, same schedule, same residual -- and adds Link's
    own lateral offset. `at_side` hands back a `RollFrame`-shaped view so `terminal`'s bracket /
    bisect / band methods run on it unchanged."""

    def __init__(self, facing=ES.TAB_FACING, thrust=14, lean=0):
        self.fr = TM.RollFrame(facing, thrust, lean)
        for a in ('m', 'q', 'brace', 'off', 'cut_step', 'facing', 'thrust', 'lean', 'ctx', 'sch',
                  'resid'):
            setattr(self, a, getattr(self.fr, a))

    def item(self, runway, side, along, lat):
        """``(tetra_x, tetra_z, entry_x, entry_z)`` -- one `ShoveCtx.sweep_par` sample."""
        ex = self.brace[0] - runway * self.m[0] + side * self.q[0]
        ez = self.brace[1] - runway * self.m[1] + side * self.q[1]
        return (ex + along * self.m[0] + lat * self.q[0],
                ez + along * self.m[1] + lat * self.q[1], ex, ez)

    def rows(self, specs):
        """``(genuine, resid, overlap, |push|, brace_dist)`` per ``(runway, side, along, lat)``, in
        ONE batch sweep -- the engine is parallel and per-sample calls throw all of it away."""
        return self.sweep([self.item(*s) for s in specs])

    def sweep(self, items):
        """The same, on RAW ``(tetra_x, tetra_z, entry_x, entry_z)`` world samples.

        This is the primitive, and the one anything razor-scale must use. ``m``/``q`` come from the
        console's f32 sin/cos tables, so the basis is orthonormal only to ~1e-7 -- projecting a world
        pair into ``(runway, side, along, lat)`` and building it back costs ~2e-5 u at these radii,
        which is the width of the acceptance itself. Hold the positions, never the coordinates."""
        out = self.ctx.sweep_par(list(items), 0, extra=True)
        return [(bool(o[0]), self.resid(o),
                 TM.CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13]),
                 math.hypot(o[5], o[6]),
                 math.hypot(o[1] - self.brace[0], o[2] - self.brace[1])) for o in out]

    def entry_at(self, runway, side=0.0):
        """Link's entry ``(x, z)`` for a rung of the approach line, offset ``side`` sideways."""
        return (self.brace[0] - runway * self.m[0] + side * self.q[0],
                self.brace[1] - runway * self.m[1] + side * self.q[1])

    def slide(self, entry, side):
        """``entry`` moved ``side`` u along the roll's perpendicular -- the herd's own razor knob."""
        return (entry[0] + side * self.q[0], entry[1] + side * self.q[1])

    def at_side(self, side):
        """A `terminal.RollFrame`-shaped view at fixed ``side`` (``0.0`` IS the `RollFrame`)."""
        return _SideView(self, float(side))

    def coords(self, link, tetra):
        """``(runway, side, along, lat)`` for a real pair of world XZ positions -- `item`'s inverse."""
        m, q, br = self.m, self.q, self.brace
        dx, dz = link[0] - br[0], link[1] - br[1]
        tx, tz = tetra[0] - link[0], tetra[1] - link[1]
        return (-(dx * m[0] + dz * m[1]), dx * q[0] + dz * q[1],
                tx * m[0] + tz * m[1], tx * q[0] + tz * q[1])

    def world(self, runway, side, along, lat):
        """``(link, tetra)`` world XZ -- `coords`' inverse, in the caller's units."""
        tx, tz, ex, ez = self.item(runway, side, along, lat)
        return (ex, ez), (tx, tz)


class _SideView:
    """`PairFrame` at a fixed ``side``, duck-typed as `terminal.RollFrame`."""

    def __init__(self, pf, side):
        self.pf, self.side = pf, side
        for a in ('m', 'q', 'brace', 'off', 'cut_step', 'facing', 'thrust', 'lean', 'ctx', 'sch',
                  'resid'):
            setattr(self, a, getattr(pf, a))

    def item(self, runway, along, lat):
        return self.pf.item(runway, self.side, along, lat)

    def rows(self, specs):
        return self.pf.rows([(r, self.side, a, l) for r, a, l in specs])

    def overlaps(self, runway, along, lat):
        tx0, tz0, ex, ez = self.item(runway, along, lat)
        res, steps = self.ctx.run_trace(tx0, tz0, 0, link_x0=ex, link_z0=ez)
        out = []
        for k, (lx, lz, tx, tz) in enumerate(steps):
            cx, cz = ((lx + self.off[k][0], lz + self.off[k][1])
                      if self.sch['is_pose'][k] else (lx, lz))
            out.append(TM.CO_R_SUM - math.hypot(cx - tx, cz - tz))
        return res, steps, out


def probe(pf, link, tetra):
    """Does a roll fired from THIS pair clip? The terminal predicate, on a delivered state.

    Sweeps the DELIVERED positions and reports the coordinates alongside -- never the other way round
    (`PairFrame.sweep`'s note: the trip through the basis costs more than the acceptance). Carries
    ``resid``, the SIGNED miss `solve_razor` bisects, so a search can bracket on it and not merely
    test it."""
    rw, sd, al, la = pf.coords(link, tetra)
    g, resid, overlap, push, brace_dist = pf.sweep([(tetra[0], tetra[1], link[0], link[1])])[0]
    return dict(runway=rw, side=sd, along=al, lat=la, genuine=g, resid=resid, overlap=overlap,
                push=push, brace_dist=brace_dist, facing=pf.facing, thrust=pf.thrust, lean=pf.lean)


def _items(pf, tetra, entry, sides):
    return [(tetra[0], tetra[1]) + pf.slide(entry, s) for s in sides]


def tetra_lateral(pf, tetra):
    """Her own lateral offset from the brace line, ``l0`` -- the CENTRE every ``side`` scan takes.

    Scanning ``side`` about zero is scanning about the brace line, and that is the wrong place: Link
    only touches her at the cut inside a corridor a couple of units wide, and that corridor sits at
    ``side ~ l0`` (she is what he has to pass). A herd parks her 60-70 u off the line routinely, so a
    brace-centred span reports NO CONTACT AT ALL and reads as infeasible (`[[infeasible-needs-proof]]`
    -- this cost session 125 a wrong answer before the span was re-centred)."""
    q, br = pf.q, pf.brace
    return (tetra[0] - br[0]) * q[0] + (tetra[1] - br[1]) * q[1]


def side_crossings(pf, tetra, entry, span=SIDE_SPAN, step=SIDE_STEP):
    """Every sign change of the razor residual along LINK's lateral axis, as ``(lo, hi)`` brackets,
    at a fixed Tetra and a fixed approach rung. One batch sweep, centred on her (`tetra_lateral`)."""
    c = tetra_lateral(pf, tetra)
    n = int(2 * span / step) + 1
    sides = [c - span + step * i for i in range(n)]
    rs = pf.sweep(_items(pf, tetra, entry, sides))
    out, prev = [], None
    for i, r in enumerate(rs):
        if prev is not None and (prev < 0.0) != (r[1] < 0.0):
            out.append((sides[i - 1], sides[i]))
        prev = r[1]
    return out


def solve_sides(pf, tetra, brackets, iters=TM.BISECT_ITERS):
    """Bisect every ``(entry, lo, hi)`` bracket IN LOCKSTEP -- one batch sweep per round, as
    `terminal.solve_razor` does on her axis."""
    if not brackets:
        return []
    lo = [b[1] for b in brackets]
    hi = [b[2] for b in brackets]
    flo = [r[1] for r in pf.sweep([(tetra[0], tetra[1]) + pf.slide(b[0], b[1]) for b in brackets])]
    for _ in range(iters):
        mid = [0.5 * (a + b) for a, b in zip(lo, hi)]
        fm = [r[1] for r in pf.sweep([(tetra[0], tetra[1]) + pf.slide(b[0], s)
                                      for b, s in zip(brackets, mid)])]
        for i, v in enumerate(fm):
            if (v < 0.0) == (flo[i] < 0.0):
                lo[i], flo[i] = mid[i], v
            else:
                hi[i] = mid[i]
    return [0.5 * (a + b) for a, b in zip(lo, hi)]


def side_band(pf, tetra, entry, side, half=BAND_HALF, step=BAND_STEP):
    """Walk the solved razor in f32-scale steps along LINK's lateral axis; the genuine band or None.

    ``clipped`` says the band reached the edge of the walk, so ``width`` is a LOWER BOUND."""
    n = int(2 * half / step) + 1
    xs = [side - half + step * i for i in range(n)]
    rs = pf.sweep(_items(pf, tetra, entry, xs))
    idx = [i for i, r in enumerate(rs) if r[0]]
    if not idx:
        return None
    mid = idx[len(idx) // 2]
    e = pf.slide(entry, xs[mid])
    rw, sd, al, la = pf.coords(e, tetra)
    return dict(runway=rw, side=xs[mid], side_lo=xs[idx[0]], side_hi=xs[idx[-1]], n=len(idx),
                width=xs[idx[-1]] - xs[idx[0]], clipped=(idx[0] == 0 or idx[-1] == n - 1),
                along=al, lat=la, resid=rs[mid][1], overlap=rs[mid][2], push=rs[mid][3],
                brace_dist=rs[mid][4], entry=[e[0], e[1]], tetra=[tetra[0], tetra[1]],
                tetra_from_corner=rw - al, facing=pf.facing, thrust=pf.thrust, lean=pf.lean)


def entry_locus(pf, tetra, runways=RUNWAYS, span=SIDE_SPAN, step=SIDE_STEP):
    """**What a herd must hand over, at the Tetra it parked** -- the genuine Link ENTRY positions for
    a FIXED Tetra, one solved ``side`` per ``runway``, in world XZ."""
    br = []
    for rw in runways:
        e = pf.entry_at(rw)
        br += [(e, lo, hi) for lo, hi in side_crossings(pf, tetra, e, span, step)]
    out = []
    for spec, side in zip(br, solve_sides(pf, tetra, br)):
        b = side_band(pf, tetra, spec[0], side)
        if b is not None:
            out.append(b)
    return out


def node_gap(pf, link, tetra, **kw):
    """How far a real herd endpoint sits from the genuine entry curve at its OWN Tetra.

    ``gap`` is the world distance from Link to the nearest genuine entry -- the units a junction has
    to close -- split into ``d_runway`` (along the approach, which a longer slide buys cheaply) and
    ``d_side`` (the razor axis)."""
    loc = entry_locus(pf, tetra, **kw)
    rw, sd, al, la = pf.coords(link, tetra)
    if not loc:
        return dict(n=0, gap=float('inf'), runway=rw, side=sd, along=al, lat=la, locus=[])
    best = min(loc, key=lambda b: math.hypot(b['entry'][0] - link[0], b['entry'][1] - link[1]))
    return dict(n=len(loc), gap=math.hypot(best['entry'][0] - link[0], best['entry'][1] - link[1]),
                d_runway=best['runway'] - rw, d_side=best['side'] - sd, runway=rw, side=sd,
                along=al, lat=la, best=best, locus=loc)


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    import warnings
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'locus'
    if cmd != 'locus':
        raise SystemExit(__doc__)
    facing = int(argv[0]) if argv else ES.TAB_FACING
    thrust = int(argv[1]) if len(argv) > 1 else 14
    pf = PairFrame(facing, thrust)
    tet = pf.world(230.0, 0.0, 50.0, 0.573628)[1]
    print("entry locus at tetra (%.4f, %.4f), facing %d thrust %d" % (tet[0], tet[1], facing, thrust))
    for b in entry_locus(pf, tet):
        print("  runway %3d  side %+9.5f  lat %+9.5f  entry (%.5f, %.5f)  width %.2e%s"
              % (b['runway'], b['side'], b['lat'], b['entry'][0], b['entry'][1], b['width'],
                 '  CLIPPED' if b['clipped'] else ''))


if __name__ == '__main__':
    main()
