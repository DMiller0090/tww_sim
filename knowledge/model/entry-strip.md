# The razor's target, in u of Link's roll entry

**Answers:** My item came back barren - how far was it from clipping, in a unit a walk can actually
steer? Is the roll ENTRY an aimable axis, or only where the pushed actor stands? How accurately does a
plan have to place the entry? Can I SOLVE for an entry that clips instead of drawing for one? May I
re-use a band I measured somewhere else?
**Status:** MEASURED (session 160) on the flooded-Hyrule Tetra corner, at both configurations this work
has delivered a clip from - the console's own (cell 2552, thrust 15, lean 64761) and s154's accepted 101
(cell 2545, thrust 15, lean 104). Gated in [`tests/test_entry_aim.py`](../../tests/test_entry_aim.py)
(12, including the rediscovery gate). Builds on
[genuine-residual-band.md](genuine-residual-band.md) - the band is what makes a residual a distance -
and scopes [braced-cut-frame.md](braced-cut-frame.md), whose entry-invariance is measured with the
pushed actor OUT of contact.
**Source:** [`harness/tetrapush/entry_aim.py`](../../harness/tetrapush/entry_aim.py) (`entry_grad`,
`offset_u`, `price`, `aim`, `walk_end_for`).

---

## The entry is a peer axis of hers, not an inert one

The razor residual's gradient, measured at each delivered row by finite difference on the sim:

| configuration | `\|d resid / d ENTRY\|` | `\|d resid / d HER\|` | band width | **strip in u of entry** |
|---|---|---|---|---|
| console's own clip | 0.3095 per u | 0.3457 per u | 3.677e-05 | **1.235e-04 u** |
| s154's accepted 101 | 0.5062 per u | 0.2589 per u | 3.387e-05 | **6.807e-05 u** |

Same order on both axes. So the razor's accepting set, seen from a plan, is a **STRIP IN THE ENTRY PLANE
about one ten-thousandth of a unit wide**, running along a level curve of the residual - band width
divided by the leverage. That number is what a planner needs, and it is why `razor_band.band_distance`
read as unsteerable: it is the same distance in the residual's units, one division away from u.

`offset_u` is that division: **the signed distance, in u, that Link's roll entry must move for the row to
clip**, zero inside the band. One sweep row plus a 2-point gradient - ~15 us a candidate against the
~1 s a screen costs - so a whole fan can be priced.

This does not contradict the brace. [braced-cut-frame.md](braced-cut-frame.md) sweeps the reachable box
with her parked OUT of contact and gets ONE distinct residual bit pattern; the leverage above is
measured with her IN contact, and it is exactly the channel that page names - the entry changes when the
roll first reaches her, hence how many frames of plow she gets. Out of contact there is nothing to
steer; in contact the entry is worth 0.3-0.5 residual per u.

## The band is sufficient along the entry axis too

s158 measured `resid in band <=> genuine` sweeping HER plane. Sweeping LINK'S ENTRY over ±0.02 u at her
own pinned placement, at 1e-04 steps:

| configuration | rows swept | in the band | genuine | disagreements |
|---|---|---|---|---|
| console's own clip | 160 801 | 875 | 875 | **0** |
| s154's accepted 101 | 160 801 | 642 | 642 | **0** |

Identical sets, both ways. That is what licenses pricing a row by its residual at all.

## Aiming works, and it finds clips that were never drawn

`aim` Newtons the entry onto the band centre and ends on the sim's own `genuine` flag. Displaced **0.70 u**
off each delivered entry - ~5700 strip-widths - it walks back onto a genuine entry in **4 and 5 steps**
(~50 ms), and what it returns at the console's configuration is a *different* clip, 0.0745 u from the
delivered one. So the strip is not a lottery ticket that has to be drawn; it can be solved for.

`walk_end_for` converts the answer into the thing a plan controls - the walk endpoint the roll must be
entered from - by inverting `entry_search.roll_entry`. On the console's own entry it returns the locked
fixture's own recorded endpoint, bit for bit.

The reason that matters more than the pricing: a fan's endpoint lattice is **0.2-0.4 u** coarse (98 618
candidates over a 114 u box), which is three orders of magnitude wider than the strip, so a blind
enumeration hits it only by accident - see [fan-containment-gap.md](fan-containment-gap.md) for what that
cost this search.

## Two traps, both measured

**The band DRIFTS with the entry.** s158 measured it as unmoved over ~0.05 u and that is the range where
it holds. `aim`'s console result sits at `resid` +1.0157e-04 against a band read at the delivered entry of
[+5.7958e-05, +9.4723e-05] - 7% above its top, 0.70 u away. So the residual PRICES a row and only the
sim's `genuine` flag VERDICTS one; never carry a band across more than a fraction of a unit.

**A dead gradient does not mean "out of contact" on this axis.** `admit_map.resid_grad` returns exactly
0 once she leaves Co range, and that IS a contact test. The entry's gradient never dies: 565 u of
displacement still reads 0.99 per u, because `resid` is the cut ray's offset from the seam vertex and
Link's entry always moves the ray. Ask the Co overlap for contact
([clip-overlap-band.md](../strategy/clip-overlap-band.md)), never this gradient.
