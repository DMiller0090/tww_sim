# A placement's price is frames, and the herd cannot pay them continuously

**Answers:** Session 104 found 211 placements at a two-frame walk and measured their herd saving as a
DISTANCE - what is that worth in frames? What does `plan_cost` count from, exactly? Can I just stop the
delivered plan early, or re-aim its escape, and have a shorter herd? Which placements is a DEPTH ranking
actually selecting for me?
**Status:** measured offline (session 105) on the flooded-Hyrule Tetra corner, on the delivered console
plan `fixtures/courtyard_plan_s73_console.json`. Gated in
[`tests/test_herd_price.py`](../../tests/test_herd_price.py).
**Source:** [`harness/tetrapush/objective.py`](../../harness/tetrapush/objective.py) (`PUSH_CEILING`,
`LATERAL_RATE`), [`harness/tetrapush/entry_fan.py`](../../harness/tetrapush/entry_fan.py) (`plan_cost`,
`base_core`), [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`probe`,
`escape_atom`, `fires`) and `_notes/s105_*.py`.

## The arrival is the whole log, not the frame she freezes on

`plan_cost` counts from the ARRIVAL, and the arrival is where `entry_fan.iter_fan2` starts its fan: it
replays the WHOLE delivered log and then holds `n0` more frames. The delivered plan is

| | frames |
|---|---|
| herd | 71 |
| escape atom | 7 |
| **log, and so the ARRIVAL** | **78** |
| of which Tetra is frozen from | 75 |

So the banked deliverable is **78 + 23 = 101** frames from state 2 to the cut, and a candidate is
`arrival + plan_cost`. Reading the arrival off `scored_frames` (75, where SHE stops) instead of
`n_last` understates every total by **3** - the atom's own post-freeze length, which Link needs whatever
she does, because a plan with no arrival has nowhere to walk from.

## A placement in Co contact at the arrival is not a placement

Every s104 station was qualified inside the 2-frame walk cloud measured from the console arrival, and
that cloud is a COUPLED fan - Link's own walk recoils off Tetra's Co cylinder
([mechanics/actor-push.md](../mechanics/actor-push.md)). So a placement she cannot statically occupy at
that arrival has no business being scored against that cloud. The test is her Co depth against Link's
exec centre, which LEADS his feet by **21.253 u** at the arrival (feet
(-1589.035522, -791.150330), centre (-1574.112183, -776.017456)):

| rung | live placements | in Co contact at the arrival |
|---|---|---|
| `plan_cost` 21 | 211 | **33** |
| `plan_cost` 20 | 56 | **11** |

The console placement itself reads depth 0.0000, and so do all 14 rows the s104 fixture pins, so this
screen costs the verified set nothing - it trims the wider population, and it trims it from the CHEAP
end, because the placements needing least herd are the ones nearest Link's approach.

Once through the screen the walk itself is safe without a second test: from the arrival Link walks
+X+Z, AWAY from both the corner and the herd, so a placement clear at the arrival is clear for the whole
two frames. Contact returns at the ROLL, which is where it belongs - that push is what steers the cut.

## Two prices, and the only place they agree is the one that matters

The delivered plan herds her **939.4737 u in 75 frames = 12.5263 u/f**, 96.4% of
`objective.PUSH_CEILING`. Two ways to spend that number, both estimates:

* **the rate price** - her state-2 distance over 12.5263. Assumes the herd is equally efficient toward
  any placement.
* **the trajectory price** - project the placement onto the delivered plan's own per-frame curve
  (`k_traj`) and charge the perpendicular miss at `objective.LATERAL_RATE` (2.92 u/f). Its along term is
  a MEASUREMENT of the delivered cadence rather than its mean, which matters because her per-frame step
  is 8-17 u depending on where in the roll cycle it lands.

| | best `plan_cost` 21 | best `plan_cost` 20 |
|---|---|---|
| rate price | 93.24 | **93.45** |
| trajectory price | **94.63** | 95.04 |

