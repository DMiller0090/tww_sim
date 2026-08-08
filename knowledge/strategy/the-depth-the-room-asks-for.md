# The depth the room asks for: one station cluster up-line, and a wall at 60 u

**Answers:** What is the separation between Link and Tetra actually FOR? Why does every endpoint on my
beam owe an arrival bill no matter where it lands? My herd finally produced a DEEP endpoint and its
escape fires nothing - is that the depth or the camera? Is my arrival half a search failure or the
room?
**Status:** MEASURED (session 123) on the flooded-Hyrule Tetra corner, off the banked cycle-3 beams -
the session-122 requirement lane (63 terminals) and the session-119 pair lane (64). Drivers
`_notes/s123_sep_vs_arrival.py` (offline, no cut) and `_notes/s123_deep_census.py` (154 s, dump
`_generated/s106/s123_deep_census.json`).
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`station_map`,
`station_gap`, `arrival_frames`, `FREE_REACH`),
[`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`fires`, `FIRES_CLAUSES`,
`fires_census`, `snap_reach`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`'s ``sep``).

---

[the-separation-is-not-a-suffix.md](the-separation-is-not-a-suffix.md) measured that Link's separation
from Tetra cannot be appended to a herd: a receding prologue spends the EBS momentum and the facing
that the escape atom needs, and ``l_ok`` then refuses all 672 variants. It closed on the one route it
could not test - **the separation is a HERD-shaped quantity, so the last roll is the only stage that
can deliver depth AND leave the posture intact.** This page is what the depth is for, and what
happened when the herd delivered it.

## What the depth is for: the stations are one cluster, up-line of every row

`arrival_frames` prices Link's gap to the LIVE stations each row's `plan_cost` was measured at. Those
are not spread like the rows. All **268** stations over the 116 rows lie in ONE cluster:

| | along | lateral |
|---|---|---|
| the 268 stations | **804.70 - 818.69** | +12.12 .. +35.46 |
| the 116 rows | **879.92 - 979.86** | -33.68 .. +1.61 |

Every row sits **72.3-162.6 u down-line** of its own stations (median 110.6). So a plan that lands
Tetra ON a row and leaves Link AT a station is by construction a plan with **61.2-175.2 u** between
them, and nothing but the separation holds that gap open. Session 114's specification of
92.5-156.8 u was not a preference - it is this measurement read from the other end.

## And it is the strongest predictor of the arrival bill there is

Over the two banked cycle-3 beams (`_notes/s123_sep_vs_arrival.py`, off the dumps, no sweep):

| | requirement lane (63) | pair lane (64) |
|---|---|---|
| ``sep`` the beam reaches | 29.6 - **59.4** u | 38.0 - **75.3** u |
| terminals reaching the SHALLOWEST ask (61.2 u) | **0** | 7 |
| terminals reaching the specification (92.5 u) | 0 | 0 |
| corr(``sep``, ``d_station``) over the firing | **-0.697** | **-0.819** |
| corr(`n_atom`, ``d_station``) | -0.489 | -0.603 |
| where the FREE-arrival terminals sit | ``sep`` **58.4 - 59.4** | ``sep`` 58.5 - 59.4 |

``sep`` is reported by `roll_probe` and ranked on by nothing, and it out-predicts the atom's own
length. Every terminal that owes no arrival at all is one of the deepest the herd produced - and the
requirement lane never reaches even the shallowest ask.

## The seven deep endpoints the herd DID produce fire nothing

The pair lane has seven terminals at or past 61.2 u. Censused with `away_walk.fires_census` against
the three deepest FIRING terminals of the same beam as the positive control - a zero is not a
diagnosis (`[[infeasible-needs-proof]]`):

| pair-lane terminal | ``sep`` | along | fires | attribution |
|---|---|---|---|---|
| control node 1 | 59.4 | 827.99 | **329 / 672** | `l_ok` 336, `dips` 50 |
| control node 7 | 58.6 | 897.04 | **226 / 672** | `dips` 439 (sole 438) |
| control node 8 | 58.5 | 897.09 | **245 / 672** | `dips` 401 (sole 400) |
| node 16 | **62.4** | 827.99 | **0** | `l_ok` **SOLE on all 672** |
| nodes 38, 39, 59, 61 | 65.5 - 67.9 | 969.2 - 970.9 | **0** | `l_ok` + `dips`, **no sole clause** |
| node 37 | 65.1 | 883.82 | **0** | `l_ok` + `dips` + `no_follow` + `recedes_at_cap`, no sole |
| node 47 | **75.3** | 980.22 | **0** | `l_ok` + `dips`, no sole |

**Every terminal deeper than 59.4 u fires nothing; every firing terminal is 59.4 u or shallower.** The
cleanest reading is the pair at the SAME endpoint along: node 1 at ``sep`` 59.4 fires 329 of 672,
node 16 at 62.4 fires **0** with ``l_ok`` the sole refusal on all 672. Three units of depth flip the
camera clause from refusing half the grid to refusing all of it - and 59.4 is already **below the
61.2 u the shallowest row asks for**.

## Read the two halves separately before spending on either

- **Six of the seven have NO sole clause.** ``l_ok`` and ``dips`` refuse together on all 672, so no
  single fix revives one variant, let alone a plan. Summing SOLE *variants* instead of counting
  *nodes* reads this population as "the camera is the whole story" - exactly the misattribution
  `fires_census` exists to prevent, and the first version of this measurement's own verdict line got
  it wrong that way.
- **The seventh, node 16, IS one camera fix from firing all 672** - and it lands Tetra at along
  **827.99, 52 u short of the nearest row at 879.92**. What a `snap_reach` win buys there is a landing
  that cannot be in band. A sole-clause node is a lever only if the rest of its record is payable.

## The rule: an irreducible bill is a room, not a search

The separation is closed at this atom recipe from both ends - it cannot be appended, and where the
herd delivers it the recipe refuses on several clauses at once. So the arrival bill is **structural**,
and that is the missing half of why
[the endpoint set answers the same 105.00 however it is cut](the-shape-of-a-cut-is-not-its-answer.md)
and why [moving the handoff along cannot pay it](the-handoff-along-was-already-spanned.md): three
differently-shaped cuts agree because they are all cutting a set whose cost is set by the room's
geometry, not by the cut.

When a bill is uniform across every candidate a search produces, price the GEOMETRY that imposes it
before shaping the search again. Here the geometry is two measured point sets 72-163 u apart and a
recipe that stops working at 60 u of separation; no keep, share, requirement or width changes any of
those three numbers.

## See also

- [the-separation-is-not-a-suffix.md](the-separation-is-not-a-suffix.md) - why a prologue cannot buy
  the depth, and the one resource that separation, momentum and facing all spend.
- [the-handoff-along-was-already-spanned.md](the-handoff-along-was-already-spanned.md) - the same
  station geometry read from the along axis, and the trade it forces.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - the two halves this bill is one of.
- [the-camera-supplies-the-cone.md](the-camera-supplies-the-cone.md) - where an ``l_ok`` refusal is
  answered when it IS sole.
- [the-dip-budget-is-not-the-lever.md](the-dip-budget-is-not-the-lever.md) - why the ``dips`` half of
  the six double refusals is not a knob either.
