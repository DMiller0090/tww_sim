# "The speed prune is the biggest untouched lever" (session 81 -> 82, 2026-08-01)

> **status: historical** - this records a prune audit that was right about the modelling and wrong
> about the payoff: the prune WAS an assumption, generalizing it was correct, and the thousands of
> configurations it unlocked turned out to be dead. Current truth is
> [strategy/clip-lottery-draws.md](../strategy/clip-lottery-draws.md) and
> [strategy/clip-entry-search.md](../strategy/clip-entry-search.md). Kept for the lesson, which is
> that "this prune is an assumption" and "removing it buys draws" are two claims, not one.

## What was claimed (session 81)

Having found that 83% of the widest entry-search pass's draws sat at a dead body lean, the audit
turned to the fan's other prune. The fan kept only walk endpoints at the speedF 17 cap, because the
compiled roll schedule bakes that cap's own roll momentum (nspeed 26). A sub-cap walk still rolls, at
`clamp(1.5 * speedF + 0.5, 5, 26)`, so:

> Dropping the prune is **3.0x** the candidates (43610 against 14529) spanning **4146 distinct nspeed
> schedules, each its own locus and band**. That is the biggest untouched lever in the search and it is
> a schedule generalization, not a new mechanic.

It was named the next session's first job, ahead of the camera axis and the two-segment fan.

## What measurement changed (session 82)

The generalization itself held up completely, and is now current truth: the momentum is threaded
through the schedule, the entry step and the band key, and it is gated against a REAL sub-cap A-press
roll - the clamp bit-for-bit at five distinct momenta, the entry position 0-ULP, the reseed's nine
baked tables identical, and the cap-assuming schedule wrong in exactly `dx`/`dz`.

What did not hold up is the payoff. Each sub-cap momentum does bake its own locus; almost none of those
loci carry any genuine dust:

1. **The productive momentum window is the cap.** Sweeping nspeed from 17 to 26 at every reachable aim
   and thrust, **2 of 181** momenta are productive and both sit at the top of the range.
2. **The barren ones are barren along their WHOLE locus**, not just at the sampled point - marched
   station by station with a re-projection onto the residual zero at each, the cap lights 44 of 58
   stations and every sub-cap momentum reads 0 of ~60.
3. **The window did not merely move.** At nspeed 22.67, swept at 8 BAM over the entire 65536-facing
   circle, **nothing** is productive, while the same sweep at the cap finds its known window.
4. **The candidates are real and useless.** An uncapped fan reaches 42807 distinct momenta of which
   **4** lie in the productive sliver. End to end at one resolution: capped 14529 candidates -> 4
   near-misses; uncapped 43653 candidates (3.00x) -> **the same 4 near-misses, gap for gap.** The 29124
   extra candidates contributed exactly zero.

The physical reason is legible. A shorter roll is not the same clip started further back: below ~17 of
momentum the roll never reaches the wall brace that pins `old`, and in the middle of the range it
reaches it but leaves the pushed actor out of Co range on the cut frame, so the push is zero and no
entry has any leverage at all.

## The lesson

The session-81 audit asked the right question - *is this prune physics or an assumption I wrote?* - and
got the right answer. The error was in the sentence after it. An assumption-prune deletes
configurations; whether those configurations are LIVE is a separate measurement, and it is the cheap
one: a handful of band scans along the unlocked axis costs a minute and would have priced this lever at
zero before three hours of plumbing. Generalize the model anyway - the code is correct now and the
axis is closed by measurement rather than by an unexamined constant - but price an axis before
promoting it to "the biggest untouched lever".
