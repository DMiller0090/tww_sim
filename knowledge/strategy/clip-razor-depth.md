# Which thrusts a corner can clip at all, before any dust is hunted

**Answers:** My frame-minimal plan presses B provably late and the earliest thrust returns nothing - is
that thin dust or is it geometry? How do I REFUSE a configuration in one call instead of buying another
lottery? Can moving the PUSHED ACTOR buy penetration? What quantity decides whether a cut reaches
through the seam at all?
**Status:** measured and gated (session 100) on the flooded-Hyrule Tetra corner, in
[`tests/test_razor_depth.py`](../../tests/test_razor_depth.py) (8 + 1 slow), with the falsifying
direction (`genuine ⇒ depth > 0`) gated over 15 000+ entries.
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
have a razor solution at all** (−0.472 … −0.133), while thrust 14 admits at 23 of 25. **One of the two
frames is available (thrust 14, cost 22); the other is not, anywhere on this corner.**

Because thrust 13's `old` is *not* pinned, that negative does rest on how finely the razor curve was
sampled - so it carries a resolution control. Over grid steps 2.0 / 1.0 / 0.5 / 0.25 the best depth moves
inside **0.008 u** and does not trend toward zero (−0.1949 / −0.1901 / −0.1868 / −0.1898) against a
**0.19 u** shortfall: a ~24x margin, so refinement is not what stands between this thrust and a clip.

## The pushed actor cannot pay for it

The obvious lever is the pushed actor's placement - she is the term in `push`, and `hull_scan` takes her
position as its first argument. Measured, she moves the depth **0.015 u per u** over a ±3 u grid
(−0.157 … −0.217 at thrust 13), and there is a mechanism: **she is PLOWED as the roll sweeps past**, so
her overlap on the CUT frame is set by the roll's own geometry rather than by where she started. Closing
0.19 u would take ~12 u of placement - 4+ frames of herding at the measured lateral authority, against a
2-frame prize, and outside the placeable thread's ~10 u lateral window entirely.

One more walk frame does not open it either (`plan_cost` would still be 22): the bigger hull reaches more
entries and every one of them shares the same `old`.

## How to use it, and how not to

- ``depth ≤ 0`` **is a proof.** The endpoint is on the near side of both planes; no razor, camera, lean,
  placement or candidate volume moves it. This is the shape [../history/](../history/) keeps asking for -
  a razor axis closed by a measurement instead of a compute budget.
- ``depth > 0`` **is only an admission.** Dust still has to exist on the locus (`hull_scan`) and a plan
  still has to land on it (`confirm_entry`).
- **It is not a density model.** Against the per-thrust live-station census it does not even correlate:
  cell 2549 at thrust 15 reads depth +0.513 with **0** live stations, cell 2553 at thrust 14 reads +0.127
  with **918**. Read it as a gate, never as a rate.
- **Screen before you buy.** One configuration is ~5 s and the whole window × thrust is ~3 min
  (`thrust_map`), against hours for one camera pass of a dust lottery.

## The rule

**Ask which clause of your acceptance test is failing before you buy more draws against it.** Six
sessions priced entry candidates by residual-band probability - the razor clause - while the endpoint at
those configurations could not reach the wall at all. A residual is the quantity that *varies*, so it is
the one a search naturally ranks on; the clause that is a hard gate had never been printed. When a
lottery comes up empty, spend the next hour making each clause a number, not on more tickets.

## See also

- [../mechanics/roll-cut-thrust-floor.md](../mechanics/roll-cut-thrust-floor.md) - why thrust 13 is the
  floor, and the frame cost the walk count hides.
- [clip-station-reachability.md](clip-station-reachability.md) - the sibling scope error one level out:
  the bands were measured outside the reachable set.
- [clip-exit-angle.md](clip-exit-angle.md) - the 0.65 u pocket this law is the ranked form of, and the
  exit-angle window it bounds.
- [../history/thrust-13-placement-lead.md](../history/thrust-13-placement-lead.md) - the superseded
  reading, that moving the pushed actor was the route to the second frame.