**They disagree about which rung wins.** They agree to 0.4 frames on placements within ~2.6 u of the
delivered curve and diverge by up to **14 frames** at 46 u off it, because that is exactly where the
lateral term does all the work. So the HEAD of the ranking is trustworthy and its tail is not, and
neither is a measurement: converting properly owes a `full_herd.chain_herd` retargeted at these rows.

Both agree the prize is real and about **6 frames** (101 -> ~95).

## The delivered herd cannot be truncated - the price is quantized

The obvious way to buy a shorter herd is to stop the delivered plan early, since its own trajectory
walks straight through this region (f68 (-1615.9, -810.8), f70 (-1620.2, -845.1), f72 (-1625.1, -874.0)).
It does not work, and the reason is structural rather than marginal. Truncating the herd at frame k and
running the ENTIRE escape-atom knob grid - 672 variants, flip bearing x `rotate_off` x
`turnaround_first` x `rotate_side` x exit bearing:

| k | 62-70 | 71 | 72 | 73 | 74 | 75-76 | 77-78 |
|---|---|---|---|---|---|---|---|
| variants that FIRE | **0** of 672 | 247 | 323 | 245 | 7 | **0** | 672 |

Nothing fires before frame 71, which is the delivered herd's own end. The escape needs the state the
last roll's exit leaves, so the herd's frame count is quantized by its cycle structure: "70.6 herd
frames" is not a plan this herd can express, and a shorter herd has to be a herd whose own last roll
ends earlier.

The control passes and is worth stating, because it is what makes the zeros mean anything
([`search-space-contains-human`](clip-station-reachability.md)): at k = 71 the enumeration contains the
delivered plan itself - **0.432 u from coord idx 274 at arrival 78**, which is the banked plan's own
landing to four decimals.

## Re-aiming the escape does not move her either

The other cheap door: keep the console-confirmed herd exactly as it is and re-aim only the escape. Of
k = 71's 247 firing variants, **62** arrive by frame 78 (so ≤ 99 total frames at `plan_cost` 21) - and
they produce **7 distinct landings**, all within ~5 u of the console placement. The nearest live
`plan_cost` 21 placement is **21.169 u** from that placement, and the atom has nothing like that
authority in ≤ 7 frames.

Tested properly - each landing's OWN 2-frame cloud re-measured from its OWN arrival, then
`entry_reach.hull_scan` - every one reads **0 leverage**, `|resid|min` 2.53e-01 against a razor band of
~1e-4. Not a dust question: from there she is out of Co range on the cut frame.

Best landing on a live placement over EVERY truncation and every variant: **6.95 u** (`plan_cost` 21, at
arrival 87, i.e. 108 frames) and **17.38 u** (`plan_cost` 20). Seven times the 1.0 u band at best, and
frame-negative where it is closest.

## Depth and frames select disjoint placements

The 14 rows s104 verified are the DEEPEST, and depth here is anti-correlated with frames:

| | rate price | trajectory price | depth |
|---|---|---|---|
| the 14 verified rows | 96.70 .. 101.66 | 103.46 .. 115.86 | +0.2075 .. +0.3399 |
| the frame-minimal head | 93.24 .. | 94.63 .. | unverified |

Under the trajectory price **not one verified row beats the banked 101**; under the rate price 6 of 14
do. They sit 23-48 u off the delivered curve - precisely where the two prices disagree - because the
deepest placements are further DOWN-herd and off-line, and depth is bought with contact
([model/required-cut-contact.md](../model/required-cut-contact.md)) while frames are bought with
proximity. **A ranking by depth is a ranking away from the objective**, so the verification effort has
to be re-pointed at the frame-minimal head before any of it is deliverable.

## The transferable rule

**A saving measured in the units of the thing you are optimising is a measurement; a saving measured in
any other unit is a hypothesis with a conversion attached.** Session 104 measured the herd saving in
UNITS and it was real; three of the four ways of spending it in FRAMES turn out to be unavailable
(truncation does not fire, re-aiming does not steer, and the verified rows are the expensive ones). The
conversion was the whole content, and it had to be done before another pass of verification, not after.
