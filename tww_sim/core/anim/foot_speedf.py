"""foot_speedf.py - offline posMoveFromFootPos: turn (mNormalSpeed, mStickDistance) into the walk
position speed `speedF`, bit-faithfully.

This is the last link of the land-walk position chain. It composes the three ported subsystems:
  UnderAnimState (anim_state.py)  -- which anims fill MOVE0/MOVE1, their frame-ctrl frames, the
                                     blend ratio, and m3598 (the WALK<->DASH speedF blend), all a
                                     bit-exact function of the already-bit-exact mNormalSpeed.
  FootFK (foot_fk.py)             -- the stateful foot forward-kinematics with the oldframe-morf,
                                     giving the model-local foot toe both feet.
  posMoveFromFootPos math (here)  -- plant select, the 1-frame-delayed toe delta f31_2, the
                                     recursive smoothing, and speedF = nspeed*(1-m3598) +/- f31_2*m3598.

Faithful to d_a_player_main.cpp:2353. Reproduces live speedF bit-exact (float ~1e-5) across the
flat on-axis walk INCLUDING the standing->walk entry: while nspeed==0 the game keeps drawing the
standing idle (FREEB advancing at rate 1.0), and the first moving frame's f31_2 is exactly the
idle-drift delta absXZ(FK(FREEB@f+2) - FK(FREEB@f+1)). We reproduce that by advancing the idle
during the input-latency frames. The fully-stopped frame (nspeed hits 0) has speedF=0 (the MOVE
proc is exiting, posMoveFromFootPos no longer drives position).

SCOPE: the normal flat, on-axis, free walk from a FREEB standing idle (the land_flatwalk anchor).
One walk burst. Attention/heavy/slope/ice, and re-entering idle after a stop, are future tiers.

Requires the gitignored _generated/anim keyframe data (Link.arc/LkAnm.arc, dev-supplied); if it is
absent `FootSpeedF()` raises and superswim.land falls back to its calibrated speedF stand-in. Use
`FootSpeedF.available()` to probe without raising.
"""
import math
import os

from .. import fp
from . import fk
from .anim_state import (UnderAnimState, ANIM_META, ANIM_CODE, ANIM_ORDER,
                         NATIVE_META_MAX, NATIVE_META_ATTR, NATIVE_HIO, H_38, H_40)

# Optional native composition (anim/_anmc.foot_compose); bit-exact with _py_foot_compose below.
try:
    from . import _anmc as _N
except ImportError:
    _N = None

# f32 literals from the posMoveFromFootPos recursive-smoothing (d_a_player_main.cpp:2400).
_F0_3 = fp.f32(0.3)
_F0_7 = fp.f32(0.7)
IDLE_ANIM = 'freeb'
# posMoveFromFootPos rest offset used only when oldFrameFlg==false (Link never posed the walk yet).
# Not reached from a standing anchor (flag already true); kept for provenance.
REST_TOE = ((-14.05, 0.0, 5.02), (14.05, 0.0, 5.02))   # [right, left]


def _f32(x):
    return fp.f32(float(x))


def _sqrtf(x):
    """std::sqrtf (MSL math.h): frsqrte seed + 3 Newton refines in DOUBLE, then f32(x*guess).
    The crude frsqrte seed (~5 bits) is fully washed out by 3 Newton steps (the comment claims 32
    sig bits, > f32's 24), so a math-accurate double seed gives the byte-identical f32 result."""
    x = fp.f32(x)
    if x > 0.0:
        g = 1.0 / math.sqrt(x)                        # frsqrte seed (low bits irrelevant after Newton)
        g = 0.5 * g * (3.0 - g * g * x)               # all 3 refines in f64
        g = 0.5 * g * (3.0 - g * g * x)
        g = 0.5 * g * (3.0 - g * g * x)
        return fp.f32(x * g)                          # y = (float)(x * guess)
    return fp.f32(x)


