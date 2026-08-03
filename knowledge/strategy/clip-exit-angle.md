# Steering a seam clip's EXIT ANGLE

**Answers:** The clip lands and Link goes out of bounds - now the DIRECTION he leaves in is worth
frames. Which quantity is the exit angle, and how finely can it be set? Can I steer where Link cuts
from? How wide is the facing window really, and what does it take to argue that a facing is dead?
**Status:** validated offline (session 92) on the flooded-Hyrule Tetra corner, against the
console-delivered clip in [`fixtures/courtyard_clip_s90_console.json`](../../fixtures/courtyard_clip_s90_console.json):
the cut-position pinning, the cell quantum and the two-lobe window are measured, and the recovered
second lobe is `ShoveCtx` dust that has NOT been cross-engine confirmed or delivered. Gated in
[`tests/test_entry_search.py`](../../tests/test_entry_search.py).
**Source:** [`harness/tetrapush/entry_search.py`](../../harness/tetrapush/entry_search.py)
(`curve_seeds`/`curve_scan`, `aim_cell`, `resid_fn`);
[`fixtures/courtyard_facing_window_s92.json`](../../fixtures/courtyard_facing_window_s92.json) is the
measured window.

A seam clip is usually asked one question - does Link go out of bounds - and the answer is a yes or a
no. Once he is out, a second question can be worth frames: **which way is he travelling?** On the
Courtyard corner that is worth about one frame downstream (the Deku Leaf), so the exit angle became an
objective term while the frame count was already at its floor.

This page is how to steer it, and what does *not* steer it. The search whose residual and window it
sits on top of is [clip-entry-search.md](clip-entry-search.md).

## The variable is `travel`, and its atom is the sine-table CELL

What carries Link away from the seam is not the teleport across it. Measured on the Courtyard clip:

- the cut segment `old -> new` is **nailed to the seam** - it has to be, since it is genuine only when
  it threads the gap at the corner vertex. Its bearing moves **0.76 deg** across the entire live facing
  window, **0.0002 deg** between the delivered cell and its right neighbour, and **0.0000 deg**
  across all 288 tabulated placements of the pushed actor.
- what moves is **`travel`**, which equals `facing` through a roll, and which is Link's heading in the
  `daPyProc_FALL_e` that follows. That is a different quantity from the cut ray, and it is the one with
  room: the same window spans **2.37 deg** of it.

So do not measure the exit angle on the displacement that clips. Measure it on the heading the fall
inherits.

