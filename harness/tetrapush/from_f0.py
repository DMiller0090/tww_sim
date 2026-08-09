"""The Courtyard from-f0 (and roll-entry) COUPLED replay -- the full-depth CC coupling wired together.

This is the last piece before the planner: seed a closed-loop `LandState` (Link) + a tracked Tetra
point at state 2 (or a roll entry), drive Link with the REAL DTM controller bytes, and apply the
CONSOLE CC push each frame (`cc_push_pair` = `cc_push.co_move_pair` = `dCcS::SetPosCorrect`):

  * Link recoils obj1's half of the overlap AWAY from Tetra (his own slowdown),
  * Tetra is shoved obj2's half AWAY from Link (the herd) -- the EXACT opposite of Link's recoil,

both the decomp 50/50 rank split (Link weight 120 / Tetra-v5 0x8C, both rank 5) computed from Link's
ANIMATED mCyl Co EXEC centre. This is 0-ULP vs the deterministic per-op ΔTetra (f2..f43, session 27),
superseding the session-8/9 DERIVED full-depth-from-SETTLED laws (`tetra_plow.plow_step` /
`link_plow.recoil`, ~1e-5 u off -- the retired laws, see `tetra_plow`). Tetra is stt-3 the WHOLE
Courtyard window (pure plow, speedF 0 -- see the cyl-fixture timeline), so she is a bare XZ point
moved by the push; there is no follow leg to model here.

This is the COURTYARD-SPECIFIC full-depth coupling. It does NOT touch the general FOLLOWING-Tetra
sandbox (`harness/rollstab/cc_stepper` + `core/cc_push.co_move_pair`, a gated 50/50) -- that stays the
default for the sandbox.

Two modelling shortcuts, both deliberate (see README "## Plan / status" from-f0 box):
  * Link's mCyl Co centre is INJECTED per frame from the live capture (`courtyard_push_cyl.json`
    `link.cyl`) rather than modelled offline -- the MOVE-phase `daPy_lk_c::setCollision` centre is not
    yet ported (`body_cyl.roll_co_center` only covers rolls). A future `move_co_center` replaces the
    injection; the coupling code here is unchanged by that swap.
  * `csangle` is INJECTED per frame (`_cam.yaw` forced, C-stick neutral) rather than integrated from
    the substick -- the "inject the camera, don't model it" convention (the frozen-cam shortcut the
    tier test uses, generalised to the captured per-frame value). SUPERSEDED when a `camera=` is
    passed (session 18): a seeded `core.camera.land_cam.LandCamera` replaces the injection, driven
    by the raw DTM substick + the sim's own Link/attention state (see the `FreeRun` class doc).
    Session 20 closed the LAST injected streams: a seeded `core.npc_zl1_look.Zl1Look` (`zl1=`)
    replaces the Tetra eyePos/tattn injections with the modeled look-at head -- with `camera=` +
    `zl1=` the replay consumes ONLY the static f0 seeds + the raw DTM bytes.

VALIDATED (`tests/test_from_f0.py`), seeded at the FIRST roll entry: the replay now CHAINS bit-exact
through cycle 2's roll -- f4..f44 is 0-ULP (every speedF, every proc, Link pos <1.4e-4 u), covering
cycle 1 (roll + the 2-frame ATN_ACTOR untarget tier -25.727/-25.452 + backslide), the whole
backslide->roll-setup re-target (proc-7 entry f26, the +18 flip f28, cyc2 roll f29), and cycle 2's
roll. Tetra is 0-ULP over the whole window. The gated range stops at f44, before the cyl fixture's
single-step-jittered cyc2 untarget (f45+, session-8 known corruption).

Runs at `input_delay=1` (see `_seed_link`): the DTM stream IS the polled `g_mDoCPd` pad, already one
pipeline stage into the raw-controller latency `LandState` models from (shipped default 2, for the live
walk goldens) -- so a DTM replay is delay-1 (live-probed s11: `m34E8`/roll-A/soft-L all land 1 frame
after the DTM). This is what makes the +18 re-target flip land on the right frame.

The TRUE f0 seed (state 2) is CLOSED (session 12): seeded at f0 with the measured mNormalSpeed
(`seed_nspeed`, from `fixtures/courtyard_push_seed.json`), f1..f44 is bit-exact (every speedF 0-ULP,
Link pos within capture precision). The gap was NOT mDirection or an attention residual (both match the
sim defaults at f0 -- live mDir DIR_NONE, no lock); it was that at f0 speedF LAGS mNormalSpeed a frame
(speedF -24.574, mNormalSpeed -24.982) and the replay seeded `nspeed = speedF`. Seeding nspeed from the
live mNormalSpeed is the whole fix; f1's speedF simply catches up to the already-set nspeed.

Pure-sim / no calibration: the replay takes only the seed + the DTM bytes + the injected centre/csangle
(all from the locked capture); the diff against the capture is the out-of-band gate, never in a loop.
Pure stdlib, no Dolphin."""
import math
import struct
import warnings

from tww_sim.core.camera.land_cam import pad_from_raw
from tww_sim.core.collision import acch_crr_pos
from tww_sim.core.fp import f32, fadds
from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST
from tww_sim.core.npc_zl1 import WALL_H as TETRA_WALL_H, WALL_R as TETRA_WALL_R
from tww_sim.core.cc_push import co_move_pair, WEIGHT_LINK, WEIGHT_TETRA_V5
from tww_sim.land.attention import LOCK as _ATN_LOCK, RELEASE as _ATN_RELEASE
from tww_sim.land.land import LandState, FRONT_ROLL, MOVE
from harness.tetrapush.link_plow import recoil
from harness.tetrapush.tetra_plow import LINK_CO_R, TETRA_CO_R, _CO_H


# One-shot guard (list-boxed so `_build_core` flips it): native consts must be armed before the
# first `step_courtyard` or the s16 `diff/scale` SIGFPEs (PROGRESS.md Stage-1 trap 2).
_NATIVE_CONSTS_ARMED = [False]


def _arm_look_consts(N):
    """Hand the C look pair its tuning values FROM the Python models (session 128).

    Every number the native `Zl1Look`/`NeckLook` port uses is read out of `core.npc_zl1_look` /
    `land.neck_look` here rather than re-declared in the .pxi -- one canonical value per constant
    (`knowledge/reference/constants.md`), and a change to a Python model cannot leave a stale copy
    compiled into C behind it."""
    from tww_sim.core import npc_zl1_look as Z
    from tww_sim.land import neck_look as NL
    N.init_zl1_consts(Z.CHAIN, Z.Zl1JntCtrl._MAX, Z.Zl1JntCtrl._MIN,
                      Z.TURN_STEP_POS, Z.TURN_STEP_NEG, Z.JNT_CHASE, Z.EYE_OFF,
                      Z.ATTN_Y_OFF, Z.PLAYER_EYE_Y_OFF, Z.ANM_MORF, Z.ANM_SPEED,
                      Z.ANM_WAIT03, Z.ANM_LOOK, Z.RND_FLOOR)
    N.init_neck_consts(NL._FLG80_PROCS, NL._FLG8M_PROCS, NL.LOOK_CONE_HALF, NL.CHASE,
                       NL.PITCH_MAX, NL.PITCH_MIN, NL.YAW_CLAMP,
                       NL.EYE_OFFSET, NL.HEAD_CENTER_OFFSET)


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _yaw_from_csangle(csangle):
    """The `dCamera_c` yaw for a captured `csangle` (== `(yaw + 0x8000) & 0xFFFF`), so forcing
    `_cam.yaw` with a neutral C-stick holds `csangle` frozen at the injected value that frame."""
    return (int(csangle) - 0x8000) & 0xFFFF


