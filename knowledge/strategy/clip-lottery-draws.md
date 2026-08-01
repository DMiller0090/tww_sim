# Counting a clip lottery's DRAWS, not its candidates

**Answers:** A razor-thin clip search returns "N near-misses, 0 genuine" - how do I tell whether the
pass was too small or aimed at nothing? What counts as one draw? Why can a search get 60% more
candidates and not one more near-miss? Which prunes in a fan are physics and which are assumptions I
put there myself?
**Status:** validated offline (sessions 81-82) on the flooded-Hyrule Tetra corner, where the honest
recount turned a pass that looked like 0.23 expected hits into 0.02, named where the missing draws
are - and then priced the biggest of those at zero. Gated in
[`tests/test_entry_fan.py`](../../tests/test_entry_fan.py). Companion to
[clip-entry-search.md](clip-entry-search.md), which is the entry-sweep method itself. The session-81
reading of the speed prune as an untapped lever is in
[history/entry-search-s81-momentum-lever.md](../history/entry-search-s81-momentum-lever.md).
**Source:** `harness/tetrapush/entry_fan.py` (`BandTable`, `stream_search`), `harness/tetrapush/
entry_search.py` (`configuration_band`, `locus_scan`, `qualify`, `window_gap`, `roll_nspeed`).

---

## A draw is one (candidate x LIVE configuration), and most of them are not live

The figure of merit for a dust-width acceptance is not the candidate count. It is

    E[hits] = (near-miss density in the razor coordinate) x (acceptance band width)

with one hard condition: the band must be the band of the configuration the candidate is actually
evaluated at. Score a candidate against some *other* configuration's band and you are counting a draw
that could never have converted, however near-zero its residual looks.

On the Tetra corner the acceptance band turned out to be a function of the roll's **body lean** as well
as its facing and thrust step. Measured at one (facing, thrust), sweeping the lean:

- lean 0 and +6 carry the full band (3.2e-5 of residual);
- +136 carries a narrower one, +266 collapses to a single f32 value;
- and a large share of leans - including most of what a real walk-in arrives at - have **nothing
  genuine at any entry on the locus at all.**

It is jagged, not signed: 448 of 556 finely-sampled leans admit something, but only about 40% of those
have a real interval rather than one f32 value. A fan's candidates carry whatever lean their own turn
history left them (~2000 distinct values over 43596 candidates here), so **83% of that pass's draws
were dead** - and its 72 "near-misses" were 6. That is the difference between "10x too small" and
"250x too small", and it is invisible until the band is measured per (facing, thrust, lean).

Cost is not the excuse it used to be: with the compiled context evaluated analytically instead of
simulated, one band costs ~14 ms, so a whole fan's worth of leans is a one-off minute and cached
afterwards.

## More candidates is not more draws if they are somewhere else

Extending the same fan's hold length until it stopped yielding new endpoints took it from 43596 to
69169 distinct candidates - **1.6x more candidates and exactly zero more near-misses.** The extra ones
are longer walks, and a longer walk goes *past* the locus. Density near the target is the only thing
that counts, so measure the yield where the target is; a saturation curve on the raw candidate count
will happily tell you the fan is still paying when it is not.

## The prunes are where the missing draws are hiding

Two prunes are usually written into a fan early, and only one of them is physics.

**The regime prune usually is.** Here it is a follow bar: past 230 u the pushed actor leaves the idle
state and starts walking, so an entry out there is not an entry - the model does not cover it.

**A speed prune usually is not.** This fan kept only endpoints at the walk cap (speedF exactly 17)
because the compiled roll schedule bakes the cap's own roll momentum (nspeed 26). But a sub-cap walk
still rolls, at `clamp(1.5 * speedF + 0.5, 5, 26)`; it just bakes a *different* schedule. Dropping the
prune multiplies the candidates 3x, over 4146 distinct schedules - each, genuinely, its own locus and
its own band. So generalize it: the momentum belongs in the schedule, the entry step and the band key,
and re-gate it against a real sub-cap A-press roll rather than trusting the algebra.

**And then price the axis, because "unlocked" is not "live".** On this corner the answer was zero. Only
2 of 181 momenta between 17 and 26 are productive and both sit at the cap; the rest are barren along
their *whole* locus, at every facing in the entire circle - so an uncapped fan reaching 42807 distinct
momenta has 4 of them worth a draw. End to end at one resolution: 14529 capped candidates find 4
near-misses, 43653 uncapped candidates find **the same 4, gap for gap.** The generalization was right
and the lever was worth nothing, and those are two claims. Pricing costs a handful of band scans along
the unlocked axis - a minute - so do it before promoting a prune audit to a plan.

The reason is worth carrying to the next corner: a shorter roll is not the same clip started further
back. Below a momentum threshold the roll never reaches the wall brace that pins the cut's start point,
and in the middle of the range it reaches the brace but leaves the pushed actor out of Co range by the
cut frame - zero push, no leverage from any entry. Do not mistake a modelling shortcut for an
infeasibility ([`[[infeasible-needs-proof]]`](seam-clip-solver.md)); do not mistake removing one for
progress either.

## Declaring a configuration dead needs the WHOLE locus, not one point

Band measurement sweeps *across* the residual zero at the one entry a Newton solve lands on. That is
enough to size a live band, and it is **not** enough to call a configuration barren: the genuine set is
a curve (104 u long here), so dust that has slid along it reads as "nothing genuine on the residual
zero". March the locus instead - step along it, re-project onto residual zero at every station because
the curve bends, and sweep across at each. It costs a couple of seconds per configuration.

Always run the live configuration as a control in the same call. The first full-circle sweep above was
run at 64-BAM steps and reported zero productive facings *at the cap*, which is only because the cap's
own window is 32 BAM wide and the stride stepped over it. A negative result whose control also reads
negative is a resolution bug, not a finding.

## Two facts that kill a local descent before it starts

Local refinement (perturb a near-miss's inputs, follow the gap down) is the right instinct - it is what
the seam solver does - but on a held-stick walk it has no gradient, for two measurable reasons:

1. **The last delivered frame is only BUFFERED.** At the replay's input delay, re-aiming the final
   frame of a plan cannot move the endpoint: 12 held frames and 11 held frames plus a *different* aim
   land on the same point to the bit. A descent that perturbs the last frame reads a flat objective and
   concludes the alphabet is degenerate.
2. **Once the new aim does act, the turn costs the cap.** The decoded-aim alphabet's local spacing is
   ~12 BAM here, one frame at 12 BAM off-travel drops speedF off 17 - and a turn writes lean besides,
   which may land dead by the section above. So there is no *small* move: the fine knob a descent needs
   does not exist inside one held walk.

Perturbing the stick BYTES instead of the decoded angle is a third way to read a flat objective: the
octagon clamp maps every byte near a saturated aim to the same angle, so those variants re-walk the
identical path. Always perturb the alphabet the physics reads.

## The checklist

Before concluding a razor search is too small:

1. measure the band at the candidate's OWN configuration - every axis of it, lean included;
2. count draws, not candidates, and report the dead share;
3. check the near-miss yield against candidate count, not the count alone;
4. audit each prune for whether it encodes physics or an assumption in your own schedule - then
   **price** the axis it hides before spending a session on it, with a control in the same sweep;
5. rank the signed distance to the band, never |residual|
   ([clip-entry-search.md](clip-entry-search.md));
6. and only then buy more candidates.
