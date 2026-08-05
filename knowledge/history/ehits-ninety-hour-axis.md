# "The missing factor makes the axis a ~90 h lottery, so the question is whether any entry's own station has dust" (session 98, 2026-08-04)

> **status: historical** - this records a correct finding priced as a slower version of the same
> purchase. The measurement it rests on reproduces exactly and is still quoted: each draw really was
> priced by a band from a station a median 20.9 u away, and 0 of 100 draws really had dust at their own.
> What was wrong is the extrapolation from it - the un-measured factor was carried as a *small rate* (a
> 95% upper bound of ~3%, hence "≈30x, hence ≈90 h"), when it is not a rate at all: for the population
> that was actually bought it is **zero**, because those bands sit outside the set a 4-frame plan can
> reach, and for the configuration nobody was buying it is **0.0711**. Current truth is
> [strategy/clip-station-reachability.md](../strategy/clip-station-reachability.md). Kept for the
> lesson: a factor measured at 0 of N is a bound, and a bound is not a rate - it invites scaling the
> budget when it should have prompted asking where the failing measurement's population lives.

## What was claimed (session 98)

Having found that `lottery` priced each draw with a band measured tens of units away, the session folded
a bound on the missing factor into the budget and handed the axis over as a spend decision:

> Fold the measured first factor back in and the 450-draw population is worth ≤ ~0.03 expected clips,
> not 1.10. At the measured spread rate **E[hits] 1 is then not ~1 hour of compute but on the order of
> 90**, which is a different decision rather than a longer version of the same one.

And it named the follow-up question as a search that had never been run:

> If the corner is still wanted, the live question is no longer "buy more draws" but **"is there any
> entry whose OWN station has dust"** - a different search, over stations rather than over cameras.

## What was actually true

The follow-up question was the right one and its answer is not a number of hours at all - it is that the
bands and the draws were never in the same set. All **450** draws sit inside the 4-frame reachable hull;
all **20** bands they were priced against sit **10.196-19.400 u** outside it. For that population the
missing factor is not ~3%, it is exactly zero, so the 90 h was a price on something unpurchasable.

And the axis it was quoted for is not the barren one. Run over the **measured hull** rather than
`reach_radius`'s 94 u box, cell 2553 is empty at **thrust 15** (0 live over 12823 in-hull stations, all
1040 leans) and carries **918 live walkable stations, 7.11%** of its in-hull locus, at **thrust 14** - a
configuration that costs zero extra frames and that session 96 had dropped on a clock argument. The
honest price, with both factors measured at the station the candidate stands on, is **~1.5e-05 per kept
draw**, order **1000 h** - a bigger number than the one being retired, for a target that at least exists.

## The lesson

"0 of 100, so ≤3%" is a sound bound and it invited exactly the wrong next move - scale the budget by the
bound and keep buying the same scope. Three checks would have separated them, all cheaper than the buy
that preceded this:

- **ask where the failing measurement's population lives** relative to the set the candidates are drawn
  from. A distance of 20.9 u between a draw and its band is a number about geometry, and it was read as
  a number about probability.
- **run the control**. The delivered clip's own configuration answers "is there reachable dust" in under
  a second, and the contrast between 518 and 0 is not a result that needed a 3-hour pass to see.
- **re-open the scope the search narrowed for cost**, before buying more of what is left. Thrust 14 was
  dropped for clock and it is where the reachable dust is; six sessions read "0 genuine" as a reason to
  buy more of the same scope rather than to question it.
