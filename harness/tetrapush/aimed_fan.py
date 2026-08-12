"""**AIM THE ENUMERATION AT THE RAZOR'S STRIP INSTEAD OF DRAWING AT IT** (session 161).

`entry_aim` turned the razor's acceptance into a signed distance in u of Link's ENTRY, and the entry is
`entry_search.roll_entry` of the walk endpoint -- so ``aim`` + ``walk_end_for`` say, before a single core
is cloned, WHERE A PLAN'S WALK HAS TO END. This module is what the fan does with that.

**WHY IT WAS BUILT, and what it turned out to be worth.** Containing the console's own plan costs
`overnight.fan_exact` 40274 fleets against the legacy 353 at walk 4 -- **114x**, ~2 h an item -- and
containment is not optional (`[[search-must-rediscover-known-answer]]`), so the price had to come off
somewhere that is not coverage. A junction is |alpha| clones and one that cannot REACH the target cannot
produce a hit at any draw, so the target should have paid for it. **It does not: the prune measures 1.4x
and the ordering ~2.4x.** The hold segment steers the at-cap endpoint over a 33 degree arc whose bearing
window is per-junction, so knowing where the walk must END pins the junction to a band most junctions are
already in. Aiming localises the razor and not the fan -- `knowledge/model/aiming-the-fan.md` is the
measurement, and this module is kept because 2.4x of a 2 h item is free and lossless, not because it
solved the problem.

**THE BOUND IS ADMISSIBLE, WHICH IS THE ONLY REASON IT MAY BE USED.** A stepped frame moves Link by
``|speedF|`` and nothing else (no walls in the Courtyard sim, and at walk 4 the leaf never touches her --
her span across a whole fan is 0.000000 u, s160). Measured over the console item's FULL stride-1
alphabet off every base offset and off its own pre junction (`_notes/s161_step.py`): displacement is
17.0000 u dead flat on the first stepped frame -- at ``input_delay = 1`` the stick has not acted yet --
and peaks at **18.70 u** one frame later before decaying. `MAX_STEP` is 19.0 u against that, and
`step_bound` re-measures it so a seed that broke the bound would be a FAILING GATE and not a silent
miss.

**WHAT THIS DELIBERATELY DOES NOT DO: refine the hold letter coarse-to-fine.** The obvious saving is to
draw the hold segment from a coarse alphabet and refine near the best, and it cannot be made lossless
here. Measured at the console junction over 2 delivered frames, adjacent byte-grid classes land
endpoints a median 0.156 u apart but up to **54.2 u** apart -- the map has real discontinuities, so a
Lipschitz bound over a coarse cell is 54 u wide and prunes nothing. A coarse-to-fine hold search would
be exactly the s160 failure in a new place: an enumeration that cannot emit a plan it needs to.

**THE TARGET IS A CURVE, NOT A POINT.** ``genuine`` is ``resid`` inside a narrow positive band
(s158), so the entries that clip form a strip ~1.2e-04 u wide and tens of u long -- `aim_curve` walks it
by stepping ALONG the level curve and re-aiming, and returns the genuine entries it confirmed. A fan
whose endpoint lattice is 0.2-0.4 u has to meet a curve, not hit a point, and the prune takes the
distance to the NEAREST target.

usage:
    python -m harness.tetrapush.aimed_fan bound         # re-measure MAX_STEP against the enumeration
    python -m harness.tetrapush.aimed_fan curve [n=24]  # the target curve at the console configuration
    python -m harness.tetrapush.aimed_fan contain [jp=2] [aimed=0] [threads=8]   # the leaf-set gate
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

from harness.tetrapush import entry_aim as EA
from harness.tetrapush import entry_search as ES

#: **u a stepped frame, and it must be an UPPER BOUND** (module docstring). Measured peak 18.70 u;
#: `step_bound` re-measures it rather than trusting it, and nothing here tunes it per item.
MAX_STEP = 19.0

#: Slack on the reach test, in u. The target is a curve sampled at finite spacing and `walk_end_for` is
#: an inverse good to ~1 ULP of 1600, so the bound is widened by one frame's worth of neither.
REACH_TOL = 1.0e-2


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', float(v)))[0]


def reachable(core, target, frames, *, tol=None, max_step=MAX_STEP):
    """**CAN THIS JUNCTION STILL REACH THE TARGET?** The subtree prune, and it is one comparison.

    ``target`` is an ``(x, z)`` walk endpoint or a sequence of them (the strip is a curve, so the test
    is against the NEAREST).

    **``frames`` IS STEPPED FRAMES, NOT DELIVERED ONES, and the difference is the whole prune.** A hold
    of ``j`` delivered frames is ``j + 1`` stepped ones (`overnight._fan`'s ``input_delay = 1``
    convention), so `fan_exact` passes ``walk - n0 - jp + 1``. The first draft of this passed the
    delivered count and pruned 20130 of 20130 junctions at the console item -- INCLUDING the branch that
    provably contains the console's own plan, whose junction sits 49.66 u from the delivered endpoint
    against a 38.0 u bound that should have been 57.0 u. `tests/test_aimed_fan.py` gates that exact
    junction as the prune's own rediscovery check.

    Admissible by construction: no sequence of ``frames`` steps moves Link further than
    ``frames * max_step``, so a junction this drops could not have produced a hit at any draw."""
    tol = REACH_TOL if tol is None else float(tol)
    lim = float(frames) * float(max_step) + tol
    x, z = core.pos_x, core.pos_z
    for t in ([target] if _is_point(target) else target):
        if math.hypot(t[0] - x, t[1] - z) <= lim:
            return True
    return False


def _is_point(t):
    return len(t) == 2 and not hasattr(t[0], '__len__')


def _nearest(core, target):
    x, z = core.pos_x, core.pos_z
    return min(math.hypot(t[0] - x, t[1] - z)
               for t in ([target] if _is_point(target) else target))


def rank(cores, target, frames, *, step=ES.WALK_CAP):
    """**ORDER THE JUNCTIONS BY HOW WELL THEY SIT ON THE TARGET, and drop none of them.**

    A junction that survives `reachable` still mostly cannot hit: measured over the console item's own
    alphabet, the leaves the fan KEEPS -- at the cap and rollable, which is what `fan_exact.collect`
    admits -- do not fill their reach disc but a thin ANNULUS around it. At 2 / 3 / 4 stepped frames the
    at-cap displacement is **33.65-34.00 / 49.60-51.00 / 64.53-68.00 u** against discs of 38 / 57 / 76,
    and the envelope reads the same at a base core and at the console's own junction. The reason is the
    cap itself: an at-cap leaf held ~17.0 u a frame the whole way, so it went nearly straight.

    **That is a ranking here and NOT a prune, deliberately.** Its upper edge is not provable (speedF
    overshoots to 18.70 one frame after a stick change before settling, so ``r x 17.61`` is not a bound)
    and its lower edge would need a maximum turn rate this work has not derived. An empirical envelope
    used as a prune is exactly the s160 failure -- an enumeration that cannot emit a plan it needs --
    so it is used where being wrong costs nothing: the ORDER a deadline-bounded fan spends its time in.
    `fan_exact` reports ``covered`` when the clock cuts it, and with this the covered part is the part
    that could have hit.

    Key is ``| |W - J| - frames * step |``: distance from the annulus the at-cap leaves actually live
    on. Returns ``cores`` reordered, never filtered.

    **AND IT IS ONLY WORTH ~2.4x, WHICH IS THE SESSION'S REAL ANSWER TO "AIM INSTEAD OF DRAW".** Ranked
    against its own delivered endpoint the console's junction lands 1366th of 3355 (gated). The hold
    segment steers the at-cap endpoint over a **33 degree arc** covering ~12 x 25 u, so knowing the
    endpoint pins the junction to an arc band most junctions are already in -- and the band's bearing
    window is per-junction, not a constant (union over 12 sampled junctions: 41% of the circle). The
    razor localises to a 1.2e-04 u strip; the FAN does not localise at all. Containment's 114x is
    therefore still unpaid, and this is a discount on it, not a solution."""
    want = float(frames) * float(step)
    return sorted(cores, key=lambda ic: abs(_nearest(ic[1], target) - want))


def annulus(base, cores, frames, *, keep=None):
    """The measured displacement envelope of ``cores`` from ``base`` -- what `rank` is ranking toward.

    ``keep(core)`` is the fan's own admission test; pass `fan_exact`'s (at cap and rollable) to get the
    envelope that matters, which is far thinner than the whole fan's. Returns
    ``dict(lo, hi, n, n_total, straight)``, where ``straight = frames * WALK_CAP`` is what a leaf that
    never turned would travel -- the envelope sits just under it, which is why `rank`'s key uses it."""
    vals = [math.hypot(c.pos_x - base.pos_x, c.pos_z - base.pos_z)
            for _i, c in cores if keep is None or keep(c)]
    return dict(lo=(min(vals) if vals else None), hi=(max(vals) if vals else None), n=len(vals),
                n_total=len(cores), straight=float(frames) * ES.WALK_CAP)


