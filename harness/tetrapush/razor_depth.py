"""WHICH THRUSTS THIS CORNER CAN CLIP AT ALL -- the depth-at-the-razor law (session 100).

Session 99 found the frame-minimal objective had never charged for the B thrust (`entry_fan.plan_frames`
counts WALK HOLDS only) and that `procFrontRoll`'s cut gate makes **thrust 13** the floor, so the
delivered clip presses B two frames late. Its handoff named the Tetra placement as the route to those
frames, on the reasoning that the reachable hull depends on Link's facing while HER placement moves the
residual locus relative to it. Measured, the placement is not the lever and the frames are not both
there -- and both facts come out of one scalar law.

THE LAW. `genuine` needs the post-CrrPos cut endpoint BEHIND a wall plane, so write the penetration as

    depth  =  -min(planeA(pred), planeB(pred))          `sweep_par` slots 8/9, `depth_of`

and note what `resid ~ 0` does to it. **S is the corner VERTEX, which lies on BOTH wall planes**, so a
razor solution -- the cut segment pointing at S -- forces `pred` onto the ``old -> S`` ray and leaves

    depth  ~  |base + push|  -  |S - old|               (up to the ray/normal projection)

where `base` (the roll step plus the cut root translate) is a constant per facing. So the depth at the
razor is decided by HOW CLOSE THE ROLL BRACES and HOW MUCH PUSH SURVIVES to the cut frame -- which is
session 99's "brace + the 49.74 u lunge pin the cut start to a 0.65 u pocket", stated as a quantity a
search can rank instead of a bound on the exit angle.

WHAT THAT MEASURES (delivered cell 2552, every in-hull razor solution Newtoned from the whole hull at
0.5 u, 4 and 5 walk frames -- 48 / 45 / 35 solutions):

    thrust 15  cost 23  old (-1692.314331, -955.076111)  |S-old| 49.3812  depth +0.2531..+0.2535
    thrust 14  cost 22  old (-1692.314697, -955.041870)  |S-old| 49.4053  depth +0.2065..+0.2074
    thrust 13  cost 21  old (-1692.317749, -954.737122)  |S-old| 49.6209  depth -0.1868..-0.3464

**HOW TIGHTLY `old` IS PINNED IS ITSELF THE MECHANISM.** At thrust 15 it is BIT-IDENTICAL at every one of
the 48 solutions -- CrrPos has finished sliding Link into the corner by the cut frame, so the entry does
not move it at all. Two frames earlier he is still moving: thrust 14's solutions spread over 4e-4 u of z,
thrust 13's over ~0.07 u with one `old` each. The floor thrust cuts BEFORE the brace, and the lunge is a
constant.

Over the whole 45-cell aim window at the frame floor, thrust 13 reads depth < 0 at **all 25 cells that
have a razor solution at all** (-0.472..-0.133) while thrust 14 admits at 23 of 25 -- so **thrust 14 at
`plan_cost` 22 is a frame available with nothing else changed**. Because thrust 13's `old` is not pinned,
that negative rests on how finely the razor curve was sampled, so it carries its own resolution control:
over grid steps 2.0 / 1.0 / 0.5 / 0.25 the best depth moves inside **0.008 u** and does not trend toward
zero (-0.1949 / -0.1901 / -0.1868 / -0.1898).

**READ EVERY NEGATIVE HERE WITH ITS SET NAMED -- THE HULL IS DOING WORK.** These functions screen over
`entry_reach`'s reachable hull, which sits ~239 u from the corner brace, and a `cut_step` N roll travels
26N u -- so out of that hull Link reaches the wall around step 9 whatever the thrust and CrrPos SLIDES him
along it. The hull therefore contains only the arrive-early-and-slide family, and two fewer slide frames IS
the 0.19 u. Session 100 removed the hull, found entries ~390 u out where the cut fires as Link ARRIVES, and
measured the depth going POSITIVE there (+0.0399 at Tetra 100 u in -z of her console read).

**THAT PLACEMENT IS 3.54 u BEHIND WALL B AND SHE CANNOT STAND IN IT** (session 101, `placeable`). The
engine never checks a seed, so she grazes Link's Co cylinder from inside the wall at a bearing no
reachable spot offers. Constrained to placements a herd can deliver -- at least her 50 u BG wall radius
off both planes, where all 288 live-validated coords sit -- **thrust 13 is refused at every one of the 45
aim cells with no hull anywhere in the search**: best depth -0.0208 at cell 2554, 0.139 u under the floor,
and a 4x finer grid moves it 0.0007. What the arrive family really trades is legible in `law_of`: its
brace is the best on the corner (49.2611) and its push is aimed 75 deg off the ray, because arriving
exactly is giving up the braced frames during which the push is both accumulated and straightened.
See `knowledge/strategy/clip-razor-depth.md`.

WHAT IT IS AND IS NOT. ``depth <= 0`` is a PROOF that a configuration cannot clip: the endpoint is on
the near side of both planes and no razor, camera, lean or candidate volume moves it. ``depth > 0`` is
only an ADMISSION -- dust still has to exist and a plan still has to land on it (`entry_reach.hull_scan`,
then `entry_search.confirm_entry`). It is NOT a density model: measured against session 99's live-station
counts the two do not even correlate (cell 2549 at thrust 15 reads depth +0.513 with 0 live stations,
cell 2553 at thrust 14 reads +0.127 with 918), so read it as a gate and never as a rate.

THE PLACEMENT IS INERT AT HERD SCALE AND DECISIVE AT ROLL SCALE. Over a +-3 u grid of Tetra the thrust-13
depth moves 0.015 u per u (-0.157..-0.217), because she is PLOWED as the roll sweeps past: her cut-frame
overlap is the roll's geometry, not her seed. At the scale a herd tolerates she cannot pay. The
through-going solution above needs her ~100 u away -- a different herd, not a tweak to this one, and that
is the real open question for the second frame.

    python -m harness.tetrapush.razor_depth screen [cell] [thrust] [lean] [frames]
    python -m harness.tetrapush.razor_depth map [step]          # the whole aim window x thrust
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
from tww_sim.core.npc_zl1 import WALL_R as TETRA_WALL_R

#: The delivered clip's lean, and the one every cross-thrust comparison here is measured at.
DELIVERED_LEAN = 64761

#: |base| (roll step + cut root translate) -- a CONSTANT, so a clip is bought with the push's PROJECTION
#: (`law_of`; knowledge/strategy/clip-razor-depth.md). `base_reach` recomputes it per configuration.
BASE_REACH = 49.220224583762864

#: The corner's depth floor, MEASURED over the brace locus (`floor_at_brace`): 0.1154..0.1216, no trend.
#: Screen with this low end; check a survivor against its own brace. knowledge/strategy/clip-razor-depth.md
DEPTH_FLOOR = 0.1150

#: Her BG wall radius -- the bar on a placement the engine does NOT enforce (`placeable`; the 288 live
#: coords clear it by 7 u). knowledge/model/placement-standability.md
TETRA_WALL_MIN = TETRA_WALL_R

#: The Co radius sum and Link's share of the ejection -- the two constants that turn a required push
#: into a required OVERLAP (`contact_required`). The 50/50 split is the live-confirmed dCcS rank table.
CO_R_SUM = ES.LINK_CO_R + ES.TETRA_CO_R
SHARE_LINK = 0.5

#: Newton solves per configuration. The cost is entirely here; seeds are taken in |resid| order so the
#: cap spends itself on the points nearest the curve rather than on a corner of the box.
SOLVE_CAP = 400

#: Solutions closer than this are the same solution reached twice (the curve is marched, not sampled).
SOLUTION_SEP = 0.25


def depth_of(row):
    """The cut endpoint's penetration PAST the nearer wall plane, from a `ShoveCtx.sweep_par` row.

    Slots 8/9 are the two plane functions at `pred`, the PRE-CrrPos endpoint. Positive means the lunge
    gets through; `genuine`'s third clause is this test on the POST-CrrPos endpoint, and the two agree
    whenever the segment is unblocked -- which is the only case where `genuine` can be true anyway
    (gated: `tests/test_razor_depth.py::test_genuine_implies_a_through_going_endpoint`)."""
    return -min(row[8], row[9])


def placeable(tetra):
    """CAN SHE STAND THERE? -- the clause the engine leaves to the caller (see `TETRA_WALL_MIN`).

    Every placement a herd can deliver is at least her BG wall radius off both wall planes, because
    that is where CrrPos would leave her. Session 100's arrive-exactly hit -- the through-going
    endpoint that made both frames look live -- sits **3.54 u BEHIND wall B**, and reads +0.0399 of
    depth precisely because a placement inside the wall can graze Link's Co cylinder from a bearing no
    reachable spot offers. Screen placements with this before ranking anything they produce."""
    q = GT.p32(tetra[0], tetra[1])
    return GT.wA.pla.func(q) >= TETRA_WALL_MIN and GT.wB.pla.func(q) >= TETRA_WALL_MIN


def base_reach(facing, lean=DELIVERED_LEAN, thrust=13):
    """|base| for a configuration -- the cut frame's roll step plus the cut root translate."""
    sch = ES.fast_schedule(facing, lean, thrust)
    k = sch['cut_step']
    return math.hypot(sch['dx'][k] + sch['cutx'][k], sch['dz'][k] + sch['cutz'][k])


