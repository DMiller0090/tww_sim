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

- **Re-enable mid-swim pumps.** Still disabled (`allow_pump=False`), but NOT because the entry anim is
  mispredicted (the sim's ×598 landing is bit-exact vs clean DTM, 11-pump build matched live 2026-07-02)
  and NOT for lack of payoff — with `allow_pump=True` + the speed gate the planner's pumped plans
  DTM-verify **bit-exact at 50k (280 fr), 100k (397), 200k (555, 26–37 dips) and 400k (814)**. BUT they
  are **not universally live-faithful: pump-300k desyncs** — the 705-frame/47-dip plan reaches only
  ~282852 live (17k short, live v=−524 vs sim −804), reproducible (2026-07-02, caught by the DTM-verified
  planner benchmark). Suspected: one dip lands on an anim phase the ×598 model mis-predicts (301k has the
  most dips). Tracked as `xfail_live` in `tests/benchmark/cases.py`; the verified 300k optimum is the
  no-pump 711. Remaining blockers to flipping the default: this desync, frontier saturation (allow_pump
  pins 8000), the multi-pump precision floor above. →
  [model/planner](../model/planner.md#why-mid-swim-pumps-are-off-by-default).

- **Camera: f32 ω precision + auto-flip envelope + negative fine-band symmetry.** We read the s16
  yaw output exactly; the internal ω velocity is f32 (upstream). The auto-camera *flip* trigger
  (speed/hold-length) is uncharacterized — steering must stay in a non-flipping band. →
  [mechanics/camera](../mechanics/camera.md#open).

- **Predictor consolidation.** The 4 `swim_predict*` variants form an evolution chain kept as
  separate modules; merging into one predictor is a known follow-up (each merge re-validated
  bit-exact). → [model/predictors](../model/predictors.md).

- **HIO constant provenance.** Not all `m_HIO->mSwim` magic constants are resolved to decomp names. →
  [reference/constants](../reference/constants.md), [reference/addresses](../reference/addresses.md).
