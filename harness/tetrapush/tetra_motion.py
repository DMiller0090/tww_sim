"""HER STATE AT THE CUT -- the seed-motion axis, and the razor solved in BATCH over it (session 102).

Every pass before this one seeded Tetra AT REST (`ShoveCtx._run`'s `placed_step` wrote a position and
zeroed her speedF and action state), and that is why the placement plane kept reading inert. Her
cut-frame distance is an **EJECTION EQUILIBRIUM**: the plow throws her out at half the overlap per
frame (the shares are 50/50), so at thrust 13's cut frame she lands at |c - t| ~ 87..93 from ANY static
seed inside contact -- measured over a +-40 u ray/lateral grid, where she is displaced 10..60 u during
the roll -- against a requirement of <= 79.4. Inbound follow momentum is the one thing an ejection
cannot undo, so the seed gains three knobs: ``(speedF, facing, stt)``.

WHAT IS AND IS NOT DELIVERABLE ON THIS AXIS (`follow_consistent` -- the clause this axis owes, since
"each axis a search gains needs its own deliverability clause"):

  * ``stt`` must be `STT_MOVE`. In `STT_IDLE` the game has already zeroed her speedF, so a moving idle
    seed is not a state that exists -- and `_run` would happily integrate it forever, because the idle
    branch never touches speedF once the engage test fails.
  * ``speedF`` must be in ``[0, FOLLOW_SPEED_MAX]`` = 10, her follow cap.
  * Near the corner she has NO DRIVE: her target speed is ``0.04*sqrt(dist^2 - 130^2)``, which is zero
    inside 130 u of Link, so the seed speed is RESIDUAL momentum decaying 1.0/frame. It is spent by
    frame `speedF`, and the cut is at frame `cut_step`. So she is not closing AT the cut -- what the
    momentum buys is a different EJECTION HISTORY, i.e. a different place to be standing when the
    animation-posed Co centre swings past her.

The search is a pattern climb on the TRUE objective -- `razor_depth.depth_of` at a razor-solved entry
-- seeded from `razor_depth.contact_required`, the analytic spot the corner needs her in. Ranking a raw
row instead is what two false starts this session both did: `depth_of` alone ignores the other two
`genuine` clauses (it happily returns +13.6 for a Link 86 u out with the endpoint behind a far wall),
and the law's `d_ray` on a raw row silently grants the steering the razor has to pay for.

    python -m harness.tetrapush.tetra_motion screen [cell] [thrust]
    python -m harness.tetrapush.tetra_motion cells [thrust]
"""
import json
import math
import os
import sys
import time
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.rollstab import geometry_tetra as GT
from harness.tetrapush import entry_reach as ER
from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_depth as RD
from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST, FOLLOW_KEEP_DIST, FOLLOW_SPEED_GAIN
from tww_sim.core.npc_zl1 import FOLLOW_SPEED_MAX, STT_MOVE

#: Her follow cap, and the only action state a moving seed can be in (see the module docstring).
SEED_SPEED_MAX = FOLLOW_SPEED_MAX
SEED_STT = STT_MOVE

#: Pattern-climb steps on (tetra x, tetra z, speedF, her facing) and their floors. The placement steps
#: start small because the climb is SEEDED AT THE ANALYTIC TARGET, not hunting for the basin.
CLIMB_STEP0 = (4.0, 4.0, 1.0, 2048.0)
CLIMB_STEP_MIN = (0.01, 0.01, 0.05, 8.0)


def seed_of(speedF, facing):
    """A `ShoveCtx` motion seed, or None for the historical at-rest seed."""
    if speedF is None or speedF <= 0.0:
        return None
    return (float(speedF), int(round(facing)) & 0xFFFF, SEED_STT)


def follow_target_speed(dist):
    """Her follow target speedF at an XZ distance -- zero inside `FOLLOW_KEEP_DIST`, so a seed near
    the corner is residual momentum and not drive."""
    d2 = dist * dist - FOLLOW_KEEP_DIST * FOLLOW_KEEP_DIST
    if d2 <= 0.0:
        return 0.0
    return min(FOLLOW_SPEED_MAX, FOLLOW_SPEED_GAIN * math.sqrt(d2))


def follow_consistent(speedF, stt=SEED_STT):
    """THE CLAUSE. A seed motion the follow model can actually be in: `STT_MOVE`, speedF within her
    cap. Position standability is `razor_depth.placeable`; whether a HERD can leave her in this state
    is the herd search's question, and this is the necessary condition it must satisfy."""
    return stt == SEED_STT and 0.0 <= speedF <= SEED_SPEED_MAX


