# The camera cannot buy the snap, but `l_ok` never needed the snap - and the supply was already in the grid

**Answers:** My census says one clause refuses most of my search - is that a physics wall or a rank
that never asked? Session 77 measured the camera unreachable; does that close the question? Why do two
nodes of the same beam, same endpoint, same roll, one firing and one dead, differ only in a camera
target? How do I tell a screen that is measuring the wrong quantity from one that is measuring a real
limit?
**Status:** MEASURED (session 116) and SWEPT WHOLE (session 117) on the flooded-Hyrule Tetra corner,
against the session-111 cycle-3 beam (`_generated/s106/s111_c3_beam.json`): `away_walk.snap_reach` at
all 64 nodes (26 distinct rolls), the atom re-enumerated at clearing camera targets, and **every one
of the 551 clearing states priced whole** by `cloud_land.cloud_landing`. Drivers
`_notes/s116_lok_supply.py` and `_notes/s117_camera_axis.py`, bed
`fixtures/courtyard_lok_s116.json`, dumps `_generated/s106/s11{6,7}_*.json`.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`lok_clear`,
`snap_reach`, `fires_census`, `escape_atom`, `snap_bill`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`lok_probe_key`,
`camera_probe_key`, `roll_candidates`' ``tcs_probe``, `ESCAPE_TCS_SPAN`/`ESCAPE_TCS_STEP`),
[`harness/tetrapush/beam_io.py`](../../harness/tetrapush/beam_io.py) (`split_last_roll`).

---

[the-separation-is-not-a-suffix.md](the-separation-is-not-a-suffix.md) ended session 115 by naming the
beam's #1 blocker: over 64 censuses `away_walk.fires`' ``l_ok`` clause is the SOLE failure on **7349
variants (63%)** and the sole blocker at **19 of the 35 nodes that fire nothing at all**. Those 19 are
not bad endpoints - they are endpoints whose atom was never allowed to run.

`l_ok` is a facing question: the escape's L frame must not act with Tetra inside the ±90 deg talk cone
([tetra-follow.md](../mechanics/tetra-follow.md)). At a herd endpoint Link is 38-75 u behind her, so
distance can never clear it, and the atom cannot turn him itself - turning spends the EBS the next
stage needs. The whole supply is the LAST ROLL's `target_cs`, idle for the roll's entire duration.

## The finding: the snap is unreachable, the CONE is not, and only one of them was ever asked for

[ebs-turnaround.md](../mechanics/ebs-turnaround.md) measured (session 77) that a roll's reachable
camera set has an 87 deg hole exactly where the snapping band sits, so the facing SNAP cannot be
bought. That half stands and is re-confirmed here. But the snap is a sufficient condition, not the
thing owed, and the two come apart by an order of magnitude:

| over 26 rolls of the beam, 107-121 reachable camera states each | states that SNAP | states that CLEAR the cone |
|---|---|---|
| range across the 26 rolls | **0-6** | **0-68** |
| rolls with none at all | 5 | 3 |
| rolls with one on the search's OWN `ESCAPE_TCS_STEP` 512 grid | - | **21 of 26** |