def _absxz(dx, dz):
    """cXyz::absXZ() for the toe delta (dx,0,dz): sqrtf(abs2XZ) where abs2XZ is the paired-single
    PSVECSquareMag == fmadds(dz,dz, fmuls(dx,dx)) (f32, one fused round of dz*dz onto the f32 dx*dx),
    NOT the double-precision math.hypot. See tww c_xyz.h / dolphin/mtx/vec.c PSVECSquareMag."""
    sq = fp.fmadds(dz, dz, fp.fmuls(dx, dx))
    return _sqrtf(sq)


def _plant_of(feet):
    """m34BC on flat ground: index (0=right jnt39, 1=left jnt34) of the lower toe/heel midpoint Y.
    `feet` is the flat 12-tuple [Rtoe, Ltoe, Rheel, Lheel] x (x,y,z) from step_feet/pose_toe."""
    m0 = _f32((feet[1] + feet[7]) * 0.5)     # right: toe.y (idx 1) + heel.y (idx 7)
    m1 = _f32((feet[4] + feet[10]) * 0.5)    # left:  toe.y (idx 4) + heel.y (idx 10)
    return 0 if m0 < m1 else 1


def _py_foot_compose(t1, t2, nspeed, msd, m3598, prev_f312, m35B4):
    """Pure-Python posMoveFromFootPos toe->speedF (fallback for _anmc.foot_compose). t1/t2 are the
    flat 12-tuples of the last two DRAWN frames. Returns (speedF, f312)."""
    plant = _plant_of(t1)
    o = plant * 3
    dx = _f32(t1[o + 0] - t2[o + 0])
    dz = _f32(t1[o + 2] - t2[o + 2])
    f312 = _absxz(dx, dz)
    if m3598 < 1.0 and abs(_f32(m35B4 - msd)) < 0.2:
        f312 = fp.fadds(fp.fmuls(f312, _F0_3), fp.fmuls(_F0_7, prev_f312))
    spz = _f32(nspeed * _f32(1.0 - m3598))
    spz = _f32(spz + _f32(f312 * m3598)) if nspeed >= 0.0 else _f32(spz - _f32(f312 * m3598))
    speedF = 0.0 if abs(spz) < 0.05 else spz
    return speedF, f312


