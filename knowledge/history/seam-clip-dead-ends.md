# Roll-stab seam-clip dead ends (sessions 4-9, 2026-07-09/10)

> **status: historical** - research log / dead ends, NOT current truth. The current pipeline and
> run protocol live in `harness/rollstab/README.md`; the methodology in
> [strategy/seam-clip-solver.md](../strategy/seam-clip-solver.md). This page consolidates the
> approaches that were TRIED and RULED OUT while planning a roll-stab clip through the kaze room-11
> 110-degree seam, so the next session does not repeat them. Append new dead ends here as they occur.

Context: the goal is a PURE-SIM one-shot (given a fixed anchor + a target seam, compute the input
sequence, no live round-trip in the loop), DTM-verified, under 2 minutes. Most of these failures come
from either fighting the razor with the wrong knob, or trusting a sim result that a live run then
contradicted. Read alongside the "Dead ends" list in the README (this is the fuller version).

## A. Delivery and validation (permanent rules)

1. **`advancewith` for off-axis sticks is wrong.** It mis-injects near-full OFF-AXIS sticks (~+-160
   s16). It caused the G1 facing confusion (advancewith read 33353 while the sim decoded 33295); a
   walk-only DTM confirmed the SIM was right and advancewith was the artifact. Validate AND deliver any
   aimed/off-axis sequence via clean DTM only, NEVER advancewith. Off-axis + advancewith is
   deterministic from a fixed savestate (fine for a one-off demo) but is NOT portable. See the
   `advancewith-offaxis-stick-artifact` memory.

2. **Teleport / position-feedback tuning as the delivery method: REJECTED (user).** The final product
   is one-shot from a fixed anchor, no teleport, no position feedback. Related placement gotcha: writing
   ONLY the debug pos globals leaves `pm_old_pos` behind, so the next CrrPos sweeps a long line and
   snaps Link ~100u away (spurious BLOCK). If you ever place for a check, write BOTH player class-pos
   triples AND the link globals (the `teleport` CLI does this) and feed FULL f32 precision (3-decimal
   rounding flips CLIP to BLOCK).

## B. Sim-artifact traps (looked like a clip, was not)

3. **Session-4's 42-frame `genuine_clip` was a SIM ARTIFACT.** The sim had no wall collision in the
   roll approach, so it rolled Link straight THROUGH the corner wall to an unreachable `old` (z~278);
   the live wall blocks the roll ~26u short at z~304. The plan targeted a position that cannot exist.
   Lesson (now enforced in the pipeline): every candidate must clear the walls on EVERY roll frame, and
   `old_z` must sit in the reachable band (kaze r11: ~[302.6, 308.2]).

4. **Session-6's collision-free clip was a SIM ARTIFACT of the naive stick decode.** It was found
   before the PADClamp octagon clamp landed; replaying the same sequence under the fixed decode shifts
   `old` ~1.06u (9072.04 to 9073.10) and it no longer clips. Lesson: the decode is the octagon-clamped
   one now (`core.mathlib.main_stick_decode`). Any pre-fix "hit" must be re-verified under the current
   decode before it is trusted.

5. **A scan "negative" from the wrong window proves nothing.** Session-5's `check_blocked_clip.py`
   reported "no clip" but was sweeping the wrong `old_x` window at the wrong facing; the real
   clip-capable `old` was elsewhere (session 6 found 93 collision-free clips at that corner). Do not
   certify a corner unclippable from a scan unless the window AND facing are correct.

## C. Search-strategy dead ends

6. **Naive constant-stick single-ray one-shot at the 110-degree corner: INFEASIBLE (hard table
   limit).** The position integrator's `>>4` cos/sin table has only 4096 directions, which quantizes the
   roll-line direction, so rho (perp offset to the corner) is quantized to ~1.15u steps here; the
   ~0.037u clip window falls in a 1.15u gap (nearest reachable rho misses by ~0.009u). This is a table
   limit, not stick-byte or sim precision: closing other sim gaps does not help. NOTE 14/88 room seams
   ARE single-ray hittable (wider windows). For a gap target you need a DENSER lattice (start-crawl
   low-speed frames or mid-walk knobs), not a single ray.

7. **Two-segment pursuit walk (fixed-F perp knob): does not cross the razor.** rho quantizes to a
   coarse global tread lattice with a dead band sitting exactly over the window; partial-msd endgame +
   neutral creeps + large (26k-run) sweeps never crossed it. Fixed-F pursuit knobs are the wrong tool
   for the perp match.

8. **Ribbon-fit / |g| minimization targeting: wrong model of the acceptance region.** The genuine set
   is f32 DUST (striped slivers per f32 x-column), not a ribbon or centerline, so being 1e-4 from a
   fitted line says nothing. Always test the EXACT f32 candidate (the real `enter_cut` lunge; `new` ==
   `f32(old + lunge)` bit-for-bit).

9. **Anchor-z transfer aiming / aiming `dz` at a sliver: lands chaotically.** The live m359C reseed
   flips the A-press frame, so trying to aim a minted anchor's `dz` at a known sliver does not land
   there. Pick a FRESH arbitrary `dz` per anchor (each is an independent lottery draw of the reachable
   manifold against the dust); do not try to aim it.

10. **Turnaround-clip coarse knobs (integer n_walk / discrete stick aim / integer thrust, Tetra
    fixed): 0 genuine even at the shipped Tetra spot (session 23-24).** The acceptance is f32 dust; the
    ONLY fine knob is Tetra's f32 placement, solved at the exact roll entry. Also **octagon-VERTEX
    turnaround aim** (stickY=255) reaches only facing 40758/40913 -- outside the ~40842 seam-gap window,
    so `new` is wall-pinned ~49u short at EVERY placement; a **DIAGONAL** stick (108,204)->40835 is
    REQUIRED to thread the corner gap (retry a vertex aim only if the camera csangle changes).

11. **Coarse-locate the genuine Tetra region via min(new-to-seam): FAILS -- no gradient (session 24).**
    The clamped `new` is ~49u (blocked) or ~0.5u (clipped) with nothing between, so there is no ridge to
    descend. BUT the engine's UNCLAMPED-endpoint plane distances DO give a smooth ridge: `sweep_par`
    out[8]/[9] = `behindA`/`behindB` (signed dist of the pre-CrrPos predicted endpoint behind each seam
    wall). Coarse-scan those to bound the behind-both region, then fine-scan (step ~0.008) only there --
    a blind fine-scan of the whole approach corridor blows the 2-minute budget. This is how the
    session-24 live clip's placement was located at the measured entry.

## D. Calibration / anim-state dead ends (relevant to killing the live calibration)

10. **Per-move-set bias correction: not transferable.** The anim-phase bias is arc-dependent (0.09u on
    one arc vs 2.6u on another), so a single correction does not carry across move classes; it would
    need one live run per class. This is the drift path that grew into the live calibration step. Do not
    extend it; model the anim state instead.

11. **A from-rest roll as an anim-reset canonicalizer: does not resync.** A roll out of the idle/yawn
    does NOT wash the cold-start anim mismatch back to a canonical phase; it diverges from frame 1. It
    cannot be used to sidestep seeding the true idle-entry anim state.

## E. Mechanic constraints (real, do not chase)

12. **Aiming the thrust more than +-0x2000 (+-45 deg) off the roll facing dispatches CUT_L / CUT_R** (a
    different, weaker move), not the forward lunge. Documented dead end; do not chase it for the big
    clip frame. To steer the 49.22 lunge you must AIM THE ROLL, not the thrust.

