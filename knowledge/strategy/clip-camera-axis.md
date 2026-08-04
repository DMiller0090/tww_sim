# The camera is an input the plan already owns - and a lever is priced against the grid the SEARCH can use

**Answers:** My razor search has saturated - more candidates return the same closest approach, bit for
bit - what is left to buy? Is a camera slew free, and how do I find out? Which half of the camera did
the earlier "worth zero" pricing actually measure? How do I run a fan at a camera the plan can really
deliver, and what does the roll's facing latch against while the camera is still moving?
**Status:** validated offline (session 95) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_entry_camera.py`](../../tests/test_entry_camera.py). The entry plan's C-stick is idle on
every console frame, so a slew there costs **zero frames**; a held byte buys **82 distinct camera
draws** within -716..+714 BAM, of which **64** keep the target cell aimable (a held-byte figure - see
[clip-camera-supply.md](clip-camera-supply.md), where the loss goes to zero). A 64-camera frame-floor
pass at a bounded shape returns **71 distinct near-miss draws, E[hits] 0.19, in 643 s** - session 94's
exhausted 3.2M-candidate pass at the frozen camera returned E[hits] 0.194 in 866 s, and **96% of these
draws stand where the frozen fan cannot reach**. What the camera does NOT do is grow the reachable
cloud: hull area moves +0.0% across the whole slew, so the second lobe stays out of reach at the frame
floor.
**Source:** `harness/tetrapush/entry_camera.py` (`cam_trail`, `camera_alphabet`, `aim_frame`, `aim_at`,
`walk_cells`, `fan_cam`, `search`), `harness/tetrapush/entry_fan.py`
(`iter_fan2(hold=, cs_trail=)`, `_fan_chunk(cs_seq=)`), `harness/tetrapush/entry_search.py`
(`confirm_entry`), `fixtures/courtyard_cam_trails_s95.json`.

---

## An idle channel is a free lever - so go and find the frames where nothing needs it

[razor-prices-every-term.md](razor-prices-every-term.md) rule 13 says price a lever in the objective's
own currency before believing it. The currency here is frames, and the answer came off a locked console
fixture rather than an argument: in the delivered movie the entry plan runs **after** the escape atom,
and every one of its frames carries `substickX == 128`. The C-stick is doing nothing there. The atom
upstream needs the camera frozen - that is what pins the search's csangle - but the atom has already
fired by then, so a slew inside the entry plan cannot cost a frame.

That is a general move, not a fact about this corner. An input channel that no constraint is using over
the frames a search spans is a **free axis**, and the way to find it is to read the delivered log
column by column rather than to reason about what the plan "needs".

What is bounded is not the price but the **reach**: from the arrival a held C-stick byte moves csangle
about **-716..+714 BAM by the 4th entry frame**, with a one-frame delay and a fine ladder in between
(byte 96/160 is -5/+4 BAM at frame 4). So the honest statement is *free, and bounded to a few degrees*.

## The two halves of a camera, and only one of them was ever closed

`csangle` enters twice, and they are different levers:

- **the AIM half** - the roll facing is `decoded_aim + 0x8000 + csangle`. This one was priced at zero
  and correctly closed: the roll's whole schedule goes through `jmaSinTable[angle >> 4]`, so the atom is
  the 16-BAM **cell**, and a slew re-indexes which stick byte lands in a cell without adding one
  ([../history/entry-search-s81-camera-lever.md](../history/entry-search-s81-camera-lever.md)).
- **the WALK half** - a held stick's world direction is `decoded_stick + 0x8000 + csangle`, quantized to
  the same cells. The camera slides the whole set of directions the fan can command, and therefore the
  set of **entry points** it can reach.

The walk half was priced too, and against the wrong grid. It counted **3612 of 4096** direction cells
reachable at the frozen camera and 3858 over all offsets - 1.07x, "buys nothing" - measured over the
whole stick alphabet at `msd_min=0`. **The fan cannot use that alphabet.** It keeps only endpoints at
the speedF cap, and a held stick walks at `msd` of the cap, so its sticks are the cap-magnitude ones:
**2280 decoded angles reaching 1736 of 4096 cells, 42.4%** (gated against a real fan, not argued from
the speed law). Slide a 42% subset and you get a different subset:

| camera offset | cells commanded | of them unreachable frozen |
|---|---|---|
| +-1 BAM | ~1730 | 74-86 |
| +-4 BAM | ~1730 | ~300 |
| +-16 BAM | 1736 | **888** |
| the whole reachable slew | - | union is all 4096 |

So neighbouring cameras are ~94% correlated and cameras a sine cell apart command largely different
directions. **A camera is a fresh draw of the entry lottery**, which is exactly what a search that has
saturated on candidates has run out of.

## What a camera draw is - dedupe on the trail, and deliver the byte

A held byte's **trail** is the csangle per frame. Two bytes with the same trail are **one draw**: 254
deliverable bytes collapse to **82 distinct trails**. Counting the bytes instead is the same error that
made the aim axis read 8.00x when it was worth nothing ([clip-lottery-draws.md](clip-lottery-draws.md)).

And the byte has to survive delivery: `dtm_make.cal` clamps a C-stick 255 to 254 and 0 to 1 exactly as
it does the main stick, so the alphabet is built on 1..254 and every representative is checked
(`[[octagon-clamp-decode-bug]]`).

The trail itself is a **pure function of the byte** - the yaw target moves only with C-stick X and
Link's motion moves only the camera centre ([../mechanics/land-camera.md](../mechanics/land-camera.md)) -
which is what lets one measured trail serve a whole fan. Gated over three held main sticks, bit-identical.

## Injecting a camera into a stripped fan

The fan runs the stripped native config with csangle injected per frame; the plan it authors will run on
a console that integrates the camera. So the injected trail has to BE the wired one, and the alignment
matters: **frame k decodes against `trail[k]`**, the value the wired run reports for frame k, not the
one committed after it. A constant injection cannot see that difference, which is why it went untested
for fourteen sessions - and why the gate is a moving camera compared position-for-position against the
wired `LandCamera`, 0-ULP.

The fan's own contract is kept by the neutral byte: at `subx=128` the trail is the constant frozen
csangle and the camera path must reproduce the default pass key **and** value, bit for bit.

## The camera is still ramping at the dispatch, so it moves the aim too

Measured by firing the roll and reading the facing back (never by trusting a commanded one): the A-press
sits on trail index `frames`, and the target is computed when the input is **acted**, one frame later -
so the roll's facing is `decoded_aim + 0x8000 + trail[frames + 1]`. Unanimous across cameras spanning
-1619..+1420 BAM, where the neighbouring indices are 90-460 BAM wrong.

Two consequences, and the second is the bound on the whole axis:

1. the aim bytes a hit must be delivered with are **not** the frozen camera's. At `subx=249` the bytes
   that roll into cell 2551 frozen roll into cell **2640**;
2. a camera draw only counts if the target cell is still **aimable** at that camera's dispatch csangle.
   The aim alphabet is ~1 aim per cell in the seam window, so some *held bytes* simply have none: cell
   2553 survives at **64 of the 82** held draws. A pass skips the rest and says so - it is
   [clip-exit-angle.md](clip-exit-angle.md)'s "not aimable at this camera", one camera at a time. That
   skip is not a bound on the axis, though: the aim frame is past the walk channel, so a tail byte buys
   the aim back without touching the walk cloud ([clip-camera-supply.md](clip-camera-supply.md)).

## What it buys, counted the way this search has learned to count

A 64-camera frame-floor pass at cell 2553, bounded shape, 643 s:

| | frozen camera, exhausted (s94) | 64 cameras, bounded shape |
|---|---|---|
| clock | 866 s | 643 s |
| candidates | 3.2 M at one camera | ~78 k each |
| near-miss draws | 83 | **71 distinct** (243 reported) |
| E[hits] | 0.194 | **0.19** (0.65 if pooled without dedup) |
| saturating? | yes - 2.4x the candidates moved the argmin by bit-identical zero | no - each camera is a fresh 10 s draw |

Three things that pass says, and the second is the one that matters:

1. **the pooled number is 3x the real one.** Neighbouring cameras command ~94% of the same directions,
   so they reach many of the same entries, and one entry at two cameras is ONE draw. `summarize`
   dedupes across cameras before summing the lottery; reporting 0.65 would have been the fourth
   instance of counting copies as discoveries in this search;
2. **96% of the draws stand at walk endpoints the frozen fan does not reach at all** (77 of 80 on the
   draw key, 71 physically distinct). The camera is not re-labelling the frozen population, it is
   drawing a different one;
3. **spend the clock on cameras, not on depth.** The same camera at a 6.5x wider shape (507 k
   candidates, 124 s) returns 17 draws against ~4 - 4.3x the draws for 12x the clock, the family axis's
   own diminishing return. Per second the bounded shape is ~3x better, so the axis's budget rule is
   many cheap cameras first.

## More cameras: how many there are, and what one draw's worth of C-stick is

The channel is idle on EVERY frame, so any C-stick path is deliverable - but a path is not a camera. The
4-frame walk trail is a function of the bytes on frames **0 and 1** alone, so the walk supply is
`(deliverable bytes)^2` (**64 / 196 / 709 / 2394 / 5300** clouds at byte stride 32 / 16 / 8 / 4 / 2) and a
switch point past the channel adds none of it. Bytes past the channel move the **aim** instead, which
makes aimability a free knob and turns the "64 of 82 cameras can aim cell 2553" bound above into a
property of held-byte enumeration rather than of the axis: pick the walk pair first, then a tail byte, and
**0 of 196** clouds are lost.

That is a page of its own - [clip-camera-supply.md](clip-camera-supply.md) - along with the two dedup keys
a pass can group cameras on and the measured trade between them.

## What the camera does NOT move: the reachable cloud

The re-index happens INSIDE the cloud. Across cameras spanning the whole slew the 4-frame walk hull's
area moves by **+0.0%** (1686.7 -> 1686.9 u2) and its bounding box not at all, and **0 of 9** second-lobe
stations enter the union hull. That is the expected shape of it - the cloud's extent is set by Link's
heading, the speed cap and the turn rate, none of which a camera touches - and it means session 93's
second-lobe negative ([clip-exit-angle.md](clip-exit-angle.md#what-a-cell-costs-in-frames)) survives
this axis rather than being reopened by it.

## The rule

**Price a lever against the subset the search can actually use, not the one the hardware has.** The
walk-side camera was dismissed on a grid twice as dense as the fan's own speed prune permits, and the
two readings differ by more than a factor of two in cells and by orders of magnitude in what a pass
returns. The tell was available: the pricing measured a grid the search had never been allowed to
enumerate.

Its companion is rule 12's corollary - a closure expires when its premise moves - and here both applied
at once: the aim half was closed against a 2-cell window that later measured 22, and the walk half was
closed against an alphabet the fan cannot hold.

## See also

- [clip-camera-supply.md](clip-camera-supply.md) - how many draws the axis holds, the two-byte walk
  channel, and why aimability is a free knob.
- [clip-lottery-draws.md](clip-lottery-draws.md) - what one draw is, and why the camera's bytes are
  deduped onto trails.
- [clip-search-budget.md](clip-search-budget.md) - the budget frame this sits in: a rate is only
  comparable inside one plan shape, and a camera is a different shape.
- [clip-exit-angle.md](clip-exit-angle.md) - the objective term the camera is being spent on, and the
  aimable/barren distinction this page reuses.
- [../mechanics/land-camera.md](../mechanics/land-camera.md) - the camera model itself: manual mode,
  the C-stick yaw target, and why Link's motion does not move it.
- [../history/entry-search-s81-camera-lever.md](../history/entry-search-s81-camera-lever.md) - the
  superseded pricing, and the aim-side half of it that still stands.
