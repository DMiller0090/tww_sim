# The search could not generate its own known answer, and the gate said it could

**Answers:** My search reports 0 genuine over hundreds of items - is the space empty, or can my
GENERATOR not express the answer? What does a containment gate actually have to check? Which of my
barren results survive finding out? What does containing the known answer cost?
**Status:** MEASURED (session 160) on the flooded-Hyrule Tetra corner, against the LOCKED console
delivery fixture. Gated in [`tests/test_overnight_driver.py`](../../tests/test_overnight_driver.py) - one
`xfail(strict)` for the gap itself, one that pins the diagnosis, and one that proves the fan's own
primitive reaches the endpoint bit for bit. The rule it belongs to is Dereck's, session 151: a search is
not trusted until it rediscovers a known answer.
**Source:** [`harness/tetrapush/overnight.py`](../../harness/tetrapush/overnight.py)
(`containment_knobs`, `verify_console`, `fan_exact`, `_families`).

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

## Two knobs exclude it, and neither is the razor

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

## What containment costs

`_fleet_estimate` at walk 4, two-segment, atom off:

| knobs | fleets |
|---|---|
| default (`PRE_STRIDE` 32, `PRE_FRAMES` (1,)) | 353 |
| containing (stride 2, `PRE_FRAMES` (1, 2)) | 33 563 |

**95x**, and the default fan already costs ~56 s an item on this hardware. That is a real decision, not a
bug fix - which is why the numbers are gated rather than the knobs quietly raised.

## What this invalidates, and what it does not

**Suspect:** every "0 genuine" the driver has reported since it started running items - the s155 sweep,
the s159 barren re-read's premise that those items were "rolling from a place where no position of hers
can clip", and any bound argued from a fan's coverage. Those runs used a generator that provably cannot
produce the one plan known to work, so their zeros are statements about the generator's reach first.

**Unaffected:** everything measured on the razor rather than on the enumeration - the genuine residual
band and its sufficiency ([genuine-residual-band.md](genuine-residual-band.md)), the 16 ms screen and the
admitting map ([admitting-configurations.md](admitting-configurations.md),
[razor-zero-curve.md](razor-zero-curve.md), [admitting-entry-region.md](admitting-entry-region.md)), the
lean's 129 cells ([lean-cells.md](lean-cells.md)), and the strip this page's companion measures
([entry-strip.md](entry-strip.md)). Those take a configuration and a position and ask the sim; no fan is
involved.
