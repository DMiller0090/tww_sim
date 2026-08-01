"""THE SEPARATE ENTRY SEARCH (Dereck, session 60): Link's roll position + angle for the clip, with
the herd ALREADY DONE and Tetra frozen where the console left her.

This is the dual of `_generated/tetra_placements.tsv`. That list sweeps TETRA at a fixed roll entry
(`harness/rollstab/turnaround.search`, the slot-7 setup the list's header names). Here the herd has
happened, so Tetra is a MEASURED CONSTANT -- `fixtures/courtyard_plan_s73_console.json` reads her
bit-frozen at the same point on console frames 76/77/78 -- and the free variable is the ENTRY. Same
razor, swept the other way round.

THE FORK IT SETTLES (open since session 45). Two routes were on the table: (A) walk Link to the
tabulated `seeds.ENTRY_ROLL_POS` that the coord list is valid for, or (B) re-solve the clip at the
herd's natural endpoint. **(A) is falsified by measurement, not by argument** -- see `tabulated_
verdict()`. The console's Tetra misses coord 274 by 0.4321 u, and that miss is 0.4313 u PERPENDICULAR
to the coord thread, so standing exactly on the tabulated entry does not clip her: the cut ray passes
`resid` +0.3139 u from the seam vertex against an acceptance window ~1.2e-4 u wide. Reaching that
entry to f32 precision was never the hard part; it would not have paid.

THE COORDINATE THE RAZOR LIVES ON. `genuine_clip` needs the cut SEGMENT old->new to thread the gap at
the corner vertex S, so the smooth residual is that segment's signed offset from S:

    pred  = old + roll_step + push + cut_lunge      (the pre-CrrPos endpoint, decomp posMove order)
    resid = cross(pred - old, S - old) / |pred - old|

`genuine` is f32 dust inside a hair of resid == 0. Measured off the 288 tabulated coords at their own
entry: the 279 that still read genuine sit in resid [-3e-6, +1.1e-4] -- about ONE f32 ULP at this
distance from the origin, which is why the tsv is dust and not a region.

WHAT ACTUALLY MOVES IT. `old` is the same wall-braced point almost everywhere (the roll runs into the
corner and CrrPos pins it), so the entry matters ONLY through the CUT-FRAME PUSH -- whether Tetra is
still shoving Link on the frame the cut fires. push 0 gives resid -0.3294 (the bare roll-stab, 0.33 u
short of threading); the tabulated entry's push (-1.115,-0.258) gives +0.3139; genuine wants
~(-0.551,-0.127). From Link's own console endpoint the push is exactly ZERO -- Tetra is out of Co
range by the cut frame -- which is why no knob moves the residual THERE.

WHAT THE SEARCH MUST CARRY (all measured, `_notes/s79_*`):
- **entry precision ~1.0e-4 u** (window / |grad resid| = 1.2e-4 / 1.18), i.e. about one f32 ULP;
- **m351C**, the body lean, is NOT free: 0 and 1 clip, **64 already does not** (resid 1.1e-2), and the
  replayed herd hands Link m351C -191 and a walk that settles near -160. A ctx is only valid for the
  m351C it was built at;
- **link_y does not matter** (the acceptance runs on the geometry's own `LINK_Y`);
- the **roll facing** is a second knob worth ~0.0075 u of locus shift per BAM, so each realizable
  A-press aim has its own locus -- a family of near-parallel curves, not one target.

THE TARGET SET, for a pinned Tetra at the tabulated facing and m351C 0: **1735 genuine entries**, one
thin curve ~104 u long (thickness 0.9 u), every one walkable. **856 of them lie inside the 230 u
follow bar** and are the USABLE target -- past the bar Tetra leaves stt 3 and walks, so an entry out
there is not an entry. `fixtures/courtyard_entry_locus_s79.json` carries them with that flag.

REACHABILITY, measured: continuing the console-confirmed log with its own last stick held walks Link
to **3.06 u** from the usable locus by frame 85, and four other steady sticks pass within 3.8-13.1 u
by frame 82-86, all still at the speedF 17 cap the roll wants. So the target is inside Link's
reachable set and the open work is LANDING on it -- a density problem, not an accuracy one.

HOW TO SIZE THAT DENSITY (session 79's first pass ran and returned 0, by the expected margin). The
figure of merit is ``P(a near-zero candidate is genuine) ~ window / local resid spacing``, and the
spacing must be measured AT ONE FACING over the candidates that actually reach near zero -- taking it
over "the N closest by |resid|" gives a clustered, far-too-good answer (that mistake produced a 0.55
estimate for a population whose real P was 0.11). A stride-2 fan x 8 holds from two base nodes gives
3699 candidates, of which only **4** reach |resid| < 5e-3 at spacing 1.0e-3 -> an expected 0.4 hits.
And **rank the SIGNED distance to the window, not |resid|**: the window is asymmetric because its sign
is which side of the gap the ray passes, so |resid| scores a blocked-side near-miss just as highly (the
pass's own best candidate was -5.45e-5 -- inside the window's width, on the wrong side of it).

    python -m harness.tetrapush.entry_search verdict   # the fork measurement (A is dead)
    python -m harness.tetrapush.entry_search window    # the acceptance window off the 288 coords
    python -m harness.tetrapush.entry_search locus     # map the genuine entries (slow; writes json)
    python -m harness.tetrapush.entry_search reach     # replay the log, walk on, distance to locus
"""
import json
import math
import os
import sys
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.rollstab import turnaround as TA
from harness.rollstab import geometry_tetra as GT
from harness.tetrapush import seeds as SD

