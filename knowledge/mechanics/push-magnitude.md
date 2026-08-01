# How FAR a Co push moves an actor - the per-frame depth law and the sustained ceiling

**Answers:** How far can an actor-vs-actor push move an actor in one frame? Is `|speedF|/2` a hard
bound or an average? What sets the sustained push rate? Why does a shallow contact push less, and what
does that cost a plan that needs the contact to END shallow?
**Status:** validated - the per-frame law is verified frame by frame over a whole 72-frame herd
(2026-07-31); the sustained/per-frame distinction is measured off the recorded courtyard TAS window
(2026-07-28); the depth-vs-distance trade is measured over 1525 real planner arrivals (2026-07-31).
**Source:** decomp `dCcS::SetPosCorrect` (`d_cc_s.cpp:138`) - the mechanism page is
[actor-push.md](actor-push.md); live courtyard herd captures; the planner measurements are
[`harness/tetrapush/objective.py`](../../harness/tetrapush/objective.py) `PUSH_CEILING` /
`push_budget` and [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py)
`push_profile` / `recovery_row`.

---

This is the MAGNITUDE half of the [Co push](actor-push.md): that page says which way an actor is
shoved and by what mechanism, this one says how far, how fast a sustained push goes, and what a plan
pays to change the contact depth.

## The sustained rate is a STEADY STATE, not a bound

Because the two actors eject in opposite directions along the centre line, a sustained push settles at
each moving **half** of the pusher's own step: with Link at the roll cap the pushed actor advances at
most `26 / 2 = 13.0` u/frame **on average**. That is the bound every herd plan is scored against
([`harness/tetrapush/objective.py`](../../harness/tetrapush/objective.py) `PUSH_CEILING`).

**A single frame is not bounded by it.** The depth is measured to Link's **animated** Co centre
([actor-push.md](actor-push.md)), which moves by his foot term *plus* the pose swing that leads/trails
his feet 6-28 u - so a frame in which the swing carries the centre forward pushes far harder than half
the foot term. Measured on the courtyard herd (GZLJ01, the recorded TAS window): the biggest single
frame advances Tetra **18.84 u** (his 4th, a FRONT_ROLL, ~1.45x the "ceiling"), and a 23-frame search
cycle sustains **13.36 u/frame**. The swing cancels over a long enough window - the pose returns -
which is why his 44-frame mean is **12.758**, 98.2% of 13.0 and under it.

So: use 13.0 u/frame for a sustained rate or a distance estimate, never as a per-frame law, and never
as a hard floor on a plan's length (a ~25-frame window can beat it by ~0.3-0.6 u/frame). A search cycle
that exceeds it is not a physics bug. Gated by
[`tests/test_objective.py`](../../tests/test_objective.py)`::test_the_push_ceiling_is_a_sustained_rate_not_a_per_frame_law`.

## What a single frame IS bounded by, exactly

The ejection is the overlap depth halved, so with the pushed actor at rest the frame's push equals
`(R_link + R_actor - centre_distance) / 2` - for the courtyard pair `(80 - centre_feet) / 2`, measured
to the ANIMATED centre. Verified frame by frame over a whole 72-frame herd (2026-07-31):
`centre_feet` 45.9 → 17.036 u, 59.6 → 10.188 u, every frame, rolls included.

So the SUSTAINED rate is set by the MEAN centre distance, and 13.0 is its fixed point - each frame the
pusher advances by his step and both actors eject, leaving `centre_next ≈ R_sum - advance`, which at
the roll cap 26 settles at 54 and hence 13.0 u/frame. A window beats it exactly when the pose swing
carries the animated centre in faster than the foot term does, and loses to it when contact goes
shallow: measured on a courtyard arrival, the rolls sustain 99.6% of the ceiling at mean `centre_feet`
54.1 while the junction frames manage 93.5% at 55.4.

## Depth trades against distance, and a plan cannot have both

The law above has a consequence for any plan that cares about the contact depth at the END of a push,
and it is the reason a push planner sits on a frontier rather than a single best: **the depth an
arrival ends at and the distance it delivered are anti-correlated**, because a contact that finishes
shallow was shallow (and so pushing weakly) on its way there.

Measured over 1525 real planner arrivals in two banded pools, best-achieved placement distance against
the arrival's final `centre_feet` (lower distance = better placed):

| final `centre_feet` | 46-48 | 48-50 | 50-52 | 52-54 | 54-56 | 56-60 | 60+ |
|---|---|---|---|---|---|---|---|
| best distance, pool A | 34.63 | **34.16** | 35.46 | 38.07 | 37.54 | 40.27 | 41.64 |
| best distance, pool B | **24.50** | 24.99 | 25.46 | 25.75 | 26.69 | 28.78 | 29.90 |

Monotone in both pools past 50 u, at **0.32-0.53 u of placement per u of depth**. So a plan that wants
a shallow finish - e.g. because separation frames are set by depth, so a shallow arrival needs fewer of
them - buys those frames at a measured price in the distance the push delivered, and the two
requirements of any frame budget move in OPPOSITE directions. Price both against the same arrival; a
depth taken from one pool and a distance from another describes no reachable state.

## See also

- [actor-push.md](actor-push.md) - the mechanism: cyl-cyl overlap, the rank-table 50/50 split, which
  way each actor goes, and the animated Co centre the depth is measured to.
- [roll.md](roll.md) - where the `speedF` 26 roll cap that sets the 13.0 fixed point comes from.
- [reference/constants.md](../reference/constants.md) - the canonical radii and cap values.
