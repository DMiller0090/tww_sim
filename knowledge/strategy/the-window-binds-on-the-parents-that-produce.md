# The screen's window binds, and only the parents that produce endpoints can say so

**Answers:** My screen reports its widest survivor sitting on the window edge - is the window
actually clipping anything, or is that just the tail? How wide should a per-aim fan be? I sampled two
parents to size a knob cheaply and got a clean answer - is it the right one? Why did widening a
screen's window change nothing on the parents I checked? How wide should a swept range be so it
proves its own edge? **My screen's frontier doubled and the plan did not move - what does that mean?**
**Status:** measured, session 136, over 5 parents of the deep-plow cycle-2 beam at
`pursuit_box`'s `max_delta` (±21.35 deg, the recorded regime). The window session 135 flagged
(`probe_half=0x600`, ±8.44 deg) **is** binding: **28.4%** of surviving aims live outside it, the best
screened `l0` goes **+117.58 -> +140.76**, and **306 of 1250** endpoints take their best `l0` from
outside. The survivor population's own edge is **~16.4 deg**. The same trap on `handoff.RUNWAYS` cost
2 rungs of the gap term; floor 190 -> 160, gated. Driver `_notes/s136_fan_width.py`.
RE-SEARCHED at `max_delta` (session 137, `_notes/s137_c3_maxdelta.py`, 2741 s): the bound is
**unchanged at 89.82** - the window bound the SCREEN and not the PLAN.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`'s
`fan_center`/`half_window`/`fan_edge`, `extend_cycle`'s `probe_half`/`probe_contact`/`probe_step`),
[`harness/tetrapush/handoff.py`](../../harness/tetrapush/handoff.py) (`RUNWAYS`, `entry_roots`).
Gated in [`tests/test_handoff.py`](../../tests/test_handoff.py).

## `fan_edge` on the edge is a hypothesis, not a measurement

[the-crossing-costs-the-arming-posture](the-crossing-costs-the-arming-posture.md) freed the push axis
and read `roll_probe`'s `fan_edge` at **8.34-8.44 deg of an 8.44 deg half-window on every parent**,
and inferred the window was clipping the population it screens. That inference is sound and it turns
out to be right - but `fan_edge` is a MAX, and a max touching the edge is equally consistent with a
thin tail that happens to reach it. The distinction costs frames in both directions: widening a
window that does not bind buys nothing at 2.5x the screen's price, and refusing to widen one that
does leaves the frontier unmeasured.

The measurement that settles it is the DISTRIBUTION at a width the population cannot reach, with the
endpoint pool held fixed so the width is the only variable:

| edge band (deg) | surviving aims | best `l0` | best rate | best \|arrive\| |
|---|---|---|---|---|
| 0.00 - 2.00 | 9621 | +51.58 | 12.833 | 0.23 |
| 2.00 - 4.00 | 5365 | +69.16 | 12.833 | 0.05 |
| 4.00 - 6.00 | 5711 | +66.86 | 12.827 | 0.11 |
| 6.00 - 8.44 | 4118 | +117.58 | 12.824 | 0.43 |
| **8.44 - 12.00** | **4730** | **+135.55** | 12.810 | 10.03 |
| **12.00 - 16.00** | **5017** | **+140.76** | 12.674 | 19.41 |
| 16.00 - 24.00 | 77 | +18.79 | 10.069 | 118.58 |

Two things read straight off it. The window binds - a quarter of the endpoints improve their `l0`
outside it, worth **+23.17 u** on the screened frontier, at a rate barely off the maximum. And the
population has its own edge at **~16.4 deg**: the 16-24 band holds 77 aims of 34639, at a third the
`l0` and 118 u of arrival error. So the width is a measured 16-ish, not the box's 21.35 and not the
shipped 8.44 - and `max_delta` is the setting that needs no new number, since it provably contains
the whole population.

## The trap: the cheap parents say the opposite

The first two parents measured say the window does NOT bind, cleanly and consistently:

| parent | junction endpoints | surviving aims | median edge | max edge | outside 8.44 |
|---|---|---|---|---|---|
| 0 | 1258 | 3071 | 2.92 | 10.74 | **42 (1.4%)** |
| 1 | 1260 | 3269 | 2.91 | 10.51 | **21 (0.6%)** |
| 2 | 8556 | 10296 | 4.13 | 16.41 | **3722 (36%)** |
| 3 | 8510 | 11715 | 6.82 | 16.19 | **4641 (40%)** |
| 4 | 8662 | 6288 | 3.97 | 14.51 | **1398 (22%)** |

On parents 0-1 the aims beyond 8.44 deg are also strictly DOMINATED - best `l0` -89.94 against
+20.60 inside, rate 10.995 against 12.819, arrival 113 u against 0.05 - so the two-parent read is not
merely underpowered, it is confidently backwards. Stopping there would have killed a real lever with
a measurement that looked decisive.

What separates them is the junction: parents 0-1 return **~1258** unique endpoints where parents 2-4
return **8510-8662**. A parent whose junction barely produces has few live states, its survivors
cluster near the bearing to Tetra, and its fan is genuinely narrow. It is also the parent that
contributes almost nothing to the beam. **The parents that produce the endpoints are the parents
whose survivors run wide**, and they are the expensive ones to probe - 1.48 s an endpoint against
0.59 - which is exactly why a cheap sample lands on them last.

The rule this generalises to: when sizing a knob by sampling parents, sample by **what a parent
CONTRIBUTES**, not by what it costs. Take the largest junctions first, or take enough that the
production distribution is represented. Two parents drawn in beam order is not a sample of the
population the stage actually screens - and per [[infeasible-needs-proof]], neither a positive nor a
negative verdict off it is a verdict.

## The same trap one layer down, on a different box

`handoff.RUNWAYS` - the rungs `entry_roots` solves the genuine entry curve on, and so the range every
`gap` in the chain-back is measured against - floored at **190** on an s124 scan reported empty below
it. Solved directly against real herd endpoints over rungs 60..320 the curve reaches **170**, so the
box was cutting two usable rungs off the cheapest term in the bound (0.15 frames at thrust 14, 0.29
at thrust 11).

The instructive part is what happened next. The floor was re-set from ONE beam's eight endpoints,
which bottom out at rung 180 - and the very next search, on a fresh beam, returned three endpoints
solving at the new first rung. One beam is not a population for a box edge any more than two parents
are for a fan width. Re-banked over both beams at both solved terminals (32 records) the curve's own
floor is 170, and the shipped floor sits one rung under it at 160, so a future hit on the first rung
is the curve speaking and not the box. That is the difference between a range that is measured and
one that is merely wider than the last thing that failed.

The general form, which is [the s135 lesson](the-crossing-costs-the-arming-posture.md) stated
positively: **a swept range should hold one rung the population does not use.** Then the sweep proves
its own edge every time it runs, and no session has to remember to re-check it.

## And the re-search says it bound the screen, not the plan

The warning below was the right one to make, and the answer is a negative result worth as much as the
measurement that prompted it. Re-searched at `max_delta` with the runway floor at the shipped 160 and
every other knob held (session 137, 2741 s), against session 136's identical search at ±8.44 deg:

| | ±8.44 deg | ±21.35 deg (`max_delta`) |
|---|---|---|
| roll survivors | 426 | **504** |
| best screened `l0`, producing parent | +71.77 | **+146.32** |
| endpoints parking her onside | 102 | 99 |
| best-of-beam `l0` | +42.11 | **+55.40** |
| **best bound** | **89.82** | **89.82** |

**The frontier the screen ranks by doubled and the objective did not move a digit.** Six of the
beam's eight nodes come back byte-identical, including the winner at `l0` +15.48 / gap 81.89. The two
that changed are the high-crossing corner, and they genuinely improved - `l0` +42.11 -> +55.40, bound
103.00 -> **96.84**, six frames - but that corner started thirteen frames behind and is still seven
behind. The extra recall was spent entirely where the plan is not.

The reason is that the screen's rank and the stage's objective are different axes. `l0` is the
CYCLE-2 requirement's axis - the bar in
[the-crossing-and-the-runway-are-one-resource](the-crossing-and-the-runway-are-one-resource.md) - while
cycle 3 is priced as `frames + gap/walk cap + cut_step`. The winner is a LOW-crossing endpoint that
wins on a short gap, and the same exchange rate that governs cycle 2 governs cycle 3's own beam:
buying crossing costs gap. So a knob that improves the frontier in `l0` can improve it a long way
without touching the bound.

Two things this pins for the next lever. The window and the runway floor are both now **cleared** and
neither can be blamed again: the fan's widest survivor reads 16.41-19.49 deg inside a 21.35 deg box,
so the box holds a rung the population does not use. And the junction's death counters come back
**byte-identical on the five that matter** - `unarmed` **429724**, `in_cone` **314542**, `outbox`
6576, `wall` 26304, `ENDPOINT` 73070 - with only the fan-dependent ones moving (`aim_followed`
341777 -> 885403, `unrollable` 874 -> 90).

That byte-identity was read here as arming refusing equally hard under both screens. It is not
evidence of that: `probe_half` is a ROLL-stage argument and `extend_cycle` never passes it into
`junction_beam`, so the junction answers twice the same **by construction**, and session 138's census
shows `unarmed` admits 73070 endpoints into a pool that takes 250 - see
[the-biggest-death-counter-was-the-alphabet](the-biggest-death-counter-was-the-alphabet.md), which
also prices the bar and names the pool as the cut that is actually binding.

## What it does not say

This measures the SCREEN's recall, not the plan. A wider window changes which endpoints the roll
stage gets to choose from; whether that reaches the bound is a re-search, not an inference - the same
warning [the-fan-is-not-a-bound](the-fan-is-not-a-bound.md) makes about every optimistic cut, and
above is the re-search that settled it here. The `l0` numbers are `roll_probe`'s per-aim delivery, and
the endgame's bar is a property of what cycle 2 hands over, not of the best aim in a screen.

The cost is real and linear in the width: 0.59-1.48 s an endpoint at 21.35 deg against ~0.5 at 8.44,
so the whole cycle-3 stage runs about **2.5x** longer. That is the price of the recall, and
`probe_half` exists precisely because [session 72 measured](clip-search-budget.md) that buying it
with a decimated `step` instead does not work: per-endpoint survival is one alphabet member wide, so
any `[::step]` finds ~1/step of the live endpoints however it is staged. Width at full resolution is
the axis; the only question is how much of it, and now that is measured.