CONSOLE_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_plan_s73_console.json')
LOCUS_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_entry_locus_s79.json')

#: The entry the 288-coord list is valid for (the tsv header; LIVE-measured, NOT the sim walk, which
#: lands 2.6 u away -- `turnaround.entry_from_walk` is not bit-exact from rest).
TAB_ENTRY = (SD.ENTRY_ROLL_POS[0], SD.ENTRY_ROLL_POS[1])
TAB_FACING = SD.ENTRY_ROLL_FACING


def console_seed(path=CONSOLE_FIXTURE):
    """The LOCKED console read this search seeds from -- a MEASURED state, not a simulated one.
    Returns Tetra's frozen point, Link's endpoint, and the delivered log."""
    d = json.load(open(path))
    by_n = {s['n']: s for s in d['samples']}
    scored = by_n[d['plan']['scored_frames']]
    last = by_n[max(by_n)]
    return dict(tetra=(scored['tetra']['x'], scored['tetra']['z']),
                link=(last['link']['x'], last['link']['z']),
                link_facing=last['link']['facing'], link_speedF=last['link']['speedF'],
                n_scored=scored['n'], n_last=last['n'], log=d['log'],
                placement_idx=d['plan']['placement_idx'],
                placement_dist=d['plan']['placement_dist'])


def resid_fn(sch):
    """The smooth razor coordinate for a baked schedule: the cut ray's signed offset from the seam
    vertex S. Takes one `ShoveCtx.sweep_par` row (genuine, old_x, old_z, new_x, new_z, push_x,
    push_z, ...) and returns u."""
    cs = sch['cut_step']
    mx, mz = sch['dx'][cs] + sch['cutx'][cs], sch['dz'][cs] + sch['cutz'][cs]

    def resid(o):
        dx, dz = mx + o[5], mz + o[6]
        return (dx * (GT.S[1] - o[2]) - dz * (GT.S[0] - o[1])) / math.hypot(dx, dz)
    return resid


def build_at(entry=TAB_ENTRY, facing=TAB_FACING, m351c=0, thrust=TA.THRUST):
    """(ctx, sch, resid) for one (facing, m351C, thrust). The ctx is valid for ANY entry POSITION --
    the baked schedule is position-independent (gated: `test_schedule_is_entry_position_invariant`),
    and `sweep_par` takes link_x0/link_z0 per sample -- but NOT for another facing or m351C."""
    ctx, sch = TA.build_ctx_at(entry, facing, m351c, TA.GROUND_Y, thrust)
    return ctx, sch, resid_fn(sch)


def evaluate(ctx, resid, tetra, entries):
    """Score a list of entry (x, z) against a pinned Tetra -> [(entry, genuine, resid, push)]."""
    rows = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1]) for e in entries], 0)
    return [(e, bool(o[0]), resid(o), (o[5], o[6])) for e, o in zip(entries, rows)]


