# Aiming localises the razor and not the fan

**Answers:** I know exactly where my plan's walk has to end - can I skip the branches that cannot get
there? Why can't I search the held stick coarse-to-fine? Why does knowing the endpoint barely narrow the
enumeration? What IS the right way to spend a fan's frame budget?
**Status:** MEASURED (session 161) on the flooded-Hyrule Tetra corner at the console item, walk 4.
Gated in [`tests/test_aimed_fan.py`](../../tests/test_aimed_fan.py): the step bound, the prune's
admissibility against a blind run, the ordering's losslessness, and the measured selectivity itself.
**Source:** [`harness/tetrapush/aimed_fan.py`](../../harness/tetrapush/aimed_fan.py)
(`reachable`, `rank`, `annulus`, `aim_curve`, `step_bound`).

---

[entry-strip.md](entry-strip.md) turned the razor's acceptance into a target a walk can steer toward: an
entry that clips, inverted through `roll_entry` into the walk ENDPOINT a plan has to reach. The obvious
next move is to spend that on the enumeration - prune the branches that cannot reach the endpoint - and
pay off the 114x that containment costs ([fan-containment-gap.md](fan-containment-gap.md)). It was built
and it does not pay. The measurements are all at the console item, walk 4.

## The target is a curve, and it has to be

`genuine` is `resid` inside a narrow positive band, so the entries that clip form a strip ~1.2e-04 u wide
and long. One `aim` returns one point on it; `aim_curve` walks ALONG the level curve (perpendicular to
the residual's gradient) and re-aims each step, keeping only the samples the sim calls genuine. At the
console configuration 14 of 24 samples land, spanning **5.09 u** of walk endpoint.

That span is the point. The fan's endpoint lattice is 0.2-0.4 u, three orders coarser than the strip, so
a fan can only ever MEET a curve - a point target at that resolution is unhittable. Every measurement
below tests against the nearest sample of the curve, never a single point.

## What a stepped frame can do: 17.85 u, and the first one is blind

The prune needs an upper bound on displacement. Displacement per stepped frame is `|speedF|` and nothing
else - no walls in the Courtyard sim, and at walk 4 a leaf never touches her (her span across a whole fan
is 0.000000 u). Measured over the full stride-1 alphabet off every base offset and off the console's own
junction:

| stepped frames | max total | per frame | max abs speedF |
|---|---|---|---|
| 2 | 35.70 u | 17.85 | 18.70 |
| 3 | 53.15 u | 17.72 | 17.45 |
| 5 | 85.00 u | 17.00 | 17.00 |

`aimed_fan.MAX_STEP` is 19.0 u against that - a search knob rather than a game constant, so it lives with
the tool and `step_bound` re-measures it instead of trusting it.

**A one-frame probe reads zero spread and means nothing.** At `input_delay = 1` the stick delivered on a
frame acts on the NEXT one, so a single stepped frame moves every draw in the alphabet the same 17.0000 u.
The same off-by-one in the other direction is what makes the prune's `frames` argument STEPPED and not
delivered: a hold of `j` delivered frames is `j + 1` stepped ones, and passing the delivered count bounds
the console's own junction at 38.0 u when it needs 57.0 - which pruned 20130 of 20130 junctions,
including the branch that contains the answer.

## The three discounts, and what each is worth

| discount | lossless? | measured |
|---|---|---|
| junction prune: drop what cannot reach the target | yes, admissible | **1.4x** |
| junction ordering: put the reachers first | yes, by construction | ~**2.4x** on time-to-first-hit |
| coarse-then-refine the held stick | **no** | refused |

**The prune is weak because the reach disc is nearly the whole reachable set.** Over 3 stepped frames the
alphabet's displacement runs 3.35 to 53.15 u against a 57 u disc, so an annulus buys almost nothing over a
disc and the disc keeps 14795 of 20130 junctions.

**The ordering is weak because the hold segment steers.** The leaves the fan actually KEEPS - at the cap
and rollable - do live on a thin annulus (33.65-34.00 / 49.60-51.00 / 64.53-68.00 u at 2 / 3 / 4 stepped
frames, against discs of 38 / 57 / 76), because holding the cap means going nearly straight. But that
annulus still spans a **33 degree arc** covering ~12 x 25 u per junction, and its bearing window is a
property of each junction rather than a constant - over 12 sampled junctions the union is 41% of the
circle. So knowing the endpoint pins the junction to an arc band most junctions are already in: ranked
against its own delivered endpoint, the console's junction lands **1366th of 3355**.

**Coarse-then-refine is refused because the endpoint map is discontinuous.** Adjacent byte-grid classes
land endpoints a median 0.156 u apart - and up to **54.2 u** apart. A Lipschitz bound over a coarse cell
is therefore 54 u wide and prunes nothing, so any coarse-to-fine hold search is a heuristic that can miss:
exactly the [fan-containment-gap.md](fan-containment-gap.md) failure in a new place. Refused rather than
tuned.

`at_cap` is not cheaply predictable either. It discards ~70% of leaves AFTER they are cloned, but the
survivor set is not a threshold in the decoded magnitude: at the console's own hold length 521 magnitude
groups are mixed, so the angle decides and a magnitude prune would drop real candidates.

## What this means for the search

Aiming is worth a great deal at the razor and very little at the fan, and the two must not be conflated.
Downstream of the enumeration the target is decisive - `offset_u` prices any row in ~15 us against ~1 s
for a screen, and the strip is a 1.2e-04 u target a Newton reaches in 4-5 steps. Upstream of it, the
enumeration's cost is set by the alphabet and the split set, and no geometric argument about where the
plan ends removes it.

So the contained fan's ~2 h an item stands, and the discount is ~2.4x on WHEN a hit appears rather than on
whether the item finishes. What the contained fan buys for that price is not a better lottery ticket but a
different population: with ~6900 at-cap leaves a junction over a ~300 u^2 cloud, a 5 u target curve and a
1.2e-04 u strip, the expected genuine count over 20130 junctions is in the hundreds, against the legacy
fan's zero-by-construction.
