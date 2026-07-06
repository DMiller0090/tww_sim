# Seam clips — why walking/rolling through a wall corner works

**Answers:** Why do "seam clips" work — how does Link pass through a wall where two collision
triangles meet? What's the float-precision root cause? Why the three requirements (≥~36 u of
displacement in one frame, corner angle >90° but not 180°, perfectly vertical walls)? How do I
model / predict one offline?
**Status:** validated — a stdlib FP-faithful port of the collision resolution
([`tww_sim/core/collision.py`](../../tww_sim/core/collision.py)) reproduces the game's per-triangle
crossing points to f32 and every hit/miss, 24/24 live position-hack cases on the GanonL
grand-staircase seam (GZLJ01, 2026-07-06), and predicts 14024/14049 (99.82%) of a brute-force clip
set offline. Model + validator: [`harness/collision/`](../../harness/collision/README.md).
**Source:** decomp `cM3d_Cross_LinTri` / `cM3d_Cross_LinPla` / `cM3d_CrossX/Y/Z_Tri`
(`SSystem/SComponent/c_m3d.cpp`), `RwgLineCheck` (`c_bg_w.cpp`), `dBgS_Acch::CrrPos` + `LineCheck`
(`d/d_bg_s_acch.cpp`), `RwgWallCorrect` (`d/d_bg_w.cpp`), player cylinders
`daPy_lk_c::setBgCheckParam` (`d_a_player_main.cpp:10715`). Live capture via a breakpoint on
`cM3d_Cross_LinTri`. Constants: [reference/constants.md](../reference/constants.md#collision-player-wall-cylinders).

---

## The two horizontal barriers each frame

Every frame the player runs `dBgS_Acch::CrrPos`, which stops/redirects XZ movement with **two
independent checks** (see [collision.md](collision.md) for the mesh/reader):

1. **LineCheck (swept).** Tests Link's centre-line from `old_pos` to `new_pos` against each wall
   triangle via `cM3d_Cross_LinTri` = a plane crossing (`cM3d_Cross_LinPla`) + a projected
   point-in-triangle test (`cM3d_CrossX/Y/Z_Tri`). Only **front→back** crossings count
   (`frontFlag=1, backFlag=0`). It runs only when the horizontal displacement exceeds the wall
   radius (`distXZ² > 35²`). On a hit it snaps `new_pos` back to the crossing point.
2. **WallCorrect (static).** At `new_pos`, pushes Link's wall **cylinder** (radius **35**, three
   heights 30.1/89.9/125.0) out of any wall it still overlaps (`RwgWallCorrect`).

A clip happens only when **both** miss.

## Root cause: independent per-triangle planes at the seam

A stage wall quad is stored as **two triangles**, and adjacent quads meet at a shared vertical
**seam** edge — so up to four triangles meet at the seam. Crucially, each triangle stores its **own
independently-normalised plane** (`cM3d_CalcPla`: `normalize(cross(v1−v0, v2−v0))`, `d=−dot(n,v0)`).
Because the normalize is per-triangle, the two triangles of one quad have normals that differ in the
last mantissa bits — e.g. at the GanonL seam the upper/lower triangles of wall A carry
`0.24360720813` vs `0.24360716343`, and the two triangles of wall B differ too.

`LineCheck` intersects the swept centre-line with **each triangle's own plane independently**, then
tests whether that crossing point lies inside that triangle. Near the seam vertex the four planes
are crossed at **four slightly different points**, and each lands **just outside** its own
triangle's shared edge — so the projected point-in-triangle test (even with its ±20 area-unit
tolerance) rejects all four. **All four triangles report "no crossing" → LineCheck finds no wall.**

Meanwhile, if the one-frame displacement is larger than the cylinder radius, `new_pos` is far enough
past the seam that WallCorrect's static radius-35 cylinder no longer overlaps either wall segment →
no push-back. With both barriers missing, Link keeps `new_pos` — he's through the wall.

This is not a coarse geometric wedge: the crossing points sit within ~0.01 u of the seam edge, and
the clip vs block outcome flips on the last few float bits. Faithful reproduction therefore needs
(a) the console's fused multiply-add (see [FP note](#fp-note)) and (b) the triangle's plane
**exactly** as the game computes it.

