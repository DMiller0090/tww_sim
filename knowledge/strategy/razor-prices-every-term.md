# A razor prices every term of its frame, not just the one you search

**Answers:** My search's acceptance window is f32-dust wide and I measured the precision it needs in
the variable I sweep - is that the whole precision budget? Why did a hit whose every swept quantity
is console-exact still fail on console? How do I know a quantity I treat as a measured CONSTANT is
still constant at the frame that is scored? When is a verdict simply not decidable by the model I
have?
**Status:** measured on console (session 86) and then CLOSED (session 87), flooded-Hyrule Tetra
corner: the frame-minimal of 49 confirmed entries delivered to the real game reproduced its entry,
its 17-frame roll and its wall brace BIT-EXACT, and did not clip. The unpriced term turned out to be
**two** terms in **two different engines** ([the reckoning](#the-reckoning-session-87)); with both
modelled the verdict is decidable again and **42 of the 49 were false positives**. Locked as
[`fixtures/courtyard_clip_s86_console.json`](../../fixtures/courtyard_clip_s86_console.json), gated
[`tests/test_clip_console.py`](../../tests/test_clip_console.py). Companion to
[clip-entry-search.md](clip-entry-search.md) (the search) and
[search-prune-the-dispatch.md](search-prune-the-dispatch.md) (the other promise a candidate makes).
**Source:** `harness/tetrapush/entry_search.py` (`resid_fn`, `build_fast`, `acceptance_window`),
`harness/tetrapush/deliver.py` (the console delivery), `_notes/s86_*.py`.

---

## The shape of the bug

A razor search has an acceptance window and a variable it sweeps, so the natural question is *how
precisely must I hit the variable* - and it has a clean answer: window divided by the gradient. The
Tetra-corner entry search asked exactly that and got **~1e-4 u of entry position**, about one f32
ULP, which is why its fan is built the way it is.

That number is a *budget for one term*, and the residual has several. Here:

    pred  = old + roll_step + push + cut_lunge
    resid = cross(pred - old, S - old) / |pred - old|

`old` is swept. `roll_step` and `cut_lunge` are constants of the schedule. And `push` - whether the
other actor is still shoving Link on the frame the cut fires - is a whole simulated trajectory. The
search seeds it from a MEASURED CONSTANT (the console's own frozen placement, exact at the
handover) and never asked what precision the *scored frame's* value of it needs.

The answer is: the same precision, because the terms are added. **The window does not get looser for
the terms you did not think of.**

## What it cost, in one delivery

Every swept term was console-exact and the clip still did not happen:

| term | status on console |
|---|---|
| roll entry, facing, lean, momentum | bit-exact (the [entry confirm](../../tests/test_entry_console.py)) |
| the 17-frame roll and every wall brace | bit-exact - `old` is `ShoveCtx`'s own value to the bit |
| the cut's frame, proc and facing | as predicted |
| **the lunge** | **0.16 u, where the prediction has 49.97 u through the gap** |

The one unpriced term decided it. During the clip roll the "constant" actor is plowed ~100 u and
braced against a wall, so the position that sets `push` is not the measurement the search seeds
from - it is a simulation of that measurement, and it is **0.15 u** off what the console reads.

## The number that settles it

Do not argue about whether 0.15 u is close. Price the term the same way the swept one was priced -
perturb it and watch the verdict:

> **One f32 ULP of her x (1.221e-4 u) flips `genuine` from True to False.**

So the verdict differs between *adjacent representable positions* of her: the razor is thinner than
her own storage grid. A model that is 1200 ULP out cannot decide it in either direction - the True
it returned is not a wrong answer so much as an undefined one. (A 1e-5 perturbation reads identical,
because it rounds to the same f32. If a sensitivity sweep shows no change, check you moved the value
at all before concluding it is insensitive.)

## The reckoning (session 87)

Both halves of the unpriced term were found by the same move -- **diff the two engines frame for
frame against the same console log** -- and neither was where "the pushed actor's position is
simulated" pointed on its own:

| # | term | where it was missing | worth |
|---|------|---------------------|-------|
| 1 | her BG `CrrPos` wall pass | the COURTYARD tracking (`from_f0`), which carried her as a bare XZ plow point | she goes through the wall entirely |
| 2 | the `body_chn` counter-twist on Link's Co centre | the SEARCH engine's baked chain (`roll_co_chain_consts`) | ~0.35 u of centre at a real turn lean, compounding through the plow into the 0.15 u |

With both closed the two engines and the console agree on **every frame of the roll, both actors,
0 ULP**, the predicted post-`CrrPos` endpoint is the console's own 0.16 u nudge rather than a 49.97 u
lunge, and re-scoring the 49 keeps **7** -- every one of them at a small turn lean, where term 2 is
below the sine-table bucket. The frame floor moves from 4 (falsified on console) to 5.

Note what term 2 does to rule 1 below: the residual's terms are not all *visible* in the residual's
formula. `push` looked like one quantity to price; it was a whole trajectory computed twice, by two
engines that had never been compared to each other.

## The rules

1. **List the terms of the residual, then price each one.** A gradient per term is one sweep each and
   it is cheap; a console delivery that fails for an unpriced term is not.
2. **"Measured constant" is a claim about a FRAME, not about a quantity.** It was measured at the
   handover; the scored frame is 18 frames later with a roll running through it. Re-ask whether it is
   still constant *there*, and if the plan moves it, it is a simulated quantity with a simulated
   error bar.
3. **Perturb by one ULP, not by "a small amount".** It converts "is this precise enough" into a yes
   or no, and it catches the case where your small amount was not representable.
4. **When the required precision is below what the model delivers, say the verdict is UNDECIDABLE**
   rather than reporting the model's answer. The population of "genuine" hits inherits the error bar
   of its worst-known term.
5. **The cheapest place to find this is a console delivery of ONE hit.** Redeeming a single lottery
   ticket priced the whole book of them; widening the search first would have bought more tickets in
   the same currency.
6. **If a quantity is computed by two engines, gate them against each other, not only each against
   its own fixture.** A term present in one and absent from the other is invisible for exactly as
   long as nobody puts the two side by side on the same frames.
7. **Cross-engine agreement is a property of the CANDIDATE, not of the engines** (session 88). Making
   them agree for one hit and gating that reads as "the engines agree"; run the same diff over the
   candidate list and some entries disagree by a few ULP of the pushed actor mid-roll - which is the
   scale rule 3 measured the verdict flipping at. Two of 19 survivors had the composite **blocking**
   the very lunge the sweep scored genuine, and one of those two was the frame-minimal candidate, i.e.
   the one a delivery would have been spent on. So diff the two engines **for the candidate you are
   about to deliver**; it costs one rollout and no console runs.
8. **A dispatch is not priced by the model that performs it** ([../mechanics/roll-attack-threshold.md](../mechanics/roll-attack-threshold.md)).
   Every term of the residual can be console-exact while the input never produces the action at all.
   Check the branch that decides the action against the decomp, separately from the physics that
   follows it - a replay-based confirm shares the omission and will agree with you.
9. **"A property of the candidate" is a code seam you have not named yet** (session 89). Rule 7 is
   how you SHIP safely; it is not the diagnosis. Ask instead which frames the disagreement lands on
   and what the two engines do differently there: session 88's four rejections were one seam - two
   different ports of Link's Co centre, agreeing to 1-2 ULP - and swapping one engine onto the other's
   port made all four agree at once
   ([../mechanics/link-co-centre.md](../mechanics/link-co-centre.md#the-two-ports-and-what-was-actually-between-them)).
   The corollary for rule 6: **a cross-engine gate is only evidence on frames where the engines CAN
   differ.** Both console captures ran on candidates where the two ports agree, so the gate was
   green and blind for two sessions. Pick the diffing candidate on purpose, and when no capture can
   discriminate, say the question is OPEN and name the one delivery that would close it rather than
   inferring a winner from the looser fixture.
10. **Every input to a cached derivation belongs in its cache key** (session 89). A fix that lands in
    a function the search calls has not landed in the search if a stale artifact sits between them.
    The 0.75 ATTACK gate of rule 8 was correct, gated, and green in nine tests, and the re-run that
    was supposed to measure it came back **bit-identical** to the pass before it - because the
    productive-configuration cache keyed on camera and thrusts and not on the threshold, and handed
    the pass two configurations whose aim was the very byte pair the console had refused. **A re-run
    that reproduces the previous run exactly is a RESULT, not a relief:** diff the populations before
    reading the yield, and if nothing moved, find out what the run actually consumed.
11. **A code seam can be a SYMPTOM: ask what each side is given before asking which side is right**
    (session 90). Rule 9's named seam was two ports of the Co centre, and the obvious next move was to
    delete the loser. The console run said `body_cyl` - and neither port was wrong. They were being
    handed **different anim frames**, one ULP apart, because a frame ctrl held a Python `double` rate
    where the hardware field is f32 ([../model/anim-frame-is-f32.md](../model/anim-frame-is-f32.md)).
    Two corollaries. **Design the run so it cannot come back ambiguous:** with every capture blind to
    the question, the move was not a better argument but a candidate where the two answers are 49.97 u
    apart instead of 1 ULP - clip against no clip. And **a small measured cost is not evidence the
    cause is small**: "4 candidates, zero frames" was one f32 tie in the shared anim engine, and the
    same duplicate-accumulator shape can sit under anything.

12. **A NEGATIVE is only as strong as the set it was argued over - and "I marched further" is not the
    same as "I started somewhere else"** (session 92). Rule 9's seam and rule 11's tie were both found
    by widening the *evidence*; this is the failure mode of narrowing it. The scope of an entire search
    rested on a per-configuration verdict that read `no leverage`, which means "the pushed actor is out
    of Co range on the cut frame" - **from the one seed it was asked at**. Leverage is a property of the
    ENTRY, so the verdict was about the seed and was recorded about the configuration, and the strong
    form that session 90 built (march ALONG the locus, not across it at one station) inherited the flaw
    intact: it returns nothing at all when its single seed has no gradient, having sampled the locus
    nowhere. Eleven sessions of passes therefore excluded **half the seam's facing window**, and with it
    the entire objective term Dereck opened - measured at +9 BAM when it was worth +336
    ([../history/entry-search-one-seed-negative.md](../history/entry-search-one-seed-negative.md)).
    Two corollaries. **Find your seeds from the structure, not from convenience:** the target is a level
    curve, so seed off its own sign changes over the reachable box - one vectorized sweep, and it is
    cheaper than the march it feeds. And **a closure expires when its premise moves**: the camera was
    priced at zero against a 2-cell window and is a live lever against a 22-cell one, so re-derive what
    a closed axis reaches whenever the thing it was closed against changes size.

13. **A POSITIVE is only as available as the BUDGET it was found under - an existence result inside a
    generous bound is not a reachable one** (session 93, and it is rule 12 in a mirror). Rule 12's fix
    was to stop arguing negatives over too small a set; the very same session then priced a prize over
    one that was too big. The recovered facing cells were found by sweeping a `reach_radius` box - four
    walk frames at the cap plus the roll's entry step, 94 u square - which is the right conservative
    place to look for a level curve and is **not the reachable set**: the actor enters on a fixed
    heading at the speed cap, so four held-stick frames reach a small curved cloud whose bounding box is
    a fraction of that area. The stations were 13-21 u from the delivered entry, which read as near, and
    a frame-capped pass over all of them returned **0 genuine, 0 near, 0 dead-tail from 7.0 M
    evaluations** - the emptiest result the search has produced, because at that budget the residual
    stays 71x to 375x outside the probe a near-miss is counted at - and past a certain cell it never
    changes sign at all. Buying 18x the candidates moved the closest approach by *bit-identical* zero,
    which is how you separate "too sparse" from "aimed at empty space" without arguing about it.
    Two corollaries. **Measure the reachable set, do not bound it:** the fan already enumerates it, so
    its convex hull is a few lines and turns "is this reachable" from an argument into a test - and keep
    the test ASYMMETRIC, since a hull off a coarse alphabet proves OUTSIDE and only suggests inside.
    And **price a lever in the objective's own currency before believing it**: "+160 BAM at a wider
    band" and "+160 BAM for three extra frames" are the same measurement and opposite answers when the
    constraint is that the movement must cost nothing
    ([../history/exit-angle-priced-without-its-frame-cost.md](../history/exit-angle-priced-without-its-frame-cost.md)).

14. **A fix to the SCOPE does not reach the RANKING - re-ask it of every consumer that shares the
    machinery** (session 94). Rules 12 and 13 are about the set a claim is argued over; this is what
    happens when the set gets fixed and the scoring does not. The escalations of sessions 90 and 92 went
    into the *qualification*, which decides which configurations a pass covers. The per-lean acceptance
    band that decides dead-tail-versus-near-miss is a **different call to the same solver**, and it kept
    its single Newton seed for thirteen sessions afterwards - long enough to report `no genuine on the
    residual zero` for the configuration of the clip that had been **delivered to console and worked**.
    Nothing looked broken, because a dead band is silent by construction: `genuine` comes from the sweep,
    so no clip is ever suppressed; the pass simply reports zero near-misses and zero expected hits for a
    configuration that has both, which reads exactly like "stop buying density here". Measured, the same
    779130 candidates go from "180 dead-tail, 0 near, E[hits] 0.000" to **34 near-misses at E[hits]
    0.079**, and one cell from 0 of its 24 heaviest leans usable to 20 of 24
    ([clip-band-per-lean.md](clip-band-per-lean.md)).
    Two corollaries. **Gate a scoring against something you have already delivered:** the console clip's
    own configuration is a free oracle for the ranking, and it had never been asked - a scoring that
    calls the known-good input dead is broken before any of its other verdicts are worth reading. And
    **an artifact that caches the old answers will serve them past the patch**, so a cached negative that
    cannot say which form it was argued under has to be dropped rather than trusted - 10360 of 15968 rows
    here.

15. **Price a lever against the subset the SEARCH can use, not the one the hardware has - and look for
    the channels nothing is using** (session 95). Rules 12-14 are about the set a claim is argued over;
    this is about the set a *price* is computed over. The camera's walk-side reach was dismissed as
    ~1.07x because it was counted over the whole stick alphabet - 3612 of 4096 direction cells. The fan
    keeps only endpoints at the speed cap, so it can hold only the cap-magnitude sticks: **1736 of 4096,
    42.4%**. Sliding a 42% subset is a different lever from nudging an 88% one - one sine cell of camera
    moves 888 of those 1736 cells onto directions the frozen camera cannot command at all - and the
    correction is worth two orders of magnitude on the closest approach where the priced axis had
    saturated ([clip-camera-axis.md](clip-camera-axis.md)).
    Two corollaries. **An input channel no constraint is using over the frames you are searching is a
    free axis:** the price here came off the delivered console log read column by column - `substickX`
    is 128 on every frame of the entry plan, so the slew cannot cost a frame - not from reasoning about
    what the plan needs. And **a free axis is still bounded somewhere else**: the camera is still ramping
    when the roll's facing latches (one frame after the press, measured by firing the roll and reading
    the facing back), so a hard slew moves the aim alphabet too and a camera draw only counts where the
    target cell stays aimable - 64 of 82 here.

## See also

- [clip-camera-axis.md](clip-camera-axis.md) - rule 15's own mechanism: the idle channel, the two
  halves of a camera, and the trail a fan injects.
- [clip-band-per-lean.md](clip-band-per-lean.md) - rule 14's own mechanism: the seed ladder, and why a
  zero-width band is odds rather than a wall.
- [clip-exit-angle.md](clip-exit-angle.md) - rule 12's own corner, and the objective term it was
  hiding.
- [clip-entry-search.md](clip-entry-search.md) - the search whose window this is, and the
  entry-precision figure that was priced correctly.
- [clip-lottery-draws.md](clip-lottery-draws.md) - the other way a razor search overstates itself:
  counting copies as discoveries.
- [../mechanics/tetra-follow.md](../mechanics/tetra-follow.md) - the pushed actor's own BG
  WallCorrect (R 50), which is what braces her mid-roll.
- [../mechanics/link-co-centre.md](../mechanics/link-co-centre.md#the-two-body-leans) - the two
  body leans of Link's Co centre, and
  [../history/co-centre-body-chn-twist.md](../history/co-centre-body-chn-twist.md) for how one of
  them stayed unmodelled behind a live 0-ULP gate.
