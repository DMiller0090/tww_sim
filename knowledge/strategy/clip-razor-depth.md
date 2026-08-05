# Which thrusts a corner can clip at all, before any dust is hunted

**Answers:** My frame-minimal plan presses B provably late and the earliest thrust returns nothing - is
that thin dust, or geometry, or the set I searched? What quantity decides whether a cut reaches through
the seam at all / how do I screen a configuration in one call instead of buying another lottery? Can
moving the PUSHED ACTOR buy penetration, and at what SCALE? Why does the same roll clip from one distance
and not from another?
**Status:** measured and gated (session 100) on the flooded-Hyrule Tetra corner, in
[`tests/test_razor_depth.py`](../../tests/test_razor_depth.py) (10 + 1 slow), with the falsifying
direction (`genuine ⇒ depth > 0`) gated over 275 genuine rows sampled on the locus.
**Source:** [`harness/tetrapush/razor_depth.py`](../../harness/tetrapush/razor_depth.py) (`depth_of`,
`razor_solutions`, `screen`, `thrust_map`), [`harness/rollstab/geometry_tetra.py`](../../harness/rollstab/geometry_tetra.py)
(`genuine_clip`, `S`), [`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py)
(the reachable hull the solutions are taken inside).

[roll-cut-thrust-floor.md](../mechanics/roll-cut-thrust-floor.md) established that the cut can dispatch
two frames earlier than the delivered clip does, and that the frame-minimal ranking could not see the
cost. This page is what happens when you go and collect those frames: **one of them is refused by the
corner's geometry**, and the quantity that says so screens a whole configuration in one call.

## The depth at the razor

`genuine_clip` is three clauses, and only two of them are ever searched for:

| | clause | what a search does with it |
|---|---|---|
| leverage | the pushed actor is still in Co range on the cut frame, else the push is 0 | seeds are taken from it |
| **depth** | the endpoint lands **behind** a wall plane | *never asked* |
| razor | the segment threads the seam gap - `resid ~ 0` to ~1e-4 u | the whole lottery |

Write the second one as a number - the penetration past the nearer plane at the cut endpoint
(`razor_depth.depth_of`, the two plane values a `ShoveCtx` sweep already returns) - and notice what the
razor does to it. **S is the corner VERTEX and lies on BOTH wall planes**, so pointing the cut at S puts
the endpoint on the `old → S` ray, and

    depth  ≈  |base + push|  −  |S − old|

with `base` (the roll step plus the cut root translate) a constant per facing. The depth at the razor is
therefore decided by two things only: **how close the roll braces**, and **how much push survives to the
cut frame**. That is [clip-exit-angle.md](clip-exit-angle.md)'s "brace plus the 49.74 u lunge pin the cut
start to a 0.65 u pocket" restated as a quantity a search can rank, rather than as a bound on the exit
angle.

## The measurement, and the frame it kills

Every in-hull razor solution at the delivered cell, Newtoned from the whole hull rather than from
`hull_seeds`' picks, at 4 and 5 walk frames (48 / 45 / 35 solutions):

| thrust | `plan_cost` | `old` | \|S − old\| | depth | admits? |
|---|---|---|---|---|---|
| 15 (delivered) | 23 | (−1692.314331, −955.076111) | 49.3812 | **+0.2533** | yes |
| 14 | 22 | (−1692.314697, −955.041870) | 49.4053 | **+0.2074** | yes |
| 13 (the floor) | 21 | (−1692.317749, −954.737122) | 49.6209 | **−0.1868 … −0.3464** | **no** |

**How tightly `old` is pinned is itself the mechanism.** At thrust 15 it is **bit-identical** at all 48
solutions - CrrPos has finished sliding Link into the corner by the cut frame, so the entry cannot move it.
Two frames earlier he is still moving: thrust 14's solutions spread over 4e-4 u of z, thrust 13's over
~0.07 u with one `old` each. So firing at `cut_step` 15 costs **0.24 u of brace** and **0.45 u of push**,
the cut lunge is a constant, and the endpoint lands ~0.19 u short of the near side of the wall.

Over the whole 45-cell aim window at the frame floor, thrust 13 reads depth < 0 at **all 25 cells that
have a razor solution at all** (−0.472 … −0.133), while thrust 14 admits at 23 of 25 - so **thrust 14 at
`plan_cost` 22 is a frame available with no other change**. The negative carries its resolution control,
which thrust 13 needs because its `old` is not pinned: over grid steps 2.0 / 1.0 / 0.5 / 0.25 the best
depth moves inside **0.008 u** and does not trend toward zero (−0.1949 / −0.1901 / −0.1868 / −0.1898).

**But read that negative with its set named, because the set is doing the work.** Everything above is
measured over the frame-floor reachable hull, which sits ~239 u from the corner brace - and that is what
makes it a statement about plans rather than geometry. See the next section.

## The two families, and why a hull hides one of them

A roll of `cut_step` N travels **26N u**. From the 4-frame hull, 239 u out, Link reaches the wall around
step 9 whatever the thrust, and CrrPos then slides him along it - a little less each frame. So the hull
contains only the **arrive-early-and-slide** family, where the razor picks a slid `old` and two fewer slide
frames *is* the 0.19 u. The tell was in the numbers all along: those solutions cut from |S−old| 49.62 while
the delivered clip cuts from 49.38.

Swept with no hull (851 598 Tetra × entry pairs, then the placement plane with Newton runs filtered back to
sane geometry - `|S−old| ≤ 56 u`, walkable, inside the box):

- **1167 razor solutions at `cut_step` 15 land on the exact brace point thrust 15 cuts from** (|S−old|
  49.3812). The brace is not the barrier it appeared to be.
- Entries ~**390 u** out - 26 × 15, the roll's own travel - put the cut on the frame Link **arrives**,
  with no slide at all, and there the depth goes **positive**: **+0.0399** at Tetra 100 u in −z of her
  console read, entry (−1422.7771688289, −677.8451372479), walkable.
- So the pushed actor's real scale on this axis is ~**100 u**, not the ±3 u a herd tolerates. Priced on the
  wrong magnitude inside the wrong family, she reads inert.

**The remaining gap is barrier clearance, not the plane.** `genuine` also needs the swept segment to clear
the CrrPos barrier, and every genuine row measured anywhere on this corner sits at depth ≥ **0.1273** (the
four known-live configurations read 0.1273 / 0.2073 / 0.2533 / 0.3398, each bit-constant across its own
genuine population). So the arrive-exactly family is ~**0.087 u** short - a fifth of what the hull-bounded
picture showed, in a family no pass has searched, with the push as the lever (0.446 there against 0.613 at
thrust 15).

## The pushed actor: inert at herd scale, decisive at roll scale

She is the term in `push`, and `hull_scan` takes her position as its first argument. **Within the
arrive-and-slide family she is inert**: over a ±3 u grid the thrust-13 depth moves **0.015 u per u**
(−0.157 … −0.217), because she is PLOWED as the roll sweeps past, so her overlap on the CUT frame is set by
the roll's geometry rather than by where she started. ±3 u is the scale a herd tolerates, and at that scale
the reading is honest and useless.

**At roll scale she changes the family.** The through-going solution above needs her ~100 u from her
console read; that is 8+ frames of herding at the measured lateral authority and far outside the placeable
thread, so it is a different herd, not a tweak to this one. Which is the actual open question for the second
frame: **what herd puts her and Link in the arrive-exactly geometry, and does it cost less than the two
frames it buys?**

One more walk frame does not open the slide family (`plan_cost` would still be 22): the bigger hull reaches
2.3x the entries and gets no nearer the plane.

## How to use it, and how not to

- ``depth ≤ 0`` **is a proof about the configurations you measured, and the ENTRY SET is part of the
  configuration.** The endpoint is on the near side of both planes, and no razor, camera or lean moves it -
  but a different distance-to-corner is a different `old`, so say which entry set you swept. Saying it over
  the frame-floor hull is a claim about plans at the floor; saying it "anywhere" needs the hull removed
  (that mistake, and its tell, is in
  [../history/thrust-13-refused-by-geometry.md](../history/thrust-13-refused-by-geometry.md)).
- ``depth > 0`` **is only an admission.** Dust still has to exist on the locus (`hull_scan`) and a plan
  still has to land on it (`confirm_entry`).
- **It is not a density model.** Against the per-thrust live-station census it does not even correlate:
  cell 2549 at thrust 15 reads depth +0.513 with **0** live stations, cell 2553 at thrust 14 reads +0.127
  with **918**. Read it as a gate, never as a rate.
- **Screen before you buy.** One configuration is ~5 s and the whole window × thrust is ~3 min
  (`thrust_map`), against hours for one camera pass of a dust lottery.

## The rules

**Ask which clause of your acceptance test is failing before you buy more draws against it.** Six sessions
priced entry candidates by residual-band probability - the razor clause - while the endpoint at those
configurations could not reach the wall at all. A residual is the quantity that *varies*, so it is the one a
search naturally ranks on; the clause that is a hard gate had never been printed. When a lottery comes up
empty, spend the next hour making each clause a number, not on more tickets.

**Then name the set that number was measured over.** The same measurement, read over the frame-floor hull,
says "this thrust cannot clip"; read over the geometry it says "this thrust cannot clip *from 239 u out*",
and those differ by a family of entries 150 u further back. A reachable hull exists to price plans - the
moment it bounds a claim about what the corner allows, the claim has inherited a herd's arrival position.

## See also

- [../mechanics/roll-cut-thrust-floor.md](../mechanics/roll-cut-thrust-floor.md) - why thrust 13 is the
  floor, and the frame cost the walk count hides.
- [clip-station-reachability.md](clip-station-reachability.md) - the sibling scope error one level out:
  the bands were measured outside the reachable set.
- [clip-exit-angle.md](clip-exit-angle.md) - the 0.65 u pocket this law is the ranked form of, and the
  exit-angle window it bounds.
- [../history/thrust-13-refused-by-geometry.md](../history/thrust-13-refused-by-geometry.md) - the
  superseded reading, that the floor thrust was refused *anywhere* on this corner.
