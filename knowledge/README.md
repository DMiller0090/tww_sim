# tww_sim knowledge base

The retrieval-first knowledge base for TWW player physics — **superswimming** (swim) and **land**
movement — plus strategy, the shared engine, and the sim/planner model. **Start here** — find your
question below, follow the link, read one small page.

## How this is organized

Knowledge is split by **layer** — different kinds of fact with different lifespans:

| Layer | What | Lifespan |
|-------|------|----------|
| [`mechanics/`](mechanics/) | Game truth — formulas, constants, decomp-grounded behavior | timeless |
| [`strategy/`](strategy/) | TAS heuristics — reboost, dips, phase ordering | evolves |
| [`model/`](model/) | How the sim/planner implements it — engine (FP, anim), swim, land | tracks code |
| [`reference/`](reference/) | [Constants](reference/constants.md), [addresses](reference/addresses.md), [glossary](reference/glossary.md), [commands](reference/commands.md), [data](reference/data.md) | lookup |
| [`history/`](history/) | Provenance, dead ends, superseded conclusions, open questions | frozen |

**`history/` is not current truth** — its pages carry a `status: historical` banner. When you grep
for an answer, prefer the mechanics/strategy/model/reference pages; only read history for "how did we
get here" or provenance. Every page opens with an **`Answers:` / `Status:` / `Source:`** header so
you can triage in one glance.

## Question index

### Basics
- **What is superswimming / potential vs true speed?** → [mechanics/overview.md](mechanics/overview.md)
- **What does <term> mean?** (csangle, ESS, head-bob, x598, …) → [reference/glossary.md](reference/glossary.md)
- **What is the value of <constant>?** → [reference/constants.md](reference/constants.md)
- **How do I run the sim / planner / a live test?** → [reference/commands.md](reference/commands.md)

### Charging, ESS, neutral, decay
- **How fast does charging build speed / what's the gain formula?** → [mechanics/charging.md](mechanics/charging.md)
- **What is ESS / what stick values / why is diagonal more efficient?** → [mechanics/ess.md](mechanics/ess.md)
- **How much speed do I lose for a given stick value?** (continuous decay law) → [mechanics/decay-curve.md](mechanics/decay-curve.md)
- **What does neutral do / is it really −2 / what's the exit-release speed?** → [mechanics/neutral.md](mechanics/neutral.md)
- **How does the animation cycle / head-bob drag / true displacement work?** → [mechanics/animation.md](mechanics/animation.md)

