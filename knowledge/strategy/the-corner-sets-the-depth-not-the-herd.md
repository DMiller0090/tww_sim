# The corner sets the depth, not the herd: the terminal configuration asks for alignment

**Answers:** My clip needs a razor-thin overlap on one frame and my push produces whatever it produces
- can a pushing roll ever arrive at that depth? Do I have to place the pushed actor precisely before
the last roll? Can the last push roll BE the clip roll, or must the pusher back off and come in clean?
Does the body lean rule some approaches out?
**Status:** MEASURED (session 124) on the flooded-Hyrule Tetra corner at the delivered facing 40835 /
thrust 14, over a 1540-cell handoff box (`runway` 140-480 u x `along` 30-245 u), with the razor solved
per cell rather than gridded. 51 genuine terminal configurations, 13 of them in unbroken contact.
**Source:** [`harness/tetrapush/terminal.py`](../../harness/tetrapush/terminal.py) (`RollFrame`,
`razor_crossings`, `solve_razor`, `genuine_band`, `solve_cell`, `scan`, `classify`),
[`harness/tetrapush/razor_depth.py`](../../harness/tetrapush/razor_depth.py) (`contact_required`,
`brace_point`), gate [`tests/test_terminal.py`](../../tests/test_terminal.py).

---

A seam clip here is bought with a **push**: the roll's own lunge lands ~0.75 u short of threading the
gap, and the cylinder-vs-cylinder shove from the other actor bends it the rest of the way. The shove is
half the overlap on the frame the cut consumes, so the clip names a depth - and the natural fear is that
a *pushing* roll cannot deliver a razor-thin one, because a plow's depth is whatever the plow produces.

**It is not the plow's to produce. It is the corner's.** Once the pusher is braced in the corner and the
pushed actor has been shoved up against him, the pair converges to a fixed terminal state and forgets how
it got there. Over handoffs **50-245 u** apart, with the roll plowing her anywhere from **53 to 126 u**:

| | measured spread over 51 genuine configurations |
|---|---|
| overlap on the frame the cut consumes | **1.1257 - 1.1328 u** |
| the last three overlaps | 18.3 / 18.4 / 13.7 → 6.76 / 6.75 / 6.70 → **1.132 / 1.132 / 1.127** |
| her position at the cut frame | a **0.054 x 0.205 u** box |
| the pusher's braced point | constant to **0.001 u** |
| where the cut lands | inside **0.003 u** |

Two things follow, and they are the whole shape of the endgame.

**The last push roll can BE the clip roll.** 13 of the 51 have the pusher *already touching her when the
roll starts* and contact never breaking for a single frame up to the cut - the full roll animation in
contact - at handoff distances **50-110 u**, which is the range a herd already oscillates over (41-85 u
measured live). There is no walk-away, no walk-back and no separate clean roll-in.

**The herd does not have to place her.** Her cut-frame position is an attractor, so precision spent
positioning her before the last roll is spent twice: the roll parks her. What the herd must deliver is
the pair's **lateral alignment** - how squarely the roll passes her - because that is the only axis the
answer is sensitive to:

    d(resid)/d(lateral)  -4.0 to -14.3 /u        d(overlap)/d(lateral)  ~-15 /u
    d(resid)/d(runway)             +0.17 /u      d(overlap)/d(runway)     +0.64 /u

Sliding the pair up and down the approach barely moves the answer. **Depth is not a lever and alignment
is the only one.**

## What this costs to find, and why a sweep will not find it

The acceptance band is **2.2e-5 to 1.5e-4 u** wide against those gradients, four orders of magnitude
finer than any affordable grid. So the grid's only job is to **bracket the sign change** of the razor
residual, and the answer comes from bisecting it - `razor_crossings` → `solve_razor` (all brackets in
lockstep, one batch sweep per round) → `genuine_band` (walk the f32 band). The module's own 281-sample
bracketing grid returns **nothing** at a cell that clips, which is gated so that a future "swept it,
found nothing" cannot be believed without clearing the same bar. A sweep is a lottery here whatever its
step, and the odds are the band width over the step.

## The body lean shifts the razor and never closes it

[`entry_search`](../../harness/tetrapush/entry_search.py) records that `m351C` 0 and 1 clip while **64
already does not** (`resid` 1.1e-2). That is measured at a **fixed entry**, where 1.1e-2 is a hundred
window widths - it says the lean must be **re-solved**, not that it is a bar. Re-solving the lateral
finds genuine terminal configurations at **every lean from -191 to +191**, most of them in unbroken
contact, including the +64 that reads dead at a fixed entry and the -191 a replayed herd actually hands
over. The lean also decays on its own
([`LandState.SLANT_DECAY`](../reference/constants.md#land-movement)), reaching 0 in 13 undriven frames -
so the same long brakeslide that buys the runway flattens it.

## Reading a configuration

`terminal.py` states a configuration in the roll's own frame, because that is what a herd hands over -
a **pair**, not a placement:

    entry  = brace - runway * m            the pusher at the end of the roll-entry frame
    tetra  = entry + along * m + lat * q   where the previous roll left her

`along` is the handoff distance; `runway` is how far back the roll starts, which a longer-than-normal
untarget brakeslide buys; `lat` is the razor. `classify` adds the facts a plan is chosen on - whether he
starts touching her, whether contact ever breaks, and how far the roll plows her.

See [clip-razor-depth.md](clip-razor-depth.md) for the depth law this measures the other side of, and
[../mechanics/actor-push.md](../mechanics/actor-push.md) for the push itself.
