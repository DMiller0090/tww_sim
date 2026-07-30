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
"""**THE HANDOFF AIM: where the last push frames POINT** (session 67).

Session 63 measured that the plan's shortfall is DIRECTIONAL rather than a want of push, and sessions
63-66 read that direction as a LATERAL DEFICIT -- "the glide cannot buy ~12 u of lateral". Measured on
the s66 beam, that reading is wrong in its sign and in its axis. The cycle-3 endpoints hand Tetra over
at lateral **+8.90 / +21.19 / +24.61** against a target thread whose lateral is **-2.27..+7.94**
(`objective.placement_thread`): she has to LOSE lateral, every stick loses it
(`full_herd.lateral_authority` reads one-sided at every endpoint), and the s66 plan lands at **-4.43**
-- it OVERSHOOTS the thread and comes out the far side.

What is actually short is the AIM. The plow ejects Tetra along the ray from Link's animated exec
Co-centre through her feet, so the direction her remaining displacement takes is a fact about where
LINK stands, and the thread runs **nearly parallel to the approach** (12.2 deg off the herd axis
against an approach 13-14 deg off it), so the directions that land her on it are a window ~**2 deg**
wide. The s66 endpoints aim 10-50 deg steeper than that window. That is the whole miss, and it is a
different quantity from "lateral": a plan can have every unit of lateral it needs available and still
spend it on the wrong frames.

This module is that geometry, derived and exact:

  * `push_step` -- the plow's next-frame push on Tetra, **BIT-EXACT one frame ahead** off the
    pre-step state: ``f32(Tetra + (CO_RADII_BAR - centre_feet)/2 * unit(Tetra - centre)) == Tetra'``
    for every contact frame, with the ejection clamped to zero at the bar. So Tetra's side of the
    endgame needs no stepping at all -- the only unknown in a placement is LINK's trajectory.
  * `eject_unit` -- that ray's direction in herd coordinates: the aim.
  * `aim_window` -- the directions from a Tetra position that reach the thread, as the bearings of
    its two ends. This is the razor: ~2 deg at the s66 handoff range.
  * `aim_miss` -- how far the current aim misses the thread SEGMENT (perpendicular u), plus the
    distance she would travel to that closest approach. A miss inside `objective.PLACEMENT_BAND` is
    an aim that lands her; the miss is priced in u, so it compares directly against the band.
  * `centre_lat_needed` -- what the aim asks of Link: the lateral his exec centre must sit at to
    aim inside the window, and how far that is from where he is. This is "squareness" as a number.
  * `push_reserve` -- ``CO_RADII_BAR - centre_feet``: the ejection still stored in the current
    overlap, which the escape spends WITHOUT Link having to close (each frame takes half the deficit,
    so a static Link delivers the whole of it). The measured escape residuals bracket it -- 26.76 u
    off a 29.07 reserve where the atom separates in 4 frames, 41.39 off 28.90 where it takes 8 and
    Link closes -- so it sizes the handoff range rather than bounding it.
  * `landing_miss` / `handoff_target` -- the EXACT half and its inverse: where a MEASURED escape
    residual leaves her, and the handoff state a given residual demands. The chain's target is not
    the coord: it is the coord minus the escape's ~44 u.
  * `handoff_spec` -- the three numbers a cycle-3 endpoint has to satisfy for the escape to place
    her, in one call: the aim inside the window, the range matched to the reserve, and the frames
    left against the bar.
  * `handoff_corridor` -- that target as a `objective.push_corridor`-shaped LINE, so the mid-chain
    keeps ride the state the chain must deliver rather than the coord itself. The two differ by
    0.46 deg of asked-for aim at the cycle-1 exit and 0.68 deg at cycle-2 range -- more than the
    whole window, and growing as the plan closes.

**AND THE TERMINAL IS NOT A SEARCH SPACE -- IT IS A CONSEQUENCE.** Measured off the s66 cycle-3
endpoint: sweep the WHOLE terminal alphabet (290 sticks x L, `full_herd._terminal_alphabet`) and
Tetra's position after each of the next FOUR frames has a spread of **0.00000 u** -- every branch
puts her at the identical place. Two mechanisms stack: the input pipeline acts 2 frames late, and by
then the actors have SEPARATED (`push_reserve` spent), so no stick re-establishes contact. That is
the whole explanation of four sessions of "rank-inert" terminals (s61 two configurations, s62 two,
s63 six byte-identical 31.406 u): there was nothing to rank. The one input sequence with any
authority left is the escape's own conversion, which flips Link -25.7 -> +17.6 in two frames and
drives him back into her -- which is why the s66 winner glides for ZERO frames. So the endgame is
decided at the cycle-3 endpoint, and the only place to spend effort is the CHAIN that produces it.

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.aim [beam|spec]``.
"""
import math