So this is not a resolution problem and never was a physics wall. For 21 of the 26 rolls the supply
sat inside the grid `full_herd.derived_target_css` already enumerates, and the cut that picks a camera
from it (`roll_candidates`' ``tcs_probe``) was ranked by `camera_probe_key` - **the snap bill**, the
one quantity the previous session had just shown to be uncollectable.

## A dead node and a firing node can be the same roll with a different camera

The beam contains its own control. Keyed by (pre-roll endpoint, aim, L window, entry csangle) its 64
nodes are **26 rolls**, and **12 of those hold BOTH a firing and a non-firing member** - identical
physics up to the last roll, identical aim, identical herd frame count, differing only in `target_cs`:

    split 49 aim (171,192) lw (4,7): fires [1]      dead [16, 17]
    split 51 aim (158,198) lw (4,7): fires [3, 6]   dead [52]
    split 55 aim (164,195) lw (4,7): fires [50, 51] dead [53]      ... 9 more

Re-firing a dead node's own roll at a clearing target, on the 512 grid, takes its atom from **0 of 672
variants to 238-624** - and `l_ok` leaves the failure census entirely at the best of them. The herd
cost does not move: it is the same number of frames, aimed the same way, with the C-stick pointed
somewhere else.

| node (l_ok-sole, 0/672 at its own camera) | clearing states | fires at a clearing target |
|---|---|---|
| 16 | 68 of 107 | 301-329 of 672 |
| 52 | 35 of 107 | **624** of 672 |
| 53 | 23 of 107 | 510-532 |
| 54 | 6 of 109 | 238-411 |
| 60 | 2 of 107 | 320-321 |

It is not confined to the 19 either. Node 18 fires nothing with NO sole clause at all (both `l_ok` and
`dips` fail on every variant) and still reaches **298 of 672**; node 14, already firing 277, reaches
**644**.

## ...and it does not move the floor, which is the other half of the result

Every revived terminal priced whole (`cloud_landing`, atom cap 6, the s115 convention) sits **above**
the beam's existing best bound: the best revived node is 16 at **94.76** against node 0's **93.95**,
reproduced bit-identically here. One `in_band` landing appears that s115 had nowhere (node 11, total
102.00), still worse than the banked **101**.

So the honest statement has two halves and neither may be dropped: **the #1 blocker is real, is a rank
error rather than a physics limit, and is fixable inside the existing grid - and fixing it re-opens a
third of the beam without moving its floor to speak of.** What it buys is a search that may now choose
among those endpoints at all.

Session 116 priced two clearing targets a roll out of up to 68, picked structurally (widest cone
margin / smallest slew / median), which is a sample of an axis rather than a measurement of it.
Session 117 swept it: **all 551 clearing states, all 23 rolls that have any, 22 minutes at 8
processes.** The verdict:

| over the whole swept axis | |
|---|---|
| beam floor | **93.87** (node 1's roll, `off` -3456), against the sampled **93.95** - it moves **0.08 f** |
| what the camera is worth WITHIN one roll | **0.01 - 5.81 f** of bound (median span 1.6) |
| what the structural sample missed at the floor's own roll | **0.89 f** (94.76 sampled vs 93.87 swept) |
| landings inside `objective.PLACEMENT_BAND` | **1 -> 14 states over 3 rolls**, best landing total **98.00** |
| `joint` (landing AND arrival owed nothing) | **still none** - see [delivery-is-two-predicates.md](delivery-is-two-predicates.md) |

So both halves survive the sweep, with one number changed: the floor moves 0.08 f, not 0. The camera
is a large lever inside a roll and a nearly flat one across the beam, because the roll that already
held the floor was already near its own camera optimum. **The banked 101 STANDS.**

## The rule: rank on the clause that refuses, and BINARY

The margin at the L frame predicts how MANY variants fire - within one roll it is monotone over the 18
enumerated states - and does **not** predict what they are worth: node 16's widest margin (47.9 deg,
1507 firing) bounds 94.78 while its narrowest (30.1 deg, 1494) bounds **94.76**, and node 52's widest
(68.2 deg, 3622 firing) bounds 98.72 against 98.41 for a narrower one. So
[`full_herd`](../../harness/tetrapush/full_herd.py)`.lok_probe_key` ties every clearing target at 0.0
and lets `landing_key`'s own order separate them - an ordering by margin would be a preference nothing
measured.

A KEEP SHARE, and ``tcs_probe`` takes a SEQUENCE, one share each, because the snap bill and the cone
are independent orders and neither contains the other. Session 116 gave two REASONS for that shape and
both have since been measured away: ``dips`` refusing the other half whatever the camera does (session
121 - it decides no endpoint at all,
[the-dip-budget-is-not-the-lever.md](the-dip-budget-is-not-the-lever.md) and
[../history/dips-refuses-the-other-half.md](../history/dips-refuses-the-other-half.md)), and the
session-73 calibration that a camera filter throws away firing states, which was measured on the SNAP
BILL and does not transfer to a predicate with no false positives (session 122,
[../history/the-cone-keep-was-a-share-because-a-filter-throws-away-firing-states.md](../history/the-cone-keep-was-a-share-because-a-filter-throws-away-firing-states.md)).
The shape ships unchanged on a measured reason instead: as a REQUIREMENT (`full_herd.as_requirement`,
`extend_cycle`'s ``lok_require``) the same predicate gives an all-firing beam 20% cheaper and returns
**the same 105.00 at the same endpoint**, so the default stays where the banked provenance is -
[the-shape-of-a-cut-is-not-its-answer.md](the-shape-of-a-cut-is-not-its-answer.md).

And the screen is **exact**, which session 117 measured rather than assumed: at the two rolls whose
every reachable state was priced (225 of them), **107 of 107 clearing states fire and 118 of 118
non-clearing states fire nothing** - no false positive, no false negative. `lok_clear` is not a
heuristic filter on the camera axis; on these rolls it IS the axis. What it is not is a rank -
[the-screen-is-not-the-rank.md](the-screen-is-not-the-rank.md) measures what the ordering left on the
table once the screen let everything through.

**The transferable rule:** when a census names one clause as the blocker, find the CHANNEL with
authority over that clause and measure what it can deliver - then check that the screen choosing from
that channel is ranked on the clause and not on a proxy for it. Two proxies stood in for `l_ok` here
for forty sessions: the snap (a sufficient condition) and the ARRIVAL's own cone margin (the wrong
frame - every revived terminal still reads -33 to -79 deg at the endpoint, and the two atom frames are
what move it).

## Traps

- **A negative measured at three arrivals is not a law.** Session 77's `n_clear` 0/0/1 was true of its
  three arrivals and false of 23 of the 26 rolls here. It closed the camera question for three
  sessions. `snap_reach`'s numbers are a property of the arrival; re-measure at the pool in hand.
- **Filtering a fine sweep down to a coarse grid UNDERCOUNTS the coarse grid.** `snap_reach` dedupes
  by the `(csangle, travel)` a target delivers, so at step 64 a multiple-of-512 offset is often dropped
  in favour of a neighbour that lands on the same state. Keeping only `off % 512 == 0` from a step-64
  sweep therefore finds supply at 19 rolls where sweeping the 512 grid DIRECTLY finds it at 21. Sweep
  the grid you mean to claim.
- **The L WINDOW is part of a roll's identity.** Nodes 0 and 16 share endpoint, aim and entry csangle
  but roll at (5,8) and (4,7): different rolls, different reachable sets (118 states / 39 clearing
  against 107 / 68). Group camera families without it and half the beam is silently skipped as
  duplicate.
- **A clearing camera is a DIFFERENT arrival.** `target_cs` steers the post-roll EBS travel, so it
  moves where Link ends and what Tetra was left at. The cone reading is a screen; the verdict is the
  whole-candidate price at the terminal it actually produces.
- **Re-open a banked terminal with [`beam_io`](../../harness/tetrapush/beam_io.py)`.split_last_roll`,
  not by hand.** It recovers the pre-roll endpoint from the last A-run in the log and asserts the
  re-fired roll is byte-identical and 0-ULP; a split one frame off measures a different roll and says
  so nowhere.

## See also

- [mechanics/ebs-turnaround.md](../mechanics/ebs-turnaround.md) - the snap itself, why the camera
  cannot deliver IT, and the s75 note that clearing the cone is what the frame owes.
- [the-separation-is-not-a-suffix.md](the-separation-is-not-a-suffix.md) - the census that named
  ``l_ok`` as the #1 blocker, and the other resource it competes with.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - what a priced candidate owes once
  its atom is allowed to fire at all.
- [mechanics/tetra-follow.md](../mechanics/tetra-follow.md) - the ±90 deg talk/lock cone `l_ok` reads.
