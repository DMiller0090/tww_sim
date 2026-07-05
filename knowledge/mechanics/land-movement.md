# Land movement: walk/run, brakeslide, EBS

**Answers:** How does on-ground walking accelerate? What are the two movement angles? What is a
brakeslide / extended brakeslide (EBS)? Why does holding ESS left/right preserve speed "almost
forever"? Is speed preservation governed by facing or travel?
**Status:** validated live (2026-07-04). The **flat-ground walk, the ATN_MOVE tier (brakeslide /
EBS / facing decouple / brake), the forward roll (FRONT_ROLL — entry→standstill and the frame-perfect
roll-EBS exit), AND the big-reversal ground-turn procs (WAIT_TURN / MOVE_TURN / SLIP) are fully
simulated** (`tww_sim.land`): `mNormalSpeed` (signed), the proc state machine, **facing
(`shape_angle.y`) and travel (`current.angle.y`) are all BIT-EXACT** vs live, and the walk + roll
`speedF`/position is bit-exact too (d≈0.0001, via the ported J3D anim engine — see below). Locked by
`tests/dolphin/run_land_tests.py`: **12 sim-vs-live cases** (nspeed dv=0.00000, facing/travel d=0.0000°)
+ the `wiggle_ebs_roll` DTM-playback lock. Position is asserted bit-exact for the on-axis walk, the
full roll, the **MOVE_TURN turn-around** (its walk blend is posed at the pre-halving speed + re-morfed
on entry/exit — see below), the **WAIT_TURN pivot + walk-off** (`ANM_ROT` pivot → the WAIT idle-proc
`WAITS`/`ANM_ATNW{L,R}S` turn-step re-pose warms the toe stream — see below), the **whole ATN_MOVE
tier** (brakeslide / EBS-release / facing-decouple / brake: `setBlendAtnMoveAnime` poses the
`ANM_ATN{L,R}S`/`W`/`D` strafe + `ANM_ATNWB`/`ATNDB` backslide anims — see below), **and the SLIP skid →
MOVE_TURN handoff** (`ANM_SLIP` scales foot-chain joint 37's X by 1.2, so the FK now applies the
scale + the oldframe-morf blends it — see below). **All land position is now bit-exact with the anim
data present**; the calibrated fallback is used only when the keyframe data is absent. The **C-up
freeze (`daPyProc_SUBJECTIVITY_e`) + B-cancel re-walk-from-rest** is also modeled and **live-proven
0 ULP** (both the pure-Python and fused-native paths; 2026-07-05) — see the C-up-cancel section below.
Anchor `land_flatwalk@twwgz.sav`.
**Source:** live captures (`harness/capture/land_capture.py`, cross-checked advancewith == advanceseq
== DTM movie); decomp `d_a_player_main.cpp` proc enum + `setSpeedAndAngleNormal`/`setNormalSpeedF` +
`setSpeedAndAngleAtn`/`setSpeedAndAngleAtnBack` + `setBlendAtnMoveAnime` (mDirection machine) +
`checkNextMode` (MOVE↔ATN_MOVE) + `posMoveFromFootPos` + `mDoExt_MtxCalcAnmBlendTblOld` (foot anim) +
`procSubjectivity_init`/`checkSubjectEnd`/`setBlendMoveAnime` (the C-up freeze + B-cancel re-walk).

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
  earlier — one constant reproduces both edges; `tww_sim.land.INPUT_DELAY`).
- **Accel = +3.5/frame** exactly: `dVar9 = cM_scos(0)·field_0x14·msd²` (`field_0x14 = 3.5`), injected
  straight into `mNormalSpeed` by `setNormalSpeedF`, clamped to the cap.
- **Decel on release = `cLib_addCalc(mNormalSpeed, 0, 0.6, 2.5, 1.8)`** (HIO `field_0x24/0x1C/0x20`):
  `17→14.5→12→9.5→7→4.5→2→0.2→0` — the constant `−2.5/frame` while far from 0, then the cLib min-step
  snap tail (not a flat −2.5). Clean stop (state 4).