import tww_sim.core.fp as fp
from harness.tetrapush.from_f0 import _computed_center
from harness.tetrapush.tetra_plow import LINK_CO_R, TETRA_CO_R

#: The plow's zero-ejection bar, one canonical value (`full_herd.CO_RADII_BAR` is the same sum; this
#: module reads the radii directly so it stays importable from `full_herd` without a cycle).
CO_RADII_BAR = LINK_CO_R + TETRA_CO_R

#: The dCcS rank split (`from_f0.cc_push_pair` / `[[tetra-push-model]]`): Link and Tetra each eject
#: HALF the overlap, which is why the sustained herd rate is |speedF|/2 (`objective.PUSH_CEILING`).
SPLIT = 0.5


# --------------------------------------------------------------------- the exact one-frame oracle

def push_step(run):
    """**Tetra's next position, EXACT, without stepping her** -- the plow law read off the pre-step
    state (`[[tetra-push-model]]`, `from_f0.cc_push_pair`):

        ``mag = SPLIT * (CO_RADII_BAR - centre_feet)``  (0 at or past the bar)
        ``dir = unit(Tetra_feet - Link_exec_centre)``
        ``Tetra' = f32(Tetra + mag * dir)``

    Gated BIT-EXACT (`tests/test_aim.py::test_push_step_predicts_the_next_tetra_bit_exact`): over the
    contact frames of a real arrival the predicted ``(x, z)`` are ``_bits``-identical to what
    `from_f0.FreeRun.step` produces, whatever the stick -- the input cannot change the frame's push,
    only where Link is for the NEXT one. That is what makes an aim rank exact rather than a proxy:
    the direction and the magnitude of the next unit of placement are both already decided.

    Returns ``dict(mag, ux, uz, centre_feet, reserve, x, z)`` -- ``ux/uz`` the WORLD ejection unit
    (None at zero range), ``x/z`` the predicted next Tetra position."""
    c = _computed_center(run.link, init_frame=False)
    dx, dz = run.tx - c[0], run.tz - c[-1]
    d = math.hypot(dx, dz)
    reserve = CO_RADII_BAR - d
    mag = max(0.0, SPLIT * reserve)
    if d < 1e-9:
        return dict(mag=0.0, ux=None, uz=None, centre_feet=d, reserve=reserve, x=run.tx, z=run.tz)
    ux, uz = dx / d, dz / d
    return dict(mag=mag, ux=ux, uz=uz, centre_feet=d, reserve=reserve,
                x=fp.f32(run.tx + mag * ux), z=fp.f32(run.tz + mag * uz))


def push_reserve(run):
    """``CO_RADII_BAR - centre_feet``: the ejection still stored in the overlap -- what the escape
    can spend on placement without Link closing (each frame takes `SPLIT` of the deficit, so the
    geometric series of a static Link sums to the whole reserve). See the module docstring for how
    the measured escape residuals sit against it."""
    return CO_RADII_BAR - push_step(run)['centre_feet']


def eject_unit(run, hl):
    """The aim: the plow's ejection direction in herd coordinates ``(along, lat)``. None when the
    centre coincides with her feet."""
    p = push_step(run)
    if p['ux'] is None:
        return None
    return (p['ux'] * hl.dx + p['uz'] * hl.dz, p['ux'] * hl.px + p['uz'] * hl.pz)


# --------------------------------------------------------------------------- the aim vs the thread

