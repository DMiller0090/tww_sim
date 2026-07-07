# Constants — canonical values

**Answers:** What is the value of <some superswim constant>? Deadzone? Stick divisor? The
turnaround angle threshold? Animation wrap points? The strobo band speeds?
**Status:** validated (decomp + live) unless a row says otherwise.
**Source:** per-row. This is the single source of truth — other pages link here instead of
restating. If a number elsewhere disagrees with this table, this table wins and the other page
is wrong.

> Scope note: this table currently covers the **stick / speed / animation / turnaround / strobo**
> constants (the pilot slice + shared foundation). Camera, balloon, and planner constants are
> added as those topics migrate.

---

## Stick geometry

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| Neutral | `(128, 128)` | center; inside the dead zone → no swim input | decomp `PADClamp` |
| Radial dead zone | **15** | raw units removed around neutral before any input registers | `PADClamp` (GC SDK) |
| Main-stick divisor | **54** | `mPosX = stickX / 54` after dead-zone removal | `JUTGamePad::CStick::update` (JUTGamePad.cpp:303-310) |
| Cardinal ESS offset | **18** | min registered deflection, e.g. `(128, 110)` | live |
| Diagonal ESS offset | **17** per axis | e.g. `(111, 111)`; magnitude ~24 but smaller per-axis | live |

**Stick distance:** `mStickDistance = clamp((|raw − 128| − 15) / 54, 0, 1)` (cardinal).

**Swim-input gate:** a frame counts as a swim input iff **`mStickDistance > 0.05`**
(`d_a_player_main`), i.e. `hypot(dz_x, dz_y) > 2.7` after dead-zone removal — a *radial* test,
not the dz-15 *square*. They differ only on a thin ring (~260 cells) just outside the square where
one axis is 1–2 past the dead zone but the radial magnitude is still ≤ 0.05; the game blocks the
tiny gain there. The sim uses this exact gate (`sim.stick_angle_deg` returns `None`), bit-identical
to the gold stick table's `value ≤ 0.05` (locked by `tests/test_stick_table_integrity.py`). Real
routes never hit the ring (they use full deflection, ess `(128,110)`, or true neutral).

## Speed deltas

Per frame, to potential speed:

| Regime | Δ potential speed | Notes | Source |
|--------|-------------------|-------|--------|
| Charge (on-axis) | **+3** | full alternating deflection; `×cos(angleΔ)` if tilted | `setSpeedAndAngleSwim` (d_a_player_swim.inc:41,66) |
| ESS cardinal | **−1/6** (≈ −0.1667) | min non-neutral hold, e.g. `(128, 110)` | live (exact) |
| ESS diagonal | **−0.1571** | octagonal geometry removes slightly more → more efficient | live |
| Neutral | **−2** | dead zone, separate code path (drag-free) | live (exact) |
| Saturation | flat **−3** | reached at off ≥ 70 (stickY ≤ 58) | live |
| Max normal speed | **18** | `maxNormalSpeed`, HIO mSwim | decomp |

**Decay law (any registered input):** `decay = clamp((|raw − 128| − 15) / 54, 0, 1) · 3`.
Piecewise-linear, exact to ~off 63; a ~1-unit shortfall appears in off 65–68 (PADClamp top-end
compression); saturates to exactly 3.0 by off ≥ 70.

## Speed gain while charging / arrow swimming

```
delta = mStickDistance · 3.0 · cM_scos(facing_after − facing_before)
```
- On-axis (Δ=0) → +3. Tilt α off the pure-back axis → `charge_rate = −3·dist·cos(2α)`.
- `mStickDistance` caps at 1 (live-confirmed); tilt changes the **cos**, not the magnitude.

## Animation

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| `End_swim` (ANM_SWIMING) | **23** | ESS anim wraps here (`nfmod(·, 23)`); = the `cos(π·x/23)` head-bob period | live (22.9965) |
| `End_wait` (ANM_SWIMWAIT) | **26** | neutral anim wraps here | live (25.997) |
| **x598** | **598** = 26·23 | the neutral→ESS anim-scramble multiplier (`End_wait · End_swim`) | derived + live |

**ESS anim increment / frame:** `|v|/36 + 3/5 + (1 − (air+1)/900)`.
**Neutral anim rate / frame:** `0.5 + 2.5·(1 − (air+1)/900)` (HIO `field_0x40 = 0.5`,
`field_0x70 = 2.5`). Speed-independent; rises as air depletes.

## Head-bob (animation-frame) drag → true speed

