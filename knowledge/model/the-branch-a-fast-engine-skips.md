# The branch a fast engine skips: port it, or make it refuse

**Answers:** My fast engine is missing a branch the slow one has - what does that actually cost me,
and how do I keep the gap from lying to me while I queue the port? Where do I get the collision /
keyframe data a C step needs? What does a 0-ULP gate for a ported branch have to compare?
**Status:** The Courtyard C step carries the last two branches it was missing - BOTH actors'
`dBgS_Acch::CrrPos` wall pass and the roll's `b_trig` CUT arm - 0-ULP against the Python procs
([`tests/test_acch_native.py`](../../tests/test_acch_native.py),
[`tests/test_courtyard_walls_native.py`](../../tests/test_courtyard_walls_native.py),
[`tests/test_cut_native.py`](../../tests/test_cut_native.py)). A **walled** clone+step goes
**717 -> 8215/s (11.5x)**; the terminal phase no longer changes engines. Two mid-roll cases stay
unported and RAISE.
**Source:** [`tww_sim/core/anim/_acchc.pxi`](../../tww_sim/core/anim/_acchc.pxi) (the wall pass),
[`_anmc.pyx`](../../tww_sim/core/anim/_anmc.pyx) (`CutAnimData`, `LandCore._cut_init`/`_proc_cut`/
`_link_wall_pass`/`_tetra_wall_pass`/`wall_check`, `seed_walls`/`seed_cut`),
[`from_f0.py`](../../harness/tetrapush/from_f0.py) (`FreeRun.wire_walls`), `seeds.wall_for_terminal`.
Measured session 150; bench `_notes/s150_bench_walled.py`.

---

## A missing branch does not announce itself

Both gaps had the same shape, and it is the shape worth recognising: **the fast engine did not fail on
the input the branch exists for - it computed something plausible and went on.**

* A mesh assigned to a native `FreeRun` was a **silent no-op**. `LandCore.step_courtyard` tracked
  Tetra as a bare XZ point, so a walled native run was bit-identical to an unwalled one and she went
  53 u THROUGH the courtyard back wall where the console braces her ([tetra-follow](../mechanics/tetra-follow.md)).
* A mid-roll **B press was ignored**: no `b_trig` arm in the C `_proc_roll`, so the roll ran to its
  ordinary exit and the ~23 u thrust lunge simply did not happen.

Neither shows up as an error, a warning, or a diverging field - the run just answers a different
question than the one asked. Both were only found by someone reading the C source beside the Python
one. The defence that works is not vigilance, it is **structure**: a branch the engine cannot carry
must refuse the frame.

## Refuse, don't skip

A `noexcept nogil` frame cannot raise - which is exactly why it is tempting to let it skip. The
pattern used here: the C step sets a sticky flag, and the GIL-holding caller converts it
(`LandCore.wall_check`, called from `FreeRun._step_native` **before any field is synced**, so a
refused frame never leaks a half-computed state).

Two cases are refused rather than modelled, both consequences of wiring Link's mesh:

| case | why it is refused |
|---|---|
| the roll **bonk** (a head-on wall hit inside the crash window) | dispatches `procFrontRollCrash`, an unported proc. A bonked roll crashed, so the plan is dead either way. |
| an A press the wall turns into a **SIDLE** | `setDoStatus` SIDLE preempts ATTACK; the sidle proc is modelled on NEITHER path (`LandState.sidle_blocked` rejects the same stream). |

The same principle covers the wiring itself. `walls_tetra` is a **property** whose setter re-seeds the
C core; `link._walls` belongs to `LandState` and cannot be intercepted, so `_step_native` compares the
run's meshes against the ones its core was seeded with and refuses a mismatch. That is the s149 trap
(a probe that assigned the mesh after construction and got a Tetra that looked walled and was not)
turned into an exception.

## Where the data comes from

A C branch needs the same data the Python one reads, and the answer both times was to hand it over
rather than restate it - the rule [`_arm_look_consts`](porting-the-look-pair.md) already follows:

* **The mesh** becomes a `WallMesh`: verts, planes, and the per-tri `sqrtf_c(nx²+nz²)` flattened to C
  arrays, built ONCE per trilist and shared by reference (the `AnimData` contract), so a beam node's
  clone copies nothing and `CourtyardFleet.run_par` reads it from every thread. No AABB prefilter: at
  48 tris the whole pass is far under the pose FK, so every tri is tested and exactness is structural
  rather than dependent on a margin being large enough.
* **The lunge** becomes a `CutAnimData`: joint 0's three translate tracks from `link_anim_cuts.json`,
  evaluated by the keyframe interpolator already in `_anmc`. Nothing else in the cut BCK moves
  position, and a cut poses no foot chain, so that is the whole root-motion port.
* **The cylinders and the HIO fields** are read out of `land.walls` / `core.npc_zl1` / `land.hio` at
  seed time (`seed_walls`, `land_init_consts`), never re-declared in the `.pxi`.

## What the gate has to compare

The wall pass is a transcription, so **Python is the oracle** and the sweep is the fixture: a
deterministic lattice over the real courtyard mesh at both actors' cylinders, sized so a few hundred
candidates genuinely correct against geometry. *A sweep that never touches a wall proves nothing.*
Writing it caught exactly one gap - `acch_crr_pos` rounds both endpoints to f32 on entry (the console
has no f64 to skip) and the C port did not, which is a 1-ULP brace, which is a razor clip turned into
a block ([[full-fp-precision-coords]]).

For the frame-level gates, three things that a naive engine-vs-engine diff would miss:

1. **The unwalled arm is half the gate.** The port added branches to the hot frame; none of them may
   move a run with no mesh. It is the reference every other native gate is built on.
2. **A silently-uncut roll passes an engine-vs-engine diff by being equally wrong on both sides.** So
   the cut frame is also reconstructed from first principles -
   `((pre + speedF·dir(travel)) + the CC recoil) + rotate(m3700, shape_angle.y)` with `m3700_prev = 0`
   - and asserted 0-ULP on BOTH engines. That is a statement about the model, not about C.
3. **Every field the branch writes goes on the allowlist**, including the four the wall pass sets that
   no earlier native gate had reason to read (`wall_hit`, `line_hit`, `wall_cir_hit`, `wall_angle`).
   A field nobody listed is a field a bug hides in - the unsynced-mirror lesson in
   [the-lean-is-the-rolls-own-dispatch.md](../strategy/the-lean-is-the-rolls-own-dispatch.md).

## The accounting

Rung 5's herd end, clone + one step, this hardware:

| configuration | Python | native | native cost of the pass |
|---|---|---|---|
| unwalled | 1709/s | 8671/s | - |
| Tetra walled | 1188/s | 8672/s | 0% |
| both walled | **717/s** | **8215/s** | 5% |

In Python the wall pass costs **58%** of the step; in C it costs **5%**. That asymmetry is the whole
argument for porting a collision pass rather than pruning around it: the reason the herd phase leans
on `objective.frame_is_wall_free` instead of the pass was never fidelity, it was that the pass was
unaffordable where the search spends its frames.

One case is still Python-only and it is NOT this port's: the walk step (`LandCore.step`) has no
`b_trig` either, so a mid-roll B on a native `LandState` outside the courtyard is still ignored.
