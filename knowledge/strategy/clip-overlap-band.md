# A clip happens at a GRAZING touch, so "closer to contact" is not "more overlap"

**Answers:** My razor search reports its best candidate as the one with the most Co overlap - is deeper
contact closer to a clip? Where in overlap does a real clip actually sit? My pass did a billion razor
scorings and found nothing - how much of that was even in a region that could clip? Can I prefilter the
overlap cheaply instead of tracing every candidate through the roll?

**Status:** measured session 150 against the LOCKED console delivery
(`fixtures/courtyard_clip_s90_console.json`) and over 72000 razor scorings of the console herd's own fan.
It corrects a reporting defect in the first overnight pass, which ranked its own diagnosis on the maximum
overlap and therefore called a candidate 62 u past the clippable band its "closest". Gated in
[`tests/test_overnight_driver.py`](../../tests/test_overnight_driver.py) (the positive control plus the
band). Companion to [clip-lottery-draws.md](clip-lottery-draws.md), which counts a pass's draws; this
says which of those draws could ever have been a clip.

**Source:** `harness/tetrapush/overnight.py` (`CLIP_TARGET`, `CLIP_BAND`, `score`),
`harness/tetrapush/terminal.py` (`CO_R_SUM`, `RollFrame.overlaps`), `harness/tetrapush/handoff.py`
(`PairFrame.sweep`).

---

## The one clip that exists sits at overlap +1.2259

Overlap is `CO_R_SUM - |Link's Co centre - Tetra|` on the frame the cut consumes
(`terminal.RollFrame.rows`), so 0 is exactly touching and negative is a gap. The console's delivered
clip - the only genuine one in the repo - reads:

    overlap  +1.2258988956677968      resid  +6.242939e-05      push  (-0.5971, -0.1383)

A **grazing** touch, just over a unit of interpenetration. That is not a coincidence of one delivery: the
clip is the CC push steering the cut lunge through a seam gap, and the push is what a small overlap
produces. At large overlap the pair is resolved apart by the Co ejection before the cut, and the cut ray
leaves at an angle the seam does not admit - a different geometry, not a nearer one.

So the target is an INTERVAL, `CLIP_BAND = (0, 3)`, and a candidate at overlap +63 is 62 u PAST it. A
search that ranks on `max(overlap)` reports that candidate as its best and reads as though it were
closing in.

## Where a blind fan's scorings actually go: 96% cannot clip

The console herd's own item (walk 4), 6000 at-cap candidates x 12 configurations = 72000 scorings:

| overlap | scorings | share |
|---|---|---|
| -inf .. -20 | 2764 | 3.8% |
| -20 .. -5 | 66439 | **92.3%** |
| -5 .. 0 | 1274 | 1.8% |
| **0 .. 3** (the band) | **239** | **0.33%** |
| 3 .. 10 | 235 | 0.3% |
| 10 .. 30 | 454 | 0.6% |
| 30 .. +inf | 595 | 0.8% |

The roll travels ~161 u from its entry, so the endpoint's distance to her maps almost one-for-one onto
the final overlap - and a 3 u band out of a +-60 u spread is a few percent of the fan at best. Measured
it is a third of a percent.

**Consequence for how a pass is reported.** Its scoring count overstates its real coverage by ~400x, so
`band_draws` - the scorings that landed in the band - is the number to quote, and the residual is only
meaningful inside it (outside contact the razor's residual is a dead constant, ~-3.29e-01; see
[clip-lottery-draws.md](clip-lottery-draws.md)).

## And the band CANNOT be prefiltered off the baked schedule

The obvious optimisation is to predict the overlap for the price of a hypot -
`CO_R_SUM - |entry + co_centre_offset - tetra|` off `fast_schedule` - and spend the razor only on the
survivors. Measured on the console's own clip before shipping it:

    predicted   -38.50          exact   +1.2259          error   39.7 u

because **Tetra is PLOWED during the roll**: she moves from `(-1629.1018, -893.7962)` to
`(-1618.9520, -940.1720)`, 47 u, and toward Link's own end position. The overlap is a property of the
whole coupled roll - her plow, her brace, and both actors' `CrrPos` - not of the entry. A prefilter at
that error would have discarded the only known clip.

So the band is a MEASUREMENT and `ShoveCtx` is the only thing that decides. What can be aimed cheaply is
the fan's own geometry (which endpoints the walk reaches), never the verdict.
