# The axis the endgame is denominated in is 64 degrees off the one the herd pushes along

**Answers:** The herd has to leave Tetra on the genuine side of the clip roll's approach line and it
keeps landing short - is that a reachability problem or a cut? Why do the endpoints that carry her
across all sit far OFF the push corridor? Which of the herd's keeps are still describing the old
target?
**Status:** measured. `l0` is linear in her herd coordinates with **unequal** gradients, so a unit of
LATERAL push buys 2.07x what a unit of down-herd push buys - and every keep in the herd stack drives
the lateral to zero. Screened with the axis at the probe pool and the per-aim screen, the cycle-2
stage reaches **`l0` -63.15** against a bar of **-80.4** and a banked beam that hands over
**-183.41**. Gate [`tests/test_l0_screen.py`](../../tests/test_l0_screen.py).
**Source:** [`harness/tetrapush/handoff.py`](../../harness/tetrapush/handoff.py) (`tetra_lateral`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`'s ``pf``,
`_probe_pool`'s ``l0_key``, `extend_cycle`'s ``l0_keep``),
[`harness/tetrapush/reposition.py`](../../harness/tetrapush/reposition.py) (`HerdLine`).
Measured session 134; probes `_notes/s134_l0_headroom.py`, `_notes/s134_free_axis.py`.

## The two gradients

`l0` is her offset from the clip roll's approach line, `(tetra - brace)·q`. Projected onto the herd
frame it is linear, and the coefficients are the whole finding:

    l0 = 0.4344838355514977 * along + 0.900679541214783 * lat - 411.99

| to gain 103 u of `l0` | costs |
|---|---|
| pure down-herd (`along`) | **237.1 u** |
| pure lateral (`lat`) | **114.4 u** |
| along `q` itself | **103.0 u** |

The herd line sits **64.25 deg** off `q` (25.75 deg off the pair frame's `m`). So the push converts
displacement into the endgame's currency at 0.43 where the best available rate is 1.0.

**This is not a bug in the herd line.** It aims at the genuine-coord centroid, and the 288 tabulated
coords do sit on it - herd **along 937.5-984.1, lat -2.3..+7.9**, `l0` **+2.50..+13.69**. Pushing her
all the way down the line reaches them. What changed is the target: session 123 deleted the
walk-away and session 125 moved the razor onto LINK, so what the herd must deliver is no longer a
POINT at along ~967 but a HALF-PLANE (`l0 > 0`) plus a pair alignment - and a half-plane is reached
fastest along its own normal.

## What the cage costs, and what it actually asserts

The plow regime is asserted in three places, and each mixes a coordinate-free claim about the pair
with a claim about which way it is pushing:

* `full_herd.in_pursuit_box` - `lead` in -127.8..-26.8 AND lateral within 18.0 u AND the bearing to
  her within **21.35 deg of the HERD bearing**;
* `two_roll.alive` - `lead <= -2` (never overtake her *along the herd line*) and herd lateral <= 60;
* `full_herd._frontier_score` - leave the talk cone, then *hug the herd line*.

Measured at the banked cycle-1 exit, the pair is **58.91 u** apart - dead inside the human's own
recorded plow band of **40.4-85.2 u** - and passes the box on the herd axis. On `q` the same state
reads `lead -18.28`, `lat +56.00`, `delta +71.93 deg` and fails **all three** clauses. So what
refuses a q-ward push is only the direction assertion.

Freed to its coordinate-free content (the separation band alone, `l0` in place of "hug the line" in
the frontier), the same stage returns **21x more surviving rolls** and moves the frontier
**-136.00 -> -120.71** on a two-parent coarse screen. Real, but not the lever on its own.

## The lever was the CUT, not reachability

The stage's own screened population and what its beam keeps are two different things:

| | `l0` |
|---|---|
| cycle-1 exit (all 8 banked parents share her) | -286.88 |
| banked cycle-2 beam, as kept | **-263.83 .. -149.08** |
| screened population, 8 parents, 250 endpoints each | **-90.39** |
| screened with the `l0`-aware pool, one parent, 1000 endpoints | **-63.15** |

The bar is **-80.4**, and 26 of 737 rolls clear it. The gap was never mostly reachability - the
endpoints that cross were being screened out and then cut out. Two reasons, both structural:

* **the POOL is blind to the axis.** A real cycle-1 parent yields 4292 unique endpoints of which
  **250 (5.8%)** are ever roll-probed, chosen by a flatness prefix and a junction-frame spread.
* **the herd keeps refuse exactly the crossing endpoints.** The best-`l0` rolls ride **25-86 u off
  the push corridor** at a positive lateral (the winner: along 620.6, **lat +88.0**, off 86.2 u,
  jf 11), and `corridor_keep` / `align_keep` / `square_keep` rank on being square to the herd line.

Those keeps are not wrong - they are HERD constraints, and by the last two cycles there is no more
herding to do. See [the-handoff-along-was-already-spanned](the-handoff-along-was-already-spanned.md)
for the earlier form of the same question.

## End to end: the chain crosses, and the cage is what caps it

With the axis at all three cuts, cycle 3 parks her on the genuine side for the first time -- **6 of 8
endpoints `onside`, best `l0` +38.92 at 77 frames, all 6 admitting an entry curve**, where the same
chain previously returned `onside=False` and `gap=inf`. Best `bound` **100.06** = 77 herd + 120.00 u
of gap at the walk cap + 16 cut, against the banked console 101 and the
[s125 floor](the-crossing-and-the-runway-are-one-resource.md) of 94.

But read which ROUTE it found. The winners' last roll buys **+199.5 u in 29 frames** -- the deep-plow
regime, not the +80.4 band-keeping one -- so Link ends 120 u past the corner and owes the retreat.
Cycle 2 handed over **-160.62**, well under the -80.4 bar, and crossed anyway: **the bar is a
condition on the BAND-KEEPING crossing specifically**, not on crossing at all.

The band-keeping route is reachable at cycle 2 and then stops dead. Dropping `require_quality`
(`junction_quality` asking whether the next junction can still herd) takes cycle 2 to **`l0` -51.75
at 52 frames**, past the bar. Cycle 3 off those states returns **zero survivors, every child killed
`outbox` at generation 1** -- the junction never starts. And the reason is the direction assertion,
measured:

| cycle-2 state | `lead` | herd `lat` | `delta` | separation | in box |
|---|---|---|---|---|---|
| `l0` -51.75 | -41.87 | **-49.24** | **-49.63 deg** | 64.64 | False |
| `l0` -63.15 | -46.91 | **-35.51** | **-37.13 deg** | 58.84 | False |
| `l0` -160.62 | -58.19 | +9.55 | +9.32 deg | 58.97 | True |

Every one of them sits at a separation of **58.8-64.6 u -- dead centre in the human's own recorded
40.4-85.2 u plow band**. They are ordinary plow pairs. What disqualifies them is only that the
separation vector points 37-67 deg off the herd line, against a `max_lat` of 17.99 u and a
`max_delta` of 21.35 deg.

So the cage is not a safety margin the endgame is abusing; it is the herd-line assumption, and it is
what caps the plan at the plow-then-walk-back route.

## The general shape

**When the target changes shape, sweep the keeps that were calibrated to the old one.** The herd
stack was tuned over sessions 63-120 to park Tetra on a coord; sessions 123-125 replaced that with a
half-plane on a different axis, and every keep kept optimising the old objective for nine sessions
while the search reported that the crossing was out of reach. The axis was free to measure the whole
time - it is one dot product on a Tetra the rollout already produced.
