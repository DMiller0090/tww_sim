# Walk stab (sword thrust out of a walk): the no-roll seam clip

**Answers:** What is the walk stab, and how does it differ from the [roll stab](roll-stab.md)? How far
does its lunge reach, and which seams can it clip without a roll? Why is the thrust delayed several
frames when Link is holding an item? How does the one-frame L-target speed it up?
**Status:** decomp-grounded + live-observed (kaze r11, savestate anchor `kaze_r11_walkstab@twwgz.sav`,
2026-07-13). The min-clip geometry is computed, the equip-change delay is live-measured, and the
from-rest sim is bit-exact in FACING (the razor-critical quantity) under a C-down camera pin (see
Simulation). The one-shot dust-solver + DTM-validated clip are PENDING.
**Source:** decomp `d_a_player_main.cpp:4087` (`checkNextActionFromButton`), `:3946`/`:3959`
(equip-anime completion), `:3436`/`:3499` (the take/rest anime setup), `d_a_player_sword.inc:404`
(`changeCutProc`); HIO `daPy_HIO_item` (`d_a_player_HIO_data.inc:293`); live captures + the
seam-clip scanner (`harness/collision`). Constants:
[reference/constants.md#land-sword-cut-roll-stab](../reference/constants.md#land-sword-cut-roll-stab).

---

The walk stab is the [roll stab](roll-stab.md) without the roll: run up to walking speed, then thrust
(forward stick + B) so the CUT_F fires out of a MOVE instead of a FRONT_ROLL. The single-frame lunge is
the same shape, only the carried speed differs.

## The lunge (same CUT_F, lower carried speed)

The cut's first-frame displacement is `speedF (carried in) + the CUT_F joint-0 root translate 23.220`
(the [roll-stab](roll-stab.md#where-the-4922-comes-from-posmove-m34c2--1) `posMove m34C2==1` stack;
`procCutF_init` zeroes `m3700` so frame 1 gets the full 23.220). A roll carries speedF 26 (lunge
**49.22**); a capped walk carries speedF 17, so the walk-stab lunge tops out at **17 + 23.220 = 40.22**.
Any sub-cap walk gives a shorter, tunable lunge down to a standstill stab's 23.22.

## Which seams a walk stab can clip (the displacement floor)

A convex-corner seam clip needs Link's settled `old` to sit `WALL_R / sin(interior/2)` in front of the
tip (the r=35 wall cylinder cannot settle closer), so the minimum one-frame displacement is a hard
geometric floor (`harness/collision/gap_search`, `seam_scan.disp_floor`):

    min_disp = 35 / sin(interior/2)      interior = 180 - acos(nA . nB)   (the two wall normals)

**Shallower (flatter) corners have a LOWER floor** (the cylinder tucks closer to a near-flat tip), so:

| corner interior | floor | reachable by |
|-----------------|-------|--------------|
| >= ~121 deg     | <= 40.22 | **WALK stab** (no roll) |
| ~91 - 121 deg   | 40.22 - 49.22 | [roll stab](roll-stab.md) |
| < ~91 deg       | > 49.22 | neither bare lunge; needs an [actor push](actor-push.md) |

Data points: the Tetra corner (interior 90.57 deg) needs a push; the kaze roll-stab seam (~110 deg)
needs the roll; a near-flat seam is walk-clippable. This is a NECESSARY floor (the exact clip also needs
the f32 acceptance dust and the `old` band, so a real seam can want a hair more), but it is the governing
lever for "roll or not."

**Worked case (kaze r11, the walkstab anchor).** The wall chain Link faces has a convex seam at
`S=(9030.955, 1385.858)` (poly 803 x 802, interior **168.97 deg**, near-flat). Exact minimum clip
displacement = **35.02 u** (f32-lattice `gap_search.min_f32_clip`, at Link's facing and the bisector
alike; floor 35.16 confirms it), so **min speedF ~= 11.8** (35.02 - 23.22), well under the 17 cap: it
clips from a plain walk, no roll, no aim change. The acceptance here is DENSE (hundreds of clipping f32
`new` in a small box), not the kaze roll-stab razor dust. All three seams in this chain clip near 35 u.

## The item put-away delay (why the thrust comes out later)

When Link holds a non-sword item (here the Wind Waker), the thrust is delayed because the game must
change the equip to the sword first. On the sword press `checkNextActionFromButton`
(`d_a_player_main.cpp:4087`) does NOT cut while `checkEquipAnime()` is true (`:4194`); the stow/draw
upper-body anime runs first (the WW stows via `LKANM_BCK_TAKEL`, `setAnimeUnequipItem` `:3499`), and only
when its frame ctrl passes the completion frame (`:3959`; single-item `mItem.field_0x20 = 4.0`, sword
`REST` 7.0) does the game run `deleteEquipItem` + `setSwordModel` and set `daPyRFlg0_UNK80`, so the NEXT
frame's `checkNextActionFromButton` fires the buffered `changeCutProc()` -> CUT_F. The delay is
**item-independent** (it is the stow-then-draw, common to every item).

**Live-measured delay = 4 frames**, constant (B edge at fN -> CUT_F at fN+4; verified at two press
frames). Crucially the equip anime is UPPER-body only, so **the lower body keeps walking through the
delay** (proc stays MOVE, speedF holds/builds). So the B-press TIMING sets where `old` lands: the cut
fires 4 walk-frames later at the then-current speedF. If Link reaches the wall before the cut, CrrPos
bleeds his speed, so the press must be timed to fire the cut at the target `old` before wall decel.

## The one-frame L-target (faster accel) and the camera

A one-frame **L-target on frame 1** enters ATN_MOVE for that frame, injecting speedF at the side-branch
`ATN_SPD = 5.0` instead of the walk's `F14 = 3.5` (a permanent ~+5.7 position lead; full mechanism in
[roll-launch.md](../strategy/roll-launch.md#why-l-on-frame-1-the-57)). It reaches the needed speedF
sooner, shortening the run-up. **Hold C-down (`substickY = 0`) on that L frame** to keep the camera in
free-cam so the auto-cam does not swing (a swinging `csangle` rotates the stick->world mapping and drifts
Link's facing, observed ~33 u16/frame while walking; free-cam pins it).

## Simulation

**Driver + from-rest seed done; the razor is perpendicular; the dust-solver + DTM are pending**
(`harness/rollstab/walkstab.py`). The driver is just walk-N-frames-then-`enter_cut(CUT_F)` from the
from-rest seed (`rest.rest_state`): the 4-frame equip delay is **delivery-only** (the lower body keeps
walking, so the sim walks then cuts and the DTM presses B at frame N-4).

**The acceptance is a perpendicular RAZOR, not a forgiving band.** `harness/collision/gap_search`
gives, for this seam: perp offset window (`rho`, the cut ray's distance to `S`) **~6e-4u** (sub-ULP at
coord 9031, so f32-striped dust like the [roll stab](../strategy/seam-clip-solver.md)), but a WIDE aim
window (**+-40 deg**) and displacement window (**35.5-40**). So the razor is only the perpendicular
offset; the thrust direction and speed are forgiving. Optimal thrust facing is the corner bisector
(~3537); the walk-up to reach `old` is a different bearing, so walk and cut decouple (a turn).

**A pure-sim one-shot is feasible, but delivery MUST pin the camera with C-down.** Stepped with C-down
(`substickY=0`), the from-rest sim is **bit-exact in facing every frame** (a centered stick lets the
auto-cam swing and drift facing -- the camera issue above). The only residual is the walk-entry foot
toe-stream (`m359C`/`f312`, the open Phase-R gap): a constant ~0.0024u error, but a *speedF-magnitude*
error, so it lies ALONG the travel -- its perpendicular component is ~3.7e-5u, 16x inside the razor. So
`rho` is preserved and the along error is absorbed by the wide disp window + B-timing; the foot residual
does NOT need closing for the clip. Live-gated: `tests/test_walkstab_rest.py`.

Open: port the [roll-stab dust solver](../strategy/seam-clip-solver.md)'s knobs (a 1-frame arc threads
`rho`; start-crawl densifies the along placement) to land a genuine clip in < 2 min, then DTM-validate
(clean DTM, C-down held, never advancewith).

## See also

- [roll-stab.md](roll-stab.md) (the same CUT_F lunge fired out of a roll; 49.22 vs 40.22) ·
  [seam-clip.md](seam-clip.md) (why the corner clips, the f32 dust) ·
  [actor-push.md](actor-push.md) (the push tier for sub-91-deg corners).
- [roll-launch.md](../strategy/roll-launch.md) (the L-target ATN_MOVE boost) ·
  [land-movement.md](land-movement.md) (the walk/MOVE baseline).
