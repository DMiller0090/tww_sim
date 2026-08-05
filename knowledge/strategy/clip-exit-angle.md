# Steering a seam clip's EXIT ANGLE

**Answers:** The clip lands and Link goes out of bounds - now the DIRECTION he leaves in is worth
frames. Which quantity is the exit angle, and how finely can it be set? Can I steer where Link cuts
from? How wide is the facing window really, and what does it take to argue that a facing is dead?
**Status:** validated offline (sessions 92-93) on the flooded-Hyrule Tetra corner, against the
console-delivered clip in [`fixtures/courtyard_clip_s90_console.json`](../../fixtures/courtyard_clip_s90_console.json):
the cut-position pinning, the cell quantum, the two-lobe window and the per-budget frame cost are
measured. The second lobe is `ShoveCtx` dust that has NOT been cross-engine confirmed or delivered, and
session 93 measured that **no plan at the frame floor reaches it** - so at the objective's own budget the
axis is the first lobe. Gated in [`tests/test_entry_search.py`](../../tests/test_entry_search.py) and
[`tests/test_entry_reach.py`](../../tests/test_entry_reach.py).
**Source:** [`harness/tetrapush/entry_search.py`](../../harness/tetrapush/entry_search.py)
(`curve_seeds`/`curve_scan`, `aim_cell`, `resid_fn`) and
[`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py) (the reachable cloud);
[`fixtures/courtyard_facing_window_s92.json`](../../fixtures/courtyard_facing_window_s92.json) is the
measured window and
[`fixtures/courtyard_walk_hull_s93.json`](../../fixtures/courtyard_walk_hull_s93.json) the measured
reach.

A seam clip is usually asked one question - does Link go out of bounds - and the answer is a yes or a
no. Once he is out, a second question can be worth frames: **which way is he travelling?** On the
Courtyard corner that is worth about one frame downstream (the Deku Leaf), so the exit angle became an
objective term while the frame count was already at its floor.

This page is how to steer it, and what does *not* steer it. The search whose residual and window it
sits on top of is [clip-entry-search.md](clip-entry-search.md).

> **THE SIGN ON THIS PAGE IS THE OPPOSITE OF THE OBJECTIVE'S (Dereck, session 99).** Every "+BAM" and
> every "righter" below means an **increasing** facing, and the direction that is worth frames here is a
> **DECREASING** one - "more to the right should mean a roll facing angle LOWER than the one we currently
> have at 40841". So read this page's `+BAM` column as *away from* the prize. Sessions 91-99 optimised
> the increasing side on the strength of this labelling; re-scanned downward, cell **2551 (40820)** carries
> **220** reachable live stations at the frame floor against the delivered cell's 208
> ([clip-station-reachability.md](clip-station-reachability.md)), which is where the axis actually lives.
> The measured *geometry* on this page is unaffected - the window, the cell quantum, the frame table and
> the reachability results are all sign-free - it is only the labelling of which end is wanted.
> Superseded reading: [../history/exit-angle-sign.md](../history/exit-angle-sign.md).

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

- **the window is much wider than any contiguous reading gives**, and the cells in the second lobe are
  not even a trade against difficulty on their own terms: cell 2562 (+160 BAM, +0.879 deg) carries a
  band of 9.24e-05, **wider** than the delivered cell's own 6.28e-05, and cell 2561 (+144 BAM) 8.60e-05.
  What the window does *not* say is which of them a plan can reach - see
  [the frame cost](#what-a-cell-costs-in-frames) below, which is where most of this width goes.
- **the lunge grows to the right** (49.74 u at the delivered cell to 50.31 u at +288 BAM). "A longer
  lunge buys angle" is not a second lever to price separately; it is this same geometry, since a ray
  rotating away from the pinned position needs more length to still reach the vertex.

## What a cell costs in FRAMES

The window says which cells *can* clip. It does not say which ones a plan can *get to*, and on this
corner that is where the axis actually lives. The entry has to be walked to inside the frame budget, and
the budget is the whole constraint: the movement to clip out of bounds must cost **zero** frames against
the delivered plan, because the exit angle only buys about one downstream.

**A station is not reachable because it is near.** The stations above were found by sweeping
`reach_radius` - the walk cap times the frame budget plus the roll's own 26 u entry step, 94 u, as a
square box. That is the right conservative place to hunt a level curve and it is *not* the reachable set:
Link arrives at the speed cap on a fixed heading, so four held-stick frames reach a small curved cloud
whose bounding box is a fraction of that box's area. Measure the cloud instead - the fan already
enumerates it, so its convex hull is a few lines ([`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py)),
and keep the test asymmetric: a hull taken off a coarse stick alphabet proves *outside* and only
suggests inside.

Measured per frame budget, as the closest any candidate gets to the residual zero (the acceptance band
is ~1e-4 wide, so a budget is only interesting once this is comparable):

| cell | +BAM | <=4 frames | <=5 | <=6 | <=7 |
|---|---|---|---|---|---|
| 2552 (delivered) | 0 | 1.3e-03 | 1.3e-03 | 9.1e-05 | 9.1e-05 |
| 2553 | +9 | 1.1e-02 | 2.3e-05 | 2.3e-05 | 2.3e-05 |
| 2561 | +149 | **0.354** | 2.6e-03 | 8.9e-04 | 2.6e-05 |
| 2562 | +154 | **0.430** | 2.2e-03 | 9.6e-04 | 4.9e-05 |
| 2570 | +284 | **1.038, one sign** | 6.2e-02 | 4.7e-03 | 4.7e-03 |
| 2581 | +455 | **1.873, one sign** | 1.0e-01 | 3.4e-03 | 2.6e-03 |

