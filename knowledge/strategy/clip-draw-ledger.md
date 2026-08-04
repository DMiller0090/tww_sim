# Pricing a search axis ACROSS passes - the draw ledger, and how a saturating axis reads

**Answers:** My new pass reports a better draw rate than the last one - is it finding new tickets or
re-drawing the ones I hold? How do I tell a saturating axis from a productive one before I spend an hour
on it? My axis has a supply table of thousands - why does it stop paying long before that? Is E[hits]
really proportional to my draw count?
**Status:** validated offline (session 97) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_entry_ledger.py`](../../tests/test_entry_ledger.py) against the locked extract
[`fixtures/courtyard_draw_ledger_s97.json`](../../fixtures/courtyard_draw_ledger_s97.json). Measured on
the session 95/96 cell-2553 camera passes: a local camera neighbourhood reported **0.127 draws/s** and
delivered **6 new draws of 31 (0.0245/s)**, which inverts the ranking that pass was used to justify.
**Source:** [`harness/tetrapush/entry_ledger.py`](../../harness/tetrapush/entry_ledger.py)
(`Ledger`, `novel`, `accumulation`, `uniformity`).

[clip-lottery-draws.md](clip-lottery-draws.md) makes one pass's count honest - what a draw is, and why
118 scorings can be 23 of them. This page is the level above it: **two passes, each honest inside
itself, whose populations overlap.** That is where a lottery search stops being able to read its own
progress, and it is the fourth time this corner has counted copies as discoveries.

## The currency is NEW draws, because that is the only thing E[hits] adds over

E[hits] is a sum over draws, each priced at its own band width
([clip-band-per-lean.md](clip-band-per-lean.md)). A sum is additive only over terms nothing before it
contributed, so a second pass's E[hits] can be added to the first's **only after removing the draws the
first already made**. Keep a ledger of draw identities (`entry_score.draw_key`: the walk endpoint, the
entry lean, the momentum, the configuration) and price each pass against it in run order.

Measured, on three shapes at one scope - cell 2553, thrust 15, the frame floor:

| where the clock went | draws | NEW | seconds | reported /s | **new /s** |
|---|---|---|---|---|---|
| the whole camera alphabet, byte stride 16 (196 clouds) | 127 | 127 | 1462 | 0.087 | *opening pass* |
| a local camera neighbourhood (±8 bytes, stride 2, 35 clouds) | 31 | **6** | 245 | 0.127 | **0.0245** |
| one camera at the paying plan shape (3.20 M candidates) | 40 | **29** | 880 | 0.045 | **0.0329** |
| the paying shape at a second camera, 78 BAM out (3.18 M) | 40 | **10** | 861 | 0.046 | **0.0116** |
| the paying shape at a third camera, 344 BAM out (3.18 M) | 40 | **31** | 871 | 0.046 | **0.0356** |

The published ranking was `0.127 > 0.087 > 0.045`, and the instruction that came out of it was *buy the
neighbourhood, skip the paying-shape product.* In the currency the estimate is additive in, the order
**reverses** and the three collapse to within 35% of one another. The pass that was told to be skipped
is the one to buy.

**The last two rows are the same lesson landing on the corrected number, and then the rule that comes out
of it.** Having ranked the paying shape first at 0.0329, buying it at a second camera returned 10 new of
40 - 0.0116/s, 2.8x worse. The 29 of 40 was never a camera-vs-camera measurement: that pass was the first
of its shape on this scope, so its newness was *density* against the bounded passes before it. A ledger row
is only as general as the comparison that produced it, so **the first pass of a new shape over-reports the
shape** exactly as the first pass into a ledger over-reports the axis.

## What actually predicts newness: distance from what you already bought

The third row is 3x the second on an identical shape and clock. What separates them is not the camera's own
merit - it is how far the camera sits from the cameras whose draws are already held, measured in the walk
BAM offset the camera delivers:

| pass | BAM from the already-bought camera | new share |
|---|---|---|
| the ±8-byte neighbourhood around it | tens | **19%** (6/31) |
| a camera 78 BAM out | 78 | **25%** (10/40) |
| a camera 344 BAM out | 344 | **78%** (31/40) |

Monotone across three passes, and it unifies them: the neighbourhood negative and the buy are one
phenomenon seen from the input side. Neighbouring cameras command nearly the same walk directions, so they
reach the same entries; separated cameras command different ones.

So the spending rule on a camera-like axis is **spread, not cluster** - the exact opposite of the
"densify around the winners" instruction this measurement replaced. Two cautions on how far to push it:
the third camera also sits at the *extreme* of the camera's reach, so "far from what is bought" and "far
from centre" are not separated by three points; and a bounded pass's own draw count did **not** predict
newness at all (it ranked the 25% camera above the 78% one). Rank candidate cameras by distance from the
ledger, not by their own yield.

**A local neighbourhood is enriched in its PARENT's draws.** Neighbouring cameras command ~94% of the
same walk directions, so they reach the same entries: 25 of those 31 draws are ticket stubs already in
the drawer, and 12 of the 35 clouds reach the record endpoint itself. Nothing about the 0.127 was
mis-measured - it is a real count of a real population, priced against itself.

## The saturation curve is the diagnostic, and it is free

Whether an axis is exhausted is not a question about the closest approach, and it does not need a new
pass. Take the per-camera draw sets a finished pass already wrote and accumulate them over **random
orderings** of the cameras (a fan enumerates x-major, so the file's own order measures the order, not
the axis - the same caveat `_marginal` carries):

| cameras spent | distinct draws | per camera |
|---|---|---|
| 1 | 4.3 | 4.30 |
| 10 | 27.7 | 2.77 |
| 50 | 72.2 | 1.44 |
| 100 | 99.0 | 0.99 |
| 196 | 127.0 | 0.648 |

The marginal yield falls **~4.3 → 0.23 draws per camera, an 18x decay**. That is the coupon-collector
shape of sampling a population far smaller than the sample count; an axis whose cameras drew
independently would hold the rate flat. So:

- **a supply table bounds TICKETS, not draws.** The camera channel really does have 196 / 709 / 2394 /
  5300 distinct clouds at byte stride 16 / 8 / 4 / 2 ([clip-camera-supply.md](clip-camera-supply.md)),
  and the draws stop arriving long before the clouds run out.
- **the average rate of a completed sweep is not repeatable.** 0.087 draws/s over 196 cameras ends at
  0.031/s, and that end rate - not the average - is what a next pass costs. Quoting the average is how
  a 50-minute budget turned out to be a two-hour one.
- **the shapes converge, and the spread is the one thing that still moves the rate.** 0.0245, 0.031,
  0.0116 clustered against 0.0356 spread: a new draw costs **28 to 86 s**, and the cheap end is reached by
  placing cameras far from the ledger rather than by any change of shape. That is the honest frontier
  statement, and it is what makes the axis's price legible instead of a per-session argument.

## Check the premise E[hits] rests on - the population tests it for free

`lottery` prices a draw at `width / (2 · near_gap)` because its residual is taken to be locally
**uniform** across the window. That is an assumption, and a finished pass can test it: count the draws
under each gap threshold against what uniformity predicts.

| gap < | observed | uniform expects | ratio |
|---|---|---|---|
| 1e-5 | 1 | 0.25 | 3.94 |
| 1e-4 | 3 | 2.54 | 1.18 |
| 1e-3 | 27 | 25.40 | 1.06 |
| 3e-3 | 76 | 76.20 | 1.00 |

It holds. There is no crowding toward zero waiting to be harvested and no avoidance of it making the
estimate a fiction, so **E[hits] really is proportional to the distinct draw count** and buying draws is
the only thing that moves it. The one row that is not 1.0 is the single best draw at the deepest
threshold - which is what one order statistic out of 127 uniform draws looks like about a tenth of the
time, and is the distributional form of "a record is not a trend"
([clip-search-budget.md](clip-search-budget.md#a-record-is-not-a-trend)).

Worth pairing with the other factor, so the arithmetic is closed rather than half-open: the band widths
here are nearly pinned. The draws land at 2.61e-05 and 2.81e-05 and the widest band any lean carries at
this cell is 3.25e-05, so perfect lean steering is worth **1.26x**. When both factors are measured, a
frontier is a single number: E[hits] ≈ 0.0026 per draw, a draw 28-86 s, **E[hits] 1 ≈ 1.4 h from 203 draws
at the spread rate** - which is a budget decision an owner can take, rather than an axis argument a
session can lose.

## The trap: a ledger's opening pass is 100% new by construction

The first pass into an empty ledger reports a 100% new share and its full rate, whatever it measured,
because nothing preceded it. Quoting *that* as the price of the next pass is the mistake in its purest
arithmetic form, and it is worth a guard rather than a habit: `Ledger.price` reports a marginal rate
over the passes that actually faced a non-empty ledger, and `None` when there are none.

The same shape, one level down, is what produced the 0.157 draws/s a whole session was budgeted at: a
rate measured on a population that had not been compared to anything
([../history/entry-search-s95-segmented-cameras.md](../history/entry-search-s95-segmented-cameras.md)).

## Make the extract tracked, or the finding is not reproducible

A pass writes to the gitignored `_generated/`, so a claim argued off one cannot be re-run from a clone -
and every number on this page is a claim about two passes' overlap. Reduce the populations to what the
arithmetic consumes (`entry_ledger.extract`: source, camera, gap, and the `draw_key` fields plus the
width) and lock that. 1025 rows is 280 KB and it re-derives the ledger, the curve and the uniformity
check exactly.

## The rule

**Price a pass against the draws you already hold, never against its own population** - and when a new
shape reports a better rate, the first question is what share of it is new. The corollaries:

- an axis's *end* rate is its price, not its average, and a **shape's** first pass over-reports the shape
  for the same reason a ledger's first pass over-reports the axis;
- what predicts a pass's newness is its **distance from the ledger**, not its own prior yield - so spread
  the buys and rank candidates by that distance;
- enrichment can be local and still be worthless, because a neighbourhood's enrichment is in its
  parent's draws;
- a supply count is an upper bound on tickets and says nothing about draws;
- and when a lottery's two factors are both measured, stop arguing about the axis and quote the hours.

## See also

- [clip-lottery-draws.md](clip-lottery-draws.md) - what ONE draw is; this page is the same discipline
  one level up, across passes instead of inside one.
- [clip-search-budget.md](clip-search-budget.md) - rates per plan shape, and why a record is not a trend.
- [clip-camera-supply.md](clip-camera-supply.md) - the ticket count this page bounds the draws against.
- [clip-band-per-lean.md](clip-band-per-lean.md) - where a draw's width comes from, i.e. the other
  factor in E[hits].
- [../history/camera-neighbourhood-enrichment.md](../history/camera-neighbourhood-enrichment.md) - the
  superseded ranking, and the measurements inside it that stand.
- [razor-prices-every-term.md](razor-prices-every-term.md) - rule 15 and its corollaries; this page is
  the currency half of them.
