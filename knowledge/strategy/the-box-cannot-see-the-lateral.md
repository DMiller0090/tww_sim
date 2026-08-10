# The terminal box cannot see the lateral, because all three of its axes are the same projection

**Answers:** My terminal scan gives me a box in `(runway, along, tetra_from_corner)` and my delivered
states miss it by 30 u - is that the whole miss? Why did screening on that box refuse a whole banked
population for the wrong reason? Which coordinate of a handoff is a property of the PUSHED actor alone,
and which can an aim still buy? My family fixture has no `side` column - what is it silently asserting?
**Status:** structural, and gated rather than argued (session 146). `along = (T-L)·m`,
`runway = -(L-brace)·m` and `tetra_from_corner = runway - along` are every one of them a projection on
the roll direction, so a pure lateral slide of BOTH actors leaves all three **bit-identical**
(`tests/test_terminal_keep.py::test_the_box_is_blind_to_the_lateral_and_l0_is_not`). The banked scans
are a **`side = 0` slice**: `terminal.RollFrame.item` takes `(runway, along, lat)` and puts the pusher
at `brace - runway*m`, exactly on the brace line. Measured consequence: the 49 banked rungs' last-roll
entries sit at `side` -170..-177 and `l0` **-128.92..-140.40** against a genuine `l0` of +0.57..+51,
where the box axis session 145 reported missed by **31.58 u**.
**Source:** [`harness/tetrapush/terminal_keep.py`](../../harness/tetrapush/terminal_keep.py)
(`TerminalKeep.screen`'s `t_l0`, `l0_band`, `side_scanned`),
[`terminal.py`](../../harness/tetrapush/terminal.py) (`RollFrame.item` - the slice),
[`handoff.py`](../../harness/tetrapush/handoff.py) (`PairFrame.item` - the 4-axis frame,
`tetra_lateral`, `endpoint`'s `sign_prune`). Gate
[`tests/test_terminal_keep.py`](../../tests/test_terminal_keep.py) (19); continues
[re-point-the-handoff-dont-re-project-it.md](re-point-the-handoff-dont-re-project-it.md).

---

## Four coordinates, and the scan only parametrises three

The handoff frame has four axes (`handoff.PairFrame.item`): `runway` and `side` place the pusher,
`along` and `lat` place the pushed actor relative to him. The terminal scan uses the three-axis frame
(`terminal.RollFrame.item`), which is the same thing at `side = 0` - so every banked family is one
slice, and the fixture has no column to say so.

That is a fair choice for the scan (the pusher must arrive AT the corner, so the ray through the brace
is the interesting line) but it is not a fair screen. Three of the four axes survive the slice unchanged
because they never depended on the lateral in the first place:

| axis | definition | moves under a lateral slide of both actors? |
|---|---|---|
| `along` | `(T - L)·m` | no |
| `runway` | `-(L - brace)·m` | no |
| `tetra_from_corner` | `runway - along` | no |
| `lat` | `(T - L)·q` | no (it is a RELATIVE lateral) |
| **`l0`** | `(T - brace)·q` = `side + lat` | **yes, by exactly the slide** |

So a screen built from `along` / `runway` / `tetra_from_corner` reports a number for a population
displaced 200 u sideways and cannot tell. Session 145 measured its misses honestly and in the right
frame, and every one of them was on an axis that could not see where the real miss was.

## Which axis belongs to whom

This is the useful half, because it says where each deficit has to be paid:

* **`l0` belongs to the PUSHED actor.** It is her offset from the clip roll's approach line, one dot
  product on her delivered position. No choice of the last roll's aim buys it - re-opening each banked
  cycle-2 terminal at its pre-roll endpoint and sweeping the whole aim circle moves the handoff by
  -10.3..+18.2 u (session 126). It is the HERD's output.
* **`side` belongs to the pusher and the junction can buy it**, which is why the razor is solved on
  `side` for a given her (`handoff.entry_locus`) rather than on her position for a given him.
* **`lat = l0 - side`** is therefore not independent: once the herd has fixed `l0`, choosing `side`
  chooses `lat`. That is the razor's own axis and it is bisected, not screened.

## So the screen refuses on the SIGN and reports the band

The genuine set is entirely at `l0 > 0` - two independent scans, and re-confirmed at session 146 where
it decides: at the four best banked cycle-2 exits (`l0` -69.66..-90.04) `entry_locus` returns 5-7 razor
ROOTS and **0 genuine**, over runway 160..520 and the full `side` sweep. Roots read as clips is the same
trap that voided a whole session's plan ([[banded-proxy-needs-its-newton]]), so the count that matters
is the second one.

The scanned family's own lateral extent is ~2.2 u wide (`un_lat`), and screening on THAT would refuse a
genuine terminal at a `side` nobody has scanned - a keep may not drop a configuration that is merely
unmeasured (`[[infeasible-needs-proof]]`). So:

> **the refusal is `l0 > 0`; the 2.2 u band is reported as `l0_miss` and never refuses**, and
> `exact_side` says whether the probed `side` is the one the box was actually measured at.

`t_l0` goes second in the screen, straight after the facing (which is what `q` needs to exist). It is
one dot product, and it is the axis that refuses the entire banked ladder - all 49 rungs, where session
145 recorded `t_along` for all 528 of its seam-window aims because this axis did not exist yet.
