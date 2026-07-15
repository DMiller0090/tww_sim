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
from harness.rollstab.geometry import SEAM as _KAZE_SEAM, load_seed
from harness.rollstab import rest as C

HITS_PATH = os.path.join(_rb, '_generated', 'rollstab_hits.json')
START_KMAX = 3                 # start-crawl window (K<=3: low-speed micro-moves, 1D approach)
_BASE = {}
_BASE_WALLED = {}


def base(anchor, dtm_seed=1):
    """A cloned from-rest sim seeded for the make_dtm `dtm_seed` the stream will be DELIVERED with.
    The roll-stab clip ships with seed=0 (the make_dtm delivery fix, session 43) so it solves on the
    seed-0 model (noops=2); legacy callers keep seed=1 (byte-identical)."""
    key = (anchor, dtm_seed)
    if key not in _BASE:
        _BASE[key] = C.rest_state(anchor, dtm_seed=dtm_seed)
    return _BASE[key].clone()


def walled_base(anchor, seam, dtm_seed=1):
    """A cloned from-rest sim with the seam's wall tris in the stepper (Phase W CrrPos), so the roll
    approach BRAKES exactly as live does. Used by `wall_faithful` to decide reachability by real
    physics rather than a typed-in `old_z` band (Dereck's session-49 call)."""
    key = (anchor, dtm_seed, id(seam))
    if key not in _BASE_WALLED:
        _BASE_WALLED[key] = C.rest_state(anchor, walls=seam.TRIS, dtm_seed=dtm_seed)
    return _BASE_WALLED[key].clone()


def wall_faithful(anchor, stream, old_ref, seam, dtm_seed=1):
    """PHYSICS reachability guard (dead-end #3): replay the candidate's exact recorded `stream`
    through a WALLED rest_state; the candidate `old` is genuinely REACHABLE iff the roll reaches it
    with NO wall stopping the approach first. Returns True/False.

    This replaces the kaze-hardcoded `ZLO/ZHI` old_z band: that band was a proxy for exactly this
    check (rejecting an `old` the wall-LESS roll overshot into -- the session-4 artifact). Deciding
    it by the actual walled sim is per-seam-general and needs no typed boundary. A candidate is
    rejected if any frame before the CUT flags `wall_hit`, or if the walled `old` differs from the
    wall-less `old` (the wall subtly diverted the approach)."""
    s = walled_base(anchor, seam, dtm_seed=dtm_seed)
    rows = []
    hit_before_cut = False
    cut_i = None
    for (sx, sy, btn) in stream:
        s.step(sx, sy, buttons=btn)
        st = s.state & 0xFF
        if cut_i is None and st in (CUT_F, CUT_A):
            cut_i = len(rows)                     # index of the CUT row (old is the row before)
        if cut_i is None and getattr(s, 'wall_hit', False):
            hit_before_cut = True
        rows.append((st, s.pos_x, s.pos_z))
    if cut_i is None or cut_i == 0 or hit_before_cut:
        return False
    from tww_sim.core.fp import f32 as _f
    wold = (rows[cut_i - 1][1], rows[cut_i - 1][2])
    return _f(wold[0]) == _f(old_ref[0]) and _f(wold[1]) == _f(old_ref[1])


