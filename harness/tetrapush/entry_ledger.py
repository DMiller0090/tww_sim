"""A PASS IS PRICED AGAINST THE DRAWS ALREADY HELD, NOT AGAINST ITSELF (session 97).

`entry_score.dedupe_near` made a pass's own count honest, and `entry_camera.summarize` made a
CAMERA pass's count honest across the cameras inside it. Both stop at the pass boundary, and that is
the last place this search could still count copies as discoveries -- the fourth level of the same
mistake `entry_score`'s header lists three of.

MEASURED, on session 96's own two probes, and it inverts that session's ranking:

| shape (cell 2553, thrust 15)      | draws | NEW vs the 196-cloud pass | seconds | reported | **new/s** |
|-----------------------------------|-------|---------------------------|---------|----------|-----------|
| camera neighbourhood, +-8 stride 2 |   31 |     **6** (19%)           |    245  | 0.127/s  | **0.0245**|
| camera x paying shape (densify)    |   40 |    **29** (73%)           |    881  | 0.045/s  | **0.0329**|
| whole walk:16 alphabet, marginal   |  127 |     by construction all   |   1462  | 0.087/s  | **0.031** |
| same paying shape, 78 BAM away     |   40 |    **10** (25%)           |    861  | 0.046/s  | **0.0116**|
| same paying shape, 344 BAM away    |   40 |    **31** (78%)           |    871  | 0.046/s  | **0.0356**|

Session 96 ranked the first three 0.127 > 0.087 > 0.045 and told the next session to buy the first and
skip the second. In the currency E[hits] is actually additive in, the order is REVERSED and the three are
within 35% of each other: a local neighbourhood is enriched in draws because it is enriched in the
PARENT'S draws. 25 of its 31 are ticket stubs already in the drawer.

Rows four and five are the same lesson one level in, and then the rule out of it. Having ranked the paying
shape first at 0.0329, buying it at a SECOND camera pays 0.0116 -- because the 29 of 40 was that shape's
first pass on this scope, so it measured density against the bounded passes and not one camera against
another. **A shape's first pass over-reports the shape exactly as a ledger's first pass over-reports the
axis** (`price` refuses to quote the latter; the former is on the reader).

And what separates 0.0116 from 0.0356 on an identical shape and clock is DISTANCE from the cameras already
bought -- 19% new at tens of BAM, 25% at 78, 78% at 344. So spread the buys and rank candidates by their
distance from the ledger, not by their own prior yield, which here ranked the 25% camera above the 78% one
(`knowledge/strategy/clip-draw-ledger.md`).

WHY THE DISTINCTION IS NOT PEDANTIC. E[hits] is a sum over draws (`entry_score.lottery`), so it is
additive only over draws nothing else has already contributed. Price a second pass on its own
population and the two E[hits] cannot be added -- which is precisely the sum `summarize` warns about
one level down (`expected_hits_pooled`) and then commits one level up.

    python -m harness.tetrapush.entry_ledger price <pass.json> [<pass.json> ...]
    python -m harness.tetrapush.entry_ledger saturate <pass.json> [trials]
    python -m harness.tetrapush.entry_ledger uniform <pass.json>
"""
import json
import os
import random
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import entry_score as SC


def near_rows(obj):
    """``[(gap, ident)]`` out of whatever a pass was saved as -- a pass dict, a list of them, or the
    file a CLI wrote (``{'passes': [...]}``).

    A saved pass keeps its near-misses in ``near_detail`` with the gap INSIDE the row, while
    `stream_search` returns them as pairs; every consumer of this module wants the pair form, so the
    conversion lives here once instead of in each probe (three `_notes/s96_*` scripts each had it)."""
    if isinstance(obj, str):
        obj = json.load(open(obj))
    if isinstance(obj, dict):
        obj = obj.get('passes', [obj])
    out = []
    for p in obj:
        for nd in p.get('near_detail', []):
            out.append((nd['gap'], {k: v for k, v in nd.items() if k != 'gap'}))
    return out


def pass_seconds(obj):
    """The WALL clock a saved pass spent -- per-camera ``wall_seconds`` where a pass has them, and the
    summary otherwise, because that is where a probe that aggregated its own passes put it.

    Read from the file rather than re-timed: a pass costs 8 to 900 seconds and the whole point of the
    ledger is that a rate is draws over the clock somebody already paid."""
    if isinstance(obj, str):
        obj = json.load(open(obj))
    passes = obj.get('passes', []) if isinstance(obj, dict) else list(obj)
    secs = sum(p.get('wall_seconds') or p.get('seconds') or 0.0 for p in passes)
    if not secs and isinstance(obj, dict):
        secs = (obj.get('summary') or {}).get('seconds') or obj.get('seconds') or 0.0
    return float(secs)


