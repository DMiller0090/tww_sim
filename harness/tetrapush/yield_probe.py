"""**THE PER-ITEM YIELD PROBE** -- which of an item's draws can produce a genuine plan at all,
measured in ~1 minute against the ~7 h the item costs to run (s163's measured price).

WHY THIS EXISTS (s163/s164). The s163 closed-loop rediscovery produced **8 genuine where the
razor-side arithmetic predicted hundreds** (`knowledge/model/fan-containment-gap.md`). The s164
decomposition of that run's own funnel says the area arithmetic is not the liar: the in-band row
count comes out at the predicted order (~200 rows from the near-row density), and the collapse to 8
is the ACCEPTANCE -- all 256 recorded near rows, one of them |resid| 3.7e-07, are refused
``blocked`` (the swept lunge path hits the wall), and the 8 genuine sit in 2 of the item's 135
(cell, thrust) draws. So an item's yield is set by **which draws have an admitting section of the
entry-plane strip within the fan's reach**, and that is answerable per draw without running any fan:
walk the strip, ask the sweep's own genuine flag station by station.

THE LOCATE HAS TO CLASSIFY REGIMES. The entry-plane ``resid = 0`` set is not one curve: measured at
the console item it has components in a **gentle ~0.3/u regime (the strip; genuine lives here)** and
components at **~650/u that are quantization-oscillating discontinuities and are never genuine**
(the same lesson as `razor-zero-curve.md`'s her-plane cliffs, now on the entry axis; the residual's
lateral profile swings +-50 within 2 u around them). A Newton seeded blind converges to the nearest
zero of EITHER kind, which is why `strip_seeds` scans lateral profiles at several depths across the
contact window and keeps only GENTLE zero-brackets (both endpoints under `GENTLE`), and why
`draw_admittance` refuses to walk from any point whose gradient reads over `CLIFF_MAG`.

WHAT A VERDICT MEANS. ``n_admit > 0`` is ground truth (every station is the sim's own genuine flag
at the item's own frozen Tetra). **A zero is a screen, not a proof**: the probe samples a handful of
leans around the herd's own (`LEAN_SPREAD`), `N_DEPTH` depth slices, and `N_ST` stations an arc --
a component that crosses no sampled slice, or admits only at an unsampled lean, is invisible
(`[[probe-below-the-quantum]]`'s cousin: report what was TESTED). Rank the queue by it; never
declare an item dead by it.

VALIDATION (its own rediscovery gate, run s164): at s163's console-w04 -- the one item with a known
answer -- the probe's top two draws by admitting stations are **exactly the two that produced all
8 genuine plans** ((2551,15) x20 stations and (2552,15) x18, both 5 in reach), s154's (2545,15) also
shows, and 129 of 135 draws read zero. Banked in
`fixtures/courtyard_yield_probe_console_w04.json`; gated in `tests/test_yield_probe.py`.

usage:
    python -m harness.tetrapush.yield_probe item <id> [incumbent=N]   # one item's draw table
    python -m harness.tetrapush.yield_probe queue [head=N] [walk_min=5] [incumbent=N]
"""
import json
import math
import os
import sys
import time

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import aimed_fan as AF
from harness.tetrapush import entry_aim as EA
from harness.tetrapush import entry_search as ES
from tww_sim.core import mathlib as ML

#: Transect residual span: 3x past any measured band (~4e-05 wide, within ~1.1e-04 of zero),
#: stepped at half a band width so no band inside the span can be stepped over.
RESID_LO, RESID_HI, RESID_STEP = -3.0e-4, 4.0e-4, 2.0e-5

#: 1 u stations do not step over an admitting run (runs are 3-13 stations at that spacing --
#: `razor-zero-curve.md`); N_ST stations each way.
ARC, N_ST = 1.0, 20

#: Regime split (`admitting-draws.md`): the strip reads 0.3-0.5/u, the never-genuine discontinuity
#: components ~650/u. GENTLE bounds a bracket endpoint; CLIFF_MAG refuses a walk from a steep point.
GENTLE = 8.0
CLIFF_MAG = 50.0

