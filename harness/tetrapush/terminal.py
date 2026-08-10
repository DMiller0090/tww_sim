"""THE TERMINAL CONFIGURATION in the ZERO-WALK-AWAY shape -- the herd's LAST ROLL *is* the clip roll.

Dereck re-aimed the problem at the end of session 123: Link never leaves her, so there is no escape
walk, no walk-back and no separate roll-entry search. That deletes the whole endgame the module spent
sessions 102-123 pricing and leaves ONE condition on ONE frame -- at the cut, is she still touching him
and is that touch steering the lunge through the seam. This module answers it.

WHAT A HERD HANDS OVER, AND SO WHAT THIS PARAMETRISES. The old search swept Tetra at a FIXED recorded
roll entry (`_generated/tetra_placements.tsv`) or entries at a FIXED Tetra (`entry_search`); both are
slices of the same surface taken in the shape where Link walks to a chosen spot. A herd hands over a
PAIR, so the pair is the coordinate -- expressed in the roll's own frame (``m`` the roll direction,
``q`` its perp, ``brace`` = `razor_depth.brace_point(35, 35)`, the corner-most point CrrPos parks
Link on):

    entry  = brace - runway * m                    Link at the END of the roll-entry frame
    tetra  = entry + along * m + lat * q            where the previous roll left HER

``runway`` is what a longer-than-normal untarget brakeslide buys (Dereck, session 124: "you may need
to EBS into her for longer than normal before doing the final roll") -- the backslide opens the gap
the roll then closes. ``along`` is the herd's own handoff distance, measured live at 41-85 u. ``lat``
is the razor.

WHY ``lat`` IS THE RAZOR AND THE OTHER TWO ARE NOT. At a grazing configuration the gradients are

    d(resid)/d(lat)     -4.00 /u          d(overlap)/d(lat)      -15.32 /u
    d(resid)/d(runway)  +0.17 /u          d(overlap)/d(runway)    +0.64 /u

-- sliding the pair up and down the approach barely moves the answer; how squarely he passes her moves
it hard. That is mechanism, not a fitting choice. The cut ray is bent onto the seam vertex by the CC
push, the push is half the cut-frame overlap, and there is exactly ONE overlap that bends it exactly
onto S. So ``lat`` is SOLVED per cell (scan for the sign change, bisect, walk the f32 band), never
gridded: the acceptance is ~1e-5..1.5e-4 u wide and a 5e-4 u sweep reads a clean cell as empty.

WHAT THE MEASUREMENT FOUND (session 124, the delivered facing/thrust, `scan`):

  * **51 genuine terminal configurations**, ``along`` 50-245 u and ``runway`` 190-310 u -- **13 of them
    with Link ALREADY TOUCHING HER at the roll entry and contact never breaking for the whole roll**,
    at handoff distances 50-110 u. The zero-walk-away best case EXISTS.
  * **THE CORNER WASHES THE HANDOFF OUT -- the last two frames are an ATTRACTOR.** Once Link is braced
    and she has been plowed against him, the pair converges: over handoffs 50-245 u apart and 10-180 u
    from the corner, the final three overlaps read 18.3/18.4/13.7 -> 6.76/6.75/6.70 -> **1.132/1.132/
    1.127**, her cut-frame position lands inside a **0.054 x 0.205 u** box, Link's braced point is
    constant to 0.001 u, and the cut lands inside 0.003 u. So the cut-frame overlap is a property of
    THE CORNER, not of the handoff and not of how far the roll plowed her (which varies 53-126 u).
    **The razor therefore asks the herd for ALIGNMENT and never for depth** -- which is what closes the
    open unknown the s123 handoff left ("a herd roll's depth is whatever the plow produces"). It also
    says the herd does not have to place her: the last roll parks her.
  * **The body lean is not a bar.** Every lean -191..+191 admits terminal configurations (most of them
    in-contact ones). `entry_search`'s "m351C 64 already does not clip" is a statement about a FIXED
    entry -- the lean moves `resid` ~1.1e-2, a hundred window widths -- and re-solving ``lat`` recovers
    it. It also decays 35%/frame (`LandState.SLANT_DECAY`), so the same long backslide that buys the
    runway flattens the lean to 0 in 13 frames.

A THRUST THAT DISPATCHES THE CUT IS NOT A THRUST THAT CLIPS (session 144). `entry_search.
cut_step_window` says which steps a roll can press B into at all; it says nothing about whether the
resulting cut reaches the seam, and the two are different questions with different answers. Scanned
over this same box at the DELIVERED lean, thrust 13 bisects **2390 razor roots and converts none of
them**, while thrust 14 converts 40 of 2513 and thrust 15 converts 107 of 2613. So the cheapest
DISPATCHABLE clip roll (17 frames) is not a deliverable one and the floor is thrust 14's 18. That is
banked rather than restated -- `fixtures/courtyard_terminal_family.json`, read through
`clipping_thrusts` / `clipping_family`, which return None at an UNMEASURED terminal rather than a
neighbour's answer.

    python -m harness.tetrapush.terminal scan [facing] [thrust] [lean]
    python -m harness.tetrapush.terminal leans [facing] [thrust]
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
from harness.tetrapush import razor_depth as RD
import tww_sim.core.mathlib as ML

#: Bisection depth for the razor. The acceptance is f32 dust ~1e-5..1.5e-4 u wide and the residual
#: gradient is ~4 /u, so a bracket must close far past the window before the band walk starts.
BISECT_ITERS = 62

#: The f32 band walk around a solved razor: half-width and step. `BAND_HALF` is deliberately wider
#: than any band measured so far (1.47e-4) -- a band that saturates it is reported CLIPPED, not wide.
BAND_HALF = 1.2e-4
BAND_STEP = 3e-7

#: The lateral scan that brackets the razor, and its step. 0.5 u is fine enough that the residual
#: (gradient ~4 /u) cannot change sign twice inside one interval at any cell measured.
LAT_SPAN = 70.0
LAT_STEP = 0.5

#: The handoff box `scan` sweeps. ``along`` reaches past the tabulated clip's own 215.0 u so the sweep
#: provably CONTAINS it (`[[search-space-contains-human]]`; gated by `test_the_scan_box_contains_*`).
RUNWAY = tuple(range(140, 481, 10))
ALONG = tuple(range(30, 246, 5))

#: The Co radius sum -- overlap is `CO_R_SUM - |co_centre - tetra|` on the frame the cut consumes.
CO_R_SUM = RD.CO_R_SUM

#: The banked family: which (facing, thrust, lean) terminals were SCANNED and what they hold. Read it
#: through `clipping_family`, never as a literal -- see that function for why the fallback is None.
FAMILY_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_terminal_family.json')
_FAMILY = None


def clipping_family(facing, thrust, lean):
    """**The banked terminal family at one (facing, thrust, lean)** -- or ``None`` if never scanned.

    `entry_search.thrust_window` answers a different question than this one. It says which ``cut_step``
    a roll can DISPATCH a cut on, which is a property of the roll's animation and nothing else; whether
    that cut then reaches the seam is a property of the corner, and the two do not agree. Measured over
    the whole `RUNWAY` x `ALONG` x ``lat`` box at the delivered lean, thrust 13 bisects **2390 razor
    roots and converts 0**, thrust 14 converts **40 of 2513**, thrust 15 **107 of 2613**. Session 143
    priced the 17-frame thrust-13 roll as the cheapest deliverable one on the strength of the dispatch
    window alone; the cheapest one that CLIPS is thrust 14's 18.

    Every record carries ``roots`` beside ``genuine`` on purpose. A bare zero cannot tell absent
    geometry from under-sampling, and this module has answered that question wrong before
    (`[[infeasible-needs-proof]]`) -- 2390 roots converting none is a statement about the cut, where
    2390 roots that were never bisected would be a statement about the scan.

    An UNMEASURED terminal returns ``None`` and the caller says so, exactly as `handoff.crossing_bar`
    does: reaching for a neighbouring thrust's family is how a thrust-14 number ended up printed beside
    thrust-11 screens for two sessions."""
    global _FAMILY
    if _FAMILY is None:
        with open(FAMILY_FIXTURE) as fh:
            d = json.load(fh)
        _FAMILY = {(r['facing'], r['thrust'], r['lean']): r for r in d['records']}
    return _FAMILY.get((int(facing) & 0xFFFF, int(thrust), int(lean) & 0xFFFF))


def clipping_thrusts(facing, lean, unbroken=False):
    """The thrusts that actually CLIP at this terminal, ascending -- ``None`` if none were scanned.

    ``unbroken=True`` narrows it to the zero-walk-away family (Link touching her at the roll entry and
    contact never breaking), which is the shape session 123 re-aimed the problem at. At the delivered
    lean that narrowing leaves **thrust 14 alone**: 15 scans 107 genuine and 0 unbroken."""
    got = [r for r in (clipping_family(facing, t, lean) for t in ES.THRUSTS) if r is not None]
    if not got:
        return None
    return tuple(sorted(r['thrust'] for r in got
                        if (r['unbroken'] if unbroken else r['genuine'])))


class RollFrame:
    """One compiled (facing, thrust, lean, nspeed) in the roll's own brace-anchored frame.

    Holds the `ShoveCtx` -- the coupled roll from Link's entry through the CUT entry step, with the
    plow, her follow AI and both actors' CrrPos -- so a configuration reads the same at every facing
    and the caller never touches world coordinates.

    ``nspeed`` is the roll's MOMENTUM and it defaults to `entry_search.ROLL_NSPEED` (26.0, the walk
    cap's roll). A roll a herd already fires carries whatever `_roll_init` clamped from its own
    pre-roll speedF, and reading a razor at the wrong momentum is reading a different schedule: it
    scales `dx`/`dz` and nothing else (`fast_schedule`), so a sub-cap roll is a DIFFERENT locus and
    not a worse one. Session 143 carried this as a `_notes` subclass; it belongs on the frame."""

    def __init__(self, facing=ES.TAB_FACING, thrust=14, lean=0, nspeed=None):
        self.ctx, self.sch, self.resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
        f = int(facing) & 0xFFFF
        self.m = (ML.cM_ssin_s16(f), ML.cM_scos_s16(f))
        self.q = (-self.m[1], self.m[0])
        self.brace = RD.brace_point(35.0, 35.0)
        self.off = RD.co_centre_offsets(self.sch)
        self.cut_step = self.sch['cut_step']
        self.facing, self.thrust, self.lean = f, int(thrust), int(lean) & 0xFFFF
        self.nspeed = ES.ROLL_NSPEED if nspeed is None else float(nspeed)

    def item(self, runway, along, lat):
        """``(tetra_x, tetra_z, entry_x, entry_z)`` -- one `ShoveCtx.sweep_par` sample."""
        ex = self.brace[0] - runway * self.m[0]
        ez = self.brace[1] - runway * self.m[1]
        return (ex + along * self.m[0] + lat * self.q[0],
                ez + along * self.m[1] + lat * self.q[1], ex, ez)

    def rows(self, specs):
        """``(genuine, resid, overlap, |push|, brace_dist)`` per ``(runway, along, lat)``.

        ``overlap`` is read off the CONTACT PAIR the engine records on ``cut_step - 1`` (the frame
        whose push the cut consumes), and ``brace_dist`` off `old` -- so a caller can tell "he never
        reached the corner" apart from "he reached it with nothing touching him"."""
        out = self.ctx.sweep_par([self.item(*s) for s in specs], 0, extra=True)
        return [(bool(o[0]), self.resid(o),
                 CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13]),
                 math.hypot(o[5], o[6]),
                 math.hypot(o[1] - self.brace[0], o[2] - self.brace[1])) for o in out]

    def overlaps(self, runway, along, lat):
        """The per-frame Co overlap through the whole roll -- the diagnosis a bare verdict cannot give.

        Positive every frame means Link never separates from her (the zero-walk-away family); the frame
        it first goes negative is where the roll left her behind."""
        tx0, tz0, ex, ez = self.item(runway, along, lat)
        res, steps = self.ctx.run_trace(tx0, tz0, 0, link_x0=ex, link_z0=ez)
        out = []
        for k, (lx, lz, tx, tz) in enumerate(steps):
            cx, cz = ((lx + self.off[k][0], lz + self.off[k][1])
                      if self.sch['is_pose'][k] else (lx, lz))
            out.append(CO_R_SUM - math.hypot(cx - tx, cz - tz))
        return res, steps, out


