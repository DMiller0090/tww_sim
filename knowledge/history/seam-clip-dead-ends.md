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

## Pointers

- Current pipeline + run protocol + verification: `harness/rollstab/README.md`.
- Methodology (why the region is dust, why calibration was added): [strategy/seam-clip-solver.md](../strategy/seam-clip-solver.md).
- Collision / clip mechanism: [mechanics/collision.md](../mechanics/collision.md).
- The SOLVED fast-exact sim-search pattern to reuse: `tww_sim/land/plan_land/_freeze/roll.py`
  (cheap monotone predictor + prune + bit-confirm, no table, no calibration).
