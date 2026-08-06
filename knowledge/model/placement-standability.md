# A seeded actor position the engine will never correct

**Answers:** My sweep found a placement that clips - can the actor actually STAND there? Why does a
seeded position inside a wall push Link perfectly happily instead of being ejected? What is the minimum
clearance a herd can deliver Tetra to? Which of my search's axes needs a standability filter?
**Status:** measured and gated (session 101) on the flooded-Hyrule Tetra corner, in
[`tests/test_razor_depth.py`](../../tests/test_razor_depth.py)
(`test_a_placement_is_a_position_she_can_stand_in`). The empirical check is the 288 live-validated
genuine coords, which clear the bar by 7 u.
**Source:** [`harness/tetrapush/razor_depth.py`](../../harness/tetrapush/razor_depth.py) (`placeable`,
`TETRA_WALL_MIN`), `tww_sim/core/_shovec.ShoveCtx` (`_run`, the `placed_step` seed),
`tww_sim/core/npc_zl1.py` (`WALL_R`).

---

## The gap

`ShoveCtx._run` (`tww_sim/core/_shovec`) seeds the pushed actor by **writing her position** at
`placed_step` and zeroing her speed. Her own CrrPos then runs that same frame - and finds nothing to complain about:

- `line_check` sweeps `old → new`, and a written position has `old == new`, so there is no segment to
  cross a wall triangle with;
- `wall_correct` tests the distance from a segment offset **outward** by her wall radius, so a point
  already *behind* the plane measures `radius + penetration` from it and is skipped as out of range.

So a placement inside a wall **stays inside the wall**, and the sweep reports its clip exactly as it
would a real one. Nothing in the engine is wrong here: `_run`'s seed is an initial condition, and the
game never produces one by teleporting an actor into geometry. The clause belongs to the caller, and
until session 101 no caller had it.

## The bar

CrrPos never leaves her nearer a wall plane than her **BG wall radius, 50 u** (`npc_zl1.WALL_R`), so
that is the floor on a deliverable placement. The empirical check agrees with room to spare: all **288**
live-validated genuine coords in `_generated/tetra_placements.tsv` sit at **≥ 56.98 u** from both planes.

    placeable(t)  ⇔  planeA(t) ≥ 50  ∧  planeB(t) ≥ 50          `razor_depth.placeable`

## What it cost to not have it

Session 100 removed the reachable hull, swept 851 598 placement × entry pairs, and found the cut
endpoint going **through** the wall plane at thrust 13 for the first time - the result that made both
frames look live. That placement is **3.54 u behind wall B**. From inside the wall she can graze Link's
Co cylinder at a bearing no reachable spot offers, which is the whole of the +0.0399 it read. With the
filter on, thrust 13 is refused at every aim cell with no hull anywhere in the search
([../strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md)).

**The tell was in the sweep's own output, one column over.** Every one of those runs printed
`walkable True` - for LINK's entry. The filter existed and was applied to the wrong actor.

## The rule

**A search axis that positions an actor needs a standability clause, and it is not the same clause as
the one on the actor that moves.** Feasibility filters get written for the search's original axis and
then silently under-cover every axis added later: Link's entry had `is_walkable` from the first pass
because entries are where the planner walks, and her placement never got one because she arrived as a
parameter rather than as a plan. When a new axis joins a search, ask what makes a value of it
*deliverable*, not just evaluable.

## See also

- [../strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md) - the depth law this filter guards,
  and the hull-free verdict it changes.
- [../mechanics/wall-response.md](../mechanics/wall-response.md) - `line_check` / `wall_correct`, the two
  tests that a written position slips between.
- [../history/arrive-exactly-through-the-plane.md](../history/arrive-exactly-through-the-plane.md) - the
  superseded reading this corrects.
- [../mechanics/tetra-follow.md](../mechanics/tetra-follow.md) - what she does once she is somewhere she
  can stand.
