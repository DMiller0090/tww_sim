# Where this corner can clip at all, and the axis that decides it

**Answers:** WHERE can a clip happen, in coordinates a walk can aim at? Which axis separates a delivered
clip from a barren item on the same cell, thrust and lean? My item admits nothing - is that a search
problem, a dead configuration, or the wrong place to roll from? How far must I move the roll entry?
**Status:** MEASURED (session 159) on the flooded-Hyrule Tetra corner. The screen carries a rediscovery
gate (both delivered clips, from a seed it locates itself) that `map` and `entrymap` refuse to run
without. Gated in [`tests/test_admit_map.py`](../../tests/test_admit_map.py).
**Source:** [`harness/tetrapush/admit_map.py`](../../harness/tetrapush/admit_map.py) (`screen`,
`screen_space`, `entry_map`, `nearest_admitting_entry`).

---

## The axis, settled by a 2x2 cross

Cell 2552, thrust 15 for all four cells, her seed **located per configuration** rather than pinned:

| | console entry | barren `w10_t15` entry, 106 u away |
|---|---|---|
| console lean (-775) | **admits** | no band, 147 stations |
| barren lean (0) | **admits** | no band, 155 stations |

The lean does not move the verdict in either column and the entry moves it in both rows. That is the
whole finding: **the roll ENTRY is what decides whether a configuration can clip**, and it is the one
razor axis with structure at the scale of the courtyard rather than the scale of a float. It is also the
axis the WALK picks directly, which is what makes the admitting set a planner objective instead of a
diagnostic. See [lean-cells.md](lean-cells.md) for why the lean is a weak axis and an output besides.

## The map

45 aim cells x 3 thrusts x 8 lean classes, screened at the tabulated entry: **1080 screens, 74 admit
(6.9%), 1465 s.**

| | cells admitting somewhere |
|---|---|
| thrust 13 | **0 of 45** |
| thrust 14 | 6 of 45 |
| thrust 15 | 12 of 45 |

**Thrust 13 admits nowhere**, which independently reproduces the console-derived session-144 result -
over the whole reachable box at the delivered lean, thrust 13 bisected 2390 razor roots and converted
none of them - from an instrument that shares no code path with it.

Five (cell, thrust) pairs admit at EVERY sampled lean: **(2551,15), (2552,14), (2552,15), (2553,15),
(2561,15)**. The console's own is among them, and 2561 is the cell session 92 flagged as carrying genuine
dust at a walkable entry. Thirteen more are partial in the lean, so the lean narrows a window without
opening or closing one.

## The region itself, and why the table above may not be used as a bound

`entry_map` over the box spanned by the two delivered entries, at 10 u:

| configuration | entries admitting | the same pair in the tabulated-entry table |
|---|---|---|
| console's own: cell 2552, thrust 15, lean -775 | **47 of 225 (20.9%)** | admits at 8 of 8 lean classes |
| s154's accepted 101: cell 2545, thrust 15, lean +104 | **97 of 225 (43.1%)** | **admits at 0 of 8** |

The second row is the warning, and this work supplied its own counterexample: **s154's accepted 101 sits
on a (cell, thrust) that the one-entry map reads as admitting nothing at any sampled lean, and it
delivered a clip.** A map at a fixed entry RANKS configurations; it never bounds them. Do not prune a
cell off it.

What the region does give is a plannable target: a fifth to two fifths of the delivered neighbourhood
admits, so a walk does not have to hit a point, it has to land in a region.

## The three verdicts a barren item can get

Before this, a barren item was "search too small" or "configuration dead". There is a third, and it is
the one that matters:

1. **admits at its own entry** - the plans missed it, so it is a search problem and worth a fan;
2. **admits, but not from where it rolls** - a WALK problem. `nearest_admitting_entry` prices it by an
   expanding ring search and returns the distance **in u of Link's roll entry**, which is a quantity a
   planner can steer, unlike `razor_band.band_distance`'s residual units;
3. **admits nowhere inside the searched radius** - and even that is quoted with its radius.

Re-read across all fifteen items of the session-155 sweep, at each item's own configuration and entry,
with both controls run first at the same settings and both firing:

| verdict | items |
|---|---|
| admits at its own entry (a search problem) | **0 of 15** |
| admits within 48 u of it (a walk problem) | **1** - `w09_t15`, cell 2561, at 48.0 u |
| admits nowhere inside 48 u | 14 |

So the sweep's barrenness was never a density problem. **Every item was rolling from a place where no
position of hers can clip**, which is why 4014 s of fanning over ten workers returned nothing, and why
widening the enumeration at those items could not have helped. The one item within reach is on cell 2561,
which is also one of the five pairs that admit at every sampled lean and the cell session 92 flagged.

## Honest limits

- The map above is read at ONE entry (the tabulated one), so a cell that admits nothing there may admit
  elsewhere. It bounds nothing; it ranks. `entry_map` is the per-configuration answer, over a box
  derived from the two delivered entries so both are inside it by construction.
- Every screen walks a bounded arc of the zero curve from a bounded ray fan, and returns both
  ([razor-zero-curve.md](razor-zero-curve.md)).
- The entry is a strong axis, not a free one: at the console's configuration, re-locating her per entry
  takes a ±0.8 u entry plane from 8.7% of entries admitting to **69.6%**, so nearby entries mostly agree
  but not always.
- The barren re-read used a shorter arc (12 u) per ring probe than a full screen, to keep 15 items x 49
  probes affordable, so its 14 "nowhere inside 48 u" are weaker negatives than the items' own screens.
  The zeros at each item's OWN entry are full-arc.
- "Admits" is a statement about the razor, not about deliverability. A configuration that admits still
  has to be reached by a plan and confirmed with a real A-press (`entry_search.confirm_entry`) and the
  walled composite (`cross_engine.agree`).
