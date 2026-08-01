# "The fan is the only remaining budget" (session 80 -> 81, 2026-08-01)

> **status: historical** - this records a search-sizing conclusion that was arithmetically right on the
> population it measured and wrong about which population that was, plus a saturation claim that was
> never measured. Current truth is [strategy/clip-lottery-draws.md](../strategy/clip-lottery-draws.md)
> and [strategy/clip-entry-search.md](../strategy/clip-entry-search.md). Kept for the lesson, which is
> about auditing a search's own accounting before scaling it.

## What was claimed (session 80)

Having corrected the entry convention and opened the aim/thrust alphabets, the roll-entry search was
qualified and run wide: 43596 candidates against the 6 (of 243) configurations that admitted a genuine
locus, 72 near-misses, 0 genuine, and

1. **"The eval is no longer the budget; the FAN is."** At ~3.5k Python coupled steps/s the widest pass
   spent 1444 s fanning and 11 s evaluating, so the named next step was to move the fan onto the native
   fleet and then spend the throughput on multi-segment holds.
2. **"Stride and base frames are exhausted"** - stride 1 saturates and base nodes past the 7th add
   nothing, so hold length was not on the list of levers.
3. **"72 near-misses over 262k evaluations is an expected 0.23 hits"**, hence "roughly 50x more
   candidates is what a confident hit needs."

## What measurement changed (session 81)

The fan did move to the fleet, and it worked: 43596 candidates in **17 s** instead of 1444, key-for-key
bit-identical to the Python pass. What that throughput then bought was the discovery that the fan had
never been the binding constraint.

1. **83% of those draws were dead.** The acceptance band is a function of the roll's body **lean** as
   well as its facing and thrust; session 80 measured bands at lean 0 and scored every candidate
   against them, but a large share of leans admit nothing genuine at any entry whatsoever. Recounted
   per (facing, thrust, lean), the same widest pass has **6** near-misses, not 72, and an expected
   **0.02** hits, not 0.23. The requirement was never 50x - it was ~250x, and buying it in candidates
   alone was the wrong plan.
2. **Hold length was not saturated, and saturating it bought nothing anyway.** Sweeping it out to
   exhaustion took the fan from 43596 to 69169 candidates (1.6x) and produced **exactly zero** extra
   near-misses: the extra candidates are longer walks, which go past the locus. So claim 2 was both
   wrong (the axis had room) and right in effect (the room was worthless) - for a reason the raw
   candidate count could never show.
3. **"6 of 243 configurations" was a property of the sampling, not the geometry.** Swept directly at
   1 BAM, the productive facing window is 32 consecutive facings wide; the frozen camera's aim alphabet
   just lands only four aims inside it. The camera is therefore a real multiplier on loci and not a
   footnote.
4. **One of the fan's two prunes was self-inflicted.** Keeping only walk-cap endpoints follows from the
   compiled schedule baking the cap's roll momentum, not from physics: sub-cap walks still roll, 3x more
   endpoints qualify, and they span thousands of distinct schedules - each its own locus.

## The lesson

A "N near-misses, 0 genuine" pass invites exactly one question - *is it too small?* - and answering it
by scaling the biggest cost centre skips the cheaper question: **is every near-miss a draw that could
have converted?** Audit the accounting first. Here the audit cost minutes, moved the estimate 12x, and
redirected the whole search: away from more candidates, towards the configuration axes (lean, camera)
and the prune that had been quietly deleting thousands of loci.