def law_of(row, base=BASE_REACH):
    """The depth law's PIECES at a sweep row -- what a search should actually be ranking.

    `resid ~ 0` puts the endpoint on the ``old -> S`` ray, so the ray-distance past the vertex is
    ``d_ray = |base + push| - |S - old|`` and the plane penetration `depth_of` reports is that times
    the ray's projection onto the nearer wall normal (``kappa`` ~ 0.712 here). Two terms, and only one
    of them is a lever: **`base` is a constant**, so a clip is bought with ``push_u``, the push's
    projection onto the ray -- which is set by WHERE SHE SITS relative to Link's Co centre on the cut
    frame, since he is shoved directly away from her.

    Measured in-hull at the delivered cell, the two terms move together with the frames, which is what
    makes the thrust a real frame cost rather than a free draw:

        thrust 15  push_u +0.5175  |S-old| 49.3812  depth +0.2532
        thrust 14  push_u +0.4773  |S-old| 49.4053  depth +0.2075
        thrust 13  push_u +0.1304  |S-old| 49.6202  depth -0.1901
    """
    old, push = (row[1], row[2]), (row[5], row[6])
    s = math.hypot(GT.S[0] - old[0], GT.S[1] - old[1])
    ux, uz = (GT.S[0] - old[0]) / s, (GT.S[1] - old[1]) / s
    kappa = max(abs(GT.wA.pla.nx * ux + GT.wA.pla.nz * uz),
                abs(GT.wB.pla.nx * ux + GT.wB.pla.nz * uz))
    return dict(s_dist=s, push_u=push[0] * ux + push[1] * uz, push_mag=math.hypot(*push),
                d_ray=math.hypot(base * ux + push[0], base * uz + push[1]) - s, kappa=kappa,
                depth=depth_of(row), old=[old[0], old[1]], push=[push[0], push[1]])