- proc = `daPyProc_MOVE_e` (state **6**). On flat, wall-free ground, collision (`mAcch` wall/slope) is
  inert, so `mNormalSpeed` is pure 1-D physics — **transcribed bit-exact** in `tww_sim.land`.

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
  position, so it is reproduced by the **ported J3D animation runtime** (`tww_sim.core.anim`), not a table.

**The foot-plant subsystem is now BUILT and bit-exact** (`tww_sim.core.anim`, FMA-faithful: single
fused-multiply-add via an f64 intermediate, `tww_sim.core.fp`). The chain, all offline: `UnderAnimState` (the `setBlendMoveAnime`/`setMoveAnime`/`J3DFrameCtrl`
state machine → which anims fill MOVE0/MOVE1, their frame-ctrl frames, the blend ratio, and `m3598`,
driven by the bit-exact `mNormalSpeed`) → `FootFK` (reduced foot-chain forward kinematics: BCK Hermite
keyframe eval → euler→quat → `QuatLerp` blend → `PSMTXQuat`/`Concat`/`MultVec`, plus the walk-entry
**oldframe-morf**) → `posMoveFromFootPos` (plant select, the 1-frame-delayed toe delta `f31_2`, the
recursive smoothing gate, and the `speedF` composition). `tww_sim.core.anim.foot_speedf.FootSpeedF` is the
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
- **Simulated bit-exact incl. position** (`tww_sim.land`, `LandState.step` with L via `buttons`/`triggerL`):
  the steady backslide poses `ANM_ATNDB` single (`setBlendAtnBackMoveAnime` else-branch) with **`m3598 = 0`**,
  so `speedF == mNormalSpeed` — the backslide position is pure momentum (see *ATN position* below).

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

## ATN position (the strafe/backslide foot anims) — BIT-EXACT

The ATN_MOVE tier's **position** is bit-exact too (`setBlendAtnMoveAnime`, `d_a_player_main.cpp:3280`,
ported into `tww_sim/core/anim/anim_state.py`; foot posed each ATN frame by `foot_speedf.step_atn`). Each
ATN frame the `mDirection` machine picks the foot anim from **`f31 = |mNormalSpeed·cos(m34E2)| /
mMaxNormalSpeed`** (on flat ground `m34E2 = getGroundAngle = 0`, so `cos = 1` ⇒ `f31 = |nspeed|/max`):
- **side** (`DIR_LEFT/RIGHT`): blends `ANM_ATN{L,R}S` → `ANM_ATNW{L,R}S` → `ANM_ATND{L,R}S` with `f31`
  (thresholds `mAtnMove.field_0x1C`=0.01 / `0x20`=0.9). At the slide speeds `f31 ≥ 0.9` ⇒ the single
  `ANM_ATND{L,R}S` pose, **`m3598 = 0`**.
- **backward** (`DIR_BACKWARD`, `setBlendAtnBackMoveAnime`): `ANM_WAITS` → `ANM_ATNWB` → `ANM_ATNDB`
  (thresholds `mAtnMoveB.field_0x1C`=0.75 / `0x20`=1.0). The brakeslide runs the single `ANM_ATNDB` at
  `f31 ≥ 1.0`, **`m3598 = 0`**.
- **forward** (`DIR_FORWARD`): reuses the plain walk `setBlendMoveAnime` (cap back to 17).

Because `m3598 = 0` at slide speed, `speedF == mNormalSpeed` — the ATN slide itself is **pure momentum**.
The one thing that matters for position is that the ATN pose still **warms the toe stream**: on an
**EBS release** (L dropped → `MOVE` next frame, `procMove_init` re-morf `mBasic.field_0xC` = 2.4), the
first walk frame's foot-plant delta `f31_2` spans the last ATN pose → the walk pose, so the strafe anim
must be posed exactly for the walk-off to be bit-exact (same warm-the-stream mechanism as the roll and
WAIT_TURN tails). Locked by `run_land_tests` `brakeslide`/`ebs`/`face_left`/`brake_right` (pos_z bit-exact)
+ offline `test_atn_*` position asserts. mDirection is validated live (player+0x34B8) and drives the pose.

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
- **Simulated** (`tww_sim.land`, `step` with A = button `0x100`): the roll is **fully bit-exact,
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
    `tww_sim/core/anim/foot_speedf.py` `enter_roll`/`step_roll`; `rollf` keyframe data added to the
    gitignored `_generated/anim/` set (frameMax 19, `EMode_NONE`, decShift 2).

