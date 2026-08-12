"""**THE RAZOR'S TARGET IN u OF LINK'S ENTRY** -- `razor_band.band_distance`, divided by the gradient it
was missing (s160).

s158 measured that ``genuine`` is exactly ``resid`` inside a narrow positive band and left the ranking key
in the residual's own units, which s159 called "a quantity no planner can steer" and replaced with
`admit_map.nearest_admitting_entry` -- a ring of ~1 s screens around a candidate's entry. Both readings
are missing one number. Measured at both delivered configurations (`_notes/s160_entryaxis.py`):

  * ``|d resid / d ENTRY|`` is **0.31 and 0.51 per u** -- the SAME order as ``|d resid / d HER|`` (0.35
    and 0.26). The entry is not a weak axis on the razor; it is a peer of hers.
  * the band is **SUFFICIENT ALONG THE ENTRY AXIS TOO**: sweeping the entry over +-0.02 u at her pinned
    placement, 875 of 160801 rows have ``resid`` inside the band measured on HER plane and **exactly
    those 875 are the genuine ones** -- no row inside the band fails, and no genuine row sits outside it
    (642 of 160801, same agreement, at s154's). So ``resid in band`` is the whole predicate on both axes.

Divide one by the other and the razor's target becomes a **STRIP IN THE ENTRY PLANE ~1.2e-04 u wide**
(band width / gradient) along a level curve of the residual -- and "how far is this plan from clipping"
becomes a signed distance IN u THAT LINK'S ENTRY MUST MOVE, at the cost of one sweep row and one
2-point gradient. `offset_u` is that number, `aim` walks it to zero, and `walk_end_for` converts the
answer back into the walk endpoint a plan has to reach.

**WHY THAT IS THE PLANNER'S OBJECTIVE, and not another ranking.** A whole 98618-candidate fan at walk 4
shares ONE Tetra position -- span 0.000000 u, measured in `_notes/s160_keys.py`, because the walk never
touches her -- so per item the razor has exactly one free variable and it is where Link enters. The
screen's question ("does this configuration clip for ANY position of hers") is the loose form of that;
this is the exact one, at the position the item actually has.

**THE TWO AXES ARE NOT SYMMETRIC, and it took a failing gate to find out.** `admit_map.resid_grad` uses
``mag == 0`` as its diagnostic that HER position has left Co range -- past that the razor stops depending
on her and there is no descent direction. **Nothing like that happens on the entry axis**: measured at
565 u of displacement the gradient is still 0.99 per u, because ``resid`` is the CUT RAY's offset from the
seam vertex and Link's entry always moves the ray. So the ``mag <= 0`` guards below are defensive, not a
contact test -- ask ``price``'s own ``in_contact`` (the Co overlap) for that.

**THE BAND DRIFTS WITH THE ENTRY, slowly, and a caller must not re-use one far from where it was read.**
`aim` walks 0.70 u off the console's delivered entry and lands on a row the sim calls GENUINE at
``resid = +1.0157e-04``, which is 7% ABOVE the band measured at the delivered entry
([+5.7958e-05, +9.4723e-05]). s158 measured the band as unmoved over ~0.05 u of entry and that is where
it holds; over 0.07 u it has already moved by a fraction of its own width. Hence the discipline
throughout: the residual PRICES a row, and only the sim's ``genuine`` flag VERDICTS one.

**HONEST LIMITS.** ``offset_u`` is a LINEARISATION: it is the exact first-order distance and the residual
is quantized (~4e-06), so a row it prices at 1e-05 u may still need `aim` -- which re-evaluates the sim
per step and ends on ``genuine`` off the sweep, never on the linearisation. And a band must come with its
``sufficient`` flag checked: `band_for` returns `razor_band.genuine_band`'s own dict, and nothing here
infers ``genuine`` from ``in_band``.

usage:
    python -m harness.tetrapush.entry_aim gate                 # rediscover both known clips by AIMING
    python -m harness.tetrapush.entry_aim price <facing> <lean> <thrust> <ex> <ez> <tx> <tz>
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

from harness.tetrapush import admit_map as AM
from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_band as RB
from tww_sim.core import mathlib as ML
from tww_sim.core.fp import fadds, fmuls

#: The gradient's FD step, in u of entry -- `entry_search.entry_gradient`'s own, and it must stay well
#: above the residual's ~4e-06 quantum or both probes land on one rung and read a gradient of 0.
ENTRY_H = 1.0e-3

#: `aim`'s stopping rule. The arbiter is the sim's own ``genuine`` flag, so this only has to get inside
#: the band -- a fifth of its width, the same reasoning as `admit_map.CORRECT_TOL`.
AIM_FRAC = 0.2


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', float(v)))[0]


def entry_grad(ctx, resid, tetra, entry, *, h=ENTRY_H):
    """``(gx, gz, mag, resid, row)`` of the razor residual w.r.t. LINK'S ENTRY, in one batched sweep.

    The mirror of `admit_map.resid_grad`, which takes it w.r.t. HER start -- but ``mag`` does NOT mean
    there what it means here. Her gradient dies the moment she leaves Co range; this one does not die at
    all (0.99 per u at 565 u of displacement, gated), because the entry moves the cut ray whether or not
    she is in reach. A zero here is a degenerate row, not a contact verdict."""
    pts = [(entry[0] + h, entry[1]), (entry[0] - h, entry[1]),
           (entry[0], entry[1] + h), (entry[0], entry[1] - h), entry]
    o = ctx.sweep_par([(tetra[0], tetra[1], p[0], p[1]) for p in pts], 0, extra=True)
    r = [resid(x) for x in o]
    gx, gz = (r[0] - r[1]) / (2.0 * h), (r[2] - r[3]) / (2.0 * h)
    return gx, gz, math.hypot(gx, gz), r[4], o[4]


def band_for(facing, lean, thrust, entry, tetra, *, ctx=None, sch=None, resid=None, **kw):
    """The genuine residual band at this configuration -- `razor_band.genuine_band`, unchanged.

    Kept as a named indirection because a band is what makes every number in this module meaningful and
    a caller must be able to see WHICH instrument produced it: this one sweeps HER plane at a reference
    row (0.5-2.5 s and it returns ``sufficient``), while `admit_map.screen` returns a band read off the
    zero curve's own ladders (~0.05-2 s) for a configuration with no in-contact row to reference."""
    return RB.genuine_band(facing, int(lean) & 0xFFFF, thrust, entry, tetra, ctx=ctx, sch=sch,
                           resid=resid, **kw)