def floor_at_brace(old, d_max=0.30, d_step=0.0005, eps_half=4e-4, eps_step=2e-6):
    """HOW DEEP MUST THE ENDPOINT BE BEFORE THIS CORNER ACCEPTS ANYTHING? -- measured, not inherited.

    `genuine` is a question about one segment, `old -> endpoint`, so sweep the endpoint directly:
    ``pred = S + d*u + eps*perp`` along this brace's own razor ray, and return the first `d` whose eps
    band holds a genuine endpoint. Returns ``(d, depth)`` or ``(None, None)``.

    Over the whole brace locus (planeA = 35 with planeB 35..36 and the mirror) this reads
    **d 0.155..0.171, depth 0.1154..0.1216 with no trend** -- a constant of the corner, not of the
    brace and not of the aim. Below it the swept segment is blocked whatever the razor does: the
    endpoint is behind both planes but the corner edge still catches the sweep."""
    ux, uz = GT.S[0] - old[0], GT.S[1] - old[1]
    s = math.hypot(ux, uz)
    ux, uz = ux / s, uz / s
    px, pz = -uz, ux
    ne = int(2 * eps_half / eps_step) + 1
    d = d_step
    while d <= d_max + 1e-12:
        bx, bz = GT.S[0] + d * ux, GT.S[1] + d * uz
        for i in range(ne):
            e = -eps_half + i * eps_step
            p = (bx + e * px, bz + e * pz)
            if GT.genuine_clip(old, p):
                q = GT.p32(*p)
                return d, -min(GT.wA.pla.func(q), GT.wB.pla.func(q))
        d += d_step
    return None, None


def co_centre_offsets(sch):
    """The animation-posed Co centre's OFFSET from Link's feet, per roll step -- the root/neck joint
    midpoint `_shovec._run` accumulates, read straight off a baked schedule."""
    nr = sch['nroot']
    return [(0.5 * (sum(sch['chx'][k][:nr]) + sum(sch['chx'][k][nr:])),
             0.5 * (sum(sch['chz'][k][:nr]) + sum(sch['chz'][k][nr:])))
            for k in range(len(sch['chx']))]


