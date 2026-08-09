# The frame an alphabet shares: one node's children are one frame with N pending inputs

**Answers:** My beam expands a node by a whole input alphabet and steps the frame once per child -
do the children actually differ? Five sessions of porting made a stage 13.6x faster and the search
barely moved; what did I mis-measure? How do I check that the stage I optimised is still the
expensive one?
**Status:** `full_herd.junction_beam` steps ONE frame per node per generation instead of one per
child, prunes the node rather than the child, and clones only what a native run does not already
hold in C -- the beam unchanged endpoint for endpoint
([`tests/test_native_junction.py`](../../tests/test_native_junction.py),
[`tests/test_fork_pending.py`](../../tests/test_fork_pending.py)). With the nodes on the C step and
the arming probe camera-free, the junction stage is **53.8 s -> 4.4 s (12.2x)** on one banked
cycle-2 parent. Numbers in [the accounting](#the-accounting).
**Source:** [`harness/tetrapush/from_f0.py`](../../harness/tetrapush/from_f0.py)
(`FreeRun.fork_pending`, `set_pending_input`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`_expand`),
[`harness/tetrapush/beam_io.py`](../../harness/tetrapush/beam_io.py) (`rebuild_beam(native=)`),
[`harness/tetrapush/two_roll.py`](../../harness/tetrapush/two_roll.py) (`junction_gates`' probe).
Measured session 133; probes `_notes/s133_junction_cost.py`, `_notes/s133_junction_split.py`,
`_notes/s133_children_share_camera.py`, `_notes/s133_beam_check.py`.

## The stage that was 84% is now 2%

Session 126 split a chained cycle into its two halves and measured **junction 16% / roll 84%**. That
ratio pointed five sessions of work at the roll, and the roll got 13.6x faster. Re-measuring the
same split afterwards, on one banked cycle-2 parent:

| | junction | roll |
|---|---|---|
| session 126 | 16% | 84% |
| session 133, as shipped | **99.2%** | 0.8% |
| session 133, junction on the C step | **95.5%** | 4.5% |

The queued next step at that point was another roll-stage port. It addressed 2% of a cycle.

**The general shape:** a profile is a statement about the code on the day it was taken. After any
port large enough to be worth doing, the ratio that justified it is stale by construction - so
re-measure the split before spending the next session on the same half.

## The children of a node are one frame

`junction_beam`'s generation expands every live node by its whole alphabet - **274 children** off one
node at the shipped knobs - and the obvious loop clones and steps once per child. Its own docstring
had said since session 68 that those children share identical physics, because the input pipeline
acts a frame late; nobody had drawn the arithmetic conclusion.

It is not merely empirical. Inside `_anmc`'s `_step_courtyard_nogil` the incoming `sx`, `sy`,
`buttons` and `triggerL` appear in exactly two places - the signature and the `_cbuf` write - so at
`input_delay=1` the delivered letter is **buffered and never read by its own frame**. The frame is a
function of the state alone.

Measured beside the proof (`_notes/s133_children_share_camera.py`), over five generations of a real
beam: all 274 children of a node land in **one physics class and one csangle class**, every time,
including across the L split.

So the frame runs once and each child is a clone of it carrying its own pending letter -
`FreeRun.fork_pending`. The stage's steps fall **91516 -> 26815 (71% fewer)** and the beam is
identical endpoint for endpoint, field by field.

What is left of the step count is almost all `two_roll.junction_gates`' arming probe, and that one is
*genuinely* per child: it steps a neutral stick so the pending letter ACTS, which is the whole
question it asks.

## A probe has no next frame

That arming probe reads one field of one frame off a throwaway clone. A camera's only output is the
csangle the NEXT frame reads, and a probe has no next frame - so it steps with the camera detached
and this frame's own csangle injected. Bit-identical (the frame reads the value already committed),
and it drops a `LandCamera.step` that costs **80 us against an 11 us native frame**.

The look pair STAYS wired through the probe, and the distinction is the point: her eye steers the
proc-7/9 re-aim and therefore the `speedF` this gate is reading, while the camera does not feed
anything the probe looks at.

## The accounting

A camera-bearing native step, idle, at a junction-shaped state - and the C engine is the small part:

| | per call | share of the step |
|---|---|---|
| `LandCamera.step` | 80.1 us | 66% |
| `cam_pad` | 8.3 us | 7% |
| the C frame + the Python wrapper | 10.8 us | 9% |
| the recorded row | 7.3 us | 6% |

The junction stage on one banked cycle-2 parent, shipped knobs, before and after:

| | before | after |
|---|---|---|
| the stage | 20.02 s (native) / 53.8 s (wired nodes) | **4.4 s** |
| `FreeRun.step` | 10.96 s, 91561 calls @ 119.7 us | 0.58 s, 26978 calls @ 21.7 us |
| `FreeRun.clone` | 5.04 s, 91516 calls @ 54.7 us | 1.4 s, 71477 calls @ 19.7 us |
| `junction_gates` | 5.78 s | 1.37 s |
| `junction_alphabet` | 1.49 s @ 6.28 ms | 0.62 s @ 2.60 ms |

Three cuts, and the third is the cheapest: `beam_io.rebuild_beam` built its nodes with
`seeds.make_freerun(env)`, whose `native` defaults to False. A banked beam is how cycles 2 and 3 are
actually searched, so the campaign's dominant stage was running on the 411 us Python step because a
camera-carrying run could not be native until session 131 - and the default outlived the reason.
**When a flag's justification is removed, sweep its defaults**; the equality was already there to be
measured (same endpoints, 0-ULP).

`junction_alphabet`'s 2.6x is `stick_for_bearing` memoised. The inverse falls into a byte-
neighborhood scan of up to 529 clamped decodes whenever the octagon clamp moves its analytic
candidate - **2.8 ms a call** against ~30 us when the analytic byte lands - and the alphabet re-asks
a FIXED bearing ladder once per node per generation. It is a pure function returning an immutable
tuple, so the memo is exact rather than an approximation
([`tests/test_stick_for_bearing_cache.py`](../../tests/test_stick_for_bearing_cache.py)).

## A seed is shared, not deep-copied

Moving a model into the C frame leaves its Python object behind, and what it leaves behind is a
SEED. `FreeRun.clone` was still deep-copying three of them every time: `link._foot` is the f0 pose
the core replaced (**9.5 us**, two thirds of the `LandState` clone) and, under `native_look`, `zl1`
and `neck` are the objects `LandCore.seed_look` was built from and that the C frame steps in their
place (**6.7 us**). Each is shared only on the path that provably never writes it - the native step
syncs scalars into a field-holder `LandState` and calls `core.look_check()` where the wired one runs
both models. A native clone is **30.8 -> 12.2 us**; the wired one is untouched at 27.4.

The camera is deliberately NOT on that list. It still runs in Python after the frame, so it is
state, and it is cloned.

**The general shape:** after a port, audit what the old object is still copying. The model moved;
the copy did not.

## The prune belongs to the node

`followed` / `wall` / `outbox` kill most children, and all three read positions and the follow flag
- fields of the shared frame. So the verdict is the NODE's: `_shared_frame` steps it once, and a
node that fails costs **zero** child clones (91516 -> 71477 a stage). Gated as the claim rather than
the consequence - every child's verdict must equal the shared frame's, on both engines.

## What is next, and it is named by the table

Of the 4.4 s left: `FreeRun.clone` ~1.4 s, `junction_gates` ~1.37 s, `junction_alphabet` ~0.62 s,
`FreeRun.step` ~0.58 s. The two structural ones left, both bigger changes than anything above:

* **~26.5k arming probes each cost a clone plus a step**, and only ~24 children per generation
  survive the frontier keep. The probe's frame IS that child's next frame (both act on its pending
  letter), so the beam computes each child's next frame twice.
* **`junction_alphabet` is one `stick_for_bearing` call**: the toward-Tetra full-deflection stick,
  whose bearing genuinely moves per node, so it takes the clamp search every time (2.6 ms). The memo
  is keyed on the bearing MINUS the camera - already normalised - so what is left needs a faster
  decode, not a better key.
