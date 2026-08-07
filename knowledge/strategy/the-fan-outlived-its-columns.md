# The fan outlived its columns: a measured table answers only the question it was measured for

**Answers:** My cheap predictor prices two halves of a candidate and one of them never seems to move -
is the term wrong, or is my TABLE missing it? What does `dict.get(key, default)` cost on a measured
record? A knob my library has had for eight sessions has never appeared in a result - how do I tell
"not worth it" from "not reachable"? My honest table is now 400x bigger and my screen cannot afford
it - do I coarsen the grid?
**Status:** MEASURED (session 119) on the flooded-Hyrule Tetra corner, over the session-111 cycle-3
beam. Drivers `_notes/s119_{fan,fan_cut,recut_c3}.py`, dumps
`_generated/s106/s119_{fan,c3_pair_landing,c3_arc_landing}.json`.
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`predict_bound`, `residual_fan`, `cloud_landing`, `_arc`, `ARC_STEP`/`ARC_HALF`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`,
`extend_cycle`'s ``cloud_exit_step``/``cloud_exit_half``). Gated in
[`tests/test_cloud_land.py`](../../tests/test_cloud_land.py).

---

[the-exit-bearing-buys-the-arrival](the-exit-bearing-buys-the-arrival.md) found 3 frames in an axis
the enumeration had never swept, and left the obvious next question: re-cut with that axis INSIDE the
cut instead of bolted on after it. Plumbing it turned up why no cut had ever seen it - and a second,
larger version of the same failure sitting under the first.

## The column that was not there

The per-aim screen (`full_herd.roll_probe`) prices a candidate through `cloud_land.predict_bound`
over a measured residual FAN. Since session 115 that prediction is JOINT: each fan member carries the
atom's **throw** - Link's own displacement - so the screen can place his arrival and charge the gap to
the row's stations.

The fan it was handed is `_generated/s106/s107_fan.json`, measured in session **107**, before the
throw existed. It carries the column on **0 of its 178 members**, and `predict_bound` read it as

```python
la = link[0] + m.get('throw_along', 0.0)      # absent measurement -> confident zero
```

So for sessions 115, 116 and 117 the joint screen placed Link's arrival **at the roll terminal** and
called that his arrival. That is not a small error in the direction of caution, and the previous
session had already measured its size without knowing it applied here:

| the same candidates | gap to the row's own stations | owes |
|---|---|---|
| at the roll TERMINAL (what the screen priced) | 67.6 - 106.7 u | 1.97 - 4.28 f |
| after the atom (where Link actually is) | 159.5 - 176.3 u | 7.38 - 8.37 f |

**The atom roughly doubles the gap**, and the screen was blind to the whole second half. Every cut
those sessions made chose its endpoints on that number. `predict_bound` now REFUSES a throw-less fan
in the joint branch, which is the module's oldest rule - unmeasured is not free - applied to the fan
the way it was already applied to a row with no hunted station.

## And the other axis could not be asked for at all

`exit_arc` has existed since session 110 and no enumeration had ever run it, for a duller reason than
anyone assumed: only `cloud_land.atom_cloud` took bearings. `cloud_landing`, `cloud_probe` and
`full_herd.extend_cycle` above it had no parameter to pass, so the axis was reachable only from a
one-off script. Eight sessions of results are the standing pair's, not a verdict on the arc.

The plumbed knob is an arc SPEC (``exit_step``/``exit_half``) and not the bearing list `atom_cloud`
takes, because the arc's centres are measured from **each endpoint's own position** - one list hoisted
to a beam sweeps a different axis at every endpoint and contains none of their controls.

## What a table that CAN answer costs

Re-measured at 6 firing endpoints of the beam being searched, with the throw, the tail and the arc:

| fan | members |
|---|---|
| `s107_fan.json` (no throw, no tail, standing pair) | 178 |
| standing pair, with throw and tails 0-6 | **7 668** |
| the same along the arc (26 bearings) | **75 627** |

The throw is two more dedup dimensions spanning ~500 u, so an honest fan is ~425x the table the screen
had been reading. At 116 rows that is 8.8M distances per surviving aim - **~10 s an aim**, where the
screen must cost milliseconds.

The reductions that first suggest themselves are all bad. Frame-dominance (same residual and throw
cell, keep the cheapest `n_atom`) is EXACT and removes **2%**. A coarser throw quantum is lossy and
barely works: 8 u - nearly half a frame of arrival resolution - buys only 2.7x.

**The one that works is the predictor's own arithmetic.** A member costs `n_atom` frames whatever it
lands, and both remaining terms are >= 0, so its best conceivable bound is
`frames + n_atom + min(plan_cost)`. Once an incumbent beats that, the member cannot be the minimum and
its entire row loop is skipped. Exact - it returns the identical record - and with `residual_fan`'s
cheap-members-first order it takes the full 75 627-member fan from ~10 s to **26 ms** an aim, ~380x,
so the cut can afford the honest table at full resolution. This is the harness's standing method (a
cheap monotone bound, a subtree prune, an exact confirm) turned on the predictor itself.

## What the fix bought, and where it stopped

Priced at the 64 endpoints the screen scores, the correction is real: the predicted bound moves
**-0.480 .. +2.814 frames** (mean +1.449), **53 of 64** endpoints change rank, and the row the
predictor quotes changes at **21 of 64**. Re-cut with it, cycle 3 comes out **byte-identical** to the
session-117 beam - all 64 nodes, every field, atom knobs included.

Both halves of that are the point, and the second one has its own page: the screen's minimum is pinned
to the cheapest atom in the fan, so it can neither be moved by the arc nor, here, by being made
correct - [the-cheapest-atom-owns-the-screen](the-cheapest-atom-owns-the-screen.md).

## The rule

**A measured table is an answer to the question it was measured for, and it will answer a different
one without complaining.** The failure is not the missing column - it is that `dict.get(key, default)`
is indistinguishable, at the call site, from a measurement that came back as `default`. A record that
predates the column being read is the same class of bug as a constant that predates the regime it is
quoted in, and it is harder to see because the table is real, the code is short, and the number it
returns is plausible.

Two habits catch it: make the reader REFUSE rather than default whenever the default is a claim about
physics, and check a dump's provenance against the fields it is being read for - a table measured in
session 107 cannot carry a column invented in 115.

The companion is [the-exit-bearing-buys-the-arrival](the-exit-bearing-buys-the-arrival.md)'s rule
about default grids: same disease at the other end of the same call. A grid's default decides what a
sweep can see; a table's missing column decides what a rank can price. Neither raises anything.

## Traps

- **A fan is not a landing table once an arrival is priced off it.** Adding the throw multiplies its
  size, and a fan that stays small after the column is added has probably dropped the column again.
- **Do not coarsen a grid to buy speed before checking whether the ranking function can prune.** The
  quantum here would have cost 0.24-0.47 frames of resolution for 2-3x; the exact prune gave 380x.
- **The prune's floor must come from the rows the branch may actually quote.** In the joint branch an
  unstationed row is skipped, so it may not lower the floor either - and an ineligible row must change
  neither the winner nor the pruning. Gated as that identity.
- **Re-running a pre-session-119 script verbatim now raises**, by design: `_notes/s11{0,1,7}_*recut*`
  hand `predict_bound` the throw-less fan. Their banked BEAM dumps are still valid records of what was
  run; the numbers their screens computed for the arrival half were not.

## See also

- [the-exit-bearing-buys-the-arrival.md](the-exit-bearing-buys-the-arrival.md) - the axis this page
  plumbs into the cut, and the terminal-vs-post-atom measurement that sizes the throw bug.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - why the arrival is priced at all.
- [landing-keep-on-a-cloud.md](landing-keep-on-a-cloud.md) - the predictor, the enumeration, and which
  of them is allowed to make a claim.
