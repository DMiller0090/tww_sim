# The razor is on the pusher, not the pushed: chaining a herd back to a terminal configuration

**Answers:** I have solved which (pusher, pushed) pair clips - how do I ask whether my HERD can deliver
one? My terminal solve pinned the pusher on a line and my herd never arrives there, is that solve still
usable? Which of my herd's endpoints admit a clip, and what is the ask - place the pushed actor, or
place the pusher? Why does a coordinate that reads exact turn a genuine cell into a dead one?
**Status:** MEASURED (session 125) on the flooded-Hyrule Tetra corner at the delivered facing 40835 /
thrust 14, against the two banked 63/64-node cycle-3 beams and the console-confirmed 71-frame herd.
15 of 127 banked endpoints park her on the genuine side; **all 15 admit a clip roll** (3-7 entries each,
74 in total). Frame floor 94 against the banked 101 - a FLOOR, priced at the walk cap, not a delivered
plan.
**Source:** [`harness/tetrapush/handoff.py`](../../harness/tetrapush/handoff.py) (`PairFrame`,
`tetra_lateral`, `side_crossings`, `solve_sides`, `side_band`, `entry_locus`, `node_gap`),
gate [`tests/test_handoff.py`](../../tests/test_handoff.py) (7); builds on
[the-corner-sets-the-depth-not-the-herd.md](the-corner-sets-the-depth-not-the-herd.md).

---

## The terminal solve pins the pusher, and a herd does not arrive there

A terminal solve naturally parametrises the pair the way a *planner* thinks: put the pusher at a chosen
spot and sweep where the pushed actor sits. That pins the pusher to the approach line through the corner
brace and leaves three coordinates -

    entry = brace - runway*m                     tetra = entry + along*m + lat*q

A herd does not choose the pusher's spot. It arrives wherever the last cycle leaves him, which is off
that line by tens of units. So chaining backwards needs the fourth coordinate restored:

    entry = brace - runway*m + side*q            tetra = entry + along*m + lat*q

and then the two lateral coordinates are not independent. **The herd parks the pushed actor and walks
away from the choice; only the pusher is still free.** At a fixed pushed actor,

    along = (tetra - brace)*m + runway            lat = (tetra - brace)*q - side

so sliding the pusher sideways by `side` moves the razor coordinate `lat` by exactly `-side`, and the
genuine set is a **curve of pusher entries**, one solved `side` per `runway`. That curve - not a cell,
not a tabulated coordinate - is what a herd has to hand over.

## Which means the razor moved onto the pusher, and it is sharper there

| axis | acceptance | residual gradient | what a scan must step |
|---|---|---|---|
| pushed actor's lateral (`lat`) | 2.2e-5 .. 1.5e-4 u | -4.0 .. -14.3 /u | 0.5 u brackets fine |
| **pusher's own lateral (`side`)** | 4.5e-5 .. 5.1e-4 u | ~3 - 7 /u near the solution | **0.005 u** |

The step is not a tuning choice. At a fixed pushed actor the pusher only still TOUCHES her at the cut
inside a corridor about **1 u wide** (measured -0.105 .. +0.895 at the reference cell); outside it the
residual saturates at its no-contact value. A half-unit bracketing step can straddle that corridor
whole, find nothing, and report a clipping configuration as infeasible.

## The one number the chain-back turns on: which side of the line she is parked on

Measure the pushed actor's own offset from the approach line (`tetra_lateral`, here `l0`):

| population | `l0` |
|---|---|
| the 288 tabulated genuine coords | **+2.50 .. +13.69** |
| the 51 solved terminal configurations | **+0.57 .. +51.00** |
| the 13 in unbroken contact | **+0.57 .. +4.89** |
| the console-confirmed 71-frame herd's endpoint | **-17.67** |
| two banked 63/64-node beams, terminals | -71.15 .. **+19.65** (median -23.6) |
| the same beams, one roll earlier | -243.8 .. -108.9 |

Every genuine configuration is on ONE side. A herd's last roll is what carries her across - from ~-135
to ~+9..+15 - and in the walk-away shape the escape push is what finished the crossing (-17.67 to the
+2.75 of the coord it landed on). So the first question to ask of any herd endpoint is not a distance,
it is a **sign**.

## And on the right side, the clip is always available

Of 127 banked endpoints, 15 park her at `l0` in the genuine range. **All 15 admit a clip roll** - 3 to 7
genuine pusher entries each, 74 in total, at `runway` 195-320. Nothing about the pushed actor's placement
is the blocker. What is left is entirely the pusher's position: he ends the herd's last roll **73-171 u**
from the nearest genuine entry (too deep by 58-190 u of `runway`, too far across by 30-57 u of `side`).

The consequence for planning: **stop scoring a herd by where it puts the pushed actor and score it by
whether it leaves the pusher on the curve.** The pushed actor's placement is free inside a wide band; the
pusher's is a 1e-4 u razor.

## Two traps that cost this session real time

- **Never round-trip a razor-scale position through the frame.** `m` and `q` come from the console's f32
  sin/cos tables, so the basis is orthonormal only to ~1e-7. Projecting a genuine world pair into
  (runway, side, along, lat) and rebuilding it moves the residual from 8.3e-5 to 1.05e-3 - **twelve band
  widths, genuine to dead** - purely in the trip. Hold the positions; use the coordinates only to
  report. Gated.
- **Centre a lateral scan on the pushed actor, never on the brace line.** A brace-centred +-60 u span at a
  real herd's parked Tetra has a maximum overlap of **-91.8 u** - not one sample in contact anywhere -
  and reads as flatly infeasible. The corridor sits at `side ~ l0`. A search failure is never a
  feasibility proof: the span was the bug, not the physics. Gated.

## What it prices

Floor for the zero-walk-away shape off the banked beams: **73 herd frames + 5 to close the gap at the
walk cap + 16 of clip roll = 94**, against the banked **101**. That 5 is a floor and not a plan - it
charges the gap at cap speed with no turnaround and no guarantee the move lands ON the 1e-4 u razor.

Those 73-171 u are **not** a ranking deficit the last cycle can be re-cut to recover: crossing the
approach line and keeping the pusher's runway are the same resource, measured over 20592 rolls -
[the-crossing-and-the-runway-are-one-resource.md](the-crossing-and-the-runway-are-one-resource.md)
carries the current statement of what a herd must hand over and which cycle owes it (the expectation
this page originally ended on is in
[history/the-last-cycle-could-be-cut-onto-the-curve.md](../history/the-last-cycle-could-be-cut-onto-the-curve.md)).
