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
| `find_tetra.py` | Locate Tetra (Zl1, id 429) live via the DMC walk, `_execute` breakpoint, `r3`. Session-stable (recomputes the REL base). |
| `capture_push.py` | Load slot 2, locate Tetra, single-step the movie N frames, log both actors + FULL pad to a fixture. The (scalar) GROUND TRUTH -- single-stepped, so `+-1` on edges. Now also logs `nspeed` (mNormalSpeed). Subcommand **`capture_push seed`** = a DETERMINISTIC single read of the complete f0 state (no single-step jitter) -> `fixtures/courtyard_push_seed.json`. |
| `fixtures/courtyard_push_seed.json` | The complete STATE-2 seed (f0): pos/travel/facing/speedF + the HIDDEN **mNormalSpeed** (`link.nspeed`) the cyl/dtm fixtures never logged, plus mDirection/m34E6/csangle + the attention state, for provenance. Deterministic single read (jitter-free). The from-f0 replay's `seed_nspeed` source AND the planner's initial condition (session 12). Session 16 added **`old_pose`** -- the live `m_old_fdata` per-joint post-morf pre-twist store (quat x,y,z,w + transform, all 42 joints) + morf counters, the `replay(..., seed_old_pose=)` source (at THIS seed it equals the pure-dash warmup; general-correctness for any f0 with live morf residue). |
| `dtm_inputs.py` | Extract the REAL per-frame raw controller BYTES from the recorded movie `GZLJ01.s02.dtm` (F0=44974 alignment, re-derived) and bake them + the live states into `fixtures/courtyard_push_dtm.json`. The 0-ULP replay input (the sim decodes raw bytes; the pad struct is post-decode/lossy). Session 19: extracts **poll index 2** of each 4-poll frame group -- the poll the game actually latches (live-pinned via the camera oracle on the window's two non-uniform groups); regen with no capture preserves the baked live rows. |
| `fixtures/courtyard_push_dtm.json` | Baked: state-2 seed + per-frame {raw DTM input, live Link proc/speedF/facing/pos, Tetra pos/stt}. Self-contained (no Dolphin/DTM needed to replay). Gated by `tests/test_tetra_untarget.py`. |
| `fixtures/courtyard_push_state2.json` | 51-frame session-1 ground-truth capture from state 2 (repo `fixtures/`). |
| `tetra_plow.py` | **The Courtyard Co-overlap GEOMETRY**: `plow_depth` (`cM3d_Cross_CylCyl` cross_len) + the Link/Tetra Co radii (30/50). The per-frame PUSH LAW is now `from_f0.cc_push_pair`; `plow_step`/`reconstruct` (the session-8 DERIVED full-depth-from-settled law) were RETIRED session 27 (superseded, ~1e-5 u off the console -- git history archives them). Gated `tests/test_tetra_plow.py`: the regime discriminator (frac==1.0) + `test_console_push_bit_exact_vs_deterministic`. |
| `from_f0.cc_push_pair` | **THE console CC push law (session 27)**: `cc_push.co_move_pair` = `dCcS::SetPosCorrect` -- the decomp 50/50 half-depth rank split on Link's EXEC centre, obj1/obj2 EXACT-opposite. 0-ULP vs the deterministic per-op ΔTetra f2..f43. Replaces `full_depth_push` (now the seed-frame f0->f1 fallback only). |
| `link_plow.py` | **The Courtyard Link-recoil LAW** (session 9, now the SEED-frame fallback path): Link's per-frame recoil = the FULL Co overlap depth AWAY from Tetra (`link += depth·unit(link_centre−Tetra)`). `recoil()`/`recoil_step()`, used by `from_f0.full_depth_push` (the f0->f1 seed push). Superseded for f1..f43 by `cc_push_pair`. Gated `tests/test_link_plow.py` (frac==1.0 regime discriminator). Reuses `tetra_plow.plow_depth`. |
| `from_f0.py` | **The from-f0 COUPLED replay** (session 10-12): wires BOTH plow laws (`link_plow`+`tetra_plow`, full-depth) into a closed-loop `LandState` replay seeded at f0 (or a roll entry), driven by the real DTM bytes, Link's mCyl Co centre + csangle INJECTED per frame. Tetra tracked as a bare XZ plow point (stt-3 the whole window). `full_depth_push()` + `replay(..., seed_nspeed=)`. Session 17 refactored the loop into **`FreeRun`** -- the planner's novel-input stepper (seed once, `step()` arbitrary raw inputs; eye/tattn per-step injectables; warns if a stepped state leaves the stt-3 plow regime, dist > `FOLLOW_ENGAGE_DIST`) -- with `replay` a thin wrapper over it. Session 19 wired the MODELED land camera in (`camera=` a seeded `LandCamera`), replacing the csangle injection entirely (see the planner box). **Session 29** closed the f1 seed-frame boundary: `FreeRun(seed_push=)` / `replay(..., seed_push=)` take the exact perop f0->f1 ΔTetra push (`full_depth_push` is now the roll-entry / no-perop fallback), and `step()` rounds the tracked Tetra point to f32 each frame (console storage) -- so the self-contained closed loop from state 2 is now bit-exact in POSITION too, f1..f43, both actors. Gated `tests/test_from_f0.py`: from the roll entry, from **state 2 itself** (dynamics), the one-step-from-exact gates (position f1..f43), and `test_closed_loop_computed_replay_bit_exact` (accumulating position f1..43). |
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
  f0 -5.198 -- the anmmtx-probe root/neck Y offset, XZ-irrelevant); equipped item `m3562` `la+0x3562`
  (u16; 0x103 = sword DRAWN, true the whole courtyard window); `m34EC` (extra draw yaw) + `shape.x`
  `la+0x20C` both 0 all window.
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
- [~] **Build the planner** -- STARTED (session 28); the forward model is now FULLY BIT-EXACT from
      state 2 -- dynamics AND position 0-ULP f1..f43 (session 27 closed f2..f43; **session 29 closed
      the f1 seed-frame boundary, entirely offline** -- see the search-proper box below). So an
      open-loop multi-cycle rollout is trustworthy and the search foundation is solid. The deliverable
      is still the input sequence that lands Tetra on a genuine `tetra_placements` coord + the matching
      roll entry. Method reference: `plan_land` / the seam-clip `solver` (cheap predictor + exact
      bit-confirm, no calibration). The camera/look/neck sub-models ARE 0-ULP-gated and reusable.
      Session-28 progress (below): the sound primitive layer is RESTORED + gated, coarse feasibility
      is CONFIRMED, and the f1 seed-frame cost was characterized (session 28) then CLOSED (session 29).
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

## Hard rules (inherited from the seam-clip work)

- **Decomp-first** (`[[decomp-first-not-brute-force]]`): read `d_a_player_main.cpp` / the JP
  `framework.map` for exact thresholds before live-bisecting. Breakpoint the JP address, not the US
  decomp comment (`[[jp-vs-us-decomp-addresses]]`).
- **When live disagrees with the sim, DIFF per-frame, never guess inputs** (`[[tetra-clip-solved-live]]`).
- **0-ULP is the bar**, validated against a locked live capture, not offline plausibility.
- A single-stepped PLAYING movie is +-1-frame ambiguous for button EDGES (`[[run-dtm-1frame-jitter]]`);
  held-stick push frames are safe. For edge delivery use a clean free-run movie.
