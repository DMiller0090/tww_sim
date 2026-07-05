# The J3D animation engine — skeleton, keyframes, foot FK

**Answers:** How is Link's skeleton laid out (Maya, 42 joints)? What's the BMD/BCK → pose pipeline?
How does Hermite keyframe interpolation work? How is the foot chain posed (euler→quat→blend)? What is
the two-anim blend / `getRatio` / oldframe-morf? Why is the foot FK run in **world space**? What is
`jointCB1`? How does the foot toe become `speedF`? Where are the live oracles?
**Status:** validated — leg chain jnt0..jnt33 bit-exact vs live `anmMtx`; straight full-deflection
walk `pos_z` float-perfect AND `speedF` bit-exact through the entry transient (live `walk_run`
bit-exact). The two entry-transient residuals were root-caused + fixed 2026-07-04 (both f64-vs-f32
constant leaks, NOT the suspected Hermite/foot-IK frontier): the oldframe-morf counter was f64 (→
jnt0.z entry-morf now bit-exact) and the `f31_2` smoothing used f64 `0.3`/`0.7` (→ speedF frames 5/6
now bit-exact) — see [history/resolved-bugs](../history/resolved-bugs.md#walk-entry-transient--two-f64-vs-f32-constant-bugs-not-a-hermitefoot-ik-frontier).
The full-speed **slip** skid + reversed-walk arc is now `pos_z` bit-exact too — it was NOT a FK
residual but a missing `speedF < 0.05 -> 0` snap (`posMoveFromFootPos`, d_a_player_main.cpp:2418);
see [land-sim](land-sim.md#speedf-snaps-to-0-below-005-the-slip-skid-tail). Still open (all sub-ULP
foot-FK-chain frontier, none reaching position): deep-release `speedF` f37/f39 (1 ULP, root-caused
below), ATN/turn endpoints (ebs/brake_right/waitturn 1–2 ULP), Y171 toe.z.
**Source:** `tww_sim/core/anim/{j3d_eval,fk,foot_fk,quat,foot_speedf,anim_state}.py`; decomp
(`J3DAnimation.cpp`, `J3DJoint.cpp`, `m_Do_ext.cpp`, `d_a_player_main`) + live foot-toe oracle.
This engine is **core** (generic, FP-faithful); only [land](land-sim.md) consumes it today, but it is
not land-specific. FP rules it relies on: [fp-faithfulness](fp-faithfulness.md).

---

Land `speedF` (and thus position) is driven by the **planted-foot toe displacement** — a value the
game reads out of the fully-posed skeleton, not a closed-form curve. Reproducing it float-perfect
required porting the J3D animation runtime the way Nintendo's code runs it, op for op. (A dumped
integer-frame table + lerp is *not* bit-exact: the WALK/DASH toe track is Hermite-interpolated, with
real curvature inside one integer frame interval.)

## Skeleton (Maya, 42 joints)

Parsed from `Link.arc` → `cl.bdl`: **INF1** hierarchy + **JNT1** bind (`harness/anim/parse_bmd.py` →
`_generated/anim/link_skeleton.json`; anim data is copyrighted — regenerate locally, never commit).
- **42 joints**; matrix-calc type = **Maya** (`INF1 flags & 0xF == 2`). JNT1 stride is the standard
  **0x40** (the decomp `J3DJointInitData` 0x30 comment is misannotated).
- **Foot FK chain:** root(0) → center(1) → waist_chn(29) → waist(30) → {L,R}clotch(31/36) →
  legA(32/37) → legB(33/38) → foot(34/39); toe joints 35/40. No animated scale in the foot chain
  (scaleCompensate on 30/33/38 is inert — parent scale stays 1). BMD joint order == the `getAnmMtx`
  index; joint enum values aren't in the decomp headers, so identify WAIST/LFOOT/RFOOT by name from
  JNT1.

## Keyframe evaluation (BCK / ANK1, Hermite)

Body anims are `.bck` (ANK1 chunk) in `LkAnm.arc` (`harness/anim/parse_bck.py`). walk/dash: 42
joints, **frameMax = 32**, decShift = 1. Per joint, three TRS tracks each with keyframes
(stride 3 `time,val,tan` or 4 `time,val,tanIn,tanOut`).
- `j3d_eval.calc_transform` evaluates one joint's TRS at frame *f*: **scale/translate** via
  `JMAHermiteInterpolation` (f32, `JMath.cpp:82`); **rotation** via `hermite_s16` — an exact
  instruction port of the `J3DAnimation.cpp:342` inline asm (s16 loaded via `psq_l` `GQR5=S16`,
  scale0 = pure `(float)s16`), the authoritative form (not the C comment), then `(s32)v << mDecShift`.
