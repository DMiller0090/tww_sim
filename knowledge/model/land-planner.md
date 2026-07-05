# The land input planner — target (x,z) → input sequence

**Answers:** What is the land planner's goal? How does `plan_land.py` reach a target (straight walk,
proportional glide, the C-up freeze)? What is the live-valid stick set? How close can it stop, and
what are the current gaps (curve residual, pillar collision)? What are the two use-case accuracy bars
(seam clips vs RTA setups)?
**Status:** milestone 1 — straight-walk reach bit-exact live; `reach_freeze` deterministic C-up-cancel
stop now **robustly float-perfect AND live-re-gated 0 ULP** (2026-07-05) — freezes byte-for-byte at the
sim's `freeze_pos.z` for every reachable on-axis target, and within a few float32 ULP (< 0.001u) of ANY
on-axis target offline (all-live-valid), not just lucky ones. Sweeps are O(n) via bit-exact mid-walk
clone. The C-up freeze + B-cancel + re-walk is now **input-driven in `step()`** (raw stream, 0 ULP live;
2026-07-05f) — a freeze plan is just an input sequence. The **fewest-frame bit-exact stop is the START
crawl** (2026-07-05h): fine-tune the from-rest accel frames (free low-speed fine grid), then cruise full
+ C-up — bit-exact ~+7 over the full-up floor, live-proven 0 ULP (supersedes chained/end-crawl for fewest
frames). Open: make the start-crawl solve sub-second (δ-prediction filtered search) + productionise into
`reach_freeze`; the chained-over-streams planner is done (modest ~1–3f); off-axis octagon clamp,
collision, A*. (Note: `reach_straight`/`reach_precise` rest are target-SENSITIVE, 0.1–9u
— use `reach_freeze` for exact stops.)
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
  back through turn procs). Bit-exact live, but the rest is **target-SENSITIVE** (0.1–9u): the 17u
  full-speed step + fixed ~49u neutral coast lands rest on a coarse lattice.
- `reach_precise(seed, tx, tz, k=0.5)` — proportional-speed glide (target speed = `k·remaining`)
  staying IN MOTION, then truncation-search the tail cut. Also **target-sensitive** (0.1–9u): the
  proportional decel LAGS, so it overshoots-at-speed on short trips and stalls to a dead stop on long
  ones. For an exact stop use `reach_freeze`. (Older docs claimed a uniform "0.10u smooth-walk floor";
  overturned — [history](../history/land-planner-precision.md).)
- `reach_freeze(seed, tx, tz)` — the **robustly float-perfect** approach via the C-up speed cancel
  (below): within a few ULP of any on-axis target.

