"""WALK-stab seam-clip driver + solver scaffold (kaze r11, anchor kaze_r11_walkstab@twwgz).

The walk stab is the roll stab WITHOUT the roll: walk up to a sub-cap speed, then thrust (fwd stick
+ B) so a CUT_F fires out of a MOVE. lunge = speedF + 23.220 (the CUT_F joint-0 root translate; KB
mechanics/walk-stab.md), so a capped walk (speedF 17) reaches disp 40.22. The kaze r11 slot-3 seam
S=(9030.955,1385.858) (poly 803 x 802, interior 168.97 deg) clips from disp >= 35.02 (min speedF
~11.8), so no roll is needed.

WHAT IS PROVEN (session 29, live-gated):
  * ACCEPTANCE STRUCTURE (harness.collision.gap_search.characterize on this seam): a perp RAZOR --
    the offset window is ~6e-4u (sub-ULP at coord 9031) -- with a WIDE aim window (+-40 deg) and a
    wide displacement window (disp 35.5-40 all clip). So the razor is the perpendicular offset `rho`
    (the cut ray's distance to S); aim and disp are forgiving.
  * FROM-REST FEASIBILITY, with the C-DOWN camera pin: `rest.rest_state(ANCHOR)` stepped with a
    C-down C-stick (substickY=0) is BIT-EXACT in FACING every frame (the auto-cam would otherwise
    swing csangle and drift facing -- session 28's camera issue). The only from-rest residual is the
    walk-entry foot toe-stream (m359C / f312, the known Phase-R / session-25 gap): a CONSTANT
    ~0.0024u error established on the last m3598>0 blend frame, then FROZEN. Crucially it is a speedF
    (magnitude) error, so it lies ALONG the travel direction: its PERPENDICULAR component is ~3.7e-5u
    -- 16x inside the 6e-4u razor. So `rho` is bit-exact to ~3.7e-5u and the along error is absorbed
    by the wide disp window + B-timing. => a pure-sim walk-stab one-shot IS feasible; it does NOT need
    the foot-FK residual closed (unlike a naive read). Delivery MUST hold C-down to pin the camera.
    Live regression: tests/test_walkstab_rest.py (fixture _generated/walkstab_rest_trace.json).

DRIVER: walk N frames from the rest seed (C-down held), then enter_cut(CUT_F). The item put-away
delay is 4 frames of continued walking (the equip anime is upper-body; KB walk-stab.md), so the sim
is just walk-N-then-cut and the B-press is delivered at frame N-4. The B-timing sets where `old`
lands; time it to fire at the target `old` before any wall decel.

SOLVER (`solve()`, session 30): a from-rest dust search (pure sim, no calibration). The acceptance
is f32 dust, so it ENUMERATES distinct C-down walk streams -- beta spiral around bearing-to-S | start-
crawl msds (along) | bearing ARC (gross perp) | per-byte FINE nudge at an arc frame (the fine f32-
lottery; bearing->stick octagon-clamping makes `off` coarse) | N (cut frame) -- and tests the EXACT
`genuine_clip`. It finds a genuine 0-ULP clip in < 2 min. The dust is SPARSE: essentially ONE reachable
`old` lands in the ~2e-4u perp sliver.

DELIVERY IS BLOCKED (session 30, dead-end #28) -- corrects the session-29 feasibility read. A found
hit is a genuine OFFLINE clip, but the clean-DTM live run (`deliver()`) does NOT clip: to thread the
perp razor the walk must TURN, and the turn overlaps the speedF-blend walk-entry frame, freezing a foot
toe-stream (m359C/f312) error whose PERPENDICULAR component (~1.9e-4u for the clipping arc walk, live-
measured) EXCEEDS the ~1e-4u perp margin -- so `old_live` falls off the razor (blocked). The session-29
"perp residual ~3.7e-5u, harmless" was measured on a STRAIGHT walk; a real (turning) clip walk is 5x
worse. The objective-compliant fix is to MODEL the walk-entry foot residual (Phase-R / session-25 gap),
NOT to calibrate. Live golden: tests/golden/walkstab_deliver.json; regression tests/test_walkstab_clip.py.
"""
import os, sys, json, math, time
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.land.land import CUT_F
from tww_sim.land.plan_land import stick_for_bearing
from tww_sim.core.collision import Tri, Plane, crr_pos_walls
from tww_sim.core.fp import f32 as _f
from harness.rollstab import rest as C

