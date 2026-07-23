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
"""COARSE-FEASIBILITY report for the Tetra-push planner (session 28) -- the first gating question
the planner must answer before any search: CAN a handful of push cycles herd Tetra the full
distance from state 2 to the genuine `tetra_placements.tsv` clip cluster, in the plow regime this
model covers?

It answers that from the EXACT (0-ULP, session-27) `FreeRun` window -- NO search, NO offline
long-rollout (which the f1 seed-frame drift would dominate past ~2 cycles; see the README planner
box + `onestep_divergence`). The argument is directional + per-cycle + regime, all read off the
bit-exact 2-cycle capture:

  * HERD DIRECTION -- the recorded 2-cycle window herds Tetra ~545 u at a bearing that is within a
    fraction of a degree of the bearing from Tetra's state-2 start to the genuine-coord cluster
    centroid. The natural push direction ALREADY points at the clip region (state 2 was set up for
    exactly this shove), so the multi-cycle plan is a near-straight herd, not a steer-around.
  * PER-CYCLE REACH -- each cycle moves Tetra a few hundred u; the cluster is <~1000 u away, so a
    small number of cycles (~3-5) covers it.
  * PLOW REGIME -- the Link<->Tetra distance stays well under `FOLLOW_ENGAGE_DIST` (230 u) the whole
    window (the chase-and-plow oscillation, 40-85 u), so Tetra stays stt-3 (the state this model is
    faithful to) throughout; a well-formed herd that keeps re-plowing every cycle never lets her
    enter the unmodeled stt-4 follow.

VERDICT: coarse feasibility CONFIRMED. What remains (README `## Plan / status`): the f1 seed-frame
exec-centre capture (so an open-loop multi-cycle rollout is 0-ULP, not drift-dominated), then the
exact SEARCH proper (one aim per cycle -> Tetra on a genuine coord + the matching final roll entry).

All numbers are recomputed live from the locked fixtures, so this report cannot silently drift.
CLI: ``python -m harness.tetrapush.feasibility``. Pure stdlib, no Dolphin."""
import math

from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST

from harness.tetrapush import seeds
from harness.tetrapush import primitives as P


def _bearing_deg(dx, dz):
    """World bearing of a +XZ vector, degrees, measured the game's way (0 = +Z, CW toward +X;
    matches `state.py` x += d*sin, z += d*cos)."""
    return math.degrees(math.atan2(dx, dz))


def herd_summary(env):
    """The recorded-window Tetra herd, per cycle and total, from the live capture (bit-exact).
    Returns ``{cycles: [{f0, f1, dist, bearing, truncated}], total: {dist, bearing}, window: (0, N)}``."""
    cyl = env['cyl']
    recs = P.window_records(env)
    spans = P.find_cycles(recs)
    last = recs[-1]['f']

    def _tp(i):
        return cyl[i]['tetra']['pos']

    cycles = []
    prev = 0
    for idx, (s, r, e) in enumerate(spans):
        a, b = _tp(prev), _tp(e)
        cycles.append(dict(
            f0=prev, f1=e, dist=math.hypot(b[0] - a[0], b[2] - a[2]),
            bearing=_bearing_deg(b[0] - a[0], b[2] - a[2]),
            # the last span is truncated at the gated window end (the cyc2 untarget is f45+,
            # single-step-corrupted -- see the from_f0 docstring), so its reach undercounts
            truncated=(idx == len(spans) - 1 and e >= last)))
        prev = e
    t0, tN = _tp(0), _tp(last)
    return dict(cycles=cycles, window=(0, last),
                total=dict(dist=math.hypot(tN[0] - t0[0], tN[2] - t0[2]),
                           bearing=_bearing_deg(tN[0] - t0[0], tN[2] - t0[2]),
                           frm=(t0[0], t0[2]), to=(tN[0], tN[2])))


def target_summary(env):
    """The genuine-coord cluster (`_generated/tetra_placements.tsv`) relative to Tetra's state-2
    start: extent, centroid, near/far distance, and the start->centroid bearing."""
    rows, _ = seeds.load_placements()
    t0 = env['cyl'][0]['tetra']['pos']
    xs = [r['x'] for r in rows]
    zs = [r['z'] for r in rows]
    cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
    dists = sorted(math.hypot(r['x'] - t0[0], r['z'] - t0[2]) for r in rows)
    return dict(n=len(rows), xr=(min(xs), max(xs)), zr=(min(zs), max(zs)),
                centroid=(cx, cz), near=dists[0], far=dists[-1],
                bearing=_bearing_deg(cx - t0[0], cz - t0[2]),
                start=(t0[0], t0[2]))