Read the bold column: at the frame floor the second lobe is **not reachable**. Those approaches are 71x
to 375x outside the ~5e-3 probe a search calls a near-miss, and for cells 2570 and right the residual
does not even change sign over the cloud. A frame-capped pass over all nine aimable second-lobe cells -
**779130 candidates, 7.01 M evaluations** - returned **0 genuine, 0 near, 0 dead-tail**. Each extra frame
buys about an order of magnitude of approach, so the lobe becomes a live lottery at 5-7 frames: three
frames for +0.85 deg, when the budget is zero frames for ~1.

**Read the 2553 row the same way, and note which axis it is a row of.** Its ≤4-frame entry (1.1e-02, 400x
outside its band) is not a resolution the later lean and camera axes improved on: they moved the residual
*number* nearer a band whose station no 4-frame plan reaches. Scanned over the measured hull instead, this
whole table's **thrust** is the axis that matters - cell 2553 carries no reachable dust at thrust 15 (0
live over 12823 in-hull stations) and **918 live stations at thrust 14, at the same 4 frames**, which
costs no frame at all. The table is not wrong; it was read as a statement about cells when it is a
statement about one configuration of them. See
[clip-station-reachability.md](clip-station-reachability.md).

Be careful what a sign census licenses. `resid`'s gradient is ~1.2 per unit and the cloud is ~60 u
across, so it spans +-70 in there; "both signs appear" (cells 2561/2562, 2.7% negative) says a boundary is
inside the sampled set, **not** that a zero a plan can land on is.

**Rule out the density explanation by measuring it, not by arguing it.** Ask the same question at two fan
densities - 157291 candidates and 2888346, an 18.4x buy. Cells 2561/2562 come back **bit-identical**
(0.35417 and 0.430095, the same f64, at the same argmin entry in both fans) while cell 2553 sharpens
**37x** on exactly that extra density, to **4.45e-05** - inside its own band width. A fan that resolves
one cell by 37x and another by nothing is not short of resolution at the second one.

And the reach measurement agrees without being told: asked which of the 40 productive configurations have
a station a 4-frame plan can put the entry on, the hull answers **cells 2551 and 2552 only** - exactly
where the whole 55-candidate console-delivered population sits, arrived at from walk endpoints and a
frame budget with no residual in sight. The 4-frame cloud is 447581 endpoints in a 58.6 x 63.8 u bounding
box, about **11%** of the area of the 188 u box `reach_radius` implies, and all four corners of that
bounding box are outside the hull - the cloud is a curved sliver, not a filled square.

Read the signed distances before trusting a verdict, though, because they say how marginal it is
(+ inside): the three delivered-cell stations sit **+1.6 to +1.8 u** inside, the second lobe **-10 to
-95 u** outside, and the cell next door **only -2.26 u**. The far verdict is not marginal; the near one
is inside the hull's own resolution, since it was swept at a coarse stride and a finer alphabet grows the
hull. A station is also one point on a curve, so "this station is out of reach" is never "this cell is".

So the axis at the floor is the **first lobe**, and its open question is cell 2553 (+9 BAM, the nearest cell
right of the delivered one). A pass there is *not* short of candidates - it puts **180**
inside the probe - but every one lands at a lean whose band has no usable width, so the target is a
single f32 value. That is the same situation the delivered cell was in at its own lean (width 0.0, 20
genuine samples) and it was won by population, so the next lever is the **lean**: the band is jagged in
`m351C`, the qualification runs at lean 0, and the fan carries ~1040 distinct entry leans. Measure the
band across the leans the fan actually arrives on, and aim at (lean, cell) pairs rather than at cells.

So the honest statement of the axis at the floor is the **first lobe**, and the open question there is
cell 2553 (+9 BAM, the nearest cell right of the delivered one) - which no pass has landed a
plan on either, the whole delivered 55-candidate population sitting at cells 2551/2552. The superseded
pricing is in
[../history/exit-angle-priced-without-its-frame-cost.md](../history/exit-angle-priced-without-its-frame-cost.md).

## The camera axis REOPENS when the window is wide

`csangle` shifts the whole aim alphabet, so it decides which cells a frozen camera can aim at. It was
priced at **zero** and closed - correctly, against a 2-cell window the frozen aims already covered
([../history/entry-search-s81-camera-lever.md](../history/entry-search-s81-camera-lever.md)). Against a
22-cell window it is a live lever again: of the live cells above, six (2550, 2560, 2563, 2565,
2566, 2571) are **not aimable** at the frozen camera, and one of them is the rightmost cell with a workable
band. Re-derive what the camera reaches whenever the window's width changes; a closure is only as
current as the window it was measured against.

The camera's bigger reach turned out to be on the **walk** side rather than the aim side, and it is free
in frames - the entry plan's C-stick is idle on every console frame. See
[clip-camera-axis.md](clip-camera-axis.md), which also carries the constraint this section's vocabulary
supplies: a camera draw only counts for a cell that is still **aimable** at that camera's dispatch
csangle (cell 2553 survives at 64 of 82 camera draws).

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
- [../history/exit-angle-priced-without-its-frame-cost.md](../history/exit-angle-priced-without-its-frame-cost.md) -
  the second lobe priced as available before its frame cost was measured.
- [clip-lottery-draws.md](clip-lottery-draws.md) - counting draws honestly; the cell is the atom there
  too.
- [razor-prices-every-term.md](razor-prices-every-term.md) - rule 12 is this page's rule in its general
  form.
- [../mechanics/seam-clip.md](../mechanics/seam-clip.md) - what makes a cut segment genuine at all.
