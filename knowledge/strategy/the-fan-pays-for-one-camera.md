# A roll fan pays for one camera, not one per aim

**Answers:** My search screens a whole fan of aims off one node and each costs a full rollout - is any
of that work shared? Is the camera really an input to a roll, or only an output? How do I port a hot
search stage without changing which candidates survive it?
**Status:** measured and gated. The csangle sequence a roll segment commits is **bit-identical across
a full 143-aim fan**, on every node and C-stick mode tried; `roll_kernel.roll_fan` rests on it and is
0-ULP against `two_roll.roll_segment` (`tests/test_roll_kernel.py`, 13 gates). **3.6x** on the fan.
**Source:** `harness/tetrapush/roll_kernel.py`; probes `_notes/s127_cam_invariance.py`,
`_notes/s127_roll_anatomy.py`; bench `_notes/s127_fan_bench.py`. Session 127.

## The observation

A herd roll is FACING-LOCKED - the main stick is inert for its duration - so the camera cannot move
its trajectory. That much was already known. What was not: the camera does not merely fail to steer
the roll, **it does not respond to it either.** Fire every aim of the full circle off one node and all
of them commit the same csangle, frame for frame, to the bit. The C-stick target changes the sequence;
the aim never does.

So the camera through a roll is a property of the NODE. A fan of 143 aims needs one camera trace, not
143 - and since the camera is ~22% of the wired step and the whole reason the fast C engine could not
be used (it has none), that is the difference between a fan that must run in Python and one that need
not.

## What a roll segment actually contains

Worth stating, because "the roll is 84% of a stage" invites a kernel that bakes the roll and stops.
A segment off a real junction endpoint is **20 frames**:

| frames | what | world-coupled? |
|---|---|---|
| 1 | the A-delivery frame - still the previous proc, at the incoming speedF | yes |
| 16 | `FRONT_ROLL`, facing-locked, constant momentum | only through the CC push |
| 2 | the proc-9 untarget tier - `setSpeedAndAngleAtnActor` re-aims to Tetra | **yes, and via her EYE** |
| 1 | back to MOVE, which ends the segment | yes |

Only the middle block is a bakeable schedule, and it is 80% of the frames, not 100% - so a
schedule-baking kernel of the `ShoveCtx` kind caps at ~5x on the segment however fast the kernel is,
because 4 frames still need the general engine. Verified directly: with no contact, Link's step during
the roll equals the constant-momentum step `p + speedF*(sin,cos)(facing)` to **exactly zero** error,
and every deviation is the plow.

The exit tier is the part that punishes a careless port. It re-aims off Tetra's **eyePos**, not her
feet, so it needs her look model - which is why the fan runs on
[the self-eye native engine](../model/the-eye-was-the-only-thing-in-python.md) rather than on a baked
schedule.

## What the kernel owes besides the trajectory

A fan record is not a position. Three fields decide which candidates exist at all, and a port that
reproduces the path while dropping them is not a speedup, it is a different search:

* **the exit csangle** - the next junction's whole aim alphabet is placed against it, so a kernel can
  look 0-ULP on one roll and corrupt every chain of two;
* **`talk_unsafe`** - an A-press that talks to Tetra kills the run. This is not an edge case: at a
  cycle TERMINAL, where Link ends facing her at contact range, the **whole circle** is unsafe (143 of
  143 aims, measured), and the seeds a gate uses have to include one or the branch goes untested;
* **`ok` / `roll_speedF`** - two endpoints identical in physics can differ in whether the roll arms at
  all.

## The method worth reusing

The invariance is the fan's whole economy, so it is gated **as itself** - "the csangle sequence does
not depend on the aim" is a test, alongside its converse ("a C-stick target does move it", so the
finding is a lever and not a dead camera). If the invariance ever breaks, the gate says which claim
died instead of leaving a mismatched endpoint to be re-derived from scratch.

And the kernel refuses to run without its fast seed rather than silently falling back to the slow
path. A port that is sometimes the reference and sometimes itself cannot be measured or trusted.
