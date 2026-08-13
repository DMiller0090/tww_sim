# The search could not generate its own known answer, and the gate said it could

**Answers:** My search reports 0 genuine over hundreds of items - is the space empty, or can my
GENERATOR not express the answer? What does a containment gate actually have to check? Which of my
barren results survive finding out? What does containing the known answer cost?
**Status:** MEASURED (session 160), **CLOSED (session 161)**, and **PROVEN END-TO-END (session 163)**
on the flooded-Hyrule Tetra corner, against the LOCKED console delivery fixture: the shipped driver,
run as-is on the console item, emitted 8 genuine plans at total 101 - one of them bit-for-bit the
console's own. The containing knobs are the shipped ones; `verify-console`
is green on all 16 checks including the two that reported NOT CONTAINED. Gated in
[`tests/test_overnight_driver.py`](../../tests/test_overnight_driver.py) - the containment equality, the
legacy diagnosis, the split expansion, and the leaf-budget trade - and in
[`tests/test_aimed_fan.py`](../../tests/test_aimed_fan.py) for the stronger form, the fan's own LEAF SET.
The rule it belongs to is Dereck's, session 151: a search is not trusted until it rediscovers a known
answer.
**Source:** [`harness/tetrapush/overnight.py`](../../harness/tetrapush/overnight.py)
(`containment_knobs`, `verify_console`, `fan_exact`, `alpha_for`, `pre_frames_for`).

---

## The measurement

Run the driver's own fan at the console's own herd, its own walk length (4) and its own camera, and ask
how near its 98 618 candidates come to the console's delivered walk endpoint:

| | |
|---|---|
| nearest fan walk endpoint | **0.212771 u** |
| nearest inside its own lean class | 0.347330 u |
| a bit-exact endpoint anywhere in the fan | **no** |
| the razor's strip at that configuration | 1.877e-04 u |

So the fan misses the one plan known to work by about **1100 strip-widths** - and it is not a near miss
that a finer sweep of the same shape closes, because the shape itself is wrong.

## Two knobs excluded it, and neither is the razor

The console's plan is `(0, 208, 110, 0, 2, 169, 192, 0, 2)`: no base frames, then its first letter held
**2** frames, then its second held **2**.

* **`PRE_FRAMES = (1,)`.** `fan_exact`'s two-segment family is `n0` base frames, ONE pre frame, then a
  uniform hold ([`_families`](../../harness/tetrapush/overnight.py) is a single held stick by
  construction). A 2+2 split is not in that set at any alphabet.
* **`PRE_STRIDE = 32`.** The pre segment is drawn from 57 decoded classes of 11 405, and the console's
  first letter `(208, 110)` is in the stride-1 and stride-2 class sets and **in none coarser**.
* **And the hold letter needs stride 1.** `(169, 192)` is a member only of the full grid. That is the
  trap in "just raise the pre resolution": `fan_exact` sizes its hold alphabet to `LEAF_BUDGET`, so a
  bigger pre makes the autoscaler coarsen the hold and break containment the other way. Both segments
  have to be paid.

**The machinery reaches it; only the enumeration does not.** Hand `overnight._fan` the console's own two
letters at its own split, off the same base core and camera trail, and the walk endpoint comes back
BIT-IDENTICAL to the fixture's own, at the cap, with the fixture's own roll lean - and its roll entry is
the delivered entry, 0-ULP, `genuine`, `offset_u` exactly 0.

## Why twelve green containment checks did not see it

`verify_console` checked the plan's letters against `entry_fan.stick_alphabet(1)` - the stride-1 grid -
which is a FINER alphabet than the run draws its pre segment from, and it never checked the split shape
at all. Everything downstream of generation was verified honestly: the letters are real classes, the aim
byte reaches its own facing, a real A-press re-derives the entry, and the plan is deliverable end to end.
None of that is the claim "the fan would produce it".

The general lesson, and it is the one to carry to the next search: **verify containment against the
alphabet and the plan SHAPE the run actually enumerates, at the knob values it will run with** - not
against the finest ones the module can express. `containment_knobs` reports both, plus the price.

## What containment costs, and it was paid

`_fleet_estimate` at walk 4, two-segment, atom off:

| knobs | fleets |
|---|---|
| legacy (`LEGACY_PRE_STRIDE` 32, `LEGACY_PRE_FRAMES` (1,)) | 353 |
| minimum containing (stride 2, `PRE_FRAMES` (1, 2)) | 33 563 |
| **shipped** (stride 2, every split a walk admits) | **40 274** |

