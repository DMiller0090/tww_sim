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
from tww_sim.core.fp import f32 as _F
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
    # Aim the approach at THIS seam's F (generalization Phase 5): C.sticks_of hardcodes geometry.F,
    # which walks a NOVEL seam's approach the wrong way. Byte-identical for the kaze seam (seam.F==G.F).
    _cs = load_seed(anchor)['csangle'] & 0xFFFF
    aim = C.dtm_stick(stick_for_bearing(seam.F, _cs, 1.0))
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


def _derive_a_projs(anchor, seam, dtm_seed, r0):
    """Per-anchor A-press thresholds that bracket the seam's reach band (generalization Phase 5).

    The A-press fires at the first frame where `along >= A_proj`; the frame is integer, so baseline
    `old` d2S JUMPS ~one walk step as A_proj varies, and the reach band usually falls in a gap between
    two landings (the start-crawl fills that gap). So we keep A_projs whose baseline landing sits within
    ~one walk-step of the band on EITHER side (dedup by integer landing d2S), nearest-to-band first.
    The hardcoded (-506,-512,-500) were tuned to the kaze roll anchor's DISTANCE; a novel anchor at a
    different distance from its seam needs a different threshold. Adaptive scan center from r0 so it
    works regardless of anchor distance. Falls back to the legacy triple if the scan finds nothing."""
    lo, hi = seam.search_band()
    ctr = (lo + hi) / 2.0
    d0 = math.hypot(r0['old'][0] - seam.S[0], r0['old'][1] - seam.S[1]) if r0.get('old') else ctr
    a_center = -506.0 + (d0 - ctr)          # slide the scan so the band lands mid-window
    cands, seen = [], set()
    for i in range(-50, 51):
        A = a_center + i * 0.5
        r = run(anchor, [], A_proj=A, dtm_seed=dtm_seed, seam=seam)
        if not (r and r.get('fired') and r.get('old') and r.get('spF_at_A') == 17.0):
            continue
        d2S = math.hypot(r['old'][0] - seam.S[0], r['old'][1] - seam.S[1])
        if lo - 18.0 <= d2S <= hi + 18.0:
            key = round(d2S, 0)
            if key not in seen:
                seen.add(key)
                cands.append((abs(d2S - ctr), A))
    cands.sort()
    return tuple(a for _, a in cands) or (-506.0, -512.0, -500.0)


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

    A_projs = _derive_a_projs(anchor, seam, dtm_seed, r0)
    print('A_projs (derived, bracket reach band): %s' % [round(a, 1) for a in A_projs], flush=True)
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


NUDGE_SPMAX = 14.0             # nudge only start-crawl frames acted below this speedF (the octagon INTERIOR;
                               # above it sticks CLAMP + the fine lattice collapses -- see solve_focused doc).


def _genuine_perps(seam, samples=None):
    """The perp offsets of the genuine dust columns inside the seam's reach band -- a PURE-GEOMETRY
    (no sim) target set for the Phase-A bracket ranker. Scans `pred_genuine` over the band in the seam's
    (along, perp) frame and returns the sorted distinct perp values where a column exists. The corner
    razor is NOT at perp 0 (that is only true for a flat grazing seam); this derives its actual offset
    band from the geometry, so the ranker needs no per-seam target perp ([[no-overtuned-constants]])."""
    lo, hi = seam.search_band()
    Sx, Sz = seam.S
    out = set()
    a = -hi
    while a <= -lo:
        p = -0.5
        while p <= 0.5:
            x = Sx + a * seam.DIRX + p * seam.PX
            z = Sz + a * seam.DIRZ + p * seam.PZ
            if seam.pred_genuine((_F(x), _F(z))):
                out.add(round(p, 3))
            p += 0.001
        a += 0.05
    return sorted(out)


