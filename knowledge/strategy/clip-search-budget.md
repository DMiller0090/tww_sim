# What a razor clip search costs, and where the budget actually goes

**Answers:** My entry sweep is too slow to run at the resolution the razor needs - what is actually
eating the time? Do I have to simulate the roll to score it? When does a compiled context stop being
reusable, and what do I do then? Can the sweep move onto the native fleet, and why won't it run from
the run's own start? Why is the fan re-walking paths it already walked, and what do I do when the
pass runs out of RAM before it runs out of clock? I bought 10x the prefix families and got 1.9x the
draws - what did I widen into?
**Status:** validated offline (sessions 80-84, extended session 94 with the per-shape draw rate) on the
flooded-Hyrule Tetra corner; every figure below is a measured before/after on that search. Gated in
[`tests/test_entry_search.py`](../../tests/test_entry_search.py) +
[`tests/test_entry_fan.py`](../../tests/test_entry_fan.py). Companion to
[clip-entry-search.md](clip-entry-search.md) (the method) and
[clip-lottery-draws.md](clip-lottery-draws.md) (how to count what it returns).
**Source:** `harness/tetrapush/entry_search.py` (`fast_schedule`, `build_fast`, `CtxPool`),
`harness/tetrapush/entry_fan.py` (`graft`, `iter_fan`, `stick_alphabet`),
`harness/tetrapush/entry_score.py` (`stream_search` `dedup_scope`), `tww_sim/core/_shovec.ShoveCtx`.

---

## The budget is the context build, not the alphabet

The instinct is that a sweep costs its alphabet. It does not: it costs **compiling one context per
`(facing, lean, thrust, momentum)`**, and the alphabet only decides how many of those you need.

Simulating a roll to read its schedule back was 22 ms here, and all of it was a 17-frame coupled
Python roll producing numbers that never depended on the world. The schedule is a pure function of the
configuration: speed is the roll's constant momentum, travel equals facing on every frame including
the cut entry, the animation frame control is a fixed accumulation, the lean decays deterministically,
the Co chain is a direct evaluation on (facing, frame, lean), and the cut lunge is a constant root
translate rotated by the facing. Evaluating it directly ran **~110x** faster, 0-ULP identical - and,
applied to the Newton solve inside the band measurement, took qualifying 243 configurations from 269 s
to 4 s.

## Keep the world, swap the schedule

Even analytic, a context is not free, and everything expensive in it is the compiled **world** - the
culled mesh, its planes, the precomputed wall-correction slices - none of which depends on the roll.
That is affordable while the configuration key is coarse enough for a fan to reuse a context many
times. It stops being affordable the moment the key grows: the lean already made it marginal, and the
momentum made it hopeless - a full-resolution pass carries nearly one momentum per candidate and would
spend hours recompiling one unchanging courtyard.

So keep one context per (facing, thrust) and **swap only the baked schedule** on it: 1.52 ms to build,
0.16 ms to re-schedule, ~10x. Gate it by sweeping a re-scheduled context against one BUILT at that
configuration - same genuine flag, same endpoint, same push, same residual - rather than trusting that
you restored every field.

## Moving the fan to the native fleet needs a graft, not a seed

Once the context build is analytic, the **fan** is the whole cost (43596 candidates: 1444 s of fan
against 11 s of evaluation), and a fan is just the same coupled frame stepped many times - which is
what a native OpenMP fleet is for.

The trap is that it usually cannot run from the run's own start. A stripped search engine (no wired
camera / look / neck models) will not reproduce a WIRED replay of the setup that got you here; on this
corner it diverges 19 frames in, on `facing`, because a lock-on re-aim falls back to the target's feet
where the wired run has its modeled eye position. So replay the setup in the wired engine and
**graft** the mid-walk state into the native core.

Grafting is the whole job. A core seeded for a run's *start* resets the mid-walk physics scalars -
stick want-angle, chase target, stick magnitude, direction, roll frame control, the previous frame's L
- and restoring those, plus the delay-1 controller buffer, is what makes the transplant bit-exact.
Whatever the core cannot reach (private fields) must be argued inert **and gated**, not assumed.

Gate the whole thing by re-running the reference fan's own output **key-for-key**: here that was 43596
candidates in 17 s against 1444 s, identical. Write order is part of that contract - the reference
collapses ~5.5M writes onto 43596 keys and the last writer wins, so a chunking that reorders the
writes gives the right key SET and a different value per key.

## The alphabet you SPEND is redundant too

Once the fan is the budget, audit what the fan is *made of*. A held stick reaches the walk only
through the main-stick decode, so two byte pairs with the same `(angle, mStickDistance)` bake a
bit-identical walk - same endpoint, same lean, same speedF, for as long as it is held. The octagon
clamp and the dead zone make that the common case rather than a corner one: the full 256x256 grid is
**65536 byte pairs and 11405 draws**, one class holding 1944 members.

