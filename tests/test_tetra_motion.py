"""HER STATE AT THE CUT, and what the corner actually asks for (session 102).

Session 101 left thrust 13 refused everywhere it had looked and named her VELOCITY as the one term no
sweep had ever varied -- she was seeded at rest every time. These gates pin what that axis is, what it
buys, and the two model pieces that came out of building it:

  * **the ejection equilibrium.** The plow throws her out at half the overlap per frame (50/50 shares),
    so at thrust 13's cut frame she lands at |c - t| ~ 87..93 from ANY static seed inside contact,
    against a requirement of <= 79.4. That is WHY the placement plane kept reading inert -- and, since
    the depth stops depending on her placement the moment contact is lost, why a climb on the depth
    goes flat exactly where it needs a gradient. `_shovec` now reports the CONTACT PAIR.
  * **the law, inverted.** `razor_depth.contact_required` turns "how much push" into "how much
    OVERLAP, and where she has to be standing" -- and that requirement is **thrust-independent**
    (13 and 15 agree to under 1%), which is Dereck's "it's all the same animations" as a measurement.
    It reproduces the delivered clip's own contact geometry to 1.2 u, which is the control every
    negative here is argued against.

Values are exact pinned model outputs (`[[zero-ulp-tests-only]]`): the additive-inertness and
batched-solve gates are bit-equality, and every depth/contact assertion re-sweeps a PINNED input.
"""
import math
import warnings

import pytest

from harness.rollstab import geometry_tetra as GT            # noqa: E402
from harness.tetrapush import entry_search as ES             # noqa: E402
from harness.tetrapush import razor_depth as RD              # noqa: E402
from harness.tetrapush import tetra_motion as TM             # noqa: E402
from tww_sim.core import cc_push as CP                       # noqa: E402
from tww_sim.core.npc_zl1 import STT_MOVE, Zl1FollowState    # noqa: E402

warnings.simplefilter('ignore')

FACING = 40841
LEAN = RD.DELIVERED_LEAN

#: The delivered clip's razor entry (thrust 15) and the 2-step shift that reproduces its brace at 13.
E15 = (-1529.6196515725367, -779.7578481252098)


def _tetra():
    return ES.console_seed()['tetra']


def _shifted_entry(thrust):
    sch = ES.fast_schedule(FACING, LEAN, thrust)
    return (E15[0] + (15 - thrust) * sch['dx'][0], E15[1] + (15 - thrust) * sch['dz'][0])


# ------------------------------------------------------------------ the axis is additive


def test_the_at_rest_seed_is_bit_identical_to_the_historical_run():
    """The motion axis must be INERT until asked for: a row swept with no seed and a row swept with an
    explicit at-rest seed (`stt < 0`) are the same bits, and so is the whole 14-slot `extra` form.

    This is the gate that lets every session-99/100/101 measurement stand unchanged -- the axis added
    three parameters to `ShoveCtx._run` and four outputs, and neither may move a delivered number."""
    tetra = _tetra()
    ctx, sch, resid = ES.build_fast(FACING, LEAN, 13)
    e = _shifted_entry(13)
    plain = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1])], 0)[0]
    tagged = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1], 0.0, 0, -1)], 0)[0]
    assert plain == tagged
    ext = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1])], 0, extra=True)[0]
    assert ext[:10] == plain                                  # extra APPENDS, never rewrites
    assert len(ext) == 14
    # and `seed=` on the call is the same as carrying it per item
    at_rest = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1])], 0, seed=None)[0]
    assert at_rest == plain