def cc_push_pair(exec_center, tetra_xz):
    """THE console CC push for one Courtyard frame (bug-#1 fix, session 27), from Link's
    EXECUTE-pass Co centre ``exec_center`` (x, z or x, y, z) and Tetra's feet ``tetra_xz``.

    This is the decomp-faithful push -- `cc_push.co_move_pair` == `dCcS::SetPosCorrect`: ONE fused
    dist, the plain 50/50 rank split (Link weight 120 / Tetra-v5 0x8C, both rank 5), obj1/obj2 moved
    EXACT-opposite by ``0.5 * cross_len`` along the centre-to-centre line. Returns ``((link_dx,
    link_dz), (tetra_dx, tetra_dz))`` -- Link's recoil (obj1, AWAY from Tetra) and Tetra's push
    (obj2, AWAY from Link), both the HALF-depth split of the overlap.

    It supersedes `full_depth_push` (full-depth from the SETTLED centre) as the push law: the two
    agree only to ~1e-5 u, and ONLY the exec-centre half-depth split is 0-ULP vs the console --
    `co_move_pair(cyl_exec)` reproduces the deterministic per-op ΔTetra (`courtyard_push_perop.json`)
    BIT-FOR-BIT on f2..f43 (verified session 27), where `full_depth_push(settled)` (fused or not)
    is 1-9 ULP off. The settled-centre `full_depth_push` remains ONLY the SEED-frame (f0->f1)
    fallback, since f0's exec centre is not offline-reconstructable (the seed doesn't carry f-1's
    lean/morf residue -- see `_seed_pose_f0` and README `## Plan / status`)."""
    ex, ez = float(exec_center[0]), float(exec_center[-1])
    tx, tz = float(tetra_xz[0]), float(tetra_xz[-1])
    (l1, _l2, l3), (v1, _v2, v3) = co_move_pair(
        (ex, 0.0, ez), LINK_CO_R, _CO_H, (tx, 0.0, tz), TETRA_CO_R, _CO_H,
        WEIGHT_LINK, WEIGHT_TETRA_V5)
    return (float(l1), float(l3)), (float(v1), float(v3))


def full_depth_push(link_center, tetra_xz):
    """The SEED-frame (f0->f1) fallback push from the SETTLED centre: returns ``((link_dx, link_dz),
    (tetra_dx, tetra_dz))`` -- Link's recoil (`link_plow.recoil`, the full Co-overlap depth AWAY from
    Tetra) and Tetra's push (the full depth AWAY from Link), computed from Link's SETTLED Co centre
    ``link_center`` (x, z or x, y, z) and Tetra's feet ``tetra_xz``.

    The two are EXACT bit-for-bit opposites (Newton's third law: a single same-rank Co pair ejects
    equal-and-opposite -- `cc_push.co_move_pair`'s vec1/vec2 sum to 0). Tetra's push is ``-recoil``
    (an exact f32 sign flip of the same delta), NOT the old ``tetra_plow.plow_step`` new-minus-old
    form (session-24 bug-#1 self-consistency violation).

    This is the full-depth-from-SETTLED-centre framing -- numerically the exec-centre half-depth to
    only ~1e-5 u, so it is NOT 0-ULP vs the console (`cc_push_pair` on the exec centre is). It
    survives ONLY as the seed-frame (f0->f1) push: f0's exec centre needs f-1's lean/morf, which the
    seed frame doesn't carry, so the settled centre is the best offline datum for that one frame."""
    rlx, rlz = recoil(link_center, tetra_xz)
    return (float(rlx), float(rlz)), (float(-rlx), float(-rlz))


def _seed_pose_f0(link, anim_frame, m351c, old_pose=None):
    """Seed the f0 DRAWN-POSE state for the computed-centre mode (state 2 is a full-speed MOVE
    backslide, so the under-body blend is the regime-3 DASH cruise -- the whole hidden anim state is
    the one frame-ctrl phase the capture logs as ``link.anim``, plus the turn lean ``m351C``).

    Enables ``body_co`` on the foot FK (poses the neck-chain extras from here on), sets the
    UnderAnimState to the dash cruise at the captured phase (ratio 1, m3598 0, rate 2.3 -- the
    regime-3 `_set_move_anime` output), and warms the stored old pose + toe stream with the last two
    drawn rest-of-cycle poses (pure dash at phase-2.3 and phase: f0-1/f0 were both regime-3 MOVE
    frames, no morf active -- the prior cycle's ATN->MOVE morf decayed frames earlier). The stored
    pose is LOCAL (position-independent), so the warmup base does not matter; the toe stream only
    feeds speedF where m3598 != 0, which never happens in the courtyard window. Python foot path
    only (the MOVE seed is already foot_native=False)."""
    from tww_sim.core.anim.anim_state import ANIM_META, EMode_LOOP
    fsf = link._foot                     # FootSpeedF
    fsf.ff.body_co = True
    st = fsf.st
    ph = float(anim_frame)
    dash = st._dash                      # 'dashs' (SWORD_DRAWN -- the mSwordAnmIndexTable swap)
    end = float(ANIM_META[dash][0])
    st.move0 = st.move1 = dash
    st.m34C3 = 1
    st.ratio = 1.0
    st.m3598 = 0.0
    st.fc0.set(EMode_LOOP, 0, end, 2.3, ph)
    st.fc1.set(EMode_LOOP, 0, end, 2.3, ph)
    ph_prev = ph - 2.3
    if ph_prev < 0.0:
        ph_prev += end
    fsf.ff.set_pos(link.pos_x, link.pos_z, py=link.pos_y, facing=link.facing)
    fsf.t2 = fsf.ff.step_feet(dash, dash, ph_prev, ph_prev, 1.0, -1.0)
    fsf.t1 = fsf.ff.step_feet(dash, dash, ph, ph, 1.0, -1.0)
    if old_pose is not None:
        # Overwrite the store with the CAPTURED live m_old_fdata (`courtyard_push_seed.json`
        # `old_pose`; RAM quat order x,y,z,w -> sim (w,x,y,z)) + seed the morf counters.
        for j, jj in enumerate(old_pose['joints']):
            q = jj['quat']
            fsf.ff.old_quat[j] = (q[3], q[0], q[1], q[2])
            fsf.ff.old_trans[j] = tuple(jj['trans'])
            fsf.ff.old_scale[j] = tuple(jj['scale'])
        ms = fsf.ff.morf
        ms.counter = old_pose['counter']
        ms.f8 = old_pose['f8']
        ms.rate = old_pose['rate']
        ms.f10 = old_pose['f10']
        ms.f14 = old_pose['f14']
    link.m351C = int(m351c) & 0xFFFF
    link._draw_lean = _s16(link.m351C) >> 1


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _computed_center(link, init_frame=False):
    """Link's body Co centre AS setCollision WRITES it (the execute-pass value): the root/neck
    midpoint rebuilt from the sim's own pose at the post-posMove position of the frame just stepped.
    Live-pinned session 14 (`_notes/tetrapush-setcol_probe.py`, JP setCollision 0x8011a670 bp): the
    breakpoint-read nodeMtx midpoint == the freshly written mCyl to <=6.1e-5 u every frame (proc-7,
    roll entry, all roll bodies), at pos == the pause-boundary pos (posMove has run; the CC pass has
    not). This is NOT yet the value the plow laws consume -- see `_cc_settled_center`.

    The BODY_CHN counter-twist uses this frame's POST-update lean (`m351C >> 1` after
    `_set_move_slant_angle`, == the execute-pass `mBodyAngle.z` at calc time), while the base keeps
    the draw lean -- the session-16 timing law (see `FootFK.body_co_center`).

    ``init_frame`` -- True when this frame DISPATCHED a proc ``*_init`` (its dispatch proc differs
    from the previous frame's). ``commonProcInit`` zeroes ``shape_angle.z`` (d_a_player_main.cpp
    :5841) BEFORE ``setWorldMatrix`` builds the base, and ``setMoveSlantAngle`` only restores it
    (from the untouched ``m351C``) after -- so the exec base has NO lean on proc-entry frames
    (live-pinned session 16: the f1/f3 base matrices read row0[1] == 0.0 while f2's carries the
    old lean; the residual was exactly sin(lean_old) x the root height)."""
    cx, cz = link._foot.ff.body_co_center(link.pos_x, link.pos_y, link.pos_z,
                                          link.facing, 0 if init_frame else link._draw_lean,
                                          body_lean=_s16(link.m351C) >> 1)
    return (float(cx), float(cz))


def _computed_head_mtx(link, init_frame=False, neck=None):
    """The exec-pass WORLD head anm matrix (`FootFK.head_mtx`) -- identical base/lean conventions
    to `_computed_center` (new-lean BODY_CHN twist, proc-init zero base lean). ``neck`` = the
    jointBeforeCB head twist ``local_38`` (`NeckLook.local_38()`), None = untwisted. The cached
    previous-frame value of THIS matrix is what the next frame's setNeckAngle measures (:11571
    runs before that frame's calc, so it reads the LAST calc's head matrix)."""
    return link._foot.ff.head_mtx(link.pos_x, link.pos_y, link.pos_z,
                                  link.facing, 0 if init_frame else link._draw_lean,
                                  body_lean=_s16(link.m351C) >> 1, neck=neck)


