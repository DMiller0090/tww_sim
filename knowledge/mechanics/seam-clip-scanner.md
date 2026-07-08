# Seam-clip scanner - "is this corner clippable, and with what exact coords?"

**Answers:** How does the region/stage/full-game scanner decide a wall seam is clippable and hand back
a performable `(old, new)`? What is the DETERMINISTIC clip model (why a clip = cone  AND  standable  AND 
unblocked)? What are the standability gates (OOB skirt, step riser)? Why does the reported seam Y sit at
the floor, not the wall base? Why is the DZB read in world coords (no MULT)? How is the whole game
batch-scanned into the collision-viewer CSVs?
**Status:** model validated; scanner complete-but-slow (see "Current search + status"). The
mechanism/root-cause is [seam-clip.md](seam-clip.md); this page is the tooling around it. Live-confirmed
on GanonL (6/6, and the full room) and Hyrule seams (near-coincident pair, -1727 needs-push), all
clean-placement CLIP drift 0. Guard: [`tests/test_seam_clip_check.py`](../../tests/test_seam_clip_check.py)
(10 offline cases). **Source:** [`harness/collision/seam_clip_check.py`](../../harness/collision/README.md)
(`clip_check` / `scan_region`), `gap_search.py` (`first_f32_clip`), `seam_scan.py` (`enumerate_seams`,
`_gather`, `floor_ys_at`, `read_region_tris`), `dzb_iso.py` (offline disc reader), `window_dataset.py`
(the ground-truth window-labeling oracle), `scan_all_dzb.py` + `export_seam_csv.py` (batch to CSV),
`validate_clips.py` (live confirm). Cylinder / ground constants: `d_bg_s_acch.cpp`, `d_a_player_main.cpp`.

---

## What it answers

`clip_check(barrier_tris, ground_tris, S, wallA, wallB, ...)` decides whether ONE seam clips and returns
one physically-valid **standable** `(old, new)` that performs it: **existence + performable coords,
NOT the minimum displacement** (that is `gap_search.min_f32_clip`, an O(box^2) lattice sweep).
`scan_region` runs it over every enumerated seam in a box; it is pure geometry, no Dolphin (region live
from `read_region_tris` or offline from `dzb_iso.load_room_region` / `seam_scan.load_region_tris`).

## The reliable detector is the f32 lattice

Link's position is f32 (`cXyz`), so the ONLY reachable clips are f32-representable. `first_f32_clip`
(ring-search the f32 lattice out from a guess `new_center`, early-exit on the first clip) is the truth.
**Detection cannot be ULP-coarsened**: the offset window is a razor ~1e-5..1e-3 u regardless of
coordinate magnitude (a coarser step false-negated the live Hyrule seam). Speed must come from
searching the right *place*, not a coarse step - which is what the deterministic model below gives.

## The DETERMINISTIC clip model (this is what makes it computable, not searched)

The game is deterministic, so a clip is *calculable* from the triangle geometry. Reverse-engineered and
validated against the bit-exact model (`window_dataset.py` oracle + the scratch experiments recorded in
[history/seam-scanner-analytic-attempts.md](../history/seam-scanner-analytic-attempts.md)):

- **A clip exists ONLY inside the geometric cone `|rel| <= interior/2`** (`rel` = bisector-relative travel
  direction). A clip needs `new` behind BOTH wall planes; the angle between the normals is
  `180-interior`, so the back-wedge sector `{nA.d<0  and  nB.d<0}` is exactly `interior` wide, i.e.
  `+/-interior/2` about the bisector. Verified: 87/88 measured windows lie inside (one leaks 2deg under the
  +/-20 area tolerance). This bound is FIRM and analytic.
- **An ISOLATED two-wall corner clips at EVERY direction in its cone** (confirmed identical across all
  congruent kaze octagon facets, sharp *and* obtuse). So the clip DIRECTION is not special.
- **Therefore: real clip = cone  AND  standable-floor  AND  valid-old  AND  NOT-barrier-blocked.** The narrow,
  scattered, asymmetric windows seen in a real room are ENTIRELY barrier + floor pruning of the full
  cone - not a property of the corner's angle. (Congruent octagon facets show wildly different real
  windows precisely because their surrounding barriers/floors differ.)
- **The old root-cause of the missed dump seams was a DISTANCE-coverage bug, not angle.** An oblique
  approach settles its `old` FARTHER from the seam than the bisector clearance (`floor`), so a clip's
  old sits at `floor + ~6..18 u`; the previous search probed only `floor + 0..2` and missed every
  oblique clip (e.g. Hyrule (1127,1621), whose window is rel -34..-68 at those deeper distances).

## Current search + status (complete-ish but SLOW - the next lever is the cheap prune)

`clip_check` now sweeps the analytic cone (`|rel| <= interior/2 + CONE_MARGIN`) hot-spot-first (bisector
and both edges first, then mid-cone) at `DIST_OFFSETS` deep distances, early-exiting on the first
standable clip (`CONE_BUDGET` / `PER_CALL_MAX` bound the unclippable-seam cost). Deep-distance coverage
recovers the previously-missed oblique clips. **KNOWN LIMITATIONS (open for the next session):**
(1) UNCLIPPABLE seams pay the full budget (~5-15 s each) because empty `first_f32_clip` rings drain it - 
a full-game dump is impractical until this is fixed. (2) The very-highest-ULP oblique clips can still be
missed at the current `PER_CALL_MAX`. The fix is NOT a bigger sweep - it is to **compute the prune
cheaply** from the model above (cone is analytic; barrier-block + valid-old + floor are cheap
per-direction tests), reducing the f32 work to a tiny verify. A naive "search the bare 2-wall corner
first, then verify barriers at that `new*`" was tried and REJECTED (not reliably faster, and incomplete
 - it verifies around a single `new*`); see the history page for that dead end.

