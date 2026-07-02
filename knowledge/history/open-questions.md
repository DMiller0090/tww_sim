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

- **Multi-pump precision floor.** Single/double pumps are bit-exact; beyond ~1.5 pump cycles the
  ×598 scramble amplifies a ~1e-4 per-entry anim oscillation past a cos-table boundary (~0.07 v per
  pump). Escape hatch: a per-entry anim ∈ [0,23] search dimension in the planner. →
  [mechanics/pumps](../mechanics/pumps.md), [model/planner](../model/planner.md).

- **Re-enable mid-swim pumps.** Currently disabled (`allow_pump=False`) because the pump ess_start
  anim is mispredicted. Re-enable only after validating the entry-anim phase live per entry-frame.

- **Camera: f32 ω precision + auto-flip envelope + negative fine-band symmetry.** We read the s16
  yaw output exactly; the internal ω velocity is f32 (upstream). The auto-camera *flip* trigger
  (speed/hold-length) is uncharacterized — steering must stay in a non-flipping band. →
  [mechanics/camera](../mechanics/camera.md#open).

- **Predictor consolidation.** The 4 `swim_predict*` variants form an evolution chain kept as
  separate modules; merging into one predictor is a known follow-up (each merge re-validated
  bit-exact). → [model/predictors](../model/predictors.md).

- **HIO constant provenance.** Not all `m_HIO->mSwim` magic constants are resolved to decomp names. →
  [reference/constants](../reference/constants.md), [reference/addresses](../reference/addresses.md).
