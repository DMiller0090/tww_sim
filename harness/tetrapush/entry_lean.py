"""The entry LEAN as an axis of the frame-floor pass: which leans a fan arrives on, with what candidate
mass, and what acceptance band each (configuration, lean) really has.

WHY THIS IS A MODULE AND NOT A SCRATCH SCRIPT. The band is a jagged function of the entry lean
(`entry_score.BandTable`) and the qualification runs at lean 0, so every statement of the form "this
cell has no usable width" is a statement about SOME lean until the leans a plan actually arrives on are
enumerated. Session 93 made exactly that statement about cell 2553 -- 180 candidates inside
`BAND_PROBE`, none converted, "every one at a lean whose band has no usable width" -- and it was wrong
in a way no amount of extra density would have exposed: the widths it read came from a table that
Newtoned every band from ONE station, so cell 2553 / thrust 15 read 0 of its 24 heaviest fan leans
usable where the ladder reads 20. The measurement that settles it is cheap (a census plus one band per
(configuration, lean)) and it has to be repeatable, so it lives here with a locked fixture.

Three things it answers, and they are different questions:
  * `census` -- the leans a bounded fan REACHES and the candidate mass each carries. Mass, not
    presence: the delivered console clip converted at a lean whose band width is 0.0, purely because
    ~287 k candidates landed on it.
  * `bands_at` -- the band per (cell, thrust, lean) off `BandTable`'s ladder, so a "no width" reading is
    a property of the configuration and not of one Newton seed.
  * `select_by_lean` -- a stream scope, for aiming a pass at (lean, cell) pairs. A COST knob only, and a
    weak one on a frame-floor pass: the FAN generation dominates it (`census` reports the fan-only
    seconds for exactly the shape a pass runs, against that pass's own total), and a lean filter runs
    downstream of the stepping, so it saves evaluation and not wall clock. It earns its keep when the
    configuration count is large, since evaluation is per candidate per configuration -- and it is NEVER
    a claim that the leans it drops cannot pay, since the delivered clip's own lean has zero width.

usage:
    python -m harness.tetrapush.entry_lean census [frames]
    python -m harness.tetrapush.entry_lean bands  [cells] [topN]      # + writes the fixture
    python -m harness.tetrapush.entry_lean rank   [cells]
"""
import json
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
# <<< repo bootstrap

from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_score as SC
from harness.tetrapush import entry_search as ES

LEAN_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_lean_bands_s94.json')

#: The frame-floor pass shape the census is taken at -- session 93's own `search2 4 2 1 2 2 frames=4`.
#: The mass distribution is a property of the FAN, so a census has to name the fan it came from.
DEFAULT_FAN = dict(base_frames=(0, 1), s1_stride=4, j1=(2,), s2_stride=1, j2max=2)
#: The delivered console clip's roll, read off `fixtures/courtyard_clip_s90_console.json`: cell 2552,
#: thrust 15, lean 64761. The reference every claim here has to survive contact with.
DELIVERED = (2552, 15, 64761)


def census(fankw=None, max_frames=ES.REACH_FRAMES, seed=None, env=None):
    """The entry leans a fan of ``<= max_frames`` plans reaches, and the candidate mass on each.

    The lean is `lean_at_roll(m351C)` at the walk endpoint -- the walk's own turn history, so it is an
    OUTPUT of a plan and never an input. That is why this is a census and not a sweep."""
    kw = dict(DEFAULT_FAN if fankw is None else fankw)
    hist = {}
    n = 0
    t0 = time.time()
    for key, plan in EF.iter_fan2(seed=seed, env=env, **kw):
        if EF.plan_frames(plan) > max_frames:
            continue
        n += 1
        lean = ES.lean_at_roll(key[2])
        hist[lean] = hist.get(lean, 0) + 1
    return dict(fan={k: list(v) if isinstance(v, tuple) else v for k, v in kw.items()},
                max_frames=int(max_frames), n_candidates=n, n_leans=len(hist), hist=hist,
                seconds=time.time() - t0)


