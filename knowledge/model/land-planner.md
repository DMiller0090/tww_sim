# The land input planner — target (x,z) → input sequence

**Answers:** What is the land planner's goal? How does `plan_land.py` reach a target (straight walk,
proportional glide, the C-up freeze)? What is the live-valid stick set? How close can it stop, and
what are the current gaps (curve residual, pillar collision)? What are the two use-case accuracy bars
(seam clips vs RTA setups)?
**Status:** milestone 1 — straight-walk reach bit-exact live; float-perfect z=2000 stop (1 ULP live)
via C-up speed-cancel. Open: curved-walk chase residual, wall/pillar collision (unported), A*.
**Source:** `tww_sim/land/plan_land.py`; live-validated via `advanceseq`. Forward model:
[land sim](land-sim.md) · [land movement](../mechanics/land-movement.md).

---

Where the [swim planner](planner.md) optimizes 1-D distance, the land planner's objective is a **2-D
position**: initial `LandState` + world target (x, z) → an input sequence that arrives there. Two use
cases set very different accuracy bars:

- **A. Seam clips (primary, knife-edge).** A clip is a boolean — the swept A→B segment threads a
  sub-ULP sliver between two triangle planes. You can't re-plan a mispredicted boolean, so **bit-exact
  position AND FMA-faithful collision are on the critical path**. Needs the approach movement
  (bit-exact) plus a collision predicate (`cM3d_CalcPla` + segment-vs-triangle, `fmadds`-faithful,
  seam triangles dumped from RAM) — the predicate is **unbuilt**; walking-position-exactness is the
  [FP proving ground](fp-faithfulness.md) for it.
- **B. RTA setup finder (robust/discrete).** Search discrete, human-executable action lattices for
  faster setups that *reliably* hit a position; score by **basin width** (timing slop tolerated),
  fastest-among-robust. Same forward model + predicate, evaluated over a perturbation neighborhood.

## Milestone 1 — straight-walk reach (`plan_land.py`)

- `world_angle_s16(dx, dz)` — travel bearing (s16, 0 = +z, 0x4000 = +x) matching
  `pos_x += d·sin(travel); pos_z += d·cos(travel)`.
- `stick_for_bearing(theta_s16, csangle, msd)` — inverse stick for the walk want-target
  `m34E8 = m34DC + csangle` (`m34DC = stickAngle + 0x8000`), adding the 15-unit dead zone back per
  axis. **Live-faithfulness rule:** for `msd ≥ 1` emit the TRUE full corner (r = 112 → 255/1); for a
  partial use the dead-zoned magnitude `msd·54`; **never** the ambiguous near-cap band (see the
  live-valid set below).
- `reach_straight(seed, tx, tz)` — aim full stick at the LIVE bearing each frame; sweep the release
  frame for minimum **resting** distance and stop at the FIRST local min (past it the re-aim orbits
  back through turn procs). Best safe-stick stop ≈ 0.23u, bit-exact live.
- `reach_precise(seed, tx, tz, k=0.5)` — proportional-speed glide (target speed = `k·remaining`)
  staying IN MOTION, then truncation-search the tail cut. Rests ~0.10u from target — the smooth-walk
  floor (min sustainable crawl); sub-0.1u needs tap-inch hops (a follow-up).

**Straight walk (0, 2000): bit-exact** (sim-vs-live Δ = 0.0003u). The milestone-1 core is real.

## Live-valid stick magnitudes

`_set_stick_data` uses `msd = min(hypot(deadzone)/54, 1)`, which **caps**; live PADClamp saturates
differently near the cap. So `Y ≤ 191` (msd ≤ 0.889) is bit-exact and `(128,255)` (true full) is
exact, but **`Y ∈ [192,254]` diverges live** (a walk at `(128,196)` gives sim v=16.38 vs live 15.76).
**Any land search over partials must restrict to `Y ≤ 191 ∪ {255}`; never emit 192–254.** From a
standstill the walk needs `msd > 0.5` to move (`(128,171)` is the smallest that cruises); the L-target
`ATN_MOVE` unlocks lower speeds (`Y=168` → 3.64). Detail: [land movement](../mechanics/land-movement.md#values).

## Float-perfect stop — the C-up speed cancel

Natural walk-stop coasts a quasi-fixed decel arc and floors at ~0.019u; float-exact resting is
unreachable that way. The **C-up speed cancel** freezes mid-motion instead: while walking, half-press
L for one frame (ends manual cam), then neutral stick + C-stick full up → after 2 latency frames + 1
decel frame the speed snaps to 0 and position locks. The sim reproduces the freeze with **zero new
code** — `frozen_pos = walk-sim pos 3 frames after the neutral+C-up input`. Because it happens
mid-motion (no resting dead-band), a slow-cruise approach tuned by a diverse beam (live-valid mags)
drilled the freeze to **z = 2000.0001221 live = 1 float32 ULP from 2000.0**, deterministically. The
last ULP is bounded by the sim's land-position residual — see
[land sim](land-sim.md#land-position-accumulates-in-f32-not-an-f64-running-sum). Mechanics of the
cancel: [land movement](../mechanics/land-movement.md#precise-stopping-live-valid-stick-magnitudes-l-target-and-the-c-up-speed-cancel).

## Open gaps

- **Curved-walk chase residual (sub-2u).** A sustained gentle-curve walk (~15° heading over ~1900u)
  drifts 0.5–1.6u — the walk facing/travel chase (`cLib_addCalcAngleS`) in a continuously-turning
  MOVE, a regime the [land tests](land-sim.md#enforced-to-the-byte-by-two-tests) don't stress (walk is
  dead-straight; turn tests are big reversals). NOT the camera (csangle stays 0). Fine for flavor B
  (unit-scale basins); must be closed before flavor-A clip planning.
- **Wall/pillar collision (unported).** A diagonal target that crosses a pillar mispredicts by ~36u.
  v1 targets OPEN GROUND only (the +z corridor is clear to ~2000). Collision is the flavor-A
  centerpiece (see above).

## Roadmap

Land A* mirroring the [swim planner](planner.md) machinery (sig/dominance/`_hcost`) over a 2-D target
+ steerable facing (reusing `plan.py`/`optimize.py`); flavor B (basin-scored reach) first, flavor A
(clip predicate) after the collision core and the curve residual are closed.

## See also

- [Land sim](land-sim.md) · [Land movement](../mechanics/land-movement.md) ·
  [Swim planner](planner.md) · [FP faithfulness](fp-faithfulness.md) (collision on-ramp).