All three sweep by **cloning a snapshot** at each candidate release/cut/cancel frame rather than
re-simulating the walk prefix — bit-exact because `LandState.clone()` is faithful **mid-walk** (it
state-copies the anim engine's toe stream + oldframe-morf, not a fresh rest rebuild). That turns the
O(n²) release sweeps O(n) (`reach_precise` to a far target: 246k → 4k `step` calls). See
[FP faithfulness](fp-faithfulness.md#cython-fast-path).

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
code** — `frozen_pos = walk-sim pos 3 frames after the neutral+C-up input` (`plan_land._freeze_pos`).

`reach_freeze` is the **deterministic offline planner** for this, in **three phases** (each
O(1)-per-candidate on the bit-exact mid-walk clone):

1. **Cruise** full-speed until the freeze lands within `coarse_gap` (60u) of the target.
2. **Sustained msd-0.5 crawl** (stick `(128,170)`, the min STABLE crawl — nspeed≈4.25 → ~1u/frame),
   snapshotting each frame until the freeze crosses the target. This is the key to robustness: it
   guarantees a **uniform ~1u fine straddle for ANY target**. The freeze coast scales with approach
   speed, so you must **arrive SLOW to arrive fine** — a proportional glide overshoots-at-speed on
   short trips and stalls on long ones, which is why the old glide-based drill was float-perfect only
   at lucky targets.
3. **Dedup-by-freeze-position beam drill** from a few crawl frames before the crossing: branch over
   `NEUTRAL ∪ {live-valid integer walk sticks}` (`msd ≤ 0.889 ∪ {1.0}`, aimed at the live bearing),
   keeping a frontier deduped by quantized freeze position and capped to those nearest the target.
   This fills the ~1u crawl step down to the float floor.

On the open **+z corridor** the production beam rests within **~1–4 float32 ULP (< 0.001u)** with an
**all-live-valid** seq. That residual is **NOT sim error** — the sim reproduces live `pos_z` at **0 ULP**
([land-sim](land-sim.md), gated no-tolerance by `run_land_tests`), so an offline *exact* freeze lands
exactly live (**confirmed 2026-07-05** by driving whole plans in Dolphin: `pos_z` froze byte-for-byte at
the sim's `freeze_pos.z` for z = 1500 / 2000 / 2500, `pos_x` = 0).

**Exact-float freeze IS reachable (resolved 2026-07-05c) — live-proven for `2000.0` AND `1800.0`.** The
~1–4 ULP is the **production beam UNDER-EXPLORING the tail**, NOT a lattice floor: the beam dedups by
freeze POSITION (+ a `beam_width` cap), which collapses the **momentum diversity** that fills the last
ULP. Two fixes recover it: (a) let the last few frames vary FULLY (unpruned over the live-valid stick
set) — depth-3 already hits many targets exactly; (b) better, a **windowed-deepening** search that keeps
every distinct STATE still short of the target within a small window (dedup by momentum, NOT position)
and deepens only those — the near-target frontier stays small, so depth-4/5/6 is cheap (~16 s, not the
~65⁴/snapshot ≈ 30 min a naïve deep drill would cost). This hit **every target tried exactly within
depth-4**, including z = 1800 / 2000.5 that a depth-3 unpruned drill misses. Since the sim is 0-ULP vs
live, the offline-exact solve lands exact on console: **verified — console froze at EXACTLY `2000.0`
(`0x44fa0000`) and `1800.0` (`0x44e10000`), `pos_x` = 0** (offline solves seconds–~16 s, early-exit).
Not yet productionised into `reach_freeze` (would be an `exact=`/windowed-deepening mode + offline & live
gates). A *universal* all-f32 reachability PROOF is still open, but empirically every target hits by
depth-4. **Off-axis freeze plans are not yet live-valid** — an off-axis
crawl emits diagonal sticks needing the octagon clamp (a separate open decode issue). Mechanics of the cancel:
[land movement](../mechanics/land-movement.md#precise-stopping-live-valid-stick-magnitudes-l-target-and-the-c-up-speed-cancel).

## Fewest-frame bit-exact stop — the START crawl (2026-07-05h)

The **cheapest** bit-exact freeze is not a slow approach (reach_freeze rests ~+19..32 over the full-up
floor) nor a chained coarse+fine (below, ~+12): it is to do the ULP fine-tuning at the **START**, then
run full speed to the target. Bit-exact needs a few LOW-SPEED frames (the freeze grid is only ULP-dense
below the 17u speed cap — see next paragraph); at the *start* the from-rest acceleration frames are
low-speed **for free**, so you spend nothing extra:

1. **k fine start frames from rest** — the natural accel ramp, magnitudes slightly reduced (live-valid
   Y∈[171,191]∪{255}). At low speed each frame's freeze step is fine; k=3–4 of them fill to the ULP (the
   same momentum-diversity that fills the drill's last ULP, but at zero frame cost).
2. **full-forward cruise** (exactly +17.000/frame), half-L on the last frame;
3. **C-up cancel** → the freeze locks on the **exact** float — the start offset shifted the whole
   full-speed lattice onto the target.

**Bit-exact at a consistent ~+7 over the full-up floor** (z=2000 → 80f/+7.3; z=1500 → 50f/+6.7;
z=2810.99 → 128f/+7.6), and **live-proven 0-ULP** (z=2000 froze at exactly `0x44fa0000` in Dolphin).
Prototype `_notes/chained-freeze-probes/start_freeze_solve.py`; the plan is a raw stream (the freeze is
input-driven in `step()`). **Open: solve time is 5–63s** (ordered exhaustive; k=4 ≈ 234k candidate starts
× a full cruise each — `freeze_below` sawtooths over [T-17,T] so no monotonic prune, and the pose is
irreducible). The fix is a **δ-prediction filtered search** (predict from the cheap position deficit +
the ±0.3u `coast(phase)` model, full-cruise only the ~24% predicted near T, hierarchical δ-prune the k=4
subtrees) — not yet built. Not yet productionised into `reach_freeze`.

**Why full-speed windows can't do it (settled, measured):** perturbing a window of the *full-speed*
cruise cannot hit bit-exact — at the 17u/frame speed cap momentum is pinned, so the freeze grid is coarse
(1 slid frame → nearest 0.0177u; an end-anchored 3-frame window, **exhaustive 274,625 combos → 0 exact
hits**; k=4/k=5 too). The smallest live-valid stick step at full speed drops speed ≥3.5u, so there is no
sub-ULP adjustment. Bit-exact *requires* momentum below the cap — which the start crawl (and the drill)
provide. **The walk anim is a ~7-frame loop but precesses sub-frame** (per-frame anim advance isn't
frame-commensurate), so the freeze coast drifts ~0.02–0.3u/cycle and is **not bit-exactly cacheable** by
frame-phase (the pose sim is the ground truth); that same precession is what lets the freeze reach *any*
float. Native `.pyx` cruise-batching won't help — `co.step` is 6.88µs (pose-bound), Python dispatch 0.09µs.

## Roadmap: chained coarse+fine freeze (B-cancel) — fewest frames (TAS)

The yardstick is the **pure full-up travel floor** ≈ `(target − 764.08)/17` frames (hold full-up the whole
way). An exact-float stop costs ~12–17 frames over that floor either way (you must decelerate and land on
the exact float). The idea of the **B-cancel chained freeze** (see [land movement](../mechanics/land-movement.md#precise-stopping-live-valid-stick-magnitudes-l-target-and-the-c-up-speed-cancel)):
**coarse-freeze from FULL speed** (0-ULP, lands on a ~17u lattice) → **B-cancel** → resume walking **from
rest** → short fine-walk → **fine-freeze** on the exact float — trades the single-freeze's slow approach
for a coarse stop + short re-walk.

**The freeze/B-cancel/re-walk mechanic is now MODELED, input-driven, and live-proven 0 ULP** (2026-07-05f).
The former blocker — the post-B-cancel re-walk inheriting the freeze's **foot-anim phase** (same nspeed,
~2× smaller low-speed `dz` than a cold walk) — is solved: it's the `m34C3 = 2` phase-preservation of the
subjectivity/WAIT blend (root cause + decomp cites in [land movement](../mechanics/land-movement.md#precise-stopping-live-valid-stick-magnitudes-l-target-and-the-c-up-speed-cancel)).
`LandState.step()` now consumes the **raw controller stream** — the C-up cancel gesture, the B button, and
the resume all fall out of the input + `INPUT_DELAY` (+1 camera frame on entry), so a plan is just an input
sequence that plays 1:1 on sim + Dolphin. Tracked live gate `tests/dolphin/spotcheck_subj_inputdriven.py`
(varied timings, 0 ULP both paths); the manual `enter_freeze/hold_freeze/resume_walk` API is retained for
fast planner re-simulation.

**Measured savings (chained_solve prototype, 2026-07-05e/f) — modest, NOT the optimistic ~7–10.** Best
chained plans vs the single-freeze baseline: **z=2000 → 86f** (vs 89), **z=2810.98 → 135f** (vs 138),
**z=1800 → ~74f** (vs 74). So the chain shaves only **~1–3 frames** vs single-freeze, and sits **~+12–14
over the full-up floor**. The exact-float stop is intrinsically expensive; the coarse+fine split barely
beats a good single freeze.

**Remaining: redo the chained PLANNER search over REAL input streams** (now that `step()` is input-driven).
Search cruise length × B-cancel timing × re-walk sticks × fine-cancel point; objective = frames over the
full-up floor, **excluding the final cancel's lock frames** (those are the "stop", not travel). Constrain
B-cancel to the realizable region (≥~3-frame resume latency). Playback is then the same stream (live gate
trivial). Compare honestly vs single-freeze — if the win stays ~1–3 frames, it may not be worth
productionising into `plan_land.py`.

## Open gaps

- **Curved-walk chase residual (sub-2u).** A sustained gentle-curve walk (~15° heading over ~1900u)
  drifts 0.5–1.6u — the walk facing/travel chase (`cLib_addCalcAngleS`) in a continuously-turning
  MOVE, a regime the [land tests](land-sim.md#enforced-to-the-byte-by-two-tests) don't stress (walk is
  dead-straight; turn tests are big reversals). NOT the camera (csangle stays 0). Fine for flavor B
  (unit-scale basins); must be closed before flavor-A clip planning.
- **Wall/pillar collision (unported).** A diagonal target that crosses a pillar mispredicts by ~36u.
  v1 targets OPEN GROUND only. Because the sim has NO collision, a plan can silently target past a
  wall: on the `land_flatwalk` anchor the +z corridor ends at a **wall at `pos_z ≈ 2932.4294`
  (`0x453746df`)** — a plan for z ≥ 3000 freezes AT the wall, not the requested z (live-observed
  2026-07-05). Keep on-axis targets in `(764.08, 2932.43)` on this anchor. Collision is the flavor-A
  centerpiece (see above).

## Roadmap

Land A* mirroring the [swim planner](planner.md) machinery (sig/dominance/`_hcost`) over a 2-D target
+ steerable facing (reusing `plan.py`/`optimize.py`); flavor B (basin-scored reach) first, flavor A
(clip predicate) after the collision core and the curve residual are closed.

## See also

- [Land sim](land-sim.md) · [Land movement](../mechanics/land-movement.md) ·
  [Swim planner](planner.md) · [FP faithfulness](fp-faithfulness.md) (collision on-ramp).
