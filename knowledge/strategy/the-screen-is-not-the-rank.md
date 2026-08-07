# The screen is not the rank: what decides WHETHER a candidate fires does not decide what it is WORTH

**Answers:** I fixed the screen that was refusing my search - why does the beam still not improve? My
keep mixes three orders; how do I find out which of its slots is earning its place? A quantity a
previous session retired as "the wrong question" - can it still be the right rank? How fine does a
swept knob's grid have to be, and how do I price the answer instead of guessing it?
**Status:** MEASURED (session 117) on the flooded-Hyrule Tetra corner, against the session-111
cycle-3 beam: every one of the **551 clearing camera states** over the beam's 23 supplied rolls priced
whole by `cloud_land.cloud_landing` at the session-114/115 atom cap, then each roll's swept optimum
compared with what every key the cut can see would have kept. Driver `_notes/s117_camera_axis.py`
(phases ``sweep`` / ``report`` / ``keyeval`` / ``grid``), dump `_generated/s106/s117_axis.json`.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`lok_probe_key`, `camera_probe_key`, `landing_key`, `_mixed_beam`, `roll_candidates`' ``tcs_probe``,
`ESCAPE_TCS_STEP`), [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py)
(`lok_clear`, `snap_reach`).

---

[the-camera-supplies-the-cone.md](the-camera-supplies-the-cone.md) found the last roll's `target_cs`
supplying the clause that was refusing 63% of the search, and fixed the cut to ask for it. The screen
works and is exact - 107 of 107 clearing states fire, 118 of 118 non-clearing ones do not. Then the
whole axis it opened was priced, and the beam floor moved **0.08 frames**.

That gap is the finding. A screen answers *may this candidate exist*; a rank answers *which of the
survivors is cheapest*. Fixing the first does nothing for the second, and once the screen passes
everything the ordering underneath it is the only thing choosing.

## What each key would have kept, against a swept truth

Per roll, take the swept minimum bound over its clearing states, then cut the same states to
``tcs_keep`` = 3 by each key and read the best bound that survives. Loss is in frames.

| key (`roll_candidates` sees all of these) | retains the roll's optimum | mean loss | max |
|---|---|---|---|
| **the arrival's own cone margin** | **15 of 23** | **+0.14** | +2.32 |
| `camera_probe_key` (the SNAP bill) | **14 of 23** | **+0.14** | +2.32 |
| \|`off`\| - the raw camera slew | 10 of 23 | +0.23 | +2.32 |
| **the SHIPPED mix** (`landing_key` order + both probe shares) | **11 of 23** | **+0.22** | +2.14 |
| `lok_probe_key` (the screen, as an order) | 10 of 23 | +0.53 | +2.13 |
| `landing_key` - the last cycle's ORDER | **9 of 23** | **+0.53** | +2.13 |

Two things fall out, and the second is the uncomfortable one.

**The screen cannot rank, by construction.** `lok_probe_key` is binary on purpose: it ties every
clearing target at 0.0. Over a set that is entirely clearing it therefore contributes no ordering at
all and the row collapses onto `landing_key`'s - which is exactly what the table shows (10 vs 9, mean
+0.53 both). That is not a defect; it is what a screen IS. It earns its slot on the full graded set,
where it is the difference between an endpoint firing and not.

**The quantity retired as "the wrong question" is the best rank measured.** `camera_probe_key` prices
the snap bill, and session 77 proved the snap is not deliverable while session 116 showed the cut had
been ranked on it blindly - both true, both about FIRING. Asked instead what a camera is *worth*, the
same key retains the roll's optimum at 14 of 23 rolls where the landing order manages 9. A key can be
the wrong screen and the right rank; retiring it as a predictor of one is not evidence about the
other.

## The same result from the other direction: re-run the cut with the screen in it

Pricing a banked beam's cameras asks what the search could have CHOSEN. Re-running the cut asks which
endpoints EXIST, which is a different question, so it was run too - the session-111 cycle-3 cut
verbatim (same c2 nodes, same target, same caps, `_notes/s117_recut_c3.py`, 4059 s) with the screen
now in the keep as its only difference:

