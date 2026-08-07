# One offset, two predicates: straight is long, and the stations are on the other side

**Answers:** Why does making the escape's push STRAIGHT cost me atom frames? Why is my arrival free at
a crooked endpoint and unpayable at an on-line one? What offset should the last cycle actually aim
for? My cut finally produced the on-line endpoints I asked for and they all read `nofire` -- is that
the knob grid or the physics?
**Status:** MEASURED (session 112) on the flooded-Hyrule Tetra corner, against the session-111
cycle-3 beam (`_generated/s106/s111_c3_{beam,landing}.json`, 64 nodes, 21 firing) and controlled
relocation beds at its frame-minimal endpoints. Drivers `_notes/s112_{offset_c3,place_curve,
atom_front,honest_surface,nofire_probe}.py`.
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`exit_arc`,
`atom_cloud`, `station_map`, `arrival_frames`),
[`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`, `fires`,
`fires_census`), [`harness/tetrapush/objective.py`](../../harness/tetrapush/objective.py)
(`PUSH_CEILING`, `PLACEMENT_BAND`).

---

[the-landing-belongs-to-the-endpoint.md](the-landing-belongs-to-the-endpoint.md) ends on a
specification: exit the last roll at 69-71 frames with Link **on-line** (`|Link lat - Tetra lat| ~ 0`)
so the forced push is straight and lands her inside the row cloud. The specification is right about
the landing and it is not free, which is what this page measures. Link's lateral offset from Tetra is
a SINGLE variable that both halves of the delivery predicate
([delivery-is-two-predicates.md](delivery-is-two-predicates.md)) read, they want it in different
places, and moving it toward either one is paid for in the currency the plan is trying to save.

## Straight and short are the same knob, not two axes