**114x**, calibrated at **0.357 s a junction / ~2 h an item** against the legacy ~1 min - and
**measured at 7.1 h for the full console item** (session 163: 20 096 junctions, 3x the calibration
slice, because `PRE_FRAMES_ALL` expands every split; 459M raw leaves, 5.6M at-cap candidates; fan
3.6 h + scoring 3.5 h at ~10 threads, ~3.7 GB peak). Session 161 shipped it anyway: a search that
cannot emit its own known answer measures nothing, so the affordability problem belongs to the
enumeration's shape and not to its coverage. Three things make the price honest rather than hidden:

* `PRE_FRAMES` is now the `PRE_FRAMES_ALL` sentinel, expanded per walk by `pre_frames_for` - **every**
  split a walk admits, not just the console's own 2+2, because a knob set fitted to the known answer
  would contain exactly one plan.
* the hold alphabet is **PINNED** at stride 1 (`alpha_for`), so the leaf budget can no longer buy a
  finer pre by coarsening the hold. An item that does not fit reports `over_budget` instead.
* `containment_knobs` and `verify_console` take the knobs as arguments and answer **at the values the
  run will use**, which is the one thing the s160 version could not do.

## Aiming does not pay it off

The obvious discount - compute where the walk has to END ([entry-strip.md](entry-strip.md)) and skip the
junctions that cannot reach it - was built and measured in session 161, and it is small: see
[aiming-the-fan.md](aiming-the-fan.md). The admissible prune is **1.4x** and the lossless ordering about
**2.4x** on time-to-first-hit. Containment's 114x is still unpaid.

## The closed loop ran, and the fan emitted the answer (session 163)

`overnight item console-w04 incumbent=102` at the shipped knobs - the exact pipeline a production
sweep runs, no special-casing - produced **8 genuine plans, all thrust 15 / total 101** (residuals
5.18e-05..1.14e-04, lean cells 2551/2552), and one of them is **bit-for-bit the console's own plan**
`(0, 208, 110, 0, 2, 169, 192, 0, 2)` from the containment fixture. The saved incumbent's confirm
stack reads `worst_ulp 0`, every check True, `stage: 'deliverable'`. This is the closed-loop form of
Dereck's session-151 rule: not "the fan CONTAINS the answer" (s161's geometric claim) but "the run,
launched blind, FINDS it".

The density is the caveat that travels: **8 genuine, not the hundreds** the naive arithmetic
(~6900 at-cap leaves a junction, a 5 u target curve, a 1.2e-04 u strip, 20k junctions) predicted -
the strip's genuine density is 1-2 orders thinner than the area ratio, consistent with the razor
being a positive-interval CURVE ([razor-zero-curve.md](razor-zero-curve.md)) rather than a band that
accepts everything inside it. **Session 164 decomposed the gap on this run's own funnel**: the area
arithmetic is roughly right about rows-on-the-strip (~200); the missing factor is the ACCEPTANCE
(every recorded near row refused ``blocked``), and it concentrates in 2 of the 135 draws - which a
~1-minute per-item probe can find without the fan. See
[admitting-draws.md](admitting-draws.md); price scheduling on measured counts, not on the ratio.

## What this invalidates, and what it does not

**Suspect:** every "0 genuine" the driver reported from when it started running items until session 160 -
the s155 sweep, the s159 barren re-read's premise that those items were "rolling from a place where no
position of hers can clip", and any bound argued from a fan's coverage. Those runs used a generator that
provably cannot produce the one plan known to work, so their zeros are statements about the generator's
reach first. Closing the gap does not retroactively make them measurements; the items have to be re-run
at the shipped knobs.

**Unaffected:** everything measured on the razor rather than on the enumeration - the genuine residual
band and its sufficiency ([genuine-residual-band.md](genuine-residual-band.md)), the 16 ms screen and the
admitting map ([admitting-configurations.md](admitting-configurations.md),
[razor-zero-curve.md](razor-zero-curve.md), [admitting-entry-region.md](admitting-entry-region.md)), the
lean's 129 cells ([lean-cells.md](lean-cells.md)), and the strip this page's companion measures
([entry-strip.md](entry-strip.md)). Those take a configuration and a position and ask the sim; no fan is
involved.