def contact_of(row, base=None):
    """The cut-frame CONTACT a row delivers: ``dict(cross_len, push_u, push_perp, theta_deg, s_dist)``.

    Free from the row -- ``|push| = share * cross_len`` and Link is shoved straight away from her, so
    the consumed push IS the contact. This is the quantity `razor_depth.contact_required` bounds."""
    old = (row[1], row[2])
    s = math.hypot(GT.S[0] - old[0], GT.S[1] - old[1])
    ux, uz = (GT.S[0] - old[0]) / s, (GT.S[1] - old[1]) / s
    px, pz = row[5], row[6]
    mag = math.hypot(px, pz)
    return dict(cross_len=mag / RD.SHARE_LINK, push_u=px * ux + pz * uz,
                push_perp=px * -uz + pz * ux, s_dist=s,
                theta_deg=math.degrees(math.atan2(abs(px * -uz + pz * ux), px * ux + pz * uz))
                if mag else 0.0, old=[old[0], old[1]])


def surplus_of(row, facing, thrust, lean=RD.DELIVERED_LEAN, depth=RD.DEPTH_FLOOR):
    """HOW MUCH CONTACT THIS ROW HAS AGAINST WHAT ITS OWN BRACE NEEDS -- the rankable scalar.

    ``surplus = cross_len delivered - cross_len required``, both read at the cut-consumed frame: the
    delivered one from the contact pair (`extra` slots 10-13), the required one from the law at this
    row's `old`. Needs an ``extra`` row. Positive means a razor solve has something to converge on.

    Ranking this instead of the depth is what makes a negative honest. The depth alone is not a
    screen -- `genuine` is three clauses, and a raw row 86 u out with its endpoint behind some far
    wall reads +13.6 -- while the surplus is scoped to the corner by construction, because the
    requirement is computed at the brace the row actually produced."""
    sx, sz = GT.S[0] - row[1], GT.S[1] - row[2]
    s = math.hypot(sx, sz)
    ux, uz = sx / s, sz / s
    px, pz = -uz, ux
    kappa = max(abs(GT.wA.pla.nx * ux + GT.wA.pla.nz * uz),
                abs(GT.wB.pla.nx * ux + GT.wB.pla.nz * uz))
    mx = ES.ML.cM_ssin_s16(int(facing) & 0xFFFF)
    mz = ES.ML.cM_scos_s16(int(facing) & 0xFFFF)
    base = RD.base_reach(facing, lean, thrust)
    g = -base * (mx * px + mz * pz)
    pu = max(s + depth / kappa - base * (mx * ux + mz * uz), 0.0)
    need = math.hypot(pu, g) / RD.SHARE_LINK
    have = RD.CO_R_SUM - math.hypot(row[10] - row[12], row[11] - row[13])
    return dict(surplus=have - need, have=have, need=need, s_dist=s,
                tetra_cut=[row[12], row[13]], co=[row[10], row[11]])


def razor_batch(ctx, resid, cands, iters=40, tol=1e-6, d=0.01):
    """`entry_search.zero_the_resid` for MANY candidates at once -- one `sweep_par` per iteration.

    ``cands`` = [(tetra, entry_start, seed)]. Returns [(entry, resid, grad, row)]. The Newton step is
    the scalar function's, term for term, so a batched solve IS the scalar one (gated:
    `tests/test_tetra_motion.py::test_the_batched_razor_solve_is_the_scalar_one`) -- which matters
    because a pattern climb needs every trial direction evaluated in the same sweep or the Python
    overhead, not the physics, sets the throughput."""
    p = [list(c[1]) for c in cands]
    live = list(range(len(cands)))
    out_r = [(0.0, 0.0)] * len(cands)
    for _ in range(iters):
        items = []
        for i in live:
            t, _e, sd = cands[i]
            spd, ang, stt = (0.0, 0, -1) if sd is None else sd
            items.append((t[0], t[1], p[i][0], p[i][1], spd, ang, stt))
            items.append((t[0], t[1], p[i][0] + d, p[i][1], spd, ang, stt))
            items.append((t[0], t[1], p[i][0], p[i][1] + d, spd, ang, stt))
        rows = ctx.sweep_par(items, 0)
        nxt = []
        for j, i in enumerate(live):
            r0 = resid(rows[3 * j])
            gx = (resid(rows[3 * j + 1]) - r0) / d
            gz = (resid(rows[3 * j + 2]) - r0) / d
            g = math.hypot(gx, gz)
            out_r[i] = (r0, g)
            if abs(r0) < tol or g == 0.0:
                continue
            s = r0 / (g * g)
            p[i] = [p[i][0] - s * gx, p[i][1] - s * gz]
            nxt.append(i)
        live = nxt
        if not live:
            break
    final = ctx.sweep_par([(cands[i][0][0], cands[i][0][1], p[i][0], p[i][1])
                          + ((0.0, 0, -1) if cands[i][2] is None else cands[i][2])
                          for i in range(len(cands))], 0, extra=True)
    return [(tuple(p[i]), out_r[i][0], out_r[i][1], final[i]) for i in range(len(cands))]


