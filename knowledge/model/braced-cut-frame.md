# The wall brace pins the cut frame, so the razor has exactly one free variable

**Answers:** My razor search sweeps thousands of roll ENTRIES and its residual barely moves - is the
entry doing anything? Can I prefilter "out of contact at the cut" before paying for the roll? Why is
almost every row of a fan bit-identical to every other? If the entry is inert, what do I aim at
instead, and how accurately can I aim?
**Status:** MEASURED (session 157) on the flooded-Hyrule Tetra corner, at s154's accepted-101
configuration (cell 2545, thrust 15, lean 104) and against a real barren item's own 261 000 rows
(walk 8, thrust 13, off the s151 rediscovery herd). Gated in
[`tests/test_cut_contact.py`](../../tests/test_cut_contact.py) (9). It refutes the session-156 prefilter
recipe it was written to build (that recipe never reached a truth page - it lived in the run's own
handoff, and the refutation is below). Companion to
[required-cut-contact.md](required-cut-contact.md), which derives the same target analytically and
predicts it to 1.2 u - this measures it on the sim to 0.046 u - and to
[../mechanics/plow-ejection-equilibrium.md](../mechanics/plow-ejection-equilibrium.md), which is the
other half of the rigidity: the brace pins the PUSHER's cut frame, the ejection equilibrium pins how
close the PUSHED one ends up.
**Source:** [`harness/tetrapush/cut_contact.py`](../../harness/tetrapush/cut_contact.py)
(`braced_row`, `braced_invariance`, `cut_slice`, `zero_bearing`, `target_ring`).

---

## Inside the reachable entry box, an untouched roll has no freedom left

Sweep the roll entry over the box a plan can actually reach - `entry_search.reach_radius`, 94 u, four
walk frames plus the roll's own 26 u step - with the pushed actor parked out of contact, and count
DISTINCT results rather than differences:

| distinct bit patterns | over 169 entries in the reachable box | the same 169 at radius 400 u |
|------|--------------------------------------|----------------------------------|
| cut-frame `old` | **1** | 129 |
| Co centre on the contact step | **1** | 129 |
| `new` | **1** | 125 |
| residual | **1** | 129 |

One distinct bit pattern each. Every entry in the box drives the roll into the same courtyard wall and
the wall absorbs the difference: `CrrPos` returns Link to the same braced point whatever he started
from. Outside the box the roll no longer reaches the wall from every corner, and the rows separate - so
the invariance is a property of the REACHABLE BOX, not an artefact of the arithmetic.

Two things follow, and the second is what a planner needs.

**Out of contact, the entry does nothing at all.** Session 156 recorded "outside contact the razor's
residual is a dead constant" as an observation; this is its mechanism. Everything the entry buys a
search, it buys through the pushed actor - by changing WHEN the roll first reaches her, hence how many
frames of plow she gets, hence where she is standing on the frame the cut consumes.

**The bare roll-stab is one row per configuration.** At the accepted configuration it reads
`resid -0.8609402`, `push (0, 0)`, `genuine False` - the 0.33 u short landing this corner is known for,
now stated as a constant rather than a sample.

## The arithmetic free path is not the roll, and contact is not the prefilter

The session-156 handoff proposed predicting the cut step's position as `entry + sum(dx, dz)` and pruning
every candidate out of contact there. Both halves fail, measurably:

* that path ignores the wall correction, so it lands **255 u** past where the roll actually ends, and a
  contact test built on it keeps **0 of 2304** entries that are genuinely in contact;
* contact is not the rare thing. On a real item's rows, **99.3%** plow her 23-68 u and only **2.2%**
  end with any different cut-frame state at all, because the brace eats Link's half of the ejection.
  A prefilter would have to predict the 2.2%, and the necessary geometric condition for it - she is
  anywhere near the swept no-Tetra path, inflated by her own plow - keeps 94-100% of rows.

The saving is real: 97.8% of a fan's rows ARE one constant. It is simply not reachable through geometry.

## So the razor is a map over ONE 2-D variable: where she stands at the cut

With `old` pinned by the brace, the only input the cut frame still has is the pushed actor's position on
step `cut_step - 1` - the CC pair whose push the cut consumes. `ShoveCtx` already takes that variable:
`placed_step` puts her anywhere in the schedule, so placing her ON the contact step reads the razor
straight off the native sim at ~66 us a point, entry-invariantly, with no fan anywhere.

Along a bearing off the braced Co centre the residual is smooth and monotone through the grazing band -
it is the push that turns the ray, and the push is `share2 * (CO_R_SUM - dist)` along that bearing - so
one bisection per bearing gives the distance at which the cut ray crosses the seam vertex. Deep inside
the overlap it STEPS instead, and a blind bisection across the whole band converges on a discontinuity
and reports it as a target (measured: distance 34.93 at `resid` +20.5), which is why the scan comes
first and a refined crossing is kept only if its own residual is small.

At the accepted configuration, on the bearing the console's own herd used:

    ring distance   76.73543 u        where she actually stood   76.78111 u        aim error  0.046 u

## Read a ring point as an aim, never as a plan

The slice pins `old` at the braced value and a real plan's is not exactly that: the accepted 101 sits
**0.0127 u** off it, an earlier frame's push, which moves its residual by ~1e-02 - a hundred times the
razor's own width. So a ring point is good to ~5e-02 u, and the last 1e-04 is what the entry lattice is
for (`entry_dust` marches it, one f32 ULP at a time).
The ring says WHERE TO PUT HER; it never says a plan clips.

## What it prices, on the item that came back barren

The useful form of "how far is this herd from a clip" is her own radial position: `|resid|` divided by
`|d resid / d dist|`, both read off the sim. Over 261 000 rows of walk 8 / thrust 13 - all 55 cells,
6000 candidates:

| | closest row | median in-contact row | s154's delivered 101 |
|---|---|---|---|
| gap to the razor | **1.006 u** | 414 u | **7.7e-04 u** |

Nothing that item can build gets within a unit of where she has to be, while the plan that delivered
was three orders of magnitude closer. The far-field numbers are a local Newton step and not a distance -
quote the small ones. And her reachable set is not free either: the rows that reach contact at all are
the ones plowed into the wall, which pins her cut-frame `z` at -940.255615 for most of them, while the
delivered row stopped **0.36 u** short of that pin.
