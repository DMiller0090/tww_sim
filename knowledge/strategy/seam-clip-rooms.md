# Seam-clip room generalization (screening and delivering beyond kaze r11)

**Answers:** How does the seam-clip pipeline run in a room other than kaze r11? How do we pick
the NEXT room worth capturing? What room-level hazards block a delivery that the seam-level
screen numbers cannot see?
**Status:** LIVE-DELIVERED in three rooms (2026-07-18): kaze r11 (8 seams), flooded Hyrule
(REST bit-exact; clip an honest lottery), Hyrule Castle interior `Hyroom` r0 (clip live 0-ULP,
session 63). Regressions: the per-seam `tests/test_*_clip.py` gates.
**Source:** sessions 62-63 (2026-07-18), `_notes/seam-clip-live-validation-handoff-*.md`;
dead-ends #46-#51 in [history/seam-clip-dead-ends.md](../history/seam-clip-dead-ends.md);
methodology in [seam-clip-solver.md](seam-clip-solver.md); run protocol in
`harness/rollstab/README.md`.

## The pipeline is room-agnostic (session 62)

The whole chain runs on any room via `mesh=`/`prefix=`/`base=` knobs: capture the room's ordered
wall mesh (`capture_walls.py`), screen it (`seam_screen mesh=`), one-shot it
(`novel_deliver mesh= prefix= base=<a settled-idle anchor in that stage>`). Proven END-TO-END
through REST on flooded Hyrule: the from-rest model held **BIT-EXACT 0-ULP outside kaze r11** on
the first try once three NEW mint-time blockers were cleared (dead-ends #46-#48): open terrain is
mostly SLOPED (the flat-floor rest model needs a genuinely flat ~1200u corridor -- floor-LADDER
the aim line before minting and require constant y, not just fall_tol "FLOOR"), a wall-bottom
`link_y` can be a phantom ledge with no ground, and a LOW-HEALTH base savestate idles in
ANM_WAITB which the rest blend model does not cover (heal Link at mint; probe for steady WAITS --
d_rate 1.1 -- before `mint_current`). A grazing `aim_deg` can trade dust density for a flat
corridor (the delivered-aim corridor must live on the flat strip; seam_2709_2919 hugs its wall's
300u strip at aim 344). Hyrule's one all-gates-green corner is dust-thin (band_dense
0.011-0.014u) -- an honest lottery with a REST-verified anchor ready; density and floor quality
trade off room by room.

## Man-made floors DO screen better -- and rooms carry EVENTS (session 63)

The Hyrule lesson held: a dungeon-class room with man-made flat floors delivered in one session
where open terrain was a lottery. `Hyroom` r0's basement corner seam_4002_4004 (interior 93.0,
band_dense 0.018u, corridor 1340u, ~9.2k exact dust points vs hseam2709's thin band) went
screen -> mint -> REST BIT-EXACT -> 1-2 clips per good-lattice draw -> live 0-ULP.

- **Pre-rank candidate ROOMS offline before capturing anything:** the seam-locator CSVs
  (`tww-python-scripts/ww/data/seam_clips/<stage>/`) count clip seams per room -- a room whose
  clips share ONE floor Y is the man-made-flat signature (Hyroom r0: 68 on Y -649.8; the winning
  basement level).
- **The room must not carry an ARMED one-shot auto-event across the corridor** (dead-end #49):
  an A press fires the event instead of the roll (Hyroom: `daPyProc_DEMO_LOOK_AROUND2_e`), while
  buttonless walks -- and therefore the REST gate -- pass clean. Consume the event in the mint
  base (it is one-shot) and validate a new room's base with an A-press probe mid-corridor.
- **A spectacular screen row can be a non-room** (room-pick notes, session 63): Siren r0 = boat
  spawn + tidal pool floor; the Hyroom hexagon chamber = visibly open gaps behind 460-700u
  corridors, under the ~900u+ (rest 580 + settle) the standard roll mint needs.
- **When a good corner draws 0 across the documented families, the ANCHOR's chaotic lattice is
  the ticket** (dead-ends #9/#51): re-mint at the NEXT frozen cam target from the cam screen's
  measured set (different csangle -> different F/dust slice/lattice). The mint itself is
  deterministic from the base, so re-running it identically is NOT a new draw. Ship -- or archive
  the winning stream + seed -- BEFORE re-minting a name (dead-end #50: a re-mint orphans a
  solved-but-unshipped hit).
