# Land movement: walk/run, brakeslide, EBS

**Answers:** How does on-ground walking accelerate? What are the two movement angles? What is a
brakeslide / extended brakeslide (EBS)? Why does holding ESS left/right preserve speed "almost
forever"? Is speed preservation governed by facing or travel?
**Status:** validated live (2026-07-04). The **flat-ground walk is fully simulated** (`superswim.land`):
`mNormalSpeed` + state machine **and now `speedF`/position are BIT-EXACT** (position d=0.0000 vs live,
via the ported J3D anim engine — see below). Locked by `tests/dolphin/run_land_tests.py`: `walk_run` is
**sim-vs-live (pos_z bit-exact)**, the other 4 (brakeslide/EBS/facing) remain live-behavior locks
(ATN_MOVE = next tier). Anchor `land_flatwalk@twwgz.sav`.
**Source:** live captures (`harness/capture/land_capture.py`, cross-checked advancewith == advanceseq
== DTM movie); decomp `d_a_player_main.cpp` proc enum + `setSpeedAndAngleNormal`/`setNormalSpeedF` +
`posMoveFromFootPos` + `mDoExt_MtxCalcAnmBlendTblOld` (the foot-chain anim path).

> First land-movement page. Land is the next target after superswim; see the architecture forward-plan
> `_notes/tww-sim-architecture-design.md` §5b. Fields logged via `dolphin_mem` named reads
> `travel_angle` / `shape_angle_y` / `target_angle` / `csangle` / `potential_speed` (see
> [addresses](../reference/addresses.md)).

---

## Two movement angles (the core of land, unlike swim)

Land separates **two** headings that swim kept fused:
- **travel** = `current.angle.y` (velocity direction), read as `travel_angle`.
- **facing** = `shape_angle.y` (visual body direction), read as `shape_angle_y`.