- Keyframe lookup = bisect + endpoint clamp (`J3DGetKeyFrameInterpolation`). Results are cached per
  anm dict keyed **on the dict contents, not `id()`** (id reuse after GC corrupted `roll_settle`).

## Posing the foot chain (euler → quat → blend → matrix)

**Key discovery:** the CL lower body (`PART_UNDER`, the foot chain) is posed by
`mDoExt_MtxCalcAnmBlendTblOld::calc` (`m_Do_ext.cpp:1164`), **not** direct `J3DMtxCalcMaya`. So each
foot-chain joint matrix is built as:

1. euler s16 (half-angle s16/2) → quaternion — `JMAEulerToQuat` (**non-fused**, see
   [fp-faithfulness](fp-faithfulness.md#fma-fusion-vs-non-fusion-the-load-bearing-distinction)),
   `quat.euler_to_quat`.
2. optional **two-anim blend** — `JMAQuatLerp` (`quat.quat_lerp`: dot in f32, lerp in f64→f32,
   **no renormalize**), plus the non-fused translate/scale blend.
3. quaternion → matrix — `mDoMtx_quat = PSMTXQuat` (fused-then-scaled off-diagonals; `fres`+Newton
   reciprocal — [fp-faithfulness](fp-faithfulness.md#psmtxquat-reciprocal-and-the-fres-table)),
   `quat.psmtx_quat`; then `setJ3DData` writes the translate column (scale = 1, no-op).

The euler `J3DGetTranslateRotateMtx` path is WRONG here — it differs ~1.5e-3/joint (half-angle table
lookups), compounding ~0.16 over the chain.

### Two-anim blend & morf

Steady cruise is **pure DASH anim in both slots** (`getRatio(1) = 1.0`) — an earlier "walk.bck → slot
1" model was wrong and gave ~20-unit Z error. The arc is FREEB → WAITS → WALK → **DASH** → WALK →
WAITS; only the accel/decel transients (≈11 frames) actually blend two changing anims (that's why
they need the anim state machine — slot management + ratio ramp + frame-ctrl rates — while cruise
needs none: `speedF = 17` there). A transient walk-start also applies an **oldframe-morf**
(`mDoExt_MtxCalcOldFrame`, non-fused). The morf **counter** (`mOldFrameMorfCounter`) and the `i_morf`
trigger value (2.4) are **f32** — quantize the constant to f32 *before* the `-=1.0`, or the rate
lands 1 ULP low and the entry-morf jnt0.z is +5 ULP (see [history](../history/resolved-bugs.md#walk-entry-transient--two-f64-vs-f32-constant-bugs-not-a-hermitefoot-ik-frontier)).

## Foot FK runs in WORLD space

`posMoveFromFootPos` computes the stored toe `spB0 = m37B4 · anmMtx(FOOT) · l_toe_pos`, where
`anmMtx(FOOT)` is the **world-space** joint matrix (translations ≈ Link's world pos, `z ≈ 764`).
Although `m37B4 = PSMTXInverse(worldBase)` cancels `worldBase` *algebraically*, it does **not** in
f32: the FK accumulates each joint matrix at world magnitude, so each is quantized to ≈6e-5 (f32
spacing at 763); `m37B4` removes the base afterward but the rounding is already baked in. FK from
identity (local scale ≈ tens → ≈1e-6 quantization) misses this — the source of the old 1–2 ULP.

**Fix (shipped):** build `worldBase` offline — `fk.world_base = transS(pos.x, 0, pos.z) · Yrot(shape_angle.y)`
(base.y is 0 live; only the Y column, irrelevant to the XZ that `f31_2` uses) — and its rigid inverse
`m37B4`; run the chain from `cur = worldBase`, then apply `m37B4` (`FootFK` world mode).
`LandState.step` feeds the current pre-integration `pos.x/pos.z/facing` each frame via
`FootSpeedF.set_pos` — the FK quantizes the toe at world magnitude, so the driver **must** get the
live position each frame.

## `jointCB1` foot rebuild (not IK)

`daPy_lk_c::jointCB1` (a J3D node callback) rewrites the leg/foot `anmMtx` after the anim calc:
`anmMtx(LFOOT) = concat(anmMtx(LLEGB), Trans(oldTrans)·Quat(oldQuat)·ZrotM(field_0x002))`, using the
**old-frame** stored pose (`m_Do_ext.cpp:1219`) and per-foot leg-angle Zrots from
`footBgCheck`/`setLegAngle`. **On flat ground every leg-angle Zrot is 0** (verified live), so
`jointCB1` reduces to a pure rebuild that is bit-exact to the FK given the (now-exact) quats —
verified `concat(live_anm33, Trans·Quat[oldQuat34]) == live anm34`, 0 ULP. So there is **no foot-IK
snap on flat ground** (the earlier "ground-snap on the planted foot" guess was wrong).

## Toe → `speedF`

The planted foot is the lower-Y of the two; `f31_2 = absXZ(toe_delta_smoothed)` where the smoothing is
`f·0.3f + 0.7f·m359C_prev` — **non-fused**, and `0.3f`/`0.7f` are **f32 literals** (multiplying by
Python's f64 `0.3`/`0.7` rounds each product 1 ULP off → speedF −1 ULP through the entry). (`absXZ` =
the faithful `sqrtf(fmadds(...))`, see
[fp-faithfulness](fp-faithfulness.md#fma-fusion-vs-non-fusion-the-load-bearing-distinction)). `f31_2`
is the plant-foot XZ delta and the only anim-derived input to land `speedF`; how it composes into
`speedF` and position is [land-sim](land-sim.md).

### Deep-release `speedF` f37/f39 — a 1-ULP-low toe **X** FK residual (not the compose path)

The straight full-deflection walk's release tail (`msd=0`, `nspeed` decaying 17→0) is `speedF`-bit-exact
except frames 37 and 39 (±1 ULP). Root-caused 2026-07-04 by a live `spB0` decomposition (reload +
`advanceseq(WALK[:n])`, read the stored toe at `+0x3CF8`/`+0x3E10`):
- **The compose is provably exact.** At f36–f39 `m3598==1.0`, so `speedF = f31_2 = absXZ(plant_delta)`
  directly (no `nspeed` term, no smoothing). Feeding the **live** `spB0` toes into `absXZ` reproduces
  live `true_speed` byte-for-byte at 36/37/38/39. So the game's math is exactly what the sim models,
  and `_sqrtf`/`fmadds`/the smoothing are **not** the cause (the earlier "compose/msd f64 constant"
  guess was wrong).
- **The fault is the sim's drawn toe X, 1 ULP low.** Comparing the sim's drawn toe (`cur`) against
  live `spB0(N+1)`: the right-foot **X** is 1 ULP *low* at frames 34/35/38 and exact at 36/37/39; **Z
  is always bit-exact.** The low-X frames feed the plant delta at 37/39, flipping `speedF` 1 ULP.
- **It is NOT world-quantization.** With `facing==0` the straight walk has `px==0`, so `worldBase` and
  `m37B4` are exact identities on row 0 → the toe **X is effectively identity-space FK**; the
  world-magnitude quantization only lives in Z (which is exact). The residual is a frame-dependent,
  consistently-low sub-ULP rounding in the local foot-FK chain's X (quat→matrix / blend / concat),
  i.e. the same fundamental FK-chain frontier as the Y171 toe.z and the ATN/turn `jnt34` residuals.
- **It does not reach position:** the LandState `pos_z` arc + endpoint are bit-exact through the whole
  release (the 1-ULP `speedF` is absorbed when multiplied by `cos(travel)` and re-added at world
  magnitude). `tests/test_land.py::test_speedf_matches_live_bit_exact` is now **LandState-driven**
  (was the raw `FootSpeedF` driver, whose release-region `ns/msd` diverge and read tens/hundreds of
  ULP off — a harness artifact, cf. the Y171 test c056bba), so it surfaces only the genuine f37/f39.

## Live oracles (for re-validation)

- `mBaseTransformMtx` = `mpCLModel@obj+0x32C → +0x24`; `m37B4` = `obj+0x37B4`.
- per-joint `anmMtx(j)` = `obj+0x32C → mpNodeMtx@+0x8C → [j]` (48-byte `Mtx`; `LFOOT = 0x22`,
  `RFOOT = 0x27`). Align by `anim_frame` (`sim(N) == live(N)`).
- stored `spB0` toe: `mFootData[i].field_0x018` (foot0/R `+0x3CF8`, foot1/L `+0x3E10` from base
  `0x803AD860`) — **lags one frame** (`sim toe(N) == live field_0x018(N+1)`).
- `oldQuat` array: `m_old_fdata@obj+0x31B4 → +0x20` (`Quaternion[jnt]`); `mOldFrameTransInfo`:
  `→+0x1C` (`J3DTransformInfo[jnt]`, translate at `+0x14`).
- frame controllers: `mFrameCtrlUnder[2]@class 0x302C` (dash `mFrame` ptr `0x2F64`, walk `0x2F78`);
  ratio(1) `0x2EE4`; loaded res idx `0x2F04`/`0x2F14`.

## See also

- [FP faithfulness](fp-faithfulness.md) · [Land sim](land-sim.md) ·
  [Land movement](../mechanics/land-movement.md) · [Animation / head-bob (swim)](../mechanics/animation.md).
