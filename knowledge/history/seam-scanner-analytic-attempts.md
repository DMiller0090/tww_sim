# Seam-scanner analytic-window attempts (2026-07-08) - what failed and why

> **status: historical** - research log / dead ends, NOT current truth. The current scanner + the
> validated deterministic model live in [mechanics/seam-clip-scanner.md](../mechanics/seam-clip-scanner.md).
> This page records the analytic approaches that were TRIED and REJECTED so the next session does not
> repeat them.

Context: the previous dump missed real clips and listed some that "don't work." Root-causing the misses
(this session) produced the deterministic model on the scanner page. Getting from that model to a
guaranteed-fast COMPLETE scanner is still open. These attempts were on the road there.

## 1. "Clips live only at the bisector or the grazing edges +-interior/2" - REJECTED (incomplete)

First hypothesis: a sharp corner clips near rel 0, an obtuse one clips at the cone edges (grazing a wall
face), so search only bands around `0` and `+-interior/2`. It caught all 80 kaze octagon 135deg facets
(they ARE symmetric, so their windows sit at the edges) and looked like the fix. It is WRONG for
ASYMMETRIC corners: Hyrule (1127,1621) (interior 144, edge +-72) clips at rel -34..-68, a broad band
MID-cone, nowhere near 0 or +-72. Windows can sit anywhere in the cone, so hot-spots-only misses them.

## 2. `sign(kA) == sign(kB)` 2D-tangent direction condition - REJECTED (predicted nothing)

Tried to predict the clip-possible directions analytically: with travel dir `d`, perp `p`, wall face
tangents `uA/uB`, the offset that makes the swept line miss wall A is `rho*kA < 0` where
`kA = (p.uA) - (nA.p)(d.uA)/(nA.d)`; a common `rho` (miss both) needs `sign(kA) == sign(kB)`. It
predicted ZERO clip directions everywhere real clips exist. WHY it is wrong: TWW's inclusion test
(`cM3d_InclusionCheckPosIn3PosBox2d` + `_tri_in_2d`) runs in the triangle's DOMINANT projection (X or Z,
which for a vertical wall involves the Y axis) with a `+-20` area tolerance, and for a diagonal wall BOTH
the X and Z projections must be inside for a hit. The pure-XZ tangent model ignores all of that. A
correct closed form must be derived from `_tri_in_2d`, not the 2D tangent.

## 3. Full-cone brute sweep with deep distances - CORRECT but SLOW

Sweeping the analytic cone (`|rel| <= interior/2`) at deep old-distances (offset +0..+18) with hot-spot
ordering DOES find the oblique clips (fixes the distance-coverage root cause). But UNCLIPPABLE seams
(the majority) drain the whole per-seam budget on empty `first_f32_clip` rings (~5-18 s each), so a
full-game dump is impractical. This is the current shipped state (complete-ish, slow).

## 4. "Search the bare 2-wall corner first, then verify barriers at that `new*`" - REJECTED

Idea: the isolated 2-wall corner clips at EVERY cone direction (verified), and its `first_f32_clip`
never rings out empty (it always finds a clip fast), so search the bare corner for `new*`, then verify
the full barrier set + wall-correct in a TINY box around `new*`. Measured on 5 Hyrule seams: NOT
reliably faster (105 s vs 36 s on one unclippable seam - the bare search itself rings far when that
specific old's bare clip is distant), and INCOMPLETE (missed rel -43 on (1127,1621), found 7 spurious
extras on (919,-7986)) because verifying around a SINGLE `new*` misses the other clipping `new` and the
tiny box mis-includes barrier-blocked ones. The right shape is a per-direction CHEAP prune
(barrier-line-block + valid-old + floor, all O(barriers), no f32 ring), reducing f32 work to a tiny
verify only on surviving directions. That prune is the open work.

## Reusable assets left for the next session

- `harness/collision/window_dataset.py`: the ground-truth window-labeling oracle (feature vector +
  measured clip window per seam, streaming JSONL). Run it to regenerate/extend the dataset.
- `_generated/window_hyrule0.jsonl`, `_generated/window_kaze12.jsonl`: partial measured datasets
  (gitignored; regenerate via the oracle).
- The deterministic model (cone + bare-corner-clips-everywhere + prune) on the scanner page is the
  foundation; the missing piece is the cheap, exact prune computation.
