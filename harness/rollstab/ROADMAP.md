# Seam-clip north star: the TETRA seam clip, pure-sim (multi-session roadmap)

The kaze r11 roll-stab clip (Phase 0, DONE) proved the method: a from-rest bit-exact sim +
exact-acceptance search one-shots a razor seam clip live, 0-ULP. The north star is the same
one-shot for the **Tetra Co-push seam clip** ([[tetra-push-model]] memory; corner at
(-1727,-990), ~1.23u Link/Tetra overlap steers the 49.22u roll-stab through). Everything below
is ordered so each phase lands as a standalone, live-gated sim capability.

**Standing rules for every phase** (same as SESSION_PROMPT.md): decomp-first; primitives already
live-proven are PROMOTED into the per-frame stepper, not rediscovered; each phase ends with a
live-data 0-ULP regression test (goldens like `tests/golden/rollstab_rest_*.json`) and a README
`## Status` update; dead ends go to `knowledge/history/seam-clip-dead-ends.md`. A phase is DONE
only on a confirmed live per-frame comparison, never on offline plausibility.

## Phase 0 -- from-rest exact walk + the kaze clip (DONE, 2026-07-10)

Live clip 0-ULP; pure sim, no calibration. See README `## Status` + the session-10 handoff.

## Phase W -- WALL collision in the stepper (DONE 2026-07-10: single-face + corner ordering)

**DONE (session 11):** `LandState(walls=)` runs the per-frame CrrPos wall pass
(`core.collision.acch_crr_pos`) + the proc wall feedback (wall-hold, m3570 bonk latch,
FRONT_ROLL_CRASH modeled, the sidle A-guard with the `sidle_blocked` planner signal). All four
live gates (head-on / oblique slide / roll crash / slow-roll grind) BIT-EXACT per frame on the
minted faceB anchor; goldens + `tests/test_rollstab_walls.py`; model page
`knowledge/mechanics/wall-response.md`. The original "done ==" bar is met for single-face walls.

**DONE (session 12): corner (multi-wall) correction ORDER.** When two non-coplanar walls correct
in one frame the poly order decides the result. The game's order is its DZB block-grid walk
(`WallCorrectGrpRp` -> `WallCorrectRp` octree DFS -> `RwgWallCorrect`); since `ClassifyPlane`
builds each block's wall list in ascending poly index it is reconstructable statically from the DZB
header tables. `capture_walls.py` reconstructs that walk and writes the room's ordered wall mesh;
the sim loads it via `load_ordered_mesh`. Corner gate (`cornergate.py`) on the minted
`kaze_r11_wallcorner` anchor: CORNER GATE BIT-EXACT 48/48 (24 two-wall frames), swapped order
diverges. Golden + `tests/test_rollstab_corner.py`. wallA(705) before wallB(713), block 137.

**Remainder (speed-only; pick up if a corner enters the solver budget):**
- Full-room block-grid AABB cull: the sim iterates all 765 ordered walls (~33 ms/frame
  pure-Python). Far polys already no-op, so the game's octree cull is a pure speed optimization.
- Walls for the ballistic hops + the freeze's early-return frames (no gate exercises them yet).
- NEW non-wall gap found by the grind gate: mid-run stop -> re-walk blend is not bit-exact
  (see README Status); becomes load-bearing for any plan that fully stops mid-run.

## Phase G -- GROUND collision (DONE 2026-07-10: the Tetra floor is FLAT -> no-op)