def test_a_moving_seed_integrates_the_games_own_follow_model():
    """A seed with motion is not a new dynamics -- it is `npc_zl1.Zl1FollowState`, which is what makes
    the axis a MODEL knob rather than a search convenience.

    Checked out of contact and away from the walls, so her CrrPos and the CC push are both inert and
    what remains is exactly the follow step: `optn_2` turns `angle.y` toward Link by
    `cLib_addCalcAngleS(.., 4, 0x800, 0x80)`, chases speedF toward `0.04*sqrt(d^2 - 130^2)` capped at
    10 with `cLib_chaseF(.., 1.0)`, and `posMoveF` steps her along it. Bit-exact, every frame."""
    ctx, sch, resid = ES.build_fast(FACING, LEAN, 13)
    e = _shifted_entry(13)
    seed_pos = (-1350.0, -650.0)                              # far from the corner and both walls
    spd, ang = 7.0, 30000
    res, steps = ctx.run_trace(seed_pos[0], seed_pos[1], 0, e[0], e[1], seed=(spd, ang, STT_MOVE))
    z = Zl1FollowState(seed_pos[0], ES.TA.GROUND_Y, seed_pos[1], ang, spd, STT_MOVE)
    for k, (lx, lz, tx, tz) in enumerate(steps):
        z.step((lx, ES.TA.GROUND_Y, lz))
        assert (z.x, z.z) == (tx, tz), (k, (z.x, z.z), (tx, tz))
    assert math.hypot(steps[-1][2] - seed_pos[0], steps[-1][3] - seed_pos[1]) > 5.0   # she MOVED


def test_the_contact_pair_is_the_push_the_cut_consumes():
    """The four new slots are the CUT'S OWN CONTACT, not a diagnostic near it: feed the reported Co
    centre and her reported position straight into `cc_push.co_move_pair` and Link's move comes back
    BIT-IDENTICAL to the push the row says the cut consumed. Without that identity the surplus metric
    the whole session ranks on would be measuring a different frame."""
    tetra = _tetra()
    ctx, sch, resid = ES.build_fast(FACING, LEAN, 15)
    row = ctx.sweep_par([(tetra[0], tetra[1], E15[0], E15[1])], 0, extra=True)[0]
    c = (row[10], ES.TA.GROUND_Y, row[11])
    t = (row[12], ES.TA.GROUND_Y, row[13])
    m1, _m2 = CP.co_move_pair(c, ES.LINK_CO_R, ES.LINK_CO_H, t, ES.TETRA_CO_R, ES.TETRA_CO_H)
    assert (m1[0], m1[2]) == (row[5], row[6])
    # and it is a GRAZE on an 80 u radius sum -- the fact the whole refusal turns on
    assert 0.9 < RD.CO_R_SUM - math.hypot(c[0] - t[0], c[2] - t[2]) < 1.5


def test_the_batched_razor_solve_is_the_scalar_one():
    """`tetra_motion.razor_batch` exists so a search can Newton many candidates in one sweep; it earns
    that only if it is `entry_search.zero_the_resid` term for term. Exact equality, at rest and in
    motion, over candidates that converge at different rates (which is what the live-set bookkeeping
    is for)."""
    tetra = _tetra()
    ctx, sch, resid = ES.build_fast(FACING, LEAN, 13)
    e = _shifted_entry(13)
    cands = [((tetra[0], tetra[1]), e, None),
             ((tetra[0] - 20.0, tetra[1] + 10.0), (e[0] + 30.0, e[1] - 25.0), None),
             ((tetra[0] - 8.0, tetra[1] - 12.0), e, (6.0, 24000, STT_MOVE))]
    got = TM.razor_batch(ctx, resid, cands)
    for (tet, e0, seed), (entry, rr, gr, _row) in zip(cands, got):
        p, r2, g2 = ES.zero_the_resid(tet, FACING, 13, LEAN, e0, seed=seed)
        assert entry == tuple(p), (tet, entry, p)
        assert (rr, gr) == (r2, g2)


# ------------------------------------------------------------ the ejection equilibrium


