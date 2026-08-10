# A cut widens two ways, and only one of them is free

**Answers:** My cut keeps 400 of 5616 - do I raise the cap or re-compose the slots I already pay for?
What does the [census](count-the-states-before-pricing-a-cut.md) have to measure to tell me which? How
do I widen a cut without losing the reproduction guard? Why did the direction that reached 7x more
states produce FEWER new identities than the direction that only added more of the same states?
**Status:** measured, session 142, the cycle-2 probe pool (`extend_cycle`'s `probe_cap`) at the
s134_recut knobs (7 producing cycle-1 parents, contact fan 0x600, `l0` screen in the thrust-14 frame,
beam 16) with `jn_keep` held open at session 141's configuration, so the reference is **86.89**.
**The pool BINDS and was costing 1.67 frames: 86.89 -> 85.22**, and every winner came from the
direction the census ranked SECOND.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`_probe_pool`,
`_mixed_beam`'s `group`/`per_group`, `_dedup_endpoints`, `_physics_tag`). Probe
`_notes/s142_pool_price.py` (stages `census` / `c2` / `attrib` / `c3`), logs
`_notes/s142_census.log`, `_notes/s142_c2_stage.log`, `_notes/s142_attrib.log`,
`_notes/s142_c3_b*.log`; artefacts `_generated/s106/s142_pool_census.json`,
`s142_pool_{pop,novel,meta}.json`, `s142_c3_rows_b*.jsonl`.

## The census, in the units the pool selects in

The pool is the widest cut in the herd: `extend_cycle` takes `probe_cap` (400) of `junction_beam`'s
deduped endpoints per parent and `roll_probe` never scores the rest. Counted before paying for one
probe (junction cost only - wrap `_dedup_endpoints`, return nothing, and no screen runs):

| | |
|---|---|
| unique endpoints, 7 producing parents | **24708** |
| distinct `_physics_tag` states under them | **261** |
| pending letters per state | **94.67** |
| states the shipped 2800 slots reach | **34** |

Two numbers make the shape: the population is ~95 letters deep per state
([the-frame-the-alphabet-shares](the-frame-the-alphabet-shares.md)), and the cut's two orders - the
generation/flatness prefix and the s134 `l0` share - both walk *inside* a few states, so 400 slots land
on 5-6 of the 41-62 a parent offers. Within those few states the shipped pool is already ~74%
letter-complete (~67 of ~90 letters each). That is the whole reason there are two widen directions
rather than one.

**The Tetra-blind key is harmless here too, now at 20x the population.** Session 141 measured zero
`(_physics_tag, pending stick, pending L)` collisions at a different Tetra over 1266 roll survivors;
over all 24708 pre-screen endpoints it is again **zero**, widest `l0` spread inside one key **0.00 u**.

## Size costs, composition does not

| direction | what it adds | reaches | extra `roll_probe` time |
|---|---|---|---|
| **size** - raise the cap to 800 | the remaining letters of states already reached, plus a few states | 62 of 261 | **+84%** |
| **composition** - the same 400 slots with `_mixed_beam`'s `group=_physics_tag, per_group=cap//nstates` | one 6-9 letter slice of every state | **261 of 261** | **none** |

Composition is free because a cut's cost is its slot count, not its spread: the s68
`group`/`per_group` guard is already a parameter of the function being called
([a-keeps-width-is-not-its-reach](a-keeps-width-is-not-its-reach.md) found the same guard missing one
cut down). So the census answers a question the cap cannot: if the slots are landing on a handful of
states, reach is available for nothing, and raising the cap is buying the expensive half of it.

## But composition alone is not a widen - it is a swap, so union it

A re-composition at fixed cap is **not a superset**: capping the productive state at 6-9 letters drops
the ~60 letters of it the shipped pool was screening, so it can lose what the shipped cut found, and
the reproduction guard dies with it. That guard is what makes any price attributable
([count-the-states-before-pricing-a-cut](count-the-states-before-pricing-a-cut.md)).

The priced population is therefore the **union** - shipped 400 UNION state-capped 400 UNION plain-widen
800, shipped first - which costs what the plain widen costs and reaches what the composition reaches:

| | endpoints screened | physics states | roll survivors |
|---|---|---|---|
| shipped pool | 2800 | 34 | 220 |
| union pool (s142) | **6632** (+137%) | **261** | **490** |

**Guard: 220 of 220** of session 141's roll survivors come back byte-identical by input log, so nothing
below the cut moved. The stage cost 2415 s and the roll stage below the cut was 3182 endpoints in 247 s
(**10.2%**) - the same "measure the share of the stage below the cut" bill that made session 141's widen
affordable.

## What each direction actually bought: the letters, not the states

Every survivor labelled by the component that first took its origin endpoint (one junction re-run,
32 s - the components are pure functions of the population):

| direction | extra endpoints | roll survivors | **novel (state, pending) identities** |
|---|---|---|---|
| shipped 400 | - | 220 | 0 (all priced by s141) |
| more states (per-state cap) | +1857 | 165 | **39** |
| more letters (plain widen) | +1975 | 105 | **69** |

The direction that reached 7x more physics states produced **more survivors but fewer identities**: its
165 survivors collapse onto 39, while the extra letters' 105 survivors carry 69. Reaching a new state
is not the same as reaching a new *outcome* - a letter changes what the roll does with a state, and the
roll is where the divergence lives. Session 141's 2.93 frames came from a letter of a state the cut
already had; this is the same fact measured as a population.

## The verdict: -1.67 frames, and the free direction bought nothing

All 108 novel identities went through the cycle-3 stage knob-for-knob with s136-s141 (terminal facing
40660 / thrust 11, +-8.44 deg window, freed axis, floor 160, cap 250) - 23563 s of node time,
population-complete. **34 yield a live handoff; three beat the reference, and all three are letters:**

| | bound | vs 86.89 |
|---|---|---|
| s141's `jn_keep` winner | **86.89** = 69 herd + 83.15 u gap (4.89 f) + 13 cut | - |
| node 12 (letters) | **85.22** = **72** herd + **3.71 u** gap (0.22 f) + 13 cut, `l0` +51.22, runway 260 | **-1.67** |
| node 44 (letters) | 85.31 = 72 herd + 5.32 u gap + 13 cut, runway 270 | -1.58 |
| node 16 (letters) | 85.73 = 71 herd + 29.35 u gap + 13 cut, runway 210 | -1.16 |

| direction | identities priced | live | best |
|---|---|---|---|
| more letters (paid) | 69 | 21 | **85.22** |
| more states (free) | 39 | 13 | 88.04 |

All three replay bit-for-bit from their stored logs on a fresh native `FreeRun` (`_notes/s142_verify.py`
- bound/gap/`l0`/runway all to <1e-9; node 12 ends Link (-1478.123291, -796.263062), Tetra
(-1527.264404, -854.942566) over a 72-frame log, 21 entry curves admitted, runway mid-range so no rung
floor or ceiling is clipping it).

**So the cheap diagnostic mis-ranked the directions.** 34-of-261 is a real and free measurement, and it
is the one that says a widen has somewhere to go - but reaching a new physics state is not reaching a
new outcome, and the direction that reached 227 extra states lost to the one that only added letters.
**Count states to size the widen; expect the frames in the letters.**

**And the winning shape retires a term.** Node 12 hands Tetra over with the gap essentially closed -
**3.71 u, 0.22 frames** - where every bound since s135 carried 80-83 u (~4.9 f). The six cuts priced
flat before s141 all act on that gap term
([price-a-cut-in-both-directions](price-a-cut-in-both-directions.md)); at 0.22 f they are retired as
levers whatever their price. What is left of 85.22 is **72 frames of herd (85%)** and the **13-frame
clip roll (15%)** - and that 13 is `PairFrame.cut_step`, the schedule's own exact length for this
terminal, not a padding allowance. It moves by CHOOSING a terminal (thrust 14 -> 11 already took it
16 -> 13), not by building the sequence more tightly.
