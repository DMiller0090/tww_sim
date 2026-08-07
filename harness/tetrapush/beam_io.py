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


def split_last_roll(env, node, *, verify=True):
    """**A terminal node re-opened as its PRE-ROLL endpoint plus the roll that made it** (session 116).

    `away_walk.snap_reach` and every other camera question take a node BEFORE its roll and the aim --
    the whole point is that they re-fire it -- while a beam holds only terminals. Reconstructing that
    by hand is where a session loses an afternoon: the split index is not in the record, and a split
    one frame off measures a different roll and says so nowhere.

    The index IS recoverable, exactly, from the log: `two_roll.roll_stream` puts k=0 at the A-press
    delivery and holds A for ``a_hold`` frames, so the LAST contiguous A-run in the log starts the last
    roll segment. The knobs come from the node's own ``plan`` tail (``aim``/``l_window``/``target_cs``).

    ``verify`` (the default, and the reason to use this instead of an inline split) re-fires the roll
    from the reconstructed endpoint and asserts the delivered stream is byte-identical to the log tail
    and the state 0-ULP against the node's own ``run`` -- so a caller measuring the camera at this
    endpoint knows it is measuring THIS node's roll (`[[zero-ulp-tests-only]]`).

    Returns ``dict(pre, aim, l_window, target_cs, split, roll_frames)``; ``pre`` is a node dict in
    `full_herd.roll_probe`'s shape (``run``/``frames``/``jf``/``log``)."""
    from harness.tetrapush import search as S
    from harness.tetrapush import two_roll as T
    log, plan = list(node['log']), list(node.get('plan') or [])
    if not plan:
        raise ValueError('node carries no plan: the roll knobs are not recoverable from the log')
    a = [k for k, d in enumerate(log) if int(d.get('buttons', 0)) & S.PAD_A]
    if not a:
        raise ValueError('node log holds no A-press: it ends in no roll')
    st = a[-1]
    while st - 1 in a:
        st -= 1
    p = plan[-1]
    aim, lw, tcs = tuple(p['aim']), tuple(p['l_window']), int(p['target_cs'])
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    for d in log[:st]:
        run.step(d)
    pre = dict(run=run, frames=st, jf=int(p.get('jframes', 0)), log=log[:st])
    if verify:
        rr, out = run.clone(), []
        seg = T.roll_segment(rr, aim, target_cs=tcs, l_window=lw, log=out)
        if [dict(d) for d in out] != [dict(d) for d in log[st:]]:
            raise AssertionError('re-fired roll is not the logged one (split %d)' % st)
        ref = node['run']
        got = (rr.link.pos_x, rr.link.pos_z, rr.link.speedF, int(rr.link.facing),
               int(rr.link.travel), int(rr.csangle), rr.tx, rr.tz, rr.link.state)
        want = (ref.link.pos_x, ref.link.pos_z, ref.link.speedF, int(ref.link.facing),
                int(ref.link.travel), int(ref.csangle), ref.tx, ref.tz, ref.link.state)
        if got != want:
            raise AssertionError('re-fired terminal is not 0-ULP (split %d)' % st)
        return dict(pre=pre, aim=aim, l_window=lw, target_cs=tcs, split=st,
                    roll_frames=int(seg['frames']))
    return dict(pre=pre, aim=aim, l_window=lw, target_cs=tcs, split=st,
                roll_frames=len(log) - st)


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
