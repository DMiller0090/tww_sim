# Land movement: walk/run, brakeslide, EBS

**Answers:** How does on-ground walking accelerate? What are the two movement angles? What is a
brakeslide / extended brakeslide (EBS)? Why does holding ESS left/right preserve speed "almost
forever"? Is speed preservation governed by facing or travel?
**Status:** validated live (2026-07-03). The **flat-ground walk is now simulated** (`superswim.land`,
bit-exact `mNormalSpeed` + state machine). Locked by `tests/dolphin/run_land_tests.py`: `walk_run` is
**sim-vs-live**, the other 4 (brakeslide/EBS/facing) remain live-behavior locks (ATN_MOVE = next tier).
Anchor `land_flatwalk@twwgz.sav`.
**Source:** live captures (`harness/capture/land_capture.py`, cross-checked advancewith == advanceseq
== DTM movie); decomp `d_a_player_main.cpp` proc enum + `setSpeedAndAngleNormal`/`setNormalSpeedF`.

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

**Position ≠ `mNormalSpeed`.** The pos actually integrates **`speedF`** (true_speed), which on land is
**foot-plant / animation driven** (`posMoveFromFootPos` reads the walk anim's foot-joint matrices):
`speedF` lags `mNormalSpeed` on accel and overshoots on the decel tail, only locking `speedF == mNormalSpeed`
at steady state. So `speedF`/position is **not** transcribable without the skeleton — `superswim.land`
models it with a **calibrated `cLib` chase** (endpoint within ±3, not bit-exact per frame), exactly as
the swim sim treats `af_drag` displacement. Trust `mNormalSpeed`/state to the ULP; treat position as ±3.

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
- `superswim.land` (`LandState`) — the walk sim; `tests/test_land.py` (offline golden arc) +
  `tests/dolphin/run_land_tests.py` (`walk_run` sim-vs-live + 4 live locks).
- `_notes/tww-sim-architecture-design.md` §5/§5b — how land folds into the generalized proc-machine sim.
