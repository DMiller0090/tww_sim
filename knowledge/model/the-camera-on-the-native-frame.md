# The camera on the native frame: when the blocker is a guard, not a gap

**Answers:** My fast engine REFUSES to carry one model and I have been queuing a port behind it -
is the missing value a real gap or a guard? The value turns out to be a constant in my regime, so
why export it at all? What is left of a stage once it takes zero wired steps?
**Status:** The herd search's `LandCamera` is driven from the C core, so a fully-wired courtyard run
- camera, her look, his neck - steps in C. A cycle-1 roll stage takes **0 wired steps**, and is
bit-identical to the wired one ([`tests/test_native_camera.py`](../../tests/test_native_camera.py)).
Numbers in [the accounting](#the-accounting).
**Source:** [`tww_sim/core/anim/_anmc.pyx`](../../tww_sim/core/anim/_anmc.pyx) (`LandCore.attn_y`),
[`harness/tetrapush/from_f0.py`](../../harness/tetrapush/from_f0.py) (`FreeRun._run_camera`, the
`_step_native` camera block), `seeds.make_freerun(native=)`, `full_herd.cycle1_nodes(native=)`.
Measured session 131; probes `_notes/s131_attn_y.py`, `_notes/s131_stage_bench.py`.

## The blocker was a guard, not an arithmetic gap

Four sessions of handoffs named the same next step: export `attn_y` = `fadds(92.5, ff.base[1][3])`
from the C core, because that is the one camera argument a native run could not supply. It reads
like a modelling gap - some value trapped inside the Python engine.

Measured first, over 90 frames spanning procs 6 / 7 / 9 / 30:

* `ff.base[1][3]` **is** Link's world Y, exactly. The `mtx_concat` that applies the turn lean has a
  zero translation column, so the lean cannot touch that row.
* The two terms that could move it are dead in this regime: `m35C4` (the `setStepsOffset` walk lift)
  and `m35B8` (the `footBgCheck` ground decay) both read 0.0, and Link's Y never changes because the
  courtyard model has no ground bookkeeping at all.
* So `attn_y` takes **one distinct value** across the whole window.

The arithmetic was never the blocker. What actually kept every camera-carrying run in Python was a
`ValueError` in `FreeRun.__init__` saying a native step cannot drive a `LandCamera` - written when
the native step was new and true only because nobody had wired the camera into `_step_native`. The
port is one property and a dozen lines of plumbing.

**The general shape:** when a port has been queued behind "we need to export X", measure X before
building anything. It may be constant, it may be derivable, and the thing in the way may be a guard
that was accurate on the day it was written.

## Export it anyway - from the engine that drew the frame

A constant argues for hardcoding it, and that would be wrong. The row belongs to `setAttentionPos`
(`d_a_player_main.cpp:10271`, right after `setCollision`), which reads the base TR matrix of
whichever engine posed the frame. Reading it live from `PoseEngine._base` costs a property access
and means the camera cannot silently go stale: the day a ground model makes Link's Y move - a slope,
a step, the m35B8 decay - the camera follows without anyone remembering this page.

That also decides what the gate asserts. It compares the core's `attn_y` against the WIRED
`FootFK`'s own base row per frame, not against a recomputation of `92.5 + Y`. The claim under test
is *the C engine's base tracks the Python one*, which is the failure the export exists to prevent;
a gate written against the number would pass forever by construction.

## One expression, two paths

`FreeRun._run_camera` is the camera Run for both step paths. They differ only in where the four
arguments come from - the Python `LandState` or the C core - never in the law, so a native run
commits the csangle the wired one does by construction instead of by a copy kept in step:

| argument | wired | native |
|---|---|---|
| pad | `cam_pad(self._prev_raw)` | the same (the native step now tracks `_prev_raw` too) |
| pos / facing | `LandState` | `LandCore` |
| `attn_pos.y` | posed `FootFK` base row | `LandCore.attn_y` |
| lock / `target_attn` | `link._atn.locked`, `self._tattn` | `core._atn_state`, the core's look state |

**A trap the port surfaced.** On the WIRED path the camera, her look and his neck all run *after*
the row dict, so `step(record=False)` skipped three models that are STATE, not diagnostics - a run
stepped that way froze its csangle and its eye silently. It was documented as a precondition and is
now enforced, because the native path genuinely does not have the problem: there the look pair runs
inside the C frame and the camera after it, so `record` controls only whether a row is built.

## Moving the engine moves what `run.link` MEANS

Flipping the chain's seed to the native engine broke a gate, and the failure is the useful part. On
a native run `run.link` is a **field-holder** synced FROM the core after each step, so two things
that read like ordinary state access are not:

* **Writing it is a silent no-op.** `run.link.pos_x = ...` moves a mirror; the engine steps from
  where it already was. The gate that caught this teleports Link to bracket the 80 u freeze bar, and
  on a native bed it was measuring an unmoved run.
* **Reading its POSE answers for the wrong frame.** `link._foot` still carries the f0 seed pose, so
  `_computed_center(run.link)` returns a Co centre from before the run started - quietly, and only
  in the low digits of the plow depth everything downstream measures.

Both now go through the run: `FreeRun.co_center()` asks whichever engine posed the frame, and
`FreeRun.place_link()` is the teleport recipe (move, recompute the exec centre, rebuild the pending
CC push) driven through that engine's own owner. Three copies of that recipe existed - two synthetic
beds and the gate - which is the usual sign that it belonged on the object.

**A correction deliberately NOT made here.** Every run-level caller reads the centre with
`init_frame=False`, while the native engine records the frame's true `*_init` flag. On a proc-init
frame those differ by ~1.7 u, so `co_center_exec` takes an override and the port reproduces the
approximation exactly. Correcting it moves search-visible numbers and is its own change, with its
own gate - not something to smuggle into a perf port.

## The accounting

Counted first (load-independent), then clocked idle - one cycle-1 roll stage off its own prologue
node at `cycle1_nodes`' shipped aim step, so these rows continue
[the shared-body table](../strategy/the-shared-roll-body.md#the-accounting):

| | wired steps | native | camera-only | wall clock (idle) |
|---|---|---|---|---|
| the stage as it was (pre-s129) | 11235 | 0 | 0 | 4.80 s |
| R1 fan + R2 shared body (s130) | 1029 | 9083 | 702 | 0.681 s |
| **+ the camera on the C frame (s131)** | **0** | 10112 | 1731 | **0.354 s** |

**1.9x on the stage, 13.6x against the all-wired one, same five candidates.** The camera model runs
exactly as often either way (1731 steps); only the frame around it moved.

## What is left is NOT what the biggest per-call number says

The camera is by far the most expensive single object in the frame - `LandCamera.step` is **44.0 us**
against a whole coupled frame's **10.9 us**, four times the cost of stepping both actors, both look
models and the CC push together. Reaching straight for it would still be the wrong read. Priced
against the stage it runs in:

| | per call | calls | share of a 0.354 s stage |
|---|---|---|---|
| the coupled frame (C 8.2 us + its Python wrapper 2.7 us) | 10.9 us | 10112 | 31% |
| `LandCamera.step` | 44.0 us | 1731 | 21% |
| everything else - clones, per-frame input dicts, prunes, metrics, sorts | | | **~48%** |

So the stage's own Python glue is now the biggest bucket, the camera is second, and the C engine
itself is a minority of its own search stage. That is the honest form of
[the look-pair lesson](porting-the-look-pair.md): each port returns less because what it leaves
behind does not get cheaper. The move that takes the top two together is stepping FRAMES in C
rather than one Python call per frame (`CourtyardFleet`, already gated bit-identical
parallel-vs-sequential) - which needs the camera in C to carry a camera run, so the two are one
piece of work rather than a queue of two.

**A measurement trap worth keeping:** cProfile put 13.2 us of "own time" per frame in
`_step_native`, which reads as a fat Python wrapper. Timed without the profiler that wrapper is
**2.7 us**. Profiler tottime on a function called ten thousand times is mostly the profiler; price a
hot call with a loop, not a profile.
