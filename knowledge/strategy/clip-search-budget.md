# What a razor clip search costs, and where the budget actually goes

**Answers:** My entry sweep is too slow to run at the resolution the razor needs - what is actually
eating the time? Do I have to simulate the roll to score it? When does a compiled context stop being
reusable, and what do I do then? Can the sweep move onto the native fleet, and why won't it run from
the run's own start?
**Status:** validated offline (sessions 80-82) on the flooded-Hyrule Tetra corner; every figure below
is a measured before/after on that search. Gated in
[`tests/test_entry_search.py`](../../tests/test_entry_search.py) +
[`tests/test_entry_fan.py`](../../tests/test_entry_fan.py). Companion to
[clip-entry-search.md](clip-entry-search.md) (the method) and
[clip-lottery-draws.md](clip-lottery-draws.md) (how to count what it returns).
**Source:** `harness/tetrapush/entry_search.py` (`fast_schedule`, `build_fast`, `CtxPool`),
`harness/tetrapush/entry_fan.py` (`graft`, `iter_fan`), `tww_sim/core/_shovec.ShoveCtx`.

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

## What the throughput is worth, and what it is not

Each step above removes a *different* bottleneck rather than compounding on one: 110x off the context
build, 10x off re-configuring a kept context, 85x off the fan. They are worth having - they are what
let an axis be priced at all, and what turns a re-run from an afternoon into four minutes.

They are **not** progress on the search. The first thing the native fan bought was the discovery that
the fan was never the binding constraint ([clip-lottery-draws.md](clip-lottery-draws.md)): 83% of that
pass's draws sat at a dead lean, and every one-segment pass from 14529 to 391446 candidates returns the
same three near-misses, gap for gap. Buy the throughput because measurement is cheap at speed - not
because a bigger pass is a better pass.
