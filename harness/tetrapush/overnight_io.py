"""**THE OVERNIGHT RUN'S CHECKPOINT LAYER** -- progressive, crash-safe, resumable, and readable
mid-run.

A search that reports only at the end is a search you lose at hour 7 (session 149's own port agent was
killed mid-work and survived only because it had committed). So every fact this run produces is on disk
the moment it exists, in append-only JSONL flushed per line, and the run's whole state lives in these
files rather than in a process:

  * ``config.json``      the configuration, the ITEM list in the order it will be worked, and every
                         herd DROPPED before any work with the reason -- a bounded search must say what
                         it did not look at. An item is one ``(herd, walk length)`` pair.
  * ``claims/<item>``    an ``O_EXCL`` claim file per item: the work queue, with no server. A worker
                         that dies leaves a stale claim, which `status` reports and ``steal=`` retakes.
  * ``manifest.jsonl``   one line per COMPLETED item. ``resume`` skips exactly these.
  * ``progress.jsonl``   per-item coverage: candidates, evaluations, genuine, near, and whether the
                         deadline cut it. Never a silent cap.
  * ``events-<w>.jsonl`` per-worker event stream (starts, exceptions by class, hits, confirms).
  * ``incumbent.json``   the best CONFIRMED plan, replaced atomically on improvement. This is how
                         branch-and-bound crosses processes: a worker re-reads it before each item.
  * ``plans/``           every accepted plan in full, log included, so a delivery needs no re-search.

Nothing here knows what a Tetra is; `overnight.py` owns the search.
"""
import json
import os
import time

#: JSONL is flushed per line, so a reader mid-run sees whole lines and a killed run keeps everything.
_ENC = 'utf-8'


