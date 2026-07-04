# The offline sim — precision & calibration

**Answers:** Why does the sim use f32 / ctypes? Why a baked console cosine table? What's
CHARGE_DISP_FACTOR? What are the four charge-frame lags? How is a cold start seeded? How accurate
is it?
**Status:** validated bit-exact (v/anim/air/state) over full cold-start swims.
**Source:** `superswim/sim.py`, `superswim/coldstart.py`; decomp + live calibration.

---

The library reproduces the swim physics with **no Dolphin dependency** (`superswim/sim.py`). It is
bit-exact for potential speed / anim / air / state; x/z displacement is a wave-affected byproduct
(well-modeled in aggregate, not bit-checked per frame). Three things make bit-exactness possible:

## All swim math runs in f32

The GameCube is single-precision. The sim uses `ctypes.c_float` throughout — f64 drifts ~0.013 anim
/ 0.004 v over ~480 frames, enough to land the wrong [exit phase](../mechanics/neutral.md). Op
**order** matters too: `af_drag` and `release_ess_speed` use *different* f32 orderings (matching two
different decomp expressions); the old shared ordering caused a ~2 ULP error that the
[x598 scramble](../mechanics/pumps.md#the-x598-scramble) amplified at pump exits.

## Land position accumulates in f32 (not an f64 running sum)

`pos.x`/`pos.z` are **f32 fields** in the game (`cXyz`), so every frame the game re-stores the running
total as f32: `pos.z = f32(pos.z + f32(speedF·cos))`. `LandState.step` therefore accumulates position
in f32 too — `self.pos_z = f32(self.pos_z + f32(d·cos))`, **not** a Python-f64 `+=` running sum. An
f64 running sum is *more* precise than the hardware and drifts ~**2.5 ULP** (~0.0003u) from the game's
f32-accumulated position over a ~115-frame walk — precisely the wrong direction for float-exact work.
With f32 accumulation + the world-space foot FK the sim is now **float-perfect (0 ULP)** over the straight
walk (see [land-movement: float-exact stop](../mechanics/land-movement.md)); the last residuals are the
planted-foot jnt34/39 toe (1–2 ULP on the ATN/waitturn tails) and the separate slip skid. The chain was
localized against a live foot-toe oracle (`mBaseTransformMtx`, `m37B4`, per-joint `anmMtx`, stored spB0):

- **Sin/cos tables (FIXED, verified bit-exact vs console).** `JMAEulerToQuat` uses `JMASSin`/`JMASCos` =
  a *separate* console `jmaSinTable` (`jmaCosTable = jmaSinTable + 1024`, `jmaSinShift=4`, size 4096), not
  a −1024 view; the old wrap-around reconstruction was 1 ULP off at **816/4096** entries. Baking the real
  `jmaSinTable` (`tables/sin_table.bin`, `sim._SIN_TABLE`) fixed it and made `roll_slow` bit-perfect. Both
  baked tables were re-verified against the live console (`jmaSinTable` ptr @ `0x803EAE28`): **0 mismatches**
  across all 4096 sin AND cos entries. The tables are NOT a source of any remaining residual.
- **Foot FK runs in WORLD space (FIXED).** `posMoveFromFootPos` computes `spB0 = m37B4 · anmMtx(FOOT) ·
  l_toe_pos` where `anmMtx(FOOT)` is the **world-space** joint matrix (translations ≈ Link's world pos, e.g.
  `z≈764`). Although `m37B4 = PSMTXInverse(worldBase)` cancels `worldBase` *algebraically*, it does NOT in
  f32: the FK accumulates each joint matrix at world magnitude, so each is **quantized to ≈6e-5** (f32
  spacing at 763); `m37B4` removes the base afterward but the rounding is already baked in. The old
  identity-space FK (local scale ≈ tens → ≈1e-6 quantization) missed this → 1–2 ULP. **Fix:** the sim now
  builds `worldBase` offline (`fk.world_base` = `transS(pos.x, 0, pos.z)·Yrot(shape_angle.y)`; base.y is 0
  live and only Y-column, irrelevant to the XZ that `f31_2` uses) and its rigid inverse `m37B4`, runs the
  chain from `cur = worldBase`, then applies `m37B4` (`FootFK` world mode; `LandState.step` feeds the
  current pre-integration `pos.x/pos.z/facing` each frame via `FootSpeedF.set_pos`). Live oracle:
  `mBaseTransformMtx` (`mpCLModel@obj+0x32C → +0x24`), `m37B4` (`obj+0x37B4`), `anmMtx(j)` (`→+0x8C → [j]`,
  48 B `Mtx`; `LFOOT=0x22`, `RFOOT=0x27`), stored `spB0` (L `obj+0x3DB8+0x130`, R `+0x18`).
- **`PSMTXQuat` grouping + reciprocal (FIXED).** `mDoMtx_quat` = retail **`PSMTXQuat`** (paired single),
  NOT `C_MTXQuat`: off-diagonals are **fused then scaled** — `m[0][1]=(x·y−z·w)·s` via `ps_msub`. The scale
  `s = 2/denom` must use the console's **`fres`+Newton reciprocal**, reproduced bit-exactly by an
  accurate-seed Newton refine (`quat._recip2_of`, `scale_mode='newton'`, the default). This matters at
  half-ULP division midpoints: a single-axis joint's `denom = cos²+sin² = 1 − 2⁻²⁴` (e.g. jnt29
  `[0,16382,0]`) is exactly such a midpoint where the console gives **`fdivs − 1 ULP`**; raw `fdivs` is 1
  ULP high and the literal `_fres` table is ≈7 ULP low. **With world FK + `newton` the leg chain jnt0..jnt33
  is BIT-EXACT vs the live `anmMtx`, and the straight walk `pos_z` is float-perfect end-to-end.**