### Turnaround & arrow
- **How do turnaround frames work? What's the angle threshold?** → 45° off straight-back (`0x6000` = 135°) → [mechanics/turnaround.md](mechanics/turnaround.md)
- **How do you reorient the charge axis?** → [turnaround.md#reorienting-the-charge-axis-turnaround-chains](mechanics/turnaround.md#reorienting-the-charge-axis-turnaround-chains)
- **What is arrow swimming / charge-rate loss / tip-over / spin-up?** → [mechanics/arrow.md](mechanics/arrow.md)
- **Does arrow swimming actually save time?** → **no** (exhaustive offline sweep, 0 wins; best case loses +4 fr) → [arrow.md#does-arrow-swimming-save-time--no-offline-exhaustive](mechanics/arrow.md#does-arrow-swimming-save-time--no-offline-exhaustive)

### Strobo & reboost
- **What is the stroboscopic effect / at what speeds?** → ≈ −794 / ≈ −1630 (air-dependent) → [mechanics/strobo.md](mechanics/strobo.md)
- **Does reboost save time? How big / when? Why does fixed cadence lose?** → [strategy/reboost.md](strategy/reboost.md)

### Pumps & dips
- **What is an ESS pump / the 1-frame entry tax / the x598 scramble?** → [mechanics/pumps.md](mechanics/pumps.md)
- **What is a neutral dip and when does it help?** → [strategy/neutral-dip.md](strategy/neutral-dip.md)
- **What order do the swim phases go in?** → [strategy/phase-ordering.md](strategy/phase-ordering.md)

### Camera
- **How does camera yaw affect movement / the steering law / fine steering?** → [mechanics/camera.md](mechanics/camera.md)

### Ocean world, refills & routing
- **How is the sea laid out / why is only one island loaded / what's a sploosh zone / why route around quadrants?** → [mechanics/ocean-environment.md](mechanics/ocean-environment.md)
- **How do air refills work / why is touching land fatal / flat vs wavy / corner refills / the manual-refill workflow?** → [mechanics/air-refill.md](mechanics/air-refill.md)
- **How does the sim handle unmodeled world features (refills, sploosh) / the re-plan loop?** → [model/planner.md#unmodeled-world-features--the-re-plan-loop](model/planner.md#unmodeled-world-features--the-re-plan-loop)

### Land movement (walk, brakeslide, EBS)
- **How does walking accelerate / what are the two movement angles (facing vs travel)?** → [mechanics/land-movement.md](mechanics/land-movement.md)
- **What is a brakeslide / extended brakeslide (EBS) / why does ESS left-or-right hold speed almost forever?** → is *facing* (not travel) relative to `csangle` → [land-movement.md#camera-relative-speed-preservation-the-ebs-payoff](mechanics/land-movement.md#camera-relative-speed-preservation-the-ebs-payoff)

### Model — engine (core)
- **Why f32/ctypes / op-order / `_F32_PI` / `cM_rad2s` truncation / the baked cos+sin tables / which matrix-quat ops are FMA-fused?** → [model/fp-faithfulness.md](model/fp-faithfulness.md)
- **How does the J3D anim runtime work / the 42-joint skeleton / Hermite keyframes / world-space foot FK / `PSMTXQuat` / how does the toe become `speedF`?** → [model/anim-engine.md](model/anim-engine.md)

### Model — swim
- **Why f32 / the console cosine table / CHARGE_DISP_FACTOR / cold-start mRate?** → [model/swim-sim.md](model/swim-sim.md)
- **How does the planner search / why are mid-swim pumps off by default / the crossover decomposition / the speed-retention prune?** → [model/planner.md](model/planner.md)
- **What are the predict/ modules / the off-axis residual?** → [model/predictors.md](model/predictors.md)

### Model — land
- **How does the land sim accumulate position (f32) / the `Y171` partial regime / the 7 red ULP tests?** → [model/land-sim.md](model/land-sim.md)
- **How does the land planner reach a target (x,z) / the live-valid stick set / the C-up freeze to z=2000 / seam-clip vs RTA bars?** → [model/land-planner.md](model/land-planner.md)

### Provenance & open work
- **Was <bug> a physics issue or an artifact?** (bug#2, 554, off-axis, omega grid, cosine table) → [history/resolved-bugs.md](history/resolved-bugs.md)
- **What's still unresolved?** → [history/open-questions.md](history/open-questions.md)

## Page template (for contributors)

```
# Title
**Answers:** <the questions this page answers, in plain language>
**Status:** validated | approximate | open  (+ how)
**Source:** decomp <file:line> · live <date> · History: <link>
---
<definition → formula → constants (LINK to reference/constants.md, don't restate) → validation>
## See also
```

Keep pages **small and single-topic** (one Read should answer the question). Put dated narrative and
superseded findings in `history/`, not in the truth pages. One canonical value per constant — link
to [constants.md](reference/constants.md) instead of restating numbers.

If a topic has an **unresolved verdict**, give it a short `## Open question — <current status>`
section *in the truth page* (state the current best answer + "unproven"), and link to `history/` for
the provenance. The definitive *current* answer must be reachable from the truth layer — not only
from a `status: historical` page. (Validated by the doc-eval: weak agents were told to prefer
non-history pages, so an answer that lives only in history is effectively hidden.)

The KB is regression-tested by a bounded weak-agent eval — bank + harness under [`_eval/`](_eval/).
