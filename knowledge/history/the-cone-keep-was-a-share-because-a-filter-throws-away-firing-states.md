# The cone keep was a share because "a camera filter throws away firing states" (retired s122)

status: historical
Source: superseded by [../strategy/the-shape-of-a-cut-is-not-its-answer.md](../strategy/the-shape-of-a-cut-is-not-its-answer.md) (session 122)

The SHAPE still ships - the keep is still a share by default - but this ARGUMENT for it was measured
wrong. Was current sessions 116-121. Code:
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`lok_probe_key`,
`as_requirement`, `roll_candidates`' ``tcs_probe``/``tcs_require``).

---

## The claim as it stood

Session 116 made the last cycle's ``l_ok`` cone (`away_walk.lok_clear`) a KEEP SHARE in
`roll_candidates`' ``tcs_probe`` - one order of three in a `_mixed_beam` of `tcs_keep` 3 - and gave
two reasons for the shape:

1. **The session-73 calibration.** A camera term used as a FILTER throws away firing states: swept
   over 16 arrivals x 41 camera targets, 274 cells fire at the live csangle and only 12 snap, so a
   filter on the bill would discard **96%** of the firing cells. Applied to the cone: a share, never a
   filter.
2. **``dips`` refuses the other half whatever the camera does**, so a camera requirement could not
   pay for itself.

Reason 2 was retired first, in session 121 - see
[dips-refuses-the-other-half.md](dips-refuses-the-other-half.md) and
[../strategy/the-dip-budget-is-not-the-lever.md](../strategy/the-dip-budget-is-not-the-lever.md).

## Why reason 1 is retired

**The 96% is a property of the SNAP BILL (`camera_probe_key`), and it does not transfer to the cone.**
The bill is a sufficient condition for firing and a badly incomplete one - a camera steer also moves
the arrival's own EBS facing, so a non-snapping target can put Tetra out of the front cone by itself.
`lok_clear` is not that: session 117 priced every reachable state at two rolls and found **107 of 107
clearing states fire and 118 of 118 non-clearing states fire nothing**, and session 121 ran it at all
99 endpoints of the uncapped census for **45 of 46 firing vs 0 of 53 dead**. A predicate with no false
positives does not "throw away firing states" when used as a filter - it throws away states that fire
nothing.

Measured directly (session 122, `_notes/s122_shape_preflight.py`, at the population's own 33 R2
cells): as a requirement the cone drops **zero junction nodes**, because all 8 cells it empties sit at
a pre-roll node that still holds live cells on another aim or L window. The share, meanwhile, was
spending **54 of its 99 kept slots** on camera targets that can never fire.

## What replaced it, and what did not change

The shape still ships as a SHARE - `extend_cycle`'s ``lok_require`` is default-off - but for a
different and measured reason: the two shapes **tie on the answer** (best delivered 105.00 at the same
endpoint), so the default stays where every banked beam's provenance already is. The current-truth
page carries the A/B and the recommendation for new cuts:
[../strategy/the-shape-of-a-cut-is-not-its-answer.md](../strategy/the-shape-of-a-cut-is-not-its-answer.md).

The s73 calibration itself is untouched and still correct **about the bill** - see
[../strategy/the-camera-supplies-the-cone.md](../strategy/the-camera-supplies-the-cone.md) and
`camera_probe_key`, where it is what keeps that probe a share.
