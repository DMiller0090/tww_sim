# The anim frame is f32, and a `double` rate breaks the tie the wrong way

**Answers:** Why must an animation frame ctrl's `rate`/`frame` be rounded to f32 rather than left as a
Python float? How can a rate that "is 1.1" advance the anim to a different frame than another rate that
"is 1.1"? Why does one ULP of anim frame matter at all? How do you catch this class?
**Status:** validated 0-ULP against a clean-DTM console capture (TWW JP, Courtyard blocked-candidate
delivery, `fixtures/courtyard_centre_seam_s90_console.json`), 2026-08-02.
**Source:** `J3DFrameCtrl::update` (`J3DAnimation.cpp:143`), `daPy_lk_c::setFrameCtrl`
(`d_a_player_main.cpp:12938`), `setSingleMoveAnime` (`:12794`). Code:
[`tww_sim/core/anim/anim_state.py`](../../tww_sim/core/anim/anim_state.py) (`FrameCtrl.set`),
[`tww_sim/land/procs/roll.py`](../../tww_sim/land/procs/roll.py) (`ROLL_RATE`). Gate:
`tests/test_centre_seam.py`.

## The rule

`J3DFrameCtrl`'s float members -- `mFrame`, `mRate`, `mStart`, `mEnd`, `mLoopFrame` -- are **f32**, and
`update()` is a single-precision `mFrame += mRate`. A port that stores a host `double` in `mRate` is
not modelling a slightly-less-precise rate; it is modelling **a different number**, and the difference
survives into the sampled pose.

`f32(1.1)` is `1.100000023841858`. The Python literal `1.1` is `1.1000000000000000888`, which is
*smaller*. Both print as `1.1` and neither is `1.1`.

## Why one ULP of rate is not one ULP of anything

Round-to-nearest is only stable when the exact sum is not on a bin boundary. Advancing the roll:

| | `frame` before | `+ rate` | exact sum | f32 result |
|---|---|---|---|---|
| f32 rate | 2.200000047683716 | `f32(1.1)` | 3.30000007152557373 -- an **exact tie** | 3.3000001907348633 (half-to-even, mantissa 5452596) |
| double rate | 2.200000047683716 | `1.1` | 3.30000004768371591 | 3.299999952316284 |

The f32 rate lands *exactly* on the midpoint between two representables, so the hardware's
round-half-to-even picks the upper one. The double rate's deficit is enough to fall below the midpoint
and round down. **One ULP of anim frame** -- but only on the frames where the tie occurs, which is why
the symptom looks intermittent and pose-specific rather than like a broken rate.

Downstream, rotations are quantized `s16` and scale is constant, so neither moves; only the **translate**
is a float Hermite interpolation, so the whole error lands there. On the Courtyard roll: 1 ULP of frame
-> 3 ULP of root-joint translate -> 1 ULP of the root/neck midpoint
([mechanics/link-co-centre.md](../mechanics/link-co-centre.md)) -> 1 ULP of Tetra -> a seam clip that
does or does not happen.

## The shape of the bug: two accumulators for one quantity

The reason this survived nine sessions is that the anim frame was tracked **twice**:
`LandState.roll_frame` accumulating from an f32 `ROLL_RATE`, and the pose driver's `fc0.frame`
accumulating from whatever `enter_roll` passed. Both are "the `rollf` frame"; nothing compared them.
They agreed on every frame where the sum was not a tie, so every gate that sampled a few frames passed,
and the two only parted where it mattered most.

**Rules this leaves:**

- **Round at the boundary that owns the type, not at the call site.** `FrameCtrl.set` f32s all five
  members, so no caller can reintroduce a double by passing a literal. Fixing `enter_roll`'s `1.1`
  alone would have left `from_f0`'s `2.3` and the next one after that.
- **A quantity tracked in two places needs a gate that compares them.** Not a gate on each -- the two
  centre ports each had their own gate (`test_body_co_native.py` compares FootFK's native fold against
  FootFK's own Python loop) and that is precisely why neither caught it.
- **A literal that "is" a console constant is a double until you round it.** Grep for bare float
  literals reaching f32 state.

## How it was found

Not by inspection -- by a **console run designed to be unambiguous**. Two engines disagreed by 1-2 ULP
with every capture in hand falling where they agreed, so the experiment was to find a candidate where
the disagreement was not 1 ULP of position but 49.9665 u of it (clip vs no clip), and deliver that. The
console named the winning port in one run; the ULP-level diff that followed named the frame, and the
frame named the rate. See [../history/co-centre-two-ports.md](../history/co-centre-two-ports.md).

Related: [fp-faithfulness](fp-faithfulness.md) (which ops fuse, and f32 discipline generally),
[euler-quat-signed-half](euler-quat-signed-half.md) (the same "two representatives of one angle" shape,
one layer up), [anim-engine](anim-engine.md) (where the frame ctrl sits in the pose pipeline).
