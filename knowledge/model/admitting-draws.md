# The density gap is acceptance, and it concentrates in a few draws

**Answers:** The run found 8 genuine where the arithmetic said hundreds - which factor lied? Why did
every near-razor row refuse? Can I know an item's yield without paying its ~7 h? How do I rank the
queue by something better than its frame floor? What can a one-minute probe miss?
**Status:** MEASURED (session 164) on s163's closed-loop console-w04 run - the one item whose genuine
plans are known - and gated in [`tests/test_yield_probe.py`](../../tests/test_yield_probe.py) (the
regime classifier + the banked rediscovery,
`fixtures/courtyard_yield_probe_console_w04.json`). Decomposes the density caveat
[fan-containment-gap.md](fan-containment-gap.md) carries; builds on
[entry-strip.md](entry-strip.md) (the strip and its gradient) and
[razor-zero-curve.md](razor-zero-curve.md) (one station is not a verdict).
**Source:** [`harness/tetrapush/yield_probe.py`](../../harness/tetrapush/yield_probe.py)
(`strip_seeds`, `gentle_brackets`, `draw_admittance`, `item_yield`).

---

## The funnel, measured where the answer is known

s163's console-w04 run, its own recorded stats (`_generated/overnight/s163-console-w04`):

| stage | rows |
|---|---|
| priced (5.61M at-cap candidates x 135 draws) | 757 553 040 |
| in contact (Co overlap >= 0) | 30 168 980 |
| in the overlap band | 5 427 187 |
| near the razor (\|resid\| < 1e-3, refused) | 11 081 |
| **genuine** | **8** |

The near rows are ~uniform in residual over the probe window, so the ~4e-05-wide genuine band
([genuine-residual-band.md](genuine-residual-band.md)) should hold **~200 rows - the arithmetic's
"hundreds" is roughly RIGHT about how many rows land on the strip.** What it omitted is the
acceptance: all 256 recorded near rows - one at \|resid\| **3.7e-07**, dead on the razor - refuse
``blocked`` (the swept lunge path hits the wall; 72 of them also fail ``crossed``, none fail
``in_front``), and the 8 that survive sit in **2 of the item's 135 (cell, thrust) draws** - (2551, 15)
and (2552, 15), both thrust 15. So:

    E[genuine] ~ (rows on the strip) x (the strip's ADMITTING fraction where those rows land)

and the second factor is ~4% here, concentrated per draw rather than spread thin everywhere.

## The entry-plane zero set mixes two regimes, and a blind Newton finds the wrong one

Locating the strip per draw hit the same trap [razor-zero-curve.md](razor-zero-curve.md) measured on
her plane, in a new form. The entry-plane ``resid = 0`` set is not one curve:

* **the strip**: gradient ~0.3-0.5 per u ([entry-strip.md](entry-strip.md)), genuine lives here;
* **discontinuity components**: gradient ~650 per u, the lateral profile swings +-50 within 2 u,
  the residual oscillates at its own quantum under Newton - and they are **never genuine**.

A Newton seeded blind converges to the nearest zero of either kind (measured: it sat down on a cliff
65 u from the known hit and reported nothing). The locate that works scans lateral profiles at several
depths across the contact window and keeps only **gentle zero-brackets** - both endpoints under
`GENTLE` - then refuses to walk from any point whose gradient reads past `CLIFF_MAG`. Outside the
contact window there is nothing to scan at all: the residual is the braced constant
([braced-cut-frame.md](braced-cut-frame.md)).

## The probe, and its own rediscovery gate

`yield_probe.item_yield` walks every located strip component of every draw, 1 u stations, and asks
the sweep's own genuine flag on a residual transect at each - ground truth at the item's frozen
Tetra, no band read, no her-plane scan. **~50 s for a whole item against the ~7 h the fan costs.**
At console-w04, derived leans (the herd's own roll lean +- the sampling spread):

| draw | stations | in reach |
|---|---|---|
| (2551, 15) | 23 | 7 |
| (2552, 15) | 19 | 7 |
| next best of 135 | 9 | <= 2 |

The top two by the ranking key are **exactly the two draws that produced all 8 genuine plans**, and
129 of 135 read zero. That concentration is what makes the score a scheduler: rank the re-run queue
by in-reach admitting stations, not only by frame floor.

## What a zero means here

``n_admit > 0`` is ground truth; **zero is a screen**. The probe samples 3 leans, 6 depth slices,
+-15 u of lateral, 20 stations an arc - a component crossing no sampled slice, or admitting only at
an unsampled lean, is invisible. Reach is `aimed_fan.MAX_STEP` x stepped frames from the herd
endpoint: admissible-generous, so "admits but none in reach" is a real verdict while "in reach"
alone does not promise the fan meets the station. **What bounds the real cloud depends on how the
herd ENDS**, and s164 paid one item run to learn it:

* a herd that ends at cap walks ~16.1-17.0 u a stepped frame and its kept leaves live on that thin
  annulus ([aiming-the-fan.md](aiming-the-fan.md); the console's shape);
* a herd that ends **mid-backslide** (31 of 46 do - the s162 census) burns frames converting, and
  its kept cloud is **conversion-limited**: rung05's walk-5 fan put its edge toward her at
  **74.1 u** where the raw full-stick rollout reads 94 and the annulus arithmetic promised 97-102.
  The probe's one in-reach station sat at 100.7 u - real (sim-genuine), but past the true edge -
  and the run returned 0 genuine with 6 in-contact rows out of 35.2M. The prediction failed on
  REACH, not on admittance. No stick-only walk ends at cap at all (the conversion needs the
  L-frame DIR_BACKWARD flip), so the kept edge cannot be read off a bare rollout: anchor it on a
  completed run's own `best_overlap_row` (the cloud's edge toward her) plus <=17 u a frame, or pay
  a small fan.

Stations INSIDE a conversion-limited cloud are the ones that count; a lone station at the edge is
the shape that just returned zero. Use the score to ORDER the ~7 h runs; never to declare an item
dead (`[[infeasible-needs-proof]]`).