def offset_u(band, resid_value, mag):
    """**HOW FAR LINK'S ENTRY MUST MOVE, IN u, FOR THIS ROW TO CLIP.** Signed; 0.0 inside the band.

    ``band_distance / |d resid / d entry|``. The sign is the residual's: negative is SHORT of the band
    (the side ``resid = 0`` is on, which is the side the whole barren sweep optimised toward), positive
    is past it. None when the band is empty or the gradient is dead, because both are statements and
    neither is a distance."""
    d = RB.band_distance(band, resid_value)
    if d is None or not mag:
        return None
    return d / mag


def price(facing, lean, thrust, entry, tetra, *, band=None, ctx=None, sch=None, resid=None,
          nspeed=None):
    """**WHAT A CANDIDATE ROW IS WORTH**: its residual, its band, its distance to clipping in u, and the
    sim's own verdict.

    ``genuine`` is the sweep's flag, never inferred from ``in_band`` -- that implication is what the band
    MEASURES (``sufficient``), so a function that assumed it could not report when it failed."""
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, int(lean) & 0xFFFF, thrust, nspeed=nspeed)
    gx, gz, mag, r, row = entry_grad(ctx, resid, tetra, entry)
    if band is None:
        band = band_for(facing, lean, thrust, entry, tetra, ctx=ctx, sch=sch, resid=resid)
    return dict(entry=[entry[0], entry[1]], tetra=[tetra[0], tetra[1]], resid=r,
                genuine=bool(row[0]), grad=[gx, gz], mag=mag,
                band=[band.get('lo'), band.get('hi')], band_sufficient=band.get('sufficient'),
                band_distance=RB.band_distance(band, r), offset_u=offset_u(band, r, mag),
                strip_u=(None if not mag or band.get('width') is None else band['width'] / mag),
                in_contact=bool(mag > 0.0), cell=ES.aim_cell(facing), thrust=int(thrust),
                lean=int(lean) & 0xFFFF)


