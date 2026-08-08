# The fan is not a bound: a predictor measured elsewhere is pessimistic exactly where it matters

**Answers:** I fixed my screen's reduction and the ranking did not improve - what else is wrong? My
cheap predictor is documented as optimistic, is it? Can I prune on it? Why does my screen call 24 of
27 endpoints deliverable when the enumeration confirms 6? My beam keeps the wrong endpoints - is it
the beam's rank, the screen, or the budget?
**Status:** MEASURED (session 120) on the flooded-Hyrule Tetra corner, at the 27 firing endpoints of
the session-119 arc re-cut, against that run's own enumerated records. Drivers
`_notes/s120_screen_rank.py` and the session-119 run logs; dump
`_generated/s106/s120_screen_rank.json`.
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`predict_bound`, `residual_fan`, `cloud_landing`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`'s
``cloud_bound``, `extend_cycle`'s shares and ``cloud_cap``). Gated in
[`tests/test_cloud_land.py`](../../tests/test_cloud_land.py).

---

[minimise-subject-to-the-predicate](minimise-subject-to-the-predicate.md) built the reduction
[the-cheapest-atom-owns-the-screen](the-cheapest-atom-owns-the-screen.md) asked for: it sees the exit
arc, it has no false negatives, and it is 22x cheaper than the one it replaces. It still does not rank
deliverability - and the reason is not the reduction.

## The ranking, measured against the enumeration

Four of the beam's 64 endpoints hold a settled record, so their delivered figures are known:
**104.00, 106.13, 106.14, 111.52**. Where each reduction puts them (rank of 64, best-delivering
first):

| reduction | the 104.00 | the 106.13 | the 106.14 | the 111.52 |
|---|---|---|---|---|
| the standing global minimum | **27** | 16 | 17 | **15** |
| `band` | 21 | 24 | 25 | 16 |
| `band` + `owes_nothing` | 23 | 18 | 19 | 17 |

The standing screen ranks them nearly BACKWARDS - the worst deliverer highest, the best lowest - and
the corrected reductions move the best one from 27th to 21st, which is not a rank a keep can act on.
Restricted to the 27 endpoints that actually fire, the best deliverer sits 12th-15th under every
reduction. Whatever is wrong is not which minimum is taken.

## The predictor is not one-sided

`predict_bound` is documented as an optimistic proxy - a lower bound to the extent the fan is
reachable from the state being scored. Measured as `enumerated bound - predicted bound` at the 27
firing endpoints:

- the error spans **-0.93 .. +5.11 frames**, mean **+1.74**;
- it is **negative at 4 of 27** - the enumeration BEATS the prediction, so the proxy is not a bound;
- **3 of those 4 are deliverable endpoints**, i.e. the pessimism lands precisely on the endpoints
  worth keeping.

That is the mechanism behind the table above. An endpoint whose reachable variants are missing from
the fan is priced by the members the fan does hold, which are the ones some OTHER endpoint could
reach - so it is ranked below endpoints whose fiction happens to be flattering.

And the error is not correctable by the dependence `residual_fan` already documents. Spearman against
the endpoint's own offset from Tetra - the axis the residual is known to track at -0.53 u per u - is
**-0.135**, against `t_lat` **+0.418** and against the enumerated miss **+0.388**. There is no
one-parameter shift that turns this fan into that endpoint's fan.

The two cheaper explanations are both ruled out. The fan is measured on the SAME grid the keep
enumerates (`residual_fan` and `cloud_landing` share `atom_cloud`'s `flip_step`, rotate offsets,
`max_frames` and tails), so it is not a resolution mismatch. And its 1.0 u dedup cell is worth at most
`remaining_frames(1.0)` = **0.077 frames**, where the largest pessimism measured is **0.935** - 12x
the cell, i.e. 12.2 u of miss. What is left is the fan's SIX measurement endpoints, applied at 64
belonging to a different beam.

## Nor is the beam's rank the binding constraint

The obvious next fix - rank the last cycle on the DELIVERED field instead of on a short-atom bound -
is built (`full_herd.extend_cycle`'s ``delivered_keep``, off by default) and **cannot bite here**. The
session-119 arc run's own log settles it: over all 165 survivors the enumeration found **6 in-band and
2 joint**, and the 64-node beam it produced holds **exactly those 6 and those 2**. Every deliverable
survivor already reaches the beam, so no share of it can add one.

What the same log does say is that **69 of the 165 survivors were never enumerated at all** - the
cloud keep is capped by wall clock, and the cap keeps the cheapest 96 by admissible frame bound. So
the standing figures (in-band 6, best delivered 104.00) are properties of 58% of the population, and
the one measure that does make claims has never been run on the rest.

## The rule

**A cheap rank that was measured somewhere else is not a bound, and a cut may not prune on it.** Check
the sign of its error before treating it as optimistic: a proxy that is pessimistic anywhere can drop
the endpoint it is pessimistic about, and it will be pessimistic exactly where the population is
unlike the sample - which is where the interesting endpoints live.

The corollary for a cut whose screen cannot discriminate: stop paying for a better rank and spend the
budget on the measure that makes claims. When the exact keep can price a survivor in 9.2 s, leaving
69 of 165 unmeasured to protect a rank that ranks backwards is the wrong trade.

## Traps

- **"Optimistic by construction" is a claim about the model, not a measurement of the code.** It
  survived five sessions here and is false at 4 of 27 endpoints.
- **A screen with no false negatives can still be useless.** The banded reduction keeps every
  deliverable endpoint live - and 24 of the 27 firing ones besides, where 6 deliver.
- **Do not conclude a keep share is the fix without checking whether its cut is binding.** One line of
  an existing log answered it here, for free, after the share was already written.
- **A capped run's floor is the capped slice's.** The runs print it; read it as a live caveat on every
  number quoted from them, not as boilerplate.

## See also

- [minimise-subject-to-the-predicate.md](minimise-subject-to-the-predicate.md) - the reduction whose
  correctness this page does not dispute, and whose insufficiency it measures.
- [the-cheapest-atom-owns-the-screen.md](the-cheapest-atom-owns-the-screen.md) - the earlier layer of
  the same screen's blindness.
- [the-fan-outlived-its-columns.md](the-fan-outlived-its-columns.md) - the fan's other failure mode: a
  measured dump that predates the column being read off it.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - what "deliverable" means here, and
  why an in-band landing is only half of it.
