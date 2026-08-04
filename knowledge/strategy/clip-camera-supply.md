# How many camera draws exist - the supply law of an input channel, and the knobs it separates into

**Answers:** My camera axis pays and does not saturate - how many draws are actually in it, and how do I
enumerate them without paying for copies? Is a C-stick that switches mid-plan more cameras? Why did
deduping my camera list collapse nothing? Some cameras cannot aim my target cell - is that a bound on the
axis or on my enumeration?
**Status:** validated offline (session 96) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_entry_camera.py`](../../tests/test_entry_camera.py). The 4-frame walk trail is a function of
the C-stick bytes on entry frames **0 and 1 only** - exact over all 4096 four-byte paths at stride 32 -
so walk supply is `(deliverable bytes)^2`, measured at **64 / 196 / 709 / 2394 / 5300** distinct walk
clouds at byte stride 32 / 16 / 8 / 4 / 2. Every later byte moves the aim frame and leaves the walk trail
bit-identical, which makes aimability a **free** knob: at stride 32 one aimable camera per walk cloud is
**64 clouds from 64 passes**, against session 95's 49 clouds from 137.
**Source:** [`harness/tetrapush/entry_camera.py`](../../harness/tetrapush/entry_camera.py)
(`walk_channel`, `WALK_CHANNEL`, `walk_cameras`, `dedupe_cameras`, `search(group_steps=)`).

---

The axis itself - why a camera is a fresh draw of an entry lottery, and what it costs in frames - is
[clip-camera-axis.md](clip-camera-axis.md). This page is the one question that page could not answer:
**how big is it, and what is one draw's worth of C-stick?**

## Enumerate the CHANNEL, not the input paths

The tempting enumeration is the input: the channel is idle on every frame, so any C-stick path is
deliverable, and a path that switches at frame k reaches trails no held byte does. Measured, that is
true and almost entirely worthless:

| enumeration at byte stride 32 | C-stick paths | `fan_steps` trails | **distinct walk clouds** |
|---|---|---|---|
| held byte | 8 | 8 | 8 |
| one switch point | 192 | 176 | **64** |
| two switch points | 1536 | 1352 | **64** |

The second switch point multiplies the paths 8x and the stepped trails 7.7x and buys **zero** walk
clouds. The reason is a measurement, not an argument: the 4-frame walk trail is a **function of the first
two bytes**, bit for bit. Over all 4096 four-byte paths at stride 32, none disagrees with its 2-byte
prefix, while 3584 disagree with its 1-byte prefix.

So the supply law is `(deliverable bytes)^WALK_CHANNEL`, capped by the BAM ladder the camera actually
resolves:

| byte stride | deliverable bytes | 2-byte paths | distinct walk clouds |
|---|---|---|---|
| 32 | 8 | 64 | 64 |
| 16 | 16 | 256 | 196 |
| 8 | 32 | 1024 | 709 |
| 4 | 64 | 4096 | 2394 |
| 2 | 128 | 16384 | 5300 |

**Measure the channel's order before enumerating over it** (`walk_channel` does, rather than trusting the
constant). Getting it wrong is expensive in both directions: assume 1 byte and 87% of the supply is
invisible; assume 4 and you pay 8x for aim variants of clouds you already hold.

## The order also explains a dedup that had no mechanism

Session 95 measured that 137 segmented cameras carried only 49 distinct walk trails and that **41 of
those 49 groups reported a bit-identical draw set**, and read it as a budget accident. It is the supply
law: those cameras differ only in bytes the walk cannot see. The 8 groups that *did* differ are the
converse - the fan steps past the plan's frame cap, so a late byte still reaches some candidates through
the later steps.

Two consequences for any pass that dedupes cameras:

- **the lossless key is `fan_steps`**, and at a bounded shape it collapses **nothing** - 0 of 137, 0 of
  440. A pass that reports a "2x cheaper" dedup it never performed is reporting the wrong budget; the
  2x came from grouping on the plan's frames, which is a different key and a *lossy* one (79% of the
  draws for 39% of the clock - still rate-positive, but it is a trade and has to be named). Both keys are
  one parameter now (`search(group_steps=)`), and a pass records which one it ran under.
- **enumerate one camera per cloud instead** and the question does not arise. That is strictly better than
  deduping a path enumeration after the fact, because the paths thrown away were never the draws.

## Aimability is a separate knob on the same channel - so it is free

The walk cannot see bytes past the channel. The **aim** can: the roll's facing latches against
`trail[frames + 1]` ([clip-camera-axis.md](clip-camera-axis.md#the-camera-is-still-ramping-at-the-dispatch-so-it-moves-the-aim-too)),
which is past frame 1 at any real plan length. So a tail byte moves the aim - and whether the target cell
is aimable at all - while leaving the walk cloud bit-identical. Measured at walk pair `(128, 160)`: eight
tail bytes give 8 different aim csangles, one of which loses cell 2553, and all eight have the same
4-frame walk trail.

That turns session 95's sharpest bound into an artifact. It reported cell 2553 aimable at **64 of 82**
cameras and skipped the rest, because a *held* byte has to serve both jobs with one value. Choose the walk
pair first and then search a tail byte for one that keeps the scope aimable, and the loss goes to zero:
**0 of 64 walk clouds at stride 32, and 0 of 196 at stride 16, are unrescuable** (`walk_cameras`).

Against the session-95 recipe at the same byte stride this is better on both terms at once:

| stride 16 | cameras scored | distinct walk clouds | clouds dropped as un-aimable |
|---|---|---|---|
| s95 segmented paths | 440 | 157 | (folded into the enumeration) |
| one aimable camera per cloud | **196** | **196** | **0** |

More supply from 45% of the passes. The general shape: **when one input value is serving two consumers,
check whether they read different frames of it** - if they do, they are two knobs and the coupling was
yours, not the game's.

## The rule

**A channel's supply is set by how many of its frames the consumer can see, so measure that before you
enumerate.** The corollary that pays here: two consumers reading *different* frames of one channel are
independent knobs, and a bound derived from an enumeration that couples them is a bound on the
enumeration.

## See also

- [clip-camera-axis.md](clip-camera-axis.md) - the axis itself: the idle channel, its price in frames,
  the two halves of a camera, and the trail a fan injects.
- [clip-lottery-draws.md](clip-lottery-draws.md) - what one draw is; this page is the same discipline
  applied to the input alphabet instead of the results.
- [clip-search-budget.md](clip-search-budget.md) - why a rate is only comparable inside one plan shape.
- [razor-prices-every-term.md](razor-prices-every-term.md) - rule 15, which this page's supply law is the
  enumeration half of.
- [../history/entry-search-s95-segmented-cameras.md](../history/entry-search-s95-segmented-cameras.md) -
  the superseded "a switch point is more cameras" recipe, and the measurement inside it that stands.