def _computed_head_top(link, init_frame=False, neck=None):
    """Link's ``mHeadTopPos`` AS the exec pass writes it (d_a_player_main.cpp:11592, right after
    the SAME ``mpCLModel->calc()`` setCollision reads) -- identical base/lean conventions to
    `_computed_center` (new-lean BODY_CHN twist, proc-init zero base lean). The Y is what Tetra's
    look-at consumes as ``dNpc_playerEyePos``; x/z are overwritten with Link's current.pos.
    ``neck`` = the head-look twist (`NeckLook.local_38()`); the <=0.96 u tier-frame Y shift."""
    return link._foot.ff.head_top(link.pos_x, link.pos_y, link.pos_z,
                                  link.facing, 0 if init_frame else link._draw_lean,
                                  body_lean=_s16(link.m351C) >> 1, neck=neck)


def _cc_settled_center(exec_center, tetra_xz):
    """The pause-boundary mCyl -- the value the gated plow laws consume (`courtyard_push_cyl.json`
    `link.cyl`): the scene CC pass's IMMEDIATE SetPosCorrect write moves Link's registered Co
    cylinder by HALF the overlap depth away from Tetra (the decomp 50/50 rank split, watchpoint-
    caught session 14 at lp+0x4064, writer LR 0x800ab5d0 in dCcS).

    Live-derived (probe frames f1..f12): ``fix(k) - exec(k) == 0.5 * depth(exec(k), tetra(k)) *
    unit(exec(k) - tetra(k))`` exactly, which also equals ``recoil(fix(k), tetra(k))`` -- the "full
    depth from the settled centre" framing the gated laws use. (This closes the session-9 "2x
    doubling" sub-puzzle: both actors take the plain 0.5*cross_len split of the EXEC-centre overlap;
    measured against the SETTLED centre it reads as the full depth.) It is a diagnostic/reporting
    value (`sim_cyl`) -- the push itself is `cc_push_pair` on the exec centre, not this."""
    from harness.tetrapush.tetra_plow import plow_depth
    from tww_sim.core.collision import is_zero, fsqrt
    from tww_sim.core.fp import f32, fsubs, fadds, fmuls, fdivs
    lx, lz = f32(exec_center[0]), f32(exec_center[-1])
    tx, tz = f32(tetra_xz[0]), f32(tetra_xz[-1])
    depth = plow_depth((lx, lz), (tx, tz))
    if depth <= 0.0:
        return float(lx), float(lz)
    dx = fsubs(lx, tx)                          # away from Tetra
    dz = fsubs(lz, tz)
    dist = fsqrt(fadds(fmuls(dx, dx), fmuls(dz, dz)))
    if is_zero(dist):
        return float(lx), float(lz)
    f = fdivs(fmuls(f32(depth), f32(0.5)), dist)
    return float(fadds(lx, fmuls(dx, f))), float(fadds(lz, fmuls(dz, f)))


# `mEquipItem` is 0x103 (SWORD) the whole window, so the walk/dash anims are WALKS/DASHS -- a
# feet-only swap, hence position wherever m3598 != 0. knowledge/model/equipped-anim-set.md.
SWORD_DRAWN = True

# Link is on his last hearts, so the WAIT stop plays the ANM_WAITATOB single (measured live at plan
# frame 76: anm idx 285, ctrl 12/0.6/0.0). knowledge/model/wait-stop-pose.md (the low-life arm).
LOW_LIFE = True


def _seed_link(row, csangle, seed_nspeed=None):
    """Seed a Python-path `LandState` from a captured frame ``row`` (``{proc, pos, facing, travel,
    speedF}`` under ``row['link']``). A roll entry is seeded FRONT_ROLL with speedF pinned at 26.0
    (constant-momentum roll -- the `couple_replay` convention, no foot-warming); any other proc is
    seeded at its live speedF with the foot stream warm (the backslide entered its proc mid-run, so
    `getOldFrameFlg` is already true).

    ``seed_nspeed`` (mNormalSpeed) seeds the potential speed SEPARATELY from ``speedF``. At the true f0
    seed (state 2) Link is mid-transition out of the prior cycle's untarget, where ``speedF`` LAGS
    ``mNormalSpeed`` a frame (speedF -24.574, mNormalSpeed -24.982); the fixture only logs ``speedF``,
    so ``nspeed = speedF`` left f1-f2 off by ~0.4/0.2. Pass the live-measured mNormalSpeed
    (`fixtures/courtyard_push_seed.json` `link.nspeed`, session 12) and the whole from-f0 chain is
    bit-exact. Omitted -> ``nspeed = speedF`` (correct wherever speedF has already settled to nspeed --
    every roll-entry seed and any steady-state frame)."""
    ll = row['link']
    proc = row['proc']
    # input_delay=1: the DTM stream IS the polled `g_mDoCPd` pad, one pipeline stage into the sim's
    # raw-controller latency, so physics + attention both act on the delay-1 pad (see README roll-setup).
    if proc == FRONT_ROLL:
        link = LandState(pos_x=ll['pos'][0], pos_z=ll['pos'][2], pos_y=ll['pos'][1],
                         facing=ll['facing'], travel=ll['travel'], csangle=csangle,
                         state=FRONT_ROLL, nspeed=26.0, speedF=26.0,
                         use_anim=True, native=False, sword_drawn=SWORD_DRAWN, input_delay=1,
                         low_life=LOW_LIFE)
        link._roll_m3570 = False           # seeded mid-roll: live grinds (no bonk) -> m3570 False
    else:
        ns = ll['speedF'] if seed_nspeed is None else float(seed_nspeed)
        link = LandState(pos_x=ll['pos'][0], pos_z=ll['pos'][2], pos_y=ll['pos'][1],
                         facing=ll['facing'], travel=ll['travel'], csangle=csangle,
                         state=proc, nspeed=ns, speedF=ll['speedF'],
                         use_anim=True, native=False, foot_native=False, sword_drawn=SWORD_DRAWN,
                         input_delay=1, low_life=LOW_LIFE)
        link._foot.started = True
    # Draw at frame END from the post-posMove base -- 0 ULP vs the live toes where pre-integration is
    # 32-128 ULP off (`tests/test_foot_draw_base.py`). knowledge/model/draw-base.md.
    link._foot.defer_draw = True
    return link