```
af_drag(v, anim) = 0.6·v + 0.4·v·|cM_scos(π·anim/23)|          # numerator
true_disp        = af_drag(v, anim) / (1 + 0.35·getSwimTimerRate(air))   # full true speed
```

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| `field_0x60` | **0.4** | head-bob cos weight (so base weight = 0.6) | decomp `d_a_player_main.cpp:2424-2428` |
| `field_0x7C` | **0.35** | swim-timer drag denominator coeff | decomp; backed out exact from live |
| `getSwimTimerRate` | `1 − air/900` | air term; decomp `1 − itemTimeCount·0.0011111111` | d_a_player_swim.inc:283 |

**`cM_scos` is the console cosine table, not `math.cos`** — a 4096-entry s16 table, low 4 bits
truncated (`index >> 4`, no interp). The ~5e-4 error vs true cos is amplified by the high-speed
exit and the x598 scramble; using `math.cos` breaks bit-exactness. See [glossary](glossary.md#cm_scos).

## Air

| Constant | Value | Source |
|----------|-------|--------|
| Max air | **900** | reset on swim entry (`changeSwimProc`, d_a_player_swim.inc:126) | 
| Air drain | **−1 / frame** | live |
| Cold-swim air budget | **≈ 900 frames** | 900 air ÷ 1/frame — a cold cruise from full air lasts this long before drowning; the planner enforces it (`allow_drown=False`) | derived |

## Turnaround / arrow angular budget

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| `0x6000` | **135°** | `DIR_BACKWARD` threshold: stick > 135° off facing → instant 180° snap | decomp `getDirectionFromAngle` (d_a_player_main.cpp:2278) |
| `0x2000` | **45°** | LEFT / RIGHT threshold | same |
| Arrow budget | **45°** off straight-back | the snap cone is 90° wide around 180°, i.e. stick < 45° off directly-behind | derived from `0x6000` |
| Gradual turn rate | **~7° / frame** | `cLib_addCalcAngleS` chase, used once the stick exceeds the 45° budget | live |
| Arrow tip-over | Xbias ≈ 190–200 (α ≳ 20°) | snap dies → forward release, speed LOSS | live |
| Arrow spin-up | **2 frames** | non-snap forward frames (−each loses ~+3/fr) before the 0↔180 swing locks in | live (sim.py) |

Angle units: `0x10000 = 360°`. World travel axis: `world_angle = stick_angle + csangle + 0x8000`.

## Stroboscopic bands

Band speeds solve `ESS increment = 23·k`, so they are **air-dependent**:

| Band | Approx |v| | Condition |
|------|-----------|-----------|
| k=1 | **≈ −794** (air 597) | increment ≈ 23 |
| k=2 | **≈ −1630** (air 900) | increment ≈ 46 |

The legacy "−850 / −1650" community figures are the same bands, off by the air dependence.

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| `charge_disp_factor` | **0.9466** | charge frames move ~5.3% LESS than ESS at the same (v,anim,air) | live (band 2 only — revalidate far from −1630) |
| `avg_ess_rate` | `(4+3π)/(5π)` | mean fraction of speed retained as displacement while ESSing | tool closed-form |

## Collision (player wall cylinders)

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| Wall radius | **35.0** | player wall-collision cylinder radius (standing/walking) — the "must-clear" distance for a seam clip | decomp `daPy_lk_c::setBgCheckParam` (d_a_player_main.cpp:10715) |
| Wall cylinder heights | **30.1 / 89.9 / 125.0** | the 3 `dBgS_AcchCir` heights above Link at which LineCheck/WallCorrect probe | decomp same fn |
| Point-in-triangle tolerance | **±20.0** (area units) | `cM3d_CrossX/Y/Z_Tri` signed-area edge slack, both windings | decomp `c_m3d.cpp` |
| `cM3d_IsZero` (kZero) | **1e-5** | float "is zero" threshold in the collision math | decomp `c_m3d.h` |

See [mechanics/seam-clip.md](../mechanics/seam-clip.md) for how these produce the seam clip.

## Collision (actor Co push)

The actor-vs-actor "Co" push (a [Tetra nudge](../mechanics/actor-push.md)). Distinct from the wall
cylinder above. All live-confirmed on GZLJ01 (2026-07-06).

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| Link Co radius | **30.0** (walking/rolling); 50.0 only if `checkGrabWear()` | Link body Co cylinder radius | decomp `daPy_lk_c::setCollision` (d_a_player_main.cpp:9762/9760) |
| Link Co height | **≈107** walking (`40.1 + neck−toe`); 81.25 in FRONT_ROLL | Link body Co cylinder height | decomp same fn (:9794/9780) |
| Link Co center | midpoint(root_jnt, neck_jnt) XZ; toe_jnt Y (feet in FRONT_ROLL) | animation-driven, **not** `current.pos` | decomp same fn (:9753/9792) |
| Tetra Co radius / height | **50.0 / 140.0**, center = `current.pos` | Tetra (`Zl1`) body Co cylinder | live read |
| Link weight / rank | **120** → rank **5** | `mStts.SetWeight(120)`; `dCcS::GetRank` | decomp `:11233`, `d_cc_s.cpp:153` |
| Tetra weight / rank | **0x8C=140** → rank **5** (the `field_0x84F==5` variant; else 0xFF→10) | live read | decomp `d_a_npc_zl1.cpp:428` |
| Push share (rank 5 vs 5) | **0.50 / 0.50** | `rank_tbl[5][5]=50` → Link takes 0.50× depth, Tetra recoils 0.50× | decomp `d_cc_s.cpp:138`, live |
| Co deadzone | **1e-5** (`cM3d_IsZero(cross_len)`) | `dCcS::SetPosCorrect` skip threshold (base `cCcS` uses 1/125) | decomp `d_cc_s.cpp:190` |

The **game uses `dCcS::SetPosCorrect`** (virtual override, JP 0x800AB1E4), whose weight split is the
`rank_tbl` above — NOT the base `cCcS` mass-proportional split (JP 0x8024101C, never fires live).

<a id="land-sword-cut-roll-stab"></a>
## Land sword-cut (roll stab)

The [roll stab](../mechanics/land-movement.md#roll-stab-sword-thrust-out-of-a-roll--the-seam-clip-lunge):
a sword cut fired out of a FRONT_ROLL. HIO `daPy_HIO_cutF_c1`/`cutA_c1`
(`d_a_player_HIO_data.inc:31/27`); procs `d_a_player_sword.inc:660/430`. Live-validated bit-exact (0 ULP,
GZLJ01 savestate 7, 2026-07-06). Only the joint-0 (root) translate of `cutf.bck`/`cuta.bck` is used.

| Constant | CUT_F | CUT_A | Meaning (field) |
|----------|-------|-------|-----------------|
| anim frame ctrl rate | **1.2** | 1.2 | `mFrameCtrlUnder[MOVE0]` rate (field_0x4) |
| anim start frame | **4.0** | 4.0 | `setSingleMoveAnime` start (field_0x8); `+1.2/frame`, `EMode_NONE` end 19 |
| checkPass launch frame | **6.0** | 6.0 | `field_0x28` → set `mNormalSpeed` |
| `mNormalSpeed` launch | `\|speedF\|·0.2 + 8.0` | `\|speedF\|·0.2 + 10.0` | field_0x10 mult / field_0x14 add |
| decel maxStep / minStep / scale | **0.95** / 0.5 / 0.7 | **2.6** / 0.5 / 0.7 | `cLib_addCalc` (field_0x18/0x1C/0x20) |
| early-exit frame → WAIT | **17.0** | 16.0 | `getFrame() > field_0xC` → `checkNextMode(1)` |
| first-frame lunge (from a 26 roll) | **49.220** | 49.220 | `speedF 26 + m3700.z(4.0)=23.220` (posMove m34C2==1) |

The lunge = `speedF` (foot term, along `current.angle.y`) + the root-translate delta `m3700(t)−m3700(t−1)`
(rotated by `shape_angle.y`); `m3700` is reset to 0 in `procCut*_init`, so frame 1 stacks the full root
translate onto the carried roll speed. See [land-movement.md](../mechanics/land-movement.md#roll-stab-sword-thrust-out-of-a-roll--the-seam-clip-lunge)
and [seam-clip.md](../mechanics/seam-clip.md).

## Camera (steering) — summary (full table migrates with the camera topic)

| Constant | Value | Meaning | Source |
|----------|-------|---------|--------|
| Camera-rate smoothing `k` | **0.5** | `omega_t = omega_{t-1} + (cmd − omega_{t-1})·0.5` | live ([camera](../mechanics/camera.md)) |
| Camera-rate saturation | **±3.0° / frame** (±546/−547 hw) | full C-stick X deflection | live |
| substickX dead zone | up to ~149 (Δ ≤ 21) | no camera rotation below this | live |
