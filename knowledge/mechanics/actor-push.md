# Actor-vs-actor "Co" push — how Tetra (or any actor) shoves Link

**Answers:** How does another actor push Link (the "Tetra nudge")? What's the cyl-cyl overlap math
and the weight/rank split? Which way and how far does Link get pushed, and on which frame? Can a
Tetra push supply the extra displacement a seam clip needs when the roll/thrust falls just short?
**Status:** validated live — decomp-faithful port ([`tww_sim/core/cc_push.py`](../../tww_sim/core/cc_push.py))
reproduces the game on GZLJ01. The overlap math (`cM3d_Cross_CylCyl`) matches 60/60; the weight split
is the **`dCcS::SetPosCorrect` rank table** (NOT the base `cCcS` mass-proportional split), confirmed
by a live `m_cc_move` capture (`|Link.cc| / |Tetra.cc| = 1.0000` every frame → exact 50/50). Tetra's
cylinder+weight and Link's cylinder are read live (Hyrule, GZLJ01, 2026-07-06). Link's **animated
cylinder center** (root+neck joint midpoint) is a decomp-faithful anim-engine port
([`body_cyl.roll_co_center`](../../tww_sim/core/anim/body_cyl.py)), **live-validated bit-exact** vs the
game's `mCyl` centre during a FRONT_ROLL (2026-07-06).
**Source:** decomp `dCcS::SetPosCorrect` / `dCcS::GetRank` / `rank_tbl` (`d_cc_s.cpp:138/153/180`),
`cM3d_Cross_CylCyl` (`c_m3d.cpp:1553`), `cCcD_Stts::PlusCcMove` (`c_cc_d.cpp`), `daPy_lk_c::posMove`
+ `daPy_lk_c::setCollision` (`d_a_player_main.cpp:9748`) + player/Tetra weights (`:11233`,
`d_a_npc_zl1.cpp`). Constants: [reference/constants.md](../reference/constants.md#collision-actor-co-push).

---

## The chain

Every frame the collision system (`cCcS::ChkCo`) tests all registered **Co** cylinders pairwise.
When two overlap it computes an overlap depth and shares a corrective move between them. Link consumes
his share on the **next** frame, before his own movement and before the wall check.

1. **Overlap depth** — `cM3d_Cross_CylCyl` (the `f32*` variant). Two vertical cylinders (center,
   radius, height). Gate on XZ distance (`dist² > (r₁+r₂)²` → miss) and on Y overlap
   (`c₁.y+h₁ < c₂.y  ||  c₁.y > c₂.y+h₂` → miss); otherwise depth `= (r₁+r₂) − √(dx²+dz²)`.
2. **Weight split** — **`dCcS::SetPosCorrect`** (the game subclass's virtual override — a live
   breakpoint on the base `cCcS::SetPosCorrect` JP 0x8024101C **never fires**; the game calls the
   override at JP 0x800AB1E4). A deadzone `cM3d_IsZero(cross_len)` (|·| < 1e-5) skips it, and a
   both-immovable pair (both weight 0, or both 0xFF) skips too. Otherwise the split is a **rank-table
   lookup**, not mass-proportional:
   - `dCcS::GetRank(weight)` collapses the raw weight to a rank 0..10 (0xFF→10, 0xFE→9, then
     `≥0xD9→8, ≥0xB5→7, ≥0x91→6, ≥0x6D→5, ≥0x49→4, ≥0x25→3, ≥0x02→2, ==1→1, else 0`).
   - `obj1`'s share = `rank_tbl[GetRank(w₁)][GetRank(w₂)] / 100`; `obj2`'s share is the complement.
     The table is **asymmetric** (lower rank ⇒ larger share ⇒ moves more). Same-rank pairs split
     **50/50** regardless of the exact weights.
   - Each actor moves `depth × its share` along the horizontal center-to-center line, **away** from
     the partner.
3. **Consumption** — the move is accumulated into `mStts.m_cc_move` (`PlusCcMove`) and applied on
   Link's next `posMove`: `current.pos += *mStts.GetCCMoveP()` (**first**), then the frame's own
   roll/thrust movement, then `dBgS_Acch::CrrPos` (the wall LineCheck + WallCorrect). So the push
   from frame *N*'s overlap lands on frame *N+1*, combined with that frame's movement, **before** the
   wall is tested.

## Link & Tetra parameters (GZLJ01, live-confirmed)

- **Link** weight **120** → `GetRank(120) = 5`. Body Co cylinder (`daPy_lk_c::setCollision`):
  **R = 30** while walking/rolling (`SetR(50)` *only* when `checkGrabWear()`, i.e. carrying/wearing
  an item); H ≈ `40.1 + (neck_jnt − toe_jnt)` ≈ 107 walking (81.25 in FRONT_ROLL). Its **center is
  the horizontal midpoint of the root & neck joints** (`0.5·(root+neck)` of the *world* anim matrices
  `getAnmMtx(joint)[0/2][3]`, d_a_player_main.cpp:9753-9754), vertical = the lower toe joint
  (FRONT_ROLL: `= current.pos.y`). So Link's Co cylinder is **animation-driven**, not feet-centered:
  it sways ~16–22 u from `current.pos` while walking and, during a **FRONT_ROLL lunge, leads the feet
  by 10–31 u** (peaks ~frame 5–6 of the roll). The offline port
  [`tww_sim/core/anim/body_cyl.roll_co_center(pos, facing, frame)`](../../tww_sim/core/anim/body_cyl.py)
  runs the same world-space FK the walk foot chain uses and is **live-validated bit-exact** (GZLJ01,
  Link rolling pinned at a wall so pos/facing were constant; < 1 ULP once the roll-entry oldframe-morf
  transient settles, ≤0.27 u residual on the first ~10 frames — see the module + `tests/test_body_cyl.py`).
- **Tetra** (NPC `Zl1`) body Co cylinder **R = 50, H = 140, center = `current.pos`** (feet). Weight
  is `0xFF` (immovable, GetRank 10) by default in `createInit`, but **`0x8C` = 140 (GetRank 5)** for
  the `field_0x84F == 5` variant — and the **flooded-Hyrule Tetra is live-confirmed as that variant**
  (`mStts.m_weight` = 0x8C, 2026-07-06).
- ⇒ Link (rank 5) vs Tetra (rank 5): `rank_tbl[5][5] = 50` → **Link takes exactly 0.50 × the overlap
  depth and Tetra recoils 0.50 ×** (live: `|Link.cc| = |Tetra.cc|`, `Link.cc + Tetra.cc = 0` every
  frame). To nudge Link by *d* toward a corner you need overlap `2d`, with Tetra placed on the far
  side of Link from the corner (push = `unit(link − tetra)`). An **immovable** (0xFF) Tetra instead
  gives Link the full depth (`rank_tbl[5][10] = 100`). **Re-confirm the live weight/rank for any other
  scene.**

> **Only actionable, *moving* Link pushes.** Live: an **idle** Link (state 4) sitting inside a 6.4 u
> overlap produced **no** `m_cc_move` and no separation — his body Co cylinder is set/checked while he
> is actively moving (walking/rolling, e.g. state 6). Validate the push with Link *walking into* the
> partner, not standing in overlap. (This is why the earlier debug-pos-hack attempts saw nothing.)

## Using it for a seam clip

A [seam clip](seam-clip.md) needs `old` settled in front of the corner and `new` far enough past the
seam vertex S that WallCorrect no longer overlaps **and** the swept LineCheck misses all four
triangle planes. When the roll/thrust displacement alone lands `new` just short, a Tetra push extends
it: `new = old + push + thrust` (the `posMove` order). [`tetra_clip.py`](../../harness/collision/README.md)
composes `co_push_link` + `crr_pos_walls`: `clip_with_push(old, link_y, thrust, tetra_xz, tris)` runs
one clip frame; `solve_min_overlap` places Tetra directly behind Link and returns the smallest overlap
that clips (with `sumR = 30 + 50 = 80`).

**Worked result (live −1727,−990 anchor, `tests/test_tetra_clip.py`):** a **roll + sword-thrust** of
**49.22 u** toward the corner does **not** clip alone; a Tetra overlap of **≈1.23 u** (push ≈**0.615 u**
at the 0.50 share) reaches ≈49.835 u and clips. (The clip window along the ray is non-monotonic — it
first clips near disp ≈49.78 u.) The Tetra nudge comfortably supplies the missing displacement; it just
needs ~2× the overlap the (wrong) 0.538 model implied.

> **The 49.22 u is a roll + sword thrust; only the roll is modeled (was 06i NEXT #1, partially
> resolved).** The displacement that reaches the corner is a **stacked land move** — a FRONT_ROLL into a
> **sword thrust** (a sword-cut/lunge fired out of the roll). The land sim (`tww_sim/land/land.py`)
> models the **roll** bit-exact — it caps at **26.0 u/frame** (`clamp(speedF·1.5+0.5, 5, 26)`,
> `cap = 0.5 + mMaxNormalSpeed·1.5`, `mMaxNormalSpeed = 17`, `d_a_player_main.cpp:6817`) — which alone is
> below the 35 u seam-clip floor. It does **not** yet model the **sword-thrust** proc that carries the
> total to the ~49 u the corner needs (floor `wall_r/sin(interior/2) = 49.26 u`, true 49.90 u). The cut
> procs live in [`d_a_player_sword.inc`](../../../tww/src/d/actor/d_a_player_sword.inc) — each sets a
> forward `mNormalSpeed` from the pre-cut `speedF` (directional cuts:
> `mNormalSpeed = fabsf(speedF)·field_0x10 + field_0x14`, e.g. cutF `26·0.2 + 8.0`; `procCutRoll`/
> `procCutJump` are the roll-cut / jump-thrust variants), HIO constants `mCut.mCut{A,F,R,L,Roll,Jump}`
> in [`d_a_player_HIO_data.inc`](../../../tww/src/d/actor/d_a_player_HIO_data.inc:27). So
> `test_tetra_clip.py` still uses the 49.22 u figure directly, pending that model. **Still open:** port
> the sword-thrust proc so the sim produces the real per-frame roll+thrust trajectory (and identifies
> the clip frame), replacing the 49.22 u literal; then live-validate 0-ULP. The Tetra-push pipeline that
> closes the gap is validated and unaffected.

> **Where the animated center matters.** The **overlap depth** (and so the push magnitude, ≈1.23 u /
> ≈0.615 u above) is *placement-invariant*: the solver puts Tetra directly behind Link colinear with
> the thrust, so `unit(center − tetra)` is the thrust direction and the depth is exactly the swept
> overlap regardless of where the center sits. What the animated center **does** change is the
> **physical world position Tetra must occupy** to realise that overlap — she stands behind the
> *cylinder center*, not the feet, so at the lunge peak (frame ~5–6, center 31 u ahead of the feet)
> the required Tetra position shifts **~31 u** further along the roll from the feet-proxy spot. Pass
> `link_center=body_cyl.roll_co_center(pos, facing, frame)` to `clip_with_push` / `solve_min_overlap`
> to place her correctly (the returned `tetra_xz`); omit it for the feet proxy. It also matters for a
> **fixed** Tetra (spawned at a set world point, not placed optimally), where the true center changes
> both the depth and the push direction. Still open (per handoff): model the **sword-thrust** half of
> the stacked roll+thrust so the land sim produces the real per-frame displacement (and *which* frame
> is the clip frame) in place of the 49.22 u literal — the roll half (26 u) is already bit-exact.

## Frame-lag caveat for setups

The push consumed on the clip frame comes from the overlap **one frame earlier**. The model assumes a
single clean overlap frame just before the roll (Link settled at `old`, Tetra positioned to overlap).
Because Tetra (rank 5, same as Link) also recoils each overlap frame, a multi-frame hold drifts her —
hold the overlap for exactly the frame before the clip.

## See also
- [mechanics/seam-clip.md](seam-clip.md) — the wall-corner clip this push feeds; `min_f32_clip` reachability.
- [mechanics/collision.md](collision.md) — the DZB wall mesh and the `CrrPos` wall barriers.
- [reference/constants.md](../reference/constants.md#collision-actor-co-push) — cylinder radii/heights, ranks.
- [history/tetra-push-massprop-superseded.md](../history/tetra-push-massprop-superseded.md) — the
  superseded mass-proportional (cCcS, 0.538, R=50) model and why it was wrong.
