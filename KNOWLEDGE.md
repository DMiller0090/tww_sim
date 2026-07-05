# tww_sim — Mechanics & TAS Optimization Reference

The knowledge base lives in [`knowledge/`](knowledge/), organized as small, single-topic pages by
layer so a specific fact is one search + one read away. It covers both the **swim** (superswimming)
and **land** movement models plus the shared engine (FP-faithfulness, the J3D animation runtime).

## → Start at the hub: [`knowledge/README.md`](knowledge/README.md)

It has a **question index** (find your question, follow the link) and a glossary, plus:

| Layer | What |
|-------|------|
| [`knowledge/mechanics/`](knowledge/mechanics/) | Game truth — swim ([charging](knowledge/mechanics/charging.md) · [ESS](knowledge/mechanics/ess.md) · [decay curve](knowledge/mechanics/decay-curve.md) · [neutral](knowledge/mechanics/neutral.md) · [animation/head-bob](knowledge/mechanics/animation.md) · [turnaround](knowledge/mechanics/turnaround.md) · [arrow](knowledge/mechanics/arrow.md) · [strobo](knowledge/mechanics/strobo.md) · [pumps/x598](knowledge/mechanics/pumps.md)), [land movement](knowledge/mechanics/land-movement.md), and shared ([camera](knowledge/mechanics/camera.md) · [ocean environment](knowledge/mechanics/ocean-environment.md) · [air refill](knowledge/mechanics/air-refill.md)) |
| [`knowledge/strategy/`](knowledge/strategy/) | TAS heuristics: [phase ordering](knowledge/strategy/phase-ordering.md) · [reboost](knowledge/strategy/reboost.md) · [neutral dip](knowledge/strategy/neutral-dip.md) |
| [`knowledge/model/`](knowledge/model/) | Sim/planner + engine: [FP faithfulness](knowledge/model/fp-faithfulness.md) · [anim engine](knowledge/model/anim-engine.md) · [swim sim](knowledge/model/swim-sim.md) · [land sim](knowledge/model/land-sim.md) · [swim planner](knowledge/model/planner.md) · [land planner](knowledge/model/land-planner.md) · [predictors](knowledge/model/predictors.md) |
| [`knowledge/reference/`](knowledge/reference/) | [constants](knowledge/reference/constants.md) · [glossary](knowledge/reference/glossary.md) · [addresses](knowledge/reference/addresses.md) · [commands](knowledge/reference/commands.md) · [data](knowledge/reference/data.md) |
| [`knowledge/history/`](knowledge/history/) | Provenance & dead ends (`status: historical`): [resolved bugs](knowledge/history/resolved-bugs.md) · [open questions](knowledge/history/open-questions.md) |

The base claims are validated bit-exact against the real game (single-precision arithmetic, the
console cosine table, the x598 pump scramble, FMA-faithful matrix/quaternion math); raw measurement
tables are in [`knowledge/reference/data.md`](knowledge/reference/data.md). The KB is
regression-tested by a bounded weak-agent doc-eval under [`knowledge/_eval/`](knowledge/_eval/).
