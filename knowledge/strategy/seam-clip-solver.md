# Seam-clip solver (roll-stab through a wall seam)

**Answers:** How do we plan a roll-stab that clips through a razor-thin wall seam, and validate it
live? What does the acceptance region actually look like? Why must every candidate be tested with
exact geometry instead of a fitted window? What made the sim bit-exact from rest?
**Status:** LIVE-DELIVERED (2026-07-10): a solver hit shipped as a clean DTM landed 0-ULP on the
sim's predicted cut (kaze r11, idle13 anchor) and threaded the seam. Regression:
`tests/test_rollstab_rest.py` (live goldens).
**Source:** sessions 7-10 (2026-07-09/10), `_notes/seam-clip-live-validation-handoff-*.md`;
run protocol + model term list in `harness/rollstab/README.md`;
collision model [`mechanics/collision.md`](../mechanics/collision.md) (CrrPos, Force25Bit);
cut mechanics in [`mechanics/land-movement.md`](../mechanics/land-movement.md) (roll stab);
constants in [`reference/constants.md#land-movement`](../reference/constants.md#land-movement).

## The acceptance region is f32 dust

A cut segment `old -> new` clips iff CrrPos does not block it, `old` is in front of both incident
wall planes, and `new` is behind one. Along the roll ray this predicate flickers at ULP scale:
the genuine set is a scatter of slivers 0.0005-0.01u wide (perp), striped per f32 x-column
(adjacent columns' slivers do not overlap in z), at ~10-30% linear density over a 0.5-3u
along-band. Consequences:

- Never target a fitted ribbon/centerline: being 1e-4 from the fit says nothing. Test the exact
  f32 candidate. The real `enter_cut` lunge is constant at fixed facing and `new` equals
  `f32(old + lunge)` bit-for-bit, so the pure-geometry test (`harness/rollstab/geometry.
  pred_genuine`) is exact and cheap.
- `old_z` must sit in a clear band (kaze r11: ~[302.6, 308.2]): lower and the roll is
  wall-blocked short of the cut; higher and the lunge cannot reach behind the planes.
- The roll carries the full 49.2202 lunge only from a capped walk: speedF == 17.0 at the A press
  is a hard gate (a sub-cap walk shrinks the lunge below the seam's displacement floor).

## The sim is bit-exact FROM REST -- plan sequences need no live calibration

The from-rest model (`harness/rollstab/rest.rest_state`) matches live 0-ULP from row 0
through walk entry, cruise, arcs, partial-magnitude dips, and the roll. The terms that closed it
(decomp-grounded; full list + code pointers in `harness/rollstab/README.md`): the WAIT(4) rest
blend with procWait's per-frame re-init (the f31 frame round-trip), the anchor's STORED delayed
foot poses (a translated anchor keeps the pre-mint position's rounding noise), the end-of-frame
draw position (setWorldMatrix runs post-integration), Link's world Y in the pose base, the MOVE
turn lean (setMoveSlantAngle's m351C), and dtm_make's 255->254 stick delivery calibration --
plans must sim the DELIVERED bytes, never the raw plan bytes.

The mid-run K0 calibration this replaces patched only the state a cruise can see (m3598 == 0
hides the toe stream), which is why its dips missed live; historical detail in the session 8-10
handoffs.

## Knobs (from rest)

- **Start crawl** (the 1D approach): K<=3 partial-magnitude sticks (msd 0.52..0.889, bearing F)
  in the first rows, while speed is low -- each partial shifts the whole downstream trajectory
  along-track by a fine quantum, densely filling the A-press 17u phase grid.
- **Bearing arcs** (hold an off-bearing stick 1-3 frames, facing returns to F): gross lateral
  shift of the roll line, several units of reach.
- **Partial-magnitude fines** (1 frame): anim-phase roll-drift classes (discrete perp steps) and
  speed dips (dense along/z fill). Both quantize; combos fill combinatorially.
- **A-press threshold**: the along/z phase on a 17u grid.

Dead ends recorded so nobody repeats them: two-segment pursuit walks (perp treads quantize with a
dead band exactly over the window), per-move-set live bias correction (arc-dependent, not
transferable), a from-rest roll as an anim canonicalizer (does not resync), anchor-z transfer
aiming (live reseeding flips the press frame; the landing is chaotic), K0 mid-run calibration
(see above). Full research log:
[history/seam-clip-dead-ends.md](../history/seam-clip-dead-ends.md); run protocol in
`harness/rollstab/README.md`.
