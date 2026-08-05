# "The second frame needs the pushed actor MOVED - the axis nothing has searched" (session 99, 2026-08-04)

> **status: historical** - this records a lead that was correctly identified as unexplored and wrongly
> assumed to be *available*. The reasoning reproduces and is still sound as far as it goes: the reachable
> hull depends on Link's facing and frame budget alone, the pushed actor's position is a free argument to
> every scan, and moving her does move the residual locus relative to the hull. What was missing is the
> clause the second frame actually fails - the endpoint's penetration past the wall plane, not the
> residual - and her authority over THAT is 0.015 u per u, because she is plowed as the roll sweeps past.
> Current truth is [strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md). Kept for the lesson:
> naming the untried axis is not the same as pricing it, and the cheapest way to price one is to make
> every clause of the acceptance test a number first.

## What was claimed (session 99)

Having found that the delivered clip fires the cut two frames later than `procFrontRoll` allows, and that
a per-thrust station census read `0 live` at thrust 13 in all four cells sampled, the handoff named the
placement as the route to it:

> **THE TETRA-PLACEMENT SEARCH -- the only plausible route to thrust 13, and nothing in 99 sessions has
> touched it.** Dereck named it twice ("the roll entry/tetra positioning will need to be adjusted"). The
> 4-frame reachable hull depends only on facing + frame budget, while HER placement moves the residual
> locus relative to it -- so she is the lever that can bring a thrust-13 station inside the floor.

The plan was a sweep of the 288 genuine placement coords × thrust 13 × the delivered and low cells,
ranked by distance from the delivered coord so the herd cost stayed payable.

## What it actually was (session 100)

The sweep was run, one ring of it, and the answer was an invariance rather than a hit: over a ±3 u grid of
placements the thrust-13 penetration past the wall plane moved from −0.157 to −0.217 u - never through
zero, and 0.015 u per u of her. Three measurements then explained why, and none of them is about dust:

- **`resid ~ 0` pins the push.** `old` is brace-pinned and the step-plus-lunge is constant per facing, so
  the razor forces the endpoint onto the `old → S` ray; the push direction is the CC geometry's and she
  sits ~80 u away, so a few u of her rotates it ~2° and leaves the magnitude the razor demands unchanged.
- **She is PLOWED.** Her position on the CUT frame is where the roll's own Co cylinder has shoved her, not
  where she was placed, so a closer placement is a plow that starts earlier and ends in the same place.
- **The failing clause was never the residual.** Thrust 13's endpoint lands ~0.19 u short of the near side
  of the wall, at every one of the 25 cells in the aim window that has a razor solution at all. The
  residual was already zeroable; the cut simply does not reach.

So the second frame is refused by the corner's geometry and the *first* one (thrust 14, `plan_cost` 22
against the delivered 23) is the whole prize. The station census the lead was built on was right about
thrust 13 being empty and could not say why - a census counts, and counting cannot distinguish "no dust
here" from "nothing here could ever reach".

## The lesson

**An untried axis is a hypothesis with a price, and the price is usually cheaper to measure than the
axis is to search.** One 60-second invariance scan retired a sweep that was scoped at 288 placements ×
24 leans (~2.4 h), and the thing that made it 60 seconds was printing the acceptance test's other clause
- which no pass in 100 sessions had ever looked at, because it does not vary and so never became a rank.