def razor_crossings(fr, runway, along, span=LAT_SPAN, step=LAT_STEP):
    """Every sign change of the razor residual along the lateral axis, as ``(lo, hi)`` brackets.

    Scanning for the SIGN CHANGE rather than for a small |resid| is the whole reason a cell is not
    missed: the acceptance is four orders of magnitude finer than any affordable grid, so the grid's
    job is only to bracket."""
    n = int(2 * span / step) + 1
    lats = [-span + step * i for i in range(n)]
    rs = fr.rows([(runway, along, x) for x in lats])
    out, prev = [], None
    for i, r in enumerate(rs):
        if prev is not None and (prev < 0.0) != (r[1] < 0.0):
            out.append((lats[i - 1], lats[i]))
        prev = r[1]
    return out


def solve_razor(fr, brackets, iters=BISECT_ITERS):
    """Bisect every ``(runway, along, lo, hi)`` bracket IN LOCKSTEP -- one sweep per round.

    The engine is a parallel batch sweep, so bisecting candidates one at a time throws away all of it:
    2500 razors cost 62 sweeps this way and 155000 the obvious way."""
    if not brackets:
        return []
    lo = [b[2] for b in brackets]
    hi = [b[3] for b in brackets]
    flo = [r[1] for r in fr.rows([(b[0], b[1], b[2]) for b in brackets])]
    for _ in range(iters):
        mid = [0.5 * (a + b) for a, b in zip(lo, hi)]
        fm = [r[1] for r in fr.rows([(b[0], b[1], m) for b, m in zip(brackets, mid)])]
        for i, v in enumerate(fm):
            if (v < 0.0) == (flo[i] < 0.0):
                lo[i], flo[i] = mid[i], v
            else:
                hi[i] = mid[i]
    return [0.5 * (a + b) for a, b in zip(lo, hi)]


