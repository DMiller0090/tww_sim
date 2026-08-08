# The dip budget is not the lever: every dip-only refusal sits at an endpoint that already fires

**Answers:** `dips` is the last unmeasured clause - is it worth a session? Would raising `DIP_BUDGET`
revive the endpoints that fire nothing? What does Dereck's bar cost in frames? Which clause actually
refuses the dead half of the cycle-3 beam? Is "no upstream knob buys a dip back" measured?
**Status:** MEASURED (session 121) on the flooded-Hyrule Tetra corner, over all **402661** escape
variants at the **99** endpoints of the UNCAPPED cycle-3 census - the whole enumerated population, not
a beam slice. Driver `_notes/s121_dips_census.py` (347 s at 5 procs), log
`_notes/s121_dips_uncapped.log`, dump `_generated/s106/s121_dips_census_uncapped.json`. Run first on
the 64-node session-119 pair beam (`s121_dips_census.json`); every conclusion below holds on both and
the population is quoted, because a finding about a slice is what this session spent its day
disproving.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`DIP_BUDGET`,
`WALK_FLOOR`, `escape_atom`'s ``dips``, `fires`, `FIRES_CLAUSES`, `fires_census`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`lok_probe_key`,
`extend_cycle`'s ``tcs_escape``).

---

A dip is a post-separation frame whose ground displacement is under `WALK_FLOOR` before Link is
receding at the cap. `DIP_BUDGET` = 3 is documented as **Dereck's bar** - a quality bar, not a
physical threshold - and ``dips`` was the last of `fires`' five clauses nobody had measured. Sessions
112 and 116 established what it is not (no camera state fixes it; it is the clause left standing at
the rolls with no clearing target) and concluded from that it is "the recipe's own shape and no
upstream knob buys them back". That is a claim about a model. Measured, the bar is real and it is not
a lever.

## Every variant the budget alone refuses is at an endpoint that already fires

Over the population's 402661 variants the bar refuses a large share and revives nothing:

| budget | variants failing nothing but the budget | vs the bar |
|---|---|---|
| **3** (the bar) | 102463 | - |
| 4 | 110814 | +8351 |
| 5 | 127598 | +25135 |
| 8 | 133041 | +30578 |
| 14 (all of them) | 142130 | **+39667** |

That +39667 is a **+38.7%** supply increase, and it is exactly `sole['dips']` counted over the whole
population - the two are the same variants, which is the arithmetic check that the table means what it
says. The decisive fact is where they sit:

- **53 of the 99 endpoints fire nothing at the bar, and 0 of them fire at ANY budget** (14 IS the
  largest dip count observed, so the last row is the whole axis and not a sample of it).
- At those 53, over their 200038 variants, ``dips`` is the sole refusal on **0**.

So on this population the dip budget cannot revive an endpoint. It can only add variants to endpoints that
already have some, which is the one thing a cut short of *endpoints* does not need. The mechanism is
in the next section and it is not subtle: at every dead endpoint another clause refuses everything, so
no budget on this one can be reached.

## What refuses the dead half is the camera, and its keep is already on

At the same 53 dead endpoints:

| clause | fails | SOLE |
|---|---|---|
| `l_ok` | **200038** (all of them) | **55754** |
| `dips` | 143805 | 0 |
| `no_follow` | 24679 | 0 |
| `separates` | 465 | 0 |
| `recedes_at_cap` | 452 | 0 |

`l_ok` fails on **every variant at every dead endpoint** (all 53 of them, not merely most), and on
55754 it is the ONLY failure - each of those fires the moment the camera clears. ``dips`` co-occurs
massively (72%) and is never the last clause standing, which is how it can be true both that dips
refuses most of the census and that fixing it is worth nothing.

