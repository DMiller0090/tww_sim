# The route planner & optimizer

**Answers:** How does the planner search? What's the objective? Why are mid-swim pumps disabled?
Why the crossover (build + cruise) decomposition? What's the balloon-swim option?
**Status:** validated (live-confirmed plans, frame-exact via DTM).
**Source:** `superswim/plan.py`, `superswim/optimize.py`; the legacy C# `SwimEnvironment`/PSO.

---

## Objective: minimum frames to a destination

The TAS objective is **minimum frames to reach a fixed target distance D**, not max distance over a
fixed window. This shapes the endgame: near D you should NOT boost (no frames to recoup the
[turnaround](../mechanics/turnaround.md) tax), and the optimum wants to finish in
[neutral](../mechanics/neutral.md) (drag-free) for the last stretch — exiting at a good
[head-bob phase](../mechanics/animation.md).

## Search

- **Beam search** over the per-frame {ESS, charge} decision space (`optimize.py`), keeping
  anim-phase diversity so a state that just paid a boost (lower x, better anim) isn't pruned by raw
  x. Air is omitted from the dominance key — every action decrements air by 1, so the whole frontier
  shares the same air per generation. Anim bucket = 0.03.
- **Speed-retention prune** (`plan_min_frames`, default `speed_gate=0.98`): drop any successor that
  keeps < 98% of the parent's `|v|`, relaxing to 90% (`speed_gate_end`) inside the last ~40 estimated
  frames so the terminal neutral dash still enters. Only speed LOSSES are pruned — charge/reboost
  build `|v|`, so the only frames it touches are off-peak neutral-dip/exit `af_drag` frames. Loss-free
  for the min-frames objective (retained speed compounds over remaining frames, so a big one-frame
  dump only pays near the end); validated byte-identical on the golden suite and cruise 200k/400k/500k
  + a full build+reboost, at 3–7× fewer nodes on cruise. Set `speed_gate=0` to disable.
- The legacy C# tool used Particle Swarm (`Omega=0.7627, Phi_G=1, Phi_P=3`) over `[chargeTime,
  essTime]` with neutral time computed analytically; PSO is overkill for this low-dimensional,
  monotonic-ish space — beam/closed-form is more reliable.
- **Closed-form helpers**: `time_to_travel_distance = (√(2·c·d + v²) − v)/c`; `ess_normal_minima`
  solves the optimal ESS↔neutral switch distance analytically; `avg_ess_rate = (4+3π)/(5π)` (mean
  speed fraction retained as displacement while ESSing).

## Why mid-swim pumps are off by default

Mid-swim pumps (`neu→ess` re-entries) are disabled by default (`allow_pump=False`); neutral is
planned as a single one-way **terminal dash** — a predictable exit from sustained ESS. Three reasons,
none of which is a sim-modeling failure:

- **No cruise payoff.** Pumps only preserve speed cheaply at LOW speed; exhaustive search finds no ESS
  pump beats the pure neutral boost at cruise. Pumps pay in the
  [build](../strategy/phase-ordering.md), not the cruise.
- **Long-chain precision floor.** The sim models the [×598 scramble](../mechanics/pumps.md#the-x598-scramble)
  exactly — cold-start and short pump chains are bit-exact vs clean DTM (an 11-pump build matched live
  `v/anim/air/state`, `dan`=0.000) — but beyond ~1.5 pump cycles a ~1e-4 per-entry anim oscillation
  accumulates (~0.07 v/pump). See [open-questions](../history/open-questions.md).
- **End-to-end validation pending.** A long pumped plan has not yet been re-validated via clean DTM.

The historic "band-1 200k plan bled to zero, 71% short" was **not** a sim error: it was the
`advanceseq` pipe-delivery artifact ([bug#2](../history/resolved-bugs.md)) plus planning from a
truncated cold-start seed. Clean-DTM playback tracks the sim frame-exact.

**Cold-start seeding:** seed builds with the savestate's LOGGED move0 mRate (`cold_mrate=`, which
seeds `ColdStartSwimState`) and a FULL-PRECISION anim — a truncated seed diverges ×598 through pumps.

## Why the crossover (build + cruise) decomposition

The flat pump DP saturates: the x598 pump scramble lands a DISTINCT anim phase per pump entry, so the
frontier hits `max_frontier` on every layer and dominance cannot merge genuinely-distinct futures
(empirically confirmed — frontier pinned at 8000 even after coarsening anim AND v buckets). A flat DP
wastes its whole long-cruise horizon carrying a saturated pumped frontier for nothing (cold
dest=100000: 511s, 388/396 layers capped). **Pumps only pay in the low-speed BUILD** (measured:
cruise dest=60000 pump vs no-pump both 41 fr; greedily inserting pumps into the pump-free optimum
never improves it). So the planner decomposes into a **pumped build + a pump-free cruise suffix**
(crossover), continuing each build-frontier node pump-free toward the far destination. Build distance
scales with seed speed (a fast seed is already cruising → pumps never help → pure cruise DP).

## Balloon swim

Project at current velocity for N frames, then **0.75× speed on landing** + 27-frame resurface
(−3/frame), forced air refill to 900. Decomp confirms the 0.75 landing multiplier
(`mNormalSpeed *= 0.75f`, d_a_player_swim.inc:137) and the 900 air reset (line 126).

## See also

- [Sim precision](sim.md) · [Pumps / x598](../mechanics/pumps.md) ·
  [strategy/reboost](../strategy/reboost.md) · [strategy/phase-ordering](../strategy/phase-ordering.md)
  · [history/resolved-bugs](../history/resolved-bugs.md) (bug#2 / DTM delivery).