class FreeRun:
    """The NOVEL-INPUT coupled stepper -- the from-f0 replay loop with no capture rows: seed once,
    then `step()` arbitrary raw controller inputs. This is the planner's forward model; `replay`
    (below) is a thin wrapper that drives it with the DTM bytes and diffs against the live capture,
    so every existing 0-ULP gate also gates this class.

    ``seed_row`` is a cyl-fixture-shaped f0 row (``{proc, csangle, link:{pos, facing, travel,
    speedF, anim, shape_z, cyl}, tetra:{pos}}``). ``computed_pose`` seeds the drawn-pose state and
    rebuilds the Co centre from the sim's own pose each frame (the self-contained mode; requires a
    non-roll f0 seed); False = the caller must inject a settled centre via ``step(center=)``.
    ``seed_push`` -- the exact f0->f1 Tetra CC push ``(dx, dz)`` (the deterministic perop ΔTetra,
    `seeds.seed_push_f0`); makes the seed frame 0-ULP (see the ``seed_push`` note in `__init__`).
    Omit for roll-entry seeds -> the settled-centre `full_depth_push` fallback.

    Per-frame injectables (until their models land): ``csangle`` -- the START-of-frame camera value
    (i.e. the value after the previous frame; omit to hold the last one), and ``eye`` -- the
    end-of-previous-frame Tetra eyePos (the proc-9 re-aim target; omit to keep the last set value,
    never-set = feet-aim).

    ``camera`` -- a SEEDED `LandCamera` (`land_cam.seed_from_block` off the f0 oracle block): the
    csangle injection is replaced by the modeled camera, stepped at the END of each frame from the
    sim's OWN post-step Link state (the game order: player execute -> camera Run; the physics of
    frame k+1 reads the csangle committed at frame k). The camera consumes the same delay-1 raw
    input the physics acts on (`pad_from_raw`; it needs the REAL substick bytes, which stay
    physics-neutral -- `_step_args` keeps feeding LandState a neutral C-stick), the sim's own
    attention lock for `LockonTruth()`, and Link's `attention_info.position` via the decomp law
    ``attn = (pos.x, f32(92.5 + baseTR[1][3]), pos.z)`` (`setAttentionPos`, d_a_player_main.cpp
    :10271, runs right after setCollision -- the sim's posed `ff.base` IS that base matrix).
    KNOWN SEED GAP: the sim does not run the `m35B8` footBgCheck decay (no ground bookkeeping in
    this replay), so at an f0 with live m35B8 residue (state 2: -5.198 dying by f3) the attn Y is
    up to ~2.7 u high for the first two frames -- a <0.15 u camera-CENTER-Y transient through the
    0.05 cushion, invisible to csangle (the yaw target moves ONLY with C-stick X, and the blip
    chase targets the camera's own committed yaw -- csangle is position-independent in this
    regime, which is exactly why it is a commanded input channel for the planner).
    While the sim's lock is engaged the camera needs the locked actor's attention position:
    inject it per step via ``tattn`` (Tetra's `attention_info.position`, her animated look-at
    point -- unmodeled, same status as eyePos; keep-last semantics like ``eye``).

    ``walls_tetra`` -- the ordered room mesh for TETRA's own ``mObjAcch.CrrPos`` (the R 50 /
    half-H 30 BG pass `npc_zl1` already models and `CcCoupledStepper(walls_tetra=)` already
    applies). None = the bare XZ plow point, which is faithful only while she is clear of the
    geometry: it is what drove her 53 u THROUGH the courtyard back wall on the clip roll, where
    the console braces her at the plane + her radius (session 86). Link's own wall pass is the
    plain `link._walls` attribute; set both to run the composite in one walled engine."""

    def __init__(self, seed_row, *, seed_nspeed=None, seed_old_pose=None, computed_pose=True,
                 camera=None, zl1=None, neck=None, seed_push=None, native_step=False,
                 walls_tetra=None, native_look=False):
        e = seed_row
        self.link = _seed_link(e, e['csangle'], seed_nspeed=seed_nspeed)
        self.computed_pose = bool(computed_pose)
        if self.computed_pose:
            if e['proc'] == FRONT_ROLL:
                raise ValueError("computed_pose needs the f0 (MOVE) seed -- a mid-roll seed has no "
                                 "pre-roll pose for the entry morf")
            _seed_pose_f0(self.link, e['link']['anim'],
                          (int(e['link']['shape_z']) << 1) & 0xFFFF, old_pose=seed_old_pose)
        self.tx, self.tz = e['tetra']['pos'][0], e['tetra']['pos'][2]
        self.ty = e['tetra']['pos'][1]
        self.walls_tetra = walls_tetra
        self.camera = camera
        # native-look mode moves BOTH look models into the C frame; the `_eye_next`/`_tattn`/`neck`
        # properties then read the core, so this must be set before either is touched.
        self._native_look = bool(native_look)
        # zl1 (a seeded Zl1Look) replaces the eye + tattn injections -- see the class doc.
        self.zl1 = zl1
        if zl1 is not None and not self.computed_pose:
            raise ValueError("zl1 mode needs computed_pose (mHeadTopPos comes from the posed FK)")
        self._eye_next = tuple(zl1.eye) if zl1 is not None else None
        # neck (a seeded `land.neck_look.NeckLook`): Link's head-look m3564; feeds only the posed
        # head matrix / mHeadTopPos. See knowledge/mechanics/link-head-look.md.
        self.neck = neck
        if neck is not None and not self.computed_pose:
            raise ValueError("neck mode needs computed_pose (m3564 measures the posed head matrix)")
        self._head_mtx = None
        if neck is not None:
            # The f0 exec head matrix (state 2 is a mid-proc MOVE cruise -- not an init frame),
            # twisted by the SEED m3564: what f1's setNeckAngle measures.
            self._head_mtx = _computed_head_mtx(self.link, neck=neck.local_38())
        self._tattn = None
        self._prev_raw = None
        self.csangle = camera.angleY if camera is not None else e['csangle']
        self._follow_warned = False
        # The f0->f1 SEED-frame push: the exact console ΔTetra (`seed_push`, 0-ULP by construction),
        # else the ~66-ULP settled-centre `full_depth_push` fallback. See README ## Plan / status.
        if seed_push is not None:
            self.pend_tetra = (float(seed_push[0]), float(seed_push[-1]))
            self.pend_link = (-self.pend_tetra[0], -self.pend_tetra[1])
        else:
            c0 = e['link']['cyl']
            self.pend_link, self.pend_tetra = full_depth_push(c0, (self.tx, self.tz))
        self.prev_disp = self.link.state               # dispatch proc of the seed frame

        # native-step mode (Stage 3): drive the frame in C (LandCore.step_courtyard, native_push=1);
        # `self.link` stays a field-holder synced from the core. See PROGRESS.md Stage 3.
        self.native_step = bool(native_step)
        self._core = None
        if self.native_step:
            if not self.computed_pose:
                raise ValueError("native_step needs computed_pose (the fused native pose FK)")
            if walls_tetra is not None:
                raise ValueError("native_step has no Tetra BG pass -- the C engine tracks her as a "
                                 "bare plow point; run the Python path for a walled Tetra")
            if self._native_look and (zl1 is None or neck is None):
                raise ValueError("native_look needs BOTH look models to seed from (zl1= and neck=)")
            self._core = self._build_core()
        elif self._native_look:
            raise ValueError("native_look is the C step running the look pair itself -- it needs "
                             "native_step=True")

    # --- live views on the C look state; `_live` is False while `_build_core` still seeds off these
    # same attributes. Why read rather than mirror: knowledge/model/porting-the-look-pair.md
    @property
    def _live(self):
        return self._native_look and self._core is not None

    @property
    def _eye_next(self):
        return self._core.look_eye if self._live else self.__eye

    @_eye_next.setter
    def _eye_next(self, v):
        self.__eye = v

    @property
    def _tattn(self):
        return self._core.look_tattn if self._live else self.__tattn

    @_tattn.setter
    def _tattn(self, v):
        self.__tattn = v

    @property
    def neck(self):
        """Link's `NeckLook`. In native-look mode this is the SEED object, refreshed from the core
        on access -- read `.x/.y/.z` freely; it is not what the frame steps."""
        n = self.__neck
        if self._live and n is not None:
            n.x, n.y, n.z = self._core.neck_snapshot()
        return n

    @neck.setter
    def neck(self, v):
        self.__neck = v

    def zl1_snapshot(self):
        """Her whole hidden look state. Native-look runs step the C copy, so `self.zl1` stays the
        SEED object (refreshing all of it every frame would cost more than the port saved) -- this is
        the live read, and what the 0-ULP gate diffs against the Python model."""
        if not self._native_look:
            raise ValueError("zl1_snapshot is the native-look read; this run steps `self.zl1`")
        return self._core.zl1_snapshot()

    def _build_core(self):
        """Build + seed the native `LandCore` for this seeded (f0) FreeRun -- the Stage-1 seeding
        bridge folded in: clone the fused C `PoseEngine`, `seed_from_foot` the Python FootSpeedF into
        it, `setup` the physics scalars, and `seed_courtyard` the coupled seeds (pos_y, lean, the
        AttentionLock state, Tetra's f0 feet, and the f0->f1 CC push pair). Idempotently arms the
        module consts (`land_init_consts`/`init_anim_consts`) -- required or the s16 divide SIGFPEs
        (PROGRESS.md trap 2)."""
        from tww_sim.core.anim import _anmc as N
        from tww_sim.core.anim.anim_state import (ANIM_ORDER, NATIVE_META_MAX,
                                                  NATIVE_META_ATTR, NATIVE_HIO)
        from tww_sim.land.state import _LAND_CONSTS
        if not _NATIVE_CONSTS_ARMED[0]:
            N.land_init_consts(_LAND_CONSTS)
            N.init_anim_consts(NATIVE_META_MAX, NATIVE_META_ATTR, NATIVE_HIO)
            _arm_look_consts(N)
            _NATIVE_CONSTS_ARMED[0] = True
        link = self.link
        code2idx = [link._foot.ff._anim_idx[name] for name in ANIM_ORDER]
        pe = link._foot.ff._pose_engine.clone_state()   # fresh engine sharing the immutable AnimData
        pe.seed_from_foot(link._foot, code2idx)
        core = N.LandCore()
        core.setup(pe, link.pos_x, link.pos_z, link.facing, link.travel, link.csangle,
                   link.state, link.nspeed, link.speedF, float(link._cam.scale))
        core.seed_courtyard(pe, link.pos_y, link.m351C, int(link._atn.state), self.tx, self.tz,
                            self.pend_link[0], self.pend_link[1],
                            self.pend_tetra[0], self.pend_tetra[1])
        core.low_life = link.low_life        # checkRestHPAnime's seeded half (wait-stop-pose.md)
        if self._native_look:
            # the look pair moves INTO the C frame here; `zl1`/`neck` are the SEED from now on and
            # the live state is the core's (knowledge/model/porting-the-look-pair.md)
            from tww_sim.core.npc_zl1_look import load as _zl1_load, CHAIN, ANM_NAME, ANM_WAIT03, ANM_LOOK
            anms, _sk = _zl1_load()
            data = N.zl1_anim_data(anms, CHAIN, ANM_NAME[ANM_WAIT03], ANM_NAME[ANM_LOOK])
            core.seed_look(data, self.zl1, self.neck, self._head_mtx, self.ty)
        return core

    def clone(self):
        """A deep copy for the planner beam search: branch the coupled state without re-running the
        rollout from state 2. `LandState.clone` shares the immutable `AnimData`; the camera / zl1 /
        neck each `clone()` (sharing their own immutable FK tables) -- so a clone is ~1 ms, not the
        ~60 ms a whole-object `deepcopy` costs (which copies every FK table). A cloned run stepped
        with the same inputs as its parent stays bit-identical (gated `tests/test_search.py`).

        Everything else is a scalar or an immutable tuple (pos points, pends, the cached head
        matrix, the raw-input dict which `step` never mutates) -- shared by reference is correct."""
        c = FreeRun.__new__(FreeRun)
        c.link = self.link.clone()
        c.computed_pose = self.computed_pose
        c.tx, c.tz, c.ty = self.tx, self.tz, self.ty
        c.walls_tetra = self.walls_tetra          # immutable mesh, shared by reference
        c.camera = self.camera.clone() if self.camera is not None else None
        c._native_look = self._native_look        # before any look property is read or written
        c.zl1 = self.zl1.clone() if self.zl1 is not None else None
        c._eye_next = self._eye_next
        c.neck = self.neck.clone() if self.neck is not None else None
        c._head_mtx = self._head_mtx
        c._tattn = self._tattn
        c._prev_raw = self._prev_raw
        c.csangle = self.csangle
        c._follow_warned = self._follow_warned
        c.pend_link = self.pend_link
        c.pend_tetra = self.pend_tetra
        c.prev_disp = self.prev_disp
        c.native_step = self.native_step
        # Native core: clone over a state-copy of its fused PoseEngine (shares the immutable AnimData);
        # a cloned run stays bit-identical (gated). Non-native runs carry _core = None.
        c._core = self._core.clone(self._core.pe.clone_state()) if self._core is not None else None
        return c

    def co_center(self, init_frame=False):
        """Link's exec-pass body-Co centre for the frame THIS RUN last stepped -- off whichever
        engine posed it (`_computed_center` wired, `LandCore.co_center_exec` native).

        Read it through here and never off ``run.link`` directly: on a native run that `LandState`
        is a field-holder whose `_foot` still carries the f0 SEED pose, so `_computed_center(run.link)`
        returns a centre for a frame the run left long ago -- silently, and only in the low digits
        of everything that consumes it.

        ``init_frame`` defaults to False on BOTH paths, which is what every run-level caller has
        always passed. On a frame that dispatched a proc ``*_init`` that is an approximation (the
        exec base carries no lean there, worth ~1.7 u at the seed frame) and the native engine knows
        the true flag -- but correcting it would move search-visible numbers, so it is a separate
        change from this port and not one smuggled into it."""
        if self._core is not None:
            return self._core.co_center_exec(init_frame=init_frame)
        return _computed_center(self.link, init_frame=init_frame)

    def place_link(self, x, z, *, tetra=None, init_frame=False):
        """**Teleport the coupled state** -- move Link (and optionally Tetra), then rebuild the
        pending CC push from the MOVED pose, which is what `step` would have left.

        This is the poke recipe the synthetic beds and the freeze-bar gate each used to spell out,
        and it has to live here because a NATIVE run's `self.link` is a field-holder synced FROM the
        C core: writing `run.link.pos_x` on one is a silent no-op, and computing its Co centre off
        `link._foot` reads the SEED's f0 pose rather than the frame it last stepped. Both engines
        are driven through their own owner here -- the core's `pos_x`/`co_center_exec` or the
        `LandState`'s -- so a bed built this way steps identically on either.

        ``init_frame`` matches `_computed_center`: True when the last frame dispatched a proc
        ``*_init`` (the exec base carries no lean there)."""
        x, z = f32(x), f32(z)
        if tetra is not None:
            self.tx, self.tz = f32(tetra[0]), f32(tetra[-1])
        self.link.pos_x, self.link.pos_z = x, z
        if self._core is not None:
            self._core.pos_x, self._core.pos_z = x, z
            self._core._tetra_x, self._core._tetra_z = self.tx, self.tz
        cx = self.co_center(init_frame=init_frame)
        self.pend_link, self.pend_tetra = cc_push_pair(cx, (self.tx, self.tz))
        if self._core is not None:
            self._core._pend_link_x, self._core._pend_link_z = self.pend_link
            self._core._pend_tetra_x, self._core._pend_tetra_z = self.pend_tetra
        return cx

    def pre_seed_input(self, inp):
        """Seed the delay-1 controller buffer (the input the FIRST `step` acts on)."""
        self.link._inbuf = [_step_args(inp)]
        self._prev_raw = inp
        if self._core is not None:
            a = _step_args(inp)
            self._core.pre_seed_courtyard(a[0], a[1], a[2], a[3])

    def set_pending_input(self, inp):
        """Replace the delay-1 pending input WITHOUT stepping -- `pre_seed_input` mid-run.

        The other half of `fork_pending`, and separate because it is the part that has to be right:
        a run's pending input lives in the C core's own buffer, so writing `link._inbuf` alone would
        leave the engine acting on the old letter. `LandCore.pre_seed_courtyard` is the setter for
        that buffer and does not care whether the run has stepped (it writes `_cbuf` and the flag;
        the two C-stick slots it also writes are never read on the courtyard path)."""
        a = _step_args(inp)
        self.link._inbuf = [a]
        self._prev_raw = inp
        if self._core is not None:
            self._core.pre_seed_courtyard(a[0], a[1], a[2], a[3])

    def fork_pending(self, inputs, csangle=None, eye=None, tattn=None):
        """**One frame, N children**: step this frame ONCE and hand it to every pending input.

        A search that expands a node by a whole input alphabet -- `full_herd.junction_beam`'s
        generation is 274 children off one node -- steps the SAME frame once per letter today,
        because the obvious loop is clone-and-step. At `input_delay=1` it does not have to: the
        delivered input is written to the delay buffer and **nothing in the frame reads it**. On the
        native path that is structural rather than empirical -- inside `_anmc`'s
        `_step_courtyard_nogil` the incoming ``sx``/``sy``/``buttons``/``triggerL`` appear in exactly
        two places, the signature and the `_cbuf` write -- so the frame is a function of the state
        alone and the children differ only in what they have PENDING. (Measured beside the proof, on
        a real junction beam: all 274 children of a node land in one physics class and one csangle
        class, at every generation.)

        So the frame runs once and each child is a clone of it carrying its own letter. Returns one
        run per input, in order, each bit-identical to ``clone()`` then ``step(inp)`` -- which is
        what `tests/test_fork_pending.py` asserts field by field, since the whole value of this is
        that it is not an approximation.

        Native runs only. The wired `LandState.step` buffers the same way, but its buffer is not
        this module's to reach into and the search that needs this is native by construction.
        ``record`` is not offered: every child's row would be the same row (it is a function of the
        shared frame), and a caller that wants it should step normally."""
        inputs = list(inputs)
        if not inputs:
            return []
        if self._core is None:
            raise ValueError("fork_pending is the native path's primitive -- the wired step's "
                             "delay buffer belongs to LandState (use clone() + step() per input)")
        base = self.clone()
        base.step(inputs[0], csangle=csangle, eye=eye, tattn=tattn, record=False)
        out = [base]
        for inp in inputs[1:]:
            child = base.clone()
            child.set_pending_input(inp)
            out.append(child)
        return out

    def step(self, inp, csangle=None, eye=None, center=None, tattn=None, record=True):
        """Advance one game frame on raw input ``inp``. ``csangle``/``eye``/``tattn`` as in the
        class doc; ``center`` = an injected SETTLED Co centre for this frame's outgoing push (the
        live-capture mode) -- None uses the computed settled centre (requires ``computed_pose``).
        Returns the sim row dict (``sim_proc``, ``sim_facing``, ``sim_shape_z``, ``sim_link``,
        ``sim_tetra``, ``speedF``, ``sim_cyl`` when computed, and ``sim_csangle`` -- the camera
        value the NEXT frame's physics will read -- when a camera is wired).

        ``record=False`` -- the SEARCH fast path: advance the coupled state (physics + computed
        exec-centre push, both actors' positions 0-ULP identical to ``record=True``) but skip the
        ``sim_cyl`` settled-centre DIAGNOSTIC and the per-frame row dict (the brute force reads
        ``run.link`` / ``run.tx`` directly). Returns None. On the WIRED path it requires
        ``computed_pose`` and no wired camera/zl1/neck (search runs stripped -- geometry-exact per
        the s34 handoff) and now says so rather than silently skipping three models that are STATE:
        the sub-models run after the row here, so a wired run stepped this way would quietly freeze
        its csangle and its eye. The native path has no such rule -- there the look pair runs inside
        the frame and the camera after it, both regardless of ``record``.

        Native-step mode (`native_step=True`) drives the whole coupled frame in C
        (`LandCore.step_courtyard`, native_push=1) -- see `_step_native`."""
        if self._core is not None:
            return self._step_native(inp, csangle=csangle, eye=eye, record=record)
        if not record and (self.camera is not None or self.zl1 is not None
                           or self.neck is not None):
            raise ValueError("record=False is the stripped fast path -- on the wired step it skips "
                             "the camera / zl1 / neck, which are state, not diagnostics")
        link = self.link
        if csangle is not None:
            if self.camera is not None:
                raise ValueError("csangle injection and a wired camera are mutually exclusive")
            self.csangle = csangle
        if self.camera is not None and self._prev_raw is None:
            raise ValueError("camera mode needs pre_seed_input (the camera reads the delay-1 pad)")
        acted_raw = self._prev_raw
        self._prev_raw = inp
        link._cam.yaw = _yaw_from_csangle(self.csangle)
        link.set_cc_move((self.pend_link[0], 0.0, self.pend_link[1]))
        link._atn_actor_pos = (self.tx, self.tz)       # Link Z-targets Tetra (the ATN_ACTOR tier)
        if eye is not None:
            if self.zl1 is not None:
                raise ValueError("eye injection and a wired zl1 look model are mutually exclusive")
            link._atn_actor_eye = (eye[0], eye[-1])
            if len(eye) == 3:
                self._eye_next = tuple(eye)      # keep-last 3D eye (the neck model's look target)
        elif self.zl1 is not None:
            # the modeled end-of-previous-frame eyePos (Link's re-aim reads Tetra's LAST setMtx)
            link._atn_actor_eye = (self._eye_next[0], self._eye_next[2])
        tetra_pre = (self.tx, self.ty, self.tz)
        # setNeckAngle reads the frame-START m34DE (:11287 is in the execute prologue) --
        # capture it BEFORE the step; see knowledge/mechanics/link-head-look.md.
        m34de_neck = link.m34de
        link.step(*_step_args(inp))
        # proc *_init (commonProcInit shape_angle.z=0) runs on the first frame whose pause-read
        # mCurProc differs from the previous frame's -- the post-step state stream is that boundary.
        init_frame = link.state != self.prev_disp
        self.prev_disp = link.state
        # Store Tetra's tracked point as f32 (console cXyz; SetPosCorrect's `*ppos += vec` is f32).
        # A f64 residue survives the per-frame round but the plow amplifier explodes it (README s29).
        self.tx = f32(self.tx + self.pend_tetra[0])
        self.tz = f32(self.tz + self.pend_tetra[1])
        if self.walls_tetra is not None:
            # Her `mObjAcch.CrrPos` where `Zl1FollowState.step` runs it -- after posMove consumes the
            # recoil, speed_y 0 on the flat floor (a gravity dip mis-ejects a corrected XZ by 1 ULP).
            (nx, _ny, nz), _info = acch_crr_pos(
                (tetra_pre[0], self.ty, tetra_pre[2]), (self.tx, self.ty, self.tz),
                self.walls_tetra, speed_y=0.0, wall_h=TETRA_WALL_H, wall_r=TETRA_WALL_R)
            self.tx, self.tz = f32(nx), f32(nz)

        # FOLLOW guard: past FOLLOW_ENGAGE_DIST live Tetra enters the stt-4 follow state this
        # stt-3 plow model does not cover (README planner box) -- warn, the sim is unfaithful.
        if not self._follow_warned:
            dist = math.sqrt((link.pos_x - self.tx) ** 2 + (link.pos_y - self.ty) ** 2
                             + (link.pos_z - self.tz) ** 2)
            if dist > FOLLOW_ENGAGE_DIST:
                self._follow_warned = True
                warnings.warn(
                    "FreeRun: Link-Tetra distance %.1f u exceeds FOLLOW_ENGAGE_DIST (%.0f u) -- "
                    "live Tetra would enter the stt-4 FOLLOW state, which this stt-3 plow model "
                    "does NOT cover; the sim is no longer faithful from this frame on"
                    % (dist, FOLLOW_ENGAGE_DIST))

        row = dict(
            sim_proc=link.state, sim_facing=link.facing,
            sim_shape_z=_s16(link.m351C) >> 1,
            sim_link=(link.pos_x, link.pos_z), sim_tetra=(self.tx, self.tz),
            speedF=link.speedF) if record else None
        # The push consumed producing the NEXT state (decomp draw-phase Ccsp()->Move() order): the
        # CONSOLE push `cc_push_pair` on this frame's EXEC centre (bug-#1 fix; see its docstring).
        if self.computed_pose:
            cx = _computed_center(link, init_frame=init_frame)
            if record:
                row['sim_cyl'] = _cc_settled_center(cx, (self.tx, self.tz))  # DIAGNOSTIC only
                row['sim_cyl_exec'] = cx        # the pose-driven exec centre (drives the push)
        if center is not None:
            # injected SETTLED centre (the live-capture 'injected' mode): approximate full-depth push
            self.pend_link, self.pend_tetra = full_depth_push(center, (self.tx, self.tz))
        elif self.computed_pose:
            # self-contained: the console push from the model's own EXEC centre (0-ULP)
            self.pend_link, self.pend_tetra = cc_push_pair(cx, (self.tx, self.tz))
        else:
            raise ValueError("step() needs either an injected center= or computed_pose")
        if not record:
            return None

        # setNeckAngle m3564: measure the CACHED previous head matrix, chase toward the look
        # target, twist THIS frame's head pose (knowledge/mechanics/link-head-look.md).
        nk = None
        if self.neck is not None:
            look = self.neck.select_look_pos(
                (link.pos_x, link.pos_y, link.pos_z), self._eye_next, m34de_neck,
                link._atn.locked, link._atn.list_present)
            self.neck.update(self._head_mtx, m34de_neck, link.state, look)
            nk = self.neck.local_38()
            self._head_mtx = _computed_head_mtx(link, init_frame=init_frame, neck=nk)
            row['sim_m3564'] = (self.neck.x, self.neck.y, self.neck.z)

        # Zl1 execute: after Link, before the camera Run (eye feeds NEXT frame's re-aim,
        # tattn THIS frame's camera; target = exec-pass mHeadTopPos). tetra-look.md has the laws.
        if self.zl1 is not None:
            ht = _computed_head_top(link, init_frame=init_frame, neck=nk)
            eye_k, tattn_k = self.zl1.step(
                pos_pre=tetra_pre, pos_post=(self.tx, self.ty, self.tz),
                link_pos=(link.pos_x, link.pos_y, link.pos_z), link_head_top_y=ht[1])
            self._eye_next = eye_k
            self._tattn = tattn_k
            row['sim_eye'] = eye_k
            row['sim_tattn'] = tattn_k
            row['sim_head_top'] = ht

        # camera Run (after the player + the CC settle, the game order): the committed csangle is
        # what frame k+1's physics reads. See the class doc for the input laws.
        if self.camera is not None:
            if tattn is not None:
                if self.zl1 is not None:
                    raise ValueError("tattn injection and a wired zl1 look model are mutually "
                                     "exclusive")
                self._tattn = (tattn[0], tattn[1], tattn[2])
            self._run_camera(acted_raw, link.pos_x, link.pos_y, link.pos_z, link.facing,
                             link._atn.locked,
                             float(fadds(f32(92.5), f32(link._foot.ff.base[1][3]))), row)
        return row

    def _run_camera(self, acted_raw, pos_x, pos_y, pos_z, facing, locked, attn_y, row):
        """The camera Run at the end of a frame -- ONE expression of it, for both step paths.

        The wired step and the native one differ only in where the four arguments come from (the
        Python `LandState` / the C core), never in the law, so a native run commits the csangle the
        wired one does by construction rather than by a copy kept in step. ``attn_y`` is Link's
        `attention_info.position` Y: the wired path takes it off the posed `FootFK` base, the
        native one off `LandCore.attn_y` -- the same `setAttentionPos` row, read from whichever
        engine drew the frame."""
        if locked and self._tattn is None:
            raise ValueError("the sim's attention lock is engaged but no tattn (the locked "
                             "actor's attention_info.position) was ever injected")
        cam_link = dict(pos=(pos_x, pos_y, pos_z), facing=facing,
                        attn_pos=(pos_x, attn_y, pos_z))
        attn = dict(truth=locked, lockon=locked, target_attn=self._tattn if locked else None)
        self.csangle = self.camera.step(cam_pad(acted_raw), cam_link, attn)
        if row is not None:
            row['sim_csangle'] = self.csangle
            row['sim_attn_y'] = attn_y
            # published so a camera can be walked off this frame's arguments: roll_kernel.SharedBody
            row['sim_cam_in'] = (cam_link, attn)

    def _step_native(self, inp, csangle=None, eye=None, record=True):
        """The NATIVE search fast path: one `LandCore.step_courtyard(native_push=1)` call, then a few
        field reads. Everything the coupled Python `step` (computed-pose config) does -- delay-1 input
        buffer, stick decode, attention machine, procs, the A-roll trigger, the fused pose FK + speedF,
        the posMove recoil consume, the body-Co exec centre, the CC push pair, and the f32 Tetra
        track -- runs inside the C engine. csangle is injected per frame (held if None); eye is the
        proc-9 re-aim target (feet-fallback when None -- the stripped no-zl1 search config). The
        Python `self.link` public fields (pos/facing/travel/speedF/state) and `self.tx/self.tz` are
        synced back so the search reads them exactly as in Python mode.

        SELF-EYE MODE (session 127): with a wired ``zl1``/``neck`` the eye is not injected at all --
        the chain runs HERE, off the core's own `head_mtx_exec` / `head_top_exec`, and the run is the
        wired one 0-ULP (Link, Tetra, the eye, m3564) with only csangle supplied. That is what makes a
        coupled rollout affordable: the camera is the caller's (and for a roll fan it is a per-node
        constant), while everything else is C plus two cheap Python models.

        NATIVE-LOOK MODE (session 128): those two models are no longer Python. They were measured at
        91% of the coupled step, so `step_courtyard` now runs them itself and this method becomes one
        C call plus the field sync -- the eye chain is inside the frame where it belongs (her eyePos
        arms the NEXT frame's proc-9 re-aim), and the look state is read through the live views.

        WIRED-CAMERA MODE (session 131): with a ``camera`` the run drives it here too, off
        `LandCore.attn_y` and the core's own pos/facing/lock -- so csangle is committed inside the
        native run instead of being injected into it, and a whole node chain (the junction, its
        quality glides, the roll exit tails) runs on the C step. The camera model itself stays
        Python: it is one step per frame against a whole coupled frame, and `_run_camera` is the
        one expression both paths call."""
        if csangle is not None:
            if self.camera is not None:
                raise ValueError("csangle injection and a wired camera are mutually exclusive")
            self.csangle = csangle
        if self.camera is not None and self._prev_raw is None:
            raise ValueError("camera mode needs pre_seed_input (the camera reads the delay-1 pad)")
        acted_raw = self._prev_raw
        self._prev_raw = inp
        if isinstance(inp, dict):
            sx = int(inp['stickX']); sy = int(inp['stickY'])
            btn = int(inp.get('buttons', 0)); trg = int(inp.get('triggerL', 0))
        else:
            t = inp
            sx = int(t[0]); sy = int(t[1])
            btn = int(t[2]) if len(t) > 2 else 0
            trg = int(t[3]) if len(t) > 3 else 0
        core = self._core
        if self.zl1 is not None:
            if eye is not None:
                raise ValueError("eye injection and a wired zl1 look model are mutually exclusive")
        if self._native_look:
            # The core holds the eye and advances it itself; nothing to capture or inject.
            ex = ez = 0.0; he = 0
            m34de_neck = None
            tetra_pre = None
        else:
            if self.zl1 is not None:
                eye = self._eye_next      # the modeled end-of-previous-frame eyePos
            if eye is not None:
                ex, ez, he = float(eye[0]), float(eye[-1]), 1
            else:
                ex = ez = 0.0; he = 0
            # setNeckAngle reads the frame-START m34DE, and her look reads her PRE-plow position --
            # both must be captured before the core steps (the Python step's own ordering).
            m34de_neck = int(core.m34de)
            tetra_pre = (self.tx, self.ty, self.tz)
        sf = core.step_courtyard(sx, sy, btn, trg, int(self.csangle) & 0xFFFF,
                                 0.0, 0.0, ex, ez, he, 0.0, 0.0, 0.0, 0, 1)   # native_push=1
        link = self.link
        link.pos_x = core.pos_x; link.pos_z = core.pos_z
        link.facing = core.facing; link.travel = core.travel
        link.speedF = sf; link.nspeed = core.nspeed
        link.state = core.state
        self.tx = core._tetra_x; self.tz = core._tetra_z
        self.pend_link = (core._pend_link_x, core._pend_link_z)
        self.pend_tetra = (core._pend_tetra_x, core._pend_tetra_z)
        # FOLLOW guard (search reads run._follow_warned): identical test to the Python step; skipped
        # once tripped (the model is unfaithful past FOLLOW_ENGAGE_DIST -- see the class doc).
        if not self._follow_warned:
            dist = math.sqrt((link.pos_x - self.tx) ** 2 + (link.pos_y - self.ty) ** 2
                             + (link.pos_z - self.tz) ** 2)
            if dist > FOLLOW_ENGAGE_DIST:
                self._follow_warned = True
                warnings.warn(
                    "FreeRun: Link-Tetra distance %.1f u exceeds FOLLOW_ENGAGE_DIST (%.0f u) -- "
                    "live Tetra would enter the stt-4 FOLLOW state, which this stt-3 plow model "
                    "does NOT cover; the sim is no longer faithful from this frame on"
                    % (dist, FOLLOW_ENGAGE_DIST))

        # The look chain in the Python step's order (neck, then her execute), off the CORE's posed
        # chain -- no Python pose FK. knowledge/model/the-eye-was-the-only-thing-in-python.md
        # In native-look mode the core already ran both models inside the frame; raise here whatever
        # the Python one would have (the nogil step can only set a flag).
        nk = None
        if self._native_look:
            core.look_check()
        elif self.neck is not None:
            look = self.neck.select_look_pos((core.pos_x, core.pos_y, core.pos_z), self._eye_next,
                                             m34de_neck, core._atn_state in (_ATN_LOCK, _ATN_RELEASE),
                                             bool(core._atn_list_present))
            self.neck.update(self._head_mtx, m34de_neck, core.state, look)
            nk = self.neck.local_38()
            self._head_mtx = core.head_mtx_exec(nk)
        if self.zl1 is not None and not self._native_look:
            ht = core.head_top_exec(nk)
            eye_k, tattn_k = self.zl1.step(
                pos_pre=tetra_pre, pos_post=(self.tx, self.ty, self.tz),
                link_pos=(core.pos_x, core.pos_y, core.pos_z), link_head_top_y=ht[1])
            self._eye_next = eye_k
            self._tattn = tattn_k
        row = None
        if record:
            row = dict(sim_proc=core.state, sim_facing=core.facing,
                       sim_shape_z=core.court_shape_z,
                       sim_link=(core.pos_x, core.pos_z), sim_tetra=(self.tx, self.tz),
                       speedF=sf)
            if self.neck is not None:
                row['sim_m3564'] = (self.neck.x, self.neck.y, self.neck.z)
            if self.zl1 is not None:
                row['sim_eye'] = self._eye_next
                row['sim_tattn'] = self._tattn
                if not self._native_look:
                    row['sim_head_top'] = core.head_top_exec(nk)
        if self.camera is not None:
            self._run_camera(acted_raw, core.pos_x, core.pos_y, core.pos_z, core.facing,
                             core._atn_state in (_ATN_LOCK, _ATN_RELEASE), core.attn_y, row)
        return row


