# Which thrusts a corner can clip at all, before any dust is hunted

**Answers:** My frame-minimal plan presses B provably late and the earliest thrust returns nothing - is
that thin dust, or geometry, or the set I searched? What quantity decides whether a cut reaches through
the seam at all / how do I screen a configuration in one call instead of buying another lottery? Can
moving the PUSHED ACTOR buy penetration, and at what SCALE? Why does the same roll clip from one distance
and not from another?
**Status:** measured and gated (sessions 100-101) on the flooded-Hyrule Tetra corner, in
[`tests/test_razor_depth.py`](../../tests/test_razor_depth.py) (16 + 2 slow), with the falsifying
direction (`genuine ⇒ depth > 0`) gated over 275 genuine rows sampled on the locus and the hull-free,
placement-constrained thrust-13 refusal gated over all 45 aim cells.
**Source:** [`harness/tetrapush/razor_depth.py`](../../harness/tetrapush/razor_depth.py) (`depth_of`,
`law_of`, `floor_at_brace`, `placeable`, `placeable_screen`, `razor_solutions`, `screen`, `thrust_map`),
[`harness/rollstab/geometry_tetra.py`](../../harness/rollstab/geometry_tetra.py)
(`genuine_clip`, `S`), [`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py)
(the reachable hull the frame-floor solutions are taken inside).

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

## What the depth is bought with: the push's PROJECTION

`base` is not just constant per facing - it is **a constant**, 49.220225 u. The roll step and the cut root
translate rotate together, so the facing only turns the pair (49.220227 / 49.220232 at the window's ends,
sine-table quantization), and the thrust does not enter it at all. Write the law with that in:

    d_ray  =  49.220225 + push·û  −  |S − old|          `razor_depth.law_of`
    depth  =  κ · d_ray                                  κ = |n·û| ≈ 0.712 here

**So every clip on this corner is bought with `push·û`, the push's projection onto the `old → S` ray**, and
`push·û` is set by WHERE THE PUSHED ACTOR SITS relative to Link's Co centre on the cut frame - he is shoved
directly away from her, so `push·û > 0` means she is up-ray BEHIND him and his recoil throws him at the
corner. Measured in-hull at the delivered cell, both terms move together with the frames:

| thrust | `plan_cost` | push·û | \|push\| | \|S−old\| | depth |
|---|---|---|---|---|---|
| 15 | 23 | +0.5175 | 0.6129 | 49.3812 | +0.2532 |
| 14 | 22 | +0.4773 | 0.5661 | 49.4053 | +0.2075 |
| 13 | 21 | +0.1304 | 0.1588 | 49.6202 | **−0.1901** |

**Only one of those two columns belongs to the thrust** (Dereck, session 101: *"it's all the same
animations"* - and he is right). The cut lunge is a constant at every thrust, and shifting the entry by
whole roll steps puts Link on the **bit-identical** brace two frames earlier: `old` reads
(−1692.3143310546875, −955.07611083984375) at thrust 13, 14 and 15 alike. So the brace column above is a
property of the ENTRY SET the hull allows, not of the frame the cut fires on, and it is recoverable by
entering closer.

**The push column is not recoverable, and it is the only real difference.** The cut-frame contact is a
~1.2 u graze on an 80 u radius sum, and Link's Co-cylinder centre is *posed from the model*
([../mechanics/link-co-centre.md](../mechanics/link-co-centre.md)) - so it is indexed by the ROLL'S OWN
ANIMATION FRAME, swinging **1.1 … 31.3 u** off his position over the roll at **2-9 u per frame**. From the
shifted entry that reproduces the brace exactly, her console spot gives a push of **0.0000** at thrust 13
where it gives 0.6129 at thrust 15: two frames earlier the same standing position is not touching her.
Same animation, a different frame of it, and the push that buys the depth is gone.

## The floor is the corner's, and it is measured

`genuine` needs the swept segment to clear the corner as well, and below some penetration it never does -
the endpoint is behind both planes but the corner edge still catches the sweep. That floor is measured
directly in endpoint space (`floor_at_brace`: sweep `pred = S + d·û + ε·perp` and find the first `d` whose
ε band holds a genuine endpoint), over the brace locus CrrPos actually parks Link on:

    depth ≥ 0.1154 … 0.1216      no trend in the brace, none in the aim → a constant of the corner

Session 100 read the same wall as "≥ 0.1273" from the four populations that happened to have live dust,
which cannot tell a corner constant from a coincidence of those braces. Screen against the low end
(`DEPTH_FLOOR`), then check a survivor against its own brace.

## Two families, and the clause that decides between them

A roll of `cut_step` N travels **26N u**. From the 4-frame hull, 239 u out, Link reaches the wall around
step 9 whatever the thrust and CrrPos slides him along it, so the hull contains only the
**arrive-early-and-slide** family - and two fewer slide frames *is* the 0.19 u. Remove the hull and entries
~**390 u** out put the cut on the frame Link **ARRIVES**, with no slide at all. Session 100 measured the
depth going positive there, at Tetra 100 u in −z of her console read.

**That placement is 3.54 u behind wall B and she cannot stand in it.** The engine does not check a seed -
`placed_step` writes her position with no motion, so her CrrPos has no sweep to line-check and
`wall_correct`'s outward-offset segment misses a point already behind the plane
([../model/placement-standability.md](../model/placement-standability.md)). From inside the wall she grazes
Link's Co cylinder from a bearing no reachable spot offers, and that graze *was* the +0.0399.

Constrained to placements a herd can deliver (≥ 50 u off both planes, her BG wall radius; the 288 live
coords sit at ≥ 56.98), swept over every aim cell with **no hull anywhere in the search**
(`placeable_screen`):

- **thrust 13 is refused at all 45 cells** - best depth **−0.0208** at cell 2554, which does not reach the
  plane, let alone the floor. A 4× finer placement grid moves it 0.0007.
- The refusal has a mechanism rather than a budget: **the push that aims at the corner is the same push
  that shoves Link off the brace**, and it costs `|S−old|` faster than it buys `push·û`. Cell 2549 carries
  push·û +0.3656 at a brace of 49.6836; cell 2554 carries +0.1834 at 49.4329; every cell loses the trade.
- The arrive-exactly family's real trade is now legible: it holds **the best brace on the corner**
  (49.2611) and aims its push **75° off** the ray, because arriving exactly is precisely giving up the
  braced frames in which the push is accumulated and straightened.

## The pushed actor: inert at herd scale, and bounded by where she can stand

She is the term in `push`, and `hull_scan` takes her position as its first argument. **Within the
arrive-and-slide family she is inert**: over a ±3 u grid the thrust-13 depth moves **0.015 u per u**
(−0.157 … −0.217), because she is PLOWED as the roll sweeps past, so her overlap on the CUT frame is set by
the roll's geometry rather than by where she started. ±3 u is the scale a herd tolerates, and at that scale
the reading is honest and useless.

At roll scale she sets the contact BEARING, which is the whole of `push·û` - but only from spots she can
occupy. Swept over the arrive-exactly entry at ±40 u and ±200 u, `push·û` is pinned at **0.11-0.12** and
the depth tops out at +0.0427: a fresh contact is only available on the crescent his cylinder has just
reached, i.e. AHEAD of him, and a from-behind push needs the braced frames the arrival gives up. The
placements that do aim it well are the ones inside the wall
([../model/placement-standability.md](../model/placement-standability.md)).

One more walk frame does not open the slide family (`plan_cost` would still be 22): the bigger hull reaches
2.3x the entries and gets no nearer the plane. Neither does the **lean** - `m351C` decays 35% per roll
frame, so a −388 draw is −1 by the cut step and ±3000 s16 moves the depth 0.0003 u
([../mechanics/roll-lean-decay.md](../mechanics/roll-lean-decay.md)).

## How to use it, and how not to

- ``depth ≤ 0`` **is a proof about the configurations you measured, and the ENTRY SET is part of the
  configuration.** The endpoint is on the near side of both planes, and no razor, camera or lean moves it -
  but a different distance-to-corner is a different `old`, so say which entry set you swept. Saying it over
  the frame-floor hull is a claim about plans at the floor; saying it "anywhere" needs the hull removed
  (that mistake, and its tell, is in
  [../history/thrust-13-refused-by-geometry.md](../history/thrust-13-refused-by-geometry.md)).
- ``depth > 0`` **is only an admission.** Dust still has to exist on the locus (`hull_scan`) and a plan
  still has to land on it (`confirm_entry`).
- **Every axis you sweep needs its own deliverability clause.** A placement is a position she can STAND in
  (`placeable`, ≥ 50 u off both planes) and the engine will not tell you otherwise; an entry is a point a
  plan can walk to (`is_walkable`, then the reachable hull). Applying one axis's filter to the other axis
  is how a graze from inside a wall reads as the second frame
  ([../model/placement-standability.md](../model/placement-standability.md)).
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

**And check that the set is one the game can produce.** Naming the set is not enough if the set contains
configurations that cannot exist: removing the hull to answer "what does the corner allow" also removed the
only thing that had been keeping the pushed actor outside the walls. Each axis a search gains needs the
clause that says which of its values are deliverable - the hull was Link's, and hers was never written.

## See also

- [../mechanics/roll-cut-thrust-floor.md](../mechanics/roll-cut-thrust-floor.md) - why thrust 13 is the
  floor, and the frame cost the walk count hides.
- [clip-station-reachability.md](clip-station-reachability.md) - the sibling scope error one level out:
  the bands were measured outside the reachable set.
- [clip-exit-angle.md](clip-exit-angle.md) - the 0.65 u pocket this law is the ranked form of, and the
  exit-angle window it bounds.
- [../model/placement-standability.md](../model/placement-standability.md) - the clause on HER axis, the
  50 u bar, and why the engine leaves it to the caller.
- [../mechanics/roll-lean-decay.md](../mechanics/roll-lean-decay.md) - why the lean is not a lever at a
  late cut, and the frozen-entry trap that makes it look like one.
- [../history/thrust-13-refused-by-geometry.md](../history/thrust-13-refused-by-geometry.md) - the
  superseded reading, that the floor thrust was refused *anywhere* on this corner.
- [../history/arrive-exactly-through-the-plane.md](../history/arrive-exactly-through-the-plane.md) - the
  superseded reading that both frames were live, from a placement inside the wall.