## Standability: a reported `old` must be somewhere Link can stand AND collide

Decided from the static DZB (Dolphin-free; `require_standable=False` / `override_link_y=` opt out):

- **Floor from the DZB ground mesh** (`floor_ys_at`, ny>=0.5) under the approach XZ, never Link's live
  Y, never the wall base; and `old` must be a settled WallCorrect fixed point in front of both walls.
- **The wall must be COLLIDABLE at that floor** (`_floor_at`): a floor is valid only if a LineCheck
  cylinder sample (feet + `WALL_H` = 30.1 / 89.9 / 125.0) lands inside the wall's vertical span. This is
  exactly the game's wall-registration rule (`RwgWallCorrect`, `d_bg_w.cpp:85-89`). It rejects **OOB
  skirt lips**: a wall that tops out below feet+30.1 is never touched (Hyrule underside: floor Y~=-100,
  wall span (-1945,-99.6); the plane-only model reported a phantom clip there).
- **Not a step / ledge riser** (the 60 u ground-snap, `m_ground_check_offset`, `d_bg_s_acch.cpp:60`):
  each frame CrrPos raises Link onto the highest floor within feet+`GROUND_SNAP`. If a staircase of
  floors at the seam XZ climbs from his floor to the wall's CROWN in <=`GROUND_SNAP` hops, he ascends
  the riser ("pops up above"), not a clip. A true barrier's crown is open, or a single jump too tall to
  snap (GanonL's 73 u steps stay clippable). Live: Hyrule (735,-150,323) climbs -150 to -100 to -75.

## Reported seam Y = the standable floor (not the wall base)

The wall is vertical, so the clip is height-invariant; the base vertex can sit well below reachable
ground (GanonL walls based at y~=5762 but the walkable floor is y~=5852, ~90 u up). `scan_region` reports
the seam at the standable floor Y (`= link_y`), so the CSV/viewer place the dot where the clip is
actually performed.

## Enumeration handles authored-geometry variance

Two live-confirmed Hyrule clips were missing from the first dump; `enumerate_seams` now handles both:

- **Near-coincident vertices.** Corner walls need NOT store a bit-identical seam vertex (observed a
  0.09 u XZ offset). An exact `round(x,2)` bucket split them into two single-normal buckets and dropped
  the corner. Now vertical edges are **clustered within `SEAM_XZ_TOL`** (grid union-find, y-span
  overlap) so the two walls pair.
- **Stacked lower/upper tris.** A tall wall is split into stacked triangles; a single representative tri
  can be the UPPER half (y 199-499). `scan_region` computes the standable `yspan` over ALL incident tris
  of the corner (from `seam['polys']`) so the floor check doesn't reject the real floor.

## DZB is stored in WORLD coordinates; MULT is NOT applied

`dzb_iso` reads raw DZB verts and does **not** apply the stage `MULT` room placement. Verified across
the whole game: **all 50 non-identity-MULT rooms are `sea` rooms, and each one's raw DZB centroid
already equals its MULT (tx,tz) exactly** (sea Room44 raw ~= (-200000,+300000) == MULT); 0 rooms are
local. Applying MULT double-offset the sea (world coords ~2x out, the source of the -603213 garbage);
dungeons were unaffected only because their MULT is identity. Planes are the bit-exact `calc_pla` (the
DZB stores none). NOTE: offline-verified (centroid == MULT is conclusive); a live sea-room RAM check
(`[cBgW+0x90]` world verts vs the DZB) is the belt-and-suspenders confirmation, not yet run.

## Batch to CSV to viewer

`scan_all_dzb` scans every game DZB (streaming, resumable, skips DZBs whose `.md` exists) into
`_generated/seam_scan/<stage>/<Arc>__<dzb>.md`. `export_seam_csv` converts those to
`tww-python-scripts/ww/data/seam_clips/<stage>/<Arc>__<dzb>.csv` (one row per clippable seam:
seam / init / dest xyz + interior angle) for the in-Dolphin collision viewer's seam overlay.

## Live validation: clean placement (HARD gotcha)

`validate_clips.py` confirms a scan's clip live: place Link at `old` by writing BOTH player class-pos
triples (`[0x803AD860]+0x10c` and `+0x120`) AND the debug `link_x/y/z` so the placement sweep is
zero-length, then step one clip frame to `new`. Debug-pos-only leaves `pm_old_pos` behind, so the next
CrrPos sweeps a long line, crosses a wall, and snaps Link ~100 u away (spurious BLOCK). Feed full f32 (a
3-decimal-rounded coord flips the razor verdict). Full detail: `../tools/DOLPHIN_CONTROL.md`.

## See also
- [mechanics/seam-clip.md](seam-clip.md): why seam clips work (the float-precision root cause) + the
  bit-exact `cM3d_CalcPla` FP note.
- [mechanics/roll-stab.md](roll-stab.md): the 49.22 single-frame lunge that reaches a clip.
- [reference/constants.md](../reference/constants.md#collision-player-wall-cylinders): wall radius,
  cylinder heights, tolerances.
- [harness/collision/](../../harness/collision/README.md): the runnable scanner + live validator.