def corridor_aim_error(run, hl, corridor):
    """**The aim as a MID-CHAIN quantity: how far a roll entry's ejection points off the push
    corridor** (session 67) -- signed degrees, positive = aiming to the high-lateral side.

    This is the same measurement as `aim_miss` one or two cycles earlier, and it is what decides a
    chain's straightness, because the push law integrates: Tetra's displacement over a contact phase
    is the SUM of its per-frame ejections, so the direction a roll carries her is the (magnitude-
    weighted) mean of its aims. Measured on the s66 plan's three rolls -- mean aim
    ``+2.55 / -6.42 / +16.56`` deg against travel ``+2.98 / -6.36 / +18.13`` -- and the entry aim
    predicts it to a few degrees, because the aim does not swing much inside a roll.

    So "a straight herd" is not a property of a roll AIM (the stick), it is the SQUARENESS of the
    junction endpoint the roll fires from. And the lateral that matters is Link's exec CENTRE's, not
    his feet's: at the s66 roll-2 entry his feet sat **+2.22 u** off Tetra's lateral while the aim was
    **-10.84 deg** -- the centre leads the feet ~17 u, and it led sideways. `full_herd`'s ``align_keep``
    ranks on the feet (``metrics['lat']``), which is why keeping by it has measured inert.

    ``corridor`` is `objective.push_corridor`. Returns signed degrees, or None at zero range."""
    ev = eject_unit(run, hl)
    if ev is None:
        return None
    ta, tl = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
    tgt = corridor['target']
    want = math.atan2(tgt[1] - tl, tgt[0] - ta)
    return math.degrees(math.atan2(ev[1], ev[0]) - want)


def _thread_ends(thread):
    """The target segment's two ends in herd coordinates."""
    lo, hi = thread['along_lo'], thread['along_hi']
    return (lo, thread['lat_at'](lo)), (hi, thread['lat_at'](hi))


def aim_window(t_along, t_lat, thread):
    """**The razor**: the directions from ``(t_along, t_lat)`` that reach the thread, as the bearings
    of its two ends (radians, measured from the down-herd axis, negative = losing lateral), plus the
    angular width between them.

    It is narrow for a structural reason, not a numerical one: the thread lies 12.2 deg off the herd
    axis and the approach comes in 13-14 deg off it, so Tetra arrives nearly END-ON to a 47.6 u
    segment. Measured at the s66 handoff (Tetra along 881.6, lat +21.19) the window is **2.1 deg**
    wide once `objective.PLACEMENT_BAND` is allowed for -- which is why an aim 12 deg steep cannot be
    salvaged by pushing further, and why the along slack is not the freedom it looks like.

    Returns ``dict(lo, hi, width, lo_dist, hi_dist)`` -- bearings sorted ascending, with the distance
    to each end."""
    (a0, l0), (a1, l1) = _thread_ends(thread)
    b0 = math.atan2(l0 - t_lat, a0 - t_along)
    b1 = math.atan2(l1 - t_lat, a1 - t_along)
    lo, hi = (b0, b1) if b0 <= b1 else (b1, b0)
    return dict(lo=lo, hi=hi, width=hi - lo,
                lo_dist=math.hypot(a0 - t_along, l0 - t_lat),
                hi_dist=math.hypot(a1 - t_along, l1 - t_lat))


def _ray_segment_miss(o, u, p, q):
    """Closest approach between the ray ``o + t*u`` (t >= 0) and the segment ``p..q``, in the plane.
    Returns ``(miss, t_at_min, s_at_min)`` with ``s`` the segment parameter in [0, 1]. Exact (the
    two-segment closest-pair algebra with one end left open), so the miss it reports IS the
    perpendicular distance a rank can compare against the placement band."""
    dx, dz = q[0] - p[0], q[1] - p[1]
    # minimise |o + t*u - (p + s*d)|^2 over t >= 0, s in [0, 1]
    a = u[0] * u[0] + u[1] * u[1]
    b = -(u[0] * dx + u[1] * dz)
    c = dx * dx + dz * dz
    wx, wz = o[0] - p[0], o[1] - p[1]
    d_ = u[0] * wx + u[1] * wz
    e = -(dx * wx + dz * wz)
    det = a * c - b * b
    best = None
    cands = []
    if abs(det) > 1e-18:
        t = (b * e - c * d_) / det
        s = (b * d_ - a * e) / det          # from a*t + b*s = -d, b*t + c*s = -e
        if t >= 0.0 and 0.0 <= s <= 1.0:
            cands.append((t, s))
    for s in (0.0, 1.0):                    # segment ends: closest point on the ray to each
        t = -(d_ + b * s) / a
        cands.append((max(0.0, t), s))
    t = 0.0                                 # the ray's own origin against the segment
    s = min(1.0, max(0.0, -(e + b * t) / c)) if c > 1e-18 else 0.0
    cands.append((t, s))
    for (t, s) in cands:
        px, pz = o[0] + t * u[0], o[1] + t * u[1]
        qx, qz = p[0] + s * dx, p[1] + s * dz
        m = math.hypot(px - qx, pz - qz)
        if best is None or m < best[0]:
            best = (m, t, s)
    return best


