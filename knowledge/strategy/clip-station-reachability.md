# The band was measured outside the set the candidates come from

**Answers:** Six passes in, my razor search is empty and my estimate says it should not be - what is
left to be wrong? Is the set my BANDS were measured in the set my CANDIDATES come from? Why does my
search's closest approach keep improving while nothing ever clips? I narrowed my search's scope on a
CLOCK argument - what could that have cost?
**Status:** validated offline (session 99) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_entry_reach_stations.py`](../../tests/test_entry_reach_stations.py) (13 + 1 slow).
**Source:** [`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py)
(`entry_hull`, `hull_field`, `hull_seeds`, `hull_scan`, `LEVERAGE_MIN`) and
[`harness/tetrapush/entry_search.py`](../../harness/tetrapush/entry_search.py) (`locus_scan`'s
``inside`` filter and ``drops``).

[clip-band-transfer.md](clip-band-transfer.md) found that each draw was priced by a band measured
14.5-26.4 u away and that 0 of 100 draws had dust at their own station. This page is the reason - a
scope error, not a probability - and the answer to the question that finding left open, which turned out
not to be the one anybody expected.

## Two sets that were never compared

| | measured in | |
|---|---|---|
| the **candidates** | the fan's own walk cloud, hull-measured ([clip-exit-angle.md](clip-exit-angle.md#what-a-cell-costs-in-frames)) | 450 draws |
| the **bands they were priced against** | `curve_scan` over `reach_radius`'s 94 u square box | 20 stations |

Against the 4-frame reachable hull:

- **450 of 450 draws are inside it** - and every one within **2.63 u** of its boundary;
- **20 of 20 bands are outside it**, by **10.196 to 19.400 u** (median 12.1).

So session 98's 14.5-26.4 u transfer distance and this hull crossing are one fact seen from two sides.
No draw in that population could have clipped at any width, and the emptiness was never Poisson luck,
never a resolution limit, and never a missing camera.

**The camera cannot close that gap, which is the one way this could have been wrong** - the hull is
measured at the frozen camera, and the camera is what sessions 95-98 varied. Re-measured as a union over
five cameras spanning the whole channel including both extremes: area **1686.7 → 1687.0 u²** (+0.02%),
bbox unchanged, and **0 of 20** stations inside it at a 1 u margin. The camera re-indexes which points
inside the cloud a plan lands on; the cloud's extent is Link's heading, the speed cap and the turn rate
(`entry_camera.hull_shift`).

**Why the "record closest approach" kept improving and never converted.** `window_gap` compares a
residual NUMBER to an interval and drops the STATION the interval belongs to, so the search drove
candidates as close as the reachable set allows to a target outside it and then held them there. Session
96's `8.829e-06` is that boundary point; session 98's `0.0` is the same point one buy later. Two entries
21 u apart can share a residual value and only one of them is standing where the genuine set is.

It also vindicates this corner's own frame table: [clip-exit-angle.md](clip-exit-angle.md#what-a-cell-costs-in-frames)
had cell 2553 reaching only **1.1e-02** at ≤4 frames, and the 400x "improvement" booked after it was
residual values nearing an interval whose station no plan can stand in.

## Asking it over the reachable set instead

`hull_scan` is `curve_scan` with the box replaced by the measured hull, plus a containment test on each
station it marches to (`locus_scan(inside=)`). Two things it must not inherit:

- **The seeds cannot be residual sign changes.** Only about **7% of the hull has leverage** - at the
  rest the plowed Tetra is out of Co range on the cut frame and the residual does not respond to the
  entry at all. That is a literal plateau, not a small slope: sampled at 5e-4 u across 0.02 u, a
  leverage point gives **41 distinct residuals** moving smoothly at ~1.3 per u, and a plateau point gives
  **one** value with every delta exactly `0.0`. So a sign change between two plateaus is a **jump**, and
  Newton returns `no leverage` from it. Seed off the leverage set (`hull_field`).
- **The grid is not a dust detector.** A band is ~3e-5 of residual against a local gradient of order 1
  per unit, so the genuine set is a ribbon **~1e-4 u wide or narrower** and a 1.5 u grid steps straight
  over it. `hull_field` returns the engine's genuine flag because a stray True would be information,
  never because a False count is evidence.

And **`stations 0` is three findings, not one**, so `locus_scan` now returns `drops`
(`no_leverage` / `no_zero` / `outside`). A locus that never comes inside the hull is not a negative about
the cell; neither is one with no leverage anywhere in it. Only "in-hull stations sampled, none live" is.

## What it found: the axis is alive at the thrust that was dropped for clock

The control and the counterfactual first, because a negative without them is not a claim
([`[[search-space-contains-human]]`](clip-entry-search.md)):