def aim(facing, lean, thrust, entry, tetra, *, band=None, ctx=None, sch=None, resid=None,
        nspeed=None, iters=12, log=None):
    """**MOVE THE ENTRY ONTO THE BAND** -- a Newton in the entry plane, ending on ``genuine`` off the sim.

    This is what makes `offset_u` a plan and not a score: from a row that is 0.5 u short, it returns the
    entry coordinates that clip, at full f32 precision (`[[full-fp-precision-coords]]` -- rounding one of
    these to three decimals is 4000 strip-widths).

    Returns ``dict(entry, resid, genuine, steps, offset_u, moved, ok, reason)``. ``ok`` is the sim's
    ``genuine``, so a converged residual that does not actually clip comes back False with the row that
    proves it -- the same discipline `admit_map.her_seeds` uses to drop a bracket that bisected to a
    discontinuity rather than a zero."""
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, int(lean) & 0xFFFF, thrust, nspeed=nspeed)
    if band is None:
        band = band_for(facing, lean, thrust, entry, tetra, ctx=ctx, sch=sch, resid=resid)
    if band.get('lo') is None:
        return dict(entry=[entry[0], entry[1]], ok=False, reason='no_band', steps=0, genuine=False,
                    resid=None, offset_u=None, moved=0.0)
    target = 0.5 * (band['lo'] + band['hi'])
    tol = AIM_FRAC * max(band['width'], 0.0)
    p, e0, best = (float(entry[0]), float(entry[1])), (float(entry[0]), float(entry[1])), None
    for k in range(int(iters)):
        gx, gz, mag, r, row = entry_grad(ctx, resid, tetra, p)
        if mag <= 0.0:
            return dict(entry=[p[0], p[1]], ok=False, reason='no_gradient', steps=k + 1,
                        genuine=bool(row[0]), resid=r, offset_u=None,
                        moved=math.hypot(p[0] - e0[0], p[1] - e0[1]))
        if best is None or abs(r - target) < abs(best[1] - target):
            best = (p, r, bool(row[0]))
        if log:
            log('  step %2d: entry %.9f %.9f  resid %+.6e  offset %+0.6f u  genuine %s'
                % (k, p[0], p[1], r, (r - target) / mag, bool(row[0])))
        if row[0]:
            return dict(entry=[p[0], p[1]], ok=True, reason='', steps=k + 1, genuine=True, resid=r,
                        offset_u=offset_u(band, r, mag),
                        moved=math.hypot(p[0] - e0[0], p[1] - e0[1]))
        if abs(r - target) <= tol:
            # inside the band by the residual and still not genuine: walk ALONG the level curve, since
            # the strip is 1.2e-04 u wide and tens of u long and the miss is transverse to nothing
            t = (-gz / mag, gx / mag)
            q = (p[0] + tol / mag * t[0], p[1] + tol / mag * t[1])
        else:
            step = (target - r) / (mag * mag)
            q = (p[0] + step * gx, p[1] + step * gz)
        if _bits(q[0]) == _bits(p[0]) and _bits(q[1]) == _bits(p[1]):
            break
        p = q
    gx, gz, mag, r, row = entry_grad(ctx, resid, tetra, best[0])
    return dict(entry=[best[0][0], best[0][1]], ok=bool(row[0]), reason='' if row[0] else 'no_clip',
                steps=int(iters), genuine=bool(row[0]), resid=r, offset_u=offset_u(band, r, mag),
                moved=math.hypot(best[0][0] - e0[0], best[0][1] - e0[1]))


