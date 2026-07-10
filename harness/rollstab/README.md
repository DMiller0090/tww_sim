# harness/rollstab - the roll-stab seam-clip solver (kaze r11 sandbox)

Plan a roll-stab (FRONT_ROLL -> single-B-edge CUT_F) that clips through the 110-degree seam at
kaze room 11 S=(9069.9043, 259.1986), and deliver it as a clean DTM. Everything here runs the
BIT-EXACT-vs-live pipeline built in sessions 7-9 (2026-07-09/10); the narrative history lives in
`_notes/seam-clip-live-validation-handoff-2026-07-10-session8.md` and the follow-up handoffs.

## The problem shape (read this before touching knobs)

- The acceptance set is f32 DUST, not a window: `genuine_clip` (CrrPos not blocked + old in
  front of both wall planes + new behind) flickers at ULP scale along the roll ray. Slivers are
  0.0005-0.01u wide in the perp/x direction, ~10-30% dense over a 0.5-3u along-band, and are
  STRIPED per f32 x-column (adjacent columns' slivers do not overlap in z). Never target a
  fitted ribbon; always test the exact candidate (`geometry.pred_genuine` == the real cut,
  verified bit-identical to the sim's `new`).
- The roll only carries the full 49.2202 lunge from a capped walk: speedF MUST be 17.0 at the A
  press (gated everywhere).
- old_z must sit in ~[302.6, 308.2]: below, the roll is wall-blocked short; above, the lunge
  cannot reach behind the planes.

## The pipeline

1. **Anchor**: a savestate resting in the sim-characterized idle (state 4/5, `waits`/FREEB
   class, sword drawn) + a `.seed.json` snapshot next to it. `mint.py` makes translated anchors
   (PAUSE FIRST, then load: letting the game run between load and save advances the idle/fidget
   anim and silently desyncs the anchor from its seed -- that bug cost a whole anchor chain).
2. **Calibrate** (`calibrate.py`, 1 live DTM run): fixed constant-stick prefix; overwrite the sim
   at row K0 with the live position, the under-body anim phases, m359C/m35B4, and a re-posed toe
   stream. After this the sim is bit-exact vs live through cruise, arcs, partial-magnitude dips,
   and the roll (verify: `python -m harness.rollstab.calibrate anchor=...` prints the per-frame
   diff; the dip diagnostic is the stronger gate -- see Verification below).
3. **Solve** (`solver.py`, offline): knobs = bearing ARCS (gross lateral shift, drho -3..+3),
   1-frame partial-magnitude FINES (anim-phase roll-drift classes + speed dips), A_proj (17u z
   grid). Exact acceptance per run. `search(anchor, do_drill=True)` runs catalog + ranked +
   iterative-deepening drill; hits -> `_generated/rollstab_hits.json`.
4. **Gate + deliver** (`deliver.py`): 0-ULP literal-stream replay gate (+ a +-2e-4 sliver
   z-margin check; shifted-anchor generations can land ~1e-4 off), then the clean DTM with a
   120-frame watch-tail, per-frame live confirmation. NEVER advancewith.

## Verification protocol (per NEW anchor, before trusting hits)

1. `calibrate` must print CALIBRATED BIT-EXACT (cruise).
2. Run a dip diagnostic (a partial-magnitude frame + A + roll) live and diff per frame -- the
   cruise is insensitive to the blend state (m3598=0), so ONLY the dip exercises the calibrated
   anim state. On the reference idle2 anchor this is 0-diff; on translated anchors expect <=
   ~1e-4 z residual (thin-sliver risk; the deliver gate's margin check covers it).

## Status (2026-07-10)

> SINGLE SOURCE OF TRUTH for current seam-clip state. A pre-commit gate blocks any commit
> that changes `harness/rollstab/*.py` without touching this file, so keep it current.
> The session prompt (`SESSION_PROMPT.md`) points here for state rather than restating it.


- Sim inaccuracies RESOLVED: sword-drawn DASHS (commit 0901d21) + WALKS (this package's commit)
  + the calibration's anim-phase/m359C/toe-stream seeding. Verified bit-exact live through every
  plan element on the idle2/idle12 anchors.
- In-sim genuine+clear hits are found routinely (drill, ~1-10 min offline per anchor
  calibration). The remaining gap to a LIVE clip is landing a hit whose sliver tolerates the
  ~1e-4 translated-anchor residual, or solving directly on a 0-diff-verified anchor.
- Dead ends (do not repeat): two-seg pursuit walks (rho treads quantize with a dead band over
  the window), ribbon-fit |g| minimization (the razor is dust), per-move-set live bias
  correction (arc-dependent), roll-as-anim-reset canonicalization (diverges from frame 1),
  anchor-z transfer aiming (the live m359C reseeding flips the press frame; z lands chaotically).

Related: `knowledge/strategy/seam-clip-solver.md` (methodology page),
[[rollstab-clip-solver-mvp]] memory, `tests/dolphin/spotcheck_rollstab.py` (cut 0-ULP),
`tests/dolphin/spotcheck_swordwalk.py` (DASHS toe).
