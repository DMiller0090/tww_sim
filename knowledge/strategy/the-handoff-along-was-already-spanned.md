# The handoff along was already spanned: attribute the population before re-cutting its parent

**Answers:** My last cycle's endpoints all land PAST the target - should I re-cut the cycle before it
to hand off earlier? How do I test an upstream re-cut before paying an hour for it? Why is my arrival
free at one endpoint and 140 u away at another 46 u down-line? What does landing nearer the target
actually buy?
**Status:** MEASURED (session 123) on the flooded-Hyrule Tetra corner, off the banked dumps alone -
the session-122 requirement lane (63 terminals), the session-119 pair lane (64) and the session-120
uncapped census (99), all attributed to the session-107 cycle-2 beam
(`_generated/s106/s107_rechain_c2_beam.json`, 16 nodes). Driver `_notes/s123_c2_preflight.py map`
(seconds, no cut).
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`extend_cycle`'s ``arrive_keep``/``target_along``, `roll_probe`'s ``arrive``/``over``/``along``),
[`harness/tetrapush/beam_io.py`](../../harness/tetrapush/beam_io.py) (`rebuild_beam`),
[`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`arrival_frames`,
`station_gap`, `FREE_REACH`), [`harness/tetrapush/aim.py`](../../harness/tetrapush/aim.py)
(`handoff_target`).

---

[the-shape-of-a-cut-is-not-its-answer.md](the-shape-of-a-cut-is-not-its-answer.md) closed the last
cycle to re-cutting: three cuts over disjoint populations all return **105.00** at the same endpoint,
so the remaining frames are a property of where the endpoint set SITS. The reading that followed was
that the set sits too far down-line - cycle-3 endpoints at along **918-971** against a
`aim.handoff_target` of **876**, and a FRONT_ROLL is a ~205 u atom that cannot stop short - so the
next lever was one cycle up: re-cut cycle 2 to hand off 40-90 u earlier.

That is wrong, and the dumps already said so. This page is the three-minute measurement that answers
an upstream re-cut without running one, and what it found instead.

## The range that motivated the re-cut was one branch of the tree

**A node's parent is recoverable exactly: its cycle-2 log is a PREFIX of the terminal's log.** (Keyed
on the log, never on geometry - a node index is a rank and geometry twins exist, [the census's
identity rule][census].) Attributed that way, all three banked cycle-3 beams descend from just **6 of
the 16** cycle-2 nodes, and the along ranges are:

| terminals | population | probed / firing | descending from c2 nodes 8+9 |
|---|---|---|---|
| requirement lane (63) | 827.99 - 984.25 | 827.99 - 970.90 | **918.85 - 984.25** (34 of 63) |
| pair lane (64) | 827.99 - 980.22 | 827.99 - 956.44 | 918.85 - 980.22 (28 of 64) |
| uncapped census (99) | 827.99 - 984.25 | 827.99 - 984.25 | 918.85 - 984.25 |

"918-971" is the c2-8/9 BRANCH, not the population. The population brackets the target: **6 terminals
land SHORT of 876** - all six firing in the requirement lane, three of six in the pair lane.

## Cycle 2 already exits at the along that lands cycle 3 on the target

One more cycle adds ``dalong`` = terminal along - its parent's exit along. It is not a constant - it
is the junction's own length, which is the adjustable part - and per parent its MINIMUM is:

| c2 node | 15 | 1 | 8 | 0 | 9 | 5 |
|---|---|---|---|---|---|---|
| exit along | 569.82 | 579.19 | 616.34 | 579.19 | 616.31 | 603.12 |
| min ``dalong`` | +258.17 | +298.69 | +302.51 | +307.63 | +317.95 | +344.28 |
| nearest terminal | **827.99** | **877.88** | 918.85 | **886.82** | 934.26 | 947.40 |

The banked cycle-2 beam exits between **569.82 and 616.34**, and nodes 0/1 at 579.19 already deliver
terminals at 877.88 and 886.82 - **on** the 876 target. Node 15 at 569.82 delivers 827.99, 48 u SHORT
of it. So the ask "hand off 40-90 u earlier" is not just unbinding, it points the wrong way: the
earlier exit the population already contains is the one that undershoots.

The cycle-3 cut was never blind here either - it ran with ``arrive_keep=True, target_along=876``. The
along axis is spanned, kept for, and its endpoints are enumerated.

## What landing near the target actually buys: a trade, and the trade is the arrival

The requirement lane's own firing terminals under along 905, with the node's floor record beside its
station gap ([the two predicates](delivery-is-two-predicates.md)):

| along | nodes | `total` | best miss (u) | `n_atom` | `d_station` (u) | `arrival_frames` |
|---|---|---|---|---|---|---|
| 827.99 | 3 | 91-92 | 36.8 - 40.0 | 3-4 | **19.7 - 32.2** | **0.00** |
| 840.78 | 3 | 92-93 | 25.4 - 27.8 | 3-4 | **23.4 - 38.7** | **0.00 - 0.27** |
| 877.88 | 3 | 92-94 | 8.5 - 17.6 | 3-4 | 124.3 - 126.7 | 5.31 - 5.45 |
| 886.82 | 3 | 92 | **4.7 - 5.2** | 2 | 136.8 - 141.4 | 6.05 - 6.32 |
| 897.04 | 2 | 97 | 15.8 - 18.9 | 7 | 45.3 - 51.5 | 0.66 - 1.03 |
| 934.26 (the winner) | 1 | 101 | 3.0 | 7 | 45.2 | 0.66 |

Reading down the miss column, landing nearer the target is exactly what a plan wants: **4.7 u at
886.82 against 38.3 u at 827.99**, on a herd two frames cheaper than the winner's. Reading down the
arrival column, it is exactly what a plan cannot pay: the same move costs **6.3 frames** of station
gap. That is [the offset's exchange][offset] on the OTHER axis.

**And the exchange is a fact about the room, not about this beam.** All **268** stations over the 116
rows lie in ONE cluster at along **804.70-818.69**, lateral **+12.12..+35.46**, while the rows
themselves run along **879.92-979.86** at lateral -33.68..+1.61: every row sits **72.3-162.6 u
down-line** of its own stations (median 110.6). So landing Tetra ON a row necessarily leaves Link
down-line of the only place he may fire from, and the column above is not monotone in the along at all
- it tracks where the herd left Link and how far the atom carries him (over the firing terminals,
corr(``sep``, `d_station`) is **-0.697** and corr(`n_atom`, `d_station`) **-0.489**;
[the separation page](the-separation-is-not-a-suffix.md) prices that). A 2-4 frame atom keeps
whatever the herd left (free at 828-841, where the
endpoint is still beside the cluster; 124-141 u at 877-887, where it is not), and the gap only closes
again at atom 7+, when the throw has opened enough to curve him back
([the-short-atom-is-a-point.md](the-short-atom-is-a-point.md)). The winner pays that: its `joint`
record runs an **11**-frame atom to reach `d_station` 29.2.

The population's whole answer follows from that column. By band, over the requirement lane:

| along band | terminals | fire | in-band | deliver | best delivered |
|---|---|---|---|---|---|
| under 876 | 6 | 6 | 0 | 0 | - |
| 876 - 900 | 8 | 8 | 3 | 1 | 106.66 |
| 900 - 925 | 7 | 7 | 0 | 0 | - |
| 925 - 950 | 25 | 22 | 3 | 3 | **105.00** |
| over 950 | 17 | 7 | 0 | 0 | - |

The near-target band delivers **106.66** - a `total` of **99**, two frames under the banked plan, with
**7.66** frames of arrival on top. The winner delivers 105.00 the other way round: a `total` of
**105** and an arrival of **zero**, its `joint` variant spending an 11-frame atom to put Link 29.2 u
from a station, inside `FREE_REACH`. Moving the handoff onto the target buys the landing and sells the
arrival at a worse rate than it buys.

## The rule: attribute the population to its parents before re-cutting a parent

An upstream re-cut is the most expensive move a chained search has - here cycles 2+3 are ~1 hour - and
the question it answers is nearly always already in the dumps. The measurement costs minutes and needs
no simulator beyond a beam rebuild:

1. **Attribute every terminal to its parent by input-log prefix.** Exact, and it survives geometry
   twins.
2. **Read the per-parent transfer** of whatever quantity you want to move. If it varies by parent it
   is not a constant offset you can shift the whole beam by.
3. **Check the population's RANGE, not the deliverers' range.** A statistic quoted off the winners is
   a statistic about the rank, and the branch that wins is not the branch that spans.
4. **Then ask what the quantity BUYS.** A range that is already spanned turns "move it" into "price
   it", which is a different session.

The generalisation of [the shape rule][shape]: a cut whose answer survives a change of population is
telling you about the set. Re-cutting the cycle that FEEDS that set is still a cut - and it only pays
if the set's spread on the axis you are moving is narrower than the move.

[census]: the-dip-budget-is-not-the-lever.md
[offset]: the-offset-cannot-pay-both.md
[shape]: the-shape-of-a-cut-is-not-its-answer.md

## See also

- [the-offset-cannot-pay-both.md](the-offset-cannot-pay-both.md) - the same exchange read on Link's
  LATERAL offset, with the relocation beds that price it.
- [the-exit-bearing-buys-the-arrival.md](the-exit-bearing-buys-the-arrival.md) - the one knob measured
  to move the arrival half, and what it is worth at this population.
- [the-short-atom-is-a-point.md](the-short-atom-is-a-point.md) - why that knob is worth nothing until
  the atom is 8 frames long, which is what pins the exchange.
- [herd-price-of-a-placement.md](herd-price-of-a-placement.md) - what a herd frame is worth in along,
  and the banked 101 the figures above are read against.