def step_bound(base, alphabet, lsched, csangle, cs_trail, cs_from):
    """The LARGEST per-stepped-frame displacement this alphabet produces off ``base``, measured.

    `MAX_STEP` is only sound while this stays under it, so the number is produced by the same primitive
    the fan steps (`overnight._fan`) rather than asserted. Returns
    ``dict(per_frame, total, speed_max, frames, n)``."""
    from harness.tetrapush import overnight as ON
    cores = ON._fan(base, alphabet, lsched, csangle, cs_trail, cs_from, 0, alive_only=False)
    d = [math.hypot(c.pos_x - base.pos_x, c.pos_z - base.pos_z) for _i, c in cores]
    sp = [abs(c.speedF) for _i, c in cores]
    n = max(len(lsched), 1)
    return dict(per_frame=(max(d) / n if d else 0.0), total=(max(d) if d else 0.0),
                speed_max=(max(sp) if sp else 0.0), frames=n, n=len(cores))


# ------------------------------------------------------------------- the target: a curve, not a point

def target_entry(facing, lean, thrust, entry, tetra, **kw):
    """One genuine entry near ``entry`` -- `entry_aim.aim`, unchanged, named for what the fan wants."""
    return EA.aim(facing, lean, thrust, entry, tetra, **kw)


def aim_curve(facing, lean, thrust, entry, tetra, *, n=24, arc=None, ctx=None, sch=None, resid=None,
              nspeed=None, band=None, log=None):
    """**THE STRIP, SAMPLED** -- ``n`` genuine entries walked ALONG the razor's level curve.

    ``genuine`` is ``resid`` inside a positive band (s158), so the clipping entries are a strip
    ~1.2e-04 u wide and long -- one `aim` returns one point on it, and a fan with a 0.2-0.4 u endpoint
    lattice needs the whole curve to have anything to meet. Each sample steps ``arc`` u along the
    residual's own level direction (perpendicular to its gradient) and re-aims, so a step that drifts
    off the band is pulled back by the sim rather than extrapolated.

    ``arc`` defaults to the fan's own endpoint lattice (0.3 u): sampling finer than the thing that has
    to hit it buys nothing. Returns ``dict(entries, walk_ends, tried, band)`` -- only the entries the
    sim called ``genuine`` are kept, so a sample that fell off the strip is DROPPED and counted, never
    returned as a target."""
    arc = 0.3 if arc is None else float(arc)
    if ctx is None:
        ctx, sch, resid = ES.build_fast(facing, int(lean) & 0xFFFF, thrust, nspeed=nspeed)
    if band is None:
        band = EA.band_for(facing, lean, thrust, entry, tetra, ctx=ctx, sch=sch, resid=resid)
    got, ends, tried, p = [], [], 0, (float(entry[0]), float(entry[1]))
    for k in range(int(n)):
        tried += 1
        a = EA.aim(facing, lean, thrust, p, tetra, band=band, ctx=ctx, sch=sch, resid=resid)
        if a['ok']:
            got.append([a['entry'][0], a['entry'][1]])
            ends.append(EA.walk_end_for(a['entry'], facing, nspeed=nspeed)['walk_end'])
            p = (a['entry'][0], a['entry'][1])
        if log:
            log('  sample %2d: genuine %s  entry (%.9f, %.9f)' % (k, a['ok'], p[0], p[1]))
        gx, gz, mag, _r, _row = EA.entry_grad(ctx, resid, tetra, p)
        if mag <= 0.0:
            break
        p = (p[0] - arc * gz / mag, p[1] + arc * gx / mag)   # along the level curve
    return dict(entries=got, walk_ends=ends, tried=tried, arc=arc,
                band=[band.get('lo'), band.get('hi')], sufficient=band.get('sufficient'))


