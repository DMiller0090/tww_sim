# Actor-vs-actor "Co" push — how Tetra (or any actor) shoves Link

**Answers:** How does another actor push Link (the "Tetra nudge")? What's the cyl-cyl overlap math
and the mass/weight split? Which way and how far does Link get pushed, and on which frame? Can a
Tetra push supply the extra displacement a seam clip needs when the roll/thrust falls just short?
**Status:** validated — decomp-faithful port ([`tww_sim/core/cc_push.py`](../../tww_sim/core/cc_push.py))
reproduces `cM3d_Cross_CylCyl` live (gate/miss 60/60 on GZLJ01) and drives a clip pipeline
([`harness/collision/tetra_clip.py`](../../harness/collision/README.md)) on the live (−1727,−990)
anchor. Tetra's cylinder + weight are **live-confirmed** (Hyrule, GZLJ01, 2026-07-06). Live push
*magnitude* observation is still pending a Co-active savestate (see the caveat below).
**Source:** decomp `cM3d_Cross_CylCyl` (`c_m3d.cpp`), `cCcS::SetPosCorrect` / `cCcS::ChkCo`
(`c_cc_s.cpp`), `cCcD_Stts::PlusCcMove` (`c_cc_d.cpp`), `daPy_lk_c::posMove`
(`d_a_player_main.cpp:2488`) + player/Tetra cylinders & weights (`:9760/:11233`, `d_a_npc_zl1.cpp`).
Constants: [reference/constants.md](../reference/constants.md#collision-player-wall-cylinders).

---

## The chain

Every frame the collision system (`cCcS::ChkCo`) tests all registered **Co** cylinders pairwise.
When two overlap it computes an overlap depth and shares a corrective move between them by weight.
Link consumes his share on the **next** frame, before his own movement and before the wall check.

1. **Overlap depth** — `cM3d_Cross_CylCyl` (the `f32*` variant). Two vertical cylinders (center at
   the feet, radius, height). Gate on XZ distance (`dist² > (r₁+r₂)²` → miss) and on Y overlap
   (`c₁.y+h₁ < c₂.y  ||  c₁.y > c₂.y+h₂` → miss); otherwise depth `= (r₁+r₂) − √(dx²+dz²)`.
2. **Weight split** — `cCcS::SetPosCorrect`. A deadzone `|depth| < 1/125 u` skips it. Each actor's
   weight *type* comes from `cCcS::GetWt` (`0xFF→Type0` immovable, `0xFE→Type1`, else `Type2` with
   the value as mass). Each actor is moved by `depth × (the OTHER actor's assigned weight)` along the
   horizontal center-to-center line, **away** from the partner:
   - Type2 vs **Type0**: the Type2 actor takes the **full** depth; the Type0 actor doesn't move.
   - **Type2 vs Type2**: mass-proportional — actor *i* moves `depth × mⱼ/(mᵢ+mⱼ)`. Both move.
3. **Consumption** — the move is accumulated into `mStts.m_cc_move` (`PlusCcMove`) and applied on
   Link's next `posMove`: `current.pos += *mStts.GetCCMoveP()` (**first**), then the frame's own
   roll/thrust movement, then `dBgS_Acch::CrrPos` (the wall LineCheck + WallCorrect). So the push
   from frame *N*'s overlap lands on frame *N+1*, combined with that frame's movement, **before** the
   wall is tested.

## Link & Tetra parameters (GZLJ01)

- **Link** body Co cylinder R=50 (standing; 30 crawling), H≈81.25; weight **120** (Type2).
- **Tetra** (NPC `Zl1`) body Co cylinder R=50, H=140, center at her feet (= `current.pos`). Weight is
  `0xFF` (Type0, immovable) by default in `createInit`, but **`0x8C` = 140 (Type2)** for the
  `field_0x84F == 5` variant — and **the flooded-Hyrule Tetra is live-confirmed as that Type2, weight-140
  variant** (read `mStts.m_weight` = 0x8C, 2026-07-06). Consequences:
  - Link takes only **140/260 ≈ 0.538×** the overlap depth (NOT the full depth an immovable Tetra
    would give), and **Tetra recoils** by `120/260 ≈ 0.462×`.
  - So to nudge Link by *d* toward a corner you need overlap `d / 0.538`, with Tetra placed on the
    far side of Link from the corner (push = `unit(link − tetra)`).
  - Re-confirm the live weight for any other scene — a Type0 Tetra elsewhere would push differently.

## Using it for a seam clip

A [seam clip](seam-clip.md) needs `old` settled in front of the corner and `new` far enough past the
seam vertex S that WallCorrect no longer overlaps **and** the swept LineCheck misses all four
triangle planes. When the roll/thrust displacement alone lands `new` just short of the corner's f32
minimum, a Tetra push extends it: `new = old + push + thrust` (the `posMove` order).
[`tetra_clip.py`](../../harness/collision/README.md) composes `co_push_link` + `crr_pos_walls`:
`clip_with_push(old, link_y, thrust, tetra_xz, tris)` runs one clip frame; `solve_min_overlap`
places Tetra directly behind Link and returns the smallest overlap that clips.

**Worked result (live −1727,−990 anchor, `tests/test_tetra_clip.py`):** a roll/thrust of **49.22 u**
toward the corner does **not** clip alone; a Tetra overlap of **≈0.68 u** (push ≈0.37 u at the 0.538
share) reaches ≈49.586 u displacement and clips. This matches the ~0.37 u the corner was missing.
(Note the clip threshold along the roll direction, ≈49.586 u, is *below* the earlier `min_f32_clip`
box-min of 49.957 u — the corner is a touch more clippable along the bisector than that logged.)

> **⚠️ Live push-magnitude validation pending.** The overlap-depth formula matches the game live
> (`cM3d_Cross_CylCyl` gate/miss, 60/60), and Tetra's weight/cylinder are read live, but a direct
> observation of Link's push *displacement* hasn't been captured yet — in this session's scene Link's
> body `mCyl` read as unregistered and no push fired, so the overlap couldn't be exercised. Do it on a
> savestate where Link is actionable next to Tetra. The math is a direct decomp port; treat the
> pipeline as model-validated, live-magnitude-pending.

## Frame-lag caveat for setups

The push consumed on the clip frame comes from the overlap **one frame earlier**. The model assumes a
single clean overlap frame just before the roll (Link settled at `old`, Tetra positioned to overlap).
Because Tetra is Type2 she also recoils each overlap frame, so a multi-frame hold drifts her — hold
the overlap for exactly the frame before the clip.

## See also
- [mechanics/seam-clip.md](seam-clip.md) — the wall-corner clip this push feeds; `min_f32_clip` reachability.
- [mechanics/collision.md](collision.md) — the DZB wall mesh and the `CrrPos` wall barriers.
- [reference/constants.md](../reference/constants.md#collision-player-wall-cylinders) — cylinder radii/heights.
