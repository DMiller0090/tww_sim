# Porting the look pair: what a ratio can and cannot tell you

**Answers:** My profile says two models are 89% of a step - is that the whole story, and how much of
it do I actually get back? How do I port a stateful animation model into C without silently changing
what it computes? What does a 0-ULP gate have to compare when the model has a long memory?
**Status:** Tetra's `Zl1Look` and Link's `NeckLook` run INSIDE the native courtyard frame, **0-ULP**
against the Python models on every field of their hidden state
([`tests/test_native_zl1_look.py`](../../tests/test_native_zl1_look.py)). The coupled step goes
**9279 -> 62682 steps/s (6.8x)**; a full roll fan goes **11.5 s -> 2.24 s (5.1x)** on top of s127's
kernel, or **18.3x** against the wired reference. This closes the port that
[the eye page](the-eye-was-the-only-thing-in-python.md) named as next.
**Source:** [`tww_sim/core/anim/_zl1c.pxi`](../../tww_sim/core/anim/_zl1c.pxi) (the port),
`_anmc.pyx` (`LandCore.seed_look` + the in-frame call), `from_f0.FreeRun(native_look=)`,
`seeds.make_freerun_native_look`. Measured session 128; benches `_notes/s128_look_split.py`,
`_notes/s128_fan_bench.py`.

## The ratio was right about the target and wrong about the size

s127 named this port from a ratio: stripped native 98179 steps/s against self-eye 10797, so the two
Python models are ~89% of the step and "worth ~9x more". Measuring the split first - which is the
habit that page argues for - said the same thing more precisely, and the extra precision mattered:

| piece | us/frame | share |
|---|---|---|
| the C core step | 10.0 | 9.1% |
| `NeckLook` (select + update) | 14.9 | 13.4% |
| `Zl1Look.step` | 85.9 | **77.5%** |

and inside her frame, `_pose_eye` is 71% of it (`pose_locals` alone 52%), `look_at_target_2` 20%.
So the money is her **J3D pose chain**, which makes this mostly a DATA port - her keyframe bank has
to become C-resident the way Link's `AnimData` already is - and not a control-flow one.

**The delivered win is 6.8x, not 9x, and the gap is the point.** A ratio of "X is 89% of the step"
silently assumes the ported X costs nothing. It does not: the look pair is 5.6 us/frame in C against
a 10.4 us core, so it is still 35% of the step afterwards. The honest form of the estimate is
`1 / (rest + ported)`, and the ceiling it names (the stripped run, 96k steps/s) is a number you
approach and never reach. Quote the delivered figure.

## What made it cheap, and what would have made it wrong

**The C engine already had the two pose values.** `LandCore.head_top_exec`/`head_mtx_exec` (s127)
were built for the Python models to call; running them in-frame needs the same two matrices. But
called separately they cost **two full 7-joint FK walks**, and `_head_top_impl` IS `_head_mtx_impl`
plus one head-offset multiply (`d_a_player_main.cpp:11592`) - so the in-frame call takes the matrix
once and derives the top from it. Worth 6.5 -> 5.6 us/frame, and free of risk because it is the same
value by construction.

**The sqrt is not the sqrt.** Both look models reach their `absXZ` through `core.collision.fsqrt`,
which is `f32(sqrt(f32(x)))` - a CORRECTLY-ROUNDED square root. The native engine also carries
`_sqrtf_c`, the MSL `frsqrte` + 3-Newton shape the game links for `std::sqrtf`
([pinned in the shipped JP binary](../mechanics/actor-push.md)). They agree to ~2^-32
relative, which is exactly the size of bug that survives a plausibility check and dies in a 0-ULP
gate. The port uses the correctly-rounded one because that is what the model it reproduces uses.

**Her non-morf pose is euler, not quat.** `Zl1Morf.pose_locals` builds the local matrix with
`J3DGetTranslateRotateMtx` off the anim TRS while STORING the euler->quat for the next morf. Those
are not the same matrix in the low bits, so a port that "simplified" to one path would be wrong on
every non-morf frame - which is most of them.

## Gating a model with a long memory

The eye is one output of a state machine that remembers. Two things follow for the gate:

**Compare the hidden state, not the output.** Her morf's per-joint OLD-POSE STORE is rewritten every
frame and only reaches the eye through the NEXT blend, so a wrong store is invisible for one frame
and then diverges. The gate diffs the whole snapshot - the joint chase angles and their clamped
targets, every timer, the McaMorf ctrl, the old-pose store, m3564 - not just the eye.

**The recorded window does not exercise her.** Over the 45 movie frames `f84d == 1` on every frame:
she looks at Link and the look-around anim never fires, because `f7b8` is seeded at **116**. So the
anim switch, the morf blend it starts, the wrap flag, and the RNG horizon are all past the end of the
fixture, and a gate that only replayed the movie would be comparing four fields against constants.
The gate runs a long window too and ASSERTS the coverage it needs.

Constants are handed to C from the Python models at arm time (`from_f0._arm_look_consts`) rather than
re-declared in the `.pxi`: one canonical value per constant, and a change to a model cannot leave a
stale copy compiled into C behind it.

## Once the state moves to C, READ it there - do not mirror it

In native-look mode the eye, her attention target and `m3564` live in the C core, and
`FreeRun._eye_next` / `_tattn` / `neck` become **properties that read the core on access**. The
alternative - mirroring the values back into Python attributes every frame - costs the hot loop
something on every step to produce a copy that is wrong in the one way that matters: stale, on a run
that still looks like a run. `self.zl1` deliberately stays the SEED object rather than being kept in
sync, so there is exactly one live copy and reading her state means asking for it (`zl1_snapshot()`).

The one wrinkle is the seed itself: `_build_core` reads those same attributes to seed the core, so
the properties must fall back to the Python values while the core does not yet exist. That is the
whole job of the `_live` guard (`native_look and _core is not None`) - not a defensive check, a
genuine two-phase lifetime.
