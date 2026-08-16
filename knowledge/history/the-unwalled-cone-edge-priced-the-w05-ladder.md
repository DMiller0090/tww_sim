# "The turning row moves the walk-5 cone edge to 0.8 u off the stations" (sessions 167-168a, 2026-08-15)

> **status: historical** - the measurement was real but taken on the UNWALLED engine, and the walls
> are load-bearing exactly where the cone edge lives. s168c proved live that the console follows the
> walled timeline (a south-station walk braces Tetra at z=-940.2556 and the unwalled sim is 9.204 u
> off from frame 78), and the s168d walled re-measure put the same walk-5 cone edge **10.15 u** short
> of every station at every turning-row variant - the "0.83 u" (and the total-97 landing that priced
> it) never physically existed. The s169 fixed-stack re-probe then measured the whole ladder head:
> **w05 is unreachable ladder-wide** (rung08/rung10-w05 closest 41.13/33.79 u, rung05-w06 43.47 u,
> rung05-w07 10.80 u), and the alive set is rung06-w06 (2.31 u to a t14 station, total 98),
> rung06-w07 (0.01 u, contact overlap +8.2, total 99) and marginally rung08-w06 (6.61 u). Current
> truth: [strategy/cap-entry-conversion.md](../strategy/cap-entry-conversion.md); the s169 tables
> live in `_notes/s169_queue/s169_*.json`.

## What was claimed (s167 stage F, repeated in the s168a queue rank)

The herd's LAST row (still in the input pipe at herd end) is a free axis within the conversion
cone, and at rung06 it moved the measured walk-5 cone edge from 5.7 u off the station family to
0.83 u - so the rung06-w05 total-97 landing was reachable, and the queue was ranked
rung06-w05 (97) < rung08/rung10-w05 (98) < rung05 re-priced 98 at w6.

## The lesson

The turning-row mechanism itself SURVIVED the correction (on the walled engine it is worth ~14.6 u
of reach at rung06-w06: canonical (128,255) reaches 16.93 u from the t14 stations, the best variant
(56,160) reaches 2.31 u) - what died was every NUMBER measured on the unwalled timeline, because the
productive region at south-station items is precisely where the walk reaches a wall. A reach
measurement is only as true as the physics under the cone: re-measure the cone whenever the engine
gains a term, and treat any pre-fix table as a re-run queue, not evidence (the same lesson class as
the entry-frame recoil's fictional entries,
[../mechanics/entry-frame-recoil.md](../mechanics/entry-frame-recoil.md)).