def aim_miss(run, hl, thread):
    """**How far the current aim misses the target thread**, and what it would cost to ride it.

    The ray is Tetra's position along `eject_unit` -- the direction the NEXT unit of push takes her,
    exactly (`push_step`). The miss is its closest approach to the thread SEGMENT in u, directly
    comparable to `objective.PLACEMENT_BAND`; ``travel`` is how far she must be pushed to reach that
    closest approach, which against `push_reserve` says whether the escape can pay for it.

    The aim ROTATES as Link moves, so this is a snapshot: exact for the next frame, a predictor over
    a phase. Measured bias over the s66 escape atoms, worth knowing before trusting it as a rank: the
    residual the atom actually delivers comes out **8-13 deg STEEPER** than the aim at handoff
    (Link closes on her through the conversion, which swings the centre), so a handoff aiming at the
    window's shallow edge is the one that lands. The exact test stays `away_walk.probe`.

    Returns ``dict(miss, travel, seg_s, along, lat, bearing, window, deg_error, deg_bias)``;
    ``deg_error`` is the signed angle from the aim to the nearest edge of `aim_window` (0 inside it),
    positive = the aim is too SHALLOW (not enough lateral), negative = too STEEP."""
    ev = eject_unit(run, hl)
    ta, tl = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
    if ev is None:
        return None
    (p, q) = _thread_ends(thread)
    miss, t, s = _ray_segment_miss((ta, tl), ev, p, q)
    bearing = math.atan2(ev[1], ev[0])
    w = aim_window(ta, tl, thread)
    if bearing < w['lo']:
        deg_error = math.degrees(bearing - w['lo'])
    elif bearing > w['hi']:
        deg_error = math.degrees(bearing - w['hi'])
    else:
        deg_error = 0.0
    return dict(miss=miss, travel=t, seg_s=s, along=ta, lat=tl, bearing=bearing, window=w,
                deg_error=deg_error, deg_bias=math.degrees(bearing - 0.5 * (w['lo'] + w['hi'])))


def centre_lat_needed(run, hl, thread):
    """**Squareness as a number**: where Link's exec Co-centre must sit LATERALLY for the aim to
    point inside `aim_window`, and how far that is from where it sits now.

    The aim is ``unit(Tetra - centre)``, so with the centre's along gap ``g`` fixed the lateral is
    what steers it: aiming at bearing ``m`` (as a lateral-per-along slope) needs the centre at
    ``lat_Tetra - m * g``. That makes the trade the chain has been paying explicit -- session 63
    found the corridor-good cycle-3 endpoint leaves Link 47 u off Tetra's lateral, and this says how
    much of that has to go.

    Returns ``dict(gap, lat_now, lat_lo, lat_hi, delta)`` -- the window's two admissible centre
    laterals and the SMALLEST signed move that enters it (0 when already inside)."""
    c = _computed_center(run.link, init_frame=False)
    ca, cl = hl.along(c[0], c[-1]), hl.lateral(c[0], c[-1])
    ta, tl = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
    gap = ta - ca                                    # + = the centre is UP-herd (behind) her
    w = aim_window(ta, tl, thread)
    lats = sorted((tl - math.tan(w['lo']) * gap, tl - math.tan(w['hi']) * gap))
    if lats[0] <= cl <= lats[1]:
        delta = 0.0
    else:
        delta = lats[0] - cl if cl < lats[0] else lats[1] - cl
    return dict(gap=gap, lat_now=cl, lat_lo=lats[0], lat_hi=lats[1], delta=delta)


# --------------------------------------------------------------------------- the handoff spec

