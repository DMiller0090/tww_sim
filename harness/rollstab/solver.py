"""From-rest dust solver: search the input knobs for a genuine+clear roll-stab clip.

Run shape (from the anchor's REST state, harness.rollstab.rest.rest_state -- bit-exact from
row 0, no live calibration):
    [start-crawl sticks (rows 0..k-1)] + [cruise on the F aim stick, with MOVES placed lead
    frames before the A press] + [A] + [15 aim] + [B edge] + [aim tail]

Knobs (all sticks are dtm_stick-calibrated -- sim ONLY the bytes dtm_make will deliver):
  * start  -- the 1D-approach START CRAWL: up to START_KMAX partial-magnitude sticks (msd
              0.52..0.889 + full, aimed at F) in the FIRST rows, while speed is LOW -- each
              partial shifts the whole downstream trajectory along-track by a fine quantum
              (the dense fill that made the freeze planner's 0-ULP targeting work);
  * moves  -- (lead, stick) 1-frame partial-magnitude "fines" and (lead, stick, dur) bearing
              ARCS (gross lateral shift of the roll line);
  * A_proj -- the press threshold (z phase, 17u grid).

Acceptance is EXACT per candidate, never a fitted residual: genuine_clip on the run's real
old->new + approach_clear (no roll segment fires the wall) + speedF==17 at the A press (a sub-cap
walk gives a sub-26 roll and a shrunken lunge -- never clips) + facing==F.

    python -m harness.rollstab.solver anchor=<anchor>        # catalog + ranked search
    python -m harness.rollstab.solver anchor=<anchor> drill  # + iterative-deepening drill

Hits -> _generated/rollstab_hits.json (ship with harness.rollstab.deliver).
"""
import os, sys, json, math, time
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.land.land import FRONT_ROLL, CUT_F, CUT_A
from tww_sim.land.plan_land import stick_for_bearing
from harness.rollstab import geometry as G
from harness.rollstab import rest as C

HITS_PATH = os.path.join(_rb, '_generated', 'rollstab_hits.json')
ZLO, ZHI = 302.6, 308.2        # old_z clear band (roll stops at the face below ~302.6)
START_KMAX = 3                 # start-crawl window (K<=3: low-speed micro-moves, 1D approach)
_BASE = {}


def base(anchor):
    if anchor not in _BASE:
        _BASE[anchor] = C.rest_state(anchor)
    return _BASE[anchor].clone()


def run(anchor, moves, A_proj=-506.0, tail=8, start=()):
    """One exact run from REST. `start` = sticks for stream rows 0..len-1 (the acceleration
    micro-crawl; the entry acts them with the 2-frame delay). `moves` = [(lead, stick[, dur]),
    ...] placed lead frames before the A press (fixpoint placement: the press frame is
    threshold-derived, so placement iterates to a fixed point). Returns an info dict
    (old/new/rho/z/genuine/clear/spF_at_A/stream) or None."""
    _, straight, aim = C.sticks_of(anchor)
    start = tuple(start)
    placed = None
    for _ in range(4):
        s = base(anchor)
        suffix = []
        ci = 0
        cross = None
        for _ in range(90):
            if ci >= len(start) and G.along((s.pos_x, s.pos_z)) >= A_proj:
                cross = ci
                break
            stk = start[ci] if ci < len(start) else aim
            if placed is not None and ci in placed:
                stk = placed[ci]
            s.step(stk[0], stk[1])
            suffix.append((stk[0], stk[1], 0))
            ci += 1
        if cross is None:
            return None
        want = {}
        for mv in moves:
            ld, stk = mv[0], mv[1]
            dur = mv[2] if len(mv) > 2 else 1
            for d in range(dur):
                idx = cross - ld + d
                if idx < len(start) or idx >= cross or idx in want:
                    return None
                want[idx] = stk
        if want != (placed or {}):
            placed = want
            continue
        spF_at_A = s.speedF
        rows = []

        def do(sx, sy, btn=0):
            s.step(sx, sy, buttons=btn)
            suffix.append((sx, sy, btn))
            rows.append((s.state & 0xFF, s.pos_x, s.pos_z, s.facing & 0xFFFF))

        do(aim[0], aim[1], G.A_BTN)
        for _ in range(G.KROLL):
            do(aim[0], aim[1])
        do(aim[0], aim[1], G.B_BTN)
        for _ in range(tail):
            do(aim[0], aim[1])
        cut_i = next((i for i, rr in enumerate(rows) if rr[0] in (CUT_F, CUT_A)), None)
        if cut_i is None or cut_i == 0:
            return dict(fired=False, spF_at_A=spF_at_A)
        old = (rows[cut_i - 1][1], rows[cut_i - 1][2])
        new = (rows[cut_i][1], rows[cut_i][2])
        roll_pts = [(rr[1], rr[2]) for rr in rows if rr[0] == FRONT_ROLL]
        gen = G.genuine_clip(old, new)
        clear = gen and not any(G.seg_blocked(roll_pts[i], roll_pts[i + 1])
                                for i in range(len(roll_pts) - 1))
        return dict(fired=True, old=old, new=new, rho=G.perp(old), z=old[1],
                    genuine=gen, clear=clear, spF_at_A=spF_at_A,
                    facing=rows[cut_i][3], cut_proc=rows[cut_i][0],
                    disp=math.hypot(new[0] - old[0], new[1] - old[1]),
                    n_roll=len(roll_pts), stream=suffix)
    return None


