# Link - the head-look twist `m3564` (setNeckAngle)

**Answers:** Why does Link's head visibly turn toward a lock-on/attention target, what state
drives it, when does it engage/disengage, and why did the self-contained courtyard replay carry a
<=16-BAM facing echo until it was modeled? What does `mHeadTopPos` (the point Tetra's look-at
chases) actually depend on?
**Status:** LIVE-VALIDATED 0-tolerance (2026-07-23, session 21). The model
([`tww_sim/land/neck_look.NeckLook`](../../tww_sim/land/neck_look.py)) reproduces every live
`m3564` AND every live facing bit-exactly over the whole 44-frame courtyard push window in the
capture-tight replay (`tests/test_neck_look.py::test_m3564_and_facing_bit_exact_vs_live_diag`,
fixture `fixtures/courtyard_m3564.json`). Wired into the coupled replay
(`harness/tetrapush/from_f0.FreeRun(neck=)`); head-top Y closed from <=0.96 u to <=1e-3 u.
**Source:** decomp GZLE01 (logic identical JP) `daPy_lk_c::setNeckAngle`
(`d_a_player_main.cpp:8938-9169`, called at :11571), `jointBeforeCB` (:269-270, :350-362),
`checkAttentionPosAngle` (:8923), the proc mode-flag table (`d_a_player_main_data.inc:223-302`),
`dAttention_c` list stocking (`d_attention.cpp:518-560`, `judgementStatus*` 764-844). Values:
[reference/constants.md#link-head-look](../reference/constants.md#link-head-look).

---

## What it is

`m3564` (csXyz, s16) is Link's **head-look twist**: `jointBeforeCB` rotates the HEAD joint
(CL_JNT_HEAD_JNT_e, 15) by `local_38 = (m3564.y, m3564.z, m3564.x)`, applied as two quat concats
onto the animated pose -- `Q(x=m3564.y, y=m3564.z, 0)` then `Q(0, 0, z=m3564.x)` (:353-362). So
`m3564.x` is pitch, `.y` yaw, `.z` (roll) is never driven on land. The twist changes only the
head joint's ROTATION -- root/neck translates (the body Co centre) are untouched; `mHeadTopPos =
anmMtx(head) * (40, 0, 0)` moves with it (up to ~1 u of Y at full tier deflection).

## The per-frame update (setNeckAngle, in the execute pass)

Runs at :11571 -- **after** `posMove`/`setMoveSlantAngle`, **before** this frame's
`mpCLModel->calc()` -- so it measures the **previous** frame's head anm matrix and twists **this**
frame's pose. Two timing traps, both live-pinned:

- **`m34DE` here is the frame-START facing** (previous frame's end value): it is written in the
  execute PROLOGUE (:11287), before the proc dispatch (:11402) updates `shape_angle.y`. Feeding
  the post-step facing lands every yaw target one re-aim ahead (the courtyard f20 y flips sign).
- **The mode flags are the pause-boundary dispatch proc's** (`mModeFlg`, set from the proc table
  at `commonProcInit` :5806, which runs on the new proc's first dispatch frame).

The law (all s16 arithmetic):

1. **Gate**: a look target is chased only when `mModeFlg` carries `0x80 | 0x8000000` AND a look
   pos was selected. MOVE / WAIT / ATN* / SIDESTEP / CUT* carry `0x80`; **FRONT_ROLL, MOVE_TURN,
   WAIT_TURN, SLIP do not** -- `m3564` chases 0 through every roll even while the actor-lock is
   held mid-roll. Gate off -> targets are 0 (every reachable else-branch: the `m34C3 == 1` arm
   reads `m34E2 >> 1`, 0 across the courtyard window).
2. **Look pos** = the locked actor's `eyePos` (`mpAttnActorLockOn`, :9014) or, unlocked, the
   attention's stocked lock-on-list head's (`GetLockonList(0)` via `checkAttentionPosAngle`,
   :9019-9029) -- both through the **+-0x6000 cone of `m34DE`** on the feet->eye bearing. The
   list is restocked every NONE-state attention Run (`stockAttention`) and kept through
   LOCK/RELEASE, but the Run that transitions to NONE has just `freeAttention()`d it and does
   NOT restock -- a **one-frame empty hole on the lock-drop frame** (courtyard f21 chases 0
   between two chase frames). Modeled by `AttentionLock.list_present`.
3. **Measure** (off the previous head matrix M): `spC4 = M*(11.25, 0, 0)` (head centre),
   `spAC = M*(11.25, 18.75, 0) - spC4` (eye direction); the anim's own pitch/yaw with the current
   twist subtracted: `r24_4 = atan2s(-spAC.y, absXZ(spAC)) - m3564.x`, `r25_3 = atan2s(spAC.x,
   spAC.z) - m34DE - m3564.y`.
4. **Targets**: `spB8 = look_pos - spC4`; pitch `r27 = atan2s(-spB8.y, absXZ(spB8))` clamped
   `[-10000, 8000]`; yaw `r23_3 = atan2s(spB8.x, spB8.z) - m34DE`, **except `absXZ(spB8) < 30`
   freezes it at the current `m3564.y`** (the tier frames -- Link is nearly on top of Tetra, so
   the courtyard yaw "dance" 60 / -3 / 0 at f19-21 is this razor branch), clamped +-14336.
5. **Chase**: `cLib_addCalcAngleS(&m3564.{x,y}, (target >> 1) - measured, 3, 0x1000, 0x100)`
   (the `>> 1` half-angle variant runs for `0x80` procs whose upper anim is not DASHKAZE), then
   the yaw overflow clamp keeps `r25_3 + m3564.y` inside +-14336 (applies on every `0x80` frame,
   selected target or not); `.z` chases 0.

## Why it mattered (the echo chain)

`m3564` -> this frame's head pose -> `mHeadTopPos.y` -> Tetra's look-at ELEVATION chase (her
target is Link's head-top Y over his feet) -> her head pose -> her **eyePos x/z** -> Link's
proc-9 re-aim bearing -> **facing**. Unmodeled, the tier-frame head-top Y sat <=0.96 u high and
facing echoed <=16 BAM on the untarget frames. With the model wired the whole chain is bit-exact
in the capture-tight replay; the fully self-contained replay keeps m3564 inside a +-16-BAM
envelope on chase frames (bearings quantized on the amplified common-mode seed noise -- every
chase increment still matches live).

## Sim wiring

`FreeRun(neck=)` / `replay(neck=)` (`harness/tetrapush/from_f0.py`): the update consumes the
cached previous-frame head matrix (`FootFK.head_mtx`, twist included), the pre-step `m34de`, the
post-step dispatch proc, `AttentionLock.locked`/`list_present`, and the end-of-previous-frame
Tetra eye (the [tetra-look](tetra-look.md) model's output). Seed = the live f0 `m3564`
(`capture_push seed` -> `link.m3564`; at state 2 it is mid-decay from the prior cycle's look).
