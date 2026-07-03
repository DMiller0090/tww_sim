# Land movement: walk/run, brakeslide, EBS

**Answers:** How does on-ground walking accelerate? What are the two movement angles? What is a
brakeslide / extended brakeslide (EBS)? Why does holding ESS left/right preserve speed "almost
forever"? Is speed preservation governed by facing or travel?
**Status:** validated live (2026-07-04). The **flat-ground walk, the ATN_MOVE tier (brakeslide /
EBS / facing decouple / brake), AND the forward roll (FRONT_ROLL — entry→standstill and the
frame-perfect roll-EBS exit) are fully simulated** (`superswim.land`): `mNormalSpeed` (signed), the
proc state machine, **facing (`shape_angle.y`) and travel (`current.angle.y`) are all BIT-EXACT** vs
live, and the walk + roll `speedF`/position is bit-exact too (d≈0.0001, via the ported J3D anim
engine — see below). Locked by `tests/dolphin/run_land_tests.py`: **9 sim-vs-live cases** (nspeed
dv=0.00000, facing/travel d=0.0000°) + the `wiggle_ebs_roll` DTM-playback lock. Position is asserted
bit-exact for the on-axis walk and the full roll (which stay in MOVE/FRONT_ROLL); runs that visit
ATN_MOVE use the calibrated position fallback (the `ANM_ATN*` foot anims are not ported — they don't
affect the velocity/state/facing physics, which are the tech). Anchor `land_flatwalk@twwgz.sav`.
**Source:** live captures (`harness/capture/land_capture.py`, cross-checked advancewith == advanceseq
== DTM movie); decomp `d_a_player_main.cpp` proc enum + `setSpeedAndAngleNormal`/`setNormalSpeedF` +
`setSpeedAndAngleAtn`/`setSpeedAndAngleAtnBack` + `setBlendAtnMoveAnime` (mDirection machine) +
`checkNextMode` (MOVE↔ATN_MOVE) + `posMoveFromFootPos` + `mDoExt_MtxCalcAnmBlendTblOld` (foot anim).

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
- proc → **`daPyProc_ATN_MOVE_e` (state 7)** — the targeting-move proc (`procAtnMove` → `setSpeedAndAngleAtn`).
- **facing LOCKS**: on the L-engage frame `m34E6 = shape_angle.y` is captured (d_a_player_main.cpp:2067)
  and every ATN frame writes `shape_angle.y = m34E6` back — the run heading is frozen.
- travel flips to 180°: `getDirectionFromCurrentAngle()==DIR_BACKWARD` reflects `current.angle.y` by
  `0x8000` and negates `mNormalSpeed` (2863) — the backward slide is represented as a **negative speed on
  a flipped heading**, world motion still forward.
- steady state runs the **`setSpeedAndAngleAtnBack`** path (`mDirection==DIR_BACKWARD`, cap → **15** =
  `mAtnMoveB.field_0xC`). The ~−0.14/frame bleed is *not* a decay term: it is the accel-inject branch of
  `setNormalSpeedF` adding `f1 = 2.5·mStickDistance·cos(Δtravel) ≈ +0.139` to the negative speed each frame,
  walking it toward 0 (`mAtnMoveB.field_0x8 = 2.5`, `msd = 0.0556` at the ESS magnitude).
- **Simulated bit-exact** (`superswim.land`, `LandState.step` with L via `buttons`/`triggerL`).

## Extended brakeslide (EBS) — release L

Same start, but **release L after the 1 full-down frame**, then hold ESS:
- proc drops out of targeting to **`MOVE` (state 6)** (`checkNextMode` `r24` false → `procMove_init`);
  facing unlocks and tracks travel via the normal facing-chase.
- momentum bleeds **~13× slower (~−0.011/frame)** than the brakeslide — the "extended" part. This is the
  ordinary `setSpeedAndAngleNormal` on a nearly-reversed heading (cap back to **17**): the `cM_scos(target−
  travel)` speed scale is ~1 while travel slowly chases the backward target, so `mNormalSpeed` barely moves.
- **Simulated bit-exact** (reuses the walk proc; the negative-speed entry carries over from the 1 ATN frame).

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
stays anti-camera brakes — same travel, opposite outcome. **Mechanism (now traced + simulated):** once
L is released the frame runs `setSpeedAndAngleNormal`, whose target-speed scale is `cM_scos(m34E8 −
current.angle.y)` — the cosine of *stick-target vs travel*. Steering the ESS toward camera keeps that
angle small (cos≈1, speed held); steering anti-camera pushes it past `0x7800`, taking the reversal
branch (`dVar9 = 0`) so the speed decays at the normal −2.5/frame brake to a full stop (state 4).