def test_the_ejection_equilibrium_pins_her_cut_frame_distance():
    """WHY THE PLACEMENT PLANE READS INERT, measured in the quantity that decides a clip.

    The plow ejects her at half the overlap every frame, so her distance from the cut frame's Co
    centre is an ATTRACTOR rather than a function of her seed: over a +-40 u grid along and across the
    razor ray, 22 of the 24 that come into range at all arrive at |c - t| in the high 80s or low 90s
    having been flung tens of units on the way, against a requirement of <= 79.4.

    **One of the 25 does get inside the radius, and it is the exception that names the trade**: it
    arrives at 68 u with 12 u of overlap and a push aimed so far off the ray that its SURPLUS is the
    worst on the grid. So the claim is not "no static seed touches him" -- it is that no static seed
    delivers the contact its own brace needs, which is what `surplus_of` measures."""
    tetra = _tetra()
    ctx, sch, resid = ES.build_fast(FACING, LEAN, 13)
    e = _shifted_entry(13)
    row0 = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1])], 0)[0]
    s = math.hypot(GT.S[0] - row0[1], GT.S[1] - row0[2])
    u = ((GT.S[0] - row0[1]) / s, (GT.S[1] - row0[2]) / s)
    items = []
    for along in (-40.0, -20.0, 0.0, 20.0, 40.0):
        for lat in (-40.0, -20.0, 0.0, 20.0, 40.0):
            t = (tetra[0] - along * u[0] - lat * u[1], tetra[1] - along * u[1] + lat * u[0])
            items.append((t, (t[0], t[1], e[0], e[1])))
    rows = ctx.sweep_par([it[1] for it in items], 0, extra=True)
    dists, moved, surp = [], [], []
    for (t, _it), row in zip(items, rows):
        d = math.hypot(row[10] - row[12], row[11] - row[13])
        if d > 130.0:                                          # never in range: not the equilibrium
            continue
        dists.append(d)
        moved.append(math.hypot(row[12] - t[0], row[13] - t[1]))
        surp.append(TM.surplus_of(row, FACING, 13)['surplus'])
    assert len(dists) >= 20, len(dists)
    assert sum(1 for d in dists if d > 85.0) >= len(dists) - 2     # the equilibrium band
    assert max(surp) < 0.0, max(surp)                          # and NOT ONE has the contact it needs
    assert max(moved) > 25.0                                   # they were flung to get there
    # the console seed's own row is the one every session-101 number was read at
    d0 = math.hypot(rows[12][10] - rows[12][12], rows[12][11] - rows[12][13])
    assert abs(d0 - 90.145) < 1e-2, d0


# --------------------------------------------------------- the law inverted: what is enough


def test_the_required_contact_is_thrust_independent():
    """DERECK'S "IT IS ALL THE SAME ANIMATIONS", AS A NUMBER. What the corner asks for -- the cut-frame
    overlap and the spot she must stand in -- is a property of the CELL and the BRACE, not of the
    thrust: at every cell the thrust-13 and thrust-15 requirements agree to under 1% in the overlap
    (the aim they ask for moves up to 2.6 deg, which is the brace shifting, not the bar). So thrust 13
    is not refused because it needs more; it is refused because the animation-posed Co centre is not
    touching her on its cut frame."""
    by = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    for cell in (2552, 2554, 2557):
        r13 = RD.contact_required(by[cell], 13)
        r15 = RD.contact_required(by[cell], 15)
        assert r13 and r15, cell
        assert abs(r13['cross_len'] - r15['cross_len']) < 0.01 * r15['cross_len'], (cell, r13, r15)
        assert abs(r13['theta_deg'] - r15['theta_deg']) < 3.0, cell


def test_the_required_contact_reproduces_the_delivered_clip():
    """THE CONTROL (`[[search-space-contains-human]]`): the requirement is derived, so it owes an
    account of the one clip this corner is known to give. At the delivered cell it predicts a
    `cross_len` of 0.8085 with her at (-1618.79, -939.00) and the push 31.6 deg off the ray -- and the
    console-confirmed thrust-15 clip delivers 1.226 at (-1618.95, -940.17), 32.4 deg. Right spot to
    1.2 u, right angle to 0.8 deg, and comfortably over the bar, which is what a clip should look
    like against a floor."""
    tetra = _tetra()
    req = RD.contact_required(FACING, 15)
    ctx, sch, resid = ES.build_fast(FACING, LEAN, 15)
    row = ctx.sweep_par([(tetra[0], tetra[1], E15[0], E15[1])], 0, extra=True)[0]
    got = TM.contact_of(row)
    assert abs(req['cross_len'] - 0.8085) < 1e-3, req['cross_len']
    assert got['cross_len'] > req['cross_len']                 # the delivered clip CLEARS its bar
    assert abs(got['cross_len'] - 1.2259) < 1e-3, got['cross_len']
    assert abs(got['theta_deg'] - req['theta_deg']) < 1.5, (got['theta_deg'], req['theta_deg'])
    assert math.hypot(req['tetra'][0] - row[12], req['tetra'][1] - row[13]) < 1.5
    assert RD.depth_of(row) > RD.DEPTH_FLOOR                   # ...and it is a clip


