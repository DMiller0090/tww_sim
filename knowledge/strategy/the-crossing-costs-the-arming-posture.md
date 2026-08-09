# The crossing and the arming posture are bought with the same push

**Answers:** I freed the constraint my search was dying on and it still returns nothing - did I free
the wrong one? What decides whether a post-roll endpoint can turn out of the talk cone in time? Why
do the endpoints that reach my target all fail the NEXT stage?
**Status:** measured, session 135. Freeing the herd-line direction from the plow regime
(`full_herd.in_pursuit_box`'s `axis`) takes cycle 3 off the band-keeping beam from **zero children**
to **170428 judged** - and every one of them still dies `in_cone`, because the binding quantity is
the EXIT'S SLIDE (`corr(l0, tangential fraction) = +0.960` over that beam). On the DEEP-PLOW beam
the same change is worth **6.9 frames**: bound **100.06 -> 93.17**, 8 of 8 endpoints onside. Gate
[`tests/test_free_axis.py`](../../tests/test_free_axis.py).
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`in_pursuit_box`, `_frontier_score`, `extend_cycle`'s `free_axis`),
[`harness/tetrapush/two_roll.py`](../../harness/tetrapush/two_roll.py) (`alive`, `junction_gates`),
[`harness/tetrapush/reposition.py`](../../harness/tetrapush/reposition.py) (`AXIS_PAIR`,
`pair_line`). Probes `_notes/s135_cone_walk.py`, `_notes/s135_why_no_arm.py`,
`_notes/s135_exit_slide.py`.

## The direction assertion was a cap, and freeing it is a re-expression

The plow regime is three predicates, and each mixes a claim about the PAIR with a claim about which
way it pushes - see
[the-axis-the-endgame-is-denominated-in](the-axis-the-endgame-is-denominated-in.md). Read about the
pair's own push axis instead of the herd line, `lead` is minus the separation and both the lateral
and the bearing terms are zero by construction, so the box collapses to the human's own measured
**26.8-127.8 u separation band**. Nothing is widened; the equality with the full three-clause form
about `reposition.pair_line` is gated, and the human still sits inside it on every recorded frame.

What it buys, measured on the band-keeping cycle-2 beam (`l0` -51.75, past the -80.4 bar):

| | children judged | how they die |
|---|---|---|
| herd axis (shipped) | **0** | `outbox` at generation 1 |
| pair axis (`free_axis`) | **170428** | `in_cone` - Link never leaves the +-90 deg talk cone |

The junction starts. It does not arm.

## What actually stops it: the exit is orbiting her

The arming gate is `|facing - bearing_to_tetra| > 90 deg`, and it has two terms. From these exits
Link's EBS backslide is almost entirely ACROSS the line to her, so the bearing runs away while he
turns:

| exit | slide/frame | radial | across | tangential | bearing turns | cone deficit closes |
|---|---|---|---|---|---|---|
| `l0` -51.75 (past the bar) | 19.63 u | +5.40 | 18.87 | **96%** | **15.3 deg/f** | stalls at ~69-78 |
| `l0` -63.47 (past the bar) | 23.02 u | +3.86 | 22.69 | **99%** | 19.0 deg/f | stalls |
| `l0` -152.14 (control) | 9.84 u | +9.81 | 0.73 | **7%** | 1.8 deg/f | 83 -> 48 -> 17 -> **0** |

Best-in-beam cone deficit per generation, band-keeping exit: **86.0, 70.6, 69.0, 69.4, 72.3, 76.3**
and then the beam is empty. The control: **48.2, 14.6, 0.0** and it holds 0 for nine more
generations. Separation over the same six frames: **64.6 -> 111.7 u** against the band's 127.8 u
ceiling, versus the control's 58.2 -> 64.0 -> 63.6 -> 57.2. Link runs out of contact before he can
turn, and he is turning against a bearing that moves 15 deg a frame.

## Why the two are the same resource

This is not a coincidence of the beam. `l0` is bought at **2.07x** by LATERAL push, and a lateral
push is one delivered ACROSS the line between the two bodies - which is exactly the momentum that
leaves the pair rotating afterwards. Over the banked cycle-2 beam the two are almost perfectly
coupled:

* past the bar (8 endpoints): tangential **80-99%**, bearing turning **10.4-19.0 deg/frame**
* short of it (8 endpoints): tangential **3-36%**, bearing turning **0.7-3.4 deg/frame**
* `corr(l0, tangential fraction)` = **+0.960**

Read it as the mechanism, not as a law: 16 endpoints of one beam are ~5 distinct states, and a
correlation over 5 points is not a feasibility verdict
([[infeasible-needs-proof]]). What generalises is the shape - the crossing and the next junction draw
on the same push, in opposite directions, which is the same trade
[the-crossing-and-the-runway-are-one-resource](the-crossing-and-the-runway-are-one-resource.md)
found one stage further out.

## The route it does pay on

The band-keeping route is where the clause was named and it is not where the frames were. Run the
same freed stage over the DEEP-PLOW cycle-2 beam - the one whose crossing s134 measured at bound
100.06 - and it returns **8 of 8 endpoints onside, all admitting an entry curve**, `l0`
**+10.41..+38.80**, best **bound 93.17 = 72 herd frames + 87.86 u of gap at the walk cap + 16 of
cut**. That is under the banked console **101**, under s126's sampled **97.35**, and under the
[s125 floor of 94](the-razor-is-on-the-pusher-not-the-pushed.md) - which it is allowed to beat
because that floor's herd term was 73, the all-out-push-to-a-COORD number, and s123/s125 replaced
that target with a half-plane that is nearer.

Read it as a bound: the gap is charged at cap speed with no turnaround and no guarantee the move
lands on the 1e-4 u razor, and the roll entry is a separate search. Two things say it is not the
frontier either - the per-aim screen's fan window is BINDING under the freed axis (`roll_probe`'s
`fan_edge` reports the furthest surviving aim at 8.34-8.44 deg of an 8.44 deg half-window on every
parent, so `probe_half` is clipping the population it screens), and the 16 is a thrust-14 cut.

The death counters say the same thing the band-keeping run did, on these parents too: `unarmed`
**429724**, `in_cone` **314542**, `outbox` **6576**. The box is no longer what refuses anywhere.

## What to do with it

The keep that follows is a PAIR-frame one and does not exist yet: rank a cycle-2 exit by the RADIAL
fraction of its slide (one dot product on a state the rollout already produced, no herd line in it),
and let `l0_keep` choose among what survives. `align_keep` / `square_keep` are the herd-frame
ancestors of that idea and they measure the wrong thing once the last two cycles stop herding.

The general lesson is about how a cap is diagnosed. Freeing the constraint the search DIES on is
worth doing - it is one measurement and it moved 0 children to 170428 - but a search that still
returns nothing afterwards has only moved its refusal, and the next question is which counter went
up. Here `outbox` -> `in_cone` named the real quantity in one run, where nine sessions of reading the
old counter named none.
