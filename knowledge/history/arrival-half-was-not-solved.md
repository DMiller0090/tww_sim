# "The arrival half is solved" (session 110, 2026-08-06)

> **status: historical** - the measurement reproduces exactly; the verdict drawn from it does not
> survive being split by thrust. What holds: with the atom's tail and the exit arc, the joint
> candidates' `hull_scan` reads 15-45 cell/thrust combos with LEVERAGE where every session-109 scan
> read `n_leverage == 0`, and the pooled razor residual falls 3.3e-01 -> 3.1e-03. What was wrong is
> reading that as the arrival half closing. Session 111 re-ran the same scans recording the thrust of
> every combo: **all 173 of them are thrust 13** - the thrust
> [this corner refuses](thrust-13-refused-by-geometry.md) - and at the deliverable thrusts 14 and 15
> those landings read **zero leverage**, which is session 109's verdict unchanged. Current truth is
> [strategy/the-landing-belongs-to-the-endpoint.md](../strategy/the-landing-belongs-to-the-endpoint.md).

## What was claimed (session 110)

That giving `away_walk.escape_atom` a tail (``exit_run``) and sweeping `cloud_land.exit_arc` had
closed the arrival half of [delivery-is-two-predicates](../strategy/delivery-is-two-predicates.md),
leaving the landing as the whole remaining gap - "razor-precision now, not band". The next step
followed from it: score the landing against the razor, follow the residual gradient out of the
clipped placement sweep, and treat the herd as the fine axis *for the landing*.

## Why it read that way, and the control that settles it

`entry_reach.hull_scan` is called per (aim cell, thrust) over `entry_search.THRUSTS`, which is
`(13, 14, 15)`. Sessions 109 and 110 summed `n_leverage` and took the minimum `abs_min` **across all
three**, so a statistic dominated by thrust 13 was read as a statement about the candidate. Thrust 13
has leverage almost everywhere and clips nowhere.

The positive control the negative needed (`[[search-space-contains-human]]`, and `hull_scan`'s own
docstring) is one line of the same call. At the **console** arrival, with a session-104 hunted row as
the placement and the same 2-frame walk budget:

| placement, at the console arrival | walk | leverage 13/14/15 | walkable live 13/14/15 |
|---|---|---|---|
| the console's OWN placement | 4 (its own) | 45 / 45 / 45 | 0 / **9** / **18** |
| the console's own placement | 2 | 0 / 0 / 0 | 0 / 0 / 0 |
| row 9 (cost 20) | 2 | 45 / 45 / 45 | 0 / **5** / **4** |
| row 16 (cost 20) | 2 | 45 / 45 / 45 | 0 / **2** / **1** |
| row 0 (cost 21) | 2 | 45 / 35 / 35 | 0 / 0 / **4** |

The delivered configuration lights up under the identical call at its own budget, which is what makes
the negatives readable; a working configuration carries leverage at every thrust and dust only at
14-15, and thrust 13 reads 0 live even there. The session-110 joint candidates carry leverage at 13
**only** - 45 combos there, 0 at 14 and 0 at 15 - so they are not near-misses on a live
configuration, they are barren at every thrust that can clip.

(The 2-frame row of the console's own placement is not a finding about it: `entry_reach.FLOOR_FRAMES`
is 4 and its station is simply further than two walk frames. The session-104 rows were hunted at 2 and
are the placements for which that budget does reach one.)

## The lesson

**A statistic pooled over an axis one of whose values is known dead is not a measurement of the other
values.** `THRUST_FLOOR` 13 was proved refused in sessions 100-102 and left in the swept set, which is
right for a scan (a stray positive would be information) and wrong for a summary. Report per thrust,
and rank only on the ones that can deliver.

The scans that carry it now: `_notes/s111_scan_landing.py` records `reason`/`drops` and the thrust of
every combo, and prints leverage split by thrust.