def test_the_delivered_cell_is_an_expensive_one_and_2557_is_the_cheapest():
    """WHERE TO HUNT, AND WHY IT IS NOT WHERE THE CLIP WAS DELIVERED. The requirement is set by how far
    the cell's own no-push razor sits from the corner-most brace: a facing that points at the corner
    braces at 49.2546 and needs the push only for the 0.0345 u the lunge is short, while cell 2552
    points 0.38 deg off and must ALSO spend perpendicular push steering the ray back onto the vertex.
    Over the window that is a factor of TWO: cell 2557 asks 0.394, cell 2552 asks 0.804."""
    by = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    need = {}
    for cell in (2557, 2556, 2558, 2555, 2554, 2553, 2552, 2551, 2549):
        r = RD.contact_required(by[cell], 13)
        assert r is not None, cell
        need[cell] = r
    assert min(need, key=lambda c: need[c]['cross_len']) == 2557
    assert abs(need[2557]['cross_len'] - 0.3939) < 1e-3, need[2557]['cross_len']
    assert abs(need[2552]['cross_len'] - 0.8037) < 1e-3, need[2552]['cross_len']
    # the cheap cell is cheap because it braces corner-most and barely has to steer
    assert abs(need[2557]['s_dist'] - 49.2546) < 1e-3, need[2557]['s_dist']
    assert need[2557]['theta_deg'] < 6.0, need[2557]['theta_deg']
    assert need[2552]['theta_deg'] > 30.0, need[2552]['theta_deg']
    # and the ordering is monotone in the brace, which is the mechanism rather than a coincidence
    order = sorted(need, key=lambda c: need[c]['cross_len'])
    assert [need[c]['s_dist'] for c in order] == sorted(need[c]['s_dist'] for c in order)


def test_the_cut_frames_co_swing_is_the_whole_difference_between_the_thrusts():
    """WHY THRUST 13 IS REFUSED, AS ONE NUMBER OFF THE BAKED SCHEDULE -- no search in it.

    The cut consumes the Co overlap on frame ``cut_step - 1``, Link is braced against the corner by
    then, and he is shoved directly AWAY from her -- so she can only pay from UP-RAY, and what decides
    whether she is touching is whether the animation-posed cylinder is closing on that direction or
    running from it. Projected on the roll direction the step into that frame is **+8.9252** at
    thrust 13, **+1.8547** at 14 and **-1.2850** at 15: the floor thrust's cut lands on the fastest
    FORWARD frame of the roll's straightening-out, and the delivered clip's lands after it has
    reversed. That reversal is where its free 1.2 u of overlap comes from.

    Aim-invariant to 1e-4 over the whole 45-cell window, because the facing rotates the offset and
    the ray together -- which is what makes it a property of the animation rather than of a search."""
    by = {c: f for f, b, s in ES.aim_cells() for c in [ES.aim_cell(f)]}
    for cell in (2552, 2554, 2557):
        s = {t: RD.cut_frame_swing(by[cell], t) for t in (13, 14, 15)}
        assert [s[t]['cut_frame'] for t in (13, 14, 15)] == [14, 15, 16]
        assert abs(s[13]['swing'] - 8.9252) < 1e-3, s[13]['swing']
        assert abs(s[14]['swing'] - 1.8547) < 1e-3, s[14]['swing']
        assert abs(s[15]['swing'] + 1.2850) < 1e-3, s[15]['swing']
        # the ordering IS the push ordering session 101 measured (+0.5175 / +0.4773 / +0.1304)
        assert s[15]['swing'] < 0.0 < s[14]['swing'] < s[13]['swing']
        # and thrust 13 is doubly unlucky: the frame BEFORE its cut is the second-fastest forward one
        assert s[13]['prev'] > 8.0, s[13]['prev']
    sw = [RD.cut_frame_swing(f, 13)['swing'] for f, _b, _s in ES.aim_cells()]
    assert max(sw) - min(sw) < 1e-3, (min(sw), max(sw))
    # the tuck the recovery is recovering FROM: deepest at roll step 11, 13.5 u behind his feet
    along = RD.cut_frame_swing(FACING, 15)['along']
    assert along.index(min(along)) == 11 and min(along) < -13.0, min(along)