## Targeted ballistic hops (sidehop / backflip)

The consistent standstill movers.

**Input mapping (decomp truth, a common gotcha).** `checkNextActionFromButton`
(`d_a_player_main.cpp:4309-4323`) routes the A ("do") button by do-status:
- **A while moving, NOT targeting** → `dActStts_ATTACK_e` → FRONT_ROLL (the roll above).
- **L held (targeting) + A + directional stick** → `dActStts_JUMP_e` →
  `getDirectionFromShapeAngle()` (= `getDirectionFromAngle(m34E8 − shape_angle.y)`): stick **LEFT/RIGHT →
  SIDE_STEP (sidehop)**, stick **BACKWARD → BACK_JUMP (backflip)**, FORWARD → nothing.

So **there is no "L+A roll" and no targeted forward move** — L+A is the *hop* family, plain A (untargeted)
is the roll. Both work from a standstill.

**These are the fully human-consistent standstill blocks** (one button combo, ballistic, no release
timing) — the backbone of the [setup finder](../model/land-setup-finder.md). Unlike the roll (entry
speed-dependent) or a walk (can't be stopped without a frame-perfect input), a hop's displacement is fixed.

**Ballistic model (`tww_sim.land.LandState`, Python path; pure momentum + gravity, `m3598 = 0`, no
foot-plant).** Per `posMoveFromFootPos` (`d_a_player_main.cpp:2464-2479`) + the `execute` order
(`11402→11407 posMove→11411 CrrPos`): each air frame `speed.y = f32(speed.y + gravity)` (clamp
`MAX_FALL = −175`), then `current.pos += speed` (x/y/z together), then collision snaps `pos.y` to the
flat floor and sets `GROUND_HIT` — **read one frame later**, so the land is detected the frame after
`pos.y` crosses. Horizontal is `speedF = mNormalSpeed` along `current.angle.y`, constant through flight.

- **Sidehop** (`procSideStep_init` 6313): `current.angle.y = shape_angle.y ± 0x4000` (perpendicular);
  `mNormalSpeed = cM_scos(6200)·30`, `speed.y = cM_ssin(6200)·30`, `gravity = −2.4`. Lands on the FIRST
  ground-hit frame. Sim net ≈ **±323u** perpendicular, ~22 frames to standstill.
- **Backflip** (`procBackJump_init` 7003): `current.angle.y = shape_angle.y + 0x8000` (backward);
  `mNormalSpeed = 22.5`, `speed.y = 19.0`, `gravity = −3.0`. Lands only once ground-hit **AND** the
  `ANM_ROLLB` frame ctrl (start 2 → end 11 @ 0.8) has finished (`getRate()<0.01`), so momentum can slide
  along the ground for the frames between contact and anim-end. Sim net ≈ **−270u** (opposite facing),
  facing unchanged, ~22 frames.

Constants: `mSideStep` `d_a_player_HIO_data.inc:223`, `mBackJump` `:102`. **Status: offline sim only —
pending live 0-ULP calibration** (the airtime/anim-gate off-by-one and the magnitude-dependent vertical
f32 rounding must be gated vs Dolphin; seed `pos_y` from the live anchor). The XZ path rides the same
0-ULP `LandState.step` accumulation as the walk. Procs `SIDE_STEP 0x0A`/`SIDE_STEP_LAND 0x0B`/
`BACK_JUMP 0x22`/`BACK_JUMP_LAND 0x23`. Ballistics live on the **Python** path only for now (the native
C twin doesn't implement them → build the state `native=False`).

**Facing turn for aiming hops — ESS + C-down in-place rotation.** Holding a low/**ESS**-magnitude stick
(e.g. `(110,128)` left / `(146,128)` right) at a world angle with the camera frozen (C-down, `substickY=0`)
rotates Link **in place** — `nspeed` stays 0 (the movement gate `msd > 0.5` isn't met) while
`setSpeedAndAngleNormal` still chases facing/travel toward the stick target, so **facing turns with zero
translation**. At the ESS magnitude the rate is only ~**0.055°/frame** (`travel` steps `≈ F0·msd² ≈ 10`
s16/frame, and facing is pinned to travel) — a **fine sidehop-aim nudge**, not a fast 90° snap. How it is
made to stop cleanly at a wanted facing (self-stop at the stick's target angle vs a release) is **not yet
confirmed live** — so it is a *pending* facing primitive, not yet a setup-finder block. It matters because
a sidehop moves perpendicular to facing, so this rotation is what points a hop along a chosen axis.

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

## Big-reversal ground-turn procs (WAIT_TURN 23 / MOVE_TURN 24 / SLIP 25)

When the stick target is a hard reversal — `cLib_distanceAngleS(m34E8, current.angle.y) > 0x7800`
(≈ >168°) with `msd > 0.05`, no attention lock — `checkNextMode` (4424) routes *away* from the plain
MOVE proc into one of three turn procs (no reversal ⇒ the aligned walk keeps facing≈travel, so these
never fire on-axis):

- **`procWaitTurn` (`WAIT_TURN`, 23)** — reversal from a **standstill** (`|mNormalSpeed| ≤ 0.001`). Link
  **pivots in place**: `mNormalSpeed` stays 0 while facing+travel rotate ~180° over ~5 frames, then it
  drops to WAIT and walks off in the new direction. (Flick down from the idle anchor → face-about.)
- **`procMoveTurn` (`MOVE_TURN`, 24)** — reversal while **moving below the slip threshold**
  (`speedF/mMaxNormalSpeed ≤ mSlip.field_0x4 = 0.6`), or as SLIP's hand-off. Travel flips to the new
  heading immediately (`current.angle.y += 0x8000`), `mNormalSpeed` is halved, then facing sweeps around
  to the new travel (`cLib_addCalcAngleS` toward `current.angle.y`) while it re-accelerates to the cap — a
  quick turn-around. It stays MOVE_TURN until facing == travel, then routes to MOVE.
- **`procSlip` (`SLIP`, 25)** — reversal while **moving fast** (`speedF/mMaxNormalSpeed > 0.6`, non-ice,
  and `getDirectionFromAngle(m34EA − m34DC) == BACKWARD` — i.e. the stick genuinely *flipped* between
  frames). Entry speed `mNormalSpeed = speedF · mSlip.field_0x8 (1.1)` (uncapped, e.g. 17 → 18.7). Link
  **keeps sliding FORWARD** (travel held at the old heading) while `mNormalSpeed` decelerates ~−1.25/frame
  through the skid; once it bleeds to ~0 it flips travel by 0x8000, re-seeds `mNormalSpeed = cap·0.5`, and
  hands to `MOVE_TURN`. So a full-speed reverse is **SLIP → MOVE_TURN → MOVE**.

**Status:** fully simulated in `tww_sim.land` (`checkNextMode`'s `!attention_lock` arbiter +
`procWaitTurn`/`procMoveTurn`/`procSlip`), **bit-exact** `mNormalSpeed`/state/facing/travel vs live.
The reversal early-return in `setSpeedAndAngleNormal` (2766) hinges on `ModeFlg_00000001` (set for the
idle procs WAIT/FREE_WAIT/WAIT_TURN, *not* MOVE/MOVE_TURN/SLIP): while idle a reversal is inert (angles
untouched), so `checkNextMode` sees the full >0x7800 gap and picks `procWaitTurn`; from MOVE the reversal
branch first chases/holds travel (dropping a slow reversal below 0x7800) so `checkNextMode` routes via
the SLIP / MOVE_TURN(1) / DIR_BACKWARD arms instead. Locked by `run_land_tests` `waitturn`/`moveturn`/`slip`
(sim-vs-live): the transient proc is proven entered by the sim's `visited` set; the reversed-walk end
state is bit-exact; the locked live distances (690/546/982 on the flat anchor) guard the anchor.

**MOVE_TURN and WAIT_TURN position are BIT-EXACT** (`test_moveturn_position_bit_exact` /
`test_waitturn_position_bit_exact`, sim-vs-live d=0.0000). MOVE_TURN uses the WALK blend (no new anim
data): (1) `procMoveTurn_init` calls `setBlendMoveAnime(mBasic.field_0xC=2.4)` at 6616 **before**
`mNormalSpeed *= 0.5` at 6623 — so the walk anim is posed at the *pre-halving* speed while
`posMoveFromFootPos` integrates with the halved speed (the anim engine takes an `anim_nspeed` split for
that one frame); (2) both the MOVE→MOVE_TURN entry *and* the MOVE_TURN→MOVE exit (`procMove_init`)
re-trigger the morf, re-warming the walk blend. **WAIT_TURN** poses `ANM_ROT` through the pivot
(`setSingleMoveAnime`, warms the toe stream); when the pivot completes `checkNextMode` drops to WAIT and
`procWait_init` runs the idle-proc `setBlendMoveAnime` (`ModeFlg_00000001` branch): because
`shape_angle.y != m34DE` (the facing just pivoted) it poses the turn-in-place walk-step **MOVE0=`ANM_WAITS`,
MOVE1=`ANM_ATNWLS`/`ANM_ATNWRS`** at ratio `clamp(0.5 + 0.001·|Δfacing|, 0, 1)` (`m3598=0`, morf 2.4). That
`ATNW` pose (not `WAITS`) is what makes the walk-off entry drift `f31_2 = |ATNW@0 − ROT@last|` bit-exact
(≈3.06 on the first moving frame) — a plain `WAITS@0` is only ~1u from the pivot pose and undershoots by
0.7u over the arc. `ANM_ATNWLS`/`ANM_ATNWRS` (frameMax 18) are added to the extracted anim set.

**SLIP → MOVE_TURN position now BIT-EXACT too.** The skid is pure momentum (position exact on its own),
but the `ANM_SLIP` pose feeds the MOVE_TURN walk tail's toe stream. The last unported detail: **`ANM_SLIP`
scales foot-chain joint 37's X by 1.2** (`calc_transform` returned it, but the reduced FK built the joint
matrix from rotation + translation only). walk/dash/rollf are all identity-scale on the foot chain, which
is why the FK ignored scale until now. Fix (`foot_fk`): build the joint matrix as **M = R·diag(scale)**
(scale each rotation column) — a no-op for the identity-scale anims — and carry `old_scale` through the
**oldframe-morf** (which blends scale too: `mScale·(1−rate) + oldScale·rate`, `m_Do_ext.cpp:1203`), so the
walk pose re-morfed off `ANM_SLIP@end` inherits the scaled toe. That fixed both the wrong toe-delta and a
plant-foot flip at the handoff (the scaled right-foot toe was mis-ordered vs the left). `slip` pos_z now
d=0.005 (advancewith/advanceseq pipe noise, not sim error). **No land tech is on the position fallback now.**

## Precise stopping: live-valid stick magnitudes, L-target, and the C-up speed cancel

For placing Link at an exact world position (float-perfect stop) — validated live 2026-07-04:

**Live-valid stick magnitudes (a sim `msd` caveat).** `_set_stick_data` uses `msd = min(hypot(deadzone)/54, 1)`.
For **Y ≤ 191** (msd ≤ 0.889) this is bit-exact live; for **Y ∈ [192, 254]** the sim OVER-reads msd vs the
live PADClamp (which saturates differently near the cap) — a walk at `(128,196)` gives sim v=16.38 but live
15.76, ~1u+ divergence over a run. `(128,255)` (true full) is exact. **So any offline search over partial
magnitudes must restrict to `Y ≤ 191 ∪ {255}`; NEVER emit 192–254** or the plan diverges live. (Same
input-layer≠`/54` family as the [stick-angle table redump](../history/resolved-bugs.md).) From a **standstill**
the walk needs `msd > 0.5` to move at all (the `setSpeedAndAngleNormal` `dVar9` gate `0.5 − 0.5·|v|/max`), so
the smallest up-input that moves is **`(128,171)`** (msd 0.519 → cruises ~4.6/fr); `(128,170)` and below stay planted.

**L-target forward = X-neutral low-speed access.** Holding L (Z-target; `buttons 0x40` + `triggerL 255`) + up-stick
+ centered X from a standstill → `ATN_MOVE` (state 7), direction FORWARD, facing locked, travel stays 0 → **X stays
0**, bit-exact live. It unlocks speeds normal walk can't reach from rest (`Y=168`→3.64, `Y=170`→4.25, below the
171 gate) and runs different accel/decel (`ATN_ACC 7.5`/`ATN_DEC 4.0`). **Hold C-DOWN (`substickY=0`) on every
targeting frame** — otherwise the camera auto-swings during targeting (moves `csangle` → moves X); C-down keeps
it frozen (the sim's `CameraManual` is frozen for `csy∈{0,128}`, so C-down keeps you in-model).

**C-up speed cancel = the instant freeze (the float-exact enabler).** While walking (free cam): one frame
**half-press L** (analog `triggerL≈100`, ends manual cam), then **left stick NEUTRAL + C-stick FULL UP**
(`substickY=255`). Effect: 2 input-latency frames (still cruising) + 1 normal-decel frame, then speed **snaps to
0 and position LOCKS** (`link_state → 1`). X stays 0. **The existing sim reproduces the freeze position with zero
new code**: `frozen_pos = walk-sim pos 3 frames after the neutral+C-up input` (the 2-frame `INPUT_DELAY` + one
`cLib` decel already produce it) — verified bit-exact (live froze at z=795.126 from a Y171 cruise; sim's
3rd-neutral-frame pos = 795.1258). Because the freeze happens MID-MOTION there is no [resting dead-band](#walk--run-acceleration-baseline),
so a slow approach + cancel places the frozen float essentially anywhere.

**Arrive SLOW to arrive fine (the freeze-coast constraint).** The frozen position = walk pos + the
3-frame coast, and that coast **scales with the approach speed** (2 latency frames still cruise the
pending sticks). So a fast arrival gives coarse ~10–17u freeze steps; only a SLOW approach gives a fine
straddle. But you can't crawl arbitrarily slowly: msd < 0.5 collapses to a dead stop (the `dVar9` gate
above), so the **minimum sustained crawl is msd 0.5 → nspeed≈4.25 → ~1u/frame** (once already moving;
it can't be started from rest). The finest *sustainable* step is therefore ~1u; sub-ULP resolution
comes from a drill that fills that 1u step, not from a slower crawl. (The freeze itself is 0-ULP-modeled
from ANY approach speed — full-speed cruise included: live froze at z=1121.9905 from a 23-frame full
cruise, sim `_freeze_pos` = same bits. The halfL frame RE-ISSUES the last approach stick, it does not add
a frame.)

**The freeze IS `daPyProc_SUBJECTIVITY_e` (first-person view).** `link_state → 1` is proc 1, and
`procSubjectivity_init` (`d_a_player_main.cpp:5948`) does two things: `mNormalSpeed = 0.0` (the position
lock) and `setBlendMoveAnime(field_0xC)`. On-axis that hits the `ModeFlg_00000001` idle arm (line 3114)
→ `setMoveAnime(f27=0, f28=1.1, f25=0.8, ANM_WAITS, ANM_WALK, r29=2, morf)`: **MOVE0 = WAITS (rate 1.1),
MOVE1 = WALK (rate (1/60)·1.1·32 = 0.587), `m34C3 = 2`, ratio 0, `m3598 = 0`**, and the walk phase is
PRESERVED (`f31 = fc0.frame/frameMax`, since the walk's `m34C3 = 1 ∉ {0,9,10}`). `procSubjectivity`
itself only `setBodyAngleToCamera`s each frame, so the WAITS frame-ctrl just advances at 1.1/frame.

**B cancels the freeze recovery (~2 frames vs ~8) — the chained coarse+fine primitive (TAS).** After the
freeze locks, Link plays a **~8-frame recovery** before actionable. **Pressing B (`PAD_BUTTON_B` 0x200)
interrupts it** via `checkSubjectEnd` (`5694`: `mItemTrigger & (BTN_A|BTN_B)`) → `changeWaitProc` → WAIT
(state 1 → 4), registered ~2 frames later (just `INPUT_DELAY`). Measured 2026-07-05c; **C-down did NOT
speed recovery (still ~8), only B did.** This enables **coarse-freeze → B-cancel → short fine-walk-from-
rest → fine-freeze**: freeze from FULL speed (fast stop on a coarse ~17u lattice), B-cancel to rest
(SKIPS the ~7-frame decel a crawl needs), then a few fine frames to the exact float.

**Why the re-walk ≠ a cold walk (SOLVED + modeled, 2026-07-05).** The post-B-cancel re-walk has the same
`nspeed` ramp but ~2× smaller low-speed `dz` — because the **foot-anim phase is CARRIED**, not reset. A
cold walk resumes from FREE_WAIT, which plays a SINGLE anim (`m34C3 = 0`), so `procMove_init`'s
`setMoveAnime` forces `f31 = 0` → the walk restarts at anim frame 0. The re-walk resumes from the
subjectivity/WAIT blend (`m34C3 = 2`), so `f31 = fc0.frame/frameMax` is preserved → the walk re-warms at
the carried WAITS phase. Live proof: first MOVE frame `fc0 = 0.000` (cold) vs `43.499` (re-walk), every
other field identical. **The sim models this exactly** (`LandState.enter_freeze / hold_freeze /
resume_walk`; the anim primitives are `FootSpeedF.enter_subjectivity / step_subjectivity`, and the fused
native twin `PoseEngine.w_enter_subjectivity / w_step_subjectivity`) — **live-proven 0 ULP** across the
whole cruise → freeze → hold → re-walk sequence, both the pure-Python and fused-native paths (test
`test_subjectivity_freeze_rewalk_bit_exact`; live gate `_notes/chained-freeze-probes/gate_subj_live.py`).
The **#hold frames is the planner's lever** for the resume phase (each +1 advances WAITS by 1.1). See
[land-planner: chained-freeze](../model/land-planner.md#float-perfect-stop--the-c-up-speed-cancel).

**Float-perfect stop achieved deterministically and ROBUSTLY** (`reach_freeze`, 2026-07-05): cruise →
sustained msd-0.5 crawl → dedup-by-freeze-position drill rests within **~1–4 float32 ULP (< 0.001u) of
ANY on-axis target** with an all-live-valid seq (the earlier glide-based drill hit ~0.003u only at lucky
targets — see [history](../history/land-planner-precision.md)). The residual ~1–4 ULP is **NOT a sim
inaccuracy** (the sim reproduces live `pos_z` at **0 ULP** byte-for-byte, enforced by the zero-tolerance
`posz_status` gate in `run_land_tests`, so an offline *exact* freeze reproduces exactly live) — it is the
**production beam under-exploring the tail** (it dedups by freeze POSITION, collapsing the momentum
diversity that fills the last ULP). A **windowed-deepening** search (keep every distinct STATE near the
target, deepen only those) hits the EXACT target float within depth-4 for every target tried — **live-
proven: console froze at exactly `2000.0` (`0x44fa0000`) and `1800.0` (`0x44e10000`)** — see
[land-planner exact-float reachability](../model/land-planner.md#float-perfect-stop--the-c-up-speed-cancel). Position path:
[model/sim: land position accumulates in f32](../model/land-sim.md#land-position-accumulates-in-f32-not-an-f64-running-sum).
**LIVE-CONFIRMED 0 ULP (2026-07-05):** driving whole `reach_freeze` plans in Dolphin (approach
`advanceseq`, then the real cancel — one half-L frame re-issuing `prefix[-1]` at `triggerL=100`, then
neutral + C-UP full `substickY=255`) froze `pos_z` at the sim's `freeze_pos.z` **byte-for-byte** for
every reachable on-axis target (z = 1500 / 2000 / 2500 all 0 ULP), `pos_x` = 0, `link_state → 1`.
The freeze thus rides the same 0-ULP-gated `LandState.step` path as the 14 locked cases — no longer
"pending". **Reachability caveat:** the sim has NO collision geometry, so a plan can target past a
wall. The `land_flatwalk` anchor's +z corridor hits a **wall at `pos_z ≈ 2932.4294` (`0x453746df`)**:
targets beyond it (z = 3000 / 4000) freeze AT the wall, not the requested z — a physical limit, not a
sim error. On-axis freeze targets must lie in `(764.08, 2932.43)` on this anchor.

## Values

| thing | value |
|-------|-------|
| run cap `mMaxNormalSpeed` | 17.0 (HIO `mMove.field_0x18`) |
| walk accel step | +3.5/fr (`field_0x14 = 3.5` × `cM_scos(0)` × `msd²`) |
| walk decel `cLib_addCalc(v,0, scale,max,min)` | scale 0.6 / max 2.5 / min 1.8 (`field_0x24/0x1C/0x20`) |
| input latency | 2 frames (press and release) |
| ESS down / left / right | `(128,110)` / `(110,128)` / `(146,128)` |
| decay: brakeslide / EBS / EBS-toward-cam / brake | −0.14 / −0.011 / ~−0.001 / −2.5 per frame |
| procs (`link_state`) | 4 WAIT · 5 FREE_WAIT · 6 MOVE · 7 ATN_MOVE · 0x17/23 WAIT_TURN · 0x18/24 MOVE_TURN · 0x19/25 SLIP · 30 FRONT_ROLL |
| slip speed threshold `mSlip.field_0x4` | `speedF/mMaxNormalSpeed > 0.6` → SLIP (else MOVE_TURN) on a moving reversal (+ genuine stick flip) |
| slip entry / decel `mSlip.0x8 · 0x18/0x10/0x14` | `nspeed = speedF·1.1` (uncapped) · decel cLib scale 0.6 / max 1.25 / min 0.1875 (~−1.25/fr) |
| WaitTurn facing pivot `mTurn.0x4/0x0/0x2` | `cLib_addCalcAngleS(scale 30, max 0x3CDF, min 0x1F40)` → ~0x1F40 (≈8000)/frame pivot |
| MoveTurn facing sweep `cLib_addCalcAngleS(scale,max,min)` | 1-path 2 / (F0·4+0x4A56) / (F0·2) · slip-exit 3 / (F0·2) / F0  (F0 = `mMove.field_0x0` = 3000) |
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
- `tww_sim.land` (`LandState`) — the walk, **ATN_MOVE, roll, and the ground-turn procs** sim
  (`setSpeedAndAngleAtn`/`AtnBack` + the `mDirection` machine + `checkNextMode`'s full reversal arbiter +
  `procWaitTurn`/`procMoveTurn`/`procSlip`; `step(sx, sy, buttons, triggerL)`);
  `tww_sim.core.anim` (`foot_speedf.FootSpeedF` + the J3D engine) — the bit-exact walk `speedF`;
  `tests/test_land.py` (offline golden walk arc + the ATN + roll + turn end-state cases) +
  `tests/dolphin/run_land_tests.py`: **13 sim-vs-live** cases (2 walk + 4 ATN + 4 roll + waitturn/moveturn/slip:
  nspeed/facing/travel bit-exact; pos_z bit-exact (0 ULP) for **every** case — walk, roll, MOVE_TURN, WAIT_TURN,
  the 4 ATN techs, and the SLIP skid→turn — the calibrated fallback is used only with no anim data) **plus**
  the `wiggle_ebs_roll` DTM-playback lock (14 total).
- [model/land-sim](../model/land-sim.md) (position precision + the 7 ULP tests) ·
  [model/land-planner](../model/land-planner.md) (target→inputs) ·
  [model/anim-engine](../model/anim-engine.md) (foot FK → `speedF`) ·
  [model/fp-faithfulness](../model/fp-faithfulness.md) (the FP contract).
- `_notes/tww-sim-architecture-design.md` §5/§5b — how land folds into the generalized proc-machine sim.
