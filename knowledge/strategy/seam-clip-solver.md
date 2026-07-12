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

## Tetra-corner placement: a thin thread, ~f32-precise perpendicular (2026-07-12)

For the Tetra push-aside / turnaround clip the free knob is not `old` but Tetra's f32 START
placement `(x, z)` (`placed_step=0`): her plow feeds the CC push that steers the lunge. The TAS
question -- must we hit her position float-perfect, or is there a targetable range? -- was answered
by an offline sweep at the FIXED, live-measured slot-7 roll entry
`(-1516.116455078125, -765.1473999023438)`, facing 40835, m351C 0 (native `ShoveCtx.sweep_par`, the
bit-confirmed genuine test; ~66k sims/s; region located via the smooth pre-CrrPos behindA/behindB
ridge then column-chunked f32 sweeps to dodge the wide-grid OOM).

The genuine placement set is a **thin connected THREAD**, not a point and not a fat band:
- It runs ~**46u** along a ~**59deg**-from-+X diagonal in `(x,z)` (slope dz/dx ~ 1.67), over roughly
  x[-1651.7, -1628.1], z[-933.3, -893.2]. It **meanders +-~2u** off a straight fit (RMS resid 1.14u),
  so you FOLLOW the thread; a linear fit is useless (dead-end #8 restated for placement).
- **Perpendicular thickness = ~f32 dust**: at a fixed x-column the genuine z is one sliver, median
  **~8 f32-ULP (~4.9e-4u)**, range 1-16 ULP (~6e-5..1e-3u). This is the precision a TAS must hit
  perpendicular to the thread.
- **Continuity**: ~**84%** of consecutive f32 x-columns carry a genuine sliver (short 1-few-column
  gaps; runs up to ~35 columns), and adjacent columns' slivers OVERLAP/touch. So unlike the kaze
  linear-approach dust (disjoint per-f32-column stripes), the Tetra-placement set is a CONNECTED
  thread -- targetable as a curve with ~46u of along-freedom.
- The clip **landing `new` drifts** monotonically ~0.001u along the thread (12 distinct f32 values);
  the shipped target `new=(-1727.1728515625, -990.4632568359375)` is reproduced bit-exact only on a
  ~1-2u sub-segment. **Any** thread point clips (Link falls, proc 39) -- the target-`new` pin matters
  only to reproduce the exact shipped landing, not to clip.

**Verdict:** a valid Tetra placement is a **line, not a lottery point** -- ~46u of along-slack -- but
perpendicular you must be f32-precise (~5e-4u). At the shipped entry the thread sits **57-100u from the
nearest floor wall** (the seam walls themselves; all other nearby polys are overhead terrain at
Y~500 that a floor actor never touches).

### Wall-brace: relocating the thread onto wallB (entry-variation)

Bracing Tetra against a wall would pin the hard perpendicular coordinate for free (WallCorrect ejects
her to a fixed distance; the TAS just walks her into the wall). Shifting the ROLL ENTRY moves the
whole thread: a **perp- entry shift** (perpendicular to the roll facing) walks the thread toward
wallB (+Z, z=-990.256), and at entry ~**perp -1.3u** from the shipped entry the thread's corner-ward
tip reaches **exactly the wallB brace locus** (fB = TET_R = 50, i.e. z = -940.25562 -- verified: any
deeper placement is CrrPos-ejected to that z, so fB=50 IS the wall). Braced-genuine placements
(genuine AND at z=-940.25562) exist across a band of entries; `new` stays bit-exact on the shipped
target throughout.

**But there is NO usable slide RANGE -- bracing only removes one coordinate, and this is fundamental.**
The along-wall window = (thread thickness ~5e-4u) / sin(crossing angle), so a range wide enough to be
useful (~0.1u) needs the thread within ~0.3deg of PARALLEL to the wall at the brace distance. It never
is:
- **wallB (reachable): near-PERPENDICULAR crossing.** Near the brace point the thread's LOCAL angle is
  **75-82deg** vs wallB's 0deg (it meanders; 59deg was the global mean). So the braced-genuine window
  is just **2-3 f32-ULP (~0.0001-0.0002u in x) at ALL in-window facings** (swept 40805-40880; the angle
  never rotates toward 0). The genuine x shifts ~1:1 with the entry shift -- trade Link's roll-entry
  for Tetra's x, but each is a point. Bracing on wallB pins the perpendicular (z) coordinate for free
  yet the along-wall (x) still needs f32 precision: **2D-f32 -> 1D-f32, not a range.**
- **wallA (near-PARALLEL, ~78-82deg -> the wall that COULD give a range): UNREACHABLE.** The genuine
  thread's corner-ward tip is pinned at x~-1650 (fA~76) at EVERY Link entry tried (9 directions:
  perp/roll/axis shifts +-1.5-3u) -- closest approach fA=75.7, still ~25u short of the wallA brace
  (fA=50, x~-1677.66). The tip pin is an acceptance-geometry limit (where Tetra must sit to steer the
  lunge), not a knob not-yet-turned.

**Bottom line for the TAS:** Tetra can be placed AGAINST wallB (z pinned by the wall) but the along-wall
x is still an f32 point; no Link knob (entry position, facing across the seam-gap window) opens a slide
range. Untried knobs that MIGHT move the tip toward wallA (unproven, likely small): a curved walk-up
(nonzero `m351C` turn-lean at roll entry) and the thrust/roll timing -- both change the push/roll
geometry, but the tip pin looks geometric, so expectations are low.

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