Hold one real endpoint and move only Link laterally (the
[the-landing-belongs-to-the-endpoint.md](the-landing-belongs-to-the-endpoint.md) relocation bed). At
cycle-3 node 0 -- herd 69, Tetra at along 840.78 lat -19.69, native offset **+17.49**, `centre_feet`
51.48 -- the push straightens exactly as that page says, the residual's lateral tracking the offset at
**-0.53 u per u** (`away_walk.probe`'s own slope: -10.34 at +17.49 through +5.63 at -12.51):

| offset | +17.49 (native) | +9.99 | +4.99 | -0.01 | -7.51 | -12.51 |
|---|---|---|---|---|---|---|
| residual (along, lat) | (20.90, -10.34) | (32.74, -12.91) | (31.91, -7.58) | (36.68, -5.14) | (43.74, +0.46) | (47.69, +5.63) |
| best-bound miss (u) | 25.400 | 18.314 | 16.793 | 12.290 | **2.016** | 5.809 |
| its atom log (frames) | **3** | 4 | 5 | 6 | **7** | 7 |

The miss collapses and the frames it collapses into are the whole saving. This is mechanical, not
incidental: the atom ends when the actors **separate** (`away_walk.fires`), an on-line Link is
directly behind her and keeps closing, so separation arrives later. At the same posture shifted 10 u
down-line, the SHORTEST firing log at offset -7.51 is **7 frames** over the standing exit pair and
**6** over a wide exit arc -- against **3** at the native +17.49. Straightening the push buys the
landing with 3-4 atom frames.

## The stations sit on the OTHER side of the herd line

The arrival half is priced against the live stations each row's `plan_cost` was measured at
(`cloud_land.station_map`). All **268** stations over the 116 rows lie at along **804.70-818.69**,
lateral **+12.12..+35.46**, while the rows themselves run along 879.9-979.9 at lateral -33.7..+1.6 --
the six cost-20 rows sit **73.1-137.3 u** down-line of their own stations and **31-46 u** across the
line from them. So Link has to finish on the POSITIVE-lateral side while a straight push needs him at
Tetra's lateral, which on the frame-minimal band is -13 to -20.

Measured across the 21 firing nodes of the session-111 cycle-3 beam, that reads as a narrow payable
window in the endpoint offset:

| endpoint offset | <= -33 | -4.1 .. +9.6 | +13.9 .. +17.5 | >= +30 |
|---|---|---|---|---|
| nodes | 9 | 4 | 3 | 5 |
| `d_station` (u) | 124 - 184 | 45 - 51 | **23 - 39** | 66 - 144 |
| `arrival_frames` | 5.31 - 8.82 | 0.66 - 1.03 | **0.00 - 0.27** | 1.89 - 6.49 |

The arrival is FREE only at offsets **+13.9 to +17.5** -- and the landing's optimum is **-7.5**. The
two optima are ~22-25 u apart and neither is a rank artifact: they are the same geometry read from
opposite ends.

## The tail is the intended escape, and its default arc cannot reach

`away_walk.escape_atom`'s tail exists precisely so the arrival can be bought after Tetra is frozen
([the-arrival-is-payable.md](the-arrival-is-payable.md)), and `cloud_land.exit_arc` is what aims it.
Its two centres are the live entry bearing and the herd UP-bearing, and the direction from a
straight-push Link (lateral ~-27) to his station (lateral ~+15) is very nearly the herd LATERAL --
about **90 deg off both centres**. Session 110's default `half=0x2000` is +-45 deg, so it cannot point
there at all, and a tail swept at it runs him further away every frame. Measured at one relocated
endpoint (Tetra along 850.78 lat -19.69, offset -7.51):

| tail | 0 | 1 | 2 | 3 | 4 | ... | 8 |
|---|---|---|---|---|---|---|---|
| `d_station` (u), `half=0x2000` | 59.8 | 73.9 | 88.2 | 103.1 | 118.4 | | first < 34 at atom **15** |
| `d_station` (u), `half=0x4000` | | | | | | | **17.6 at atom 12** |

The wide arc pays the arrival and barely touches the landing -- the cost-20 landing floor at that
endpoint moves **2.401 -> 2.047 u** across the whole widening. So the arc is an ARRIVAL knob in
practice, whatever its docstring's joint framing.

**Scope this by Link's lateral, not by the endpoint.** The 90 deg figure is the DEEP straight-push
geometry (Link at lateral ~-27). At a shallower one -- cycle-3 node 4's posture at offset +6.83, Link
at lateral -6.67 -- the winning exit bearing sits **9.8 deg** from its centre, well inside the old
+-45 deg, and widening buys nothing. So the rule is not "always widen": measure where the tail has to
point, and check the winning bearing against the half-window (a sweep that reports its own edge is
how a binding window shows up instead of being assumed).

## The landing half IS solvable at the bar -- the ARRIVAL is what costs the last two frames

`total = herd + len(atom log) + row.plan_cost`, and the six cheapest rows cost 20, so a **95** at
herd 69 allows an atom of **6**. Given a free (along, offset) placement, six frames is enough for the
landing and not for the arrival. Measured at cycle-3 node 4 relocated to offset +6.83 (herd 69, Tetra
along 877.88 lat -13.50), enumerating 40900 variants over the full grid crossed with an 18-bearing
exit arc:

| atom log | 5 | **6** | 7 | **8** | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|
| best cost-20 landing (u) | 8.577 | **0.083** | 0.083 | 0.311 | 0.042 | 0.042 | 0.042 |
| `d_station` there (u) | 82.7 | **99.9** | 113.0 | **25.2** | 33.7 | 17.5 | 7.4 |
| total | 94 | **95** | 96 | **97** | 98 | 99 | 100 |

A **settled** 6-frame atom lands **0.083 u** from row 74 (`plan_cost` 20) at total **95** -- the bar,
and the first time any measurement has put the landing there. It is not deliverable: at that frame
Link is **99.9 u** from the row's station and the two tail frames that bring him to 25.2 u cost
exactly the two frames the plan does not have.

The mechanism is that the atom throws Link OUT and the tail curves him back. At the herd endpoint he
is already ~32 u from the station; six atom frames carry him to 99.9, and `d_station` only returns
under `FREE_REACH` at atom 8-12 (25.2 / 33.7 / 17.5 / 7.4). So the arrival is not decided by where the
herd leaves him but by where the ATOM does, and a fully-paid 95 needs an endpoint whose SHORT-atom
excursion happens to end near a station -- a placement question, ranked on `d_station` at atom <= 6,
which no cut has ever ranked on.

Swept over the whole (along, offset) surface -- 105-170 cells at each of three frame-minimal postures,
herd priced -- the split holds everywhere and the paid floor is the SAME number at all three:

| posture (c3 node) | herd | best IN-BAND | best FULLY PAID |
|---|---|---|---|
| 1 | **68** | **94.00** @ 0.685 u (atom 5, `d_station` 58.8) | 97.00 @ 0.685 u (atom 8, `d_station` 23.1) |
| 4 | 69 | 95.00 @ 0.083 u (atom 6, `d_station` 99.9) | 96.27 @ 0.477 u (atom 7, `d_station` 26.9) |
| 0 | 69 | 96.00 @ 0.082 u (atom 7, `d_station` 46.6) | 97.00 @ 0.089 u (atom 7, `d_station` 22.1) |

The landing reaches **94** and every fully-paid cell is **97** in whole herd frames (node 4's 96.27
carries a 0.27 fractional charge for going 3.5 u past the ceiling). Node 1's two entries are the SAME
cell -- offset -13.06, along 868.0 -- differing only in the atom log, 5 against 8: three tail frames,
and nothing else, is the entire distance between the bar and the floor.

## Half the on-line endpoints refuse, and it is not because they are on-line

The session-111 cut is not blind to the specification -- its cycle-3 beam contains twelve on-line
endpoints at herd 69-74, offsets -6.04 to +9.63. **Four of them fire and eight do not**, and the split
does not follow the offset: node 7 (herd 70, offset **-0.54**) fires 1568 of 4654 variants at the
standing pair and 17220 at a wide arc, while node 32 -- 0.2 u away in along, 1.2 u in lateral, offset
**-0.13** -- fires **zero**. So the refusal is state-specific, not a law about being on-line, and
`away_walk.fires_census` says which clause it is at each:

| node | herd | offset | variants | fire (pair / wide arc) | failing clauses | sole |
|---|---|---|---|---|---|---|
| 36 | 69 | -1.04 | 2301 | 0 / 0 | `l_ok` 672, `dips` 672, `recedes_at_cap` 336 | none |
| 43 | 69 | -5.13 | 3972 | 0 / 0 | `l_ok` 672, `dips` 535, `separates` 29 | **`l_ok` 108** |
| 45 | 69 | -6.04 | 4040 | 0 / 0 | `l_ok` 672, `dips` 465, `separates` 34 | **`l_ok` 173** |
| 32 | 70 | -0.13 | 3476 | 0 / 0 | `l_ok` 672, `dips` 672 | none |
| 33 | 73 | +0.14 | 3325 | 0 / 0 | `l_ok` 672, `dips` 672 | none |
| 35 | 73 | +0.97 | 3684 | 0 / 0 | `l_ok` 672, `dips` 575, `recedes_at_cap` 2 | **`l_ok` 97** |
| 40 | 73 | +4.24 | 3404 | 0 / 0 | `l_ok` 672, `dips` 672 | none |
| **7** | 70 | -0.54 | 4654 | **1568 / 17220** | `dips` 439, `recedes_at_cap` 8, `separates` 6 | `dips` 438 |
| **0** | 69 | +17.49 | 4704 | **2828 / 26801** | `dips` 209 | `dips` 209 |

The last two rows are the positive control, and they are what makes the zeros mean anything: an
endpoint that converts reports thousands of firing variants and fails only `dips`, never `l_ok`. Among
the refusers, nodes 36/32/33/40 fail every clause at once and no knob buys them back, while 43, 45 and
35 have **108, 173 and 97 variants one clause from firing** -- and that clause is `l_ok`, a facing
question the PREVIOUS roll's camera has authority over rather than the escape's own shape
([clip-camera-supply.md](clip-camera-supply.md) and `away_walk.snap_reach` are where that is
answered). So "the cut cannot produce on-line endpoints" was never the problem: it produces them, the
camera refuses some of them, and the ones it admits (node 7) fail for the ordinary reason instead --
node 7 sits at lateral -48, 25 u below the cloud, and lands 18.9 u out at total 97.

## See also

- [the-landing-belongs-to-the-endpoint.md](the-landing-belongs-to-the-endpoint.md) - the endpoint owns
  the landing, and the offset points the forced push. This page prices what steering it costs.
- [the-arrival-is-payable.md](the-arrival-is-payable.md) - the tail, and why the joint bound is
  tail-invariant. The arc width above is the missing precondition for aiming it.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - the two halves themselves.
- [herd-price-of-a-placement.md](herd-price-of-a-placement.md) - what a herd frame is worth in along,
  including the search beam's measured delivery ceiling.
