# "The floor thrust is refused by the corner's geometry, anywhere on it" (session 100, first half, 2026-08-05)

> **status: historical** - this records a measurement that reproduces exactly and a verdict drawn from it
> that was scoped wrong, corrected the same day. What holds: at `cut_step` 15 the cut endpoint lands
> 0.19-0.35 u short of the nearer wall plane at every razor solution INSIDE the 4-frame reachable hull, at
> all 25 cells of the aim window that have one, and ±3 u of the pushed actor moves that by 0.015 u per u.
> What was wrong is the word *anywhere*: the hull is anchored ~239 u from the corner brace, and a roll of
> `cut_step` N travels 26N u, so from there Link always arrives at the wall early and SLIDES - the hull
> only ever contained the arrive-early family. Remove it and a second family appears at ~390 u out where
> the cut fires as he arrives, and the depth there goes POSITIVE. Current truth is
> [strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md). Kept for the lesson below, which is the
> same one session 99 learned one level out and which I then repeated.

## What was claimed (session 100, first half)

Having derived that `resid ~ 0` forces the cut endpoint onto the `old → S` ray and so pins the penetration
past the wall plane, and having screened all 45 cells × 3 thrusts:

> Over the whole 45-cell aim window at the frame floor, thrust 13 reads depth < 0 at **all 25 cells that
> have a razor solution at all**. `depth ≤ 0` **is a proof**: no razor, camera, lean, placement or
> candidate volume moves the endpoint through a plane. **One of the two frames is available (thrust 14,
> cost 22); the other is not, anywhere on this corner.**

The pushed actor was priced out alongside it, on a ±3 u grid: 0.015 u of depth per u of her, with the
mechanism that she is plowed as the roll sweeps past.

## What it actually was (same session, after Dereck said he wanted both frames)

Everything above was measured over `entry_reach`'s hull, which is the set of entries a 4-frame plan reaches
**from the delivered herd's arrival** - about 239 u from the corner brace. A `cut_step` N roll travels
26N u, so out of that hull Link reaches the wall around step 9 and CrrPos then slides him along it, each
frame a little less; the razor picks a slid `old`, and two fewer slide frames is exactly the 0.19 u.

Swept with no hull at all (851 598 Tetra × entry pairs, then the placement plane with the Newton runs
filtered back to sane geometry), the picture changes:

- **1167 razor solutions at `cut_step` 15 land on the very brace point thrust 15 cuts from** (|S−old|
  49.3812), so the brace is not the barrier it looked like;
- entries ~**390 u** out - 26 × 15, the roll's own travel - make the cut fire as Link ARRIVES rather than
  after sliding, and there the hull-free razor depth goes **positive**: +0.0399 at Tetra 100 u in −z,
  entry (−1422.777, −677.845), walkable, |S−old| 49.2792;
- so the pushed actor's real scale is ~100 u, not the ±3 u a herd tolerates - she was priced on the wrong
  axis, at the wrong magnitude, inside the wrong family.

The frame is still not banked: `genuine` also needs the swept segment to clear the CrrPos barrier, and
every genuine row measured anywhere on this corner sits at depth ≥ **0.1273**, so +0.0399 is ~0.087 u
short. But that is a search with a direction, not an impossibility.

## The lesson

**A negative inherits the scope of the set it was measured over, and "at the frame floor" is a scope.**
Session 99 closed a six-session drought by finding that its acceptance bands were measured outside the
reachable hull. One session later I argued the opposite direction of the same mistake - taking a hull that
exists to price *plans* and letting it bound a claim about *geometry*. The tell was available and I wrote
it down without reading it: the sweep found razor solutions at |S−old| 49.62 while the delivered clip cuts
from 49.38, which says the entry set was the constraint, not the corner. **When a screen says "impossible",
name the set out loud and ask what put it there.**
