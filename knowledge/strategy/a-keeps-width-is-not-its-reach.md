# A keep's width is not its reach: count what its slots reach, in the cut's own key

**Answers:** My cut keeps 6 of 259 - how many distinct states do those 6 slots actually reach? The
[census](count-the-states-before-pricing-a-cut.md) says count states, but my population has 1266
members and 34 states - which is the census unit? Why does the same keep carry a per-state cap at one
cut and none at the next? What does a population-complete widen cost when the stage below the cut is
9% of the cycle?
**Status:** measured, session 141, the cycle-2 stage at the s134_recut knobs (8 cycle-1 parents,
contact fan 0x600, `l0` screen in the thrust-14 frame, cap 400) with the `jn_keep` cut opened to the
ENTIRE rolling population and every survivor labelled by its endpoint's rank in the cut's own order.
**It is the first cut priced since s135 that PAYS: bound 89.82 -> 86.89** (-2.93 frames), and the
endpoint that carries it sat at **rank 3 of a cut that keeps 6**.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`extend_cycle`'s
`jn_keep` cut, `junction_beam`'s frontier keep, `_mixed_beam`'s `group`/`per_group`, `_physics_tag`,
`_dedup_endpoints`). Probe `_notes/s141_jnkeep_price.py` (stages `c2`/`c3`), log
`_notes/s141_c2_stage.log`, artefacts `_generated/s106/s141_jn_pop.json` (all 220 survivors),
`s141_jn_novel.json`, `s141_jn_meta.json` (per-survivor rank/state/`l0`).

## The census unit is the cut's OWN key, and it can invert the answer

Session 140's census found a population smaller than its node count - 31 nodes, 18 states - so its cut
selected realizations, not states, and could not be worth much. One stage up, at the `jn_keep` cut that
decides which rolling endpoints ever become states, the same census comes back the other way round:

| | population | distinct cut keys | bit-exact states |
|---|---|---|---|
| cycle 2's final beam cut (s140) | 31 nodes | - | **18** |
| `jn_keep`, the same stage (s141) | **1266** rolling endpoints | **1266** | **34** (4-6 per parent) |

Every one of the 1266 is distinct in the cut's key and there are only 34 states under them, because
the key is `(_physics_tag, pending stick, pending L)` and the population is one node's children:
[the-frame-the-alphabet-shares](the-frame-the-alphabet-shares.md) - the delivered letter is buffered
and never read by its own frame, so a node's whole alphabet lands in one physics class carrying N
pending letters. So this cut chooses **which letter launches the roll**, and "count the states" alone
would have called a live 1266-way selection a 34-way one. Count both, in the cut's own key: the state
count bounds what the cut can be worth, the key count says what it is choosing between.

**The Tetra-blind key is measurably harmless.** `_physics_tag` carries no Tetra, so the key *could*
merge two endpoints differing only in where she is - the axis the whole objective is denominated in.
Measured over all 1266: **zero** collisions, widest `l0` spread inside one key **0.00 u**. A real
structural worry, closed by the census that was already running.

## The width was half nominal, and the guard against it already exists one cut down

The shipped cut spends **42 slots** (6 per producing parent) and reaches **20** of the 34 states:
**22 slots go to a state another slot already had**, and 14 states are never reached at all. Per
parent the keep of 6 lands on 1, 4, 2, 4, 4, 4 and 1 states.

That is exactly the failure mode session 68 built a guard for, and the guard is present at the cut one
level down and absent here:

| cut | `ident` | group cap |
|---|---|---|
| `junction_beam`'s frontier keep | `(_physics_tag, pending stick, pending L)` | `group=_physics_tag, per_group=per_state` (4) |
| `extend_cycle`'s `jn_keep` | the same tuple | **none** |

`_mixed_beam`'s own docstring names the consequence - "a beam whose members TIE fills every slot with
variants of a single state" - and the knob that fixes it (`group`/`per_group`) is already a parameter
of the function being called. So if the missed states are worth frames, the fix is an existing
mechanism with an existing constant, not a new tuned one.

## Price the widest direction: measure the stage split before budgeting the widen

