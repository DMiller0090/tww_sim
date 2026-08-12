# The roll lean has cells, exactly as the aim does

**Answers:** How fine does a lean sweep have to be before its zeros are real? How many distinct roll
leans are there actually? Is the lean an axis a planner can steer, or an output? Why is a lean grid the
wrong shape for a configuration sweep?
**Status:** MEASURED (session 159) on the flooded-Hyrule Tetra corner, by fingerprinting the baked
schedule across the whole reachable lean range at five cells and all three thrusts. Gated in
[`tests/test_admit_map.py`](../../tests/test_admit_map.py).
**Source:** [`harness/tetrapush/admit_map.py`](../../harness/tetrapush/admit_map.py) (`lean_runs`,
`lean_cell`, `schedule_fingerprint`).

---

## The atom

[`entry_search.aim_cell`](../../harness/tetrapush/entry_search.py) is the load-bearing idea in this
work's cost model: two roll facings in one console sine-table cell bake a **bit-identical** schedule and
are ONE draw, so the 81 aims in the window are 45 evaluations rather than 81. The same is true one axis
over, and it had never been measured.

Fingerprint the whole baked schedule - every array, every float through its raw f32 bits - across the
leans a bounded fan actually reaches, and the result is a **partition**:

| | |
|---|---|
| reachable leans (`entry_lean.census`, contiguous) | **1040**, spanning −775..+266 (only −1 and +1 absent) |
| distinct baked schedules over that hull | **129** |
| run widths | 1 to 32 BAM, mean 8.1 |
| partition re-derived at cells 2525 / 2545 / 2552 / 2554 / 2581, thrusts 13 / 14 / 15 | **identical** |

So the lean axis is 129 values, not 1042 and not a grid - and because the partition belongs to the lean
rather than to the configuration it was measured at, one derivation serves a whole configuration sweep.

## Why this matters more than an 8× saving

A sweep over a **grid** of leans has to argue its own resolution, and session 158 measured that the
argument is delicate: the admitting lean window at the console's configuration is ~181 BAM wide, so a
128-apart sweep steps over it and reports a false zero. Enumerating the 129 classes removes the argument
entirely - nothing is being sampled, so nothing can be stepped over. It is the same move
[`aim_cells`](../../harness/tetrapush/entry_search.py) made for the aim.

## The lean is an OUTPUT, not a steering axis

`lean_at_roll(m351C)` is the walk's own turn history at the endpoint, which is why `entry_lean` takes a
**census** of the leans a fan arrives on rather than sweeping a range. A planner cannot ask for a lean;
it can only notice which ones its plans produce, and how much mass lands on each.

Measured on the admitting side, that turns out not to cost much: at the console's own cell 2552 and
thrust 15, screened at an admitting entry, **all ten sampled lean classes admit** across the whole
reachable range, and the barren item's own lean admits there too. The axis that decides admissibility is
the entry - see [admitting-entry-region.md](admitting-entry-region.md).

## Honest limits

- The reachable hull comes from the banked census in
  [`fixtures/courtyard_lean_bands_s94.json`](../../fixtures/courtyard_lean_bands_s94.json), taken at one
  fan shape (`entry_lean.DEFAULT_FAN`, ≤ 4 frames). A different fan can reach further, and the partition
  would simply extend - the classes themselves are a property of the schedule bake.
- Two leans in one class are one draw for the **schedule**. They are not necessarily one draw for
  anything upstream of it that reads the raw s16 lean, the same caveat `aim_cell` carries about the entry
  frame's own MOVE.
- "All ten sampled classes admit" is ten of 129, at one (cell, thrust) and one entry. It says the lean is
  a weak axis there; it does not say the lean never matters - cell 2531 / thrust 14 admits at 2 of 8.