def heaviest(cen, topn=None):
    """The census' leans, heaviest first."""
    top = sorted(cen['hist'].items(), key=lambda kv: -kv[1])
    return [(int(l), int(n)) for l, n in (top if topn is None else top[:topn])]


def bands_at(quals, leans, seed=None, table=None, progress=False):
    """One band per (configuration, lean), off `BandTable`'s ladder.

    ``usable`` is the width filter `stream_search` ranks with (`MIN_BAND`), and it is reported beside
    ``productive`` rather than instead of it because they license different things: not-productive means
    the ladder found no genuine dust on that locus at that lean, while productive-and-zero-width means
    the target is a single f32 -- long odds, and exactly what the console clip was won at."""
    seed = seed or ES.console_seed()
    tab = table if table is not None else SC.BandTable(seed, quals=quals)
    rows = []
    for q in sorted(quals, key=lambda q: (ES.aim_cell(q['facing']), q['thrust'])):
        fac, thr = int(q['facing']) & 0xFFFF, int(q['thrust'])
        for lean, mass in leans:
            t0 = time.time()
            b = tab.get(fac, thr, lean)
            rows.append(dict(cell=ES.aim_cell(fac), facing=fac, thrust=thr, lean=int(lean),
                             mass=int(mass), productive=bool(b['productive']), width=b['width'],
                             usable=bool(b['productive'] and b['width'] >= SC.MIN_BAND),
                             n_genuine=b['n_genuine'], entry=b['entry'], seed=b.get('seed'),
                             escalated=bool(b.get('escalated')), reason=b['reason'],
                             seconds=time.time() - t0))
            if progress:
                r = rows[-1]
                print("  cell %4d thr %2d lean %5d: %-10s width %.4e mass %7d seed %-9s [%.0fs]"
                      % (r['cell'], r['thrust'], r['lean'],
                         'usable' if r['usable'] else ('zero-width' if r['productive'] else 'barren'),
                         r['width'], r['mass'], r['seed'], r['seconds']))
    return rows


def rank(rows):
    """(lean, cell) pairs a pass could pay at, by width x mass -- usable ones first.

    Width x mass is the pass's own expectation up to a constant: `lottery` prices each near-miss at
    ``width / (2 * near_gap)`` and the mass is how many draws that lean will contribute. It ranks; it
    does not filter (see the module docstring)."""
    return sorted((r for r in rows if r['mass']),
                  key=lambda r: (not r['usable'], -(r['width'] * r['mass'])))


def parse_lean_spec(spec, fixture=None):
    """A pass's lean scope, from a spec string. Comma-separated mix of:
    ``65281`` a lean; ``top8`` the N heaviest in the fixture's census; ``paying`` every lean with a
    usable band at any configuration in the fixture; ``paying:2553`` at that cell.

    The named forms resolve out of `LEAN_FIXTURE`, so a re-measure moves every selector with it."""
    fx = fixture or load()
    cen = fx['census']
    out = set()
    for item in str(spec).replace(' ', '').split(','):
        if not item:
            continue
        if item.startswith('top'):
            out |= {l for l, _n in heaviest(cen, int(item[3:]))}
        elif item.startswith('paying'):
            cell = int(item.split(':', 1)[1]) if ':' in item else None
            out |= {int(r['lean']) for r in fx['rows']
                    if r['usable'] and (cell is None or int(r['cell']) == cell)}
        else:
            out.add(int(item) & 0xFFFF)
    return tuple(sorted(out))


def select_by_lean(pairs, leans=None):
    """A fan stream with candidates whose ENTRY lean is outside ``leans`` dropped.

    Order-preserving, so a family-major stream stays family-major and `stream_search`'s
    ``dedup_scope='family'`` still bounds memory at one family -- the same contract as
    `entry_fan.capped`."""
    if not leans:
        return pairs
    want = frozenset(int(l) & 0xFFFF for l in leans)
    return ((k, p) for k, p in pairs if ES.lean_at_roll(k[2]) in want)