def thread_miss(along, lat, thread):
    """How far a POINT in herd coordinates is from the target thread SEGMENT (not from a line):
    ``dict(miss, seg_s)``. `landing_miss` is this applied to a run plus an escape residual, and
    `full_herd.roll_probe`'s ``land`` axis applies it to a delivered roll -- one implementation, so a
    keep and the verdict it predicts cannot disagree by arithmetic."""
    (p, q) = _thread_ends(thread)
    dx, dz = q[0] - p[0], q[1] - p[1]
    c = dx * dx + dz * dz
    s = 0.0 if c < 1e-18 else min(1.0, max(0.0, ((along - p[0]) * dx + (lat - p[1]) * dz) / c))
    return dict(miss=math.hypot(along - (p[0] + s * dx), lat - (p[1] + s * dz)), seg_s=s)


def landing_miss(run, hl, thread, resid):
    """**The EXACT half**: where a MEASURED escape residual leaves her, against the thread.

    ``resid`` is ``(along, lat)`` as `away_walk.escape_atom` reports it (``resid_along``/
    ``resid_lat``) -- Tetra's whole displacement over the escape's conversion frames. Her landing is
    then a POINT, not a ray, so the miss is exact and needs no aim bias allowance: this is what
    `aim_miss` is a cheap predictor OF. Returns ``dict(miss, along, lat, seg_s)``."""
    ta, tl = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
    la, ll = ta + resid[0], tl + resid[1]
    tm = thread_miss(la, ll, thread)
    return dict(miss=tm['miss'], along=la, lat=ll, seg_s=tm['seg_s'])


def handoff_target(thread, resid, *, seg_s=0.0):
    """**The spec solved BACKWARDS**: the handoff state an escape with residual ``resid`` must be
    given, in herd coordinates -- the thread point at ``seg_s`` (0 = the near end, the frame-minimal
    one) minus the residual. This is the number the CHAIN aims at, and the reason a chain rank cannot
    be escape-blind: the target moves ~44 u up-herd and ~5 u across from the coord itself.

    Returns ``(along, lat)``."""
    (p, q) = _thread_ends(thread)
    s = min(1.0, max(0.0, float(seg_s)))
    tp = (p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1]))
    return (tp[0] - resid[0], tp[1] - resid[1])


def handoff_rows(rows, hl, resid):
    """**The placement rows as the HERD's target rather than the ESCAPE's** (session 70): every coord
    translated up-herd by the measured residual ``resid`` = ``(along, lat)``, in WORLD coordinates so
    the result drops into any ``placements=`` parameter unchanged (`full_herd.rank_key`,
    `objective.placement_thread`, `objective.push_corridor`, `full_herd._placement_dist`).

    `handoff_target` is this for ONE point on the thread; this is the whole set, which is what a rank
    needs -- `objective.plan_bound` measures a distance to the NEAREST coord and
    `objective.thread_frames` minimises over WHERE on the thread she stops, so both want the target
    set moved, not a single point substituted.

    Why a rank needs it at all (the session-69 measurement it answers): the thread has 47.6 u of along
    slack, so an endpoint anywhere inside along 937.5..984.1 pays ZERO along cost -- and the s69
    cycle-3 endpoints sat at 947, i.e. 53 u past the state the herd had to deliver, entirely free to
    the rank and worth ~4 frames of the run's 78-80 against a 75-frame budget. Shifted, the same
    segment is 893.9..940.5 and 947 is past its far end.

    A pure translation, so the thread built from these rows keeps its slope, length and off-axis angle
    (`objective.placement_thread`) -- gated in `tests/test_aim.py`."""
    dx = resid[0] * hl.dx + resid[1] * hl.px
    dz = resid[0] * hl.dz + resid[1] * hl.pz
    out = []
    for p in rows:
        q = dict(p)
        q['x'], q['z'] = p['x'] - dx, p['z'] - dz
        out.append(q)
    return out


