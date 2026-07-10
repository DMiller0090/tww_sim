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

## Phase W -- WALL collision in the stepper (NEXT)

Today walls exist only as post-hoc checks (`geometry.seg_blocked` on trajectories computed as if
no walls exist); the live game blocks/slides/holds. Goal: `LandState.step` responds to walls
0-ULP.

- Promote the proven primitives (`core/collision.py` `calc_pla`/`crr_pos_walls`, bit-exact vs
  RAM planes incl. Force25Bit) into a per-frame CrrPos position RESPONSE: block + slide, not a
  boolean. Decomp-first: the player's mAcch/dBgS CrrPos + WallCorrect pipeline and its exact
  ORDER within the execute frame (one anchor point is known: `current.pos += *mStts.GetCCMoveP()`
  right after posMoveFromFootPos, d_a_player_main.cpp:2558; the mAcch pass sits elsewhere).
- Wall-hit STATE into the procs: `mAcch.ChkWallHit()` (roll bonk / short-stop -- a walled roll
  cannot build to the 26 cap; wall-hold; procWait's L wall-snap). Session 5's live trace (roll
  freezes at the kaze face z~304 while the old sim rolled through) is a free first gate.
- Full room mesh in-sim (the live reader `collision_geo.py` exists; kaze fixture exists) + the
  game's block-grid spatial lookup so the 2-minute search budget survives.
- **Done ==** walks and rolls INTO walls (head-on + oblique slide + roll bonk) reproduce live
  per-frame 0-ULP on minted kaze anchors, committed as goldens with a regression test.

## Phase G -- GROUND collision (scope after measuring)

First measure the Tetra spot's floor: if flat, this phase shrinks to nearly nothing. Otherwise:
GroundCross/mAcch ground hits, `getGroundAngle` (the sim hardcodes the slope term r3=0 in the
speedF `cM_scos(r3)` scale + the r3<0 x0.85 branch), and the m35B8 per-foot ground-lift
(provably 0 on flat; already on the Phase R suspect list).

## Phase C -- CC collision Link<->Tetra in the stepper

The model is live-confirmed but lives in standalone probes (`cc_push.py`/`tetra_clip.py`,
[[tetra-push-model]]): dCcS rank-table 50/50 split, Link Co R=30, joint-midpoint center, push
STEERS. Missing:
- The per-frame `GetCCMoveP` term at the decomp's exact point in the frame.
- A **Tetra counterpart state**: her per-frame position/Cyl + reactions. DECIDE (with Dereck):
  full NPC model vs a captured per-frame schedule (anchor-style) -- the schedule bounds plan
  length but is far cheaper.
- The three-way ordering CC-push -> WallCorrect -> net overlap (this interaction IS the clip
  mechanism; order comes from the decomp, not intuition).

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