Measured first, as planned: the walkable floor Link's roll crosses at the (-1727,-990) Tetra corner
is PERFECTLY FLAT. `harness/rollstab/capture_ground.py` (self-contained, `dolphin_mem` only) samples
the DZB ground along the whole roll footprint old->seam (flooded Hyrule, savestate slot 3): a single
tri (poly 2917), normal (0,1,0), plane Y=0.16327, covers the entire footprint; the normal recomputed
from raw vertices == the game's stored plane == (0, 1, 8e-08). (The ~25-deg surface that shares the
XZ footprint sits ~560u OVERHEAD -- Hyrule terrain -- and the roll at Y~0.16 never touches it; that
was the only thing that could have made "flat" wrong, and it is ruled out.) So `getGroundAngle`'s
slope term r3 = 0 (the sim already hardcodes r3=0 in the speedF `cM_scos` scale; the r3<0 x0.85
branch never fires) and the m35B8 per-foot ground-lift is provably 0 -- the existing flat-floor model
(exact at kaze, also flat) applies to the Tetra clip UNCHANGED. No GroundCross / getGroundAngle /
m35B8 modeling is needed. Fixture `fixtures/hyrule_tetra_ground.json`; regression
`tests/test_tetra_ground.py` (flatness + full-footprint coverage + single-plane; goes RED if a future
Tetra spot ever shows slope -- the signal Phase G modeling has become load-bearing).

## Phase C -- CC collision Link<->Tetra in the stepper

The push model is live-confirmed but lives in standalone probes (`cc_push.py`/`tetra_clip.py`,
[[tetra-push-model]]): dCcS rank-table 50/50 split, Link Co R=30, joint-midpoint center, push
STEERS.

**Tetra counterpart state DONE (session 14).** Decided with Dereck: a PARTIAL `daNpc_Zl1_c` model,
not a full NPC port and not a captured schedule -- her FOLLOW behaviour (she chases Link when he
gets too far) plus the LOCK-ON/TALK region (so a planner avoids accidentally talking/locking her).
`tww_sim/core/npc_zl1.Zl1FollowState` (the `optn_1`/`optn_2` idle<->move follow: engage > 230, turn,
accelerate to `0.04*sqrt(dist^2-130^2)` capped 10, stop <= 130) is **live-gated 0-ULP** on slot 3
(`capture_tetra_follow.py`, `tests/test_tetra_follow.py`), and `zl1_attention_active` is the
decomp-exact avoid predicate (`dist_table[0xAB]`: XZ < 300, ±90deg cone). Her **BG collision** is
modelled too (`mObjAcch.CrrPos` = the same Phase-W `dBgS_Acch::CrrPos`, `dBgS_ObjAcch` subclass, her
single R=50/half-H=30 AcchCir; `step(walls=)`), LIVE-GATED 0-ULP by a corner-wall eject. This
WallCorrect **wall-brace** (wedged Tetra's CC recoil is canceled so she holds) is a validated MECHANIC.
Whether it helps the clip is OPEN (session-19 correction): a corner-braced Tetra pushes the WRONG way
and a stationary behind-Link Tetra gets plowed, so the clip STAGING is unsolved (see Phase T).
Mechanic page `knowledge/mechanics/tetra-follow.md`.

**CC push WIRED into the stepper + live-validated to the push frame (session 15).** The Co push now
runs in the per-frame stepper in the decomp's order: `LandState._cc_move` is consumed in `posMove`
AFTER `posMoveFromFootPos` and BEFORE the m34C2 cut lunge + `CrrPos` (`d_a_player_main.cpp:2556-2610`;
the overlap feeding it is computed in the DRAW phase, `dScnPly_Draw -> dCcS::Move`). `cc_push.
co_move_pair` gives both actors' `SetPosCorrect` moves; `cc_stepper.CcCoupledStepper` couples Link
(`LandState`) + Tetra (`Zl1FollowState`) each frame via Link's animated roll Co centre. LIVE (slot 3,
`capture_cc_push.py`): Tetra teleported into the corner (WallCorrect braces her), Link rolls in and
CONVERGES into her; the coupled sim is **0-ULP** on Link's wall-approach roll AND Tetra's brace, and
Link stays bit-exact through the frame the push is first consumed. Offline gate `tests/test_cc_gate.py`
(no Dolphin, fixture `fixtures/hyrule_cc_push.json`) + math/consumption `tests/test_cc_stepper.py`.