def regime_bounds(env):
    """Min/max Link<->Tetra feet distance over the recorded window (from the capture). The plow
    model is faithful only while Tetra is stt-3, i.e. below `FOLLOW_ENGAGE_DIST`."""
    cyl = env['cyl']
    n = 0
    lo = hi = None
    for k in range(len(cyl)):
        lp = cyl[k]['link']['pos']
        tp = cyl[k]['tetra']['pos']
        d = math.hypot(lp[0] - tp[0], lp[2] - tp[2])
        lo = d if lo is None else min(lo, d)
        hi = d if hi is None else max(hi, d)
        n = k
    return dict(lo=lo, hi=hi, engage=FOLLOW_ENGAGE_DIST, frames=n + 1)


def main():
    env = seeds.load_env()
    herd = herd_summary(env)
    tgt = target_summary(env)
    reg = regime_bounds(env)

    print("=== Tetra-push COARSE FEASIBILITY (from the bit-exact %d-frame window) ===\n"
          % herd['window'][1])

    print("HERD (recorded, live-exact):")
    for i, c in enumerate(herd['cycles']):
        tag = " [truncated at window end -- undercounts]" if c['truncated'] else ""
        print("  cycle %d  f%d..%-2d  %6.1f u  @ %+.1f deg%s"
              % (i + 1, c['f0'], c['f1'], c['dist'], c['bearing'], tag))
    tt = herd['total']
    print("  TOTAL   f%d..%-2d  %6.1f u  @ %+.1f deg   (%.1f,%.1f)->(%.1f,%.1f)"
          % (herd['window'][0], herd['window'][1], tt['dist'], tt['bearing'],
             tt['frm'][0], tt['frm'][1], tt['to'][0], tt['to'][1]))

    print("\nTARGET (%d genuine clip coords):" % tgt['n'])
    print("  x[%.1f, %.1f]  z[%.1f, %.1f]  centroid (%.1f, %.1f)"
          % (tgt['xr'][0], tgt['xr'][1], tgt['zr'][0], tgt['zr'][1],
             tgt['centroid'][0], tgt['centroid'][1]))
    print("  from Tetra start (%.1f, %.1f): %.1f-%.1f u away, centroid @ %+.1f deg"
          % (tgt['start'][0], tgt['start'][1], tgt['near'], tgt['far'], tgt['bearing']))

    d_bearing = abs(((tt['bearing'] - tgt['bearing']) + 180.0) % 360.0 - 180.0)
    # per-cycle reach: use the non-truncated cycles' mean (fall back to total/ncycles)
    full = [c['dist'] for c in herd['cycles'] if not c['truncated']]
    per_cycle = (sum(full) / len(full)) if full else tt['dist'] / len(herd['cycles'])
    cyc_near = tgt['near'] / per_cycle
    cyc_far = tgt['far'] / per_cycle

    print("\nANALYSIS:")
    print("  herd bearing vs target bearing:   %.1f deg apart" % d_bearing)
    print("  per-cycle reach (full cycles):    ~%.0f u/cycle" % per_cycle)
    print("  cycles to cover %.0f-%.0f u:        ~%.1f-%.1f cycles"
          % (tgt['near'], tgt['far'], cyc_near, cyc_far))
    print("  Link<->Tetra dist over window:    %.1f-%.1f u  (engage %.0f u)"
          % (reg['lo'], reg['hi'], reg['engage']))

    ok_dir = d_bearing < 5.0
    ok_reach = cyc_far <= 8.0
    ok_regime = reg['hi'] < reg['engage']
    verdict = ok_dir and ok_reach and ok_regime
    print("\nVERDICT: coarse feasibility %s" % ("CONFIRMED" if verdict else "NOT established"))
    print("  [%s] direction aligned (<5 deg)   [%s] reachable in <=8 cycles   "
          "[%s] stays in plow regime"
          % ("x" if ok_dir else " ", "x" if ok_reach else " ", "x" if ok_regime else " "))
    print("\nNEXT (README ## Plan / status): capture f0's exec centre (close the f1 seed-frame\n"
          "boundary so an open-loop multi-cycle rollout is 0-ULP), then the exact aim-per-cycle\n"
          "search -> Tetra on a genuine coord + the matching final roll entry.")
    return verdict


if __name__ == '__main__':
    main()
