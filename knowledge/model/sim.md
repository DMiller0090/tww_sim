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
With f32 accumulation the sim matches live to **~1–2 ULP** over that walk (see [land-movement: float-exact
stop](../mechanics/land-movement.md)). The **remaining residual** is a sub-ULP-per-frame difference in the
anim-driven `speedF` (the foot-FK FMA chain) and/or the cos table, accumulating over the run — the open
target for bit-perfect land position. Same f32-vs-f64 discipline as the swim rules below.

**This is now enforced to the byte** by two tests with distinct jobs:
- **Live** (`tests/dolphin/run_land_tests.py`, the accuracy gate — live is the source of truth): the
  pass condition is **float-perfect, 0 ULP vs live**, with NO tolerance and NO xfail. It is currently
  **RED**: `brakeslide/roll_run/roll_ebs/moveturn` pass (0 ULP), while `walk (2), ebs (1), face_left
  (1), brake_right (2), roll_slow (4), roll_settle (2), waitturn (1), slip (74 ULP)` FAIL on the open
  residual below. Those failures are the to-do list for a bit-perfect land position.
- **Offline** (`tests/test_land.py`, no Dolphin): the token-cheap **shadow** of the live gate — the
  golden (`tests/golden/land_walk_speedf.csv` + `CASE_POSZ`) is the GAME's live f32 bytes (captured by
  `tests/gen_land_golden.py`), and the tests assert `f32_bits(sim) == live`, so the SAME techs fail here
  (10 tests red today). The per-frame walk arc localizes it: the foot-FK `speedF` is already off live at
  frame 3, and `pos_z` first flips a bit at frame 33 (decel) — the anim-FK FMA chain is the root.
  Regenerate the golden from live after a sim fix via `python tests/gen_land_golden.py`.

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
