# The acceptance band is per (configuration, lean, STATION) - and a one-seed band is a dead cell

**Answers:** My razor pass reports "N draws at a DEAD configuration, 0 near-misses, E[hits] 0" - is the
cell dead or is my band measurement? Why does the same table call the input I already delivered to
console dead? How do I measure a band so the verdict is about the configuration and not about where I
started the solve? Is a zero-width band a wall? Which entry lean does a band belong to?
**Status:** validated offline (session 94) on the flooded-Hyrule Tetra corner. The ladder recovers cell
2553 / thrust 15 from **0 of its 24 heaviest fan leans usable to 20 of 24**, and re-running session 93's
own frame-floor pass over the *same* 779130 candidates turns "180 dead-tail, 0 near, E[hits] 0.000" into
**34 near-misses and E[hits] 0.079** - a live, priced lottery where the pass had reported a dead cell.
Gated in [`tests/test_entry_lean.py`](../../tests/test_entry_lean.py). The overturned dead-share reading
is in [history/band-dead-share-from-one-seed.md](../history/band-dead-share-from-one-seed.md).
**Source:** `harness/tetrapush/entry_score.py` (`BandTable`, `stream_search`),
`harness/tetrapush/entry_lean.py` (`census`, `bands_at`, `rank`, `select_by_lean`),
`harness/tetrapush/entry_search.py` (`configuration_band`, `locus_scan`, `curve_scan`, `lean_at_roll`).

---

## What the band decides, and what it does not

The band is the width of the genuine interval across the residual zero at one
(facing, thrust, lean, momentum). A pass uses it for exactly two things:

- a near-zero candidate with **no usable band** is counted **dead-tail** and dropped;
- a near-zero candidate **with** one becomes a near-miss ranked by `window_gap`, and its width is its
  term in `E[hits]` ([clip-lottery-draws.md](clip-lottery-draws.md)).

It is never a veto on a clip: `genuine` comes from the sweep itself, so a hit is reported whatever the
band says. That is what makes a wrong band so quiet. Nothing breaks, no clip is lost - the pass simply
reports **zero near-misses and zero expected hits** for a configuration that has both, and the honest
reading of that output is "stop buying density here".

## The failure: a band is a Newton solve, and a Newton solve has a seed

`configuration_band` walks the entry down the residual gradient to `resid ~ 0` and sweeps across the
locus there. The locus **moves with the lean** - that is this page's other half - so a seed that sits on
the curve at lean 0 can be off it entirely at lean 64761, and the function then answers `no leverage`
(gradient ~0 at the seed) or `no genuine on the residual zero` (nothing genuine at *that* station).