`potential_speed` is **signed** relative to facing (negative = moving opposite to facing). World
motion = |speed| along (facing + 180° if speed<0). All ground tech below lives in how these three
(facing, travel, speed-sign) diverge. The stick's world target is `target_angle = m34DC(stick) +
csangle` — camera-relative, so `csangle` is a first-class input, not a constant (swim could pin it).

## Walk / run acceleration (baseline)

From idle (state 5/4), full stick accelerates straight to the run cap **`mMaxNormalSpeed` = 17**
units/frame via `setNormalSpeedF` — **no walk-before-run plateau** (an apparent ~16-frame 5.0 plateau
in an early capture was a phantom **front roll**, state 30, from a stray button — not a mechanic).
- **2-frame input latency** on both press AND release (the game acts on the stick delivered 2 frames
  earlier — one constant reproduces both edges; `superswim.land.INPUT_DELAY`).
- **Accel = +3.5/frame** exactly: `dVar9 = cM_scos(0)·field_0x14·msd²` (`field_0x14 = 3.5`), injected
  straight into `mNormalSpeed` by `setNormalSpeedF`, clamped to the cap.
- **Decel on release = `cLib_addCalc(mNormalSpeed, 0, 0.6, 2.5, 1.8)`** (HIO `field_0x24/0x1C/0x20`):
  `17→14.5→12→9.5→7→4.5→2→0.2→0` — the constant `−2.5/frame` while far from 0, then the cLib min-step
  snap tail (not a flat −2.5). Clean stop (state 4).
- proc = `daPyProc_MOVE_e` (state **6**). On flat, wall-free ground, collision (`mAcch` wall/slope) is
  inert, so `mNormalSpeed` is pure 1-D physics — **transcribed bit-exact** in `superswim.land`.

**Position ≠ `mNormalSpeed`.** The pos integrates **`speedF`** (true_speed), a **blend** of the
potential speed and the foot-plant delta. The composition is now known **bit-exact** (verified 0-ULP
across an accel+cruise+decel arc, `land_walk_anim.csv`):

```
speedF = f32( mNormalSpeed·(1 − m3598)  +  f31_2·m3598 )
```
- **`m3598`** = the WALK↔DASH **blend factor** (`blend_move`, pointer-off `0x34C0`). On the flat on-axis
  walk it is a **closed form in the (already bit-exact) `mNormalSpeed`**, no animation state needed:
  `m3598 = clamp( f32(2·(1 − mNormalSpeed/17)), 0, 1 )` — bit-exact (the op order matters: divide by
  17 first, subtract from 1, ×2; the reversed order misses by 1 ULP). ⇒ `m3598 = 0` at cruise
  (`mNormalSpeed = 17`), ramps to 1 as speed falls below ½·max. **Needs off-axis/partial-stick
  validation** before trusting beyond the on-axis walk (it may really be a frame-controller ratio that
  only *coincides* with this form when `msd = 1`).
- **`f31_2`** = the **planted foot's XZ displacement** this frame (`foot_delta_prev` / `m359C`,
  pointer-off `0x34C4`) — the genuinely animation-driven term (`posMoveFromFootPos` reads the WALK/DASH
  foot-joint matrices; plant = the foot with lower Y). It is a per-frame *delta* of a joint world
  position, so it is reproduced by the **ported J3D animation runtime** (`superswim.anim`), not a table.

**The foot-plant subsystem is now BUILT and bit-exact** (`superswim.anim`, FMA-faithful: single
fused-multiply-add via an f64 intermediate, `superswim.fp`). The chain, all offline: `UnderAnimState` (the `setBlendMoveAnime`/`setMoveAnime`/`J3DFrameCtrl`
state machine → which anims fill MOVE0/MOVE1, their frame-ctrl frames, the blend ratio, and `m3598`,
driven by the bit-exact `mNormalSpeed`) → `FootFK` (reduced foot-chain forward kinematics: BCK Hermite
keyframe eval → euler→quat → `QuatLerp` blend → `PSMTXQuat`/`Concat`/`MultVec`, plus the walk-entry
**oldframe-morf**) → `posMoveFromFootPos` (plant select, the 1-frame-delayed toe delta `f31_2`, the
recursive smoothing gate, and the `speedF` composition). `superswim.anim.foot_speedf.FootSpeedF` is the
whole thing; `LandState` drives it each frame → **`speedF` matches live to ~1e-5 across accel/cruise/
decel including the standing→walk entry and the stop; final `pos_z` bit-exact (d=0.0000)**.
- The steady-walk pose is the **DASH** anim (cruise = both slots DASH, ratio 1); the arc is
  FREEB(idle)→WAITS→WALK→DASH→WALK→WAITS. The standing→walk **entry** frame's `f31_2` is the FREEB idle
  drift `absXZ(FK(FREEB@f+2) − FK(FREEB@f+1))`, so the engine advances the standing idle through the
  input-latency frames to get it exact.
- **Cruise needs none of it** — since `m3598 = 0` at `mNormalSpeed = 17`, `speedF = mNormalSpeed` exactly;
  `f31_2` only bends position during the ~11 transient frames (accel + release decel).
- **Copyright:** the anim keyframe DATA (Link.arc/LkAnm.arc) is gitignored under `_generated/anim/` and
  dev-supplied from the user's own ISO — **not shipped**. When absent, `LandState` falls back to a
  calibrated `cLib` chase (endpoint ±3) so the package still runs; the offline golden tests SKIP.

## Brakeslide (L held)

From a run, **press L (target) + full-down for 1 frame, keep L held, then hold ESS-down** `(128,110)`:
- proc → **`daPyProc_ATN_MOVE_e` (state 7)** — the targeting-move proc.
- **facing LOCKS** at the run heading (targeting holds it); travel flips to 180° (a 180° facing/travel
  split); speed goes negative (backward-representation) but world motion continues forward.
- speed bleeds **~−0.14/frame** — a braking slide.

## Extended brakeslide (EBS) — release L

Same start, but **release L after the 1 full-down frame**, then hold ESS:
- proc drops out of targeting to **`MOVE` (state 6)**; facing unlocks.
- momentum bleeds **~13× slower (~−0.011/frame)** than the brakeslide — the "extended" part.

## Camera-relative speed preservation (the EBS payoff)

Once in the EBS, the **held ESS direction relative to `csangle`** decides everything:
- **ESS steering facing TOWARD `csangle`** → decay collapses to **~−0.001/frame** — speed held *almost
  forever* (minutes).
- **ESS steering facing toward `csangle + 180°`** (straight away from camera) → the **normal −2.5/frame
  brake** engages → full stop in ~7 frames (state 4).

Which of left/right preserves vs brakes depends on the camera angle (with `csangle`=0: **left preserves,
right brakes**). The brakeslide brakes precisely *because* its facing points anti-camera.

**Facing, not travel, is the predictor.** In the decoupling test both directions hold near-identical
travel (~172°), yet the one whose *facing* rotates toward camera preserves and the one whose facing
stays anti-camera brakes — same travel, opposite outcome. (Mechanism not yet decomp-traced; observed.)

## Facing/travel decoupling (how to turn facing independently)

Timing matters: **ESS-down for exactly ONE frame, then ESS-left/right the very next frame (held)**
makes **facing rotate to the ESS direction (~90°) and lock there while travel stays at the slide
heading (~171°)** — a sustained ~80° facing≠travel split, speed preserved. (Holding ESS-down 3+ frames
first instead keeps facing glued to travel.)

## Values

| thing | value |
|-------|-------|
| run cap `mMaxNormalSpeed` | 17.0 (HIO `mMove.field_0x18`) |
| walk accel step | +3.5/fr (`field_0x14 = 3.5` × `cM_scos(0)` × `msd²`) |
| walk decel `cLib_addCalc(v,0, scale,max,min)` | scale 0.6 / max 2.5 / min 1.8 (`field_0x24/0x1C/0x20`) |
| input latency | 2 frames (press and release) |
| ESS down / left / right | `(128,110)` / `(110,128)` / `(146,128)` |
| decay: brakeslide / EBS / EBS-toward-cam / brake | −0.14 / −0.011 / ~−0.001 / −2.5 per frame |
| procs (`link_state`) | 4 WAIT · 5 FREE_WAIT · 6 MOVE · 7 ATN_MOVE · 30 FRONT_ROLL |

## See also

- [ESS](ess.md) — the same `(128,110)`-class stick position (land reuses the swim ESS coordinate).
- [Camera](camera.md) — `csangle` / `dCam_getControledAngleY`, here a live per-frame movement input.
- `superswim.land` (`LandState`) — the walk sim; `superswim.anim` (`foot_speedf.FootSpeedF` + the J3D
  engine) — the bit-exact `speedF`; `tests/test_land.py` (offline golden arc, incl. per-frame speedF/
  pos_z vs `tests/golden/land_walk_speedf.csv`) + `tests/dolphin/run_land_tests.py` (`walk_run`
  sim-vs-live pos_z bit-exact + 4 live locks).
- `_notes/tww-sim-architecture-design.md` §5/§5b — how land folds into the generalized proc-machine sim.
