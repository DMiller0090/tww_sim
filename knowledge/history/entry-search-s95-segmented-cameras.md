# "A C-stick switch point is more cameras, and the dedup makes it 2x cheaper" (session 95, 2026-08-03)

> **status: historical** - this records an axis enumerated over the wrong object. The measurements in it
> are right and are still quoted; what was wrong is what they were read to mean - that C-stick *paths*
> are camera draws, and that the shipped dedup was collapsing them. Current truth is
> [strategy/clip-camera-supply.md](../strategy/clip-camera-supply.md) (the walk trail is a function of the
> first two bytes, so supply is `bytes^2` and a switch point buys none) and
> [strategy/clip-camera-axis.md](../strategy/clip-camera-axis.md) (the axis itself, which stands). Kept
> for the lesson: an enumeration over an input's *paths* over-counts an axis whose consumer only reads
> part of it, and the tell was sitting in the session's own dedup number.

## What was claimed (session 95)

Having priced the camera as free in frames and measured that it draws entries the frozen camera cannot
reach, the axis needed a bigger alphabet than the 82 trails a single held byte draws. The C-stick is idle
on *every* entry frame, not merely uniformly, so any path is deliverable and a path that switches at frame
k reaches trails no held ramp does. A segmented alphabet at byte stride 32 was built on exactly that:

- **137 cameras -> 105 distinct near-miss draws, E[hits] 0.273, 1365 s.**
- Those 137 carried only **49 distinct 4-frame walk trails**, and **41 of the 49 groups reported a
  bit-identical draw set**. One representative per group bought 83 of the 105 draws in 530 s -
  **0.157 draws/s against 0.077**.
- Conclusion drawn: the segmented alphabet is how the axis is spent, `dedupe_cameras` collapses the
  duplicates automatically inside `search`, and the next pass should run **stride 16 or two switch
  points** and budget at ~0.157 draws/s (E[hits] ~1 in about 1.5 h).

## What was actually true

Every number above reproduces. Two readings of them did not.

**A switch point is not a camera.** The 4-frame walk trail is a function of the C-stick bytes on frames 0
and 1 and of nothing later - exact over all 4096 four-byte paths at stride 32, where 3584 disagree with
their 1-byte prefix. So a second switch point multiplies paths 8x and stepped trails 7.7x and adds **zero**
walk clouds (64 -> 64 at stride 32, 196 -> 196 at stride 16). The supply law is `(deliverable bytes)^2`,
and the real supply was much larger than the recipe implied in one direction and much smaller in the
other: **709 clouds at stride 8 and 5300 at stride 2**, but no amount of switching adds one.

**The dedup was never happening.** `dedupe_cameras` keys on `fan_steps` - 6 frames at the bounded shape -
and collapses **0 of 137** and **0 of 440**. The 0.157 draws/s came from grouping on the plan's 4 frames,
which is a *different* key and a lossy one (79% of the draws for 39% of the clock). So the handoff's "the
dedup is automatic" was false and its budget was 2x optimistic; the honest form is a named parameter with
the trade stated (`search(group_steps=)`).

And one bound turned out to belong to the enumeration rather than the axis: cell 2553 was reported aimable
at **64 of 82** cameras, with the rest skipped. That is a property of enumerating *held* bytes, where one
value serves both the walk and the aim. Bytes past the walk channel move the aim frame while leaving the
walk cloud bit-identical, so choosing the walk pair first and then a tail byte drops **0 of 196** clouds.

## The lesson

The tell was inside the session's own output. A dedup that collapses 137 objects into 49 is not a budget
accident, it is the statement that **the consumer cannot see most of what you enumerated** - and that
number was measured, written down, and read as a discount instead of as a supply law. When an enumeration
collapses hard, ask what the collapsing function is ignoring, because that is the shape of the axis.

Its companion: a bound reported as a property of the axis ("64 of 82 cameras can aim this cell") should be
re-asked of the enumeration that produced it whenever the enumeration changes.