`BandTable` handed it **one seed for every key**: the single global `ref_entry`. This is the same defect
fixed at the qualification twice - session 90's `escalate` (march ALONG the locus) and session 92's
`curve` (seed off the level curve's own sign changes) - one level down, in the ranking rather than in
the scope, and it survived both fixes untouched.

**The tell, and it is unambiguous:** ask the one-seed table for the band at the configuration of the
clip that was delivered to console and *worked* - facing 40841, thrust 15, lean 64761
(`fixtures/courtyard_clip_s90_console.json`) - and it answers `no genuine on the residual zero`. A
ranking whose input says the known-good, console-confirmed solution has no band is broken before any
of its other verdicts are worth reading ([[search-space-contains-human]] is the general form).

## What it cost, in numbers

| | one seed | the ladder |
|---|---|---|
| cell 2553 / thrust 15, of the 24 heaviest fan leans | **0 usable** | **20 usable** |
| the delivered clip's own configuration | `no genuine on the residual zero` | productive, 20 genuine |
| session 93's frame-floor pass at cell 2553 (identical 779130 candidates) | 180 dead-tail, 0 near, E[hits] **0.000** | 51 dead-tail, **34 near**, E[hits] **0.079** |
| cached band entries that were one-seed negatives | **10360 of 15968** | re-measured on demand |

Cell 2553 is +9 BAM of exit angle and the only cell right of the delivered pair that a 4-frame plan can
reach ([clip-exit-angle.md](clip-exit-angle.md)), so "the leans it arrives on have no usable width" was
the whole reason the axis read closed at the frame floor. It was a property of the seed.

## The ladder, and why every rung is fixed

Cheapest first, stopping at the first station that HAS a band:

1. the global `ref_entry` (the old behaviour);
2. the configuration's **own qualified station** - `qualify` already found somewhere on this locus with
   genuine dust, and that is the natural place to start;
3. `locus_scan` from (2) - march along the locus, sweep across at each station;
4. `curve_scan` from (2) - seed off the residual-zero curve's own sign changes inside the reachable box.

No single cheap seed dominates, which is why this is a ladder and not a better default: over those 24
leans the global ref wins 19/24 at cell 2551 and **0/24** at 2553, the qualified station 17 and 11.
Rungs 3-4 cost ~2-6 s and rungs 1-2 ~30 ms, and a pass only measures a band for its **near-zero tail**,
so the bill stays proportional to the tail rather than to the candidate count.

**Every seed is fixed per key, deliberately.** A first cut also carried the last station that had paid
for the same (facing, thrust) at any lean - free, and it does convert keys - but it makes the answer a
function of the order the keys were *requested*: two passes over one scope report different widths and
any gate on a single key is flaky. An order-dependent memo is not a measurement.

**And a one-seed negative must not survive its own fix.** The band cache is a pure memo, so the
temptation is to keep it; but 10360 of its rows were negatives of exactly the kind being fixed, and a
memo that keeps serving them carries the bug past the patch silently. A cached row that is not
productive and does not record that it was escalated is therefore **dropped on load and re-measured**,
while a productive row is kept whatever rung found it - a cheap-path positive is a positive.

## A zero-width band is odds, not a wall

The delivered console clip converted at a band whose width is **0.0** - 20 genuine samples all at one
f32 residual. So the `MIN_BAND` width test is False at the one configuration we know clips, and any pass
that *filtered* on width would have discarded the console solution. Width therefore ranks and never
filters, in this module and in the pass. The same reading applies to a cell: zero width at a lean means
the target there is a single f32 value, which is long odds against a big candidate mass - and the
delivered lean carried ~287 k candidates, which is how those odds were paid.

## The lean a band belongs to, and where the leans come from

Two different `m351C` values are in play and mixing them scores every candidate at a neighbouring lean's
band. A candidate's key carries the **walk endpoint's** m351C; the band is keyed on the **roll entry's**,
one `_set_move_slant_angle` decay step later - `entry_search.lean_at_roll`. Pinned against the console
clip, which records both (`m351C_walk` 64345 -> `m351C` 64761).

The lean is an **output** of a plan, never an input: it is the walk's own turn history. So the useful
question is a census - which leans a bounded fan reaches, and with how much candidate mass - and
`entry_lean.census` answers it at the fan shape it was taken at, because the mass distribution is a
property of the fan. `rank` then orders (lean, cell) pairs by width x mass, which is `E[hits]` up to a
constant.

Aiming a pass at those pairs (`entry_lean.select_by_lean`, `search2 leans=paying:2553`) is a **cost**
knob and a weak one on a frame-floor pass: the FAN generation dominates it, and a lean filter runs
downstream of the stepping, so it saves evaluation and not wall clock. It earns its keep when the
configuration count is large, since evaluation is per candidate per configuration - session 92's 40
configurations are ~6.7x the evaluation of 6. It is never a claim about the leans it drops - see the
zero-width section above.

## See also

- [clip-lottery-draws.md](clip-lottery-draws.md) - what the band is *for*: draws, the dead share, and
  `E[hits]`. This page is the correction to how its widths were measured.
- [clip-exit-angle.md](clip-exit-angle.md) - the objective term cell 2553 carries, and what a cell
  costs in frames.
- [razor-prices-every-term.md](razor-prices-every-term.md#the-rules) - rule 14, the general form: the
  ranking's own inputs need the escalation the scope got.
- [clip-entry-search.md](clip-entry-search.md) - the entry sweep and the qualification ladder this one
  mirrors.
