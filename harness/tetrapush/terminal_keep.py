"""THE TERMINAL AS A KEEP, NOT A RANK -- the three windows a last roll must satisfy AT ONCE.

Sessions 134-142 bred 49 herd rungs by ranking endpoints on `handoff.probe`'s ``resid``, and session
144 measured what that produced: of the 49, **4** satisfy ``tetra_from_corner``, **0** satisfy
``along``, **0** aim inside the seam's own facing window, and **none** satisfies more than one. That
is not bad luck. Ranking a roll on a residual whose facing is 11+ deg outside the window is ranking a
quantity that CANNOT reach zero, and a rank on one criterion breeds a population satisfying one
criterion. So the terminal belongs on the KEEP side of the cut, all three axes together, with the
residual demoted to what it can honestly do -- ordering the survivors.

WHAT THE THREE WINDOWS ARE, AND WHERE EACH COMES FROM (no literal is restated here):

  * the FACING -- `seam_window`, off `fixtures/courtyard_facing_window_s92.json`: which console
    sine-table CELLS admit genuine dust at the seam at all. Two lobes with a dead gap between them.
  * the BOX -- ``along`` / ``runway`` / ``tetra_from_corner``, off `terminal.clipping_family`'s
    banked scan of the terminal, narrowed to the ``unbroken`` family (Link touching her at the roll
    entry, contact never breaking) because that is the zero-walk-away shape session 123 re-aimed the
    problem at.

THE BOX IS A NEIGHBOURHOOD PROXY AND SAYS SO. `clipping_family` refuses to answer for an unmeasured
(facing, thrust, lean) precisely so a neighbour's number is never quoted as a measurement, and the
scan exists at ONE facing inside the seam window (40835). The box here is that facing's, applied
across the window's live cells as a cheap pre-filter, and `TerminalKeep.exact` says whether the
probed facing is the scanned one. Nothing rests on the proxy: it decides only which aims are worth
compiling a `ShoveCtx` for, and the answer for a kept aim is `handoff.probe` at the roll's OWN
facing, lean and momentum -- exact, and the thing the razor is then bisected on.

THE BOX IS ALSO GRID-COARSE, AND A SCREEN TIGHTER THAN ITS OWN RESOLUTION REFUSES ITS GENERATING SET.
`terminal.RUNWAY`/`ALONG` step 10 u and 5 u, so ``un_along`` = 60..100 is the extent of the SAMPLED
hits: the family provably contains those points and its true edge is somewhere inside the next cell.
Screening on the bare extent is not merely conservative, it is WRONG -- projecting a banked hit's own
world pair back through the f32 sin/cos basis lands it ~3e-5 u below its integer coordinate, so three
of the eight unbroken hits fail a keep built from those same eight (`[[search-space-contains-human]]`:
a search whose range does not intrinsically contain the known-good reference is broken; gate it).
So the screen window is the sampled extent widened by HALF a scan cell each side -- the resolution the
extent is known to, nothing more -- and `test_the_keep_contains_every_hit_it_was_built_from` holds it
there. ``pad`` adds WHOLE further cells on top for a caller that wants the benefit of the doubt; it
defaults to 0, and `windows` reports ``sampled`` beside the screen window so the two never blur.

    python -m harness.tetrapush.terminal_keep [thrust] [lean]
"""
import json
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
from harness.tetrapush import handoff as HO
from harness.tetrapush import razor_depth as RD
from harness.tetrapush import terminal as TM
import tww_sim.core.mathlib as ML

#: The seam's measured facing window -- which cells admit genuine dust (`entry_search.curve_scan`).
SEAM_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_facing_window_s92.json')
_SEAM = None

#: The terminal the delivered state pins (session 144): the only thrust with an unbroken-contact
#: family at the delivered body lean. Both are read back off the family record, never assumed.
DEFAULT_THRUST = 14
#: The body lean every one of the 49 banked rungs delivers at its roll entry -- one distinct value.
DELIVERED_LEAN = 648


def seam_window():
    """**Which roll facings the seam admits at all**, as measured cells -- the first keep.

    Returns ``dict(cells, lobes, dead_gap, scanned, window, cell_bam)``. ``cells`` is the set of
    scanned cells with at least one live station; ``window`` is their facing extent.

    Read ``scanned`` before treating ``window`` as a boundary: the scan covers cells 2548..2575 and
    the top two are LIVE, so the window's upper end is where the sweep stopped and not where the seam
    closes. Its lower end is a real edge only in the sense that nothing below it was asked. Neither
    matters for the herd, whose delivered facings sit 11-78 deg BELOW the whole thing -- but a claim
    that a facing is unreachable must not lean on an unmeasured edge (`[[infeasible-needs-proof]]`)."""
    global _SEAM
    if _SEAM is None:
        with open(SEAM_FIXTURE) as fh:
            d = json.load(fh)
        cells = frozenset(r['cell'] for r in d['rows'] if r['live'])
        fac = sorted(r['facing'] for r in d['rows'] if r['live'])
        _SEAM = dict(cells=cells, lobes=tuple(tuple(l) for l in d['lobes']),
                     dead_gap=tuple(d['dead_gap']), scanned=tuple(d['scanned']),
                     window=(min(fac) & ~(d['cell_bam'] - 1),
                             (max(fac) & ~(d['cell_bam'] - 1)) + d['cell_bam'] - 1),
                     cell_bam=int(d['cell_bam']))
    return _SEAM