def handoff_corridor(env, hl, thread, *, rows=None, feet=56.0, resid=None, seg_s=0.0):
    """**The line the CHAIN must ride, which is NOT the line to the coord** (session 69) -- the same
    shape as `objective.push_corridor` (``target``/``slope``/``lat_at``/``offset``) so it drops into
    every keep that reads one, but aimed at `handoff_target` instead of at the nearest genuine coord.

    Why it is a different line at all: the escape spends ~44 u of placement AFTER the herd hands over
    (`landing_miss`), so a chain that rides the corridor to the COORD aims past the state it has to
    deliver -- and the error is of the same order as the whole `aim_window` (**0.53-0.62 deg**).
    Measured from Tetra's start, the two lines' slopes are ``+0.008472`` (coord, target along 937.5
    lat +7.94) and ``+0.002764`` (handoff, along 893.9 lat +2.47), and the aim they ask for from an
    on-line Tetra differs by **0.46 deg at the cycle-1 exit (along 276), 0.68 deg at cycle-2 range
    (along 500) and 1.19 deg by along 700**. It GROWS as the plan closes, which is the wrong way
    round for a bias to be left in.

    The residual is MEASURED, not assumed (`[[no-overtuned-constants]]`): probe the real escape atom
    (`away_walk.probe`) on an on-line mid-depth arrival at the thread's near end. Its depth barely
    matters and its distance from the coord does -- over ``feet`` 52..64 the residual runs 45.96..40.04
    u, moving the target along 891.9..897.8 and the asked-for aim by **0.04 deg**, i.e. 1/14th of the
    window, while dropping the correction entirely costs 0.68 at the same range. So ``feet`` is a knob
    inside the noise and the default is the shallow end of the measured handoff band (feet ~52-56,
    `handoff_spec`) -- the depth a grazing arrival actually reaches.

    Returns the corridor dict plus ``resid``/``feet``; ``ok`` is False (and the fields fall back to
    `push_corridor`'s) if the probe atom does not fire, so a caller never silently rides a guess."""
    from harness.tetrapush import objective as O
    from harness.tetrapush import full_herd as FH
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush import seeds
    rows = seeds.load_placements()[0] if rows is None else rows
    if resid is None:
        near = min(rows, key=lambda p: hl.along(p['x'], p['z']))
        nd = FH.synthetic_hot_arrival(env, hl, near['idx'], d_short=0.0, feet=float(feet))
        res = AW.probe(nd['run'], hl)
        if res is None or not AW.fires(res):
            cor = dict(O.push_corridor(hl, rows))
            cor.update(resid=None, feet=float(feet), ok=False)
            return cor
        resid = (res['resid_along'], res['resid_lat'])
    ta, tl = handoff_target(thread, resid, seg_s=seg_s)
    slope = tl / ta
    return dict(target=(ta, tl), slope=slope, lat_at=lambda a: slope * a,
                offset=lambda a, l: abs(l - slope * a), resid=resid, feet=float(feet), ok=True)


def handoff_spec(run, hl, thread, frames, *, band=None, budget=None, escape_frames=4, resid=None):
    """**What a cycle-3 endpoint must satisfy for the escape to place her** -- the three measurements
    in one call, so an upstream keep can be gated on PREDICTION alone (no rollout, no atom), with the
    same call reporting the EXACT verdict once a residual has been probed.

      * ``aim_ok``   -- the escape's landing point is inside ``band`` of the thread. With ``resid``
        given that is `landing_miss` (EXACT, and the only form to trust as a verdict); without it,
        `aim_miss` -- the ejection ray reaching the thread at all, which is the next frame's
        direction exactly and the phase's direction only to within the bias `aim_miss` documents.
      * ``range_ok`` -- the travel to that closest approach is within `push_reserve`. CONSERVATIVE by
        measurement, not exact: the escape delivers MORE than the reserve (34.8-47.9 u against
        reserves of 27.1-43.1 on the on-line bed) because its conversion drives Link back into her,
        so a state passing this certainly has the magnitude, and one failing it may still land.
      * ``frames_ok`` -- ``frames + escape_frames`` inside ``budget`` (`objective.frame_floor`'s
        ``budget``, i.e. the floor plus `objective.TIMELOSS_BUDGET`).

    **The spec has a solution, and that is the session-67 result worth carrying.** Solve it backwards
    (`handoff_target`): the escape delivers ~44 u from a mid-depth on-line handoff, so the state it
    must be handed is the thread's near end MINUS that -- Tetra at along **~894, lateral ~+2.5**, on
    line, at ``feet`` ~52-56. A herd that stays straight reaches along 894 in **69 frames** at
    `objective.PUSH_CEILING`, and the escape's 5 frames finish it: **74 frames, +1, inside Dereck's
    PREFERRED budget**. So the plan is not out of frames; the s66 chain hands over 25 u short in along
    and 22 u high in lateral, and spends ~26 u of the difference sideways (`objective.push_budget`).

    Returns the measured fields plus ``ok`` (all three). ``escape_frames`` is the measured 4-5 frame
    atom (`away_walk`, no turnaround), not a tuned constant -- pass the probed ``freeze_f`` when one
    is in hand."""
    from harness.tetrapush import objective as O
    band = O.PLACEMENT_BAND if band is None else float(band)
    am = aim_miss(run, hl, thread)
    lm = None if resid is None else landing_miss(run, hl, thread, resid)
    res = push_reserve(run)
    cl = centre_lat_needed(run, hl, thread)
    total = int(frames) + int(escape_frames)
    out = dict(aim_miss=None if am is None else am['miss'],
               deg_error=None if am is None else am['deg_error'],
               travel=None if am is None else am['travel'],
               window_deg=None if am is None else math.degrees(am['window']['width']),
               landing_miss=None if lm is None else lm['miss'], exact=lm is not None,
               reserve=res, centre_lat_delta=cl['delta'], frames=int(frames), total=total,
               escape_frames=int(escape_frames), band=band)
    out['aim_ok'] = (lm['miss'] <= band) if lm is not None else (am is not None
                                                                and am['miss'] <= band)
    out['range_ok'] = True if lm is not None else (am is not None and am['travel'] <= res)
    out['frames_ok'] = (budget is None or total <= int(budget))
    out['ok'] = bool(out['aim_ok'] and out['range_ok'] and out['frames_ok'])
    return out


