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

## THE key modeling gap: untarget brakesliding = the ATN_ACTOR procs  [MODELED session 2; live-validation pending]

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

## Tooling

| File | What |
|------|------|
| `find_tetra.py` | Locate Tetra (Zl1, id 429) live via the DMC walk, `_execute` breakpoint, `r3`. Session-stable (recomputes the REL base). |
| `capture_push.py` | Load slot 2, locate Tetra, single-step the movie N frames, log both actors + pad to a fixture. The GROUND TRUTH the sim is validated against. |
| `fixtures/courtyard_push_state2.json` | 51-frame ground-truth capture from state 2 (repo `fixtures/`). |

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
- [~] **Validate sim vs live from state 2**, 0-ULP over the ~45 push frames. IN PROGRESS (session 2):
      `capture_push.py` now logs the FULL pad (stick + C-stick + L + a/b/l) and the real state-2 input
      timeline is captured. It CONFIRMS the mechanic's shape (both cycles: L held into ATN_MOVE proc 7
      no-actor -> A roll -> L re-pulsed MID-ROLL acquires the Tetra lock -> released -> roll exits into
      ATN_ACTOR_MOVE proc 9 -> speedF flips +26 -> -25.73 -> MOVE). NOT yet 0-ULP. Three gaps to close:
      1. **Raw DTM stick bytes** -- feed the sim raw bytes (it decodes them; the octagon clamp is part
         of the physics), not the pad struct's decoded (lossy) stick. Use the `harness/dtm/run_dtm.py`
         path against `28_Courtyard_TetraPush_Unfinished.dtm`.
      2. **`chaseAttention` acquisition gate** (range + view cone) -- the lock acquires MID-ROLL, not at
         the first L (frames 0-1 read proc 7 = no actor), so `target_present` is NOT a constant flag.
      3. **Pin `FADE_FRAMES`** -- live-observed ~8 (L-release to proc-9->MOVE, INPUT_DELAY-corrected),
         NOT the placeholder 2; confirm exactly with the raw-byte replay. It is an anim length, not a knob.
      Then seed LandState + `cc_stepper(atn_lock=True)` + `Zl1FollowState`, replay raw inputs, per-frame
      diff BOTH actors. NOTE: the single-stepped fixture's per-frame POSITION deltas are jitter-corrupted
      (`[[run-dtm-1frame-jitter]]`), so it is scalar (proc/speedF/facing) ground truth; positions need a
      clean run_dtm capture.
- [x] **Viable Tetra clip positions = `_generated/tetra_placements.tsv`** (Dereck, 2026-07-21): those
      288 genuine coords are the target set. They were recorded at a specific roll entry, but the
      planner ARRANGES the matching roll entry as part of the push sequence (the genuine-coord set is
      coupled to Link's final roll entry, so the two are solved jointly). From state 2 Link/Tetra are
      still far from the corner, so there is runway to steer both into place.
- [ ] **Build the planner**: state-2 config to a coupled sim (Link roll/untarget-EBS + Tetra
      plow/follow) to a search for the input sequence that lands Tetra on a genuine `tetra_placements`
      coord AND sets up the matching roll entry. Method reference: `plan_land` / the seam-clip `solver`
      (cheap predictor + exact bit-confirm, no calibration).

## Hard rules (inherited from the seam-clip work)

- **Decomp-first** (`[[decomp-first-not-brute-force]]`): read `d_a_player_main.cpp` / the JP
  `framework.map` for exact thresholds before live-bisecting. Breakpoint the JP address, not the US
  decomp comment (`[[jp-vs-us-decomp-addresses]]`).
- **When live disagrees with the sim, DIFF per-frame, never guess inputs** (`[[tetra-clip-solved-live]]`).
- **0-ULP is the bar**, validated against a locked live capture, not offline plausibility.
- A single-stepped PLAYING movie is +-1-frame ambiguous for button EDGES (`[[run-dtm-1frame-jitter]]`);
  held-stick push frames are safe. For edge delivery use a clean free-run movie.