13. **The camera cannot be forced behind Link in kaze room 11.** `cam_yaw` writes are clobbered by the
    integrator each frame (forcing them diverges facing); C-down drifts csangle to an unpredictable rest
    (~13-27 deg off); a full-up "camera-behind" roll goes off-course and bonks. Aim the STICK
    (`stick_for_bearing` at the stable csangle), do not fight the camera.

14. **speedF must be 17.0 at the A press (hard gate).** A sub-cap walk gives a sub-26 roll and a shrunk
    lunge that never reaches behind the seam planes. Gate it everywhere; it is not tunable down.

## K0 mid-run calibration + the "anchor lottery" (sessions 8-9; superseded session 10)

Pinning the sim to one live run at a mid-cruise row K0 (position + fc phases + m359C/m35B4 + a
re-posed toe stream) verified bit-exact on the CRUISE -- but at cap m3598 == 0, so the cruise
exposes none of the pose-dependent state, and the calibration silently left it sim-derived. Dip
frames (m3598 > 0) then consumed wrong poses and shipped hits missed live by ~0.3u; each anchor
looked like an independent "lottery draw". Session 10 replaced it with the from-rest exact model
(rest-blend seeding + stored mFootData poses + end-of-frame draw pos + world Y + turn lean +
dtm_make's 255->254 delivered-byte calibration) and the "lottery" vanished: the first robust hit
shipped clipped live 0-ULP. Lesson: a calibration verified only on a regime that HIDES state is
not a calibration of that state.

## The FRONT_ROLL Co-centre residual is the BASE LEAN, not the oldframe-morf (session 16)

The session-15 push-frame drift was blamed on `body_cyl.roll_co_center` carrying the FRONT_ROLL
**oldframe-morf** transient (supposedly bit-exact only after roll frame ~11), with the fix being "model
the morf". **Ruled out by a live capture** (`harness/rollstab/capture_roll_lean.py`, logging mCyl centre
+ `mBodyAngle` + `m34F2/m34F4` per roll frame): the roll's `i_morf` is `mRoll.field_0x14 = 2.0`, so the
oldframe-morf blends **roll frame 0 only** -- it cannot be the frames-1..11 residual. That residual is
the missing `setWorldMatrix` base `ZXYrotM` z-tilt by `shape_angle.z` (the MOVE turn lean `m351C>>1`,
decaying ~35%/frame): a curved approach carries a nonzero lean into the roll (`mBodyAngle.x=y=0`,
`m34F2=m34F4=0` throughout; only `mBodyAngle.z==shape_angle.z`), and the clean lean-0 pose is off by it.
Feeding the previous frame's `shape_z` to the base is 0-ULP on every settled roll frame; the
`jointBeforeCB` body_chn rotation contributes nothing to the root/neck xz midpoint (adding it breaks
it). Lesson: capture the actual per-frame quantity before attributing a residual to a plausible
mechanism -- two mechanisms with different timescales were conflated. Do NOT build a morf driver for the
push frames; the morf still owns roll frame 0 only (out of push scope).

## Tetra push STAGING: corner-brace and colinear-behind are both WRONG (session 19)

