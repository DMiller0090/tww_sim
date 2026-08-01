# Solving for the roll ENTRY instead of the target's position

**Answers:** A push-assisted seam clip needs a pushed actor on a razor-thin "genuine" spot. What do I
do when that actor is already placed and I cannot move her - can I solve for Link's roll entry
instead? Which quantity is the razor, and what precision does hitting it need? Why does the
perpendicular half of a placement miss decide a clip that a nearest-sample distance says is 0.4 u
away?
**Status:** validated offline (sessions 79-80) on the flooded-Hyrule Tetra corner: the acceptance
window is measured off a live-anchored 288-sample list, the entry locus re-derives that list's own
endpoint, and the roll the sweep scores is gated bit-identical to a real A-press roll out of a walk.
All of it is gated in [`tests/test_entry_search.py`](../../tests/test_entry_search.py). No hit has
been DELIVERED yet (no DTM confirm). Two premises this page carried in session 79 were overturned by
that gate and now live in
[history/entry-search-s79-superseded.md](../history/entry-search-s79-superseded.md).
**Source:** `harness/tetrapush/entry_search.py`, `harness/tetrapush/roll_fidelity.py`,
`harness/rollstab/turnaround.py`, `harness/rollstab/geometry_tetra.genuine_clip`,
`tww_sim/core/_shovec.ShoveCtx`. Constants:
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
there**: `P(a near-zero candidate is genuine) ~ window / local spacing`.

Measure that spacing **at one facing, over the candidates that actually reach near zero** - not over
"the N closest by |resid|", which are clustered and give an answer that is too good. On the Tetra
corner the honest numbers from a 3699-candidate fan against ONE locus were: 4 candidates inside
|resid| < 5e-3, local spacing 1.0e-3, so `P ~ 0.11` and an expected 0.4 hits, which is exactly what
that pass returned (zero). The fix is more draws, never a wider tolerance, and the cheapest draws are
the multipliers above: correcting the entry and opening the aim and thrust alphabets took the same
fan from 4 near-zero candidates in 3699 to **53 in 615**. After that, more candidates: finer stick
stride, more base frames to fan from, and **multi-segment holds** (stick S1 for j1 frames then S2 for
j2), which is the combinatorially large one.

Do not assume the loci are all equally productive. Scanning 281 facings instead of 81 bought only 1.1x
the near-zero yield for 3.5x the work, because only the aims whose locus threads the candidate cloud
produce anything. Scan wide once, cheaply, to find the productive band; then spend the budget on
candidates.

And **rank the signed distance to the window, not |resid|**. The window is asymmetric because its sign
is which side of the gap the ray passes on, so |resid| scores a blocked-side near-miss as highly as a
real one. The Tetra pass's best candidate was -5.45e-5: inside the window's *width*, on the wrong side
of it.

## Sweep the entry the game hands you, not the one the walk ends on

A reseeded `FRONT_ROLL` advances its animation frame control on its first step. A **real** roll's
entry frame does not: `_roll_init` runs, and the frame after it is where the animation starts moving.
So the reseeded schedule's step 0 is the real roll's *second* frame, and the entry position a compiled
context wants is the one at the **end** of the entry frame:

    entry = walk_endpoint + one roll step at the AIMED facing        (26 u on the Tetra corner)

and the lean is likewise the post-entry-frame value (one decay tick past the walk's). This is decided
by measurement, not convention: feeding the pre-entry values mismatches the pose-chain tables outright,
while the post-entry values reproduce a real A-press roll bit-for-bit.

The consequence is larger than the correction. That step is taken **along the aim**, so an aim is not
just its own locus - it is its own candidate. Sweeping aims moves the entry and the target together.

## Three multipliers on the lottery, and where the budget actually goes

The figure of merit is candidates x **independent loci**. A locus is independent whenever the baked cut
schedule changes, so:

- **the aim.** The roll needs no stick magnitude - it takes its whole speed from the walk cap and
  `_roll_init` snaps facing to the latched target whatever the deflection - so the alphabet is the full
  decoded-angle grid, not the saturated octagon boundary. On the Tetra corner that is **81** facings in
  the seam window rather than 6. Fire each one and read the facing back before believing it.
- **the thrust step.** The B edge can dispatch the cut at more than one roll frame (13/14/15 here).
  Each lands the cut on a different step and reads a completely different residual at the same entry,
  so each is its own draw.
- **the camera**, which shifts the whole alphabet by moving `csangle`.

The budget is **not** the size of the alphabet - it is the cost of compiling one context per
`(facing, lean, thrust)`. Simulating that roll to read its schedule back is the expensive part (22 ms
here) and it is unnecessary: the schedule is a pure function of those three parameters. Speed is the
constant roll momentum and travel equals facing on every frame including the cut entry, the animation
frame control is a fixed accumulation, the lean decays deterministically, the Co chain is a direct
evaluation on (facing, frame, lean), and the cut lunge is a constant root translate rotated by the
facing. Evaluating it directly instead of simulating it ran **~110x** faster, 0-ULP identical, and that
is what made 243 loci affordable.

## One parameter that is easy to leave out

**Body lean (`m351C`) is not free.** It feeds the roll pose, hence the Co centre that does the pushing.
On the Tetra corner lean 0 and 1 clip the same entry and **64 already does not** (residual 1.1e-2, ~95
windows out), while a real walk-in arrives at lean -191 settling near -160. A compiled context is valid
only for the lean it was built at, so candidates must be grouped by lean. Link's ground Y, by contrast,
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
