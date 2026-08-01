# harness/tetrapush - the Courtyard Tetra-push planner (the real TAS)

Take the actual any% TAS at the flooded-Hyrule "courtyard" Tetra push and, starting from a fixed
mid-run state, compute the **optimal input sequence that shoves Tetra into a known viable
seam-clip position**. This is a ONE-TIME sequence for the real run (not a generalized solver), so a
>2-minute search is fine.

This is distinct from `harness/rollstab/` (the generalized seam-clip *solver*), but reuses its
Tetra machinery: `tww_sim/core/npc_zl1` (follow), `harness/rollstab/cc_stepper` +
`tww_sim/core/cc_push` (the CC plow), `tww_sim/land` (roll / EBS / cut), `harness/rollstab/
geometry_tetra` (push-aware clip acceptance). Read the seam-clip memories first: `[[tetra-push-model]]`,
`[[cc-push-stepper]]`, `[[tetra-follow-model]]`, `[[tetra-clip-solved-live]]`, `[[turnaround-clip-followenabled]]`.

## North star (this session's directive)

- **Load savestate slot 2**, mid-playback of the real TAS DTM
  (`…/Dolphin TAS-Studio 1.2/TAS Files/28_Courtyard_TetraPush_Unfinished.dtm`; the movie itself
  runs in the pipe-enabled research build, `Dolphin-Zelda-TAS-Edition/…/Release`).
- **Determine the optimal input sequence from state 2 that gets Tetra into a known viable clipping
  position.**

To get there:
1. Make the sim reproduce the ~45 hand-performed push frames after state 2 **bit-exact** for all
   relevant live RAM (Link pos/speed/facing/anim/proc; Tetra pos/facing/speed/stt).
2. Build a planner: state-2 config to an input sequence that lands Tetra on a viable clip coord.

## Live setup (HARD-WON, session 14 -- read before rebuilding the slot-2 state)

The real-TAS setup runs on **`TWW-JP.iso`** (the official unmodified JP disc), NOT `twwgz.iso` (the
practice hack every sandbox anchor uses) -- match the iso to the savestate's origin. On the wrong
iso the state half-loads and **Dolphin exits cleanly seconds-to-minutes later** (no crash dump, no
log line). Two more traps:

- **`MMU = True` is required** in `Release/User/Config/Dolphin.ini` (`[Core]`); the slot-1/2 states
  were saved with MMU on, and with it off `loadstate 2` **silently aborts** (`MemoryManager::DoState`
  fake-vmem mismatch; the only signal is a 3-second OSD toast -- screenshot the render window to read
  OSD, it is never logged). MMU stays on, always (Dereck's standing requirement).
- **A movie-anchored state needs its movie active before the load**: from a stopped instance,
  `play <StateSaves/GZLJ01.s02.dtm> game=<TWW-JP.iso>`, wait for `running/playing:true`, then
  `loadstate 2` (lands paused at frame 89952). This fork does not sync MMU from DTM headers. The pipe
  command is **`playmovie`** (`{"path":..,"game":..}`); the CLI `play` maps to it.
- **A breakpoint-driven capture MUST step with `advance`, NEVER `resume`** (session 26, hard-won). On
  this movie-anchored state a bare `resume` lets the DTM free-run to its end and **Dolphin cleanly
  EXITS** (the same "clean exit" signature as the wrong-iso trap, but here caused by the free-run) --
  no crash dump, the process is just gone. Set the code breakpoint, then `advance frames=1` in a loop:
  the bp fires once per game frame (at posMove, ~2 advances apart -- a boundary halt then the posMove
  halt), Dolphin survives the whole window, and the frame count is PINNED by the bp (immune to any
  single-step edge jitter). `capture_push` proved `advance` safe over 60 frames; `_notes/tetrapush-
  perop_probe.py` is the advance+breakpoint template.
- **Launch Dolphin DETACHED so it survives across separate shell commands** (session 26). A Dolphin
  launched by a short-lived helper (`subprocess.Popen` from a script that then exits, or an
  `ensure_running` invoked as its own command) dies with that command -- the next command finds no
  process. Launch it with PowerShell `Start-Process` (fully detached), verify it persists into a
  separate command, THEN drive it. (`ensure_running` still works when ONE long-lived process launches
  AND does all the work, e.g. `run_tests.py`.)

## The setup (measured live, 2026-07-21)

"Courtyard" = the flooded **Hyrule** castle room (stage `Hyrule`, room 0), flat floor **Y = 0.16327**,
the SAME geometry as the seam-clip sandbox (the `(-1727,-990)` corner). Tetra is herded in
-Z/-X, i.e. **toward that corner**, from her start near `(-1337, -1)`.

**State-2 seed** (frame 89952; `fixtures/courtyard_push_state2.json` `seed`):

| Actor | pos (x, y, z) | travel (angle.y) | facing (shape.y) | speedF | proc |
|-------|---------------|------------------|------------------|--------|------|
| Link  | (-1329.4236, 0.1633, 39.8988) | 4705 | 12386 | **-24.574** | MOVE (6) |
| Tetra | (-1336.7809, 0.1633, -0.9584) | 65516 | 65516 | 0.0 | type 5, stt 3 |

csangle ~ 39432. Link enters state 2 **already in a near-full-roll-speed backslide** (speedF -24.57,
hotter than the usual -23.5 EBS), the untarget brakeslide (below), heading toward Tetra ~41u away.

## What the hand-performed push does

A repeated **~26-frame cycle**, twice over ~45 frames, that herds Tetra ~535u in -Z (to `(-1510,-535)`):

```
MOVE backslide (speedF ~ -24.6, decaying ~-0.01/f)     [plain EBS glide; sim models this]
  -> ATN_MOVE (7), 1-2 frames, re-target; speedF briefly flips +18  (roll setup)
  -> FRONT_ROLL (30), 26.0, ~16 frames, facing LOCKED   [plows Tetra as the roll passes through]
  -> ATN_ACTOR_MOVE (9) @ 26 -> flips to -25.7           [THE UNTARGET BRAKESLIDE; 2 frames, no held L]
  -> MOVE backslide (-25.4, decaying) -> repeat
```

Tetra during the rolls: **stt 3, speedF 0, she is PLOWED** (her `current.pos` is shoved by Link's
rolling Co-center, no self-locomotion). Once Link's rolls stop and he glides away she flips to
**stt 4 and FOLLOWS** (speedF ramps 0 to the 10 cap then decays; the `Zl1FollowState` model). So the
herd is a **mix of CC-plow (during roll-throughs) + follow-chase (between)**, both already in the sim.

## The CC split (Courtyard push) = BOTH actors eject the full Co overlap  [live-derived + gated, s8-9]

> **Session-27 note (the bit-exact law):** the per-frame push is now `from_f0.cc_push_pair` =
> `cc_push.co_move_pair` (`dCcS::SetPosCorrect`) -- the decomp **50/50 HALF-depth split on the EXEC
> centre**, obj1/obj2 exact-opposite -- which is 0-ULP vs the deterministic per-op ΔTetra (f2..f43).
> The "both actors eject the FULL depth" framing below is the equivalent measured against the SETTLED
> (pause-boundary) centre (full-from-settled == half-from-exec, but only to ~1e-5 u -- that ~1e-5 u
> was session-24's "bug #1"). The derived full-depth laws (`tetra_plow.plow_step`, `link_plow.recoil`)
> are retired / seed-frame-fallback only. The live-derived facts below (radii, ranks, the Co centre =
> animated mCyl root/neck midpoint, Tetra = feet) all stand.

The Tetra herd is a Co-cylinder push. Session 8 measured Tetra's side **live from slot 2 (frac =
tetra_move / overlap_depth = 1.000 for 40 consecutive frames, both cycles)**; session 9 measured
Link's side (his recoil = the full depth too, the mirror). Grounded geometry:

- **Link's push Co centre is his ANIMATED `mCyl` centre**, the `setCollision` root/neck joint midpoint
  (`d_a_player_main.cpp:9748-9754`), read live at `lp+0x4064` -- **NOT `current.pos`**. It leads the
  feet **6-28 u** through the backslide/roll pose. On roll frames `body_cyl.roll_co_center` reproduces
  it once fed the **lagged draw-base position** (d drops 8-17 u -> 1.4-8.9 u; the residual is the draw
  position lag, which the stepper frame order handles); the lean (`shape.z`) is negligible. R_link = 30,
  R_tetra = 50, Tetra centre = her feet -- all live-confirmed.
- **Tetra absorbs the FULL overlap depth each frame** (`depth = 80 - dist(link_centre, tetra_feet)`),
  ejected away from Link's centre. Given Link's mCyl-centre path, `tetra_plow.reconstruct` predicts her
  WHOLE trajectory to **<0.01 u over 40 frames** -- the herd is a deterministic function of Link's centre
  path. Gated: `harness/tetrapush/tetra_plow.py` + `tests/test_tetra_plow.py`.
- **Link's OWN displacement is ALSO reduced by the full depth -- MODELED + gated (session 9), the mirror
  of the Tetra plow.** Live (`vec_decomp` off `courtyard_push_cyl.json`), on every push frame Link's
  recoil = the **full** overlap depth directed AWAY from Tetra along the centre-to-centre line
  (`recoil/depth == 1.000`, `recoil.dir == centre->Link`), so his net ground move = `foot term
  (speedF along current.angle.y) - full depth away from Tetra`. i.e. **BOTH actors eject the full
  cross_len** (total separation 2*depth per frame -- exactly why the live Link<->Tetra feet distance
  OSCILLATES 41-85 u, the chase-and-plow). This is the mirror of the Tetra plow, and it reconstructs
  Link's whole roll+backslide feet path to <0.01 u (rolls) / <0.06 u (single-step-jittery backslides)
  vs live. Gated: `harness/tetrapush/link_plow.py` + `tests/test_link_plow.py` (frac==1.0 every push
  frame; recoil vector + feet reconstruction 0-ULP-within-jitter on the clean roll frames). This
  **overturns** the session-8 "Tetra 100 % / Link 0 %" reading (Link is not 0 %; he ejects the full
  depth too), and is distinct from the type-5 FOLLOWING Tetra's gated 50/50 (`[[tetra-push-model]]`,
  the sandbox `cc_stepper`) -- this open-floor being-pushed (stt-3) split is Courtyard-specific.
- **The "2x the naive split" sub-puzzle -- SOLVED (session 14): there is no doubling; it IS the plain
  50/50.** The scene CC pass applies the decomp 50/50 rank split to the **EXEC-time** centres (each
  actor moves `0.5 * cross_len` of the `setCollision`-written overlap), and the immediate
  `SetPosCorrect` write (watchpoint-caught at `lp+0x4064`, writer LR `0x800ab5d0` in dCcS) moves
  Link's REGISTERED Co cylinder by that half-depth away from Tetra. Because that shrinks the
  centre-to-centre gap by the same half, "full depth measured from the PAUSE-BOUNDARY (settled)
  centre" -- what the fixtures log and the gated `link_plow`/`tetra_plow` laws consume -- is
  numerically identical to "half depth from the exec centre". Verified exactly on probe frames
  f1..f12 (`fixtures/courtyard_push_setcol.json`; `delta == recoil(fix, tetra) == 0.5 *
  recoil(exec, tetra)` to 4 decimals). The gated full-depth laws stay as-built (they are the settled-
  centre framing of the same numbers); `from_f0._cc_settled_center` encodes the exec-to-settled map.

## THE key modeling gap: untarget brakesliding = the ATN_ACTOR procs  [MODELED s2; FLIP live-exact s3; LOCK-LIFETIME + 2-FRAME TIER s6; BACKSLIDE-UNZEROED + GAP-2 CONE s7]

The payoff frames read **`ATN_ACTOR_MOVE` (proc 9)**, `daPyProc_ATN_ACTOR_MOVE_e`, the
**actor-lock** variant of ATN_MOVE, plus its idle sibling **`ATN_ACTOR_WAIT` (proc 8)**. The land sim
originally modeled only **plain `ATN_MOVE` (7)** (targeting a *direction*, not an *actor*); session 2
added procs 8/9 + the attention lock-on state machine per the recipe below (see `## Plan / status`).
It is implemented decomp-first and offline-gated but **not yet 0-ULP-validated against a live capture**.

The mechanic (Dereck's description, confirmed live): target Tetra mid-roll; **releasing L does not
untarget immediately, it takes several frames.** Time the L release to the end of the roll anim and
you go straight into ESS-down **without spending the 1 "L+down" frame** that the standard roll-EBS
needs, so the retained EBS speed is **near the full roll speed (-25.7)** instead of -23.5. Live: the
roll (30) exits into ATN_ACTOR_MOVE (9) at 26, flips to -25.7 over ~2 frames with the pad already
near-neutral (no held L), then drops to MOVE (6). The actor-lock persisting past L-release is what
keeps Link in the ATN tier for the hot flip.

### Decomp anchors (verified 2026-07-21, `src/d/actor/d_a_player_main.cpp` + `src/d/d_attention.cpp`)

The mechanism is fully grounded (US GZLE01 line numbers; logic identical to JP):

1. **Procs 8/9** = `procAtnActorWait`/`procAtnActorMove` (6254-6311); BOTH call
   **`setSpeedAndAngleAtnActor()`** (2909-2935). Unlike plain ATN (proc 7,
   `setSpeedAndAngleAtn`/`setSpeedAndAngleAtnBack`, 2850-2907), proc 9 has NO forward/backward split:
   it always uses the `mAtnMove` param family AND `setShapeAngleToAtnActor()` (2625-2631, keeps facing
   the locked actor). Facing the actor while sliding keeps `getDirectionFromCurrentAngle()==DIR_BACKWARD`
   true, so the negation branch (2913-2915: `current.angle.y += 0x8000; mNormalSpeed *= -1`) stays
   engaged, flipping +26 to -26.
2. **Roll-exit routing** = `checkNextMode` (4423-4521): `r24 = checkAttentionLock()`; if locked AND
   `mpAttnActorLockOn != NULL` AND `|speed| > 0.001` -> `procAtnActorMove_init` (proc 9, 4472-4476);
   attention-but-no-actor -> proc 7; no attention -> proc 6/turn. `mMaxNormalSpeed` = 12.0 (`mAtnMove.
   field_0xC`) when locked else 17.0. Roll init caps at `0.5 + 17.0*1.5 = 26.0` (6817-6849).
3. **Untarget latency is ANIMATION-driven, not a fixed frame count.** L-release from `LockState_LOCK`
   goes to **`LockState_RELEASE`** (not NONE; `d_attention.cpp:814-819`), and `LockonTruth()`
   (1049-1051) stays true through RELEASE while a target exists, so `checkAttentionLock()` stays true
   and the roll keeps exiting into proc 9. RELEASE ends only when `AttnFlag_40000000` clears, which is
   when the lock-on reticle **fade-out animation completes** (678-695). That is the "several frames".
4. **Why -25.7 not -23.5:** the roll's `-5.0` decel (`mRoll.field_0x20`) is subtracted ONLY on the
   anim-complete exit AND only with a neutral stick (`mStickDistance <= 0.05`, 6860-6864); the
   held-stick early-turn exit (`getFrame() > 17`, `checkNextMode(1)`, 6866) SKIPS it. Then proc 9
   decays the -26 with the gentle `mAtnMove` params (scale 0.5, maxStep 7.5) via `setNormalSpeedF`
   (2300-2350) + `cLib_addCalc` (`c_lib.cpp:22-53`). The plain roll-EBS drops attention or passes a
   neutral frame -> eats the -5.0 + the proc 6/7 decel -> only -23.5.

### Modeling recipe (what to add to the sim)

- An **attention state machine** `LockState in {NONE, LOCK, RELEASE}` mirroring `dAttention_c`
  hold-mode (`d_attention.cpp:764-844`): L-release from LOCK with a valid target -> RELEASE; RELEASE
  persists while `target != NULL AND reticle-out-anim still playing` (model `AttnFlag_40000000` as the
  reticle fade timer, NOT a magic constant). `mpAttnActorLockOn` non-NULL iff `checkAttentionLock()`.
- **Roll-exit routing** gated on that state (proc 9 vs 7 vs 6), with the conditional `-5.0`.
- **`setSpeedAndAngleAtnActor`** as a new proc mixin (does the existing `_AtnMixin` in
  `tww_sim/land/procs/atn.py` generalize, or add `atn_actor.py`?): the DIR_BACKWARD negation, the
  `mAtnMove` decay family (table in the agent findings), and re-aim `shape_angle.y` at the locked
  actor each frame. HIO params: `mAtnMove` cap 12.0 / push 5.0 / decel scale 0.5 / maxStep 7.5 /
  minStep 4.0 (vs `mAtnMoveB` 15.0 / 2.5 / 0.5 / 8.0 / 2.0).

## The land camera (csangle) -- PORTED + 0-ULP GATED  [session 18; overturns the session-17 map]

**Truth page: [`knowledge/mechanics/land-camera.md`](../../knowledge/mechanics/land-camera.md).**
csangle on land is owned by **`manualCamera` (mode 12)**, not a follow spring: the courtyard room
(type 7, styles MM03/FN02) stays in the manual camera the whole window because the TAS holds the
C-stick down (`m144 == 0` routes to mode 12 BEFORE the lock-on branches), with a 1-frame
followCamera blip on each L rising edge. The yaw target moves ONLY with C-stick X (8 deg/frame
shaped by `rationalBezierRatio`); the view globe chases it at 0.66/frame; Link's motion moves only
the camera CENTER. **The session-17 "csangle is EMERGENT from follow springs chasing the
backslide" reading was WRONG** - the observed 116-BAM/frame swings were the TAS's own C-stick
inputs. So for the planner the camera is a directly commanded INPUT channel, not a coupled
dynamic. Port: `tww_sim/core/camera/land_cam.py` (+ `cam_angle.py`), gated fully-chained 0-ULP
over the 120-frame live oracle by `tests/test_land_cam.py` (fixture
`fixtures/courtyard_cam_oracle.json`). Gotchas (decomp-source traps, live style rows, fp details)
are on the truth page. `lockonCamera` / followCamera's main path are unreached in this regime and
deliberately unported.

## Tooling

| File | What |
|------|------|
| `deliver.py` | **THE TIER-2 LIVE DELIVERY (session 54)** -- author a computed plan onto console and read the endpoint. `build_boot_movie` SPLICES the plan onto the recorded BOOT movie (game-frames 0..F0 byte-identical, tail = `log[i]` -> F0+1+i, `bFromSaveState=0`); **both savestate-anchor routes are dead** (see `## Plan / status` s54). `tick_mode='extend'` is mandatory (the recorded tickCount truncates the tail; the maxed 0xFFFF... reads as signed -1 = s53's State::Load crash). `play_spliced` issues ONLY `playmovie` + `savestate load 1` -- the subset-state shortcut that skips the ~9.5-min boot replay (~8 s/run); any pause/resume/advance of ours makes Dolphin re-pause. `deliver_plan` = author+play+read; **`divergence_curve` = TRUNCATE-AND-READ** (author the first N frames, PauseMovie halts at plan frame N-1, so one plain run samples that frame for BOTH actors -- a per-frame sim-vs-console curve with no stepping). Gated `tests/test_tetrapush_deliver.py` (6 offline: round-trip + prefix byte-identity, latched-input equality vs the recording, L/A/B + cal-clamp encoding, the tick_mode invariants incl. the maxed-value crash pin, truncation alignment). |
| `find_tetra.py` | Locate Tetra (Zl1, id 429) live via the DMC walk, `_execute` breakpoint, `r3`. Session-stable (recomputes the REL base). **`tetra_scan` (session 54) = the breakpoint-FREE locator** (one MEM1 block + `field_0x84F == 5` on the courtyard floor Y): required for any endpoint read off a HALTED movie, where the `_execute` bp cannot trap and silently yields nothing. |
| `capture_push.py` | Load slot 2, locate Tetra, single-step the movie N frames, log both actors + FULL pad to a fixture. The (scalar) GROUND TRUTH -- single-stepped, so `+-1` on edges. Now also logs `nspeed` (mNormalSpeed). Subcommand **`capture_push seed`** = a DETERMINISTIC single read of the complete f0 state (no single-step jitter) -> `fixtures/courtyard_push_seed.json`. |
| `fixtures/courtyard_push_seed.json` | The complete STATE-2 seed (f0): pos/travel/facing/speedF + the HIDDEN **mNormalSpeed** (`link.nspeed`) the cyl/dtm fixtures never logged, plus mDirection/m34E6/csangle + the attention state, for provenance. Deterministic single read (jitter-free). The from-f0 replay's `seed_nspeed` source AND the planner's initial condition (session 12). Session 16 added **`old_pose`** -- the live `m_old_fdata` per-joint post-morf pre-twist store (quat x,y,z,w + transform, all 42 joints) + morf counters, the `replay(..., seed_old_pose=)` source (at THIS seed it equals the pure-dash warmup; general-correctness for any f0 with live morf residue). |
| `fixtures/courtyard_plan_s73.json` | **THE PLAN THAT PASSES THE OBJECTIVE** (session 73) -- a complete state-2 input log (71 frames, ending AT THE ARRIVAL because `objective.score_plan` probes the escape atom itself) plus its provenance (which cycle-2 beam node, junction endpoint, roll aim and ``target_cs`` offset) and the ``atom_kw`` it must be scored with. `objective.replay_and_score` on it reads **75 frames (floor 73, timeloss +2), placement 0.4321 u on genuine coord 274, ``complete``/``terminal_ok``/``wall_ok``/``regime_ok``/``within_budget`` all True -> `objective.verdict` TRUE**, with the atom's ``cs_bill`` 0. Gated as a regression (`tests/test_objective.py::test_the_shipped_plan_passes_the_whole_objective_from_its_input_log_alone`), so milestone 2 is a test rather than a session claim. Score it with the fixture's own ``atom_kw``: with the default single-flip atom the same log reads 77 f / pd 4.48, a different escape. |
| `fixtures/courtyard_plan_s73_console.json` | **THE SAME PLAN, ON CONSOLE** (session 78) -- LOCKED. The DELIVERABLE sequence (the plan fixture's 71 herd frames plus the escape atom's own 7, which `score_plan` probes on a clone and so were never in the plan file) and the console-measured Link + Tetra at **22 truncate-and-read samples**, N = 1..78 covering the first frames after state 2, all three herd cycles, the arrival, the scored frame and every atom frame. **Every one is 0-ULP on both actors**, and matches on ``proc``/``facing``/``travel``/``speedF`` besides; Tetra reads stt 3 throughout, so there is NO open frontier and nothing is xfailed (contrast node 1's curve, whose plan left the regime at 83 and hit a wall at 84). Milestone 2 is a console number here: at the scored frame the console's own Tetra is **0.4321 u from genuine coord 274**. Gated `tests/test_plan_console.py` (6 tests, 48 cases) -- and, like every clean-DTM capture, IMMUTABLE: for a fixed input log the console is ground truth and the sim converges to it. |
| `entry_search.py` | **THE SEPARATE ENTRY SEARCH (Dereck s60), and the s45 fork settled by measurement (session 79).** The DUAL of `_generated/tetra_placements.tsv`: the herd is console-confirmed, so Tetra is a MEASURED CONSTANT and the ROLL ENTRY is what gets swept. `tabulated_verdict` is the fork measurement -- standing exactly on `seeds.ENTRY_ROLL_POS` does NOT clip the console's own Tetra (resid **+0.3139 u** against a **1.16e-4 u** window), because her 0.4321 u placement miss is **0.4314 u perpendicular** to the coord thread; route (A) is dead on its premise, not on walk precision. `resid_fn` is the razor's smooth coordinate (the cut ray's offset from the seam vertex S -- the seam PLANES are negative almost everywhere and useless); `acceptance_window` MEASURES the genuine band off the 288 coords rather than assuming it; `genuine_entries` maps the entry locus (coarse residual sweep -> keep near zero -> refine to the f32 dust: blind fine sweeping finds 1 hit in 231k); `locus_metrics`/`entry_gradient` give the shape and the ~1 ULP precision a search must hit; `continue_walk` replays the locked console log and keeps walking (reachability). CLI `{verdict,window,locus,reach}`. Gated `tests/test_entry_search.py` (16). |
| `roll_fidelity.py` | **THE GATE THAT SAYS THE SWEEP IS SCORING THE RIGHT ROLL** (session 80). `walk_then_roll` performs a REAL from-rest walk + A-press turnaround roll + UP+B in the WALLED coupled engine and bakes the same nine tables `extract_schedule_at` does, so the reseed can be diffed per frame against the thing it stands in for. It decides three questions at once: which frame's position and lean the ctx wants (the END of the entry frame -- the pre-entry reading mismatches `chx/chz`), whether the reseed's cold anim/pose state matters (it does not, all nine bit-identical), and whether the armed crash latch matters (a real roll ARMS `_roll_m3570` and does contact the wall mid-roll, but the bonk cone never lines up before the B edge -- 0 of 246 entry x facing rolls differ). Also the honest way to enumerate aims: fire the roll and read the facing back, never trust a commanded one. Gated `tests/test_entry_search.py`. |
| `entry_search.{fast_schedule,roll_entry,aim_alphabet,qualify}` | **THE SESSION-80 SEARCH ENGINE.** `fast_schedule` drops the 22 ms simulated ctx build for a 0.19 ms analytic one, 0-ULP identical over facing x lean x thrust -- the ctx build, not the alphabet, was the whole budget. `roll_entry`/`lean_at_roll` convert a walk endpoint into the entry the game hands you (one 26 u roll step along the AIM, one lean decay tick), both bit-exact; s79 fed the walk endpoint straight in. `aim_alphabet` is 81 wide, not 6 -- the msd 1.0 floor was not physical. And `qualify`/`configuration_band` is the one that matters: of 243 (facing, thrust) configurations only **6** admit a genuine locus, **169** have no leverage at all (grad < 1e-3 -- Tetra out of Co range on the cut frame), and each productive one has its OWN acceptance band, narrower than and offset from the fixture window that is their union. |
| `fixtures/courtyard_entry_locus_s79.json` | **THE ENTRY LOCUS** -- 1735 genuine roll entries for Tetra pinned at her console-measured herd endpoint, at facing 40835 / m351C 0, plus the acceptance window, the fork verdict, the gradient, the m351C sensitivity table and the reachability rows. One thin curve 104 u long; **856 inside the 230 u follow bar** = the usable target, nearest 49.7 u from where the escape leaves Link. DERIVED, not measured -- regenerable by `python -m harness.tetrapush.entry_search locus` (~250 s), pinned so the gates do not pay the sweep. |
| `dtm_inputs.py` | Extract the REAL per-frame raw controller BYTES from the recorded movie `GZLJ01.s02.dtm` (F0=44974 alignment, re-derived) and bake them + the live states into `fixtures/courtyard_push_dtm.json`. The 0-ULP replay input (the sim decodes raw bytes; the pad struct is post-decode/lossy). Session 19: extracts **poll index 2** of each 4-poll frame group -- the poll the game actually latches (live-pinned via the camera oracle on the window's two non-uniform groups); regen with no capture preserves the baked live rows. |
| `fixtures/courtyard_push_dtm.json` | Baked: state-2 seed + per-frame {raw DTM input, live Link proc/speedF/facing/pos, Tetra pos/stt}. Self-contained (no Dolphin/DTM needed to replay). Gated by `tests/test_tetra_untarget.py`. |
| `fixtures/courtyard_push_state2.json` | 51-frame session-1 ground-truth capture from state 2 (repo `fixtures/`). |
| `tetra_plow.py` | **The Courtyard Co-overlap GEOMETRY**: `plow_depth` (`cM3d_Cross_CylCyl` cross_len) + the Link/Tetra Co radii (30/50). The per-frame PUSH LAW is now `from_f0.cc_push_pair`; `plow_step`/`reconstruct` (the session-8 DERIVED full-depth-from-settled law) were RETIRED session 27 (superseded, ~1e-5 u off the console -- git history archives them). Gated `tests/test_tetra_plow.py`: the regime discriminator (frac==1.0) + `test_console_push_bit_exact_vs_deterministic`. |
| `from_f0.cc_push_pair` | **THE console CC push law (session 27)**: `cc_push.co_move_pair` = `dCcS::SetPosCorrect` -- the decomp 50/50 half-depth rank split on Link's EXEC centre, obj1/obj2 EXACT-opposite. 0-ULP vs the deterministic per-op ΔTetra f2..f43. Replaces `full_depth_push` (now the seed-frame f0->f1 fallback only). |
| `link_plow.py` | **The Courtyard Link-recoil LAW** (session 9, now the SEED-frame fallback path): Link's per-frame recoil = the FULL Co overlap depth AWAY from Tetra (`link += depth·unit(link_centre−Tetra)`). `recoil()`/`recoil_step()`, used by `from_f0.full_depth_push` (the f0->f1 seed push). Superseded for f1..f43 by `cc_push_pair`. Gated `tests/test_link_plow.py` (frac==1.0 regime discriminator). Reuses `tetra_plow.plow_depth`. |
| `from_f0.py` | **The from-f0 COUPLED replay** (session 10-12): wires BOTH plow laws (`link_plow`+`tetra_plow`, full-depth) into a closed-loop `LandState` replay seeded at f0 (or a roll entry), driven by the real DTM bytes, Link's mCyl Co centre + csangle INJECTED per frame. Tetra tracked as a bare XZ plow point (stt-3 the whole window). `full_depth_push()` + `replay(..., seed_nspeed=)`. Session 17 refactored the loop into **`FreeRun`** -- the planner's novel-input stepper (seed once, `step()` arbitrary raw inputs; eye/tattn per-step injectables; warns if a stepped state leaves the stt-3 plow regime, dist > `FOLLOW_ENGAGE_DIST`) -- with `replay` a thin wrapper over it. Session 19 wired the MODELED land camera in (`camera=` a seeded `LandCamera`), replacing the csangle injection entirely (see the planner box). **Session 29** closed the f1 seed-frame boundary: `FreeRun(seed_push=)` / `replay(..., seed_push=)` take the exact perop f0->f1 ΔTetra push (`full_depth_push` is now the roll-entry / no-perop fallback), and `step()` rounds the tracked Tetra point to f32 each frame (console storage) -- so the self-contained closed loop from state 2 is now bit-exact in POSITION too, f1..f43, both actors. Gated `tests/test_from_f0.py`: from the roll entry, from **state 2 itself** (dynamics), the one-step-from-exact gates (position f1..f43), and `test_closed_loop_computed_replay_bit_exact` (accumulating position f1..43). **Session 58** pinned the two POSE-STREAM seed facts in `_seed_link`: `SWORD_DRAWN = True` (mEquipItem 0x103 -> the WALKS/DASHS pair) and `defer_draw = True` (the end-of-frame post-posMove draw base). Both are inert until an anim-driven speedF frame and then they ARE the position -- do not "simplify" either away; `tests/test_foot_draw_base.py` fails immediately if you do. **Session 59** added the third: `LOW_LIFE = True` (Link is on his last hearts, so the WAIT stop poses the `ANM_WAITATOB` single, which also resets the re-walk's anim phase); `tests/test_wait_stop_pose.py` is its gate. |
| `fixtures/courtyard_node1_wait_s59.json` | **The WAIT-STOP ground truth (session 59, LOCKED)**: the console's UNDER-BODY ANIM REGISTERS at plan frames 74..78 -- both J3DFrameCtrls (attr/end/rate/frame), the two blend ratios, `m34C3`, `m_anm_heap_under[0].mIdx`, `mModeFlg` -- plus the foot internals and the model-local `mFootData` toes. This is what identified the stop's pose as `procWait_init`'s low-life `ANM_WAITATOB` SINGLE (idx 285, ctrl end/rate/start 12/0.6/0.0 == `mMove.field_0x10/0x68/0x6C`) rather than the WAITS/WALK idle blend everything else in `setBlendMoveAnime` would give. Gated by `tests/test_wait_stop_pose.py` (5): the branch, every anim clock 0-ULP across the stop, the toe stream (x/z, Y excluded like the s57 gate), and the composition state. Probe `_notes/tetrapush-s59_waitscan.py`. |
| `fixtures/courtyard_node1_foot_s57.json` | **The POSE-STREAM ground truth (session-57 footscan, baked + LOCKED session 58)**: the console's `mFootData` model-local toe/heel poses at plan frames 62/64/66/68/69, plus `m3598`/`m359C`/`m35B4`/`msd`/plant. Deterministic truncate-and-read halts. Gated by `tests/test_foot_draw_base.py`: every x/z 0-ULP (Y carries the unmodeled `m35B8` draw-base shift and is excluded, deliberately, so the gap stays visible). This is the gate that discriminates a draw-base / anim-set fault from a composition one WITHOUT a live run -- score a candidate against the toes, not the endpoint. |
| `fixtures/courtyard_push_cyl.json` | Session-8 live ground truth: per-frame Link **mCyl Co-centre** + **csangle** + Tetra pos, single-stepped from slot 2 (`capture_push`). The Co-centre/csangle source the from-f0 replay needs. **Single-step, so cyc2 is edge-jittery** (the `_dedup` in the plow test drops the f44==f45 double-read); NOT a pinned edge oracle. |
| `fixtures/courtyard_push_setcol.json` | Session-14 breakpoint ground truth (f1..f12): at each JP-`setCollision` hit, the nodeMtx root/neck translates + pos/anim/facing AT CALL TIME and the freshly-written **`cyl_exec`**. Pins the mCyl timing law (exec midpoint) + the half-depth settled-centre map. Source probe `_notes/tetrapush-setcol_probe.py`. |
| `fixtures/courtyard_push_perop.json` | **Session-26 DETERMINISTIC per-op ground truth (f0..f43)**: both actors' `current.pos` (+ proc/facing/travel/speedF/shape_z/anim/csangle/`cyl`/`cc_move`/Tetra stt) read at the JP `posMove` (0x80106514) breakpoint, ONE hit per game frame (the bp pins the frame count -- immune to single-step edge jitter). PROVES the cyl POSITIONS are exact 0-ULP over the whole window (`test_perop_confirms_cyl_positions_are_deterministic`), so the two open push/foot bugs are REAL sim-vs-console residuals, not fixture noise. Tetra has no foot term (stt-3), so her per-frame push = ΔTetra (bug-#1 truth); Link's foot term = ΔLink + ΔTetra (recoil = −ΔTetra, same-rank Newton) -- deterministically a CONSTANT 26.0 u/frame during each roll, with the entry-morf RAMP at roll-start (bug #2). Source probe `_notes/tetrapush-perop_probe.py` (advance+breakpoint, NEVER resume). |
| `fixtures/courtyard_push_eyepos.json` | Session-15 live ground truth (single-stepped, f0..f28): Tetra's **eyePos** (fopAc `+0x260` -- her animated head-joint world pos, the `setShapeAngleToAtnActor` aim target), her feet pos, Link facing, and `mpAttnActorLockOn` per frame (non-NULL f8-f20, NULL f21+). The `replay(..., eyes=)` injection source. Probe `_notes/tetrapush-eyepos_probe.py`. |
| `_notes/tetrapush-chain_probe.py` | (gitignored) Session-16 breakpoint probe: FULL 3x4 nodeMtx for the neck-chain joints [0,1,2,3,4,14] at each JP-setCollision hit + `mBodyAngle`/`m351C`/`m34F2/F4`/`m34C2`/`m35E0`/`m35B8` at hit time. The joint-by-joint diff that pinned all four exec-pose laws. Companion `_notes/tetrapush-setframe_probe.py`: the J3DModel BASE TR mtx + `m_old_fdata` morf state + under-blend packs at the f1-f3 hits (the init-frame zero-lean base + the true morf cadence). |
| `fixtures/courtyard_zl1look.json` | Session-20 live ground truth (single-stepped f0..f44): Tetra's FULL look-at state per frame -- the `dNpc_JntCtrl_c` block (chased angles + clamped targets), the McaMorf ctrl (frame/morfs), the look timers (`f7B8/f7BA/f7BC`), anim number, half-angle twists, eyePos/tattn/pos, and Link's `mHeadTopPos`. The `tests/test_zl1_look.py` gate + the `Zl1Look.seed_from_row` shape. Probe `_notes/tetrapush-zl1look_probe.py`; companion `_notes/tetrapush-m3564_probe.json` (Link's head-look state -- the named open gap). |
| `../anim/extract_zl1.py` | Extract Tetra's `zl.bdl` skeleton + the stt-3 BCKs (wait03/look/wait) from `Zl.arc` (TWW-JP) to the gitignored `_generated/anim/zl1_{skeleton,anims}.json` -- the `core.npc_zl1_look` FK data (same policy as Link's `parse_bck`/`parse_bmd`). |
| `fixtures/courtyard_m3564.json` | Session-21 live ground truth (single-stepped f0..f44, baked from `_notes/tetrapush-m3564_probe.py`): Link's head-look `m3564` + `m34DE`/`m34C3`/`m34E2` + `mHeadTopPos` per frame. The `tests/test_neck_look.py` gate + the `NeckLook` f0 seed. Pinned the m34DE frame-START timing + the (3, 0x1000, 0x100) chase knobs (the f0..f5 decay). |
| `onestep_divergence.py` | **The 0-ULP divergence diagnostic** (session 24; console push session 27; f1 closed session 29): reset the sim to the EXACT captured state[k-1] each frame, feed the console push (`cc_push_pair` on the model exec centre; f1 = the deterministic perop ΔTetra seed push), step once, report the per-axis sim-vs-live position divergence in ULP + abs-u. The human-readable form of `tests/test_from_f0.py::test_onestep_pos_bit_exact_from_exact_state`. Now prints **0 ULP on every frame f1..43**. CLI `python -m harness.tetrapush.onestep_divergence`. |
| `seeds.py` | **The planner SEED FACTORY** (session 22, restored session 28, f1-closed session 29): `make_freerun` builds the fully self-contained `FreeRun` (camera + Zl1 look + NeckLook wired, no injections -- the session-21 gate config) from the locked fixtures, now passing the exact f0->f1 seed push (`seed_push_f0` = the perop ΔTetra) so the rollout is 0-ULP in POSITION from f1 (verified: the `make_freerun` self-contained rollout is 0-ULP vs perop over the whole DTM window); `load_placements` loads the 288 genuine `tetra_placements.tsv` coords; `dtm_input_at` is the movie-window input accessor; `load_env` loads the fixture set (incl. `perop`). `make_freerun(tetra_at=)` re-seats Tetra's seed for clean no-contact template rollouts (falls back to the settled-centre approximation, since the recorded push no longer applies). Pure fixture plumbing (no model content). |
| `primitives.py` | **The planner PRIMITIVE LAYER** (session 22, restored session 28): decomposes the bit-exact `FreeRun` window into the search's reusable pieces -- `window_records` (the instrumented rollout: per frame proc/speedF/facing/feet/exec-centre/recoil/plow/depth), `find_cycles` (the cycle spans), `cycle_template` (one cycle in the AIM frame -- foot term + exec-centre offset), and `input_macro`/`macro_inputs` (the cycle's raw-input pattern, stick bytes abstracted so a cycle re-aims to any world angle via `plan_land._primitives.stick_for_bearing`). CLI prints the cycle table + rigidity + the drift diagnostic. Gated `tests/test_planner_primitives.py` (structural). |
| `search.py` | **The exact aim-per-cycle SEARCH foundation** (session 30): `rollout(env, aims)` stitches re-aimed push-cycle macros (`canonical_cycle` = the 26-frame roll-to-roll unit) through the 0-ULP `FreeRun` (C-stick pinned DOWN; main stick re-aimed per frame from the LIVE csangle; the aim is NOMINAL, the achieved landing is read back). `FreeRun.clone` (~0.025 ms, shares anim tables) is the beam branch; `reach_one_cycle` maps the per-cycle reach (the RESONANCE at the recorded aim, ~324 u); `beam_search` is the clone-branched beam ranked by nearest-genuine-coord dist, regime-pruned, each candidate a real FreeRun rollout. CLI `python -m harness.tetrapush.search {selfcheck\|reach\|sweep\|chain\|herd\|turnaround}` -- `selfcheck` proves the 0-ULP round-trip, `herd` shows the CONTINUOUS overlap-push, `chain` reproduces the old re-aimed-macro cycle-chaining blocker, and **`turnaround`** (session 31) reproduces the FRAME-MINIMAL turnaround-roll finding (`cyc1_to_untarget` + `turnaround_reroll`: the A-roll re-rolls THROUGH Tetra from the grounded post-untarget MOVE with no lock/cone gate; an immediate re-roll GRAZES min_ovl ~66 vs the human oracle's DEEP ~40, so the search knob is the minimal camera-assisted reposition, `[[tetrapush-frame-minimal]]`). Gated `tests/test_search.py` (0-ULP: recorded replay, macro re-aim, clone; structural: clean cycle, resonance, beam cycle-1, turnaround-roll fires). |
| `reposition.py` | **The FRAME-MINIMAL reposition primitives** (session 33; Dereck's live steers): `HerdLine` (herd axis + `lead`/`on_line_ok` = the STEER-#1 past-Tetra prune, Link must stay behind her), `l_release_early` (STEER-#2/#3: release the mid-roll lock-L 1 frame early -> a 1-frame untarget tier -> the backslide retains **-25.727** vs the human's -25.454), `turnaround` (the 1-frame INSTANT 180 facing-snap out of the EBS via a precise csangle, `move.py:115`, speed preserved), and `frame_min_reroll` (turnaround -> proc-7 flip -> talk-safe +26 roll, a ~3-frame reposition vs the human's ~10). CLI `python -m harness.tetrapush.reposition {verify\|retain\|chain}` -- `verify` shows the human stays 40-85 u behind Tetra, `retain` shows the -25.727 retention, `chain` runs the frame-minimal cycles (currently OVERSHOOTS -- the roll leaves Link ~15 u off-line: the on-line reposition SEARCH is the open blocker). Gated `tests/test_reposition.py` (5). |
| `native_search.py` | **The native-fleet reposition BFS** (session 38): a beam BFS whose frontier is native `FreeRun` nodes (each wrapping a `LandCore`); a generation is expanded by fanning every (node, candidate-input) child through `CourtyardFleet.run_par` ONE frame in parallel (`batch_step`), syncing the public C fields, pruning off-line/past-Tetra (`reposition.HerdLine`), talk-unsafe (`search.a_press_is_talk`), and out-of-regime (follow) nodes, deduping by a quantized state tag, and keeping the top-`beam` by down-herd progress. `Node`/`reconstruct` record the input chain; `bit_confirm` re-runs the winning plan on a FRESH Python-stepped `FreeRun` 0-ULP. `seed_root` = the state-2 f0 seed (the BFS finds the WHOLE push -- the recorded human's inputs are NOT a valid pursuit template in the stripped sim, see below). CLI `python -m harness.tetrapush.native_search {selfcheck\|search}`. Gated `tests/test_native_search.py` (3: fleet-frontier readout 0-ULP vs a native FreeRun rollout, batch-step == individual, tiny-search prunes on-line + bit-confirms). **KEY FINDING (s38): the stripped sim's +26 roll cannot be an on-line pursuit -- it OVERSHOOTS.** The search finds the continuous glide-push herds Tetra on-line ~12 u/f for ~10 frames then STALLS at along ~148 (Link drifts laterally to +65), and EVERY roll is pruned (overshoots past Tetra). Root cause PINNED (inject the full sim's own csangle to remove it as a variable): the ONLY stripped-vs-full difference is the **roll-entry facing, -102 BAM** (full 35316 vs stripped 35214), the proc-7 re-aim to Tetra's animated **eyePos** (leads her feet 16-26 u) that the stripped config replaces with feet-aim; -102 BAM at entry compounds over the 16-frame locked roll into Tetra diverging 69 u by f18 -> overshoot (stripped) vs pursuit (full). So the on-line-roll chain needs the **zl1 eye-aim ported into the native step** (proc-7/9 re-aim to eyePos), OR the search run in the full Python sim. |
| `steered_reposition.py` | **The REALIZABLE camera-steered reposition primitives** (session 39; Dereck's live design): the validated pieces the frame-minimal branching search is built from -- `camera_authority` (neutral substickX FREEZES csangle; full stick ~+-460..530 BAM/frame -> csangle is a STEERED, not free, channel), `_steered_cyc1` (replay the first roll steering substickX toward a `target_cs` during the locked-roll frames, camera+zl1 ON = realizable + eye-aim), `armed_geometry` (lead/lat/dist/bearing-to-Tetra/talk of an armed EBS -- shows the camera sets FACING not POSITION), `roll`/`recorded_online_metrics` (the on-line self-stabilization evidence: the recorded 2-roll window stays behind Tetra). CLI `python -m harness.tetrapush.steered_reposition {authority\|armed\|selfstab}`. Gated `tests/test_steered_reposition.py` (3, structural). The full architecture (roll = zero-branch camera-steer segment; junctions branch facing/position/release; three coupled controls; on-line self-stabilization) is in the module docstring + the `## Plan / status` s39 box. |
| `steered_search.py` | **The per-cycle branching search + THE HERD-RATE CEILING** (session 40). The s39 design made concrete: a cycle is glide (the EBS reposition, small msd so the -25.7 is retained) -> L-held proc-7 flip -> talk-safe A-roll -> roll, branching at the junctions only, pruned by talk/on-line/regime, ranked frame-minimal. **`push_ceiling`** (CLI `ceiling`) is the session's durable result: the push is a SPLIT of Link's step, so herd <= `\|speedF\|/2` = 13.0 u/f and the human already runs at 12.76 = 98.2% (contact 95%, alignment 0.996) -- a roll is NOT privileged and no reposition can pay for itself. CLI `python -m harness.tetrapush.steered_search {ceiling\|probe\|cycle\|search\|confirm}`. |
| `two_roll.py` | **The 2-roll proof harness + THE SEARCH-SPACE CONTAINMENT GATE** (session 40, re-founded session 41; Dereck's bar: chain TWO rolls above the human's **12.758 u/frame** from state 2). `human_baseline` = the bar. **`reachable_stick_fan`** = the controller's true aim alphabet: the full 256x256 byte grid deduped by DECODED ANGLE (**7032** aims; csangle-independent), replacing s40's inversion through `stick_for_bearing`, whose image is only the maximal-radius octagon-boundary bytes (**544 of 2280** at full msd) -- that narrowing WAS the s40 blocker. `roll_facing_fan` places alphabet members at a csangle via `world_facing`; `roll_stream` = the delivered main-stick/button stream as a pure function of the knobs (`hold`, `a_hold`, `l_window` = the mid-roll L PULSE, `post_l`, `post` -- three stick phases, split at the aim release and the L-pulse end); `roll_segment` rides it with the C-stick as the computed csangle slew (the camera / instant-turnaround setup). **`contains_human`** = the gate that the human's recorded inputs are a SUBSET of what the parameterization can emit (`_fit_roll_knobs` reads his knobs back off the DTM); **`reproduces_recorded_roll`** = the 0-ULP fidelity gate (generated bytes, not his, reproduce both recorded rolls exactly); **`roll_is_stick_inert`** = the measured fact that the main stick does NOTHING inside a FRONT_ROLL. Runs in the full Python sim deliberately (the native fleet passes `has_eye=0` -> feet-aim, the s38 -102 BAM error). **Session 42 chained cycle 2 and CLEARED THE BAR: 12.862 u/f over 46 frames** (see the s42 status box): `run_junction`/`_fit_phases` = the generic inter-roll junction as a PHASE LIST; `ess_fan` = the low-magnitude junction stick alphabet (64 angles -- an 8-direction compass here is the s40 narrowing again); `junction_variants` = the turnaround + human-shaped-swing families; `junction_gates` = the hard endpoint gates incl. the ARMING probe (flip must have fired or the roll is the weak +5); `cycle2_chain` = the two-stage search (fine junction sweep -> roll-2 on kept endpoints, mixed \|lat\|/shortest keep, state-dedup incl. the pending delay-1 input); `reproduces_recorded_chain` = the WHOLE-WINDOW 0-ULP fidelity gate (the generators emit the human's complete f1..f44); `confirm_chain` = the winner bit-confirm on a fresh replay of its own log. Gated `tests/test_two_roll.py` (10 + 1 slow). CLI `python -m harness.tetrapush.two_roll {human\|contain\|fan\|chain}`. |
| `full_herd.py` | **The N-CYCLE CHAIN** (session 43): s42's junction+roll unit composed cycle-over-cycle toward the genuine-coord cluster, every roll sweeping its OWN derived camera grid (`derived_target_css`). `target_cs_is_exit_only` = the measured SEPARABILITY (inside a roll the camera target changes nothing but the camera -- the C-stick counterpart of s41's stick inertness) that lets a cycle factor into aim-sweep + camera-sweep (cycle 1: 159 s -> 10 s, same 13.147 best). `pursuit_box`/`in_pursuit_box`/`human_in_box` = the plow regime measured off the human (lead -40..-85, \|lat\| <= 12, bearing within ~14 deg) + its containment gate. `junction_beam` = the junction as a PER-FRAME beam (atom = one frame's (stick, L); 432 gate-passing endpoints vs the family's 7), frontier ranked by CONE DEFICIT (ranking on \|lat\| is myopic -- the flattest states are the ones still facing Tetra and can never arm). **`roll_probe` = the endpoint keep's real criterion, ROLLABILITY not flatness** (32 of 400 endpoints rollable, none among the flattest -- the cause of the repeated "many endpoints, zero rolls" stalls). `roll_candidates`/`extend_cycle`/`chain_herd` = the staged search; `confirm_plan` = the N-roll bit-confirm; `placement_report` = the endgame score. **Session 44 added THE PLACEMENT ENDGAME**: `terminal_targeting` = the placement-RANKED terminal glide (per-frame beam ranked by Tetra-to-nearest-coord distance, REGIME-only prune since the terminal has no next roll, tracking the global closest at any frame) on the `_terminal_alphabet` (a full-circle push fan at msd {0.08..1.0} -- the mid-mags the junction alphabet lacks); `endgame_report` = the COUPLED score (Tetra->coord dist AND Link->`seeds.ENTRY_ROLL_POS/FACING` gap). Lands Tetra **1.98 u from a genuine coord** (INTO the band), bit-confirmed; the Link-entry gap (159.8 u) is the open joint-solve. **Session 45 added the coupled-entry stage**: `separation_scan` = the measured BARRIER (placement lands at deep contact dist ~47.5 u; every separation step ejects Tetra >= 4.2 u off the thin genuine thread, and the placed state is already the glide's entry-distance minimum -- `clean_separation=False`); `entry_targeting` = the reposition beam (regime + genuine-band pruned, ranked Link->`ENTRY_ROLL_POS`, bit-confirms its whole state-2->placement->reposition log), INERT until fed a grazing-arrival placement (see the s45 `## Plan / status` box); both wired into the `endgame` CLI. **Session 46 quantified the barrier against the decomp bar**: `CO_RADII_BAR` (= `LINK_CO_R + TETRA_CO_R` = 80) + `_centre_feet` (Link's exec Co-centre to Tetra); `separation_scan` now reports `centre_feet`/`deficit`/`freeze_ok` -- the plow ejection is `(CO_RADII_BAR - centre_feet)/2`, ZERO (Tetra FROZEN) at `centre_feet >= 80`, so the s44 placement's `centre_feet 64.6` is 15.4 u below the bar (the deep-contact barrier). Above the bar 2b is a Link-ONLY navigation (Tetra frozen) that the push-fan `entry_targeting` STALLS on (EBS backslide) -- it stays the in-band guard; the reposition wants a WALK planner. **Session 47 BUILT that walk planner + found the barrier's second half**: `walk_to_entry` = the Link-only `reach_precise` glide to `seeds.ENTRY_ROLL_POS` on the coupled `FreeRun` (proportional-speed into a crawl, controller-gain swept, per-frame clone+coast, FOLLOW-regime pruned, Tetra displacement MEASURED), reaches the entry to ~7 u clean; `synthetic_frozen_arrival` mints the above-the-bar frozen placement (`momentum`='rest' clean / 'ebs' hostile) to develop 2b before the grazing chain exists. THE FINDING (corrects s46): `freeze_ok` is POSITIONAL, necessary but NOT sufficient -- the SAME freeze_ok position walks clean (Tetra 0.000 u) from a near-rest arrival but re-plows her ~59 u from a hot EBS (the -25.7 momentum takes ~5 f to bleed off, a turnaround doesn't rescue it), so route a's chain must arrive NEAR-REST / receding up-herd, not just at centre_feet >= 80. **Session 48 built route-a piece 1's rank machinery**: `arrival_quality` = the CHEAP two-halves gate (POSITION `freeze_ok` + MOMENTUM `approach_rate` = Link's velocity toward Tetra via `_link_velocity`/`_approach_rate`; `arrival_ok` = freeze_ok AND on-coord AND approach <= a few u/f) -- the s47 finding as a scalar predictor (rest -0.00 u/f pass, ebs +25.56 reject) agreeing with the walk without running it; `terminal_targeting(objective='grazing')` = the re-ranked terminal (`_terminal_score` adds deficit + closing-approach penalty; placement mode byte-unchanged, `score==dist`) that seeks an on-thread AND freeze_ok AND receding endpoint (cf 61->89, deficit 18.8->0, approach +23.5->-10.8, bit-confirmed). **Session 49 ran route-a piece 1 (the RUN) and root-caused the grazing barrier + gated the recipe**: off the regenerated chain the grazing terminal reaches freeze_ok + receding but lands Tetra 10.85 u off a coord (the deep->freeze_ok separation of the hot -23 glide drags her ~10 u LATERALLY off the thin thread -- frame-by-frame proven). `place_on_thread` = the CLEAN-ARRIVAL RECIPE: from a near-REST arrival behind the coord one gentle down-line push ejects Tetra ALONG the line -> she freezes ON-thread (pd < 1, ~0 lateral drift, arrival_ok). So the barrier is the ARRIVAL MOMENTUM; the next target is a DECELERATING, on-line-centered approach (not the EBS glide). **Session 50 DELIVERED route-a piece 1 -- the DECELERATING on-line placement approach**: `decel_place` = the terminal that BEATS the s49 barrier by inverting its failure mode -- `_reverse_brake` (steer down the herd line at low deflection -> REVERSES the hot EBS, Link coasts to near-rest UP-herd with the plow on-line so Tetra freezes ~0 lateral drift) then an on-line forward `_glide_to_entry` (the walk machinery, aimed `back` u behind the coord, swept) that herds Tetra straight down the thread, `place_on_thread` finishing. On `synthetic_hot_arrival` (the deep-contact hot state the chain terminal produces) it reaches arrival_ok: Tetra pd < 0.13 u ON the coord, lat_drift +0.000 (s49's 10.85 u LATERAL drag GONE), cf 80 freeze_ok, Link at rest -- the miss is now a clean sub-unit ALONG-line residual. **Session 51 CLOSED the OFF-THREAD arrival -- `homing_place`**: `decel_place` herds Tetra straight DOWN the line (needs her already on the thread), so on the REAL 3-cycle chain endpoint it stalled at pd ~41 (the chain leaves Tetra ~28 u OFF the thread laterally, s44's offset). `homing_place` (+ `_homing_glide`) fixes exactly that -- after the same reverse-brake it aims Link each frame at a moving standoff BEHIND Tetra RELATIVE TO THE COORD (`Tetra + standoff·unit(Tetra−coord)`), so the plow (ejects Tetra away from Link's exec centre) pushes her TOWARD the coord in along AND lateral, coast-probing to REST each frame for the clean frozen placement, standoff+gain swept. On `synthetic_hot_arrival(lat_off=±28..40)` (the off-thread testbed, `lat_off` new this session) it lands Tetra pd < 0.1 u ON a coord, freeze_ok, the lateral offset NULLED (arrival_ok), where `decel_place` provably cannot (pd ~ the offset). CLI `python -m harness.tetrapush.full_herd {sep\|box\|plan\|endgame\|walk\|arrivals\|place\|decel\|homing}`; `endgame` prints the ARRIVAL GATE, `place` demos the finish recipe, `decel` contrasts the hot glide vs the on-line decel, `homing` contrasts on-line decel vs homing on an off-thread arrival. Gated `tests/test_full_herd.py` (17 fast + 1 slow), incl. `test_homing_place_corrects_an_off_thread_lateral_offset` (s51, both offset signs), `test_decel_place_beats_the_hot_glide_with_an_on_line_near_rest_arrival` (s50, synthetic), `test_place_on_thread_freezes_tetra_on_the_thread_from_an_online_rest_arrival` (s49 recipe), `test_arrival_quality_gates_position_and_momentum`, `test_terminal_grazing_objective_seeks_freeze_ok_without_breaking_placement_mode`, `test_walk_to_entry_is_clean_from_rest_and_flags_a_hot_arrival` (the momentum finding), `test_freeze_bar_is_the_co_radii_sum` (the decomp-exact freeze law) + the clone-independence gate for the s43 harness bug. **Session 61 wired the OBJECTIVE into the search itself**: `frame_in_model` = BOTH model-boundary prunes in one predicate (the regime `_follow_warned` half that was everywhere, plus the wall half that was nowhere -- now at every junction/roll/terminal site, and measured per frame with the exact metric by `confirm_plan`, which reports `wall_ok`/`wall_margin`/`wall_margin_at` and refuses `ok` without them); `rank_key('bound'\|'rate')` = the beam's ordering, defaulting to `objective.plan_bound` so every stage is frame-minimal AND pays for lateral drift (a herd rate is a down-herd projection and cannot see a lateral miss at all), threaded through `roll_candidates`/`extend_cycle`/`cycle1_nodes`/`chain_herd`; `_budget_cut` drops nodes whose bound is already past the frame budget; `terminal_targeting(objective='frame_minimal')` ranks by the bound and **STOPS at the first frame that satisfies rules 1+3** (in the band with Link still MOVING, `_terminal_ready`), returning it as `placed` -- plus `closest` (min placement distance at ANY frame), which is what to read in that mode since one extra frame costs exactly 1.0 of score and can win back at most 1.0. Also split the junction/roll dead counters by REASON (`followed`/`wall`/`outbox`, `aim_talk`/`aim_no_roll`/`aim_weak`/`aim_offline`/`aim_wall`): "the beam emptied" is not a diagnosis -- and reading them found the s43 "cycle-3 stall", which was `chain_herd` requiring its LAST cycle to be CONTINUABLE (`require_quality` now `(c < ncycles)`; True -> 0 cycle-3 survivors, False -> 7 at bound 74.4-74.7, inside budget). New CLI **`solve`** = chain -> frame-minimal terminal -> `objective.replay_and_score` on the winner's own log: one command for the acceptance test, printing the frame accounting and the endpoint's position on the target thread. **Session 68 fixed the junction FRONTIER, which had been a greedy walk over ONE physics state**: a node's children all share identical physics (the input pipeline acts a frame late), so every frontier key TIED across the alphabet and a stable sort filled all `beam` slots with pending-input variants of one state -- the beam walked a single trajectory, ranked cone-deficit-first, i.e. the fastest TURN out of the talk cone, which is exactly the motion that rotates Link's ~17 u exec-centre lead and spends the push aim (kept aim -12 -> -41 over five generations). `_physics_tag` + `_mixed_beam(group=, per_group=)` + `junction_beam(per_state=, aim_share=)` cap the slots per physics state and give a share to `_armable_square` (|`aim.corridor_aim_error`| and |aim| + the cone deficit in degrees, one scalar so neither starves): squarest armed endpoint off a real cycle-1 exit **-15.34 -> +0.03 deg**, and faster (46 s -> 22 s). `roll_probe` now returns `dict(rate, off, off_rate, n)` -- the corridor offset its best surviving roll DELIVERS, not the endpoint's own aim, because at jf 10-12 the aim swings 5-8 deg/frame and a +1.12 deg endpoint fires a roll landing 37.6 u off with a next junction that arms nothing -- and `extend_cycle`'s `square_keep` ranks its share of `jn_keep` on that. `_probe_pool` names the `probe_cap` truncation (932 square endpoints dropped off one node) and keeps the PREFIX as its default, because every share spent on squareness took cycle 2 from 8 survivors to zero (`square_pool` is the knob). Net on cycle 2: corridor offset 44.9 -> 37.0 u, `plan_bound` 72.92 -> 72.81 f. |
| `objective.py` | **THE OBJECTIVE, as executable predicates (session 60)** -- Dereck's steer turned into what a search prunes and a session reports on, so the bar cannot drift back into prose. `frame_floor` = the all-out-push FRAME FLOOR (nearest genuine coord / the CC-split ceiling `ROLL_SPEED_CAP/2` = 13.00 u/f) -> **73 frames**, accepted `TIMELOSS_BUDGET` +2 = **75**, preferred +1 = **74**. `wall_margin`/`clear_of_walls`/`frame_is_wall_free` = rule 4, the herd-phase wall PRUNE that stands in for the `WallCorrect` the Courtyard `FreeRun` deliberately does not model (Link 35 / Tetra 50, the actors' own cylinder radii; exact, bounding-box-accelerated to ~89 us/call). `in_regime` = `FOLLOW_ENGAGE_DIST`, the stt-4 boundary. Rule 3 (session 66, replacing the s64-falsified `turnaround_ready`): `terminal_moving` = the CHEAP per-frame scalar (Link still moving -- all a beam can afford), `escape_ready` = the EXACT bar (run the s65 escape atom off the terminal state, `away_walk.probe` + `fires`: l_ok, separation, dips <= `DIP_BUDGET`, receding at the cap), probed on winners -- `score_plan(run=)`/`replay_and_score` use it and read placement/frames POST-atom at the slam. `score_plan`/`verdict` score a whole plan; `complete` stops an unfinished window reading as under budget. CLI `python -m harness.tetrapush.objective {bar\|score\|walls}`. Gated `tests/test_objective.py` (17), incl. the console cross-check that the wall metric reproduces the game's own brace point (34.99995 u vs `LINK_WALL_R` 35.0 at the two braced rows) and the pin that node 1's plan violates three rules. **Session 61 added the three things a SEARCH needs from it**, all gated: (1) **`placement_thread`** -- what the target actually IS in the herd frame, and it is not a cluster: a 47.6 u near-straight SEGMENT 12.2 deg off the herd axis, i.e. a LINE (lateral falls 0.216 u per u of along, +7.94 at along 937.5 to -2.27 at 984.1), so a plan has ~46 u of ALONG slack but a ~10 u LATERAL window, and pushing further down-herd TRADES along for lateral rather than fixing it -- surfaced per plan by `score_plan`'s `tetra_along`/`tetra_lat`/`lat_error`/`placeable`; (2) **`plan_bound`/`remaining_frames`** = `f = g + h`, the frame-minimal rank the beams now use (and `bound` in every score); (3) **`replay_and_score`** = the acceptance test from a plan's raw input log alone, replayed from state 2 on the 0-ULP model. `clear_of_walls` is now cell-bracketed (`_cell_distance`, memoised exact distance from each 32 u grid cell's centre brackets every point in it, so the predicate is 16 us/frame instead of 136 and still EXACT, gated against `wall_distance` over 2000 room points). **Session 62 added the LATERAL half of what a finish costs**, all gated: `LATERAL_RATE` (the plow's measured sideways authority, `full_herd.lateral_authority`) + **`thread_frames`** = the fewest further frames to land on the thread with ALONG and LATERAL counted at the rates the plow achieves on each -- the `max` of the two (one push moves both), minimised over WHERE on the 47.6 u segment she stops -- and **`thread_cost`** = frames + that, floored at one frame while rule 3 is unmet. It is a RANK, never a prune (`LATERAL_RATE` is a sustained rate a single frame can beat, so it is not admissible; `_budget_cut` keeps cutting on `plan_bound`). Its measured shape is the reason it is the LAST cycle's rank and not the chain's: mid-chain the lateral is genuinely FREE (39.9 u off-thread at the cycle-2 endpoint costs nothing, because there are more along frames left than lateral ones), and it becomes the binding term only in the last ~70 u. **AND A CORRECTION**: `PUSH_CEILING` 13.0 u/f is the STEADY STATE of the split law, NOT a per-frame law -- the depth is measured to Link's ANIMATED Co-centre, so the human's own 4th frame advances Tetra 18.84 u and a 23-frame search cycle sustains 13.36; the 73-frame floor is therefore asymptotic, not a theorem (Dereck's 75 is a spec either way). |
| `full_herd.junction_authority` | **What the JUNCTION can do to Tetra, and what it costs to use it** (session 64) -- `lateral_authority`'s method one stage earlier, and the measurement that RETIRED session 63's next step. Holds each `junction_alphabet` member and reports both halves: the corridor-offset span reached (**0.79..14.10** / **0.01..9.16** from entry 3.51, i.e. 2.6 / 2.2 u per frame -- real authority, more than the ~9 u the plan needs, with the corridor-good branches clearing every prune at Link lat -7.56 inside the human's envelope) AND the number of held families that ARM, which is **0** with the pursuit box on or off. Arming needs a varying sequence, steering needs a sustained one, so inside the junction the two are mutually exclusive -- and `turnaround_and_flip` from a steered state prices the mechanism exactly (arms 32x, but drags the offset 0.79 -> 12.4-13.1, `preroll` -22.9 against the +17 a flip needs, 0 rollable, 26 junction frames vs a 23-25 frame cycle atom). Gated `tests/test_full_herd.py::test_junction_authority_is_real_and_cannot_be_armed`; ~15 s off one `cycle1_nodes` node, no chain. |
| `away_walk.py` | **The AWAY-WALK escape atom** (session 65; Dereck's recipe: the herd junction's convert-to-positive with the roll replaced by a BACKWARDS SLAM -- "L+up, left/right, slam down"). `escape_atom` = [optional ESS turnaround when the EBS still faces her] -> ONE L frame + the toward-Tetra stick held one more (the proc-7 DIR_BACKWARD negation fires on the next dispatch frame, L already released: **-25.727 -> +17.614 POSITIVE**, motion unchanged -- still placement frames) -> one ~90-deg rotate frame (defeats the genuine-flip gate) -> backwards slam (`procMoveTurn(1)` halves the POSITIVE run onto the reversed travel: **+8.5 up-herd, NO zero crossing**) -> exit stick to the walk cap (f8), stopping at the handoff (receding at 17). Separation = the slam frame; Tetra's residual **34.8-40 u, lat < 9** (the terminal's deterministic undershoot); **3 post-separation sub-17 frames** (`DIP_BUDGET`, the halving dip + two accel frames -- Dereck confirmed the dip is inherent). `probe` sweeps turnaround/rotate-side/exit and ranks L-cone compliance FIRST (an L that locks her = the facing was wrong), then dips, then receding-at-cap, then entry progress. Measured traps in the module docstring (slam-first decays through zero ~12 dips; no-rotate re-fires the negation; side-stick-on-negation-frame reads DIR_SIDE). **Session 66 hardened it for consumption as rule 3**: `fires(res)` = the shared acceptance (l_ok + not followed + **SEPARATED** (`freeze_f` -- a deep terminal can recede at the cap with the centre still inside the 80 u bar, Tetra still taking push; the s66 solve crashed on exactly that state) + dips <= `DIP_BUDGET` + `rec17_f`); the atom runs until receding-at-cap AND separated; probe clones detach a wired camera (`_clone_for_atom`, the commanded-csangle convention -- the csangle used is recorded on the result, its C-stick-slew realization is the camera leg, like the roll stage's `target_cs`); a no-snap-window terminal can still run the NO-turnaround variants on its live csangle. **Session 74 priced its FRAMES**: rows carry ``tstep`` (Tetra's own displacement that frame -- not a ``tres`` difference, which under-reads a turning plow) and `push_profile` reads them against `objective.PUSH_CEILING`. On the shipped 75-frame plan the last ROLL pushes her **12.911 u/frame, 99.3% of the ceiling, over all 19 frames**, while the escape's 4 frames push **9.177, 70.6%** -- profile **16.506 / 0.000 / 12.469 / 7.732**, i.e. the **proc-7 negation frame plows NOTHING** and the slam plows on a halved speed -- so the escape costs **1.18 frames** of the 2-frame timeloss by itself, and what it can RECOVER of the placement is bounded by what it pushes (max over 85192 firing variants: -0.24 u at ``freeze_f`` 1, 22.94 at 3, 34.54 at 4). That is what makes the frame rung a property of the ARRIVAL -- see the session-74 `## Plan / status` box for the ledger. Gated `tests/test_away_walk.py` (10). CLI `python -m harness.tetrapush.away_walk {probe\|trace}` (``trace`` prints the profile). |
| `full_herd.glide_probe` / `lateral_authority` | **The LAST cycle's keep and the measurement behind it** (session 62). `lateral_authority` holds each terminal-alphabet stick for 6 frames and reads the SPREAD of Tetra laterals reached -- the plow's sideways authority, **2.92-2.96 u/f** across contact depths on the synthetic bed (CLI `full_herd lat`, ~20 s) and 3.5-5.9 on the real cycle-3 endpoints, against `PUSH_CEILING` 13.0 for the along axis; that ~4.5x is what `objective.LATERAL_RATE` encodes. GOTCHA: `synthetic_hot_arrival`'s `d_short`/`lat_off` translate BOTH actors rigidly, so no relative measurement moves with them -- sweep `feet`. `glide_probe` is `roll_probe`'s counterpart one stage later: the last cycle keeps endpoints for a TERMINAL, so measure the terminal -- run a short narrow glide (5 frames, beam 4, ~1 s) and rank the endpoint by the best `frames + thread_frames` it reaches. Wired as `extend_cycle(glide_keep=True)`, which `chain_herd` sets on the last cycle only. It DOES discriminate (the s62 cycle-3 survivors span 74.24..87.14, and it demotes the endpoint `thread_cost` likes best) but was **INERT on the s62 beam** -- the top 8 after dedup are unchanged. Gated `tests/test_full_herd.py` (the measurement, the disagreement on two synthetic arrivals, and the wiring). |
| `aim.py` | **THE HANDOFF AIM -- where the last push frames POINT** (session 67), and the module that inverted s63-s66's "lateral deficit" reading. `push_step` = the plow as an **exact one-frame oracle**: ``f32(Tetra + (CO_RADII_BAR - centre_feet)/2 * unit(Tetra - exec_centre))`` is `FreeRun.step`'s next Tetra bit-for-bit on every contact frame (the pipeline acts 2 frames late, so the frame's push is already decided by the state) and exactly 0 at the bar -- so Tetra's side of a placement is analytic and an aim is an exact quantity, not a proxy. `eject_unit` = that ray in herd coords; **`aim_window`** = the directions from a Tetra position that reach the target thread, which is a RAZOR (**0.53-0.62 deg** at the s66 handoff range) because the thread lies 12.2 deg off the herd axis and the approach comes in 13-14 deg off it, i.e. she arrives nearly END-ON; `aim_miss` = how far the current aim misses the 47.6 u SEGMENT, in u, comparable to `objective.PLACEMENT_BAND` (the s66 endpoints: 12.28 / 11.89 / 47.72 u, 10-46 deg steep); `centre_lat_needed` = the same statement as Link's job (his exec centre must sit 9.15 / 10.86 / 40.96 u lower in lateral); `push_reserve` = ``CO_RADII_BAR - centre_feet``, the ejection already stored in the overlap; `landing_miss`/`handoff_target` = the EXACT half and its inverse (where a MEASURED escape residual leaves her, and the handoff a given residual demands -- the chain's target is the coord MINUS the escape's ~44 u: along ~894, lateral ~+2.5); `handoff_spec` = the three numbers in one call. **`corridor_aim_error`** is the same measurement MID-CHAIN, and it is what decides straightness: the push law integrates, so the direction a roll carries Tetra is the mean of its aims (s66 plan, three rolls: mean aim +2.55 / -6.42 / +16.56 deg vs travel +2.98 / -6.36 / +18.13, ~205 u each), the entry aim predicts it to a few degrees, and the human enters his two recorded rolls at +1.22 / -0.70 deg and finishes 44 frames in **0.71 u** off the corridor. The lateral that steers the push is the exec CENTRE's, not the feet's (s66 roll-2 entry: feet +2.22 u off her lateral, aim -10.84 deg). Gated `tests/test_aim.py` (6): the 0-ULP oracle, the razor window, the aim<->centre-lateral inversion, **the terminal alphabet's 2-frame inertness**, the roll-aim law on the HUMAN's own rolls, and the handoff-target round trip. CLI `python -m harness.tetrapush.aim {spec\|beam}`. |
| `full_herd.escape_probe` | **The LAST cycle's endpoint keep, one stage out from `glide_probe`** (session 67): rank an endpoint by what its real ESCAPE lands (`away_walk.probe` -> `aim.landing_miss` + the frames to the slam), because the terminal GLIDE was measured to have no authority over Tetra at all -- the whole `_terminal_alphabet` moves her identically for four frames (`aim`), which is why six terminal rank configurations came out byte-identical across s61-s63. Wired as `extend_cycle(escape_keep=True)` (a rank AND a keep share) and `chain_herd(last_escape=True)`, superseding `glide_keep` on the last cycle; ~2-5 s per survivor. Result on the s66 cycle-2 beam (461 s, no chain): 21 survivors, **18 fire, best lands 45.62 u off the thread**, and the keep is INERT (byte-identical 8 nodes) -- the right metric, proving the cycle-3 stage cannot reach the handoff. |
| `full_herd.junction_square_probe` / `cycle1_nodes(square_keep=)` | **THE CYCLE-1 EXIT'S KEEP -- what squareness its junction can still DELIVER** (session 69), the stage s68 pointed at with "squareness is a property of the cycle EXIT". Run the exit's junction at a coarse budget and report the smallest `objective.push_corridor` offset any surviving roll delivers (`roll_probe`'s ``off``; never the endpoint's own entry aim -- s68 measured that swings 5-8 deg/frame at jf 10-12). ~15-25 s per exit; cycle 1 has ~21 unique ones, so it costs 308 s ONCE per solve. It exists because the cycle-1 candidate set is **one roll aim swept over the 25-value `derived_target_css` grid** -- measured: of the whole fan x 3 l_windows exactly 3 (aim, window) pairs survive and all three are the same aim, and every candidate scores `plan_bound` **71.90**, so the frame rank cannot separate them at all. Only 6 of the 25 arm anything, and their deliverable squareness spans **11.20 .. 141.83 u**; the old ``tcs_keep=3`` cut by `junction_quality` (frames in the box) and kept 141.83 / 27.81 / 14.67, with the best at quality rank 5. **The POOL is what makes the probe honest** (`_probe_pool(spread=False)`): on three real exits prefix-only reads `1.34 / none / 27.02`, squarest-only `none / 141.83 / 14.67`, the uncapped mix `1.34 / 141.83 / 14.67` (12 rollable where each single pool found 9), and s68's state-CAPPED pool `none / 141.83 / 25.89` -- it calls an exit that reaches 1.34 u unrollable, so that cap is the one thing not to reuse here. Result on cycle 2, same config and 75-frame budget: corridor offset **37.00 -> 8.97 u**, Tetra lat **-32.10 -> -3.65**, Link's lateral off her **+11.14 -> -0.69**, `plan_bound` 72.81 -> **72.69**, roll survivors **18 -> 71** (964 s vs 516). Gated `tests/test_full_herd.py` (+2: the pool as pure selection, and a slow contrast that the squarest exit is one the old cut drops and the keep keeps). |
| `aim.handoff_corridor` | **The line the CHAIN must ride, which is not the line to the coord** (session 69) -- `objective.push_corridor`'s shape (``target``/``slope``/``lat_at``/``offset``) aimed at `handoff_target` instead, so every keep that reads a corridor rides the state the chain must DELIVER. The residual is measured, never assumed: probe the real escape atom on an on-line mid-depth arrival at the thread's near end (feet 56 -> resid **43.65 along / +5.47 lat** -> target along **893.89** lat **+2.47**, reproducing s67's solved-backwards "along ~894, lat ~+2.5"), and report ``ok=False`` rather than guess if the atom does not fire. The two lines ask an on-line Tetra for aims **0.46 deg apart at the cycle-1 exit, 0.68 at cycle-2 range, 1.19 by along 700** -- it GROWS as the plan closes. Depth is a knob inside the noise (feet 52..64 moves the ask 0.04 deg, 1/17th of what ignoring the escape costs). Wired `chain_herd(handoff=True)` -> `cycle1_nodes`/`extend_cycle(corridor=)`. **Measured INERT at cycle 2** (identical 8 survivors; the frontier's dead counts and the cycle-1 probe values do move -- best exit 11.20 -> 7.93 u), kept ON because it is the correct target and the bias grows. Gated `tests/test_aim.py`, which also pins WHY it matters: the razor is a property of where the handoff sits, not of the thread -- from the s66 handoff (along 881.6 lat +21.19) the 47.6 u segment is nearly end-on and the window is **0.53 deg**, from the handoff target it subtends **10.04**. |
| `full_herd.square_probe_key` / `CHEAP_PROBE` | **The tcs cut's mid-chain keep, and the CALIBRATION that overturned the plan it came from** (session 70). Session 69 handed over "give `junction_quality`'s glide an AIM-aware key" for cycles >= 2. Cycle 1's 25-exit grid is fully probed, so the proxy was calibrated against the truth BEFORE being wired -- and an aim key is not merely no better, it is the worst of the candidates. Keep of 3, what it DELIVERS in corridor offset: stock `(-inbox, |lat|)` **14.67 u** (best at rank 5), `(-inbox, glide |aim|)` **116.93** (rank 7), `(-inbox, glide |aim|+cone)` **116.93** (rank 4), `(-inbox, exit |aim|)` and exit-aim-alone **NOTHING** (rank 19), the CHEAP probe **11.20** (rank **1**), the full probe 11.20. The reason is structural: **18 of the 25 exits sit at |aim| 1.26-2.05 deg and not one of them can roll at all** -- every exit that delivers anything measures |aim| >= 3.0 -- so the cheapest scalar that looks like squareness ranks the dead exits first. What IS affordable is the same `junction_square_probe` at a coarser budget (`CHEAP_PROBE`: max_frames 5, beam 8, ess_step 3, aim_step 48, cap 12, step 48, per_state 2 -- **~2.7 s against ~21 s**), because coarseness costs RECALL, not precision: it scores only 2 of the 6 armable exits, but both are real, they are the full probe's **#1 and #3**, and on the one it ranks best its value is **bit-identical** to the full probe's (11.200566297610363). It declined every exit the full probe also calls dead. (The 9.6 s budget does NOT have that property -- it reported 59.97 and 100.74 on two exits the full probe calls unrollable, which is why the cheap budget is the small one.) Wired as a KEEP share (`roll_candidates(tcs_probe=)`, `extend_cycle(tcs_square=)`, `chain_herd(mid_square=)`, default OFF at ~2.7 s per surviving (aim, tcs) pair). Gated `tests/test_full_herd.py` (slow). |
| `full_herd.landing_key` | **The LAST cycle's tcs cut, which was ranked by a question that cycle does not have** (session 70). `junction_quality` asks whether the NEXT junction can continue from a roll's exit; the last cycle has none -- `extend_cycle` already turns the GATE off (``require_quality=False``) and s43-s69 left the ORDER ranked by it anyway. Its exit IS the handoff state, so rank it by where the escape lands from it: `objective.thread_frames` of `aim.landing_miss` (the exit plus the MEASURED residual), free to compute and the same prediction `escape_probe` then confirms with the real atom on the survivors. The contrast is measured on real arrivals: `rank_key('thread')` scores an arrival sitting ON the coord -- 44 u past the state the escape needs -- as its **BEST (0.00 frames)** and one at the handoff target **3.36 worse**, because the thread's 47.6 u of along slack charges nothing for along inside it; `landing_key` reverses that, and the exact landing says which is right (the escape from the coord position overshoots the thread by **14.54 u**, from the handoff target one by **5.47**). Wired `chain_herd(last_landing=True)`, default ON. Gated `tests/test_full_herd.py`. |
| `full_herd.roll_probe(target_along=)` / `aim.handoff_rows` | **THE OVERSHOOT, priced in the keep and in the rank** (session 70). A cycle's roll is a ~205 u atom that cannot stop short, so where a plan FINISHES is decided when its last endpoint is chosen -- and nothing ranked that: s69's cycle-3 endpoints landed Tetra at along **947** against a `aim.handoff_target` of **894**, ~4 frames of push spent going past and then paid back in lateral, which is that run's whole **78-80 against a 75-frame budget**. `roll_probe` already fires the entire aim fan, so the along its rolls DELIVER costs nothing to report: ``arrive`` = the smallest |delivered along - target| any surviving roll reaches, ``over`` its signed value, purely additive (rate/off/n unchanged). A share of `extend_cycle`'s endpoint keep goes to it (``arrive_keep``, `chain_herd(last_arrive=)` default ON, LAST cycle only -- measured, from a cycle-2-range endpoint every surviving roll undershoots by ~300 u, so there the keep is inert by construction). `aim.handoff_rows` is the rank-side twin: the whole placement set translated up-herd by the measured residual, an exact translation (slope/length/off-axis/chord-dev identical, near end == `handoff_target` to the last digit) that drops into any ``placements=``, so `rank_key(resid=)` prices arrival at the handoff -- against the shifted thread the s69 overshoot costs 0.54 frames where the real thread paid it 1.0 for going past. NEVER passed to the admissible budget CUT. Gated `tests/test_aim.py` + `tests/test_full_herd.py`. |
| `away_walk.snap_bill` / `full_herd.camera_probe_key` | **THE ESCAPE'S CAMERA BILL, AND THE STAGE THAT PAYS IT** (session 73). The atom's turnaround needs the csangle inside its snap window and its own C-stick is neutral, so it cannot slew there -- yet `escape_atom` simply COMMANDED the value, and `snap_csangle` scanned from csangle 0 and returned the FAR edge of a window that is **78.8-81.6 deg wide**: 91.3-113.8 deg off live on every one of 112 real arrivals, which is the camera state every atom number from s65 to s72 was computed at. The NEAREST member is **15.3-37.8 deg** (median 21.0) and one roll's C-stick slews **-46.6..+40.7**, so the bill fits in the LAST ROLL's otherwise idle camera channel. Now: `snap_csangle(near=True)` returns the near member; `escape_atom`'s ``csangle`` defaults to the arrival's own LIVE value (replay-faithful -- the neutral C-stick holds it) with ``'snap'`` an explicit mode and ``cs_bill`` on every result; `snap_bill` reports what is owed; and the last cycle's grid widens `TCS_SPAN` -> `ESCAPE_TCS_SPAN` with `camera_probe_key` as a keep share on the bill (`extend_cycle(tcs_escape=)`, `chain_herd(last_camera=)`, default ON, ~free). **63 of 112 arrivals then owe nothing** (0 do at the shipped neutral camera) and the faithful frontier beats the commanded one: **75 f, pd 0.432 u, `objective.verdict` TRUE** against s72's 1.644 at the same 75. A KEEP and never a filter, measured: over 656 (arrival, tcs) cells 274 fire and only 12 snap, so a filter would drop 96% of the firing states, while a keep of 3 by the bill retains a best-bound cell for 13 of 14 arrivals at median 0.00 frames of loss (the front-cone margin retains 7 / 3). Gated `tests/test_away_walk.py` + `tests/test_full_herd.py`. |
| `away_walk.recovery_row` / `fires_census` / `snap_reach` | **THE THREE MEASUREMENTS THE LEDGER WAS BEING RUN WITHOUT** (session 77). `recovery_row` is the producer `objective.along_floor`'s ``recovery`` never had: every variant of the knob grid bucketed by ``freeze_f``, both populations, in the ledger's own currency -- it re-derives BOTH banked arrivals of `fixtures/courtyard_arrivals_s75.json` **0-ULP**, so s75/s76's rows stop being a scratch script's word, and the "never borrow a row across bands" rule finally has something to measure with. It is a BUCKET and not a new rank: at a fixed arrival ``pd_pre`` is constant, so max-recovery is the same order as min-landing (``rank='miss'``); what it adds is the per-``freeze_f`` split, since ``total = arrival_frames + freeze_f``. `fires_census` decomposes `fires` into its five clauses (`FIRES_CLAUSES`, gated EQUIVALENT to it) and reports which one refuses plus the SOLE-blocker count -- because "0 of 672 variants fire" is a count, not a diagnosis, and on the live bands the answer is ``l_ok`` on **all 672** with nothing else down on 239-364. `snap_reach` is why that cannot be bought: it sweeps the channel that would actually PAY (the previous roll's ``target_cs``) and reports the ``(csangle, travel)`` states it delivers -- **0-1 of 110 snap where the same csangles COMMANDED on a travel-frozen state snap 9-10**, because travel chases csangle and ``want - travel`` has an 87 deg hole exactly where the window is. Ask it before spending a session on the camera; `snap_bill`'s 29 deg can be unpayable at any price. Gated `tests/test_away_walk.py` (+4, 2 ``slow``) on `fixtures/courtyard_snapreach_s77.json`; the mechanic is `knowledge/mechanics/ebs-turnaround.md`. |
| `beam_io.py` | **The CHEAP-ITERATION path** (session 61): dump a search beam to JSON and rebuild it BIT-EXACT. A node's identity IS its delivered input log (`confirm_plan`'s own convention), so a beam round-trips through plain JSON with no simulator state to serialise, and `rebuild_beam` (~0.3 ms per logged frame) hands back live nodes `extend_cycle`/`terminal_targeting`/`confirm_plan` accept. Use it instead of re-running the ~475 s stages that produced a beam -- session 61 burned ~25 minutes of search on a one-expression bug for want of this. Gated `tests/test_full_herd.py::test_a_dumped_beam_rebuilds_bit_exact_from_its_input_logs` (fingerprint equality + the rebuilt node confirming). |
| `feasibility.py` | **The COARSE-FEASIBILITY report** (session 28): from the bit-exact 2-cycle window, answers "can a few push cycles herd Tetra the full ~960 u to the genuine-coord cluster, in-regime?" -- directional (herd bearing vs target bearing), per-cycle reach, and the plow-regime bound. VERDICT: CONFIRMED (0.2 deg direction match, ~3 cycles, dist 40-85 u < engage 230). All numbers recomputed live. CLI `python -m harness.tetrapush.feasibility`. |
| `_notes/tetrapush-camoracle_probe.py` | (gitignored) Session-18 land-camera ORACLE probe: run A re-captured with the FULL dCamera_c block (0x520 B, incl. mEventFlags/mCurStyle/mCurType), player status words, attention lockstate, both actors' `attention_info.position`, and the pad main-stick angle. Baked to `fixtures/courtyard_cam_oracle.json` (the `test_land_cam.py` gate). |
| `_notes/tetrapush-eyeindep_probe.py` | (gitignored) Session-17 A/B probe: two 120-frame runs from slot 2 diverging only in post-f48 inputs; logs both actors + csangle + the RAW `dCamera_c` block (0x450 B/frame). DISPROVED the eyePos input-independence shortcut (offsets diverge f51, both runs stt 3); run A doubles as the extended csangle + camera-spring ground truth (f0..f120) for the camera port, and run B pins the stt-3->4 follow flip (crossed 230 at f63, stt 4 at f75). `.json` beside it. |
| `_notes/tetrapush-reticle_probe.py` | (gitignored) Live per-frame dump of the attention lock lifetime: `mLockOnState`, `mpAttnActorLockOn`, `field_0x01a`, and the reticle `YJ_DELETE` frame ctrl. The ground truth behind the session-6 `FADE_FRAMES=10` + delay-1 findings. Also `_notes/tetrapush-{live_lock_probe,bp_setnormalspeedf,verify_2frame}.py` (session 5), `_notes/tetrapush-retarget_probe.py` (session 11), `_notes/tetrapush-seed_probe.py` (session 12: reads the hidden f0 seed fields -- mNormalSpeed/mDirection/attention -- that pinned the true-f0 seed as a speedF-lags-mNormalSpeed gap), and `_notes/tetrapush-{upper_probe,anmmtx_probe}.py` (session 13: the upper anim part / mBodyAngle state and the live `mpNodeMtx` root+neck matrices + `.json` dumps -- the ground truth behind the body-Co FK validation + the open mCyl timing law). |

Run: `python -m harness.tetrapush.capture_push frames=60` (needs Dolphin up with slot 2 = the
courtyard push; `harness/dolphin_env.ensure_running` if not). Reads/writes RAM via `dolphin_mem`
(`../../tools`) only, self-contained.

## Addresses / offsets (JP GZLJ01)

- Link `daPy_lk_c` this = `[0x803AD860]`; **fopAc base = this - 0xD8**.
  proc `[this+0x3100]` (s32); anim frame ctrl `[this+0x2F64]`; mRate `[this+0x2F60]`.
- fopAc fields (both actors): current.pos `+0x1F8`, travel(current.angle.y) `+0x206`,
  facing(shape_angle.y) `+0x20E`, speedF `+0x254`.
- Tetra `daNpc_Zl1_c`: stt `field_0x84B`, type `field_0x84F` (==5 following). Instance this session
  `0x80ace20c`; `_execute` `0x80f4cb9c` (REL base moves per load, recompute).
- Pad `g_mDoCPd_cpadInfo[0]` @ `0x80398308`: px `+0x00`, py `+0x04`, value `+0x08`, angle(s16) `+0x0C`.
- daPyProc: 6 MOVE, 7 ATN_MOVE, **8 ATN_ACTOR_WAIT, 9 ATN_ACTOR_MOVE**, 30 FRONT_ROLL.
- **Attention lock (session 5, decomp header offsets are fopAc-base-relative = `la = this - 0xD8`):**
  `mpAttnActorLockOn` = `this + 0x30C4` (header `0x319C`) -- the proc-9 driver, non-NULL iff the
  actor-lock is live; `mpAttention` = `this + 0x33A8` (header `0x3480`) -> deref the `dAttention_c`
  instance (this run `0x80ac...`); attention `mLockOnState` `+0x18` (u8: 0 NONE/1 LOCK/2 RELEASE),
  `mFlags` `+0x20` (u32; `AttnFlag_40000000` = reticle fade alive), reticle `draw[0].anm` `+0x038`.
  `mMaxNormalSpeed` = `la + 0x2A8` (12 locked / 17 unlocked); `mNormalSpeed` `la+0x35BC`;
  `mStickDistance` `la+0x35B0`; `m34E8` (target) `la+0x34E8`.
  - **Attention detail (session 6):** `field_0x01a` `mAttention+0x1a` (u8, `judgementButton` L machine:
    0 off / 1 rising / 2 held -- delay 1 from the raw pad, one less than physics `INPUT_DELAY=2`);
    `field_0x028` `+0x28` (s8). Reticle `draw[0].anm` `+0x38` = `mDoExt_McaMorf*`; its `J3DFrameCtrl`
    is at McaMorf `+0x58` -> `mEnd` (s16) `+0x60`, `mRate` (f32) `+0x64`, `mFrame` (f32) `+0x68`,
    `mState` (u8, 0x1 STOP) `+0x5D`. `YJ_DELETE` (untarget fade) = `end 10 / rate 1.0`; `YJ_IN` end 13,
    `YJ_SCALE` end 34. The anim completing (frame->10) clears `AttnFlag_40000000` -> RELEASE ends.
  - **Re-target state (session 11, `_notes/tetrapush-retarget_probe.py`):** `m34DC` (stick want-angle,
    `= mMainStickAngle + 0x8000`) `la+0x34DC` (u16); `m34E8` (world target `= m34DC + csangle`) `la+0x34E8`;
    `mDirection` (the ATN branch selector) `la+0x34B8` (u8). The probe read these + the delivered pad
    per single-step frame and found `m34DC[k] = DTM_inp[k-1]` UNIFORMLY -- the stick target, the roll-A,
    and the soft-lock L all land exactly 1 frame after the DTM stream (because the DTM IS the polled
    `g_mDoCPd` pad, already one pipeline stage in). This is why a DTM replay runs at `input_delay=1`
    (see the `## Plan / status` roll-setup box) and the raw-controller default is 2.
- **JP GZLJ01 function addrs (framework.map):** `setNormalSpeedF` `0x80105ae0`, `setSpeedAndAngleNormal`
  `0x80107474` (+0x498), `setSpeedAndAngleAtnActor` `0x80107b24` (+0x108), `procMoveTurn_init` `0x80111874`,
  **`daPy_lk_c::posMove` `0x80106514`** (break here to read Link's `m_cc_move` before it's consumed --
  the clean way to pin the CC-split doubling), **`dCcS::SetPosCorrect` `0x800ab1e4`** (confirmed halting,
  session 9 -- the Co push split; note MANY scene Co pairs hit it, identify the Link-Tetra pair by ppos
  centres ~ Link Co (-1310, 61) / Tetra feet (-1337, -1)).
- **Anim parts + body angles (session 13; `la = lp - 0xD8`):** `mBodyAngle` (csXyz s16) `la+0x2B4`
  (`.z == shape_angle.z` per :9526; x/y = attention twists, 0 all window); `mAnmRatioUnder` `la+0x2FB4`
  (2 x {f32 ratio +0, anm* +4}), `mAnmRatioUpper` `la+0x2FC4` (3 packs); `mFrameCtrlUnder` `la+0x302C`
  (2 x J3DFrameCtrl 0x14: rate +0xC, frame +0x10 -- so lp+0x2F60/0x2F64 == ctrl0), `mFrameCtrlUpper`
  `la+0x3054` (3 ctrls); `mpCLModel` `la+0x32C` -> `mpNodeMtx` (J3DModel +0x8C, 0x30/joint; translate
  col +0xC/+0x1C/+0x2C) = `getAnmMtx`. **JP `setCollision` = `0x8011a670`** (`setCollision__9daPy_lk_cFv`,
  framework.map; US 0x8011D788), sole caller `daPy_lk_c::execute+0x119c` (LR `0x8011f8ec`), once per
  frame. The dCcS immediate half-depth writer to `lp+0x4064` traps with LR `0x800ab5d0` (session-14
  watchpoint; probe `_notes/tetrapush-setcol_probe.py`, baked to `fixtures/courtyard_push_setcol.json`).
- **Session-16 exec-pose fields:** `m_old_fdata` (`mDoExt_MtxCalcOldFrame*`, header 0x31B4) =
  `lp + 0x30DC` -> deref: flg `+0`, morf counter `+4`, f8 `+8`, rate `+0xC`, f10 `+0x10`, f14
  `+0x14`, start/end joint `+0x18/+0x1A`, `J3DTransformInfo*` `+0x1C` (0x20/joint: scale +0,
  rot s16x3 +0xC, trans +0x14), `Quaternion*` `+0x20` (0x10/joint, **x,y,z,w order**). The J3DModel
  base TR mtx = `[la+0x32C] + 0x24` (Mtx 3x4 -- how the init-frame zero-lean base was pinned).
  NOTE the morf counters read at a setCollision hit are POST-calc (the last-joint dec already
  fired); the rate the calc USED is one dec earlier.
- **Session-15 pose/aim fields:** fopAc `eyePos` = fopAc `+0x260` (cXyz; any actor -- Tetra's is her
  animated head-joint world pos, the proc-9 re-aim target). Link waist twist `m34E0` `la+0x34E0`
  (s16; jointBeforeCB WAIST_JNT=30 z-rot, LEGS subtree only; f0 residual 1325 decaying
  addCalcAngleS(2,0x800,0x200) to 0 by f3); `m35B8` `la+0x35B8` (f32, footBgCheck draw-base Y shift;
  f0 -5.198 -- the anmmtx-probe root/neck Y offset, XZ-irrelevant, still unmodeled: it is the
  residual Y in the `courtyard_node1_foot_s57` toe gate); equipped item `m3562` `la+0x3562`
  (u16; 0x103 = sword DRAWN, true the whole courtyard window -- so `getAnmData` poses **WALKS/DASHS**,
  which IS the position wherever `m3598 != 0`; see `knowledge/model/equipped-anim-set.md`); `m34EC`
  (extra draw yaw) + `shape.x` `la+0x20C` both 0 all window.
- **dCamera_c (session 17, decomp US GZLE; chain base = `[[0x803AD380]+0x34]` = `camera_class`):**
  `dCamera_c` = `camera_class + 0x244`; `mAngleY` (cSAngle, == csangle) `+0x6C` (chain `+0x2B0`, as
  already used); `mDirection` (cSGlobe `mEye-mCenter`) `+0x008` -- radius f32 `+0`, `mAzimuth`
  (elevation!) s16 `+0x04`, `mInclination` (the HORIZONTAL yaw; the old RE's "+0x0E yaw") s16
  `+0x06`; `mWork` union (follow/lockon spring state) `+0x378` (`m3AC` yaw-offset accum `+0x3AC`,
  `m3B8` yaw rate, `m3E0` pitch gain, etc.). Engines: `followCamera` (mode 0, style `FN08`),
  `lockonCamera` (mode 2, while `LockonTruth()`), committed by `bumpCheck`; `mAngleY` written at
  `Run` d_camera.cpp:905. NOTE the decomp header's cSGlobe SETTER bindings are wrong; binary truth U=yaw(+6), V=elevation(+4) both accessors (see `## The land camera`).
- **Zl1 look-at fields (session 20; `z` = the Tetra actor base from `find_tetra`):** `m_jnt`
  (`dNpc_JntCtrl_c`) `z+0x290` -- `mAngles[2][2]` s16 `+0x290..0x296` ([head][x,y] then
  [bbone][x,y]), `mbTrn/mbHeadLock/mbBackBoneLock` u8 `+0x29A/B/C`, min/max/step tables
  `+0x29E/0x2A6/0x2AE`, targets `f2C/f2E/f30/f32` `+0x2BC..0x2C2`; `mpMorf*` `z+0x330` ->
  McaMorf frame ctrl attr/state/start/end/loop/rate/frame `+0x5C/5D/5E/60/62/64/68`,
  cur/prev/step morf `+0x74/78/7C`, `mpAnm` `+0x54`; look fields `f849` (anim) `z+0x849`,
  `f84D` `z+0x84D`, timers `f7B8/f7BA/f7BC` `z+0x7B8/BA/BC`, wrap flag `f7C3` `z+0x7C3`,
  `mFrame` `z+0x78C`, half-angles `f83C/f83E` `z+0x83C/3E`, eye pre-copy `f74C` `z+0x74C`,
  last target `f758` `z+0x758`, base angle `f73E` `z+0x73E`; eyePos fopAc `+0x260`,
  `attention_info.position` `+0x274`. **Link:** `mHeadTopPos` `la+0x2BC` (= exec
  `anmMtx(15)*(40,0,0)`, :11592); head-look `m3564` (csXyz) `la+0x3564` (modeled session 21,
  `tww_sim/land/neck_look.py`).
- **CC push + camera (session 8, live-found 2026-07-22; `this` = deref `0x803AD860` = `lp`):**
  Link body **Co cylinder centre** = `lp + 0x4064` (cXyz; radius `lp+0x4070` = 30.0, height `lp+0x4074`
  ≈ 104.6; the `lp+0x4044` block is the derived AABB, `centre ± (r,0,r)`/`+(0,h,0)` -- how the centre was
  confirmed). This is the ANIMATED `setCollision` root/neck midpoint (`d_a_player_main.cpp:9748-9754`),
  the actual dCcS push centre -- NOT `current.pos` (leads the feet 6-28 u through the backslide/roll
  pose). `mStts` (weight/`m_cc_move`) is `lp+0x3FE8` (header 0x3FE8; `m_cc_move` cXyz +0x00, reads 0 at a
  frame-boundary pause = post-consume; `m_weight` +0x14). `shape_angle.z` (the `m351C>>1` lean) = `la+0x210`.
  **csangle** (`dCam_getControledAngleY`) = pointer chain `[[0x803AD380]+0x34]+0x2B0` (u16).

## Plan / status

- [x] **Ground truth captured** (state-2 seed + 51 push frames to the fixture).
- [x] **Push mechanic characterized** (roll to ATN_ACTOR untarget-EBS to re-roll; plow + follow herd).
- [x] **Model the untarget brakeslide** (ATN_ACTOR procs 8/9 + the attention lock-on state machine),
      decomp-first (session 2). `tww_sim/land/attention.py` = the `AttentionLock` (NONE/LOCK/RELEASE,
      hold mode, animation-driven untarget latency); `tww_sim/land/procs/atn_actor.py` =
      `setSpeedAndAngleAtnActor` (the DIR_BACKWARD negation + `setShapeAngleToAtnActor` re-aim);
      `checkNextMode` routes the roll exit to proc 9 while `_atn.locked`. Purely additive -- inert
      without a driven lock-on actor, so all 16 land goldens + the full offline suite (438) stay green.
      Gate: `tests/test_atn_actor.py` (11 offline invariants: state machine, routing, the negation
      flip + re-aim, additive inertness -- ALL exact/0-ULP against pinned model outputs, no tolerances).
      **NOT yet live-0-ULP-validated** (that is the next box); the flip physics are decomp-faithful and
      the model produces the right shape, but the magnitude is only validated against the MODEL, not live.
- [x] **Validate sim vs live from state 2**, 0-ULP -- **CLOSED for cyc1 (session 10):** the from-f0
      coupled replay (below) validates the untarget flip AND body2 **0-ULP** from the clean roll-entry
      seed (`test_from_f0.py`: flip -25.727313995361328, body2 -25.452238082885742, both bit-exact),
      resolving the "body2 ULP-exact awaits the from-f0 replay" residual noted below. The
      untarget-brakeslide FLIP is validated
      BIT-EXACT for BOTH cycles (session 3), and (session 4) it stays bit-exact under FULL Tetra
      coupling. Session 5 RAM+asm-proved the untarget brakeslide is a **2-frame proc-9
      (`ATN_ACTOR_MOVE` / `setSpeedAndAngleAtnActor`) tier** in BOTH cycles -- body1 = the flip
      (-26 + the ATN speed term ~0.273 -> -25.727), **body2 = a SECOND `setSpeedAndAngleAtnActor`
      frame** (no re-flip; travel chases the target, +ATN term ~0.26-0.275 -> -25.452 / -25.486) --
      and ONLY THEN does MOVE decay it ~0.0095/frame; the sim ran proc-9 body ONCE because the
      actor-lock (`mpAttnActorLockOn`) dropped **one dispatch-frame too early**.
      **Session 6 CLOSED that gap** -- the actor-lock lifetime is now modeled decomp-faithfully and
      the sim runs the **2-frame proc-9 tier from the REAL `AttentionLock`** (no RAM-timeline
      injection): the sim's per-frame lock timeline now matches the live RAM `mpAttnActorLockOn`
      bit-for-bit (LOCK f8-10, RELEASE f11-20, drop f21 cyc1; LOCK f32-36, RELEASE f37-46, drop f47
      cyc2 de-duplicated), the **flip stays bit-exact**, and body2 lands (off ~0.0024, the mid-roll
      seed -- ULP-exact awaits the from-f0 replay). Two decomp-grounded fixes did it (both LIVE-
      measured, no guessed constants):
      - **The untarget latency is the reticle `YJ_DELETE` J3D anim = exactly 10 frames** (`end=10`,
        `rate=1.0`, `EMode_NONE`), read live from the reticle frame ctrl at `mAttention+0x38`
        (`draw[0].anm`, a `mDoExt_McaMorf*`; frame ctrl `+0x58` -> `mFrame +0x68` / `mEnd +0x60`).
        `runDrawProc` sets it on the LOCK->RELEASE frame and clears `AttnFlag_40000000` when it
        completes -> RELEASE->NONE. **The session-5 "10 vs 11" was a single-step capture DOUBLE-READ**
        (Link's anim ctrl was byte-identical across the duplicated frame -- `_notes/tetrapush-reticle_probe.py`),
        NOT a real variation; it is a FIXED anim-length constant. `AttentionLock.DEFAULT_FADE_FRAMES = 10`.
      - **The attention's L-input delay is 1, not the physics `INPUT_DELAY = 2`.** The attention reads
        L via `mDoCPd_L_LOCK_BUTTON` (`g_mDoCPd_cpadInfo`) directly; live, `field_0x01a` rises/falls
        exactly 1 frame after the raw DTM L on BOTH edges, while the physics acted-L is 2 frames after.
        `state.py` now feeds `_atn.update` the delay-1 L (`_inbuf[0]` right after the delay-2 pop), not
        the physics `l_held`. Gate: `tests/test_tetra_untarget.py::test_untarget_2frame_tier` (both
        cycles: exactly 2 proc-9 body frames, body2 an ATN ~0.27 step matching the fixture within the
        mid-roll-seed budget). Purely additive -- 441 offline + 16 goldens byte-identical.
      - **Gap 1 (raw DTM stick bytes) -- CLOSED.** `harness/tetrapush/dtm_inputs.py` extracts the real
        per-frame raw controller bytes from the recorded movie `GZLJ01.s02.dtm` (the companion DTM
        beside slot 2, NOT a TAS-Studio export). Alignment: port0 = odd DTM rows, 4 uniform polls/game
        frame, and **captured f0 == DTM game-frame `F0 = 44974`** (re-derived from the two roll-trigger
        A-runs 26 frames apart). The delivered stick DECODES to the session-2 captured pad EXACTLY every
        frame -- buttons + magnitude + angle, 0 mismatch over the 45 movie frames. The movie ends at
        group 45019 (== cap f45); cap f46+ is free-run holding stick 111,111. Baked (inputs + live
        ground-truth states) into `fixtures/courtyard_push_dtm.json`.
      - **Untarget flip -- VALIDATED BIT-EXACT (both cycles).** Seed a LandState at each roll entry
        (constant-momentum roll, so no foot-warming needed -- the `couple_replay` convention) and feed
        the exact DTM bytes: the roll exits into ATN_ACTOR_MOVE (proc 9) and speedF flips 26 -> the live
        value, `_bits`-identical -- cycle 1 `-25.727313995361328`, cycle 2 `-25.742908477783203`. Gate:
        `tests/test_tetra_untarget.py` (offline, self-contained; expected flip derived from the fixture's
        own capture, not a literal). Required a decomp-consistent sim fix in `state.py`: on the proc-9
        BODY frame the flip sets `mNormalSpeed`, but `checkNextMode` may already have routed `self.state`
        to MOVE for NEXT frame, so the position section now keys the momentum branch on the DISPATCH proc
        (like the CUT branch) -- else the MOVE foot path overwrote the flipped speedF to 0. Golden-inert
        (441 offline pass; goldens never drive the lock).
      - **Gap 3 (`FADE_FRAMES`) -- RESOLVED (session 6): a fixed 10-frame anim length.** Reading the
        reticle J3D frame ctrl live (`_notes/tetrapush-reticle_probe.py`, `mAttention+0x38` -> `McaMorf`
        -> frame ctrl `+0x58`) shows `YJ_DELETE` = `end=10 / rate=1.0 / EMode_NONE`, advancing frame
        1->10 over **exactly 10 game frames in BOTH cycles**. `runDrawProc` (`d_attention.cpp` 686-698)
        clears `AttnFlag_40000000` the Run the anim completes -> the next `judgementStatusHd` sets
        RELEASE->NONE. The session-5 "RELEASE = 10 vs 11" was a **single-step capture DOUBLE-READ** (the
        `advance` re-sampled a game frame -- Link's anim ctrl was byte-identical across the dup, cyc2 f44==f45),
        NOT a real variation; the true RELEASE is 10 in both. So `FADE_FRAMES = 10` is faithful (it IS the
        anim length, not a tuned knob). **Attention L-input delay = 1** (vs physics `INPUT_DELAY = 2`):
        `field_0x01a` rises/falls exactly 1 frame after the raw DTM L on both edges (the attention reads
        `g_mDoCPd_cpadInfo` directly); `state.py` feeds `_atn.update` the delay-1 L (`_inbuf[0]` after the
        delay-2 pop). With both, the sim's lock timeline matches RAM `mpAttnActorLockOn` bit-for-bit.
      - **Gap 2 (`chaseAttention` acquisition gate) -- MODELED (session 7), decomp-first + live-geometry-
        gated.** `chaseAttention` (`d_attention.cpp:563`) gates the lock-on target on the front-of-player
        cone (`check_flontofplayer`): a target is chaseable only within **+-0x4000 (90 deg)** of
        `shape_angle.y` (ftp bit 0x04 -> `ang_table[0]`; Tetra's `dist_table[0xAB]`, matching
        `knowledge/mechanics/tetra-follow.md`). XZ distance (<=~300) never binds here. This is EXACTLY why
        the Courtyard lock acquires MID-ROLL and never at the first held L: at state 2 Tetra is **~122 deg
        BEHIND** Link (out of cone -> `chaseAttention` false -> live proc 6/7, no actor), and only when the
        roll swings Link to face her (~0-2 deg) does the mid-roll L re-pulse acquire. `state.py` now feeds
        `_atn.update` a cone-gated `target_present` (`_AtnActorMixin._atn_target_present`, reusing the
        `setShapeAngleToAtnActor` bearing); `attention.FRONT_CONE_HALF = 0x4000`. Golden-inert (no actor ->
        False -> machine stays NONE). Gate: `tests/test_atn_actor.py::test_chase_attention_front_cone`
        (synthetic +-90 boundary + the force override) and
        `tests/test_tetra_untarget.py::test_chase_acquires_mid_roll_not_at_state2` (the live-pose per-frame
        cone: False f0-2, in-cone across both roll bodies). A **bare non-coupled replay** (the tier test)
        can't compute the real cone (its rolled position diverges ~100u with no CC plow), so it sets
        `_atn_force_present = True` to inject the acquisition it knows happened live; the coupled from-f0
        replay leaves it None so the cone runs for real.
      - **The `started`/`getOldFrameFlg` fix -- DONE (session 7), both foot paths.**
        `FootSpeedF.step_single_anim` (Python) and `w_step_single` (native `_anmc`) now set `started`
        (the `getOldFrameFlg()` analog, posMoveFromFootPos:2354) like `step_atn`/`enter_wait_idle`/
        `enter_single` do -- so the MOVE backslide AFTER the proc-9 tier no longer takes `FootSpeedF.step`'s
        cold `not started and nspeed<=0` rest path and return 0 (probe: cyc1 f22-25 read 0.0, cyc2 f48-55
        read 0.0 pre-fix). With the fix the backslide is pure momentum (m3598==0 -> `speedF == mNormalSpeed`
        bit-for-bit) and tracks the live decay within the mid-roll-seed budget (cyc1 <=0.0024, cyc2 <=0.0005
        with the +1 capture-shift alignment; ULP-exactness awaits the from-f0 replay). **Golden-safe**: every
        real roll/slip/WAIT_TURN enters via `enter_single` (which already sets `started`) BEFORE
        `step_single_anim` runs, so the fix is inert in every existing path (16 land goldens + 445 offline
        byte-identical). Native `_anmc` rebuilt. Gate: `tests/test_tetra_untarget.py::test_untarget_backslide_unzeroed`.
      - **Gap-2 note (superseded):** the roll-entry-seeded flip validation was MOOT for Gap 2 (the only
        L in-window is the intended re-pulse -> `target_present=True` was correct); the cone gate is now
        modeled for real and is required by the from-f0 replay + the planner.
      - **The capture frame-axis is CLEAN (session 4 -- the "jitter-free capture" worry does not apply
        here).** The player anim frame ctrl advances a dead-constant `+1.1`/frame through the roll and
        `+2.3`/frame through the MOVE in the single-stepped fixture, so each captured row IS exactly one
        game-logic frame (proven; not `+-1` on the frame count). The large per-frame POSITION swings are
        REAL coupled physics -- the Link<->Tetra CC plow (`dCcS::SetPosCorrect`) + the roll root-motion
        envelope -- NOT a capture artifact (Dereck's correction). A live re-capture re-confirmed the
        settled scalars bit-for-bit. So the proc-9 tier and the roll length ARE reliably placed.
      - **FULL-COUPLED per-frame diff (session 4, Tetra sim-driven).** Seed the coupled sim
        (`CcCoupledStepper(atn_lock=True)`, Tetra = `Zl1FollowState`) at a roll entry, feed the DTM
        bytes, diff BOTH actors vs the fixture. Result: **Link roll + untarget flip are BIT-EXACT
        through the flip** (both cycles) even under full coupling. Two divergences named:
        1. **The Tetra plow "divergence" is a SEED-STARTUP ARTIFACT, not a model bug.** Live Link<->Tetra
           feet distance OSCILLATES 41-85u (a chase-and-plow: shove her ahead, gap opens, catch up,
           shove again). Seeding at the roll entry with no prior push lets sim-Link roll into a
           stationary sim-Tetra -> a false ~70u Co overlap that blasts them apart (`co_move_pair`
           correctly resolves it, ~28u/frame). The CC model is fine; it must run from BEFORE Link
           reaches Tetra -- i.e. **from state 2 (f0)**, where the push builds naturally frame-by-frame.
        2. **The 0.27 "MOVE-decel" drop is actually a SECOND proc-9 (ATN_ACTOR) frame (session 5,
           RAM+asm-PROVEN; supersedes the session-4 root-cause).** Breakpoint at `setNormalSpeedF`
           (JP `0x80105ae0`) on the drop frame (cycle 1 f21): `param_1 (f1) = 0.27507579`, `param_2/3/4
           = 0.5 / 7.5 / 4.0` (== `ATN_SCL`/`ATN_ACC`/`ATN_DEC`, the `mAtnMove` family, NOT the MOVE
           family 0.6/2.5/1.8), and `LR = 0x80107c0c` lands INSIDE `setSpeedAndAngleAtnActor`
           (`0x80107b24`..`0x80107c2c`). So the 0.275 is `ATN_SPD(5.0)*msd(0.0556)*cos(travel-chase)`,
           i.e. a second `ATN_ACTOR` body frame -- `travel` snaps 4548->6005 via the ATN turn chase.
           The `mCurProc` read of 6 (MOVE) at that frame's END is `checkNextMode`'s `procMove_init`
           setting NEXT frame's proc early -- not the proc that ran the body. The gap was the actor-lock
           lifetime -- **CLOSED session 6** (reticle-anim + delay-1 L, above): the REAL `AttentionLock`
           now runs the 2-frame tier, flip bit-exact, body2 off ~0.0024 (mid-roll-seed `travel`/`csangle`
           imprecision, not a model error -- ULP-exact awaits the from-f0 replay). The
           `started`/`getOldFrameFlg` fix for the MOVE backslide AFTER the tier is now **DONE (session 7,
           both foot paths; see the bullet above)** -- the backslide is `speedF == mNormalSpeed` bit-exact,
           no longer the cold-path 0. It was NOT the 0.27 drop (that is body2, a proc-9 ATN frame); it only
           un-zeroes the backslide. Its remaining consumer is the from-f0 coupled replay (where body2 goes
           ULP-exact).
      - **The `procAtnActorMove_init` frame** (decomp 6294: init does NOT call `setSpeedAndAngleAtnActor`
        or `checkNextMode`) is still merged in the sim, but MOOT for magnitude: the frame axis is clean
        and the flip lands on the right frame. Model it as an `_atn_actor_entered` entry-hold only if a
        frame-exact placement is later needed.
- [x] **Viable Tetra clip positions = `_generated/tetra_placements.tsv`** (Dereck, 2026-07-21): those
      288 genuine coords are the target set. They were recorded at a specific roll entry, but the
      planner ARRANGES the matching roll entry as part of the push sequence (the genuine-coord set is
      coupled to Link's final roll entry, so the two are solved jointly). From state 2 Link/Tetra are
      still far from the corner, so there is runway to steer both into place.
- [x] **The Tetra-plow law + the CC split (session 8, live-derived + gated).** See `## The CC split`
      above. Tetra takes the FULL Co overlap depth from Link's ANIMATED mCyl centre (frac 1.000 x 40
      frames); `tetra_plow.reconstruct` predicts her whole trajectory from Link's centre path + seed to
      <0.01 u. New live ground truth `fixtures/courtyard_push_cyl.json` (Link mCyl centre + csangle +
      Tetra pos, from `capture_push` extended to log them). Gate `tests/test_tetra_plow.py`. New live
      addrs (Co centre, csangle chain, mStts, shape.z) in `## Addresses`. This is the Tetra side of the
      coupled dynamics -- the planner's Tetra-trajectory predictor, given Link's centre path.
- [x] **Link's own push slowdown = the full-depth recoil, MODELED + gated (session 9).** The session-8
      from-f0 blocker ("the sim applies Link's full speedF while live Link moves `speed - depth`") is
      root-caused and closed as a LAW: Link ejects the **full** Co-overlap depth away from Tetra every
      push frame (the mirror of the Tetra plow; `recoil/depth == 1.000` live). `harness/tetrapush/
      link_plow.py` + `tests/test_link_plow.py` gate it (frac==1.0 all push frames; recoil vector + feet
      reconstruction 0-ULP-within-single-step-jitter on the clean roll frames; foot term uses the
      POST-update speedF along `current.angle.y`). See `## The CC split`. The 2x-vs-naive-50/50 doubling
      source is an open sub-puzzle (not needed for the law). 453 offline pass; land goldens byte-identical.
- [x] **From-f0 coupled replay -- BUILT + cyc1 bit-exact (session 10).** `harness/tetrapush/from_f0.py`
      wires BOTH full-depth plow laws (`link_plow` recoil + `tetra_plow` push) into a closed-loop
      `LandState` replay: seed at f0 (or a roll entry), feed the real DTM bytes, INJECT Link's mCyl Co
      centre + csangle per frame (deferring the MOVE-phase Co-centre model), track Tetra as a bare XZ
      plow point (stt-3 the WHOLE window -- no follow leg). It is a COURTYARD-SPECIFIC full-depth mode;
      the general `cc_stepper`/`co_move_pair` 50/50 is untouched. **Gated `tests/test_from_f0.py` (4
      green):** seeded at the first roll entry, cycle 1 -- the FRONT_ROLL, the 2-frame ATN_ACTOR
      untarget tier (flip -25.727313995361328 + body2 -25.452238082885742), and the following MOVE
      backslide (f4-23) -- is bit-exact vs the locked capture (**every speedF 0-ULP**; Link pos within
      the injected-cyl single-step capture precision, max 6.1e-5 u), and **Tetra's full-depth plow from
      f0 reproduces her whole trajectory to <=9 ULP / <1.4e-4 u over the plow window, both cycles**.
      457 offline pass, land goldens byte-identical (additive; no library change). This closes the s9
      "wire it together" -- the full-depth coupling physics is validated. The mechanical scaffold works:
      input pre-seed `_inbuf=[inp[entry-1],inp[entry]]` -> step `inp[k]`->`live[k]` (INPUT_DELAY=2 handled
      internally), csangle injected via `_cam.yaw` (C-stick neutral).
- [x] **The backslide->roll-setup transition (MOVE->ATN_MOVE +18 re-target) -- SOLVED + gated (session
      11).** The from-f0 replay now **chains bit-exact through cycle 2's roll**: seeded at the first roll
      entry, f4..f44 is 0-ULP (every speedF, every proc, Link pos <1.4e-4 u) INCLUDING the whole
      backslide->roll-setup -- the proc-7 re-target entry (f26), the +18 flip (f28 -25.15 -> +18.574),
      and cyc2's roll trigger (f29). Gate: `tests/test_from_f0.py::test_chained_replay_through_cyc2_roll_bit_exact`
      (stops at f44, before the cyl fixture's single-step-jittered cyc2 untarget f45+; session-8 known
      corruption). **Root cause (live-probed s11, `_notes/tetrapush-retarget_probe.py`), one clean law:**
      the re-target flip landed 1 frame late because the DTM-driven replay ran at the shipped
      `INPUT_DELAY = 2`, but **the DTM stream IS the polled `g_mDoCPd` pad -- already one pipeline stage
      in -- so a DTM replay is delay-1, not delay-2.** The probe read `m34DC`/`m34E8` (stick want-angle,
      `la+0x34DC`/`la+0x34E8`) + `mDirection` (`la+0x34B8`) per single-step frame against the delivered
      pad and found `m34DC[k] = DTM[k-1]` UNIFORMLY (the stick target, the roll-A, and the soft-lock L
      all land exactly 1 frame after the DTM). The +18 is the `setSpeedAndAngleAtn` DIR_BACKWARD negation
      (`mNormalSpeed *= -1`, travel += 0x8000; d_a_player_main.cpp:2863) firing when the big off-axis
      re-target target arrives -- which at delay-1 is inp[27] at f28 (`|m34E8-travel|>0x6000` -> BACKWARD),
      not inp[26] at f29. **Fix:** a `LandState(input_delay=1)` param -- at 1 the physics AND the
      attention both act on the delay-1 pad (no ahead-by-one split); the shipped default stays 2 (the
      raw-controller latency the live walk goldens validate, untouched -- 458 offline pass, goldens
      byte-identical). `from_f0` seeds `input_delay=1` + a 1-frame `_inbuf`. This SUPERSEDES the
      session-10 "gate r24 on delay-1 / model the DIR flip separately" plan (those per-consumer delay-1
      hacks broke the EBS/brakeslide goldens -- the delay is a whole-pipeline property, not per-consumer).
- [x] **The TRUE f0 seed (state 2) -- CLOSED (session 12); the from-f0 replay is complete f0->f44.**
      Seeded at STATE 2 itself with the measured **mNormalSpeed**, the replay is bit-exact from the
      FIRST stepped frame: f1..f44 every Link speedF 0-ULP, every proc matching live, Link pos within the
      injected-cyl capture precision (max 1.4e-4 u). **Root cause (live-probed, `_notes/tetrapush-seed_probe.py`,
      NOT mDirection/attention):** at f0 Link is mid-transition out of the prior cycle's untarget, where
      **speedF LAGS mNormalSpeed by a frame** -- live f0 speedF `-24.573892593`, mNormalSpeed
      `-24.982038498` (bits `c1c7db37`). The replay seeded `nspeed = speedF`, so f1 (a MOVE backslide,
      which can only decay toward 0) gave `-24.572` instead of letting speedF catch up to the already-set
      nspeed `-24.980`. **The whole fix is seeding `nspeed` from the live mNormalSpeed** -- f1 then reads
      `-24.980` bit-exact and the +18 re-target flip (f2) + cyc1 roll (f3) + the cyc1->cyc2 chain follow.
      The session-11 "seed mDirection + the attention RELEASE residual" hypothesis was a **red herring**:
      live f0 `mDirection = 4 = DIR_NONE` and the attention is NONE / no actor -- both already the sim's
      fresh-`LandState` defaults (confirmed live). New deterministic seed capture (single read, no
      single-step jitter): `capture_push seed` -> `fixtures/courtyard_push_seed.json` (the complete f0
      state incl. mNormalSpeed); `from_f0.replay(..., seed_nspeed=)` threads it; `_seed_link` uses it for
      the non-roll seed. Gate: `tests/test_from_f0.py::test_true_f0_seed_bit_exact` (f1..f44 0-ULP). 459
      offline pass, land goldens byte-identical (additive; no library change).
- [x] **The SELF-CONTAINED Co centre (replace the per-frame cyl injection) -- the planner
      prerequisite -- CLOSED (session 16).** The computed centre now matches the capture on EVERY
      frame f1..43 to <3e-4 u (the cyl fixture's own single-step precision), and the fully
      **CLOSED-LOOP replay (`centers='computed'`) chains from state 2 with every proc, speedF, and
      lean 0-ULP f1..43** (facing within a +6-BAM eye-aim echo of the amplified capture noise;
      positions amplify that ~1e-4 noise ~1.35x/frame through the plow feedback. **The "common-mode,
      contact dynamics stay exact" reading here was WRONG -- session 22 measured the drift as
      DIFFERENTIAL**: e_link ~ -e_tetra (a pair mode), and by f39 the sim's Link<->Tetra distance
      (127.9 u) has left the live one (40.4 u) -- the late-window contact dynamics diverge. The
      seed is bit-exact across fixtures. **Session 23 re-diagnosed the residual: it is NOT the
      computed exec-centre FK** (proven bit-exact given exact pos -- 0 ULP vs the setcol breakpoint
      f1..12) but a ~1e-5 u/frame position-integration residual at the single-step fixtures' f32
      noise floor, amplified ~1.35x/contact-frame by the unstable plow feedback (see the FK 0-ULP
      box below). Four decomp-pinned
      exec-pose laws closed it (all live-verified at the JP setCollision breakpoint; gates
      `test_computed_centers_track_on_settled_roll_frames` + NEW
      `test_closed_loop_computed_replay_dynamics_bit_exact`):
      1. **The BODY_CHN twist uses the NEW lean** (`mBodyAngle.z`): in execute, `setWorldMatrix`
         (:11551, the base -- OLD lean) runs BEFORE `setMoveSlantAngle` (:11561, re-sets
         `mBodyAngle.z = shape_angle.z`), and `mpCLModel->calc()` (:11591) after both -- so the
         counter-twist is one lean update ahead of the base. The old-lean error only showed where
         the two leans cross a sin-table bucket (`JMAEulerToQuat` half-angle >>4), which is why the
         gap toggled per frame (f2/f4/f6 on, f5/f7-13 off).
      2. **J3D segment-scale-compensation on the neck chain** (`BODY_CO_SSC` = stomach/chest/neck,
         skeleton `scale_compensate=1`): `mDoExt_setJ3DData` (m_Do_ext.cpp:47-59) row-scales the SSC
         joint's local 3x3 by `1/mParentS` (the parent's local anim scale). The dash bck scales
         `stomach_jnt.x` 0.91-1.07, so the neck sat `scale_err * 22.26 u` off along the chest X on
         every dash-posed frame -- THE "dash-backslide root-pose XZ bias" (and the f0-seed gap).
         The foot chains carry SSC flags too (30/33/38) but only ANM_SLIP's jnt37 1.2 has a
         non-identity parent there -- the foot path is deliberately untouched (validated live
         separately); open question noted in the session-16 handoff.
      3. **Signed body_x euler quantization**: `JMAEulerToQuat` halves the angle as a SIGNED s16;
         the rebuild masked to unsigned first, mis-rounding every negative twist (worst at -1 BAM:
         game half=0 -> identity, masked 65535//2 -> a ~-32-BAM ghost twist -- the f14/15 residue).
      4. **Proc-init frames have NO base lean**: `commonProcInit` zeroes `shape_angle.z` (:5841)
         BEFORE `setWorldMatrix`; `setMoveSlantAngle` restores it (from the untouched `m351C`)
         after -- so the exec base is lean-free exactly on proc-entry frames (live-pinned: the
         f1/f3 base matrices read row0[1]==0.0 while f2 carries the old lean). `from_f0` flags
         init frames off the post-step proc stream.
      Plus: the state-2 seed fixture now carries the captured live `m_old_fdata` per-joint OLD-POSE
      store + morf counters (`capture_push seed`; `replay(..., seed_old_pose=)`) -- at THIS seed it
      equals the pure-dash warmup bit-for-bit (f0's morf is dead), but it is the general-correctness
      seed for any f0 with a live morf residue. The SEED frame's own Co centre stays part of the
      static initial condition (computing it needs f-1's m351C, which the seed doesn't carry).
      Earlier steps (sessions 13-15) built the FK/body-Co machinery, the mCyl timing law
      (exec-time midpoint + dCcS half-depth settled write), and the proc-9 pose fixes:
      - **`FootFK.body_co_center`** (`core/anim/foot_fk.py`, `body_co=True` mode): poses the neck
        chain `[0,1,2,3,4,14]` alongside the foot joints and rebuilds `setCollision`'s root/neck
        world midpoint from the stored old pose at any (pos, facing, lean), including the
        `jointBeforeCB` body_chn extra rotation `Q(-mBodyAngle.z,0,0)` (`d_a_player_main.cpp:289`,
        `mBodyAngle.z == shape_angle.z` :9526; x/y attention twists are 0 across the whole courtyard
        window -- live-probed, `_notes/tetrapush-upper_probe.py`).
      - **Proc-8/9 frames now pose the real ATN blend** (`state.py`: `step_atn`, entry morf on the
        routing frame) instead of advancing the stale single-anim ctrl -- `procAtnActorMove` calls the
        same `setBlendAtnMoveAnime` dispatcher (:6299/:6308). speedF untouched (m3598==0 tier);
        459 offline green, land goldens byte-identical.
      - **The f0 pose seed** (`from_f0._seed_pose_f0` + `replay(centers='computed')`): state 2 is a
        regime-3 DASH cruise, so the hidden anim state is one phase (the cyl fixture's `link.anim`
        25.4) + the lean (`shape_z<<1`); old pose warmed with two pure-dash poses.
      - **VALIDATED: the FK == the game's draw-final anm matrices.** Against a live nodeMtx probe
        (`mpCLModel` la+0x32C -> `mpNodeMtx` +0x8C; `_notes/tetrapush-anmmtx_probe.py`), the computed
        centre matches `mid(root,neck)` to **~6e-5 u on every settled roll frame** (entry-morf frames
        0.05-0.8 u; proc-9 frames 3.8-8.1 u still off -- the ATN side/direction pose needs pinning).
      - **The mCyl TIMING law -- CLOSED (session 14, breakpoint-pinned).** Broke on JP setCollision
        `0x8011a670` (caller `daPy_lk_c::execute+0x119c`, once per frame): the write IS the plain
        root/neck nodeMtx midpoint AT CALL TIME (<=6.1e-5 u every probed frame) -- the EXECUTE-pass
        matrices (`mpCLModel->calc()` :11591 after `posMove` :11407, before the scene CC pass), at
        the pause-boundary `current.pos`. The session-13 residual was comparing against the DRAW-pass
        matrices (a different, lagged base). The pause-boundary `mCyl` the fixtures log = that exec
        midpoint + the dCcS immediate HALF-DEPTH write (see `## The CC split`), encoded as
        `from_f0._cc_settled_center`. Probe fixture `fixtures/courtyard_push_setcol.json`; gates
        `test_from_f0.py::{test_settled_center_law_half_depth,
        test_setcollision_is_execute_time_midpoint, test_computed_centers_track_on_settled_roll_frames}`
        (462 offline green). Open-loop (diag mode) the computed centre now matches the capture to
        **<2e-3 u on every settled single-anim roll frame** (many at ~1e-5); closed-loop
        (`centers='computed'`) procs+speedF chain through f28.
      - **The proc-9 POSE gap -- CLOSED (session 15, three decomp-pinned fixes; facing + lean now
        bit-exact f1..f43).** The f19-21 blend (4.6-8.5 u) + the f22-26 morf decay (1.1-3.0 u) + the
        cyc2 roll residue f29-38 (0.04-0.24 u) all collapse (f19-20 ~2e-5 u; f27-43 <2e-3 u; f21-26
        <=0.35 u) with NO physics perturbation:
        1. **The mDirection actor-lock gate** (`_update_atn_direction`): the FORWARD/BACKWARD branch
           requires `mpAttnActorLockOn == NULL` (:3299) -- locked, the direction can only go SIDE, so
           the tier poses the ATN{L,R} strafe family (`atnd{l,r}s` @ rate 1.8), not dash/atndb.
        2. **The routing-frame pose timing**: `checkNextMode` returning TRUE skips the body's
           `setBlendAtnMoveAnime(-1)` (:6307), and a proc `*_init` (its pose included) runs on the NEW
           proc's FIRST dispatch frame (the `mCurProc == X` guard), not the routing frame. So the
           body2 frame advances the atnd ctrl with NO pose call, and `procMove_init`'s
           `setBlendMoveAnime(2.4)` fires on the first MOVE frame (live: atnd@3.6 maps to dash@6.4 =
           3.6/18*32). `state.py` now runs the walk pose (pending morf) on that frame instead of
           `step_atn`. Live truth: the session-13 `_notes/tetrapush-upper_probe.json` under-anim
           frame/rate stream, which the sim now matches on EVERY frame f1-28.
        3. **The re-aim law** (`_set_shape_angle_to_atn_actor`): `setShapeAngleToAtnActor` chases the
           bearing to the locked actor's **eyePos** -- Tetra's ANIMATED head-joint world pos
           (`d_a_npc_zl1.cpp:1283`), leading her feet 16-26 u -- and no-ops while `mpAttnActorLockOn
           == NULL` (:2627; the body2 frame runs one frame past the lock drop and must NOT re-aim).
           Live-pinned (`_notes/tetrapush-eyepos_probe.py` -> `fixtures/courtyard_push_eyepos.json`):
           eye-aim reproduces facing 37548 bit-exact where feet-aim lands 184 BAM short, and the
           ghost f21 re-aim added +432. The facing error was ALSO the m351C lean sawtooth offset
           (`setMoveSlantAngle` tgt = 1.6*(m34DE - facing)*ratio -- m34DE = PREV frame's facing, so a
           facing error feeds the lean for frames). Gates: `test_facing_and_lean_bit_exact_with_eye_aim`
           (facing + shape_z 0-ULP f1..f43), the extended `test_computed_centers_...` (per-frame
           ceilings). The replay injects the eye stream (`replay(..., eyes=)`) like csangle; the
           PLANNER model for eyePos (her look-at head anim chasing Link) is still open.
      - **The "remaining POSE gaps" of session 15 are ALL CLOSED by the session-16 laws above**
        (the "dash-backslide root-pose XZ bias" WAS the missing SSC; f14-16 the unsigned body_x;
        f1/f3 the proc-init base lean; f21-26 the new-lean twist). The session-15 rule-out list
        (lean scale, phase lag, dashs-vs-dash root content, m34EC/shape.x, m35B8, m34E0 waist,
        m3730/m36B8) stands -- those were all correctly eliminated. Sword-drawn note kept: `m3562 =
        0x103` all window, physics-inert (dash/dashs identical at joints 0-4/14; only feet differ),
        may matter for the final CUT pose set.
        **"Physics-inert" was true only of the CO-CENTRE and only while `m3598 == 0` -- OVERTURNED by
        session 58 (box below): the FEET are `posMoveFromFootPos`, so the dash/dashs swap IS the
        position from plan frame 72 on. The replay now seeds `sword_drawn`.**
- [~] **Build the planner** -- STARTED (session 28); the forward model is now FULLY BIT-EXACT from
      state 2 -- dynamics AND position 0-ULP f1..f43 (session 27 closed f2..f43; **session 29 closed
      the f1 seed-frame boundary, entirely offline** -- see the search-proper box below). So an
      open-loop multi-cycle rollout is trustworthy and the search foundation is solid. The deliverable
      is still the input sequence that lands Tetra on a genuine `tetra_placements` coord + the matching
      roll entry. Method reference: `plan_land` / the seam-clip `solver` (cheap predictor + exact
      bit-confirm, no calibration). The camera/look/neck sub-models ARE 0-ULP-gated and reusable.
      Session-28 progress (below): the sound primitive layer is RESTORED + gated, coarse feasibility
      is CONFIRMED, and the f1 seed-frame cost was characterized (session 28) then CLOSED (session 29).
      - [~] **THE OUT-OF-BAND DTM TIER-2 LIVE CONFIRM -- STRATEGY A KILLED, STRATEGY B ANCHOR CONFIRMED
            (session 53). This is the last open tier; the offline model + 2b are CLOSED.** Node 1's full
            **241-frame** input log was extracted (`_notes/node1_full_log.json`; the offline model lands
            Tetra pd **0.011** on genuine coord 287 `(-1627.42, -892.34)`, Link 10.42 u from the entry)
            and it is **delivery-robust**: re-simulating on the console's cal-clamped delivered bytes
            (0->1, 255->254) is BIT-IDENTICAL (the octagon dead-zone absorbs the extremes), so
            `[[octagon-clamp-decode-bug]]` does not bite -- authoring cal'd bytes is exact.
            - **Strategy A (extend the recorded boot movie + `loadstate 2`) is DEAD.** Authored the
              continuation movie `GZLJ01.s02.node1.dtm` (recorded prefix byte-identical through F0=44974,
              my 241 frames after, round-trips 0/241 vs `dtm_inputs`), but **`loadstate 2` REJECTS any
              modified movie**: with `tickCount` maxed Dolphin CRASHES at State::Load; with a minimal
              header edit it HANGS on a blocking modal (baseline recorded-movie loadstate returns <1s).
              The movie-anchored slot-2 savestate is bound to the EXACT recorded movie -- you cannot
              deliver computed inputs by extending it. Baseline re-verified healthy (recorded movie
              loadstate 2 reads the seed exactly: `(-1329.424, 39.899) sF -24.574 proc 6`).
            - **Strategy B (a fresh `bFromSaveState=1` movie anchored to the slot-2 savestate, `run_dtm`'s
              flow) WORKS -- CONFIRMED LIVE.** A trivial 20-frame `bFromSaveState=1` movie authored from
              the `run_dtm` template, with the slot-2 savestate `GZLJ01.s02` copied to `<out>.sav` + the
              companion `<out>.sav.dtm` (the deep-anchor `m_current_frame!=1` trick), playmovies straight
              into the courtyard: Link reads the state-2 seed EXACTLY (`(-1329.424, 39.899) sF -24.574
              proc 6`) -- decoupled from the recorded movie. So the plan CAN be delivered this way.
      - [~] **THE TIER-2 CONFIRM RAN (session 54): the DELIVERY PATH IS BUILT + VALIDATED, and it
            FALSIFIED node 1's plan on console -- a REAL, localized CC-PUSH divergence.** The plan is not
            console-faithful: Tetra ends **113.3 u** from coord 287 (Link 165.9 u from the entry, vs the
            model's 10.4), reproducibly. This is the first live test of the model BEYOND the 43-frame
            recorded window, and it found a genuine modeling gap -- exactly what tier 2 is for.
            - **Session 53's "Strategy B confirmed" is OVERTURNED: it only ever verified the seed
              APPEARS, never that inputs PLAY.** The slot-2 savestate is welded to the recorded 90k-frame
              movie (`currentFrame` 89952), so a fresh anchored movie is instantly past its end -> Link
              frozen at the seed + the **input-mismatch dialog**. A clean anchor cannot be minted at the
              seed either (`recordstart` is a no-op while a movie plays; no pipe verb ends playback while
              keeping the game running). Both savestate-anchor routes are dead.
            - **THE WORKING DELIVERY (Dereck's steer): splice the tail onto the recorded BOOT movie.**
              Keep game-frames 0..F0 BYTE-IDENTICAL, replace F0+1.. with the plan (`log[i]` -> game-frame
              F0+1+i), leave `bFromSaveState=0`, and `playmovie` it. Validated end-to-end: re-appending the
              recorded tail delivers **latched inputs (poll index 2) 0/45 mismatch** vs the recording (raw
              diffs in the other 3 polls are irrelevant -- the game latches poll 2 only). Byte-aligned by
              construction, so **`REST_NOOPS` is moot** (no savestate alignment padding).
            - **`tickCount` must be EXTENDED, not maxed.** `Movie::CheckInputEnd` ends playback when
              `GetTicks() > tickCount`, so keeping the recorded value truncated ~197 of the 241 tail frames
              (playback stopped at the RECORDING's frameCount); but maxing to `0xFFFFFFFFFFFFFFFF` reads as
              signed -1 -- **the real cause of s53's "maxed tickCount crashes State::Load"**. Scale the
              recorded ticks to the longer movie + 10% (`author_boot.build_boot_movie(tick_mode='extend')`).
            - **The ~9.5-min boot replay is SKIPPABLE (Dereck's rule): `loadstate 1`.** Start the boot movie,
              then load a state whose inputs are a SUBSET of that movie's -- slot 1 is frame 89682, INSIDE
              the identical prefix -- and it is equivalent to having replayed to that frame, so read the
              result as the full playback's. A full delivery run is then **~8 s**. Slot 2 is NOT usable (it
              sits AT the splice, reading plan frame i=0, and trips the mismatch). Issue ONLY `playmovie` +
              `savestate load 1`: any `pause`/`resume`/per-frame `advance` of ours makes Dolphin re-pause
              (PauseMovie=True, restored frame/tick bookkeeping) and needs manual unpausing.
            - **THE DIVERGENCE, localized by TRUNCATE-AND-READ** (author the first N plan frames; PauseMovie
              halts at plan frame N-1, so a plain 8-s run reads that exact frame -- no stepping):
              N=20 **0.0000**, N=30 0.0002, N=40 0.0106, N=45 0.0958, N=50 0.5243, N=55 4.4162, N=60 31.63.
              **dLink == dTetra at EVERY N** -- equal-and-opposite displacement, the signature of the
              **CC push split**, so the error is in the PUSH MAGNITUDE, not Link's foot term (his proc and
              speedF stay bit-identical: at the first divergence both read p7 / sF -25.387, position alone
              differs). The model pushes very slightly TOO HARD (separation at N=50: live 46.49 vs model
              46.60 u). A tiny residue seeds between plan frames 20-30 and amplifies ~1.4x/frame -- the
              known ~1.35x/contact-frame plow amplifier -- until the 4th roll passes to Tetra's LEFT and
              misses her entirely (observed live), leaving her 113 u short.
            - **THE GATE = `tests/test_node1_console.py`** (offline, 0.3 s, runs by default). The locked
              fixture `fixtures/courtyard_node1_console.json` carries node 1's 241-frame log AND the
              console-measured state at each sample; the test replays the log and demands the sim predict
              it **0-ULP**. Correct polarity: for a fixed input log the console is ground truth and never
              moves, so the SIM converges to the fixture -- never edit it to pass (immutability hard rule).
              Currently n=20 PASSES bit-exact and n={30,40,45,50,55,60} are **`xfail(strict=True)`**, so a
              model fix XPASSes and FAILS the suite until its `n` is removed from `OPEN` -- the frontier
              ratchets and cannot regress (`test_the_frontier_is_contiguous...` keeps the exact region a
              prefix). Two assertions double as the diagnosis: proc/facing/stt match at EVERY sample, and
              the Link/Tetra error magnitudes are EXACTLY equal (the push-split signature) -- pinned so a
              "fix" that moves the foot term instead of the push is caught, not mistaken for progress.
            - **NEXT:** root-cause the push residue that appears by plan frame ~30, decomp-first. Link's
              foot term is exonerated, so suspect the **animated exec Co-centre** (`body_co_center` at poses
              the recorded window never visited) or the f32 Tetra-track rounding. The existing 0-ULP gates
              only cover the RECORDED inputs' f1..f43, which never excited it -- so build the gate from a
              truncate-and-read live curve on node 1's OWN inputs. Iterate with
              **`deliver.divergence_curve`** -- each N is one ~8-s run; bisect plan frames 20..30 to find
              the seed frame, then diff the push vector there against the decomp.
            - **SUPERSEDED IN PART BY SESSION 55 (box below): the "CC-push magnitude" diagnosis was
              right, and the cause was an FP-SHAPE error in the push, not the Co-centre.** The frontier
              is now bit-exact through plan frame 38.
            - The delivery tooling is TRACKED (`deliver.py` + `find_tetra.tetra_scan`, gated by
              `tests/test_tetrapush_deliver.py`) -- do not rebuild it in scratch. Research scratch
              (gitignored `_notes/`): `node1_full_log.json` (THE plan), `node1_perframe.json` (the offline
              expectation, regenerated by `tetrapush-node1_perframe.py`), `node1_bisect.json` (the curve).
              `[[courtyard-tetra-push]]`, `[[tetrapush-dtm-delivery]]`.
      - [~] **THE PUSH'S FP SHAPE WAS WRONG -- FIXED FROM THE SHIPPED BINARY (session 55). The
            frontier moved from plan frame 20 to plan frame 38, 0-ULP.** Session 54's divergence was
            root-caused to a single wrong FP assumption in `cM3d_Cross_CylCyl` / `dCcS::SetPosCorrect`,
            not to any missing mechanic; the Co-centre, the foot term and the delivery were all exact.
            - **THE BUG: `dist²` was FUSED and it must not be.** `cc_push.py` computed
              `fmadds(dz, dz, fmuls(dx, dx))`, justified in its own FP note as "fused like `PSVECMag`".
              `PSVECMag` is a different (paired-single) routine and its fusing does NOT carry over.
              Disassembled live in the JP binary: **`cM3d_Cross_CylCyl` 0x8024C44C** = `fmuls f1,f2,f2` /
              `fmuls f0,f0,f0` / `fadds f4,f1,f0`, and **`dCcS::SetPosCorrect`'s `objDistLen` 0x800AB430**
              = the same three ops (0x800AB394 for the correctY branch) -- there is no `fmadds` in either.
              Fusing put `cross_len` ~2 ULP high, biasing the push ~3e-6 u/frame.
            - **`std::sqrtf` is `__frsqrte` + 3 double Newton steps**, inlined at 0x800AB444 exactly as
              MSL `math.h` writes it -- not a correctly-rounded sqrt. Now
              `collision.sqrtf_msl`. (It happens to agree with a correctly-rounded sqrt on 400k random
              operands; it is here because the push is a 0-ULP surface and the primitive should be the
              game's. It was NOT the cause -- checked at the seed frame before the real bug was found.)
            - **HOW IT WAS FOUND (the method that generalizes): a CONSECUTIVE truncate-and-read sweep.**
              `deliver.py` gives one console-measured frame per ~25 s run, so N=21..30 back-to-back named
              the seed exactly (frame 22, **1 ULP on Link's z only, Tetra still exact**) instead of the
              10-frame bracket s54 had. Then eliminate, live, term by term: the root/neck world anm
              matrices (`mpCLModel->mpNodeMtx[0]/[14]`, the two values `setCollision` averages) are
              **bit-exact** -> the Co-centre is exact; `speed` (`la+0x220`, the exact `current.pos +=
              speed` displacement) is **bit-exact**; `m36A0`/`m36B8`/`m3730` -- posMove's other
              unconditional position writes (:2583-2591), none of them modeled -- all read **exactly
              0.0**. With every other term verified, the residue had to be the push, and inverting the
              f32 bin boundary said the console's `cc_z` was >=2.9e-6 larger. Enumerating the FP-shape
              variants against that interval left exactly one: unfused.
            - **RESULT.** n=30 0-ULP (was 2-3), n=40 78/153 -> 0/2 ULP, n=60 31.6 u -> 0.031 u (~1000x).
              A live full-plan delivery re-ran the 241 frames and reproduced session 54's endpoint
              **bit-for-bit** (`(-1547.8871, -811.6024)`) -- the console replay is deterministic across
              sessions, which re-validates the locked fixture. The endpoint miss is still 113.3 u,
              as it must be: the model moved toward the console, not the reverse, and the remaining
              ~180 frames still amplify the NEXT seed.
            - **THE GATE RATCHETED + DENSIFIED.** `fixtures/courtyard_node1_console_dense.json` (NEW,
              LOCKED) adds the consecutive n=21..40 console rows, so `test_node1_console.py` now pins
              **every frame** through 38 rather than 10-frame strides -- a regression names its own
              frame. n=30/40 were measured in BOTH sessions and agree bit-for-bit
              (`test_the_two_captures_agree_where_they_overlap`). `OPEN` is now {39,40,45,50,55,60}.
            - **NEXT: plan frame 39** -- already localized live. Unlike frame 22 it is equal-and-opposite
              on both actors from the start (Link z +1 ULP, Tetra z -1 ULP), so it is a push-magnitude
              error again. Same method: it is one frame, so instrument that frame's push inputs and diff
              the FP shape against the binary. Frames 21-38 are bit-exact and must stay so.
            - **FOUND A LATENT NATIVE BUG -- DO NOT ASSUME IT IS BENIGN.** Calling `_shovec`'s
              table-seeded `sqrtf_c`/`_frsqrte` from the Co-push block **faults the process** (Windows
              access violation in `tests/test_pushaside_clip.py`, reproducible on a clean rebuild); the
              same MSL sqrt with a math-accurate seed is fine and is provably bit-identical (400k
              operands in Python, 40k push pairs native-vs-Python). The native push therefore uses
              `_sqrtf_msl_c`, but `_frsqrte` is UNDIAGNOSED and still sits under the acch/WallCorrect
              call sites (`_shovec` ~297/467/549/668/856). Worth root-causing before trusting it.
      - [x] **THE SCOPE DECISION IS MADE, AND IT CAME WITH A SECOND UNMODELLED BOUNDARY: THE WALLS
            (session 60). The objective is now a frame budget, and it is gated.**
            Session 59 handed over a choice between modelling stt-4 follow and re-solving in
            regime. Dereck picked neither as posed, and narrowed the job instead:
            - **DERECK'S STEER (the new objective).** (1) The only goal of the push is getting
              Tetra onto a viable known clip coord; **Link's roll position/angle for the recorded
              solution is a SEPARATE search afterwards**, so no frame may be spent positioning him
              for the clip -- this OVERTURNS the s44-s51 "coupled entry" framing (milestone 2b).
              (2) **This is a TAS: frames are the objective.** Maximum acceptable timeloss versus
              an all-out push is **2 frames, 1 preferred**. (3) The terminal must leave Link
              **MOVING**, so a 1-frame 180 (`reposition.turnaround`) carries him away from Tetra
              with speed in hand -- which **retires the near-rest arrival gate** (`arrival_quality`
              wants approach <= 3 u/f; the deceleration that buys costs exactly the frames rule 2
              refuses). (4) Neither actor may touch a wall **during the herd**; the wall contact at
              the clip itself is already owned by the recorded solution list.
            - **THE BAR, derived and gated.** The herd ceiling is the CC split law's `|speedF|/2`
              at the roll cap = **13.00 u/frame** (`steered_search.push_ceiling`, human 98.2%), and
              the nearest genuine coord is **937.568 u** away (idx 287), so the all-out-push
              **FRAME FLOOR is 73 frames**; accepted **75**, preferred **74**. Equivalently the
              plan must average **12.50 u/frame** over its whole length, against a per-cycle rate
              that decays with junction overhead -- so **the placement has to RIDE the last push,
              not follow it as a separate glide** (s44's terminal was a separate phase).
            - **THE WALLS -- A REAL, SILENT INFIDELITY, and rule 4 is why it was looked for.** The
              Courtyard `FreeRun` models **no BG collision at all** (`seeds.py`/`from_f0.py` never
              mention walls). Replaying node 1's locked plan, the sim walks Link **into the
              courtyard back wall from plan frame 84** (poly 1950/1953, plane **z = -990.2557**),
              reaching 2.5 u from the wall edge at frame 88, while the console has him **braced at
              exactly `LINK_WALL_R`**: the locked s56 rows read wall distance **34.99995 u** at
              BOTH n=100 and n=160, `speedF` 0.10/0.53, z identical to the bit 60 frames apart.
              That is the LINK-side half of the open-sample divergence (console displaces 49.84 u
              from n=80 to n=100 where the sim displaces 101.64 u, with **proc and facing still
              matching bit-for-bit at every open sample**) -- and no amount of FP work would ever
              have closed it. The two scope breaks open together: **regime at frame 83, wall at
              84**, ~16 frames before the first sample the console measured, which is the only
              reason the frontier reads as n=100.
            - **BUILT + GATED: `objective.py` + `tests/test_objective.py` (12).** The steer as
              predicates a search prunes on -- `frame_floor` (the bar), `wall_margin` /
              `clear_of_walls` / `frame_is_wall_free` (rule 4, exact but bounding-box-accelerated,
              89 us/call), `in_regime` (`FOLLOW_ENGAGE_DIST`), `turnaround_ready` (rule 3, on
              velocity MAGNITUDE and post-snap direction, so an EBS backslide counts as moving),
              `score_plan`/`verdict`. Every threshold is derived or decomp-cited; the only two
              chosen numbers are Dereck's budget and the terminal rule, labelled as such. The
              strongest gate is `test_the_wall_metric_reproduces_the_console_s_own_brace_point` --
              the wall set and radius are validated against the console's own brace, offline.
              667 offline pass (+12), 0 fail, same 8 xfails.
            - **NODE 1'S PLAN FAILS THREE RULES AT ONCE** (`objective score`): 241 frames vs a
              73-frame floor (**+168**), wall margin **-34.1 u**, left the regime at frame **83**,
              and ends at **rest** (speed 0.000) -- the near-rest arrival rule 3 retires. Pinned by
              `test_the_locked_plan_fails_the_objective_on_three_independent_rules` so it is not
              re-adopted as a starting point. The recorded human window, by contrast, is wall-free,
              in-regime, and already terminal-READY (speedF 26 travelling away) -- it just stops
              at 44 frames without finishing the herd.
            - **CAUTION for the re-solve: every search result from s42-s51 predates the s55-s59
              model fixes** (the unfused `dist_sq`, the signed half-angle, the RELEASE gate, the
              pose stream, the WAIT stop). The 3-cycle chain's 868.3 u / 69 f / 12.584 u/f and the
              s44 terminal's pd 1.98 were measured on a model that has since moved; re-measure
              before trusting any of them. Node 1's plan replayed on today's model lands Tetra
              **198 u** from the coord, not the 0.011 it was solved for.
            - **NEXT: re-solve under the objective.** Wire `frame_is_wall_free` in beside the
              existing `_follow_warned` prunes in `full_herd` (the regime half is already enforced
              everywhere; the wall half is nowhere), re-aim the terminal from `arrival_quality` to
              `turnaround_ready` + placement-on-the-last-push, and run the chain against a hard
              75-frame budget. `objective.score_plan` is the acceptance test.
              **DONE in session 61 (box below) -- and it moved the blocker onto the CHAIN.**
      - [x] **THE OBJECTIVE IS NOW THE SEARCH'S RANK AND PRUNE, AND RUNNING IT FOUND WHY THE CHAIN
            "STALLED": ITS LAST CYCLE WAS OVER-CONSTRAINED (session 61).** All three of session 60's
            next-step pieces landed. The terminal is measured and exonerated (3-4 frames); the chain
            reaches 69-70 frames at `plan_bound` 74.4-74.7 -- inside the 75-frame budget -- with Tetra
            57.5-71.5 u still to go, and THAT last stretch is the open blocker.
            - **WIRED (piece 1): the wall prune, at every active site, behind ONE predicate.**
              `full_herd.frame_in_model` carries the regime half (`_follow_warned`, which was
              everywhere) and the wall half (which was nowhere) TOGETHER, so they cannot drift apart
              again -- junction beam, junction quality, both roll stages, the terminal -- and
              `confirm_plan` measures clearance on EVERY frame with the exact metric, reporting
              `wall_ok`/`wall_margin`/`wall_margin_at` and refusing `ok` without them. Affordability
              came first: `clear_of_walls` brackets each 32 u grid cell by its centre's exact distance
              (`_cell_distance`), **136 -> 16 us/frame, still exact** (gated vs `wall_distance` over
              2000 room points). Inert on clean plans (cycle-1 margin > 50 u); it **BITES on node 1**
              (`wall_ok=False`, `ok=False`, replay still bit-exact -- the plan is model-faithful and
              the MODEL is out of bounds). It is NOT what stalls cycle 3: margins through that whole
              corridor are **+68..+195 u**, and the prune only bites past along ~1000, beyond the
              target thread's far end.
            - **WIRED (piece 2): the frame budget as the RANK.** `objective.plan_bound` = `f = g + h`
              (frames spent + distance / `PUSH_CEILING`), `rank_key('bound'|'rate')` threaded through
              `roll_candidates`/`extend_cycle`/`cycle1_nodes`/`chain_herd`, `_budget_cut` for the hard
              budget. Why it replaced the herd rate: **a rate is a down-herd PROJECTION and cannot see
              a lateral miss at all**, while the bound counts it as the frames it costs. Measured
              caveat: the two ranks are currently **INERT against each other** -- byte-identical beams
              -- because the beam is too thin (5 cycle-1 nodes, 7 cycle-2) to have alternatives to
              choose between. Right by construction, unexercised; do not read it as a win either way.
            - **THE TARGET IS A SEGMENT, NOT A CLUSTER** (`objective.placement_thread`, gated; the
              session's most useful measurement). The 288 coords are a near-straight **47.6 u segment
              12.2 deg off the herd axis**, i.e. a LINE in the herd frame: lateral falls **0.216 u per
              u of along**, from **+7.94 at along 937.5** (idx 287, the nearest) to **-2.27 at 984.1**.
              So a plan has **~46 u of ALONG slack** (+-4.7 u keeps Tetra inside 1 u of the thread --
              the terminal does NOT have to hit a point) and only a **~10 u LATERAL window**, and
              pushing further down-herd **trades along for lateral instead of fixing it**. Surfaced per
              plan by `score_plan`'s `tetra_along`/`tetra_lat`/`lat_error`/`placeable`. Aiming the herd
              line at coord 287 instead of the centroid would rotate it only **0.485 deg**, so the
              lateral problem is drift, not aim.
            - **THE TERMINAL IS EXONERATED: it costs 3-4 FRAMES.** `terminal_targeting(objective=
              'frame_minimal')` ranks by the bound and STOPS at the first frame satisfying rules 1+3
              (in the band with Link still MOVING, `_terminal_ready`), returned as `placed`. Measured
              on `synthetic_hot_arrival` at coord 287: from **25 u short on the thread -> PLACED in 3
              frames at pd 0.473**; from **40 u short at lat +4 -> 4 frames, pd 0.173**; from 69 u short
              it MISSES (closest 11-14 u) because 69 u of along moves the thread's required lateral
              14.9 u. **So the arrival window is ~25-40 u short with lateral within ~+-4 u of
              `lat_at(along)`** -- that is the chain's spec now, and it is a lateral spec.
            - **THE CHAIN, RE-MEASURED ON TODAY'S MODEL (piece 3): cycle 1 275.8 u / 21 f / 13.135 u/f
              (bound 71.9), cycle 2 590.9 u / 46 f / 12.846 (bound 72.9), and cycle 3 initially
              produced ZERO roll survivors** -- which read as "s43's 868.3 u / 69 f no longer
              reproduces". **It does**: with the over-constraint below removed, cycle 3 comes back at
              **869.2 u / 69 f / 12.597 u/f, bound 74.4, 8 nodes** -- s43's number to within a unit, on
              a model that has moved five times since. The cause was never the model, the rank or the
              walls.
            - **THE STALL'S CAUSE, FOUND AND FIXED: `chain_herd` required its LAST cycle to be
              CONTINUABLE.** `junction_quality` asks whether the next junction could carry on from a
              roll's endpoint; the final cycle has no next junction -- only the terminal glide, which
              needs contact and the regime, not a junction posture. `roll_candidates(require_quality=
              False)` was already the documented terminal-roll mode and the chain never used it.
              Measured from the real cycle-2 beam: `True` -> **0** cycle-3 survivors, `False` -> **7**,
              at **69-70 frames, 12.51-12.60 u/f, `plan_bound` 74.4-74.7 -- INSIDE the 75-frame
              budget**, with Tetra 57.5-71.5 u from the coord. `chain_herd` now passes
              `require_quality=(c < ncycles)`; gated by `test_the_chain_does_not_require_its_LAST_
              cycle_to_be_continuable` (a wiring spy -- reproducing the measurement costs ~15 min).
              **Attributed both ways, not assumed**: with this session's wall prune STUBBED OUT
              entirely, cycle 3 still yields **0** (448 s run), and with the prune fully ON but
              `require_quality=False` it yields **7** -- so the new prune is exonerated and the
              over-constraint is the cause.
            - **THE LATERAL OSCILLATES; IT DOES NOT ACCUMULATE.** Cycle 1 leaves Tetra at lat +5.8
              (inside the window, near the thread's +7.9), cycle 2 swings her to **-39.9** (`lat_error`
              -47.8, ~5x the window), and cycle 3's roll swings her back to **+8.90 .. +24.61** -- the
              best node landing essentially ON the window's edge (+8.90 against +7.94 plus the 1.02 u
              perpendicular tolerance). So a cycle-2 endpoint reading -39.9 is NOT proof the plan is
              lost, and ranking a mid-chain beam on lateral alone would have thrown the survivor away.
              What sets the lateral is per-frame geometry, not the roll's heading: the surviving roll
              aims are only **-4.5 deg / +5.0 deg** off the herd bearing, while the pursuit box
              tolerates Link **+-18 u** off-line and 18 u of offset ejects Tetra ~3.9 u/frame sideways
              (~97 u per cycle; even 4 u gives ~22 u).
            - **THE RANK'S OWN LIMITATION, worth knowing before leaning on it.** Scored side by side
              (`objective score`), the recorded 44-frame human window ends at **lat +5.47, `lat_error`
              -2.48, `placeable` TRUE, bound 72.9** and the search's 46-frame 2-cycle chain at **lat
              -39.9, `placeable` FALSE, bound 72.9** -- `plan_bound` calls them EQUAL, because pd
              treats along and lateral as interchangeable. They are not: along trades into lateral
              later for free (0.216 u per u), while correcting lateral needs Link to reposition to her
              SIDE and costs frames. A future refinement is `h = max(along_remaining,
              lateral_remaining / the measured lateral rate)`, not a weight on `lat_error`.
            - **WHY ROLL AIMS DIE at cycle 3** (the new counters, from 27.5k probed): `followed`
              **26670** -- the ~400 u roll carries Link past the 230 u follow shell -- then `offline`
              459 and `wall` 367. So the wall prune does bite near the corner, but it is 1.3% of the
              deaths; the fan is simply mostly pointed at directions that lose contact.
            - **A CORRECTION worth more than it looks: `PUSH_CEILING` 13.0 u/f is the STEADY STATE of
              the split law, not a per-frame law.** The depth is measured to Link's ANIMATED exec
              Co-centre, which moves by the foot term PLUS the pose swing that leads/trails his feet
              6-28 u -- so the human's own 4th recorded frame advances Tetra **18.84 u** and a 23-frame
              search cycle sustains **13.36**. The swing cancels over a long window (his 44-frame mean
              is 12.758), not over one cycle. Consequences: the **73-frame floor is asymptotic, not a
              theorem** (Dereck's 75 is a spec either way, and this only makes it more reachable), and
              `plan_bound`'s `h` can be ~1 frame pessimistic over ~25 frames -- as a PRUNE, cut on
              `budget + 1` if it ever binds. Pinned by `test_the_push_ceiling_is_a_sustained_rate_
              not_a_per_frame_law` so nobody "fixes" a cycle that legitimately beats 13.0.
            - **TOOLING: `full_herd solve`** = chain -> frame-minimal terminal -> the acceptance test
              on the winner's own log (`objective.replay_and_score` from state 2, so no beam prune is
              taken on trust). One command, and it prints the frame accounting and the thread position.
              Dead counters are now **split by reason** (`followed`/`wall`/`outbox`,
              `aim_talk`/`aim_no_roll`/`aim_weak`/`aim_offline`/`aim_wall`) -- "the beam emptied" is not
              a diagnosis, and folding the wall prune into the existing `outbox` counter (which I did
              first) destroyed exactly the diagnostic the stall needed.
            - **THE END-TO-END SOLVE (`full_herd solve cycles=3`, 940 s): 73 FRAMES AT TIMELOSS +0,
              wall-free, in regime, bit-exact -- and 31.4 u short of the coord.** The full acceptance
              test on the winner's own log: `frames 73 vs floor 73 -> timeloss +0`, `wall +50.4 u`,
              `regime ok`, `confirm bit_exact=True talk_safe=True wall_ok=True`, Tetra at **along 907.9
              lat -2.44, `placeable` TRUE**, `placement 31.406 u` (idx 287), terminal `speed 23.87 but
              ready=False`, bound 75.4, **VERDICT fail -- on `complete`, and only on it**. So the frame
              budget is NOT the binding constraint; the plan runs out of thread, not of frames.
            - **THE REMAINING GAP IS NOW ARITHMETIC, and it is ~10 u of LATERAL worth ~4 frames.** At
              lat **-2.44** Tetra matches the thread only at its FAR end (`lat_at(984.1) = -2.09`), so
              she needs **+76 u** of further along (~6 frames, blowing the budget). Sitting ~10 u higher
              (**lat ~+8**) she would match it at the NEAR end (`lat_at(937.5) = +7.95`), only **+30 u**
              away (~2.4 frames, INSIDE the budget). Same distance to the coord, four frames apart,
              decided entirely by the lateral the last cycle leaves. Note the cheap-node contrast in the
              same run: a 1-cycle solve lands lat **+7.91**, `lat_error` **-0.04** -- dead on the near
              end -- so the on-thread lateral is reachable and the later cycles lose it.
            - **NEXT, in this order.** (1) **Rank/steer the LAST cycle on `lat_error` against the NEAR
              end**, not on down-herd progress: +8 rather than -2.4 is worth ~4 frames and turns a
              73-frame `fail` into a candidate PASS. (2) **Rule 3 is a separate miss**: the terminal
              ends `ready=False` (speed 23.87, but travelling AWAY, so the 180 would turn Link back
              into her) -- the placement frame has to be one where he is closing, which is a phase
              choice inside the glide, not a new mechanic. (3) If more roll survivors are wanted the
              gate to attack is **`followed`** (26670 of 27.5k cycle-3 aims; `aim_wall` is 76), i.e.
              the ~400 u roll leaving the 230 u shell -- a shorter roll or a contact-preserving fan,
              not the rank. And do NOT over-fit the mid-chain lateral: it OSCILLATES (+5.8 -> -39.9 ->
              +8.9 -> -2.4), so ranking a mid-chain beam on it would have discarded the survivor that
              came back. Iterate from `solve dump=<path>` + `beam_io.rebuild_beam` (bit-exact) rather
              than re-paying the 940 s.
              **Session 62 followed all of it and OVERTURNED item 1 -- see the box below: the lateral
              is not the gap.**
      - [~] **THE LATERAL IS NOT THE GAP. THE TERMINAL IS OUT OF PUSH (session 62).** Session 61
            handed over "steer the last cycle's LATERAL to the thread's near end -- worth ~4 frames
            and the whole remaining gap". Both halves of it are now built, measured and gated; the
            steer does what it says and the gap does not move, because the gap was somewhere else.
            The blocker is now stated in units that name a mechanism.
            - **BASELINE, re-run first: s61 reproduces to the digit.** `full_herd solve cycles=3`
              (956 s): cycle 1 275.8 u / 21 f / 13.135, cycle 2 590.9 / 46 / 12.846, cycle 3 869.2 /
              69 / 12.597, terminal to **73 frames, timeloss +0, wall +50.4, in regime, bit-exact,
              placement 31.406 u from idx 287, lat -2.44, ready=False, VERDICT fail on `complete`**.
              Dumped via `beam_io`, and every measurement below is off that dump rather than off a
              re-search -- which is what made an eight-experiment session affordable.
            - **BUILT: the lateral half of the objective's arithmetic** (`objective.LATERAL_RATE` /
              `thread_frames` / `thread_cost`, gated). A finish costs the **max** of along/`PUSH_CEILING`
              and lateral/`LATERAL_RATE` -- one push moves both axes, so they are not additive -- and
              it is minimised over WHERE on the 47.6 u segment she stops, because the two ends want
              different laterals. `LATERAL_RATE` is MEASURED (`full_herd.lateral_authority`: hold each
              terminal-alphabet stick 6 frames, read the spread of laterals reached) at **2.94 u/f**
              on the synthetic bed and 3.5-5.9 on the real endpoints, i.e. lateral is ~4x dearer than
              along. It is a RANK and never a prune: `LATERAL_RATE` is a sustained rate a single frame
              can beat, so `thread_cost` is not admissible and `_budget_cut` stays on `plan_bound`
              (gated by a wiring spy).
            - **AND ITS MEASURED SHAPE SAYS WHY IT IS THE LAST CYCLE'S RANK, NOT THE CHAIN'S**: the
              lateral is FREE while there is more along left than lateral. At the cycle-2 endpoint
              39.9 u off-thread costs exactly zero extra frames (~26 along frames remain, the lateral
              needs ~14), and it only becomes the binding term inside the last ~70 u. That is the
              same conclusion s61 reached from the oscillation (+5.8 / -39.9 / +8.9), now falling out
              of the arithmetic instead of being a policy laid on top of it.
            - **BUILT: `glide_probe`, the last cycle's keep** -- `roll_probe`'s counterpart one stage
              later, and the same lesson. `roll_probe` exists because the endpoints that look best are
              not the ones a roll can fire from; the last cycle has that bug against the TERMINAL,
              because `thread_cost` scores where TETRA is and says nothing about how much push LINK has
              left. So run the real glide, short and narrow (5 frames, beam 4, ~1 s), and rank the
              endpoint by the best `frames + thread_frames` it hands over. It measurably
              discriminates -- the 21 cycle-3 survivors span **74.24 .. 87.14**, and it demotes the
              endpoint `thread_cost` ranks best (node 6, cost 74.47, glides to only h 5.47).
            - **BOTH ARE INERT ON THIS BEAM, and that is a measurement, not a hedge.** Re-running
              cycle 3 from the dumped cycle-2 beam with `rank='thread'` + `glide_keep=True` (508 s)
              against `rank='bound'` gives the **same 8 nodes** and the same terminal endpoint
              (31.406 u, lat -2.44). Same signature as s61's two inert ranks: the beam has no
              alternatives to choose between, so a better rank changes nothing.
            - **THE MEASUREMENT THAT MOVED THE BLOCKER: the terminal glide is EXHAUSTED, and the
              lateral is fine.** Gliding each cycle-3 endpoint out 14 frames ranked on the thread
              cost: along advances for **3-5 frames and then FREEZES** -- node 0 to 891.3, node 3 to
              904.6, node 6 to 876.3 -- and stays frozen for eight more generations before the beam
              dies on the wall prune. Link's centre-to-feet distance grows **monotonically 66 -> 129 u**
              through it: his post-roll EBS carries him past the 80 u freeze bar and he cannot get
              back. Adding a contact tie-break to the rank changes **nothing** (attributed, not
              assumed: re-ran with and without). Meanwhile node 3 reaches **lat +8.64 at along 901.4**
              -- essentially ON the thread's near-end lateral (+7.95). **So the lateral is steerable
              and nearly free, and s61's "~10 u of lateral is the whole remaining gap" is wrong: the
              gap is ~33 u of ALONG that no glide can supply.**
            - **THE BLOCKER, RESTATED AS PHASING.** The chain's own sustained rate reaches the
              thread's near end (937.6 u) at frame **74.4 -- inside the 75-frame budget**. But the
              herd arrives in ~280 u CYCLE CHUNKS, and the last chunk ends at along 869-882 at frame
              69-70, leaving ~68 u to a glide that can only add ~23-35 u before Link separates. The
              deficit is therefore not rate and not lateral: **the last roll ends in the wrong place**.
            - **TWO PHASING LEVERS TRIED AND MEASURED OUT, so the next session does not re-pay them.**
              (i) **A LONGER LAST JUNCTION does not exist to be had**: the junction herds while it
              repositions, so more junction frames should push the roll's start down-herd -- but
              raising `junction_beam(max_frames=)` from 12 to 18 to 24 produces **byte-identical dead
              counters and the identical 21 roll survivors**, because the beam empties on the PURSUIT
              BOX long before the cap (measured directly on a cycle-2 node: same 6576 `outbox` /
              15618 `unarmed` at 12 and at 24). The junction's length is bounded by the posture it has
              to preserve for the roll, not by a parameter. (ii) **A WIDER cycle-3 beam does not help
              either**: at `beam=10` two more nodes appear, including the s61-reported lat **+8.90**
              endpoint -- and `glide_probe` correctly ranks it WORSE (74.74) than the ones already
              kept, and the terminal still lands at 31.406 u.
            - Gates: `tests/test_objective.py` 17 -> **21**, `tests/test_full_herd.py` **+3**. Full
              suite **684 passed, 0 failed, 1 skipped, 8 xfailed** (the same 8).
            - **NEXT: the cycle COUNT is the phasing knob that is left.** Four cycles with the budget
              cut ON, so the beam is forced to find SHORTER cycles that land the last roll near 937,
              instead of three long ones that land it at 869 and hand the rest to a glide that has
              nothing left. Do not spend more on the terminal or on ranks: the terminal is measured at
              3-4 frames and ~30 u before Link is gone, and three ranks now produce byte-identical
              beams.
              **Session 63 measured the cycle atom and this next step is RETIRED, unrun: a cycle is
              junction 4-5 + arm 2 + roll 16 + exit 2 = 23-25 frames, so four of them cost >= 90
              frames against a 75-frame budget, and a fourth roll would herd Tetra to along ~1120
              past a thread that ends at 984. See the s63 box below -- "out of push" was also wrong.**
      - [~] **THE PLAN IS NOT OUT OF PUSH -- IT SPENDS 27 u OF IT SIDEWAYS (session 63). The
            shortfall is DIRECTIONAL, and the axis is LINK's lateral, not Tetra's.** Session 62
            handed over "the terminal is exhausted; the cycle COUNT is the phasing knob left".
            Both halves are now measured out, and the accounting that replaced them is exact
            rather than inferred, because Tetra is stt-3 and has no foot term: her whole
            displacement IS the push, so a plan's along shortfall decomposes with nothing to fit
            (`objective.push_budget`).
            - **THE LEDGER of the s61/s62 winner (73 frames, 29.64 u short), phase by phase.**
              Push MAGNITUDE bought **935.13 u = 98.5% of 73 x `PUSH_CEILING`**, and it is saturated
              EVERYWHERE -- junction1 106.9%, roll1 98.9%, junction2 98.0%, roll2 98.2%, junction3
              96.2%, roll3 98.6%, **the terminal 99.2%**. What reached the target axis was 907.89 u.
              The difference, **27.24 u, went sideways** -- against a 29.64 u miss. So s62's "the
              terminal is out of push / along FREEZES" reads a 99.2%-saturated stage as exhausted:
              its 6 frames buy 77.41 u of push where the straight line to coord 287 is 70.4 u. It
              had enough. It spent 10.89 u of it sideways, and roll3 spent 10.57.
            - **AND THE HUMAN IS THE CONTROL.** His recorded 44 frames buy **12.805 u/frame at the
              same 98.5%** -- the search's plan buys 12.810 -- and he spends **2.10 u** sideways
              where it spends 27.24. Identical push, different straightness. Two consequences: a
              shortfall can never again be blamed on push magnitude, and **the frames a STRAIGHT
              plan needs is 937.53/12.805 = 73.2**, not the 72.1 that `PUSH_CEILING` implies. That
              is inside Dereck's accepted 75 with under 2 frames of slack -- which is exactly why
              27 u of sideways is fatal and 2 u is not.
            - **THE CYCLE-COUNT LEVER IS DEAD ARITHMETICALLY, and it cost nothing to find out.**
              Read off the dumped logs (roll triggers at log idx 1/26/50, `FRONT_ROLL` spans
              3-18/28-43/52-67): a cycle is **junction 4-5 + arm 2 + roll 16 + exit 2 = 23-25
              frames**. Four cycles therefore cost **>= 90 frames** against a 75-frame budget, and a
              fourth roll would herd Tetra to along ~1120 past a thread that ends at **984**. The
              s62 next step was retired without running the 30-minute solve.
            - **THE TERMINAL IS RANK-INERT, MEASURED SIX WAYS -- so its limit is geometric.**
              `terminal_targeting` from the dumped cycle-3 beam under `placement` / `thread` /
              `frame_minimal` x beam 48 / 192 returns the **identical 31.406 u at frame 73**, every
              time. That is the third rank-inertness result in a row (s61's two, s62's two), and it
              is what redirected this session from ranks to reachability.
            - **REACHABILITY, the measurement the two inert ranks left open** (`reach2.py`/
              `reach3.py`: every R1 roll survivor off every ROLLABLE junction endpoint, both stages
              widened past the real stage's `jn_keep`/`aim_keep` funnels, ~20 min):
              - **Cycle 2 HAS an on-corridor alternative and the rank throws it away.** The beam
                kept along 590.7 / lat **-40.49** (45.5 u off the push corridor) at `plan_bound`
                **72.94** -- BEST -- with along 585.9 / lat **-2.02** (7.0 u off) at 73.06, **0.12
                frames behind**, and along 571.7 / lat +5.98 (1.1 u off) at 73.14. That 45 u
                excursion is what the last roll and terminal then paid 21.5 u of sideways to undo.
              - **Cycle 3 is a razor: SEVEN reachable roll endpoints in total** (1000 junction
                endpoints probed, 4 rollable) -- which is exactly s62's 21 = 7 x 3 camera targets.
                The lateral cannot be fixed at cycle 3; there is nothing there to choose.
            - **THE AXIS IS LINK'S LATERAL, NOT TETRA'S -- a hypothesis of mine, killed by
              measurement.** The one cycle-3 endpoint ON the corridor (Tetra lat +8.90, 0.95 u off,
              70 frames) leaves **Link 47.0 u off her lateral**, so his push points sideways: its
              terminal recovers **7.6 u** (pd 61.6 -> 54.0) where the beam's own endpoint recovers
              **39.0** (70.4 -> 31.4). Across all three endpoints whose terminals were run the
              recovery is monotone in Link's offset -- **16.6 u -> 39.0, 22.8 -> 14.0, 47.0 -> 7.6**
              -- and all seven reachable endpoints sit **16.6-56.7 u** off, while the human never
              exceeds **12 u** and `two_roll.alive` admits **60**. `glide_probe`'s s62 demotion of
              the +8.90 endpoint was therefore RIGHT, for a reason s62 did not have.
            - **AND THE TWO ARE ANTI-CORRELATED INSIDE A ROLL -- which is the session's structural
              finding, and it explains four sessions of inert ranks.** The plow ejects Tetra AWAY from
              Link's exec Co-centre, so moving her TOWARD the corridor requires him to sit off it on
              the far side. Measured at cycle 2, from a cycle-1 endpoint with Tetra 3.5 u off the
              corridor and Link +7.9 u off her lateral, every reachable roll breaks one or the other:
              the corridor-good endpoints (Tetra lat -0.03 / -1.81 / -2.02) leave **Link -50.8 /
              -58.1 / -50.2** u off her, and the ones that keep Link inside the human's envelope
              (+10.2..+14.9) leave **Tetra 45-59 u off the corridor**. The corridor-good ones are
              REACHED and KEPT by the rollability stage, then correctly dropped by `require_quality`
              -- with Link 50 u off-line the next junction cannot continue -- so they never appear in
              a mid-chain beam whatever the rank. That is why s61's lateral rank, s62's `thread_cost`
              + `glide_keep`, and this session's first two keeps were all inert mid-chain: **within a
              single 16-frame roll the two cannot both be had.** The human has both (Link within 12 u
              AND 2.10 u of total sideways), so it is reachable -- just not by choosing a roll aim.
            - **WHERE THE KEEP DOES BITE: the LAST cycle, where `require_quality` is off** -- and it
              buys rule 3. Wiring the corridor keep into the beam cut left cycles 1-2 byte-identical
              (same 9 survivors, offsets 44.9-59.0) and changed cycle 3, whose beam then held offsets
              **1.5..17.2**. Two full solves, ~930 s each, differing only in the last cycle's keep:
              - keep = glide bound + **corridor** -> **74 frames (timeloss +1), terminal speed 20.86
                `ready=True`** (rule 3 PASSES, where s61/s62 ended `ready=False`), thread error
                **-4.22 u** (Tetra along 904.3 lat +3.72, `placeable`), wall +57.4, in regime,
                bit-exact, **33.5 u short**;
              - keep = glide bound + **alignment** -> s62's plan reproduced to the digit: 73 frames,
                `ready=False`, thread error -10.38, **31.4 u short**.
              So the two frontiers TRADE rule 3 against placement distance, and the 74-frame one is the
              one a frame of herding from a PASS. The final code keeps all three orders at every cycle,
              and `terminal_targeting` now reports `closest_ready` beside `closest` -- because `closest`
              is rule-3-blind and would have reported only the 31.4 (gated).
            - **BUILT + GATED.** `objective.push_budget` (the accounting, wired into `score_plan` as
              `push`/`sideways`/`push_saturation`/`sideways_frames`), `objective.push_corridor` (the
              straight line `frame_floor` already prices the bar against -- derived, no new
              constant), and `full_herd._mixed_beam`: both the cycle beam cut AND
              `roll_candidates`' `aim_keep` cut are now MIXED keeps over the rank PLUS the corridor
              offset PLUS |Link - Tetra lateral| (`metrics['lat']`, which already existed). Keeps,
              never ranks, so the rank's own best always survives and s61's oscillation warning still
              holds. Honest scope: the aim-cut half is **inert on today's stages** (R1 rarely exceeds
              `aim_keep` -- ~1.7 survivors per endpoint at cycle 2), kept because it is the correct
              shape and costs nothing; the beam-cut half is what produced the s63 result above.
              `tests/test_objective.py` 21 -> **24**, `tests/test_full_herd.py` +2.
            - **NEXT: correct the lateral in the JUNCTION, not in the roll.** The anti-correlation says
              a roll cannot fix Tetra's lateral without putting Link where the next cycle cannot
              continue -- but the junction can, because Link repositions there in single frames with no
              400 u commitment, and the plan only needs **~9 u of net lateral** (Tetra +5.8 -> +7.94)
              across 73 frames. So: (1) rank roll aims by DRIFT (Tetra's lateral CHANGE across the
              roll) instead of by where the lateral lands -- low-drift aims exist (+0.14 u was measured
              at cycle 2) and a chain of them needs no correction at all; (2) give `junction_beam`'s
              frontier a corridor term beside its cone-deficit/flatness pair, so the few junction
              frames are spent moving her onto the line while Link re-arms. Do NOT re-pay: terminal
              ranks (six configurations, byte-identical 31.406), the cycle count (the atom is 23-25
              frames), "more push" (98.5% saturated everywhere), or a keep that only re-orders roll
              ENDPOINTS mid-chain (`require_quality` gates them, measured above).
              **Session 64 ran both moves and RETIRED them: the junction's authority is real and
              cannot be spent, because ARMING is what destroys the corridor. See the box below.**
      - [~] **THE JUNCTION CANNOT FIX THE LATERAL EITHER -- STEERING AND ARMING ARE MUTUALLY
            EXCLUSIVE INSIDE IT (session 64).** Session 63 handed over "correct the lateral in the
            junction, not in the roll", on the premise that Link repositions there in single frames
            with no 400 u commitment. **The premise is TRUE and the conclusion is FALSE**, and one
            measurement separates them (`full_herd.junction_authority`, new + gated).
            - **THE AUTHORITY IS REAL, and bigger than the plan needs.** Holding one
              `junction_alphabet` member for 5 frames spans corridor offset **0.79..14.10** on one
              cycle-1 node and **0.01..9.16** on another, entry 3.51 -- Tetra lateral spread 13.1 /
              11.0 u, **2.6 / 2.2 u per frame**, the order of `LATERAL_RATE`. The corridor-good
              branches are not exotic and not pruned: they clear the box, the walls and the regime
              with Link INSIDE the human's envelope (offset **0.01** at Link lat -7.56, lead -46.6),
              against a beam that lands its own endpoints at **8.12** and **13.73**. The plan needs
              ~9 u; the junction has ~13.
            - **AND IT CANNOT BE SPENT: a constant stick never ARMS.** Zero of 274 x 2 held families
              produce a gate-passing (`two_roll.junction_gates`) endpoint, **with the pursuit box on
              OR off** -- so the box is not the blocker. Arming needs a VARYING sequence (clear the
              +-90 deg cone, then L plus a toward-Tetra stick on the delay-1 timing), which is
              exactly what a sustained steering stick is not. Confirmed from the other side: the
              shipped `junction_beam` run FROM a corridor-good steered state yields **0 armed
              endpoints in 6 further frames**.
            - **THE ONE ARMING ROUTE THAT DOES FIRE PRICES THE MECHANISM.** `turnaround_and_flip`
              (s33's tight cycle, the s42 junction family generator, never before run from a steered
              state) arms 32 times from a 0.79 u steer -- and the armed states carry corridor offset
              **12.41..13.09**, `preroll` **-22.9** where a flip needs >= +17, so **0 of 32 are
              rollable**, at **26 junction frames** against a 23-25 frame cycle atom. So the arming
              frames are themselves what spend the junction's authority in the wrong direction, and
              they are not optional. That is the whole finding in one line.
            - **THE THREE FRONTIER VARIANTS THE MOVE IMPLIED, ALL MEASURED.** A corridor order MIXED
              into `_frontier_score`'s cut is **byte-identical** to the shipped one (636/636 and
              2288/2288 endpoints, same rollables); a uniform STRIDE over the ties gives **74
              endpoints, 0 rollable**; a corridor order on a 2-frame LOOKAHEAD gives **424 endpoints,
              1 rollable** (vs 636 / 33). Move 1 (rank roll aims by DRIFT) never became reachable:
              its premise was that a better roll endpoint survives, and the reachability join below
              says none does.
            - **WHY THE BEAM IS BLIND, LOCALISED.** At generation 1 the input pipeline's delay-1 lag
              makes all 274 candidates **physically identical** (Link spread 0.000, Tetra spread
              0.000) -- so they TIE on `_frontier_score` and the frontier keeps *the first 24 in
              ALPHABET order*; every later generation descends from that arbitrary slice, which is
              why its candidates share one corridor offset to 2 dp and why `sorted`'s stability makes
              a corridor order a no-op. `lateral_authority` already noted the degeneracy makes "the
              early ranking arbitrary"; this is the rest of that sentence.
            - **THE ANTI-CORRELATION, NOW OVER THE WHOLE REACHABLE SET rather than three sampled
              endpoints** (join of s63's `reach2.json` survivors against their endpoints): of the 140
              cycle-2 R1 survivors, the **26** with Link inside the box (|Link - Tetra lat| <= 17.99)
              have corridor offset **>= 56.60 u**, and every corridor-good one (<= 2 u) leaves Link
              **46-48 u** off. The two properties are **DISJOINT** -- so no keep, rank or frontier
              anywhere in the cycle can hold both, which is the general form of s63's finding.
            - **AND THE ROLL-ENTRY GEOMETRY PREDICTS WHICH SIDE YOU LAND ON**, which is where the next
              session should aim. Entries with Link ON Tetra's lateral (|dl| ~ 0.2-0.5) exit at
              corridor offset as low as **1.14**; entries at dl **17.0** exit at **102..165**. But
              the entry set is IMPOVERISHED: the whole dump holds **6 distinct entry geometries**, all
              with Tetra already **8.12-13.73 u** off the corridor -- never the 0.01-0.79 the junction
              demonstrably reaches, because those states cannot arm.
            - **BUILT + GATED.** `full_herd.junction_authority` (the authority AND the arming count,
              both halves, ~15 s off one `cycle1_nodes` node -- no chain) +
              `tests/test_full_herd.py::test_junction_authority_is_real_and_cannot_be_armed`, which
              fails loudly if a held family ever arms. Offline suite **690 -> 692**.
            - **AND A REAL SIM BUG, FOUND BY THE STRIDE PROBE AND FIXED DECOMP-FIRST.**
              `tww_sim/land/procs/move.py` `_set_speed_and_angle_normal` dropped the decomp's explicit
              ``else { dVar9 = 0.0f; }`` (`d_a_player_main.cpp` 2828-2830) on the bVar2 arm -- the
              fast near-reversal that is not a genuine stick flip -- so that branch left ``dVar9``
              unbound and raised **UnboundLocalError** instead of sliding with no acceleration. It is
              reachable from a plain junction search state. The NATIVE port (`_anmc.pyx`) inits
              dVar9 to 0.0 and was always right, so this is the Python path catching up to it; no
              bit-exact result can move, because every path that reached it crashed.
              Gated by `tests/test_land.py::test_near_reversal_slide_keeps_dvar9_zero_and_does_not_raise`
              (verified RED without the fix).
            - **RULE 3 IS WRONG, TWICE OVER (Dereck, session 64) -- and the correction disqualifies
              the current best plan.** `objective.turnaround_ready` asserts "a 180 turnaround snaps
              the facing across travel; the resulting motion is the reverse" and scores it at ZERO
              frames. Measured, both halves fail:
              - **THE NEGATION DOES NOT REVERSE MOTION.** The proc-7 DIR_BACKWARD branch
                (2913-2915) flips `current.angle.y` by 0x8000 AND negates `mNormalSpeed`, so the two
                cancel and the HEADING IS UNCHANGED: cycle-3 endpoint travel **4666 @ -23.2** ->
                travel **35434 @ +17.6**, same motion direction (s47 saw the consequence -- "a
                turnaround PRESERVES the -25.7 so doesn't rescue it" -- without naming the cause).
                So the flip is the LAUNCH, not the escape.
              - **AND THE RULE PASSES PLANS THAT CANNOT DO THE MANEUVER.** `ready = speed > 0 and
                away > 0` is nearly a tautology in the backslide. The negation MIRRORS the entry
                speed, so what a terminal can arm is set by the EBS speed it leaves: **-25.73 ->
                +17.6** (roll-capable; `_roll_init` clamps 17.6*1.5+0.5 to the full **26**) but
                **-20.86 -> +14.3**, under the +17 a full roll needs. The 74-frame winner ends at
                -20.86, so it reads `ready=True` and **cannot arm at all**. Rule 3 is really a floor
                on the terminal's EBS speed (~-22), which is a constraint on where the HERD stops.
              - **THE CONVERSION IS THE ROLL-CHAIN PRIMITIVE, and it is aim-sensitive.** L + a stick
                along Link's TRUE heading -- `current.angle.y + 0x8000` while speedF is negative --
                fires the negation; aiming at the raw `current.angle.y` field reads DIR_FORWARD and
                never flips (cost me a probe). Two L-frames land it, and the window is **ONE frame**:
                the negation re-fires while the ATN condition holds, so the next frame flips back
                (+17.6 -> -17.3). It is landed on deliberately, exactly as each herd cycle arms.
              - **THE EBS SUSTAINS; A NEUTRAL STICK DOES NOT.** The right `ess_fan` stick holds
                **-25.7 FLAT over 6 frames** (terminal: -20.8 flat) where neutral brakes -25.7 ->
                -11.1. Any away-turn measurement that shows the glide bleeding 2-3 u/frame is
                measuring its own alphabet, not the mechanic.
              - **THE SKID GATE, decomp-exact** (`checkNextMode` 4499-4509): procSlip needs
                `dist(m34E8, travel) > 0x7800` AND `speedF/mMaxNormalSpeed > 0.6` AND
                `getDirectionFromAngle(m34EA - m34DC) == DIR_BACKWARD`. **m34DC is THIS frame's stick
                want-angle and m34EA the PREVIOUS frame's**, so the skid arm fires only on a SLAMMED
                stick (|delta| > 0x6000 in one frame); rotating the stick around routes to
                `procMoveTurn(1)` instead, at any speed.
              - **GROUND-MOTION reversal is a DIFFERENT quantity from the travel field**, and far
                more expensive: searched over the full circle + the ESS fan, the motion 180 lands in
                **2 frames but at speedF ~ -9**, and NO sequence reverses ground motion while holding
                |speedF| >= 17 within 5 frames. Also, every away-turn traced moved **Tetra 7-19 u**,
                which would undo a placement -- she is frozen only above `CO_RADII_BAR` (centre_feet
                >= 80).
              - **NOT WIRED.** `turnaround_ready` is unchanged on disk; the correction above is
                measured, not shipped. Wiring it will invalidate the 74-frame plan and most of the
                beam (the terminal glide is what bleeds -25.7 to -20.9), so it moves the BAR, not
                just the score. **(Wired in session 66: `turnaround_ready` is GONE --
                `objective.terminal_moving` + `escape_ready`, the s66 box.)**
            - **NEXT (Dereck, end of session 64): WORK OUT THE AWAY-WALK. It is KNOWN TECH -- the
              task is to figure out HOW IT WORKS, not to establish that it is possible.** Once Tetra
              is in position, Link has to walk AWAY from her to start the roll clip into the corner.
              The pieces above are the launch half and they are settled; what is not worked out is
              the ESCAPE, and the constraints it has to satisfy are all now measured:
                * the negation cannot do it (heading unchanged -- it is the launch, so it belongs
                  LAST, as the two frames before the roll, not first as the escape);
                * Tetra must not move, so the escape has to respect `CO_RADII_BAR` (centre_feet >= 80);
                * the flip mirrors the entry speed, so the EBS has to still be ~-25.7 when it fires
                  (a brake-to-rest-then-walk escape cannot then arm above +17);
                * ground-motion reversal at speed is NOT available (2 frames at -9, nothing >= 17 in 5).
              Read those four together before proposing a shape. Reference material for the mechanic:
              `reposition.turnaround` / `l_release_early` (s33's retention + 1-frame facing snap),
              `two_roll.turnaround_and_flip` (the arming pair), and `full_herd.walk_to_entry` /
              `decel_place` / `homing_place` (s47-51, the Link-only navigation above the freeze bar).
              The synthetic beds `synthetic_frozen_arrival` / `synthetic_hot_arrival` develop it
              WITHOUT the ~930 s chain.
              Do NOT re-pay: the junction moves (measured, this box), terminal ranks (six
              configurations, byte-identical 31.406), the cycle count (atom 23-25 frames), "more
              push" (98.5% saturated everywhere), or any keep over roll ENDPOINTS mid-chain.
              Still open behind it, when the away-walk is understood: the ROLL-ENTRY set is
              impoverished (6 geometries, all 8-14 u off the corridor) and entry geometry predicts the
              cycle outcome (dl 0.2-0.5 -> exit off 1.14; dl 17.0 -> exit off 102-165), so sweeping
              the entry as a first-class axis is the lever the reachability join leaves open.
              **Session 65 worked out the away-walk's mechanics and shipped the atom -- see the box
              below.**
      - [~] **RULE 3 AND THE TERMINAL ARE WIRED TO THE ATOM, AND THE HONEST FRONTIER IS 26.5 u
            SHORT AT +5 (session 66).** The s65 handoff's steps (1) and (2), shipped and solved
            once for the re-baselined bar.
            - **RULE 3 (`objective.py`): `turnaround_ready` is GONE.** The cheap per-frame half is
              `terminal_moving` (Link still MOVING -- all a beam can afford, and all that is true
              per-frame: a rest terminal has nothing for the conversion to mirror); the EXACT bar
              is `escape_ready` -- run the s65 atom off the terminal state (`away_walk.probe`) and
              read the acceptance off the measurement (`away_walk.fires`: l_ok, SEPARATED, dips <=
              `DIP_BUDGET`, receding at the cap). `full_herd._terminal_ready` is the cheap half;
              `score_plan(run=)`/`replay_and_score` run the exact probe on winners, and **when it
              fires the plan is scored POST-atom: placement, thread position and frame count all
              read at the SLAM** (the conversion frames are the plan's own last push frames).
              Node 1's rest endpoint now reads NOT READY exact (nothing to convert); the human
              window's mid-roll endpoint keeps its cheap READY (a window, not a plan).
            - **THE TERMINAL (`full_herd.terminal_targeting`, atom mode -- default under the
              `'thread'` objective): placement is a POST-atom fact.** `_atom_place` probes the atom
              from a candidate, requires it to FIRE, and reads Tetra's distance at the slam; the
              thread rank aims the glide at coord-minus-residual (`_terminal_score(resid=)`), with
              the residual PROBED per state and refined by every fire -- measured 38-68 u across
              glide states on the bed (the s65 34.8-40 was two knob variants of one state), so a
              constant would have been wrong within one generation. `atom_probes` (2/gen) bounds
              the cost to the most-landable candidates by |pre-atom dist - residual|. Placed nodes
              carry the whole atom log through the handoff + `pre_run`/`pre_log` (what
              `confirm_plan`/`replay_and_score` consume). Gates:
              `tests/test_objective.py` (the cheap/exact split, the residual read),
              `tests/test_full_herd.py::test_the_atom_wired_terminal_places_post_atom_at_the_slam`
              (probe the bed's residual, start that far short, the atom lands her ON the coord;
              frames count to the slam). Offline suite **696 -> 698**, 0 fail, same 8 xfails,
              land goldens byte-identical.
            - **ATOM HARDENING (s66, found by the solve crashing on a real cycle-3 state):
              separation joined the acceptance.** A deep-contact terminal can be receding at the
              walk cap with the exec centre still INSIDE the 80 u Co bar -- Tetra still taking
              push -- so `fires` now requires `freeze_f` and the atom runs until receding-at-cap
              AND separated. Also: probe clones detach a wired camera (`_clone_for_atom`, the
              commanded-csangle convention; the csangle used is recorded on the result -- its
              C-stick-slew realization is **the open camera leg**, same shape as the roll stage's
              `target_cs`), and a terminal with no ESS snap window still runs the no-turnaround
              variants on its live csangle.
            - **THE RE-BASELINED SOLVE (`full_herd solve`, 846 s, beams dumped
              `_generated/s66_solve_beams.json`).** Chain unchanged (cycle 3: 8 nodes, 869.2 u in
              69 f, 57.5-70.4 u from a coord, corridor offsets 1.5-17.2). Terminal, honest for the
              first time: **NOT placed -- closest POST-atom placement 26.494 u at slam frame 78
              (+5 vs the 73 floor)**, atom firing, bit-confirmed pre-atom log, wall-free,
              in-regime, terminal speed 25.45 READY exact. The s61/s63 "31.406 u at 73 f" survives
              only as the rule-3-CHEAP diagnostic; it was never a plan (its terminal could not
              escape). **The shortfall is still DIRECTIONAL, not push**: the endpoint sits lat
              -4.43 = 12.37 u off the thread, `placeable=False` -- the s63 sideways accounting
              outlived the rewire. The blocker is unchanged in kind: the chain hands the terminal
              endpoints 13.7-17.2 u off the corridor (the two 1.5-offset cycle-2 branches carry
              Link-Tetra lat +47, unsquare), and 12 glide frames cannot buy ~12 u of lateral at
              2.9 u/f AND keep the EBS the atom needs.
            - **NEXT, in order.** (1) **Attack the lateral handoff**: iterate the terminal off the
              DUMPED cycle-3 beam (`beam_io.rebuild_beam`, no 14-min chain) -- longer horizon
              (`tframes`), wider `atom_probes`, and rank experiments are now ~1-min loops; if the
              glide provably cannot pay ~12 u, the fix is upstream (the corridor-vs-squareness
              trade in the cycle-2/3 keeps, or the ROLL-ENTRY axis -- still the standing lever,
              6 geometries all 8-14 u off corridor). (2) **The entry leg** (s65 step 3):
              `walk_to_entry`/`reach_precise` from the atom's handoff (receding at 17) to
              `ENTRY_ROLL_POS` facing 40835. (3) **The camera leg**: realize the atom's commanded
              csangle with a C-stick slew so an end-to-end log replays camera-wired.
              **Session 67 ran (1) and it inverted the reading: the shortfall is an AIM, the terminal
              has no authority at all, and the blocker is the ROLL-ENTRY squareness at cycle 2.
              See the box below.**
      - [~] **THE SHORTFALL IS AN AIM, NOT A LATERAL DEFICIT -- AND THE TERMINAL IS NOT A SEARCH
            SPACE (session 67).** The s66 handoff step (1) was to buy ~12 u of lateral in the
            terminal. Measured off the dumped beam, that is the wrong axis, the wrong sign, and the
            wrong stage, all three. New module `aim.py`, gated `tests/test_aim.py` (6).
            - **THE PUSH IS AN EXACT ONE-FRAME ORACLE (`aim.push_step`), 0-ULP.**
              ``f32(Tetra + (CO_RADII_BAR - centre_feet)/2 * unit(Tetra - exec_centre))`` IS
              `FreeRun.step`'s next Tetra, `_bits`-identical on every contact frame whatever stick is
              delivered (the pipeline acts 2 frames late, so the frame's push is already decided),
              and exactly zero at the bar. So Tetra's whole side of a placement is analytic: the only
              unknown in an endgame is where LINK is.
            - **THE SIGN WAS BACKWARDS.** The cycle-3 endpoints hand Tetra over at lateral
              **+8.90 / +21.19 / +24.61** against a thread at **-2.27..+7.94**: she has to LOSE
              lateral, `lateral_authority` is one-sided losing at every endpoint, and the s66 plan
              lands at **-4.43** -- it OVERSHOOTS the thread and comes out the far side. "The glide
              cannot buy 12 u of lateral" was a plan spending 12 u too much of it.
            - **WHAT IS SHORT IS THE AIM, and the window is a RAZOR.** The thread lies 12.2 deg off
              the herd axis and the approach comes in 13-14 deg off it, so Tetra arrives nearly
              END-ON: the directions that reach the 47.6 u segment span **0.53-0.62 deg** at the s66
              handoff range (`aim.aim_window`; 4.91 deg from the closer, lower-lateral endpoint).
              The endpoints aim **-23.75 / -25.26 / -51.65** deg into windows of
              **[-13.70,-13.08] / [-13.32,-12.80] / [-5.80,-0.89]** -- 10.05, 11.94 and 45.85 deg
              steep, missing the thread by 12.28 / 11.89 / **47.72 u** (`aim.aim_miss`). In Link's
              terms (`aim.centre_lat_needed`) his exec centre must sit **9.15 / 10.86 / 40.96 u**
              lower in lateral. The corridor-good endpoint (Tetra lat +8.90, 1.47 u off) is the
              WORST aim of the eight, which is the s63 anti-correlation stated as one number.
            - **AND THE TERMINAL CANNOT FIX ANY OF IT, BECAUSE IT HAS NO AUTHORITY.** Sweep the whole
              `_terminal_alphabet` (290 sticks x L) off the s66 endpoint and Tetra's position after
              each of the next **FOUR frames is bit-identical across every branch** -- spread
              **0.00000 u** (`tests/test_aim.py` gates the universal two). The pipeline acts 2 frames
              late and by then the actors have SEPARATED, so no stick re-establishes contact. That is
              the whole explanation of the rank-inertness that ate s61-s63 (two configurations, two,
              then six byte-identical 31.406 u): **there was nothing to rank.** The only inputs left
              with authority are the escape's own conversion frames, which is why the s66 winner
              glides for zero frames.
            - **SO THE KEEP MOVED OUT ONE STAGE: `full_herd.escape_probe` + `extend_cycle(
              escape_keep=)` + `chain_herd(last_escape=True)`** -- rank a last-cycle endpoint by what
              its real escape LANDS (`away_walk.probe` -> `aim.landing_miss`), not by what a glide
              reaches (`glide_probe`, now superseded on the last cycle). Re-run off the dumped
              cycle-2 beam (461 s, no chain): **21 survivors, 18 fire, best lands 45.62 u off the
              thread**, and the keep is INERT -- byte-identical 8 nodes. It is the right metric and
              it PROVES the cycle-3 stage cannot deliver the handoff: the candidate set tops out at
              26.49 u (the s66 winner) and the reachability, not the ranking, is the wall.
            - **THE SPEC HAS A SOLUTION, SOLVED BACKWARDS (`aim.handoff_target`/`handoff_spec`).**
              The escape delivers **34.8-47.9 u** from a mid-depth on-line handoff (measured across
              reserves 27.1-43.1; it OVERSHOOTS `push_reserve` because its conversion drives Link
              back in), so the state it must be handed is the thread's near end MINUS that: **Tetra
              at along ~894, lateral ~+2.5, on line, `feet` ~52-56.** A straight herd reaches along
              894 in **69 frames** at `PUSH_CEILING`, and the escape's 4-5 frames finish it --
              **74 frames, +1, inside Dereck's PREFERRED budget.** The plan is not out of frames.
            - **AND THE MISSING FRAMES ARE THE ROLL-ENTRY SQUARENESS AT CYCLE 2 -- one number, with
              the human as the control.** The push law integrates, so the direction a roll carries
              Tetra is the mean of its aims: measured on the s66 plan's three rolls, mean aim
              **+2.55 / -6.42 / +16.56** deg against travel **+2.98 / -6.36 / +18.13**, each roll
              ~205 u long. The human's two recorded rolls enter at aim **+1.22 / -0.70** deg
              (corridor error +0.66 / -1.83) and he ends 44 frames in at corridor offset **0.71 u**;
              the search's roll 1 is the same state and the same +1.22, and then **its roll-2 entry
              aims -10.84 deg where his aims -0.70**. Those ~10 deg over 205 u ARE the -22.6 u
              excursion (corridor offset 11.6 -> 36.0) that roll 3 then pays +18 deg to undo, and the
              s63 ledger's 27.24 u of sideways. **The lateral that steers the push is Link's exec
              CENTRE's, not his feet's**: at that entry his feet sat **+2.22 u** off Tetra's lateral
              while the aim was -10.84 deg (the centre leads the feet ~17 u, and it led sideways) --
              so `extend_cycle`'s ``align_keep`` has been keeping on the wrong quantity, which is why
              keeping by it measured inert.
            - **NEXT: the junction's frontier keeps by AIM.** `junction_beam` ranks its frontier by
              cone deficit and `extend_cycle` keeps by the FEET lateral; neither is the aim.
              Put `aim.corridor_aim_error` in as a keep share (a keep, never a rank -- s43's
              measurement that ranking on flatness/|lat| starves arming still stands), so cycle 2
              fires its roll from a square endpoint, and re-run the chain against the handoff target
              (along ~894, lat ~+2.5 at frame <= 69-70). Behind it, unchanged: the entry leg
              (`walk_to_entry` to `ENTRY_ROLL_POS` facing 40835) and the camera leg (realize the
              atom's commanded csangle with a C-stick slew). Do NOT re-pay: terminal ranks (now
              PROVEN inert -- zero authority), the cycle count (s63), "more push" (98.5% saturated),
              or the lateral-magnitude framing (the sign is the other way).
              **Session 68 ran it, and the keep could not have worked as specified: the frontier had
              no square endpoint to keep, because it was a greedy walk over ONE physics state. See
              the box below.**
      - [~] **THE JUNCTION FRONTIER WAS A GREEDY WALK OVER ONE PHYSICS STATE, AND THE TURN IT WALKED
            IS WHAT WAS SPENDING THE AIM (session 68).** Session 67 handed over "put
            `aim.corridor_aim_error` into the junction's keep". Measured first, as it asked -- and no
            keep could have worked as specified, because the frontier had no square endpoint to keep.
            - **NOTHING ARMED IS SQUARE, and the endpoint aim is QUANTIZED BY JUNCTION LENGTH.** Off
              the dumped cycle-1 beam, **4832** armed endpoints span **-35.9..-15.3 deg** with NOTHING
              inside 15; within one junction length the spread is 0.2-0.3 deg (jf6 -17.3, jf7 -21.5,
              jf8 -27.0, jf9 -32.1) and only jf5 spans a range at all. Meanwhile the cycle-1 EXITS are
              fine (**-4.5..+4.8**) and a plain held-ESS glide from any of them passes |aim| ~ 0 within
              2-5 frames. So the aim was not missing from the search space -- the JUNCTION was
              destroying it, monotonically: the kept frontier reads **-12 -> -20 -> -26 -> -34 -> -41**
              over five generations.
            - **ROOT CAUSE, structural and exact: the frontier TIES, and the tie fills the beam with
              ONE state.** The input pipeline acts a frame late, so all 138 children of a node have
              IDENTICAL physics (measured: **1** distinct `_physics_tag`) and every frontier key -- cone
              deficit, feet lateral, aim -- is the SAME NUMBER across them; a stable sort then keeps
              ``beam`` PENDING-INPUT VARIANTS of a single state. The beam has been walking ONE
              trajectory, and the "diversity" it reported (636 / 2288 / 4832 endpoints) was pending
              variants of one path -- which retires the s43 reading "the win is DIVERSITY, 432 endpoints
              against the family's 7". And the path the stock key walks is the fastest TURN out of the
              talk cone, which is exactly the motion that rotates Link's ~17 u exec-centre lead
              sideways. Gated structurally (`test_a_frontier_generation_is_one_physics_state_so_every_
              rank_ties`), because the fix is worthless if a later change lets it degenerate again.
            - **THE FIX (two keeps, no new rank): `_mixed_beam(group=, per_group=)` +
              `junction_beam(per_state=4, aim_share=True)`.** Cap the slots one PHYSICS state may take,
              and give a share of the frontier to `_armable_square` -- |aim|, and |aim| + the cone
              deficit in degrees, one scalar so neither starves (|aim| alone finds **ZERO** armed
              endpoints -- it never leaves the cone; cone alone walks to -41). Squarest armed endpoint
              per cycle-1 exit, stock -> fixed: node 1 **-15.34 -> +0.03**, node 2 **-15.56 -> -1.90**,
              the human's own exit -2.98 -> +2.42, and nodes 0/3 unmoved at -33/+29 under a frontier
              four times wider. It is also FASTER (46 s -> 22 s: the beam stops re-expanding one state).
            - **CYCLE 2, off the dumped cycle-1 beam, stock vs fixed** (same beam, same 75-frame budget,
              ~400-500 s each): corridor offset at the exit **44.9 -> 37.0 u**, Tetra's lateral
              **-39.9 -> -32.1**, `plan_bound` **72.92 -> 72.81 f**, 7 -> 8 survivors. Real, and small:
              the human's cycle 2 sits **0.71 u** off the corridor.
            - **AND THE `probe_cap` IS A PREFIX, WHICH HIDES REAL COVERAGE -- BUT BUYING IT BACK COSTS
              MORE THAN IT PAYS.** `extend_cycle` roll-probes `uniq[:250]` in collection order, so of
              node 1's 4158 armed endpoints -- **932 of them within 5 deg** -- the 250 probed were all
              -15.5..-15.8 and every square one was dropped. Cutting it as a keep instead (a share by
              squareness, spread over the distinct physics states) does surface them: **7 rollable
              instead of 6, squarest ROLLABLE +1.12 deg instead of +15.52**. It also took cycle 2 from
              8 survivors to **ZERO**, twice -- the rollable-AND-continuable endpoints are concentrated
              in a few early states and only some PENDING inputs of those states roll at all (the s42
              arming lesson), so a spread pool holds one pending each of mostly-uncontinuable ones. So
              `_probe_pool` keeps the prefix as its DEFAULT with the square share as a knob
              (``square_pool``), and the cost is recorded in its docstring and gated
              (`test_the_probe_pool_is_a_prefix_by_default_and_a_keep_when_asked`).
            - **WHY THAT SQUARE ENDPOINT WAS NOT WORTH KEEPING -- the entry aim is the wrong key once a
              roll can be probed.** The +1.12 deg endpoint sits at **jf 12**, where the aim swings
              **5-8 deg per frame**, and the roll it fires leaves Tetra **37.6 u** off the corridor with
              Link **51 u** off her lateral -- and the REAL next junction off it arms **0** endpoints,
              so `junction_quality` was telling the truth rather than proxying badly. `roll_probe` now
              returns what its sweep already knew: ``off``, the corridor offset the best surviving roll
              DELIVERS, and ``off_rate``, what that straightness costs in rate. `extend_cycle`'s
              ``square_keep`` ranks its share on THAT (exact, measured on a real roll), not on the
              endpoint's aim.
            - **The roll's own stick has ~36 deg of authority over the realized travel, and `alive` is
              what kills the straight roll.** Off the unsquare endpoints: entry aim vs realized travel
              correlates only **+0.665** (mean |entry - travel| **14.8 deg**), the travel from ONE
              endpoint spans **-26..+10 deg**, and rolls landing within 2 deg of the corridor exist --
              **25 of them, 1 alive**. The one that lives needs Link **53 u** off her lateral and fails
              `junction_quality`. That is s63's anti-correlation, now measured at the roll-entry level,
              and it says the straightness has to come from the ENTRY, not from the aim fan.
            - **NEXT: buy the squareness at the CYCLE-1 EXIT, because that is where it lives.** Two of
              the five cycle-1 exits cannot be squared at all, the other three only at jf 10-12 where
              the aim is unstable -- while the HUMAN's exit yields a square armed endpoint at jf 8
              (-2.98) that he rolls from, ending his cycle 2 **0.71 u** off the corridor. So widen the
              cycle-1 candidate set (`cycle1_nodes` sweeps aim x tcs x nflip and keeps 8 by
              `plan_bound` + `junction_quality`) and add a keep share by a JUNCTION-SQUARENESS PROBE:
              the smallest `roll_probe`-``off`` reachable through that exit's junction (~15-25 s per
              exit, and there are tens of candidates, so it is affordable). Then re-run the chain and
              score against the handoff target (Tetra at along ~894, lat ~+2.5, frame <= 69-70,
              `escape_probe` / `aim.handoff_spec` as the acceptance). One refinement to fold in: the
              mid-chain aim key points at `objective.push_corridor`'s coord, but the state the chain
              must deliver is `aim.handoff_target` (the coord MINUS the escape residual) -- a ~0.7 deg
              bias at cycle-2 range, which matters against a 0.53-0.62 deg window at the end.
            - Do NOT re-pay: terminal ranks (s67, proven zero authority), the cycle count (s63), "more
              push" (98.5% saturated), the lateral-magnitude framing (s67, the sign is the other way),
              a wider junction frontier (s68: 4x wider moves nodes 0/3 not at all), or a squareness
              share in the probe pool (s68, measured: it stalls the chain).
              **Session 69 bought the squareness where s68 said it lived -- at the cycle-1 EXIT -- and
              cycle 2's corridor offset went 37.0 -> 8.97 u. See the box below.**
      - [~] **THE SQUARENESS IS BOUGHT AT THE CYCLE-1 EXIT, AND WHAT CYCLE 1 IS CHOOSING IS A CAMERA
            TARGET (session 69): cycle 2's corridor offset 37.0 -> 8.97 u, Tetra's lateral -32.1 ->
            -3.65, Link's lateral off her +11.1 -> -0.69.** Session 68 handed over "buy the squareness
            at the cycle-1 exit, because that is where it lives". It is, and the stage was choosing
            with a rank that is ANTI-CORRELATED with it.
            - **THE WHOLE CYCLE-1 CANDIDATE SET IS ONE ROLL AND ITS CAMERA, AND EVERY MEMBER IS
              BOUND-TIED.** Instrumented at the R1/R2 stages: of the entire `half_window` aim fan x
              three ``l_windows``, exactly **3** (aim, window) pairs survive the roll prunes and all
              three are the SAME aim (want 35324) -- the l-window only decides which frame the exit
              lands on (f20 / f21 / f22), and f20's whole tcs family fails `junction_quality`. So the
              set is one roll swept over the 25-value `derived_target_css` grid, of which only **6**
              arm anything at all, and every candidate scores `plan_bound` **71.90**: the frame rank
              cannot separate them, so whatever else the cut ranks on IS the decision.
            - **AND WHAT IT RANKED ON WAS ANTI-CORRELATED.** The deliverable squareness of those six
              spans **11.20 .. 141.83 u** (`junction_square_probe` -- the smallest corridor offset a
              real roll through the exit's junction DELIVERS). ``tcs_keep=3`` cut them by
              `junction_quality`, which counts frames in the pursuit box, and its top three are
              **141.83 / 27.81 / 14.67** -- the worst-but-one first. The best sits at quality rank 5.
            - **THE FIX: enumerate the grid, keep by the probe** -- `cycle1_nodes(square_keep=True,
              tcs_keep=<no cut>)`, a `_mixed_beam` share at the beam cut by the probe's ``off``. 27
              survivors -> 21 unique -> all probed in **308 s**, once per solve. It takes tcs 38788
              (11.20 u) and 38020 (14.51), the two the old cut dropped. **Opt-in, via
              `chain_herd(c1_square=True)`** (default ON): 15 other tests call `cycle1_nodes` only to
              get a node to build on, and making the probe their default cost the suite ~77 minutes.
              A solve wants it; "give me a cycle-1 node" does not.
            - **THE POOL IS WHAT MAKES THE PROBE HONEST, AND THE s68 STATE CAP MUST NOT BE REUSED
              HERE.** Same three exits, four pools: prefix-only **1.34 / none / 27.02**, squarest-only
              **none / 141.83 / 14.67**, the UNCAPPED mix **1.34 / 141.83 / 14.67** (and 12 rollable
              endpoints where each single pool found 9), s68's state-capped `_probe_pool`
              **none / 141.83 / 25.89**. The cap calls an exit that reaches 1.34 u unrollable. The
              distinction is the job: `_probe_pool`'s default is choosing endpoints to CARRY (where the
              spread is right, s68), ``spread=False`` is SCORING an exit. Gated as pure selection.
            - **CYCLE 2, off the identical cycle-2 config and 75-frame budget** (the stock run
              reproduces s68 exactly -- 37.00 u, lat -32.10, bound 72.81, 8 survivors -- so the
              contrast is clean): corridor offset **37.00 -> 8.97 u**, Tetra's lateral **-32.10 ->
              -3.65**, Link's lateral offset from her **+11.14 -> -0.69** (he now stands on her
              lateral, which is the squareness the human has), `plan_bound` **72.81 -> 72.69**, roll
              survivors **18 -> 71**, 8 kept either way. 964 s against 516 (the beam is wider). The
              human's own cycle 2 sits 0.71 u off, so a 52x gap is now 12x.
            - **CONTAINMENT HOLDS, AND THE REMAINING 8x IS THE CAMERA LEG'S REACHABILITY
              (`[[search-space-contains-human]]`).** At f21 the human's Tetra is bit-identical to the
              search's exits and his facing is within **4 BAM**; the difference is the camera (his
              csangle **38776** against the grid's reachable 38675 / 39085) and ~1 u of Link lateral.
              His exit's junction delivers **1.34 u** where the best grid member delivers 11.20. The
              gap is not the keep: `two_roll.roll_segment` holds ONE ``target_cs`` for the whole roll,
              and the ACHIEVED exit csangle quantizes coarsely and non-monotonically (tcs 38404 -> cs
              38159 while tcs 38276 -> cs 38624; tcs 39172..39684 all -> 39428), so 38776 is simply not
              in the reachable set at this roll length.
            - **`aim.handoff_corridor`: correct, derived, and measured INERT at cycle 2.** Every keep
              read the line to the nearest COORD, but the state the chain must deliver is that coord
              minus the escape's residual. Measured, not assumed: probe the real atom on an on-line
              mid-depth arrival at the thread's near end -> resid **43.65 along / +5.47 lat** at feet
              56 -> target along **893.89** lat **+2.47**, reproducing s67's solved-backwards
              "along ~894, lat ~+2.5". The two lines ask an on-line Tetra for aims **0.46 deg apart at
              the cycle-1 exit, 0.68 at cycle-2 range, 1.19 by along 700** -- growing as the plan
              closes. Re-running cycle 2 on it returns the IDENTICAL 8 survivors (the frontier's dead
              counts and the cycle-1 probe values DO move -- best exit 11.20 -> 7.93 u), so it is inert
              at this range; `chain_herd(handoff=True)` keeps it ON because it is the right target and
              the bias grows. Depth is a knob inside the noise: feet 52..64 moves the ask **0.04 deg**.
            - **CYCLE 3 OFF IT: THE PLACEMENT FRONTIER 45.62 -> 15.70 u, AND THE BINDING CONSTRAINT IS
              NOW FRAMES.** Run off the dumped cycle-2 beam (774 s, `escape_keep`): 18 roll survivors,
              **all 18 fire the escape**, and the best lands **15.70 u** off the thread against s67's
              45.62 u frontier -- but at **78-80 frames** against the 75 budget (`plan_bound` 77.27), so
              at the real budget the cut empties (0 survivors). Where the frames go is legible and it is
              NOT the squareness: the cycle-3 endpoints sit at along **947.4 / 949.5**, i.e. **53 u PAST**
              the handoff target at 893.9, with Tetra's lateral back out at **-26.0 / -29.6** and Link
              **45 u** off her lateral. One FRONT_ROLL is ~205 u and cannot stop short, so a cycle 2 that
              ends at along 628 overshoots.
            - **WHICH NAMES THE SAME BLIND CUT ONE CYCLE UP.** `roll_candidates`' ``tcs_keep`` is ranked
              by `junction_quality` at EVERY cycle, not just cycle 1 -- so cycle 3's camera target is
              chosen by frames-in-the-box exactly as cycle 1's was, and cycle 3's roll is now the
              unsquare one (corridor offset **8.97 -> 28.62 u** across it). The cycle-1 fix is the
              template; cycle 2's exit is where it goes next.
            - **AND THE RAZOR IS A PROPERTY OF WHERE THE HANDOFF SITS, NOT OF THE THREAD** (gated):
              from the s66 handoff (along 881.6, lat +21.19 -- short AND off-line) the 47.6 u segment is
              nearly end-on and `aim.aim_window` is **0.53 deg**, while from the handoff target itself
              it subtends **10.04**. Non-monotone in the offset, so this is two measured points and not
              a trend -- but it reframes the endgame: riding the right line is not bias correction, it
              is what opens the window from a razor to a door.
              **Session 70 took the frames back: the overshoot was not a rank or a keep, it was the
              PROBE POOL. See the box below.**
      - [~] **THE FIDELITY GATE IS CLOSED, AND RUNNING IT FIRST WAS THE WHOLE SESSION: IT FOUND THE
            s79 SEARCH SCORING AN ENTRY 26 u FROM WHERE LINK ROLLS, AND THEN QUALIFICATION KILLED THE
            "243 INDEPENDENT LOCI" MULTIPLIER -- ONLY **6 OF 243** CONFIGURATIONS ADMIT A GENUINE
            LOCUS AT ALL, 169 HAVE NO LEVERAGE WHATEVER. STILL 0 GENUINE, BUT THE EVAL IS NOW ~40x
            CHEAPER AND THE FAN IS THE ONLY REMAINING BUDGET (session 80).**
            The s79 handoff ordered the widening first and the fidelity gate second. Reversed, because
            the gate does not only validate hits -- it validates the objective function, and a search
            aimed at the wrong one cannot be rescued by making it bigger.
            - **THE GATE ITSELF PASSES, AND IT PINS THE SEEDING.** A real from-rest walk + A-press
              turnaround roll, run in the WALLED coupled engine and diffed per frame against
              `extract_schedule_at`, matches on all **nine** baked tables. Two things it CLEARED
              rather than found: the reseed's cold anim/pose state is not a problem, and the crash
              latch is not either -- a real roll ARMS `_roll_m3570` where the reseed forces it off,
              and it does contact the wall for ten mid-roll frames, but the bonk cone never lines up
              before the B edge (**0 of 246** entry x facing rolls differ), so `ShoveCtx` having no
              crash branch is exact here. New `harness/tetrapush/roll_fidelity.py`.
            - **WHAT IT FOUND: `link_x0` IS THE POST-ENTRY-FRAME POSITION.** The reseed's step 0 IS
              the roll's SECOND frame (a reseeded FRONT_ROLL advances its frame ctrl on its first
              step; a real entry frame does not). So the entry is the walk endpoint **plus one full
              26 u roll step**, and the lean is one decay tick on. s79 fed the walk endpoint, so
              every one of its candidates was scored at a place Link never rolls from. Both
              conversions are now bit-exact and gated (`roll_entry`, `lean_at_roll`), and the
              pre-entry reading is gated to MISMATCH (`chx/chz`) so the convention cannot drift back.
              The consequence is the bigger half: the step is taken along the AIM, so an aim is its
              own entry as well as its own locus.
            - **THE AIM ALPHABET IS 81 WIDE, NOT 6 -- AND IT DOES NOT MATTER.** s79's six came from
              `reachable_stick_fan(msd_min=1.0)`, the saturated octagon boundary. That floor is not
              physical (the roll takes its speed from the walk cap; `_roll_init` snaps facing to the
              latched target at any deflection), and all 81 aims in the seam window fire the roll and
              land on the facing they command -- measured, read back. But see the next box: only
              three distinct facings are worth aiming at.
            - **QUALIFICATION IS THE REAL RESULT.** `configuration_band` Newton-zeroes the residual
              at a (facing, thrust, lean) and sweeps ACROSS the locus to read that configuration's OWN
              acceptance band. Of 243 configurations, **6 are productive** (really 3 distinct: facing
              ~40820 thrust 15, ~40834 thrust 14, ~40834 thrust 15 -- a **21 BAM** facing window),
              **169 have no leverage** (grad < 1e-3: Tetra is out of Co range on the cut frame, so
              nothing about the entry moves the razor -- the s79 trap, now a cheap measurable), 57
              have leverage but nothing genuine on the residual zero, 11 will not zero.
            - **AND THE WINDOW THE SEARCH WAS RANKING AGAINST IS A UNION.** `fixtures/courtyard_entry_
              locus_s79.json`'s `[-2.5e-6, +1.13e-4]` was measured at ONE configuration off the 288
              coords. Each configuration's own band is 0 to 5e-5 wide and sits offset **on the
              positive side**, so a search centred on resid 0 aims between them. That is why the
              stride-2 pass could report **1018** near-zero candidates and zero clips.
            - **THE PASS.** 18161 candidates (stride 2, 7 base nodes) x 243 configurations, 595 s:
              1018 near-zero, 0 genuine. Re-run against the 6 qualified configurations the same
              candidates cost **2 s instead of 269**. So the eval is no longer the budget -- the FAN
              is, at ~3.5k `FreeRun` steps/s, and that is the next lever.
            - **Gates** (+11 in `tests/test_entry_search.py`, 26 fast + 2 slow): the nine-table
              fidelity diff, the post-entry-frame convention (and the pre-entry mismatch), the
              bit-exact entry/lean conversions, the armed-latch clearance, the analytic schedule
              0-ULP over facing x lean x thrust, the 81-vs-11 alphabet with every sampled aim fired
              and read back, thrust independence, the per-configuration band, the leverage census,
              the walk fan's two prunes, and the signed-gap rank.
            - **NEXT.** The fan is the only remaining lever and it is Python-step-bound. Grow it
              (stride 1, more base frames, then TWO-SEGMENT holds) and, when that runs out, move the
              fan onto the native fleet -- the eval side already has 40x of headroom. Then the one
              link the fan still does not exercise: `confirm_entry` replays a hit's own plan with a
              REAL A-press on the courtyard engine and checks the predicted entry/facing/lean
              bit-for-bit. It already caught an INPUT_DELAY bookkeeping error in the plan attribution
              (the fan's j-step endpoint is not the endpoint of a j-frame plan), which is fixed for
              the entry values but means **a hit's `plan` must be re-derived through `confirm_entry`
              before it is delivered.**
      - [x] **THE s45 FORK IS SETTLED BY MEASUREMENT AND ROUTE (A) IS DEAD: STANDING EXACTLY ON THE
            TABULATED ENTRY DOES NOT CLIP THE CONSOLE'S OWN TETRA, BECAUSE HER 0.4321 u MISS ON COORD
            274 IS 0.4314 u *PERPENDICULAR* TO THE COORD THREAD. ROUTE (B) IS ALIVE AND MEASURED: WITH
            TETRA PINNED THERE ARE 1735 GENUINE *ENTRIES* (856 INSIDE THE FOLLOW BAR), AND LINK'S OWN
            ESCAPE WALK PASSES 3.06 u FROM THEM (session 79).** The handoff asked for the fork to be
            decided before searching; it is decided, and not by argument.
            - **THE DUAL OF THE COORD LIST.** `_generated/tetra_placements.tsv` sweeps TETRA at a fixed
              entry. The herd is finished and console-confirmed, so she is a MEASURED CONSTANT (the
              console reads her bit-identical on frames 76/77/78) and the free variable is the ENTRY.
              `harness/tetrapush/entry_search.py` sweeps it: the native `ShoveCtx` already takes
              `link_x0/link_z0` per sample, and the baked schedule is entry-POSITION-invariant (gated),
              so one ctx maps the whole entry plane. New `fixtures/courtyard_entry_locus_s79.json`.
            - **THE RAZOR'S SMOOTH COORDINATE, and the acceptance window MEASURED not assumed.** The
              seam PLANES are useless here (`behindA/behindB` are negative almost everywhere); the razor
              is the SEGMENT test, so the residual is the cut ray's signed offset from the seam vertex
              S -- ``resid = cross(pred - old, S - old)/|pred - old|`` with ``pred = old + roll_step +
              push + cut_lunge``. Off the 288 tabulated coords at their own entry, the 279 that still
              read genuine sit in resid **[-2.52e-6, +1.13e-4]**, width **1.16e-4 u** -- about ONE f32
              ULP at this distance from the origin, which is why the tsv is dust and not a region. The 9
              that do not read genuine sit INSIDE that band, so the window is a dust edge to aim with,
              never an acceptance test.
            - **WHAT ACTUALLY MOVES IT IS THE CUT-FRAME PUSH, NOT THE ENTRY DIRECTLY.** `old` is the
              same wall-braced point almost everywhere (the roll runs into the corner and CrrPos pins
              it), so the entry matters only through whether Tetra is still shoving Link on the frame
              the cut fires. push 0 -> resid **-0.3294** (the bare roll-stab, 0.33 u short of
              threading); the tabulated entry's push (-1.115,-0.258) -> **+0.3139**; genuine wants
              ~(-0.551,-0.127). **At Link's own console endpoint the push is exactly ZERO** -- she is out
              of Co range by the cut frame -- so no knob moves the residual THERE, and the three
              probe lines through it read a dead-constant -0.3294.
            - **THE TARGET SET.** 1735 genuine entries at the tabulated facing and m351C 0: ONE thin
              curve, 104 u long, 0.93 u thick, every one walkable. **856 lie inside the 230 u follow
              bar** and are the usable target -- past the bar Tetra leaves stt 3 and walks, so an entry
              out there is not an entry. Nearest usable entry **49.7 u** from where the escape leaves
              Link, and all of them 136-230 u from her.
            - **REACHABILITY IS NOT THE PROBLEM.** The console log continued with its own last stick
              held walks to **3.06 u** of the usable locus by frame 85, and four other steady sticks
              pass within 3.8-13.1 u by frame 82-86 -- all still at **speedF 17.0**, the walk cap the
              roll needs for its full nspeed 26. The escape atom manufactures the slot-7 posture for
              free.
            - **THE SEARCH IS A COUNTABLE LOTTERY, AND THE FIRST PASS RAN AND CAME UP EMPTY BY THE
              EXPECTED MARGIN -- IT IS ~10x TOO SMALL, NOT MIS-AIMED.** The needed entry precision is
              **window / |grad resid| = 1.16e-4 / 1.196 = 9.7e-5 u**, one ULP, so this is a DENSITY
              problem and not an accuracy one. A stride-2 stick fan x 8 hold lengths from two base
              nodes, pruned to speedF 17 and the follow bar, gives **3699** distinct
              ``(entry, m351C)`` candidates over 720 lean groups; against all 6 realizable facings that
              is 180 s of ctx builds and **0 genuine**. The diagnosis is a count, measured at the best
              facing (40884): only **4** candidates reach |resid| < 5e-3 and their local spacing is
              **1.01e-3**, so ``P(a near-zero candidate is genuine) ~ window/spacing ~ 0.11`` and 4
              tries is an expected 0.4 hits. **The earlier 0.55 estimate was optimistic**: it took the
              spacing over the 200 closest by |resid|, which are clustered, rather than the local
              spacing at one facing. Levers in order of cheapness: stride 1 (4x the fan); more base
              nodes N0; TWO-SEGMENT holds (stick S1 for j1 then S2 for j2 -- combinatorially the big
              one); and the **C-stick**, which moves csangle ~460-530 BAM/frame and so multiplies the
              facing alphabet, each facing contributing its own near-zero set.
            - **RANK THE SIGNED DISTANCE TO THE WINDOW, NOT |resid|.** The window is asymmetric
              ([-2.5e-6, +1.13e-4]) because its sign carries which side of the gap the ray passes, so
              |resid| rewards near-misses on the BLOCKED side equally. The first pass's own best
              candidate was **-5.45e-05** -- inside the window's width, on the wrong side of it.
            - **TWO PARAMETERS THE SEARCH MUST CARRY (both measured, both easy to get wrong).**
              (i) **m351C**: 0 and 1 clip the same entry, **64 already does not** (resid 1.1e-2), and the
              replayed herd hands Link m351C **-191** with a steady walk settling near -160 -- so a ctx
              is valid only for the lean it was built at, and the search groups candidates by m351C to
              share one. `link_y`, by contrast, does not matter at all.
              (ii) **the facing alphabet is only 6 wide at a frozen camera.** csangle is frozen at
              **34325** by the atom's neutral C-stick, so the realizable roll facings
              (`two_roll.reachable_stick_fan` + 0x8000 + csangle) inside the 40600-41100 seam window are
              exactly **40617, 40665, 40773, 40884, 40925, 41037** -- and **40835, the tabulated facing
              the locus fixture is computed at, is NOT one of them.** Each realizable facing has its own
              locus (~0.0075 u of shift per BAM), so the real target is a union of 6 curves. The C-stick
              is what widens that alphabet, and it is otherwise free during the walk-in.
            - **Gates** (+16, `tests/test_entry_search.py`): the harness reproduces the tsv at its own
              entry (279/288 + the 9 pinned), the window is ~1 ULP wide, route (A)'s falsification and
              the perpendicular split, the zero push at Link's endpoint, the schedule's entry-position
              invariance (what licenses the whole sweep), the m351C sensitivity, the locus's shape and
              usable subset, the entry precision, and the replay landing 0-ULP on the console endpoint.
            - **NEXT (the search proper).** Widen the fan by the levers above until the near-zero
              population is ~10x, ranking the signed distance to the window. Then the one fidelity gate
              this all rests on: a real A-press roll out of the walk must be shown **bit-identical** to
              the schedule `extract_schedule_at` bakes (it reseeds a fresh FRONT_ROLL at nspeed 26), so
              every hit is a CANDIDATE until that confirm passes.
      - [x] **THE SHIPPED PLAN IS CONFIRMED ON CONSOLE -- 22 OF 22 TRUNCATE-AND-READ SAMPLES 0-ULP ON
            BOTH ACTORS, AND TETRA'S 0.4321 u LANDING ON GENUINE COORD 274 IS NOW A CONSOLE
            MEASUREMENT RATHER THAN A SIMULATION RESULT (session 78).** The tier-2 confirm was one of
            the two genuinely open items and it did not depend on the frame question at all. It passed
            on the first delivery, with no model work: `fixtures/courtyard_plan_s73.json` spliced onto
            the recorded boot movie at F0 44974, played with `loadstate 1`, both actors read at the
            PauseMovie halt for each N (`deliver.divergence_curve`, ~25 s per sample unattended).
            - **WHAT WAS DELIVERED is the plan PLUS its escape atom.** The shipped log ends at the
              ARRIVAL because `objective.score_plan` probes the atom on a clone, so the atom's own 7
              inputs were never in the plan file; `away_walk.probe(...)['log']` re-derives them, and the
              delivered sequence is **78 frames** -- 71 herd + 7 atom, of which the SCORED end is 75
              (herd + ``freeze_f`` 4). The remainder is Link's escape, delivered so the console measures
              that too.
            - **THE CURVE: N = 1, 4, 8, 14, 21, 28, 35, 42, 49, 56, 62, 66, 69, 70, 71, 72, 73, 74, 75,
              76, 77, 78 -- every one bit-exact on Link x/z AND Tetra x/z**, and on ``proc``,
              ``facing``, ``travel`` and ``speedF`` besides. Tetra reads **stt 3 at every sample**, so
              unlike node 1's curve this plan has NO open frontier and nothing is xfailed: the regime
              prune and rule 4 are what buy that, and this is the first end-to-end evidence that they
              do. It is also an independent re-validation of the s55-s59 fidelity fixes on a
              trajectory none of them was tuned against.
            - **MILESTONE 2 IS NOW A CONSOLE NUMBER.** At the scored frame the console's own Tetra sits
              **0.4321 u from genuine coord 274** -- computed from the console read, not from the sim.
            - **THE ONE CORRECTION, and it is the camera.** The atom is scored on a camera-DETACHED
              clone commanding the arrival's LIVE csangle, on the premise that its neutral C-stick
              freezes it there. The freeze is real; the VALUE is not. The C-stick owns the yaw TARGET
              while the view-cache CHASES it at 0.66/frame, so a plan whose last roll SLEWED the stick
              hands over a globe still in flight: the shipped plan holds C-stick X at 255 through its
              last roll and csangle finishes the chase on the atom's FIRST frame, **34181 -> 34330 ->
              34325**, constant after. The console plays the WIRED value (facing 2099 at the scored
              frame; the detached clone reads 2070). **Cost, measured: zero where the objective looks**
              -- Tetra is bit-identical on every atom frame and so are ``freeze_f`` 4, ``reversed_f``
              4, ``rec17_f`` 7, ``l_ok``, the 3 dips, ``resid`` and every ``tstep``; what moves is
              Link's own escape path (0.12 -> 0.65 u), which belongs to the separate entry search. Kept
              for that reason, and because detaching keeps s65-s77's banked rows comparable -- but
              ``cs_bill`` 0 means "off the ARRIVAL's csangle", not off the delivered one. Before
              pricing a camera bill on an arrival whose last roll slewed, read the settled value off a
              WIRED clone.
            - **AND THE DELIVERED BYTES ARE THE SCORED ONES, measured not assumed.** An authored DTM
              delivers 255 as 254 and 0 as 1 (`[[octagon-clamp-decode-bug]]`), and this log carries
              substickY 0 on all 71 frames plus substickX 0/255 on 43 -- so EVERY delivered frame
              differs from the scored one. The C-stick deltas land inside the camera's own deadzone and
              the trajectory is bit-identical; a plan whose MAIN stick reached the extremes would move,
              which is why it is a gate and not a footnote.
            - **Gates** (+6, 48 cases): `tests/test_plan_console.py` on the LOCKED
              `fixtures/courtyard_plan_s73_console.json` -- the 22 samples parametrized twice (0-ULP
              positions; whole-state proc/facing/travel/speedF/stt), the console placement against
              coord 274, the delivered log's provenance (its prefix IS the plan fixture), the
              calibration no-op, and the wired-vs-detached camera contrast. KB:
              `knowledge/mechanics/land-camera.md` gains the neutral-C-stick gotcha and a console
              re-confirmation in its ``Status:``.
      - [~] **THE 74-FRAME RUNG IS CLOSED ON BOTH LIVE BANDS, AND BY ONE QUANTITY: THE ARRIVAL'S
            CONTACT DEPTH. ROUTE A HAS ITS SEPARATION FRAME BUT **0 OF 4180** VARIANTS FIRE THERE
            (``l_ok`` ON EVERY ONE, AND THE CAMERA CANNOT MOVE IT -- TRAVEL CHASES csangle, SO THE SNAP
            WINDOW SITS IN AN 87 deg HOLE OF THE REACHABLE SET); ROUTE D HAS **NO frz-2 VARIANT AT ALL**
            (MIN SEPARATION 3-4 -- EVERY ARRIVAL OF BOTH BANDS LANDS AT cf 47-51 WHERE frz 2 NEEDS
            ~55.5). AND DEPTH IS ANTI-CORRELATED WITH PLACEMENT AT 0.32-0.53 u PER u OVER 1525 REAL
            ARRIVALS, SO THE RUNG'S TWO REQUIREMENTS MOVE IN OPPOSITE DIRECTIONS (session 77).**
            Session 76 handed over "attack the escape's push DIRECTION, not the arrival's placement --
            that is where the 74th frame now is", with a two-step recipe: re-rank the atom sweep on
            recovery, then sweep ``target_cs`` and the atom JOINTLY. Both were run. Step 1's answer was
            already banked and step 2 turned into the closure, because the joint sweep found the refusal
            is not a magnitude at all.
            - **STEP 1 WAS A RANK THAT ALREADY EXISTS, and its number was mis-transcribed.** At a FIXED
              arrival ``pd_pre`` is constant, so maximising ``recovery = pd_pre - pd_post`` is the same
              ORDER as minimising the landing -- which `away_walk.probe`'s ``rank='miss'`` already is;
              what the recovery question adds is the ``freeze_f`` BUCKET, since ``total =
              arrival_frames + freeze_f`` and a rung may only spend its own row. Re-read off s76's own
              `s76_reprice` output, the CLOSEST jf-7 arrival (``pd_pre`` 34.162) recovers **28.87 u** at
              frz 3, not the 21.08 the handoff quoted (that is a different arrival's row, 34.629): the
              deficit was **4.29 u**, not 12.08.
            - **AND THE MEASUREMENT IT NEEDS IS NOW SHIPPED, because the ledger had no producer**:
              `away_walk.recovery_row` -- every variant of the grid bucketed by ``freeze_f``, both
              populations, in `objective.along_floor`'s own currency. It re-derives BOTH banked arrivals
              of `fixtures/courtyard_arrivals_s75.json` **0-ULP** (every ``firing_freeze_f`` count and
              every ``per_freeze_f`` recovery/plow), so s75/s76's rows stop being a scratch script's
              word. The "never borrow a row" rule now has something to measure with.
            - **THE JOINT SWEEP: ``target_cs`` IS EXIT-ONLY, SO IT BUYS FIRING AND NOTHING ELSE** (2 x
              252 cells, 41 camera targets x the 672-variant knob grid on the 6 closest arrivals of each
              band, ~680 s each over 10 workers). ``pd_pre`` is **bit-identical across all 41 targets**
              on all 12 arrivals -- `target_cs_is_exit_only`, re-confirmed on the live bands -- so the
              camera cannot move the placement, only whether a variant fires. And it barely does:

                  band          arrivals  cells with a FIRING variant   best firing total (pd_post)
                  jf 7 (71 f)      6              1 of 252              75 f, pd_post 7.317
                  jf 8 (72 f)      6              5 of 252              76 f, pd_post 2.959

              The shipped plan is 75 f at pd **0.432**, so nothing here beats it -- and at the RUNG the
              two routes need, the count is 0.
            - **ROUTE A: THE SEPARATION FRAME EXISTS AND NOTHING FIRES AT IT.** At ``freeze_f`` 3 the
              six jf-7 arrivals hold 202-1278 variants each (4180 in total across the camera grid) and
              **0 fire, on every arrival**. `away_walk.fires_census` -- new, because a count is not a
              diagnosis -- names the clause: ``l_ok`` fails on **all 672** variants and is the SOLE
              blocker on 239-364 of them, so nothing about the escape's own shape needed fixing. The
              recovery magnitude is short too (frz-3 max 21.7-29.1 u against a 33.16-33.77 u need), so
              even a firing variant would miss.
            - **AND THE CAMERA CANNOT FIX ``l_ok``, for a mechanical reason worth not re-paying**
              (`away_walk.snap_reach`, new, + `knowledge/mechanics/ebs-turnaround.md`, new). The snap
              fires on ``want - travel`` (the ESS stick's world want-angle against TRAVEL, not against
              facing -- `reposition.turnaround`), and the post-roll EBS travel CHASES csangle, so
              slewing the camera moves both together. Measured, +-0x4000 at step 64 → 110 distinct
              reachable ``(csangle, travel)`` states per arrival:

                                          reachable        commanded (travel frozen)
                  states that SNAP         0 / 0 / 1        10 / 9 / 9   of 110
                  want-travel covered      87 deg HOLE      continuous

              The hole is exactly where the snapping band sits. So a bill `snap_bill` prices at 29 deg
              inside a 56 deg slew span is **unpayable at any price**, and s76's "0 of 672 fire" was not
              an unmeasured column -- it was this.
            - **ROUTE D: THE FRAME ITSELF DOES NOT EXIST.** 74 frames from a 72-f arrival needs
              ``freeze_f`` 2, and across all 6 jf-8 arrivals x 41 camera targets x 672 knobs there are
              **0 variants at frz 2** -- the minimum separation is 3 or 4. ``freeze_f`` is set by the
              arrival's own `full_herd._centre_feet` (s75) and every arrival of both bands lands at
              **47.0-51.2**, where the one real frz-2 arrival sits at **55.50**. So route D fails in
              FRAMES, before placement is considered.
            - **WHICH NAMES THE AXIS NOTHING HAS SEARCHED -- AND PRICES IT AGAINST THE PUSH LAW**
              (`s77_pareto`, 1081 + 444 real arrivals, 11 s each). The bands DO reach shallow arrivals
              (cf up to 66.4), but placement degrades monotonically with depth, because a contact that
              finishes shallow was pushing weakly on its way there -- `(80 - centre_feet)/2` per frame,
              s76's own law:

                  final centre_feet   46-48  48-50  50-52  52-54  54-56  56-60   60+
                  best pd_pre, jf 7   34.63  34.16  35.46  38.07  37.54  40.27  41.64
                  best pd_pre, jf 8   24.50  24.99  25.46  25.75  26.69  28.78  29.90

              **0.32-0.53 u of placement per u of depth.** And the rung wants BOTH: a shallow arrival to
              separate in 2-3 frames, and a close one to be inside the allowance -- while a shallower
              escape ALSO recovers less (frz 2 ~15 u against frz 3's 21-29). Priced at cf 55: the
              requirement tightens ~14 u while the supply worsens 3.4 u. That is why s71-s76 each moved
              a different knob and none moved the frontier -- the two requirements are coupled by the
              push law, and both bands sit on their own Pareto frontier. KB: the split-out
              `mechanics/push-magnitude.md` carries the trade.
            - **Gates** (+4, 2 of them ``slow``): `tests/test_away_walk.py::
              test_recovery_row_is_the_ledgers_measurement_and_a_bucket_not_a_rank` (the currency, the
              recovery/pd_post identity, and that a single-best probe cannot answer a per-rung row),
              `test_recovery_row_re_derives_the_banked_ledger_rows_bit_exact` (``slow``, 0-ULP vs the
              s75 fixture), `test_fires_census_attributes_a_refusal_to_a_clause_instead_of_counting_it`
              (pins `FIRES_CLAUSES` EQUIVALENT to `fires`, so the census cannot mis-attribute) and
              `test_the_camera_cannot_deliver_the_snap_because_travel_chases_it` (the reachable-vs-
              commanded CONTRAST -- either half alone is misleading -- plus a live re-measure), with
              `test_snap_reach_re_derives_the_banked_camera_census` (``slow``) re-deriving the numbers
              above. New fixture `fixtures/courtyard_snapreach_s77.json` (3 pre-roll nodes as delivered
              input logs -- `snap_reach` needs a NODE, so a banked arrival cannot serve it).
      - [x] **THE JUNCTION BEAM IS NOT THE BINDING STAGE: 9.8x THE ENDPOINTS BUYS 0.00 u OF ARRIVAL
            REACH. AND THE LEDGER THAT CALLED THE ROUTES SHORT IS NOT BAND-PORTABLE -- MEASURED ON THE
            jf-7 BAND'S OWN ARRIVALS ITS ALLOWANCE IS 34.76-37.05, NOT 23.94, WHICH ADMITS THE BAND.
            WHAT ACTUALLY REFUSES 74 FRAMES IS THE ESCAPE'S PUSH **DIRECTION** (21.08 u of a 33.76 u
            PLOW POINTS AT THE THREAD) AND THE CAMERA BILL (0 of 672 VARIANTS FIRE) (session 76).**
            Session 77 ran both steps of this box's handoff and CLOSED the rung: the direction is not
            the binding term either -- ``l_ok`` refuses every frz-3 variant, the camera cannot fix it,
            and route D has no frz-2 frame at all. See the box above.
            Session 75 handed over "widen the JUNCTION beam, not the node -- it is the stage this
            session measured to be the binding one, and it has never been widened", with one number to
            decide it: does node 0's jf-7 floor drop below 23.94 at ``beam`` 64/128? It was run at full
            aim resolution over the whole pool, at BOTH live rungs, and the answer is no -- but the
            reason the rung is short turns out not to be the one the ledger said.
            - **THE WIDENING, MEASURED AT BOTH RUNGS** (`junction_beam` at ``beam`` 24 / 64 / 128,
              node 0; endpoints dumped as delivered input logs so a shard rebuilds one in ~15 ms
              instead of re-running a 128-wide beam per worker, the ~130 s x 10 s75 paid):

                  band        pool 24 -> 128   new probed   rolls   pd floor        along ceiling
                  jf 7 (71 f)    420 -> 4110      3690      1081   34.977 -> 34.162  908.68 -> 908.68
                  jf 8 (72 f)    632 -> 2204      2204       444   23.495 -> 23.495  920.22 -> 920.70

              4400 s + 1300 s over 10 workers. So **9.8x the endpoints moves the jf-7 pd floor 0.82 u
              and its arrival REACH 0.00 u**, and at jf 8 the widened pool's own best (24.499) does not
              even reach the narrow beam's floor. Route A needs 23.94, route D 16.08. The endpoint
              stage is saturated; this is not where the frames are.
            - **AND ``beam`` IS NOT MONOTONE IN WIDTH, which is worth knowing before the next widening**
              -- `_mixed_beam`'s ``per_group`` cap is shared ACROSS its orders, so giving order 1 more
              slots can starve order 2 of a group budget it used to get. Measured: at jf 7 the beam-128
              pool CONTAINS all 420 of beam 24's, at jf 8 the two are **DISJOINT** (632 and 2204, 0
              shared physics tags). So a wider beam is a different sample, not a superset, and the
              honest floor is the UNION across widths (which is what the table above reports).
            - **THE LATERAL-INDEPENDENT LEDGER, now encoded as `objective.along_floor`.** ``pd_pre`` is
              JOINT, so a short floor cannot say whether a band ran out of DISTANCE or only of aim. The
              coords start at along **937.53** and along/lateral is orthonormal, so
              ``pd_pre >= 937.53 - along`` whatever the lateral -- a band's along CEILING (a max over
              the same rolls the sweep already fires) tests the rung on its own. Ceilings 896.60 /
              908.68 / 920.70 / 932.66 at 70 / 71 / 72 / 73-frame arrivals, i.e. best-possible pd
              40.94 / 28.85 / 16.83 / 4.88 with a PERFECT lateral -- so each band's floor is carrying
              6-12 u of pure lateral error, and s71-s75 each paid ~2700 s of aim sweep to learn a
              verdict this inequality gives off a number the sweep already prints.
            - **THE CEILINGS ARE A HERD RATE, WHICH IS WHY THE BEAM CANNOT MOVE THEM.** Divide the node
              and the beam out: measured from Tetra's state-2 along, every band sits at **98.24-98.53%
              of `PUSH_CEILING`** (12.771-12.809 u/f of 13.0) -- the recorded human's own 98.2%. 74
              total frames needs **98.55%** (``freeze_f`` 2, 72 herd frames, 12.812 u/f); 75 frames
              needs 97.20-97.99%, which every band CLEARS, which is why the shipped plan exists. So the
              whole 74-frame question is **0.24 percentage points**, 2.23 u of along (1.23 after the
              `PLACEMENT_BAND` credit). **Not a physical bound**: `PUSH_CEILING` is asymptotic and a
              23-frame cycle has sustained 13.36 u/f = 102.8% (knowledge/mechanics/actor-push.md), so
              this is a SEARCH deficit.
            - **AND THE DEFICIT HAS AN ADDRESS: THE JUNCTION'S 8 FRAMES.** `objective.push_budget` on
              the real best 72-frame arrival (endpoint 471, aim (171,192), pd 23.495) splits it with
              nothing to fit -- state-2 prefix 45 f at **99.56%** magnitude, junction 8 f at
              **93.51%**, roll 19 f at **99.55%**, total sideways only **10.27 u** over 72 frames
              (prefix 3.22, junction 2.27, roll 4.78). The junction loses **6.75 u of push**; route D is
              short **6.17 u of along**. Per frame the push is EXACTLY
              ``(CO_RADII_BAR - _centre_feet) / 2`` -- verified on every frame of that arrival, rolls
              included (cf 45.9 -> 17.036 u, cf 59.6 -> 10.188 u), the s46 freeze law running the whole
              window -- so the sustained rate is set by the MEAN contact depth, and the junction's mean
              ``_centre_feet`` is **55.4** against the roll's 54.1.
            - **THE CORRECTION, and it re-opens route A's arithmetic: s75's ledger allowances are
              PER-ARRIVAL and were borrowed across bands.** The allowance is ``plow(freeze_f) +
              PLACEMENT_BAND``, and the plow bound is a property of the arrival for the same reason
              ``freeze_f`` is (s75): at ``freeze_f`` 3 it reads **20.31 u** on node 5's arrival, **33.76
              -36.05 u** across the widened jf-7 band's own closest arrivals, and **48.57 u** on node 0
              jf 10's. Screening jf 7 with the borrowed 22.94 REFUSES it (needs along 913.59, ceiling
              908.68); screening it with its own 33.76 ADMITS it (needs 902.5). Session 75 lost the
              72-frame rung to exactly this mistake one level down.
            - **SO WHAT REFUSES 74 FRAMES NOW IS THE ESCAPE'S DIRECTION AND ITS CAMERA BILL, NOT THE
              ARRIVAL'S PLACEMENT.** On the widened jf-7 band's closest arrival (``pd_pre`` 34.162, cf
              48.13) the escape's 3 frames plow **33.76 u** -- enough for a 34.76 allowance against a
              34.162 floor -- but only **21.08 u** of it is directed at the thread (short 12.08 of the
              33.16 the rung needs), and **0 of 672 variants FIRE** at the arrival's own csangle. The
              bill is not separable from the arrival (`away_walk.snap_bill`: the post-roll EBS travel
              chases csangle, so paying it MOVES the arrival, s42), so it is a term in the roll's
              ``target_cs`` -- unmeasured on this band, and the reason these arrivals have no frame
              answer yet rather than a bad one.
            - **Gates** (+2): `tests/test_objective.py::test_the_along_floor_bounds_the_placement_
              distance_whatever_the_lateral` (the inequality, on the two banked real arrivals plus the
              coord set, and tight straight up-herd of the near end) and
              `test_the_along_floor_s_ALLOWANCE_is_per_arrival_and_must_not_be_borrowed` (the banked
              pair's plow spread at a shared ``freeze_f``, and the screen's verdict flipping on it).
      - [x] **THE OTHER SEVEN CYCLE-2 NODES ARE MEASURED AND NONE OF THEM ARRIVES: NODE 0/1 IS THE ONLY
            USABLE EXIT IN THE BEAM. THE LEDGER ROW THAT RETIRED THE 72-FRAME RUNG WAS A ONE-NODE
            ARTIFACT, AND WITH THE FOURTH ROUTE RESTORED AND PROBED THE 74-FRAME LEDGER IS COMPLETE:
            EVERY ROUTE IS SHORT, THE BEST BY 7.41 u (session 75).
            Session 76 ran its handoff's step 1 at both live rungs and the widening buys 0.00 u of
            arrival reach -- and it found this ledger's allowances are not band-portable, which re-opens
            route A's arithmetic. See the box above.**
            Session 74 handed over "fix the ARRIVAL's lateral one cycle upstream": node 0, which
            s71-s74 all built on, has the WORST Tetra exit lateral of the eight (-25.608 against node
            2's -3.654), and the other nodes' extra 3-4 frames were read as BUYING that lateral. Run
            across the whole beam at full resolution, they do not -- and the reason inverts the
            diagnosis rather than refining it.
            - **THE CENSUS FIRST, BECAUSE THE ARITHMETIC DECIDES WHICH BANDS EXIST** (122 s, 8 nodes in
              parallel). An arrival costs ``node frames + jf + the roll's own 19``, so a longer prefix
              only pays if its junction ARMS sooner. The `junction_beam` pool by ``jf``: node 0/1
              **45 f** jf 5-12 · node 2 **49 f** EMPTY · node 3 **48 f** jf 4-8 · node 4 **48 f** EMPTY
              · node 5 **48 f** jf 4-5 · node 6 **47 f** jf 5-12 · node 7 **47 f** jf 4-12.
            - **TWO OF THE FOUR BETTER-LATERAL NODES CANNOT JUNCTION AT ALL, for two different reasons,
              and neither is the beam keep** ("the pool is empty" is not a diagnosis, and a keep that
              hides survivors is this work's most-repeated failure mode). **Node 2** -- the best lateral
              in the beam -- dies in 5 s, every branch of its frontier leaving the pursuit box
              (``outbox`` 4384), and **widened to ``beam`` 64 it is still EMPTY** with the same counter
              growing (17536): it is the box, not the cut. **Node 4** runs all 12 generations with all
              64384 candidates ``unarmed`` -- at cone deficit 15838, dead behind her (his lateral -4.72
              against her -4.89), 12 frames of ESS never clear the +-90 deg cone, so the proc-7 flip
              never fires. At ``beam`` 64 node 4 does yield 70 endpoints, **all at jf 11** (a 78-frame
              arrival), so the width is real and buys nothing at the rung.
            - **AND WHERE THEY DO JUNCTION, A SHORT JUNCTION DOES NOT SURVIVE A ROLL.** Full aim
              resolution over the WHOLE pool (s74's lesson: a decimated ``step`` reads a live band as
              DEAD), 3144 endpoints x ~325 aims, 3117 s over 10 workers:

                  band          arrival   endpoints  rolls   along          lateral        min pd  needs
                  node 7 jf 4     70 f       208       0        -              -              -    35.54
                  node 3 jf 4     71 f       832       0        -              -              -    23.94
                  node 5 jf 4     71 f       848       7      894.9         -56.17         76.98   23.94
                  node 6 jf 5     71 f       416       0        -              -              -    23.94
                  node 7 jf 5     71 f       840      16   897.3..904.3  -57.32..-36.47    59.95   23.94

              against node 0's own floors of **52.97** (70 f) and **34.98** (71 f). ``followed`` is
              95%+ of every death -- the roll leaves her behind. **So routes A and B are closed on
              every node in the beam that can reach them, and node 0 is still the best of them.**
            - **THE INVERSION, stated as what was measured: node 0/1 is the ONLY node in the beam whose
              junction produces a usable arrival at any rung inside the frame budget.** Its bands roll
              healthily at every ``jf`` probed (131 / 69 / 154 / 83 / 232 surviving rolls at jf
              6/7/8/9/10, s71-s75); every other node yields 0-16 rolls at the 70-72-frame rungs, and
              the ones that do survive land Tetra at lateral -36..-57. So the arrival is a property of
              WHICH cycle-2 exit the junction runs from, and the exit with the best Tetra lateral is not
              the one that can use it -- s74's "nodes 2-5 hand over 20 u better lateral and their extra
              3-4 frames BUY it" is falsified in both halves: they do not hand it over usably, and the
              frames are spent before the junction starts.
            - **AND THE OBVIOUS MECHANISM IS NOT THE MECHANISM -- a measured negative, so it is not
              re-derived.** The exit POSTURE scalars do not separate the productive node from the rest:
              `_cone_deficit` is **14672-15994 BAM (80.6-87.9 deg)** across ALL EIGHT nodes -- node 0
              sits at 15896, mid-range -- and the Link-minus-Tetra lateral gap runs -2.97..+5.62 with
              node 0 at +5.62 but the dead nodes 6/7 at +4.32/+4.44. So "the good laterals come with
              Link parked behind her in the talk cone" is a plausible story that the numbers refuse.
              What makes node 0's exit rollable is still unidentified, and it is the question the next
              widening answers rather than assumes.
            - **THE LEDGER'S ``freeze_f`` 2 ROW WAS A ONE-NODE ARTIFACT, AND CORRECTING IT OPENS A
              FOURTH ROUTE.** s74 read "there is no ``freeze_f`` 2 anywhere in the population" off node
              0's 85192 variants and retired the 72-frame rung with it. On node 5's arrival freeze_f 2
              is the **MODAL** separation -- **384 firing variants of 672** -- and its escape reaches
              **74 total frames** with `fires` True (pd 57.3: the arrival fails, not the escape). The
              mechanism is DEPTH, which is why the row cannot be a constant: ``freeze_f`` is the first
              frame clearing `CO_RADII_BAR`, so an arrival ending SHALLOW (`_centre_feet` **55.50**)
              leaves in 2 where a DEEP one (**49.32**) never leaves before 4. **Route D = 72-f arrival +
              ``freeze_f`` 2**, priced the same way as the others: recovery **14.86 u** against a plow
              bound of **15.08**, i.e. ``pd_pre <= 15.86`` measured / **16.08** bound -- the tightest of
              the four, because the escape's frame 2 is the dead one. Gated
              (`test_which_freeze_f_can_fire_is_a_property_of_the_arrival_not_of_the_recipe`) on two
              banked real arrivals, since one bed can only ever show one side of it.
            - **AND ROUTE D'S OWN RUNG WAS PROBED, ALL FOUR 72-FRAME BANDS** (2434 endpoints, 2693 s):

                  band          endpoints  rolls   along          lateral        min pd  best landing
                  node 0 jf 8      632      154  899.8..920.2  -52.06..+26.60    23.49       0.47
                  node 3 jf 5      832        0       -              -             -          -
                  node 6 jf 6      630        0       -              -             -          -
                  node 7 jf 6      524       45  911.3..916.9  -52.26..-35.81    51.01      33.76

              **min pd_pre 23.49** against route D's 16.08 -- short by **7.41 u**, the CLOSEST any route
              has come (A 11.04, B 17.43, C 13.67), and again it is node 0 that gets there. Its closest
              arrivals sit at lateral **+0.40 / +1.13 / +2.50** -- laterally ON the thread, the miss
              purely along -- and the band's best PREDICTED landing is **0.47 u**.
            - **SO THE 74-FRAME LEDGER IS COMPLETE FOR THE FIRST TIME, AND EVERY ROUTE IS SHORT:**
              70 f **52.97** vs 35.54 (short 17.43) · 71 f **34.98** vs 23.94 (**11.04**) · 72 f
              **23.49** vs 16.08 (**7.41**) · 73 f **14.43** vs 0.76 (13.67). The deficit falls with the
              rung until route C's cliff, where a 1-frame escape recovers nothing.
            - **AND ROUTE D HAS A SECOND CONDITION THAT PULLS AGAINST THE FIRST.** A firing ``freeze_f``
              2 needs a SHALLOW arrival, and shallow arrivals are the ones that have not pushed her:
              over the 11 arrivals measured this session `_centre_feet` and ``pd_pre`` correlate
              **+0.723**, slope **+3.14 u of miss per u of depth**, and exactly **1 of 11** has a firing
              freeze_f 2 -- the one at ``pd_pre`` **76.98**. Node 0 jf 8's own arrivals sit at
              `_centre_feet` 47.0-49.5 and separate at 3/5/6, never 2. So route D would have to move
              ~7.4 u of placement AND ~6 u of depth in OPPOSITE directions along that slope, which is
              the same shape as the dead push frame: not a knob, the recipe's geometry. (n=11 across
              mixed bands, so a measured trend and not a law -- but the mechanism is plain, since
              shallow IS less overlap and less overlap IS less push.)
            - **s74's OPEN ITEM IS SETTLED AND THE GUARD IS GONE.** `away_walk.probe`'s ``can_snap``
              WAS over-strict -- a sufficient condition used as a necessary one -- and over the 10
              closest s74 arrivals it turned a FIRING escape (pd **7.739**, ``cs_bill`` 0) into a
              non-firing one (pd 8.147) on **7** of them. See the `away_walk.py` docstrings; gated as
              INDEPENDENCE from `snaps_at`. Suite green at **727**.
      - [x] **THE FINER CAMERA GRID IS MEASURED AND CLOSED -- 2.4x THE SNAPPING POPULATION BUYS
            0.000 u -- BECAUSE THE 2-FRAME TIMELOSS IS THE ESCAPE'S OWN DEAD PUSH FRAME. 74 FRAMES IS
            AN ARRIVAL QUESTION AND HAS EXACTLY THREE ROUTES, EACH PRICED (session 74).
            Session 75 ran its handoff's step 1 across the whole cycle-2 beam and FALSIFIED it -- the
            better-lateral nodes cannot junction in the frames they have left -- and corrected its
            ``freeze_f`` 2 row, which adds a fourth route. See the box above.**
            Session 73 handed over "widen the snapping population, not the grid", with the finer
            `ESCAPE_TCS_STEP` as step 1. It was run, and it is a clean negative: **512 is the right
            step, not a compromise.** Then the frames were priced instead of searched for, and that is
            the session's result -- the frontier has not moved since s71 because the timeloss is
            STRUCTURAL to the escape recipe, and every axis widened since (s72's atom knobs, s73's snap
            window, s74's finer grid) is an axis that cannot reach it.
            - **THE FINER STEP: 2.4x THE POPULATION, 0.000 u OF FRONTIER.** The tcs sweep re-run at 128
              BAM (161 targets x the same 112 real arrivals; 128 strictly contains the 512 and 256
              grids, so one run prices all three): snapping arrivals **63 -> 70 -> 83 of 112** and
              snapping (arrival, tcs) pairs **84 -> 117 -> 199** at step 512 / 256 / 128, with **20**
              arrivals whose window is NARROWER than 512 BAM (all at -13.4..-21.1 deg -- the shipped
              grid stepped straight over them). The faithful atom sweep over all 199 pairs is **85192**
              firing variants against s73's 33927, and the frontier reads: 75 f **0.432 -> 0.432**,
              76 f 1.523 -> 1.523, 79 f 0.080 -> 0.080, 81 f 0.006 -> 0.006, best-by-bound
              **75.12 bit-identical** (jf 7 end 285, ``freeze_f`` 4, `aim.handoff_spec` True, now at tcs
              -32.3 deg instead of -30.9). Only 74 f moves at all -- 24.680 -> **23.919** -- against a
              `objective.PLACEMENT_BAND` of 1.0. End to end, `objective.replay_and_score` on the new
              winner reads **75 f, pd 0.4321, coord 274, cs_bill 0, `objective.verdict` True**: the SAME
              plan as `fixtures/courtyard_plan_s73.json`, at a neighbouring camera offset. The step stays
              512 and the constant now carries the measurement.
            - **AND THE REASON IS SEPARABILITY, WHICH WAS ALREADY GATED.** `target_cs` is EXIT-ONLY for
              Tetra (`target_cs_is_exit_only`), so over 161 targets x 112 arrivals the arrival's
              along/lateral spread is **0.00 u**. A finer grid buys more camera states for the SAME
              arrivals; it cannot buy a better arrival. The general form: **more camera is not more
              placement**, and any future camera axis has the same ceiling.
            - **WHERE THE TWO FRAMES ACTUALLY GO -- the escape's own frames, and one of them is DEAD**
              (`away_walk.push_profile`, new). Priced against `objective.PUSH_CEILING`, the sustained
              plow rate the frame floor is built from, on the shipped 75-frame plan: the LAST ROLL pushes
              Tetra **12.911 u/frame over all 19 of its frames -- 99.3% of the ceiling**, so the herd
              loses nothing; the ESCAPE's 4 frames to separation push **9.177 u/frame, 70.6%**, costing
              **1.18 frames** on their own. Its plow profile is **16.506 / 0.000 / 12.469 / 7.732** --
              frame 1 is the biggest single push in the whole plan, frame 2 (the **proc-7 negation
              frame**, where the flip has Link receding and the conversion has not yet fired) plows
              **0.000 u**, and frame 4 (the slam) plows 7.7 on a HALVED mNormalSpeed. That is the
              recipe's shape (`away_walk`'s module docstring), not a knob: no camera target, aim, flip or
              rotate can buy a dead plow frame back.
            - **SO THE ESCAPE'S REACH IS CAPPED, AND THE FRAME RUNG IS FIXED BY THE ARRIVAL.** What the
              atom RECOVERS of the placement is bounded by what it pushes (gated: moving her by ``total``
              closes at most ``total`` of her distance to a fixed coord). Measured as the max over 85192
              firing variants: **-0.24 u at ``freeze_f`` 1, 22.94 at 3, 34.54 at 4**, 41.96 at 5, 51.50
              at 6, 57.20 at 7, 59.32 at 9 (there is no ``freeze_f`` 2 anywhere in the population). With
              the pool's two arrival bands -- **70 f** (142 pairs, pd_pre floor **52.97**, jf 6 end 391)
              and **71 f** (57 pairs, floor **34.98**, jf 7 end 285) -- the ledger is arithmetic:
              ``total = arrival + freeze_f`` needs ``pd_pre <= recovery(freeze_f) + PLACEMENT_BAND``.
              75 f = 71-f arrival + 4 needs pd_pre <= 35.54 against a floor of 34.98: **REACHED, with
              0.56 u of margin** -- which is exactly why the shipped plan lands at 0.432 and why no
              amount of camera moved it.
            - **74 FRAMES HAS THREE ROUTES AND ALL THREE ARE ARRIVAL QUALITY.** Each deficit is quoted
              twice on purpose: against the MEASURED best recovery (how far the search actually is) and
              against the PLOW (what the escape physically cannot exceed, since closing distance to a
              fixed coord costs at least that much displacement -- the gated bound). The plow ceiling is
              per-state, not universal; on the frontier plan its cumulative reads **16.506 / 16.506 /
              28.975 / 36.707** at frames 1-4.
              * **A. 71-f arrival + ``freeze_f`` 3** -- pool floor **34.98**. Needs pd_pre <= 23.94
                measured (**short 11.04 u**), <= ~29.98 at a perfectly aimed escape (**short ~5.0 u**).
              * **B. 70-f arrival + ``freeze_f`` 4** -- pool floor **52.97**. Needs <= 35.54 measured
                (**short 17.43 u**), <= ~37.71 perfectly aimed (**short ~15.3 u**).
              * **C. 73-f arrival + ``freeze_f`` 1** -- needs pd_pre <= **0.76** either way (frame 1
                closes nothing: the ARRIVAL places her and the escape only separates). **Never probed**
                (see below).
              So 74 f is out of reach from THIS pool on every route even at a perfect escape aim, and
              73 f (short 29.03 measured) and 72 f (34.22) are not close. 74 is the only rung in play,
              and the whole of it is arrival quality.
            - **A AND B ARE ONE NUMBER: THE LATERAL, AND IT TRACES TO THE NODE EVERY SESSION SINCE s71
              HAS USED.** The jf-6 band (70-f arrivals, full resolution, s71's whole dump) sits at along
              **885.0..896.6** -- the `aim.handoff_corridor` target is 893.9, i.e. the along is RIGHT --
              and at lateral **-59.68..-11.89**, so the entire band is >= **14.4 u** below the spec's
              +2.48. jf 7 reaches the lateral (-55.66..**+30.27**) but its 7th junction frame is the
              frame the rung needs. And the cycle-2 beam has **8 distinct nodes over 4 distinct Tetra
              states** -- node 0/1 **45 f, lat -25.608**; node 2 **49 f, -3.654**; nodes 3/4/5 **48 f,
              -4.893**; nodes 6/7 **47 f, -17.097** -- so node 0, the one s71-s74 all built on, has the
              **WORST lateral of the eight**, and its junction spends its frames undoing that. Nodes 2-5
              hand over 20 u better at 3-4 more frames (all four sit on the same ~12.5 u/frame
              closing line, so the frames are not wasted -- they buy the lateral).
            - **ROUTE C WAS UNREACHABLE BY CONSTRUCTION, BECAUSE THE SEARCH HAS BEEN AIMED AT THE OTHER
              TARGET.** Every keep since s70 ranks arrivals against `aim.handoff_target` (along
              **893.9**), which is the coord MINUS a 4-frame escape's ~44 u residual. For a 1-frame
              escape the target is the COORD ITSELF -- the genuine coords run along **937.53..984.07,
              lateral -2.27..+7.94** -- so ``roll_probe``'s ``arrive``/``over`` and `handoff_rows` have
              been penalising exactly the arrivals route C needs. The machinery already expresses it:
              `aim.handoff_target(thread, (0.0, 0.0))` IS the coord thread's near end.
            - **THE REACH LADDER, MEASURED: THE ALONG IS AVAILABLE AND THE LATERAL IS NOT.** Node 0's
              junction pools are far bigger than the two bands ever probed (jf 5:210, 6:416, 7:420,
              8:632, 9:420, 10:**1156**, 11:420, 12:948), and a capped step-4 survey walks the along up
              at **~+15 u per junction frame** -- jf 5 873.9..883.6, jf 6 886.0..895.1, jf 7 898.0..907.2,
              jf 8 920.0, jf 10 **936.6**, jf 11 **950.9..952.5** -- so the coord box is entered from
              **jf 10-11**. But every sampled lateral is **-16.5..-61.9**, none inside the box, and the
              closest arrival anywhere in the survey is **23.73 u** (jf 11, along 952.5, lat -21.39) with
              Link's own lateral **-38.2**, i.e. 17 u further out than hers -- the plow's
              anti-correlation, ejecting her further negative. That sample is thin by design (a few
              percent of endpoints, and survival is one alphabet member wide), so the LATERAL ENVELOPES
              are not envelopes; the along ladder and the sign of the lateral are what it establishes.
            - **AND THE STEP-4 SCREEN CALLS jf 9 DEAD WHEN IT IS NOT -- s71's LESSON, RECURRING.** The
              capped survey found **0 surviving rolls of 120 endpoints probed** in the jf-9 band (the
              73-f arrivals route C needs). At FULL aim resolution the same band yields **83 surviving
              rolls over its whole 420-endpoint pool** (325 aims per endpoint; the per-shard yields are
              15 / 33 / 15 / 11 / 0 / 8 / 1 / 0, so they are clustered, not uniform). So a decimated
              ``step`` does not merely lose the tail here, it reads the band as empty -- exactly what
              s71/s72 measured ("survival is ONE alphabet member wide; a ``[::step]`` decimation is a
              strict subset"), and the reason route C cannot be settled from a screen.
            - **ROUTE C IS CLOSED, AND CLOSING IT PROVED `aim.handoff_target` RIGHT.** The
              full-resolution whole-pool probe (325 aims per endpoint over the 420 + 1156 pools, 996 s):
              **jf 9** (73-f arrivals -- route C's own band) yields **83 rolls** reaching along
              **912.6..932.7**, lateral -47.6..+23.5, **min pd 14.43**, and **0 in the coord box** -- the
              along tops out **4.1 u short** of the 936.8 route C needs and the placement is short by
              **13.67 u**, so route C is unreachable at the band that would pay for it. **jf 10** (74-f
              arrivals) DOES enter the box -- **232 rolls, 16 of them inside it, min pd 2.59 u**, the
              first arrivals this work has ever measured ON a coord -- but at 74 arrival frames even a
              1-frame escape only ties the shipped 75.
            - **AND AT AN ON-COORD ARRIVAL THE ESCAPE IS DAMAGE, NOT RECOVERY** -- which is the positive
              confirmation of the ~44 u handoff offset. Firing the real atom on the 10 closest arrivals:
              pd_pre **2.59 -> pd_post 20.07**, 4.22 -> 22.87, 5.30 -> 17.55, and the best of them ends
              **7.74-8.15 u** out. The escape's ~35 u of push has to go somewhere, so an arrival already
              on the thread gets shoved off it. Aiming the herd AT the coord is the wrong target, exactly
              as `aim.handoff_target` says.
            - **THE THREE CLOSEST IN-BOX ARRIVALS HAVE NO VALID ESCAPE AT ALL**: at pd 2.59 / 4.22 / 5.30
              **all 176** swept atom variants read ``l_ok`` False -- Tetra is inside the front cone and
              the L targets her. **OPEN, and deliberately not claimed:** at the pd-5.59 arrival **135**
              variants DO satisfy `away_walk.fires` at ``cs_bill`` **0** (replay-faithful), but every one
              is ``turnaround_first=True``, which `away_walk.probe` REFUSES because that arrival's live
              csangle has no snap window (bill 40.6 deg) -- so `probe` returns ``fires`` False. Whether
              that ``can_snap`` guard is over-strict is unsettled: the ESS frame there turns only
              **0x1425 (28.3 deg)**, below the 0x4000 snap threshold, and Tetra is STILL in the cone
              immediately after it, so the ``l_ok`` is earned a frame later at the frame the L actually
              acts -- not by the snap. It buys nothing here (best 7.74 u at 78 f against the shipped
              0.432 at 75), but it is the same SHAPE of error s73 found in the snap scan order: a
              sufficient condition used as a necessary one. Worth one measurement before it is trusted.
            - **GATED, not narrated**: `away_walk.push_profile` + a per-frame ``tstep`` on
              `escape_atom`'s rows (Tetra's own displacement that frame -- NOT a ``tres`` difference,
              which under-reads a turning plow), and `tests/test_away_walk.py::
              test_the_escapes_own_frames_are_worth_less_than_a_ceiling_frame_and_one_is_dead` pins the
              dead frame AS the proc-7 negation frame, the sub-ceiling rate, and the recovery bound that
              makes the ledger admissible. The `ESCAPE_TCS_STEP` constant carries the 0.000 u
              measurement so the sweep is not re-run. Suite green at 724.
      - [x] **THE CAMERA ANGLE NOTHING PAID FOR WAS A SCAN ORDER, AND ONCE THE LAST ROLL PAYS THE REAL
            BILL THE PLAN PASSES: `objective.verdict` TRUE -- 75 FRAMES, pd 0.432 u, EVERY RULE MET,
            REPLAY-FAITHFUL (session 73).
            Session 74 measured its handoff's step 1 and closed it: a 2.4x finer snapping population
            moves the frontier 0.000 u, because the camera cannot move the ARRIVAL. See the box above.**
            Session 72 handed over "pay for the escape's csangle inside the plan", with the bill priced
            at 105-111 deg and one roll's slew worth ~47. **The bill was never 105 deg.**
            `away_walk.snap_csangle` scanned ``range(0, 0x10000)`` and returned the FIRST member of a
            window that is **78.8-81.6 deg wide** (28-30 members on the 512 grid, measured over 112 real
            arrivals) -- i.e. its FAR edge, 91.3-113.8 deg off live on every arrival. The NEAREST member
            is **15.3-37.8 deg** (median 21.0), and one roll's C-stick slews **-46.6..+40.7 deg**, so the
            bill fits inside the last roll's own idle camera channel. Charging it there closes the s65-s72
            caveat and the frontier gets BETTER, not worse.
            - **THE FIX IS TWO DEFAULTS AND A GRID.** `snap_csangle(near=True)` returns the window
              member nearest the live csangle; `escape_atom`'s ``csangle`` now defaults to the arrival's
              own LIVE value (its C-stick is neutral, so the camera holds it -- the replay-faithful
              convention), with ``'snap'`` kept as an explicit research mode and every result carrying
              ``cs_bill`` so a billed variant can never pass as faithful; and the LAST cycle's camera grid
              widens from `TCS_SPAN` (+-8.4 deg, derived for the mid-chain junction's razor travel band)
              to `ESCAPE_TCS_SPAN` (the roll's measured slew reach), with `camera_probe_key` as a keep
              share on what the arrival still owes (`extend_cycle(tcs_escape=)`, `chain_herd(last_camera=)`,
              default ON for the last cycle).
            - **63 OF 112 ARRIVALS THEN OWE NOTHING** -- their own roll's C-stick reaches a camera state
              whose arrival snaps at its own live csangle (84 (arrival, target_cs) pairs; **0 of 112** do
              at the shipped neutral camera).
            - **AND THE FAITHFUL FRONTIER BEATS THE COMMANDED ONE.** Swept over those 84 pairs at the same
              resolution s72 used (flip 0x400 over +-0x2800 x 4 rotates x side x exit x turnaround, 33927
              firing variants): **75 f -> pd 0.432 u** (miss 0.699, `aim.handoff_spec` True) against s72's
              1.644 at the same 75; 74 -> 24.68, 73 -> 32.31, 79 -> 0.080.
            - **THE ACCEPTANCE TEST PASSES, WHICH IS THE NUMBER TO QUOTE.**
              `objective.replay_and_score` from the raw input log on a fresh `FreeRun`: **frames 75
              (floor 73, timeloss +2, inside `TIMELOSS_BUDGET`), placement 0.4321 u on genuine coord idx
              274, ``complete`` True, ``terminal_ok`` True, ``wall_ok`` True (margin 56.37), ``regime_ok``
              True, ``within_budget`` True -> `objective.verdict` TRUE**, with the atom's ``cs_bill``
              **+0 BAM**. That is milestone 2 met offline: every one of Dereck's four rules, on a plan
              whose every input is in the log, with no camera assumption unpaid. The DTM confirm is the
              out-of-band tier-2 step (`[[tetrapush-dtm-delivery]]`).
            - **AND IT IS A REGRESSION, NOT A SESSION CLAIM.** The log is tracked at
              `fixtures/courtyard_plan_s73.json` with its provenance and the ``atom_kw`` it must be scored
              with, and `tests/test_objective.py::
              test_the_shipped_plan_passes_the_whole_objective_from_its_input_log_alone` replays it on a
              fresh `FreeRun` every run (~21 s) and asserts the whole verdict plus ``cs_bill == 0``.
            - **THE SNAP IS SUFFICIENT, NOT NECESSARY -- SO THE CAMERA TERM IS A KEEP, NEVER A FILTER.**
              Swept over 16 arrivals x 41 camera targets (656 cells): **274 fire** at the live csangle and
              only **12 snap**; all 12 fire, but **262 firing cells do not snap**, because a camera steer
              also moves the arrival's own EBS facing and can take Tetra out of the front cone by itself
              (the 75-frame winner fires at ``turnaround_first=False``). As a keep of 3 the bill is still
              the best cheap term measured -- it retains a BEST-bound firing cell for **13 of 14**
              arrivals at median **0.00** frames of loss, where the front-cone margin retains one for 7
              (widest-first) or 3 (narrowest-first). The cone cannot screen it: the frontier cell's own
              margin is **5.2 deg**, below the DEAD cells' median of 11.1.
            - **AND THE REST OF THE GRID IS NOT WHERE THE LANDINGS ARE -- THE SNAP TEST IS.** The widened
              grid spans **4592** cells and the 84 snapping pairs are 1.8% of it, so the obvious next move
              was to sweep the rest. Measured first, on a uniform **224-cell (4.9%)** stratified sample at
              the same full flip resolution: **67 fire (30%)** and the frame-capped frontier is **75 f ->
              pd 18.50 u**, 74 -> 23.16, 73 -> 37.24, best bound **75.56**, with `aim.handoff_spec` True
              exactly **once** -- against the snapping pairs' **0.432 u at 75** with spec True. The two
              samples agree on it: the dense 16-arrival census's own best cell by bound is its SNAPPING
              one (75.12), and its 262 non-snapping firing cells never beat it. So FIRING is common
              (30-42% of cells) and LANDING is not, and the snap test -- which looks like a 4.4%-recall
              filter on firing -- is the thing that selects landers. The mechanism is unexplained; the
              measurement is what the next search should ride. The productive widening is therefore of the
              SNAPPING population, not of the grid: a finer ``ESCAPE_TCS_STEP`` (the snapping targets are
              1-2 members wide AT 512, so 256/128 should multiply the set), the arrivals of the other
              junction-frame bands, and the other cycle-2 beam nodes.
            - **A SYNTHETIC TERMINAL CANNOT GATE THE FAITHFUL PATH** (the trap this created): a bed minted
              by relocation (`synthetic_hot_arrival`) has no roll to have paid its bill, so its inherited
              csangle sits ~25 deg outside the window and **0 of 2048** swept variants fire there. Beds that
              run the atom take ``snap_camera=True`` (it fabricates the camera the last roll delivers, so
              the atom runs at bill 0); `aim.handoff_corridor` probes its residual with ``csangle='snap'``
              for the same reason.
      - [x] **THE PLACEMENT WAS NEVER IN THE HERD'S HANDS AT ALL: THE ESCAPE ATOM'S TWO UNSWEPT
            KNOBS MOVE TETRA FURTHER THAN A WHOLE CYCLE'S WORTH OF SEARCH DOES, AND THE WHOLE
            FRONTIER IS CONDITIONAL ON A CAMERA ANGLE NOTHING IN THE PLAN PAYS FOR (session 72).
            Session 73 closed the camera half: the bill was the snap window's FAR edge, the near edge
            is 15-38 deg, the last roll pays it, and the faithful frontier is 0.432 u at 75 f with
            `objective.verdict` True. See the box above.**
            The band's landing goes **4.90 -> 0.202 u** and the plan's end-to-end score reads **75
            frames (timeloss +2, INSIDE the accepted budget) at pd 1.644 u**, `objective.verdict`
            False on the placement band alone (0.644 u) -- but at the LIVE csangle the same band's
            best is **46.3 u**, because every atom variant there locks the L. Session 71 handed over
            two steps: probe the true escape over the whole step-1 band, and make the screen
            two-stage. The first found the frontier was already right and the ATOM was not; the
            second cannot be built as specified.
            - **THE WIDE EXACT PROBE CONFIRMS s71's FRONTIER RATHER THAN MOVING IT** (the handoff's
              step 1b). All **69** step-1 jf-7 rolls, exact escape, 13 s (not the ~10 min estimated --
              the atom is ~0.06 s, so an exact escape over a whole band is free): the best landing is
              **4.90 u** and the best coord distance **3.124 u**, i.e. bit-identical to the 15
              best-PREDICTED that s71 ran. The prediction is optimistic but its TOP is right.
            - **AND THE BOUND-RANK IS WORTH 2 FRAMES ON THE BINDING CONSTRAINT** (step 1a): ranking
              the same 8 atom variants by `escape_probe`'s ``bound`` instead of its ``miss`` takes the
              best from **77.50 to 75.51** (``freeze_f`` 4 against 5, landing 4.90 -> 6.78). The
              ``freeze_f``-1 arrivals the handoff pointed at are real and useless on their own -- they
              land 42-50 u out -- so the frames and the landing have to be priced TOGETHER, which is
              what ``bound`` is.
            - **THE TWO-STAGE SCREEN CANNOT WORK, BECAUSE PER-ENDPOINT SURVIVAL IS ONE ALPHABET
              MEMBER WIDE.** Measured over both full-resolution bands (200 surviving rolls): the
              median live endpoint has **1** surviving aim and the widest survivor window is **0.04
              deg**. A ``[::step]`` decimation is a strict SUBSET of the full-resolution fan, so no
              refinement stage can recover what the coarse pass missed -- and it misses most of them:
              ``probe_step=8`` finds **21%** of jf 7's 66 live endpoints and **8%** of jf 6's 126.
              What it drops is not tail: it loses jf 7's best bound (77.54 against **75.51**) and jf
              6's best landing (32.13 against **19.97 u**).
            - **THE AXIS THAT WORKS IS THE WINDOW, AND IT IS CHEAPER THAN THE STEP.** Survival is
              razor-thin in aim but its LOCATION is not: every survivor of both bands sits within
              **8.34 deg** of the bearing to Tetra, and both bands' best arrival on BOTH keys sits
              inside **2 deg** of it. Per endpoint that is **20 aims** against ~31-35 for the shipped
              screen, i.e. the complete choice is also the cheap one. Recall of ENDPOINTS still falls
              with the width (+-2 deg holds 18% / 60%, +-8 deg holds 98% / 99% at 83 aims), and the
              cost is NOT a general inequality -- the aim alphabet is not uniformly dense, so on the
              human's own cycle-1 exit +-2 deg holds 62 members of 429 where a uniform fan would hold
              40. So ``probe_half`` is a budget knob whose cost is measured per stage, gated as such.
              A fitted lead does NOT shrink it further: the offset correlates strongly WITHIN a band
              (r -0.87..-0.90 on jf 7) and a pooled single-feature fit still needs +-7.4 deg.
            - **AND END TO END IT IS NOW A WIN, WHICH IT WAS NOT AT s71.** Cycle 3 off the same dumped
              s69 cycle-2 beam, same 250-of-4622 pool, at ``probe_contact=True probe_step=1
              probe_half=+-4 deg`` with ``land_keep`` and the swept escape: **21** roll survivors ->
              **8** diverse (s71: 12 -> 3 identical), and the best lands **0.49 u** off the thread at
              80 f with `aim.handoff_spec` **True** -- the first True in a real chain run -- against
              s71's 21.46 u at 77 f and s70's best-landing 15.70 u at 80 f. 1637 s against 1116.
            - **THE ATOM'S ``flip_bearing`` AND ``rotate_off`` WERE AT THEIR DEFAULTS, AND THEY ARE
              THE PLACEMENT.** `away_walk.probe` swept 8 variants that decide WHEN the atom separates
              and where LINK ends up, and left the direction its conversion frames PUSH HER at the
              herd's own down-bearing. Those frames are the last inputs with authority over Tetra
              (s67), so that default was the single largest unexamined term in the plan. Swept
              (`probe(flip_step=, rotate_offs=)`, 0x400 over +-56 deg x 4 rotates, ~30 s an endpoint),
              over all 112 unique arrivals of both bands: **51067** firing variants, and the
              frame-capped frontier reads **75 f -> pd 1.644**, 76 -> 1.242, **77 -> 0.202**, 79 ->
              0.079, with `aim.handoff_spec` **True** for the first time in this work. Against the
              session's own starting frontier (4.90 u at bound 77.50) that is the whole remaining gap
              closed except **0.644 u at the accepted budget**. The landing is PIECEWISE CONSTANT in
              the flip bearing (plateaus 10-25 deg wide), so 0x400 resolves it and a 0x40 pass found
              nothing between.
            - **SWEEPING IT FORCES THE FRAMES RANK, WHICH IS NOT A PREFERENCE.** The same arrival
              reaches 0.33 u at ``freeze_f`` 12 and 1.64 u at 4, so a landing-only rank pays 8 frames
              for 1.3 u against an objective that allows 2 (`objective.TIMELOSS_BUDGET`).
              ``rank='frames'`` prices the landing in the objective's currency (``freeze_f +
              objective.thread_frames``, i.e. ``bound`` minus the constant arrival) with the miss as
              tie-break.
            - **AND THE FLIP HAS NO STATIC ADMISSIBLE ARC -- THE COST OF ASSUMING ONE IS MEASURED.**
              The conversion IS `getDirectionFromAngle`'s DIR_BACKWARD negation, whose cone is 90 deg
              wide about 180 (`reference/constants.md`'s 0x6000 row), which looks like a derived bound
              on the flip stick. It is not: the cone is about ``travel`` AT THE CONVERSION FRAME,
              which the ESS snap and the L frame's own chase move. The 75-frame winner sits **61 deg**
              off the ARRIVAL's back-bearing -- outside the cone -- and lands 1.644 u where the best
              variant inside it lands **4.112**. So `away_walk.flip_arc`'s ``half`` is a BUDGET
              (`FLIP_SPAN`) and `fires` stays the filter.
            - **THE END-TO-END SCORE, WHICH IS THE NUMBER TO QUOTE**
              (`objective.replay_and_score`, log ending at the arrival so `score_plan` probes the atom
              itself -- appending the atom's own frames instead double-counts and re-probes from a
              separated state, reading pd 21.5): **frames 75, timeloss +2, INSIDE the accepted
              budget**, ``terminal_ok`` **True**, ``wall_ok`` and ``regime_ok`` True, pd **1.644 u**
              -> ``complete`` False and `objective.verdict` False on the placement band alone.
              ``atom_kw`` now forwards the swept knobs to that probe, without which a swept plan is
              scored against a different escape than the one it plans.
            - **AND THE WHOLE THING RESTS ON A CAMERA ANGLE NOTHING IN THE PLAN PAYS FOR, WHICH IS
              THE OPEN ITEM AND IS NOT NEW TO s72.** `away_walk._clone_for_atom` detaches the wired
              camera and COMMANDS ``csangle``; `probe` uses `snap_csangle`'s value for EVERY variant,
              including the ``turnaround_first=False`` ones that never snap. On these arrivals that
              value is **105-111 deg** from the live csangle, and at the LIVE csangle the band's best
              placement is **46.3 u** -- because **1024 of 1024** variants there die on ``l_ok``: the
              arrival's EBS still faces Tetra, so Dereck's rule-1 turnaround is MANDATORY and it needs
              the snap window (at the snap csangle 493 of the same 1024 fire). One cycle-3 roll's
              C-stick slew delivers ~**47 deg** of the 105 (0x9ae6 -> 0x79c1 in 19 frames), and asking
              for it CHANGES the arrival (the roll's exit ESS decodes against csangle), so the aim and
              the camera target have to be searched jointly -- which is what `roll_candidates`' tcs
              grid already is. Every atom number in this work since s65 carries this condition; s72 is
              where it was measured.
            - **jf 5 IS NOT WHERE THE FRAMES ARE** (a probe worth not repeating): the earliest band
              arrives at **69 f** against jf 7's 71, and at +-8 deg step 1 it holds 77 live endpoints
              of 210 whose 78 arrivals ALL fire -- but its best placement is **10.9 u** and its best
              bound 74.33 comes with pd 57. Two frames earlier, ten units worse.
            - Do NOT re-pay: a two-stage screen staged on ``step`` (survival is one aim wide), a flip
              arc derived from the ARRIVAL's travel (the winner is outside it), appending the atom's
              own frames to a log handed to `score_plan` (it probes the atom itself; the log ends at
              the arrival), or treating an atom landing as replay-faithful without checking the
              csangle it was computed at.
      - [x] **THE SQUARE ARRIVING ENDPOINT EXISTS -- THE SCREEN'S AIM RESOLUTION COULD NOT SEE IT
            (session 71). In the ARRIVING band the endpoint probe finds 2 rollable endpoints of 420 at
            its shipped resolution and 66 at full resolution, and the best of those delivers Tetra to
            lateral +0.26 with Link 1.2 u off her lateral -- a predicted escape landing of 0.53 u where
            the s70 plan's was 36.4 and its exact escape 57.69.** Session 70 handed over "buy the
            squareness at the new arrival: probe the jf-6 band wider and report ``off`` beside
            ``arrive``, and if a square arriving endpoint exists the keep is a COMBINED key". It does
            exist, the keep did need fixing, and neither was the binding constraint: the SCREEN was.
            - **THE WIDE CENSUS FIRST (the handoff's step 1, done at 20x its size).** Every armed
              endpoint of two real cycle-2 exits, all eight junction-frame bands, `roll_probe`'s joint
              (|over|, ``off``) frontier per band via the new ``collect`` sink -- 9022 endpoints, 98
              surviving rolls, ~50 min. The arriving band (jf 6) holds **2** rollable rolls in 416
              endpoints and neither is square (``off`` 47.7 / 35.7); jf 7 reads **0 of 420**, i.e. DEAD;
              and one band later jf 8 holds 23 rolls of which one delivers ``off`` **3.08** at ``over``
              +18.8. So on that evidence the squareness lives one band PAST the arrival and the keep
              would have to trade ~1.4 frames of overshoot for ~32 u of squareness.
            - **BUT THE SCREEN IS 3x COARSER THAN THE STAGE IT SCREENS FOR, OVER A FAN 6x WIDER THAN ANY
              ROLL CAN SURVIVE IN.** `roll_probe` swept +-0x2800 (112.5 deg) about the HERD bearing at
              ``step=24`` (~27 aims) while `roll_candidates`, the stage it feeds, uses ``step=8``. Death
              is 95-99% ``followed`` -- Link past `FOLLOW_ENGAGE_DIST`, which a ~223 u roll does the
              instant it stops plowing her -- so survival is a narrow cone about the bearing to TETRA,
              and measured over the whole armed set the 33 survivors occupy **18.5 deg** of that 112.5
              herd-relative and **13.4 deg** Tetra-relative. The budget was being spent where nothing
              can live. Re-centred on the per-endpoint bearing to her and narrowed to `pursuit_box`'s
              measured ``max_delta`` (**+-21.35 deg**, the recorded regime -- containment holds, the
              human's own two rolls sit at +0.76 and +0.63 deg and the widest survivor at 7.65), ~31
              aims at ``step=8`` cost what ~27 at ``step=24`` cost. Wired
              `roll_probe(fan_center=)` / `extend_cycle(probe_step=, probe_contact=)`, self-checking via
              ``fan_edge``/``fan_half`` so a binding window reports itself instead of being assumed away.
            - **AND THE ARRIVING BAND WAS NEVER DEAD.** jf 7, 420 endpoints: **0** rollable at the
              shipped screen, **2** at ``step=8`` over the wide fan, **14** at ``step=8`` over the narrow
              one, **66** at ``step=1`` over the narrow one (69 surviving rolls). Its frontier is smooth
              at full resolution -- (|over|, ``off``, Tetra lat, Link-Tetra lat): (6.8, 1.1, +3.5, -0.1),
              (9.1, 0.3, +2.2, -12.2) -- and its best predicted landing is **0.53 u** at ``over`` +7.8,
              ``off`` 2.24, Tetra lateral **+0.26**, Link **1.2 u** off her lateral. That is the
              squareness the human has, in the band that arrives, at ~71 frames. 1013 s for the one band,
              so full resolution is a two-stage screen's job (coarse to find the live bands, fine inside
              them), not a new default.
            - **THE KEEP DID NEED FIXING, AND THE CORRIDOR IS WHY: IT IS A LINE THROUGH ONE POINT.**
              ``square_keep`` ranks `roll_probe`'s ``off``, the distance from `aim.handoff_corridor` --
              which runs from the origin through the SINGLE handoff target. The real target is a segment
              whose lateral falls **0.215 u per u of along, 78x the corridor's own slope**, so the two
              agree only where the arrival is exactly on target. Short of it they still agree (the near
              end clamps the landing, which is why this never showed while the chain undershot); past it
              the corridor's lateral ask is wrong by **1.33 u at along 900, 4.11 at 912.7, 10.18 at
              949.5** against a `objective.PLACEMENT_BAND` of **1.0** -- and a roll cannot stop short, so
              every arrival the last cycle chooses between is past it. On four measured rolls at jf
              7/8/10/12 ``off`` ranks them in EXACTLY the reverse order of where the escape lands, and
              puts LAST (5.01) the roll that lands best (2.93) and takes the fewest junction frames.
              Fix: `aim.thread_miss` + `roll_probe(thread=, resid=)`'s ``land`` axis (the landing point
              measured against the segment, exact given the residual, free -- the sweep already fires
              every aim) as a keep share, `extend_cycle(land_keep=)`. It SUBSUMES ``off`` and ``arrive``
              rather than joining them.
            - **AND THE ESCAPE ATOM'S OWN VARIANT CHOICE WAS PLACEMENT AUTHORITY SPENT ON THE OTHER
              SEARCH.** `away_walk.probe` ranks its ~8 variants by rule-3 compliance and then by
              ``d_e_end``, how far Link got toward `seeds.ENTRY_ROLL_POS` -- the SEPARATE entry search
              (s60). But s67's own finding is that the atom's conversion frames are the LAST inputs with
              authority over Tetra, so its knobs are part of the placement. Measured over the sweep, the
              residual's lateral tracks Link's lateral offset from her at **-0.53 u per u (r -0.926)**
              and its along collapses from **41.60 u** aligned to **6.29-15.33** at 30-47 u off -- so the
              corridor's one measured residual is the ALIGNED case only, and ``rotate_side`` (which way
              he steps before the slam) moves the landing a long way. Ranking the COMPLIANT variants by
              the landing improves **6 of 8** real arrivals (median **2.70 u**, max **10.08**) and takes
              the sample's best from `probe`'s 16.34 u off the thread to **6.25** (7.15 u from a genuine
              coord) at 77 frames, with ``rotate_side=+1`` winning 6 of 8. Wired
              `away_walk.probe(thread=)` / `escape_probe(atom_landing=)`, default ON; the acceptance
              (``l_ok``, the follow shell, separation, ``DIP_BUDGET``, receding at the cap) stays a hard
              term ahead of it, and without ``thread`` the key is bit-identical to the s65 rank.
            - **THE CHEAP-KEY CALIBRATION, against the real atom over 35 firing picks** (the s70 method):
              ``land`` **r +0.834**, ``off`` +0.783, |``over``| **-0.423**, |Link-Tetra lat| +0.326. So
              ``land`` is the best cheap key and the sign on the arrival is NEGATIVE -- more overshoot
              landed better, because within this sample the corridor's bias grew with it. All of them are
              weak enough that the true landing has to be probed, which is what `escape_keep` is for. (A
              12-row contact-fan sample read |Link-Tetra lat| at +0.878 and ``land`` at +0.524; that
              sample was 8 duplicate rows of one arrival. Dedupe before correlating.)
            - **AND THE EXACT ESCAPE OFF THOSE ROLLS MOVES THE PLACEMENT FRONTIER 15.70 -> 4.90 u, WITH
              THE ARRIVAL INSIDE THE PREFERRED FRAME BUDGET.** The real atom (landing-ranked) on the 15
              best full-resolution rolls: **18 of 18 fire**, the best lands **4.90 u** off the thread and
              **4.902 u from a genuine coord** from a **71-frame** arrival at `plan_bound` **73.76** --
              inside `objective.frame_floor`'s PREFERRED 74, let alone the 75 budget -- and the best coord
              distance in the set is **3.124 u** (row 3: ``over`` +9.2, ``off`` 5.00, Link 2.9 u off her
              lateral, escape bound 77.89). Against the s67/s70 frontier of 15.70 u at 78-80 frames that
              is 5x closer at 7-9 fewer arrival frames. What is still open is the ESCAPE's own bound
              (76-77 frames + the landing's remaining `objective.thread_frames` = 77.50) and the
              `aim.handoff_spec` verdict, which needs the landing inside `objective.PLACEMENT_BAND` (1.0)
              and reads False on all 18.
            - **THE PREDICTION REMAINS OPTIMISTIC AND NO CHEAP KEY DOMINATES ACROSS SAMPLES.** pred 0.53
              -> true 12.55, pred 7.64 -> true 4.90: the ordering is only ~0.73 correlated, and the two
              samples disagree about which cheap key is best (35-pick census: ``land`` +0.834, |Link-Tetra
              lat| +0.326; 18-pick full-resolution: |Link-Tetra lat| **+0.827**, ``land`` +0.728). So
              ``land`` is the right axis to KEEP on -- it is the only one measured against the real target
              -- but the landing itself has to be probed, which is what `escape_keep` is for.
            - **END TO END THE AFFORDABLE WIRING IS NOT YET A WIN, WHICH IS THE OPEN ITEM.** Cycle 3 off
              the same dumped s69 cycle-2 beam with the narrow fan + ``probe_step=8`` + ``land_keep`` at
              the SAME 250-of-4622 pool: 12 roll survivors -> 3 after the beam, all identical (along
              936.64, lat -24.49, ``off`` 27.08, ``over`` +42.8), escape landing **21.46 u at 77 f**
              (`plan_bound` 76.39, escape bound 81.41), 1116 s. That beats s70's in-budget arrival
              (57.69 u at 71 f) and LOSES to s70's best-landing survivor (15.70 u at 80 f) -- and the
              beam collapsed because at a fixed ``step`` the narrow fan is a different SUB-LATTICE of the
              reachable set rather than a superset: it found 10 and 4 rollable endpoints on two of the six
              nodes and none on the rest at that cap (s70's run had 21 survivors). The strict win is
              RESOLUTION, which at 1013 s a band cannot be paid uniformly -- hence the two-stage screen.
              The session's value is the census and the atom rank, not this run.
            - Do NOT re-pay: "rank the arriving band by ``off``" as a gate width (the corridor is the
              wrong line past the target, so a width on it cannot help), an aim key for the tcs cut
              (s70), the narrow fan at a fixed step treated as a superset of the wide one (measured: jf 6
              gives 20 rollable wide against 10 narrow), or the assumption that a band reading 0 rollable
              is dead -- at this stage that is a statement about the screen.
              **Session 72 answered both handoff steps: the wide exact probe confirms this frontier
              rather than moving it, the two-stage screen it proposed cannot be built (survival is one
              aim wide -- the axis is the WINDOW), and the placement was in the ESCAPE ATOM's two
              unswept knobs all along. See the box above.**
      - [x] **THE OVERSHOOT WAS THE PROBE POOL, WHICH IS A FLATNESS PREFIX AND NOT THE GENERATION
            PREFIX IT SAID IT WAS (session 70): cycle 3's arrival went along 947.4 (+53.5 PAST the
            handoff target) -> 886.81 (7.1 SHORT), frames 75 -> 70, `plan_bound` 77.27 -> 75.03, the
            escape landing frame 78-80 -> 71.** Session 69 handed over two steps -- an AIM-aware key for
            the tcs cut at cycles >= 2, and "price the OVERSHOOT". Both were built; both were measured
            INERT; the measurement of WHY named a coverage bug one stage down that was worth 9 frames.
            - **THE CALIBRATION KILLED THE AIM KEY BEFORE IT WAS WIRED, AND THE GRID SAYS WHY.** Cycle
              1's 25-exit grid is fully probed (s69), so a proxy can be scored against the truth for
              free. Keep of 3, what it DELIVERS in corridor offset: stock `(-inbox, |lat|)` **14.67 u**
              (best at rank 5), `(-inbox, glide |aim|)` **116.93** (rank 7), `(-inbox, glide |aim| +
              cone)` **116.93** (rank 4), `(-inbox, exit |aim|)` and exit-aim-alone **NOTHING** (rank
              19), the CHEAP probe **11.20** (rank **1**), the full probe 11.20. So the proposed key is
              not merely no better than the one it replaces, it is the worst of the candidates -- and
              structurally, not by luck: **18 of the 25 exits sit at |aim| 1.26-2.05 deg and not one of
              them can roll at all**, while every exit that delivers anything measures |aim| >= 3.0. The
              cheapest scalar that looks like squareness ranks the DEAD exits first.
            - **WHAT IS AFFORDABLE IS THE SAME PROBE, COARSER** (`full_herd.CHEAP_PROBE` /
              `square_probe_key`, ~2.7 s against ~21 s): coarseness costs RECALL, not precision. It
              scores only 2 of the 6 armable exits, but both are real, they are the full probe's #1 and
              #3, and on the one it ranks best its value is **bit-identical** to the full probe's
              (11.200566297610363). It declined every exit the full probe also calls dead. The 9.6 s
              budget does NOT have that property (it reported 59.97 and 100.74 on two exits the full
              probe calls unrollable), which is why the cheap budget is the small one. Wired as a KEEP
              share, opt-in (`chain_herd(mid_square=)`, ~2.7 s per surviving (aim, tcs) pair).
            - **AND THE LAST CYCLE'S CAMERA CUT WAS RANKED BY A QUESTION IT DOES NOT HAVE**
              (`landing_key`, free, default ON). `junction_quality` asks whether the NEXT junction can
              continue; the last cycle has none. Its exit IS the handoff, so rank it by where the escape
              lands from it. Measured on real arrivals, the stock rank is PAID for overshooting:
              `rank_key('thread')` scores an arrival sitting ON the coord -- 44 u past the state the
              escape needs -- as its BEST (0.00 frames) and one at the handoff target **3.36 worse**,
              because the thread's 47.6 u of along slack charges nothing for along inside it. The exact
              landing says which is right: **14.54 u** off the thread from the coord position, **5.47**
              from the handoff-target one.
            - **THE OVERSHOOT PRICED IN THE KEEP AND IN THE RANK -- AND ALL THREE INERT.**
              `roll_probe(target_along=)` reports the arrival its rolls DELIVER (``arrive``/``over``,
              purely additive), a share of the endpoint keep goes to it (``arrive_keep``), and
              `aim.handoff_rows` shifts the whole target set up-herd by the measured residual so
              `rank_key(resid=)` prices arriving at the handoff (never the admissible budget CUT). Run
              on the dumped s69 cycle-2 beam, all three together returned a **byte-identical** cycle 3
              -- same 18 survivors, same 15.70 u frontier, same 78-80 frames.
            - **BECAUSE THE POOL HELD EXACTLY TWO ARRIVALS.** The whole surviving set was along 947.40
              or 949.50, so a keep by arrival had nothing to choose between. `_probe_pool`'s own note
              said `extend_cycle` probes the first ``cap`` "in COLLECTION order (generation order), i.e.
              the earliest junction frames" -- it does not: with ``keep`` unbounded `junction_beam`
              RETURNS its endpoints sorted by ``(|Link - Tetra lateral|, jf)``, so the prefix is a
              FLATNESS sample. Off cycle-2 node 0 the beam arms **4622** endpoints spread over jf 5..12
              and the 250 probed were **entirely jf 8 and jf 10**.
            - **AND THE JUNCTION FRAME IS THE ARRIVAL.** The roll's length is fixed (~223 u off that
              exit) while the junction pushes 11-12 u/frame, so from Tetra at along 579.19 the bands land
              at jf 6 -> **887**, jf 8 -> 895, jf 10 -> 921, jf 12 -> **947**. Probing 25 per band: the
              earliest rollable endpoint is at **jf 6 and its roll delivers 886.81, i.e. 7.07 u from the
              target** where the flattest-250 pool's best was 53.5 u past it. The dominant death across
              every band is the MODEL boundary, not physics -- `followed` (Tetra past
              `FOLLOW_ENGAGE_DIST`) kills 660-676 of ~675 aims per band, with wall/offline in single
              digits.
            - **THE FIX IS A BAND SHARE IN THE POOL** (`_probe_pool(jf_spread=)`, on whenever
              ``arrive_keep`` is): walk the junction-frame bands round-robin so every band is probed
              rather than whichever one happens to be flattest, at the same pool size. It must NOT
              inherit the squareness pool's per-state cap (that hands back one pending variant per
              physics state). Flatness not predicting rollability is `roll_probe`'s own founding
              measurement; this is the same lesson applied to WHICH endpoints get probed at all.
            - **CYCLE 3 ON THE FIXED POOL, off the identical dumped beam and config**: 21 roll survivors
              (18), 8 kept, **all 21 fire**; the new best sits at along **886.81** (``over`` **-7.1**
              against +53.5), **70 frames** against 75, `plan_bound` **75.03** against 77.27, and its
              escape lands at frame **71** against 78-80. 780 s.
            - **SO THE FRAMES ARE BOUGHT AND THE DEFICIT MOVED BACK TO SQUARENESS AT THE NEW ARRIVAL.**
              That endpoint's corridor offset is **35.73 u** with Link **55.3 u** off Tetra's lateral, so
              its escape lands **57.69 u** off the thread against the 947-arrival's 15.70. The frame
              position is now at the budget (bound 75.03, escape at 71 f) and the whole remaining gap is
              lateral -- which is what s68/s69's machinery is for, now pointed at the ARRIVING band
              instead of at the whole endpoint set.
            - Do NOT re-pay (all measured inert this session): an AIM key for the tcs cut at any cycle
              (worse than stock, and worst as the exit's own aim), `landing_key` / ``arrive_keep`` /
              `rank_key(resid=)` WITHOUT the pool fix (byte-identical cycle 3), or the coarse probe at
              the 9.6 s budget (false positives).
              **Session 71 found the next layer of the same bug: the pool decides WHICH endpoints get
              probed, and the probe's own AIM RESOLUTION decides whether it can see them. See the box
              above.**
      - [x] **THE AWAY-WALK, WORKED OUT AND SHIPPED AS AN ATOM (session 65): it is THE HERD
            JUNCTION WITH THE ROLL REPLACED BY A BACKWARDS SLAM -- convert to positive first, so
            the reversal never crosses zero.** Dereck steered live throughout: (1) the placement
            planner must ACCOUNT for the movement that reverses travel direction toward the
            roll-from region, herding COMPLETE at separation, the Link-only leg then borrowing the
            existing 2D planners; (2) the bar is true per-frame displacement vs the 17 u walk cap
            after separation -- and he CONFIRMED the turnaround's dip is inherent (0 sub-17 frames
            is not feasible); (3) no A press; an L that targets Tetra means the facing was toward
            her during the EBS; one L frame converts; (4) **the recipe: "do the same inputs you do
            during the herd phase to convert to positive and then roll, but instead of rolling,
            slam backwards (one frame left or right beforehand)"** -- measured, it is the known
            best by a wide margin. Developed on `synthetic_hot_arrival` (coord 287, feet 64).
            - **THE ATOM (`away_walk.py`, gated `tests/test_away_walk.py`), frame by frame on the
              bed:** [optional ESS turnaround when the EBS still faces her] -> L + toward-Tetra
              stick, ONE L frame, stick held one more (the delay-1 shape of "L+up": the negation
              fires on the ATN dispatch frame with the L already released) -> **-25.727 ->
              +17.614 POSITIVE** (travel down-herd, motion unchanged -- still placement frames)
              -> one frame ~90 deg off ("left/right", defeats the genuine-flip gate) -> backwards
              slam -> `procMoveTurn(1)` halves the POSITIVE run onto the reversed travel:
              **+17.0 -> +8.5 moving UP-HERD, no zero crossing** -> accel +10 -> +13 -> **17.0 at
              f8**, receding every frame from the slam.
            - **THE NUMBERS THE PLANNER CONSUMES.** Separation = the slam frame (freeze and
              reversal are the SAME frame); **3 post-separation sub-17 frames** (the halving dip
              + two accel frames -- `DIP_BUDGET`, pinned both ways in the gate); Tetra's residual
              over the conversion frames is **34.8-40 u, lat < 9 u** (rides the corridor) -- the
              terminal targeting's deterministic UNDERSHOOT. Contact displacement is
              recoil-halved (~12.9 u/f) so pre-separation frames are herd frames; the bar counts
              from the slam.
            - **WHY CONVERT FIRST (the traps, all measured -- do not re-pay).** Slamming the
              NEGATIVE EBS directly also reverses in one frame but the halved run decays through
              zero (~12 sub-17 frames -- speed targets are non-negative for a backslide, move.py
              95-99, so a negative run has nothing to rebuild from); slamming the positive run
              WITHOUT the rotate frame re-fires the negation ("fast + genuine stick flip") and
              flips it back negative; moving the stick to left/right ON the negation frame reads
              DIR_SIDE and never converts (hold the toward stick across the L release);
              `procSlip` skids to zero before flipping; the L+A ballistic hops reverse at 22.5+
              with no dips but Dereck ruled A out (and they talk or break the follow shell).
            - Offline suite **692 -> 696** (+`tests/test_away_walk.py` 4: one-L conversion + no
              zero crossing, slam = reversal = separation + the corridor residual, Dereck's
              rules, the 3-dip pin), 0 fail, same 8 xfails; land goldens byte-identical (no
              library change -- the harness only).
            - **NEXT, in order.** (1) **Wire rule 3 to the atom**: `objective.turnaround_ready`
              is still the s64-falsified predicate on disk; replace it with "the escape atom
              fires from the terminal state" (`escape_atom`'s `l_ok` + dips <= `DIP_BUDGET` +
              receding at the cap), which re-scores the 73/74 f plans -- expected to move the
              bar. (2) **Wire the terminal targeting to the residual**: aim the last pushes so
              the atom's ~35-40 u lands her ON the coord (deterministic undershoot, no new
              search). (3) The entry leg: `walk_to_entry`/`reach_precise` from the atom's
              handoff (receding at 17 toward the entry side) to `ENTRY_ROLL_POS`/facing 40835 --
              the SEPARATE search s60 scoped.
            Do NOT re-pay: the escape traps above, the junction moves (s64), terminal ranks
            (s63), the cycle count (s63), or "more push" (98.5% saturated).
            **Session 66 wired steps (1) and (2) -- see the box above.**
      - [x] **THE LAST FIDELITY SEED IS CLOSED: 0-ULP ON EVERY IN-REGIME SAMPLE THE CONSOLE
            MEASURED, n=1..80 (session 59). What is still open is SCOPE, not fidelity.**
            Session 58 handed over "model the WAIT stop". The sim did not pose at all across it
            (`FootSpeedF.step` early-returns at `|mNormalSpeed| <= 0.001`), so the re-walk at 78
            measured its `f31_2` off the WALKING poses from 74/75: 2.617 u where the console takes
            0.379 u. The handoff's expected fix -- reuse `enter_subjectivity`/`step_subjectivity`,
            the WAITS/WALK idle blend -- was the RIGHT SHAPE and the WRONG ARM.
            - **THE BRANCH, read live rather than inferred.** A plain WAITS idle at rate 1.1 drifts
              at most 0.230 u/frame ANYWHERE in its 60-frame cycle, so 0.379 was never reachable by
              tuning the phase or the morf (swept: no value hits both 78 and 79). One truncate-and-read
              pass over n=74..78 reading the under-body anim registers settled it:
              **`m34C3 == 0`** at 76/77 -- a SINGLE, not a blend -- on arc entry **285 =
              `waitatob.bck`**, frame ctrl end/rate/start **12 / 0.6 / 0.0**. Those three are
              `mMove.field_0x10`/`0x68`/`0x6C`, and they appear together in exactly one place:
              `procWait_init`'s `checkRestHPAnime()` arm (`setSingleMoveAnime(ANM_WAITATOB, ...)`,
              6072). **Link is on his last hearts here**, so the stop plays the low-life wait A-to-B
              transition. Truth page `knowledge/model/wait-stop-pose.md`.
            - **IT ALSO OWNS THE RE-WALK.** A single leaves `m34C3` at 0, and `setMoveAnime` carries
              the anim phase only when `m34C3` is not 0/9/10 (12729) -- so the walk at 78 restarts
              BOTH controllers at frame 0 instead of resuming the carried WAITS phase. The console
              agrees to the bit (fc0 0.0, fc1 0.0, ratio 0.343418986). Two more shape facts, both
              gated: MOVE1's ctrl takes its actor-execute advance on the stop frame and then FREEZES
              (`setSingleMoveAnime` clears its heap idx), and `procWait` re-poses only if the
              single's rate died or life recovered -- here it just advances 0.6/frame.
            - **AND `procMove_init`'s MORF FIRES ON THE WAIT EXIT**, exactly as it already did on the
              ATN->MOVE one (6215). That was the whole of frames 79-80; with it, 78/79/80 went 0-ULP
              together.
            - **WHAT `low_life` IS.** `checkRestHPAnime` is `getLife() <= mMove.field_0xE` (6) AND
              `mpAttnActorLockOn == NULL` AND no upper anime AND no guard. Link's life is not
              simulated, so `LandState(low_life=)` seeds that half (`from_f0.LOW_LIFE`, defaulting
              False so every anchor and golden keeps the idle-blend arm) and
              `_check_rest_hp_anime()` evaluates the half that varies inside a run: the actor lock.
            - **GATE.** `fixtures/courtyard_node1_wait_s59.json` (NEW, LOCKED -- the live under-body
              anim registers + `mFootData` toes at n=74..78) + `tests/test_wait_stop_pose.py` (5),
              which scores a WAIT-pose candidate offline in 0.2 s instead of a live run. It caught a
              real gap while being written (MOVE1's missing advance on the stop frame). `OPEN` is now
              **{100, 120, 160, 200}**, all of them at or past the regime break; the localization
              test is REPLACED by `test_the_first_open_sample_is_the_follow_flip_not_a_fidelity_gap`.
              655 offline pass, 0 fail. Native twin ported (`C_WAITATOB`, `_w_pose_idle_blend_c`,
              `_w_enter_wait_rest_hp_c`) and `test_freerun_native` green over the whole 241-frame plan.
            - **CAPTURE-ALIGNMENT FACT worth keeping** (it cost a wrong-looking diff): a
              truncate-and-read halt lands AFTER `posMoveFromFootPos` but BEFORE the end-of-execute
              tail (11285-11289). So position and `m359C` are frame N's, while `m35B4`, `m34DE` and
              `m34EA` still hold N-1's -- like `mFootData`. Check it on a field that actually CHANGES
              (facing at the re-walk) before reading a mismatch as a bug.
            - **NEXT: the SCOPE decision, and it wants Dereck.** From plan frame 100 the console's
              Tetra reads stt 4 (FOLLOW) and `FreeRun` raises its own FOLLOW_ENGAGE_DIST warning on
              that exact frame. The plan's second half is outside the stt-3 plow model BY
              CONSTRUCTION and is the likely real cause of the 113 u endpoint miss. Two ways: model
              stt-4 follow, or re-solve the plan under a Link-Tetra distance < 230 u constraint.
              This is NOT another FP hunt -- the FP/pose frontier is closed.
      - [x] **THE POSE STREAM IS NOW CONSOLE-EXACT, AND THE FRONTIER IS THE WAIT STOP (session 58).
            Bit-exact through plan frame 77; the next seed at 78 is the walk RE-ENTRY out of WAIT.**
            Session 57 handed over "the toe stream leaves the console at sim frame 69". It was two
            independent faults in WHAT gets posed, both invisible until plan frame 72 -- the first
            frame whose speedF is anim-driven -- because the toe stream is warmed and unused while
            `m3598 == 0`.
            - **BUG 1: the sword-drawn anim pair.** `mEquipItem` is SWORD all window (`m3562 == 0x103`,
              noted in `## Addresses` since s15 and explicitly filed as "physics-inert"), so
              `getAnmData` (`d_a_player_main.cpp`:12950) serves the under-body anims out of
              `mSwordAnmIndexTable`: **ANM_WALK -> WALKS, ANM_DASH -> DASHS**. That table ends at
              0x1A, so ANM_ROLLF (0x32) and the ATN strafe set map to themselves -- which is exactly
              why the roll and proc-9 poses were already right and only the first DASH pose was not.
              The pair differs ONLY at the feet (joints 0-4/14 identical -> the CC push never saw it),
              and the feet ARE `posMoveFromFootPos`. `from_f0.SWORD_DRAWN`; truth page
              `knowledge/model/equipped-anim-set.md`. Alone it took n=72 from 12/58 ULP to 0.
            - **BUG 2: the draw base.** The game draws at frame END, from the POST-posMove position,
              with the lean (`m351C >> 1`) in the base EXCEPT on a proc `*_init` frame (`commonProcInit`
              zeroes `shape_angle.z` before `setWorldMatrix`) -- the same base the exec Co-centre has
              been live-pinned to since s16, because both come from the one `mpCLModel->calc()`. The
              replay posed pre-integration with no lean. `defer_draw` + the init-lean rule in
              `state.py`'s frame-end block; truth page `knowledge/model/draw-base.md`. It closed the
              1-ULP residue at 73/75/76/77 -- and forcing the lean to 0 puts it back (1-3 ULP), so
              the lean term is load-bearing, not decoration.
            - **HOW IT WAS SETTLED -- against the live TOES, not the endpoint.** s57's footscan already
              held the console's `mFootData` model-local poses (n=62..69). Scoring both draw bases
              against them is decisive and offline: pre-integration is 32-128 ULP off on x/z, deferred
              is **0 ULP on all 20 x/z components**. (Y stays off by 16-36 ULP: `m35B8`, footBgCheck's
              draw-base Y shift, is unmodeled and XZ-irrelevant -- the gate says so.) That capture is
              now the LOCKED fixture `fixtures/courtyard_node1_foot_s57.json` +
              `tests/test_foot_draw_base.py` (7), so the pose stream has its own gate instead of only
              being visible through the endpoint.
            - **BOTH ENGINES.** The native twin carries both: `_anmc` gained the WALKS/DASHS codes
              (`ANIM_ORDER` 15/16, `PoseEngine.set_sword`, `N_ANIM` 17) and the deferred draw
              (`_finish_draw_c` + a leaned `_set_pos_c`), wired into `LandCore.step_courtyard` at the
              same moment as the Co-centre. `test_freerun_native.py` (native == Python over the whole
              241-frame plan) is green, so the search fast path did not silently fork.
            - **GATE.** `OPEN` = {78, 79, 80, 100, 120, 160, 200}; the localization test is REPLACED by
              `test_the_first_open_sample_is_the_walk_re_entry_out_of_wait`. 634 offline pass.
            - **NEXT: plan frame 78 = the WAIT stop / re-walk tier.** Link stops (proc 4 at 76-77) and
              the sim stops posing: `FootSpeedF.step` early-returns at `|mNormalSpeed| <= 0.001`, so
              its toe stream still holds the walking poses from 74/75 and the re-walk's `f31_2` is
              **2.617** where the console's is an idle-drift **0.379** (same direction, 6.9x long).
              The game keeps drawing: `procWait_init` re-poses via `setBlendMoveAnime(field_0xC)` and
              `procWait` leaves `m34C3 == 2` so the ctrls just advance -- the shape
              `enter_subjectivity`/`step_subjectivity` already implement for the C-up freeze (a WAIT
              whose anim keeps running). Confirm the branch live first (one footscan at n=76..78 reads
              `m3598`/`m359C`/the toes and says whether `ModeFlg_00000001` took the idle arm), then
              reuse those two, since `foot_speedf`'s own docstring lists this tier as unmodeled.
      - [x] **THE SECOND UNTARGET CYCLE NOW DISPATCHES ON THE CONSOLE'S FRAME, AND THE FRONTIER IS
            THE FOOT POSE (session 57). Bit-exact through plan frame 71; the next seed at 72 is the
            first ANIM-DRIVEN speedF frame since the roll.**
            - **THE BUG: `chaseAttention`'s front cone is an ACQUIRE/LOCK gate, never a RELEASE one.**
              `judgementStatusHd` consults `chaseAttention()` in NONE (acquire, `d_attention.cpp`:810)
              and in LOCK (`judgementLostCheck`, 816), but RELEASE (837) tests
              `LockonTarget(0) == NULL || !AttnFlag_40000000` -- the FROZEN list entry plus the
              reticle-fade flag. `stockAttention` runs only in the NONE branch, so nothing can re-make
              the list mid-fade either: for an actor that does not despawn, RELEASE is a pure
              countdown. The sim fed the same cone-gated `target_present` to all three branches, so
              when Tetra swung out of the +-0x4000 cone at plan frame 64 the lock died with 5 fade
              frames still owed, and the roll exited into MOVE_TURN (24) where the console takes its
              proc-9 brakeslide frame (68). Truth page:
              `knowledge/mechanics/attention-lock-lifetime.md`. Fixed in both engines
              (`attention.py` `update(..., target_exists)`, `_anmc.pyx` `_atn_update`); the RELEASE
              branch now keys on `_atn_target_exists` (`procs/atn_actor.py`). Frames 68, 69 and 70 all
              went 0-ULP on both actors at once.
            - **THEN THE BAND BEHIND IT WAS SAMPLED LIVE** (`_notes/tetrapush-s57_bracket.py`, 9
              truncate-and-read runs): n=71 exact, n=72 the first miss.
              `fixtures/courtyard_node1_console_s57.json` (NEW, LOCKED; consecutive n=71..79).
            - **FRAME 72 IS A FOOT-POSE DIVERGENCE, NOT A TURN ONE.** It is the first MOVE_TURN body
              frame, i.e. the first frame since the roll whose speedF comes from the walk anim
              (`m3598 != 0`) instead of momentum. The console's step is PARALLEL to the sim's to the
              last ULP and 0.05% longer -- pure magnitude. Reading the live foot internals at the halt
              (`_notes/tetrapush-s57_footscan.py`, the `foot_probe` offsets) splits the layers: the
              composition math is right (live `m3598`/`msd`/`m35B4` match the sim 0-ULP, and
              `0.3*raw + 0.7*prev` on the live plant-toe delta reproduces the live `m359C` exactly),
              while its INPUT stream is not. The model-local toe positions track live to ~1 ULP at
              sim frames 4, 9, 19, 45, 59, 61, 63, 65, 67 and 68, then jump to ~0.02 u at **sim frame
              69** -- the roll/ATN -> MOVE re-entry pose (`MOVE_REENTRY_MORF`). The stream is warmed
              but unused while speedF is momentum, which is exactly why the error surfaces 3 frames
              later. (Alignment is not assumed: live `mFootData` at frame N == the sim's pose at N-1,
              verified on the known-exact early frames before any claim was made.)
            - **GATE.** `OPEN` = {72..80, 100, 120, 160, 200}; the localization test is REPLACED by
              `test_the_first_open_sample_is_the_first_anim_driven_speedf_frame`, which asserts the
              parallel-and-longer signature off the fixture + rollout. New offline gates:
              `test_atn_actor.py::test_release_survives_leaving_the_front_cone_but_lock_does_not`
              (all three branches, incl. a deleted target) and
              `test_freerun_native.py::test_native_and_python_agree_across_the_second_lock_cycle`
              (the DTM window ends at f43 and never reached the second cycle, so the native engine's
              copy of the machine was ungated). 625 offline pass.
      - [x] **THE FP FRONTIER IS CLOSED, AND WHAT IS LEFT IS NOT FP (session 56). Bit-exact through
            plan frame 67; the next seed at 68 is a PROC divergence, and from frame 100 the console
            leaves the modeled regime entirely.**
            - **THE BUG: `JMAEulerToQuat`'s half-angle must be taken on the SIGNED s16.** `quat.
              euler_to_quat` halved the raw u16, so an animated rotation `>= 0x8000` (a negative angle)
              landed **2048 sin-table entries away**. That yields the mathematically EQUIVALENT NEGATED
              quaternion, which is why it hid for months: negation is bit-neutral through `mtx_quat`
              (every element uses components in pairs). But `jmaSinTable`'s two entries are rounded
              independently, so the magnitudes differ by tens of ULP on the cancellation-prone
              components. Truth page: `knowledge/model/euler-quat-signed-half.md`.
            - **WHAT IT COST.** Live at `rollf` joint 0 frame 11 (rotation.x = u16 33160 = s16 -32376)
              the sim's `w` was 47 ULP short, which through `2(yz - wx)` with |x| ~ 1 moved the NECK
              world z 1 ULP, hence the root/neck midpoint `setCollision` uses as the push Co-centre,
              hence the CC push. Fixed in both engines (`quat.py`, `_anmc.pyx` `_half`); native rebuilt.
            - **IT ALSO CLOSED A SEPARATE 16-DAY-OLD GAP**: `test_rest_roll_pose_bitexact` (late
              FRONT_ROLL drawn poses, 1-122 ULP, open since 2026-07-10) XPASSed and its marker is gone.
              The suspects on that marker (thigh lean, m35C4, foot lift) were all wrong. Late roll
              frames are exactly where a joint rotation crosses into negative s16.
            - **METHOD (reusable, and it beat guessing three times running).** Invert the f32 bin
              boundary at the seed frame to BOUND the required change (frame 39 wanted the push z
              +3..+35 ULP); enumerate FP-shape variants against that interval -- **every one moved it 0
              ULP**, which exonerated the push arithmetic and pointed at its INPUTS; then eliminate live,
              term by term (`_notes/tetrapush-node1_chainscan.py`, NEW: the full 3x4 world matrix of
              every NECK_CHAIN joint plus the `m_old_fdata` quat/trans/scale store, diffed joint by
              joint -- "the divergence frame names the bug", applied down the chain instead of down
              time). Joints 1-14's quats were bit-exact and joint 0's was the sign-flipped
              representative; a two-variable ULP brute force over `cos_0`/`sin_0` returned a UNIQUE
              solution (c0 47 ULP away, s0 unchanged) = the fingerprint of a table-INDEX error.
            - **RESULT.** Every previously-open sample (39, 40, 45, 50, 55, 60) went 0-ULP at once, and
              the live sweep past 60 kept it: 61, 62, 65, 66, 67 all bit-exact on BOTH actors. Full
              offline suite green (615).
            - **THE NEXT SEED IS FRAME 68, AND IT IS NOT FP.** The console exits the roll into **proc 9
              (`ATN_ACTOR_MOVE`, the untarget brakeslide)**; the sim goes to **proc 24
              (`MOVE_TURN`)** -- the attention actor-lock is dropping early again, exactly the session-6
              failure one cycle later. Tetra is still 0-ULP at n=80, so the push is not implicated.
              Start at `checkNextMode`'s roll-exit routing + `AttentionLock` lifetime, decomp-first.
            - **AND A SCOPE GAP BEHIND IT, which is the likely real cause of the 113 u miss.** From plan
              frame 100 the console's Tetra reads **stt 4 (FOLLOW)** -- and `FreeRun`'s own
              FOLLOW_ENGAGE_DIST guard fires at that very frame. The stt-3 plow model does not cover
              follow, so the plan's second half is outside the model by construction. Closing it is a
              SCOPE task (model stt-4 follow, or re-solve the plan under an in-regime constraint), NOT
              another rounding hunt. `test_the_out_of_regime_rows_are_flagged_not_silently_expected`
              pins that distinction so a future session cannot mistake it for one.
            - **GATE.** `fixtures/courtyard_node1_console_s56.json` (NEW, LOCKED; n=61..70, 80, 100,
              120, 160, 200) joins the s54/s55 fixtures. `OPEN` = {68,69,70,80,100,120,160,200}; the
              push-symmetry test is REPLACED (that signature is gone) by
              `test_the_first_open_sample_is_a_proc_divergence_not_a_push_one`.
      - [x] **ROUTE (a) PIECE 2 CLOSED -- THE COUPLED Link->ENTRY WALK BIT-CONFIRMS END-TO-END
            (session 52).** From the s51 confirmed homing placement, `walk_to_entry` (s47, Link-only
            reach_precise to `seeds.ENTRY_ROLL_POS`, Tetra frozen above the bar) closes the entry with
            ZERO new code -- the s47 walk + s51 homing compose directly. Off the real 3-cycle chain
            dump (`_notes/tetrapush-walk_chain.py` regenerates it, ~800 s; the RUN half
            `tetrapush-walk_run.py` rebuilds each placement from its cached log and iterates the walk):
            - **node 1 (the best homing node, Tetra pd 0.011 on a genuine coord, Link at rest lead
              -62.9 BEHIND Tetra / lat +51.6 off-line): the walk reaches the entry to `dist 10.42 u`,
              `max_tetra_disp 0.000` (Tetra bit-FROZEN -- untouched), `clean=True`, follow-free, Tetra
              pd after the walk still 0.011.** `confirm_plan` replays the WHOLE state-2 -> chain ->
              brake -> homing -> walk log (**241 frames**) **0-ULP: bit_exact=True, talk_safe=True,
              follow-free**. So from state 2 a single fully-computed input sequence lands Tetra ON a
              genuine seam-clip coord AND stands Link at the final-clip entry, bit-confirmed.
            - **The node SIDE is the discriminator (why node 1 alone):** nodes 0/2/3 also arrive+confirm
              their placement but re-plow Tetra during the walk (node 0 lead +55 = OVERTOOK her; nodes
              2/3 lat -80 = far off-line the wrong side) -- the walk to the UP-HERD entry crosses Tetra.
              Node 1 ends behind-and-beside her, so the walk never crosses her (Tetra 0.000).
            - **The 10.42 u entry residual is a genuine floor** (stable across a dense gain grid +
              min_crawl {0.043,0.03,0.02}): the 2-frame input latency + coast-to-rest granularity, the
              s47 walk floor (~7 u synthetic). FINE because the entry is a reposition target the final
              clip re-solves per (entry,facing) (`ENTRY_ROLL_FACING` is unoptimised -- the clip's own
              turnaround sets it); a sub-unit entry tail is follow-up, not a blocker.
            - **No new gate** (matches the s49-s51 discipline): the real bit-confirm is the scratch run
              (documented), not a unit test (the 800 s chain); the synthetic recipe-physics of
              `walk_to_entry` (rest clean / ebs re-plow) + `homing_place` are already gated. A synthetic
              off-line `lat_off` walk was probed and is clean but only duplicates the s47 rest-clean
              property (it can't reproduce the node-side crossing on the fixed coord). 543 offline pass.
            - **2b is CLOSED end-to-end OFFLINE**; only the out-of-band DTM tier-2 confirm + an optional
              sub-unit entry-precision tail remain. `[[courtyard-tetra-push]]`.
      - [~] **ROUTE (a) PIECE 1: THE OFF-THREAD ARRIVAL CLOSED -- `homing_place` BUILT + GATED
            (session 51).** The s50 handoff's concrete next target -- get Tetra ONTO the thread
            laterally so the placement closes -- is delivered as a gated terminal, `full_herd.
            homing_place`, that corrects the s44 lateral OFFSET the on-line `decel_place` (s50) cannot:
            - **Why decel_place stalled on the real chain (s50):** it herds Tetra straight DOWN the
              line (`lat_drift ~0`), so it needs her already on the thread laterally. The real 3-cycle
              chain endpoint leaves Tetra ~28 u OFF the thread (endpoint pd 74.7 = hypot(69 along, 28
              lat)), and the on-line herd cannot pull her onto it from behind -> it stalled at pd ~41.
            - **The lever, exactly as the s50 handoff named it:** the plow ejects Tetra AWAY from Link's
              exec centre, so approaching from the HIGH-lateral side pushes her TOWARD the line. First
              tried as a fixed lateral BIAS on the on-line glide's aim point -- it corrects only ~15 u
              (a single fixed aim can't null both along and lateral; past bias ~60 it worsens). The
              robust form is HOMING: aim Link each frame at a moving standoff BEHIND Tetra RELATIVE TO
              THE COORD (`Tetra + standoff·unit(Tetra − coord)`), so the push points at the coord and
              corrects along + lateral together, converging as she nears it. Coast-probe to REST each
              frame for the clean frozen placement; sweep standoff + gain.
            - **RESULT (`synthetic_hot_arrival(lat_off=±28, 40)`, the off-thread testbed -- `lat_off`
              new this session, shifts both actors off the thread to reproduce the chain endpoint):**
              `homing_place` lands Tetra pd **< 0.1 u** ON a genuine coord, **freeze_ok** (cf 80), the
              **lateral offset NULLED** (`lat_drift` cancels the seeded ~28 u), `arrival_ok` -- for
              BOTH offset signs. `decel_place` fed the same off-thread arrival stalls at pd ~22-31
              (aok False). CLI `full_herd homing` shows the contrast.
            - Gated `tests/test_full_herd.py::test_homing_place_corrects_an_off_thread_lateral_offset`
              (both signs; synthetic, no bit-confirm -- gates the recipe physics like decel/walk/place;
              17 fast). Land goldens + code hygiene green.
            - **REAL-CHAIN BIT-CONFIRM -- 2b's PLACEMENT HALF CLOSED (session 51).** Ran the real
              3-cycle chain (`_notes/tetrapush-homing_chain.py`, 976 s: reproduces s46 -- 868.3 u/69 f,
              last beam pd 74.7) -> `homing_place` -> `confirm_plan` on each last-beam node. **ALL 4
              nodes land Tetra `arrival_ok` ON a genuine coord AND bit-confirm** (bit_exact + talk-safe):
              node 1 = **Tetra pd 0.011 u** (lat_drift -29.0 = the s44 offset nulled, cf 80, 164 f,
              standoff 70); nodes 0/2/3 pd 0.08/0.24/0.23 (2/3 home in from 171 u lateral). So from
              **state 2** a fully-computed input sequence (chain -> reverse-brake -> homing) lands Tetra
              on a genuine seam-clip coord, **0-ULP bit-confirmed + talk-safe** -- milestone 2b's
              placement half is done on the real run; only the coupled Link->entry navigation remains.
            - **NEXT (route a, piece 2 -- the coupled entry):** from the confirmed placement (node 1:
              Tetra pd 0.011, Link at rest on the far-standoff side, Tetra frozen at cf 80) run
              `walk_to_entry` (Link-only reach_precise to `seeds.ENTRY_ROLL_POS`, above the freeze bar,
              built + gated s47) then `confirm_plan` the FULL state-2 -> chain -> brake -> homing ->
              walk log 0-ULP. Homing leaves Link ~70 u OFF-line on the standoff side (not
              on-line-behind like decel), so CHECK the walk starts in-regime + above the bar from this
              arrival (it may want a short on-line reposition first, or take the homing endpoint
              directly). If it confirms, 2b is CLOSED end-to-end. Iterate on a cached chain dump
              (~798 s), not a re-run. `[[courtyard-tetra-push]]`.
      - [~] **ROUTE (a) PIECE 1 DELIVERED: THE DECELERATING ON-LINE PLACEMENT APPROACH -- BUILT +
            GATED (session 50).** The s49 handoff's concrete next target -- a decelerating,
            on-line-centered approach that lands Tetra on a coord near-rest instead of the hot EBS
            glide that drags her laterally -- is now a gated primitive, `full_herd.decel_place`, that
            INVERTS the s49 failure mode on the synthetic barrier testbed:
            - **The recipe (both phases reuse existing machinery):** (1) **kill the EBS**
              (`_reverse_brake`) -- steer DOWN the herd line at a low deflection, which REVERSES the
              hot backslide, so Link coasts to near-rest UP-herd while the plow stays on the line and
              Tetra freezes with ~0 lateral drift (measured tlat -1.3 u vs a neutral brake's -6 u; the
              separation happens FAR from the coord, not at deep contact); (2) **on-line forward
              glide** (`_glide_to_entry`, the `walk_to_entry` reach_precise machinery) -- from the
              braked rest, proportional-speed-glide FORWARD to an on-line point `back` u behind the
              coord, coasting to a crawl, so the metered on-line plow herds Tetra straight DOWN the
              thread onto the coord; `back` + gain SWEPT (not tuned), `place_on_thread` finishes.
            - **RESULT (synthetic `synthetic_hot_arrival`, the deep-contact hot state the chain
              terminal produces):** across d_short 30/40/55, `decel_place` reaches **arrival_ok**:
              Tetra pd **< 0.13 u** (ON the coord), **lat_drift +0.000** (the s49 lateral drag GONE),
              centre_feet 80 (freeze_ok), Link at rest -- a complete inversion of s49 (whose miss was
              10.85 u LATERAL). The miss is now a clean sub-unit ALONG-line residual, a 1-D tune. The
              raw hot glide fed the same arrival still leaves her pd 1.98-11.9 -- `decel_place` beats
              it strictly.
            - **The barrier framing resolves:** the s49 lever was the ARRIVAL MOMENTUM; the fix is to
              bleed it OFF-line (reverse-brake, far from the coord) then re-approach ON-line at a crawl,
              so the herding push is always on the thread. This is exactly the arrival `arrival_quality`
              gates for and `walk_to_entry` needs.
            - Gated `tests/test_full_herd.py::test_decel_place_beats_the_hot_glide_with_an_on_line_
              near_rest_arrival` (synthetic, no bit-confirm -- gates the recipe physics like the
              walk/place gates; +1 -> 16 fast). CLI `full_herd decel` contrasts the hot glide vs decel.
            - **RAN it on the REAL chain endpoint (822 s) -- the remaining piece is the s44 lateral
              OFFSET, not the s49 drag.** `chain_herd` (reproduces s46: 868.3 u/69 f, last beam pd
              74.7) -> `decel_place` -> `confirm_plan`: the decel reaches only **pd 40.8** (lat_drift
              +0.000, cf 80, arrival_ok False), not the sub-0.13 the on-line synthetic hits. Root cause
              (s44's known geometry): the chain leaves Tetra ~28 u OFF the thread LATERALLY (endpoint pd
              74.7 = hypot(69 along, 28 lat)), and `decel_place` herds her down-line ON-line (lat_drift
              0) but does NOT correct the ABSOLUTE lateral offset -> she freezes at pd ~41 (= hypot(~35
              along, 28 lat)). So `decel_place` SOLVES the s49 lateral DRAG (proven on the on-line
              synthetic) but the real chain ALSO has the s44 lateral OFFSET the decel cannot pull her
              onto from behind.
            - **NEXT (route a, piece 1): get Tetra ONTO the thread laterally, then decel closes it.**
              Cheaper lever first: (1) approach from the HIGH-lateral side -- the plow ejects Tetra AWAY
              from Link's exec centre, so aiming the decel glide so Link approaches from her off-thread
              side gives the push a component pulling her TOWARD the line (s44 noted this); extend
              `decel_place` with a swept lateral bias on the `back` point so the herd corrects the ~28 u
              offset, not just herds along. (2) if too large, rank the CHAIN low-abs-lateral (the
              s44-open route-a item) so Tetra arrives near the thread and the decel is a short on-line
              finish. Then `decel_place` -> `place_on_thread` -> `walk_to_entry` -> `confirm_plan` closes
              2b. Iterate on a cached chain dump (~822 s), not a re-run. `[[courtyard-tetra-push]]`.
      - [~] **ROUTE (a) PIECE 1 RUN + THE GRAZING BARRIER ROOT-CAUSED + THE CLEAN-ARRIVAL RECIPE
            GATED (session 49).** Ran the s48 handoff's directed RUN: regenerated the chain dump
            (reproduces s46 -- 3 cycles, 868.3 u in 69 f, last beam 74.7 u from a coord) and ran
            `terminal_targeting(objective='grazing')` off it, gating on `arrival_quality`. The result
            names the barrier precisely and the recipe to beat it:
            - **The grazing terminal SOLVES the momentum half but is POSITION-limited.** Off the deep
              3-cycle endpoint it reaches `freeze_ok` (centre_feet 81.8) AND receding (approach -8.82),
              bit-confirmed -- but lands Tetra **10.85 u from a coord**, so `arrival_ok=False`. The
              miss is almost purely LATERAL (d_along -2.28, d_lat -10.6; the thread is lat 0..8, along
              937-984).
            - **ROOT CAUSE (frame-by-frame trace of the glide):** the hot -23 EBS glide places Tetra
              ON a coord only at DEEP contact (frame 9: pd 1.98, centre_feet 64.6, approach +12
              closing), then overshoots -- as Link separates to `freeze_ok` (cf 64.6->81.8 over 3
              frames) he DRAGS her ~10 u LATERALLY off the ~5e-4 u-thin thread (lat +4.3->-9.8). The
              deep->freeze_ok separation of a hot, off-center approach IS the lateral drag; from the
              on-coord state NO separation direction (neutral / up-push / ess-down) keeps her within
              pd 9 (all reach lat -9..-15 at the bar).
            - **REJECTED: moving grazing to a WIDE-lateral last cycle** (`grazing_cycle` scratch,
              half_window 0x4000, require_quality=False): WORSE (best pd 136 vs 10.85). The on-line,
              herd-rate-ranked endpoints the chain already finds ARE the best-positioned; a wide
              lateral roll just shoves Tetra off-line. The lever is NOT a wider roll.
            - **THE CLEAN-ARRIVAL RECIPE (validated + gated): `full_herd.place_on_thread`.** From a
              near-REST arrival behind the coord (Link lateral-matched, speedF ~0, centre_feet just
              below the bar) a single gentle down-line crawl-push ejects Tetra ALONG the line, so she
              freezes ON-thread: **pd < 1, ~0 lateral drift, arrival_ok** (measured pd 0.40-0.78 across
              cf 74/76/78). So the barrier is the ARRIVAL MOMENTUM, not the lateral position -- even
              an off-center REST arrival places clean (the -23 glide is the killer). Gated
              `tests/test_full_herd.py::test_place_on_thread_freezes_tetra_on_the_thread_from_an_online_
              rest_arrival` (synthetic, no bit-confirm; gates the freeze/placement physics + recipe);
              CLI `full_herd place`.
            - **NEXT (route a, piece 1, the concrete target):** the chain/terminal must deliver Link
              **on-line-behind Tetra + near-rest** before the placing push -- a DECELERATING,
              lateral-centered approach (kill the EBS into a crawl as Tetra reaches the coord, the
              `walk_to_entry` deceleration machinery aimed at the coord instead of the entry), NOT the
              sustained EBS glide. Then `place_on_thread` freezes her on-thread and `walk_to_entry`
              closes the coupled entry. `[[courtyard-tetra-push]]`.
      - [~] **THE CHEAP ARRIVAL GATE + THE GRAZING-RANKED TERMINAL BUILT + GATED (session 48).**
            Route a, piece 1's machinery -- the rank change the s47 handoff said to design + gate
            BEFORE regenerating the 800 s chain dump. Both are cheap prediction (no walk, no chain),
            gated offline:
            - **`full_herd.arrival_quality` = the two-halves gate**: from a placed state it reports
              POSITION (`placement_dist`, `centre_feet`, `freeze_ok`) AND MOMENTUM (`approach_rate` =
              Link's ground-velocity component toward Tetra, via `_link_velocity`/`_approach_rate`;
              `receding`), and the combined `arrival_ok` (`freeze_ok` AND on-coord AND
              `approach_rate <= a few u/f`). The session-47 finding as a SCALAR predictor: at the SAME
              freeze_ok position the clean rest arrival reads approach **-0.00 u/f** (arrival_ok) and
              the hot EBS **+25.56 u/f** (rejected) -- agreeing with `walk_to_entry`'s measured plow
              (0.000 vs 58.9 u) WITHOUT running it. So a grazing-chain candidate is gated on it before
              paying the walk / the 800 s re-run. `approach_tol` is a "few u/f" (the split is 0 vs
              +25.6, a wide margin), not a tuned constant (`[[no-overtuned-constants]]`).
            - **`terminal_targeting(objective='grazing')` = the re-ranked terminal**: the s44 default
              `'placement'` (nearest coord) is byte-for-byte unchanged (`score == dist`); `'grazing'`
              adds a `deficit` (below-the-bar) + closing-`approach_rate` penalty (`_terminal_score`),
              so the endpoint it seeks is on-thread AND freeze_ok AND receding. Measured off cheap
              cycle-1 nodes: placement mode lands cf 61.2 / deficit 18.8 / approach +23.5 (deep,
              closing) while grazing lands cf 89.1 / deficit 0.0 / approach **-10.8** (freeze_ok,
              receding), bit-confirmed. This is the rank the re-ranked CHAIN will inherit.
            - Gated `tests/test_full_herd.py` (+2 -> 14 fast): `test_arrival_quality_gates_position_
              and_momentum` (the scalar predictor agrees with the walk) + `test_terminal_grazing_
              objective_seeks_freeze_ok_without_breaking_placement_mode` (placement rank preserved,
              grazing seeks freeze_ok/receding, bit-confirms). CLI adds `arrivals` (the gate demo);
              `endgame` now prints the ARRIVAL GATE (both halves) above the separation barrier.
            - **NEXT (route a, piece 1, the run): regenerate the chain dump (`run_chain_dump.py`-style
              scratch) and run `chain_herd` -> `terminal_targeting(objective='grazing')`, gating
              candidates on `arrival_quality(...).arrival_ok`.** The rank + gate are now designed +
              gated, so the chain re-run is aimed. If the terminal alone cannot graze from the 3-cycle
              endpoint (s46's expectation), push the grazing term earlier -- rank the last CHAIN cycle
              by `arrival_quality`, not just the terminal. `[[courtyard-tetra-push]]`.
      - [~] **The native-fleet reposition SEARCH -- BUILT + GATED (session 38); the on-line-roll
            blocker is now root-caused, not just observed.** `harness/tetrapush/native_search.py` is
            the search the session-37 handoff called for: a beam BFS whose frontier is native
            `FreeRun` nodes expanded a frame at a time through `CourtyardFleet.run_par` (`batch_step`),
            pruned off-line/past-Tetra (`reposition.HerdLine`) + talk-unsafe + out-of-regime, deduped
            by a quantized state tag, ranked by down-herd progress; a winning plan is bit-confirmed on
            a fresh Python-stepped `FreeRun`. Gated `tests/test_native_search.py` (3, all 0-ULP /
            structural: the fleet-frontier readout reproduces a native FreeRun rollout bit-for-bit, a
            batch step == stepping each clone alone, a tiny search prunes to an on-line waypoint +
            bit-confirms). **The search RUNS end-to-end and reveals the stripped sim CANNOT sustain an
            on-line +26-roll pursuit: every roll OVERSHOOTS (Link overtakes Tetra) and is pruned; the
            frontier instead exploits the continuous glide-push (~12 u/f on-line for ~10 frames, then
            STALLS at along ~148 as Link drifts laterally to +65).** ROOT CAUSE PINNED (inject the full
            camera sim's own csangle to remove it as a variable -> the ONLY stripped-vs-full difference
            is the **roll-entry facing, -102 BAM**: full 35316 vs stripped 35214). That -102 BAM is the
            proc-7 re-aim to Tetra's animated **eyePos** (leads her feet 16-26 u) which the stripped
            config replaces with her feet; over the 16-frame locked roll it compounds into Tetra
            diverging 69 u by f18 -> overshoot instead of the full sim's pursuit (lead recovers -85 ->
            -40). Supersedes the vague s34 "facing differs stripped" note with the exact BAM +
            mechanism. **The s38 NEXT ("port the zl1 eye-aim into native, then re-run the SAME beam")
            was SUPERSEDED by session 39** -- running the reposition beam in the full Python sim
            (eye-aim correct) found the beam STILL finds zero rolls (it is lured into the same
            glide-drift local optimum), so the eye-aim port alone would not have found the chain.
            The missing piece is a REALIZABLE, roll-seeking search structure, not (only) eye-aim.
            See the s39 box below.
      - [~] **The REALIZABLE camera-steered reposition -- DESIGN VALIDATED (session 39; Dereck's live
            steer). The search structure, not eye-aim/fleet-speed, is the real blocker; the design that
            fixes it is validated primitive-by-primitive, the branching search is the build.**
            Running the reposition beam in the FULL Python `FreeRun` (0-ULP `land_cam` + `zl1` wired,
            so the proc-7/9 re-aim uses eyePos -- correct pursuit facing) reframed everything: (a) the
            greedy along-score beam finds ZERO rolls (glide-drift local optimum, the same stall the
            s38 native beam hit) -- so porting eye-aim into native and re-running that beam would NOT
            have found the chain; (b) csangle is NOT a free per-frame lever -- the camera yaw moves at
            a BOUNDED rate via the C-stick (neutral substickX FREEZES it; full stick ~+-460..530
            BAM/frame; ~+-8000 BAM reachable in a 16-frame roll), so an injected-csangle plan is not
            realizable. Dereck's design makes the search BOTH correct and tractable:
            **roll = a zero-branch camera-steering segment** (facing is locked, so spend the free
            substick pre-rotating the camera to the csangle the NEXT turnaround needs; the steered
            untarget then lands Link facing AWAY = talk-safe, arming the +18 flip -> a talk-safe +26
            roll), **branch aggressively at the junctions** (roll FACING is a free variable -- any
            halfword, since facing = decode(stick, csangle) and csangle is C-stick-controllable -- so
            PREDICT the plow-into-Tetra facing and fan around it; branch the main-stick position + the
            release timing). THREE coupled per-cycle controls pinned: **camera -> facing/talk-safety,
            main-stick -> on-line POSITION (the camera CANNOT move position -- armed-state lat/lead are
            invariant across the reachable target_cs), release-timing -> the -25.727-vs-on-line
            tradeoff.** SELF-STABILIZATION (Dereck; confirmed by the ground-truth recording): an
            on-line plow-roll KEEPS Link on-line (the recorded 2-roll window: worst_lead -40.3,
            on_line=True), so the off-line landing is a ONE-TIME bootstrap artifact, not an intrinsic
            property of the cycle -- the search optimizes per-cycle knobs WITHIN the on-line
            self-stabilizing regime (off-line nodes prune as non-self-sustaining), which bounds the
            branching. Primitives BUILT + GATED: `harness/tetrapush/steered_reposition.py` (camera
            authority; steer-during-roll; armed-state geometry; the self-stab evidence), gated
            `tests/test_steered_reposition.py` (3: neutral freezes / full stick steers bounded; camera
            sets facing not position; on-line roll self-stabilises). **NEXT: build the per-cycle
            branching search** -- bootstrap on-line once (first-roll angle/release, or a one-time
            main-stick slide), then chain the self-consistent camera-steer -> turnaround -> plow-roll
            cycle, branching (target_cs = next roll facing) x (main-stick position) x (release), pruning
            off-line/talk-unsafe/follow, ranked frame-minimal. Bit-confirm any winner on the full
            Python `FreeRun` (realizable = C-stick-driven csangle, no injection).
      - [~] **THE LINK-ONLY WALK PLANNER BUILT + GATED, AND THE BARRIER'S SECOND HALF FOUND:
            ARRIVAL MOMENTUM, NOT JUST POSITION (session 47).** Milestone-2b piece 2 (the s46 "next
            step") is DELIVERED as a maneuver, and building it surfaced a correction to the s46 framing.
            All offline (no chain needed -- the walk is develop-able against a synthetic frozen arrival):
            - **`full_herd.walk_to_entry` = the Link-only WALK to `seeds.ENTRY_ROLL_POS`** above the
              bar (Tetra frozen). A `reach_precise` glide on the coupled `FreeRun` (proportional-speed
              into a crawl, controller-gain SWEPT, per-frame clone+coast to the min resting gap),
              pruned by the FOLLOW regime, Tetra displacement MEASURED (not assumed). Replaces the
              inert push-fan of `entry_targeting` above the bar (which stays as the in-band guard).
              Reaches the entry to **~7 u clean** from a near-rest arrival (facing is the clip
              turnaround's, not optimised). CLI `full_herd walk`.
            - **THE MOMENTUM FINDING (corrects s46): `freeze_ok` (centre_feet >= 80) is POSITIONAL and
              necessary but NOT sufficient.** At the SAME freeze_ok position a REST arrival walks clean
              (Tetra bit-frozen, 0.000 u) but a hot down-herd EBS arrival re-plows her **~59 u** -- the
              ~5 frames it takes to bleed a -25.7 momentum off drift Link back below the bar, and a
              turnaround does NOT rescue it (the snap preserves the -25.7, still ~44 u of plow). So
              route a's grazing chain must deliver Link **NEAR-REST / receding up-herd**, not merely at
              centre_feet >= 80. `walk_to_entry` reports `max_tetra_disp`/`clean` so a hot arrival is
              flagged, never silently plowed.
            - **`full_herd.synthetic_frozen_arrival`** mints the above-the-bar frozen placement (real
              Link state, relocate Tetra onto a coord + Link up-herd at target centre_feet; `momentum`
              = 'rest' clean / 'ebs' hostile) for developing/gating 2b BEFORE the grazing chain exists.
              Not chain-reachable, so no bit-confirm -- it exercises the walk's regime/freeze properties.
            - Gated `tests/test_full_herd.py::test_walk_to_entry_is_clean_from_rest_and_flags_a_hot_arrival`
              (same freeze_ok position, rest walks clean + reaches the entry, ebs flagged unclean).
              **538 offline pass.** `endgame` CLI now routes to the walk above the bar / the guard below.
            - **NEXT (route a, piece 1, unchanged but now sharper): rank the CHAIN to land Tetra at
              centre_feet >= 80 AND arrive near-rest / receding up-herd** (the momentum requirement is
              the new constraint). Gate cheap via `separation_scan(...).freeze_ok` AND a low arrival
              speed BEFORE paying the 800 s chain; then `walk_to_entry` closes the coupled entry.
              `[[courtyard-tetra-push]]`.
      - [~] **THE CLEAN-SEPARATION BAR MEASURED DECOMP-EXACT + 2b RE-REFRAMED as a Link-ONLY
            navigation above it (session 46).** Route (a) chosen. The s45 barrier was quantified into
            an un-tuned target and the fork sharpened. All recomputed live-faithful off the s45 chain
            dump (no 800 s re-run; scratch `graze_explore`/`window_map`/`navigate_probe`):
            - **THE BAR: the plow ejects Tetra by `CO_RADII_BAR - centre_feet` (halved by the 50/50
              `cc_push_pair` split), so she is FROZEN on her coord exactly when Link's animated exec
              Co-centre sits >= `LINK_CO_R + TETRA_CO_R` = 80 u from her feet.** Decomp-exact, no
              tuning. Measured: at centre_feet 64.6 -> 82 the neutral-step ejection falls 7.7 -> 0.0000 u,
              `== (80 - centre_feet)/2` every sample. The s44 placement lands at **centre_feet 64.6 --
              15.4 u below the bar** (feet dist 47.5; the centre leads the feet ~17 u), so it is the
              deep-contact barrier. `separation_scan` now reports `centre_feet`/`co_radii_bar`/
              `deficit`/`freeze_ok`; gated decomp-exact by `test_freeze_bar_is_the_co_radii_sum`.
            - **THE TERMINAL CANNOT GRAZE FROM THE s45 ENDPOINT** (3 frontiers -- nearest-coord,
              on-line-first, graze -- all reach the SAME single in-band state at centre_feet 64.6):
              Tetra arrives 74.7 u short at lateral +36, so the terminal must push her PERPENDICULAR
              into the thin thread, which is inherently deep. So the grazing term belongs on the
              CHAIN (deliver Tetra on-thread within a hair, so the placing push is one light touch at
              centre_feet ~80), NOT on the terminal rank -- that would be inert here.
            - **ABOVE THE BAR, 2b IS A LINK-ONLY NAVIGATION** (Tetra frozen, untouched). Proven: from
              a synthetic centre_feet-90 placement Tetra holds (pd <= 2.9) while Link moves freely,
              but `entry_targeting`'s down-herd PUSH fan STALLS -- Link leaves in a hot EBS backslide
              (speedF ~-23) whose momentum carries him AWAY from the up-herd entry faster than a
              push-bearing stick can turn him (greedy nav GROWS the entry gap). So the reposition tool
              is a WALK/EBS planner (`plan_land`), not the push fan; `entry_targeting` stays as the
              in-band GUARD (proves Tetra holds). `entry_targeting` docstring updated to say so.
            - **NEXT (route a, two coupled pieces):** (1) rank the CHAIN's last cycle/terminal to land
              Tetra on a coord at centre_feet >= 80 (grazing) -- the precise, gated target is now known,
              so a re-ranked chain run is aimed; gate it by `separation_scan(...).freeze_ok` BEFORE
              paying the 800 s chain. (2) build the Link-only WALK planner to the entry (Tetra frozen,
              dist held in 80..230), replacing the inert push-fan in `entry_targeting`. `[[courtyard-tetra-push]]`.
      - [~] **MILESTONE 2b REFRAMED + THE SEPARATION BARRIER MEASURED; the reposition machinery is
            built + gated but INERT until a grazing-arrival chain feeds it (session 45).** The
            coupled entry is not a small correction on the s44 endpoint -- it is structural, and the
            geometry names why (all recomputed live, no chain needed -- scratch `geom_entry`):
            - **The final clip is the FOLLOW-enabled turnaround roll** (`[[turnaround-clip-followenabled]]`,
              slot 7), NOT the glitched-no-follow push-aside. So Tetra FOLLOWS past 230 u -- but the
              entry sits only **~201 u from the coord (< the 230 u follow threshold)**, so Link CAN
              stand at the entry with Tetra held.
            - **The entry is UP-HERD of and OFF the herd line** (`seeds.ENTRY_ROLL_POS` = along 781 /
              lateral 73; the 288 coords are along 937-984 / lateral -2..8). The down-herd plow leaves
              Link BEHIND + on-line; the entry is back up-herd + 73 u lateral. So route (a) "keep Tetra
              on-line" alone does NOT reach the entry -- 2b is a genuine post-placement REPOSITION of
              Link (~174 u back + 73 u lateral). The clip ROLL itself then plows Tetra along its
              ~200 u path, so the coupled target is: at the clip-roll entry FRAME, Link at the entry
              AND Tetra on a coord.
            - **THE BARRIER (`separation_scan`, measured on the real s44 endpoint):** `terminal_targeting`
              lands Tetra on a coord ONLY at DEEP contact (dist(Link,Tetra) = **47.5 u**, depth ~32),
              because the genuine coords are a thin thread (~46 u long, ~5e-4 u perpendicular, s26)
              the plow can only reach by pushing INTO it. From there EVERY one-frame separation step
              ejects Tetra to **>= 4.2 u off a coord** (off the thread), AND the placed state is
              already the glide's entry-distance MINIMUM (159.8 u; the entry is up-herd, opposite the
              glide), so no forward step reduces the gap either. `clean_separation = False`. So
              "place, then hold Tetra and reposition Link" is BLOCKED at the seam.
            - **THE FIX (aimed, not built): a GRAZING arrival.** The chain must be ranked to reach the
              band on-line with Link near dist 80 and DECELERATING up-herd (route a, but for
              separability, not just precision), so the placing push is the LAST significant one and
              Link recedes to the entry without shoving Tetra off the thread. Alternatively, RE-SOLVE
              the clip (the `rollstab/turnaround` Tetra-thread solver relocates per (entry,facing)) at
              the herd's NATURAL Link endpoint instead of forcing the fixed entry -- the two are a
              genuine fork for the next session (see the handoff).
            Built + gated (`tests/test_full_herd.py`, 10 fast): `full_herd.separation_scan` (the
            barrier metric), `entry_targeting` (the reposition beam -- regime + band pruned, ranked
            Link->entry, bit-confirms its whole state-2->placement->reposition log), wired into
            `full_herd endgame`. `[[courtyard-tetra-push]]`.
      - [~] **THE PLACEMENT ENDGAME LANDS TETRA ON A GENUINE COORD -- 1.98 u from coord idx241,
            bit-confirmed, in 78 frames from state 2 (session 44).** The 3-cycle chain leaves Tetra
            69 u short down-herd AND 28 u off-line laterally (`endgame_geom`: the coords sit ON the
            herd line at along 937-984 / lateral -2..8, the chain drifts her to along 868 / lateral
            36). A FOURTH full roll overshoots (each cycle herds ~280 u, only ~99 remain), so the
            terminal is a **PLACEMENT-RANKED GLIDE**, not another u/frame cycle: `terminal_targeting`
            is a per-frame beam ranked by the CURRENT Tetra-to-nearest-coord distance, tracking the
            global closest state reached at ANY frame (a glide sweeps THROUGH the band). Two findings
            made it land IN the band (both `[[no-overtuned-constants]]`-clean):
            - **The prune is REGIME-ONLY, not the pursuit box.** The deepest approach happens AFTER
              Link overtakes Tetra and leaves the box (measured `probe_glide`: a plain (111,111)
              glide off the endpoint carries her to 6.4 u, min at f8 when Link is lead +18). The
              pursuit box keeps a posture for the NEXT roll; the terminal has none, so the only hard
              constraint is the stt-3 plow regime (no follow) + talk-safety (no A in a glide).
            - **The alphabet needs MID magnitudes** (`_terminal_alphabet`): a full-circle push-bearing
              fan at msd {0.08, 0.2, 0.35, 0.5, 0.7, 1.0}. The junction alphabet (ESS msd<=0.10 + a
              full-mag aim fan) has a GAP at the moderate down-herd sticks that give the fine plow
              control; adding the mid-mags took the terminal from 10.4 u to **1.98 u** (Tetra to
              along 956 / lat 4.3, INSIDE the tabulated band -- the 1.98 u is distance to the nearest
              of 288 dense samples, not to the clippable region she is already in).
            The winner replays 0-ULP on a fresh `FreeRun` (`confirm_plan`: bit_exact, talk_safe, in
            regime). Gated `tests/test_full_herd.py` (`test_endgame_report_scores_both_halves...`,
            `test_terminal_targeting_reduces_placement_distance_and_bit_confirms`).
            **THE OPEN HALF (milestone 2b, the COUPLED entry): `endgame_report` measures Link ends
            159.8 u / -22403 BAM from the final-clip entry** (`seeds.ENTRY_ROLL_POS/FACING`, the
            slot-7 setup the coord list is valid for). The herd delivers Tetra onto a coord but leaves
            Link nowhere near the entry -- reconciling the two is the joint solve. Two routes to weigh
            next session: (a) rank the WHOLE chain to keep Tetra ON-LINE (low absolute lateral) so she
            lands in the band with far less terminal correction AND Link nearer the line; or (b) treat
            the final clip as a SEPARATE reposition after the herd (does Tetra hold the coord while
            Link walks to the entry -- follow vs glitched-no-follow, `[[tetra-glitched-nofollow]]` vs
            `[[turnaround-clip-followenabled]]`). Reproduce: `full_herd endgame` (chain ~800 s +
            terminal ~28 s).
      - [~] **THE N-CYCLE CHAIN RUNS: 3 cycles, 868.3 u of the 967.5 u herd in 69 frames,
            bit-confirmed -- plus a REAL SEARCH BUG fixed underneath it (session 43).**
            `harness/tetrapush/full_herd.py`
            generalizes s42's junction+roll unit to N cycles, every roll sweeping its OWN derived
            `target_cs` grid (cycle 2 never needed one -- nothing followed it). Gated
            `tests/test_full_herd.py` (6 fast + 1 slow). What this session established:
            - **THE CLONE BUG -- `FreeRun`/`LandState` branches were NOT independent, and every
              beam search in this harness rested on the assumption that they were.**
              `LandState.clone` did `__dict__.update` and then re-cloned only `_inbuf`/`_cam`/
              `_gnd`/`_foot`/`_core`; the mutable **`AttentionLock` was shared by reference**, as
              was `visited`. Since that machine decides whether a roll exits into proc 9 or proc 6,
              a sibling branch rewrote its parent's lock state and the corruption PERSISTED:
              replaying one junction from a clone of a fixed base gave facing 16138, then 34819
              after 25 unrelated sibling rollouts, while a fresh base still gave 16138. Fixed by
              `AttentionLock.clone` + copying `visited` (`tww_sim/land/attention.py`,
              `tww_sim/land/state.py`); gated 0-ULP by
              `test_clone_is_independent_of_sibling_branches`. **The s42 12.862 result SURVIVES**
              (it was bit-confirmed on a fresh `FreeRun`, so it never depended on clone state --
              the slow s42 gate still clears the bar after the fix). Findings measured *before*
              the fix are not trustworthy: one such reading is retracted below.
            - **SEPARABILITY: inside a roll, `target_cs` moves only the camera** -- Tetra's
              trajectory is bit-identical every frame under any camera target, as are the roll's
              speedF and locked facing; nothing diverges before the exit. This is the C-stick
              counterpart of s41's main-stick inertness, and it is what makes an N-cycle search
              affordable: a cycle factors into an aim sweep (frozen camera) plus a much cheaper
              camera sweep instead of the |aim| x |tcs| cross product. Applying it to cycle 1 cut
              **159 s -> 10 s for the identical 13.147 u/f best**. Gated `target_cs_is_exit_only`.
            - **THE PURSUIT BOX** (`pursuit_box`, derived not tuned): over his whole window the
              human holds lead -40..-85 u, |lat| <= 12 u, and bearing-to-Tetra within ~14 deg of the
              herd axis. Outside it a roll cannot reach her at all -- from a lat +43 / lead -17
              endpoint, ZERO of 95 full-circle aims survives the on-line prune. Containment-gated
              (`human_in_box`: he is inside on every frame).
            - **THE ENDPOINT KEEP MUST BE ROLLABILITY, NOT FLATNESS** (`roll_probe`) -- the session's
              main search lesson, and the cause of four separate "hundreds of endpoints, zero
              surviving rolls" stalls. Ranking junction endpoints by |lat| (or fewest frames)
              selects states every roll aim dies from; measured on one cycle-1 node, **32 of 400
              endpoints were rollable and none were among the flattest** (they sat at |lat| ~17).
            - **The junction is now a per-frame BEAM** (`junction_beam`: the atom is one frame's
              (stick, L), the s41 "the atom is the byte pair" lesson one level up), which returns
              **432** gate-passing in-box endpoints where `junction_variants` returns **7**, at the
              same best flatness. The win is DIVERSITY, which is what a razor-thin roll-survival
              stage needs. **RETRACTED** (measured under the clone bug): "the single-stick family
              cannot express the reposition at all" -- it reaches the same min |lat| 7.26.
              Also fixed: ranking the beam frontier on |lat| is myopic in the wrong direction (the
              flattest states are the ones still facing Tetra, which can never arm), so a beam of
              16 found ZERO endpoints where a beam of 12 found 162 -- a wider beam finding less is
              the tell. The frontier now ranks by CONE DEFICIT first (`_frontier_score`).
            - **THE RESULT (`full_herd plan cycles=3`, 662 s, every stage bit-confirmed on a fresh
              `FreeRun` by `confirm_plan` -- talk-safe, on-line, in the stt-3 plow regime throughout):**

              | cycle | frames | herd | u/frame | remaining |
              |-------|--------|------|---------|-----------|
              | 1 | 21 | 275.8 | 13.135 | 691.7 |
              | 2 | 46 | 590.9 | **12.845** (clears the 12.758 bar) | 376.7 |
              | 3 | 69 | 868.3 | 12.584 | **99.3** |

              So the chain reaches **90 % of the way to the cluster** and leaves Tetra at
              (-1578.792, -835.603), **74.7 u from genuine coord idx 287** (-1627.424, -892.340).
              Note the CLI labels cycle 3's 12.584 "below the human's 12.758", which is
              apples-to-oranges: his recording is only 2 rolls / 45 frames, so there is no recorded
              3-roll rate to compare against -- the honest statement is that the plan's first 46
              frames clear the bar and the third cycle costs ~0.26 u/frame of average rate.
              Off the recorded human's OWN cycle-1 exit the same unit chains at **12.833** over 46
              frames, independently reproducing s42-class quality from a different entry.
              **NEXT: the placement endgame** -- close the last ~99 u and land Tetra ON a genuine
              coord with the matching final roll entry (the coupled objective; `placement_report`
              scores the nearest coord, `seeds.ENTRY_ROLL_POS/FACING` carry the entry the list is
              valid for). Watch the stt-3 regime bound as the herd nears the corner.
      - [x] **THE 2-ROLL BAR IS CLEARED -- 12.862 u/frame vs the human's 12.758, from state 2, in
            the full realizable sim (session 42).** The winning chain (46 frames, 591.6 u herded,
            talk-safe, on-line the whole way, lead -57.7 / lat +7.8 at exit, bit-confirmed by a
            fresh replay of its own input log): cycle 1 = the 13.15 entry with the roll-1 C-stick
            slewed to **target_cs 38812** and the (5,8) L pulse -> a **6-frame ESS-swing junction**
            (the human-shaped family: low-magnitude swing dragging the facing chase out of the talk
            cone, L re-target, 1-frame full-stick pre-aim) -> **roll 2 at the full 26** (aim 36843).
            Seven distinct chains beat or tie the bar. What it took, each found by measurement:
            - **The junction is a generic PHASE LIST** (`run_junction`/`_fit_phases`), swept as two
              families (`junction_variants`): the 1-frame ESS turnaround x nflip, and the
              human-shaped swing over `ess_fan` -- the byte grid's **64 low-magnitude angles** (an
              8-direction ESS compass is the s40 aim-fan narrowing all over again; with it the glide
              veers to lat +34 and every roll-2 overshoots, s38-style).
            - **The ARMING gate** (`junction_gates`): a 1-frame probe must show the proc-7 flip has
              FIRED (speedF >= +17) at the endpoint or the roll-A only ever fires the weak +5 --
              delay-1 means L two frames back + toward-Tetra stick one frame back (the human's own
              f26/f27 pattern). Without the gate, jf-ranked keeps fill with flip-starved endpoints.
            - **The endpoint dedup must include the PENDING delay-1 input**: two junctions can share
              a physics state and differ only in whether the flip fires at the A press.
            - **THE razor knob: cycle-1's `target_cs` sets the post-roll EBS TRAVEL** (the glide
              chases `cs + 0x8000`). The s42 bisect (transplanting the human's f21 fields into the
              nearest search exit) showed a **~550-BAM travel error kills every junction** while
              csangle-at-junction alone changes nothing; the viable band is ~+-300 BAM, so the
              target_cs sweep is a **fine 128-BAM grid over the entry csangle +- 1536** (the
              camera's ~460-530 BAM/frame slew authority over the roll's first frames -- derived
              bounds). The controlled experiment that localized it: from the human's OWN f21 state
              the junction families chain at **12.820** (his continuation runs 12.413 for cycle 2),
              so the machinery was adequate and only the entry state was wrong.
            **Fidelity, whole-window:** `reproduces_recorded_chain` -- the chain generators
            (junction phase lists + `roll_stream` at fitted knobs with FAN aim bytes) emit the
            human's ENTIRE f1..f44 and the replay matches the raw DTM **0-ULP** every frame.
            Gated `tests/test_two_roll.py` (10 fast + 1 slow: the budgeted chain search finds a
            >12.758 winner and `confirm_chain` bit-confirms it). **NEXT: extend the chain to the
            full herd** -- ~3 cycles to the genuine-coord cluster (the from-here junction+roll unit
            now exists and beats the human's cadence), then the placement endgame (land Tetra on a
            genuine `tetra_placements` coord with the matching final roll entry).**
      - [x] **THE S40 BLOCKER IS CLOSED -- the roll segment now reproduces the human 0-ULP, and the
            search space PROVABLY CONTAINS him (session 41; Dereck's containment steer).**
            The cause was never the in-roll stick stream (the s40 reading below is **overturned**);
            it was **aim GENERATION**, in two compounding ways, both found by per-frame diff:
            - **`stick_for_bearing` cannot express most aims.** Its image is only the MAXIMAL-RADIUS
              (octagon-boundary) byte pairs. The human's own A-press pair `(181,236)` is an INTERIOR
              pair -- identical decoded angle **28732** and a saturated `mStickDistance` 1.0, so
              physically equivalent, but simply not in that image. `roll_facing_fan` deduping by
              those emitted BYTES therefore reached **544 of the 2280** distinct aims the byte grid
              actually realizes: the fan did not contain the human.
            - **The aim was built at the LIVE csangle**, but a delivered stick is acted the NEXT
              frame against the csangle committed then -- so every commanded facing landed one frame
              of camera slew off (**76 BAM** at the state-2 entry: world target 35392 -> achieved
              35316). s40 read that offset as a physics divergence.
            **The structural fix: the fan's atom is the stick BYTE PAIR, not a world bearing.**
            `reachable_stick_fan` enumerates the full 256x256 grid deduped by DECODED ANGLE (which is
            csangle-INDEPENDENT); the world facing a member achieves is
            `decoded + 0x8000 + csangle_at_act`, read back off the run. Containment is then true by
            construction. **`contains_human` gates it** (CLI `two_roll contain`): every recorded aim
            is a fan member (**0 missing of 7032**), and both recorded roll segments are emittable by
            `roll_stream` -- which needed one genuine widening the check itself found, a **third
            stick phase**: the human moves his stick again when the L pulse ENDS (cycle 2
            `(128,110) -> (111,111)`; cycle 1 does not), so the knobs are
            `hold` x `a_hold` x `l_window` x `post_l` x `post`.
            **FIDELITY, 0-ULP:** `reproduces_recorded_roll` replays to the human's own entry, then
            drives the GENERATED stream (fan aim bytes `(154,170)`/`(151,172)` -- **not** his
            `(181,236)`/`(172,243)`, same decoded angle) and reproduces **both** recorded rolls
            bit-exactly, both actors' positions + facing, every frame to the exit.
            **The main stick is INERT inside a FRONT_ROLL -- MEASURED**
            (`roll_is_stick_inert`): pegging the mid-roll stick to `(255,128)`, `(0,128)`,
            `(128,255)`, `(128,0)`, `(255,255)`, `(1,1)` or the aim itself all reproduce the recorded
            roll **0-ULP**. So **the s39 "a roll is a zero-branch segment" premise is RESTORED** and
            s40's overturn of it was an artifact of the aim bug. The roll's live channels are only
            the mid-roll **L pulse** (the untarget tier) and the **C-stick slew** (the camera /
            instant-turnaround setup, which Dereck wants kept as a supported control).
            With the fan fixed, `cycle1_candidates` now yields on-line cycle-1 survivors at
            **13.15 u/frame** vs the human's 12.758 (`two_roll fan window=2000`). Cycle 1 alone is
            a transient; the sustained 2-roll bar was met in session 42 (box above).
            Gated `tests/test_two_roll.py` (7: fan-vs-`stick_for_bearing` strict-subset, fan members
            decode to their own angle, containment, the fitted knobs are the human's real pattern,
            0-ULP roll reproduction x2, stick inertness). 523 offline pass.
      - [~] **THE HERD-RATE CEILING -- MEASURED (session 40); the objective is re-framed. Plus the
            2-roll proof harness, and the in-roll stick stream named as the live blocker
            (that blocker diagnosis is OVERTURNED by session 41 -- see the box above).**
            **The push rate is a pure SPLIT of Link's speed.** Both actors eject the full Co overlap
            depth, so on a contact frame Link advances `|speedF| - e` down-herd and Tetra advances
            `e`; a sustained push is the steady state `e == |speedF|/2`. Measured on the recorded
            window (`steered_search.push_ceiling`, CLI `ceiling`): mean Link down-herd move
            **12.627 u/f**, mean Tetra **12.761 u/f**, **sum 25.388 == mean |speedF|**. So with
            `_roll_init` capping speed at 26 the ceiling is **13.0 u/frame**, and the recorded human
            already runs at **12.76 = 98.2%** of it, in contact **95%** of frames at push alignment
            **0.996**. Consequences, and they overturn the framing every session since s31 worked
            under: **a ROLL IS NOT PRIVILEGED** (the -25.7 backslide pushes exactly as hard as the
            +26 roll), so the s38/s39 beams "finding zero rolls" were reporting a real property, not
            a search bug; and **no reposition can pay for itself** (any out-of-contact or
            reduced-speed frame is a direct unrecoverable loss). Frame-minimality on the push proper
            therefore reduces to maximizing the sum of |speedF| subject to contact + on-line, and
            the whole remaining prize is **~1.8% (~1.4 frames per 75)**. The only lever that breaks
            the cap is a mechanic moving Link faster than 26 (e.g. the roll-stab CUT lunge's 23.22 u
            root translate, `[[tetra-push-model]]`).
            **Dereck's bar for the next increment (s40, live):** do not chase an 80-frame plan --
            **chain TWO rolls above the human's 12.758 u/frame from state 2**, sweeping the first
            roll over every reachable halfword facing, aggressively pruned. `two_roll.py` is that
            harness (`human_baseline`, `roll_facing_fan` = **312 reachable facings within +-8192
            BAM**, deduped by ACHIEVED stick bytes; `roll_segment`, `turnaround_and_flip`,
            `cycle1_candidates`). **The bar was met in session 42 (top box).** Two bugs were found and fixed by
            measurement on the way: the **delay-1 A-press** (`nflip=2` delivers A a frame late, so
            the flip has decayed and the roll fires **+22.235** instead of +26 -- `nflip=1` is the
            correct pairing, verified +26.0 exactly), and the fan being nominal rather than reachable.
            **The s40 blocker reading -- "the in-roll STICK STREAM steers the roll" -- is WRONG and
            was closed in session 41 (box above).** The +88 u lateral divergence it measured came
            from generating the aim through `stick_for_bearing` at the live csangle, not from
            in-roll steering; the main stick is provably inert inside a roll. The s40 fan figure
            ("312 reachable facings, deduped by ACHIEVED stick bytes") is likewise superseded --
            that dedup key was the narrowing.
            (Note `[[tetra-clip-solved-live]]` already recorded "NEUTRAL roll stick (not UP)" as a
            delivery truth; s40 re-derived it the hard way -- read that memory before authoring
            roll inputs.)
      - [x] **The f1 seed-frame boundary MATTERS -- CHARACTERIZED (session 28), then CLOSED OFFLINE
            (session 29; see the search-proper box).** Session 28 measured that the f1 seed-push error
            (~3.3e-5 u, from `full_depth_push` on the settled seed centre) grows GEOMETRICALLY at
            ~1.35x/contact-frame -- f16 ~1e-4 u, f24 ~4e-3, f32 ~0.08, f36 ~0.52, **f43 ~4.1 u** (2
            cycles) -- past the 0.004 u placement resolution within ~1 cycle, catastrophic over 4-6.
            Session 28 planned a live `setCollision`-breakpoint capture of f0's exec centre; **session
            29 showed that was unnecessary AND that there were TWO residuals, not one.** f0's exec
            centre is not pose-reconstructable, but the f0->f1 push RESULT is the perop ΔTetra
            (0-ULP by construction, since Tetra has no foot term); and the closed loop ALSO needed
            Tetra stored as f32 (the console's storage), because the plow amplifier explodes the f64
            residue -- closing the push alone made the drift WORSE (~50 u). Both are offline.
      - [x] **The primitive layer RESTORED on the 0-ULP model + GATED (session 28).** The session-22
            `seeds.py` (self-contained FreeRun factory + the 288-coord `tetra_placements.tsv` loader)
            and `primitives.py` (`window_records` = the instrumented rollout, `find_cycles`,
            `cycle_template`, `input_macro`/`macro_inputs` = the cycle's raw-input pattern re-aimable to
            any world angle via `plan_land._primitives.stick_for_bearing`) are back -- they run
            unchanged against the current bit-exact `FreeRun` API. Only the premature TOLERANCE-based
            `tier0.py` search layer stays removed (the exact confirm is FreeRun, not a `0.13 u` bound).
            Gate `tests/test_planner_primitives.py` (5, STRUCTURAL not sim-vs-console -- the fidelity
            is `test_from_f0`'s): the window covers f1..43, `find_cycles` recovers the 2 cycles (rolls
            f3/f29), the roll-body FOOT term is cycle-rigid to <0.02 u (WHY a cycle is a re-aimable
            primitive), `macro_inputs` reproduces the exact button/trigger pattern + valid bytes +
            C-stick pinned DOWN, and the analog re-aim is faithful (<1 LSB) where the stick BITES
            (msd>0.3; the ~4-deg residuals are all at msd~0.05 roll-body frames where facing is locked
            and the angle is irrelevant -- a documented tier-0 property, not a bug).
      - [x] **Coarse feasibility CONFIRMED (session 28), from the bit-exact window** (`feasibility.py`,
            CLI `python -m harness.tetrapush.feasibility`; all numbers recomputed live so they can't
            drift). The recorded 2-cycle window herds Tetra **544.8 u @ -161.7 deg**; the genuine-coord
            cluster centroid is **967.5 u @ -161.5 deg** from her state-2 start -- i.e. **the natural
            push direction already points at the clip region (0.2 deg off)**, so the plan is a
            near-straight herd, not a steer-around (state 2 was set up for exactly this shove).
            Per-cycle reach ~345 u (full cycle 1) -> ~3 cycles cover the ~940-984 u span; Link<->Tetra
            distance stays **40-85 u** (well under `FOLLOW_ENGAGE_DIST` 230), so Tetra stays stt-3 (the
            plow regime this model covers) throughout. Verdict boxes all green (direction / reach /
            regime). A trustworthy open-loop 4+ cycle ROLLOUT waits on the f1 capture (the drift would
            dominate past ~2 cycles); the feasibility argument here is directional + per-cycle + regime
            off the bit-exact 2-cycle capture, which needs no long rollout.
      Original-model-blocker context (RESOLVED session 27; kept for provenance): the search could not
      begin while position drifted (the session-22 Phase-1/Tier-0 scaffolding was REMOVED as premature,
      below, exactly because a position-drifting model is sand). The camera/look/neck sub-models ARE
      0-ULP-gated and reusable:
      - [x] **The novel-input stepper** (`from_f0.FreeRun`): the replay loop refactored into a
            seed-once / step-arbitrary-inputs class (computed centres; csangle/eyePos per-step
            injectables); `replay` is now a thin wrapper over it so every existing 0-ULP gate gates
            the planner path too, plus the direct-API gate `test_freerun_direct_api_matches_replay`.
            **FOLLOW guard**: the stepper warns (once) the first frame the 3D Link-Tetra distance
            exceeds `npc_zl1.FOLLOW_ENGAGE_DIST` (230) -- live Tetra flips to the UNMODELED stt-4
            follow state at-or-after that crossing (s17 probe: crossed 231.9 f63, stt 4 f75), so a
            plan must keep Link inside the plow regime; `test_freerun_warns_when_tetra_would_follow`.
      - [x] **The csangle (land camera) model -- PORTED + 0-ULP GATED (session 18).** The
            session-17 "emergent follow springs" map was WRONG: the window runs **manualCamera
            (mode 12)** (C-stick held down keeps `m144 == 0`, which outranks lock-on in
            `nextMode`), with 1-frame followCamera blips on L rising edges - csangle is a
            directly C-stick-commanded input channel (yaw target 8 deg/frame shaped, view globe
            chase 0.66/frame; Link only moves the CENTER). `tww_sim/core/camera/land_cam.py`
            (LandCamera + cam_angle.py) reproduces the fully-chained 120-frame live oracle
            bit-exactly (every csangle, view-cache globe, center, work spring; the four L blips
            and both lock windows included). Gate `tests/test_land_cam.py`, oracle
            `fixtures/courtyard_cam_oracle.json` (probe `_notes/tetrapush-camoracle_probe.py`).
            Truth page [`knowledge/mechanics/land-camera.md`](../../knowledge/mechanics/land-camera.md)
            (decomp-source traps: manualCamera is EMPTY in the zeldaret decomp - recovered via the
            JP Ghidra DB headless (`pyghidra`, `tools/GHIDRA_CONTROL.md`); the source style table
            and the cSGlobe setter bindings both differ from the shipped binary).
      - [x] **LandCamera WIRED into `FreeRun` (session 19) -- the csangle injection is gone.**
            `FreeRun(camera=)` / `replay(camera=, tattns=)` run a `land_cam.seed_from_block`-seeded
            LandCamera in the closed loop, stepped at the END of each frame from the sim's own
            post-step state (the game order: player execute -> camera Run; frame k+1's physics
            reads the csangle committed at k). Inputs, all self-contained: the delay-1 raw DTM
            bytes decoded by `land_cam.pad_from_raw` (PADClamp octagons + JUTGamePad TStick +
            ClampTrigger; gated 0-ULP vs the oracle's post-updatePad stick lasts), the sim's own
            `AttentionLock.locked` for `LockonTruth()`, and Link's attention position via the
            decomp law `attn = (pos.x, f32(92.5 + baseTR[1][3]), pos.z)` (`setAttentionPos`
            :10271; gated 0-ULP vs the oracle f3..f9 -- the unmodeled m35B8 seed residue gives a
            2-frame <0.15 u center-Y transient, csangle-invisible since the yaw target is C-stick-
            only). Only `tattn` (the locked actor's attention pos, lock windows) stays injected,
            same status as eyePos. Gates: `test_camera_in_the_loop_replay_bit_exact` (every
            committed csangle f1..43 == live == the cam oracle, physics rows byte-identical to the
            injected-csangle reference) + `test_pad_decode_matches_oracle`. TWO extraction truths
            found on the way: **the game latches POLL INDEX 2 of a DTM frame's 4-poll group** (the
            window's only two non-uniform groups pin it uniquely; `dtm_inputs.frame_input` fixed,
            fixture regenerated -- only f25's substickX byte changed, physics-inert), and the
            oracle's `main_angle` is a probe-timing shift (it decodes the NEXT frame's raw bytes;
            DMC-only, inert at status 0).
      - [x] **The Tetra eyePos + tattn model -- MODELED + 0-ULP GATED + WIRED (session 20); the
            replay is FULLY SELF-CONTAINED (no injected streams).** Truth page:
            [`knowledge/mechanics/tetra-look.md`](../../knowledge/mechanics/tetra-look.md).
            `tww_sim/core/npc_zl1_look.py` ports the whole chain decomp-first: `optn_1`'s look
            timer machine (wait03/look anims, the `rnd(90,180)` countdown -- the RNG re-seed after
            a full look cycle is flagged as `rng_horizon`, beyond any plan window), `lookBack` ->
            `dNpc_JntCtrl_c::lookAtTarget_2` (the head/backbone chkLim split + the
            `cLib_addCalcAngleL(..,4,step,4)` chase; step 0x1000 live -- `field_0x7BC = -1`, NOT
            the 0x0180 default), the `mDoExt_McaMorf` frame ctrl + 8-frame quat-lerp morf, the
            Zl1 head FK (zl.bdl chain 0-1-2-5-6, `harness/anim/extract_zl1.py` -> `_generated/`),
            the two node CBs (chest `XrotM(bb_y) ZrotM(-bb_x)`; head `YrotM(-hy/2) ZrotM(-hx/2)`)
            + the (20,-16,0) eye offset, and `setAttention` (tattn = feet + f32(y+140), verified
            against the s18 cam oracle). Link's look target = his exec-pass **mHeadTopPos** =
            `anmMtx(15)*(40,0,0)` (`FootFK.head_top`, same base/lean/init-frame laws as the Co
            centre). Gates (`tests/test_zl1_look.py`, fixture `fixtures/courtyard_zl1look.json`
            from `_notes/tetrapush-zl1look_probe.py`): the model reproduces EVERY live eyePos,
            tattn, chased angle, target, and half-angle f1..f44 **0-ULP** given live inputs; the
            self-contained replay (`FreeRun(camera=, zl1=)` -- eye/tattn injections deleted)
            keeps every proc + speedF 0-ULP + lean exact + **every csangle live-exact** f1..43,
            facing within a +12-BAM eye-aim echo on the untarget frames (see the m3564 box
            below). `capture_push seed` now also captures her hidden look state (the seed
            fixture's `zl1` block -> `Zl1Look.seed_from_row`). 474 offline green, land goldens
            byte-identical.
      - [x] **Link's own head-look `m3564` -- MODELED + 0-TOLERANCE GATED (session 21); the
            model-gap list is EMPTY.** Truth page:
            [`knowledge/mechanics/link-head-look.md`](../../knowledge/mechanics/link-head-look.md).
            `tww_sim/land/neck_look.NeckLook` ports `setNeckAngle` (:8938-9169) decomp-first: the
            proc-table mode-flag gate (0x80 procs look, rolls/turns chase 0), the lock-or-list
            look-pos selection through the +-0x6000 m34DE cone (with `AttentionLock.list_present`
            -- the stock/free timing whose one-frame hole IS the probe's f21 chase-to-0), the
            prev-frame head-matrix measure (`FootFK.head_mtx`, the jointBeforeCB two-concat twist),
            the absXZ<30 yaw freeze (the tier-frame razor: f19-21 y = 60/-3/0 exact), the
            [-10000,8000]/+-14336 clamps, and the (3, 0x1000, 0x100) half-angle chase. Two
            live-pinned timing laws: **m34DE at setNeckAngle is the frame-START facing** (:11287
            is in the execute prologue, before the proc dispatch :11402), and the head matrix
            measured is the PREVIOUS frame's calc. Gates (`tests/test_neck_look.py`, fixture
            `fixtures/courtyard_m3564.json` baked from the probe): capture-tight (diag) replay =
            **every m3564 AND every facing f1..43 bit-exact vs live** (the <=16-BAM echo is
            CLOSED; head-top Y <=0.96 u -> <=1e-3 u); self-contained replay = physics 0-ULP with
            m3564 exact outside the chase window, +-16 BAM inside it (drift-quantization only --
            every chase increment matches live). `capture_push seed` now also logs `link.m3564`
            (the NeckLook f0 seed; fixture regen pending next live session). 478 offline green,
            land goldens byte-identical.
      - **Phase 1 + Tier 0 (session 22) -- BUILT then REMOVED as premature (session 24, Dereck).**
            `seeds.py` / `primitives.py` / `tier0.py` + `tests/test_tier0.py` were a geometric
            shove-search layer (rigid cycle templates + a cheap monotone predictor + a beam sweep).
            They were built ON TOP of a forward model whose POSITION is not bit-exact, so any landing
            map they produce is unsound -- and `tier0.validate` was a `0.13 u vs FreeRun` TOLERANCE,
            i.e. a heuristic-vs-sim approximation bound, never a fidelity gate. Removed: the search
            cannot start until the forward model is 0-ULP (the two bugs above). The one durable
            session-22 finding survives in the code/gates: the plow feedback is an unstable
            ~1.35x/contact-frame amplifier and multi-cycle dynamics are chaotically sensitive
            (an 11-BAM cycle-1 aim change flips cycle-2's viable band), which is precisely WHY the
            model must be bit-identical, not merely bit-faithful, before any open-loop multi-cycle
            plan. (git history has the removed code if the template idea is wanted post-0-ULP.)
      - [x] **THE FK 0-ULP HUNT -- RE-DIAGNOSED (session 23): the FK matrix is NOT the blocker.**
            Session 22 named the blocker "make `FootFK.body_co_center` fp-faithful." That is
            **misdiagnosed** -- `body_co_center` is ALREADY bit-exact: fed the breakpoint-exact pos,
            the computed exec centre equals `courtyard_push_setcol.json`'s `cyl_exec` to **0 ULP on
            every frame f1..12** (the joint-chain accumulation, SSC, worldBase concat, quantization
            are all correct). The console `sqrtf` (MSL `frsqrte` + 3 double Newton steps + f32 cast,
            math.h:89) was also RULED OUT -- bit-identical to a correctly-rounded `math.sqrt` over the
            loop's whole dist_sq range, swapping it in changes nothing. **The real picture (gated
            `test_from_f0.py::test_onestep_error_bounded_from_exact_state`):** the coupled STEP
            FUNCTION is bit-faithful -- reset to the exact captured state each frame and step once, the
            one-step Link-pos error stays BOUNDED and NON-accumulating (<=64 ULP in z ~ 1.5e-5 u,
            largest at the roll-entry morf frames k3..k5 = the known `calc_transform`/Hermite
            entry-morf sub-ULP flagged in `core/anim/quat.py`; single-digit ULP elsewhere; x 0-ULP
            throughout -- its coarse f32 quantum at ~1335 hides the same ~1e-5 u residual that shows
            at small-z). facing + speedF bit-exact every frame; diag mode (push driven by the injected
            fixture centre) does NOT drift over all 43 frames. So the `centers='computed'` blow-up is
            the plow feedback (depth = 80 - dist, **~1.35x/contact-frame = an unstable amplifier**)
            magnifying a ~1e-5 u/frame residual that sits at the single-step fixtures' own f32 noise
            floor. The FK matrix, the sqrt, the plow/recoil math, and the seed are each correct to
            that resolution.
      - [x] **STRATEGY DECIDED (session 24, Dereck): 0-ULP is the bar, non-negotiable** -- "we must
            have 0 ULP or else this tool is worthless." This CLOSES the session-23 open question: NO
            tier-2-envelope / trust-~1-cycle escape. The planner stays pure-sim-from-state-2 (the hard
            rule), which the multi-cycle deliverable (~4-6 cycles to herd Tetra ~960 u, the placements
            coupled to the final roll entry) FORCES to be bit-identical -- the ~1.35x amplifier makes
            open-loop multi-cycle prediction explode with ANY residual. Directive: capture the
            live/offline divergences as concrete TEST CASES, then drive each to 0.
      - [x] **DIVERGENCE TEST CASES BUILT + the residual ATTRIBUTED to TWO bugs (session 24), all
            offline.** The one-step-from-EXACT-state gate (`tests/test_from_f0.py::
            test_onestep_pos_bit_exact_from_exact_state`, xfail-strict) pins the Link divergence at
            0 ULP: live pos is breakpoint-exact (`setcol.pos == cyl.pos`), so the ~5-56-ULP z error is
            REAL sim-vs-console. The per-frame table is `python -m harness.tetrapush.onestep_divergence`
            (worst 56 ULP ~1.3e-5 u at f4; 28/43 z frames diverge). **The split (decisive, no live
            needed):** Tetra has NO foot term (stt-3, speedF 0), so her pos-delta isolates the push law
            -- it diverges ~9 ULP with **no roll-entry spike**, while Link's has the spike (f3-5,
            56 ULP, decaying with the morf). So:
            * **BUG #1 -- the push/recoil law** (both actors, ~few ULP): the Courtyard replay uses the
              session-9 DERIVED `full_depth_push` (`link_plow.recoil` + `tetra_plow.plow_step`: TWO
              separate `fsqrt`; and `full_depth_push` returns Tetra's move as an f64 `new-minus-old`
              while Link's is a direct f32 delta -> the two are NOT exact opposites, ~1 ULP off), NOT
              the decomp-faithful `cc_push.co_move_pair` (ONE dist, obj1/obj2 moves exact-opposite,
              `sum==0` live-confirmed). Gates (both xfail-strict):
              `test_tetra_push_bit_exact_from_exact_state` (push vs live Tetra, no foot confound) +
              `test_full_depth_push_recoil_is_exact_opposite_of_tetra` (the Newton's-3rd-law
              self-consistency invariant -- a pure code bug, no live needed). **Fix = compute the push
              the console's way** (`co_move_pair` math on the right centres, f32 Tetra tracking).
            * **BUG #2 -- Link's roll-entry foot term** (Link only, f3-5 spike): the sim omits a
              foot-position delta during the entry morf that the console has (the `calc_transform`/
              Hermite jnt0 lead in `quat.py`). Isolate it cleanly AFTER bug #1 (once the recoil is
              bit-exact, Link's residual IS the foot term).
      - [x] **ALL tetra-push tests REWRITTEN to 0-ULP (session 25, `[[zero-ulp-tests-only]]`).** Every
            sim-vs-console assertion across `tests/test_{from_f0,tetra_plow,link_plow,tetra_untarget,
            atn_actor,land_cam,zl1_look,neck_look}.py` is now `_bits==_bits` (0 ULP), `xfail(strict)`
            where blocked, or deleted -- there are NO `err < eps` position/plow fidelity tolerances
            left (the class that hid the 5-56 ULP residual for ~15 sessions). Concretely: (a) the two
            DETERMINISTIC-capture tolerances flipped to true 0-ULP `==` (measured: `setCollision` exec
            midpoint and the settled-centre half-depth law are BIT-EXACT vs the setcol breakpoint over
            f1..12); (b) the standalone plow law got a 0-ULP `xfail(strict)` gate
            (`test_plow_step_bit_exact_vs_live` -- the clean f32 twin of the buggy `full_depth_push`
            wrapper); (c) the dynamics gates (chained/f0-seed replays, closed-loop, the zl1/neck
            wiring) were STRIPPED of their tacked-on position/facing tolerances and now assert only
            the genuinely-0-ULP dynamics (proc/speedF/facing/lean/csangle/m3564/tattn); (d) six
            redundant single-step position trackers were DELETED (Link-pos, Tetra-pos cumulative,
            computed-centre, reconstruct, and the two link-recoil tests whose comparison target was a
            lossy `math.sin` reconstruction -- superseded by the session-24 divergence gates); (e) the
            surviving non-fidelity checks are each explicitly RELABELLED -- the frac==1.0 full-vs-half
            REGIME discriminators, the proc-9-vs-MOVE step-magnitude discriminator, the fixture-identity
            guard, and the bounded-error/amplification REGRESSION GUARDRAIL. The position 0-ULP bar is
            now the three session-24 `xfail(strict)` divergence gates + the new plow gate; when the two
            bugs close (via the live per-op capture below) they auto-flip to hard passes. 472 offline
            passed, 9 xfailed (was 479 passed / fewer xfails: -6 deleted, +1 pass->xfail, +2 new 0-ULP
            `==`); land goldens byte-identical, KB gates green. The rollstab `cc_stepper`/`cc_rollstab`
            were reviewed and hold NO sim-vs-console fidelity tolerances (already 0-ULP where they
            compare to console; their remaining bounds are model-algebra/meaningfulness), so they were
            left as-is.
      - [x] **BUG #1's SELF-CONSISTENCY part CLOSED OFFLINE (session 26).** `full_depth_push` now
            returns Tetra's push as `-recoil` (an exact f32 sign flip off the SAME dist/pushFactor)
            instead of the old f64 new-minus-old, so Link recoil and Tetra push are EXACT bit-for-bit
            opposites (Newton's 3rd law for the same-rank Co pair, `cc_push.co_move_pair` sum==0).
            `test_full_depth_push_recoil_is_exact_opposite_of_tetra` flipped from `xfail` to a HARD
            PASS; every dynamics gate stayed 0-ULP, land goldens byte-identical. This is a pure-code
            fix (no live capture). The remaining exec-vs-settled push gap + the foot term are the two
            gates below.
      - [x] **THE LIVE PER-OP CAPTURE -- DELIVERED (session 26); it OVERTURNS the "noise floor" framing.**
            Baked `fixtures/courtyard_push_perop.json` (probe `_notes/tetrapush-perop_probe.py`): both
            actors' `current.pos` read at the JP `posMove` (0x80106514) breakpoint, one hit per game
            frame f0..f43 (DETERMINISTIC -- the bp pins the frame count). **KEY FINDING: this
            breakpoint capture matches the single-stepped cyl fixture BIT-FOR-BIT (0 ULP) at EVERY
            frame f0..f43, both actors** (`test_perop_confirms_cyl_positions_are_deterministic`, hard
            pass). So the cyl POSITIONS were exact deterministic ground truth all along (not just the
            setcol-confirmed f1..12); the ~5-56 ULP one-step divergence is a REAL sim-vs-console
            residual, not the "~1e-5 u single-step noise floor" the session-24 xfails cited. The two
            bugs are therefore pure OFFLINE code bugs -- no more live capture is needed to fix them.
            Method notes (hard-won, in "## Live setup"): a bare `resume` free-runs the movie -> Dolphin
            cleanly EXITS; step with `advance` + breakpoint. `m_cc_move` (`lp+0x3FE8`) reads 0 even at
            posMove entry (the push lands via immediate `current.pos` writes in the CC pass, not a
            deferred move), so the push is measured from POSITIONS: Tetra has no foot term (stt-3) so
            her push = ΔTetra (bug-#1 truth); Link's foot term = ΔLink + ΔTetra -- deterministically a
            CONSTANT 26.0 u/frame during each roll with the entry-morf RAMP at roll-start (18.5->26.0),
            i.e. bug #2 = the `calc_transform`/Hermite jnt0 entry-morf, laid bare.
      - [x] **THE TWO FIXES PORTED -- and it was ONE bug, not two (session 27, fully offline). The
            one-step-from-exact-state POSITION is now 0-ULP f2..f43 (42 consecutive frames), Link AND
            Tetra.** Bug #1 = the push law: replaced the DERIVED `full_depth_push` on the SETTLED centre
            with `from_f0.cc_push_pair` = `cc_push.co_move_pair` (`dCcS::SetPosCorrect`, the decomp
            50/50 half-depth split) on the model's own EXEC centre `cx`. Verified vs the deterministic
            per-op ΔTetra: `co_move_pair(cyl_exec)` reproduces it BIT-FOR-BIT f2..f43, where
            full-depth-from-settled (fused or not) is 1-9 ULP off (they agree only to ~1e-5 u). **Bug #2
            does NOT exist as a separate bug:** the session-24 "roll-entry foot term / f3-5 spike (56
            ULP)" was the RECOIL error (bug #1) being larger at roll entry (where the geometry ramps),
            measured THROUGH Link's position. With the console recoil (pinned to Tetra's deterministic
            ΔTetra by the exact-opposite Newton pair), Link's foot term is bit-exact -- the entry-morf
            ramp (18.5->26.0) the sim already reproduces correctly; no `calc_transform`/Hermite change
            was needed. Gates flipped from `xfail(strict)` to HARD PASSES:
            `test_from_f0.py::{test_onestep_pos_bit_exact_from_exact_state,
            test_tetra_push_bit_exact_from_exact_state}` (model exec centre, f2..f43 vs perop) and
            `test_tetra_plow.py::test_console_push_bit_exact_vs_deterministic` (renamed from
            `test_plow_step_bit_exact_vs_live`; the standalone twin -- `cc_push_pair` on the setcol
            EXEC centre vs perop ΔTetra, f1..12). Code cleanup: retired the superseded derived laws
            `tetra_plow.{plow_step,reconstruct}` (git history is the archive; `plow_depth` + the radii
            stay); `full_depth_push` survives ONLY as the seed-frame (f0->f1) fallback. The
            closed-loop `centers='computed'` drift COLLAPSED from ~93 u to ~4 u. **f1 is the only
            residual: the seed-frame push comes from f0's exec centre, which is NOT
            offline-reconstructable** (the seed frame doesn't carry f-1's lean/morf -- documented in
            `from_f0._seed_pose_f0`). Closing the closed loop / f1 to full 0-ULP would need ONE
            deterministic `setCollision`-breakpoint read at the seed frame (f0's exec centre) -- the
            only place a further live capture would help. 476 offline pass / 5 xfail (all pre-existing,
            non-tetrapush), land goldens byte-identical, KB + code-hygiene green.
      - [x] **The f1 seed-frame boundary -- CLOSED to 0-ULP, ENTIRELY OFFLINE (session 29). The
            self-contained closed loop from state 2 is now bit-exact in POSITION too, f1..43.** This
            OVERTURNS the session-28 plan (which called for a live `setCollision`-breakpoint read of
            f0's exec centre): no live capture was needed, and the drift was TWO offline residuals,
            not one. (a) f0's exec centre is indeed NOT pose-reconstructable (session-29 check: the
            pose-computed centre is ~0.5 u off -- the seed lacks f-1's lean/morf), BUT the f0->f1 push
            RESULT was already in the locked deterministic `courtyard_push_perop.json`: Tetra has NO
            foot term (stt-3, speedF 0), so her whole f0->f1 move IS the CC push, and `ΔTetra =
            perop.tetra[1] - perop.tetra[0]` gives `f0 + ΔTetra == f1` BIT-FOR-BIT. (b) Closing (a)
            alone made the closed loop WORSE (~4 u -> ~50 u): it exposed a SECOND bug -- the model
            carried Tetra as an f64 point while the console stores current.pos as f32, and the
            ~1.35x/contact-frame plow amplifier explodes that sub-f32 residue. Rounding the tracked
            Tetra point to f32 each frame (matching `dCcS::SetPosCorrect`'s f32 `*ppos += vec`) is the
            other half. With BOTH: the one-step-from-exact-state gate now asserts f1..f43 (was f2..f43),
            the ACCUMULATING closed loop is 0-ULP f1..43 for both actors vs perop, and the planner's own
            `seeds.make_freerun` self-contained rollout (camera+zl1+neck, no injections) is 0-ULP
            position over the whole DTM window. Wiring: `FreeRun(seed_push=)` takes the exact perop
            ΔTetra (`seeds.seed_push_f0`); `full_depth_push` stays the roll-entry / no-perop fallback.
            Gates: `test_from_f0.py::{test_onestep_pos_bit_exact_from_exact_state,
            test_tetra_push_bit_exact_from_exact_state}` (now f1..f43) +
            `test_closed_loop_computed_replay_bit_exact` (NEW position 0-ULP). 481 offline pass.
      - [~] **The search proper** -- the exact-search FOUNDATION is BUILT + gated (session 30,
            `harness/tetrapush/search.py` + `tests/test_search.py`); the coarse multi-cycle herd is
            BLOCKED on cycle chaining (below). Delivered, all on the 0-ULP `FreeRun`:
            * **`rollout(env, aims)`** -- stitch re-aimed push-cycle macros (`canonical_cycle` =
              the 26-frame roll-to-roll unit) through `FreeRun` from state 2, C-stick pinned DOWN,
              main stick re-aimed per frame from the LIVE csangle. 0-ULP self-consistency gated two
              ways: the recorded-input replay reproduces the window bit-for-bit, and the macro
              re-aimed to its own recorded aim (with the recorded C-stick + frame-aligned csangle)
              reproduces cycle 1 bit-for-bit. THE AIM IS A NOMINAL KNOB -- with a pinned C-stick the
              csangle evolves differently than the recording and the stick byte grid quantizes the
              achievable aims, so the search RANKS BY THE ACHIEVED LANDING read back from FreeRun.
            * **`FreeRun.clone()`** -- ~0.025 ms deep copy (shares the immutable anim tables via
              `LandState.clone` + `LandCamera/Zl1Look/NeckLook.clone`, vs ~60 ms for a whole-object
              deepcopy); a clone steps bit-identically to its parent. The beam-search branch.
            * **Reachability** (`reach`): the per-cycle Tetra reach is a DISCRETE set of byte-
              quantized aims with a sharp **RESONANCE at the recorded aim** -- one cycle herds Tetra
              **~324 u** @ -162 deg staying coupled (max Link<->Tetra 85 u), vs ~150 u and higher
              maxdist for aims +-600 BAM off. The hand-performed TAS sits on this resonance. (This is
              the concrete form of the session-22 "sharp sensitivity" -- deterministic, not chaos.)
            * **`beam_search`** -- the clone-branched beam over per-cycle aims, ranked by nearest
              genuine-coord distance, pruned by the stt-3 plow-regime guard, each candidate a REAL
              FreeRun rollout (no rigid-template approximation -- that was the removed `tier0.py`).
            **CYCLE CHAINING = RE-DIAGNOSED (session 31); the FRAME-MINIMAL TURNAROUND-ROLL is the
            path (`turnaround` CLI, `[[tetrapush-frame-minimal]]`).** Dereck steer: this is a speedrun,
            so the objective is FEWEST TOTAL FRAMES to a genuine coord, not just "reach it".
            - **Session 30's "chaining needs C-stick camera management" was WRONG about the lever.**
              The recorded window's csangle barely moves (~28 BAM over f20..28); feeding the recorded
              C-stick only "chains" cycle 2 as a byte-quantization ARTIFACT (its ~655 BAM csangle
              offset perturbs a razor-margin cone gate). The REAL gate for the re-aimed-macro chain is
              the inter-roll MOVE-backslide FACING TURN: the next re-target's held L re-acquires the
              attention lock (-> proc-9 slide, no roll, drift out of regime) UNLESS Tetra has left the
              +-0x4000 (90 deg) front cone by the L-pulse. The recorded run clears it by ~2600 BAM; the
              pinned macro misses by ~145 BAM (the session-22 chaotic sensitivity).
            - **The turnaround-roll SIDESTEPS all of that.** The roll is an A-roll (`a_pressed`, PAD
              0x100) and `_roll_init` snaps `facing = target` (the stick world-target). So a turnaround-
              roll -- face away from Tetra, then A + stick-toward-Tetra -- rolls THROUGH her in one
              frame with NO attention lock and NO cone gate (it also dodges the console talk cone,
              `[[turnaround-roll-tech]]`). It fires only from a GROUNDED proc (MOVE/ATN_MOVE), not the
              proc-9 untarget slide, so it is available ~2 frames after the untarget drops to MOVE.
              Gated: `test_search.py::test_turnaround_reroll_fires_from_grounded`
              (`search.cyc1_to_untarget` + `turnaround_reroll`).
            - **Tetra is stt-3 (does NOT self-locomote; waits where plowed, until dist > 230 -> stt-4
              follow).** So chaining has no time pressure FROM HER; the only cost is FRAMES.
            - **DEEP vs GRAZE is the crux, and it is POSITIONING, not aim.** An immediate A-roll GRAZES
              (min_ovl ~66, snowplows Tetra ahead, cyc2 adds only ~64 u); sweeping the roll aim at
              reposition 0 NEVER beats ~66 (at dist ~59 Link and Tetra co-move SW at ~equal speed
              through the roll). The recorded human cyc2 plows DEEP (min_ovl ~40, +185 u) because its
              ~8-frame CURVED backslide (facing 37548->16140 while backing up) lands Link NE of Tetra
              at a cut-THROUGH approach before the roll.
            - **THE FRAME-MINIMAL LEVER (Dereck, session 31):** the human's ~8-frame face-away turn is
              the suboptimal part. Since the roll snaps `facing = decode(stick) + 0x8000 + csangle` and
              csangle is a per-frame input, PRECISE CAMERA control can reorient Link ~180 deg in ONE
              frame -- collapsing the ~8-frame reposition-turn to ~1. NEXT: build the frame-minimal
              turnaround-roll chain -- the MINIMAL (camera-assisted) reposition that places Link NE of
              Tetra for the deepest through-roll, chained, with total FRAMES the objective; the
              recorded 2-cycle human playback (f0..44) is the feasibility ORACLE, not the target. THEN
              the exact placement (walk-push nudge endgame) + the entry walk-in + tier-2 DTM confirm.
              NO further live capture is needed for the forward model.
            (Superseded session-30 continuous-overlap reframe, still true and useful: per-frame
            instrumentation (`herd` CLI) shows the herd is a CONTINUOUS overlap-push, ~10-18 u/frame
            EVERY frame Link's Co-cyl overlaps Tetra (dist < 80), roll AND backslide alike; a proc-9
            slide keeps plowing but DECAYS as Link drifts to dist > 80, so rolls -- forward-drive at
            +26, tight overlap -- are ~3-4x more herd-efficient per frame.)
            - **SESSION 32 -- the session-31 pure turnaround-roll is a DEAD END; the primitive is the
              HUMAN'S re-aimed cycle. TALK-SAFE GATE built + wired + gated.** Two defects the forward
              sim hid (it models neither the talk trigger nor a facing gate on A) sink the turnaround-
              roll, both surfaced offline via `[[turnaround-roll-tech]]`/`knowledge/mechanics/tetra-follow.md`:
              1. **It TALKS.** A roll-trigger A-press (PAD 0x100) from a GROUNDED proc while Tetra is a
                 valid attention target (`zl1_attention_active`: XZ<300, |dy|<300, Link facing within
                 +-90 deg of the bearing to her) TALKS/LOCKS on console instead of rolling -- INVALID.
                 The turnaround-roll fires facing ~straight AT Tetra (face-err ~3 deg), so it talks.
                 **GATE (session 32):** `search.a_press_is_talk`/`talk_active` (wraps
                 `zl1_attention_active`) is now checked at every roll-A press and reported as
                 `talk_unsafe` by `rollout`/`rollout_recorded`/`turnaround_reroll`, and PRUNED in
                 `beam_search`. Gated `tests/test_search.py` (10): the human's recorded window is
                 talk-safe (every roll-A fires with Tetra OUT of the cone -- the gate does not
                 false-positive), the turnaround-roll is talk-UNSAFE + weak, the beam keeps only
                 talk-safe cycles. A genuine turnaround-roll needs Link facing AWAY (cone False) at
                 the A-press; the roll then snaps facing THROUGH her AFTER the talk check.
              2. **It is a WEAK +5 roll, not +26.** `roll._roll_init` sets the roll COAST speed ONCE =
                 `clamp(pre_roll_speedF*1.5 + 0.5, 5.0, 26.0)` (constant momentum, no build-up). Fired
                 from the -25 EBS backslide it FLOORS at +5 -> Link crawls while the Co-cyl still punts
                 Tetra out of the 80 u range: the "graze" (min_ovl ~66; session 31 mis-attributed this
                 to "positioning"). A FAST (+26) roll needs positive pre-roll speedF (~>=17), which the
                 human gets from the proc-7 ATN re-target DIR_BACKWARD flip (+18, `atn.py` `nspeed *=
                 -1`) -- and that flip needs L held with Tetra OUT of the cone (else L hard-locks ->
                 proc-9 slide, no roll).
              - **The EFFICIENT primitive = the human's re-aimed cycle** (turn to clear the cone ->
                L-held proc-7 re-target +18 flip -> A-roll +26 with Tetra out of cone at the trigger
                -> ride the +26 roll), ~12 u/frame. The proc-9 locked slide (hold L + stick->Tetra, no
                A, talk-safe) is a ~6.6 u/frame monotonic fallback (NOT validated beyond the 2-cycle
                window, so not a 0-ULP deliverable yet).
              - **MONOTONIC HERD requires Link ON the herd line, BEHIND Tetra, rolling ALONG it.** A
                roll travels in a STRAIGHT line (facing locked at `_roll_init`). On-line behind her +
                aim along-line -> a SELF-STABILISING pursuit (dist oscillates 40..85, Link never
                overtakes; the recorded human f3..44 stays up-herd every frame, herd monotonic
                +8..+18/f). Laterally offset or aiming at her instantaneous position -> the straight
                roll crosses her path and OVERSHOOTS (dist balloons, herd freezes -- the oscillating
                hand-designed chains). So the roll aim is the herd-line bearing; the reposition must
                place Link on-line behind her.
              - **NEXT -- the OPTIMAL, BETTER-THAN-HUMAN solution** (Dereck, session 32: NOT the
                ~6.6 u/f proc-9 slide, NOT merely matching the human's ~12 u/f -- the recorded human is
                a LOWER BOUND to BEAT). Objective: fewest TOTAL frames from state 2 to Tetra on a
                genuine coord (+ the matching final roll entry). The human averages ~12.4 u/f only
                because ~10 inter-roll frames herd ~8-13 while a deep +26 roll peaks ~16-18; the win is
                COMPRESSING that inter-roll overhead toward the ceiling. Build a cycle from PRIMITIVES
                (not the fixed 26-frame macro) so the roll-to-roll PERIOD is a search variable: reverse
                (the untarget -25.7 backslide backs Link up-herd on-line for FREE) -> minimal cone-clear
                turn (camera/csangle = the fast-reorient knob) -> proc-7 +18 flip -> +26 roll aimed
                ALONG the herd line, ridden while Link stays on-line. Search (reverse frames, cone-clear,
                roll ride) per cycle to MAXIMISE herd/frame; chain via `FreeRun.clone`, prune by
                talk-safety (`a_press_is_talk`) + regime + on-line. FIRST verify the reverse-from-
                primitives (L held late in a corner-aimed roll -> untarget -> on-line backslide). THEN
                exact placement (walk-push nudge) + entry walk-in + tier-2 DTM. NO further live capture
                is needed for the forward model.
            - **SESSION 33 -- the FRAME-MINIMAL reposition PRIMITIVES built + gated
              (`harness/tetrapush/reposition.py`, `tests/test_reposition.py` (5)); Dereck taught the
              tech live and CORRECTED the session-32 "reverse backs Link up-herd" premise.** Every
              mechanic verified in the 0-ULP `FreeRun`:
              1. **STEER #1 -- prune "past Tetra".** `HerdLine` (herd axis = Tetra-start -> genuine-coord
                 centroid, -161.5 deg) + `lead` (Link's signed along-herd position vs Tetra: <0 =
                 behind = valid pursuit, >0 = OVERTAKEN). The human stays 40-85 u BEHIND her every frame
                 (`verify` CLI); a straight roll that overtakes shoves her sideways -> herd freezes, so
                 `on_line_ok` prunes it. The search prunes only regime+talk before this -- past-Tetra is
                 the missing prune.
              2. **STEER #2/#3 -- retain -25.727, don't settle for -25.45.** The human's untarget is a
                 2-frame proc-9 tier (body1 flips +26 -> -25.727; body2 adds the +0.275 ATN accel term
                 `ATN_SPD*msd(0.0556)*cos` -> -25.454). RELEASING the mid-roll lock-L ONE frame early
                 (`l_release_early`) drops the actor-lock a dispatch-frame sooner -> a 1-frame tier -> the
                 backslide inherits -25.727 (decays ~0.011/f). The L-release frame is a search variable.
                 (A truly-neutral stick does NOT help -- proc-6 MOVE with a neutral stick BRAKES to 0 in
                 ~5 frames; the human's slight held stick sustains the EBS glide.)
              3. **The 1-frame INSTANT 180 TURNAROUND (`turnaround`), csangle-dependent.** In the
                 untarget EBS facing sits ~exactly 0x8000 from travel; holding ESS-down (or a diagonal
                 ESS) with a PRECISE csangle sets the want-angle so the facing chase steps ACROSS travel
                 -> `temp*temp2 <= 0` -> `facing = travel` in ONE frame (`move.py:109-116`), speed
                 PRESERVED (cos(target-travel)~1, -25.727 held). Wide csangle snap window (~14k BAM, not
                 knife-edge; off it you get a MOVE_TURN reversal). csangle is the camera lever
                 (manualCamera C-stick); generalises to diagonal ESS + matching diagonal csangle. This
                 REPLACES the human's ~8-frame curved backslide-turn with 1 frame.
              4. **The tight cycle = turnaround(1f) -> proc-7 flip(2f) -> talk-safe +26 roll.** After the
                 turnaround Link faces AWAY from Tetra (up-herd); holding L + stick toward her (she is OUT
                 of the cone) fires the proc-7 DIR_BACKWARD flip (-25.7 -> ~+23, the "1 frame > +17"),
                 then the A-roll is TALK-SAFE (facing away at the press, `a_press_is_talk` False) and
                 clamps to +26 (not the +5 graze). A ~3-frame reposition vs the human's ~10.
              - **THE BLOCKER (the on-line reposition SEARCH -- "smart enough search space", Dereck).**
                The +26 roll travels ~400 u over ~15 frames; it stays a PURSUIT (dist 40-85, Link never
                overtakes) ONLY if Link is ON the herd line DIRECTLY behind Tetra so the Co-cyl plows her
                straight ahead continuously (the human's self-stabiliser). The hand-composed `frame_min_
                reroll` leaves Link ~15 u LATERALLY off-line, so the straight roll crosses her path and
                OVERSHOOTS (lead -53 -> +285, `chain` CLI OVERTOOK). Aiming ALONG the herd line (not her
                instant bearing) fixes the direction but not the lateral offset. NEXT = SEARCH the
                reposition params (turnaround csangle, `nflip`, roll aim, L-release/`release_at`, and the
                C-stick that realises the csangle) to place Link on-line behind her; prune past-Tetra +
                talk + regime; chain via `FreeRun.clone`; score herd/frame. The primitives + prunes are
                built and gated -- this is the remaining search. THEN exact placement + entry walk-in +
                tier-2 DTM. NO further live capture is needed for the forward model.
            - **SESSION 34 -- RE-DIAGNOSED the reposition (the session-33 turnaround is a DEAD END for
              on-line) + started the SEARCH + hit the throughput wall; ended on Dereck's PERFORMANCE
              pivot (CYTHONIZE for a hard brute force).** Full writeup:
              `_notes/tetrapush-session34-rediagnosis.md`; framework `harness/tetrapush/repo_search.py`.
              1. **The turnaround-roll (`reposition.frame_min_reroll`) cannot be on-line.** Validity
                 sweep over (nflip in 2..4, roll aim +-3000 BAM, csangle): **worst_lead >= +235 for
                 EVERY combo**. The turnaround snaps facing in 1 frame but Link's +lateral drift
                 compounds (entry lat +10 -> +21 at roll start), so the +26 roll shoves Tetra sideways
                 (overlaps her at dist 56-76 but lat +21->+76) and overshoots (lead -63 -> +261). The
                 corrected flip is `nflip=3` (the +18 completes; nflip=2 floored the roll at +5), but
                 even talk-safe + nflip=3 overshoots.
              2. **release-early (steer #2/#3, -25.7 retention) is INCOMPATIBLE with on-line.** From the
                 full 2-frame tier (-25.455, facing 37552, lat +5.1) an ESS-down hold nulls lat to -2 in
                 ONE frame with lead staying -33..-69 (never overtakes); from the release-early untarget
                 (-25.727, facing 35324, lat +10.2) the SAME hold makes lat GROW +14..+58 and Link
                 overtakes. Use the full tier for the reposition; the 0.27 u/f is not worth on-line-ness.
              3. **The on-line lever is the human's ESS-curved backslide** (facing/travel decouple),
                 NOT the turnaround; csangle is ~frozen in the recording but its VALUE is razor-critical
                 (the human's working curve sits ~650 BAM off a coarse grid).
              4. **THE WALL -- the coff-vs-lat coupling.** A talk-safe +26 roll needs facing OUT of
                 Tetra's +-90 cone at the L/A press (else L actor-locks -> +12 slide, and the A talks),
                 which requires rotating facing ~110 deg off the bearing. But rotating facing out-of-cone
                 via the backslide (preserving speed) forces lat to drift to ~-19 u by the frame coff
                 exits the cone -- NEVER both out-of-cone AND lat~0. The human evades this with the
                 **MAINTAINED actor-lock** (soft-lock, L held, `AttnFlag_20000000`; persists from cyc1's
                 roll through RELEASE + mid-roll L re-pulses) which FREEZES facing out-of-cone so he
                 never rotates it via the backslide. Neither the from-scratch primitives NOR a replay of
                 the recorded reposition CHAIN a valid on-line cycle (recorded replay -> proc-9 slide,
                 talk, overshoot +268).
              5. **`repo_search.py` (BUILT, not yet finding a cycle):** `curve_beam` = a per-frame beam
                 over speed-preserving backslide inputs (HARD-PRUNE speed drops below |24| -- Dereck
                 steer: a braked backslide is physically dead; fine aim + csangle vernier + soft-lock
                 L-held candidates), `flip_roll`, CLIs `curve`/`cycle`. Finds no on-line roll from the
                 reachable setups (the coupling + coarse vernier + no maintained-lock).
              6. **PERF (the pivot):** `FreeRun.step` = ~2500/s full, ~7600/s stripped (zl1=None,
                 neck=None -- PROVEN geometry-exact, 0.000 u diff, a safe no-miss search proxy; only the
                 head-look facing-echo differs). The pose-FK exec-centre (`foot_fk._pose_frame`/
                 `_local_from_old`/`body_co_center`, needed for the push) is the floor and runs in
                 PYTHON; native `_anmc.pyx` exists but does not cover it. **NEXT (Dereck's directive):
                 CYTHONIZE the step to 300k-1M/s, then HARD BRUTE-FORCE the reposition** -- a COMPLETE
                 state-space BFS (full per-frame branching on a FINE grid, dedup by discretized state,
                 hard-prune only speed/overtake/regime, NEVER rank-drop), with the MAINTAINED-ACTOR-LOCK
                 lever (freeze facing out-of-cone). Bit-confirm on the full 0-ULP FreeRun. THEN exact
                 placement + entry walk-in + tier-2 DTM.
            - **SESSION 35 -- the CYTHONIZE started: native `co_center` + a search fast-path (2.6x,
              0-ULP-gated); the physics-proc + anim-sampler port is the remaining chunk to 300k-1M/s.**
              Measured (stripped geometry proxy, zl1/neck OFF): baseline **6.8k/s** -> **8.4k/s** (native
              `co_center`) -> **17.5k/s** (`record=False`). Two safe, gated deliverables:
              1. **`_anmc.co_center` (native, 0-ULP).** Folded the whole `FootFK.body_co_center` neck-chain
                 accumulation (the setCollision root/neck midpoint -- 6x `_local_from_old` + concat + the
                 BODY_CHN twist + neck SSC) into ONE C call, reusing the existing native f32/quat/concat
                 primitives (+ a new `_quat_concat_c`). `body_co_center` calls it when `_anmc` is built
                 (Python loop kept as the `_force_py` reference). This removed the #1 Python hotspot
                 (`_local_from_old`). Gate: `tests/test_body_co_native.py` (native vs `_force_py` bit-exact
                 over a pos/facing/lean/body-lean sweep on a real dash old-pose) + `test_from_f0` stays
                 16/16 0-ULP.
              2. **`FreeRun.step(record=False)` -- the search fast path.** Skips the `sim_cyl` settled-centre
                 DIAGNOSTIC (`_cc_settled_center`) and the per-frame row dict; the brute force reads
                 `run.link`/`run.tx` directly. PROVEN geometry 0-ULP vs `record=True` over 40 f (pos,
                 speedF, facing, Tetra x/z all `_bits`-equal). The push (`cc_push_pair` on the computed
                 exec centre) is unchanged.
              **The remaining port (NEXT, still Dereck's 300k-1M/s directive):** the profile of the
              `record=False` step is now dominated by (a) the LAND PHYSICS procs -- `state.step` own +
              `move._set_speed_and_angle_normal` + `atn`/`atn_actor` + `main_stick_decode` +
              `_clamped_angle_s16`/`s16_signed`/`_dist_angle_s` (~33%), and (b) the ANIM KEYFRAME SAMPLER
              `j3d_eval.calc_transform`/`_keyframe_interp` (~20%; hermite is already native, the per-track
              dispatch is not). There is NO single remaining big lever -- 300k-1M/s needs the WHOLE step in
              one nogil C translation unit (physics procs + anim sampler + the FK glue), operating on C
              scalars with no per-frame Python object churn, then optionally an OpenMP `prange` fan-out over
              the BFS frontier (the `_shovec.pyx` pattern) to multiply by cores. Architecture: extend the
              C-resident `PoseEngine` to also pose the neck chain + expose `co_center`/`head_top` natively
              (so `from_f0` can drop `foot_native=False` and the whole pose FK is one C call), and port the
              courtyard procs (MOVE / ATN_MOVE / ATN_ACTOR / FRONT_ROLL + the attention machine) to a
              native `LandCore`-style struct. Keep the pure-Python step as the 0-ULP differential ORACLE
              at every stage (the `test_body_co_native` pattern: native vs `_force_py`, `_bits`-equal).
              **DERECK STEER (s35): MORE ROLLS ARE OPTIMAL** -- the brute force must NOT cap or penalise
              roll count. The roll is the productive frame (~26 u/f deep-overlap herd); the dead cost is the
              inter-roll REPOSITION. Frame-minimal = pack MORE rolls with minimal reposition between them,
              not fewer-rolls-with-long-glides and not a single big roll (`[[tetrapush-frame-minimal]]`).
            - **SESSION 36 -- 1M IS ALREADY IN C; the task is to PORT the courtyard step, not decorate it
              (Dereck: "1M no exceptions").** The decisive measurement: the EXISTING native `LandCore.step`
              (the C walk step) runs **1.48M steps/s raw** / 390k/s through the `LandState.step` wrapper.
              The courtyard search is slow (~17k/s stripped, ~2.6k/s in the real `make_freerun` rec=True
              config) ONLY because `from_f0.FreeRun` runs the courtyard step in **Python**
              (`native=False`). Native-leaf-op folding of the Python orchestration is a PROVEN DEAD END
              (~17k ceiling); this session's `pose_chain` fold was bit-exact but a perf wash (~1.0x
              rec=False / ~1.35x rec=True) -- do NOT continue that approach. **THE ONLY task = implement
              the courtyard procs natively in `LandCore` and wire `from_f0.FreeRun` to it** (attention
              machine + procs 8/9 ATN_ACTOR + the checkNextMode lock routing + `_cc_move` consume +
              `cc_push_pair` + f32 Tetra tracking, stripping zl1/neck/camera for the search; each gated
              0-ULP vs the Python step). Full port recipe = the newest handoff `## Next step`.
              **Also fixed this session:** the native engine was GLOBALLY DISABLED -- the land anim set
              grew to **17** but `AnimData`/the FootFK gate were capped at **16**, silently forcing the
              whole land sim (incl. the fused `LandCore`) onto Python. Bumped the cap to **20**; a default
              `LandState` has `_core` active again (497 offline pass + goldens byte-identical at the last
              check). KEEP that; `pose_chain` is optional scaffolding.
            - **SESSION 37 -- THE COURTYARD STEP IS NATIVE; 1M steps/s ACHIEVED (goal met).** The whole
              coupled Courtyard frame now runs in C and is fanned across OpenMP threads:
              `LandCore.step_courtyard` (physics + attention machine + procs 8/9 ATN_ACTOR + the
              checkNextMode lock routing + native body-Co exec centre + `dCcS` CC push + f32 Tetra
              track) is 0-ULP vs the Python `from_f0.FreeRun` over f1..f43, `FreeRun(native_step=True)`
              drives it (~190k steps/s single-thread), and `CourtyardFleet.run_par` (prange, all leaf
              helpers `noexcept nogil`) fans it BIT-IDENTICALLY to sequential across threads:
              **measured 1.06M steps/s at 10 threads (1.16M at 12)** on this 12-core box -- Dereck's 1M
              directive MET. Built in 5 gated stages (commits f2227ff cM_atan2s + dCcS Co push;
              d7db997 native physics + seed bridge; 9f8d765 native exec centre + push; 1671729 FreeRun
              wiring; d1ec838 the prange fleet). Gates: `tests/test_{cc_push,step_courtyard,freerun,
              courtyard_fleet}_native.py` + `test_body_co_native.py` (510 offline pass, goldens
              byte-identical). Detail log: `_notes/native-courtyard-step-PROGRESS.md`. The proc-9 eye +
              csangle are still injected (zl1 look-at not ported -- the stripped search uses feet-aim,
              geometry-exact per s34). **NEXT: hard-brute-force the on-line reposition on the native
              fleet** (the pre-perf blocker, `[[courtyard-tetra-push]]`); a complete state-space BFS is
              now affordable (>1M steps/s), MORE ROLLS optimal (don't cap roll count, Dereck s35).

## Hard rules (inherited from the seam-clip work)

- **Decomp-first** (`[[decomp-first-not-brute-force]]`): read `d_a_player_main.cpp` / the JP
  `framework.map` for exact thresholds before live-bisecting. Breakpoint the JP address, not the US
  decomp comment (`[[jp-vs-us-decomp-addresses]]`).
- **When live disagrees with the sim, DIFF per-frame, never guess inputs** (`[[tetra-clip-solved-live]]`).
- **0-ULP is the bar**, validated against a locked live capture, not offline plausibility.
- A single-stepped PLAYING movie is +-1-frame ambiguous for button EDGES (`[[run-dtm-1frame-jitter]]`);
  held-stick push frames are safe. For edge delivery use a clean free-run movie.
