# Minimise subject to the predicate, don't trade against it - and index the rows so you can afford to

**Answers:** My cheap screen and my exact keep rank the same candidates differently - which term is
doing it? How do I predict "the cheapest variant that LANDS" rather than "the cheapest variant"? A
predicate has no incumbent to prune against, so is a banded search always the slow one? What does a
length restriction fix that a predicate does not, and the other way round?
**Status:** MEASURED (session 120) on the flooded-Hyrule Tetra corner, at all 64 endpoints of the
session-119 arc re-cut, against that run's own enumerated records. Drivers
`_notes/s120_screen_keys.py` (the per-length vectors) and `_notes/s120_screen_rank.py` (the shipped
reductions); dumps `_generated/s106/s120_screen_{keys,rank}.json`.
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`predict_bound`'s ``atom_min`` / ``by_atom`` / ``band`` / ``owes_nothing``, `_band_index`,
`delivered`). Gated in [`tests/test_cloud_land.py`](../../tests/test_cloud_land.py).

---

[the-cheapest-atom-owns-the-screen](the-cheapest-atom-owns-the-screen.md) measured that
`predict_bound`'s minimum sits on an `n_atom` = 3 member at 64 of 64 endpoints, so any knob paying
after frame 6 is invisible to it, and closed with: the screen needed a different QUESTION, not a
bigger table. This is the question, and what each version of it is worth.

## Two different failures, two different fixes

The screen's bound is `frames + n_atom + plan_cost + remaining(miss) + arrival_frames(gap)`; the
keep's ``in_band`` / ``joint`` are min-TOTAL among variants that SATISFY a predicate. The gap between
them is two independent things, and they do not fix each other:

| | what it is | what it corrects |
|---|---|---|
| ``atom_min`` / ``by_atom`` | the same minimum over members of at least length K, or the whole per-length vector | the predicted **VALUE** |
| ``band`` / ``owes_nothing`` | minimise subject to `miss <= band` (and to owing nothing on the arrival) | the **QUESTION** - it predicts the field the objective is denominated in |

Measured at the beam's best-delivering endpoint, whose enumerated delivered figure is **104.00**:

| reduction | predicts | error |
|---|---|---|
| the standing global minimum | 100.93 | **-3.07** |
| `k>=9` | 103.07 | -0.93 |
| `k>=10` | **104.05** | **+0.05** |
| `band` | 102.15 | -1.85 |
| `band` + `owes_nothing` | 103.07 | -0.93 |

A length restriction alone recovers the value almost exactly - which is the direct confirmation of
the earlier page's mechanism, since the whole error was the 7 frames of atom the minimum refused to
spend.

## The predicate is not the expensive one - if you index the rows

A predicate has no incumbent for the arithmetic prune (`frames + n_atom + min(plan_cost)`) to bite on
until it finds its first satisfying member, so the obvious implementation degrades to the whole fan
by the whole row list: ~10 s per aim on the shipped 75 627-member fan, where a screen must cost
milliseconds. But a banded search does not need every row. Only a row within `band` of the predicted
landing can be quoted at all, so bucket the rows on a `band`-wide grid and look at the 9 cells around
each landing (`_band_index`). Measured per call on the full arc fan:

| | the global minimum | `band` | `band` + `owes_nothing` |
|---|---|---|---|
| mean cost per call | **3189 ms** | **128 ms** | **147 ms** |

The predicated reduction is **~22x cheaper than the reduction it replaces**, because the index makes
its inner loop O(1) in the rows while the unpredicated minimum still pays the full row scan on every
member it cannot prune. It is exact rather than approximate - gated as an identity against the
brute-force banded scan, including rows placed at the cell boundary and at the band's own radius.

## What it buys, and what it does not

- It **sees the arc**: pair -> arc moves the banded key by **-1.443 .. 0** (33 of 64 ranks) and the
  joint-banded key by **-7.028 .. 0**, where the global key measured `+0.000 at 64 of 64`.
- It has **no false negatives**: all 6 endpoints the enumeration proved in-band are live under it.
- It **returns None**, which the unpredicated call cannot: 23 of 64 endpoints have no member landing
  in band at any length. A screen that can say "not here" is a screen.
- It does **not** fix the RANK. That is [the-fan-is-not-a-bound](the-fan-is-not-a-bound.md), and it is
  the reason this page stops at "what the reduction is worth" instead of claiming a better cut.

## The rule

When a cheap rank and an exact rank disagree, ask first whether they are answering the same QUESTION.
A trade (`+ remaining(miss)`) and a predicate (`miss <= band`) are different questions, and no budget
spent on the trade converges to the predicate's answer - a screen that prices a 20 u miss at 1.7
frames will keep choosing the variant that does not land, forever, however finely it is measured.

And when the predicate looks unaffordable, check whether it also makes the search SMALLER. A
constraint that bounds a distance is a spatial index waiting to be used; here it turned the
supposedly expensive reduction into the cheap one.

## Traps

- **`owes_nothing` without stations is a refusal, not a default.** It is a claim about the arrival
  half, and a call with no station map has no way to price it (`station_map`'s standing rule).
- **A predicate at the fan's own resolution is at the edge of what the fan can resolve.** The fan
  dedups on a 1.0 u quantum and `objective.PLACEMENT_BAND` is 1.0 u, so the banded key is a screen and
  never a claim - the enumeration still makes the claim (`landing-keep-on-a-cloud.md`).
- **Do not measure a candidate reduction on a proxy for it.** The first pass here applied the
  predicate to each length's own bound-minimising record rather than to every (member, row) pair;
  it ranked the deliverable endpoints 7th / 14th / 15th / 26th, and the SHIPPED reduction ranks them
  21st / 24th / 25th / 16th. The proxy was accidentally stricter, and believing it would have shipped
  a rank that does not exist.

## See also

- [the-cheapest-atom-owns-the-screen.md](the-cheapest-atom-owns-the-screen.md) - the blindness this
  page is the answer to, and the argmin-on-the-charged-axis diagnostic that found it.
- [the-fan-is-not-a-bound.md](the-fan-is-not-a-bound.md) - why the corrected reduction still does not
  rank deliverability, measured at the same endpoints.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - the two predicates `band` and
  `owes_nothing` are the cheap forms of.
- [landing-keep-on-a-cloud.md](landing-keep-on-a-cloud.md) - the screen/keep division of labour.
