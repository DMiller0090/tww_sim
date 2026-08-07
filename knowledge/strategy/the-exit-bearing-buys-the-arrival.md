# The exit bearing buys the arrival: an enumeration's default grid is a claim about the axis it never sweeps

**Answers:** Every candidate on my beam owes the same arrival bill - is that the geometry or is it my
station list? How do I tell an arrival that is too FAR from one that is pointed the wrong WAY? Why
does adding tail frames make my arrival worse? My knob grid holds two values of an axis and ranks on
the other half of the problem - what does that cost?
**Status:** MEASURED (session 118) on the flooded-Hyrule Tetra corner, over the 14 in-band camera
states the session-117 sweep produced from the session-111 cycle-3 beam. Driver
`_notes/s118_arrival_scan.py` (phases ``control`` / ``scan`` / ``trace`` / ``arc``), dumps
`_generated/s106/s118_{arrival_scan,arc,arc_floor}.json`.
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`exit_arc`,
`atom_cloud`'s ``exit_bearings``/``exit_runs``, `arrival_frames`, `station_gap`),
[`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`'s
``exit_bearing``/``exit_run``), [`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py)
(`hull_scan`). Gated in [`tests/test_cloud_land.py`](../../tests/test_cloud_land.py).

---

[the-screen-is-not-the-rank](the-screen-is-not-the-rank.md) solved the LANDING fourteen ways and
every one came back owing **7.38-8.37 frames of arrival** - a 163-168 u station gap, the same across 3
rolls and 2 rows. That uniformity read as geometry: both halves are set by where the herd ends, so
nothing downstream can move it.

Half of that is right. The bill is real and the herd does set most of it. But ~3 frames of it were
being spent by the atom's own **exit bearing**, an axis `cloud_land.exit_arc` has swept since session
110 and which no enumeration on this beam had ever turned on.

## First: the bill is real, and it is not the station list

`arrival_frames` prices the gap to the **hunted** stations, which were gridded out of the CONSOLE's
own walk cloud - so quoting it for a plan that arrives elsewhere could be
[the plan_cost gotcha](plan-cost-walk-budget.md) one level up. It is not. Hull-scanned at their own
arrivals and their own landings over 45 aim cells x 3 thrusts:

| the 14 swept in-band states, 19 distinct arrivals | |
|---|---|
| positive control (hunted tetra, console hulls) | **3 of 3 rows LIT** (live walkable dust) |
| arrivals reading ANY leverage | **0 of 19** |
| of those, arrivals that fan an EMPTY walk cloud | **9** - not settled, so they reach nothing at any distance |
| the other 10 | settled, **133 444-134 381** walk endpoints against the console's 139 213 |

So it is not the proxy and it is not the [`iter_fan2` cap](the-arrival-is-payable.md) either, for the
family that matters: those ten arrivals fan a console-sized cloud and there is still no leverage
anywhere in it. **``n_leverage == 0`` with a full cloud is a PLACE verdict** - the hull is a fan along
Link's facing and it is in the wrong part of the room.

It also corrects a quoted figure. The sweep's cheapest in-band landing (total 98.00, delivered 105.90)
is one of the nine **unsettled** ones: it was never deliverable. The honest session-117 delivered best
is **106.62** (total 99.00 + 7.62), and `settled` has to be read beside `in_band` every time.

## What the gap is made of: the herd owes half, the atom spends the other half

Measured at the roll TERMINAL (before the atom) and again after it:

| | terminal gap | owes | post-atom gap | owes |
|---|---|---|---|---|
| node 11 | 67.6 u | 1.97 f | 159.5 u | 7.38 f |
| node 4 | 86.4-86.9 u | 3.08-3.11 f | 168.3-176.3 u | 7.90-8.37 f |
| node 3 | 105.9-106.7 u | 4.23-4.28 f | 163.5-164.2 u | 7.62-7.66 f |

The atom roughly DOUBLES the gap - it spends **3.3-5.4 frames of arrival** on top of what the roll
left owing. Over all 551 priced camera states the terminal gap runs **26.6-125.9 u**, and per roll it
is what the bill is: Spearman(terminal gap, arrival bill) = **+0.858** across the 22 rolls that price
a variant. The landing is close to independent of it (**+0.189**), so the two halves are not one
quantity with two names.

## Why the atom spends it: the tail runs the wrong way

Traced at the cheapest settled in-band state out to the 230 u follow bar (`trace`), the tail is not a
payment at all:

- ``d_station`` is **minimised at tail 0 (146.4 u)** and RISES to 227.2 u by tail 20.
- The variant holds the **live entry bearing, 85.8 deg** - while the bearing from its own handoff to
  its own station is **27.7 deg**.
- The other member of the same standing pair, the herd up-bearing, is **18.5 deg** - nine degrees off.

The grid held a nearly-right answer and the rank never chose it, because the rank prices the LANDING
and the exit stick is held while the conversion frames are still plowing her: the bearing that lands
her is not the bearing that arrives.

## Turning the axis: the same 14 states, the same tails, 26 bearings

`exit_arc` at step 0x800 over +-0x3000, tails 0-12, with the standing PAIR re-priced inside the same
call as its own control (69k-101k variants a state, ~9 min at 7 processes):

| at the 14 in-band states | standing pair | the arc |
|---|---|---|
| smallest in-band station gap | 31.3 - 176.3 u | **9.9 - 162.1 u** |
| best DELIVERED (``total + arr_frames``, settled) | 106.45 | **103.45** |
| states holding a ``joint`` record | 1 (total 111.0) | **10 (total 104.0)** |

Best delivered: node 3 ``off`` -3968, **total 103.0 + 0.45 owed = 103.45**, miss 0.492 u, tail 10,
row 30. Best `joint` - nothing owed on either half: node 3 ``off`` -3264, **total 104.0**, miss
0.403 u, tail 11, gap 25.3 u. This beam had produced **no** `joint` record before.

Both lanes ran the widened tail, so the 3 frames are the ARC's and not the tail's. And the frames it
saves are not a discount on the walk cap - the arc buys a bearing along which the tail's ~17 u/frame
actually points at the station, where the pair's pointed 58 deg off it.

## What it does not buy: the floor rolls still cannot land her

The two rolls whose arrival is free at the terminal (node 0 at 26.6 u, node 1 at 39.5 u) hold the beam
floor (93.95 / 93.87), so an in-band landing at either would deliver ~94. Swept the same way at their
4 + 3 cheapest camera states (30k-59k firing variants each):

- **node 0: zero in-band landings**, arc or pair, at every state.
- **node 1: 3 in-band at 2 states, arc only** - and 134.9 u from a station, delivering **111.93**.

So the arc does not cross the exchange. The banked **101 stands**, and the remaining 2.45 frames are
not in the atom.

## The rule

**An enumeration's default grid is a modelling assumption about every axis it does not sweep**, and
the assumption is invisible because the grid still returns an answer. This one held two values of the
exit bearing for eight sessions; both were reasonable directions, neither was a steering axis, and the
rank could not have noticed because it scores the other half of the problem. Before believing a
quantity is structural, list the knobs the measurement varied and ask which of them the number is
actually a minimum over.

The companion is [the-arrival-is-payable](the-arrival-is-payable.md)'s rule about break conditions:
same failure, one axis over. A loop's break condition answers everything downstream of it with
whatever the last frame held; a grid's default answers everything the rank cannot see with whatever
the first author wrote down.

## Traps

- **`in_band` without `settled` is not a candidate.** An arrival off the walk cap fans an EMPTY entry
  cloud (`entry_fan.iter_fan2` keeps junctions only at the cap), so it reaches nothing at any
  distance - and it will still print the cheapest total on the beam. Nine of nineteen scanned
  arrivals were in this state, including the one whose 98.00 got quoted.
- **A longer tail can move the arrival FURTHER from the station.** The tail runs at the cap along a
  held bearing and Link's heading CHASES it, so the path is a curve; `EXIT_RUNS`' longest member is
  not its best one. Gated.
- **Do not hold a candidate's row fixed while its tail moves the landing.** Before ``freeze_f`` Tetra
  is still taking push, so a shorter tail lands somewhere else and inherits a `plan_cost` belonging to
  a row it does not hit. The first version of the trace did exactly this and printed a delivered 99.61
  that was not a candidate at all.
- **``n_leverage == 0`` is a direction verdict, not a distance one**, and it means nothing without the
  control: run the call that BUILT a row's price at the console arrival first, every time
  (`[[search-space-contains-human]]`).

## See also

- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - the two halves, and the arrival
  constant this page takes 3 frames out of.
- [the-arrival-is-payable.md](the-arrival-is-payable.md) - the tail and the arc, built in session 110;
  its "the grid only ever held two" section is what this page finally measured.
- [the-screen-is-not-the-rank.md](the-screen-is-not-the-rank.md) - the sweep that produced the 14
  states, and the corrected 105.90.
- [clip-station-reachability.md](clip-station-reachability.md) - what `hull_scan`'s three ways of
  reading zero mean.
