# "Further to Link's RIGHT means an increasing roll facing" (sessions 91-99, 2026-07-25 to 2026-08-05)

> **status: historical** - this records a sign, not a measurement. Everything sessions 91-99 measured
> about the exit angle stands: the variable is `travel` (= `facing` through the roll), its atom is the
> sine-table cell, the live window is two lobes, the per-frame reach table is real, and the
> reachable-station census is real. What was wrong is which END of that axis the objective wants.
> Dereck, session 99: *"more to the right should mean a roll angle facing angle LOWER than the one we
> currently have at 40841."* Current truth is
> [strategy/clip-exit-angle.md](../strategy/clip-exit-angle.md) (whose header now states the inversion)
> and [strategy/clip-station-reachability.md](../strategy/clip-station-reachability.md). Kept for the
> lesson: a direction is a convention, and a convention nobody restated became nine sessions of search
> scope.

## What was claimed

`clip-exit-angle.md` opened the axis with the objective as "as far to Link's RIGHT as possible" and then
tabulated candidate cells with a **`+BAM`** column that increases with the facing:

> | cell | +BAM | <=4 frames | ... |
> | 2552 (delivered) | 0 | ... |
> | 2553 | +9 | ... |
> | 2561 | +149 | ... |
> | 2581 | +455 | ... |

Every pass from session 91 on took the positive column as the prize. Session 94 exhausted the family axis
at cell 2553; sessions 95-98 bought ~450 camera draws at it; session 99 spent 98.2 M candidates on it,
swept every cell from 2553 to 2581 at three thrusts, and priced a ~1000 h lottery for the +9 BAM.

## What was actually true

The objective wants the facing to go DOWN from 40841, not up. Re-scanned in that direction over the
measured frame-floor hull, the low side is the productive one:

| cell | facing | vs delivered | live stations at the frame floor |
|---|---|---|---|
| 2552 (delivered) | 40841 | - | 208 (thrust 15) |
| **2551** | 40820 | **0.115 deg right** | **220** (thrust 15) |
| 2549 | 40795 | 0.25 deg | 10 (thrust 14) |
| 2525 / 2532 / 2533 | 40400-40529 | 1.7-2.4 deg | 1 each (plateau bands) |

Cell 2551 - one cell the *other* way - carries more reachable dust than the cell the console clip was
delivered at, and a genuine 4-frame clip was found, confirmed and cross-engine-agreed there within three
camera passes. The increasing side, by contrast, never produced a single genuine candidate in 98.2 M.

## The lesson

The number was never wrong; the arrow on it was, and nothing in the page or the code ever wrote the arrow
down in a form that could be checked. Two guards would have caught it:

- **state a direction against a fixed landmark, not a hand.** "Right" needs a frame of reference nobody
  agreed on; "facing below 40841" does not.
- **when an axis produces nothing across many sessions, re-derive its SIGN before buying more of it.**
  The emptiness on the increasing side was information about the direction, and it was read every time as
  information about the budget.
