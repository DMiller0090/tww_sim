# "The barren item is dead on every axis, so the entry is not the live one" (session 158, 2026-08-12)

> **status: historical** - this records a set of measurements that are all correct and a CONCLUSION drawn
> from them that is not. What holds, and stays on the truth pages: a clip lives in a strictly positive
> residual interval that excludes zero; `razor_band.admits` screens a configuration in ~16 ms; and the
> barren `w10_t15` really does admit nothing anywhere near its own roll entry. What was wrong is the word
> **every**. Session 159 screened that item's own lean at the CONSOLE's entry, 106 u away on the same
> cell 2552 and thrust 15, and it admits. The entry is exactly the separating axis; session 158 swept it
> over +-0.8 u and +-5 u, which is 1 to 5% of the distance that actually separates the two. Current truth
> is [model/admitting-entry-region.md](../model/admitting-entry-region.md) and
> [model/razor-zero-curve.md](../model/razor-zero-curve.md); the surviving half is
> [model/genuine-residual-band.md](../model/genuine-residual-band.md).

## What was claimed (session 158)

`w10_t15` shares the console's cell 2552 and thrust 15 and came back barren from an hour of fanning. Every
axis it could vary was swept at its own entry:

| axis swept, holding the rest | the barren item |
|---|---|
| where she stands (her plane, +-2 u) | 0 of 7 112 889 placements |
| the roll entry (2-D plane, +-0.8 u at 0.02) | 0 of 6561 |
| the roll entry (+-5 u along x) | 0 of 501 |
| the roll lean (full 16-bit range, 4 BAM apart) | 0 of 16384 |

The console's own configuration lit up under every one of those same sweeps, so the sweeps were sensitive.
The conclusion was that the item is "dead on every axis, not short of search", and therefore that the
handoff's line "the entry is the live axis" was false as stated.

## What overturned it

A 2x2 cross, at cell 2552 and thrust 15 for all four cells, with her seed **located per configuration**
rather than pinned (`_notes/s159_cross.py`):

| | console entry | barren entry, 106 u away |
|---|---|---|
| console lean (-775) | **admits** | no band, 147 stations |
| barren lean (0) | **admits** | no band, 155 stations |

The lean does not move the verdict in either column, and the entry moves it in both rows. The item's own
lean admits perfectly well; it is standing in the wrong place to roll from.

## Why the session-158 sweeps could not see it

Three things, each of which narrows a window rather than being wrong:

- **Scale.** +-5 u along one axis of the entry, against a 106 u separation. The entry is the one razor
  axis with structure at the scale of the courtyard, not at the scale of a float.
- **Her seed was pinned.** The entry-plane figures were read by moving the entry while leaving her where
  the row put her. Re-locating her per entry at the console's own configuration takes a +-0.8 u plane from
  **8.7% of entries admitting to 69.6%** - so a pinned-seed entry sweep understates admissibility roughly
  eightfold, and its zeros are largely a statement about the seed.
- **One station.** `admits` ladders through one point of the `resid = 0` curve. At the console's own
  configuration only 27% of the curve's stations admit, so a single-station read is a coin flip weighted
  against a positive ([model/razor-zero-curve.md](../model/razor-zero-curve.md)).

## The lesson worth keeping

The failure mode is not the measurements, it is quantifying over an axis that was sampled at the wrong
scale. "Dead on every axis" was four sweeps, each honest about its own window, summed into a claim that
none of them supported. `[[probe-below-the-quantum]]` is the same error at the small end: there the
sweep stepped finer than the axis's own quantum and re-tested one point; here it stepped over 1% of the
axis and reported the whole of it. Both are fixed the same way, by pricing the axis before sweeping it.