- **`JMAEulerToQuat` is NON-fused (FIXED).** The "planted foot jnt34 ~1 ULP" residual was a real bug in
  `euler_to_quat`: `JMAEulerToQuat` (JMath.cpp:41) computes each component as `(a·b) ± (c·d)` with BOTH
  products **separately f32-rounded, then added/subtracted** — NOT fused into `fmadds`/`fnmsubs`. The old
  code fused `x` and `y`, which put jnt34's quat 1 ULP off. Verified against the **live `oldQuat` array**
  (`m_old_fdata@obj+0x31B4 → +0x20`, a `Quaternion[jnt]` of `x,y,z,w`): with the non-fused form ALL
  foot-chain joints (32/33/34, 37/38/39) are bit-exact at both the idle and the walk-blend frames. (The
  earlier "foot-IK ground snap" guess is WRONG — see below.)
- **jointCB1 foot rebuild (CONFIRMED, not IK).** `daPy_lk_c::jointCB1` (a J3D node callback) rewrites the
  leg/foot `anmMtx` after the anim calc: `anmMtx(LFOOT) = concat(anmMtx(LLEGB), Trans(oldTrans)·Quat(oldQuat)·
  ZrotM(field_0x002))`, using the **old-frame** trans/quat (this frame's post-morf stored pose, m_Do_ext.cpp:
  1219) and per-foot leg-angle Zrots from `footBgCheck`/`setLegAngle`. **On flat ground every leg-angle Zrot
  (`field_0x002/006/008/00A`) is 0** (verified live), so `jointCB1` reduces to a pure rebuild that is
  bit-exact to our FK given the (now-exact) quats — verified `concat(live_anm33, Trans·Quat[oldQuat34]) ==
  live anm34`, 0 ULP. So there is NO foot-IK snap on flat ground.
- **OPEN (sub-ULP): m3598-MIXED speedF frames + ATN/slip tails.** With exact quats + `set_pos` fed each
  frame, the walk `speedF` is bit-exact EXCEPT the walk↔dash-blend frames where `0<m3598<1` (frames 5/6/34):
  a ~1 ULP in the world-magnitude **matrix accumulation** (concat/PSMTXMultVec rounding), NOT the quat, NOT
  the recursive smoothing (all fusion variants agree), NOT the composition. It does not affect the (bit-exact)
  walk position. NOTE: the offline `test_speedf` does not feed per-frame `pos` to the standalone `FootSpeedF`,
  so its `worldBase` is frozen at the anchor → feeding pos flips 5 of its 8 red frames; the LandState-based
  position tests already feed pos. The `slip` case (74 ULP) is a separate skid modelling gap.

**This is now enforced to the byte** by two tests with distinct jobs:
- **Live** (`tests/dolphin/run_land_tests.py`, the accuracy gate — live is the source of truth): the
  pass condition is **float-perfect, 0 ULP vs live**, with NO tolerance and NO xfail. With the world FK +
  `newton` reciprocal it is **9 pass / 4 fail**: `walk/brakeslide/face_left/roll_run/roll_slow/roll_settle/
  roll_ebs/moveturn` pass (0 ULP), while `ebs (1), brake_right (2), waitturn (2)` (the planted-foot
  jnt34/39 residual) and `slip (74 ULP, a separate skid residual)` FAIL. Those are the to-do list.