def acceptance_window(placements=None):
    """The genuine `resid` band, MEASURED off the tabulated coords at their own entry rather than
    assumed. Returns dict(lo, hi, width, n_genuine, n_total, miss_lo, miss_hi)."""
    rows = placements if placements is not None else SD.load_placements()[0]
    ctx, sch, resid = build_at()
    scored = ctx.sweep_par([(r['x'], r['z'], TAB_ENTRY[0], TAB_ENTRY[1]) for r in rows], 0)
    ok = [resid(o) for o in scored if o[0]]
    no = [resid(o) for o in scored if not o[0]]
    return dict(lo=min(ok), hi=max(ok), width=max(ok) - min(ok), n_genuine=len(ok),
                n_total=len(rows), miss_lo=(min(no) if no else None),
                miss_hi=(max(no) if no else None),
                miss_idx=[r['idx'] for r, o in zip(rows, scored) if not o[0]])


def tabulated_verdict(seed=None, placements=None):
    """**THE FORK MEASUREMENT.** Stand Link exactly on the tabulated entry the coord list is valid
    for and fire the clip at the console's own Tetra. Returns the residual, the genuine flag, and the
    perpendicular half of her miss on the nearest coord -- the three numbers that kill route (A)."""
    seed = seed or console_seed()
    rows = placements if placements is not None else SD.load_placements()[0]
    ctx, sch, resid = build_at()
    o = ctx.sweep_par([(seed['tetra'][0], seed['tetra'][1], TAB_ENTRY[0], TAB_ENTRY[1])], 0)[0]
    idx = seed['placement_idx']
    c = next(r for r in rows if r['idx'] == idx)
    # split her miss into along-thread and perpendicular, using the local thread direction
    nxt = next(r for r in rows if r['idx'] == idx + 1)
    ux, uz = nxt['x'] - c['x'], nxt['z'] - c['z']
    n = math.hypot(ux, uz)
    ux, uz = ux / n, uz / n
    dx, dz = seed['tetra'][0] - c['x'], seed['tetra'][1] - c['z']
    along = dx * ux + dz * uz
    perp = math.hypot(dx - along * ux, dz - along * uz)
    return dict(genuine=bool(o[0]), resid=resid(o), push=(o[5], o[6]), old=(o[1], o[2]),
                coord_idx=idx, miss=math.hypot(dx, dz), miss_along=along, miss_perp=perp)


def genuine_entries(tetra, *, facing=TAB_FACING, m351c=0, centre=None, half=130.0,
                    coarse=0.5, fine=0.002, tol=0.05, thrust=TA.THRUST, progress=False):
    """Map the genuine ENTRY set for a pinned Tetra: coarse-sweep the smooth residual, keep the
    cells within `tol` of zero, then refine those to the f32 dust. Blind fine sweeping does not work
    -- the window is ~1 ULP wide, so a 0.25 u grid over a 120 u box finds 1 hit in 231k."""
    ctx, sch, resid = build_at(TAB_ENTRY, facing, m351c, thrust)
    if centre is None:
        centre = TAB_ENTRY
    n = int(half / coarse)
    keys = [(centre[0] + i * coarse, centre[1] + j * coarse)
            for i in range(-n, n + 1) for j in range(-n, n + 1)]
    seeds_ = [k for k, o in zip(keys, ctx.sweep_par(
        [(tetra[0], tetra[1], k[0], k[1]) for k in keys], 0)) if abs(resid(o)) < tol]
    if progress:
        print("  coarse %d -> %d seed cells" % (len(keys), len(seeds_)))
    m = int(coarse / fine) // 2
    hits = []
    for c, k in enumerate(seeds_):
        pts = [(tetra[0], tetra[1], k[0] + i * fine, k[1] + j * fine)
               for i in range(-m, m + 1) for j in range(-m, m + 1)]
        for p, o in zip(pts, ctx.sweep_par(pts, 0)):
            if o[0]:
                hits.append(dict(entry=[p[2], p[3]], resid=resid(o), push=[o[5], o[6]]))
        if progress and (c + 1) % 50 == 0:
            print("  refined %d/%d cells, %d genuine" % (c + 1, len(seeds_), len(hits)))
    return hits