The caveat that keeps this honest: `atom_cloud` runs every variant at the arrival's **own** camera
(``csangle='live'``, session 73's honest default), so this is the refusal at the camera each endpoint
arrived with. That is not a gap in the measurement - it is the measurement. `extend_cycle` already
runs with ``tcs_escape=True``, so `lok_probe_key` was an active keep share in the very cut that
produced this population, and 53 of its 99 endpoints still arrive at a camera that refuses
everything. A share is not authority over which endpoints are kept.

`lok_clear` run at all 99 arrivals separates the population almost perfectly:

| | clears the cone at its own camera | cone margin (deg, + = outside) |
|---|---|---|
| the 46 endpoints that fire | **45** | -9.8 .. +85.9, median **+41.0** |
| the 53 that fire nothing | **0** | -88.2 .. **-1.7**, median -48.0 |

One clause, one camera, and the population splits 45/46 against 0/53. As a predictor of "this endpoint
fires" `lok_clear` is exact but for a single conservative miss: **1 false negative, 0 false
positives** (one endpoint reads clear=False at -9.8 deg and still fires, because `atom_cloud` sweeps
flip/rotate/exit knobs that move the cone where `lok_clear`'s one two-step rollout does not). It never
calls a dead endpoint clear.

And the dead endpoints are not far outside: nodes 81 and 92 miss by **1.72** and **1.74 deg**, node 71
by 5.63, node 59 by 7.63, node 78 by 9.06. Five of the fifty-three are within ten degrees of the
clause that refuses all 200038 of their variants.

## What the bar costs, read at held push

Frames alone is the wrong comparison and the first pass of the driver made that mistake: the cheapest
``freeze_f`` is 2 in every class at every budget, which reads as "the bar costs nothing" and means no
such thing. An atom separates early precisely BECAUSE it pushed less, and the frames it saves come
back as herd frames elsewhere.

Read at held push - per class, the most along-push reachable at each separation frame, the gap
converted at the herd rate 12.8177 u/f `_notes/s112_honest_surface.py` measured over these same cycle-3
nodes - **27 of 99 endpoints hold a dip-refused variant that beats every firing one**:

| endpoint | at freeze_f | bar caps push at | refused variant reaches | worth |
|---|---|---|---|---|
| node 32 (herd 76, offset +7.06) | 11 | 69.600 u | 82.911 u | **1.04 f** |
| node 19 (herd 73, offset +33.66) | 8 | 38.362 u | 48.340 u | 0.78 f |
| node 14 (herd 72, offset -4.14) | 11 | 71.510 u | 79.892 u | 0.65 f |
| node 13 (herd 73, offset +9.63) | 9 | 60.173 u | 67.915 u | 0.60 f |

Node 13 is the endpoint the census delivers 105.00 from. The best win anywhere is **1.04 frames** and
the tail falls under 0.25.

**That figure is the reason to measure the population and not a beam.** On the 64-node session-119
beam the same driver returns a maximum of **0.78** frames, and the conclusion drawn from it - "relaxing
the bar cannot buy a whole frame at any single endpoint" - is false on the full population by a node
the beam does not contain. The KIND of answer does not change (0 endpoints revived on either), but the
one quantity anybody would quote does.

## The rule

**A clause that refuses a majority of variants is not thereby a lever.** What decides whether an axis
is worth a session is not how much it refuses but whether it is ever the LAST clause standing: a
refusal that only ever co-occurs can be removed entirely without any endpoint changing state. Count
`sole`, not `fail` - `fires_census` has had the column since session 77.

The corollary for the bar itself: `DIP_BUDGET` is Dereck's and this page does not propose moving it.
It prices it. The price is **1.04 frames** at the one endpoint where it is largest, under 0.25 at
most of the rest, and zero endpoints anywhere.

Where the axis goes instead: the dead half of this population is a **camera** problem and nothing else
- 0 of 53 clear the cone, 55754 of their variants fail `l_ok` alone, and the nearest miss is 1.7
degrees. That axis is not untouched - `lok_probe_key` was added in session 116 and A/B re-cut in
session 117, which moved the firing count **21 -> 27** with the best bound unchanged at **93.95**
([the-camera-supplies-the-cone](the-camera-supplies-the-cone.md)). What this page changes is the
argument for its SHAPE. Session 116 made it a share and not a requirement on two grounds: a camera
filter throws away firing states, and "the other half of the census is ``dips``, which no camera
fixes". The first stands. The second is measured false - dips decides no endpoint - so the only
remaining reason to let a refusing camera into the beam at all is the first one, and it is worth
re-testing against a population where 53 of 99 endpoints can never end a plan.

## Traps

- **A short atom is not a cheap atom.** Comparing separation frames without holding push constant
  reports that the bar is free. Hold `resid_along` and the cost becomes visible - and stays small.
- **"No upstream knob buys it back" is a claim about the recipe.** It is true of the dip count and
  irrelevant to the search, because the dip count never decides an endpoint.
- **A keep share being wired is not the same as it binding.** `lok_probe_key` has been on since
  session 116 and 53 of 99 endpoints still arrive at a refusing camera.

## See also

- [the-camera-supplies-the-cone.md](the-camera-supplies-the-cone.md) - the `l_ok` clause this page
  hands the axis back to, and the supply measured for it.
- [the-fan-is-not-a-bound.md](the-fan-is-not-a-bound.md) - the same session-120 discipline applied to
  the screen: check a claim about a model against the code.
- [the-screen-is-not-the-rank.md](the-screen-is-not-the-rank.md) - why an exact binary screen can
  still supply no ordering.
