# "Every aim in the window fires the roll" (session 79 -> session 88, 2026-08-02)

> **status: historical** - this records a claim that was measured, written down, gated, and used to
> widen a search by 13x, and it was wrong because the engine it was measured on shared the omission.
> Current truth is [mechanics/roll-attack-threshold.md](../mechanics/roll-attack-threshold.md).
> Kept for the lesson, which is about measuring a dispatch on the model that dispatches it.

## What was claimed

Session 79 built the Courtyard entry search's aim alphabet off
`two_roll.reachable_stick_fan(msd_min=1.0)` - the saturated octagon-boundary byte pairs - and got six
aims in the seam window. Session 80 called that floor unphysical and removed it:

> That floor is not a physical one: `_set_stick_data` latches the target from ANY non-dead-centre
> stick and `_roll_init` snaps facing to it unconditionally, while the roll's speed comes from the
> walk cap and not from the stick. **Measured, every aim in the window fires the roll and lands on
> the facing it commands**, so the alphabet is the whole decoded-angle grid - 81 in the seam window,
> not 6.

It was gated (`test_the_aim_alphabet_is_the_whole_decoded_grid_not_its_octagon_boundary`), banked as
one of the "~40x more independent loci" that made the razor search affordable, and every pass from
s80 to s87 drew from it.

## What it actually is

The reasoning about the ROLL is correct and still stands: a roll needs no magnitude, its speed comes
from the pre-roll `speedF`, and `_roll_init` snaps facing to the latched target at any deflection.
What it skips is **getting** the roll. `setDoStatusBasic` (`d_a_player_main.cpp:2220`) only sets
`dActStts_ATTACK_e` - the one status `checkNextActionFromButton` turns into `procFrontRoll_init` - for
`mStickDistance > mBasic.field_0x1C` = **0.75**. Below it the press is `PUT_AWAY` and Link sheathes.

## Why the gate could not see it

"Measured, every aim fires the roll" was measured in the sim, whose roll dispatch tested `msd > 0.05`
- the locomotion floor - so it could only ever agree. `confirm_entry`, the check whose whole job is
"does Link actually roll from here", replays a real A-press **on that same engine**, so it confirmed
sub-threshold aims too. A gate is only evidence about the thing it does not share with the claim.

The alphabet dedupes the byte grid by decoded ANGLE and keeps the first pair in grid order, which is
usually a shallow interior one - so the widening did not merely add deep aims, it **replaced**
representatives with shallow ones. Angle 28732 is represented by `(154,170)` at msd 0.540 while the
human's own press for the same angle is `(181,236)` at 1.0.

## What it cost

One console delivery, which is what falsified it: the frame-minimal hit of session 87's 55-candidate
pass, aim `(95,168)` at msd 0.5705. The movie went out exactly as authored and Link never entered
`FRONT_ROLL` at all - at the sampled frame he is walking to a stop with Tetra bit-identical to her
pre-roll position, because he never reached her. `fixtures/courtyard_attack_gate_s88_console.json`.

Of that pass's 55 confirmed, DTM-deliverable hits, **36 used the shallow representative** and could
never have rolled; 19 survived, and the frame floor moved 4 -> 5. The seam window's alphabet is 60
aims / 45 cells rather than 81 / 49, and the cell at facing 40834 has no deep member at all.

Session 80's correction of s79 was still right, and the honest reading is the one in between: the
alphabet is every ANGLE, each represented by a member deep enough to dispatch
(`two_roll.roll_aim_fan`).

## The lesson

**Measure a dispatch against the decomp, not against the model that performs it.** Every part of this
claim was checked - swept, gated, cross-checked against the recorded human's own inputs - and the one
unchecked assumption was the branch that decides whether the press is a roll at all. The
`contains_human` containment check passed throughout, because the human's stick is a grid member by
construction; containment tells you the space is wide enough, never that every member is legal.