| the session-111 cut, before and after the screen | before | after |
|---|---|---|
| endpoints shared with the old beam | - | **45 of 64** (19 out, 12 new) |
| endpoints whose atom FIRES | 21 | **27** (+29%) |
| best bound | **93.95** | **93.95** |
| median firing bound | 100.44 | **101.89** (worse) |
| the `joint` winner | node 11, total 105, 0.474 u | **the same candidate**, bit-identical, at index 13 |

The screen changes a third of the beam and buys nearly a third more firing endpoints, and the floor
does not move by a thousandth. The median even degrades, because what the keep admits is endpoints
that FIRE - not endpoints that are close. That is the thesis of this page arriving from the other
side: a screen bought exactly what a screen buys.

## The grid: price the resolution, do not argue about it

The same sweep answers what `full_herd.ESCAPE_TCS_STEP` costs, by enumerating the 512 grid DIRECTLY
and joining to the sweep **by delivered state** rather than by offset (see the traps):

| the 512 step against the whole reachable axis | |
|---|---|
| bound loss, median / mean / max | **+0.01 / +0.30 / +3.00 f** |
| rolls holding no clearing grid member at all | **2 of 23** |
| clearing states a roll's grid can reach | typically 1-15 of 27-68 |

So the step is right where it matters and has a real tail: at one roll it gives up 3 frames, and at
two the entire clearing supply lies off-grid. A resolution argument is cheap to settle once the axis
is priced, and expensive to settle any other way.

## The rule

**Measure a keep against a swept truth, one slot at a time.** The operational question is never "is
this key correlated with value" - it is "would the cut have KEPT the best one", which is a property of
the key, the beam width, and the mix together. Sweeping one axis whole is what makes that answerable:
551 states at ~2.4 s each is 22 minutes at 8 processes, against the weeks of sessions spent arguing
about which proxy to trust.

And when a sweep is unaffordable, **say the sample is a sample**. Session 116 priced 2 targets a roll
out of up to 68 and reported the floor unmoved; at the roll that turned out to hold the floor its
structural picks were **0.89 f** off the roll's own optimum. The conclusion happened to survive - the
floor moved 0.08 f - but nothing in the sample said it would.

## Traps

- **A screen that passes everything is invisible in the rank.** A binary keep share over an
  all-passing set is not "a slot spent badly", it is a slot spent on nothing at all - and it still
  consumes one of `tcs_keep`'s three. Score the mix (`_mixed_beam` over the real orders), not the keys
  in isolation: they answer different questions and only the mix is what runs.
- **Filtering a fine sweep down to a coarse grid UNDERCOUNTS the coarse grid.** `snap_reach` dedupes
  by the `(csangle, travel)` a target delivers, so a multiple-of-512 offset is routinely dropped in
  favour of a neighbour landing on the same state. Enumerate the coarse grid directly and join by
  DELIVERED STATE; keeping `off % 512 == 0` from a step-64 sweep is a different, smaller set.
- **Do not average an infinite loss into a mean.** A roll whose entire axis fires nowhere has no
  ranking question on it; counting it reports `nan` instead of a fact. Report those rolls separately
  and say how many there were.
- **`in_band` is the landing alone.** The sweep's cheapest in-band landing reads total 98.00 against a
  banked delivery of 101 and is not better - it still owes 7.90 frames of arrival. Quote
  `total + arr_frames`, never `total`
  ([delivery-is-two-predicates.md](delivery-is-two-predicates.md)).

## See also

- [the-camera-supplies-the-cone.md](the-camera-supplies-the-cone.md) - the screen this measures the
  rank underneath: what the camera supplies, and why the snap is not it.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) - why a solved landing is not a
  solved plan, and what the 14 swept in-band landings still owe.
- [the-separation-is-not-a-suffix.md](the-separation-is-not-a-suffix.md) - the census that named the
  clause, and the resource the camera does NOT supply.
- [history/separation-priced-at-the-endpoint-speed.md](../history/separation-priced-at-the-endpoint-speed.md)
  - the same shape one layer down: a price is not a price until the frames have been run.
