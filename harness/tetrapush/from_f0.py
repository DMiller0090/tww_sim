"""The Courtyard from-f0 (and roll-entry) COUPLED replay -- the full-depth CC coupling wired together.

This is the last piece before the planner: seed a closed-loop `LandState` (Link) + a tracked Tetra
point at state 2 (or a roll entry), drive Link with the REAL DTM controller bytes, and apply BOTH
gated plow laws each frame:

  * `link_plow.recoil`  -- Link recoils the FULL Co-overlap depth AWAY from Tetra (his own slowdown),
  * `tetra_plow.plow_step` -- Tetra is shoved the FULL depth AWAY from Link (the herd),

each computed from Link's ANIMATED mCyl Co centre. Both eject the full `cross_len` (the mirror pair,
2*depth total separation per frame -- the live 41-85 u chase-and-plow). Tetra is stt-3 the WHOLE
Courtyard window (pure plow, speedF 0 -- see the cyl-fixture timeline), so she is a bare XZ point
moved by `tetra_plow`; there is no follow leg to model here.

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

from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST
from tww_sim.land.land import LandState, FRONT_ROLL, MOVE
from harness.tetrapush.link_plow import recoil


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _yaw_from_csangle(csangle):
    """The `dCamera_c` yaw for a captured `csangle` (== `(yaw + 0x8000) & 0xFFFF`), so forcing
    `_cam.yaw` with a neutral C-stick holds `csangle` frozen at the injected value that frame."""
    return (int(csangle) - 0x8000) & 0xFFFF


def full_depth_push(link_center, tetra_xz):
    """The Courtyard full-depth CC push for one frame: returns ``((link_dx, link_dz), (tetra_dx,
    tetra_dz))`` -- Link's recoil (`link_plow.recoil`, the full Co-overlap depth AWAY from Tetra)
    and Tetra's push (the full depth AWAY from Link), computed from Link's Co centre ``link_center``
    (x, z or x, y, z) and Tetra's feet ``tetra_xz``.

    The two are EXACT bit-for-bit opposites: a single same-rank Co pair ejects equal-and-opposite
    (Newton's third law in the CC resolution -- `cc_push.co_move_pair`'s vec1/vec2 sum to 0,
    live-confirmed). Tetra's push is therefore ``-recoil`` (an exact f32 sign flip of the same
    delta), NOT the old ``tetra_plow.plow_step`` new-minus-old form (which recomputed the new pos in
    f64 and subtracted the original, differing from Link's direct f32 delta by ~1 ULP where Tetra's
    coord is large -- the session-24 bug-#1 self-consistency violation). This is still the
    full-depth-from-SETTLED-centre framing (numerically the exec-centre half-depth to ~1e-5 u); the
    remaining exec-vs-settled ~few-ULP gap vs the console needs the per-op `m_cc_move` capture."""
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
    dash = st._dash                      # 'dash' (sword_drawn=False)
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
    measured against the SETTLED centre it reads as the full depth.) fp-faithful mirror of
    `tetra_plow.plow_step` with the half factor, directed away from Tetra."""
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
                         use_anim=True, native=False, sword_drawn=False, input_delay=1)
        link._roll_m3570 = False           # seeded mid-roll: live grinds (no bonk) -> m3570 False
    else:
        ns = ll['speedF'] if seed_nspeed is None else float(seed_nspeed)
        link = LandState(pos_x=ll['pos'][0], pos_z=ll['pos'][2], pos_y=ll['pos'][1],
                         facing=ll['facing'], travel=ll['travel'], csangle=csangle,
                         state=proc, nspeed=ns, speedF=ll['speedF'],
                         use_anim=True, native=False, foot_native=False, sword_drawn=False,
                         input_delay=1)
        link._foot.started = True
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
    point -- unmodeled, same status as eyePos; keep-last semantics like ``eye``)."""

    def __init__(self, seed_row, *, seed_nspeed=None, seed_old_pose=None, computed_pose=True,
                 camera=None, zl1=None, neck=None):
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
        self.camera = camera
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
        # The SEED frame's Co centre is static initial-condition data even in computed mode
        # (computing it needs f-1's m351C, which the seed doesn't carry); f1 on is computed. (s16)
        c0 = e['link']['cyl']
        self.pend_link, self.pend_tetra = full_depth_push(c0, (self.tx, self.tz))
        self.prev_disp = self.link.state               # dispatch proc of the seed frame

    def pre_seed_input(self, inp):
        """Seed the delay-1 controller buffer (the input the FIRST `step` acts on)."""
        self.link._inbuf = [_step_args(inp)]
        self._prev_raw = inp

    def step(self, inp, csangle=None, eye=None, center=None, tattn=None):
        """Advance one game frame on raw input ``inp``. ``csangle``/``eye``/``tattn`` as in the
        class doc; ``center`` = an injected SETTLED Co centre for this frame's outgoing push (the
        live-capture mode) -- None uses the computed settled centre (requires ``computed_pose``).
        Returns the sim row dict (``sim_proc``, ``sim_facing``, ``sim_shape_z``, ``sim_link``,
        ``sim_tetra``, ``speedF``, ``sim_cyl`` when computed, and ``sim_csangle`` -- the camera
        value the NEXT frame's physics will read -- when a camera is wired)."""
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
        self.tx += self.pend_tetra[0]
        self.tz += self.pend_tetra[1]

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
            speedF=link.speedF)
        # end-of-frame check: the push consumed producing the NEXT state uses this frame's SETTLED
        # centre + Tetra pos (the decomp draw-phase Ccsp()->Move() order).
        if self.computed_pose:
            cx = _computed_center(link, init_frame=init_frame)
            ck = _cc_settled_center(cx, (self.tx, self.tz))
            row['sim_cyl'] = ck
            row['sim_cyl_exec'] = cx           # the pose-driven exec centre (pre-CC-settle),
                                               # a diagnostic for the centre/divergence work
        else:
            ck = None
        if center is not None:
            ck = center
        self.pend_link, self.pend_tetra = full_depth_push(ck, (self.tx, self.tz))

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
            locked = link._atn.locked
            if locked and self._tattn is None:
                raise ValueError("the sim's attention lock is engaged but no tattn (the locked "
                                 "actor's attention_info.position) was ever injected")
            from tww_sim.core.fp import f32, fadds
            from tww_sim.core.camera.land_cam import pad_from_raw
            attn_y = float(fadds(f32(92.5), f32(link._foot.ff.base[1][3])))
            cam_link = dict(pos=(link.pos_x, link.pos_y, link.pos_z), facing=link.facing,
                            attn_pos=(link.pos_x, attn_y, link.pos_z))
            attn = dict(truth=locked, lockon=locked,
                        target_attn=self._tattn if locked else None)
            self.csangle = self.camera.step(pad_from_raw(_raw_dict(acted_raw)), cam_link, attn)
            row['sim_csangle'] = self.csangle
            row['sim_attn_y'] = attn_y
        return row


