# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""Dump a search beam to JSON and rebuild it BIT-EXACT -- the cheap-iteration path (session 61).

A chained cycle costs ~475 s, so every session that wanted to work on cycle N has re-run cycles
1..N-1 to get there, and session 61 spent ~25 minutes of search finding a one-expression bug that way.
There is no need: **a node's identity IS its delivered input log.** `full_herd.confirm_plan` already
rests on that -- replay a node's own log on a fresh self-contained `FreeRun` and every field comes back
bit-identical -- so a beam round-trips through plain JSON with no simulator state to serialise, and a
rebuilt beam is a legitimate starting point for `extend_cycle` / `terminal_targeting`, not an
approximation of one.

Rebuilding is ~0.3 ms per logged frame (a 46-frame node ~15 ms), i.e. a whole beam in well under a
second against the ~475 s it replaces. Gated by `tests/test_full_herd.py::
test_a_dumped_beam_rebuilds_bit_exact_from_its_input_logs`.

Pure stdlib, no Dolphin.
"""
import json

from harness.tetrapush import seeds
from harness.tetrapush import two_roll as T


def beam_record(nodes, hl, placements=None):
    """The serialisable form of a beam: each node's input log plus the metrics worth eyeballing in the
    file (they are DERIVED -- the log is the source of truth, and `rebuild_beam` recomputes them)."""
    from harness.tetrapush import full_herd as F
    from harness.tetrapush import objective as O
    rows = placements if placements is not None else seeds.load_placements()[0]
    out = []
    for n in nodes:
        pd = F._placement_dist(n['run'], rows)
        out.append(dict(log=list(n['log']), frames=n['frames'], plan=n.get('plan', []),
                        per_frame=n['m']['per_frame'] if 'm' in n else None,
                        placement_dist=pd, bound=O.plan_bound(n['frames'], pd),
                        lat=hl.lateral(n['run'].tx, n['run'].tz)))
    return out


def dump_beams(path, beams, hl, placements=None):
    """Write every cycle's beam to ``path`` (``{"cycles": [[node, ...], ...]}``)."""
    rec = dict(cycles=[beam_record(b, hl, placements) for b in beams])
    with open(path, 'w') as fh:
        json.dump(rec, fh)
    return rec


def load_beams(path):
    with open(path) as fh:
        return json.load(fh)


def rebuild_beam(env, rec, cycle=-1, hl=None):
    """Rebuild one dumped cycle's nodes as live search nodes, by replaying each log on a fresh
    `FreeRun`. ``cycle`` is 1-based (``-1`` = the last dumped cycle).

    The returned dicts carry ``run``/``log``/``frames``/``plan``/``m`` -- what `extend_cycle`,
    `terminal_targeting` and `confirm_plan` consume -- plus ``dumped`` (the recorded metrics), so a
    caller can assert the rebuild against them rather than trusting it."""
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(env) if hl is None else hl
    dtm = seeds.dtm_input_at(env)
    beam = rec['cycles'][cycle if cycle < 0 else cycle - 1]
    out = []
    for nd in beam:
        run = seeds.make_freerun(env)
        run.pre_seed_input(dtm(0))
        for d in nd['log']:
            run.step(d)
        out.append(dict(run=run, log=list(nd['log']), frames=nd['frames'],
                        plan=nd.get('plan', []), m=T.metrics(run, hl, nd['frames']), dumped=nd))
    return out
