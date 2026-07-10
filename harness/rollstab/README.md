# harness/rollstab - the roll-stab seam-clip solver (kaze r11 sandbox)

Plan a roll-stab (FRONT_ROLL -> single-B-edge CUT_F) that clips through the 110-degree seam at
kaze room 11 S=(9069.9043, 259.1986), and deliver it as a clean DTM. Standing instructions:
`SESSION_PROMPT.md`; current state: `## Status` below; narrative history:
`_notes/seam-clip-live-validation-handoff-*.md` (sessions 7-10).

## The problem shape (read this before touching knobs)

- The acceptance set is f32 DUST, not a window: `genuine_clip` (CrrPos not blocked + old in
  front of both wall planes + new behind) flickers at ULP scale along the roll ray. Slivers are
  0.0005-0.01u wide in the perp/x direction, ~10-30% dense over a 0.5-3u along-band, and are
  STRIPED per f32 x-column. Never target a fitted ribbon; always test the exact candidate
  (`geometry.pred_genuine` == the real cut, verified bit-identical to the sim's `new`).
- The roll only carries the full 49.2202 lunge from a capped walk: speedF MUST be 17.0 at the A
  press (gated everywhere).
- old_z must sit in ~[302.6, 308.2]: below, the roll is wall-blocked short; above, the lunge
  cannot reach behind the planes.

## The model: bit-exact FROM REST -- pure sim, no calibration

`rest.rest_state(anchor)` seeds a sim that matches live 0-ULP from row 0 through walk entry,
cruise, bearing arcs, partial-magnitude dips, and the roll, taking ONLY the anchor's seed json
as input (the objective's no-calibration requirement; the old K0 live-calibration crutch is
deleted). The terms that made it exact (each decomp-grounded, found by per-frame live diffing):

1. **The WAIT(4) rest blend** (`foot_speedf.seed_rest_blend`): the anchor rests in
   setMoveAnime(WAITS, WALK, r29=2) with BOTH frame ctrls live; procWait RE-INITS the blend every
   idle frame (`setBlendMoveAnime(-1.0f)` -> the f31 frame ROUND-TRIP `frame/60*60`, not an f32
   identity, and fc1 re-derived `f31*32`). Seeded from the seed json's `rest_*` fields plus the
   STORED delayed foot poses (mFootData 018/00C) -- those carry the pre-mint position's rounding
   noise, which re-posing at a translated position cannot reproduce (this was session 9's
   mysterious ~1e-4 translated-anchor residual).
2. **2 alignment no-ops** (`REST_NOOPS`): a savestate-anchored run_dtm movie's first two rows
   exist only for row alignment -- the game has not run yet (live d_frame holds the rest value
   through them).
3. **The draw happens at frame END** (deferred-draw mode): setWorldMatrix builds the pose base at
   the POST-integration position (d_a_player_main.cpp:11551), not the pre-step one the sim used
   to pose at. Invisible at cruise (m3598=0 hides the toe stream) and at small coords (the
   flat-arena suite), fatal on dip frames at kaze magnitudes.
4. **Link's world Y is in the base** (y=-6534 here): the m37B4 inverse's cancellation rounding is
   magnitude-dependent in every axis.
5. **The MOVE turn lean** (`LandState._set_move_slant_angle`, setMoveSlantAngle 9499):
   shape_angle.z = m351C>>1 tilts the base via ZXYrotM's z concat; m351C chases
   1.6*(m34DE - shape.y)*speed-factor while walking near cap, decays 35%/frame otherwise. The
   draw uses the PREVIOUS frame's lean (setWorldMatrix runs before setMoveSlantAngle).
6. **dtm_make's stick calibration** (`rest.dtm_stick`): every authored DTM delivers 255 as 254
   and 0 as 1, so plans are built FROM the delivered bytes. The un-calibrated (73,255) arc stick
   decoded 60 treads off and cost a 0.3u live miss -- the stick DECODE itself (PADClamp octagon +
   JUT CStick) matches the decomp exactly.

## The pipeline

1. **Mint** (`mint.py`): PAUSE FIRST, load the base anchor, auto-capture the `rest_*` seed fields
   (frame ctrls, m359C/m35B4, stored foot poses t2 + t1-via-one-paused-advance), re-load, write
   link_x/z += delta, save. Letting the game run between load and save desyncs the anchor (cost
   the idle4..idle11 chain).
2. **Verify** (`rest.py` CLI, 1 live DTM run per NEW anchor -- verification only, never in the
   solve loop): play the verification stream, log the anim fields per frame, then the offline
   from-rest diff. Must print **REST BIT-EXACT** (pos + d/w frame ctrls + m359C, every row)
   before the anchor's hits are trusted.
3. **Solve** (`solver.py`, offline): knobs = bearing ARCS (gross lateral shift), 1-frame
   partial-magnitude FINES, A_proj (17u z grid), and the **START CRAWL** -- the 1D-approach
   micro-moves: K<=3 partial-magnitude sticks (msd 0.52..0.889, aimed at F) in the first rows
   while speed is LOW, each shifting the downstream trajectory along-track by a fine quantum.
   Exact acceptance per run. `search(anchor, do_drill=True)` runs catalog + start-crawl sweep +
   iterative-deepening drill; hits -> `_generated/rollstab_hits.json`.
4. **Gate + deliver** (`deliver.py`): 0-ULP literal-stream from-rest replay gate (+ a +-2e-4
   sliver z-margin robustness check), then the clean DTM with a 120-frame watch-tail, per-frame
   live confirmation. NEVER advancewith.

## Status (2026-07-10)

> SINGLE SOURCE OF TRUTH for current seam-clip state. A pre-commit gate blocks any commit
> that changes `harness/rollstab/*.py` without touching this file, so keep it current.
> The session prompt (`SESSION_PROMPT.md`) points here for state rather than restating it.

- **North star: the TETRA seam clip, pure-sim** -- the phased plan (wall collision -> ground ->
  CC Link<->Tetra -> the Tetra clip) lives in `ROADMAP.md`. Open phase: **W (wall collision in
  the stepper, 0-ULP live-gated)**.
- **Phase 0 / kaze OBJECTIVE MET (session 10): LIVE CLIP CONFIRMED, 0-ULP.** A solver hit planned entirely
  offline from the idle13 anchor's rest state shipped as a clean DTM and clipped through the
  seam live: the cut fired on the predicted frame at the bit-identical position
  (`d(old) = (0.000000, 0.000000)`, old=(9071.9804688,303.1956787),
  new=(9069.6601562,254.0301819)).
- **PURE SIM / NO CALIBRATION: satisfied.** The K0 live-calibration crutch is DELETED
  (`base_state`/`apply_calibration`/`calibrated_state` are gone); `rest.rest_state` models the
  from-rest idle->walk entry from the anchor seed alone (model terms above). The only remaining
  live run is the OPTIONAL per-new-anchor verification gate (`rest.py` CLI) -- outside the loop.
- Search cost: singles + start-crawl sweep ~15s; full drill found 4 hits in ~4 min on idle13
  (first hits well inside the 2-minute budget; the drill tail is depth-2 combos).
- Regression: `tests/test_rollstab_rest.py` + live goldens
  `tests/golden/rollstab_rest_{cruise,ship}.json` (2 green, 1 strict-xfail).
- **Known open gap (flagged RED)**: late FRONT_ROLL drawn poses drift 1-122 ULP vs live (ship
  trace rows 32-36; sub-1e-5 on near-zero coords). NO effect on any current plan element --
  m3598 is frozen during the roll, positions/facing/cut stay 0-ULP -- but a post-roll WALK
  resuming on blend frames would consume the stale toe stream. Prime suspect: the
  daPy_lk_c::jointBeforeCB body-lean on the MOMI/thigh joints (m3516/m3518/m351A quat concat --
  in the foot FK chain, currently unmodeled; listed as future work in SESSION_PROMPT.md), then
  m35C4 / foot-lift m35B8 / recovery shape angle. Decomp-first: jointBeforeCB + procFrontRoll +
  setFootPos (8780) + setWorldMatrix (9554).
- idle2/idle12 seed jsons predate the `rest_*` schema -- run `mint.capture_rest` (or re-mint)
  before solving off them.
- Dead ends (do not repeat; full ledger
  [knowledge/history/seam-clip-dead-ends.md](../../knowledge/history/seam-clip-dead-ends.md)):
  two-seg pursuit walks, ribbon-fit |g| minimization, per-move-set live bias correction,
  roll-as-anim-reset canonicalization, anchor-z transfer aiming, and K0 mid-run calibration
  (patched only the state the cruise could see; m3598=0 hid the rest).

Related: `knowledge/strategy/seam-clip-solver.md` (methodology page),
[[rollstab-clip-solver-mvp]] memory, `tests/dolphin/spotcheck_rollstab.py` (cut 0-ULP),
`tests/dolphin/spotcheck_swordwalk.py` (DASHS toe).