ANCHOR = 'kaze_r11_walkstab@twwgz'
CUT_ROOT = 23.220
CDOWN = 0                       # substickY=0 = C-down = the free-cam pin (delivery MUST hold it)
LINK_Y = -6534.329
SEAM = (9030.955078125, 1385.858)

_M = json.load(open(os.path.join(_rb, 'fixtures', 'kaze_r11_walls_ordered.json')))
_BY = {p['poly']: p for p in _M['polys']}


def _mk(pid):
    p = _BY[pid]
    return Tri(p['v'][0], p['v'][1], p['v'][2],
               plane=Plane(p['n'][0], p['n'][1], p['n'][2], p['d']))


WALLA = _mk(803)                # n ~ (-0.4217,-0.9067)
WALLB = _mk(802)                # n ~ (-0.2404,-0.9707)
# the local wall chain as the CrrPos barrier (the r=35 cylinder sweep sees every tri it could touch)
TRIS = [_mk(801), WALLA, WALLB, _mk(804), _mk(798), _mk(800)]


def _pfunc(pla, x, z):
    return pla.func((_f(x), LINK_Y, _f(z)))


def in_front(x, z):
    return _pfunc(WALLA.pla, x, z) > 0 and _pfunc(WALLB.pla, x, z) > 0


def genuine_clip(old, new):
    """EXACT acceptance: the cut segment old->new clips the seam -- CrrPos NOT blocked, `old` in
    front of BOTH seam faces, `new` behind at least one. Returns (ok, why)."""
    if not in_front(*old):
        return False, 'old_behind'
    ox, oz, nx, nz = _f(old[0]), _f(old[1]), _f(new[0]), _f(new[1])
    _, info = crr_pos_walls((ox, LINK_Y, oz), (nx, LINK_Y, nz), TRIS)
    if info['line_hit'] or info['wall_hit']:
        return False, 'blocked'
    behind = _pfunc(WALLA.pla, nx, nz) < 0 or _pfunc(WALLB.pla, nx, nz) < 0
    return (behind, 'clip' if behind else 'short')


def perp_dist_to_S(old, facing):
    """Perpendicular distance from S to the ray from `old` at angle `facing` -- the RAZOR quantity
    (`rho`). Bit-exact from rest to ~3.7e-5u under the C-down pin (see the module docstring)."""
    a = facing / 65536.0 * 2 * math.pi
    dx, dz = math.sin(a), math.cos(a)
    px, pz = -dz, dx
    return (SEAM[0] - old[0]) * px + (SEAM[1] - old[1]) * pz


_BASE = None


def seed():
    """The from-rest seed for the walkstab anchor -- rest.rest_state (bit-exact facing under C-down).
    Cached; clone per run."""
    global _BASE
    if _BASE is None:
        _BASE = C.rest_state(ANCHOR)
    return _BASE.clone()


def walk_then_cut(sticks, N, aim=None):
    """DRIVER: walk `sticks` for N frames from rest (C-down held), then enter_cut(CUT_F). Frames past
    len(sticks) reuse the last. The 4-frame equip delay is delivery-only (the sim just walks then
    cuts; the DTM presses B at frame N-4). Returns an acceptance dict or None."""
    s = seed()
    for k in range(N):
        stk = sticks[k] if k < len(sticks) else sticks[-1]
        s.step(stk[0], stk[1], csx=128, csy=CDOWN)
    old = (s.pos_x, s.pos_z)
    fac, spF = s.facing, s.speedF
    try:
        s.enter_cut(CUT_F, aim=aim)
    except Exception:
        return None
    new = (s.pos_x, s.pos_z)
    disp = math.hypot(new[0] - old[0], new[1] - old[1])
    ok, why = genuine_clip(old, new)
    return dict(old=old, new=new, facing=fac, spF=spF, disp=disp, ok=ok, why=why,
                rho=perp_dist_to_S(old, fac))


def snapshot_walk(sticks, nmax=18):
    """Walk the rest seed (C-down), returning a clone at the START of each frame (so all cut frames N
    come from one walk)."""
    s = seed()
    snaps = []
    for k in range(nmax):
        snaps.append(s.clone())
        stk = sticks[k] if k < len(sticks) else sticks[-1]
        s.step(stk[0], stk[1], csx=128, csy=CDOWN)
    return snaps


def cut_at(snap, aim=None):
    c = snap.clone()
    old = (c.pos_x, c.pos_z); fac, spF = c.facing, c.speedF
    try:
        c.enter_cut(CUT_F, aim=aim)
    except Exception:
        return None
    new = (c.pos_x, c.pos_z)
    ok, why = genuine_clip(old, new)
    return dict(old=old, new=new, facing=fac, spF=spF,
                disp=math.hypot(new[0] - old[0], new[1] - old[1]),
                ok=ok, why=why, rho=perp_dist_to_S(old, fac))


