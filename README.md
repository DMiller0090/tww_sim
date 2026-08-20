# tww_sim — TWW player-physics simulation & route planners

A bit-exact, **offline** simulation and route/input planner for *The Wind Waker* (GZLJ01 / JP)
player physics — both **superswimming** (the swim TAS mechanic) and **land** movement (walking,
rolling, turns). The physics are reproduced from the game's decompilation and validated
frame-by-frame against the real game (single-precision arithmetic, the console cosine table, the
x598 pump scramble, FMA-faithful matrix/quaternion math — see [`KNOWLEDGE.md`](KNOWLEDGE.md)), plus
an optional live-Dolphin validation harness.

On top of the physics sits a **seam-clip solver**: given a room's collision mesh and a static
starting state, it computes the controller inputs that clip Link through a wall seam, entirely
offline, and the plan then reproduces on console bit-for-bit. Eleven seams across four rooms are
shipped and gated this way -- see [`harness/rollstab/README.md`](harness/rollstab/README.md).

The importable `tww_sim` package is **pure Python (standard library only) with no emulator
dependency**, so other projects can depend on it to run simulations. It is split into
`core/` (shared engine), `swim/` (superswimming), and `land/` (land movement); importing one
component never drags in the other.

## Install

```bash
pip install -e .          # from the repo root; makes `tww_sim` importable anywhere
```

## Use as a library

```python
from tww_sim.swim import SwimState, plan_min_frames, expand

# Simulate an action sequence (one action = one game frame).
st = SwimState(v=0.0, anim=0.06392288208007812, air=900)   # a real cold-start anim
for a in expand("chg,60;ess,200;neu,50"):
    st.step(a)
print(st.v, st.anim, st.air, st.state)

# Plan the minimum-frame route to a destination.
res = plan_min_frames(dest=200000, v=0.0, anim=0.06392288208007812, air=900)
print(res["frames"], "frames")

# Land movement (walking / rolling / turns) is a separate, isolated component.
from tww_sim.land import LandState
```

Or from the CLI: `python -m tww_sim.swim.sim seq "ess,200;neu,50"` (prints a SUMMARY line and can
emit an animated HTML viewer with `viz=out.html`).

## Layout

| Path | What |
|------|------|
| **`tww_sim/core/`** | Shared player engine: `fp` (FMA-faithful f32), `mathlib` (console trig/tables), `camera/`, `anim/` (J3D animation runtime), `tables/` (console lookup data). |
| **`tww_sim/swim/`** | The swim library: `sim` (physics), `plan` / `optimize` (route planner), `coldstart`, `actions` (seq helpers), `predict/` (position predictors). |
| **`tww_sim/land/`** | The land library: `land` (walk/roll/turn physics) + `plan_land` (input planner). |
| `tests/` | Offline `pytest` suite: unit tests for the physics helpers + golden/characterization tests freezing bit-exact sim/planner output (`test_*.py`, `golden/`). No Dolphin needed. |
| `tests/dolphin/` | Live sim-vs-Dolphin validators (`run_tests.py`, `run_land_tests.py`, `verify_state.py`, `spotcheck_*`). Need a running Dolphin. |
| **`harness/rollstab/`** | The seam-clip solver: mint an anchor, solve for a clipping cut, author a DTM, verify the clip live. Offline apart from the optional per-anchor verification gate. |
| `harness/collision/` | DZB stage-collision reader, seam locator and room-wide clip screens. |
| `harness/` | The rest of the live-Dolphin tooling — `capture/` (read game state), `validate/` (sim-vs-live), `dtm/` (movie authoring/playback), `search/` (live-grounded planning), `anim/` (J3D probes). Depends on `../tools/dolphin_mem`. |
| `viz/` | HTML/JSON trajectory artifact builders (offline). |
| `fixtures/` | Code-referenced baseline action sequences. |
| `knowledge/` | The knowledge base (mechanics, strategy, sim/planner model, reference tables, JP addresses). |
| `archive/` | One-off probes, calibrations, and traces kept for provenance (not part of the supported surface). |

## Docs

- **Source of truth: the knowledge base** under [`knowledge/`](knowledge/) — start at the
  question-indexed hub [`knowledge/README.md`](knowledge/README.md). Organized by layer:
  `mechanics/` (game truth), `strategy/` (TAS heuristics), `model/` (sim/planner + engine/FP),
  `reference/` ([constants](knowledge/reference/constants.md),
  [glossary](knowledge/reference/glossary.md), [addresses](knowledge/reference/addresses.md),
  [commands](knowledge/reference/commands.md), [data](knowledge/reference/data.md)), `history/`
  (provenance). The root [`KNOWLEDGE.md`](KNOWLEDGE.md) is a thin pointer to the hub.

## Testing

Two layers, run both before/after any sim change:

```bash
pip install -e ".[test]"
pytest                              # offline: unit + golden suite (no Dolphin), runs anywhere/CI
python tests/dolphin/run_tests.py   # live: sim-vs-Dolphin accuracy (needs Dolphin, see below)
```

- **Offline (`pytest`)** — unit tests for the physics helpers plus golden/characterization tests
  that freeze the current bit-exact sim/planner output. This is the fast logic-regression gate.
  After a deliberate, live-verified behavior change, refresh the goldens with
  `python -m tests.golden_regen`.
- **Live (`tests/dolphin/`)** — replays baselines on a running Dolphin and compares to the sim,
  confirming the model still matches the real game. See [`tests/dolphin/README.md`](tests/dolphin/README.md):
  it needs Dolphin + `twwgz.iso` and a cold-start slate you supply (`TWWGZ_SLATE=...` or `slot=N`) —
  the slate is a dump of copyrighted game RAM and is **not** shipped here.

## Standalone vs. workspace

The **offline `tww_sim` package and `pytest` suite work standalone** — `pip install -e .` and go.
The **live tooling** (`harness/`, `tests/dolphin/`) additionally needs `dolphin_mem` from the sibling
`../tools/` workspace (reached via a path bootstrap; absent in a standalone clone) and a running
Dolphin. Read [`../tools/DOLPHIN_CONTROL.md`](../tools/DOLPHIN_CONTROL.md) before using it.

## Status / follow-ups

- The `swim_*` predictor variants in `tww_sim/swim/predict/` form an evolution chain and are kept
  as separate modules; consolidating them into one predictor is a known follow-up (each merge
  step must be re-validated bit-exact).
- The land layer is bit-exact: the foot-FK ULP frontier that used to leave `tests/test_land.py`
  partly red is closed, and so is the late-FRONT_ROLL drawn-pose gap (it was the quaternion sign
  extension plus a `FrameCtrl` frame kept in double, not an unmodelled body lean).
- Three seams have REST-bit-exact anchors and verified-genuine dust but no delivered clip yet
  (`seam97`, `seam97m`, `hseam2709`). All three are the same situation -- the dust is thin enough
  that the per-draw hit expectation sits just under 1 inside the search budget -- not a model gap.
- A one-off Courtyard Tetra-push route planner that this repo carried for ~170 sessions lives on
  branch `dmiller/courtyard-tetra-push`, forked at `c516cc3`. It is parked, not abandoned; nothing
  on `main` depends on it.
- `bug#2` (dense-pump live divergence) is resolved as a pipe input-delivery artifact — DTM movie
  playback is the faithful delivery path, not the `advanceseq` pipe (see `KNOWLEDGE.md`).