def run_dir(root, run_id):
    return os.path.join(root, '_generated', 'overnight', run_id)


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def append(path, obj):
    """One JSON object, one line, flushed. Append mode: concurrent workers write different files, and
    a line is short enough that even the same file would not tear on this platform."""
    with open(path, 'a', encoding=_ENC) as fh:
        fh.write(json.dumps(obj, default=float) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def read_jsonl(path):
    """Every parseable line. A run being READ while it is written can see a torn last line, so a bad
    line is skipped rather than raising -- the reader is a status report, not a gate."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding=_ENC) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
    return out


def write_atomic(path, obj):
    """Write-then-replace, so a reader never sees half an incumbent."""
    tmp = path + '.tmp%d' % os.getpid()
    with open(tmp, 'w', encoding=_ENC) as fh:
        json.dump(obj, fh, default=float, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path, dflt=None):
    if not os.path.exists(path):
        return dflt
    try:
        with open(path, encoding=_ENC) as fh:
            return json.load(fh)
    except ValueError:
        return dflt


# --------------------------------------------------------------------------- the work queue

def claim(d, unit, worker, steal_after=None):
    """Take item ``unit`` for this worker, or return False if someone else holds it.

    ``O_CREAT | O_EXCL`` is the whole lock: it is atomic on every filesystem this runs on, needs no
    server, and a killed worker leaves evidence rather than a held mutex. ``steal_after`` (seconds)
    retakes a claim whose heartbeat has gone quiet -- off by default, because stealing an item that is
    merely slow duplicates work."""
    ensure(os.path.join(d, 'claims'))
    p = os.path.join(d, 'claims', '%s.claim' % unit)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if steal_after is None:
            return False
        old = read_json(p, {})
        if time.time() - float(old.get('beat', old.get('t', 0)) or 0) < float(steal_after):
            return False
        write_atomic(p, dict(worker=worker, pid=os.getpid(), t=time.time(), beat=time.time(),
                             stolen_from=old.get('worker')))
        return True
    with os.fdopen(fd, 'w', encoding=_ENC) as fh:
        json.dump(dict(worker=worker, pid=os.getpid(), t=time.time(), beat=time.time()), fh)
    return True


def beat(d, unit, worker, **extra):
    """Refresh a claim's heartbeat -- what tells `status` a long item is alive rather than abandoned.

    Creates the claim directory: a single-item probe run beats without ever having claimed."""
    p = os.path.join(ensure(os.path.join(d, 'claims')), '%s.claim' % unit)
    write_atomic(p, dict(worker=worker, pid=os.getpid(), t=time.time(), beat=time.time(), **extra))


def completed(d):
    """The item ids `resume` must skip: every one with a manifest line."""
    return {r['item'] for r in read_jsonl(os.path.join(d, 'manifest.jsonl')) if 'item' in r}


def claims(d):
    out = {}
    cd = os.path.join(d, 'claims')
    if not os.path.isdir(cd):
        return out
    for name in os.listdir(cd):
        if name.endswith('.claim'):
            out[name[:-len('.claim')]] = read_json(os.path.join(cd, name), {})
    return out


# --------------------------------------------------------------------------- the incumbent

def incumbent(d, dflt_total):
    """The bound branch-and-bound cuts on: the best CONFIRMED total so far, or the banked console
    number when nothing has beaten it yet."""
    rec = read_json(os.path.join(d, 'incumbent.json'))
    if not rec or 'total' not in rec:
        return int(dflt_total), None
    return int(rec['total']), rec


def offer(d, rec):
    """Publish a plan if it beats what is on disk. Returns True when it became the incumbent.

    Last-writer-wins between processes is correct here: both writes are atomic and the record carries
    its own total, so a reader always sees a real plan and the loser is still on disk under
    ``plans/``. A plan is never DELETED by a better one."""
    p = os.path.join(d, 'incumbent.json')
    cur = read_json(p)
    if cur and int(cur.get('total', 1 << 30)) <= int(rec['total']):
        return False
    write_atomic(p, rec)
    return True


def save_plan(d, rec):
    ensure(os.path.join(d, 'plans'))
    name = 'total%03d-%s-w%d-t%d.json' % (rec['total'], rec['unit'], rec.get('walk', -1),
                                          rec.get('thrust', -1))
    write_atomic(os.path.join(d, 'plans', name), rec)
    return name


# --------------------------------------------------------------------------- the status report

def summarise(d):
    """Everything a mid-run question needs, as data. `overnight.py status` formats it."""
    cfg = read_json(os.path.join(d, 'config.json'), {})
    man = read_jsonl(os.path.join(d, 'manifest.jsonl'))
    prog = read_jsonl(os.path.join(d, 'progress.jsonl'))
    ev = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if name.startswith('events-') and name.endswith('.jsonl'):
            ev += read_jsonl(os.path.join(d, name))
    cl = claims(d)
    done = {r['item'] for r in man if 'item' in r}
    units = [u['item'] for u in cfg.get('items', [])]
    t0 = float(cfg.get('t0', 0) or 0)
    deadline = float(cfg.get('deadline', 0) or 0)
    now = time.time()
    inflight = {k: v for k, v in cl.items() if k not in done}
    tot = dict(candidates=0, evaluations=0, genuine=0, near=0, confirmed=0, deliverable=0,
               band_draws=0, fan_seconds=0.0, score_seconds=0.0)
    for r in prog:
        for k in tot:
            tot[k] += r.get(k, 0) or 0
    secs = [r['seconds'] for r in man if r.get('seconds')]
    per_unit = sum(secs) / len(secs) if secs else None
    left = [u for u in units if u not in done and u not in inflight]
    workers = int(cfg.get('workers', 1) or 1)
    eta = (per_unit * len(left) / workers) if (per_unit and left) else None
    exc = {}
    for e in ev:
        if e.get('event') == 'exception':
            exc[e.get('cls', '?')] = exc.get(e.get('cls', '?'), 0) + 1
    inc = read_json(os.path.join(d, 'incumbent.json'))
    return dict(dir=d, config=cfg, n_units=len(units), n_done=len(done), n_inflight=len(inflight),
                n_left=len(left), done=sorted(done), inflight=inflight, left=left,
                elapsed=(now - t0) if t0 else None,
                remaining=(deadline - now) if deadline else None,
                deadline=deadline, per_unit=per_unit, eta=eta, totals=tot, exceptions=exc,
                incumbent=inc, manifest=man, progress=prog,
                hits=[e for e in ev if e.get('event') in ('genuine', 'plan')],
                events=len(ev))