def genuine_band(fr, runway, along, lat, half=BAND_HALF, step=BAND_STEP):
    """Walk the solved razor in f32-scale steps; return the genuine band or None.

    ``clipped`` says the band reached the edge of the walk, so ``width`` is a LOWER BOUND -- the
    distinction a deliverability claim needs and a bare number hides."""
    n = int(2 * half / step) + 1
    xs = [lat - half + step * i for i in range(n)]
    rs = fr.rows([(runway, along, x) for x in xs])
    idx = [i for i, r in enumerate(rs) if r[0]]
    if not idx:
        return None
    mid = idx[len(idx) // 2]
    return dict(lat=xs[mid], lat_lo=xs[idx[0]], lat_hi=xs[idx[-1]], n=len(idx),
                width=xs[idx[-1]] - xs[idx[0]], clipped=(idx[0] == 0 or idx[-1] == n - 1),
                resid=rs[mid][1], overlap=rs[mid][2], push=rs[mid][3], brace_dist=rs[mid][4])


def solve_cell(fr, runway, along):
    """Every genuine razor at one handoff cell (a cell can hold more than one crossing)."""
    br = [(runway, along, lo, hi) for lo, hi in razor_crossings(fr, runway, along)]
    out = []
    for spec, lat in zip(br, solve_razor(fr, br)):
        b = genuine_band(fr, runway, along, lat)
        if b is not None:
            b.update(runway=runway, along=along, tetra_from_corner=runway - along,
                     facing=fr.facing, thrust=fr.thrust, lean=fr.lean)
            e = fr.item(runway, along, b['lat'])
            b['entry'] = [e[2], e[3]]
            b['tetra'] = [e[0], e[1]]
            out.append(b)
    return out


def classify(fr, hit):
    """Add the shape facts a plan is chosen on: does he start TOUCHING her, does contact ever break,
    and how far the roll plows her. ``unbroken`` is the zero-walk-away family's defining property."""
    res, steps, ov = fr.overlaps(hit['runway'], hit['along'], hit['lat'])
    k = fr.cut_step
    tx0, tz0, _ex, _ez = fr.item(hit['runway'], hit['along'], hit['lat'])
    out = dict(hit, genuine_confirmed=bool(res['genuine']), overlap_entry=ov[0],
               unbroken=min(ov[:k]) > 0.0, break_frames=sum(1 for v in ov[:k] if v <= 0.0),
               plowed=math.hypot(steps[k - 1][2] - tx0, steps[k - 1][3] - tz0),
               tetra_at_cut=[steps[k - 1][2], steps[k - 1][3]], new=[res['new'][0], res['new'][1]])
    return out


def scan(facing=ES.TAB_FACING, thrust=14, lean=0, runways=RUNWAY, alongs=ALONG, progress=False):
    """The whole handoff box -> every genuine terminal configuration, classified."""
    fr = RollFrame(facing, thrust, lean)
    t0 = time.time()
    br = []
    for runway in runways:
        for along in alongs:
            br += [(runway, along, lo, hi) for lo, hi in razor_crossings(fr, runway, along)]
    if progress:
        print("  %d razor crossings over %d cells  [%.0f s]"
              % (len(br), len(runways) * len(alongs), time.time() - t0), flush=True)
    hits = []
    for spec, lat in zip(br, solve_razor(fr, br)):
        b = genuine_band(fr, spec[0], spec[1], lat)
        if b is None:
            continue
        b.update(runway=spec[0], along=spec[1], tetra_from_corner=spec[0] - spec[1],
                 facing=fr.facing, thrust=fr.thrust, lean=fr.lean)
        e = fr.item(spec[0], spec[1], b['lat'])
        b['entry'] = [e[2], e[3]]
        b['tetra'] = [e[0], e[1]]
        hits.append(classify(fr, b))
    if progress:
        print("  %d GENUINE (%d touching at entry, contact unbroken)  [%.0f s]"
              % (len(hits), sum(1 for h in hits if h['unbroken']), time.time() - t0), flush=True)
    return hits, time.time() - t0


# --------------------------------------------------------------------------- CLI

def _cmd_scan(argv):
    facing = int(argv[0]) if argv else ES.TAB_FACING
    thrust = int(argv[1]) if len(argv) > 1 else 14
    lean = int(argv[2]) if len(argv) > 2 else 0
    print("terminal scan: facing %d thrust %d lean %d" % (facing, thrust, lean), flush=True)
    hits, secs = scan(facing, thrust, lean, progress=True)
    out = os.path.join(_rb, '_generated', 's124', 'terminal_%d_%d_%d.json'
                       % (facing, thrust, lean & 0xFFFF))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(source='harness.tetrapush.terminal.scan', facing=facing, thrust=thrust,
                   lean=lean, seconds=secs, hits=hits), open(out, 'w'), indent=1)
    inc = [h for h in hits if h['unbroken']]
    if hits:
        ov = sorted(h['overlap'] for h in hits)
        print("  overlap at the cut %.4f..%.4f u (the corner's, not the handoff's)" % (ov[0], ov[-1]))
    if inc:
        al = sorted(h['along'] for h in inc)
        print("  IN CONTACT the whole roll: %d, he starts %d..%d u behind her" % (len(inc), al[0], al[-1]))
    print("wrote %s  [%.0f s]" % (out, secs))


def _cmd_leans(argv):
    facing = int(argv[0]) if argv else ES.TAB_FACING
    thrust = int(argv[1]) if len(argv) > 1 else 14
    runways = tuple(range(180, 341, 20))
    alongs = tuple(range(40, 126, 5))
    print("lean    genuine   in-contact   he starts behind her")
    for sl in (0, -8, -24, -64, -125, -191, 8, 24, 64, 125, 191):
        hits, _s = scan(facing, thrust, sl & 0xFFFF, runways, alongs)
        inc = [h for h in hits if h['unbroken']]
        al = sorted(h['along'] for h in hits)
        print("%+5d  %8d   %10d   %s" % (sl, len(hits), len(inc),
                                         "%d..%d u" % (al[0], al[-1]) if al else "--"))


def main(argv=None):
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'scan'
    if cmd == 'scan':
        _cmd_scan(argv)
    elif cmd == 'leans':
        _cmd_leans(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