#: The locate's SAMPLING grid (depth slices x lateral profiles over the contact window):
#: a miss at this grid is "not found", never "not there".
N_DEPTH = 6
LAT_HALF, LAT_STEP = 15.0, 0.5
DEPTH_MIN, DEPTH_MAX, DEPTH_STEP = 60.0, 236.0, 4.0

#: Leans probed per draw: the herd's own roll lean +- this, covering the fan's measured ~510 BAM
#: walk-lean span with margin. A SAMPLING knob, not a truth constant.
LEAN_SPREAD = 384


def strip_seeds(ctx, resid, fac, tetra):
    """Gentle zero-brackets of the residual over (depth x lateral) slices of the entry plane.

    Depth runs along the approach ray (entry = tetra - D*dir(fac)); the contact window is where the
    residual VARIES along it (outside it the cut is braced and the value is a dead constant --
    `braced-cut-frame.md`). A bracket whose endpoints both read under `GENTLE` is a strip crossing;
    anything steeper is one of the never-genuine discontinuity components and is dropped."""
    fac = int(fac) & 0xFFFF
    dx, dz = ML.cM_ssin_s16(fac), ML.cM_scos_s16(fac)
    lx, lz = -dz, dx
    nD = int((DEPTH_MAX - DEPTH_MIN) / DEPTH_STEP) + 1
    Ds = [DEPTH_MIN + DEPTH_STEP * i for i in range(nD)]
    pts = [(tetra[0] - D * dx, tetra[1] - D * dz) for D in Ds]
    rows = ctx.sweep_par([(tetra[0], tetra[1], p[0], p[1]) for p in pts], 0, extra=True)
    rs = [resid(o) for o in rows]
    vary = [i for i in range(len(rs) - 1) if rs[i] != rs[i + 1]]
    if not vary:
        return []
    lo, hi = Ds[vary[0]], Ds[min(vary[-1] + 1, len(Ds) - 1)]
    depths = [lo + (hi - lo) * k / (N_DEPTH - 1.0) for k in range(N_DEPTH)]
    lats = [-LAT_HALF + LAT_STEP * i for i in range(int(2 * LAT_HALF / LAT_STEP) + 1)]
    seeds = []
    for D in depths:
        base = (tetra[0] - D * dx, tetra[1] - D * dz)
        ep = [(base[0] + l * lx, base[1] + l * lz) for l in lats]
        out = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1]) for e in ep], 0, extra=True)
        rr = [resid(o) for o in out]
        for i in range(len(rr) - 1):
            a, b = rr[i], rr[i + 1]
            if a == b:
                continue
            if (a <= 0.0 <= b or b <= 0.0 <= a) and max(abs(a), abs(b)) < GENTLE:
                t = abs(a) / (abs(a) + abs(b))
                seeds.append((ep[i][0] + t * (ep[i + 1][0] - ep[i][0]),
                              ep[i][1] + t * (ep[i + 1][1] - ep[i][1])))
    return seeds


def gentle_brackets(lats, resids, gentle=GENTLE):
    """The bracket classifier alone, on one lateral profile -- pure, for the gate.

    Returns the (i, i+1) index pairs whose residuals change sign with BOTH endpoints under
    ``gentle``: strip crossings, with the cliff crossings (+-50 swings) rejected."""
    out = []
    for i in range(len(resids) - 1):
        a, b = resids[i], resids[i + 1]
        if a == b:
            continue
        if (a <= 0.0 <= b or b <= 0.0 <= a) and max(abs(a), abs(b)) < gentle:
            out.append((i, i + 1))
    return out


