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
"""WHAT A TETRA PLACEMENT COSTS IN FRAMES -- the conversion session 104 handed over (session 105).

Session 104 measured the herd saving of the `plan_cost`-21 placements as a DISTANCE (-50.6..+64.6 u
about the console placement) and said, correctly, that it is a distance and never a frame count. This
module is the conversion, and it is deliberately two conversions plus a screen, because a single number
here would hide how much of it is assumption.

  `arrival_frames`      -- THE ACCOUNTING, and it is off by three if you read the wrong field.
  `contact_at_arrival`  -- THE SCREEN: a placement she cannot statically occupy is not a placement.
  `rate_price`          -- her distance over the delivered plan's own sustained rate.
  `trajectory_price`    -- her position projected onto the delivered plan's own frame-vs-position curve.

The two prices AGREE to 0.4 frames on placements within ~2.6 u of that curve and diverge by up to 14
frames at 46 u off it, so the head of a ranking built on them is trustworthy and its tail is not.
Neither is a measurement: the real count owes a `full_herd.chain_herd` retargeted at the rows. See
knowledge/strategy/herd-price-of-a-placement.md, which holds every number and the negatives that go
with them (the delivered herd cannot be truncated; re-aiming its escape does not steer her).

Pure stdlib apart from the harness itself; no Dolphin.
"""
import math


def arrival_frames(seed):
    """The frame the WALK fan starts from -- `console_seed`'s ``n_last``, not its ``n_scored``.

    `entry_fan.plan_cost` counts from the ARRIVAL, and `entry_fan.base_core` replays the WHOLE
    delivered log before holding anything, so the arrival is the log's own length (78 = herd 71 +
    escape atom 7). ``n_scored`` (75) is where TETRA freezes, three frames earlier; Link still has to
    run the atom's tail to BE at an arrival, so pricing a candidate off 75 understates every total by
    the atom's post-freeze length."""
    return int(seed['n_last'])


def total_frames(arrival, plan_cost):
    """Frames from the state-2 seed to the cut: the arrival plus `entry_fan.plan_cost`.

    The banked deliverable is 78 + 23 = **101**; a `plan_cost`-21 plan has to arrive by 79 to beat it."""
    return int(arrival) + int(plan_cost)


def link_co_centre(run):
    """Link's exec Co centre at a run's current state -- the point the plow laws measure from
    (`from_f0._computed_center`). It LEADS his feet by 21.253 u at the console arrival, which is why
    a screen run on his feet is wrong by more than the thing it is screening for."""
    from harness.tetrapush.from_f0 import _computed_center
    return _computed_center(run.link)


def contact_at_arrival(centre, placement):
    """Is she inside Link's Co cylinder at the arrival? Returns the overlap depth (0.0 = clear).

    THE SCREEN, and it is about the CLOUD as much as about her. Every s104 station was qualified
    inside the 2-frame walk cloud measured from the console arrival, and that fan is COUPLED -- Link's
    own walk recoils off her Co cylinder at the full depth (`link_plow`). A placement in contact there
    is not a placement she statically occupies, and its cloud is not the cloud she was scored in.

    Only the arrival frame needs testing: from it Link walks +X+Z, away from both the corner and the
    herd, so a placement clear at the arrival stays clear for both walk frames. Contact returns at the
    ROLL, where it is wanted -- that push is what steers the cut."""
    from harness.tetrapush.tetra_plow import plow_depth
    return plow_depth(centre, placement)


def console_trajectory(env, log):
    """Tetra's per-frame position over a delivered log, on the 0-ULP `FreeRun`: ``[(n, x, z)]``, n
    from 1. The frame-vs-position curve `trajectory_price` reads."""
    from harness.tetrapush import seeds as SD
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    out = []
    for i, inp in enumerate(log):
        run.step(inp)
        out.append((i + 1, run.tx, run.tz))
    return out


def project_on_trajectory(traj, p):
    """Where a placement sits on that curve: ``(k_traj, lat_miss)`` -- the fractional frame index of
    the closest point on the polyline, and the perpendicular distance to it.

    Frames the trajectory does not move (the escape's separation frames, and the delivered plan's f73)
    are skipped rather than treated as zero-length segments, so ``k_traj`` never charges for a frame
    that herds nothing."""
    best = None
    for i in range(len(traj) - 1):
        (n0, x0, z0), (n1, x1, z1) = traj[i], traj[i + 1]
        dx, dz = x1 - x0, z1 - z0
        L2 = dx * dx + dz * dz
        if L2 == 0.0:
            continue
        t = ((p[0] - x0) * dx + (p[1] - z0) * dz) / L2
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        qx, qz = x0 + t * dx, z0 + t * dz
        d = math.hypot(p[0] - qx, p[1] - qz)
        if best is None or d < best[1]:
            best = (n0 + t * (n1 - n0), d)
    return best


def sustained_rate(t0, seed):
    """The delivered plan's own herd rate: her state-2-to-placement distance over ``n_scored``.
    939.4737 u in 75 frames = 12.5263 u/f, 96.4% of `objective.PUSH_CEILING` -- so the ceiling is a
    fair asymptote and this is what a real plan achieved."""
    d = math.hypot(seed['tetra'][0] - t0[0], seed['tetra'][-1] - t0[-1])
    return d / float(seed['n_scored'])


def atom_tail(seed):
    """The delivered escape's post-freeze length (78 - 75 = 3): the frames between where SHE stops
    and where LINK is at an arrival. Common to every candidate priced against this plan."""
    return int(seed['n_last']) - int(seed['n_scored'])


def rate_price(t0, seed, placement):
    """Herd frames to a placement at the delivered plan's sustained rate, plus the atom's tail.

    Assumes the herd is equally efficient toward any placement, which is optimistic for anything far
    off the delivered curve -- see `trajectory_price` for the other end of the bracket."""
    d = math.hypot(placement[0] - t0[0], placement[-1] - t0[-1])
    return d / sustained_rate(t0, seed) + atom_tail(seed)


def trajectory_price(traj, seed, placement, lateral_rate=None):
    """Herd frames to a placement read off the delivered plan's own curve: the frame it reaches that
    along-position at, plus the perpendicular miss at `objective.LATERAL_RATE`, plus the atom's tail.

    Returns ``(frames, k_traj, lat_miss)``. Its along term is a measurement of the delivered cadence
    (her per-frame step runs 8-17 u depending on where in the roll cycle it falls, so a mean rate
    smears it); its lateral term is still a rate, and a herd that leaves the curve at frame k does not
    simply add frames at the end -- which is why this is pessimistic in the tail."""
    from harness.tetrapush import objective as O
    r = O.LATERAL_RATE if lateral_rate is None else float(lateral_rate)
    k, lat = project_on_trajectory(traj, placement)
    return k + lat / r + atom_tail(seed), k, lat