def draw_ids(near):
    """The DRAW identities in a near-miss population -- `entry_score.draw_key`, as a set.

    The key is the walk endpoint, the entry lean, the momentum and the configuration: everything the
    delivered input decides. Two passes that reach one endpoint from different C-stick paths hold the
    same ticket, and that is the whole point of keying on it rather than on the input."""
    return {SC.draw_key(i) for _g, i in near}


def novel(near, held):
    """The rows of ``near`` whose draw is NOT already in ``held`` -- deduped among themselves too."""
    best = {}
    for g, i in near:
        k = SC.draw_key(i)
        if k in held:
            continue
        if k not in best or g < best[k][0]:
            best[k] = (g, i)
    return list(best.values())


class Ledger:
    """The cumulative draw population, and the only place a pass's yield can honestly be read.

    Add passes in the order they were RUN. Each `add` reports what that pass contributed on top of
    everything before it, so a session's passes sum -- and a pass that re-draws the drawer reports the
    zero it earned rather than the population it re-measured.

    ``near_gap`` is the window `lottery` prices against and it must be the one the passes were scored
    at: E[hits] is ``width / (2 * near_gap)`` per draw, so a ledger mixing two windows is comparing
    probabilities of different events."""

    def __init__(self, near_gap=SC.BAND_PROBE):
        self.near_gap = float(near_gap)
        self.seen = set()
        self.held = []
        self.rows = []

    def add(self, label, obj, seconds=None):
        """Price one pass against the ledger, absorb it, and return its row."""
        if isinstance(obj, str):
            obj = json.load(open(obj))
        near = near_rows(obj)
        fresh = novel(near, self.seen)
        ded = SC.dedupe_near(near)
        if seconds is None:
            seconds = pass_seconds(obj)
        against = len(self.seen)
        self.seen |= draw_ids(fresh)
        self.held += fresh
        # the FIRST pass in a ledger is 100% new by construction and its rate is not a rate anything
        # can be bought at -- flagged so a budget cannot quote it (it is how session 96 got 0.157)
        row = dict(label=label, against=against, n_draws=len(ded), n_new=len(fresh),
                   new_share=(len(fresh) / float(len(ded)) if ded else 0.0),
                   seconds=float(seconds),
                   reported_per_second=(len(ded) / seconds if seconds else 0.0),
                   new_per_second=(len(fresh) / seconds if seconds else 0.0),
                   new_expected_hits=SC.lottery(fresh, self.near_gap),
                   total_draws=len(self.seen),
                   total_expected_hits=SC.lottery(self.held, self.near_gap))
        self.rows.append(row)
        return row

    def price(self):
        """The ledger as a table plus the union totals -- what a handoff should quote.

        ``marginal_per_second`` is the rate a NEXT pass can be budgeted at, and it deliberately
        ignores the ledger's opening pass: that one is 100% new because nothing preceded it, so its
        rate describes the axis's first visit and not the price of another one."""
        later = [r for r in self.rows if r['against'] and r['seconds']]
        return dict(near_gap=self.near_gap, rows=list(self.rows), total_draws=len(self.seen),
                    total_expected_hits=SC.lottery(self.held, self.near_gap),
                    seconds=sum(r['seconds'] for r in self.rows),
                    marginal_per_second=(max(r['new_per_second'] for r in later) if later else None),
                    best_gap=min([g for g, _i in self.held] or [None]))

    def draws_for(self, expected_hits):
        """How many MORE draws E[hits] ``expected_hits`` needs, at this ledger's measured per-draw rate.

        The per-draw rate is not a constant of the axis, it is the mean band width of the draws seen
        so far over the window -- so this is an extrapolation and reads as one. It is still the number
        a budget decision needs: with the widths pinned (`entry_lean`), it moves by a few percent."""
        if not self.held:
            return None
        per = SC.lottery(self.held, self.near_gap) / float(len(self.held))
        return max(0.0, (float(expected_hits) - SC.lottery(self.held, self.near_gap)) / per)