- **Offline** (`tests/test_land.py`, no Dolphin): the token-cheap **shadow** of the live gate — the
  golden (`tests/golden/land_walk_speedf.csv` + `CASE_POSZ`) is the GAME's live f32 bytes (captured by
  `tests/gen_land_golden.py`), and the tests assert `f32_bits(sim) == live`, so the SAME techs fail here
  (5 red today: `speedf` frame 5, `ebs`, `brake_right`, `waitturn`, `slip`). The walk arc is now
  float-perfect every frame. Regenerate the golden from live after a sim fix via `python tests/gen_land_golden.py`.

## Console cosine table

`cM_scos` indexes the **real console table** dumped live from `jmaCosTable` @ `0x80498168`, not
`math.cos`. The game builds the table with PowerPC libm; an x86 recompute differs at **2964/4096
entries** (max 4.17e−7, 1–2 ULP). x598-amplified, that 1 ULP became a **0.07 potential-speed jump**
at pump exits. The table is 4096 entries, indexed by the s16 angle with the **low 4 bits truncated**
(`index >> 4`, no interpolation). Also: `J3DFrameCtrl::update` is replicated as a **repeated f32
subtraction loop** (not a single modulo) so post-x598 the anim loops down with the console's exact
rounding (~0.004 entry residual otherwise).

## Charge-frame model (four 1-frame lags)

Charging is governed by four separate live-calibrated lags (each measured against unrounded RAM):
1. **Anim-rate lag** — the anim controller advances using the PREVIOUS frame's speed; advance anim
   *before* applying the speed change.
2. **Swim-gain lag (uniform)** — the `setSpeedAndAngleSwim` gain (charge +3 *and* the ESS
   facing-gain alike) lands on the NEXT frame, replacing that frame's decay. ESS and charge use
   the SAME 1-frame deferral (as `ArrowState` does). The earlier asymmetric same-frame-ESS /
   lagged-charge split dropped a partial hold's last gain at a hold→charge boundary — see
   [resolved BUG #3](../history/resolved-bugs.md#bug3--partial-hold-gain-dropped-at-a-holdcharge-boundary).
3. **First-charge decay** — the first `chg` of a burst still applies the normal ESS decay; +3
   engages from the 2nd frame.
4. **Facing flip** — each `chg` toggles a 180° facing flip applied the next frame; even-length
   bursts return to the original heading.

`CHARGE_DISP_FACTOR = 0.9466` — charge frames move ~5.3% LESS than ESS at the same (v, anim, air).
Measured live band-2 (ESS 1463.60 vs charge 1385.44 at v=−1632, anim=17.66, air=895). **Band-2 only
— revalidate far from −1630.**

## Cold-start seeding (the mRate rule)

A cold start is hypersensitive to the seed: a seed anim rounded to 4 digits (vs the true
0.06392288…) drifts ~2e−5 → ~0.012 anim after the cold-start x598 scramble → a *completely different*
swim (one test reached 1408 vs 3004). **Always seed the full-precision live anim.** The cold-start
scramble oldframe is:

```
oldframe       = f32( f32(anim_seed + mRate_seed) + neutral_anim_rate(air_seed − 1) )
scramble_anim  = f32( f32(oldframe · 26.0) · 23.0 )
```

`mRate_seed` (the MOVE0 anim-rate at seed) **must be LOGGED live** — it carries pre-seed air history
and cannot be recomputed from a snapshot. (`coldstart.py`; cold-start uses logged mRate, warm pumps
recompute `neutral_anim_rate(air−1)` — different entry histories, different rules.)

## Accuracy

Against a full-precision RAM capture: per-frame anim to **0.00002**, v to **0.0003**. On a 150-frame
ESS run vs Dolphin: cumulative path error **−0.02%**, mean per-frame step **0.15%** (excluding 2
Dolphin auto-camera glitch frames). The earlier "1–3% gap" was the four lags + the cosine table —
all resolved.

## See also

- [Planner](planner.md) · [Predictors](predictors.md) · [Animation](../mechanics/animation.md) ·
  [Pumps / x598](../mechanics/pumps.md) · [history/resolved-bugs](../history/resolved-bugs.md).
