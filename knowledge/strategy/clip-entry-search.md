# Solving for the roll ENTRY instead of the target's position

**Answers:** A push-assisted seam clip needs a pushed actor on a razor-thin "genuine" spot. What do I
do when that actor is already placed and I cannot move her - can I solve for Link's roll entry
instead? Which quantity is the razor, and what precision does hitting it need? Why does the
perpendicular half of a placement miss decide a clip that a nearest-sample distance says is 0.4 u
away?
**Status:** validated offline (sessions 79-83) on the flooded-Hyrule Tetra corner: the acceptance
window is measured off a live-anchored 288-sample list, the entry locus re-derives that list's own
endpoint, and the roll the sweep scores is gated bit-identical to a real A-press roll out of a walk.
Gated in [`tests/test_entry_search.py`](../../tests/test_entry_search.py) +
[`tests/test_entry_fan.py`](../../tests/test_entry_fan.py). No hit has been DELIVERED yet (no DTM
confirm). **How to size such a search honestly is
[clip-lottery-draws.md](clip-lottery-draws.md); read it before buying more candidates.** What one
costs is [clip-search-budget.md](clip-search-budget.md). Premises this page carried in sessions 79-81
were overturned by measurement
and now live in [history/entry-search-s79-superseded.md](../history/entry-search-s79-superseded.md),
[history/entry-search-s80-superseded.md](../history/entry-search-s80-superseded.md) and
[history/entry-search-s81-camera-lever.md](../history/entry-search-s81-camera-lever.md).
**Source:** `harness/tetrapush/entry_search.py`, `harness/tetrapush/entry_fan.py`,
`harness/tetrapush/roll_fidelity.py`, `harness/rollstab/turnaround.py`,
`harness/rollstab/geometry_tetra.genuine_clip`, `tww_sim/core/_shovec.ShoveCtx`. Constants:
[reference/constants.md](../reference/constants.md#collision-player-wall-cylinders).

---

## The two duals of one acceptance

A push-assisted clip ([seam-clip.md](../mechanics/seam-clip.md),
[actor-push.md](../mechanics/actor-push.md)) accepts on a function of **both** actors: the cut segment
has to thread the corner gap, and the pushed actor's CC shove is what steers it there. So the same
acceptance can be swept two ways:

| sweep | fixed | free | produces |
|-------|-------|------|----------|
| **placement** | Link's roll entry + facing | the pushed actor's spot | the "genuine coord" list |
| **entry** | the pushed actor's spot | Link's roll entry + facing | the **entry locus** |

The placement sweep is the natural one while you can still put the actor anywhere. Once a herd/route
has *delivered* her, she is a measured constant and only the entry sweep is available. It is the same
native sweep either way - the entry position is a per-sample parameter, and the baked roll schedule is
**entry-position-invariant** (the roll's displacement/cut/pose stream is momentum-driven), so one
compiled context maps the whole entry plane.

## The razor's smooth coordinate

Do **not** reach for the seam planes. `genuine_clip` needs three things - `old` in front of both
walls, the segment `old -> new` unblocked, and `new` behind a wall - and the *plane* values at the cut
endpoint are negative over almost the whole region, so they separate nothing. The razor is the
**segment** test, so the coordinate to use is the cut ray's signed offset from the seam vertex `S`:

    pred  = old + roll_step + push + cut_lunge        (the pre-CrrPos endpoint, decomp posMove order)
    resid = cross(pred - old, S - old) / |pred - old|

`resid` is smooth in the entry, in the facing and in the push; `genuine` is f32 dust inside a hair of
`resid == 0`. That gives the working method: **sweep the residual coarsely, keep what is near zero,
and only then resolve the dust.** A blind fine sweep does not work - on the Tetra corner a 0.25 u grid
over a 120x120 u box found 1 genuine entry in 231361 samples.

## Measure the acceptance window; never assume it

The window is not a modelling choice - it is measurable against any existing live-anchored list. Score
that list through the same context and read off the residuals of the members that clip. On the Tetra
corner the 279 (of 288) tabulated coords that still read genuine sit in

    resid in [-2.52e-6, +1.13e-4] u     -- width 1.16e-4 u

which is about **one f32 ULP** at that distance from the origin. That is why such lists are dust and
not regions. The 9 members that do *not* read genuine sit *inside* that band, so the window is a
**dust edge to aim with, never an acceptance test** - only the sim's own `genuine` decides.

## The perpendicular half of a placement miss is the one that matters

A route's placement objective usually scores *distance to the nearest tabulated sample*. That number
is a poor predictor of a clip, because the genuine set is a thread: a miss **along** the thread is
free and a miss **across** it is fatal. Split it before believing it.

On the Tetra corner the delivered herd put her 0.4321 u from her target coord - of which **0.0240 u
along** the thread and **0.4314 u perpendicular**. So the herd's own entry, standing exactly on the
entry the list was tabulated for, misses the seam by 0.3139 u of residual: **2707x the window**. The
route that "walks Link to the tabulated entry" fails on its premise, not on walk precision.

## What actually moves the residual: the CUT-FRAME push

When the roll ends against the corner, `CrrPos` pins Link at the *same* wall-braced `old` almost
regardless of where the roll started. So the entry does **not** move the residual directly - it moves
it only through whether the pushed actor is still overlapping Link on the frame the cut fires:

- push `0` -> the bare roll-stab, which on this corner lands **0.33 u short** of threading;
- too much push -> overshoots the gap the other way;
- the genuine band is a narrow push, and the entry is what dials it.

The corollary is a trap worth knowing: **at an entry where the actor is out of Co range by the cut
frame, no knob moves anything.** Probe lines through such a point read a dead-constant residual, which
looks like "the entry has no leverage" when it actually means "there is no push to modulate here."

## Precision, and why it is a density problem

The precision a search must hit is `window / |grad resid|`. On the Tetra corner that is
`1.16e-4 / 1.196 = 9.7e-5 u` - one ULP. You cannot aim at that; you count your way into it. So the
figure of merit is **how many candidates land near zero, and how finely spaced their residuals are
there**: `P(a near-zero candidate is genuine) ~ window / local spacing`. Measure that spacing **at one
facing, over the candidates that actually reach near zero** - not over "the N closest by |resid|",
which are clustered and give an answer that is too good.

Counting those draws honestly is [clip-lottery-draws.md](clip-lottery-draws.md) - get it right first;
on this corner it moved the same pass's expected yield by 12x, downward.

Do not assume the loci are all equally productive: only the aims whose locus threads the candidate
cloud produce anything, so scan wide once, cheaply, to find the productive band, then spend the budget
on candidates.

And **rank the signed distance to the window, not |resid|**. The window is asymmetric because its sign
is which side of the gap the ray passes on, so |resid| scores a blocked-side near-miss as highly as a
real one. The Tetra pass's best candidate was -5.45e-5: inside the window's *width*, on the wrong side
of it.

## Sweep the entry the game hands you, not the one the walk ends on

A reseeded `FRONT_ROLL` advances its animation frame control on its first step. A **real** roll's
entry frame does not: `_roll_init` runs, and the frame after it is where the animation starts moving.
So the reseeded schedule's step 0 is the real roll's *second* frame, and the entry position a compiled
context wants is the one at the **end** of the entry frame:

    entry = walk_endpoint + one roll step at the AIMED facing        (26 u at the walk cap)

and the lean is likewise the post-entry-frame value (one decay tick past the walk's). This is decided
by measurement, not convention: feeding the pre-entry values mismatches the pose-chain tables outright,
while the post-entry values reproduce a real A-press roll bit-for-bit.

That step is the roll's own momentum, `clamp(1.5 * speedF + 0.5, 5, 26)` off the **walk endpoint's**
speed - 26 only because the cap saturates the clamp, measured bit-for-bit against a real A-press out
of a decelerating walk at five sub-cap momenta. A sub-cap roll bakes the same schedule with `dx`/`dz`
scaled and nothing else; whether those extra loci are worth searching is a separate question with its
own answer ([clip-lottery-draws.md](clip-lottery-draws.md)) - here it was no. And the step is taken
**along the aim**, which is what makes an aim its own candidate as well as its own locus.

## The multipliers, and the UNIT they have to be counted in

The figure of merit is candidates x **independent loci**. A locus is independent whenever the baked cut
schedule changes - and the schedule changes in the units the console's maths quantizes to, which are
coarser than the ones you are sweeping in.

- **the aim, whose atom is the console sine-table CELL - 16 BAM, not 1.** `cM_ssin_s16` is JMASSin,
  `jmaSinTable[(u16)angle >> 4]`, 4096 entries with no interpolation
  ([model/fp-faithfulness.md](../model/fp-faithfulness.md)), and *every* term a roll facing reaches
  goes through it: the per-frame travel, the cut lunge's rotation, the Co pose chain, and the entry
  step. Two facings in one cell bake a bit-identical schedule at a bit-identical entry and are ONE
  draw. So sweep the alphabet - the roll needs no stick magnitude, it takes its whole speed from the
  walk cap and `_roll_init` snaps facing to the latched target whatever the deflection, so the
  alphabet is the full decoded-angle grid rather than the saturated octagon boundary - and then
  **collapse it onto cells before counting**. On the Tetra corner 81 realizable aims are 49 cells.
  Fire each one and read the facing back before believing it.
- **the thrust step.** The B edge can dispatch the cut at more than one roll frame (13/14/15 here).
  Each lands the cut on a different step and reads a completely different residual at the same entry,
  so each is its own draw.
- **the camera is NOT one**, though it was counted as the biggest of the three for two sessions
  ([history/entry-search-s81-camera-lever.md](../history/entry-search-s81-camera-lever.md)). Moving
  `csangle` shifts the whole alphabet, which looks like a way to reach the aims a frozen camera misses
  at zero frame cost (the C-stick is a free channel during the walk-in and `csangle` is
  position-independent there, so one measured stream serves a whole fan). But it can only reach a new
  **cell**, and here the frozen camera's four aims already covered both cells the productive window
  contains - which is why that window is 32 BAM wide and worth two draws. Priced end to end it read
  exactly 8.00x, and every extra near-miss was an existing one re-counted.

An aim is still worth firing at full byte resolution, for a different reason: it is not only its own
locus, it is its own *candidate*, because the entry step is taken along it. And the entry FRAME is not
cell-quantized - it compares raw s16 angles - so two aims in one cell can differ in whether the walk
brakes before the roll dispatches. Same locus, different momentum.

What a search of this shape COSTS - why the context build and not the alphabet is the budget, when
to stop rebuilding a context and swap only its schedule, and what it takes to move the fan onto a
native fleet - is [clip-search-budget.md](clip-search-budget.md).

## One parameter that is easy to leave out

**Body lean (`m351C`) is not free.** It feeds the roll pose, hence the Co centre that does the pushing.
On the Tetra corner lean 0 and 1 clip the same entry and **64 already does not** (residual 1.1e-2, ~95
windows out), while a real walk-in arrives at lean -191 settling near -160. A compiled context is valid
only for the lean it was built at, so candidates must be grouped by lean.

It is worse than "group by it": whether **any** entry clips is itself a function of the lean, so the
lean belongs in the configuration key beside facing and thrust, and a candidate at a dead lean is not a
near-miss at all - see [clip-lottery-draws.md](clip-lottery-draws.md). Link's ground Y, by contrast,
does not matter: the acceptance runs on the geometry's own floor.

## What the fidelity gate decides (run it FIRST)

Sweeping the entry evaluates a *reseeded* roll. Whether that is the roll Link performs is not a
formality to settle after a hit turns up - it is the objective function, and a search aimed at the
wrong one cannot be rescued by making it bigger. Diff a real walk + A-press against the reseeded
schedule, per frame, in an engine that has the walls, and it decides three things at once:

1. **the seeding convention** (which frame's position and lean the context wants) - the one that was
   wrong above;
2. **whether the reseed's anim/pose history matters** - here it does not, all nine baked tables come
   out bit-identical;
3. **whether the crash latch matters.** A roll started in the open ARMS the mid-roll bonk, while a
   reseed typically forces it off and the compiled engine has no crash branch at all. On this corner
   the roll does contact the wall for ten frames and the bonk still never fires (the cone does not line
   up before the B edge), so disarming it is exact. That is a *measured* clearance, not an assumption,
   and it has to be re-measured on any new corner.

A hit is still a candidate until it is DTM-confirmed, but it is a candidate for the right reason.
