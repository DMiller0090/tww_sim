# The entry search's two superseded premises (session 79 -> 80, 2026-08-01)

> **status: historical** - this records two measurements that were RIGHT about their own arithmetic
> and WRONG about the roll they were measuring, and how a fidelity gate corrected them. Current truth
> is [strategy/clip-entry-search.md](../strategy/clip-entry-search.md). Kept for the lesson, which is
> about *when* to run the fidelity gate, not about these particular numbers.

## What was claimed (session 79)

Solving for Link's roll ENTRY against a pinned pushed actor was set up, gated, and run. Two of its
premises turned out to be about a roll nobody performs:

1. **"The candidate entry is where the walk leaves Link."** The fan collected Link's position at the
   end of each walk frame and fed it to the compiled context as the roll's starting point.
2. **"The realizable facing alphabet is only six wide at a frozen camera."** The aims were enumerated
   from the saturated stick set (`reachable_stick_fan(msd_min=1.0)`, the octagon boundary), giving six
   facings inside the seam window, and the conclusion that widening the alphabet needed the C-stick.

Together these sized the lottery at ~0.4 expected hits from 3699 candidates against six loci, and the
pass returned zero, which matched. The diagnosis ("the pass is ~10x too small, not mis-aimed") was
correct arithmetic on the wrong population.

## Why they were wrong (session 80, measured)

Both fell out of the one gate session 79 left open: *is a real A-press roll out of a walk the roll the
sweep scores?* Running it (a real walk + A-press in the walled coupled engine, diffed per frame
against the reseeded schedule) answered yes for the schedule and no for the seeding.

1. **The reseed's step 0 is the roll's SECOND frame.** A reseeded `FRONT_ROLL` advances its animation
   frame control on its first step; a real roll's ENTRY frame does not. So the position the context
   wants is the one at the *end* of the entry frame, one full roll step (**26 u**) past the walk
   endpoint. Feeding the walk endpoint scored every candidate at a place Link never rolls from. The
   pre-entry-frame reading is not merely offset: it mismatches the pose-chain tables outright, which
   is how the convention got decided rather than assumed.
   The consequence is bigger than the correction: the step is taken along the **aim**, so each aim
   contributes its own entry as well as its own locus.
2. **The magnitude floor was not physical.** A roll takes its whole speed from the walk cap
   (`clamp(speedF*1.5 + 0.5)`), and `_roll_init` snaps facing to the latched stick target whatever the
   deflection is, so an aim needs no magnitude at all. The alphabet is the entire decoded-angle grid:
   **81** facings in the seam window, not 6, and every one of them, fired and read back, rolls at the
   facing it commands. The C-stick was never the only way to widen it.

A third multiplier was simply never looked for: the **thrust step** (13/14/15) bakes its own cut
schedule and so its own locus.

## The lesson

**Run the fidelity gate before the expensive search, not after it.** Session 79 correctly identified
the gate and correctly deferred it as "no hit is a solution until this passes", but the gate does not
only validate hits. It validates the *objective function*. A search aimed at the wrong function cannot
be rescued by making it bigger, and its density diagnosis will look perfectly healthy the whole time:
the residuals were smooth, the spacing was measurable, the expected-hit count matched the observed
zero. Nothing about a population looks wrong when the population is the wrong one.

Related: [[search-space-contains-human]] is the same failure mode one level up. The corrected rule is
that a search must be gated on the mechanism it claims to search, not only on the range it sweeps.