**PUSH FRAMES now bit-exact through the whole roll (session 16): the body lean, not the morf.** The
push overlap uses `body_cyl.roll_co_center`, which drifted on early roll frames -- root-caused (live
capture `capture_roll_lean.py`) to the missing `setWorldMatrix` base z-tilt by `shape_angle.z` (the
MOVE turn lean `m351C>>1`), NOT the oldframe-morf (that touches roll frame 0 only). A curved approach
carries a nonzero turn lean into the roll; `body_cyl.roll_co_center(..., shape_z=)` now feeds the
previous frame's lean, `LandState` exposes `_draw_lean` + evolves `m351C`, `cc_stepper` seeds `m351C`
at roll entry. Live re-capture (slot 3): **every FRONT_ROLL push frame 0-ULP for Link AND Tetra**
(`test_cc_gate::test_coupled_push_frames_bitexact`, xfail->pass; scoped to the roll frames). Live land
14/14 byte-identical.

**CLIP-FRAME ORDERING now bit-exact through the CUT_F entry (session 17).** The clip frame -- Link
fires a FORWARD `CUT_F` out of the roll into the corner-braced Tetra -- stacks, in the decomp's
`posMove` order (`d_a_player_main.cpp:2556-2610`), the roll speedF move -> the ~22u CC push consume ->
the `m34C2` cut lunge (~49u) -> `dBgS_Acch::CrrPos`. Already structural in `step()`; this session
live-VALIDATED it. `cc_stepper.couple_replay` now replays the capture's per-frame controller inputs +
seeds `sword_drawn` so the B thrust fires the roll->CUT at the same frame it did live. LIVE (slot 3,
`capture_cc_push.py draw_at=/thrust_at=`): sword drawn early during the walk-up (drawn-sword walk still
reaches the speedF-17 cap -> full-26 roll), Link rolls into wall-braced Tetra, a UP+B thrust (a neutral
B is a side slash -- dead-end #12) fires an in-line `CUT_F` at roll anim-frame >17. **Every frame from
Tetra's placement through the CUT_F entry is 0-ULP for BOTH actors.** Gate `tests/test_cc_rollstab.py`
(fixture `fixtures/hyrule_cc_rollstab.json`). Scoped to the entry (the single-frame lunge that decides
the clip); wall-BLOCKED here, so it validates the ORDERING, not a clip-through (Phase T threads the
lunge behind the seam).

Still missing to close Phase C:
- The CUT *tail* (the frames after the CUT_F entry): the sim keeps posing Link's Co centre with the
  frozen roll anim (`body_cyl.roll_co_center`) rather than the CUT pose, and live enters a post-cut
  recovery proc (`0x5a`) the sim does not model. Both moot for the clip (decided by the entry lunge;
  the roll never re-walks), like the descoped roll->MOVE exit gap -- model them to extend the window.
- The roll's EXIT to MOVE is not bit-exact (the neutral-hold capture's f27+, the separate "mid-run
  stop -> re-walk" gap). Irrelevant to the clip, which fires a CUT out of the roll, not a MOVE exit.
- Live reticle confirmation of the attention region; the Tetra read-lag (execute order Link-then-
  Tetra in the driver); `GetCCMoveP` from Tetra's own recoil buffer; the `move_jmp` gap hop
  (unmodelled, no gate needs it yet).

## Phase R -- residuals (parallel, pick up when they block)

- Late FRONT_ROLL drawn poses (strict-xfail `test_rest_roll_pose_bitexact`): jointBeforeCB MOMI
  body-lean prime suspect. Becomes load-bearing when a plan WALKS AGAIN after a roll on blend
  frames -- likely in Tetra setups (roll, reposition, roll again).
- `rest_state` models only the sword-drawn `waits` idle arm; a Tetra-area anchor may rest in
  wait00/fidget arms (mint's capture generalizes; the re-init modeling doesn't yet).
- Camera-in-the-loop: kaze's csangle sat frozen; a panning camera feeds the stick decode
  per-frame (CameraManual is bit-exact but unexercised by this pipeline).
- Re-verify the DTM contract (2 alignment rows; 255->254) per new stage via the rest.py gate.

## Phase T -- the Tetra seam clip end-to-end

Same solver shape as Phase 0: from-rest exact approach -> steer via push overlap -> roll+cut
acceptance through exact geometry at the Tetra corner -> deliver clean DTM -> live 0-ULP clip.
No new physics should need discovering by this point; if it does, a phase above was closed
early.

**Acceptance FOUNDATION DONE (session 18), measure-first.** The Tetra corner (-1727,-990) is now in
the rollstab conventions: `fixtures/hyrule_tetra_geo.json` (built offline from the live RAM golden
`tests/golden/hyrule_seam_1727_ram.json` by `make_tetra_geo.py`; wallA +X poly 2915, wallB +Z poly
2904, 90.57-deg corner, the 4-tri CrrPos barrier, `link_y`=0.16327, seam vertex S, authoritative
old/new) + the PUSH-AWARE acceptance module `geometry_tetra.py` (`pred_genuine(old, push)` tests the
coupled `new = f32(old + push + lunge)`). Live-anchored facts (gate `tests/test_tetra_geo.py`, 5
green): NEEDS-PUSH -- the 49.2202u lunge (F=40874) is ~0.7507u short; a ~0.7506u Link push (~1.5u
corner-braced-Tetra overlap x 0.50 share) reproduces the live golden endpoint BIT-EXACT. The approach
razor is threadable (with push fixed, `old` clips over a ~0.86u along-band at ~8% f32 density, kaze-
like); the push is not a free continuous knob -- the coupled sim produces it bit-exactly from Tetra's
f32 placement, so the solver tests the exact candidate.

**Coupled solver core built, but STAGING REOPENED (session 19).** `harness/rollstab/solver_tetra.py` (the
Tetra counterpart of `solver.py`) is wired and its offline STATIC-`co_move_pair` acceptance is gated vs
the live golden (`tests/test_tetra_solver.py`, 6 green) -- but it assumes a staging the DYNAMICS refute.
- **REFUTED: BEHIND-LINK, stationary idle Tetra.** The needed push (~235deg, ~0.75u) is only ~11deg off
  the roll line, so the delivering Tetra sits ~15u from the line -- exactly where Link's rolling Co centre
  travels -- so the roll-in PLOWS her (large chaotic pushes) and flings an un-braced Tetra ~40u away
  before the cut; the CUT_F fires with zero/wrong push (`scratchpad/proto_dynamics.py`, `confirm_plow.py`;
  dead-ends #17). Still sound: the corner NEEDS a push toward the seam (bare is wall-blocked at every
  reachable start), so Tetra must be behind (corner-brace pushes the wrong way); collision-valid start =
  r=35 cylinder clears both walls. The only controlled push is Link plowing a BRACED Tetra.
- Acceptance must be the DYNAMIC coupled cut (run the plow through `cc_stepper.CcCoupledStepper`), NOT the
  static per-position predictor `solver_tetra` uses. `solver.py`'s families' new `F=` param stands.

**Next: the STAGING STRATEGY (open).** Position Link + Tetra so a controlled seam-ward push lands on the
cut frame. Candidates (session-19 handoff): (1) brace Tetra on the behind side (hunt DZB geometry for a
brace); (2) accept the big braced-plow push and search old+aim+placement via the full coupled dynamics.
Then it feeds the from-rest solver (needs a minted slot-3 rest anchor; none exists -- `mint.py` only
translates within a room), verify REST BIT-EXACT (`rest.py`), deliver via `deliver.py`; live 0-ULP clip.