def start_family(anchor, kmax=START_KMAX, F=None):
    """The 1D-approach start-crawl lattice: distinct dtm-calibrated sticks at bearing F, full +
    every distinct live-valid partial (msd 0.889..0.52, the movement gate band -- the (0.889,1)
    band is live-divergent, see plan_land._freeze_start_lattice). Combos are k-tuples with the
    NON-FULL stick count kept low (each run is exact; the full x full.. prefix is the baseline).
    Ordered shallow-first so cheap candidates come first. `F` overrides the aim facing (default the
    kaze `geometry.F`) so the Tetra-corner solver can reuse this at its own clip facing."""
    F = G.F if F is None else F
    seed = G.load_seed(anchor)
    cs = seed['csangle'] & 0xFFFF
    full = C.dtm_stick(stick_for_bearing(F, cs, 1.0))
    alph, seen = [], {full}
    for j in range(889, 519, -1):
        stk = C.dtm_stick(stick_for_bearing(F, cs, j / 1000.0))
        if stk not in seen:
            seen.add(stk)
            alph.append(stk)
    combos = []
    for stk in alph:                                     # k=1: one partial first frame
        combos.append((stk,))
    for stk in alph:                                     # k=2: partial + full, full + partial
        combos.append((stk, full))
        combos.append((full, stk))
    for stk in alph:                                     # k=3: one partial in three slots
        combos.append((stk, full, full))
        combos.append((full, stk, full))
        combos.append((full, full, stk))
    for a in alph[::4]:                                  # k=2 double-partial (coarse subsample)
        for b in alph[::4]:
            combos.append((a, b))
    return combos


def fine_family(anchor, mstep=0.004, leads=(4, 5, 6, 7, 10), F=None):
    F = G.F if F is None else F
    out, seen = [], set()
    seed = G.load_seed(anchor)
    cs = seed['csangle'] & 0xFFFF
    aim = C.dtm_stick(stick_for_bearing(F, cs, 1.0))
    for j in range(-4, 5):
        m = 0.999
        while m >= 0.50:
            stk = C.dtm_stick(stick_for_bearing((F + 16 * j) & 0xFFFF, cs, m))
            if stk not in seen:
                seen.add(stk)
                out.append(stk)
            m -= mstep
    return [(ld, stk) for stk in out if stk != aim for ld in leads]


def arc_family(anchor, bstep=50, durs=(1, 2, 3), leads=(10, 9, 8, 7), min_settle=5, F=None):
    F = G.F if F is None else F
    out, seen = [], set()
    seed = G.load_seed(anchor)
    cs = seed['csangle'] & 0xFFFF
    aim = C.dtm_stick(stick_for_bearing(F, cs, 1.0))
    for d in list(range(-1000, -149, bstep)) + list(range(150, 1001, bstep)):
        stk = C.dtm_stick(stick_for_bearing((F + d) & 0xFFFF, cs, 1.0))
        for dur in durs:
            for ld in leads:
                if ld - dur < min_settle:
                    continue
                key = (stk, dur, ld)
                if key in seen or stk == aim:
                    continue
                seen.add(key)
                out.append((ld, stk, dur))
    return out


def _record(hits, r, moves, A_proj, start, anchor):
    hits.append(dict(anchor=anchor, moves=[[m[0], list(m[1])] + list(m[2:]) for m in moves],
                     A_proj=A_proj, start=[list(x) for x in start],
                     old=list(r['old']), new=list(r['new']),
                     rho=r['rho'], facing=r['facing'], disp=r['disp'], cut_proc=r['cut_proc'],
                     n_roll=r['n_roll'], stream=[list(x) for x in r['stream']]))
    os.makedirs(os.path.dirname(HITS_PATH), exist_ok=True)
    json.dump(hits, open(HITS_PATH, 'w'))