def perp_ray(old, new):
    """Signed perpendicular distance from S to the ACTUAL cut ray old->new (table-exact geometry).
    ~0 for a clip. This is the correct razor quantity (unlike `perp_dist_to_S`, which uses continuous
    trig for the direction and is offset by the >>4 console table -- fine as a rough label, not a
    predictor). A clip needs |perp_ray| inside the seam's ~2e-4u f32 sliver at the walk facing."""
    dx, dz = new[0] - old[0], new[1] - old[1]
    L = math.hypot(dx, dz) or 1.0
    return ((SEAM[0] - old[0]) * dz - (SEAM[1] - old[1]) * dx) / L


def perp_margin(old, new):
    """Delivery-robustness metric: the contiguous perp half-window at `old` (fresh in-line lunge), in
    +-2e-5u steps -- how far `old` can shift PERPENDICULAR and still clip. This is what the walk-entry
    foot residual eats: the residual is ALONG travel, but a TURNING walk (needed to thread the razor)
    freezes a blend-frame toe-stream error whose PERP component (~1-2e-4u, walk-dependent) is the
    threat. A hit delivers only if this margin exceeds that perp residual (see the module docstring /
    dead-end #28: for the clipping arc walk the residual EXCEEDS the ~1e-4u margin -> blocked)."""
    a = math.atan2(new[0] - old[0], new[1] - old[1])
    pdx, pdz = -math.cos(a), math.sin(a)
    lunge = (_f(new[0] - old[0]), _f(new[1] - old[1]))

    def clips(k):
        o2 = (_f(old[0] + _f(k * 2e-5 * pdx)), _f(old[1] + _f(k * 2e-5 * pdz)))
        n2 = (_f(o2[0] + lunge[0]), _f(o2[1] + lunge[1]))
        return genuine_clip(o2, n2)[0]

    if not clips(0):
        return -1
    p = 0
    while p < 40 and clips(p + 1):
        p += 1
    n = 0
    while n < 40 and clips(-(n + 1)):
        n += 1
    return min(p, n)


# --- the dust solver (ported from harness.rollstab.solver; walk-N-then-cut form) -----------------
_BEAR_S = None
CRAWLS = ((0.72, 0.72), (0.6, 0.72), (0.72, 0.6), (0.66, 0.66), (0.6,))
LEADS_DURS = ((5, 3), (4, 3), (5, 2), (4, 2))
OFFS = (800, 900, 1000, 700, 600, 1100, 400, 0)
WIN_LO, WIN_HI = 34.5, 40.35
NMAX = 15
HITS_PATH = os.path.join(_rb, '_generated', 'walkstab_hits.json')


def bear_to_S():
    """Bearing from the anchor's start to S (s16) -- centers the beta sweep (no hardcode)."""
    global _BEAR_S
    if _BEAR_S is None:
        s = seed()
        _BEAR_S = int((math.atan2(SEAM[0] - s.pos_x, SEAM[1] - s.pos_z) % (2 * math.pi))
                      / (2 * math.pi) * 65536)
    return _BEAR_S


def _dtm(stk):
    return C.dtm_stick(stk)


def build_stream(beta, crawl_msds, off, lead, dur, fframe=None, fdx=0, fdz=0):
    """Walk stream: [start-crawl msds] + full-mag cruise at `beta`, a bearing ARC (off-aim `off` for
    `dur` frames at `lead`, the gross perp knob), and an optional per-byte FINE nudge (fdx,fdz) at
    `fframe` -- THE fine f32-lottery (bearing->stick octagon-clamping makes `off` coarse)."""
    cs = seed().csangle
    cruise = _dtm(stick_for_bearing(beta, cs, 1.0))
    sticks = [_dtm(stick_for_bearing(beta, cs, m)) for m in crawl_msds] + [cruise] * 30
    astk = _dtm(stick_for_bearing((beta + off) & 0xFFFF, cs, 1.0))
    for d in range(dur):
        sticks[lead + d] = astk
    if fframe is not None and (fdx or fdz):
        b = sticks[fframe]
        sticks[fframe] = (b[0] + fdx, b[1] + fdz)
    return sticks