So a fan enumerating BYTES buys 5.75 frames of fleet per frame of new physics - and worse than that
average, because the classes that survive a walk-cap prune are exactly the saturated ones with the
most members. Collapsing both segments of a two-segment pass onto the decoded alphabet reproduced its
near-misses **gap for gap in 48 s against 220 s**, and 25x fewer writes streamed.

The tell is a dedup ratio that outruns the physics: if a fan streams far more writes than it has
distinct endpoints, most of its cores are re-walking a path some other core already walked. This is
the same lesson as counting a scored axis in the unit the code reads
([clip-lottery-draws.md](clip-lottery-draws.md)) - it is just worth more here, because the scored
alphabet costs an evaluation and the spent one costs a simulation.

Two things to keep right when collapsing:

- **Pick the representative for delivery.** Every member of a class is the same physics, so choose the
  one that survives authoring: `dtm_make` rewrites 0 and 255 to 1 and 254
  ([`[[octagon-clamp-decode-bug]]`](../mechanics/walk-run.md)), so prefer an interior byte pair
  wherever the class offers one.
- **Gate the candidate SET, not the plans.** The collapsed fan must reach exactly the keys the byte
  grid reached. The plan each key carries may differ: two genuinely different sticks can land on one
  endpoint, and which one is the last writer depends on the order the alphabet is enumerated in.

## The memory ceiling arrives before the time one

Speed moves the wall rather than removing it. With the fan 5.75x cheaper, the binding constraint on
this search became the pass's **global dedup key set** - about 200 B a candidate, so a 10M-candidate
pass is the whole machine, and it hits that hours before it hits the clock.

The way out is to notice that a fan streams **family-major** and nearly all of its repeats are inside
one family. Scoping the key set per family bounds memory at one family's worth and re-evaluates only
the handful of endpoints two prefixes genuinely share - and evaluation is a few percent of a pass
where the key set is all of its memory. Nothing is double-counted as long as the near-misses carry
identity and are deduped on the draw before anything is reported
([clip-lottery-draws.md](clip-lottery-draws.md)), which makes the reported population identical to a
globally deduped pass. The pass is then as wide as the clock allows rather than as wide as RAM allows.

## A FAMILY is a budget unit only inside one plan SHAPE

Draws scale with prefix families rather than with candidates, so "buy more families" is the natural way
to spend a bigger clock. It is only true within a fixed plan shape. Measured at the frame floor on this
corner, near-misses per family by the plan's own `(base frames, first hold)`:

| shape | families | rate |
|---|---|---|
| `j1 = 2` (the delivered shape's own) | 1713 | **0.032 / family** |
| `(n0 1, j1 1)` | 2781 | 0.0025 / family |
| `(n0 0, j1 1)` and `(n0 2, j1 1)` | 5542 | **0** |

So a pass widened from `j1=2, nbase=2` to `j1=1,2, nbase=3` went from 1012 families to 10036 - a 9.9x
buy - for **1.9x the near-misses**, because 5542 of the new families are shapes that have never produced
a draw and the cumulative rate fell 5.2x. The same clock spent at stride 1 on `j1=2` alone buys *fewer*
families and more draws. Two consequences:

- **Report the rate per shape, not per pass.** A pooled `near/family` over shape-mixed families is an
  average over populations with rates differing by more than 10x, and it moves when the mix moves rather
  than when the search does. The `subgrid_rate` readout inherits this: it reads a coarser pass out of a
  finer one honestly, but only if both are the same shape.
- **Price a shape before widening into it, the same way an axis gets priced.** One pass per shape is
  cheap and the answer is stable across strides here (0.032/family at both stride 4 and stride 2), so
  the exclusion is then a *measurement* rather than an assumption
  ([razor-prices-every-term.md](razor-prices-every-term.md#the-rules) rule 13).

## What the throughput is worth, and what it is not

Each step above removes a *different* bottleneck rather than compounding on one: 110x off the context
build, 10x off re-configuring a kept context, 85x off the fan. They are worth having - they are what
let an axis be priced at all, and what turns a re-run from an afternoon into four minutes.

They are **not** progress on the search. The first thing the native fan bought was the discovery that
the fan was never the binding constraint ([clip-lottery-draws.md](clip-lottery-draws.md)): 83% of that
pass's draws sat at a dead lean, and every one-segment pass from 14529 to 391446 candidates returns the
same three near-misses, gap for gap. Buy the throughput because measurement is cheap at speed - not
because a bigger pass is a better pass.