## Facing/travel decoupling (how to turn facing independently)

Timing matters: **ESS-down for exactly ONE frame, then ESS-left/right the very next frame (held)**
makes **facing rotate to the ESS direction (~90°) and lock there while travel stays at the slide
heading (~171°)** — a sustained ~80° facing≠travel split, speed preserved. (Holding ESS-down 3+ frames
first instead keeps facing glued to travel.)

## Roll (FRONT_ROLL) — the fast approach movement

Press **A** (the "do" button, `dActStts_ATTACK_e`) while moving on the ground → **`procFrontRoll_init`
(state 30)**, `ANM_ROLLF`. On entry, facing snaps to the stick target (`shape_angle.y = m34E8`).
- **Speed (set once at entry, from the PRE-roll `speedF`):** `mNormalSpeed = clamp(speedF·1.5 + 0.5,
  5.0, 26.0)` (`mRoll.field_0x18/0x1C/0x20`). Full-run (`speedF` 17) → the **26 cap**; barely-moving →
  the **5.0 floor**. It's a big boost — 26 vs the walk cap 17 — which is why rolling is the workhorse
  ground-cover tech. During the roll `speedF == mNormalSpeed` (constant, momentum; **no foot-plant
  blend**, `m3598 = 0`), so position advances at the roll speed exactly.
- **Duration:** state 30 while the `ANM_ROLLF` frame ctrl runs ~0→17 (`mRoll.field_0x10`, rate 1.1,
  ≈18 frames), then `checkNextMode(1)` exits to MOVE carrying the speed, which decels to a stop
  (a full-run roll travels ≈ **760 units** — pos_z 764→1525 on the flat anchor).
