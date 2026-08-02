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

## See also

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
