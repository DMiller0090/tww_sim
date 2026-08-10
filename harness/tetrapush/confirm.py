"""**Clip viability, computed on demand and cached -- never tabulated.**

`_generated/tetra_placements.tsv` is a table of genuine Tetra coords recorded at ONE roll entry, and
session 142 showed what leaning on a table costs in both directions: the search never read it (so it
was not restricting anything) and nothing replaced it (so the herd optimised toward `l0` +51 while
clips fire at +4..+13). Dereck's rule, session 142: **do not build another table.** A precomputed
"genuine set" is only as good as the grid it was sampled on, and no grid is exhaustive.

So viability is a FUNCTION here, evaluated per candidate:

    confirmed(pf, tetra) -> {'n': int, 'gap': float|None, 'entries': [...]}

which is `handoff.entry_locus` -- `side_band` walked in f32 steps until the pair actually overlaps --
with a persistent cache keyed by the exact bits of ``(facing, thrust, lean, tetra, runways)``. The
cache makes repetition free without making the answer a lookup: a Tetra never seen before is computed,
and the number returned is always the derived one.

**The pairing that makes this affordable is branch-and-bound, not the cache.** `entry_roots` (what
`handoff.endpoint(roots=True)` ranks on) solves the razor's residual zero-crossings without checking
overlap, so it is an UNDER-ESTIMATE of the confirmed gap by construction -- an admissible heuristic.
`best_confirmed` therefore scans candidates in ascending roots-bound, confirms each, and STOPS when
the next roots-bound is already worse than the best confirmed bound found: everything past that point
has a true bound at least as large, so it cannot win. No candidate is skipped on a guess, and the scan
is exact over whatever population it is handed.
"""
import json
import os
import struct

from . import handoff as HO

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: derived and regenerable, so it lives with the other `_generated` artefacts
CACHE = os.path.join(_ROOT, '_generated', 'confirm_cache.json')

_MEM = None


def _key(pf, tetra, runways):
    """Exact bits, never rounded: two Tetras 1e-7 u apart are different questions on a razor this
    thin (`[[full-fp-precision-coords]]`), so the cache must not merge them."""
    b = struct.pack('>dd', float(tetra[0]), float(tetra[1])).hex()
    return '%d:%d:%d:%s:%s' % (pf.facing, pf.thrust, pf.lean, b,
                              ','.join(str(int(r)) for r in runways))


def _load():
    global _MEM
    if _MEM is None:
        try:
            with open(CACHE) as fh:
                _MEM = json.load(fh)
        except (IOError, ValueError):
            _MEM = {}
    return _MEM


def save():
    """Persist the cache. Callers batch this -- a confirm is ~15 s, a dump is milliseconds."""
    if _MEM is None:
        return
    d = os.path.dirname(CACHE)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    tmp = CACHE + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(_MEM, fh)
    os.replace(tmp, CACHE)


def confirmed(pf, tetra, link=None, runways=HO.RUNWAYS, use_cache=True):
    """**Does a genuine entry exist at this Tetra, and how far is Link from the nearest one?**

    Returns ``n`` (confirmed entries), ``entries`` (world XZ + runway), and -- when ``link`` is given
    -- ``gap``, the distance to the nearest one. ``n == 0`` is a real answer: the clip does not fire
    at this Tetra for this terminal, and no amount of herding to it will help.

    This is `entry_locus`, i.e. every root's `side_band` walked until the pair overlaps -- the same
    predicate `handoff.probe` reports, with nothing tabulated in the path."""
    mem = _load() if use_cache else {}
    k = _key(pf, tetra, runways)
    rec = mem.get(k)
    if rec is None:
        loc = HO.entry_locus(pf, tetra, runways=tuple(runways))
        rec = dict(n=len(loc), entries=[[b['entry'][0], b['entry'][1], b['runway'],
                                         b['side'], b['width']] for b in loc])
        if use_cache:
            mem[k] = rec
    if link is None:
        return dict(rec, gap=None, cached=(rec is mem.get(k)))
    if not rec['n']:
        return dict(rec, gap=float('inf'))
    d = [((e[0] - link[0]) ** 2 + (e[1] - link[1]) ** 2) ** 0.5 for e in rec['entries']]
    i = min(range(len(d)), key=lambda j: d[j])
    return dict(rec, gap=d[i], best=rec['entries'][i])


def confirmed_bound(pf, frames, tetra, link, runways=HO.RUNWAYS, **kw):
    """`handoff.endpoint`'s bound with the gap CONFIRMED: ``frames + gap / WALK_CAP + cut_step``.

    ``inf`` when nothing confirms -- which is the honest value, not a missing one."""
    c = confirmed(pf, tetra, link, runways=runways, **kw)
    return (float('inf') if not c['n']
            else frames + c['gap'] / HO.WALK_CAP + pf.cut_step), c


def best_confirmed(pf, cands, runways=HO.RUNWAYS, verbose=False, on_result=None):
    """**Branch-and-bound over candidates ranked by an admissible under-estimate.**

    ``cands`` are dicts carrying ``frames``, ``tetra``, ``link`` and ``bound_lo`` (the roots bound --
    `handoff.endpoint(roots=True)`'s, which cannot exceed the confirmed one). Scans ascending, confirms
    each, and stops when ``bound_lo`` of the next candidate is already >= the best confirmed bound: no
    remaining candidate can beat it, because its true bound is at least its ``bound_lo``.

    Returns ``(best, scanned)`` -- ``best`` None if nothing in the population confirms at all, which is
    a measurement over that population and not a claim about the geometry
    (`[[infeasible-needs-proof]]`)."""
    order = sorted(cands, key=lambda c: c['bound_lo'])
    best, scanned = None, 0
    for c in order:
        if best is not None and c['bound_lo'] >= best['bound']:
            if verbose:
                print('  STOP: next lower bound %.2f >= best confirmed %.2f -- nothing left can win'
                      % (c['bound_lo'], best['bound']))
            break
        b, rec = confirmed_bound(pf, c['frames'], c['tetra'], c['link'], runways=runways)
        scanned += 1
        if verbose:
            print('  %-22s lo %7.2f -> %s (%d confirmed)'
                  % (c.get('label', '?'), c['bound_lo'],
                     ('%.2f' % b) if rec['n'] else 'NO GENUINE ENTRY', rec['n']))
        if on_result is not None:
            on_result(c, b, rec)
        if rec['n'] and (best is None or b < best['bound']):
            best = dict(c, bound=b, confirmed=rec)
    return best, scanned
