# Open questions

> **status: historical/tracking** — the open research register. Each item's *current best answer*
> also lives on its truth page (linked); this page is the running list of what's unresolved.

---

- **Does arrow swimming save time?** RESOLVED (2026-07-02): **no.** Exhaustive offline insertion
  sweep (134 cells: every insertion point × distance 100k–800k × arrow length × schedule shape)
  found zero wins; best case loses +4 frames, worsening monotonically the later/longer you arrow. →
  [mechanics/arrow](../mechanics/arrow.md#does-arrow-swimming-save-time--no-offline-exhaustive).

- **Stroboscopic band exact derivation.** The bands are empirical (emerge from the increment
  formula); the exact decomp source (likely a Nonmatching `J3DFrameCtrl::update` term) and whether
  the bands are sharp or fuzzy are unpinned. → [mechanics/strobo](../mechanics/strobo.md#open--approximate).

- **Multi-pump precision floor — RESOLVED 2026-07-02.** The "~1e-4 per-entry anim oscillation past a
  cos-table boundary (~0.07 v per pump)" was a **double-vs-single-pi bug** in the sim's release cos: the
  console computes `cM_fcos(fVar2·M_PI)` in SINGLE precision (`lfs M_PI; fmuls` → f32 pi, ~1 ULP above
  double pi), which flips the truncated `cM_rad2s` cos-cell at knife-edge anims. Sim used double `math.pi`.
  Fixed with `sim._F32_PI` in `release_ess_speed` (+ the head-bob `af_drag`/`swim_exact`). No planner
  escape-hatch needed. → [mechanics/pumps](../mechanics/pumps.md), and the FP rules in memory
  `superswim-gekko-fp` / `_notes/gekko-fp.md`.

- **Re-enable mid-swim pumps.** Entry anim bit-exact (×598 landing matches clean DTM) and payoff is
  real. With `allow_pump=True` + the speed gate the pumped plans DTM-verify **bit-exact at 50k (280 fr),
  100k (397), 200k (555), 400k (814) AND 300k (705, 39 dips → 300941 live)** — the earlier pump-300k
  desync was the double-vs-single-pi release-cos bug above (RESOLVED 2026-07-02; re-planned & DTM-verified,
  `xfail_live` cleared). Remaining blockers to flipping the `allow_pump=False` default: frontier
  saturation (allow_pump pins the 8000 cap) and confirming no other dest desyncs. →
  [model/planner](../model/planner.md#why-mid-swim-pumps-are-off-by-default).

- **Main-sim displacement omits the head-bob divisor.** `sim.af_drag` (used by `true_disp`, so by
  the planner for distance) computes `0.6·v + 0.4·v·|cM_scos|` but DROPS the console's
  `/(1 + field_0x7C·getSwimTimerRate())` divisor (field_0x7C = 0.35; posMoveFromFootPos,
  d_a_player_main.cpp:2425-2429). So net/distance is a validated approximation, not bit-exact
  (v/anim ARE bit-exact — af_drag never feeds them). The exact form already exists in
  `predict/swim_exact.disp_magnitude` (divisor + f32 pi). Porting it into `af_drag` would make
  net-distance bit-faithful, but needs live net validation + a `cold_plan3k` golden regen. Low
  priority (displacement is not amplified and doesn't affect plan v/anim/air/state verification).
  → memory `superswim-gekko-fp`, `_notes/gekko-fp.md`.

- **Camera: f32 ω precision + auto-flip envelope + negative fine-band symmetry.** We read the s16
  yaw output exactly; the internal ω velocity is f32 (upstream). The auto-camera *flip* trigger
  (speed/hold-length) is uncharacterized — steering must stay in a non-flipping band. →
  [mechanics/camera](../mechanics/camera.md#open).

- **Predictor consolidation.** The 4 `swim_predict*` variants form an evolution chain kept as
  separate modules; merging into one predictor is a known follow-up (each merge re-validated
  bit-exact). → [model/predictors](../model/predictors.md).

- **HIO constant provenance.** Not all `m_HIO->mSwim` magic constants are resolved to decomp names. →
  [reference/constants](../reference/constants.md), [reference/addresses](../reference/addresses.md).