def replay(frames, input_at, entry, upto=None, pre_inputs=None, seed_nspeed=None,
           centers='injected', eyes=None, seed_old_pose=None, camera=None, tattns=None,
           zl1=None, neck=None):
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

    Link's Co centre and csangle are injected from ``frames`` each frame; Tetra is a tracked XZ point
    moved by the full-depth plow. Returns a list of per-frame dicts: ``f``, live/sim ``proc``,
    ``sim_link``/``live_link`` and ``sim_tetra``/``live_tetra`` (x, z), the sim-minus-live position
    ULP diffs ``dlx/dlz/dtx/dtz`` (0 == bit-exact), and ``speedF``/``live_speedF``."""
    if upto is None:
        upto = len(frames)

    run = FreeRun(frames[entry], seed_nspeed=seed_nspeed, seed_old_pose=seed_old_pose,
                  computed_pose=centers in ('computed', 'diag'), camera=camera, zl1=zl1,
                  neck=neck)
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


def _step_args(inp):
    """Normalise a raw controller tuple/dict to the 6-arg `LandState.step` call (C-stick neutral --
    csangle is injected via `_cam.yaw`, not steered)."""
    if isinstance(inp, dict):
        return (int(inp['stickX']), int(inp['stickY']), int(inp.get('buttons', 0)),
                int(inp.get('triggerL', 0)), 128, 128)
    t = tuple(inp)
    return (int(t[0]), int(t[1]), int(t[2]) if len(t) > 2 else 0,
            int(t[3]) if len(t) > 3 else 0, 128, 128)