def test_the_swing_is_visible_as_overlap_gained_or_lost_on_the_cut_frame():
    """THE SWING, READ BACK OFF THE ENGINE at the two entries that share a brace.

    Session 101 pinned that shifting the entry by whole roll steps reproduces `old` BIT-IDENTICALLY at
    every thrust, so the two runs below differ in nothing but which frame of the animation the cut
    fires on. From the console placement the thrust-15 cut GAINS overlap on its cut-consumed frame
    while the thrust-13 cut is already 10 u clear and opening -- the sign of `cut_frame_swing`,
    measured rather than asserted."""
    tetra = _tetra()
    got = {}
    for thrust, entry in ((15, E15), (13, _shifted_entry(13))):
        ctx, sch, resid = ES.build_fast(FACING, LEAN, thrust)
        off = RD.co_centre_offsets(sch)
        _r, steps = ctx.run_trace(tetra[0], tetra[1], 0, entry[0], entry[1])
        k = sch['cut_step'] - 1
        d = []
        for j in (k - 1, k):
            lx, lz, tx, tz = steps[j]
            d.append(RD.CO_R_SUM - math.hypot(lx + off[j][0] - tx, lz + off[j][1] - tz))
        got[thrust] = d
    assert got[15][1] > got[15][0]                 # thrust 15 CLOSES into its cut frame
    assert got[15][1] > 0.0                        # ...and lands in contact
    assert got[13][1] < got[13][0] < 0.0           # thrust 13 is already clear and still opening
    assert got[13][1] < -10.0, got[13]             # by 10 u, against a bar of ~0.4 u of overlap


def _conjunction(facing, thrust, halo=48.0, hstep=8.0, travel=(160.0, 420.0), t_step=26.0,
                 lat=32.0, lat_step=32.0, speeds=(0.0, 5.0, 10.0), aim_step=0x2000):
    """Best `achievable_depth` per |resid| band over placement x entry x seed motion. Returns
    ``{band: (depth, cross_len)}``. A reduced form of session 102's scan, sized for a gate."""
    ctx, sch, resid = ES.build_fast(facing, LEAN, thrust)
    req = RD.contact_required(facing, thrust, LEAN)
    k = sch['cut_step']
    mx, mz = sch['dx'][k] + sch['cutx'][k], sch['dz'][k] + sch['cutz'][k]
    bd = math.hypot(mx, mz)
    rx, rz, qx, qz = mx / bd, mz / bd, -mz / bd, mx / bd
    brace = RD.brace_point(35.0, 35.0)
    entries, t = [], travel[0]
    while t <= travel[1] + 1e-9:
        o = -lat
        while o <= lat + 1e-9:
            entries.append((brace[0] - t * rx + o * qx, brace[1] - t * rz + o * qz))
            o += lat_step
        t += t_step
    tgt = tuple(req['tetra'])
    seeds = [(0.0, 0, -1)] + [(s, a, STT_MOVE) for s in speeds if s > 0.0
                              for a in range(0, 0x10000, aim_step)]
    bands = {0.05: None, 0.5: None, 2.0: None, 10.0: None}
    n = int(2 * halo / hstep) + 1
    for i in range(n):
        for j in range(n):
            tet = (tgt[0] - halo + i * hstep, tgt[1] - halo + j * hstep)
            if not RD.placeable(tet):
                continue
            rows = ctx.sweep_par([(tet[0], tet[1], e[0], e[1]) + sd
                                  for e in entries for sd in seeds], 0, extra=True)
            for row in rows:
                # `achievable_depth` ranks the PUSH, so the row owes its own |S - old| clause
                # (knowledge/model/required-cut-contact.md; without it 107 u out scores, then solves to -41)
                if math.hypot(GT.S[0] - row[1], GT.S[1] - row[2]) > 56.0:
                    continue
                q = GT.p32(row[1], row[2])
                if not (GT.wA.pla.func(q) > 0.0 and GT.wB.pla.func(q) > 0.0):
                    continue
                got = RD.achievable_depth((row[5], row[6]), facing, thrust)
                if got is None:
                    continue
                cross = RD.CO_R_SUM - math.hypot(row[10] - row[12], row[11] - row[13])
                rr = abs(resid(row))
                for b in bands:
                    if rr <= b and (bands[b] is None or got[0] > bands[b][0]):
                        bands[b] = (got[0], cross)
    return bands