def in_seam_window(facing):
    """Is this roll facing inside a LIVE seam cell? The keep the 49 banked rungs all fail.

    Cell-quantized on purpose: `entry_search.aim_cell` is the alphabet's real atom (the console sine
    table has 4096 entries and no interpolation), so two facings in one cell bake a bit-identical
    schedule and are one draw."""
    return ES.aim_cell(facing) in seam_window()['cells']


class TerminalKeep:
    """The three-way keep for ONE banked terminal, plus the exact residual for what survives it.

    ``unbroken`` narrows the box to the zero-walk-away family, which is the default and the shape;
    ``unbroken=False`` reads the whole genuine extent instead (a wider box that includes rolls which
    lose contact mid-roll and pick it back up).

    Raises if the terminal was never scanned. That is `terminal.clipping_family`'s contract kept
    rather than softened: a keep built on a neighbour's box would report a population it never
    measured."""

    def __init__(self, facing=ES.TAB_FACING, thrust=DEFAULT_THRUST, lean=DELIVERED_LEAN,
                 unbroken=True, pad=0):
        rec = TM.clipping_family(facing, thrust, lean)
        if rec is None:
            raise ValueError("terminal (facing %d, thrust %d, lean %d) was never scanned -- "
                             "%s holds no record for it" % (facing, thrust, lean, TM.FAMILY_FIXTURE))
        n = 'un_' if unbroken else ''
        if not rec['unbroken' if unbroken else 'genuine']:
            raise ValueError("terminal (facing %d, thrust %d, lean %d) has %d roots and no %s "
                             "family -- there is no box to keep on"
                             % (facing, thrust, lean, rec['roots'],
                                'unbroken' if unbroken else 'genuine'))
        # the scan's own resolution: ``tetra_from_corner`` = runway - along, so it is only resolved
        # to the gcd of the two steps, never to the finer of them
        d_al, d_rw = TM.ALONG[1] - TM.ALONG[0], TM.RUNWAY[1] - TM.RUNWAY[0]
        d_tfc = math.gcd(d_al, d_rw)
        p = int(pad)
        self.rec, self.unbroken, self.pad = rec, bool(unbroken), p
        self.thrust, self.lean = int(rec['thrust']), int(rec['lean'])
        self.box_facing = int(rec['facing'])
        self.cut_step, self.roll_frames = int(rec['cut_step']), int(rec['roll_frames'])
        self.step = dict(along=d_al, runway=d_rw, tetra_from_corner=d_tfc)
        self.sampled = dict(along=tuple(rec[n + 'along']), runway=tuple(rec[n + 'runway']),
                            tetra_from_corner=tuple(rec[n + 'tetra_from_corner']))
        self.along = self._widen(self.sampled['along'], d_al, p)
        self.runway = self._widen(self.sampled['runway'], d_rw, p)
        self.tfc = self._widen(self.sampled['tetra_from_corner'], d_tfc, p)
        self.lat = tuple(rec['un_lat']) if unbroken else None
        self.brace = RD.brace_point(35.0, 35.0)
        self._pool = ES.CtxPool()

    @staticmethod
    def _widen(sampled, step, pad):
        """A grid-sampled extent as a screen window: half a cell each side, plus ``pad`` whole ones.

        Half a cell is the resolution the extent is KNOWN to and not a tolerance -- the scan proves
        the family holds the sampled points and says nothing about the interior of the next cell."""
        return (sampled[0] - (0.5 + pad) * step, sampled[1] + (0.5 + pad) * step)

    # ------------------------------------------------------------------ the cheap half
    def coords(self, facing, link, tetra):
        """``(runway, side, along, lat)`` at the ROLL's own facing -- `handoff.PairFrame.coords`
        without the `ShoveCtx`, so a fan can be screened without compiling anything."""
        f = int(facing) & 0xFFFF
        m = (ML.cM_ssin_s16(f), ML.cM_scos_s16(f))
        q = (-m[1], m[0])
        dx, dz = link[0] - self.brace[0], link[1] - self.brace[1]
        tx, tz = tetra[0] - link[0], tetra[1] - link[1]
        return (-(dx * m[0] + dz * m[1]), dx * q[0] + dz * q[1],
                tx * m[0] + tz * m[1], tx * q[0] + tz * q[1])

    def screen(self, entry):
        """The keep on one roll ENTRY (`two_roll.roll_segment`'s ``entry``): ``dict(ok, why, ...)``.

        ``why`` names the FIRST axis that refused, so a stalled sweep reads as a diagnosis rather
        than a count -- ``t_facing`` / ``t_along`` / ``t_runway`` / ``t_tfc``. The order is by cost
        and by how hard each is to buy: the facing is one integer compare and is the axis nothing in
        the banked population comes near, so it goes first."""
        f = int(entry['facing']) & 0xFFFF
        rw, sd, al, la = self.coords(f, entry['link'], entry['tetra'])
        out = dict(ok=False, why=None, facing=f, cell=ES.aim_cell(f), runway=rw, side=sd,
                   along=al, lat=la, tetra_from_corner=rw - al,
                   exact=(f == self.box_facing), dist=math.hypot(*[a - b for a, b in
                                                                  zip(entry['tetra'],
                                                                      entry['link'])]))
        if not in_seam_window(f):
            return dict(out, why='t_facing')
        if not (self.along[0] <= al <= self.along[1]):
            return dict(out, why='t_along')
        if not (self.runway[0] <= rw <= self.runway[1]):
            return dict(out, why='t_runway')
        if not (self.tfc[0] <= out['tetra_from_corner'] <= self.tfc[1]):
            return dict(out, why='t_tfc')
        return dict(out, ok=True)

    # ------------------------------------------------------------------ the exact half
    def frame(self, facing, lean, nspeed):
        """A `handoff.PairFrame`-shaped view on the POOLED ctx at the roll's own configuration.

        `entry_search.CtxPool` keeps one compiled courtyard per (facing, thrust) and re-schedules it
        per (lean, momentum) -- 0.13 ms against `handoff.PairFrame`'s 17 ms, which is the difference
        between ranking a fan and not. The ctx is SHARED, so a caller must finish one configuration's
        sweeps before asking for the next (`CtxPool.get`)."""
        return _PooledPair(self._pool, facing, self.thrust, lean, nspeed)

    def probe(self, entry):
        """`handoff.probe` at the roll's OWN facing / lean / momentum -- the exact answer.

        This is what a kept aim is ranked on and what a razor solve then bisects. It is never a
        neighbour's box and never the scan grid: the coordinates come back from the compiled frame."""
        pf = self.frame(entry['facing'], entry['lean'], entry['nspeed'])
        return HO.probe(pf, entry['link'], entry['tetra'])

    def score(self, entry):
        """`screen` and, for what it keeps, `probe` -- merged, with ``resid``/``genuine`` present
        only when the screen passed. One call per aim is the whole per-aim cost of the terminal."""
        s = self.screen(entry)
        if not s['ok']:
            return s
        p = self.probe(entry)
        return dict(s, resid=p['resid'], genuine=bool(p['genuine']), overlap=p['overlap'],
                    push=p['push'], brace_dist=p['brace_dist'])

    def windows(self):
        """The keep as data, for a gate or a report to assert on instead of on prose."""
        return dict(facing=seam_window()['window'], cells=sorted(seam_window()['cells']),
                    along=self.along, runway=self.runway, tetra_from_corner=self.tfc,
                    lat=self.lat, thrust=self.thrust, lean=self.lean, box_facing=self.box_facing,
                    unbroken=self.unbroken, pad=self.pad, cut_step=self.cut_step,
                    roll_frames=self.roll_frames, sampled=dict(self.sampled),
                    step=dict(self.step))


