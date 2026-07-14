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

## Status (2026-07-14, session 46)

> SINGLE SOURCE OF TRUTH for current seam-clip state. A pre-commit gate blocks any commit
> that changes `harness/rollstab/*.py` without touching this file, so keep it current.
> The session prompt (`SESSION_PROMPT.md`) points here for state rather than restating it.

> **CURRENT THREAD (2026-07-14, session 46): the SOLVER GENERALIZATION is BEGUN -- Phases 1-2 of the
> session-45 kickoff are DONE + green (OFFLINE, ZERO behavior change).** Dereck scoped this: the Tetra
> push clip (`geometry_tetra`/`solver_tetra`/`pushaside`/`turnaround`) is a STANDALONE, single-seam solver
> and stays separate; the generalization is for STANDARD roll/wall clips (`geometry.py` + `solver.py` +
> `walkstab.py`). Done this session:
> - **`SeamGeo` abstraction built (`harness/rollstab/seamgeo.py`).** A per-seam roll/wall-clip geometry +
>   exact-acceptance object, DERIVED from a geo fixture + the anchor camera yaw. `geometry.py` is now a
>   THIN instance-backed shim over it (loads the kaze r11 fixture, builds `SeamGeo`, re-exports the whole
>   `G` surface -- `F`/`LUNGE`/`TRIS`/`genuine_clip`/`pred_genuine`/`perp`/`along`/...). Both of SeamGeo's
>   inputs come from STATE, not pasted constants -- exactly what a live tww-python Dolphin feed will supply:
>   the seam geometry from the room's DZB collision (the fixture was built from live RAM by
>   `capture_walls.py`) and the camera yaw from Link's `csangle` (READ from the canonical kaze anchor's
>   rest snapshot, not hardcoded). The full suite is BYTE-IDENTICAL (346 pre-existing passed, unchanged;
>   the razor accept in `solver.run` already used the real sim cut, not `G.LUNGE`).
> - **F is DERIVED, not pasted (`seamgeo.derive_F`).** F = the walk want-target (m34E8) of the
>   closest-reachable full-deflection stick to the interior `bisector_deg` at csangle
>   (`stick_for_bearing(bisector, csangle, 1.0)` -> decode -> `+0x8000+csangle`). GATE: derived F == 33295
>   bit-exact at the kaze roll seam (csangle 29883); `test_F_is_camera_dependent` proves it moves with the
>   camera (no reintroduced literal). The pasted `F = 33295` is deleted.
> - **The cut LUNGE is DERIVED per-candidate, not a frozen delta.** `SeamGeo.cut_new(old)` computes the
>   CUT_F entry endpoint from the CUT anim's joint-0 root translate at F + the roll speedF (26) lunge term,
>   BIT-IDENTICAL to `LandState.enter_cut` (gated `test_cut_new_matches_enter_cut_bit_exact`, 4 olds
>   spanning the band, 0-ULP). This deletes the pasted `LUNGE = (-2.32.., -49.16..)`: the old literal was
>   an approximation extracted at ONE `old` (the shipped hit's ~9072), and (the audit found) the two
>   geometry modules' LUNGE literals were even extracted at DIFFERENT `old` conventions (kaze at the
>   shipped old, tetra at origin) -- computing per-`old` removes that drift entirely. Verified: the new
>   per-`old` `pred_genuine` gives IDENTICAL genuine verdicts to the old frozen add over the entire
>   337,200-point dust-cache region + the deliver sliver points (0 mismatches). `LUNGE` remains exposed as
>   an origin-referenced derived property (magnitude 49.2202, the roll-stab reach) for compatibility.
> - **Regression `tests/test_seamgeo.py` (5 green)** locks F-derived-bit-exact, F-camera-dependent,
>   cut_new==enter_cut 0-ULP, shim-is-instance-backed (verdicts identical over the dust band), and the
>   reach magnitude. Suite **351 passed, 1 skipped, 2 xfailed** (was 346; +5 new). NO `sim.py`/`land.py`
>   change, so the live sim-vs-Dolphin regression is unaffected.
>
> **NEXT (per the session-45 handoff, OFFLINE until the Phase-5 live close):** (3) thread `SeamGeo` through
> `solver.run`/`base`/`search`/families (replace the module-global `G`; `!= G.F` gate -> `seam.F`; the
> drill cache -> `seam.pred_genuine`) -- GATE: re-solve the kaze roll seam via the parameterized path,
> reproduce the shipped seed-0 hit bit-exact. (4) Generalize `walkstab` the same way (absorb its PRIVATE
> acceptance duplicates into SeamGeo; derive the settled thrust facing from the bisector like F; derive the
> crawl-window center from `bear_to_S`, not `CRUISE_BETA`) -- GATE: reproduce the shipped walk-stab clip.
> (5) Drop `thrust_scan`'s `_matches` kaze guard, dispatch to a NEW enumerated seam, MINT an anchor there,
> solve via the generalized path, DELIVER a clean-DTM 0-ULP clip -- that live clip on a novel seam is the
> real "generalization works" proof. Every other thread (sheathed clip DONE, walk-stab clip, Tetra
> push-aside/turnaround, thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-14, session 44): the SHEATHED ROLL-STAB CLIP IS DELIVERED LIVE, 0-ULP,
> pure-sim, no calibration.** The session-43 blocker (the session-39 hit "doesn't survive seed=0") was
> NOT a density wall to grind past -- it was a GENERAL seed-0 crawl-composition bug, fixed structurally
> (no tuned constants). Done this session (offline + 2 live clean-DTM runs -- 1 ship + 1 golden capture,
> never advancewith):
> - **ROOT CAUSE nailed + fixed GENERALLY (dead-end #35's "NEXT" step 1).** Under `dtm_seed=0` the game
>   delivers one FEWER leading neutral poll, so `rest_state` burns one MORE leading no-op
>   (`noops = rest_noops + (1 - dtm_seed)`, measured live s43). That extra no-op was silently EATING the
>   start-crawl's first frame `start[0]` (a dead no-op absorbs it), so every crawl-based search composed
>   one frame short under seed=0 -- exactly why the s43 re-solve "hit a density wall". The fix
>   (`solver.run`): prepend `(1 - dtm_seed)` neutral ABSORBER frames so `start[0]` always lands on the
>   first LIVE frame. The absorber is a FULL frame (a `polls` multiple), so seed-0's correct sub-frame
>   poll phase is PRESERVED (unlike a seed neutral = 1 poll). seed=1 => 0 absorbers => byte-identical.
> - **The session-39 recipe, RE-COMPOSED under `dtm_seed=0`, is genuine bit-for-bit AND ships.** This is
>   NOT the ruled-out "deliver the s39 BYTES via seed=0" (#35: replaying the seed=1 bytes with no
>   absorber lands +0.588u off-razor). Re-composing produces DIFFERENT bytes (absorber prepended) that
>   compose correctly for seed=0 delivery: `run(..., dtm_seed=0)` reproduces
>   `old=(9072.2089844,308.0280762) -> new=(9069.8886719,258.8625793)`, disp 49.2202, CUT_F, spF@A=17,
>   genuine+clear+sliver-robust -- bit-identical to the seed=1 sim. The general fix, applied to the
>   existing derived recipe, delivered it; no bespoke/tuned solver.
> - **LIVE CLIP CONFIRMED 0-ULP.** `deliver ship` (auto seed=0 from the hit's `dtm_seed`) played a clean
>   DTM: live `old`/`new` bit-for-bit == the sim (drift d(old)=(0,0)), proc 0x42 (CUT_F) at the cut then
>   proc 0x24 (OOB) -- threads=True, behindA=True, behindB=True. The scanner now routes a NOT-DRAWN
>   (sheathed) anchor's ROLL verdict end-to-end to a live clip (the milestone's "done").
> - **Locked live-data-backed:** immutable game_frame-tagged golden
>   `fixtures/sheathed_roll_ship_seed0_golden.json` (captured from the successful ship). Gate
>   `tests/test_sheathed_roll_clip.py`: `test_sheathed_ship_delivery` RED-xfail -> **GREEN** (sim bit-exact
>   vs the seed-0 golden on every game_frame-aligned row THROUGH the CUT_F entry; the post-cut OOB fall
>   proc 0x24 is the known-unmodeled CUT tail, moot for the clip); NEW `test_seed0_crawl_frame_acts`
>   locks the general fix (seed-0 stream carries one absorber, crawl composes seed-invariantly);
>   `test_seed1_delivery_drops_band` keeps the #34 seed=1 drop gated (xfail). `test_s39_hit_not_genuine_
>   under_seed0` (s43) still PASSES -- the raw seed=1 bytes are correctly still not seed-0-deliverable
>   (re-composing, not byte-replay, is the fix). Suite **346 passed, 1 skipped, 2 xfailed**. Only
>   `harness/rollstab/solver.py` behavior changed (the absorber; seed=1 byte-identical) -- NO
>   `sim.py`/`land.py` change, so the live sim-vs-Dolphin regression is unaffected.
>
> **NEXT (the clip is DONE; remaining is polish, not blocking):** (1) OPTIONAL -- fold the seed-0 solve
> into the harness as a reproducible <2-min search: the generic `solver.search`/drill under seed=0 is
> still over-budget and does NOT reach the f32 dust on its own (a real property of the seam -- the derived
> recipe came from session 39's focused warm-start, now made deliverable by the general fix). A reproducible
> focused solve (warm-started, no tuned constants) would close the objective's "found by the search"
> clause; the CLIP itself is delivered. (2) The generalize-off-hardcoded-kaze-seam work (thrust_scan
> dispatch to any enumerated seam) stands. Every other thread (walk-stab clip, Tetra push-aside/turnaround,
> thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-14, session 43): the make_dtm seed=0 delivery fix is PLUMBED end-to-end and
> its from-rest model is MEASURED LIVE + bit-exact -- but shipping is BLOCKED on a RE-SOLVE: the
> session-39 hit does NOT survive seed=0, and re-solving hits the sessions-39/40 f32-dust density wall.
> No sim/physics behavior changed; all `seed`/`dtm_seed` plumbing is byte-identical at the seed=1
> default (suite 342 passed, unchanged).** This was session-42 NEXT (ship the fix). Done this session
> (offline + 1 live jitter-immune capture_walkentry seed=0, never advancewith):
> - **`seed`/`dtm_seed` threaded end-to-end** (additive, default 1 = byte-identical): `rest.rest_state
>   (dtm_seed=, noops=)`, `capture_walkentry.capture(seed=)`, `solver.base/run/search(dtm_seed=)` +
>   `_record` tags each hit's `dtm_seed`, `deliver.gate/replay/ship` read the hit's `dtm_seed` and
>   author the DTM with it. The `run_dtm`/`make_dtm` `seed` param already existed.
> - **The seed-0 leading-poll layout is MEASURED, not guessed (handoff step 2 DONE).** Captured the
>   seed-0 walk-entry live (jitter-immune, game_frame-tagged) and diffed the sim d_frame-aligned vs the
>   seed-1 golden: seed=1 => noops=1 (28/0 bit-exact, byte-identical to before), **seed=0 => noops=2
>   (28/0 bit-exact, dz=0 every aligned row)**. So the coupling is `noops = rest_noops + (1 - dtm_seed)`
>   (fewer leading neutral polls => the game's rest blend advances one MORE frame before the plan, so
>   the sim needs one MORE leading no-op -- the OPPOSITE sign of the intuitive guess). Immutable golden
>   `fixtures/sheathed_walkentry_seed0_golden.json`; gate `tests/test_sheathed_roll_rest.py::
>   test_sheathed_rest_bitexact_seed0`.
> - **The `solver.fine_family` band-exclusion is REMOVED (handoff step 4a):** band fines (msd 0.889-1.0)
>   are usable again under seed=0 (delivery faithful). NOTE they are an ALONG knob (the speedF dip), not
>   perp, and near-cap ones octagon-clamp -- so they did NOT break the perp density wall below.
> - **LOAD-BEARING NEGATIVE RESULT: the session-39 hit does NOT clip under seed=0.** Replaying its exact
>   stream bytes through the (measured-correct) seed-0 model, `old` shifts **+0.588u in z (308.028 ->
>   308.616), off the f32 razor -> NOT genuine** (behind neither wall). So the handoff's hope that "the
>   s39 hit should clip" under seed=0 is DISPROVEN; a fresh seed-0 solve is REQUIRED (gate
>   `test_s39_hit_not_genuine_under_seed0`). [Mechanism: seed-0's extra leading no-op shifts the whole
>   from-rest approach; the dust is single f32 columns, so any along-shift lands off-razor.]
> - **The re-solve hits the sessions-39/40 f32-DUST DENSITY WALL (open).** ~several-thousand-run focused
>   sweeps under seed=0 (arc gross-perp -> |rho| 0.017 collapses because full-mag arcs octagon-clamp;
>   partial interior 3rd-crawl-byte fine-perp -> ~2e-4 steps but a DEAD-BAND GAP over rho=0; A_proj/sub-
>   band along fines -> coarse z, few distinct sticks at bearing F; partial-mag arc -> 0.033 worse)
>   reached **~0.0035u nearest, 0 genuine** -- mirroring session 40's 0.0013u wall. The lattices tried
>   don't align onto a genuine column. This is the SAME frontier that consumed sessions 39-40; the
>   generic `solver.search` drill is over-budget (>2min) and under-samples.
>
> **DEEPER ROOT CAUSE + anti-overtuning course-correction (session 43, later in the session):** the
> re-solve difficulty is NOT a constant-tuning problem -- it is a GENERAL seed-0 CRAWL bug. Under
> `dtm_seed=0` the leading no-op count is 2, so `rest_state`'s seed step eats noop #1 and **the FIRST
> start-crawl frame (`start[0]`) is eaten as a dead no-op** -- so any crawl-based search under seed=0
> silently loses its first crawl frame (this is almost certainly why the existing derived search
> under-performed under seed=0, NOT its constants). Verified knob roles (Dereck's hint): the ACTED crawl
> MAGNITUDE is the fine along/z fill (an acted crawl frame's magnitude walks `old` z across ~298.5..308.5
> in fine steps); partial-INTERIOR crawl BEARINGS give continuous perp (|rho|->0.0007); `A_proj` is COARSE
> (the fixpoint crossing pins the along-position -> A_proj only selects the ~16u walk-step, NOT the
> sub-step fill). A prototype `solve_focused` with hand-tuned bearing/magnitude/A_proj grids was built and
> DISCARDED as calibration-flavored drift (Dereck flagged the overtuning). dead-end #35 (expanded).
>
> **NEXT (the principled, least-tuning path -- delivery fix + live-measured model are DONE and locked;
> only the seed-0 solve remains):** (1) fix the seed-0 leading-dead-frame GENERALLY at
> `run()`/crawl-composition (so `start[0]` is not silently dropped) -> every DERIVED family
> (`start_family`/`arc_family`/`fine_family`, already parameterized off csangle + the movement-gate band,
> no magic constants) composes correctly under seed=0; (2) run the EXISTING `solver.search`/catalog under
> `dtm_seed=0` (do NOT hand-tune a bespoke per-seam solver); (3) if it still can't reach the f32 dust in
> <2 min, that is a real finding about the seam, not something to paper over with tuned constants. Then
> `deliver ship` (auto seed=0 from the hit's dtm_seed) -> live OOB clip -> flip `test_sheathed_ship_
> delivery` GREEN. Validate any hit with `capture_decode.delivery_sweep` (every fine received + roll-row
> unchanged + OOB). Every other thread (walk-stab clip, Tetra push-aside/turnaround, thrust scanner)
> UNCHANGED.

> **PRIOR THREAD (2026-07-14, session 42): the sheathed-clip row-18 blocker is RAM-CONFIRMED as a
> `make_dtm` DELIVERY DROP -- NOT a physics/decode gap, and NOT the "band walk-speed" of #33 (overturned).
> The game never RECEIVES the row-18 band fine; make_dtm's default `seed=1` poll phase drops it. The fix
> is characterized live (`seed=0` + re-derive `rest_noops`) but NOT yet shipped. No sim/physics code
> changed.** Following Dereck's steer to READ THE PAD FROM RAM (not infer it), done this session
> (decomp trace + ~7 live DTM captures reading `g_mDoCPd_cpadInfo[0]`, never advancewith):
> - **Decomp EXONERATES the physics + decode (traced, not assumed).** Every row-18-path function matches
>   the sim line-for-line (`setStickData` 10569, `setNormalSpeedF` 2301 -- the `msd^2*max` decel is
>   UNCONDITIONAL once below nspeed, `setSpeedAndAngleNormal` 2751, `setBlendMoveAnime` m3598, the 0.3/0.7
>   toe recursion 2399-2484); `PADRead->PADClamp->CStick::update->mMainStickValue` is stateless. So IF the
>   game received `(96,192)` (msd 0.9605) it MUST decel -- there is nothing to "model" (kills #33).
> - **The decode is faithful even for Y>=192 when ISOLATED.** A 1-frame `(96,192)` after plain cruise
>   delivers `cpad_val=0.9605` == the sim and dips (`transient_probe`). So no band-walk-speed gap exists.
> - **In the SHIP the band fine is DROPPED (RAM-confirmed).** At fed-index 16 (acted row 18) the game polls
>   the FULL neighbour: `cpad_val=1.0, (px,py)=(-0.32,0.95)` = the `(77,249)` stick, not `(96,192)`. A
>   distinctive px=0 marker at fed-16 ALSO drops (positional, value-independent); an all-full ramp delivers
>   every frame; the ship's other fines (0.9313/0.7848/0.8784) DO deliver -- so a CLUSTER of preceding
>   partials induces a poll-phase slip that drops a later 1-frame partial. That one dropped dip is the
>   ENTIRE 1.9125u miss (offline: forcing row-18 to full shifts along-track by exactly -1.91248u).
> - **`make_dtm`'s poll cadence is the cause; `seed` controls it (live sweep, `delivery_sweep`):**
>   `(polls=4, seed=1)` [default] drops the band, roll row 22; `(4, seed=0)` DELIVERS it at the SAME roll
>   row 22 (timing preserved); `(4, seed>=2)` delivers but shifts timing to row 23; `(8, *)` delivers all
>   but at ~2x timing (breaks the plan's discrete B/A). The game reads ~4 SI polls / 30fps frame (polls=4
>   = correct 1:1); `seed=1`'s leading neutral poll is the phase that slips.
> - **THE FIX (characterized live, NOT shipped):** `make_dtm(seed=0)` alone delivers the band but leaves a
>   ~0.6u residual and no OOB clip -- because it shifts the leading-poll layout the from-rest prefix's
>   `rest_noops` (s38) is calibrated to. Clean fix = **`seed=0` PLUS re-derive `rest_noops` for the seed-0
>   layout**, re-verify REST BIT-EXACT, then the session-39 hit should clip. The `fine_family` band-exclusion
>   (s41/solver.py) is NOT the fix and should be REMOVED once delivery is faithful (it kills usable density).
> - **Artifacts:** the RAW pad read (`g_mDoCPd_cpadInfo[0]`) is PROMOTED into `capture_decode.py`
>   (`capture` logs cpad_val/px/py; `delivery_sweep(anchor, stream, combos)` = the (polls,seed) delivery
>   probe reporting fines-received/roll-row/OOB-clip; `python -m harness.rollstab.capture_decode sweep`).
>   RED gate renamed `test_sheathed_roll_clip.py::test_sheathed_ship_delivery` (reason corrected to the
>   delivery drop). dead-end #34 (+ #33 correction banner). Suite **342 passed, 1 skipped, 2 xfailed**
>   (unchanged count). NO sim/physics behavior changed; the interim `fine_family` exclusion is UNTOUCHED.
>
> **NEXT: ship the make_dtm fix.** (1) `make_dtm`/`run_dtm`/deliver default to `seed=0` (or thread it),
> keeping `polls=4`. (2) Re-derive the sheathed anchor's `rest_noops` for the seed-0 leading-poll layout
> (mint.capture_rest derives it; or bump/measure it) and re-verify REST BIT-EXACT via `capture_walkentry`.
> (3) `deliver ship` the session-39 hit -> confirm live 0-ULP CLIP (proc 0x24 OOB) -> flip
> `test_sheathed_ship_delivery` GREEN. (4) REMOVE `solver.fine_family` band-exclusion, re-solve if needed.
> GUARD: re-run the existing bit-exact goldens (walk-stab, tetra, rollstab_rest) under the new seed --
> if seed=0 changes their alignment, thread `seed` per-call rather than changing the global default.
> Every other thread (walk-stab clip, Tetra push-aside/turnaround, thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-14, session 41): the sheathed-clip row-18 blocker is RE-ROOT-CAUSED
> DETERMINISTICALLY and it OVERTURNS BOTH #31 AND #32 -- the live miss is a ONE-FRAME WALK-SPEED
> gap the sim isn't modeling (a band-magnitude stick at cap), NOT a decode or facing error. Per
> Dereck's directive, a RED gate is added for next session to resolve by MODELING it. No sim behavior
> shipped except the interim `fine_family` band-exclusion.** Done this session (offline + ~5 live
> DETERMINISTIC DTM measurements, never advancewith):
> - **The band DECODE is faithful even for a 1-frame transient (overturns #32).** A deterministic
>   stopped-position probe (`aim-cruise + [1-frame T] + neutral-to-DEAD-STOP`, read the constant
>   stopped pos -> ±1 log jitter cannot corrupt it): the culprit `(96,192)` live stopped pos == the
>   sim's RAW-decode prediction BIT-FOR-BIT (the "holds prior" prediction was off 20.9u); sub-band
>   control likewise. The decode formula is correct; the whole game stick path (PADRead->PADClamp->
>   CStick::update) is STATELESS (decomp), zero prior-frame state.
> - **The divergence is purely ALONG-TRACK (speedF), not facing (overturns #31).** gf-aligned to the
>   jitter-immune golden (emulator counter ticks 2x/game frame -> gf = 2*row + const, 0 conflicts):
>   rows 0-17 BIT-EXACT (incl. the arc + sub-band fines + a held-2 full stick), then row 18 the sim
>   dips speedF 17->15.091 while live holds 17.0 (perp x matches to 0.02u). `17-15.091 = 1.909` ==
>   the 1.9125u lag, frozen through the roll -> `old` off the razor -> no clip. Two independent live
>   runs agree (golden + a fresh `deliver ship`: live old z 306.116 vs sim 308.028).
> - **The gap = the console's BAND-magnitude WALK-SPEED (the thing to model).** decomp: target speed
>   `dVar10 = msd^2*max` (setNormalSpeedF 2306); `mStickDistance = mMainStickValue` (setStickData
>   10569). For a band magnitude (0.889,1.0) the console's effective walk-speed differs from the sim's
>   `min(hypot/54,1)`->msd^2 model -- the SAME caveat precise-stop.md documents (held `(128,196)`:
>   console 15.76 vs sim 16.38). Only band AT CAP dips (`start1 (98,191)` is band but was bit-exact --
>   it is in the low-speed start crawl, still accelerating). Sessions 39/40 misdiagnosed it (MOVE-turn
>   / band-decode) by reading run_dtm's ±1-ambiguous per-frame log instead of the robust z-trajectory.
> - **OPEN SUBTLETY (recorded, not over-claimed): the probe (band after plain cruise) matched the
>   sim's dip, yet the ship (band after the ARC) shows live NOT dipping** -- an arc-carried hidden
>   state changes the console's band-speed response; not isolated. Doesn't change the fix. (dead-end #33.)
> - **Artifacts:** RED gate `tests/test_sheathed_roll_clip.py::test_sheathed_band_speed_at_cap`
>   (strict-xfail, corrected reason: band walk-speed, gf-aligned to the immutable jitterproof golden);
>   interim `solver.fine_family` band-exclusion (`_in_band`, `BAND_LO/HI`); `capture_decode.band_sweep`
>   (per-frame sweep -- but per-frame band reads are ±1-unreliable, use the stopped-position probe).
>   Suite **342 passed, 1 skipped, 2 xfailed** (unchanged count).
>
> **NEXT (Dereck's directive: model what the sim isn't modeling): resolve the RED gate by modeling the
> console's band-magnitude walk speed to f32.** Decomp-first from `setStickData`/`mMainStickValue` /
> `JUTGamePad::CStick::update` value near the cap; characterize the arc-carried context dependence via
> the DETERMINISTIC stopped-position probe **`harness.rollstab.capture_decode.transient_probe`**
> (`... capture_decode probe`; PROMOTED this session out of scratch -- it is the band-walk-speed
> measurement tool: sweep `holds=(1,2,3,4)` on a band stick at cap, the incremental stopped distance
> per added frame is the console's per-frame band speed). NEVER per-frame run_dtm reads for 1-frame
> events (±1-ambiguous; the `band_sweep` per-frame decode is flagged unreliable). Then
> REMOVE the `fine_family` band-exclusion so the solver can USE band sticks again (restoring the
> near-full-mag fine-perp density the band-free search lacks -- session 40's 0.0013u wall), re-solve,
> deliver. Every other thread (walk-stab clip, Tetra push-aside/turnaround, thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-14, session 40): the session-39 live blocker is RE-ROOT-CAUSED
> (jitter-immune) and it OVERTURNS dead-end #31. No sim code changed. The tried approaches did not
> deliver; the frontier is open.** Path 1 (the session-39 handoff's "try first") was run, then the
> blocker was re-measured jitter-immune. Done this session (offline + 3 live jitter-immune DTM captures,
> never advancewith):
> - **Path 1 (re-search for a deliverable pure-sim hit) did NOT find one in the structures tried.** A
>   pure LIVE-VALID search (every stick msd<=0.889 or ==1.0, avoiding the (0.889,1.0) band) reached
>   **~0.0013u from the f32 dust with 0 genuine hits over ~60k runs** (dense 2-knob vernier: arc + clean
>   fine + K3-crawl-3rd byte). The genuine dust is single f32 columns (~0.001u spaced, most z empty); the
>   live-valid lattices tried did not align onto one. This bounds the recipe SHAPES tried, not the clip.
>   (The `clean_settle` speedF-dip filter I prototyped is the WRONG filter -- a dip on a fine-ACTED frame
>   is live-faithful; reverted.)
> - **The row-18 blocker RE-ROOT-CAUSED, jitter-immune -> dead-end #31 was WRONG.** Using deterministic
>   game_frame tags (`fixtures/sheathed_roll_ship_jitterproof.json`) instead of run_dtm's jittery poll:
>   the stick DECODE is bit-exact live (held 8 frames, `(96,192)`->0.9605 == sim). But a **1-FRAME
>   TRANSIENT band stick** `(96,192)` (msd 0.9605, in the (0.889,1.0) band) decodes live to ~aim
>   (33295, msd 1.0 -- it holds the prior value) and does NOT turn; the sim decodes it raw (33367,
>   0.9605) and turns -> the row-18 divergence. Non-band 1-frame fines register correctly. The
>   two-angle chase is FAITHFUL; it is a TRANSIENT input-layer effect ("input-layer != /54", the freeze
>   planner already excludes the band). The session-39 "shape overshoot / MOVE-turn settle" reads were
>   run_dtm poll-jitter (live-row-19 poll caught the neighboring aim frame). dead-end #32 (corrects #31).
> - **The session-39 winning offline hit relies on the sim's transient-band mis-model, so THAT hit does
>   not reproduce live.** Its genuine landing depends on the sim treating the transient band stick as a
>   ~0.9605/33367 perp nudge, which live reads as ~aim. So a FAITHFUL transient-band model is needed to
>   make the sim predictive here; it removes that artifact rather than delivering THIS hit -- a new,
>   band-faithful solve is what delivers.
> - **Artifacts:** jitter-immune golden `fixtures/sheathed_roll_ship_jitterproof.json` (game_frame-
>   tagged, IMMUTABLE). Gate `tests/test_sheathed_roll_clip.py`: offline clip test GREEN (the solve is
>   real, in the sim), `test_sheathed_ship_matches_live` strict-xfail RED with the CORRECTED reason
>   (transient-band decode, not MOVE-turn). Suite still **342 passed, 1 skipped, 2 xfailed**. NO
>   `harness/rollstab/*.py` behavior changed (the exploratory `clean_settle` field was reverted).
>
> **NEXT (open approaches -- the clip is not solved yet; keep pushing):** (1) **model the transient-band
> input-layer behavior to f32** -- characterize it with a live band-transient sweep via
> **`harness/rollstab/capture_decode.py`** (the jitter-immune decode + two-angle capture tool promoted
> this session; `capture()`/`hold_decode()`/`ship`, RAM offsets + the run_dtm poll-jitter trap in its
> docstring): is a 1-frame band stick == the prior frame's value? a 2-frame slew? -- then make
> `main_stick_decode`/the input buffer reproduce it, so the sim is FAITHFUL and the solver searches over
> what live ACTUALLY does; then solve band-faithfully and deliver. (2) **expand the search** far beyond
> the shapes tried -- more knobs, longer
> crawls, other draw/arc placements, other A_proj phases, a warm-start off the walk-stab solver -- to
> close the last ~0.0013u to the f32 dust; the 0.0013u floor is a property of the LATTICES tried, so a
> richer input alphabet is the lever. (3) reconsider the delivery mechanics themselves (draw timing, B
> timing, the roll-entry frame) for degrees of freedom not yet exploited. Every other thread (walk-stab
> clip, Tetra push-aside/turnaround, thrust scanner) UNCHANGED.

> **CURRENT THREAD (2026-07-13, session 39): the sheathed roll-stab clip is SOLVED offline
> (pure-sim, from-rest, 0-ULP ship-gate PASS) but LIVE delivery is BLOCKED by a newly root-caused
> sim MOVE-turn facing-settle residual. Diagnosed to a single frame; RED regression added; NO sim
> code changed (Dereck's call: diagnose first).** This is session-38 NEXT (solve + deliver).
> Done this session (offline, plus 4 live DTM runs -- 1 ship + 3 diagnostic, never advancewith):
> - **SOLVE done.** A from-rest SHEATHED roll-stab genuine clip found ENTIRELY in the sim:
>   `old=(9072.2089844,308.0280762)` -> `new=(9069.8886719,258.8625793)`, disp 49.2202, CUT_F,
>   facing 33295, spF@A=17.0, sliver-robust (+-2e-4). `deliver.py gate` PASSES 0-ULP (dOLD/dNEW=(0,0),
>   genuine, clear, behind BOTH walls). Recipe (pure sim, seed-only): `A_proj=-500`, `draw_at=3`, a
>   K=2 crawl `((77,249),(98,191))` + arc `(9,(73,254),2)` + fines `(10,(99,183))`,`(4,(96,192))`,
>   `(6,(98,188))`. Found in **91 s** by a focused sweep warm-started from the same-seam idle13 recipe.
> - **LIVE ship FAILED -- root-caused by per-frame sim-vs-live diff (do NOT guess inputs).** Rows 0-17
>   of the ship stream (crawl, the row-3 draw B-edge, arc, fines) are **BIT-EXACT live** -- so delivery
>   alignment and `rest_noops` are correct. At **row 18** (an aim frame after the row-16 fine settles)
>   the SIM's `shape_angle` OVERSHOOTS to 33367 while live holds the settled 33295; that phantom
>   one-frame turn dips speedF to 15.05 vs live's 17.0 cap -> a **~1.9u along-track lag that freezes**
>   for the rest of the roll -> `old` lands off the f32 razor -> the CUT fires from the wrong spot (no
>   clip; live `new` is not behind the walls). The **drawn idle13 cached hit has the IDENTICAL row-18
>   overshoot**, so this blocks the roll-stab clip for BOTH anchors -- the cached idle13 hit appears to
>   have never been live-shipped through the current turn model.
> - **DISCRIMINATOR (Dereck's directive): it is a two-angle/MOVE-turn SETTLE residual, NOT an input-
>   delay/buffering shift.** Live shape+travel per frame (`0x136`/`0x12E`) vs the sim: `live[row r] ==
>   sim[row r]` on EVERY row except 18 -- live does NOT lead the sim by a frame (rules out the
>   pushaside-#3 class). The sim inserts one spurious facing value (33367) at row 18 that live never
>   has. Root is the `shape_angle` chase / `setMoveSlantAngle` settle after an arc+fine (README model
>   term #5; the Phase-R MOVE-turn frontier). dead-end #31 (NEW).
> - **Artifacts:** offline hit recorded to `_generated/rollstab_hits.json[0]` (gitignored);
>   live-golden fixture `fixtures/sheathed_roll_ship_live.json` (jitter-immune: shape+travel+pos per
>   row, first divergence row 18, IMMUTABLE); gate `tests/test_sheathed_roll_clip.py` -- offline clip
>   test GREEN (the solve is real), ship-vs-live test strict-xfail RED (the turn residual). Full suite
>   **342 passed, 1 skipped, 2 xfailed** (was 341/1xf). NO `harness/rollstab/*.py` behavior changed.
> - **Side finding:** `solver.search` is over-budget for the roll-stab -- at 200s it had not finished
>   drill level 0 for EITHER idle13 or sheathed (the dust cache under-samples the 1-f32-col-per-z
>   genuine set, mis-guiding the drill). The 91s find used a focused warm-start, not `solver.search`.
>   The <2-min pure-sim search is met by the focused path, not the generic drill as it stands.
>
> **NEXT (Dereck decides the branch; diagnosis is DONE): make the sheathed clip deliver live.** Two
> objective-compliant paths, neither started this session:
> 1. **Re-search for a CLEAN-SETTLE hit (no sim change):** add an acceptance constraint that the
>    from-rest approach holds speedF==17 on every cruise frame from the last intended turn through the
>    A press (reject any stream with a phantom row-18-type dip), then search for a deliverable sheathed
>    hit. Fast to try; open whether such a hit reaches the f32 razor.
> 2. **Fix the sim MOVE-turn model (decomp-first, the general fix):** find why `shape_angle` overshoots
>    one frame after an arc+fine (`setMoveSlantAngle`/two-angle settle, `d_a_player_main.cpp`) and model
>    it to f32 so any arc approach delivers 0-ULP -- flips `test_sheathed_ship_matches_live` GREEN. Per
>    the sim-change protocol: decomp-first, then live-confirm. Also fixes the drawn idle13 clip.
> Separately, fold the 91s focused solve into the harness as a reproducible <2-min sheathed solve.
> Every other thread (walk-stab clip, Tetra push-aside/turnaround, thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-13, session 38): the sheathed anchor's `REST`-not-bit-exact blocker is
> RESOLVED offline -- and it was NEVER the walk-entry foot-FK (session 37 was wrong). The sole cause
> was a one-frame walk-entry DTM-ALIGNMENT noop, which is the anchor savestate's emulator SUB-FRAME
> CAPTURE PHASE (not in-game). Now derived per-anchor; sheathed from-rest is BIT-EXACT; RED test flipped
> GREEN; 341 passed, locked goldens untouched.**
> Diagnosis (offline vs the s37 goldens + 2 paused-RAM probes; Dolphin up for the derivation):
> - **The FK poses are bit-exact.** With the 1-frame `mFootData` lag, every idle13 golden row matches
>   the sim 12/12 and BOTH sheathed WAIT frames match 12/12 EXACT. Session 37's `f312` "razor" mismatch
>   was an ALIGNMENT artifact -- it compared a sim MOVE frame against a live WAIT frame at the same
>   d=55.0, because the sim was one d-advance ahead. No FK residual.
> - **Sole divergence = WAIT->MOVE alignment.** By the jitter-immune d_frame clock, live sheathed does
>   3 WAIT d-advances then MOVE; the sim (REST_NOOPS=2) did 2. With **noops=1** sheathed is 0-divergence
>   on pos + m3598 + m359C at every d-aligned frame. idle13 needs 2 (breaks at 1); the two anchors
>   genuinely differ by one leading no-op.
> - **Proven a savestate CAPTURE-PHASE artifact, not in-game.** Loading each anchor paused + single-
>   stepping: idle13's first frame HOLDS d then advances; sheathed's advances immediately. idle13's hold
>   frame mutates ZERO player-RAM bytes (a pure re-display of a frame captured mid-execution); survives
>   load->save; a single advance destroys it; no player-RAM field flips it. idle13 = legacy MID-FRAME
>   capture (+1 spurious re-display -> noops=2); sheathed = `mint_current` BOUNDARY capture -> noops=1.
>   **noops=1 is the canonical standard** (clean mints + the future live-RAM UI feed all land there);
>   idle13's 2 is an artifact pinned to its locked golden.
> - **FIX (no hardcode, no re-mint, no refactor -- Dereck's call to keep noops=2 for legacy alignment):**
>   `mint.capture_rest` DERIVES the phase from its existing t1-advance (advances-until-`d`-changes) into
>   `seed['rest_noops']`; `rest.rest_state` reads it (default `REST_NOOPS=2` for legacy seeds, so
>   idle13/walkstab locked goldens stay bit-exact). Sheathed seed `rest_noops=1` (derived live).
>   `tests/test_sheathed_roll_rest.py` flipped xfail->PASS (d_frame-aligned vs the jitter-proof
>   `sheathed_walkentry_golden.json`). Full suite **341 passed, 1 skipped, 1 xfailed** (was 340/2xf).
>   dead-end #30 corrected. The FK model of #25/#28 stays genuinely open (session-25 slot-7 residual) --
>   it was simply NOT the sheathed blocker.
>
> **NEXT (the remaining LIVE increment -- the sheathed-roll milestone's "done"): solve + deliver.** The
> offline from-rest sim is now bit-exact for the sheathed anchor, so: `solver.search(anchor, draw_at=~3)`
> offline (<2 min; `draw_at` plumbing done s36) -> a from-rest sheathed roll-stab hit -> `deliver.py`
> clean DTM + live 0-ULP clip -> "done" = the scanner routes a not-drawn anchor's ROLL verdict end-to-end
> to a live clip. Verify the anchor jitter-proof with `capture_walkentry` (d_frame-aligned), NOT the
> row-indexed `rest.py` gate (which the run_dtm poll jitter can trip -- it misled sessions 36-37). Every
> other thread (walk-stab clip, Tetra push-aside/turnaround, thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-13, session 37): the sheathed anchor's `REST`-not-bit-exact blocker is
> RE-ROOT-CAUSED -- the session-36 diagnosis was a POLL-JITTER artifact; the real cause is the
> walk-entry foot toe-stream FK residual (dead-end #25/#28). No solver behavior changed; the fix
> (model the walk-entry foot poses to f32) is HANDED OFF to a dedicated session (Dereck's call).**
> Done this session (2 live runs, otherwise offline):
> - **Refuted session-36 lead (a) + dead-end #30's "extra idle frame" story.** Two run-free RAM reads:
>   the loaded idle bck `m_anm_heap_under[0].mIdx` is `BCK_WAITS` (0x126) at BOTH idle13 (drawn) and the
>   sheathed anchor -- the idle ARM is identical (only `heap[1]` differs, WALKS vs WALK = the modelled
>   `sword_drawn` walk arm), and both seed.jsons match live RAM. So `idle_anim='waits'` is correct.
> - **Jitter-proof measurement (`harness/rollstab/capture_walkentry.py`, NEW):** tag every live row with
>   the deterministic emulator frame (game_frame = emu - F0). BOTH anchors reach proc-MOVE at the SAME
>   game-frame (gf6) and the big walk step at gf8 -- the session-36 "3 idle rows vs 2" was `run_dtm`'s
>   row-0 fast-poll catching the two captures at different start frames.
> - **Real root cause = the walk-entry toe-stream `f312`, amplified by the 0.05 speedF clamp.** At the
>   sheathed idle phase (d~52.8) the sim's first-walk-frame toe delta is ~0.034 vs live ~0.060; the
>   decomp-faithful `_py_foot_compose` clamp (`speedF=0 if |spz|<0.05`) zeros the sim but keeps live ->
>   opposite sides of the razor -> ~0.8u accumulated over the m3598>0 blend frames (freezes when m3598
>   hits 0, same class as #25). PHASE-driven, NOT equip (forcing `sword_drawn`/`model_draw` -> ~0.003u).
> - **Ground-truth artifacts for the fix:** `fixtures/sheathed_walkentry_golden.json` (RED) +
>   `fixtures/idle13_walkentry_golden.json` (bit-exact reference) -- game_frame-aligned, raw mFootData
>   toe/heel + plant per frame. RED test `tests/test_sheathed_roll_rest.py` reason corrected (still xfail).
>   dead-end #30 corrected. Full suite unchanged (340 passed, 2 xfailed).
>
> **NEXT (Dereck's decision -- the objective-compliant frontier fix, its own session): MODEL the
> walk-entry foot poses to f32** so `posMoveFromFootPos`/`f312` is bit-exact from rest at ANY idle
> phase (fixes the sheathed anchor AND the session-25 slot-7 residual). Diff the sim against
> `sheathed_walkentry_golden.json` on the raw foot poses (aligned by game_frame), find where the pose
> delta drifts on the m3598>0 blend frames (the `plant` foot flips 0->1 at gf6 for sheathed but stays 1
> for idle13 -- likely a lead), and model it. THEN the sheathed anchor goes `REST BIT-EXACT` ->
> `solver.search(anchor, draw_at=~3)` (draw_at plumbing DONE session 36) -> `deliver.py` clean DTM +
> live 0-ULP -> flip `test_sheathed_roll_rest.py` green. Cheap first check: try a clean-provenance
> re-mint (lead b) before the FK model -- low odds but fast. Everything else UNCHANGED.

> **PRIOR THREAD (2026-07-13, session 36): started the LIVE sheathed-roll increment -- the
> `draw_at` solver plumbing + a full-seed mint tool + a minted sheathed anchor are DONE, but the
> anchor is NOT YET `REST BIT-EXACT` (BLOCKED on a walk-entry alignment; root-caused, RED test
> added).** This is session-35 NEXT #1. Done this session:
> - **`solver.search`/`check` now thread `draw_at`** into every `run` call (was the trivial-but-missing
>   plumbing session 35 flagged; additive, default None = byte-identical). `run` already accepted it.
> - **`mint.py` gained `mint_current(name)` + `capture_full_seed`** -- mint the CURRENT live paused
>   state as a fresh FULL-seed anchor (every field read from RAM, no base-seed inheritance), so an
>   equip change is mintable (`mint.py`'s translate path only shifts pos within a room). CLI:
>   `python -m harness.rollstab.mint current=<name>`.
> - **Minted `kaze_r11_rollstab_sheathed@twwgz`** at idle13's spot (equip-only change: load idle13,
>   press A while idle to put the sword away -> `mEquipItem` 0x100, settle, mint). Pos/facing (33328)/
>   csangle (29883)/state (4) identical to idle13; blend rates match (`d_rate` 1.1, `w_rate` 0.5867 --
>   the same WAIT/WALK arm). `rest.rest_state` auto-enables `model_draw` for it (sheathed => not
>   sword_drawn).
> - **RED regression `tests/test_sheathed_roll_rest.py`** (strict xfail) + live calib fixture
>   `fixtures/sheathed_rest_calib.json`. Full suite **340 passed** (unchanged), now **2 xfailed**.
>
> **THE BLOCKER (root-caused, do NOT re-derive):** the sheathed from-rest walk is NOT bit-exact. The
> sword-DRAWN idle13 IS (its gates are green), so it is NOT the code, NOT `sword_drawn`, NOT
> `model_draw` (forcing either changes the ramp by ~0.003u -- ruled out offline). **The sheathed idle
> takes ONE EXTRA idle frame before the WAIT->MOVE walk transition** (live: 3 idle rows k=0..2, MOVE at
> k=3; idle13: 2 idle rows, MOVE at k=2), so the sim's walk starts one frame early and every downstream
> row is off by ~one walk step (both still hit the same 16.98 cap). A single `REST_NOOPS` shift CANNOT
> fix it: that constant holds the idle-anim `d_frame` and the position TOGETHER, but live advances
> `d_frame` at k=2 while position stays at rest until k=3 -- a WAIT->MOVE / stick-delivery latency the
> drawn idle lacks. Two things to chase (see the session-36 handoff): (a) **the sheathed idle likely
> rests in a non-`waits` anim arm** (`rest_state` hardcodes `idle_anim='waits'`; the Phase-R risk the
> session-35 handoff flagged) whose transition differs by a frame -- verify the live idle anim ID; OR
> (b) **mint a clean-provenance sheathed savestate** (the current one was made via `advancewith`
> frame-stepping; a real-time `resume`/`setinput` sheathe was attempted but the idle A-press needs an
> EDGE that held-A / post-`clearinput` timing missed -- get the clean sheathe working, then re-check).
> NOTE the live DTM row-0 alignment is also jittery +-1 idle frame (`run_dtm` fast-poll), which muddies
> single-run diffs -- diff the STABLE structure (idle-row count before MOVE), not row-0 `d`.
>
> **NEXT (unchanged goal): make the sheathed anchor `REST BIT-EXACT`, then solve + deliver live.** Fix
> the walk-entry alignment (a or b above) so `rest.py` prints `REST BIT-EXACT`; then thread `draw_at`
> through `solver.search` (done) to solve offline (<2 min); then `deliver.py` clean DTM + live-gate
> 0-ULP, flipping `test_sheathed_roll_rest.py` green and replacing the synthetic-seed wiring test with
> a live golden. Everything else (walk-stab clip, Tetra push-aside/turnaround, thrust scanner) UNCHANGED.

> **PRIOR THREAD (2026-07-13, session 35): the SHEATHED ROLL PATH is WIRED offline + gated; the
> live mint/deliver is the remaining increment (deliberate checkpoint).** This is session-34 NEXT #1
> -- routing a NOT-DRAWN (sheathed) anchor's ROLL verdict to a roll-stab clip. Decision (Dereck):
> REUSE the kaze roll seam (S=(9069.904,259.199), F=33295) with a sheathed anchor, so NO geometry
> generalization is needed for this milestone -- only the draw wiring is new. **Done this session
> (OFFLINE, no live runs):**
> - `rest.rest_state(anchor, model_draw=None)`: defaults to `not sword_drawn`, so a SHEATHED anchor
>   auto-enables `LandState(model_draw=True)` (a drawn anchor stays OFF = byte-identical).
> - `solver.run(anchor, ..., draw_at=None)`: feeds a single B rising edge on approach row `draw_at`
>   (the mid-walk sword pull-out). With model_draw ON the draw completes before the A press, so the
>   roll routes to a CUT (`land/procs/roll.py:79` needs `sword_drawn`).
> - **Offline-proven end to end** (synthetic sheathed seed = drawn idle13 + equip forced sheathed):
>   draw-B@row3 -> `sword_drawn` flips at row8 (5 frames after the raw feed, matching the live-pinned
>   `f_draw`) -> foot set base->sword (`walk`->`walks`) -> speedF holds the 17 cap across the
>   phase-preserved swap -> A@row19 -> FRONT_ROLL -> **CUT_F fires**. The draw is LOAD-BEARING:
>   `draw_at=None` leaves the roll->CUT gate unsatisfied and NO cut fires.
> - Gate `tests/test_sheathed_roll_wiring.py` (4 green, OFFLINE); full suite **340 passed** (was 336),
>   1 skipped, 1 xfailed. Additive/backward-compatible: the existing drawn-anchor solvers are
>   byte-identical (both new params default to the old behavior).
>
> **NEXT (the remaining LIVE increment for this milestone -- checkpointed, not started):**
> 1. **Mint a sheathed roll-clippable anchor at the kaze roll seam.** Every existing roll anchor
>    (`idle13`, `mEquipItem=0x103`) is sword-DRAWN, and `mint.py` only translates within a room (no
>    equip change), so this needs a fresh live capture: place Link with enough run-up (draw + build to
>    cap + roll before the seam), sheathe the sword (`mEquipItem` 0x100), let the idle settle, save +
>    auto-capture the `rest_*` seed. A sheathed idle may rest in a different arm than `waits`
>    (`rest_state` models the `waits` arm; Phase R residual) -- verify `REST BIT-EXACT` (`rest.py`).
> 2. **Solve** offline (`solver.search` with `draw_at` threaded through; <2 min) -> a from-rest sheathed
>    roll-stab hit.
> 3. **Deliver** as a clean DTM + live-gate 0-ULP; replace the synthetic-seed offline test with a live
>    golden. "Done" = the scanner routes a not-drawn anchor's ROLL verdict end-to-end to a live clip.
> NOTE: `solver.search` does not yet thread `draw_at` into its `run` calls -- that plumbing is part of
> step 2 (trivial: pass `draw_at` through `run`/`check`; the offline path already accepts it).

> **CURRENT THREAD (2026-07-13, session 34): the MID-WALK SWORD PULL-OUT is MODELLED + live-gated
> 0-ULP.** This was the session-33 NEXT #1 (Dereck's directive) and it UNBLOCKS the scanner's ROLL
> dispatch for a not-drawn anchor. The sim froze the foot anim set (base WALK/DASH vs sword
> WALKS/DASHS) at `FootSpeedF` construction, so it couldn't represent a draw. **Decomp settled the
> OPEN question (no live breakpoint needed -- priority A):** the anim-set swap is an INSTANTANEOUS,
> phase-preserved pose jump with NO oldframe-morf -- `getAnmData` reselects the sword table the instant
> `mEquipItem` flips at the equip-anime completion (`d_a_player_main.cpp:3976`), `setMoveAnime`
> re-fetches it every frame (12734), and `procMove`'s steady `setBlendMoveAnime(-1.0f)` (6229) passes
> `i_morf < 0`; WALK/WALKS + DASH/DASHS share `frameMax` so the preserved phase `f31` leaves the frame
> value unchanged, only the legs swap. **Model:** `FootSpeedF.draw_sword()` flips `_walk`/`_dash`
> base->sword; `LandState(model_draw=True)` (opt-in; forces the pure-Python foot path -- native `_anmc`
> has no DASHS; default OFF = byte-identical) auto-triggers it `DRAW_DELAY=3` acted-frames after a B
> rising edge while walking sheathed. **`f_draw` = 5 frames after the raw B feed** (= 3 after the
> `INPUT_DELAY`-acted swordTrigger edge), live-pinned. **Live-gated 0-ULP:** capture
> `harness/rollstab/capture_draw.py` (`land_flatwalk`, sheathed `mEquipItem 0x100`; straight UP walk
> drawn at start via UP+B, then decelerated through the WALK<->DASH blend so the DASHS legs show on
> VISIBLE `m3598>0` frames); offline replay `harness/rollstab/validate_draw.py`; fixture
> `fixtures/walk_draw.json`; gate `tests/test_draw_switch.py` (5 green). The from-rest walk with the
> switch is 0-ULP vs live, and BOTH naive baselines DRIFT (never-draw stays DASH -> 1028 ULP off on the
> post-draw decel frames; always-drawn poses DASHS pre-draw -> 57 ULP), so the switch TIMING is
> load-bearing for the roll `old`. Full suite 336 passed (was 331; +5 `test_draw_switch.py`). The scanner /
> roll-stab / Tetra threads are otherwise UNCHANGED; the roll solver is not wired to `model_draw=True`
> yet (deferred with the roll-path solve).
>
> **NEXT (deferred to dedicated sessions):**
> 1. **Wire the scanner's ROLL dispatch to use `model_draw=True`** so a sheathed anchor draws mid-walk,
>    rebuilds to cap in the sword set, then A-presses to roll (roll->cut requires `sword_drawn`, which
>    `draw_sword` now sets on completion). Needs the roll-path solver (generalize `walkstab`/`solver` off
>    the hardcoded kaze seam -- see below), then a from-rest sheathed roll-stab delivered + live-gated.
> 2. **sword-OUT walk-stab live validation** (unchanged from s33): mint a sword-OUT anchor at a
>    walk-clippable seam + deliver/confirm live (`deliver` b_frame is already sword-aware, N-1 vs N-5).
> 3. **(optional) generalize the two solvers off their hardcoded kaze seam** (parameterize the settled
>    facing + crawl count from the seam bearing) so `thrust_scan.scan` can dispatch any enumerated seam.

> **CURRENT THREAD (2026-07-13, session 33): the CENTRALIZED THRUST-CLIP SCANNER is built (offline
> decision layer + dispatch), gated, and validated end-to-end.** `harness/rollstab/thrust_scan.py` is
> the front-end that, given an anchor seed + a target seam, DECIDES WALK vs ROLL vs INFEASIBLE and
> dispatches the matching existing solver (it does NOT rewrite them). The decision: the displacement
> floor `35/sin(interior/2)` sets the geometric tier (WALK <= 40.22, ROLL <= 49.22, else PUSH = actor
> push, out of scope), then a RUN-UP-SPACE feasibility gate simulates the straight approach from the
> anchor (`rest.rest_state`, C-down pin, per-frame re-aim at S) and requires the needed speedF (WALK:
> `floor-23.220`; ROLL: the 17 cap) to be built while `old` is still `>= floor` from the tip. FEWEST
> FRAMES wins -> prefer WALK when it fits the space, else ROLL, else INFEASIBLE(`push`|`space`). Gate
> `tests/test_thrust_scan.py` (9 green, OFFLINE): the four handoff cases (kaze walk seam -> WALK; kaze
> roll seam -> ROLL; a synthetic 90-deg seam -> INFEASIBLE/push; a close-start anchor -> INFEASIBLE/
> space) + tier boundaries + fewest-frames + dispatch. End-to-end validated: `scan(solve=True)` routes
> the walk seam to `walkstab.solve_focused` and reproduces the shipped clip's `old` (offline, 72.6s).
> `walkstab.deliver` is now sword-aware (B at N-1 sword-OUT vs N-5 sheathed; backward-compatible with
> the shipped golden). The Tetra-push / roll-stab threads remain PAUSED.
>
> **NEXT (deferred by Dereck to dedicated LIVE sessions):**
> 1. **MODEL the mid-walk sword pull-out (Dereck's directive 2026-07-13, session 33).** For a
>    NOT-DRAWN anchor the sword must be pulled out mid-walk, and the sim can't represent it: the foot
>    anim set (`_walk`/`_dash` -> WALK/DASH vs WALKS/DASHS) is frozen once at `FootSpeedF` construction
>    (`anim_state.py:170-171`), a STATIC flag. The current walk-stab escapes this only by construction
>    (B at N-5 times the draw to complete AT the cut, so no walk frame is posed in the sword set --
>    decomp `d_a_player_main.cpp:3975-3976` flips `mEquipItem` -> sword at the equip-anime completion
>    frame, and `getAnmData` keys the leg set off `mEquipItem`). It BREAKS for the ROLL path from a
>    sheathed anchor: the roll->cut trigger REQUIRES `sword_drawn` (`land/procs/roll.py:79`), so Link
>    must draw BEFORE the A-press then rebuild to cap in the SWORD set (DASHS != DASH, session 31), and
>    those frames drift. Model = make the foot anim set SWITCHABLE at a draw-completion frame `f_draw`
>    (from the B-press + equip duration: item put-away `field_0x20`/`0x30` then take-sword at 7.0; an
>    on-back sword is just the take at 7.0). OPEN, needs a live breakpoint: does the `mEquipItem` swap
>    trigger an oldframe-morf, or is it an instantaneous leg-pose jump (DASH/DASHS share frameMax 32 ->
>    rates match, so likely instantaneous -- VERIFY, don't assume). Then live-capture a mid-walk draw
>    (sheathed -> draw -> keep walking), per-frame diff to pin `f_draw` + confirm 0-ULP after, add a
>    live regression. This BLOCKS the scanner's ROLL dispatch for any not-drawn anchor.
> 2. **sword-OUT walk-stab live validation.** The B-frame code is in (`deliver` derives N-1 vs N-5 from
>    the anchor equip); what remains is minting a sword-OUT anchor at a walk-clippable seam (an equip
>    change at capture -- `mint.py` only translates within a room) and delivering + confirming live,
>    same rigor as the sheathed one.
> 3. **(optional) generalize the two solvers off their hardcoded kaze seam** (the scanner dispatches by
>    seam match today; a new-seam solve needs the settled facing + crawl count parameterized).
>
> **PRIOR THREAD (2026-07-13, session 32): the pure-sim WALK-STAB seam clip is DELIVERED LIVE, 0-ULP,
> no calibration -- the objective is MET for the walk stab.** A `solve_focused` hit found ENTIRELY in the
> sim shipped as a clean DTM and clipped the kaze r11 slot-3 seam (S=(9030.955,1385.858), poly 803x802,
> interior 168.97deg): the CUT_F fired at N=13 with `old=(9011.2773438,1352.7379150)` and
> `new=(9031.8212891,1387.3160400)` -- **BIT-FOR-BIT the sim's from-rest prediction** -- the clip is
> genuine, and Link went OOB (proc 0x24, `pos_y` below the floor) THROUGH the seam (Dereck confirmed OOB
> on screen). Anchor `tests/dolphin/anchors/kaze_r11_walkstab@twwgz.sav`; live golden
> `tests/golden/walkstab_deliver.json`; gate `tests/test_walkstab_clip.py` (xfail flipped -> PASS).
> Mechanism + disp-floor in KB `knowledge/mechanics/walk-stab.md`. The roll-stab / Tetra-push state below
> is PAUSED (same solver shape).
>
> (Session 32's "NEXT PHASE = a centralized thrust-clip scanner" is DONE -- see the session-33 thread
> at the top of this Status.)
>
> **SESSION-32 FINDINGS (the load-bearing ones):**
> - **The blocker was NEVER throughput -- it was distinct-old DENSITY near the razor perp.** The
>   acceptance perp razor (~2e-4u) is a GAP in the reachable-`old` byte lattice at K<=2 crawls: an offline
>   sweep floored `min|perp|` at **~1.3e-3u (~13x the razor)**. So the legacy `solve()` (CRAWLS K<=2 +
>   collapsing knobs) finds **0 hits even given the full 110s budget** -- speeding it up cannot help. The
>   fine knobs it leaned on (bearing arc `off`, the arc-frame byte nudge) are FULL-MAG sticks that
>   octagon-CLAMP, so they collapse (52k streams -> ~14 distinct near-razor `old`).
> - **The fix = a K=3 START CRAWL.** Each crawl frame densifies the perp lattice ~20x (K=1 ~0.03u -> K=2
>   ~1.3e-3u -> **K=3 ~2e-5u**, reaching the razor). The fine perp knob is the 3rd crawl frame's BYTE
>   nudge -- a PARTIAL-mag stick sits in the octagon INTERIOR, so every byte is distinct (unlike the
>   clamped full-mag arc). `solve_focused` (session 32): Phase A brackets `|perp_ray|` coarsely (cheap, no
>   CrrPos), Phase B drills the byte-nudged 3rd frame + tests EXACT `genuine_clip`, Phase C re-sims WITH
>   walls and accepts only `wall_hit==False` (rejecting the dead-end #28 wall-overshoot artifacts). It
>   found **3 wall-faithful genuine hits in 67s** (< 2 min); the top clipped live 0-ULP.
> - **RIGOROUS MULTI-POSITION VALIDATION (Dereck's ask): 3/3 distinct `old` positions clip live 0-ULP.**
>   Delivered three different positions around the seam (d2S 37.80 / 38.52 / 38.91; `old_x`
>   9011.08..9011.65), each `old`/`new` bit-for-bit its sim prediction, each genuine + OOB (proc 0x24,
>   `pos_y` below the floor). The DELIVERABLE window is a narrow **~1u band at d2S~38**: closer to S the
>   walk brakes on the seam wall pre-cut (the wall-faithful gate bounds it), farther the lunge cannot
>   reach. Within it the pipeline is reliable. Fixture `tests/golden/walkstab_positions.json`, gate
>   `tests/test_walkstab_clip.py::test_walkstab_multiple_positions_clip`.
> - **Dead-end #28 RETIRED at the premise.** "The walk-entry foot residual eats the razor" was the
>   session-31 sword/anim-set bug (already fixed); with the from-rest sim 0-ULP, any genuine offline clip
>   is a TRUE one-shot and the search's `old` IS the live `old` bit-for-bit. The margin-5 hit delivered
>   cleanly (0-ULP leaves no residual for the margin to absorb).
> - **The search speedups (all bit-exact-validated, committed):** module-cached cut anim (killed a
>   per-clone pyproject root-walk; `enter_cut` ~8.5x), `fast_cut` (cached constant CUT_F lunge, ~20x vs
>   `enter_cut`, 0-ULP over 378 snapshots), `FootSpeedF.skip_cruise_pose` opt-in flag (skip the cruise
>   foot pose -- 0-ULP for walk-then-cut over 1944 streams), and **memoized `stick_for_bearing`** (the
>   dominant win: 20M redundant `main_stick_decode` calls eliminated). Search 105 -> ~1340 streams/sec;
>   `run_dtm` now logs `pos_y` (the OOB/fall detector).
> - **Shipped this session:** `solve_focused` + `fast_cut` + memoized sticks in `harness/rollstab/walkstab.py`
>   (legacy `solve` kept as `solve_legacy`); `deliver` rewritten (explicit-sticks replay, OOB detection,
>   golden save); `cut.py` module anim cache; `foot_speedf.py` `skip_cruise_pose`; `run_dtm.py` `pos_y`;
>   `tests/golden/walkstab_deliver.json` (NEW live golden); `tests/golden/walkstab_positions.json` (the
>   3 live-confirmed positions); `tests/test_walkstab_clip.py` (gate PASS + from-rest re-sim + the
>   3-position guard).

- **WALL-BRACED CLIP TRIED LIVE -> INFEASIBLE on slot 7 (session 27, dead-end #27); NEXT = simulate
  PUSHING Tetra onto a genuine coord.** Drove the full live braced pipeline (perp-shifted Link start ->
  measured entry -> solved braced Tetra at (-1652.293,-940.256), fB=50 ON wallB -> deliver -> per-frame
  diff). Link's roll was BIT-EXACT but Tetra DRIFTED off the wall before it: the deep-corner brace spot is
  ~220u from Link, so the speed-building away-walk crosses her 230u follow threshold (peak 249u) and she
  flees; the cut wall-pinned short (no clip). Full roll + seam-reach + follow-safe cannot coexist (#27) --
  bracing is incompatible with the FOLLOW clip because follow breaks it (might work on slot 6's glitched
  no-follow Tetra; untried). **The shipped free-floor clip is UNCHANGED / still live bit-exact.**
  - **Genuine-placement list shipped: `_generated/tetra_placements.tsv`** (288 float-exact Tetra (x,z) at
    the session-24 working entry, step 0.004, with new/dist_wallB/dist_wallA/on_target/against_wall).
    Any row clips; none are against the wall (closest 56.98u -- the working entry's thread doesn't reach
    wallB). Regenerate: `_notes/scratch-session27/gen_placements.py`.
  - **NEXT (real-TAS positioning): simulate PUSHING/HERDING Tetra onto a genuine coord** -- you can't
    memory-write her in a TAS. Link's levers (all modelled + live-gated 0-ULP): FOLLOW
    (`core.npc_zl1.Zl1FollowState`), CC contact push (`cc_push`/`cc_stepper.CcCoupledStepper`), BG
    WallCorrect. Build a herding driver (Link inputs -> Tetra final f32 (x,z)) + search maneuvers that
    land her on a genuine spot; genuine test = `turnaround.search`/`ShoveCtx.sweep_par`. Open question:
    the coords are f32 slivers -- is Tetra's arrival f32-controllable by physics? See the session-27 handoff.

- **TETRA-PLACEMENT PRECISION CHARACTERIZED (session 26, SIM-ONLY): the genuine set is a thin
  CONNECTED THREAD, not a lottery point and not a fat band.** At the FIXED live-measured slot-7 roll
  entry `(-1516.116455078125, -765.1473999023438)` facing 40835 m351C 0, an offline f32 sweep
  (`ShoveCtx.sweep_par`, region located via the smooth behindA/behindB pre-CrrPos ridge then
  column-chunked f32 scans -- streaming to dodge the wide-grid OOM; ~66k sims/s) maps the genuine
  Tetra START placements to a **~46u thread** along a ~59deg-from-+X diagonal (slope dz/dx~1.67,
  x[-1651.7,-1628.1] z[-933.3,-893.2]), **meandering +-~2u** (RMS 1.14u off a straight fit -- follow
  the thread, never fit a line). Perpendicular it is **~8 f32-ULP thick (median ~4.9e-4u, range
  1-16 ULP)**; ~**84%** of consecutive f32 x-columns carry a genuine sliver and adjacent slivers
  overlap/touch (a CONNECTED thread, unlike kaze's disjoint per-column stripes). The landing `new`
  drifts ~0.001u along the thread (12 f32 values); the shipped target `new` is bit-exact only on a
  ~1-2u sub-segment, but ANY thread point clips (Link falls). **Verdict for the TAS:** ~46u of
  along-slack, but ~f32-precise (~5e-4u) perpendicular -- a targetable line, not a point.
  Full numbers + method on the KB page [[seam-clip-solver]] ("Tetra-corner placement" section).
  - **Dereck's wall-brace question, FULLY answered: Tetra can be braced on wallB but there is NO slide
    RANGE -- bracing only removes ONE coordinate, and this is fundamental.** Shifting the ROLL ENTRY
    (perp- ~-1.3u) walks the thread's corner-ward tip exactly onto the wallB brace locus (fB=TET_R=50,
    z=-940.25562 -- verified: deeper placements CrrPos-eject there, so fB=50 IS the wall), and
    braced-genuine placements exist (`new` bit-exact). BUT the along-wall window = thread-thickness
    (~5e-4u) / sin(crossing angle), and: **wallB is crossed near-PERPENDICULARLY** (local thread angle
    75-82deg at the brace point; swept facing 40805-40880, never rotates parallel) -> window only
    **2-3 f32-ULP (~0.0002u)** -- a point, so x still needs f32 precision (2D-f32 -> 1D-f32). **wallA
    (near-PARALLEL, the wall that could give a range) is UNREACHABLE** -- the thread's tip pins at
    x~-1650 (fA~76) at every entry tried (9 directions), ~25u short of the wallA brace (fA=50), an
    acceptance-geometry limit. So no Link knob (position, facing) opens a range. Untried long-shots:
    curved walk-up (`m351C` lean) + thrust timing (tip pin looks geometric -> low expectations).
    Numbers + method on KB [[seam-clip-solver]] "Wall-brace"; session-26 handoff has the tooling.

- **THE CLIP IS UNCHANGED AND STILL LIVE + BIT-EXACT (session 24, below).** Session 25 attempted the
  optional pure-sim polish (compute the roll entry from the slot-7 rest seed instead of measuring it)
  and ROOT-CAUSED the residual but did not close it -- the clip's shipped status is untouched (it still
  seeds at the MEASURED live entry, exactly as the pushaside clip does).
  - **From-rest slot-7 DOWN-walk residual ROOT-CAUSED (session 25), left open by choice.** The
    computed-from-rest entry lands ~**2.54u** NE of the live entry. Diagnosed by per-frame diff of the
    seeded sim vs a rich live walk trace (`_generated/turnaround_walk_trace.json`), and it is NOT what
    the session-24 handoff guessed ("seed_rest_blend + deferred-draw class"):
    - **Proc/frame alignment is PERFECT with `noops=0`** (NOT the kaze `REST_NOOPS=2`): WAIT f0-f2 (no
      move), MOVE f3-f8, roll entry f9 -- bit-identical frame numbering to live. The slot-7 idle
      genuinely RUNS procWait each WAIT frame (the WAIT/WALK blend advances d 17.80->18.20->18.60,
      w +0.674/frame); it is NOT the "game hasn't run yet" alignment-noop regime kaze modelled.
    - **The WAIT<->WALK blend `m3598` matches live BIT-EXACT** (0,0,0,1.0,1.0,0.7647,0.3529,0,0) and
      **`nspeed` ramps cleanly** (+3.5/frame to the 17 cap). So the accel integrator and the blend
      weight are already right.
    - **The entire error is in the foot toe-stream `f312`** (`posMoveFromFootPos`, `_py_foot_compose`)
      on the THREE walk-entry frames where `m3598 > 0` (f3-f5): there `speedF = nspeed*(1-m3598) +
      f312*m3598`, and the sim's `f312` is low (f3 0.068 vs live 0.105; f4 1.42 vs 2.15; f5 2.42 vs
      4.62). Once `m3598` hits 0 (f7+) `speedF == nspeed` and the two agree exactly, so the 2.54u
      freezes and never grows. Live's RAM `m359C` column IS this `f312` (0.105, 2.146, 4.618, ...).
    - This is the **same foot-FK-precision residual class as the Phase-R late-roll-pose drift**
      (jointBeforeCB MOMI body-lean / the walk-entry oldframe-morf toe stream), NOT a proc or blend
      bug. Closing it means modelling the walk-entry foot poses to f32, not re-seeding. Deferred: the
      clip does not need it (measured entry is 0-ULP live), and it is orthogonal to the Tetra-precision
      question the next session answers. Regression captured as the live trace fixture above; no RED
      test added (the finding is recorded here + in the handoff instead).

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