THREE Tetra stagings for the (-1727,-990) corner clip are ruled out (#15 corner-brace, #16 colinear-
behind, #17 stationary behind-Link). The correct staging is STILL OPEN (session-19 handoff): the push
must point toward the seam (so Tetra behind Link), but a stationary behind-Link Tetra gets plowed, so
some form of BRACING or timed placement is needed. NOTE `co_move_pair`/`cc_stepper._cc_check` reproduces
the golden push STATICALLY, but that is not the dynamically-reachable push (see #17).

15. **Corner-BRACED Tetra pushes the WRONG WAY.** The sessions-15..17 captures teleport Tetra INTO the
    corner and roll Link in; her push then points AWAY from the seam (she shoves Link out of the corner),
    so it cannot close a clip that needs ~0.75u ADDED toward the seam. Those captures were wall-BLOCKED
    and only ever validated the CC frame ORDERING (push consume -> m34C2 lunge -> CrrPos), never a
    clip-through. The corner-brace is stable (WallCorrect holds her) but geometrically wrong. The clip
    needs Tetra BEHIND Link (push toward the seam) -- but a *stationary* behind-Link Tetra is itself
    ruled out, see #17.

16. **Colinear-behind Tetra (push along the roll facing F) does NOT clip -- the STEER matters.** Placing
    Tetra exactly opposite the lunge (along -F) gives a push along +F (224.53deg), but the needed push
    bearing is ~235deg (~11deg off F): the ~0.75u must STEER `new` sideways onto the seam vertex, not
    just extend the lunge. So the Tetra placement is a 2D f32 knob, not a 1D distance
    (`tetra_clip.solve_min_overlap`'s colinear-behind placement fails for the real thrust; [[tetra-push-model]]).

17. **Stationary behind-Link Tetra CANNOT deliver the push -- she gets PLOWED (session 19).** An earlier
    draft claimed a stationary idle Tetra behind Link (within the follow radius) would deliver the push as
    her anim Co centre sweeps the overlap. The DYNAMICS refute it (`scratchpad/proto_dynamics.py`,
    `confirm_plow.py`): because the needed push is only ~11deg off the roll line (#16), the delivering
    Tetra sits ~15u from the line -- exactly where Link's rolling Co centre travels -- so the roll-in
    PLOWS her over ~8 frames with large (3-12u) chaotic pushes and flings an un-braced Tetra ~40u away
    before the cut frame; the CUT_F then fires with zero/wrong push. Link's FRONT_ROLL Co centre LEADS the
    feet toward the corner (away from a behind Tetra), and its wall-pinned sweep never gives a clean single
    ~1.5u graze; a tangential (side) graze gives a ~90deg-wrong (pure-lateral) push. "Forward push" and
    "off the roll path" are mutually exclusive here. The only dynamically-controlled push is Link plowing a
    BRACED Tetra -- so the open staging must BRACE her (on the behind side, if geometry allows) or use a
    timed placement, and acceptance must be the DYNAMIC coupled cut, not the static `co_move_pair`
    predictor `solver_tetra`/`test_tetra_solver.py` uses.

18. **Fast bare-centre push predictor is INVALID for the coupled Tetra clip (session 20).** A cheap solver
    that precomputes Link's roll Co-centre trajectory ONCE (Tetra-free) and then rolls only Tetra's shove per
    candidate placement (the freeze-solver pattern) does NOT work here: the CC push perturbs Link's FEET
    substantially (live: his roll z lagged -910 vs the bare -955), so his Co-centre is NOT Tetra-independent.
    Only the FULL coupled sim (`cc_stepper.CcCoupledStepper`) is faithful. Corollary confirmed live 0-ULP on
    slot 6: the un-braced shove + roll-stab CUT_F entry are bit-exact, so the substrate is trustworthy -- but
    a 460-placement sweep at a FIXED roll timing found 0 genuine (closest `new` pins ~35u short of the seam;
    the seam-ward push and a full lunge from the golden `old` are mutually exclusive under a movable Tetra's
    plow, restating #15-17 with coupled data). NOT proven across all roll timings / roll angles -- the search
    is blocked on coupled-sim SPEED (~1.3s/sim, 99% in `acch_crr_pos` over all 765 walls; needs the Phase-W
    wall cull + precomputed roll/cut tables before a timing x placement sweep is feasible).

19. **[RESOLVED session 22 -- the push-aside CLIPS LIVE, bit-exact. Kept only as the record of why the
    session-21 slice was empty.]** A THIN plow-staging slice came up empty (session 21) -- the push-aside
    itself was never ruled out.
    With the exact >=100k sims/sec engine (`tww_sim/core/_shovec`), 13M+ coupled sims over placement
    x[-1725,-1600] z[-1000,-860] x thrust steps 13/14/15 x placement steps found 0 genuine -- but ALL of
    it at ONE Link approach line, ONE roll-entry point, ONE roll angle. ~98% of un-walled cut endpoints
    are already BEHIND the seam plane, so the razor is the CrrPos block, and in THAT slice no
    plow-perturbed `old` landed on a threading sliver. Dereck's correction (21b): the push-aside is the
    REQUIRED mechanism (a mid-run Tetra placement is a hack) and manual testing has produced a 50.6u
    displacement with a bad angle/position (>= the ~49.99 the clip needs) -- so the lesson is scope, not
    impossibility. Retry WITH the wide knobs: roll timing / Link entry point (`link_x0/z0`), lateral
    placement, finer + wider Tetra initial positions (`placed_step=0`), thrust timing, roll angle.

20. **Transferring a threading push between different `old`s (session 21).** The session-18 golden push
    (-0.618,-0.427) does NOT thread from the straight-roll wall pin (`pred_genuine(pin, golden)` False):
    the acceptance slivers are a function of `old`'s exact bits. Search pushes per-old (the polar graze
    sweep over the FULL angular range, 0.05 deg x 0.002u depth); never re-aim a known-good push at a new old.

## The four things that made the push-aside miss LIVE (session 22 -- all fixed; do not relearn)

The push-aside clip is SOLVED and live-confirmed bit-exact (README `## Status`). Getting there burned a
lot of live runs on four traps, each of which LOOKED like "the sim is wrong" and was not:

21. **A Tetra spot that is not on WALKABLE FLOOR.** The coupled sim clamps Tetra to the flat ground plane
    everywhere and never models her FALLING, so it will happily "stand" her behind a wall and report a
    genuine clip. Live she drops OOB, delivers **no push at all**, and the bare cut is wall-blocked. The
    first live attempt died exactly here (her spot had `fB = -6.8`, behind wall B). **Constrain her start
    to `in_front` of BOTH seam walls** (and keep her plow path there too). A sim "hit" on non-floor is an
    artifact, in the same family as dead-ends #3/#4.

22. **Holding UP through the roll in the delivered DTM.** A pushed stick (`msd > 0.05`) force-exits
    `FRONT_ROLL` the moment `roll_frame > ROLL_EARLY` (`land/procs/roll.py:60`), so the roll ends into
    MOVE and the B can only ever fire a plain MOVE-slash (proc 90, backward recoil, no lunge) -- the
    roll-stab CUT_F never happens. The capture fixture holds UP (it was driven by `capture_cc_push`), but
    the SIM's schedule (`fast_shove.make_inputs`) holds **NEUTRAL** + one UP+B. **Deliver the sim's
    sticks, not the capture's.** Symptom: proc goes 30 -> 6 (MOVE) instead of 30 -> 66 (CUT_F).

23. **Assuming the sim's B step is the DTM's B step.** The sim buffers B with a 2-step INPUT_DELAY (B at
    step 14 -> CUT at step 16); the clean DTM delivers it with **1**. So the B goes one step LATER in the
    DTM (sim-step 15). Off by one either way and you get: too early -> the edge is consumed mid-roll and
    ignored; too late -> the roll has already exited and you get the MOVE-slash of #22.

24. **Seeding the sim at the CAPTURE's roll entry instead of the DTM's.** `dtm_make` calibrates sticks
    (255->254), so the delivered walk enters the roll ~0.004u away from the advancewith capture's entry.
    The acceptance is f32 DUST, so a placement solved at the capture's entry lands `old` on a sliver the
    real run MISSES -- block, not clip. **Seed `link_x0/z0` at the entry the DTM actually produces**;
    there the engine is 0-ULP vs live on every frame for both actors. (Generalises README model term #6:
    *always* sim the DELIVERED bytes, not the authored ones.)

**Method lesson (Dereck, session 22):** when a live delivery disagrees with the sim, do NOT tweak inputs
by guesswork -- **log the DTM per-frame and diff it against the sim** (both actors), and the divergence
frame names the bug. Four live runs were wasted guessing the B frame before the per-frame diff instantly
exposed #22/#23/#24. `run_dtm` has a `log_frames` param for exactly this.

## The from-rest slot-7 walk residual is a FOOT-POSE precision gap, not a seeding gap (session 25)

25. **"Seed the slot-7 DOWN-walk via `seed_rest_blend` + REST_NOOPS=2 + deferred-draw" (the session-24
    handoff's guess for computing the roll entry): WRONG lever.** Diagnosed by per-frame diff of the seeded
    sim vs a rich live walk trace. `noops=2` (kaze's value) FREEZES the WAIT/WALK blend advance and
    mis-aligns the walk start (residual worsens to ~4.2u); the slot-7 idle genuinely runs procWait every
    WAIT frame (blend advances d 17.80->18.20->18.60), so the right value is **`noops=0`**. At `noops=0`
    the proc/frame alignment is PERFECT (WAIT f0-2 / MOVE f3-8 / roll f9), the WAIT<->WALK blend `m3598`
    matches live BIT-EXACT (0,0,0,1.0,1.0,0.7647,0.3529,0,0), and `nspeed` ramps cleanly (+3.5/frame to
    cap) -- yet the entry is still ~**2.54u** off. The ENTIRE residual is the foot toe-stream `f312`
    (`posMoveFromFootPos` / `_py_foot_compose`) on the 3 walk-entry frames where `m3598>0` (f3-f5:
    speedF `nspeed*(1-m3598)+f312*m3598`, sim f312 low -- 0.068 vs live 0.105, 1.42 vs 2.15, 2.42 vs 4.62);
    it FREEZES at 2.54u once m3598 hits 0 (speedF==nspeed thereafter) and never grows. So this is the
    **same foot-FK-precision class as the Phase-R late-roll-pose drift** (jointBeforeCB MOMI body-lean /
    the walk-entry oldframe-morf toe stream), NOT a proc/blend/seed bug. Retry a computed entry only WITH
    a walk-entry foot-pose model, not more seeding knobs. The clip does not need it (measured entry is
    0-ULP live). Live trace: `_generated/turnaround_walk_trace.json`.

## Wall-brace for a Tetra-placement RANGE: no usable slide range exists (session 26)

26. **Bracing Tetra on a wall to get a targetable placement RANGE: RULED OUT (does not yield a range;
    bracing removes only one coordinate).** The genuine Tetra-placement set is a ~5e-4u-thin THREAD (KB
    [[strategy/seam-clip-solver]] "Tetra-corner placement"), so the along-wall braced window = thickness
    / sin(crossing angle) -- a useful range (~0.1u) needs the thread within ~0.3deg of PARALLEL to the
    wall at the brace distance. It never is. **wallB** (+Z) IS reachable -- a perp- roll-entry shift
    (~-1.3u) walks the thread's tip exactly onto the fB=TET_R=50 brace locus (z=-940.25562; verified the
    engine CrrPos-ejects deeper placements there, so fB=50 is the wall) -- but the thread crosses it
    near-PERPENDICULARLY (local angle 75-82deg; swept facing 40805-40880, never rotates toward 0), so the
    braced-genuine window is only 2-3 f32-ULP (~0.0002u): a POINT, x still f32-precise. **wallA** (+X) is
    the near-PARALLEL wall (thread local angle ~78-82deg ~ wallA's 90deg) that COULD give a range, but it
    is UNREACHABLE: the thread's corner-ward tip pins at x~-1650 (fA~76) at every Link entry tried (9
    directions, +-1.5-3u perp/roll/axis), ~25u short of the wallA brace (fA=50, x~-1677.66) -- an
    acceptance-geometry limit, not an unturned knob. Net: Tetra CAN be placed against wallB (z pinned
    free) but the along-wall x still needs f32 precision, and no Link position/facing knob opens a slide
    range. Untried long-shots (low expectations, the pin looks geometric): curved walk-up (nonzero
    `m351C` turn-lean) + thrust/roll timing. Tooling: `scratchpad/entry_brace.py`, `wall_range.py`,
    `walla_probe.py` (perp sweep + f32 thread-track + braced-z-line scan + wallA reachability).

## Wall-braced clip on the FOLLOW-enabled turnaround (slot 7): infeasible, Tetra flees (session 27, LIVE)

27. **A wall-braced Tetra clip is INFEASIBLE on slot 7 (follow-enabled turnaround) -- the deep-corner
    brace spot is not follow-safe.** Ran the full live pipeline: perp-shifted Link's start ~-1.3u so the
    roll entry reaches the wallB brace locus, measured the live entry (-1515.11,-766.13; the
    start-perp-shift translates to the entry RIGIDLY, matching the sim-predicted perp entry ~bit-for-bit),
    solved the braced-genuine placement (Tetra (-1652.293,-940.256), fB=50 ON wallB, bit-confirmed genuine
    at that entry), placed her, delivered, and per-frame-diffed. **Link's roll was BIT-EXACT (dLink=0), but
    Tetra DRIFTED off the wall before the roll reached her:** the brace spot sits ~220u from Link, and the
    speed-building DOWN away-walk pushes him PAST her 230u follow threshold (peak 249u at the walk end), so
    she ENGAGES follow and flees toward him; the cut wall-pinned short (live new=(-1692.3,-954.9), no clip).
    Offline-confirmed the bind: full roll (nspeed 26 needs walk>=5 frames) + seam-reach (Link far NE -- the
    +110 move exists because closer entries wall-pin) + follow-safe (walk peak<230) CANNOT coexist -- every
    follow-safe entry (backshift>=+24u toward the corner) has ZERO genuine (roll wall-pins). So bracing is
    incompatible with the FOLLOW-enabled clip *because follow is what breaks it*. Might work with the
    glitched no-follow Tetra (slot 6 pushaside, she stays put) -- UNTRIED. Tooling:
    `_notes/scratch-session27/{braced_live,entry_brace,wall_range,walla_probe}.py`.

## The pure-sim WALK-stab one-shot is blocked by the walk-entry foot residual (session 30, LIVE)

28. **A found walk-stab clip clips OFFLINE (0-ULP) but the clean-DTM live delivery does NOT -- the
    walk-entry foot toe-stream residual eats the razor.** The kaze r11 slot-3 walk-stab seam
    (S=(9030.955,1385.858), poly 803x802, interior 168.97deg) clips genuinely in the sim:
    `harness/rollstab/walkstab.solve()` finds it 0-ULP in < 2 min (the acceptance is f32 DUST, so it
    ENUMERATES distinct C-down walk streams -- beta spiral / start-crawl / bearing arc / per-byte fine
    nudge / N -- and tests the exact `genuine_clip`; the dust is SPARSE, ~ONE reachable `old` in the
    ~2e-4u perp sliver). Delivered as a clean DTM (C-down every frame, never advancewith), the walk is
    FACING-bit-exact every frame, but the CUT does NOT clip (`old_live` -> `genuine_clip` blocked;
    nearest clip ~1.2e-4u further in perp).
    - **Root cause:** to thread the perp razor the walk must TURN (aim the crawl+arc so the cut ray
      hits S); the turn overlaps the speedF-BLEND walk-entry frame (f6 here), which freezes a foot
      toe-stream (`m359C`/`f312`) position error of ~0.00037u. That error is a speedF-magnitude error
      (ALONG travel), but because the walk was TURNING when it froze, its component perpendicular to
      the FINAL cut facing is ~**1.9e-4u** (live-measured) -- and the clip's perp margin is only
      ~**1e-4u**. So `old_live` falls off the razor.
    - **This CORRECTS the session-29 feasibility read.** Session 29 measured the residual on a
      STRAIGHT walk (facing constant) and got perp ~3.7e-5u ("16x inside the razor, harmless"). But a
      real clip walk CANNOT be straight -- the 17u/frame along-granularity forces a start-crawl + arc
      (a turn) to place `old` in-window AND thread rho -- and the turning walk's perp residual is ~5x
      worse and comparable to the whole clip window (~2e-4u). No reliable margin exists. (The crawl
      entry actually SHRANK the residual, 0.00037u vs the straight walk's 0.0024u, and delayed it to
      the ramp frame -- but not enough.)
    - **Objective-compliant fix = MODEL the walk-entry foot toe-stream** (the Phase-R / session-25
      gap: `posMoveFromFootPos` / `_py_foot_compose` f312 is low on the m3598>0 blend frames;
      jointBeforeCB MOMI body-lean / oldframe-morf). NOT calibrate: choosing a window-EDGE hit so
      `old_sim + measured_residual` lands inside the sliver is position feedback (forbidden), and the
      residual is walk-dependent so it doesn't transfer. Once the toe-stream is bit-exact from rest,
      any centered hit delivers.
    - **B-timing (live-diffed, do not guess):** a B edge at DTM frame N-5 fires CUT_F at frame N (the
      4-frame item put-away delay + 1-frame DTM buffering); the lower body walks through the delay so
      `old` = the position after N walk steps. Symptom of +1: the CUT fires one frame late, `old`
      ~17u further along.
    - Tooling: `harness/rollstab/walkstab.py` (`solve`/`deliver`/`perp_margin`); live golden
      `tests/golden/walkstab_deliver.json`; regression `tests/test_walkstab_clip.py` (offline clip
      GREEN, live-clips xfail). Never re-ship a dust hit for delivery without the residual modelled
      (or a fat-band, residual-robust acceptance -- which this near-flat seam does not offer).
    - **CORRECTED (session 31): the "walk-entry foot residual" was the WRONG ANIM SET, not a
      foot-FK/lean/IK gap. `rest.rest_state` hardcoded `sword_drawn=True`, but this anchor holds the
      Wind Waker (`mEquipItem` 0x22, not `daPyItem_SWORD_e` 0x103), so `getAnmData` selects the base
      WALK/DASH legs, not the sword-drawn WALKS/DASHS.** WALK and WALKS share leg keyframes (a
      WAITS<->WALK entry is bit-identical either way, which is why f0-f3 matched), but DASH and DASHS
      differ, so the sword-drawn assumption drifted the plant toe ~0.0024u the instant DASH blends in
      (regime 2). Live-captured `mFootData` proved EVERY `jointBeforeCB`/`jointCB1` lean + foot-plant
      IK term is ZERO on this flat ground (waist tilt `m34E0`, CLOTCH `field_0x030`, leg bends
      `field_0x008/00A/002`; the SESSION_PROMPT note's "MOMI thigh lean from lateral accel" was wrong
      twice over -- MOMI 0x10/0x11 are FACE joints, not in the foot chain, and the lean is wind-driven).
      Fix: `rest.rest_state` seeds `sword_drawn` from the anchor's captured equip (`seed.json`
      `sword_drawn`/`equip_item`; default True for the sword-drawn roll-stab idle anchors). The
      from-rest walk is now BIT-EXACT 0-ULP in position + facing (`tests/test_walkstab_rest.py`), so
      any genuine OFFLINE clip is a true one-shot -- there is no residual to eat the razor. The
      session-30 hit no longer clips (fixing the ~0.0024u along-track error shifts `old` ~2-3 f32
      x-columns off its sliver; the dust is striped per column), so a deliverable hit is re-found in
      the corrected sim. **Lesson: verify the anim SET (equip state) before attributing a foot-pose
      residual to FK precision -- and capture the actual per-frame RAM quantity (mFootData, mEquipItem)
      before believing a plausible mechanism (cf. the session-16 morf-vs-lean lesson).**
    - **RESOLVED (session 32): the WALK-STAB clip is DELIVERED LIVE, 0-ULP, pure sim -- #28's premise
      is fully retired.** With the sim 0-ULP from rest (the session-31 sword fix), the live `old` lands
      exactly on the sim's; the only remaining problem was FINDING a deliverable hit, and that was
      NEVER throughput (see #29) -- it was distinct-`old` DENSITY near the razor perp. A K=3 crawl
      search (`solve_focused`) found wall-faithful genuine hits in 67s and the top clipped the seam live
      (CUT_F@N=13, `old`/`new` bit-for-bit the sim, Link OOB proc 0x24). Golden
      `tests/golden/walkstab_deliver.json`.

29. **The reachable-`old` byte lattice is a GAP over the perp razor at K<=2 crawls; the fine knobs the
    legacy `solve()` leaned on COLLAPSE under octagon clamping (session 32).** The acceptance perp razor
    is ~2e-4u; an offline sweep floored the reachable `min|perp|` at **~1.3e-3u (~13x)** with K<=2
    crawls, so `solve()` finds 0 even given the full 2-min budget -- MORE SPEED CANNOT HELP (the extra
    streams are octagon-clamped DUPLICATES: 52k streams -> ~14 distinct near-razor `old`). Root cause:
    the bearing arc `off` and the arc-frame per-byte fine nudge are FULL-magnitude sticks (octagon
    VERTEX), and PADClamp clamps them to the same delivered byte, so they do not move `old`. **The fine
    perp knob must be a PARTIAL-magnitude (octagon INTERIOR) stick, where every byte is a distinct
    decoded direction.** The fix (`solve_focused`): a K=3 START CRAWL -- each partial-mag crawl frame
    densifies the perp lattice ~20x (K=1 ~0.03u -> K=2 ~1.3e-3u -> K=3 ~2e-5u, below the razor), with
    the 3rd frame's BYTE nudge as the fine fill; bracket `|perp_ray|` cheap (no CrrPos), exact-test near
    the razor, and gate on a WITH-walls re-sim (`wall_hit==False`) to drop the #3/#28 wall-overshoot
    artifacts (an N=13 cut whose walk touched the seam wall has an `old` the wall-less sim overshot).
    **Lesson: when a byte-quantized reachable set won't hit an f32 razor, the lever is lattice DENSITY
    (more interior-stick DOF), not search speed -- measure `distinct near-razor old`, not `streams/sec`.**

## The SHEATHED roll anchor is not REST BIT-EXACT: an extra walk-entry idle frame (session 36)

30. **Equip-only sheathed mint off idle13 + default `rest_state`: NOT REST BIT-EXACT (a genuine
    walk-entry transition gap, not a fixable knob).** For the sheathed-roll milestone (session 35) a
    sheathed anchor was minted at idle13's spot (`kaze_r11_rollstab_sheathed@twwgz`; press A while idle
    to sheathe -> `mEquipItem` 0x100; pos/facing/csangle/state + blend rates all match idle13). The
    sword-DRAWN idle13 verifies `REST BIT-EXACT`, but the sheathed one does NOT, and the following were
    RULED OUT as the cause:
    - **NOT the code / `model_draw` / `sword_drawn`.** `model_draw`'s only effect without a B edge is
      forcing `native/foot_native=False` (already the case) -- all three of `model_draw` None/False/True
      give an identical sim walk. Forcing `sword_drawn` True vs False changes the entry ramp by ~0.003u
      (the base-vs-sword leg set is NOT the divergence). idle13 (drawn, same code path) is bit-exact.
    - **NOT a single `REST_NOOPS` / prepended-idle shift.** The real divergence: the sheathed idle takes
      **3 idle rows before the WAIT->MOVE transition** (live proc 4 at k=0..2, proc 6 at k=3) vs idle13's
      **2** -- the sim's walk starts one frame early and every downstream row is off by ~one 16.98u walk
      step (both reach the same cap). `REST_NOOPS` holds the idle-anim `d_frame` AND position TOGETHER,
      but live advances `d_frame` at k=2 while position stays at rest until k=3 -- so no dead-no-op count
      (0..4 swept) and no prepended blend/neutral step makes it bit-exact. The extra frame is a
      WAIT->MOVE / stick-delivery latency the drawn idle does not have.
    - **`run_dtm`'s row-0 alignment is JITTERY +-1 idle frame** (the `_log_playback` fast-poll lands "a
      couple frames in"): one sheathed verify showed row0 `d` = seed+1.1, another (same savestate) showed
      row0 `d` = seed. So diff the STABLE structure (idle-row count before MOVE), NOT row-0 `d`; a single
      run's +1 pre-advance is a red herring.
    Likely cause (untested, the session-35 Phase-R warning): the **sheathed idle rests in a non-`waits`
    anim arm** (`rest.rest_state` hardcodes `idle_anim='waits'`) whose WAIT->MOVE transition differs by a
    frame -- VERIFY the live idle anim ID before modelling. Or mint a clean-provenance sheathed savestate
    (the current one was made via `advancewith` frame-stepping; a real-time `resume`/`setinput` sheathe
    needs the idle A-press as a clean EDGE, which held-A / post-`clearinput` timing missed). RED test:
    `tests/test_sheathed_roll_rest.py` (strict xfail); live calib `fixtures/sheathed_rest_calib.json`.
    - **CORRECTED (session 37): the "one extra idle frame before WAIT->MOVE" was a `run_dtm` row-0
      POLL-JITTER artifact, and the "non-`waits` arm" lead is REFUTED.** Two run-free RAM reads + a
      jitter-proof measurement settled it:
      - **Idle arm is IDENTICAL** -- `m_anm_heap_under[0].mIdx` (loaded lower-body bck) reads `BCK_WAITS`
        (0x126) at BOTH the drawn idle13 and the sheathed anchor; only `heap[1]` differs (WALKS 0x135 vs
        WALK 0x12E = the already-modelled `sword_drawn` walk arm). So `idle_anim='waits'` is correct for
        the sheathed anchor. Both seeds are faithful (seed.json == live RAM). (Decomp: `getAnmData`
        d_a_player_main.cpp:12951 remaps the anim resource by `mEquipItem`; sheathed 0x100 -> base table,
        but `mAnmDataTable[ANM_WAITS]`'s under-bck IS WAITS 0x126, confirmed by the read.)
      - **Both anchors reach proc-MOVE at the SAME game-frame.** Tagging every live row with the
        deterministic emulator frame counter (game_frame = emu - F0; F0 = the savestate's stored frame,
        read by loading it paused) and aligning by that, BOTH transition proc 4->6 at gf6 and take the big
        walk step at gf8. The session-36 "3 idle rows vs 2" was the fast-poll catching the two captures at
        different start frames. `harness.rollstab.capture_walkentry` is the jitter-proof capture (plays the
        clean-DTM verification stream, tags emu, logs raw mFootData toe/heel + plant + m3598 + m359C).
      - **The REAL residual = the walk-entry foot TOE-STREAM (`posMoveFromFootPos`/`f312`), amplified by
        the 0.05 speedF clamp.** At the sheathed idle phase (d~52.8) the sim's first-walk-frame toe delta
        is ~0.034; live's is ~0.060 (`m359C`). The decomp-faithful `_py_foot_compose` clamp
        (`speedF = 0 if |spz| < 0.05`) then zeros the sim's step while live keeps it -- opposite sides of
        the razor -- and the error accumulates to ~0.8u over the m3598>0 blend frames (freezing once
        m3598 hits 0, same class as #25's 2.54u freeze). It is PHASE-driven, NOT equip (forcing
        `sword_drawn`/`model_draw` moves it ~0.003u; re-seeding at idle13's phase d=30.8 moves gf6 from
        0.0->0.056). `plant` also differs at entry (idle13 stays 1; sheathed flips 0->1 at gf6). So this
        is the **walk-entry foot-FK frontier of #25/#28**, exposed at a phase idle13 does not hit -- NOT a
        proc-timing, idle-arm, `REST_NOOPS` (swept 0..4, s36), or equip bug. Fix = model the walk-entry
        foot poses to f32 (session 37 handoff). Ground truth: `fixtures/sheathed_walkentry_golden.json`
        (RED) + `fixtures/idle13_walkentry_golden.json` (bit-exact reference), game_frame-aligned.
    - **CORRECTED + RESOLVED (session 38): the session-37 `f312`-FK story is REFUTED; the walk-entry
      foot-FK is BIT-EXACT. The real (and only) cause was a one-frame walk-entry DTM-ALIGNMENT noop --
      the anchor savestate's emulator SUB-FRAME CAPTURE PHASE, NOT in-game.** Diagnosis, all offline
      against the s37 goldens except two paused-RAM probes:
      - **The FK poses are bit-exact.** With the known 1-frame `mFootData` lag (sim pose N == live
        mFootData N+1) EVERY idle13 golden row matches the sim 12/12, and BOTH sheathed WAIT frames
        (gf2 d=53.9, gf4 d=55.0) match 12/12 EXACT. The s37 `m359C` "razor" mismatch was an ALIGNMENT
        artifact: the sim was one d-advance AHEAD (already MOVE at d=55.0 while live is still WAIT at
        d=55.0), so s37 compared a sim MOVE frame against a live WAIT frame -- not an FK residual.
      - **The sole divergence is the WAIT->MOVE alignment.** By the jitter-immune d_frame clock, live
        sheathed does 3 WAIT d-advances (52.8->53.9->55.0->MOVE@56.1) but the sim (REST_NOOPS=2) did 2
        (->MOVE@55.0). With **`noops=1`** the sheathed from-rest sim is **0-divergence on pos, m3598, and
        m359C at every d-aligned WAIT+MOVE frame**. idle13 needs 2, breaks at 1 (converse confirmed).
      - **It is a savestate CAPTURE PHASE, proven not in-game.** Loading each anchor paused and
        single-stepping neutral (no DTM, no jitter): idle13's first frame HOLDS d (30.8->30.8) then
        advances; sheathed's ADVANCES immediately. idle13's hold frame mutates **zero** player-RAM bytes
        (a pure emulator re-display of a frame captured mid-execution). It survives `load->save`, a single
        advance destroys it, VI-frame parity doesn't predict it, and none of 6 candidate player-RAM fields
        flip it (causal write-test). idle13 was minted MID-FRAME (legacy translate lineage) -> +1 spurious
        re-display -> noops=2; sheathed via `mint_current` (boundary capture, the canonical phase, same as
        the future live-RAM UI feed) -> noops=1. So `noops=1` is the STANDARD; idle13's 2 is a capture
        artifact pinned to its locked golden.
      - **FIX (no hardcode, no re-mint, locked goldens intact):** `mint.capture_rest` now DERIVES the
        phase from its existing t1-advance (advances-until-`d`-changes) into `seed['rest_noops']`;
        `rest.rest_state` reads it (legacy seeds default `REST_NOOPS=2`). Sheathed seed `rest_noops=1`
        (derived live). `tests/test_sheathed_roll_rest.py` FLIPPED to a plain assert (d_frame-aligned vs
        `sheathed_walkentry_golden.json`, GREEN); full suite 341 passed, locked idle13/walkstab untouched.
        The FK model of #25/#28 remains genuinely open (session-25 slot-7 residual, curved MOVE-turn
        overlap) -- it was just NOT the sheathed blocker.

## The sheathed roll-stab clip: SOLVED offline, LIVE-blocked by a sim MOVE-turn facing overshoot (session 39, LIVE)

31. **[CORRECTED session 40 -> #32: the "two-angle/MOVE-turn SETTLE residual" diagnosis below is WRONG.
    A jitter-immune measurement proved the row-18 divergence is a TRANSIENT (0.889,1.0)-BAND STICK
    input-layer decode divergence; the two-angle chase is faithful. The session-39 "shape overshoot"
    reads were run_dtm poll-jitter. Read #32.]**
    **The row-18 facing overshoot is a two-angle/MOVE-turn SETTLE residual, NOT input buffering, and it
    blocks the live roll-stab clip for BOTH the sheathed and drawn anchors.** Session 39 SOLVED a
    from-rest sheathed roll-stab clip (pure sim, seed-only; `old=(9072.209,308.028)`, offline `deliver
    gate` PASS 0-ULP genuine, sliver-robust) but the LIVE ship did not clip. Per-frame sim-vs-live diff
    (fixture `fixtures/sheathed_roll_ship_live.json`):
    - **Rows 0-17 are BIT-EXACT live** -- the K=2 crawl, the row-3 draw B-edge, the arc, and the fines
      all deliver 0-ULP, so delivery alignment / `rest_noops` (#30) are correct and the draw is not it.
    - **Row 18 diverges by a single frame:** on an aim-stick frame (after the row-16 fine settles) the
      SIM's `shape_angle` OVERSHOOTS to 33367 while live holds the settled 33295; the phantom turn dips
      speedF to 15.05 vs live's 17.0 cap -> a **~1.9u along-track lag that FREEZES** for the whole roll
      -> `old` lands off the f32 razor -> the CUT fires from the wrong spot (live `new` not behind the
      walls; the lunge misdirects). Same class as the #25 speedF-freeze, but the trigger is the TURN.
    - **DISCRIMINATOR (ruled out the buffering hypothesis): live shape+travel (`0x136`/`0x12E`) per
      frame == the sim on EVERY row except 18** -- live does NOT lead the sim by a frame, so it is NOT a
      stick INPUT_DELAY/buffering shift (the pushaside-#3 class). The sim inserts one spurious facing
      value at row 18 that live never has -> a genuine `shape_angle` chase / `setMoveSlantAngle` settle
      overshoot after an arc+fine (README model term #5; the Phase-R MOVE-turn frontier). NOT fixed this
      session (Dereck: diagnose first). Two open paths: (a) re-search for a CLEAN-SETTLE hit (constrain
      speedF==17 on every cruise frame from the last turn through A -- no sim change); (b) model the turn
      overshoot to f32 (decomp-first, the general fix, also unblocks the drawn idle13 hit). RED gate
      `tests/test_sheathed_roll_clip.py::test_sheathed_ship_matches_live` (strict-xfail).
    - **Side note (search speed):** `solver.search` is over-budget for the roll-stab -- at 200s it had
      not finished drill level 0 for idle13 OR sheathed; its `_dust_cache` under-samples the
      1-f32-col-per-z genuine set (step 0.001 >> f32) and mis-guides the drill. The 91s find used a
      focused warm-start from the same-seam idle13 recipe (objective-compliant: seed-only). Fold that
      into a reproducible <2-min sheathed solve; do NOT trust the generic drill for the roll-stab.

## The sheathed roll-stab clip: row-18 blocker RE-ROOT-CAUSED as a transient band-stick decode divergence (session 40, LIVE, jitter-immune)

32. **[CORRECTED session 41 -> #33: the "1-frame band stick decodes to ~aim / holds prior" claim below
    is WRONG. A deterministic stopped-position probe proved the band DECODE registers its raw value
    bit-for-bit (target + msd), even as a 1-frame transient. The row-18 divergence is a WALK-SPEED gap
    (the sim dips speedF on the band magnitude at cap; the console does not), NOT a decode gap. The
    session-40 single-frame decode read was itself a ±1-frame misread of run_dtm's log (the same trap
    it claimed to have designed out -- the log's stream->frame offset is ±1 ambiguous, and a 1-frame
    event lives entirely inside that window). Read #33.]**
    **The row-18 blocker is a TRANSIENT (0.889,1.0)-magnitude-band stick input-layer decode divergence
    -- NOT the two-angle/MOVE-turn settle of #31.** Session 40, all measured jitter-immune (deterministic
    game_frame tags, `fixtures/sheathed_roll_ship_jitterproof.json`), the run_dtm poll-jitter that misled
    #31 designed out:
    - **The stick DECODE is bit-exact live.** Holding each band stick CONSTANT for 8 frames, live
      `mStickDistance`/`m34DC` == the sim's closed-form `main_stick_decode` exactly (`(96,192)`->0.9605,
      `(98,191)`->0.9313, ...). So there is nothing wrong with the decode formula, and the two-angle
      chase is faithful (it follows `target`, which is correct for held sticks).
    - **But a 1-FRAME TRANSIENT band stick decodes DIFFERENTLY live.** At ship row 18 the acted stick is
      the fine `(96,192)` (msd 0.9605, in the band). The sim decodes it raw (target 33367, msd 0.9605)
      and turns; LIVE decodes the 1-frame transient to ~aim (target 33295, msd 1.0 -- it HOLDS the prior
      value) and does not turn. Non-band 1-frame fines (`(98,188)` 0.878, `(99,183)` 0.785) register
      correctly. So the band divergence is a TRANSIENT/input-layer effect (input smoothing/latency near
      the magnitude cap), the same "input-layer != /54" family precise-stop.md/land-planner.md warn about
      and the freeze planner already excludes from its crawl.
    - **This means the session-39 winning hit is not predictive live (it depends on the sim's mis-model),
      and the SEARCH SHAPES tried this session did not find a band-faithful hit.** The winning hit's
      genuine landing depends on the sim treating that transient band stick as a real ~0.9605/33367 perp
      nudge, which live reads as ~aim -- so the sim must be made band-FAITHFUL before its hits are
      trustworthy. And the pure LIVE-VALID lattices tried (every stick msd<=0.889 or ==1.0, avoiding the
      band; dense 2-knob vernier arc + clean fine + K3-crawl-3rd-byte) reached only ~0.0013u from the f32
      dust with 0 genuine over ~60k runs. The dust is single f32 columns (~0.001u spaced); those
      lattices did not align onto one. NOTE: 0.0013u bounds the recipe SHAPES tried, NOT the clip -- a
      richer input alphabet / faithful band model is the untried lever.
    - **RULED OUT this session (approaches, not the clip):** (a) path-1 "clean-settle" re-search -- a
      speedF dip on a fine-ACTED frame is live-faithful (live turns there too), so a clean_settle filter
      wrongly rejects real dips; only transient BAND sticks are sim-only. (b) "fix the decode as a
      closed-form" -- the held decode is already bit-exact; only the 1-frame transient diverges (needs an
      input-layer/buffer model, not a decode-formula change). (c) the #31 "two-angle settle" story --
      refuted (chase faithful).
    - **Open approaches to PURSUE (the clip is not solved -- keep pushing):** (1) MODEL the transient-band
      input-layer behavior to f32 -- characterize it with a live band-transient sweep (is a 1-frame band
      stick == prior-frame value? a 2-frame slew?) and make `main_stick_decode`/the input buffer
      reproduce it, so the solver searches over what live ACTUALLY does, then solve band-faithfully; (2)
      EXPAND the search well beyond the shapes tried (more knobs, longer crawls, other draw/arc/A_proj
      placements, a walk-stab-solver warm-start) to close the last ~0.0013u -- the 0.0013u floor is a
      property of the tried lattices, so a richer alphabet is the lever; (3) exploit delivery-mechanics
      DOF not yet used (draw timing, B timing, roll-entry frame). Ground truth:
      `fixtures/sheathed_roll_ship_jitterproof.json`.

## The sheathed roll-stab clip: row-18 blocker is a BAND WALK-SPEED gap, not decode (session 41, LIVE, deterministic)

33. **[CORRECTED session 42 -> #34: the "console's BAND WALK-SPEED is unmodeled" mechanism below is
    WRONG. Reading the RAW SI-delivered pad (`g_mDoCPd_cpadInfo[0]`) from RAM proved the sim/decomp
    physics are FAITHFUL and the stick decode is faithful even for Y>=192 when ISOLATED -- there is no
    band-walk-speed gap to model. The row-18 miss is a make_dtm DELIVERY DROP: the game never receives
    the band fine (it polls the full neighbour). The "OPEN SUBTLETY" below (probe dips, ship doesn't)
    was the tell -- a walk-speed formula cannot be context-dependent; a delivery cadence can. The z/speed
    observations below are all correct; only the mechanism (walk-speed formula) is wrong. Read #34.]**
    **The row-18 live miss is a ONE-FRAME along-track (walk-SPEED) deficit from a band-magnitude stick
    at the speed cap -- the sim is NOT modeling the console's band walk-speed. NOT a decode gap (#32
    wrong) and NOT a facing/MOVE-turn overshoot (#31 wrong).** Both prior diagnoses were ±1-frame
    misreads of run_dtm's per-frame log; reading the ROBUST z-trajectory (immune to ±1 -- a
    misalignment shows as a ~17u step, not 1.9u) settled it. Established this session:
    - **The band DECODE is faithful, even for a 1-frame transient.** A DETERMINISTIC probe -- deliver
      `aim*cruise + [1-frame T] + neutral*16 (decel to a DEAD STOP)` and read the STOPPED position
      (constant -> ±1 read cannot corrupt it) -- gives, for the culprit `(96,192)`, live stopped pos ==
      the sim's raw-decode prediction BIT-FOR-BIT (0 ULP; sim's no-op "holds prior" prediction was off
      by 20.9u). A sub-band control `(98,188)` likewise. So the sim's `main_stick_decode` (target + msd)
      is correct for band 1-frame transients -- overturns #32. Tool: `harness.rollstab.capture_decode.
      transient_probe` (stopped-position, deterministic; `python -m harness.rollstab.capture_decode
      probe`); the per-frame `capture_decode.band_sweep` is NOT
      reliable for 1-frame reads (its stream->row offset is ±1 ambiguous; O=2 and O=3 both give 0
      disagreement on settled runs).
    - **The divergence is purely SPEED (z), not facing (x).** gf-aligned to the jitter-immune golden
      (`fixtures/sheathed_roll_ship_jitterproof.json`, gf = 2*row + const; the emulator counter ticks
      twice per game frame -- 0 gf conflicts, clean +2 cadence): rows 0-17 are BIT-EXACT (incl. the
      whole arc at rows 12-16, and sub-band 1-frame fines, and a held-2 full stick). At row 18 the sim
      dips speedF 17->15.091 while live holds 17.0; perp x matches to 0.02u. The one-frame deficit
      `17 - 15.091 = 1.909` == the observed 1.9125u lag, which FREEZES through the roll -> `old` off the
      f32 razor -> no clip. Confirmed by two independent live runs (the golden + a fresh `deliver ship`:
      live old z 306.116 vs sim 308.028, d = -1.912).
    - **The mechanism (decomp): `mStickDistance` walk-speed.** `setNormalSpeedF` (d_a_player_main.cpp:2306)
      sets the target speed `dVar10 = mStickDistance * (mMaxNormalSpeed * mStickDistance)` = msd^2*max;
      for `(96,192)` msd 0.9605 that is 15.68 < 17 -> the sim decelerates. `setStickData` (10569) sets
      `mStickDistance = g_mDoCPd_cpadInfo[0].mMainStickValue` (JUTGamePad::CStick::update value =
      `min(hypot(clamped)/54, 1)`). The whole game path (PADRead->PADClamp->CStick::update) is STATELESS
      (decode faithful), so the gap is the console's EFFECTIVE walk-speed for a band magnitude, which
      differs from msd^2*max. This is the SAME band-speed caveat precise-stop.md already documents
      (held `(128,196)`: console 15.76 vs sim 16.38 -- sim HIGHER when held; but for a 1-frame band at
      cap the console holds full and the sim dips -- sim LOWER). Only band magnitudes (0.889,1.0)
      diverge; sub-band and full are bit-exact live (rows 0-17 prove it). `start1 (98,191)` is band too
      but was bit-exact -- because it is in the start crawl at LOW speed (target above current -> still
      accelerating -> no dip); only band AT CAP dips.
    - **OPEN SUBTLETY (do not over-claim a mechanism -- the #31/#32 lesson): the probe (band after plain
      cruise) MATCHED the sim's dip bit-for-bit, yet the ship (band after the arc) shows live NOT
      dipping.** Same stick, same cap speed, same bit-exact entering state -- so an arc-carried hidden
      state (travel/anim/turn-lean) changes the console's band-speed response, and the sim does not model
      it. Not isolated this session; it does not change the fix.
    - **INTERIM WORKAROUND (session 41): `solver.fine_family` now EXCLUDES the (0.889,1.0) band**
      (`_in_band`), so the solver cannot emit a divergent 1-frame band fine. But this lands on session
      40's wall -- the band-free search does not reach the f32 dust (band fines were the near-full-mag
      fine-perp density). Deliverable hit is NOT found band-free.
    - **NEXT (Dereck's directive: model what the sim isn't modeling): resolve the RED gate
      `tests/test_sheathed_roll_clip.py::test_sheathed_band_speed_at_cap` by modeling the console's
      band-magnitude walk speed to f32** -- decomp-first from `setStickData`/`mMainStickValue` /
      `JUTGamePad::CStick::update` value near the cap (and characterize the arc-carried context
      dependence via the deterministic stopped-position probe, NOT per-frame run_dtm reads). Once
      faithful, REMOVE the `fine_family` band-exclusion so the solver can USE band sticks again
      (restoring density), re-solve, deliver.

## The sheathed roll-stab clip: row-18 miss is a make_dtm DELIVERY DROP, not physics (session 42, LIVE, RAM-confirmed)

34. **The row-18 live miss is a `make_dtm` poll-cadence DELIVERY DROP -- the game never receives the
    band fine -- NOT a Link-physics gap and NOT the "band walk-speed" of #33 (WRONG).** Found by reading
    the RAW SI-delivered pad from RAM (`g_mDoCPd_cpadInfo[0].mMainStickValue` @ JP 0x80398310, and PosX/
    PosY/Angle @ 0x80398308/+4/+0xC), i.e. what the game ACTUALLY polls, instead of inferring it from
    downstream speed/position. Tool: the cpad read is now in `harness.rollstab.capture_decode` (`capture`
    logs cpad_val/px/py; `delivery_sweep` = the (polls,seed) delivery probe; `sweep` CLI). Established:
    - **The decomp physics + decode are FAITHFUL (traced, not assumed).** Every function in the row-18
      path matches the sim line-for-line: `setStickData` (10569), `setNormalSpeedF` (2301: the
      `dVar10 = msd^2*max` decel is unconditional once `msd^2*max < mNormalSpeed`), `setSpeedAndAngleNormal`
      (2751), `setBlendMoveAnime`'s `m3598` (pure function of nspeed, 2976/3163/3180), the 0.3/0.7 toe
      recursion (2399-2484). `PADRead->PADClamp->CStick::update->mMainStickValue` is stateless. So per the
      decomp, IF the game received `(96,192)` msd 0.9605, it MUST decel -- there is nothing to "model".
    - **The stick decode is faithful even for Y>=192 when ISOLATED.** A 1-frame `(96,192)` (and `(96,193)`,
      `(98,192)`) after plain cruise delivers `cpad_val` == the sim's `main_stick_decode` bit-for-bit and
      dips. So #33's "band walk-speed" premise is void -- there is no band-magnitude walk-speed gap.
    - **In the SHIP the band fine is DROPPED in delivery.** At fed-index 16 (acted row 18) the game polls
      the FULL neighbour: `cpad_val=1.0, (px,py)=(-0.32,0.95)` == the `(77,249)` stick, NOT `(96,192)`'s
      `(-0.3148,0.9074)`. A distinctive px=0 marker at fed-16 ALSO drops (positional, value-independent);
      an all-full ramp delivers every frame; the ship's OTHER fines (0.9313 START, 0.7848 arc, 0.8784)
      DO deliver -- so a CLUSTER of preceding partials induces a sub-frame poll-phase slip that drops a
      later 1-frame partial. This single dropped dip is the ENTIRE 1.9125u miss (offline: forcing row-18
      to full shifts along-track by exactly -1.91248u; live old_z 306.116 == sim 308.028 - 1.912).
    - **The cause is `make_dtm`'s poll cadence, and `seed` controls it (live sweep):** with the pipeline
      default `(polls=4, seed=1)` the band drops (roll row 22); `(4, seed=0)` DELIVERS the band at the
      SAME roll row 22 (timing preserved); `(4, seed>=2)` delivers but shifts timing (roll row 23);
      `(8, *)` delivers every frame but at ~2x timing (each authored frame spans 2 game frames -> the
      plan's discrete B/A land wrong; no clip). So the game reads ~4 SI polls per 30fps logic frame
      (polls=4 = correct 1:1); `seed=1`'s leading neutral poll sets the phase that slips.
    - **THE FIX (characterized, NOT yet shipped):** `make_dtm(seed=0)` restores delivery at correct
      timing, BUT seed=0 alone still leaves a ~0.6u residual and no OOB clip -- because changing the
      leading-poll layout desyncs the from-rest prefix the sim's `rest_noops` (session 38) is calibrated
      to. So the clean fix is **`seed=0` PLUS re-derive `rest_noops` for the seed-0 layout** (mint.capture_rest
      derives it from the t1-advance), re-verify REST BIT-EXACT, then the session-39 hit should clip.
      Validate with `capture_decode.delivery_sweep`: VALID == every authored fine received + roll row
      unchanged + OOB `proc 0x24`. The `fine_family` band-exclusion (#33/solver.py) is NOT the fix and
      should be REMOVED once make_dtm delivers faithfully (it removes usable fine-perp density -- s40's
      0.0013u wall). OPEN: whether this drop is Dolphin-DTM-specific or real-hardware (a real TAS would
      hit the same SI cadence) -- the fix makes the sim+DTM self-consistent regardless.

## Pointers

- Current pipeline + run protocol + verification: `harness/rollstab/README.md`.
- Methodology (why the region is dust, why calibration was added): [strategy/seam-clip-solver.md](../strategy/seam-clip-solver.md).
- Collision / clip mechanism: [mechanics/collision.md](../mechanics/collision.md).
- The SOLVED fast-exact sim-search pattern to reuse: `tww_sim/land/plan_land/_freeze/roll.py`
  (cheap monotone predictor + prune + bit-confirm, no table, no calibration).
