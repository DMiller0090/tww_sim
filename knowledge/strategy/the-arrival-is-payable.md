# The arrival was never fixed: the atom has a tail, and it costs exactly what it buys

**Answers:** My candidate's landing is right and its ARRIVAL is in the wrong place -- is that a
property of the endpoint, or of where I stopped measuring? What ends the escape atom, and what happens
if I keep holding the exit stick? Why does an arrival that stands 20 u from a station reach nothing?
Why does adding tail frames never improve my frame bound -- and why is the axis still worth having?
**Status:** MEASURED (session 110; the exit arc finally swept on a real beam in session 118) on the
flooded-Hyrule Tetra corner -- 46877 firing variant/tail records over the session-107 re-chain's 24 firing survivors; the tail's laws gated bit-exact in
[`tests/test_away_walk.py`](../../tests/test_away_walk.py), the pricing in
[`tests/test_cloud_land.py`](../../tests/test_cloud_land.py). Driver
`_notes/s110_joint_census.py`, dump `_generated/s106/s110_joint_census.json`.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`'s
``exit_run``, `tail_variant`), [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`arrival_frames`, `_joint_row`, `atom_cloud`'s ``exit_runs``).

## The measurement stopped at the handoff, so every arrival ever enumerated was the same shape

`escape_atom` broke the frame its result first recedes at the cap AND separates. That is the right
place to stop asking about the LANDING -- past separation Tetra takes no more push -- and it silently
fixed the other half of [delivery-is-two-predicates](delivery-is-two-predicates.md): every variant in
every enumeration ended Link beside her, deep, pointed down-herd, and often still flying backwards on
the untarget flip. Session 109 read the resulting front -- *miss < 1 u only at d_station ~127* -- as a
property of the population. It was a property of where the loop stopped.

Hold the exit stick past the handoff and the frames are ordinary: Tetra is separated, so they move the
ARRIVAL and nothing else. Two laws make that exact rather than approximate, and both are gated:

- **While the separation holds, her coordinate is bit-identical** -- 0 ULP, not "close" -- so a tail
  costs the landing nothing.
- **When it stops holding, the variant is refused.** A tail long enough to walk Link back into Co
  range breaks ``freeze_f`` and `away_walk.fires` drops it; a tail long enough to cross the 230 u
  follow bar ends the rollout. The tail is bounded by physics that were already modelled.

## What a tail is actually for: an arrival that is not at the cap reaches nothing

`entry_fan.iter_fan2` keeps an entry junction ONLY at ``speedF == WALK_CAP``, so an arrival caught
mid-backslide fans an **empty** walk cloud -- it reaches no station at any distance, however close it
stands. That is session 109's first failure shape, and it is not a rare one: the untarget flip is
still flying at -23 to -25 u/frame when the handoff fires. On the banked `shallow` arrival the handoff
reads ``speedF`` **-23.217** and **two tail frames** settle it at 17.0 exactly.

So ``settled`` is a hard clause on any claim that a candidate is deliverable, not a tie-break -- and
it is the first thing to read before believing a distance.

## The price is the walk cap, which is exactly what a tail frame delivers

The station gap is payable at ~17 u/frame ([delivery-is-two-predicates](delivery-is-two-predicates.md)),
and a tail frame delivers ~17 u/frame. So `cloud_land.arrival_frames` charging the gap at the cap and
the tail paying it are the same number, and the consequence is worth stating as a law:

> **The joint frame bound is TAIL-INVARIANT.** Measured at every firing endpoint of the re-chain
> population: the best bound at tail 0 and the best bound over all tails 0-6 agree to the digit
> (node 4, 93.95; node 7, 102.96; node 25, 106.60; 24 of 24).

That is the sign the term is priced HONESTLY -- an arrival term a tail could arbitrage would be a term
measuring the wrong thing. It also says what the axis is for, and it is not frames: the tail buys
**deliverability** (a settled arrival, a real hull over the stations) and it makes a bound quotable,
because the frames it names are frames the plan actually spends.

## What it bought: the front is an exchange, not a wall

The same population, re-priced with the tail axis and with the row chosen jointly (`_joint_row` --
which moves the choice: a row 6 u from the landing whose stations sit 130 u behind Link loses to one
20 u away that the arrival already covers):

| arrival owes | station gap | landing miss | settled | total |
|---|---|---|---|---|
| **0.00 f** | 30.5 u | **1.881 u** | yes | 104 |
| 1.57 f | 60.7 u | 0.299 u | yes | 118 |
| 8.45 f | 177.7 u | 0.167 u | no | 104 |

Session 109's front had nothing within 126 u of paying both. This one has a settled, fully-paid
arrival **0.881 u** outside the placement band. The exchange is soft, and what it now costs is frames
on the herd -- which is where [herd-price-of-a-placement](herd-price-of-a-placement.md) already says
the search has to go.

## The tail needs a bearing to run along, and the grid only ever held two

A tail runs at the cap along the exit-hold bearing, so that bearing decides where the arrival lands --
and the stations are a few points at a specific lateral offset, not a halo. The atom's grid carried
exactly two (the live entry bearing and the herd up-bearing), which is a direction and not a steering
axis. `cloud_land.exit_arc` sweeps it, and it moves BOTH halves, since the exit stick is already held
while the conversion frames are still plowing her.

Swept 18 wide at the population's best endpoint, that alone turned its best fully-paid landing from
1.881 u to **0.8008 u** and produced the first records that pay both predicates at once. It is not
free (each bearing is its own rollout, unlike the tail), so the pattern is the usual one: the standing
pair sizes the search, the arc refines where it pointed.

**And every enumeration for the next seven sessions then ran the pair anyway.** Session 118 turned the
arc on the swept session-111 beam and it is worth ~3 frames of the arrival bill there - the pair's
chosen bearing sat 58 deg off its own station while the pair's OTHER member sat 9 deg off it:
[the-exit-bearing-buys-the-arrival](the-exit-bearing-buys-the-arrival.md).

## What it is worth, against the razor rather than against a bound

Hull-scanned at their own arrivals and landings, **6 of 8 of those candidates read LEVERAGE** -- 15-45
cell/thrust combos, up to 1760 grid hits -- where every session-109 scan read `n_leverage == 0`.
Leverage is monotone in the tail (0 combos at tail 3, 18-25 at 4, 45 at 5), and the razor residual
falls from **3.3e-01 to 3.1e-03**. The tail and the arc measurably move the arrival.

**Those numbers are all thrust 13, and thrust 13 cannot clip here.** `hull_scan` is called over
`entry_search.THRUSTS` = (13, 14, 15) and these statistics pooled the three. Split by thrust, all 173
leverage-carrying combos sit at **13** -- the thrust
[this corner refuses](../history/thrust-13-refused-by-geometry.md) -- and the same landings read
**zero** leverage at 14 and 15, where a control at the console arrival reads 45 combos at every thrust
and dust at 14-15. So the tail and the arc are real and the candidates are not near-misses:
[arrival-half-was-not-solved](../history/arrival-half-was-not-solved.md). Rank on the deliverable
thrusts only.

One caveat the numbers force, and it is the optimism above made concrete: ``arr_frames == 0`` is a
RADIUS and the hull is a FAN. Two tail-3 candidates standing **23.5-24.0 u** from their stations read
zero leverage while tail-4/5 candidates at **19-33 u** read plenty. Direction, not distance -- so the
term ranks and `hull_scan` claims.

## The transferable rule

**A loop's break condition is a modelling assumption about everything downstream of it.** This one was
correct for the half of the problem it was written for (the landing) and quietly answered the other
half (the arrival) with whatever the last frame happened to hold. Before reading a front as a property
of the population, ask which of its axes the measurement was even allowed to vary.
