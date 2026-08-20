# Courtyard Tetra-push: the session journal

The full session-by-session record of the Courtyard Tetra-push planner, sessions 1-170, moved here
from the Claude memory store when the work was parked on this branch. It is the narrative record:
what was tried, what each session overturned, the steers, and the traps. The technical doc is
`README.md`; the standing instructions are `SESSION_PROMPT.md`; the state is the README's
`## Plan / status`. Read this when you need to know WHY something is the way it is.

The headline: the console 101 stood from session 73 to 169, and session 170 beat it -- TOTAL 98,
three genuine accept()-green plans, the clip landed live.

---

**NEW line of work started 2026-07-21** (pivot back to Tetra pushing, now on the ACTUAL any% TAS,
not the slot-7 sandbox). Home: `harness/tetrapush/` (README is the durable doc). Distinct from the
seam-clip solver (`harness/rollstab/`) but reuses its Tetra machinery. Builds on [[tetra-push-model]]
[[cc-push-stepper]] [[tetra-follow-model]] [[tetra-clip-solved-live]] [[turnaround-clip-followenabled]].

**North star (Dereck):** load **savestate slot 2** (mid-playback of the real DTM
`28_Courtyard_TetraPush_Unfinished.dtm`; runs in the pipe-enabled research build) and compute the
optimal input sequence from there that shoves Tetra into a known viable clipping position. ONE-TIME
sequence for the real run (>2min search OK). Sub-tasks: (1) make the sim bit-exact over the ~45
hand-performed push frames after state 2; (2) build the planner (state-2 config -> input seq).

**Setup (measured live):** stage `Hyrule` room 0 (flooded castle, flat Y=0.16327, SAME geometry as
the (-1727,-990) sandbox corner). State-2 seed frame 89952: **Link (-1329.4236,0.1633,39.8988) travel
4705 facing 12386 speedF -24.574 proc MOVE(6)**, csangle ~39432; **Tetra (-1336.7809,0.1633,-0.9584)
type 5 stt 3 speedF 0**. Link ENTERS state 2 already in a near-full-roll-speed backslide (-24.57,
hotter than the usual -23.5 EBS). Tetra herded in -Z/-X toward the corner.

**The push = a repeated ~26-frame cycle** (x2 over ~45 frames, herds Tetra ~535u -Z to (-1510,-535)):
MOVE backslide (~-24.6, decays ~-0.01/f) -> ATN_MOVE(7) 1-2f re-target (speedF flips +18) ->
FRONT_ROLL(30) 26.0 ~16f facing-locked (PLOWS Tetra) -> **ATN_ACTOR_MOVE(9) @26 -> flips -25.7**
(2 frames, pad near-neutral, NO held L) -> MOVE backslide -> repeat. Tetra during rolls: stt3/speedF0,
PLOWED (pos shoved by Link's roll Co-center); when Link glides away she flips stt4 and FOLLOWS
(speedF 0->10 cap; Zl1FollowState). Herd = plow + follow, both already in the sim.

**THE modeling blocker = untarget brakesliding = the ATN_ACTOR procs.** proc 9 =
`daPyProc_ATN_ACTOR_MOVE_e`, proc 8 = `ATN_ACTOR_WAIT_e` (actor-lock variants of ATN_MOVE). The land
sim only models plain ATN_MOVE(7) (target a DIRECTION, not an ACTOR). Mechanic: target Tetra mid-roll;
releasing L does NOT untarget immediately (mAttentionActor persists several frames); timing L-release
to the roll-anim end goes straight into ESS-down WITHOUT the 1 "L+down" frame, so EBS retains ~-25.7
(near full roll 26) vs the standard -23.5. Must be modeled decomp-first (d_a_player_main.cpp:
ATN_ACTOR proc funcs, checkNextMode roll-exit routing, the L-release/lock latency, why -25.7 retains).

**Tooling delivered (this session, on main-to-be):** `harness/tetrapush/find_tetra.py` (locate Tetra
Zl1 id 429 via DMC walk -> _execute bp -> r3; session-stable), `capture_push.py` (loadstate 2 ->
locate -> single-step movie N frames -> log both actors + pad), fixture
`fixtures/courtyard_push_state2.json` (51-frame ground truth). Live addrs (JP): Link daPy this
[0x803AD860], fopAc = this-0xD8, proc +0x3100, anim +0x2F64; fopAc pos +0x1F8 travel +0x206 facing
+0x20E speedF +0x254; Tetra stt +0x84B type +0x84F, instance this session 0x80ace20c, _execute
0x80f4cb9c (REL base moves per load). Pad g_mDoCPd_cpadInfo[0] @0x80398308 (px/py/val/ang +0/4/8/C).

**Target set RESOLVED (Dereck 2026-07-21):** the viable Tetra coords ARE
`_generated/tetra_placements.tsv` (288 genuine positions). They were recorded at a specific roll
entry, but the planner ARRANGES the matching roll entry as part of the push sequence (genuine-coord
set is coupled to Link's final roll entry, solved jointly). From state 2 Link+Tetra are still far
from the corner, so there is runway to steer both into place.

**Decomp for untarget brakeslide GROUNDED (2026-07-21, in the README):** procs 8/9 both call
`setSpeedAndAngleAtnActor` (2909-2935, always actor-facing so DIR_BACKWARD negation stays on, 26->-26);
roll-exit routing `checkNextMode` (4423-4521, r24=checkAttentionLock, mpAttnActorLockOn!=NULL ->
proc 9); untarget latency is ANIMATION-driven (L-release -> LockState_RELEASE, persists until the
reticle fade-out anim / AttnFlag_40000000 clears, NOT a fixed counter); -25.7 vs -23.5 = the -5.0 roll
decel is SKIPPED on the held-stick early-turn exit + proc 9's gentle mAtnMove decel (cap 12 push 5
scale 0.5 maxStep 7.5). Full recipe + line cites in harness/tetrapush/README.md.

**SESSION 2 (2026-07-21): untarget-brakeslide model IMPLEMENTED (the session-1 blocker), decomp-first,
offline-gated, NOT yet live-validated.** New: `tww_sim/land/attention.py` (`AttentionLock` NONE/LOCK/
RELEASE hold-mode machine; `locked`==mpAttnActorLockOn!=NULL; untarget latency = reticle YJ_DELETE anim
length `FADE_FRAMES`, placeholder 2, live-source it) + `tww_sim/land/procs/atn_actor.py` (`_AtnActorMixin`
= setSpeedAndAngleAtnActor DIR_BACKWARD negation flip + setShapeAngleToAtnActor re-aim). Wired into
state.py (proc-8/9 dispatch, `_atn`/`_atn_actor_pos` fields, per-frame `_atn.update`, proc-8/9 position
via speedF momentum [2-frame proc-9 pos is provisional/live-gated]) + `move.py::_check_next_mode` (true
r24 = l_held OR _atn.locked; routes roll-exit to proc 9 iff locked). PURELY ADDITIVE: inert without a
driven lock-on actor, so all 438 offline + 16 land goldens stay byte-identical. Split the 123-line HIO
const block into `tww_sim/land/hio.py` (_LandHIO base) to stay under the 800-line cap. cc_stepper gained
`atn_lock=` opt-in (feeds Tetra XZ as Link's actor). Gate `tests/test_atn_actor.py` (11, ALL exact/0-ULP
vs pinned model outputs, NO tolerances). Decomp cites verified live-in-source: setSpeedAndAngleAtnActor
:2909, setShapeAngleToAtnActor :2625, checkNextMode :4424, getDirectionFromCurrentAngle=getDirFromAngle(
m34E8-current.angle.y), d_attention.cpp judgementStatusHd :804-844 / Lockon :1049 / reticle-fade :653-698.
CAUTION (Dereck's steer, session 2): DO NOT treat any offline magnitude match as validation -- the
"-25.72 vs live -25.727" used a GUESSED input (msd 0.056 from the pad value) and proves nothing; 0-ULP
is the bar and it's PENDING. The state-2 fixture is SCALAR-only ground truth (proc/speedF/facing); its
per-frame POSITION deltas are jitter-corrupted (single-stepped playing movie, [[run-dtm-1frame-jitter]]:
disp/speedF bounces 0.18-0.68 at constant speedF/travel), so position must be validated vs a CLEAN
free-run capture.

SESSION 2 LIVE CAPTURE (Dolphin up, state 2): extended capture_push.py to log the FULL pad (main+C
stick, analog L, decoded a/b/l bits; interface_of_controller_pad offsets in c_API_controller_pad.h:
main +0x00..0x0C, C +0x10..0x1C, trigL +0x28, mButtonHold +0x30 [byte0 l=0x02 a=0x01, byte1 b=0x80]).
Read the real 45-frame input timeline. Both cycles identical: L held into ATN_MOVE(7, NO actor) -> A
roll -> **L re-pulsed MID-ROLL** (pad f7-9/f31-35, acquires Tetra lock) -> released -> roll to anim end
-> exits into ATN_ACTOR_MOVE(9) f19/f46 -> speedF flips +26 -> **-25.73** -> MOVE. The modeled path is
CONFIRMED structurally; NOT yet 0-ULP. THREE gaps the timeline forces: (1) **FADE_FRAMES ~8 not 2**
(L-release pad f10 -> proc9 f19, holds thru f20; RELEASE persists ~8 physics frames w/ INPUT_DELAY=2) --
updated attention.py default to 8 (PROVISIONAL, pin via raw-byte replay); (2) **lock acquires MID-ROLL
not at first L** (f0-1 hold L but read proc 7 = no actor), so target_present is NOT a constant -- need
the chaseAttention range+cone gate, or drive presence from the capture; (3) **byte-exact POSITION needs
the RAW DTM stick bytes** (pad struct is DECODED/lossy; the octagon clamp is part of physics) -- use the
run_dtm path vs 28_Courtyard_TetraPush_Unfinished.dtm.

SESSION 3 (2026-07-21): the untarget-brakeslide FLIP is now VALIDATED BIT-EXACT vs live, BOTH cycles.
(1) **Gap 1 (raw DTM bytes) CLOSED.** New `harness/tetrapush/dtm_inputs.py` extracts the real per-frame
raw controller BYTES from the recorded movie `GZLJ01.s02.dtm` (companion DTM beside slot 2, NOT a
TAS-Studio file): controllers=3, port0=ODD rows, 4 uniform polls/game frame; **cap f0 == DTM
game-frame F0=44974** (re-derived from the two roll-trigger A-runs 26 apart). Delivered stick DECODES
to the session-2 captured pad EXACTLY every frame (buttons+mag+angle, 0 mismatch f0..f45); movie ends
group 45019 (=f45), f46+ free-run holds stick 111,111. Baked to `fixtures/courtyard_push_dtm.json`
(inputs + live states, self-contained). (2) **Flip validated bit-exact** via `tests/test_tetra_untarget.py`
(3 offline): seed a LandState at each roll entry (state=30, speedF/nspeed=26, _roll_entered=True,
_roll_m3570=False; couple_replay convention), feed the raw DTM bytes with Tetra driven as lock actor,
assert roll->proc9 and min speedF _bits-identical to the captured flip -- cycle1 -25.727313995361328,
cycle2 -25.742908477783203 (expected derived from the fixture's own capture, not a literal).
target_present=True throughout is CORRECT (not oracle): seeding after the initial directional L, the
only L in-window is the intended re-pulse, so the AttentionLock RELEASE fade (FADE_FRAMES=8) drives the
untarget latency. (3) **Sim fix in `tww_sim/land/state.py`** (position sect ~536): on the proc-9 BODY
frame the flip sets mNormalSpeed but checkNextMode may have already routed self.state->MOVE for NEXT
frame, so the momentum branch now keys on the DISPATCH `proc` (like the CUT branch) -- else the MOVE
foot path overwrote the flipped speedF to 0. Decomp-faithful (integrate pos with the proc that RAN,
then pick next), GOLDEN-INERT (441 offline pass; goldens never drive the lock). (4) Decomp init/body
split confirmed: procAtnActorMove_init (d_a_player_main.cpp:6294) is commonProcInit+setBlendAtnMoveAnime+
m34D0=20 ONLY -- no setSpeedAndAngle/checkNextMode; proc 9 is a 2-frame tier live (init@26, body@flip),
the sim merges them.

STILL OPEN for full frame-exact 0-ULP (ALL blocked on a JITTER-FREE capture -- single-step is +-1 on
edges, [[run-dtm-1frame-jitter]]; DON'T chase with the single-stepped fixture): (a) the
procAtnActorMove_INIT frame (model as an _atn_actor_entered entry-hold, cf _roll_entered); (b) the MOVE
backslide speedF after the flip (cold foot engine zeroes it; the flip itself is exact -- this is the
foot-warming problem, same class as seeding a MOVE backslide at f0); (c) a from-state-2 full replay
(needs the foot warmed to the -24.57 backslide). THEN gap 2 (chaseAttention range+cone) for the planner
+ build the planner. NEXT: jitter-free per-frame capture (read pad/proc/speedF from RAM at settled
points, or a clean run_dtm free-run) then close (a)/(b) together. Detail: handoff
`_notes/tetrapush-handoff-2026-07-21-session3.md`.

SESSION 4 (2026-07-21): ran the FULL-COUPLED per-frame diff and REFRAMED the whole problem. (1) The
"jitter-free capture" worry was WRONG for this capture: the anim ctrl advances a dead-constant +1.1/f
(roll) / +2.3/f (MOVE), so each captured row IS one game-logic frame; the big per-frame position swings
are REAL coupled physics -- the Link<->Tetra CC plow + roll root-motion (Dereck's correction: "we are
pushing tetra"). (2) Seeding the coupled sim (CcCoupledStepper atn_lock=True, Tetra=Zl1FollowState) at
a roll entry + feeding DTM bytes: **Link roll + untarget flip are BIT-EXACT through the flip under full
coupling** (both cycles). (3) The Tetra plow "divergence" is a **SEED-STARTUP ARTIFACT, not a model
bug** -- live Link<->Tetra feet dist oscillates 41-85u (chase-and-plow); seeding at the roll entry with
no prior push lets sim-Link roll into a stationary sim-Tetra -> false ~70u Co overlap -> co_move_pair
correctly blasts them ~28u apart. The CC model is fine; it must run from **f0 (state 2)** so the push
builds naturally. DON'T touch cc_push/co_move_pair. (4) Root-caused the MOVE-backslide speedF-zero:
`foot_speedf.step_single_anim` (roll/proc-9 pose) warms the toe stream but NEVER sets `self.started`
(the getOldFrameFlg() analog, posMoveFromFootPos d_a_player_main.cpp:2354) unlike step/step_atn/
enter_wait_idle -> MOVE-from-backslide (nspeed<0) hits the cold path, returns 0, can't self-start on
negative nspeed. Setting started=True un-zeroes it (441 offline pass, golden-safe) -- tested then
REVERTED (incomplete: native w_step_single also needs it + residual unclosed + no live gate). (5)
LIVE-CONFIRMED (backslide_probe.py, loadstate 2): the backslide is `speedF == mNormalSpeed` EXACTLY,
`m3598 == 0` every frame -> **NO foot term** (the "cold foot engine" framing was imprecise). The
residual is PURELY mNormalSpeed's decel: live drops 0.275 on the first MOVE frame then ~0.011/f; the
started-fixed sim drops only 0.010. So the crux collapsed to a `setNormalSpeedF`/`dVar9` decel-step at
the ATN_ACTOR->MOVE transition. NEXT: apply started fix to BOTH paths + fix the mNormalSpeed decel
(instrument _set_normal_speed_f at f21 vs the live -25.727->-25.452 drop, decomp-first) + gate vs the
settled f21-25 backslide, THEN seed the coupled sim from f0 (plow artifact resolves). Detail: handoff
`_notes/tetrapush-handoff-2026-07-21-session4.md`. Live addrs (Pp=deref 0x803AD860, Pp-relative):
mNormalSpeed +0x34E4, m3598 +0x34C0, foot_delta_prev +0x34C4, msd_prev +0x34DC, true_speed +0x17C.

SESSION 5 (2026-07-21): RAM+asm-PROVED the real gap and OVERTURNED session 4's "MOVE-decel residual"
framing (Dereck's steer: no guess-and-check, concrete proof from decomp/asm/RAM). The untarget
brakeslide is a **2-frame proc-9 (ATN_ACTOR_MOVE / setSpeedAndAngleAtnActor) tier** in BOTH cycles, not
1: body1 = flip (-26 + ATN term ~0.273 -> -25.727), **body2 = a 2nd setSpeedAndAngleAtnActor frame**
(no re-flip; travel chases target; +ATN term ~0.26-0.275 -> -25.452/-25.486), THEN MOVE decays
~0.0095/f. The sim runs proc-9 body ONCE -> drops to MOVE at flip+1 and MISSES body2. PROOF: breakpoint
at setNormalSpeedF (JP 0x80105ae0) on the drop frame -> param_1(f1)=0.27507579, param_2/3/4=0.5/7.5/4.0
(=ATN_SCL/ATN_ACC/ATN_DEC, the mAtnMove family NOT MOVE's 0.6/2.5/1.8), LR=0x80107c0c INSIDE
setSpeedAndAngleAtnActor (0x80107b24..0x80107c2c). The mCurProc=6 read at that frame's END is
checkNextMode's procMove_init setting the NEXT proc early (not the body that ran). Root cause: the
actor-lock (mpAttnActorLockOn) drops **1 dispatch-frame too early** in the sim. Driving the sim's lock
from the RAM-measured mpAttnActorLockOn timeline (verify_2frame.py) reproduces the 2-frame tier -- flip
bit-exact, body2 off only 0.0024 (mid-roll-seed travel/csangle imprecision, NOT a model error). The
FADE_FRAMES=constant model is PROVEN WRONG: RAM mLockOnState RELEASE lasts 10 frames (cyc1 f11-20) vs 11
(cyc2 f37-47) -> untarget latency is the reticle YJ_DELETE anim completing (d_attention.cpp runDrawProc
692-698 clears AttnFlag_40000000), NOT a fixed count. NEW live addrs (fopAc-relative, la=this-0xD8;
this=deref 0x803AD860): mpAttnActorLockOn this+0x30C4 (hdr 0x319C), mpAttention this+0x33A8 (hdr 0x3480)
-> dAttention_c: mLockOnState +0x18, mFlags +0x20 (AttnFlag_40000000), draw[0].anm +0x038; mMaxNormalSpeed
la+0x2A8 (12 locked/17 free); m34E8 la+0x34E8. JP fn addrs: setNormalSpeedF 0x80105ae0,
setSpeedAndAngleNormal 0x80107474, setSpeedAndAngleAtnActor 0x80107b24, procMoveTurn_init 0x80111874.
JP framework.map: C:\Users\pinhi\Documents\TWW JP Extract\files\maps\framework.map. NEXT: model the
actor-lock lifetime decomp-faithfully (reticle YJ_DELETE anim frame ctrl, NOT a magic FADE const;
mind the attention's L-input delay differs from physics INPUT_DELAY=2 -- LOCK engaged f8 vs acted-L f9),
so proc-9 runs 2 body frames; then the started/getOldFrameFlg fix for the MOVE backslide after; then
from-f0 coupled replay + gates + live 0-ULP. Reusable probes in _notes/tetrapush-{live_lock_probe,
bp_setnormalspeedf,verify_2frame}.py. Detail: handoff _notes/tetrapush-handoff-2026-07-21-session5.md.

SESSION 6 (2026-07-21): CLOSED the actor-lock-lifetime gap; the sim now runs the 2-frame proc-9 tier
from the REAL AttentionLock (no RAM-timeline injection), lock timeline matching live RAM
mpAttnActorLockOn bit-for-bit (cyc1 LOCK f8-10/RELEASE f11-20/drop f21; cyc2 f32-36/f37-46/f47
de-duplicated). Flip stays bit-exact; body2 lands (off ~0.0024 mid-roll-seed; ULP-exact awaits from-f0).
Two decomp-grounded, LIVE-MEASURED fixes (no guessed constants), via new probe
`_notes/tetrapush-reticle_probe.py` (reads the reticle J3D frame ctrl): (1) **untarget latency = the
reticle YJ_DELETE anim = FIXED 10 frames** (McaMorf frame ctrl end=10/rate=1.0/EMode_NONE; McaMorf at
mAttention+0x38, frame ctrl +0x58 -> mFrame+0x68/mEnd+0x60). Session-5's "10 vs 11" was a SINGLE-STEP
CAPTURE DOUBLE-READ (Link anim ctrl byte-identical across cyc2 f44==f45), NOT a real variation --
FADE_FRAMES=10 is faithful (anim length, not a knob); AttentionLock.DEFAULT_FADE_FRAMES 8->10. (2)
**attention L-input delay = 1** (vs physics INPUT_DELAY=2): field_0x01a (mAttention+0x1a) rises/falls
exactly 1 frame after the raw DTM L on both edges; state.py feeds _atn.update the delay-1 L (_inbuf[0]
after the delay-2 pop), NOT physics l_held. Purely additive (443 offline pass incl. 16 goldens
byte-identical; gate tests/test_tetra_untarget.py::test_untarget_2frame_tier, both cycles). NEXT
(unchanged, now un-blocked): the started/getOldFrameFlg fix for the MOVE backslide AFTER the tier
(re-confirmed s6: without it cyc1 f22-25 read 0 vs live -25.44; foot_speedf.step_single_anim must set
self.started like step_atn does -- AND native w_step_single) + the from-f0 coupled replay (its only
consumer) + live 0-ULP, together with a proper live gate. Detail:
_notes/tetrapush-handoff-2026-07-21-session6.md.

SESSION 8 (2026-07-22): went LIVE from slot 2 for the from-f0 replay and DERIVED + GATED the Tetra-plow
law; found the real from-f0 blocker. (1) **The CC split at the Courtyard push is Tetra-100%/Link-0%,
NOT 50/50** (frac = tetra_move/overlap_depth = 1.000 measured over 40 consecutive frames, both cycles).
Tetra absorbs the FULL Co overlap depth each frame; Link's push share is 0 -- the dCcS rank split when
Link out-ranks Tetra during her stt-3 "being pushed" state (opposite of the type-5 FOLLOWING Tetra's
50/50 in [[tetra-push-model]]). (2) **Link's push Co centre = his ANIMATED mCyl centre** (setCollision
root/neck midpoint, d_a_player_main.cpp:9748), read live at lp+0x4064 -- NOT current.pos; leads the feet
6-28u through the backslide/roll pose. roll_co_center reproduces it given the LAGGED draw-base position
(d 8-17u -> 1.4-8.9u; residual = draw pos lag). (3) **Gated deliverable:** harness/tetrapush/tetra_plow.py
(the law: Tetra += depth*unit(Tetra-link_centre), depth = (30+50)-dist) + tests/test_tetra_plow.py --
reconstruct Tetra's WHOLE trajectory from Link's mCyl-centre path + seed to <0.01u over 40 frames (frac
1.000 every frame). This IS the planner's Tetra-trajectory predictor given Link's centre path. (4) **New
live ground truth** fixtures/courtyard_push_cyl.json (per-frame Link mCyl centre + csangle + Tetra pos,
single-stepped); capture_push + dtm_inputs extended to log Co centre + csangle + shape.z. NEW ADDRS
(lp = deref 0x803AD860): Co-cyl centre lp+0x4064 (r lp+0x4070=30, h lp+0x4074~104.6; AABB lp+0x4044),
mStts lp+0x3FE8 (m_cc_move +0, weight +0x14), shape.z la+0x210; csangle = chain [[0x803AD380]+0x34]+0x2B0
(u16). (5) **THE from-f0 blocker is now Link's OWN slowdown, precisely posed:** live Lmove + Tmove ~=
Link speed each push frame, i.e. Link's ground move = speed - depth (a roll at speedF 26 advances only
7-17u). So Link recoils by depth AND Tetra advances by depth -- EACH the full cross_len (total 2*depth),
NOT the fractional co_move_pair 50/50. The sim applies Link's FULL speedF, so a from-f0 Link replay
drifts ~250u (roll dir/pos diverge -> untarget cone mis-fires). Model this Link-side slowdown decomp-
first (SetPosCorrect for Link>>Tetra rank, or each actor resolving the full penetration) NEXT; the Tetra
plow (done) then rides the correct Link path. (6) **cyc2's untarget is single-step-edge-jittery** -- a
re-capture exited the roll to +26 decaying, NOT the -25.7 flip; the pinned courtyard_push_dtm.json is
IMMUTABLE (I overwrote it, caught it via the flip values, `git checkout`-restored) and the deterministic
from-f0 replay disambiguates cyc2. From-f0 mechanical scaffold understood (input pre-seed _inbuf=[inp[-1],
inp[0]] -> step inp[1..], foot warm, INJECT captured csangle not model the camera, pending-push pre-seed).
450 offline pass. Detail: _notes/tetrapush-handoff-2026-07-22-session8.md.

SESSION 9 (2026-07-22): CLOSED the session-8 from-f0 blocker ("Link's own slowdown") as a LAW +
gated it, mirror of the Tetra plow. Measured off fixtures/courtyard_push_cyl.json (scratch vec_decomp):
on EVERY push frame Link's recoil = the FULL Co overlap depth directed AWAY from Tetra along the
centre-to-centre line (recoil/depth == 1.000, recoil.dir == centre->Link, to 0.1deg). So Link's net
ground move = foot term (POST-update speedF along current.angle.y) MINUS full depth away from Tetra;
BOTH actors eject the full cross_len (2*depth total sep -> the live 41-85u chase-and-plow oscillation).
This OVERTURNS session-8's "Tetra 100%/Link 0%" -- Link is NOT 0%, he ejects the full depth too (the
mirror). Feet reconstruction from f0 (feet + speedF[i+1]*dir(travel[i]) + full-depth recoil) tracks live
to <0.01u on ALL roll frames (cyc1) / <0.0025u (cyc2), <0.06u on the single-step-jittery backslides;
only the mid-frame speed-FLIP frames (proc-7 re-target, proc-9 entry) and the f44 double-read miss.
DELIVERED: harness/tetrapush/link_plow.py (recoil()/recoil_step(), reuses tetra_plow.plow_depth) +
tests/test_link_plow.py (3 green: frac==1.0 all push frames; recoil vector + feet reconstruction
0-ULP-within-jitter on the clean roll frames). 453 offline pass, land goldens byte-identical (standalone,
not wired into LandState). DECOMP: dCcS::SetPosCorrect (d_cc_s.cpp:180, JP 0x800ab1e4 -- CONFIRMED
halting live) Link=obj1 side gives Link cross_len*obj2Weight along (link-tetra); the NET m_cc_move
delivered to Link is the FULL cross_len (obj2Weight==1.0 measured). OPEN SUB-PUZZLE (not a blocker, the
law is derived+gated): the static decomp gives a SINGLE SetPosCorrect/pair/frame (ChkCo unordered pairs
once; Ccsp Move once/frame d_s_play.cpp:287) and Link(120,rank5) vs Tetra(temp=0x8C=140,rank5) is a
50/50 split (0.5*depth each) -- HALF what live does; the 2x doubling source is unpinned (candidates:
the immediate *ppos+=vec writes d_cc_s.cpp:267-268 on top of deferred m_cc_move; a 2nd resolution;
SetMass/mMass_Mng -- but Tetra registers no mass). Pin next session via posMove entry (JP 0x80106514):
read Link m_cc_move before consume, is it 0.5*depth or full? Live SetPosCorrect reg-probe was fragile
(struct offsets); the fixture already live-confirms the law so it wasn't needed. Distinct from the
FOLLOWING-Tetra sandbox 50/50 (cc_stepper) -- keep that default, add a Courtyard full-depth mode. NEXT:
from-f0 replay = model the MOVE-phase Link Co centre (or inject fixture cyl) + wire link_plow+tetra_plow
into a coupled stepper + seed f0 + feed DTM bytes/csangle + per-frame diff (cyc1 clean). Detail:
_notes/tetrapush-handoff-2026-07-22-session9.md.

SESSION 10 (2026-07-22): BUILT the from-f0 coupled replay + gated cyc1 bit-exact (the s9 "wire it
together"). NEW `harness/tetrapush/from_f0.py` (`full_depth_push()`+`replay()`): closed-loop LandState
(Link) + tracked Tetra XZ, seeded at f0 or a roll entry, driven by the real DTM bytes, applying BOTH
gated plow laws (link_plow recoil + tetra_plow push, each FULL depth from Link's Co centre) with Link's
mCyl Co centre + csangle INJECTED per frame (defers the MOVE-phase Co-centre model). Tetra is stt-3/
speedF-0 the WHOLE ~45f window -> pure plow, NO follow leg (verified from the cyl-fixture timeline).
Courtyard-specific mode; general cc_stepper/co_move_pair 50/50 untouched. GATE tests/test_from_f0.py
(4 green): seeded at the first roll entry (f3), cyc1 -- FRONT_ROLL + the 2-frame ATN_ACTOR untarget tier
(flip -25.727313995361328 + body2 -25.452238082885742) + the MOVE backslide, f4-23 -- reproduces EVERY
live speedF 0-ULP and Link pos within the injected-cyl single-step capture precision (max 6.1e-5u); and
Tetra's full-depth plow FROM f0 reproduces her whole trajectory <=9 ULP / <1.4e-4u over the plow window
BOTH cycles. 457 offline pass, land goldens byte-identical (additive, no library change). Gate reads
cyl/csangle from courtyard_push_cyl.json + raw inp from courtyard_push_dtm.json (the DTM fixture has no
baked cyl/csangle); both self-contained for f<=43 (cyc2 f44==f45 double-read is past the gated range;
_dedup drops it). THE NEW BLOCKER (diagnosed via per-frame diff): the backslide->roll-setup transition
(MOVE->ATN_MOVE re-target, speedF ~-25 -> +18 just before each roll) -- why cyc2 doesn't chain + f0 seed
isn't bit-exact. TWO 1-frame timing issues: (1) proc-7 ENTRY is 1f late -- checkNextMode r24
(checkAttentionLock) uses physics delay-2 L but live routes on the attention's DELAY-1 L (s6); gating
r24 on `_inbuf[0]` (the l_atn already computed at state.py:338) fixes the entry, cyc1 stays bit-exact
(monkeypatch-verified) -- but (2) the +18 re-target flip is THEN 1f late the other way (live f28, sim
f29): setSpeedAndAngleAtn DIR_FORWARD/BACKWARD split + ~180deg travel chase, a multi-frame subtlety
needing a jitter-free live probe (single-step is +-1 on this edge). DON'T half-ship the delay-1 change
(fixes entry not flip, touches hot dispatch). Model the WHOLE re-target decomp-first + gate the full
chained replay. THEN f0 seed also needs the prior cycle's attention-RELEASE residual seeded (f0 = mid-
fade -> proc 7 f1-2 with no L; fresh NONE seed can't reproduce). GOTCHA: my scratch delay1_test.py
showed a FALSE cyc1 explosion (test artifact) -- a controlled same-process A/B confirmed the patch is
safe; Tetra's plow is INJECTED-cyl-driven so 0-ULP even while Link's setup is open (don't read a Tetra
match as Link validation). Detail: _notes/tetrapush-handoff-2026-07-22-session10.md.

SESSION 11 (2026-07-22): SOLVED the backslide->roll-setup blocker; the from-f0 replay now CHAINS
bit-exact through cycle 2's roll. Seeded at the first roll entry, f4..f44 is 0-ULP (every speedF, every
proc, Link pos <1.4e-4u) -- cyc1 + the whole MOVE->ATN_MOVE +18 re-target (proc-7 entry f26, flip f28
-25.15->+18.574, cyc2 roll f29) + cyc2 roll. Gate tests/test_from_f0.py::test_chained_replay_through_
cyc2_roll_bit_exact (stops f44, before the cyl fixture's single-step-jittered cyc2 untarget f45+).
ROOT CAUSE (LIVE-PROBED, _notes/tetrapush-retarget_probe.py -- the deferred jitter-free probe, DONE):
the flip landed 1 frame late because the DTM-driven replay ran at INPUT_DELAY=2, but **the DTM stream
IS the polled g_mDoCPd pad, already ONE pipeline stage in, so a DTM replay is delay-1**. The probe
single-stepped slot 2 logging the delivered pad + m34DC/m34E8 (stick target, la+0x34DC/la+0x34E8) +
mDirection (la+0x34B8) and found m34DC[k]=DTM_inp[k-1] UNIFORMLY (stick target, roll-A, soft-lock L all
land 1 frame after the DTM). The +18 is setSpeedAndAngleAtn's DIR_BACKWARD negation (mNormalSpeed*=-1,
travel+=0x8000, d_a_player_main.cpp:2863) firing when the big off-axis re-target arrives -- at delay-1
that's inp[27] at f28 (|m34E8-travel|>0x6000 -> BACKWARD), not inp[26] at f29. FIX = one clean param
LandState(input_delay=1): at 1 the physics AND attention both act on the delay-1 pad (no ahead-by-one
split); shipped default stays 2 (raw-controller latency, walk goldens untouched -- 458 offline pass,
goldens byte-identical). from_f0 seeds input_delay=1 + a 1-frame _inbuf. SUPERSEDES the s10 "gate r24 on
delay-1 / model the DIR flip separately" plan -- those per-consumer delay-1 hacks BROKE the EBS/brakeslide
goldens (the delay is a whole-pipeline property, not per-consumer; goldens are immutable live truth).
Decomp facts confirmed en route (not needed by the fix but grounded): checkNextMode r24 = checkAttentionLock
= LockonTruth() || AttnFlag_20000000 (the soft-lock, L held no actor, d_attention.cpp:872-889);
setSpeedAndAngleNormal's facing chase + reversal branch gate on !checkAttentionLock (2763/2834) so a MOVE
proc freezes facing under the lock; m34E6=shape_angle.y latches every checkAttentionLock frame in
setAtnList (2067). REMAINING: the TRUE f0 seed (state 2) -- all procs match from f0 but f1-f2 speedF off
~0.4/0.2 (Link is mid-backslide from the prior cycle's untarget; the seed needs the prior-cycle mDirection
[live la+0x34B8=4 at f0] + the AttentionLock RELEASE residual). Small; the chained physics is proven.
THEN the planner. Detail: _notes/tetrapush-handoff-2026-07-22-session11.md.

SESSION 12 (2026-07-22): CLOSED the TRUE f0 seed; the from-f0 replay is now bit-exact from STATE 2
itself (not just a roll entry) -- f1..f44 every Link speedF 0-ULP, procs match, Link pos within capture
precision (max 1.4e-4u). ROOT CAUSE (live-probed, `_notes/tetrapush-seed_probe.py` reading the hidden
f0 fields, NOT a guess): at f0 Link is mid-transition out of the prior cycle's untarget where **speedF
LAGS mNormalSpeed by a frame** -- live f0 speedF -24.573892593, mNormalSpeed -24.982038498 (bits
c1c7db37). The replay seeded `nspeed = speedF`, so f1 (a MOVE backslide, which can ONLY decay toward 0)
gave -24.572 instead of letting speedF catch up to the already-set nspeed -24.980. **The whole fix is
seeding nspeed from the live mNormalSpeed**; f1 then reads -24.980 bit-exact and the +18 re-target flip
(f2 18.490) + cyc1 roll (f3) + the cyc1->cyc2 chain all follow, 0-ULP. The session-11 "seed the
prior-cycle mDirection + attention RELEASE residual" hypothesis was a **RED HERRING**: live f0
mDirection=4=DIR_NONE and the attention is NONE/no actor -- both already the sim's fresh-LandState
defaults (confirmed live). NEW deterministic seed capture (single read, no single-step jitter):
`python -m harness.tetrapush.capture_push seed` -> `fixtures/courtyard_push_seed.json` (the complete f0
state incl. mNormalSpeed + mDir/m34E6/attention for provenance). `from_f0.replay(..., seed_nspeed=)` +
`_seed_link(seed_nspeed=)` thread it; `capture_push._snap` now also logs nspeed. Gate
`tests/test_from_f0.py::test_true_f0_seed_bit_exact` (f1..f44 0-ULP). 459 offline pass, land goldens
byte-identical (ADDITIVE -- no tww_sim library change, purely harness/tetrapush + fixture + test). New
addr used: mNormalSpeed la+0x35BC (== lp+0x34E4), mStickDistance la+0x35B0, m34E6 la+0x34E6, attention
mLockOnState [lp+0x33A8]+0x18, actor-lock lp+0x30C4. From-f0 replay COMPLETE. NEXT: the planner
(state-2 config -> input-seq search landing Tetra on a genuine `_generated/tetra_placements.tsv` coord
AND arranging the matching roll entry; method ref = plan_land/the seam-clip solver, cheap predictor +
exact bit-confirm, no calibration). Detail: _notes/tetrapush-handoff-2026-07-22-session12.md.

SESSION 13 (2026-07-22): STARTED the planner and hit its real prerequisite -- the from-f0 replay
INJECTS Link's mCyl centre + csangle per frame, which a planner exploring NOVEL inputs cannot do; the
push fires EVERY frame (Link<->Tetra centre dist 61-79 < 80 all window) so the MOVE/ATN-phase centre
matters, not just rolls. BUILT the self-contained centre machinery + validated the FK; found and
LEFT OPEN the mCyl timing law. (1) **FootFK body-Co mode** (core/anim/foot_fk.py `body_co=True`):
poses the neck chain [0,1,2,3,4,14] alongside the foot joints; `body_co_center(px,py,pz,facing,lean)`
rebuilds setCollision's root/neck world midpoint from the stored old pose (position-independent
LOCAL storage -> re-accumulate at any base), incl. the jointBeforeCB body_chn extra rot
Q(-mBodyAngle.z,0,0) (d_a_player_main.cpp:289; :9526 mBodyAngle.z=shape_angle.z; x/y attention twists
LIVE-PROBED 0 all window). (2) **state.py proc-8/9 frames now pose the real ATN blend** (step_atn +
entry morf on the routing frame; procAtnActorMove calls the same setBlendAtnMoveAnime :6299/:6308) --
was step_single_anim on the stale rollf ctrl; speedF untouched (m3598==0), 459 offline + goldens
byte-identical. (3) **f0 pose seed** (from_f0._seed_pose_f0 + replay(centers='computed')): state 2 is
regime-3 DASH cruise so the hidden anim state = ONE phase (cyl fixture link.anim=25.4, rate 2.3) +
lean (shape_z<<1=648); old pose warmed with 2 pure-dash poses. (4) **VALIDATED: the FK == the game's
draw-final anm matrices ~6e-5u** on every settled roll frame (live nodeMtx probe: mpCLModel la+0x32C
-> mpNodeMtx J3DModel+0x8C, 0x30/joint; _notes/tetrapush-anmmtx_probe.py + upper_probe.py + .json
dumps). Proc-9 frames still 3.8-8.1u off (ATN side/direction pose detail) and f1 ~2u (warmup approx).
(5) **OPEN -- the mCyl TIMING law:** the captured/pushed mCyl(k) (self-consistent with Tetra's gated
plow!) equals NEITHER mid(k) nor mid(k-1) of the draw-final matrices (0.3-9u, deterministic per cycle
phase; alignment sweeps, implied-base solves, mixed root/neck-timestamp fits ALL fail). setCollision
(:9748) is a plain midpoint SetC (no smoothing) -- it must read matrices at a mid-frame state the
pause boundary never shows. **NEXT = breakpoint JP setCollision (US 0x8011D788 -> framework.map) and
read mpNodeMtx[0/14] at hit time + find its caller position in execute.** DECOMP structure learned:
UNDER/UPPER anim part split (root+center+legs UNDER, body_chn subtree UPPER via
getJointNodePointer setMtxCalc :11574-11576; setMoveAnime/setSingleMoveAnime fill BOTH tables, upper
falls back to the UNDER bck when no upper variant exists -- courtyard window plays no distinct upper
anim, upper ratios probe-confirmed); morf ranges DIFFER by call site (roll initOldFrameMorf(2.0,0,0x2A)
vs setActAnimeUpper [BODY_CHN,WAIST_CHN) :12863 -- sim's global [0,0x2A) matches the paths gated so
far). Also: cap cyl(k) ~ pose/base of k-1 (the lag alignment, e_lag << e_same) -- the s8 "draw
position lag" note was this, never actually pinned. csangle remains injected (camera_exact models
only the C-stick omega path; the follow-camera chase drifts ~6 BAM/frame max -- planner-relevant,
unmodeled). New addrs in README ## Addresses (mBodyAngle la+0x2B4, mAnmRatio* la+0x2FB4/0x2FC4,
mFrameCtrlUnder/Upper la+0x302C/0x3054, mpCLModel la+0x32C). Detail:
_notes/tetrapush-handoff-2026-07-22-session13.md.

SESSION 14 (2026-07-22): CLOSED the mCyl TIMING LAW (the s13 blocker) + SOLVED the s9 "2x doubling"
sub-puzzle, both breakpoint/watchpoint-pinned live. (1) **setCollision (JP 0x8011a670, framework.map;
sole caller execute+0x119c, once/frame) writes the plain root/neck nodeMtx midpoint AT CALL TIME**
(<=6.1e-5u every probed frame): the EXECUTE-pass matrices (mpCLModel->calc() :11591 after posMove
:11407, before the scene CC pass), at the pause-boundary current.pos. s13's 0.3-9u residual was
comparing against the DRAW-pass matrices (different, lagged base) -- never use pause-boundary nodeMtx
as the setCollision source. (2) **The pause-boundary mCyl (what the fixtures log + the gated plow laws
consume) = exec midpoint + the dCcS immediate HALF-DEPTH SetPosCorrect write** (watchpoint on lp+0x4064:
second writer LR 0x800ab5d0; delta == 0.5*recoil(exec,tetra) == recoil(fix,tetra) exactly, f1..f12).
So there IS no 2x: both actors take the plain decomp 50/50 split of the EXEC-centre overlap; measured
from the SETTLED centre it reads as full depth -- the gated full-depth laws are the settled framing of
the same numbers, unchanged. `from_f0._cc_settled_center` encodes the map; computed mode = FK exec
midpoint -> settled. (3) Baked fixtures/courtyard_push_setcol.json (probe f1..f12: nodeMtx@hit +
cyl_exec); gates test_from_f0::{settled_center_law_half_depth, setcollision_is_execute_time_midpoint,
computed_centers_track_on_settled_roll_frames} (+ a 'diag' replay mode: injected pushes, computed-centre
diffs). 462 offline green, goldens byte-identical. Open-loop the computed centre is <2e-3u on EVERY
settled single-anim roll frame (many ~1e-5u); closed-loop procs+speedF chain to f28. (4) **Remaining
POSE gaps enumerated** (the new blocker, largest first): proc-9 ATN blend f19-21 (4.6-8.5u), its
post-untarget morf decay f22-26 (1.1-3.0u), f0-seed warmup f1 (1.8u) + roll-entry morf f3 (1.2u), blend
residue f14-16/f29-38 (0.03-0.3u). These drift the closed loop so cyc2 diverges past f28. (5) Live setup
hard-won: TWW-JP.iso (NOT twwgz -- wrong iso = clean Dolphin exit after loadstate 2) + MMU=True (else
silent load abort) + play the companion StateSaves/GZLJ01.s02.dtm before loading slot 2
([[tetrapush-real-tas-iso]], [[dolphin-mmu-required]], README "## Live setup"). Probe
_notes/tetrapush-setcol_probe.py. Detail: _notes/tetrapush-handoff-2026-07-22-session14.md.

SESSION 15 (2026-07-22): CLOSED the proc-9 POSE gap (the s14 blocker, items 1+2 of the handoff list)
via THREE decomp-pinned fixes; facing + m351C lean now BIT-EXACT f1..f43 and the computed centre is
<2e-3u on ALL settled frames (f19-20 ~2e-5; f27-43 <2.5e-4; f21-26 morf tail <=0.35), zero physics
perturbation (463 offline green, goldens byte-identical). (1) **mDirection actor-lock gate**
(procs/atn.py `_update_atn_direction`): setBlendAtnMoveAnime's FORWARD/BACKWARD branch requires
mpAttnActorLockOn==NULL (:3299) -- locked can only go SIDE, so the untarget tier poses atnd{l,r}s@1.8
(sim was posing dash/atndb). (2) **Routing-frame pose timing** (state.py): checkNextMode TRUE skips the
body's setBlendAtnMoveAnime (:6307) and a proc *_init (incl. its pose) runs on the NEW proc's FIRST
dispatch frame (the mCurProc==X guard) -- so body2 advances the atnd ctrl with NO pose and
procMove_init's setBlendMoveAnime(2.4) fires on the first MOVE frame (atnd@3.6 -> dash@6.4 = 3.6/18*32;
the sim now runs the walk pose/pending-morf there instead of step_atn). The s13 upper_probe under-anim
frame/rate stream is now matched EXACTLY f1-28. (3) **The re-aim law** (procs/atn_actor.py):
setShapeAngleToAtnActor chases the bearing to the actor's **eyePos** (fopAc+0x260; Tetra's = her
ANIMATED head-joint world pos, d_a_npc_zl1.cpp:1283, leads her feet 16-26u) and no-ops while
mpAttnActorLockOn==NULL (:2627 -- body2 runs one frame past the lock drop, must NOT re-aim). Live-pinned
(_notes/tetrapush-eyepos_probe.py -> fixtures/courtyard_push_eyepos.json; lock non-NULL f8-f20 NULL
f21+): eye-aim = facing 37548 exact, feet-aim 184 BAM short + ghost f21 re-aim +432; the facing error
fed the m351C lean sawtooth (setMoveSlantAngle tgt = 1.6*(m34DE-facing)*ratio, m34DE = PREV facing).
replay(..., eyes=) injects the eye stream like csangle; the planner's eyePos model (her look-at anim
chasing Link) is OPEN. Gates: test_facing_and_lean_bit_exact_with_eye_aim + extended
computed-centre ceilings. **NEW BLOCKER pinned + partially root-caused: a systematic dash-backslide
ROOT-pose XZ bias ~0.1-0.4u** (f22-25; the f0 seed pose shows the same 0.42/0.72u root/neck XZ gap) --
ruled out: lean scale, 1-frame phase lag, dashs-vs-dash (root content identical; NB live m3562=0x103,
sword IS drawn all window, physics-inert), m34EC + shape.x (0), the Y gap (= m35B8 -5.198 footBgCheck
draw-base shift, XZ-irrelevant), m34F2/F4 (0), and the f0 waist-twist residual m34E0=1325 (decays
(2,0x800,0x200) to 0 by f3; jointBeforeCB WAIST_JNT=30 = LEGS subtree only, not the neck chain).
Left: upper-part phase, wind-ish m3730/m36B8, morf residue. This bias is what blocks the CLOSED-LOOP
computed replay: the plow coupling has POSITIVE FEEDBACK (centre bias -> depth=80-dist -> both actors
shoved -> bias compounds ~1.3x/frame -> tens of units by f19, common-mode; speedF/procs stay exact
thru f25). Probes: _notes/tetrapush-{eyepos,waist}_probe.py + reused upper/anmmtx JSONs. Detail:
_notes/tetrapush-handoff-2026-07-22-session15.md.

SESSION 16 (2026-07-22): CLOSED the SELF-CONTAINED Co centre -- the planner prerequisite is DONE.
FOUR decomp-pinned exec-pose laws (all breakpoint-verified at JP setCollision 0x8011a670 via NEW
joint-by-joint nodeMtx chain probes, _notes/tetrapush-{chain,setframe}_probe.py): (1) **BODY_CHN twist
= the NEW lean** (setMoveSlantAngle re-sets mBodyAngle.z between setWorldMatrix and mpCLModel->calc,
:11551/:11561/:11591; the old-lean error only shows across JMAEulerToQuat half-angle>>4 sin-table
buckets -- why it toggled per frame); (2) **J3D SEGMENT-SCALE-COMPENSATION on the neck chain**
(stomach/chest/neck scale_compensate=1; dash bck scales stomach_jnt.x 0.91-1.07; mDoExt_setJ3DData:47
row-scales the child 3x3 by 1/parentS) -- THIS WAS the s15 "dash-backslide root-pose XZ bias" (neck
sat scale_err*22.26u off; also the f0-seed gap); (3) `_local_from_old` passed body_x to euler_to_quat
UNSIGNED (game halves a SIGNED s16: -1 BAM = identity, masked = -32-BAM ghost -- the f14/15 residue);
(4) **proc-init frames have ZERO base lean** (commonProcInit zeroes shape_angle.z :5841 BEFORE
setWorldMatrix; setMoveSlantAngle restores after -- live f1/f3 base row0[1]==0.0 exactly; from_f0
flags init frames off the post-step proc stream). Plus seed upgrades: capture_push seed now dumps the
live m_old_fdata store (lp+0x30DC; TransformInfo* +0x1C, Quaternion* +0x20 x,y,z,w) + morf counters ->
fixtures/courtyard_push_seed.json old_pose (at this seed == pure-dash warmup bit-for-bit, kept for
general correctness); the SEED frame's own Co centre stays captured data (computing it needs f-1's
m351C). RESULT: diag centre <3e-4u on EVERY frame f1..43 (capture precision, no open pose gaps);
CLOSED LOOP (centers='computed') chains from state 2 with every proc/speedF/lean 0-ULP f1..43, facing
<=+6 BAM (eye-aim echo of the amplified noise), positions amplify the fixture's ~1e-4 single-step
noise ~1.35x/frame COMMON-MODE (pair drifts together; contact dynamics exact -- irrelevant for a
novel-input planner, which has no reference to drift from; the end DTM check is the exactness gate).
Gates: test_computed_centers_... rewritten all-frames <3e-4 + NEW
test_closed_loop_computed_replay_dynamics_bit_exact. 464 offline green, goldens byte-identical
(library change = foot_fk body-co rebuild only). GOTCHAS: morf counters read at a setCollision hit
are POST-calc (dec fired); OPEN flag -- foot chains 30/33/38 also have SSC and ANM_SLIP scales
jnt37 1.2 (game compensates at 38, sim's foot path doesn't, yet slip is live-validated; start there
if a slip pose gap surfaces). NEXT = the planner (csangle ~6 BAM/frame drift + Tetra eyePos [probe
range f0-28] to model or bound). Detail: _notes/tetrapush-handoff-2026-07-22-session16.md.

SESSION 17 (2026-07-22): built the planner's NOVEL-INPUT scaffold + characterized (not yet modeled)
the two remaining injected quantities. (1) **from_f0.FreeRun**: the replay loop refactored into a
seed-once/step-any-raw-input class (computed centres; csangle/eye per-step injectables); replay is
now a thin WRAPPER over it so every existing 0-ULP gate gates the planner path; gates
test_freerun_direct_api_matches_replay + test_freerun_warns_when_tetra_would_follow. **FOLLOW guard
(Dereck's steer): the sim must NEVER model Tetra entering stt-4 follow -- FreeRun warns (once) the
first frame 3D Link-Tetra dist > npc_zl1.FOLLOW_ENGAGE_DIST (230); live flips AT-or-AFTER the
crossing (s17 probe: crossed 231.9 f63, stt 4 f75), so the warning is conservative; treat it as
"candidate infeasible".** (2) **csangle: the s16 "~6 BAM/frame" note was WRONG** -- capture shows up
to 116 BAM/frame (camera chasing the backslide); sensitivity ~2.4u lateral Tetra drift/cycle/100 BAM
vs the 2u-wide placement band. Decomp recon (README ## The follow camera): csangle = mAngleY =
angle(mEye-mCenter)+0x8000 re-derived EVERY frame (Run :905) -- EMERGENT from followCamera (mode 0,
style FN08) eye/center springs; full L-lock (LockonTruth incl. RELEASE) switches to lockonCamera
(mode 2) EVERY untarget cycle; yaw rate m3B8 = f(MAIN-stick X via rationalBezierRatio -- EMPTY in
the decomp, pin live at the JP bp); C-stick on land = mode requests only (recenter/peek), NOT orbit;
GOTCHA cSGlobe getter/setter fields SWAPPED (getter U()==mInclination==the yaw, globe+0x06). The
swim camera_exact recurrence does NOT transfer to land. dCamera_c = camera_class+0x244; mAngleY
+0x6C; hidden spring state mWork +0x378 -- s17 dumped it RAW per frame f0..f120
(_notes/tetrapush-eyeindep_probe.json cam_raw, 0x450 B/frame) = the port's oracle + f0 seed. (3)
**eyePos is INPUT-DEPENDENT -- the "stt-3 disables look-at" shortcut DISPROVEN live** (A/B probe,
runs diverge only in post-f48 inputs: eye-feet offsets diverge from f51 while BOTH runs still stt 3;
her stt-3 action re-arms field_0x84D=1). Model = lookBack -> dNpc_JntCtrl_c::lookAtTarget_2
(d_npc.cpp:828-915; target dNpc_playerEyePos(-20) = player head-top height over FEET XZ; addCalcAngleL
scale 4, steps 0x1000/0x0180, head/backbone clamps in README) + wait.bck head-joint FK +
_nodeCB_Head half-angle twist + (20,-16,0) offset (d_a_npc_zl1.cpp:166-182,:1258-1262,:1283). (4)
Planner scoping: placement band = 48u x 2u strip; ~337u herd left from capture end (~1.5 cycles);
Link entry ~260u away. (5) Live gotchas: ensure_running() boots the WRONG iso for this work (twwgz)
-- rebuild = kill Dolphin, relaunch, pipe op `playmovie` (NOT `play`, that's the CLI verb) with
StateSaves/GZLJ01.s02.dtm + TWW-JP.iso, wait playing:true, then loadstate 2; control_pipe_quiet
returns a JSON STRING. 466 offline green, goldens untouched. Detail:
_notes/tetrapush-handoff-2026-07-22-session17.md.

SESSION 7 (2026-07-21): TWO decomp-grounded, golden-safe closures (offline-only, no live gate this
session; 445 offline + 16 land goldens byte-identical). (1) **started/getOldFrameFlg fix DONE, both
foot paths.** foot_speedf.step_single_anim (Python) + w_step_single (native _anmc, rebuilt) now set
started like step_atn/enter_wait_idle/enter_single -> the MOVE backslide after the proc-9 tier no
longer takes FootSpeedF.step's cold `not started and nspeed<=0` path returning 0 (pre-fix probe: cyc1
f22-25 & cyc2 f48-55 read 0.0). With the fix the backslide is pure momentum (m3598==0 -> speedF ==
mNormalSpeed BIT-EXACT) tracking live within the mid-roll-seed budget (cyc1 <=0.0024, cyc2 <=0.0005 with
the +1 capture-shift value-alignment). GOLDEN-SAFE because every real roll/slip/WAIT_TURN enters via
enter_single FIRST (already sets started), so step_single_anim's set is inert in all existing paths --
only bites the direct-seed (couple_replay / from-f0) convention. Gate:
tests/test_tetra_untarget.py::test_untarget_backslide_unzeroed. (2) **Gap 2 (chaseAttention acquisition
cone) MODELED decomp-first + live-geometry-gated.** chaseAttention (d_attention.cpp:563) gates the
lock-on target on the FRONT-OF-PLAYER cone (check_flontofplayer): chaseable only within +-0x4000 (90deg)
of shape_angle.y (ftp bit 0x04 -> ang_table[0]; Tetra dist_table[0xAB]; already in
knowledge/mechanics/tetra-follow.md). This IS why the lock acquires MID-ROLL not at the first held L: at
state 2 Tetra is ~122deg BEHIND Link (out of cone -> live proc 6/7 no actor); only the roll swings Link
to face her (~0-2deg) so the mid-roll L re-pulse acquires. state.py now feeds _atn.update a cone-gated
target_present = _AtnActorMixin._atn_target_present() (reuses the setShapeAngleToAtnActor bearing;
attention.FRONT_CONE_HALF=0x4000). Golden-inert (no actor -> False -> machine NONE). A BARE non-coupled
replay (tier test) can't compute the real cone (its rolled pos diverges ~100u w/o the CC plow) so it
sets _atn_force_present=True to inject the known acquisition; the coupled from-f0 replay leaves it None.
Gates: test_atn_actor.py::test_chase_attention_front_cone + test_tetra_untarget.py::test_chase_acquires_mid_roll_not_at_state2.
**From-f0 coupled replay = DIAGNOSED, NOT built (next frontier).** Probe
(_notes/tetrapush-from_f0_probe.py, gitignored) findings: (a) the CC PLOW IS ACTIVE FROM f0 -- live Link displaces only ~12u at f0 despite speedF -24.57
because Tetra (behind, backslid-into) is plowed ~12.6u and Link's net move is reduced by the equal-opp
CC recoil; so Link is in MOVE (feet Co-cyl), NOT the FRONT_ROLL cyl cc_stepper hardcodes (LINK_CO_R=
FRONT_ROLL_R) -> MODEL the MOVE-phase Link Co-radius. (b) input-delay pre-seed: _inbuf needs the 2 pre-f0
DTM inputs (F0-1/F0-2), align post-step(inp[i]) to live[i+1]. (c) foot warm link._foot.started=True at
seed. (d) camera: feed real substick through CameraManual. Detail:
_notes/tetrapush-handoff-2026-07-21-session7.md.


**Session 18 (2026-07-23): the land camera is CLOSED.** manualCamera owns csangle on land (mode 12
persists because C-stick-down holds nextMode's m144==0, which outranks lock-on); yaw is a pure
C-stick input channel, Link's motion only chases the camera CENTER. Port land_cam.py + cam_angle.py,
oracle probe _notes/tetrapush-camoracle_probe.py -> fixtures/courtyard_cam_oracle.json, chained
0-ULP gate tests/test_land_cam.py (120 frames incl. 4 L-blips + 2 lock windows; f45 is a single-step
dup). Traps burned: live JP style rows differ from decomp source (MM03 cushion 0.66/zoom 20); cSGlobe
setter U=yaw(+6)/V=elev(+4) (header swapped); style params must be f32; PSVECSquareMag fused for the
cushion-init dist; Link mHeight=125.0 (la+0x2AC). Ghidra headless: 12.1.2 + pyghidra venv python
(uv tools), project TWW_JP_NEW3 in C:/Users/pinhi, -readOnly; 11.0.1 can no longer open it.

**Session 19 (2026-07-23): the camera is WIRED INTO THE CLOSED LOOP; csangle injection GONE.**
FreeRun(camera=)/replay(camera=,tattns=): a seed_from_block-seeded LandCamera steps at the END of
each frame from the sim's own post-step state (player execute -> camera Run; frame k+1 physics
reads csangle committed at k). Inputs all self-contained: (1) the DELAY-1 raw DTM pad decoded by
land_cam.pad_from_raw (PADClamp octagons main 15/72/40 sub 15/59/31, TStick unit clamp,
ClampTrigger 30/180; gated 0-ULP vs the oracle stick lasts) -- NEVER the physics delay-2 pad; (2)
Link attn pos law attn=(pos.x, f32(92.5+baseTR[1][3]), pos.z) (setAttentionPos :10271, right after
setCollision; sim's posed ff.base IS that matrix; gated 0-ULP f3..f9 -- f1-2 differ by the
unmodeled m35B8 seed residue, a <0.15u center-Y transient, csangle-invisible); (3) the sim's own
AttentionLock.locked == LockonTruth. Gate test_camera_in_the_loop_replay_bit_exact: every csangle
f1..43 == live == oracle AND physics rows byte-identical to the injected reference (csangle is
POSITION-INDEPENDENT in this regime: yaw target is C-stick-only, the L-blip chase targets the
camera's own committed yaw -- survives the closed loop's amplified pos noise). TWO extraction
truths: **the game latches POLL INDEX 2 of a DTM frame's 4-poll group** (pinned via the oracle on
the window's two non-uniform groups; dtm_inputs fixed, fixture regen'd -- only f25 substickX
98->99, physics-inert; build() now preserves baked live rows, the session-2 capture file is gone);
the oracle's main_angle is a PROBE-TIMING SHIFT (decodes the NEXT frame's bytes; DMC-only, inert).
472 offline green. Remaining injected: Tetra eyePos (proc-9 re-aim) + tattn (her attention_info
pos, fopAc+0x274, lock windows only; != feet != eyePos; s18 oracle logs it as ground truth) --
ONE open model (lookAtTarget_2 recipe in the README planner box), then the search.

**Session 20 (2026-07-23): eyePos + tattn CLOSED -- the coupled replay is FULLY SELF-CONTAINED
(zero injected streams); the planner is unblocked.** New core module tww_sim/core/npc_zl1_look.py
(Zl1Look), decomp-first port of the WHOLE Tetra look-at chain: optn_1's look-timer machine
(wait03/look bcks, f7B8=rnd(90,180) countdown; the post-look-cycle RNG re-seed is flagged
rng_horizon -- beyond any plan window; f7B8=116 at f0 so it never fires in-window), lookBack ->
dNpc_JntCtrl_c::lookAtTarget_2 (chkLim head/backbone split + addCalcAngleL(..,4,step,4) chase --
step is 0x1000 live, field_0x7BC=-1, NOT the 0x0180 default), mDoExt_McaMorf (frame ctrl + 8f
quat-lerp morf), the zl.bdl head FK chain 0-1-2-5-6 (harness/anim/extract_zl1.py -> _generated;
scales all 1.0 so SSC moot), the two node CBs (chest XrotM(bb_y) ZrotM(-bb_x); head YrotM(-hy/2)
ZrotM(-hx/2)) + (20,-16,0) eye offset, setAttention tattn=(x, f32(y+140), z). Link's look target
= exec-pass mHeadTopPos = anmMtx(15)*(40,0,0) -> FootFK.head_top (joint 15 added to
BODY_CO_EXTRA; same base/lean/init-frame laws as the Co centre). Zl1 execute order: Link first;
eye consumed by NEXT frame's re-aim, tattn by THIS frame's camera Run; lookBack src = PRE-move
pos + her own prev eyePos.y. GATES (tests/test_zl1_look.py, fixture courtyard_zl1look.json from
_notes/tetrapush-zl1look_probe.py): given live inputs the model is 0-ULP on EVERY output f1..44
(eye, tattn, all 4 JntCtrl angles, targets, half-angles) -- first try; the self-contained replay
(FreeRun(camera=, zl1=), eye/tattn injections deleted) keeps every proc + speedF 0-ULP + lean +
csangle live-exact f1..43. capture_push seed now captures her hidden look state (seed fixture
zl1 block -> Zl1Look.seed_from_row). KB: knowledge/mechanics/tetra-look.md (new page) +
reference/constants-npc.md (SPLIT from constants.md -- it hit the 250 cap; Co-push table moved
there + the Zl1 look values; referrer links repointed). 474 offline green, goldens
byte-identical. **THE ONE NAMED GAP LEFT: Link's own head-look m3564** (la+0x3564; jointBeforeCB
twists his HEAD joint toward the locked actor's eye, d_a_player ~:9060-9170, chased
addCalcAngleS(..,3,0x1000,0x100); live probe _notes/tetrapush-m3564_probe.json: zero through
rolls, -2492 swing on the untarget tier f19-27) -- unmodeled costs <=0.96u of head-top Y there ->
a <=16-BAM facing echo on re-aim frames in the self-contained loop (physics otherwise exact).
NEXT = model m3564 decomp-first, THEN the search (state-2 -> input seq to a tetra_placements
coord + matching roll entry).

**Session 21 (2026-07-23): m3564 CLOSED -- the model-gap list is EMPTY; next is THE SEARCH.**
New tww_sim/land/neck_look.py (NeckLook): setNeckAngle (d_a_player_main.cpp:8938-9169, called
:11571) decomp port -- proc-table mode-flag gate (0x80 procs look: MOVE/WAIT/ATN*/SIDESTEP/CUT*;
rolls/turns chase 0 -- why m3564 zeroes mid-roll despite the held lock), look-pos = lock actor OR
the attention lock-on-list head through the +-0x6000 m34DE cone, prev-frame head-matrix measure
(spC4=M*(11.25,0,0), spAC=M*(11.25,18.75,0)-spC4), absXZ(target-headC)<30 yaw FREEZE (the tier
razor -- f19-21 y=60/-3/0), clamps [-10000,8000]/+-14336 (HIO mShip.m.field_0x0), half-angle
(3,0x1000,0x100) chase + :9159 yaw overflow clamp. AttentionLock.list_present = the dAttention
stock/free timing (stocked every NONE Run, kept LOCK/RELEASE, EMPTY exactly on the
transition-to-NONE Run -- freeAttention w/o restock = the probe's f21 chase-to-0 hole).
FootFK.head_mtx + head_top(neck=): jointBeforeCB HEAD twist = TWO quat concats Q(m3564.y,
m3564.z,0) then Q(0,0,m3564.x). TWO live-pinned TIMING LAWS (each cost a first attempt):
(1) m34DE at setNeckAngle = the FRAME-START facing (:11287 is in the execute PROLOGUE before the
proc dispatch :11402 -- capture link.m34de BEFORE step(); post-step flips the f20 yaw sign);
(2) the head matrix measured is the PREVIOUS frame's calc (:11571 runs before this frame's
calc). Wiring: FreeRun(neck=)/replay(neck=), cached head mtx re-twisted per frame, sim_m3564
rows. Fixture fixtures/courtyard_m3564.json (baked from the probe; f0..f5 decay 1262/842/562/
306/50/0 pins the chase knobs). GATES (tests/test_neck_look.py, 4): capture-tight (centers=
'diag') replay = EVERY m3564 + EVERY facing f1..43 bit-exact vs live (echo CLOSED; head-top Y
<=0.96u -> <=1e-3u); self-contained = physics 0-ULP, m3564 exact outside f19-32 + <=16 BAM
inside (drift-quantization only: every chase INCREMENT matches live; bearings measured on
~0.02u amplified-noise geometry, 1 BAM ~ 0.002u at 13u -- exactness vs live is structurally
unreachable there, diag mode is the 0-tolerance oracle; DON'T chase it). capture_push seed now
logs link.m3564 (seed-fixture regen pending next live session). KB: knowledge/mechanics/
link-head-look.md (new) + constants.md ## Link head-look + tetra-look Open flip; doc-eval 5/5.
478 offline green, goldens byte-identical. NEXT = the search: state-2 -> input seq landing
Tetra on a genuine _generated/tetra_placements.tsv coord + the matching roll entry (coupled,
solve jointly); forward model = FreeRun (camera+zl1+neck); method = the seam-clip solver
pattern (cheap monotone predictor + prune + exact bit-confirm); keep dist <= 230 (follow
guard); >2-min search fine.

**Session 22 (2026-07-23): Phase-1 + Tier-0 BUILT; THREE findings reshape the search; the new
blocker = THE FK 0-ULP HUNT.** Built (all gated, tests/test_tier0.py, 483 offline green):
harness/tetrapush/seeds.py (make_freerun == the s21 gate config byte-for-byte; load_placements;
entry constants), primitives.py (window_records instrumented rollout: per-frame exec centre +
LOCAL offset + recoil/plow/depth; cycle spans; the RIGID cycle template -- roll rows foot exactly
26.000-along, o_local rigid ~0.5u across cycles; abstract input macro + macro_inputs re-aim via
stick_for_bearing, C-stick pinned down; drift diagnostic), tier0.py (geometric shove stepper:
rigid templates + the EXACT fp plow laws per frame in the FreeRun pend order; build_first_template
= cycle 1's RECORDED state-2 entry [fixed data for every plan]; validate = 0.13u vs FreeRun at
f43 on recorded aims; sweep = guard-pruned beam -> _generated/tetra_push_landings.tsv).
FreeRun.step rows now carry sim_cyl_exec. FINDINGS: (1) **the s16 "common-mode drift" claim is
OVERTURNED** -- the self-contained replay's drift vs live is DIFFERENTIAL (e_link ~ -e_tetra, a
pair mode; plow feedback amplifies ~1.35x/contact-frame) reaching 93u by f43, and by f39 the
sim's CONTACT DYNAMICS leave live (dist 127.9 vs 40.4); seed is bit-exact across fixtures, so
the driver is the computed exec-centre FK residual <=3e-4u/frame (~1-2 f32 ULP at courtyard
magnitudes: float64 matrix path vs console f32 PSMTX). Gate test_drift_is_differential_not_
common_mode self-skips when fixed. (2) **The steering law is a RAZOR**: a cycle sustains the
chase-and-plow only ~+-100 BAM around bearing(Link->Tetra)+~1000 BAM (recorded +689/+701);
dead-on or off-band breaks contact mid-roll (late-roll o_local retracts; gap outruns the centre)
and Link rolls 300-480u away past the follow bound -- sweeps need <=100-BAM grids. (3)
**Multi-cycle dynamics are CHAOTIC**: 11 BAM at cycle 1 flips cycle 2's sweet band entirely --
a 4+-cycle open-loop plan needs the forward model to BE the game bit-for-bit; approximate models
only map the reachable ENVELOPE. Tier-0 6-cycle sweeps reach (-1635,-460): right x-band, ~450u
short of the placements (-1640,-910); coarse feasibility UNRESOLVED (suspect the canonical-
template re-engagement approximation; honest test = FreeRun-confirmed chains via macro_inputs).
GOTCHA (cost a debug loop): re-target/flip frames are NOT rigid rel-old-AIM rows -- backslide-
continuation rows travel along the CURRENT motion dir (flipped travel), the +18 flip along the
NEW aim; and cycle 1 must use build_first_template, never the canonical one. NEXT = **the FK
0-ULP hunt**: make FootFK.body_co_center (joints [0,1,2,3,4,14]: quat->mtx, SSC, worldBase
concat) fp-faithful to the console f32 PSMTX pipeline (core.fp; PSMTXConcat paired-single madds
rounding), 0-ULP vs the LOCKED courtyard_push_setcol.json exec centres + the settled cyl stream
f1..43 -- that collapses the whole self-contained replay to bit-exact POSITIONS and unblocks
tier-2 exact confirm at full plan horizon. Decomp-first: mDoMtx/PSMTX in setWorldMatrix/
mDoExt_setJ3DData/J3D calc. Detail: _notes/tetrapush-handoff-2026-07-23-session22.md.

**Session 23 (2026-07-23): the FK 0-ULP hunt is RE-DIAGNOSED, not solved -- the FK matrix is NOT
the blocker (s22 was misdiagnosed).** Four offline experiments (scratchpad, reproducible) + one
durable gate. (1) **body_co_center is ALREADY bit-exact**: fed the breakpoint-exact pos it
reproduces courtyard_push_setcol.json's cyl_exec to 0 ULP on every frame f1..12 (re-accumulating
the joint chain with the EXACT pos -> mid 0 ULP; the per-joint 711k-ULP diffs were only the Y
translate, XZ-irrelevant). So "make the FK fp-faithful" targets already-correct code. (2) **console
sqrtf RULED OUT**: the MSL sqrtf (frsqrte + 3 double Newton refines + f32 cast, math.h:89 -- what
cM3d_Cross_CylCyl :1585 + SetPosCorrect :339 use via std::sqrtf) is bit-identical to a
correctly-rounded math.sqrt->f32 over 90k samples of the loop's dist_sq range; patching it into the
plow changes NOTHING. (3) **diag (push driven by the INJECTED fixture centre) does NOT drift** --
bounded ~few ULP over all 43 frames -- while computed (self-computed centre push) blows up; the ONLY
difference is which centre feeds the push, so the drift is the CLOSED FEEDBACK, not the foot term.
(4) **the one-step error from EXACT state is BOUNDED + non-accumulating** (gate
tests/test_from_f0.py::test_onestep_error_bounded_from_exact_state, 484 offline green): reset pos +
Tetra + push to the exact capture each frame, step once -> Link-pos err <=64 ULP z (~1.5e-5u),
biggest at the roll-entry morf frames k3..k5 (= the known calc_transform/Hermite entry-morf sub-ULP
flagged in core/anim/quat.py), single-digit ULP elsewhere; x 0-ULP throughout (its coarse f32
quantum at ~1335 hides the same ~1e-5u residual that shows at small-z -- judge the residual in u,
not per-axis ULP); facing+speedF bit-exact every frame. CONCLUSION: every component (FK matrix,
sqrt, plow/recoil, seed) is correct to the single-step fixtures' ~1e-5u f32 noise floor; the
centers='computed' blow-up is the plow feedback (depth=80-dist, ~1.35x/contact-frame = an UNSTABLE
AMPLIFIER, session-22 finding 2's chaotic sensitivity) magnifying floor-level residuals. THE REAL
BLOCKER = the last <=1-ULP op(s) in the DASH/ROLL foot-term+recoil path -- but the single-step
fixtures resolve only to ~1e-5u, so localizing needs a per-op LIVE capture (breakpoint the foot toe
/ m_cc_move / roll root-motion delta across f1..43, the way setcol pinned the exec centre).
**OPEN STRATEGY QUESTION (decide FIRST):** the ~1.35x amplifier is plausibly a REAL chaotic
sensitivity, so no bit-faithful-but-not-bit-IDENTICAL model predicts >~1 cycle open-loop -> the
planner should trust the sim ~1 cycle + confirm multi-cycle chains via DTM-on-Dolphin (tier 2) with
tier-0 for the coarse envelope, rather than chase a possibly-irreducible ULP. README FK box flipped
to [x] RE-DIAGNOSED + new [ ] remaining-ULP box; s16 box "residual = the FK" line corrected. DO NOT
re-attempt "make body_co_center fp-faithful" (gated-exact). Detail:
_notes/tetrapush-handoff-2026-07-23-session23.md.

**Session 24 (2026-07-23): STRATEGY DECIDED + the position residual ATTRIBUTED to 2 bugs (offline) +
a hard-rule correction on test rigor.** (1) Dereck DECIDED the s23 strategy fork: **0-ULP is
non-negotiable** ("we must have 0 ULP or else this tool is worthless") -- NO tier-2-envelope escape;
the planner stays pure-sim-from-state-2, which the multi-cycle deliverable forces to be bit-identical
(the ~1.35x amplifier explodes ANY residual over ~4-6 cycles). (2) Discovered + owned a HARD-RULE MISS:
the tetra-push gates enforced 0-ULP on the SCALAR DYNAMICS (speedF/proc/facing/lean/csangle -- genuinely
`_bits==_bits`) but gated POSITION with TOLERANCES (`err<1e-3 u`, plow `<=9 ULP`) labeled "within
capture precision." A real ~5-56 ULP/step position residual sat under those for ~15 sessions, invisible
until the amplifier made it fatal. Dereck's directive: **rewrite ALL tetrapush tests to enforce 0-ULP;
tolerance regression tests are worthless, don't want to see them again** -> new HARD RULE
[[zero-ulp-tests-only]]. (3) Built the DIVERGENCE TEST CASES (tests/test_from_f0.py, xfail(strict), so
suite stays green + auto-flip when closed): `test_onestep_pos_bit_exact_from_exact_state` (Link one-step
from EXACT state vs live, 0 ULP; worst 56 ULP z at f4, 28/43 frames), `test_tetra_push_bit_exact_from_exact_state`
(push law isolated -- Tetra has NO foot term), `test_full_depth_push_recoil_is_exact_opposite_of_tetra`
(Newton-3rd-law self-consistency, a PURE code bug fixable w/o live). Diagnostic CLI
`harness/tetrapush/onestep_divergence.py` (per-frame ULP table; live pos is breakpoint-exact, setcol==cyl
0 ULP f1..12, so the divergence is REAL sim-vs-console). (4) ATTRIBUTED the residual to 2 bugs, ENTIRELY
OFFLINE via the Tetra-no-foot-confound + a z-delta decompose (sim's speedF-move is CONSTANT through the
roll & travel bit-exact, so the roll error is NOT the speedF move): **BUG #1 = the push/recoil law**
(both actors ~few ULP): the Courtyard replay uses the s9 DERIVED `full_depth_push` (link_plow.recoil +
tetra_plow.plow_step: TWO separate fsqrt; full_depth_push returns Tetra's move as f64 new-minus-old vs
Link's f32 delta -> NOT exact opposites, ~1 ULP off), NOT the decomp-faithful `cc_push.co_move_pair`
(one dist, obj1/obj2 exact-opposite, sum==0 live-confirmed). Fix = compute the push the console's way
(co_move_pair math on the right centres + f32 Tetra tracking). **BUG #2 = Link's roll-entry foot term**
(Link only, f3-5 56-ULP spike decaying with the morf; Tetra has NO such spike): the sim omits a
foot-position delta during the entry morf that the console has (calc_transform/Hermite jnt0, quat.py
flagged). Isolate cleanly AFTER #1. (5) NEXT: rewrite all tetrapush tests to 0-ULP (the targets) + a
LIVE per-op breakpoint capture -- at posMove JP 0x80106514 / the CC pass, read both actors' m_cc_move
(Link lp+0x3FE8+0, Tetra mStts+0) = bug-#1 truth, AND Link current.pos right after the foot apply before
cc-consume (or m3598) = bug-#2 truth -- because the single-step cyl fixture resolves only to ~1e-5 u
(== residual size), so 0-ULP validation needs a DETERMINISTIC capture. 484 offline pass, 8 xfailed (+3).
Detail: _notes/tetrapush-handoff-2026-07-23-session24.md.

SESSION 25 (2026-07-23): DONE the s24 directive -- **all tetra-push tests rewritten to enforce 0-ULP**
([[zero-ulp-tests-only]]), a test-rigor pass only (the forward model is UNCHANGED). No `err < eps`
sim-vs-console position/plow fidelity tolerance survives in tests/test_{from_f0,tetra_plow,link_plow,
tetra_untarget,atn_actor,land_cam,zl1_look,neck_look}.py. EVERY decision was MEASURED first (scratchpad
diagnostics, not guessed): (a) 2 DETERMINISTIC-capture tolerances flipped to true 0-ULP `==` -- the
setCollision exec-midpoint and the settled-centre half-depth law are BIT-EXACT vs the setcol breakpoint
over f1..12 (measured 0 ULP); (b) the standalone plow law got a 0-ULP `xfail(strict)` gate
`test_plow_step_bit_exact_vs_live` (the clean f32 `plow_step` vs live Tetra pos, DISTINCT from the buggy
f64-delta `full_depth_push` wrapper); (c) the dynamics gates (chained/f0-seed replays, closed-loop, the
zl1/neck wiring) were STRIPPED of tacked-on position/facing tolerances -> now assert only the
genuinely-0-ULP dynamics (proc/speedF/facing/lean/csangle/m3564/tattn); (d) 6 redundant single-step
position trackers DELETED (Link-pos, Tetra-pos cumulative, computed-centre, reconstruct, + the two
link_plow recoil tests whose comparison target was a lossy math.sin reconstruction -> un-0-ULP-able);
(e) surviving non-fidelity checks each RELABELLED explicitly -- the frac==1.0 full-vs-half REGIME
discriminators, the proc-9-vs-MOVE step-magnitude discriminator, the fixture-identity guard, and the
bounded-error/amplification REGRESSION GUARDRAIL (category (a), never called 0-ULP). Rollstab
cc_stepper/cc_rollstab reviewed -> no sim-vs-console fidelity tolerances (already 0-ULP where they
compare to console), left as-is. The POSITION 0-ULP bar is now the 3 session-24 divergence gates + the
new plow gate (4 xfail-strict, all pinned to the 2 attributed bugs; auto-flip to hard passes when
closed). 472 offline pass / 9 xfail (was 479p: -6 deleted, +1 pass->xfail, +2 new ==); land goldens
byte-identical, KB + code-hygiene gates green. NEXT (unchanged, the sole remaining foundation work) =
the LIVE per-op breakpoint capture (s24 recipe) to fix bugs #1/#2 and flip the 4 gates. Detail:
_notes/tetrapush-handoff-2026-07-23-session25.md.

SESSION 26 (2026-07-23): (1) **Bug #1's SELF-CONSISTENCY part CLOSED OFFLINE** -- `from_f0.
full_depth_push` now returns Tetra's push as `-recoil` (exact f32 sign flip off the SAME dist/
pushFactor) not the old f64 new-minus-old, so Link recoil == -Tetra push BIT-FOR-BIT (Newton 3rd law,
same-rank Co pair, co_move_pair sum==0). `test_full_depth_push_recoil_is_exact_opposite_of_tetra`
FLIPPED xfail->hard pass; dynamics gates all stayed 0-ULP; goldens byte-identical. Pure code, no live.
(2) **DELIVERED the LIVE per-op capture -- and it OVERTURNS the "single-step noise floor" framing.**
`fixtures/courtyard_push_perop.json` (probe `_notes/tetrapush-perop_probe.py`): both actors'
current.pos read at the JP posMove (0x80106514) breakpoint, one hit/game frame f0..f43 (deterministic,
bp pins the frame count). **KEY FINDING: this breakpoint capture == the single-stepped cyl fixture
BIT-FOR-BIT (0 ULP) at every f0..f43, both actors** (`test_perop_confirms_cyl_positions_are_
deterministic`, hard pass). So the cyl POSITIONS were exact ground truth all along (not just
setcol-confirmed f1..12); the 5-56 ULP one-step divergence is a REAL sim-vs-console residual, NOT
noise -- and the [[zero-ulp-tests-only]] "cyl resolves only ~1e-5 u" caveat does NOT apply to this
held-stick push window. **Both bugs are now pure OFFLINE code bugs -- no more live capture needed.**
Bug #2 laid bare: Tetra has no foot term (stt-3), so her push = ΔTetra; Link foot term = ΔLink+ΔTetra
= deterministically a CONSTANT 26.0 u/frame during each roll with an entry-morf RAMP at roll-start
(18.5->26.0) = the calc_transform/Hermite jnt0 entry-morf. (3) **LIVE-SETUP TRAPS (hard-won, now in
README ## Live setup, [[harden-harness-traps]]):** a bare `resume` free-runs the movie -> Dolphin
CLEANLY EXITS (same signature as the wrong-iso trap); step with `advance`+breakpoint (never resume),
bp fires once/game frame ~2 advances apart, Dolphin survives the whole window. Launch Dolphin DETACHED
(PowerShell Start-Process) so it survives across separate shell commands (a Popen'd child dies with
its launcher). Pipe movie command = `playmovie {path,game}`. m_cc_move (lp+0x3FE8) reads 0 even at
posMove entry (push lands via immediate current.pos writes in the CC pass, not a deferred move) -> the
push is measured from POSITIONS, not m_cc_move. 474 offline pass / 8 xfail (self-consistency->pass +
new determinism test), goldens byte-identical. NEXT (fully offline, unblocked) = PORT the 2 fixes:
bug #1 = co_move_pair on the model's EXEC centre cx (half-depth) not full_depth_push on the settled
centre; bug #2 = the entry-morf foot term; validate vs courtyard_push_perop.json, flip the 3 remaining
xfails. Detail: _notes/tetrapush-handoff-2026-07-23-session26.md.

SESSION 27 (2026-07-23): **PORTED bug #1 -- and it turned out there was only ONE bug. POSITION is now
0-ULP one-step-from-exact-state f2..f43 (42 consecutive frames), Link AND Tetra.** Bug #1 = the push
law: added `from_f0.cc_push_pair` (`cc_push.co_move_pair` = `dCcS::SetPosCorrect`, decomp 50/50
HALF-depth split, obj1/obj2 EXACT-opposite) computed from the model's own EXEC centre `cx`, replacing
`full_depth_push` on the SETTLED centre in FreeRun's computed path. Verified vs the deterministic per-op
ΔTetra: `co_move_pair(cyl_exec)` reproduces it BIT-FOR-BIT f2..f43 (the model's computed exec centre ==
setcol `cyl_exec` 0-ULP where both exist, and stays exact to f43), where full-depth-from-settled (fused
or not) is 1-9 ULP off (they agree only to ~1e-5 u -- THAT was bug #1). **Bug #2 does NOT exist as a
separate bug:** the session-24 "roll-entry foot term / f3-5 56-ULP spike" was the RECOIL error (bug #1)
being larger at roll entry (geometry ramps), measured THROUGH Link's position. With the console recoil
(pinned to Tetra's deterministic ΔTetra by the exact-opposite Newton pair, so NO compensating error is
possible), Link's one-step position is 0-ULP too -- his foot term (incl. the entry-morf ramp 18.5->26.0)
was exact all along; NO calc_transform/Hermite/quat.py change was needed. Gates flipped xfail->HARD PASS:
`test_from_f0.py::{test_onestep_pos_bit_exact_from_exact_state, test_tetra_push_bit_exact_from_exact_state}`
(model exec centre, f2..f43 vs perop, shared `_onestep_console_push` helper) +
`test_tetra_plow.py::test_console_push_bit_exact_vs_deterministic` (RENAMED from
test_plow_step_bit_exact_vs_live; standalone twin -- cc_push_pair on the setcol EXEC centre vs perop
ΔTetra f1..12, two deterministic captures, no model). Deleted the now-subsumed
`test_onestep_error_bounded_from_exact_state` guardrail. CODE CLEANUP (delete-obsolete rule): retired
the superseded DERIVED laws `tetra_plow.{plow_step,reconstruct}` (git history archives them; `plow_depth`
+ radii stay); `full_depth_push`+`link_plow.recoil` survive ONLY as the seed-frame (f0->f1) fallback.
Closed-loop `centers='computed'` drift COLLAPSED ~93u -> ~4u. **f1 is the SOLE residual: its push comes
from f0's EXEC centre, which is NOT offline-reconstructable** (the seed frame doesn't carry f-1's
lean/morf; documented `from_f0._seed_pose_f0`). Closing f1 / the closed loop to full 0-ULP would need
ONE deterministic setCollision-breakpoint read at the seed frame -- the only place further live capture
helps; decide if it matters for the multi-cycle planner before scaling. 476 offline pass / 5 xfail (all
pre-existing, non-tetrapush), land goldens byte-identical, KB + code-hygiene green. **The forward model
is now BIT-EXACT (dynamics 0-ULP + position 0-ULP f2..f43) -- the planner (the last open [ ] box) is
unblocked.** Detail: _notes/tetrapush-handoff-2026-07-23-session27.md.

SESSION 28 (2026-07-23): PLANNER BUILD STARTED (the forward model was made bit-exact s27). Three
things, all offline. (1) **DECIDED the f1 seed-frame question (the Next-step "decide first"): it
MATTERS, decisively.** Measured the self-contained closed loop from f0 (`centers='computed'`) vs the
deterministic capture: the f1 seed-push error (~3.3e-5 u -- `full_depth_push` on the SETTLED seed
centre, since f0's EXEC centre is not offline-reconstructable) grows GEOMETRICALLY at ~1.35x/contact-
frame (f16 ~1e-4 u, f24 ~4e-3, f32 ~0.08, f36 ~0.52, **f43 ~4.1 u** over 2 cycles). The genuine coords
are sampled at 0.004 u, so the error passes placement resolution within ~1 cycle and is catastrophic
over a 4-6 cycle herd. FIX = capture f0's exec centre with ONE deterministic setCollision-bp read and
route the f0->f1 push through `cc_push_pair` too; since f0 is the FIXED state-2 seed its exec centre is
INPUT-INDEPENDENT (one capture valid for every sequence) -- in-band of the "no live feedback in the
loop" rule (a static seed). This is the next LIVE step; NOT needed for coarse feasibility (~4 u over 2
cycles is <1% of the ~545 u herd). (2) **RESTORED the sound primitive layer on the 0-ULP model +
GATED.** `harness/tetrapush/seeds.py` (self-contained FreeRun factory `make_freerun` + the 288-coord
`tetra_placements.tsv` loader + DTM input accessor) and `primitives.py` (`window_records` = the
instrumented FreeRun rollout, `find_cycles`, `cycle_template`, `input_macro`/`macro_inputs` = the
cycle's raw-input pattern re-aimable to any world angle via `plan_land._primitives.stick_for_bearing`)
are back from git (removed s24 with the premature tier0) -- they run UNCHANGED on the current bit-exact
FreeRun API. Only the tolerance-based `tier0.py` search layer stays removed (the exact confirm is
FreeRun, not a `0.13 u` bound). Gate `tests/test_planner_primitives.py` (5 STRUCTURAL, not sim-vs-console
-- that fidelity is test_from_f0's): window covers f1..43, `find_cycles` recovers the 2 cycles (rolls
f3/f29), the roll-body FOOT term is cycle-rigid to <0.02 u (WHY a cycle is a re-aimable primitive),
`macro_inputs` reproduces the exact button/trigger pattern + valid bytes + C-stick pinned DOWN, and the
analog re-aim is <1 LSB where the stick BITES (msd>0.3); the ~4-deg residuals are all at msd~0.05
roll-body frames where facing is LOCKED at the aim and the angle is irrelevant (documented tier-0
property, not a bug). (3) **COARSE FEASIBILITY CONFIRMED** (`harness/tetrapush/feasibility.py`, CLI
`python -m harness.tetrapush.feasibility`; all numbers recomputed live so they can't drift). From the
bit-exact 2-cycle window: recorded herd **544.8 u @ -161.7 deg**; the genuine-coord cluster centroid is
**967.5 u @ -161.5 deg** from Tetra's state-2 start -- **the natural push direction already points at
the clip region (0.2 deg off)**, so the plan is a near-straight herd, not a steer-around (state 2 was
set up for exactly this shove). Per-cycle reach ~345 u -> ~3 cycles cover the ~940-984 u span;
Link<->Tetra distance stays **40-85 u** (well under FOLLOW_ENGAGE_DIST 230), so Tetra stays stt-3
throughout. A trustworthy open-loop 4+ cycle rollout waits on the f1 capture (the drift dominates past
~2 cycles); the feasibility argument is directional + per-cycle + regime off the bit-exact 2-cycle
capture. 481 offline pass / 5 xfail (pre-existing, non-tetrapush), land goldens byte-identical, KB +
code-hygiene green. NEXT: (a) capture f0's exec centre live to close f1; (b) the exact aim-per-cycle
search (stitch re-aimed cycles -- the removed tier0.build_template stitch is in git history -- rank in a
cheap predictor, bit-confirm each candidate in FreeRun then DTM). Detail:
_notes/tetrapush-handoff-2026-07-23-session28.md.

SESSION 29 (2026-07-23): CLOSED the f1 seed-frame boundary to 0-ULP -- **ENTIRELY OFFLINE, NO LIVE
CAPTURE** -- OVERTURNING the session-28 plan (which called for a live setCollision-breakpoint read of
f0's exec centre). The self-contained closed loop from state 2 is now bit-exact in POSITION too, f1..43,
both actors; the planner's own `seeds.make_freerun` self-contained rollout (camera+zl1+neck, no
injections) is 0-ULP vs perop over the whole DTM window. The session-28 diagnosis was INCOMPLETE in two
ways: (1) f0's exec centre is not pose-reconstructable (confirmed: the pose-computed centre is ~0.5 u
off -- seed lacks f-1 lean/morf), BUT the f0->f1 push RESULT was already in the locked deterministic
`courtyard_push_perop.json`: Tetra has NO foot term (stt-3, speedF 0), so her whole f0->f1 move IS the
CC push, and `ΔTetra = perop.tetra[1]-perop.tetra[0]` gives `f0+ΔTetra==f1` BIT-FOR-BIT (`full_depth_push`
on the settled seed centre was +66 ULP off). (2) closing (1) ALONE made the closed loop WORSE (~4 u ->
~50 u) -- it exposed a SECOND bug: the model carried Tetra as an f64 point while the console stores
current.pos as f32, and the ~1.35x/contact-frame plow amplifier explodes that sub-f32 residue. Rounding
the tracked Tetra point to f32 each frame (matching `dCcS::SetPosCorrect`'s f32 `*ppos += vec`) is the
other half. So the session-28 "f1 is the only residual, closing it collapses the drift" was WRONG on
both counts (wrong that it needs a live capture; wrong that f1 is the whole story). CODE: `FreeRun(seed_push=)`
/ `replay(..., seed_push=)` take the exact perop ΔTetra (`seeds.seed_push_f0`); `full_depth_push` stays
the roll-entry / no-perop fallback; `FreeRun.step` rounds `self.tx/tz` to f32 each frame (had to hoist the
module-level `f32` import + drop step's local shadowing import). GATES (all HARD PASS): the two one-step
gates now assert **f1..f43** (was f2..f43); NEW `test_closed_loop_computed_replay_bit_exact` asserts the
accumulating closed loop's Link+Tetra position 0-ULP vs perop f1..43 (renamed from the dynamics-only
test, whose stale "drifts ~4 u / needs f0 exec centre live" docstring is rewritten); `onestep_divergence`
CLI now prints 0/43 divergent. 481 offline pass / 5 xfail / 1 skip (native LandCore unavailable,
pre-existing), goldens byte-identical, KB+code-hygiene green. The forward model is now FULLY 0-ULP from
state 2 (dynamics+position); NO further live capture is needed for it -- live is only the final tier-2
DTM confirm. NEXT: the exact aim-per-cycle search (unblocked -- open-loop multi-cycle rollouts are now
trustworthy). Detail: _notes/tetrapush-handoff-2026-07-23-session29.md.

SESSION 30 (2026-07-23): built the EXACT-SEARCH FOUNDATION on the 0-ULP FreeRun + hit (and diagnosed)
the cycle-chaining blocker + got a key REFRAME from Dereck. NEW `harness/tetrapush/search.py` +
`tests/test_search.py` (488 offline pass, +7; goldens byte-identical; library change = additive
clone() methods only). (1) **rollout(env,aims)** stitches re-aimed 26-frame push-cycle macros
(`canonical_cycle` = the roll-to-roll unit, find_cycles span 0) through FreeRun from state 2, C-stick
pinned DOWN, main stick re-aimed per frame via stick_for_bearing at the LIVE csangle. 0-ULP gated 2
ways: recorded-input replay reproduces the window bit-for-bit, AND macro@recorded-aim +
recorded-C-stick + frame-aligned csangle reproduces cycle 1 bit-for-bit. CRUCIAL: the AIM IS A NOMINAL
KNOB -- pinned C-stick makes csangle evolve differently than the recording (which MOVED the C-stick to
drive manualCamera) + the stick byte grid quantizes achievable aims, so the search RANKS BY THE
ACHIEVED landing read back from FreeRun, never the commanded aim. (2) **FreeRun.clone()** ~0.025ms
(shares immutable anim tables via LandState.clone + new LandCamera/Zl1Look/Zl1Morf/Zl1JntCtrl/NeckLook
.clone; deepcopy was 62ms) -- a clone steps bit-identically to its parent; the beam branch. (3)
**Reachability (`search reach`):** per-cycle achievable aims are DISCRETE (byte-quantized ~68-170 BAM
apart) with a sharp RESONANCE at the recorded aim -- one cycle herds Tetra ~324u @ -162deg staying
coupled (maxdist 85), vs ~150u + higher maxdist +-600 BAM off. Deterministic (not chaos); the human
sits on it. (4) **beam_search** = clone-branched beam over per-cycle aims, ranked by nearest
genuine-coord dist, pruned by the stt-3 plow-regime guard, each candidate a REAL FreeRun rollout (no
approximation -- supersedes the removed rigid-template tier0). **BLOCKER: cycle chaining under pinned
C-stick.** Cycle 1 herds 324u but cycle 2 does NOT chain (`search chain`): cycle 1 leaves Link facing
~toward the now-plowed-ahead Tetra -> the next re-target's held L RE-ACQUIRES the attention lock (she's
in the front cone) -> Link stays in the proc-9 LOCKED SLIDE, no roll, drifts to dist 390 (out of
regime). The recorded run chained only via its C-stick CAMERA motion (shapes the re-target facing / the
acquisition cone), which a pinned plan discards. Lockless (no L, `lockless_macro`) rolls every cycle
but plows only ~77u (facing not pinned to the aim -> grazes) + still turns not rolls on cycle 2. So
beam reaches 1 cycle. **REFRAME (Dereck, mid-session; `search herd` CLI): don't assume the human cadence
is optimal.** Per-frame instrumentation of the resonance cycle: the herd is a CONTINUOUS overlap-push
~10-18u/frame EVERY frame Link's Co-cyl overlaps Tetra (dist<80) -- during the roll AND the
backslide/untarget alike, NOT discrete roll-plows. So the objective is SUSTAIN + DEEPEN overlap (a
tighter chase dist~20-40 pushes harder than the recorded 40-85 band) + forward drive, without overshoot
(dist->0, Link passes through) or fall-behind (dist->80+ -> stt-4 follow). The chaining break IS an
overlap-loss. NEXT: recast the cycle as a PARAMETERIZED control (roll timing / backslide length / aim /
attention-L + C-stick timing all free) and search to MAXIMIZE sustained-overlap herd-per-frame + keep
chaining; the recorded run is a feasibility ORACLE, not the target. THEN the exact placement (walk-push
nudge endgame) + entry walk-in + tier-2 DTM confirm. NO further live capture is needed for the forward
model. Detail: _notes/tetrapush-handoff-2026-07-23-session30.md.

SESSION 31 (2026-07-23): RE-DIAGNOSED the cycle-chaining blocker offline (0-ULP model, no Dolphin) and
Dereck steered it to the FRAME-MINIMAL TURNAROUND-ROLL. Method: per-frame diff of the recorded window
(the oracle that chains cyc2 at f29) vs a pinned-C-stick rollout (fails). FINDINGS: (1) **s30's "chaining
needs C-stick camera management" is WRONG about the lever.** Recorded csangle barely moves (~28 BAM over
f20..28); feeding the recorded C-stick only "chains" cyc2 as a BYTE-QUANTIZATION ARTIFACT (its ~655 BAM
csangle offset perturbs a razor-margin cone gate). The real re-aimed-macro gate is the inter-roll
MOVE-backslide FACING turn: the next re-target's held L re-acquires the attention lock (-> proc-9 slide,
no roll, drift out of regime) UNLESS Tetra left the +-0x4000 (90deg) front cone by the L-pulse. Recorded
clears by ~2600 BAM, pinned misses by ~145 (the s22 chaotic sensitivity). (2) **The turnaround-roll
sidesteps all of it.** The roll is an A-roll (a_pressed, PAD 0x100) and _roll_init snaps facing=target
(=decode(stick)+0x8000+csangle), so face-away + A + stick-toward-Tetra rolls THROUGH her in 1 frame with
NO lock and NO cone gate (dodges the console talk cone, [[turnaround-roll-tech]]). It fires only from a
GROUNDED proc (MOVE/ATN_MOVE), NOT the proc-9 untarget slide (state.py grounded set), so available ~2f
after the untarget tier drops to MOVE. (3) **Tetra is stt-3** (no self-locomotion; waits where plowed
until dist>FOLLOW_ENGAGE_DIST 230 flips her to stt-4), so chaining has no time pressure FROM HER; only
FRAMES cost (Dereck [[tetrapush-frame-minimal]]: it's a speedrun). (4) **DEEP-vs-GRAZE is POSITIONING,
not aim.** An immediate A-roll GRAZES (min_ovl~66, cyc2 +64u); sweeping the roll aim at reposition 0
never beats ~66 (at dist~59 Link+Tetra co-move SW at ~equal speed through the roll, gap never closes).
The recorded human cyc2 plows DEEP (min_ovl~40, +185u) because its ~8-frame CURVED backslide (facing
37548->16140 while backing up) lands Link NE of Tetra at a cut-THROUGH approach. (5) **FRAME-MINIMAL
LEVER (Dereck):** the human's ~8-frame face-away turn is the suboptimal part; since csangle is a
per-frame input and the roll snaps facing=stick+csangle, PRECISE CAMERA control reorients Link ~180deg
in ONE frame, collapsing the reposition-turn to ~1. DELIVERED (all on main-to-be, 489 offline pass / 5
pre-existing xfail, land goldens byte-identical, additive): search.py corrected docstring + `turnaround`
CLI (`cyc1_to_untarget` + `turnaround_reroll`), gate test_search.py::test_turnaround_reroll_fires_from
_grounded, README ## Plan/status s31 box + tooling row, memory [[tetrapush-frame-minimal]] + this. NEXT
= build the frame-minimal turnaround-roll chain: the MINIMAL camera-assisted reposition placing Link NE
of Tetra for the DEEPEST through-roll, chained, with total FRAMES the objective (recorded 2-cycle
playback = feasibility oracle); THEN exact placement (walk-push nudge) + entry walk-in + tier-2 DTM.
Detail: _notes/tetrapush-handoff-2026-07-23-session31.md.

SESSION 34 (2026-07-23): RE-DIAGNOSED the on-line reposition (OVERTURNS the s33 turnaround premise) +
started the SEARCH + hit the throughput wall; ended on Dereck's PERFORMANCE pivot (CYTHONIZE for a hard
brute force). Findings (0-ULP sim; full writeup _notes/tetrapush-session34-rediagnosis.md; framework
harness/tetrapush/repo_search.py): (1) the s33 TURNAROUND-ROLL (reposition.frame_min_reroll) CANNOT be
on-line -- validity sweep (nflip 2..4, roll aim +-3000, csangle): worst_lead >= +235 EVERYWHERE; the
turnaround snaps facing 1f but the +lateral drift compounds (entry lat +10 -> +21 at roll-start vs
human -2), so the +26 roll overlaps Tetra (dist 56-76) but shoves her LATERALLY (lat +21->+76) and
overshoots (lead -63->+261). The correct flip is nflip=3 (the +18 completes; nflip=2 floored at +5),
but even talk-safe+nflip=3 overshoots. (2) release-early (steer #2/#3, -25.7 retention) is
INCOMPATIBLE with on-line: from the full 2-frame tier (-25.455, facing 37552, lat +5.1) an ESS-down
hold nulls lat to -2 in 1 frame w/ lead -33..-69 (never overtakes); from the release-early untarget
(-25.727, facing 35324, lat +10.2) the SAME hold GROWS lat +14..+58 and overtakes. USE THE FULL TIER
for the reposition. (3) the on-line lever is the HUMAN'S ESS-CURVED BACKSLIDE (facing/travel decouple),
NOT the turnaround; csangle ~frozen in the recording but its VALUE is razor-critical (~650 BAM off a
coarse grid = missed). (4) THE WALL = the coff-vs-lat COUPLING: a talk-safe +26 roll needs facing OUT
of Tetra's +-90 cone at the L/A press (else L actor-locks -> +12 slide, A talks), i.e. facing ~110deg
off the bearing; but rotating facing out-of-cone via the backslide (preserving speed) forces lat to
drift ~-19u by the frame coff exits the cone -- NEVER both out-of-cone AND lat~0. The human evades this
via the MAINTAINED ACTOR-LOCK (soft-lock = L held, AttnFlag_20000000; persists from cyc1's roll through
RELEASE + mid-roll L re-pulses) which FREEZES facing out-of-cone so he never rotates it via the
backslide. (5) NEITHER the from-scratch primitives NOR a replay of the recorded reposition CHAIN a
valid on-line cycle (recorded replay -> proc-9 slide, talk, overshoot +268). (6) repo_search.py BUILT
(curve_beam = per-frame beam over speed-preserving backslide inputs, HARD-PRUNE speed drops < |24| per
Dereck [a braked backslide is physically dead]; fine aim + csangle vernier + soft-lock L-held
candidates; flip_roll; CLIs curve/cycle) -- finds NO on-line roll yet (coupling + coarse vernier + no
maintained-lock). (7) PERF: FreeRun.step ~2500/s full, ~7600/s STRIPPED (zl1=None,neck=None -- PROVEN
GEOMETRY-EXACT 0.000u diff, safe no-miss search proxy; only the head-look facing-echo differs). The
pose-FK exec-centre (foot_fk._pose_frame/_local_from_old/body_co_center, for the push) is the FLOOR and
runs in PYTHON; native _anmc.pyx exists but doesn't cover it. NEXT (Dereck directive): CYTHONIZE the
step to 300k-1M/s -> HARD BRUTE-FORCE the reposition = a COMPLETE state-space BFS (full per-frame
branching on a FINE grid, dedup by discretized state, hard-prune ONLY speed/overtake/regime, NEVER
rank-drop), with the MAINTAINED-ACTOR-LOCK lever (freeze facing out-of-cone w/o the lat-drift coupling);
bit-confirm on the full 0-ULP FreeRun; THEN exact placement + entry walk-in + tier-2 DTM. Detail:
_notes/tetrapush-handoff-2026-07-23-session34.md.

SESSION 35 (2026-07-23): STARTED the CYTHONIZE (Dereck's 300k-1M steps/s requirement). Two safe,
0-ULP-gated increments; the stripped geometry step (zl1/neck OFF -- the s34 no-miss search proxy) went
6.8k/s -> 8.4k/s -> 17.5k/s (2.6x). (1) **Native `_anmc.co_center`**: folded the whole
`FootFK.body_co_center` neck-chain accumulation (setCollision root/neck midpoint -- 6x `_local_from_old`
+ concat + the BODY_CHN twist on jnt 2 + the neck SSC on jnts 3/4/14) into ONE C call, reusing the
existing native f32/quat/psmtx/concat primitives + a new `_quat_concat_c` (mDoMtx_QuatConcat, plain f64
then single f32). `body_co_center` calls it when `_anmc` is built; the Python loop kept behind a new
`_force_py=True` kwarg as the differential reference. Removed the #1 Python hotspot (`_local_from_old`).
(2) **`FreeRun.step(record=False)`** -- the search fast path: skips the `sim_cyl` settled-centre
DIAGNOSTIC (`_cc_settled_center`) and the per-frame row dict; the push + both actors' positions are
UNCHANGED (proven geometry 0-ULP vs record=True over 40f). Gates: NEW `tests/test_body_co_native.py`
(native vs `_force_py` bit-exact over a pos/facing/lean/body-lean sweep on a real dash old-pose);
`test_from_f0` stays 16/16; 497 offline pass / 5 xfail (pre-existing), land goldens byte-identical, KB
green. **The remaining port (NEXT, still the 300k-1M directive):** the `record=False` profile is now
LAND PHYSICS procs (~33%: `state.step` own + `move._set_speed_and_angle_normal` + `atn`/`atn_actor` +
`main_stick_decode` + `_clamped_angle_s16`/`s16_signed`/`_dist_angle_s` + `_check_next_mode`) + the ANIM
KEYFRAME SAMPLER (~20%: `j3d_eval.calc_transform`/`_keyframe_interp`; hermite already native). NO single
lever left -- need the WHOLE step in one nogil C translation unit. Recommended arch: (a) extend the
C-resident `PoseEngine` to ALSO pose the neck chain [2,3,4,14,15] + expose native `co_center`/`head_top`,
so `from_f0` drops `foot_native=False` and the whole pose FK is one C call (kills the standalone
calc_transform/_pose_frame Python); (b) port the courtyard procs (MOVE/ATN_MOVE/ATN_ACTOR/FRONT_ROLL +
attention machine + stick decode) to a native `LandCore` struct, proc-by-proc, each gated native-vs-
`_force_py` `_bits`-equal; (c) OpenMP `prange` fan-out over the BFS frontier (the `_shovec.pyx` pattern)
once the step is nogil. Keep the pure-Python step as the 0-ULP oracle at every stage. WATCH: `co_center`
reads the FootFK Python old-pose dicts (populated by the Python `_pose_frame`), so step (a) must move
the old-pose read into the engine or it breaks -- that coupling is why (a) is one port, not two halves.
**DERECK STEER s35: MORE ROLLS ARE OPTIMAL** -- the brute force must NOT cap/penalise roll count (the
roll is the productive ~26 u/f frame; the dead cost is the inter-roll reposition; [[tetrapush-frame-minimal]]).
Detail: _notes/tetrapush-handoff-2026-07-23-session35.md.

SESSION 36 (2026-07-23): PROVED 1M is already in C + found/fixed a global native-disable regression;
reset the perf approach (Dereck: "1M no exceptions"). (1) **The existing native `LandCore.step` (the C
walk step, `tww_sim/core/anim/_anmc.pyx`) runs 1.48M steps/s raw / 390k via the `LandState.step`
Python wrapper.** The courtyard search is slow (~17k/s stripped, ~2.6k/s real make_freerun rec=True)
ONLY because `from_f0.FreeRun` runs the courtyard step in PYTHON (native=False). Native-leaf-op folding
of the Python orchestration is a PROVEN DEAD END (~17k ceiling); this session's marginal `pose_chain`
fold (bit-exact, ~1.0x rec=False / ~1.35x rec=True -- a wash) confirmed it. **THE ONLY task now = port
the courtyard procs natively into `LandCore` (attention machine [attention.py] + procs 8/9 ATN_ACTOR
[procs/atn_actor.py] + checkNextMode lock routing + `_cc_move` consume + `cc_push_pair`
[core/cc_push] + f32 Tetra tracking; strip zl1/neck/camera for the search, geometry-exact per s34;
`co_center` already native), wire from_f0.FreeRun to it, gate 0-ULP vs the Python step, then OpenMP
prange over the BFS frontier.** (2) **Fixed: the native engine was GLOBALLY DISABLED** -- the land anim
set grew to 17 but `AnimData`/the FootFK build gate were capped at 16, silently forcing the WHOLE land
sim (incl. the fused LandCore, the "88x" in [[land-sim-perf]]) onto Python. Bumped the cap to 20
(_anmc.pyx `_meta[20][17]` + `_sdata/rdata/tdata/dec[20]` + range(20); foot_fk gate `<= 20`); a default
LandState has `_core` active again, 0-ULP (497 offline pass + goldens byte-identical at the last check
before checks were cut). Added `_CJALL[17]` + `PoseEngine.pose_chain` + foot_fk `_pose_engine` handle
(scaffolding; keep or drop). Changes UNCOMMITTED-then-committed; .pyd rebuilt. Detail:
_notes/tetrapush-handoff-2026-07-23-session36.md.

**s40 -- THE HERD-RATE CEILING (re-frames the whole objective; measure before optimizing).** Both
actors eject the full Co overlap depth, so a contact frame is a pure SPLIT of Link's step: he
advances `|speedF| - e` down-herd, Tetra advances `e`, and a sustained push is the steady state
`e == |speedF|/2`. Measured on the recorded window (`steered_search.push_ceiling`, CLI `ceiling`):
mean Link down-herd 12.627 u/f, mean Tetra 12.761 u/f, **sum 25.388 == mean |speedF|**. With
`_roll_init` capping speed at 26 the **ceiling is 13.0 u/frame and the human already runs at 12.76 =
98.2%** (contact 95%, push alignment 0.996). So: **a ROLL IS NOT PRIVILEGED** (the -25.7 backslide
pushes as hard as the +26 roll) -- the s38/s39 beams "finding zero rolls" reported a REAL property,
not a search bug -- and **no reposition can pay for itself**; only ~1.8% (~1.4 frames per 75) is left
on the push proper. The only lever that breaks the cap is a mechanic moving Link faster than 26 (e.g.
the roll-stab CUT lunge's 23.22 u root translate, [[tetra-push-model]]). **Dereck's bar (s40, live):
chain TWO rolls above the human's 12.758 u/f from state 2**, first roll swept over every reachable
halfword facing, aggressively pruned -- `two_roll.py` (`roll_facing_fan` = 312 reachable facings
within +-8192 BAM, deduped by ACHIEVED stick bytes). **BAR NOT MET.** Bugs fixed by measurement: the
**delay-1 A-press** (nflip=2 delivers A a frame late so the roll fires +22.235 not +26; **nflip=1** is
correct) and the fan being nominal not reachable. **LIVE BLOCKER: the in-roll STICK STREAM -- a HELD
STICK STEERS THE ROLL.** From the human's own f1 entry at his own facing 35316 our roll matches
bit-for-bit 6 frames then diverges **+88 u lateral**; holding the aim (+88.6), going neutral (+97.5,
worse), and every mid-roll L-pulse window all fail. **This OVERTURNS the s39 "a roll is a zero-branch
segment" premise.** Also: L mid-roll is a ~3-frame PULSE not a hold (a held L keeps the lock live so
`setShapeAngleToAtnActor` re-aims facing every frame). Native fleet still can't adjudicate rolls
(`CourtyardFleet._step_core_frame` passes `has_eye=0` -> feet-aim, the s38 -102 BAM error; needs
`npc_zl1_look` ported to C), and its real 1-frame-BFS throughput is **200-260k steps/s**, NOT the s37
1.06M (that was long shared schedules; the O(n) fleet rebuild does not amortize -- 260k @512 frontier,
137k @8192). Detail: _notes/tetrapush-handoff-2026-07-24-session40.md.


## Session log s52-s66 (migrated from MEMORY.md 2026-07-29; README `## Plan / status` is authoritative)

The s52 "milestones 1/2a/2b closed" claim is SUPERSEDED: node 1's 241-frame plan is stale (198 u off on today's model) and fails Dereck's s60 objective on three rules. Live tier-2 + the model fixes (s53-60) are in [[tetrapush-dtm-delivery]]; s61 put the objective INSIDE the search and solved to **73 frames at timeloss +0** (wall-free, in regime, bit-exact) failing on ONE rule, 31.4 u short. s62 built + gated s61's lateral rank and glide keep and read the terminal as "out of push"; **s63 OVERTURNED that with an exact accounting** (`objective.push_budget`: Tetra is stt-3 so her displacement IS the push) -- the plan buys 935.13 u = **98.5% of the ceiling on EVERY phase, terminal 99.2%**, and the whole 29.6 u shortfall is **27.24 u spent SIDEWAYS**; the human buys the same 12.805 u/f and spends 2.10. s63 also retired the cycle-count lever by arithmetic (cycle atom 23-25 f -> 4 cycles >= 90 f) and found the structural blocker: **inside a roll, Tetra-on-corridor and Link-on-line are ANTI-CORRELATED** (plow ejects her away from him), so no mid-chain rank/keep over roll ENDPOINTS can help. s64 RAN that and **RETIRED it**: the junction's lateral authority IS real (2.6 u/f, reaches corridor offset 0.01 with Link inside the human's envelope) but **cannot be spent -- a constant stick never ARMS, and the arming frames themselves drag her back off** (0.79 -> 12.4), so steering and arming are mutually exclusive inside the junction; all three frontier variants inert/worse, and over the WHOLE reachable cycle-2 set corridor-good and Link-in-box are **disjoint**. s64 ALSO: **Dereck CORRECTED RULE 3 and it disqualifies the 74 f plan** -- the proc-7 negation flips travel 0x8000 AND negates speed so they CANCEL (heading unchanged: it is the LAUNCH, not the escape), and it MIRRORS the entry speed, so -25.73 arms +17.6 (full 26 roll) but the winner's -20.86 arms only +14.3 while still reading `ready=True`. Rule 3 is really a floor on the TERMINAL EBS SPEED (~-22). Measured, NOT wired (wiring it moves the bar, not the score). s65 WORKED OUT + SHIPPED the away-walk atom (`harness/tetrapush/away_walk.py`, gated x4, 696 offline) -- **Dereck gave the RECIPE live: the herd junction's convert-to-positive with the roll replaced by a BACKWARDS SLAM** ('L+up, left/right, slam down'). Measured: [optional ESS turnaround if the EBS faces her] -> ONE L frame + toward-Tetra stick held one more (delay-1: the negation fires next dispatch frame, L released) -> -25.727 -> +17.614 POSITIVE (motion unchanged, still placement frames) -> ~90-deg rotate frame (defeats the genuine-flip gate) -> backwards slam -> procMoveTurn(1) halves the POSITIVE run onto reversed travel: +8.5 up-herd **NO zero crossing** -> walk cap 17 at f8. Separation = the slam frame; Tetra residual 34.8-40 u riding the corridor (lat<9) = the terminal's deterministic undershoot; **3 post-separation sub-17 frames (DIP_BUDGET, Dereck confirmed the dip is inherent -- 0 infeasible)**. Traps (measured, don't re-pay): slam-FIRST decays through zero ~12 dips; no-rotate re-fires the negation (flips back negative); side-stick on the negation frame reads DIR_SIDE (never converts); L+A ballistic hops reverse at 22.5+ 0-dip but A is ruled out (talk / follow shell). s66 WIRED both: rule 3 = `terminal_moving` (cheap scalar, beams) + `escape_ready` (EXACT -- run the atom, `away_walk.fires`; turnaround_ready DELETED), plans scored POST-atom at the SLAM (`score_plan(run=)`/`replay_and_score`); terminal atom mode (`_atom_place`, thread rank aims coord-minus-PROBED-residual -- 38-68 u across states, a constant would be wrong) placed post-atom, `pre_log`/`pre_run` kept for confirm. Atom hardened: `fires` requires SEPARATION (deep terminal can recede at cap with centre still <80 -- Tetra still pushed; crashed the first solve), probe clones detach a wired camera (commanded csangle recorded -- the C-stick-slew CAMERA LEG is open). **Re-baselined solve (beams dumped `_generated/s66_solve_beams.json`): NOT placed -- closest POST-atom 26.494 u at slam f78 (+5), atom firing, bit-confirmed; the s61 "31.4 u at 73 f" was rule-3-false, never a plan. Shortfall still DIRECTIONAL (lat -12.4 off thread, placeable=False).** **NEXT: attack the lateral handoff off the DUMPED beam (~1-min loops: tframes/atom_probes/rank; if the glide can't pay ~12 u at 2.9 u/f, fix upstream -- cycle-2/3 corridor-vs-squareness keeps or the ROLL ENTRY axis, still the standing lever), then the entry leg (walk_to_entry/reach_precise to ENTRY_ROLL_POS facing 40835), then the camera leg.** **s67 RAN that next step and INVERTED it -- the shortfall is an AIM, the terminal has ZERO authority, and the blocker is roll-entry SQUARENESS at cycle 2. New `harness/tetrapush/aim.py` + `tests/test_aim.py` (6), suite 703.** (1) `push_step` = the plow as a **0-ULP ONE-FRAME ORACLE**: `f32(Tetra + (80-centre_feet)/2 * unit(Tetra - exec_centre))` IS FreeRun.step's next Tetra bit-for-bit on every contact frame whatever stick is delivered (the pipeline acts 2 frames late, so the frame's push is already decided), 0 at the bar -- Tetra's whole side of a placement is analytic. (2) THE SIGN WAS BACKWARDS: cycle-3 endpoints hand her over at lat +8.90/+21.19/+24.61 against a thread at -2.27..+7.94, so she must LOSE lateral (every stick does) and the s66 plan lands at -4.43 -- it OVERSHOOTS; the s63-s66 'glide cannot buy 12 u of lateral' framing is RETIRED. (3) What is short is the AIM and the window is a RAZOR: the thread is 12.2 deg off the herd axis and the approach comes in 13-14 deg off it, so she arrives END-ON and the directions reaching the 47.6 u segment span **0.53-0.62 deg** (`aim_window`); the endpoints aim 10.05/11.94/45.85 deg steep, miss by 12.28/11.89/47.72 u (`aim_miss`), and Link's exec centre must sit 9.15/10.86/40.96 u lower in lateral (`centre_lat_needed`). The corridor-GOOD endpoint (Tetra +8.90) has the WORST aim -- the s63 anti-correlation as one number. (4) **THE TERMINAL IS NOT A SEARCH SPACE**: sweep the whole `_terminal_alphabet` (290 sticks x L) off the real endpoint and Tetra's position is bit-identical across every branch for FOUR frames (spread 0.00000 u; 2-frame input delay + the actors separate) -- THE explanation of s61-s63's rank-inertness (2, 2, then 6 byte-identical 31.406 u): nothing to rank. Only the escape's own conversion has authority (why the s66 winner glides 0 frames). (5) The keep moved out one stage: `full_herd.escape_probe` + `extend_cycle(escape_keep=)` + `chain_herd(last_escape=True)` rank a last-cycle endpoint by what its real ESCAPE lands (`away_walk.probe` -> `aim.landing_miss`), superseding `glide_probe`; re-run off the dumped cycle-2 beam (461 s) = right metric, INERT -- 21 survivors, 18 fire, **best lands 45.62 u off the thread**, same 8 nodes -> the cycle-3 stage cannot reach the handoff, reachability not ranking. (6) THE SPEC HAS A SOLUTION, solved backwards (`handoff_target`): the escape delivers 34.8-47.9 u (OVERSHOOTS `push_reserve` 27.1-43.1 -- its conversion drives Link back in), so hand it Tetra at **along ~894, lat ~+2.5, on line, feet ~52-56 at frame <=69** and its 4-5 frames finish it = **74 frames, +1, inside PREFERRED**. (7) AND THE MISSING FRAMES ARE ONE NUMBER UPSTREAM: the push law integrates, so a roll carries her at the MEAN of its aims (s66 rolls: mean +2.55/-6.42/+16.56 deg vs travel +2.98/-6.36/+18.13, ~205 u each); the HUMAN enters his two recorded rolls at +1.22/-0.70 deg and sits **0.71 u** off the corridor at f44, and **the search's roll-2 entry aims -10.84 deg where his aims -0.70** -- 10 deg over 205 u = the -22.6 u excursion = s63's 27.24 u sideways. The steering lateral is the exec CENTRE's, NOT the feet's (that entry: feet +2.22 u off her lateral, aim -10.84) -- so `extend_cycle`'s `align_keep` keeps on the wrong quantity, which is why it measured inert. **NEXT: put `aim.corridor_aim_error` into `junction_beam`'s frontier as a keep SHARE (never a rank -- s43: ranking on flatness/|lat| starves arming) so cycle 2 rolls from a SQUARE endpoint, then re-run the chain against the handoff target; cheap first look = histogram the ARMED cycle-1 junction endpoints' corridor_aim_error off the dumped beam. Then the entry leg, then the camera leg. DO NOT re-pay the terminal (inertness now PROVEN).** **s68 RAN that next step and the cheap look INVERTED its premise: no keep could have worked, because `junction_beam`'s FRONTIER WAS A GREEDY WALK OVER ONE PHYSICS STATE.** (1) THE ROOT CAUSE, structural: the input pipeline acts a frame late, so ALL of a node's children have IDENTICAL physics (measured 138 children -> **1** distinct `_physics_tag`) and every frontier key -- cone deficit, feet lateral, aim -- TIES across the whole alphabet; a stable sort then fills all 24 slots with PENDING-INPUT variants of one state. So the beam walked ONE trajectory and its reported diversity (636/2288/4832 endpoints) was pending variants of one path -- **the s43 claim 'the win is DIVERSITY, 432 vs the family's 7' is RETIRED**. And the path the stock key walks is the fastest TURN out of the talk cone, which is exactly the motion that rotates Link's ~17 u exec-centre lead sideways: kept aim degraded **-12 -> -20 -> -26 -> -34 -> -41** over five generations, all 4832 armed endpoints came out **-35.9..-15.3 deg** (nothing inside 15), and the aim is QUANTIZED BY JUNCTION LENGTH (jf6 -17.3, jf7 -21.5, jf8 -27.0, jf9 -32.1; only jf5 spans a range). The aim was never missing from the space -- the cycle-1 EXITS read -4.5..+4.8 and a plain ESS glide passes |aim| ~ 0 within 2-5 frames -- it was being SPENT. (2) THE FIX, two keeps no new rank: `_mixed_beam(group=, per_group=)` caps the slots one PHYSICS state may take + `junction_beam(per_state=4, aim_share=True)` gives a share to `_armable_square` (|aim|, and |aim| + cone deficit in DEGREES -- one scalar so neither starves: |aim| alone finds ZERO armed endpoints, cone alone walks to -41). Squarest armed endpoint per cycle-1 exit stock -> fixed: node 1 **-15.34 -> +0.03**, node 2 -15.56 -> -1.90, human -2.98 -> +2.42; nodes 0/3 UNMOVED at -33/+29 under a frontier 4x wider. FASTER too (46 s -> 22 s). Real cycle 2 (off the dumped c1 beam, same budget): corridor offset **44.9 -> 37.0 u**, Tetra lat -39.9 -> -32.1, plan_bound 72.92 -> **72.81 f**, 7 -> 8 survivors -- real but SMALL (the human's cycle 2 is 0.71 u off). (3) TWO NEGATIVE RESULTS worth not re-paying: (a) the `probe_cap` IS a prefix (probes `uniq[:250]` in collection order, dropping all **932** endpoints within 5 deg off one node) but every share of the pool spent on squareness took cycle 2 from 8 survivors to **ZERO**, twice -- rollable-AND-continuable endpoints concentrate in a few early states and only some PENDING inputs of those roll (s42 arming), so a state-spread pool holds one pending each of mostly-uncontinuable ones; `_probe_pool` keeps the PREFIX as default, `square_pool` is the knob. (b) NEVER rank a keep on the ENDPOINT's aim once a roll can be probed: at jf 10-12 the aim swings 5-8 deg/FRAME, so a +1.12 deg endpoint fires a roll landing **37.6 u** off with Link 51 u off her lateral and the REAL next junction arming **0** endpoints (`junction_quality` was telling the TRUTH, not proxying badly) -- so `roll_probe` now returns `dict(rate, off, off_rate, n)` (the corridor offset its best surviving roll DELIVERS, free from the sweep it already runs) and `extend_cycle`'s `square_keep` ranks its share on THAT. Also measured: the roll's own stick has ~36 deg of authority over the realized travel (entry-vs-travel corr only +0.665, mean |err| 14.8 deg, travel from ONE endpoint spans -26..+10), and rolls within 2 deg of the corridor EXIST -- 25 of them, **1 alive** -- the survivor needing Link 53 u off her lateral and failing `junction_quality` (s63's anti-correlation, at the roll-entry level). Gates `tests/test_full_herd.py` +3 (the frontier tie structurally, the pool's two behaviours as pure selection, a slow stock-vs-fixed contrast minted from state 2 via `cycle1_nodes`); suite 705 pass / 0 fail / 8 xfail. GOTCHA that cost ~10 min: two of those tests spy via `inspect.getsource`, which reads the FILE -- editing `full_herd.py` while the suite runs fails them spuriously. **NEXT: buy the squareness at the CYCLE-1 EXIT -- it is a property of the exit, not of the junction search** (2 of 5 exits cannot be squared at all; the human's yields a square armed endpoint at jf 8 that he rolls from, ending cycle 2 0.71 u off). Widen the cycle-1 candidate set and add a keep share by a JUNCTION-SQUARENESS PROBE = the smallest `roll_probe`-`off` reachable through that exit's junction (~15-25 s/exit, `cycle1_nodes` itself ~12 s), then re-run the chain against the handoff target; and point the mid-chain aim key at `aim.handoff_target` (coord minus the escape residual) not `push_corridor`'s coord -- a ~0.7 deg bias at cycle-2 range against a 0.53-0.62 deg window at the end.** **s69 BOUGHT IT, and cycle 2 went 37.00 -> 8.97 u off the push corridor** (Tetra's lateral -32.10 -> -3.65, Link's lateral off her +11.14 -> -0.69, `plan_bound` 72.81 -> 72.69, roll survivors 18 -> 71; the stock run reproduces s68 exactly so the contrast is clean). WHAT MADE IT WORK was measuring what cycle 1 actually chooses: instrumented at R1/R2, the ENTIRE candidate set is ONE roll aim (of the whole fan x 3 l_windows exactly 3 pairs survive and all three are the same aim, want 35324; the l-window only picks the exit frame f20/f21/f22 and f20's whole tcs family fails `junction_quality`) swept over the 25-value `derived_target_css` grid, of which only 6 arm anything -- and EVERY member scores `plan_bound` 71.90, so the frame rank cannot separate them and whatever else the cut ranks on IS the decision. It ranked on `junction_quality` (frames-in-box), which is ANTI-CORRELATED here: deliverable squareness spans 11.20..141.83 u and quality's top three are 141.83 / 27.81 / 14.67, the best at quality rank 5. NEW `full_herd.junction_square_probe` (run the exit's junction at a coarse budget, report the smallest corridor offset a real roll DELIVERS -- `roll_probe`'s `off`, never the entry aim) + `cycle1_nodes(square_keep=, tcs_keep=<no cut>)` + `chain_herd(c1_square=True)`. **THE POOL is what makes the probe honest** (`_probe_pool(spread=False)`): on three real exits prefix-only reads 1.34/none/27.02, squarest-only none/141.83/14.67, the UNCAPPED mix 1.34/141.83/14.67 (12 rollable where each single pool found 9), and s68's state-CAPPED pool none/141.83/25.89 -- the cap calls an exit that reaches 1.34 u unrollable. The keep is OPT-IN: 15 non-slow tests call `cycle1_nodes` just to get a node, and defaulting the 308 s probe on added ~77 min to `pytest`. ALSO SHIPPED `aim.handoff_corridor` -- `push_corridor`'s shape aimed at `handoff_target` (residual MEASURED off the real atom: 43.65 along/+5.47 lat at feet 56 -> target along 893.89 lat +2.47, reproducing s67's backwards solve), the two lines asking aims 0.46/0.68/1.19 deg apart at along 276/500/700 (GROWING as the plan closes); wired `chain_herd(handoff=True)`, and **measured INERT at cycle 2** (identical 8 survivors) -- kept ON because it is the correct target. CONTAINMENT HOLDS ([[search-space-contains-human]]): at f21 the human's Tetra is bit-identical to the search's exits and his facing is within 4 BAM; his exit delivers 1.34 u where the best grid member delivers 11.20, and the gap is CAMERA REACHABILITY -- his exit csangle 38776 vs the grid's reachable jump 38675 -> 39085, because `roll_segment` holds ONE `target_cs` for the whole roll so the achieved exit csangle quantizes coarsely and non-monotonically (tcs 38404 -> cs 38159 while 38276 -> 38624; 39172..39684 all -> 39428). CYCLE 3 off it: the placement frontier moved **45.62 -> 15.70 u** off the thread with ALL 18 escapes firing, but at **78-80 frames vs the 75 budget** (so at the real budget the cut empties) -- and the frames are legible: the endpoints sit 53 u PAST the handoff target (along 947 vs 894), Tetra's lateral back out at -26, Link 45 u off her lateral, corridor offset 8.97 -> 28.62 across cycle 3. So the binding constraint is now FRAMES, and the SAME blind cut exists one cycle up. Suite 708 pass / 0 fail / 8 xfail, land goldens byte-identical. **NEXT: (1) give `roll_candidates`' `tcs_keep` an aim-aware key at cycles >= 2 -- `junction_quality` is a ~5 ms glide so it can report the corridor aim it reaches instead of only frames-in-box + |lat|; calibrate that cheap proxy against the probe on cycle 1's already-dumped grid, since a full probe per (aim, tcs) at cycle 2 is unaffordable; (2) PRICE THE OVERSHOOT -- the last cycle must want to arrive AT `aim.handoff_target`, not 53 u past it. Behind those: the camera leg (per-frame C-stick in the roll) to make csangle 38776 reachable, worth the remaining 8x at cycle 1.** AIM-WINDOW GOTCHA: `aim_window` is NOT monotone in the lateral offset (it is a subtended angle -- 10.04 deg on line at the target, 3.25 at +10, 3.18 at +20, 8.37 at +30); the 0.53 deg razor belongs to the s66 handoff's along AND lateral together, so a gate must assert measured points, never a trend.
 **s71: THE SQUARE ARRIVING ENDPOINT EXISTS -- THE SCREEN'S AIM RESOLUTION COULD NOT SEE IT.** s70 handed over "probe the jf-6 band wider reporting `off` beside `arrive`; if a square arriving endpoint exists the keep is a COMBINED key". Ran the census 20x wider than asked (`roll_probe(collect=)` -> the JOINT (|over|,off) frontier per band, every armed endpoint of two real cycle-2 exits x all 8 jf bands, 9022 endpoints / 98 surviving rolls / ~50 min): the arriving band (jf 6) holds 2 rollable rolls in 416 endpoints and NEITHER is square (off 47.7/35.7), jf 7 reads 0 of 420, and jf 8 holds 23 of which one delivers off 3.08 at over +18.8 -- on which evidence the squareness lives one band PAST the arrival. But the SCREEN was the constraint: `roll_probe` swept +-0x2800 (112.5 deg) about the HERD bearing at step 24 (~27 aims) while `roll_candidates`, the stage it screens FOR, uses step 8; death is 95-99% `followed` (Link past FOLLOW_ENGAGE_DIST, which a ~223 u roll does the instant it stops plowing her), so survival is a NARROW CONE about the bearing to TETRA -- the 33 survivors occupy 18.5 deg of that 112.5 herd-relative, 13.4 Tetra-relative, i.e. ~85% of the rollouts were spent where nothing can live. Re-centred on the per-endpoint bearing to her and narrowed to `pursuit_box.max_delta` (+-21.35 deg, the RECORDED regime; containment measured -- the human's own two rolls sit at +0.76/+0.63 deg, the widest survivor at 7.65), ~31 aims at step 8 cost what ~27 at step 24 cost. **jf 7: 0 rollable (shipped) -> 2 (step 8 wide) -> 14 (step 8 narrow) -> 66 of 420 (step 1 narrow, 69 rolls)**, and that band's best roll leaves Tetra at lateral +0.26 with Link 1.2 u off her lateral -- predicted escape landing 0.53 u at ~71 f, where s70's plan predicted 36.4 and its exact escape landed 57.69. Its frontier is smooth at full resolution ((6.8,1.1,+3.5,-0.1), (9.1,0.3,+2.2,-12.2)); 1013 s for the ONE band, so full resolution is a TWO-STAGE screen's job, not a default. TWO REAL KEEP BUGS from the same census. (a) `aim.handoff_corridor` is a line from the origin through ONE point (the thread's near end minus the residual) while the target is a SEGMENT whose lateral falls 0.215 u per u of along -- 78x the corridor's own slope -- so `off`, what `square_keep` ranks, is right only where the arrival is exactly on target; SHORT of it the near end clamps and the two agree (which is why this never showed while the chain undershot), PAST it the ask is wrong by 1.33 u at along 900, 4.11 at 912.7, 10.18 at 949.5 against PLACEMENT_BAND 1.0, and a roll cannot stop short so every arrival the last cycle chooses between is past it. On four measured rolls (jf 7/8/10/12) `off` ranks them in EXACTLY the reverse order of the escape landing, putting LAST (5.01) the roll that lands best (2.93) and takes the fewest junction frames. Fix = `aim.thread_miss` (extracted from `landing_miss`, bit-identical) + `roll_probe(thread=,resid=)`'s **`land`/`land_frames`/`land_off`/`land_over`** + `extend_cycle(land_keep=)`; it SUBSUMES `off` and `arrive` rather than joining them, and is inert mid-chain by construction (gated). (b) `away_walk.probe` ranked its ~8 variants by rule-3 compliance then `d_e_end` = how far Link got toward ENTRY_ROLL_POS, i.e. the SEPARATE entry search (s60) -- but s67's own finding is that the atom's conversion frames are the LAST inputs with authority over Tetra, so its knobs ARE part of the placement. Ranking the COMPLIANT variants by the landing improves 6 of 8 real arrivals (median 2.70 u, max 10.08) and takes the sample's best from 16.34 u off the thread to **6.25** (7.15 u from a genuine coord) at 77 f; `rotate_side=+1` wins 6 of 8. Wired `away_walk.probe(thread=)` / `escape_probe(atom_landing=)` default ON, acceptance (l_ok, follow shell, separation, DIP_BUDGET, receding at the cap) a HARD term ahead of the landing, and without `thread` the key is bit-identical to s65's. THE LAW behind (b), measured over the sweep: **resid_lat tracks Link's lateral offset from her at -0.53 u per u (r -0.926)** and resid_along COLLAPSES from 41.60 u aligned to 6.29-15.33 at 30-47 u off -- so `handoff_corridor`'s single measured residual describes the ALIGNED case only. CHEAP-KEY CALIBRATION against the real atom, 35 firing picks (the s70 method): `land` r +0.834, `off` +0.783, |over| -0.423, |link_lat| +0.326 -- `land` is the best cheap key, the sign on ARRIVAL is NEGATIVE, and all are weak enough that the true landing must be probed (what `escape_keep` is for). **END-TO-END, THE AFFORDABLE WIRING IS NOT YET A WIN -- report it as it measured**: cycle 3 off the same dumped s69 cycle-2 beam with the narrow fan + step 8 + land_keep at the SAME 250-of-4622 pool gives 12 roll survivors -> 3 after the beam (all identical, along 936.64 lat -24.49, off 27.08, over +42.8) landing 21.46 u off the thread at 77 f, bound 81.41, 1116 s. That beats s70's in-budget arrival (57.69 u at 71 f) but LOSES to s70's best-landing survivor (15.70 u at 80 f), and the beam collapsed because at a fixed `step` the narrow fan is a different SUB-LATTICE and found only 10 and 4 rollable endpoints on 2 of 6 nodes (zero on the rest) at that cap. The value is in the census + the atom rank; the wiring needs the two-stage screen. Gates +4 (test_aim: the one-point line + thread_miss==landing_miss; test_full_herd: `land` additive/min-over-fan/==thread_miss/mid-chain-inert/the four-roll INVERSION, and the re-centred fan derived+not-binding; test_away_walk: the atom rank), suite 716 pass, 8 xfail, land goldens byte-identical. Commit 54c439f. GOTCHAS: "0 rollable" is a statement about the SCREEN not the band (jf 7 read 0/2/14/66 at four settings); at a fixed `step` the narrow fan is a different SUB-LATTICE, NOT a superset (jf 6: 20 wide vs 10 narrow) -- the strict win is RESOLUTION; DEDUPE before correlating (a 12-row sample put |link_lat| first at r +0.878 and `land` last, but 8 rows were the same arrival). NEXT: (1) probe the TRUE escape (landing-ranked atom) on the step-1 jf-7 rolls -- the prediction is OPTIMISTIC every time (pred 0.12 -> true 16.34; 2.93 -> 10.70); if one lands inside PLACEMENT_BAND the plan is CLOSED at ~75-77 f and the rest is the frame budget; (2) make the screen TWO-STAGE (`extend_cycle(probe_refine=)`: step 8 to find which endpoints are LIVE, step 1 on those only -- survivors are 2-16% of a band). Dumps in _generated/s71/. **s71 EXACT-ESCAPE RESULT (the frontier this session actually bought): the real atom (landing-ranked) on the 15 best FULL-RESOLUTION jf-7 rolls fires 18 of 18 and lands 4.90 u off the thread, 4.902 u FROM A GENUINE COORD (best coord distance in the set 3.124 u -- over +9.2, off 5.00, Link 2.9 u off her lateral, escape bound 77.89), from a 71-FRAME arrival at plan_bound 73.76, i.e. inside objective.frame_floor's PREFERRED 74 let alone the 75 budget. Against the s67/s70 frontier of 15.70 u at 78-80 frames that is 5x closer at 7-9 fewer arrival frames. STILL OPEN: the ESCAPE's own bound (freeze_f 4-6 -> 76-77 f, plus the landing's remaining ~1.5 thread_frames = 77.50) and aim.handoff_spec, which needs the landing inside PLACEMENT_BAND 1.0 and reads False on all 18. Also: jf 6 at full resolution gives 126 rollable of 416 (vs 2 shipped, 63x) but its CEILING is 16.13 u -- jf 7 is the band. The prediction stays OPTIMISTIC and only ~0.73 correlated, and the best-PREDICTED roll was not the best-TRUE (pred 0.53 -> true 12.55; pred 7.64 -> true 4.90); across the two samples no cheap key dominates (census 35 picks: land +0.834, |link_lat| +0.326; full-res 18 picks: |link_lat| +0.827, land +0.728), so `land` is the right axis to KEEP on but the landing must be probed. NEXT, concretely: (a) re-rank the endpoint keep by escape_probe's BOUND not its miss, and hunt arrivals whose atom freezes in 1-3 frames (one row freezes in 1); (b) probe all 69 jf-7 rolls exactly (~10 min) since the predictor mis-orders them. **s72 ANSWERED BOTH s71 STEPS AND FOUND THE PLACEMENT WAS NEVER IN THE HERD'S HANDS: the ESCAPE ATOM's two unswept knobs move Tetra further than a cycle of search does, and the WHOLE frontier is conditional on a camera angle nothing in the plan pays for.** (1) The wide exact probe CONFIRMS s71's frontier rather than moving it -- all 69 step-1 jf-7 rolls, exact escape, **13 s** (the atom is ~0.06 s, not the '2-5 s per endpoint' the docstring claimed, so an exact escape over a whole band is free and a PREDICTED one is never needed again): best landing 4.90 u, best coord 3.124 u, identical to the 15 best-predicted. (2) The BOUND-rank is worth 2 frames (77.50 -> 75.51 at freeze_f 4 vs 5); the freeze_f-1 arrivals are real and useless alone (42-50 u out), so frames and landing must be priced TOGETHER. (3) The s71 two-stage screen CANNOT BE BUILT: per-endpoint survival is **ONE alphabet member wide** (median 1 aim, widest window 0.04 deg over 200 rolls), so a [::step] fan is a strict SUBSET of the full-resolution one and no refine stage recovers the misses -- probe_step=8 finds 21% of jf 7's 66 live endpoints and 8% of jf 6's 126, losing jf 7's best bound (77.54 vs 75.51) and jf 6's best landing (32.13 vs 19.97). THE AXIS IS THE WINDOW: every survivor sits within 8.34 deg of the bearing to Tetra and both bands' best arrival within 2 deg = 20 aims/endpoint against the shipped 31-35, so the complete screen is the cheap one (wired `extend_cycle(probe_half=)`; a per-state budget, since the alphabet is NOT uniformly dense -- on the human's own exit +-2 deg holds 62 of 429 where uniform gives 40; a fitted lead does not shrink it, pooled residual +-7.4 deg despite r -0.87..-0.90 WITHIN jf 7). END TO END that is now a WIN (it was not at s71): cycle 3, same beam and 250-of-4622 pool, probe_step=1 + probe_half=+-4 deg + land_keep + swept escape -> **21** roll survivors -> **8 diverse** (s71: 12 -> 3 identical), best lands **0.49 u** off the thread at 80 f with handoff_spec **True** (first True in a chain run) vs s71's 21.46 u and s70's 15.70; 1637 s. (4) THE SESSION'S REAL FINDING: `away_walk.probe` swept 8 variants deciding WHEN the atom separates and where LINK ends up, and left ``flip_bearing`` -- the direction its conversion frames PUSH HER, the last inputs with authority over her (s67) -- at the herd down-bearing, with ``rotate_off`` at 0x4000. Swept (0x400 over +-56 deg x 4 rotates, ~30 s an endpoint) over all 112 unique arrivals of both bands = 51067 firing variants: the frame-capped frontier is **75 f -> pd 1.644 u**, 76 -> 1.242, **77 -> 0.202**, 79 -> 0.079, handoff_spec TRUE for the first time. `replay_and_score` confirms end to end: **frames 75, timeloss +2, INSIDE the accepted budget**, terminal_ok True, wall/regime True, complete **False** on the placement band alone -- **0.644 u**. Sweeping it FORCES the frames rank (the same arrival reaches 0.33 u at freeze_f 12 and 1.64 at 4, so a landing-only rank pays 8 frames for 1.3 u against a 2-frame budget): ``rank='frames'`` = freeze_f + thread_frames. The landing is PIECEWISE CONSTANT in the flip bearing (plateaus 10-25 deg wide), so 0x400 resolves it and 0x40 found nothing between. (5) THE OPEN ITEM, and it is not new to s72: every atom number since s65 is computed at a COMMANDED csangle (probe uses snap_csangle for EVERY variant, including turnaround_first=False ones that never snap) **105-111 deg from the live one**; at the LIVE csangle **1024 of 1024** variants die on ``l_ok`` -- the arrival's EBS still faces Tetra so Dereck's rule-1 turnaround is MANDATORY and needs the snap window (493 of the same 1024 fire at the snap) -- and the band's best placement there is **46.3 u**. One cycle-3 roll's C-stick slew delivers ~**47 deg** of the 105 (0x9ae6 -> 0x79c1 in 19 f) and asking for it CHANGES the arrival (the roll's exit ESS decodes against csangle), so aim x target_cs is a joint search -- which that stage already is. NEXT: (a) charge the csangle to the camera channel (two rolls + the junction C-stick, make the atom's required csangle a TERM in the tcs cut); (b) or screen the band for arrivals already facing AWAY, where rule 1 skips the snap and the leg disappears; (c) then the last 0.644 u -- only node 0 of the s69 cycle-2 beam is probed at full resolution, and the cycle-3 run's 8 diverse survivors are the next pool. NEGATIVE results worth not repeating: jf 5 arrives 2 frames earlier (69 f) and tops out at **10.9 u** (77 live endpoints of 210, all 78 arrivals fire, best bound 74.33 at pd 57); a flip arc derived from the ARRIVAL's travel excludes the winner (61 deg off it, 1.644 vs 4.112 in-arc) because the DIR_BACKWARD cone is about travel at the CONVERSION frame; and never append the atom's own frames to a log handed to `score_plan` -- it probes the atom itself, so that double-counts and re-probes from a separated state (read pd 21.5 where the real score is 1.644).


**s73: MILESTONE 2 MET OFFLINE AND GATED -- `objective.verdict` TRUE.** `objective.replay_and_score` on a complete state-2 input log: **75 frames (floor 73, timeloss +2, inside `TIMELOSS_BUDGET`), Tetra 0.4321 u from genuine coord 274, `complete`/`terminal_ok`/`wall_ok` (margin 56.37)/`regime_ok`/`within_budget` all True, atom `cs_bill` 0**. Tracked as `fixtures/courtyard_plan_s73.json` (log ENDS AT THE ARRIVAL + provenance + the `atom_kw` it must be scored with) and gated by `tests/test_objective.py::test_the_shipped_plan_passes_the_whole_objective_from_its_input_log_alone`. WHAT CLOSED IT: s72's "the frontier rests on a camera angle nothing pays for, 105-111 deg vs one roll's 47" was a SCAN ORDER, not a physical bill. `snap_csangle` walked `range(0, 0x10000)` and returned the FIRST member of the turnaround's snap window -- and that window is **78.8-81.6 deg WIDE** (28-30 members on the 512 grid, measured over all 112 unique arrivals of both bands), so the scan returned its FAR edge: 91.3-113.8 deg off live on EVERY arrival, which is the camera state every atom result s65-s72 was computed at. The NEAREST member is **15.3-37.8 deg (median 21.0)** and one roll's C-stick realizes **-46.6..+40.7 deg**, so the bill fits inside the LAST ROLL's otherwise-idle camera channel. Also measured: **0 of 112** arrivals have an EBS already facing away, so s72's proposed thread 2 has no takers at the neutral camera -- the camera IS the answer. THE CODE: `away_walk.snaps_at`, `snap_csangle(near=True)`, `snap_bill(free/bam/deg)`; `escape_atom(csangle=)` now defaults to the arrival's own LIVE csangle (the atom's C-stick is neutral so the camera holds it -- replay-faithful) and every result carries `cs_bill`; `probe(csangle='live'|'snap'|int)`; `full_herd.ESCAPE_TCS_SPAN=0x2800`/`ESCAPE_TCS_STEP=512` (the roll's measured reach; the snapping targets are 1-2 members wide AT 512, a razor), `camera_probe_key` (a `tcs_probe` KEEP share on what the arrival owes), `roll_candidates(tcs_span=,tcs_step=)`, `extend_cycle(tcs_escape=)`, `chain_herd(last_camera=)` default ON for the last cycle only (mid-chain the widened band strands the next junction, s42). **63 of 112 arrivals then owe NOTHING** (84 (arrival, target_cs) pairs; **0 of 112** at the shipped neutral camera), and the FAITHFUL frontier over those pairs at s72's own resolution beats the commanded one: **75 f -> pd 0.432 u** (miss 0.699, `handoff_spec` True) vs s72's 1.644 at the same 75; 74 -> 24.68, 73 -> 32.31, 79 -> 0.080. THE TERM IS A KEEP, NEVER A FILTER, and that is measured: over 656 (arrival, tcs) cells **274 fire** at the live csangle and only **12 snap** -- all 12 fire, but **262 firing cells do not snap**, because a camera steer also moves the arrival's own EBS facing and can clear the front cone by itself (the 75-frame winner fires at `turnaround_first=False`). As a keep of 3 the bill still retains a BEST-bound firing cell for **13 of 14** arrivals at median **0.00** frames of loss, where the front-cone margin retains one for 7 (widest-first) / 3 (narrowest-first) and cannot screen at all (the frontier cell's own margin is 5.2 deg, BELOW the dead cells' median 11.1). THE TRAP THIS CREATED: a SYNTHETIC bed (`synthetic_hot_arrival`) has no roll to have paid its bill, so its inherited csangle sits ~25 deg outside the window and **0 of 2048** swept variants fire -- beds that run the atom need `snap_camera=True` (it fabricates the camera the last roll delivers) or an explicit `csangle='snap'`; that is what broke `test_aim`, `test_objective` and `test_full_herd`'s atom-wired terminal when the default flipped, and why `aim.handoff_corridor` probes its residual with `csangle='snap'`. `_atom_place`'s round-trip band moved 6.0 -> 8.0 for a measured reason (the residual is state-dependent: 39.69 u probed at the bed vs 34.47 achieved from the shifted bed, and the near-edge camera requantizes the atom's sticks so its `rotate_side` flips). **AND THE REST OF THE GRID IS NOT WHERE THE LANDINGS ARE -- THE SNAP TEST IS**: the widened grid spans **4592** cells (every one arriving at 70-71 f, so all frame-eligible) and the 84 snapping pairs are 1.8% of it, so sweeping the rest was the obvious next move -- measured first on a uniform **224-cell (4.9%)** sample at full flip resolution, **don't**: 67 fire (30%) and the frontier is 75 f -> pd **18.50 u**, 74 -> 23.16, 73 -> 37.24, best bound 75.56, `handoff_spec` True exactly ONCE, vs the snapping pairs' 0.432 at 75. The dense census agrees (its best-bound cell is its SNAPPING one; its 262 non-snapping firing cells never beat it). So FIRING is common (30-42%) and LANDING is not, and the snap test selects landers (mechanism unexplained). NEXT: widen the SNAPPING population, not the grid -- (1) finer `ESCAPE_TCS_STEP` (snapping targets are 1-2 members wide AT 512, so 256/128 should multiply the set), (2) the other jf bands + the other cycle-2 beam nodes (everything s71-s73 measured comes from ONE node, jf 6/7; `chain_herd(last_camera=True)` now searches them with the camera term in place, so a real chain run is the vehicle), (3) `replay_and_score` each candidate and bank verdict-True logs as fixtures -- 74 f (`TIMELOSS_PREFERRED`) is the next rung. Then the out-of-band tier-2 DTM confirm (`[[tetrapush-dtm-delivery]]`) and the SEPARATE entry search (`walk_to_entry`, never coupled -- Dereck s60). Scratch (gitignored): `_generated/s73/s73_{window,tcs,faithful,score,screen,wide}.json`; every script rebuilds the endpoint pool (~105 s) from `_generated/s69_cycle2_handoff.json`. **s74: THE FINER CAMERA GRID IS A CLEAN NEGATIVE AND THE 2-FRAME TIMELOSS IS THE ESCAPE'S OWN DEAD PUSH FRAME.** s73's handoff step 1 was run: `ESCAPE_TCS_STEP` 128 grows the snapping set 2.4x (63->83 of 112 arrivals, 84->199 pairs, 33927->85192 firing atom variants, 20 arrivals with sub-512-BAM windows, all at -13.4..-21.1 deg) and moves the frontier 0.000 u -- pd 0.432 at 75 f both ways, best-by-bound bit-identical 75.12 (jf 7 end 285, frz 4), and `replay_and_score` on the new winner returns the SAME plan the shipped fixture holds (75 f, pd 0.4321, coord 274, verdict True) at tcs -32.3 instead of -30.9 deg. Cause is separability, already gated: `target_cs` is EXIT-ONLY for Tetra, so over 161 targets x 112 arrivals her arrival along/lateral spread is 0.00 u -- a finer grid buys more camera states for the SAME arrivals. MORE CAMERA IS NOT MORE PLACEMENT. Recorded as data in `full_herd.escape_tcs_step_note()` + gated (the finer grid strictly contains the shipped one, so the null is not a sampling artifact). Then the frames were PRICED instead of searched for -- new `away_walk.push_profile` + a per-frame ``tstep`` on `escape_atom`'s rows (her own displacement that frame, NOT a ``tres`` difference, which under-reads a turning plow): the last ROLL pushes 12.911 u/f = 99.3% of `objective.PUSH_CEILING` over all 19 of its frames, the ESCAPE's 4 frames push 9.177 = 70.6%, profile 16.506 / 0.000 / 12.469 / 7.732 -- frame 1 is the biggest push in the whole plan, frame 2 (the proc-7 NEGATION frame, flip receding + conversion not yet fired) plows 0.000, frame 4 (the slam) plows on a HALVED mNormalSpeed -- so the escape costs 1.18 frames of the 2-frame timeloss by itself and that is Dereck's recipe's shape, not a knob. THE RUNG LEDGER (the durable result): recovery <= -0.24 u at freeze_f 1 / 22.94 at 3 / 34.54 at 4 (max over 85192 variants; bounded above by its own plow, which is the GATED invariant that makes the ledger admissible), arrival bands 70 f (pd_pre floor 52.97, jf 6 end 391) and 71 f (34.98, jf 7 end 285), so 75 f = 71-f arrival + frz 4 needs pd_pre <= 35.54 and REACHES it with 0.56 u of margin (exactly why the frontier never moved), and 74 f is short on every route even at a perfect escape aim: A (71-f + frz 3, needs <= 23.94) short 11.04 u / ~5.0 at the plow bound, B (70-f + frz 4) short 17.43 / ~15.3, C (73-f + frz 1, needs <= 0.76) NEVER PROBED. NEXT = the ARRIVAL's LATERAL, one cycle upstream: jf 6's whole band sits at lat -59.68..-11.89 against the spec's +2.48 while its along is already right (885.0..896.6 vs 893.9), jf 7 reaches the lateral (+30.27) only by spending the frame the rung needs, and cycle-2 node 0 -- which s71-s74 all built on -- has the WORST exit lateral of the 8 nodes (-25.608; node 2 -3.654, nodes 3/4/5 -4.893, nodes 6/7 -17.097, all on the same ~12.5 u/f closing line so their extra 3-4 frames BUY the lateral). Route C needs the OTHER target: `aim.handoff_target(thread, (0.0,0.0))` IS the coord thread's near end (coords along 937.53..984.07, lat -2.27..+7.94), and every keep since s70 ranks against `handoff_target` 893.9 = the coord minus a 4-frame escape's residual, so `roll_probe`'s ``arrive``/``over`` penalise exactly route C's arrivals. REACH LADDER measured: node 0's junction pools are far bigger than the two bands ever probed (jf 5:210, 6:416, 7:420, 8:632, 9:420, 10:1156, 11:420, 12:948) and the arrival along walks up ~+15 u per junction frame (jf 5 873.9..883.6 -> jf 11 950.9..952.5), entering the coord box at jf 10-11, but every sampled lateral is -16.5..-61.9. GOTCHA that matters: a DECIMATED band screen reads jf 9 as DEAD (0 surviving rolls of 120 endpoints at step 4) where full aim resolution yields 83 rolls over its whole 420-endpoint pool (per-shard 15/33/15/11/0/8/1/0, clustered) -- s71's 'survival is one alphabet member wide', recurring, so treat a capped survey's along ladder and lateral SIGN as its result and never its envelopes. Also: `roll_probe`'s ``collect`` rows carry ENDPOINT frames not arrival frames (add the roll's ~19), and `rebuild_beam`'s nodes have no ``lat``/``placement_dist`` (compute from ``node['run']``). Gates +2, suite green 724: `tests/test_away_walk.py::test_the_escapes_own_frames_are_worth_less_than_a_ceiling_frame_and_one_is_dead` and `tests/test_full_herd.py::test_the_escape_camera_step_is_measured_right_and_a_finer_one_is_a_null_result`. Commit 6c30d39; handoff `_notes/tetrapush-handoff-2026-07-30-session74.md`. **s74 addendum -- ROUTE C IS CLOSED** (full-resolution whole-pool probe, 325 aims/endpoint over the jf-9 420 + jf-10 1156 pools, 996 s): jf 9 (route C's own 73-f band) yields 83 rolls at along 912.6..932.7 (needs 936.8 -- short 4.1 u), lat -47.6..+23.5, min pd 14.43, **0 in the coord box**; jf 10 (74-f arrivals) DOES enter the box -- 232 rolls, 16 inside, min pd 2.59, the first arrivals this work has measured ON a coord -- but at 74 arrival frames a 1-frame escape only ties the shipped 75. **And the escape at an on-coord arrival is DAMAGE, not recovery**: pd 2.59 -> 20.07 post-atom, 4.22 -> 22.87, best in-box 7.74-8.15 u out, because its ~35 u of push has to go somewhere -- so `aim.handoff_target`'s ~44 u offset is CONFIRMED right and aiming the herd AT the coord is wrong. Route A/B (the arrival's LATERAL at 70-71 frames, off cycle-2 nodes 2-5) is the whole remaining question. OPEN and deliberately NOT claimed: the 3 closest in-box arrivals (pd 2.59/4.22/5.30) have NO valid escape (all 176 swept variants ``l_ok`` False -- Tetra inside the front cone), while the pd-5.59 arrival has 135 variants passing `fires` at ``cs_bill`` 0, EVERY one ``turnaround_first=True``, which `away_walk.probe` refuses via its ``can_snap`` guard (that csangle's snap bill is 40.6 deg). The mechanism is NOT cone-clearing by the snap -- the ESS frame turns 0x1425 (28.3 deg, below the 0x4000 threshold) and Tetra is STILL in the cone immediately after it, so the ``l_ok`` is earned a frame later at the frame the L acts. Buys nothing on that arrival (7.74 u at 78 f vs the shipped 0.432 at 75) but is the same SHAPE as s73's snap scan-order bug: a sufficient condition used as a necessary one. Commit 31448a3. **s76: THE JUNCTION BEAM IS NOT THE BINDING STAGE, AND THE LEDGER THAT CALLED THE ROUTES SHORT IS NOT BAND-PORTABLE.** Ran s75's handoff step 1 at both live rungs, full aim resolution over the whole pool (5700 s / 10 workers), with endpoints dumped as DELIVERED INPUT LOGS so a shard rebuilds one in ~15 ms instead of re-running a 128-wide beam per worker (the ~130 s x 10 s75 paid; the rebuild is gated 0-ULP against s72's banked floor first, `s76_check.py`). Result: jf 7 (71 f) pool 420->1366->4110 at beam 24/64/128, 3690 new probed, 1081 rolls -> pd floor 34.977->34.162 and along CEILING 908.68->908.68 (**0.00 u**); jf 8 (72 f) pool 632->2204, 444 rolls -> floor stays 23.495 (the widened pool's own best 24.499 is WORSE) and ceiling 920.22->920.70. Route A needs 23.94, route D 16.08. **The endpoint stage is saturated -- do not widen it again.** Also: **`beam` is NOT monotone in width** (`_mixed_beam`'s per_group cap is shared ACROSS its orders, so more slots for order 1 can starve order 2) -- at jf 7 beam 128 contains all 420 of beam 24's, at jf 8 the pools are DISJOINT (0 shared physics tags); the honest floor is the UNION. **NEW: `objective.along_floor` (+2 gates), the LATERAL-INDEPENDENT screen** -- coords start at along 937.53 and along/lat is orthonormal, so `pd_pre >= 937.53 - along` whatever the lateral, and a band's along CEILING (a max over the rolls the sweep already fires) tests the rung for free where s71-s75 each paid ~2700 s to learn it. Ceilings 896.60/908.68/920.70/932.66 at 70/71/72/73 f => best-possible pd 40.94/28.85/16.83/4.88, so every band's floor carries 6-12 u of PURE LATERAL error. **THE CEILINGS ARE A HERD RATE (why the beam can't move them): 98.24-98.53% of PUSH_CEILING from Tetra's state-2 along, the human's own 98.2%; 74 total frames needs 98.55% (freeze_f 2, 72 herd frames) = 0.24 pp = 2.23 u of along (1.23 after the band credit); 75 f needs 97.20-97.99%, cleared by every band -- which is why the shipped plan exists.** NOT a physical bound (asymptotic; a 23-f cycle sustained 13.36 = 102.8%), so it is a SEARCH deficit. **THE ADDRESS (`objective.push_budget`, real best 72-f arrival end 471 aim (171,192)): prefix 45 f 99.56% magnitude / JUNCTION 8 f 93.51% / roll 19 f 99.55%; sideways only 10.27 u over 72 f (prefix 3.22, junction 2.27, roll 4.78). The junction loses 6.75 u of push; route D is short 6.17 u.** Per frame the push is EXACTLY `(CO_RADII_BAR - _centre_feet)/2` -- verified on EVERY frame incl. rolls (cf 45.9->17.036, 59.6->10.188) -- so the sustained rate is set by MEAN contact depth (junction 55.4 vs roll 54.1) and 13.0 is that law's fixed point at advance 26 (KB `actor-push.md` 'How FAR' updated). **THE CORRECTION, which re-opens route A: s75's allowances are PER-ARRIVAL and were borrowed across bands.** allowance = plow(freeze_f)+PLACEMENT_BAND and at frz 3 the plow reads 20.31 (node 5) / 33.76-36.05 (the widened jf-7 band's OWN arrivals) / 48.57 (node 0 jf 10): the borrowed 22.94 REFUSES jf 7 (needs along 913.59 vs ceiling 908.68), its own 33.76 ADMITS it (needs 902.5). **So 74 frames is now refused by the escape's push DIRECTION -- only 21.08 u of the 33.76 u plow points at the thread (short 12.08 u of RECOVERY with the MAGNITUDE already there) -- and by the CAMERA BILL: 0 of 672 variants FIRE at the arrival's live csangle, so these arrivals have no frame answer yet rather than a bad one.** NEXT: (1) re-rank the atom sweep on RECOVERY, not `probe`'s 'frames' -- same knob grid s72 swept, different question, ~100 s/arrival; (2) then sweep `target_cs` and the atom JOINTLY (the bill is NOT separable: the post-roll EBS travel chases csangle so paying it MOVES the arrival, s42/s73; step 512 is right, s74); (3) if direction is capped, the junction's 6.75 u is the only slack left and it is an ALPHABET question (hold mean centre_feet near 54.1 while clearing the +-90 deg cone), not a beam-width one. TRAPS: the band probe's atom column runs at target_cs=None so its `total`/`pd_post` come from NON-FIRING variants (nearly read a 28.9 u recovery off one); `land`/`resid` prices the escape's FULL 40-46 u residual over tens of frames and must not be mixed with `recovery(freeze_f)`; the ledger's floors are world-space `_placement_dist` while the band probes' `_pd` is (along,lat) and differs 5e-14. **s77: THE 74-FRAME RUNG IS CLOSED ON BOTH LIVE BANDS, AND BY ONE QUANTITY -- THE ARRIVAL'S CONTACT DEPTH. Ran s76's handoff in full. Step 1 (re-rank on recovery) was a rank that ALREADY EXISTS: at a fixed arrival pd_pre is constant, so max-recovery is the same ORDER as min-landing (`probe(rank='miss')`); what the recovery question adds is the freeze_f BUCKET (total = arrival_frames + freeze_f). Also corrected s76's number: the CLOSEST jf-7 arrival (pd_pre 34.162) recovers 28.87 u at frz 3, not 21.08 (that is arrival 34.629's row) -- deficit 4.29 u, not 12.08. Step 2, the JOINT target_cs x 672-knob sweep on BOTH bands (2x252 cells, ~680 s each over 10 workers): pd_pre is BIT-IDENTICAL across all 41 camera targets on all 12 arrivals (`target_cs_is_exit_only` re-confirmed live), so the camera buys FIRING and nothing else -- and barely: jf 7 **1 of 252** cells fires (best 75 f pd_post 7.317), jf 8 **5 of 252** (best 76 f pd_post 2.959); neither beats the shipped 75 f at pd 0.432. **ROUTE A (71-f arrival, needs frz 3): the frame EXISTS (4180 variants) and 0 FIRE.** `fires_census` (NEW) names the clause: `l_ok` fails on ALL 672 variants of every arrival, SOLE blocker on 239-364. **AND THE CAMERA CANNOT FIX IT, MECHANICALLY** (`snap_reach`, NEW; KB `mechanics/ebs-turnaround.md`, NEW): the ESS snap fires on `want - travel` (the stick's world want-angle vs TRAVEL, not facing) and the post-roll EBS travel CHASES csangle, so slewing moves both together -- over +-0x4000 at step 64 (110 distinct reachable states/arrival) **0/0/1 of 110 SNAP where the same csangles COMMANDED on a travel-frozen state snap 10/9/9**, and reachable want-travel has an **87 deg HOLE exactly where the snapping band sits**. So a `snap_bill` of 29 deg inside a 56 deg slew span is UNPAYABLE AT ANY PRICE. **ROUTE D (72-f arrival, needs frz 2): the FRAME ITSELF DOES NOT EXIST** -- 0 variants at frz 2 across 6 arrivals x 41 targets x 672 knobs, min separation 3-4, because every arrival of BOTH bands lands at centre_feet 47.0-51.2 where the one real frz-2 arrival sits at 55.50. **AND THE AXIS NOBODY SEARCHED IS PRICED AGAINST s76'S OWN PUSH LAW: DEPTH IS ANTI-CORRELATED WITH PLACEMENT.** Over 1081+444 real arrivals, best pd_pre by final centre_feet -- jf 7: 34.63/34.16/35.46/38.07/37.54/40.27/41.64 at cf 46-48/48-50/50-52/52-54/54-56/56-60/60+; jf 8: 24.50/24.99/25.46/25.75/26.69/28.78/29.90 -- **0.32-0.53 u of placement per u of depth**, monotone past 50, because a contact that finishes shallow was pushing weakly ((80-cf)/2 per frame). The rung wants a SHALLOW arrival (to separate in 2-3) AND a CLOSE one, and a shallower escape ALSO recovers less (frz 2 ~15 u vs frz 3's 21-29): at cf 55 the requirement tightens ~14 u while the supply worsens 3.4 u. That is why s71-s76 each moved a knob and none moved the frontier -- the two requirements are COUPLED by the push law and both bands sit on their own Pareto frontier. SHIPPED: `away_walk.recovery_row` (the producer `objective.along_floor`'s `recovery` never had -- re-derives BOTH banked s75 arrivals 0-ULP, every firing_freeze_f count + per_freeze_f recovery/plow), `fires_census`+`FIRES_CLAUSES` (gated EQUIVALENT to `fires`), `snap_reach`; fixture `fixtures/courtyard_snapreach_s77.json` (3 PRE-ROLL nodes as delivered logs -- snap_reach needs a NODE); +4 gates (2 slow), suite **732**; KB split the over-cap `actor-push.md` -> NEW `mechanics/push-magnitude.md` (per-frame depth law + sustained ceiling + the depth/placement trade) + NEW `mechanics/ebs-turnaround.md`. **NEXT: do NOT re-attack 74 frames on node 0's bands.** (1) the tier-2 DTM confirm of the shipped 75-f plan ([[tetrapush-dtm-delivery]]) and (2) the separate entry search (Dereck s60) are the two genuinely open items. (3) If the 74th frame is still wanted, the ONLY untried lever is a herd path that arrives SHALLOW WITHOUT having pushed weakly -- a STEP rather than a RAMP in centre_feet over the last ~6 frames (the push law forbids pushing hard while shallow, not arriving shallow after pushing hard); that is a junction-ALPHABET question with depth as the objective (`objective.push_budget` prints the per-phase profile, `s77_pareto.py` is the 11 s/band screen), and s76 measured the junction as the only phase with slack (93.5% vs 99.55%). DON'T RE-PAY: the camera/target_cs channel (unreachable by mechanism, gated); the endpoint stage (s76, 0.00 u); COMMANDING a csangle onto a state whose travel was fixed elsewhere and reading a window off it (the s73 mistake in a new disguise -- it makes a cliff appear that no plan can cross); reading a shallow arrival's freeze_f with a deep one's pd_pre (the s76 borrowing mistake in a new column); the synthetic bed for depth (`synthetic_hot_arrival(feet=)` gives min frz 5 FLAT across cf 32.9-62.9 with 0 firing -- relocation-only, no roll, no camera).** **s79 SETTLED THE s45 FORK BY MEASUREMENT AND OPENED THE ENTRY SWEEP (the only remaining item, Dereck s60). ROUTE (A) -- walk Link to the tabulated `seeds.ENTRY_ROLL_POS` the 288-coord list is valid for -- IS DEAD ON ITS PREMISE, not on walk precision: standing EXACTLY there does not clip the console's own Tetra, because her 0.4321 u miss on coord 274 is 0.4314 u PERPENDICULAR to the coord thread and only 0.0240 u along it (LESSON: a placement objective's nearest-sample distance is a poor clip predictor -- always split perp/along, the perp half is the one that decides). ROUTE (B) = sweep the ENTRY, the DUAL of tetra_placements.tsv (the herd is console-confirmed so Tetra is a MEASURED CONSTANT): `harness/tetrapush/entry_search.py`, `fixtures/courtyard_entry_locus_s79.json`, `tests/test_entry_search.py` (16 gates), KB `knowledge/strategy/clip-entry-search.md`. THE MACHINERY: `ShoveCtx.sweep_par` already takes link_x0/link_z0 per sample and the baked schedule is entry-POSITION-invariant (gated), so one ctx maps the whole entry plane at 87k/s. THE RAZOR'S SMOOTH COORDINATE = the cut ray's signed offset from the seam vertex S, `resid = cross(pred-old, S-old)/|pred-old|` with `pred = old + roll_step + push + cut_lunge` -- NOT the seam PLANES (behindA/behindB are negative at 129450 of 130321 entries and separate nothing), and NOT the cut lunge alone (omitting the cut frame's roll step reads +0.23 on known-genuine coords -- the tell). WINDOW MEASURED off the 288 coords at their own entry: 279 read genuine in resid [-2.52e-6,+1.13e-4], width 1.16e-4 = ~ONE f32 ULP here; the 9 that don't sit INSIDE that band, so the window is a dust EDGE to aim with, never an acceptance test. WHAT MOVES IT = the CUT-FRAME PUSH (CrrPos pins the roll at the same wall-braced `old` almost everywhere): push 0 -> resid -0.3294 (bare roll-stab, 0.33 u short), tabulated entry's push (-1.115,-0.258) -> +0.3139, genuine wants ~(-0.551,-0.127). TRAP: at Link's own console endpoint the push is EXACTLY ZERO (she's out of Co range by the cut frame) so probe lines through it read a dead-constant resid -- that looks like 'the entry has no leverage' and means 'no push to modulate here'. TARGET SET: 1735 genuine entries, ONE thin curve 104 u long x 0.93 u thick, all walkable; 856 inside the 230 u follow bar = the USABLE target (past the bar Tetra goes stt-4 and walks, so it isn't an entry), nearest 49.7 u from where the escape leaves Link. REACHABILITY IS FREE: the console log continued with its own last stick held reaches 3.06 u of the usable locus by frame 85, four other steady sticks 3.8-13.1 u by 82-86, ALL still at speedF 17.0 (the cap the roll needs for nspeed 26) -- the escape atom manufactures the slot-7 posture for nothing. PRECISION = window/|grad| = 1.16e-4/1.196 = 9.7e-5 u = one ULP, so it is a DENSITY problem. FIRST SEARCH PASS RAN AND RETURNED 0 BY THE EXPECTED MARGIN: stride-2 fan x 8 holds x 2 base nodes = 3699 candidates / 720 lean groups, 180 s over all 6 realizable facings, and at the best facing (40884) only 4 candidates reach |resid|<5e-3 at 1.0e-3 local spacing -> P~window/spacing~0.11 -> expected 0.4 hits. (My 0.55 estimate from the stride-4 probe was OPTIMISTIC: it took the spacing over 'the 200 closest by |resid|', which are clustered; measure the LOCAL spacing at ONE facing.) TWO KNOBS THE SEARCH MUST CARRY: (i) m351C is NOT free -- lean 0/1 clip the same entry, 64 already doesn't (resid 1.1e-2), and the replayed herd hands Link -191 settling near -160, so a ctx is valid only for its lean and candidates must be GROUPED by lean (link_y doesn't matter at all); (ii) the realizable roll-facing alphabet is only 6 WIDE at the atom's frozen csangle 34325 -- 40617/40665/40773/40884/40925/41037 in the 40600-41100 seam window, and 40835 (the facing the locus fixture is computed at) is NOT one of them; each facing has its own locus (~0.0075 u/BAM) so the target is a union of curves, and the C-stick (~460-530 BAM/frame) is what widens the alphabet. ALSO: rank the SIGNED distance to the window, not |resid| -- the window is asymmetric because its sign is which side of the gap the ray passes, and the pass's own best candidate was -5.45e-5, inside the window's WIDTH on the wrong SIDE. GOTCHAS: `turnaround.entry_from_walk()` reproduces the tabulated entry NEITHER by default (its link0 is the raw slot-7 LINK_START, 107 u off -- the list uses `moved_start()`, Link +110 u NE) NOR with it (2.6 u off, the from-rest walk isn't bit-exact) -- seed from `seeds.ENTRY_ROLL_POS` / `ENTRY_ROLL_FACING` / m351C 0 / `TA.GROUND_Y`, else every coord reads not-genuine with `new` wall-pinned at (-1692.32,-954.92) and it looks like a broken harness; the tsv reproduces 279/288 (missing 20,23,80,125,148,206,209,250,287 -- pinned, don't 'fix'); a SINGLE fanned input frame is INERT (INPUT_DELAY 2 -> a one-frame fan gave exactly ONE distinct child), so the search atom is 'hold stick S for j frames'. NEXT = widen the population ~10x (two-segment holds first, then stride 1 / more base frames / the C-stick), then THE ONE OPEN FIDELITY GATE: the sweep evaluates a RESEEDED roll (`extract_schedule_at` starts a fresh FRONT_ROLL at nspeed 26), so a real A-press roll out of the walk must be shown BIT-IDENTICAL to it -- every hit is a CANDIDATE until that passes.** **s81: THE FAN IS NATIVE AND GATED, AND THE THROUGHPUT'S FIRST FINDING IS THAT THE FAN WAS NEVER THE BINDING CONSTRAINT.** New `harness/tetrapush/entry_fan.py` runs the fan on `CourtyardFleet.run_par`: 43596 candidates in **17.2 s against 1444 s**, equal to the cached s80 Python pass as a DICT -- key AND value, 0 either side, 0 value diffs (write order is part of the contract: the reference collapses ~5.5M writes onto 43596 keys, last writer wins, so hits are applied stick-major / j-inner). It needs a GRAFT: the stripped native config does NOT reproduce the WIRED replay of the console log (diverges at log frame **19** on `facing` -- the proc-9 re-aim falls back to Tetra's FEET where the wired run has her modeled eyePos), so `entry_fan.graft` transplants the wired mid-walk state into a `LandCore`; `LandCore.setup` resets the mid-walk scalars (m34dc/target/msd/direction/roll_frame/_l_prev), all `cdef public`, so restoring them + the delay-1 buffer needed NO pyx change, and the three private fields it cannot reach (attention fade/prev-L, C-up counters, camera privates) are inert here by measurement. csangle is frozen at 34325 through the whole fan window. **THE CORRECTION THAT MATTERS: the acceptance band is a function of the LEAN as well as (facing, thrust).** Swept at one configuration, 448 of 556 finely sampled leans admit something genuine but only ~40% have a real interval rather than one f32 value, and many -- including much of what a real walk-in arrives at -- have NOTHING genuine at ANY entry. s80 measured bands at lean 0 and scored every candidate against them, so recounted per triple the widest pass is **69038 live evals against 345976 DEAD-LEAN draws, 6 near-misses (not 72), E[hits] 0.02 (not 0.23)** -- the requirement is ~250x and not in candidates. `entry_fan.BandTable` keys the band by (facing,thrust,m351C) and caches it (~14 ms each); `stream_search` scores each candidate against ITS OWN triple and reports the dead share. THREE MORE MEASUREMENTS: (1) hold length was NOT saturated (jmax 12->36 = 43596->69169 candidates) and saturating it yielded **ZERO** extra near-misses -- longer walks go PAST the locus, so raw candidate count is not the figure of merit; base nodes past n0=6 add exactly 0. (2) The productive facing window is **32 BAM wide** -- sweeping facing at 1 BAM over the whole seam range (2703 configurations, 37 s) finds 48 productive, ALL in 40816..40847, one window, thrust 15 carrying the real 3.2e-5 band and thrust 14 a zero-width one; s80's '3 distinct' was the spread of the aim SAMPLES. The alphabet at csangle 34325 lands exactly [40820,40826,40834,40841] in it, so the C-stick is worth ~8x more usable configurations at ZERO frame cost (csangle is position-independent during the walk-in -> one measured stream serves a whole fan, and the fleet schedule already carries a per-frame csangle column). (3) **The speedF-17 prune is a `fast_schedule` assumption (ROLL_NSPEED 26), not physics** -- a sub-cap walk still rolls at clamp(1.5*speedF+0.5,5,26); dropping the prune is 3.0x the candidates (43610 vs 14529) spanning **4146 distinct nspeed schedules, each its own locus and band**. That is the biggest untouched lever and s81's named NEXT step (generalize `fast_schedule`/`roll_entry` off the cap, then GATE it with `roll_fidelity.walk_then_roll` at a sub-cap entry speed -- the s80 gate only ever ran at nspeed 26), then the camera axis, then two-segment holds (built, `iter_fan2`, same near-miss yield per candidate). Also made qualification ~70x cheaper (`entry_gradient` builds the analytic ctx with a small cache instead of simulating one per Newton iteration: 269 s -> 4 s for 243 configurations, 0-ULP identical and gated). WHY A LOCAL DESCENT HAS NO GRADIENT (both gated): a plan's LAST delivered frame is only BUFFERED (`INPUT_DELAY`), so 12 held frames == 11 held + a DIFFERENT aim to the bit; once the aim acts, a one-frame turn at the alphabet's ~12 BAM local spacing drops Link off the cap and writes lean; and perturbing stick BYTES near a saturated aim is flat too (the octagon clamp maps them all to one decoded angle -- always perturb the alphabet the physics reads). Gates `tests/test_entry_fan.py` (11 fast + 1 slow, 18 s). KB: NEW `knowledge/strategy/clip-lottery-draws.md` (what one draw is, which prunes are physics), s80's claims MIGRATED to `knowledge/history/entry-search-s80-superseded.md`.** **s82: THE MOMENTUM AXIS IS GENERALIZED + GATED BIT-EXACT AND THEN MEASURED DEAD -- the s81 'biggest untouched lever' (drop the speedF-17 cap: 3x candidates, 4146 nspeed loci) buys ZERO.** GENERALIZATION (kept, current truth): entry_search.roll_nspeed = _roll_init's clamp read off LandState's constants (ROLL_NSPEED DERIVED at WALK_CAP, not written down), threaded through fast_schedule/roll_entry/build_fast/configuration_band/entry_gradient/qualify + the BandTable key + the fan key (walk_fan/iter_fan cap=None emit a 4-tuple carrying the endpoint's own speedF -- two candidates on one point at different speeds are different draws); turnaround.extract_schedule_at(nspeed=) lets the SIMULATED reference run sub-cap. GATE at 5 momenta (5.06/8.31/14.61/22.67/26, real from-rest walk + A-press in the walled coupled engine): the clamp off the WALK ENDPOINT's speedF IS the roll's momentum bit-for-bit (the entry frame dispatches after MOVE and it is STILL the endpoint's speed _roll_init reads -- measured); roll_entry(walk,facing,nspeed) is the entry position 0-ULP (cap-assuming is >20u out at nspeed 5); the reseed's NINE baked tables are identical to the real roll at every thrust; analytic fast_schedule(nspeed=) == simulated; and the cap-assuming schedule differs in EXACTLY dx/dz. THE PRICE = ZERO: sweeping nspeed 17..26 at every reachable aim x thrust, 2 of 181 productive (both at the cap); marched ALONG the whole locus (NEW entry_search.locus_scan -- re-project onto resid 0 at each station; a one-point band CANNOT declare a curve barren) the control at 26 lights 44/58 stations and every sub-cap momentum reads 0/~60; at nspeed 22.67 NOTHING is productive in the FULL 65536-facing circle (8 BAM); an uncapped fan reaches 42807 distinct momenta of which 4 are in the productive sliver; and END TO END at one resolution 43653 uncapped candidates find THE SAME 4 near-misses GAP FOR GAP as 14529 capped ones. PHYSICAL REASON (portable): a shorter roll is not the same clip started further back -- below ~17 momentum the roll never reaches the wall brace that pins `old`, and mid-range it reaches the brace but leaves Tetra out of Co range on the CUT frame so the push is exactly (0,0) and NO entry has leverage (grad 0.000 at 14.61). ENABLERS: NEW ShoveCtx.set_link_schedule (pyx) -- everything expensive in a ctx is the compiled WORLD (mesh/planes/_precompute_slices), the schedule is ~20 doubles a step, so build_fast 1.52ms -> re-schedule 0.16ms; entry_search.CtxPool keeps one ctx per (facing,thrust) and re-schedules per (lean,nspeed), gated 0-ULP vs a ctx BUILT at that configuration. stream_search's band strategy INVERTED: with the momentum in the key a band (14ms) costs 70x the group eval (0.2ms) it would save, so EVERY draw is evaluated (genuine is ground truth, needs no band) and bands are measured only for the near-zero tail (18 bands over a 43653-candidate pass); the s81 dead-configuration correction is KEPT (a tail draw at a dead configuration counts dead, not near-miss). Also fixed confirm_entry (reads iter_fan2's 7-tuple two-segment plans -- s81 built them and left it unpacking 4 -- and checks the roll's own nspeed, not 'is it at the cap'). GOTCHAS: roll_fidelity.walk_then_roll takes B_STEP (= thrust+2), NOT thrust -- passing the thrust makes all nine tables differ and looks like a fidelity failure; a negative sweep whose CONTROL also reads negative is a RESOLUTION bug (the first full-circle sweep at 64 BAM read 0 productive at the cap too -- its window is 32 BAM wide); a momentum dies TWO ways (locus with no dust vs 'no leverage at the seed') so a gate demanding stations>20 fails on the second; qualified() returns 6 configurations (81-aim alphabet x 3 thrusts), NOT s81's 48 (that is the direct 1-BAM facing sweep). Gates +5 test_entry_search.py / +3 test_entry_fan.py (45 fast, 32s). KB: clip-lottery-draws.md prune section rewritten + NEW 'declaring a configuration dead needs the WHOLE locus'; s81's lever claim MIGRATED to knowledge/history/entry-search-s81-momentum-lever.md. **NEXT = the CAMERA AXIS, the only lever left with a measured nonzero price (32-BAM productive facing window, frozen csangle 34325 reaches exactly 4 aims -> up to 8x usable configurations at zero frame cost; csangle is position-independent during the walk-in so one measured stream serves a whole fan; the fleet schedule already carries a per-frame csangle column). PRICE IT FIRST with locus_scan -- that is the lesson s82 paid for.**
 **s83: THE CAMERA AXIS IS DEAD, and the reason is a UNIT error worth carrying: the aim alphabet's atom is the CONSOLE SINE-TABLE CELL (16 BAM). `cM_ssin_s16` = `jmaSinTable[(u16)angle>>4]`, 4096 entries, NO interpolation (documented in knowledge/model/fp-faithfulness.md the whole time), and every term a roll facing reaches goes through it -- per-frame travel, cut-lunge rotation, Co pose chain, and roll_entry's own 26u step -- so two facings in one cell bake a BIT-IDENTICAL schedule at a BIT-IDENTICAL entry and are ONE draw. s81's '32-BAM productive window vs 4 reachable aims = 8x' is cells 2551 (40816..40831, thrust 15, the only real-width band 3.2e-5) + 2552 (40832..40847, width 0 = ULP tickets), and the frozen csangle's 4 aims (40820/40826 | 40834/40841) already reach BOTH -> a csangle slew adds EXACTLY ZERO configurations. Priced end-to-end BEFORE the diagnosis it read exactly 8.00x (6->48 near-misses, E[hits] 0.019->0.154) and printing IDENTITY showed all 48 were 3 candidates counted 16x at bit-identical resid. LESSON (now KB): a perfectly integral multiplier + measurements repeating to 4 figures = counting copies; count draws in the unit the PHYSICS quantizes to. Camera's only remaining reach = the WALK's direction cells (3612/4096 frozen, 3858 over all 16 offsets = ~1.07x CANDIDATES). SHIPPED: entry_search.{SIN_CELL_BAM,PRODUCTIVE_CELLS,aim_cell,aim_cells}; qualify runs one config per CELL carrying sibling aim bytes (confirm_entry delivers BYTES, and the entry FRAME is NOT cell-quantized -- raw s16 compare, so siblings can differ on whether the walk brakes); entry_fan.qualified refuses a pre-cell cache. qualified() 6->3 (1 usable + 2 ULP), honest reference read 3 near-misses / E[hits] 0.0096 = HALF what s81/s82 reported. +3 gates in tests/test_entry_search.py. THE REAL CONSTRAINT, measured: at the live config 91% of the fan piles at |resid| 0.1..0.5, only 17 below 5e-3 (3 at a live lean = exactly the pass's 3 near-misses), 34.5% carry a live lean; the closest family is n0=5 + ONE delivered frame whose byte alphabet is ALREADY exhaustive (one frame of stick moves the endpoint ~4e-3u per direction cell vs a 1.95e-4u band -- the fine knob CANNOT resolve into it), which is why every one-segment pass 14529..391446 candidates (27x) returns the SAME 3 near-misses gap-for-gap. What varies the sub-cell offset is the PREFIX -> near-misses scale with S1 FAMILIES: 32 families -> 3, 192 -> 13, best gap 8.14e-4 -> 2.79e-4 (272599 candidates, 220s, ~1.15 s/family). NEXT = the two-segment pass at s1_stride 4-8 + wider j1 + more bases (~50x families, ~3h, for E[hits] ~1), re-pricing near-misses-per-FAMILY as it goes; if that saturates the search is out of axes and the next move is structural (3-segment prefix, or re-solving the clip geometry) not bigger. GOTCHA: never measure a band per (facing,lean) eagerly -- 31k x 14ms; evaluate first, band only the tail.** **s84: THE ENTRY SEARCH HAS HITS.** Priced the two-segment axis first (as s83 ordered) and the pricing found the FAN'S OWN HELD-STICK ALPHABET was 5.75x redundant: a held stick reaches the walk only through `main_stick_decode`, so the 65536 byte pairs `stick_grid` enumerates are 11405 DRAWS (one class 1944 members; the classes surviving the walk-cap prune are the saturated/most-redundant ones). `entry_fan.stick_alphabet` collapses BOTH segments of iter_fan2 onto decoded (angle,msd), preferring an INTERIOR representative so dtm_make's 0->1/255->254 can't rewrite it; s83's own reference pass then reproduces GAP FOR GAP in 48 s vs 220 s (25x fewer writes). NOT wired into iter_fan -- that one is gated key AND VALUE vs the Python reference which enumerates bytes and lets the LAST duplicate win. Gate the candidate KEY SET, not the plans (two different sticks can land on one endpoint, so last-writer depends on enumeration order). THE WIDE PASS (`search2 4 2,4,6 1 6 4`, 2776 s): 5038 prefix families, 15.8M candidates, 47.4M evals -> 925 near-misses (925 distinct) and 118 genuine SCORINGS = **23 DISTINCT DRAWS at 20 entries**; `confirm_entry` (new tracked CLI `entry_fan confirm`, `confirm_hits`) replays **20 of 23 clean**. FRAME-MINIMAL CONFIRMED = 4 delivered frames, plan [1,180,184,2,180,183,1] aim [85,182] facing 40820 thrust 15 entry (-1531.49853515625,-781.9691162109375). THE AXIS DID NOT SATURATE: corrected reference 94 families -> 12 draws (s83's '192 -> 13' was the ASKED count; alphabet is 57 draws and 45% of junctions never form), vs 5038 -> 925 = 53.6x families for 77x draws, BETTER than linear -- first axis since s80 to pay. THREE COUNTING FIXES: near-misses dedupe on the DRAW (draw_key/dedupe_near, s83's 13 is 12); HITS need it far more (hit_draws: 118 scorings are 23 draws, ONE entry reached by 95 prefixes); `lottery` sums each draw's OWN band not count x lean-0 mean width (had overstated E[hits] 27%). MEMORY not time is the new ceiling -> `stream_search(dedup_scope='family')` held 15.8M candidates at 211 MB flat (fan streams family-major; draw dedup keeps reported numbers identical). GOTCHA: NEVER read the TAIL marginal near/family as saturation -- the stick grid is x-major so a sweep crosses the productive band ONCE (this pass: 0.00 for 300 families, peak 0.86, ended 0.13); the honest test is two whole-circle alphabets compared on draws/family. The 3 unconfirmed draws all read procs [24,24,6,6,6] -- proc 24 = MOVE_TURN, the prefix left Link mid-turn so the A-press TURNED instead of rolling -> NEXT = prune the fan on the endpoint's PROC (`c.state` is on the core beside the speedF prune), then re-run wider (j1 past 6, more bases, S1 stride 2). Offline only; the DTM CONSOLE confirm of these entries is untouched and is the real remaining risk. entry_fan.py now 819 lines (split candidate). **s85: THE CONFIRM RATE IS 100% AND THE YIELD TRIPLED -- 49 DISTINCT GENUINE ENTRIES, ALL 49 CONFIRMED BY A REAL A-PRESS AND ALL 49 DTM-DELIVERABLE (s84: 23 draws / 20 confirmed).** THE PROC PRUNE (the s84 next step) is in: an endpoint is a PROMISE that Link rolls from it, and the fan checked only the follow bar + walk cap; checkNextActionFromButton also needs a proc the ATTACK roll dispatches from = NEW canonical `tww_sim/land/constants.ROLL_FROM` (MOVE, ATN_MOVE) read by BOTH state.py's dispatch and `entry_fan._is_rollable`. The endpoint's own `state` IS the A frame's dispatch proc (aim delivered on the endpoint frame, acted the next) so NO lookahead needed. Drops ~7% of endpoints, saves NO fleet time (frames already stepped), IS exactly s84's 3 failures. Gated vs a real A-press BOTH ways + cross-engine (wired Python proc vs native core). OFF in iter_fan (its key-AND-value equality with walk_fan is a contract). NEW KB page knowledge/strategy/search-prune-the-dispatch.md. THE PASS `search2 2 1,2 1 6 2` (S1 stride 2, j1 (1,2), 2 bases): 8069 families, 39.3M candidates, 5086 s -> 2007 near draws, E[hits] 4.638, 49 genuine draws of 259 scorings, 3 best gaps exact 0.000e+00. SCOPED OFF s84's HIT SHAPE not the open axes (17 of its 20 hits at j1=2, all 4-7 frames; longer j1/more bases buy LONGER plans on a 5x-less-productive prefix) -- and the previously-unswept j1=1 returned 33 of the 49, MORE than j1=2's 16, while being shorter. **THE AXIS IS NOT SATURATING: a stride-4 pass would have found 8 of the 49 (stride 8 -> 1, stride 16 -> 0)**, read out of THIS pass via the new `entry_score.near_families`/`subgrid_rate` (a fine alphabet CONTAINS every coarser one, so the two-alphabet saturation test costs ONE pass, not two). Per family 0.184 -> 0.2487. **4 DELIVERED FRAMES IS NOW A FLOOR not a best-of** -- the 2- and 3-frame shapes were swept and returned nothing; two entries at 4 (`[0,200,144,1,195,164,3]` NEW + s84's, reproduced); the one 4-frame shape unswept anywhere is n0=2,j1=1,j2=1. GOTCHAS: the tail marginal lied in BOTH directions (0.50 -> 0.20 -> ended at 1.10, i.e. INSIDE a productive band -- stopping on the dip loses most of the yield); the live progress near/family counted SCORINGS not draws and read 2.3x high (FIXED, trace now deduped+walkable, gated); realized-family fraction is a function of j1 (77% at short prefixes vs s84's 34%) so it does NOT carry between scopings -- the first s85 scoping projected 5.7 h and was re-scoped at 4 min. ALSO: `survives_delivery`/`delivered` check a plan's bytes vs dtm_make's extreme clamp ON THE DECODE (held sticks are interior by design, AIMS only by luck) and confirm_hits carries `deliverable`; `BandTable.save` was NON-ATOMIC (a concurrent pass read a torn 4 MB json and died; killing a pass mid-save would have poisoned it) -> atomic + self-healing, gated. entry_fan.py SPLIT 880 -> 547 + entry_score.py 471 (re-export gated on identity). Suite 846 pass / 1 skip / 8 xfail. **NEXT = THE OUT-OF-BAND DTM CONSOLE CONFIRM** -- every configuration axis is closed and there are 49 unredeemed entries; what nothing has tested is the COMPOSITE (the wall-less courtyard FreeRun hands over an entry, the walled ShoveCtx decides `genuine`, and those two halves have never been on console end to end). **s86: THE COMPOSITE IS ON CONSOLE AND IT SPLIT IN TWO -- THE HANDOVER IS PERFECT, THE CLIP DID NOT HAPPEN, AND THE REASON RETIRES THE VERDICT COLUMN.** (1) THE ENTRY CONFIRM PASSED FIRST DELIVERY: the frame-minimal deliverable hit of the 49 (plan [0,200,144,1,195,164,3], aim [85,182]) appended to the s78 console log as one 86-frame movie, 9 truncate-and-read samples (n=78 the CONTROL, already-measured, reproduced 0-ULP -> licensed the rest), ALL 0-ULP on Link x/z/proc/facing/travel/speedF/**m351C/nspeed** (the two a ShoveCtx is KEYED on; deliver.read_link now reads them, plus shape_z) AND on Tetra x/z, who stays stt 3 + BIT-FROZEN every frame. LOCKED fixtures/courtyard_entry_s86_console.json + tests/test_entry_console.py (24). (2) THE CLIP DID NOT: extending the same log to the thrust (UP+B on plan frame 100, cut dispatches 101) the console's pre-cut point is BIT-IDENTICAL to ShoveCtx's own `old` (-1692.3143310547,-955.0763549805) and the cut fires on the predicted frame at the predicted facing/phase -- then Link travels 0.16 u where the prediction has 49.97 u through the gap. LOCKED fixtures/courtyard_clip_s86_console.json + tests/test_clip_console.py (8 + 7 xfail(strict) contiguous suffix). (3) THE PER-FRAME DIFF NAMED TETRA, NOT LINK: Link 0-ULP through plan 89, **Tetra off 6.8 u at 91 while Link is still exact**. Her console z pins to the BIT at -940.25561523 across five frames = back-wall plane -990.255615 + her R 50 = a WallCorrect brace (s60's 'a repeated-to-the-bit position is a wall pin', applied to the OTHER actor). The rollstab CcCoupledStepper(walls_tetra=) reproduces that pin exactly; **the courtyard from_f0 carries her as a bare XZ plow point with NO BG collision and drives her 53 u THROUGH the wall** by the cut frame. (4) THE PRICE OF HER IS ONE ULP: the entry search priced the precision it needs in the variable it SWEEPS (~1e-4 u of entry) and never priced the other terms of the same residual; **one f32 step of her x (1.221e-4 u) flips `genuine` True->False**, so the razor is thinner than her own storage grid, and the best model of her cut-frame position is 0.15 u (~1200 ULP) off the console. => `genuine` is UNDECIDABLE at current fidelity for ALL 49, not wrong for this one. KB: new knowledge/strategy/razor-prices-every-term.md + hub row; mechanics/tetra-follow.md gains the console brace. (5) FREE WINS: the whole composite now runs in ONE engine (wired delay-1 FreeRun + `link._walls = TA.WALLS`; `_walls` is a plain attribute on the Python path), which removes the schedule-step-vs-plan-frame mapping -- and attaching those walls leaves EVERY console-confirmed frame byte-identical, i.e. the herd provably never touches a wall (objective rule 4, asserted since s60, now MEASURED). Delivered composite is clean of the dtm_make extreme clamp on every byte. **NEXT = TETRA THROUGH THE CLIP ROLL: (a) wire the npc_zl1 CrrPos pass into the courtyard tracking (the xfail frontier is exactly that; strictly additive, no herd gate can move), (b) close the residual 0.15 u -- her z is within 0.03 u and braced, so the error is the SLIDE along the wall = the push magnitude during the roll (courtyard full-depth law vs the rollstab 50/50 the sweep uses); the console rows are locked so this costs no live runs. THEN the 49 get RE-SCORED, not re-searched. DO NOT widen the fan.** GOTCHAS: ShoveCtx indexes by SCHEDULE STEP at INPUT_DELAY 2 (step 0 = the roll's SECOND frame) while the DTM is delay-1 by plan frame, so the UP+B goes at entry_i + b_step (NOT +1+; cost a live run) -- cross-check in the delay-1 engine's proc stream first; a sensitivity row that shows no change may not have moved the value (1e-5 rounds to the same f32 -- perturb by one ULP off the bits); 'cut fired but did not lunge' is ALSO what a blocked lunge looks like (the b sweep settles it: the delivered frame is the LAST that cuts out of the roll at all); each delivery is ~30 s (relaunch-dominated), so put the DECISIVE sample first. Suite 878 pass / 15 xfail.


## s93 -- THE SECOND LOBE IS NOT REACHABLE AT THE FRAME FLOOR (the axis, priced)

s92 recovered the second facing lobe and priced the exit-angle axis at +160 BAM; s93 measured that price in FRAMES and it is not available. The completed pass (`search2 4 2 1 2 2 cells=lobe2 frames=4`, 779130 candidates / 7.01 M evals / 9 configurations / 494 s) returned **0 genuine, 0 near, 0 dead-tail**. Three separate measurements, none of them density: closest approach 0.354 (cell 2561) rising monotonically to 1.873 (2581) = 71-375x outside `BAND_PROBE`; **18.4x more candidates moved that by BIT-IDENTICAL zero at the SAME argmin entry** while the same density sharpened cell 2553 37x (to 4.45e-05); cells 2570+ never change sign over the cloud. ROOT CAUSE: `curve_seeds` sweeps `reach_radius` = WALK_CAP*frames + ROLL_NSPEED, a 94 u BOX, and the real 4-frame cloud is 447581 endpoints in 58.6 x 63.8 u (~11% of it) -- an existence result inside a bound read as availability under the budget (razor rule 13, the MIRROR of s92's rule 12).

NEW `harness/tetrapush/entry_reach.py` measures the cloud instead of bounding it (stdlib convex hull; ONE facing-independent hull serves every configuration because `roll_entry` is a pure translation in the walk position). **Asked which of the 40 productive configurations have a reachable station at 4 frames it answers cells 2551/2552 ONLY -- independently, from walk endpoints alone, exactly where the whole 55-candidate delivered population sits.** The test is ASYMMETRIC by design: a hull is a SUPERSET of the cloud, so OUTSIDE proves unreachable and INSIDE proves nothing -- never prune on the positive side. Same caution on the sign census: `resid`'s grad ~1.2/u over a ~60 u cloud spans +-70, so 'both signs present' means a boundary is in the sampled set, NOT that a landable zero is.

OPEN: **cell 2553 (+9 BAM) is the whole axis at the floor and it is a LEAN problem, not a candidate problem** -- its own pass puts 180 candidates inside the probe and converts none, because every one lands at a lean whose band has no usable width (the band is jagged in m351C; the qualification runs at lean 0). That is exactly the delivered cell 2552's situation at its own lean 64761 (width 0.0, 20 genuine) and that one was won by POPULATION, so a one-f32 target is odds and not a wall. Next: `_notes/s93_lean_band.py` at 2553 both thrusts, rank leans by CANDIDATE MASS (1040 distinct entry leans; 65281 carries 202 k, then 6 / 65151 / 65021 / 65411, delivered 64761 carries 95 k), then aim `search2` at the (lean, cell) pair.

GOTCHAS: `stream_search` DISCARDS everything past `BAND_PROBE`, so a pass can never tell you whether it missed by a ULP or by twenty units -- run `_notes/s93_reach_probe.py` (60 s) before buying candidates. `search2` now takes `cells=` (lobe2 / right / explicit / ranges, resolved out of the window fixture) and `frames=` (the plan-length cap; `j1`/`j2max`/`nbase` bound the fan's SHAPE, not its plan LENGTH, so an uncapped bounded pass spends most of its evaluation on plans Dereck refuses). `right` runs to the AIM ALPHABET's edge, not the scan's -- s92's scan stopped at 2575 while its own qualification reached 2581. Session 92's work was UNCOMMITTED at session start (committed as aa40606; three of its comment blocks needed tightening for the comment-length hook). PERF: run ONE heavy job at a time -- the fan is Python-per-core-per-frame bound (~44 k core-frames/s) and OpenMP busy-waits under oversubscription; three concurrent jobs starved a full suite past 90 min.
## s94 -- CELL 2553 WAS NEVER A LEAN PROBLEM: THE BAND WAS A ONE-SEED NEGATIVE

`configuration_band` Newtons the entry onto the residual zero FROM A SEED, and `BandTable` handed it ONE seed for every key -- the single global `ref_entry`. That is the s90 (`escalate`/`locus_scan`) and s92 (`curve`/`curve_scan`) single-station defect **one level down, in the RANKING instead of the scope**, and it survived both fixes untouched. **The tell needs no argument: ask that table for the band at the configuration of the clip DELIVERED TO CONSOLE AND CLIPPED (facing 40841, thrust 15, lean 64761) and it answers `no genuine on the residual zero`.** A ranking whose input calls the known-good input dead is broken before its other verdicts are worth reading. Cost, measured three ways: cell 2553/thrust 15 goes **0 -> 20 of its 24 heaviest fan leans usable**; **10360 of 15968 cached band rows were one-seed negatives** (the unaudited `_generated/s81/bands.json` four handoffs kept flagging -- audited, and non-productive rows without an `escalated` flag are now DROPPED on load); and s93's own pass over IDENTICAL candidates reports **34 near-misses at E[hits] 0.079** instead of "180 dead-tail, 0 near, 0.000". A dead band is SILENT by construction (`genuine` comes from the sweep, so no clip is ever suppressed) -- it only kills the near-miss population, which is the only thing `lottery` is computed from. Razor rule **14**; KB `strategy/clip-band-per-lean.md`; overturned share migrated to `history/band-dead-share-from-one-seed.md`.

The ladder (`BandTable._measure`): global ref -> the configuration's OWN qualified station -> `locus_scan`/`curve_scan` seeded from it. No cheap seed dominates (over 24 leans the ref wins 19/24 at cell 2551 and 0/24 at 2553; the qual station 17 and 11). **Every seed is FIXED per key on purpose** -- a first cut also carried the last station that had paid for the same (facing, thrust), which is free and converts keys but makes the answer depend on the ORDER keys were requested, so two passes disagree and any single-key gate is flaky. Rungs 1-2 ~30 ms, 3-4 ~2-6 s, and only a pass's near-zero TAIL owes a band. NEW `harness/tetrapush/entry_lean.py` (census/bands_at/rank/parse_lean_spec/select_by_lean) + `search2 leans=/thrusts=`; LOCKED `fixtures/courtyard_lean_bands_s94.json` (2553/t15 = 20 usable, 2551/t15 15, 2552/t14 4, 2552/t15 2, **2553/t14 = 0** -- thrust 14 is the genuinely dead one, and the s93 handoff pointed at it). **Width RANKS and must never filter: the delivered clip converted at width 0.0** (20 genuine samples at one f32).

**AND THE FAMILY AXIS IS NOW EXHAUSTED AT THE FRAME FLOOR FOR 2553 (~E[hits] 0.2 per pass).** A family is a budget unit only inside one plan SHAPE: widening `j1=2,nbase=2` to `j1=1,2,nbase=3` bought 1012 -> 10036 families (9.9x) for 1.9x the near-misses, because `j1=2` pays 0.032/family, `(n0 1, j1 1)` 0.0025 and `(0,1,*)`/`(2,1,*)` (5542 families) exactly zero (KB `strategy/clip-search-budget.md`). The best pass is stride-1 `j1=2`: 3213312 candidates / 4162 families / 866 s -> 83 near, E[hits] 0.194, 0 genuine, and its closest approach **3.287248e-04 is BIT-IDENTICAL to the stride-2 pass's at the SAME entry** (12.6x outside the 2.6066e-05 band). Family count grows at ~45% of alphabet growth (a finer alphabet mostly adds decode classes that do not hold the speedF cap). **NEXT LEVER = THE CAMERA:** at the frozen csangle 34325 exactly ONE aim reaches cell 2553 (60 aims across `AIM_WINDOW`); s83 priced a slew at zero against a 2-CELL window and the window is now 22 cells / 40 configurations -- rule 12's corollary, a closure expires when its premise moves. GOTCHA: `subgrid_rate` undercounts a coarse sub-pass 4x at these strides (its own attribution caveat) -- compare two real passes.

## s95 -- THE CAMERA IS A FREE INPUT CHANNEL INSIDE THE ENTRY PLAN (the walk side, not the aim side)

**PRICE: ZERO FRAMES, read off the locked console log.** The entry plan runs AFTER the escape atom (`fixtures/courtyard_entry_s86_console.json` rows 78..) and every one of those frames carries `substickX == 128` -- the C-stick is idle there, so a slew cannot cost a frame. Bounded instead by REACH: a held byte moves csangle **-716..+714 BAM by the 4th entry frame**, 1-frame delay, fine ladder (byte 96/160 = -5/+4). **s83's "camera worth zero" was right on the AIM side and wrong on the WALK side**: it counted 3612 of 4096 direction cells over the whole stick grid at `msd_min=0`, but the fan keeps only speedF-cap endpoints, so its alphabet is the cap-magnitude one -- **2280 angles reaching 1736 of 4096 cells (42.4%)** -- and one sine cell of camera moves **888 of those 1736** onto directions the frozen camera cannot command. Razor rule **15**: price a lever against the subset the SEARCH can use, not the one the hardware has; and an input channel nothing is using over your frames is a free axis.

MEASURED at cell 2553: **64 cameras / 643 s -> 71 DISTINCT near-miss draws, E[hits] 0.19, 0 genuine**, against s94's exhausted 3.2 M-candidate frozen pass at E[hits] 0.194 / 866 s -- same rate, **96% of the draws standing where the frozen fan cannot reach**, and **no saturation** (each camera is a fresh 10 s draw). Closest approach on one bounded fan: 1.49e-3 frozen -> 2.9e-5 at +200 BAM. Budget rule: **many cheap cameras, not deeper ones** -- the same camera at a 6.5x wider shape buys 4.3x the draws for 12x the clock (~3x worse per second).

TOOLING: NEW `harness/tetrapush/entry_camera.py` (`cam_trail` measured on the WIRED camera and injected per frame, `camera_alphabet` 254 bytes -> **82 distinct trails**, `segmented_alphabet` for a C-stick that switches mid-plan, `aim_frame`/`aim_at`, `walk_cells`/`cell_census`, `fan_cam`, `probe`, `search`, `hull_shift`) + one hook in `entry_fan.iter_fan2(hold=, cs_trail=)`/`_fan_chunk(cs_seq=)` and `confirm_entry(hit['substickX'])`. Gate `tests/test_entry_camera.py` (13 + 1 slow); KB `strategy/clip-camera-axis.md`.

GOTCHAS. **(1) Frame k decodes against `trail[k]`** -- a CONSTANT injection cannot see the alignment, which is why it went untested for 14 sessions; gate a moving camera against the wired `LandCamera`. **(2) The camera is still RAMPING when the roll's facing latches**: facing = `decoded_aim + 0x8000 + trail[frames+1]` (measured by firing the roll and reading it back), so a hard slew moves the aim alphabet -- at subx 249 the bytes reaching cell 2551 frozen roll into cell **2640** -- and a camera draw only counts where the cell stays aimable (**64 of 82** for 2553). **(3) DEDUPE ACROSS CAMERAS**: neighbours command ~94% of the same directions, so 243 reported near-misses are 71 draws; pooled E[hits] reads 3.4x high. `draw_key` still keys the raw entry lean, so 80 rows are 71 physically distinct. **(4) The camera does NOT grow the cloud** -- hull area +0.0% across the whole slew, 0 of 9 second-lobe stations enter the union hull, so s93's second-lobe negative survives; do not reopen it on camera grounds. **(5)** The fan holds ONE input across its base frames, so a segmented C-stick may not switch inside `base_frames` (`fan_cam` raises). **(6)** `dtm_make.cal` clamps the C-stick 255->254 / 0->1 exactly as the main stick, so the alphabet is built on delivered bytes.

**s95 SEGMENTED CAMERAS + THE DEDUP THAT MAKES THE AXIS 2x CHEAPER.** The C-stick may CHANGE mid-plan, so the 82 held ramps are not the alphabet: `segmented_alphabet(2553, frames=4, step=32)` = 137 cameras -> **105 distinct draws, E[hits] 0.273, 1365 s** (pooled would read 1.434). But those 137 carry only **49 distinct WALK trails** -- a camera that changes only AFTER the walk re-aims the same cloud -- and 41 of the 49 groups report a BIT-IDENTICAL draw set, so one representative each buys 83 of the draws in 530 s (**0.157 draws/s vs 0.077**). `dedupe_cameras` (now inside `search`) keys on the trail prefix the fan actually STEPS (`fan_steps` = max(base_frames)+max(j1)+j2max+1), NOT the plan's frame cap -- the other 8 groups genuinely differ because the fan records the endpoint after j+1 steps. Budget by DRAWS: ~0.157/s means E[hits] ~1 is ~1.5 h. GOTCHA: `_generated/s95/search_2553.json` was overwritten by a later single-camera run (the output tag now includes the byte spec); the 64-camera numbers are in `_notes/s95_search_2553_all.log`.


## s96 -- THE CAMERA AXIS IS A TWO-BYTE CHANNEL (supply = bytes^2), AND THE APPROACH IS NOW INSIDE ONE BAND WIDTH

**THE SUPPLY LAW, measured.** The 4-frame walk trail is a function of the C-stick bytes on entry frames **0 and 1 ONLY** -- exact over all 4096 four-byte paths at stride 32, where 3584 disagree with their 1-byte prefix (`entry_camera.walk_channel`, `WALK_CHANNEL = 2`). So a switch point past the channel adds **ZERO** walk clouds: it multiplies C-stick paths 8x and `fan_steps` trails 7.7x and leaves the distinct walk clouds bit-identical (64 -> 64 at stride 32, 196 -> 196 at stride 16). Supply is `(deliverable bytes)^2`: **64 / 196 / 709 / 2394 / 5300** walk clouds at byte stride 32 / 16 / 8 / 4 / 2. This is also the mechanism behind s95's unexplained "41 of 49 groups report a bit-identical draw set" -- those cameras differ only in bytes the walk cannot see.

**AIMABILITY IS A FREE, INDEPENDENT KNOB.** The aim frame (`trail[frames+1]`) sits past the walk channel, so a TAIL byte moves the aim -- and whether the cell is aimable -- while leaving the walk cloud bit-identical. So s95's "cell 2553 aimable at only 64 of 82 cameras" bounded the ENUMERATION (held bytes, where one value serves both jobs), not the axis: pick the walk pair first, then search a tail, and **0 of 196 clouds are dropped** (`walk_cameras`, and the `walk:STEP` CLI byte spec -- USE THIS for a pass). At stride 16 that is **196 clouds from 196 passes** against s95's 157 from 440.

**THE PASS: 196 cameras / 1462 s -> 127 DISTINCT draws (816 reported), E[hits] 0.329, 0 genuine -- and closest approach `8.829e-06` against a band `2.8125e-05` wide, i.e. 0.31 BAND WIDTHS**, vs 3.287e-04 (s94 exhausted frozen) and 1.073e-04 (s95 cameras) -- 37x and 12x closer. **BUT THAT RECORD IS ONE DRAW, NOT A TREND, and I initially wrote it up as convergence before checking.** It is a single candidate (walk `(-1511.5211181640625, -760.56689453125)`, lean 65281, nsp 26, camera `[16,32,128]`, plan `[0,208,192,2,192,88,2]`) and it is INVARIANT: the s94 paying shape at that camera (3.20M cand, 881 s, 41x the density) moved it by BIT-IDENTICAL ZERO, and 35 neighbouring walk clouds all report the same gap bit for bit (12 of the 35 reach that endpoint). Closing it needs the residual to fall 7.1% ~ 2.9e-04 u of entry movement, finer than the endpoint lattice stride-1 density produces. So the axis is still a LOTTERY governed by E[hits]/s. **RATES, all on cell 2553 / thrust 15: local camera NEIGHBOURHOOD (+-8 bytes, stride 2, 35 clouds) 0.127 draws/s and 0.886 draws/camera; whole alphabet at stride 16 0.087 and 0.648; camera x paying shape 0.045.** So spend on local neighbourhoods around productive clouds (1.46x), NOT a finer whole-alphabet sweep -- draws/camera already fell from 1.11 (coarse held) to 0.648 (stride 16), so the supply table bounds TICKETS not draws. At 0.0026 E[hits]/draw, E[hits] ~1 is ~385 draws ~ 50 min at the neighbourhood rate. [**s97: THIS WHOLE RATE RANKING IS OVERTURNED** -- priced in NEW draws it reverses and the budget is ~1.9 h; see the s97 section.]

**THE DEDUP THE s95 HANDOFF PROMISED WAS NEVER HAPPENING.** `dedupe_cameras` keys on `fan_steps` (6 frames at the bounded shape) and returns **137 of 137, 440 of 440** -- zero collapse. The "2x cheaper / 0.157 draws/s" came from grouping on the plan's 4 frames, a DIFFERENT and LOSSY key (79% of the draws for 39% of the clock). Both are now `search(group_steps=)` and every pass records which key it ran under.

**THE SCOPE, PRICED BOTH WAYS.** Cell 2553's thrust-14 configuration = **3.8% of the draws / 4.5% of E[hits] for 24% of the clock** -> drop it (`thrusts=(15,)`). And a NEGATIVE worth keeping: adding cell **2551** buys **3.1x the draws for the same clock and is worth ZERO**, because 2551 is LEFT of the console-delivered cell **2552** and the objective is the exit angle as far RIGHT as possible. Right of 2552 there is only 2553, then measured-dead 2554-2559, then a second lobe no frame-floor plan reaches. A rate in the SEARCH's currency read 2.9x on a prize the OBJECTIVE refuses (razor rule 15's third corollary).

**TWO DELIVERY BUGS -- a camera hit could NOT have been cashed (both fixed, both inert at a frozen camera).** (1) `confirm_entry` did `int(hit['substickX'])`, which RAISES on a sequence camera; it now schedules the path frame-for-frame (byte k on replayed frame k, `cam_trail`'s alignment) and RETURNS the frames it replayed so a delivery authors the CONFIRMED input (`deliver.build_boot_movie` reads `substickX` per row). (2) The aim was stamped at the pass's frame CAP, not the candidate's own plan length (`plan_frames`) -- the facing latches against `trail[n+1]`, so a short-plan hit carried bytes delivering a facing **12 BAM off**. Both invisible frozen (constant trail) and invisible in the s95 numbers (all 540 of its near-misses came in at the cap). LESSON: when an axis makes an input non-constant, re-ask every consumer that indexes it by frame.

KB: NEW `strategy/clip-camera-supply.md`; razor rule 15 third corollary + its "64 of 82" corrected; s95's recipe MIGRATED to `history/entry-search-s95-segmented-cameras.md`. Gates `tests/test_entry_camera.py` (21 + 1 slow).

## s97 -- THE AXIS'S DRAWS ARE MOSTLY COPIES: PRICE A PASS AGAINST THE DRAWS ALREADY HELD (s96's ranking INVERTS)

**THE FOURTH LEVEL OF "COPIES AS DISCOVERIES", and the tooling was already honest at the three below it.** `dedupe_near` makes a pass's own count honest and `entry_camera.summarize` explicitly REFUSES to sum `expected_hits` across the cameras INSIDE one pass (it says why) -- and then s96 summed across PASSES. Priced against the population it was run after: the local camera neighbourhood's 31 draws are **6 NEW (0.0245 new/s)**, the camera x paying-shape "densify" pass s96 said to SKIP is **29 of 40 new (0.0329/s)**, and the whole alphabet's END rate is **0.031/s**. So **s96's 0.127 > 0.087 > 0.045 REVERSES** -- the recommended buy is last, the forbidden one first -- and the three collapse to within 35%. Robust to the obvious objection: drop the centre camera's rows entirely and the neighbourhood still reads 31 draws / 6 new, and only 1 of its 35 clouds was in the parent's camera list. **Different cameras reach the SAME entries** (neighbours command ~94% of the same walk directions).

**THE AXIS IS SATURATING and the curve was FREE** (accumulate the 196 cameras' draw sets over random orderings, `entry_ledger.accumulation`): **4.3 draws at the first camera -> 0.23 over the last quarter, an 18x decay** -- coupon-collector, i.e. sampling a population far smaller than the sample count. So the supply table (196/709/2394/5300 clouds) bounds **TICKETS** and says NOTHING about draws, and a completed sweep's AVERAGE rate is not repeatable (0.087/s ends at 0.031/s -- the END rate is what a next pass costs).

**BOTH FACTORS OF E[hits] ARE NOW MEASURED, WHICH CLOSES THE ARITHMETIC.** (1) `lottery`'s premise -- residuals locally UNIFORM across the window -- **HOLDS** on the population itself: observed/expected **1.00 to 1.18 from 3e-3 down to 1e-4** (`entry_ledger.uniformity`), so no crowding near zero to harvest. (2) Widths are nearly pinned: draws land at 2.61e-05/2.81e-05 and the widest band ANY lean carries at 2553 is 3.25e-05 = a **1.26x ceiling**. Therefore **E[hits] = 0.0026 x distinct draws EXACTLY**, a draw costs **~30 s whatever you buy**, and **E[hits] 1 = +225 draws ~ 1.9 h** (not s96's 50 min). Also: the 8.829e-06 record is ONE ORDER STATISTIC -- 127 uniform draws produce a best that deep ~a tenth of the time (the distributional form of s96's "a record is not a trend").

**THE FRAME LEVER IS ALREADY CLOSED BY THE OBJECTIVE, IN CODE -- don't re-open it.** `clip-exit-angle.md`'s frame table has cell 2553 reaching **2.3e-05 at <=5 frames against a 2.6e-05 band** (one extra frame would likely just convert it), and `entry_fan.capped` drops >floor plans citing Dereck's zero-frames constraint. 2553 IS the whole exit-angle prize at the floor, so the lottery is the route and ~2 h is the price.

**THE PRIZE HAS NEVER BEEN PRICED PER CELL** (the open objective question for Dereck): 2553 is +9 BAM = **+0.088 deg**, and the WHOLE exit-angle axis is worth ~1 frame downstream. If linear in the 2.37 deg span that is ~**0.04 frames** -- six sessions on ~4% of a frame. It is FREE (0 frames) so it stays objective-positive however small, but the compute-to-prize ratio is now legible and the spend is his call.

**THE BUY FOUND WHAT ACTUALLY GOVERNS THE RATE: DISTANCE FROM THE CAMERAS ALREADY BOUGHT, AT PURCHASE TIME -- SPREAD, DON'T CLUSTER.** FIVE fresh cameras, identical paying shape and clock (3.18M cand, ~849 s each), EVERY one 40 draws and 0 genuine, and the NEW share spans 4x tracking only the BAM distance to the nearest camera already held: ~20 BAM -> 19% (the neighbourhood), 78 -> 25%, 84 -> 20%, 170 -> 48%, **266 -> 78%**, 312 -> 57%. **Spearman 0.886 over six passes** (strongly rank-ordered, NOT strictly monotone). **THE CONFOUND IS CLOSED and it is the LEDGER, not the frozen camera:** `[160,240,128]` at **+194** is further from centre than anything else bought and pays the LEAST (20%) because `[96,224,128]` had just been bought 84 BAM away -- reverse the purchase order and the yields swap. So **recompute the ranking after EVERY buy**. **A bounded pass's own `n_near` predicts NOTHING** (9/8/8/8/8 -> 10/31/19/23/8). Union **253 draws / E[hits] 0.651**, best gap unchanged 8.829e-06; buy aggregate 91 new in 4246 s = 0.0214/s (worst 0.0096, best 0.0356); **E[hits] 1 is +132 draws ~ 1.0 h**. And the emptiness is NOT a tension with the model: 253 draws at E[hits] 0.651 with 0 genuine is Poisson **P(0)=0.52**, the most likely single outcome. NB the 0.0329 I ranked the shape by was itself optimistic: densify's 29-of-40 was that shape's FIRST pass on this scope, so it measured DENSITY against bounded passes, not camera vs camera -- **a shape's first pass over-reports the shape exactly as a ledger's first pass over-reports the axis.**

**ALSO:** `lottery` must be handed DRAWS, not reported near-misses (`from_extract` gives all 816 rows of the walk16 pass; pricing those without `dedupe_near` reads 6.4x high -- `Ledger` does it internally). A ledger's OPENING pass is 100% new by construction, so its rate is not one anything can be budgeted at -- `price()` reports a marginal rate over passes that faced a non-empty ledger, `None` otherwise (same arithmetic shape as the s95 handoff's 0.157/s).

NEW tracked `harness/tetrapush/entry_ledger.py` (`Ledger`/`novel`/`accumulation`/`uniformity`/`extract`, CLI `price`/`saturate`/`uniform`) + LOCKED `fixtures/courtyard_draw_ledger_s97.json` (1025 rows -- a pass writes to the GITIGNORED `_generated/`, so a finding argued off one is not re-runnable from a clone). Gates `tests/test_entry_ledger.py` (9). KB: NEW `strategy/clip-draw-ledger.md`; s96's ranking MIGRATED to `history/camera-neighbourhood-enrichment.md`; `clip-search-budget.md` split so "a record is not a trend" keeps its own anchor. The buy is `_notes/s97_ledger_buy.py` (paying shape, fresh cameras, ledger-priced, incremental JSON).

## Session 98 (2026-08-04) -- THE AXIS IS SETTLED: E[hits] COUNTS THE WRONG EVENT

Dereck authorized the grind (1 h, then 3+). The buy ran as ordered and is honest; what it found is that
the estimate it was bought against is not a count of clips.

- **THE BUY.** 14 cameras, paying shape, `entry_ledger.spread_cameras` re-ranked after every pick.
  11257 s, clock dead steady 763-859 s. **197 new draws, union 450, E[hits] 1.0971, 0 genuine.**
  Distance law held OUT OF SAMPLE across all 14: 520 BAM -> 85% new, 256 -> 65%, 128 -> 62%, 83 -> 35%,
  43 -> 5%. So s97's law extends past the 312 BAM its fit ended at.
- **THE POOL GAP.** `entry_camera.deliverable_bytes` walks `range(0, 256, step)` -> every strided
  alphabet stops at byte 240, so `[254,254]` (walk **+714**, the channel's positive extreme) had never
  been a candidate since s95. Its mirror `[1,1]` (-716) always was, because 0 clamps to 1. Bought at
  520 BAM out it paid **34 of 40**, this axis's best pass. Fixed via `SPREAD_EXTREMES`.
  GOTCHA: any alphabet built from `range(0,256,step)` here has the same missing endpoint.
- **THE RESULT.** The run printed `best gap 0.0000e+00` with every row `genuine 0`. `window_gap` is 0.0
  only INSIDE the band, so that draw is the event `lottery` prices every draw by -- the first in 450,
  arriving about when E[hits] 1.0971 predicts -- and it is **NOT genuine**, reproduced bit-for-bit
  (entry, resid 1.5499e-04 to the ULP, engine flag False).
- **THE MECHANISM.** `BandTable` may source a band via `curve_scan`, which marches ALONG the locus to a
  station that HAS dust (a correct s94 fix for false negatives -- without it cell 2553 has no priced
  population at all). Sampled over the union: **100/100 draws priced by the `curve` rung at a station
  14.5-26.4 u away (median 20.9); 0/100 have any dust at their OWN station**, inside a transverse window
  ~35x the band width. So `P(clip) = P(own station has dust) x P(resid in band)` and only the second was
  ever computed, the first taken as 1 and measured at 0/100 (95% upper bound ~3%).
- **THE PRICE.** 450 draws are worth **<= ~0.03 expected clips, not 1.10**. E[hits] 1 is **~90 h**, not
  ~1. Six sessions of emptiness were never Poisson luck. FIFTH level of counting copies as discoveries,
  and the first where the count was honest and the EVENT was wrong.
- **GOTCHA -- do NOT check this with a naive grid.** My first sweep used a 40x40 u box at 0.25 u and
  read "0 genuine anywhere", which looked damning and proved nothing: the genuine set is a razor ~0.006 u
  across the locus. Use `configuration_band` (sweeps across the locus at the right scale).
- Gates NEW `tests/test_band_transfer.py` (2), `tests/test_entry_ledger.py` 9->13. KB NEW
  `strategy/clip-band-transfer.md`, `strategy/clip-camera-spread.md`; overturned reading MIGRATED to
  `history/ehits-priced-as-clips.md`. Commit 4f39e07.
- **NEXT:** Dereck's call, recommendation STOP. If continued, the question is no longer "buy more draws"
  but "is there any reachable entry whose OWN station admits dust" -- a search over STATIONS, tooling
  not built (`configuration_band` at the candidate's own entry is the predicate, ~30 ms).

## Session 99 (2026-08-04) -- THE BANDS WERE MEASURED OUTSIDE THE REACHABLE SET, AND THE TARGET IS AT THE THRUST s96 DROPPED

Dereck's call: **"run the station check, then stop"**, plus the disposition -- **tetrapush is a ONE-OFF
solver; the general-purpose Tetra-free seam solver, integrated into Dolphin python scripting, is the line
that continues** ([[seam-solver-generalization]]).

- **THE RESULT, IN ONE FACT.** Against the 4-frame reachable hull (`entry_reach`, s93): **450 of 450
  draws INSIDE** it, every one within **2.63 u** of its boundary, and **20 of 20 acceptance bands
  OUTSIDE** it by **10.196-19.400 u** (median 12.1). So s98's 14.5-26.4 u draw-to-station transfer
  distance and this hull crossing are ONE fact from two sides. One frame up, 13/20 come strictly inside
  (19/20 at `reachable`'s 1 u margin). No draw in six sessions could have clipped at any width.
- **THE TOOL, TRACKED:** `entry_reach.entry_hull` / `hull_field` / `hull_seeds` / `hull_scan` /
  `LEVERAGE_MIN` = `curve_scan` with `reach_radius`'s 94 u box replaced by the MEASURED hull + a
  containment test on every marched station (new additive `entry_search.locus_scan(inside=)`, inert by
  default + gated). **The gap was named in `reachable_quals`' own docstring since s93 and never built.**
- **GOTCHA -- IT CANNOT SEED LIKE `curve_seeds`.** Only **~7% of the reachable hull has leverage**
  (elsewhere the plowed Tetra is out of Co range at the cut, so resid sits on a FLAT PLATEAU). A resid
  sign change between two plateaus is a **JUMP**, and Newton returns `no leverage` from it -- so
  box-style seeding reads a cell barren for a reason unrelated to dust. Seed off the LEVERAGE field.
  The 7% holds at the DELIVERED configuration too, which is what proves it is the corner's shape.
- **THE THREE-WAY SWEEP** (`sep` 6.0): control cell 2552 f4 thr15 = **518 live walkable stations over
  60/60 leans**, landing **0.044 u** from the console-delivered entry; target cell **2553 f4 thr15 = 0**
  over **1040/1040** leans (12823 in-hull stations); counterfactual cell 2553 **f5 = 243** over 44/60
  leans, landing 0.24 u from the station s94 measured that cell's band at. Both directions pinned against
  something measured independently of the scan ([[search-space-contains-human]]).
- **AND THEN THRUST 14 OVERTURNED THE CLOSURE I HAD ALREADY WRITTEN UP.** Cell 2553 at **thrust 14**,
  same 4-frame budget: **LIVE walkable stations at ~7% of its in-hull locus, with real bands (3.05e-05,
  the same order as the delivered clip's own)**. **The thrust is NOT a frame cost** -- it only picks which
  roll frame the B edge dispatches the cut on (`cut_step` = thrust+2 = 15/16/17) and
  `entry_fan.plan_frames` counts walk holds only -- so it is objective-legal at the floor and firing one
  roll frame earlier is if anything frame-POSITIVE. **s96 dropped thrust 14 on a CLOCK argument** ("3.8%
  of the draws / 4.5% of E[hits] for 24% of the clock" -> `thrusts=(15,)`), and every pass from there on
  bought the barren thrust. **GOTCHA -- why it looked barren: every s94 thrust-14 band read width 0.0,
  which is NOT "no dust" but genuine points on a residual PLATEAU** (many genuine samples sharing one
  residual to the bit, `grad ~ 0`). `lottery` prices a zero-width band at probability ZERO, so the
  configuration was scored worthless by the one quantity that cannot see it. Dust there is POSITIONAL and
  a resid-ranked search is blind to it.
- **SO THE AXIS IS A SPEND CALL ON A REAL TARGET, NOT IMPOSSIBILITY.** Recommendation still STOP (prize
  ~2-4% of a frame), but the reason changed and the "~90 h" figure is retired either way (it priced a
  population that could not clip at all).
- **LESSON: SCOPE NARROWED ON A CLOCK ARGUMENT OWES A RE-ASK WHEN THE SEARCH COMES UP EMPTY.** A budget
  decision ("this axis is expensive per draw") silently becomes a claim about where the answer is. Six
  sessions read "0 genuine" as needing MORE of the same scope rather than a DIFFERENT one.
- **THE ONE HOLE THAT COULD HAVE MADE IT WRONG, CLOSED.** The hull is measured at the FROZEN camera and
  the camera is what s95-98 varied. `entry_camera.hull_shift` over five cameras spanning the channel
  incl. `[1,1]` and s98's `[254,254]`: area 1686.7 -> **1687.0 u2** (+0.02%), bbox unchanged, **0 of 20**
  stations inside at 1 u margin.
- **WHY THE "RECORD" KEPT IMPROVING AND NEVER CONVERTED.** `window_gap` compares a residual NUMBER to an
  interval and **drops the STATION the interval belongs to**, so the search drove every candidate to the
  reachable boundary nearest an unreachable target and held it there (s96's 8.829e-06, s98's 0.0 = the
  same point). **It vindicates s93's own frame table:** cell 2553 reading 1.1e-02 at <=4 frames was RIGHT,
  and the 400x "improvement" the lean+camera axes booked was resid values nearing a band no plan can
  stand in.
- **THE FRAME LEVER IS NOW ONLY THE THRUST-15 STORY.** At thrust 15 the dust is at **5 walk frames**, the
  frame is what `entry_fan.capped` refuses, and cell 2553 is +9 BAM of a 455 BAM axis worth ~1 frame total
  (~2-4% of a frame) -- **~25:1 against.** At thrust 14 the dust is at **4**, so the frame is no longer
  the binding constraint; the price is.
- **THE LESSON (sixth level, and the first that was not about COUNTING).** Every number was honest and
  measured in the wrong SET. General check: **ask where a measurement's population lives relative to the
  set the candidates are drawn from.** And "0 of 100, so <=3%" is a bound on a rate, not a rate -- it
  scaled the budget 30x and kept the purchase.
- Gates NEW `tests/test_entry_reach_stations.py` (10 + 1 slow). KB NEW
  `strategy/clip-station-reachability.md`; superseded 90 h reading MIGRATED to
  `history/ehits-ninety-hour-axis.md`; `clip-band-transfer.md` + `clip-exit-angle.md` corrected.
- **GOTCHA `sep` 20 UNDER-TILES** `hull_scan` (marches leave the hull, counterfactual goes dark = a false
  negative from the knob). Robust at `sep` 6/12 and grid step 1.0/1.5/3.0; argue negatives at `sep` 6.

### s99 continuation -- DERECK'S TWO CORRECTIONS, and they overturn the axis AND find 2 frames

- **CORRECTION 1 -- "MORE TO THE RIGHT" MEANS A **LOWER** FACING THAN 40841. The KB HAS THE SIGN
  BACKWARDS.** `clip-exit-angle.md` labels INCREASING facing "+BAM ... as far to Link's RIGHT as
  possible" and that is what aimed s91-s99 (and all of s99's first half) at cells 2553-2581. **The
  productive side is DOWN.** Re-scanned: cell **2551 (facing 40820, 0.115 deg right) has 220 reachable
  live stations at the frame floor -- MORE than the delivered 2552's 208**; 2549 (40795) has 10 at
  thrust 14; 2525/2532/2533 (1.7-2.4 deg right) have 1 each (plateau bands). **THE PAGE STILL NEEDS
  MIGRATING** -- the sign drove nine sessions of spend.
- **A CLIP 0.115 deg RIGHT IS BUILT AND CONFIRMED (model-side).** Cell 2551, facing 40822, aim [91,180],
  thrust 15, lean 64793, plan `[0,228,168,2,198,146,2]`, camera `[254,254,128]`, entry
  (-1529.8834228516,-780.0580444336), 4 walk frames. 7 genuine found; all 7 pass `confirm_entry` AND
  cross-engine at **worst_ulp 0**. DTM `_generated/s99/tetrapush_2551_frame_floor.dtm`.
  **Dereck's verdict: 0.115 deg is indistinguishable from what he has -- not worth a console run.**
- **THE CORNER'S HARD LIMIT (geometry, validated two ways).** Link's brace (>=35 u off each wall, the
  delivered `old` sits at **exactly 35.00003**) plus the 49.74 u max lunge pin the cut start to a
  **0.65 u pocket** on the corner diagonal, so the seam vertex bears **224.19-225.25 deg** -- the whole
  achievable facing window. The external catalogue
  (`tww-python-scripts/ww/data/seam_clips/Hyrule/Room0__room.csv`, `init->dest`) independently gives
  **224.717** for this corner. **So facing ~35000 (192.26 deg) is IMPOSSIBLE here -- 32 deg out, ~30x the
  window** -- at any Tetra placement or entry. The nearest ~192 deg exit in the room is **198.0 deg at
  (-1269.6,-14416.6), 13 400 u away.** A different exit direction = a different SEAM, not a solver knob.
  **That CSV's `angle_deg` is the seam's INTERIOR angle (90.566 here), NOT the exit direction.**
- **CORRECTION 2 (THE BIG ONE) -- "WE PRESS B 2 FRAMES LATER THAN POSSIBLE", AND HE IS RIGHT.**
  `procFrontRoll` (decomp 6852) dispatches a cut only when `getFrame() > mRoll.field_0x10` (**17.0**);
  the frame ctrl advances at `field_0x8` (**1.1**) from a start of `field_0xC` (**0.0**, checked in
  `d_a_player_HIO_data.inc`), so 1.1*16=17.6 first clears it -> **cut_step 15 = THRUST 13 is the floor**.
  **The delivered clip is thrust 15 = 2 frames late.** Cause: `entry_fan.plan_frames` counts WALK HOLDS
  ONLY, and the thrust is modelled as a third DRAW axis, so a later thrust cost the frame-minimal
  ranking NOTHING. Honest cost = `plan_frames + thrust + 4` (matches the console fixture's
  `cut_i - n_console` = 23). NEW tracked `entry_fan.THRUST_FLOOR` + `plan_cost` + 2 gates. **The existing
  ranking is deliberately UNCHANGED (it would change which candidate a delivery goes to -- Dereck's
  call).** **HIS STICK HYPOTHESIS IS RULED OUT:** `mStickDistance` is only in the OTHER branch (the
  rate<0.01 normal-speed decrement); the cut gate has no stick term. Per-thrust live stations at the
  floor: 2552 = 208/111/0 (thr 15/14/13), 2553 = 0/918/0, 2551 = 220/0/0, 2549 = 0/10/0 -- so **1 frame
  looks collectable at the delivered facing (thrust 14) and thrust 13 has NO reachable live station
  anywhere sampled** (the 2nd frame likely needs Tetra moved -- unsearched).
- **THE PREDICATE THAT FINALLY WORKED: the engine's own `genuine` flag, not a band.** `ShoveCtx.sweep_par`
  returns it per candidate; it is what `confirm_entry` re-derives. **Calibration: the DELIVERED cell 2552
  is 1 genuine in 2 888 346 frame-floor candidates**, so one pass is a lambda~1 draw -- which is how
  "0 genuine in one pass" was correctly read as a 37% coin flip rather than a wall. Cell 2551 hit on
  camera 3. Empty after full hunts: 2553 thr14 (98.2M over 34 cameras), 2549 thr14 (40.4M/14 cameras),
  2553 thr13, sub-cap thr14 (29.3M, though |resid| got to 4.1e-07).
- **THREE HARNESS BUGS FOUND, ALL FIXED, ALL WOULD HAVE BITTEN THE NEXT SESSION:**
  1. **`cross_engine.composite_log` NEVER CARRIED `substickX`** -- it built every frame off
     `seed['log'][-1]`, so any CAMERA-found hit was replayed at the FROZEN camera: different trail,
     different arrival, `handover_ok` False at ~1e6 ULP, `composite_moved` 0.24 vs a 49.86 predicted
     lunge. **Reads exactly like the composite refusing the lunge.** It predates the camera axis (s95)
     and no camera pass had ever produced a genuine hit, so nothing exercised it. Fixed; control = the
     s90 delivered clip, still 0 ULP.
  2. **DELIVERY MUST AUTHOR THE **FULL** LOG (herd + plan), not the tail.** `build_boot_movie` puts
     `log[i]` at game-frame F0+1+i and the herd's last 78 frames are PART of the log (s90 authored 107
     frames: n_console 78 + plan). Authoring only the 29-frame tail shifted everything 78 frames early --
     the A-press fired mid-herd next to Tetra and **Link TALKED to her** (Dereck saw this on console).
  3. **A fixed output path let the 2549 hunt CLOBBER the 2551 hits** the delivery was built from; the
     hunt now writes `hunt_<cell>_thr<thrust>.json`.
- **KB NEW `mechanics/roll-cut-thrust-floor.md`** (the gate + the uncounted frame cost). Gates
  `tests/test_entry_reach_stations.py` 13 -> **15**.

### s100 -- BOTH FRAMES ARE LIVE. Thrust 13 clips from an ENTRY FAMILY the hull cannot see (Dereck's re-ask).

- **THE TETRA-PLACEMENT LEAD (s99's next step) IS CLOSED WITH A MECHANISM: she is PLOWED as the roll sweeps
  past, so her overlap on the CUT frame is the roll's geometry, not her seed.** Over a +-3 u grid of her the
  thrust-13 shortfall moves **0.015 u per u** (-0.157..-0.217, never through zero). Closing 0.19 u needs
  ~12 u of her = 4+ herd frames at `objective.LATERAL_RATE`, for a 2-frame prize, and outside
  `placement_thread`'s ~10 u lateral window. **Do not re-open it.**
- **WHAT THE INVARIANCE POINTED AT: `genuine_clip` IS THREE CLAUSES AND A SEARCH ONLY EVER RANKS THE RAZOR.**
  Printed as numbers (7 s, `_notes/s100_thrust13_diagnose.py`), thrust 13's cut endpoint lands **0.172 u
  SHORT of the nearer wall plane** while `old` is the same brace-pinned point at all three thrusts and the
  lunge is constant -- so the only differing term is the cut-frame push: **0.077 u at thrust 13's razor
  stations vs 0.613 at thrust 15's genuine ones**.
- **THE LAW (new KB `strategy/clip-razor-depth.md`): S IS THE CORNER VERTEX, so it lies on BOTH wall
  planes** -> a razor solution puts the endpoint on the ``old -> S`` ray and
  **`depth ~ |base + push| - |S - old|`**, `base` constant per facing. s99's "0.65 u pocket" as a RANKABLE
  quantity. Measured over every in-hull razor solution (Newtoned from the whole hull, 4 + 5 walk frames):
  thrust 15 |S-old| 49.3812 depth **+0.2533**; thrust 14 49.4053 **+0.2074**; thrust 13 49.6209
  **-0.1868..-0.3464, 0 genuine**. `plan_cost` 23 / 22 / 21.
- **HOW TIGHTLY `old` IS PINNED IS THE MECHANISM** (and do NOT assert a pin off a 6-decimal print -- three
  gates were written on that over-claim and caught it): thrust 15 = **bit-identical** at all 48 solutions;
  thrust 14 = 4e-4 u of z; thrust 13 = one `old` each over ~0.07 u. **The floor thrust cuts BEFORE the
  brace** (costing 0.24 u of brace + 0.45 u of push).
- **AT THE FRAME FLOOR: over the whole 45-cell aim window, thrust 13 reads depth < 0 at ALL 25 cells that
  have a razor solution at all** (-0.472..-0.133); thrust 14 admits at 23 of 25, so **thrust 14 (`plan_cost`
  22) is a frame available with nothing else changed**. **THAT IS A CLAIM ABOUT THE FRAME-FLOOR HULL, NOT THE
  CORNER -- see the s100 correction below.** Resolution control (needed because thrust 13's
  `old` is not pinned): over grid steps 2.0/1.0/0.5/0.25 the best depth moves inside **0.008 u** and never
  trends to zero -- a ~24x margin on a 0.19 u shortfall.
- **DEPTH IS A GATE, NEVER A RATE.** `depth <= 0` is a proof; `depth > 0` is only an admission. It does NOT
  correlate with live-station counts (cell 2549/thr15: depth +0.513, **0** live; cell 2553/thr14: +0.127,
  **918**).
- **NEXT SESSION'S BUY: thrust 14 at cells 2525 / 2533 / 2549** -- genuine solutions on a 1 u grid and
  2-5x the delivered cell's depth (+0.85/+0.94/+0.45 vs +0.207), on the LOW (Dereck's "right") side, and
  **s99 never hunted 2533 or 2525 at thrust 14 at all**.
- **TRACKED so it cannot be re-bought:** NEW `harness/tetrapush/razor_depth.py` (`depth_of`,
  `razor_solutions`, `screen`, `thrust_map`; CLI `screen`/`map`; ~5 s a configuration, ~3 min the whole
  window x thrust) + NEW `tests/test_razor_depth.py` (**9 + 1 slow**). Superseded lead MIGRATED to
  `knowledge/history/thrust-13-placement-lead.md`.
- **GOTCHA -- A GRID CANNOT FALSIFY ANYTHING ABOUT `genuine`:** a 0.25 u grid over **7.44 M** in-hull
  entries turned up **ONE** genuine row (the set is a ~1e-4 u ribbon). Sample dense ACROSS the locus at
  `hull_scan`'s live stations: **275 genuine rows in 8 s, 0 counterexamples** to `genuine => depth > 0`.
- **GOTCHA -- `GT.genuine_clip(old, pred)` is NOT the engine's predicate** (the engine tests the POST-CrrPos
  endpoint; `depth` = sweep slots 8/9 at the PRE-CrrPos one), and a 0.02 u push grid "proves" a genuine push
  impossible because the razor is ~1e-4 u wide ([[full-fp-precision-coords]]).
- **GOTCHA -- the cost of any hull sweep is the PYTHON `entry_reach.contains`, not the native sweep.** The
  hull depends only on (facing, frames): build the point list once and reuse it across thrusts/leans
  (25+ min -> 558 s for the same work).
- **LESSON: ask which CLAUSE of the acceptance test is failing before buying more draws against it.** Six
  sessions priced draws by residual-band probability while the endpoint at those configurations could not
  reach the wall at all -- the residual is the quantity that VARIES, so it is the one a search naturally
  ranks; the hard gate had never been printed.

### s100 CORRECTION -- Dereck: "if slashing on frame 13 works I want both frames." IT WORKS.

- **MY "REFUSED BY THE CORNER'S GEOMETRY, ANYWHERE ON IT" VERDICT WAS SCOPED TO THE FRAME-FLOOR HULL.** The
  law and every number above reproduce; the word *anywhere* was wrong. `entry_reach`'s hull sits **~239 u**
  from the corner brace and a `cut_step` N roll travels **26N u**, so out of it Link always reaches the wall
  around step 9 and CrrPos SLIDES him in -- the hull holds ONLY the arrive-early-and-slide family, and two
  fewer slide frames IS the 0.19 u. **The tell was in my own output: those solutions cut from |S-old| 49.62
  while the delivered clip cuts from 49.38** -- the ENTRY SET was the constraint, not the corner.
- **THE ARRIVE-EXACTLY FAMILY (hull removed, 851 598 Tetra x entry pairs in ONE `sweep_par`):** 1167 razor
  solutions at cut_step 15 land on the exact brace thrust 15 cuts from, and entries **~390 u** out (26 x 15 =
  the roll's own travel, so the cut fires as Link **ARRIVES** instead of sliding) go **POSITIVE**: **depth
  +0.0399, Tetra 100 u in -z of her console read, entry (-1422.7771410239, -677.8451682961), WALKABLE**,
  |S-old| 49.2792, travel 386.8 u.
- **THE PLACEMENT HAS TWO SCALES AND I PRICED THE WRONG ONE:** inert at the +-3 u a herd tolerates (0.015 u
  per u, she is plowed), DECISIVE at ~100 u where she changes the entry family. That means a **different
  herd**, which is the real open question.
- **WHAT IS STILL MISSING IS BARRIER CLEARANCE, NOT THE PLANE.** `genuine` needs the swept segment to clear
  the CrrPos barrier and every genuine row on this corner sits at depth **>= 0.1273** (four known-live
  configurations: 0.1273 / 0.2073 / 0.2533 / 0.3398, each bit-constant across its own population). The
  arrive-exactly family is **~0.087 u** short -- a FIFTH of the hull-bounded gap, push as the lever (0.446
  vs 0.613), in a family no pass has searched.
- **NEXT: (1) sweep the placement plane FINELY about off (0,-100) -- the hit came off a 20 u grid -- plus the
  LEAN axis (it sets the Co centre at the cut); (2) put the entry on the arc `|entry-brace| ~ 26*cut_step`
  and sweep along it + the aim cells; (3) only then price the herd. Tools `_notes/s100_{pair_refine,
  arrive_exact}.py`. Thrust 14 stays the safe frame.**
- **GOTCHA -- `zero_the_resid` IS UNCONSTRAINED AND LEAVES THE ROOM** on hull-free solves: "depth +5120" at
  entries like (-6397,-5796), |S-old| **7091 u**. Filter to inside-the-box + walkable + |S-old| <= 56.
- **GOTCHA -- `sweep_par` TAKES PER-ITEM 4-TUPLES `(tetra_x, tetra_z, link_x0, link_z0)`**, so the whole
  PAIR space sweeps in one native call (851 598 combinations in 13 s). Use it instead of looping placements.
- **LESSON (and it is s99's, one session later and pointed the other way): A HULL IS A CLAIM ABOUT PLANS,
  NEVER ABOUT GEOMETRY.** A reachable set exists to price plans; the moment it bounds a claim about what the
  corner ALLOWS, the claim has silently inherited a herd's arrival position. Name the set before writing
  "impossible".

### s101 -- THE ARRIVE-EXACTLY HIT IS UNPLACEABLE. Thrust 13 refused with no hull AND a legitimate placement.

- **A PLACEMENT IS A POSITION SHE CAN STAND IN, AND THE ENGINE DOES NOT CHECK ONE.** `ShoveCtx._run` seeds
  her by WRITING a position with no motion at `placed_step`, so her own CrrPos has no sweep to line-check
  and `wall_correct`'s outward-offset segment misses a point already behind the plane -- she stays inside
  the wall and grazes Link's Co cylinder from a bearing no reachable spot offers. Bar = her BG wall radius
  **50 u** (`npc_zl1.WALL_R`); all **288** live-validated genuine coords sit at **>= 56.98 u** off both
  planes. NEW `razor_depth.placeable`. **s100's headline hit (Tetra 100 u in -z) is 3.54 u behind wall B**,
  and that graze WAS its +0.0399. Superseded claim migrated to
  `knowledge/history/arrive-exactly-through-the-plane.md`; the clause is `knowledge/model/placement-standability.md`.
- **THE LAW IN ITS USABLE FORM: `|base|` IS A CONSTANT 49.220224583762864** (thrust-invariant exactly,
  facing-invariant to sine-table quantization), so `depth = kappa*(|base| + push.u - |S-old|)` with
  kappa = |n.u| ~ 0.712, and **a clip is bought with `push.u`** -- the push's PROJECTION on the old->S ray,
  set by where she sits relative to his Co centre (he is shoved directly AWAY from her, so push.u > 0 means
  she is up-ray BEHIND him). `razor_depth.law_of`.
- **WHAT ACTUALLY DIFFERS BETWEEN THE THRUSTS (Dereck: "it's all the same animations" -- HE IS RIGHT, and
  this retires half my own reading).** In-hull the columns read push.u **+0.5175 / +0.4773 / +0.1304** at
  thrust 15 / 14 / 13 against braces **49.3812 / 49.4053 / 49.6202** -- but **shift the entry by whole roll
  steps and `old` is BIT-IDENTICAL at all three** (-1692.3143310546875, -955.07611083984375). The brace is a
  property of the ENTRY SET, not of the frame the cut fires on. **Only the push is the thrust's.** The
  cut-frame contact is a **1.2 u graze on an 80 u radius sum**, and Link's Co centre is POSED FROM THE MODEL
  (animation-frame-indexed), swinging **1.1..31.3 u** off his position over the roll at **2-9 u per frame** --
  so from the brace-reproducing entry her console spot pushes **0.0000** at thrust 13 where it pushes 0.6129
  at thrust 15. Same animation, a different frame of it. Gated
  `test_the_brace_is_reproducible_at_every_thrust_but_the_push_is_not`.
- **THE FLOOR IS THE CORNER'S AND IS NOW MEASURED** in endpoint space over the brace locus
  (`razor_depth.floor_at_brace`): **0.1154..0.1216, no trend** in brace or aim. s100's ">= 0.1273" was the
  min over the four populations that happened to have live dust. `DEPTH_FLOOR = 0.1150` screens safely.
- **VERDICT: 0 of 45 cells reach the floor at thrust 13**, hull-free, placement-constrained
  (`razor_depth.placeable_screen`, ~3 s a cell) -- best depth **-0.0208** (cell 2554), which does not reach
  the PLANE; a 4x finer grid moves it 0.0007. Mechanism, not budget: **the push that aims at the corner is
  the same push that shoves Link off the brace**, and it costs |S-old| faster than it buys push.u.
- **TWO LEVERS MEASURED DEAD (both were the s100 handoff's next step):** the placement plane (push.u pinned
  **0.11-0.12** over +-40 u at 4 u and +-200 u at 8 u -- a fresh contact is only available on the crescent
  his cylinder just reached, i.e. AHEAD of him) and the LEAN (`m351C` decays 35%/frame, the delivered -388
  draw is **-1 by roll frame 15**, so +-3000 s16 moves depth 0.0003 u -- `knowledge/mechanics/roll-lean-decay.md`).
- **GOTCHA -- DO NOT SWEEP THE LEAN AT A FROZEN ENTRY:** reads 0.03 u of sensitivity where the truth is
  0.0003; changing the lean moves the razor, so re-solve the entry per value.
- **GOTCHA -- `GT.genuine_clip(old, NEW)` IS the engine's predicate** (post-CrrPos endpoint), so it is a free
  independent cross-check of any engine hit; only `(old, pred)` is the wrong one ([[full-fp-precision-coords]]).
- **GOTCHA -- a literal copied from a print is not a measurement.** `BASE_REACH` was first written with digits
  the print never had; `DEPTH_FLOOR` 0.1155 sat above a brace measuring 0.11536. Exact-equality gates caught both.
- **LESSON (the third scope error in three sessions, and past "name the set"): EACH AXIS A SEARCH GAINS NEEDS
  ITS OWN DELIVERABILITY CLAUSE.** The filter written for the first axis will not cover the second -- Link's
  entry had `is_walkable` from the first pass, her placement never got one because she arrived as a parameter
  rather than as a plan. **The tell was in my own output, one column over: every row printed `walkable True`,
  for LINK.**

## Session 102 (2026-08-05) -- THE REFUSAL IS A CONJUNCTION, AND IT IS MONOTONE

s101's axis 1 (her VELOCITY at the cut, the one term no sweep had varied) is BUILT and 0-ULP the game's
own `Zl1FollowState` -- and it is **not what was refusing thrust 13**. What was refusing it is that the
razor and the contact had never been asked at the same time.

- **THE CONJUNCTION IS THE VERDICT.** Band a swept space (placement x entry x seed motion, 10-13 M rows a
  cell) by |resid| and take the best `achievable_depth`. **Every unit of residual left un-zeroed buys
  depth**: cell 2557 reads **-0.0363 with NO contact** at |resid| <= 0.05 (exactly the no-push value) and
  +0.2205 by |resid| 10; cell 2552 reads **+0.0399 with 0.65 u of real contact** at <= 0.05, then +0.156 /
  +0.391 / +0.512. **The razor's own acceptance band is ~1e-4, 500x tighter than the tightest column** --
  so the paying push is real and NEAR the curve, never ON it. Best corner-scoped near-razor value **+0.0399
  at cell 2552**: past the PLANE (s101's best over everything was -0.0208), still 0.075 under the 0.1150
  floor, and an UPPER bound (it over-reads the delivered clip by 0.066).
- **THE EJECTION EQUILIBRIUM = why the placement plane reads inert** (not a budget, a mechanism). The plow
  ejects her HALF the overlap per frame, so her cut-frame distance is an ATTRACTOR: 22 of 24 static seeds
  land at |c - t| **87..93 u** having been flung **10..60 u**, against a requirement of <= 79.4. Seeding
  her closer buys a deeper plow that ejects her further. KB `mechanics/plow-ejection-equilibrium.md`.
- **THE LAW INVERTED** (`razor_depth.contact_required`): the smallest cut-frame OVERLAP a cell can clip on
  + the spot she must stand in, analytic. **THRUST-INDEPENDENT** (13 vs 15 within 1% at every cell = Dereck's
  "it's all the same animations" as a number), **MONOTONE IN THE BRACE**, and it reproduces the delivered
  clip to **1.2 u and 0.8 deg**. `|base|` 49.2202 is **0.0345 u SHORT** of the corner-most brace 49.2546,
  so every clip here is bought with contact. KB `model/required-cut-contact.md`.
- **THE DELIVERED CELL IS EXPENSIVE (0.8037) AND CELL 2557 IS CHEAPEST (0.3939) -- AND 2552 STILL WINS THE
  CONJUNCTION.** 2557 wants her 4.9 deg off the ray = ON Link's roll line, where the plow ejects hardest;
  2552's 34 deg costs more overlap and lets her stand off the line. **The optimum is INTERIOR and the two
  cells measured are its ends** -- sweeping the other 43 on the corner-scoped conjunction is the next step.
- **NEW TOOLING.** `ShoveCtx._run` seed motion `(speedF, facing, stt)` (`stt < 0` = the historical at-rest
  seed, bit-identical) + `sweep_par(..., extra=True)` exposing the **CONTACT PAIR** on the cut-consumed
  frame (slots 10-13), bit-identical to `cc_push.co_move_pair`. NEW `harness/tetrapush/tetra_motion.py`
  (`razor_batch` == `zero_the_resid` batched, `contact_of`, `surplus_of`, `target_spot`, `climb`).
  `razor_depth.achievable_depth` / `brace_for_ray`. Gate `tests/test_tetra_motion.py` (10).
- **GOTCHA -- a climb on the DEPTH cannot find contact.** With no overlap the push is zero and the depth is
  FLAT in her placement, so a pattern search stalls on the no-push plateau. Use the contact pair.
- **GOTCHA -- FOUR scope errors in one session, all one shape: a scalar ranked over rows it did not scope.**
  Raw `depth_of` = **+13.6** for a Link 86 u out; the law's `d_ray` on a raw row silently grants the
  steering the razor must pay; magnitude-only surplus = **+6.5** for a 7.4 u overlap pointing anywhere;
  `achievable_depth` = **+0.0955** at `|S-old|` **107.46**, Newtoning to -41. **`achievable_depth` reports
  the brace the razor WOULD use, not the one the row is at -- screen `|S - old|` first.**
- **GOTCHA -- never call `achievable_depth` per row in a sweep** (it rebuilds `fast_schedule`: a 4-minute
  scan became overnight). `contact_required` is ~13 s a cell; hoist it. And `pkill -f` does not kill a
  `nohup`ed python here -- use `Stop-Process -Id`.

## Session 103 (2026-08-05/06) -- THE BANDED PEAK IS REAL AND DOES NOT SURVIVE THE RAZOR

All three s102 handoff items ran. The peak exists in the BAND, dies on the razor, and the reason is a
single number off the baked schedule that no search can move.

- **THE TWO NUMBERS TO QUOTE**, both on the razor (`|resid| <= 1e-4`), both cell 2554, floor +0.1150:
  **hull-free -0.015503**, **deliverable (4-frame hull, `plan_cost` 21) -0.026245**. NEITHER REACHES THE
  WALL PLANE. s101's on-razor best was -0.0208, so the seed-motion axis + interior optimum + wide box +
  fine grids together are worth **+0.005**, not the +0.088 the bands read.
- **DERECK PUSHED BACK ON THE METHOD ("you haven't identified the correct location yet for where to roll
  and where to place tetra") AND HE WAS RIGHT, BUT THE ANSWER DID NOT MOVE.** The first confirmation
  Newtoned the BAND'S OWN top 8-16 rows over a +-40..60 u entry corridor -- a biased sample ranked by a
  proxy the same session proved bad. Redone: a **dense march** (505 k Newtons a cell, +-200 u corridor,
  4.0 M over 8 cells, no band in the ranking) SMOOTHS the raggedness (2552 -0.065 -> -0.0317) and leaves
  the peak at **-0.015503**; a **fine local test** (placement 1 u / entry 2 u / seed speed 0.25 / seed aim
  1.4 deg, 1.0 M Newtons) returns **EXACTLY -0.015503 at a different triple 2-3 u away**. Depth
  bit-identical across neighbours = the ejection equilibrium as a PLATEAU, so the grid was never the
  bound. **0 of 320 genuine.** And `AIM_WINDOW`'s hardcoded 900 BAM is not the bound either: the
  geometric window is 2304 BAM but the requirement minimises INTERIOR to it (facing 40920) and climbs to
  13.2 at the edge. Tools `_notes/s103_{march,local}.py`.
- **THE CONFIRMATION IS THE VERDICT AND NOBODY HAD RUN IT.** Banded at `|resid| <= 0.05` the conjunction
  reads 2551 +0.0295 / 2552 +0.0427 / 2553 +0.0536 / **2554 +0.0674** / 2555 +0.0603 / 2556 -0.0170 /
  2557 -0.0363 (45-cell coarse best +0.05966 at 2555). Newtoned onto the razor: 2551 -0.0529 / 2552
  -0.0648 / 2553 -0.0293 / **2554 -0.0157** / 2555 -0.0918 / 2556 -0.1327 / 2557 -0.0795, **0 of 56
  genuine**. Two independent routes agree at the peak (lead-set Newton -0.015747; a 44.8 M-row fine
  sweep at a 10x tighter band -0.015625). **THE BAND ALSO MIS-RANKS THE CELLS** (banded 2554~2555 within
  0.007; on the razor 2555 is fourth-worst). **NEVER QUOTE A BANDED DEPTH WITHOUT ITS NEWTON.**
- **THE TRADE IS NOT STEERING (item 2).** At the brace its OWN razor forces (`brace_for_ray` of the
  facing, fixed-pointed in the push) `delta` is **0.000 at all 45 cells**, so a cell pays no steering
  and the bar is just `2*(s_forced - |base| + floor/kappa)`: min **0.4256 at 2557** vs a theoretical
  0.3927. What refuses thrust 13 is the CONTACT, not the aim.
- **AND THE CONTACT IS REFUSED BY `razor_depth.cut_frame_swing` (NEW).** The along-roll step of the
  animation-posed Co centre INTO the cut-consumed frame is **+8.9252 (t13) / +1.8547 (t14) / -1.2850
  (t15)**, **aim-invariant to 1e-4**. She can only pay from UP-RAY, so positive = the cylinder RECEDING
  from the only direction that pays. The Co centre tucks to -13.5 u at step 11 then straightens +8.07,
  +8.93 -- **t13's cut lands on both**; t15's lands after the reversal, which IS its free 1.2 u. Matches
  s101's push column (+0.1304/+0.4773/+0.5175). KB NEW `mechanics/cut-frame-co-swing.md`.
- **THE WALK COUPLING IS PRICED AND IT DOES NOT BITE (item 3).** Asking whether the conjunction's rows
  happen to be hull-reachable says 94% are outside even the 6-frame hull -- but that prices the GEOMETRIC
  entry family, not the corner (s100's error again). Gridding `entry_reach.entry_hull` itself recovers
  banded results within **0.004** of hull-free at every peak cell, confirmed -0.026367 vs -0.015747. **The
  hull costs 0.011 of depth; `plan_cost` 21 entries EXIST, they just do not clip.** Control passes.
- **`placed_step` IS A LIVE ENGINE KNOB NOBODY HAD MOVED OFF 0** and it localises the refusal to the
  PLOW: the depth clears the floor the moment she gets 3-4 frames of plow-freedom (+0.886 at P=12, cell
  2557) and every such row misses its own deliverability clause by 30-70 u.
- **ONE FRAME IS AVAILABLE, THE OTHER IS REFUSED BY THE ANIMATION.** Thrust 14 (`plan_cost` 22)
  re-measured on the current engine, in-hull, console placement (`placeable` True): **+0.2075 at cell
  2552** vs t15's +0.2532. NOT delivered and NOT a substitute (Dereck's call stands); reported because
  it prices the second frame.
- **GOTCHA -- THE PLACEMENT HALO WAS THE BOUND**: every peak cell's best sat ON the +-60 u box edge
  (2555 at offset (-48,+60)), s100's hull error in a smaller box. Re-centred on the corner BRACE at
  +-200 u it reads +0.06026 and is off the edge, so the plateau is genuinely flat -- luck, not method.
  Scans now report `on_box_edge`.
- Tools NEW: `_notes/s103_{conjunction,forced_brace,placed_step,walk_price,inhull,fine,co_swing,
  untouched}.py`; `razor_depth.{cut_frame_swing,co_centre_offsets}`.

## Session 104 (2026-08-06) -- THE FRAMES WERE ON THE OTHER ADDEND OF plan_cost

`plan_cost = plan_frames + thrust + 4`. Four sessions attacked the THRUST term and closed it against an
animation constant. **The WALK term had never been taken down**, and both frames were sitting there.

- **THE LADDER, her placement SWEPT (+-170 u / 4 u about the brace), entries gridded 1.0 u inside the
  measured 2-frame cloud, locus walked at ~1e-5, all independently re-verified from station coordinates
  alone** (engine genuine flag AND `GT.genuine_clip` on the post-CrrPos endpoint, containment in the FINE
  stride-2 2-frame cloud, `is_walkable`, `placeable`, depth over floor):

  | plan_cost | thrust | live placements | verified | deepest | cut_frame_swing |
  |---|---|---|---|---|---|
  | 21 | 15 | **211** (1130 stations) | 8/8 | **+0.339905** | -1.2850 |
  | 20 | 14 | **56** | 6/6 | **+0.207886** | +1.8547 |
  | 19 | 13 | **0** | - | none (nearest 1.6e-03) | +8.9252 |

  Floor +0.1150; the banked 4-frame clip reads +0.2533, so **21 is DEEPER than the deliverable it beats by
  two frames**. Endpoints land within 1 u of the known seam corner (-1727,-990), free corroboration.
  `|resid|` down to 2.1e-07. Fixture `fixtures/courtyard_walk_budget_s104.json`, gate
  `tests/test_walk_budget.py` (14 + 1 slow).
- **THE ADDENDS ARE INTERCHANGEABLE IN THE ARITHMETIC AND NOT IN THE PHYSICS.** A shorter walk starts the
  roll earlier WITHOUT re-phasing it, so it moves the whole roll-and-cut in time and can never rescue the
  floor thrust -- `cut_frame_swing` still orders the rungs, and 19 is refused for exactly s103's reason.
  Second independent re-confirmation of s103: thrust 13 at walk 4 on the widened hull is 0 live over all 22
  cells **even with a grid point at `|resid|` 1.31e-05, inside the razor band**.
- **THE WALK FLOOR WAS INHERITED, NOT MEASURED.** `entry_reach.FLOOR_FRAMES = 4` documents itself as *the
  delivered clip's plan length*; s100 tested walk **5** (more) and nothing tested 2 or 3. And
  `MEASURE_FAN`'s ``j1=(2,3,4)`` cannot EXPRESS a 2-frame plan (`plan_frames` = base + j1 + j2, j2>=1), so
  the pinned fixture returns **0 endpoints** at budget 2 and that reads as "no such plan". `iter_fan2`
  accepts ``j1=1``: ``base_frames=(0,), j1=(1,), j2max=1`` is a real two-stick plan.
- **GOTCHA THAT NEARLY SHIPPED A FALSE NEGATIVE ON THE HEADLINE QUESTION.** `hull_scan`/`hull_field` grid
  LINK'S ENTRY with the pushed actor FROZEN at one placement. Over the 2-frame cloud at her console
  placement she is out of Co range on the cut frame from ~40 u away, so the field is a no-push plateau and
  the scan reports `no leverage` at all 22 aimable cells. Cell 2552, the SAME 492-point grid: **console
  placement 0 leverage / |resid|min 3.29e-01; a productive placement 293 leverage / 3.50e-03.** **ANY SCAN
  THAT GRIDS ONE ACTOR'S POSITION MUST SWEEP THE OTHER'S, or its zero is about the frozen actor.** Third
  session of this shape (s99 clip-station-reachability, s100 reading a reachability filter as a price).
  Dereck caught it: *"i assumed for testing you would just teleport Link to locations ... we should just be
  trying to prove it works first before finding the walk plan."*
- **THE 2-FRAME CLOUD IS BOUNDED BY PHYSICS, NOT THE ALPHABET** -- do not refine sticks at it. On the only
  2-frame plan shape: stride 8 (583 sticks) 139 213 endpoints / 123.8 u^2; stride 2 (3355) 1 577 346 /
  **129.7 u^2**. 5.75x the alphabet buys **+4.8%** area, 0.1 u of extent, and did not move the nearest
  genuine entry off 2.218 u. Two frames at the speedF cap is the bound.
- **FIXTURE DEFECT FOUND: the pinned s93 walk hull is 4.8x too small in AREA** (1688 -> 8074 u^2, all 616
  vertices contained), same ``j1`` truncation. Only `outside` was ever a claim, so every prune against it
  was over-tight -- negatives too EARLY, never too late. NEW `fixtures/courtyard_walk_hull_s104.json`
  (budgets 2/3/4 + the fine 2-frame clouds); **s93 left pinned**, its own gates were written against it.
- **THE HERD IS NOW THE PRIZE, AND THE SIGN IS FAVOURABLE.** `plan_cost` counts from the ARRIVAL, so a
  shorter walk is only real if the herd does not hand the frames back. Against the console placement's
  137.2560625336703 u to the corner (POSITIVE = less to herd): **cost 21 spans -50.6..+64.6 u, 163 of 211
  need LESS herd; cost 20 spans -16.2..+69.4 u, 46 of 56.** A DISTANCE, never a frame count.
  **DERECK RELEASED THE THRUST-13 REQUIREMENT:** *"I'm fine with a 15 frame thrust if it means we need to
  herd her less as well."* So the objective is frame-minimal across ALL THREE addends now.
- **THE REMAINING DELIVERY GAP IS A MATCHING JOB, NOT A FEASIBILITY ONE.** A station inside the cloud is
  dust at an entry a two-frame plan can REACH, not one it LANDS on; the fan's entries are discrete (two
  sticks in the whole plan) and the genuine set is a ~1e-4 u ribbon. Density is ample -- stride 1 gives
  ~1 M endpoints per u^2 against a ~1.7e-3 u^2 ribbon.
- Tools NEW: `_notes/s104_{walk_hulls,march_cost21,fine_hull2,cost21_hunt,verify_cost21,mint_fixtures}.py`
  (+ `short_walk_{scan,window}.py`, the VOID frozen-placement pass, kept as the counterexample).
  KB NEW `knowledge/strategy/plan-cost-walk-budget.md`.

## Session 105 (2026-08-06) -- THE PRICE OF A PLACEMENT, IN FRAMES

s104 measured the saving in UNITS and said the conversion was the job. Done: one correction, one screen,
one bracketed price and two closed doors. KB NEW `knowledge/strategy/herd-price-of-a-placement.md`; the
conversion is `harness/tetrapush/herd_price.py`, gated `tests/test_herd_price.py` (13, 1.9 s).

- **THE ACCOUNTING WAS OFF BY THREE.** `plan_cost` counts from the ARRIVAL, and the arrival is where
  `entry_fan.iter_fan2` starts its fan -- it replays the WHOLE delivered log: **78** frames
  (`n_last`; herd 71 + escape atom 7), NOT the **75** (`n_scored`) at which Tetra freezes. **The banked
  deliverable is 78 + 23 = 101 frames from state 2 to the cut**; a candidate is `arrival + plan_cost`.
- **THE SCREEN, and it is about the CLOUD as much as about her.** `iter_fan2` fans the COURTYARD fleet,
  so Link's walk recoils off her Co cylinder at the full depth -- a placement inside his Co cylinder at
  the arrival is being PUSHED, and the cloud it was scored in is not its cloud. On the exec centre
  (which LEADS his feet by **21.253 u**; feet-based would be wrong by more than the screen):
  **33 of 211** (cost 21) and **11 of 56** (cost 20) fail. The console placement and all 14 pinned s104
  rows read 0.0000, so the screen costs the VERIFIED set nothing -- it trims from the CHEAP end. Only
  the arrival frame needs testing: Link walks +X+Z, AWAY from her; contact returns at the ROLL, wanted.
- **THE PRICE, TWO WAYS, DISAGREEING ON THE RUNG.** Delivered plan: 939.4737 u in 75 f = **12.5263 u/f**
  (96.4% of PUSH_CEILING). Rate price: c21 **93.24**, c20 **93.45**. Trajectory price (project onto the
  delivered plan's own per-frame CURVE, charge the perpendicular miss at LATERAL_RATE 2.92): c21
  **94.63**, c20 **95.04**. **Agree to 0.4 f within ~2.6 u of the curve, diverge up to 14 f at 46 u** --
  so the HEAD of the ranking is trustworthy and the tail is not. Both: the prize is ~**6 frames**.
- **NEGATIVE 1 -- THE DELIVERED HERD CANNOT BE TRUNCATED; the price is QUANTIZED by the roll cycle.**
  Truncate at k, run the ENTIRE 672-variant escape knob grid: **0 fire at every k in 62..70**, 247 at
  **71** (the herd's own end), 323/245/7 at 72/73/74, 0 at 75-76. The escape needs the state the last
  roll's exit leaves. **CONTROL: the k=71 enumeration contains the delivered plan itself -- 0.432 u from
  coord idx 274 at arrival 78.**
- **NEGATIVE 2 -- RE-AIMING THE ESCAPE DOES NOT STEER HER.** Of k=71's 247 firing variants, **62** arrive
  by 78 (<=99 total at cost 21) and give **7 distinct landings**, all ~5 u from the console placement,
  against a nearest live placement **21.169 u** away. Each tested against its OWN re-measured 2-frame
  cloud: all **0 leverage**, `|resid|min` 2.53e-01 vs a ~1e-4 band. Best landing on a live placement over
  EVERY truncation and variant: **6.95 u** (c21, arrival 87 = 108 f) / 17.38 u (c20).
- **DEPTH AND FRAMES SELECT DISJOINT PLACEMENTS.** s104's 14 VERIFIED rows are the DEEPEST, sit **23-48 u
  off** the delivered curve: trajectory price **103.46..115.86 -- not one beats 101**; rate price
  96.70..101.66 (6 of 14 do). Depth is bought with contact, frames with proximity. **A depth ranking is a
  ranking away from the objective** -- re-verify at the frame-minimal head, which is unverified.
- **HARNESS FIX + GOTCHAS.** (a) `entry_fan.base_core` read ``seed['log']`` for the HOLD but always
  REPLAYED `console_seed`'s log, so **every cloud `walk_clouds(seed=)` ever measured was the CONSOLE
  arrival's** -- fixed, inert at the default, 0-ULP gated. (b) **`away_walk.probe` does NOT rank on the
  landing** without a ``thread`` (key = compliance then `d_e_end`), so a negative built on its landing is
  not a negative -- enumerate. (c) **Measure a 2-frame cloud with the 2-frame shape**
  (``base_frames=(0,), j1=(1,), j2max=1``): **~3-6 s** vs MINUTES for `MEASURE_FAN`, bit-identical
  (139213 endpoints / 123.8 u^2).
- **NEXT = THE RETARGETED `chain_herd`**, the only door left, target ~95 frames vs the banked 101. Config:
  `rank='bound'`, `last_rank='bound'`, `handoff=False`, `last_landing=False`, `last_arrive=False` --
  the endgame is tuned to the 288-coord THREAD (`placement_thread` fits a LINE) and a ±170 u cloud breaks
  that fit. Target set = the SCREENED rows of `_generated/s105/price_herd.json`, ranked by `total`.
- Tools NEW: `_notes/s105_{price_herd,truncate_herd,atom_landing,arrival_cloud}.py`.

## Session 106 (2026-08-06) -- THE RETARGETED CHAIN ARRIVES AND STILL LOSES TO THE BANK

The s105 solve ran, three configurations off ONE chain (cycles 1-2 are target-blind -- identical beams
all rounds -- so rounds 2-3 iterated cycle 3 alone off `beam_io.rebuild_beam`, ~27 min not ~65). KB:
new measured section in `knowledge/strategy/herd-price-of-a-placement.md`. The banked 101 STANDS.

- **ROUND 1 (the s105 config exactly: pure `plan_bound`, 116 screened+deduped rows, budget 79).** It
  ARRIVES -- 947.4 u in 75 herd frames, 6 nodes 1.56-1.69 u from rows -- but on the FAR rows (~947 u
  ≈ the console's 939, not the head's 880-900): with `last_arrive=False` nothing prices the ~205 u
  last roll's overshoot and the far rows catch it. A herd endpoint is NOT an arrival -- the atom's
  frames still owe: naive total ~103.
- **THE HONEST SCORER = enumerate the 672-variant atom grid at each endpoint** (s105 `all_variants`
  pattern; `probe`/`escape_probe` rank on the thread FIT -- fiction on a ±170 u 2D cloud). Pareto
  fronts: fast atoms (arrival = herd+2..3) land **5.93-6.32 u** off at totals **98-99**; the only
  inside-band landing (0.299 u) rides a 16-frame atom to **112**. Fast landing ~6x the 1.0 u band.
- **THE RESIDUAL IS A 2D FAN AND ITS LATERAL NEVER GOES BELOW +13.8 u** (along -31..+23, lat
  +13.8..+52 over all 1345 firing variants): the atom ALWAYS pushes her lat-positive, so the herd must
  deliver ~14+ u lat-LOW of a row while the chain's natural last cycle sits at lat +9..+25.
- **ROUNDS 2-3 MEASURED OUT the `aim.handoff_rows` residual shift** (head-15 rows, fast resid
  (12.35, 19.03)): budget 76 drops ALL 33 cycle-3 roll survivors (a hard budget against a
  single-POINT shift of a FAN target = false-negative generator); budget=None fills 8 nodes whose
  landings are WORSE (7.8-33.8 u @99-100) -- the shift steers the rank to badly-converting endpoints.
- **THE FLOOR IS SO FAR THE CUT'S, NOT THE POPULATION'S**: every keep that chose the scored 6-8 of
  the 18-33 roll survivors is landing-blind. NEXT = `_notes/s106_retarget4.py` (READY; killed mid-run
  by a session-wide background-task stop): beam=64, no thread keeps, enumerate ALL survivors. If the
  floor holds, the missing tool is a LAST-CYCLE KEEP RANKED ON THE ENUMERATED CLOUD LANDING
  (`_placement_dist`-style vs rows, not `landing_miss` vs the thread fit) -- a `full_herd` change.
- **HARNESS FIX (in-place):** `extend_cycle`'s stock sort crashed on None-vs-tuple `quality` under
  `require_quality=False` + no escape/glide keep (path never run before); None-safe now, gated by the
  82-test full_herd/herd_price/objective pass. **CHORE DONE BY MEASUREMENT:** 8 tests in
  `tests/test_entry_fan.py` marked `@pytest.mark.slow` (each >90 s solo, one >1 h; per-test
  90 s-timeout classifier) -- default file now 35 passed in 44 s; `test_cross_engine` +
  `test_courtyard_fleet_native` measured FAST (7.9 s) so NO marks (s105's suspicion wrong there).
  GOTCHA: pytest `--collect-only` ids carry `\r` on Windows -- `tr -d '\r'` or rc=4.
- ACCOUNTING GOTCHA: `escape_probe.frames` = herd + freeze_f (the `n_scored` analog), NOT the
  arrival; a candidate total = herd + len(atom log) + plan_cost, off the ENUMERATION only.

**SESSION 107 (2026-08-06): the s106 question is CLOSED IN THE NEGATIVE, and the tool it asked for was
built at the wrong stage -- so it now exists at both.**
- **THE MEASUREMENT (round 4, 2256 s, `_generated/s106/retarget4_landing.json`):** the un-kept cycle-3
  stage gave 36 roll survivors / 30 after dedup+beam, and the 672-variant atom grid was enumerated at
  **all 30**. Only **3 fire**. Population floor at totals <=101 = **8.919 u @99** (node 7, herd 75,
  3-frame atom, row 111 cost 21); the other two firing nodes land 25.342 @102 and 42.900 @104. The
  s106 landing-blind CUT reached **5.933 @99 / 6.317 @98**. So the ~6 u floor was NOT an artifact of
  the cut, and removing `escape_keep` made it WORSE.
- **WHY, DIAGNOSED not counted** (`away_walk.fires_census`, the s77 tool): on all four non-firing
  survivors sampled (0/1/5/12) **`l_ok` refuses ALL 672 variants** (sole-blocker 0 on three of four)
  -- the L would act with Tetra in the front cone, which `snap_reach` already showed the camera
  channel cannot buy. 27 of 30 are structurally escape-LESS, not a knob away.
- **THE GENERAL LESSON (worth more than the number):** `escape_keep`'s contribution was never its
  rank -- probing the escape at all FILTERS to endpoints that can escape, and a fiction rank rides on
  a real filter. Before replacing a proxy-ranked keep, ask what its probe was filtering as a side
  effect.
- **THE STRUCTURAL HALF:** `extend_cycle` cuts junction -> aim/camera -> ENDPOINT, and on the last
  cycle nothing follows the endpoint -- so an endpoint keep, however honestly ranked, only REORDERS a
  set the upstream cuts fixed. That is why the floor had no keep-shaped fix.
- **DELIVERED `harness/tetrapush/cloud_land.py`** (new single-topic module, gate
  `tests/test_cloud_land.py` 17, KB `knowledge/strategy/landing-keep-on-a-cloud.md`): `cloud_landing`
  = the enumeration priced as WHOLE candidates (herd + atom LOG + row `plan_cost` + miss at
  PUSH_CEILING; `in_band` reported SEPARATELY from the rank), ~28 s -- the CLAIM. `residual_fan` +
  `predict_bound` = the residual as the SET s106 measured (lat never < +13.8) crossed with the rows,
  microseconds/aim -- the CUT, wired `roll_probe(fan=, rows=)` -> `cloud_bound` and
  `extend_cycle(cloud_fan=)`; optimistic, so Newton it via the enumeration before quoting.
  `extend_cycle(cloud_keep=, cloud_cap=)` is the endpoint form; the cap PRINTS what it skipped.
  Also `herd_rows`: the RAW `seeds.load_placements` rows carry only idx/x/z (no along/lat/plan_cost)
  and would have crashed the predictor.
- **BOTH HALVES POINT UPSTREAM:** the last cycle is exhausted (90% escape-less pool, 6-9 u either
  way). The lever is the **target-blind CYCLE-2 beam** every round since s106 has iterated off -- a
  ~65-min full re-chain, not a cycle-3 iteration.
- **NEXT = `_notes/s107_fan_cut.py`** (ready): fan measured at round 4's survivors -> per-aim cut ->
  enumeration at the survivors, printing the proxy's error per node. **Read `n_firing` as the primary
  result**, since the per-aim cut now has two jobs (keep firing endpoints AND rank the landing).
- **THREE HARNESS TRAPS, all now in the README `## Tooling`:** (1) `nohup ... &` from a tool-call
  shell dies with the call's process group while LOOKING alive -- use PowerShell `Start-Process
  ... -PassThru` and watch the PID; (2) never reuse a log path across relaunches (a killed writer's
  bytes + NUL padding make an EARLIER run's lines sit adjacent to a later run's -- two per-node
  "probing N of M" lines from different nodes read as nondeterminism; it was not); (3) **never edit a
  `.py` while pytest is live** -- this repo's wiring gates assert on `inspect.getsource`, which
  resolves by file+first-line, so a line-shifting edit returns an unrelated fragment (cost: five
  phantom failures and a 21-min re-run). Always `-u`.
- **THE FAN'S SIGN IS BAND-LOCAL (s107, found while validating the s107 driver).** Measured at round
  4's two firing survivors the residual fan spans lat **-74.5..-1.9** (along +14.7..+72.3, 110
  members, 40 s); s106 measured **+13.8..+52** at ITS endpoints -- same herd line, same code, OPPOSITE
  SIGN. So s106's "the atom always pushes her lat-positive, so the herd must deliver ~14 u lat-LOW of
  a row" is a band-local instruction and is backwards on the other band. Mechanism: the residual's
  lateral tracks Link's offset from her at -0.53 u/u (`away_walk.probe`), so which side of her a
  family of endpoints sits on flips the whole fan. NEVER cache a fan or carry one across states;
  `residual_fan` takes its endpoints as an argument for exactly this reason. (s106 KB claim scoped in
  place, not deprecated -- the measurement stands for its band.)

**SESSION 108 (2026-08-06): the re-chain with a TARGET-AWARE CYCLE 2 crossed the band -- a candidate
that BEATS the banked 101 is in hand, offline-confirmed: TOTAL 100 (73 herd + 6-frame atom + row 105
plan_cost 21), landing 0.7886909226025417 u from row 105, in-band, wall +12.07 u, talk-safe, in
regime, deterministic bit-exact from state 2.**
- **THE FAN-CUT RAN FIRST (the s107 default) and closed its question: the last cycle WAS exhausted
  over the old beam.** Fix first: the driver took the first-3 round-4 survivors as fan sources --
  escape-less; the fan MUST be measured at FIRING endpoints (nodes 7/18/25 per the landing dump's
  census; 178 members, lat -74.5..+4.7). Result: 6/30 fire (vs 3/30), floor 8.919 u @99 UNCHANGED
  (same endpoint), proxy error -0.51..+1.25 f (0.00 on the floor node).
- **THE RE-CHAIN (`_notes/s107_rechain.py`, 2578 s): cycle 2 landing-aware (`extend_cycle(cloud_fan=)`
  per-aim + endpoint beam 16 vs the reused 8) -> fan-cut cycle 3 verbatim -> enumeration at all 54
  survivors.** 16 cycle-2 nodes (corridor offsets down to 0.1), 54 cycle-3 survivors, **19 fire**
  (vs 3/30, 6/30), and the front crossed: node 11 (herd 73) = 2.224 u @99 / **0.801 u @100**; node 40
  2.58 @100, node 23 4.54 @99. The lever was exactly where both s107 halves pointed: the beam that
  decides which entry geometries cycle 3 sees. Dumps `_generated/s106/s107_rechain_*.json`.
- **CONFIRMED (`_notes/s107_confirm_winner.py`): quote the WIRED replay, not the detached
  enumeration.** `_clone_for_atom` detaches the camera; on this MID-CHASE arrival (csangle
  36254->36375 over the atom) wired-vs-detached moves TETRA's landing 0.026 u -- a band edge (here
  favorable, 0.801->0.789). The docstring's "Tetra is bit-identical" was the SHIPPED plan's number,
  not a law -- scope-corrected in place (`away_walk.py`). Rank detached; QUOTE wired. Full 79-frame
  log replays deterministic (`confirm_plan` ok), atom fires clauses re-measured wired (l_ok True,
  freeze/rec17 f6, no dips). Winner package = `_generated/s106/s107_winner.json` (full log + knobs).
- **NEXT = THE DELIVERY TIER (the claim is offline; the console owes the number):** 2-frame cloud
  from THIS arrival (`_notes/s105_arrival_cloud.py` pattern) -> `entry_search.confirm_entry` ->
  `cross_engine` -> boot-movie splice (`[[tetrapush-dtm-delivery]]`), gating console total <=100 vs
  the banked 101. Iterate more landings off `s107_rechain_c2_beam.json` (16 nodes), NOT off
  `retarget2_beams.json` (measured exhausted: 4 rounds + the fan-cut).
- Gates: touched-area 90 passed (away_walk + plan_console + cloud_land + KB guards). Library
  untouched; only tracked-code edit is the docstring scope correction.

**SESSION 109 (2026-08-06): THE DELIVERY TIER KILLED THE s107 WINNER AT ITS FIRST GATE, and the
finding is the predicate: DELIVERY IS TWO PREDICATES -- dust needs the LANDING on the razor band,
leverage needs the ARRIVAL hull at the stations ~130-165 u UP-HERD -- and `in_band`/`plan_cost`
answer only the landing half (a row's cost was PRICED at the console arrival; quoting it for a plan
that arrives elsewhere is the s104 gotcha one level up).** The banked 101 STANDS; the offline 100 is
a landing-half number. KB: NEW `knowledge/strategy/delivery-is-two-predicates.md`.
- **The diagnostic split (`_notes/s109_control_diag.py`, reuse it):** control = hunt tetra + console
  hulls -> 4 live (scan sound); winner landing + console hulls -> 1 live (0.789 u miss is fine);
  hunt tetra + WINNER hulls -> **0 leverage**. Killer = Link's arrival, 128.2 u from the nearest
  hunted station (console: 25.0 u). `hull_scan` counters split the halves: `n_leverage==0` = the
  arrival refusing; leverage-without-live = the landing refusing.
- **The census (all 8581 firing atoms at all 24 firing survivors):** (miss, d_station) front is a
  hard exchange -- miss<1 only @ d_st~127 (node 11); d_st<10 only @ miss~25 (nodes 4/5, totals
  97-99). No joint variant; both halves are set by where the HERD ends.
- **The scans (20 near-arrival candidates, own cloud + 45 cells x 3 thrusts): 0 live.** Two legible
  failure shapes: mid-backslide arrival -> EMPTY cloud (`iter_fan2` junctions need speedF==cap 17);
  settled arrival AT the stations with landing 24-40 u off-band -> leverage 135/135 combos, dust 0.
- **The console pays both, and says how:** its herd ends flip-flying (f71 speedF -25.7), Tetra
  COASTS ~36 u on plow momentum through the atom window, Link runs up-herd at cap 17 to 111 u
  behind her / 25 u from the station, arriving WALKING AT THE CAP. Post-freeze exit-run frames move
  the arrival and nothing else (she is frozen) -- the atom tail and the entry walk are one currency.
- **NEXT = the JOINT last-cycle keep:** price d_station beside miss in `cloud_land`, iterate cycle 3
  off `s107_rechain_c2_beam.json` toward the console geometry (disengage early, coast, run). The
  node-4/5 family (herd 68-69, arrival already AT the stations, landing ~26 u ~= 2 push frames
  short) is the concrete probe; honest gate stays per-candidate cloud + hull_scan (~30 s).
- Drivers `_notes/s109_{winner_cloud,control_diag,arrival_census,arrival_rank,scan_best}.py`; dumps
  `_generated/s106/s109_*.json`. Gates: KB guards + cloud_land + away_walk 42 passed. No tracked
  code changed (README box + KB page + hub only).

**SESSION 110 (2026-08-06): THE ARRIVAL WAS NEVER FIXED -- THE ATOM'S BREAK CONDITION WAS. The tail
breaks s109's "hard" front, it costs exactly what it buys, and the ARRIVAL HALF IS NOW SOLVED (first
leverage ever from a non-console arrival).** The banked 101 still stands.
- **THE TAIL** (`escape_atom(exit_run=)` + `tail_variant`, tracked+gated): `escape_atom` broke the
  frame it recedes at the cap AND separates -- right for the LANDING, and it silently answered the
  ARRIVAL with whatever the last frame held, so **every arrival ever enumerated was one shape** (Link
  beside her, deep, often still flying backwards at -23). Hold the exit stick past the handoff and
  past `freeze_f` the frames move the arrival and NOTHING else: her coord is **bit-identical (0 ULP)**
  while the separation holds, `fires` refuses the frame it breaks, and the 230 u follow bar ends the
  rollout. `tail_variant` reads every tail length off ONE rollout (bit-exact vs fresh) -- 672 rollouts
  -> 4700 priced variants for +1 s.
- **TWO LAWS.** (1) An UNSETTLED arrival fans an EMPTY cloud (`iter_fan2` junctions need
  `speedF == WALK_CAP`); the banked `shallow` hands off at **-23.217** and 2 tail frames settle it at
  17.0. (2) **The joint bound is TAIL-INVARIANT** (24/24 endpoints, to the digit) because the station
  gap is priced at the walk cap == what a tail frame delivers. That invariance is the sign the term is
  HONEST; the tail buys DELIVERABILITY, not frames.
- **THE JOINT KEEP** (`cloud_land`: `station_map` (refuses a dump hunted at another walk budget),
  `arrival_frames` (= `remaining_frames`' twin, gap past `FREE_REACH`=34 u at the cap), `_joint_row`
  (the row CHOICE moves), `atom_cloud(exit_runs=, exit_bearings=)`, `exit_arc`, and ``joint`` = in-band
  AND arrival paid AND settled). Wired `extend_cycle(cloud_stations=, cloud_exit_runs=)`.
- **THE EXIT ARC WAS THE MISSING KNOB.** The grid only ever held 2 exit bearings; sweeping an 18-wide
  arc at node 11 turned its best fully-paid landing from **1.881 -> 0.8008 u** and produced the FIRST
  **14 JOINT records** -- the predicate IS satisfiable (totals 106-108 vs the bank's 101).
- **THE SCAN (the claim, not the bound): 6 of 8 JOINT candidates read LEVERAGE** -- 15-45 cell/thrust
  combos, up to 1760 grid hits -- where EVERY s109 scan read `n_leverage == 0`. Leverage is MONOTONE in
  the tail (tail 3: 0 combos, tail 4: 18-25, tail 5: 45). Best razor residual **3.1e-3** vs s109's
  3.3e-1 and live dust at 8e-5..7e-4. **0 live: the ARRIVAL half is solved and the LANDING is the whole
  remaining gap** -- and it is a razor-precision problem now, not a band one (0.80 u from row 105 is a
  DIFFERENT placement; `PLACEMENT_BAND`=1.0 is a proxy the dust ribbon does not honour).
- GOTCHA: `arr_frames == 0` is a RADIUS and the hull is a FAN -- two tail-3 candidates at d_st 23.5-24.0
  read 0 leverage while tail-4/5 ones at 19-33 read plenty. Direction, not distance.
- KB: NEW `knowledge/strategy/the-arrival-is-payable.md`; `delivery-is-two-predicates.md` scoped in
  place (its front is the one the break condition allowed). Drivers `_notes/s110_{joint_census,
  rechain_c3,scan_c3,refine_arc,scan_arc}.py`. Gates: 182 passed (away_walk +5, cloud_land +10).
- **THE CYCLE-3 ITERATION WITH THE JOINT KEEP (2324 s, 96 probed / 54 beamed) REPRODUCES THE SAME
  POPULATION BOUND FOR BOUND** (93.95 / 94.08 / 95.41 / 102.53 / 102.96; its node 3 IS the old node 11
  at 0.801 u @100). Clean negative, and it CONFIRMS s107's structural finding: an ENDPOINT keep
  reorders a set the upstream cuts fixed, it cannot create a joint-payable endpoint. It also reports
  "0 pay both" at the very endpoint where the ARC found 14, since `extend_cycle`'s keep runs the
  standing two exit bearings. **So the arrival term AND the arc belong in the per-aim CUT
  (`roll_probe`'s `cloud_bound` / `predict_bound`): give `residual_fan` members Link's own world
  displacement (link_dx/link_dz) and price `arrival_frames` per row there.** Commit 6ada24e.

---

## Session 111 (2026-08-07) -- the escape has no authority; the landing is the endpoint's

- **THE ATOM IS NOT A STEERING CHANNEL** (`_notes/s111_atom_reach.py`): both bearing arcs at FULL
  circle x 4 rotates x turnaround x side x tails 0-6, ~115k variants an endpoint. Reachable landing is
  a blob fixed by the endpoint. **Herd 68 is out of REACH** (node 2 tops out at along 862; rows start
  at 880). Herd 69 spans lat -30..-124 against a cloud floor of -19.9 at every along band.
- **THE LAW**: forced displacement = the plow's half-depth ejection `(CO_RADII_BAR - centre_feet)/2`
  on frame 1 + as much again per closing frame. Measured floor vs law: node 7 (cf 62.5) 9.02 v 8.74;
  ratio ~1.0 at `rec` -8..-12 rising to **2.3-3.2** at -25. DIRECTION = Link's lateral offset from her.
- **THE CAUSAL CONFIRMATION** (`_notes/s111_offset_curve.py`, relocate ONLY Link at node 4): miss
  **36.7 -> 25.4 (native +17.49) -> 7.0 -> 1.755 u** as the offset runs +42.5 -> +17.5 -> +2.5 -> -7.5,
  with `res_lat` collapsing to -1.16 and the landing reaching row 26 (cost 20) at total 96. Monotone.
  Relocation bed (anim/momentum do not move with position) -- a causal probe, not a candidate.
- **THE MAGNITUDE AXIS AND THE NO-CONVERT DEPARTURE, both new, both closed** (`s111_{hold_atom,hold2}.py`,
  all 54 nodes). msd 0.0-1.0 moves the forced push <0.1 u. The hold fires in 2-3 frames (recipe 4) and
  fires where the recipe fires NOTHING (nodes 6/8: 0 firing over the whole full-circle recipe grid) but
  **never settles inside 16 frames** -> empty entry cloud -> not a plan.
- **s110's LEVERAGE WAS ALL THRUST 13.** `hull_scan` sweeps THRUSTS (13,14,15) and s109/s110 pooled
  them: **all 173** leverage combos at the joint candidates are 13, **0** at 14/15. Control (console's
  own placement, its own 4-frame walk): leverage 45/45/45, walkable dust **0/9/18**; hunted rows at 2
  frames 0/5/4, 0/2/1, 0/0/4. So s109's verdict stands and the razor residual 3.3e-1 -> 3.1e-3 is a
  thrust-13 number. NEVER pool over THRUSTS.
- **DETACH TRAP**: `_clone_for_atom` detaches the camera; a wired replay drifts 121-654 BAM, moving
  Tetra 0.008-0.080 u and Link 0.75-2.00 u. `_notes/s111_scan_landing.py` now takes the replay as truth,
  records `hull_scan`'s `reason`/`drops`, and splits leverage per thrust.
- **FRAME IDENTITY**: `herd + atom + plan_frames + thrust + 4`; thrust floor 14 (13 refused);
  the recipe atom's shortest SETTLED log is **4**. Beam floors: 93 (node 4, herd 69), 93-94 (nodes 2/5)
  -- the frames are there, only the landing is not. `plan_frames`=1 (cost 19) probed: the 1-frame hull
  is real (41643 endpoints) but carries no live station for any cost-20 row -- it needs its own HUNT.
- **NEXT**: the endpoint SPECIFICATION belongs in the per-aim cut -- `roll_probe` already collects
  `link_lat`; give it `centre_feet` and `rec` and run 1-2 real departures per surviving roll instead of
  `predict_bound`'s static fan (whose minimum along-push is +14.7 where the real one is -1.0, and which
  cannot see the offset at all). `budget=` on a last-cycle `extend_cycle` empties it (s106 r2, and again
  at 78 -> 0 survivors); pass None. Re-cut running at handoff: `_notes/s111g_recut_full.log`.

---

## Session 112 (2026-08-07) -- the landing reaches 95; the gap is two frames of ARRIVAL

- **THE s111 RE-CUT FINISHED AFTER ITS HANDOFF WAS WRITTEN AND IS A CLEAN NEGATIVE** (3360 s, 153 roll
  survivors -> 64 beamed, 57 unenumerated under the 96 cloud cap): frame-minimal nodes still at offset
  +13.9/+16.1/+17.5 (miss 25-40 u, totals 91-93), only both-halves node = node 11 (herd 73) at **105**.
- **BUT ITS BEAM DOES CONTAIN THE ON-LINE ENDPOINTS s111 SPECIFIED** -- twelve at herd 69-74, offsets
  -6.04..+9.63 -- and **four FIRE while eight do not, with the split NOT following the offset**: node 7
  (offset -0.54) fires **1568/4654** at the standing pair and 17220 at a 90 deg arc, node 32 (offset
  -0.13, 0.2 u away in along) fires **zero**. So the refusal is STATE-SPECIFIC, not a property of being
  on-line. `fires_census` with its positive control: converting endpoints (7, and node 0 at 2828/26801)
  fail only `dips`, NEVER `l_ok`; refusers 36/32/33/40 fail everything at once (**sole: none**) and
  43/45/35 have **108 / 173 / 97 variants failing ONLY `l_ok`** -- the PREVIOUS ROLL'S CAMERA (s77).
  The on-line endpoint the cut DOES admit fails downstream instead: node 7 is at lat -48, 25 u below
  the cloud, landing 18.9 u out at total 97. "The cut never asked for on-line endpoints" was WRONG, and
  so is "on-line endpoints refuse".
- **STRAIGHT AND SHORT ARE THE SAME KNOB.** At c3 node 0 the miss collapses 25.400 -> **2.016 u** from
  offset +17.49 to -7.51 (residual lateral tracking at the documented -0.53 u/u) while the atom's LOG
  grows **3 -> 7** frames (6 at a wide arc). The atom ends when the actors SEPARATE and an on-line Link
  keeps closing, so the s111 specification buys the landing in the currency the objective is saving.
- **THE STATIONS ARE ACROSS THE LINE.** All **268** stations over 116 rows: along **804.70-818.69**,
  lat **+12.12..+35.46**; the six cost-20 rows sit 73-137 u down-line and 31-46 u across. Over the 21
  firing c3 nodes `arrival_frames` <= 1.03 only at offsets **-4.1..+17.5** and **0.00** only at
  **+13.9..+17.5**. The landing wants -7.5, the free arrival wants +14..+17: ONE VARIABLE, TWO MASTERS.
- **A RELOCATION BED MUST CHARGE FOR THE ALONG AXIS** (worth up to 5 frames). The search's
  along-per-herd-frame caps hard at **12.8177 u/f** (top six of 64 nodes inside 0.006; 98.6% of
  PUSH_CEILING 13.0). Node 0: +43.6 u free, then 0.078 f/u. Now in `herd-price-of-a-placement.md`.
- **AND WITH IT PRICED, THE LANDING HALF HITS THE BAR.** c3 node 4 relocated to offset +6.83, 40900
  variants x an 18-bearing arc: a **SETTLED 6-frame atom lands 0.083 u from row 74 (cost 20) at TOTAL
  95**. NOT deliverable: Link is **99.9 u** from the station at frame 6; atom 8 = 0.311 u / d_st 25.2 /
  **97 PAID**; atom 9-12 = 0.042 u, d_st 33.7/17.5/7.4/19.5. The atom throws him OUT and the tail
  curves him back -- at the herd endpoint he was already ~32 u away. So **the arrival is decided by
  where the ATOM leaves him, not the herd**.
- **ALL THREE SURFACES FINISHED AND THE PAID FLOOR IS THE SAME NUMBER AT EACH.** node 1 (herd **68**)
  in-band **94.00** @ 0.685 u (atom 5) / paid **97.00** @ 0.685 u (atom 8) -- the **SAME CELL** (offset
  -13.06, along 868.0) differing only in the atom log, so **three tail frames is the entire distance
  from bar to floor**; node 4 95.00 / 96.27; node 0 96.00 / 97.00. Node 1 also carries the best bound
  anywhere: **93.00** at 5.994 u with **d_st 35.4** -- 1.4 u over FREE_REACH at a 5-frame atom, the
  closest a short atom has come to a free arrival.
- **SCOPE `exit_arc` BY LINK'S LATERAL, DO NOT JUST WIDEN.** From a DEEP straight-push endpoint (Link
  lat ~-27) the station bears ~90 deg off both centres, so s110's `half=0x2000` cannot face it (d_st
  59.8 -> 73.9 -> 88.2 -> 103.1 over tails 0-3, first under 34 at atom 15; at 0x4000, **17.6 at atom
  12**). At node 4's shallower posture the winner sits **9.8 deg** from its centre and widening buys
  nothing. The arc moves the LANDING floor only 2.401 -> 2.047 u -- it is an ARRIVAL knob.
- GOTCHA: `cloud_landing`'s `in_band` does NOT require `settled` (only `joint` does), so an in-band
  total read off it can be an unsettled arrival, which fans an empty entry cloud (s110).
- GOTCHA: **quote a `nofire` against a positive control** -- two of the nine probed endpoints fire in
  the thousands, and without them "0 of 3476" reads as a law it is not (the rule that killed s110).
- **NEXT = rank a placement sweep on `d_station` AT ATOM <= 6**, which no cut has ever ranked on (the
  landing comes free at 0.04-0.69 u across a wide band). **START AT NODE 1 (herd 68), not node 4** --
  best bound anywhere and d_st 35.4 at atom 5. Beside it: (1) `l_ok` is the sole blocker on 97-173
  variants at three refusers -> `snap_reach`/`derived_target_css`; (2) `plan_frames`=1 (cost 19) still
  has no hunt and buys one frame everywhere.
- Drivers `_notes/s112_{offset_c3,place_curve,atom_front,honest_surface,nofire_probe}.py`; dumps
  `_generated/s106/s112_*.json`. Gates: KB+code hygiene 10 passed. Commits **2ea4015 / b844305 / 95941dc** (KB page
  `knowledge/strategy/the-offset-cannot-pay-both.md` + hub + herd-price + README box).

## Session 113 (2026-08-07) -- the short atom is a POINT; both halves solved, never together

- **THE s112 NEXT STEP, RUN: rank on `d_station` at atom <= 6** (`_notes/s113_arrival_surface.py`, 90
  cells at node 1). **The arrival is NOT the scarce half**: floor ``d_station`` **4.8 u** (inside
  FREE_REACH 34) at a **5-frame** atom, total 94.00 -- its landing 35.9 u out. The LANDING floor is
  **0.685 u** in band, also atom 5, total 94.00 -- its arrival 58.2 u. **NO CELL PAYS BOTH**, in none of
  the **170** cells across all three relocation axes. The two floors sit **40 u apart** down the line.
- **WHY -- THE ARRIVAL SET AT ATOM <= 7 IS A POINT** (`_notes/s113_arrival_front.py`, two endpoints 45 u
  apart). Extent of Link's end positions by log length: **1.1 x 1.1 u at atom 5 over FORTY knob
  combinations** (2.0 x 12.6 at the 2nd), 4x4 at 6, ~9x6 at 7, then **111 x 94 u at atom 8** -- 2-3
  orders of area in ONE frame, at both endpoints. Frame 8 is where the blob first CONTAINS the station
  cluster = where `arrival_frames` first reads 0 = the banked 97. Cause: `escape_atom` is 4-5 PRESCRIBED
  inputs then ~25.7 u/f of flip momentum one stick cannot turn.
- **THE THROW IS RIGID AND POINTS OUT OF THE STATION BAND.** Link does NOT have to travel to the
  stations -- at node 1's 94/97 cell he stands at along **808.58**, INSIDE their band (804.7-818.7),
  gap essentially pure LATERAL. The 5-frame atom fixes the lateral (resid +3.18) and BREAKS the along,
  throwing him to 862.5, **43.8 u past**. Displacement **(+53.9,+60.8)** and **(+60.1,+62.9)** = an
  81-87 u throw at ~47 deg. The 3 tail frames from 94 to 97 are that EXCURSION, not a journey.
- **`exit_arc` IS WORTH EXACTLY ZERO AT ATOM <= 6.** Standing pair vs a 34-bearing +-90 arc: 1242 ->
  **21114** and 1248 -> 21216 variants, arrival floor 43.9/46.9 and landing 0.685@73.3 / 1.160@63.5 --
  **IDENTICAL TO THE LAST DIGIT**. Control: s112 moved d_st 59.8 -> 17.6 with the same arc at atom
  12-15. It is a LONG-atom knob. **Do not spend rollouts on it short.**
- **NEW THIRD RELOCATION AXIS = THE SEPARATION** (`_notes/s113_sep_curve.py`, `sep_shifted`: Link alone
  ALONG the line; offset and placement beds both hold it invariant). 80 priced cells. **`CO_RADII_BAR`
  80 is NOT a firing bar** -- the atom fires at ``centre_feet`` **160** -- it only stops the PUSH, which
  makes the landing the herd's problem alone and drives it to **0.163 u from row 26**. Takes the arrival
  floor 43.9 -> **2.6 u** and the joint BOUND from s112's paid 97.00 to **96.00** (da +58/sep -80: in
  band, total 95.12, d_st 48.9). Still never PAYS -- ``near`` and ``near_band`` stay 30-45 u apart.
- **`plan_frames`=1 (cost 19) RETIRED BY ARITHMETIC, no hunt.** `FREE_REACH` = `WALK_CAP*WALK_FRAMES` is
  DERIVED from the hunt's own budget, so cost 19 credits 17 u not 34 and the bound moves by
  ``min(1, max(0,34-d_st)/17)``: a frame only inside 17 u, **exactly 0** past 34. At d_st 58.2 both
  score 21.424.
- GOTCHA: **s112's ``short`` is NOT the arrival floor** -- it keeps the min-LANDING variant and reports
  its passenger d_station: **73.3 against the cell's own 43.9**.
- **NEXT = SOLVE the endpoint, do not sweep 2D slices.** The map is rigid, so the two predicates are two
  2D conditions on a 4D endpoint space (Tetra along/lat, Link along/lat) -> a root-find. **Tetra's
  LATERAL has never been moved by ANY bed** and it is what selects which row (rows span lat
  -33.7..+1.6). Pick the arrival first (Link at ``station-throw`` ~ (753,-42), already reached at near
  2.6), then solve Tetra's (along,lat) for a cost-20 row under that endpoint's real push, and Newton it.
  Beside it: (1) `l_ok` camera supply (s112 item 1, untouched); (2) re-run the arrival surface at nodes
  0 and 4 -- everything here is node 1 only.
- KB `knowledge/strategy/the-short-atom-is-a-point.md` (NEW) + hub; `plan-cost-walk-budget.md` gains the
  derived-credit section. Gates: KB+code hygiene 10 passed. Commit **4dcfc0a**.

---

## Session 114 (2026-08-07) -- the basis was a dimension short; the fourth coordinate pays both

- **THE THREE BEDS SPAN THREE OF FOUR COORDINATES.** An endpoint is Tetra's (along, lat) + Link's
  (along, lat); OFFSET moves Link's lat, PLACEMENT both alongs, SEPARATION Link's along -- and **all
  three hold TETRA'S LATERAL where the node was born**, while priced rows span lat **-33.68..+1.61**.
  So s113's "no cell pays both in 170 cells" was about the SLICE. New 4th bed `tlat_shifted` + `placed`
  (absolute herd coords, all four composed); `basis_check` leak **4.6e-05 u**.
- **AND THE FOURTH COORDINATE PAYS BOTH HALVES** (`_notes/s114_endpoint_solve.py` + independent
  re-verify `_notes/s114_verify_winner.py`, dump `s114_winner.json`). c3 node 0, herd 69, row 9 (cost
  20): endpoint **Link (712.5708, -25.9759) / Tetra (882.4369, -13.5871)**, landing **0.000056 u** in
  the 1.0 band, arrival **7.7252 u** inside FREE_REACH 34 (arr_frames 0.00), 6-frame firing settled
  atom, all five `fires` clauses PASS, cs_bill 0, **TOTAL 95.00** (herd 69 + 0 along + atom 6 + 20).
  Needed **Tetra's lat +6.10 from native**. FIRST endpoint ever to pay both at once.
- **THE MECHANISM IS A DECOUPLING** -- ``centre_feet`` **160.25**, 2x CO_RADII_BAR, so Tetra takes NO
  push and her end IS her start verbatim: the landing becomes her PLACEMENT and the arrival Link's
  alone, i.e. **two independent 2D problems instead of one coupled 4D one**. s113's `sep_curve` reached
  that regime (cf 159.8, landing 0.163 u) and could not use it -- with her lateral pinned it could only
  land her where that one line passed a row.
- **RIGIDITY = ARITHMETIC** (`_notes/s114_throw_map.py`, throw per VARIANT per node): `link_end = start
  + throw` -> **Link's start is ``station - throw``**; past the bar **Tetra's start is the row**.
  Nothing searched; totals as low as **93.00** fall out.
- **A FROZEN-KNOB FD NEWTON STALLS AT ITERATE 0** -- ``len(log) = handoff_f + exit_run`` and
  ``handoff_f`` is set by CO_RADII_BAR + the recession test, **step functions in POSITION**, so a
  relocated n=4 combo runs to n=6 and the quotient measures the jump. FIXES (both generalise):
  re-select the best GRID MEMBER each iterate (rigidity licenses it), and iterate on the objective's
  **ACCEPTANCE** not the equation (landing owes the band, arrival owes only FREE_REACH) -- accepts at
  iterate 2 what grinding refuses at 6.
- **THE SEPARATION IS NOW PRICED (new 4th herd-price axis) AND THE CHARGE IS SMALL.** Full beam (707 s,
  all 64 nodes; **29** hold a firing settled atom at n<=6): over all **1160** specs the required
  separation runs **92.5..156.8 u**, while every beam node sits **38.09..75.25 u** (mean 53.83), **zero
  >= 100** -- a CUT observation (beam ranked on `junction_quality`, never on separation; s107 lesson).
  Rate = Link's endpoint speed, cap **25.727 u/f** (speedF -25.727..+18.500, all MOVE; a +18.5 node is
  CLOSING). **THE CLOSEST SPEC IS ONLY 7.5 u PAST THE LIVE 41-85 BAND** -- node 8 / row 9 / atom 6 /
  **total 96.00** at sep 92.5 = **0.67 f** from the beam's widest -> ~**96.7** honest (arithmetic spec,
  unsolved). Node 0's SOLVED 95.00 needs 169.87 u = **3.68 f** -> ~98.7. Both beat banked 101, STANDS.
  Throw's along is POSITIVE at all 66 (node,length) classes: **+55.01..+113.42 u** (lat -44.52..+59.63).
- **THE ROW-STATION ALONG GAP HAS A HARD FLOOR OF 72.29 u** over all **268** priced pairs (mean 115.37;
  floor row 0 cost 21, row 9's cost-20 pair 0.8 u behind at 73.09). Stations along 804.70-818.69, rows
  879.92-979.86 -> **Link must end >= 72 u up-line because that is where the two target sets ARE**. No
  cheaper pairing at either cost. Required sep = ``gap + throw_along - push_along``.
- **`turnaround_first` DOES NOT REVERSE THE THROW -- IT ENLARGES IT**: node 0 +54.82..+81.11 ->
  **+74.43..+90.82**; node 13 +61.79..+92.76 -> +83.12..+99.68 (node 1's non-ta branch fires NOTHING,
  all 1059 fail `l_ok`). The conversion negates an up-line backslide into down-line flight, so the
  displacement points AT Tetra by construction.
- **s113's "POINT" IS POSTURE-DEPENDENT**: at nodes' own postures the extent runs **0.05 x 0.36 u**
  (node 13 atom 4, 24 variants) to **14.87 x 47.77 u** (node 6 atom 5, 202), tracking `fires` survivors.
- GOTCHA: a backgrounded `nohup ... &` inside a Bash tool call **does not survive the shell** (first
  full-beam throw map died at node 22, truncated, no summary). Use the tool's background mode.
- **NEXT = RE-CUT THE HERD AIMED AT THE SEPARATION** -- the only unpaid term. Add it to the last
  cycle's keep (`full_herd.extend_cycle`/`roll_probe`, beside the `link_lat` already collected) and
  price at 25.727 u/f so a deep-separation endpoint is not ranked out for the frames it spends. `fires`
  is NOT the obstacle (winner at cf 160.25, 6/690 fire). Beside it: re-launch the 8-node
  `s114_endpoint_solve` (STOPPED at 8 of ~192 solves, ~150 s each -- where a sub-95 would show up; node
  0's n=4 class says 93.00 but **fires nothing** relocated), and `l_ok` (s112 item 1, still untouched).
- KB `knowledge/strategy/the-endpoint-is-four-numbers.md` (NEW) + hub; `the-short-atom-is-a-point.md`
  gains forward links + the posture scope. Gates: KB+code hygiene 10 passed.

---

## Session 115 (2026-08-07) -- the separation is not a suffix; `l_ok` is the beam's real blocker

- **RAN THE SEPARATION'S FRAMES, WHICH NO SESSION HAD** (`_notes/s115_recede.py`; prologue swept as a
  GRID -- 16 bearings x msd 0.06/0.2/0.5/1.0 x k=0..8 at all 64 nodes -- because the named-stick pass
  before it mis-measured the rate). Depth IS deliverable: **+8.3..+10.6 u/f** sustained (NOT s114's
  25.727 -- at the endpoint Link is still CLOSING at ~+12 u/f along, so the cap is a direction he is
  not travelling in); node 8 sep **58.52 -> 129.88 u** in 8 frames; **Tetra freezes at k=2-3**, measured
  from her own displacement, never inferred from `CO_RADII_BAR` (``centre_feet`` oscillates with the pose).
- **AND EVERY UNIT IS PAID OUT OF THE ATOM: 0 of 672 fire** at every deep pick (nodes 0/1/8) against the
  same endpoints' controls at **56/720, 1888/2640, 1964/4038**. `fires_census`: ``l_ok`` fails **672/672**,
  SOLE on all 672 at node 0's momentum-preserving pick.
- **MECHANISM, MEASURED END TO END -- SEPARATION, MOMENTUM AND FACING ARE ONE RESOURCE.** Turning Link
  costs the EBS (**-25.45 -> -11.43**); `reposition.turnaround` requires the EBS PRESERVED
  (`_SNAP_KEEP_SPEED` -24.5) so `snap_csangle` is **None at every receded endpoint** where every control
  has a window (34816/34304/31232); the atom's own first frame then turns him in (**cone +3.51 ->
  -37.64 deg**, -71 by the L frame) and ``turnaround_first=True`` changes nothing (identical facing 25265).
  **So the separation is HERD-SHAPED: only the last roll can deliver depth AND leave the posture intact.**
- **s114's 0.67-3.68-frame price is RETIRED** -> `knowledge/history/separation-priced-at-the-endpoint-speed.md`.
  Lesson: **a price is not a price until the frames have been run** -- units-owed/units-per-frame is a
  claim about a DISPLACEMENT; a frame cost is a claim about a reachable STATE, and they differ whenever
  the frames that buy the displacement spend something a later stage needs. Its next step SURVIVES for a
  better reason.
- **THE BEAM PRICED BY ENUMERATION FOR THE FIRST TIME** (64 nodes, 23 min): **29 fire**; the two floors
  sit on **DISJOINT** nodes -- arrival free at **2** (landings 25.40-40.02 u), in-band landing at **3**
  (arrivals owe 7.38-8.37 f), **``joint`` 0**. Best bound anywhere node 0 **93.95** (total 92.00) -- a
  BOUND, not a delivery; banked **101 STANDS**. Correlation only **-0.089** (the first FIVE nodes read
  -0.866: never quote a correlation off five points).
- **`l_ok` IS THE #1 BLOCKER, NOT THE SEPARATION**: SOLE clause on **7349 variants (63%)** vs ``dips``
  4117 (35%), and the sole blocker at **19 of the 35 nodes that fire NOTHING**. That is the s112
  side-item, untouched 3 sessions, now the main one. Lever = `away_walk.snap_reach` /
  `full_herd.derived_target_css` (s77's reachable-vs-commanded camera).
- **THE PER-AIM CUT WAS SCORING HALF A CANDIDATE -- FIXED** (library): `predict_bound` priced only the
  LANDING, so the screen that decides which endpoints EXIST never saw the arrival (the keep has priced it
  since s110, but only at survivors). `residual_fan` now carries the **THROW** per member (+``exit_runs``),
  `predict_bound` takes ``link``/``stations``, new `herd_stations`, `roll_probe` gains ``stations`` +
  reports ``sep`` (reported, never ranked -- maximising depth selects states that cannot fire),
  `extend_cycle` plumbs its map. **A/B on ONE enumeration scored both ways: old key understates its own
  pick by median +6.51 f (max +9.23), ROW moves at 9/29 -- but top-8 ranking IDENTICAL and honest gain
  <= +0.28 f.** Removes a fiction + re-aims a third of the beam; does NOT move this cut.
- `_notes/s114_endpoint_solve.py` now dumps **after every solve** (s114 lost 8 h); relaunched detached.
- KB `knowledge/strategy/the-separation-is-not-a-suffix.md` (NEW) + hub + history page;
  `the-endpoint-is-four-numbers.md` price section rewritten. Gates: 103 passed (+6 new in
  `tests/test_cloud_land.py`), then 42 after doc edits.
- **NEXT = the `l_ok` camera supply** (`snap_reach` at the l_ok-sole nodes named in
  `_generated/s106/s115_beam_frontier.json`); then re-cut the last cycle with the joint screen ON.


---

## Session 116 (2026-08-07) -- the camera supplies the cone; `l_ok` was a rank error, not a wall

- **THE SNAP AND THE CONE COME APART BY AN ORDER OF MAGNITUDE** (`_notes/s116_lok_supply.py reach`,
  `away_walk.snap_reach` at all 64 c3-beam nodes, 237 s). The 64 nodes are **26 DISTINCT ROLLS** once
  keyed by (pre-roll endpoint, aim, **L WINDOW**, entry csangle); over 107-121 reachable camera states
  per roll the SNAP is reachable at **0-6** (s77's 87 deg hole is real; 5 rolls have none) while the
  CONE clears at **0-68** (3 rolls none), and **21 of 26** hold a clearing target on the search's own
  `ESCAPE_TCS_STEP` **512** grid. So `l_ok` was never a physics wall and never a resolution problem:
  the last cycle's camera cut was ranked by `camera_probe_key` = **the snap bill**, the one quantity
  s77 had just proved uncollectable.
- **THE BEAM CONTAINS ITS OWN CONTROL: 12 of the 26 rolls hold BOTH a firing and a non-firing member**
  -- identical up to the last roll, same aim, same herd frames, differing ONLY in `target_cs`
  (1[F] vs 16/17; 3,6[F] vs 52; 50,51[F] vs 53; ...).
- **RE-FIRED AT A CLEARING TARGET ON THE 512 GRID, EVERY DEAD FAMILY COMES BACK: 0/672 -> 238-624**
  (`revive`, full `fires_census` at the terminal the roll actually produces, never at the cone
  reading). Node 52 **0 -> 624** with ``l_ok`` gone from its census entirely; 16 -> 301-329; 53 ->
  510-532; 54 -> 238-411; 60 -> 320. **Not confined to the 19**: node 18 (fires nothing, NO sole
  clause) -> **298**; node 14 (already firing 277) -> **644**. Herd cost unchanged.
- **AND THE FLOOR DOES NOT MOVE -- the other half of the result.** 33 terminals over 19 families priced
  whole (`cloud_landing`, atom cap 6, the s115 convention): best is node 1 at **94.76** against node
  0's **93.95**, reproduced BIT-IDENTICALLY. One `in_band` appears that s115 had nowhere (node 11,
  total **102.00**) -- still worse than the banked **101**. **SAMPLE, NOT A SWEEP:** 2 clearing targets
  priced per roll out of up to 68, picked structurally (widest cone / smallest slew / median).
- **THE RANK FIX, SHIPPED + GATED.** `away_walk.lok_clear` = the `l_ok` predicate as ONE shared
  definition (`snap_reach` now uses it); `full_herd.lok_probe_key` wired beside `camera_probe_key` on
  the last cycle; `roll_candidates`' ``tcs_probe`` now takes a SEQUENCE (one keep share each -- neither
  order contains the other). **BINARY on purpose, measured:** the L-frame margin predicts HOW MANY
  variants fire (monotone within a roll over 18 states) and NOT what they are worth -- node 16's widest
  margin bounds 94.78 vs **94.76** for its narrowest; node 52's widest 98.72 vs 98.41 for a narrower.
- **NEW HARNESS + BED.** `beam_io.split_last_roll` re-opens a banked terminal as pre-roll endpoint +
  roll knobs, asserting byte-identical re-fire + 0-ULP terminal; `snap_reach` states carry the ``off``
  that re-fires them. `fixtures/courtyard_lok_s116.json` (3 families) exists because the s77 bed CANNOT
  express the finding -- there nothing snaps AND nothing clears, so the two agree on every state.
- **THE 8-NODE ENDPOINT SOLVE FINISHED** (128 solves, 3261 s, no ``partial``): 23 accepted, floor
  **TOTAL 95.00** (node 0, rows 9/16, atom 6; node 8 96.00). **NO SUB-95 EXISTS IN THAT BED.** Required
  separations 99.2-235.7 u vs the live band 41-85 -- the term s115 showed cannot be a suffix.
- **TWO METHOD TRAPS, BOTH PAID FOR THIS SESSION:**
  1. **The L WINDOW is part of a roll's identity.** Keying camera families without it merges nodes 0
     and 16 (rolls (5,8) vs (4,7), 118 states/39 clearing vs 107/68), silently skips half the beam as
     duplicates, and produced two wrong counts ("26 of 26", "9 rolls with none") before correction.
  2. **Filtering a fine sweep down to a coarse grid UNDERCOUNTS the coarse grid** -- `snap_reach`
     dedupes by the delivered `(csangle, travel)`, so `off % 512 == 0` kept from a step-64 sweep finds
     supply at 19 rolls where sweeping 512 DIRECTLY finds **21**. Sweep the grid you mean to claim.
- KB `knowledge/strategy/the-camera-supplies-the-cone.md` (NEW) + hub; forward link in
  `mechanics/ebs-turnaround.md` (its s77 numbers are about the SNAP and stand -- nothing deprecated in
  place). +5 gates in `tests/test_{away_walk,full_herd}.py`.
- **NEXT = CUT THE LAST CYCLE OVER THE CAMERA AXIS** -- it is live now and nothing has swept it. Sweep
  node 1's 68 clearing states and node 0's 39 with `cloud_landing` (~25 s each, ~45 min) -- those two
  bracket the floor and that single number says whether 93.95 survives. Then re-run `extend_cycle` with
  the new keep (which changes which endpoints EXIST, a different question). Only untouched clause left:
  ``dips`` -- no camera fixes it, it is the recipe's own shape.


---

## Session 117 (2026-08-07) -- the camera axis swept and CLOSED; the screen is exact and is not the rank

- **THE WHOLE AXIS PRICED** (`_notes/s117_camera_axis.py`, phases `sweep`/`report`/`keyeval`/`grid`;
  **551 clearing states over the 23 supplied rolls, 1293 s at 8 procs**; dumps
  `_generated/s106/s117_axis{,_all}.json`). Unit of work = the FAMILY, and `assert_families` PROVES
  the 64-nodes-are-26-rolls grouping bit-exact instead of inferring it from the key. **Beam floor
  93.95 -> 93.87** (node 1's roll, `off` -3456, total 91.00): the camera moves it **0.08 f**. Within
  a roll the axis is worth **0.01-5.81 f** (median span 1.6) -- a large lever locally, nearly flat
  globally, because the roll that already held the floor was already near its own camera optimum.
  s116's structural 2-per-roll sample was **0.89 f** off at that very roll (94.76 vs 93.87).
- **THE SCREEN IS EXACT** (`states=all` at the two bracket rolls, 225 states): **107/107 clearing
  states fire, 118/118 non-clearing fire NOTHING** -- no false positive, no false negative. So
  `away_walk.lok_clear` IS the camera axis on these rolls; sweeping only the clearing subset
  elsewhere loses nothing.
- **AND IT IS NOT THE RANK, WHICH IS WHY BOTH PROBES STAY** (`keyeval`: each roll's swept optimum vs
  what every key would keep at `tcs_keep` 3). `lok_probe_key` is BINARY, so over an all-clearing set
  it ties everything and its slot collapses onto `landing_key`'s order -- **10 of 23** rolls, mean
  **+0.53 f**, indistinguishable from `landing_key` alone (**9**, +0.53); the SHIPPED mix reaches
  **11**, +0.22. The best VALUE key is **`camera_probe_key` -- the snap bill s116 showed was the
  wrong SCREEN** -- at **14 of 23**, **+0.14** (arrival cone margin 15 / +0.14 the only better).
  **A key can be the wrong screen and the right rank**; both docstrings now carry the calibration so
  neither share is dropped on the other's argument.
- **THE A/B RE-CUT SAYS THE SAME FROM THE OTHER SIDE** (`_notes/s117_recut_c3.py`, the s111 cycle-3
  cut verbatim with s116's keep as its ONLY difference, 4059 s): **45 of 64 endpoints shared** (19
  out, 12 new), firing endpoints **21 -> 27 (+29%)**, best bound **93.95 both**, `joint` winner the
  **same candidate bit-identical** (herd 73, along 934.2644, total 105 at 0.474 u) at index 11 -> 13,
  median firing bound WORSE (100.44 -> 101.89). **A screen buys FIRING, not value.**
- **THE 512 STEP PRICED, NOT ARGUED** (`grid`, enumerating the grid DIRECTLY and joining BY DELIVERED
  STATE): loss median **+0.01**, mean +0.30, max **+3.00 f**; **2 of 23 rolls hold no clearing grid
  member at all**. The offset filter is the trap -- `snap_reach` dedupes by delivered state, so
  `off % 512 == 0` names 15-17 of the 31 states the grid really delivers. s116 documented it, s117
  did it anyway and nearly published a wrong resolution figure. **NOW GATED.**
- **THE LANDING IS SOLVED 14 WAYS AND THE ARRIVAL IS A CONSTANT.** `in_band` **1 -> 14 states over 3
  rolls**, best landing total **98.00** (s116's 102.00) -- and every one owes **7.38-8.37 arrival
  frames**, a **163-168 u** station gap, across 3 rolls and 2 rows. Delivered best **105.90**,
  `joint` **still none**. **THE BANKED 101 STANDS.** `in_band` is the LANDING ALONE: quote
  `total + arr_frames`.
- KB: NEW `knowledge/strategy/the-screen-is-not-the-rank.md` + hub; `the-camera-supplies-the-cone.md`
  "SAMPLE, not a sweep" section REPLACED with the swept verdict (the page had staked it as a sample,
  so resolved not deprecated); arrival constant added to `delivery-is-two-predicates.md`. Gates
  **111 passed** (+2 in `tests/test_away_walk.py`, sharing a `lok_reach_s116` fixture). Commit
  d3b02e6. No behaviour changed -- the only source edits are two docstrings.
- **NEXT = THE ARRIVAL CONSTANT.** It is the entire remaining bill and neither the camera nor the
  keep touches it. Its uniformity across rolls and rows says it is set by where the HERD ends, so the
  lever is up-herd of the terminal. (1) `entry_reach.hull_scan` at one of the 14 actual arrivals --
  is the 165 u a facing problem, a distance problem, or the `iter_fan2` cap? -- with the console's
  own 25 u shape as the control. (2) Put the station gap in the LAST CYCLE's RANK, not just its keep:
  `landing_key` prices where she LANDS and nothing prices where Link ends. ``dips`` still untouched.


---

## Session 118 (2026-08-07) -- the arrival is partly a BEARING; the exit arc is worth 3 frames, 101 stands

- **THE BILL IS REAL AND IT IS NOT THE STATION LIST** (`_notes/s118_arrival_scan.py`, phases
  `control`/`scan`/`trace`/`arc`; dumps `_generated/s106/s118_{arrival_scan,arc,arc_floor}.json`).
  All 14 s117 in-band states re-fired + re-enumerated; **19 distinct arrivals `hull_scan`ed at their
  OWN arrival and OWN landing over 45 aim cells x 3 thrusts -> 0 read ANY leverage**, against a
  positive control LIT at **3 of 3** rows (0/26/107, live-walkable 2/1/15). So `arrival_frames` is
  not a fiction of the s104 hunted stations; if anything it is optimistic.
- **AND 9 OF THE 19 WERE NEVER DELIVERABLE**: EMPTY walk cloud, not settled at `WALK_CAP`, so
  `iter_fan2` keeps no junction. **That includes s117's headline** (node 4, landing 98.00, delivered
  105.90). The other 10 (node 3's family) ARE settled and fan **133444-134381** endpoints vs the
  console's **139213** -- a console-sized cloud with no leverage in it = a PLACE verdict, not a
  distance one. **Honest s117 delivered best = 106.62**, not 105.90.
- **THE GAP DECOMPOSES: THE HERD OWES HALF, THE ATOM SPENDS THE OTHER HALF.** At the roll TERMINAL
  the gap to the row's station is **67.6-106.7 u (1.97-4.28 f)**; post-atom **159.5-176.3 u
  (7.38-8.37 f)** -- the atom adds **3.3-5.4 f**. Over all 551 priced states the terminal gap runs
  **26.6-125.9 u**; Spearman(terminal gap, arrival bill) **+0.858** over the 22 rolls that price a
  variant, vs **+0.189** against the landing miss (they are NOT one quantity with two names).
- **THE TAIL RUNS THE WRONG WAY** (`trace` out to the 230 u follow bar): ``d_station`` is **minimised
  at tail 0 (146.4 u)** and RISES to **227.2 u** by tail 20. The variant held the live entry bearing
  at **85.8 deg** while the bearing from its handoff to its station is **27.7 deg** -- and the
  standing pair's OTHER member (herd up-bearing) is **18.5 deg**. The grid held a nearly-right answer
  and the rank never took it: the rank prices the LANDING and the exit stick moves both halves.
- **SO TURN THE AXIS -- `cloud_land.exit_arc`, BUILT s110 AND NEVER RUN ON A BEAM SINCE** (26
  bearings step 0x800 half 0x3000, tails 0-12, 69k-101k variants/state, 546 s at 7 procs; the
  standing PAIR re-priced INSIDE the same call as its control, so the gain is the arc's not the
  tail's): in-band station gap **31.3-176.3 -> 9.9-162.1 u**, best DELIVERED **106.45 -> 103.45**,
  states holding `joint` **1 (total 111.0) -> 10 (total 104.0)**. **This beam had NO `joint` record
  before.** Best: node 3 `off` -3968, total 103.0 + 0.45, miss 0.492, tail 10, row 30.
- **BUT THE FLOOR ROLLS STILL CANNOT LAND HER** (`arc f0,f1`): node 0 (terminal **26.6 u**, arrival
  free, bound 93.95) has **ZERO** in-band landings arc or pair over 30k-73k variants at 4 states;
  node 1 (**39.5 u**, bound 93.87) has 3 at 2 states, arc only, 134.9 u out -> delivered **111.93**.
  The arc does not cross the exchange. **THE BANKED 101 STANDS**; the remaining 2.45 f are not in the
  atom.
- KB: NEW `knowledge/strategy/the-exit-bearing-buys-the-arrival.md` + hub;
  `delivery-is-two-predicates.md` (105.90 -> **106.62** + the s118 paragraph),
  `the-screen-is-not-the-rank.md` (the `settled` trap), `the-arrival-is-payable.md` (its "the grid
  only ever held two" section now says what happened when it was swept). Gates +3 in
  `tests/test_cloud_land.py` (**114 passed**, 6 deselected, 8:48; commit **1bcbb4f**). **NO library behaviour changed** -- the arc and the tail were already
  built; what changed is that they were run.
- **NEXT = PLUMB THE ARC INTO THE CUT, THEN RE-CUT.** `cloud_landing` cannot pass ``exit_bearings``
  (only `atom_cloud` takes it) and `extend_cycle` has no ``cloud_exit_bearings``, which is exactly
  why s110 built the arc and no enumeration since used it. Add the passthrough (additive, default =
  the standing pair) + give `residual_fan` the arc (its members carry the THROW `predict_bound`
  prices the arrival with), then re-cut cycle 3 with the arc as its ONLY difference (s117 A/B shape,
  ~68 min): not "what could these 14 endpoints reach" but "which endpoints EXIST once the screen sees
  the arrival the arc delivers". ``dips`` still untouched.
- **TRAPS PAID FOR THIS SESSION**: (1) `in_band` WITHOUT `settled` is not a candidate and still
  prints the cheapest total; (2) holding a candidate's ROW fixed while the tail moves the landing
  printed a delivered **99.61** that was not a candidate (re-price `_joint_row` every frame);
  (3) a longer tail can move the arrival FURTHER from the station (now gated);
  (4) `full_herd.synthetic_hot_arrival` fires NOTHING at any feet/d_short, so a gate needing
  `away_walk.fires` cannot use it.

## Session 119 (2026-08-07) -- the arc is plumbed, and the SCREEN structurally cannot see it

- **THE PLUMBING WAS ONE PARAMETER DEEP, AND IT IS DONE** (commit **0d6a63b**, all additive except
  one refusal). Only `atom_cloud` ever took ``exit_bearings``, so `cloud_landing` / `cloud_probe` /
  `extend_cycle` had nothing to pass -- which is the whole reason s110's `exit_arc` had never entered
  an enumeration. Now ``exit_step``/``exit_half`` on `cloud_landing` + `residual_fan`,
  ``cloud_exit_step``/``cloud_exit_half`` on `extend_cycle`, `ARC_STEP`/`ARC_HALF` = what s118 priced.
  It is an arc SPEC and not a bearing list because `exit_arc`'s centres are measured from each
  endpoint's OWN position (`cloud_land._arc`).
- **AND UNDER IT, A BIGGER FAULT: THE JOINT SCREEN HAD BEEN PRICING LINK'S ARRIVAL AT HIS ROLL
  TERMINAL SINCE s115.** `predict_bound` read the throw as ``m.get('throw_along', 0.0)`` and the fan
  every joint cut was handed (`s107_fan.json`, measured in s107 BEFORE `residual_fan` carried the
  throw) has the column on **0 of its 178 members**. s118 had already measured the size of that
  without knowing it applied: terminal gap 67.6-106.7 u vs post-atom 159.5-176.3. Now a **refusal**.
  Re-running `_notes/s11{0,1,7}_*recut*` verbatim raises, by design.
- **THE HONEST FAN IS 425x THE TABLE THE SCREEN WAS READING** (`_notes/s119_fan.py`, 6 firing c3
  endpoints, both lanes one call, 257 s at 6 procs): 178 -> **7668** (pair, with throw + tails 0-6)
  -> **75627** (arc). ~10 s an aim at 116 rows. Frame-dominance is exact and removes 2%; an 8 u throw
  quantum costs 0.47 f for 2.7x. **What works is `predict_bound`'s OWN arithmetic**: a member's best
  conceivable bound is ``frames + n_atom + min(plan_cost)``, so once an incumbent beats that its whole
  row loop is skipped -- exact, order-independent, **~380x, to 26 ms an aim**.
- **THEN BOTH FIXES HIT THE SAME WALL, AND THAT IS THE SESSION'S FINDING**
  (`_notes/s119_screen_delta.py`, 3 lanes at all 64 c3 nodes; ``zero`` REPRODUCES the s115-s118
  behaviour rather than remembering it). **`n_atom` is charged 1:1 in frames, so the minimum sits on
  an `n_atom` = 3 member at 64/64 endpoints in every lane** -- the fan spans 3..24 and only **3** of
  75627 members are at 3, so ~3 members decide every answer. The arc only differentiates from atom
  **6** (the exit stick is held at the END; pair and arc fans have IDENTICAL counts at n_atom 3/4/5 =
  3/50/166), so **pair -> arc moves the bound +0.000 at 64 of 64**, 0 rank changes, identical member.
  **A knob that pays late is invisible to a measure that minimises a quantity it adds frames to.**
  The arc's frames live in the keep's ``joint``/delivered fields, never in ``bound`` -- exactly the
  shape of s118's numbers (bound 93.95 unchanged, delivered 106.45 -> 103.45 at tails 10-11).
- **THE THROW FIX IS REAL AND STILL CHANGES NO OUTPUT**: bound **-0.480..+2.814** (mean +1.449),
  **53 of 64** ranks and **21 of 64** row choices move -- and `_notes/s119_recut_c3.py pair` (3936 s)
  re-cuts **byte-identical to `s117_c3_landing.json`**, all 64 nodes, every field, atom knobs
  included. The predictor is one of four `_mixed_beam` orders and its share picked the same six.
- **KB**: TWO new truth pages -- `the-fan-outlived-its-columns.md` (the plumbing + the missing
  column) and `the-cheapest-atom-owns-the-screen.md` (the wall) + 2 hub entries. Gates +7 in
  `tests/test_cloud_land.py`: **121 passed**, 6 deselected (11:15).
- **NEXT = CHANGE WHAT THE CUT RANKS, NOT WHAT IT READS.** (1) Give the last cycle a keep share on
  the DELIVERED field (``joint`` / ``total + arr_frames`` on a SETTLED arrival) -- a min-TOTAL among
  predicate-satisfying variants, not a frame minimum, so it is free to sit at the tails 10-11 where
  the arc pays; `extend_cycle` currently sorts on ``cloud['bound']`` and shares on ``cloud['miss']``,
  both from ``best``, both short-atom. (2) Then give the SCREEN a predictor of THAT: not a bigger fan
  but a different reduction (min at a FIXED atom length, so long members compete with each other
  instead of against a 3-frame floor). ``dips`` still untouched.
- **TRAPS PAID FOR THIS SESSION**: (1) a byte-identical output does NOT mean a fix was inert -- report
  the delta at the SCORER too; (2) a superset table returning the identical minimum is evidence about
  the REDUCTION, not the table -- the one-line diagnostic is *report the argmin's position on the
  charged axis*; (3) a node's ``in_band`` and ``joint`` are DIFFERENT variants, so a "best delivered"
  computed off ``in_band`` alone under-reports; (4) the pre-commit comment gate allows **2**
  consecutive added `#` lines -- put rationale in docstrings or the KB.
- **AND THROUGH THE OTHER MEASURE THE ARC DOES PAY -- ONE FRAME** (`_notes/s119_arc_at_beam.py`, the
  KEEP run at the beam's own **27 firing survivors**, both lanes in one call, 1420 s at 5 procs;
  legitimate at the banked beam precisely because the screen was measured not to move under the arc).
  in-band nodes **2 -> 6** (nodes 3/4/6/8 gained one), joint nodes **1 -> 2**, best DELIVERED
  **105.00 -> 104.00** (node 13, tail 3 -> tail 2, miss 0.474 u), best `bound` unchanged at 93.95
  (moved at 7 of 27, by <= 0.176). The winner's station gap is **33.4 u against `FREE_REACH` 34.0** --
  it clears the arrival predicate by 0.6 u and still owes `hull_scan` at its own arrival.
  **THE BANKED 101 STANDS, now by 3 frames.**

## Session 120 (2026-08-07) -- the reduction is fixed, and it was never the binding error

- **THE s119 CROSS-CHECK IS DISCHARGED: NO DISAGREEMENT** (commit **20fd812**). The in-process `arc`
  re-cut finished (16781 s) and reproduces the parallel probe exactly: 27/64 fire, bound 93.95,
  in-band **2 -> 6**, joint **1 -> 2**, best DELIVERED **105.00 -> 104.00** at miss 0.474 u. The
  "node 13 vs node 14" is a LABEL: the two lanes' beams are identical except an **exact swap of slots
  13/14**, and the winner is the same endpoint (herd 73, along 934.264, lat -10.204, offset +9.632),
  one frame cheaper under the arc (`n_atom` 11 -> 10, `exit_run` 3 -> 2). **A node index is a rank
  position, not an identity** -- compare lanes by endpoint geometry.
- **STEP 1 OF THE s119 PLAN (the delivered keep share) IS BUILT AND CANNOT BITE.**
  `cloud_land.delivered` (both records, SETTLED only) + `extend_cycle`'s ``delivered_keep``, off by
  default. One line of the s119 arc log settles its value for free: over all **165** survivors the
  enumeration found **6 in-band and 2 joint**, and the 64-node beam holds **exactly those 6 and those
  2**. Every deliverable survivor already reaches the beam. **Check whether a cut is BINDING before
  building the share that fixes it.**
- **STEP 2 (the screen's reduction) IS BUILT, EXACT, 22x CHEAPER -- AND STILL DOES NOT RANK.**
  `predict_bound` gains ``atom_min``/``by_atom`` (minimum per atom LENGTH) and
  ``band``/``owes_nothing`` (minimise subject to the keep's predicate; the second REFUSES without
  stations). The two fix different halves: at the beam's best-delivering endpoint (true delivered
  **104.00**) the global minimum reads 100.93 (**-3.07**) where ``k>=10`` reads **104.05** (+0.05),
  while the BANDED key is what makes the arc visible at all -- **-1.443 over 33 of 64 ranks**
  (joint-banded -7.028) against the global key's `+0.000 at 64/64`. A banded search has no incumbent
  to prune on, so `_band_index` buckets the rows on a band-wide grid and each member reads 9 cells,
  not 116 rows: **128-147 ms a call vs the global key's 3189 ms**, gated as an identity against the
  brute-force scan. **A constraint that bounds a distance is a spatial index waiting to be used.**
- **AND THE REASON IT STILL DOES NOT RANK IS THE FAN, NOT THE REDUCTION** (`_notes/s120_screen_
  {keys,rank}.py`, dumps `s120_screen_{keys,rank}.json`). The four endpoints with settled records
  deliver 104.00/106.13/106.14/111.52; the standing screen ranks them **27/16/17/15** of 64 -- worst
  deliverer highest, best lowest -- and the banded reductions move the best only to 21st/23rd.
  Measured at the 27 firing endpoints, `predict_bound`'s error (enumerated - predicted) spans
  **-0.93 .. +5.11 f** (mean +1.74) and is **NEGATIVE at 4 of 27, 3 of them deliverable**: the
  "optimistic by construction" proxy **is not a bound**, and it is pessimistic exactly where the
  keepable endpoints are. Not the documented -0.53 u/u offset dependence either (Spearman **-0.135**;
  `t_lat` +0.418, enumerated miss +0.388), so no one-parameter shift repairs it. **Check the SIGN of
  a proxy's error before pruning on it.**
- **SO THE LEVER IS THE CAP, NOT THE RANK: 69 of 165 survivors have NEVER been enumerated** (the keep
  is capped by wall clock at the cheapest 96 by admissible bound), so in-band 6 / delivered 104.00 are
  properties of **58%** of the population. **LEFT RUNNING**: `_notes/s120_uncapped_c3.py` (log
  `_notes/s120c_uncapped.log`) -- the s119 PAIR lane verbatim with ``cap=None`` and ``beam=165``, so
  every survivor is enumerated AND dumped (~1.3 h; control = the capped pair lane's 2 in-band, 1
  joint, delivered 105.00). Its permanent gain: the dump holds every survivor's cloud record, so any
  future keep share is priceable OFFLINE instead of costing another 1-5 h cut.
- **KB**: TWO new truth pages -- `minimise-subject-to-the-predicate.md` (the reduction, what each half
  is worth, the index) and `the-fan-is-not-a-bound.md` (why it does not fix the rank) + 2 hub entries.
  Gates +7: **128 passed**, 6 deselected (10:37).
- **TRAPS PAID FOR**: (1) a node index is a rank, not an identity -- comparing lanes by number
  invented a disagreement; (2) do not measure a candidate reduction on a PROXY for it (applying the
  band predicate to each length's own bound-minimising record ranked the deliverable endpoints
  7/14/15/26, their TRUE order, where the shipped reduction ranks them 21/24/25/16 -- the proxy was
  accidentally stricter and would have shipped a rank that does not exist); (3) "optimistic by
  construction" is a claim about a model, not a measurement of code.
- **NEXT = READ THE UNCAPPED CENSUS AND SPEND WHERE IT SAYS.** If the population holds in-band/joint
  records the capped 96 never saw, the CAP was the binding constraint (re-price those with the arc,
  ~128 s each, and 104.00 is provisional); if not, cycle 3's endpoint set is exhausted and the open
  axes are ``dips`` (still untouched) and a fan measured/corrected PER ENDPOINT -- not another
  reduction.

## Session 121 (2026-08-07) -- the census says exhausted, and dips is measured dead

- **THE UNCAPPED CENSUS IS IN: BRANCH 2, THE CAP WAS NEVER BINDING ON THE ANSWER.** s120's run
  finished (4309 s; dumps `s120_c3_uncapped_{beam,landing}.json`), enumerating all **165** roll
  survivors instead of the cheapest 96. **Best DELIVERED over the whole population: 105.00 at node 13
  -- the SAME endpoint and SAME figure as the capped slice**; best bound 93.95 unchanged; 81 fire, 3
  in-band, 1 joint. The cap DID hide records -- 12 of the 46 firing endpoints in the dump and 1 of the
  2 deliverers -- but the hidden deliverer is **117.85**, 12.85 frames off, and the arc moves a
  delivered figure ~1 frame. **Reproduces its control exactly: 47 endpoints probed in both lanes, 0
  disagree on every field.** So the remaining frames are NOT in cycle 3's endpoint set.
- **``dips``, THE LAST UNMEASURED CLAUSE, IS NOT A LEVER** (`_notes/s121_dips_census.py`, 402661
  variants at all **99** UNCAPPED-census endpoints, 347 s). Relaxing `DIP_BUDGET` 3 -> 14 admits
  **+39667** variants (+38.7%) and revives **0** of the **53** endpoints that fire nothing:
  ``sole['dips']`` is 39667 across the population and **0** at every dead one -- every dip-only refusal already sits at an
  endpoint that fires. Priced at HELD PUSH (most `resid_along` per `freeze_f`; frames alone reads
  "free" because a short atom separates early only because it pushed less) the bar is worth **<= 0.78
  frames** anywhere. KB `strategy/the-dip-budget-is-not-the-lever.md`; s116's contrary claim MIGRATED
  to `history/dips-refuses-the-other-half.md`.
- **WHAT REFUSES THE DEAD HALF IS `l_ok`**: all 200038 variants at the 53 dead endpoints, SOLE on
  55754. `lok_clear` at all 99 arrivals splits **45 of 46** firing against **0 of 53** dead (1 false
  negative, 0 false positives). Three dead endpoints are within 8 deg of clearing; node 56 by
  **1.72 deg** (node 81; node 92 at 1.74). This retires ONE of s116's two reasons for the camera being a share not a
  requirement; the other (a filter throws away firing states, s73: 96%) stands and is what to re-test.
- **THE CAP RECORDS A SKIPPED ENDPOINT AS A REFUSED ONE** (``fires=False``/``bound`` inf beside
  ``unprobed=True``): **7 of 17** skipped beam slots really fire (1410-3263 variants each). Priced
  with the pair lane's own keep (`_notes/s121_price_hidden.py`, control node 13 exact): all 7 fire,
  **none delivers**, bounds 107.79..113.36, the worst in the beam.
- **TRAPS PAID FOR**: (1) **never edit a source file while a gate run is in flight** -- gates here
  assert on source TEXT via `inspect.getsource`, and a mid-run docstring edit to `full_herd.py` made
  `getsource(extend_cycle)` return one unrelated line, failing 4 `test_cloud_land.py` gates that look
  exactly like a regression (clean re-run: 49 passed); (2) **existence is not the branch test,
  improvement is** -- the reader first printed BRANCH 1 off a deliverer 12.85 frames WORSE; (3)
  **geometry is not an identity either** -- 7 of 64 beam slots are twins with bit-identical endpoint /
  offset / centre-feet and different bounds (``offset`` is Link's LATERAL only), so key on the dumped
  input ``log`` (64/64 unique); (4) a clause that refuses a majority is not thereby a lever -- count
  ``sole``, not ``fail``.
- **NEXT = STOP RE-CUTTING CYCLE 3 AND CHANGE WHAT ENTERS IT.** The population has now been
  enumerated whole, once, and it says 105.00. The lever named by measurement is that **53 of 99
  endpoints are ones where `l_ok` refuses every variant** while 55754 of those fail nothing
  else: re-test the camera keep's SHAPE (share vs requirement) on the s117 A/B, or price the three
  near-miss dead endpoints via `snap_reach` (which needs their PRE-roll node + aim from the junction
  beam, not the c3 dump).

## Session 122 (2026-08-08) -- the shape is measured too, and the answer still does not move

- **THE CAMERA'S SHAPE IS AN A/B NOW, AND IT TIES.** The last cycle's `l_ok` keep was a SHARE, so it
  could not stop admitting the 53-of-99 dead endpoints. Made a REQUIREMENT (`full_herd.as_requirement`
  + `roll_candidates`' ``tcs_require`` + `extend_cycle`'s ``lok_require``, all additive, DEFAULT-OFF)
  and re-cut whole (`_notes/s122_recut_c3.py`, the s119 PAIR lane with one knob, **3160 s** vs 3936 s):
  terminals clearing `l_ok` **33/64 -> 63/63**, probed endpoints that FIRE **27/47 -> 50/50**, in-band
  **2 -> 6**, deliverers **1 -> 4**, **34 endpoints the share never reached**, **0 disagreements** at
  the 23 shared -- and best DELIVERED **105.00 at the SAME endpoint**, best bound 93.95 unchanged. The
  three new deliverers are 106.66 / 115.82 / 117.85, all worse.
- **SO 105.00 IS RETURNED BY THREE CUTS THAT DO NOT SHARE A POPULATION** (capped slice 58%, uncapped
  census 165, requirement-shaped reaching 34 endpoints neither held). That is evidence about the
  ENDPOINT SET, not about the cut. KB `strategy/the-shape-of-a-cut-is-not-its-answer.md`.
- **PRE-FLIGHT BEFORE THE HOUR** (`_notes/s122_shape_preflight.py`, 41 s + 62 s): re-run R2 whole at
  the cells behind a banked beam (pre-roll endpoint from `beam_io.split_last_roll`). The share spends
  **54 of 99 slots** on states that can never fire; the requirement returns **63 that all fire** (25
  never kept before) and loses **ZERO junction nodes** -- all 8 emptied cells sit at a pre-roll node
  keeping live cells on another aim. Emulation self-checked to reproduce the banked keep 33 of 33.
- **THE s73 "96%" NEVER APPLIED TO THIS PREDICATE** -- it was measured on the SNAP BILL, and
  `lok_clear` has no false positives, so as a filter it drops only states that fire nothing. That
  ARGUMENT is MIGRATED to `history/the-cone-keep-was-a-share-because-a-filter-throws-away-firing-states.md`;
  the share still ships, on a measured reason (the lanes tie; default-off keeps banked provenance).
- **TRAPS PAID FOR**: (1) **`nohup … &` from a tool call does not reliably detach and `pgrep -f`
  cannot see the process** -- "it died silently" was wrong, BOTH runs were alive writing one log (NUL
  padding is the tell) and racing one JSON dump; use the harness `run_in_background` + `Get-CimInstance
  Win32_Process`; (2) an emulation of a library cut must be SELF-CHECKED against the banked keep --
  `junction_quality` is still computed on the last cycle and sorts `(-inbox, lat)` ahead of every
  unscored target; (3) prove the knob was IN FORCE with a prediction made before the run, or a dead
  knob looks exactly like a tie; (4) a `history/` page needs the bare `status: historical` line, not
  `**Status:** historical` (the gate regex is `status:\s*historical`).
- **NEXT = GO UPSTREAM OF CYCLE 3.** Its endpoints land at along **918-971** against the handoff target
  **876** (shifted thread 893.9) -- 40-95 u PAST it, and one FRONT_ROLL is ~205 u and cannot stop
  short. Re-cut **CYCLE 2's exit** / `target_along` so the handoff lands earlier (the require lane's
  106.66 deliverer sits at along 886.8 with in-band total **99**, its whole bill in the ARRIVAL), or
  price the arrival at the 6 in-band records that now exist. Do NOT re-cut cycle 3 again, and s121's
  near-miss-dead-endpoint option is ANSWERED (the requirement lane spends every slot on a clearing
  endpoint and still finds 105.00).

## Session 123 (2026-08-08) -- both s122 options answered; the arrival bill is the ROOM

- **OPTION 1 (re-cut cycle 2 / `target_along`) IS DEAD, ANSWERED IN MINUTES OFF THE BANKED DUMPS**
  (`_notes/s123_c2_preflight.py map`). Attribute all 226 cycle-3 terminals to their cycle-2 parents by
  **input-log PREFIX**: the population spans along **827.99-984.25** with **6 terminals SHORT of the
  876 target**, and cycle 2 already exits where it would have to (nodes 0/1 at **579.19** deliver
  **877.88 / 886.82**; the earliest exit 569.82 UNDERSHOOTS to 827.99). The **"918-971" was ONE BRANCH**
  (34 of 63, off c2 nodes 8/9), not the population -- a range quoted off the winners.
- **THE ALONG IS A TRADE WHOSE LOSING HALF IS THE ARRIVAL.** Near-target best deliverer 106.66 =
  `total` **99** (two frames UNDER the banked 101) + **7.66** arrival, vs the winner 105.00 = `total`
  105 + arrival ZERO (11-frame atom, Link 29.2 u from a station).
- **AND THE BILL IS GEOMETRY, NOT SEARCH**: all **268** stations in ONE cluster at along
  **804.70-818.69**, the 116 rows at **879.92-979.86** -> every row **72.3-162.6 u down-line of its own
  stations** (median 110.6), so delivering asks **61.2-175.2 u** of separation. corr(``sep``,
  `d_station`) **-0.697 / -0.819** (vs `n_atom` -0.489/-0.603); beam tops out at **59.4 u**.
- **THE HERD CANNOT BUY THE DEPTH EITHER -- s115's OPEN HALF CLOSES** (`_notes/s123_deep_census.py`):
  7 herd-produced deep terminals (sep 62.4-75.3) fire **0 of 672**; controls (deepest firing) fire
  **226-329**. **6 of 7 have NO sole clause** (`l_ok`+`dips` together); the 7th is one camera fix from
  firing all 672 but lands **52 u short** of the nearest row. Same along: sep 59.4 -> 329 fire,
  sep 62.4 -> **0**, `l_ok` SOLE.
- **OPTION 2 PRICED WHOLE: THE ARC IS ONE FRAME, A FOURTH TIME** (`_notes/s123_arc_at_require.py`,
  2464 s): at the require lane's **50 firing**, control **50/50** reproduces the banked record; in-band
  6->10, joint 1->2, deliverers 4->7, best DELIVERED **105.00 -> 104.00**, bound 93.95 unchanged. s112's
  never-run EDGE CHECK: winners **-22.5..+11.25 deg** off centre vs **+-67.5**, **0 of 7** at the edge
  -- widening is NOT an unpriced lever.
- **LIBRARY**: `beam_io.attribute_parents` (the method, executable) + gate. Gates **130** (+1).
  KB: NEW `strategy/the-handoff-along-was-already-spanned.md`, NEW `strategy/the-depth-the-room-asks-for.md`
  (SPLIT, not appended to the s115 page), + updates to `the-exit-bearing-buys-the-arrival.md` and
  `the-separation-is-not-a-suffix.md`.
- **TRAPS**: (1) a range quoted off the WINNERS is a statistic about the rank; (2) an emulation's own
  verdict line lies the same way -- the census first printed "the camera refuses" by summing SOLE
  *variants* (672, all one node) where 6 of 7 nodes have no sole clause: **count NODES**; (3) READ THE
  KB before the obvious experiment -- "widen the arc" was already worth zero (s113); (4) a node's
  top-level `total`/`arr_frames` is its floor record, NOT its delivered one.
- **NEXT = PRICE THE STATION SET ITSELF, the one input nothing has ever varied.** `cloud_land.HUNTS`
  is two s104 dumps at `plan_cost` **21**, thrusts **14/15**, a **2-frame** walk; the 804.7-818.7
  cluster is where THOSE hunts found dust, and every structural number above is relative to it (s118
  verified the bill is real for the arrivals it SCANNED -- a different claim). Hunt at `plan_cost` 20
  (s104 found 56 such placements) / other thrusts / other walk budgets and see whether the cluster
  moves down-line. If it moves, the endgame reopens at the `total` 91-99 endpoints that already exist;
  if not, **101 is at or near this route's floor** and that is the bankable finding. Do NOT re-cut
  cycle 3 (s122), re-cut cycle 2 (s123), widen the arc, or chase separation (closed both ends).

## Session 123 END -- Dereck re-aimed the problem: ZERO WALK-AWAY, and the search was 34x slow

- **THE NEW SHAPE (supersedes everything above): the herd's LAST ROLL *is* the clip roll.** No escape,
  no walk-back, no separate roll-entry search -- Link never leaves her. This DELETES rather than
  optimises the escape atom + all five `away_walk.fires` clauses, the station cluster and
  `arrival_frames`, the 61.2-175.2 u separation ask, and the 230 u follow limit. What remains is ONE
  condition on ONE frame: at the cut, is Tetra in a clipping position and is Link's overlap steering
  him through the seam. **Order (his "reduce variables"): solve the TERMINAL CONFIGURATION first**
  (which (Link, Tetra) geometry at the cut clips -- use `harness/rollstab` acceptance / `tetra_clip` /
  `razor_depth`, NOT the `cloud_land` stack), then chain backwards to state 2. Open unknown = the
  razor: the clip wants ~**1.23 u** overlap at the cut and a herd roll's depth is whatever the plow
  produces.
- **THE SEARCH HAS BEEN 34x SLOWER THAN THE ENGINE ALREADY IN THE REPO** (`_notes/s123_bench.py`):
  `beam_io.rebuild_beam` -> `seeds.make_freerun` (camera + Tetra look/eye + neck wired, Python pose FK)
  = **2915 steps/s, 74 roll rollouts/s**; `seeds.make_freerun_native` (`LandCore.step_courtyard`,
  `native_push=1`) = **99523 steps/s, 2583 rollouts/s**, already 0-ULP gated
  (`tests/test_freerun_native.py`). A 100k-aim sweep = **~39 s single-threaded**, and s123's own 2464 s
  arc sweep was ~70 s of work. **Every wall-clock figure in the s102-s123 boxes is inflated ~35x** --
  the arithmetic stands, "too expensive to sweep" never did. NOT a one-line swap: the native config is
  stripped (no camera -> `csangle`/`l_ok`/`target_cs` predicates need care) and the CUT is Python-only
  (no cut in `_anmc.pyx`) -> **native for the mass sweep, Python for the exact clip confirm**.
- **CORRECTION I OWE**: I told Dereck the courtyard Tetra is the glitched no-follow one. **She is
  not** -- that is the SANDBOX push-aside setup. She is genuine and follows past **230 u**
  (`FOLLOW_ENGAGE_DIST`, closing back to 130), `from_f0.py:546` warns, and `roll_probe` kills any aim
  that trips it (``followed``; 95-99% of swept aims die that way). Terminals measured 57.0-75.4 u, so
  s123's numbers are inside the limit. [[tetra-glitched-nofollow]] is now scoped so it cannot mislead.
- **AND SPEAK PLAINLY TO HIM**: "along/sep/d_station/arr_frames/in-band/joint/atom" is noise. Say push
  her / walk away / roll in for the slash, and quote FRAMES. He found the real hole in the accounting
  -- the walk-out and walk-back are ONE round trip, not two bills -- as soon as the words were plain.

## Session 124 (2026-08-08) -- the zero-walk-away best case EXISTS; the razor wants alignment, not depth

- **THE TERMINAL CONFIGURATION IS SOLVED** (`harness/tetrapush/terminal.py`, tracked + gated
  `tests/test_terminal.py`, 11 gates 1.4 s). **51 genuine terminal configurations; 13 with Link ALREADY
  TOUCHING her at the roll entry and contact NEVER breaking to the cut**, at handoff distances
  **50-110 u** -- the herd's own live range (41-85). Dereck's re-aimed shape holds at its first question.
  1540-cell box (``runway`` 140-480 x ``along`` 30-245) in **41 s**.
- **THE OPEN UNKNOWN WAS THE WRONG WORRY. THE CORNER SETS THE DEPTH, NOT THE HERD.** Over handoffs
  50-245 u apart, plowing her 53-126 u, the last three overlaps converge 18.3/18.4/13.7 ->
  6.76/6.75/6.70 -> **1.132/1.132/1.127**; her cut-frame spot lands in a **0.054 x 0.205 u** box, Link's
  brace is constant to 0.001 u, the cut lands inside 0.003 u. So **the herd does not have to place her
  (the last roll parks her)** and the ONLY sensitive axis is the pair's LATERAL ALIGNMENT:
  ``d(resid)/d(lat)`` -4.0..-14.3 /u vs ``d(resid)/d(runway)`` **+0.17 /u**.
- **THE PAIR IS THE COORDINATE**: ``entry = brace - runway*m``, ``tetra = entry + along*m + lat*q``.
  `tetra_placements.tsv` and `entry_search`'s locus are both SLICES of this surface. `classify` reports
  touching-at-entry / contact-unbroken / how far she was plowed. ``runway`` (190-310 u at every hit) is
  what Dereck's longer-than-normal EBS buys.
- **THE LEAN IS NOT A BAR -- s79's claim RE-SCOPED.** "m351C 64 already does not clip (resid 1.1e-2)" is
  at a FIXED ENTRY (1.1e-2 = a hundred window widths). Re-solving ``lat`` clips at **every lean
  -191..+191**, incl. the -191 a replayed herd hands over. Decays 35%/frame -> 0 in 13 frames
  (`SLANT_DECAY` now has a canonical row in `reference/constants.md`).
- **METHOD -- BRACKET THEN BISECT, NEVER SWEEP.** Band **2.2e-5..1.5e-4 u**; the module's own
  281-sample bracketing grid returns NOTHING at a clipping cell (gated). `solve_razor` bisects all
  brackets IN LOCKSTEP (2500 razors = 62 batch sweeps, not 155000).
- **PERF**: `ShoveCtx.sweep_par` = **76k full coupled rolls/s**, 30x `make_freerun_native`. The s123 "34x
  slow" applies to the HERD stage (`beam_io.rebuild_beam`), not the terminal one.
- **TRAPS PAID FOR**: (1) `lat` rounded to 4 decimals reads `genuine False` -- full float precision or
  nothing; (2) NEVER hand-pad a pinned value from `%.9f` output (3 gates failed at the 10th sig fig --
  take `repr`); (3) a gradient measured at one cell is not the family's (3-5 /u at (200,85), 14.30 at
  (230,50)); (4) "no genuine found" from a ONE-runway/4-cell probe called three leans dead that a proper
  scan revives -- `[[infeasible-needs-proof]]` at its cheapest; (5) `razor_depth.cut_frame_swing` does
  NOT explain the 1.13 u (it projects on the roll dir only and reads +1.85 at thrust 14; Link is sliding
  11-17 u/frame down the wall, not stationary) -- the CONVERGENCE is the mechanism.
- **NEXT = CHAIN BACKWARDS.** Which herd delivers a pair in the terminal set. The target changed shape:
  not "land her on a tabulated coord" but **"leave the pair laterally aligned at a 50-110 u handoff"**.
  Re-point the herd's terminal predicate at `terminal.solve_cell`, not `cloud_land`'s station/arrival
  stack (which the new shape deletes). Then price it in FRAMES vs the banked 101. Cheap and unexplored:
  the scan is ONE facing (40835) + ONE thrust (14); 45 aim cells exist and thrust 13 is a frame cheaper.

## Session 125 (2026-08-08) -- the chain-back: the razor is on LINK, and every on-side herd endpoint clips

- **THE CHAIN-BACK IS RUN** (`harness/tetrapush/handoff.py`, tracked + gated `tests/test_handoff.py`,
  6 gates 4.1 s). Of the **127 banked cycle-3 endpoints, 15 park her on the genuine side** of the clip
  roll's approach line and **ALL 15 ADMIT A CLIP ROLL** -- 3-7 genuine Link entries each, **74 total**,
  at ``runway`` 195-320. Her placement is NOT the blocker and never was.
- **THE COORDINATE NEEDED A FOURTH AXIS.** `terminal.RollFrame` pins Link's entry to the brace line
  (the s124 shape, where Link WALKS to a chosen spot). A herd arrives off it by tens of units, so
  `PairFrame` restores ``side`` (``entry = brace - runway*m + side*q``). At a FIXED Tetra the two
  laterals collapse (``lat = l0 - side``) -> the genuine set is a **CURVE OF LINK ENTRIES**,
  one solved ``side`` per ``runway`` (`entry_locus`). ``side`` 0 is `RollFrame` bit-for-bit, so s124's
  bracket/bisect/band methods run on it unchanged.
- **THE CHAIN-BACK TURNS ON A SIGN, NOT A DISTANCE.** Her offset from the approach line
  (`tetra_lateral`, ``l0``): 288 tabulated coords **+2.50..+13.69**, 51 solved terminals
  **+0.57..+51.0**, the 13 unbroken **+0.57..+4.89** -- all ONE side. Console-confirmed 71-frame herd
  leaves her at **-17.67** (the escape push finished the crossing to the +2.75 of coord 274); the two
  banked beams' terminals span **-71.15..+19.65**, their pre-roll states -243.8..-108.9. So the last
  roll is what carries her across; ask the SIGN first (one dot product kills 112 of 127).
- **WHAT IS LEFT IS ENTIRELY LINK'S POSITION**, and on his axis the acceptance is **4.5e-5..5.1e-4 u**
  inside a contact corridor only **~1 u wide** (-0.105..+0.895 at the s124 reference cell). Hence
  `SIDE_STEP` **0.005**, 100x finer than `terminal.LAT_STEP` -- 0.5 u straddles the whole corridor.
  Link ends the last herd roll **73-171 u** from the nearest genuine entry.
  **SCORE A HERD BY WHETHER IT LEAVES LINK ON THE CURVE, NOT BY WHERE IT PUTS HER.**
- **PRICE: floor 94** (73 herd + 5 to close 73.69 u at the walk cap 17.0 + 16 clip roll) vs the banked
  **101**, at three 73-frame nodes of the s122 require beam. A FLOOR, not a plan
  ([[banded-proxy-needs-its-newton]]): no turnaround, no landing guarantee on a 1e-4 u razor.
- **THE CLIP ROLL'S AIM IS NOT FREE.** Same coarse box: 40835 -> 15 genuine/13 unbroken; **every facing
  on a 500-BAM ladder 29000..44000 -> 0**; at 25 BAM, 40810/40860 -> 0. Full s124 box: 40810 -> 3
  genuine (0 unbroken, overlap 1.50-1.68 not 1.13), **36888 (a herd's own last-roll aim) -> 0 of 1540**.
  The last roll must be aimed at the corner deliberately.
- **TRAPS PAID FOR (both gated)**: (1) **NEVER round-trip a razor-scale position through the frame** --
  `m`/`q` are the console's f32 sin/cos tables, orthonormal only to ~1e-7, so project-and-rebuild moved
  the residual **8.3e-5 -> 1.05e-3, genuine to DEAD** (12 band widths) with no bug anywhere; hold
  positions (`PairFrame.sweep`), report coordinates. (2) **Centre a lateral scan on HER, never on the
  brace line** -- a brace-centred +-60 u span at a real herd Tetra has max overlap **-91.8 u**, not one
  sample in contact, and reads as flatly infeasible ([[infeasible-needs-proof]], one axis over from
  s124's version).
- **NEXT = RE-CUT THE LAST CYCLE AGAINST `entry_locus`**: rank `full_herd.extend_cycle` /
  `terminal_targeting` endpoints on Link's distance to the genuine entry curve (prune on her ``l0``
  sign first), then close the last 1e-4 u by bracket-then-bisect ONE LEVEL UP -- on a herd control's
  alphabet, not on ``side``. Seeds: `_generated/s125/onside_nodes.json` (each endpoint's locus, entries
  at full precision). Unexplored + cheap: thrust 13 (a frame cheaper) and lean != 0.

## Session 126 (2026-08-08) -- the last cycle cannot BE the terminal: crossing and runway are one resource

- **THE s125 NEXT STEP IS DONE**: the terminal predicate is the last cycle's endpoint rank
  (`full_herd.extend_cycle(handoff_keep=...)` + `handoff.endpoint`, gate `tests/test_handoff.py` 7->12,
  8.9 s). Price = ``frames + gap/WALK_CAP + cut_step``, admissible on every term; her ``l0`` SIGN is a
  FREE refusal. Two economies took it from **19 s to ~1.5 s** per endpoint (vs ~28 s for the
  `cloud_land` stack it replaces): **`resid_window`** -- outside contact the roll never touches her so
  the residual is ONE NUMBER BIT-FOR-BIT, and a 561-sample coarse pass says where the 28001-sample fine
  one has anything to find (**identical brackets**, fine samples on the full span's own lattice) --
  and **`entry_roots`**, the bisected roots without the f32 band walk (an under-estimate BY
  CONSTRUCTION, so it prunes soundly and claims nothing; 2 roots at a rung where the genuine curve is
  empty).
- **AND RUNNING IT SAYS THE RE-CUT CANNOT WORK AS POSED -- IT IS NOT A RANKING PROBLEM.** 20592
  full-circle rolls off 3 banked c2 parents, every herd prune OFF: **51 carry her across the approach
  line, 12366 leave Link at runway >= 190, ZERO do both.** Deepest crossing roll ends at runway **89**;
  the entry curve starts at **190**. Carrying her across means rolling THROUGH her, which carries Link
  just as far past the corner.
- **THE EXCHANGE RATE IS THE USABLE FORM**: past ~150 u of runway the best crossing is dead flat at
  **+80.0..+80.4 u over six hundred units** (that is her FOLLOW, not a plow); below ~100 u the plow
  engages and it reaches **+196.2**. Knee at runway 89 (+12.9) -> 107 (-30.8). So a last roll that
  keeps the band buys **<= +80.4 u**, and **CYCLE 2 MUST HAND OVER ``l0`` >= -80.4** against the
  **-160.6..-183.4** it delivers. The whole remaining gap, stated one cycle up.
- **THE PLOW-THEN-WALK-BACK ROUTE IS PRICED, NOT FREE**: all 51 crossing rolls admit an entry curve
  (s125's "every on-side endpoint clips", re-confirmed on a fresh population), Link lands **112-238 u**
  out (median 217) = **7-14 frames** of retreat before any turn; best **97.35** vs banked 101 / floor 94.
  A SAMPLING statement (48 junction endpoints of 4382-8678, one `l_window`), not a frontier.
- **THRUST DOES NOT MOVE THE ENTRY BAND BUT BUYS 5 FRAMES.** ``cut_step = thrust + 2`` and thrust is
  just the B-press frame, but swept 6..16 the band's lower edge stays **~180-200 at every thrust**
  (Link must REACH the corner and brace before the cut -- s124's attractor); below thrust 9 nothing is
  genuine at any rung 30-400. What it buys is ``cut_step``: **thrust 9 cuts at 11**, still genuine,
  bound **92.50 vs 97.35** at the same endpoint. Cheapest single knob in this shape, never swept.
- **TRAPS**: (1) a c2 node's own ``l0`` does NOT predict whether its children cross -- nodes 0 and 1
  sit at the SAME ``l0`` -183.41 and node 1 reaches +19.65 where node 0 reaches -27.10; the junction
  decides ([[infeasible-needs-proof]] -- I called node 0 dead off 12 endpoints of 4622). (2) **The
  runway band alone is a useless filter**: rolls landing at runway 240 routinely sit **322 u** off the
  approach line sideways. Always ask `handoff.endpoint` for the gap.
- **AND THE c2 REQUIREMENT IS ON THE CYCLE, NOT ON ITS AIM (preflighted).** `beam_io.split_last_roll`
  re-opens each banked c2 terminal at its PRE-ROLL endpoint (0-ULP, re-fired) and the FULL aim circle
  from there moves the handoff by only **-10.3..+18.2 u** -- best ``l0`` **-159.4** vs the -80.4 needed,
  and several nodes' best re-aim is WORSE than what they bank. The roll buys ~+89-118 u off that state
  however it is aimed, so **the crossing must come from the JUNCTION** (Link repositions without a
  400 u commitment) -- the same conclusion `roll_candidates` reached about the LATERAL one cycle down.
- **PERF IS THE NEXT SESSION'S WORK (Dereck, end of s126: "we need to attack this more aggressively
  with raw compute").** Benched, three engines on the SAME coupled frame: `seeds.make_freerun` (Python,
  wired camera/zl1/neck -- **what the herd search runs on**) **2431 steps/s**; `make_freerun_native`
  (same frame in C, camera STRIPPED) **106294 steps/s (43.7x)**; `ShoveCtx.sweep_par`
  (`tww_sim/core/_shovec.pyx`, compiled roll, parallel) **130137 ROLLS/s = 2.08M frame-steps/s (857x)**.
  So Dereck's remembered 100k/s is REAL and IS in this repo -- it is the razor engine, and the herd
  search was never moved onto it; a 100k-aim sweep costs **~21 min single-threaded** and every
  wall-clock figure from s102 on is inflated by that. Python step split: **anim/pose 33%, camera 22%,
  land 9%, zl1 look 9%, push/cc 7%, math 6%, neck 4%**. **Stage split at `probe_cap=250`: junction 16%
  / roll 84%**, and a roll is **FACING-LOCKED** (main stick inert), so 84% of a search stage needs NO
  camera -- exactly what ShoveCtx already does. ORDER: (1) write the 0-ULP gate vs
  `two_roll.roll_segment` FIRST, (2) port the herd roll onto a ShoveCtx-class kernel (~6x/stage),
  (3) port `LandCamera`+`NeckLook`+`Zl1Look` into the native step for the junction's 16% (~25-30x
  total), (4) parallelise the rest (a node IS its input log, so workers rebuild from logs).
  **THE PORT MUST NOT DROP**: the roll's **exit csangle** (the C-stick IS live during the roll slewing
  to `target_cs`, and the next junction's aim alphabet is placed against it -- looks 0-ULP on one roll,
  corrupts every chain of two), `talk_unsafe`, and `ok`/`roll_speedF` (prune predicates, not
  diagnostics). Benches: `_notes/s123_bench.py`, `s126_perf_profile.py`, `s126_stage_split.py`.
- **QUEUED BEHIND THE PERF WORK = RE-CUT CYCLE 2 AGAINST ``l0``** (target >= -80.4 while keeping Link's runway).
  `handoff.tetra_lateral` is FREE, so unlike the terminal rank this one can go at the per-aim SCREEN -- and it is the JUNCTION stage that must be re-cut, not the aim fan (`junction_beam`'s `box`/`corridor` keeps are HERD constraints and the last two cycles are no longer herding),
  which is the cut that decides which endpoints exist (s107). Then re-run the s126 endpoint rank on
  cycle 3. Beside it: **thrust 9-11** for the clip roll, and a FACING sweep AT that thrust (40835 was
  solved for 14, and the facing window is ~one value wide).

## s127 -- THE ROLLOUT RUNS IN C, AND THE EYE WAS THE ONLY THING KEEPING IT IN PYTHON

**The s126 perf ORDER above is OVERTURNED by measurement -- do not chase the ShoveCtx port.** The
gate was written first as instructed (`tests/test_roll_kernel.py`, 14, runs by default: a fan kernel
vs `two_roll.roll_segment` on the WHOLE record over 4 configs x 6 seeds x 24 aims, `==`), and what
the measurements said changed the design three times:

- **The camera never needed porting.** Through a roll segment the committed csangle sequence is
  **bit-identical across a full 143-aim fan**, on every node and every C-stick mode. A fan pays for
  ONE camera. (The C-stick TARGET does move it -- gated -- so this is a lever, not a dead camera.)
- **The blocker was Tetra's proc-9 re-aim EYE.** `_step_native` was already the wired step 0-ULP given
  (csangle, eye); her feet instead of her eye costs 180 BAM of re-aim and **123 u** over a node log.
  Her `Zl1Look` needs Link's exec-pass ``mHeadTopPos.y`` and `NeckLook` needs his cached head MATRIX --
  both needed the Python pose FK, and **both were already computed in C**: joint 15 is posed with the
  body-Co extras, so ``HEAD_CHAIN`` is ONE concat past the Co-centre chain the engine already walks.
  `LandCore.head_top_exec`/`head_mtx_exec` + `PoseEngine._head_top`/`_head_mtx` (~120 lines,
  `tests/test_native_head_top.py`, 4 gates) -- and the port touched NEITHER subsystem the profile named.
- **`seeds.make_freerun_self_eye`** = the coupled frame in C generating its own eye
  (`from_f0._step_native` self-eye mode; the constructor's blanket refusal is now camera-only).
  **2796 -> 10797 steps/s (3.9x)**, 0-ULP on Link, Tetra, the eye and m3564 + a cloned run
  (`tests/test_freerun_self_eye.py`). `roll_kernel.roll_fan`: a 143-aim fan **1.05 s -> 0.29 s (3.6x)**.
- **A ROLL SEGMENT IS 20 FRAMES: 1 A-delivery + 16 `FRONT_ROLL` + a 2-frame proc-9 tier + 1 MOVE.**
  Only the middle block bakes (with no contact Link's step equals the constant-momentum step to
  EXACTLY zero error), so a ShoveCtx-class kernel caps at ~5x on a segment however fast it is, and the
  exit tier re-aims off her EYE, which a schedule cannot supply. s126's "84% at ~500x = ~6x" is right
  about where the time is and wrong about how much of it bakes.
- **NEXT = PORT `Zl1Look` + `NeckLook` INTO THE NATIVE STEP.** The ratio names it: stripped native is
  98179 steps/s and self-eye is 10797, so the two Python look models are **~89% of the step** (~9x
  more) and nothing else in the frame is worth looking at. Then: fan kernel into `full_herd._roll_stage`
  (have it RECORD csangle as it steps instead of `wired_csangle_trace` replaying); then the junction,
  which needs `LandCamera` fed from the core (one more export, ``attn_y`` = `fadds(92.5, ff.base[1][3])`);
  then parallelise (`CourtyardFleet.run_par` exists and is bit-identical parallel-vs-sequential).
- **TRAPS.** (a) **A cycle TERMINAL cannot roll at all -- all 143 aims TALK** (`a_press_is_talk` is a
  property of (node, first input), not of the aim), so seed anything about rolls from JUNCTION
  endpoints; terminals are the only place the `talk_unsafe` branch can be gated. (b) **Never quote
  98179 as the search's speed** -- `make_freerun_native` is a DIFFERENT simulation (feet fallback).
  (c) The twin's camera is injected a frame LATE and an off-by-one is silent -- gate the twin against
  the wired node before any fan runs off it. (d) The proc-`*_init` zero-lean convention differs by
  1.4 u in x / 3.4 in z on frame 1, and `FreeRun.step` consumes its own init flag, so track it yourself.
  (e) The record owes ``followed`` too -- `two_roll.alive` prunes on it.
- Rebuild after pulling: `python _build_native.py _anmc`. KB:
  `knowledge/model/the-eye-was-the-only-thing-in-python.md`, `knowledge/strategy/the-fan-pays-for-one-camera.md`.

## s128 -- THE LOOK PAIR IS IN THE C FRAME; THE STEP IS 6.8x AND A ROLL FAN 18x

s127's next step, done. The ratio that named it (stripped 98179 / self-eye 10797 = "the pair is ~89%
of the step, worth ~9x") was right about the TARGET and wrong about the SIZE, and both halves matter:

- **MEASURE THE SPLIT BEFORE PORTING** (`_notes/s128_look_split.py`): her `Zl1Look` **77.5%** of the
  step, `NeckLook` **13.4%**, the C core itself **9.1%** -- and inside her frame `_pose_eye` is 71%
  (`pose_locals` alone 52%). So the port is mostly a DATA move: her keyframe bank becomes C-resident
  (`Zl1AnimData`) the way Link's `AnimData` already is, not a control-flow rewrite.
- **DELIVERED 6.8x, NOT 9x -- and always quote the delivered figure.** **9279 -> 62682 steps/s**; the
  look pair **97.4 -> 5.6 us/frame**. A "X is 89% of the step" ratio assumes the ported X is FREE. It
  is not: the pair is still ~35% of the step afterwards. The honest form is `1/(rest + ported)`, and
  the stripped run's 96k is a ceiling you approach and never reach.
- **WHERE THE SEARCH SPENDS**: `roll_kernel.self_eye_twin` defaults to the native-look twin, so
  `roll_fan` gets it (+ `record=False`, since the fan reads the endpoint off the run, never the row).
  A 143-aim fan on the s127 unit: **1.05 s wired -> 0.29 s (s127) -> 0.057 s**; the full 5600-aim
  `roll_aim_fan` grid **41.0 s -> 2.24 s**, records `==` the reference.
- **`tww_sim/core/anim/_zl1c.pxi`** (new), `include`d into `_anmc.pyx` because it runs inside
  `_step_courtyard_nogil`. `LandCore.seed_look`; `FreeRun(native_look=)`; `seeds.make_freerun_native_look`.
  Constants are handed to C from the Python models at arm time (`from_f0._arm_look_consts`), never
  re-declared in the .pxi. Gates `tests/test_native_zl1_look.py` (7).
- **THE PARALLEL PATH IS DE-RISKED**: `CourtyardFleet.run_par` carries the chain bit-identical to
  sequential (gated). Its csangle spread must be WIDE -- at 1 BAM eight cores land on three distinct
  Link positions, Tetra does not move differently at all, and every eye is identical, so such a gate
  would pass without the look chain running at all.
- **TRAPS.** (a) **The recorded window does not exercise her**: over the 45 movie frames `f84d == 1`
  every frame and `f7b8` is seeded at **116**, so the look-around anim switch, the morf blend it
  starts, the wrap flag and the RNG horizon are ALL past the end of the fixture -- gate on a LONG
  window and assert the coverage. (b) **Compare the hidden state, not the output**: her morf's
  per-joint OLD-POSE STORE is rewritten every frame and only reaches the eye through the NEXT blend,
  so a wrong store is silent for one frame and then diverges. (c) **Two ~2^-32 FP traps**: the models
  reach `absXZ` through `collision.fsqrt` = a CORRECTLY-ROUNDED sqrt, while `_anmc` also carries
  `_sqrtf_c` (the MSL `frsqrte`+3-Newton `std::sqrtf`); and her NON-morf pose is
  `J3DGetTranslateRotateMtx` off the EULER while storing the euler->quat for the next morf -- not the
  same matrix in the low bits, so the paths cannot be merged. (d) `FreeRun._eye_next`/`_tattn`/`neck`
  are now PROPERTIES (live views on the C state); `self.zl1` stays the SEED object -- read the live
  state via `zl1_snapshot()`. (e) The honest step rate is **62682**, never the stripped 96k.
- **NEXT** = put the fan kernel in `full_herd._roll_stage` (have it RECORD csangle as it steps rather
  than `wired_csangle_trace` replaying); then the junction's own step (needs `LandCamera` fed from the
  core -- one export, `attn_y` = `fadds(92.5, ff.base[1][3])`); then parallelise.
- Rebuild after pulling: `python _build_native.py _anmc`. KB: `knowledge/model/porting-the-look-pair.md`.

## s129 -- THE SCREEN IS ON THE FAN KERNEL, AND IT NEVER NEEDED RUNS AT ALL

s128's next step, done -- and the shape came from reading what the stage KEEPS rather than from
profiling it:

- **`roll_candidates`' R1 DISCARDS EVERY RUN IT BUILDS.** It fires the aim fan x the L windows,
  ranks, and keeps three ``(want, aim, l_window)`` triples. What the prunes and rank read in between
  is NINE fields (Link XZ/facing/travel/speedF/proc, Tetra XZ, csangle, follow flag) and
  `roll_kernel.segment_record` already carries all nine -- so `RecordRun` presents a record in the
  shape a run is read in and `two_roll.metrics`/`alive`/`frame_in_model`/`rank_key` run over fan
  records UNCHANGED (no second expression of a prune to keep in step). R2 stays wired: its survivors
  ARE their runs (carried to the next cycle, stepped by `junction_quality`).
- **COUNTED, NOT TIMED** (load-independent): one cycle-1 stage **6719 wired steps -> 2251 wired +
  4566 native**. ~**17x on R1**, ~**2.8x on the stage** at the s128 engine rates -- the look-pair
  lesson again: the part that is 74% of the work returns 2.8x because the rest does not get cheaper.
  **All 2251 remaining wired steps are R2.**
- **THE SEED WAS THE HARD PART OF THE GATE.** Off EVERY banked cycle-2 junction endpoint the stage
  returns NOTHING at any thinning -- from ~40-70 u behind her a ~205 u `FRONT_ROLL` ends **231-253 u**
  away, past `FOLLOW_ENGAGE_DIST`, so `alive` prunes on ``followed`` (the few inside it end AHEAD of
  her -> ``lead``). Both implementations agreed about nothing. The firing seed is cycle 1's own
  PROLOGUE node (state 2 + one L-held flip frame, 5 candidates). ALWAYS assert non-vacuity.
  Gate `tests/test_fan_stage.py` (8).
- **TRAPS.** (a) The screen's sort is STABLE, so ties break by INSERTION ORDER, and the fan evaluates
  per L WINDOW while the wired loop walks (aim, window) -- walk the wired order. (b) A twin is exact
  about whatever state it reaches: *a node IS its log* now holds at RUNTIME via
  `node_twin(check=run)`. (c) `aim_keep=1` empties cycle 1 unless `require_quality=False`. (d) The
  gate's fan CANNOT be thinned for speed -- at `step=16` cycle 1 returns nothing (the survivors are
  three (aim, window) pairs, all the SAME aim).
- **THE s128 csangle-RECORDER STOPGAP STAYS, measured**: the wired replay is one ~55-frame log
  against ~216 roll segments = a few percent of the stage, vs a change to every log-append site.
- **NEXT = R2's SHARED ROLL BODY**, named by the module's OWN gated fact `target_cs_is_exit_only`
  (inside a roll the camera target changes nothing but the camera): the 25 rollouts per kept aim are
  the SAME physics 25 times and differ only in the exit tail. NOT a fan -- fanning over tcs is a LOSS
  (a camera trace is 32 wired steps vs a 20-step rollout and cannot be shared across camera targets).
  Needs a DIVERGENCE-FRAME gate, not the assumption.
- **PROCESS LESSON (cost ~40 min): never run the full suite while editing the tree.**
  `test_kb_hygiene`/`test_code_hygiene` rglob `knowledge/` and `tww_sim/` at RUN time, so a long run
  reads a moving tree -- six `test_cloud_land.py` failures appeared that reproduce nowhere (49/49
  clean). Run subsets while working; the full suite when the edits are done.

## s130 -- THE CAMERA-TARGET PASS SHARES THE ROLL; THE BRANCH IS READ, NOT SET

s129's next step, done -- and the two things that decided the design were both MEASUREMENTS that
overturned the obvious move:

- **THE DIVERGENCE FRAME IS THE ROLL'S OWN END.** Over the real 25-value tcs grid x 5 aims x 3 L
  windows: physics bit-identical for **17 of a 22-frame segment**, first difference exactly at the
  first non-`FRONT_ROLL` frame. So `roll_kernel.SharedBody` READS ``branch`` off the roll as it
  steps (right for whatever this node's roll is) instead of taking a constant. The gate
  (`tests/test_tcs_kernel.py`, 7) asserts SAFETY (nothing before it depends on the target) and
  TIGHTNESS (something diverges AT it) separately -- per aim it can be later, or NEVER (a roll
  ending in proc 6 with Link stopped has nothing left for the camera to steer), so tightness is a
  population claim. The branch is a complete swap because the only stored csangle-carrying state is
  `m34E8`, recomputed by `setStickData` every non-neutral frame. 250/250 branched segments `==`.
- **ONE FROZEN BODY'S CAMERA ARGS SERVE THE WHOLE FAMILY, PAST THE DIVERGENCE** (0-ULP on every
  target's committed csangle over the whole segment) -- `FreeRun`'s "csangle is position-independent
  in this regime" cashed in. Walked as a PREFIX TREE (same C-stick bytes so far = same camera
  object): **775 -> 529** camera steps. `FreeRun.step` publishes ``sim_cam_in`` so the walk reads the
  pad law through the run's own expression, not a copy.
- **THE FAN WAS THE WRONG LEVER TWICE.** (a) Fanning over tcs is a LOSS (a camera trace ~32 wired
  steps vs the 20-step rollout). (b) **A NATIVE ENDPOINT CANNOT BE STEPPED BY THE NEXT STAGE** --
  and the gate that said it could was VACUOUS: `junction_quality` matched native-vs-wired 250/250,
  which was two `None`s 250 times (`scored 0/25` on that node). Behind the tie the glide differs
  (1 of 25, 0.009 u) because **a centred C-stick does NOT freeze csangle on the spot -- the camera
  chases for several frames**. `slew_substick`'s "neutral FREEZES csangle" is the STEADY STATE. The
  same wrong assumption as a walk shortcut collapses 775 camera steps to 10 and is off by 178 BAM at
  frame 5. ALWAYS count a green comparison's non-vacuity before believing it.
- **DELIVERED** (counted, at the aim step s129's row used, so the rows compare): **2251 wired + 4566
  native -> 1030 wired + 4566 native + 701 camera-only; 1.088 s -> 0.629 s (1.73x)**; 4.82x vs the
  all-wired stage; same 5 candidates. At `cycle1_nodes`' shipped aim step (2x the fan): 11235 ->
  1030 wired, 4.871 -> 0.719 s (**6.78x**) -- R2's cost does not grow with the fan.
- **DROP-IN, and it works on EVERY cycle** (a genuine wired run at the genuine endpoint, so
  `junction_quality` / ``tcs_probe`` / ``tcs_key`` / the next junction are untouched).
  ``shared_body`` defaults on wherever ``env``/``twin`` is; `tests/test_fan_stage.py` now runs R1
  and R2 alone AND together so two ports cannot cancel.
- **NEXT = the camera itself.** **654 of the surviving 1030 wired steps (63%) are
  `junction_quality`** (6 frames x 3 sticks per surviving target), 376 the bodies and tails. It is
  wired precisely because the camera is still chasing during those 6 frames -- so the cut is not
  another sharing trick but `LandCamera` driven from the C core (the one export queued since s127,
  ``attn_y`` = `fadds(92.5, ff.base[1][3])`), which also unlocks the junction's own step.
- KB: `knowledge/strategy/the-shared-roll-body.md`. No `.pyx` change, no rebuild needed.

## s131 -- THE CAMERA RUNS ON THE C FRAME; THE BLOCKER WAS A GUARD, AND THE STAGE IS ZERO WIRED

s130's next step, done -- and the two things worth carrying forward are both about what a queued
port and a moved engine actually mean:

- **THE QUEUED EXPORT WAS NOT THE BLOCKER.** Four handoffs (s127-s130) carried
  ``attn_y = fadds(92.5, ff.base[1][3])`` as *the* thing standing between the search and a native
  camera. Measured first (`_notes/s131_attn_y.py`), over 90 frames across procs 6/7/9/30: that row
  **is** Link's world Y exactly (the lean concat has a zero translation column), `m35C4`/`m35B8`
  both read 0.0, his Y never moves -- **one distinct value**. What actually held it was a
  `ValueError` in `FreeRun.__init__` ("native_step cannot drive a LandCamera"), true only because
  nobody had wired one into `_step_native`. **Measure the value a queued port waits on before
  building it, and re-read old guards -- they are true on the day they are written.**
- **EXPORTED ANYWAY, FROM THE ENGINE THAT DREW THE FRAME.** `LandCore.attn_y` reads
  `PoseEngine._base` live rather than hardcoding: the row is `setAttentionPos`'s
  (`d_a_player_main.cpp:10271`), so a ground model that ever moves Y carries the camera with it. The
  gate asserts it against the WIRED `FootFK`'s own row per frame -- "the C base tracks the Python
  one", not "92.5+Y is 92.5+Y", which would pass by construction.
- **DELIVERED** (counted, same stage/knobs/prologue as the s130 row): **1029 wired + 9083 native ->
  0 wired + 10112 native**, **0.681 s -> 0.354 s (1.9x)**, **13.6x** vs the all-wired stage, same 5
  candidates. The camera model runs equally often either way (1731 steps) -- only the frame around
  it moved. `seeds.make_freerun(native=)` is the switch; `cycle1_nodes(native=True)` (default) /
  `chain_herd(native=)` hand it to the chain, since a node's run is what every later stage steps.
- **MOVING THE ENGINE MOVED WHAT `run.link` MEANS** (a gate caught it, `test_freeze_bar_is_the_co_
  radii_sum`): on a native run it is a FIELD-HOLDER synced from the core, so `run.link.pos_x = ...`
  is a **silent no-op** and `_computed_center(run.link)` answers off the **f0 SEED pose**. Fixed on
  the object: `FreeRun.co_center()` (all six run-level callers routed through it) and
  `FreeRun.place_link()` (the teleport recipe, which existed in three copies); second export
  `LandCore.co_center_exec(init_frame=)`. **NEVER poke `run.link` directly again.**
- **A CORRECTION DELIBERATELY NOT MADE**: every run-level caller reads the centre with
  `init_frame=False` while the core knows the frame's true `*_init` flag (~1.7 u apart at the seed
  frame). The export takes an override so the port reproduces the approximation EXACTLY -- fixing it
  moves search-visible numbers and is its own change with its own gate.
- **TRAPS.** (a) `record=False` means different things per path and now says so (wired: forbidden
  with camera/zl1/neck, which run AFTER the row and were silently frozen; native: only skips the
  row). (b) A running pytest HOLDS `_anmc.pyd`, so a rebuild silently fails ("Access is denied") and
  the next run imports the OLD engine against NEW Python -- surfaces as a `TypeError`, not a build
  error. (c) `test_kb_hygiene`'s code-path regex stopped at `.py`, so `.pyx`/`.pxi` paths were
  uncitable; now `(?:pyx|pxi|py)` -- longest-first, since Python alternation is leftmost-first.
- **NEXT = STEP FRAMES IN C (`CourtyardFleet`), AND THE CAMERA COMES WITH IT** -- profiled, not
  assumed (`_notes/s131_profile.py`). Priced idle against the 0.354 s stage: the coupled frame
  **10.9 us** x 10112 = **31%** (C 8.2 + a 2.7 us Python wrapper), `LandCamera.step` **44.0 us** x
  1731 = **21%**, and **~48% is the stage's own Python glue** (clones, per-frame input dicts,
  prunes, metrics, sorts). So the camera is 4x a frame PER CALL but not the biggest bucket, and the
  C engine is a minority of its own search stage; the fleet removes the wrapper + glue and needs the
  camera in C to carry a camera run -- ONE piece of work. **Do not price a hot call with cProfile:**
  it charged `_step_native` 13.2 us/frame of own time; a loop says 2.7. KB:
  `knowledge/model/the-camera-on-the-native-frame.md`. Rebuild after pulling:
  `python _build_native.py _anmc`.

## s133 -- THE STAGE FIVE SESSIONS WENT INTO IS 2% OF A CYCLE; A NODE'S 274 CHILDREN ARE ONE FRAME

The queued next step (`CourtyardFleet`) was a ROLL-stage port. Measured first -- s131's own lesson
applied to the profile that named the port rather than to the port -- and it does not survive:

- **THE RATIO THAT AIMED s127-s131 WAS STALE BY CONSTRUCTION.** s126 measured a cycle at **junction
  16% / roll 84%**; the roll then got 13.6x faster. Re-measured on one banked cycle-2 parent
  (`_notes/s133_junction_cost.py`): **junction 99.2% / roll 0.8%** as shipped, 95.5/4.5 native. The
  queued port addressed **2%** of a cycle. **A profile is a statement about the code on the day it
  was taken -- after any port worth doing, re-measure the split that justified it.**
- **AND s131's "~48% GLUE" WAS A MISATTRIBUTION**: timed by section, the roll stage's
  prunes/metrics/sorts/keeps are **2.0%**; 52.8% of it is four camera-bearing R2 blocks (
  `camera_walks` 17.7, `junction_quality` 22.5, `tcs_segment` 9.9, `SharedBody` 2.7) vs 44.9% fan.
- **A CAMERA-BEARING NATIVE STEP IS 120.6 us AND THE C FRAME IS 10.8 OF IT**: `LandCamera.step`
  **80.1 us at a junction state** (46.2 at a roll state -- a junction's stick is live every frame),
  `cam_pad` 8.3, the row 7.3. Camera = **66% of a junction step**, junction = 98% of a cycle, so the
  camera is ~2/3 of the whole herd search.
- **THE CHILDREN OF A NODE ARE ONE FRAME, STRUCTURALLY.** In `_step_courtyard_nogil` the incoming
  `sx`/`sy`/`buttons`/`triggerL` appear in exactly TWO places -- the signature and the `_cbuf` write
  -- so at `input_delay=1` a delivered letter cannot touch its own frame. Measured beside the proof:
  all **274** children land in ONE physics class and ONE csangle class, every generation.
  `FreeRun.fork_pending` + `full_herd._expand`: steps **91516 -> 26815**, beam identical endpoint for
  endpoint. `set_pending_input` is the other half (`LandCore.pre_seed_courtyard` is the buffer's
  setter and is safe mid-run; `_cbuf[4]/[5]` are never read on the courtyard path).
- **A PROBE HAS NO NEXT FRAME**: `two_roll.junction_gates`' arming probe steps with the camera
  detached + this frame's csangle injected. The look pair STAYS -- her eye steers the proc-7/9 re-aim
  and therefore the `speedF` the gate reads.
- **THE CHEAPEST CUT WAS A STALE DEFAULT**: `beam_io.rebuild_beam` built nodes with
  `make_freerun(env)`, `native=False` -- so the campaign's dominant stage ran on the **411 us**
  Python step because a camera run could not be native until s131. **When a flag's justification is
  removed, sweep its defaults.** `rebuild_beam(native=)` now defaults ON.
- **`stick_for_bearing` MEMOISED**: its octagon-clamp fallback scans up to 529 clamped decodes,
  **2.8 ms a call** vs ~30 us analytic, and `junction_alphabet` re-asks a FIXED bearing ladder per
  node per generation. Pure fn + immutable return -> exact. Alphabet **6.28 -> 2.40 ms**.
- **A SEED IS SHARED, NOT DEEP-COPIED** (Dereck chose to keep going on compute; the cuts above had
  promoted `FreeRun.clone` to 58% of the stage). A port leaves the Python object behind as a SEED and
  the clone was still deep-copying three: `link._foot` = the f0 pose the core replaced (**9.5 us**,
  2/3 of the `LandState` clone) and, under `native_look`, `zl1`/`neck` = what `LandCore.seed_look`
  was built from (**6.7 us**). Shared ONLY where the path provably never writes them --
  `LandState.clone(share_foot=)` REFUSES when `_core` is set. Native clone **30.8 -> 12.2 us**, wired
  untouched 27.4. **The camera is deliberately still cloned -- it runs in Python AFTER the frame, so
  it is state, not a seed.** General rule: **after a port, audit what the old object still copies.**
- **THE PRUNE BELONGS TO THE NODE**: `followed`/`wall`/`outbox` all read the SHARED frame, so
  `_shared_frame` decides them once and a dead node costs ZERO child clones (**91516 -> 71477**).
  Gated as the CLAIM (every child's verdict == the shared frame's, both engines), not the consequence.
- **DELIVERED: 53.8 s -> 4.4 s (12.2x)** on 98% of a cycle (the cycle 52.6 -> 4.8 s), endpoints 0-ULP
  throughout. Full suite **1:05** green. Gates `tests/test_fork_pending.py` (6),
  `test_native_junction.py` (6+1 slow), `test_stick_for_bearing_cache.py` (3). No `.pyx` change, no
  rebuild. Commits 061fb3d + f344017.
- **THE SEARCH PATH RE-MEASURED END-TO-END (`_notes/s133_search_smoke.py`), and the starting line is
  now on record**: c2 parents `l0` **-183.41** (reproduces s126 exactly) -> cycle 3 **-56.66** at 70 f
  (shipped screen) / **-27.10** at 74 f (s126 contact screen, 3x the time), ALL `onside=False`. So the
  last roll already buys **+126..+156 u**, past the +80.4 s126 measured as the band-keeping cap, and
  still lands short. **-27.10 is the number to move.**
- **TRAP THAT WOULD COST AN HOUR: `extend_cycle` AT BARE DEFAULTS RETURNS ZERO SURVIVORS** off a
  banked c2 parent (250/250 `unrollable`). NOT a regression -- identical on both engines -- it simply
  needs what `chain_herd` passes: the handoff `corridor`, its `resid`, `target_along`, `arrive_keep`.
  With those: 3 survivors. The working invocation is in `_notes/s133_search_smoke.py`.
- **NEXT = THE SEARCH (Dereck chose it explicitly at the end of s133)**: re-cut cycle 2 against `l0`
  >= -80.4 at the JUNCTION (via the FREE `handoff.tetra_lateral`, at the per-aim screen; question
  `junction_beam`'s `box`/`corridor` keeps -- herd constraints the last two cycles no longer obey),
  then the s126 endpoint rank on cycle 3; thrust 9-11 + a facing sweep. Affordable at **4.8 s a cycle**.
  The cheap compute cuts are TAKEN; of the 4.4 s left, clone ~1.4 / `junction_gates` ~1.37 / alphabet
  ~0.62 / step ~0.58, and the two remaining levers are both bigger changes: (a) ~26.5k arming probes
  each pay a clone+step to compute a frame the NEXT generation computes again (the probe's frame IS
  the child's next frame -- both act on its pending letter) while only ~24 children a generation
  survive the keep; (b) the alphabet is ONE `stick_for_bearing` (toward-Tetra, full deflection) whose
  bearing genuinely moves per node -> the 2.6 ms clamp search every time; its memo is ALREADY keyed on
  bearing MINUS camera, so that one needs a faster `main_stick_decode` in C, not a better key.
  **NOT `CourtyardFleet` -- it is a roll-stage port and the roll is now 1-9% of a cycle.**
- **TRAPS**: (a) a thinned junction beam is VACUOUS -- endpoints need FIVE generations (the arming
  pattern wants L two frames back), so `max_frames` 2/3/4 return zero and every equality gate passes
  on an empty beam; (b) `check-comment-length.sh --worktree` does not see NEW files -- an over-long
  `#` block in a new test only surfaces at `git commit`.
- KB: NEW `knowledge/strategy/the-frame-the-alphabet-shares.md`.

## s134 -- THE CROSSING WAS A CUT, NOT A DISTANCE; THE HERD PUSHES 64 DEG OFF THE ENDGAME'S AXIS

s126 reduced the endgame to ``l0 >= -80.4`` handed over by cycle 2 against the -183.41 it delivers,
and s126-s133 read that 103 u as unreachable. Measured this session, it is mostly a CUT:

- **THE TWO GRADIENTS ARE NOT EQUAL.** ``l0 = 0.4344838355514977*along + 0.900679541214783*lat
  - 411.99`` in herd coords, so **lateral buys 2.07x what down-herd buys**, and ``q`` (which IS the
  l0 axis) buys 1.0 against the herd's 0.43. The herd line is **64.25 deg** off ``q``. NOT a bug in
  the line -- it aims at the genuine-coord centroid and the 288 coords ARE on it (herd along
  937.5-984.1, lat -2.3..+7.9, l0 +2.50..+13.69). What changed is the TARGET: s123 deleted the
  walk-away, s125 moved the razor onto Link, so the ask is a HALF-PLANE plus a pair alignment, and a
  half-plane is reached fastest along its normal. Walls are not the ceiling (at along 579 a wall-free
  Tetra spans lat -190..+200 = l0 up to **+19.71**).
- **A NUMBER QUOTED OFF `nodes[:1]` IS A NODE, NOT A BEAM.** Every "-183.41" in the s126-s133 record
  is banked node 0. The 16-node beam spans **-263.83..-149.08**; cycle 1 hands over a single -286.88.
- **WHAT THE STAGE PRODUCES vs WHAT ITS CUTS KEEP DIFFER BY 93 u.** Contact screen, 8 banked cycle-1
  parents, 250 endpoints each -> population best **-90.39**. With the ``l0``-aware POOL, one parent at
  1000 endpoints -> **-63.15**, and **26 of 737 rolls clear -80.4**. THE BAR IS MET AT THE STAGE.
  Two structural reasons it was not: the pool screens **250 of 4292 (5.8%)** by a flatness prefix +
  jf spread, both blind to the axis; and the crossing rolls ride **25-86 u off the push corridor** at
  a positive lateral (winner: along 620.6, **lat +88.0**, jf 11) -- exactly what ``corridor_keep`` /
  ``align_keep`` / ``square_keep`` rank against. Those are HERD constraints; the last two cycles no
  longer herd.
- **THE PLOW CAGE IS THREE HERD-RELATIVE PREDICATES AND ONLY THE DIRECTION BINDS**
  (`in_pursuit_box`, `two_roll.alive`, `_frontier_score`). At the cycle-1 exit the pair is **58.91 u**
  apart -- inside the human's own recorded **40.4-85.2 u** plow band -- and in the box on the herd
  axis, while on ``q`` it reads lead -18.28 / lat +56.00 / delta +71.93 deg and fails ALL THREE.
  Freed to its coordinate-free content: **21x more surviving rolls**, coarse frontier -136.00 ->
  -120.71. Real, but the pool + keeps are the bigger lever.
- **SHIPPED (additive, default OFF)**: `roll_probe(pf=)` -> ``l0_max``/``l0_off``/``l0_along`` +
  ``l0``/``frames`` in ``collect``; `_probe_pool(l0_key=)`; `extend_cycle(l0_keep=)`. Gate
  `tests/test_l0_screen.py` (7 in 1.55 s + 1 slow re-derivation) against banked
  `fixtures/courtyard_l0_screen_nodes.json`. Suite **1140 green in 1:13**; regression set 124/124.
  Commit c83c16c. KB: NEW `knowledge/strategy/the-axis-the-endgame-is-denominated-in.md`.
- **THRUST 9-11 SWEPT, AND A CHEAP THRUST DOES NOT COST CONTACT** (the other half of the s133 next
  step). The facing window WIDENS from s125's one value (thrust 14) to **12-23 facings**; none of the
  cells found admit an UNBROKEN family, and that is the BOX, not the thrust. Measured: ``thrust``
  moves only WHEN the cut fires and the roll before it is **BIT-IDENTICAL** (traces at one cell agree
  through frame 10, first differ at frame 11 = thrust 9's ``cut_step``), and ``unbroken`` reads the
  PREFIX ``ov[:cut_step]`` -- so a shorter cut is strictly EASIER to keep unbroken (**+11.86 margin
  at thrust 9 vs +1.13 at 14** on the s124 cell). What moves is the genuine LOCUS (``lat`` +4.0..+7.4
  at thrust 14 -> +16.8..+27.8 at thrust 9). The coarse 135-cell box finds **1 unbroken where s124's
  1540-cell one finds 13**, so zero is NOT evidence of absence (`[[infeasible-needs-proof]]` -- I
  asserted the tension first and it does not exist). The FINE box at thrust 9-11 is the cheap open
  item, worth **4.85 frames**.
- **TRAPS**: (a) `[[infeasible-needs-proof]]` again -- the stage with the box evaluated about ``q``
  returns ZERO endpoints, because the pair leaves cycle 1 arranged for a herd-line plow and the box is
  a hard prune from generation 1; the regime transfers, the state must get there first. (b) A BIGGER
  JUNCTION CAN BE WORSE: ``max_frames`` 12->18 took endpoints 4292->12556 at a fixed ``probe_cap`` 250
  and moved the frontier **-120.71 -> -134.55** (a thinner sample of a larger space). (c) The
  roll-kernel fixture's 6 endpoints ALL die ``followed`` (>230 u) under `roll_probe`, and a flatness
  prefix over `uniq[:600]` finds ZERO rolling endpoints -- mint gate seeds through the real
  `_probe_pool`. (d) The contact fan is the cost and is IRREDUCIBLE (``step=4`` zeroes two of four
  seeds) -- bank the artefact, never coarsen the fan to make a budget.
- **A KEEP THAT REACHES TWO OF THREE CUTS IS ONE THE THIRD UNDOES.** The CHAINED re-cut (8 parents,
  cap=400) hands over **-160.62 at 48 f** -- better than node 0's -183.41, but short of the banked
  beam's own best (-149.08) and far from the -90.39 its population screens. DIAGNOSED, not guessed:
  re-opening each kept node at its pre-roll endpoint (`beam_io.split_last_roll`) and re-screening it,
  `roll_candidates` delivers exactly what that endpoint promised (**0.00 u lost at 3 of 4, one node
  +4.73 u** on the wider fan), and the kept nodes' endpoints screen at ``l0_max`` **-165..-269**. So
  the beam carries LOW-``l0`` endpoints and the leak is the **FINAL beam cut**, which sorts on the
  frame rank with no share for the axis. An ``l0`` share was added there (`extend_cycle`'s ``orders``,
  beside corridor/align).
- **END TO END: THE CHAIN CROSSES FOR THE FIRST TIME.** Cycle 3 off the re-cut beam: **6 of 8 ONSIDE,
  best `l0` +38.92 at 77 f, ALL 6 admit an entry curve** (s133 baseline: -56.66, onside False, gap
  inf -- no plan). Best **bound 100.06** = 77 herd + 120.00 u gap at the walk cap + 16 cut, vs banked
  console **101**, s125 floor **94**, s126 sampled plow-then-walk-back **97.35**. It found the
  PLOW-THEN-WALK-BACK route: the last roll buys **+199.5 u in 29 f** (deep-plow regime), Link ends
  120 u out. Cycle 2 handed over **-160.62**, UNDER the bar, and crossed anyway -- so **the -80.4 bar
  is a condition on the BAND-KEEPING crossing, not on crossing at all**.
- **THE BAND-KEEPING ROUTE IS REACHED, THEN REFUSED BY ONE CLAUSE -- `in_pursuit_box` IS THE CAP.**
  Dropping ``require_quality`` takes cycle 2 to **`l0` -51.75 at 52 f** (past the bar). Cycle 3 off
  those states = **ZERO survivors, every child `outbox` at generation 1**; the junction never starts.
  They fail ONLY the direction clauses: separations **58.84 / 63.86 / 64.64 u** -- dead centre in the
  human's own **40.4-85.2 u** plow band -- against ``max_lat`` 17.99 (they read -35.51/-49.24/-58.57)
  and ``max_delta`` 21.35 deg (they read -37.13/-49.63/-66.52). Ordinary plow pairs pointing 37-67
  deg off the herd line.
- **NEXT = promote the FREE-AXIS box from monkeypatch to a gated knob** (`_notes/s134_free_axis.py`,
  already measured: 21x more surviving rolls), then re-run cycle 3 off
  `_generated/s106/s134_c3_noquality_beam.json` (cycle idx 1 = the -51.75 beam). **Do NOT widen
  ``max_delta``** (`[[no-overtuned-constants]]`) -- keep every measured number and drop ONE
  assumption: the regime is "Link 27-128 u behind her, aligned to push" and the push axis is a
  PARAMETER (`reposition.HerdLine` already is that object). Then price it: 77 herd f is already 2
  over the 75 accepted, the band-keeping route starts at 52 cycle-2 f, and it must pay by driving
  ``gap`` from 120 u toward 0 (17 u = 1 frame).

## s135 -- THE PLAN IS 93.17; THE BOX WAS WORTH 6.9 FRAMES, BUT NOT ON THE ROUTE IT WAS FREED FOR

s134's next step, done. **NEW BEST BOUND 93.17** = 72 herd + 87.86 u of gap at the walk cap + 16
cut, off the DEEP-PLOW beam with the axis freed and s134's knobs otherwise identical -- **8 of 8
endpoints ONSIDE**, all admitting an entry curve, ``l0`` +10.41..+38.80, 2606 s. Against banked
console **101**, s134 **100.06**, s126 sampled **97.35**, s125 floor **94** (allowed to beat it:
that floor's herd term was 73, the all-out-push-to-a-COORD number, and s123/s125 replaced that
target with a nearer half-plane). Herd **72 f**, inside the OLD 75 bar. **A BOUND, not a plan** --
gap charged at cap speed, no turnaround, no guarantee of landing the 1e-4 u razor; roll entry is a
separate search. On the BAND-KEEPING route, though, the clause was a cap and not THE cap:

- **SHIPPED: THE PUSH AXIS IS A PARAMETER OF THE PLOW REGIME.** `reposition.AXIS_HERD`/`AXIS_PAIR` +
  `pair_line`; `full_herd.in_pursuit_box(axis=)`, `human_in_box(axis=)`, `junction_beam(axis=, pf=)`,
  `junction_quality(axis=)`, `roll_probe(axis=)`, `roll_candidates(axis=)`, `_frontier_score(pf=)`,
  `two_roll.alive(axis=)`, `junction_gates(axis=)`, `extend_cycle(free_axis=)` (one axis into all
  THREE prune sites). Default OFF everywhere. In the pair's frame ``lead`` is minus the separation
  and the lateral and bearing terms are zero by construction, so the box collapses to the human's own
  **26.8-127.8 u separation band** and costs one hypot.
- **GATED AS A RE-EXPRESSION, NOT A WIDENING** -- `tests/test_free_axis.py` (8 + 1 slow, 1.3 s) vs
  banked `fixtures/courtyard_free_axis_states.json`: the collapsed form equals the FULL three-clause
  predicate about `pair_line` over the banked states and 50000 swept geometries (0 mismatches); the
  human is inside it on every recorded frame; and it is **NOT a superset** (a far-lead corner at the
  full 18 u lateral is 129 u apart and the freed band refuses it -- ~0.06% of the sweep).
- **IT UNBLOCKS THE PRUNE AND ONLY THE PRUNE: 0 children -> 170428 JUDGED.** Cycle 3 off the
  band-keeping beam (`s134_c3_noquality_beam.json` cycle 1, ``l0`` -51.75 at 52 f) went from *every
  child `outbox` at generation 1* to a junction that runs -- ``outbox`` 60280 / ``in_cone`` 170428 /
  ZERO endpoints, 13 s. **The refusal MOVED. Read which counter went up.**
- **THE BINDING QUANTITY IS THE EXIT'S SLIDE.** The arming gate is ``|facing - bearing| > 90 deg``
  and it has TWO terms. From these exits Link's EBS backslide is **96-99% TANGENTIAL** to the line to
  her, so the bearing runs **15-19 deg/frame** while he turns; best-in-beam cone deficit **86.0,
  70.6, 69.0, 69.4, 72.3, 76.3** then the beam is empty, separation **64.6 -> 111.7 u** vs the band's
  127.8. The herd-passing control (``l0`` -152.14) slides **7% tangential**, bearing 1.8 deg/frame,
  deficit **83.0 -> 48.2 -> 14.6 -> 0.0** in three generations, holds for nine more.
- **AND THE TWO ARE ONE RESOURCE**: past the bar tangential **80-99%** / bearing 10.4-19.0 deg/f,
  short of it **3-36%** / 0.7-3.4 deg/f, ``corr(l0, tangential fraction)`` = **+0.960**. Mechanism,
  not coincidence -- ``l0`` is bought at 2.07x by LATERAL push and a lateral push is one delivered
  ACROSS the line between the bodies, which is the momentum that leaves the pair rotating. Read as a
  mechanism, NOT a law: 16 endpoints of one beam are ~5 distinct states (`[[infeasible-needs-proof]]`).
- **DERECK'S STEER, IN `objective.py`**: *"more than 75 herd frames is acceptable if it saves time
  overall."* Rule 2 is now about the TOTAL -- s60 wrote the 2-frame budget when the plan WAS the herd,
  and s123/s125 replaced the ending, so a plan costs herd + the gap Link must still close at the walk
  cap + the cut. `score_plan(total=)`, `TOTAL_INCUMBENT` = banked console **101**, and `verdict`
  accepts an over-budget herd whose TOTAL wins. Without a measured ``total`` the verdict is exactly
  the pre-s135 one.
- **NEXT = WIDEN ``probe_half`` AND RE-RUN THE 93.17** (below), then price the thrust-11 cut
  properly, then -- only if the band-keeping route is still wanted -- the RADIAL-EXIT KEEP at cycle 2
  (one dot product in the PAIR's frame, beside `l0_keep` at the same three cuts). The question it
  answers: over a POPULATION rather than one beam's 16 endpoints, is a high-``l0`` exit with a RADIAL
  slide reachable? If the +0.960 holds over the population, that route is structurally paid for with
  the arming posture and the plan is the deep-plow one -- which is now also the cheapest measured.
- **TRAPS**: (a) a search that still returns nothing has MOVED its refusal, not failed -- always
  print the dead-counter breakdown; (b) a two-stage sweep inherits the SCREEN's recall (the coarse
  handoff box keeps 1 of 17 facings at thrust 9 where the fine box finds 113 genuine at that one
  facing, and genuine cells sit at facings the coarse screen REJECTED); (c) the per-test budget gate
  is sensitive to CPU contention -- with two searches running, three pre-existing tests read 1.5-1.6 s
  against the 1.5 s budget.
- **THE SCREEN'S FAN WINDOW IS NOW THE CAP, AND IT IS THE NEXT STEP.** With the axis freed the
  junction yields **6850-9604** unique endpoints a parent (s134: 4292) and `roll_probe`'s
  ``fan_edge`` reports the furthest SURVIVING aim at **8.34-8.44 deg of the 8.44 deg half-window on
  every parent** -- ``probe_half=0x600`` is clipping the population it screens. Widen it (and
  ``probe_cap`` with it, s134's thinner-sample trap) and re-run the 93.17. Cheapest frames on the
  table: one knob, one re-run.
- **s134'S CHEAP ITEM ANSWERED, AND IT IS THRUST 11, NOT 9.** Full fine box, NO coarse screen, 17
  facings x 1540 cells a thrust: thrust 9 **133 genuine / 0 unbroken**, thrust 10 **46 / 0**, thrust
  11 **53 / 1**. s126's 4.85-frame thrust-9 hope is DEAD on the fine box; a family exists one rung up
  -- unbroken cells across **facings 40600-40670**, ``cut_step`` **13 vs 16 = 3 frames** off the CUT
  TERM (not off the bound: the entry curve moves with facing/thrust, so re-solve `handoff_pf`).
  **`terminal.RUNWAY`'s floor of 140 was CLIPPING it**: widened to 60-200 the family spans **130-160**
  and its own floor is 130, so s126's "the genuine band's lower edge parks at 180-200 whatever the
  thrust" is a THRUST-14 statement. A family that parks on the first rung of a swept range is the
  BOX's answer, not the family's -- widen before quoting an edge.
- **DON'T PIPE A LONG RUN THROUGH `tail`** (Dereck's steer, this session): it buffers to EOF, so a
  90-minute search shows nothing and a timeout loses everything. `python -u` + redirect to a log.

## s136 -- THE PLAN IS 89.82; THE CUT IS THE FRAMES AND THE RE-PRICE ALREADY KNEW IT

s135's three ordered items, all answered. **NEW BEST BOUND 89.82** = 72 herd + 81.89 u of gap at the
walk cap + 13 cut, re-searching cycle 3 with `handoff_pf` at the s135 unbroken thrust-11 family
(facing **40660**, thrust **11**, ``cut_step`` 13), every other knob identical to s135's -- **8 of 8
endpoints onside**, all admitting an entry curve, 1696 s
(`_generated/s106/s136_c3_t11_f40660.json`). Under banked console **101**, s135 **93.17**, s126
sampled 97.35, s125 floor 94. Still a BOUND: gap at cap speed, no turnaround, roll entry separate.

- **THE RE-SEARCH ADDS NOTHING OVER THE RE-PRICE, AND THAT IS THE FINDING.** Re-pricing s135's OWN 8
  endpoints in the new frame (`_notes/s136_thrust11_price.py`, ~4 min) gives **89.81**, the whole
  unbroken family is FLAT (89.81 at facings 40600/40610/40620, 89.82 at 40640-40670, gap
  81.77..81.89), and the 1696 s re-search returns the SAME winner / gap / ``l0`` +15.48. Junction
  death counters byte-identical to s135's. So the 3.35 frames are the TERMINAL, not the herd -- cut
  term 3, shorter roll's own entry curve the rest. **RE-PRICE BEFORE RE-SEARCHING**: when a change
  moves a TERM of the objective rather than the reachable set, price the banked endpoints first.
- **THE FAN WINDOW IS BINDING (s135 was right) AND THE WIDTH IS NOW MEASURED.** Swept at
  `pursuit_box`'s ``max_delta`` (+-21.35 deg) with the endpoint pool held fixed, 5 parents:
  **28.4%** of surviving aims outside the shipped +-8.44 deg, best screened ``l0`` **+117.58 ->
  +140.76** (+23.17 u), **306 of 1250** endpoints take their best ``l0`` from outside, population's
  own edge **~16.4 deg** (16-24 band = 77 aims of 34639 at a third the l0). Cost linear in width,
  ~2.5x the stage. **The re-run needs NO new constant**: drop ``probe_half`` and `probe_contact`
  supplies `max_delta`.
- **AND THE TRAP THAT NEARLY KILLED IT: A CHEAP SAMPLE IS BIASED TOWARD THE PARENTS THAT CONTRIBUTE
  NOTHING.** Parents 0-1 return ~1258 junction endpoints against 8510-8662 for parents 2-4, put
  **0.6-1.4%** outside the window against 22-40%, and their outside aims are strictly DOMINATED
  (l0 -89.94 vs +20.60, rate 10.995 vs 12.819, arrival 113 u vs 0.05). Two independent parents gave
  a clean, confident, BACKWARDS verdict. Sample parents by what they CONTRIBUTE, not by cost.
- **A SECOND RUNWAY BOX WAS CLIPPING THE GAP TERM.** `handoff.RUNWAYS` (the rungs `entry_roots`
  solves on, so the range every chain-back ``gap`` is measured against) floored at **190** on an s124
  scan reported empty below it; solved directly over rungs 60..320 the curve reaches **170** -- worth
  +0.15 f at thrust 14, +0.29 at thrust 11. Shipped **160** (one rung under the measured edge),
  banked `fixtures/courtyard_entry_locus_floor.json` (32 records, BOTH beams, both terminals), gated
  `tests/test_handoff.py::test_the_runway_box_does_not_clip_the_entry_curve`.
- **ONE BEAM IS NOT A POPULATION FOR A BOX EDGE EITHER**: the floor re-set from the s135 beam (bottoms
  out at rung 180) came straight back clipping on the s136 beam (reaches 170) -- the re-search's own
  first-rung self-check caught it. General form, now in the KB: **a swept range should hold one rung
  the population does not use**, so it proves its own edge every run.
- **THE ``-80.4`` BAR IS A THRUST-14 NUMBER** still printed beside thrust-11 screens. The runs are
  self-consistent (l0 / `l0_keep` / sign prune all ride the thrust-11 `PairFrame`); only the
  annotation is stale. But a SHORTER roll should buy LESS crossing, so the bar cycle 2 must clear may
  have moved AGAINST us at exactly the terminal that just saved 3.35 frames. Re-derive it (s126's way).
- **NEXT** = re-run the 89.82 at ``max_delta`` (~70 min), then the -80.4 bar at thrust 11, then
  ``probe_cap`` (250 of 8510-9604 is **2.6-2.9%** -- the window fix widens what each PROBED endpoint
  reports and does nothing about the 97% never probed), then s135's radial-exit keep.
- KB: NEW `knowledge/strategy/the-window-binds-on-the-parents-that-produce.md`. Suite **1151 passed,
  3 skipped, 8 xfailed in 1:01** (quiet).

## s137 -- THE WINDOW BOUND THE SCREEN, NOT THE PLAN; AND THE BAR BELONGS TO ITS TERMINAL

s136's two ordered items, both answered, both NEGATIVE in the useful way. **BOUND UNCHANGED AT
89.82** re-searched at `pursuit_box`'s ``max_delta`` (+-21.35 deg), every other knob held
(`_notes/s137_c3_maxdelta.py`, 2741 s, `_generated/s106/s137_c3_maxdelta_t11_f40660.json`).

- **THE FRONTIER DOUBLED AND THE OBJECTIVE DID NOT MOVE A DIGIT.** Roll survivors **426 -> 504**,
  best screened ``l0`` on the producing parent **+71.77 -> +146.32**, best-of-beam ``l0`` **+42.11 ->
  +55.40** -- bound **89.82 = 72 herd + 81.89 u gap + 13 cut, bit-identical to s136's**. Six of eight
  beam nodes come back unchanged including the winner (``l0`` +15.48); the two that moved are the
  high-crossing corner, +6.16 frames real (103.00 -> 96.84) and still seven behind.
- **BECAUSE THE SCREEN'S RANK AND THE STAGE'S OBJECTIVE ARE DIFFERENT AXES.** ``l0`` is the CYCLE-2
  requirement's axis; cycle 3 is priced ``frames + gap/walk cap + cut_step`` and its winner is a
  LOW-crossing endpoint that wins on a SHORT GAP. The s126 exchange rate governs cycle 3's own beam
  too -- buying crossing costs gap. **GENERAL LESSON: before buying recall on an axis, check the axis
  predicts the thing being minimised.** s136's measurement was right in every particular and the
  lever was still empty.
- **AND THE NULL NAMES THE REFUSAL, ON BYTE-IDENTICAL COUNTERS.** Across two very different screens
  five counters do not move a count: ``unarmed`` **429724**, ``in_cone`` **314542**, ``outbox`` 6576,
  ``wall`` 26304, ``ENDPOINT`` 73070 (only fan-dependent ``aim_followed`` 341777 -> 885403 and
  ``unrollable`` 874 -> 90 change). **ARMING refuses, identically, under every screen knob tried.**
  Window CLEARED (widest survivor 16.41-19.49 deg inside a 21.35 box) and runway floor CLEARED.
- **THE ``-80.4`` BAR IS A TERMINAL'S, NOT THE PROBLEM'S: -77.83 at thrust 11 / facing 40660**, i.e.
  **2.6 u AGAINST us at the terminal that saved 3.35 frames**. Re-derived WITHOUT firing a roll:
  ``l0``/``runway`` are affine projections of banked WORLD positions, so s126's 20592-roll census
  re-reads in any frame exactly (`_notes/s137_bar_thrust11.py`). **The licence is the round trip** --
  it returns -80.44 in the frame it was measured in. Family spans -76.87..-77.83. Structure survives
  (67 rolls cross vs 51; all still leave Link at runway <=89, so ZERO still do both). Banked 11
  terminals `fixtures/courtyard_crossing_bar.json`, read via new `handoff.crossing_bar(pf)` which
  returns **None** for an unmeasured terminal (never a neighbour's number); gated
  `tests/test_handoff.py::test_the_crossing_bar_belongs_to_its_terminal_and_an_unmeasured_one_says_so`.
  Bar is FLAT in the band's near edge (swept 130..220), so floor and bar are independent knobs.
- **PRICE THE CONFOUND BEFORE THE SEARCH.** Two knobs moved (window + the shipped 160 floor vs
  s136's as-run 170); a 4-minute `_notes/s137_floor_price.py` says the floor is worth **0.00 frames**
  here (winner's curve at runway 179, clear of both), which is what makes the 2741 s null readable.
- **NEXT = GO AT ``unarmed``** (429724, the only thing that has never moved): instrument the arming
  cone deficit's TRAJECTORY over the children that die there -- reachable tail or hard floor, and
  which parents make the near-misses. Then ``probe_cap`` BUT re-ranked by something that predicts the
  BOUND (`_probe_pool` selects by flatness/jf/``l0`` share -- the axis just shown not to predict it),
  then s135's radial-exit keep. Also open: s134's "26 of 737 rolls over the bar" count needs a re-run
  at -77.83 (`_notes/s134_l0_headroom.py` prints and banks NOTHING -- make it dump a census).
- KB: both OWNING pages updated, no new page (these answer questions those pages already asked).
  Suite **1152 passed, 3 skipped, 8 xfailed in 1:03** (quiet).

## s138 -- THE BIGGEST COUNTER WAS THE ALPHABET; THE BAR IS THE CLAMP'S KNEE; THE HERD IS 80%

s137's ordered item, answered, and it RETIRES the counter nine sessions read as the refusal. No
search ran; **bound unchanged at 89.82**. Census `_notes/s138_unarmed_census.py` (124 s, `.log` +
`.json`), KB `knowledge/strategy/the-biggest-death-counter-was-the-alphabet.md`, gate
`tests/test_arming_bar.py` (3, 0.23 s). Suite **1155 passed, 3 skipped, 8 xfailed in 1:02**.

- **``unarmed`` 429724 DOES NOT BIND.** The same junction stage ADMITS **73070** armed endpoint
  children -- **1258-9604** on each of the 13 parents that produce -- into a probe pool that takes
  **250**. A gate above a cut that discards **97.1%** cannot be what binds.
- **AND THE BYTE-IDENTITY WAS PLUMBING, NOT A MECHANIC.** ``probe_half`` and `handoff.RUNWAYS` are
  ROLL-stage / chain-back arguments and `extend_cycle` passes NEITHER into `junction_beam`, so the
  junction is a deterministic function of parents+alphabet and answered s136/s137 identically **by
  construction**. **GENERAL: a counter's stability is evidence only if the knob reaches the stage
  that raises it.** Check the call site before reading the number.
- **THE REFUSAL IS TWO POPULATIONS, NEITHER A LEVER.** **97.77%** (420144) never flip -- probe
  speedF -26..-10, a **28-unit** floor, FLAT across all 12 generations -- and **2.23%** (9580) flip
  and land under the bar. Best refused **+16.998**, worst armed **+17.000**, nothing between. 3 of 16
  parents produce ZERO endpoints and top out at -11.4, so no threshold reaches them either.
- **THE BAR IS DECOMP, NOT A TUNED CONSTANT.** `_roll_init` = ``clamp(speedF*1.5 + 0.5, 5, 26)``, so
  ``min_preroll = 17.0`` is exactly where the clamp SATURATES and each 1.0 of deficit costs exactly
  **1.5 u/f** of roll. Relaxing to +16.0 = 5677 children at <=5.8% weaker rolls = **+7.8% endpoints
  into a pool already discarding 97.1%**. Gated (knee + affine slope + the ROLL_MIN +5 graze floor).
- **A PENDING L ARMS NOTHING -- 36535 of 251397 EITHER WAY, to the count.** `chaseAttention` only
  acquires inside the +-90 deg front cone and every child at this probe is OUT of it by the
  ``in_cone`` gate above, so the lock that routes the flip is **INHERITED** -- arming is a posture
  carried IN, never bought on the last frame. Toward-Tetra stick: 14.53% -> **36.80%**, decides
  nothing.
- **THE ARITHMETIC THAT SHOULD AIM THE NEXT SESSIONS: 89.82 = 72 herd + 4.82 gap + 13 cut** (81.89 u
  at the 17.0 u/f walk cap). Every screen-side knob priced since s135 -- window, runway floor, probe
  pool, ``l0`` frontier -- acts on the GAP term, **5.4%** of the bound. **The herd is 80%.**
- **NEXT = the pool, but price its CEILING first**: re-run cycle 3 on the same beam with the pool
  selected DIFFERENTLY (different tie-break/slice, same cap 250, everything else held, ~1700 s). If a
  different 250 of 9604 returns 89.82 again, the pool does not bind either and the frames are not in
  the screen at all -- redirect to the herd's 72. If it moves, build the rank, and rank by predicted
  **GAP**, not ``l0``.
- **METHOD (reusable):** instrument by wrapping `full_herd._expand` (child -> delivered letter,
  cleared per call so ids cannot recycle) + the REAL gate for the LABEL, never a replica -- then the
  self-check is reproducing the banked counter (429724) to the count. **Measure the ADMITTED class
  too**: a near-miss tail and a hard binary look identical from the dead side.
- **TRAP:** `nohup ... &` in the Bash tool returns instantly and the harness reports the SHELL's exit,
  not the job's -- read the log, never trust that completion notice.

## s139 -- THE POOL BINDS AND HIDES NOTHING; THE SCREEN IS PRICED OUT (compact; s139 wrote no section)

Two runs, one knob each (`_notes/s139_pool_price.py`): the DISJOINT runner-up 250 loses **+7.57 f**
(97.39) -- the pool is LIVE -- and cap **500** at the shipped orders returns **89.82 BIT-IDENTICAL**,
same winner -- nothing sits past index 250. **A named cut has two prices and only the widen direction
is money**; KB NEW `knowledge/strategy/price-a-cut-in-both-directions.md`. With it every screen knob
since s135 is flat: **89.82 = 72 herd + 4.82 gap + 13 cut; the herd is 80% and unpriced.** Next =
this instrument one stage up (the cycle-2 beam's 16). Traps: `_mixed_beam` is NOT prefix-stable
across caps (disjoint slice by EXCLUSION, never `pool(2*cap)[cap:]`); junction-counter byte-identity
across pool knobs is the EXPECTED self-check, not a finding.

## s140 -- THE CYCLE-2 BEAM CUT IS TWINS AND PRICES 0.00 BOTH WAYS; THE 72 IS UPSTREAM OF IT

s139's ordered item, answered over the cut's ENTIRE population (`_notes/s140_c2_price.py`, stages
`c2` 929 s / `c3` 523 s; logs `_notes/s140_c2_stage.log`, `_notes/s140_c3_alt.log`; beams
`_generated/s106/s140_c2_{shipped16_repro,alt16}.json`, `s140_c3_alt16_t11_f40660.json`). Bound
unchanged at **89.82**. KB NEW `knowledge/strategy/count-the-states-before-pricing-a-cut.md`.

- **REPRODUCTION GUARD FIRST, AND IT MATTERED**: the banked 16 (`s134_c3_l0_beam.json` cyc 1)
  predate s134's `l0` share at the final beam cut, so the re-run (s134_recut knobs: 8 cycle-1
  parents, contact fan, thrust-14 l0 screen, cap **400**, beam 16) tested BOTH hypotheses: the
  PRE-FIX rank-only cut reproduces **byte-identical by input log**; today's mixed cut does not.
  Perturb the cut the artefact was actually cut by.
- **THE POPULATION IS 31 NODES = 18 BIT-EXACT STATES.** The cut keeps 16; the dropped 15 = 9
  bit-exact twins of kept members + **2 novel states** (6 nodes, all cycle-1-parent-0). A
  runner-up "16" does not exist; the honest counterfactual is the WHOLE complement -- which makes
  the verdict population-complete, no slice caveat. **COUNT THE STATES FIRST -- the census is free
  (rebuild + hash the state bits) and it bounds what any pricing run can return.**
- **THE COMPLEMENT REACHES 89.82 WITH THE WINNER'S OWN NUMBERS** (c3 knob-for-knob with s136/s139:
  72 herd + 81.89 gap + 13 cut, l0 +15.48, runway 179): the winner's cycle-2 state sits on BOTH
  sides of the cut -- `alt[0]`'s 45-frame log differs from every kept node's, end state
  bit-identical to kept `S1` (the-frame-the-alphabet-shares, at whole-history scale). The 2 novel
  states both lose (70-71 f OFFSIDE l0 -33.66 / no endpoint). Union = min(89.82, 89.82): the c3
  stage is per-parent independent up to its final cut and `handoff` is computed pre-cut, so ONE
  run carries both directions.
- **WHERE THE CYCLE-2 SELECTION ACTUALLY IS** (none perturbed yet): `jn_keep` **6** of 58-259
  rolling endpoints a parent; the c2 probe pool **400** of 424-5616; cycle 1's beam (8 parents,
  only **4 produce** the banked 16 -- 5 nodes from parent 4, 6 from 6, 4 from 0, 1 from 5; the
  winner descends from parent 4). That, or the herd's PHYSICS (cycle count), is where the 72
  lives. NEXT = census + two-direction price at `jn_keep`, then the c2 pool, then cycle 1's beam.
- **TRAPS**: (a) the c2 stage prints "probing N of M" ONLY when M > cap -- a parent under the cap
  is silent, so count parents by the screened-l0 lines, not the probing lines; (b) dump artefacts
  BEFORE any assert that can fail -- the first c2 run died on a size assert AFTER 933 s with the
  beams unbanked; (c) an `attribute_parents` row is an index into the beam it was called with --
  label which beam before quoting "parent N".

## s141 -- NEW BEST BOUND 86.89: `jn_keep` WAS COSTING 2.93 FRAMES, AND THE SLOT WENT TO THE `l0` SHARE

s140's ordered item, and the **FIRST cut priced since s135 that PAYS**. **86.89 = 69 herd + 83.15 u of
gap at the walk cap (4.89 f) + 13 cut**, `l0` +29.47, runway 230, terminal facing 40660 / thrust 11 --
under 89.82 and **14.11 under `TOTAL_INCUMBENT` 101**. Probe `_notes/s141_jnkeep_price.py` (`c2` 1042 s
+ 7892 s of per-node `c3`), logs `_notes/s141_c2_stage.log` / `s141_c3_novel_b*.log`, artefacts
`_generated/s106/s141_jn_{pop,novel,meta}.json` + `s141_c3_rows_b*.jsonl`. KB NEW
`knowledge/strategy/a-keeps-width-is-not-its-reach.md`.

- **THE CENSUS UNIT IS THE CUT'S OWN KEY, and counting it PREDICTED the cut would pay.** The rolling
  population is **1266 endpoints = 1266 distinct cut keys over 34 bit-exact states** (4-6 a parent) --
  the MIRROR of s140's 31-nodes-18-states -- because the key is `(_physics_tag, pending stick,
  pending L)` and the members are one node's children ([[the-frame-the-alphabet-shares]] at endpoint
  level). So this cut selects **which pending letter launches the roll**; a state-only census would
  have called a live 1266-way selection a 34-way one. COUNT BOTH.
- **THE WIDTH WAS HALF NOMINAL:** the shipped 42 slots reach **20** of 34 states and spend **22**
  re-picking a state another slot already had -- exactly the s68 failure mode, whose guard
  (`_mixed_beam`'s `group`/`per_group`) is present at `junction_beam`'s frontier keep and **ABSENT**
  here. The Tetra-blind ident is HARMLESS though: zero key collisions at a different Tetra, widest
  `l0` spread inside one key 0.00 u.
- **THE WINNER SAT AT RANK 3 OF A CUT THAT KEEPS 6.** `_mixed_beam` gives each order
  `beam // len(orders)` slots = 3 each, so the rate order never sees rank 3 and the s134 `l0` share
  spent the slot -- on an axis s137 had already measured does not predict the bound. The winner's own
  cycle-2 `l0` is **-175.60**, WORSE than the shipped -154.38: the screen ranks it near-last.
- **PRICED POPULATION-COMPLETE, 66 of 66**, because the roll stage is only **9.0% of the stage**
  (0.074 s an endpoint, +94 s of 1042 s) -- the queued `jn_keep=12` was budgeted "~2x 929 s", off ~20x.
  **MEASURE THE SHARE OF THE STAGE BELOW A CUT BEFORE BUDGETING ITS WIDEN.** 189 dropped-origin
  survivors = 66 novel identities on 66 states none of the shipped 31 reach; the other 123 are
  bit-exact twins of the shipped 18 (= s140's own census of those nodes, cross-checked free).
- **THE CROSSING STILL DOES NOT PAY:** identities reaching the bar (`l0` -79.26..-81.87 vs -77.83)
  price 95.45..107.40 at 52-53 herd frames; two reach **71** herd frames and hand back 158-221 u of gap.
- **TRAP THAT COST A 45-PARENT RUN:** `handoff` is computed only after ALL parents finish, so a killed
  multi-parent `extend_cycle` returns NOTHING. Fix (now in the probe, copy it): **one node per call,
  append a JSONL row after each, resume by node index** -- identical numbers, and a partial run is a
  partial ANSWER. Background tasks were killed twice this session.
- **DEREck's CORRECTION (s141): do not size headroom as "distance to 75".** `frame_floor`'s 72.12/75
  prices the OLD ending (push her onto a coord and stop) with NO gap and NO cut term; his rule is
  "more than 75 herd frames is acceptable if it saves time overall" and the test is beating **101 on
  the TOTAL** (`objective.verdict` = complete AND (`within_budget` OR `beats_incumbent`)).
- **WHAT SIZES THE REST:** 7 cuts priced, 6 flat and all on the GAP term (4.89 f, 5.6%, ceiling 4.89
  and can only GROW when the walk is made real); the 1 inside the HERD (69 f, 79%) paid 2.93. Two herd
  selections left: the **c2 probe pool** (400 of 424-5616) and **cycle 1's beam** (8 parents, 4
  produce). **Dereck approved TWO more pricing sessions (s141), then assembly.** s142 = census + price
  the **c2 pool** (census free) **with `jn_keep` HELD OPEN** -- pricing it at the shipped `jn_keep=6`
  would filter the pool's extra endpoints through a cut known to drop rank 3, a FALSE NEGATIVE by
  construction; s141's config (86.89) is the baseline, not the shipped one. s143 = **cycle 1's beam**
  (4 of 8 produce) and SHIP the winning config -- note the `jn_keep` fix **cannot beat 86.89 through
  s141's pool** (that population was priced completely), it only reproduces it in a shipped config, so
  it is bookkeeping before delivery, not a frame-finder (candidates: `jn_keep=12` / the s68 per-state
  cap / **drop the `l0` share at this cut**). THEN ASSEMBLE AND DELIVER (86.89 is not a deliverable:
  69 real frames + two allowances).

## s142 -- NEW BEST 85.22: THE POOL BINDS TOO, AND THE FREE CENSUS RANKED THE TWO DIRECTIONS WRONG

s141's ordered item, priced population-complete with `jn_keep` HELD OPEN at s141's config (reference
**86.89**, not the shipped 89.82). **85.22 = 72 herd + 3.71 u gap (0.22 f) + 13 cut**, `l0` +51.22,
runway 260 -- **-1.67 f**, **15.78 under `TOTAL_INCUMBENT` 101**. Probe `_notes/s142_pool_price.py`
(stages `census`/`c2`/`attrib`/`c3`) + `_notes/s142_verify.py`; logs `_notes/s142_{census,c2_stage,
attrib,verdict,verify}.log` + `s142_c3_b*.log`; artefacts `_generated/s106/s142_pool_census.json`,
`s142_pool_{pop,novel,meta}.json`, `s142_c3_rows_b*.jsonl`. KB NEW
`knowledge/strategy/a-cut-widens-two-ways.md`.

- **THE CENSUS IS FREE (junction cost only -- wrap `_dedup_endpoints`, return nothing, no `roll_probe`
  runs; 32 s) AND IT MIS-RANKED THE DIRECTIONS.** Population **24708 unique endpoints = 261 physics
  states at 94.67 pending letters a state**; the shipped 2800 slots reach **34**. Cap 800 reaches 62 and
  PAYS; the same 400 slots under the s68 `group`/`per_group` cap reach **all 261 FREE**. Priced: free
  direction best **88.04**, paid direction (more LETTERS of states already reached) **85.22** and all
  three sub-86.89 results. **Reaching a new state is not reaching a new OUTCOME** -- a letter changes
  what the roll DOES with a state (s141's 2.93 f was a letter too). Count states to SIZE a widen; expect
  the frames in the letters.
- **PRICE A UNION, NEVER A RE-COMPOSITION.** A per-state cap at fixed cap is a SWAP (drops ~60 of the
  productive state's ~90 letters), so the guard dies with it. Run = shipped 400 U state-capped 400 U
  plain-widen 800 = **6632 screened (+137%)**, 2415 s, roll stage 3182 in 247 s (10.2%). **GUARD 220 of
  220** s141 survivors byte-identical. 490 survivors -> **108 novel identities, priced 108 of 108**
  (23563 s node time, 9 parallel batches of 12 on 12 cores = ~55 min wall). 34 live.
- **TOP THREE REPLAY BIT-FOR-BIT** (<1e-9, `s142_verify.py`): node 12 85.22 (72 f, 3.71 u, runway 260,
  21 entry curves; Link (-1478.123291,-796.263062) Tetra (-1527.264404,-854.942566), 72-frame log),
  node 44 85.31, node 16 85.73 -- all **letters**.
- **THE GAP TERM IS RETIRED.** Every bound since s135 carried 80-83 u (~4.9 f); node 12 hands her over
  at 3.71 u = **0.22 f**. The six cuts priced flat all act on that term -> dead levers whatever their
  price. 85.22 is now **72 f herd (85%) + the 13-f clip roll (15%)** -- and that 13 is `PairFrame.cut_step`,
  the schedule's EXACT length for the chosen terminal, NOT a padding allowance: it moves by choosing
  a terminal (thrust 14->11 already took it 16->13), not by building the sequence tighter. Crossing still does not pay (3rd session): bar-reaching `l0` -81.88/-84.18 price
  104.17-109.90 at 82-84 herd f.
- **TRAP: A PARALLEL BATCH'S VERDICT LINE IS A SLICE VERDICT.** Six of nine c3 batches printed "nothing
  the wider pool reached buys a frame" while the winner sat in a seventh -- ALWAYS aggregate every
  `*_rows_b*.jsonl` before quoting. Also: a runway on a rung EDGE (160 floor / 320 ceiling) is not
  quotable; the three winners sit mid-range (260/270/210).
- **THE RANKED LADDER IS TRACKED NOW** (Dereck asked, s142): `fixtures/courtyard_candidate_ladder.json`
  = all **49** live candidates from s141+s142, best bound first, each with its FULL herd input log and
  scored by `objective.replay_and_score`; every rung replay-verified on build. **27 of 49 viable;
  85.22 -> 85.31 -> 86.89 -> 90.41 -> 91.74** (rung 2 costs 0.09 f). **Rung 3 (85.73) beats the bound
  and FAILS rule 3** -- score a ladder, never rank it. Gate `tests/test_candidate_ladder.py`. Before
  s142 every plan lived only in gitignored `_generated/`: a lost rung meant re-running the search.
- **NOTHING SCORES THIS SHAPE END TO END YET, and that is the real gate on a DTM delivery.**
  `objective.verdict` still needs ``complete`` = Tetra within the band of a `tetra_placements.tsv`
  coord -- the OLD ending, and that table is tied to ONE banked entry. This shape's completeness is
  `handoff`'s ``onside`` + ``n`` (`entry_locus` solves Link's entry points for a FIXED Tetra; node 12
  has 21). Node 12 today: wall_ok/regime_ok/terminal_ok/beats_incumbent all True, ``complete`` False
  at pd 92.83 u (wrong table). Also `score_plan` adds the escape ATOM's 12 f (84, not 72) -- the old
  walk-away s123 removed. Build the shape's acceptance test BEFORE assembling.
- **NEXT (s143), re-aimed by this result:** (1) **price DEEPER in the LETTERS direction** -- 6632 of
  24708 screened, the axis that paid is nowhere near exhausted; scale the cap to a c3 budget (108
  identities = 23563 s) and keep the union shape; (2) **price the 13-f TERMINAL CUT ALLOWANCE** -- 15%
  of the bound, never touched, and the only remaining pure assumption; (3) then cycle 1's beam (4 of 8
  produce) and SHIP (bookkeeping, not a frame-finder -- this population was priced completely). THEN
  ASSEMBLE AND DELIVER.

## s142 LATE -- THE TERMINAL WAS NEVER CONFIRMED: NO RUNG ADMITS A GENUINE ENTRY

Dereck asked "are we ready to look for a concrete DTM-deliverable solution?" -- running the acceptance
test to answer it found the real blocker, and it is not search and not the scorer. Probes
`_notes/s142_{genuine,control,densify,region}.py`, logs beside them, artefact
`_generated/s106/s142_genuine_region.json`. KB NEW
`knowledge/strategy/confirm-the-terminal-before-you-rank.md`.

- **THE RANK WAS A PROXY NOBODY HAD CASHED.** `handoff.endpoint` takes ``roots``; **s134-s142 all ran
  the DEFAULT `roots=True`** = `entry_roots`, the UNCONFIRMED razor curve its own docstring calls "an
  under-estimate by construction... so a bound is never quoted as a solved entry". Through
  `entry_locus` (`roots=False`): **rungs 1/2/4/7 confirm 0/0/0/0** against 21/21/17/25 roots. A
  residual zero-crossing is necessary, NOT sufficient -- so every `gap`/`bound` since s134 measures a
  distance to a point where the clip does not fire, and the ladder's ORDERING is unfounded. The herd
  input logs stay real and bit-exact.
- **NOT THE CONFIRM, NOT THE SAMPLING** (the order that keeps `[[infeasible-needs-proof]]`):
  (1) positive control -- 2 of 6 tabulated coords confirm at this terminal, `genuine` True, resid
  ~5e-5 u, base rate **0-1 confirmed per 22-29 roots**; (2) densify by RESOLUTION only -- 81 runways
  instead of 17 (111/125 roots) and a **+-0.05 u** band walk vs `side_band`'s +-1.2e-3 -> still 0;
  (3) locate the SET instead of the failure.
- **THE GENUINE SET AT facing 40660 / thrust 11**: `l0` **+4.11..+12.67**, x -1650.61..-1627.94,
  z -929.51..-893.00 (9 of 29 tabulated coords survive here, with entry curves banked). **The ladder
  parks her at `l0` +29.47..+51.97 -- 4x outside.** Dereck is right that `tetra_placements.tsv` must
  not restrict the plan and NOTHING in the search path reads it (`probe` derives `genuine` from the
  roll sweep) -- but the replacement is a set DERIVED at the terminal in use, not no set. `sign_prune`
  only ever asked `l0 > 0` (the genuine set spans +0.57..+51.0 over solved terminals), so nothing ever
  told the herd that clips live NEAR the line.
- **NEXT, BEFORE ANY OTHER ITEM: invert the targeting.** Derive the genuine set (one `entry_locus` a
  Tetra, ~20-30 s), aim the herd at it, and rank on a CONFIRMED gap -- or carry the confirm as a hard
  gate on anything quoted. `fixtures/courtyard_candidate_ladder.json` now carries a
  `CONFIRMATION_WARNING` + `genuine_region` and is gated as a BANK of herd endpoints, not a shortlist.
- **THE CUT-PRICING RESULTS STAND as RELATIVE measurements on a fixed metric** (s141 `jn_keep` -2.93,
  s142 pool -1.67, the widen-direction ranking); what does not stand is "85.22 is nearly deliverable".

## s142 FINAL -- THE CONFIRMED PLAN IS 88.82, VIA A CACHED GATE AND BRANCH-AND-BOUND (Dereck's steer)

Dereck (s142) rejected mapping a genuine set -- "no matter what it won't be exhaustive, so computing a
positive for clip viability each time (unless cached) seems more rigorous" -- and he was right twice:
it is more rigorous AND it produced the number. NEW `harness/tetrapush/confirm.py`, gated by
`tests/test_confirm.py`; scan `_notes/s142_scan.py`, logs `_notes/s142_scan{,_dense,_rw1}.log`,
artefact `_generated/s106/s142_scan_results.json`, cache `_generated/confirm_cache.json`.

- **VIABILITY IS A FUNCTION, CACHED ON EXACT BITS** -- `confirmed(pf, tetra)` = the derived
  `entry_locus` predicate, keyed by `(facing, thrust, lean, tetra f64 bits, runways)`. Never a table:
  a precomputed set is `tetra_placements.tsv` again with new provenance.
- **IT COMPOSES INTO SOUND BRANCH-AND-BOUND.** `entry_roots` (what `roots=True` ranks on) is an
  under-estimate BY CONSTRUCTION -> admissible. So: rank on roots, confirm ascending, STOP when the
  next roots bound >= the best confirmed. Over the 49 banked rungs that is EXACT, and it closed in
  **6 rungs / 211 s**.
- **THE ANSWER: 88.8186 = 73 herd + 47.92 u gap (2.82 f) + 13 cut**, rung 5 (s142 node 75), Tetra
  **(-1615.514893, -887.797729)**, walk to **(-1563.932791, -820.661232) at runway 186**, 4 confirmed
  entries, band width **6.96e-4 u**. **12.18 under `TOTAL_INCUMBENT` 101.** Rungs 1-4 (85.22..86.89)
  confirm NOTHING -- their bounds were roots fiction.
- **THE RUNWAY GRID IS WORTH FRAMES AND HAS CONVERGED**: the locus is a CURVE (one solved `side` a
  runway), so the grid step is a knob -- step 10 -> 1 entry, 94.79 u, **91.58**; step 2 -> 3 entries,
  47.92 u, **88.82**; step 1 -> IDENTICAL. So 47.92 u is real distance, and the proxy's optimism fell
  3.5 f -> 0.78 f. **Sample a solved curve finely before believing a gap.**
- **THE DELIVERABLE IS NOW THREE PIECES**: the 73-frame herd log (DONE, bit-exact, replays <1e-9),
  ~2.82 f of walk onto a **7e-4 u razor** (to build), the 13-f clip roll (to build).
- **OPEN FLAG ON THIS PLAN**: rung 5 scores `terminal_ok` False (`escape_ready` does not fire), and
  whether that rule applies to the zero-walk-away shape is itself unresolved -- `escape_ready` probes
  the away walk s123 removed. Resolve, do not assume.
- **AND THE SEARCH IS STILL NOT CONFIRM-AWARE**: 88.82 is optimal over the 49 we happen to have, NOT
  over what the herd could produce. Putting `confirm` in the loop (it is ~8 s cached) is the next
  frame-finder.

## s142 END -- DERECK: "WE ARE STILL WALKING AWAY FROM HER?" -- the `gap` term contradicts the shape

- **HE IS RIGHT, AND IT IS THE SHAPE.** s123 set ZERO WALK-AWAY: "the herd's LAST ROLL *is* the clip
  roll... no escape, no walk-back, no separate roll-entry search -- Link never leaves her." But
  `handoff.endpoint` has priced `frames + gap/WALK_CAP + cut_step` since s135 and **`gap` IS a walk**.
  On the confirmed 88.82: Link ends the herd **57.85 u** from Tetra (inside s123's own measured
  57.0-75.4 u terminals), the confirmed entry is **84.66 u** away, so the 47.92 u walk ends **26.81 u
  FURTHER from her**. Not the round trip s123 killed (no walk-back), but Link leaving all the same.
- **THE RIGHT TARGET IS `gap` = 0** -- the herd's LAST FRAME already on a confirmed entry. For the SAME
  73-frame log that is **73 + 13 = 86 frames**, better than 88.82 AND the correct shape. So `confirm`
  belongs as the ACCEPTANCE TEST on the herd's final frame (confirmed gap inside the ~7e-4 u band) and
  the search should rank on HERD FRAMES alone, not on a walk it should not be taking.
- **UNCHECKED RISK THE WALK ADDS**: Tetra may FOLLOW during those 2.82 frames, which would make the
  Tetra position the clip was confirmed against STALE (she is inside the 130 u close-back distance, so
  probably not -- but nobody has gated it).
- **DERECK: NO DTM UNTIL THE FULL CLIP SEQUENCE EXISTS.** A movie of the herd alone is not a
  deliverable -- do not author or play a partial one (I did, and he corrected it). The delivery path IS
  proven wired for this plan shape though: `_notes/s142_dtm.py` spliced the 73 real frames as a WIRING
  CHECK and passed both guards (F0 44974, ticks extended, `rt_mismatch` 0 / `prefix_ok` True), so
  `deliver.build_boot_movie` is known good -- point it at the COMPLETE sequence and deliver once.
- **NEXT SESSION'S ORDER**: (1) fix the shape (`gap`=0, the herd's last frame ON a confirmed entry --
  86 f for the same log) BEFORE building any inputs, since a walk phase should not exist; (2) build the
  **13-frame clip roll's inputs**, the piece with no substitute; (3) score the assembled sequence end to
  end (nothing does -- `complete` is the old ending's clause, `score_plan` adds the removed atom's 12 f,
  and rung 5's `terminal_ok` False is of unresolved relevance); (4) THEN one DTM.

## s143 -- THE TERMINAL'S CUT IS NOT DISPATCHABLE, THE CLIP ROLL COSTS +2, AND NOTHING BANKED CLIPS

Built the clip roll's inputs (Dereck's item 2) and that is what found all of it. NEW tracked
`harness/tetrapush/clip_roll.py` + `tests/test_clip_roll.py` (9, 0.8 s); `entry_search.cut_step_window`
/ `thrust_window` + `fast_schedule` now RAISES; probes `_notes/s143_{shape,tail,exit,clip,rolls,reprice}.py`,
artefact `_generated/s106/s143_roll_entries.json`.

- **THRUST 11 IS A ROLL THAT NEVER CUTS.** `fast_schedule` computed `cut_step = thrust + 2` in closed
  form and never checked; `turnaround.extract_schedule_at` (which SIMULATES) raises for every thrust
  outside **13..15**. Derived from `LandState.ROLL_RATE`/`ROLL_EARLY`/`ROLL_END`: the cut dispatches
  only at `cut_step` **15..17** -- below the floor the B lands before the early-turn arm opens (roll
  ignores it and runs on), above the ceiling the roll has already exited to MOVE. `thrust_window()`
  reproduces `ES.THRUSTS` exactly. **So s136's "thrust 14 -> 11 = 3 frames off the cut" is fiction,
  and every bound since carries it.** The old gate swept `ES.THRUSTS` only -- exactly where analytic
  and simulated already agreed. New gate sweeps thrust 9..18 both directions.
- **THE CLIP ROLL COSTS `cut_step + 2` FRAMES.** The entry frame runs one full roll step before
  schedule step 0 (`roll_entry`; `extract_schedule_at` seeds a LandState already rolling at `entry`).
  Simulated across the realizable window. Cheapest deliverable roll = **17 f** (thrust 13) vs the 13
  charged: **+4 frames on every bound**, before the terminal re-solve.
- **A HERD ENDPOINT CANNOT FIRE IT.** The roll EXIT frame is `ATN_ACTOR_MOVE` and the A-roll
  dispatches only from `ROLL_FROM` = (MOVE, ATN_MOVE) -- the natural chain frame is the one frame
  that refuses; one frame later the untarget flip has run and `roll_nspeed(-25.72)` = **5.0**, a 65 u
  roll against a runway grid starting at 160. **And the native core has NO cut branch**
  (`_anmc._proc_roll` omits the `b_trig` arm) -- build the herd native, `fire` on a Python-path run.
- **NO BANKED ENDPOINT CLIPS IN s123'S SHAPE, POPULATION-COMPLETE**: the razor read at every roll
  entry the 49 logs already fly = 147 entries x 17 thrusts, **2499 probes, 0 genuine** (contact at the
  cut in 479, all low thrust; last rolls at resid -25..-307 u). MECHANISM, not a near miss: a herd
  roll is aimed AT Tetra to plow her; a clip roll must be aimed at the CORNER with her ON that line
  (`along` 50-245, `lat` ~0, `runway` 190-310). Her `lat` is already right (+0.2..+2.8); Link's
  `side` is not.
- **SO s142'S "WALK-AWAY" IS AN ALIGNMENT.** She sits ~24 u OFF Link's line to the corner, and
  putting her BETWEEN him and the corner is what requires backing off that line -- which is why the
  entry reads 26.81 u further from her. Not s123's round trip. But its price is optimistic in a NEW
  way: the herd hands Link over at speedF -25.72, so the walk must turn around and re-accelerate past
  17 before any roll carries 26, and `gap / WALK_CAP` charges none of it.
- **`gap` IS ALSO MEASURED TO THE WRONG POINT**: `handoff.endpoint` measures walk -> `entry`, but
  `entry` IS the post-roll-entry-frame position (`entry_reach` translates by exactly that step), so
  the target is `entry - roll_step` (+4.92 u at the confirmed rung's delivered state; 26 u at the cap).
- **THE FRAME ARITHMETIC, CORRECTED (s143 got it wrong twice -- Dereck caught it).** Every plan =
  `(frames before the clip roll dispatches) + roll_frames(cut_step)`, the second term 17/18/19 at
  thrust 13/14/15. **WALK shape** = herd + walk + 17; banked herds are **69..84**, so the floor is
  **86** and **88 needs only a 2-frame walk -- NOT ruled out** (the "88 is impossible" claim came from
  anchoring on the 73-frame confirmed rung). **ZERO-WALK** = prefix + 17; banked prefixes are
  **51..66**, so entry+16 = 68..83. **NOT COMPARABLE**: the zero-walk prefix is TWO cycles of plowing,
  not three, and the third exists because two did not put her where the search wanted -- the clip roll
  would finish with its own 53-126 u of plow, and nothing shows a clip exists at the 2-cycle Tetra
  position. **68..83 is a floor under an assumption, not a plan length.** Prefer zero-walk because it
  deletes an UNPRICED phase (Link hands over at speedF -25.72 and must turn around and re-accelerate
  past 17 before a roll carries 26) and matches s123's geometry -- not because it is 15 f faster.
- **THE REAL BLOCKER (Dereck s143: "part of the final roll has to be spent going around her, so how
  would we ever be close enough" -- he is RIGHT and it is worse): THE HERD MUST FINISH THE PLOW AND END
  UP ON THE CORNER AXIS AT ONCE, AND THE TWO ARE ANTI-CORRELATED.** The clip roll plows Tetra only
  **24.7-125.9 u** (`_generated/s124/terminal_40835_14_0.json`, `plowed`), so a genuine config needs her
  within **180 u of the corner at the roll entry** (unbroken subset **100..180**, `along` 50..110,
  `runway` 190..260). The banked last rolls split DISJOINTLY: **8 rungs** have her at
  `tetra_from_corner` **120..178 u** but are aimed **33..47 deg off** the corner (`side` 149..228 u off
  the brace line); **7 rungs** are aimed **1.2..8.4 deg** but leave her **293..337 u** out = 113..157 u
  past the ceiling = 9..12 more frames of pushing. **NO RUNG IS BOTH.** Closing the first group's
  149..228 u at the walk cap is **9..13 frames** -- that IS the "going around her".
- **SO BEST CASE ~84..95 f, AND THE TWO SHAPES ARE THE SAME PROBLEM**: the 8 close rungs total 75..82
  before the line-up, +9..13 to line up = where the WALK shape lands too (86+walk). Zero-walk saves the
  turnaround out of the untarget flip, NOT the distance. **~6..17 frames under the banked 101.**
  **The s143 "1.3 u re-point" is RETIRED** -- measured on rung 15, which is 113 u short of the ceiling.
- **NOT PROVEN that the geometry forbids it** (`[[infeasible-needs-proof]]`): all 49 were bred ranking
  on distance-to-a-razor-entry-AFTER-A-WALK, so none was ever asked for both criteria -- and a keep
  carrying one of them is exactly what breeds a population satisfying one. Also the 180 u ceiling is a
  THRUST-14 number and **thrust 13/15 families have never been scanned** (s124 did 14; s136 did 9/10/11,
  void); a longer roll plows further, so one `terminal.scan` a thrust re-prices it.
- **THE 4-STEP PLAN (s143, agreed with Dereck)**: (0) VALIDATE the razor engine at a delivery state --
  `fast_schedule` seeds Tetra IDLE at rest and every terminal scan ran lean 0, while the herd hands
  over a FOLLOWING Tetra and m351C 648; `zero_the_resid` already takes a Tetra `seed=(speedF,facing,stt)`
  and the terminal path never passed one. (1) RE-POINT the last cycle's keep: `roll_probe` already
  sweeps the aim fan per junction endpoint -- rank it on `handoff.probe(pf, roll_entry, tetra)['resid']`
  and keep on `genuine`, thrust 13..15. (2) LAND the razor by bracketing the SIGNED resid across the aim
  fan and bisecting (`terminal.solve_razor`'s method); junction lateral = coarse knob, `aim_cell` = fine.
  (3) EMIT + verify offline: `clip_roll.fire` must return CUT_F and the Python replay must reproduce the
  razor engine's endpoint -- if they disagree, STOP. (4) THEN one DTM.
- **STANDING RULE: NO BOUND IS A PLAN.** Nothing is reported as a plan unless `clip_roll.fire` produced
  a CUT_F from its own log. s142 (a razor ROOT read as a clip) and s143 (a schedule built outside the
  thrusts it was verified at) are the SAME failure -- checked in one place, used in another -- and
  emitting the button presses is what caught it. De-prioritise `_notes/s143_reprice.py`: it prices the
  shape we are leaving, and it stalls because a B&B only pays when the RANK is cheap.

## s144 -- THE 17-FRAME FLOOR DOES NOT EXIST; THE DELIVERED LEAN COSTS A FIFTH OF THE FAMILY

Items 0 and 0b of the s143 plan, both DONE and BANKED. NEW tracked
`fixtures/courtyard_terminal_family.json` (8 scans, each with `roots` beside `genuine`) +
`terminal.clipping_family`/`clipping_thrusts` + `tests/test_terminal_family.py` (12 fast 0.3 s, 1 slow
38 s); NEW truth page `knowledge/strategy/dispatchable-is-not-clipping.md`; probes
`_notes/s144_{delivery,family,thrust13,bank}.py`. Gate **1184 passed, 66.18 s, exit 0**.

- **A THRUST THAT DISPATCHES THE CUT IS NOT A THRUST THAT CLIPS.** `cut_step_window` is a property of
  `procFrontRoll`'s animation; reaching the seam is the corner's. Over the whole scan box at the
  delivered lean: thrust 13 = **2390 roots, 0 genuine**; 14 = 2513 -> **40** (8 unbroken); 15 = 2613 ->
  **107** (0 unbroken). **So s143's "cheapest deliverable clip roll = 17 frames" is fiction and the
  floor is 18** (+1 on every bound it wrote, on top of its own +4). ABSENT GEOMETRY not a thin scan
  (`[[infeasible-needs-proof]]`): root counts within 10% across the three thrusts, thrust 13's roots
  solve to |resid| ~2e-7, `brace_dist` reaches **0.00** so Link ARRIVES and the cut still misses; 0 at
  lean 0 too (2414 roots). The KB half-knew it -- `roll-cut-thrust-floor.md` had "thrust 13 has no
  reachable live station" from s99 and hedged that a ~390 u entry might go through; swept to 480 u, no.
- **THE DELIVERED LEAN IS 648, ONE DISTINCT VALUE OVER ALL 49 RUNGS, AND THE FAMILY WAS SCANNED AT 0.**
  Re-scanned at 648: genuine **51 -> 40**, unbroken **13 -> 8**, `plowed` ceiling 125.88 -> 106.05,
  and the number the endgame is priced against -- how far from the corner a herd may leave her --
  **180 -> 160 u**, which HALVES the rungs clearing it (**8 -> 4**: rungs 44/41/46/43, tfc
  119.9..158.1). `roll-lean-decay.md` stands and is now scoped ON the page: the lean is spent before a
  late cut so the DEPTH at a solved configuration moves 0.0003 u -- a different quantity from WHICH
  configurations admit a solvable razor. `_cmd_leans` had only ever swept ±191.
- **THE TERMINAL IS PINNED TO THRUST 14**: the only thrust with an unbroken-contact family at the
  delivered lean (15 has the most genuine of any thrust and ZERO unbroken). Its window: `along`
  **60..100**, `runway` **190..240**, `tetra_from_corner` **105..160**, `lat` **+3.07..+5.23**.
- **ITEM 0'S TETRA HALF DOES NOT EXIST -- she is IDLE AND AT REST, faithfully.** Over all 49 rungs Link
  never reaches `FOLLOW_ENGAGE_DIST` (max **222.14 u**, rung 47), so she never leaves stt 3 and
  `fast_schedule`'s at-rest `tet_seed` IS the delivered one. No seed threading needed -- a MEASUREMENT
  was (49 rungs in 1 s). **Margin 7.86 u**, so it is gated: a re-pointed herd crossing 230 puts
  `FreeRun` outside the state it models, and its warning is swallowed by the `simplefilter('ignore')`
  every probe runs (the flag still works -- `roll_probe` reads `_follow_warned` as a death reason).
- **THE AIM IS A BAR IN THE SAME POPULATION-COMPLETE SENSE.** Delivered last-roll facings
  **26637..38782**; the seam's own measured window (`courtyard_facing_window_s92.json`, cells
  2548..2573) is **40768..41183**. **0 of 49 aim into it**; the closest (11.0 deg below the floor)
  bisects **2674 roots and clips at none**, a mid-pack -34.1 deg one 1778 and none. The camera is NOT
  the constraint: **27** of the 5600 deliverable facings at `CSANGLE` land inside the window.
- **SO THE ANTI-CORRELATION IS A THREE-WAY DISJOINTNESS, ALL MEASURED**: `tetra_from_corner` 105..160
  -- **4** of 49; `along` 60..100 -- **0** of 49 (delivered 42.0..56.0, so 4..18 u short of a 40 u-wide
  window); facing in the seam window -- **0** of 49. Only `runway` is fine (8 of 49). **`along` is the
  cheap axis to attack, the FACING is the expensive one** -- and the facing IS Dereck's s143 "part of
  the final roll has to be spent going around her": a herd roll points AT her to plow her, a clip roll
  points at the CORNER.
- **NEXT (s144's ordered item): give `roll_probe` the three windows as a KEEP, not a rank.** s143's
  item 1 with the order corrected -- ranking on `resid` at a facing 11+ deg outside the window ranks a
  quantity that cannot reach zero, which is what bred 49 rungs satisfying one criterion. Keep on all
  three at once, thrust 14 only (`clipping_thrusts(..., unbroken=True)` is the filter; `ES.THRUSTS` is
  the DISPATCH window and the wrong list to iterate). Expect `followed` to be the death counter and
  READ `dead` rather than assume. Then s143's 2/3/4 unchanged.
- **RE-PRICE NOTHING ON THE OLD NUMBERS**: every s143 bound charges 17 frames for a roll that never
  clips and measures against a 180 u ceiling that is 160.

## s145 -- THE TERMINAL IS A KEEP, AND s144 READ THE DISJOINTNESS IN 49 WRONG FRAMES

Item 1 of the s144 plan, order corrected as it asked. NEW tracked `harness/tetrapush/terminal_keep.py`
(`TerminalKeep`, `seam_window`) + `tests/test_terminal_keep.py` (16, 2.0 s); `full_herd.roll_probe`
takes `terminal=`/`terminal_sink=`, `extend_cycle` passes both through; `nspeed` reached
`terminal.RollFrame`/`handoff.PairFrame` (retires the s143 `_notes` subclass); NEW truth page
`knowledge/strategy/re-point-the-handoff-dont-re-project-it.md`. Gate **1200 passed, 68.44 s, exit 0**.

- **THE BOX BELONGS TO THE CLIP ROLL'S FACING.** `runway`/`along`/`lat` project on `m` = the ROLL
  DIRECTION, so they are a property of a pair PLUS a facing; `tetra_from_corner` = `-(tetra-brace)*m`.
  s144's delivery block came from `_notes/s143_rolls.py`, which builds a frame **per rung at that
  rung's own facing** -- 49 bases, none the box's. And a re-point is NOT a re-projection: `entry` is
  Link's position at the END of the roll-entry frame, which steps `nspeed` in the aim direction, so a
  re-pointed roll STARTS somewhere else and must be SIMULATED.
- **RE-MEASURED IN THE BOX'S FRAME, 49 rungs x the full 2280-member alphabet, 112k rollouts, 210 s
  (`_notes/s145_repoint.py`, `_generated/s106/s145_repoint.json`): 0 KEPT, 0 GENUINE.** Over the 528
  aims reaching a live seam cell: `runway` 185..245 vs 193.69..360.51, **best miss 0.00 (10 of 49
  satisfy it)**; `along` 57.5..102.5 vs -12.43..50.43, **7.07**; `tetra_from_corner` 102.5..162.5 vs
  194.08..331.52, **31.58**; `lat` +3.07..+5.23 vs 15.80..79.57, **10.57**. **So s144's "4 of 49
  satisfy tfc" does not survive the frame correction -- nothing is within 31 u -- and the FREE axis is
  `runway`, not `along`.** Closest overall rung 49 (along 41.28, runway 236.28, tfc 195.00, lat 39.39,
  pair 57.06 u). Delivered separation 52.85..79.82 u where the terminal wants 60..100 ON-AXIS, at a
  pair bearing 15..45 deg off the corner's against ~3.
- **THE FAN EVERY SCREEN BEFORE THIS SWEPT COULD NOT CONTAIN THE ANSWER**: the corner is up to 78 deg
  off the herd bearing and the default fan is +-56.25. Sweep the full circle and use `AXIS_PAIR` (s135)
  so "stay near the herd line" is not asserted of a roll that turns away from it.
- **`followed` IS THE DEATH COUNTER, MEASURED (s144 item 2 answered):** `followed` 110321, `wall` 680,
  `t_facing` 719, and the cross-tab **`followed@seam` 528 of 528**. Not a model limit hiding a
  solution -- a corner-aimed roll stops plowing her and Link runs ~470 u past; screen and box refuse it
  together. All 528 fail `t_along` first.
- **A GRID EXTENT IS NOT A BOUNDARY.** The bare `un_*` extent refused **3 of the 8 banked unbroken
  hits** (scan grid 10 u/5 u; the f32 basis lands a banked hit ~3e-5 u below its integer coordinate).
  Window = sampled extent + HALF a scan cell each side, gated by
  `test_the_keep_contains_every_hit_it_was_built_from` (`[[search-space-contains-human]]`).
- **DIAGNOSIS BESIDE THE COUNT**: `terminal_sink` takes the screen for EVERY aim whose roll FIRED (kept
  or dead) -- without it the geometry reported is exactly that of the aims NOT pointed at the corner.
  New `roll_probe` fields are ABSENT (not None) when unasked, so `courtyard_l0_screen_nodes.json`'s
  key-for-key `best` comparison stays valid.
- **NEXT (s145's ordered item): RE-BREED THE LAST CYCLE with `terminal=` on, from the CYCLE-2 exits**
  (s141/s142 drivers hold the seeds), `free_axis=True`, and READ `terminal_sink` -- the per-axis miss
  is the steer, `kept` is only the verdict. **Do NOT re-sweep the banked junctions**: that is this
  session, population-complete, and it returns 0 by MECHANISM not resolution. Price it honestly:
  31.58 u at `PUSH_CEILING` 13.00 = **>=2.4 frames** on top of every banked herd before the alignment,
  and a plan is `jf + 18` at best (rung 49 is jf 65 -> 83) against the banked console 101.

## s146 -- THE CYCLE-2 REQUIREMENT WAS READ PAST THE FOLLOW GUARD, AND THE KEEP COULD NOT SEE `l0`

I did NOT run the s145 re-breed. Two measurements say it would have bred cycle 3 against a screen blind
to the axis that refuses all 49 rungs, toward a target with no in-domain population. NEW truth pages
`knowledge/strategy/a-bound-read-past-the-guard-is-not-a-bound.md` +
`the-box-cannot-see-the-lateral.md`; migrated `history/the-crossing-bar-was-read-past-the-follow-guard.md`;
corrected `the-crossing-and-the-runway-are-one-resource.md`. `TerminalKeep` gains `t_l0`;
`tests/test_terminal_keep.py` 16 -> 19. Gate **1203 passed, 3 skipped, 8 xfailed, 66.02 s, exit 0**.

- **`crossing_bar` -80.4359 IS NOT A CONTINUABLE STATE.** `FreeRun` has NO follow model -- past
  `FOLLOW_ENGAGE_DIST` it sets `_follow_warned` and says the sim "is no longer faithful from this frame
  on" -- and s126 attributed the flat +80.0..+80.4 plateau to "her FOLLOW, not a plow". Audited on the
  banked census, no re-simulation (end separation > 230 PROVES the guard fired): the setter ends
  **402.9 u** away and **all 2339 band-keeping rolls end past the guard**. The only in-domain crossing in
  the census is `l0` +35.48 at runway **6.64** -- the deep plow, i.e. the surviving structural claim.
- **IN-DOMAIN (218880 rolls, `_notes/s146_bar_domain.py`): 98.8% of full-circle rolls trip the guard, and
  a band-keeping roll that never does reaches `l0` -123.48** -- it LOSES crossing. The guard costs
  **96.93 u** in the band.
- **THE JUNCTION IS THE CROSSING INSTRUMENT AND IS IN-DOMAIN BY CONSTRUCTION** (Link walks touching her).
  Population-complete over the banked c2 beam: 58 of 61 exits arm one, **309500 endpoints, 0 guard
  trips**, buying **+2.46..+89.71 u** (median +53.79), best absolute `l0` **-30.7501**. **SO WHAT IS LEFT
  IS 30.75 u ON `l0`**, not s145's 31.58 u on `tetra_from_corner`.
- **`l0` DOES NOT PREDICT ITS OWN JUNCTION'S CARRY** (s126 trap 1, now population-complete): best-`l0`
  exit (-69.66) buys +11.0; the +89.71 sits at -193.73; only **2 of 58** reach past -50. Five sessions of
  `l0_keep` ranked the wrong half -- the keep is `l0 + (junction carry)`, one junction beam per exit, NO
  aim sweep.
- **THE KEEP WAS STRUCTURALLY BLIND.** `along`/`runway`/`tetra_from_corner` are all projections on `m`,
  so a lateral slide of BOTH actors leaves them bit-identical (gated); and `terminal.RollFrame.item` has
  no `side` axis, so all 8 banked scans are a **side = 0 SLICE**. Rungs sit at `side` -170..-177, `l0`
  **-128.92..-140.40**. `screen` now refuses on `t_l0` = the SIGN (the 2.2 u `un_lat` band is reported as
  `l0_miss` and never refuses -- it would drop an unscanned `side`), reports `exact_side`.
- **0 GENUINE ENTRY LOCI AT THE BANKED NEGATIVE `l0`**: `sign_prune` off, `roots=False`, runway grid
  320 -> 520; the four best c2 exits give 5-7 ROOTS and 0 genuine, every root pinned at the old edge.
- **NEXT: WIRE HER FOLLOW INTO `FreeRun`** -- `npc_zl1.Zl1FollowState` exists and is live-0-ULP
  (`tests/test_tetra_follow.py`, engage 230 / break 130); her `step` already takes `cc_move`. Python path
  first, INERT below 230 u so every 0-ULP gate stays byte-identical (the DTM window peaks at 222.14),
  gate the boundary, then decide the native port (until then a >230 search must not run `native_step`).
  Residual to record: the live capture has Link STATIONARY, so the moving-Link read lag is unpinned.
  THEN re-breed cycle 2 on `l0 + junction carry`; s143's 2/3/4 unchanged.
- **TRAPS**: a cycle-2 exit dispatches NO roll (post-roll EBS backslide; 0 of 285 aims) -- sweep off
  `junction_beam`. `handoff.endpoint` defaults to `roots=True` (ROOTS, not clips). `handoff.RUNWAYS` stops
  at 320 and the roots landed exactly there. A guard that WARNS is invisible under `simplefilter('ignore')`.

## s147 -- THE HERD HANDS HIM OVER INSIDE HER, SO THE 94.56's TETRA DOES NOT EXIST; AND `side` IS THE AXIS

**THE 94.56 IS GONE.** s146 confirmed 16 genuine entries at rung 5's herd-END Tetra and priced a walk
from there. Three corrections, all measured, all the same direction:

1. **THE FIRST FRAME AFTER THE LOG MOVES HER 16.5 u, FOR EVERY INPUT IN THE ALPHABET.** Rung 5 ends
   with Link's exec Co centre inside her (feet 57.85 u) and the pipeline acts a frame late, so the
   escape has no say in the first two frames at all. Neutral, her z: -887.80 -> -904.29 -> -918.22 ->
   -930.13 -> -940.54 -> -950.02 -> -957.01. s146's own step-2 rule ("never within 80 u of Tetra --
   a walking push makes the razor stale") is violated **at frame 0, by the herd**. The terminal sees
   the POST-CONTACT Tetra -- `away_walk` has said so since s65 (34.8-44.7 u residual) and it had
   never been applied to the ladder's pricing.
2. **THE GAP IS NOT THE WALK.** The walk ends one full ROLL STEP short of the entry
   (`entry_search.roll_entry`) and the roll runs toward the brace while Link sits between the entry
   and the brace, so the walk-end is FURTHER out, never nearer: 60.46 u -> **83.75** at the herd-end
   Tetra, **112.36** at the real one.
3. **THE TERMINAL IS THEN UNREACHABLE.** Re-solved at (-1619.928101, -930.130066), runways 100..480
   step 2: **10 genuine entries**, `runway` 198..300 / `side` +19..+21, so Link owes `runway >= 224`
   at `side ~ +21`. The herd parks him at **runway 146.41, side -29.12** with **-25.72** of backslide
   pointed AT the brace. A 500-node beam closes ~5 u/frame, bottoms out **63.3 u short at f7 then
   DIVERGES**; every at-cap node stays 80..90 u out through f18.

**THE AXIS NOBODY SCREENED: `side` = LINK's lateral, the coordinate `entry_locus` SOLVES.** `l0` is
TETRA's and is what s146 screened (rung 5 +7.86, on side). Rung 5 is **50 u** off `side`. 49-rung
census three frames past each herd (`_generated/s106/s147_census.json`): Link `side` **-43.42 ..
+269.46**, Tetra `l0` **-0.34 .. +116.57**. `TerminalKeep` has `t_l0` and no axis for `side`.

**THE INSTRUMENT (use it, do not rebuild it): the razor on ANY (Link, Tetra) pair, 0.013 ms batched,
no locus solve, no frozen Tetra** -- `pf.sweep([(tx, tz, ex, ez)])` -> `(genuine, resid, overlap,
push, brace_dist)`, `resid` being the SIGNED miss `solve_razor` bisects. Gated: every solved genuine
entry reads **overlap +1.13 / push 0.566** = `entry_search`'s "genuine wants ~(-0.551,-0.127)" from
the other side. **TRAP: `resid` is FLAT outside contact** (bare roll-stab **-3.293847e-01** whatever
the entry) -- rank on `overlap` to reach contact first, only then on `|resid|`.

**THE LIVE LEAD IS RUNG 3 AND ITS BLOCKER IS `at_cap`.** Three frames past its herd: Link **runway
190.63, side +37.21**, Tetra `l0` +47.19; **one** genuine entry (runway 178, side +43.29, width
1.56e-04), walk-end **14.69 u** away -> bound **71 + 3 + 1 + 18 = 93**. But the box is reached at
**f10 to 0.001 u** and at cap only at **f12** -> **101**, a tie not a win.

**AND REACHING THE BOX BOUGHT NOTHING**: at `need` **0.016 u** the best at-cap `|resid|` was
**6.083** against a ~1e-4 acceptance. **The razor is JOINT in (Link, Tetra) -- never rank on a box
solved at another Tetra.**

**TRAPS RE-PAID.** (a) A runway grid STRIDE is a boundary too: a census at step 4 read 0 genuine on
eight rungs incl. rung 3, whose only entry sits at **runway 178**, off the step-4 lattice. Use step 2.
(b) A beam here dies on the pending-input tie -- children are physics-identical until the pipeline
clears, so a dedup key without the delivered stick collapses the generation, and a `per_state` CUT of
one sorted list starves it to 4 nodes on f1. Round-robin over physics states; key carries the input
(`full_herd.junction_beam` s68). (c) `nohup ... &` from the Bash tool does not survive.

**NOTHING DELIVERED, CORRECTLY**: `clip_roll.fire` never returned a CUT_F, so no plan and no DTM. No
tracked library/test change. Probes `_notes/s147_{handover,escape,razor,razorbeam,trace,reach,census,
terminals}.py`.

**THE LADDER CENSUS (banked, `_generated/s106/s147_terminals.json`, 78 min): THE HERD IS AIMED AT THE
WRONG ACTOR.** All 49 rungs, locus re-solved at each rung's own post-contact Tetra, runways 100..400
step 2. **19 of 49 have a genuine entry** (rung 12 has 18, rung 10 has 17, rung 15 has 15) -- clip
geometry is NOT scarce. What is scarce is Link being near one, and what he owes is a GAP not a
spread: **rung 3 owes 14.69 u (bound 93), rung 5 owes 112.36 (bound 101), the other 17 owe 179..343
(bounds 106..121)**. Rung 3 is an order of magnitude closer than anything else and is the ONLY rung
that beats the console. Every one of the 19 delivers a live terminal and then stands 180-340 u from
it; `objective`/`TerminalKeep` rank TETRA's placement and nothing ranks LINK's distance to the entry
curve his own Tetra generates -- which `pf.sweep` now makes free.

**NEXT: land rung 3 jointly, and attack `at_cap` rather than the distance.** Its box is reached at
**f10 to 0.001 u** and at cap only at **f12**, so two frames decide 93 vs 101; `away_walk`'s proc-7
DIR_BACKWARD negation converts **-25.727 -> +17.614** (already past `WALK_CAP`, motion unchanged) in
2 frames against the reach beam's ~10 -- that is the atom to aim the approach at. Then land with
`pf.sweep` per node, ranked `(not at_cap, contact deficit, |resid|)`, hunting a SIGN CHANGE of `resid`
over the reachable cloud -- rung 3 has ONE entry at width 1.56e-04, so a minimum of `|resid|` will not
find it. Size with `entry_search.window_gap` before paying for a fan. If it will not land, re-breed
against `side` AND against Link's distance to his own Tetra's entry curve.

## s148 -- `at_cap` IS 4 FRAMES NOT 12, AND THE TERMINAL'S LEAN WAS A STATE-2 SEED READ OFF A DEAD MIRROR

**1. THE s147 BLOCKER WAS ITS OWN RANK.** The reach beam hunted `at_cap` in ACCELERATION and priced it
at frame 12 (total 101, a tie). `away_walk`'s conversion buys it outright: the `setSpeedAndAngleAtn`
DIR_BACKWARD negation puts speedF at **+17.609** with motion unchanged, and `roll_nspeed` clamps that
to 26. The bare recipe reaches the cap at **f3** but the L LOCKS (Tetra is in the front cone at the
handover, `talk_active` True) into proc 9, which cannot dispatch; **with the recipe's own turnaround
frame first it is f4, proc 6, dispatchable -> total 93 (-8 vs the console)**. Whole-family enumeration
(`_notes/s148_cap.py`, 82432 rollouts): **67 at-cap dispatchable states at f4, 869 at f5**, ~all
talk-free. Rung 3's floor is 93; the walk budget is 11 frames.

**2. THE JOINT BEAM GETS TO |resid| 4.109e-02 AT TOTAL 100, THEN HITS A QUANTUM.** `_notes/s148_land.py`
sweeps every node at its own (Link, Tetra) pair, ranks `(fireable, deficit, |resid|)`. Its in-contact
cloud reads ONE residual across 514 nodes = the pending-input tie, not a sample. **SIZED THE FAN
(`_notes/s148_fan.py`) -- THE DURABLE NUMBER: the whole 254x254 stick grid on the frame that ACTS
expresses 171 DISTINCT residuals over -70.96..+66.14 (41148 neg / 2524 pos, so the razor IS bracketed)
at a MEDIAN NEIGHBOUR GAP of 1.663e-01 = 1066x the 1.56e-04 acceptance.** One walk frame cannot land
this razor however wide the fan; `knowledge/strategy/clip-lottery-draws.md` already names the fix
(widen the PREFIX, count draws per family). **Pipeline lesson re-paid a 3rd time:** fanning the input
delivered ON the landing frame gave **129032 children, ONE distinct residual** -- fan `len(log)-2`.

**3. THE BIG ONE: `terminal_keep.DELIVERED_LEAN` = 648 IS THE STATE-2 SEED, NOT A MEASUREMENT.** Its
docstring is the tell -- "the body lean every one of the 49 rungs delivers at its roll entry, ONE
DISTINCT VALUE". `from_f0._step_native` copied back 7 fields and NOT `m351C` (same hole in
`LandState._sync_from_core`), so on a native run `run.link.m351C` held its seed for the whole herd.
**NO PHYSICS DIVERGENCE** -- the native core's own `m351C` matches Python bit-for-bit (422, 275, 77,
10, 0, 0) and pos/speedF/facing/travel/Tetra were already 0-ULP. Nothing INSIDE the sim reads the
mirror, so it is invisible until a HARNESS script reads it -- which is how 648 was derived. The native
gates could not catch it: `test_freerun_native.py` compares an ALLOWLIST that never held `m351C`.

**AND THE WALK-END VALUE IS WRONG TOO (nailed by SIMULATION).** The roll's first frame is still MOVE
(A acts a frame late) and ITS turn WRITES `m351C`: walk end **0** -> dispatch frame **200** -> entry
frame **130**, and 130 is `fast_schedule`'s seed (draws `[65,42,28,18,12]` reproduce the simulated roll
exactly; 648 gives `[324,211,137,89,58]`). **So the lean is the ROLL'S OWN DISPATCH -- an axis the plan
CHOOSES, never swept because everyone thought it was pinned.**

**WHAT IT COSTS: RUNG 3 DOES NOT EXIST.** At its census state the dispatch lean is **0**; there the
s147 entry reads `genuine False / resid -3.294e-01 / overlap -32.989` against `True / +6.745e-05 /
+1.126` at 648, and re-solving the locus at lean 0 (runways 100..400 step 2) gives **0 genuine
entries**. s144's pinning (thrust 14 alone, plow ceiling 180->160 u, 8->4 rungs clearing, genuine
51->40, unbroken 13->8) all rests on 648 -- it "corrected" a family scanned at 0, which was nearer the
truth. **The correction wipes the LEAD, not the ladder:** re-census (in flight,
`_generated/s106/s148_lean_census.json`) rungs 1-10 -- rung 3 **0** (was 1); rung 5 **9** (10) owes
101.95 u -> **bound 100, the new lead**; rung 6 13 (13) 107; rung 7 1 (4) 107; rung 8 7 (6) 109;
rung 10 19 (17) 108.

**FIXED + GATED (tracked):** `_sync_from_core` + `_step_native` now sync `m351C`/`_draw_lean` (both
native branches are pure delegation + copy-back, so physics cannot move), and `test_freerun_native.py`
gains both to its 0-ULP allowlist. `pytest` **1203 passed, 3 skipped, 8 xfailed**, counts unchanged.
New KB: `strategy/the-lean-is-the-rolls-own-dispatch.md`; migrated claim
`history/the-delivered-lean-was-an-unsynced-mirror.md`.

**NOTHING DELIVERED, CORRECTLY** -- `clip_roll.fire` never returned a CUT_F.

**TRAPS.** (a) `terminal_keep.DELIVERED_LEAN` is STILL 648 in tracked source, left deliberately -- the
lean is per-plan, so it needs a considered replacement, not a new magic number. (b)
`razor_depth.DELIVERED_LEAN` = 64761 is a DIFFERENT constant (a console-delivered clip's, signed -775)
-- do not sweep it in unmeasured. (c) **A trailing `&` inside a Bash tool call does not survive even
with `run_in_background`** -- the launching shell exits and takes the job (killed the census once at 7
rows). Use `run_in_background` and NO `&`. (d) The `confirm` CACHE makes a census's first rungs look
~1 s when uncached ones are ~150 s -- never read a rate off the cached head.

**NEXT:** finish the census and re-rank (rung 5 leads at 100); re-read every s144-s147 number quoted at
648 incl. `TerminalKeep`'s box and `fixtures/courtyard_terminal_family.json`'s lean-648 records; then
SWEEP THE LEAN AS THE AXIS IT IS (fire the aim, read the entry-frame `m351C`, solve THERE, vary the
approach so the dispatch turn writes another); carry the 1066x density into whatever lands it -- the
landing is bought in PREFIX FAMILIES, not fan width.

### s148 CENSUS RESULT (done, `_generated/s106/s148_lean_census.json`)
All 49 rungs at their own DISPATCH lean: **16 of 49 have a genuine entry, against 19 at the stale
648** -- and it moves BOTH ways, `clip-band-per-lean.md`'s jagged band exactly (rung 27 **13->16**,
rung 10 17->19, rung 36 **0->2**; vs rung 12 18->13, rung 7 4->1, **rung 3 1->0**). Ranked:
**rung 5 n 9 owes 101.95 u -> bound 100 (-1), THE ONLY RUNG UNDER THE CONSOLE**; then 6 and 7 at 107,
10 and 15 at 108, 8/16/20 at 109, 12/24/27 at 110, 29 112, 36 115, 25 116, 37 118, 42 121.
**Rung 3 is gone and the margin collapsed 8 frames -> 1.**
**THE AXIS IS DEGENERATE AT THIS AIM: all 49 dispatch at lean 0** -- the lean is real and plan-chosen
(one at-cap cloud reached -130..+240) but the terminal's aim from a settled 3-frame handover barely
turns, so a different lean is bought through the APPROACH (the facing the dispatch frame turns
THROUGH), not the aim. **NEXT = re-run the s148 stack on RUNG 5 at lean 0** (budget 73+f+18<=100 ->
f<=9, its 101.95 u is 6 walk frames at the cap, so 3 frames of slack, not rung 3's apparent 7).

## s149 -- RUNG 5's BLOCKER IS TETRA'S WALL, AND THAT GUARD IS A PRUNE FOR A CONSOLE-GATED MECHANIC

**1. THE ENDGAME'S NUMBERS ARE CONFIRMED, INDEPENDENTLY.** `_notes/s149_rung5.py`: rung 5's dispatch
lean is **0** (measured by firing its own aim and reading `m351C` at the entry frame, not inherited),
all **9** census entries re-read GENUINE there, `need` **101.94509** u and bound **100** reproduce
exactly, terminal cut_step 16 / **18** roll frames.

**2. THE s144 "THRUST 14 ALONE" PIN, RE-READ AT LEAN 0.** thrust 13 barren at BOTH leans (0/0);
thrust 14 **51 genuine / 13 unbroken** at lean 0 vs 40/8 at 648; thrust 15 **82/1** vs 107/**0**. So
14 keeps the pin on COST (18 roll frames vs 19) but "alone" is false at the true lean. **The lean-0
BOX IS WIDER than the 648 one that replaced it**: along 47.50..112.50 (was 57.50..102.50), runway
185..265 (was 185..245), tfc 97.50..182.50 (was 102.50..162.50), l0_band 0.5736..4.8928 (was
3.0693..5.2277). s144's narrowing was the stale mirror's.

**3. ZERO OF THE 49 RUNGS IS AT THE ROLL CAP** (off the banked census, no compute): `roll_nspeed` of
every delivered speedF is **5.00..12.73, never 26**, so every ladder bound prices a roll its own
handover cannot dispatch and the missing term is the CONVERSION to speedF >= +17. **DERECK STEER
(s149): 26 IS A THRESHOLD, NOT A LOCUS TO TRADE** -- the cut frame's displacement is `nspeed` + the
**23.22 u** constant ANM_CUT root translate against a seam minimum of ~**49.46 u**, so nspeed 5 gives
28.2 u and cannot cross the wall at ANY entry (and 26's own 49.22 still needs the ~1.23 u CC-push to
tip it). **The sub-cap axis is CLOSED, not unexplored** -- s82 measured it from the other side. I
mis-read `roll_nspeed`'s "a sub-cap roll is a DIFFERENT locus, not a worse one" as leaving the low end
open; it does not.

**4. THE DISTANCE WAS NEVER THE BLOCKER.** From the HERD END the cheapest genuine dispatch point is
**83.7 u = 4.92 frames at the cap**, 41/41 straight-segment samples wall-free, all 9 entries + their
dispatch points clear with **117..171 u** of margin. The census's 101.945 u is measured after the
backslide has spent **26.73 u** of runway on the three settle frames -- **price a rung from the herd
END or the bound is ~18 u pessimistic**.

**5. THE CONVERSION IS PAID, AT THE LIVE csangle, NO CAMERA BILL** (`_notes/s149_cap.py`, 82432
rollouts, 69 s native): **122 at-cap dispatchable frames / 104 states -- 2 at frame 4 (total 95), 102
at frame 5 (96)**, 2 and 24 talk-free, budget 9. The PRE-FRAME is the whole trick: Tetra is IN the
front cone at the handover, so a bare L locks the ACTOR into proc 9, whose slide caps at speedF **12**
and never reaches 17. (`away_walk`'s recipe needed the SNAP csangle only because it pins the pre-frame
to the ESS turnaround.)

**6. THE BLOCKER: TETRA'S WALL, and it killed both beams 100%.** The handover carries her **16.5 u a
frame** at a wall she has **+52.46 u** of slack from; `objective.frame_is_wall_free` refuses her at
**herd+4 (slack -0.28) ON NEUTRAL INPUT**, so the census state (herd+3, +10.13) is ONE FRAME from
illegal, and every one of stage A's 104 at-cap states has her inside **+4.5..+12.4 u** of her cylinder
edge -- less than one push frame. Both beams died wholesale the next frame: **0 of 205600 children,
100% wall_tetra** (not follow; Link never comes within 87 u of a wall).

**7. AND THE GUARD IS A PRUNE, NOT PHYSICS.** `seeds.make_freerun` leaves **`walls_tetra` None**, so
Tetra is a bare XZ plow point -- the config that drove her 53 u THROUGH the courtyard back wall (s86)
-- and `frame_is_wall_free` is the conservative stand-in. **The WALLED engine is the console-gated one**
(`cross_engine.composite_rollout` defaults it ON; `rollstab.cc_stepper`: "a real, live-gated MECHANIC
-- a wedged Tetra's own CC recoil is canceled, so she HOLDS"). Measured (`_notes/s149_walled.py`):
walled vs unwalled **BIT-IDENTICAL through frame 3**, parting at frame 4 exactly where the guard
fires (the self-gate), and the walled Tetra **BRACES at wall distance exactly 50.000**, moving
**0.13..1.96 u/frame** against 9.48..7.00. **So rung 5's 9 frames are intact, and a braced Tetra is
not a worse target but a FIXED one** -- what a 1e-4 u razor wants.

**8. TRAP: THE NATIVE STEP IGNORES `walls_tetra`.** Measured all four ways -- native+walled passes
through the wall exactly like native+unwalled; only the PYTHON path braces. A walled search must be
`native=False`, at **717 clone+steps/s against 9406, 13x**. Porting Tetra's `mObjAcch.CrrPos` into
`LandCore.step_courtyard` is what makes a walled beam affordable.

**TRAPS RE-PAID.** (a) A beam collapses without the PENDING INPUT in its key -- at `input_delay=1` a
whole generation is physics-identical, so a position novelty key kept **1 of 513** and a (runway,side)
CELL key kept **1 cell**; key on `(cell, delivered stick)` and round-robin over cells. (b) **A beam
ranked on distance cannot find the conversion** (s148 said so): `s149_reach.py` ran 5 frames with **0
fireable nodes**. Enumerate the conversion family, THEN beam off it. (c) `roll_nspeed` needs speedF
**>= +17.0 exactly** (16.9 -> 25.85, not at cap).

**NOTHING DELIVERED, CORRECTLY** -- `clip_roll.fire` never returned a CUT_F. No tracked library/test
change; only the README status box.

**NEXT:** finish the WALLED stack on rung 5 (`s149_cap.py walled=1` -> `s149_land.py walled=1`, both
already carry the mode: guard reduced to LINK's cylinder, Tetra's pass modelled); then PORT Tetra's
`CrrPos` into `step_courtyard`, gated the `test_body_co_native` way against the Python walled path on
rung 5's own herd (known bit-identical through f3, parting at f4). Hunt a resid SIGN CHANGE, not a
minimum -- rung 5's entry widths are 6.4e-05..3.4e-04.

### s149 WALLED RESULT (the stack ran; contact at TOTAL 98 and the razor is BRACKETED)
Stage A walled survives to f6 (51 at-cap dispatchable, total 97), deficit closing **21.49 -> 16.96 ->
13.20**. Stage B walled (`_generated/s106/s149_land_walled.json`):

    f7  total  98 | deficit 0.0000 | 171 in contact, 159 resid- / 12 resid+  <- SIGN CHANGE
                    spans -2.8165e+01..+2.9435e+01; best |resid| 1.65958e-01 at LEAN -98 (65438)
    f8  total  99 | 0 in contact (fireable 15163 -> 1799)
    f9  total 100 | 0 fireable -- the cap is LOST

s148's best was ONE residual across 514 nodes at total 100 with no bracket. **But the bracket is
UNDER-SAMPLED: 171 nodes express only 4 DISTINCT residuals** (all feet 74.073 -- the pending-input tie
one layer on) against a ~1e-4 acceptance. **And the best node's dispatch lean is NOT 0** -- in-contact
leans `[0, -98, -80, -15]` -- so s148's "the axis is degenerate at this aim" is a property of the
SETTLED handover, not of the at-cap cloud, exactly as s148 predicted.

**NEXT = FAN AT f7, DO NOT WALK TO 8-9** (a f7 hit is total 98, and the beam cannot keep the bracket
past it): widen the PREFIX (f5-f6, the parents feeding it), draws per prefix family per
`clip-lottery-draws.md`, fan at `len(log)-2`. The f7 cloud is banked ready under `bank['7']` (300
fireable / 171 in contact) -- re-seed off it, do not re-beam. Then PORT Tetra's `CrrPos` into
`LandCore.step_courtyard` (13x) gated `test_body_co_native`-style against the Python walled path on
rung 5's herd, whose console-locked pin **-940.25561523** is the gate's own reference.

### s149 END -- DERECK: THE WALL PASS IS A PHASE SETTING, AND THE 101 IS NOW A SEARCH-SPACE GATE
**THE RULE (standing):** Tetra's `dBgS_Acch::CrrPos` is **OFF during the herd** -- there
`objective.frame_is_wall_free` IS the intended constraint (`objective` rule 4: keep both actors off the
walls, since the herd is stepped unwalled) -- and **ON and REQUIRED for the FINAL ROLL + THRUST**,
where the clip happens with her wedged in the corner and her brace is the mechanic. My first read ("the
guard is a prune to be lifted") was half wrong: only the TERMINAL needed it lifted. The s149 walled
result stands under the rule -- its 73-frame herd is the banked ladder rung, bred with the guard ON,
and only the post-herd walk + roll ran walled.

**"WE NEED A WAY TO ENSURE CRAP LIKE THIS CANT HAPPEN"** (Dereck) -> feed the existing 101 solution
through the search and gate that the right physics are on at the right phases. **It caught the bug
retroactively: replayed through the search's own configuration, the unwalled prune refuses the
console's OWN clip from frame 90 of 107** -- seven frames into the clip roll and every frame after,
including the cut at 101. The best plan in the repo sat outside the search's own range and nothing said
so ([[search-space-contains-human]]).

**SHIPPED (commit `f0d1791`):** `seeds.make_freerun(..., walls=False)` + **`seeds.wall_for_terminal`**
(the phase boundary; sets `walls_modelled`; **REFUSES a native run** -- the C core has no BG pass and
assigning the mesh post-construction bypasses `FreeRun.__init__`'s guard, which is exactly how s149's
probes got a Tetra that looked walled and was not); **`objective.frame_ok(run, walls)`** (refuses only
the actors whose pass is unmodelled -- the RUN decides, not the caller);
**`tests/test_console_solution_in_search_space.py`** (6) and **`tests/test_tetra_walls.py`** (5).

**THE GATE'S OWN BUDGET (Dereck: essential it runs under 1 s): 11 tests, 0.79 s total, slowest 0.16 s**
against the enforced 1.5 s/test + 120 s total. Fast because they replay LOCKED fixture logs with
module-scoped fixtures -- no planner, no beam ([[slow-offline-tests]]). **Mutation-checked: reverting
the fix fails two of them by name.** Turning the pass on is bit-identical over the 45-frame window
every 0-ULP gate is built on (both actors 331-337 u from geometry there), so nothing banked re-bases.
`TOTAL_INCUMBENT` is now tied by test to the locked log's own `cut_i`.

**ALSO LEARNED:** the console's delivered clip is **thrust 15 / m351C 64761** (`razor_depth`'s
DELIVERED_LEAN, signed -775), not the thrust-14 / lean-0 terminal the ladder is pinned to -- worth
reconciling before the next terminal claim.

### s149 THRUSTS -- AN OPTION SET (13/14/15 = 17/18/19 FRAMES), AND THE SLICE'S "BARREN" WAS AN ARTIFACT
**DERECK: thrusting works on frames 13-15 and it is good to have options.** `roll_frames = cut_step+2`,
so 13/14/15 cost **17/18/19** frames. Re-scored on the REACHABLE frame-7 cloud at each node's own
dispatch lean (`_notes/s149_thrusts.py` -> `_generated/s106/s149_thrusts.json`, no re-beaming -- the
entry is thrust-independent), **ALL THREE BRACKET THE RAZOR**:

    thrust 13 | 17 roll frames | TOTAL 97 | 158 neg / 13 pos | resid +-45.7 | best |resid| 6.76
    thrust 14 | 18 roll frames | TOTAL 98 | 159 neg / 12 pos | resid +-29.4 | best |resid| 0.166
    thrust 15 | 19 roll frames | TOTAL 99 | 158 neg / 13 pos | resid +-11.9 | best |resid| 0.245

**SO "THRUST 13 IS BARREN" WAS A SCAN ARTIFACT, NOT A REFUSAL.** The banked family reads 13 as 2414
roots / 0 genuine -- but EVERY banked scan is a `side = 0` SLICE (`terminal.RollFrame.item` puts Link
on the brace line), so it cannot vary LINK's lateral, the axis the endgame hinges on (s147). A zero
from it is not proof ([[infeasible-needs-proof]]). **NEVER use the banked family to refuse a thrust.**

**THE TRADE-OFF: the bracket TIGHTENS as thrust rises** (+-45.7 -> +-29.4 -> +-11.9), so 13 is the
cheapest and coarsest, 15 the tightest -- **and the console's own delivered clip is thrust 15 / m351C
64761, the most expensive of the three**, so the options are worth up to 2 frames against it. All on
4-value samples (the pending-input tie), so the ordering is suggestive, not established. 0 genuine at
every thrust -- still no plan.

### s149 SCOPE -- THE WALL BUG WAS IN ONE OF TWO ENGINES; THE CENSUS SURVIVES
Dereck asked whether every census claim is worthless given the missing BG collision. **NO -- checked,
not reasoned.** Two engines, only the walk stepper was broken:
- **`ShoveCtx`/`tww_sim/core/_shovec.pyx` = the RAZOR engine** (scores a candidate roll; produced the
  census, `courtyard_terminal_family.json`, the 288 placements). **It HAS the `dBgS_Acch::CrrPos` pass
  for BOTH actors and always did** (module docstring line 7). Verified at the console's own hit config:
  Tetra's z pins at **-940.25562 for roll steps 10-14**, the console-locked brace, to the bit.
- **`from_f0.FreeRun` = the frame-by-frame HERD/WALK stepper.** Pass optional, never wired by
  `make_freerun`. THIS was the broken one.
**BUT 11 OF THE 16 "LIVE" CENSUS ROWS ARE STILL FICTION -- Dereck was right to push.** The razor engine
is sound, but the (Link,Tetra) PAIR it was handed came from an UNWALLED herd replay, and a correct
verdict on an impossible input is worthless. Measured over all 49 rungs (walled vs unwalled, first
divergence vs herd length H):
- **8 rungs diverge INSIDE the herd** (42,43,44,45,46,47,48,49 -- all 2-3 frames before the herd ends):
  the BANKED HERD ITSELF is not what the console-gated engine produces.
- **16 diverge in the 3 SETTLE frames** the census added (herd fine, census state fiction): 8,10,12,15,
  19,24,25,27,29,30,32,33,36,37,38,40.
- **25 never part through herd+3.**
- **5 rungs are inside her own CYLINDER at the census state** (illegal Tetra): 8 (-3.57), 10 (-5.47),
  12 (-15.35), 30 (-11.69), 37 (-5.86).
**Of the 16 rungs the census called LIVE: 1 diverges inside the herd (42, n=5), 10 in the settle frames
(8:7, 10:19, 12:13, 15:14, 24:3, 25:10, 27:16, 29:3, 36:2, 37:4 -- every high-count row), and only 5
are CLEAN: rung 5 (n 9, bound 100), 6 (13,107), 7 (1,107), 16 (4,109), 20 (2,109).** The LEAD survives
by luck, not design. **CONSEQUENCE: the census's live/dead labels may NOT order or prune a search** --
reopen all 49 rungs, replay herds on the WALLED engine, and re-verify the 8 herd-diverging rungs before
quoting their bounds.

**So the defect was REACHABILITY, not scoring:** the guard stopped the search from REACHING states
where she neared the wall; the razor verdict on every state it did reach was correct. Rung 4's census
zero is a real thrust-14/own-lean measurement taken WITH collision on -- it is only not a refusal at
thrust 13/15, which that census never ran. (GOTCHA when re-checking this: a `wall_dist < 50.0` test
reads a PINNED Tetra as "inside" -- she sits at 49.9999 vs the radius 50.0.)

### s149 LADDER PROVENANCE -- THE BANKED LADDER IS RANKED AGAINST THE WRONG TERMINAL, AND 89 IS NOT A FLOOR
Checked when Dereck asked how I knew 89 was the lowest total. Two facts off
`fixtures/courtyard_candidate_ladder.json`'s OWN header:
- **It was bred for a DIFFERENT TERMINAL:** its `terminal` block is **thrust 11 / facing 40660 /
  cut_step 13**, `crossing_bar` -77.83 -- while everything since s124 scores it at **thrust 14 / facing
  40835 / cut_step 16**. The 49 rungs were ranked to hand over to a terminal that is not the one being
  solved.
- **`CONFIRMATION_WARNING`: "NO rung on this ladder has a CONFIRMED genuine entry (session 142)"** --
  every `bound` used `handoff.endpoint(roots=True)`, the UNCONFIRMED razor curve, "an under-estimate by
  construction". Its `genuine_region` note: the ladder parks Tetra at `l0` +29.47..+51.97 against a
  genuine band of [4.11, 12.67], "four times outside this band".

**SO 89 IS NOT A FLOOR ON THE PROBLEM.** It is `min(banked herd)=69 + 3 walk + 17 roll`, and
`objective.frame_floor(env)` = **72.12 -> 73 frames** just to put her on the nearest genuine coord at
the push ceiling (budget 75, preferred 74). Rung 4 herds in 69 *because it never lands her*. **The
honest floor for a plan that actually lands is 73 + 3 + 17 = 93**; floors 89..92 are unfinished-herd
artifacts. Of 147 units (49 rungs x 3 thrusts) **25 have floor >= 101 and cannot beat the console --
drop before any work** (and LOG the drop, never omit silently). A hit at 97 prunes 76 of 147.
**BEFORE any overnight run: re-price the ladder at the real terminal, or order on `frame_floor` + the
herd's measured cost rather than on the banked `herd` field.**

### WHAT THE 101 ACTUALLY IS (do not get this wrong -- s149 did)
**The 101 is a DELIVERED, CONSOLE-CONFIRMED, END-TO-END CLIP**, not a bound and not a target on paper:
`fixtures/courtyard_clip_s90_console.json` (s90, LOCKED) -- 107-frame input log, roll dispatches at
`entry_i` 83, UP+B at `b_log` 100, **CUT at `cut_i` 101**, and its own verdict reads "THE FRAME-MINIMAL
CLIP IS ON CONSOLE, IN ONE DELIVERY": at the cut frame Link is bit-identical to the prediction, 49.7368
u off `old` and out through the seam, Tetra 0-ULP and stt 3, and five frames later he is in
`daPyProc_FALL_e` at (-1751.6227, -1015.5969) -- off the courtyard floor, which is what a seam clip IS.
`objective.TOTAL_INCUMBENT` == that log's own `cut_i` (gated,
`tests/test_console_solution_in_search_space.py`).

**SO THE PIPELINE IS VALIDATED AND HAS BEEN SINCE s90.** The ONLY open work is BEATING 101. There is no
"first delivery" left to earn, so a slower-but-delivered plan is worth NOTHING and any unit whose floor
is >= 101 is simply dead -- never search it for "pipeline validation" (s149 argued this and was wrong;
Dereck: "In the 70s sessions we found the 101 dtm"). Delivery mechanics: [[tetrapush-dtm-delivery]].

### s149 REGIMES -- s149's RESULT IS STAY-IN-CONTACT; WALK-AWAY IS UNSEARCHED AND THE RANK IS WHY
Dereck asked whether the search covers Link walking AWAY from Tetra as a dedicated phase vs staying in
contact throughout. Measured, not reasoned:
- **REGIME 1 (stay in contact)** = `TerminalKeep(unbroken=True)`'s zero-walk-away box, **13 of the 51
  genuine** at thrust 14 / lean 0; costs no walk frames.
- **REGIME 2 (walk away as a phase)** = what `away_walk.py` is for, and where the CENSUS's own targets
  live (runway 186..326, Tetra behind at `along` 51..68, Link owing 83.7..210 u -- unpayable without
  breaking contact).
**s149's ENTIRE RESULT IS REGIME 1:** its 3 best f7 nodes hold feet **49..74 u** against `CO_R_SUM` 80
and NEVER break contact. So the 97/98/99 bracket is the stay-in-contact shape, and stage B reached it by
finding contact LOCALLY -- never by walking to a census entry. **That is why it read deficit 0.0 at f7
while the census said Link owed 83.7 u: the two numbers were never measuring the same plan.** (I had
conflated them all session.)
**REGIME 2 IS EFFECTIVELY UNSEARCHED and the RANK is the reason:** `(fireable, contact deficit, |resid|)`
REWARDS contact, so a beam never spends frames getting worse to reach a distant entry -- s148's
conversion myopia one level up. The census only ever priced regime 2 by STRAIGHT-LINE distance; nothing
has simulated it. **The driver must carry the regime as an EXPLICIT axis** -- regime 1 on the contact
rank, regime 2 as an ENUMERATED phase with its own rank that does not punish leaving her -- then compare
on TOTAL frames. One rank must not arbitrate both.

## s150 -- THE SEARCH IS BUILT, GATED AND RUNNING: EVERY HERD THROUGH THE MACHINERY THAT DELIVERED THE 101
**`harness/tetrapush/overnight.py` + `overnight_io.py`, 17 gates in `tests/test_overnight_driver.py`
(1.7 s), commits `d24f990` + `3a86b18`.** The pipeline is NOT a new one: `entry_fan.iter_fan2`'s OpenMP
`prange` fleet -> `ShoveCtx.sweep_par` -> `entry_search.confirm_entry` (a REAL A-press) ->
`cross_engine.agree` (the walled composite, frame for frame) is what produced the banked console 101, and
it had only ever been pointed at ONE herd. **Measured on this hardware:** the fan is **216k core-frames/s
at 12 threads, 74k at one -> 11 workers x 1 thread BEATS one 12-thread process 3.8x**; the razor sweeps
**75.5k scorings/s**; the walled terminal steps **4220 clone+steps/s native vs 350 Python (12x, the s149
port)**; `dispatch_lean` 197/s and `clip_roll.fire` 231/s (gate those, do not spend them per node).
**THREE SHARED STAGES SILENTLY REPLAYED THE CONSOLE ARRIVAL whatever seed they were handed** --
`walk_fan`, `confirm_entry`, `entry_camera.cam_trail` all called `continue_walk(...)` without ``log=``,
the same defect `entry_fan.base_core` fixed at the fan in s105. Fixed in place, inert at every default.
**THE FAN NOW CARRIES TETRA** (`entry_fan._fan_chunk(with_tetra=)`) -- every earlier pass scored a whole
fan against ONE pinned Tetra, true only when contact is broken (the console arrival), false of a herd end
still plowing her. The razor takes her per item, so **regime 1 and regime 2 are ONE population**, which
is s149's "explicit regime axis" answered by removing the need for one.
**TWO MODEL CORRECTIONS THE FAN NEEDED, both measured:**
* **``at_cap`` is `roll_nspeed(speedF) == 26`, NOT `speedF == 17.0`.** The conversion lands at **+17.6**
  (17.183998 / 17.833548 on real rungs), so the equality every fan since s80 pruned on would have
  refused the only states worth searching.
* **A plan needs an L AXIS the triple plan encoding cannot express.** Off ANY herd end a bare walk-up
  tops out at speedF **exactly 12.000, proc 9** -- 1206 Python rollouts and 57025 native ones agree --
  because Tetra is in the front cone so the L locks the ACTOR. **The cone-clearing PRE-FRAME is the whole
  difference** (s149 said it; this is it re-measured from the other side). Plans are
  ``(n0, sx, sy, l, j, ...)``; `overnight.plan_rows` delivers the L, and `confirm_entry(rows=)` /
  `cross_engine.agree(log=, ix=, tetra=)` take a raw log so the ONE verdict implementation still decides.
**THE WORK ORDER IS THE OBJECTIVE:** one item per ``(herd, walk length)``, ordered by
``total = herd + walk + thrust + 4`` ASCENDING -- **348 items over 46 herds, totals 87..100**, 4 herds
dropped with a proof. Unit-major ordering would spend the first hours on 100-frame plans off rung 4 while
a 91-frame plan sat unexamined on rung 5.
**A FAN'S COST IS ITS CORE CLONES, not its frames** (2.6 M clones was 31 s where the stepping was ~5 M
frames), and fleets grow as ``|pre| x walk`` -- so the flip alphabet is now COARSENED until an item fits
`LEAF_BUDGET` 8 M clones and the stride is logged (`alpha_stride`). Every item 1..330 s; the whole queue
~2 h instead of never finishing walk 5. The PRE is never coarsened (its job is only to rotate him).
**CONTAINMENT IS GATED END TO END** and it is a COMMAND: ``overnight verify-console`` (12 checks) --
the console herd is a live item, its walk length is inside its own budget, its walk letters are members
of the 11405-class fan alphabet, its aim is in the alphabet at the camera the fan runs, a real A-press
re-derives its entry on all six flags, and **its own candidate comes back DELIVERABLE with the cut on
frame 101**. Plus `test_the_composite_log_is_the_console_log_row_for_row`: the driver rebuilds the
delivered movie byte for byte with no sim in it.
**WHAT THE RUN SAYS, and it is the instrument working:** outside contact the razor's residual is a DEAD
CONSTANT, so ``0 genuine`` is a DISTANCE statement, not a refusal. The reporting therefore carries the
CONTACT population, the best overlap and the residual SIGN SPLIT. At walk 1-3 the whole at-cap
population is **17..95 u short of touching her**; rung 5 at walk 3 reads best overlap **-16.98 u from 424
at-cap candidates**, which REPRODUCES s149's stage-A deficit of 16.96 from a completely different
enumeration. Contact closes ~4 u a walk frame, so **walk 7-8 is where a hit can exist** -- which is what
the clone budget was spent to reach.
**KNOWN COVERAGE GAP, sized, deliberately not added mid-run:** the families are ``pre + flip + hold`` with
the hold on the FLIP's own stick, so nothing steers PER FRAME after the conversion (s149's stage-B beam
did). The fix is cheap because the at-cap prefix set is small (424 at walk 3): extend each at-cap prefix
at ``walk - k`` by ``k`` fine frames -- ~130 s an item at k=1, ~150 s at k=2 with a 400-node beam.

## s150 CORRECTION (same session, written after the section above): DO NOT TRUST THE SEARCH RESULTS ABOVE
The s150 section above was written mid-session and is OVERCONFIDENT. Read it, then read this before
acting on anything in it. Three things happened after it was written, in order:

**A real memory bug shipped and crashed the first focused pass.** `_steered_tail`'s prefix pool held
one live `LandCore` clone per at-cap prefix with NO CAP -- at `pre_stride=16` over the full 11405-letter
alphabet that is hundreds of thousands of clones alive at once. 11 workers hit `MemoryError`
simultaneously and lost 3 items outright; the tail never called `beat()`, so a stuck worker read as
merely slow for over an hour with no way to tell "working" from "hung". **Caught by Dereck asking
whether an overnight run could possibly be sound, not by a measurement of ours.** Fixed, commit
`d128031`: `PREFIX_CAP=20000` truncates the pool (ranked on distance to her) the moment it is crossed,
logged not silent; `beat()` now fires from inside the tail's own loops.

**The overlap reporting was pointed backwards, and the real coverage was ~400x lower than reported.**
The console's OWN genuine clip sits at overlap **+1.2259 -- a GRAZING touch**, not at the maximum. Deep
overlap is Link buried in her, a different geometry that cannot clip. Measured over 72000 scorings off
the console herd: **96.1% land at overlap < -5, only 0.33% in the clippable band [0,3)**. So a pass's
razor-scoring count overstated its real coverage by ~400x, and "best overlap +63.5 u" (what s150's first
run reported as its headline) was Link 62 u PAST the band, not close to it. Fixed, commit `5264409`:
`CLIP_TARGET=1.2259` / `CLIP_BAND=(0,3)`, `band_draws` is now the coverage number, `best_overlap` means
nearest the target. A hypot-based prefilter for the band was measured and REFUSED before shipping --
39.7 u wrong on the known clip, because she is plowed 47 u during the roll; only the full sweep may
decide. See `knowledge/strategy/clip-overlap-band.md`.

**THE SERIOUS ONE, found while re-verifying the memory fix: the fan's conversion is a hand-rolled
substitute for an existing, validated primitive, and it was never checked against it.** The walk-fan's
conversion (`overnight.py`'s `PRE` + `L_AXIS`: turn, one L frame, release) is code written fresh this
session. `[[tetrapush-frame-minimal]]`'s away-walk work already built `away_walk.escape_atom`, already
gated, whose own docstring says it produces **"the console's own delivered shape"**: turnaround ->
L-conversion -> **ROTATE** (one frame, off the flip bearing) -> **BACKWARDS SLAM** -> hold the exit
stick, with an `exit_run` tail. Confirmed directly against the locked console log
(`fixtures/courtyard_clip_s90_console.json`): frames 71-77 of its OWN 78-frame herd ARE exactly this
atom (L at frame 71 on stick `176,247`, released holding the same stick at 72, rotate/slam/hold through
77) -- **seven frames before the herd hands off, not a separate walk-away ending appended after it.**

**Why `verify-console` passing (12/12) did not catch this.** The console's "herd" is defined as its own
recorded first 78 frames, which already CONTAIN the atom as fixed history; its walk plan
(`[0, 208, 110, 2, 169, 192, 2]`) is four plain directional frames needing no conversion, because the
herd already performed one. Containment proved the forward model REPLAYS the console's exact recording
bit-exact; it never exercises the fan's OWN conversion code, because that item never calls
`_families`'s PRE/L logic at all. **The 49 banked ladder herds are the ones that do** -- frozen
mid-backslide, before any such conversion, so the fan has to invent one from scratch, and has been
doing that with a cruder tool (no rotate, no slam, no exit tail) than the one that actually works on
console. None of the 48 non-console herds this session searched have ever produced a genuine hit; that
is no longer a surprise. **Lesson for future memory: containment-of-the-answer and correctness-of-the-
generator are different claims, and a gate proving one says nothing about the other** -- check whether
a passing containment test actually EXERCISES the code path you think it validates, not just whether it
passes.

**STANDING RULE ADDED THIS SESSION: before hand-rolling ANY game-mechanic recipe (a button sequence, an
input shape, a conversion), grep for an existing primitive first** (`away_walk.py`, `clip_roll.py`,
`two_roll.py`, `entry_search.py` are the usual homes). This session paid real search time (and two
sessions of trust) for skipping that check once.

**NEXT SESSION'S FIRST JOB, gating everything else**: rework `overnight.fan_exact`'s conversion phase
to call `away_walk.escape_atom` (or the primitives it composes) instead of the ad hoc `PRE`/`L_AXIS`
construction -- read the whole handoff (`_notes/tetrapush-handoff-2026-08-11-session150.md`) before
touching it, since `escape_atom` was built for a DIFFERENT terminal shape (the pre-s123 "away walk"
ending) and may not compose directly with the fleet-based fan without adaptation. Do not trust or
re-launch a multi-hour search on the 48 non-console herds until this is done and containment is
re-verified.

## s151 UPDATE: THE REWORK IS DONE. THE ABOVE BLOCKER IS RESOLVED -- read this section, not the s150 one, for what to do next
`_families`' `lswitch` (L-press, release, nothing after) is DELETED, not kept beside its replacement.
New `overnight._atom_junction`: runs `away_walk.escape_atom`'s own recipe (L-press, release, rotate,
backwards slam) NATIVELY, per candidate, off `away_walk.flip_arc`'s bearing sweep (NOT a stick-byte
alphabet -- see the design correction below). `_atom_candidates` composes it into `fan_exact` the same
way the existing PRE segment already composes: a junction, then the ordinary family sweep for whatever
walk remains. Full detail: `_notes/tetrapush-handoff-2026-08-11-session151.md`.

**Confirmed against the sim first, independently of s150's own (correct but ungated) claim.** Seeded a
`FreeRun` at the console's own locked log truncated to frame 71 -- one frame before its recorded
conversion begins -- and ran `away_walk.probe`'s own knob sweep off it: `flip_bearing=hl.bearing_bam()`
(the herd's own down-bearing, no sweep needed), `rotate_side=-1`, `rotate_off=0x6000` fires clean --
separates in 5 frames, ZERO dips, better than the human's own 7. The proc sequence (6 -> 7 ATN_MOVE -> 6
at +17.6 the negation -> 24 MoveTurn halved to +8.5 -> 6 settling at +17.0) matches the console's own
recorded frames 71-77 exactly. The byte-for-byte stick values do NOT match -- a real, ALREADY-DOCUMENTED
~144 BAM camera-chase gap (`_clone_for_atom`'s own accepted cost) -- expected, not a defect worth
chasing further.

**A real design correction mid-session, caught by a gate, not by inspection: the flip axis cannot be a
stick-byte alphabet.** The FIRST `_atom_junction` swept `entry_fan.stick_alphabet` directly for the flip
candidate, and the resulting rotate/slam bytes disagreed with `escape_atom`'s own computation on EVERY
draw. Root cause: `escape_atom` always drives the L-press at FULL deflection
(`stick_for_bearing(flip, cs, msd=1.0)`), and a byte-alphabet draw is not guaranteed to already be at
full deflection -- decoding and re-encoding at msd=1.0 changes the byte pair even though the bearing is
unchanged. Fixed by sourcing the flip from `away_walk.flip_arc`'s own bearings instead (full deflection
by construction): all 168 tested combinations then agree with `escape_atom` bit-for-bit on all four
frames. **Lesson for future memory: when re-implementing a validated primitive's formula against a NEW
axis of candidates, check that the candidates satisfy every implicit precondition the primitive itself
assumes (here: full stick deflection), not just that the formula is copied correctly.**

**Containment verified the literal way Dereck asked for it**: a test seeds the same real frame-71
backslide (never the answer itself) and asserts `_atom_junction` -- the search's own generator -- converts
it to a rollable at-cap state. `overnight verify-console` still passes 12/12 unchanged (the console's own
item bypasses the conversion phase entirely, so this could not move it either way). A random sample of
300 atom-shaped candidates from a real `fan_exact` run, replayed from scratch on the wired python engine,
lands rollable-and-at-cap on ~70% of them -- the rest is the SAME prediction-vs-reality fallout
`accept()`'s multi-stage pipeline already exists to filter, not a new failure mode.

**STILL SCOPED, not silent**: `turnaround_first` is not swept (every real backslide measured so far
already faces away); the atom does not yet compose with a PRE pre-turn (runs bare off each `n0` only).
Neither blocks containment; both are honest follow-up.

**NEXT (supersedes s150's "next session" above): RE-LAUNCH A REAL `overnight run`.** Nothing from s150's
own runs (all pre-fix) is trustworthy evidence the space is barren on the 48 non-console herds -- that
conclusion is RETRACTED, not confirmed, by this session. The driver is clear to launch for real. Full
default `pytest` (1256 passed) confirmed green after the `lswitch` removal.

## s151 FINAL CORRECTION (Dereck, end of session, after the section above was written): "i refuse to
allow any search that cant also rediscover the 101 solution." Bit-exactness against `escape_atom` and
containment-of-shape on the frame-71 proxy state (both sections above) are MECHANISM proofs, not a
search-finds-answers proof -- "the driver is clear to launch for real" was premature and is RETRACTED
by Dereck directly, not by this session's own review. `[[search-must-rediscover-known-answer]]` is the
hard gate this created. Before trusting or launching anything: run the actual `fan_exact -> score ->
accept` pipeline on the console's own herd with its real conversion removed (`log[:71]`, truncated
before frame 71) and confirm it REDISCOVERS a genuine, deliverable plan <=101 -- not a replay, not a
proxy check. This is the ONLY next step; see the s152 section below for what it found.

## s152: THE REDISCOVERY GATE RAN FOR REAL. One genuine razor hit surfaced (walk 9, would total 99
frames -- 2 faster than the console's 101), `accept()` refused it, and the refusal's root cause is now
KNOWN and cross-confirmed two independent ways -- not a mystery, not a shrug.

**The gate itself, run properly** (`_notes/s152_rediscover_run.py`): seeded the console's own herd with
`log[:71]` (its real conversion removed, exactly s151's own recipe), ran `fan_exact(atom=True) -> score
-> accept` for real, widened walk 7/8/9. Walk 7: 0 genuine, best overlap 0.0006u off the console's own
+1.2259 target. Walk 8: 0 genuine, 0.00007u off, residual inside the ~5e-5 acceptance band. **Walk 9: 1
genuine hit** (thrust 15, total 99 frames) -- refused at `accept()`'s `confirm_entry` stage on a tiny
(facing 11 BAM, walk 0.013u, entry 0.027u) but nonzero exact-match gap (`confirm_entry` is `==`, no
tolerance, `[[zero-ulp-tests-only]]`). Stopped widening past 9 (escalating per-walk cost; Dereck's call,
not a silent cap) to dig into the one hit instead of blindly continuing to 13.

**A real tool gap, found and fixed: `overnight.score` was discarding the exact data needed to look at a
near-miss.** `best_overlap`/`best_resid_in_contact` were bare running scalars, no record of which
candidate produced them -- so inspecting one meant a full expensive re-run (Dereck, directly: "I want
the tool to actually record the inputs when they find them. We should never need to recompute like
this."). Fixed: `best_overlap_row`/`best_resid_row`/`near_rows` (capped, flagged if truncated) now carry
full candidate identity, same shape as a genuine hit. Purely additive, gated, full suite unchanged.

**Broader survey (86 rows across walk 7/8/9, using the fixed `score`): 0/86 pass `confirm_entry`, and
the facing delta is NEVER continuous -- exactly one of 11, 31 or 81 BAM, every single row.** Position
error tracks the bucket. This pattern (three fixed values, not a spread) is what pointed at a discrete,
structural cause rather than float accumulation, and directly enabled the root-cause below.

**ROOT CAUSE, cross-confirmed two independent ways with zero shared assumptions between them.**
`tww_sim/core/camera/land_cam.py`'s `LandCamera` fires a real, DOCUMENTED 1-frame followCamera blip on
every L rising edge; re-entering manual mode afterward resets the camera's internal yaw TARGET to
wherever the yaw-chase happens to sit at that instant (mid-convergence, if the chase hasn't settled).
`harness/tetrapush/entry_camera.cam_trail` -- the camera projection the fast search injects -- builds
its own reference replay L-free (constant input, never presses L), so it never experiences this blip and
injects the PRE-blip angle for every candidate whose walk presses L -- which is EVERY escape-atom-
junction candidate, unconditionally, by construction (`overnight._atom_junction`'s first action is
always an L-press). An isolated sweep of the L-press timing alone (no atom/rotate/slam, just press-then-
release at output offsets n0=0..8) reproduced **-81 / -31 / -11 (saturating from n0=2 on)** exactly --
the identical three numbers the 86-row survey found empirically, with no parameter shared between the
two investigations. This is about as clean a root-cause confirmation as this codebase gets.
**NOT fixed**: a real fix means teaching `cam_trail` (or a sibling) the candidate's actual button/main-
stick schedule instead of a bare C-stick byte, a new 0-ULP gate against the wired camera under L=1, and a
decision on whether ordinary `_families` L=1 candidates carry the same exposure (unaudited). Scoped,
multi-piece, left for next session -- see `[[courtyard-tetra-push]]`'s standing next-step.

**Separately: Dereck asked directly, "why wouldn't confirm_entry also be native?" -- answer: it can, a
full-fidelity native path already exists, but the specific change REGRESSES 5 tests and is unmerged.**
`seeds.make_freerun(env, native=True)` already runs physics + both look models in C while the camera
stays real and live-computed (never injected, NOT the search's own stripped fast-path config) and is
already 0-ULP gated including L-press/attention-lock cases. `entry_search.continue_walk` grew a
`native=` flag, `confirm_entry` opted in, plus a genuine related fix (`continue_walk` was reading the
never-synced `link.csangle` instead of the authoritative `run.csangle` -- exactly the trap
[[tetrapush-frame-minimal]]'s s151 "Watch out for" already named). The new test passes standalone, but
the FULL default suite regresses `test_entry_camera.py` (4 cases) + `test_entry_ledger.py` (1) that are
clean on the unmodified branch -- root cause not yet found. **Preserved per Dereck's explicit
instruction ("if there's usuable code in part 2 I don't want to throw it away... do not discard it"):**
committed to `dmiller/tetrapush-native-confirm-entry-wip` (commit `e2b396e`, honest message naming
exactly what regresses), worktree checkout removed (the commit is what preserves it, not the directory),
not pushed. Dereck's own order for next session: resolve that branch FIRST, then continue the search.

**Process lessons this session, worth keeping:** (1) a background job piped through `tail -N` shows
NOTHING until the whole thing exits -- that is not evidence of a hang, judge by whether CPU time is
still climbing between checks, not by whether piped output has appeared (cost real time chasing a
"stuck" run that was just slow from CPU contention with other things running concurrently). (2) A
subagent's own "safe, small, already-gated" claim is not the same as the change passing the full suite
-- it had only run its one new targeted test; always independently verify the full suite before trusting
a safety claim. (3) A subagent again ran something slow-suite-adjacent and had to be killed directly by
Dereck -- the same recurring failure `[[slow-offline-tests]]` already documents (a s149 subagent ran the
slow suite too); be explicit in every test-touching subagent prompt about the bare default command, no
`-m slow`, no hand-picked file bundles.

## s153: ITEM (1) RESOLVED -- the native `confirm_entry` regression was a ONE-FRAME SHIFT, not a stale
field, and the WIP branch's own diagnosis of its own bug was backwards.
`dmiller/tetrapush-native-confirm-entry-wip` (`e2b396e`) blamed `link.csangle` being stale on a native
step (true) and "fixed" it by reading `run.csangle` AFTER `run.step()` instead (wrong): the camera runs
at the END of a frame and commits the csangle the NEXT frame decodes against, so a post-step read is
one frame ahead of what THIS frame actually used, **in both engines, wired included** -- not a
native-only concern. `entry_camera.cam_trail` builds the search's entire camera reference off exactly
this field, so every L-pressing candidate's trail silently shifted by a frame, landing the regression
precisely on `test_entry_camera.py` (4 cases) + `test_entry_ledger.py` (1) and nothing else. **Confirmed
empirically before touching the fix, not guessed**: a throwaway probe stepping a wired run and a native
run side by side showed the OLD `link.csangle` read always equals `run.csangle` taken BEFORE that
frame's `step()`, never after -- in both engines, with the exact same per-frame delta sequence. Fix:
capture `run.csangle` before calling `step()`, uniformly in both engines -- reproduces the old wired
behaviour exactly AND fixes the real native staleness, since `run.csangle` (unlike `link.csangle`) is
threaded through `_run_camera` on both step paths regardless of engine. Full default suite: 1257 passed,
0 regressed. Squashed onto `dmiller/tetrapush-native-engine` as one commit (`f39a97a`) rather than
carrying the "known-broken, do not merge" WIP commit into the mainline history; the WIP branch is fully
folded in and left in place (branch deletion is Dereck's call, not made here).
**Lesson for future memory: when a commit says "likely X, not yet root-caused," that hunch is not a
finding -- diff the actual values per frame (here: one Python probe script) before trusting or building
on it.** The WIP branch's own comment ("run.csangle is what `_run_camera` actually commits") was true
and still pointed at the wrong fix, because "authoritative" is not the same claim as "the same frame."
**NEXT (unchanged from s152, now the real next step for real): teach `entry_camera.cam_trail` the actual
L-press followCamera blip** (the camera-yaw-reset root cause s152 found and cross-confirmed), then
re-run the widened rediscovery sweep (walk 7..13) with both fixes in -- that is what would satisfy
`[[search-must-rediscover-known-answer]]` for real, not another mechanism proof.

**Same session, item (2) also done: `cam_trail` now models the blip -- INCLUDING a second one the
reasoning alone missed.** `cam_trail` grows `l_frame` (press L one frame at a given index, then
release; a held L reaches the identical settled csangle by the same frame, gated). A new
`entry_camera.CamTrail` wrapper threads the correction through `overnight._fan` (auto-detects L
anywhere in a schedule) and `_atom_junction`'s rotate/slam (previously frozen at the pre-junction
csangle for the INJECTED physics value -- the stick-DECODING reference correctly stays frozen, matching
`escape_atom`'s own convention; only the value actually reaching the physics was wrong). **Verified
directly against the wired camera, not just gated in the abstract**: a controlled single-blip
atom-junction candidate now matches the wired camera's facing bit-for-bit (was 29 BAM off pre-fix).

**Testing against the actual walk=9 case -- not reasoning it through -- caught a second bug the
reasoning missed.** The first (junction-only) fix still left an 11 BAM residual on session 152's own
walk=9 hit. Cause: a `_families` L_AXIS continuation choosing l=1 AFTER the junction's own release is a
SECOND, independent rising edge on a camera that already went through one blip and settle -- and the
first version of `CamTrail.from_l` built that correction from a fresh L-free reference instead of
composing onto the real (already-blipped) history. Fixed: `from_l` now composes (an L press adds to
whatever a trail already carries, so pressing twice presses on the SAME continuous replay);
`overnight._atom_candidates` threads the junction's own corrected trail into its continuation instead of
the plain one from the caller. **Lesson for future memory: a single-instance fix that passes its own
gate is not the same claim as "this mechanism is fully modelled" -- re-running against the concrete case
that first surfaced the bug is what caught the second, compounding instance; a synthetic single-press
test alone would not have.**

**The walk=9 re-run's answer changed shape, and that is the correct outcome, not a regression**: "1
genuine hit, refused by `confirm_entry`" became "0 genuine, best overlap 3.85e-5 off target" -- the SAME
close-but-not-quite shape already seen at walk 7/8. The original "genuine" hit was a FALSE POSITIVE
produced by this exact modelling gap (its own plan presses L twice); once the physics is modelled
correctly, it no longer lands in the acceptance band. Full default suite: 1261 passed.

**ITEM 3 IS DONE: the widened sweep (walk 7-13, both fixes in place) found 0 deliverable plans anywhere
-- `[[search-must-rediscover-known-answer]]` is NOT satisfied by this herd at this discretization.** Six
of seven walk depths (7/8/9/10/12/13) are cleanly `genuine=0`. Walk 11 produced ONE genuine razor hit
(thrust=15, `resid=1.967e-04`) refused at `confirm_entry` -- the same "genuine but refused" shape as the
original walk=9 case, NOT YET DIAGNOSED (the diagnostic script exists, `_notes/s153_walk11_diagnostic.py`,
launched and killed before printing anything -- just re-run it next session). Every walk's own
`best_overlap` lands within ~1e-4..2e-4 of the 1.2259 clip target (`_notes/s152_rediscover_results.json`,
the complete record) -- consistently CLOSE, never exact, across the WHOLE range, which points at the
DISCRETIZATION (`alpha_stride`, `ATOM_ROTATE_OFFS`, `ATOM_FLIP_STEP`) being the limiting factor, not the
walk range itself. **NEXT: either widen those knobs (the more principled move, given the consistent
near-miss pattern) or report this sweep's own finding to Dereck and let him decide whether to chase finer
discretization on this herd or look at the OTHER 48 non-console rungs instead.**

**A real trap this cost real time to: a script that overwrites ONE hardcoded checkpoint filename every
run can hand you a stale result indistinguishable from a fresh one by content alone.** Read the
checkpoint mid-run, saw walk=9 at `genuine=1` matching session 152's OWN ORIGINAL pre-fix number exactly,
and spent real time chasing it as a possible NEW non-determinism bug in this session's own fix -- three
independent reproductions all agreed with each other (`genuine=0`) and only the file disagreed, because
its mtime was 8 hours stale (the run reading it had not yet progressed that far). **Lesson for future
memory: a checkpoint file's CONTENT matching a plausible-looking prior result is not evidence it is
CURRENT -- check its mtime against how long the run producing it has actually been alive before trusting
any of its numbers**, especially right after killing and relaunching a script that writes to a fixed
filename. Cross-reference `[[harden-harness-traps]]`.

## s154: THE REDISCOVERY GATE IS SATISFIED -- the search itself produced a genuine, CONFIRMED, DELIVERABLE plan at total 101, and the thing that had been refusing it was the AIM CAMERA (so the 7..13 sweep's "0 deliverable" was that bug's artefact, and DISCRETIZATION was the wrong suspect)

**Read this section, not the s153 one, for what the rediscovery sweep actually measured.**

**THE RESULT, first.** Re-running walk=11 / thrust=15 off `log[:71]` with the aim-camera fix in -- same
seed, same fan (319167 candidates, bit-identical), only the camera changed -- turns s153's
"genuine=1, refused at `confirm_entry`" into **`genuine=1, ACCEPTED, total=101`**:
`plan=[3, 104,252,1,1, 104,252,0,1, 0,103,0,1, 152,0,0,1, 112,2,0,4]`, `aim=[88,179]`, `facing=40727`,
`cell=2545`, `csangle=34395`, `resid=1.966531e-04`, `overlap=3.221763`, `agree` deliverable/genuine/
handover_ok/cut_ok with `worst_ulp=0` at `cut_i=101`, `accept() ok=True stage=deliverable`
(`verdict=False` only because 101 cannot BEAT 101). `_notes/s154_walk11_refixed.{py,json,log}`.
**It is NOT the console's own plan** -- its conversion fires at n0=3 and holds ONE stick for four frames
where the human's fires at n0=0 and holds three -- so the pipeline found its OWN answer at the console's
own cost. **And it is the SAME candidate s153 called "genuine but refused", with the same razor draw
(cell 2545) and a bit-identical `resid`: only the recorded aim BYTE changed** (`[86,182]` -> `[88,179]`).
So that hit was a TRUE positive the broken byte->facing map was hiding -- the exact opposite of the walk=9
case, which really was a false positive. Run bookkeeping: `cameras=4`, `cells=56` swept (the union, vs 43
at the single L-free camera -- a 30% cost, score 341.9 s -> 441.5 s), `unaimable=4168443`,
`evaluations=13704909`, `best_overlap=1.22592287` (2.3e-5 off target), `best_resid_in_contact=1.85e-05`,
`bracketed=True`.

**THE ARITHMETIC FIRST, because it reframes the whole sweep.** The rediscovery seed is `log[:71]` and the
console's own A-press is row `a_i = 82`, so the console's own answer off that seed is its own rows
71..81 -- **`walk = 82 - 71 = 11`** -- and `total_frames(71, 11, 15) = 101` = the locked cut frame
exactly. **The one depth of the seven that produced a genuine razor hit is the one where a known-good
answer is known to exist.** s152/s153 swept 7..13 without connecting those two facts, which is why walk
11's refusal read as one more anomaly instead of as the gate's own answer being rejected.

**ROOT CAUSE (measured, three independent ways): `configurations()` prices every candidate at the L-FREE
camera, and every plan that presses L latches its roll facing against a different one.** This is the
THIRD camera case, and it is exactly the one s153 explicitly scoped OUT ("the AIM/entry-camera
`trail[walk]` lookup ... a coarse pre-filter, not a source of false acceptances"). That reasoning was
wrong: it is a source of false PREDICTIONS. The blip FREEZES the yaw chase where it stands while the
L-free chase keeps climbing, so:
  * the console's own conversion (L on its first walk frame) latches against **34325**, the L-free trail
    says **34406** -- **81 BAM, five sine cells**; its aim byte `[82,186]` reaches facing 40841 at the
    real camera and 40922 at the L-free one;
  * s153's own refused walk=11 hit (L pressed at n0=3, 8 frames before its aim frame) is **11 BAM** out
    -- still crossing a cell (2545 vs 2544), so a different razor draw entirely.
**THOSE ARE s152's THREE DISCRETE FACING BUCKETS**: -81/-31/-11 is ONE curve -- the freeze point sampled
at different press-to-aim offsets -- not three phenomena. s153 attributed the buckets to the stepping
csangle it fixed; the stepping fix was right and necessary (`walk_matches` now passes), but the buckets
were the AIM lookup all along.
**An off-by-one rode along**: the facing latches against `entry_camera.aim_frame`'s `trail[walk + 1]`,
never `trail[walk]` -- the A-press is delivered on index `walk` and its target is computed when the input
is ACTED, one frame later. Re-measured 18/18 at walk 2..5 off this seed where the chase is still climbing
(17 BAM at walk 2). Inert wherever the camera has settled, which is why it survived unnoticed.

**THE ACCEPTANCE STACK IS SOUND -- it was only ever the enumeration.** Fed the human's own 11 rows off
herd=71 (read back with the new `overnight.plan_from_rows`, never authored), `confirm_entry` passes every
flag, the razor returns `resid = +6.242939e-05` (**the LOCKED fixture's own value**) with overlap
`+1.225899`, `cross_engine.agree` is `deliverable=True` / `worst_ulp=0` / `cut_i=101`, and `accept()` is
`ok=True, stage=deliverable, total=101` (`verdict=False` only because 101 cannot beat 101). So handing the
pipeline the known answer from the rediscovery seed gets it ACCEPTED, bit-exact -- that half of
`[[search-must-rediscover-known-answer]]` is now demonstrated, not assumed.
**GOTCHA that cost the first pass**: score her at the SEED's Tetra and the very same plan reads
`genuine=False, overlap=-15.34`. She moves **36.7 u** across the human's own conversion, and `score` uses
each candidate's OWN walk-endpoint Tetra (s150's `with_tetra`), never the seed's. A probe that reuses
`seed['tetra']` for a plan that plows her is measuring a Tetra the roll never sees.

**THE FIX COSTS NOTHING, because a CELL IS ONE RAZOR DRAW AT ANY CAMERA** -- every term a facing reaches
goes through `jmaTable[angle >> 4]`, so two facings in one cell bake a bit-identical schedule and a
bit-identical 26 u entry step (already gated 0-ULP, `test_the_aim_alphabet_resolves_to_the_sine_table_cell`).
So `score(cam=...)` sweeps per CELL over exactly the old lean groups and batches, and only the
`(facing, aim)` pair it RECORDS is resolved per candidate at that candidate's own camera. Same cost, same
batching -- what the camera changes is the BYTE, not the draw. New: `entry_camera.aim_camera`,
`overnight.l_press_frames` / `aim_camera` / `aim_cell_map` / `plan_from_rows`; `unaimable`/`cameras`/`cells`
join the stats and every row carries the `csangle` it was priced at. `verify_console` now checks the PAIR
(the byte REACHES its own facing), not just alphabet membership -- membership alone passed while the pair
sat five cells apart. Commit `736db77`, full default suite **1267 passed** (was 1261), 69 s.

**A SECOND, INDEPENDENT CONTAINMENT GAP that no camera fix touches**: the human's own 11 frames are the
4-frame atom recipe EXACTLY (L+flip, flip, rotate, slam) followed by a **THREE-segment** continuation
((241,59) x3, (208,110) x2, (169,192) x2), and `_families` enumerates exactly ONE held stick. **So the
console's own input is not a member of the enumerated set at walk=11 whatever the camera does** -- the
search must find a DIFFERENT plan of the same length, a strictly harder ask than the gate's name suggests.
`_steered_tail` is the axis that would contain it, and it was OFF in the sweep AND builds its prefixes
from `_families`/PRE only, never from the atom junction. Concrete recipe for closing it: an atom junction,
a uniform continuation, then `tail_frames=(4,)` steering the last four frames -- that shape contains the
human's own (prefix = atom + 3x(241,59), steered = 208,110 / 208,110 / 169,192 / 169,192). Gated now
(`test_plan_from_rows_round_trips_the_console_conversion`) so the shape claim cannot drift.

**KNOWN, SCOPED, NOT SILENT**: the fan's candidate key is the physical endpoint
`(pos, m351C, speedF, tetra)`, so two plans reaching a bit-identical endpoint with DIFFERENT L-press
frames collapse to one dict entry -- and they stopped being interchangeable the moment the aim camera
became per-plan. It can only LOSE a draw, never invent one. One-line fix if it ever matters: append the
plan's own `aim_camera` to `collect`'s key, at the cost of a larger candidate set; unmeasured, unshipped.

**LESSON, general**: a stage that consumes a per-item constant where the truth is per-candidate is
invisible to every gate written at the item level. The blip fix (s153) and this one are the same bug in
two places -- s153 fixed the consumer that steps the physics and left the consumer that enumerates the
aim, because the second one was reasoned about ("coarse pre-filter") instead of measured. When a fix
lands on one consumer of a shared quantity, grep every OTHER consumer and measure each one.

## s155: THE RE-RUN SWEEP IS COMPLETE AND BARREN FOR A NAMED REASON -- EVERY NEAR-RAZOR ROW IS REFUSED BY THE BARRIER, AND `resid` CANNOT SEE IT. Shallow walks are physically OUT OF REACH; the s154 enumeration gap is CLOSED.

**THE VERDICT, first.** The re-run sweep the s154 handoff owed is DONE: 21 items, walk 5..12 x every
admissible thrust -- exactly ``walk + thrust <= 25``, which is what BEATS 101 off herd=71
(``total = 75 + walk + thrust``) -- all run at the corrected aim camera, none bound-retired.
**0 genuine, 0 deliverable. The banked 101 STANDS.** 4014 s over 10 workers. Closest approach:
**|resid| = 3.11e-06 u at walk 12 / thrust 13, overlap 1.225884 (1.6e-05 off the 1.2259 clip target)**.
14 of the 15 in-contact items BRACKET the razor. So this is now evidence about the ITEMS -- the gate was
cleared in s154 -- and the old s152/s153 numbers stay void.

**WHY THEY MISS -- THE FINDING (`_notes/s155_why_not_genuine.py`).** `_shovec`'s acceptance is THREE
tests, ``(not blocked) and in_front(old) and crossed(new)``, and it reports only the AND -- so
``genuine = 0`` beside a 3e-6 residual reads as a mystery. Re-evaluating the recorded near-razor rows at
their own configuration, **38/38 across walks 7..10 are refused at the FIRST test: the swept lunge path
HITS THE WALL (`wall_hit`)**, and 22 of them additionally never cross a seam plane at all, with
**overlap -2.7..-5.7** (no contact at the cut -> no push -> the lunge falls short). **THE CONTROL is what
makes this a finding and not a bug report: s154's own accepted 101 re-evaluates GENUINE through the same
probe** -- `blocked=False`, `in_front=True`, `crossed=True`, both seam-plane values -0.845, `resid`
bit-identical. **So `resid` is BLIND to what refuses them**: it is the cut RAY's signed offset from the
seam vertex, and a ray can aim through a wall -- walk 9 / thrust 14 reached **2.09e-05, closer to the
razor than the console's own genuine 6.24e-05**, with no clip. `[[banded-proxy-needs-its-newton]]`
generalised: the proxy does not merely mis-rank, it cannot see the binding constraint. **Since the baked
roll schedule is entry-position-INDEPENDENT, the unblocked entry set is a computable geometric region per
(facing, lean, thrust)** -- i.e. clearing the barrier can be a search CONSTRAINT instead of a post-hoc
verdict. That is the next lever, and it is not "more density".
**Recorded from now on rather than re-derived**: every row `score` singles out carries ``pred`` (the two
seam-plane values) and ``why`` (`blocked`/`line_hit`/`wall_hit`/`in_front`/`crossed`), gated by a positive
control on the delivered clip (`test_a_scored_row_carries_the_acceptances_own_three_terms`). LIMIT: ``why``
is computed for SINGLED-OUT rows only (genuine hits, the two bests, the capped near set), never per
evaluation -- it describes the near-razor population, not the whole in-contact one. Rows banked by this
sweep predate the field; the probe reads them.

**THE ENUMERATION GAP IS CLOSED (s154's own item 1).** `_steered_tail`'s headline is "PER-FRAME STEERING
AFTER THE CONVERSION" and it built its prefixes from `_families`/PRE ONLY -- so it could steer only after
a UNIFORM walk, never after the conversion a real backslide actually reaches the cap through. Handed
``flips`` it now builds ATOM-JUNCTION prefixes too (`fan_exact` passes its own), including
``remaining == 0`` (steer straight off the slam), so the shape the console's own 11 frames live in --
atom + a uniform continuation + `tail_frames=(4,)` -- is enumerated for the first time.
**Two more instances of s154's own lesson rode along, both fixed in the same place:**
  * **the per-prefix CAMERA** (`_trail_for`): a prefix that pressed L has already fired the followCamera
    blip, and `_fan` only ever corrected the edges inside its OWN schedule -- so every steered frame after
    an atom junction AND every one after a `_families` L_AXIS hold read the L-FREE trail. The trail is now
    derived from the prefix PLAN's own edges (`l_press_frames`), which cannot disagree with the schedule
    that built it;
  * **the pool RANK**: prefixes were ranked by distance from Link to the SEED's Tetra while she moves
    36.7 u across a conversion that plows her -- now the prefix's own tracked Tetra, the same
    ``with_tetra`` rule `score` follows.
**CONTAINMENT IS MEASURED, not reasoned, on BOTH filters** (`_notes/s155_atcap_through_the_console_
conversion.py`): the shape delivers the console's own rows bit-for-bit
(`test_the_steered_tail_shape_contains_the_console_conversion`), and its `at_cap` PREFIX filter admits the
human's own prefix at every ``k <= 5`` -- because her conversion DIPS below the cap on the slam and the two
frames after it (**nspeed 13 / 15 / 18 at delivered frames 3, 4, 5**) and holds **17.0 / nspeed 26 from
frame 6 on**, so the dip sits inside the prefix where nothing filters it. A shape containing a plan and a
filter admitting it are two claims; this is the second one.
**COST CLASS CHANGED, and it is documented rather than defaulted**: off a backslide the ordinary families
reach the cap almost never (the old pool was ~empty, so `PREFIX_CAP` never bound), but EVERY atom junction
converts -- the pool is now ``flips x 8 knob combos x families x |alpha|`` and the first steered depth costs
``|pfx| x |alpha|`` clones (20000 x 11405 = 228 M -- minutes). Size `prefix_cap`/`alpha` per run;
``prefix_cap_hit`` says when it bound. A 10-minute probe timed out learning exactly this.

**THE ITEMS SPLIT IN TWO, and only one half is about the search** (`_notes/s155_sweep_{item,launch}.py`,
rollup `_notes/s155_rollup.py`, per-item JSON+log in `_notes/s155_sweep/`; items ordered by total
ascending, one process each). **Walk 5 and 6 -- six items, totals 93-96, never swept before -- reach
`n_contact = 0`: she is 12.7-15.2 u OUT OF REACH at every thrust.** Those totals are barren for a PHYSICAL
reason and no enumeration widening touches them; do not re-run them. Walk 7..12 are in contact and get
deeper with depth (**170** scorings at walk 7, **380,860** at walk 12), and their near-razor rows are the
barrier-refused population above.
**READ A BARREN ITEM BY ITS CONTACT COLUMNS.** `genuine=0` alone cannot tell an item that was 13 u from
touching her from one that bracketed the razor and missed by 5e-4; `n_contact` / `band_draws` /
`best_overlap` / `resid_neg`+`resid_pos` are what separate them, and every one of them is recorded per item.
**`best_overlap` at the clip target is NOT sufficient**: walk 8 t14/t15 sit 3e-6 and 2e-6 off it with 0
genuine -- the razor's own flag is the verdict, never the hypot (`BAND_IS_NOT_PREFILTERABLE`).
**PERF NOTE for the next run**: 10 workers x 1 OpenMP thread is ~1.75x one 12-thread process on the SCORE
stage (not the fan's 3.8x -- `sweep_par` scales better with threads than the fan does), and a pinned
straggler leaves 11 cores idle at the tail of a run, so `s155_sweep_launch.py` now gives each spawn
``cpu // min(workers, items_left)`` threads.

## s156: THE BARREN SWEEP IS TWO MEASURED NUMBERS -- 97% OF ITS EVALUATIONS WERE OUT OF CONTACT, AND THE IN-CONTACT REST SIT AT CONFIGURATIONS 40-112x POORER IN DUST. The deciding axis is the roll FACING; herd depth is EXONERATED. Every earlier entry probe sampled BELOW the entry's own f32 quantum.

**THE FORK s155 ASKED FOR IS SETTLED, AND THE ANSWER IS NEITHER.** Not a thin sliver missed by microns,
not a region the walk never reaches. The reason neither reading was available: **`ShoveCtx._run` starts
from ``f32(link_x0), f32(link_z0)``, so the reachable entries form an f32 LATTICE of pitch
1.220703125e-04 u** -- and `configuration_band` sweeps +-0.006 u in 1201 samples (1e-05 u apart) while
`locus_scan` sweeps +-0.02 u in 2001 (2e-05 u apart). **~12 consecutive "samples" are the SAME f32 entry**,
so both probes' negatives were one lattice rung of evidence, never a barren configuration. NEVER sample the
entry below one ULP again; `entry_dust.entry_ulp` / `lattice_step` (bit-stepped, both signs) exist for it.

**NUMBER ONE -- 97.0% of the sweep's evaluations could never have clipped, and the sweep already recorded
it.** Walk 12: ``n_contact = 380,860`` of ``evaluations = 12,807,108`` = **2.97% in contact**. Outside
contact the push is zero, `old` is the same wall-braced point, the bare roll-stab lands 0.33 u short and the
razor's residual is a DEAD CONSTANT (gated: `test_the_cut_frame_push_is_what_moves_the_razor_and_it_is_zero_
at_links_endpoint`). Verified directly at w12_t13's own best-overlap endpoint -- cells 2540..2575 read
overlap **-2.7 to -10.9 u**. So `n_contact` was never a diagnostic column; it is the size of the search.

**NUMBER TWO -- the in-contact 3% are 40-112x poorer in genuine dust than the configuration that
delivered.** Measured per REACHABLE f32 entry over a 300 u locus march: s154's accepted 101 gives **228
genuine of 5265** (1 in 23); every barren in-contact near-razor row gives **0 or 1 of 891..2511** (w07_t13
0/891, w07_t15 0/1701, w08_t13 0/1620, w08_t14 0/1053, w08_t15 0/2511, w07_t14 1/1215). The two numbers
together ARE the arithmetic of "0 genuine out of 12.8 M": ~3% of nominal at ~1/50th the hit density.

**THE DECIDING AXIS IS THE ROLL FACING (the aim CELL).** At FIXED (lean, thrust, Tetra), adjacent 16-BAM
cells run **1 in 6 -> 0 of ~4700**: cell 2551 **719/4617**, 2545 **228/5265**, 2552 **86/4455**, 2548
**0/4941**, 2544 **0/4779** -- with ``grad`` 0.41-0.76 for all of them, so it is not a dead or a steep razor
doing it. Facings 40817 and 40823 (both cell 2551) return BIT-IDENTICAL marches, so one probe prices a cell.

**HERD DEPTH IS EXONERATED, and so is grad-at-the-seed.** Configuration held at the accepted row's own,
Tetra slid along the herd line: density flat **3.9e-2..5.7e-2 wherever contact exists**, 45 u DEEPER
included, and ``grad = 0`` ("no leverage") shallower where she is not there to be pushed. The live cell SET
barely moves over that 45 u (\{2545, 2551\} at +0 and +20 u, \{2551\} at +45 u). **At +59 u grad is 51.9 and
density is still 3.9e-2**, which kills the session's own first hypothesis (that
``grad = |d resid / d entry|`` predicts barrenness -- genuine population 0.104-0.313 vs barren 0.006-52.4).
The tell was CONTACT, not steepness: every barren row whose grad landed inside the genuine range had
NEGATIVE overlap.

**SO s155's "38/38 wall_hit" IS THE SHAPE OF A NEAR MISS, NOT A SECOND CONSTRAINT.** Under the rigid entry
translation the search actually varies, the segment's LINE test stays clear and the ENDPOINT's proximity to
the wall chord is what flips -- one f32 ULP either side of the accepted entry is ``wall_hit``. And the
genuine set is dust ON the razor, not a band around ``resid = 0``: at the accepted row exactly ONE of eleven
lattice entries is genuine, at ``resid = +1.9665e-04``, with ``resid = 0`` itself refused. Ranking on
\|resid\| aims at a value that is not the target.

**TRACKED TOOL: `harness/tetrapush/entry_dust.py`** -- `dust_density` (march the residual zero as
`locus_scan` does, but test the bit-stepped lattice neighbourhood at each station), `cell_dust(walk=)` (per
aim cell, each cell seeded from its OWN `roll_entry` 26 u out along its own facing), `live_cells`,
`needed_multiplier` (returns None for a cell with no dust, omits an unsampled one -- an unbounded
multiplier is not a number). **~0.5 s per configuration, no fan.** 9 gates in `tests/test_entry_dust.py`;
suite 1280 passed, 73.8 s, exit 0.
**HONEST LIMITS, carried in the tool**: ``genuine`` counts sweep-level PREDICTIONS (`overnight.accept` --
a real A-press plus the walled `cross_engine.agree` -- is what makes one a plan, and ~1 aim in 8 brakes on
the entry frame); ``density`` is per lattice point tested NEAR THE LOCUS; the march is finite, so
``genuine == 0`` means "none in this arc" and ``tested`` belongs in every quote; the march needs a seed WITH
LEVERAGE (priced off one walk endpoint, 40 of 42 cells returned ``no leverage`` -- a true statement about
the ENDPOINT, saying nothing about the cells, so read ``tested`` before ``density``); and counts move with
the seed while the live/dead verdict does not (2551 read 719/4617 and 763/4617 from two seeds).

**NEXT (s157): prune the 97%, then AIM instead of drawing.** (1) Contact is predictable BEFORE the roll --
the cut step's position is ``entry + sum(dx, dz)``, entry-position-independent and gated, so
``|cut_pos - tetra| <= CO_R_SUM + margin`` is arithmetic on numbers the fan already holds; wire it as a
candidate x cell filter (score stage ~30x smaller, ~2000 s -> ~70 s per item) and gate it by CONTAINMENT of
the unpruned sweep's in-contact rows. (2) For a live cell the target is a computable 1-D curve and
`dust_density` already returns genuine entries ON it (``dust[i]['entry']``, ``walkable`` beside it), so
measure the gap first: how far is the nearest fan endpoint from the endpoint a recorded dust point implies
(``dust_entry - 26 * (sin, cos)(facing)``)? That distance decides densifier-vs-new-primitive.


## s157: THE PREFILTER CANNOT EXIST -- THE WALL BRACE PINS THE WHOLE CUT FRAME, SO OUT OF CONTACT THE ENTRY DOES NOTHING AND THE RAZOR'S ONE FREE VARIABLE IS WHERE TETRA STANDS AT THE CUT. New tool prices the aim to 0.046 u against the console's own row; the barren item is 1.006 u away and the delivered one was 7.7e-04 u.

**s156's RECIPE IS FALSE IN BOTH HALVES, MEASURED BEFORE BUILDING ON IT.** (1) ``entry + sum(dx, dz)``
is not the roll -- the wall corrects it, so that path lands **255 u** past where Link ends and a contact
test on it keeps **0 of 2304** entries genuinely in contact. (2) Contact is not the prunable thing: on a
real item's rows **99.3% plow her 23-68 u** while only **2.2%** end with any different cut-frame state,
because the brace eats Link's half of the ejection and `CrrPos` returns him to the same point. The saving
is real -- 97.8% of a fan's rows ARE one constant -- but no geometric predicate reaches it: the necessary
condition (she is anywhere near the swept no-Tetra path, inflated by her plow) keeps 94-100%, and the
tight point test keeps 61.5% AND LEAKS 1070 of 3883 differing rows.

**THE ENTRY IS INERT OUT OF CONTACT, BIT-EXACTLY.** Over the whole reachable entry box
(`entry_search.reach_radius`, 94 u) an untouched roll returns **ONE distinct ``old``, Co centre, ``new``
and residual for 169 entries**. It is a property of the BOX, not of the arithmetic: the same 169 entries
at radius 400 u give 129/129/125/129. So s156's "outside contact the residual is a dead constant" has its
mechanism, and everything the entry buys a search it buys THROUGH her plow (it changes WHEN the roll
reaches her, hence how many frames of plow she gets).

**SO THE RAZOR IS A MAP OVER ONE 2-D VARIABLE, AND `ShoveCtx` ALREADY TAKES IT.** ``placed_step`` puts
her anywhere in the schedule, so `cut_contact.cut_slice` places her ON the contact step (``cut_step - 1``)
and reads the razor off the native sim -- **~66 us a point, no fan, entry-invariant** (gated bit-exact
from two entries 50 u apart). At the position the console's herd left her in it reproduces that row's
push to 1.5e-03 and its residual to 1e-02.

**THE AIM: `target_ring`.** Scan the contact band, then bisect the residual's zeros per bearing off the
braced Co centre -- scanning FIRST because deep in the overlap the residual STEPS and a blind bisection
reports the jump as a target (dist 34.93 at ``resid`` +20.5, measured). On the bearing the console used
the ring sits at **76.73543 u** against the **76.78111 u** she actually stood at: **aim error 0.046 u**.
It is an AIM, never a plan -- the slice pins ``old``, and the accepted 101's own ``old`` is 0.0127 u off
the brace, worth ~1e-02 of residual against a razor 1e-04 wide. Ring to place her, entry lattice
(`entry_dust`) to close the last 1e-04.

**THE BARREN ITEM, PRICED IN HER COORDINATE.** ``gap = |resid| / |d resid / d dist|``, both off the sim,
over **261k rows** of walk 8 / thrust 13 (all 55 cells, 6000 candidates): closest row **1.006 u**, median
in-contact row 414 u, against the delivered 101's **7.7e-04 u**. Nothing that item can build gets within
a unit of where she has to be. The far field is a local Newton step and not a distance -- quote the small
ones. And her reachable set is not free either: the rows that reach contact are the ones plowed INTO the
wall, which pins her cut-frame ``z`` at **-940.255615**, while the delivered row stopped **0.36 u short**
of that pin.

**TRACKED:** `harness/tetrapush/cut_contact.py`, `tests/test_cut_contact.py` (9 gates, slowest 0.20 s),
KB page `knowledge/model/braced-cut-frame.md` (+ hub line). Suite 1289 passed, 83 s. A real item's
candidate set is banked for probes (`_notes/s157_fan_item.py` -> `_notes/s157_cands_w08_t13.pkl`, 67 s to
rebuild).

**NEXT (s158): ask whether a herd can reach the ring at all, per cell, before aiming at it.** Her
cut-frame positions spread 25.5 x 5.2 u but the in-contact ones are pinned on the wall; the question is
whether that reachable set CROSSES the ring. If it does not, no densifier fixes it and the last herd
cycle has to change. Then make the walk's objective "land her cut-frame position on the ring", and rank
items by ``gap`` -- the first quantity in this work that says HOW FAR a herd is from a clip.

## s158: THE RAZOR IS A POSITIVE RESIDUAL INTERVAL AND `resid = 0` IS NOT IN IT -- so every zero-seeking tool in this work (zero_the_resid, locus_scan, configuration_band, entry_dust, target_ring, s157's gap) aims at the ONE value the razor refuses. Her plane is EXHAUSTED at the barren configurations; the live axis is the ENTRY.

**s157's REACHABILITY QUESTION WAS ALREADY ANSWERED ON DISK, AND IT KILLS THE FORK.** The s155 per-item
JSONs carry ``bracketed``/``best_resid_in_contact``: **14 of 15 in-contact items BRACKET ``resid = 0`` and
the closest reaches 3.11e-06 -- nearer zero than the console's own genuine 6.24e-05.** So the ring is
reached abundantly, the "no densifier fixes it, change the last herd cycle" branch is refuted, and
re-running `s155_why_not_genuine.py` re-confirms all 15 near-razor rows refuse at ``wall_hit``.

**THE FINDING, MEASURED AT FULL FIDELITY ON BOTH ROWS KNOWN TO CLIP.** Sweep HER WALK-END position over
her own plane at ``placed_step = 0`` (her own plow, the row's own ``old``) and read ``genuine`` off the sim:
the genuine placements occupy ONE narrow, strictly POSITIVE residual interval that EXCLUDES ZERO --
console's own clip **[+5.796e-05, +9.918e-05]** (7 values, 301/301, overlap +1.2259), s154's accepted 101
**[+1.628e-04, +1.967e-04]** (4 values, 510/510, overlap +3.2218). Each delivered row sits inside its own
interval and both reproduce their recorded residual **0-ULP**. Inside a band ``resid`` is **SUFFICIENT** --
no row lands in it and fails, in every one of 20+ configurations. So a row at ``resid = 0`` is not NEAR the
razor, it is past it: that is the mechanism under s155's "every near-razor row is ``wall_hit``" and s156's
"one f32 ULP either side flips it" (a ULP of Tetra IS a residual quantum; the band is a few quanta wide).

**PER CONFIGURATION, NOT A SEAM CONSTANT.** Cell 2545 sits ~3x further from zero than cell 2552 and they do
not overlap; cell 2551 lands at [+1.66e-05, +4.42e-05] at overlap +1.512. Stable against lean +-8 and entry
~0.05 u. A **+-0.02 u scan of her plane (~0.5 s)** returns the same interval as one 2.5x wider / 2x finer.
Her position is QUANTIZED into the residual: 160801 placements -> only ~1900-4700 distinct residual values
(~86 placements each), genuine taking 4 and 7 -- reachable RUNGS, not a continuum.

**HER PLANE IS EXHAUSTED AT THE BARREN CONFIGURATIONS.** A +-0.6 u scan (641k placements) at all 15 barren
items' own best-row configurations returns **0 genuine**; widened to **+-2 u (7,112,889 placements)** on two,
still 0 -- one being w10_t15 on **the console's own cell 2552 / thrust 15**, where a band demonstrably exists
at the console's own entry. Both clipping configurations find dust under the IDENTICAL scan, so sensitivity
is controlled. Those rows are disqualified by their ENTRY/configuration; the deciding variable is upstream.

**THE s157 TOOL IS CORRECTED, NOT DELETED.** `cut_slice` pins ``old`` ~1e-02 out = ~300 band-widths, so its
``genuine`` and `target_ring`'s ``lattice_genuine``/``live`` are FALSE NEGATIVES near the razor (0 of 289 at
every bearing incl. the console's own; False on the delivered placement itself). Docstrings say so + a gate.
And s157's ``gap`` headline "1.006 u" is the 6000-candidate SAMPLE's minimum -- that item's own banked
`best_resid_row` prices at **0.0301 u** through the identical formula (33x). GOTCHA that cost a control:
``console_candidate()['m351C']`` is ALREADY the roll lean; `lean_at_roll` on it again gives 65032 and a row
8.8e-02 off the fixture.

**TRACKED:** `harness/tetrapush/razor_band.py` (`genuine_band`, `in_band`, `band_distance`,
`zero_is_outside`), `tests/test_razor_band.py` (8 gates, slowest 0.93 s), KB
`knowledge/model/genuine-residual-band.md` + history
`knowledge/history/the-ring-and-the-gap-aimed-at-the-residual-zero.md`. Suite 1297 passed, 75 s.

**THE FOLLOW-UP (same session, after Dereck asked whether "the entry is the live axis" had been
MEASURED -- it had not, and measuring it moved it).** New `razor_band.admits`: since ``genuine`` is exactly
``resid`` inside the band, ONE march along the residual's gradient (401 rungs over +-5e-04, ~806
placements, **~16 ms**) answers "does this configuration clip for ANY position of hers". Fires on both
controls; agrees with the full plane scan at **11 of 12** entries around the console's own (the miss is at
the admitting region's EDGE: 33 genuine of 160801 vs 301 at the centre). For scale, s155 spent **4014 s over
ten workers** to conclude "0 genuine" for 21 items.

**THE BARREN ITEM IS DEAD ON EVERY AXIS, NOT SHORT OF SEARCH.** w10_t15 shares the console's **cell 2552 and
thrust 15**. At its own entry: **0 of 16384 leans** (full 16-bit range, 4 BAM apart); **0 of 6561 entries**
over a +-0.8 u PLANE and 0 of 501 over +-5 u along x; **0 of 7,112,889 placements** of hers over +-2 u. The
console's configuration lights up under every one of those same sweeps. So "the entry is the live axis" is
FALSE as stated -- nothing that item can vary admits.

**THE ADMITTING SET'S SHAPE (console's configuration).** LEAN window **~181 BAM wide**, its own lean inside
it (two windows within +-400: -118..+62 and +75..+78) -- so **a lean sweep coarser than ~180 BAM reports
FALSE zeros** (a 128-apart sweep finds 1 bucket of 512 at a config that clips; the same trap one axis over
from [[probe-below-the-quantum]]). The admitting ENTRY set is **diffuse, not a blob**: 571 of 6561 (8.7%)
over the whole +-0.8 u plane, while one line through it at dz=0 admits only -0.08..+0.06 of +-5 u swept --
**never read one line through the entry plane as the entry set.** GOTCHA: `admits` walks the gradient out to
0.06 u so it is NOT bounded by `genuine_band`'s box and can report genuine where a +-0.02 u scan has none
(the screen being right, not a disagreement).

**TRACKED (follow-up):** `razor_band.admits`, 4 more gates (12 total in `tests/test_razor_band.py`), KB page
`knowledge/model/admitting-configurations.md` + hub line. Suite **1301 passed**, 82 s.

**NEXT (s159): MAP THE ADMITTING SET OVER CONFIGURATION SPACE WITH THE SCREEN, THEN PLAN INTO IT.** The
pipeline has always been "enumerate plans, evaluate genuine"; `admits` inverts it at 16 ms a configuration.
(1) Screen cell x thrust x lean x entry -- 45 cells x 3 thrusts x a lean grid **no coarser than ~90 BAM** x
a small entry patch -- and bank the admitting set; that is the first map of WHERE a clip is possible.
(2) The planner's objective becomes "reach an admitting configuration", a target with coordinates, which the
herd/walk search has never had; `band_distance` ranks how close a row got. (3) Re-run items only after that:
a barren item now splits into "admits, but the plans missed it" (a search problem) vs "admits nothing" (no
enumeration widening touches it), and only the first is worth a fan.

## s159: THE ADMITTING SET IS MAPPED AND **THE ENTRY IS THE AXIS THAT DECIDES IT, AT COURTYARD SCALE** -- the lean has cells (129, enumerated), `resid = 0` is a CURVE that a one-station screen misses 73% of, thrust 13 admits at 0 of 45 cells, and 0 of 15 barren items admit at their own entry

**THE HANDOFF'S MAP GOT RESHAPED BY THREE MEASUREMENTS TAKEN BEFORE RUNNING IT.** New tracked module
`harness/tetrapush/admit_map.py`, 14 gates in `tests/test_admit_map.py`.

**1. THE LEAN HAS CELLS, EXACTLY AS THE AIM DOES.** Fingerprint the BAKED SCHEDULE across the 1040
reachable leans (`entry_lean.census`, contiguous -775..+266, only -1/+1 absent) and you get **129 distinct
schedules** in 129 contiguous runs 1-32 BAM wide, with the partition **bit-identical** at cells
2525/2545/2552/2554/2581 and thrusts 13/14/15. So configuration space is 45 x 3 x 129 = **17415, an
ENUMERATION** -- s158's "a lean sweep coarser than ~180 BAM reports FALSE zeros" stops applying because
nothing is sampled. `lean_runs` / `lean_cell` / `schedule_fingerprint`. **The lean is an OUTPUT of a plan
(the walk's turn history), never an input** -- a planner cannot ask for one.

**2. ``resid = 0`` IS A CURVE AND EVERY VERDICT IN THIS WORK READ ONE POINT OF IT.** It runs a ~160 u
contact region. Walk it with a ladder per station: console **51 of 188 stations admit (27%)** over 116 u,
s154 **98 of 123 (80%)**. So `razor_band.admits`, and every s158 negative, **misses an admitting
configuration ~3 times in 4**. Three traps, all gated: (a) the corrector CANNOT use an absolute tolerance
-- resid is quantized ~4e-06, so a 1e-08 target rejects every station after the seed and read a 116 u
curve as **1 u**; `CORRECT_TOL = LADDER_RESID/5`. (b) OUT OF CONTACT ``|grad|`` is EXACTLY 0.0 (5 u off her
row), so the locate can never be a Newton from far -- it is a ray fan out of the braced Co centre.
(c) a ray's SIGN CHANGE IS NOT ALWAYS A ZERO (one bisected to |resid| = 68.4 against slope 24/u, the
`cut_contact.zero_bearing` trap), so `her_seeds` keeps only brackets a Newton brings onto the curve.

**3. THE ENTRY IS THE SEPARATING AXIS; THE LEAN IS NOT.** 2x2 cross at cell 2552 / thrust 15, her seed
LOCATED per configuration: barren w10_t15's own lean **ADMITS at the console's entry**; the console's own
lean **does NOT admit at the barren entry**; the two entries are **106 u apart**. s158 swept the entry
+-0.8 u and +-5 u with her seed PINNED = 1-5% of that distance at ~8x the false-negative rate (relocating
her per entry takes a +-0.8 u plane from **8.7% to 69.6%**). **s158's "the barren item is dead on every
axis" is MIGRATED to `knowledge/history/the-barren-item-dead-on-every-axis.md`** -- it is dead NEAR ITS OWN
ENTRY, and its disqualification is a WALK problem, not a dead end.

**THE MAP (tabulated entry, 45 cells x 3 thrusts x 8 lean classes = 1080 screens, 74 admit 6.9%, 1465 s):**
**thrust 13 admits at 0 of 45 cells** -- independently reproducing s144's console-derived "thrust 13
bisects 2390 razor roots and converts none", from a different instrument. Thrust 14: 6 of 45; thrust 15:
12 of 45. Five pairs admit at EVERY sampled lean: **(2551,15) (2552,14) (2552,15) (2553,15) (2561,15)** --
the console's own among them, and 2561 is s92's flagged cell. 13 more partial, so the lean narrows a
window without opening one.

**THE 15 BARREN ITEMS RE-READ (both controls fire first at the same settings):** **0 of 15 admit at their
own entry**; **1 (w09_t15, cell 2561) admits 48.0 u away**; 14 admit nowhere inside 48 u (ring probes at
arc 12 u, so those 14 are weaker negatives than the items' own full-arc zeros). **So the sweep was never a
density problem -- every item was rolling from a place where no position of hers can clip**, which is why
4014 s over ten workers returned nothing and why widening the enumeration there could not have helped.

**TOOL SHAPE.** `screen(facing, lean, thrust, entry=, first_only=)` -> dict with `admits`, `stations`,
`admitting`, `arc_neg/arc_pos`, `components`, `reason` in {'', 'no_curve', 'no_band'}, `bearings` -- a
zero ALWAYS quotes its window. `entry_map` = the admitting entry region over a box DERIVED from the two
delivered entries. `nearest_admitting_entry` = how far the WALK must move the entry, in u (the ranking key
a planner can steer, unlike `band_distance`'s residual units). CLI `gate` / `one` / `leans` / `map` /
`entrymap`; **`map` and `entrymap` REFUSE to run unless the rediscovery gate passes**. Costs: admitting
screen ~0.05 s with `first_only`, dead screen ~0.7-1.0 s (~150 stations x 241 rungs; the rung step 2.5e-06
must stay under the residual's own ~6e-06 quantum and cannot be coarsened).

**NEXT (s160): PLAN INTO THE ADMITTING ENTRY REGION.** The objective now has coordinates. (1) Bank the
entry map over the (cell, thrust) pairs that admit -- start with the five that admit at every lean.
(2) Point the walk/herd search at "put the roll entry inside the admitting region" and rank by
`nearest_admitting_entry`. (3) The 14 items that admit nowhere within 48 u are not worth another fan at
their own configuration; w09_t15 at 48.0 u is.

## s160: **THE SEARCH CANNOT GENERATE ITS OWN KNOWN ANSWER** -- the fan misses the console's delivered walk endpoint by 0.213 u against a 1.9e-04 u razor strip, and the exclusion is two constants; separately the razor's target now has a unit a walk can steer (`entry_aim.py`)

**s159's "plan into the admitting entry region" led somewhere upstream of every entry question.** Pricing
what a plan would have to DO to reach an admitting entry exposed a COVERAGE gap in the generator.

**1. THE FAN DOES NOT CONTAIN THE CONSOLE'S OWN CANDIDATE.** Run the driver's fan at the console's own
herd, walk length (4) and camera: 98618 at-cap candidates, **nearest walk endpoint 0.212771 u** from the
delivered one (0.347330 u inside its own lean class), **no bit-exact endpoint anywhere**, against a razor
strip **1.877e-04 u** wide -- ~1100 strip-widths. Two constants in `fan_exact` do it: **`PRE_FRAMES = (1,)`**
(one pre frame then a UNIFORM hold -- the console's plan `(0, 208,110,0,2, 169,192,0,2)` is a **2+2** split,
not in the family set at any alphabet) and **`PRE_STRIDE = 32`** (57 decoded classes of 11405; its first
letter (208,110) exists at stride 1 and 2 and **nowhere coarser**). Its HOLD letter (169,192) needs stride
1, so `LEAF_BUDGET`'s autoscaler **cannot** absorb a bigger pre by coarsening the hold -- both segments must
be paid. Containment costs **353 -> 33563 fleets = 95x** (`overnight.containment_knobs`), on a fan already
~56 s an item. **THE MACHINERY REACHES IT BIT-EXACT**: `overnight._fan` fed those letters at that split off
the same base core/trail returns the endpoint BIT-IDENTICAL to the locked `hit['walk']`, at the cap, lean
64761, roll entry = the delivered entry 0-ULP, `genuine`, offset 0. **WHY 12 GREEN CHECKS MISSED IT:**
`verify_console` tested `stick_alphabet(1)` -- finer than the run draws the pre from -- and never tested the
SPLIT SHAPE. Both checks added; it now says **NOT CONTAINED**. Gated `xfail(strict)` + pinned diagnosis +
the bit-exact reproduction (`tests/test_overnight_driver.py`). **So no "0 genuine" from s155-s159 is a
statement about the SPACE**; razor-side results (bands, screens, admitting maps, lean cells) never go
through the fan and stand.

**2. THE RAZOR'S TARGET IS A STRIP ~1.2e-04 u WIDE IN THE ENTRY PLANE** (`harness/tetrapush/entry_aim.py`,
12 gates, KB `model/entry-strip.md`). `|d resid / d ENTRY|` = **0.3095 / 0.5062 per u** at the two delivered
configurations -- the SAME ORDER as `|d resid / d HER|` (0.3457 / 0.2589) -- so `band_distance` was only
unsteerable because **nobody divided it by the gradient**. `offset_u` = band_distance/|grad| = the signed u
Link's entry must move, ~15 us a row (vs ~1 s a screen). Band width / leverage = strip **1.235e-04 u** and
**6.807e-05 u**. The band is **SUFFICIENT ALONG THE ENTRY AXIS TOO**: over +-0.02 u, 875 of 160801 rows are
in-band and **exactly those 875 are genuine** (642/160801 same agreement at s154's). **`aim` SOLVES it**:
displaced 0.70 u it returns a genuine entry in 4-5 steps (~50 ms) -- at the console's configuration a NEW
clip 0.0745 u from the delivered row. `walk_end_for` inverts `roll_entry` onto the fixture's own recorded
endpoint bit-exactly.

**3. HER POSITION IS ONE POINT PER ITEM.** All 98618 candidates share ONE Tetra placement (span
**0.000000 u** -- a 4-frame walk never touches her), so per item the razor has exactly ONE free variable and
it is the entry. Also measured: the fan spans **45 cells x 128 of 129 lean classes** and **32488 distinct
(cell, thrust, lean class, 10 u entry) keys** -- a per-key screen oracle is ~9 h an item and **cannot** be
the router; its endpoint lattice is **0.2-0.4 u**, 3 orders coarser than the strip (so blind enumeration is
a lottery with ~2-4 expected hits an item). Closest draw at the console's own cell: **4.575e-04 u**.

**TRAPS (both cost real time).** **Reference a band at a GRAZING row, never at maximum overlap** -- max
overlap is Link buried in her, `|grad|` reads ~**3000 per u** instead of 0.3 and every cell comes back
band-EMPTY; use `overnight.CLIP_TARGET` (+1.2259). **The band DRIFTS with the entry** (7% of a width at
0.70 u): price with the residual, VERDICT with the sim's `genuine`. And **`entry_grad`'s `mag` is not a
contact test** -- hers dies out of Co range, Link's does not (0.99/u at 565 u), because `resid` is the cut
RAY's offset; a gate caught me asserting otherwise.

**THE s159 SUITE MYSTERY WAS THE BOX.** A s159 `admit_map map` run (17415 configurations) was still going at
12 threads: `pytest` **139 s contended -> 130 s at Idle priority -> 75.5 s free, 0 over-budget, 1316
passed**. s159's `sweep_par` re-benchmark exonerated the box while measuring under the same contention.
`admit_map` is now RESUMABLE (`banked`, `screen_space(resume=)`, `map` resumes by default, torn last line
tolerated); 4167 of 17415 rows banked, restart only when the box is idle.

**NEXT (s161): MAKE THE FAN CONTAIN THE 101, THEN AIM IT.** (1) `PRE_FRAMES` = every `jp < walk`, pre
alphabet stride 2, hold stays stride 1 (do not let the autoscaler trade one for the other); the honest gate
is the fan's leaf set containing the console's endpoint BIT-EXACTLY, not just `verify-console` going green.
(2) Then stop drawing: `aim` + `walk_end_for` give a TARGET walk endpoint per (cell, thrust, lean class);
prune junctions by reachability to it (17 u a frame) -- cheap monotone predictor, subtree prune, exact
bit-confirm.

## s161: **THE CONTAINMENT GAP IS CLOSED AND THE KNOBS ARE PAID (114x)** -- and "aim instead of draw" is a measured NEGATIVE: aiming localises the RAZOR and not the FAN (1.4x prune, 2.4x ordering)

**1. THE SHIPPED KNOBS NOW CONTAIN THE CONSOLE'S PLAN.** `overnight verify-console` is green on **all 16
checks**, including the two that said NOT CONTAINED at the end of s160. `PRE_FRAMES` is the
`PRE_FRAMES_ALL` sentinel expanded per walk by `pre_frames_for` -- **every** split a walk admits, not the
console's own 2+2, because a knob set fitted to the known answer would contain exactly one plan.
`PRE_STRIDE` is **2**. The hold alphabet is **PINNED** at stride 1 by the new `alpha_for`, so
`LEAF_BUDGET` can no longer buy a finer pre by coarsening the hold (the trade s160 named); an item that
does not fit reports `over_budget` instead of absorbing it. The old values survive as
`LEGACY_PRE_STRIDE` / `LEGACY_PRE_FRAMES` because the s160 diagnosis is a measurement ABOUT them, and the
`xfail(strict)` is deleted and replaced by an equality. `containment_knobs` / `verify_console` now take
the knobs as arguments and answer **at the values the run will use** -- the one thing the s160 version
could not do. **PRICE, CALIBRATED: 353 -> 40274 fleets (114x), 0.357 s a junction, ~2 h an item at walk 4**
against the legacy ~1 min. Shipped anyway: a search that cannot emit its own known answer measures nothing.

**2. AIMING DOES NOT PAY THAT OFF, AND THAT IS THE SESSION'S REAL RESULT** (`harness/tetrapush/
aimed_fan.py`, 12 gates, KB `model/aiming-the-fan.md`). The target from `entry_aim` is a **CURVE**
(`aim_curve` walks the level curve and re-aims; 14 of 24 samples genuine, spanning **5.09 u** of walk
endpoint) because the fan's lattice is 0.2-0.4 u and a point is unhittable there. Against it:
  * the admissible junction **prune is 1.4x** -- the reach disc is nearly the whole reachable set
    (displacement over 3 stepped frames runs 3.35..53.15 u against a 57 u disc), 14795 of 20130 kept;
  * the lossless **ordering is ~2.4x** on time-to-first-hit -- ranked against its own delivered endpoint
    the console's junction lands **1366th of 3355**.
**WHY:** the hold segment steers the at-cap endpoint over a **33 degree arc** covering ~12 x 25 u, and
that arc's bearing window is a property of EACH JUNCTION, not a constant (union over 12 sampled
junctions: **41% of the circle**). So knowing where the walk must END pins the junction to an arc band
most junctions are already in.

**3. TWO CHEAPER IDEAS MEASURED AND REFUSED.** **Coarse-then-refine on the held stick cannot be made
lossless**: adjacent byte-grid classes land endpoints a median 0.156 u apart but up to **54.2 u** apart,
so a Lipschitz bound over a coarse cell is 54 u wide and prunes nothing -- it would be the s160 failure in
a new place. And **`at_cap` is not predictable from the stick**: it discards ~70% of leaves AFTER cloning
them, but at the console's own hold length **521 magnitude groups are MIXED**, so the angle decides and a
magnitude threshold would drop real candidates.

**4. THE AT-CAP ANNULUS IS REAL BUT MAY NOT BE A PRUNE.** The leaves the fan KEEPS live in a thin annulus
(**33.65-34.00 / 49.60-51.00 / 64.53-68.00 u** at 2/3/4 stepped frames, against discs of 38/57/76) because
holding the cap means going nearly straight. Its edges are NOT provable -- speedF overshoots to **18.70**
one frame after a stick change so `r x 17.61` is not an upper bound, and the lower edge needs a max turn
rate this work has not derived. Used as an ORDERING (`rank`), where being wrong costs nothing.

**TWO OFF-BY-ONES, BOTH GATED.** A **ONE-stepped-frame probe measures NOTHING**: at `input_delay = 1` the
stick has not acted, so every draw moves the same 17.0000 u and any spread reads exactly 0 (my first
`s161_step.py` was one). Mirror: `reachable`'s `frames` is **STEPPED** (`walk - n0 - jp + 1`, since a
`j`-delivered hold is `_fan`'s `j+1` schedule); passing the delivered count bounded the console's junction
at 38.0 u when it needs 57.0 and pruned **20130 of 20130** junctions, including the branch containing the
answer.

**NEXT (s162): RUN THE CONTAINED FAN FOR REAL.** Containment is settled and no geometric discount is
coming, so the question is empirical: at ~6900 at-cap leaves a junction over a ~300 u^2 cloud, a 5 u target
curve and a 1.2e-04 u strip, the expected genuine count over 20130 junctions is **in the hundreds** vs the
legacy fan's zero-by-construction. (1) finish/bank the leaf-set containment run
(`aimed_fan contain jp=2` -> `fixtures/courtyard_fan_containment.json`; the gate is written and
`skipif`-guarded), (2) score ONE full contained item end to end and count GENUINE, not near. WATCH: the
contained fan's `out` dict hit **540 MB** an hour into a single `jp=2` item -- s150's `MemoryError` shape.


## s163 (2026-08-13): **THE REDISCOVERY GATE IS CLOSED-LOOP GREEN -- the shipped driver, launched blind, generated the console's own plan** (and s162's salvage)

Session 162 ran after the s161 handoff and died without a handoff. It banked the LEAF-SET containment
(`fixtures/courtyard_fan_containment.json`, commit bfa8c60: console endpoint at **d = 0.0** among the
contained fan's 2.1M keys; `tests/test_aimed_fan.py` gate live) and fixed the `item` CLI (commit
2970051: `incumbent=N` now reaches `run_item`, not just the listing -- at 101 `max_walk` drops the
console's own thrust 15, so rediscovery NEEDS `incumbent=102`). **Its working tree held an exact
unexplained revert of that fix** (stale-buffer write); s163 restored to HEAD, pytest 1348/0.

**The run (s163):** `overnight item console-w04 incumbent=102 threads=8` at the shipped contained
knobs, 25 659 s = **7.1 h** (fan 13 038 s / 20 096 junctions -- 3x the jp=2 calibration, PRE_FRAMES_ALL
expands every split -- + scoring 12 619 s which NEVER BEATS: a frozen claim heartbeat with ~10 busy
cores is the scoring half's normal shape, not a stall). Raw 459.3M leaves, 5.61M at-cap, near 11 081,
**genuine 8** -- all thrust 15 / total 101, resid 5.18e-05..1.14e-04, cells 2551/2552, and genuine #3
is **BIT-EXACT the console's own plan** `(0,208,110,0,2,169,192,0,2)`. Confirm 0-ULP, stage
'deliverable'. So `[[search-must-rediscover-known-answer]]` is satisfied in its strongest form and a
"0 genuine" from THIS generator is a statement about the space.

**Density caveat:** 8, not the s161-arithmetic hundreds -- the strip's genuine density is 1-2 orders
thinner than the area ratio (the razor is a positive-interval CURVE, s158). Schedule on measured
counts. **Price caveat:** budget ~7 h a walk-4 item, more at walk 5+.

**The s162 walk-1..4 ladder is COMPLETE and the frame-cheap half of the queue is DEAD**
(`_notes/s162_ladder.jsonl`, 177 admissible items): exactly ONE row has any roll-to-Tetra contact --
the console's own herd at walk 4 (3.1%, best |resid| 7e-03). 31/46 herds end mid-backslide and burn
walk frames converting before a roll dispatches; rungs 42/43/45/47 refused (walled-vs-unwalled herd
divergence). **So beating 101 lives at walk >= 5**, re-run at the shipped knobs in frame-minimal
order -- the s155 walk-5+ zeros were the broken generator's and are a QUEUE, not evidence.


## s164: the density gap decomposed; a ~1-min yield probe now orders the queue; rung05-w05 f95 running

**The 8-vs-hundreds gap is ACCEPTANCE, not area** (s163's own funnel): rows-on-the-strip came out at
the arithmetic's order (~200); all 256 recorded near rows -- one at |resid| 3.7e-07 -- refuse
``blocked``, and the 8 genuine sit in 2 of 135 (cell, thrust) draws. **Shipped
`harness/tetrapush/yield_probe.py`** (commit b798e03): walks every draw's entry-plane strip directly
(the zero set mixes the ~0.3/u strip with never-genuine ~650/u discontinuities -- gentle-bracket
locate, 1 u stations, the sweep's genuine flag), **~50 s an item vs the ~7 h fan**; rediscovery gate
green (console-w04's top-2 probe draws = exactly the two that produced all 8 plans); gate
`tests/test_yield_probe.py`, fixture banked, KB `knowledge/model/admitting-draws.md`. **Zeros are a
screen, never proof** (3 leans / 6 depths / 20-station arcs).

**All-units sweep: 14 of 39 units admit** (`_notes/s164_herd_sweep.json`). Her frozen point is a
HERD property -- walk only buys reach + the aimable cell window. **Check the ANNULUS before the disc
score**: kept leaves live on ~16.1-17.0 u/stepped-frame, and rung07-w08's disc-score 15 sits
entirely in the w08/w09 annulus gap (0 real). Frame-minimal schedule (floor, annulus stations):
**rung05-w05 f95 (1) > rung05-w06 f96 (1) > rung05-w07 f97 (7) / rung10-w05 f97 (6) / rung06-w06
f97 (1) > rung05-w08 f98 (1) / rung07-w09 f98 (7)**. The old floor-order head (rung04, 03/17/32/33,
01/02) probes 0 ANYWHERE -- the s164 rung04-w05 run was killed mid-fan for it and the slot repointed:
**rung05-w05 RUNNING** (`_generated/overnight/s164-rung05-w05`, launched 2026-08-13, 12 h deadline).
Its result is also the probe's first positive-side test on an unseen item -- compare vs prediction
(score 1) and note in `admitting-draws.md`.


### s164 late: rung05-w05 returned 0 -- the miss was REACH; rung06-w05 running

rung05-w05 ran 2.75 h: **0 genuine, 6 in-contact rows of 35.2M** -- the fan's kept edge toward her
is **74.1 u** (`best_overlap_row`) vs the probe's one station at 100.7 u. **Two reach regimes**
(KB `admitting-draws.md`): cap-ending herds walk the 16.1-17/frame annulus; MID-BACKSLIDE herds
(31/46) are conversion-limited far inside it, and no stick-only walk ends at cap at all (the
conversion needs the L-frame flip), so kept-reach anchors on a completed run's `best_overlap_row`
+ <=17 u/frame -- never on a bare rollout or the annulus. Corrected schedule = stations INSIDE the
kept cloud: **rung06-w05 f96 (5 stations 38.8-54.8 u, RUNNING since 2026-08-14 ~01:32Z,
`_generated/overnight/s164-rung06-w05`) > rung10-w05 / rung08-w05 f97 (nearest 61.5 / 44.3 u) >
rung07-w09 f98 (stations 158+, longest-reach herd)**; rung05's own remaining rungs are edge-grazers.


### s164 overnight: rung06 zero-contact; bearings decide; the pivot is the s155 STEERED TAIL

rung06-w05 plain ran **0 genuine, ZERO contact** with stations radially inside its cloud band --
**bearing decides; radial reads and coarse mini-fans (bearing-biased once pre-stride coarsens away
the turning plans) do NOT schedule runs.** rung14 = the only cap-ending admitting herd; its dense
(trustworthy) 2D sample puts its stations 43-60 u off-bearing -- dead at w06/w07. The pivot:
`overnight._steered_tail` (s155, `item ... tail=1,2 tbeam=400`) re-fans the last k frames from
contact-ranked at-cap prefixes -- convert-then-steer, SAME walk/floor, the branch that contains the
console's own w11 plan. **rung05-w05+tail (still floor 95) is the right shape**: its plain fan is
the only one that BRACKETED the razor (6 in-contact rows, |resid| 3.3). Launched ~06:38Z 2026-08-14
(`_generated/overnight/s164-rung05-w05-tail`). **Triage for every other item: coarse fan + score
(the s162 ladder recipe at walk 5, ~5-10 min/item) to find plain-fan CONTACT, then tail-run those**
-- never buy a 3-h slot on a radial/2D estimate again.


### s164 end: the tail is INERT at walk 5 (post-mortem); rung05-w05 EXHAUSTED at f95; rung05-w07 running

The tail run COMPLETED (6.2 h, never deadline-cut) bit-identical to plain: 0 genuine. Post-mortem
(the run's `fan` block): **`tail_atom_prefixes = 0` vs 336 atom junctions** -- walk 5 admits only
atom(4)+steer(1) via `remaining == 0`, gated on `at_cap` READ ON THE SLAM FRAME where the conversion
has not fired -> dead branch (invisible at the walk-11 scale s155 built it for; candidate fix: test
at_cap a frame later -- needs Dereck's bless before touching the production fan). k=2 pool empty on
backslide herds; the k=1 family-steer exhausts into sub-cap drops + held-stick duplicates. **So
`tail=` adds nothing at walk 5**; it matters again at walk >= 6-7 once the slam-frame gate is fixed.
rung05-w05 is EXHAUSTED at floor 95 (plain+tail; its 100.7 u station is past the item's real 74.1 u
cloud). **rung05-w07 (f97) RUNNING since 2026-08-14 ~15:20Z, NO deadline** (Dereck: run items to
completion) -- same-herd reach anchor 74.1+2x17 ~ 108 u covers the station; then rung10-w05 plain.


### s165-eve: rung05-w07 zero -- the axis is now DENSITY; rung10-w05 running

rung05-w07 completed naturally (8.1 h, 1.01M cands): **0 genuine but the ladder's residual axis
moved from reach to DENSITY** -- contact 6->110 rows, first in-band overlaps (21), best_overlap
+1.27 (real contact), best in-contact |resid| 0.067 = ~0.15 u off the strip = ONE endpoint-lattice
cell short. Reach fixed, bearing fine; the miss is 110 contact rows vs console's 30.2M (5 orders).
**More walk frames buy reach, not density** -- this herd GRAZES her at its far edge. rung10-w05
(f97, best triage approach) RUNNING; its verdict decides whether ANY non-console herd sits ON her.
If it grazes too: the plain-fan ladder is density-starved everywhere and the moves are (a) fix the
tail's slam-frame at_cap gate (needs Dereck) or (b) aim-solved last segment (`entry_aim.aim` +
`walk_end_for` -- the enumeration cannot hit a 1.2e-4 u strip on density it does not have).


## s165: THE CAMERA AXIS -- csangle is a real knob; walk-6/floor-96 station 2.48 u away; f95 closed by physics

Dereck steer (s165): stop searching slower-than-cheapest totals; **open new input variation --
the camera**. MEASURED at the rung05 herd (scratch method: wired herd replay -> `run.camera=None`
-> per-frame `csangle=` injection on the native step; the stripped config is the gated one):
csangle reshapes the backslide CONVERSION (as early as f3), **+15 u at-cap reach at walk 5**
(89.0 vs the fan's 74.1), and at **walk 6 the camera-freed cloud CONTAINS the station radius**
(max 105.9 u vs 100.7). Local search: 1-seg 17.4 u -> **2-seg 2.48 u from the f95/f96 station**
(recipe + exact knobs in the s165 handoff). **Floor 95 is CLOSED by cap physics** (station 100.7 vs
~102 absolute / 89 measured at w5) -- the camera ladder starts at rung05-w06 = FLOOR 96. Remaining:
sub-lattice landing (Newton the endpoint onto the station, per-frame csangle freedom), camera
DELIVERABILITY (slew during the herd -- C-stick idle ~80 frames, snap-bill pattern; wired camera IS
the s131 dCamera_c model), herd RE-ENCODING under the moving camera (same decoded bearings ->
bit-exact herd), then the standard accept stack. Also re-rank all 14 admitting units' stations
under camera-freed reach before any more plain-fan slots. Gotchas: csangle injection xor wired
camera (from_f0 raises); neutral C freezes csangle (which value = the pre-positioning problem).


## s166: THE CAMERA AXIS IS REALIZABLE END-TO-END; a total-99 candidate sits 2.3e-03 u (46 strip-widths) from genuine

Dereck steer (mid-session): **csangle is C-stick-DRIVEN -- not all csangles are reachable in a
given time from a given state** -- so s166 rebuilt the whole search on the WIRED camera with real
substick bytes, no injection anywhere. The findings, all banked in `_notes/s166_camera_landing/`
(8 stage scripts + JSONs) + the s166 handoff + README s166 box:
- **Tetra-safe pre-positioning = the final roll f55-70 + untarget f71-72**: substick slew there
  leaves her frozen point BIT-EXACT (verified both extremes) -- stations stand, **no herd
  re-encode needed** (s165 leg B dissolves). Reachable herd-end cs **[0x6e68, 0xa8a2]** (natural
  0x882d). Never touch f53-54 (ATN_MOVE stick-acting).
- **THE CAP-ENTRY REGIME**: cs >= ~0xa5d7 at the f71-72 decode CONVERTS the untarget during the
  herd -- walk starts +18.5 at cap, no L spent; narrow window, right-slew only; the plain fan
  structurally lacks it.
- w06 = 9.03 u short of the (2551,15) station in this regime; **w07 closes to 0.098 u geometric
  (total 99 at thrust 15, beats 101 by 2)**.
- **confirm_entry ALL-GREEN on physics** at the w07 arrival: walk bit-exact, ROLLED at
  **nspeed 26** (the ~131-deg aim-swing entry brake does NOT fire), cell-2551 aim aimable, entry
  bit-exact. Endpoint convention: N-frame walk = N rows, razor endpoint one step PAST the last
  byte (feeding N+1 = phantom frame, false 17 u mismatch).
- **Razor lean convention pinned off the console control: ctx lean = ENTRY-frame m351C =
  lean_at_roll(walk-end m351C)** (console hit: m351C 64761 == lean_at_roll(m351C_walk 64345)).
  Strips exist at EVERY lean (draw_admittance -400..+200: 9-17 stations each; the "lean 25 dead"
  band read was a fixed-entry artifact) but a station is genuine at its EXACT integer lean
  (~5e-5 u strip, ~0.1 u shift/lean); walk-end lean quantizes ~+-200 per final AT-CAP turning
  frame; sub-cap turning is lean-free; settled lean-0 w07 arrivals top out 66.9 u short -- score
  each candidate on its OWN entry-lean strip (lean-adaptive descent + paired early/late moves).
- **Landing state: banded distance 2.3e-03 u** (resid +0.0032, band [4.6e-05, 7.8e-05], entry-lean
  -130). The +-2-byte/+-2-substick final cloud = NULL PROBE (one endpoint 15625x: octagon cell +
  C dead zone). Next knobs: substick grades OUTSIDE the dead zone (~1-3 BAM/grade), msd on EARLY
  frames, bearing bytes at distinct octagon cells; then confirm_entry -> cross_engine ->
  objective.verdict -> DTM.

**s166 end (Dereck: "95 should still be possible"): the schedule's FLOORS are not plan TOTALS.**
Thrust 13 admits NOWHERE at the probed placements (3 facings x 7 leans + the 132-draw table;
screen, not proof), so no banked station yields 95 -- rung05's in-reach station is thrust 15
(total 97 even at w05, and reach makes it w07 = 99). TRUE admitting totals off the banked draw
tables: **rung06-w05 = 97 (t14 station 54.3 u from its herd end) > rung08/rung10-w05 = 98 >
rung05 = 98-99 > rung14/15 = 101+** -- rung06/08/10 were dismissed on PLAIN-fan bearing grounds
that predate the camera axis. Next session: cap-entry + wired-camera pipeline on rung06 FIRST
(each unit needs its own Tetra-safe slew window + converting-cs measurement), then rung08/10,
then the rung05 sub-lattice polish.

**STANDING OBJECTIVE (Dereck, s166 end, supersedes the per-item framing): the FASTEST CONFIRMED
TOTAL with the camera variation.** Work units best-first by TRUE admitting total (a station's own
thrust is part of its price; never quote an item floor as a plan total), run the cheapest all the
way through confirm before touching anything slower, and a cheaper rung's confirmed plan obsoletes
polishing a dearer one. The truncation axis (`units(trunc=)`, new frozen point per cut, yield-probe
priced) is the only banked lever below 97.

## s167: every herd converts (two bytes), the razor is per-CELL, rung06 total-97 at 3.55e-4 u

- **Cap-entry is a STICK DECODE at the untarget frames, not a camera state: camera-forward
  (128,255) on the last two herd rows converts 49/49 rungs to at-cap walk starts
  (+18.86..+19.00), ALL Tetra `_bits`-safe** -- the "31 of 46 mid-backslide" penalty is gone
  (KB `knowledge/strategy/cap-entry-conversion.md`; `_notes/s167_rung06/s167_conv_survey.json`).
  The s166 camera-slew route was the indirect spelling (rotating cs under the fixed (128,110)
  stick); the converting cone is ~+-40 deg of the roll facing.
- **What cap-entry does NOT buy: the TURN.** The walk starts along the roll facing (toward her);
  stations sit 100-137 deg off; turn completes only over distance. Walk-3/4 cones stop 11-38 u
  short of everything (straight-line ceil(d/19) 95/96-total rows are turn-INFEASIBLE); walk 5
  reaches a 137-deg station 88 u out to 0.83 u. One extra free turning row: the herd's LAST row
  is still in the input pipe at herd end and acts on walk step 1 -- hand it to the walk optimizer.
- **The razor is per 16-BAM CELL (`jmaSinTable[angle>>4]`), not per facing**: ctx/band/stations
  bit-identical at 40752 vs 40759 (both cell 2547). Aimability gates check the CELL; the
  confirm's exact facing comes from the aim alphabet at the ARRIVAL cs (the s164 tables' facing
  is the plain fan's csa -- carrying it over cost half a session).
- **Landing: rung06-w05 (cell 2547, thrust 14) = TOTAL 97 (74+5+14+4) at 3.55e-4 u banded**
  (resid -0.001125, band [4.66e-5,8.31e-5], lean_e -260, t14b station 88 u; f72=(160,255);
  rows `s167_r06_stageH.json`) -- 6.5x closer than s166's 99 candidate, 2 frames cheaper.
  Needed precision along the gradient ~1.1e-5 u; byte lattice is a local min; live axes =
  paired near-perp byte moves, C-dead-zone-EDGE substick grades (zone [103,155] measured at
  this herd end), f72 byte grades, the LEAN family. Hop loops `s167_r06_stageJ/K.py` -- read
  their logs FIRST next session (GENUINE True = done), then confirm_entry (seed log = rung06
  rows 0..72 + f72 override; rows = f73 replacement + 5 walk rows; A-press replaces the
  razor-endpoint pad row) -> prepared walls/follow -> cross_engine -> verdict -> DTM.
- Truncation = accounting shuffle at these rungs (c1-c3 re-label final-roll rows as walk rows,
  her point still through them; same physical timelines, no lever below turn-feasible totals).
  Re-ranked queue: rung06 97 (this) < rung08/rung10 t14 98 < rung05 re-priced 98 at w6.
- **s167 END: the lattice at the 3.55e-4 winner is FROZEN** -- 89/126 single lattice moves are
  exact NO-OPs, smallest real endpoint step 6.4e-2 u (180x the gap), 7476-pair scan improved
  nothing: the 16-BAM decode cells eat every sub-cell knob (the s166 "substick ~1e-4 u/grade"
  expectation is DEAD; dead-zone-edge cs grades change no decode). Finish = DENSITY = the fan
  (its s163-proven regime IS cap-start herds): **overnight launched detached on converted
  rung06-w05** (`_notes/s167_rung06/s167_overnight_rung06.py` ->
  `_generated/overnight/s167rung06/`, thrusts [13,14,15], inc 101, ~7 h). Next session READS
  THAT FIRST; thrust-14 genuine = TOTAL 97 -> confirm stack -> DTM. A zero is trustworthy ->
  rung08/rung10 converted the same way (98). rung06-c1 CANNOT cap (the flip needs both
  untarget decode frames -- truncation kills the conversion).

## s168: the entry frame RECOILS off Tetra -- every pre-s168 in-contact result is fiction

- **The s167rung06 overnight (16.3 h) minted 4 thrust-15 "genuine" (total 98) and 0 plans -- and
  BOTH halves of that are fiction**: confirm refused all 4 honestly (their true timelines sweep
  ~0.86 u off-strip), and the zero says nothing (all 9.4M candidates were scored at entries 5-8 u
  off reality). **A pre-s168 zero or landing on any IN-CONTACT item (walk ends near her) is a
  re-run queue, not evidence** -- incl. the s167 3.55e-4 landing, unmeasured until re-priced.
- **The law (proven 0-ULP forward, 5 engine-measured plans + cross-cell aim-independence)**: on
  the roll-dispatch frame the engine resolves the CC pair off Link's WALK-END exec Co centre
  (1-frame pose lag; `co_center_exec(init_frame=False)`) at walk-end positions; the
  `cc_push_pair` halves land on the POST-roll-step Link and on Tetra (5.5-7.6 u each here).
  True entry = `roll_entry + link_half`; razor tetra = `walk_tetra + tetra_half`. The pair is a
  function of the CANDIDATE alone (never the aim). KB: `knowledge/mechanics/entry-frame-recoil.md`.
- **Why 15 sessions of gates never saw it**: the console regime broke contact before entry
  (centre 184.5 u out, engine-checked) -- s163's 8/8, the banked 101, verify-console all live
  where the recoil is exactly 0. The converted cap-entry regime walks TOWARD her stations.
- **Fixed in `overnight.py` (commit 85ea621)**: key = (x, z, m351C, speedF, ccx, ccz, tx, tz)
  (exec centre banked at collect; consumers use [0..3]/[-2:]); `entry_recoil` once per key;
  `entry_corrected`/`tetra_corrected` feed the razor; rows carry tetra (corrected) + tetra_walk +
  co_center + recoil. Out of contact = byte-identical no-op. Gates: `tests/test_entry_recoil.py`
  + `fixtures/courtyard_entry_recoil_s168.json`; closed loop GREEN (score -> confirm all 6 flags).
- **s168rung06 relaunched on the fixed scorer** (converted rung06-w05, thrusts [13,14,15], inc
  101). Price UNMEASURED and > s167's 16.3 h (centre-split key weakens dedupe). The claim
  heartbeat is SILENT for the whole scoring half (measured: 23:27 -> 07:06) -- watch the PID,
  never the beat, in that phase. Thrust-14 genuine = 97, thrust-15 = 98; both beat 101.
- Zero-queue stays pre-armed: `_notes/s168_queue/s168_overnight_item.py` (rung10-w05 15 rerank
  rows vs rung08-w05 7 at total 98, then rung06-w06) -- all three re-run the in-contact ladder
  verdict too.

## s168c: live falsification -> TWO MORE fan fictions (talk-eaten A, unwalled walk); s168 fan KILLED

- **Live DTM of refused#1 (Dereck-requested): NO clip -- the roll never dispatches; console spends
  the A on a CONVERSATION** (proc 170 DEMO_TALK, A at 78.675 u / 5872 BAM off her bearing). The
  acceptance stack (confirm/accept/cross_engine) NEVER models the talk-eat: a confirm-ALL-GREEN
  plan can talk on console. Decomp lead: `setTalkStatus` (d_a_player_main.cpp:2139) -- the eat is
  `mpAttnEntryA` (the ATTENTION JUDGEMENT's A-action selection; SPEAK, or TALK when locked), NOT a
  plain dist/cone -- the console 101's A also lands within 300 u and ROLLS. Model the entry
  selection (d_attention dist_table per-type regions + Zl1 attention_info) decomp-first; the
  turnaround-roll memory's "A while facing away = no talk" is the dodge this selects for.
- **The console follows the WALLED timeline; the fan enumerates UNWALLED**: refused#1's own walk
  shoves Tetra into the south wall (braces z=-940.2556); WALLED sim = live BIT-EXACT through herd
  + conversion + walk + both braces; unwalled 9.204 u off from frame 78. Unwalled scoring is
  fiction wherever the walk reaches a wall = the productive region at south-station items. Fix:
  wall the fan cores (FreeRun has `_core_walls`; native walled cores exist per
  `tests/test_courtyard_walls_native.py`) + re-mint the s168 recoil fixture on the WALLED engine
  (the LAW stands; its 5 fixture rows were unwalled-timeline).
- Delivery clamp safe: (128,255)->(128,254) still cap-converts (live +18.861622); raw-vs-delivered
  bit-identical 104/104. Sim console-0-ULP everywhere modeled; divergence = the talk dispatch only.
- **s168rung06 killed ~1.3 h in** (wall gap -> zero untrustable; talk gap -> positives can talk).
  Relaunch ONLY after: talk gate (validated on refused#1-talks AND console-101-rolls) + walled fan.
  Artifacts: `_notes/s168_queue/live_falsify/` (6 truncation DTMs, sim_reference.json,
  live_results.json, pad readback).

## s168d: fixed stack SHIPPED + live-0-ULP through the cut; w05 stations UNREACHABLE; queue needs re-probe

- **Commits `855514b`/`43447fe`/`cd41b7f`**: walled fan/confirm/trail; talk gate (decomp-cited,
  prunes talker CANDIDATES pre-draw -- key now `(x,z,m351C,speedF,ccx,ccz,facing,tx,tz)`);
  Tetra entry-frame wall brace in `tetra_corrected`. All 5 s167 "genuine" talk-prune at score.
- **w05 STATIONS PHYSICALLY UNREACHABLE under true physics: closest 10.15 u at every
  conversion-cone turning-row variant** (s167's "0.83 u"/total-97 was unwalled fiction). w06
  reaches them (355 candidates) but NO cut touches her there (best ovl -4.97 u) -- **the s164
  admitting stations/yield tables presumed pre-fix physics; re-probe on the fixed stack before
  ordering ANY queue** (that is the next session's job; rung06-w06 98 = only verified-reachable
  rung06 item).
- **Live verify (Dereck's ask)**: best-overlap w06 pick DTM-delivered, truncate-and-read
  ALL-BIT-EXACT (dl=dt=0) at herd end / walk end / ENTRY / mid-roll / CUT frame; diverges only
  PAST the cut (unmodeled aftermath, outside the claim window). First end-to-end console
  verification of converted herd + turning row + walk + cut on the fixed stack.
- **New measured gap: the camera-TRAIL approximation is ~0.41 u soft on turn-heavy walks** (fan
  fleet walks the injected trail; the real wired camera differs when the plan's sticks differ
  from the hold). confirm_entry catches it; fan razor numbers soft until confirmed.
- 10-min-search lesson: the production fan's 10-min prefix never reaches contact (target
  ordering starves pre-junction); the aimed mini-beam (`_notes/s168_queue/s168_aimed_mini*.py`)
  is the <10-min tool (turning-row cone grid + 2-seg beam + production score()).

## s169: ladder RE-PROBED on the fixed stack; w05 dead ladder-wide; turning row = a ~14.6 u axis the fan can't enumerate; rung06-w06 fan LAUNCHED

- **The re-probe** (`_notes/s169_queue/s169_reprobe.py`, the s168 aimed mini generalized per item:
  converted herd + turning-row cone on log[nh-1] + per-item razor stations as biased aim targets +
  walled 2-seg beam + production score()): validated against s168d's rung06-w06 numbers first.
  ~11 min/item. A SCREEN for ordering; `best_station_u` = the honest per-thrust reach.
- **Measured ladder head (10 items): w05 unreachable EVERYWHERE** (rung08/10-w05 41.13/33.79 u
  short, rung05-w06 43.47, rung05-w07 10.80, rung04 no stations), t13 admits nowhere ->
  **no total below 98 exists on the sampled head**. Alive: rung06-w06 (98 @ t14, reach 2.31 u,
  no contact at beam density), rung06-w07 (99 @ t14, IN-CONTACT ovl +4.17 with resid 2.1356e-05 =
  half a band-width below the s167 genuine band -- near-certain at fan density), rung08-w06
  marginal (6.61 u).
- **The turning row (herd's last row, acts on walk step 1) is a reach axis worth ~14.6 u at
  rung06-w06** (canonical (128,255) 16.93 u from t14 stations; best variant (56,160) 2.31 u,
  45/45 ranked) **and the production fan CANNOT enumerate it** (pre-frames = the walk's own
  split) -> a launch BAKES the variant into the herd log (`s169_overnight_item.py <item> <vx>
  <vy>`, gate: at-cap + Tetra _bits vs natural). Every plain-converted fan zero (incl. s167's
  16 h) was reach-starved -- pre-s169 zeros are re-run queues TWICE over (recoil AND reach).
- **RUNNING: rung06-w06 (56,160) fan** -> `_generated/overnight/s169rung06w06_v56_160/`
  (launched 2026-08-16 ~17:30, seed gated sF +18.8616 at cap, fleet est 1.5x w05, expect
  ~24-30 h, scoring half heartbeat-silent). t14 genuine = TOTAL 98. On zero: rung06-w07 next
  (variant-rank it first). KB: cap-entry-conversion.md re-measured; unwalled cone numbers ->
  history/the-unwalled-cone-edge-priced-the-w05-ladder.md. Trail-softness driver queued unrun
  (`s169_trail_softness.py`, only while no fan is up).
- **s169 END, Dereck steer: the next session ARMS A WATCH LOOP on the detached fan (PID 17956)
  and continues AUTONOMOUSLY on completion** (hit -> offline acceptance chain, pause only at the
  live-DTM verify; zero -> variant-rank + detached relaunch of rung06-w07). Detached =
  Start-Process, never run_in_background (the session reaper killed the first launch). Dead PID
  + no result = crash -> relaunch same run_id (claims dir resumes).

## s170: THE BAR IS BEATEN -- total 98 genuine + accepted + clip landed LIVE

The s169 rung06-w06 fan completed clean (69.3 h = 38.6 gen + 30.7 score; 50661 junctions, 38.5M
candidates, 3.04B evaluations) with **THREE genuine total-98 plans at t14**, every one through the
full acceptance chain (confirm_entry six-flags; cross_engine worst_ulp 0, bit-identical cut i=98;
verdict true). Incumbent = 98. Frame accounting vs console 101: **herd 78->74 (-4, cap-entry
conversion + (56,160) turning row), thrust 15->14 (-1), walk 4->6 (+2)**. Live verify (s168
boot-splice protocol, `_notes/s170_queue/s170_live_verify.py`): **Tetra f32-bit-exact at EVERY
truncation end-to-end, Link bit-exact through mid-roll, live cut fired i=98, Link rest PAST the
wall at (-1751.784912, -1016.144958) ~= the predicted 50.2775 u lunge = the clip landed.**
- **The walled sim cannot verify the cut window** -- `wall_for_terminal` braces at the seam, so a
  live clip reads as a lunge-length "divergence" against it BY CONSTRUCTION. Cut-window Link
  reference = the cross-engine composite (0-ULP offline). Live bit-compare of the post-clip rest
  still open.
- **save_plan collision**: names by total-item-thrust, so 3 plans overwrote to ONE file. Recovery
  recipe (worked): tuples+resids from the driver log `[genuine]` events; replay tuple to walk end
  (aim byte inert on the walk-end frame), key off `run._core.co_center_exec(init_frame=False)`,
  re-`score()` the one-key dict, identity pinned by resid (`_notes/s170_queue/s170_remint.py`).
  Facings: 40609 (resid 3.2e-05, cell 2538, aim (94,179)) vs 40752 x2 (cell 2547). All three are
  frame-identical in timing (cut i=98; a suspected 1-frame clip offset was a mis-read).
- **Estimation lessons (three wrong ETAs in one run)**: `st['junctions']` is not fleet units; the
  closed-form `_fleet_estimate` is ~2x under exact; scoring scales with the at_cap CANDIDATE count
  (~343 rows/s measured, s167 basis). `fan_exact(dry=True)` (landed, overnight.py) prices an item
  EXACTLY in ~4 s; `_notes/s169_queue/s169_progress_probe.py map` turns a live claim into exact %.
- **Crash truth (Dereck ask)**: resume is ITEM-granular -- 38M leaves live in RAM until the
  progress row writes, so a mid-item crash loses the whole item (~70 h here). Checkpoint design
  (append-only collect spill + cursor; fast-forward skips leaf fleets; idempotent by
  dict-overwrite) is in the s170 handoff; NOT built.
- Ladder at incumbent 98: rung06-w07 (99) and rung08-w06 dead as chasers; t13 (=97) admits
  nowhere per the s169 re-probe -- 98 may be this shape's floor.
