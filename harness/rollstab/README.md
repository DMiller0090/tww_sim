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

**The Tetra push-aside clip has its own shipped pipeline: `pushaside.py`** (`mint` / `deliver` / `diff`
/ `search`). Read its docstring before ANY Tetra-clip delivery work -- it encodes the four delivery
truths (walkable Tetra floor; NEUTRAL roll stick; B one step later in the DTM than in the sim; seed the
sim at the DTM's REAL roll entry) which are NOT re-derivable from the sim alone and which each cost a
live run in session 22. When live disagrees with the sim, run `pushaside diff` (per-frame, BOTH actors)
-- never guess inputs.

## Status (2026-07-12, session 24)

> SINGLE SOURCE OF TRUTH for current seam-clip state. A pre-commit gate blocks any commit
> that changes `harness/rollstab/*.py` without touching this file, so keep it current.
> The session prompt (`SESSION_PROMPT.md`) points here for state rather than restating it.

- **KILL-THE-GLITCHED-TETRA DONE (session 24): the FOLLOW-ENABLED turnaround-roll seam clip is LIVE,
  BIT-EXACT, with a NORMAL following Tetra.** The whole `turnaround.py` live pipeline is wired
  (`entry`/`solve`/`deliver`/`diff`) and delivered the clip on slot 7. LIVE: DOWN-walk + A+diagonal
  turnaround roll plows the type-5 Tetra aside; her CC push steers the roll-stab `CUT_F` lunge through
  the seam; the cut fires at `old=(-1692.314697265625, -955.0416870117188)` and lands at
  **`new=(-1727.1728515625, -990.4632568359375)` -- BIT-FOR-BIT the sim's prediction** -- then Link
  drops to proc 39 (falling), THROUGH the seam. **Every frame entry->cut is 0-ULP for BOTH actors**
  (the plow AND the push-steered lunge). Delivered by a clean DTM (never advancewith). This retires
  the session-22 GLITCH dependency: same corner, same target `new`, but a normal following Tetra.
  - **Winning setup (slot 7):** Link MOVED +110u NE along his facing to start
    (-1531.94677734375, -787.6950073242188) -- Dereck OK'd moving Link; the as-is start's roll entry
    lands ~110u short (wall-pinned). Tetra placed at **(-1645.696044921875, -919.3839721679688)**
    (walkable, bit-confirmed genuine). Stream: DOWN x6 -> A+diagonal (108,204) turnaround -> NEUTRAL
    roll -> UP+B at roll-index **b_step=16**. Measured live roll entry
    (-1516.116455078125, -765.1473999023438) facing 40835 m351C 0 speedF 26.
  - **Two delivery calibrations this cost** (on top of the four pushaside truths, which all carried over):
    1. **The from-rest walk is NOT yet bit-exact** -- the live roll entry is ~2.6u from the sim's
       from-rest entry, and the genuine Tetra region is f32-DUST sensitive to the entry, so the
       placement is solved AT the MEASURED live entry (pushaside truth #4, generalized). facing (40835)
       and speedF (26) ARE exact -- only the walk DISTANCE differs.
    2. **`b_step=16`, not the sim thrust+1=15** (pushaside was +1). At 15 the CUT fires ONE FRAME
       EARLY -> no lunge -> proc 90 recoil; at 16 it fires on the sim-step-16 frame and lunges through.
       The turnaround PRESS consumes an input, shifting the buffer by one vs the pushaside walk.
  - **Method that cracked it (do not guess inputs):** `turnaround.diff` per-frame BOTH-actor DTM-vs-sim
    diff showed the roll bit-exact (k0-k14 dLink=dTetra=0.00000) with the cut one frame early -> the
    b_step fix was named by the divergence frame, not guessed. The genuine region was LOCATED cheaply
    via the engine's unclamped-endpoint plane distances (`sweep_par` out[8]/[9] = behindA/behindB, a
    smooth ridge) instead of a blind fine-scan of the whole corridor.
  - Fixture `fixtures/hyrule_turnaround_clip_live.json`; gate `tests/test_turnaround_clip.py` (6 green,
    offline). Open (pure-sim polish, not the clip): model the from-rest slot-7 walk so the roll entry
    is computed, not measured (then it is a true one-shot; today `entry` measures it via one DTM run).

- **KILL-THE-GLITCHED-TETRA (session 23): the FOLLOW-ENABLED turnaround-roll clip is VIABLE in the
  sim; the solver is built (`turnaround.py`); live delivery was the open next step (DONE session 24,
  above).** The session-22 clip needed a GLITCHED no-follow Tetra; this is the successor with a NORMAL
  following Tetra. Dereck's **slot 7**: type-5 following-enabled Tetra idle in the corner, Link behind
  her facing away, sword OUT.
  The mechanic (all sim-validated): hold **DOWN** ~6 frames (speedF caps at 17 by ~frame 5; Tetra stays
  in her 130/230 follow band so she never engages) -> one frame **A + a DIAGONAL stick** = the
  turnaround roll ([[turnaround-roll-tech]]) entering FRONT_ROLL at nspeed 26 (full ~49u lunge; the roll
  SPEED comes from the walk cap, NOT the stick magnitude, so the entry stick is free to AIM) -> NEUTRAL
  roll -> **UP+B** CUT_F.
  - **PROVEN feasibility:** at a turnaround entry, facing in the seam-gap window (~40842, 224.35 deg)
    yields ~14-35 genuine Tetra placements landing EXACTLY on the shipped target `new=(-1727.173,
    -990.464)`. The lunge must aim THROUGH the fixed corner gap: outside the window `new` stays
    wall-pinned ~49u short and NO push helps. The octagon stick VERTEX only reaches 40758/40913 (miss);
    a **DIAGONAL stick (108,204) -> 40835** (or (108,203) -> 40849) hits the window under the slot-7
    camera (csangle 39981), NO camera change. The walk is ~6 frames, follow-safe (peak ~224u < 230),
    no initial Co overlap. Solver machinery gated: `turnaround.extract_schedule_at` is BIT-EXACT vs
    `fast_shove.extract_schedule` at the fixture entry/facing.
  - **Delivery = the session-22 recipe** (`pushaside.py` truths; [[tetra-clip-solved-live]] #4): the
    genuine Tetra spot is f32-DUST sensitive to the roll ENTRY (a ~0.2u entry shift relocates the whole
    genuine region out of a 20u box) and the from-rest walk is not yet bit-exact, so **seed the
    placement search at the DTM's MEASURED real roll entry**, fine-scan Tetra there, place her, deliver +
    per-frame diff (never guess inputs). `turnaround.py` has the offline solver (`search`) + stick
    builder (`build_sticks`) ready; the live plumbing (`entry`/`deliver`/`diff`, reusing `pushaside.play`
    with SLOT=7 sharing Tetra base 0x80ACD20C) is the next increment. See the session-23 handoff.
  - Ruled out this session: the octagon-VERTEX turnaround aim (40758/40913) never threads (wall-pinned
    49u short) -- the diagonal-stick aim is REQUIRED; a coarse (integer n_walk / discrete stick / integer
    thrust) sweep finds 0 genuine (the acceptance is f32 dust -- fine Tetra-placement is the only knob).

- **PHASE T / NORTH STAR ACHIEVED (session 22): the TETRA PUSH-ASIDE SEAM CLIP IS LIVE, BIT-EXACT.**
  Tetra stands at her spot from the START (`placed_step=0` -- an initial setup var, **no mid-run
  write**); Link's roll PLOWS her aside; her CC push steers the roll-stab `CUT_F` lunge through the
  seam at the (-1727,-990) corner. Delivered by a **clean DTM** (never advancewith). LIVE:
  the cut fires at `old=(-1692.314697265625, -955.0418090820312)` and lands at
  **`new=(-1727.173095703125, -990.4635009765625)` -- BIT-FOR-BIT the sim's prediction** -- then Link
  drops to proc 39 (falling), i.e. he is THROUGH the seam behind the corner. Winning setup: Tetra
  start **(-1652.2239990234375, -939.447998046875)**, roll entry (-1513.3475341796875,
  -763.5128784179688), thrust at sim-step 15, cut at step 16. Fixture
  `fixtures/hyrule_pushaside_clip_live.json`; gate `tests/test_pushaside_clip.py` (6 green, offline).
  This retires dead-end #19: the push-aside was always viable, the earlier "empty" was SCOPE.
  - **Four delivery truths this cost, all now permanent (do not relearn them):**
    1. **Tetra's START must be on WALKABLE floor** (`in_front` of BOTH seam walls). The sim clamps her
       to flat ground everywhere and NEVER models her falling, so it happily "stands" her behind a
       wall; live she falls OOB and there is **no push at all** (this is exactly how the first live
       attempt failed: her spot had `fB = -6.8`). The search now hard-constrains this.
    2. **The roll phase must hold a NEUTRAL stick, not UP.** A pushed stick (`msd > 0.05`) force-exits
       `FRONT_ROLL` the instant `roll_frame > ROLL_EARLY` (`land/procs/roll.py:60`), so the CUT can
       never fire OUT of the roll -- the B degrades to a plain MOVE-slash (proc 90 recoil, no lunge).
       The sim's own schedule (`fast_shove.make_inputs`) is NEUTRAL + one UP+B; **the DTM must deliver
       THAT**, not the capture fixture's UP-held sticks.
    3. **The B goes one step LATER in the DTM than in the sim**: the sim buffers B with a 2-step
       INPUT_DELAY (B at step 14 -> CUT at step 16), the DTM delivers it with 1 (B at sim-step 15).
    4. **Seed the sim at the DTM's ACTUAL roll entry**, not the capture fixture's. The DTM's
       calibrated walk (`dtm_make` 255->254) enters the roll ~0.004u away from the advancewith
       capture; on f32 dust that is block-vs-clip. Seeded at the real entry the engine is **0-ULP vs
       live on every frame for BOTH actors, including the cut**.
  - Open (the remaining pure-sim gap): the walk-up is still the CAPTURED slot-6 walk, so the roll
    entry is taken from a live trace rather than modelled. Closing it = a from-rest slot-6 anchor
    (cf. kaze's `rest.rest_state`) simulated on the DELIVERED bytes (254, not 255). The clip itself
    needs no live round-trip once the entry is known.

- **Phase T (session 21b, Dereck's correction): the ACCEPTED mechanism is the PUSH-ASIDE -- Tetra
  stands in place from the start (an initial setup var) and Link's roll PLOWS her aside into the
  clip-delivering position. NO mid-run writes.** The session-21 live "clip" below placed Tetra by
  teleport ON the last pre-cut frame -- that is a mid-run hack, so it is a VALIDATION artifact (it
  live-proves the engine, the graze-push physics, and the acceptance 0-ULP end-to-end), NOT the
  solve. The push-aside is NOT impossible: manual testing produced a **50.6u displacement** even
  with a bad angle/position (the clip needs ~49.99), so the earlier "plow-mediated staging never
  clips" result only means the SEARCHED SLICE was too thin -- one Link approach line, one entry
  point, 3 thrust steps. The search must widen: **roll timing (= Link's roll-entry point along the
  approach line -- the biggest knob, now a per-run engine param `link_x0/z0`, gated 15/15 vs the
  Python engine), Link lateral placement, a much wider/finer Tetra initial-position space, thrust
  timing, and roll angle (a schedule re-extract with a facing override)**. Tetra-from-the-start =
  `placed_step=0` (an initial condition, not a hack). See the session-21 handoff for the search plan.
- **Phase T (session 21): the fast exact engine + a teleport-staged live validation.**
  The two session-20 blockers fell in one session:
  1. **The fast coupled sim (>=100k sims/sec, EXACT -- not a predictor).** `tww_sim/core/_shovec.pyx`
     (build: `python _build_native.py _shovec`) runs the full coupled Link-roll + Tetra dynamics in C:
     the acch `CrrPos` for both actors (frsqrte `sqrtf_c`, `is_zero_x`, WallHDirect), the `dCcS`
     rank-split push pair, the complete type-5 Zl1 idle/move port (console sin/cos/atan tables), and
     Link's roll/cut folded to per-frame constants -- valid because (a) FRONT_ROLL/CUT world moves are
     `pos += f32(speedF*sin/cos(travel))` with a schedule-fixed speedF/travel (bonk disabled per the
     live-validated `m3570=False` grind), and (b) the animated Co-centre decomposes EXACTLY into
     position-independent per-joint f32-add constants (`body_cyl.roll_co_chain_consts`). Speed comes
     from exact-no-op reductions only: the static room cull (`land.walls.cull_walls`), an in-CrrPos
     AABB candidate prefilter, hoisted per-tri constants, precomputed WallCorrect slice chords, and an
     OpenMP `sweep_par`. Gated BIT-IDENTICAL to the live-validated Python `couple_replay` engine per
     placement (`harness/rollstab/fast_shove.py::gate_vs_reference`; `tests/test_shove_fast.py`).
     1.3 s/sim -> ~10 us/sim: a ~130,000x speedup.
  2. **A teleport-staged staging that threads (found by `harness/rollstab/search_shove.py`), kept as
     validation only (see 21b -- it is a mid-run hack, not the accepted mechanism).** The coarse sweep
     (13M+ sims, ONE approach line / entry point x thrust 13-15 x all placement steps) found no
     plow-mediated clip in THAT slice; the **last-pre-cut-step graze** (Tetra teleported onto the
     pre-cut Co-centre's graze circle so `old` stays on the wall pin and one clean ~0.6-0.83u
     seam-ward push feeds the cut) found **10 genuine coupled clips across 3 thrust timings** via the
     polar micro-search (angle 0.05 deg x depth 0.002u; the push sliver is dust, a 0.25u grid finds
     nothing), all bit-confirmed vs the Python engine. NOTE: acceptance slivers are per-`old`-bits --
     the session-18 golden push does NOT thread from the pin (`pred_genuine(pin, golden_push)` is
     False); never transfer a push between olds.
  3. **LIVE (slot 6): the teleport-staged clip reproduced, proving the whole physics chain.**
     `capture_cc_push slot=6 ... thrust_at=14 place_after_roll=14 tcx=-1625.9922189608035
     tcz=-923.4329080655332`: Link rolls to the pin (-1692.3143311, -955.0761108), Tetra appears on
     the graze, the UP+B CUT_F fires, and Link lands at **(-1727.45263671875, -990.7470703125)** --
     bit-for-bit the sim's genuine `new`, BEHIND the seam past the (-1727,-990) corner. Replay: both
     actors 0-ULP on the placement + clip frames (the parked-Tetra free-fall rows and the post-clip
     CUT tail are the known out-of-scope gaps). Locked fixture `fixtures/hyrule_tetra_clip_live.json`,
     gate `tests/test_shove_fast.py` (also gates the cull, the chain-consts decomposition, and
     native==Python). This retires any doubt about the engine, the CC push, the cut lunge, or the
     acceptance -- the remaining problem is purely the SEARCH for a no-hack staging (21b).
  - Also new: `land.walls.cull_walls` (order-preserving exact AABB cull), `fixtures/hyrule_shove_roll6.json`
    (the session-20 live shove capture, promoted from scratchpad -- the engine's gate fixture).
  - Open next (see 21b): the WIDE push-aside search (roll timing / Link entry / Tetra initial
    position / thrust timing / roll angle); then from-rest planning (the slot-6 walk-up modeled from
    a rest anchor, cf. the kaze `rest.rest_state`); the descoped CUT-tail/post-clip recovery.
- **Phase T (session 20): un-braced Tetra shove + roll-stab CUT_F entry LIVE-VALIDATED 0-ULP; the
  placement search was BLOCKED on coupled-sim SPEED (now resolved, above).** On slot 6 (Dereck's ideal setup: Link facing/camera
  40842 on-axis, sword DRAWN, ~528u runway) a straight roll into a movable behind-placed Tetra plows +
  repositions her and thrusts; the coupled sim (`cc_stepper` via `capture_cc_push`, now `slot=`/`sword_drawn=`
  aware) matches live BIT-EXACT for BOTH actors through the roll AND the CUT_F entry frame (the CUT tail
  diverges, descoped as in session 17). So the un-braced shove the staging search leans on is proven. BUT a
  460-placement offline sweep (thrust-frame 14, via the `couple_replay` engine) found **0 genuine clips**:
  closest `new` pins at the golden `old` z (~35u short), because a seam-ward push needs Tetra BEHIND, whose
  plow (a) is razor-chaotic and (b) knocks Link OFF the golden `old` so the lunge is wall-blocked short
  (seam-ward push and full-lunge-from-golden-old are mutually exclusive here at this timing; strengthens
  dead-ends #15-17). The FAST-centre predictor is INVALID (the push perturbs Link's feet, so his Co-centre
  is NOT Tetra-independent). **Blocker for the real search: the coupled sim is ~1.3s/sim** (99% in
  `acch_crr_pos` iterating all 765 walls/3162 tris every frame; anim secondary). Fix (handed off): cull walls
  to the corner (the pending Phase-W AABB cull) + precompute the roll Co-centre-offset + CUT `m3700` tables so
  the per-placement inner loop is pure arithmetic; target >=100k/sec. Then search placement x roll/thrust
  timing x placement-frame, and if empty, vary Link's roll angle/approach. Immovable Tetra (rank-10, near-
  guaranteed) is CONFIRMED IMPOSSIBLE here (decomp: escort hardcoded type-5 movable). Details:
  session-20 handoff; memory `tetra-clip-targeted-oneshot`.
- **North star: the TETRA seam clip, pure-sim** -- the phased plan (wall collision -> ground ->
  CC Link<->Tetra -> the Tetra clip) lives in `ROADMAP.md`. Phases W + G + the load-bearing Phase-C
  items are DONE; **Phase T is OPEN** -- its acceptance FOUNDATION landed (session 18). The Phase-T
  STAGING is the current open question (session 19 REOPENED it, below): how to position Link + Tetra so
  a controlled, seam-ward push lands on the cut frame. Remaining Phase-C items are the CUT *tail* (Co
  centre during the cut + the post-cut recovery proc), `GetCCMoveP` from Tetra's own recoil buffer, and
  the read-lag; the Phase-W full-room cull is speed-only.
- **Phase T (session 19): STAGING REOPENED -- the behind-Link *stationary* Tetra is REFUTED; the
  correct staging is now the open question.** An earlier draft of this entry claimed staging was
  "resolved = behind-Link stationary idle Tetra"; the coupled DYNAMICS refute it. What holds:
  - **The corner needs a push** (bare roll-stab is wall-blocked at every REACHABLE start; the wall pins
    Link at `old` ~= the golden and the bare CUT_F is blocked), and **the push must point TOWARD the
    seam** (bearing ~235deg, ~0.75u), which requires Tetra BEHIND Link (a corner-braced Tetra pushes the
    wrong way). Collision-valid start = Link's r=35 wall cylinder clears both walls (signed plane dist
    >= 35). These are sound.
  - **REFUTED: a stationary behind-Link Tetra cannot deliver a controlled push.** The needed push is
    only ~11deg off the roll line, so the delivering Tetra sits ~15u from the line -- exactly where
    Link's rolling Co centre travels -- so the roll-in PLOWS her (large chaotic pushes) and flings an
    un-braced Tetra ~40u away before the cut frame; the CUT_F then fires with zero/wrong push. The
    ONLY dynamically-controlled push is Link plowing a BRACED Tetra (sessions 15-17), but braced-in-
    corner points the wrong way. See dead-ends #17 and the session-19 handoff.
  - `harness/rollstab/solver_tetra.py` + `tests/test_tetra_solver.py` (6 green) exist and the offline
    STATIC-`co_move_pair` acceptance core is bit-exact vs the golden, BUT it assumes the refuted
    stationary-behind mechanism, so DO NOT build the from-rest solver on it as-is. Acceptance must be
    the DYNAMIC coupled cut (run the plow through `cc_stepper.CcCoupledStepper`), not a static predictor.
  - `solver.py`'s knob families gained an optional `F=` param (backward-compatible; default kaze) -- that
    part stands.
  - **NEXT (open): the staging strategy** -- position Link + Tetra so a controlled seam-ward push lands
    on the cut frame. Candidates (session-19 handoff): brace Tetra on the behind side; or accept the big
    braced-plow push and search old+aim+placement via the full coupled dynamics. Then it feeds the
    from-rest solver (needs a minted slot-3 rest anchor; none exists -- `mint.py` only translates within
    a room).
- **Phase T OPENED (session 18): the Tetra-corner seam-clip ACCEPTANCE FOUNDATION, live-anchored.**
  Measure-first (Phase-G discipline), the flooded-Hyrule corner at (-1727,-990) is now in the rollstab
  pipeline's conventions: `fixtures/hyrule_tetra_geo.json` (built offline from the live RAM golden
  `tests/golden/hyrule_seam_1727_ram.json` by `make_tetra_geo.py`: the two incident wall tris --
  wallA +X poly 2915, wallB +Z poly 2904, a 90.57-deg corner -- the 4-tri CrrPos barrier, `link_y` =
  Phase-G's flat 0.16327, seam vertex S, and the authoritative live-confirmed clip target old/new) and
  the acceptance module `geometry_tetra.py` (the `geometry.py` sibling, PUSH-AWARE: `pred_genuine(old,
  push)` tests the COUPLED endpoint `new = f32(old + push + lunge)` in the decomp `posMove` order, not
  the bare kaze `old + LUNGE`). **Established facts (gate `tests/test_tetra_geo.py`, offline, 5 green):**
  the corner is a NEEDS-PUSH clip -- the 49.2202u lunge (facing F=40874) lands **~0.7507u short** of the
  seam; a **~0.7506u Link CC push** (the ~1.5u corner-braced-Tetra overlap x the 0.50 rank-table share)
  steers `new` behind the seam and reproduces the live golden endpoint **BIT-EXACT** (0-ULP). Measured
  dust structure (informs the coupled solver): with the push fixed, `old` clips over a **~0.86u
  along-band at ~8% f32 density** (kaze-like -- the approach razor is threadable by the from-rest knobs,
  not a single lottery point); the push is razor-thin as a continuous knob but that is a NON-issue --
  it is produced bit-exactly by the coupled sim from Tetra's f32 placement, so the solver places Tetra
  at f32 coords, lets the exact push fall out, and tests the exact candidate (the seam-clip-solver
  discipline, extended to placement). NOT yet done: the from-rest COUPLED solver (search a Tetra
  placement + approach that lands `old` on the sliver) and its clean-DTM live clip -- the next increment.
- **Phase C CLIP-FRAME ORDERING now BIT-EXACT (session 17): the roll-stab CUT_F entry, LIVE-GATED
  0-ULP.** The clip frame is the single frame Link fires a FORWARD `CUT_F` out of the roll into the
  corner-braced Tetra, so it stacks -- in the decomp's `posMove` order (`d_a_player_main.cpp:2556-2610`)
  -- `posMoveFromFootPos` (the roll speedF move) -> consume `mStts.m_cc_move` (the ~22u CC push from
  the prior frame's `dCcS` overlap) -> the `m34C2` cut root-translate lunge (~49u) -> `dBgS_Acch::CrrPos`
  (the wall pass). This ordering was already structurally in `step()`; this session live-VALIDATED it.
  The coupled stepper already dispatches the roll->CUT continuation (`roll._roll_exit` -> `_cut_init` on
  the B rising edge with the sword drawn); `cc_stepper.couple_replay` now replays the capture's per-frame
  controller inputs (not a neutral hold) and seeds `sword_drawn`, so the B thrust fires the CUT at the
  same frame it did live. **LIVE (slot 3, `capture_cc_push.py` with `draw_at=`/`thrust_at=`):** sword
  drawn early during the walk-up (so the drawn-sword walk still rebuilds to the speedF-17 cap for a
  full-26 roll), Link rolls into wall-braced Tetra, and a UP+B thrust (a *neutral* B is a side slash --
  dead-end #12) fires an in-line `CUT_F` at roll anim-frame >17. The coupled sim reproduces **every
  frame from Tetra's placement through the CUT_F entry 0-ULP for BOTH actors** (the roll-into-braced-
  Tetra approach AND the push x cut-lunge x wall-pass on the clip frame). Gate `tests/test_cc_rollstab.py`
  (fixture `fixtures/hyrule_cc_rollstab.json`, no Dolphin via `couple_replay`).
  - Scoped to the CUT_F ENTRY (the single-frame lunge that decides the clip). The CUT *tail* diverges
    and is NOT asserted (a separate, non-clip gap): the sim keeps posing Link's Co centre with the
    frozen roll anim (`body_cyl.roll_co_center`) rather than the CUT pose, and live enters a post-cut
    recovery proc (`0x5a`) the sim does not model. Both are moot for the clip (fully decided by the
    entry-frame lunge; the roll never re-walks after) -- like the descoped roll->MOVE exit gap.
  - This capture is wall-BLOCKED (Link rolled straight into the corner, so `CrrPos` eats the lunge's
    z): it validates the ORDERING, not a clip-through. Threading the lunge behind the seam is the
    solver's job (Phase T), not this ordering gate.
- **Phase C CC-PUSH STEPPER wired + live-validated to the push frame (session 15).** The Co push is
  now in the per-frame stepper in the decomp's order: `LandState._cc_move` (set via `set_cc_move`)
  is consumed in `posMove` AFTER `posMoveFromFootPos` (the speedF/foot move) and BEFORE the m34C2
  cut root-translate + the CrrPos wall pass (`d_a_player_main.cpp:2556-2610`; the overlap that feeds
  it is computed in the DRAW phase, `dScnPly_Draw -> dCcS::Move`, from the prior frame's settled
  positions). `cc_push.co_move_pair` returns BOTH actors' `SetPosCorrect` moves (Link's is bit-
  identical to the shipped `co_push_link`; same-rank 50/50 -> equal and opposite). The coupled driver
  `harness/rollstab/cc_stepper.CcCoupledStepper` runs Link (`LandState`) + Tetra (`Zl1FollowState`)
  together, computing the overlap each frame from Link's animated roll Co centre (`body_cyl.
  roll_co_center`) and Tetra's cylinder. **LIVE (slot 3, `capture_cc_push.py`):** Tetra teleported
  into the corner (WallCorrect braces her), Link rolls in from far out and CONVERGES into her while
  she is wall-braced. The coupled sim reproduces this **0-ULP**: Link's wall-approach roll AND
  Tetra's teleport-into-corner brace are bit-exact every frame, and Link stays bit-exact right up to
  the frame the push is first consumed (proving the push is applied at the right point). Offline gate
  `tests/test_cc_gate.py` (fixture `fixtures/hyrule_cc_push.json`, replayed with no Dolphin via
  `cc_stepper.couple_replay`); offline math/consumption gates `tests/test_cc_stepper.py`.
- **Phase C PUSH FRAMES now BIT-EXACT through the whole roll (session 16): the body lean, not the
  morf.** `test_coupled_push_frames_bitexact` was RED because once the push converged (roll frame ~6)
  Link drifted; the session-15 note blamed the `roll_co_center` oldframe-morf. Root-caused this session
  by capturing the live lean terms (`harness/rollstab/capture_roll_lean.py`, mCyl centre + `mBodyAngle`
  + `m34F2/m34F4` per frame): the early-frame residual is **NOT** the morf (`initOldFrameMorf(mRoll.
  field_0x14=2.0,...)` touches roll frame 0 only) -- it is the missing `setWorldMatrix` base `ZXYrotM`
  z-tilt by `shape_angle.z` (the MOVE turn lean `m351C>>1`). A curved approach carries a nonzero turn
  lean into the roll (`mBodyAngle.x=y=0`, `m34F2=m34F4=0` throughout -- only `mBodyAngle.z==shape_angle.z`
  is nonzero); it decays ~35%/frame, and the old clean (lean-0) centre made the push overlap -- hence
  Link -- drift. Fix: `body_cyl.roll_co_center(..., shape_z=)` feeds the **previous frame's** lean to the
  base (the setWorldMatrix/setMoveSlantAngle 1-frame lag; the `jointBeforeCB` body_chn rotation
  contributes nothing to the xz midpoint, verified live). `LandState` now exposes `_draw_lean` + evolves
  `m351C` every frame; `cc_stepper` passes it and seeds `m351C` at roll entry from the live value.
  **RESULT (live re-capture, slot 3): every FRONT_ROLL push frame 0-ULP for BOTH actors** (was bit-exact
  only to the pre-push f14; now through the entire roll to f26). Regression: `body_cyl` 0-ULP vs
  `fixtures/hyrule_roll_lean.json` (`tests/test_body_cyl.py`); `test_cc_gate.py::test_coupled_push_frames_bitexact`
  flipped xfail->pass (scoped to the roll frames). Offline land + live land 14/14 byte-identical (the
  `state.py` lean change is inert on position).
  - Still open for Phase C: the roll's EXIT to MOVE is not bit-exact (the neutral-hold capture's f27+;
    the separate "mid-run stop -> re-walk" gap -- irrelevant to the clip, which fires a CUT out of the
    roll); `GetCCMoveP` wired from Tetra's own recoil pending-buffer; the three-way CC -> WallCorrect ->
    net-overlap ordering on the actual clip frame; the Tetra read-lag (execute order Link-then-Tetra).
- **Phase C Tetra FOLLOW + attention DONE (session 14): the Tetra counterpart state, LIVE-GATED
  0-ULP.** The type-5 (following) Tetra's per-frame model is decomp-faithful and bit-exact vs live:
  `tww_sim/core/npc_zl1.Zl1FollowState.step(link_pos)` runs the `optn_1`/`optn_2` idle<->move state
  machine (`d_a_npc_zl1.cpp`) -- engage at 3D dist > 230, turn (`cLib_addCalcAngleS 4/0x800/0x80`),
  accelerate (`cLib_chaseF` 1 u/f) to a distance-capped target speed (`0.04*sqrt(dist^2-130^2)`, max
  10), decelerate, stop <=130 -- then `posMoveF`/`calcSpeed`/`posMove` + a flat-ground `CrrPos` Y
  clamp. Live gate: `harness/rollstab/capture_tetra_follow.py` teleports Tetra far on slot 3, logs
  her chase back to a stationary Link; the offline replay matches **0-ULP over 119 frames** (pos +
  facing + speedF + action-state), engage->cruise->stop (fixture `fixtures/hyrule_tetra_follow.json`,
  regression `tests/test_tetra_follow.py`; seed from frame 1 past the 1-frame post-teleport settle).
  Also `zl1_attention_active(link_pos, link_facing, tetra_pos)`: the decomp-exact L-target / talk /
  speak AVOID region (`dist_table[0xAB]`: XZ < 300, |dy| < 300, Link facing within +-90deg of Tetra)
  so a planner routes the setup so an A/L press near her doesn't talk/lock instead. Her **BG
  collision** is also modeled + LIVE-GATED 0-ULP: `mObjAcch.CrrPos` is the SAME `dBgS_Acch::CrrPos`
  pass as Phase W (`dBgS_ObjAcch` subclass, no override) with her single R=50/half-H=30 AcchCir;
  `Zl1FollowState.step(walls=)` runs it. She floats with speed.y==0 on the corner (live), so the
  pass uses speed_y=0 (a -4.5 dip is 1 ULP off). Validated by a corner-wall eject
  (`fixtures/hyrule_tetra_wallcorrect.json`) - this WallCorrect wall-brace (wedged Tetra's CC recoil is
  canceled so she holds) is a validated MECHANIC; whether it helps the clip is OPEN (a corner-braced
  Tetra pushes the WRONG way, a stationary behind-Link Tetra gets plowed -- clip staging unsolved, see
  the Phase-T status entry). Mechanic page `knowledge/mechanics/tetra-follow.md`. Open Phase-C items: the `GetCCMoveP` term at
  the decomp's frame point, the three-way CC-push -> WallCorrect -> net-overlap ordering, the
  attention live reticle confirmation, and the Tetra read-lag (the follow gate used a stationary Link).
- **Phase G DONE (session 13): the Tetra floor is FLAT -> ground collision is a no-op for this clip.**
  Measured before modeling (as ROADMAP prescribes): the walkable floor Link's roll crosses at the
  (-1727,-990) Tetra corner (flooded Hyrule, savestate slot 3) is a single flat tri (poly 2917),
  normal (0,1,0), plane Y=0.16327, spanning the entire roll footprint old->seam. Verified by an
  INDEPENDENT method (normal recomputed from raw vertices via cross-product == the game's stored
  plane == (0,1,8e-08); a dense grid over the whole roll region finds no other walkable-height tri).
  The 25-deg surface sharing the XZ footprint sits ~560u overhead (terrain) and is never touched. So
  `getGroundAngle` r3 = 0 (already hardcoded in the sim's speedF `cM_scos` scale; r3<0 x0.85 never
  fires) and m35B8 per-foot ground-lift is provably 0 -- the existing flat-floor model applies to the
  Tetra clip unchanged; NO GroundCross/getGroundAngle/m35B8 modeling needed. Self-contained capture
  `harness/rollstab/capture_ground.py` (`dolphin_mem` only, capture_walls.py pattern) -> fixture
  `fixtures/hyrule_tetra_ground.json`; regression `tests/test_tetra_ground.py` (flatness + footprint
  coverage + single-plane; goes RED if a future Tetra spot ever shows slope).
- **Phase W CORNER ORDERING DONE (session 12): multi-wall WallCorrect in game order, LIVE-GATED
  0-ULP.** When the cylinder wedges between two non-coplanar walls, WallCorrect corrects them
  sequentially, so the poly ORDER decides the result. The game's order is its DZB block-grid walk
  (`WallCorrectGrpRp` -> `WallCorrectRp` octree DFS -> `RwgWallCorrect`), and since `ClassifyPlane`
  builds each block's wall list in ascending poly index it is reconstructable STATICALLY from the
  DZB header tables. `capture_walls.py` reconstructs that walk and writes the room's walls in exact
  game order to `fixtures/kaze_r11_walls_ordered.json` (stored bit-exact planes) -> the sim loads it
  via `land.walls.load_ordered_mesh`. Corner gate (`cornergate.py`): walk into the
  110-deg seam vertex on the minted `kaze_r11_wallcorner` anchor; **CORNER GATE BIT-EXACT** per
  frame (48/48, incl. 24 two-wall frames), and the SWAPPED order diverges (24/48) so the ordering
  is load-bearing. Golden `tests/golden/rollstab_corner.json`, regression
  `tests/test_rollstab_corner.py` (incl. an order-load-bearing guard). At kaze the seam is wallA
  (poly 705) before wallB (poly 713): same block 137, ascending index.
- **Phase W CORE DONE (session 11): WALLS IN THE STEPPER, LIVE-GATED 0-ULP.** `LandState(walls=)`
  runs the player-faithful per-frame CrrPos wall pass (`core.collision.acch_crr_pos`: every-frame
  LineCheck with the full normal-add/WallHDirect response, WallCorrect with the mid-frame gravity
  dip, console `sqrtf_c`, exact 2^-18 IsZero) + the proc feedback (setNormalSpeedF wall-hold, the
  m3570 roll-bonk latch, FRONT_ROLL_CRASH fully modeled, the sidle A-guard). Four clean-DTM gates
  on the minted `kaze_r11_wallgate_faceB` anchor (head-on hold / oblique slide / roll crash /
  slow-roll grind) verified **WALL GATE BIT-EXACT** per frame (pos bits + proc + facing), via
  `wallgate.py` (mint/plan/run/verify/golden). Goldens `tests/golden/rollstab_wall_*.json` +
  regression `tests/test_rollstab_walls.py`; mechanics page `knowledge/mechanics/wall-response.md`.
  - Planner-rejection contract: a bonk = FRONT_ROLL_CRASH in `visited`; a sidle-suppressed roll
    sets the sticky `sidle_blocked` (the sidle proc itself is intentionally unmodeled).
  - Phase-W open edge (speed-only): a full-room block-grid AABB cull so a corner could enter the
    2-minute solver budget (the sim iterates all 765 ordered walls today, ~33 ms/frame pure-Python;
    far polys already no-op, so a cull is pure speed). Walls for the ballistic hops + freeze frames.
  - **NEW flagged gap (non-wall, found by the grind gate): mid-run stop -> re-walk.** A full stop
    to WAIT and MOVE re-entry is NOT bit-exact (the WAIT row matched; the re-walk entry speedF
    diverged). From-rest entries are exact; avoid full stops inside plans until modeled.
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
