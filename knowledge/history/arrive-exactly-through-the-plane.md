# "Both frames are live - the arrive-exactly family goes through the plane" (session 100, second half, 2026-08-05)

> **status: historical** - the measurement reproduces exactly and the family is real; the configuration
> it was measured at is one the pushed actor cannot stand in. At ~390 u out the cut does fire as Link
> ARRIVES rather than after sliding, and at that entry the endpoint reads **+0.0399 u past the wall
> plane** at thrust 13 - the first positive depth ever measured for the floor thrust. But the placement it
> needs puts Tetra **3.54 u BEHIND wall B**, and the engine does not check a seed
> ([../model/placement-standability.md](../model/placement-standability.md)). Constrained to placements a
> herd can deliver, thrust 13 is refused at all 45 aim cells with no hull in the search. Current truth is
> [../strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md). Kept for the lesson, which is the
> third scope error on this corner in three sessions and the first one that was not about a hull.

## What was claimed (session 100, second half, on Dereck's re-ask for both frames)

The first half had ruled thrust 13 "refused by the corner's geometry, anywhere on it"; that was scoped to
the frame-floor hull and was corrected the same day
([thrust-13-refused-by-geometry.md](thrust-13-refused-by-geometry.md)). Removing the hull and sweeping
851 598 placement × entry pairs found a second family:

> Entries ~390 u out - 26 × 15, the roll's own travel, so the cut fires as Link **ARRIVES** rather than
> after sliding - go **POSITIVE**: depth **+0.0399** at Tetra 100 u in −z of her console read, entry
> (−1422.7771410239, −677.8451682961), walkable, |S−old| 49.2792. What is still missing is barrier
> clearance, not the plane: every genuine row on this corner sits at depth ≥ 0.1273, so this family is
> **~0.087 u short** - a fifth of the hull-bounded gap, in a family no pass has searched.

## What it actually was

**Tetra at 100 u in −z of her console read is 3.54 u behind wall B.** `placeable` is now the one-line
check; at the time nothing applied one to her. She can never be there: CrrPos would never leave her
nearer than her 50 u BG wall radius to a wall plane, and all 288 live-validated genuine coords sit at
≥ 56.98 u. The engine keeps her there because `placed_step` writes a position with no motion, so her own
`line_check` has no segment to test and `wall_correct`'s outward-offset segment misses a point already
behind the plane.

And the depth *came from* that: from inside the wall she grazes Link's Co cylinder from a bearing no
reachable spot offers. With placements constrained and no hull anywhere in the search, the best thrust-13
depth over all 45 cells is **−0.0208** (cell 2554) - it does not reach the plane, let alone the floor,
and a 4× finer grid moves it 0.0007.

The "0.087 u short" figure was also measured against the wrong bar. The floor is not the minimum over the
four populations that happened to have live dust (0.1273); measured directly in endpoint space over the
whole brace locus it is **0.1154 … 0.1216** with no trend - a constant of the corner.

## The tell

**It printed `walkable True` on every row - for Link's entry.** The filter existed, was correct, and was
applied to the actor that walks. Her placement had joined the search as a parameter rather than as
something a plan has to deliver, so it never acquired a feasibility clause.

The second tell was in the law's own decomposition, unmade at the time: that family's push is **75° off**
the `old → S` ray while the delivered clip's is 32° off. A push aimed three-quarters sideways is the
signature of an actor beside Link rather than behind him - which, on this corner, means somewhere he
cannot have pushed her to.

## The lesson

**Feasibility filters are written for a search's first axis and silently under-cover every axis added
after it.** Three sessions running, the corner has answered a question that was asked over the wrong set:
session 99's bands were measured outside the reachable set, session 100's negative inside a hull that
excluded a whole entry family, and this one over placements the pushed actor cannot occupy. The
generalisation is not "name the set" (that was the last lesson and it was already written down) - it is
that **each axis carries its own deliverability clause, and adding an axis means adding one**.

## See also

- [../model/placement-standability.md](../model/placement-standability.md) - the clause, the bar, and why
  the engine leaves it to the caller.
- [../strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md) - the current verdict and the law in
  its push-projection form.
- [thrust-13-refused-by-geometry.md](thrust-13-refused-by-geometry.md) - the sibling scope error the same
  day, one level out.
