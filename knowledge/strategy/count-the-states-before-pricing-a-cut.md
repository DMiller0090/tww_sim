# Count the states before pricing a cut

**Answers:** I am about to perturb or price a selection cut (the
[price-a-cut](price-a-cut-in-both-directions.md) instrument) - what free check comes first? Can a
beam hold the same coupled state twice under different input logs / why did the cycle-2 beam cut
price 0.00 in both directions at once? Where does the herd's 72 live, if not in cycle 2's final
beam cut?
**Status:** measured, session 140, the cycle-2 stage re-run at its banked knobs (8 cycle-1 parents,
contact fan, `l0` screen in the thrust-14 frame, cap 400, beam 16) with the final `_mixed_beam` cut
captured, then the s136/s139 cycle-3 stage (terminal facing 40660 / thrust 11, +-8.44 deg window,
freed axis, floor 160) run on the cut's ENTIRE complement. Both prices **0.00**: the complement's
best bound is **89.82** with the winner's own numbers, because the winner's cycle-2 state sits on
BOTH sides of the cut.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`_mixed_beam`,
`_state_tag`, `extend_cycle`). Probe `_notes/s140_c2_price.py` (stages `c2`/`c3`), logs
`_notes/s140_c2_stage.log` / `_notes/s140_c3_alt.log`, beams
`_generated/s106/s140_c2_shipped16_repro.json` / `s140_c2_alt16.json` /
`s140_c3_alt16_t11_f40660.json`.

## A population can be smaller than its node count, and the census is free

The cycle-2 stage's final beam cut looks like a real cut - 16 kept of 31 roll survivors - until the
survivors are counted by BIT-EXACT coupled state (position/speed/facing/travel/csangle/Tetra, all
by bits) instead of by node: **31 nodes are 18 states**. The 15 dropped nodes are 9 bit-exact twins
of kept members plus 6 nodes forming just **2 novel states**. A cut over such a population selects
REALIZATIONS - which input log carries a state forward - not states, and its maximum possible price
is whatever the novel-state complement is worth. The census costs seconds (rebuild the beam, hash
the state bits); the perturbation run it bounds costs an hour. Run the census first: it can say
"this cut cannot bind by more than N states" before anything is re-searched.

Twins across a cut are invisible to the cut itself: `_mixed_beam` dedups by `_state_tag` WITHIN one
call, so the kept 16 are tag-distinct, but nothing compares the dropped nodes to the kept ones.
The mechanism that mints twins is
[the-frame-the-alphabet-shares](the-frame-the-alphabet-shares.md) one level up: a delivered letter
cannot touch its own frame, whole letter-sequences differ in ways the physics never reads, and
45-frame histories converge to the same coupled state down to the last bit.

## The measurement: s139's instrument one stage up, on the whole complement

Session 139's two-direction pricing assumed a population much larger than the cap (250 of 9604).
One stage up the population IS the cap's size, so "the runner-up slice" degenerates and the honest
counterfactual is the ENTIRE complement - which upgrades the verdict: this prices the whole
population, no slice caveat.

| run | parents | best bound | vs 89.82 |
|---|---|---|---|
| s136/s137/s139 (reference) | the banked 16 | **89.82** = 72 herd + 81.89 u gap + 13 cut | - |
| the complement, all 15 nodes | 7 tag-distinct, 2 novel states | **89.82**, the same winner's numbers (l0 +15.48, runway 179, 72 herd) | **-0.00** |

- **The winner has a twin.** The complement's best descends from `alt[0]`, whose 45-frame input log
  differs from every kept node's and whose end state is bit-identical to kept node S1 - the
  winner's own cycle-2 state, reachable through two distinct input histories. The junction is a
  deterministic function of the state, so the 89.82 endpoint reappears to the digit.
- **The two novel states are now measured, and both lose**: one produces the 70-71-frame family
  that parks her OFFSIDE (`l0` -33.66, no plan), the other survives to no endpoint at all. With
  them, every state the cycle-2 stage's roll stage produces has been through the cycle-3 stage.
- **Union verdict:** bound(shipped UNION complement) = min(89.82, 89.82) = **89.82**. The cycle-3
  stage is per-parent independent up to its own final cut and `handoff` is computed per node over
  ALL survivors before that cut, so the union bound is the min of the two runs - no third run
  needed.

## Reproduce the banked artefact under its OWN cut, not today's

The banked beam predates session 134's `l0` share at the final cut, so today's code cuts by a
DIFFERENT rule than the one that made the artefact. The re-run tested both hypotheses against the
banked 16 by input log: the pre-fix rank-only cut reproduces **byte-identical** (twice, 933 s and
929 s); today's mixed cut does not. A counterfactual built on the wrong cut hypothesis prices a cut
nobody took. When an artefact outlives a code change to the stage that made it, the reproduction
guard is what keeps the perturbation attributable.

## What it retires, and where the 72 lives instead

The herd's 72 frames do not depend on cycle-2's final beam cut - that cut is now priced flat over
its entire population, both directions. The cycle-2 stage's LIVE selection is upstream of it:
`jn_keep` passes **6** of 58-259 rolling endpoints per parent, the probe pool passes **400** of
424-5616 junction endpoints per parent, and cycle 1's own beam hands over 8 parents of which only
**4 produce** any of the banked 16 (the winner descends from cycle-1 parent 4). Those cuts decide
WHICH 18 states exist at all, and none of them has been perturbed. The same two-direction
instrument applies to each - with this page's census run first each time, because it is free and it
bounds what the perturbation can possibly return.