def replay(frames, input_at, entry, upto=None, pre_inputs=None, seed_nspeed=None,
           centers='injected', eyes=None, seed_old_pose=None, camera=None, tattns=None,
           zl1=None, neck=None, seed_push=None):
    """Run the coupled from-f0 replay and diff BOTH actors vs the live capture, frame by frame.

    ``frames``   -- the live-capture rows (the cyl fixture), each ``{proc, csangle, link:{pos, facing,
                    travel, speedF, cyl}, tetra:{pos, stt, speedF}}``; ``frames[i]`` is game-frame i.
    ``input_at`` -- ``input_at(k)`` -> the raw controller tuple ``(sx, sy, buttons, triggerL)`` (or a
                    6-tuple; extra entries ignored) delivered at game-frame ``k`` (from the DTM).
    ``entry``    -- the seed frame (0 = true state-2 from-f0; a roll-entry index = the validated mode).
    ``upto``     -- exclusive end frame (default ``len(frames)``).
    ``pre_inputs`` -- optional pre-seed for the delay-1 controller buffer; a single input (or a
                    1-tuple/list). If omitted, uses ``input_at(entry)`` (the convention: after seeding
                    state[entry], ``step(input_at(entry+1))`` acts on ``input_at(entry)`` at
                    input_delay=1 -- physics reads the delay-1 DTM pad). See the README from-f0 box.
    ``seed_nspeed`` -- optional mNormalSpeed for a non-roll seed (the true f0 seed needs it; speedF
                    lags nspeed a frame there -- see `_seed_link`). Omit for roll-entry seeds.
    ``seed_old_pose`` -- optional captured live `m_old_fdata` store for the f0 pose seed
                    (`courtyard_push_seed.json` ``old_pose``): the per-joint post-morf pre-twist
                    quat/transform of the last live-posed frame + the morf counters. Required for a
                    bit-exact f1 entry-morf pose (the pure-dash warmup is ~1.7 u off at f0 -- the
                    store still carries the prior cycle's ATN->MOVE morf mixture; session 16).
                    Computed/diag modes only.
    ``eyes``     -- optional per-frame Tetra EYE positions (``fixtures/courtyard_push_eyepos.json``
                    ``frames[k]['eye']``, indexed by game frame): the proc-9 re-aim target
                    (`setShapeAngleToAtnActor` chases the bearing to `mpAttnActorLockOn->eyePos`,
                    Tetra's ANIMATED head-joint world pos -- it leads her feet 16-26 u, so the feet
                    fallback lands the chase ~200 BAM short; session 15). Injected as end-of-previous-
                    frame values (Link executes before Tetra). None -> aim at the plowed feet.
    ``centers``  -- ``'injected'`` (default): Link's Co centre comes from the capture
                    (``frames[k]['link']['cyl']``), the validated mode. ``'computed'``: the centre is
                    rebuilt each frame from the SIM'S OWN drawn pose (`FootFK.body_co_center` --
                    setCollision's root/neck midpoint), seeded at f0 off the captured anim phase +
                    turn lean (`_seed_pose_f0`) -- the self-contained mode the planner needs (no
                    per-frame injection; only csangle stays injected). f0-seed only. Each row then
                    also carries ``sim_cyl`` and the centre-vs-capture ULP diffs ``dcx``/``dcz``.
    ``camera``   -- a SEEDED `LandCamera` (see the `FreeRun` class doc): replaces the per-frame
                    csangle injection with the modeled camera driven by the sim's own state; each
                    row then also carries ``sim_csangle`` (vs ``frames[k]['csangle']``, the live
                    value the NEXT frame's physics read).
    ``tattns``   -- per-frame locked-actor attention positions (camera mode; indexed by game frame,
                    consumed on lock-window frames -- the session-18 cam oracle's ``tattn``).
    ``zl1``      -- a SEEDED `core.npc_zl1_look.Zl1Look` (`Zl1Look.seed_from_row` off the
                    ``fixtures/courtyard_zl1look.json`` f0 row): replaces BOTH the ``eyes`` and
                    ``tattns`` injections with the modeled Tetra look-at (mutually exclusive with
                    them). Computed mode only. Each row then also carries ``sim_eye``,
                    ``sim_tattn``, ``sim_head_top``.
    ``neck``     -- a SEEDED `land.neck_look.NeckLook` (the live f0 ``m3564``,
                    ``fixtures/courtyard_m3564.json`` f0): models Link's own head-look twist
                    (setNeckAngle), so ``sim_head_top`` carries the tier-frame Y shift Tetra's
                    elevation chase consumes. Computed mode only. Each row then also carries
                    ``sim_m3564``.
    ``seed_push``-- the DETERMINISTIC f0->f1 Tetra CC push ``(dx, dz)`` (from f0 seeds only):
                    ``courtyard_push_perop.json`` ΔTetra = ``tetra[1] - tetra[0]`` (the exact
                    console push; Tetra has no foot term so her whole f0->f1 move IS the push).
                    Passed to `FreeRun` so the f0 seed frame is 0-ULP (see the class doc). Omit
                    for roll-entry seeds.

    Link's Co centre and csangle are injected from ``frames`` each frame; Tetra is a tracked XZ point
    moved by the full-depth plow. Returns a list of per-frame dicts: ``f``, live/sim ``proc``,
    ``sim_link``/``live_link`` and ``sim_tetra``/``live_tetra`` (x, z), the sim-minus-live position
    ULP diffs ``dlx/dlz/dtx/dtz`` (0 == bit-exact), and ``speedF``/``live_speedF``."""
    if upto is None:
        upto = len(frames)

    run = FreeRun(frames[entry], seed_nspeed=seed_nspeed, seed_old_pose=seed_old_pose,
                  computed_pose=centers in ('computed', 'diag'), camera=camera, zl1=zl1,
                  neck=neck, seed_push=seed_push)
    if pre_inputs is not None:
        pi = pre_inputs[-1] if isinstance(pre_inputs, (list, tuple)) and pre_inputs and \
            isinstance(pre_inputs[0], (list, tuple, dict)) else pre_inputs
        run.pre_seed_input(pi)
    else:
        run.pre_seed_input(input_at(entry))             # delay-1: state[entry+1] acts inp[entry]

    out = []
    for k in range(entry + 1, upto):
        lv = frames[k]
        # csangle/eye = end-of-frame-(k-1) values; the centre stays injected from the capture
        # except in the self-contained 'computed' mode (see the FreeRun class doc).
        eye = eyes[k - 1] if (eyes is not None and k - 1 < len(eyes)) else None
        tattn = tattns[k] if (tattns is not None and k < len(tattns)) else None
        row = run.step(input_at(k), csangle=None if camera is not None else frames[k - 1]['csangle'],
                       eye=eye, tattn=tattn,
                       center=None if centers == 'computed' else lv['link']['cyl'])
        row.update(
            f=k, live_proc=lv['proc'], live_facing=lv['link']['facing'],
            live_shape_z=lv['link'].get('shape_z'),
            live_link=(lv['link']['pos'][0], lv['link']['pos'][2]),
            live_tetra=(lv['tetra']['pos'][0], lv['tetra']['pos'][2]),
            live_speedF=lv['link']['speedF'],
            dlx=_bits(row['sim_link'][0]) - _bits(lv['link']['pos'][0]),
            dlz=_bits(row['sim_link'][1]) - _bits(lv['link']['pos'][2]),
            dtx=_bits(row['sim_tetra'][0]) - _bits(lv['tetra']['pos'][0]),
            dtz=_bits(row['sim_tetra'][1]) - _bits(lv['tetra']['pos'][2]))
        if centers in ('computed', 'diag'):
            row['dcx'] = _bits(row['sim_cyl'][0]) - _bits(lv['link']['cyl'][0])
            row['dcz'] = _bits(row['sim_cyl'][1]) - _bits(lv['link']['cyl'][-1])
        out.append(row)
    return out