And it is **quantized**. `cM_ssin_s16`/`cM_scos_s16` are `jmaTable[(u16)angle >> 4]` with no
interpolation ([../model/fp-faithfulness.md](../model/fp-faithfulness.md)), so every facing inside one
16 BAM cell leaves Link on a *bit-identical* heading. The exit angle therefore has a hard **0.087891
deg** quantum, and "the rightmost facing" is a category error - ask for the rightmost **cell**. This is
the same atom the draw count uses, for the same reason
([clip-entry-search.md](clip-entry-search.md#the-multipliers-and-the-unit-they-have-to-be-counted-in)).

## What does NOT steer it: Link's cut position

The tempting lever is where Link cuts from. A clip map that sweeps the cut position `old` and records,
per position, which displacement magnitudes thread the gap will show a wide spread of geometry - and
reading that spread as reachable is a mistake worth naming, because it looks like a large prize.

**When the roll ends against a corner, `CrrPos` pins `old` at exactly `WALL_R` from the wall, and the
brace is an attractor with a basin tens of units wide.** Measured on the Courtyard: slide the entry
±30 u along the roll direction and the cut position does not move one f32 ULP; slide it ±1 u and all
seven samples are the same bit-identical point; and across a whole 55-candidate deliverable population
- four different plan lengths, two facing cells, every entry - there are **3 distinct cut positions
inside 0.035 u**. A clip-map row 0.25 u away is geometry no roll into that corner can occupy.

What the entry moves is the **cut-frame push**, and only that: the pushed actor is plowed differently
on the way in, so she ejects Link differently on the frame the cut fires. That is visible as a
residual sliding smoothly (~0.03 u per u of entry) while `old` stays frozen - and it is the whole
mechanism by which a righter facing still clips, because the push *rotates* to supply the offset that
puts the rotated ray back on the vertex.

## The window is a MEASURED set of cells, and it need not be contiguous

With the cut position pinned, whether a facing cell can clip at all is a question about the push it
would need. Do not reason it out - the answer is not an interval. Measured on the Courtyard corner
(48 level-curve seeds per cell, one thrust, entries restricted to the reachable box):

| cells | live? | notes |
|---|---|---|
| 2548-2553 | yes | the lobe every pass knew about; the delivered clip is 2552 |
| 2554-2559 | **no** | 0 live stations from ~48 seeds each - a negative worth quoting |
| 2560-2575 | yes | a **second lobe**, dust thinning and bands narrowing sharply past 2563 (several read zero width) |

Scanned 2548-2575; re-qualifying the whole alphabet on the same seeding takes the search's productive
set from **6 configurations to 40** (none lost) and reaches **cell 2581, +464 BAM**, so the lobe's right
edge is past where this table stops.

Two things fall out of it:

- **the axis is worth an order of magnitude more than a contiguous reading gives.** Off the delivered
  cell, +1 cell (+0.088 deg) is all the first lobe offers. The best cell that is *aimable at the frozen
  camera, carries a real band, and sits near the delivered entry* is **cell 2562: +160 BAM
  (+0.879 deg), band 9.24e-05, nearest station 21.0 u away** - and its band is **wider** than the
  delivered cell's own 6.28e-05, so it is not even a trade against difficulty. Cell 2561 is the near
  alternative (+144 BAM, band 8.60e-05, 13.9 u).
- **the lunge grows to the right** (49.74 u at the delivered cell to 50.31 u at +288 BAM). "A longer
  lunge buys angle" is not a second lever to price separately; it is this same geometry, since a ray
  rotating away from the pinned position needs more length to still reach the vertex.

## The camera axis REOPENS when the window is wide

`csangle` shifts the whole aim alphabet, so it decides which cells a frozen camera can aim at. It was
priced at **zero** and closed - correctly, against a 2-cell window the frozen aims already covered
([../history/entry-search-s81-camera-lever.md](../history/entry-search-s81-camera-lever.md)). Against a
22-cell window it is a live lever again: of the live cells above, six (2550, 2560, 2563, 2565,
2566, 2571) are **not aimable** at the frozen camera, and one of them is the rightmost cell with a workable
band. Re-derive what the camera reaches whenever the window's width changes; a closure is only as
current as the window it was measured against.

## The rule this corner paid for

A configuration that reads dead may only be dead **from where you asked**. `grad ~ 0` means "the pushed
actor is out of Co range on the cut frame *from this entry*" - leverage is a property of the ENTRY, not
of the configuration, and a righter facing's roll leaves her behind from a seed chosen for a different
facing. So the strong form of "is anything genuine here" is not a longer march from one seed; it is
seeding off the residual-zero curve's **own crossings** (`curve_seeds`: sweep the reachable box, take
every adjacent pair whose residual changes sign, dedupe, march each). One vectorized sweep per
configuration, and it is what the negative has to be argued from.

Cost of getting that wrong here: **every pass from session 81 to 91 had the entire second lobe out of
scope**, because it was excluded by a `no leverage at the seed` reading taken at one point. The
migrated claims are in
[../history/entry-search-one-seed-negative.md](../history/entry-search-one-seed-negative.md).

## See also

- [clip-entry-search.md](clip-entry-search.md) - the residual, the acceptance window, and the
  wall-braced `old` this page leans on.
- [clip-lottery-draws.md](clip-lottery-draws.md) - counting draws honestly; the cell is the atom there
  too.
- [razor-prices-every-term.md](razor-prices-every-term.md) - rule 12 is this page's rule in its general
  form.
- [../mechanics/seam-clip.md](../mechanics/seam-clip.md) - what makes a cut segment genuine at all.