def draw_admittance(fac, lean, thrust, tetra):
    """``dict(n_admit, entries, ends, reason)`` for ONE (facing, lean, thrust) draw at the item's
    own frozen Tetra: the sim-genuine stations found along every gentle strip component located.

    Every returned entry is ground truth (the sweep's own genuine flag). Zero is a screen -- see the
    module docstring for what the sampling can miss."""
    ctx, sch, resid = ES.build_fast(int(fac) & 0xFFFF, int(lean) & 0xFFFF, int(thrust),
                                    nspeed=ES.ROLL_NSPEED)
    seeds = strip_seeds(ctx, resid, fac, tetra)
    if not seeds:
        return dict(n_admit=0, entries=[], ends=[], reason='no_gentle_bracket')

    def transect(q):
        gx, gz, mag, r, _row = EA.entry_grad(ctx, resid, tetra, q)
        if mag <= 0.0 or mag > CLIFF_MAG:
            return None
        ts, t = [], RESID_LO
        while t <= RESID_HI:
            ts.append(t)
            t += RESID_STEP
        ents = [(q[0] + (t - r) / (mag * mag) * gx, q[1] + (t - r) / (mag * mag) * gz) for t in ts]
        out = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1]) for e in ents], 0, extra=True)
        hit = [e for e, o in zip(ents, out) if o[0]]
        rb = min(range(len(out)), key=lambda i: abs(resid(out[i])))
        return (hit[0] if hit else None), ents[rb], (gx, gz, mag)

    admit, visited = [], []
    for s in seeds:
        if any(math.hypot(s[0] - v[0], s[1] - v[1]) < 2.0 for v in visited):
            continue
        p, okseed = s, True
        for _ in range(8):
            gx, gz, mag, r, _row = EA.entry_grad(ctx, resid, tetra, p)
            if mag <= 0.0 or mag > CLIFF_MAG:
                okseed = False
                break
            if abs(r) < 1.0e-4:
                break
            step = (0.0 - r) / (mag * mag)
            d = math.hypot(step * gx, step * gz)
            if d > 0.75:                       # a longer step leaves the gentle regime it was aimed in
                step *= 0.75 / d
            p = (p[0] + step * gx, p[1] + step * gz)
        if not okseed:
            continue
        for sgn in (+1.0, -1.0):
            q = p
            for _k in range(N_ST):
                if any(math.hypot(q[0] - v[0], q[1] - v[1]) < 0.5 for v in visited):
                    break
                got = transect(q)
                if got is None:
                    break
                hit, q, (gx, gz, mag) = got
                visited.append(q)
                if hit is not None:
                    admit.append(hit)
                q = (q[0] - sgn * ARC * gz / mag, q[1] + sgn * ARC * gx / mag)
    if not admit:
        return dict(n_admit=0, entries=[], ends=[], reason='strip_never_genuine')
    ends = [EA.walk_end_for(h, fac)['walk_end'] for h in admit]
    return dict(n_admit=len(admit), entries=[[h[0], h[1]] for h in admit],
                ends=[[e[0], e[1]] for e in ends], reason='')


def herd_end_lean(item, env):
    """The herd's own m351C at its last frame -- the lean the fan's walks drift around."""
    import warnings
    from harness.tetrapush import seeds as SD
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        run = SD.make_freerun(env, native=True)
        run.pre_seed_input(SD.dtm_input_at(env)(0))
        for d in item['log']:
            run.step(d, record=False)
    return int(run.link.m351C) & 0xFFFF