def test_the_razor_and_the_contact_are_mutually_exclusive_at_thrust_13():
    """THE SESSION-102 VERDICT, and it is a mechanism rather than a budget.

    `achievable_depth` says the push available in this space is worth well over the floor: +0.22 at
    cell 2557, where the corner asks 0.394 of overlap and the space offers 5.05. But those rows sit at
    |resid| **7.5** -- nowhere near the razor -- and pulling one onto the razor with the entry Newton
    leaves NO contact at all (`grad` 0.000, `zero_the_resid`'s own no-leverage diagnostic).

    Banded by |resid| the trade is monotone: the depth on offer grows with how far the row is from the
    curve. In the tightest band the best row has **negative** overlap and its achievable depth is
    exactly the NO-PUSH value for its brace -- i.e. at the razor, thrust 13 gets no contact, and what
    is left is the 0.0345 u the lunge is short. That is one statement covering every negative sessions
    99-101 measured piecemeal, and it is what has to be broken."""
    bands = _conjunction(40914, 13)
    got = {b: v for b, v in bands.items() if v is not None}
    assert set(got) == {0.05, 0.5, 2.0, 10.0}, sorted(got)
    depths = [got[b][0] for b in (0.05, 0.5, 2.0, 10.0)]
    assert depths == sorted(depths), depths                    # monotone in the distance to the razor
    assert depths[-1] > RD.DEPTH_FLOOR                         # the push exists, far from the razor
    assert depths[0] < 0.0, depths[0]                          # and at the razor it is not there
    assert got[0.05][1] < 0.0, got[0.05]                       # the tightest band has NO contact
    # ...and that best-at-the-razor IS the no-push value for cell 2557's own brace
    nopush = RD.achievable_depth((0.0, 0.0), 40914, 13)[0]
    assert abs(depths[0] - nopush) < 1e-3, (depths[0], nopush)


def test_even_a_perfect_brace_needs_a_push_because_the_lunge_is_short():
    """THE IRREDUCIBLE PART, and it is why no aiming trick alone can pay for this corner. `|base|` --
    the roll step plus the cut root translate -- is 49.2202, and the corner-most brace CrrPos can park
    Link on is 49.2546 from the vertex. The lunge is 0.0345 u SHORT before the depth floor is even
    considered, so every clip on this corner is bought with contact."""
    brace = RD.brace_point(35.0, 35.0)
    s = math.hypot(GT.S[0] - brace[0], GT.S[1] - brace[1])
    assert abs(s - 49.254610) < 1e-5, s
    assert RD.BASE_REACH < s
    assert abs((s - RD.BASE_REACH) - 0.034385) < 1e-5, s - RD.BASE_REACH
    # stated as the contact it forces, with the floor: about 0.39 u of overlap, perfectly aimed
    need = 2.0 * (s - RD.BASE_REACH + RD.DEPTH_FLOOR / 0.7106)
    assert 0.38 < need < 0.40, need