def target_spot(row, facing, thrust, lean=RD.DELIVERED_LEAN, depth=RD.DEPTH_FLOOR, margin=0.0):
    """WHERE SHE HAS TO BE STANDING on the cut-consumed frame, for THIS row's brace and Co centre.

    `razor_depth.contact_required` answers this for an idealised brace; this answers it for the one
    the run actually produced, which is what an inverse solve needs. Uses the row's own Co centre
    (slots 10/11 of an ``extra`` row) rather than an assumed pose, so the animation phase is taken from the engine.
    ``margin`` buys depth above the floor. Returns ``(t_star, cross_req, push_vec)`` or None."""
    old = (row[1], row[2])
    s = math.hypot(GT.S[0] - old[0], GT.S[1] - old[1])
    ux, uz = (GT.S[0] - old[0]) / s, (GT.S[1] - old[1]) / s
    px, pz = -uz, ux
    kappa = max(abs(GT.wA.pla.nx * ux + GT.wA.pla.nz * uz),
                abs(GT.wB.pla.nx * ux + GT.wB.pla.nz * uz))
    mx = ES.ML.cM_ssin_s16(int(facing) & 0xFFFF)
    mz = ES.ML.cM_scos_s16(int(facing) & 0xFFFF)
    base = RD.base_reach(facing, lean, thrust)
    g = -base * (mx * px + mz * pz)
    pu = s + depth / kappa - base * (mx * ux + mz * uz) + margin
    if pu <= 0.0:
        pu = margin if margin > 0.0 else 1e-4
    vx, vz = pu * ux + g * px, pu * uz + g * pz
    mag = math.hypot(vx, vz)
    cross = mag / RD.SHARE_LINK
    if cross >= RD.CO_R_SUM:
        return None
    c = (row[10], row[11])
    d = RD.CO_R_SUM - cross
    return ((c[0] - d * vx / mag, c[1] - d * vz / mag), cross, (vx, vz))


def solve_placement(ctx, resid, facing, thrust, lean, seed_motion, entry0, tetra0, margin=0.0,
                    outer=24, relax=1.0, tol=1e-4):
    """FIXED-POINT ON HER SEED: place her so the ROLL leaves her where the corner needs her.

    Seeding her at the required spot does not put her there -- the plow displaces her 10..60 u during
    the roll, which is the ejection equilibrium every static scan has been reading. But the engine now
    reports both ends of that map (slots 12/13 of an ``extra`` row are where she actually stands on
    the cut-consumed frame), so the correction is just ``seed -= (t_cut - t_star)`` iterated, with the entry razor-
    solved inside every step. Out of contact the map is the IDENTITY -- she does not move at rest --
    so the iteration is well conditioned exactly where a climb on the depth goes flat.

    Returns ``dict(tetra, entry, resid, grad, row, err, t_star, cross_req)`` or None."""
    tet = list(tetra0)
    e = tuple(entry0)
    last = None
    for _ in range(outer):
        entry, rr, gr, row = razor_batch(ctx, resid, [((tet[0], tet[1]), e, seed_motion)])[0]
        e = entry
        tgt = target_spot(row, facing, thrust, lean, margin=margin)
        if tgt is None:
            return None
        t_star, cross_req, _pv = tgt
        t_cut = (row[12], row[13])
        ex, ez = t_cut[0] - t_star[0], t_cut[1] - t_star[1]
        last = dict(tetra=[tet[0], tet[1]], entry=list(entry), resid=rr, grad=gr, row=row,
                    err=math.hypot(ex, ez), t_star=[t_star[0], t_star[1]], cross_req=cross_req)
        if last['err'] < tol:
            break
        tet = [tet[0] - relax * ex, tet[1] - relax * ez]
    return last


