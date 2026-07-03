# Glossary

**Answers:** What does <term> mean? (csangle, ESS, head-bob, af_drag, x598, strobo, reboost,
pump, slate, …)
**Status:** reference.
**Source:** terms defined from the mechanics pages; follow the links for detail.

One-line definitions. Each links to the page that explains it fully.

| Term | Definition |
|------|-----------|
| **Superswim** | A swimming state (set up via Storage + camera lock with the Wind Waker) where alternating the control stick fully back-and-forth each frame builds speed. |
| **Potential speed** (`mNormalSpeed`, `velocity`) | The underlying speed value. Charging adds to it; ESS/neutral decay it. Negative-signed by convention. |
| **True speed / true displacement** | How far Link actually moves this frame = potential speed scaled by [head-bob](#af_drag) and air drag. |
| **Charge** | Full alternating deflection: **+3** potential speed/frame (on-axis). See [constants](constants.md#speed-deltas). |
| **ESS** (Extra Slow Swim) | Holding the **minimum** non-neutral stick deflection (e.g. `(128,110)`). Decays potential speed only **−1/6** but pays head-bob + air drag on true speed. See [glossary: head-bob](#af_drag). |
| **Neutral** | Stick at `(128,128)`, inside the dead zone. Decays **−2/frame** but is **drag-free** (true speed = potential speed). A separate code path, not a point on the ESS decay curve. |
| **`mStickDistance`** | Normalized stick deflection `clamp((|raw−128|−15)/54, 0, 1)`; the magnitude that scales the per-frame speed gain. |
| **Animation frame / anim** | Position in the swim stroke cycle (`0..23` ESS, `0..26` neutral). Drives the head-bob. |
| <a id="af_drag"></a>**Head-bob drag** (`af_drag`) | Link's head bobs with the anim cycle, modulating true speed. Numerator `0.6v + 0.4v·|cM_scos(π·anim/23)|`, then **divided by `1 + 0.35·getSwimTimerRate(air)`** for full true speed (don't drop the denominator). `cM_scos` is the [console cosine](#cm_scos) ≈ `cos`. Near anim 0/23 → ~100% kept; near 11.5 → ~60%. Full formula + constants: [constants](constants.md#head-bob-animation-frame-drag--true-speed). |
| <a id="cm_scos"></a>**`cM_scos`** | The **console** cosine: a 4096-entry s16 lookup with the low 4 bits truncated, *not* `math.cos`. Tiny error, amplified by [x598](#x598) and high-speed exits → must be matched for bit-exactness. |
| **Instant turnaround / charge snap** | When charging, Link's facing flips 180° in one frame if the stick points within **45°** of straight-back. See [turnaround](../mechanics/turnaround.md). |
| **Arrow swimming** | Charging while tilted toward the target so Link drifts toward it ("tip of an arrow") at a reduced charge rate. See [arrow](../mechanics/arrow.md). |
| **Tilt α** | Arrow move-direction offset from the pure-back axis. `charge_rate = −3·cos(2α)`; cross-drift `= disp·sin α`. Usable α ∈ [0°, ~20°]. |
| **Stroboscopic band** | A speed (≈ −794, ≈ −1630) where the anim increment ≈ 23·k, so the anim barely advances (aliases) and head-bob efficiency stays roughly stable. See [strobo](../mechanics/strobo.md). |
| **Reboost** | A short up/down charge in a strobo band to bump speed and re-aim the slow anim drift back toward the head-bob peak. Phase-triggered, not on a timer. See [strategy/reboost](../strategy/reboost.md). |
| **Pump (ESS pump)** | A short ESS burst out of neutral on a favorable anim frame to preserve speed cheaply. Pays a 1-frame entry tax (first frame is still neutral). Low-speed tech. |
| <a id="x598"></a>**x598 scramble** | The neutral→ESS transition multiplies the anim by `End_wait·End_swim = 26·23 = 598`, scrambling the ESS-start phase. Deterministic but hypersensitive — see [model](../model/) (planner) and [history](../history/). |
| **`release_ess_speed`** | The speed carried into neutral on ESS→neutral exit = `af_drag` at the release anim. Exit near anim 0/23 keeps ~100%; near 11.5 keeps ~60%. |
| **csangle** | The camera yaw. The stick is camera-relative: `world_angle = stick_angle + csangle + 0x8000`. A fine lateral-steering lever. |
| **Slate** | A savestate dump of game RAM used as a known starting point for live tests (e.g. "slot 10", a flat-water cold-start). Not shipped (copyrighted RAM). |
| **Anchor** | A test-owned savestate `<test>@<isokey>.sav` under `tests/dolphin/anchors/`. |
| **DTM** | A Dolphin movie file; the faithful input-delivery path for live validation (vs the `advanceseq` pipe — see bug#2). |
| **Bug#2** | The dense-pump live divergence — resolved as a pipe input-delivery artifact, not physics. DTM playback is faithful. |
| **Cold start** | A swim begun from `v = 0` (vs seeded at cruise speed). |
| **Quadrant grid** | The Great Sea = a **7×7 grid of 49 quadrants**, one island each. Routes are planned quadrant-to-quadrant. See [ocean-environment](../mechanics/ocean-environment.md). |
| **Air refill** | Resetting air to [900](constants.md#air) by skimming a loaded island's land/water boundary while still swimming (**touching land 1 frame loses ALL speed**). See [air-refill](../mechanics/air-refill.md). |
| **Sploosh zone** | A sparse flat-ocean quadrant where the **ocean surface collision loads too slowly** — entering too fast drops Link to the sea floor ("sploosh"). Must be approached under a max-speed cap or routed around. See [ocean-environment](../mechanics/ocean-environment.md#sploosh-zones-ocean-collision-load-failure). |
| **Collision streaming** | Only **one island's collision is loaded at a time** (load timing unpredictable) — why mid-swim refills are rare. See [ocean-environment](../mechanics/ocean-environment.md). |
