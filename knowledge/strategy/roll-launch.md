# Roll launch (fastest standstill → roll-chain)

**Answers:** From a standstill, what is the fastest input sequence to get into a high-speed roll
chain? Why hold L on the first frame? Why does a slight up-left/up-right (off-axis) stick beat
straight-up? Why does the frame-6 roll cap at ~25.9 instead of the full 26? Can the camera help?
**Status:** SIM-DERIVED (mechanism is decomp-grounded; the exact magnitudes/ceiling are sim numbers,
**DTM/live validation pending**). The core tech (L + slight-diagonal before straightening) is a
runner-known technique the sim reproduces.
**Source:** decomp HIO `mAtnMove`/`mMove` constants + `_update_atn_direction` (`setBlendAtnMoveAnime`
@3280) + `procFrontRoll`; sim exploration 2026-07-06 (native `LandCore`, seeded from savestate 6 =
the resting-anchor defaults). Constants live in [`land-movement.md#values`](../mechanics/land-movement.md#values).

---

## The sequence (from a forward standstill)

1. **Frame 1: L-target + full-forward** (hold each 1 frame combo; L only this frame).
2. **Slight off-axis full-magnitude stick for ~3–4 frames** — up-left or up-right at the octagon
   edge (raw `(96,255)` ≈ **8.6° off**; `(159,255)` mirrors it). Release L after frame 1.
3. **Straighten to full-forward and hold A** — the roll fires ~frame 6 and chains (roll speed is
   maintained across rolls; hold A + forward).

Over a ~2.5-roll horizon (46 frames from rest) this nets **~1066.8** forward vs ~1058.7 for a plain
straight-up-then-roll and ~365 for rolling immediately. Breakdown: **L-on-frame-1 alone ≈ +5.7**,
the **slight off-axis ≈ +2.4 more** (both banked permanently once the roll chain saturates).

## Why L on frame 1 (the +5.7)

From a standstill, holding L enters `ATN_MOVE`. The **first ATN frame** takes the side branch
(`mDirection` is still `NONE` at entry), which injects speed at **`ATN_SPD = 5.0`** — vs the walk's
target-speed scale **`F14 = 3.5`**. So `mNormalSpeed` jumps to 5.0 that frame instead of 3.5. Both
paths hit the 17 cap at the same frame, but the head start is a *permanent position lead* because
the roll chain equalizes speed afterward (a higher `speedF` earlier is never repaid). This is the
[ATN_MOVE tier](../mechanics/land-movement.md#brakeslide-l-held) engaged for one frame from rest.

## Why the slight diagonal beats straight-up (the +2.4)

`_update_atn_direction` picks the next frame's `mDirection` from `cos(travel − facing)`:

- `cos ≥ ATNB_COS_FWD (0.99)` → **`DIR_FORWARD`** → next ATN frame uses the walk path (**+3.5**).
- otherwise → a **SIDE** direction → next ATN frame uses the side branch (**+5.0**).

Straight-up keeps travel = facing → `cos = 1` → FORWARD → only **one** 5.0 frame (the entry). A
slight off-axis stick pushes `travel` off `facing`; if `cos(travel−facing) < 0.99` the direction
buckets **SIDE**, so the *second* ATN frame also injects 5.0. That extra +1.5 `nspeed` on frame ~3
is the whole edge. From frame 4 on both are plain walk (+3.5), so the lead is preserved into the
roll (higher `speedF` at entry → faster roll).

The threshold is `arccos(0.99) ≈ 8.11°`, but the game's **s16 cosine table** pushes the effective
boundary out: `(97,255)` at 8.13° still reads FORWARD; **`(96,255)` at 8.63° is the first that
trips SIDE**. So the useful deflection is right at the octagon edge (X ≈ 95–96 / 159–161), NOT a
mild tilt — a mild tilt stays FORWARD and does nothing. It is a precise, edge-of-gate input.

## Why the frame-6 roll caps at ~25.9, not 26

Roll speed = `clamp(speedF·1.5 + 0.5, 5, 26)`; the 26 cap needs `speedF ≥ 17` at entry. The frame-6
roll tops out at `speedF ≈ 16.94` → **25.9**. The missing 0.06 is structural:

- Getting the *second* SIDE frame requires the *setup* frame to be off-axis, but that frame's own
  injection is `5.0 · cos(travel_change)`, and **`travel_change == the off-axis angle θ`** (from
  rest, `travel` chases `0 → θ` in one frame). The same θ must exceed the SIDE threshold, so
  `cos(θ) < 0.99` is *forced* → the setup-frame injection is pinned at **`5·cos(8.63°) = 4.944`**.
- You can't have both a clean +5.0 setup frame *and* a SIDE next frame: straight is +5.0 but snaps
  FORWARD (no bonus); off-axis earns the bonus but costs the setup-frame cosine. Net `speedF ≈ 16.94`
  at frame 5.

So the choice is **f6 @ ≤25.9** (what this tech gets) or **f7 @ 26.0** (straight-up, one frame later
→ less total distance). A full-26 roll *earlier* than f7 is unreachable from a standstill.

**Camera doesn't help.** The side-branch injection is a fixed rate (`ATN_SPD`), independent of the
off-axis angle (16° injects the same ~5.0, and rolls slightly *worse*), and hard-capped by the
side-direction `mMaxNormalSpeed = ATN_MAX (12)`. The camera only re-aims the world target — which the
stick already controls — so it adds nothing (a pre-set camera merely reproduces the off-axis target
from a clean stick, an octagon-gate *bypass*, not extra speed).

**The one escape (untested):** the ceiling is specific to a *standstill*. If `travel` were already
off-axis vs `facing` at the start (entering from prior motion / a turn), the setup frame could be
both clean (+5.0) *and* SIDE-bucketed → `speedF = 17` at frame 5 → a **26 roll at frame 6**. Needs a
realistic non-rest seed to confirm.

## See also

- [land-movement.md](../mechanics/land-movement.md) — the ATN_MOVE tier, roll mechanics, and the
  `Values` table (ATN_SPD, F14, ATNB_COS_FWD, ATN_MAX, roll `clamp`).
- [turnaround.md](../mechanics/turnaround.md) — the analogous instant-snap threshold (charge/swim).
