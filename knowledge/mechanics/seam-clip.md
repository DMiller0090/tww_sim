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
the clip vs block outcome flips on the last few float bits. The model is only faithful when fed the
game's **stored** per-triangle planes (not recomputed unit normals) and the console's fused
multiply-add (see [FP note](#fp-note) below).

## Why the three requirements

- **≥ ~36 u of displacement in one frame** (35 is the hard floor). The displacement must exceed the
  radius-35 wall **cylinder** so that WallCorrect's *static* test at `new_pos` no longer overlaps the
  wall. Below that, even if LineCheck's swept test misses, WallCorrect shoves Link back out.
- **Corner angle > 90°, easier near 180°, but not 90° or 180°.** The seam must be a genuine
  **non-coplanar corner** so the two walls' planes differ — that difference is what makes the
  per-triangle crossings land on different sides of the seam and all miss. At exactly **180°** the
  walls are coplanar (one plane, no seam gap) → impossible. A shallower bend (closer to 180°, the
  GanonL seam is a ~137° dihedral) keeps the crossings clustered right at the seam vertex where the
  gap is, which is why near-flat corners clip more readily.
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
of `CrrPos` (LineCheck + WallCorrect + the `cM3d` math). [`harness/collision/seam_model.py`](../../harness/collision/README.md)
wraps it with the GanonL seam's four wall triangles (verts + stored planes) and exposes
`predict_clip(initial, end)` → clip/block. `harness/collision/validate_live.py` checks it against a
running game by position-hacking Link's debug pos (`0x803D78FC`).

<a id="fp-note"></a>**FP note.** The one fused op a naive port gets wrong is the plane function's dot
product: `PSVECDotProduct` (paired-single) computes `dot = fadds(fmadds(nx,px, fmuls(ny,py)),
fmuls(nz,pz))` — `nx*px + ny*py` is **fused** (rounds once). `cM3d_VectorProduct2d` (the
point-in-triangle signed areas) and the crossing interpolation (`cM3d_InDivPos1/2`) are **not**
fused. The port uses [`core.fp`](../../tww_sim/core/fp.py)'s `fmadds`/`fmuls`/`fadds` accordingly.

**old_pos matters.** The discriminator is the swept line, so the *exact* `old_pos` (Link's previous
position) decides clip vs block at the razor edge. When feeding a raw brute-force initial, first
**settle** it (a few `WallCorrect` iterations) — the game nudges an initial that overlaps the wall
cylinder off the wall front before the swept frame, so its carried `pm_old_pos` differs from the
placed position by ~0.08 u, which is enough to flip boundary cases.

## See also
- [mechanics/collision.md](collision.md) — the DZB triangle mesh, the `dBgS` manager, the live reader/viewer.
- [reference/constants.md](../reference/constants.md#collision-player-wall-cylinders) — wall radius, cylinder heights, tolerances.
- [harness/collision/](../../harness/collision/README.md) — the runnable model + live validator + ground-truth capture.