def _cut_all(sticks, base, base_k):
    """Continue the C-down walk from `base` (already `base_k` frames in) to NMAX, cutting in-window."""
    s = base.clone()
    snaps = []
    for k in range(base_k, NMAX + 1):
        snaps.append((k, s.clone()))
        if k < NMAX:
            s.step(sticks[k][0], sticks[k][1], csx=128, csy=CDOWN)
    out = []
    for (k, snap) in snaps:
        if k < 10:
            continue
        r = cut_at(snap)
        if r is None:
            continue
        dd = math.hypot(SEAM[0] - r['old'][0], SEAM[1] - r['old'][1])
        if WIN_LO <= dd <= WIN_HI:
            out.append((k, dd, r))
    return out


def _beta_spiral(center, half, step):
    yield center
    d = step
    while d <= half:
        yield center + d
        yield center - d
        d += step


def solve(budget=110.0, want=20, verbose=True):
    """One-shot dust search from the anchor seed (pure sim, no calibration). Enumerates distinct C-down
    walk streams (beta spiral around bearing-to-S | crawl | arc | per-byte fine nudge | N) and tests
    the EXACT genuine_clip -- the acceptance is f32 dust, so this is enumerate-and-test, not threading.
    Collects unique clips, ranks by perp_margin, writes HITS_PATH. Returns the ranked hits.

    NOTE (dead-end #28): a found hit is a GENUINE offline clip (0-ULP), but LIVE delivery is currently
    BLOCKED by the walk-entry foot residual -- the clipping walk must TURN to thread the razor, which
    freezes a blend-frame toe-stream error whose perp component (~1-2e-4u) exceeds the ~1e-4u perp
    margin. The objective-compliant fix is to MODEL that residual (Phase-R), not to calibrate."""
    t0 = time.time()
    c = bear_to_S()
    if verbose:
        print('bearing Link->S=%d; spiral beta around %d' % (c, c - 24), flush=True)
    clips, seen = [], set()
    for beta in _beta_spiral(c - 24, 40, 2):
        if time.time() - t0 > budget or len(clips) >= want:
            break
        cs = seed().csangle
        cruise = _dtm(stick_for_bearing(beta, cs, 1.0))
        for crawl in CRAWLS:
            crawl_sticks = [_dtm(stick_for_bearing(beta, cs, m)) for m in crawl]
            for (lead, dur) in LEADS_DURS:
                base = seed()
                pre = crawl_sticks + [cruise] * 30
                for k in range(lead):
                    base.step(pre[k][0], pre[k][1], csx=128, csy=CDOWN)
                for off in OFFS:
                    for fframe in range(lead, lead + dur):
                        for fdx in range(-4, 5):
                            for fdz in range(-4, 5):
                                sticks = build_stream(beta, crawl, off, lead, dur, fframe, fdx, fdz)
                                for (N, dd, r) in _cut_all(sticks, base, lead):
                                    if r['ok']:
                                        key = (round(r['old'][0], 5), round(r['old'][1], 5))
                                        if key not in seen:
                                            seen.add(key)
                                            clips.append(dict(
                                                beta=beta, crawl=list(crawl), off=off, lead=lead,
                                                dur=dur, fframe=fframe, fdx=fdx, fdz=fdz, N=N,
                                                d2S=dd, old=list(r['old']), new=list(r['new']),
                                                facing=r['facing'], disp=r['disp'],
                                                perp=perp_ray(r['old'], r['new'])))
                    if time.time() - t0 > budget or len(clips) >= want:
                        break
                if time.time() - t0 > budget or len(clips) >= want:
                    break
            if time.time() - t0 > budget or len(clips) >= want:
                break
    for h in clips:
        h['margin'] = perp_margin(h['old'], h['new'])
    clips.sort(key=lambda h: -h['margin'])
    os.makedirs(os.path.dirname(HITS_PATH), exist_ok=True)
    json.dump(clips, open(HITS_PATH, 'w'), indent=1)
    if verbose:
        print('%d unique clips in %.1fs -> %s. top by perp margin:'
              % (len(clips), time.time() - t0, HITS_PATH), flush=True)
        for h in clips[:8]:
            print('  margin=%d beta=%d crawl=%s arc(off=%+d,l%d,d%d) fine(f%d,%+d,%+d) N=%d d2S=%.2f '
                  'facing=%d disp=%.3f old=(%.6f,%.6f)'
                  % (h['margin'], h['beta'], h['crawl'], h['off'], h['lead'], h['dur'], h['fframe'],
                     h['fdx'], h['fdz'], h['N'], h['d2S'], h['facing'], h['disp'],
                     h['old'][0], h['old'][1]))
    return clips


