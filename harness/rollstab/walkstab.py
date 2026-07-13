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

SOLVER (OPEN -- the next build): the razor `rho` needs the roll-stab dust knobs (harness.rollstab.
solver.py): a 1-frame ARC (off-aim stick at a low-speed frame) threads `rho` sub-s16, and START-CRAWL
partials densify the ALONG placement (full-mag frames step ~17u, skipping the ~0.5u clipping old-band
for disp 40.22). `search_arc` below threads `rho` (the proven half); the along densification +
fixpoint placement + the sub-2-min budget are TODO. Then DTM-verify (clean DTM, C-down, never
advancewith), per-frame diff.
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


def search_arc(betas=range(5700, 5760, 4), mag=1.0, arc_frames=(2, 3, 4),
               darange=range(-8, 9), n_range=range(9, 14), verbose=True):
    """PROVEN HALF: full-mag cruise + a 1-frame arc threads the razor `rho` toward 0. Returns any
    exact clips + the min-|rho| in-play candidate. NOTE the ALONG densification (start-crawl) is not
    yet wired, so old lands on the 17u full-mag lattice (skips the ~0.5u clipping band for disp
    40.22) -- expect min-|rho| near the razor but few/no exact clips until start-crawl lands old on
    the band. See the module docstring."""
    t0 = time.time()
    clips, best, tested = [], None, 0
    for beta in betas:
        cr = stick_for_bearing(beta, seed().csangle, mag)
        for af in arc_frames:
            for dsx in darange:
                for dsz in darange:
                    sticks = [cr] * 20
                    sticks[af] = (cr[0] + dsx, cr[1] + dsz)
                    snaps = snapshot_walk(sticks, nmax=max(n_range) + 1)
                    for N in n_range:
                        r = cut_at(snaps[N]); tested += 1
                        if r is None:
                            continue
                        if r['ok']:
                            clips.append((beta, af, dsx, dsz, N, r))
                        d2S = math.hypot(SEAM[0] - r['old'][0], SEAM[1] - r['old'][1])
                        if 36 < d2S < 44 and (best is None or abs(r['rho']) < abs(best[-1]['rho'])):
                            best = (beta, af, dsx, dsz, N, r)
    if verbose:
        print('tested %d in %.1fs  exact clips=%d' % (tested, time.time() - t0, len(clips)))
        if best:
            b, af, dx, dz, N, r = best
            print('min|rho|=%.6f (razor ~6e-4) beta=%d arc=f%d(%+d,%+d) N=%d facing=%d spF=%.3f '
                  'disp=%.3f old_d2S=%.3f why=%s' % (abs(r['rho']), b, af, dx, dz, N, r['facing'],
                  r['spF'], r['disp'], math.hypot(SEAM[0]-r['old'][0], SEAM[1]-r['old'][1]), r['why']))
    return clips, best


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


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'reach'
    if cmd == 'reach':
        reachability()
    elif cmd == 'search':
        search_arc()
