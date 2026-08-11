# The delivered lean of 648 was an unsynced mirror (sessions 144-147)

status: historical
**Superseded by:** [../strategy/the-lean-is-the-rolls-own-dispatch.md](../strategy/the-lean-is-the-rolls-own-dispatch.md)
(session 148). The half that survives is the QUESTION - the body lean does move which configurations
admit a solvable razor, and a family must be scanned at the lean it will be entered with. What did not
survive is the value, and everything ranked against it.

---

## What was claimed

Session 144 measured the roll-entry body lean across all 49 banked ladder rungs, found **one distinct
value, 648**, and re-scanned the Courtyard terminal family there against session 124's scan at lean 0:

| | genuine | unbroken | `plowed` | `tetra_from_corner` |
|---|---|---|---|---|
| lean 0 (session 124's scan) | 51 | 13 | 24.70..125.88 u | 10..**180** |
| lean 648 ("delivered") | 40 | 8 | 25.26..106.05 u | 25..**160** |

On that basis the terminal was pinned - **thrust 14 alone** carries a zero-walk-away family - the plow
ceiling the whole endgame is priced against moved **180 -> 160 u**, and the ladder rungs clearing it
halved, 8 of 49 to 4. `terminal_keep.DELIVERED_LEAN = 648` became the default every terminal was built
at, and sessions 145-147 ranked on it: the `TerminalKeep` box, the 49-rung census of session 147, and
its headline that **rung 3 owes 14.69 u for a bound of 93 and is the only rung in the ladder that
beats the console.**

## Why it was wrong

648 is the **state-2 seed's `m351C`**, not a measurement of anything.

`from_f0.FreeRun._step_native` copied seven fields back from the native `LandCore` and not `m351C`
(the same hole was in `LandState._sync_from_core`), so on a native run `run.link.m351C` held its seed
for the entire herd. Session 144 read that mirror on all 49 rungs and got one value **because it is
the seed** - and recorded the unanimity as evidence rather than as the tell it was.

There was never a physics divergence. The native core's own `m351C` matches the Python path
bit-for-bit (422, 275, 77, 10, 0, 0 over the first frames of rung 3), and position, speedF, facing,
travel and Tetra were already 0-ULP. Nothing *inside* the sim reads the mirror - the core uses its own
copy - so the staleness is invisible until a harness script reads it as a measurement. The native
gates could not have caught it either: `tests/test_freerun_native.py` compares an allowlist of fields,
and `m351C` was never on it.

## What it cost

At rung 3's own census state the roll's dispatch lean is **0**. Read there, session 147's single
genuine entry is not an entry at all:

    lean 648 (the mirror) : genuine True   resid +6.745e-05  overlap  +1.126
    lean   0 (the real one): genuine False  resid -3.294e-01  overlap -32.989

and re-solving the whole locus at lean 0 over runways 100..400 step 2 returns **0 genuine entries**.
The ladder's only rung that beat the console did not exist. The correction does not empty the ladder -
re-censused at the true lean, rung 5 keeps 9 of its 10 entries and leads at bound 100 - it removes the
LEAD.

Session 144 also "corrected" a family that had been scanned at lean 0, which was nearer the truth than
what replaced it.

## The lesson

**A field a native bridge does not sync back is not inert - it reads as a measurement that never
moved.** Two tells were present and both were recorded as findings instead:

- **one distinct value across 49 independent objects.** `clip-lottery-draws.md` already says this in
  the other direction ("a suspiciously integral multiplier... print the IDENTITY of what you counted");
  unanimity across things that have no reason to agree is the same signal.
- **a constant whose provenance is a read rather than a derivation.** 648 was never re-derived from
  the roll it describes. One simulated roll would have shown the schedule seed is 130.

The durable form of the fix is on the successor page: sync every field a caller can see, gate the
field rather than the physics, and read the lean off the roll's own dispatch.
