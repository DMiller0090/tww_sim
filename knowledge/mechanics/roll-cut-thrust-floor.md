# The earliest a roll can cut, and the frames a search spends not knowing it

**Answers:** How early can the B thrust fire out of a forward roll? Does holding the stick during the
roll open the cut window sooner? My frame-minimal search returned a plan that is provably late - what
cost was it not counting?
**Status:** decomp-derived and gated (session 99), against the HIO data and the console-delivered
Courtyard clip, in [`tests/test_entry_reach_stations.py`](../../tests/test_entry_reach_stations.py).
**Source:** `tww/src/d/actor/d_a_player_main.cpp` (`procFrontRoll` 6852, `procFrontRoll_init` 6817,
`setSingleMoveAnime` 12795), `tww/src/d/actor/d_a_player_HIO_data.inc` (`daPy_HIO_roll_c0::m`),
[`harness/tetrapush/entry_fan.py`](../../harness/tetrapush/entry_fan.py) (`THRUST_FLOOR`, `plan_cost`),
[`tww_sim/land/procs/roll.py`](../../tww_sim/land/procs/roll.py).

## The gate is the animation frame, and only that

`procFrontRoll` routes to a cut through `checkNextMode(1)`, and reaches it on one condition:

```c
if (mFrameCtrlUnder[UNDER_MOVE0_e].getFrame() > m_HIO->mRoll.m.field_0x10) {   // 17.0
    checkNextMode(1);
```

The roll's frame control is set by `procFrontRoll_init` through
`setSingleMoveAnime(anm, f32 rate, f32 start, s16 end, f32 morf)`:

| | field | value |
|---|---|---|
| rate | `mRoll.field_0x8` | **1.1** per frame |
| start | `mRoll.field_0xC` (passed as `param_1`) | **0.0** |
| gate | `mRoll.field_0x10` | **17.0** |

So `getFrame()` after k frames is `1.1k`, and `1.1 × 16 = 17.6` is the first value past 17.0. **The
earliest cut dispatch is roll step 15** - `cut_step` 15, which on the Courtyard corner's indexing is
**thrust 13**.

Two things worth stating because both were guessed wrong before being checked:

- **the start frame is 0.0.** The sim initialises `roll_frame = 0` and that is correct - but only by
  luck of the value, since the model's roll HIO block never carried `field_0xC` at all. `setSingleMoveAnime`
  takes rate BEFORE start, and the same argument slot is read as a rate for the roll and as a start for
  the cut, so the layout is worth re-deriving rather than pattern-matching.
- **the stick is not in the gate.** `mStickDistance` appears in the *other* branch of `procFrontRoll` -
  the `getRate() < 0.01` path, where a neutral stick subtracts `field_0x20` from `mNormalSpeed`. Holding
  the stick up (or any direction) through the roll cannot make the cut window open sooner. It does change
  the cut's AIM once the window is open (`_roll_exit`: `aim = target if msd > 0.05 and not l_held`).

## What the search was not charging for

`entry_fan.plan_frames` counts a plan's **walk holds** - the base hold plus each segment's - and that is
what `stream_search` ranks on and `capped` prunes on. The thrust is modelled as a third *draw* axis,
because each step bakes its own locus ([../strategy/clip-entry-search.md](../strategy/clip-entry-search.md)),
so it never appeared in a frame count at all.

It is a frame count. Reading the delivered clip's own log indices:

    a_i     = n_console + plan_frames        the A-press
    entry_i = a_i + 1                        the first FRONT_ROLL frame
    b_log   = entry_i + thrust + 2           the UP+B
    cut     = b_log + 1

so the cost from the seed to the cut is `plan_frames + thrust + 4` (`entry_fan.plan_cost`), and the
console fixture agrees exactly: `cut_i − n_console` = 23 = 4 + 15 + 4.

**The delivered clip is thrust 15 against a floor of 13 - two frames the frame-minimal objective could
not see.** A thrust-15 clip and a thrust-13 clip ranked as equal cost, so a pass had no reason to prefer
the cheaper one, and every delivery this corner has made went to whichever thrust the geometry happened
to light up.

## What it costs to collect

Each thrust bakes a different locus, so a lower thrust is not a discount on the same candidate - it is a
different search. Measured over the frame-floor reachable hull
([../strategy/clip-station-reachability.md](../strategy/clip-station-reachability.md)):

| cell | thrust 15 | thrust 14 | thrust 13 |
|---|---|---|---|
| 2552 (delivered) | 208 live stations | 111 | **0** |
| 2553 | 0 | 918 | 0 |
| 2551 | 220 | 0 | 0 |
| 2549 | 0 | 10 | 0 |

So one frame is plausibly available at the delivered facing (thrust 14) and **thrust 13 has no reachable
live station at any cell sampled** - the full two frames would need something else to move, the pushed
actor's placement being the obvious unexplored candidate.

## The rule

**A quantity a search treats as a free axis is only free if it is absent from the objective's unit.**
The thrust earned its place as a draw axis honestly - three independent loci for one alphabet - and that
framing quietly carried it past the frame count, because the frame count was written for the walk. When
an axis is added for the *variety* it buys, re-ask what it *costs*.

## See also

- [../strategy/clip-entry-search.md](../strategy/clip-entry-search.md) - the thrust as one of the three
  draw axes, which is where it entered.
- [../strategy/clip-station-reachability.md](../strategy/clip-station-reachability.md) - the per-thrust
  live-station census the table above comes from.
- [roll-attack-threshold.md](roll-attack-threshold.md) - the *other* roll gate a press has to clear, on
  deflection rather than frame.