def cut_frame_swing(facing, thrust, lean=DELIVERED_LEAN):
    """WHY ONE THRUST CLIPS AND ITS NEIGHBOUR DOES NOT -- one number, and no search in it.

    The cut consumes the Co overlap on frame ``cut_step - 1``. A clip is bought with `push_u` and
    Link is shoved directly AWAY from the pusher, so the only place she can pay from is UP-RAY,
    behind him -- and by that frame he is braced against the corner, so the Co centre's whole step is
    the ANIMATION. Project that step on the roll direction:

        swing  =  (off[cut_step-1] - off[cut_step-2]) . m_hat

    Positive means the cylinder is moving forward, away from the only direction that pays; negative
    means it is swinging back onto her. Measured over the whole 45-cell aim window it is a CONSTANT
    to 1e-4 -- the facing rotates the offset and the ray together:

        thrust 13   cut frame 14   +8.9252    receding at 8.9 u/frame
        thrust 14   cut frame 15   +1.8547
        thrust 15   cut frame 16   -1.2850    closing -- and this IS the delivered clip's 1.2 u

    The roll's Co centre sweeps back through frames 9-12 (the tuck, reaching -13.5 u) and then
    straightens hard; thrust 13's cut lands on the two fastest FORWARD frames of that recovery
    (+8.07 then +8.93) while thrust 15's lands after it has settled and reversed. Returns
    ``dict(swing, prev, cut_frame, along)``. See knowledge/mechanics/cut-frame-co-swing.md."""
    sch = ES.fast_schedule(facing, lean, thrust)
    off = co_centre_offsets(sch)
    mx = ES.ML.cM_ssin_s16(int(facing) & 0xFFFF)
    mz = ES.ML.cM_scos_s16(int(facing) & 0xFFFF)
    along = [o[0] * mx + o[1] * mz for o in off]
    k = sch['cut_step'] - 1
    return dict(cut_frame=k, swing=along[k] - along[k - 1], prev=along[k - 1] - along[k - 2],
                along=along, facing=int(facing) & 0xFFFF, thrust=thrust)


def brace_for_ray(ux, uz):
    """``(|S-old|, old, kappa)`` for a razor RAY DIRECTION -- where the brace locus puts Link if the
    cut segment is to point at S along ``u``.

    `old` lies on ``S - t*u`` and on the locus CrrPos parks him on (35 u off one wall, at least 35 off
    the other), so ``t`` is forced: the larger of the two wall roots. This is the function that makes
    a misaligned push expensive without any hand-waving -- rotating the ray slides `old` down the wall
    and `t` grows with it."""
    a, b = GT.wA.pla, GT.wB.pla
    da, db = a.nx * ux + a.nz * uz, b.nx * ux + b.nz * uz
    ts = [-35.0 / d for d in (da, db) if d < 0.0]
    if not ts:
        return None
    t = max(ts)
    return t, (GT.S[0] - t * ux, GT.S[1] - t * uz), max(abs(da), abs(db))


def achievable_depth(push, facing, thrust, lean=DELIVERED_LEAN):
    """THE DEPTH A CUT-FRAME PUSH IS WORTH, wherever the razor has to brace to use it.

    A raw row cannot be ranked by its own `depth_of` -- `genuine` is three clauses, and a row 86 u out
    with its endpoint behind a far wall reads +13.6 -- nor by comparing push MAGNITUDES against
    `contact_required`, which scores a 7.4 u overlap pointing anywhere at +6.5. Both were false starts
    this session. The scalar that is actually well posed depends on the push VECTOR alone:

        ray = |base| * m_hat + push        (the cut segment, whatever `old` is)
        depth = kappa(ray) * (|ray| - |S - old(ray)|)

    because `resid = 0` says the ray points at S, which FIXES the brace via `brace_for_ray`. A big
    misaligned push therefore pays for itself twice over -- it rotates the ray and slides `old` down
    the wall -- and a small aligned one is worth more than a large crooked one. Reproduces the
    delivered clip's +0.2533 from its push alone. Returns ``(depth, s_dist, old, phi_deg)``.

    **THE CLAUSE IT DOES NOT ENFORCE, AND A SEARCH MUST**: this is a function of the PUSH, so the
    brace it reports is the one the razor WOULD use, not the one the row is at. A row whose own Link
    is 107 u out in the courtyard still scores its push here, and Newtoning it leaves him 107 u out
    (measured, session 102: +0.0955 at ``|S - old| 107.46``, solving to -41). Screen rows on their own
    ``|S - old|`` before ranking them with this."""
    mx = ES.ML.cM_ssin_s16(int(facing) & 0xFFFF)
    mz = ES.ML.cM_scos_s16(int(facing) & 0xFFFF)
    base = base_reach(facing, lean, thrust)
    vx, vz = base * mx + push[0], base * mz + push[1]
    L = math.hypot(vx, vz)
    if L <= 0.0:
        return None
    br = brace_for_ray(vx / L, vz / L)
    if br is None:
        return None
    s, old, kappa = br
    phi = math.degrees(math.atan2(mx * (vz / L) - mz * (vx / L), mx * (vx / L) + mz * (vz / L)))
    return kappa * (L - s), s, old, phi


