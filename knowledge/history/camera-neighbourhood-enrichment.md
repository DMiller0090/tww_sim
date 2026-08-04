# "The neighbourhood of a productive camera is enriched 1.46x, so spend the axis locally" (session 96, 2026-08-04)

> **status: historical** - this records a three-way axis ranking priced in the wrong currency. Every
> measurement in it reproduces and is still quoted; what was wrong is what the numbers were read to
> mean, because each pass was priced against its OWN population instead of against the draws already
> held. Current truth is [strategy/clip-draw-ledger.md](../strategy/clip-draw-ledger.md) (price a pass
> in NEW draws; the ranking inverts and the three shapes collapse to within 35%). The half of the
> section that stands - a record is not a trend - is still in
> [strategy/clip-search-budget.md](../strategy/clip-search-budget.md#a-record-is-not-a-trend). Kept for
> the lesson: an axis's local enrichment can be entirely enrichment in the parent pass's draws.

## What was claimed (session 96)

Three shapes had been run on one scope (cell 2553, thrust 15, the frame floor), and the ranking was
taken to be the budget decision:

| where the clock goes | draws/s | draws per camera |
|---|---|---|
| a local camera neighbourhood (±8 bytes, stride 2, 35 clouds) | **0.127** | 0.886 |
| the whole camera alphabet at byte stride 16 (196 clouds) | 0.087 | 0.648 |
| one camera at the paying plan shape (3.20 M candidates) | 0.045 | - |

Two readings came out of it. That **the breadth axis thins as it densifies** - draws per camera falling
1.11 → 0.648 - so a supply count bounds tickets rather than draws and a finer global stride overlaps the
sweep before it. And that **the neighbourhood of a productive draw is enriched**, 1.46x the rate, so the
cheap spend is local density around the winners. The handoff instructed the next session to rank the 196
clouds by draws, take the top ten, and run a ±8-byte stride-2 neighbourhood around each - budgeted at
E[hits] ~1 in about 50 minutes - and explicitly not to buy the camera × paying-shape product.

## What was actually true

The first reading stands and is now sharper: the axis saturates, and the marginal yield falls ~4.3 → 0.23
draws per camera across the 196-camera pass.

The second inverts. Priced against the population it was run after, the neighbourhood's 31 draws are
**6 new** - 0.0245 new draws/s - while the paying-shape product's 40 are **29 new**, 0.0329/s. The
neighbourhood is enriched, and what it is enriched in is the *parent pass's own draws*: neighbouring
cameras command ~94% of the same walk directions, so they reach the same entries, and 12 of the 35 clouds
reach the record endpoint itself. The recommended buy was the worst of the three and the forbidden one
was the best, and the ~50-minute budget was a two-hour one.

Nothing was mis-measured. 0.127 draws/s is a true count of a true population; it is just not a rate at
which anything can be bought, because a pass priced against itself cannot see an overlap it does not
look for.

## The lesson

**Local enrichment is not the same as local supply.** When a region of an axis looks denser in results,
ask what share of those results the rest of the axis already produced - the answer can be nearly all of
it, and it will be exactly where the previous pass did best, because that is where the neighbourhood was
centred.

Its companion, and the reason the error was invisible: the tooling was honest at every level it had been
taught about. `dedupe_near` makes a pass's own count honest, and `entry_camera.summarize` explicitly
refuses to sum `expected_hits` across the cameras *inside* one pass, warning that it would double-count
the overlap. Then the session summed across passes. **When a guard exists at one boundary, ask whether
the boundary above it needs the same guard** - that is now `entry_ledger`.