The queued plan was `jn_keep=12`, budgeted at "~2x 929 s" because doubling the keep doubles the roll
stage. Measured on the run: the roll stage costs **0.074 s an endpoint**, so passing the WHOLE
population - 1266 endpoints, 30x the shipped 42 - cost **94 s of a 1042 s stage, 9.0%**. The estimate
was off by ~20x, and the widen that looked like a slice was affordable as a population-complete run.

This is [the-frame-the-alphabet-shares](the-frame-the-alphabet-shares.md)'s own lesson pointed at a
budget instead of a port: **a widen's cost is the share of the stage BELOW the cut, and that share is
a measurement, not an intuition.** One `time.perf_counter()` around the wrapped call answers it before
the run is designed - and the answer decided whether this session priced a slice or a population.

## The guard that makes the perturbation attributable

The shipped 6 are rolled FIRST and unchanged, so the run reproduces its own reference: **31 of 31**
banked roll survivors come back byte-identical by input log, all off shipped endpoints, and the seven
junction death counters are byte-identical to s140's (they must be - `jn_keep` sits below the junction,
[the-biggest-death-counter-was-the-alphabet](the-biggest-death-counter-was-the-alphabet.md)'s plumbing
lesson running in the expected direction). The 31's own identity count is **18**, matching s140's
independent census of the same nodes - so the (state, pending) key cross-checks free.

What the dropped endpoints add: **189 survivors = 66 novel (state, pending) identities** on **66
distinct coupled states, none of them a state the shipped 31 reach**; the other 123 are bit-exact
realizations of the 18 the shipped cut already had. The letters do not stay letters - they diverge
through the roll into new states, which is what makes the wasted slots load-bearing rather than untidy.

## The verdict: -2.93 frames, and the slot was taken by the `l0` share

All 66 novel identities went through the cycle-3 stage knob-for-knob with s136/s139/s140 (terminal
facing 40660 / thrust 11, +-8.44 deg window, freed axis, floor 160, cap 250). **15 yield a live
handoff; one beats the reference:**

| | bound | vs 89.82 |
|---|---|---|
| the shipped `jn_keep` (s136-s140) | **89.82** = 72 herd + 81.89 u gap + 13 cut | - |
| node 16, off a dropped endpoint | **86.89** = **69** herd + 83.15 u gap (4.89 f) + 13 cut, `l0` +29.47, runway 230 | **-2.93** |

Three fewer herd frames at the same gap. It replays bit-exact from its stored 69-frame log (`bound
86.8914 / gap 83.1545 / l0 +29.4681` recomputed to 1e-9 on a fresh native run), its runway sits
mid-range so no rung floor or ceiling is clipping it, and cycle 3 ran with `jn_keep=6` unwidened (48
roll survivors a node, 8 after the beam - the widening is behind a flag the c3 stage never sets).

**The endpoint was at rank 3 of a cut that keeps 6.** `_mixed_beam` gives each order `beam //
len(orders)` slots, so with the rank and the s134 `l0` share that is **3 each** - the rate order never
sees rank 3 at all, and the `l0` share spent the slot. Session 137 had already measured that `l0` does
not predict the bound; this is that finding's bill, in frames. The winner's own cycle-2 `l0` is
**-175.60**, WORSE than the shipped beam's -154.38, so the screen would rank it near-last.

**And the crossing still does not pay.** The identities that reach the bar (`l0` -79.26 to -81.87,
against this terminal's -77.83) price **95.45 to 107.40** - they buy the crossing with 52-53 herd
frames. Two others reach **71** herd frames, fewer than the winner's 72, and hand back 158-221 u of
gap. [the-crossing-and-the-runway-are-one-resource](the-crossing-and-the-runway-are-one-resource.md)
holds; what changed is that a cut, not a distance, was hiding the three frames.

**What it costs to find, and what to price next.** 1042 s for the widened c2 stage plus 7892 s of
per-node cycle-3 pricing - and the six cuts priced flat before this one all act on the gap term (4.89
f, 5.6% of the bound) while this one was the first inside the herd (79%). The remaining unpriced
selections are also inside the herd: the cycle-2 probe pool (400 of 424-5616) and cycle 1's beam
(8 parents, 4 produce).
