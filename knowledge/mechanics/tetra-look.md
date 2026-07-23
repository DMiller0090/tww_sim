# Tetra (NPC `Zl1`) - the look-at head: eyePos + attention position

**Answers:** Where does Tetra's **eyePos** (the point Link's proc-9 `setShapeAngleToAtnActor`
re-aim chases) actually come from, frame by frame? Where is her **attention position** (`tattn`,
the camera's lock target)? How does her head/backbone turn to look at Link, which animation plays
while she is plowed, and what hidden state does a from-f0 replay need to seed?
**Status:** LIVE-VALIDATED 0-ULP (2026-07-23, session 20). The model
([`tww_sim/core/npc_zl1_look.Zl1Look`](../../tww_sim/core/npc_zl1_look.py)) reproduces every live
eyePos, attention position, chased joint angle, clamped target, and half-angle twist bit-exactly
over the whole 44-frame courtyard push window given the live per-frame inputs
(`tests/test_zl1_look.py::test_look_replay_bit_exact_vs_live`, fixture
`fixtures/courtyard_zl1look.json` from `_notes/tetrapush-zl1look_probe.py`). Wired into the
courtyard coupled replay (`harness/tetrapush/from_f0.FreeRun(zl1=)`), replacing the last two
injected streams -- the replay now consumes ONLY the static f0 seed + raw DTM bytes.
**Source:** decomp GZLJ01 `daNpc_Zl1_c` (`lookBack`, `setAttention`, `setMtx`, `_nodeCB_Head`/
`_nodeCB_BackBone`, `optn_1`, `setAnm`/`setAnm_NUM`, `play_animation`; `d_a_npc_zl1.cpp`),
`dNpc_JntCtrl_c` (`lookAtTarget_2` + turn/clamp helpers, `d_npc.cpp:775-915`),
`dNpc_playerEyePos` (`d_npc.cpp:609`), `mDoExt_McaMorf` (`m_Do_ext.cpp:1267-1560`),
`J3DFrameCtrl::update` (`J3DAnimation.cpp:143`), `mDoMtx_*rot*` (`m_Do_mtx.cpp`). Values:
[reference/constants-npc.md#zl1-look](../reference/constants-npc.md#zl1-look).

---

## The two outputs

- **`attention_info.position` (tattn)** -- `setAttention` (:1277), every execute frame:
  `(pos.x, f32(pos.y + 140.0), pos.z)` at her **post-move** position (140.0 = HIO `field_1C`).
  That's it -- feet plus a constant. The camera consumes it during lock windows.
- **`eyePos`** -- her **animated head-joint world position** pushed through the look-at twists
  plus a constant offset (`_nodeCB_Head`, :167-182):

  ```
  eye = anmMtx(head) · RotY(-head_y/2) · RotZ(-head_x/2) · (20, -16, 0)
  ```

  where `anmMtx(head)` is the head joint's world matrix from the model calc in `setMtx` (execute
  pass, post-move position) and `head_x/2`, `head_y/2` are the stored half-angles (`field_0x83C/E`
  -- the other half of the look goes to her pupils via `eye_ctrl`). Link's re-aim reads the value
  Tetra wrote LAST frame (Link executes before Zl1 in the actor list).

## The head FK chain

`setMtx`: base = `transS(current.pos) · ZXYrotM(current.angle)` (angle x/z are 0 in this regime,
so base = translate · RotY(travel)); then the zl.bdl chain `world_root(0) -> stomach(1) ->
chest(2) -> neck(5) -> head(6)` posed by the playing BCK via `mDoExt_McaMorf` (single anim +
8-frame quat-lerp morf on anim switches -- the same old-pose blend machinery as Link's engine;
all chain scale tracks are static 1.0, so the Maya scale/SSC branches are no-ops). Two node
callbacks apply the look-at:

- **chest** (`_nodeCB_BackBone`): `M · RotX(backbone_y) · RotZ(-backbone_x)` -- propagates to
  neck + head;
- **head** (`_nodeCB_Head`): records the head world origin, then the negative HALF angles as
  above (mDoMtx JMAS-table rotations, post-multiplied).

## The look-at chase (`dNpc_JntCtrl_c::lookAtTarget_2`)

Every execute frame `lookBack` runs the chase with source = `(pos.x, eyePos.y, pos.z)` (her PRE-
move position, her own previous eye height) and target = `dNpc_playerEyePos(-20)` =
`(link.pos.x, mHeadTopPos.y - 20, link.pos.z)` -- Link's exec-pass head-top Y over his feet
(`FootFK.head_top`: `anmMtx(head_jnt 15) · (40,0,0)`, written right after the same
`mpCLModel->calc()` setCollision reads). The yaw delta splits between head and backbone through
the `chkLim` clamp cascade (head first or backbone first, keyed on the old backbone target's
sign); elevation splits head-clamp-first. All four angles chase their clamped targets with
`cLib_addCalcAngleL(angle, target, 4, step, 4)` where `step` = **0x1000** while `field_0x7BC < 0`
(the courtyard case, live-probed) else 0x0180. The body-turn branch (`mbTrn`) is blocked in the
stt-3 regime (`optn_1` sets `field_0x7D8`), so her `current.angle.y` never moves.

## The stt-3 anim machine (what plays while she is plowed)

`setStt(3)` -> **wait03.bck** (40f, LOOP, rate 1.0, morf 8) and seeds the look-around countdown
`field_0x7B8 = rnd(90, 180)`. Each `optn_1` frame (in plow range, no talk) decrements it; at 0
she switches to **look.bck** (80f, LOOP, morf 8) with `field_0x84D = 0` (target released -> the
chase decays home) for `(g_Counter & 1) + 1` anim wraps, then returns to wait03 and **reseeds
7B8 from the global RNG stream** -- unmodelable offline, so the model flags `rng_horizon` there
(same guard class as the stt-4 follow warning). At the courtyard f0 the timer reads 116, so the
look anim never fires inside the ~45-frame window; a plan that runs longer than the seeded
timer + one look cycle (~200+ frames) crosses the horizon.

## Hidden seed state (what `capture_push seed` now captures)

`Zl1Look.seed_from_row` consumes the `zl1` block of `fixtures/courtyard_push_seed.json` (same
shape as the probe fixture rows): the four chased `mAngles` + the clamped targets
(`f2C/f2E/f30/f32`), `mbTrn`, the McaMorf frame ctrl + cur/prev morf + step, the current anim
number (`f849`), the timers `f7B8/f7BA/f7BC`, the wrap flag `f7C3` + `mFrame`, the half-angles
`f83C/f83E`, her `eyePos`, and `travel`. A morf ACTIVE at the seed would also need the per-joint
old-pose store (not the case at the courtyard f0 -- `cur_morf == 1.0`).

## Open

- **Link's own head-look (`m3564`)** -- MODELED + live-validated (session 21): her elevation
  chase consumes his twisted `mHeadTopPos.y` via [link-head-look.md](link-head-look.md)
  (`FreeRun(neck=)`); the former <=16-BAM facing echo is closed (facing bit-exact in the
  capture-tight replay, `tests/test_neck_look.py`).
- Her `pos.y` is tracked static in the replay (live CrrPos wiggles it ~1e-5 u) -- a last-bit
  echo in eye/tattn Y only.
- The morf (anim-switch) pose path is decomp-faithful but has no live ground truth yet (no
  switch occurs in the gated window); a look-anim window capture would gate it.