def contact_required(facing, thrust, lean=DELIVERED_LEAN, depth=DEPTH_FLOOR, w_max=8.0,
                     w_step=0.01, u_step=0.002, u_max=6.0):
    """THE LAW INVERTED: the SMALLEST cut-frame OVERLAP this cell can clip on, and where.

    `law_of` reads a configuration and reports what it is worth. This asks the question a search
    actually needs -- what would be enough -- and it is exact, analytic and ~30 ms, because at a razor
    solution every term is pinned by the CELL and the BRACE:

      * `resid = 0` means ``base_vec + push`` is PARALLEL to ``old -> S``, so the push's perpendicular
        component is not free: it must cancel `base`'s, ``g = -|base| sin(delta)``, where `delta` is
        the facing's angle off that ray. **That perpendicular push is not a cost -- it ROTATES the ray
        and buys a NEARER brace**, which is why the delivered clip cuts from 49.3812 while cell 2552's
        no-push razor is stuck at 49.6161.
      * the parallel component must then reach the floor: ``f = |S-old| + depth/kappa - |base| cos(delta)``.
      * `|push| = share2 * cross_len` (the shares are 50/50, live-confirmed), and Link is shoved
        directly away from Tetra -- so the push DIRECTION fixes where she has to be, ``t = c -
        (R_sum - cross_len) * push_hat`` about the animation-posed Co centre ``c = old + off[cut-1]``,
        and `placeable` decides whether that spot exists. A push aimed too far off the ray puts her
        inside a wall, so `push_u` has a floor from the GEOMETRY as well as from the depth.

    Sweeping `old` along the brace locus (both slide branches) and `push_u` up from `f`, the first
    placeable spot gives that brace's requirement; the minimum over the locus is the CELL's. Returns
    ``dict(cross_len, push_u, push_perp, s_dist, w, branch, tetra, old, c, theta_deg)`` or None.

    This is what makes a thrust's refusal a measurement rather than a search outcome: thrust 15
    delivers `cross_len` 1.226 at cell 2552, and what a candidate must beat is this number."""
    sch = ES.fast_schedule(facing, lean, thrust)
    k = sch['cut_step']
    nr = sch['nroot']
    off = (0.5 * (sum(sch['chx'][k - 1][:nr]) + sum(sch['chx'][k - 1][nr:])),
           0.5 * (sum(sch['chz'][k - 1][:nr]) + sum(sch['chz'][k - 1][nr:])))
    mhat = (ES.ML.cM_ssin_s16(int(facing) & 0xFFFF), ES.ML.cM_scos_s16(int(facing) & 0xFFFF))
    base = base_reach(facing, lean, thrust)
    best = None
    for branch in ('A', 'B'):
        w = 0.0
        while w <= w_max + 1e-12:
            old = brace_point(35.0, 35.0 + w) if branch == 'B' else brace_point(35.0 + w, 35.0)
            sx, sz = GT.S[0] - old[0], GT.S[1] - old[1]
            s = math.hypot(sx, sz)
            w += w_step
            if s > 56.0:
                continue
            ux, uz = sx / s, sz / s
            px, pz = -uz, ux
            cosd = mhat[0] * ux + mhat[1] * uz
            sind = mhat[0] * px + mhat[1] * pz
            kappa = max(abs(GT.wA.pla.nx * ux + GT.wA.pla.nz * uz),
                        abs(GT.wB.pla.nx * ux + GT.wB.pla.nz * uz))
            g = -base * sind
            f = s + depth / kappa - base * cosd
            c = (old[0] + off[0], old[1] + off[1])
            pu = max(f, 0.0)
            while pu <= u_max:
                mag = math.hypot(pu, g)
                cross = mag / SHARE_LINK
                if cross >= CO_R_SUM:
                    break
                hx, hz = (pu * ux + g * px) / mag, (pu * uz + g * pz) / mag
                tet = (c[0] - (CO_R_SUM - cross) * hx, c[1] - (CO_R_SUM - cross) * hz)
                if placeable(tet):
                    row = dict(cross_len=cross, push_u=pu, push_perp=g, s_dist=s, w=w - w_step,
                               branch=branch, tetra=[tet[0], tet[1]], old=[old[0], old[1]],
                               c=[c[0], c[1]], theta_deg=math.degrees(math.atan2(abs(g), pu)),
                               kappa=kappa, facing=int(facing) & 0xFFFF, thrust=thrust)
                    if best is None or cross < best['cross_len']:
                        best = row
                    break
                pu += u_step
    return best


