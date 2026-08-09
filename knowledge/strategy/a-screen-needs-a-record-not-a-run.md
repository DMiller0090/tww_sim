# A screen needs a record, not a run

**Answers:** My search stage fires hundreds of rollouts and keeps three - what does it actually need
from each one? How do I drop a fast kernel into a stage without changing which candidates survive?
Why did my port's speedup land far below the ratio that named it, again? How do I pick a seed for a
gate that compares two implementations?
**Status:** The herd search's roll stage runs its aim screen on
[the fan kernel](the-fan-pays-for-one-camera.md) instead of one wired rollout per aim, and the stage
is bit-identical either way ([`tests/test_fan_stage.py`](../../tests/test_fan_stage.py)). One cycle-1
stage: **6719 wired steps -> 2251 wired + 4566 native**, so 66% of the stage moved onto the C engine
- **3.000 s -> 1.078 s (2.78x)**, same candidates.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`roll_candidates`, the ``env``/``twin`` path), `roll_kernel.RecordRun` / `node_twin`. Measured
session 129.

## The stage discards every run it makes

`roll_candidates` is two passes. R1 sweeps the reachable aim fan crossed with the L windows, prunes,
ranks, and keeps three. R2 re-runs those three over the camera-target grid and keeps the ones a next
junction can continue from.

R1 is ~74% of the stage's rollouts and its entire output is **three `(want, aim, l_window)`
triples**. Every `FreeRun` it built to get them is thrown away. So the question is not "how do I make
these rollouts cheaper" but "what do these rollouts have to RETURN", and the answer is small: the
prunes and the rank between them read Link's XZ / facing / travel / speedF / proc, Tetra's XZ, the
csangle and the follow flag. Nine fields, all of which `roll_kernel.segment_record` already carries
because the kernel's own gate demanded the whole record.

That is what makes the swap a drop-in rather than a rewrite. `RecordRun` presents a record in the
shape a run is read in, so `two_roll.metrics`, `two_roll.alive`, `frame_in_model` and the beam's
`rank_key` run over fan records **unchanged** - no second expression of a prune to keep in step with
the first. It deliberately cannot step, and it carries only those nine fields, so a consumer that
reaches for something else raises `AttributeError` on that line instead of reading a stale default.

R2 stays wired, and the reason is the same question answered the other way: its survivors ARE their
runs. The candidate carries one forward into the next cycle and `junction_quality` steps it.

## Three traps, and only one of them is about physics

**The order is part of the answer.** The screen ranks with a stable sort, so ties break by insertion
order - and the fan evaluates a whole aim fan per L window while the wired loop walks (aim, window).
Emitting the records in fan order changes which of two tied aims survives the keep. The fix is one
line (walk the fans in the wired path's order); noticing it is the work. The gate squeezes both keeps
to one so that order decides the entire stage output rather than three-of-many.

**A twin is exact about whatever state it reaches.** The fan runs on a native twin rebuilt by
replaying the node's input log from f0, which rests on *a node IS its log*. That had never been
checked past the csangle. It holds - a banked `junction_beam` endpoint replays to the Link position
and camera the fixture recorded from the search's own run - but `node_twin(check=)` now asserts it at
runtime anyway, because a log that no longer reconstructs its node would make every record in the
stage bit-exact about a state the search never visits, and nothing downstream could tell.

**A gate that compares two empty lists proves nothing.** The obvious seeds - the banked cycle-2
junction endpoints the roll kernel is gated on - return NO candidates at any thinning: from ~40-70 u
behind Tetra a ~205 u `FRONT_ROLL` ends 231-253 u away, past `FOLLOW_ENGAGE_DIST`, and `alive` prunes
the fan on ``followed`` (the few that stay inside it end AHEAD of her and die on ``lead``). Both
implementations agreed perfectly and said nothing. The seed that earns the equality is cycle 1's own
prologue node - state 2 plus one L-held flip frame - which is where the first roll stage really runs
and which returns five candidates. Assert the comparison is non-vacuous, or it will quietly stop
being one.

## The accounting, and where the cost went next

Counted first, so the figures do not move with machine load - one cycle-1 roll stage at the shipped
knobs:

| | wired steps | native steps | wall clock (idle) |
|---|---|---|---|
| the stage as it was | 6719 | 0 | 3.000 s |
| the stage on the fan | **2251** | 4566 | **1.078 s** |

R1's 4468 wired steps become 4566 native ones plus one camera trace per L window and one log replay
per node. At the s128 engine rates (2431 wired / 62682 native steps per second) that predicts ~17x on
R1 and ~2.8x on the stage, and the clock agrees: **2.78x**, same five candidates. Which is
[the look-pair lesson](../model/porting-the-look-pair.md) arriving on schedule - a part that is 74%
of the work returns 2.8x, not 17x, because what is left does not get cheaper. Quote the stage.

**And the leftover is now the whole wired cost.** All 2251 remaining wired steps are R2: the 25
camera targets per kept aim, plus the `junction_quality` glide on each survivor. The lever for it is
already measured and gated in the same module - `target_cs_is_exit_only`: inside a roll the camera
target changes nothing but the camera, so those 25 rollouts are the same physics 25 times and differ
only in the exit tail. That is a shared-body kernel, not a fan, and it needs its own divergence-frame
gate rather than the assumption.