> **✅ Status: `calc_pla` is bit-exact (4506/4506 Hyrule planes).** Both paths are now verified.
> The sim *logic* (LineCheck + WallCorrect + `cM3d` math), fed the game's stored planes, reproduces
> real clips bit-for-bit (incl. a live Hyrule clip at the (−1727,−990) seam). And the plane *compute*
> path [`calc_pla`](../../tww_sim/core/collision.py) now matches every RAM plane, every field, so the
> **synthetic-angle results below are trustworthy** (no longer provisional). Reading the plane from
> RAM (`cBgW.pm_tri`, stride 0x18) is still the simplest path for a real seam, but `calc_pla`
> reproduces it exactly — see the FP note under "The model."

## Why the three requirements

- **≥ ~36 u of displacement in one frame** (35 is the hard floor). The displacement must exceed the
  radius-35 wall **cylinder** so that WallCorrect's *static* test at `new_pos` no longer overlaps the
  wall. Below that, even if LineCheck's swept test misses, WallCorrect shoves Link back out.
- **A corner is needed, but there is NO clean angle cutoff — including near 90°.** The two walls'
  planes must differ so the per-triangle crossings land on different sides of the seam; the *amount*
  of difference is set by the per-triangle plane **fan**, a sub-ULP property of the exact vertices,
  not a clean function of the dihedral. The synthetic-angle sweep
  ([`harness/collision/angle_experiment.py`](../../harness/collision/README.md)) — now on
  **bit-exact `calc_pla` planes** — finds clips across interior angles
  **80°–137°** (and reflex/concave corners wider); near-90° clips are also confirmed live on real
  RAM geometry, so the *qualitative* result (no clean angle cutoff) holds. Clippability at a given
  angle is decided by the exact float fan, so it is effectively per-geometry: exactly-90.0° can miss
  while 88°/92° clip. The folk "> 90° and not 180°" rule is only approximate — treat the real
  gate as "the two triangles' bit-exact planes fan enough to miss both crossings," which you check by
  running the model on the actual geometry. (Sharper convex corners tend to need more displacement to
  clear the cylinder, so speed rises as you sharpen.)

