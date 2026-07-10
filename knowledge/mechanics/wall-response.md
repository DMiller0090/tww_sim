# Player wall response (the per-frame CrrPos wall pass)

**Answers:** What does the game do, each frame, when Link's body meets a wall? Where in the frame
does the correction run, what state does it leave for the procs, and how does the sim reproduce it
0-ULP? Why does A against a wall not roll? When does a roll bonk vs grind?
**Status:** LIVE-GATED 0-ULP (2026-07-10): four clean-DTM gates on a minted kaze r11 anchor
(head-on hold, oblique slide, roll bonk/crash, slow-roll grind) all per-frame bit-exact.
Regression: `tests/test_rollstab_walls.py` (live goldens) + `tests/test_land_walls.py` (mechanics).
**Source:** decomp `d_a_player_main.cpp` (execute 11407-11411, setBgCheckParam 10680,
setNormalSpeedF 2311, procFrontRoll 6838/6869, procFrontRollCrash 6891, setFrontWallType 4552),
`d_bg_s_acch.cpp` (CrrPos 209, LineCheck 175), `d_bg_w.cpp` (RwgWallCorrect 43); session-11
handoff. Constants: [reference/constants.md#land-movement](../reference/constants.md#land-movement).

## Where the wall pass sits in the frame

Player execute order: procs run, then `posMove()` integrates `current.pos += speed`, then
**`mAcch.CrrPos`** (the collision pass), then water/ground bookkeeping, and `setWorldMatrix`
draws at the END of the frame. So the wall response sees the POST-integration position, and the
drawn pose is at the POST-correction position. Inside `CrrPos` the wall part is: conditional
**LineCheck** (swept centre line), then **WallCorrect** (static cylinder push-out), then a
re-LineCheck if a wall corrected, then roof, then **GroundCheck** (snaps y up, zeroes `speed.y`).

Two details that took live diffing to get right:

- **The player line-checks EVERY frame.** The `LINE_CHECK` flag is on for all non-HANG procs, so
  the "only when displacement > radius" shortcut is wrong for Link.
- **WallCorrect sees the mid-frame gravity dip.** `posMoveFromFootPos` adds gravity (-2.5) to the
  snap-zeroed `speed.y` and integrates it BEFORE CrrPos; the ground snap comes after. The slice
  height per cylinder is `sp7C = GetWallAddY + (pos.y + wallH) - speed.y` with the dipped
  `pos.y`: deterministic, but not algebraically `ground + wallH` in f32. `GetWallAddY` (the
  previous ground plane's slope lift) is exactly 0 on a flat floor.

Link's wall body = three cylinders at heights {30.1, 89.9, 125.0}, radius 35 (normal ground
state; crawl/swim/hang differ, see `setBgCheckParam`). On a LineCheck wall hit the game snaps to
the crossing, **adds one full unit of the plane normal**, latches `SetWallHDirect(pos.y)` (which
replaces that cylinder's `sp7C`), then subtracts the cylinder height. The `sqrtf` throughout is
the console's MSL frsqrte + 3 double Newton iterations, not a correctly-rounded sqrt.

## The wall-hit state the procs read (one frame late)

CrrPos leaves `mAcch.ChkWallHit()` (aggregate), per-cylinder `mAcchCir[i].ChkWallHit()`, and
`SetWallAngleY(cM_atan2s(n.x, n.z))`. Procs run before the frame's CrrPos, so they see the
PREVIOUS frame's flags. Consumers:

- **Wall-hold** (`setNormalSpeedF` 2311): heading into a hit wall (`|travel+0x8000 -
  wallAngleY| < 0x4000`) scales the target speed by `1 - cos(diff)*0.6`. A head-on walk holds at
  0.4x target while the cylinder pins the position at the 35u tangent.
- **Roll bonk** (`procFrontRoll` 6869): crash fires iff speedF >= 10, the roll did NOT start
  against the wall (the `m3570` init latch, same head-on test), cir0 hit, head-on within 5000,
  and the ROLLF anim frame is in [6, 15]. `procFrontRollCrash`: `nspeed = speedF*0.4` with travel
  reversed, `speed.y = 7` (airborne bounce), ROLLFMIS frozen at frame 6 until the landing, then
  played at 0.7/frame to 24. **A roll that misses any window grinds instead**: it coasts pinned
  against the face for its full length (a sub-10-speed roll, or an off-angle > 5000 hit like the
  seam-corner rolls).
- **Sidle preempts the roll**: A while wall-hit with facing within 0x2000 of head-on (and a
  25+radius facing ray hitting a steep `|n_y| <= 0.05` wall) sets `mFrontWallType = 2`, doStatus
  SIDLE, `procWHideReady`. The ATTACK/roll dispatch never runs. You cannot roll from against a
  wall; back off or face > 45 deg away first.

## The sim (Phase W)

`LandState(walls=[Tri...])` opts in (`land/walls.py`); wall-free behavior stays byte-identical.
The pass runs `core.collision.acch_crr_pos` (the exact acch layer: every-frame LineCheck with the
full response, WallHDirect, console `sqrtf_c`, exact `cM3d_IsZero` 2^-18) right after position
integration, then stores the wall-hit state on the LandState for the next frame's procs. The
crash proc is fully modeled (positions are pure momentum, exact without ROLLFMIS keyframes). The
sidle is NOT: the sim just forbids the roll and latches the sticky `sidle_blocked` flag, and a
bonk shows up as `FRONT_ROLL_CRASH` in `state`/`visited`. **Planners must reject either.**

Scope/caveats (the open edges, in priority order):

- **Corner ordering**: corrections mutate the position sequentially, so when two NON-coplanar
  walls engage in one frame the poly ORDER matters. The game's order is its block/octree
  traversal; the sim takes the caller's list order. Single-face interactions (all four gates)
  are order-free. Needed for the seam-corner and Tetra work.
- **Mesh coverage**: the sim only knows the tris it is given (kaze fixture = the corner + faceB).
  A full-room mesh in the game's traversal order is the roadmap item.
- **Not wall-passed yet**: the ballistic hops and the C-up freeze's early-return frames.
- **Post-crash walking** consumes an unwarmed ROLLFMIS toe stream (the anim dump lacks
  `rollfmis`). Same flagged class as the late-roll drawn poses.
- **Mid-run stop then re-walk** (found by the grind gate's first design): a full stop to WAIT
  and re-entry into MOVE is NOT bit-exact yet. The one-frame WAIT matched; the re-walk entry
  speedF diverged. Unrelated to walls: a from-rest anchor entry is exact, a mid-run re-entry is
  not. Avoid full stops in plans until modeled.

## See also

- [collision.md](collision.md) - the collision system + geometry readers this builds on.
- [seam-clip.md](seam-clip.md) - the CrrPos FP port + why razor seams thread it.
- [roll.md](roll.md) · [land-movement.md](land-movement.md) - the procs the wall state feeds.
- `harness/rollstab/wallgate.py` - the four live gates (mint / plan / run / verify / golden).
