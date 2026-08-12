# Which configurations can clip at all, screened in 16 ms

**Answers:** My item came back barren after an hour of fanning and scoring - was the search too small, or
can that configuration not clip at all? Which axis do I steer: the entry, the lean, or where the pushed
actor stands? How wide is the window on each? Can I check a configuration before paying for a fan?
**Status:** MEASURED (session 158) on the flooded-Hyrule Tetra corner. The screen is validated against
the full plane scan on both configurations known to clip and at twelve entries around the console's own.
Gated in [`tests/test_razor_band.py`](../../tests/test_razor_band.py). Builds directly on
[genuine-residual-band.md](genuine-residual-band.md) - the screen only works because `genuine` is
exactly `resid` inside the band, so one march along the residual's gradient visits every level.
**Source:** [`harness/tetrapush/razor_band.py`](../../harness/tetrapush/razor_band.py) (`admits`).

---

## The screen

Scanning her plane to answer "does this configuration clip for ANY position of hers" costs 0.5-14 s, so
it cannot screen a configuration *space*. `admits` walks the only axis that matters instead: it locates
where her residual crosses zero along its own gradient, then places her at 401 rungs spanning ±5e-04 of
residual either side. A band is ~4e-05 wide, so a ladder at ~2.5e-06 a rung cannot step over one.

Three batched sweeps, **~806 placements, ~16 ms** - against ~161 000 for a plane scan. For scale, the
session-155 sweep spent 4014 s over ten workers to conclude "0 genuine" for 21 items.

Read a positive as certain. A single negative is "not at this configuration, to this detector" - and it
is a weaker negative than it looks, because the detector reads ONE station of a curve: see
[razor-zero-curve.md](razor-zero-curve.md), where 27% of the stations along the console's own curve
admit. The strong form is a zero over a swept **range** with the range quoted.

## What a clip requires, measured on each axis

Every axis was swept at the console's own configuration (which clips) and at `w10_t15`'s (which shares
the console's **cell 2552 and thrust 15** and came back barren), holding the rest fixed:

| axis swept, at each item's OWN entry | console's own configuration | the barren one |
|---|---|---|
| where she stands (her plane) | genuine dust at ~0.3% of placements | **0** of 7 112 889 over ±2 u |
| the roll entry (2-D plane, ±0.8 u at 0.02) | 571 of 6561 admit, spread over the whole plane | **0** of 6561 |
| the roll entry (±5 u along x) | admits near its own | **0** of 501 |
| the roll lean (full 16-bit range, 4 BAM apart) | window ~181 BAM wide, its own lean inside | **0** of 16384 |

Those zeros hold, and they say the barren item admits nothing **anywhere near its own roll entry**. They
do not say it admits nothing: its own lean admits at the console's entry, 106 u away, and the axis that
separates the two is the entry at courtyard scale rather than float scale. The 2×2 cross that settles it,
and the map of where a clip is possible, are in
[admitting-entry-region.md](admitting-entry-region.md); the reading this table used to carry is in
[history/the-barren-item-dead-on-every-axis.md](../history/the-barren-item-dead-on-every-axis.md).

## The shape of the admitting set, at the console's own configuration

- **The lean window is ~181 BAM wide** and its own lean sits inside it. Within ±400 BAM there are two
  contiguous windows, `-118..+62` and `+75..+78`. A lean sweep coarser than ~180 BAM will step over it
  and report a false zero - which is exactly what a 128-apart sweep does, finding one bucket of 512. The
  way to stop arguing about that resolution is to enumerate the lean's 129 equivalence classes instead:
  [lean-cells.md](lean-cells.md).
- **The admitting entry set is diffuse, not a blob.** 571 of 6561 entries (8.7%) in a ±0.8 u plane admit,
  spread across the full extent in both axes. A march along one line through it gives a misleadingly
  compact answer: at `dz = 0` only offsets `-0.08..+0.06` admit, out of ±5 u swept. The set is a strip,
  and a single line samples it badly. Those percentages are read with her seed PINNED; re-locating her
  per entry takes the same plane to 69.6%.

## How to use it

Screen the configuration BEFORE paying for a fan. A barren item is now separable into two very different
verdicts, cheaply: *its configuration admits and the plans did not reach the admitting set*, versus *its
configuration admits nothing at this entry*, which no enumeration widening touches without moving the
entry. Only the first is a search problem, and the second is a walk problem rather than a dead end.

## Honest limits

- The screen walks the gradient out to `LOCATE_SPAN` (0.06 u), so it is **not** bounded by a tighter
  plane-scan box and will report genuine where a ±0.02 u window has none. That is the screen being right
  and the box being small, not a disagreement.
- It is conservative at an admitting region's **edge**: at the one entry of twelve where it disagreed
  with the full scan, the scan found 33 genuine of 160801 against 301 at the centre.
- It reads one station of the zero curve, so a negative from `admits` alone is weak. `admit_map.screen`
  walks the curve and is the stronger form.
- Every zero above is quoted with what was swept. A negative on one axis holds the others fixed, and in
  particular holds the ENTRY fixed, which is the axis that turned out to matter.
