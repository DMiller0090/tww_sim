# The razor is a positive residual interval, and zero is not in it

**Answers:** My sweep reports `|resid| = 3e-06` beside 0 genuine - how can a row be on the razor and
refused? What should a search MINIMISE, if not the residual? Why does one f32 ULP either side of a
clipping row fail? Is `resid` a proxy for a clip, or the thing itself?
**Status:** MEASURED (session 158) on the flooded-Hyrule Tetra corner, at full fidelity (`placed_step
= 0`, the row's own plow and its own `old`), on BOTH rows known to clip: the console's own delivered
clip (herd 78, cell 2552) and session 154's accepted 101 (herd 71, cell 2545). Gated in
[`tests/test_razor_band.py`](../../tests/test_razor_band.py) (8). It corrects the target every earlier
instrument in this work aims at, including
[braced-cut-frame.md](braced-cut-frame.md)'s ring - see [What this overturns](#what-this-overturns).
**Source:** [`harness/tetrapush/razor_band.py`](../../harness/tetrapush/razor_band.py)
(`genuine_band`, `in_band`, `band_distance`, `zero_is_outside`).

---

## The measurement

Hold a configuration (aim cell, thrust, lean) and its roll entry, sweep **where Tetra stands at the
walk end** over her own plane, and read `genuine` straight off the native sim. The genuine placements
do not scatter: they occupy one narrow, strictly positive interval of the residual.

| configuration | genuine residual interval | width | distinct values | in-band rows genuine | overlap |
|---|---|---|---|---|---|
| console's own clip (cell 2552, thrust 15) | **+5.796e-05 .. +9.918e-05** | 4.1e-05 | 7 | 301 / 301 | +1.2259 |
| s154 accepted 101 (cell 2545, thrust 15) | **+1.628e-04 .. +1.967e-04** | 3.4e-05 | 4 | 510 / 510 | +3.2218 |

Each delivered row lands inside its own interval, and **neither interval contains zero**. Inside an
interval the residual is not merely necessary but **sufficient**: no placement whose residual falls in
the interval fails. That held in every one of the 20+ configurations measured, and `genuine_band`
returns `sufficient` per call rather than assuming it.

## So a row at `resid = 0` is not near the razor - it is on the far side of it

The whole [barren re-run sweep](../history/) drove its rows toward zero and reported the closest as its
best: `|resid| = 3.11e-06` at walk 12. Priced against the interval, those rows are a full band-width
and more SHORT of any clip, on the side where the cut ray passes the wrong side of the seam vertex and
aims through the wall. That is the mechanism behind the two earlier readings that looked like fine
structure:

- every near-razor row of the barren sweep re-evaluates `wall_hit`, the acceptance's FIRST test, while
  the one row that clipped has it clear;
- one f32 ULP either side of a clipping row flips `wall_hit` - because a ULP of Tetra is a
  residual quantum, and the interval is only a handful of quanta wide.

`band_distance` is the ranking key this implies: signed, zero inside the band, negative for the short
side. `|resid|` ranks a hopeless row first.

## The interval is per configuration - do not carry a number

Cell 2545 sits about three times further from zero than cell 2552, and cell 2551 lands at
[+1.66e-05, +4.42e-05] with its own overlap of +1.512. The interval is stable against the lean over
±8 and against the entry over the ~0.05 u neighbourhood measured, and it is **not** a seam constant. A
search solves it per configuration; a ±0.02 u scan of her plane returns the same interval as one 2.5×
wider and one 2× finer, in about half a second.

## Her position reaches the residual through a quantized channel

A 160801-placement scan of her plane returns only ~1900-4700 **distinct** residual values - about 86
placements per value - and the genuine ones take 4 and 7 distinct values at the two controls. So a band
is a handful of reachable rungs, not a continuum, and a row that lands between two rungs cannot be
nudged onto one by moving her a ULP. This is the same lesson as
[the entry's own f32 quantum](braced-cut-frame.md), in Tetra's coordinate.

## Where her position is NOT the missing variable

Scanning a ±0.6 u square of her plane (641601 placements) at each of the 15 barren items' own
best-row configurations returns **no genuine placement at all**, while the identical scan at both
clipping configurations finds them - so the controls establish the scan's sensitivity before the zero
is read as a result. Widened to ±2 u (**7 112 889 placements**) on two of them, it is still zero, and
one of those two is `w10_t15` on **cell 2552 at thrust 15** - the console's own cell and thrust, where a
band demonstrably exists at the console's own entry.

So for those rows the entry and configuration are already disqualifying: moving Tetra does not rescue
them, a herd that aims her better at the same entry is aiming at nothing, and the deciding variable is
upstream of her. Quote it with its window - it is a statement about a 2 u neighbourhood of where each
herd left her, not about her whole plane.

## What this overturns

- **`resid = 0` as the target.** `entry_search.zero_the_resid` / `locus_scan` / `configuration_band`,
  `entry_dust`'s march, `cut_contact.target_ring`'s bisection and session 157's `gap` all solve for the
  residual's zero. The zero is refused at every configuration measured. Those tools still locate the
  right NEIGHBOURHOOD - the band is only a few quanta away - which is why marching the zero with a
  ±4 ULP lattice probe found dust at all.
- **`cut_contact.cut_slice`'s `genuine` flag.** The slice pins `old` at the braced value, which moves
  its residual by ~1e-02 - 300 band-widths. On the very placement that delivered it reports
  `genuine = False`, and `target_ring(lattice=)` returns 0 genuine at every bearing including the
  console's own. The slice is an aim; the band must be read at full fidelity.

## Honest limits

- `sufficient` is measured per call and returned. `in_band` is a verdict only while it holds.
- `genuine == 0` is a statement about the WINDOW scanned, never about the configuration - move the
  entry 0.2 u and the same scan finds nothing while the band is unchanged. Quote `tested` with it.
- The band is read at ONE entry and is not claimed beyond the ~0.05 u neighbourhood measured.
