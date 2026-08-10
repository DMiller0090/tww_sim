# Confirm the terminal before you rank on it

**Answers:** My beam ranks endpoints by distance to a solved target - what if the target was never
confirmed to exist? Why did every candidate on a 49-rung ladder score well and confirm ZERO genuine
entries? How do I tell "my search under-sampled" from "the geometry is not there"? Where is the
Courtyard clip's genuine Tetra set at the thrust-11 terminal, and why is the herd not aiming at it?
**Status:** measured, session 142, at the terminal the whole s134-s142 chain optimises against
(facing 40660 / thrust 11, `cut_step` 13, runways 160..320). **No candidate on the banked ladder has a
confirmable genuine entry**, and the confirmable set sits at `l0` **+4.11..+12.67** while the ladder
parks her at **+29.47..+51.97**.
**Source:** [`harness/tetrapush/handoff.py`](../../harness/tetrapush/handoff.py) (`endpoint`'s ``roots``,
`entry_roots` vs `entry_locus`, `side_band`, `probe`, `tetra_lateral`),
[`objective.py`](../../harness/tetrapush/objective.py) (`score_plan`'s `complete`). Probes
`_notes/s142_genuine.py`, `_notes/s142_control.py`, `_notes/s142_densify.py`, `_notes/s142_region.py`;
logs beside them; artefact `_generated/s106/s142_genuine_region.json` (9 confirmed Tetras with their
entry curves).

## The rank was a proxy nobody had cashed

`handoff.endpoint` prices a herd endpoint as `frames + gap / WALK_CAP + cut_step`, where ``gap`` is the
distance to the nearest genuine Link entry at the Tetra the herd parked. It takes a ``roots`` flag:

| | what it measures | cost |
|---|---|---|
| `entry_roots` (``roots=True``, the DEFAULT) | zero-crossings of the razor residual - the **unconfirmed** curve | ~10x cheaper |
| `entry_locus` (``roots=False``) | `side_band` walked in f32 steps: a genuine band, or None | the claim |

Its own docstring says roots is "an under-estimate by construction… so a bound is never quoted as a
solved entry". Every session from s134 to s142 ranked, cut and reported on ``roots=True``, and none ran
the confirm. Measured on the four best rungs of the banked ladder:

| rung | bound | `l0` | roots | **confirmed** |
|---|---|---|---|---|
| 1 | 85.22 | +51.22 | 21 | **0** |
| 2 | 85.31 | +51.97 | 21 | **0** |
| 4 | 86.89 | +29.47 | 17 | **0** |
| 7 | 90.41 | +9.47 | 25 | **0** |

A residual zero-crossing is necessary and not sufficient: the pair still has to overlap. So the whole
ladder's ORDERING is unfounded - 85.22 against 90.41 compares two distances to points where the clip
does not fire. The herd frames in those logs are real and bit-exact; the terminal term is not.

## Three checks, in this order, before calling it infeasible

A zero from a search is not a verdict (`[[infeasible-needs-proof]]` - session
71 and session 125 both paid for that). The order matters because each one is cheaper than the next
question it makes worth asking:

1. **Positive control on the confirm path.** Run the same confirm at a KNOWN-genuine target
   (`[[search-space-contains-human]]`). At this terminal, 2 of 6 tabulated
   coords confirm with ``genuine`` True at residuals ~5e-5 u - so the machinery works, and the base
   rate is **0-1 confirmed per 22-29 roots**. That rate is what makes "0 of 21" look like sampling.
2. **Densify, and by resolution only** (`[[no-overtuned-constants]]`): the
   runway rungs at step 2 instead of 10 (81 against 17 -> 111 and 125 roots), and a band walk of
   **+-0.05 u** against `side_band`'s +-1.2e-3. Both rungs still confirm **0**. Forty times the span
   and five times the roots is enough to stop calling it density.
3. **Locate the set instead of the failure.** The genuine set is derivable at any Tetra - one
   `entry_locus` call, ~20-30 s - so ask where it IS rather than why the candidate is not in it.

## Where the set is, and where the herd aims

`_generated/tetra_placements.tsv` is not the set: it is 288 coords recorded at ONE banked roll entry,
and nothing in the search path reads it (`probe` derives ``genuine`` from the roll sweep). Dereck
(s142) is right that it must not restrict the plan - but the replacement is a set DERIVED at the
terminal in use, not no set at all. Measured over 29 of those coords at this terminal:

| | `l0` | x | z |
|---|---|---|---|
| **confirms (9 of 29)** | **+4.11 .. +12.67** | -1650.61 .. -1627.94 | -929.51 .. -893.00 |
| ladder rungs 1-4 | +29.47 .. +51.97 | - | - |

So a third of a table recorded at another entry survives here, in a band ~8 u wide - and the herd's
best endpoints sit four times outside it. That is the gap between the project's bound and a
deliverable, and it is a TARGETING error, not a frame count: `endpoint`'s ``sign_prune`` only asks
`l0 > 0` (the genuine set spans +0.57..+51.0 over solved terminals), so nothing in the stack ever told
the herd that clips live near the line rather than far across it.

## What this costs and what it does not

The cut-pricing results stand as RELATIVE measurements on a fixed metric - `jn_keep` and the probe pool
each bind, and the widen directions rank as measured
([a-cut-widens-two-ways](a-cut-widens-two-ways.md), [a-keeps-width-is-not-its-reach](a-keeps-width-is-not-its-reach.md)).
What does not stand is any claim that a numbered bound is near-deliverable. Two named optimisms in
`endpoint`'s own docstring - it charges nothing for turning to the roll facing, nothing for landing on
the razor rather than its neighbourhood - are the same debt this page cashes:
`[[banded-proxy-needs-its-newton]]`, one level up from a cell to a whole
search. **Rank on the confirmed quantity, or carry the confirm as a hard gate on whatever you rank.**