def run(anchor, moves, A_proj=-506.0, tail=8, start=(), draw_at=None, dtm_seed=1, seam=None):
    """One exact run from REST. `start` = sticks for stream rows 0..len-1 (the acceleration
    micro-crawl; the entry acts them with the 2-frame delay). `moves` = [(lead, stick[, dur]),
    ...] placed lead frames before the A press (fixpoint placement: the press frame is
    threshold-derived, so placement iterates to a fixed point). `draw_at` (session 35, sheathed
    roll path): the approach row index to feed a single B rising edge (the mid-walk sword
    pull-out). With `rest_state`'s model_draw ON (auto for a sheathed anchor), the sword draw
    completes DRAW_DELAY acted-frames later and sets `sword_drawn` before the A press, so the
    roll routes to a CUT. draw_at MUST land before the A press with margin (the draw + rebuild to
    cap in the sword set). Returns an info dict (old/new/rho/z/genuine/clear/spF_at_A/stream) or
    None."""
    seam = _KAZE_SEAM if seam is None else seam
    _, straight, aim = C.sticks_of(anchor)
    start = tuple(start)
    # Prepend (1-dtm_seed) neutral ABSORBER frames so the seed-0 layout's extra leading no-op does not
    # silently eat start[0] (dead-end #35; a full frame preserves seed-0's poll phase). seed=1 => 0.
    n_absorb = max(0, 1 - int(dtm_seed))
    placed = None
    for _ in range(4):
        s = base(anchor, dtm_seed=dtm_seed)
        suffix = []
        for _ in range(n_absorb):
            s.step(128, 128)
            suffix.append((128, 128, 0))
        ci = 0
        cross = None
        for _ in range(90):
            if ci >= len(start) and seam.along((s.pos_x, s.pos_z)) >= A_proj:
                cross = ci
                break
            stk = start[ci] if ci < len(start) else aim
            if placed is not None and ci in placed:
                stk = placed[ci]
            btn = seam.B_BTN if (draw_at is not None and ci == draw_at) else 0
            s.step(stk[0], stk[1], buttons=btn)
            suffix.append((stk[0], stk[1], btn))
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

        do(aim[0], aim[1], seam.A_BTN)
        for _ in range(seam.KROLL):
            do(aim[0], aim[1])
        do(aim[0], aim[1], seam.B_BTN)
        for _ in range(tail):
            do(aim[0], aim[1])
        cut_i = next((i for i, rr in enumerate(rows) if rr[0] in (CUT_F, CUT_A)), None)
        if cut_i is None or cut_i == 0:
            return dict(fired=False, spF_at_A=spF_at_A)
        old = (rows[cut_i - 1][1], rows[cut_i - 1][2])
        new = (rows[cut_i][1], rows[cut_i][2])
        roll_pts = [(rr[1], rr[2]) for rr in rows if rr[0] == FRONT_ROLL]
        gen = seam.genuine_clip(old, new)
        clear = gen and not any(seam.seg_blocked(roll_pts[i], roll_pts[i + 1])
                                for i in range(len(roll_pts) - 1))
        return dict(fired=True, old=old, new=new, rho=seam.perp(old), z=old[1],
                    genuine=gen, clear=clear, spF_at_A=spF_at_A,
                    facing=rows[cut_i][3], cut_proc=rows[cut_i][0],
                    disp=math.hypot(new[0] - old[0], new[1] - old[1]),
                    n_roll=len(roll_pts), stream=suffix)
    return None


def start_family(anchor, kmax=START_KMAX, F=None, seam=None):
    """The 1D-approach start-crawl lattice: distinct dtm-calibrated sticks at bearing F, full +
    every distinct live-valid partial (msd 0.889..0.52, the movement gate band -- the (0.889,1)
    band is live-divergent, see plan_land._freeze_start_lattice). Combos are k-tuples with the
    NON-FULL stick count kept low (each run is exact; the full x full.. prefix is the baseline).
    Ordered shallow-first so cheap candidates come first. `F` overrides the aim facing (default the
    kaze `geometry.F`) so the Tetra-corner solver can reuse this at its own clip facing."""
    F = (_KAZE_SEAM if seam is None else seam).F if F is None else F
    seed = load_seed(anchor)
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


def fine_family(anchor, mstep=0.004, leads=(4, 5, 6, 7, 10), F=None, seam=None):
    """1-frame partial-magnitude perp fines across the full msd range down to 0.50. The (0.889, 1.0)
    band is INCLUDED (session 43): the s41 "band walk-speed" exclusion was overturned -- RAM-reading
    `g_mDoCPd_cpadInfo[0]` proved the physics + decode are faithful and a 1-frame band stick delivers
    its raw value when ISOLATED (dead-end #34). The s41 live miss was a make_dtm DELIVERY DROP (the
    default seed=1 poll cadence dropped a clustered band fine), fixed by delivering with seed=0; so
    band fines are usable again and restore the near-full-mag perp density the band-free search lacked
    (session 40's ~0.0013u wall). Solve on the seed-0 model (`run(..., dtm_seed=0)`) so the sim matches
    the seed-0 delivery, and ship via seed=0."""
    F = (_KAZE_SEAM if seam is None else seam).F if F is None else F
    out, seen = [], set()
    seed = load_seed(anchor)
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


def arc_family(anchor, bstep=50, durs=(1, 2, 3), leads=(10, 9, 8, 7), min_settle=5, F=None, seam=None):
    F = (_KAZE_SEAM if seam is None else seam).F if F is None else F
    out, seen = [], set()
    seed = load_seed(anchor)
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


def _record(hits, r, moves, A_proj, start, anchor, dtm_seed=1, draw_at=None):
    hits.append(dict(anchor=anchor, moves=[[m[0], list(m[1])] + list(m[2:]) for m in moves],
                     A_proj=A_proj, start=[list(x) for x in start], dtm_seed=dtm_seed, draw_at=draw_at,
                     old=list(r['old']), new=list(r['new']),
                     rho=r['rho'], facing=r['facing'], disp=r['disp'], cut_proc=r['cut_proc'],
                     n_roll=r['n_roll'], stream=[list(x) for x in r['stream']]))
    os.makedirs(os.path.dirname(HITS_PATH), exist_ok=True)
    json.dump(hits, open(HITS_PATH, 'w'))