# --------------------------------------------------------------------------- CLI

def _print_spec(label, run, hl, thread, frames, budget=None):
    am = aim_miss(run, hl, thread)
    cl = centre_lat_needed(run, hl, thread)
    sp = handoff_spec(run, hl, thread, frames, budget=budget)
    print("  %-12s Tetra along %7.2f lat %+7.2f | aim %+6.2f deg  window %+6.2f..%+6.2f "
          "(%4.2f deg wide)"
          % (label, am['along'], am['lat'], math.degrees(am['bearing']),
             math.degrees(am['window']['lo']), math.degrees(am['window']['hi']),
             math.degrees(am['window']['width'])))
    print("               miss %7.2f u  travel %6.2f u  reserve %6.2f u  "
          "centre lat %+7.2f -> [%+7.2f, %+7.2f] (move %+6.2f)"
          % (am['miss'], am['travel'], sp['reserve'], cl['lat_now'], cl['lat_lo'], cl['lat_hi'],
             cl['delta']))
    print("               deg_error %+6.2f  aim_ok %-5s range_ok %-5s frames %d(+%d) -> %s"
          % (sp['deg_error'], sp['aim_ok'], sp['range_ok'], sp['frames'], sp['escape_frames'],
             'OK' if sp['ok'] else 'no'))
    return sp


def main(argv):
    import warnings
    warnings.simplefilter('ignore')
    from harness.tetrapush import seeds, objective as O, full_herd as FH
    from harness.tetrapush.reposition import HerdLine
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    rows, _ = seeds.load_placements()
    thread = O.placement_thread(hl, rows)
    bar = O.frame_floor(env, rows)
    cmd = argv[0] if argv else 'spec'
    print("THE HANDOFF AIM (session 67): the thread is %.1f deg off the herd axis, so the "
          "directions\nthat reach it are a WINDOW, not a half-plane.\n" % thread['deg_off_axis'])
    if cmd == 'spec':
        for feet in (56.0, 64.0, 72.0):
            for d_short in (30.0, 45.0):
                nd = FH.synthetic_hot_arrival(env, hl, 287, d_short=d_short, feet=feet)
                _print_spec("feet %.0f/-%.0f" % (feet, d_short), nd['run'], hl, thread,
                            bar['frames_int'] - 4, budget=bar['budget'])
                print()
    elif cmd == 'beam':
        from harness.tetrapush import beam_io
        path = argv[1] if len(argv) > 1 else '_generated/s66_solve_beams.json'
        beam = beam_io.rebuild_beam(env, beam_io.load_beams(path), cycle=3, hl=hl)
        for i, nd in enumerate(beam):
            _print_spec("node %d" % i, nd['run'], hl, thread, nd['frames'], budget=bar['budget'])
            print()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
