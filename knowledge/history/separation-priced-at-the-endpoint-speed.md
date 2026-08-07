# "The separation is a price, not a wall -- 0.67 to 3.68 frames" (session 114, 2026-08-07)

> **status: historical** - the arithmetic reproduces exactly; the frame price drawn from it does not
> survive being run. What holds: a specification that pays both delivery predicates needs 92.5-156.8 u
> of separation, every beam node sits at 38.09-75.25 u, and endpoint speedF spans -25.727..+18.500. What
> was wrong is dividing the first by the second and calling the quotient a frame cost. Session 115 ran
> the frames: the separation moves at **8.3-10.6 u/frame** (Link is CLOSING at the endpoint, so the
> 25.727 belongs to a direction he is not travelling in), and every deep prologue makes the escape atom
> refuse outright -- **0 of 672 variants fire** at three nodes against controls firing 56-1964, with
> ``l_ok`` the sole blocker on all 672. Current truth is
> [strategy/the-separation-is-not-a-suffix.md](../strategy/the-separation-is-not-a-suffix.md).

## What was claimed (session 114)

That the last unpaid term of a 95.00 endpoint had been converted "from a wall into an addend": the
separation's rate is Link's endpoint speed, capped at 25.727 u/frame, so the cheapest specification
(node 8, row 9, atom 6) owed **0.67 frames** on top of its 96.00 and the solved node-0 endpoint owed
**3.68** on top of its 95.00 -- honest totals ~96.7 and ~98.7, both beating the banked 101. The next
step followed from it: re-cut the herd with the separation in the last cycle's keep, priced at that cap
so a deep endpoint is not ranked out for the frames it spends getting there.

The claim was hedged in the right places -- it was called an UPPER bound at the fastest separating frame
available, and the endpoint a specification rather than a candidate -- and it was still wrong, in a way
the hedges did not cover.

## Why it did not survive

Two independent errors, and the second is the one that matters:

1. **The rate belongs to a direction Link is not travelling in.** At a herd endpoint his speedF is the
   untarget backslide's -25.4, but its along-component points DOWN-line at ~+12 u/frame: he is still
   chasing her. A separating prologue has to reverse that first, so the best sustained rate measured
   over a 16-bearing x 4-magnitude grid at all 64 nodes is 8.3-10.6 u/frame, not 25.727.

2. **The separation cannot be bought as a suffix at any rate.** Turning Link costs the EBS
   (speedF -25.45 -> -11.43), the turnaround that is the atom's only facing lever requires the EBS be
   PRESERVED (`away_walk._SNAP_KEEP_SPEED` -24.5, and `snap_csangle` returns None at every receded
   endpoint where every control has a window), so the atom's own first frame turns Link into Tetra's
   +-90 deg cone (+3.51 -> -37.64 deg) and ``l_ok`` refuses every variant. Separation, momentum and
   facing are one resource.

## The lesson

A price is not a price until the frames have been run. The quotient (units owed / units per frame) is
an arithmetic statement about a DISPLACEMENT; a frame cost is a claim about a reachable STATE, and the
two differ whenever the frames that buy the displacement also spend something the plan needs later.
Here the same frames paid for the depth and destroyed the posture the next stage is written for -- and
nothing in the arithmetic could see it, because the arithmetic had no representation of the posture.

The next step it implied survives, for a better reason than it was given: the separation does belong in
the cut that chooses endpoints, not because it can be bought there cheaply but because the last roll is
the ONLY stage that can deliver depth while leaving the EBS posture intact.
