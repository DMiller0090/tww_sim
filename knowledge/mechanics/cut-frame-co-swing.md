# The cut frame's Co-centre swing

**Answers:** Why does the same corner clip on one thrust and refuse on the one two frames earlier,
when the animation is identical? Which frame of a roll can a cut actually collect a push on? Why is
sweeping the pushed actor's placement, velocity, lean and aim all worth so little at the floor thrust?
**Status:** derived and gated (session 103) on the flooded-Hyrule Tetra corner, in
[`tests/test_tetra_motion.py`](../../tests/test_tetra_motion.py)
(`test_the_cut_frames_co_swing_is_the_whole_difference_between_the_thrusts`,
`test_the_swing_is_visible_as_overlap_gained_or_lost_on_the_cut_frame`). The control is the delivered
thrust-15 clip, whose free 1.2 u of overlap this predicts the sign and the frame of.
**Source:** [`harness/tetrapush/razor_depth.py`](../../harness/tetrapush/razor_depth.py)
(`cut_frame_swing`, `co_centre_offsets`).

---

## The one number

A corner clip is bought with `push_u`, [the push's projection on the `old -> S` ray](../strategy/clip-razor-depth.md),
and the pushed actor shoves Link **directly away from herself**. So the only place she can pay from is
**up-ray, behind him**. The cut consumes the Co overlap on frame `cut_step - 1`, and by that frame Link
is braced against the corner, so his feet contribute nothing and the Co centre's entire step is the
animation's. Project it on the roll direction:

    swing  =  (off[cut_step-1] - off[cut_step-2]) . m_hat

`off[k]` is the animation-posed Co centre's offset from his feet, the root/neck joint midpoint the
engine accumulates. Positive means the cylinder is moving forward, **away from the one direction that
pays**; negative means it is **swinging back onto her**.

| thrust | `cut_step` | cut-consumed frame | swing | frame before |
|---|---|---|---|---|
| 13 | 15 | 14 | **+8.9252** | +8.07 |
| 14 | 16 | 15 | **+1.8547** | +8.93 |
| 15 | 17 | 16 | **-1.2850** | +1.85 |

That ordering **is** the push ordering measured independently in the depth law (`push_u` +0.1304 /
+0.4773 / +0.5175 at thrust 13 / 14 / 15). The delivered clip's contact is not a lucky placement: it
is the frame on which the cylinder comes back.

## Why it is a property of the animation and not of a search

`off[k]` is a pure function of `(facing, roll_frame, lean)`. `roll_frame` is a fixed `f32` accumulation
of `ROLL_RATE`, so it is pinned by `k`. The [lean is spent](roll-lean-decay.md): `m351C` decays 35 %
per frame, so the delivered draw is -1 by roll step 15 and cannot move a pose there. And the facing
rotates the offset **and the ray together**, so over the whole 45-cell aim window the swing varies by
less than **1e-4**.

There is no knob on it. A search may move where she stands, how fast she is closing, which aim cell
fires and where Link enters; none of those change which frame of the roll the cut lands on, or which
way the cylinder is travelling when it does.

## What the roll is actually doing

The Co centre sweeps forward to +31.3 u during the launch, then back through the tuck to -13.5 u at
roll step 11, then straightens hard:

    step   9   10    11     12     13     14     15     16     17
    along -0.7 -8.1 -13.5  -13.2   -5.1   +3.8   +5.7   +4.4   +4.0

The straightening is the fast part, +8.07 then +8.93 u/frame, and **thrust 13's cut lands on both of
them**. Thrust 15's lands two frames later, after the recovery has settled and reversed. Same
animation, and this names exactly which property of "a different frame of it" does the work.

## What it costs a search

The overlap the cut sees is not free of the frames before it: the plow resolves the whole penetration
each frame ([the ejection equilibrium](plow-ejection-equilibrium.md)), so a spot that is touching on
the cut frame was touching more deeply the frame before and has been thrown out for it. With the
cylinder receding at 8.9 u/frame, reaching the corner's
[required overlap](../model/required-cut-contact.md) on the cut frame demands roughly twice that much
overlap on the frame before, and twice again on the one before that, a chain that runs past the 80 u
radius sum within three or four frames. Her own closing speed (capped at 10 u/frame and decaying 1.0
with no drive inside 130 u) offsets part of it, and is why the floor thrust's best measured depth moved
from -0.19 to about +0.067 once her velocity was swept. It does not turn the sign of the swing.

## Reading it on a new corner

`cut_frame_swing(facing, thrust)` is analytic and instant, so **check it before pricing a thrust**. A
thrust whose cut-consumed frame has a positive swing is collecting its push from a receding cylinder,
and every downstream search is fighting that; one with a negative swing gets contact for free. It is a
gate and not a rate: a negative swing admits a clip, it does not supply the dust or the plan.
