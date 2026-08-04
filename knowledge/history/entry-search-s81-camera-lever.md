# "The camera is worth 8x more usable configurations" (session 81 -> 83, 2026-08-01)

> **status: historical** - this records a lever measured in the wrong UNIT. The facing sweep behind it
> was real and its numbers are still right; they were read in BAM, and the physics reads the console
> sine table's 16-BAM cell. Current truth is
> [strategy/clip-entry-search.md](../strategy/clip-entry-search.md) (the cell is the aim alphabet's
> atom) and [strategy/clip-lottery-draws.md](../strategy/clip-lottery-draws.md) (count draws in the
> unit the physics quantizes to). Kept for the lesson, which is that a multiplier measured in a unit
> finer than the one the code quantizes to is a multiplier of copies.

## What was claimed (session 81)

With the momentum axis about to be generalized, the entry search's other configuration axis was the
camera. Sweeping the roll facing DIRECTLY at 1 BAM over 40400..41300 - 2703 configurations, 37 s -
found 48 productive, all inside one window 40816..40847, against an alphabet that the frozen csangle
34325 lands only four aims inside:

> The productive facing window is **32 BAM of consecutive facings** and the frozen camera reaches
> exactly **four** aims inside it, so the C-stick is worth up to **8x more usable configurations at
> zero frame cost** - csangle is position-independent during the walk-in, so one measured stream
> serves a whole fan.

Session 82 closed the momentum axis and named this "the only priced-nonzero lever left".

## What measurement changed (session 83)

The pricing pass ran first, as the s82 lesson demands, and it read exactly **8.00x**: scoring the
cached 43596-candidate fan against the whole window instead of the frozen aims took 6 near-misses to
48 and E[hits] 0.019 to 0.154. Then the near-misses were printed **with their identity**, and all 48
were **three candidates counted sixteen times, at bit-identical residuals**.

The cause is one line of console maths. `cM_ssin_s16` is JMASSin - `jmaSinTable[(u16)angle >> 4]`,
4096 entries, no interpolation ([model/fp-faithfulness.md](../model/fp-faithfulness.md)) - and every
term a roll facing reaches goes through it: the per-frame travel, the cut lunge's rotation, the Co
pose chain, and the roll entry's own 26 u step. So a facing's low four bits reach nothing, and:

1. **the 32-BAM window is TWO cells** (2551 = 40816..40831, 2552 = 40832..40847), which is also why
   the sweep's two halves have different thrusts and different band widths - they are two
   configurations, described sixteen times each;
2. **the frozen camera already reaches both.** Its four aims are 40820 and 40826 (cell 2551) and
   40834 and 40841 (cell 2552). There was never a missing cell to slew to;
3. **so a csangle slew adds exactly zero configurations**, and the qualified set drops from 6 to 3 -
   of which one has a real band and two are ULP tickets.

The camera keeps one much smaller reach, on the other side of the search. A held stick's world
direction is `decoded + 0x8000 + csangle`, quantized to the same cell, and the decoded-angle grid is
not uniform: 3612 of 4096 direction cells (88.2%) are reachable at the frozen camera and 3858 (94.2%)
over all 16 offsets. That is ~1.07x on CANDIDATES, an axis session 81 had already measured as buying
nothing (1.6x candidates, zero extra near-misses).

## What measurement changed AGAIN (session 95): the walk-side half above is wrong

That last paragraph priced the walk side over the **whole stick alphabet** (`msd_min=0`, 7032 decoded
angles). The fan cannot hold that alphabet: it keeps only endpoints at the speedF cap, so its sticks are
the cap-magnitude ones - **2280 angles reaching 1736 of 4096 cells, 42.4%**, not 88.2%. Sliding a 42%
subset is a different lever: a single sine cell of camera moves **888 of 1736** cells onto directions
the frozen camera cannot command at all, and the union over the reachable slew is the whole circle.
Measured, that re-draws the entry cloud - closest approach to one cell's residual zero 1.49e-3 frozen
against 2.9e-5 at +200 BAM on the same bounded fan. Current truth is
[strategy/clip-camera-axis.md](../strategy/clip-camera-axis.md). The AIM-side half of this page (the
cell is the atom; a slew re-indexes and cannot add a cell inside the window it was measured over) is
untouched and still current.

## The lesson

Sweeping a parameter at finer resolution than the code quantizes it to does not measure a finer
window; it measures the same window in more words. Both halves of the s81 reading were affected - the
"32 BAM wide" and the "four aims inside it" - and dividing one by the other cancelled nothing, because
both were inflated by the same 16.

The tell was available before the diagnosis and was ignored twice: the sweep's productive set split
into two blocks of exactly 16 facings with identical band widths and identical genuine counts, and the
pricing pass returned a multiplier of exactly 8.00x with near-miss gaps repeating to four significant
figures. **A perfectly integral multiplier and a repeated measurement are the signature of counting
copies.** Print the identity of what you counted before believing the count.
