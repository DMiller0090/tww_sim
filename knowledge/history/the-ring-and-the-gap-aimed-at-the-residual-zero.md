# "Aim her at the ring, and price a herd by its distance to it" (session 157, 2026-08-12)

> **status: historical** - this records a construction that is correct in its own terms and a TARGET
> that is not. What holds, and stays on the truth page: the wall brace pins the whole cut frame, so out
> of contact the roll entry is bit-exactly inert and the razor's remaining freedom is where the pushed
> actor stands; `cut_slice` reads that map off the native sim entry-invariantly at ~66 us a point. What
> was wrong is what the map was aimed AT. The ring is the locus `resid = 0`, and session 158 measured at
> full fidelity that a clip lives in a strictly POSITIVE residual interval which excludes zero - so the
> ring points at the one value the razor refuses, and the `gap` that prices a herd by its radial distance
> to that zero prices the distance to the wrong place. Current truth is
> [model/genuine-residual-band.md](../model/genuine-residual-band.md); the surviving half is
> [model/braced-cut-frame.md](../model/braced-cut-frame.md).

## What was claimed (session 157)

With `old` pinned by the brace, `target_ring` bisects the residual's zero per bearing off the braced Co
centre and reports the distance at which the cut ray crosses the seam vertex. On the bearing the
console's own herd used:

    ring distance   76.73543 u        where she actually stood   76.78111 u        aim error  0.046 u

and the recipe that followed was "ring to place her, entry lattice (`entry_dust`) to close the last
1e-04". Beside it, the herd's own price in her coordinate - `gap = |resid| / |d resid / d dist|`, both
off the sim - over 261 000 rows of walk 8 / thrust 13:

| | closest row | median in-contact row | s154's delivered 101 |
|---|---|---|---|
| gap to the residual's zero | 1.006 u | 414 u | 7.7e-04 u |

read as "nothing that item can build gets within a unit of where she has to be".

## Why the target is wrong

Sweeping her walk-end position at full fidelity - her own plow, the row's own `old` - the genuine
placements occupy a narrow positive interval of the residual and **zero is not in it**: the console's
own clip at [+5.796e-05, +9.918e-05], session 154's accepted 101 at [+1.628e-04, +1.967e-04]. Both
delivered rows sit inside their own interval; inside it the residual is sufficient, and no configuration
measured admits `resid = 0`.

So the 0.046 u agreement above is real and is a coincidence of scale, not a validation of the target:
the ring lands 0.046 u from where she stood while the interval itself is only a few residual quanta
wide. The ring locates the right NEIGHBOURHOOD - which is why marching the zero with a ±4 ULP lattice
probe found dust at all - and then aims at the refused point inside it.

The `gap` table inherits the same defect twice over. It measures the radial distance to the zero rather
than to the interval, and its "1.006 u" is a property of the 6000-candidate SAMPLE it was measured on,
not of the item. That item's own banked sweep already held a nearer row: priced through the identical
formula, walk 8 / thrust 13's recorded `best_resid_row` (`resid` +5.868e-03, slope -0.195 per u) has a
gap of **0.0301 u** - 33x under the sampled minimum, from a row the sweep had written to disk. A
minimum over a 4% sample of the candidates is not the item's minimum, and the sweep's own singled-out
rows were the place to check it.

## The lesson

`resid` was introduced as a *threading closeness* metric and then quietly promoted to the objective by
every tool that solved it for zero - `zero_the_resid`, `locus_scan`, `configuration_band`, `entry_dust`,
`target_ring`, `gap`. Session 155 had already measured that it is blind to the constraint that refuses
these rows (`wall_hit`, the acceptance's first test) and named it as
[[banded-proxy-needs-its-newton]] generalised. This is the same failure one step further in: not merely
a proxy that mis-ranks, but a proxy whose *root* is outside the accepting set. Before solving a residual
for zero, measure what the accepting set's residual actually is.
