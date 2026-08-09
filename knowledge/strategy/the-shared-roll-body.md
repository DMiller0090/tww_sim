# The shared roll body

**Answers:** My stage re-runs the same rollout under N variants of ONE input - how much of that is
shared, and where does the divergent tail actually start? Should I reach for the fast kernel that
worked on the stage upstream? Why can a ported endpoint be exact and still be unusable by the next
stage? How do I tell a gate that passed from a gate that was vacuous?
**Status:** The herd search's camera-target pass (`roll_candidates`' R2) runs off one shared roll per
aim instead of ~25 whole ones, and the stage is bit-identical either way
([`tests/test_tcs_kernel.py`](../../tests/test_tcs_kernel.py),
[`tests/test_fan_stage.py`](../../tests/test_fan_stage.py)). Numbers in
[the accounting](#the-accounting) below.
**Source:** [`harness/tetrapush/roll_kernel.py`](../../harness/tetrapush/roll_kernel.py)
(`SharedBody` / `camera_walks` / `tcs_segment`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_candidates`, the
``shared_body`` path). Measured session 130.

## The family shares the roll, and the branch is READ, not set

R2 fires one aim's roll under every value of the camera-target grid. `full_herd.target_cs_is_exit_only`
already said what that buys - inside a roll the camera target changes nothing but the camera - but a
two-offset, six-field measurement is not a branch frame. Measured over the real 25-value grid, five
aims, three L windows: the physics is bit-identical for **17 of a 22-frame segment**, and the first
frame that differs is exactly the first frame after the `FRONT_ROLL` block.

So the branch is not a constant. It is read off the roll's own end as the body steps, which means it
is right for whatever this node's roll turns out to be rather than for the one that was measured.

Two things have to hold and they are different claims, so
[the gate asserts both](../../tests/test_tcs_kernel.py):

* **safety** - no frame BEFORE the branch depends on the camera target, for any target on the grid.
  This is what lets the shared frames be shared.
* **tightness** - somewhere on the population a target diverges AT the branch. Per aim it can be
  later (frame 18, 19) or never at all: when the roll ends in proc 6 with Link stopped there is
  nothing left for the camera to steer. Without this half, a branch set cautiously early would pass
  the safety check while quietly sharing nothing.

What makes the branch a clean cut is that the only stored state carrying the camera into a later
frame is the stick want-angle `m34E8`, and `setStickData` recomputes it from the stick and the
csangle on every non-neutral frame. So swapping in the target's own camera, csangle and last
delivered input is a COMPLETE swap - 250 of 250 branched segments `==` their wired originals.

## One body's camera arguments serve the whole family

`LandCamera.step` takes Link's pose and the attention, so the arguments the frozen-camera body
produces are every target's arguments - up to the branch, trivially, because the physics is the same.

The stronger form is the useful one and it was measured rather than assumed: those arguments
reproduce every target's committed csangle **over the whole segment, past the frame where the
physics has diverged**. That is `FreeRun`'s own "csangle is position-independent in this regime"
cashed in, and it is why a camera can be walked outside a run at all.

The walk is a PREFIX TREE. Two targets that have delivered the same C-stick bytes so far are at the
same camera state, so they walk as one camera object and split only when `slew_substick` first tells
them apart: **775 camera steps become 529** on the shipped grid.

**The tempting third cut is wrong.** `slew_substick`'s "a centred C-stick FREEZES csangle" is the
steady state, not the transient - the camera keeps chasing for several frames after the stick
centres. Taking it literally collapses the walk to 10 camera steps and is wrong by 178 BAM at frame
5. It cost one measurement to find out, which is the whole argument for measuring the cut before
building on it.

## Why not the kernel that worked one stage up

[The fan](the-fan-pays-for-one-camera.md) is the right unit for R1 and the wrong one here, twice
over:

* **Fanning over camera targets is a LOSS.** The fan's economy is that a fan pays for ONE camera; a
  target grid is nothing but cameras. A camera trace costs ~32 wired steps against the 20-step
  rollout it would replace.
* **A native endpoint cannot be stepped by the next stage.** R2's survivors ARE their runs - the
  candidate carries one into the next cycle and `junction_quality` glides it forward six frames on a
  centred C-stick. Off a frozen-csangle native endpoint that glide is *not* the wired one, for the
  reason above: the camera has not finished chasing, so it is still moving during those six frames.
  Measured, 1 of 25 endpoints glides differently, by 0.009 u.

A shared BODY has neither problem. What comes out of it is a genuine wired run at the genuine
endpoint, so `junction_quality`, the `tcs_probe`/`tcs_key` orders and the next cycle's junction are
all untouched - the port is a drop-in, and it works on every cycle rather than only the ones that
rank plainly.

## The gate that passed and meant nothing

Before that 0.009 u showed up, the native endpoint looked *fine*: `junction_quality` returned the
same score on the native and wired endpoints, **250 of 250**. It was vacuous. On that node the
function returns `None` for every target on the grid - the comparison was two `None`s, 250 times.
The finding was one line of counting away (`scored: 0/25`), and without it the session would have
shipped a native endpoint on the strength of a green number.

This is [the s129 lesson](a-screen-needs-a-record-not-a-run.md#three-traps-and-only-one-of-them-is-about-physics)
one level down. A comparison passing is not evidence until you have checked it had something to
compare - and a coarse score (here `(-frames_in_box, |lat|)`) can tie while the states behind it
differ, so compare the STATE when the state is what gets carried forward.

## The accounting

Counted first, so the figures do not move with machine load - one cycle-1 roll stage off its own
prologue node, at the aim step the s129 row was measured at so the three rows compare:

| | wired steps | native | camera-only | wall clock (idle) |
|---|---|---|---|---|
| the stage as it was (pre-s129) | 6719 | 0 | 0 | 3.031 s |
| R1 on the fan (s129) | 2251 | 4566 | 0 | 1.088 s |
| **+ R2 on the shared body (s130)** | **1030** | 4566 | 701 | **0.629 s** |

**1.73x on the stage, 4.82x against the all-wired stage, same five candidates.** At
`cycle1_nodes`' own shipped aim step the fan is twice as wide and the same three rows read 11235 ->
1030 wired and 4.871 s -> 0.719 s (**6.78x**), because R2's cost does not grow with the fan.

A camera-only step is 66.6 us against a whole wired step's 398.8 us, so what the shared body trades
per target is ~17 wired frames for one walked camera plus a ~5-frame tail.

**And the leftover names itself**: of the 1030 wired steps that survive, **654 (63%) are
`junction_quality`** - the six-frame glide on three sticks, per surviving target - and only 376 are
the bodies and tails. It is wired for the reason above (the camera is still chasing during exactly
those six frames), so the next cut is not another sharing trick but the camera itself: a
`LandCamera` driven from the C core, which is the one export the search has been queuing behind
since s127.