- **Frame-perfect EBS out of a roll (~−23):** HOLD **L + full-down through the roll**. Because the
  stick is pushed, the `getFrame()>17` (`field_0x10`) early-turn `checkNextMode(1)` fires *one frame
  before* the anim-end exit — and since L is held it routes to **ATN_MOVE at the full 26** (skipping
  both the `getRate<0.01` branch's `−5` and the roll→MOVE walk decel). Then **release L into ESS-down**
  → the ATN backward-flip preserves it as **≈ −23.1** speed (state 6 EBS). A one-frame window — release
  a frame late and the roll→MOVE decel bleeds it to ~−18; a frame early and it dead-stops. This combo
  (huge negative speed from a roll) is a prime seam-clip setup.
- Rolling **into a wall** → `procFrontRollCrash` (needs `speedF ≥ 10` = `field_0x3C`); inert on flat
  wall-free ground.
- **Simulated** (`superswim.land`, `step` with A = button `0x100`): the roll is **fully bit-exact,
  entry to standstill AND the roll-EBS exit** (`roll_run`/`roll_slow`/`roll_settle`/`roll_ebs` are all
  sim-vs-live, pos_z d≈0.0001, roll-EBS speed −23.109 bit-exact). Duration = the `ANM_ROLLF` frame ctrl
  running 0→`field_0x0` (19) at rate 1.1 (~18 frames). Two exits: with a **neutral** stick the
  `getFrame()>17` early-turn `checkNextMode(1)` is inert (returns false when `msd≤0.05` and no action
  button), so the roll runs to the anim end (`getRate<0.01`), takes `mNormalSpeed -= 5.0` (26→21), and
  MOVE decels to a stop; with a **pushed** stick that early exit fires one frame sooner (no `−5`) and
  routes via `checkNextMode` to ATN_MOVE (L held) or MOVE — this is the roll-EBS above.
  - **The low-speed post-roll tail** (`nspeed < 17`, where the walk foot-plant `m3598 > 0` resumes)
    is bit-exact because `posMoveFromFootPos` runs *every* frame — including the roll — so the foot
    engine poses `ANM_ROLLF` (a `setSingleMoveAnime`, MOVE0=rollf, MOVE1=NULL, `m34C3=0`) throughout
    the roll and keeps the smoothed toe-delta stream (`m359C`) warm. During the roll `m3598` stays
    frozen at its pre-roll value (0 here) so `speedF == mNormalSpeed` momentum. On the roll→MOVE exit
    the walk blend re-inits its frame ctrl to **frame 0** *because* `m34C3 == 0` (not phase-continued),
    and `procMove_init` re-triggers the oldframe-morf (`mBasic.field_0xC` = 2.4). The first `m3598>0`
    frame then reads the correct roll-warmed `m359C` via the 0.3/0.7 recursive smoothing. Foot engine:
    `superswim/anim/foot_speedf.py` `enter_roll`/`step_roll`; `rollf` keyframe data added to the
    gitignored `_generated/anim/` set (frameMax 19, `EMode_NONE`, decShift 2).

## Wiggle EBS + L+Up cancel → chained roll (speed-preservation combo)

A chain that carries a roll's speed through a direction reversal into a *second* roll — the highest
speed-preservation tech found so far. Observed from a recorded DTM (`run_land_tests` `wiggle_ebs_roll`,
DTM-playback lock; the wiggle is dense frame-perfect input so it's replayed via the movie system, not
`advanceseq`). Full chain: **roll (26) → frame-perfect roll-EBS (−23) → wiggle EBS → L+Up cancel →
second roll (24.088) → stop**.

- **Wiggle EBS:** during the EBS, *alternate* the ESS between two positions (observed `target_angle`
  cycling ~`270° → 270° → 135°`, msd ≈ 0.06) so **facing oscillates right around forward** (≈ 328–360°/
  0–2°) while travel stays pinned backward (~185°). This holds the −23 speed at only **≈ −0.002/frame**
  — the camera-relative preservation (`cM_scos(target − travel) ≈ 1`), but wiggled so the *body* points
  roughly forward instead of drifting. Keeping facing forward is what makes the next step give forward
  speed. **The C-stick is also nudged to shift the camera** (`csangle`) into the angle that yields the
  desired EBS — `target = m34DC(stick) + csangle`, so camera is a live input to the whole thing.
- **L+Up cancel:** tapping L + forward (Up) snaps `target` to forward, the ATN backward-flip converts
  the backward slide, and it lands in MOVE at **+16** forward (speedF ~15.7).
- **Second roll:** rolling off that preserved speedF → `15.725·1.5 + 0.5 =` **24.088** — a second
  near-cap roll out of what began as a braking slide. Net: a huge fraction of the first roll's speed
  is carried through the reversal.

Not yet SIMULATED (depends on the roll + a camera model); the DTM-playback lock guards the end-to-end
signature (the two roll speeds, the −23 wiggle plateau, and the final `pos_z 2341.62`).

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
| ATN cap `mMaxNormalSpeed` (attention / DIR_BACKWARD) | 12 (`mAtnMove.field_0xC`) / 15 (`mAtnMoveB.field_0xC`) |
| ATN speed scale (side / back) `field_0x8` | 5.0 / 2.5 |
| ATN `setNormalSpeedF` (scale/max/min) side / back | 0.5 / 7.5 / 4.0 · 0.5 / 8.0 / 2.0 |
| ATN travel-chase `cLib_addCalcAngleS(scale,max,min)` | 6 / 3000 / 2000 |
| direction cos thresholds (fwd / back) `mAtnMoveB.0x2C/0x30` | ≥0.99 → FORWARD · ≤−0.99 → BACKWARD (else side by sin) |
| roll speed `clamp(speedF·field_0x18 + field_0x1C, field_0x20, cap)` | ×1.5 + 0.5, floor 5.0, cap 26.0 (= 0.5 + 17·1.5) |
| roll duration / exit frame `mRoll.field_0x10` | 17 (anim rate 1.1, ≈18 frames) |
| roll-EBS (frame-perfect) | full-run roll → hold L+down through roll → release L into ESS-down → ≈ −23.1 |

## See also

- [ESS](ess.md) — the same `(128,110)`-class stick position (land reuses the swim ESS coordinate).
- [Camera](camera.md) — `csangle` / `dCam_getControledAngleY`, here a live per-frame movement input.
- `superswim.land` (`LandState`) — the walk **and ATN_MOVE** sim (`setSpeedAndAngleAtn`/`AtnBack` +
  the `mDirection` machine + `checkNextMode` transitions; `step(sx, sy, buttons, triggerL)`);
  `superswim.anim` (`foot_speedf.FootSpeedF` + the J3D engine) — the bit-exact walk `speedF`;
  `tests/test_land.py` (offline golden walk arc + the ATN + roll end-state cases) +
  `tests/dolphin/run_land_tests.py`: **9 sim-vs-live** cases (walk + 4 ATN + roll_run/roll_slow/roll_settle/
  roll_ebs: nspeed/facing/travel bit-exact; walk, mid-roll, and full roll-to-standstill pos_z bit-exact)
  plus the `wiggle_ebs_roll` DTM-playback lock.
- `_notes/tww-sim-architecture-design.md` §5/§5b — how land folds into the generalized proc-machine sim.
