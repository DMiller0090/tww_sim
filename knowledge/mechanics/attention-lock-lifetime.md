# Attention lock-on lifetime (NONE / LOCK / RELEASE)

**Answers:** How long does a lock-on target keep driving the ATN_ACTOR procs after L is let go? Which
check ends the lock -- the front-of-player cone, the target existing, or the reticle fade? Why does
the Courtyard roll keep exiting into the untarget brakeslide even after Tetra has swung out of frame?
**Status:** validated live 0-ULP (2026-07-26): the second Courtyard cycle's brakeslide dispatches on
the console's frame (`tests/test_node1_console.py` n=68..71 exact), and the state machine is gated
offline by `tests/test_atn_actor.py`.
**Source:** decomp `d_attention.cpp` `judgementStatusHd` (804-844) / `judgementLostCheck` (751) /
`chaseAttention` (563) / `runDrawProc` (653); sim `tww_sim/land/attention.py` + `_anmc.pyx`
`_atn_update`.

---

`dAttention_c` holds three states -- NONE, LOCK, RELEASE -- and `LockonTruth()` is true in both LOCK
and RELEASE. That truth IS `mpAttnActorLockOn != NULL`, which is what `checkNextMode` reads to route a
roll exit into the ATN_ACTOR procs (9 moving / 8 stopped) instead of MOVE. So the RELEASE tail is the
whole reason [the untarget brakeslide](brakeslide-ebs.md) exists: L is already gone when it runs.

## Each state consults a DIFFERENT gate

This is the part that is easy to get wrong, because all three read like "is the target still there".

| State | What ends it | Decomp |
|-------|--------------|--------|
| NONE | nothing; the L rising edge ACQUIRES via `chaseAttention()` (cone + distance) | 810 |
| LOCK | `judgementLostCheck()` -- `chaseAttention()` again, so leaving the front cone drops it THAT frame | 816 |
| RELEASE | `LockonTarget(0) == NULL \|\| !AttnFlag_40000000` -- the frozen list entry, or the reticle fade completing | 837 |

RELEASE never calls `chaseAttention`. A target that swings out of the front cone mid-fade keeps the
lock until the fade runs out, and the list cannot change underneath it either: `stockAttention` only
runs in the NONE branch, so `LockonTarget(0)` stays whatever LOCK froze. For an actor that does not
despawn, RELEASE is therefore a pure countdown.

The fade length is the reticle `YJ_DELETE` anim, `end=10 / rate=1.0` -- an animation constant, not a
tuned latency. `runDrawProc` clears `AttnFlag_40000000` when it completes; the value itself lives in
[reference/constants.md](../reference/constants.md#land-movement) with the rest of the land family.

## Why it matters (the Courtyard push)

The push's second cycle releases L while Link is mid-roll and still swinging. Tetra leaves the
±0x4000 cone partway through the fade, so a model that gates RELEASE on the cone drops the lock ~5
frames early, and the roll exits into MOVE_TURN (24) instead of ATN_ACTOR_MOVE (9). The console does
the opposite: it spends the full fade locked, takes its one proc-9 brakeslide frame, and only then
falls to MOVE. Session 57 read that straight off the tier-2 gate -- the sim and the console dispatched
different procs at the same frame -- and the fix is one gate, not a timing constant.

The acquisition side of the same cone is why the lock is picked up MID-ROLL rather than at state 2;
that is [tetra-follow.md](tetra-follow.md)'s `dist_table[0xAB]` geometry.