def curve_span(walk_ends):
    """How much of a target a fan is actually being asked to meet: the sampled curve's extent in u."""
    if len(walk_ends) < 2:
        return 0.0
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(walk_ends, walk_ends[1:]))


# --------------------------------------------------------------------------------- the CLI + the gate

def _console_setup(walk=None):
    from harness.tetrapush import entry_fan as EF
    from harness.tetrapush import objective as O
    from harness.tetrapush import overnight as ON
    from harness.tetrapush import seeds as SD
    env = SD.load_env()
    cc = ON.console_candidate()
    walk = cc['walk'] if walk is None else int(walk)
    prep, hold, trail = ON.prepared(cc['unit'], env, O.courtyard_walls(), walk)
    plan = ON.from_triples(cc['plan'])
    csa = ON.aim_camera(plan, walk, trail)
    return dict(env=env, cc=cc, walk=walk, prep=prep, hold=hold, trail=trail, plan=plan, csa=csa,
                EF=EF, ON=ON)


def bound(verbose=True):
    """**RE-MEASURE `MAX_STEP` AGAINST THE ENUMERATION IT BOUNDS.** A prune is only admissible while
    this passes, so it is a gate and not a note."""
    s = _console_setup()
    alpha = s['EF'].stick_alphabet(1)
    worst, rows = 0.0, []
    for n0 in range(s['walk']):
        base, _run = s['EF'].base_core(n0, seed=s['prep']['seed'], env=s['env'], hold=s['hold'])
        for j in range(1, s['walk'] - n0 + 1):
            b = step_bound(base, alpha, [0] * (j + 1), s['csa'], s['trail'], n0)
            worst = max(worst, b['per_frame'])
            rows.append(dict(n0=n0, j=j, **b))
            if verbose:
                print('  n0 %d, %d delivered: <= %.4f u total, %.4f u a frame, |speedF| <= %.4f'
                      % (n0, j, b['total'], b['per_frame'], b['speed_max']))
    if verbose:
        print('MAX_STEP %.2f vs measured %.4f u a frame -- %s'
              % (MAX_STEP, worst, 'HOLDS' if worst <= MAX_STEP else 'VIOLATED'))
    return dict(measured=worst, max_step=MAX_STEP, ok=bool(worst <= MAX_STEP), rows=rows)


