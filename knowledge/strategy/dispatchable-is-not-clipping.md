# A thrust that dispatches the cut is not a thrust that clips

**Answers:** My roll fires its cut at the cheapest thrust in the window - why does nothing clip there?
Which Courtyard thrusts can actually reach the seam, and how many frames does the cheapest one really
cost? How do I tell "no geometry" from "my scan was too coarse" when a scan returns zero? Does the
body lean matter to the terminal family, when the lean page says it is spent before the cut?
**Status:** measured session 144, population-complete over `terminal.scan`'s whole box (35 runways x
44 alongs x a ±70 u lateral sweep) at the delivered body lean and the scanned one. **Thrust 13
bisects 2390 razor roots and converts 0**; thrust 14 converts 40 of 2513 and thrust 15 converts 107 of
2613. Gated in [`tests/test_terminal_family.py`](../../tests/test_terminal_family.py) off the banked
`fixtures/courtyard_terminal_family.json`.
**Source:** [`harness/tetrapush/terminal.py`](../../harness/tetrapush/terminal.py)
(`clipping_family`, `clipping_thrusts`, `scan`, `razor_crossings`, `solve_razor`, `genuine_band`),
[`entry_search.py`](../../harness/tetrapush/entry_search.py) (`cut_step_window`, `thrust_window`).
Probes `_notes/s144_family.py`, `_notes/s144_thrust13.py`, `_notes/s144_bank.py`; artefact
`_generated/s106/s144_family.json`.

---

## Two different questions, asked of two different objects

[../mechanics/roll-cut-thrust-floor.md](../mechanics/roll-cut-thrust-floor.md) derives which roll steps
can **dispatch** a cut: `cut_step` 15..17, thrust 13..15, straight out of the roll's own animation
constants. That is a property of `procFrontRoll` and it is exact.

Whether the resulting cut **reaches the seam** is a property of the corner, and nothing in the
dispatch window speaks to it. The two answers do not agree:

| thrust | `cut_step` | roll frames | razor roots | genuine | contact unbroken |
|---|---|---|---|---|---|
| 13 | 15 | 17 | 2390 | **0** | 0 |
| 14 | 16 | 18 | 2513 | 40 | **8** |
| 15 | 17 | 19 | 2613 | 107 | 0 |

*(facing 40835, the delivered lean 648, over the full scan box.)*

**So the cheapest DISPATCHABLE clip roll is not a deliverable one.** Session 143 corrected the roll's
cost to `cut_step + 2` and read the floor off the dispatch window alone - 17 frames at thrust 13 -
and every bound it wrote carries that. The floor is **18**, thrust 14's.

## Roots are what separate absent geometry from a thin scan

A bare zero cannot tell the two apart, and this corner has answered that question wrong before
(`[[infeasible-needs-proof]]`, and see
[confirm-the-terminal-before-you-rank.md](confirm-the-terminal-before-you-rank.md) for the same shape
one level up). So the count that matters is not the hits - it is the **conversion**:

- the root counts are within 10% of one another across all three thrusts, so the scan resolves the
  residual's sign changes equally well at each. It is not sampling.
- thrust 13's roots solve to |resid| ~2e-7 and its `brace_dist` reaches **0.00**, so Link does arrive
  at the corner there. He arrives and the cut does not go through.

`terminal.clipping_family` banks both numbers per record for exactly this reason, and
`clipping_thrusts` is the filter a search should iterate rather than
`entry_search.THRUSTS` - which is, correctly, the *dispatch* window.

## The body lean moves the family, and it belongs to the roll's own dispatch

[../mechanics/roll-lean-decay.md](../mechanics/roll-lean-decay.md) shows the entry lean is spent long
before a late cut fires, and that **with the razor re-solved the cut-frame depth moves 0.0003 u over
±3000 s16**. Both remain true and neither implies what was assumed from them: depth at a solved
configuration is not the same quantity as *which configurations admit a solvable razor*. Scanned at
lean 0 the box carries 51 genuine and 13 unbroken; the family genuinely does move with the lean.

**Which lean, though, is not a property of the corner** - it is written by the roll's own dispatch
frame, which is still a MOVE and turns. See
[the-lean-is-the-rolls-own-dispatch.md](the-lean-is-the-rolls-own-dispatch.md): the schedule seed is
the `m351C` *after* the entry frame, one simulated roll reads it, and one at-cap cloud reached leans
from -130 to +240. So this table has to be re-asked per plan rather than quoted, and the session-144
numbers that pinned it to "thrust 14 alone" and moved the plow ceiling 180 → 160 u were taken at
**648, a state-2 seed read off a native mirror that is never synced back** - see
[../history/the-delivered-lean-was-an-unsynced-mirror.md](../history/the-delivered-lean-was-an-unsynced-mirror.md).

## The rule

**A window derived from one object does not license a claim about another.** Both halves of this were
already in the repo and both were used one object away from where they were measured: the dispatch
window is about the animation and got quoted as a frame floor for the *clip*, and the lean's
depth-invariance is about a solved configuration and got quoted as invariance of the *family*. The
check is cheap and mechanical - re-ask the question of the object the claim is about, and bank the
answer with its own root count beside it.

## See also

- [../mechanics/roll-cut-thrust-floor.md](../mechanics/roll-cut-thrust-floor.md) - the dispatch window
  itself, decomp-derived, and why it went seven sessions unenforced.
- [../mechanics/roll-lean-decay.md](../mechanics/roll-lean-decay.md) - the lean's decay and the depth
  invariance this page scopes.
- [confirm-the-terminal-before-you-rank.md](confirm-the-terminal-before-you-rank.md) - the same
  root-is-not-a-hit distinction, applied to a rank instead of a thrust.
- [the-corner-sets-the-depth-not-the-herd.md](the-corner-sets-the-depth-not-the-herd.md) - why the
  cut-frame overlap is the corner's property, which is what makes one family scan speak for every
  handoff.
