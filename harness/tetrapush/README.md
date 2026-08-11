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
| `terminal_keep.py` | **THE TERMINAL AS A KEEP, NOT A RANK (session 145)** -- the three windows a last roll must satisfy AT ONCE, and the module that makes them affordable at the per-aim cut. `seam_window` reads which sine-table CELLS admit genuine dust off `fixtures/courtyard_facing_window_s92.json` (22 live, two lobes, a measured dead gap at 2554..2559, **and both scan edges live -- the top of the window is where the sweep stopped**); `in_seam_window` is the cell test. `TerminalKeep` reads the box off `terminal.clipping_family` (`un_along`/`un_runway`/`un_tetra_from_corner`, the ZERO-WALK-AWAY family) and RAISES at an unmeasured terminal rather than answering from a neighbour. Two halves by cost: `screen` = the cheap projection at the ROLL's own facing (no ctx, names the first axis that refused -- ``t_facing``/``t_along``/``t_runway``/``t_tfc``), `probe`/`score` = `handoff.probe` on a pooled `entry_search.CtxPool` ctx (0.13 ms against `PairFrame`'s 17), exact at the roll's own facing/lean/momentum. **The window is the sampled extent widened by HALF a scan cell**: a grid extent is not a boundary and the f32 basis lands a banked hit ~3e-5 u below its own integer coordinate, so the bare extent refused three of the eight hits it was read from. Gated `tests/test_terminal_keep.py` (16). CLI `python -m harness.tetrapush.terminal_keep [thrust] [lean]`. |
| `clip_roll.py` | **THE CLIP ROLL'S INPUTS AND ITS REAL FRAME COST (session 143)** -- the piece every bound priced and nobody had emitted. `clip_stream` = the raw rows (`rollstab.turnaround.build_sticks`' shape: aim + A, NEUTRAL through the roll, ONE UP+B rising edge at `b_index` = ``cut_step + 1``; a pushed mid-roll stick exits the roll before the thrust, and a neutral B is a side slash rather than the in-line CUT_F whose root translate IS the lunge). `roll_frames(cut_step)` = **``cut_step + 2``**, the corrected cost -- the entry frame runs one full roll step before schedule step 0, so the cut at step ``cut_step`` is roll frame ``cut_step + 2``; `handoff.endpoint` charges ``cut_step``. `aim_bytes_for` inverts `entry_search.aim_alphabet` onto a wanted facing and reports whether the residual BAM error stays inside its `aim_cell`. `dispatchable` = the two traps that stop a herd endpoint firing it (proc must be in ``ROLL_FROM``; `roll_nspeed` off the PRE-roll speedF). `fire` steps a Python-path `FreeRun` through the roll and reports the entry/cut frames -- **the native core has no cut branch at all** (`_anmc._proc_roll` omits the ``b_trig`` arm), so build the herd native and fire on `beam_io.rebuild_beam(native=False)`. Gated `tests/test_clip_roll.py` (9). CLI `python -m harness.tetrapush.clip_roll stream [cut_step]`. |
| `deliver.py` | **THE TIER-2 LIVE DELIVERY (session 54)** -- author a computed plan onto console and read the endpoint. `build_boot_movie` SPLICES the plan onto the recorded BOOT movie (game-frames 0..F0 byte-identical, tail = `log[i]` -> F0+1+i, `bFromSaveState=0`); **both savestate-anchor routes are dead** (see `## Plan / status` s54). `tick_mode='extend'` is mandatory (the recorded tickCount truncates the tail; the maxed 0xFFFF... reads as signed -1 = s53's State::Load crash). `play_spliced` issues ONLY `playmovie` + `savestate load 1` -- the subset-state shortcut that skips the ~9.5-min boot replay (~8 s/run); any pause/resume/advance of ours makes Dolphin re-pause. `deliver_plan` = author+play+read; **`divergence_curve` = TRUNCATE-AND-READ** (author the first N frames, PauseMovie halts at plan frame N-1, so one plain run samples that frame for BOTH actors -- a per-frame sim-vs-console curve with no stepping). Gated `tests/test_tetrapush_deliver.py` (6 offline: round-trip + prefix byte-identity, latched-input equality vs the recording, L/A/B + cal-clamp encoding, the tick_mode invariants incl. the maxed-value crash pin, truncation alignment). **Session 86** added `m351C`, `shape_z` and `nspeed` to `read_link`: a roll-entry confirm owes the two a `ShoveCtx` is keyed on (the lean it was built at and the momentum its schedule was baked at), not just position and facing. |
| `find_tetra.py` | Locate Tetra (Zl1, id 429) live via the DMC walk, `_execute` breakpoint, `r3`. Session-stable (recomputes the REL base). **`tetra_scan` (session 54) = the breakpoint-FREE locator** (one MEM1 block + `field_0x84F == 5` on the courtyard floor Y): required for any endpoint read off a HALTED movie, where the `_execute` bp cannot trap and silently yields nothing. |
| `capture_push.py` | Load slot 2, locate Tetra, single-step the movie N frames, log both actors + FULL pad to a fixture. The (scalar) GROUND TRUTH -- single-stepped, so `+-1` on edges. Now also logs `nspeed` (mNormalSpeed). Subcommand **`capture_push seed`** = a DETERMINISTIC single read of the complete f0 state (no single-step jitter) -> `fixtures/courtyard_push_seed.json`. |
| `fixtures/courtyard_push_seed.json` | The complete STATE-2 seed (f0): pos/travel/facing/speedF + the HIDDEN **mNormalSpeed** (`link.nspeed`) the cyl/dtm fixtures never logged, plus mDirection/m34E6/csangle + the attention state, for provenance. Deterministic single read (jitter-free). The from-f0 replay's `seed_nspeed` source AND the planner's initial condition (session 12). Session 16 added **`old_pose`** -- the live `m_old_fdata` per-joint post-morf pre-twist store (quat x,y,z,w + transform, all 42 joints) + morf counters, the `replay(..., seed_old_pose=)` source (at THIS seed it equals the pure-dash warmup; general-correctness for any f0 with live morf residue). |
| `fixtures/courtyard_plan_s73.json` | **THE PLAN THAT PASSES THE OBJECTIVE** (session 73) -- a complete state-2 input log (71 frames, ending AT THE ARRIVAL because `objective.score_plan` probes the escape atom itself) plus its provenance (which cycle-2 beam node, junction endpoint, roll aim and ``target_cs`` offset) and the ``atom_kw`` it must be scored with. `objective.replay_and_score` on it reads **75 frames (floor 73, timeloss +2), placement 0.4321 u on genuine coord 274, ``complete``/``terminal_ok``/``wall_ok``/``regime_ok``/``within_budget`` all True -> `objective.verdict` TRUE**, with the atom's ``cs_bill`` 0. Gated as a regression (`tests/test_objective.py::test_the_shipped_plan_passes_the_whole_objective_from_its_input_log_alone`), so milestone 2 is a test rather than a session claim. Score it with the fixture's own ``atom_kw``: with the default single-flip atom the same log reads 77 f / pd 4.48, a different escape. |
| `fixtures/courtyard_plan_s73_console.json` | **THE SAME PLAN, ON CONSOLE** (session 78) -- LOCKED. The DELIVERABLE sequence (the plan fixture's 71 herd frames plus the escape atom's own 7, which `score_plan` probes on a clone and so were never in the plan file) and the console-measured Link + Tetra at **22 truncate-and-read samples**, N = 1..78 covering the first frames after state 2, all three herd cycles, the arrival, the scored frame and every atom frame. **Every one is 0-ULP on both actors**, and matches on ``proc``/``facing``/``travel``/``speedF`` besides; Tetra reads stt 3 throughout, so there is NO open frontier and nothing is xfailed (contrast node 1's curve, whose plan left the regime at 83 and hit a wall at 84). Milestone 2 is a console number here: at the scored frame the console's own Tetra is **0.4321 u from genuine coord 274**. Gated `tests/test_plan_console.py` (6 tests, 48 cases) -- and, like every clean-DTM capture, IMMUTABLE: for a fixed input log the console is ground truth and the sim converges to it. |
| `entry_search.py` | **THE SEPARATE ENTRY SEARCH (Dereck s60), and the s45 fork settled by measurement (session 79).** The DUAL of `_generated/tetra_placements.tsv`: the herd is console-confirmed, so Tetra is a MEASURED CONSTANT and the ROLL ENTRY is what gets swept. `tabulated_verdict` is the fork measurement -- standing exactly on `seeds.ENTRY_ROLL_POS` does NOT clip the console's own Tetra (resid **+0.3139 u** against a **1.16e-4 u** window), because her 0.4321 u placement miss is **0.4314 u perpendicular** to the coord thread; route (A) is dead on its premise, not on walk precision. `resid_fn` is the razor's smooth coordinate (the cut ray's offset from the seam vertex S -- the seam PLANES are negative almost everywhere and useless); `acceptance_window` MEASURES the genuine band off the 288 coords rather than assuming it; `genuine_entries` maps the entry locus (coarse residual sweep -> keep near zero -> refine to the f32 dust: blind fine sweeping finds 1 hit in 231k); `locus_metrics`/`entry_gradient` give the shape and the ~1 ULP precision a search must hit; `continue_walk` replays the locked console log and keeps walking (reachability). CLI `{verdict,window,locus,reach}`. Gated `tests/test_entry_search.py` (16). |
| `roll_fidelity.py` | **THE GATE THAT SAYS THE SWEEP IS SCORING THE RIGHT ROLL** (session 80). `walk_then_roll` performs a REAL from-rest walk + A-press turnaround roll + UP+B in the WALLED coupled engine and bakes the same nine tables `extract_schedule_at` does, so the reseed can be diffed per frame against the thing it stands in for. It decides three questions at once: which frame's position and lean the ctx wants (the END of the entry frame -- the pre-entry reading mismatches `chx/chz`), whether the reseed's cold anim/pose state matters (it does not, all nine bit-identical), and whether the armed crash latch matters (a real roll ARMS `_roll_m3570` and does contact the wall mid-roll, but the bonk cone never lines up before the B edge -- 0 of 246 entry x facing rolls differ). Also the honest way to enumerate aims: fire the roll and read the facing back, never trust a commanded one. Gated `tests/test_entry_search.py`. |
| `entry_search.{fast_schedule,roll_entry,aim_alphabet,qualify}` | **THE SESSION-80 SEARCH ENGINE.** `fast_schedule` drops the 22 ms simulated ctx build for a 0.19 ms analytic one, 0-ULP identical over facing x lean x thrust -- the ctx build, not the alphabet, was the whole budget. `roll_entry`/`lean_at_roll` convert a walk endpoint into the entry the game hands you (one 26 u roll step along the AIM, one lean decay tick), both bit-exact; s79 fed the walk endpoint straight in. `aim_alphabet` is 81 wide, not 6 -- the msd 1.0 floor was not physical. And `qualify`/`configuration_band` is the one that matters: of 243 (facing, thrust) configurations only **6** admit a genuine locus, **169** have no leverage at all (grad < 1e-3 -- Tetra out of Co range on the cut frame), and each productive one has its OWN acceptance band, narrower than and offset from the fixture window that is their union. |
| `entry_fan.py` | **THE FAN ON THE NATIVE FLEET, AND THE HONEST DRAW COUNT (session 81).** `graft` transplants the WIRED Python `FreeRun`'s mid-walk state into a `LandCore` -- required because the stripped native config does NOT reproduce the wired replay of the console log (it diverges at log frame 19 on `facing`, the proc-9 re-aim falling back to Tetra's feet), and `LandCore.setup` resets the mid-walk scalars `CARRY` restores. `iter_fan`/`fleet_fan` are `entry_search.walk_fan` on `CourtyardFleet.run_par`: **43596 candidates in 17 s against 1444 s, key AND value bit-identical** to the cached s80 pass (write order is part of the contract -- the reference collapses ~5.5M writes onto 43596 keys, last writer wins). `iter_fan2` adds TWO-SEGMENT holds off the first segment's own junction cores. `BandTable` is the correction that matters: the acceptance band is a function of the **lean** too, so a candidate at a dead lean is not a near-miss -- **83% of the widest pass's draws are dead**, its 72 near-misses are 6, and E[hits] is 0.02 not 0.23. `stream_search` scores a fan stream batch-by-batch against each candidate's OWN band. **Session 82** put the roll's MOMENTUM in that key (`iter_fan(cap=None)` keeps sub-cap endpoints, keyed by their own speedF) and INVERTED the band strategy: with the momentum in the key a band costs 70x the group evaluation it would save, so every draw is evaluated and a band is measured only for the near-zero tail (18 bands over a 43653-candidate pass). **Session 84** collapsed the fan's own HELD-STICK alphabet and made a pass auditable and unbounded: `stick_alphabet` keys the byte grid by what the physics reads (`main_stick_decode`'s `(angle, msd)`) -- **65536 byte pairs are 11405 draws**, one class holding 1944, so a byte-grid fan spends 5.75 frames per frame of new physics; both segments of `iter_fan2` now run the decoded alphabet, preferring an interior representative so `dtm_make`'s 0->1/255->254 cannot rewrite it. `family_of_plan` + `_marginal` price a pass in PREFIX FAMILIES with a per-batch `trace` (the marginal rate is the stop signal, the cumulative one is not); near-misses carry their identity, `dedupe_near`/`draw_key` collapse them onto the DRAW, and `lottery` sums each draw's OWN band instead of the count x a lean-0 width. `dedup_scope='family'` bounds the key set at one family -- the memory ceiling, once the fan got cheap -- with the draw dedup keeping the reported population identical. `confirm_hits`/`confirm` is the A-press replay every hit owes, ranked confirmed-first then frame-minimal. **Session 85** added the THIRD prune, the one the confirm step asked for: `_is_rollable` keeps an endpoint only if the A-press that follows it can actually dispatch the roll (`land.ROLL_FROM` = MOVE/ATN_MOVE -- the endpoint's own `state` IS the A frame's dispatch proc, since the aim is delivered on the endpoint frame and acted on the next), which is exactly why s84's three unconfirmed draws all read `procs [24, 24, 6, 6, 6]`, proc 24 being `MOVE_TURN`. On by default in `iter_fan2` and deliberately OFF in `iter_fan`, whose key-AND-value equality with `walk_fan` is a contract. It drops ~7% of endpoints and saves no fleet time -- a validity filter, not a budget one -- and is gated against a real A-press in BOTH directions. The same session SPLIT the scoring half out to `entry_score.py` (this module was 880 lines) with a name-for-name re-export, so `entry_fan.stream_search` and the rest still resolve. CLI `{gate,fan,fan2,search1,search2,confirm}`, `search1 <jmax> <nbase> <stride> [uncapped]`, `search2 <s1_stride> <j1> <s2_stride> <j2max> <nbase>`. Gated `tests/test_entry_fan.py` (28 + 1 slow). |
| `entry_score.py` | **THE SCORING HALF OF THE FAN (session 85 split; the code is s81-84's, unchanged).** Everything that turns a candidate stream into a counted population: `qualified`/`BandTable` (the per-(facing, thrust, lean, momentum) acceptance band), `stream_search` (batch-by-batch scoring, `family_of_plan` pricing, `dedup_scope`), the counting vocabulary `draw_key`/`dedupe_near`/`hit_draws`/`distinct_near`/`lottery`, and `confirm_hits`. It is one module because every headline number a pass prints has been wrong once, always by counting COPIES as discoveries -- s81's lean-0 bands, s83's camera at 8.00x (48 near-misses that were 3 candidates x16), s84's 118 genuine scorings that were 23 draws. `entry_fan` re-exports the lot. |
| `entry_search.{aim_cell,aim_cells,SIN_CELL_BAM,PRODUCTIVE_CELLS}` | **THE AIM ALPHABET'S REAL ATOM (session 83): the console sine-table CELL, 16 BAM.** `cM_ssin_s16` is `jmaSinTable[(u16)angle >> 4]` with no interpolation, and every term a roll facing reaches goes through it -- travel, cut rotation, Co pose chain, and `roll_entry`'s own 26 u step -- so two facings in one cell bake a bit-identical schedule at a bit-identical entry and are ONE draw. `aim_cells` collapses the 81-aim alphabet onto its 49 atoms (siblings kept, because `confirm_entry` delivers BYTES and the entry FRAME is not cell-quantized); `qualify` runs one configuration per cell, taking `qualified()` from 6 to 3 and the reference pass from "6 near-misses" to the honest 3. It also read as closing the camera axis -- the productive window looked like cells 2551/2552, which the frozen csangle reaches both of. **Session 92: `PRODUCTIVE_CELLS` is a HISTORICAL MARKER, not the window** (it was measured one seed at a time); the real window is 22 LIVE cells in two lobes (`curve_scan`, `fixtures/courtyard_facing_window_s92.json`), so the camera axis is live again -- several live cells are not aimable frozen. The CELL-is-the-atom half is unaffected and still current. Gated `tests/test_entry_search.py`. |
| `entry_search.{roll_nspeed,CtxPool,locus_scan}` | **THE MOMENTUM AXIS (session 82) -- generalized, gated, and measured DEAD.** `roll_nspeed` is `_roll_init`'s clamp off `LandState`'s own constants (`ROLL_NSPEED` is DERIVED from it at the cap, not written down); it threads through `fast_schedule`/`roll_entry`/`build_fast`/`configuration_band`/`qualify`, and `turnaround.extract_schedule_at(nspeed=)` lets the simulated reference follow. `CtxPool` keeps one compiled ctx per (facing, thrust) and swaps only Link's baked schedule via the new `ShoveCtx.set_link_schedule` (1.52 ms -> 0.16 ms), which is what makes a per-candidate configuration key affordable. `locus_scan` is the STRONG form of "is this configuration barren" -- march ALONG the locus re-projecting onto resid 0 at every station, because a one-point band cannot declare a curve dead. The verdict: 2 of 181 momenta productive (both at the cap), every sub-cap one barren along its whole locus and at every facing in the full circle, and an uncapped pass finds the SAME near-misses as a capped one gap for gap. |
| `fixtures/courtyard_entry_s86_console.json` | **THE ENTRY HANDOVER, ON CONSOLE (session 86; LOCKED).** The s78 herd log plus the frame-minimal confirmed entry plan and a real A-press, delivered as one 86-frame movie and truncate-and-read at nine frames (n=78 the control, n=79..86 the entry). All nine 0-ULP on Link x/z/`proc`/`facing`/`travel`/`speedF`/`m351C`/`nspeed` and on Tetra x/z, who stays stt 3 and bit-frozen -- so the console rolls from the entry the walled engine scored, exactly. Gate `tests/test_entry_console.py` (24). |
| `fixtures/courtyard_clip_s86_console.json` | **THE CLIP ATTEMPT, ON CONSOLE (session 86; LOCKED).** The same log extended to the thrust. Carries the eight console samples across the roll, the `ShoveCtx` prediction it is being judged against (`genuine`, `old`, `new`, `push`, the window), the measured Tetra wall brace (plane -990.255615 + R 50 = -940.255615) and the `tetra_ulp` price: **one f32 step of her x flips `genuine`**. The console did NOT clip. Gate `tests/test_clip_console.py` (8 + 7 xfail(strict) on a contiguous open suffix). |
| `body_cyl.{co_leans,roll_co_center,roll_co_chain_consts}` + `from_f0.FreeRun(walls_tetra=)` | **THE TWO TERMS THAT MADE `genuine` A FALSE POSITIVE (session 87), one per engine.** `walls_tetra=` runs Tetra's own `mObjAcch.CrrPos` (R 50 / half-H 30) in the courtyard tracking, where she had no BG collision at all and the clip roll drove her through the back wall -- attaching it took the whole s86 xfail frontier to 0 ULP on both actors in one change. `co_leans(link)` is the OTHER half: the Co centre takes the turn lean TWICE, one frame apart (`setWorldMatrix` base = the DRAW lean, `jointBeforeCB` `body_chn` twist = the POST-update one), and the baked chain the native `ShoveCtx` sweeps carried only the base. Below ~30 BAM the twist rounds to the identity in `jmaSinTable`, which is why the live lean capture (max 28) could never decide it and why the search was wrong only where a candidate's roll carries a real lean; at -388 it is ~0.35 u of centre. All four schedule bakers (`turnaround.extract_schedule_at`, `fast_shove.extract_schedule`, `entry_search.fast_schedule`, `roll_fidelity.walk_then_roll`) and `cc_stepper.link_co_center` pass both leans. KB `knowledge/mechanics/link-co-centre.md`; the overturned claim in `knowledge/history/co-centre-body-chn-twist.md`. Gated `tests/test_body_cyl.py` (incl. the fixture's own lean bound) + `tests/test_clip_console.py`. |
| `entry_score.rescore` (CLI `entry_fan rescore <hits json>`) | **ASK A FINISHED PASS AGAIN, ON THE ENGINE AS IT STANDS (session 87).** One sweep per hit, grouped by configuration so the `CtxPool` re-schedules instead of recompiling the courtyard. A hit is a claim about the engine that scored it, and when the correction is a function of the candidate -- as the `body_chn` twist is, through the lean -- it cannot be reasoned about hit by hit. On s85's 49: **7 kept**, the 42 rejected all past -1e-3, the survivors' residuals unchanged to the bit. What it does NOT give you is a re-measured axis: the hits are the old engine's, so the survivor rate is a lower bound. |
| `fixtures/courtyard_entry_s87_rescored.json` | **THE 49 RE-SCORED (session 87).** A MODEL output, not a console capture -- every hit of the s85 pass with its verdict and residual on the fixed engine beside the recorded ones, pinned so the engine cannot move under the candidate set without the gate naming which hits moved. 7 genuine, frame floor 5. Gate `tests/test_entry_fan.py`. |
| `fixtures/courtyard_entry_s87_hits.json` | **THE CURRENT CANDIDATE LIST (session 87).** s85's scoping re-run on the fixed engine (`search2 2 1,2 1 6 2`, 39.3 M candidates, 4997 s): **55 distinct genuine draws, 55/55 confirmed by a real A-press and 55/55 DTM-deliverable**, frame floor **4**, five at gap exactly 0. Yield unchanged vs s85 (1950 near draws / E[hits] 4.547 / 0.2417 near per family, against 2007 / 4.638 / 0.2487) over a largely NEW population -- only 7 of s85's 49 are in it, which is why a re-score is a lower bound and not a measurement. A MODEL output, pinned with the list itself rather than a summary (re-sweeping all 55 is 0.1 s, replaying them 2.5 s). Gate `tests/test_entry_fan.py`. |
| `fixtures/courtyard_attack_gate_s88_console.json` | **THE PRESS THAT DID NOT ROLL (session 88; LOCKED).** The frame-minimal hit of the s87 55, delivered: the movie went out exactly as authored and Link never entered FRONT_ROLL at all -- MOVE at the sampled frame, walk facing continued past the A-press, and **Tetra bit-identical to her pre-roll position** because he never reached her. `setDoStatusBasic` (2220) only sets `dActStts_ATTACK_e` for `mStickDistance > mBasic.field_0x1C` = **0.75**; this aim decodes to 0.5705, so the press was `PUT_AWAY` and SHEATHED the sword. With s86's aim at 0.889 the two deliveries BRACKET the threshold on the real game. Carries the falsified model prediction as `model_of_the_day`. Gate `tests/test_attack_threshold.py` (10). |
| `fixtures/courtyard_clip_s88_console.json` | **THE CLIP, ON CONSOLE (session 88; LOCKED) -- `genuine` is a measured number now.** The frame-minimal survivor of the re-confirmed list delivered end to end: at the cut frame Link is **bit-identical to the prediction, 49.8582 u off `old` and out through the seam**, and five frames later he is in `daPyProc_FALL_e` off the courtyard floor. Tetra bit-frozen, stt 3, both samples. Nothing past `cut_i` is claimed -- the composite is a flat-ground engine and the console has left the floor (`post_cut`). Gate `tests/test_clip_delivered.py` (10). |
| `fixtures/courtyard_entry_s88_hits.json` | **THE CANDIDATE LIST, TWICE FILTERED (session 88).** The s87 55 re-confirmed against the ATTACK gate (36 `dropped` -- their aim cannot roll) and then against the CROSS-ENGINE gate (`rejected`): **15 deliverable, frame floor 5**. Each row carries its `cross_engine` block (handover, worst ULP over the roll, cut-frame agreement, `ShoveCtx` lunge vs the composite's own move). Row 0 is the one delivered. A MODEL output; regenerate with `_notes/s88_{confirm,agree}.py`. Gates `tests/test_clip_delivered.py` + `tests/test_entry_fan.py`. |
| `cross_engine.py` (+ `entry_score.confirm_hits(cross_engine=True)`, CLI `entry_fan confirm <hits> xengine`) | **THE CROSS-ENGINE PRE-FLIGHT, PROMOTED INTO THE SCORING LOOP (session 89).** Session 88 ran this diff by hand after the confirm step and it rejected 4 of 19 -- one of them the frame-minimal candidate the next delivery would have gone to -- so it is a filter, not a diagnostic, and it now runs where the other two do. `composite_log`/`composite_rollout` are s88's composite path verbatim (the wired delay-1 `FreeRun`, culled mesh on BOTH actors, plan frame i == plan frame i); `agree(hit)` returns the handover, `genuine`, `worst_ulp` over the roll on both actors, `cut_ok`, `predicted_lunge` vs `composite_moved`, and `deliverable` = all of them. `blocked(res)` names the expensive class (the composite refusing a lunge `ShoveCtx` scores ~50 u). Costs one rollout (~0.4 s) per confirmed hit and no console runs; only confirmed + DTM-clean hits are rolled out. Reproduces s88's 55 -> 19 -> 15 with floor 5 in 10 s. **A 1-ULP pre-cut divergence can still end in a bit-identical cut frame, so `cut_ok` alone is not agreement** -- `deliverable` demands `worst_ulp == 0` too. Gated `tests/test_cross_engine.py` (12). |
| `fixtures/courtyard_entry_s89_hits.json` | **THE SAME PASS AS THE PRE-FIX ENGINE FILTERED IT (session 89; superseded as the candidate list by the s90 file below).** The s85/s87 scoping re-run once the ATTACK gate actually reached the pass (`search2 2 1,2 1 6 2`, 39.3 M candidates, 4701 s): the same 81 walkable scorings / **55 draws** at the same entries and residuals as s87 -- the sine-table CELL is the atom and 40834/40841 are both 2552, so the gate moved the cell's REPRESENTATIVE (`[95,168]` msd 0.5705, sheathes -> `[82,186]` msd 0.9817, rolls) rather than the population. **0 of 81 aims are unrollable (was 57), all 55 confirm (0 dropped, was 36), 51 of 55 deliverable at frame floor 4** (s88: 15 at 5). The 4 rejections are the Co-centre seam and each carries its WHOLE hit, so it can be re-run from this file. A MODEL output; regenerate with `entry_fan confirm <hits> xengine` + `_notes/s89_pin.py`. Gate `tests/test_entry_fan.py`. |
| `fixtures/courtyard_centre_seam_s90_console.json` | **THE BLOCKED-CANDIDATE DELIVERY THAT SETTLED THE Co-CENTRE SEAM (session 90; LOCKED).** The experiment session 89 named: `rejected[0]` of the s89 pass, where `body_cyl` predicts a 49.8582 u lunge out through the seam and `foot_fk` predicts 0.1534 u and no clip -- **49.9665 u apart, so the console cannot land between them**. Three truncate-and-read samples (the cut, plus two pre-cut controls chosen where the ports differ at 1 and 10 ULP): **all three 0-ULP on `body_cyl`, on both actors**, and it CLIPPED. Carries each sample's two PRE-FIX predictions, which is what makes it a measurement rather than three ordinary reads. Root cause one layer down: the ports were sampling `rollf` at two different f32 FRAMES (`FrameCtrl` held `enter_roll`'s Python double `1.1`; `J3DFrameCtrl::mRate` is f32; at 2.2 -> 3.3 the f32 sum is an exact tie the double falls short of). Fixed at the `FrameCtrl` boundary -> the ports agree bit-for-bit, the DEFAULT composite reproduces this capture, all four rejections deliver. Gate `tests/test_centre_seam.py` (8); KB [`model/anim-frame-is-f32.md`](../../knowledge/model/anim-frame-is-f32.md) + [`mechanics/link-co-centre.md`](../../knowledge/mechanics/link-co-centre.md#the-two-ports-and-what-was-actually-between-them), history [`co-centre-two-ports.md`](../../knowledge/history/co-centre-two-ports.md), razor rule 11. |
| `fixtures/courtyard_clip_s90_console.json` | **THE FRAME-MINIMAL CLIP, ON CONSOLE (session 90; LOCKED).** Row 0 of the s90 list -- a **4-frame** walk-up, one frame under the s88 delivery, and rejected by the cross-engine filter until the seam above was settled -- delivered end to end in ONE run. At the cut Link is bit-identical to the prediction, **49.7368 u off `old`** and out through the seam; five frames later `daPyProc_FALL_e` off the courtyard floor, with Tetra bit-frozen and stt 3 at BOTH samples. Nothing past `cut_i` is claimed of Link (`post_cut`) -- the composite is flat-ground; Tetra is gated there anyway. So milestone 2 is console-confirmed at the FRAME FLOOR. Gate `tests/test_clip_frame_minimal.py` (6). |
| `fixtures/courtyard_entry_s90_hits.json` | **THE CURRENT CANDIDATE LIST (session 90).** The s89 pass re-confirmed on the fixed engine: **55 of 55 deliverable, frame floor 4, 0 rejected, 0 dropped** -- the seam's whole cost recovered, and the s89 rows plus its four rejections are exactly these rows. Frame-minimal row 0 = plan `[0,208,110,2,169,192,2]`, aim `[82,186]`, facing 40841, thrust 15, m351C 64761, entry `(-1531.1784667969, -781.7215576172)`, resid +6.2429e-05, 4 walk frames, lunge 49.7368 u. A MODEL output; regenerate with `entry_fan confirm <hits> xengine` + `_notes/s89_pin.py`. Gate `tests/test_entry_fan.py`. |
| `fixtures/courtyard_entry_locus_s79.json` | **THE ENTRY LOCUS** -- 1735 genuine roll entries for Tetra pinned at her console-measured herd endpoint, at facing 40835 / m351C 0, plus the acceptance window, the fork verdict, the gradient, the m351C sensitivity table and the reachability rows. One thin curve 104 u long; **856 inside the 230 u follow bar** = the usable target, nearest 49.7 u from where the escape leaves Link. DERIVED, not measured -- regenerable by `python -m harness.tetrapush.entry_search locus` (~250 s), pinned so the gates do not pay the sweep. |
| `fixtures/courtyard_terminal_family.json` | **THE TERMINAL FAMILY AT THE DELIVERED STATE (session 144)** -- 8 `terminal.scan`s over the axes the family had never been scanned at: thrust across the whole realizable window (s124 did 14 only), the DELIVERED body lean 648 beside the scanned 0, and two delivered roll facings beside the seam's own. Every record carries **`roots` beside `genuine`**, which is the point: a bare zero cannot separate absent geometry from a thin scan (`[[infeasible-needs-proof]]`), and 2390 roots converting none at thrust 13 against 2513 -> 40 at thrust 14 is a statement about the CUT. Also banks `delivery` -- what all 49 ladder rungs actually hand over (lean 648, nspeed 26.0, Tetra never past `FOLLOW_ENGAGE_DIST`, last-roll facings 26637..38782 against a seam window of 40768..41183, `along` 42.0..56.0). Read through `terminal.clipping_thrusts` / `clipping_family`, which return **None** at an unmeasured terminal rather than a neighbour's answer. Built by `_notes/s144_bank.py`; gated `tests/test_terminal_family.py` (12 fast + 1 slow re-scan). |
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
| `seeds.py` | **The planner SEED FACTORY** (session 22, restored session 28, f1-closed session 29): `make_freerun` builds the fully self-contained `FreeRun` (camera + Zl1 look + NeckLook wired, no injections -- the session-21 gate config) from the locked fixtures, now passing the exact f0->f1 seed push (`seed_push_f0` = the perop ΔTetra) so the rollout is 0-ULP in POSITION from f1 (verified: the `make_freerun` self-contained rollout is 0-ULP vs perop over the whole DTM window); `load_placements` loads the 288 genuine `tetra_placements.tsv` coords; `dtm_input_at` is the movie-window input accessor; `load_env` loads the fixture set (incl. `perop`). `make_freerun(tetra_at=)` re-seats Tetra's seed for clean no-contact template rollouts (falls back to the settled-centre approximation, since the recorded push no longer applies). **Session 131** added `make_freerun(native=)`: the SAME wired configuration on the C step, with the camera driven from `LandCore.attn_y` (0-ULP either way, `tests/test_native_camera.py`); `cycle1_nodes(native=True)` hands it to the whole chain. Pure fixture plumbing (no model content). |
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
| `away_walk.py` | **The AWAY-WALK escape atom** (session 65; Dereck's recipe: the herd junction's convert-to-positive with the roll replaced by a BACKWARDS SLAM -- "L+up, left/right, slam down"). `escape_atom` = [optional ESS turnaround when the EBS still faces her] -> ONE L frame + the toward-Tetra stick held one more (the proc-7 DIR_BACKWARD negation fires on the next dispatch frame, L already released: **-25.727 -> +17.614 POSITIVE**, motion unchanged -- still placement frames) -> one ~90-deg rotate frame (defeats the genuine-flip gate) -> backwards slam (`procMoveTurn(1)` halves the POSITIVE run onto the reversed travel: **+8.5 up-herd, NO zero crossing**) -> exit stick to the walk cap (f8), stopping at the handoff (receding at 17). Separation = the slam frame; Tetra's residual **34.8-40 u, lat < 9** (the terminal's deterministic undershoot); **3 post-separation sub-17 frames** (`DIP_BUDGET`, the halving dip + two accel frames -- Dereck confirmed the dip is inherent). `probe` sweeps turnaround/rotate-side/exit and ranks L-cone compliance FIRST (an L that locks her = the facing was wrong), then dips, then receding-at-cap, then entry progress. Measured traps in the module docstring (slam-first decays through zero ~12 dips; no-rotate re-fires the negation; side-stick-on-negation-frame reads DIR_SIDE). **Session 66 hardened it for consumption as rule 3**: `fires(res)` = the shared acceptance (l_ok + not followed + **SEPARATED** (`freeze_f` -- a deep terminal can recede at the cap with the centre still inside the 80 u bar, Tetra still taking push; the s66 solve crashed on exactly that state) + dips <= `DIP_BUDGET` + `rec17_f`); the atom runs until receding-at-cap AND separated; probe clones detach a wired camera (`_clone_for_atom`, the commanded-csangle convention -- the csangle used is recorded on the result, its C-stick-slew realization is the camera leg, like the roll stage's `target_cs`); a no-snap-window terminal can still run the NO-turnaround variants on its live csangle. **Session 74 priced its FRAMES**: rows carry ``tstep`` (Tetra's own displacement that frame -- not a ``tres`` difference, which under-reads a turning plow) and `push_profile` reads them against `objective.PUSH_CEILING`. On the shipped 75-frame plan the last ROLL pushes her **12.911 u/frame, 99.3% of the ceiling, over all 19 frames**, while the escape's 4 frames push **9.177, 70.6%** -- profile **16.506 / 0.000 / 12.469 / 7.732**, i.e. the **proc-7 negation frame plows NOTHING** and the slam plows on a halved speed -- so the escape costs **1.18 frames** of the 2-frame timeloss by itself, and what it can RECOVER of the placement is bounded by what it pushes (max over 85192 firing variants: -0.24 u at ``freeze_f`` 1, 22.94 at 3, 34.54 at 4). That is what makes the frame rung a property of the ARRIVAL -- see the session-74 `## Plan / status` box for the ledger. **Session 110 gave the atom a TAIL** (``exit_run``, + `tail_variant`): the break condition above stops at the handoff, which is right for the landing and silently fixed the ARRIVAL at whatever the last frame held -- Link beside her, pointed down-herd, often still flying backwards on the flip (the banked ``shallow`` arrival hands off at ``speedF`` **-23.217**, which fans an EMPTY entry cloud since `entry_fan.iter_fan2` keeps junctions only at ``WALK_CAP``; two tail frames settle it at 17.0). Holding the exit stick past the handoff moves the arrival and NOTHING else -- her coordinate is bit-identical while the separation holds, and the frame it stops holding `fires` refuses the variant -- so the tail is bounded by the freeze and the 230 u follow bar, both already modelled. `tail_variant` reads every tail length off ONE rollout (bit-exact against a fresh one), which is what makes the axis nearly free to enumerate. KB: [`knowledge/strategy/the-arrival-is-payable.md`](../../knowledge/strategy/the-arrival-is-payable.md). Gated `tests/test_away_walk.py` (10 + 5 tail). CLI `python -m harness.tetrapush.away_walk {probe\|trace}` (``trace`` prints the profile). |
| `full_herd.glide_probe` / `lateral_authority` | **The LAST cycle's keep and the measurement behind it** (session 62). `lateral_authority` holds each terminal-alphabet stick for 6 frames and reads the SPREAD of Tetra laterals reached -- the plow's sideways authority, **2.92-2.96 u/f** across contact depths on the synthetic bed (CLI `full_herd lat`, ~20 s) and 3.5-5.9 on the real cycle-3 endpoints, against `PUSH_CEILING` 13.0 for the along axis; that ~4.5x is what `objective.LATERAL_RATE` encodes. GOTCHA: `synthetic_hot_arrival`'s `d_short`/`lat_off` translate BOTH actors rigidly, so no relative measurement moves with them -- sweep `feet`. `glide_probe` is `roll_probe`'s counterpart one stage later: the last cycle keeps endpoints for a TERMINAL, so measure the terminal -- run a short narrow glide (5 frames, beam 4, ~1 s) and rank the endpoint by the best `frames + thread_frames` it reaches. Wired as `extend_cycle(glide_keep=True)`, which `chain_herd` sets on the last cycle only. It DOES discriminate (the s62 cycle-3 survivors span 74.24..87.14, and it demotes the endpoint `thread_cost` likes best) but was **INERT on the s62 beam** -- the top 8 after dedup are unchanged. Gated `tests/test_full_herd.py` (the measurement, the disagreement on two synthetic arrivals, and the wiring). |
| `aim.py` | **THE HANDOFF AIM -- where the last push frames POINT** (session 67), and the module that inverted s63-s66's "lateral deficit" reading. `push_step` = the plow as an **exact one-frame oracle**: ``f32(Tetra + (CO_RADII_BAR - centre_feet)/2 * unit(Tetra - exec_centre))`` is `FreeRun.step`'s next Tetra bit-for-bit on every contact frame (the pipeline acts 2 frames late, so the frame's push is already decided by the state) and exactly 0 at the bar -- so Tetra's side of a placement is analytic and an aim is an exact quantity, not a proxy. `eject_unit` = that ray in herd coords; **`aim_window`** = the directions from a Tetra position that reach the target thread, which is a RAZOR (**0.53-0.62 deg** at the s66 handoff range) because the thread lies 12.2 deg off the herd axis and the approach comes in 13-14 deg off it, i.e. she arrives nearly END-ON; `aim_miss` = how far the current aim misses the 47.6 u SEGMENT, in u, comparable to `objective.PLACEMENT_BAND` (the s66 endpoints: 12.28 / 11.89 / 47.72 u, 10-46 deg steep); `centre_lat_needed` = the same statement as Link's job (his exec centre must sit 9.15 / 10.86 / 40.96 u lower in lateral); `push_reserve` = ``CO_RADII_BAR - centre_feet``, the ejection already stored in the overlap; `landing_miss`/`handoff_target` = the EXACT half and its inverse (where a MEASURED escape residual leaves her, and the handoff a given residual demands -- the chain's target is the coord MINUS the escape's ~44 u: along ~894, lateral ~+2.5); `handoff_spec` = the three numbers in one call. **`corridor_aim_error`** is the same measurement MID-CHAIN, and it is what decides straightness: the push law integrates, so the direction a roll carries Tetra is the mean of its aims (s66 plan, three rolls: mean aim +2.55 / -6.42 / +16.56 deg vs travel +2.98 / -6.36 / +18.13, ~205 u each), the entry aim predicts it to a few degrees, and the human enters his two recorded rolls at +1.22 / -0.70 deg and finishes 44 frames in **0.71 u** off the corridor. The lateral that steers the push is the exec CENTRE's, not the feet's (s66 roll-2 entry: feet +2.22 u off her lateral, aim -10.84 deg). Gated `tests/test_aim.py` (6): the 0-ULP oracle, the razor window, the aim<->centre-lateral inversion, **the terminal alphabet's 2-frame inertness**, the roll-aim law on the HUMAN's own rolls, and the handoff-target round trip. CLI `python -m harness.tetrapush.aim {spec\|beam}`. |
| `full_herd.escape_probe` | **The LAST cycle's endpoint keep, one stage out from `glide_probe`** (session 67): rank an endpoint by what its real ESCAPE lands (`away_walk.probe` -> `aim.landing_miss` + the frames to the slam), because the terminal GLIDE was measured to have no authority over Tetra at all -- the whole `_terminal_alphabet` moves her identically for four frames (`aim`), which is why six terminal rank configurations came out byte-identical across s61-s63. Wired as `extend_cycle(escape_keep=True)` (a rank AND a keep share) and `chain_herd(last_escape=True)`, superseding `glide_keep` on the last cycle; ~2-5 s per survivor. Result on the s66 cycle-2 beam (461 s, no chain): 21 survivors, **18 fire, best lands 45.62 u off the thread**, and the keep is INERT (byte-identical 8 nodes) -- the right metric, proving the cycle-3 stage cannot reach the handoff. |
| `cloud_land.py` | **THE LANDING, MEASURED INSTEAD OF PREDICTED -- and the honest statement of what a keep in that position can do** (session 107). `escape_probe` (the row above) ranks against `objective.placement_thread`'s FIT, and session 106 measured that a fit through the frame-minimal target set is fiction: the set is a ~170 u-wide 2D CLOUD of rows, so every beam ranked by that miss was landing-blind and the ~6 u floor it reported was the CUT's. `cloud_landing` replaces the predictor with the ENUMERATION -- the whole atom knob grid (`atom_cloud` = `away_walk.probe`'s loop with the rank removed, 672 variants, ~28 s) priced as WHOLE candidates: herd frames + the atom's own LOG length + the row's `plan_cost` + the remaining miss at `PUSH_CEILING`. Every term is one this work has already been burned by: the log not `freeze_f` (s105's off-by-three, the banked 101), and the row's own cost because the rows are 19-23 frames apart (s104), so a landing 6 u from a cheap row beats 1 u from an expensive one. `in_band` (inside `objective.PLACEMENT_BAND`) is reported SEPARATELY from the rank, since only it answers "solved". Wired `extend_cycle(cloud_keep=)` with a ``cloud_cap`` that PRINTS what it did not enumerate (unprobed survivors keep an infinite bound, never a default). **But note where that keep sits and what it therefore cannot do:** it is an ENDPOINT keep on the last cycle, so it reorders a set the junction and aim cuts already fixed -- it names the best of the survivors, it does not create better ones. The axis with authority is per-AIM, inside `roll_probe`, which cannot afford 28 s; hence `residual_fan` + `predict_bound`, the cheap half: the residual is a FAN (s106: lateral never below +13.8 u, so a point-shift like `aim.handoff_rows` measurably steers the rank toward badly-converting endpoints), so the predictor is a minimum over the fan crossed with the rows, in the same currency as the enumeration, at microseconds an aim. It is OPTIMISTIC by construction (the fan's lateral tracks Link's offset from her at -0.53 u/u), so it sizes the CUT and the enumeration makes the CLAIM. KB: [`knowledge/strategy/landing-keep-on-a-cloud.md`](../../knowledge/strategy/landing-keep-on-a-cloud.md). **Session 110 made it JOINT**, because a landing in the band is half a candidate ([delivery-is-two-predicates](../../knowledge/strategy/delivery-is-two-predicates.md)): `station_map` joins the rows to the LIVE stations their `plan_cost` was priced at (`_generated/s104/cost21_hunt_*.json`, and it REFUSES a dump hunted at another walk budget, since `FREE_REACH` is derived from it), `arrival_frames` charges the station gap past that free reach at the walk cap -- `objective.remaining_frames`' twin for the other half -- and `_joint_row` chooses the row with both addends, which genuinely moves the choice (a row 6 u from the landing whose stations sit 130 u behind Link loses to one 20 u away the arrival already covers). ``exit_runs`` crosses the grid with the atom's tail, and ``joint`` is the new claim: in-band AND owing no arrival frames AND settled at the cap. Note the bound is TAIL-INVARIANT by construction (the gap is priced at the cap, which is what a tail frame delivers, measured identical at 24 of 24 endpoints) -- the tail buys DELIVERABILITY, not frames. Gate `tests/test_cloud_land.py` (25, incl. the containment check that the enumerated grid holds `away_walk.probe`'s own chosen variant). |
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

### Launching a search that runs longer than ten minutes (session 107 -- two traps, both real)

The chain stages here take 30-90 minutes, which is longer than an agent session's background-command
budget, and two of the obvious ways to launch one silently lose the run:

- **A `nohup ... &` from a tool-call shell dies with the call's process group.** It looks fine (the
  process reports a pid, the log gets its banner) and is gone minutes later, with no traceback and no
  completion line -- indistinguishable from a run still working. Launch it as a genuinely detached
  Windows process instead: `Start-Process python -ArgumentList "-u","<script>" -RedirectStandardOutput
  <log> -RedirectStandardError <err> -WindowStyle Hidden -PassThru`, and watch the pid, not the log.
- **Reuse the same log path across relaunches and the record becomes unreadable as a SEQUENCE.** A
  killed writer's bytes survive in the file (Windows leaves NUL padding where the handle was), so a later
  run's lines end up adjacent to an earlier run's with nothing marking the seam. Concretely: two
  "probing N of M endpoints" lines that belong to *different nodes of different runs* read as two
  different answers for the same node, which looks exactly like nondeterminism in a search whose whole
  value is that it is reproducible. (It was not -- the counts are per node and both were correct.) Give
  every launch its own log file, and if a log has holes in it, rerun rather than reason from it.

And always pass `-u`: without it a redirected run buffers, so the log stays empty for its whole first
stage and a healthy run is indistinguishable from a hung one.

**Do not edit a `.py` file while a `pytest` run is live** -- and in this repo that rule has teeth, because
many gates here are WIRING gates that assert on `inspect.getsource(...)`. `getsource` resolves through the
loaded code object's file *and its first line number*, so an edit that shifts lines under a running
process makes it return an unrelated fragment of the new file. Session 107 spent a cycle on five
"failures" that were all this: three `test_full_herd` wiring assertions comparing against a stray
`orders.append(...)` line, plus two of its own new tests. Nothing was wrong with the code, and no
attribution work was needed once the mechanism was recognised -- but a 21-minute suite had to be re-run
from scratch. Land the edits first, then gate.

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
      - [~] **THE SEARCH IS WRITTEN, GATED AND RUNNING: THE WHOLE HERD SET THROUGH THE TERMINAL
            MACHINERY THAT ACTUALLY DELIVERED THE CONSOLE CLIP, ORDERED SO THE CHEAPEST PLAN IN THE
            SPACE IS TRIED FIRST (session 150).** `harness/tetrapush/overnight.py` +
            `overnight_io.py`; 17 gates in `tests/test_overnight_driver.py` (1.7 s).
            - **SESSION 152 -- THE REDISCOVERY GATE RAN FOR REAL (s151's item 0): ONE GENUINE RAZOR HIT
              SURFACED, `accept()` REFUSED IT, AND THE REFUSAL'S ROOT CAUSE IS NOW KNOWN AND
              CROSS-CONFIRMED TWO INDEPENDENT WAYS.** Seeded the console's own herd with its real
              conversion REMOVED (`log[:71]`) and ran `fan_exact(atom=True) -> score -> accept` for
              real, widening walk 7/8/9. Walk 7 and 8: 0 genuine, but overlap landed within 0.0006u /
              0.00007u of the console's own +1.2259 target. **Walk 9: ONE genuine razor hit** (thrust
              15, would total **99 frames -- 2 faster than the console's 101**) -- but `accept()`
              refused it at `confirm_entry`, on a predicted-vs-measured gap of facing 11 BAM / walk
              0.013u / entry 0.027u, tiny in absolute terms but nonzero against `confirm_entry`'s exact
              `==` (`[[zero-ulp-tests-only]]`, no tolerance to fall back on). Widening stopped there
              (escalating per-walk cost, and the walk-9 signal was already the useful one).
              - **`overnight.score` was silently discarding exactly the data needed to look at a
                near-miss** -- `best_overlap`/`best_resid_in_contact` were bare running scalars with no
                record of which candidate produced them, so inspecting one meant a full expensive
                re-run. Fixed: `best_overlap_row`/`best_resid_row`/`near_rows` (capped, `near_capped`
                flagged) now carry the full candidate identity, same shape as a genuine `hit`, so
                `composite_log`/`accept` can rebuild and inspect ANY of them without recomputing, ever
                again. Purely additive, gated (`tests/test_overnight_driver.py` unchanged, 23/23; full
                default suite 1256 passed, byte-identical to pre-fix).
              - **Surveyed `confirm_entry` against every genuine/near-miss/best-overlap/best-resid row
                across walk 7/8/9 (86 rows, using the fixed `score`): 0/86 pass, and the facing delta is
                NEVER continuous -- it is EXACTLY one of three discrete values, 11, 31 or 81 BAM, every
                single time.** Position error tracks the bucket (11-BAM rows smallest, 81-BAM rows
                worst), naming facing error as the actual driver, not independent noise.
              - **ROOT CAUSE (cross-confirmed): `LandCamera` fires a real, documented 1-frame
                followCamera blip on every L-press** (its own module docstring); re-entering manual mode
                resets the camera's internal yaw TARGET to wherever the yaw-chase happens to sit at that
                instant. `entry_camera.cam_trail` -- what the fast search injects as its camera
                projection -- builds its own reference replay with an L-free, constant input, so it
                never sees this and injects the PRE-blip angle for every candidate whose walk presses L
                (every escape-atom-junction candidate, unconditionally, by construction). An isolated
                sweep of the L-press timing alone (no atom/rotate/slam) reproduced **-81 / -31 /
                -11 (saturating)** exactly, with zero free parameters shared with the empirical survey
                above -- about as clean a confirmation as this gets. **NOT fixed**: a real fix means
                teaching `cam_trail` (or a sibling) the candidate's real button/stick schedule instead
                of a bare C-stick byte, new 0-ULP gates, and a decision on whether ordinary `_families`
                L=1 candidates need the same treatment -- scoped, multi-piece, left for next session.
              - **Separately, built + wired a full-fidelity native `confirm_entry` (Dereck: "why
                wouldn't confirm_entry also be native?") -- it exists, but REGRESSES 5 tests, unmerged.**
                `seeds.make_freerun(env, native=True)` already runs physics + both look models in C with
                the camera still live-computed (never injected), already 0-ULP gated including L-press
                cases; `entry_search.continue_walk` grew a `native=` flag and `confirm_entry` opted in,
                plus a real fix along the way (`continue_walk` was reading the never-synced
                `link.csangle` instead of the authoritative `run.csangle`). Its own new test passes
                standalone, but the full default suite regresses 4 `test_entry_camera.py` cases + 1
                `test_entry_ledger.py` case that are clean on the unmodified branch -- likely the
                csangle field swap, not yet root-caused. **Preserved, not merged**: committed to
                `dmiller/tetrapush-native-confirm-entry-wip` (commit `e2b396e`), worktree removed, not
                pushed. **NEXT (Dereck: resolve that branch, then continue the search)**: (1) trace the
                5-test regression on that branch to a root cause and fix it (same per-frame-diff rigor
                as the camera-blip finding, not a guess); (2) teach `cam_trail` the real L/button
                schedule so escape-atom candidates stop being scored against the wrong camera; (3)
                re-run the widened rediscovery sweep (7..13) with both fixes in and see whether a
                genuine, deliverable, <=101-frame plan actually surfaces -- THAT is what would satisfy
                s151's hard gate for real, not a bound and not a mechanism proof.
              - **SESSION 153 -- ITEM (1) IS RESOLVED: THE NATIVE `confirm_entry` BRANCH IS FIXED AND
                SQUASHED INTO THIS ONE, AND THE REAL BUG WAS A ONE-FRAME SHIFT, NOT THE FIELD ITSELF.**
                The "real fix along the way" above had it backwards: `link.csangle` was correctly
                flagged as stale on a native step, but the replacement -- a POST-step `run.csangle` --
                reads the NEXT frame's committed value, not this one's. The camera runs at the END of a
                frame and commits the csangle the frame AFTER reads, so the swap shifted every row's
                csangle forward by exactly one frame, in BOTH engines, wired included. `entry_camera.
                cam_trail` builds the search's whole camera reference off this exact field, which is
                why the regression landed precisely on `test_entry_camera.py` (4 cases) +
                `test_entry_ledger.py` (1) and nowhere else. Confirmed empirically before fixing, not
                guessed (`_notes/s153_csangle_shift_probe.py`): the OLD `link.csangle` read always
                equals `run.csangle` taken BEFORE that frame's `step()`, never after, in both wired and
                native runs alike. Fix: capture `run.csangle` before stepping -- exactly reproduces the
                old wired behaviour and fixes the real native staleness at the same time, since
                `run.csangle` (unlike `link.csangle`) is threaded through `_run_camera` on both step
                paths. Full default suite: 1257 passed, 0 regressed. Squashed onto this branch
                (`f39a97a`); `dmiller/tetrapush-native-confirm-entry-wip` is fully folded in and can be
                deleted whenever Dereck wants -- not done here (branch deletion is his call).
                **NEXT (items (2) and (3) above, unchanged and still the real blocker)**: teach
                `cam_trail` the real L-press followCamera blip, then re-run the widened rediscovery
                sweep (7..13) with both fixes in -- THAT is what satisfies s151's hard gate for real.
            - **THE PIPELINE IS THE ONE THAT HAS EVER DELIVERED, POINTED SOMEWHERE NEW.**
              `entry_fan.iter_fan2`'s OpenMP `prange` fleet -> `ShoveCtx.sweep_par` ->
              `entry_search.confirm_entry` (a REAL A-press) -> `cross_engine.agree` (the walled
              composite, frame for frame) is what produced the banked 101, and it had only ever been
              run off ONE herd. Measured on this hardware: the fan is **216k core-frames/s at 12
              threads, 74k at one**, so **11 workers x 1 thread beats one 12-thread process 3.8x**;
              the razor sweeps **75.5k scorings/s**; the walled terminal steps **4220 clone+steps/s
              native against 350 in Python (12x)**.
            - **THREE STAGES SILENTLY REPLAYED THE CONSOLE ARRIVAL WHATEVER SEED THEY WERE HANDED**
              -- `walk_fan`, `confirm_entry` and `entry_camera.cam_trail` all called
              `continue_walk(...)` without ``log=``, the same defect `entry_fan.base_core` had fixed
              at the fan in s105. Any of them pointed at a ladder rung measured the wrong herd. Fixed
              in place, inert at every default.
            - **THE FAN NOW CARRIES TETRA** (`entry_fan._fan_chunk(with_tetra=)`): every pass before
              this scored a whole fan against ONE pinned Tetra, which is true only while Link has
              broken contact -- true of the console arrival, false of a herd end still plowing her.
              The razor takes her per item, so **the stay-in-contact and walk-away regimes are one
              population** instead of two searches with two ranks (s149's open axis).
            - **``at_cap`` IS A THRESHOLD AND THE OLD PRUNE WAS AN EQUALITY.** Every fan kept
              ``speedF == 17.0``; the conversion lands at **+17.6** (17.183998 and 17.833548 measured
              on real rungs this session), so the equality refused the only states worth searching.
              It is `roll_nspeed(speedF) == 26` now.
            - **AND A PLAN NEEDS AN L AXIS, WHICH THE TRIPLE PLAN ENCODING CANNOT EXPRESS.** Measured
              on BOTH engines off rung 5: a bare walk-up from a herd end tops out at speedF **exactly
              12.000, proc 9** over 1206 Python rollouts and 57025 native ones -- Tetra is in the
              front cone at the handover, so the L locks the ACTOR and the proc-9 slide caps at 12.
              The **cone-clearing pre-frame** is the whole difference (s149 said so; this is it
              re-measured from the other side). Plans are now
              ``(n0, sx, sy, l, j, ...)`` and `plan_rows` delivers the L for real.
            - **THE WORK ORDER IS THE OBJECTIVE.** One item per ``(herd, walk length)``, ordered by
              ``total = herd + walk + thrust + 4`` ASCENDING -- **348 items over 46 herds, totals 87
              to 100**, four herds dropped with a proof (floor >= 101 at every thrust). Unit-major
              ordering would spend the first hours on 100-frame plans off rung 4 while a 91-frame
              plan sat unexamined on rung 5.
            - **CONTAINMENT IS GATED END TO END, and it is the driver's own command**
              (``overnight verify-console``, 12 checks): the console's herd is a live item, its walk
              length is inside its own budget, **its walk letters are members of the fan alphabet**
              (as decoded classes, of 11405), its aim is in the alphabet at the camera the fan runs,
              its facing cell is one of the 45 enumerated, a real A-press re-derives its entry on all
              six flags, and **its own candidate comes back DELIVERABLE with the cut on frame 101**.
              `test_the_composite_log_is_the_console_log_row_for_row` pins the same thing with no sim
              in it: the driver rebuilds the delivered movie byte for byte.
            - **THE RUN REPORTS COVERAGE, NOT JUST ANSWERS.** ``overnight status`` gives elapsed /
              remaining / ETA, items done-in-flight-left, candidates, razor evaluations, GENUINE, the
              CONTACT population and best overlap, the residual sign split (the razor bracket),
              exceptions counted by class, and the incumbent. Every fact is on disk the moment it
              exists (append-only JSONL, flushed per line, atomic incumbent), the queue is ``O_EXCL``
              claim files, and ``resume=1`` skips exactly the completed items and releases abandoned
              claims -- exercised by killing a dry run, not by reasoning about it.
            - **WHAT IT HAS SAID SO FAR (first minutes, and it is the instrument working):** at walk
              1-3 the whole at-cap population is **17 to 87 u short of touching her** (best overlap
              -16.98 u on rung 5 at walk 3, from 424 at-cap candidates -- which REPRODUCES s149's
              stage-A deficit of 16.96 from a completely different enumeration). Outside contact the
              razor's residual is a dead constant, so ``0 genuine`` at short walks is a distance
              statement and not a refusal; the deficit is what closes with walk length.
            - **THE KNOWN COVERAGE GAP, sized:** the fan's families are ``pre + flip + hold`` with the
              hold on the FLIP's own stick, so nothing steers PER FRAME after the conversion -- what
              s149's stage-B beam did. The fix is cheap because the at-cap prefix set is small (424 at
              walk 3): extend each at-cap prefix at ``walk - k`` by ``k`` fine frames, ~130 s per item
              at k=1 and ~150 s at k=2 with a 400-node beam.
            - **THE OVERLAP TARGET WAS BEING REPORTED BACKWARDS, and the fix is committed
              (`5264409`).** The console's own clip sits at overlap **+1.2259**, a GRAZING touch, not
              at the maximum -- deep overlap is Link buried in her, a geometry that cannot clip.
              Measured over 72000 scorings: 96.1% land at overlap < -5, **0.33% in the clippable band**.
              `overnight.score` now ranks and reports ``band_draws`` (nearest `CLIP_TARGET`), not the
              max; `knowledge/strategy/clip-overlap-band.md`. A hypot-based prefilter for the band was
              measured and REFUSED before shipping: 39.7 u wrong on the known clip (she is plowed 47 u
              during the roll), so only the full sweep may decide.
            - **A MEMORY BUG SHIPPED AND CRASHED THE FIRST FOCUSED PASS (`d128031`).**
              `_steered_tail`'s prefix pool held one live `LandCore` clone per at-cap prefix with NO
              CAP; at ``pre_stride=16`` over the full 11405-letter alphabet that is hundreds of
              thousands of clones alive at once. 11 workers hit `MemoryError` simultaneously and lost 3
              items; the tail never called `beat()`, so a stuck worker read as merely slow for over an
              hour. Fixed: `PREFIX_CAP` truncates the pool (nearest her, kept) the moment it is
              crossed, logged not silent; `beat()` fires from inside the tail's own loops. **Caught by
              Dereck asking whether the search could possibly be sound -- not by a measurement of
              ours.**
            - **THE REAL BLOCKER, FOUND WHILE ANSWERING THAT SAME QUESTION: THE FAN'S CONVERSION IS A
              HAND-ROLLED SUBSTITUTE FOR AN EXISTING, VALIDATED PRIMITIVE, AND IT WAS NEVER CHECKED
              AGAINST IT.** The ``PRE`` + ``L_AXIS`` recipe above (turn, one L frame, release) is code
              written fresh this session. `away_walk.escape_atom` already exists, is already gated, and
              its own docstring says it produces **"the console's own delivered shape"**: turnaround ->
              L-conversion -> **rotate** (one frame, off the flip bearing) -> **backwards slam** -> hold
              the exit stick. Confirmed directly against the locked console log: frames 71-77 of its
              own 78-frame herd ARE exactly this atom (`176,247` with L at frame 71, released holding
              the same stick at 72, then the rotate/slam/hold through 77) -- seven frames before the
              herd hands off, not a separate walk-away ending appended after it.
              **Why `verify-console` passing did not catch this**: the console's herd is defined as its
              own recorded first 78 frames, which already CONTAIN the atom as fixed history, and its
              walk (``[0, 208, 110, 2, 169, 192, 2]``) is four plain directional frames that need no
              conversion because the herd already performed one. Containment proved the forward model
              REPLAYS the console's exact recording bit-exact; it never exercises the fan's own
              conversion logic at all, because that item never calls `_families`' PRE/L code. **The 49
              banked ladder herds are the ones that do** -- they are frozen mid-backslide, before any
              such conversion, so the fan has to invent one from scratch, and it has been doing that
              with a cruder tool than the one that actually works on console. None of the 48 non-console
              herds have ever produced a genuine hit; that is no longer a surprise.
              **NEXT SESSION'S FIRST JOB, before trusting any further search output from this driver**:
              rework `fan_exact`'s conversion phase to call `away_walk.escape_atom` (or the equivalent
              primitives it is built from) instead of the ad hoc ``PRE``/``L_AXIS`` construction. Not
              attempted this session -- three real mistakes is enough for one sitting, and this needs a
              clean look, not a rushed patch on top of the others.
            - **SESSION 151 -- THE HAND-ROLLED CONVERSION IS DELETED, THE REAL RECIPE IS NATIVE AND
              GATED AGAINST THE PRIMITIVE, AND THE SEARCH SPACE NOW PROVABLY CONTAINS THE CONSOLE'S OWN
              CONVERSION SHAPE.** `_families`' ``lswitch`` (L-press, release, nothing after) is gone
              outright, not kept beside its replacement: `overnight._atom_junction` runs
              `away_walk.escape_atom`'s own recipe (L-press, release, rotate, backwards slam) NATIVELY,
              per candidate, and `_atom_candidates` composes it into `fan_exact` exactly the way the
              PRE segment already composes -- a junction, then the ordinary family sweep for whatever
              walk remains. Gates: `tests/test_overnight_driver.py` (+4, all under 0.2 s).
              - **CONFIRMED AGAINST THE SIM FIRST, NOT JUST THE STICK-DECODE.** Seeded a `FreeRun` at
                the console's own locked log truncated to frame 71 -- one frame before its recorded
                conversion begins -- and ran `away_walk.probe`'s own knob sweep off it:
                ``flip_bearing=hl.bearing_bam()`` (the herd's own down-bearing, no sweep needed),
                ``rotate_side=-1``, ``rotate_off=0x6000`` FIRES clean -- separates in 5 frames, ZERO
                dips, better than the human's own 7. The proc sequence (6 -> 7 ATN_MOVE -> 6 at +17.6
                the negation -> 24 MoveTurn halved to +8.5 -> 6 settling at +17.0) matches the console's
                own recorded frames 71-77 exactly; the byte-for-byte stick values do not, a documented
                ~144 BAM camera-chase gap (`_clone_for_atom`'s own accepted cost) -- expected, not a
                defect.
              - **A REAL DESIGN CORRECTION MID-SESSION: THE FLIP AXIS CANNOT BE A STICK-BYTE ALPHABET.**
                The first `_atom_junction` swept `entry_fan.stick_alphabet` directly for the flip, and
                the resulting rotate/slam bytes DISAGREED with `escape_atom`'s own computation on every
                draw, because `escape_atom` always drives the L-press at FULL deflection
                (``stick_for_bearing(flip, cs, msd=1.0)``, its module docstring: "full stick toward
                Tetra") and a byte draw is not guaranteed to be. Swapped the flip axis for
                `away_walk.flip_arc`'s own bearings (full deflection by construction): all 168 tested
                (flip x rotate_side x rotate_off) combinations then agree with `escape_atom` bit-for-bit
                on all four frames. Gate: ``test_the_atom_junction_agrees_with_escape_atom_bit_for_bit``.
              - **CONTAINMENT, THE LITERAL ASK.** ``test_the_atom_conversion_reaches_at_cap_from_the_
                consoles_own_backslide`` seeds the SAME real frame-71 backslide (never the answer
                itself) and asserts `_atom_junction` converts it to a rollable at-cap state -- the
                search's own generator doing what previously only a hand-run `escape_atom.probe` could.
                ``overnight verify-console`` still passes 12/12 unchanged (the console's own item
                bypasses the conversion phase entirely, as s150 found, so this was never going to move
                it).
              - **A REAL FLEET RUN THROUGH THE WHOLE PIPELINE, SAMPLED.** Off the same frame-71 seed at
                walk 7, `fan_exact` returns ~98.6k atom-shaped at-cap candidates; 300 sampled at random
                and replayed on the WIRED python engine via `plan_rows` land rollable-AND-at-cap on
                ~70% of them. The rest is the SAME prediction-vs-reality fallout `accept()`'s
                multi-stage pipeline already exists to filter (`entry_fan.py`'s own docstring: "about
                one aim in eight brakes on the entry frame instead") -- not a new failure mode.
              - **STILL SCOPED, NOT SILENT.** ``turnaround_first`` is not swept (every real backslide
                measured so far already faces away; a facing-forward one still has the existing PRE
                segment to clear the cone, untested in combination). The atom does not yet compose with
                a PRE pre-turn -- it only runs bare off each ``n0``. Neither blocks the containment
                claim; both are honest follow-up, not a gap these tests paper over.
              - **DERECK REFUSED TO ACCEPT THIS AS ENOUGH: "i refuse to allow any search that cant also
                rediscover the 101 solution."** Bit-exactness against `escape_atom` and containment-of-
                shape on a proxy state are MECHANISM proofs, not a search-finds-answers proof --
                `[[search-must-rediscover-known-answer]]` is the hard gate this created, and nothing in
                this box before this line satisfies it. Nothing from s150's own runs (all pre-fix) is
                trustworthy evidence the space is barren on the 48 non-console herds either -- that
                conclusion stays RETRACTED, not confirmed, but re-launching `overnight run` is NOT the
                next step until the gate below passes.
              - **NEXT (BLOCKING, before `overnight run` or trusting any of its output):** run the
                ACTUAL pipeline -- `fan_exact` -> `score` (the real razor sweep against real aim/thrust
                configurations, `configurations()`) -> `accept` (`confirm_entry` + the walled composite)
                -- on the console's own herd with its real conversion REMOVED (truncated to before frame
                71, session 151's own probe point: `seed=dict(log=FIX['log'][:71])`), swept over a
                reasonable walk-length range. The bar: does the GENERATOR itself (never the recorded
                plan, never a hand-picked aim) produce a GENUINE, DELIVERABLE plan totalling <=101? A
                yes is the first real evidence this search can find anything; a no is the real blocker,
                to report as such -- not a reason to re-run with different knobs before understanding
                why.

      - [~] **RUNG 5's BLOCKER IS NEITHER THE DISTANCE NOR THE CONVERSION -- IT IS TETRA HITTING A
            WALL, AND THE GUARD THAT REFUSES IT STANDS IN FOR A MECHANIC THE CONSOLE GATED
            (session 149).** The ladder's only sub-console rung is not dead; both beams that died on
            it died 100% on one prune, and the walled engine models what the prune was covering for.
            - **EVERY NUMBER THE ENDGAME RESTS ON, RE-DERIVED AT THE CORRECTED LEAN**
              (`_notes/s149_rung5.py`): rung 5's dispatch lean is **0**, measured by firing its own
              aim and reading ``m351C`` at the entry frame, not inherited; all **9** census entries
              re-read GENUINE there; ``need`` 101.94509 u and bound **100** reproduce exactly; the
              terminal is cut_step 16 / **18** roll frames.
            - **AND THE s144 "THRUST 14 ALONE" PINNING, RE-READ AT LEAN 0 RATHER THAN 648.** Thrust
              13 is barren at BOTH leans (0 genuine, 0 unbroken); thrust 14 reads **51 genuine / 13
              unbroken** at lean 0 against 40/8 at 648; thrust 15 reads **82/1** against 107/**0**.
              So thrust 14 stays the pin on COST (18 roll frames against 19) but "thrust 14 alone" is
              false at the true lean -- thrust 15 has an unbroken hit. And the lean-0 box is **WIDER
              than the 648 one that replaced it**: along 47.50..112.50 (was 57.50..102.50), runway
              185..265 (was 185..245), ``tetra_from_corner`` 97.50..182.50 (was 102.50..162.50),
              ``l0_band`` 0.5736..4.8928 (was 3.0693..5.2277). s144's narrowing was the stale
              mirror's.
            - **ZERO OF THE 49 RUNGS IS AT THE ROLL CAP** -- read straight off the banked census,
              no new compute: ``roll_nspeed`` of every delivered speedF is **5.00..12.73, never 26**.
              Every bound on the ladder therefore prices a roll its own handover cannot dispatch, and
              the missing term is the CONVERSION to speedF >= +17. **The 26 is a THRESHOLD, not a
              locus to trade** (Dereck, s149): the cut frame's displacement is ``nspeed`` + the
              **23.22 u** constant `ANM_CUT` root translate against a seam minimum of ~**49.46 u**
              (`[[tetra-clip-map]]`), so at ``nspeed`` 5 the cut delivers 28.2 u and cannot cross the
              wall at ANY entry -- which is also why 26 alone (49.22) still needs the ~1.23 u CC-push
              ejection to tip it over. Do not reopen the sub-cap axis; s82 measured the same thing
              from the other side (2 of 181 momenta genuine, both at the cap).
            - **THE DISTANCE WAS NEVER THE BLOCKER.** From the HERD END -- not the census's
              three-settle-frames state -- the cheapest dispatch point is **83.7 u = 4.92 frames at
              the cap**, and every one of the 9 entries and its dispatch point is wall-free with
              **117..171 u** of clearance (41 of 41 samples along the straight segment clear). The
              census's 101.945 u is measured AFTER the backslide has spent **26.73 u** of runway on
              the settle frames.
            - **THE CONVERSION IS PAID, AT THE LIVE csangle, WITH NO CAMERA BILL**
              (`_notes/s149_cap.py`, 82432 rollouts): **122 at-cap dispatchable frames / 104 distinct
              states -- 2 at frame 4 (total 95) and 102 at frame 5 (total 96)**, 2 and 24 of them
              talk-free, against a budget of 9. A first crude sweep read NONE because it had no
              pre-frame: Tetra is IN the front cone at the handover, so a bare L locks the ACTOR into
              proc 9, whose slide caps at speedF **12** and never reaches 17. The cone-clear frame is
              the whole difference, and `away_walk`'s own recipe needed the SNAP csangle (a -1069 BAM
              bill) only because it fixes the pre-frame to the ESS turnaround.
            - **THE BLOCKER, MEASURED: TETRA'S WALL.** The handover carries her **16.5 u a frame** at
              a wall she has only **+52.46 u** of slack from, and `objective.frame_is_wall_free`
              refuses her at **herd+4 (slack -0.28) on NEUTRAL input** -- so the census state
              (herd+3, +10.13) is ONE FRAME from illegal. Every one of stage A's 104 at-cap states
              has her inside **+4.5..+12.4 u** of her own cylinder edge, i.e. less than one push
              frame. That is what killed both beams wholesale at the next frame: **0 of 205600
              children survived, 100% wall_tetra**, not follow and not Link (who never comes within
              87 u of a wall).
            - **AND THAT GUARD IS A PRUNE, NOT PHYSICS.** `seeds.make_freerun` leaves
              ``walls_tetra`` **None**, so Tetra is a bare XZ plow point -- the configuration that
              drove her 53 u THROUGH the courtyard back wall (s86) -- and `frame_is_wall_free` is the
              conservative stand-in for the missing pass. The WALLED engine is the one the console
              gated (`cross_engine.composite_rollout` defaults ``walls_tetra`` ON;
              `rollstab.cc_stepper`: "a real, live-gated MECHANIC -- a wedged Tetra's own CC recoil is
              canceled, so she HOLDS"). Measured (`_notes/s149_walled.py`): walled and unwalled are
              **BIT-IDENTICAL through frame 3** and part exactly at frame 4 where the guard fires
              (the self-gate), and the walled Tetra **BRACES at wall distance exactly 50.000**,
              moving **0.13..1.96 u/frame** thereafter against 9.48..7.00 unwalled. So rung 5's 9
              frames are intact -- and a braced Tetra is not a worse target but a **FIXED** one,
              which is what a 1e-4 u razor wants.
            - **TRAP: THE NATIVE STEP IGNORES ``walls_tetra``.** Measured all four ways --
              native+walled passes through the wall exactly like native+unwalled; only the PYTHON
              path braces. So a walled search runs at **717 clone+steps/s against the native 9406,
              13x**, and porting Tetra's ``mObjAcch.CrrPos`` into `LandCore.step_courtyard` is what
              makes a walled beam affordable.
            - **THE THRUST IS AN OPTION SET, NOT A PIN, AND THE SLICE'S "BARREN" WAS AN ARTIFACT**
              (Dereck: thrusting works on 13-15, and it is good to have options; measured
              `_notes/s149_thrusts.py`). ``roll_frames = cut_step + 2``, so 13/14/15 cost
              **17/18/19** frames -- and re-scored on the REACHABLE frame-7 cloud at each node's own
              dispatch lean, **all three bracket the razor**: 13 reads 158 neg / 13 pos at **total
              97**, 14 reads 159/12 at **98**, 15 reads 158/13 at **99**. So the earlier reading off
              the banked family ("thrust 13 is barren, 2414 roots and 0 genuine") was the ``side = 0``
              SLICE speaking: `terminal.RollFrame.item` puts Link on the brace line, so no banked scan
              can vary LINK's lateral -- the one axis the endgame hinges on (s147) -- and a zero from
              it is not a refusal (`[[infeasible-needs-proof]]`). **The console's own delivered clip is
              thrust 15 / m351C 64761, the most expensive of the three**, so the options are worth up
              to 2 frames against it.
              **And the bracket TIGHTENS as the thrust rises** -- resid spans +-45.7, +-29.4, +-11.9 u
              at 13, 14, 15 -- so 13 is the cheapest and coarsest and 15 the tightest, which is
              presumably why the console took it. Best |resid| runs 6.76 (13), **0.166 (14)**, 0.245
              (15), all on 4-value samples, so the ordering is suggestive and not established.
            - **AND WITH THE GUARD OFF THE STACK RAN: CONTACT IS REACHED AT TOTAL 98 AND THE RAZOR
              IS BRACKETED.** Walled stage A survives to frame 6 (51 at-cap dispatchable states,
              total 97) with the contact deficit closing monotonically **21.49 -> 16.96 -> 13.20**,
              and walled stage B (`_notes/s149_land.py walled=1`) reaches **deficit 0.0000 at frame
              7 = TOTAL 98**, three frames under the console: **171 in-contact fireable nodes, 159
              with ``resid`` < 0 and 12 > 0 -- a SIGN CHANGE, the razor is bracketed** over
              -2.8165e+01 .. +2.9435e+01. s148's best was ONE residual across 514 nodes at total
              100 with no bracket at all.
            - **BUT THE BRACKET IS UNDER-SAMPLED, AND THE LEAN AXIS IS LIVE.** The 171 in-contact
              nodes express only **4 distinct residuals** (all at feet 74.073 -- the pending-input
              tie one layer on), best **|resid| 1.65958e-01** against a ~1e-4 acceptance. That best
              node's dispatch lean is **-98 (65438), not 0**, and the in-contact leans are
              ``[0, -98, -80, -15]`` -- so the axis s148 measured as degenerate at a settled
              handover IS live in the at-cap cloud, exactly as it predicted, and the own-lean
              re-sweep is doing real work (257 nodes re-leaned at frame 7).
            - **AND THE BEAM DOES NOT KEEP THE BRACKET**: frame 8 falls back to **0 in contact**
              (fireable 15163 -> 1799) and frame 9 loses the cap entirely (**fireable 0**). Since a
              hit at frame 7 already beats the console by 3, the remaining budget belongs in a FAN
              at frame 7, not in walking to 8-9 -- which is `clip-lottery-draws.md`'s prescription
              (widen the PREFIX, count draws per family) applied to the frames that FEED frame 7.
            - **WHICH ENGINE WAS BROKEN, AND WHAT IT COSTS THE CENSUS.** There are two, and only the
              stepper was missing the pass: **`ShoveCtx` / `tww_sim/core/_shovec.pyx`, the RAZOR
              engine** that scores a candidate roll (and produced the census, the terminal family and
              the 288 placements), **has the ``dBgS_Acch::CrrPos`` pass for BOTH actors and always
              did** -- verified at the console's own hit configuration, where Tetra's z pins at
              **-940.25562 for roll steps 10-14**, the console-locked brace to the bit. It is
              `from_f0.FreeRun`, the frame-by-frame herd/walk stepper, that `make_freerun` never
              wired. So the SCORING was right and the defect was REACHABILITY.
              **But the pair the census HANDED that engine came off an unwalled herd replay, and a
              correct verdict on an impossible input is still worthless.** Measured over all 49 rungs
              (walled vs unwalled, first divergence against the herd length): **8 diverge INSIDE the
              herd** (42..49, all 2-3 frames before it ends -- those banked herds are not what the
              console engine produces), **16 in the 3 settle frames the census added**, 25 never part;
              and **5 sit inside her own cylinder at the census state** (8, 10, 12, 30, 37). Of the
              **16 rungs the census called LIVE, only 5 are clean** -- rung **5 (n 9, bound 100)**, 6,
              7, 16, 20 -- against 1 inside-herd (42) and 10 settle-frame, which is **every
              high-count row** (10 n=19, 27 n=16, 15 n=14, 12 n=13, 25 n=10). The lead survives by
              luck, not design. **CONSEQUENCE: the census's live/dead labels may NOT order or prune a
              search** -- reopen all 49 rungs, replay every herd on the WALLED engine, and re-verify
              the 8 herd-diverging rungs before quoting their bounds.
            - **NOTHING WAS DELIVERED, correctly:** `clip_roll.fire` never returned a CUT_F, so by
              the standing rule there is no plan and no DTM.
      - [~] **``at_cap`` WAS THE RANK AND NOT THE PHYSICS -- IT IS FOUR FRAMES -- AND THEN THE LEAN
            EVERY TERMINAL HAS BEEN SOLVED AT SINCE s144 IS A STATE-2 SEED READ OFF A MIRROR THAT IS
            NEVER SYNCED (session 148).** Rung 3's single genuine entry, the ladder's only rung that
            beats the console, does not exist at the lean its own roll carries. The bug is fixed in
            the library and gated; the ladder is being re-censused at the corrected axis.
            - **``at_cap`` IS FRAME 4, NOT 12.** s147's reach beam looked for the cap in
              ACCELERATION; `away_walk`'s conversion buys it outright -- the `setSpeedAndAngleAtn`
              DIR_BACKWARD negation puts speedF at **+17.609** with the motion unchanged, which
              `entry_search.roll_nspeed` clamps to 26. The bare recipe reaches it at frame 3 but the
              L LOCKS (Tetra is in the front cone at the handover) into proc 9, which cannot
              dispatch; with the recipe's own turnaround frame first it is **frame 4, proc 6,
              dispatchable -> total 93 (-8 vs the console)**. Enumerated over the whole conversion
              family (`_notes/s148_cap.py`, 82432 rollouts): **67 at-cap dispatchable states at
              frame 4, 869 at frame 5**, essentially all talk-free. So rung 3's floor is 93 and the
              walk budget is 11 frames.
            - **THE JOINT BEAM REACHES |resid| 4.109e-02 AT TOTAL 100 AND THEN HITS A QUANTUM.**
              `_notes/s148_land.py` sweeps every node at its own (Link, Tetra) pair and ranks
              ``(fireable, contact deficit, |resid|)`` as s147 prescribed. Its in-contact cloud reads
              ONE residual across 514 nodes -- the pending-input tie, not a sample of the razor.
            - **SO THE FAN WAS SIZED BEFORE IT WAS PAID FOR, AND THIS IS THE DURABLE NUMBER
              (`_notes/s148_fan.py`): the whole 254x254 stick grid on the frame that ACTS expresses
              171 DISTINCT residuals** over -70.96..+66.14 -- 41148 negative, 2524 positive, so the
              razor IS bracketed -- at a **median neighbour gap of 1.663e-01, 1066x the 1.56e-04
              acceptance.** One walk frame cannot land this razor however wide the fan.
              `knowledge/strategy/clip-lottery-draws.md` already names the fix ("when the fine knob
              is saturated, widen the PREFIX"; count draws per prefix family) -- this is that
              measurement one layer over, on a walking rather than a held-stick alphabet. **And the
              pipeline lesson was re-paid a third time:** fanning the input delivered ON the landing
              frame returned **129032 children with ONE distinct residual**, none of them having
              acted yet; fan the input at ``len(log) - 2``.
            - **THE LEAN: `terminal_keep.DELIVERED_LEAN` = 648 IS THE STATE-2 SEED, NOT A
              MEASUREMENT.** Its own docstring is the tell -- "the body lean every one of the 49
              banked rungs delivers at its roll entry, **one distinct value**". `from_f0._step_native`
              copied back seven fields and not ``m351C`` (same hole in `LandState._sync_from_core`),
              so on a native run `run.link.m351C` held its seed for the whole herd. It is one value
              across 49 different herds because it is the seed. **There is no physics divergence:**
              the native core's OWN ``m351C`` matches Python bit-for-bit (422, 275, 77, 10, 0, 0),
              and nothing inside the sim reads the mirror -- so the staleness is invisible until a
              HARNESS script reads it, which is how 648 was derived. The native gates could not have
              caught it: `test_freerun_native.py` compares an ALLOWLIST that never held ``m351C``.
            - **AND THE RIGHT VALUE IS NOT THE WALK-END ONE EITHER (nailed by simulation).** The
              roll's first frame is still MOVE -- the A acts a frame late -- and ITS turn WRITES
              ``m351C``: from a walk end of **0** the dispatch frame wrote **200**, the ENTRY frame
              decayed it to **130**, and that is `fast_schedule`'s seed. Seeded at 130 the analytic
              draws ``[65, 42, 28, 18, 12]`` reproduce the simulated roll exactly; at 648 they read
              ``[324, 211, 137, 89, 58]``. **The lean is a product of the ROLL'S OWN DISPATCH -- how
              far that frame turns -- so it is an axis the plan CHOOSES, and it has never been swept
              because everyone believed it was pinned.**
            - **WHAT IT COSTS.** At rung 3's census state the dispatch lean is **0**, and there the
              s147 entry reads ``genuine False, resid -3.294e-01, overlap -32.989`` against
              ``genuine True, +6.745e-05, +1.126`` at 648; re-solving the whole locus at lean 0 over
              runways 100..400 step 2 returns **0 genuine entries**. Session 144's pinning (thrust 14
              alone, the 180 -> 160 u plow ceiling, 8 -> 4 rungs clearing it, genuine 51 -> 40,
              unbroken 13 -> 8) all rests on 648 -- it "corrected" a family scanned at 0, which was
              nearer the truth.
            - **THE RE-CENSUS, ALL 49 RUNGS AT THEIR OWN DISPATCH LEAN** (`_notes/s148_lean_census.py`,
              `_generated/s106/s148_lean_census.json`): **16 of 49 have a genuine entry, against 19 at
              648** -- and it moves BOTH ways, exactly as `clip-band-per-lean.md`'s jagged band says it
              should (rung 27 **13 -> 16**, rung 10 17 -> 19, rung 36 **0 -> 2**; rung 12 18 -> 13,
              rung 7 4 -> 1, **rung 3 1 -> 0**). **Rung 3 is gone and rung 5 is the whole ladder's only
              rung under the console: n 9, owes 101.95 u -> bound 100, a ONE-frame margin** where rung
              3 claimed eight. Next: 6 and 7 at 107, then 108..121. So the correction wipes the LEAD,
              not the ladder -- and it costs the endgame its cushion.
            - **AND THE AXIS IS DEGENERATE AT THIS AIM: every one of the 49 rungs dispatches at lean
              0.** The lean is real and plan-chosen -- one at-cap cloud reached -130..+240 -- but the
              terminal's own aim from a settled 3-frame handover barely turns, so the dispatch writes
              nothing. Buying a different lean means changing the APPROACH (the facing the dispatch
              frame turns THROUGH), not the aim.
            - **FIXED + GATED (tracked).** `_sync_from_core` and `_step_native` now sync ``m351C`` and
              ``_draw_lean`` (both native branches are pure delegation + copy-back, so this cannot
              move physics -- it only makes the mirror true), and `tests/test_freerun_native.py`
              gains both to its 0-ULP allowlist so an unlisted field cannot hide again. `pytest`
              **1203 passed, 3 skipped, 8 xfailed, exit 0**, counts unchanged.
            - **NOTHING WAS DELIVERED, CORRECTLY.** `clip_roll.fire` never returned a CUT_F, so by
              the standing rule there is no plan and no DTM.
            - **NEXT: rung 5 at bound 100 is the whole endgame now, and it is a one-frame margin, so
              re-run this session's stack on IT** -- the conversion (`at_cap` at frame 4) then the
              joint beam, with the razor solved at rung 5's own lean 0 rather than 648. Its 101.95 u
              is 6 walk frames at the cap against a budget of 73 + f + 18 <= 100, i.e. **f <= 9**, so
              the slack is 3 frames and not the 7 rung 3 appeared to have. Then re-read every
              s144-s147 number quoted at 648 (`TerminalKeep`'s box,
              `fixtures/courtyard_terminal_family.json`'s lean-648 records, the "thrust 14 alone"
              pinning). The lean stays an axis but it must be bought through the APPROACH; and carry
              the 1066x density number into whatever lands it -- the landing is bought in PREFIX
              FAMILIES, not fan width.
      - [~] **THE HERD HANDS LINK OVER STILL INSIDE TETRA, SO THE 94.56'S RAZOR WAS SOLVED AT A
            TETRA THAT DOES NOT SURVIVE THE HERD -- AND THE AXIS IT PASSED WAS NEVER THE ONE THE
            LOCUS SOLVES (session 147).** Session 146 banked 16 genuine entries at rung 5's herd-END
            Tetra and priced a walk from there. Three measured corrections, all in the same
            direction, and the plan does not survive any of them.
            - **THE FIRST FRAME AFTER THE LOG MOVES HER 16.5 u, FOR EVERY INPUT IN THE ALPHABET.**
              Rung 5 ends with Link's exec Co centre inside her (feet 57.85 u), and the pipeline acts
              a frame late, so the escape has no say in the first two frames at all. Neutral
              continuation, her z: -887.80 -> -904.29 -> -918.22 -> -930.13 -> -940.54 -> -950.02 ->
              -957.01. The s146 step-2 requirement ("never comes within 80 u of Tetra -- a walking
              push moves her and makes the razor stale") is therefore violated **at frame 0, by the
              herd**, not by the walk. The terminal sees the POST-CONTACT Tetra; that ordering is
              `away_walk`'s own since s65 (her residual over the conversion frames, 34.8-44.7 u) and
              it had never been applied to the ladder's own pricing.
            - **THE GAP IS NOT THE WALK.** The walk ends one full ROLL STEP short of the entry
              (`entry_search.roll_entry`), and the roll runs toward the brace while Link sits between
              the entry and the brace -- so the walk-end is FURTHER OUT than the entry, never nearer.
              Rung 5's 60.46 u is **83.75 u** at the herd-end Tetra and **112.36 u** at the Tetra
              that exists.
            - **AND THE TERMINAL IS THEN UNREACHABLE, MEASURED.** Re-solved at the post-contact Tetra
              (-1619.928101, -930.130066) over runways 100..480 step 2: **10 genuine entries** at
              ``runway`` 198..300 / ``side`` +19..+21, so Link owes ``runway >= 224`` at ``side ~
              +21``. The herd parks him at **runway 146.41, side -29.12** carrying **-25.72** of
              backslide pointed AT the brace. A 500-node beam closes ~5 u a frame, bottoms out
              **63.3 u short at frame 7 and then DIVERGES**, and every at-cap node stays **80..90 u**
              out through frame 18.
            - **THE AXIS: ``side`` IS LINK'S LATERAL AND IT IS THE ONE `entry_locus` SOLVES.** s146
              screened ``l0`` -- TETRA's lateral -- and rung 5 passes it at +7.86. Nothing has ever
              screened Link's, and rung 5 is **50 u** on the wrong side of it. Census of all 49 rungs
              three frames past their herds (`_notes/s147_census.py`,
              `_generated/s106/s147_census.json`): Link's ``side`` spans **-43.42 .. +269.46**,
              Tetra's ``l0`` spans **-0.34 .. +116.57**. `TerminalKeep` has an axis for the second
              and none for the first.
            - **THE INSTRUMENT THIS BUYS: the razor scored on ANY (Link, Tetra) pair in 0.013 ms,
              batched, with no locus solve and no frozen Tetra** --
              ``pf.sweep([(tetra_x, tetra_z, entry_x, entry_z)])`` returns ``(genuine, resid,
              overlap, push, brace_dist)``, ``resid`` being the SIGNED miss `solve_razor` bisects.
              Gated against the solved entries: every genuine one reads **overlap +1.13 / push
              0.566**, which is `entry_search`'s own "genuine wants ~(-0.551,-0.127)" arriving from
              the other side. **Its trap: ``resid`` is FLAT outside contact** (the bare roll-stab
              **-3.293847e-01** whatever the entry, `handoff.resid_window`), so a beam ranked on
              ``|resid|`` alone has nothing to descend -- ``overlap`` is the gradient that gets it
              into contact first.
            - **THE LIVE LEAD IS RUNG 3, AND ITS BLOCKER IS ``at_cap``, NOT DISTANCE.** Three frames
              past its herd Link is at **runway 190.63, side +37.21** with Tetra at ``l0`` +47.19;
              its razor solves to **one** genuine entry (runway 178, side +43.29, width 1.56e-04)
              whose walk-end is **14.69 u** away -> a bound of **71 + 3 + 1 + 18 = 93**. The reach
              beam then prices the momentum: the box is reached at **frame 10 to 0.001 u** but at
              ``at_cap`` only at **frame 12** -> **101**, a tie and not a win.
            - **AND REACHING THE BOX BOUGHT NOTHING** -- at ``need`` **0.016 u** the best at-cap
              ``|resid|`` was **6.083** against a ~1e-4 acceptance. The razor is JOINT in
              (Link, Tetra): the box was solved at one continuation's Tetra and the beam's own Tetra
              is elsewhere, so proximity to it is evidence of nothing. **Never rank on a box solved
              at another Tetra.**
            - **TWO TRAPS RE-PAID, both already documented one layer up.** A first census pass at
              runway step **4** read 0 genuine entries on eight rungs including rung 3, whose only
              entry sits at **runway 178** -- a rung the step-4 lattice does not contain: a grid
              STRIDE is not a boundary either (`[[infeasible-needs-proof]]`). And a beam over this
              state dies on the pending-input tie -- every child of a node is physics-identical until
              the pipeline clears, so a dedup key without the delivered stick collapses the
              generation to one trajectory, and a ``per_state`` CUT of one sorted list starves it to
              4 nodes on frame 1. Round-robin over physics states; the key carries the input
              (`full_herd.junction_beam`, s68).
            - **NOTHING WAS DELIVERED AND NOTHING SHOULD HAVE BEEN.** `clip_roll.fire` never returned
              a CUT_F this session, so by the standing rule there is no plan and no DTM. No tracked
              library or test changed; the default gate is untouched.
            - **THE LADDER CENSUS SAYS THE HERD IS AIMED AT THE WRONG ACTOR.** All 49 rungs, entry
              locus re-solved at each rung's own post-contact Tetra, runways 100..400 step 2
              (`_notes/s147_terminals.py`, `_generated/s106/s147_terminals.json`, 78 min):
              **19 of 49 have a genuine entry** -- rung 12 has 18 of them, rung 10 has 17, rung 15
              has 15 -- so clip geometry is NOT the scarce resource. What is scarce is Link being
              near one, and the distribution of what he owes is a GAP rather than a spread: **rung 3
              owes 14.69 u (bound 93), rung 5 owes 112.36 (bound 101), and the other 17 owe 179..343
              (bounds 106..121)**. Rung 3 is an order of magnitude closer than anything else and is
              the ONLY rung in the ladder that beats the console. Every one of the 19 delivers a live
              terminal and then stands 180-340 u from it, and nothing in `objective` /
              `TerminalKeep` ranks that distance -- they rank TETRA's placement, while the binding
              constraint is where the herd parks LINK.
            - **NEXT: land rung 3's razor jointly, and attack ``at_cap`` rather than the distance.**
              Its box is reached at frame 10 to **0.001 u** and at cap only at frame 12, so two
              frames decide 93 against 101; `away_walk`'s proc-7 DIR_BACKWARD negation converts
              **-25.727 -> +17.614** (already past `WALK_CAP`, motion unchanged) in 2 frames against
              the reach beam's ~10, which is the atom to aim the approach at. Then land it with
              `pf.sweep` per node, ranked ``(not at_cap, contact deficit, |resid|)``, hunting a SIGN
              CHANGE of ``resid`` over the reachable cloud -- rung 3 has ONE genuine entry at width
              1.56e-04, so a minimum of ``|resid|`` will not find it. Size it with
              `entry_search.window_gap` before paying for a fan. If it will not land, re-breed the
              ladder against ``side`` and against Link's distance to the entry curve his own Tetra
              generates, which `pf.sweep` now makes free.
      - [~] **THE CYCLE-2 REQUIREMENT WAS READ PAST THE MODEL'S OWN FOLLOW GUARD, AND THE KEEP COULD
            NOT SEE THE AXIS THE WHOLE LADDER FAILS ON (session 146).** Two corrections, both
            measured, and they redirect the re-breed the s145 handoff asked for rather than run it.
            NEW truth pages
            [`a-bound-read-past-the-guard-is-not-a-bound.md`](../../knowledge/strategy/a-bound-read-past-the-guard-is-not-a-bound.md)
            and [`the-box-cannot-see-the-lateral.md`](../../knowledge/strategy/the-box-cannot-see-the-lateral.md);
            migrated claim
            [`history/the-crossing-bar-was-read-past-the-follow-guard.md`](../../knowledge/history/the-crossing-bar-was-read-past-the-follow-guard.md).
            `TerminalKeep` gains the ``l0`` axis; gate `tests/test_terminal_keep.py` **16 -> 19**;
            default `pytest` **1203 passed, 3 skipped, 8 xfailed, 66.02 s, exit 0**.
            - **`crossing_bar` = -80.4359 IS NOT A CONTINUABLE STATE.** The bound every cycle-2 keep
              has been bred against since s126 ("cycle 2 must hand over ``l0 >= -80.4``") is a max over
              rolls that leave the model: `FreeRun` has **no follow model at all** -- past
              `npc_zl1.FOLLOW_ENGAGE_DIST` it sets ``_follow_warned`` and says the sim "is no longer
              faithful from this frame on" -- and s126 attributed the flat +80.0..+80.4 plateau to
              "her FOLLOW, not a plow". Audited on the banked census itself, no re-simulation
              (end separation > 230 u PROVES the guard fired): the roll that SET the bar ends **402.9 u**
              from her, and **all 2339 band-keeping rolls in the census end past the guard** -- there is
              no in-domain member of the population the maximum was taken over. The only in-domain
              crossing in the census reaches ``l0`` +35.48 at runway **6.64**, i.e. the deep plow, which
              is the surviving structural claim.
            - **RE-SWEPT INSIDE THE DOMAIN (218880 rolls, 8 cycle-2 exits x 48 junction endpoints x the
              full aim circle, `_notes/s146_bar_domain.py`):** 98.8% of full-circle rolls trip the guard;
              a band-keeping roll that never does reaches ``l0`` **-123.48**, so inside the model such a
              roll LOSES crossing rather than buying +80.4. Respecting the guard costs **96.93 u** in the
              band.
            - **THE JUNCTION IS THE CROSSING INSTRUMENT, AND IT IS IN-DOMAIN BY CONSTRUCTION** (Link
              walks while touching her, so he never leaves 230 u). Population-complete over the banked
              cycle-2 beam -- 58 of 61 exits arm one, **309500 endpoints, 0 guard trips**: a junction
              buys **+2.46 .. +89.71 u** (median +53.79), more than the retired roll bar ever claimed,
              and the best absolute reach anywhere in the population is ``l0`` **-30.7501**. **So what
              is left is 30.75 u on `l0`**, not the 31.58 u on `tetra_from_corner` s145 measured.
            - **AND `l0` DOES NOT PREDICT WHAT ITS OWN JUNCTION CARRIES** -- s126's trap (1), now
              population-complete. The best exit by ``l0`` (-69.66) has a junction worth **+11.0 u**;
              the biggest gain **+89.71** sits at ``l0`` -193.73; only **2 of 58** reach past -50. Five
              sessions of `l0_keep` ranked the wrong half of the sum: the keep is
              ``l0 + (what this exit's junction can carry)``, and the second term is one junction beam
              per exit with NO aim sweep -- affordable exactly at the cut that decides which exits exist.
            - **THE KEEP WAS STRUCTURALLY BLIND TO IT.** ``along`` = `(T-L)·m`, ``runway`` =
              `-(L-brace)·m` and ``tetra_from_corner`` = their difference are all projections on the roll
              direction, so a lateral slide of BOTH actors leaves the three bit-identical (gated
              directly). And `terminal.RollFrame.item` has no ``side`` axis, so every banked scan puts
              Link exactly on the brace line -- the family is a **side = 0 slice** and the box is that
              slice's. The banked rungs sit at ``side`` -170..-177, ``l0`` **-128.92..-140.40**.
              `TerminalKeep.screen` now refuses on ``t_l0`` (the SIGN, measured; the 2.2 u ``un_lat``
              band is reported as ``l0_miss`` and never refuses, since it would drop an unscanned
              ``side``) and reports ``exact_side``. All 49 rungs refuse on ``t_l0``, gated off the
              banked s143 entries.
            - **AND 0 GENUINE ENTRY LOCI EXIST AT THE BANKED NEGATIVE `l0`** -- re-confirmed with
              `sign_prune` off, `roots=False` and the runway grid widened 320 -> 520: the four best
              cycle-2 exits (``l0`` -69.66..-90.04) give **5-7 razor ROOTS and 0 genuine**, every root
              pinned at the old grid's top edge. s142's trap, one axis over.
            - **NEXT (the ordered item): WIRE HER FOLLOW INTO `FreeRun`.** It is the only way to know
              what the crossing budget really is, and the model already exists and is live-0-ULP --
              `npc_zl1.Zl1FollowState` (stt-3/4, engage 230 / break 130), gated
              `tests/test_tetra_follow.py` against `fixtures/hyrule_tetra_follow.json`; the courtyard
              step just carries her as a bare f32 point. Wire it Python-side first, keep it INERT below
              230 u so every existing 0-ULP gate stays green (the DTM window never crosses it -- s144
              measured max 222.14), gate the boundary, then decide the native port. Named residual: the
              live capture has Link STATIONARY, so the moving-Link read lag is unpinned (`test_tetra_follow`
              says so itself). THEN re-breed cycle 2 on ``l0 + junction gain``, and s143's 2/3/4 unchanged.
              **Standing rules hold: no bound is a plan, and no DTM until the full clip sequence exists.**
      - [~] **THE TERMINAL IS A KEEP NOW, AND IT MEASURES THAT NO RE-POINT OF A BANKED LAST ROLL CAN
            REACH IT -- s144's DISJOINTNESS WAS READ IN 49 DIFFERENT FRAMES, AND IN THE BOX'S OWN
            FRAME `tetra_from_corner` IS SATISFIED BY NOTHING (session 145, item 1 of the s144 plan).**
            NEW tracked `terminal_keep.py` (`TerminalKeep`, `seam_window`; gated
            `tests/test_terminal_keep.py`, 16), wired into `full_herd.roll_probe` as ``terminal`` /
            ``terminal_sink`` and passed through `extend_cycle`. The keep refuses an aim failing ANY
            of facing / ``along`` / ``runway`` / ``tetra_from_corner`` and ranks only survivors on the
            exact residual at the roll's own facing, lean and momentum. **`nspeed` reached the tracked
            frames** (`terminal.RollFrame` / `handoff.PairFrame` take it; it lived in a `_notes`
            subclass since s143). Default `pytest` **1200 passed, 68.44 s, exit 0**.
            - **THE MEASUREMENT: 0 KEPT, 0 GENUINE, over all 49 rungs.** Re-point each rung's LAST
              roll from its own last junction across the FULL 2280-member alphabet -- the corner sits
              up to 78 deg off the herd bearing, i.e. **outside the ±56.25 deg fan every screen
              before this one swept** -- with `reposition.AXIS_PAIR` so "stay near the herd line" is
              not asserted of a roll that turns away from it. 112k rollouts, 210 s
              (`_notes/s145_repoint.py`, `_generated/s106/s145_repoint.json`).
            - **THE BOX BELONGS TO THE CLIP ROLL'S FACING.** ``runway``/``along``/``lat`` are
              projections on ``m`` = the ROLL DIRECTION, so they are properties of a pair PLUS a
              facing; ``tetra_from_corner`` is `-(tetra - brace)·m`. s144's delivery block reads them
              off `_notes/s143_rolls.py`, which builds a frame **per rung at that rung's own
              facing** -- 49 different bases, none of them the box's. And the re-point is not a
              re-projection: ``entry`` is Link's position at the END of the roll-entry frame, which
              steps ``nspeed`` in the aim direction, so a re-pointed roll STARTS somewhere else and
              has to be simulated. New truth page
              [`re-point-the-handoff-dont-re-project-it.md`](../../knowledge/strategy/re-point-the-handoff-dont-re-project-it.md).
            - **RE-MEASURED IN THE BOX'S FRAME, over the 528 aims that reach a live seam cell:**

              | axis | window | delivered | best miss |
              |---|---|---|---|
              | `runway` | 185.00..245.00 | 193.69..360.51 | **0.00** -- satisfied on 10 of 49 rungs |
              | `along` | 57.50..102.50 | -12.43..50.43 | 7.07 |
              | `tetra_from_corner` | 102.50..162.50 | 194.08..331.52 | **31.58** |
              | `lat` (solved, not kept) | +3.07..+5.23 | 15.80..79.57 | 10.57 |

              So **s144's "4 of 49 satisfy `tetra_from_corner`" does not survive the frame
              correction: nothing is within 31 u**, and the axis that is genuinely FREE is
              ``runway`` -- the opposite of the s144 reading, which had ``along`` cheap at 4..18 u.
              Closest overall is rung 49 (along 41.28, runway 236.28, tfc 195.00, lat 39.39, pair
              57.06 u apart). Delivered separation is 52.85..79.82 u where the terminal wants 60..100
              **on-axis**, at a pair bearing 15..45 deg off the corner's against the box's ~3.
            - **`followed` IS THE DEATH COUNTER, MEASURED RATHER THAN PREDICTED (s144 item 2).**
              `followed` 110321, `wall` 680, `t_facing` 719 -- and the CROSS-TAB ``followed@seam``
              **528 of 528**: every aim that reached a live seam cell died it. That is not a model
              limit hiding a solution, it is the same fact the box states: a corner-aimed roll stops
              plowing her, Link runs ~470 u past her, and the screen and the box refuse it together.
              All 528 fail ``t_along`` first.
            - **A GRID EXTENT IS NOT A BOUNDARY.** `terminal.scan` samples ``runway`` every 10 u and
              ``along`` every 5, and projecting a banked hit's own world pair back through the f32
              basis lands it **~3e-5 u below** its integer coordinate -- so the bare ``un_*`` extent
              refused **three of the eight unbroken hits it was read from**. The window is the
              sampled extent widened by HALF a scan cell (the resolution it is known to, not a
              tolerance); `test_the_keep_contains_every_hit_it_was_built_from` holds it there
              (`[[search-space-contains-human]]`).
            - **SO THE KEEP HAS TO BE BRED AGAINST, NOT APPLIED AT THE END.** Nothing a last-roll
              re-point can do moves ``tetra_from_corner``, ``along`` or ``lat`` -- those are set by
              the CYCLES. ``terminal`` is already plumbed through `extend_cycle`; the next run is the
              last cycle re-bred with it, not another sweep of the banked junctions.
      - [~] **THE 17-FRAME FLOOR DOES NOT EXIST, THE DELIVERED LEAN COSTS A FIFTH OF THE FAMILY, AND
            TETRA WAS NEVER THE PROBLEM WITH THE SEED (session 144, items 0 and 0b of the s143 plan).**
            All three axes the terminal family had never been scanned at are now measured and BANKED
            (`fixtures/courtyard_terminal_family.json`, read through `terminal.clipping_thrusts` /
            `clipping_family`; gated `tests/test_terminal_family.py`, 12 fast + 1 slow). The reference
            row re-scans identical to session 124's (51 genuine / 13 unbroken / `plowed`
            24.70..125.88), which is what licenses reading the rest as differences.
            - **A THRUST THAT DISPATCHES THE CUT IS NOT A THRUST THAT CLIPS.** New truth page
              [`dispatchable-is-not-clipping.md`](../../knowledge/strategy/dispatchable-is-not-clipping.md).
              `cut_step_window` is a property of `procFrontRoll`'s animation; whether the cut reaches
              the seam is the corner's, and over the whole scan box at the delivered lean:

              | thrust | `cut_step` | roll frames | roots | genuine | unbroken |
              |---|---|---|---|---|---|
              | 13 | 15 | 17 | 2390 | **0** | 0 |
              | 14 | 16 | 18 | 2513 | 40 | **8** |
              | 15 | 17 | 19 | 2613 | 107 | 0 |

              **So s143's "cheapest deliverable clip roll = 17 frames" is fiction and the floor is 18**
              -- +1 frame on every bound it wrote, on top of its own +4. It is ABSENT GEOMETRY, not a
              thin scan (`[[infeasible-needs-proof]]`): the root counts sit within 10% of one another
              across the three thrusts, thrust 13's roots solve to |resid| ~2e-7, and its `brace_dist`
              reaches **0.00**, so Link arrives at the corner and the cut still does not go through.
              The 0 also holds at lean 0 (2414 roots), so it is the thrust and not the state. The KB
              half-knew this -- `roll-cut-thrust-floor.md` recorded "thrust 13 has no reachable live
              station at any cell sampled" in s99 and hedged that a ~390 u entry might still go
              through; runways out to 480 were swept here and it does not.
            - **THE DELIVERED LEAN IS 648 AT EVERY ROLL ENTRY OF ALL 49 RUNGS, AND THE FAMILY WAS
              SCANNED AT 0.** One distinct value, one distinct nspeed (26.0). Re-scanned at 648:
              genuine **51 -> 40**, unbroken **13 -> 8**, `plowed` ceiling 125.88 -> 106.05 u, and the
              number the whole endgame is priced against -- how far from the corner a herd may leave
              her -- **180 -> 160 u**. That HALVES the ladder rungs clearing it (**8 -> 4**: rungs 44,
              41, 46, 43 at `tetra_from_corner` 119.9..158.1). `roll-lean-decay.md` is not contradicted
              and its scope is now stated on it: the lean is spent before a late cut, so the DEPTH at a
              solved configuration moves 0.0003 u -- which is a different quantity from WHICH
              configurations admit a solvable razor.
            - **AND THE ZERO-WALK-AWAY FAMILY IS THRUST 14 ALONE AT THE DELIVERED LEAN.** Thrust 15
              has the most genuine configurations of any thrust (107) and **zero** with contact
              unbroken. So the terminal is pinned: thrust 14, 18 roll frames, `along` 60..100,
              `runway` 190..240, `tetra_from_corner` 105..160, `lat` +3.07..+5.23.
            - **ITEM 0'S TETRA HALF DOES NOT EXIST -- SHE IS IDLE AND AT REST, FAITHFULLY.** The s143
              plan opened with "a herd hands over a FOLLOWING Tetra" and that is measured false:
              across all 49 rungs Link never reaches `FOLLOW_ENGAGE_DIST` (max **222.14 u**, rung 47),
              so she never leaves stt 3 and `fast_schedule`'s at-rest ``tet_seed`` IS the delivered
              one. No seed threading was needed -- a measurement was (`_notes/s144_delivery.py`, 49
              rungs in 1 s). **The margin is 7.86 u**, so this is gated rather than noted: a re-pointed
              herd that crosses 230 u puts `FreeRun` outside the state it models at all, and its own
              warning is suppressed by the `simplefilter('ignore')` every probe here runs (the flag
              still works -- `roll_probe` reads `_follow_warned` as a death reason).
            - **THE AIM IS A BAR IN THE SAME POPULATION-COMPLETE SENSE THE THRUST IS.** The delivered
              last-roll facings are **26637..38782**; the seam's own measured cell window
              (`fixtures/courtyard_facing_window_s92.json`, cells 2548..2573) is **40768..41183**.
              **0 of 49 rungs aim into it**, the closest being 11.0 deg below its floor -- and scanned
              over the whole box that facing bisects **2674 roots and clips at none of them** (a
              mid-pack -34.1 deg facing: 1778 roots, 0). The camera is not the constraint: 27 of the
              5600 deliverable facings at `CSANGLE` land inside the window. **The herd's last roll
              points AT her, to plow her; the clip roll must point at the CORNER.**
            - **WHICH MAKES THE s143 ANTI-CORRELATION A THREE-WAY DISJOINTNESS, ALL MEASURED, NONE
              SATISFIED BY ANY RUNG:** `tetra_from_corner` in 105..160 -- **4** of 49; `along` in
              60..100 -- **0** of 49 (delivered 42.0..56.0); the facing in the seam window -- **0** of
              49. The `runway` is the one axis that is fine (8 of 49 already in 190..240). So the herd
              is short on the handoff distance by 4..18 u, outside the plow ceiling on 45 rungs, and
              pointed 11..78 deg away on all of them.
      - [~] **THE TERMINAL'S CUT IS NOT DISPATCHABLE, THE CLIP ROLL COSTS TWO FRAMES MORE THAN
            ANYTHING CHARGED IT, AND NO BANKED ENDPOINT CLIPS IN THE ZERO-WALK-AWAY SHAPE
            (session 143, going to build the clip roll's inputs).** Building the sequence Dereck
            asked for is what found all three; the clip roll's bytes now exist
            (`clip_roll.py`) and there is nothing yet to fire them from. **Session 144 corrects two
            numbers in this box: the 17-frame floor is thrust 13's and thrust 13 clips nowhere, so the
            floor is 18; and the 180 u plow ceiling is a lean-0 number, 160 at the delivered lean.**
            - **THE THRUST-11 TERMINAL IS A ROLL THAT NEVER CUTS -- and the repo already knew the
              floor.** [`mechanics/roll-cut-thrust-floor.md`](../../knowledge/mechanics/roll-cut-thrust-floor.md)
              derived it in session 99 ("the earliest cut dispatch is roll step 15... on the
              Courtyard corner's indexing, thrust 13") and `entry_fan.THRUST_FLOOR` has held the 13
              ever since. The TERMINAL path never consulted either: `fast_schedule` computes
              ``cut_step = thrust + 2`` in closed form and checked nothing, so s136 read a thrust-11
              family off it and "thrust 14 -> 11 takes the cut 16 -> 13, three frames off every
              plan" went into every bound after it. `turnaround.extract_schedule_at`, which
              SIMULATES, raises "schedule never reached a CUT" for every thrust outside **13..15**.
              **The old fidelity gate could not have caught it: it swept `ES.THRUSTS` only, i.e.
              exactly where analytic and simulated already agreed.**
              NEW `entry_search.cut_step_window` derives the whole window off `LandState`'s own
              ``ROLL_RATE``/``ROLL_EARLY``/``ROLL_END`` rather than restating a literal -- ``cut_step``
              **15..17**, the KB's floor plus a CEILING it does not state (past 17 the anim has
              completed and the roll has exited to MOVE, so the press finds no roll). `thrust_window()`
              reproduces `ES.THRUSTS` exactly, which is what that tuple always was. `fast_schedule`
              now RAISES, gated by
              `test_the_analytic_schedule_refuses_exactly_what_the_simulator_refuses` (thrust 9..18,
              analytic vs simulated, both directions) -- **the doc was right and unenforced, which is
              the whole failure**.
            - **AND THE CLIP ROLL COSTS ``cut_step + 2`` FRAMES, NOT ``cut_step``** -- also already
              known, as `entry_fan.plan_cost`'s ``plan_frames + thrust + 4``, and also dropped when
              `handoff.endpoint` was written at s135. The entry frame runs one full roll step BEFORE
              the schedule's step 0 (`entry_search.roll_entry`; `extract_schedule_at` seeds a
              `LandState` already rolling at ``entry`` and calls its first STEPPED frame k=0).
              Re-derived here by SIMULATION across the whole realizable window rather than from the
              schedule that produced the number. The cheapest deliverable clip roll is therefore
              **17 frames** (thrust 13) against the 13 the ladder charges -- **+4 frames on every
              bound**, on top of the re-solve the new terminal forces.
            - **THE CLIP ROLL'S INPUTS EXIST NOW** -- NEW `clip_roll.py` (see `## Tooling`), gated by
              `tests/test_clip_roll.py` (9, 0.8 s). And two traps say a herd endpoint cannot fire
              them: the roll EXIT frame is ``ATN_ACTOR_MOVE`` and the A-roll dispatches only from
              ``ROLL_FROM`` = (MOVE, ATN_MOVE) -- **the natural chain frame is the one frame that
              refuses** -- while one frame later the untarget flip has run and
              `roll_nspeed(-25.72)` clamps to **5.0**, a 65 u roll against a runway grid starting at
              160. Also **the native core has no cut at all** (`_anmc._proc_roll` omits the
              ``b_trig`` arm), which is why nobody had ever stepped one: build the herd native,
              `fire` the clip roll on a Python-path run.
            - **NO BANKED ENDPOINT CLIPS IN s123'S SHAPE, POPULATION-COMPLETE.** If the herd's LAST
              ROLL *is* the clip roll then the acceptance belongs at each roll's OWN entry, which
              nothing had ever asked. Read there across all 49 rungs -- 147 roll entries x 17
              thrusts, **2499 probes: 0 genuine** (`_notes/s143_rolls.py`,
              `_generated/s106/s143_roll_entries.json`). Cut-frame CONTACT in 479 of them, all at low
              thrust; the last rolls sit at resid **-25 .. -307 u**. The mechanism is not a near
              miss: a herd roll is aimed AT Tetra to plow her, and a clip roll must be aimed at the
              CORNER with her ON that line (the terminal's ``along`` 50-245 / ``lat`` ~0 /
              ``runway`` 190-310). Her ``lat`` is already right (+0.2..+2.8 u); Link's ``side`` is
              not. **The shape itself survives the thrust correction** -- session 124's scan at the
              delivered facing / thrust **14** found 51 genuine terminal configurations, 13 of them
              with contact unbroken for the whole roll (`terminal.py`'s own docstring), so what has
              to change is the herd's AIM, not the family.
            - **WHAT THE TWO SHAPES COST -- and the first two answers s143 gave were both wrong, so
              read the arithmetic and not the headline.** Every plan is ``(frames before the clip
              roll dispatches) + roll_frames(cut_step)``, the second term 17/18/19 at thrust 13/14/15.
              **WALK shape** = herd + walk + 17; banked herds are **69..84**, so its floor is **86**
              at the shortest and **88 needs a 2-frame walk -- not ruled out** (the first claim that
              it was came from anchoring on the 73-frame confirmed rung and generalising). Its open
              term is the walk itself: Link hands over at speedF **-25.72** and must turn around and
              re-accelerate past 17 before a roll carries 26, which ``gap / WALK_CAP`` charges
              nothing for. **ZERO-WALK shape** = the prefix before the last roll + 17; banked
              prefixes are **51..66**, so ``entry + 16`` = 68..83. **THE TWO ARE NOT COMPARABLE:**
              the zero-walk prefix is **two** cycles of plowing, not three, and the third cycle
              exists because two did not put her where the search wanted -- the clip roll would have
              to finish with its own 53-126 u of plow (`terminal.classify`'s ``plowed``), and nothing
              shows a clip is available at the 2-cycle Tetra position. **68..83 is a floor under an
              assumption, not a plan length**; quoting it as one is the same proxy-as-plan error the
              standing rule below forbids. Prefer zero-walk because it deletes an unpriced phase and
              matches s123's geometry, not because it is 15 frames faster.
            - **THE REAL BLOCKER, IN ONE LINE: the herd has to FINISH THE PLOW and END UP ON THE
              CORNER AXIS at the same time, and nothing in 49 rungs does both** (Dereck: "part of the
              final roll has to be spent going around her, so how would we ever be close enough" --
              measured, and it is worse than that, because the two are ANTI-CORRELATED). The clip roll
              plows Tetra only **24.7-125.9 u** (`_generated/s124/terminal_40835_14_0.json`,
              ``plowed``), so a genuine configuration needs her within **180 u of the corner at the
              roll entry**; the unbroken-contact subset needs **100..180 u** at ``along`` 50..110 /
              ``runway`` 190..260. The banked last rolls split cleanly and disjointly: **8 rungs have
              her at ``tetra_from_corner`` 120..178 u and are aimed 33..47 deg off the corner**
              (``side`` 149..228 u off the brace line), and **7 rungs are aimed 1.2..8.4 deg and leave
              her 293..337 u out** -- 113..157 u past the plow ceiling, i.e. 9..12 more frames of
              pushing. Closing the first group's 149..228 u at the walk cap is **9..13 frames**. Both
              costs land in the same place.
            - **SO THE BEST CASE IS ~84..95 FRAMES, AND THE TWO SHAPES ARE THE SAME PROBLEM.** The 8
              close-enough rungs total 75..82 before the line-up, plus 9..13 to line up -- which is
              where the WALK shape lands too (86 + walk). Either the herd's last cycle swings Link onto
              the corner axis or a walk does it afterwards; zero-walk saves the turnaround out of the
              untarget flip, not the distance. Against the banked **101** that is roughly **6..17
              frames**. **The s143 "1.3 u re-point" is RETIRED** -- it was measured on rung 15, which is
              113 u short of the plow ceiling, so the nudge is real and buys nothing.
            - **WHAT IS NOT PROVEN is that the geometry forbids it** (`[[infeasible-needs-proof]]`):
              all 49 rungs were bred by a search ranking on distance-to-a-razor-entry-AFTER-A-WALK, so
              none was ever asked to satisfy both criteria at once. A keep that carries only one of
              them is exactly what produces a population satisfying only one. And the 180 u ceiling is
              itself a THRUST-14 number -- **the family at thrust 13 and 15 has never been scanned**
              (s124 did 14; s136 did 9/10/11, void), and a longer roll plows further, so one
              `terminal.scan` a thrust re-prices the whole table above before any search runs on it.
            - **THE MODEL ASSUMPTIONS NOBODY HAS CHECKED AT A DELIVERY STATE**, and the reason the
              next step is a validation rather than a search: `fast_schedule` seeds Tetra **idle and
              at rest** (``tet_seed`` = FAR + ``STT_IDLE``, speed 0) and every terminal scan ran
              **lean 0**, while a herd hands over a FOLLOWING Tetra and endpoints carrying m351C
              **648**. `entry_search.zero_the_resid` already accepts a Tetra ``seed=(speedF, facing,
              stt)``; the terminal path has never passed one.
            - **THE STANDING RULE OUT OF THIS SESSION: no bound is a plan.** Nothing is reported as a
              plan unless `clip_roll.fire` produced a ``CUT_F`` from its own input log, and the Python
              coupled replay reproduces the razor engine's predicted endpoint. A bound is a research
              number; the reportable artefact is a sequence that fires the cut. Both s142 (a razor
              ROOT read as a clip) and s143 (a schedule built outside the thrusts it was verified at)
              are the same failure -- something checked in one place, used in another -- and emitting
              the button presses is what caught it.
            - **WHICH GIVES s142'S "WALK-AWAY" A GEOMETRIC READING: it is an ALIGNMENT.** On the
              confirmed plan Link ends 57.85 u from her and the entry is 84.66 u away -- 26.81 u
              FURTHER -- but she sits ~24 u OFF his line to the corner, and putting her BETWEEN him
              and the corner is what requires backing off that line. Not the round trip s123 killed.
              Its priced cost is optimistic in a second, new way though: the herd hands Link over at
              speedF **-25.72**, so the walk must turn around and re-accelerate past 17 before any
              roll can carry 26 -- ``gap / WALK_CAP`` charges none of that.
            - **AND ``gap`` IS MEASURED TO THE WRONG POINT.** `handoff.endpoint` measures
              walk -> ``entry``, but ``entry`` IS the post-roll-entry-frame position
              (`entry_reach.reachable` translates by exactly this step), so the herd's real target is
              ``entry - roll_step``. At the confirmed rung's own delivered state that is **+4.92 u**
              of gap; at the walk cap the step is 26 u.
      - [~] **THE TERMINAL WAS NEVER CONFIRMED: NO LADDER RUNG ADMITS A GENUINE ENTRY, AND THE
            CONFIRMABLE SET IS FOUR TIMES CLOSER TO THE LINE THAN THE HERD PARKS HER (session 142,
            after Dereck asked whether we are ready to assemble).** The blocker on a DTM delivery is
            not search and not the scorer. One new truth page,
            [`confirm-the-terminal-before-you-rank.md`](../../knowledge/strategy/confirm-the-terminal-before-you-rank.md).
            - **THE RANK WAS A PROXY NOBODY HAD CASHED.** `handoff.endpoint` takes ``roots``, and
              **s134-s142 all ran the DEFAULT ``roots=True``** -- `entry_roots`, the UNCONFIRMED razor
              curve its own docstring calls "an under-estimate by construction… so a bound is never
              quoted as a solved entry". Run through `entry_locus` (``roots=False``, the claim):
              **rungs 1 / 2 / 4 / 7 confirm 0, 0, 0, 0** genuine entries against 21 / 21 / 17 / 25
              roots. A residual zero-crossing is necessary, not sufficient -- so ``gap`` and ``bound``
              measure the distance to a point where the clip does NOT fire, and the ladder's ORDERING
              (85.22 vs 90.41) is unfounded. The herd logs stay real and bit-exact.
            - **IT IS NOT THE CONFIRM AND IT IS NOT SAMPLING.** Positive control first
              (`[[search-space-contains-human]]`): 2 of 6 tabulated coords confirm at this terminal,
              ``genuine`` True, resid ~5e-5 u -- the machinery works, at a base rate of **0-1
              confirmed per 22-29 roots**. Then densify by RESOLUTION only: 81 runways instead of 17
              (111 and 125 roots) and a band walk of **+-0.05 u** against `side_band`'s +-1.2e-3.
              Still **0**. Forty times the span and five times the roots retires the density story
              without retiring `[[infeasible-needs-proof]]`.
            - **WHERE THE SET ACTUALLY IS** (`_generated/s106/s142_genuine_region.json`, 9 confirmed
              Tetras with their entry curves): **`l0` +4.11..+12.67, x -1650.61..-1627.94,
              z -929.51..-893.00** -- 9 of 29 tabulated coords survive at THIS terminal. The ladder
              parks her at **`l0` +29.47..+51.97**. Dereck (s142) is right that
              `tetra_placements.tsv` must not restrict the plan and nothing in the search path reads
              it (`probe` derives ``genuine`` from the roll sweep) -- but the replacement is a set
              DERIVED at the terminal in use, and the herd has been aiming outside it. `sign_prune`
              only ever asked `l0 > 0`.
            - **AND THE FIX IS A GATE, NOT A TABLE (Dereck, s142): 88.82 IS CONFIRMED.** A
              precomputed genuine set is `tetra_placements.tsv` again with new provenance, so
              viability is COMPUTED per candidate and cached on the exact bits of
              ``(facing, thrust, lean, tetra, runways)`` -- NEW `harness/tetrapush/confirm.py`
              (`confirmed` / `confirmed_bound` / `best_confirmed`, gated by `tests/test_confirm.py`).
              It composes into branch-and-bound because `entry_roots` is an under-estimate BY
              CONSTRUCTION: rank on roots, confirm ascending, stop when the next roots bound cannot
              beat the best confirmed. Over the 49 banked rungs that is EXACT and it closed in
              **6 of 49 rungs, 211 s**:
              **88.8186 = 73 herd + 47.92 u gap (2.82 f) + 13 cut**, rung 5 (s142 node 75), Tetra
              (-1615.514893, -887.797729), walk to **(-1563.932791, -820.661232) at runway 186**,
              4 confirmed entries, band width 6.96e-4 u -- **12.18 under `TOTAL_INCUMBENT` 101**.
            - **THE RUNWAY GRID WAS WORTH 2.76 FRAMES AND HAS NOW CONVERGED.** The locus is a CURVE
              (one solved ``side`` a runway); sampling it at step 10 gave 1 entry and a 94.79 u gap
              (91.58), step 2 gave 3 entries and 47.92 u (**88.82**), and step 1 (161 runways) returns
              the SAME entry and gap -- so 47.92 u is real distance, not sampling, and the proxy's
              optimism fell from 3.5 f to 0.78 f. Sample a solved curve finely before believing a gap.
            - **DERECK'S CORRECTION, AND IT IS THE SHAPE: THE ``gap`` TERM IS A WALK-AWAY.** He
              asked why we are walking away from Tetra when s123 set ZERO WALK-AWAY ("the herd's LAST
              ROLL *is* the clip roll... Link never leaves her"). Measured on this plan: Link ends the
              herd **57.85 u** from her -- inside s123's measured 57.0-75.4 u terminals -- and the
              confirmed entry is **84.66 u** away, so the 47.92 u walk ends **26.81 u FURTHER from
              her**. `handoff.endpoint` has priced `frames + gap/WALK_CAP + cut_step` since s135 and
              ``gap`` is exactly that walk; it is not s123's round trip (no walk-back) but it IS Link
              leaving. **The shape's own target is ``gap`` = 0 -- the herd's LAST FRAME already on a
              confirmed entry -- which for this same 73-frame log is 73 + 13 = 86 frames**, better
              than 88.82 AND the right shape. So `confirm` belongs as the ACCEPTANCE TEST on the
              herd's final frame (is the confirmed gap inside the ~7e-4 u band), not as a distance to
              minimise. Unchecked risk the walk adds: Tetra may FOLLOW during those 2.82 frames, which
              would make the position the clip was confirmed against stale.
            - **THE DELIVERY PATH IS PROVEN WIRED FOR THIS PLAN SHAPE, and a partial DTM is NOT a
              deliverable (Dereck, s142: no DTM until the full clip sequence exists).**
              `_notes/s142_dtm.py` spliced the 73 real frames onto the recorded boot movie as a wiring
              check only -- F0 44974, ticks EXTENDED, **`rt_mismatch` 0 / `prefix_ok` True** -- so
              `deliver.build_boot_movie` is known good here. Point it at the COMPLETE sequence
              (herd + clip roll) when that exists, and deliver once.
            - **STILL OPEN ON THIS PLAN:** rung 5 scores ``terminal_ok`` False (`escape_ready` does
              not fire), and whether that rule even applies to the zero-walk-away shape is itself
              unresolved -- `escape_ready` probes the away walk s123 removed. Resolve it, do not
              assume it. `fixtures/courtyard_candidate_ladder.json` carries a `CONFIRMATION_WARNING`
              and is gated as a BANK of herd endpoints, not a shortlist
              (`tests/test_candidate_ladder.py`).
      - [~] **NEW BEST BOUND 85.22: THE POOL BINDS TOO, AND EVERY WINNER CAME FROM THE DIRECTION
            THE CENSUS RANKED SECOND (session 142).** s141's ordered item -- the cycle-2 probe pool,
            400 of 424-5616 a parent -- priced population-complete with ``jn_keep`` HELD OPEN at
            s141's configuration, so the reference is 86.89 and not the shipped 89.82. **85.22 = 72
            herd + 3.71 u of gap (0.22 f) + 13 cut**, `l0` +51.22, runway 260; **-1.67 frames**, and
            **15.78 under `TOTAL_INCUMBENT` 101**. Still a BOUND: 72 real bit-exact frames, 3.71 u
            un-routed, a 13-f cut allowance with no cut sequence. One new truth page,
            [`a-cut-widens-two-ways.md`](../../knowledge/strategy/a-cut-widens-two-ways.md).
            - **THE CENSUS IS FREE AND IT MIS-RANKED THE TWO DIRECTIONS.** Junction cost only (wrap
              `_dedup_endpoints`, return nothing, no screen runs; 32 s): the population is **24708
              unique endpoints = 261 physics states at 94.67 pending letters a state**, and the
              shipped 2800 slots reach **34**. A widen to 800 reaches 62 and pays for it; the same
              400 slots under the s68 ``group``/``per_group`` cap reach **all 261 for free** -- so
              the cut's reach looked like a composition problem. It was not: the FREE direction
              priced **88.04** at best and the PAID one (more letters of states already reached)
              priced **85.22**, taking all three sub-86.89 results. Reaching a new state is not
              reaching a new OUTCOME; s141's 2.93 frames were a letter too.
            - **THE PRICED POPULATION IS A UNION, WHICH IS WHAT KEEPS THE GUARD.** A re-composition
              at fixed cap is a SWAP, not a widen (it drops ~60 of the productive state's letters),
              so the run screened shipped 400 UNION state-capped 400 UNION plain-widen 800 =
              **6632 endpoints (+137%)**, 2415 s, roll stage 3182 in 247 s (**10.2%**).
              **GUARD: 220 of 220** s141 roll survivors byte-identical by input log. 490 survivors ->
              **108 novel (state, pending) identities**, priced 108 of 108 (23563 s of node time,
              9 parallel batches of 12 with the s141 one-node-per-call JSONL checkpoint).
            - **THE RANKED LADDER IS NOW A TRACKED FIXTURE**, so a rung that does not survive
              assembly has a written successor instead of "re-run the search":
              [`fixtures/courtyard_candidate_ladder.json`](../../fixtures/courtyard_candidate_ladder.json)
              -- all **49** live candidates from s141+s142, best bound first, each with its FULL herd
              input log, and each scored by `objective.replay_and_score` so ``viable`` means wall_ok
              AND regime_ok AND rule 3 AND onside AND off the rung edges. **27 of 49 are viable, and
              the ladder reads 85.22 -> 85.31 -> 86.89 -> 90.41 -> 91.74**: rung 2 costs 0.09 frames.
              Rung 3 (85.73) is exactly why the flag exists -- it beats the reference on ``bound`` and
              FAILS rule 3, which a bound-only list would have hidden until assembly. Every rung was
              replay-verified on build (all 49 reproduce their banked bound/gap exactly). Gate:
              `tests/test_candidate_ladder.py` (structure + top rung locked 0-ULP; the replay is
              slow-marked).
            - **THE TOP THREE REPLAY BIT-FOR-BIT** from their stored logs on a fresh native
              `FreeRun` (`_notes/s142_verify.py`, all fields <1e-9): node 12 **85.22** (72 f, 3.71 u,
              runway 260, 21 entry curves), node 44 85.31 (72 f, 5.32 u), node 16 85.73 (71 f,
              29.35 u). Node 12 ends Link (-1478.123291, -796.263062), Tetra (-1527.264404,
              -854.942566) over a 72-frame log.
            - **THE WINNING SHAPE RETIRES THE GAP TERM.** Every bound since s135 carried 80-83 u of
              gap (~4.9 f); node 12 hands her over at **3.71 u = 0.22 f**. The six cuts priced flat
              before s141 all act on that term, so they are retired as levers whatever their price.
              85.22 is now **72 f of herd (85%) + the 13-f clip roll (15%)**, and that 13 is
              ``PairFrame.cut_step`` -- the schedule's own EXACT length for this terminal, not a
              padding allowance; it moves by choosing a terminal (thrust 14 -> 11 already took it
              16 -> 13), not by building the sequence tighter. The crossing still does not pay: the identities
              that reach the bar (`l0` -81.88 / -84.18 against -77.83) price 104.17-109.90 at 82-84
              herd frames.
      - [~] **NEW BEST BOUND 86.89: ``jn_keep`` WAS COSTING 2.93 FRAMES, AND THE ENDPOINT THAT
            CARRIES THEM SAT AT RANK 3 OF A CUT THAT KEEPS 6 (session 141).** s140's ordered item, and
            the FIRST cut priced since s135 that pays. **86.89 = 69 herd + 83.15 u of gap at the walk
            cap (4.89 f) + 13 cut**, `l0` +29.47, runway 230, terminal facing 40660 / thrust 11 -- under
            s136-s140's 89.82 and the banked console 101. Still a BOUND: gap at cap speed, no
            turnaround, roll entry separate. One new truth page,
            [`a-keeps-width-is-not-its-reach.md`](../../knowledge/strategy/a-keeps-width-is-not-its-reach.md).
            - **THE CENSUS INVERTS s140's, AND IT PREDICTED THE CUT WOULD PAY.** The rolling population
              is **1266 endpoints = 1266 distinct cut keys over 34 bit-exact states** (4-6 a parent) --
              the mirror of the final cut's 31-nodes-18-states -- because the key is
              ``(_physics_tag, pending stick, pending L)`` and the members are one node's children
              (the-frame-the-alphabet-shares). So this cut selects **which pending letter launches the
              roll**, and a state-only census would have called a live 1266-way selection a 34-way one.
              The Tetra-blind ident is measurably HARMLESS: zero key collisions at a different Tetra,
              widest ``l0`` spread inside one key **0.00 u**.
            - **THE WIDTH WAS HALF NOMINAL.** The shipped 42 slots (6 x 7 producing parents) reach
              **20** of the 34 states and spend **22** re-picking a state another slot already had --
              the exact failure mode s68 built `_mixed_beam`'s ``group``/``per_group`` cap for, present
              at `junction_beam`'s frontier keep (`group=_physics_tag, per_group=per_state`) and
              **absent** at this cut.
            - **AND THE SLOT WAS TAKEN BY THE ``l0`` SHARE.** `_mixed_beam` gives each order
              ``beam // len(orders)`` slots, so rank + the s134 ``l0`` share is **3 each** and the rate
              order never sees rank 3 -- which is exactly where the winner sat. The winner's own
              cycle-2 ``l0`` is **-175.60**, WORSE than the shipped beam's -154.38, so the screen ranks
              it near-last: s137's "the screen's axis does not predict the bound", now billed in frames.
            - **PRICED POPULATION-COMPLETE, 66 of 66.** Rolling the WHOLE population cost **+94 s of a
              1042 s stage (9.0%, 0.074 s an endpoint)** where the queued `jn_keep=12` was budgeted at
              "~2x 929 s" -- so measure the share of the stage BELOW a cut before budgeting its widen.
              189 dropped-origin survivors = **66 novel (state, pending) identities on 66 states none
              of the shipped 31 reach** (the other 123 bit-exact twins of the shipped 18, which is
              s140's own census of those nodes, cross-checked free). 15 of the 66 yield a live handoff;
              the runners-up are 91.74 / 92.33 / 92.72, and the identities that reach the crossing bar
              (``l0`` -79.26..-81.87) price **95.45..107.40** at 52-53 herd frames, so the crossing
              still does not pay. GUARD: 31 of 31 banked logs reproduced byte-identical, junction death
              counters byte-identical to s140's.
            - **WHAT IS LEFT, AND AGAINST THE RIGHT BAR.** The acceptance test is
              `objective.verdict` = complete AND (``within_budget`` OR ``beats_incumbent``), i.e.
              **beat `TOTAL_INCUMBENT` 101 on the TOTAL** -- Dereck's s135 rule, in the module's own
              words, is that "more than 75 herd frames is acceptable if it saves time overall".
              `frame_floor`'s 72.12/75 prices the OLD ending (push her onto a coord and stop) and
              carries NO gap and NO cut term, so it is not this route's bar and a "distance to 75" is
              not a headroom. What sizes the remaining cut-pricing is the term split and the base rate:
              **six cuts priced flat, all on the GAP term** (4.89 f, 5.6% of the bound, ceiling 4.89
              even at zero distance and only able to GROW when made real), and **one priced inside the
              HERD** (69 f, 79%) which paid **2.93**. Two herd selections are left -- the **cycle-2
              probe pool** (400 of 424-5616 a parent) and **cycle 1's beam** (8 parents, 4 produce);
              past them the remainder is cycle count and junction length, a different attack.
      - [~] **THE CYCLE-2 BEAM CUT IS TWINS AND PRICES 0.00 BOTH WAYS -- THE 72 IS UPSTREAM OF IT
            (session 140).** Session 139's ordered item -- its instrument one stage up -- answered
            over the cut's ENTIRE population, and the answer moves the herd question past the
            final cut. One new truth page,
            [`count-the-states-before-pricing-a-cut.md`](../../knowledge/strategy/count-the-states-before-pricing-a-cut.md).
            - **THE REPRODUCTION GUARD CAME FIRST AND IT MATTERED.** The banked 16
              (`s134_c3_l0_beam.json` cycle 1) predate s134's ``l0`` share at the final beam cut,
              so the re-run (s134_recut knobs: 8 cycle-1 parents, contact fan, thrust-14 ``l0``
              screen, cap 400, beam 16; `_notes/s140_c2_price.py c2`, 929 s) tested BOTH cut
              hypotheses against the banked logs: the PRE-FIX rank-only cut reproduces
              **byte-identical**; today's mixed rank+``l0`` cut does not. Perturb the cut the
              artefact was actually cut by, or the counterfactual prices a cut nobody took.
            - **THE POPULATION IS 31 NODES = 18 BIT-EXACT STATES.** The final cut keeps 16; the 15
              it drops are 9 bit-exact twins of kept members plus **2 novel states** (6 nodes, all
              cycle-1-parent-0 descendants). A runner-up "16" does not exist -- the honest
              counterfactual is the WHOLE complement, which upgrades the verdict from a slice to
              the population.
            - **THE COMPLEMENT REACHES 89.82 WITH THE WINNER'S OWN NUMBERS** (cycle-3 stage
              knob-for-knob with s136/s139, 523 s: 72 herd + 81.89 u gap + 13 cut, ``l0`` +15.48,
              runway 179) -- because the winner's cycle-2 state sits on BOTH sides of the cut:
              ``alt[0]``'s 45-frame input log differs from every kept node's and its end state is
              bit-identical to kept ``S1``. The two novel states both lose (one is the 70-71 f
              family that parks her OFFSIDE at ``l0`` -33.66, the other survives to no endpoint).
              Union verdict: min(89.82, 89.82) -- the cycle-3 stage is per-parent independent up
              to its final cut and ``handoff`` is computed pre-cut, so ONE run carries both
              pricing directions.
            - **WHERE THE CYCLE-2 SELECTION ACTUALLY IS**: ``jn_keep`` passes **6** of 58-259
              rolling endpoints a parent, the cycle-2 probe pool passes **400** of 424-5616, and
              cycle 1 hands 8 parents of which only **4 produce** the banked 16 (the winner
              descends from cycle-1 parent 4). None of those has been perturbed; the s139/s140
              instrument -- the free bit-exact state census FIRST, then the two-direction price --
              applies to each in turn. That, or the herd's physics (the cycle count itself), is
              where the 72 lives.
      - [~] **THE POOL BINDS AND HIDES NOTHING -- THE SCREEN IS PRICED OUT, GO AT THE HERD'S 72
            (session 139).** Session 138's ordered item, answered with the two runs that decide it,
            and the answer retires the whole screen as the place frames live. One new truth page,
            [`price-a-cut-in-both-directions.md`](../../knowledge/strategy/price-a-cut-in-both-directions.md).
            - **A NAMED CUT HAS TWO PRICES AND ONLY ONE IS MONEY.** Both runs are s136's config to
              the knob (terminal 40660 / thrust 11 / cut 13, +-8.44 deg window, freed axis, floor at
              the shipped 160 -- priced 0.00 by s137), one probe script both modes
              (`_notes/s139_pool_price.py`, logs `_notes/s139_{pool_price,cap500}.log`, beams
              `_generated/s106/s139_c3_{altpool,cap500}_t11_f40660.json`).
            - **PERTURB THE SELECTION: the RUNNER-UP 250 loses 7.57 frames** (97.39 = 79 herd +
              91.70 u gap + 13 cut). The alternate pool is the shipped `_probe_pool` applied one
              slice down -- compute the shipped 250 with the untouched function, exclude by
              identity, re-apply to the remainder -- so it is a different 250 by construction (no
              new criterion enters; `_mixed_beam` is not prefix-stable across caps, which is why
              exclusion and not `pool(2*cap)[cap:]`). The pool is LIVE: the bound rides on which
              250 get probed.
            - **WIDEN THE CAP: 500 AT THE SHIPPED ORDERS RETURNS 89.82 BIT-IDENTICAL**, same winner
              (72 herd, gap 81.89, ``l0`` +15.48, runway 179). The next 250 by the same orders
              produce real families -- 91.34 at 73 herd, 93.56 at 76, 94.94 at 77, all onside, all
              admitting entry curves -- and every one worse. No frames sit past index 250 by these
              orders, so the gap-denominated re-rank s138 sketched has nothing on this beam to
              surface; it is DEPRIORITIZED by measurement, not by fiat.
            - **THE SELF-CHECKS BOTH FIRED THE RIGHT WAY.** The five junction counters are
              byte-identical across all three runs (they must be -- the pool sits below the
              junction; s138's plumbing lesson in the expected direction), the roll-stage counters
              move with the pool, disjointness asserted per parent (overlap 0 on all 13), and the
              runner-up run's first-rung warning (winner runway 159 at floor 160) cannot touch the
              verdict -- that family's floor is 79 + 13 = 92 with the gap at zero.
            - **WHAT IT RETIRES: the whole screen.** Window (s137, 0.00), floor (s137, 0.00),
              arming bar (s138, arithmetic), ``l0`` frontier x2 (s137, 0.00), pool slice (s139,
              only losable), pool cap (s139, 0.00) -- and the ceiling on everything screen-side is
              the gap term's 4.82 frames (gap at literal zero still reads 72 + 13 = 85). **89.82 =
              72 herd + 4.82 gap + 13 cut; the herd is 80% and it is unpriced.** The instrument to
              take there is this session's: perturb what the CYCLE-2 beam hands the junction (its
              16 survivors, the keeps that chose them) and see whether the 72 depends on it.
      - [~] **`unarmed` IS THE ALPHABET, NOT THE WALL -- AND THE BOUND IS 80% HERD (session 138).**
            Session 137's ordered item, answered, and it retires the counter nine sessions have read
            as the refusal. One new truth page,
            [`the-biggest-death-counter-was-the-alphabet.md`](../../knowledge/strategy/the-biggest-death-counter-was-the-alphabet.md);
            the stale inference corrected on
            [`the-window-binds-on-the-parents-that-produce.md`](../../knowledge/strategy/the-window-binds-on-the-parents-that-produce.md).
            - **THE CENSUS, AND ITS SELF-CHECK.** `_notes/s138_unarmed_census.py` runs the cycle-3
              JUNCTION STAGE ONLY over the same 16 parents at the same knobs, with `full_herd._expand`
              and `two_roll.junction_gates` wrapped so every child reports its arming probe, its cone
              margin and the letter it carries -- streamed into histograms, never a 429k-row dump.
              124 s, and it reproduces `unarmed` **429724** to the count, so the population is the
              search's own (`_notes/s138_unarmed_census.{log,json}`).
            - **THE BYTE-IDENTITY WAS PLUMBING, NOT A MECHANIC.** `probe_half` and `handoff.RUNWAYS`
              are ROLL-stage / chain-back arguments and `extend_cycle` passes NEITHER into
              `junction_beam`, so the junction is a deterministic function of the parents and the
              alphabet and answers twice the same **by construction**. Before reading a counter's
              stability as a wall, check the knob reaches the stage that raises it.
            - **THE REFUSAL IS TWO POPULATIONS AND NEITHER IS A LEVER.** **97.77%** (420144) never
              flip at all -- probe speedF -26..-10, a **28-unit** hard floor that is FLAT across all
              12 generations -- and **2.23%** (9580) flip and land under the bar. Best refused
              **+16.998**, worst armed **+17.000**, nothing in between. Three of 16 parents produce
              ZERO endpoints and their refusals top out at -11.4, so no threshold reaches them either.
            - **THE BAR IS THE DECOMP'S KNEE AND ITS PRICE IS EXACT.** `_roll_init` is
              `clamp(speedF*1.5 + 0.5, 5, 26)`, so `min_preroll = 17.0` is where the clamp SATURATES,
              and each 1.0 of deficit costs exactly **1.5 u/frame** of roll. Relaxing to +16.0 admits
              5677 children at <=5.8% weaker rolls -- **+7.8% endpoints into a pool that already
              discards 97.1%** (1258-9604 endpoint children a producing parent, `probe_cap` takes
              **250**). The gate above the pool cannot matter while the pool is the cut. Gate
              `tests/test_arming_bar.py` pins the knee and the 1.5 u/f slope.
            - **AND A PENDING L ARMS NOTHING -- 36535 of 251397 EITHER WAY, to the count.** Decomp
              says why: `chaseAttention` only acquires inside the +-90 deg front cone and every child
              at this probe is OUT of it by the `in_cone` gate immediately above. The lock that routes
              the flip is INHERITED; arming is a posture carried in, never bought on the last frame.
              The toward-Tetra stick raises the rate 14.53% -> **36.80%** and decides nothing.
            - **THE ARITHMETIC THAT SHOULD AIM THE NEXT SESSION: 89.82 = 72 herd + 4.82 gap + 13
              cut.** (81.89 u at the 17.0 u/f walk cap.) Every screen-side knob priced since s135 --
              window, runway floor, probe pool, `l0` frontier -- acts on the GAP term alone, which is
              **5.4%** of the bound. The herd is **80%**.
      - [~] **THE WINDOW BOUND THE SCREEN AND NOT THE PLAN -- 89.82 STANDS, AND THE BAR BELONGS TO
            ITS TERMINAL (session 137).** Session 136's two ordered items, both answered, both
            negative in the useful way: the fan window it measured is real and it is not worth a
            frame, and the ``-80.4`` it flagged as a stale annotation has moved AGAINST us. Both
            owning KB pages updated;
            [`the-crossing-and-the-runway-are-one-resource.md`](../../knowledge/strategy/the-crossing-and-the-runway-are-one-resource.md)
            and
            [`the-window-binds-on-the-parents-that-produce.md`](../../knowledge/strategy/the-window-binds-on-the-parents-that-produce.md).
            - **THE RE-SEARCH AT ``max_delta``: THE FRONTIER DOUBLES, THE BOUND DOES NOT MOVE.**
              Same beam, same terminal, ``probe_half`` dropped so `probe_contact` supplies the
              measured +-21.35 deg and no new constant enters (`_notes/s137_c3_maxdelta.py`, 2741 s,
              `_generated/s106/s137_c3_maxdelta_t11_f40660.json`). Roll survivors **426 -> 504**,
              best screened ``l0`` on the producing parent **+71.77 -> +146.32**, best-of-beam
              ``l0`` **+42.11 -> +55.40** -- and **bound 89.82 = 72 herd + 81.89 u of gap + 13 cut,
              bit-identical to s136's**. Six of the eight nodes come back unchanged including the
              winner; the two that moved are the high-crossing corner, which improved a real
              **6.16 frames** (103.00 -> 96.84) and is still seven behind.
            - **BECAUSE THE SCREEN'S RANK AND THE STAGE'S OBJECTIVE ARE DIFFERENT AXES.** ``l0`` is
              the CYCLE-2 requirement's axis; cycle 3 is priced ``frames + gap/walk cap + cut_step``
              and its winner is a LOW-crossing endpoint that wins on a short gap. The s126 exchange
              rate governs cycle 3's own beam too -- buying crossing costs gap -- so a knob can move
              the ``l0`` frontier a long way without touching the bound.
            - **AND IT NAMES THE REFUSAL, ON BYTE-IDENTICAL COUNTERS.** Across two very different
              screens the five junction counters that matter do not move a single count: ``unarmed``
              **429724**, ``in_cone`` **314542**, ``outbox`` 6576, ``wall`` 26304, ``ENDPOINT``
              73070, with only the fan-dependent ``aim_followed`` (341777 -> 885403) and
              ``unrollable`` (874 -> 90) changing. **Arming is what refuses, and no screen knob has
              ever touched it.** The window is now cleared as a lever (widest survivor 16.41-19.49
              deg inside a 21.35 deg box, so the box holds a rung the population does not use) and
              so is the runway floor.
            - **THE ``-80.4`` BAR IS A TERMINAL'S, NOT THE PROBLEM'S: -77.83 AT THRUST 11.** It
              needed no re-run -- ``l0`` and ``runway`` are affine projections of banked WORLD
              positions, so s126's 20592-roll census re-reads in any frame exactly
              (`_notes/s137_bar_thrust11.py`). The re-projection returns **-80.44** at the frame it
              was measured in, which licenses the rest: the thrust-11 family sits at **-76.87 ..
              -77.83**, i.e. **2.6 u harder at the terminal that just saved 3.35 frames**. The
              structure survives whole (67 rolls cross instead of 51; every one still leaves Link at
              runway <= 89, so **zero still do both**). Banked over 11 terminals
              (`fixtures/courtyard_crossing_bar.json`), read through the new `handoff.crossing_bar`,
              and the stale literal is gone from `full_herd.py`'s screen print -- an UNMEASURED
              terminal now prints "NOT MEASURED" rather than a neighbour's number. Gate
              `tests/test_handoff.py::test_the_crossing_bar_belongs_to_its_terminal_and_an_unmeasured_one_says_so`.
              The bar is also **flat in where the band's near edge is drawn** (swept 130..220 it does
              not move a digit), so the floor and the bar are independent knobs.
            - **AND THE FLOOR WAS PRICED BEFORE THE SEARCH SO THE RESULT WOULD BE READABLE**
              (`_notes/s137_floor_price.py`): s136 searched at a 170 floor and this ran at the
              shipped 160, worth **0.00 frames** on these endpoints -- the winner's entry curve sits
              at runway 179, clear of both. So the null result is the window's alone.
      - [~] **THE PLAN IS 89.82: THE CUT IS WORTH 3.35 FRAMES AND THE SEARCH ONLY CONFIRMS THE
            RE-PRICE (session 136).** Session 135 left three ordered items; all three are answered.
            The thrust-11 terminal is the frames, the fan window it named IS binding and now has a
            measured width, and the runway box under the gap term was clipping the entry curve.
            One new truth page,
            [`knowledge/strategy/the-window-binds-on-the-parents-that-produce.md`](../../knowledge/strategy/the-window-binds-on-the-parents-that-produce.md).
            - **THE NUMBER: 93.17 -> 89.82**, re-searched with `handoff_pf` at the session-135
              unbroken family (facing **40660**, thrust **11**, ``cut_step`` **13**), every other
              knob identical to s135's: **8 of 8 endpoints onside**, all admitting an entry curve,
              **bound 89.82 = 72 herd + 81.89 u of gap at the walk cap + 13 cut** (1696 s,
              `_notes/s136_c3_t11.log`, beam `_generated/s106/s136_c3_t11_f40660.json`). Under the
              banked console **101**, s135's 93.17, s126's sampled 97.35 and the s125 floor of 94.
              Still a BOUND on the same two counts: the gap is charged at cap speed with no
              turnaround, and the roll entry is a separate search.
            - **AND THE RE-SEARCH ADDS NOTHING OVER THE RE-PRICE, WHICH IS THE FINDING.** Re-pricing
              s135's OWN eight endpoints in the new frame (`_notes/s136_thrust11_price.py`) gives
              **89.81** and the whole unbroken family is FLAT -- 89.81 at facings 40600/40610/40620,
              89.82 at 40640-40670, ``gap`` 81.77..81.89 -- and the re-search returns the same
              winner, the same gap and the same ``l0`` **+15.48**. So the 3.35 frames are the
              TERMINAL, not the herd: the cut term gives 3 and the shorter roll's own curve gives
              the rest. The junction death counters come back byte-identical to s135's
              (``in_cone`` 314542, ``outbox`` 6576, ``unarmed`` 429724), which is the same statement
              -- the terminal reorders the keeps and never touches the junction.
            - **THE FAN WINDOW IS BINDING, AND THE WIDTH IS MEASURED.** s135 inferred it from
              ``fan_edge`` alone; swept at `pursuit_box`'s ``max_delta`` (+-21.35 deg) with the
              endpoint pool held fixed, **28.4%** of surviving aims live outside the shipped 8.44
              deg, the best screened ``l0`` goes **+117.58 -> +140.76** (+23.17 u), **306 of 1250**
              endpoints take their best ``l0`` from outside it, and the population's own edge is
              **~16.4 deg** (the 16-24 band holds 77 aims of 34639, at a third the ``l0``).
              **AND THE CHEAP PARENTS SAY THE OPPOSITE**: parents 0-1, whose junctions return ~1258
              endpoints against 8510-8662, put 0.6-1.4% outside the window and every one of those
              aims strictly dominated. Sample parents by what they CONTRIBUTE, not by what they cost.
            - **`handoff.RUNWAYS`' FLOOR WAS CLIPPING THE GAP TERM** -- the OTHER runway box, never
              examined, floored at **190** on an s124 scan reported empty below it. Solved directly
              over rungs 60..320 the entry curve reaches rung **170**, so the floor cut two usable
              rungs: worth **+0.15 frames** at thrust 14 and **+0.29** at thrust 11. Shipped at
              **160** -- one rung below the measured edge, so a hit on the first rung is the curve
              speaking and not the box -- banked (`fixtures/courtyard_entry_locus_floor.json`) and
              gated (`tests/test_handoff.py::test_the_runway_box_does_not_clip_the_entry_curve`).
              **AND ONE BEAM WAS NOT A POPULATION HERE EITHER**: a floor set from the s135 beam
              alone, whose endpoints bottom out at 180, came straight back clipping on the s136
              beam, whose endpoints reach 170 -- the re-search's own self-check caught it. The bank
              spans both beams at both terminals (32 records).
            - **NOTE the printed ``-80.4`` bar is a THRUST-14 number** still being shown beside
              thrust-11 screens. The run is self-consistent (``l0``, `l0_keep` and the sign prune all
              ride the thrust-11 `PairFrame`); only that annotation is stale. What the shorter roll
              actually buys in crossing is unmeasured.
      - [~] **THE PLAN IS 93.17 AND THE BOX WAS WORTH 6.9 FRAMES -- BUT NOT ON THE ROUTE IT WAS
            FREED FOR (session 135).** Session 134 named `in_pursuit_box`'s direction clause as the
            measured cap on the BAND-KEEPING route and left the free-axis prototype as a
            monkeypatch. Promoted, gated, run -- and on that route the clause was *a* cap and not
            *the* one (the refusal moves `outbox` -> `in_cone`), while on the DEEP-PLOW route it
            takes the bound from **100.06 to 93.17**, under the banked console 101, s126's 97.35
            and the s125 floor of 94. One new truth page,
            [`knowledge/strategy/the-crossing-costs-the-arming-posture.md`](../../knowledge/strategy/the-crossing-costs-the-arming-posture.md).
            - **SHIPPED: the push axis is a PARAMETER, not the herd line.**
              `reposition.AXIS_HERD`/`AXIS_PAIR` + `pair_line`; `full_herd.in_pursuit_box(axis=)`,
              `human_in_box(axis=)`, `junction_beam(axis=, pf=)`, `junction_quality(axis=)`,
              `roll_probe(axis=)`, `roll_candidates(axis=)`, `_frontier_score(pf=)`,
              `two_roll.alive(axis=)`, `junction_gates(axis=)` and `extend_cycle(free_axis=)`, which
              wires one axis into all three of its prune sites. Default OFF at every seam. In the
              pair's frame ``lead`` is minus the separation and the lateral and bearing terms are
              zero by construction, so the box collapses to the human's own **26.8-127.8 u**
              separation band and costs one hypot. **Nothing is widened**
              (`[[no-overtuned-constants]]`): gate
              [`tests/test_free_axis.py`](../../tests/test_free_axis.py) (8 + 1 slow) proves the
              collapsed form IS the three-clause predicate about `pair_line` over the banked states
              and 50000 swept geometries, that the human is still inside it on every recorded frame,
              and that it is **not a superset** (a far-lead corner at the full 18 u lateral is 129 u
              apart and the freed band refuses it).
            - **IT UNBLOCKS THE PRUNE: 0 CHILDREN -> 170428 JUDGED.** Cycle 3 off the band-keeping
              cycle-2 beam (``l0`` -51.75 at 52 f, `_generated/s106/s134_c3_noquality_beam.json`
              cycle 1) went from *every child `outbox` at generation 1* to a junction that runs --
              and then dies whole on the NEXT gate, ``in_cone``: 170428 children judged, zero
              endpoints, 13 s.
            - **AND THE REAL QUANTITY IS THE EXIT'S SLIDE.** The arming gate is
              ``|facing - bearing_to_tetra| > 90 deg`` and it has two terms. From these exits Link's
              EBS backslide is **96-99% TANGENTIAL** to the line to her, so the bearing runs at
              **15-19 deg a frame** while he turns; best-in-beam cone deficit goes **86.0, 70.6,
              69.0, 69.4, 72.3, 76.3** and the beam is empty, with separation **64.6 -> 111.7 u**
              against the band's 127.8 ceiling. The herd-passing control at ``l0`` -152.14 slides
              **7% tangential**, its bearing moves 1.8 deg a frame, and its deficit closes
              **83.0 -> 48.2 -> 14.6 -> 0.0** in three generations and holds for nine more.
            - **THE TWO ARE ONE RESOURCE, MEASURED.** Over the banked beam: past the bar tangential
              **80-99%** and bearing 10.4-19.0 deg/f, short of it **3-36%** and 0.7-3.4 deg/f,
              ``corr(l0, tangential fraction)`` = **+0.960**. Not a coincidence -- ``l0`` is bought
              at 2.07x by LATERAL push, and a lateral push is one delivered ACROSS the line between
              the bodies, which is exactly the momentum that leaves the pair rotating. Read it as
              the mechanism, not a law: 16 endpoints of one beam are ~5 distinct states
              (`[[infeasible-needs-proof]]`).
            - **DERECK'S STEER, IN `objective.py`:** *"more than 75 herd frames is acceptable if it
              saves time overall."* Rule 2 is now about the TOTAL -- session 60 wrote the 2-frame
              budget when the plan WAS the herd, and s123/s125 replaced the ending, so a plan costs
              herd + the gap Link must still close at the walk cap + the cut. `score_plan(total=)`
              reports it, `TOTAL_INCUMBENT` = the banked console **101** is the number to beat, and
              `verdict` accepts a herd over budget whose total wins. Without a measured ``total``
              the verdict is exactly the pre-s135 one.
            - **AND ON THE DEEP-PLOW BEAM IT IS WORTH 6.9 FRAMES: BOUND 100.06 -> 93.17.** The same
              cycle-3 stage over s134's re-cut cycle-2 beam (`s134_c3_l0_beam.json` cycle 1, 16
              nodes, ``l0`` -269.26..-160.62), knobs identical to s134's, axis freed:
              **8 of 8 endpoints park her ONSIDE and all 8 admit an entry curve** (s134: 6 of 8),
              ``l0`` **+10.41 .. +38.80**, best **bound 93.17 = 72 herd + 87.86 u of gap at the walk
              cap + 16 cut** (2606 s). Against the banked console **101**, s134's **100.06**, s126's
              sampled **97.35** and the s125 floor of **94** -- which it beats because that floor's
              herd term was 73, the all-out-push-to-a-COORD number, and reaching the half-plane is
              cheaper than reaching the cluster. Its herd is **72 frames**, inside the old 75 bar,
              so this winner does not even spend the relaxed rule.
              **It is a BOUND, not a delivered plan**: the gap is charged at cap speed with no
              turnaround and no guarantee the move lands on the 1e-4 u razor, and the roll entry is
              a separate search. Two reasons it is not the frontier either -- the screen's fan
              window was binding throughout (below), and the 16 is a THRUST-14 cut.
            - **AND THE BOX IS NO LONGER THE BINDING PRUNE ANYWHERE.** The freed junction's death
              counters on this beam: ``unarmed`` **429724**, ``aim_followed`` 554159, ``in_cone``
              **314542**, ``aim_wall`` 89171, ``wall`` 26304, ``outbox`` **6576**. Arming is what
              refuses now, on the deep-plow parents as on the band-keeping ones.
            - **AND s134'S CHEAP OPEN ITEM IS ANSWERED -- 3 FRAMES, AT THRUST 11, NOT 9.** The full
              fine box with NO coarse screen (17 facings x 1540 cells a thrust): thrust 9 gives
              **133 genuine / 0 unbroken**, thrust 10 **46 / 0**, thrust 11 **53 / 1**. So s126's
              4.85-frame thrust-9 hope is dead on the fine box, and a family exists one rung up.
              It is a FAMILY, not a razor: walked at 5-10 BAM it holds unbroken cells across
              **facings 40600-40670** (one gap at 40630), one or two cells a rung, every one
              ``genuine_confirmed`` with ``break_frames`` 0 and a lat window 3e-5..1.2e-4 u wide.
              ``cut_step`` **13 against thrust 14's 16 = 3 frames off the cut term** of every plan
              that uses it. The gap term must be re-solved at the new `handoff_pf`, so no other rung
              of the bound carries over -- in particular a shorter runway is NOT yet a shorter walk,
              it is a different entry point and the gap is what prices it.
            - **AND `terminal.RUNWAY`'S FLOOR WAS CLIPPING THAT FAMILY.** Re-scanned over runways
              **60-200**, its lowest unbroken cell is at runway **130**, under the shipped box's
              first rung of 140, and it spans **130-160** -- so session 126's "the genuine band's
              lower edge parks at ~180-200 whatever the thrust" is a THRUST-14 statement, not a
              general one. Nothing unbroken exists below 130 over the widened floor, so 130 is the
              family's own edge and not the box's.
            - **THE SCREEN'S FAN WINDOW IS NOW BINDING.** With the axis freed the junction yields
              **6850-8662 unique endpoints** a parent against s134's 4292, and `roll_probe`'s
              ``fan_edge`` reports the furthest surviving aim at **8.39-8.43 deg of the 8.44 deg
              half-window** on every parent -- so ``probe_half=0x600`` is clipping the population it
              screens. Widen it with the axis, or the freed stage is measured through the old
              window (`[[infeasible-needs-proof]]`).
      - [~] **THE CROSSING WAS A CUT, NOT A REACHABILITY -- AND THE HERD PUSHES 64 DEG OFF THE AXIS
            THE ENDGAME IS DENOMINATED IN (session 134).** Session 126 reduced the endgame to one
            number, ``l0 >= -80.4`` handed over by cycle 2 against the -183.41 it delivers, and nine
            sessions read that as 103 u of unreachable distance. It is mostly a CUT. One new truth
            page,
            [`knowledge/strategy/the-axis-the-endgame-is-denominated-in.md`](../../knowledge/strategy/the-axis-the-endgame-is-denominated-in.md).
            - **THE TWO GRADIENTS ARE NOT EQUAL, AND THAT IS THE WHOLE FINDING.** ``l0`` is linear in
              her herd coordinates -- ``0.43448*along + 0.90068*lat - 411.99`` -- so a unit of
              LATERAL push buys **2.07x** what a unit of down-herd push buys, and a unit along the
              pair frame's own ``q`` buys 1.0 against the herd's 0.43. The herd line is **64.25 deg**
              off ``q``. Not a bug in the line: it aims at the genuine-coord centroid and the 288
              coords ARE on it (herd along 937.5-984.1, lat -2.3..+7.9). What changed is the target
              -- s123 deleted the walk-away and s125 moved the razor onto Link, so the ask is a
              HALF-PLANE plus a pair alignment, and a half-plane is reached fastest along its normal.
            - **WHAT THE STAGE PRODUCES AND WHAT ITS CUTS KEEP DIFFER BY 93 u.** Screened over the
              eight banked cycle-1 parents (contact fan, 250 endpoints each) the population's best
              DELIVERED ``l0`` is **-90.39**; the beam hands over **-263.83..-149.08**. With the axis
              at the probe POOL as well, one parent at 1000 endpoints reaches **-63.15** and **26 of
              737 rolls clear the -80.4 bar**. The bar is met. Two structural reasons it was not
              before: the pool screens **250 of 4292 (5.8%)** by a flatness prefix and a jf spread,
              both blind to the axis; and the crossing rolls ride **25-86 u off the push corridor**
              at a positive lateral (the winner: along 620.6, **lat +88.0**, jf 11), which is exactly
              what ``corridor_keep``/``align_keep``/``square_keep`` rank against. Those keeps are
              HERD constraints and the last two cycles are no longer herding.
            - **THE PLOW CAGE IS THREE HERD-RELATIVE PREDICATES, AND ONLY THE DIRECTION BINDS.**
              `in_pursuit_box` (lead band + lateral band + bearing within 21.35 deg of the herd
              bearing), `two_roll.alive` and `_frontier_score`. At the banked cycle-1 exit the pair is
              **58.91 u** apart -- inside the human's own recorded **40.4-85.2 u** plow band -- and in
              the box on the herd axis, while on ``q`` the same state reads lead -18.28 / lat +56.00 /
              delta +71.93 deg and fails all three. Freed to its coordinate-free content the stage
              returns **21x more surviving rolls** and moves a coarse two-parent frontier
              **-136.00 -> -120.71**. Real, but the pool and the keeps are the bigger lever.
            - **END TO END, THE CHAIN CROSSES THE LINE FOR THE FIRST TIME -- AND THE BOX IS WHAT CAPS
              IT.** Cycle 3 off the re-cut beam: **6 of 8 endpoints ONSIDE, best ``l0`` +38.92 at 77
              frames, all 6 admitting an entry curve**, against s133's -56.66 / ``onside=False`` /
              ``gap=inf``. Best **bound 100.06** = 77 herd + 120.00 u of gap at the walk cap + 16 cut
              (banked console 101, s125 floor 94, s126's sampled plow-then-walk-back 97.35). Read the
              ROUTE: the winners' last roll buys **+199.5 u in 29 f**, the deep-PLOW regime, so Link
              ends 120 u out and owes the retreat -- and cycle 2 handed over **-160.62**, under the
              bar, and crossed anyway. **The -80.4 bar is a condition on the BAND-KEEPING crossing,
              not on crossing at all.**
            - **AND THE BAND-KEEPING ROUTE IS REACHED AND THEN REFUSED, BY ONE CLAUSE.** Dropping
              ``require_quality`` takes cycle 2 to **``l0`` -51.75 at 52 f**, past the bar. Cycle 3
              off those states returns **ZERO survivors, every child ``outbox`` at generation 1** --
              the junction never starts. They fail ONLY the direction clauses: separations **58.84 /
              63.86 / 64.64 u**, dead centre in the human's own **40.4-85.2 u** plow band, against
              ``max_lat`` 17.99 (they read -35.51 / -49.24 / -58.57) and ``max_delta`` 21.35 deg (they
              read -37.13 / -49.63 / -66.52). Ordinary plow pairs pointing 37-67 deg off the herd
              line. So `in_pursuit_box` is the measured cap on the plan, and the free-axis prototype
              (`_notes/s134_free_axis.py`, 21x more surviving rolls) is the next step -- as a gated
              knob, NOT a widened ``max_delta`` (`[[no-overtuned-constants]]`).
            - **AND A KEEP THAT REACHES TWO OF THREE CUTS IS ONE THE THIRD UNDOES.** The CHAINED
              re-cut with the pool and the screen alone hands over **-160.62 at 48 f**, against the
              -90.39 the same stage's population screens. Diagnosed, not guessed: re-opening each kept
              node at its own pre-roll endpoint (`beam_io.split_last_roll`) and re-screening it,
              `roll_candidates` delivers exactly what that endpoint promised -- **0.00 u lost at 3 of
              4, one node +4.73 u** on the wider fan -- and the kept nodes' endpoints screen at
              ``l0_max`` -165..-269. So the beam is carrying LOW-``l0`` endpoints and the leak is the
              FINAL beam cut, which sorts on the frame rank. An ``l0`` share now sits there too.
            - **SHIPPED**: `roll_probe(pf=)` -> ``l0_max``/``l0_off``/``l0_along`` (one dot product on
              the Tetra the rollout already produced), `_probe_pool(l0_key=)`, `extend_cycle
              (l0_keep=)` -- a share at the POOL, the SCREEN and the BEAM cut -- all additive and
              default OFF. Gate
              [`tests/test_l0_screen.py`](../../tests/test_l0_screen.py) (7 + 1 slow) against a banked
              artefact [`fixtures/courtyard_l0_screen_nodes.json`](../../fixtures/courtyard_l0_screen_nodes.json).
            - **THE CLIP ROLL'S THRUST WIDENS THE FACING WINDOW, AND IT DOES NOT COST CONTACT.**
              s126 quoted thrust 9 at bound 92.50 vs 97.35 (4.85 frames). Swept thrust 9/10/11 x a
              61-value facing ladder at 5 BAM on a coarse 135-cell box: the facing window WIDENS from
              s125's one value (thrust 14) to **12-23 facings**, and none of the cells found admit an
              UNBROKEN family. **That is a property of the box, not of the thrust** -- measured,
              ``thrust`` moves only WHEN the cut fires and the roll before it is BIT-IDENTICAL (the
              overlap traces at one cell agree exactly through frame 10 and first differ at frame 11,
              thrust 9's own ``cut_step``), and ``unbroken`` reads the PREFIX ``ov[:cut_step]`` -- so
              a cheaper thrust makes the contact window SHORTER and therefore strictly EASIER to keep.
              At the s124 reference cell the margin is **+11.86 at thrust 9 against +1.13 at 14**.
              What moves is the genuine LOCUS (thrust 14's cells sit at ``lat`` +4.0..+7.4, thrust
              9's at +16.8..+27.8), and in this box those happen to be non-contact cells. The box
              finds **1 unbroken where s124's fine one finds 13**, so zero at thrust 9-11 is not
              evidence of absence (`[[infeasible-needs-proof]]`). The FINE box at thrust 9-11 is the
              open cheap item, and it is worth 4.85 frames.
      - [x] **THE STAGE FIVE SESSIONS WERE SPENT ON IS NOW 2% OF A CYCLE, AND A NODE'S 274 CHILDREN
            ARE ONE FRAME (session 133).** The queued next step was another ROLL-stage port
            (`CourtyardFleet`). Measured before building it -- s131's own lesson, applied to the
            profile that named the port rather than to the port. One new truth page,
            [`knowledge/strategy/the-frame-the-alphabet-shares.md`](../../knowledge/strategy/the-frame-the-alphabet-shares.md).
            - **THE RATIO THAT AIMED s127-s131 WAS STALE BY CONSTRUCTION.** s126 measured a cycle at
              **junction 16% / roll 84%** and the roll then got 13.6x faster. Re-measured on one
              banked cycle-2 parent (`_notes/s133_junction_cost.py`): **junction 99.2% / roll 0.8%**
              as shipped, 95.5 / 4.5 with the junction native. The queued fleet port addressed
              **2%** of a cycle. Re-measure the split after any port big enough to be worth doing.
            - **AND THE "~48% GLUE" WAS A MISATTRIBUTION** (`_notes/s133_stage_split.py`). Timed by
              section, the roll stage's prunes, metrics, sorts and keeps are **2.0%**; what the s131
              row called glue is per-frame Python inside the sections, and 52.8% of that stage is
              four camera-bearing R2 blocks against 44.9% for the fan.
            - **A CAMERA-BEARING NATIVE STEP IS 120.6 us AND THE C FRAME IS 10.8 OF IT**
              (`_notes/s133_step_anatomy.py`, `s133_camera_anatomy.py`): `LandCamera.step` **80.1 us
              at a junction state** (46.2 at a roll state -- the junction's stick is live every
              frame), `cam_pad` 8.3, the recorded row 7.3. The camera is **66% of a junction step**
              and the junction is 98% of a cycle.
            - **THE CHILDREN OF A JUNCTION NODE ARE ONE FRAME, AND IT IS STRUCTURAL.** Inside
              `_step_courtyard_nogil` the incoming `sx`/`sy`/`buttons`/`triggerL` appear in exactly
              two places -- the signature and the `_cbuf` write -- so at `input_delay=1` a delivered
              letter is buffered and never read by its own frame. Measured beside the proof: all
              **274** children land in ONE physics class and ONE csangle class at every generation.
              `FreeRun.fork_pending` steps it once and hands it to every pending letter
              (`full_herd._expand`): steps **91516 -> 26815**, the beam identical endpoint for
              endpoint. What is left is the arming probe, which is genuinely per child.
            - **A PROBE HAS NO NEXT FRAME**, so `two_roll.junction_gates` steps its arming clone with
              the camera detached and this frame's csangle injected -- bit-identical, and it drops an
              80 us model from ~26.5k probes. The look pair STAYS: her eye steers the proc-7/9 re-aim
              and therefore the `speedF` the gate reads, while the camera feeds nothing it looks at.
            - **AND THE CHEAPEST CUT WAS A STALE DEFAULT**: `beam_io.rebuild_beam` built its nodes
              with `seeds.make_freerun(env)`, `native=False` -- so the campaign's dominant stage ran
              on the **411 us** Python step, because a camera-carrying run could not be native until
              s131 and the default outlived its reason.
            - **THEN THE CLONE, which the first three cuts promoted to 58% of the stage.** A port
              leaves the Python object behind as a SEED and `FreeRun.clone` was still deep-copying
              three of them: `link._foot` is the f0 pose the core replaced (**9.5 us**, two thirds
              of the `LandState` clone) and, under ``native_look``, `zl1`/`neck` are what
              `LandCore.seed_look` was built from (**6.7 us**). Shared only where the path provably
              never writes them (`LandState.clone(share_foot=)` refuses when `_core` is set). A
              native clone **30.8 -> 12.2 us**; the wired one untouched at 27.4. The camera is
              deliberately NOT in that list -- it runs in Python after the frame, so it is state.
              **After a port, audit what the old object is still copying.**
            - **AND THE PRUNE BELONGS TO THE NODE**: `followed`/`wall`/`outbox` all read the shared
              frame, so `_shared_frame` decides them once and a dead node costs ZERO child clones
              (**91516 -> 71477**). Gated as the claim (every child's verdict == the shared frame's,
              both engines), not as its consequence.
            - **DELIVERED, one banked cycle-2 parent, same endpoints 0-ULP: 53.8 s -> 4.4 s
              (12.2x)**; the cycle 52.6 s -> 4.8 s. Gates
              [`tests/test_fork_pending.py`](../../tests/test_fork_pending.py) (6),
              [`tests/test_native_junction.py`](../../tests/test_native_junction.py) (6 + 1 slow),
              [`tests/test_stick_for_bearing_cache.py`](../../tests/test_stick_for_bearing_cache.py) (3).
            - **AND THE SEARCH PATH WAS RUN BEFORE HANDING IT OVER, which put the starting line on
              record.** Cycle-2 parents hand over ``l0`` **-183.41** (reproducing s126 exactly);
              cycle 3 reaches **-56.66** at 70 frames on the shipped screen and **-27.10** at 74 on
              s126's contact screen (``probe_contact=True, probe_step=1, probe_half=0x600``, 3x the
              time) -- **all `onside=False`**. So the last roll already buys **+126..+156 u**, past
              the +80.4 s126 measured as the band-keeping cap, and still lands short of the line.
              **-27.10 is the number a cycle-2 re-cut has to move.** TRAP worth an hour:
              `extend_cycle` at BARE defaults returns **zero** survivors here (250/250
              ``unrollable``) -- not a regression (identical on both engines), it just needs what
              `chain_herd` passes it (the handoff ``corridor``, its ``resid``, ``target_along``,
              ``arrive_keep``).
            - **WHAT IS LEFT, and both are bigger changes than any above.** Of the 4.4 s: clone
              ~1.4, `junction_gates` ~1.37, alphabet ~0.62, step ~0.58. (a) ~26.5k arming probes
              each cost a clone + a step while only ~24 children a generation survive the frontier
              keep -- and the probe's frame IS that child's next frame, so the beam computes it
              twice. (b) The alphabet is ONE `stick_for_bearing`: the toward-Tetra full stick, whose
              bearing genuinely moves per node, so it takes the 2.6 ms clamp search every time. The
              memo is already keyed on bearing MINUS camera, so that one needs a faster decode.
      - [x] **THE GATE WAS 29 MINUTES BECAUSE MOST OF ITS COST WAS NOT TESTS AT ALL -- IT IS NOW
            1:07, AND THE 2-MINUTE RULE IS MACHINE-CHECKED (session 132).** Dereck's steer, and then
            his hard rule: the per-session suite must never exceed 2 minutes, and a functionality test
            does not take a second. No model, harness or fixture code changed -- `tww_sim/` and
            `harness/` are byte-identical, so the 0-ULP surface is untouched by construction.
            - **THE DIAGNOSIS IS HIS QUESTION, NOT A SPEEDUP.** The expensive cases were not
              functionality tests: they re-ran the planner, the fan or the camera pool at test time and
              asserted the measurement that came back. `test_the_gate_reaches_the_PASS_and_not_only_the_alphabet`
              re-derived `entry_score.qualified` from an empty cache (**117 s**);
              `test_the_probe_fan_is_recentred_on_tetra...` ran a herd stage (**61 s**); the three
              `entry_ledger` spread gates each ran the camera model over a pool (**12-16 s**). Research
              re-derived per run, wearing a test's clothes. The real fidelity gates were always fast --
              `test_node1_console` 0.3 s, the 12 `test_native_camera` gates 1.9 s together.
            - **MEASURED, NEVER GUESSED, AND WITHOUT EVER RUNNING THE 29-MINUTE SUITE TO FIND THEM.**
              Per FILE first, each in its own process under a 45 s cap, so a file that blows the cap
              IS a carrier and the search is bounded (11 min): **89 of 126 files run in 87 s together**
              and six held nearly all the rest. Then per TEST, streaming `pytest -v` with a reader
              thread and a deadline so a killed run still names the case it died in.
            - **THE BAR IS THE RULE: 135 marks across 34 files**, ending with every case over 1 s.
              **29:00 -> 1:07** (1118 passed, 3 skipped, 159 deselected, 8 xfailed), serial, on the
              same box. Everything marked still runs: `pytest -m slow`.
            - **AND IT IS GATED, because a convention this repo does not machine-check drifts.**
              [`tests/conftest.py`](../../tests/conftest.py) fails the default run when it exceeds
              **120 s** or when any unmarked test exceeds the per-test budget, printing the offenders
              by name. Cost is charged as setup+call+teardown on purpose (a module fixture is paid by
              its first consumer). It trips at 1.5 s rather than 1.0 because a band of tests sits at
              0.9-1.1 and a hard 1.0 flags a different two every run -- that is noise, not drift.
              Subset and `-m slow` runs are exempt: a one-file run's first test absorbs the whole cold
              start, which is ~0.5 s of fiction.
            - **TWO NEGATIVE RESULTS worth not repeating.** `pytest-xdist` is INSTALLED but
              deliberately NOT wired in: measured 280 s -> 152 s with `-n auto --dist loadfile` and
              **worse** at 175 s with `--dist load` (module fixtures rebuild per worker), i.e. ~1.8x
              for a hard dependency, while marking alone got 4.7x for free. And marking the top test
              in a file often just MOVES its cost: `test_entry_ledger` read 20 s -> 14.4 -> 14.5 ->
              14.4 across three marks as the camera warm-up was handed down the file, and only
              re-measuring per test showed all three spread gates were independently 12-16 s (the file
              is now **1.06 s**).
      - [x] **THE CAMERA RUNS ON THE C FRAME, AND THE THING IN THE WAY WAS A GUARD -- THE STAGE
            NOW TAKES ZERO WIRED STEPS (session 131).** s130's next step, done. One new truth page,
            [`knowledge/model/the-camera-on-the-native-frame.md`](../../knowledge/model/the-camera-on-the-native-frame.md).
            - **THE EXPORT WAS NOT THE BLOCKER, AND ONE PROBE SAID SO** (`_notes/s131_attn_y.py`).
              Four handoffs queued the port behind ``attn_y`` = `fadds(92.5, ff.base[1][3])`.
              Measured over 90 frames across procs 6/7/9/30 that row **is** Link's world Y exactly
              (the lean concat has a zero translation column, so it cannot touch row 1), `m35C4`
              and `m35B8` both read 0.0, and his Y never moves -- **one distinct value** all
              window. What actually kept every camera-carrying run in Python was a `ValueError` in
              `FreeRun.__init__` saying the native step cannot drive a `LandCamera`, true only
              because nobody had wired one into `_step_native`. Measure the value a queued port
              waits on BEFORE building it.
            - **EXPORTED ANYWAY, FROM THE ENGINE THAT DREW THE FRAME.** `LandCore.attn_y` reads
              `PoseEngine._base` live rather than hardcoding a constant: the row is
              `setAttentionPos`'s (`d_a_player_main.cpp:10271`), so a ground model that ever makes
              Y move carries the camera with it. The gate asserts it against the WIRED `FootFK`'s
              own base row per frame -- the claim is "the C base tracks the Python one", not
              "92.5 + Y is 92.5 + Y", which would pass by construction.
            - **ONE EXPRESSION, TWO PATHS.** `FreeRun._run_camera` is the camera Run for both step
              paths; they differ only in where pos/facing/`attn_y`/lock come from. It surfaced a
              real trap on the WIRED path: its camera, her look and his neck all run AFTER the row,
              so `step(record=False)` silently froze three models that are STATE. Documented as a
              precondition since s34, now enforced -- and the native path keeps `record` meaning
              only "build a row", since there the look pair is inside the frame and the camera
              after it.
            - **DELIVERED, counted then clocked idle** (same stage, same knobs, same prologue as
              the s130 row): **1029 wired + 9083 native -> 0 wired + 10112 native**, 0.681 s ->
              **0.354 s (1.9x)**, **13.6x** against the all-wired stage, same five candidates. The
              camera model runs exactly as often either way (1731 steps) -- only the frame around
              it moved. `seeds.make_freerun(native=)` is the whole switch; `cycle1_nodes(native=)`
              (on by default) hands it to the chain, since a node's run is what every later stage
              steps.
            - **MOVING THE ENGINE MOVED WHAT ``run.link`` MEANS, AND A GATE CAUGHT IT.** On a
              native run that `LandState` is a FIELD-HOLDER synced from the core, so
              `run.link.pos_x = ...` is a silent no-op and `_computed_center(run.link)` answers off
              the **f0 SEED pose**. Both now go through the run -- `FreeRun.co_center()` asks
              whichever engine posed the frame, `FreeRun.place_link()` is the teleport recipe
              (move, re-centre, rebuild the pending push) driven through that engine's owner, and
              the three copies of that recipe (two synthetic beds + the freeze-bar gate) are one.
              `LandCore.co_center_exec` is the second export. **A correction deliberately NOT made
              here:** every run-level caller reads the centre with ``init_frame=False`` while the
              core knows the frame's true `*_init` flag (~1.7 u apart on an init frame), so the
              export takes an OVERRIDE and the port reproduces the approximation exactly rather
              than smuggling a search-visible change into a perf port.
            - **WHAT IS LEFT IS NOT WHAT THE BIGGEST PER-CALL NUMBER SAYS.** A `LandCamera.step` is
              **44.0 us** against a whole coupled frame's **10.9 us** (C 8.2 + a 2.7 us Python
              wrapper) -- 4x -- but priced against the stage it runs in: frames **31%** (10112),
              camera **21%** (1731), and **~48% is the stage's own Python glue** (clones, per-frame
              input dicts, prunes, metrics, sorts). The C engine is now a minority of its own search
              stage, and the move that takes the top two TOGETHER is stepping frames in C rather
              than one Python call per frame (`CourtyardFleet`) -- which needs the camera in C to
              carry a camera run, so they are one piece of work. **Trap:** cProfile charged
              `_step_native` 13.2 us of own time per frame; timed in a loop the wrapper is 2.7 --
              price a hot call with a loop, not a profile. Gate
              [`tests/test_native_camera.py`](../../tests/test_native_camera.py) (12), which
              counts the stage's wired steps as a claim of its own so a silent fallback to Python
              cannot pass by being the reference.
      - [x] **THE CAMERA-TARGET PASS SHARES THE ROLL, AND THE BRANCH IS READ OFF THE ROLL RATHER
            THAN SET (session 130).** s129's next step, done. One new truth page,
            [`knowledge/strategy/the-shared-roll-body.md`](../../knowledge/strategy/the-shared-roll-body.md).
            - **THE DIVERGENCE FRAME, MEASURED FIRST** (the s129 handoff's own condition). Over the
              real 25-value grid x 5 aims x 3 L windows the physics is bit-identical for **17 of a
              22-frame segment**, and the first frame that differs is exactly the first frame after
              the `FRONT_ROLL` block -- so `roll_kernel.SharedBody` reads its ``branch`` off the
              roll's own end as it steps, and is right for whatever THIS node's roll is.
              [`tests/test_tcs_kernel.py`](../../tests/test_tcs_kernel.py) gates both halves
              separately: SAFETY (no frame before it depends on the target, any target) and
              TIGHTNESS (some target diverges AT it -- per aim it can be later, or never, when the
              roll ends in proc 6 with Link stopped and there is nothing left to steer).
            - **ONE BODY'S CAMERA ARGUMENTS SERVE THE WHOLE FAMILY, PAST THE DIVERGENCE.** They are
              Link's pose and the attention, so they are shared -- and measured, they reproduce
              every target's committed csangle 0-ULP over the WHOLE segment, including frames where
              that target's physics has already diverged (`FreeRun`'s "csangle is
              position-independent in this regime", cashed in). `camera_walks` walks them as a
              PREFIX TREE -- targets that have delivered the same C-stick bytes share one camera
              object -- **775 camera steps -> 529**. `FreeRun.step` now publishes the arguments as
              ``sim_cam_in`` so the walk reads the pad and the law through the run's own expression.
            - **THE FAN WOULD HAVE BEEN THE WRONG LEVER TWICE, AND ONE OF THEM ONLY SHOWED UP
              BECAUSE A GREEN GATE WAS CHECKED FOR VACUITY.** (1) Fanning over camera targets is a
              LOSS: a camera trace is ~32 wired steps against the 20-step rollout it replaces.
              (2) A native endpoint cannot be stepped by the next stage -- `junction_quality`
              scored IDENTICALLY on native and wired endpoints, 250 of 250, and that was **two
              `None`s 250 times** (`scored: 0/25` on this node). The states behind the tie differ:
              a centred C-stick does NOT freeze csangle on the spot, the camera chases for several
              frames, so the six-frame glide off a frozen-csangle endpoint is not the wired one
              (1 of 25, 0.009 u). The same wrong assumption, taken as a walk shortcut, collapses
              775 camera steps to 10 and is off by 178 BAM at frame 5.
            - **WHAT IT COST AND WHAT IS LEFT** (counted, at the aim step s129's row was measured
              at, so the rows compare): **2251 wired + 4566 native -> 1030 wired + 4566 native +
              701 camera-only**, **1.088 s -> 0.629 s (1.73x)**, 4.82x against the all-wired stage,
              same five candidates. At `cycle1_nodes`' own shipped aim step (twice the fan) the
              same stage is 11235 -> 1030 wired and 4.871 s -> 0.719 s (**6.78x**) -- R2's cost
              does not grow with the fan. **654 of the surviving 1030 wired steps (63%) are
              `junction_quality`**, 376 the bodies and tails.
            - The port is a DROP-IN: what comes out is a genuine wired run at the genuine endpoint,
              so `junction_quality`, the ``tcs_probe``/``tcs_key`` orders and the next cycle's
              junction are untouched, and it works on EVERY cycle rather than only plainly-ranked
              ones. ``shared_body`` defaults to on wherever ``env``/``twin`` already is;
              [`tests/test_fan_stage.py`](../../tests/test_fan_stage.py) now runs R1 and R2 alone
              as well as together, so two ports cannot cancel and a failure names its half.
      - [x] **THE SCREEN IS ON THE FAN KERNEL, AND IT NEVER NEEDED RUNS AT ALL -- 66% OF THE STAGE
            IS NOW C (session 129).** s128's next step, done. One new truth page,
            [`knowledge/strategy/a-screen-needs-a-record-not-a-run.md`](../../knowledge/strategy/a-screen-needs-a-record-not-a-run.md).
            - **WHAT THE STAGE ACTUALLY KEEPS.** `roll_candidates`' R1 is ~74% of the stage's
              rollouts and its whole output is three ``(want, aim, l_window)`` triples -- every
              `FreeRun` it builds is DISCARDED. The prunes and the rank in between read nine fields
              (Link XZ/facing/travel/speedF/proc, Tetra XZ, csangle, the follow flag), and
              `segment_record` already carries all nine, so `roll_kernel.RecordRun` presents a record
              in the shape a run is read in and `two_roll.metrics` / `alive` / `frame_in_model` /
              `rank_key` run over fan records UNCHANGED. R2 stays wired on purpose: its survivors ARE
              their runs (the candidate carries one to the next cycle, `junction_quality` steps it).
            - **THE ACCOUNTING, COUNTED FIRST** (so it does not move with machine load) -- one
              cycle-1 roll stage at the shipped knobs: **6719 wired steps -> 2251 wired + 4566
              native**. At the s128 engine rates that predicts ~17x on R1 and ~2.8x on the stage, and
              the idle clock agrees: **3.000 s -> 1.078 s (2.78x)**, same 5 candidates. The look-pair
              lesson on schedule -- what is left does not get cheaper, so quote the stage. **All 2251
              remaining wired steps are R2.**
            - **THE GATE, AND THE SEED THAT MAKES IT MEAN ANYTHING.**
              [`tests/test_fan_stage.py`](../../tests/test_fan_stage.py) (8, ~19 s) compares the
              STAGE fan-on vs fan-off -- same candidates, same order, same knobs, endpoints `==`.
              The obvious seeds are the wrong ones: off every banked cycle-2 junction endpoint the
              stage returns NOTHING at any thinning (from ~40-70 u behind her a ~205 u `FRONT_ROLL`
              ends 231-253 u away, past `FOLLOW_ENGAGE_DIST`, and `alive` prunes on ``followed``;
              the few that stay inside end AHEAD of her and die on ``lead``), so both paths agreed
              about nothing. The firing seed is cycle 1's own PROLOGUE node -- state 2 plus one
              L-held flip frame, 5 candidates -- and the gate asserts the comparison is non-vacuous.
            - **TWO TRAPS THAT ARE NOT ABOUT PHYSICS.** (1) The screen's sort is STABLE, so ties
              break by insertion order, and the fan evaluates per L WINDOW while the wired loop walks
              (aim, window) -- the fan path walks the wired order deliberately, and the gate squeezes
              both keeps to 1 so that order decides the whole output. (2) A twin is exact about
              whatever state it reaches: the replay-from-log premise held (a banked endpoint replays
              to the position and camera the fixture recorded from the search's own run) but
              `node_twin(check=)` now asserts it at RUNTIME, since a log that stopped reconstructing
              its node would make every record bit-exact about a state the search never visits.
            - **THE STOPGAP STAYS, MEASURED.** s128 wanted `full_herd` to RECORD csangle as it steps
              rather than replay for it. The replay is one log (~55 frames) against a screen of ~216
              roll segments, so it is a few percent of the stage it feeds -- and the recorder is a
              change to every log-append site with clone/branch semantics. Not worth it yet.
            - **NEXT IS NAMED BY THE MODULE'S OWN GATED FACT**: `target_cs_is_exit_only` -- inside a
              roll the camera target changes nothing but the camera -- so R2's 25 rollouts per kept
              aim are the SAME physics 25 times, differing only in the exit tail. A shared-body
              kernel, not a fan, and it needs its own divergence-frame gate.
      - [x] **THE LOOK PAIR IS IN THE C FRAME TOO -- THE COUPLED STEP IS 6.8x AND A ROLL FAN 18x
            (session 128).** s127's next step, done. One new truth page,
            [`knowledge/model/porting-the-look-pair.md`](../../knowledge/model/porting-the-look-pair.md).
            - **THE GATE FIRST, AND IT FAILED AS WRITTEN.**
              [`tests/test_native_zl1_look.py`](../../tests/test_native_zl1_look.py) (7, 0.9 s)
              diffs a fully-native run against `make_freerun_self_eye` frame by frame: physics, the
              eye, m3564, and her WHOLE hidden state -- the joint chase angles and their clamped
              targets, every timer, the McaMorf ctrl, and **the morf's per-joint old-pose store**,
              which is the one that matters: it is rewritten every frame and only reaches the eye
              through the NEXT blend, so a wrong store is silent for a frame and then diverges.
              Sensitivity checked rather than assumed -- a 1-BAM perturbation of an armed constant
              diverges at frame 10 (hers) and frame 3 (the neck's).
            - **THE RECORDED WINDOW DOES NOT EXERCISE HER, so the gate runs a long one too.** Over
              the 45 movie frames ``f84d == 1`` on every frame and ``f7b8`` is seeded at **116**, so
              the look-around anim switch, the morf blend it starts, the wrap flag and the RNG
              horizon are ALL past the end of the fixture. `test_the_long_window_actually_exercises_her`
              asserts that coverage, so none of those four fields is being compared to a constant.
            - **THE SPLIT, MEASURED FIRST (s127's own habit).** Her `Zl1Look` **77.5%** of the step,
              `NeckLook` **13.4%**, the C core itself **9.1%** -- and inside her frame `_pose_eye` is
              71% (`pose_locals` alone 52%). So the port is mostly a DATA move: her keyframe bank
              becomes C-resident (`Zl1AnimData`) the way Link's `AnimData` already is.
              [`tww_sim/core/anim/_zl1c.pxi`](../../tww_sim/core/anim/_zl1c.pxi), `include`d into
              `_anmc.pyx` because it runs inside `_step_courtyard_nogil`.
            - **DELIVERED 6.8x, NOT THE 9x THE RATIO NAMED, and the gap is worth keeping.**
              **9279 -> 62682 steps/s**; the look pair went **97.4 -> 5.6 us/frame**. A ratio of
              "X is 89% of the step" assumes the ported X is free -- it is not (still 35% after),
              and the stripped run's 96k is a ceiling you approach and never reach.
            - **THE FAN, WHERE THE SEARCH ACTUALLY SPENDS.** `roll_kernel.self_eye_twin` defaults to
              the native-look twin, so `roll_fan` gets it directly: on the s127 unit a 143-aim fan is
              **1.05 s (wired) -> 0.29 s (s127) -> 0.057 s**; on the full 5600-aim `roll_aim_fan`
              grid **41.0 s -> 2.24 s (18.3x)**, records `==` the reference. `test_roll_kernel` now
              runs its whole 14-gate record comparison on BOTH engines (23 tests) rather than
              inheriting the claim.
            - **THE PARALLEL PATH IS ALREADY DE-RISKED.** The chain is nogil, so
              `CourtyardFleet.run_par` carries it bit-identical to sequential -- gated, with a
              deliberately WIDE csangle spread: at a 1-BAM spread eight cores land on three distinct
              Link positions, Tetra does not move differently at all, and every eye comes out
              identical, so a fleet gate seeded like that would pass without the look chain running.
            - **TWO TRAPS THE 0-ULP GATE CAUGHT-BY-DESIGN.** (1) The models reach `absXZ` through
              `collision.fsqrt` = a CORRECTLY-ROUNDED sqrt, while the native engine also carries
              `_sqrtf_c` (the MSL `frsqrte`+3-Newton `std::sqrtf`); they agree to ~2^-32, the exact
              size that survives a plausibility check. (2) Her non-morf pose is
              `J3DGetTranslateRotateMtx` off the EULER while storing the euler->quat for the next
              morf -- not the same matrix in the low bits, so the two paths cannot be merged.
      - [x] **THE ROLLOUT NOW RUNS IN C, AND THE EYE WAS THE ONLY THING KEEPING IT IN PYTHON
            (session 127).** s126's next step, done -- but not the way it was written. The port is
            NOT a ShoveCtx-class baked kernel and the camera did NOT need porting. Two new truth
            pages, [`knowledge/model/the-eye-was-the-only-thing-in-python.md`](../../knowledge/model/the-eye-was-the-only-thing-in-python.md)
            and [`knowledge/strategy/the-fan-pays-for-one-camera.md`](../../knowledge/strategy/the-fan-pays-for-one-camera.md).
            - **THE GATE FIRST, AS ORDERED, AND IT FAILED AS WRITTEN.**
              [`tests/test_roll_kernel.py`](../../tests/test_roll_kernel.py) (14, 15 s, runs by
              default) compares a fan kernel to `two_roll.roll_segment` on the WHOLE record -- every
              returned field plus the endpoint state -- over 4 configs x 6 real seeds x 24 aims,
              `==` and never a tolerance. The record carries ``followed`` for the same reason it
              carries ``talk_unsafe``: `two_roll.alive` PRUNES on it through `metrics`, and a kernel
              that reproduced the endpoint but not the flag would change which rolls survive. One
              gate asserts the seeds produce BOTH values of each prune field, so none of them is
              being checked against a constant. Seeds are minted (`fixtures/courtyard_roll_kernel_nodes.json`)
              as `junction_beam` endpoints AND cycle terminals, because they are not interchangeable:
              at a junction endpoint the whole fan is talk-SAFE and at a terminal the whole circle
              TALKS (**143 of 143**, measured), which is the only place the refusal branch can be
              gated at all.
            - **WHAT THE MEASUREMENTS SAID, and each one moved the design.** (1) The native step IS
              the wired step, 0-ULP over whole banked node logs, when csangle and the proc-9 eye are
              injected. (2) **The csangle sequence through a roll is bit-identical across a full
              143-aim fan** -- on every node, at every C-stick mode -- so a fan pays for ONE camera;
              the C-stick target does move it, so this is a lever and not a dead camera. (3) The eye
              is NOT shareable (143 distinct sequences) and cannot be dropped: her feet instead of her
              eye moves the re-aim 180 BAM and a node log **123 u**. (4) Link's head-top Y is not
              aim-independent either (41 classes), and she looks at him every frame of the segment
              (``f84d == 1``), so no shortcut around her look model exists.
            - **SO THE BLOCKER WAS TWO MATRICES, AND THEY WERE ALREADY IN C.** `Zl1Look` needs Link's
              exec-pass ``mHeadTopPos.y``; `NeckLook` needs the cached previous head MATRIX. Joint 15
              is already posed with the body-Co extras, so ``HEAD_CHAIN`` is ONE concat past the
              Co-centre chain the engine already walks: `PoseEngine._head_top`/`_head_mtx` +
              `LandCore.head_top_exec`/`head_mtx_exec`, gated 0-ULP vs `foot_fk` AND vs
              `from_f0._computed_head_{top,mtx}` frame by frame
              ([`tests/test_native_head_top.py`](../../tests/test_native_head_top.py), 4). The gate
              pins the proc-``*_init`` zero-lean CONVENTION, not just the value: the two differ by
              **1.4 u in x and 3.4 in z on frame 1**, ~100x the razor's acceptance band.
            - **`seeds.make_freerun_self_eye` -- the coupled frame in C, generating its own eye**
              (`from_f0._step_native` self-eye mode). 0-ULP vs the wired run on Link, Tetra, the eye
              and m3564, plus a cloned run ([`tests/test_freerun_self_eye.py`](../../tests/test_freerun_self_eye.py), 4).
              **2796 -> 10797 steps/s (3.9x)**, and `roll_kernel.roll_fan` does a 143-aim fan in
              **0.29 s against 1.05 s (3.6x**, 3.2x with the per-node twin+trace setup).
            - **THE NEXT PORT IS NAMED BY THE RATIO, NOT GUESSED.** Stripped native is 98179 steps/s
              and self-eye is 10797, so **`Zl1Look` + `NeckLook` are now ~89% of the step** -- worth
              ~9x more, and nothing else in the frame is worth looking at. Do NOT quote the 98179: it
              is a DIFFERENT simulation (the feet fallback), and reporting it as the search's speed
              is reporting a different answer arriving faster.
      - [~] **THE SEARCH IS ON THE SLOW ENGINE, AND 84% OF A STAGE NEEDS NO CAMERA (session 126,
            Dereck's directive: "we need to attack this with raw compute").** Measured, three engines
            in this repo, same coupled courtyard frame:
            | engine | rate | vs the search |
            |---|---|---|
            | `seeds.make_freerun` -- Python step, wired camera/zl1/neck, **what the herd search runs on** | **2431 steps/s** | 1x |
            | `seeds.make_freerun_native` -- the same frame in C, camera STRIPPED | **106294 steps/s** | **43.7x** |
            | `ShoveCtx.sweep_par` (`tww_sim/core/_shovec.pyx`) -- compiled roll, parallel | **130137 ROLLS/s = 2.08M frame-steps/s** | **857x** |
            So the 100k/s Dereck remembers is real and is IN this repo -- it is what the razor solve
            runs on, and the herd search was never moved onto it. One roll rollout is 7.5-12.5 ms, so
            a 100k-aim sweep costs **~21 minutes single-threaded**, and every wall-clock figure from
            s102 on is inflated by that factor. Where the Python step goes: **anim/pose 33%, camera
            22%, land 9%, zl1 look 9%, push/cc 7%, math 6%, neck 4%.**
            - **THE SPLIT IS THE OPENING.** At the shipped ``probe_cap=250`` a stage is **junction 16%
              / roll 84%** (measured on a real c2 node: junction_beam 4622 endpoints in 53 s, then
              3432 rolls in 25.9 s, scaled to the shipped cap). And a roll is **FACING-LOCKED** -- the
              main stick is inert for its duration -- so the camera cannot move its trajectory. 84% of
              a search stage is exactly the workload `ShoveCtx` already does at 130k coupled rolls/s,
              plow + her follow AI + both CrrPos included.
            - **THE ORDER, AND WHAT EACH BUYS.** (1) Port the HERD roll onto a ShoveCtx-class kernel
              (analytic schedule, no cut, batch parallel sweep) -- 84% at ~500x is **~6x per stage**
              and reuses a kernel that is already 0-ULP-gated. (2) Then the junction's 16%, which is
              camera-dependent: port `LandCamera` + `NeckLook` + `Zl1Look` into the native step so the
              whole rollout runs in C -- the 43.7x path, another ~5x, **~25-30x total**. (3)
              Parallelise whatever stays in Python; a node IS its input log (`beam_io`), so workers
              rebuild from logs and nothing shared has to be pickled.
            - **THE GATE COMES FIRST, NOT THE PORT.** A kernel roll must be 0-ULP against
              `two_roll.roll_segment` on Link pos/facing/travel/speedF/proc + Tetra XZ, seeded from
              real banked beam nodes, or it is worthless (`[[zero-ulp-tests-only]]`).
            - **THREE THINGS THE PORT MUST NOT DROP** (all read off `roll_segment`, and all cheap to
              forget): the roll's **exit csangle** -- the C-stick IS live during the roll, slewing
              toward ``target_cs``, and the next junction's whole aim alphabet is placed against that
              exit value, so the trajectory is camera-free but the EXIT STATE is not; ``talk_unsafe``
              (an A-press that talks to her kills the run); and ``ok``/``roll_speedF`` (the arming
              predicates the fan prunes on). A kernel that reproduces the path but not these three
              silently changes which endpoints exist.
      - [~] **THE LAST CYCLE CANNOT ALSO BE THE TERMINAL -- THE CROSSING AND THE RUNWAY ARE ONE
            RESOURCE, AND THE BILL BELONGS TO CYCLE 2 (session 126).** The s125 next step is DONE (the
            terminal predicate is wired in as the last cycle's endpoint rank) and running it says the
            re-cut cannot succeed as posed: it is not a ranking problem. New truth page
            [`knowledge/strategy/the-crossing-and-the-runway-are-one-resource.md`](../../knowledge/strategy/the-crossing-and-the-runway-are-one-resource.md),
            gate [`tests/test_handoff.py`](../../tests/test_handoff.py) (12, 8.9 s, runs by default).
            - **THE RANK IS WIRED AND AFFORDABLE.** `extend_cycle` takes ``handoff_keep`` -- her ``l0``
              SIGN first, then `handoff.endpoint`, which prices a herd endpoint as
              ``frames + gap/WALK_CAP + cut_step``, admissible on every term. Two economies made it a
              rank rather than a report: `resid_window` (outside contact the residual is ONE NUMBER
              bit-for-bit, so a 561-sample coarse pass says where the 28001-sample fine one has
              anything to find -- **identical brackets**, 4-11x) and `entry_roots` (the bisected roots
              without the f32 band walk, an under-estimate by construction, another 3x). **19 s ->
              ~1.5 s per endpoint**, against ~28 s for the `cloud_land` stack it replaces.
            - **AND THE POPULATION IT RANKS IS STRUCTURALLY WRONG.** Over **20592 full-circle rolls**
              off 3 banked c2 parents (48 armed junction endpoints each, every herd prune off): **51
              carry her across the approach line, 12366 leave Link at runway >= 190, ZERO do both.**
              The deepest crossing roll ends at runway **89**; the entry curve starts at 190. Carrying
              her across means rolling THROUGH her, and that carries Link just as far past the corner.
            - **THE EXCHANGE RATE, WHICH IS THE USABLE FORM OF IT.** Past ~150 u of runway the best
              crossing available stops moving at all -- **+80.0..+80.4 u over six hundred units** (that
              is her FOLLOW, not a plow) -- and below ~100 u it more than doubles (+196.2 at runway
              0-50). The knee is sharp: runway 89 -> +12.9, runway 107 -> -30.8. So a last roll that
              keeps the band buys at most **+80.4 u**, and **cycle 2 must hand over ``l0`` >= -80.4**
              against the **-160.6..-183.4** the banked c2 beam delivers. That is the whole remaining
              gap, stated one cycle up.
            - **THE OTHER ROUTE IS PRICED, NOT FREE.** Let the last roll plow her across (+196 u) and
              walk Link back: measured on all 51 crossing rolls he lands **112-238 u** from the nearest
              genuine entry (median 217) = **7-14 frames** of retreat before any turn to the roll's
              facing. All 51 admit an entry curve (s125's "every on-side endpoint clips", re-confirmed
              on a fresh population); the best is **97.35** frames against the banked **101** and the
              s125 floor of **94**. That best is a SAMPLING statement -- 48 of 4382-8678 junction
              endpoints, one ``l_window`` -- not a frontier.
            - **THE CUT TIMING DOES NOT MOVE THE BAND, BUT IT BUYS 5 FRAMES.** ``thrust`` is the
              B-press frame and the cut lands at ``thrust + 2``, so a shorter roll looked like the way
              to walk the entry band down onto the herd. Swept 6..16 at a real crossing endpoint it
              does not: the band's lower edge stays ~180-220 at every thrust (Link must REACH the
              corner and brace before the cut -- s124's attractor). What it does buy is ``cut_step``:
              **thrust 9 cuts at 11**, five frames cheaper than 14, still genuine -- bound **92.50 vs
              97.35** at the same endpoint. The cheapest single knob measured in this shape, and it was
              never swept. **The empty rows (6-8, 12, 13, 16) are SCOPED negatives, not refusals**
              (`knowledge/history/thrust-13-refused-by-geometry.md` is this mistake one axis over): one
              Tetra, one facing -- solved at thrust 14, and s125 measured that window to be ~one value
              wide -- lean 0, rungs 30-400, while the arrive-rather-than-slide family sits near
              ``26 * cut_step``, i.e. 286 u at thrust 9 but **416 u at thrust 14, past the ceiling
              swept**. A claim about a thrust owes its own facing sweep and a wider ladder.
            - **AND THE c2 REQUIREMENT IS ON THE CYCLE, NOT ON ITS AIM (preflight, run).**
              `beam_io.split_last_roll` re-opens each banked c2 terminal at its PRE-ROLL endpoint
              (0-ULP, re-fired) and the full aim circle from there moves the handoff by **-10.3 to
              +18.2 u** -- best ``l0`` **-159.4** against the -80.4 needed, and several nodes' best
              re-aim is WORSE than what they bank. Off that state the roll buys ~+89-118 u of crossing
              however it is aimed. So the crossing must come from the JUNCTION (where Link repositions
              without a 400 u commitment), which is exactly what `extend_cycle` searches -- the same
              conclusion `roll_candidates` reached about the LATERAL one cycle down.
            - **NEXT: RE-CUT CYCLE 2 AGAINST ``l0``**, at the per-aim SCREEN and not only at the
              endpoint keep (`tetra_lateral` is one dot product, so unlike the terminal rank it is
              free there -- and the screen is the cut that decides which endpoints exist, s107). Then
              let the last cycle spend its length on Link's position instead of on her crossing and
              re-run this session's endpoint rank on it. Cheap and unexplored beside it: thrust 9-11
              for the clip roll (5 frames), and a facing sweep AT that thrust (40835 was solved for 14
              and s125 measured the facing window to be ~one value wide, so thrust 9's is elsewhere).
      - [x] **THE RAZOR IS ON LINK, NOT ON HER -- AND EVERY HERD ENDPOINT THAT PARKS HER ON THE RIGHT
            SIDE ADMITS A CLIP ROLL (session 125).** The chain-back, run: 15 of 127 banked cycle-3
            endpoints leave her on the genuine side of the clip roll's approach line, and **all 15 have
            a genuine Link entry** (3-7 each, 74 in total). New library
            [`harness/tetrapush/handoff.py`](handoff.py), new truth page
            [`knowledge/strategy/the-razor-is-on-the-pusher-not-the-pushed.md`](../../knowledge/strategy/the-razor-is-on-the-pusher-not-the-pushed.md),
            gate [`tests/test_handoff.py`](../../tests/test_handoff.py) (7, 2.4 s, runs by default).
            - **THE COORDINATE HAD TO GROW A FOURTH AXIS.** `terminal.RollFrame` pins Link's entry to
              the brace line (``entry = brace - runway*m``) because s124 asked the question in the shape
              where Link WALKS to a chosen spot. A herd arrives off that line by tens of units, so
              `PairFrame` restores ``side`` -- ``entry = brace - runway*m + side*q`` -- and at a FIXED
              Tetra the two laterals collapse (``lat = l0 - side``), which makes the genuine set a
              **CURVE OF LINK ENTRIES**, one solved ``side`` per ``runway`` (`entry_locus`). ``side`` 0
              is `RollFrame` bit-for-bit, so terminal's bracket/bisect/band methods run on it unchanged.
            - **AND ON LINK'S AXIS THE ACCEPTANCE IS 4.5e-5..5.1e-4 u INSIDE A CONTACT CORRIDOR ~1 u
              WIDE** (measured -0.105..+0.895 at the s124 reference cell; outside it the residual
              saturates at its no-contact value). So `SIDE_STEP` is **0.005**, 100x finer than
              `terminal.LAT_STEP` -- a half-unit bracket step straddles the whole corridor and reports a
              clipping configuration as empty. Affordable: one span is a single 28001-sample batch sweep,
              0.4 s at 72k coupled rolls/s.
            - **THE CHAIN-BACK TURNS ON A SIGN, NOT A DISTANCE.** Her own offset from the approach line
              (`tetra_lateral`, ``l0``) is **+2.50..+13.69** over the 288 tabulated coords, **+0.57..
              +51.00** over the 51 solved terminals and **+0.57..+4.89** over the 13 unbroken-contact
              ones -- all one side. The console-confirmed 71-frame herd leaves her at **-17.67** (the
              escape push is what finished the crossing to the +2.75 of the coord it landed on), the two
              banked beams' terminals span **-71.15..+19.65** and their pre-roll states -243.8..-108.9.
              So the last roll is what carries her across, and the first question of any endpoint is
              which side it left her on.
            - **WHAT IS LEFT IS ENTIRELY LINK'S POSITION.** On the 15 on-side endpoints the clip roll is
              always available; Link ends the herd's last roll **73-171 u** from the nearest genuine
              entry (too deep by 58-190 u of ``runway``, too far across by 30-57 u of ``side``). The
              planning consequence: **score a herd by whether it leaves LINK on the curve, not by where
              it puts her** -- her placement is free inside a wide band, his is a 1e-4 u razor.
            - **PRICE: a floor of 94** (73 herd frames + 5 to close 73.69 u at the walk cap + 16 of clip
              roll) against the banked **101**, at three 73-frame nodes of the s122 require beam. It is a
              FLOOR, not a plan: the 5 charges the gap at cap speed with no turnaround and no guarantee
              the move lands ON the razor (`[[banded-proxy-needs-its-newton]]`).
            - **THE CLIP ROLL'S AIM IS NOT FREE.** On one coarse handoff box (14x19 cells) facing 40835
              yields 15 genuine / 13 unbroken and **every facing on a 500-BAM ladder from 29000 to 44000
              yields 0**; refined at 25 BAM, 40810 and 40860 yield 0 and 40735/40760 one each. On the
              FULL s124 box 40810 gives 3 genuine (0 unbroken, overlap 1.50-1.68 not 1.13) and **36888 --
              a facing the herd's own last rolls actually deliver -- gives 0 of 1540**. So the last roll
              has to be aimed at the corner deliberately; the herd's own 31474-36888 are dead.
            - **TWO TRAPS, BOTH GATED.** (1) `m`/`q` come from the console's f32 sin/cos tables, so the
              basis is orthonormal only to ~1e-7: projecting a genuine world pair into the coordinates
              and rebuilding it moves the residual **8.3e-5 -> 1.05e-3, genuine to dead**, twelve band
              widths lost in the trip -- hold positions, report coordinates. (2) A brace-centred +-60 u
              ``side`` span at a real herd Tetra reaches a maximum overlap of **-91.8 u**, not one sample
              in contact, and reads as flatly infeasible; the corridor sits at ``side ~ l0``.
            - **NEXT: re-cut the LAST CYCLE against `entry_locus`.** The terminal predicate is now
              computable on a delivered state (`handoff.probe` / `node_gap`), so the last cycle can be
              searched to leave Link ON the curve instead of 74 u past it -- which is where the frames
              below 94 are.
      - [x] **THE ZERO-WALK-AWAY BEST CASE EXISTS, AND THE RAZOR ASKS FOR ALIGNMENT AND NEVER FOR DEPTH
            (session 124).** The terminal configuration is SOLVED -- the first work in Dereck's re-aimed
            shape, and it closes the open unknown the s123 handoff named. New library
            [`harness/tetrapush/terminal.py`](terminal.py), new truth page
            [`knowledge/strategy/the-corner-sets-the-depth-not-the-herd.md`](../../knowledge/strategy/the-corner-sets-the-depth-not-the-herd.md),
            gate [`tests/test_terminal.py`](../../tests/test_terminal.py) (11, 1.4 s, runs by default).
            - **THE BEST CASE EXISTS: 51 genuine terminal configurations, 13 of them with Link ALREADY
              TOUCHING HER at the roll entry and contact NEVER BREAKING for the whole roll**, at handoff
              distances **50-110 u** -- the range the herd already oscillates over (41-85 u live). No
              escape, no walk-back, no separate clean roll-in. Swept over a 1540-cell handoff box
              (``runway`` 140-480 u x ``along`` 30-245 u) at the delivered facing 40835 / thrust 14 in
              **41 s**.
            - **THE OPEN UNKNOWN IS ANSWERED, AND THE ANSWER IS THAT IT WAS THE WRONG WORRY.** "The clip
              wants ~1.23 u of overlap and a herd roll's depth is whatever the plow produces" is true and
              does not matter: **the corner washes the handoff out.** Over handoffs **50-245 u** apart,
              with the roll plowing her **53-126 u**, the last three overlaps converge to 18.3/18.4/13.7
              -> 6.76/6.75/6.70 -> **1.132/1.132/1.127**, her cut-frame position lands in a **0.054 x
              0.205 u** box, Link's braced point is constant to **0.001 u** and the cut lands inside
              **0.003 u**. So the depth is the CORNER's, the herd does not have to place her (the last
              roll parks her), and the only sensitive axis is the pair's LATERAL ALIGNMENT:
              ``d(resid)/d(lat)`` -4.0..-14.3 /u against ``d(resid)/d(runway)`` **+0.17 /u**.
            - **THE PAIR IS THE COORDINATE.** `RollFrame` states a configuration the way a herd hands one
              over -- ``entry = brace - runway*m``, ``tetra = entry + along*m + lat*q`` -- instead of the
              old fixed-entry/fixed-Tetra slices (`tetra_placements.tsv` and `entry_search`'s locus are
              both slices of this surface). `classify` adds whether he starts touching her, whether
              contact breaks, and how far the roll plows her. ``runway`` is what a longer-than-normal EBS
              buys (Dereck's s124 steer, and it is 190-310 u at every hit).
            - **THE LEAN IS NOT A BAR** -- `entry_search`'s "m351C 64 already does not clip (resid 1.1e-2)"
              is measured at a FIXED ENTRY, where 1.1e-2 is a hundred window widths. Re-solving ``lat``
              finds genuine configurations at **every lean -191..+191**, most in unbroken contact,
              including the +64 that reads dead and the -191 a replayed herd hands over. It also decays
              35%/frame -> 0 in 13 frames, so the long backslide flattens it for free.
            - **METHOD: BRACKET, THEN BISECT -- never sweep.** The acceptance band is **2.2e-5..1.5e-4 u**
              against a residual gradient of 4.0-14.3 /u, so the module's own 281-sample bracketing grid
              returns NOTHING at a cell that clips (gated). `razor_crossings` finds the SIGN CHANGE,
              `solve_razor` bisects every bracket IN LOCKSTEP (one batch sweep per round -- 2500 razors
              cost 62 sweeps, not 155000), `genuine_band` walks the f32 band and flags ``clipped`` when
              the width is only a lower bound.
            - **THE ENGINE WAS NEVER THE 34x PROBLEM HERE**: `ShoveCtx.sweep_par` is **76k full coupled
              rolls/s** on this hardware -- 30x the `seeds.make_freerun_native` rollout rate the s123
              handoff pointed at, which is the right tool for the HERD stage, not the terminal one.
            - **NEXT: chain backwards.** The terminal set is characterised, so the question is now which
              herd delivers a pair in it -- and the target is a lateral alignment at a 50-110 u handoff,
              not a placement.
      - [x] **THE ALONG AXIS WAS NEVER A LEVER, AND THE ARRIVAL BILL IS THE ROOM: BOTH s122 OPTIONS
            ARE ANSWERED, ONE IN THREE MINUTES (session 123).** Two new truth pages,
            [`knowledge/strategy/the-handoff-along-was-already-spanned.md`](../../knowledge/strategy/the-handoff-along-was-already-spanned.md)
            and
            [`knowledge/strategy/the-depth-the-room-asks-for.md`](../../knowledge/strategy/the-depth-the-room-asks-for.md)
            (the latter SPLIT out rather than grown onto the s115 page), + hub; updates to
            `the-exit-bearing-buys-the-arrival.md` and `the-separation-is-not-a-suffix.md`. Library:
            **`beam_io.attribute_parents`** (this session's method, made executable) + its gate.
            - **OPTION 1 IS DEAD AND THE DUMPS ALWAYS SAID SO** (`_notes/s123_c2_preflight.py map`,
              seconds, no cut). Attributing all 226 banked cycle-3 terminals to their cycle-2 parents
              by input-log PREFIX: the population spans along **827.99-984.25** with **6 terminals
              SHORT of the 876 target**. The "918-971" that motivated the re-cut is the branch off c2
              nodes 8/9 -- **34 of 63**, not the population. And cycle 2 already exits where it would
              have to: nodes 0/1 at along **579.19** deliver terminals at **877.88 / 886.82**, on the
              target, while the earliest exit (569.82) UNDERSHOOTS to 827.99. The ask "hand off 40-90 u
              earlier" pointed the wrong way.
            - **BECAUSE THE ALONG IS A TRADE AND THE ARRIVAL IS THE HALF THAT LOSES.** The near-target
              band's best deliverer is **106.66** -- `total` **99**, two frames UNDER the banked plan,
              plus **7.66** frames of arrival -- against the winner's 105.00 (`total` 105, arrival
              zero, an 11-frame atom putting Link 29.2 u from a station).
            - **AND THE BILL IS THE ROOM, NOT THE SEARCH.** All **268** stations lie in ONE cluster at
              along **804.70-818.69** while the 116 rows run **879.92-979.86**: every row is
              **72.3-162.6 u down-line of its own stations** (median 110.6), so delivering needs
              **61.2-175.2 u** of separation. Over both banked beams (`_notes/s123_sep_vs_arrival.py`)
              ``sep`` is the strongest predictor of the bill -- corr(``sep``, `d_station`) **-0.697**
              (require) / **-0.819** (pair), against `n_atom`'s -0.489 / -0.603 -- every free-arrival
              terminal is one of the deepest, and the beam tops out at **59.4 u**.
            - **THE HERD CANNOT BUY THE DEPTH EITHER, WHICH CLOSES s115's OPEN HALF**
              (`_notes/s123_deep_census.py`, 154 s, dump `s123_deep_census.json`). The 7 herd-produced
              deep terminals (``sep`` 62.4-75.3) fire **0 of 672** each; the 3 deepest FIRING controls
              fire **226-329**. **6 of 7 have NO sole clause** (`l_ok` + `dips` refuse together, so no
              single fix revives a variant); the 7th is one camera fix from firing all 672 and lands
              **52 u short** of the nearest row. Tightest reading: at the SAME endpoint along, ``sep``
              59.4 fires 329/672 and ``sep`` 62.4 fires **0** with `l_ok` SOLE.
            - **OPTION 2 PRICED WHOLE: THE ARC IS WORTH ONE FRAME, A FOURTH TIME**
              (`_notes/s123_arc_at_require.py`, 2464 s at 5 procs, dump `s123_arc_require.json`, read
              by `_notes/s123_read_arc.py`). At the requirement lane's **50 firing** terminals, with
              the pair lane re-priced in the same call and asserted against the banked dump --
              **control 50 of 50** -- in-band **6 -> 10**, joint **1 -> 2**, deliverers **4 -> 7**,
              best bound 93.95 unchanged, best DELIVERED **105.00 -> 104.00** at the same endpoint.
              Next best are 105.75 / 106.13 / 111.52, far behind.
            - **AND THE ARC'S WINDOW IS NOT BINDING** -- s112's standing prescription, run at last.
              All 7 deliverers' winning `exit_bearing` sits **-22.50 to +11.25 deg** off its nearest
              centre against a **+-67.5 deg** half-window: **0 of 7 at the edge**. Widening is not an
              unpriced lever, which is `the-short-atom-is-a-point` read from the other side.
            - **SO THE BANKED 101 STANDS, by 3 frames**, and the remaining gap is not in the cut, the
              cut's shape, the handoff along, the arc, or the separation.
            - **AND THEN DERECK RE-AIMED THE WHOLE PROBLEM (end of s123, in conversation). Read this
              box's numbers as CORRECT ARITHMETIC ON A SUPERSEDED FORMULATION.** Everything above --
              the arrival bill, the station cluster, the 61.2-175.2 u separation ask, the 230 u follow
              limit, the five `away_walk.fires` clauses -- exists ONLY because the plan walks AWAY from
              her and comes back. **Target zero walk-away frames: the herd's LAST ROLL *is* the clip
              roll.** Link never leaves her; the search becomes ONE condition on ONE frame (at the cut,
              is Link's overlap steering him through the seam), and the escape/arrival/station/roll-
              entry stages are deleted rather than optimised. Order (Dereck, "reduce variables"): solve
              the TERMINAL CONFIGURATION first -- which (Link, Tetra) geometry at the cut frame clips --
              and only then ask which herd arrives there. Open unknown: the clip wants ~**1.23 u** of
              overlap at the cut and a herd roll's depth is whatever the plow produces, so the terminal
              solve has to answer the razor first.
            - **THE SEARCH HAS BEEN RUNNING 34x SLOWER THAN THE ENGINE IT ALREADY HAS**
              (`_notes/s123_bench.py`, measured this hardware). `beam_io.rebuild_beam` -> `seeds.
              make_freerun`, which wires camera + Tetra look/eye + neck and runs the pose FK in Python:
              **2,915 coupled steps/s (343 us), 74 roll rollouts/s**. `seeds.make_freerun_native`
              (`LandCore.step_courtyard`, `native_push=1`, the STRIPPED config) measures **99,523
              steps/s (10.0 us) and 2,583 roll rollouts/s** -- and is already gated 0-ULP against the
              Python path (`tests/test_freerun_native.py`). So a 100k-aim sweep is **~39 s
              single-threaded**, not 21 minutes, and s123's own 2464 s arc sweep was ~70 s of work.
              **Every wall-clock figure in the boxes above is inflated ~35x**; the arithmetic stands,
              but "too expensive to sweep" was never true. Not a one-line fix: the native config has no
              camera, so any predicate reading `csangle`/`l_ok`/`target_cs` needs care, and the CUT is
              Python-only (no cut in `_anmc.pyx`) -- so the split is the module's usual one, **native
              for the mass sweep, Python for the exact clip confirm**.
      - [x] **THE CAMERA'S SHAPE IS MEASURED AND IT DOES NOT MOVE THE ANSWER EITHER: A 100%-FIRING
            BEAM LANDS THE SAME 105.00 (session 122).** The last lever s121 named -- the last cycle's
            ``l_ok`` keep is a SHARE, so it cannot stop admitting the 53 of 99 endpoints where the
            clause refuses every variant -- is now an A/B. New truth page
            [`knowledge/strategy/the-shape-of-a-cut-is-not-its-answer.md`](../../knowledge/strategy/the-shape-of-a-cut-is-not-its-answer.md),
            one MIGRATION to
            [`knowledge/history/the-cone-keep-was-a-share-because-a-filter-throws-away-firing-states.md`](../../knowledge/history/the-cone-keep-was-a-share-because-a-filter-throws-away-firing-states.md)
            + hub. Library: `roll_candidates` gains ``tcs_require`` and `extend_cycle` ``lok_require``,
            both additive and DEFAULT-OFF.
            - **PRE-FLIGHT FIRST, AND IT WAS BINDING** (`_notes/s122_shape_preflight.py`, 41 s + 62 s
              -- the s120 lesson, check a cut is binding before building the fix). Re-running R2 whole
              at the cells behind the banked beam (pre-roll endpoint from `beam_io.split_last_roll`),
              over the 165-survivor population's **33 R2 cells**: the share spends **54 of its 99
              slots** on states that can never fire; the requirement returns **63, all firing**, 25 of
              them targets the share never kept. It empties 8 cells and loses **ZERO junction nodes**
              -- every emptied cell sits at a pre-roll node that keeps live cells on another aim.
              The emulation is self-checked to reproduce the banked keep at **33 of 33** (its first
              version did not: `junction_quality` is still COMPUTED on the last cycle, and a scored
              target sorts `(-inbox, lat)` ahead of every unscored one).
            - **AND THE s73 CALIBRATION NEVER APPLIED TO THIS PREDICATE.** "A camera filter throws
              away 96% of firing states" was measured on the SNAP BILL; `lok_clear` has no false
              positives (s117: 107/107 and 118/118; s121: 45 of 46 vs 0 of 53), so what it drops fires
              nothing. That argument is MIGRATED; the share still ships, for a measured reason.
            - **THE RE-CUT DELIVERS EVERY STRUCTURAL PROMISE AND NOT ONE FRAME**
              (`_notes/s122_recut_c3.py`, the s119 PAIR lane with one knob, **3160 s** vs 3936 s; dumps
              `s122_c3_require_{beam,landing}.json`, log `s122b_require.log`, read by
              `_notes/s122_read_shape.py`). Terminals clearing `l_ok` **33 of 64 -> 63 of 63**; probed
              endpoints that FIRE **27 of 47 -> 50 of 50**; in-band **2 -> 6** (spread 877.9 x2 /
              886.8 / 934.3 / 936.6 / 947.4 against 877.9 / 934.3); deliverers **1 -> 4**; **34
              endpoints the share never reached**; **0 disagreements** at the 23 shared. Best bound
              93.95 unchanged and best DELIVERED **105.00 at the SAME endpoint**. The three new
              deliverers are 106.66 / 115.82 / 117.85.
            - **SO 105.00 IS NOW RETURNED BY THREE CUTS THAT DO NOT SHARE A POPULATION** -- the capped
              slice (58% of survivors), the uncapped census (all 165), and a requirement-shaped cut
              reaching 34 endpoints neither contained. That is evidence about the ENDPOINT SET, not
              about the cut.
            - **BOTH SIDES OF THE A/B PROVED, NOT ARGUED.** The knob was in force (a prediction made
              BEFORE the run: 63 of 63 terminals clear), and the CONTROL is still the control -- the
              pre-edit `roll_candidates` loaded out of git returns **0-ULP identical keeps** on 6 real
              pre-roll nodes (`_notes/s122_inert_check.py`), so the banked lane needed no re-run.
      - [x] **THE UNCAPPED CENSUS IS IN, AND IT IS BRANCH 2: THE CAP WAS NEVER BINDING ON THE ANSWER
            (session 121).** s120's `_notes/s120_uncapped_c3.py` finished in **4309 s** (dumps
            `s120_c3_uncapped_{beam,landing}.json`, log `s120c_uncapped.log`): the s119 PAIR lane with
            ``cap=None`` and ``beam=165``, so every survivor was enumerated rather than the cheapest
            96. Read with `_notes/s121_read_census.py`.
            - **165 roll survivors, all enumerated, 99 after dedup in the dump; 81 fire; 3 land
              in-band and 1 pays both halves. Best DELIVERED over the WHOLE population: 105.00 at
              node 13 -- the SAME endpoint and the SAME figure as the capped slice.** Best bound
              93.95, unchanged. So the standing answer is not a property of 58% of the population:
              **the remaining frames are not in cycle 3's endpoint set at all.**
            - **THE CAP DID HIDE RECORDS, AND THEY ARE WORSE.** 12 of the 46 firing endpoints in the
              dump and **1 of the 2 deliverers** were never reported by the capped control -- and the
              hidden deliverer is node 23 at **117.85**, 12.85 frames off the standing best. (The arc
              was measured to move a delivered figure by ~1 frame, so it cannot close that.)
              **Existence is not the branch test -- improvement is**: the first version of the reader
              printed BRANCH 1 off the mere presence of a new deliverer and was corrected.
            - **AND IT REPRODUCES ITS CONTROL EXACTLY**: 47 endpoints probed in both lanes, **0
              disagree** across `fires`/`bound`/`miss`/`total`/`n_atom`/`row_idx`/`knobs`/
              `d_station`/`arr_frames`/`in_band`/`joint`. The s120 handoff's reproducibility check is
              discharged.
            - **A NODE'S GEOMETRY IS NOT AN IDENTITY EITHER** (the reader's own foundation). Session
              119 retired the node INDEX as an identity and prescribed geometry; that is necessary
              and not sufficient -- **7 of 64 beam slots are geometry twins** carrying a BIT-identical
              Tetra endpoint, Link offset and centre-feet (delta exactly 0.0 at full repr) with the
              same knobs, row and total, and DIFFERENT bounds, because ``offset`` records Link's
              LATERAL alone and two routes reach one Tetra endpoint with Link at different alongs.
              The dumped input ``log`` is exact: 64 of 64 unique in both lanes, and all 64 shared
              between them. Keyed on it the reader reports 0 disagreements pair-vs-pair and 27
              arc-vs-pair, every one of them in ``exit_bearing`` -- the arc's own knob.
      - [~] **THE DIP BUDGET IS NOT THE LEVER, AND THE CAP RECORDS A SKIPPED ENDPOINT AS A REFUSED
            ONE (session 121).** One new truth page,
            [`knowledge/strategy/the-dip-budget-is-not-the-lever.md`](../../knowledge/strategy/the-dip-budget-is-not-the-lever.md),
            one migration to
            [`knowledge/history/dips-refuses-the-other-half.md`](../../knowledge/history/dips-refuses-the-other-half.md)
            + hub. No library behaviour changed -- one `full_herd.lok_probe_key` docstring corrected
            where it carried the retired claim.
            - **``dips``, THE LAST UNMEASURED CLAUSE, IS MEASURED AND IT IS NOT AN AXIS**
              (`_notes/s121_dips_census.py`, 347 s at 5 procs over **402661** variants at all **99**
              endpoints of the UNCAPPED census -- the whole population, re-run there after the
              64-node beam because a finding about a slice is what this session disproved; dump
              `s121_dips_census_uncapped.json`, log `s121_dips_uncapped.log`). Relaxing `DIP_BUDGET`
              3 -> 14 (14 IS the largest dip count observed) admits **+39667** variants (+38.7%) and
              revives **0** of the **53** endpoints that fire nothing. Every dip-only refusal already
              sits at an endpoint that fires -- ``sole['dips']`` is 39667 across the population and
              **0** at every dead one. Priced at HELD PUSH (the most
              ``resid_along`` reachable at each ``freeze_f``; frames alone reads "free" because a
              short atom separates early only because it pushed less), the bar is worth at most
              **1.04 frames** anywhere (0.60 at the endpoint that delivers 105.00). **The beam slice said
              0.78 and "cannot buy a whole frame" -- false on the population by a node the beam does
              not contain.**
            - **WHAT REFUSES THE DEAD HALF IS THE CAMERA.** At those 30, `l_ok` fails on **all
              200038** variants and is SOLE on **55754**; ``dips`` fails on 143805 and is sole on
              0. `lok_clear` run at all 99 arrivals splits the population **45 of 46** firing against
              **0 of 53** dead -- 1 false negative, 0 false positives. Five dead endpoints are within
              10 deg of clearing; nodes 81/92 miss by **1.72 / 1.74 deg**.
              This retires one of session 116's two reasons for making the camera a share and not a
              requirement (the other -- a filter throws away firing states -- stands).
            - **THE CAP'S DUMP CANNOT TELL "NOT MEASURED" FROM "REFUSED"** and 7 of 17 skipped beam
              slots really fire. The keep is capped at the cheapest 96 by admissible bound and records
              every skipped survivor as ``fires=False`` with ``bound`` inf beside ``unprobed=True``.
              Probing all 64 (this session's predicate agrees with the enumeration on **47 of 47** it
              can check) finds **7 of the 17** hold 1410-3263 firing variants each. Priced with the
              pair lane's OWN keep (`_notes/s121_price_hidden.py`, control node 13 reproduces its
              dumped record exactly): all 7 fire, **none delivers**, and their enumerated bounds
              **107.79 .. 113.36** are the worst in the beam. So on this beam the cap hid real
              endpoints and no deliverable one -- the screen ranked them expensive and was right.
            - **AND THE `fires`-FIRST SCREEN IS A DEAD IDEA, MEASURED**: `cloud_landing`
              short-circuits right after `atom_cloud`, but `atom_cloud` IS the cost (~15 s a node
              against the whole keep's ~15 s), so screening on `fires` before pricing saves nothing.
            - **TRAP -- NEVER EDIT A SOURCE FILE WHILE A GATE RUN IS IN FLIGHT.** Many gates here
              assert on source TEXT (`inspect.getsource`), which resolves `co_firstlineno` against the
              file on disk at call time. A docstring edit to `full_herd.py` mid-run shifted every line
              below it and `getsource(extend_cycle)` returned one unrelated line, failing 4
              `test_cloud_land.py` gates that read as a real regression. Re-run on the settled file:
              49 passed.
      - [~] **THE REDUCTION IS FIXED AND IT IS NOT THE BINDING ERROR: THE PREDICTOR IS NOT A BOUND,
            AND 69 OF 165 SURVIVORS HAVE NEVER BEEN ENUMERATED (session 120).** Two new truth pages,
            [`knowledge/strategy/minimise-subject-to-the-predicate.md`](../../knowledge/strategy/minimise-subject-to-the-predicate.md)
            (the banded reduction and what it is worth) and
            [`knowledge/strategy/the-fan-is-not-a-bound.md`](../../knowledge/strategy/the-fan-is-not-a-bound.md)
            (why it does not fix the rank) + hub x2. Library change in `cloud_land` + `full_herd`,
            all additive; `predict_bound` gains four reductions and one refusal.
            - **THE SESSION-119 CROSS-CHECK IS DISCHARGED: NO DISAGREEMENT.** The in-process ``arc``
              lane finished (16781 s) and reproduces the parallel probe exactly -- 27/64 fire, bound
              93.95, in-band **2 -> 6**, joint **1 -> 2**, best DELIVERED **105.00 -> 104.00** at miss
              0.474 u. The apparent "node 13 vs node 14" is a LABEL, not a result: the two lanes'
              beams are identical except an **exact swap of slots 13/14**, and the winner is the same
              endpoint (herd 73, along 934.264, lat -10.204, offset +9.632) in both, one frame
              cheaper under the arc (`n_atom` 11 -> 10, `exit_run` 3 -> 2). A node index is a rank
              position; compare endpoints across lanes by their geometry.
            - **THE KEEP SHARE (step 1 of the s119 next step) IS BUILT AND CANNOT BITE.**
              `extend_cycle`'s ``delivered_keep`` ranks a share of the beam on `cloud_land.delivered`
              (``total + arr_frames`` over a SETTLED ``in_band``/``joint`` record) instead of on
              ``best``, which is short-atom at 64 of 64. One line of the s119 arc log settles its
              value, for free: over all **165** survivors the enumeration found **6 in-band and 2
              joint**, and the beam it produced holds **exactly those 6 and those 2**. Every
              deliverable survivor already reaches the beam, so no share of it can add one. Shipped
              off by default and gated.
            - **THE SCREEN'S REDUCTION (step 2) IS BUILT, EXACT, 22x CHEAPER -- AND STILL DOES NOT
              RANK** (`_notes/s120_screen_{keys,rank}.py`, all 64 nodes of the s119 arc beam against
              that run's own enumerated records; dumps `s120_screen_{keys,rank}.json`).
              `predict_bound` now takes ``atom_min`` / ``by_atom`` (the minimum per atom LENGTH) and
              ``band`` / ``owes_nothing`` (minimise subject to the predicate the keep applies, the
              second a refusal without stations). The two fix different halves: at the beam's
              best-delivering endpoint (true delivered **104.00**) the standing global minimum reads
              100.93 (**-3.07**) where ``k>=10`` reads **104.05** (+0.05), while the banded key is
              what makes the arc visible at all -- **-1.443 .. 0 over 33 of 64 ranks** (joint-banded
              -7.028), against the global key's `+0.000 at 64 of 64`. It costs **128-147 ms** a call
              against the global key's **3189 ms**, because a band bounds a distance and therefore
              indexes: `_band_index` buckets the rows and each member reads 9 cells, not 116 rows
              (gated as an identity against the brute-force scan, boundary rows included).
            - **BUT THE RANK IT PRODUCES IS STILL WRONG, AND THE REASON IS THE FAN.** The four
              endpoints with settled records deliver 104.00 / 106.13 / 106.14 / 111.52; the standing
              screen ranks them **27 / 16 / 17 / 15** of 64 -- the worst deliverer highest, the best
              lowest -- and the banded reductions move the best one only to 21st / 23rd. Measured
              against the enumeration at the 27 firing endpoints, `predict_bound`'s error spans
              **-0.93 .. +5.11 frames** (mean +1.74) and is **negative at 4 of 27**: the "optimistic
              by construction" proxy is **not a bound**, and **3 of those 4 are deliverable
              endpoints**, so it is pessimistic exactly where it matters. It is not the documented
              -0.53 u/u offset dependence either -- Spearman(error, offset) **-0.135** (vs `t_lat`
              +0.418, enumerated miss +0.388), so no one-parameter shift repairs it.
            - **SO THE LEVER IS THE CAP, NOT THE RANK.** The same logs say **69 of 165 survivors were
              never enumerated** (the keep is capped by wall clock at the cheapest 96 by admissible
              bound), so in-band 6 and delivered 104.00 are properties of **58%** of the population
              and the only measure that makes claims has never seen the rest. Running now
              (`_notes/s120_uncapped_c3.py`, log `_notes/s120c_uncapped.log`): the s119 PAIR lane
              verbatim with ``cap=None`` and ``beam=165``, so every survivor is enumerated AND
              dumped -- which also makes any future keep share priceable OFFLINE against that dump
              instead of costing another cut.
            - **Gates**: `tests/test_cloud_land.py` +7 (the cheapest atom hides a late knob;
              ``by_atom`` is the same minimum per length; ``atom_min`` admits exactly what it says;
              the banded reduction is the keep's predicate; the band index is exact; `delivered`
              reads both records and refuses an unsettled one; the share is wired and off by
              default). **128 passed, 6 deselected (10:37)** against s119's 121. Log
              `_notes/s120_gates.log`. No land-layer source changed, so the land goldens are
              untouched.
      - [~] **THE ARC IS PLUMBED INTO THE CUT, AND THE CUT STRUCTURALLY CANNOT SEE IT: THE SCREEN'S
            MINIMUM IS PINNED TO THE CHEAPEST ATOM AT 64 OF 64 ENDPOINTS (session 119).** Two new truth
            pages,
            [`knowledge/strategy/the-fan-outlived-its-columns.md`](../../knowledge/strategy/the-fan-outlived-its-columns.md)
            (the plumbing + the missing column) and
            [`knowledge/strategy/the-cheapest-atom-owns-the-screen.md`](../../knowledge/strategy/the-cheapest-atom-owns-the-screen.md)
            (the wall both fixes hit) + hub x2. Library change in `cloud_land` + `full_herd`, all
            additive except one refusal.
            - **THE ANSWER TO s118's QUESTION, AND IT IS A NEGATIVE WITH A PROOF**
              (`_notes/s119_screen_delta.py`, all 64 nodes of the s111 c3 beam, 3 lanes in one call;
              dump `s119_screen_delta.json`). ``zero`` reproduces the s115-s118 behaviour rather than
              remembering it. **pair -> arc: the predicted bound moves +0.000 at 64 of 64**, 0 rank
              changes, the identical member chosen -- from a table 10x larger that strictly CONTAINS
              the smaller one. Because `predict_bound` charges ``n_atom`` 1:1 in frames: **the minimum
              sits on an `n_atom` = 3 member at 64/64 in all three lanes**, the fan spans 3..24, and
              only **3** of its 75627 members are at 3. The two fans have IDENTICAL counts at n_atom
              3/4/5 (3/50/166) and diverge only from 6 up -- the exit stick is held at the END of the
              atom, so below that the bearing has not happened yet
              (`the-short-atom-is-a-point.md` measured the same boundary from the other side).
              **A knob that pays late is invisible to a measure that minimises a quantity it adds
              frames to**; the arc's frames live in the keep's ``joint``/delivered fields, never in
              ``bound``, which is exactly the shape of s118's numbers (bound 93.95 unchanged,
              delivered 106.45 -> 103.45 at tails 10-11).
            - **AND THE THROW FIX IS REAL BUT DOES NOT REACH THE OUTPUT**: bound **-0.480 .. +2.814**
              (mean +1.449), **53 of 64** endpoints change rank, **21 of 64** change the row the
              predictor quotes -- and the re-cut (`_notes/s119_recut_c3.py pair`, 3936 s) comes out
              **byte-identical to `s117_c3_landing.json` on all 64 nodes, every field, atom knobs
              included**. The predictor is one of four `_mixed_beam` orders and its share picked the
              same six endpoints. Report the delta at the SCORER, not only at the output, or a real
              correction reads as a no-op.
            - **THE PLUMBING, WHICH IS WHY SESSION 110's ARC HAD NEVER RUN IN AN ENUMERATION.** Only
              `atom_cloud` took ``exit_bearings``; `cloud_landing`, `cloud_probe` and `extend_cycle`
              above it had no parameter to pass, so eight sessions of results are the standing PAIR's
              and not a verdict on the arc. Now ``exit_step``/``exit_half`` on `cloud_landing` and
              `residual_fan`, ``cloud_exit_step``/``cloud_exit_half`` on `extend_cycle`, default None
              = the pair so every banked number is unchanged. It is an arc SPEC and not a bearing
              list because `exit_arc`'s centres are measured from each endpoint's OWN position
              (`cloud_land._arc`) -- one list hoisted to a beam sweeps a different axis at every
              endpoint and contains none of their controls.
            - **AND THE LARGER FIND UNDER IT: THE JOINT SCREEN HAS BEEN PRICING LINK'S ARRIVAL AT HIS
              ROLL TERMINAL SINCE SESSION 115.** `predict_bound` read the throw as
              ``m.get('throw_along', 0.0)``, and the fan every joint cut was handed --
              `_generated/s106/s107_fan.json`, measured in s107, BEFORE `residual_fan` carried the
              throw -- has the column on **0 of its 178 members**. s118 measured what that costs
              without knowing it applied: terminal gap **67.6-106.7 u** against the same candidates'
              post-atom **159.5-176.3**, so the atom roughly DOUBLES the half the screen could not
              see. Now a **refusal** (unmeasured is not free, the module's oldest rule, applied to
              the fan). Re-running `_notes/s11{0,1,7}_*recut*` verbatim raises, by design.
            - **THE FAN, RE-MEASURED** (`_notes/s119_fan.py`, 6 firing endpoints of the s111 c3 beam,
              both lanes in one call, 257 s at 6 procs; dump `_generated/s106/s119_fan.json`):
              178 -> **7668** at the standing pair with the throw and tails 0-6 -> **75627** along the
              arc. An honest fan is ~425x the table the screen was reading, which at 116 rows is
              ~10 s an aim where the screen must cost milliseconds.
            - **AND THE PREDICTOR PRUNES ITSELF ONTO IT, EXACTLY** (`_notes/s119_fan_cut.py` priced the
              alternatives first): frame-dominance is exact and removes **2%**; an 8 u throw quantum
              costs 0.47 frames of resolution and buys 2.7x. What works is `predict_bound`'s own
              arithmetic -- a member's best conceivable bound is ``frames + n_atom + min(plan_cost)``,
              so once an incumbent beats that its whole row loop is skipped. Identical record,
              order-independent, **~10 s -> 26 ms an aim (~380x)**, so the cut can afford the full
              75627 at full resolution.
            - **AND WHAT THE ARC IS WORTH THROUGH THE OTHER MEASURE: ONE FRAME**
              (`_notes/s119_arc_at_beam.py`, the keep run at the beam's own **27 firing survivors**,
              both lanes in one call, 1420 s at 5 procs; dump `s119_arc_at_beam.json`). Legitimate at
              the banked beam precisely because the screen was measured not to move under the arc, so
              the survivor set is the same either way.

              | at the 27 firing survivors | standing pair | the arc |
              |---|---|---|
              | nodes holding an `in_band` record | 2 | **6** (nodes 3, 4, 6, 8 gained one) |
              | nodes holding a `joint` record | 1 | **2** |
              | best DELIVERED (settled) | 105.00 (node 13, tail 3) | **104.00** (node 13, tail 2) |
              | best ``bound`` | 93.95 | 93.95 (moved at 7 of 27, by <= 0.176) |

              The winner owes nothing on either half -- and its station gap is **33.4 u against a
              `FREE_REACH` of 34.0**, so it clears the arrival predicate by 0.6 u and still owes
              `entry_reach.hull_scan` at its own arrival. **The banked 101 STANDS**, now by 3 frames.
            - **STILL RUNNING**: the in-process ``arc`` lane of the re-cut (cap 96, ~13x the pair per
              survivor). It is a cross-check, not the measurement: it must reproduce the same 165
              survivors and the same 64-node beam, and the arc records above.
            - **Gates**: `tests/test_cloud_land.py` +7 (the arc reaches the keep and defaults to the
              pair; the arc is resolved per endpoint; the fan carries it into the screen; a throw-less
              fan is refused; the prune is an identity both ways; its floor comes from the rows the
              branch may quote; `extend_cycle`'s passthrough). **121 passed, 6 deselected (11:15)**
              against s118's 114. Log `_notes/s119_gates.log`.
      - [~] **THE ~165 u ARRIVAL IS A BEARING, NOT ONLY A GEOMETRY: THE EXIT ARC TAKES THE DELIVERED
            FIGURE 106.62 -> 103.45 AND GIVES THE BEAM ITS FIRST `joint` RECORDS (session 118).**
            New truth page
            [`knowledge/strategy/the-exit-bearing-buys-the-arrival.md`](../../knowledge/strategy/the-exit-bearing-buys-the-arrival.md)
            + hub; `delivery-is-two-predicates.md` / `the-screen-is-not-the-rank.md` /
            `the-arrival-is-payable.md` carry the corrected figures (nothing deprecated -- the s117
            table's `delivered 105.90` was arithmetic on an UNSETTLED record and is now 106.62).
            - **THE BILL IS REAL AND IT IS NOT THE STATION LIST** (`_notes/s118_arrival_scan.py`
              phases `control`/`scan`, dump `_generated/s106/s118_arrival_scan.json`). All 14 swept
              in-band states re-fired and re-enumerated, 19 distinct arrivals `entry_reach.hull_scan`ed
              at their OWN arrival and OWN landing over **45 aim cells x 3 thrusts**: **0 of 19 read
              ANY leverage**, against a positive control that LIT at **3 of 3** rows (the hunted tetra
              in the console hulls -- rows 0/26/107, live 2/1/15). So `arrival_frames` is not a
              fiction of the s104 hunted-station list; if anything it is optimistic.
            - **...AND NINE OF THE NINETEEN WERE NEVER DELIVERABLE AT ALL.** They fan an **EMPTY** walk
              cloud -- not settled at `WALK_CAP`, so `entry_fan.iter_fan2` keeps no junction and they
              reach nothing at any distance. **That includes the state behind s117's headline** (node 4,
              landing total 98.00, delivered 105.90). The other ten (node 3's family) are settled and
              fan **133 444-134 381** endpoints against the console's **139 213** -- a console-sized
              cloud with no leverage in it, which is a PLACE verdict and not a distance one. Honest
              s117 delivered best: **106.62**.
            - **WHAT THE GAP IS MADE OF -- THE HERD OWES HALF, THE ATOM SPENDS THE OTHER HALF.** At the
              roll TERMINAL the gap to the row's own station is **67.6-106.7 u (1.97-4.28 f)**; after
              the atom it is **159.5-176.3 u (7.38-8.37 f)**. The atom roughly DOUBLES it. Over all 551
              priced camera states the terminal gap runs **26.6-125.9 u**, and per roll it IS the bill:
              Spearman(terminal gap, arrival bill) **+0.858** over the 22 rolls that price a variant,
              while the landing is near-independent of it (**+0.189**) -- so the two halves are not one
              quantity with two names.
            - **AND THE TAIL RUNS THE WRONG WAY** (`trace`, out to the 230 u follow bar at the cheapest
              settled in-band state): ``d_station`` is **minimised at tail 0 (146.4 u)** and RISES to
              **227.2 u** by tail 20. The variant holds the live entry bearing at **85.8 deg** while the
              bearing from its own handoff to its own station is **27.7 deg** -- and the standing pair's
              OTHER member, the herd up-bearing, is **18.5 deg**. The grid held a nearly-right answer and
              the rank never picked it, because the rank prices the LANDING and the exit stick moves both.
            - **SO TURN THE AXIS** (`arc`, `cloud_land.exit_arc` step 0x800 half 0x3000 = 26 bearings,
              tails 0-12, 69k-101k variants a state, 546 s at 7 procs; dump `s118_arc.json`). The
              standing PAIR is re-priced inside the same call at the same tails, so the gain is the
              ARC's and not the tail's:

              | at the 14 in-band states | standing pair | the arc |
              |---|---|---|
              | smallest in-band station gap | 31.3 - 176.3 u | **9.9 - 162.1 u** |
              | best DELIVERED (`total + arr_frames`, settled) | 106.45 | **103.45** |
              | states holding a `joint` record | 1 (total 111.0) | **10 (total 104.0)** |

              Best delivered: node 3 ``off`` -3968, **total 103.0 + 0.45 = 103.45**, miss 0.492 u, tail
              10, row 30. Best `joint` (nothing owed on either half): node 3 ``off`` -3264, **total
              104.0**, miss 0.403 u, tail 11, gap 25.3 u. **This beam had produced no `joint` record
              before.**
            - **WHAT IT DOES NOT BUY: THE FLOOR ROLLS STILL CANNOT LAND HER** (`arc f0,f1`, dump
              `s118_arc_floor.json`). Node 0 (terminal gap **26.6 u**, arrival free, bound 93.95) and
              node 1 (**39.5 u**, bound 93.87) would deliver ~94 if either landed in band. Swept at
              their 4 + 3 cheapest camera states, 30k-59k firing variants each: **node 0 has zero
              in-band landings** with pair or arc, and node 1 has **3 at 2 states, arc only**, 134.9 u
              from a station -> delivered **111.93**. The arc does not cross the exchange.
              **The banked 101 STANDS**, and the remaining 2.45 frames are not in the atom.
            - **Gates**: `tests/test_cloud_land.py` +3 --
              `test_the_exit_arc_strictly_contains_the_standing_pair_the_grid_defaults_to`,
              `test_the_exit_arc_reaches_arrivals_the_standing_pair_cannot`,
              `test_a_longer_tail_can_move_the_arrival_FURTHER_from_the_station`. No library behaviour
              changed this session -- the arc and the tail were already built; what changed is that they
              were run.
      - [~] **THE CAMERA AXIS IS SWEPT AND CLOSED: THE FLOOR MOVES 0.08 FRAMES, THE SCREEN IS EXACT
            AND IS NOT THE RANK, AND THE WHOLE REMAINING BILL IS A ~165 u ARRIVAL (session 117).**
            New truth page
            [`knowledge/strategy/the-screen-is-not-the-rank.md`](../../knowledge/strategy/the-screen-is-not-the-rank.md);
            `the-camera-supplies-the-cone.md`'s "SAMPLE, not a sweep" section replaced with the swept
            verdict; the arrival constant added to `delivery-is-two-predicates.md`.
            - **THE WHOLE AXIS, PRICED** (`_notes/s117_camera_axis.py sweep`, **551 clearing states
              over the 23 supplied rolls, 1293 s at 8 processes**; dump
              `_generated/s106/s117_axis.json`). The unit of work is the FAMILY -- the 64 nodes are 26
              rolls, and `assert_families` PROVES the grouping (every member's pre-roll log and
              endpoint bit-identical) instead of inferring it from the key. Beam floor **93.95 ->
              93.87** (node 1's roll at ``off`` -3456, total 91.00): the camera moves it **0.08 f**.
              Within a roll the axis is worth **0.01-5.81 f** (median span 1.6), so it is a large lever
              locally and a nearly flat one globally -- the roll that already held the floor was
              already near its own camera optimum. s116's structural 2-per-roll sample was **0.89 f**
              off at that very roll (94.76 vs 93.87); its conclusion survived, but nothing in it said
              it would.
            - **THE SCREEN IS EXACT** (`sweep ... states=all` at the two bracket rolls, 225 states,
              `_generated/s106/s117_axis_all.json`): **107 of 107 clearing states fire and 118 of 118
              non-clearing states fire nothing** -- no false positive, no false negative. So
              `away_walk.lok_clear` is not a heuristic filter on this axis; on these rolls it IS the
              axis, and sweeping only the clearing subset at the other 21 rolls loses nothing.
            - **...AND IT IS NOT THE RANK, WHICH IS WHY BOTH PROBES STAY** (`keyeval`: each roll's
              swept optimum against what every key the cut can see would have kept at ``tcs_keep`` 3).
              `lok_probe_key` is binary, so over an all-clearing set it ties everything and its slot
              collapses onto `landing_key`'s order -- **10 of 23** rolls retain their optimum at mean
              **+0.53 f**, indistinguishable from `landing_key` alone (**9**, +0.53). The SHIPPED mix
              reaches **11**, +0.22. And the best VALUE key measured is **`camera_probe_key` -- the
              snap bill s116 showed was the wrong SCREEN** -- at **14 of 23**, mean **+0.14** (the
              arrival's own cone margin, 15 / +0.14, is the only thing better). A key can be the wrong
              screen and the right rank; the s116 retirement is evidence about the first only. Both
              docstrings now carry the calibration so neither share gets dropped on the other's
              argument.
            - **THE 512 STEP, PRICED INSTEAD OF ARGUED** (`grid`, enumerating the grid DIRECTLY and
              joining to the sweep BY DELIVERED STATE): bound loss median **+0.01**, mean +0.30, max
              **+3.00 f**, and **2 of 23 rolls hold no clearing grid member at all**. So
              `ESCAPE_TCS_STEP` 512 is right where it matters and has a real tail. **The offset filter
              is the trap** -- `snap_reach` dedupes by delivered state, so filtering its step-64 states
              by ``off % 512 == 0`` names 15-17 of the 31 states the grid really delivers; this session
              nearly published a resolution figure off it (now gated).
            - **AND THE LANDING IS SOLVED FOURTEEN WAYS WHILE THE ARRIVAL IS A CONSTANT.** `in_band`
              goes **1 -> 14 states over 3 rolls**, best landing total **98.00** (s116's was 102.00) --
              and every one of the 14 owes **7.38-8.37 arrival frames**, a **163-168 u** station gap,
              across 3 different rolls and 2 different rows. So the s109 exchange front is not
              something a lucky candidate slips through: solving the landing puts Link in the same
              place every time, because both halves are set by where the herd ended. Delivered best
              **105.90** (`total + arr_frames`), `joint` **still none**, **the banked 101 STANDS**.
            - **AND THE SAME ANSWER FROM THE OTHER DIRECTION -- THE A/B RE-CUT** (the handoff's second
              option: pricing a banked beam's cameras asks what the search could have CHOSEN, re-running
              the cut asks which endpoints EXIST). `_notes/s117_recut_c3.py` re-runs the s111 cycle-3
              cut verbatim -- same c2 nodes, same ``target_along`` 876, same beam/cloud caps -- with
              s116's keep as its ONLY difference (4059 s, `_generated/s106/s117_c3_{beam,landing}.json`).
              **45 of 64 endpoints shared** (19 out, 12 new), endpoints whose atom FIRES **21 -> 27
              (+29%)**, best bound **93.95 -> 93.95**, and the `joint` winner is **the same candidate
              bit-identical** (herd 73, along 934.2644, lat -10.2041, offset +9.6323, total 105 at
              0.474 u) at index 11 -> 13. The median firing bound gets WORSE (100.44 -> 101.89),
              because what a screen admits is endpoints that FIRE, not endpoints that are close.
            - **Gates**: `tests/test_away_walk.py` +2 --
              `test_the_screen_cannot_order_the_axis_it_lets_through` (the `l_ok` probe must TIE over a
              clearing set while the snap bill separates it) and
              `test_a_coarse_camera_grid_must_be_swept_directly_not_filtered_from_a_fine_one` (the join
              trap), sharing one `lok_reach_s116` fixture. **111 passed, 6 deselected (11:13)** over
              `test_{full_herd,away_walk,cloud_land,kb_links,kb_hygiene,code_hygiene}.py`, against
              s116's 109.
      - [~] **THE CAMERA CANNOT BUY THE SNAP, BUT `l_ok` NEVER NEEDED THE SNAP -- AND THE SUPPLY WAS
            ALREADY INSIDE THE SEARCH'S OWN GRID. 19 DEAD NODES COME BACK; THE FLOOR DOES NOT MOVE
            (session 116).** New truth page
            [`knowledge/strategy/the-camera-supplies-the-cone.md`](../../knowledge/strategy/the-camera-supplies-the-cone.md);
            forward link added to `knowledge/mechanics/ebs-turnaround.md` (its s77 numbers are about
            the SNAP and stand unchanged).
            - **THE SNAP AND THE CONE COME APART BY AN ORDER OF MAGNITUDE** (`_notes/s116_lok_supply.py
              reach`, `away_walk.snap_reach` at all 64 nodes = **26 distinct rolls**, 237 s). Over
              107-121 reachable camera states per roll the snap is reachable at **0-6** (s77's hole is
              real; 5 rolls have none) while the cone CLEARS at **0-68** (3 rolls have none), and
              **21 of 26** rolls hold a clearing target on the search's own `ESCAPE_TCS_STEP` **512**
              grid. So it was never a resolution problem and never a physics wall: the cut that picks
              the camera
              (`roll_candidates`' ``tcs_probe``) was ranked by `camera_probe_key` -- **the snap bill**,
              the one quantity s77 had just shown uncollectable.
            - **AND THE BEAM CONTAINS ITS OWN CONTROL.** Keyed by (pre-roll endpoint, aim, **L
              window**, entry csangle) the 64 nodes are 26 rolls and **12 hold BOTH a firing and a
              non-firing member** -- identical up to the last roll, same aim, same herd frames,
              differing only in ``target_cs`` (1[F] vs 16/17; 3,6[F] vs 52; 50,51[F] vs 53; ...).
            - **RE-FIRED AT A CLEARING TARGET, EVERY DEAD FAMILY PROBED COMES BACK: 0 of 672 -> 238-624**
              (`revive`, on the 512 grid, `fires_census` at the terminal the roll actually produces).
              Node 52 **0 -> 624/672** with ``l_ok`` gone from the census entirely; 16 **0 -> 301-329**;
              53 **0 -> 510-532**; 54 **0 -> 238-411**; 60 **0 -> 320**. Not confined to the 19: node 18
              (fires nothing, NO sole clause) reaches **298**, and node 14 (already firing 277) **644**.
              The herd cost does not move -- same frames, C-stick pointed elsewhere.
            - **AND IT DOES NOT MOVE THE FLOOR** (`price`, `cloud_landing` at atom cap 6, the s115
              convention). Best revived is node 16 at **94.76** against node 0's **93.95**, which
              reproduces bit-identically here. One `in_band` appears that s115 had nowhere (node 11,
              total **102.00**) -- still worse than the banked **101**. **This is a SAMPLE, not a
              sweep:** 2 clearing targets priced per roll out of up to 68, picked structurally (widest
              cone / smallest slew / median), so nothing here says 93.95 survives a real cut.
            - **THE RANK FIX, GATED.** New `away_walk.lok_clear` (the ``l_ok`` predicate as ONE shared
              definition -- the screen and the enumeration may not each spell it out) and
              `full_herd.lok_probe_key`, wired beside `camera_probe_key` on the last cycle;
              ``tcs_probe`` now takes a SEQUENCE, one keep share each, because neither order contains
              the other. **BINARY on purpose:** the L-frame margin predicts how many variants fire
              (monotone within a roll over 18 states) and NOT what they are worth -- node 16's widest
              margin bounds 94.78 against **94.76** for its narrowest -- so every clearing target ties
              and `landing_key` separates them.
            - **NEW BED + HARNESS.** `beam_io.split_last_roll` re-opens a banked terminal as its
              pre-roll endpoint + roll knobs, asserting the re-fire is byte-identical and 0-ULP;
              `snap_reach` states now carry the ``off`` that re-fires them (a census a caller can act
              on). Fixture `fixtures/courtyard_lok_s116.json` (3 families) exists because the s77 bed
              CANNOT express the finding: there nothing snaps AND nothing clears, so the two agree on
              every state. **+5 gates**, `tests/test_{away_walk,full_herd}.py`.
            - **AND THE s114/s115 8-NODE ENDPOINT SOLVE FINISHED** (128 solves, 3261 s, complete dump
              -- no ``partial``): **23 accepted, floor TOTAL 95.00** (node 0, rows 9/16, atom 6; node 8
              at 96.00). **No sub-95 exists in that bed.** Its required separations run **99.2-235.7 u**
              against the live band 41-85, which is exactly the term s115 measured cannot be delivered
              as a suffix -- so the hope that "a sub-95 would show up there" is retired.
      - [~] **THE SEPARATION IS NOT A SUFFIX -- IT IS THE SAME RESOURCE AS THE MOMENTUM AND THE
            FACING, AND `l_ok` IS THE MEASURED #1 BLOCKER ON THE BEAM (session 115).** New truth page
            [`knowledge/strategy/the-separation-is-not-a-suffix.md`](../../knowledge/strategy/the-separation-is-not-a-suffix.md);
            s114's frame price migrated to
            [`knowledge/history/separation-priced-at-the-endpoint-speed.md`](../../knowledge/history/separation-priced-at-the-endpoint-speed.md).
            - **THE SEPARATION MOVES AT A THIRD OF THE QUOTED RATE** (`_notes/s115_recede.py`, a
              16-bearing x 4-magnitude prologue grid x k = 0..8 at all 64 nodes). Best sustained
              **+8.3..+10.6 u/frame**, not the quoted 25.727: at the herd endpoint Link is still
              CLOSING (~+12 u/f along), so the cap belongs to a direction he is not travelling in.
              Depth itself is not the problem -- node 8 reaches sep **58.52 -> 129.88 u** in 8 frames,
              node 0 **58.48 -> 124.87**, and Tetra's own displacement stops at **k = 2-3** (measured,
              never inferred from `CO_RADII_BAR`, whose ``centre_feet`` oscillates with the pose).
            - **AND EVERY UNIT OF IT IS PAID OUT OF THE ATOM.** Enumerated at every deep pick at nodes
              0/1/8: **0 of 672 variants fire**, against the same endpoints' controls at **56/720,
              1888/2640, 1964/4038**. `away_walk.fires_census` attributes it -- ``l_ok`` fails on
              **672 of 672** and is the SOLE clause on all 672 at node 0's momentum-preserving pick.
            - **ONE RESOURCE, SPENT THREE WAYS (the mechanism, measured end to end).** Turning Link
              costs the EBS (speedF **-25.45 -> -11.43**); the turnaround -- the atom's only facing
              lever -- requires the EBS PRESERVED (`_SNAP_KEEP_SPEED` -24.5), and `snap_csangle` finds
              a window at **every control** (34816/34304/31232 at nodes 8/0/1) and **None at every
              receded endpoint**; so the atom's own first frame turns him in, cone margin **+3.51 ->
              -37.64 deg** (-71 by the L frame), and ``turnaround_first=True`` changes nothing
              (identical facing 25265 -- the ESS cannot snap without the speed). So the separation is
              **herd-shaped**: only the last roll can deliver depth AND leave the posture intact.
            - **THE BEAM PRICED BY ENUMERATION FOR THE FIRST TIME** (`s115_recede.py frontier`, 64
              nodes, 23 min): **29 fire**; the two floors are held by DISJOINT nodes -- arrival free at
              **2** (landings 25.40-40.02 u out), in-band landing at **3** (arrivals owe 7.38-8.37
              frames), **``joint`` 0**. Correlation only **-0.089**, so it is s113's bind on delivered
              endpoints, not a smooth trade. Best bound anywhere: node 0 **93.95** (total 92.00,
              landing 25.400, arrival free) -- a bound, not a delivery.
            - **`l_ok` IS THE BEAM'S #1 BLOCKER, NOT THE SEPARATION.** Over all 64 censuses it is the
              SOLE failing clause on **7349 variants (63%)** against ``dips`` 4117 (35%), and the sole
              blocker at **19 of the 35 nodes that fire nothing at all**. That is the s112 side-item,
              untouched for three sessions, now measured as the main one -- `away_walk.snap_reach` /
              `full_herd.derived_target_css` is where a camera supply is answered (s77).
            - **AND THE PER-AIM CUT WAS SCORING HALF A CANDIDATE -- FIXED.** `cloud_land.predict_bound`
              priced only the LANDING, so the screen that decides which endpoints exist never saw
              Link's arrival (the keep has priced it since s110, but only at the survivors). Fixed with
              s114's own finding: the THROW is rigid, so `residual_fan` carries it per member and the
              predictor places the arrival at ``link + throw`` and prices `arrival_frames` beside the
              miss; `roll_probe` gains ``stations``/``sep``, `extend_cycle` hands its map through.
              Measured by scoring ONE enumeration both ways (`_notes/s115_screen_ab.py`): the old key
              **understates its own pick by median +6.51 frames (max +9.23)**, the ROW moves at **9 of
              29** endpoints -- but the top-8 endpoint ranking is **identical** and the honest gain is
              **<= +0.28 frames**. So it removes a fiction and re-aims a third of the beam; it does not
              move this cut. Gates: `tests/test_cloud_land.py` (+6), 103 passed.
            - **A LONG-RUNNING SOLVE WAS LEFT RUNNING, AND ITS DUMP IS THE ONLY THING TO TRUST.**
              `_notes/s114_endpoint_solve.py 0,7,8,11,13,10,12,1 all 6` was relaunched detached at the
              end of this session (~150 s a solve, ~192 solves, ~8 h) and now writes
              `_generated/s106/s114_endpoint_solve.json` **after every solve** -- s114's run was stopped
              at 8 of them and lost all of it to a dump written only on completion. **Read that file,
              not a process:** ``partial: true`` with ``n_solves`` says how far it got, and the log is
              `_notes/s115c_endpoint_solve.log`. Do NOT test the pid it was launched under (5164) --
              Windows recycles pids, so a live pid is not evidence this job is the one running, and a
              dead one is not evidence it failed. It was at **60 solves** at handoff, best total 89.00
              (node 0, row 9) -- an arithmetic SPECIFICATION whose separation this session measured
              cannot be delivered as a suffix, so read it with that box above in hand.
      - [~] **THE BASIS WAS A DIMENSION SHORT: THE FOURTH COORDINATE (TETRA'S LATERAL) PAYS BOTH
            HALVES AT TOTAL 95.00, AND WHAT IS LEFT IS THE SEPARATION -- A PRICE, NOT A WALL
            (session 114; its frame price is retired above).** New truth page
            [`knowledge/strategy/the-endpoint-is-four-numbers.md`](../../knowledge/strategy/the-endpoint-is-four-numbers.md).
            - **THE THREE RELOCATION BEDS SPAN THREE OF FOUR COORDINATES.** A herd endpoint is Tetra's
              (along, lat) and Link's (along, lat); the OFFSET moves Link's lateral, the PLACEMENT both
              actors' along, the SEPARATION Link's along -- and **every one holds TETRA'S LATERAL at
              whatever the node was born with**. The priced rows span lat **-33.68..+1.61**, so the
              s113 negative ("no cell pays both, in none of 170 cells") was a statement about the
              SLICE. New fourth bed `tlat_shifted` + `placed` (absolute herd coordinates, all four
              beds composed), gated by `basis_check`: max off-diagonal leak **4.6e-05 u**.
            - **AND THE FOURTH COORDINATE PAYS BOTH HALVES** (`_notes/s114_endpoint_solve.py`, c3 node
              0, herd 69, row 9 at `plan_cost` 20). Endpoint Link (along **712.571**, lat **-25.976**)
              / Tetra (along **882.437**, lat **-13.587**): landing **0.0001 u** in the 1.0 u band,
              arrival **7.73 u** inside `FREE_REACH` 34 (so `arrival_frames` 0), 6-frame firing settled
              atom, confirmed over the full 690-variant grid -- **TOTAL 95.00** = herd 69 + 0
              relocation + atom 6 + cost 20. It needed **Tetra's lateral +6.10 u from native**. First
              endpoint in this work that pays both at once; a second solve from the n=6 class reaches
              the same total independently (arrival 11.9 u, separation 176.3).
            - **RIGIDITY MAKES BOTH ENDPOINTS ARITHMETIC** (`_notes/s114_throw_map.py`, the throw
              measured PER VARIANT at every node). `link_end = start + throw` -> **Link's start is
              ``station - throw``**; past `CO_RADII_BAR` the push is zero -> **Tetra's start is the
              row**. Nothing is searched. Totals as low as **93.00** by arithmetic alone.
            - **A FINITE-DIFFERENCE NEWTON STALLS AT ITERATE 0, AND THE FIX GENERALISES.**
              ``len(log) = handoff_f + exit_run`` and ``handoff_f`` is decided by `CO_RADII_BAR` and the
              recession test -- **both step functions in POSITION** -- so a relocated n=4 combo runs to
              n=6 and the difference quotient measures the jump. Two corrections: **re-select the best
              member of the grid each iterate** (the rigidity licenses it) instead of freezing a combo,
              and **iterate on the objective's ACCEPTANCE, not the equation** (the landing owes the
              band, the arrival owes only `FREE_REACH`; grinding Link onto the station is a tighter
              problem than the objective poses, and it is the tight part that stalls). Accepts at
              iterate 2 what grinding refuses at 6.
            - **WHAT IS LEFT IS THE SEPARATION, AND IT IS NOW PRICED (a fourth herd-price axis).**
              Over all **1160** specs at the **29 of 64** nodes holding a firing settled short atom the
              required separation runs **92.5..156.8 u**, while every beam node sits at
              **38.09..75.25 u** (mean 53.83) and **none reaches 100** -- a CUT observation, not a
              population law (the s107 lesson: the beam was ranked on `junction_quality`, never on
              separation). It decomposes as ``(row along - station along) + throw along - push along``:
              the first term is **fixed by the target set at 72.29..164.58 u over all 268 priced
              row-station pairs** (floor row 0 cost 21; row 9's cost-20 pair 0.8 u behind at 73.09), so
              **Link must end >= 72 u up-line because that is simply where the two target sets are**;
              the second is **positive at every node** (+55.01..+113.42 u over 66 (node, length)
              classes); the third gives back up to ~41 u.
              **NEW PRICE:** the separation's rate is Link's endpoint speed, cap **25.727 u/frame**
              (speedF spans -25.727..+18.500, every node in MOVE, so a +18.5 node is CLOSING and the
              rate belongs to the node). Against the beam's widest: the cheapest SPEC (node 8, row 9,
              atom 6, total 96.00) needs **92.5 u = 0.67 frames** -> ~**96.7**; node 0's SOLVED
              endpoint needs 169.87 u = **3.68 frames** -> ~**98.7**. The closest any spec comes to the
              live 41-85 u band is **7.5 u**. Both beat the banked 101.
            - **THE OVERSHOOT IS NOT A KNOB.** `turnaround_first` was the candidate for reversing the
              throw's along component and it ENLARGES it: node 0 **+54.82..+81.11 -> +74.43..+90.82**,
              node 13 +61.79..+92.76 -> +83.12..+99.68 (node 1's non-turnaround branch fires nothing --
              all 1059 fail `l_ok`). The conversion negates a ~25.7 u/f up-line backslide into
              down-line flight, so the displacement points AT Tetra by construction.
            - **AND THE POINT IS POSTURE-DEPENDENT.** s113's 1.1 x 1.1 u extent belongs to its two
              relocated cells; at the nodes' own postures the extent spans **0.00 x 0.03 u (node 55,
              atom 4, 22 variants)** to **14.87 x 47.77 u (node 6, atom 5, 202 variants)** -- 0.00..20.76
              along and 0.03..51.62 lateral over all 66 classes -- tracking how many variants survive
              `fires`. Read it at the endpoint in hand.
            - **PROVENANCE, since the total rests on it:** `_generated/s106/targets.json`'s rows are the
              **s104 placement HUNT's** hits, screened by `herd_price.contact_at_arrival` and priced by
              s105 -- NOT the original 288-coord `seeds.load_placements` set, from which row 9 is 59.15 u
              away. That has been the target set since s104 (where `plan_cost` 19-23 comes from);
              whether row 9 is among the 6-of-56 that session re-verified live is NOT established.
      - [~] **BOTH HALVES ARE SOLVED AT A 5-FRAME ATOM AND NEVER AT THE SAME ENDPOINT: THE SHORT
            ATOM'S ARRIVAL SET IS A *POINT* UNTIL FRAME 8 (session 113).** New truth page
            [`knowledge/strategy/the-short-atom-is-a-point.md`](../../knowledge/strategy/the-short-atom-is-a-point.md).
            - **THE ARRIVAL SET AT ATOM <= 7 IS A POINT** (`_notes/s113_arrival_front.py`, two
              endpoints 45 u apart, 768 / 752 firing+settled variants). Grouped by log length, the
              EXTENT of Link's end positions is **1.1 x 1.1 u at atom 5 over forty distinct knob
              combinations** (2.0 x 12.6 at the second endpoint), 4 x 4 at 6, ~9 x 6 at 7 -- and then
              **111 x 94 u at atom 8**, two to three orders of magnitude of area in one frame, at BOTH
              endpoints. Frame 8 is where the blob first contains the station cluster, which is
              exactly where `arrival_frames` first reads 0 and exactly the banked 97. Cause is
              `escape_atom`'s own recipe: 4-5 PRESCRIBED inputs, then frames that start on ~25.7 u/f
              of untarget-flip momentum one stick cannot turn.
            - **SO `exit_arc` IS WORTH EXACTLY ZERO AT A SHORT ATOM** (`_notes/s113_arrival_surface.py`,
              three cells at node 1). The standing pair against a 34-bearing +-90 deg arc: 1242 ->
              **21114** variants and 1248 -> **21216**, and the arrival floor (43.9 / 46.9) and the
              landing (0.685 u @ 73.3 / 1.160 u @ 63.5) are IDENTICAL TO THE LAST DIGIT. Seventeen
              times the rollouts for nothing. Positive control: s112 measured the same arc moving
              ``d_station`` 59.8 -> 17.6 at atom 12-15, so it is a LONG-atom knob, not a broken one.
            - **THE THROW IS RIGID AND POINTS OUT OF THE STATION BAND.** Link does not have to travel
              to the stations -- at node 1's 94/97 cell he stands at along **808.58**, INSIDE their own
              along band (804.7-818.7), with a gap that is essentially pure lateral. The 5-frame atom
              fixes the lateral (residual **+3.18**) and BREAKS the along, throwing him to 862.5,
              **43.8 u past** where he started. Displacement **(+53.9, +60.8)** and **(+60.1, +62.9)**
              at the two endpoints -- an 81-87 u throw at ~47 deg. The three tail frames from the 94 to
              the 97 are that EXCURSION, not a journey.
            - **THE THIRD RELOCATION AXIS EXISTS -- THE SEPARATION -- AND IT TAKES THE BOUND TO 96.00**
              (`_notes/s113_sep_curve.py`, new `sep_shifted`, 80 priced cells over d_along +50..+64 x
              d_sep -110..-15). Every bed until now moved Link LATERALLY or moved BOTH actors
              down-line, so the Link-Tetra separation was invariant by construction. `CO_RADII_BAR` 80
              is NOT the blocker -- `fires` only needs the separation to persist, so the atom still
              fires at ``centre_feet`` **160**, and past the bar Tetra takes no push at all, which
              makes the landing the herd's problem alone and drives it to **0.163 u from row 26**
              (cost 20). The axis takes the ARRIVAL floor 43.9 -> **2.6 u** and the best joint BOUND
              from s112's paid 97.00 to **96.00** (d_along +58 / d_sep -80: in band at total 95.12,
              ``d_station`` 48.9, owing 0.88 frames). It still does not PAY: ``near`` and ``near_band``
              never converge -- at every deep cell the arrival-optimal blob member lands 28-36 u out
              while the landing-optimal one arrives 45-49 u from a station, and the blob is small
              precisely because the atom is rigid.
            - **AND THE BIND IN ITS FINAL FORM: EACH HALF IS ALREADY SOLVED AT A 5-FRAME ATOM.** Over
              90 cells at node 1 the ARRIVAL floor is ``d_station`` **4.8 u** (inside `FREE_REACH` 34)
              at atom 5, total 94.00 -- its landing 35.9 u out; the LANDING floor is **0.685 u** in
              band, also atom 5, total 94.00 -- its arrival 58.2 u, owing 1.42 frames. **No cell pays
              both, in none of the 170 cells across all three axes.** The two floors sit 40 u apart
              down the line and the throw is rigid, so the endpoint that puts Link's point on the
              stations is the endpoint that leaves Tetra 40 u short of the rows.
            - **`plan_frames`=1 (cost 19) BUYS NOTHING UNTIL THE ARRIVAL IS SOLVED** -- s111 item 3,
              retired by arithmetic rather than a hunt. `FREE_REACH` is `WALK_CAP * WALK_FRAMES`,
              DERIVED from the budget the hunt ran at, so cost 19 credits 17 u instead of 34 and the
              bound moves by ``min(1, max(0, 34 - d_station)/17)``: a full frame only inside 17 u,
              **exactly zero** past 34. At the best in-band arrival anywhere (58.2) cost-19 and cost-20
              both score 21.424. Recorded in
              [`plan-cost-walk-budget.md`](../../knowledge/strategy/plan-cost-walk-budget.md).
      - [~] **THE LANDING HALF REACHES THE BAR AT 95, AND THE WHOLE REMAINING GAP IS TWO FRAMES OF
            ARRIVAL. THE OFFSET IS ONE VARIABLE SERVING TWO PREDICATES THAT WANT IT 22-25 u APART
            (session 112).** New truth page
            [`knowledge/strategy/the-offset-cannot-pay-both.md`](../../knowledge/strategy/the-offset-cannot-pay-both.md).
            - **THE s111 RE-CUT FINISHED AFTER ITS HANDOFF WAS WRITTEN AND IS A CLEAN NEGATIVE**
              (`_notes/s111g_recut_full.log`, 3360 s, 153 roll survivors -> 64 beamed, 57 of them
              NOT enumerated under the 96 cloud cap). Its frame-minimal nodes still carry offset
              **+13.9 / +16.1 / +17.5** (miss 25-40 u at totals 91-93) and its only both-halves node
              is node 11 (herd 73) at **total 105**. No <=95 candidate.
            - **BUT THE CUT IS NOT BLIND TO THE SPECIFICATION -- IT PRODUCES ON-LINE ENDPOINTS AND
              HALF OF THEM REFUSE, NOT BECAUSE THEY ARE ON-LINE** (`_notes/s112_nofire_probe.py`).
              The beam holds twelve on-line endpoints at herd 69-74 (offsets -6.04..+9.63); **four
              fire and eight do not**, and the split does not follow the offset -- node 7 (herd 70,
              offset **-0.54**) fires 1568 of 4654 variants at the standing pair and 17220 at a 90 deg
              arc, while node 32 at offset **-0.13**, 0.2 u away in along, fires **zero**. Positive
              control: the converting endpoints (7, and node 0 at 2828/26801) fail only `dips`, never
              `l_ok`. Among the refusers 36/32/33/40 fail every clause at once (**sole: none**) while
              43/45/35 have **108 / 173 / 97 variants one clause from firing** and that clause is
              `l_ok` -- the PREVIOUS roll's camera (s77). So the refusal is STATE-SPECIFIC, and the
              on-line endpoint the cut does admit fails for the ordinary reason instead: node 7 sits
              at lateral -48, 25 u below the cloud, and lands 18.9 u out at total 97.
            - **STRAIGHT AND SHORT ARE THE SAME KNOB** (`_notes/s112_offset_c3.py`, the s111 bed with
              the JOINT price added). At c3 node 0 the residual's lateral tracks the offset at the
              documented **-0.53 u/u** and the miss collapses 25.400 -> **2.016 u** from +17.49 to
              -7.51 -- while the atom's own log goes **3 -> 7** frames (6 at a wide arc). The atom ends
              when the actors SEPARATE, and an on-line Link keeps closing.
            - **THE STATIONS SIT ACROSS THE LINE.** All 116 rows' live stations lie at along
              **804.7-810.0, lat +12.1..+18.6**; the six cost-20 rows are 73-137 u down-line and 27-49 u
              across from their own. Over the 21 firing c3 nodes `arrival_frames` is <=1.03 only at
              offsets **-4.1..+17.5** and **0.00** only at **+13.9..+17.5** (d_station 23-39), against
              124-184 u at offset <=-33 and 66-144 at >=+30. The landing wants -7.5; the free arrival
              wants +14..+17.
            - **THE RELOCATION BED WAS CHARGING NOTHING FOR THE ALONG AXIS, worth up to 5 frames.** The
              search's along-per-herd-frame has a hard measured ceiling of **12.8177 u/f** (top six of
              64 nodes inside 0.006; 98.6% of `PUSH_CEILING`), so a relocation is free only while the
              endpoint is under it. Priced into `_notes/s112_honest_surface.py`; recorded in
              [`herd-price-of-a-placement.md`](../../knowledge/strategy/herd-price-of-a-placement.md).
            - **AND WITH IT PRICED, THE LANDING HALF HITS THE BAR** (`_notes/s112_atom_front.py`, c3
              node 4 relocated to offset +6.83, 40900 variants x an 18-bearing arc): a **SETTLED
              6-frame atom lands 0.083 u from row 74 (cost 20) at TOTAL 95** -- the first time any
              measurement has put the landing on the bar. It is not deliverable: Link is **99.9 u**
              from that row's station at frame 6, and the two tail frames that bring him to 25.2 cost
              exactly the two frames the plan does not have. The atom throws him OUT and the tail
              curves him back -- at the endpoint he was already ~32 u from the station, and
              `d_station` only returns under `FREE_REACH` at atom 8-12 (25.2 / 33.7 / 17.5 / 7.4).
              Swept over the whole (along, offset) surface at three frame-minimal postures (105-170
              cells each, herd priced) the split holds everywhere and the PAID FLOOR IS THE SAME
              NUMBER: node 1 (herd **68**) in-band **94.00** @ 0.685 u / paid **97.00** @ 0.685 u;
              node 4 in-band 95.00 @ 0.083 / paid 96.27 @ 0.477; node 0 in-band 96.00 @ 0.082 / paid
              97.00 @ 0.089. Node 1's pair is the SAME CELL (offset -13.06, along 868.0) differing
              only in the atom log, **5 against 8** -- three tail frames, and nothing else, is the
              whole distance from the bar to the floor.
            - **`exit_arc`'s +-45 deg default cannot face the stations from a DEEP straight-push
              endpoint** (Link lat ~-27: the station bears ~90 deg off both centres, and a tail swept
              at 0x2000 runs `d_station` 59.8 -> 73.9 -> 88.2 -> 103.1, first under 34 only at atom 15;
              at 0x4000 it reaches **17.6 at atom 12**). SCOPE IT BY LINK'S LATERAL: at node 4's
              shallower posture the winning bearing sits **9.8 deg** from its centre and widening buys
              nothing. The arc moves the LANDING floor 2.401 -> 2.047 u -- it is an arrival knob.
      - [~] **THE ESCAPE IS NOT A STEERING CHANNEL: THE LANDING BELONGS TO THE HERD ENDPOINT, AND
            SESSION 110's "ARRIVAL HALF IS SOLVED" WAS THRUST-13 LEVERAGE (session 111).**
            The session-110 handoff's default step was instrumental (put the arrival term in the
            per-aim cut). This session inverted it and went at the outcome -- Dereck's bar is the full
            ~6-frame saving, 101 -> <=95 -- by asking what an endpoint has to LOOK like. New truth
            page:
            [`knowledge/strategy/the-landing-belongs-to-the-endpoint.md`](../../knowledge/strategy/the-landing-belongs-to-the-endpoint.md);
            overturned claim migrated to
            [`knowledge/history/arrival-half-was-not-solved.md`](../../knowledge/history/arrival-half-was-not-solved.md).
            - **THE ATOM HAS NO AUTHORITY OVER THE LANDING** (`_notes/s111_atom_reach.py`, both
              bearing arcs at FULL circle -- 32 flips x 32 exits x 4 rotates x turnaround x side x
              tails 0-6, ~115k variants per endpoint). The reachable landing set is a blob fixed by
              the endpoint: node 2 (herd 68) tops out at along **862** where the row cloud starts at
              **880** -- herd 68 is out of REACH, not out of rank -- and node 4 (herd 69) spans lat
              **-30..-124**, 12-40 u below the cloud's lat floor at every along band it reaches.
            - **WHY: THE PLOW'S HALF-DEPTH EJECTION, POINTED BY LINK.** The first frame ejects her
              `(CO_RADII_BAR - centre_feet)/2` and each further closing frame adds more -- forced and
              input-independent. Measured floor vs the law: node 7 (`cf` 62.5) 9.02 against 8.74
              predicted; the ratio rises with the approach rate, ~1.0 at ``rec`` -8..-12 to
              **2.3-3.2** at -25 (38-48 u of forced push at the deep endpoints). Its DIRECTION is
              Link's lateral offset from her, which is why every frame-minimal miss is LATERAL: the
              row cloud's lat floor drifts -0.17 u per u of along, node 4 at offset **+17.5** pays
              ~20 u of lateral to reach the rows (= its 21.75 u miss), node 11 at **+3.9** lands 0.80.
            - **AND THE OFFSET IS CAUSAL, not a correlation across unlike endpoints**
              (`_notes/s111_offset_curve.py`): hold ONE real endpoint and move only LINK, laterally.
              The landing tracks it monotonically -- miss **36.7 / 30.7 / 25.4 / 15.9 / 7.0 /
              1.755 u** at offset +42.5 / +27.5 / **+17.5 (native)** / +7.5 / +2.5 / -7.5, with
              ``resid_lat`` collapsing -9.2 -> **-1.2**. At -7.5 node 4's push is straight (+46.5
              along, -1.2 lat) and lands her **1.755 u from row 26** (cost 20) at total 96. Nothing
              changed but where Link stood. It is a RELOCATION bed (anim/momentum do not follow
              position), so it is a causal probe and never a candidate -- the re-cut is what has to
              produce the endpoint.
            - **THE MAGNITUDE AXIS AND THE NO-CONVERSION DEPARTURE, both new, both closed**
              (`_notes/s111_{hold_atom,hold2}.py`, all 54 beam nodes). Every enumeration since s65
              pinned ``msd=1.0``; sweeping 0.0 (neutral) through 1.0 moves the forced push by
              **< 0.1 u** -- the ejection is instantaneous and depth-based, so a gentler stick buys no
              gentler plow. Holding one bearing from frame 1 (the console's own shape, Dereck's s110
              question) fires in **2-3 frames** against the recipe's 4, and fires where the recipe
              fires NOTHING (nodes 6 and 8 read 0 firing over the whole full-circle recipe grid). It
              is still not a plan: `entry_fan.iter_fan2` keeps an entry junction only at
              ``speedF == WALK_CAP`` and a departure that declines to convert **never settles inside
              16 frames** (shortest settled log 11-16 against the conversion's 4-6). That is what the
              L conversion is for.
            - **THE FRAME IDENTITY, CORRECTED.** `total = herd + atom + plan_frames + thrust + 4`;
              thrust 13 is refused so 14 is the floor; the recipe atom's shortest SETTLED log is
              **4** frames, not 6. So the frame-minimal beam nodes have floors 93 (node 4, herd 69)
              and 93-94 (nodes 2/5) -- the frames are there and only the landing is not.
            - **SESSION 110's LEVERAGE WAS ALL THRUST 13** (`_notes/s111_scan_landing.py`). `hull_scan`
              runs `entry_search.THRUSTS` = (13, 14, 15) and s109/s110 pooled the three. Split: **all
              173** leverage-carrying combos at the joint candidates are thrust **13**, and they read
              **0 leverage at 14 and 15**. The control passes and is what makes that mean something --
              the CONSOLE's own placement at its own 4-frame walk reads leverage 45/45/45 and
              walkable dust **0 / 9 / 18** by thrust, and hunted rows at the 2-frame budget read
              0/5/4 (row 9), 0/2/1 (row 16), 0/0/4 (row 0). So the joint candidates
              are barren at every thrust that can clip, the razor residual 3.3e-01 -> 3.1e-03 is a
              thrust-13 number, and session 109's verdict stands unchanged. The scan now splits by
              thrust and refuses to bank a thrust-13 hit.
            - **A HARNESS TRAP, MEASURED: the atom rolls out on a DETACHED camera.**
              `away_walk._clone_for_atom` detaches so ``csangle`` can be commanded; a wired replay of
              the same log drifts **121-654 BAM** and re-quantises every stick, moving the recipe
              atom's Tetra by **0.008-0.080 u** and Link by **0.75-2.00 u** against a razor band of
              ~1e-4. Quote a landing from the REPLAY. `_notes/s111_scan_landing.py` now takes the
              replay as truth and reports the delta; re-gating the s110 joint candidates that way
              changes nothing (still 0 live), so the detach is a trap for future numbers rather than
              the cause of that negative.
            - **THE SPECIFICATION A 95-FRAME PLAN IS**: exit a roll at **69-71 frames** (mid-roll
              truncation does not fire, s105), leaving Tetra where the endpoint's OWN forced push
              lands her inside the cloud, with Link **on-line** (`|Link lat - Tetra lat| ~ 0`) so that
              push is straight. The s107 beam contains no such endpoint -- its 68-69 frame nodes run
              12.19 u/frame at offset +14..+19, its on-line ones (node 10 at +1.78, node 11 at +3.91)
              are all at herd 73+ -- because the cut has never ranked the exit along and the offset
              together.
      - [~] **THE ARRIVAL WAS NEVER FIXED -- THE ATOM'S BREAK CONDITION WAS. THE TAIL BREAKS s109's
            HARD FRONT, AND IT COSTS EXACTLY WHAT IT BUYS (session 110).**
            The s109 handoff's joint keep is built, and building it named the reason the front looked
            hard: `escape_atom` stopped the frame it recedes at the cap AND separates, which is the
            right place to stop asking about the LANDING and silently answered the ARRIVAL with
            whatever the last frame held. **Every arrival in every enumeration this work has ever run
            was that one shape** -- Link beside her, deep, pointed down-herd, often still flying
            backwards on the untarget flip. New truth page:
            [`knowledge/strategy/the-arrival-is-payable.md`](../../knowledge/strategy/the-arrival-is-payable.md).
            - **THE TAIL** (`escape_atom`'s ``exit_run``, + `tail_variant`): hold the exit stick past
              the handoff and the frames are ordinary. Two gated laws make it exact -- while the
              separation holds her coordinate is **bit-identical (0 ULP)**, and the frame it stops
              holding `fires` refuses the variant, so the tail is bounded by the freeze and the 230 u
              follow bar, both already modelled. `tail_variant` reads every tail length off ONE
              rollout (gated bit-exact vs a fresh one), so the axis is nearly free: 672 rollouts
              become 4700 priced variants for +1 s.
            - **WHAT IT IS FOR IS NOT FRAMES.** `iter_fan2` keeps an entry junction only at
              ``speedF == WALK_CAP``, so an unsettled arrival fans an EMPTY cloud and reaches no
              station at any distance -- the banked ``shallow`` arrival hands off at **-23.217** and
              two tail frames settle it at 17.0. And since the station gap is priced at the walk cap,
              which is what a tail frame delivers, **the joint bound is TAIL-INVARIANT** (best bound at
              tail 0 == best over tails 0-6, 24 of 24 endpoints). That invariance is the sign the term
              is priced honestly; the tail buys DELIVERABILITY, not frames.
            - **THE JOINT KEEP** (`cloud_land`: `station_map` / `arrival_frames` / `_joint_row`, and
              ``joint`` = in-band AND owing no arrival frames AND settled). The row CHOICE moves under
              it: a row 6 u from the landing whose stations sit 130 u behind Link loses to one 20 u
              away the arrival already covers. Wired `extend_cycle(cloud_stations=, cloud_exit_runs=)`.
            - **THE RE-PRICED POPULATION** (`_notes/s110_joint_census.py`, 46877 firing variant/tail
              records at the 24 firing s107 survivors, 303 s): the front is an EXCHANGE, not a wall --
              a **settled, fully-paid arrival (station gap 30.5 u, ``arr_frames`` 0.00) at a landing
              miss of 1.881 u** (node 11, tail 2, total 104), where s109 had nothing within 126 u of
              paying both. 68 records land in-band, 0 of them pay the arrival, and the 4 settled
              in-band candidates scan **0 leverage** -- re-confirming s109's diagnosis with its own
              counter. The shape of the remaining gap: the herd 68-69 family (nodes 2/4/5) arrives
              already paid (``arr_frames`` 0.00-0.27) and lands **25-40 u short** at joint bound
              **93.95**, while every close landing owes 1.2-8.1 frames of walking.
            - **THE EXIT ARC WAS THE MISSING KNOB, AND IT PRODUCED THE FIRST JOINT CANDIDATES**
              (`cloud_land.exit_arc`, `_notes/s110_refine_arc.py`): the grid only ever held TWO exit
              bearings (the live entry bearing and the herd up-bearing), and the exit stick is held
              while the conversion frames are still plowing her, so it steers BOTH halves. An 18-wide
              arc at node 11 turned its best fully-paid landing **1.881 -> 0.8008 u** and produced
              **14 JOINT records** -- in band, arrival paid, settled. The predicate is SATISFIABLE.
              At node 40 the same sweep gives 0: its fully-paid family sits on a plateau at exactly
              2.5815 u (the landing is piecewise-constant in the atom's knobs) and its 0.15 u landings
              all arrive 176 u away, unsettled.
            - **AND THE SCAN SAYS THE ARRIVAL HALF IS SOLVED** (`_notes/s110_scan_arc.py`): **6 of 8
              JOINT candidates read LEVERAGE** -- 15-45 cell/thrust combos, up to **1760 grid hits**,
              razor residual down from session 109's **3.3e-01 to 3.1e-03** -- where EVERY s109 scan
              read `n_leverage == 0`. Leverage is monotone in the tail (0 combos at tail 3, 18-25 at
              4, 45 at 5). GOTCHA: ``arr_frames == 0`` is a RADIUS and the hull is a FAN -- two tail-3
              candidates at d_st 23.5-24.0 read 0 leverage while tail-4/5 ones at 19-33 read plenty.
              Direction, not distance.
            - **SO THE LANDING IS THE WHOLE REMAINING GAP, AND IT IS RAZOR-PRECISION, NOT BAND.**
              0.80 u from row 105 is what `objective.PLACEMENT_BAND` calls in-band and what the razor
              calls a different placement. Holding a leverage-carrying arrival fixed and sweeping HER
              placement about its landing (`_notes/s110_landing_radius.py`): 0 of 441 placements in
              ±2 u are live, and the deepest residual is **1.307e-05 with leverage 44 at the sweep's
              own CORNER** -- the curve is outside the window, so that 0 is the sweep's bound and not
              the physics. Next pass follows the gradient.
            - **THE LEVER IS STILL THE HERD ENDPOINT** -- both halves are set by it, the atom's
              landing is piecewise-constant in its own knobs, and a JOINT candidate costs **106-108**
              at node 11 against the banked 101 (the atom spends tail 4-5 retreating to the stations).
              A frame win needs a SHORTER herd whose atom lands genuine.
            - **AND THE CYCLE-3 ITERATION SAYS WHERE THE LEVER IS NOT** (`_notes/s110_rechain_c3.py`,
              2324 s, 96 probed / 54 beamed): re-iterated off `s107_rechain_c2_beam.json` with the
              joint keep, it **reproduces the same population bound for bound** (93.95 / 94.08 / 95.41
              / 102.53 / 102.96; its node 3 IS the old node 11 at 0.801 u @100). That is session 107's
              structural finding holding: an ENDPOINT keep reorders a set the upstream cuts fixed, and
              cannot create a joint-payable endpoint. It also reports "0 pay BOTH halves" at the very
              endpoint where the ARC found 14, since `extend_cycle`'s keep runs the standing two exit
              bearings -- so the arc, and the arrival term, belong in the per-aim CUT
              (`roll_probe`'s ``cloud_bound``), which is what decides which endpoints exist at all.
      - [~] **THE DELIVERY TIER KILLED THE s107 WINNER, AND THE FINDING IS THE PREDICATE ITSELF:
            DELIVERY IS TWO PREDICATES, AND THE POPULATION'S FRONT NEVER PAYS BOTH (session 109).**
            The s108 handoff's delivery chain ran and stopped at its first gate: the winner's own
            2-frame cloud (control: the console arrival's cloud reproduces s104's 139213 endpoints
            bit-for-bit) has **leverage 0 at every in-hull grid point, all cells** -- row 105's
            `plan_cost` 21 was PRICED at the console arrival, and this plan arrives elsewhere. The
            banked 101 stands; the offline 100 is a landing-half number only. New truth page:
            [`knowledge/strategy/delivery-is-two-predicates.md`](../../knowledge/strategy/delivery-is-two-predicates.md).
            - **THE DIAGNOSTIC SPLIT (one run, `_notes/s109_control_diag.py`):** control (hunt tetra
              + console hulls) = 4 live walkable stations, so the scan path is sound; winner landing
              + console hulls = **1 live** (the 0.789 u miss costs leverage 9 -> 4, not the dust);
              hunt tetra + winner hulls = **0 leverage**. The killer is LINK'S ARRIVAL: his atom
              ends him 128.2 u from the nearest hunted station (console: 25.0 u), and his ~20 u
              2-frame hull points down-herd. Leverage tracks the ARRIVAL; dust tracks the LANDING.
            - **THE CENSUS (all 8581 firing atom variants at all 24 firing re-chain survivors,
              `_notes/s109_arrival_census.py`):** the (landing miss, arrival d_station) front is a
              hard exchange -- **miss < 1 u only at d_station ~ 127 u (node 11); d_station < 10 u
              only at miss ~ 25 u (nodes 4/5, totals 97-99)**. No variant pays both, because both
              are set by where the HERD ends.
            - **THE SCANS (20 distinct near-arrival candidates, own cloud + all 45 cells x 3
              thrusts, `_notes/s109_scan_best.py`): 0 of 20 live.** Two failure shapes, both now
              legible: an arrival still mid-backslide fans an **EMPTY cloud** (`iter_fan2` keeps
              junctions only at ``speedF == cap``), and a settled arrival AT the stations with a
              landing 24-40 u off the band reads **leverage in all 135 combos, dust in none**.
            - **THE CONSOLE'S OWN SHAPE PAYS BOTH, and says how** (replayed): its herd ends with the
              flip already flying (f71 speedF -25.7), **Tetra coasts ~36 u on her own plow momentum
              through the atom window** while Link runs up-herd at the 17 u/f cap to 111 u behind
              her, 25 u from the station, walking AT the cap. The atom's exit-hold run and the entry
              walk are the same currency; after ``freeze_f`` extending the run moves the arrival and
              nothing else.
            - **NEXT: a JOINT last-cycle keep** -- price d_station beside the landing miss in the
              cloud keep (`cloud_land`), and iterate cycle 3 off `s107_rechain_c2_beam.json` letting
              the chain reach the console's geometry (disengage early, coast, spend the atom's tail
              running to the stations). The node-4/5 family (herd 68-69, arrivals already AT the
              stations, landings ~26 u short ~= 2 push frames) is the concrete probe: if +2 herd
              frames of that family exists in the c2 beam's reach, totals land ~99-100 with both
              halves paid. Do NOT re-price rows at foreign arrivals; the honest gate stays the
              per-candidate cloud + `hull_scan` (~30 s).
      - [~] **THE RE-CHAIN WITH A TARGET-AWARE CYCLE 2 LANDS INSIDE THE BAND: 0.789 u FROM ROW 105
            AT TOTAL 100 -- ONE FRAME UNDER THE BANKED 101, CONFIRMED REPLAY-FAITHFUL OFFLINE
            (session 108).** Both halves of the s107 handoff ran, in order, and the second one
            produced a candidate that beats the bank.
            - **THE FAN-CUT (the handoff's default step) CLOSED ITS OWN QUESTION: the last cycle was
              exhausted over the OLD beam.** `_notes/s107_fan_cut.py` (fixed first: it took the
              first 3 round-4 survivors as fan sources, which are escape-less -- the fan must be
              measured at the FIRING ones, nodes 7/18/25 per the landing dump's census; 178 members,
              along +14.7..+72.3 lat **-74.5..+4.7**, the band-local sign again). With the per-aim
              fan screen on: **6 of 30 survivors fire** (round 4: 3 of 30) and the floor DOES NOT
              MOVE -- **8.919 u @99, the identical endpoint round 4 found**. The proxy validated on
              its own band: `predict_bound` error -0.51..+1.25 f, **0.00 on the floor node**. So the
              population over `retarget2_beams` was the ceiling, exactly the handoff's first branch.
            - **THE RE-CHAIN (`_notes/s107_rechain.py`, 2578 s): cycle 2 made landing-aware --
              `extend_cycle(cloud_fan=)` in its per-aim cut + endpoint beam 16 (vs the 8 every round
              since s106 reused) -- then the fan-cut cycle 3 verbatim, then the enumeration at all
              54 survivors.** The richer cycle-2 entry set (16 nodes, corridor offsets down to 0.1)
              nearly doubled the cycle-3 population (54 vs 30), **19 of 54 fire** (vs 3/30 and
              6/30), and the front finally crossed the band: **node 11 (herd 73 f) lands 0.801 u
              from row 105 (`plan_cost` 21) with a 6-frame atom -> total 100**; node 40 has 2.58 u
              @100, node 23 4.54 u @99, and the s106/s107 5.93-8.92 floor endpoints reappear as a
              mid-pack. The lever was exactly where both s107 halves pointed: upstream, in the beam
              that decides which entry geometries cycle 3 ever sees.
            - **CONFIRMED from the raw log (`_notes/s107_confirm_winner.py`; the quotable number is
              the WIRED one): total 100 = 73 herd + 6 atom log + 21 plan_cost, landing 0.7886909226
              u from row 105, in-band.** The full 79-frame input log replays from state 2
              deterministic and bit-exact (`confirm_plan` ok: talk-safe, wall margin **+12.07 u** at
              f79, 3 rolls, regime held), and the atom's acceptance clauses re-measured on the WIRED
              continuous replay all hold (`l_ok` True, freeze_f 6, rec17_f 6, no dips, follow shell
              untripped). Winner package (full log + knobs + landing): `_generated/s106/
              s107_winner.json`; beams/landing dumps `s107_rechain_{c2_beam,beam,landing}.json`.
            - **A SCOPE CORRECTION ON `_clone_for_atom`, found by the confirm and now in its
              docstring: "Tetra is bit-identical under detachment" was the shipped plan's number,
              not a law.** This arrival's camera is still mid-chase (csangle 36254 -> 36375 over the
              atom), and wired-vs-detached moves TETRA's landing 0.026 u -- the size of a band edge
              (here favorable: 0.801 -> 0.789). Rank on the detached enumeration; QUOTE the wired
              replay. (The chase mechanism itself was already console-gated, s78.)
            - **NEXT: the delivery gap, per the s107 handoff's second branch** -- the 2-frame
              per-candidate cloud from THIS winner's arrival (`_notes/s105_arrival_cloud.py`
              pattern) -> `entry_search.confirm_entry` -> `cross_engine` -> the boot-movie splice
              (`[[tetrapush-dtm-delivery]]`), gating a console total <= 100 against the banked 101.
              Note row 105 is an s105-priced walk-budget row: its `plan_cost` 21 is a trajectory
              price, so the delivery confirm is what turns 100 from a priced claim into a console
              number. Do NOT re-pay: the endpoint-keep question (s107, closed negative), the
              cycle-3-alone iteration (four rounds, floor pinned), or a cached fan (band-local,
              both signs measured).
      - [~] **THE ~6 u FLOOR WAS NOT THE CUT'S -- REMOVING THE LANDING-BLIND KEEPS MADE IT WORSE, AND
            WHAT THAT KEEP WAS REALLY BUYING WAS ENDPOINTS THAT CAN ESCAPE AT ALL (session 107).**
            Round 4 ran to completion (2256 s): the un-kept cycle-3 stage produced 36 roll survivors, 30
            after dedup/beam, and the atom grid was enumerated at **every one of the 30**. Result: only
            **3 of 30 fire**, and the population floor at totals <= 101 is **8.919 u at total 99**
            (node 7, herd 75, a 3-frame atom onto row 111 at `plan_cost` 21) against session 106's
            kept-cut **5.933 u at 99 / 6.317 at 98**. The other two firing nodes are far worse (25.342 u
            @102 and 42.900 @104). So session 106's open question is CLOSED in the negative: the floor is
            not an artifact of the landing-blind cut, and dropping `escape_keep` did not reveal hidden
            landings -- it admitted endpoints that cannot end a plan.
            - **AND THE REFUSAL IS DIAGNOSED, not counted** (`away_walk.fires_census`, the s77 tool):
              on all four non-firing survivors sampled (nodes 0, 1, 5, 12) **`l_ok` refuses ALL 672
              variants** -- the L would act with Tetra in the front cone -- with ``dips`` down on most
              too and a sole-blocker count of 0 on three of the four. That is the same clause s77
              measured on the live bands, and `snap_reach` already showed the camera channel cannot buy
              it (0-1 of 110 states snap where the same csangles COMMANDED on a travel-frozen state snap
              9-10). So these 27 endpoints are structurally escape-less, not a knob away from firing.
            - **WHICH MEANS THE LAST CYCLE'S ENDPOINT POOL IS NOT THE LEVER**, and the structural half of
              this session says the same thing from the other side: `extend_cycle` cuts junction ->
              aim/camera -> ENDPOINT, and on the last cycle nothing follows the endpoint, so an endpoint
              keep -- however honestly it ranks -- reorders a survivor set the two upstream cuts already
              fixed. It names the least-bad survivor; it cannot create a better one. Both halves point
              upstream: the CYCLE-2 beam every round since s106 has iterated off (itself chosen
              target-blind), and the per-aim cut, which is what `cloud_fan` is for.
            - **THE FAN'S SIGN IS BAND-LOCAL, and this session measured both signs.** Validating the
              s107 driver's first stage against round 4's own dump: the residual fan at its two firing
              survivors spans lat **-74.5..-1.9** (along +14.7..+72.3, 110 members), where session 106
              measured **+13.8..+52** at ITS endpoints -- same herd line, same code, opposite sign. So
              s106's "the atom always pushes her lat-positive, so deliver her ~14 u lat-LOW of a row" is
              an instruction for that band and BACKWARDS for this one. It follows from the dependence
              `away_walk.probe` documents (the residual's lateral tracks Link's offset from her at
              **-0.53 u per u**), so which side of her a family of endpoints sits on flips the whole fan.
              The s106 page's claim is SCOPED, not retired -- it is right about its own band. Never cache
              a fan: `residual_fan` takes its endpoints as an argument for this reason.
            - The tool session 106 asked for is built and gated anyway, because it is the honest ranking
              of a final list and because running both measures on the same survivors is how this
              question gets answered on any future cycle. KB:
              [`knowledge/strategy/landing-keep-on-a-cloud.md`](../../knowledge/strategy/landing-keep-on-a-cloud.md);
              gate `tests/test_cloud_land.py` (17, 7 s). Scratch: `_notes/s106_retarget4.py` (the run),
              `_notes/s107_fan_cut.py` (the fan-cut, ready); `_generated/s106/retarget4_landing.json`.
            - **`cloud_land.py` -- the honest measure, at two prices.** `cloud_landing` enumerates the
              whole 672-variant atom grid at an endpoint (`atom_cloud` = `away_walk.probe`'s loop with
              the rank removed) and prices every firing variant as a WHOLE candidate: herd frames + the
              atom's own LOG length + the row's `plan_cost` + the remaining miss at `PUSH_CEILING`. The
              log not `freeze_f` (s105's off-by-three -- the bank is 101, not 98), and the row's own cost
              because the rows are 19-23 frames apart (s104), so 6 u from a cheap row beats 1 u from an
              expensive one. ~28 s an endpoint. `in_band` is reported SEPARATELY from the rank, since
              only it answers "solved".
            - **`residual_fan` + `predict_bound` -- the cheap half, and the axis with authority.** The
              residual is a FAN (s106: lateral never below +13.8 u), which is exactly why s106's
              `aim.handoff_rows` point-shift steered the rank toward badly-converting endpoints. So the
              predictor is a minimum over fan x rows in the SAME currency as the enumeration, at
              microseconds an aim -- affordable in `roll_probe`, where the survivor set is decided.
              Wired `roll_probe(fan=, rows=)` -> ``cloud_bound`` + `extend_cycle(cloud_fan=)` as a
              ``jn_keep`` share. OPTIMISTIC by construction (the fan's lateral tracks Link's offset from
              her at -0.53 u/u), so it sizes the CUT and the enumeration makes the CLAIM
              (`[[banded-proxy-needs-its-newton]]`).
            - **`extend_cycle(cloud_keep=, cloud_cap=)`** is the endpoint form, kept because it is the
              honest ranking of a final list and because running both measures on the same survivors is
              how the cut-vs-population question gets answered on any future cycle. ``cloud_cap`` PRINTS
              what it did not enumerate; unprobed survivors keep an infinite bound and a `None` miss,
              never a default -- a silent truncation is the error s106 found one level up.
            - **Two launch traps cost this session its first hour, both now in `## Tooling`:** a
              `nohup ... &` from a tool-call shell dies with the call's process group while LOOKING
              alive (pid returned, banner written, then gone -- no traceback, indistinguishable from a
              run still working; use `Start-Process ... -PassThru` and watch the PID), and reusing one
              log path across relaunches leaves a killed writer's bytes in the file (Windows NUL
              padding), so an earlier run's lines sit adjacent to a later run's with nothing marking the
              seam: two per-node "probing N of M endpoints" lines from DIFFERENT nodes of different runs
              read as two answers for the same node, which looks exactly like nondeterminism in a search
              whose value is reproducibility. It was not -- both counts were correct for their own node.
              Re-ran clean rather than reason from a holed log. Always `-u`.
      - [~] **THE RETARGETED CHAIN ARRIVES AND STILL LOSES TO THE BANK: the fast-atom landing floor
            over every scored endpoint is 5.93 u at totals 98-99 against a 1.0 u band, and the floor
            measured so far is the CUT's, not yet the population's (session 106).** The s105 handoff's
            solve ran, three configurations of it, all off one ~34-min chain (cycles 1-2 are
            target-blind, so rounds 2-3 iterated cycle 3 alone off the dumped beam via
            `beam_io.rebuild_beam`, ~27 min each). KB:
            [`knowledge/strategy/herd-price-of-a-placement.md`](../../knowledge/strategy/herd-price-of-a-placement.md)
            (new section). Scratch: `_notes/s106_{retarget_chain,escape_landing,retarget2,retarget3,retarget4}.py`
            + logs; `_generated/s106/*.json` (targets, beams, landings -- local).
            - **ROUND 1 (the handoff's config: pure `plan_bound`, the 116 screened rows, budget 79).**
              It ARRIVES: 947.4 u in 75 herd frames, 6 nodes 1.56-1.69 u from screened rows -- but on
              the FAR rows (herd_dist ~947 ≈ the console's 939, not the head's 880-900), because with
              `last_arrive=False` nothing prices the last ~205 u roll's overshoot and the far rows
              catch it. And a herd endpoint is not an arrival: the atom's own frames put the naive
              total at ~103.
            - **THE HONEST SCORER (adapted from `_notes/s105_atom_landing.py`): enumerate the whole
              672-variant atom grid at every endpoint and read the (miss, total) Pareto front.**
              `probe`'s rank never looks at the landing, and `escape_probe`'s `landing_miss` reads the
              thread FIT, which a ±170 u 2D cloud makes meaningless. Fronts: fast atoms (arrival =
              herd + 2..3) land **5.93-6.32 u** off the nearest row at totals **98-99**; the only
              inside-band landing (**0.299 u**, row idx 48) needs a 16-frame atom -- total 112.
            - **THE RESIDUAL IS A 2D FAN AND ITS LATERAL NEVER GOES BELOW +13.8 u** (along -31..+23,
              lat +13.8..+52 over all 1345 firing variants at the round-1 endpoints): the atom always
              pushes her lat-positive, so the herd must deliver ~14+ u lat-LOW of a row -- and the
              chain's natural last-cycle corridor sits at lat +9..+25.
            - **ROUND 2 (head-15 rows shifted by the measured fast residual (12.35, 19.03) via
              `aim.handoff_rows`, budget 76): STALLED by the budget** -- 0 of 33 cycle-3 roll
              survivors under a bound measured against the SHIFTED rows, which overstates endpoints
              the atom's fan can still convert. **ROUND 3 (same, `budget=None`): fills 8 nodes at
              75-76 f whose landings are WORSE (7.8-33.8 u at 99-100)** -- the single-point shift
              steers the rank toward endpoints that convert badly. The shift is not the lever.
            - **WHAT THE THREE ROUNDS LEAVE OPEN, and it is a specific tool:** every keep that chose
              the 6-8 scored endpoints out of the 18-33 roll survivors is landing-blind, so the ~6 u
              floor is the cut's. `_notes/s106_retarget4.py` (ready, was killed mid-run) enumerates
              ALL survivors (`beam=64`, no thread keeps); if the floor holds there too, the missing
              tool is a last-cycle keep ranked on the ENUMERATED cloud landing (not `escape_probe`'s
              thread miss) -- the s107 job either way.
            - **TWO HARNESS FIXES, both in-place per `[[harden-harness-traps]]`:** `extend_cycle`'s
              stock sort crashed comparing `None` vs tuple `quality` under `require_quality=False`
              with no escape/glide keep (a path no prior session ran) -- now None-safe, gated by the
              82-test `test_full_herd`/`test_herd_price`/`test_objective` pass. And **8 slow tests in
              `tests/test_entry_fan.py` are now `@pytest.mark.slow`** (measured individually: each
              >90 s, one >1 h; the other 35 run in 44 s; `test_cross_engine` +
              `test_courtyard_fleet_native` measured FAST, 18 tests in 7.9 s, so they carry no marks
              -- TESTS marked, not files, and the `base_core` gates stay in the default run).
      - [~] **THE SAVING IS REAL IN UNITS AND THE HERD CANNOT PAY IT CONTINUOUSLY: the price is ~6
            frames (101 -> ~95), no prefix of the delivered plan reaches it, and the 14 rows s104
            VERIFIED are the expensive ones (session 105).** s104 handed over the distance-to-frames
            conversion as the job. It is done, and it is three findings and two negatives. KB:
            [`knowledge/strategy/herd-price-of-a-placement.md`](../../knowledge/strategy/herd-price-of-a-placement.md);
            gate `tests/test_herd_price.py` (13, 1.9 s); the conversion itself is now
            `harness/tetrapush/herd_price.py`.
            - **THE ACCOUNTING WAS OFF BY THREE.** `plan_cost` counts from the ARRIVAL, and the
              arrival is where `entry_fan.iter_fan2` starts its fan -- it replays the WHOLE delivered
              log. That log is **78** frames (herd 71 + escape atom 7), not the **75** at which Tetra
              freezes. **The banked deliverable is 78 + 23 = 101 frames from state 2 to the cut**, and
              a candidate is `arrival + plan_cost`. Every total below is on that basis.
            - **THE SCREEN: 33 of the 211 and 11 of the 56 are not static placements at all.** The
              2-frame cloud they were qualified in is a COUPLED fan from the console arrival -- Link's
              own walk recoils off her Co cylinder at the full depth -- so a placement inside his Co
              cylinder there is being pushed, and its cloud is not that cloud. Measured on the exec
              centre, which LEADS his feet by **21.253 u** at the arrival. The console placement and
              all 14 pinned s104 rows read depth 0.0000, so the screen costs the verified set nothing;
              it trims from the CHEAP end, since least-herd means nearest Link's approach.
            - **THE PRICE, TWO WAYS, AND THEY DISAGREE ABOUT WHICH RUNG WINS.** The delivered plan
              herds her 939.4737 u in 75 frames = **12.5263 u/f** (96.4% of `PUSH_CEILING`). Priced at
              that rate: best `plan_cost` 21 = **93.24**, best 20 = **93.45**. Priced by projecting
              onto the delivered plan's own per-frame CURVE and charging the perpendicular miss at
              `LATERAL_RATE`: 21 = **94.63**, 20 = **95.04**. They agree to **0.4 frames** within
              ~2.6 u of that curve and diverge by up to **14** at 46 u off it, so the HEAD of the
              ranking is trustworthy and the tail is not. Both say the prize is about **6 frames**.
            - **NEGATIVE 1 -- THE DELIVERED HERD CANNOT BE TRUNCATED; the price is QUANTIZED.** Its own
              trajectory walks through this region (f68 (-1615.9,-810.8), f70 (-1620.2,-845.1)), so the
              cheap plan is to stop early. Truncating at k and running the ENTIRE 672-variant escape
              knob grid: **0 fire at every k in 62..70**, 247 at 71 (the herd's own end), 323/245/7 at
              72/73/74, 0 at 75-76. The escape needs the state the last roll's exit leaves, so
              "70.6 herd frames" is not a plan this herd can express. **Control: the k=71 enumeration
              contains the delivered plan itself -- 0.432 u from coord idx 274 at arrival 78.**
            - **NEGATIVE 2 -- RE-AIMING THE ESCAPE DOES NOT STEER HER EITHER.** Of k=71's 247 firing
              variants, **62** arrive by frame 78 (<= 99 total at `plan_cost` 21) and they produce
              **7 distinct landings**, all within ~5 u of the console placement, against a nearest live
              placement **21.169 u** away. Tested properly -- each landing's OWN 2-frame cloud
              re-measured from its OWN arrival, then `hull_scan` -- all 7 read **0 leverage**,
              `|resid|min` 2.53e-01 against a ~1e-4 band. Best landing on a live placement over EVERY
              truncation and variant: **6.95 u** (cost 21, at arrival 87 = 108 frames) / 17.38 u (20).
            - **DEPTH AND FRAMES SELECT DISJOINT PLACEMENTS, which re-points the verification.** The 14
              rows s104 verified are the DEEPEST and sit **23-48 u off** the delivered curve: under the
              trajectory price **not one beats the banked 101** (103.46..115.86), under the rate price
              6 of 14 do (96.70..101.66). Depth is bought with contact and frames with proximity, so
              **a depth ranking is a ranking away from the objective** -- re-verify at the frame-minimal
              head (unverified) before another delivery pass.
            - **HARNESS FIX (`entry_fan.base_core`), and it is why any of this could be measured.** It
              read ``seed['log']`` for the hold but always REPLAYED `console_seed`'s log, so every
              cloud `entry_reach.walk_clouds` ever measured with a ``seed=`` was the CONSOLE arrival's,
              silently. Now it replays the seed's own log; inert at the default (gated 0-ULP).
              Related: measuring a 2-frame cloud with `MEASURE_FAN` costs MINUTES against **~3-6 s**
              for ``base_frames=(0,), j1=(1,), j2max=1``, the only shape whose length IS 2 -- which is
              why a per-candidate cloud looked unaffordable and is not.
            - **NEXT: the retargeted `chain_herd`.** Nothing short of a new solve reaches these
              placements, and the estimate it has to beat is ~95 frames against the banked 101.
      - [~] **THE FRAMES WERE ON THE OTHER ADDEND: `plan_cost` 21 AND 20 BOTH CARRY GENUINE DUST AT A
            **TWO-FRAME WALK**, AND THE WALK FLOOR OF 4 WAS INHERITED FROM THE DELIVERED CLIP AND NEVER
            MEASURED (session 104).** `plan_cost` is `plan_frames + thrust + 4`. Sessions 100-103 read the
            standing ask for 21 as a THRUST and closed it against an animation constant (the box below).
            The walk addend had never been taken DOWN -- s100 tested walk 5 (more) and nothing tested 2 or 3.
            - **DERECK KILLED THE FIRST PASS AND HE WAS RIGHT.** "i assumed for testing you would just
              teleport Link to locations. i doubt your 2/3 frame walk search was exhaustive. we should just
              be trying to prove it works first before finding the walk plan." The first pass gridded
              `entry_reach.hull_scan` over the 2-frame cloud and reported ``n_leverage 0`` at all 22
              aimable cells -- **VOID**: `hull_scan` grids LINK'S ENTRY with HER FROZEN at the console
              placement, and a 2-frame entry sits ~40 u away, so she is out of Co range on the cut frame
              and the field is a no-push plateau. Same cloud, same thrust, same facing, cell 2552, 492
              grid points: **console placement 0 leverage / |resid|min 3.29e-01; a productive placement
              293 leverage / 3.50e-03.** HER PLACEMENT IS THE SWITCH, so it is the swept axis. (And a
              1.5 u grid steps over a ~1e-4 u ribbon anyway -- `hull_field`'s own docstring says so.)
            - **THE LADDER, her placement SWEPT over ±170 u / 4 u about the brace, entries gridded at
              1.0 u inside the 2-frame cloud, locus walked at ~1e-5:**

              | `plan_cost` | thrust | live placements | verified | deepest | `cut_frame_swing` |
              |---|---|---|---|---|---|
              | 21 | 15 | **211** (1130 stations) | 8/8 | **+0.339905** | -1.2850 |
              | 20 | 14 | **56** | 6/6 | **+0.207886** | +1.8547 |
              | 19 | 13 | **0** | - | none (nearest \|resid\| 1.6e-03) | +8.9252 |

              Floor +0.1150; the banked 4-frame thrust-15 clip reads +0.2533, so **`plan_cost` 21 is
              DEEPER than the deliverable it beats by two frames.** Every verified row is re-derived from
              its station coordinates alone and passes the engine's genuine flag AND `GT.genuine_clip` on
              the post-CrrPos endpoint, containment in the FINE 2-frame cloud, `is_walkable`, `placeable`
              and depth over floor, at `|resid|` down to 2.1e-07; endpoints land within 1 u of the known
              seam corner (-1727, -990). **19 is refused for the reason the box below already gave** --
              the addends are interchangeable in the ARITHMETIC and not in the physics, since a shorter
              walk starts the roll earlier without re-phasing it.
            - **AND THE SHORT WALK MOVES HER PLACEMENT OUTWARD, WHICH IS WHERE THE NEXT FRAMES ARE.**
              `plan_cost` counts from the ARRIVAL, so a shorter walk is only real if the herd does not hand
              the frames back. Measured against the console placement's 137.2560625336703 u to the corner
              (POSITIVE = less distance to herd): **21 spans -50.6..+64.6 u with 163 of 211 needing LESS
              herd; 20 spans -16.2..+69.4 u with 46 of 56.** A DISTANCE, never a frame count.
              **Dereck's call: "I'm fine with a 15 frame thrust if it means we need to herd her less as
              well"** -- so the objective is now frame-minimal across ALL THREE addends (herd + walk +
              thrust), not the thrust alone, and pricing the herd is the next job.
            - **THE s93 HULL FIXTURE IS 4.8x TOO SMALL AND EVERY `outside the hull` PRUNE SINCE WAS
              OVER-TIGHT.** `MEASURE_FAN` sweeps ``j1=(2,3,4)``, and since `plan_frames` is
              ``base + j1 + j2`` with ``j2 >= 1`` its shortest representable plan is **3 frames** -- it
              returns **0 endpoints** at budget 2, which reads as "no such plan" and is an alphabet
              artifact (`iter_fan2` accepts ``j1=1``). Widening ``j1`` grows the FOUR-frame hull
              **1688 -> 8074 u²** with all 616 pinned vertices contained. Only `outside` was ever a claim,
              so the error made negatives too EARLY, never too late. New fixture
              `fixtures/courtyard_walk_hull_s104.json` (budgets 2/3/4); **the s93 fixture is left pinned**,
              since its own gates were written against it.
            - **THE 2-FRAME CLOUD IS BOUNDED BY PHYSICS, NOT BY THE ALPHABET** -- worth knowing before
              anyone refines sticks at it. On the only 2-frame plan shape (``base_frames=(0,), j1=(1,),
              j2max=1``): stride 8 (583 sticks) = 139 213 endpoints / 123.8 u²; stride 2 (3355 sticks) =
              1 577 346 / **129.7 u²**. A 5.75x alphabet buys **+4.8%** of area and 0.1 u of extent, and
              the nearest genuine entry stayed 2.218 u out of both. Two frames at the speedF cap is the bound.
            - NEW [`knowledge/strategy/plan-cost-walk-budget.md`](../../knowledge/strategy/plan-cost-walk-budget.md)
              + hub; NEW `tests/test_walk_budget.py` (**14 + 1 slow, green**); NEW fixtures
              `courtyard_{walk_hull,walk_budget}_s104.json`; `_notes/s104_*.py`.
            - **NOT A DELIVERED CLIP, and this is the whole remaining gap:** a station inside the cloud is
              dust at an entry a two-frame plan can **REACH**, not one it **lands on**. The fan's entries
              are discrete (two sticks in the whole plan) and the genuine set is a ~1e-4 u ribbon, so
              delivery owes a 2-frame plan whose own predicted entry coincides with a station, then
              `confirm_entry` -> `cross_engine` at 0 ULP -> the DTM. Entry density at stride 1 is ample
              (~1 M endpoints per u² against a ~1.7e-3 u² ribbon), so this is a matching job, not a
              feasibility one.
      - [~] **THE INTERIOR OPTIMUM IS REAL IN THE BAND AND DOES NOT SURVIVE THE RAZOR: 5.0 M NEWTONS SAY
            -0.015503, AND THE REFUSAL IS ONE NUMBER NO SEARCH CAN MOVE (session 103).** All three
            handoff items ran and the peak session 102 predicted is there. Then the confirmation nobody
            had run says the banded gains were the BAND: Newtoned onto the razor the whole peak region
            goes negative, and the s102 + s103 banded headlines collapse to **+0.005** of real progress
            against session 101's own on-razor number.
            - **DERECK: "SOUNDS TO ME YOU HAVEN'T IDENTIFIED THE CORRECT LOCATION YET FOR WHERE TO ROLL
              AND WHERE TO PLACE TETRA." HE WAS RIGHT ABOUT THE METHOD, AND THE ANSWER DOES NOT MOVE.**
              The confirmation below Newtons the BAND'S OWN top 8-16 rows -- a biased sample of the razor
              curve, taken with a proxy this very session proved bad, over an entry corridor only
              +-40..60 u wide. Three things fix it, and all three ran:
              - **THE DENSE MARCH.** `_notes/s103_march.py`: placement x seed motion x entry seed over a
                **+-200 u** corridor, **505 k candidates a cell, every one Newtoned**, nothing ranked by
                its band -- 4.0 M Newtons over eight cells in 25 min. The landscape comes back SMOOTH
                where the sample was ragged (2552 -0.065 -> **-0.0317**, 2553 -0.029 -> -0.0219, 2551
                -0.0416, 2549 -0.0662, 2555 -0.0911, 2557 -0.0776), so the raggedness WAS sampling --
                **but the peak is unmoved: -0.015503 at cell 2554, cross +0.4552, 0 genuine of 320.**
              - **THE FINE LOCAL TEST.** `_notes/s103_local.py` re-searches that row's neighbourhood at
                the resolution the quantities live at -- placement **1 u**, entry **2 u**, seed speed
                **0.25 u/frame**, seed aim **1.4 deg**, 1.0 M Newtons -- and returns **exactly
                -0.015503**, at a DIFFERENT (tetra, entry, seed) triple 2-3 u away. The depth is
                bit-identical across neighbours, which is the ejection equilibrium as a plateau: the
                cut-frame geometry is an attractor, so the grid was never the bound.
              - **AND THE AIM WINDOW IS NOT THE BOUND EITHER.** `AIM_WINDOW` is a hardcoded 900 BAM and
                the GEOMETRIC window (`brace_for_ray` with `|S-old| <= 56`) is **2304 BAM** -- but the
                requirement MINIMISES at facing 40920, interior to the searched range, and climbs from
                0.43 to **13.2** at the geometric edge. Widening it goes the wrong way.
            - **THE CONFIRMATION (the biased sample, kept for the record).** Every banded best is an
              upper bound and owes a Newton (s102 said so; this ran it). Pulling the kept leads onto
              `|resid| <= 1e-4`:
              2551 **-0.0529** / 2552 **-0.0648** / 2553 **-0.0293** / 2554 **-0.0157** / 2555
              **-0.0918** / 2556 -0.1327 / 2557 -0.0795 / 2558 -0.0261, **0 of 56 GENUINE**. Two
              independent routes agree at the peak (the lead-set Newton reads -0.015747, an independent
              10x-tighter-band fine sweep of 44.8 M rows reads -0.015625). So the honest hull-free
              thrust-13 number is **-0.0157 at cell 2554: it does not reach the wall PLANE**, against
              s101's on-razor -0.0208 -- the seed-motion axis, the interior optimum, the wide box and
              the fine grids together are worth **+0.005**, not the +0.088 the bands read.
              **AND THE BAND MIS-RANKS THE CELLS**: banded it peaks at 2554/2555 within 0.007, on the
              razor 2555 is the fourth-worst cell in the window. Never quote a banded depth again
              without its Newton. `_notes/s103_confirm.py`, `_notes/s103_fine.py`.
            - **THE 45-CELL CONJUNCTION (item 1). Every number in this bullet is BANDED, so read it as
              the upper bound the bullet above prices.** All 45 cells at the `coarse` grid: best
              **+0.05966 at cell 2555**, and the whole high side 2558+ has no near-razor row at all.
              Re-run at the `wide` grid over the eight cells around that peak the shape is
              2551 +0.0295 -> 2552 +0.0427 -> 2553 +0.0536 -> **2554 +0.06739** -> 2555 +0.0603, then a
              COLLAPSE at 2556 (-0.0170) and 2557 (-0.0363) where the contact vanishes. So the interior
              optimum session 102 predicted does exist in this metric (its own best was +0.0399 at 2552),
              0.048 under the floor. `_notes/s103_conjunction.py` (three grids; ~25 s a cell coarse, and
              its full grid reproduces s102's cell-2557 reading of -0.0363, at -0.03628).
            - **THE TRADE IS NOT STEERING (item 2).** NEW `_notes/s103_forced_brace.py` asks what a cell
              costs AT THE BRACE ITS OWN RAZOR FORCES (`brace_for_ray` of the facing, iterated to a
              fixed point in the push, since the push rotates the ray). `delta` comes back **0.000 at
              every one of the 45 cells**, so a cell pays NO steering at its own brace and the
              requirement is just `2*(s_forced - |base| + floor/kappa)`. It bottoms out at **0.4256 at
              cell 2557** against a theoretical 0.3927. `contact_required`'s min-over-the-locus sits
              under that (0.3939) only because it lets `old` slide to a nearer brace and buys the slide
              with perpendicular push. Either way the bar is ~0.4 u of overlap, and what refuses thrust
              13 is the CONTACT.
            - **AND THE CONTACT IS REFUSED BY ONE NUMBER OFF THE BAKED SCHEDULE.** NEW
              `razor_depth.cut_frame_swing`: the along-roll step of the animation-posed Co centre INTO
              the cut-consumed frame is **+8.9252 at thrust 13, +1.8547 at 14, -1.2850 at 15**, and it
              is **aim-invariant to 1e-4** over the whole window (the facing rotates the offset and the
              ray together). She can only pay from UP-RAY, so a positive swing is the cylinder RECEDING
              from the only direction that pays. The roll's Co centre tucks to -13.5 u by step 11 and
              then straightens at +8.07 then +8.93, and **thrust 13's cut lands on both of those
              frames**; thrust 15's lands after the recovery has reversed, which IS its free 1.2 u of
              overlap. The ordering reproduces s101's independently measured push column (+0.1304 /
              +0.4773 / +0.5175). KB NEW [`mechanics/cut-frame-co-swing.md`](../../knowledge/mechanics/cut-frame-co-swing.md);
              gates `tests/test_tetra_motion.py` +2.
            - **THE WALK COUPLING IS PRICED AND IT DOES NOT BITE (item 3), and the first way I asked
              was wrong.** Taking the conjunction's kept rows and asking whether they happen to be
              hull-reachable says **94% are outside even the SIX-frame hull** -- but that is a statement
              about the GEOMETRIC entry family those scans generate, not about the corner, and reading
              it as a price is s100's error again. Searching INSIDE the four-frame hull instead
              (`_notes/s103_inhull.py`, entries gridded off `entry_reach.entry_hull`) recovers
              essentially the same result: banded within **0.004** at every peak cell, and confirmed on
              the razor **-0.026367 at cell 2554 with the entry verified in the 4-frame hull**, against
              the hull-free -0.015747. **So the hull costs 0.011 of depth and is not the constraint:
              `plan_cost` 21 entries exist, they simply do not clip.** Control passes -- the delivered
              thrust-15 entry prices at 4 frames, `plan_cost` 23 (`_notes/s103_walk_price.py`).
            - **`placed_step` IS A LIVE ENGINE KNOB NOBODY HAD MOVED OFF 0**, and sweeping it says the
              refusal is the PLOW and not the razor: at cells 2552/2557 the depth CLEARS the floor the
              moment she gets 3-4 frames of plow-freedom (+0.886 at P=12, cell 2557), and every one of
              those rows fails its own deliverability clause by 30-70 u -- she would have had to be that
              far inside his cylinder the frame before. `_notes/s103_placed_step.py` prints the clause
              beside the depth so the two can never be read apart.
            - **GOTCHA -- THE PLACEMENT HALO WAS THE BOUND AND THE PEAKS SAT ON ITS EDGE.** Every peak
              cell's best placement came back at the +-60 u box boundary (cell 2555 at offset
              (-48, +60)): session 100's hull error in a smaller box. Re-run centred on the corner BRACE
              at +-200 u it reads +0.06026 vs +0.05966 and is NOT on the edge, so the plateau really is
              flat and the box was not binding -- but it was luck, not method. Every scan now reports
              `on_box_edge`.
            - **ONE OF THE TWO FRAMES IS AVAILABLE AND THE OTHER IS REFUSED BY THE ANIMATION.** Thrust
              14 (`plan_cost` 22) re-measured on the CURRENT engine, in-hull, on the console placement
              (`placeable` True): depth **+0.2075 at cell 2552**, +0.09 clear of the floor, against
              thrust 15's +0.2532 at the same cell. Not delivered, and NOT a substitute (Dereck's call
              stands) -- reported because it prices what the second frame is worth chasing.
            - **AND THE THRUST-13 NEGATIVE IS THE PROOF DIRECTION, NOT A NEAR MISS.** `depth <= 0` means
              the endpoint is on the near side of BOTH wall planes, which no razor, camera, lean or
              candidate volume moves -- so at every one of the eight peak cells the lunge **does not get
              through the wall at all** and the 0.1150 floor is moot rather than close. Combined with an
              aim-invariant swing that has no knob, the useful next move is a question for Dereck (the
              available frame vs the refused one) and not a finer pass: nothing in the swept space is
              within 0.14 of clipping, and the term that would have to move is an animation constant.
      - [~] **THE REFUSAL IS A CONJUNCTION, AND IT IS MONOTONE: EVERY UNIT OF RESIDUAL LEFT UN-ZEROED
            BUYS DEPTH, SO THE PUSH THAT PAYS FOR A CLIP IS NEAR THE RAZOR AND NEVER ON IT (session 102).**
            The handoff's axis 1 (her VELOCITY, the one term never varied) is now BUILT and it is the
            game's own follow model, but the axis is not what was refusing thrust 13. What was refusing it
            is a pair of constraints nobody had asked at the same time.
            - **THE MECHANISM BEHIND THE INERT PLACEMENT PLANE: AN EJECTION EQUILIBRIUM.** The plow throws
              her out at HALF the overlap every frame, so her distance from the cut frame's Co centre is an
              ATTRACTOR: over a +-40 u grid of static seeds, 22 of the 24 that touch him at all arrive at
              |c - t| **87..93 u** having been flung **10..60 u**, against a requirement of <= 79.4.
              Seeding her a unit closer buys a deeper early plow that ejects her a unit further. The one
              seed that does get inside (68 u, 12 u of overlap) is aimed so far off the ray it is the worst
              row on the grid. KB NEW `mechanics/plow-ejection-equilibrium.md`.
            - **THE SEED-MOTION AXIS, 0-ULP AND ADDITIVE.** `ShoveCtx._run` takes `(speedF, facing, stt)`
              at `placed_step`; `stt < 0` is the historical at-rest seed, bit-identical. A moving seed
              integrates `npc_zl1.Zl1FollowState` **bit-exactly, every frame** (gated). What is
              deliverable is narrow: `STT_MOVE` only, speedF <= 10, and near the corner she has NO DRIVE
              (target speed 0 inside 130 u), so a seed is RESIDUAL momentum decaying 1.0/frame, spent by
              frame `speedF`. It does not close the contact at the cut; it buys a different EJECTION
              HISTORY. Measured worth: it moves the equilibrium ~3 u against a 10.8 u deficit.
            - **THE ENGINE NOW REPORTS THE CONTACT PAIR** (`sweep_par(..., extra=True)`, slots 10-13: the
              animation-posed Co centre and where she stands on the cut-consumed frame), bit-identical to
              `cc_push.co_move_pair` (gated). It exists because a search is BLIND without it: with no
              overlap the push is zero and the depth stops depending on her placement at all, so a climb
              has no gradient exactly where it needs one.
            - **THE LAW INVERTED -- what would be ENOUGH.** NEW `razor_depth.contact_required`: the
              smallest cut-frame OVERLAP a cell can clip on, and the spot she must stand in for it,
              analytic in ~30 ms. Control: at the delivered cell it predicts `cross_len` **0.8085** at
              (-1618.79, -939.00), 31.6 deg off the ray; the console clip delivers **1.2259** at
              (-1618.95, -940.17), 32.4 deg -- **right spot to 1.2 u, right angle to 0.8 deg**. And the
              requirement is **THRUST-INDEPENDENT** (13 vs 15 agree to under 1% at every cell), which is
              Dereck's "it's all the same animations" as a number: thrust 13 is not refused for needing
              more. KB NEW `model/required-cut-contact.md`.
            - **THE DELIVERED CELL IS AN EXPENSIVE ONE.** Required overlap is MONOTONE IN THE BRACE:
              cell **2557 asks 0.3939** (corner-most brace 49.2546, only 4.9 deg off the ray) against
              cell 2552's **0.8037**. Also pinned: `|base|` 49.2202 is **0.0345 u SHORT** of the
              corner-most brace, so every clip here is bought with contact and no aiming trick pays alone.
            - **THE CONJUNCTION, WHICH IS THE VERDICT.** Banding a swept space (placement x entry x seed
              motion, ~10-13 M rows a cell) by |resid| and taking the best `achievable_depth`:

              | \|resid\| | cell 2557 (needs 0.394) | cell 2552 (needs 0.804) |
              |---|---|---|
              | <= 0.05 | **-0.0363**, NO contact | **+0.0399**, 0.65 u of contact |
              | <= 0.5 | -0.0020 | +0.1564 |
              | <= 2 | +0.0841 | +0.3910 |
              | <= 10 | +0.2205 | +0.5121 |

              The razor's own acceptance band is ~1e-4, **500x tighter than the tightest column**. So the
              paying push is real and near the curve, never on it: at 2557 the near-razor rows have no
              contact and the best is exactly the no-push value. **Best corner-scoped near-razor
              achievable depth: +0.0399 at cell 2552** -- past the PLANE, where s101's best over
              everything was -0.0208, and still 0.075 under the 0.1150 floor. It is an UPPER bound
              (it over-reads the delivered clip by 0.066), so treat it as the ceiling, not a result.
            - **AND THE CELL THAT WINS THE CONJUNCTION IS NOT THE CHEAP ONE**, which names the trade: 2557
              asks half the overlap but wants her 4.9 deg off the ray, i.e. essentially ON Link's roll
              line where the plow ejects hardest; 2552's 34 deg costs more overlap and lets her stand off
              the line. **The optimum over the window is INTERIOR and the two cells measured are its ends.**
            - **GATES `tests/test_tetra_motion.py` NEW (10, ~110 s), `razor_depth` 17+2 still green.**
              Bit-equality gates: the at-rest seed is the historical run, a moving seed IS `Zl1FollowState`,
              the contact pair IS `co_move_pair`, `razor_batch` IS `zero_the_resid`.
            - **FOUR SCOPE ERRORS IN ONE SESSION, ALL THE SAME SHAPE** -- a scalar ranked over rows it did
              not scope. Raw `depth_of` returns **+13.6** for a Link 86 u out with the endpoint behind a far
              wall; the law's `d_ray` on a raw row silently grants the steering the razor must pay; a
              magnitude-only surplus scores a **7.4 u** overlap pointing anywhere at +6.5; and
              `achievable_depth` scores **+0.0955** for a row at `|S-old|` **107.46** that Newtons to -41.
              Each was caught by printing the clause, not the proxy.
            - **NEXT: SWEEP ALL 45 CELLS ON THE CORNER-SCOPED CONJUNCTION** and find the interior optimum
              (the two ends are measured; the middle is not). Then attack the trade itself rather than
              either half: what a given contact costs in RESIDUAL is set by how much perpendicular push
              the cell has to spend steering, so the question is which cell's no-push razor sits where the
              contact-bearing configurations naturally brace. Do NOT re-run at-rest placement, lean, or
              hull scans, and do not rank any raw row without first screening its own `|S - old|`.
      - [~] **THE ARRIVE-EXACTLY HIT PUTS TETRA 3.54 u INSIDE WALL B. SHE CANNOT STAND THERE, THE ENGINE
            NEVER CHECKS A SEED, AND WITH THE CLAUSE ENFORCED THRUST 13 IS REFUSED AT ALL 45 CELLS WITH NO
            HULL IN THE SEARCH (session 101).** The box below is measured correctly and reproduces; what it
            was measured at is not a configuration the game can produce. What the session BUYS in exchange
            is the mechanism: the law's push term, decomposed, says exactly what a clip costs and why the
            two frames are not there.
            - **THE CLAUSE.** `ShoveCtx._run` seeds her by WRITING a position with no motion, so her own
              CrrPos has no sweep to line-check and `wall_correct`'s outward-offset segment misses a point
              already behind the plane -- she stays inside the wall and grazes Link's Co cylinder from a
              bearing no reachable spot offers. Her BG wall radius is **50 u** (`npc_zl1.WALL_R`) and all
              **288** live-validated genuine coords sit at **>= 56.98 u** off both planes. NEW
              `razor_depth.placeable`. **The tell was one column over in my own output: every row printed
              `walkable True` -- for LINK's entry.** The filter existed, applied to the other actor.
            - **THE LAW, DECOMPOSED -- `|base|` IS A CONSTANT (49.220224583762864), so a clip is bought with
              `push.u`, the push's PROJECTION on the `old -> S` ray** (`razor_depth.law_of`;
              `depth = kappa*(|base| + push.u - |S-old|)`, kappa = |n.u| ~ 0.712). In-hull at the delivered
              cell: thrust 15 push.u **+0.5175** at brace 49.3812 -> +0.2532; thrust 14 **+0.4773** at
              49.4053 -> +0.2075; thrust 13 **+0.1304** at 49.6202 -> **-0.1901**.
            - **ONLY THE PUSH COLUMN BELONGS TO THE THRUST (Dereck: "it's all the same animations" -- he is
              right).** Shift the entry by whole roll steps and `old` is **BIT-IDENTICAL** at 13/14/15
              (-1692.3143310546875, -955.07611083984375), so the brace is a property of the ENTRY SET, not
              of the frame -- the "0.24 u of brace" reading is retired. What does not survive the shift is
              the push: the cut-frame contact is a **1.2 u graze on an 80 u radius sum** and the Co centre
              is POSED FROM THE MODEL, swinging **1.1..31.3 u** off his position at **2-9 u per frame**, so
              from the brace-reproducing entry her console spot pushes **0.0000** at thrust 13 against
              0.6129 at thrust 15. Same animation, a different frame of it. Gated
              `test_the_brace_is_reproducible_at_every_thrust_but_the_push_is_not`.
            - **THE FLOOR IS THE CORNER'S, AND IT IS NOW MEASURED** (`razor_depth.floor_at_brace`, in
              endpoint space, over the brace locus CrrPos parks him on): **0.1154..0.1216 with no trend** in
              the brace or the aim. s100's ">= 0.1273" was the min over the four populations that happened
              to have live dust, which cannot tell a corner constant from those braces.
            - **THE HULL-FREE, PLACEMENT-CONSTRAINED VERDICT: 0 of 45 cells** reach the floor at thrust 13 --
              best depth **-0.0208** (cell 2554), which does not reach the PLANE, and a 4x finer placement
              grid moves it **0.0007**. The refusal has a mechanism rather than a budget: **the push that
              aims at the corner is the same push that shoves Link off the brace**, and it costs `|S-old|`
              faster than it buys `push.u` (cell 2549: push.u +0.3656 at brace 49.6836; cell 2554: +0.1834
              at 49.4329). NEW `razor_depth.placeable_screen` (~3 s a cell, no hull, both entry families
              swept in the roll's own frame).
            - **TWO LEVERS THE HANDOFF NAMED, BOTH MEASURED DEAD.** The placement plane (+-40 u at 4 u and
              +-200 u at 8 u): `push.u` pinned at **0.11-0.12**, depth ceiling +0.0427 -- a fresh contact is
              only available on the crescent his cylinder has just reached, i.e. AHEAD of him. The LEAN:
              `m351C` decays 35%/frame, so the delivered -388 draw is **-1 by roll frame 15** and +-3000 s16
              moves the depth **0.0003 u**. GOTCHA: sweeping the lean at a FROZEN entry reads a spurious
              0.03 u -- changing the lean moves the razor, so the entry must be re-solved per value.
            - **GATES `tests/test_razor_depth.py` (16 + 2 slow, green; 45 s fast).** NEW
              `test_a_placement_is_a_position_she_can_stand_in`, `..._depth_floor_is_a_corner_constant...`,
              `..._clip_is_bought_with_the_pushs_projection`, `..._entry_lean_is_spent_before_the_cut_fires`,
              `..._no_placeable_configuration_reaches_the_floor_at_thrust_13...` (+ the slow 45-cell form);
              the s100 arrive gate RENAMED to `..._only_from_inside_the_wall` and given the placeability
              assertion. **KB:** NEW `model/placement-standability.md`, NEW `mechanics/roll-lean-decay.md`,
              superseded claim MIGRATED to NEW `history/arrive-exactly-through-the-plane.md`;
              `strategy/clip-razor-depth.md` corrected (floor, projection law, the trade), hub +2.
            - **NEXT -- THE REQUIRED DTM IS THRUST 13 (`cut_step` 15, `plan_cost` 21), Dereck's explicit
              call.** That is the deliverable this work owes, and **thrust 14 is NOT a substitute**: bank it
              only if it falls out free, never as what a delivery run targets. The refusal to break, stated
              exactly: at the converged brace the cut ray misses S by **0.329 u** with no push at all, so the
              push must BOTH steer the razor onto the vertex and add >= ~0.118 of depth -- and every
              placement that restores enough contact to steer it displaces Link off the brace, which is what
              the two extra frames of CrrPos exist to clean up. The open axis is the one term the sweep has
              never varied: **her VELOCITY at the cut** (seeded at rest every time -- `tet_seed` speedF 0,
              stt 3, and `placed_step` re-zeros both), because in stt-4 follow she closes at up to 10 u/frame
              against a 2-9 u Co-centre swing, and that adds push WITHOUT a placement that displaces him.
              Then the pose axis (`nspeed` re-times the chain against the anim frame, but shrinks `|base|`
              1:1). Do NOT re-run placement or lean sweeps for thrust 13. **Price the walk coupling before
              delivering** (unmeasured): buying the brace by entering ~52 u closer costs ~3 walk frames at
              the 17 u/frame cap to save 2 roll frames at 26 u/frame, so a working thrust 13 may not be two
              frames cheaper end to end -- that changes what the frames are worth, not the target.
      - [~] **DERECK: "IF SLASHING ON FRAME 13 WORKS I WANT BOTH FRAMES" -- AND IT DOES, FROM AN ENTRY
            FAMILY THE HULL CANNOT SEE. MY OWN "REFUSED BY THE CORNER" VERDICT WAS SCOPED TO THE FRAME-FLOOR
            HULL AND IS CORRECTED HERE (session 100, second half; SCOPE CORRECTED BY THE BOX ABOVE -- the
            placement it is measured at is inside the wall).** The depth law below all reproduces; what
            was wrong was the word *anywhere*.
            - **THE SET WAS DOING THE WORK.** `entry_reach`'s hull sits **~239 u** from the corner brace and
              a `cut_step` N roll travels **26N u**, so out of that hull Link reaches the wall around step 9
              at every thrust and CrrPos then SLIDES him along it -- the hull holds only the
              **arrive-early-and-slide** family, and two fewer slide frames IS the 0.19 u. The tell was in my
              own numbers: those solutions cut from |S-old| **49.62** while the delivered clip cuts from
              **49.38**, which says the ENTRY SET was the constraint, not the corner.
            - **SWEPT WITH NO HULL (851 598 Tetra x entry pairs in one `sweep_par`, then the placement plane
              with the Newton runs filtered back to sane geometry):** **1167 razor solutions at cut_step 15
              land on the exact brace point thrust 15 cuts from**, and entries **~390 u** out -- 26 x 15, the
              roll's own travel, so the cut fires as Link **ARRIVES** rather than after sliding -- go
              **POSITIVE**: **depth +0.0399** at Tetra **100 u in -z** of her console read, entry
              **(-1422.7771410239, -677.8451682961)**, WALKABLE, |S-old| 49.2792, travel 386.8 u.
            - **SO THE PLACEMENT HAS TWO SCALES AND I PRICED THE WRONG ONE.** At the +-3 u a herd tolerates
              she is inert (0.015 u per u, she is plowed); at **~100 u** she changes the entry family
              outright. That is a different HERD, not a tweak to this one -- which is now the real question
              for the second frame.
            - **WHAT IS STILL MISSING IS BARRIER CLEARANCE, NOT THE PLANE.** `genuine` also needs the swept
              segment to clear the CrrPos barrier, and every genuine row on this corner sits at depth **>=
              0.1273** (the four known-live configurations read 0.1273 / 0.2073 / 0.2533 / 0.3398, each
              bit-constant across its own population). The arrive-exactly family is **~0.087 u** short -- a
              FIFTH of the hull-bounded gap, with the push as the lever (0.446 there vs 0.613 at thrust 15),
              and in a family no pass has ever searched. **A search with a direction, not an impossibility.**
            - **GATED BOTH WAYS** (`tests/test_razor_depth.py`, now **11 + 1 slow**): the hull-scoped gates
              are RENAMED so their names carry the scope
              (`test_from_the_frame_floor_hull_the_floor_thrust_cannot_reach_the_plane`,
              `test_no_frame_floor_entry_at_any_cell_reaches_the_plane_at_thrust_13`), plus NEW
              `test_the_arrive_exactly_family_reaches_through_the_plane_at_cut_step_15` (pins the solution,
              asserts it is OUTSIDE the hull, and asserts it is still short of clearance) and
              `test_the_genuine_depth_floor_is_measured_not_assumed`. Superseded verdict MIGRATED to
              [`history/thrust-13-refused-by-geometry.md`](../../knowledge/history/thrust-13-refused-by-geometry.md);
              `strategy/clip-razor-depth.md` gained "The two families".
            - **NEXT: close the 0.087 u.** Levers, in order: (1) the PUSH at the arrival -- sweep the
              placement plane finely (this was a 20 u grid) and the lean axis, which sets the Co centre at
              the cut; (2) the arrival geometry -- put the entry on the arc `|entry - brace| ~ 26 * cut_step`
              and sweep ALONG it plus the aim cells, since a cell that cuts from nearer S needs less push;
              (3) only then price the herd that delivers it. Do NOT re-run hull-bounded scans for thrust 13.
      - [~] **AT THE FRAME FLOOR ONE FRAME IS FREE (thrust 14) AND THE FLOOR THRUST CANNOT REACH THE PLANE
            -- MEASURED, NOT HUNTED. THE PLACEMENT IS INERT AT HERD SCALE: SHE IS *PLOWED*, 0.015 u PER u
            (session 100, first half; scope corrected by the box ABOVE).** The handoff ordered the placement
            sweep as the route to thrust 13. It ran, and its first ring came back an INVARIANCE, which turned
            into the clause nobody had printed.
            - **THE DIAGNOSIS, IN 7 SECONDS.** `genuine_clip` is three clauses and a search only ever ranks
              one of them (the razor, `resid ~ 0`). Printed as numbers at the delivered cell: `old` is the
              SAME brace-pinned point at all three thrusts, the lunge is a constant, and thrust 13's cut
              endpoint lands **0.172 u SHORT of the nearer wall plane** -- clause 3, never once asked. Its
              cut-frame push reads **0.077 u** where thrust 15's genuine stations carry **0.613**.
            - **THE LAW THAT EXPLAINS IT AND SCREENS EVERYTHING ELSE. S IS THE CORNER VERTEX, so it lies on
              BOTH wall planes** -- a razor solution puts the endpoint on the ``old -> S`` ray and
              **`depth ~ |base + push| - |S - old|`**, with `base` constant per facing. So the penetration
              at the razor is decided by how close the roll braces and how much push survives to the cut:
              s99's "0.65 u pocket" as a rankable quantity instead of a bound on the exit angle. Over EVERY
              in-hull razor solution (Newtoned from the whole hull, 4 and 5 walk frames, 48/45/35 solutions):

              | thrust | `plan_cost` | \|S-old\| | depth | genuine |
              |---|---|---|---|---|
              | 15 (delivered) | 23 | 49.3812 | **+0.2533** | yes |
              | 14 | 22 | 49.4053 | **+0.2074** | yes |
              | 13 (the floor) | 21 | 49.6209 | **-0.1868..-0.3464** | **0** |

            - **HOW TIGHTLY `old` IS PINNED IS THE MECHANISM.** At thrust 15 it is **bit-identical** at all
              48 solutions (CrrPos has finished sliding him in; the entry cannot move it); at 14 the
              solutions spread 4e-4 u of z; at 13 **one `old` each over ~0.07 u** -- the floor thrust cuts
              BEFORE the brace. Firing at `cut_step` 15 costs 0.24 u of brace plus 0.45 u of push.
            - **THE VERDICT, OVER THE WHOLE 45-CELL AIM WINDOW at the frame floor: thrust 13 reads
              depth < 0 at ALL 25 cells that have a razor solution at all** (-0.472..-0.133); thrust 14
              admits at 23 of 25 and has genuine grid solutions at cells 2525 / 2533 / 2549. **So thrust 14
              (`plan_cost` 22) is a frame available with nothing else changed, and no entry AT THE FLOOR
              reaches the plane at thrust 13** (which is NOT "nowhere" -- see the box above).
              Its own resolution control, since thrust 13's `old` is NOT pinned: over grid steps
              2.0/1.0/0.5/0.25 the best depth moves inside **0.008 u** and never trends toward zero
              (-0.1949/-0.1901/-0.1868/-0.1898) against a 0.19 u shortfall -- a ~24x margin.
            - **AND THE PLACEMENT CANNOT PAY AT HERD SCALE.** Over a +-3 u grid of Tetra the thrust-13
              depth moves **0.015 u per u** (-0.157..-0.217), with a mechanism: **she is PLOWED as the roll
              sweeps past**, so her overlap on the CUT frame is the roll's geometry and not her seed. So no
              herd-scale nudge buys 0.19 u. (At ~100 u she moves the entry FAMILY instead -- the box above.)
              One more walk frame does not open the slide family either (cost would still be 22): 2.3x the
              entries, no nearer the plane.
            - **DEPTH IS A GATE, NEVER A RATE.** ``depth <= 0`` is a PROOF (no razor, camera, lean,
              placement or candidate volume moves the endpoint through a plane); ``depth > 0`` is only an
              admission. Against s99's live-station census the two do not even correlate -- cell 2549 at
              thrust 15 reads depth +0.513 with **0** live stations, cell 2553 at thrust 14 reads +0.127
              with **918**.
            - **TRACKED, so no future session re-buys the axis:** NEW
              [`harness/tetrapush/razor_depth.py`](razor_depth.py) (`depth_of`, `razor_solutions`,
              `screen`, `thrust_map`; CLI ``screen``/``map`` -- one configuration ~5 s, the whole window x
              thrust ~3 min) + NEW `tests/test_razor_depth.py` (**9 + 1 slow**, all green), incl. the
              falsifying direction: **`genuine => depth > 0` over 275 genuine rows sampled ON the locus,
              0 counterexamples** (a 0.25 u grid over 7.44 M in-hull entries turned up ONE genuine row and
              tests nothing -- the dust is a ~1e-4 u ribbon). KB NEW
              [`strategy/clip-razor-depth.md`](../../knowledge/strategy/clip-razor-depth.md); the
              superseded placement lead MIGRATED to
              [`history/thrust-13-placement-lead.md`](../../knowledge/history/thrust-13-placement-lead.md);
              `mechanics/roll-cut-thrust-floor.md` corrected, hub +1 question.
      - [~] **DERECK CORRECTED TWO PREMISES AND BOTH WERE LOAD-BEARING: "RIGHT" IS A **LOWER** FACING
            (the KB has the sign backwards, and it aimed s91-s99), AND THE B THRUST HAS BEEN FIRING **2
            FRAMES LATE** because the frame-minimal objective never charged for it (session 99, second
            half).** The exit-angle axis is not where nine sessions looked, and the biggest prize on this
            corner was never the angle at all.
            - **THE SIGN.** `clip-exit-angle.md` labels INCREASING facing "+BAM ... as far to Link's RIGHT
              as possible"; Dereck: *"more to the right should mean a roll angle facing angle LOWER than
              the one we currently have at 40841."* Re-scanned downward over the measured hull, the low
              side is the rich one: cell **2551 (40820, 0.115 deg right) = 220 live stations at the frame
              floor vs the delivered 2552's 208**; 2549 (40795) = 10 at thrust 14; 2525/2532/2533
              (1.7-2.4 deg) = 1 each, plateau bands. The increasing side never produced one genuine
              candidate in 98.2 M. Page header now states the inversion; superseded reading MIGRATED to
              [`history/exit-angle-sign.md`](../../knowledge/history/exit-angle-sign.md).
            - **A 0.115 deg-RIGHT CLIP IS BUILT AND FULLY CONFIRMED (offline).** Cell 2551, facing 40822,
              aim `[91,180]`, thrust 15, lean 64793, plan `[0,228,168,2,198,146,2]`, camera
              `[254,254,128]`, 4 walk frames, entry `(-1529.8834228516,-780.0580444336)`. 7 genuine; all 7
              pass `confirm_entry` AND cross-engine at **worst_ulp 0** with the composite moving the full
              49.8582 u. DTM `_generated/s99/tetrapush_2551_frame_floor.dtm`. **Dereck's call: 0.115 deg is
              indistinguishable from what he has -- not worth a console run.**
            - **THE 2 FRAMES (the session's real find).** `procFrontRoll` (decomp 6852) dispatches a cut
              only when `getFrame() > mRoll.field_0x10` (**17.0**); the frame ctrl runs at `field_0x8`
              (**1.1**) from a start of `field_0xC` (**0.0**, checked in `d_a_player_HIO_data.inc`), so
              1.1*16 = 17.6 first clears it -> **cut_step 15 = THRUST 13 IS THE FLOOR** and the delivered
              clip is thrust 15. It hid because `entry_fan.plan_frames` counts WALK HOLDS ONLY while the
              thrust is modelled as a third DRAW axis -- so a later thrust cost the ranking NOTHING.
              Honest cost `plan_frames + thrust + 4` = the console fixture's own `cut_i - n_console` (23).
              NEW `entry_fan.THRUST_FLOOR` + `plan_cost`; **the existing ranking is deliberately UNCHANGED**
              (re-ranking changes which candidate a delivery targets -- Dereck's call). KB NEW
              [`mechanics/roll-cut-thrust-floor.md`](../../knowledge/mechanics/roll-cut-thrust-floor.md).
              **Dereck's stick hypothesis is RULED OUT:** `mStickDistance` appears only in the
              `getRate()<0.01` branch, never in the gate.
            - **NEITHER FRAME IS BANKED YET.** thrust 14 at the delivered facing: **0 genuine in 23.1 M**
              over ~7 independent cameras (cam 4 duplicated cam 1's TRAIL again), so lambda <= 0.43/pass at
              95%. **Thrust 13 has NO reachable live station at any cell sampled** -- the second frame
              likely needs Tetra MOVED, the axis Dereck named and which nothing in 99 sessions has searched.
            - **THE CORNER'S CEILING, VALIDATED TWO WAYS -- so facing ~35000 never comes up again.** Link's
              brace (the delivered `old` sits at **exactly 35.00003 u** off wall A) plus the 49.74 u max
              lunge pin the cut start to a **0.65 u pocket** on the diagonal, so the seam vertex bears
              **224.19-225.25 deg**: that IS the achievable facing window. The independent catalogue
              `tww-python-scripts/ww/data/seam_clips/Hyrule/Room0__room.csv` (`init->dest`) gives
              **224.717** for this corner. Facing 35000 = **192.26 deg, 32 deg out = ~30x the window** --
              impossible here at ANY placement or entry. Nearest ~192 deg exit in the room is **198.0 deg
              at (-1269.6,-14416.6), 13 400 u away**: a different exit direction is a different SEAM.
              (That CSV's `angle_deg` is the seam's INTERIOR angle, 90.566 here -- NOT the exit direction.)
            - **THREE HARNESS BUGS, ALL FIXED.** (1) **`cross_engine.composite_log` never carried
              `substickX`** -- it built every frame off `seed['log'][-1]`, so a CAMERA-found hit was
              replayed at the FROZEN camera: `handover_ok` False, ~1e6 ULP, `composite_moved` 0.24 against a
              49.86 predicted lunge -- indistinguishable from the composite refusing the lunge. Predates the
              camera axis (s95); no camera pass had ever produced a genuine hit, so nothing exercised it.
              Control = the s90 clip, still 0 ULP. (2) **A delivery must author the FULL log (herd+plan)**:
              `build_boot_movie` puts `log[i]` at F0+1+i and the herd's last 78 frames are PART of the log
              (s90 authored 107). Authoring only the 29-frame tail shifted the plan 78 frames early, the
              A-press fired mid-herd, and **Link TALKED to Tetra** -- caught by Dereck on console.
              (3) A fixed hunt output path let one cell's hunt **clobber another's hits**; now
              `hunt_<cell>_thr<thrust>.json`.
      - [~] **EVERY BAND THE LOTTERY EVER PRICED A DRAW AGAINST WAS MEASURED 10-19 u OUTSIDE THE SET A
            FRAME-FLOOR PLAN CAN REACH -- AND RE-ASKING THE QUESTION INSIDE THAT SET FOUND THE TARGET AT
            THE THRUST SESSION 96 DROPPED FOR CLOCK (session 99).** Dereck's call was "run the station
            check, then stop". The check answers session 98's open question -- "is there any entry whose
            OWN station has dust" -- with a measurement rather than a budget, and the answer is **YES,
            but not at the thrust six sessions were spent on.** At thrust **15** cell 2553 is barren at
            the frame floor: **0 live stations over 1040 of 1040 leans, 12823 in-hull stations sampled**.
            At thrust **14** -- which costs **ZERO extra frames** -- it has live walkable stations at
            **~7%** of its in-hull locus, with real bands. So the six empty sessions were never Poisson
            luck, never a resolution limit and never a missing camera; they were a scope error stacked on
            a clock decision.
            - **DO NOT READ THIS BOX AS "THE AXIS IS DEAD".** The frame-floor negative belongs to
              **thrust 15 only**, which is what `thrusts=(15,)` narrowed every pass to from s96 on. The
              thrust is not a frame cost -- it chooses WHICH roll frame the B edge dispatches the cut on
              (`cut_step` 15/16/17) and `entry_fan.plan_frames` counts walk holds only -- so thrust 14 is
              objective-legal at the floor, and firing one roll frame earlier is if anything
              frame-positive. **s96 dropped it on a clock argument** ("3.8% of the draws / 4.5% of
              E[hits] for 24% of the clock") and that budget decision silently became a claim about
              where the answer is.
            - **WHY THRUST 14 LOOKED BARREN WHEN IT WAS NOT.** Every thrust-14 band s94 measured for
              this cell came out **width 0.0**, which reads as unusable -- but that is not "no dust". It
              is genuine points on a residual **PLATEAU**: many genuine samples sharing one residual to
              the bit, where `grad ~ 0`. `lottery` prices a zero-width band at probability ZERO, so the
              configuration was scored worthless by the one quantity that cannot see it. The dust there
              is positional, and a resid-ranked search is blind to it.
            - **THE TWO SETS, MEASURED AGAINST EACH OTHER.** Against the 4-frame reachable hull
              (`entry_reach`, session 93): **450 of 450 draws INSIDE** it -- every one within **2.63 u**
              of its boundary -- and **20 of 20 bands OUTSIDE** it, by **10.196 to 19.400 u** (median
              12.1). So session 98's 14.5-26.4 u draw-to-station transfer distance and this hull crossing
              are ONE fact from two sides. One frame up, 13 of the 20 come strictly inside (19 at
              `reachable`'s own 1 u margin).
            - **WHY THE "RECORD CLOSEST APPROACH" KEPT IMPROVING AND NEVER CONVERTED.** `window_gap`
              compares a residual NUMBER to an interval and drops the STATION the interval belongs to,
              so the search drove every candidate as near as the reachable set allows to a target outside
              it and then held it there. s96's `8.829e-06` is that boundary point; s98's `0.0` is the
              same point one buy later. **It also vindicates s93's own frame table** (`clip-exit-angle.md`):
              cell 2553 reading 1.1e-02 at <=4 frames was RIGHT, and the 400x "improvement" the lean and
              camera axes booked after it was residual values nearing a band no plan can stand in.
            - **THE TOOL: `entry_reach.hull_scan`** -- `curve_scan` with `reach_radius`'s 94 u box
              replaced by the measured hull, plus a containment test on every station it marches to
              (new additive `entry_search.locus_scan(inside=)`, inert by default and gated so).
              **Two things it must NOT inherit:** (1) seeds cannot be residual sign changes -- only
              **~7% of the hull has leverage**, and the rest is a LITERAL plateau, measured: at 5e-4 u
              steps across 0.02 u a leverage point gives **41 distinct residuals** (~1.3/u, smooth) and a
              plateau point gives **ONE**, every delta exactly 0.0 (the plowed Tetra is out of Co range at
              the cut). So a sign change between two plateaus is a JUMP that Newton returns
              `no leverage` from; seed off the leverage field (`hull_field`). The 7% holds at the
              DELIVERED configuration too, so it is the corner's shape and not a barren cell.
              (2) The grid is not a dust detector -- a ~3e-5 band against a local gradient of order 1/u
              is a ribbon ~1e-4 u wide or narrower -- so `n_genuine_grid` is information, never evidence.
            - **THE RESULT, WITH THE CONTROL AND THE COUNTERFACTUAL THAT MAKE IT A CLAIM** (thrust 15,
              `sep` 6.0, the finer of the two tilings that agree; knob-robust over `sep` 6/12 and grid
              step 1.0/1.5/3.0):

              | scan | live walkable stations | reads as |
              |---|---|---|
              | cell 2552, f4, **thr 15** -- the CONSOLE-DELIVERED clip | **518**, 60 of 60 leans | the scan works |
              | cell **2553**, f4, **thr 15** | **0**, 1040 of 1040 leans, 12823 stations | barren, densely sampled |
              | cell 2553, **f5**, thr 15 | **243**, 44 of 60 leans | the frame WOULD buy it |
              | cell **2553**, f4, **thr 14** | **918** over **561 of 1040** leans, 12914 stations (**7.11%**) | **the target was there** |

              The thrust-14 population is not marginal -- its 561 live leans carry **65.8% of the fan's
              candidate mass** -- and it is the ONLY one: every cell right of 2552 re-swept at **all three
              thrusts** gives **exactly one** live configuration (`_generated/s99/right_thrusts.json`).
              Cells 2554-2556 sample 157-612 in-hull stations and read **0 live at every thrust**;
              **2557 and right have NO in-hull stations at all** (`no leverage on the locus inside the
              hull` -- s93's second-lobe result, now confirmed across three thrusts instead of one). So
              the bigger prizes (2561 +149 BAM, 2581 +455) are not expensive, they are absent.

              The control lands **0.044 u** from the console-delivered entry `(-1531.1785, -781.7216)`
              and the counterfactual **0.24 u** from the station s94 measured 2553's band at -- both
              directions pinned against something measured independently of the scan
              (`[[search-space-contains-human]]`; a negative without its control is not a claim).
              **AND `stations 0` IS THREE FINDINGS, NOT ONE**, so `locus_scan` now returns ``drops``
              (`no_leverage` / `no_zero` / `outside`): a locus that never comes inside the hull is not a
              negative about the cell (cells 2557+ read `no leverage on the locus inside the hull`, which
              is s93's second-lobe result restated), and neither is one with no leverage in it. Only
              "in-hull stations sampled, none live" is -- which is what cell 2553 at thrust 15 is.
            - **THE CAMERA CANNOT CLOSE THE GAP -- the one way this could have been wrong.** The hull is
              measured at the FROZEN camera and the camera is exactly what s95-98 varied. Re-measured as
              a union over five cameras spanning the whole channel including both extremes (`[1,1]` and
              the `[254,254]` s98 found): area **1686.7 -> 1687.0 u2** (+0.02%), bbox unchanged, **0 of
              20** stations inside at a 1 u margin (`entry_camera.hull_shift`, the check s95 built for
              the second lobe).
            - **THE FRAME LEVER IS NOW ONLY THE THRUST-15 STORY.** At thrust 15 the dust is real and at
              **5 walk frames**; that frame is what `entry_fan.capped` refuses, and against cell 2553's
              **+9 BAM** of a 455 BAM axis worth ~1 frame in total (~2-4% of a frame) the trade is
              **~25:1 against**. Thrust 14 reaches dust at **4**, so the frame is no longer the binding
              constraint -- the PRICE is.
            - **AND THE PLATEAU THAT HID THE POPULATION IS ALSO WHAT IT COSTS.** Only **58 of the 918**
              live stations carry a resid-measurable band (median **3.26e-05**, max 3.49e-05); at the
              other **93.7%** the residual is FLAT, so "is my resid inside the band" is either always or
              never true there and **a resid-ranked search cannot sample into it** -- those need ~1e-4 u
              POSITIONAL precision, which a walk-endpoint lattice has not got and no tool here targets.
              Both factors, finally measured at the station the candidate stands on:
              P(station live) **0.0711** x P(it has a steerable band) **58/918 = 0.063** x P(resid in
              band) **3.26e-03** = **~1.5e-05 per kept draw**, i.e. **E[hits] 1 ~ 68000 draws, order
              1000 h** (`_generated/s99/thrust14_sweep.json`).
            - **WHAT IS OPEN IS A SPEND DECISION, NOT A MODEL GAP.** The thrust-14 population is real,
              objective-legal and measured; the prize is unchanged and small (~2-4% of a frame).
              **Recommendation is still STOP -- but on the price of a REAL target rather than on
              impossibility**, and s98's "~90 h" pricing is retired either way since it was computed for a
              population that could not clip at all. If it is ever spent, the pass to run is a frame-floor
              fan at **thrust 14** over the 561 live leans scored against each candidate's OWN station
              (`configuration_band` at its entry, ~30 ms) instead of `BandTable` -- the correct predicate,
              never yet run. NOT another camera lottery: the camera does not move the cloud (+0.02%).
            - Gates: NEW `tests/test_entry_reach_stations.py` (**13 + 1 slow**). KB: NEW
              [`strategy/clip-station-reachability.md`](../../knowledge/strategy/clip-station-reachability.md);
              the superseded "~90 h buys E[hits] 1, so the open question is a station search" MIGRATED to
              [`history/ehits-ninety-hour-axis.md`](../../knowledge/history/ehits-ninety-hour-axis.md);
              `clip-band-transfer.md` + `clip-exit-angle.md` corrected, hub +1 question.
            - **THE DELIVERABLE IS BANKED WHATEVER IS DECIDED (Dereck, session 99).** Tetrapush is a
              one-off solver: milestone 2 stays console-confirmed at the frame floor
              (`fixtures/courtyard_clip_s90_console.json`, `tests/test_clip_frame_minimal.py`). The
              general-purpose Tetra-free seam solver -- to be integrated into Dolphin python scripting --
              is the line that continues (`[[seam-solver-generalization]]`). The exit-angle bonus is the
              only thing this box leaves open, and it is a spend call, not a blocker.
      - [~] **THE LOTTERY'S E[hits] WAS NEVER A COUNT OF CLIPS -- EACH DRAW IS PRICED BY A BAND
            MEASURED ~21 u AWAY, AND THE ONE DRAW THAT EVER LANDED IN ITS BAND DID NOT CLIP
            (session 98).** Dereck authorized the grind (first an hour, then 3+), so the buy ran as
            ordered and delivered its numbers; what it also delivered is the reason those numbers do
            not convert. **The axis is not a 1-hour lottery at 63% odds. It is ~90 h.**
            - **THE BUY, AS ORDERED, AND THE DISTANCE LAW HELD OUT OF SAMPLE.** 14 cameras at the paying
              shape, `spread_cameras` re-ranked after every pick, 11257 s, clock dead steady (763-859 s,
              no drift). **197 new draws, union 450, E[hits] 1.0971, 0 genuine.** New share tracked the
              BAM distance across all 14 points -- **85% at 520 BAM**, 65% at 256, 62% at 128, 35% at 83,
              **5% at 43** -- so session 97's law extends past the 312 BAM its fit ended at.
            - **AND THE POOL HAD BEEN MISSING ITS OWN EXTREME THE WHOLE TIME.** `deliverable_bytes` walks
              ``range(0, 256, step)``, so every strided alphabet stops at byte 240 and `[254,254]`
              (walk **+714**) had never been a candidate in any pass since s95. Its mirror `[1,1]` (-716)
              always was -- 0 clamps into 1 -- and was s97's best pass. Bought here at **520 BAM out**, it
              paid **34 new of 40**, the best pass this axis has produced. `SPREAD_EXTREMES`.
            - **THEN THE RUN PRINTED `best gap 0.0000e+00` WITH EVERY ROW READING `genuine 0`, AND THAT
              CONTRADICTION IS THE SESSION.** `window_gap` returns 0.0 only INSIDE the acceptance band,
              so this is the event `lottery` prices every draw by its probability of reaching -- the
              first in 450 draws, arriving about when E[hits] 1.0971 predicts. It is **not genuine**,
              reproduced bit-for-bit (same entry, resid `1.5499e-04` to the ULP, engine flag False).
            - **THE MECHANISM, MEASURED.** `BandTable` keys a band on (facing, thrust, lean, nspeed) and
              since s94 may find it via `curve_scan`, which marches ALONG the locus to a station that has
              dust. That fixed real false negatives -- it is why this cell has a priced population at all
              -- and it introduced an unstated **transfer assumption**. Sampled over the union:
              **100 of 100** draws are priced by the `curve` rung, at a station **14.5-26.4 u away**
              (median 20.9), and **0 of 100** have any genuine dust at their OWN station -- inside a
              transverse window ~35x the band's own width, so it is a measurement and not resolution.
              For scale, a 4-frame plan's whole reachable entry cloud is ~59 x 64 u.
            - **SO E[hits] IS A PRODUCT OF TWO FACTORS AND ONLY ONE WAS EVER COMPUTED**
              (`P(own station has dust) x P(resid in that station's band)`), the first silently taken as
              1 and measured at 0 of 100 (95% upper bound ~3%). The 450-draw population is worth
              **<= ~0.03 expected clips, not 1.10**, E[hits] 1 is **~90 h** rather than ~1, and the six
              sessions of emptiness were never Poisson luck. **This is the FIFTH level at which this
              search counted copies as discoveries, and the first at which the count was honest and the
              EVENT was wrong.**
            - Gates: NEW `tests/test_band_transfer.py` (**2**, ~0.5 s -- the in-band draw is not genuine
              0-ULP; its band's station is 14.52 u off while its own is barren) and 4 added to
              `tests/test_entry_ledger.py` (**13**). NEW tracked `entry_ledger.walk_bam` /
              `ledger_distance` / `spread_cameras` / `SPREAD_EXTREMES` + CLI `spread`. KB: NEW
              [`strategy/clip-band-transfer.md`](../../knowledge/strategy/clip-band-transfer.md) and
              [`strategy/clip-camera-spread.md`](../../knowledge/strategy/clip-camera-spread.md); the
              overturned "E[hits] is a clip count, so the emptiness is Poisson luck" MIGRATED to
              [`history/ehits-priced-as-clips.md`](../../knowledge/history/ehits-priced-as-clips.md);
              `clip-draw-ledger.md` corrected + hub updated (2 new questions).
            - **OPEN FOR DERECK:** the axis is now priced at ~90 h for E[hits] 1, against a prize
              (+0.088 deg of exit angle, ~4% of a frame if linear) that is still unpriced per cell. The
              recommendation is to STOP the camera lottery. If the corner is still wanted, the live
              question is no longer "buy more draws" but **"is there any entry whose OWN station has
              dust"** -- a different search, over stations rather than over cameras.
      - [~] **THE CAMERA AXIS'S DRAWS ARE MOSTLY COPIES, AND THE THREE-WAY RANKING INVERTS IN THE ONLY
            CURRENCY E[hits] ADDS OVER (session 97).** The handoff ordered local camera neighbourhoods
            around the productive clouds, ranked 0.127 draws/s against 0.087 and 0.045, budgeted at
            E[hits] ~1 in ~50 min. Priced against the draws already held, that ranking is **backwards**
            and the budget is **2.3x** optimistic. Every measurement in it reproduces; none of them was
            compared to anything.
            - **THE NEIGHBOURHOOD RE-DREW ITS PARENT PASS: 6 NEW DRAWS OF 31.** `summarize` dedupes
              across the cameras INSIDE a pass and explicitly refuses to sum `expected_hits` over them --
              and then the session summed across passes. The neighbourhood's 0.127/s is a true count of a
              true population, 25 of whose 31 draws were already in the drawer. Not the centre camera
              either: drop its rows entirely and the answer is bit-identical (31 draws, 6 new), with only
              1 of the 35 clouds in the parent's list at all. **Different cameras reach the same
              entries** -- neighbours command ~94% of the same walk directions.
            - **SO THE RANKING REVERSES AND COLLAPSES.** In NEW draws per second: camera x paying shape
              **0.0329** (29 new of 40), whole alphabet's END rate **0.031**, neighbourhood **0.0245**
              (the pass the handoff said to buy is last; the one it said to skip is first), and the three
              sit inside 35% of each other rather than spanning 2.8x.
            - **THE AXIS IS SATURATING, AND THE CURVE WAS FREE.** Accumulate the 196 cameras' draw sets
              over random orderings: **4.3 draws at the first camera falling to 0.23 over the last
              quarter, an 18x decay** -- the coupon-collector shape of sampling a population far smaller
              than the sample count. So the supply table (196/709/2394/5300 clouds) bounds TICKETS with no
              claim on draws, and a completed sweep's average rate is not repeatable: 0.087/s ends at
              0.031/s, which is the number a next pass costs.
            - **AND BOTH FACTORS OF E[hits] ARE NOW MEASURED, WHICH CLOSES THE ARITHMETIC.** The premise
              `lottery` rests on -- residuals locally uniform across the window -- holds on the population
              itself (**observed/expected 1.00 to 1.18 from 3e-3 down to 1e-4**), so there is no crowding
              near zero to harvest; and the widths are nearly pinned (draws at 2.61e-05/2.81e-05, the
              widest band any lean carries at 2553 is **3.25e-05 = a 1.26x ceiling**). Therefore
              **E[hits] = 0.0026 x distinct draws, exactly**, so the frontier is a draw count and a clock:
              **E[hits] 1 needs 385 draws total, ~1.0 h from the 253 now held** at the spread rate the buy
              measured (below) -- not the handoff's 50 min. The 8.829e-06 record is one order
              statistic out of 127 uniform draws, which is ~a tenth-of-the-time event: s96's "a record is
              not a trend" now has a distributional proof and not only an invariance check.
            - **AND THEN THE BUY FOUND WHAT ACTUALLY GOVERNS THE RATE: DISTANCE FROM THE CAMERAS ALREADY
              BOUGHT, AT PURCHASE TIME.** Five fresh cameras, identical shape and clock (3.18 M candidates,
              ~849 s each), every one **40 draws and 0 genuine** -- and the new share spans **4x**, tracking
              only the BAM distance to the nearest camera already held: 19% at ~20 BAM (the
              neighbourhood), 25% at 78, 20% at 84, 48% at 170, **78% at 266**, 57% at 312.
              **Spearman 0.886 over six passes** -- strongly rank-ordered, not strictly monotone.
              Neighbouring cameras command nearly the same walk directions, so they reach the same
              entries. **So the rule is SPREAD, NOT CLUSTER**, the exact opposite of the handoff's
              "densify around the winners".
            - **AND IT IS THE LEDGER, NOT THE FROZEN CAMERA -- the last camera settles that.**
              `[160,240,128]` sits at **+194**, further from the frozen centre than anything else bought,
              and pays the **LEAST of the five (20%)**, because `[96,224,128]` had just been bought 84 BAM
              away. Reverse their purchase order and their yields swap: the quantity is a property of the
              LEDGER at purchase time. And a bounded pass's own draw count predicted NOTHING -- bounded
              9/8/8/8/8 gave 10/31/19/23/8 new.
            - **WHERE THAT LEAVES THE AXIS: 253 draws, E[hits] 0.651, 0 genuine, best gap unchanged.**
              The buy added 91 new draws in 4246 s (0.0214/s aggregate, 0.0096 worst, 0.0356 best), and
              **E[hits] 1 is +132 draws ~ 1.0 h** at the spread rate. The emptiness is not a tension with
              the model: 253 draws at E[hits] 0.651 with 0 genuine is Poisson **P(0) = 0.52**, the most
              likely single outcome. `_generated/s97/ledger_buy_2553.json`, `_notes/s97_ledger_buy.py`.
              **Cost note, measured rather than inferred:** the pass reaches its first row in **862 s
              against 861 s of search** -- setup is ~1 s, at **9.5 of 12 logical cores** -- so budget a
              run as simply `~860 s x cameras`.
            - **THE FRAME LEVER IS ALREADY CLOSED BY THE OBJECTIVE, IN CODE.** `clip-exit-angle.md`'s
              frame table has cell 2553 reaching 2.3e-05 at <=5 frames against a 2.6e-05 band -- i.e. one
              extra frame would likely just convert. It is not available: `entry_fan.capped` drops plans
              over the floor citing Dereck's zero-frames constraint, and 2553 IS the whole exit-angle
              prize at the floor. So the lottery is the route, and its price is the number above.
            - NEW tracked `harness/tetrapush/entry_ledger.py` (`Ledger`/`novel`/`accumulation`/
              `uniformity`/`extract`, CLI `price`/`saturate`/`uniform`) + LOCKED
              `fixtures/courtyard_draw_ledger_s97.json` (the three passes' populations reduced to what
              `draw_key`/`lottery`/`accumulation` consume -- a pass writes to the gitignored
              `_generated/`, so the finding was not otherwise re-runnable from a clone); gate
              `tests/test_entry_ledger.py` (**9**). KB: NEW
              [`strategy/clip-draw-ledger.md`](../../knowledge/strategy/clip-draw-ledger.md); the
              overturned ranking MIGRATED to
              [`history/camera-neighbourhood-enrichment.md`](../../knowledge/history/camera-neighbourhood-enrichment.md)
              and `clip-search-budget.md`'s section split so the half that stands keeps its own anchor.
      - [~] **THE CAMERA AXIS IS A TWO-BYTE CHANNEL, SO ITS SUPPLY IS `bytes^2` AND NOT PATHS -- AND THE
            CLOSEST APPROACH IS NOW INSIDE ONE BAND WIDTH (session 96).** The handoff ordered the
            segmented alphabet run at stride 16, "deduped, the dedup is automatic", budgeted at 0.157
            draws/s. Three of those premises were wrong; the pass that replaced them is cheaper, bigger,
            and 12x closer.
            - **THE SHIPPED DEDUP COLLAPSED NOTHING.** `dedupe_cameras` keys on `fan_steps` (6 frames at
              the bounded shape) and returns **137 of 137, 440 of 440**. The 0.157 draws/s came from
              grouping on the plan's 4 frames -- a different key, and a LOSSY one (79% of the draws for
              39% of the clock). Both are one named parameter now (`search(group_steps=)`), and a pass
              records which key it ran under, as it already did for its cell scope.
            - **A SWITCH POINT IS NOT A CAMERA.** The 4-frame walk trail is a function of the C-stick
              bytes on frames **0 and 1** and nothing later -- exact over all 4096 four-byte paths at
              stride 32, where 3584 disagree with their 1-byte prefix. A second switch point multiplies
              paths 8x and stepped trails 7.7x and adds **zero** walk clouds (64 -> 64 at stride 32,
              196 -> 196 at stride 16). So supply is `(deliverable bytes)^2`: **64 / 196 / 709 / 2394 /
              5300** distinct walk clouds at byte stride 32 / 16 / 8 / 4 / 2. It is also the mechanism
              behind s95's unexplained "41 of 49 groups report a bit-identical draw set".
            - **AIMABILITY IS A FREE KNOB, so s95's "64 of 82 aimable" bounded the ENUMERATION, not the
              axis.** The aim frame sits past the walk channel, so a tail byte moves the aim -- and
              whether the cell is aimable at all -- while leaving the walk cloud bit-identical. Choose
              the walk pair first, then search a tail: **0 of 196 clouds dropped** (`walk_cameras`). At
              stride 16 that is **196 clouds from 196 passes**, against s95's 157 from 440.
            - **THE SCOPE, PRICED BOTH WAYS -- and the second half is a negative.** Cell 2553's
              thrust-14 configuration is **3.8% of the draws and 4.5% of E[hits] for 24% of the clock**,
              so a pass drops it (`thrusts=(15,)`). Adding cell 2551 measures **3.1x the draws for the
              same clock and is worth ZERO**: 2551 is LEFT of the console-delivered cell 2552 and the
              objective term is the exit angle as far RIGHT as possible. A rate in the search's own
              currency read 2.9x on a prize the objective refuses (razor rule 15's third corollary).
            - **THE PASS: 196 cameras / 1462 s -> 127 DISTINCT draws (816 reported), E[hits] 0.329, 0
              genuine -- and a closest approach of `8.829e-06` against a band `2.8125e-05` wide.** That
              is **0.31 band widths**, where session 94's exhausted 3.2 M-candidate frozen pass sat at
              3.287e-04 (12.6x outside) and session 95's cameras at 1.073e-04 -- **37x and 12x closer**.
              Draw rate **0.087/s**, 1.13x the seg:32 pass's on 1.07x the clock.
            - **BUT THE RECORD IS ONE DRAW, NOT A TREND -- CHECKED, AND IT COST NOTHING TO CHECK.** That
              approach is a single candidate (walk endpoint `(-1511.5211181640625, -760.56689453125)`,
              lean 65281, nspeed 26, camera `[16, 32, 128]`, plan `[0, 208, 192, 2, 192, 88, 2]`), and it
              is **invariant**: densifying that camera **41x** (the s94 paying shape, 3.20 M candidates,
              881 s) moved it by *bit-identical zero*, and **35 neighbouring walk clouds all report the
              same gap bit for bit** (12 of the 35 reach that very endpoint). So the axis is still a
              LOTTERY and E[hits] per second is still the number that governs it -- a best-of-population
              statistic improving 37x is not convergence, and the 7.1% the residual would have to fall is
              ~2.9e-04 u of entry movement, finer than the endpoint lattice stride-1 density produces.
            - **WHAT DOES PAY: LOCAL CAMERA NEIGHBOURHOODS.** The 35 clouds within +-8 bytes of the
              winner returned **31 draws in 245 s = 0.127 draws/s and 0.886 draws/camera**, against
              0.087/s and 0.648 over the whole alphabet -- a **1.46x** rate. The neighbourhood of a
              productive cloud is enriched even though its best gap is not better, which makes
              "densify the CAMERA around the top clouds" the cheapest known way to buy draws here.
            - **AND THE CAMERA x PAYING-SHAPE PRODUCT IS PRICED AND NOT WORTH BUYING** (the s95 handoff's
              second item, measured on the winning camera rather than on spread): 0.045 draws/s against
              the bounded shape's 0.087 -- 41x the candidates for 129x the clock, 8x the draws.
              The axis DOES thin with camera density too (0.648 draws/camera at stride 16 against 1.11
              at the coarse held alphabet), so the supply table bounds tickets, not draws.
            - **TWO DELIVERY BUGS, both fixed, both inert at a frozen camera -- so a camera hit could not
              have been cashed.** `confirm_entry` did `int(hit['substickX'])`, which RAISES on a sequence
              camera: every camera pass since s95 could have produced a hit nothing could replay. It now
              schedules the path frame-for-frame (byte k on replayed frame k, `cam_trail`'s own
              alignment) and RETURNS the frames it replayed, so a delivery authors the confirmed input
              instead of rebuilding it (`deliver.build_boot_movie` reads `substickX` per row). And the
              aim was stamped at the pass's frame CAP rather than the candidate's own plan length: the
              facing latches against `trail[n + 1]`, so a short-plan hit carried bytes delivering a
              facing **12 BAM off** (measured). Both invisible frozen (constant trail) and invisible in
              the s95 numbers (every one of its 540 near-misses came in at the cap).
            - NEW `entry_camera.walk_channel`/`WALK_CHANNEL`/`walk_cameras`/`plan_frames`,
              `search(group_steps=, thrusts=)`, the `walk:STEP` byte spec and a thrust argument on the
              CLI; `entry_search.confirm_entry` schedules a C-stick PATH and returns its frames. Gates
              `tests/test_entry_camera.py` (**20 + 1 slow**). KB: NEW
              [`strategy/clip-camera-supply.md`](../../knowledge/strategy/clip-camera-supply.md); razor
              rule 15 gains a third corollary and its "64 of 82" bound is corrected; the superseded s95
              recipe MIGRATED to
              [`history/entry-search-s95-segmented-cameras.md`](../../knowledge/history/entry-search-s95-segmented-cameras.md).
      - [~] **THE CAMERA IS A FREE INPUT CHANNEL INSIDE THE ENTRY PLAN, AND THE HALF OF IT PRICED AT
            ZERO WAS PRICED OVER A GRID THE FAN CANNOT HOLD (session 95).** *(Its "spend the axis" item
            is done in the box above -- and three of the recipe's premises did not survive it.)* The handoff ordered the
            csangle swept and its frame cost taken to Dereck before any pass. **The cost is ZERO and it
            is read off the locked console log rather than argued**, and the axis it opens is not the
            one session 83 closed.
            - **THE PRICE, from the fixture's own bytes.** The entry plan runs AFTER the escape atom
              (`fixtures/courtyard_entry_s86_console.json` rows 78..), and every one of those frames
              carries `substickX == 128`. The C-stick there is IDLE -- the atom has already fired, so
              nothing downstream needs the camera frozen -- so a slew inside the entry plan cannot cost
              a frame. What is bounded is the REACH: a held byte moves csangle **-716..+714 BAM by the
              4th entry frame**, 1-frame delay, on a fine ladder (byte 96/160 = -5/+4).
            - **AND THE AXIS IS THE WALK, NOT THE AIM.** s83 was right about the aim side (the schedule
              is cell-quantized; a slew re-indexes and cannot add a cell). It also priced the WALK side
              -- 3612 of 4096 direction cells, "1.07x" -- **over the whole stick grid at `msd_min=0`,
              which the fan cannot hold**: it keeps only endpoints at the speedF cap, so its alphabet is
              the cap-magnitude one, **2280 angles reaching 1736 of 4096 cells, 42.4%** (gated against a
              real fan, not argued from the speed law). One sine cell of camera moves **888 of those
              1736** onto directions the frozen camera cannot command at all; the union over the slew is
              the whole circle. A different camera is a different discrete ENTRY SET -- exactly what
              session 94 ran out of.
            - **MEASURED: 64 CAMERAS, 643 s -> 71 DISTINCT NEAR-MISS DRAWS, E[hits] 0.19, of which 96%
              STAND WHERE THE FROZEN FAN CANNOT REACH.** Session 94's exhausted 3.2 M-candidate pass at
              the frozen camera read E[hits] 0.194 in 866 s, so the rate matches at 0.74x the clock --
              but on a population the frozen camera has no access to, and **without saturating**: each
              camera is a fresh 10 s draw where more candidates at one camera had stopped paying.
              Closest approach at cell 2553 on one bounded fan: **1.49e-3 frozen, 2.9e-5 at +200 BAM.**
            - **COUNTED THE WAY THIS SEARCH HAS LEARNED TO COUNT.** The pass reports **243** near-misses
              and they are **71 draws**: neighbouring cameras command ~94% of the same directions, so
              one entry reached at two cameras is ONE draw. `summarize` dedupes ACROSS cameras before
              summing the lottery -- pooling would have read 0.65 and been the fourth instance of
              counting copies as discoveries here.
            - **AND THE BUDGET RULE: MANY CHEAP CAMERAS, NOT DEEPER ONES.** The same camera at a 6.5x
              wider shape (507 k candidates, 124 s) buys 4.3x the draws for 12x the clock -- the family
              axis's own diminishing return. Per second the bounded shape is ~3x better.
            - **MORE CAMERAS EXIST -- THE C-STICK MAY CHANGE MID-PLAN -- AND THEY NEED THE SAME DEDUP.**
              A segmented alphabet at byte stride 32 is **137 cameras -> 105 distinct draws, E[hits]
              0.273, 1365 s**. But those 137 carry only **49 distinct walk trails**: a camera that
              changes only AFTER the walk re-aims the same cloud, and **41 of the 49 groups report a
              bit-identical draw set**. One representative per group buys 83 of the 105 draws in 530 s
              (**0.157 draws/s against 0.077**). The key is the trail prefix the fan actually STEPS
              (`fan_steps` = `max(base_frames) + max(j1) + j2max + 1`), not the plan's frame cap -- the
              other 8 groups differ precisely because the fan steps past the cap. `dedupe_cameras` is
              in `search` now and reports the collapse.
            - **WHAT THE CAMERA DOES NOT MOVE: THE CLOUD.** Hull area across the whole slew changes by
              **+0.0%** (1686.7 -> 1686.9 u2), bbox not at all, and **0 of 9** second-lobe stations enter
              the union hull. The re-index happens INSIDE the cloud, so session 93's second-lobe
              negative survives this axis instead of being reopened by it.
            - **THE THING THAT COULD HAVE MADE IT A PHANTOM, checked:** the camera is still RAMPING when
              the roll's facing latches. Measured by firing the roll and reading the facing back, the
              facing is `decoded_aim + 0x8000 + trail[frames + 1]` (unanimous over cameras spanning
              -1619..+1420 BAM; the neighbouring indices are 90-460 BAM wrong). So a hard slew moves the
              aim alphabet too -- at subx 249 the bytes that reach cell 2551 frozen roll into cell
              **2640** -- and a camera draw only counts where the cell stays aimable: **64 of 82**. A
              pass skips the rest and says so.
            - NEW `harness/tetrapush/entry_camera.py` (`cam_trail`, `camera_alphabet`,
              `segmented_alphabet`, `aim_frame`/`aim_at`, `walk_cells`/`cell_census`, `fan_cam`,
              `probe`, `search`, `hull_shift`; CLI `reach|alphabet|cells|hull|probe|search`);
              `entry_fan.iter_fan2(hold=, cs_trail=)` + `_fan_chunk(cs_seq=)` inject the trail per
              frame; `entry_search.confirm_entry` honours `hit['substickX']`. LOCKED
              `fixtures/courtyard_cam_trails_s95.json`. Gates `tests/test_entry_camera.py` (13 + 1
              slow) -- including the trail-vs-WIRED-camera 0-ULP check that pins the injection
              alignment (frame k decodes against `trail[k]`, which a constant injection cannot see) and
              the regression that the neutral byte reproduces the default fan key AND value.
            - **KB:** NEW [`strategy/clip-camera-axis.md`](../../knowledge/strategy/clip-camera-axis.md);
              razor rule **15** (price a lever against the subset the SEARCH can use, not the one the
              hardware has; an input channel nothing is using over your frames is a free axis; a free
              axis is still bounded somewhere else); the overturned walk-side share appended to
              [`history/entry-search-s81-camera-lever.md`](../../knowledge/history/entry-search-s81-camera-lever.md)
              (its aim-side half stands); `clip-exit-angle.md` + hub updated.
      - [~] **CELL 2553 WAS NEVER A LEAN PROBLEM -- THE ACCEPTANCE BAND WAS A NEGATIVE ARGUED FROM ONE
            NEWTON SEED, AND THE SAME TABLE CALLED THE CONSOLE-DELIVERED CLIP'S OWN CONFIGURATION DEAD
            (session 94).** *(Its open item -- "the camera is the lever left" -- is measured in the box
            above: the axis is real, free, and does not saturate; the cell is still unconverted.)* The handoff asked for cell 2553's band across the leans the fan arrives on,
            expecting to aim the pass at (lean, cell) pairs. The measurement says the leans were never
            the problem: it is the s90/s92 single-station defect one level down, in the RANKING instead
            of the scope, and it had survived both fixes untouched.
            - **THE TELL, and it needs no argument.** `configuration_band` Newtons the entry onto the
              residual zero FROM A SEED, and `BandTable` handed it one seed for every key -- the single
              global `ref_entry`. Ask that table for the band at the configuration of the clip that was
              DELIVERED TO CONSOLE AND WORKED (facing 40841, thrust 15, lean 64761,
              `fixtures/courtyard_clip_s90_console.json`) and it answers `no genuine on the residual
              zero`. A ranking whose input says the known-good input has no band is broken before any
              of its other verdicts are worth reading (`[[search-space-contains-human]]`).
            - **WHAT IT COST, MEASURED THREE WAYS.** Cell 2553 / thrust 15 goes from **0 of its 24
              heaviest fan leans usable to 20 of 24**; **10360 of the 15968 rows** in the band cache were
              negatives of the one-seed kind (that is the unaudited cache the s89-s93 handoffs kept
              flagging -- audited now); and re-running session 93's own pass over the **identical 779130
              candidates** turns "180 dead-tail, 0 near, E[hits] 0.000" into **34 near-misses at E[hits]
              0.079**. So cell 2553 -- +9 BAM, the whole exit-angle axis at the floor -- is a live,
              PRICED lottery where the pass had reported a dead cell. Nothing was ever suppressed: a
              band never vetoes a `genuine` (that comes from the sweep), which is exactly why a wrong
              one is silent and reads as "stop buying density here".
            - **THE LADDER** (`BandTable._measure`): the global ref, then the configuration's OWN
              qualified station, then `locus_scan`/`curve_scan` seeded from it. No single cheap seed
              dominates -- over those 24 leans the global ref wins 19/24 at cell 2551 and 0/24 at 2553,
              the qual station 17 and 11 -- so it is a ladder and not a better default. Every seed is
              FIXED per key on purpose: a first cut also carried the last station that had paid for the
              same (facing, thrust), which is free and converts keys but makes the answer depend on the
              order the keys were REQUESTED, so two passes over one scope disagree and any single-key
              gate is flaky. Rungs 1-2 cost ~30 ms and 3-4 ~2-6 s, and a pass measures a band only for
              its near-zero tail, so the bill tracks the tail and not the candidate count.
            - **AND THE CACHE CANNOT OUTLIVE THE FIX.** A cached row that is NOT productive and does not
              record that it was escalated is dropped on load and re-measured; a productive one is kept
              whatever rung found it. Saves are versioned (`version: 2`) so the distinction is legible
              from the file.
            - **THRUST 14 IS THE GENUINELY DEAD ONE**, which is worth pinning because the s93 handoff
              pointed here at thrust 14 (the fine probe's 4.45e-05 closest approach is there): at cell
              2553 it is barren at every one of the 24 leans even escalated, while every near-miss the
              re-run found is **thrust 15**. Closest approach and band width are different quantities.
            - **THE (lean, cell) AIMING THE HANDOFF ASKED FOR IS BUILT AND IS A WEAK KNOB, honestly
              reported as one.** NEW `harness/tetrapush/entry_lean.py` (`census`/`bands_at`/`rank`/
              `parse_lean_spec`/`select_by_lean`) + `search2 leans=paying:2553 thrusts=15`. But the FAN
              generation dominates a frame-floor pass and a lean filter runs downstream of the stepping,
              so it saves evaluation and not wall clock -- it pays when the configuration count is large
              (s92's 40 configurations are ~6.7x the evaluation of 6). And
              it is never a claim about what it drops: **the delivered clip converted at a band of width
              0.0** (20 genuine samples at one f32), so width RANKS and must never filter.
            - **WHERE THE DRAWS ACTUALLY COME FROM** (the re-run's own census): all 34 near-misses are
              thrust 15, all are 4-FRAME shapes -- 23 at `(n0 0, j1 2, j2 2)` and 11 at `(1, 2, 1)`,
              none from a 2- or 3-frame plan -- and 17 of 34 sit at the delivered lean 64761.
            - **AND A FAMILY IS A BUDGET UNIT ONLY INSIDE ONE PLAN SHAPE -- the density buy measured
              that the hard way.** Widening `j1=2, nbase=2` to `j1=1,2, nbase=3` at stride 2 went 1012 ->
              **10036 families, a 9.9x buy, for 1.9x the near-misses** (65, E[hits] 0.160) because the
              cumulative rate fell 5.2x: `j1=2` pays **0.032/family** (stable at stride 4 AND stride 2),
              `(n0 1, j1 1)` 0.0025, and `(0, 1, *)`/`(2, 1, *)` -- 5542 families -- pay **exactly zero**.
              So the same clock at stride 1 on `j1=2` alone buys FEWER families and more draws. KB
              [`strategy/clip-search-budget.md`](../../knowledge/strategy/clip-search-budget.md)
              gains `## A FAMILY is a budget unit only inside one plan SHAPE`; report the rate per shape,
              never pooled, and price a shape before widening into it.
            - **THE STRIDE-1 PASS AT THE PAYING SHAPE RAN, AND IT SAYS THE FAMILY AXIS IS EXHAUSTED
              HERE.** `search2 1 2 1 2 2 cells=2553 frames=4`: 3213312 candidates / 4162 families /
              6.43 M evaluations / 866 s -> **83 near-misses, E[hits] 0.194, 0 genuine**. The best
              approach is **3.287248e-04 -- BIT-IDENTICAL to the stride-2 pass's, at the SAME entry**
              (reached by a different prefix), against a band width of 2.6066e-05 at that lean, so it is
              12.6x short and 2.4x the candidates moved it by exactly zero. That is s93's own controlled
              comparison, applied to this axis and giving the same verdict. Two more numbers say the
              same: the marginal rate inside the pass falls to **0.0087/family against 0.0199
              cumulative**, and family count grows at ~45% of alphabet growth (alphabet 1x/2.7x/9.2x ->
              families 1012/1713/4162) because a finer alphabet mostly adds decode classes that do not
              hold the speedF cap.
            - **SO CELL 2553 IS LIVE, PRICED, AND NOT CONVERTIBLE ON THIS AXIS: ~E[hits] 0.2 per
              exhaustive frame-floor pass.** The lever left is the one s92 re-opened -- the CAMERA. At
              the frozen csangle 34325 **exactly ONE aim reaches cell 2553** (1 each for 2551/2552; 60
              aims across the window, most cells 1-3), and a slew shifts the whole alphabet, so it moves
              both WHICH cells are aimable and how many aims reach each. s83 priced the camera at zero
              against a 2-cell window; rule 12's corollary is that a closure expires when its premise
              moves, and the window is now 22 live cells / 40 productive configurations.
            - LOCKED `fixtures/courtyard_lean_bands_s94.json`; gates `tests/test_entry_lean.py`
              (incl. the console clip reproduced GENUINE through `stream_search` at its own entry and
              residual, 0-ULP, with an escalated band); KB
              [`strategy/clip-band-per-lean.md`](../../knowledge/strategy/clip-band-per-lean.md) + razor
              rule **14** (a fix to the SCOPE does not reach the RANKING -- re-ask it of every consumer
              that shares the machinery, and gate a scoring against something you have already
              delivered); the overturned dead-share MIGRATED to
              [`history/band-dead-share-from-one-seed.md`](../../knowledge/history/band-dead-share-from-one-seed.md).
      - [~] **THE SECOND LOBE IS NOT REACHABLE AT THE FRAME FLOOR, AND THE AXIS SESSION 92 PRICED AT
            ~10x WAS PRICED OVER A 94 u BOX THAT IS NOT THE REACHABLE SET (session 93).** The handoff
            asked whether a frame-floor plan lands on cell 2561/2562's locus. It does not, nothing at
            the right does, and the reason is a claim argued over the wrong set again -- this time a
            POSITIVE over one too big, in the same session that fixed a negative over one too small.
            - **THE PASS RAN TO COMPLETION AND IS THE EMPTIEST THIS SEARCH HAS PRODUCED.** The whole
              aimable second lobe (9 configurations, cells 2561/2562/2564/2567-2570/2572/2573), frame-
              capped at the delivered floor of 4: **779130 candidates, 2.89 M streamed, 7.01 M
              evaluations, 1012 prefix families, 494 s -> 0 genuine, 0 near, 0 dead-tail.** Not one
              candidate came within `BAND_PROBE` (5e-3) of any right cell's residual zero.
            - **WHY, AND IT IS NOT DENSITY.** `stream_search` drops everything past the probe, so it
              cannot say whether a pass missed by a ULP or by twenty units -- measure that instead: the
              closest a 4-frame candidate gets is **0.354 at cell 2561, rising monotonically with the
              facing offset to 1.873 at cell 2581**, i.e. **71x to 375x outside the probe**, at a
              `grad == 0` entry. For cells **2570 and right the residual does not even change sign**
              over the whole cloud (0 of 46495 samples on the other side). Careful what the signs
              license, though: `resid`'s gradient is ~1.2/u over a ~60 u cloud so it spans +-70 there,
              and "both signs present" (2561/2562, 2.7% negative) says a boundary is in the sampled set,
              NOT that a zero a plan can land on is.
            - **THE DENSITY EXPLANATION IS RULED OUT BY A CONTROLLED COMPARISON.** Same question, two fan
              densities at the floor -- 157291 candidates and 2888346, an **18.4x** buy. Cells 2561/2562
              come back **bit-identical** (0.35417 / 0.430095, the same f64, at the same argmin entry in
              both fans) while cell 2553 sharpens **37x** on exactly that extra density (1.64e-03 ->
              **4.45e-05**, inside its own band width). A fan that resolves one cell 37x and another by
              nothing is not short of resolution at the second. LOCKED
              `fixtures/courtyard_frame_price_s93.json`; gate `tests/test_entry_reach.py`.
            - **AND THE HULL AGREES WITHOUT BEING TOLD -- the second witness.** It knows nothing about
              residuals; it is walk endpoints and a frame budget. Asked which of the 40 productive
              configurations have a station a 4-frame plan can put the entry on, it answers **cells 2551
              and 2552 ONLY** -- exactly and independently where the entire 55-candidate console-delivered
              population sits. The 4-frame cloud is **447581 endpoints in a 58.6 x 63.8 u bbox against
              the 188 u box `reach_radius` implies (~11% of its area)**, and all four bbox corners are
              outside the hull, so the cloud is genuinely curved rather than box-filling.
            - **THE SIGNED DISTANCES, because they say how marginal the verdict is** (+ inside): the three
              delivered-cell stations read **+1.61 / +1.80 / +1.83 u**, the second lobe **-10 to -95 u**,
              and cell **2553 only -2.26 u** (thrust 14). So the second lobe is not a marginal call, but
              **2553's is inside the hull's own resolution** -- it was swept at s1/s2 stride 8, and a finer
              alphabet grows the hull. Do NOT read the hull as calling 2553 unreachable; its own pass
              (180 candidates inside the probe) shows the fan does reach near that locus, and a station is
              one point on a curve. That asymmetry is the module's stated contract, not a caveat added
              afterwards.
            - **CELL 2553 (+9 BAM) WAS RUN TOO, and it is a ULP lottery this pass did not win:** the same
              779130 candidates, 1.56 M evaluations, **180 dead-tail, 0 near, 0 genuine**. So unlike the
              second lobe (0 dead-tail from 7.01 M evals) candidates DO reach its residual zero -- 180 of
              them inside `BAND_PROBE` -- but every one sits at a lean whose band has no usable width, so
              the target there is a single f32 value. Which is also true of the delivered cell 2552 at
              its own lean 64761 (width 0.0, 20 genuine samples), and that one was won by population.
            - **THE FRAME PRICE OF THE AXIS, per budget** (closest approach; the band is ~1e-4 wide):
              cell 2552 delivered 1.3e-03 at 4 frames; **2561** 0.354 / 2.6e-03 / 8.9e-04 / 2.6e-05 at
              4/5/6/7; **2562** 0.430 / 2.2e-03 / 9.6e-04 / 4.9e-05; **2570** one-sign / 6.2e-02 /
              4.7e-03; **2581** one-sign / 1.0e-01 / 3.4e-03. Roughly an order of magnitude of approach
              per extra frame, so the lobe becomes a live lottery at 5-7 frames -- **three frames for
              +0.85 deg, against a budget of zero frames for ~1** (`[[tetrapush-frame-minimal]]`).
              `_notes/s93_frame_price.json`, `_notes/s93_reach_probe*.json`.
            - **THE ROOT CAUSE: `reach_radius` is a RADIUS and it was used as the SET.** `curve_seeds`
              sweeps a 94 u square box (`WALK_CAP * REACH_FRAMES + ROLL_NSPEED`) around `ref_entry` --
              the right conservative place to hunt a level curve, and not where a plan can put the
              entry. Link arrives at the speedF 17 cap on a fixed heading, so four held-stick frames
              reach a small curved cloud. NEW `harness/tetrapush/entry_reach.py` measures it instead:
              the fan already enumerates the cloud, so its convex hull is thirty lines of stdlib
              (`hull`/`contains`/`walk_cloud`/`reachable`/`reachable_quals`), and ONE facing-independent
              hull serves every configuration because `roll_entry` is a pure translation in the walk
              position. **The test is deliberately ASYMMETRIC** -- a hull off a coarse alphabet proves
              OUTSIDE and only suggests inside, so only the negative is used to prune. LOCKED
              `fixtures/courtyard_walk_hull_s93.json`; gate `tests/test_entry_reach.py`, whose licence
              assertion is that the hull CONTAINS the console-delivered clip's own entry.
            - **THE PASS CAN NOW BE SCOPED, which is what made a targeted pass affordable at all.**
              `search2` had no way to pick configurations and the s92 set is 40 of them (~6.7x the
              evaluation of every pass before it): `cells=` takes `lobe2` / `right` / `2561,2562` /
              `2564-2570` (`entry_score.parse_cell_spec`, resolved out of the measured window fixture so
              a re-scan moves every selector with it), and `frames=` caps the plan length, which is the
              objective as a prune rather than a ranking (`capped`; `j1`/`j2max`/`nbase` bound the
              fan's shape but not its plan LENGTH, so a bounded pass spent most of its evaluation on
              plans Dereck refuses outright). `cell_scope` reports what a spec missed AND which of the
              two kinds of miss it was -- not aimable at this camera (the camera lever) versus
              qualified and barren (the dead gap) -- because those are different facts. Gated
              `tests/test_entry_fan.py`, including the contract that scoping changes the COST and never
              an ANSWER.
            - **KB:** [`strategy/clip-exit-angle.md`](../../knowledge/strategy/clip-exit-angle.md) gains
              the frame-cost section and its status is corrected; the overturned pricing is MIGRATED to
              [`history/exit-angle-priced-without-its-frame-cost.md`](../../knowledge/history/exit-angle-priced-without-its-frame-cost.md);
              razor rule **13** (a positive is only as available as the budget it was found under --
              measure the reachable set, do not bound it; price a lever in the objective's own currency).
            - **SUPERSEDED BY SESSION 94 (the box above) on cell 2553 ONLY: the second-lobe negative and
              the frame pricing all stand, the "no usable width at the leans it arrives on" does not.**
              Those 180 dead-tail readings came from a band table that Newtoned every key from one seed;
              with the ladder the same cell reads 20 of 24 heaviest leans usable and the same 779130
              candidates report 34 near-misses at E[hits] 0.079. It was the ranking's seed, not the lean.
            - **WHAT IS STILL OPEN: cell 2553, as a LEAN problem rather than a candidate problem.** +9
              BAM is the whole axis at the floor and the pass above shows the fan reaches its residual
              zero; what it lacks is a usable band AT THE LEANS IT ARRIVES ON. So the next lever is the
              one the s92 handoff listed second and nobody has pulled: the band is jagged in `m351C`, the
              qualification runs at lean 0, and the 4-frame fan carries ~1040 distinct entry leans (the
              commonest being 65281 with 202 k candidates, then 6, 65151, 65021, 65411, and the delivered
              64761 with 95 k). Measure cell 2553's band ACROSS those leans, then aim the pass at the
              (lean, cell) pairs that have real width instead of at cells. `_notes/s93_lean_band.py` is
              that measurement for cells 2561/2562 already -- point it at 2553 and rank by candidate mass.
      - [x] **THE EXIT-ANGLE AXIS IS REAL AND IT IS ~10x WHAT SESSION 91 COULD SEE -- BECAUSE THE
            SEAM'S FACING WINDOW IS **TWO LOBES**, AND HALF OF IT HAD BEEN OUT OF SCOPE FOR ELEVEN
            SESSIONS BEHIND A NEGATIVE ARGUED FROM ONE SEED ENTRY (session 92).** The handoff asked for
            the clip map's rightward candidates to be verified against `ShoveCtx`. They were, the lead
            died, and the axis it was pointing at turned out to be somewhere else entirely.
            - **THE MAP LEAD IS DEAD, both halves of it.** Its `aim` column **is** the rounded bearing
              to the seam vertex -- computed at our own `old` it reads **40882** against the map's
              40881 -- so the join session 91 flagged never existed. And Link's cut position is not a
              steering wheel at all: **`CrrPos` pins `old` at exactly `WALL_R` from wall A and the brace
              has a 30 u basin.** Slide the entry ±30 u along the roll direction and `old` does not move
              one f32 ULP; ±1 u and all seven samples are the same bit-identical point; and the whole
              55-candidate deliverable population (4 plan lengths, 2 cells, every entry) holds **3
              distinct cut positions inside 0.035 u**. A map row 0.25 u away is geometry no roll into
              this corner can occupy. Gated `test_the_entry_does_not_move_links_cut_position_it_is_the_
              wall_brace`.
            - **WHAT THE ENTRY *DOES* MOVE IS THE PUSH, AND THAT IS THE WHOLE MECHANISM.** `resid`
              slides smoothly (~0.03 u per u of entry) while `old` stays bit-frozen, and the push
              **rotates** with the facing -- (-0.597,-0.138) at the delivered cell against
              (-0.119,-0.506) at +144 BAM -- supplying exactly the offset that puts a righter facing's
              ray back on the vertex. Which is also why **the lunge grows to the right** (49.74 ->
              50.31 u): session 91's "the lunge buys angle" is this same geometry, not a second lever.
            - **THE VARIABLE IS `travel`, AND ITS ATOM IS THE SINE-TABLE CELL.** `cM_ssin_s16` is
              `jmaTable[angle >> 4]`, so every facing in a 16 BAM cell leaves Link on a BIT-IDENTICAL
              heading: the exit angle has a hard **0.087891 deg** quantum and "the rightmost facing" is
              a category error -- ask for the rightmost CELL. Session 91 had the right variable (the
              cut ray is nailed to the seam; `travel` is what carries the fall) and went looking for it
              in the map's positions. Gated
              `test_the_exit_direction_is_quantized_to_the_sine_table_cell`.
            - **THE BUG, AND IT IS THE s90 LESSON ONE LEVEL DEEPER.** `locus_scan` is the strong form,
              but it MARCHES from one Newton solve at `ref_entry` and returns **0 stations** when that
              point reads `grad < 1e-3` -- having sampled the locus nowhere. **Leverage is a property of
              the ENTRY** (is the plowed Tetra still in Co range on the cut frame), so a righter
              facing, whose roll leaves her behind from a seed picked for a different facing, was
              scoped out by a verdict about the seed. `curve_seeds`/`curve_scan` seed off the
              residual-zero curve's OWN sign changes over the reachable box -- one vectorized sweep,
              cheaper than the march it feeds -- and `curve` is in `qualified`'s cache key (the s89
              lesson). Gated `test_the_second_lobe_needs_the_curve_to_find_its_own_seeds` +
              `test_no_leverage_is_a_property_of_the_seed_entry_not_of_the_configuration` (which
              REPLACES the overturned "most configurations have no locus" claim), and the s91-owed
              escalation gate landed too (`test_the_escalation_recovers_the_cell_one_station_reads_
              barren`).
            - **THE WINDOW, MEASURED (48 curve seeds per cell): TWO LOBES.** Cells **2548-2553** (the
              one every pass knew about; the delivered clip is 2552), a genuinely **dead gap 2554-2559**
              (0 live from ~48 seeds each -- a negative worth quoting), then a **second lobe 2560-2575**
              with dust thinning and most bands collapsing to zero width past 2563. All 8 sampled
              second-lobe stations are **real clips, lunge 49.66-50.31 u**, at WALKABLE entries inside
              the follow bar -- never the 0.15 u refusal shape. LOCKED
              `fixtures/courtyard_facing_window_s92.json`; gate
              `test_the_facing_window_fixture_is_two_lobes_with_a_dead_gap`.
            - **THE OTHER PLACE THE WEAK FORM LIVES IS BENIGN, and it was audited rather than assumed.**
              `BandTable` is `configuration_band` at one `ref` too -- but `stream_search` uses it only to
              RANK a near-miss, and `genuine` is ground truth that a band never vetoes, so no real hit
              was ever pruned by it. Only the CLAIMS needed fixing: `n_dead`'s "nothing genuine here, at
              any entry" and `test_entry_fan.py`'s "the productive facing window is 32 BAM".
            - **THE PRIZE, AND THE SCOPE IT BUYS.** Re-qualifying the alphabet on the curve seeding
              takes the pass's productive set **6 -> 40 configurations, 0 lost** (624 s), rightmost cell
              **2581 = +464 BAM**. The best cell that is *aimable at the frozen camera, carries a real
              band, and sits near the delivered entry* is **cell 2562: +160 BAM (+0.879 deg), band
              9.24e-05 -- WIDER than the delivered cell's own 6.28e-05 -- nearest station 21.0 u away**;
              cell 2561 is the near alternative (+144 BAM, band 8.60e-05, 13.9 u). Against session 91's
              reachable **+9 BAM**, that is ~10x on the axis Dereck priced at ~1 frame. The set is PINNED
              (`fixtures/courtyard_qualified_s92.json`) so the suite does not re-measure 624 s every run
              -- the `courtyard_entry_locus_s79.json` convention -- with a spot-check gate re-measuring
              one right-lobe configuration and one dead-gap facing against it.
            - **AND THE CAMERA AXIS REOPENS.** s83 priced `csangle` at exactly zero and closed it --
              correctly, against a 2-cell window the frozen aims already covered. Against a 22-cell
              window it is a live lever: cells 2550/2560/2563/2565/2566 are **not aimable frozen**, and
              one of those is the rightmost cell with a workable band. **A closure expires when its
              premise moves.** KB: NEW [`strategy/clip-exit-angle.md`](../../knowledge/strategy/clip-exit-angle.md),
              the overturned claims MIGRATED to
              [`history/entry-search-one-seed-negative.md`](../../knowledge/history/entry-search-one-seed-negative.md),
              the s83 camera bullet corrected in place on
              [`strategy/clip-entry-search.md`](../../knowledge/strategy/clip-entry-search.md), and
              razor rule **12** (a negative is only as strong as the set it was argued over; "I marched
              further" is not "I started somewhere else"; find seeds from the STRUCTURE).
            - **WHAT IS NOT DONE: no plan, and no cross-engine confirm.** Every second-lobe number is
              `ShoveCtx` dust at an entry, not a candidate -- there is no walk plan that lands on it, so
              `cross_engine.agree` cannot run and nothing has been near a console. **The open question
              is whether a FRAME-FLOOR (4-frame) plan exists at cell 2561/2562**, which is the pass the
              refreshed 40-configuration scope now makes possible and which session 91's bounded pass
              (stopped at 1056 s, 0 genuine / 40 near) never had in scope. `stream_search` picks the new
              scope up with no flag (it defaults `quals` to `qualified`), but **40 configurations is
              ~6.7x the evaluation of 6** -- so pass a SUBSET (the lobe's aimable cells) rather than
              running an s89-shaped pass wider; `search2` has no `facings` argument yet.
            - **SUPERSEDED IN PART BY SESSION 93 (the box above): the window measurements all stand,
              the PRICING does not.** That pass ran -- 779130 candidates, 7.01 M evaluations at the nine
              aimable second-lobe cells, 0 genuine / 0 near / 0 dead-tail -- because these stations were
              found by sweeping the `reach_radius` BOX, which is not the set a plan at the frame floor
              can reach. At that budget the axis is the first lobe, and the second costs three frames.
      - [x] **THE CONSOLE SETTLED THE Co-CENTRE SEAM -- AND NEITHER PORT WAS WRONG. IT WAS ONE ULP OF
            ANIM FRAME, BECAUSE A FRAME CTRL HELD A PYTHON `double` RATE WHERE `J3DFrameCtrl::mRate`
            IS f32. THE POPULATION GOES 51 -> **55 OF 55** AT FRAME FLOOR 4 (session 90).** The
            handoff named one console run and it came back bigger than the question it was asked.
            - **THE EXPERIMENT, AND IT COULD NOT COME BACK AMBIGUOUS.** Session 89 left two ports of
              Link's Co centre disagreeing by 1-2 ULP with every capture in hand blind to it, so the
              move was to find the candidate where the disagreement is not a ULP of position but
              **49.9665 u** of it: on `rejected[0]` of the s89 pass (plan `[0,186,98,1,200,108,4]`,
              m351C 64915) `ShoveCtx` and a body_cyl composite predict a 49.8582 u lunge out through
              the seam and the FootFK composite refuses to move Link at all (0.1534 u). Delivered at
              three truncate-and-read samples -- the cut, plus two PRE-CUT controls picked where the
              ports differ by 10 and by 1 ULP, so the reading is independent of the cut's amplitude.
              **All three 0-ULP on `body_cyl`, on BOTH actors, and it CLIPPED** (49.8582 u off `old`,
              at `(-1727.3033447266, -990.5955200195)`). LOCKED
              `fixtures/courtyard_centre_seam_s90_console.json`, which carries each sample's two
              pre-fix predictions -- without them it is three ordinary 0-ULP reads.
            - **THE ROOT CAUSE IS ONE LAYER UNDER THE SEAM, AND IT IS NOT A CENTRE.** Diffing the
              winning port against the losing one frame by frame: the CHAIN shape is innocent (0 ULP
              between one walk and two), the quats and scales are 0 ULP, and the whole gap is the
              **root joint's TRANSLATE, 3 ULP** -- which is the only component a frame value can move,
              since rotations are quantized s16 and scale is constant. The two engines were sampling
              `rollf` at two different f32 frames: `LandState.roll_frame` at 3.3000001907348633 and
              the pose driver's `fc0.frame` at 3.299999952316284. `FrameCtrl.set` stored the Python
              **double** `1.1` that `enter_roll` passes, where `J3DFrameCtrl`'s float members are f32
              -- and at roll frame 2.2 -> 3.3 the true f32 sum is an **exact tie**, so the double's
              deficit broke it DOWN where the hardware rounds half-to-even UP. One ULP of anim frame
              -> 3 ULP of root translate -> 1 ULP of the Co centre -> 1 ULP of Tetra -> the clip
              verdict. Fixed at the boundary that owns the type (`FrameCtrl.set` f32s all five
              members, so no caller can reintroduce a literal), NOT at `enter_roll`.
            - **WHAT IT BOUGHT.** The two ports now agree bit-for-bit on every roll frame; the
              DEFAULT composite -- no port swapping anywhere -- reproduces the console capture 0-ULP
              on both actors; and the pass re-confirmed on the fixed engine is **55 of 55 deliverable
              at frame floor 4**, against 51 and the same floor. The four rejections were the seam and
              they are all back. `fixtures/courtyard_entry_s90_hits.json`; the s89 file stays as the
              record of what the seam cost while it was open. 16 land goldens byte-identical.
            - **THE SHAPE OF THE BUG IS THE REUSABLE PART: two accumulators for one quantity.** The
              anim frame was tracked twice and nothing compared them, so they agreed on every frame
              where the f32 sum was not a tie and every gate that sampled a few frames passed. Each
              port had its own gate and neither could see this -- `test_body_co_native.py` compares
              FootFK's native fold against FootFK's own Python loop. `tests/test_centre_seam.py` (8)
              is now the gate that compares the two, plus the console capture and the tie arithmetic
              itself; `tests/test_cross_engine.py` asserts the blocked class is EMPTY every run, since
              a filter that starts rejecting again means a regression. KB: NEW
              [`model/anim-frame-is-f32.md`](../../knowledge/model/anim-frame-is-f32.md), the settled
              section of [`mechanics/link-co-centre.md`](../../knowledge/mechanics/link-co-centre.md#the-two-ports-and-what-was-actually-between-them),
              the open-question narrative MIGRATED to
              [`history/co-centre-two-ports.md`](../../knowledge/history/co-centre-two-ports.md), and
              razor rule **11** (a code seam can be a SYMPTOM -- ask what each side is GIVEN before
              asking which side is right; design the run so it cannot come back ambiguous; a small
              measured cost is not evidence the cause is small).
            - **AND THEN THE FRAME-MINIMAL CLIP WENT TO CONSOLE, IN ONE DELIVERY.** The candidate the
              fix unlocked: row 0 of the s90 list, a **4-frame** walk-up (plan
              `[0,208,110,2,169,192,2]`, aim `[82,186]`, facing 40841, thrust 15, m351C 64761, entry
              `(-1531.1784667969, -781.7215576172)`, resid +6.2429e-05) -- **one frame under the s88
              delivery, and rejected by the cross-engine filter until this session**. Console at the
              cut is bit-identical to the prediction, **49.7368 u off `old` and out through the
              seam**, with Tetra bit-exact and stt 3; five frames later `daPyProc_FALL_e` at
              `(-1751.6227, -1015.5969)`, off the courtyard floor, and Tetra STILL 0-ULP there. So
              milestone 2's verdict column is console-confirmed **at the frame floor**, not merely at
              some deliverable plan. LOCKED `fixtures/courtyard_clip_s90_console.json`; gate
              `tests/test_clip_frame_minimal.py` (6).
      - [x] **THE RE-RUN CAME BACK BIT-IDENTICAL, AND THAT WAS THE RESULT: THE 0.75 ATTACK GATE
            NEVER REACHED THE PASS, BECAUSE THE PRODUCTIVE-CONFIGURATION CACHE DID NOT KEY ON IT.
            ALSO: THE FOUR CROSS-ENGINE REJECTIONS ARE NOT FOUR CANDIDATES, THEY ARE **ONE CODE
            SEAM** -- TWO PORTS OF LINK'S Co CENTRE THAT AGREE TO 1-2 ULP (session 89).** The handoff
            asked for the pass re-run on the corrected alphabet plus one diagnosis each on the two
            blocked candidates. Both came back bigger than asked.
            - **THE PASS RE-RUN MEASURED NOTHING, AND FINDING THAT OUT IS THE SESSION'S MAIN RESULT.**
              `search2 2 1,2 1 6 2`, 5000 s, and the output was **bit-identical to session 87's**:
              same 39291750 candidates, same 1950 near draws, same E[hits] 4.547, the same **81
              genuine scorings**, every entry and residual to the bit, and not one aim byte pair
              changed. The cause: `entry_score.qualified` caches the productive (facing, thrust) set
              -- and the aim bytes that reach each one -- to `_generated/s81/qualified.json`, and its
              key validated `cells`/`csangle`/`thrusts` and **not the threshold**. So the pass was
              handed a qualification written before session 88 existed, in which **2 of the 3
              configurations carried aim `[95,168]`, msd 0.5705 -- the exact aim of the delivery that
              sheathed the sword**, and 57 of the 81 scorings had an aim that cannot roll.
              `msd_min` is in the key now and a pre-gate cache is refused. **Refreshed, the
              productive set really does move: facing 40834 is gone and 40841 takes its place**
              (thrusts 14+15, aim `[82,186]` msd 0.9817, both zero-width bands), while 40820 keeps
              thrust 15 at aim `[85,182]` msd 0.8891 -- the aim that rolled on console -- with a
              3.205e-05 band. Gate
              `tests/test_attack_threshold.py::test_the_gate_reaches_the_PASS_and_not_only_the_alphabet`;
              razor rule 10 (**a re-run that reproduces the previous run exactly is a RESULT, not a
              relief** -- diff the populations before reading the yield).
            - **THE CORRECTED PASS: THE ATTACK GATE COSTS THE AXIS NOTHING, AND THE FRAME FLOOR GOES
              BACK TO 4.** Re-run on the fixed qualification (4701 s, same 39291750 candidates): the
              population is *still* the same 81 walkable scorings / 55 draws at the same entries and
              residuals, 1950 near, E[hits] 4.547 -- because **the physical atom is the sine-table
              CELL, and 40834/40841 are both cell 2552**. Dropping the angle only moved the cell's
              REPRESENTATIVE, from `[95,168]` msd 0.5705 (sheathes) to `[82,186]` msd 0.9817 (rolls).
              So **0 of the 81 scorings now carry an unrollable aim, against 57**; all 55 draws
              confirm (**0 dropped at the A-press**, against 36); and with the cross-engine filter in
              the same loop **51 of 55 are deliverable at frame floor 4**, against s88's 15 at 5. The
              four rejections are the same four, and they are the Co-centre seam below. Session 88's
              "36 of the 55 are dead, floor 4 -> 5" was a property of the PINNED ROW re-confirmed
              against the stale representative, never of the candidates -- corrected on
              [`mechanics/roll-attack-threshold.md`](../../knowledge/mechanics/roll-attack-threshold.md)
              and in [`history/aim-alphabet-whole-grid.md`](../../knowledge/history/aim-alphabet-whole-grid.md).
              Pinned `fixtures/courtyard_entry_s89_hits.json` (rejected rows now carry the WHOLE hit,
              so a rejection is re-runnable from the file); gate `tests/test_entry_fan.py`. The
              frame-minimal is **plan `[0,208,110,2,169,192,2]`, aim `[82,186]`, facing 40841, thrust
              15, m351C 64761, entry `(-1531.1784667969, -781.7215576172)`, resid +6.2429e-05, 4 walk
              frames, lunge 49.7368 u**.
            - **THE CROSS-ENGINE PRE-FLIGHT IS IN THE SCORING LOOP NOW**, which is what the handoff
              asked for and where session 88's 4-of-19 failure rate said it belonged. New tracked
              `cross_engine.py` (session 88's composite path verbatim, plus `agree`/`blocked`), wired
              as `confirm_hits(cross_engine=True)` and `entry_fan confirm <hits> xengine`; only
              confirmed + DTM-clean hits are rolled out, ~0.4 s each. It reproduces s88's
              55 -> 19 -> 15 at frame floor 5 in **10 s and two commands**, where the session before
              needed three scripts. Gate `tests/test_cross_engine.py` (12).
            - **AND THE REJECTIONS IT MAKES ARE ONE SEAM.** The composite computes Link's Co centre
              with `foot_fk.body_co_center` (rebuilt from the pose driver's STORED OLD POSE) and the
              search bakes `body_cyl.roll_co_chain_consts` (the `rollf` anim sampled directly). Same
              quantity, two routes, **1-2 ULP apart on isolated frames** -- and nothing gated them
              against each other, because `test_body_co_native.py` gates FootFK's native fold against
              FootFK's own Python loop. Census over the s88 population: **4 of 4** cross-engine
              rejections sit on a frame where the two differ, **0 of 36** ATTACK-gate drops do, 1 of
              15 kept does. Causal: put the composite on the search's centre and **all four agree**,
              two of them flipping from the composite refusing to move Link (0.1534 u) to the
              identical **49.8582 u** lunge. Cost: 15 of 19 deliverable becomes 19 of 19, frame floor
              **unchanged at 5**.
            - **WHICH PORT IS RIGHT IS OPEN, AND NEITHER ENGINE WAS CHANGED.** Both console captures
              fall on candidates where the two paths agree -- measured, not assumed: swapping the
              centre changes the composite on **0** frames of the s86 console roll -- so neither
              capture discriminates. `roll_co_center` is console-gated 0-ULP for these leans;
              `body_co_center` is live-pinned only to a **<=6.1e-5 u tolerance**, about 1 ULP at
              these magnitudes. Suggestive, not evidence. **THE EXPERIMENT: deliver a BLOCKED
              candidate** -- `ShoveCtx` and a body_cyl-composite predict 49.8582 u out through the
              seam, the FootFK composite predicts 0.1534 u and no clip; one console run settles it
              for the whole population. `fixtures/courtyard_centre_seam_s89.json` +
              `tests/test_centre_seam.py` (6); KB
              [`mechanics/link-co-centre.md`](../../knowledge/mechanics/link-co-centre.md#the-two-engines-and-the-1-2-ulp-between-them),
              razor rule 9 (**"a property of the candidate" is a code seam you have not named yet**).
      - [x] **THE CONSOLE CLIPPED. `genuine` IS A MEASURED NUMBER NOW -- MILESTONE 2's VERDICT COLUMN
            IS CONSOLE-CONFIRMED. IT TOOK TWO DELIVERIES, AND THE FIRST ONE FOUND A GATE THE MODEL
            NEVER HAD: AN A-PRESS BELOW `mStickDistance` 0.75 IS NOT A ROLL, IT SHEATHES THE SWORD --
            SO **36 OF THE 55 COULD NEVER HAVE ROLLED**, AND THE CROSS-ENGINE DIFF THEN REJECTED 4
            MORE (session 88).** The handoff said to spend ONE delivery on the frame-minimal hit and
            read the cut frame first. That delivery came back with Link WALKING and Tetra untouched,
            which is a stranger result than a missed clip and a cheaper one to diagnose.
            - **THE FIRST DELIVERY: THE PRESS DID NOTHING.** Not a roll that went wrong -- MOVE at the
              sampled frame, the walk facing continued past the A-press, and Tetra **bit-identical**
              to her pre-roll position, so Link never reached her. Decomp-first named it in one read:
              `setDoStatusBasic` (`d_a_player_main.cpp:2220`) sets `dActStts_ATTACK_e` -- the ONLY
              status `checkNextActionFromButton` (4318) turns into `procFrontRoll_init` -- solely for
              `mStickDistance > m_HIO->mBasic.m.field_0x1C`, and `daPy_HIO_basic_c0::m` puts that at
              **0.75**. At or below it the same press is `dActStts_PUT_AWAY_e` (2218) and the sword
              goes away. The delivered aim `[95,168]` decodes to **0.5705**; s86's `[85,182]`, which
              rolled, is **0.889**. Two deliveries, one each side of the threshold.
            - **THE MODEL GATED THE ROLL ON THE 0.05 LOCOMOTION FLOOR** in both engines. Fixed at the
              source: `LandState.ATTACK_MSD_MIN` (hio.py, beside the other `mBasic` fields), the
              dispatch in `state.py` latching a new sticky `attack_blocked` the way a wall-suppressed
              roll latches `sidle_blocked` (the sheathe proc stays unmodelled), and BOTH native
              `_anmc.pyx` dispatch sites. New `two_roll.roll_aim_fan` is the aim alphabet's real
              membership test; `entry_search.aim_alphabet` defaults to it (`msd_min=0.0` still
              reproduces the falsified one for diagnostics). Land goldens byte-identical.
            - **WHY IT SURVIVED NINE SESSIONS, and it is a gating lesson.** s80 removed the alphabet's
              magnitude floor on the measurement "every aim in the window fires the roll and lands on
              the facing it commands" -- measured on a sim whose roll gate was the 0.05 floor, so it
              could only agree. `confirm_entry`, whose entire job is "does Link actually roll from
              here", replays a real A-press **on that same engine**. A gate is evidence only about
              what it does not share with the claim. Worse, the alphabet dedupes the byte grid by
              decoded ANGLE keeping the FIRST pair in grid order -- typically a shallow interior one
              -- so widening did not add deep aims, it REPLACED representatives with shallow ones.
              MIGRATED to `knowledge/history/aim-alphabet-whole-grid.md`; truth in
              `knowledge/mechanics/roll-attack-threshold.md`.
            - **WHAT IT COSTS THE AXIS.** The seam window's alphabet goes 81 aims / 49 cells ->
              **60 / 45**; facing 40834's cell drops out entirely because NO byte pair reaching that
              angle clears 0.75. Both PRODUCTIVE cells (2551/2552) are still reachable, so the camera
              conclusion is unchanged. Of the pinned 55: every one still SCORES genuine at its
              recorded residual to the bit (the razor did not drift), **36 cannot roll**, 19 confirm,
              frame floor 4 -> **5**.
            - **THEN THE CROSS-ENGINE DIFF REJECTED 4 MORE, AND ONE OF THEM WAS THE NEXT CANDIDATE IN
              LINE.** s87 made `ShoveCtx` and the composite agree for ONE hit and gated it; run the
              same diff per candidate and agreement is a property of the CANDIDATE. Two of the 19 have
              the composite **blocking** the very lunge `ShoveCtx` scores genuine (0.15 u where the
              prediction has 49.86), two more diverge by 1 ULP pre-cut -- and the frame-minimal
              survivor was one of the blocked pair, i.e. exactly what a third delivery would have been
              spent on. It costs one rollout and no console runs, so it is now a pre-flight:
              `_notes/s88_agree.py`, pinned into `fixtures/courtyard_entry_s88_hits.json`
              (**15 deliverable, frame floor 5**). Razor rule 7.
            - **THE SECOND DELIVERY CLIPPED.** Plan `[1,196,92,1,202,152,3]`, aim `[85,182]`, facing
              40820, thrust 15, m351C 64652, entry `(-1517.9427490234, -765.2719116211)`, resid
              -5.454e-06, 5 walk frames, cut at plan frame 102. Every pre-flight passed first
              (handover 0-ULP, cut at `b_log + 1`, 18 plan frames 0-ULP cross-engine on both actors,
              delivered bytes bit-identical) and then the console put Link at
              **(-1727.3033447266, -990.5955200195) -- bit-identical to the prediction, 49.8582 u off
              `old`, out through the seam** -- 0-ULP on x, z, facing, proc, speedF and on Tetra, who is
              still stt 3 and frozen. Five frames later the console is in `daPyProc_FALL_e`: off the
              floor, which is what a seam clip IS. `fixtures/courtyard_clip_s88_console.json` LOCKED,
              gate `tests/test_clip_delivered.py`. Nothing past the cut is claimed -- the composite is
              flat-ground and the console has left the floor.
            - **NEXT: RE-RUN THE PASS ON THE CORRECTED ALPHABET** (`search2 2 1,2 1 6 2`, ~4997 s).
              The 15 in hand are enough to deliver from, but they are a FILTERED old population, not a
              measurement of the axis: the corrected alphabet changes which byte pairs represent each
              cell, so the walk endpoints -- and therefore the entries -- are different candidates.
              Run `two_roll contain` and the new `tests/test_attack_threshold.py` first, then score
              with the cross-engine pre-flight in the loop rather than after it.
      - [x] **THE CLIP FRAME IS BIT-EXACT NOW, BOTH ACTORS, IN BOTH ENGINES -- AND THE VERDICT THE
            CONSOLE FALSIFIED IS THE VERDICT THE MODEL NOW RETURNS. THE UNPRICED TERM WAS **TWO**
            TERMS IN **TWO DIFFERENT ENGINES**: TETRA HAD NO BG PASS IN THE COURTYARD TRACKING, AND
            THE SEARCH'S BAKED Co CENTRE HAD NO `body_chn` TWIST. **RE-SCORING THE 49 KEEPS 7**, AND
            THE FRAME FLOOR MOVES 4 -> 5 (session 87).** The handoff named step 1 (give her the wall)
            and step 2 (close the residual 0.15 u, suspecting the push split). Step 1 was right and
            one line long. Step 2 was a different bug in the other engine, and the thing that found
            it was diffing the two engines against each other -- which nothing had ever done.
            - **TETRA'S BG PASS, and the whole xfail frontier XPASSED on it.** `from_f0.FreeRun`
              gains `walls_tetra=`, running her `mObjAcch.CrrPos` (R 50 / half-H 30) at the same
              point in the frame `npc_zl1.Zl1FollowState.step` does -- after `posMove` consumes the
              CC recoil, `speed_y` 0 on the flat floor. Every previously-open console sample went
              **0 ULP on both actors in one change**, including the cut frame: the composite blocks
              the lunge exactly as the game did (0.16 u off `old`, not 49.97).
            - **THE 0.15 u WAS NOT THE PUSH SPLIT.** With her walled the COMPOSITE is console-exact
              at the cut frame, so the 0.15 u belonged to the other engine. Diffing `ShoveCtx`'s
              trace against the composite's plan frames: both actors agree for three steps, then
              diverge EQUAL-AND-OPPOSITE from the first contact frame -- the push-split signature
              again, and again not the split. Subtracting Link's own position difference leaves a
              CHAIN difference that decays to exactly 0 by roll frame 6, which is the shape of a
              lean, not of a morf (the morf counter reads 0 all through).
            - **THE TERM: the `body_chn` counter-twist.** `body_cyl.roll_co_center` /
              `roll_co_chain_consts` applied the `setWorldMatrix` base lean and NOT the
              `jointBeforeCB` `Rx(-mBodyAngle.z)` twist at `CL_JNT_BODY_CHN`, which takes the
              **POST-update** lean -- the session-16 timing law `foot_fk.body_co_center` has run
              since it was found, which is why the composite was right all along and the search was
              not. Twisting reproduces the composite's posed centre 0 ULP on every roll frame.
              `body_cyl.co_leans(link)` returns the (base, twist) pair and all four schedule bakers
              plus `cc_stepper.link_co_center` now pass both. New KB page
              `knowledge/mechanics/link-co-centre.md`; the overturned claim MIGRATED to
              `knowledge/history/co-centre-body-chn-twist.md`.
            - **WHY IT HID FOR A YEAR, and it is a gating lesson not an FP one.** `euler_to_quat`
              halves the angle into `jmaSinTable[(u16)a >> 4]`, so a twist below ~30 BAM rounds to
              the identity. `fixtures/hyrule_roll_lean.json` -- the capture built to isolate the
              lean, and the one that recorded "adding the body_chn quat breaks it" -- never exceeds
              **28** past its exempt entry frames, so it cannot decide the term in either direction;
              and the "breaks it" measurement had fed the twist the OLD lean. At the lean a roll off
              a curved approach carries (`m351C >> 1` = -388) the term is worth **~0.35 u** of
              centre, ~0.17 u of push per frame, compounding through the plow into the 0.15 u.
              `tests/test_body_cyl.py` now asserts that fixture's own lean bound, so a future
              capture with a real lean makes the gate demand the term instead of permitting it.
            - **THE 49, RE-SCORED: 7 SURVIVE.** `entry_score.rescore` (+ `entry_fan rescore` CLI)
              re-sweeps a finished pass on the engine as it stands. The 42 that fall are not
              near-misses that drifted -- every one lands past **-1e-3**, decades outside a 1.2e-4
              window -- and the survivors' residuals are UNCHANGED to the bit, because their leans
              are the small ones. All 7 still `confirm_entry` clean and DTM-deliverable. The
              frame-minimal survivors are **5 frames** (`[0,188,174,2,166,64,3]` aim `[95,168]` and
              `[0,174,184,1,194,90,4]`), against the 4-frame hit the console falsified. Pinned
              `fixtures/courtyard_entry_s87_rescored.json` + `tests/test_entry_fan.py`.
            - **THE PASS RE-RUN: THE YIELD IS UNCHANGED AND THE POPULATION IS NEW.** s85's exact
              scoping (`search2 2 1,2 1 6 2`) on the fixed engine, 39.3 M candidates / 117.9 M
              evaluations / 4997 s: **1950 near draws** (s85: 2007), **E[hits] 4.547** (4.638),
              **0.2417 near/family** (0.2487) -- and **55 DISTINCT GENUINE DRAWS from 81 walkable
              scorings of 81** (s85: 49), **55 of 55 confirmed by a real A-press and 55 of 55
              DTM-deliverable**, five with gap exactly 0.000e+00. **The frame floor is 4 again**
              (three 4-frame plans, all facing 40834 / thrust 15 / aim `[95,168]`; the best is
              `[0,208,110,2,169,192,2]`, resid +6.243e-05). So the axis did not get harder -- what
              changed is WHICH candidates are genuine: **only 7 of s85's 49 are in the 55**, which is
              the re-score's "lower bound, not a measurement" caveat measured. Pinned
              `fixtures/courtyard_entry_s87_hits.json` (+ the overlap) in `tests/test_entry_fan.py`;
              re-sweeping all 55 is 0.1 s and replaying them 2.5 s, so the list itself is gated.
              **Scope note:** the ONE-segment coarse fan did thin (a stride-16 `iter_fan` pass now
              finds no near-miss at all, which is why `test_dropping_the_cap...` moved to stride 4);
              that is a different population from the two-segment pass and must not be read as the
              axis.
            - **THE GATE THAT WAS MISSING, now standing.** `tests/test_clip_console.py` diffs
              `ShoveCtx` against the composite frame for frame on both actors, and both against the
              console log -- 16 tests, no xfails. Two engines each gated against their own fixture
              and never against each other is exactly how a term present in one and absent from the
              other survives.
            - **NEXT: SPEND ONE CONSOLE DELIVERY on the frame-minimal hit of the 55**,
              `[0,208,110,2,169,192,2]` / aim `[95,168]` / thrust 15 / 4 delivered frames. With both
              engines console-exact on every frame of the roll through the cut, that delivery finally
              tests `genuine` rather than the model -- which is exactly what s86's could not do.
              Reuse the s86 composite path unchanged (append to the s78 log, `deliver.py`
              truncate-and-read); the entry half is locked and gated, so the decisive sample is the
              cut frame. **Do not widen the fan** -- the axis is re-measured now and 55 confirmed
              deliverable tickets is not the bottleneck.
      - [~] **THE COMPOSITE IS ON CONSOLE, AND IT SPLIT IN TWO: THE HANDOVER IS PERFECT AND THE CLIP
            DID NOT HAPPEN. THE ENTRY, THE 17-FRAME ROLL AND EVERY WALL BRACE REPLAY **BIT-EXACT**
            ON THE REAL GAME -- LINK'S PRE-CUT POINT IS `ShoveCtx`'s OWN `old` TO THE BIT -- AND THEN
            THE LUNGE DOES NOT THREAD THE SEAM. THE UNPRICED TERM IS **TETRA AT THE CUT FRAME**: THE
            CLIP ROLL PLOWS HER ~100 u INTO THE BACK WALL, AND **ONE f32 ULP OF HER FLIPS `genuine`**
            (session 86).** The handoff called the console confirm the only unpaid risk left. Paying
            it bought both the confirmation the entry search wanted and the reason its verdict
            column cannot be trusted yet.
            - **THE ENTRY CONFIRM -- 9 of 9 samples 0-ULP** (`fixtures/courtyard_entry_s86_console.
              json`, gate `tests/test_entry_console.py`, 24 tests). The frame-minimal deliverable hit
              of the 49 -- plan `[0,200,144,1,195,164,3]`, aim `[85,182]`, 4 walk frames -- appended
              to the s78 console log and delivered as one 86-frame movie. n=78 is the control (the
              frame `courtyard_plan_s73_console.json` already measured); n=79..86 are the entry
              frames. Every one is bit-exact on Link x/z, `proc`, `facing`, `travel`, `speedF`,
              **`m351C` and `nspeed`** -- the two a `ShoveCtx` is keyed on, read live for the first
              time (`deliver.read_link` now carries them) -- and on Tetra x/z, who stays stt 3 and
              **bit-frozen every frame**, which is the premise the whole entry search rests on. So
              the console rolls from the entry the walled engine was scored at, exactly.
            - **THE CLIP -- IT DID NOT.** Extending the same log to the thrust (UP+B on plan frame
              100, the cut dispatching on 101) puts the console 0.16 u from `old` where the
              prediction puts it **49.97 u away, through the gap**. Everything up to the cut is
              right: `old` is bit-identical to `ShoveCtx`'s, and the cut fires on the predicted
              frame at the predicted facing and roll phase. `fixtures/courtyard_clip_s86_console.
              json` + `tests/test_clip_console.py` (8 console samples; the model gaps `xfail(strict)`
              on a contiguous suffix, so closing one XPASSes and fails the suite).
            - **THE PER-FRAME DIFF NAMED IT, AND IT NAMED TETRA FIRST.** Link is 0-ULP through plan
              frame 89 and **Tetra diverges at 91 while Link is still exact**. Her console z pins at
              **-940.25561523** for five frames = the back-wall plane **-990.255615** plus her **R
              50** -- a WallCorrect brace, read straight off the mesh. The rollstab coupled engine
              reproduces that pin exactly; the courtyard `from_f0` carries her as a bare XZ plow
              point with NO BG collision and drives her **53 u through the wall** by the cut frame.
            - **AND THE PRICE OF HER IS ONE ULP.** The entry search priced the precision it needs in
              the variable it SWEEPS (~1e-4 u of entry) and never priced the other terms of the same
              residual. Perturbing her: **one f32 step of her x, 1.221e-4 u, takes `genuine` True ->
              False**. The razor is thinner than her own storage grid, and the best model of her
              cut-frame position is **0.15 u (~1200 ULP)** off the console read -- so the verdict is
              not wrong so much as UNDECIDABLE at current fidelity, for all 49 and not just this
              one. New KB page `knowledge/strategy/razor-prices-every-term.md`; the wall brace is a
              console-measured upgrade on `knowledge/mechanics/tetra-follow.md`.
            - **ALSO ESTABLISHED, cheaply:** the whole composite runs in ONE engine now -- the wired
              delay-1 `FreeRun` with `TA.WALLS` attached to `link._walls` -- which removes the
              schedule-step-vs-plan-frame mapping that cost this session a live run, and attaching
              those walls leaves **every console-confirmed frame byte-identical**, i.e. the herd
              provably never touches a wall (`objective` rule 4, asserted since s60, now measured).
              The delivered composite is also clean of the `dtm_make` extreme clamp on every byte.
            - **NEXT: TETRA THROUGH THE CLIP ROLL, to the standard the herd got.** Give her the
              `npc_zl1` `CrrPos` pass in the courtyard tracking (the xfail frontier is exactly that),
              then close the residual 0.15 u at the cut frame -- her z is already within 0.03 u and
              braced, so the error is in the SLIDE along the wall, i.e. the push magnitude during the
              roll. Only then does `genuine` mean anything, and the 49 are re-scored rather than
              re-searched. Widening the fan is now certainly the wrong move: it buys more tickets in
              a currency whose value is unmeasured.
      - [~] **A CANDIDATE IS A PROMISE, AND AUDITING THE ONES THE FAN MAKES TOOK THE CONFIRM RATE TO
            100%: THE PROC PRUNE IS IN, AND THE WIDE PASS RETURNS **49 DISTINCT ENTRIES, ALL 49
            CONFIRMED BY A REAL A-PRESS AND ALL 49 DTM-DELIVERABLE** (against session 84's 23 draws /
            20 confirmed). THE AXIS IS NOWHERE NEAR SATURATED -- A STRIDE-4 PASS WOULD HAVE FOUND
            **8 OF THESE 49** -- AND 4 DELIVERED FRAMES IS NOW A MEASURED FLOOR RATHER THAN A BEST-OF
            (session 85).** The handoff asked for the prune and then a wider run. The prune is what
            made the run's yield trustworthy; the run is what priced the axis honestly.
            - **THE PRUNE, and it is the game's own condition rather than a threshold.** An endpoint
              is a claim that Link ROLLS from it, and the fan checked only where he stood (the 230 u
              follow bar) and how fast (the walk cap). `checkNextActionFromButton` also needs a proc
              the ATTACK roll dispatches from, which is `tww_sim/land/constants.ROLL_FROM` = MOVE /
              ATN_MOVE -- now ONE canonical tuple that `state.py`'s dispatch and `entry_fan.
              _is_rollable` both read, so the search cannot drift from the physics it predicts. The
              endpoint's own `state` IS the A frame's dispatch proc (the aim is delivered on the
              endpoint frame and acted the next), so the prune needs no lookahead. It drops **~7%**
              of endpoints, saves NO fleet time -- the frames are stepped before it reads the proc --
              and is exactly s84's three unconfirmed draws, all of which read `procs [24, 24, 6, 6,
              6]`. Gated against a real A-press BOTH ways, cross-engine (the wired Python replay's
              proc at that frame against the native core's). OFF in `iter_fan`, whose key-AND-value
              equality with `walk_fan` is a contract. New KB page
              `knowledge/strategy/search-prune-the-dispatch.md`.
            - **THE RESULT.** `search2 2 1,2 1 6 2` -- S1 stride 2 (3355 draws), j1 (1,2), S2 stride
              1, j2max 6, 2 bases -- **8069 prefix families, 39.3 M candidates, 117.9 M evaluations,
              5086 s**: **2007 near-miss draws, E[hits] 4.638, and 49 DISTINCT GENUINE DRAWS from
              259 walkable scorings**, three best gaps exact **0.000e+00**. `confirm_entry` replays
              **49 of 49** clean and none of them is rewritten by `dtm_make`. Output
              `_generated/s85_search2_a2_j1-2_b2.out`, hits + `..._confirmed.json` under
              `_generated/s81/`.
            - **SCOPED OFF THE PREVIOUS PASS'S HIT SHAPE, not off the axes nominally open.** s84's
              20 confirmed hits sit **17 at j1=2** and every one at 4-7 total frames, so widening j1
              or the base count buys longer plans on a 5x-less-productive prefix -- and frames are
              the objective. The budget went on a FINER PREFIX GRID at SHORT prefixes instead, and
              the previously-unswept **j1=1 returned 33 of the 49 draws**, more than j1=2's 16, while
              being the shorter prefix. A first scoping (`2 1,2,3 1 6 4`) was killed at 4 min when
              its own live trace projected 5.7 h: short prefixes realize **77%** of their asked
              junctions against s84's 34%, so the realized-family fraction is a function of j1 and
              does not carry between scopings.
            - **THE AXIS IS NOT SATURATING, and the sub-grid readout says so without a second pass.**
              A fine alphabet CONTAINS every coarser one, so restricting this pass's own families to
              a coarse sub-grid reads the coarse pass's yield straight off (`entry_score.
              near_families` / `subgrid_rate`, printed per stride). Measured on the genuine draws:
              **stride 4 -> 8 of 49, stride 8 -> 1, stride 16 -> 0.** Per family the honest
              comparison is s84's 0.184 draws/family against this pass's **0.2487** -- 1.6x the
              families for 2.17x the draws, still better than linear.
            - **AND THE TAIL MARGINAL LIED AGAIN, in both directions this time.** It read 0.50 early,
              fell to 0.20 a third of the way in, and finished at **1.10** -- the pass ended INSIDE a
              productive band. Stopping on the mid-pass dip would have thrown away most of the yield.
              Watch `subgrid_rate`, never the tail (s84's lesson, now with a counter-example).
            - **4 FRAMES IS A FLOOR, not a best-of.** The pass swept the 2- and 3-frame shapes
              (n0 0/1 x j1 1/2 x j2 1) and returned nothing genuine there; the two 4-frame entries
              are `[0,200,144,1,195,164,3]` (NEW) and s84's `[1,180,184,2,180,183,1]`, reproduced.
              The one 4-frame shape still unswept anywhere is n0=2, j1=1, j2=1.
            - **TWO MORE PROMISES AUDITED AT THE SAME SEAM, both of which had been luck.**
              `entry_fan.delivered`/`survives_delivery` check a plan's bytes against `dtm_make`'s
              extreme clamp on the DECODE (a clamped extreme is usually the same draw), and
              `confirm_hits` carries a `deliverable` column and ranks an undeliverable hit last --
              the held sticks are interior BY DESIGN, the aims only by luck. And `BandTable.save`
              was dumping the 4 MB cache straight onto the live path: a second pass read a torn one
              and died in `json.load`, and killing a pass mid-save would have poisoned it for every
              later run. Atomic now (temp + `os.replace`), self-healing on a damaged file.
            - **`entry_fan.py` SPLIT** at the fan-vs-scoring seam s84 named: 880 lines -> 547 + a new
              `entry_score.py` at 471, re-exported name for name and gated on identity.
            - **NEXT: the out-of-band DTM CONSOLE CONFIRM.** Every configuration axis is closed by
              measurement and the candidate axis has produced far more entries than can be spent;
              what nothing has tested is the COMPOSITE, since the offline result is stitched from two
              engines (the wall-less courtyard `FreeRun` hands over an entry, the walled `ShoveCtx`
              decides `genuine`). Widening further is buying lottery tickets with 49 unredeemed ones
              on the table.
      - [~] **THE ENTRY SEARCH HAS HITS. THE TWO-SEGMENT AXIS DID NOT SATURATE -- IT PAID BETTER
            THAN LINEAR -- AND THE PASS THAT FOUND THEM IS THE ONE s83 PRICED AT 3 h, RUN IN 46 min
            BECAUSE THE FAN'S OWN HELD-STICK ALPHABET WAS 5.75x REDUNDANT. 20 DISTINCT ENTRIES
            CONFIRMED BY A REAL A-PRESS; THE FRAME-MINIMAL ONE IS **4 DELIVERED FRAMES** (session
            84).** Four sessions of closing configuration axes ended with the one axis still priced
            nonzero, and running it wide worked.
            - **THE RESULT.** `search2 4 2,4,6 1 6 4` -- S1 stride 4, j1 (2,4,6), S2 stride 1,
              j2max 6, 4 bases -- **5038 prefix families, 15.8 M candidates, 47.4 M evaluations,
              2776 s**: **925 near-misses (925 distinct) and 118 genuine scorings = 23 DISTINCT
              DRAWS at 20 entries**, best gaps two exact **0.000e+00**. `confirm_entry` replays
              **20 of the 23** clean. Best is `plan [1,180,184,2,180,183,1]` aim `[85,182]` facing
              40820 thrust 15, entry `(-1531.49853515625, -781.9691162109375)`, resid +9.021e-05,
              **4 frames**. Output `_generated/s84_search2_a4_b4.out`, hits +
              `..._confirmed.json` under `_generated/s81/`.
            - **THE 5.75x: THE FAN'S ALPHABET WAS THE BYTE GRID, AND THE PHYSICS READS THE DECODE.**
              A held stick reaches the walk only through `main_stick_decode`, so two byte pairs with
              one `(angle, msd)` bake a bit-identical walk -- gated over the widest classes. The
              octagon clamp and the dead zone make that the common case: **65536 byte pairs are
              11405 draws**, one class holding 1944, and the classes that survive the walk-cap prune
              are the saturated ones with the most members. `stick_alphabet` collapses both segments;
              s83's own reference pass then reproduces **gap for gap in 48 s against 220 s**, 25x
              fewer writes streamed. This is s83's sine-cell lesson applied to the alphabet the
              search SPENDS rather than the one it scores -- and it was worth more.
            - **THE AXIS DID NOT SATURATE.** Corrected reference: 94 families -> 12 draws
              (0.128/family). This pass: **5038 families -> 925 draws (0.184/family)** -- 53.6x the
              families for 77x the draws, the first axis since s80 to pay at better than linear. The
              handoff's "192 families -> 13" was the ASKED count; the alphabet collapses to 57 draws
              and 45% of junctions never form one, so the real reference was 94 -> 12.
            - **DO NOT READ THE TAIL MARGINAL AS SATURATION.** The stick grid is enumerated x-major,
              so a sweep crosses the productive direction band ONCE: this pass's marginal near/family
              read 0.00 for its first 300 families, peaked at 0.86, and finished at 0.13. The tail is
              the number a pass prints when it ends and the least informative of the three. The
              honest test is two whole-circle alphabets compared on draws per family.
            - **THREE COUNTING FIXES, all of which moved a headline number.** (1) Near-misses now
              carry identity and dedupe on the DRAW: s83's "13" is **12** -- one draw was reached by
              three prefixes. (2) The same applies to HITS, harder: 118 scorings are 23 draws, one
              entry reached by **95** prefixes (`hit_draws`, frame-minimal representative). (3)
              `lottery` sums each draw's OWN band instead of count x a lean-0 mean width, which had
              overstated E[hits] by 27% (2.159 vs 2.965 here).
            - **MEMORY, not time, is the new ceiling** -- and `dedup_scope='family'` removes it. The
              global key set is ~200 B a candidate; a fan streams family-major with nearly all
              repeats inside one family, so scoping it per family held this 15.8 M-candidate pass at
              **211 MB flat**. The draw dedup is what keeps the reported population identical.
            - **THE 3 THAT DID NOT CONFIRM name the next prune:** all three read `procs [24, 24, 6,
              6, 6]` -- proc 24 is `MOVE_TURN`, so the prefix left Link mid-turn at the aim frame and
              the A-press turned instead of rolling. The fan prunes on speedF and the follow bar but
              not on the proc it will press A from.
            - **NEXT: prune the fan on the endpoint's PROC** (`c.state` is already on the core beside
              the `speedF` the prune reads), then re-run wider -- j1 past 6, more bases, S1 stride 2
              -- since the axis is still paying. Every new hit still owes `confirm_entry`, and the
              whole set still owes the out-of-band DTM console confirm, which this session did NOT do.
      - [~] **THE CAMERA AXIS IS DEAD TOO, AND THE REASON RETIRES A WHOLE CLASS OF COUNTING ERROR:
            THE AIM ALPHABET'S ATOM IS THE CONSOLE SINE-TABLE CELL (16 BAM), SO s81's "32-BAM
            PRODUCTIVE WINDOW AGAINST FOUR REACHABLE AIMS = 8x" IS **TWO CELLS THE FROZEN CAMERA
            ALREADY REACHES BOTH OF**. PRICED END TO END IT READ EXACTLY 8.00x -- AND ALL 48 OF ITS
            NEAR-MISSES WERE **THREE CANDIDATES COUNTED SIXTEEN TIMES** AT BIT-IDENTICAL RESIDUALS.
            WITH EVERY CONFIGURATION AXIS NOW CLOSED, THE ONE LIVE LEVER IS THE TWO-SEGMENT FAN, AND
            IT IS PRICED NONZERO: **6x THE S1 FAMILIES -> 4.3x THE NEAR-MISSES** (session 83).** The
            handoff ordered the camera axis and said to price it first. Pricing it is what killed it.
            - **THE PRICE, MEASURED BEFORE THE DIAGNOSIS.** Scoring the cached 43596-candidate fan
              against the whole productive window instead of the frozen aims: 6 near-misses -> 48,
              E[hits] 0.019 -> 0.154, exactly **8.00x**. Then the near-misses were printed WITH THEIR
              IDENTITY and all 48 were three candidates, sixteen times each, `resid` bit-identical.
            - **THE CAUSE, one line of console maths.** `cM_ssin_s16` is JMASSin --
              `jmaSinTable[(u16)angle >> 4]`, 4096 entries, NO interpolation
              (`knowledge/model/fp-faithfulness.md`, one page away the whole time) -- and every term a
              roll facing reaches goes through it: the per-frame travel, the cut lunge's rotation, the
              Co pose chain, and `roll_entry`'s own 26 u step. So a facing's low 4 bits reach NOTHING.
              The 32-BAM window is cells **2551** (40816..40831, thrust 15, the only band with real
              width) and **2552** (40832..40847, width 0, ULP tickets) -- which is also why the s81
              sweep's two halves had different thrusts and identical widths within each half. The
              frozen csangle's four aims are 40820/40826 (cell 2551) and 40834/40841 (cell 2552):
              **both cells, already.** A csangle slew can re-index which stick byte lands in a cell;
              it cannot add one. Gated `test_the_camera_cannot_add_an_aim_cell`.
            - **THE CAMERA'S ONLY REMAINING REACH IS THE WALK, and it is ~7%.** A held stick's world
              direction is quantized to the same cell and the decoded grid is not uniform: 3612 of
              4096 direction cells at the frozen camera, 3858 over all 16 offsets. That is a CANDIDATE
              axis worth 1.07x, not a configuration axis -- and s81 already measured 1.6x candidates
              buying zero draws.
            - **ENCODED, so the search stops counting copies.** `entry_search.aim_cell` /
              `aim_cells` / `SIN_CELL_BAM` / `PRODUCTIVE_CELLS`; `qualify` runs one configuration per
              CELL and carries the sibling aim bytes for `confirm_entry`; `entry_fan.qualified`
              refuses a pre-cell cache. `qualified()` drops **6 -> 3** configurations (one usable,
              two ULP tickets) and the reference pass's honest read is **3 near-misses / E[hits]
              0.0096** -- half of what s81 and s82 reported, because 40820 and 40826 are one draw.
            - **AND THE REAL CONSTRAINT, found by looking at where the candidates ARE.** At the live
              configuration 91% of the fan (39705 of 43596) piles up at |resid| 0.1..0.5 and only 17
              reach below 5e-3 -- of which **3** carry a live lean, which ARE the pass's three
              near-misses; 34.5% of candidates carry a lean with any band at all. Every
              ONE-SEGMENT pass from 14529 to 391446 candidates (27x) returns the SAME three
              near-misses gap for gap, because the closest family is `n0=5` + ONE delivered frame and
              that frame's byte alphabet is already exhaustive -- the fine knob is saturated. What
              varies the sub-cell offset is the PREFIX, so near-misses should scale with S1 FAMILIES.
              Measured: 32 families -> 3, **192 families -> 13**, best gap 8.14e-4 -> **2.79e-4**
              (`_generated/s83_search2_a32.out`, 272599 candidates, 220 s). At that rate E[hits] ~ 1
              wants ~313 near-misses, i.e. ~50x the families, ~3 h at the measured 1.15 s/family.
            - **NEXT: the two-segment pass at S1 stride 4-8, widened j1, more bases** -- the only axis
              left and the only one still priced nonzero. Every hit still owes `confirm_entry`.
      - [~] **THE MOMENTUM AXIS IS GENERALIZED, GATED -- AND MEASURED DEAD. THE s81 "BIGGEST
            UNTOUCHED LEVER" (3x THE CANDIDATES OVER 4146 ROLL SCHEDULES) BUYS **ZERO**: AN
            UNCAPPED FAN REACHES 42807 DISTINCT MOMENTA OF WHICH **4** ARE PRODUCTIVE, AND THE
            FULL-RESOLUTION UNCAPPED PASS -- **391446 CANDIDATES, 9.0x THE s80/s81 REFERENCE** --
            RETURNS THE **SAME 6 NEAR-MISSES AND THE SAME E[hits] 0.02** (session 82).** The
            handoff ordered: generalize the
            schedule off the walk cap, gate it at a sub-cap speed, then re-run `search1`. All three
            ran. The model work is right and is kept; the lever it was supposed to unlock is not
            there, and the axis is now closed by measurement instead of by an unexamined constant.
            - **THE GENERALIZATION (kept, current truth).** `entry_search.roll_nspeed` is
              `_roll_init`'s clamp read off `LandState`'s own constants, `ROLL_NSPEED` is DERIVED
              from it at the cap rather than written down, and the momentum is threaded through
              `fast_schedule` / `roll_entry` / `build_fast` / `configuration_band` /
              `entry_gradient` / `qualify` / the band key / the fan key (4-tuple when uncapped:
              two candidates on one point at different speeds are different draws).
              `turnaround.extract_schedule_at(nspeed=)` lets the SIMULATED reference run sub-cap too.
            - **THE GATE, at five sub-cap momenta (5.06 / 8.31 / 14.61 / 22.67 vs the cap's 26).**
              A REAL from-rest walk + A-press roll: the clamp off the WALK ENDPOINT's speedF is the
              roll's momentum **bit-for-bit** (the entry frame dispatches after MOVE, and it is
              still the endpoint's speed `_roll_init` reads -- measured, not assumed);
              `roll_entry(walk, facing, nspeed)` is the entry position **0-ULP** (the cap-assuming
              one is >20 u out at nspeed 5); the reseed's **nine baked tables are identical** to
              the real roll at every thrust; the analytic `fast_schedule(nspeed=)` IS the simulated
              one; and the cap-assuming schedule differs in exactly **`dx`/`dz`** -- the momentum
              scales the travel and nothing else.
            - **THEN THE AXIS WAS PRICED, WHICH IS WHERE IT DIED.** Sweeping nspeed 17..26 at every
              reachable aim x thrust: **2 of 181** momenta productive, both at the cap. Marched
              ALONG the whole locus (`entry_search.locus_scan` -- re-project onto resid 0 at each
              station, because a one-point band verdict cannot declare a curve barren) the control
              at 26 lights **44 of 58** stations, every sub-cap momentum reads **0 of ~60**. And the
              window did not merely MOVE: at nspeed 22.67, swept at 8 BAM over the ENTIRE 65536-facing
              circle, nothing is productive. (First circle sweep ran at 64 BAM and read 0 at the cap
              too -- its own window is 32 BAM wide, so the stride stepped over it. A negative whose
              control is also negative is a resolution bug; always sweep the live one in the same call.)
            - **THE PHYSICAL REASON, legible and portable.** A shorter roll is not the same clip
              started further back. Below ~17 of momentum the roll never reaches the wall brace that
              pins `old`; in the middle of the range it reaches the brace but leaves Tetra out of Co
              range on the CUT frame, so the push is **zero** and no entry has leverage at all
              (grad 0.000, push (0,0) at nspeed 14.61).
            - **THE RE-RUN (the handoff's step 3), at two resolutions.** Same fan, cap on vs off:
              stride 4 gives 14529 -> 43653 candidates (3.00x) and **the same 4 near-misses, gap for
              gap**; stride 1 gives **391446** candidates (9.0x the s80/s81 reference 43596), 2.35M
              evaluations in **231 s**, and **6 near-misses / E[hits] 0.02** -- exactly what s81's
              honest recount read off the CAPPED pass. Nine times the candidates, the same lottery.
            - **`ShoveCtx.set_link_schedule` (new, pyx) is what made any of this affordable.**
              Everything expensive in a ctx is the compiled WORLD (mesh, planes, `_precompute_slices`);
              the schedule is ~20 doubles a step. `build_fast` is 1.52 ms, a re-schedule is 0.16 ms.
              `entry_search.CtxPool` keeps one ctx per (facing, thrust) and re-schedules per
              (lean, nspeed) -- without it a per-candidate configuration key is hours of recompiling
              one unchanging courtyard. Gated: a pooled ctx sweeps IDENTICALLY to one built at that
              configuration (genuine flag, endpoint, push, residual).
            - **`stream_search`'s band strategy INVERTED, for the same reason.** s81 looked a band up
              per group and skipped the dead ones -- correct when a band serves ~20 candidates. With
              the momentum in the key a band (14 ms) costs 70x the group evaluation (0.2 ms) it would
              save, so every draw is now EVALUATED (`genuine` is ground truth and needs no band) and
              a band is measured only for the near-zero tail. The uncapped 43653-candidate pass
              measured **18** bands. The s81 dead-configuration correction is kept, not dropped: a
              tail draw whose configuration has no usable band is counted dead, not as a near-miss.
            - **Also fixed:** `confirm_entry` reads two-segment plans (`iter_fan2`'s 7-tuples) -- s81
              built them and left the confirmer unpacking 4 -- and checks the roll's own **nspeed**
              instead of "is it at the cap".
            - **Gates** (+5 in `tests/test_entry_search.py`, +3 in `tests/test_entry_fan.py`; both
              files 45 fast, 32 s): the momentum law + entry step against a real A-press, the sub-cap
              nine tables + analytic-vs-simulated + the `dx`/`dz`-only difference, the pooled ctx,
              the uncapped fan being the capped one plus its sub-cap endpoints (and equal to the
              Python fan key-for-key), the dead momentum axis along the whole locus (BOTH death
              modes: a locus with no dust, and no leverage at all), and the end-to-end
              "2x the draws, the same near-misses". KB: `clip-lottery-draws.md` rewritten on the
              prune section + a new "declaring a configuration dead needs the WHOLE locus";
              `clip-entry-search.md` momentum + ctx-reuse; s81's claim MIGRATED to
              `knowledge/history/entry-search-s81-momentum-lever.md` + a hub row.
            - **NEXT: the CAMERA AXIS, now the only priced-nonzero lever left.** s81 measured it:
              the productive facing window is 32 BAM of consecutive facings and the frozen csangle
              (34325) reaches exactly four aims inside it -- up to **8x more usable configurations
              at zero frame cost**, since csangle is position-independent during the walk-in, so one
              measured stream serves a whole fan. Slew it in the base prefix (measure the stream once
              in the wired run, inject it into the fleet schedule, which already carries a per-frame
              csangle column). Two-segment holds after that. Every hit still owes `confirm_entry`.
              **Session 83 priced it at ZERO: 32 BAM is two sine-table cells and the frozen camera
              already reaches both. See the box above.**
      - [~] **THE FAN IS NATIVE AND GATED (43596 CANDIDATES IN 17 s AGAINST 1444, KEY-FOR-KEY
            BIT-IDENTICAL) -- AND THE THROUGHPUT'S FIRST FINDING IS THAT THE FAN WAS NEVER THE
            BINDING CONSTRAINT: THE ACCEPTANCE BAND IS A FUNCTION OF THE **LEAN**, SO **83% OF THE
            WIDEST PASS'S DRAWS ARE DEAD** -- 72 NEAR-MISSES ARE REALLY 6 AND E[hits] IS **0.02, NOT
            0.23** (session 81).** The handoff asked for the fan on the fleet and then two-segment
            holds; the fan landed, and the first thing it bought was an audit that redirected the
            search away from candidates altogether.
            - **THE GRAFT IS WHAT MAKES A NATIVE FAN POSSIBLE.** The stripped native config does NOT
              reproduce the WIRED replay of the console log -- it diverges at log frame **19** on
              `facing`, the proc-9 re-aim falling back to Tetra's FEET where the wired run has her
              modeled eyePos -- so the fan cannot run natively from f0. `entry_fan.graft`
              transplants the wired Python mid-walk state into a `LandCore`: `LandCore.setup` resets
              the mid-walk physics scalars (`m34dc`/`target`/`msd`/`direction`/`roll_frame`/`_l_prev`),
              all of them `cdef public`, and restoring them plus the delay-1 buffer is the whole job
              -- no pyx change. The three private fields it cannot reach are inert here by
              measurement (the lock reads NONE and the fan's held input has buttons 0 / triggerL 0,
              so no L edge fires; the C-up counters are never armed; the camera privates are
              walk-step-only). csangle is frozen at **34325** through the whole fan window.
            - **THE EQUALITY GATE, at full resolution.** `fleet_fan` == `walk_fan` as a DICT, key and
              value, over the cached s80 pass: 43596/43596 shared, 0 either side, 0 value diffs, in
              **17.2 s**. Write order is part of the contract (the reference collapses ~5.5M writes
              onto 43596 keys and the last writer wins), so the fleet applies each core's hits
              stick-major / j-inner exactly as the reference loop does.
            - **THE BAND IS PER (facing, thrust, m351C).** s80 fixed "the fixture window is a union"
              by measuring a band per (facing, thrust) -- at lean 0 -- and then `search` scored every
              candidate against it. Swept on the lean axis at one configuration: 448 of 556 finely
              sampled leans admit something genuine, but only ~40% of those have a real interval
              rather than a single f32 value, and many (including much of what a real walk-in
              arrives at) have **nothing genuine at any entry**. Recounted per triple, the widest
              one-segment pass reads **69038 live evaluations against 345976 dead-lean draws**, 6
              near-misses, E[hits] **0.02**. The requirement is ~250x, not 50x -- and not in
              candidates.
            - **HOLD LENGTH WAS NOT SATURATED, AND SATURATING IT BOUGHT NOTHING.** Measured (cheap
              now): base nodes past n0=6 add EXACTLY 0, but jmax 12 -> 36 takes the fan from 43596 to
              **69169** candidates -- and yields **exactly zero** extra near-misses. The extra
              candidates are longer walks, which go past the locus. Raw candidate count is not the
              figure of merit; density at the target is.
            - **THE PRODUCTIVE FACING WINDOW IS 32 BAM WIDE AND THE FROZEN CAMERA REACHES FOUR AIMS
              IN IT.** Sweeping facing directly at 1 BAM over the whole seam range (2703
              configurations, 37 s) finds **48 productive**, all inside facings **40816..40847** --
              one window, 32 distinct facings, thrust 15 carrying the real 3.2e-5 band and thrust 14
              a zero-width one. s80's "3 distinct" was the spread of the aim SAMPLES. The alphabet at
              csangle 34325 lands exactly `[40820, 40826, 40834, 40841]` inside it, so the C-stick is
              worth up to **8x more usable configurations**, at zero frame cost (csangle is
              position-independent during the walk-in, so one measured stream serves a whole fan).
            - **AND ONE OF THE TWO FAN PRUNES IS SELF-INFLICTED.** speedF == 17.0 is kept because
              `fast_schedule` bakes ROLL_NSPEED 26 (the cap's own roll momentum) -- but a sub-cap walk
              still rolls, at `clamp(1.5*speedF + 0.5, 5, 26)`. Dropping the prune is **3.0x** the
              candidates (43610 against 14529) spanning **4146 distinct nspeed schedules, each its own
              locus and band**. That is the biggest untouched lever in the search and it is a schedule
              generalization, not a new mechanic (it does owe a `roll_fidelity` gate at sub-cap speed).
            - **WHY A LOCAL DESCENT HAS NO GRADIENT** (two measured facts, both gated): the last
              delivered frame is only BUFFERED, so re-aiming a plan's final frame lands on the SAME
              endpoint to the bit (12 held == 11 held + a different aim); and once the new aim does
              act, a one-frame turn at the alphabet's ~12 BAM local spacing drops Link off the cap and
              writes lean besides. Perturbing stick BYTES is a third flat objective -- the octagon
              clamp maps every byte near a saturated aim to the same decoded angle.
            - **THE TWO-SEGMENT FAN IS BUILT** (`iter_fan2`, junction cores re-fanned, plans are
              7-tuples) and pilots at the same near-miss yield per candidate as one segment (6 per
              ~60k live draws). It is a real candidate multiplier; it is just not the cheapest one any
              more.
            - **Gates** (+11 fast, +1 slow, `tests/test_entry_fan.py`): the graft bit-for-bit against
              the wired run (and that dropping CARRY diverges), fan equality at small resolution and
              against the cached full pass, the per-lean band with three pinned dead leans, the
              locus moving with lean, the dead-draw majority, the 32-facing window against the four
              reachable aims, the buffered-aim fact, the cap prune's ratio + nspeed family, the
              analytic gradient 0-ULP vs the simulated one, and streaming == materialised scoring.
              KB: `knowledge/strategy/clip-lottery-draws.md` NEW (how to count draws), the s80
              claims MIGRATED to `knowledge/history/entry-search-s80-superseded.md`.
            - **NEXT, in this order** (all three are configuration axes, not candidate count):
              **(i) generalize the schedule off the walk cap** -- `fast_schedule(nspeed=...)` +
              `roll_entry` from the real `_roll_init` law, gated by `roll_fidelity` at a sub-cap
              speed; that is 3x candidates and thousands of loci. **(ii) the camera axis** -- slew
              csangle in the base prefix (measure the stream once in the wired run, inject it into
              the fleet schedule, which already carries a per-frame csangle) to bring the other 28
              productive facings into reach. **(iii) then** spend the fleet on a wide two-segment
              pass. Every hit still owes `confirm_entry`.
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
            - **THE PASSES.** 18161 candidates (stride 2, 7 base nodes) x 243 configurations, 595 s:
              1018 near-zero, 0 genuine. Then the widest: **43596 candidates** (stride 1, 7 bases,
              jmax 12) x the 6 qualified configurations -- fan **1444 s**, eval **11 s**, **72
              near-zero, 0 genuine**, best gap 2.21e-4. Base nodes past n0=6 add nothing and stride 1
              saturates. 72 near-zero over 262k evaluations against a ~1e-5..5e-5 band is an expected
              **~0.2 hits**, so a confident hit wants **~50x more candidates** -- which is ~20 h of
              Python fan and minutes of `CourtyardFleet.run_par`. The eval is no longer the budget;
              the FAN is, at ~3.5k `FreeRun` steps/s. Fan cached at
              `_generated/s80/fan_s1_j12_b7.json`.
            - **Gates** (+11 in `tests/test_entry_search.py`, 26 fast + 2 slow): the nine-table
              fidelity diff, the post-entry-frame convention (and the pre-entry mismatch), the
              bit-exact entry/lean conversions, the armed-latch clearance, the analytic schedule
              0-ULP over facing x lean x thrust, the 81-vs-11 alphabet with every sampled aim fired
              and read back, thrust independence, the per-configuration band, the leverage census,
              the walk fan's two prunes, and the signed-gap rank.
            - **NEXT: move the FAN onto the native fleet.** Stride and base frames are exhausted, so
              the 50x wants `CourtyardFleet.run_par` (1M steps/s vs 3.5k) and then TWO-SEGMENT holds;
              gate it 0-ULP against the cached Python fan first. And every hit owes `confirm_entry`,
              which replays a hit's own plan with a REAL A-press on the courtyard engine and checks
              the predicted entry/facing/lean bit-for-bit. It has already earned its keep twice: it
              caught an INPUT_DELAY off-by-one in the fan's plan labels (now fixed and gated -- the
              endpoint after j+1 steps is what a j-frame plan rolls from), and it found that
              `roll_entry` assumes an entry frame that does not BRAKE. When the aim swings far from
              travel, MOVE decelerates before the roll dispatches and nspeed lands at 18.99 instead
              of 26 -- about one candidate-aim pair in eight. Whenever it does roll, the walk
              endpoint, facing and lean are exactly as labelled.
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