def hull_points(poly, step=1.0):
    """The grid of a polygon's interior, at ``step`` u. Shared by the field and the screen so a negative
    and the seeds it was argued from are the same population."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    pts, x = [], min(xs)
    while x <= max(xs):
        z = min(zs)
        while z <= max(zs):
            if ER.contains(poly, (x, z), 0.0):
                pts.append((x, z))
            z += step
        x += step
    return pts


def razor_solutions(tetra, facing, thrust, lean=DELIVERED_LEAN, frames=ER.FLOOR_FRAMES, hulls=None,
                    step=1.0, nspeed=None, cap=SOLVE_CAP, sep=SOLUTION_SEP):
    """Every in-hull entry where the razor can be zeroed, with its `old`, depth and genuine flag.

    Seeded from the WHOLE hull rather than from `entry_reach.hull_seeds`, and that difference is the
    point: `hull_seeds` takes strongest-leverage points deduped at 6 u, so a claim argued from its
    marches is a claim about the branches those seeds happened to find. Here every in-hull point with
    leverage is a candidate seed, taken in |resid| order.

    Returns a list of ``dict(entry, old, resid, depth, push, genuine, s_dist)``, ``s_dist`` being
    ``|S - old|`` -- the other half of the law."""
    hulls = ER.load() if hulls is None else hulls
    poly = ER.entry_hull(facing, frames, nspeed, hulls)
    pts = hull_points(poly, step)
    ctx, sch, resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
    d = 0.01                                     # `entry_gradient`'s probe, so `grad` is comparable

    def sweep(ps):
        return ctx.sweep_par([(tetra[0], tetra[1], p[0], p[1]) for p in ps], 0)
    r0 = sweep(pts)
    rx = [resid(o) for o in sweep([(p[0] + d, p[1]) for p in pts])]
    rz = [resid(o) for o in sweep([(p[0], p[1] + d) for p in pts])]
    seeds = []
    for i, p in enumerate(pts):
        r = resid(r0[i])
        g = (((rx[i] - r) / d) ** 2 + ((rz[i] - r) / d) ** 2) ** 0.5
        if g >= ER.LEVERAGE_MIN:
            seeds.append((abs(r), p))
    seeds.sort()
    out, seen = [], []
    for _, p0 in seeds[:cap]:
        p, rr, gr = ES.zero_the_resid(tetra, facing, thrust, lean, p0, nspeed=nspeed)
        if gr < ER.LEVERAGE_MIN or abs(rr) > 1e-3 or not ER.contains(poly, p, 0.0):
            continue
        if any(math.hypot(p[0] - q[0], p[1] - q[1]) < sep for q in seen):
            continue
        seen.append(p)
        o = ctx.sweep_par([(tetra[0], tetra[1], p[0], p[1])], 0)[0]
        old = (o[1], o[2])
        out.append(dict(entry=[p[0], p[1]], old=[old[0], old[1]], resid=resid(o), depth=depth_of(o),
                        push=[o[5], o[6]], genuine=bool(o[0]),
                        s_dist=math.hypot(GT.S[0] - old[0], GT.S[1] - old[1])))
    return out


def brace_point(pa, pb):
    """The point at the given signed distances from the two wall planes -- the locus CrrPos parks Link
    on (both at 35 is the corner-most brace, |S - old| 49.2546, the cheapest on the corner)."""
    a, b = GT.wA.pla, GT.wB.pla
    det = a.nx * b.nz - a.nz * b.nx
    rx, rz = pa - (a.ny * GT.LINK_Y + a.d), pb - (b.ny * GT.LINK_Y + b.d)
    return ((rx * b.nz - a.nz * rz) / det, (a.nx * rz - rx * b.nx) / det)


def placeable_screen(facing, thrust, lean=DELIVERED_LEAN, p_half=120.0, p_step=8.0, ebox=110.0,
                     estep=8.0, travel_mid=311.0, seed_cap=8, nspeed=None):
    """THE DEEPEST CLIP ONE AIM CELL CAN BUY -- **no hull, and only placements she can stand in**.

    The two axes a hull-free question needs are her placement and Link's entry, and both are swept in
    the ROLL's own frame so neither family is covered by luck: entries are the brace backed off by
    `travel_mid +- ebox` of roll travel (26 x cut_step ~ 390 is the cut firing as he ARRIVES, ~233 the
    delivered slide), placements are a grid about the brace filtered by `placeable` and by Co reach.
    Every near-curve seed is Newtoned onto the razor and filtered back to sane geometry.

    Returns the best row (`law_of` fields plus entry/tetra/travel/genuine) or None. At thrust 13 this
    reads NEGATIVE at all 45 cells -- best -0.0208 at cell 2554, against a floor of ~0.118."""
    ctx, sch, resid = ES.build_fast(facing, lean, thrust, nspeed=nspeed)
    k = sch['cut_step']
    mx, mz = sch['dx'][k] + sch['cutx'][k], sch['dz'][k] + sch['cutz'][k]
    bd = math.hypot(mx, mz)
    rx, rz = mx / bd, mz / bd
    qx, qz = -rz, rx
    brace = brace_point(35.0, 35.0)
    ecen = (brace[0] - travel_mid * rx, brace[1] - travel_mid * rz)

    entries, t = [], travel_mid - ebox
    while t <= travel_mid + ebox + 1e-9:
        lat = -ebox / 2.0
        while lat <= ebox / 2.0 + 1e-9:
            entries.append((brace[0] - t * rx + lat * qx, brace[1] - t * rz + lat * qz))
            lat += estep
        t += estep

    best, n = None, int(2 * p_half / p_step) + 1
    for i in range(n):
        for j in range(n):
            tet = (brace[0] - p_half + i * p_step, brace[1] - p_half + j * p_step)
            if not placeable(tet) or math.hypot(tet[0] - brace[0], tet[1] - brace[1]) > 95.0:
                continue
            out = ctx.sweep_par([(tet[0], tet[1], e[0], e[1]) for e in entries], 0)
            seen = []
            for _r, p0 in sorted((abs(resid(o)), e) for e, o in zip(entries, out))[:seed_cap * 4]:
                if len(seen) >= seed_cap:
                    break
                if any(math.hypot(p0[0] - q[0], p0[1] - q[1]) < 6.0 for q in seen):
                    continue
                p, rr, gr = ES.zero_the_resid(tet, facing, thrust, lean, p0, nspeed=nspeed)
                if gr < ER.LEVERAGE_MIN or abs(rr) > 1e-3:
                    continue
                if math.hypot(p[0] - ecen[0], p[1] - ecen[1]) > ebox * 2.0:
                    continue
                if not (GT.wA.pla.func(GT.p32(*p)) > 0.0 and GT.wB.pla.func(GT.p32(*p)) > 0.0):
                    continue
                o = ctx.sweep_par([(tet[0], tet[1], p[0], p[1])], 0)[0]
                law = law_of(o)
                if law['s_dist'] > 56.0:
                    continue
                seen.append(p)
                law.update(entry=[p[0], p[1]], tetra=[tet[0], tet[1]], resid=resid(o),
                           genuine=bool(o[0]), facing=facing, thrust=thrust,
                           travel=math.hypot(p[0] - law['old'][0], p[1] - law['old'][1]))
                if best is None or law['depth'] > best['depth']:
                    best = law
    return best


def screen(tetra, facing, thrust, lean=DELIVERED_LEAN, frames=ER.FLOOR_FRAMES, **kw):
    """CAN THIS CONFIGURATION CLIP AT ALL? -- one call, ~5 s, where a dust hunt is hours.

    ``admits`` False is the proof direction (no razor solution's endpoint gets through a plane, so
    `genuine` is impossible at this facing/thrust/lean/budget); True only means the geometry allows it.
    ``reason`` names which of the two ways ``admits`` can be False it is, because "no razor solution at
    all" is session 93's second-lobe result and not a statement about the thrust."""
    sols = razor_solutions(tetra, facing, thrust, lean=lean, frames=frames, **kw)
    if not sols:
        return dict(admits=False, reason='no razor solution inside the reachable hull', n=0,
                    facing=facing, thrust=thrust, lean=lean, frames=frames)
    ds = sorted(s['depth'] for s in sols)
    sd = sorted(s['s_dist'] for s in sols)
    olds = {(s['old'][0], s['old'][1]) for s in sols}
    return dict(admits=ds[-1] > 0.0, reason='' if ds[-1] > 0.0 else
                'the lunge lands %.4f u short of the nearer wall plane at every razor solution' % -ds[-1],
                n=len(sols), n_genuine=sum(1 for s in sols if s['genuine']),
                depth=[ds[0], ds[-1]], s_dist=[sd[0], sd[-1]], n_distinct_old=len(olds),
                old=sorted(olds)[0], facing=facing, thrust=thrust, lean=lean, frames=frames,
                best=max(sols, key=lambda s: s['depth']))


