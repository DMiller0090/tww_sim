# A landing in the band is half a candidate: delivery is two predicates

**Answers:** My plan lands the pushed actor inside the placement band at a winning total -- why is it
still not deliverable? What does a row's `plan_cost` silently assume about MY plan's arrival? Why does
`hull_scan` read `no leverage anywhere` at one arrival and leverage-everywhere-but-no-dust at another?
Which half of the predicate does each term track?
**Status:** MEASURED (session 109) on the flooded-Hyrule Tetra corner -- the s107 re-chain winner
(total 100, 0.789 u in-band) and the whole re-chain population, killed against the full predicate;
drivers `_notes/s109_{winner_cloud,control_diag,arrival_census,arrival_rank,scan_best}.py`, dumps
`_generated/s106/s109_*.json`.
**Source:** [`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py) (`hull_scan`,
`hull_field`), [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py)
(`cloud_landing` -- the half it prices), `_generated/s104/cost21_hunt_*.json` (the stations the rows'
costs were measured at).

## The two halves, and what tracks what

A deliverable candidate owes the razor two different positions at once:

- **The LANDING owes the dust.** Genuine solutions exist only where the pushed actor's rest position
  sits on the razor's genuine curve -- the rows band. Session 109 measured landings 24-40 u off the
  band: **zero genuine dust in every one of 45 aim cells x 3 thrusts**, even from a perfect arrival.
- **The ARRIVAL owes the leverage.** The stations the clip fires from sit **~130-165 u up-herd of the
  landing** (the roll+thrust is a ~205 u atom), so leverage -- the plowed actor still in Co range on
  the cut frame, the thing `hull_field` reports -- exists only if the plan's own walk hull covers that
  region. From the s107 winner's arrival (Link 128 u from the nearest station, his 2-frame hull ~20 u
  across and pointed down-herd): **leverage 0 at every grid point, all cells** -- while the identical
  call from the console arrival lights 4 live walkable stations (the control).

The failure is invisible to any landing-side score because a row's `plan_cost` is a price measured at
SOMEBODY'S arrival -- the s104/s105 hunts measured every station inside the walk cloud of the CONSOLE
arrival. Quoting that cost for a plan that arrives elsewhere is the s104 gotcha
([plan-cost-walk-budget](plan-cost-walk-budget.md)) one level up: `in_band` answers the landing's half
only, and "total = herd + atom + plan_cost" imports the other half from a different plan.

## The diagnostic split (reuse this shape)

One cross-scan run separates the halves in minutes (`_notes/s109_control_diag.py`):

| call | tetra | hulls | read |
|---|---|---|---|
| A control | the row's hunted placement | console arrival | **must light** or the scan is broken |
| B | the candidate's landing | console arrival | landing half alone (miss tolerance) |
| C | the row's hunted placement | candidate arrival | arrival half alone |

Session 109: A = 4 live, B = 1 live (a 0.789 u landing miss costs leverage, not the dust), C = 0
leverage -- the killer named in one table. `hull_scan`'s own counters give the same split per scan:
``n_leverage == 0`` is the ARRIVAL half refusing (the hull is in the wrong place); leverage without
``live`` is the LANDING half refusing (no genuine curve under the locus).

## Why the population could not pay both (and what can)

Over all 8581 firing atom variants at the s107 re-chain's 24 firing survivors, the (landing miss,
arrival-to-station) front is a hard exchange: **miss < 1 u only at d_station ~ 127 u; d_station < 10 u
only at miss ~ 25 u**. No variant carries both, because both are set by where the HERD ends: an atom
that lands her on the band ends Link beside her (deep, down-herd); an atom that ends Link at the
stations fires off a herd that has not finished pushing her.

The console's own delivered shape pays both at once, and says how: its herd log ends with the
untarget flip already flying (speedF -25.7), **Tetra coasts ~36 u down-herd on her own plow momentum
through the atom window** while Link runs up-herd at the 17 u/f cap, ending 111 u behind her and 25 u
from the station, walking at the cap (`iter_fan2` keeps junctions only at ``speedF == cap``, so an
arrival still mid-backslide fans an EMPTY cloud -- another way a "close" arrival can be worth
nothing). Frames that close the station gap are ordinary plan frames wherever they sit -- the atom's
exit-hold run and the entry plan's walk are the same currency -- so the budget identity is
``herd + atom-to-settled-arrival + walk + thrust + 4``, with the station gap payable at ~17 u/f only
while the landing stays put (after ``freeze_f`` she takes no more push; extending the exit run moves
the arrival and nothing else).

So the lever is a JOINT last-cycle keep: the landing keep
([landing-keep-on-a-cloud](landing-keep-on-a-cloud.md)) must price the arrival's station distance
beside the landing miss, and the chain must be allowed the console's geometry -- disengage early, let
her coast, spend the atom's tail running to the stations.
