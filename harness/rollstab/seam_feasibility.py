"""Is a seam roll-clippable, and AT WHICH AIM? -- a full-aim-circle f32 feasibility probe.

WHY THIS EXISTS (session 51): session 50 ruled the 97-deg corner S=(13539.24,493.36) "NOT
roll-clippable at any displacement" using tools that swept aim only `dir +-15deg` around the
INTO-CORNER bisector. That was WRONG: the seam IS clippable, its genuine gap sitting at a ~90-deg
GRAZING aim (~41deg off the bisector) that no sweep reached (dead-end ledger, "A sharp corner's
clippable aim can be FAR off the bisector"). The lesson: a feasibility check MUST sweep the FULL
aim circle at TRUE f32 perp resolution -- a coarse perp step reads 0 even for the PROVEN/mirror
seams (the genuine acceptance is single ~0.001u f32 columns), and a bisector-only aim misses
off-bisector gaps.

This probe scans `SeamGeo.pred_genuine` (the EXACT sim cut acceptance, bit-identical to
LandState.enter_cut) over (along, perp) at each facing across the whole circle, so it answers
both "is this seam clippable at all?" and "at what aim does its razor sit?" -- the aim to pass as
`SeamGeo(aim_deg=)` and to mint an anchor toward. It is the correct front-end to a novel-seam pick
(run it BEFORE minting; a nonzero genuine count at some aim == a real, if precise, target).

    python -m harness.rollstab.seam_feasibility geo=fixtures/kaze_r11_seam_mirror_geo.json
    python -m harness.rollstab.seam_feasibility geo=<fixture> anchor=<any kaze anchor> [fstep=2048]
"""
import os, sys, json, math, time
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.core.fp import f32 as _f
from harness.rollstab.seamgeo import SeamGeo
from harness.rollstab.geometry import load_seed


def scan_aim(seam, F, perp_w=2.0, pstep=0.001, astep=0.3, along_frac=(0.5, 1.05), speedf=None):
    """Genuine f32 dust for a roll-stab firing its CUT at facing `F`. Places `old` at
    `S - along*dir(F) + perp*perp(F)` over the reach band and tests the EXACT `pred_genuine`
    (== the sim cut). f32 resolution in perp is LOAD-BEARING (coarse steps miss the ~0.001u
    columns). Returns (count, [(along, perp, old_x, old_z), ...])."""
    Sx, Sz = seam.S
    reach = seam.reach_at(speedf)
    r = (F & 0xFFFF) / 65536.0 * 2 * math.pi
    dx, dz = math.sin(r), math.cos(r)
    px, pz = -dz, dx
    hits = []
    a = reach * along_frac[0]
    while a <= reach * along_frac[1]:
        p = -perp_w
        while p <= perp_w:
            ox, oz = _f(Sx - a * dx + p * px), _f(Sz - a * dz + p * pz)
            if seam.pred_genuine((ox, oz), facing=(F & 0xFFFF), speedf=speedf):
                hits.append((a, p, float(ox), float(oz)))
            p += pstep
        a += astep
    return len(hits), hits


WALL_R = 35.0   # Link's roll wall-cylinder radius (WallCorrect wall_r, collision.py): his center is held
                # >= this from every incident wall, so dust within WALL_R of a wall is unreachable by a roll.


def wall_reach(seam, hits, wall_r=WALL_R):
    """Nearest-incident-wall distance of each genuine `old` (from scan_aim), and how many are REACHABLE
    (nearest-wall dist >= wall_r). Returns (n_reachable, min_d, max_d). NB scan_aim's default perp_w=2.0
    only samples near the ray-through-S; reachable dust (if any) sits further out, so 0-reachable here
    means 'none near the razor' -- confirm with a WIDE-perp scan before concluding (see the s52 reachscan)."""
    ds = [min(seam.wA.pla.func(seam.p32(ox, oz)), seam.wB.pla.func(seam.p32(ox, oz)))
          for _a, _p, ox, oz in hits]
    if not ds:
        return 0, None, None
    return sum(1 for d in ds if d >= wall_r), min(ds), max(ds)


def feasible_aims(seam, fstep=2048, budget=140.0, verbose=True, **scan_kw):
    """Sweep the FULL aim circle; return the facings whose roll-stab has genuine dust, most first.
    A coarse facing step FLAGS candidate aims (the razor spans a few hundred s16 in aim); refine a
    flagged aim with `scan_aim` at a finer facing/perp grid to characterize + locate its `old`."""
    t0 = time.time()
    found = []
    for F in range(0, 65536, fstep):
        n, _ = scan_aim(seam, F, **scan_kw)
        if n:
            found.append((F, n))
            if verbose:
                print('  aim F=%5d (%.1fdeg): genuine=%d' % (F, F / 65536 * 360, n), flush=True)
        if time.time() - t0 > budget:
            if verbose:
                print('  ...budget cutoff at F=%d' % F, flush=True)
            break
    found.sort(key=lambda x: -x[1])
    if verbose:
        if found:
            print('CLIPPABLE at %d aim(s); best F=%d (%.1fdeg, genuine=%d). Derived bisector F=%d.'
                  % (len(found), found[0][0], found[0][0] / 65536 * 360, found[0][1], seam.F),
                  flush=True)
        else:
            print('NO genuine dust at any swept aim (fstep=%d) -- likely truly infeasible; '
                  'try a finer fstep before concluding.' % fstep, flush=True)
    return found


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    anchor = o.get('anchor', 'kaze_r11_rollstab_mirror@twwgz')
    cs = load_seed(anchor)['csangle'] & 0xFFFF
    seam = SeamGeo(json.load(open(o['geo'])), cs)
    print('seam interior=%.2f bisector-derived F=%d reach=%.3f'
          % (seam.geo.get('interior', -1), seam.F, seam.reach), flush=True)
    aims = feasible_aims(seam, fstep=int(o.get('fstep', 2048)))
    if aims:
        Fb = aims[0][0]
        n, hits = scan_aim(seam, Fb, pstep=0.0005, astep=0.1)
        print('refine F=%d: %d f32 points' % (Fb, n))
        for a, p, ox, oz in hits[:8]:
            print('   along=%.2f perp=%+.4f old=(%.5f,%.5f) d2S=%.2f'
                  % (a, p, ox, oz, math.hypot(ox - seam.S[0], oz - seam.S[1])))
        nr, dmin, dmax = wall_reach(seam, hits)
        if dmin is not None:
            print('REACHABILITY: dust nearest-wall dist %.2f..%.2f u (roll hold ~%.0fu); %d/%d reachable.'
                  % (dmin, dmax, WALL_R, nr, len(hits)))
            if nr == 0:
                print('  -> clippable but the dust HUGS a wall: NOT reachable near the razor. Before minting,'
                      ' run a WIDE-perp reachability scan + relax wall_faithful for concave touches / verify'
                      ' the hold live (session-52 97-deg corner; see the dead-end ledger).')