def item_yield(item, env, *, leans=None, on_draw=None):
    """The probe over EVERY draw of one queue item: ``dict(item, draws, n_admitting, in_reach,
    score, seconds, ...)``.

    ``score`` is the count of admitting stations whose walk endpoint the fan can reach at this walk
    length -- the ranking key. Reach is `aimed_fan.MAX_STEP` times the plan's stepped frames
    (``walk + 1`` -- `aimed_fan.reachable`'s own convention), measured from the herd endpoint:
    admissible-generous (the true at-cap set is an annulus inside that disc), so ``in_reach = 0``
    over every draw really does mean the fan cannot meet any admitting station found."""
    from harness.tetrapush import objective as O
    from harness.tetrapush import overnight as ON
    from harness.tetrapush import entry_camera as EC
    t0 = time.time()
    walk = item['walk']
    prep, hold, trail = ON.prepared(item, env, O.courtyard_walls(), walk)
    if not prep['ok']:
        return dict(item=item['item'], ok=False, reason=prep['reason'])
    seed = prep['seed']
    tetra, link_end = seed['tetra'], seed['link']
    csa = EC.aim_camera(trail, walk)
    quals = ON.configurations(csa, item['thrusts'])
    if leans is None:
        m0 = herd_end_lean(item, env)
        leans = [ES.lean_at_roll(m0), ES.lean_at_roll((m0 - LEAN_SPREAD) & 0xFFFF),
                 ES.lean_at_roll((m0 + LEAN_SPREAD) & 0xFFFF)]
    reach = AF.MAX_STEP * (walk + 1)
    draws = []
    for q in quals:
        best = None
        for lean in leans:
            r = draw_admittance(q['facing'], lean, q['thrust'], tetra)
            r['lean'] = int(lean) & 0xFFFF
            if best is None or r['n_admit'] > best['n_admit']:
                best = r
            if r['n_admit']:
                break
        in_reach = sum(1 for e in best['ends']
                       if math.hypot(e[0] - link_end[0], e[1] - link_end[1]) <= reach)
        row = dict(cell=q['cell'], thrust=q['thrust'], facing=q['facing'], lean=best['lean'],
                   n_admit=best['n_admit'], in_reach=in_reach, reason=best['reason'],
                   ends=best['ends'])
        draws.append(row)
        if on_draw:
            on_draw(row)
    return dict(item=item['item'], unit=item['unit'], herd=item['herd'], walk=walk,
                floor=item['floor'], ok=True, tetra=[tetra[0], tetra[1]],
                link_end=[link_end[0], link_end[1]], reach=reach, leans=[int(l) for l in leans],
                n_draws=len(draws), n_admitting=sum(1 for r in draws if r['n_admit']),
                in_reach_draws=sum(1 for r in draws if r['in_reach']),
                score=sum(r['in_reach'] for r in draws),
                draws=draws, seconds=round(time.time() - t0, 1))


def main(argv=None):
    from harness.tetrapush import overnight as ON
    from harness.tetrapush import objective as O
    from harness.tetrapush import seeds as SD
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'queue'
    opt = dict(a.split('=', 1) for a in argv if '=' in a)
    inc = int(opt.get('incumbent', O.TOTAL_INCUMBENT))
    env = SD.load_env()
    keep, _d = ON.items(incumbent=inc)
    if cmd == 'item':
        want = argv[0] if argv and '=' not in argv[0] else opt.get('item')
        sel = [x for x in keep if x['item'] == want]
        if not sel:
            print('no such item %r at incumbent %d' % (want, inc))
            return 1
        r = item_yield(sel[0], env,
                       on_draw=lambda d: (print('  cell %4d thrust %2d lean %5d  ADMITS %2d, %d in reach'
                                                % (d['cell'], d['thrust'], d['lean'], d['n_admit'],
                                                   d['in_reach']), flush=True)
                                          if d['n_admit'] else None))
        print(json.dumps({k: v for k, v in r.items() if k != 'draws'}, default=float))
        out = opt.get('out')
        if out:
            json.dump(r, open(out, 'w'), indent=1)
            print('full table -> %s' % out)
        return 0
    if cmd == 'queue':
        head = int(opt.get('head', 12))
        wmin = int(opt.get('walk_min', 5))
        sel = [x for x in keep if x['walk'] >= wmin]
        # one probe per UNIT+walk is one probe per item already; walk the queue's own (floor) order
        sel = sel[:head]
        print('probing %d items (walk >= %d, floor order, incumbent %d)' % (len(sel), wmin, inc),
              flush=True)
        ranked = []
        for it in sel:
            r = item_yield(it, env)
            if not r.get('ok'):
                print('  %-14s REFUSED: %s' % (it['item'], r['reason']), flush=True)
                continue
            ranked.append(r)
            print('  %-14s floor %3d  admitting draws %2d (%2d in reach)  score %3d   %5.1f s'
                  % (r['item'], r['floor'], r['n_admitting'], r['in_reach_draws'], r['score'],
                     r['seconds']), flush=True)
        ranked.sort(key=lambda r: (-r['score'], r['floor']))
        print('\nby yield (score = in-reach admitting stations), then floor:')
        for r in ranked:
            print('  %-14s score %3d  floor %3d' % (r['item'], r['score'], r['floor']))
        out = opt.get('out')
        if out:
            json.dump([{k: v for k, v in r.items() if k != 'draws'} for r in ranked],
                      open(out, 'w'), indent=1)
            print('table -> %s' % out)
        return 0
    raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