def _raw_dict(inp):
    """Normalise a raw controller tuple to the dict form `pad_from_raw` reads (dicts pass through).
    Tuple convention as `_step_args`: (sx, sy[, buttons[, trigL[, subX, subY]]])."""
    if isinstance(inp, dict):
        return inp
    t = tuple(inp)
    return dict(stickX=int(t[0]), stickY=int(t[1]),
                buttons=int(t[2]) if len(t) > 2 else 0,
                triggerL=int(t[3]) if len(t) > 3 else 0,
                substickX=int(t[4]) if len(t) > 4 else 128,
                substickY=int(t[5]) if len(t) > 5 else 128)


def cam_pad(inp):
    """The `LandCamera` pad for a raw controller input -- the camera's whole view of the controller.

    Public, and used by `step` itself, so a caller that walks a camera outside a `FreeRun` (a
    `roll_kernel` tcs family drives one over a shared body's arguments) reads the pad through the
    same expression the run does rather than a second copy of it."""
    return pad_from_raw(_raw_dict(inp))


def _step_args(inp):
    """Normalise a raw controller tuple/dict to the 6-arg `LandState.step` call (C-stick neutral --
    csangle is injected via `_cam.yaw`, not steered)."""
    if isinstance(inp, dict):
        return (int(inp['stickX']), int(inp['stickY']), int(inp.get('buttons', 0)),
                int(inp.get('triggerL', 0)), 128, 128)
    t = tuple(inp)
    return (int(t[0]), int(t[1]), int(t[2]) if len(t) > 2 else 0,
            int(t[3]) if len(t) > 3 else 0, 128, 128)