| scan | live walkable stations | reads as |
|---|---|---|
| cell 2552, 4 frames, thrust 15 - the **console-delivered** clip | **518** over 60 of 60 leans, 0.044 u from the delivered entry | the scan works |
| cell **2553**, 4 frames, **thrust 15** | **0** over **1040 of 1040** leans, 12823 in-hull stations | barren, densely sampled |
| cell 2553, **5** frames, thrust 15 | 243 over 44 of 60 leans, 0.24 u from session 94's band station | the frame would buy it |
| cell **2553**, 4 frames, **thrust 14** | **918** over **561 of 1040** leans, 12914 in-hull stations (**7.11%** live) | **the target was there all along** |

The thrust-14 population is not marginal: 561 live leans carry **65.8% of the fan's candidate mass**.

**And it is the only one.** Every cell right of the delivered 2552 was then swept at **all three
thrusts** - the right side had only ever been sampled at thrust 15, now known to be the blind one, and
the prize scales hard with the cell (2553 is +9 BAM, 2561 +149, 2581 +455). Cells 2554-2556 sample
157-612 in-hull stations and read **0 live at every thrust**; **2557 and right have no in-hull stations at
all** (`drops` says `no leverage on the locus inside the hull` - session 93's second-lobe result,
confirmed across three thrusts instead of one). So the bigger prizes are not merely expensive, they have
no locus inside the reachable set, and cell 2553 at thrust 14 is the whole remaining axis.

**Thrust 14 is not a frame cost.** The thrust chooses which roll frame the B edge dispatches the cut on
(cut_step 15/16/17); `entry_fan.plan_frames` counts walk holds only, so thrust 14 is objective-legal at
the frame floor - and firing one roll frame earlier is if anything frame-positive. Session 96 dropped it
on a clock argument: *"3.8% of the draws / 4.5% of E[hits] for 24% of the clock"*. Every pass from there
on ran `thrusts=(15,)`, and at cell 2553 thrust 15 is the barren one.

**Why it looked barren when it was not.** Every thrust-14 band session 94 measured came out **width
0.0**, which reads as unusable - but that is not "no dust". It is genuine points sitting on a residual
**plateau**: many genuine samples all sharing one residual to the bit, where `grad ≈ 0`. `lottery`
prices a zero-width band at probability zero, so the configuration was scored worthless by the one
quantity that cannot see it.

## And that plateau is also what the axis costs

Only **58 of the 918** live stations carry a residual-measurable band (median width **3.26e-05**, max
3.49e-05). At the other 93.7% the residual is flat, so "is my residual inside the band" is either always
or never true there and **a resid-ranked search cannot sample into it** - reaching those needs positional
precision of order 1e-4 u, which a walk-endpoint lattice does not have and no tool here targets.

So the two factors, both now measured at the right place:

| | |
|---|---|
| P(a kept draw's station is live) | **0.0711** |
| P(that live station has a steerable band) | **58/918 = 0.063** |
| P(residual inside the band) at the median width | **3.26e-03** |

which puts a kept thrust-14 draw at **~1.5e-05** and E[hits] 1 at **~68 000 draws** - on the order of
**1000 hours** at the 63 draws/hour this corner measured, for a cell worth ~2-4% of a frame. Read that as
a floor rather than an estimate: the rate was measured on thrust-15 passes, and thrust 14 was dropped
precisely because it costs more clock per draw. The remaining 93.7% is genuine dust that would need a
*positional* search rather than a cheaper lottery.

That is the honest close: **not impossibility, a measured price on a real target** - and it is the first
number on this axis computed from both factors at the station the candidate actually stands on.

## The rule

**A search's scope must be the set it can deliver from, and every quantity it ranks on must be measured
inside that set.** The box was a conservative superset for hunting a level curve, which is what it is
good for; the error was letting a measurement taken in it price candidates drawn from something else.

Three corollaries this corner paid six sessions for:

- **an improving best-approach is not evidence of convergence unless the target is reachable** - a
  ranked search will always walk to the edge nearest an unreachable target and stop there;
- **a negative needs a control AND a counterfactual.** The control catches a broken scan; the
  counterfactual turns "empty" into *why*, which is the difference between closing an axis and
  abandoning it;
- **scope narrowed on a clock argument owes a re-ask when the search comes up empty.** Dropping an axis
  because it is expensive per draw is a budget decision that silently becomes a claim about where the
  answer is. Thrust 14 cost 24% of the clock for 3.8% of the draws and it is where the reachable dust
  is; six sessions of buying never re-opened it, because "0 genuine" was always read as needing MORE of
  the same scope rather than a different one.

## See also

- [clip-band-transfer.md](clip-band-transfer.md) - the symptom this page is the cause of.
- [clip-exit-angle.md](clip-exit-angle.md#what-a-cell-costs-in-frames) - the frame budget, the hull, and
  the per-cell prize.
- [clip-band-per-lean.md](clip-band-per-lean.md) - why a zero-width band is not a wall; this page is the
  thrust axis of the same mistake.
- [razor-prices-every-term.md](razor-prices-every-term.md) - the general form: every term gets priced,
  including the set a term was measured in.
