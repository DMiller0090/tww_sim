# Price a cut in both directions before building it a better rank

**Answers:** My search named its binding cut and I am about to build it a better rank - what do I
measure first? Can a cut be load-bearing and still hide no frames? How do I price a cap without
designing the new rank / how do I perturb a selection without inventing a new criterion / when does
a null result retire a whole TERM of the bound instead of one knob?
**Status:** measured, session 139, the cycle-3 stage of the deep-plow route at s136's knobs (terminal
facing 40660 / thrust 11, +-8.44 deg window, freed axis, floor 160). Two runs, one knob each: a
DISJOINT runner-up 250 loses **+7.57 frames** (97.39 vs 89.82), and cap **500** at the shipped orders
returns **89.82 bit-identical**, same winner. The pool binds downward and hides nothing upward -
and with it every screen-side knob since s135 is priced flat, on a term whose ceiling is **4.82
frames** while the herd holds **72 of 89.82**.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`_probe_pool`,
`_mixed_beam`, `extend_cycle`), [`harness/tetrapush/handoff.py`](../../harness/tetrapush/handoff.py)
(`endpoint`, the bound's terms). Probe `_notes/s139_pool_price.py` (both modes), logs
`_notes/s139_pool_price.log` / `_notes/s139_cap500.log`, beams
`_generated/s106/s139_c3_altpool_t11_f40660.json` / `s139_c3_cap500_t11_f40660.json`.

## A named cut has two prices, and only one of them is money

Session 138 ended with the probe pool as THE named cut: the junction admits 1258-9604 endpoint
children per producing parent and `_probe_pool` passes 250 to the screen
([the-biggest-death-counter-was-the-alphabet](the-biggest-death-counter-was-the-alphabet.md)). The
reflex is to build it a better rank. The measurement that comes first is cheaper than the rank and
decides whether the rank is worth building, and it is TWO runs, not one, because a cut binds in two
independent directions:

- **Perturb the selection** (hold the cap, change WHICH 250): does a different slice lose frames?
  This prices whether the cut is LIVE - whether the bound depends on the selection at all.
- **Widen the cap** (hold the orders, change HOW MANY): does more of the same selection gain frames?
  This prices whether the cut is HIDING anything - the only direction that pays.

| run | pool | bound | vs 89.82 |
|---|---|---|---|
| s136/s137 (reference) | shipped mixed keep, 250 | **89.82** = 72 herd + 81.89 u gap + 13 cut | - |
| runner-up slice | the NEXT 250 by the same orders, disjoint | **97.39** = 79 + 91.70 u + 13 | **+7.57** |
| widened cap | shipped orders, **500** | **89.82**, same winner (l0 +15.48, runway 179) | **-0.00** |

A cut can be strongly load-bearing (a careless re-selection costs 7.57 frames) and still hide
nothing (doubling it returns the bound to the last digit). Only the second run answers the question
the rank would be built for. If only the first had run, its verdict - "the pool binds" - would have
launched the build; the second is the refutation of the build's upside at a third of the build's
cost.

## The perturbation that proves the first price without inventing a criterion

The runner-up pool is the shipped `_probe_pool` applied one slice down: compute the shipped 250 with
the UNTOUCHED function, exclude it by identity, apply the same function to the remainder. No new
constant, no new order - the same three-order mixed keep (flatness prefix, `l0` share,
junction-frame round-robin) choosing from the population minus its own first choice. Disjointness is
asserted per parent, so the run is a different-250 by construction, not by hope.

Note `_mixed_beam` is NOT prefix-stable across caps (each order's share is `beam // len(orders)`, so
pool(500) is not pool(250) plus 250 more of a single list) - which is why the disjoint slice is
built by exclusion rather than by `pool(2*cap)[cap:]`, and why the cap-500 run is honestly "more of
each order" rather than a superset test.

The self-checks come free and both fired correctly: the five junction death counters (`ENDPOINT`
73070, `in_cone` 314542, `outbox` 6576, `unarmed` 429724, `wall` 26304) are byte-identical across
all three runs - they MUST be, the pool sits below the junction, the s138 plumbing lesson run in the
expected direction - while the roll-stage counters (`aim_followed`, `aim_wall`, `unrollable`) move
with the pooled set.

## What the runner-up population lacks is not rollability and not `l0`

The next 250 per parent still roll broadly (94-250 of 250) and their screened `l0` frontier is
comparable or better (best +130.35 against the shipped slice's +120.87 on the same parent). What
collapses is the handoff: 60 of 450 survivors park her onside and 48 admit an entry curve, against
102 of 426 and 102 for the shipped slice - and the best surviving family starts at 79 herd frames
against the winner's 72. So the shipped orders' first slice is not winning on the axes the orders
rank by; it happens to contain the endpoints whose rolls PRICE well at the terminal. That is one
more instance of
[the-window-binds-on-the-parents-that-produce](the-window-binds-on-the-parents-that-produce.md)'s
lesson that the screen's rank and the stage's objective are different axes - and the cap-500 null
says exploiting it with a gap-denominated rank has nothing above index 250 to surface on this beam.

(The runner-up run's own winner sits on the first handoff rung, runway 159 at floor 160 - a wider
rung set could shave its 97.39, but that family's floor is 79 + 13 = 92 with the gap at ZERO, still
above 89.82, so the +7.57 verdict does not ride on the rung floor.)

## The null retires the screen, not just the knob

Every screen-side lever between the junction and the terminal has now been priced on the same beam
at the same terminal: the fan window at `max_delta` (s137, 0.00), the runway floor 160/170 (s137,
0.00), the arming bar (s138, arithmetic - the gate above a 97%-discarding pool), the `l0` frontier
doubling (s137, 0.00), the pool's selection (s139, only losable) and the pool's cap (s139, 0.00).
The bound's own decomposition says why that had to be cheap: **89.82 = 72 herd + 4.82 gap + 13
cut**, so the whole screen acts on 5.4% of the bound, and even a gap of literal zero only reaches
72 + 13 = 85. The frames are in the herd's 72, and the way at them is this same instrument moved one
stage up: perturb what the CYCLE-2 beam hands the junction - its 16 survivors, its keeps - and see
whether the 72 depends on it. (Session 140 did: it does not - the cycle-2 final cut prices 0.00 both
ways because its population is twins - and the free census that bounds any such pricing BEFORE the
run is [count-the-states-before-pricing-a-cut](count-the-states-before-pricing-a-cut.md).)