def search(anchor, nhits=4, do_drill=False, K=60, levels=2, draw_at=None, dtm_seed=1, seam=None):
    """Arc/fine singles, then the start-crawl sweep (dense along-track fill), then (optionally)
    an iterative-deepening drill combining the nearest configs. Every accept is the exact run.

    `draw_at` (session 35, sheathed roll path): forwarded to every `run` -- the approach row on
    which to feed the mid-walk sword draw's single B rising edge. For a sheathed anchor
    (`rest_state` model_draw ON) the draw completes before the A press so the roll routes to a
    CUT; None (a drawn anchor) is byte-identical to the pre-session-35 behaviour.

    `seam` (session 46, generalization Phase 3): the per-seam `SeamGeo` supplying `F` + exact
    acceptance; default None = the kaze r11 seam (`geometry.SEAM`), so the standard invocation is
    byte-identical. Threaded into every `run`/family call and the `!= seam.F` accept gate + drill
    dust cache, so a NEW enumerated seam solves via the same path (no module-global geometry)."""
    seam = _KAZE_SEAM if seam is None else seam
    t0 = time.time()
    r0 = run(anchor, [], draw_at=draw_at, dtm_seed=dtm_seed, seam=seam)
    print('baseline old=(%.7f,%.7f) z=%.4f rho=%+0.6f' % (
          r0['old'][0], r0['old'][1], r0['z'], r0['rho']), flush=True)
    hits, samples, n = [], [], 0

    def check(moves, A_proj, start=()):
        nonlocal n
        n += 1
        r = run(anchor, moves, A_proj, start=start, draw_at=draw_at, dtm_seed=dtm_seed, seam=seam)
        if (r is None or not r.get('fired') or r['facing'] != seam.F or r['spF_at_A'] != 17.0):
            return None
        samples.append((r['old'][0], r['old'][1], [list(m) for m in moves], A_proj,
                        [list(x) for x in start]))
        # Reachability is decided by the WALLED physics re-sim, not a typed-in old_z band (session 49):
        # accept only genuine + clear cuts whose approach actually reaches `old` past the wall.
        if r['genuine'] and r['clear'] and wall_faithful(anchor, r['stream'], r['old'], seam, dtm_seed):
            print('CLIP start=%s moves=%s A=%.0f old=(%.7f,%.7f) rho=%+0.6f (%.0fs)' % (
                  list(start), moves, A_proj, r['old'][0], r['old'][1], r['rho'],
                  time.time() - t0), flush=True)
            _record(hits, r, moves, A_proj, start, anchor, dtm_seed=dtm_seed, draw_at=draw_at)
        return r

    A_projs = (-506.0, -512.0, -500.0)
    fam = arc_family(anchor, seam=seam) + fine_family(anchor, seam=seam)
    for mv in fam:
        for A in A_projs:
            check([mv], A)
            if len(hits) >= nhits:
                return hits
    print('singles done: %d runs, hits=%d (%.0fs)' % (n, len(hits), time.time() - t0), flush=True)
    starts = start_family(anchor, seam=seam)
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
        # The drill's genuine TARGET set: sweep pred_genuine over the region the search REACHES --
        # centered on the sim baseline `old`, extents from the seam reach band, capped (session 49; no kaze box).
        if not _dc:
            from tww_sim.core.fp import f32 as _f
            lo, hi = seam.search_band()
            span = min(hi - lo, 8.0)                     # along extent, capped
            cx, cz = r0['old']
            olds = [(s[0], s[1]) for s in samples] or [(cx, cz)]
            hx = min(max(abs(o[0] - cx) for o in olds) + 0.6, 2.0)   # perp-ish (x), thin
            hz = min(max(abs(o[1] - cz) for o in olds) + 0.6, span)  # along-ish (z)
            x_lo, x_hi, z_lo, z_hi = cx - hx, cx + hx, cz - hz, cz + hz
            zz = z_lo
            while zz <= z_hi:
                xx = x_lo
                while xx <= x_hi:
                    if seam.pred_genuine((_f(xx), _f(zz))):
                        _dc.append((float(_f(xx)), float(_f(zz))))
                    xx += 0.001
                zz += 0.02
            print('dust cache: %d pts (box x[%.2f,%.2f] z[%.2f,%.2f])' % (
                  len(_dc), x_lo, x_hi, z_lo, z_hi), flush=True)
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
                for st in start_family(anchor, seam=seam)[:120]:
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
