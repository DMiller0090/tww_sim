# Re-point the handoff, don't re-project it: a terminal box belongs to ONE roll facing

**Answers:** My terminal scan gives a box in `(runway, along, lat)` - can I check a delivered herd
state against it by projecting? Why did "4 of 49 rungs satisfy `tetra_from_corner`" become 0 when the
same rungs were measured again? My search ranks endpoints on a residual - when does a rank have to
become a KEEP instead? A screen refuses the very hits its window was read from - what did I get wrong
about a grid-sampled extent?
**Status:** MEASURED, session 145, on the flooded-Hyrule Courtyard Tetra push, over all 49 banked
ladder rungs (`fixtures/courtyard_candidate_ladder.json`) against the thrust-14 delivered-lean
terminal. Each rung's last roll re-pointed across the FULL 2280-member aim alphabet from its own last
junction: **528 aims reach a live seam cell, every one dies `followed`**, and none is inside the box.
**Source:** [`harness/tetrapush/terminal_keep.py`](../../harness/tetrapush/terminal_keep.py)
(`TerminalKeep`, `seam_window`, `_widen`), [`handoff.py`](../../harness/tetrapush/handoff.py)
(`PairFrame.coords`, `probe`), [`full_herd.py`](../../harness/tetrapush/full_herd.py)
(`roll_probe`'s ``terminal`` / ``terminal_sink``), [`terminal.py`](../../harness/tetrapush/terminal.py)
(`clipping_family`). Gate `tests/test_terminal_keep.py`; probe `_notes/s145_repoint.py`, artefact
`_generated/s106/s145_repoint.json`.

---

## The box is a coordinate, and the coordinate has a facing in it

A terminal configuration is written in the clip roll's own brace-anchored frame:

    entry = brace - runway * m + side * q          tetra = entry + along * m + lat * q

`m` is the ROLL DIRECTION - `cM_ssin_s16(facing)`, `cM_scos_s16(facing)` - and `q` is its perp. So
`runway`, `along` and `lat` are not properties of a pair of actors. They are properties of a pair
*plus a facing*, and `tetra_from_corner = runway - along` reduces to `-(tetra - brace)·m`: how far she
is from the corner **measured along the direction the roll will travel**. Change the facing and every
one of those four numbers changes, at the same two world positions.

That matters here because the box only EXISTS at a handful of facings. The seam admits genuine dust in
22 measured sine-table cells ([clip-exit-angle.md](clip-exit-angle.md)), and outside them a scan of
the whole handoff box converts nothing: at facing 38782 - the closest any banked rung delivers, 11 deg
below the window - thrust 14 bisects **2674 razor roots and clips at none of them**
([dispatchable-is-not-clipping.md](dispatchable-is-not-clipping.md)). A delivered state read in its
own roll's frame is therefore being scored against a box that does not apply to it.

## Two questions, and only one of them is about the plan

1. **Fired at the facing the herd delivers, is the pair in the box?** Moot: at that facing there is no
   box. Session 144's delivery block answers this one - its `along` / `runway` / `tetra_from_corner`
   come from `_notes/s143_rolls.py`, which builds a frame per rung at **that rung's own facing**.
2. **Re-pointed at the corner, is the pair in the box?** This is the plan's question, and answering it
   is not a re-projection of the same positions. The roll's ENTRY moves with the aim: `entry` is
   Link's position at the END of the roll-entry frame, which steps `nspeed` units in the aim
   direction, so a re-pointed roll starts somewhere else. It has to be SIMULATED.

Re-pointed and simulated, over the whole ladder:

| axis | window | delivered | best miss |
|---|---|---|---|
| `runway` | 185.00..245.00 | 193.69..360.51 | **0.00** (satisfied outright on 10 of 49 rungs) |
| `along` | 57.50..102.50 | -12.43..50.43 | 7.07 |
| `tetra_from_corner` | 102.50..162.50 | 194.08..331.52 | **31.58** |
| `lat` (the razor, solved not kept) | +3.07..+5.23 | 15.80..79.57 | 10.57 |

So `tetra_from_corner` is not "4 of 49 satisfy it" - in the frame the box is written in, **nothing on
the ladder is within 31 u**, and the axis that is actually free is `runway`. The herd is short on how
far it plows her toward the corner, and the pair's own axis sits 15-45 deg off the corner's where the
terminal wants ~3.

## Which is why the terminal is a KEEP and not a rank

`handoff.probe`'s `resid` is the signed razor miss, and five sessions ranked herd endpoints on it. At a
facing 11 deg outside the seam window that residual **cannot reach zero**, so ranking on it ranks a
quantity with no root in it - and a rank on one criterion breeds a population satisfying one
criterion, which is exactly the ladder that resulted. `full_herd.roll_probe` now takes a
`terminal_keep.TerminalKeep` and refuses an aim failing any of facing / `along` / `runway` /
`tetra_from_corner`, ranking only what survives all four on the exact residual at the roll's own
facing, lean and momentum. See [the-screen-is-not-the-rank.md](the-screen-is-not-the-rank.md) for the
general form and [confirm-the-terminal-before-you-rank.md](confirm-the-terminal-before-you-rank.md)
for the sibling failure (ranking on a target never confirmed to exist).

The measurement also says where the keep must LIVE. Re-pointing the last roll from a banked junction
cannot recover any of it: all 528 corner-aimed aims die `followed` - Link stops plowing her the moment
his roll passes her - and they miss the box by the margins above. Those three deficits are set by the
CYCLES, so the keep has to be bred against, not applied at the end.

## A grid-sampled extent is not a boundary

`terminal.scan` samples `runway` every 10 u and `along` every 5 u, so `un_along = 60..100` is the
extent of the SAMPLED hits: the family provably contains those points and its true edge lies somewhere
inside the next cell. Screening on the bare extent is not merely conservative, it is wrong - projecting
a banked hit's own world pair back through the f32 sin/cos basis (orthonormal only to ~1e-7) lands it
**~3e-5 u below** its integer coordinate, and three of the eight banked unbroken hits failed a screen
built from those same eight.

The window is therefore the sampled extent widened by **half a scan cell** each side - the resolution
the extent is known to, not a tolerance - and `test_the_keep_contains_every_hit_it_was_built_from`
holds it there. A screen that refuses its own generating set is broken whatever else it does
(`[[search-space-contains-human]]`, the general form) - the same lesson
[the-window-binds-on-the-parents-that-produce.md](the-window-binds-on-the-parents-that-produce.md)
records on the other side of a cut.

## Reading a zero

Two habits make a zero legible here, and both are in the code rather than in prose:

* **the cross-tab.** `dead['<why>@seam']` counts aims that died a HERD death while their achieved
  facing was already inside the seam window. Every death after "the roll never fired" has fired its
  roll, so the achieved facing is exact and the cross-tab needs no proxy. It is what turns "2280 aims
  died" into "528 of them were pointed at the corner and every one stopped plowing her".
* **the sink.** `terminal_sink` takes the screen for EVERY aim whose roll fired, kept or dead. Without
  it a keep reports only survivors - and since none of the corner-aimed aims survives, the geometry
  reported would have been exactly the geometry of the aims that are not pointed at the corner.