def reachability(beta=5730, mag=1.0, nmax=15):
    """Print the C-down walk's per-frame (facing, speedF, old_d2S, rho) at aim `beta` -- the map the
    solver threads. facing settles at the stick-decode-quantized aim; `rho` at the along-correct
    frame is the razor to thread with the arc."""
    cr = stick_for_bearing(beta, seed().csangle, mag)
    snaps = snapshot_walk([cr] * (nmax + 1), nmax=nmax + 1)
    print('aim beta=%d mag=%.2f  (facing settles at the quantized decode)' % (beta, mag))
    for N in range(2, nmax):
        r = cut_at(snaps[N])
        if r is None:
            continue
        d2S = math.hypot(SEAM[0] - r['old'][0], SEAM[1] - r['old'][1])
        print('  N=%-2d facing=%d spF=%6.3f old_d2S=%6.2f rho=%+.4f disp=%.3f %s'
              % (N, r['facing'], r['spF'], d2S, r['rho'], r['disp'], r['why']))


def deliver(hit=None, b_frame=7, log_n=22, norelaunch=False, verbose=True):
    """LIVE clean-DTM delivery of a solver hit (C-down every frame; NEVER advancewith). Authors the
    hit's walk stream + a B edge at `b_frame` (the ~4-frame item put-away delay + DTM buffering fires
    CUT_F ~5 frames later), logs per frame, and diffs vs the from-rest sim. Reports the walk residual,
    where CUT_F fires, and whether `old_live` clips (Link falls, proc 39). Per-frame diff -> never
    guess the B frame; read the divergence.

    Returns 0 (clip confirmed) / 2 (blocked -- currently the case: the walk-entry foot residual, see
    dead-end #28) / 1 (no CUT fired). Reads the top hit from HITS_PATH if `hit` is None."""
    from harness.dtm.run_dtm import run_dtm, land_ready
    B_BTN = 0x200
    if hit is None:
        hit = json.load(open(HITS_PATH))[0]
    sticks = build_stream(hit['beta'], tuple(hit['crawl']), hit['off'], hit['lead'], hit['dur'],
                          hit['fframe'], hit['fdx'], hit['fdz'])
    N = hit['N']
    s = C.rest_state(ANCHOR)
    rows = []
    for k in range(N):
        s.step(sticks[k][0], sticks[k][1], csx=128, csy=CDOWN)
        rows.append((s.pos_x, s.pos_z, s.facing & 0xFFFF))
    sold = (s.pos_x, s.pos_z)
    s.enter_cut(CUT_F)
    snew = (s.pos_x, s.pos_z)
    if verbose:
        print('SIM hit: old=(%.7f,%.7f) new=(%.7f,%.7f) genuine=%s' %
              (sold[0], sold[1], snew[0], snew[1], genuine_clip(sold, snew)))
    dtm = [dict(stickX=sticks[k][0] if k < len(sticks) else sticks[-1][0],
                stickY=sticks[k][1] if k < len(sticks) else sticks[-1][1],
                substickX=128, substickY=CDOWN, buttons=(B_BTN if k == b_frame else 0))
           for k in range(18)]
    dtm += [dict(stickX=128, stickY=128, substickX=128, substickY=CDOWN, buttons=0)] * 90
    end = run_dtm(dtm, anchor=ANCHOR, ready=land_ready, relaunch_dolphin=not norelaunch,
                  log_frames=log_n, verbose=verbose)
    live = end['log']
    cut_i = next((i for i, f in enumerate(live) if f['proc'] == 0x42), None)
    if cut_i is None:
        print('NO CUT_F (0x42) -- adjust b_frame'); return 1
    lold = (live[cut_i - 1]['pos_x'], live[cut_i - 1]['pos_z'])
    lnew = (live[cut_i]['pos_x'], live[cut_i]['pos_z'])
    gen, why = genuine_clip(lold, lnew)
    fell = any(f['proc'] in (0x27, 39) for f in live[cut_i:])
    if verbose:
        print('LIVE CUT_F@f%d: old=(%.7f,%.7f) new=(%.7f,%.7f) genuine=%s(%s) fell=%s'
              % (cut_i, lold[0], lold[1], lnew[0], lnew[1], gen, why, fell))
        print('  %s' % ('*** CLIP CONFIRMED LIVE ***' if (gen and fell) else
                        'BLOCKED -- walk-entry foot residual (dead-end #28)'))
    return 0 if (gen and fell) else 2


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'reach'
    if cmd == 'reach':
        reachability()
    elif cmd == 'solve':
        solve()
    elif cmd == 'deliver':
        bf = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('b=')), 7)
        sys.exit(deliver(b_frame=bf, norelaunch=('norelaunch' in sys.argv)))