class FootSpeedF:
    """Stateful offline posMoveFromFootPos driver. step(nspeed, msd) -> speedF for this frame.

    Seed idle_frame with the live FREEB frame-controller value at the anchor (mFrameCtrlUnder[0]
    frame); it fixes the entry idle-drift phase. Default 70.0 = the land_flatwalk anchor.
    """

    @staticmethod
    def available():
        """True iff the generated anim + skeleton data is present (so the engine can run)."""
        try:
            fk.load()
            return True
        except (FileNotFoundError, OSError):
            return False

    def __init__(self, idle_frame=70.0, idle_anim=IDLE_ANIM, pos_x=0.0,
                 pos_z=764.0791015625, facing=0, native=True):
        self.anm, self.sk = fk.load()                 # raises if the data is absent
        self.idle_anim = idle_anim
        self._core = None                             # fused native engine (set up below if available)
        self._idle_frame_py = float(idle_frame)       # backing store for the idle_frame property
        self.idle_end = float(ANIM_META[idle_anim][0])
        self.st = UnderAnimState(move0_anim=idle_anim, move0_frame=self.idle_frame, m34C3=0)
        from .foot_fk import FootFK
        self.ff = FootFK(self.anm, self.sk)
        # Link's world pose for the frame being posed (the foot FK runs from worldBase(pos)). LandState
        # updates it via set_pos BEFORE each step; seeded here at the anchor rest pose.
        self.pos_x = float(pos_x)
        self.pos_z = float(pos_z)
        self.facing = int(facing) & 0xFFFF
        self.ff.set_pos(self.pos_x, self.pos_z, facing=self.facing)
        self.started = False
        self.stopped = False
        # Seed the FootFK old pose + delayed toe stream (t1=draw_{N-1}, t2=draw_{N-2}) with the
        # idle rest pose. Pre-walk seeds only feed m3598==0 frames (speedF==0), so they're immaterial.
        self.ff.seed(idle_anim, self.idle_frame)
        draw0 = self.ff.step_feet(idle_anim, idle_anim, self.idle_frame, self.idle_frame, 0.0, -1.0)
        self.t1 = draw0
        self.t2 = draw0
        self.prev_f312 = 0.0
        self.m35B4 = 0.0                               # previous frame's mStickDistance
        self._single_entered = False                   # single-anim entry frame: hold the ctrl at start
        self._pending_py = None                        # morf to apply on the next step (Python fallback store)
        # Fused native path (one C call/frame): the Python seeding above already left the engine's
        # old-pose correct + produced draw0; w_init captures the toe stream. Python st/ff = fallback.
        if native and _N is not None and getattr(self.ff, '_engine', None) is not None:
            _N.init_anim_consts(NATIVE_META_MAX, NATIVE_META_ATTR, NATIVE_HIO)   # idempotent
            code2idx = [self.ff._anim_idx[name] for name in ANIM_ORDER]
            self._core = self.ff._engine
            self._core.init_anim(code2idx)
            self._core.w_init(ANIM_CODE[idle_anim], self._idle_frame_py, draw0)
        elif not native:
            # Force the pure-Python st/ff path (drop only the C-resident STATE; native math accel stays)
            # -- the SUBJECTIVITY freeze lives on the Python UnderAnimState. draw0/seed above left t1/t2 exact.
            self.ff._engine = None

    def clone(self):
        """State-copy clone (mid-walk-safe). Shares the immutable parsed anim/skeleton; deep-copies
        the stateful anim engine (the fused C PoseEngine via FootFK.clone, or the Python
        UnderAnimState) + the delayed toe stream, so a clone taken mid-walk continues bit-exactly
        (0 divergence at every frame). Replaces the old rebuild-at-rest clone, which reset the toe
        stream to the idle pose and so was only valid to clone before the first walk step."""
        c = FootSpeedF.__new__(FootSpeedF)
        c.anm = self.anm; c.sk = self.sk
        c.idle_anim = self.idle_anim
        c.idle_end = self.idle_end
        c.pos_x = self.pos_x; c.pos_z = self.pos_z; c.facing = self.facing
        c.started = self.started; c.stopped = self.stopped
        c._single_entered = self._single_entered
        c._idle_frame_py = self._idle_frame_py
        c._pending_py = self._pending_py
        c.st = self.st.clone()
        c.ff = self.ff.clone()
        c._core = c.ff._engine                 # fused engine lives on the cloned FootFK (None in Py mode)
        c.t1 = self.t1; c.t2 = self.t2         # flat toe tuples (immutable) -> share the reference
        c.prev_f312 = self.prev_f312
        c.m35B4 = self.m35B4
        return c

    @property
    def idle_frame(self):
        """The (drifting) standing-idle frame. Fused mode tracks it in C; clone reads it here so a
        clone taken mid input-latency drift re-seeds at the right phase (matches the Python path)."""
        return self._core.w_get_idle_frame() if self._core is not None else self._idle_frame_py

    @idle_frame.setter
    def idle_frame(self, v):
        # Only the Python fallback mutates this (fused w_step owns the C copy).
        self._idle_frame_py = float(v)

    @property
    def _pending_morf(self):
        return self._core.w_get_pending() if self._core is not None else self._pending_py

    @_pending_morf.setter
    def _pending_morf(self, v):
        if self._core is not None:
            self._core.w_set_pending(v)
        else:
            self._pending_py = v

    def set_pos(self, px, pz, facing=0):
        """LandState calls this each frame BEFORE stepping, with the CURRENT (pre-integration) world
        pos + shape_angle.y. The foot FK poses from worldBase(pos), so the toe carries the game's
        world-magnitude quantization for THIS frame's draw (stored into the toe stream)."""
        self.pos_x = fp.f32(px)
        self.pos_z = fp.f32(pz)
        self.facing = int(facing) & 0xFFFF
        if self._core is not None:
            self._core.set_pos(self.pos_x, 0.0, self.pos_z, self.facing)

    def _apply_base(self):
        self.ff.set_pos(self.pos_x, self.pos_z, facing=self.facing)

    def enter_single(self, anim, morf, start=0.0, end=None, rate=1.0):
        """setSingleMoveAnime(anim, rate, start, end, morf) (12794): the under-body switches to a single
        anim (m34C3=0), so posMoveFromFootPos keeps posing the foot + updating the toe stream while m3598
        stays frozen (=> speedF stays the proc's own value: roll/slip momentum, WaitTurn frozen at 0).
        Because m34C3==0, the following walk blend re-inits its frame ctrl to 0 on the proc->MOVE exit.
        Shared by procFrontRoll_init (ANM_ROLLF), procWaitTurn_init (ANM_ROT), procSlip_init (ANM_SLIP);
        call step_single_anim() each proc frame. `end` defaults to the anim's frameMax."""
        if end is None:
            end = float(ANIM_META[anim][0])
        if self._core is not None:
            self.started = True
            self._core.w_enter_single(ANIM_CODE[anim], float(morf) if morf is not None else 0.0,
                                      float(start), float(end), float(rate), morf is not None)
            return
        self.st.set_single(anim, start, end, rate)
        self.started = True
        self._single_entered = True                # entry frame: don't advance the ctrl (matches land)
        self._pending_morf = float(morf) if morf is not None else None

    def enter_roll(self, morf=2.0, start=0.0, end=19.0, rate=1.1):
        """procFrontRoll_init: setSingleMoveAnime(ANM_ROLLF). morf = the roll-entry oldframe-morf
        (mRoll.field_0x14); it decays out long before the exit."""
        self.enter_single('rollf', morf, start, end, rate)

    def step_single_anim(self, nspeed, msd):
        """One single-anim proc frame: advance the anim frame ctrl, pose the foot, run the
        posMoveFromFootPos toe-stream bookkeeping (f31_2, m359C, stored toe). Returns speedF (which the
        caller discards for the momentum/frozen procs). Its real job is warming the toe stream so the
        post-proc walk tail is bit-exact."""
        if self._core is not None:
            return self._core.w_step_single(_f32(nspeed), _f32(msd))
        nspeed = _f32(nspeed)
        msd = _f32(msd)
        morf = self._pending_morf if self._pending_morf is not None else -1.0
        self._pending_morf = None
        if self._single_entered:                   # entry frame: pose at the start frame (no ctrl advance)
            self._single_entered = False
            state = dict(move0=self.st.move0, move1=self.st.move0, f0=self.st.fc0.frame,
                         f1=self.st.fc0.frame, ratio=0.0, m3598=self.st.m3598, morf=False)
        else:
            state = self.st.step_single()
        return self._foot_speedf(nspeed, msd, state, morf)

    # back-compat alias: the roll uses the shared single-anim stepper.
    step_roll = step_single_anim

    def enter_wait_idle(self, ratio, r27_anim, morf, msd):
        """One WAIT idle-proc frame right after a WAIT_TURN pivot (procWait_init/procWait ->
        setBlendMoveAnime idle branch, ModeFlg_00000001, shape_angle.y != m34DE). Poses the
        WAITS/ANM_ATNW{L,R}S turn-step blend (m3598=0) and updates the toe stream so the following
        walk-off entry (its f31_2 = |ATNW pose - the last ROT pose|) is bit-exact. mNormalSpeed is 0
        (WAIT) so speedF/position is 0 this frame; the pose only warms t1. Sets `_pending_morf` so
        the next frame's walk step re-triggers the oldframe-morf (procMove_init on WAIT->MOVE, 6215)."""
        self.started = True
        m = float(morf)
        if self._core is not None:
            return self._core.w_enter_wait_idle(float(ratio), ANIM_CODE[r27_anim], m, _f32(msd))
        self.st.set_wait_idle(ratio, r27_anim, m)
        state = dict(move0=self.st.move0, move1=self.st.move1, f0=self.st.fc0.frame,
                     f1=self.st.fc1.frame, ratio=self.st.ratio, m3598=self.st.m3598, morf=True)
        self._foot_speedf(0.0, _f32(msd), state, m)   # poses ATNW@0, shifts it into the toe stream
        self._pending_morf = m
        return 0.0

    def enter_subjectivity(self, msd, morf=2.4):
        """procSubjectivity_init on-axis (d_a_player_main.cpp:5948) -- the C-up-cancel FREEZE.
        The J3DFrameCtrl advances the walk one frame (actor execute), then setBlendMoveAnime's
        ModeFlg_00000001 idle arm (line 3114) re-poses as
        setMoveAnime(f27=0, f28=H_38, f25=H_40, ANM_WAITS, ANM_WALK, r29=2, field_0xC):
        MOVE0=WAITS (rate 1.1), MOVE1=WALK (rate (1/60)*1.1*32=0.587), m34C3=2, ratio 0, m3598=0,
        phase f31 PRESERVED from the walk (old m34C3=1). mNormalSpeed=0 so speedF/position is frozen;
        the pose warms the toe stream at the carried WAITS phase so the eventual re-walk is bit-exact
        (its f31 is preserved BECAUSE m34C3=2, vs a cold FREE_WAIT walk's m34C3=0 -> f31=0 reset).
        Python-path only (the native fused engine has no subjectivity proc)."""
        if self._core is not None:
            raise NotImplementedError("subjectivity freeze needs the pure-Python foot path (native=False)")
        self.started = True
        msd = _f32(msd)
        m = float(morf) if morf is not None else -1.0
        self.st.fc0.update()                        # actor execute advances the walk ctrl this frame
        self.st.fc1.update()
        self.st._set_move_anime(0.0, H_38, H_40, 'waits', 'walk', 2, m)
        self.st.m3598 = 0.0
        state = dict(move0='waits', move1='walk', f0=self.st.fc0.frame, f1=self.st.fc1.frame,
                     ratio=self.st.ratio, m3598=0.0, morf=(m >= 0.0))
        self._foot_speedf(0.0, msd, state, m)
        return 0.0

    def step_subjectivity(self, msd):
        """One SUBJECTIVITY (or the post-B WAIT) HOLD frame. procSubjectivity only setBodyAngleToCamera,
        so the WAITS/WALK ctrls just advance (no re-pose/remap) and the foot poses at the frozen ratio
        (0 -> pure WAITS). mNormalSpeed=0 -> speedF 0 (position frozen); the pose keeps warming the toe
        stream so the carried phase stays bit-exact when MOVE resumes. Python-path only."""
        if self._core is not None:
            raise NotImplementedError("subjectivity freeze needs the pure-Python foot path (native=False)")
        msd = _f32(msd)
        self.st.fc0.update()
        self.st.fc1.update()
        state = dict(move0=self.st.move0, move1=self.st.move1, f0=self.st.fc0.frame,
                     f1=self.st.fc1.frame, ratio=self.st.ratio, m3598=self.st.m3598, morf=False)
        self._foot_speedf(0.0, msd, state, -1.0)
        return 0.0

    def step_atn(self, nspeed, msd, direction, f31, morf=None):
        """One ATN_MOVE frame (procAtnMove -> setBlendAtnMoveAnime, d_a_player_main.cpp:6249). Advances
        the frame ctrls, poses the ATN strafe/back anim (warming the toe stream for any following MOVE),
        and returns speedF via the same posMoveFromFootPos composition as the walk step. `direction` =
        mDirection (post setBlendAtnMoveAnime update, from LandState); `f31` = |nspeed*cos(gndAngle)|/max.
        `morf` = mBasic.field_0xC (2.4) on ATN entry or a direction change, else None (-1 = no morf)."""
        if self._core is not None:
            self.started = True
            return self._core.w_step_atn(_f32(nspeed), _f32(msd), int(direction), _f32(f31),
                                         float(morf) if morf is not None else 0.0, morf is not None)
        nspeed = _f32(nspeed)
        msd = _f32(msd)
        self.started = True
        m = float(morf) if morf is not None else -1.0
        state = self.st.step_atn(nspeed, direction, _f32(f31), m)
        return self._foot_speedf(nspeed, msd, state, m)

    def _shift(self, cur, f312, msd):
        self.m35B4 = _f32(msd)
        self.t2 = self.t1
        self.t1 = cur
        self.prev_f312 = f312

    def step(self, nspeed, msd, anim_nspeed=None):
        """Advance one frame. `nspeed` = mNormalSpeed (bit-exact from LandState), `msd` =
        mStickDistance (the acted-on/latency-delayed stick magnitude). Returns speedF.

        `anim_nspeed` splits the anim-blend speed from the position-integrating speed for the
        one frame where the game poses the walk anim at a DIFFERENT mNormalSpeed than it later
        integrates position with. This happens at procMoveTurn_init(1): setBlendMoveAnime runs
        (posing at the full pre-turn speed) BEFORE `mNormalSpeed *= 0.5` (6616 vs 6623), and
        posMoveFromFootPos integrates with the halved speed. Default None => same value for both."""
        if self._core is not None:
            return self._core.w_step(_f32(nspeed), _f32(msd),
                                     0.0 if anim_nspeed is None else _f32(anim_nspeed),
                                     anim_nspeed is not None)
        nspeed = _f32(nspeed)
        msd = _f32(msd)
        an = nspeed if anim_nspeed is None else _f32(anim_nspeed)

        if not self.started:
            if nspeed <= 0.0:
                # input-latency / standing frame: keep drawing the idle so its drift is carried
                # into the toe stream; the game's m3598 here is 0 so speedF is 0 regardless.
                self.idle_frame = fp.fadds(self.idle_frame, 1.0)
                self._apply_base()
                cur = self.ff.step_feet(self.idle_anim, self.idle_anim,
                                        self.idle_frame, self.idle_frame, 0.0, -1.0)
                self._shift(cur, 0.0, msd)
                return 0.0
            self.started = True
            morf = 2.4                                # oldframe-morf triggers at walk-proc entry
        elif abs(nspeed) <= 0.001:
            # MOVE exit (speed bled to ~0 -> WAIT): speedF = 0. Gate on |nspeed| not sign -- the EBS runs
            # MOVE at a large NEGATIVE mNormalSpeed and must still integrate the composition below.
            self.stopped = True
            self.m35B4 = msd
            return 0.0
        elif self._pending_morf is not None:
            morf = self._pending_morf                 # roll->walk re-entry: re-trigger oldframe-morf
            self._pending_morf = None
        else:
            morf = -1.0

        state = self.st.step(an)
        return self._foot_speedf(nspeed, msd, state, morf)

    def _foot_speedf(self, nspeed, msd, state, morf):
        """The shared posMoveFromFootPos math (d_a_player_main.cpp:2372+): pose the foot, take the
        1-frame-delayed plant toe delta f31_2 with the recursive smoothing, and compose
        speedF = nspeed*(1-m3598) +/- f31_2*m3598. The plant/delta/smoothing/compose tail runs in C
        (_anmc.foot_compose) when available, else the bit-identical _py_foot_compose. t1 = the toe
        DRAWN last frame (1-frame delay), t2 = the frame before (both flat 12-tuples)."""
        self._apply_base()
        cur = self.ff.step_feet(state['move0'], state['move1'], state['f0'], state['f1'],
                                state['ratio'], i_morf=morf)
        compose = _N.foot_compose if _N is not None else _py_foot_compose
        speedF, f312 = compose(self.t1, self.t2, nspeed, msd, state['m3598'],
                               self.prev_f312, self.m35B4)
        self._shift(cur, f312, msd)
        return speedF
