# The offline land sim — position precision & status

**Answers:** How does the land sim accumulate position (why f32, not an f64 running sum)? What is the
partial-magnitude (`Y171`) regime and why does it exercise the foot toe? How accurate is it — what
are the remaining ULP residuals and which tests gate them?
**Status:** float-perfect (0 ULP) on the straight full-deflection walk, the front-roll, and the
full-speed **slip** skid + reversed-walk arc; ~1 ULP `speedF` / 2 ULP `pos_z` on the `Y171` partial
cruise. Open residuals: planted-foot toe + entry-morf jnt0 sub-ULP FK-X frontier (6 red
`tests/test_land.py` cases: `Y171` speedF/pos, ATN `ebs`/`brake_right`, `waitturn`, deep-release f37).
**Source:** `tww_sim/land/land.py`; the [anim engine](anim-engine.md) (foot FK → `speedF`) and the
[FP contract](fp-faithfulness.md). History: [history/resolved-bugs](../history/resolved-bugs.md).

---

`tww_sim/land/land.py` (`LandState`) simulates walk, ATN move, front-roll, and reversal turns; the
movement mechanics are in [land movement](../mechanics/land-movement.md). Position is bit-exact for
every tech that has anim data (no `_pos_fallback`). The precision hinges on two things: **f32
position accumulation** and the [world-space foot FK](anim-engine.md#foot-fk-runs-in-world-space) that
produces `speedF`.

## Land position accumulates in f32 (not an f64 running sum)

`pos.x`/`pos.z` are **f32 fields** in the game (`cXyz`), so every frame the game re-stores the running
total as f32: `pos.z = f32(pos.z + f32(speedF·cos))`. `LandState.step` therefore accumulates position
in f32 too — `self.pos_z = f32(self.pos_z + f32(d·cos))`, **not** a Python-f64 `+=` running sum. An
f64 running sum is *more* precise than the hardware and drifts ~**2.5 ULP** (~0.0003u) from the game's
f32-accumulated position over a ~115-frame walk — precisely the wrong direction for float-exact work.
With f32 accumulation + the world-space foot FK the sim is **float-perfect (0 ULP)** over the straight
**full-deflection** walk (see [land movement: float-exact stop](../mechanics/land-movement.md)); the
last residuals are the planted-foot toe (1–2 ULP on the ATN/waitturn tails, the sub-ULP FK-X frontier).

## `speedF` snaps to 0 below 0.05 (the slip-skid tail)

`posMoveFromFootPos` (`d_a_player_main.cpp:2418`) snaps the composed speed to zero every frame:
`if (fabsf(sp7C.z) < 0.05f) { speedF = 0; speed.x = speed.z = 0; }`. This runs for **all** grounded
procs, but only bites where the sim previously drove position from raw `mNormalSpeed`. The **slip**
skid bleeds `mNormalSpeed` via `cLib_addCalc` (`minStep 0.1875`), which lands one frame at ≈`0.0045`
before the hand-off to `MOVE_TURN`; the game reads `speedF == 0` there (`m3598 == 0`, so `sp7C.z ==
mNormalSpeed < 0.05`), so the skid does **not** creep that last sub-0.05 step. Omitting the snap left
a constant ≈0.0045u forward leak → the reported **74-ULP** endpoint drift (74, not 37, only because
`pos_z` had crossed `1024` where the ULP halves). The front-roll floors at `ROLL_MIN` (5.0) so it
never reaches the snap. The `0.05` threshold is modeled in `foot_speedf._foot_speedf`
([anim engine](anim-engine.md)) and applied in `LandState.step`'s SLIP/ROLL branch.

## Partial-magnitude regime (`Y171`, `msd`≈0.52)

> Not to be confused with **which partial stick magnitudes are safe to emit** in a land plan (the
> live-valid `Y ≤ 191 ∪ {255}` band, never `192–254`) — that is a stick-input rule, covered in
> [mechanics/land-movement.md](../mechanics/land-movement.md#precise-stopping-live-valid-stick-magnitudes-l-target-and-the-c-up-speed-cancel). This section is about the sim's *speed regime* at `msd≈0.52`.

The z=2000 stop rides this regime (verified 2026-07-04). The full-deflection golden covers only
`msd` 0/1, whose DASH cruise has `m3598 == 0` (so `speedF == nspeed` and the foot-toe term drops out
entirely). The `Y171` cruise instead sits in **regime 1 (WAITS↔WALK, `m3598 == 1.0`)**, where
`speedF` **IS the plant-foot toe delta** — making the `Y171` golden the *only* land test that
exercises the foot-FK toe every cruise frame.

Driven correctly it tracks live to **~1 ULP `speedF` / 2 ULP `pos_z`** — NOT the "tens/thousands of
ULP" an earlier draft reported. That scare was a **harness artifact**: driving the raw `FootSpeedF`
from the golden's `ns` column, written with `%g` (6 sig figs), fed a *truncated* nspeed
(`4.57064` vs `4.5706443786`) into `f30 = ns/17` → the WAITS↔WALK blend ratio shifted → the toe pose
diverged. Fixed: golden `ns`/`msd` are now full-precision (`repr`), and `test_speedf_y171` drives
**LandState** (full-precision nspeed + the world position — the foot FK quantizes the toe at world
magnitude, so the driver MUST get `set_pos` each frame; posing at the stale seed z was the other half
of the artifact). For the z=2000 beam a 2-ULP `pos_z` oracle is likely already good enough
(live-verify once). Gated by `test_speedf_y171_matches_live_bit_exact` /
`test_pos_z_arc_y171_matches_live_bit_exact` and the `walk_y171` case in `run_land_tests.py`.

## Open residuals (the 7 red land tests)

With the [fres + non-fused fixes](fp-faithfulness.md) the walk-blend foot toe (frames 5/6/34) is
bit-exact and the straight walk arc is float-perfect. What remains:

- **Entry-morf jnt0 (sub-ULP).** The first 1–2 MOVE frames have jnt0.z ~5 ULP off (decaying with the
  morf rate) — seed/ratio/rate/morf-fusion all verified exact, so it is a `calc_transform`/Hermite
  sub-ULP in the root Z-translate track. It leaks into the ATN/turn endpoints
  (`ebs` 1, `brake_right` 2, `waitturn` 1 ULP) and is the `speedf` test's frame-5 miss.
- **Toe.z world-quantization (~0.6 ULP)** at f26/27 → the `Y171` 2-ULP `pos_z`.
- **`slip` (74 ULP)** — a separate ANM_SLIP skid-modelling gap, not a foot-FK residual.

These are immutable per the [locked-test rule](../../tests/dolphin/README.md#locked-tests-are-immutable-hard-rule):
red until the sim closes the gap; never edit the test/golden to pass.

## Enforced to the byte by two tests

- **Live** (`tests/dolphin/run_land_tests.py`, the accuracy gate — live is the source of truth): pass
  condition is **0 ULP vs live**, no tolerance, no xfail. `walk/brakeslide/face_left/roll_run/
  roll_slow/roll_settle/roll_ebs/moveturn` pass; `ebs/brake_right/waitturn/slip` (and the `Y171`
  cases) are the to-do list.
- **Offline** (`tests/test_land.py`, no Dolphin): the token-cheap **shadow** — the golden
  (`tests/golden/land_walk_speedf.csv` + `CASE_POSZ`) is the GAME's live f32 bytes (captured by
  `tests/gen_land_golden.py`), and the tests assert `f32_bits(sim) == live`, so the SAME techs fail
  (7 red: `speedf` frame 5, `speedf_y171`, `pos_z_arc_y171`, `ebs`, `brake_right`, `waitturn`, `slip`;
  173 pass). Regenerate the golden from live after a sim fix via `python tests/gen_land_golden.py`.

## See also

- [Anim engine](anim-engine.md) (produces `speedF`) · [FP faithfulness](fp-faithfulness.md) ·
  [Land movement](../mechanics/land-movement.md) · [Land planner](land-planner.md).