def search(anchor, nhits=4, do_drill=False, K=60, levels=2):
    """Arc/fine singles, then the start-crawl sweep (dense along-track fill), then (optionally)
    an iterative-deepening drill combining the nearest configs. Every accept is the exact run."""
    t0 = time.time()
    r0 = run(anchor, [])
    print('baseline old=(%.7f,%.7f) z=%.4f rho=%+0.6f' % (
          r0['old'][0], r0['old'][1], r0['z'], r0['rho']), flush=True)
    hits, samples, n = [], [], 0

    def check(moves, A_proj, start=()):
        nonlocal n
        n += 1
        r = run(anchor, moves, A_proj, start=start)
        if (r is None or not r.get('fired') or r['facing'] != G.F or r['spF_at_A'] != 17.0):
            return None
        samples.append((r['old'][0], r['old'][1], [list(m) for m in moves], A_proj,
                        [list(x) for x in start]))
        if (ZLO <= r['z'] <= ZHI) and r['genuine'] and r['clear']:
            print('CLIP start=%s moves=%s A=%.0f old=(%.7f,%.7f) rho=%+0.6f (%.0fs)' % (
                  list(start), moves, A_proj, r['old'][0], r['old'][1], r['rho'],
                  time.time() - t0), flush=True)
            _record(hits, r, moves, A_proj, start, anchor)
        return r

    A_projs = (-506.0, -512.0, -500.0)
    fam = arc_family(anchor) + fine_family(anchor)
    for mv in fam:
        for A in A_projs:
            check([mv], A)
            if len(hits) >= nhits:
                return hits
    print('singles done: %d runs, hits=%d (%.0fs)' % (n, len(hits), time.time() - t0), flush=True)
    starts = start_family(anchor)
    for st in starts:
        check([], A_projs[0], start=st)
        if len(hits) >= nhits:
            return hits
    print('start-crawl done: %d runs, hits=%d (%.0fs)' % (n, len(hits), time.time() - t0),
          flush=True)
    if not do_drill:
        return hits
    # drill: extend the configs nearest to genuine dust with one more move / a start crawl
    def score(x, z):
        # x-column match dominates: the razor is thin in x and the along-track knobs are dense
        best = 1e9
        for gx, gz in _dust_cache():
            d = math.hypot((gx - x) * 200.0, gz - z)
            best = min(best, d)
        return best

    _dc = []

    def _dust_cache():
        if not _dc:
            from tww_sim.core.fp import f32 as _f
            zz = 302.6
            x_lo, x_hi = 9071.5, 9072.7
            while zz <= 308.2:
                xx = x_lo
                while xx <= x_hi:
                    if G.pred_genuine((_f(xx), _f(zz))):
                        _dc.append((float(_f(xx)), float(_f(zz))))
                    xx += 0.001
                zz += 0.02
            print('dust cache: %d pts' % len(_dc), flush=True)
        return _dc

    pool = {json.dumps(s[2]) + str(s[3]) + json.dumps(s[4]): s for s in samples}
    for lvl in range(levels):
        cands = sorted(pool.values(), key=lambda s: score(s[0], s[1]))[:K]
        print('drill level %d (best %.5f)' % (lvl, score(cands[0][0], cands[0][1])), flush=True)
        for x, z, moves, A, start in cands:
            used = set()
            for m in moves:
                dur = m[2] if len(m) > 2 else 1
                used |= set(range(m[0] - dur + 1, m[0] + 1))
            movesT = [tuple([m[0], tuple(m[1])] + list(m[2:])) for m in moves]
            startT = tuple(tuple(x2) for x2 in start)
            for mv in fam:                       # one more arc/fine on this config
                dur = mv[2] if len(mv) > 2 else 1
                if set(range(mv[0] - dur + 1, mv[0] + 1)) & used:
                    continue
                check(movesT + [mv], A, start=startT)
                if len(hits) >= nhits:
                    return hits
            if not startT:                       # or a start crawl under this config
                for st in start_family(anchor)[:120]:
                    check(movesT, A, start=st)
                    if len(hits) >= nhits:
                        return hits
        pool = {json.dumps(s[2]) + str(s[3]) + json.dumps(s[4]): s for s in samples}
    print('done: %d runs, hits=%d (%.0fs)' % (n, len(hits), time.time() - t0), flush=True)
    return hits


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    search(o.get('anchor', 'kaze_r11_rollstab_idle2@twwgz'),
           do_drill=('drill' in sys.argv))