def _score(v, res, tol=1e-3):
    """The climb's objective: the razor-solved depth, walled off from anything undeliverable."""
    entry, rr, gr, row = res
    if not RD.placeable((v[0], v[1])):
        return -9.9
    if not follow_consistent(max(0.0, v[2])):
        return -9.9
    if abs(rr) > tol or gr < ER.LEVERAGE_MIN:
        return -9.9
    q = GT.p32(row[1], row[2])
    if not (GT.wA.pla.func(q) > 0.0 and GT.wB.pla.func(q) > 0.0):
        return -9.9
    if math.hypot(GT.S[0] - row[1], GT.S[1] - row[2]) > 56.0:
        return -9.9
    return RD.depth_of(row)


def climb(ctx, resid, start, entry0, iters=600, step0=CLIMB_STEP0, step_min=CLIMB_STEP_MIN):
    """Pattern search on (tetra x, tetra z, speedF, her facing), entry razor-solved every trial.

    Returns ``(depth, vector, (entry, resid, grad, row))``. The entry is NOT a climb knob: it is
    pinned by the razor, and carrying it as a free dimension is what let session 102's first climb
    wander into families whose perpendicular push has the wrong sign to ever be a solution."""
    v = list(start)
    step = list(step0)
    cur = razor_batch(ctx, resid, [((v[0], v[1]), entry0, seed_of(v[2], v[3]))])[0]
    best = _score(v, cur)
    n = 0
    while n < iters and any(step[i] > step_min[i] for i in range(4)):
        trials = []
        for i in range(4):
            for sgn in (1.0, -1.0):
                w = list(v)
                w[i] += sgn * step[i]
                trials.append(w)
        res = razor_batch(ctx, resid, [((w[0], w[1]), cur[0], seed_of(w[2], w[3]))
                                       for w in trials])
        n += len(trials)
        sc = [_score(trials[j], res[j]) for j in range(len(trials))]
        j = max(range(len(sc)), key=lambda q: sc[q])
        if sc[j] > best:
            best, v, cur = sc[j], trials[j], res[j]
        else:
            step = [max(step_min[i], step[i] * 0.5) for i in range(4)]
    return best, v, cur


def entry_starts(facing, thrust, lean, target, n_seed=3, travel=(150.0, 430.0), t_step=6.0,
                 lat=40.0, lat_step=8.0):
    """Entry seeds for the Newton: the brace backed off along the roll's own direction over the whole
    travel range (the ARRIVE family at ~26*cut_step as well as the arrive-early-and-slide one), taken
    in |resid| order at the target placement so the solve starts near the curve rather than at a
    corner of a box."""
    ctx, sch, resid = ES.build_fast(facing, lean, thrust)
    k = sch['cut_step']
    mx, mz = sch['dx'][k] + sch['cutx'][k], sch['dz'][k] + sch['cutz'][k]
    bd = math.hypot(mx, mz)
    rx, rz, qx, qz = mx / bd, mz / bd, -mz / bd, mx / bd
    brace = RD.brace_point(35.0, 35.0)
    pts, t = [], travel[0]
    while t <= travel[1] + 1e-9:
        o = -lat
        while o <= lat + 1e-9:
            pts.append((brace[0] - t * rx + o * qx, brace[1] - t * rz + o * qz))
            o += lat_step
        t += t_step
    out = ctx.sweep_par([(target[0], target[1], p[0], p[1]) for p in pts], 0)
    order = sorted(range(len(pts)), key=lambda i: abs(resid(out[i])))
    keep, seen = [], []
    for i in order:
        if any(math.hypot(pts[i][0] - q[0], pts[i][1] - q[1]) < 30.0 for q in seen):
            continue
        seen.append(pts[i])
        keep.append(pts[i])
        if len(keep) >= n_seed:
            break
    return keep


