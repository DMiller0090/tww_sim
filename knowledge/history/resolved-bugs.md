# History — resolved bugs & their provenance

> **status: historical** — how these were found and fixed. The current truth is in the linked
> mechanics/model pages. Kept because the *reasons* (and the wrong turns) matter for future debugging.

---

## bug#2 — dense-pump live divergence = pipe artifact, NOT physics

Dense back-to-back pump plans reached only ~127k live vs the sim's ~300k. Root cause: the external
`advanceseq` pipe's FrameAdvance listener **jitters SI polls** on dense neutral↔ESS transitions
(off-thread input misses the emu-thread poll). A cleanly **authored** DTM (8 ControllerState rows per
30 fps game-frame, 254/1 calibration) played via the movie system is **bit-exact** (cruise_pump300k:
net 300,816). A DTM *recorded* from the pipe inherits the jitter — only an independently authored DTM
is unbiased. **Dense plans are valid.** → [reference/commands](../reference/commands.md#live-validation--dtm-the-faithful-delivery-path), [model/planner](../model/planner.md).

> The `run_tests.py` **pump-transition** DTM baseline (formerly labelled "bug2 neu-pump") is a
> LOCKED clean-DTM sync, bit-exact. A one-session "sim over-bleeds pump exits" scare was a
> **seed mismatch** (the sim seeded with the slot-10 slate's mRate 0.5472 while validated against
> the anchor's cold start, real mRate 0.5); seeded correctly the sim is bit-exact. The mRate rule
> and the [554 cold-start seeding](../model/swim-sim.md#cold-start-seeding-the-mrate-rule) stand. Lesson
> in [tests/dolphin/README](../../tests/dolphin/README.md#locked-tests-are-immutable-hard-rule).

## bug3 — partial-hold gain dropped at a hold→charge boundary

A **partial** on-axis hold (e.g. `(128,77)`) interleaved in a charge burst was mispredicted: live
`25×chg + 4×(128,77) + 10×chg` gave **v=−92.0** but the sim gave **−93.83** (dv ≈ 1.83); the
`(128,110)` ESS control was bit-exact. Per-frame DTM ground truth localized it to the first `chg`
*after* the holds: live applied the 4th hold's `setSpeedAndAngleSwim` gain (lagged one frame, +2),
but the sim took its `is_chg` branch and applied `ess_decay` (+1/6) instead — **dropping the last
hold's gain** (error 2 − 1/6 = 1.833). Root cause: `step()` applied the ESS gain *same-frame* but
the charge gain *lagged*, carrying only one preempted transient (`_post_burst_transient`); at a
hold→charge boundary the steady holds had self-applied, so nothing was pending and the charge
overwrote the slot. **Fix:** defer the swim gain ONE frame UNIFORMLY for ESS and charge (the
discipline `ArrowState` already used). Validated bit-exact via clean DTM (110 **and** 77);
`run_tests.py bug3 partial hold` is now a baseline. Repro: `harness/dtm/partial_hold_dtm.py`. →
[model/sim](../model/swim-sim.md#charge-frame-model-four-1-frame-lags), [mechanics/decay-curve](../mechanics/decay-curve.md).

## walk entry-transient — two f64-vs-f32 constant bugs (NOT a Hermite/foot-IK frontier)

The straight-walk `speedF`/`pos_z` was float-perfect at cruise but the **entry transient** stayed
RED for several sessions: jnt0.z ~5 ULP off at MOVE frame 3, `speedF` −1 ULP at frames 5/6. The
04x hypothesis was "a `calc_transform`/Hermite sub-ULP in the root jnt0.z track" + "a planted-foot
jnt34/39 sub-ULP (likely a foot-IK ground snap)." **Both were wrong.** Live decomposition
(reload-anchor + `advanceseq` prefix-replay, reading `oldTransInfo`/`m359C` via the
[anim-engine oracles](../model/anim-engine.md#live-oracles-for-re-validation)) proved:

1. **oldframe-morf counter was f64.** At MOVE frame 3 the anim frames are *exactly* 0.0/0.0 and the
   ratio is bit-exact, so the per-anim jnt0.z and the ratio-blend are trivially exact — the divergence
   was entirely in the morf blend, and a single-input sweep pinned it to `oldFrameRate` being 1 ULP
   low. `MorfState.init_morf` stored `self.counter = float(i_morf)` — Python's **f64** `2.4`
   (=2.39999999…), but `mOldFrameMorfCounter` and the `i_morf` param are **f32** in the game
   (`m_Do_ext.cpp:1227`), so the constant is `f32(2.4)`=2.40000009… *before* the `-=1.0`. The f64
   value rounds `counter` (then `f10`, then the rate) 1 ULP low. **Fix:** `i_morf = fp.f32(i_morf)`
   on entry → jnt0.z entry-morf bit-exact.
2. **`f31_2` smoothing used f64 `0.3`/`0.7`.** With jnt0.z fixed the toe stream is fully bit-exact
   (both feet, x+z, aligned by the 1-frame lag `sim toe(N)==live spB0(N+1)`), so the remaining
   `speedF` −1 ULP at frames 5/6 was pure `posMoveFromFootPos` arithmetic. It traced to the recursive
   smoothing `f31_2 = f31_2*0.3f + 0.7f*m359C` (`d_a_player_main.cpp:2400`): `0.3f`/`0.7f` are **f32
   literals**, but the sim multiplied by Python's f64 `0.3`/`0.7` (=0.2999999…/0.6999999…), rounding
   each product 1 ULP off. The expression is **non-fused** (fused forms miss). **Fix:** f32 constants
   `_F0_3`/`_F0_7` → `m359C` bit-exact frames 3–7, live `walk_run` bit-exact.

**Lesson:** an entry-transient "sub-ULP FK frontier" was really two garden-variety **f64 constant
leaks** — a Python literal fed to an `fp` op is f64; the game's constant is whatever its field/param
type says (usually f32). Quantize constants to f32 at the site that mirrors an f32 store/param.
`fp.fmuls`/`fadds` do **not** quantize their operands, so the caller must. Also: the raw-`FootSpeedF`
driver in `test_speedf_matches_live_bit_exact` is a **harness artifact** in the release region
(frames 33–36 read hundreds of ULP off while LandState is bit-exact) — same class as the Y171 raw
driver; trust LandState-driven values. Still open after these fixes: ATN/turn endpoints
(ebs/brake_right/waitturn 1–2 ULP), slip (74 ULP), Y171 toe.z, deep-release frames 37/39 (1 ULP).
→ [model/anim-engine](../model/anim-engine.md), [model/land-sim](../model/land-sim.md).

## 554 / "anim drifts ~3 fr by f400" — truncated-seed artifact

A phantom ~3-frame anim drift by f400 was a **truncated cold-start seed** (anim 8.9417 vs true
8.941699028…); the cold-start [×598 scramble](../mechanics/pumps.md#the-x598-scramble) amplified the
sub-ULP error ~600×. With the full-precision seed the sim is bit-exact per-frame. Fix: never seed a
truncated anim. → [model/sim](../model/swim-sim.md#cold-start-seeding-the-mrate-rule).

## Off-axis charge v residual — corrupt stick-angle table (input path)

A 0.0105 too-high v on off-axis charge was traced (after a wrong "camera-field mismatch" hypothesis)
to `stick_angle_table.csv` being dumped via the **calibrated `set_gc_buttons`** path while the
game/tests/DTM use the **raw-byte `advancewith`** path — differing up to ±155 s16 on ~12k off-axis
cells. Regenerating via `advancewith` → v bit-exact. This fixed the x/y/`value` (magnitude) alignment;
a separate **read-latency** corruption in the `angle` and `stick_dist` columns survived it and was
found+fixed later (next entry). → [model/predictors](../model/predictors.md#stick-angle-table-corruption-resolved).

## Stick-angle table — read-latency corruption in angle + stick_dist (gold re-dump)

The `advancewith`-regenerated table still carried a 1-frame **read-latency** artifact: the set/read
dump pipeline (`tww-python-scripts/stick_angle_grid_dump.py`) read `mMainStickAngle` / `mStickDistance`
one frame before the game had updated them. ~2609 `angle` cells and the **entire** `stick_dist` column
were lagged (`stick_dist` shifted ~2 rows), worst at exact-diagonal cells: (160,160) read 24260 vs the
correct 24576, (160,112) 15162 vs 15771. The sim reads the `angle` column to drive facing, so this was
a **real** sim-vs-live facing desync (3.35° at (160,112), confirmed via a clean-DTM negative-v true-
superswim test; corrected cell → 0.00°). `test_complicated` missed it — its inputs (sx 98–157,
sy∈{0,255}) never reach the sx≥160 / diagonal region.

Fixed by a settle-and-verify gold re-dump (`harness/capture/stick_grid_redump.py` +
`run_parallel_dump.py`): hold each stick through a multi-frame settle, verify stability across two
consecutive settled frames (0 unstable / 65536), per-frame air/speed/pos re-lock. New table: `angle`
bit-consistent with `atan2f(x,−y)` for all 65536 cells, exact-diagonals on the 45° grid, and
`stick_dist == value == mMainStickValue == /54` (so `test_partial_magnitude.py` now LOCKS the grid ==
closed-form magnitude, inverted from the old "is-not-the-gain"). Integrity locked offline by
`tests/test_stick_table_integrity.py`. A pure decomp port (`mAngle = 10430.379·atan2f(x,−y)`,
`mStickDistance = min(hypot/54,1)`) reproduces the angle at non-boundary cells but diverges from live
Dolphin at 17.6 % of cells (deadzone-boundary/octagon byte-mapping), so the live capture — not a
closed form — is authoritative. → [model/predictors](../model/predictors.md#stick-angle-table-corruption-resolved).

## Omega camera grid — input-path corruption + coarse subsample

The camera-rate grid had the same input-path bug (`set_gc_buttons` recorded −546 where `advancewith`
gives −547; 1816/4096 cells off by +1), and the shipped grid had been a **coarse 4096-cell
subsample** (csx 0..15 only), so `camera_arbitrary` raised KeyError off-grid for csy ≠ 128.
Regenerated first as the raw-byte grid (`omega_full_redump.py`), then **completed to the full
csx 0..255 × csy 0..255 = 65536 grid** (2026-07-01) — no more off-grid gaps; charge cases go cam=0hw.
Dump method history and the fast in-place redump are in
[camera-model-history](camera-model-history.md#omega-grid-completed). → [mechanics/camera](../mechanics/camera.md).

## Console cosine table — 1-ULP exits

x86 `cos()` differs from the console `jmaCosTable` at 2964/4096 entries; ×598-amplified, a 1 ULP
became a 0.07 v jump at pump exits. Fixed by baking the live table from `0x80498168`. →
[model/sim](../model/fp-faithfulness.md#console-cosine-and-sine-tables).

## release_ess_speed — 2-increment phase error

The exit speed was computed off the wrong (last-ESS) anim frame; the game applies `af_drag` at the
release frame (exit-frame physics + 1-frame lag), up to ~40% off when the offset lands a mid-cos
frame. Fixed by advancing the exit-frame physics before `af_drag`. →
[mechanics/neutral](../mechanics/neutral.md#ess--neutral-exit-release_ess_speed).