def load(path=LEAN_FIXTURE):
    """The locked measurement: the census, the per-(configuration, lean) bands, and the delivered
    clip's own row."""
    return json.load(open(path))


def measure(cells='2553,2551,2552', topn=24, fankw=None, max_frames=ES.REACH_FRAMES, seed=None,
            path=LEAN_FIXTURE, progress=True):
    """Census + bands + the delivered row, written to the fixture."""
    seed = seed or ES.console_seed()
    quals = SC.select_quals(SC.qualified(seed), cells=EF.parse_cell_spec(cells))
    cen = census(fankw, max_frames, seed=seed)
    leans = heaviest(cen, topn)
    for extra in (DELIVERED[2], 0):                 # the console lean, and the qualification's own
        if not any(l == extra for l, _n in leans):
            leans.append((extra, cen['hist'].get(extra, cen['hist'].get(str(extra), 0))))
    if progress:
        print("census: %d candidates, %d distinct entry leans at %s frames<=%d  [%.0fs]"
              % (cen['n_candidates'], cen['n_leans'], cen['fan'], cen['max_frames'],
                 cen['seconds']))
        print("  the %d heaviest: %s" % (topn, leans[:topn]))
    rows = bands_at(quals, leans, seed=seed, progress=progress)
    fx = dict(source='harness/tetrapush/entry_lean.py measure',
              note=('the entry lean as a search axis: the leans a frame-floor fan reaches, the mass on'
                    ' each, and the band per (configuration, lean) off BandTable\'s ladder'),
              cells=cells, topn=int(topn), delivered=list(DELIVERED),
              census=dict(cen, hist={str(k): v for k, v in cen['hist'].items()}), rows=rows)
    if path:
        json.dump(fx, open(path, 'w'), indent=1)
        print("wrote %s" % path)
    return fx


def _cmd_census(argv):
    frames = int(argv[0]) if argv else ES.REACH_FRAMES
    cen = census(max_frames=frames)
    print("census at %s, frames<=%d: %d candidates, %d distinct entry leans  [%.0fs]"
          % (cen['fan'], cen['max_frames'], cen['n_candidates'], cen['n_leans'], cen['seconds']))
    for l, n in heaviest(cen, 24):
        print("  lean %5d: %7d candidates" % (l, n))


def _cmd_bands(argv):
    cells = argv[0] if argv else '2553,2551,2552'
    topn = int(argv[1]) if len(argv) > 1 else 24
    fx = measure(cells=cells, topn=topn)
    _print_rank(fx['rows'])


def _cmd_rank(argv):
    fx = load()
    rows = fx['rows']
    if argv:
        want = set(EF.parse_cell_spec(argv[0]))
        rows = [r for r in rows if int(r['cell']) in want]
    _print_rank(rows)


def _print_rank(rows):
    top = rank(rows)
    print("\n(lean, cell) pairs by width x mass -- usable-width first:")
    for r in top[:24]:
        print("  cell %4d thr %2d lean %5d  width %.4e  mass %7d  -> %.3e  %s"
              % (r['cell'], r['thrust'], r['lean'], r['width'], r['mass'],
                 r['width'] * r['mass'], '' if r['usable'] else '(not usable)'))
    d = [r for r in rows if (r['cell'], r['thrust'], r['lean']) == DELIVERED]
    if d:
        r = d[0]
        print("\nthe DELIVERED console clip's own row: cell %d thr %d lean %d -> productive %s,"
              " width %.4e, usable %s  (%r)"
              % (r['cell'], r['thrust'], r['lean'], r['productive'], r['width'], r['usable'],
                 r['seed']))


def main(argv=None):
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'rank'
    if cmd == 'census':
        _cmd_census(argv)
    elif cmd == 'bands':
        _cmd_bands(argv)
    elif cmd == 'rank':
        _cmd_rank(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
