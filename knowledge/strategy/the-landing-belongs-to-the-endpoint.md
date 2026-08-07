# The landing belongs to the herd endpoint, not to the escape

**Answers:** I have swept every knob the escape has and my landing barely moves -- is the atom a
steering channel at all? Why is my frame-minimal candidate's miss always LATERAL? What exactly does
the escape push her, and can I make it push less? Why is a shorter herd not simply a cheaper plan?
**Status:** MEASURED (session 111) on the flooded-Hyrule Tetra corner. Both bearing arcs swept at
FULL circle (32 flips x 32 exits x 4 rotates x turnaround x side x tails 0-6, ~115k variants) at the
session-107 re-chain's frame-minimal endpoints; the stick MAGNITUDE axis and a no-conversion
departure swept over all 54 beam nodes. Drivers `_notes/s111_{atom_reach,hold_atom,hold2}.py`, dumps
`_generated/s106/s111_*.json`.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`,
`fires`), [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`_centre_feet`, `CO_RADII_BAR`), [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`atom_cloud`, `exit_arc`).

## The escape is not a steering channel

Sessions 65-110 treated the escape atom as the last place with authority over Tetra, and searched it
accordingly: the flip arc, the rotate offsets, the turnaround, the exit bearing, then session 110's
exit ARC and tail. Widening those axes to the whole circle settles the question, and the answer is
that the authority was never there. At a herd endpoint the reachable landing set is a small blob
whose position is fixed by the endpoint, and every knob moves within it:

| endpoint (herd frames) | Tetra at exit | reachable landing after ANY departure |
|---|---|---|
| node 2 (68) | along 828.0, lat -17.6 | along 833-862, lat -26..-71 |
| node 4 (69) | along 840.8, lat -19.7 | along 860-958, lat **-30..-124** |
| node 7 (73) | along 923.8, lat -26.0 | along 923-933, lat **-35..-51** |

The lat **ceiling** is what binds. At every along band node 4 reaches, its best lateral sits 12-40 u
below the row cloud's floor there, so no atom lands it -- and the miss is not a rank, it is a reach.
The same sweep prices herd 68 out entirely: node 2's whole landing set tops out at along **862** and
[the row cloud starts at 880](herd-price-of-a-placement.md).

## Why: the plow's half-depth ejection, in Link's direction

The push is not something the escape chooses. On the first frame the dCcS write ejects her by half
the overlap deficit, `(CO_RADII_BAR - centre_feet)/2`
([plow-ejection-equilibrium](../mechanics/plow-ejection-equilibrium.md)), along the line from Link's exec centre -- and then by
as much again each frame he keeps closing. Measured over the beam, the minimum displacement any
departure achieves tracks that law: node 7 (`centre_feet` 62.5) has a predicted 8.74 u and a measured
floor of **9.02**; node 6 (66.8) 6.62 against 9.58. Where Link is still flying at the terminal the
first term is only the start -- the ratio of measured to half-depth rises with his approach rate,
from ~1.0 at `rec` -8..-12 to **2.3-3.2** at `rec` -25, i.e. 38-48 u of forced push at the deep
endpoints.

Its DIRECTION is Link's lateral offset from her, which is why the miss is lateral. The row cloud's
lat floor drifts only **-0.17 u per u** of along, while the push drags her lat-negative in proportion
to the offset. Node 4 sits at offset **+17.5** and needs ~40 u of along to reach the rows, which
costs ~20 u of lateral -- exactly its 21.75 u miss. Node 11 sits at offset **+3.9** and lands
0.80 u. Nothing else about the two endpoints explains that gap.

## So a frame-minimal plan is a specification on the ENDPOINT

The total is `herd + atom + plan_frames + thrust + 4`
([plan-cost-walk-budget](plan-cost-walk-budget.md)), the thrust floor of 13 is
[refused by this corner's geometry](../history/thrust-13-refused-by-geometry.md) so 14 is the real floor, and the
atom's own log is 4 frames at its shortest **settled** (below). A 95-frame plan therefore needs a
herd that

1. **exits a roll** at 69-71 frames -- mid-roll truncation does not fire
   ([session 105](herd-price-of-a-placement.md)), so the frame count is quantised by the cycle;
2. leaves Tetra where the endpoint's own forced push lands her **inside the cloud** (at node 4's
   depth that is along ~840 -> ~880, row 20);
3. **on-line**: `|Link lat - Tetra lat| ~ 0`, so that push is straight and her lateral survives it.

The session-107 beam contains no such endpoint. Its 68-69 frame nodes run 12.19 u/frame at offset
+14..+19; its on-line ones (node 10 at +1.78, node 11 at +3.91) are all at herd 73+. That is a
property of the cut, which has never ranked the exit along and the offset together.

## The no-conversion departure is cheap and undeliverable

Dereck's recipe converts (`L` + the held stick) before slamming, and session 110 asked whether an
atom that simply LEAVES -- the console's own shape -- would be cheaper. It is, in log length: holding
one bearing from frame 1 fires in **2-3 frames** where the recipe's shortest is 4, and it fires at
endpoints where the recipe fires nothing at all (nodes 6 and 8 read 0 firing over the entire
full-circle recipe grid, and 10-12k firing tail-variants over the hold grid).

It is still not a plan, and the reason is the other predicate: `entry_fan.iter_fan2` keeps an entry
junction only at `speedF == WALK_CAP`, and a departure that declines to convert **never settles**
inside 16 frames -- its shortest settled log is 11-16 frames against the conversion's 4-6. That is
what the L conversion is really for: it turns -25.7 into +17.6 in two frames, which is the fast route
to the cap. Sweeping stick MAGNITUDE (0.0 neutral through 1.0, an axis every previous enumeration
left pinned at full deflection) changes the forced push by less than 0.1 u -- the ejection is
instantaneous and depth-based, so a gentler stick does not buy a gentler plow.

## Watch out

- **The atom rolls out on a DETACHED camera.** `away_walk._clone_for_atom` detaches so `csangle` can
  be commanded; a wired replay of the same log drifts 121-654 BAM from it and re-quantises every
  stick. Measured on the recipe atom: **0.008-0.080 u** on Tetra and **0.75-2.00 u** on Link, against
  a razor band of ~1e-4. Quote a landing from the REPLAY, never from the rollout.
- **`stations 0` is three findings**; `hull_scan` returns `reason` and `drops`
  (`no_leverage`/`no_zero`/`outside`) and every scan before session 111 discarded them
  ([clip-station-reachability](clip-station-reachability.md)). `outside` dominating is an ARRIVAL
  problem; `no_zero` dominating is a LANDING problem, and they need opposite work.
- **Do not re-sweep the atom for a better landing.** Full circle on both bearings, all four rotate
  offsets, both sides, both turnaround choices, tails 0-6 and the whole magnitude axis are done, at
  the frame-minimal endpoints and at the herd-73 ones. The lever is upstream.
