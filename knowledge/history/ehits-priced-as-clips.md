# "E[hits] is the expected number of clips, so 0 genuine at E[hits] 1 is Poisson luck" (session 97, 2026-08-04)

> **status: historical** - this records an estimator read as counting clips when it counts a different
> event. The arithmetic in it reproduces exactly and is still quoted: E[hits] IS proportional to the
> distinct draw count, the uniformity premise IS satisfied, and the band widths ARE pinned to 1.26x.
> What was wrong is the event being counted - each draw was priced by the acceptance band of a station
> a median 20.9 u away, and the factor "does this draw's own station have any genuine dust" was taken
> to be 1 when it measures 0 of 100. Current truth is
> [strategy/clip-band-transfer.md](../strategy/clip-band-transfer.md). Kept for the lesson: an
> estimator can pass every check of its internal consistency and still be a count of the wrong thing.

## What was claimed (session 97)

Having measured both factors of the estimate - the uniformity of the residual population and the
ceiling on band width - the axis was declared priced, and the price was handed over as a budget
decision:

> When both factors are measured, a frontier is a single number: E[hits] ≈ 0.0026 per draw, a draw
> 28-104 s, **E[hits] 1 ≈ 1.0 h from 253 draws at the spread rate** - which is a budget decision an
> owner can take, rather than an axis argument a session can lose.

And the emptiness of the search was explicitly checked against the model and cleared:

> And the model is not in tension with the search's emptiness, which is worth checking rather than
> worrying about: 253 draws at E[hits] 0.65 with **0 genuine** is a Poisson P(0) of **0.52**. The most
> likely single outcome, not evidence that anything is broken.

## What was actually true

The reassurance was the load-bearing claim, and it is the one that broke. Session 98 bought 197 further
draws, taking the union to 450 and E[hits] to 1.0971 - still 0 genuine, which the Poisson reading scores
at P(0) = 0.33 and passes.

The population's first in-band draw arrived in the same buy: `window_gap` **0.0**, the only zero this
corner has produced. It is not genuine, bit-for-bit. Its band is real - 43 genuine samples - and belongs
to a station **14.52 u** away, while at the draw's own station there is no genuine dust at any residual.
Sampled across the union, that is not an outlier but the rule: **100 of 100** draws priced by a station
14.5-26.4 u off, **0 of 100** with dust at their own.

So the estimate omitted a factor rather than mis-measuring one, and folding it back in puts the
450-draw population at **≤ ~0.03 expected clips** against the 1.10 quoted. The emptiness was never
Poisson luck.

## The lesson

Every internal check this estimator was given, it passed - the residuals really are uniform, the widths
really are pinned, the draws really are distinct, and the ledger really does sum. None of them could
have caught this, because all of them ask whether the count is honest and none asks whether it is a
count of the right event.

The cheap test that would have: **audit the estimator's own realizations.** One draw landing inside its
band was enough to falsify the whole chain, and any pass that produced one could have been asked.
