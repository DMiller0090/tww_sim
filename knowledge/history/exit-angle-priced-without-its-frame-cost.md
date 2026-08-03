# The exit-angle axis priced without its frame cost (session 92)

status: historical
Source: superseded by [../strategy/clip-exit-angle.md](../strategy/clip-exit-angle.md) (session 93)

Session 92 recovered the seam's whole second facing lobe from behind a one-seed negative
([entry-search-one-seed-negative.md](entry-search-one-seed-negative.md)) and priced the exit-angle
objective term off it. The recovery is real and still current -- the dust is there, the cells are
aimable, the bands were measured. **What was wrong was the price**, and the error is worth recording
because it is the exact mirror of the one it had just fixed.

## Claim (dead): the reachable exit-angle axis is worth +144 to +160 BAM

As written: "the best cell that is *aimable at the frozen camera, carries a real band, and sits near the
delivered entry* is **cell 2562: +160 BAM (+0.879 deg)**, band 9.24e-05 -- WIDER than the delivered
cell's own -- nearest station 21.0 u away; cell 2561 is the near alternative (+144 BAM, 13.9 u). Against
session 91's reachable +9 BAM, that is ~10x on the axis Dereck priced at ~1 frame."

Every clause of that is a correct measurement. The conclusion does not follow, because **"near the
delivered entry" is not "reachable by a plan at the frame floor"**, and the frame floor is the only
budget the objective has: the herd must lose ZERO frames
([../strategy/razor-prices-every-term.md](../strategy/razor-prices-every-term.md)).

What it actually was: the stations were found by `curve_seeds` sweeping `entry_search.reach_radius` -- a
**94 u square box** around `ref_entry` (four walk frames at the cap plus the roll's 26 u entry step).
That box is a deliberate over-approximation and correct as a place to look for a level curve. It is not
the reachable set. Link enters the window at the speedF 17 cap on a fixed heading, and four held-stick
frames can only turn him so far, so the set is a small curved cloud whose bounding box is a fraction of
that area.

Measured in session 93, against that cloud:

- a frame-capped pass over the whole aimable second lobe -- **779130 candidates, 7.01 M evaluations, 9
  configurations** -- returns **0 genuine, 0 near, 0 dead-tail**, the emptiest result the search has
  produced;
- the closest any 4-frame candidate comes to a right cell's residual zero is **0.354** at cell 2561,
  rising monotonically with the facing offset to **1.873** at cell 2581 -- **71x to 375x** outside
  `BAND_PROBE`, at a `grad == 0` entry;
- for cells **2570 and further right the residual does not even change sign** over the 4-frame cloud;
- **18.4x more candidates moved cells 2561/2562 by bit-identical zero**, while the same extra density
  sharpened cell 2553 by 37x -- so it is not the fan that is short of resolution;
- and the reachable cloud, measured from the fan and knowing nothing about residuals, has a station for
  **only cells 2551 and 2552** at that budget -- exactly where every console-delivered candidate sits.

## Why the mirror image matters

Session 92's own lesson was that a **negative** is only as strong as the set it was argued over. This
claim is a **positive** argued over a set that was too big: an existence result inside a generous bound,
read as availability under the objective's budget. Both are the same failure of asking what set the
claim is actually about, and the second one arrived in the same session that named the first.

The current pricing, the per-budget measurement behind it, and the reachability test are on
[../strategy/clip-exit-angle.md](../strategy/clip-exit-angle.md#what-a-cell-costs-in-frames);
the general form is
[../strategy/razor-prices-every-term.md](../strategy/razor-prices-every-term.md) rule 13.

## See also

- [entry-search-one-seed-negative.md](entry-search-one-seed-negative.md) - the negative this claim was
  the reward for fixing.
- [entry-search-s81-camera-lever.md](entry-search-s81-camera-lever.md) - the camera, closed and reopened
  and now bounded by the same reach question.