def curve(n=24, verbose=True):
    """The target curve at the console's own configuration, and what it costs to build."""
    from harness.tetrapush import admit_map as AM
    cfg = AM.CONSOLE
    t0 = time.time()
    c = aim_curve(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'], n=int(n))
    dt = time.time() - t0
    if verbose:
        print('console configuration: cell %d thrust %d, band [%+.4e, %+.4e] sufficient %s'
              % (ES.aim_cell(cfg['facing']), cfg['thrust'], c['band'][0], c['band'][1],
                 c['sufficient']))
        print('  %d of %d samples genuine in %.1f s (%.0f ms a sample), arc step %.2f u'
              % (len(c['entries']), c['tried'], dt, 1000.0 * dt / max(c['tried'], 1), c['arc']))
        print('  walk-endpoint curve spans %.4f u' % curve_span(c['walk_ends']))
        for e, w in list(zip(c['entries'], c['walk_ends']))[:4]:
            print('    entry (%.9f, %.9f) <- walk end (%.9f, %.9f)' % (e[0], e[1], w[0], w[1]))
    return dict(seconds=dt, span=curve_span(c['walk_ends']), **c)


#: Where `contain` banks its result. TRACKED, because it is the artefact the containment gate asserts
#: against: the run itself is ~40 min and a 1-second gate may not re-run it (`[[slow-offline-tests]]`).
CONTAIN_BANK = os.path.join(_rb, 'fixtures', 'courtyard_fan_containment.json')


def contain(pre_frames=(2,), aimed=False, atom=False, nthreads=0, deadline=None, walk=None,
            bank=None, verbose=True):
    """**DOES `overnight.fan_exact`'s OWN LEAF SET CONTAIN THE CONSOLE'S WALK ENDPOINT, BIT-EXACTLY?**

    The honest form of the containment question (`[[search-must-rediscover-known-answer]]`), one level
    up from `_notes/s160_reach.py`: s160 showed the fan's PRIMITIVE reproduces the endpoint when handed
    the console's own letters, which is a statement about `_fan`. This one runs the ENUMERATION -- every
    ``n0``, both families, the full stride-2 pre alphabet and the pinned stride-1 hold -- and asks
    whether the endpoint comes back as a KEY.

    **``pre_frames`` MAY BE RESTRICTED WITHOUT WEAKENING THE CLAIM, and that is what makes this
    affordable.** ``pre_frames`` only ADDS branches, so the leaf set at ``(2,)`` is a subset of the leaf
    set at every split: finding the endpoint in the subset proves the full contained fan contains it.
    The full fan is 20130 junctions at a calibrated 0.357 s each (~2 h an item); the console's own split
    alone is 6710 (~40 min).

    ``aimed=True`` additionally runs it through `reachable`. That is the PRUNE's own rediscovery check:
    the prune is admissible, so it may only remove -- and if it removed THIS junction the bound would be
    wrong, which is exactly how the first draft's delivered-vs-stepped frame count was caught."""
    s = _console_setup(walk)
    ON = s['ON']
    want = tuple(json.load(open(ON.CONSOLE_CLIP))['hit']['walk'])
    tgt = want if aimed else None
    t0 = time.time()
    out, st = ON.fan_exact(s['prep']['seed'], s['env'], s['walk'], s['csa'], s['trail'], s['hold'],
                           contained=True, atom=atom, two_segment=True, pre_frames=pre_frames,
                           nthreads=nthreads, deadline=deadline, target=tgt)
    dt = time.time() - t0
    keys = list(out)
    hit = next((k for k in keys if _bits(k[0]) == _bits(want[0]) and _bits(k[1]) == _bits(want[1])),
               None)
    near = sorted(keys, key=lambda k: math.hypot(k[0] - want[0], k[1] - want[1]))[:5]
    res = dict(ok=hit is not None, want=list(want), seconds=dt, aimed=bool(aimed), atom=bool(atom),
               pre_frames=list(pre_frames), keys=len(keys), plan=(list(out[hit]) if hit else None),
               nearest=[dict(xz=[k[0], k[1]], d=math.hypot(k[0] - want[0], k[1] - want[1]),
                             lean=k[2], speedF=k[3]) for k in near],
               stats=dict((k, v) for k, v in st.items() if k != 'pre_frames'))
    if hit is not None:
        res['hit'] = dict(xz=[hit[0], hit[1]], lean=hit[2], speedF=hit[3],
                          at_cap=bool(ON.at_cap(hit[3])))
    if verbose:
        print('contained fan, splits %s%s: %d at-cap keys in %.1f s (%d junctions, %d sub-cap)'
              % (list(pre_frames), ' AIMED' if aimed else '', len(keys), dt,
                 st.get('junctions', 0), st.get('sub_cap', 0)))
        print('  console walk endpoint (%.9f, %.9f) IN THE LEAF SET: %s'
              % (want[0], want[1], res['ok']))
        if hit is not None:
            print('    as plan %s, lean %d, speedF %.6f' % (res['plan'], hit[2], hit[3]))
        print('  nearest keys: %s' % ['%.3e' % n['d'] for n in res['nearest']])
    if bank:
        json.dump(res, open(bank, 'w'), indent=1, default=float)
    return res


def main(argv):
    cmd = argv[0] if argv else 'bound'
    kw = dict(a.split('=', 1) for a in argv[1:] if '=' in a)
    if cmd == 'contain':
        r = contain(pre_frames=tuple(int(x) for x in kw.get('jp', '2').split(',')),
                    aimed=bool(int(kw.get('aimed', 0))), atom=bool(int(kw.get('atom', 0))),
                    nthreads=int(kw.get('threads', 0)),
                    bank=kw.get('bank', CONTAIN_BANK))
        print('LEAF-SET CONTAINMENT: %s' % ('PASS' if r['ok'] else 'FAIL'))
        return 0 if r['ok'] else 1
    if cmd == 'bound':
        b = bound()
        print('STEP-BOUND GATE: %s' % ('PASS' if b['ok'] else 'FAIL'))
        return 0 if b['ok'] else 1
    if cmd == 'curve':
        c = curve(n=int(kw.get('n', 24)))
        print(json.dumps(dict(n=len(c['entries']), span=c['span'], seconds=c['seconds']), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