def locus_metrics(hits, seed=None):
    """Shape of a `genuine_entries` result: principal axis, extent, thickness, and the reachability
    numbers (distance from Link's console endpoint, distance to Tetra vs the 230 u follow bar)."""
    seed = seed or console_seed()
    pts = [tuple(h['entry']) for h in hits]
    xs, zs = [p[0] for p in pts], [p[1] for p in pts]
    mx, mz = sum(xs) / len(xs), sum(zs) / len(zs)
    sxx = sum((x - mx) ** 2 for x in xs)
    szz = sum((z - mz) ** 2 for z in zs)
    sxz = sum((x - mx) * (z - mz) for x, z in zip(xs, zs))
    th = 0.5 * math.atan2(2 * sxz, sxx - szz)
    ux, uz = math.cos(th), math.sin(th)
    ts = sorted((p[0] - mx) * ux + (p[1] - mz) * uz for p in pts)
    ps = [abs((p[0] - mx) * -uz + (p[1] - mz) * ux) for p in pts]
    dl = sorted(math.hypot(p[0] - seed['link'][0], p[1] - seed['link'][1]) for p in pts)
    dt = sorted(math.hypot(p[0] - seed['tetra'][0], p[1] - seed['tetra'][1]) for p in pts)
    return dict(n=len(pts), axis=(ux, uz),
                axis_bam=math.degrees(math.atan2(ux, uz)) % 360 / 360 * 65536,
                extent=ts[-1] - ts[0], thickness=max(ps), centroid=(mx, mz),
                d_link=(dl[0], dl[-1]), d_tetra=(dt[0], dt[-1]),
                walkable=sum(1 for p in pts if TA.is_walkable(p[0], p[1])),
                follow_ok=sum(1 for d in dt if d <= 230.0))


def entry_gradient(tetra, entry, *, facing=TAB_FACING, m351c=0, d=0.01, thrust=TA.THRUST):
    """|d resid / d entry| at a point, and the entry precision it implies for a given window."""
    ctx, sch, resid = build_at(TAB_ENTRY, facing, m351c, thrust)
    q = ctx.sweep_par([(tetra[0], tetra[1], entry[0], entry[1]),
                       (tetra[0], tetra[1], entry[0] + d, entry[1]),
                       (tetra[0], tetra[1], entry[0], entry[1] + d)], 0)
    r0 = resid(q[0])
    gx, gz = (resid(q[1]) - r0) / d, (resid(q[2]) - r0) / d
    return dict(resid=r0, gx=gx, gz=gz, grad=math.hypot(gx, gz))


def continue_walk(extra, *, log=None, env=None):
    """Replay the console-confirmed delivered log on a fresh `FreeRun`, then keep stepping `extra`
    (a list of raw input dicts). Returns (run, rows) with one row per EXTRA frame -- the reachability
    probe, seeded from the measured endpoint the handoff asks for."""
    seed = console_seed()
    env = env or SD.load_env()
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for inp in (log if log is not None else seed['log']):
            run.step(inp)
        n0 = len(seed['log'])
        for k, inp in enumerate(extra):
            run.step(inp)
            lk = run.link
            rows.append(dict(n=n0 + k + 1, x=lk.pos_x, z=lk.pos_z, facing=lk.facing & 0xFFFF,
                             proc=lk.state & 0xFF, speedF=lk.speedF,
                             m351C=getattr(lk, 'm351C', 0) & 0xFFFF,
                             csangle=getattr(lk, 'csangle', 0) & 0xFFFF))
    return run, rows


def load_locus(path=LOCUS_FIXTURE):
    return json.load(open(path))


# --------------------------------------------------------------------------- CLI

