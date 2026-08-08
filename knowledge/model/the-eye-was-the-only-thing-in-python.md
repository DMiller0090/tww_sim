# The eye was the only thing keeping the rollout in Python

**Answers:** My search runs on a Python engine at 2.4k steps/s while a C engine in the same repo does
100k - why can't I just use the C one? Which parts of a coupled two-actor frame are genuinely
camera-dependent and which only look it? How do I decide what to port when a profile says the cost is
spread across five subsystems?
**Status:** the coupled courtyard rollout runs in C, **0-ULP** on Link, Tetra, the eye and the neck
(`tests/test_freerun_self_eye.py`, `tests/test_native_head_top.py`). **3.9x** on the step, **3.6x** on
a roll fan. The remaining Python is `Zl1Look` + `NeckLook`, now ~89% of the step.
**Source:** `harness/tetrapush/from_f0.py` (`_step_native` self-eye mode), `seeds.make_freerun_self_eye`,
the native `_anmc.pyx` (`head_top_exec`/`head_mtx_exec`), `harness/tetrapush/roll_kernel.py`.
Measured session 127; benches `_notes/s127_bench.py`, `_notes/s127_fan_bench.py`.

## The shape of the problem

A profile said the Python step was anim/pose 33%, camera 22%, land 9%, her look 9%, push 7%, math 6%,
neck 4%, and the obvious reading is that no single port pays - you would have to move all of it. That
reading is wrong, and it is wrong in a way worth naming, because the same trap is waiting in any
coupled sim: **a profile ranks subsystems by cost, and what you actually need is the DEPENDENCY
ORDER.** The question is not "what is expensive" but "what does the fast engine not have, and what
does that missing thing cost to supply".

The C engine (`LandCore.step_courtyard`) already ran the whole frame - the input pipeline, the stick
decode, the attention machine, the procs, the fused pose FK, the CC push pair, the f32 Tetra track. It
was not used because it is the STRIPPED configuration: no camera, no look models. Two injections stand
between it and the wired engine, and they are not alike.

## The two injections, priced

**csangle is free.** Not cheap - free, for a roll. Through a roll segment the committed csangle
sequence is bit-identical across a whole 143-aim fan, on every node and every C-stick mode tried, so a
fan evolves the camera ONCE and replays it. (The C-stick target does move it; the AIM does not. See
[the roll fan](../strategy/the-fan-pays-for-one-camera.md).)

**The eye is not**, and it cannot be dropped. Falling back to Tetra's feet - which is what the stripped
run does - moves Link's proc-9 re-aim by 180 BAM and a banked 45-frame node log by **123 u**. Her eye
is `Zl1Look`'s output, and her look model needs exactly one thing from Link that is not a position:
his exec-pass `mHeadTopPos.y` (`dNpc_playerEyePos`). `NeckLook` needs one more: the cached
previous-frame head MATRIX, which it measures its current angles from.

So the entire 100x gap came down to two matrices per frame - and both were already computed in C. Joint
15 is posed with the body-Co extras for the push centre, so `HEAD_CHAIN = [0,1,2,3,4,14,15]` is one
matrix concat further than the Co-centre chain the engine already walks. `head_top_exec` /
`head_mtx_exec` cost no extra pose work at all.

## What that buys, and what is next

| engine | steps/s | is it the wired run? |
|---|---|---|
| `make_freerun` - wired Python | 2796 | yes (it IS the reference) |
| **`make_freerun_self_eye` - C step, look models in Python** | **10797** | **yes, 0-ULP** |
| `make_freerun_native` - stripped | 98179 | **no** - the feet fallback is a different run |

The third row is the one to be careful with. It is 35x and it is not the same simulation; quoting it
as the speed of the search would be quoting a different answer arriving faster. The middle row is the
honest number, and the ratio between them is now a work order rather than a mystery: at 10797 vs 98179
the two Python look models are **~89% of the step**, so porting `Zl1Look` + `NeckLook` into the native
step is worth ~9x more and there is nothing else in the frame worth looking at.

## The lesson, stated generally

When a fast engine exists and is unused, do not port the expensive subsystem - **find what the fast
engine cannot supply, and ask what the smallest sufficient export is.** Here the profile pointed at
pose FK (33%) and the camera (22%); the actual blocker was a Y coordinate and a 3x4 matrix that the
fast engine was already computing internally and simply never handed back. The port was ~120 lines and
touched neither subsystem the profile named.

The corollary is the trap: an export like this is only worth anything if it is BIT-EXACT, and the two
lean conventions for that head matrix (the exec base drops the lean on a proc-`*_init` frame) differ
by **1.4 u in x and 3.4 in z on the first frame** - 100x the razor's whole acceptance band. A port
that picks the wrong one produces a run that looks entirely reasonable. Gate the convention, not just
the value.