def solve_focused(anchor, seam, dtm_seed=0, budget=110.0, want=8, off_span=1800,
                  off_step=120, nudge=10, kbr=40, m2s=(1.0, 0.72, 0.6), c3m=0.66,
                  verbose=True):
    """Focused roll-stab dust search (the walkstab.solve_focused pattern in the roll `run` form): an ARC
    gross-perp bracket + a LOW-SPEED byte-nudge densifier + the wall_faithful gate. Pure sim, no
    calibration. This is the objective-compliant one-shot for a NOVEL seam whose reachable roll line sits
    units off the razor -- which the cold `search`/drill cannot thread.

    WHY the cold drill fails and this doesn't (session 51): the genuine acceptance is a single f32 column
    (~0.001u wide, sparse) and, for a novel seam, the reachable roll `old` sits GROSSLY off it in perp (the
    mirror seam's approach line is ~2.7u off the F-through-S line; the proven kaze seam was already near its
    razor, so `search`'s fine knobs sufficed there). Closing that gap needs the ARC (a full-mag off-aim
    stint -- the gross perp knob; it octagon-SATURATES, so a wide off range collapses onto the same shift).
    Then the exact column is threaded by a byte-NUDGE of a start-crawl frame acted at LOW speed (the nudged
    frame's speedF < NUDGE_SPMAX): near the walk cap sticks octagon-CLAMP and the reachable lattice
    collapses; below it the partial-mag stick stays in the octagon INTERIOR. NOTE the nudge is NOT a smooth
    fine knob in the roll form (unlike walk-stab's short walk-then-cut): a low-speed perturbation propagates
    through the whole cruise+roll, so the reachable `old` lattice is CHAOTIC -- a genuine hit is an isolated
    lattice point, found by sweeping the nudge grid and testing each EXACTLY.

    Phase A (wall-less, cheap): sweep arc(off, lead, dur) x the derived A_projs; rank the fired spF@A==17
      candidates by how near `old`'s perp sits to a genuine dust COLUMN in the reach band (`_genuine_perps`,
      pure geometry -- the corner razor's perp offset is derived, not a typed target). Keep the top `kbr`.
    Phase B (nudge): for each bracket, add a K=3 start crawl (full, 2nd-frame at an octagon-interior
      partial magnitude `m2`, byte-NUDGED 3rd frame, acted at low speed) and sweep the nudge over a
      +-`nudge` byte grid per m2; test the EXACT genuine_clip + clear at spF@A==17, facing==seam.F.
      `m2s` sweeps the documented start-crawl partial-magnitude family (README knobs, msd 0.52..0.889 --
      the walkstab densifier's earlier-frame partials, session 55): m2=1.0 first (the original full-full
      lattice, byte-identical), then each partial RESHUFFLES the whole downstream chaotic lattice, giving
      fresh independent clouds around the same bracket -- needed when a seam's dust slivers are thinner
      than one cloud's local density (the 97m corner: <=0.0006u slivers in a 0.02u perp band).
    Phase C (walled confirm): `wall_faithful` re-sim -- accept only cuts whose approach reaches `old` past
      the wall (dead-end #3). Rank by the perp sliver margin (delivery robustness). Records to HITS_PATH
      (same schema as `search`, carrying the explicit `start`/`moves`/`A_proj`/`dtm_seed`) for `deliver`.

    Every knob is derived or a documented physical regime (NUDGE_SPMAX, the octagon-interior magnitude
    0.66, the general symmetric arc span, the geometry-derived genuine-perp target) -- no per-seam tuned
    constants ([[no-overtuned-constants]])."""
    t0 = time.time()
    _cs = load_seed(anchor)['csangle'] & 0xFFFF
    full = C.dtm_stick(stick_for_bearing(seam.F, _cs, 1.0))
    c3raw = stick_for_bearing(seam.F, _cs, c3m)       # octagon-interior mid-magnitude nudge base
    #                                                   (c3m: the documented msd family 0.52..0.889 --
    #                                                   a different base = a fresh independent lattice)
    r0 = run(anchor, [], dtm_seed=dtm_seed, seam=seam)
    A_projs = _derive_a_projs(anchor, seam, dtm_seed, r0)
    gperps = _genuine_perps(seam)

    def score(old):                                   # nearness of old's perp to a genuine column
        po = seam.perp(old)
        return min((abs(po - g) for g in gperps), default=abs(po))

    if verbose:
        print('focused: %d genuine perp cols in band [%s]; A_projs=%s (%.0fs)' % (
              len(gperps), ('%.3f..%.3f' % (gperps[0], gperps[-1])) if gperps else '-',
              [round(a, 1) for a in A_projs[:8]], time.time() - t0), flush=True)

    # --- Phase A: arc gross-perp brackets, ranked by nearest genuine perp column ---
    brackets, n_arc = [], 0
    for off in range(-off_span, off_span + 1, off_step):
        if off == 0:
            continue
        arc = C.dtm_stick(stick_for_bearing((seam.F + off) & 0xFFFF, _cs, 1.0))
        for dur in (2, 3, 4, 5):
            for lead in (4, 5, 6, 7):
                for A in A_projs[:6]:
                    n_arc += 1
                    r = run(anchor, [(lead, arc, dur)], A_proj=A, dtm_seed=dtm_seed, seam=seam)
                    if not (r and r.get('fired') and r.get('old') and r.get('spF_at_A') == 17.0):
                        continue
                    brackets.append((score(r['old']), off, dur, lead, A))
    brackets.sort(key=lambda b: b[0])
    brackets = brackets[:kbr]
    if verbose:
        print('Phase A: %d arcs -> %d brackets, best score=%.5f (%.0fs)' % (
              n_arc, len(brackets), brackets[0][0] if brackets else -1,
              time.time() - t0), flush=True)

    # --- Phase B + C: low-speed byte-nudge densifier on each bracket ---
    hits, seen = [], set()
    for (pr0, off, dur, lead, A) in brackets:
        if time.time() - t0 > budget or len(hits) >= want:
            break
        arc = C.dtm_stick(stick_for_bearing((seam.F + off) & 0xFFFF, _cs, 1.0))
        for m2 in m2s:
            if time.time() - t0 > budget or len(hits) >= want:
                break
            f2 = full if m2 >= 1.0 else C.dtm_stick(stick_for_bearing(seam.F, _cs, m2))
            for dx in range(-nudge, nudge + 1):
                for dz in range(-nudge, nudge + 1):
                    c3d = C.dtm_stick((min(254, max(1, c3raw[0] + dx)),
                                       min(254, max(1, c3raw[1] + dz))))
                    start = (full, f2, c3d)
                    r = run(anchor, [(lead, arc, dur)], A_proj=A, start=start,
                            dtm_seed=dtm_seed, seam=seam)
                    if not (r and r.get('fired') and r['facing'] == seam.F
                            and r['spF_at_A'] == 17.0):
                        continue
                    if not (r['genuine'] and r['clear']):
                        continue
                    if not wall_faithful(anchor, r['stream'], r['old'], seam, dtm_seed):
                        continue
                    key = (round(r['old'][0], 5), round(r['old'][1], 5))
                    if key in seen:
                        continue
                    seen.add(key)
                    margin = _perp_margin(seam, r['old'], r['new'])
                    moves = [(lead, arc, dur)]
                    _record(hits, r, moves, A, start, anchor, dtm_seed=dtm_seed)
                    hits[-1]['margin'] = margin
                    json.dump(hits, open(HITS_PATH, 'w'))
                    if verbose:
                        print('  CLIP margin=%d off=%+d dur=%d lead=%d A=%.1f m2=%.2f nudge=(%+d,%+d) '
                              'old=(%.7f,%.7f) perp_ray=%+.6f d2S=%.3f (%.0fs)' % (
                              margin, off, dur, lead, A, m2, dx, dz, r['old'][0], r['old'][1],
                              seam.perp_to_ray(r['old'], r['new']), seam.d2S(r['old']),
                              time.time() - t0), flush=True)
    hits.sort(key=lambda h: -h.get('margin', 0))
    json.dump(hits, open(HITS_PATH, 'w'))
    if verbose:
        print('focused done: %d wall-faithful clips in %.0fs -> %s' % (
              len(hits), time.time() - t0, HITS_PATH), flush=True)
    return hits


