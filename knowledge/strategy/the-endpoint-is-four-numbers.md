# The endpoint is four numbers, and the fourth one pays both halves

**Answers:** Every relocation axis I sweep trades my two predicates against each other and none solves
both -- is that the physics or my basis? Once I know the escape is a rigid throw, where do I GET the
endpoint from instead of gridding for it? Why does a finite-difference Newton stall at its first
iterate here? What is actually left blocking a paid endpoint, and how big is it?
**Status:** MEASURED (session 114) on the flooded-Hyrule Tetra corner, against the session-111
cycle-3 beam (`_generated/s106/s111_c3_beam.json`) -- the throw taken per variant at every node, the
endpoint solved by fixed-point iteration at eight of them, and the row/station geometry counted over
all **268** priced row-station pairs. Drivers `_notes/s114_{throw_map,endpoint_solve}.py`, dumps
`_generated/s106/s114_*.json`.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`,
`fires`), [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`atom_cloud`,
`station_gap`, `arrival_frames`, `FREE_REACH`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`CO_RADII_BAR`).

---

[the-short-atom-is-a-point.md](the-short-atom-is-a-point.md) closed sessions 111-113 with a negative:
over 170 relocation cells on three axes, each half of the delivery predicate is solvable and **no cell
pays both**. That measurement is correct and its conclusion was wrong, because the search space it was
taken in was one dimension short.

## The basis was three-dimensional and the endpoint is four numbers

A herd endpoint is Tetra's (along, lat) and Link's (along, lat). The three beds built by sessions
111-113 span three of those four:

| bed | moves | driver |
|-----|-------|--------|
| the OFFSET | Link's lateral | `_notes/s112_offset_c3.py` |
| the PLACEMENT | BOTH actors' along | `_notes/s112_place_curve.py` |
| the SEPARATION | Link's along | `_notes/s113_sep_curve.py` |

Every one of them leaves **Tetra's lateral** exactly where the node was born. That is not an arbitrary
gap: the priced rows span lat **-33.68..+1.61**, so a bed that cannot move her across the line is
hunting for a landing among rows it has already excluded, and "no cell pays both" was a statement
about the slice, not about the space. `_notes/s114_endpoint_solve.py`'s `tlat_shifted` is the fourth
bed and `placed` composes all four into absolute herd coordinates -- gated by `basis_check`, which
moves one coordinate at a time and reads a maximum off-diagonal leak of **4.6e-05 u**.

## Rigidity makes both endpoints ARITHMETIC rather than a search

The rigid throw is not the obstacle those sessions read it as; it is the tool. If the atom's
displacement is fixed, both endpoints are DETERMINED by the target:

* **ARRIVAL.** ``link_end = link_start + throw`` must land inside `cloud_land.FREE_REACH` of a
  station, so **Link's start is ``station - throw``**.
* **LANDING.** ``tetra_end = tetra_start + push``, and past `full_herd.CO_RADII_BAR` the push is
  exactly zero, so **Tetra's start is ``row - push``**, or the row itself when they are separated.

Nothing is searched. `_notes/s114_throw_map.py` measures the throw per variant per node and reads the
specification straight off, and the iteration that closes the residual is the same arithmetic re-read
at the current point -- a fixed point whose Jacobian is the identity by construction, converging at a
rate set by how much the throw moves per unit of relocation.

## And the fourth coordinate pays both halves, at total 95

Node 0 (herd 69, native Link along 782.30 lat -2.19, Tetra along 840.78 lat -19.69, separation 58.5),
target row 9 at `plan_cost` 20 -- re-verified from the four coordinates alone at the full grid
resolution (`_notes/s114_verify_winner.py`, dump `_generated/s106/s114_winner.json`):

| | |
|---|---|
| endpoint | Link (along **712.5708**, lat **-25.9759**), Tetra (along **882.4369**, lat **-13.5871**) |
| landing | **0.000056 u** from row 9 (`objective.PLACEMENT_BAND` 1.0) |
| arrival | **7.7252 u** from its station (`FREE_REACH` 34, so `arrival_frames` reads 0.00) |
| atom | 6 frames, `exit_run` 0, `handoff_f`/`settled_f` 6, `cs_bill` 0; all five `fires` clauses PASS |
| **total** | **95.0000** = herd 69 + **0** along relocation + atom 6 + `plan_cost` 20 |

It required **Tetra's lateral +6.10 u from native** -- the coordinate no bed had ever moved. First
endpoint in this work that pays both halves at once, and the along relocation is free because Tetra's
882.44 sits inside the herd's own 69 x 12.8177 = 884.42 u of travel.

**What "row 9" is, precisely**, since the whole total rests on it: the rows in
``_generated/s106/targets.json`` are the session-104 placement HUNT's hits, screened by
`herd_price.contact_at_arrival` and priced by session 105 -- not the original 288-coord
`seeds.load_placements` set, from which row 9 is 59.15 u away. That is the target set this work has
used since session 104 (which is where `plan_cost` 19-23 and the six cost-20 rows come from), and
whether row 9 is specifically among the 6-of-56 that session independently re-verified live is NOT
established here.

## The win is a DECOUPLING, and that is the part that generalises

The endpoint sits at ``centre_feet`` **160.25**, twice `CO_RADII_BAR` -- so Tetra takes **no push at
all** and her end is her start VERBATIM (she ends at row 9's coordinate to 5.6e-05 u). That is the
mechanism, not a coincidence:

> past the bar, the landing is Tetra's PLACEMENT and the arrival is Link's ALONE, so the 4D endpoint
> separates into two independent 2D problems -- and two 2D problems with two coordinates each always
> have a solution, where one 2D problem with four coupled predicates need not.

Which is exactly why three axes could never find it. The offset and placement beds hold the separation
invariant by construction, so they can never enter the decoupled regime at all; `_notes/s113_sep_curve.py`
did reach it (cf 159.8) and got the landing to **0.163 u** -- 0.163 u away from this result -- but with
Tetra's lateral pinned it could only land her where that one line happened to pass a row. The fourth
coordinate is what puts her ON one.

Two things this costs, and both are named below: the separation it requires, and the fact that cf
160.25 sits at the very top of the range where `fires` still fires at all (session 113 measured the
atom firing at ``centre_feet`` up to 160, 30 short variants a cell -- here 6 of 690).

## A finite-difference Newton stalls here, and the reason is worth keeping

The first attempt froze one knob combo to make the residual smooth and ran a 4x4 FD Jacobian. It
stalled at iterate 0 at every seed. The cause is that ``len(log) = handoff_f + exit_run`` and
``handoff_f`` is decided by `CO_RADII_BAR` and the recession test -- **both step functions in
position**. A relocated n=4 combo runs to n=6, so the difference quotient measures the jump and not
the map. Two corrections, and they generalise to any solve over this atom:

* **Re-select the best member of the grid at every iterate** rather than freezing a combo. The
  rigidity licenses exactly this: the members are interchangeable to ~1 u, so the selection is stable
  while the log length stays free to be whatever the state makes it.
* **Iterate on the objective's acceptance, not on the equation.** The landing owes
  `PLACEMENT_BAND` and the arrival owes only `FREE_REACH`, so driving Link ONTO his station solves a
  tighter problem than the objective poses -- and it is the tighter part that stalls, because the last
  few units are precisely what no knob supplies. Stopping at ``landing <= 0.1 u`` and
  ``arrival <= FREE_REACH`` accepts at iterate 2 what grinding refuses at iterate 6.

## What is left is the SEPARATION, and it is a PRICE, not a wall

Every specification wants Link further up-line than the beam supplies. Over all **1160** specs at the
29 of 64 nodes that hold a firing settled short atom, the required separation runs **92.5..156.8 u**,
while the beam's own nodes sit at **38.09..75.25 u** (mean 53.83; feet distance 57.0-75.5,
`centre_feet` 46.7-71.1) and **none reaches 100 u**. The requirement decomposes:

    required separation  =  (row along - station along)  +  throw along  -  push along

* The first term is **fixed by the target set** and is the hard floor. Over all 268 priced
  row-station pairs it runs **72.29..164.58 u** (mean 115.37); the minimum belongs to row 0 at
  `plan_cost` 21, with row 9's cost-20 pair 0.8 u behind it at **73.09**. The stations sit at along
  804.70-818.69 and the rows at 879.92-979.86, so Link must END at least 72 u up-line of Tetra because
  that is simply where the two target sets are. No cheaper pairing exists, at either cost.
* The second term is the atom's own overshoot, and it is **positive at every node**: over 66
  (node, length) classes the throw's along runs **+55.01..+113.42 u** (lateral -44.52..+59.63).
* The third gives it back, up to ~41 u at the deepest.

**And the separation has a herd price, which no session had taken.** Session 112 priced the ALONG axis
at `RATE_CAP` **12.8177 u/frame** ([herd-price-of-a-placement.md](herd-price-of-a-placement.md)); the
separation's own rate is Link's endpoint speed, because a frame of backslide moves him up-line and
grows the gap directly. Endpoint speedF spans **-25.727..+18.500** with every node in MOVE, so the cap
is **25.727 u/frame** -- and a node at +18.5 is CLOSING, not opening, so the rate belongs to the node
and not to the axis.

That converts the last obstacle from a wall into an addend, and the addend is small:

| | separation | gap from the beam's widest (75.25) | frames at 25.727 u/f | honest total |
|---|---|---|---|---|
| the cheapest SPEC (node 8, row 9, atom 6, total 96.00) | **92.5 u** | 17.3 u | **0.67** | ~**96.7** |
| node 0's SOLVED endpoint (total 95.00) | 169.87 u | 94.6 u | **3.68** | ~**98.7** |

The first row is arithmetic only -- a specification, not a solved and confirmed endpoint; the second is
both. Both beat the banked 101. Neither is a candidate: a relocation bed is self-consistent physics
that no state-2 log reaches, and the frames are an UPPER bound charged at the fastest separating frame
available -- a re-cut may find such endpoints for less, since Tetra also coasts ~36 u on plow momentum
after the last push (session 105) and the beam was ranked on `junction_quality`, never on separation.
The closest any spec comes to the live 41-85 u band is **7.5 u**.

## The overshoot is not a knob: `turnaround_first` makes it worse

The obvious move is to look for a throw whose along component is small or negative, and the ESS facing
snap is the knob that would do it. It does the opposite. Censused at three nodes over the firing
settled short variants:

| node | `turnaround_first=False` | `turnaround_first=True` |
|------|--------------------------|-------------------------|
| 0 | 80 fire, throw along +54.82..+81.11 | 88 fire, **+74.43..+90.82** |
| 13 | 69 fire, +61.79..+92.76 | 70 fire, **+83.12..+99.68** |
| 1 | 0 fire (all 1059 fail `l_ok`) | 218 fire, +76.26..+102.68 |

Both branches throw Link down-line and the turnaround enlarges it. The mechanism is the atom's own:
the conversion negates a ~25.7 u/frame up-line backslide into down-line flight, so the displacement
points at Tetra by construction and its magnitude is the flight time.

## The rigidity is posture-dependent -- read it at the node, not from the table

[the-short-atom-is-a-point.md](the-short-atom-is-a-point.md)'s 1.1 x 1.1 u extent is real and belongs
to the two relocated cells it was measured at. Taken at the nodes' OWN postures the same measurement
spans two orders of magnitude at the same log length:

| node | atom | variants | extent (along x lat) |
|------|------|----------|----------------------|
| 55 | 4 | 22 | **0.00 x 0.03 u** |
| 13 | 4 | 24 | 0.05 x 0.36 u |
| 8 | 6 | 8 | 0.75 x 0.19 u |
| 0 | 4 | 36 | 0.84 x 1.77 u |
| 0 | 6 | 48 | 15.98 x 11.52 u |
| 6 | 5 | 202 | **14.87 x 47.77 u** |

Over all 66 (node, length) classes the extent spans **0.00..20.76 u along** and **0.03..51.62 u
lateral**. The throw is rigid ENOUGH to build a specification on wherever the extent is small, and the
extent tracks how many variants survive `fires` -- so measure it at the endpoint being used
(`_notes/s114_throw_map.py`'s per-node table) instead of inheriting a number from another posture.