class _PooledPair(HO.PairFrame):
    """`PairFrame` on a shared `entry_search.CtxPool` ctx rather than a freshly compiled one."""

    def __init__(self, pool, facing, thrust, lean, nspeed):
        self.ctx, self.sch, self.resid = pool.get(facing, lean, thrust, nspeed=nspeed)
        f = int(facing) & 0xFFFF
        self.m = (ML.cM_ssin_s16(f), ML.cM_scos_s16(f))
        self.q = (-self.m[1], self.m[0])
        self.brace = RD.brace_point(35.0, 35.0)
        self.off = RD.co_centre_offsets(self.sch)
        self.cut_step = self.sch['cut_step']
        self.facing, self.thrust, self.lean = f, int(thrust), int(lean) & 0xFFFF
        self.nspeed = ES.ROLL_NSPEED if nspeed is None else float(nspeed)
        self.fr = self


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    import warnings
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    thrust = int(argv[0]) if argv else DEFAULT_THRUST
    lean = int(argv[1]) if len(argv) > 1 else DELIVERED_LEAN
    sw = seam_window()
    print("seam facing window %d..%d BAM, cells %d..%d scanned, %d live, lobes %s, dead gap %s"
          % (sw['window'][0], sw['window'][1], sw['scanned'][0], sw['scanned'][1],
             len(sw['cells']), sw['lobes'], sw['dead_gap']))
    k = TerminalKeep(thrust=thrust, lean=lean)
    w = k.windows()
    print("terminal thrust %d lean %d (box from facing %d, %s): cut_step %d, %d roll frames"
          % (w['thrust'], w['lean'], w['box_facing'],
             'unbroken' if w['unbroken'] else 'genuine', w['cut_step'], w['roll_frames']))
    for a in ('along', 'runway', 'tetra_from_corner', 'lat'):
        print("  %-18s %s" % (a, "%.4f .. %.4f" % w[a] if w[a] else '--'))


if __name__ == '__main__':
    main()