def accumulation(passes, trials=40, seed=0, ordered=False):
    """Is the axis SATURATING? The distinct-draw count against the number of cameras spent.

    Averaged over random orderings of the cameras, because a single ordering measures the order and
    not the axis (a fan is enumerated x-major, so its own sequence is not a random sample -- the same
    caveat `entry_score._marginal` carries). ``ordered=True`` keeps the file's order, which is what to
    use when the passes really were a time series.

    The shape of the answer is the verdict. Measured on session 96's 196-cloud walk:16 pass, the
    marginal yield falls **4.08 draws per camera at the first to 0.23 over the last quarter** -- a
    coupon-collector curve, i.e. the cameras are sampling a population far smaller than their count.
    An axis with independent draws per camera would hold that rate flat."""
    sets = [draw_ids(near_rows([p])) for p in (passes.get('passes', [passes])
                                              if isinstance(passes, dict) else passes)]
    n = len(sets)
    curve = [0.0] * (n + 1)
    orders = ([list(range(n))] if ordered else None)
    if orders is None:
        rng = random.Random(seed)
        orders = []
        for _ in range(int(trials)):
            o = list(range(n))
            rng.shuffle(o)
            orders.append(o)
    for o in orders:
        got = set()
        for i, idx in enumerate(o, 1):
            got |= sets[idx]
            curve[i] += len(got)
    for i in range(1, n + 1):
        curve[i] /= float(len(orders))
    quarter = max(1, n // 4)
    return dict(n_cameras=n, curve=curve, total=curve[n] if n else 0.0,
                per_camera=(curve[n] / n if n else 0.0),
                first=curve[1] if n else 0.0,
                marginal_last_quarter=((curve[n] - curve[n - quarter]) / quarter if n else 0.0))


#: Thresholds the uniformity check reads the population at -- three decades below the window, which is
#: where a band actually sits (`MIN_BAND` .. ~3e-5 measured).
UNIFORM_AT = (1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3)


def uniformity(near, near_gap=SC.BAND_PROBE, at=UNIFORM_AT):
    """Does `lottery`'s premise hold? Observed draws under each gap against the uniform expectation.

    `lottery` prices a draw at ``width / (2 * near_gap)`` because its residual is taken to be locally
    uniform across the window. That is an ASSUMPTION and the population can test it for free: if draws
    crowded toward zero the estimate would be low, and if they avoided it the estimate would be a
    fiction. Measured on the 127-draw walk:16 population the ratio is **1.00 to 1.18 from 3e-3 down to
    1e-4**, so the model stands as written.

    It also settles what a record approach is worth. The single best draw sits at 3.9x the expectation
    at 1e-5, which is what one order statistic out of 127 uniform draws looks like ~10% of the time --
    the distributional form of session 96's "a record is not a trend"."""
    ded = SC.dedupe_near(near)
    n = len(ded)
    gaps = sorted(g for g, _i in ded)
    rows = []
    for t in at:
        exp = n * float(t) / float(near_gap)
        obs = sum(1 for g in gaps if g < t)
        rows.append(dict(under=float(t), observed=obs, expected=exp,
                         ratio=(obs / exp if exp else None)))
    return dict(n_draws=n, near_gap=float(near_gap), rows=rows,
                best_gap=(gaps[0] if gaps else None))


# ------------------------------------------------------------------ making the measurement tracked

#: The locked extract every gate reads: the pass populations reduced to what `draw_key`, `lottery` and
#: `accumulation` consume, since a pass's own output lands in the gitignored `_generated/`.
EXTRACT = os.path.join(_rb, 'fixtures', 'courtyard_draw_ledger_s97.json')

#: What a draw row has to carry for the ledger to recompute everything from the extract alone.
IDENT_FIELDS = ('walk', 'm351C', 'facing', 'thrust', 'nspeed', 'width')


def extract(sources, path=EXTRACT, note=None):
    """Reduce saved passes to the tracked form -- ``{'sources': [...], 'rows': [...]}``, and write it.

    ``sources`` is ``[(label, path)]`` in RUN order, because the ledger's whole content is the order.
    Each row keeps its camera so `accumulation` can still group by one, and its width so `lottery` can
    still price it; nothing else about a candidate is needed to re-derive a single number on this page."""
    out, srcs = [], []
    for label, p in sources:
        d = json.load(open(p))
        passes = d.get('passes', [d])
        n = 0
        for pss in passes:
            cam = ','.join(str(b) for b in pss.get('substickX', []))
            for nd in pss.get('near_detail', []):
                row = dict(source=label, camera=cam, gap=nd['gap'])
                row.update({k: nd[k] for k in IDENT_FIELDS})
                out.append(row)
                n += 1
        srcs.append(dict(label=label, file=os.path.basename(p), seconds=pass_seconds(d),
                         n_cameras=len(passes), n_reported=n))
    doc = dict(source='harness/tetrapush/entry_ledger.extract, session 97',
               note=note or ("The near-miss populations of the session 95/96 cell-2553 passes, in run"
                             " order, reduced to what a draw IS (`entry_score.draw_key`) plus the band"
                             " width `lottery` prices it at. Pinned because the passes themselves are"
                             " written under the gitignored `_generated/`, so the session-97 finding"
                             " -- that a local camera neighbourhood re-draws the parent pass -- could"
                             " not otherwise be re-run from a clone."),
               near_gap=SC.BAND_PROBE, sources=srcs, rows=out)
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(doc, open(path, 'w'), indent=1)
    return doc


def from_extract(path=EXTRACT, label=None):
    """``[(gap, ident)]`` out of the locked extract -- one source's rows, or all of them."""
    d = json.load(open(path)) if isinstance(path, str) else path
    return [(r['gap'], r) for r in d['rows'] if label is None or r['source'] == label]


def extract_cameras(path=EXTRACT, label=None):
    """The extract's rows regrouped as per-camera pass stubs, for `accumulation`."""
    by = {}
    for g, r in from_extract(path, label):
        by.setdefault(r['camera'], []).append(dict(r, gap=g))
    return [dict(substickX=k, near_detail=v) for k, v in sorted(by.items())]


def ledger_of(path=EXTRACT):
    """The extract priced as a `Ledger`, its sources absorbed in RUN order -- the tracked measurement.

    This is the whole session-97 result in one call, and the order is load-bearing: the neighbourhood
    was run after the pass whose draws it re-drew, so pricing it second is what makes its 6-of-31 read
    as the buy it was rather than as a population."""
    d = json.load(open(path)) if isinstance(path, str) else path
    led = Ledger(d.get('near_gap', SC.BAND_PROBE))
    for s in d['sources']:
        led.add(s['label'], [dict(near_detail=[dict(r, gap=r['gap'])
                                              for _g, r in from_extract(d, s['label'])])],
                seconds=s['seconds'])
    return led


# --------------------------------------------------------------------------- CLI

def _cmd_price(argv):
    """``price`` with no argument prices the LOCKED extract; with paths, those passes in that order."""
    paths = argv or [EXTRACT]
    if len(paths) == 1 and 'sources' in json.load(open(paths[0])):
        led = ledger_of(paths[0])
    else:
        led = Ledger()
        for path in paths:
            led.add(os.path.basename(path), path)
    for r in led.rows:
        print("%-44s %4d draws, %4d NEW (%3.0f%%), %6.0f s -> reported %.4f/s, NEW %.4f/s,"
              " E[hits] +%.4f (union %.4f over %d draws)"
              % (r['label'], r['n_draws'], r['n_new'], 100 * r['new_share'], r['seconds'],
                 r['reported_per_second'], r['new_per_second'], r['new_expected_hits'],
                 r['total_expected_hits'], r['total_draws']))
    p = led.price()
    print("\nUNION: %d draws, E[hits] %.4f, %.0f s, best gap %s"
          % (p['total_draws'], p['total_expected_hits'], p['seconds'],
             '%.4e' % p['best_gap'] if p['best_gap'] is not None else 'none'))
    need = led.draws_for(1.0)
    rate = p['marginal_per_second']
    if need and rate:
        print("E[hits] 1 needs %.0f more draws -- %.1f h at the best MARGINAL rate (%.4f/s, the"
              " opening pass's %.4f/s is not one)"
              % (need, need / rate / 3600.0, rate, p['rows'][0]['new_per_second']))
    elif need:
        print("E[hits] 1 needs %.0f more draws; no pass here was priced against a non-empty ledger,"
              " so there is no marginal rate to budget at" % need)


def _cmd_saturate(argv):
    path = argv[0] if argv else EXTRACT
    d = json.load(open(path))
    d = extract_cameras(d, 'walk16') if 'sources' in d else d
    a = accumulation(d, trials=int(argv[1]) if len(argv) > 1 else 40)
    print("%d cameras -> %.1f distinct draws (%.3f per camera)"
          % (a['n_cameras'], a['total'], a['per_camera']))
    for n in (1, 5, 10, 20, 50, 100, a['n_cameras']):
        if n <= a['n_cameras']:
            print("   %4d cameras -> %7.1f draws (%.3f per camera)"
                  % (n, a['curve'][n], a['curve'][n] / n))
    print("first camera %.2f draws, marginal over the last quarter %.3f -- %.1fx decay"
          % (a['first'], a['marginal_last_quarter'],
             a['first'] / a['marginal_last_quarter'] if a['marginal_last_quarter'] else float('inf')))


def _cmd_uniform(argv):
    path = argv[0] if argv else EXTRACT
    d = json.load(open(path))
    u = uniformity(from_extract(d, 'walk16') if 'sources' in d else near_rows(d))
    print("%d draws, window %.0e, best gap %.4e" % (u['n_draws'], u['near_gap'], u['best_gap']))
    for r in u['rows']:
        print("   gap < %8.1e: observed %4d, uniform expects %7.2f, ratio %s"
              % (r['under'], r['observed'], r['expected'],
                 '%.2f' % r['ratio'] if r['ratio'] else '-'))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'price'
    if cmd == 'price':
        _cmd_price(argv)
    elif cmd == 'saturate':
        _cmd_saturate(argv)
    elif cmd == 'uniform':
        _cmd_uniform(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
