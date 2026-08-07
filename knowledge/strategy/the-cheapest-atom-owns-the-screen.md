# The cheapest atom owns the screen: a min over a frame-charged table is blind to any axis that pays late

**Answers:** I plumbed a measured axis into my per-aim screen and the predicted bound moved by exactly
zero at every endpoint - is the plumbing broken? Why does my 75 627-member table return the same answer
as a 3-member one? I corrected a term that was off by 2x, the ranks all moved, and the cut came out
byte-identical - was the fix pointless? Which of my two measures (the cheap screen, the exact keep) can
see a knob that only pays after frame 6?
**Status:** MEASURED (session 119) on the flooded-Hyrule Tetra corner, at all 64 nodes of the
session-111 cycle-3 beam, three lanes in one call. Driver `_notes/s119_screen_delta.py`, dump
`_generated/s106/s119_screen_delta.json`; the re-cut it explains is `_notes/s119_recut_c3.py`.
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`predict_bound`, `cloud_landing`'s ``best``/``in_band``/``joint``, `residual_fan`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`'s
``cloud_bound``, `extend_cycle`'s `_mixed_beam` shares). Gated in
[`tests/test_cloud_land.py`](../../tests/test_cloud_land.py).

---

[the-exit-bearing-buys-the-arrival](the-exit-bearing-buys-the-arrival.md) found 3 frames in the exit
arc and asked for it to be plumbed into the cut rather than swept after it.
[the-fan-outlived-its-columns](the-fan-outlived-its-columns.md) did the plumbing and fixed a second,
larger fault on the way. Both halves then landed on the same wall, and the wall is worth more than
either fix: **the screen cannot see the arc, and no amount of plumbing will let it.**

## The measurement

Three lanes at the same 64 endpoints, each priced by `predict_bound` exactly as the per-aim screen
prices them. ``zero`` reproduces the session-115-to-118 behaviour (the throw defaulted to 0), it does
not remember it.

| | bound delta | endpoints whose RANK moves | top-6 keep |
|---|---|---|---|
| zero -> pair (the throw fix) | **-0.480 .. +2.814**, mean +1.449 | **53 of 64** | unchanged |
| pair -> arc (the arc, 7 668 -> 75 627 members) | **+0.000 at 64 of 64** | **0 of 64** | unchanged |

The throw fix is not cosmetic - it moves the predicted bound by up to 2.8 frames and changes the ROW
the predictor quotes at 21 of 64 endpoints. The arc changes **nothing, exactly**, and a 10x larger
table that strictly contains the smaller one returns the identical member every time.

## Why: the minimum is pinned to the cheapest member

The bound is `frames + n_atom + plan_cost + remaining(miss) + arrival_frames(gap)`. The atom's length
is charged **1:1 in frames**, and the two remaining terms are priced at ~12 u and 17 u per frame - so
one extra atom frame has to buy back a whole frame of landing or arrival, and it essentially never
does. Measured:

- the fan spans `n_atom` **3..24**;
- the minimum sits on an `n_atom` = **3** member at **64 of 64** endpoints, in **all three** lanes;
- the whole 75 627-member fan holds exactly **3** members at `n_atom` 3.

So the screen is a one-atom predictor wearing a large table. Its answer is a function of ~3 members;
the other 75 624 are priced and discarded (which is also why `predict_bound`'s own prune is worth 380x
- it stops almost immediately).

And the arc's members are all in the part of the table the minimum never reaches. The two fans have
**identical member counts at `n_atom` 3, 4 and 5** (3 / 50 / 166) and diverge only from **6** upward
(301 -> 593, 537 -> 2 269): the exit stick is held at the END of the atom, so until the atom is long
enough to reach the hold, the bearing has not happened yet.
[the-short-atom-is-a-point](the-short-atom-is-a-point.md) measured the same boundary from the other
side - the arrival set is a POINT until frame 8, and the arc at atom <= 6 is identical to the standing
pair to the last digit printed.

## What it means for the two measures

`predict_bound` and `cloud_landing` are not the same rank with different budgets. The screen returns
one field - the min bound - and that field is structurally short-atom. The keep returns three, and the
other two are **min-TOTAL among variants that already satisfy a predicate** (``in_band``, ``joint``),
which is not a frame minimum and is free to sit on a long atom. That is exactly where the arc's frames
showed up in session 118: the best BOUND never moved (93.95 before and after), while the best
DELIVERED went 106.45 -> 103.45 at tails 10-11.

**A knob that pays late is invisible to any measure that minimises a quantity the knob adds frames
to.** Plumbing it in is necessary and insufficient - the plumbing was still right to do, because it is
what lets the keep ask, but the screen needed a different QUESTION, not a bigger table.

Priced through the keep at the same beam's 27 firing survivors, that is exactly what the arc pays:
in-band nodes 2 -> **6**, joint nodes 1 -> **2**, best delivered **105.00 -> 104.00** - while the best
`bound` stays 93.95 and moves at all in only 7 of 27 nodes, by at most 0.176
([the-exit-bearing-buys-the-arrival](the-exit-bearing-buys-the-arrival.md) carries the table). The
same axis, through the two measures, is worth a frame and nothing.

## The rule

Before widening a table a cut reads, check which rows of it the cut's reduction can actually select.
A `min` over a sum that charges one axis linearly will sit at that axis's floor forever, and every
measurement you add above the floor is priced, discarded, and invisible in the output - so the search
looks like it considered the axis and cannot have. The diagnostic is one line: **report the argmin's
position on the charged axis.** If it is pinned to the extreme at every sample, the table's other
dimensions are decoration.

The corollary for this harness is that "the screen is landing-blind" (session 107) and "the screen is
arrival-blind" (session 115) were both true and both under-diagnosed. The screen is *cheapest-atom*
blind, and the two earlier findings are what that looks like from inside a particular half.

## Traps

- **A byte-identical cut does not mean the fix was inert.** Here 53 of 64 ranks and 21 of 64 row
  choices moved and the beam still came out identical, because the predictor is one of four orders in
  `full_herd._mixed_beam` and its share picked the same endpoints. Report the delta at the SCORER, not
  only at the output, or a real correction reads as a no-op.
- **A superset table returning the identical minimum is evidence about the REDUCTION, not the table.**
  It is the cheapest thing to check and it is the one that names the wall.
- **Do not price a "did the axis help" question on ``bound``.** Use the field that can hold a long
  atom (``joint`` / delivered), which is what the objective is denominated in anyway.

## See also

- [the-short-atom-is-a-point.md](the-short-atom-is-a-point.md) - why an atom below frame 8 is a rigid
  throw, and the independent measurement that the arc is worth zero there.
- [the-fan-outlived-its-columns.md](the-fan-outlived-its-columns.md) - the throw fix and the plumbing
  this page is the outcome of.
- [the-exit-bearing-buys-the-arrival.md](the-exit-bearing-buys-the-arrival.md) - where the arc's 3
  frames actually live, and in which field.
- [landing-keep-on-a-cloud.md](landing-keep-on-a-cloud.md) - the screen/keep division of labour this
  page puts a limit on.