def thrust_map(tetra, cells=None, thrusts=ES.THRUSTS, lean=DELIVERED_LEAN, frames=ER.FLOOR_FRAMES,
               step=1.0, hulls=None, progress=False):
    """`screen` over the whole aim window x thrust -- the map that answers "is this frame collectable
    ANYWHERE on this corner" with a measurement instead of a budget.

    Costs ~4 s per configuration, so the 45-cell window at three thrusts is ~3 min: cheaper than one
    camera pass of the session 95-98 lotteries, and it is the question those passes were betting on."""
    hulls = ER.load() if hulls is None else hulls
    by_cell = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    keys = sorted(by_cell) if cells is None else [c for c in cells if c in by_cell]
    out = []
    for cell in keys:
        row = dict(cell=cell, facing=by_cell[cell], bam=by_cell[cell] - 40841)
        for thrust in thrusts:
            r = screen(tetra, by_cell[cell], thrust, lean=lean, frames=frames, step=step, hulls=hulls)
            r.pop('best', None)
            row['thr%d' % thrust] = r
        out.append(row)
        if progress:
            print("  cell %d (%+d BAM): %s" % (cell, row['bam'], ' '.join(
                '%d:%s' % (t, 'ADMITS' if row['thr%d' % t]['admits'] else 'no') for t in thrusts)),
                flush=True)
    return out


