# What a corner clip costs, stated as contact instead of depth

**Answers:** How much overlap does my cut frame need, and where exactly must the pushed actor be
standing? Why is a small aligned push worth more than a large crooked one? How do I rank a raw sweep
row when the razor has not been solved yet? Which aim cell is cheapest to clip on?
**Status:** derived and gated (session 102) on the flooded-Hyrule Tetra corner, in
[`tests/test_tetra_motion.py`](../../tests/test_tetra_motion.py)
(`test_the_required_contact_reproduces_the_delivered_clip`,
`test_the_delivered_cell_is_an_expensive_one_and_2557_is_the_cheapest`). The control is the one clip
this corner is known to give: the requirement predicts its contact to 1.2 u and 0.8 deg.
**Source:** [`harness/tetrapush/razor_depth.py`](../../harness/tetrapush/razor_depth.py)
(`contact_required`, `achievable_depth`, `brace_for_ray`).

---

## The inversion

[The depth law](../strategy/clip-razor-depth.md) reads a configuration and reports what it is worth.
A search needs the other direction: what would be **enough**. At a razor solution every term is pinned
by the aim cell and the brace, so the answer is analytic.

`resid = 0` says the cut segment `base_vec + push` is parallel to `old -> S`. That single constraint
does all the work:

1. **The perpendicular push is not free and not a cost.** It must exactly cancel `base`'s own
   perpendicular component, `g = -|base| sin(delta)`, where `delta` is the facing's angle off the
   `old -> S` ray. In exchange it **rotates the ray**, which lets `old` sit nearer the vertex. This is
   why the delivered clip cuts from 49.3812 while its cell's no-push razor is stuck at 49.6161.
2. **The parallel push must reach the floor**: `f = |S-old| + depth/kappa - |base| cos(delta)`.
3. **The push direction says where she stands.** `|push| = share * cross_len` and the pusher is shoved
   directly away from her, so `t = c - (R_sum - cross_len) * push_hat` about the animation-posed Co
   centre `c`. [Whether that spot exists](placement-standability.md) is a hard constraint, so
   `push_u` has a floor from the GEOMETRY as well as from the depth: aim the push too far off the ray
   and the only place she could be standing is inside a wall.

Walk `old` along the brace locus, walk `push_u` up from `f`, take the first placeable spot, and the
minimum over the locus is that cell's requirement.

## What it says about the Courtyard corner

The corner-most brace CrrPos can park Link on is **49.2546** from the vertex and `|base|` is
**49.2202**, so the lunge is **0.0345 u short before the depth floor is even considered**. Every clip
here is bought with contact; no aiming trick pays for it alone.

Per aim cell, at the frame floor (thrust 13), the required `cross_len`:

| cell | facing | required overlap | aim off the ray | its brace |
|---|---|---|---|---|
| 2557 | 40914 | **0.3939** | 4.9 deg | 49.2546 (corner-most) |
| 2556 | 40901 | 0.4097 | 16.7 deg | 49.2546 |
| 2558 | 40939 | 0.4338 | 25.2 deg | 49.2546 |
| 2552 (delivered) | 40841 | **0.8037** | 34.2 deg | 49.3885 |
| 2549 | 40795 | 1.1268 | 34.5 deg | 49.5227 |

Two things fall out. The requirement is **monotone in the brace**, which is the mechanism rather than a
coincidence: a facing that points at the corner braces corner-most and needs the push only for the
0.0345 u the lunge is short, while one that points 0.38 deg off must also spend perpendicular push
steering the ray back onto the vertex. And the clip that was actually delivered sits on an **expensive**
cell: cell 2557 asks less than half of what cell 2552 does.

**The requirement is thrust-independent.** At every cell, thrusts 13 and 15 agree to under 1%. So the
floor thrust is not refused because it needs more; it is refused because the animation-posed Co centre
is not touching her on its cut frame. That is
["it is all the same animations"](../history/thrust-13-refused-by-geometry.md) as a number.

## Ranking a raw row

`achievable_depth(push, facing, thrust)` is the scalar a sweep can rank before any Newton, and it
depends on the **push vector alone**:

    ray   = |base| * m_hat + push
    depth = kappa(ray) * (|ray| - |S - old(ray)|)

because `resid = 0` fixes the brace from the ray direction (`brace_for_ray`). A large misaligned push
pays twice, rotating the ray and sliding `old` down the wall, so a small aligned push outranks a big
crooked one. On the delivered clip it returns +0.3195 against the measured +0.2533: an **upper bound**,
since it grants the ideal brace for that ray. A negative is therefore a proof and a positive is a lead.

Two cheaper-looking scalars are wrong, and both were tried first:

- **the raw row's own `depth_of`** ignores the other two `genuine` clauses. It happily returns +13.6
  for a row with Link 86 u out and the endpoint behind some far wall.
- **comparing push MAGNITUDES against the requirement** ignores the direction. It scores a 7.4 u
  overlap pointing anywhere at +6.5.

And `achievable_depth` itself owes one clause it cannot check: it is a function of the PUSH, so the
brace it reports is the one the razor WOULD use, not the one the row is at. A row whose own Link is
107 u out in the courtyard still scores its push, and Newtoning it leaves him 107 u out (measured:
+0.0955 at `|S - old|` 107.46, solving to -41). **Screen rows on their own `|S - old|` first.**

## The conjunction, which is where the refusal lives

Neither half is the constraint; the pair is. Banding a swept space (placement x entry x seed motion) by
|resid| and taking the best `achievable_depth` in each band, the trade is **monotone in the distance to
the razor**: every unit of residual left un-zeroed buys depth.

| `\|resid\|` band | cell 2557 (needs 0.394) | cell 2552 (needs 0.804) |
|---|---|---|
| ≤ 0.05 | **-0.0363**, no contact at all | **+0.0399**, 0.65 u of contact |
| ≤ 0.5 | -0.0020 | +0.1564 |
| ≤ 2 | +0.0841 | +0.3910 |
| ≤ 10 | +0.2205 | +0.5121 |

The razor's own acceptance band is ~1e-4, 500x tighter than the tightest column here. So the push that
would pay for a clip is real and it is *near* the curve, not on it: at cell 2557 the near-razor rows have
**no contact**, and the best achievable depth there is exactly the no-push value, the 0.0345 u the lunge
is short. At the delivered cell there IS contact at the razor, and it is worth +0.04 against a 0.115
floor.

Note which cell wins the conjunction: **not the cheap one**. Cell 2557 asks less than half the overlap,
but the spot it asks for is 4.9 deg off the ray, which puts her essentially ON Link's roll line, where
[the plow ejects her hardest](../mechanics/plow-ejection-equilibrium.md). Cell 2552's 34 deg costs more
overlap and lets her stand off the line. The optimum over the aim window is therefore **interior**, and
the two cells sampled here are its ends.