def screen(facing, thrust, lean=RD.DELIVERED_LEAN, halo=24.0, halo_step=8.0, speeds=(0.0, 3.0, 6.0,
           9.0), aim_step=0x2000, progress=False):
    """THE DEEPEST CLIP ONE AIM CELL CAN BUY WITH HER IN MOTION -- razor-solved, placement-clamped.

    Seeded at `razor_depth.contact_required`'s analytic spot (plus a `halo` grid around it and every
    entry family), then climbed on the true depth. Returns the best row or None."""
    req = RD.contact_required(facing, thrust, lean)
    if req is None:
        return None
    ctx, sch, resid = ES.build_fast(facing, lean, thrust)
    tgt = (req['tetra'][0], req['tetra'][1])
    e0 = entry_starts(facing, thrust, lean, tgt)
    aims = list(range(0, 0x10000, aim_step))
    best = None
    n = int(2 * halo / halo_step) + 1
    for i in range(n):
        for j in range(n):
            tet = (tgt[0] - halo + i * halo_step, tgt[1] - halo + j * halo_step)
            if not RD.placeable(tet):
                continue
            for spd in speeds:
                for a in (aims if spd > 0.0 else [0]):
                    for e in e0:
                        d, v, cur = climb(ctx, resid, [tet[0], tet[1], spd, float(a)], e)
                        if d > -9.0 and (best is None or d > best['depth']):
                            c = contact_of(cur[3])
                            best = dict(depth=d, tetra=[v[0], v[1]], speedF=v[2],
                                        seed_facing=int(round(v[3])) & 0xFFFF, entry=list(cur[0]),
                                        resid=cur[1], grad=cur[2], genuine=bool(cur[3][0]),
                                        facing=int(facing) & 0xFFFF, thrust=thrust, required=req,
                                        **c)
                            if progress:
                                print("    depth %+.5f cross_len %.4f (need %.4f) theta %.1f"
                                      " |S-old| %.4f spd %.2f aim %d"
                                      % (d, c['cross_len'], req['cross_len'], c['theta_deg'],
                                         c['s_dist'], v[2], int(round(v[3])) & 0xFFFF), flush=True)
    return best


# --------------------------------------------------------------------------- CLI

def _cells():
    return {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}


def _cmd_screen(argv):
    cell = int(argv[0]) if argv else 2552
    thrust = int(argv[1]) if len(argv) > 1 else 13
    facing = _cells()[cell]
    t0 = time.time()
    b = screen(facing, thrust, progress=True)
    print("cell %d (facing %d) thrust %d -- plan_cost %d"
          % (cell, facing, thrust, ER.FLOOR_FRAMES + thrust + 4))
    if b is None:
        print("  no razor solution with a placeable, follow-consistent seed")
    else:
        print("  BEST depth %+.6f (floor %+.4f) -> %s"
              % (b['depth'], RD.DEPTH_FLOOR, 'CLEARS' if b['depth'] >= RD.DEPTH_FLOOR else 'SHORT'))
        print("  cross_len %.4f against the required %.4f; theta %.1f deg, |S-old| %.4f"
              % (b['cross_len'], b['required']['cross_len'], b['theta_deg'], b['s_dist']))
        print("  tetra (%.6f, %.6f) speedF %.3f facing %d | entry (%.6f, %.6f) resid %.2e"
              % (b['tetra'][0], b['tetra'][1], b['speedF'], b['seed_facing'], b['entry'][0],
                 b['entry'][1], b['resid']))
    print("  [%.0f s]" % (time.time() - t0))


def _cmd_cells(argv):
    thrust = int(argv[0]) if argv else 13
    by = _cells()
    t0, rows = time.time(), []
    for cell in sorted(by):
        req = RD.contact_required(by[cell], thrust)
        b = screen(by[cell], thrust)
        rows.append(dict(cell=cell, facing=by[cell], required=req and req['cross_len'],
                         best=b and b['depth'], cross_len=b and b['cross_len']))
        print("  cell %d: required cross_len %s, best depth %s (cross_len %s)"
              % (cell, '%.4f' % req['cross_len'] if req else 'n/a',
                 '%+.5f' % b['depth'] if b else 'none', '%.4f' % b['cross_len'] if b else 'n/a'),
              flush=True)
    out = os.path.join(_rb, '_generated', 's102', 'motion_cells_t%d.json' % thrust)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(source='harness.tetra_motion.screen', thrust=thrust, rows=rows,
                   seconds=time.time() - t0), open(out, 'w'), indent=1)
    have = [r for r in rows if r['best'] is not None]
    print("wrote %s -- %d of %d cells solved, best %+.5f  [%.0f s]"
          % (out, len(have), len(rows), max([r['best'] for r in have] or [float('nan')]),
             time.time() - t0))


def main(argv=None):
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'screen'
    if cmd == 'screen':
        _cmd_screen(argv)
    elif cmd == 'cells':
        _cmd_cells(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