# --------------------------------------------------------------------------- CLI

def _cmd_screen(argv):
    cell = int(argv[0]) if argv else 2552
    thrust = int(argv[1]) if len(argv) > 1 else 13
    lean = int(argv[2]) if len(argv) > 2 else DELIVERED_LEAN
    frames = int(argv[3]) if len(argv) > 3 else ER.FLOOR_FRAMES
    by_cell = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    t0 = time.time()
    r = screen(ES.console_seed()['tetra'], by_cell[cell], thrust, lean=lean, frames=frames)
    print("cell %d (facing %d) thrust %d lean %d, %d walk frames -- plan_cost %d"
          % (cell, by_cell[cell], thrust, lean, frames, frames + thrust + 4))
    print("  %d razor solutions, %d distinct `old`, %d genuine" % (r['n'], r.get('n_distinct_old', 0),
                                                                   r.get('n_genuine', 0)))
    if r['n']:
        print("  depth %+.4f..%+.4f u | |S-old| %.4f..%.4f | old %.6f %.6f"
              % (r['depth'][0], r['depth'][1], r['s_dist'][0], r['s_dist'][1], r['old'][0],
                 r['old'][1]))
    print("  ADMITS A CLIP" if r['admits'] else "  REFUSED: %s" % r['reason'])
    print("  [%.0f s]" % (time.time() - t0))


def _cmd_map(argv):
    step = float(argv[0]) if argv else 1.0
    t0 = time.time()
    rows = thrust_map(ES.console_seed()['tetra'], step=step, progress=True)
    for thrust in ES.THRUSTS:
        have = [r for r in rows if r['thr%d' % thrust]['n']]
        pos = [r for r in have if r['thr%d' % thrust]['admits']]
        print("thrust %2d (plan_cost %2d): %d of %d cells have a razor solution, %d ADMIT a clip"
              % (thrust, ER.FLOOR_FRAMES + thrust + 4, len(have), len(rows), len(pos)))
    out = os.path.join(_rb, '_generated', 's100', 'razor_depth_map.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(source='harness.tetrapush.razor_depth.thrust_map', rows=rows,
                   seconds=time.time() - t0), open(out, 'w'), indent=1)
    print("wrote %s  [%.0f s]" % (out, time.time() - t0))


def main(argv=None):
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'screen'
    if cmd == 'screen':
        _cmd_screen(argv)
    elif cmd == 'map':
        _cmd_map(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
