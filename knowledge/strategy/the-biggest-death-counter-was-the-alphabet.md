# The biggest death counter was the alphabet, not the wall

**Answers:** My search's largest death counter is byte-identical under every knob I try - is that the
thing that binds? How do I tell a refusal that binds from one that is just arithmetic? Is my arming
(or entry) threshold clipping a reachable tail, and what does relaxing it cost? Why can a counter be
huge and still be worth nothing to attack?
**Status:** measured, session 138, over the whole cycle-3 junction stage - 16 parents of the
deep-plow cycle-2 beam, 124 s. `unarmed` **429724** does not bind. The same stage ADMITS **73070**
armed endpoint children - **1258-9604** on each of the 13 parents that produce at all - into a probe
pool that takes **250**. The refused population is **97.77%** never-flipped, a 28-unit hard floor below
the bar, and **2.23%** flipped-but-just-short, whose rolls are weaker by exactly `1.5 x deficit`
u/frame. Self-checked: the census reproduces `unarmed` **429724** to the count.
**Source:** [`harness/tetrapush/two_roll.py`](../../harness/tetrapush/two_roll.py) (`junction_gates`'
`min_preroll` probe), [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`junction_beam`, `junction_alphabet`, `extend_cycle`),
[`tww_sim/land/procs/roll.py`](../../tww_sim/land/procs/roll.py) (`_roll_init`, the clamp that sets
the bar). Probe `_notes/s138_unarmed_census.py`, census `_notes/s138_unarmed_census.json`.

## The counter was byte-identical because the stage takes no screen knob

Sessions 136 and 137 changed the fan window and the runway floor and reported that five junction
counters did not move a single count, `unarmed` **429724** among them, and read that as arming
refusing equally hard under both screens. The counters are real and the reading was not: `probe_half`
and `handoff.RUNWAYS` are arguments to the ROLL stage and the chain-back, and `extend_cycle` passes
neither into `junction_beam`. The junction is a deterministic function of the parents and the
alphabet, so its counters were identical **by construction**. Byte-identity across a knob the stage
never sees is evidence about the plumbing, not about the mechanic.

**The general form: before reading a counter's stability as a wall, check that the knob you moved
reaches the stage that raises it.** A stage that ignores the knob will always answer twice the same.

## What the refused population actually is

`junction_gates` arms on a 1-frame NEUTRAL probe reading `speedF >= 17.0`. That is a scalar, so the
refusal has a distribution, and it is two populations, not a tail:

| probe `speedF` | children | share of refused | what it is |
|---|---|---|---|
| -26.0 .. -10.0 | **420144** | **97.77%** | never flipped - still gliding backwards |
| +12.0 .. +17.0 | **9580** | **2.23%** | flipped, landed under the bar |
| **>= +17.0** | **73070** | - | **armed** (the stage's endpoints) |

Best refused **+16.998**, worst armed **+17.000**: nothing lives in between, because the bar is
exact. The gap between the two refused populations is real too - the never-flipped floor tops out at
**-11.088** on the parents that have no flipping tail at all, twenty-eight units short.

Per generation the armed share rises 0% -> **18.12%** (jf 7) and settles near 14%, while the
never-flipped best is flat at -11.4 the whole way: that population is not closing on the bar, and no
extra depth brings it in.

## The bar's price is exact, and the bar sits on the knee

`_roll_init` sets the roll from the pre-roll speed as `clamp(speedF * 1.5 + 0.5, 5.0, 26.0)`, so
`min_preroll = 17.0` is not a tuned constant - it is exactly where the clamp saturates. Below it the
roll is continuous, and **each 1.0 of arming deficit costs exactly 1.5 u/frame of roll speed**:

| refused band | children | roll it would fire | cost vs the clamp |
|---|---|---|---|
| +16.0 .. +17.0 | 5677 | 24.50 - 26.00 | <= 5.8% |
| +12.0 .. +16.0 | 3903 | 18.50 - 24.50 | <= 29% |

So the bar refuses 5677 children whose rolls are at most 5.8% weaker, and the closest of them miss by
**0.003 u/frame** (banked: the best 200 refusals all sit above +16.939). Physically that cut is
arbitrary. It is still not worth relaxing, for a reason that has nothing to do with arming - below.

## Why widening it cannot buy anything: the pool already discards 97%

The stage's own arithmetic closes it. A producing parent hands **1258-9604** endpoint children to the
dedup and `_probe_pool`, which passes **250** of them to the screen - **2.6-2.9%** on the big
producers. Relaxing the bar to +16.0 adds **7.8%** more endpoints, every one of them a strictly
weaker roll, to a selection that already throws away **97.1%** of the stronger ones. The binding cut
is the pool, not the gate above it.

## A pending L cannot arm, and that is the decomp saying so

The letter cross-tab is exact and it is a zero:

| pending letter | children | armed | rate |
|---|---|---|---|
| any stick, **L released** | 251397 | 36535 | 14.53% |
| the same sticks, **L held** | 251397 | 36535 | 14.53% |
| the toward-Tetra arming stick | 1837 x 2 | 676 x 2 | **36.80%** |

Holding L on the delivered frame changes the arm verdict for **not one child**. That is
`chaseAttention` (`d_attention.cpp:563`): a target is only acquirable inside the +-90 deg front cone,
and every child that reaches this probe is out of that cone by the gate immediately above it
(`in_cone`). A fresh L cannot acquire what a junction endpoint is defined as facing away from, so the
lock that routes the flip must already be inherited. Arming is a posture carried IN, never bought on
the last frame - which is also why the toward stick helps (36.8% against 14.5%) without deciding
anything: the stick chooses whether the inherited posture fires, and the posture is chosen cycles
earlier.

## What it leaves

Three of the sixteen parents produce **zero** endpoints (one of them puts no child in front of the
probe at all). They are not near misses: their refused populations top out at -11.4 to -11.5,
twenty-eight short, with no flipping tail. No threshold reaches them either.

So arming is not a prune to widen, not a posture buyable at the junction, and not the wall - it is
the alphabet's arithmetic, ~274 letters a node of which about one in seven arms. What the census
points at instead is the cut that actually decides which endpoints exist, the 250-of-9604 probe pool,
whose rank is on an axis
[the-window-binds-on-the-parents-that-produce](the-window-binds-on-the-parents-that-produce.md)
already showed does not predict the objective.

And the bound's own arithmetic says how much is there to win: **89.82 = 72 herd frames + 4.82 frames
of gap (81.89 u at the 17.0 u/f walk cap) + 13 of cut**. Every screen-side knob priced since session
135 - window, runway floor, probe pool, `l0` frontier - acts on the gap term alone. That term is
**5.4%** of the bound. The herd is 80%.
