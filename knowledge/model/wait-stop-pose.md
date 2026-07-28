# The WAIT stop pose (what the game draws while Link is standing still)

**Answers:** Does the anim keep running while Link is stopped? Why does the first frame of a re-walk
step a tiny amount instead of a full stride? Why does a stop sometimes RESET the walk's anim phase
and sometimes carry it? What does low health change about a stop?
**Status:** validated live 0-ULP (2026-07-28). Modelling this closed the last fidelity seed on the
Courtyard tier-2 gate: `tests/test_node1_console.py` is now bit-exact on both actors at every sample
the console measured in-regime (n=1..80). Gate: `tests/test_wait_stop_pose.py` +
`fixtures/courtyard_node1_wait_s59.json` (locked live capture of the under-body anim registers).
**Source:** decomp `d_a_player_main.cpp` `procWait_init` (:6053), `procWait` (:6093),
`setBlendMoveAnime` (:2969, idle arm :3114), `setMoveAnime` (:12723), `commonProcInit` (:5805),
`checkRestHPAnime` (:5618); HIO `d_a_player_HIO_data.inc` `daPy_HIO_move_c0::m`. Sim
`tww_sim/core/anim/foot_speedf.py` (`pose_idle_blend` / `enter_wait_rest_hp` / `step_wait`),
`tww_sim/land/state.py` (the WAIT branch), `_anmc.pyx` (`_w_pose_idle_blend_c`).

---

**A stopped Link is still being posed.** `speedF` is 0 and the position is frozen, but the frame
controllers keep advancing and `posMoveFromFootPos` keeps running, so the stored toe stream keeps
moving at the standing-idle drift. That matters because the next walk frame's `f31_2` is a delta
between two STORED poses ([anim-engine](anim-engine.md#toe--speedf)). What the game drew while
stopped IS the first step of the re-walk.

Model the stop as "do nothing" and the re-walk steps by the last WALKING delta instead. In the
Courtyard plan that was 2.617 u where the console takes 0.379 u, a 6.9x overshoot on the frame Link
starts moving again, out of two frames of doing nothing.

## Which pose: three arms

`procWait_init` picks, and `procWait` re-picks every frame afterwards:

```
procWait_init (6068)                     procWait (6119-6144), each later frame
  commonProcInit(WAIT)   -> m3598 = 0      m34C3 == 0 -> re-pose ONLY if the single's rate
  mNormalSpeed = 0                                      died or life recovered
  checkRestHPAnime() && !guard                        else: leave it alone, ctrl just advances
      -> setSingleMoveAnime(ANM_WAITATOB) m34C3 != 0 -> setBlendMoveAnime(-1.0f)
      else setBlendMoveAnime(field_0xC)
```

| arm | condition | pose | `m34C3` |
|-----|-----------|------|---------|
| **idle blend** (the usual one) | healthy, facing unchanged | `setMoveAnime(0, H_38, H_40, WAITS, WALK, 2)`, pure WAITS at ratio 0 | 2 |
| **turn-step** | `shape_angle.y != m34DE` and no attention lock | WAITS/`ATNW{L,R}S` at `clamp(0.5 + 0.001·|Δfacing|, 0, 1)` | 2 |
| **low life** | `checkRestHPAnime()` | `setSingleMoveAnime(ANM_WAITATOB, …)`, a SINGLE, not a blend | **0** |

`setBlendMoveAnime` reaches the idle arm because the WAIT proc's `mProcFlags` set
`ModeFlg_00000001`; with `mNormalSpeed == 0` that arm forces **`m3598 = 0`**, which is what pins
`speedF` at exactly 0. The non-idle regime-1 branch would set `m3598 = 1` and let the idle toe drift
drive Link forward, so `ModeFlg_00000001` is load-bearing here, not cosmetic.

## The low-life arm, and why it changes the RE-walk

`checkRestHPAnime()` is `dComIfGs_getLife() <= mMove.field_0xE` **and** `mpAttnActorLockOn == NULL`
**and** `checkNoUpperAnime()` **and** `!checkPlayerGuard()`. On the last hearts, a stop plays the
"wait A to B" transition `ANM_WAITATOB` as a single, with the frame controller's arguments taken
from HIO rather than from the clip, see
[constants](../reference/constants.md#land-movement-walk--roll--atn--hops). The end is **12**, not
`waitatob.bck`'s own frameMax of 13.

Three consequences, all of them observable:

1. **`m34C3` lands at 0.** `setMoveAnime` carries the anim phase as `f31 = frame/frameMax`, but only
   when `m34C3` is not 0/9/10 (:12729). So the walk that follows a low-life stop restarts BOTH
   controllers at frame 0, where one after a normal idle-blend stop resumes on the carried phase.
   The stop reaches two frames further than it looks.
2. **MOVE1's controller freezes.** `setSingleMoveAnime` clears `m_anm_heap_under[MOVE1].mIdx`, so
   the model calc stops advancing a slot it no longer draws. It takes exactly one more update, the
   actor-execute advance that precedes the proc's re-pose on the stop frame, and then holds.
3. **`procWait` leaves it alone.** With `m34C3 == 0` the body frame re-poses only if the single's
   rate has died (`< 0.01`) or life recovered; otherwise the controller just advances 0.6/frame.

## In the sim

`LandState.low_life` seeds the LIFE half, since Link's health is not simulated, and
`_check_rest_hp_anime()` evaluates the half that varies within a run (the actor lock). It defaults
to `False`, so every anchor and golden keeps the idle-blend arm.

The three poses are one code path each, shared with their non-WAIT twins:
`FootSpeedF.pose_idle_blend` (also `procSubjectivity_init`, and the resting anchors'
`seed_rest_blend` frames, since the C-up freeze is a WAIT whose anim keeps running),
`enter_wait_idle` (the turn-step, shared with the post-`WAIT_TURN` pivot), and
`enter_wait_rest_hp` + `step_single_anim` (the low-life single). `procMove_init`'s oldframe-morf
fires on the WAIT->MOVE exit like it does on the ATN->MOVE one.

## Reading a stop off a live capture

A truncate-and-read halt lands **after `posMoveFromFootPos` but before the end-of-execute tail**
(:11285-11289). At sample N the position and `m359C` are frame N's, while `m35B4`, `m34DE` and
`m34EA` still hold frame N-1's, and `mFootData` holds the pose drawn at N-1. Check that alignment on
a frame where the value actually CHANGES (facing, at the re-walk) before reading anything into a
mismatch. Three of those fields are one frame behind the rest by construction.

## See also

- [anim-engine](anim-engine.md), the blend/pose pipeline, and how a toe becomes `speedF`
- [draw-base](draw-base.md), where the pose is taken from · [equipped-anim-set](equipped-anim-set.md), which clips get posed
- [precise-stop](../mechanics/precise-stop.md), the C-up SUBJECTIVITY freeze, a WAIT whose anim keeps running