> **Open question — flat / 180° seams + a better search.** A real flat seam DOES have a ~1-ULP
> plane difference between its two coplanar segments (verified in RAM: `nx` `0x3f800000` vs
> `0x3f800001`). A brute-force high-speed search (123k lines, disp 70–100, RAM planes) found no clip,
> and the "coplanar segments tile → no divergent wedge" argument suggests flat is unclippable — but
> that is **not a proof** (a brute-force negative can't certify impossibility). **Do not rule out
> flat seams yet.** The clippability search is currently brute-force (start × aim × D) and misses
> razor gaps; the standing TODO is to derive the gap region **analytically** (solve for the line
> offsets/angles where both per-triangle crossings straddle the seam). The prerequisite — a bit-exact
> `calc_pla` for synthetic geometry — is now **done** (4506/4506), so this is the next open item.
> Practical bar for a usable clip: **< 49.6 u/frame** displacement.
- **Perfectly vertical walls (ny ≈ 0).** This is the sharpest requirement, and its cause is
  **LineCheck's three fixed cylinder heights** (30.1 / 89.9 / 125.0), *not* the Y-projection gate.
  A vertical seam's gap is a height-invariant vertical slab, so all three heights miss the same XZ
  point together. Tilt the walls and the seam's gap sits at a *different* XZ at each height — even a
  0.5° lean spreads the three crossing points ~0.4–1.3 u apart (the cylinders are ~95 u apart in Y),
  versus a gap only ~0.01 u wide — so no single straight line can thread all three at once and at
  least one cylinder catches the wall. Verified with the model
  ([`harness/collision/`](../../harness/collision/README.md), `tilt_experiment`): a vertical seam
  yields many clip solutions; **any** tilt ≥0.01° (ny ≥ 0.0002, well below the 0.008 Y-projection
  threshold) drops it to **zero**. With a *single* cylinder height a tilted seam does still clip —
  confirming the per-triangle-plane gap itself is not tilt-dependent; it's the "all three heights
  must miss simultaneously" condition that forces verticality.

## Modelling / predicting a clip

[`tww_sim.core.collision`](../../tww_sim/core/collision.py) is a geometry-agnostic FP-faithful port
of `CrrPos` (LineCheck + WallCorrect + the `cM3d` math). Its `cM3d_CalcPla` is **bit-exact**
(4506/4506 Hyrule planes; see the status note above), so it works on synthetic geometry as well as
on RAM-read planes. [`harness/collision/seam_model.py`](../../harness/collision/README.md)
wraps it with the GanonL seam and exposes `predict_clip(initial, end)` → clip/block;
[`angle_experiment.py`](../../harness/collision/README.md) sweeps synthetic corner angles.
`harness/collision/validate_live.py` checks it against a running game by position-hacking Link's
debug pos (`0x803D78FC`).

<a id="fp-note"></a>**FP note.** `cM3d_CalcPla` is bit-exact (4506/4506 RAM planes) once you get four
console-exact details right — all four verified live via a breakpoint at `PSVECMag`/`cM3d_CalcPla`
(inject a known `sq`, single-step, read the FPRs):
1. **Plane dot product** — `PSVECDotProduct` (paired-single) computes `dot = fadds(fmadds(nx,px,
   fmuls(ny,py)), fmuls(nz,pz))`; `nx*px + ny*py` is **fused** (rounds once). `cM3d_VectorProduct2d`
   (point-in-triangle) and the crossing interpolation (`cM3d_InDivPos1/2`) are **not** fused.
2. **Cross product** — `PSVECCrossProduct` (asm @ `0x8030BC14`) has an exact paired-single lane
   layout: the `nx` lane is `fmsubs(a.y, b.z, fmuls(b.y, a.z))` — it **fuses `a.y*b.z`** and
   **pre-rounds `b.y*a.z`** with a separate `ps_mul`. Getting which product is fused vs pre-rounded
   wrong (e.g. the naive `-(a*b - c)`) flips ~36% of normals by 1 ULP.
3. **Plane normalise** — `cM3d_CalcPla` normalises via `VECMag` (`0x8030BBB0`), which uses Gekko
   **`frsqrte`** (recip-sqrt estimate + ONE Newton step), *not* a correctly-rounded `sqrt`. `calc_pla`
   ports Dolphin's exact `frsqrte` table, and the Newton step is the **fused** `fnmsubs(esq, sq, 3.0)`
   (= `3.0 - esq*sq`, one rounding) — not a separate `fmuls` then subtract.
4. **Gekko 25-bit multiply** — single-precision `fmuls`/`ps_mul` round the **`frC` (multiplier)
   operand to 25 mantissa bits** before the op (Dolphin `Force25Bit`). This is a no-op for genuine
   f32 operands (their low mantissa bits are 0), so it only bites in one place: `fmuls e, e` in
   `VECMag`, where `e` is the ~27-bit `frsqrte` estimate (a f64, not an f32). Without it, `e*e`
   double-rounds 1 ULP off — the last ~3.6% of planes. See `collision.py::_force25`.
The port uses [`core.fp`](../../tww_sim/core/fp.py)'s `fmadds`/`fmuls`/`fadds`/`fmsubs`/`fnmsubs`.

**old_pos matters.** The discriminator is the swept line, so the *exact* `old_pos` (Link's previous
position) decides clip vs block at the razor edge. When feeding a raw brute-force initial, first
**settle** it (a few `WallCorrect` iterations) — the game nudges an initial that overlaps the wall
cylinder off the wall front before the swept frame, so its carried `pm_old_pos` differs from the
placed position by ~0.08 u, which is enough to flip boundary cases.

## See also
- [mechanics/collision.md](collision.md) — the DZB triangle mesh, the `dBgS` manager, the live reader/viewer.
- [reference/constants.md](../reference/constants.md#collision-player-wall-cylinders) — wall radius, cylinder heights, tolerances.
- [harness/collision/](../../harness/collision/README.md) — the runnable model + live validator + ground-truth capture.
