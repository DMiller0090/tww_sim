# Seam-clip solver (roll-stab through a wall seam)

**Answers:** How do we plan a roll-stab that clips through a razor-thin wall seam, and validate it
live? What does the acceptance region actually look like? Why must every candidate be tested with
exact geometry instead of a fitted window? Why does the walk have to be live-calibrated first?
**Status:** SIM-VALIDATED end to end (bit-exact vs live through cruise/arcs/dips/roll on verified
anchors); in-sim genuine clips found routinely; the LIVE clip delivery is the open last step (see
`harness/rollstab/README.md` for the run protocol and status).
**Source:** sessions 7-9 (2026-07-09/10), `_notes/seam-clip-live-validation-handoff-*.md`;
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

## Why live calibration, and what it seeds

Walk startup speed is animation-read (`posMoveFromFootPos`), and the from-rest entry is only
characterized for the fresh-idle anchors. The solver therefore starts every plan with a fixed
constant-stick prefix and pins the sim to ONE live run at a row K0: position, the under-body
frame-controller phases, the `m359C`/`m35B4` smoothing state, and a re-posed toe stream. After
that the sim is bit-exact vs live through cruise, bearing arcs, partial-magnitude dips, and the
roll. The cruise alone cannot verify this (at cap `m3598 = 0` hides the anim state); the gate is
a dip diagnostic (one partial-magnitude frame, then per-frame diff).

## Knobs (mid-walk, from the calibrated state)

- **Bearing arcs** (hold an off-bearing stick 1-3 frames, facing returns to F): gross lateral
  shift of the roll line, several units of reach.
- **Partial-magnitude fines** (1 frame): anim-phase roll-drift classes (discrete perp steps) and
  speed dips (dense along/z fill). Both quantize; combos fill combinatorially.
- **A-press threshold**: the along/z phase on a 17u grid.

Dead ends recorded so nobody repeats them: two-segment pursuit walks (perp treads quantize with a
dead band exactly over the window), per-move-set live bias correction (arc-dependent, not
transferable), a from-rest roll as an anim canonicalizer (does not resync), anchor-z transfer
aiming (live reseeding flips the press frame; the landing is chaotic). Full details:
`harness/rollstab/README.md`.
