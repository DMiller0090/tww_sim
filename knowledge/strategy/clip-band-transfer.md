# The band a draw is priced with was measured SOMEWHERE ELSE

**Answers:** My lottery estimate says E[hits] 1 and my search is empty - is that bad luck or a broken
estimate? What exactly is the "hit" my E[hits] counts? A candidate scored a perfect zero gap and did
not clip - how?
**Status:** validated offline (session 98) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_band_transfer.py`](../../tests/test_band_transfer.py). Measured on the 450-draw union of
the session 95-98 cell-2553 passes.
**Source:** [`harness/tetrapush/entry_score.py`](../../harness/tetrapush/entry_score.py) (`BandTable`,
`stream_search`, `lottery`) and
[`harness/tetrapush/entry_search.py`](../../harness/tetrapush/entry_search.py)
(`configuration_band`, `curve_scan`, `window_gap`).

[clip-lottery-draws.md](clip-lottery-draws.md) makes one pass's draw count honest.
[clip-draw-ledger.md](clip-draw-ledger.md) makes a second pass honest against the first. Both are
about the *count*. This page is about the *price* each counted draw is given - and it is the level
where the previous four corrections were spending their honesty.

## The event E[hits] counts is not "a clip"

`lottery` prices a draw at `width / (2 · near_gap)`: the chance its residual lands inside its
acceptance band. `BandTable` supplies that band, keyed on `(facing, thrust, lean, nspeed)` and reused
for every candidate carrying the key. The band itself comes from `configuration_band`, which Newtons an
entry onto the residual zero **from a seed** and sweeps across the locus there.

Since session 94 that seed may be `curve_scan`, which marches ALONG the locus until it finds a station
with genuine dust. That was a real fix for real false negatives - it is why this cell has a priced
population at all ([clip-band-per-lean.md](clip-band-per-lean.md)). What it introduced, and what
nobody stated, is a **transfer assumption**: the width belongs to a station the draw is not standing at.

Measured over 100 draws sampled from the 450-draw union:

| | |
|---|---|
| priced by the `curve` rung | **100 of 100** |
| distance from the draw to its band's station | **14.5 - 26.4 u**, median **20.9** |
| draws whose own station has any genuine dust | **0 of 100** |

The own-station test sweeps ±0.006 u across the locus against a gradient of ~0.167 per u - a residual
range about **35x the band's own width** - so "no genuine on the residual zero" there is a measurement
and not a resolution artifact. For context on the scale: a 4-frame plan's entire reachable entry cloud
is about 59 x 64 u, so a 21 u offset is a large fraction of the whole search space.

So the estimate is a product of two factors and only one of them was ever computed:

    P(draw clips) = P(its own station has dust) · P(its residual lands in that station's band)

`lottery` computes the second using a foreign station's width, and silently takes the first to be 1.
Measured, the first is **0 of 100** - a 95% upper bound of ~3%.

## The one time the predicted event fired, it did not clip

This is not only an argument from a missing factor. Across 450 draws E[hits] reached **1.0971**, and
exactly one draw landed inside its own quoted band - `window_gap` **0.0**, the only zero this corner has
produced in four sessions of passes. So the event was realized about as often as predicted.

It is **not genuine**, reproducibly and bit-for-bit: same entry, residual `1.5499e-04` to the ULP, and
the engine's ground-truth flag says no. Its band is real (43 genuine samples, width 2.81e-05) and sits
at a station **14.52 u** away; at the draw's own station `configuration_band` returns `productive=False,
'no genuine on the residual zero'`.

**A zero gap is therefore not a near-clip. It is a residual that would have been genuine somewhere
else.**

## What this costs, in the currency the search is spent in

Fold the measured first factor back in and the 450-draw population is worth **≤ ~0.03 expected clips**,
not 1.10. It retires the reassurance that the emptiness was luck: 450 draws at a true expectation near
0.03 is not a Poisson coin that came up tails; it is a search whose near-miss population was never near.
The superseded framing is in
[../history/ehits-priced-as-clips.md](../history/ehits-priced-as-clips.md).

**The remaining factor is not a small rate - for the population that was bought it is zero**, and the
reason is a scope error: those stations sit 10-19 u **outside the set a frame-floor plan can reach**, so
no amount of buying converts these draws. Measured over the reachable set instead, the same cell carries
**918** live stations at a different thrust - so the factor is 0 where it was being spent and 0.0711 one
configuration away. Both are [clip-station-reachability.md](clip-station-reachability.md), which also
retires the compute price this page first quoted the missing factor as
([../history/ehits-ninety-hour-axis.md](../history/ehits-ninety-hour-axis.md)).

## The rule

**Check that a measurement is taken where it is applied, not merely that it is a real measurement.**
Every number in this chain was true of something: the band's 43 genuine samples are real, the widths are
real, the uniformity check is real. The error is entirely in the distance between where each was taken
and where it was spent - and it survived four corrections because each of those asked whether a count
was honest, never whether it was a count of the right thing.

The corollaries this corner paid for:

- **a fix for false negatives can manufacture false positives**, and the escalation that finds a band
  further away is exactly such a fix - so when a search stops discarding candidates, re-ask what the
  surviving ones now mean;
- **an estimator needs its own realization audited.** One in-band draw was enough to falsify the chain,
  and it had been derivable from any pass that produced one;
- **quote the event, not the number.** "E[hits] 1.1" reads as one clip; "1.1 draws expected to land in
  the acceptance interval of a station ~21 u away" is the same arithmetic and nobody would have
  budgeted an hour against it.

## See also

- [clip-band-per-lean.md](clip-band-per-lean.md) - where a band comes from and why it is per-lean; this
  page is the station axis that page's key does not carry.
- [clip-draw-ledger.md](clip-draw-ledger.md) - counting draws honestly ACROSS passes, the correction one
  level below this one.
- [clip-lottery-draws.md](clip-lottery-draws.md) - what one draw is.
- [razor-prices-every-term.md](razor-prices-every-term.md) - the general form: every term gets priced,
  including the ones that look like bookkeeping.