def walk_end_for(entry, facing, nspeed=None):
    """**THE WALK ENDPOINT A PLAN HAS TO REACH** to enter the roll at ``entry`` -- `roll_entry` inverted.

    The forward step is f32 (`entry_search.roll_entry`: ``fadds(p, fmuls(nspeed, sin/cos))``), so the
    inverse is exact only up to a rounding; the arbiter is a forward re-evaluation, and ``error`` is it.
    A caller steering a walk cares about the endpoint in u and this is 1 ULP of 1600, but the razor's
    strip is 1.2e-04 u wide -- the same order -- so the error is REPORTED rather than assumed away."""
    facing = int(facing) & 0xFFFF
    v = ES.ROLL_NSPEED if nspeed is None else nspeed
    w = (fadds(entry[0], -fmuls(v, ML.cM_ssin_s16(facing))),
         fadds(entry[1], -fmuls(v, ML.cM_scos_s16(facing))))
    back = ES.roll_entry(w, facing, v)
    return dict(walk_end=[w[0], w[1]], entry=[entry[0], entry[1]], round_trip=[back[0], back[1]],
                error=math.hypot(back[0] - entry[0], back[1] - entry[1]),
                exact=bool(_bits(back[0]) == _bits(entry[0]) and _bits(back[1]) == _bits(entry[1])))


# --------------------------------------------------------------------------------- the CLI + the gate

def gate(verbose=True, displace=0.5):
    """**THE TOOL HAS TO FIND A CLIP FROM A STATE WHERE ONE EXISTS** (`[[search-must-rediscover-known-
    answer]]`).

    Two checks per delivered configuration, at its own pinned Tetra:

      1. its DELIVERED entry prices at ``offset_u == 0`` and ``genuine`` True -- the control;
      2. displaced ``displace`` u off that entry, `aim` walks back onto a GENUINE entry -- and the entry
         it returns is a clip the sim confirms, not a converged residual.

    The displacement is 4000 strip-widths, so passing is a statement about the aim and not about the
    starting point being nearly right already."""
    out = {}
    for cfg in (AM.CONSOLE, AM.ACCEPTED):
        ctx, sch, resid = ES.build_fast(cfg['facing'], cfg['lean'] & 0xFFFF, cfg['thrust'])
        band = band_for(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'],
                        ctx=ctx, sch=sch, resid=resid)
        own = price(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'],
                    band=band, ctx=ctx, sch=sch, resid=resid)
        off = (cfg['entry'][0] + displace, cfg['entry'][1] - displace)
        got = aim(cfg['facing'], cfg['lean'], cfg['thrust'], off, cfg['tetra'], band=band, ctx=ctx,
                  sch=sch, resid=resid)
        out[cfg['tag']] = dict(own=own, aimed=got, band=band)
        if verbose:
            print('%-20s cell %4d thrust %2d: delivered row genuine %s offset %s u, strip %.3e u; '
                  'band [%+.4e, %+.4e] sufficient %s'
                  % (cfg['tag'], own['cell'], own['thrust'], own['genuine'],
                     '%+0.6f' % own['offset_u'] if own['offset_u'] is not None else 'none',
                     own['strip_u'], band['lo'], band['hi'], band['sufficient']))
            print('%-20s aimed from %+0.2f u away: genuine %s in %d steps, moved %.6f u, '
                  'entry (%.9f, %.9f)'
                  % ('', displace * math.sqrt(2.0), got['genuine'], got['steps'], got['moved'],
                     got['entry'][0], got['entry'][1]))
    return out


def main(argv):
    cmd = argv[0] if argv else 'gate'
    if cmd == 'gate':
        g = gate()
        ok = all(v['own']['genuine'] and v['own']['offset_u'] == 0.0 and v['aimed']['ok']
                 for v in g.values())
        print('ENTRY-AIM GATE: %s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1
    if cmd == 'price':
        f, ln, t = int(argv[1]), int(argv[2]), int(argv[3])
        e = (float(argv[4]), float(argv[5]))
        tet = (float(argv[6]), float(argv[7]))
        print(json.dumps(price(f, ln, t, e, tet), indent=1, default=float))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