def _perp_margin(seam, old, new, step=2e-5, cap=60):
    """The contiguous perp half-window at `old` (fresh in-line lunge), in +-`step` u -- how far `old` can
    shift PERPENDICULAR and still clip. Ranks hits by f32-sliver width (delivery robustness); the from-rest
    sim is 0-ULP so the live `old` lands exactly on the sim's and any positive-margin hit delivers (the
    same metric walkstab.perp_margin uses)."""
    from tww_sim.core.fp import f32 as _f
    a = math.atan2(new[0] - old[0], new[1] - old[1])
    pdx, pdz = -math.cos(a), math.sin(a)
    lunge = (_f(new[0] - old[0]), _f(new[1] - old[1]))

    def clips(k):
        o2 = (_f(old[0] + _f(k * step * pdx)), _f(old[1] + _f(k * step * pdz)))
        n2 = (_f(o2[0] + lunge[0]), _f(o2[1] + lunge[1]))
        return seam.genuine_clip(o2, n2)

    if not clips(0):
        return -1
    p = 0
    while p < cap and clips(p + 1):
        p += 1
    q = 0
    while q < cap and clips(-(q + 1)):
        q += 1
    return min(p, q)


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    anchor = o.get('anchor', 'kaze_r11_rollstab_idle2@twwgz')
    if 'focused' in sys.argv:
        from harness.rollstab.seamgeo import SeamGeo
        geo = json.load(open(o['geo'])) if 'geo' in o else None
        seam = SeamGeo(geo, load_seed(anchor)['csangle']) if geo else _KAZE_SEAM
        solve_focused(anchor, seam, dtm_seed=int(o.get('seed', 0)))
    else:
        search(anchor, do_drill=('drill' in sys.argv))
