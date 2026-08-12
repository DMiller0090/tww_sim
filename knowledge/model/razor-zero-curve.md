# The razor's zero is a curve, and one station is not a verdict

**Answers:** I screened a configuration and it came back "no clip for any position of hers" - how much of
her plane did that actually cover? Why does a Newton onto the residual never converge? Why can't I start
a descent from a seed a few u away? How far apart may stations on the curve be?
**Status:** MEASURED (session 159) on the flooded-Hyrule Tetra corner, at both configurations known to
clip and at the barren `w10_t15`. Gated in [`tests/test_admit_map.py`](../../tests/test_admit_map.py).
Builds on [genuine-residual-band.md](genuine-residual-band.md): the ladder at a station only works
because `genuine` is exactly `resid` inside the band.
**Source:** [`harness/tetrapush/admit_map.py`](../../harness/tetrapush/admit_map.py) (`walk_curve`,
`station_band`, `newton_to_zero`, `her_seeds`).

---

## The geometry every earlier verdict was read against

`resid` is a scalar on her 2-D start plane, so `resid = 0` is a **curve**, and it runs the length of a
contact region about 160 u across. Every negative in this work was read over a window a few u wide:
session 158's widest was a +-2 u plane, 7.1 M placements, and
[`razor_band.admits`](../../harness/tetrapush/razor_band.py) ladders along the gradient through ONE point
of the curve. Walking the curve instead, with a ladder at every station:

| configuration | curve walked | stations | admitting |
|---|---|---|---|
| the console's own clip | 116 u | 188 | **51 (27%)** |
| s154's accepted 101 | 67 u | 123 | **98 (80%)** |

So a **one-station screen misses an admitting configuration about three times in four** at the console's
own configuration. A zero has to name the arc it covered, and 4 u of a curve tens of u long is not the
same claim as "her plane is exhausted".

The admitting stations are not scattered: they come in contiguous runs of 3 to 13 stations separated by
gaps of 1 to 4, on one side of her own row. That is what sets the 1 u station spacing - a coarser walk
can step over a run.

## Two traps in walking it

**The corrector cannot use an absolute tolerance.** `resid` is quantized: 160801 placements return only
~1900-4700 distinct residual values, so the quantum is ~4e-06 and nothing finer is reachable. A Newton
aimed at 1e-08 therefore never converges, and the first version of this walk rejected every station after
its seed and reported the console's 116 u curve as **1 u long**. `CORRECT_TOL` is a fifth of the ladder's
span instead, because a station only has to land inside the range the ladder then sweeps - and the ladder
targets absolute residual levels, so it re-centres itself on whatever the station's own residual is.

**Out of contact there is no gradient to descend.** 5 u off her delivered row the razor stops depending
on her at all and `|grad|` is exactly 0.0 (the same reading `entry_search.zero_the_resid` gives for the
entry). So the locate cannot be a Newton from anywhere: `her_seeds` fires a fan of rays out of the braced
Co centre, keeps only the in-contact rows, and takes each sign change of `resid` between neighbours. The
curve runs ACROSS the contact region rather than along a ray, which is why a ray fan finds it for a few
ms where a 2-D grid of her plane costs 0.1-0.3 s.

## Honest limits

- A walk follows the curve **component** it was seeded on. A component that crosses no ray is not walked,
  so `screen` returns the ray count with the verdict.
- The arc is bounded (`ARC`, 25 u each way by default) and returned as `arc_neg` / `arc_pos`. A negative
  is a statement about that arc.
- Adaptive step halving keeps a sharply bending curve from truncating the walk, but a walk can still end
  early where the curve leaves contact. `w10_t15`'s reached 8 u before the first version gave up on it.