def _cmd_verdict():
    seed = console_seed()
    v = tabulated_verdict(seed)
    w = acceptance_window()
    print("THE s45 FORK, MEASURED (session 79)\n")
    print("  console Tetra          (%r, %r)  frozen on frames %d..%d"
          % (seed['tetra'][0], seed['tetra'][1], seed['n_scored'], seed['n_last']))
    print("  nearest genuine coord  idx %d, %.4f u away" % (v['coord_idx'], v['miss']))
    print("     of which ALONG the thread %+.4f u, PERPENDICULAR %.4f u" % (v['miss_along'], v['miss_perp']))
    print("  acceptance window      resid [%+.2e, %+.2e]  (%d/%d tabulated coords re-read genuine)"
          % (w['lo'], w['hi'], w['n_genuine'], w['n_total']))
    print("\n  AT THE TABULATED ENTRY (%r, %r) facing %d:" % (TAB_ENTRY + (TAB_FACING,)))
    print("     resid %+.6f u   push (%+.5f, %+.5f)   genuine = %s"
          % (v['resid'], v['push'][0], v['push'][1], v['genuine']))
    print("\n  => route (A) -- walk to the tabulated entry -- is DEAD: standing exactly on it misses")
    print("     the seam by %.0fx the window. Route (B), re-solving the clip at the herd's own"
          % (abs(v['resid']) / w['width']))
    print("     endpoint, is the live one; the ENTRY becomes the razor knob.")


def _cmd_window():
    w = acceptance_window()
    print("acceptance window, measured off the %d tabulated coords at their own entry:" % w['n_total'])
    print("  genuine  n=%d   resid %+.3e .. %+.3e   (width %.2e u)"
          % (w['n_genuine'], w['lo'], w['hi'], w['width']))
    print("  NOT      n=%d   resid %+.3e .. %+.3e   idx %s"
          % (w['n_total'] - w['n_genuine'], w['miss_lo'], w['miss_hi'], w['miss_idx']))
    print("  (the two overlap -- the boundary is f32 dust, which is what makes this a lottery)")


def _cmd_locus(argv):
    half = float(argv[0]) if argv else 130.0
    seed = console_seed()
    hits = genuine_entries(seed['tetra'], half=half, progress=True)
    m = locus_metrics(hits, seed)
    print("\n%d genuine entries" % m['n'])
    print("  axis %.0f BAM   extent %.2f u   thickness %.3f u   centroid (%.3f,%.3f)"
          % (m['axis_bam'], m['extent'], m['thickness'], m['centroid'][0], m['centroid'][1]))
    print("  d(Link console endpoint) %.2f..%.2f u   d(Tetra) %.2f..%.2f u (bar 230)"
          % (m['d_link'] + m['d_tetra']))
    print("  walkable %d/%d   inside the follow bar %d/%d"
          % (m['walkable'], m['n'], m['follow_ok'], m['n']))
    out = os.path.join(_rb, '_generated', 's79', 'entry_locus.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(facing=TAB_FACING, m351c=0, tetra=list(seed['tetra']), hits=hits, metrics=
                   {k: (list(v) if isinstance(v, tuple) else v) for k, v in m.items()}),
              open(out, 'w'))
    print("  wrote %s" % out)


def _cmd_reach(argv):
    n = int(argv[0]) if argv else 10
    seed = console_seed()
    loc = load_locus() if os.path.exists(LOCUS_FIXTURE) else None
    # the USABLE subset only -- an entry outside the follow bar is not an entry
    pts = [tuple(h['entry']) for h in loc['hits'] if h.get('follow_ok', True)] if loc else []

    def dloc(x, z):
        return min(math.hypot(x - p[0], z - p[1]) for p in pts) if pts else float('nan')

    last = dict(seed['log'][-1])
    sticks = [('hold last', (last['stickX'], last['stickY'])), ('N', (128, 255)),
              ('NE', (219, 219)), ('E', (255, 128)), ('SE', (219, 37))]
    print("reachability from the console-measured endpoint (frame %d), %d extra frames:\n"
          % (seed['n_last'], n))
    for name, (sx, sy) in sticks:
        inp = dict(last, stickX=sx, stickY=sy, buttons=0)
        _, rows = continue_walk([inp] * n)
        best = min(rows, key=lambda r: dloc(r['x'], r['z']))
        print("  %-10s closest at frame %d: (%12.5f,%12.5f) d(locus) %7.3f u  m351C %5d csangle %d"
              % (name, best['n'], best['x'], best['z'], dloc(best['x'], best['z']),
                 best['m351C'], best['csangle']))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'verdict'
    if cmd == 'verdict':
        _cmd_verdict()
    elif cmd == 'window':
        _cmd_window()
    elif cmd == 'locus':
        _cmd_locus(argv)
    elif cmd == 'reach':
        _cmd_reach(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
