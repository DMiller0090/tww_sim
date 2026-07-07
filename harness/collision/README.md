# harness/collision — seam-clip model & live validator

Offline, bit-exact model of the **GanonL grand-staircase seam clip** + a live sim-vs-game validator.
The mechanics/root-cause write-up is [`knowledge/mechanics/seam-clip.md`](../../knowledge/mechanics/seam-clip.md);
this folder is the runnable model.

## What's here

| File | Role |
|------|------|
| [`seam_model.py`](seam_model.py) | The seam geometry (4 wall tris + STORED per-triangle planes) + `predict_clip(initial, end)` / `settle_initial`. Wraps [`tww_sim.core.collision`](../../tww_sim/core/collision.py). |
| [`validate_live.py`](validate_live.py) | Drives a running Dolphin (position-hacking) and compares live clip/block vs `predict_clip` fed the game's actual old_pos. |
| [`gap_search.py`](gap_search.py) | Seam-gap finder. **`min_f32_clip`** = the reliable f32-lattice search (settled f32 `old` + f32 `new` box; no false positives, authoritative min-displacement) — use this. `find_clip` / `characterize` / `min_displacement_for_line` = the continuous approximation (pin the line through S, sweep direction, micro-scan offset); now f32-snapped (`_p32`) so it no longer false-POSITIVES on sub-ULP double-precision "gaps", but its `min_displacement` over-estimates. All candidate positions MUST be f32 (Link's pos is `cXyz`=f32); see the f32-honesty notes in the module + `knowledge/mechanics/seam-clip.md`. |
| [`seam_scan.py`](seam_scan.py) | **Stage-wide region scanner** (live). Enumerates a box's differing-normal vertical seam corners, screens each by the analytic floor `wall_r/sin(interior/2)`, and reports its reliable f32 min-displacement via `min_f32_clip`. `python -m harness.collision.seam_scan box=xmin,xmax,ymin,ymax,zmin,zmax target=<D>` (needs `DOLPHIN_PID`). `enumerate_seams`/`scan_seam`/`disp_floor` are the pure pieces. |
| [`angle_experiment.py`](angle_experiment.py) | Sweeps synthetic corner angles (pivot wall B about the seam) through `gap_search` and reports clippability. Near-90° clips; no clean angle cutoff (per-geometry float fan). |
| [`tetra_clip.py`](tetra_clip.py) | **Tetra-nudge → clip pipeline.** Composes [`tww_sim.core.cc_push`](../../tww_sim/core/cc_push.py) (the decomp cyl-cyl Co-push: overlap depth + weight split) with `crr_pos_walls`. `clip_with_push(old, link_y, thrust, tetra_xz, tris)` = one clip frame (`new = old + push + thrust`); `solve_min_overlap(...)` places Tetra behind Link and returns the smallest overlap that clips. On the live (−1727,−990) anchor a 49.22 u roll needs ≈1.23 u overlap (push ≈0.615 u; game uses `dCcS::SetPosCorrect` rank-table split → Link/Tetra both rank 5 → 50/50, live-confirmed; `sumR=30+50`). See `knowledge/mechanics/actor-push.md`. |
| `ganonl_seam_capture.json` | Ground truth: every triangle the game's `LineCheck` tested for the row-1 clip line, with stored plane (n, D) + the game's crossing point + return. Captured via a breakpoint on `cM3d_Cross_LinTri`. Also the oracle for the bit-exact `calc_pla` (frsqrte) test. |

The reusable, geometry-agnostic port of the collision resolution (`LineCheck` + `WallCorrect` +
the `cM3d` math) lives in [`tww_sim/core/collision.py`](../../tww_sim/core/collision.py).

## Run it

```bash
# offline: predict clip vs the brute-force solution set (14k rows)
python -c "from harness.collision.seam_model import predict_clip; print(predict_clip((-817.6296387,-37307.21875),(-855.1299438,-37343.96094)))"

# live vs the game (needs Dolphin on the GanonL seam savestate in slot 1; target it by PID)
DOLPHIN_PID=<pid> python -m harness.collision.validate_live 20
```

## Root cause (one paragraph)

A stage wall quad is two triangles; adjacent quads meet at a shared vertical **seam** edge, so four
triangles meet there. Each triangle stores its **own independently-normalised plane**
(`cM3d_CalcPla`), so the two triangles of one quad differ in the last mantissa bits. `LineCheck`
intersects Link's swept centre-line with **each triangle's own plane** and then runs a projected
point-in-triangle test; near the seam the four crossings land at four slightly different points,
each **just outside** its own triangle → all miss → no wall is reported. If the one-frame
displacement also exceeds the radius-35 wall cylinder (so the static `WallCorrect` at the new
position no longer overlaps the wall), Link ends up past the wall — a clip. This explains the
observed requirements: **>~36 u displacement** (clear the cylinder), **corner angle >90° and not
180°** (the walls must be non-coplanar so their planes differ but still form a seam), and
**perfectly vertical walls** (ny≈0, so `cM3d_Cross_LinTri` skips the Y projection and the seam edge
is a clean shared vertical line).

## Validation

* **Bit-exact**: fed the stored planes, the port reproduces the game's per-triangle crossing points
  to f32 and every hit/miss (`ganonl_seam_capture.json`).
* **Live**: 24/24 cases agree when the port is fed the game's actual old_pos (20-row boundary sweep
  + 4 offline-miss rows), GZLJ01 2026-07-06.
* **Offline over the 14k brute-force clip set**: 14024/14049 (99.82%) predicted as clips with an
  approximated (4-frame WallCorrect) old_pos; the residual is old_pos approximation + dump entries
  that don't reproduce under a clean settle, not model error.

The one fused op that a naive port gets wrong: the plane function's dot product
(`PSVECDotProduct`) fuses `nx*px + ny*py` (`ps_madd`, one rounding). `cM3d_VectorProduct2d` and the
crossing interpolation are NOT fused. See `tww_sim/core/collision.py`.
