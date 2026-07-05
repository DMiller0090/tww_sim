#!/usr/bin/env python3
"""land.py - first LAND-movement sim increment: flat-ground walk/run (`procMove`).

Pure-offline transcription of the on-ground locomotion proc, validated bit-exact vs the
live game for `mNormalSpeed` (potential_speed) and the state machine on a flat, wall-free
floor. This is design-note tww-sim-architecture-design.md 10.3 -- the forcing function that
draws the future core/land boundary. Kept minimal INSIDE `superswim/` for now; shared bits
(fp/stick/camera) are still imported from `superswim.sim` rather than pre-extracted (10.2).

Decomp = spec (`tww/src/d/actor/d_a_player_main.cpp`):
  procMove (6221) -> setSpeedAndAngleNormal (2751) -> setNormalSpeedF (2301); stick via
  setStickData (10530). HIO walk constants: d_a_player_HIO_data.inc:8 (see LandState.HIO).

WHAT IS BIT-EXACT vs WHAT IS CALIBRATED (read this before trusting a number)
--------------------------------------------------------------------------
* `mNormalSpeed` (nspeed / potential_speed): BIT-EXACT. The +3.5/frame accel to the cap
  17 and the cLib_addCalc decel 17->14.5->12->9.5->7->4.5->2->0.2->0 fall straight out of
  setSpeedAndAngleNormal + setNormalSpeedF with the shipped HIO constants (0 fitting).
* state machine (FREE_WAIT 5 -> MOVE 6 -> WAIT 4) and the two angles: reproduced.
* `speedF` (true_speed) and hence POSITION: BIT-EXACT (float, ~1e-5) when the anim engine is
  available. On land the real speedF is foot-plant/animation driven -- posMoveFromFootPos (2353)
  reads the walk anim's foot-joint matrices -- so it needs the ported J3D animation runtime
  (superswim.anim: the BCK keyframe eval + reduced foot-chain FK + two-anim blend + oldframe-morf,
  all FMA-faithful). superswim.anim.foot_speedf.FootSpeedF is that chain; LandState drives it each
  frame and it reproduces speedF to ~1e-5 across accel/cruise/decel INCLUDING the standing->walk
  entry and the stop. Its keyframe DATA (Link.arc/LkAnm.arc) is copyrighted and gitignored under
  _generated/anim/, so it is dev-supplied: when absent, speedF FALLS BACK to a calibrated cLib
  chase toward mNormalSpeed (SPEEDF_CHASE below), matching the END position within +-3 and locked
  at steady state. => nspeed/state/angles are ULP-exact always; position is ~1e-5 with the anim
  data present, a +-3 model without it.

INPUT LATENCY: the game acts on the stick delivered 2 frames earlier (INPUT_DELAY). This one
constant reproduces BOTH observed edges: forward accel starts on the 3rd up-frame and the
release decel starts on the 3rd neutral-frame (live land_walk_gt.csv).
"""
from __future__ import annotations
import math
from ..core import mathlib as S
from ..core.mathlib import f32, cLib_addCalc, cM_scos_s16, deg_to_s16, s16_signed, _deadzone, stick_angle_deg
from ..core.camera import CameraManual, LAND_SCALE

# link_state / daPyProc values (d_a_player_main.h). Walk trio + the targeting-move proc.
SUBJECTIVITY = 1  # daPyProc_SUBJECTIVITY_e (first-person view; the C-up-cancel FREEZE: mNormalSpeed=0)
WAIT = 4          # daPyProc_WAIT_e         (idle standstill)
FREE_WAIT = 5     # daPyProc_FREE_WAIT_e    (anchor's resting proc)
MOVE = 6          # daPyProc_MOVE_e         (ground locomotion)
ATN_MOVE = 7      # daPyProc_ATN_MOVE_e     (targeting move: brakeslide / L-held slide)
WAIT_TURN = 23    # daPyProc_WAIT_TURN_e    (pivot-in-place reversal from a standstill)
MOVE_TURN = 24    # daPyProc_MOVE_TURN_e    (turn-around reversal, low speed / post-slip)
SLIP = 25         # daPyProc_SLIP_e         (high-speed reversal skid, hands to MOVE_TURN)
FRONT_ROLL = 30   # daPyProc_FRONT_ROLL_e   (A-button forward roll)
# Targeted ballistic hops (L-held + A + directional stick -> doStatus JUMP). Pure momentum + gravity,
# no foot-plant (m3598==0), so position is scalar-exact without the anim engine. See land-movement.md.
SIDE_STEP = 0x0A       # daPyProc_SIDE_STEP_e       (sidehop: stick L/R while targeting)
SIDE_STEP_LAND = 0x0B  # daPyProc_SIDE_STEP_LAND_e  (sidehop recovery -> WAIT)
BACK_JUMP = 0x22       # daPyProc_BACK_JUMP_e       (backflip: stick back while targeting)
BACK_JUMP_LAND = 0x23  # daPyProc_BACK_JUMP_LAND_e  (backflip recovery -> WAIT)

_STATE_TAG = {MOVE: "MOVE", ATN_MOVE: "ATN", FRONT_ROLL: "ROLL", WAIT_TURN: "WAITTURN",
              MOVE_TURN: "MOVETURN", SLIP: "SLIP", WAIT: "WAIT", FREE_WAIT: "WAIT",
              SIDE_STEP: "SIDEHOP", SIDE_STEP_LAND: "SIDEHOPLAND",
              BACK_JUMP: "BACKFLIP", BACK_JUMP_LAND: "BACKFLIPLAND"}

# mDirection enum (d_a_player_main.h daPy_lk_c::direction_e). getDirectionFromAngle buckets the
# stick-vs-heading angle into these; ATN physics branches on it (fwd->Normal, back->AtnBack, side).
DIR_FORWARD = 0
DIR_BACKWARD = 1
DIR_LEFT = 2
DIR_RIGHT = 3
DIR_NONE = 4

# Frames of controller-input latency: physics at frame f acts on the stick from frame f-2.
INPUT_DELAY = 2

# speedF->pos FALLBACK: calibrated cLib chase toward mNormalSpeed, used only when the anim engine
# (superswim.anim.foot_speedf) lacks keyframe data (endpoint +-3). With data, speedF is bit-exact.
SPEEDF_CHASE = (0.5, 2.0, 1.4)   # (scale, maxStep, minStep) fit vs land_walk_gt.csv

# Standing-idle FREEB frame-controller value at the land_flatwalk anchor (mFrameCtrlUnder[0]). It
# sets the entry idle-drift phase for the anim engine; seed it from live for other anchors.
DEFAULT_IDLE_FRAME = 70.0


def cLib_addCalcAngleS(value, target, scale, max_step, min_step):
    """Faithful cLib_addCalcAngleS (c_lib.cpp:160), s16 integer math. Chase an s16 `value`
    toward `target` by diff/scale, clamped to +-max_step, else snap by +-min_step without
    overshoot. Returns the new value (the decomp mutates in place + returns the residual).
    All arithmetic is s16-wrapping like the game (diff = target - value as s16)."""
    value &= 0xFFFF
    target &= 0xFFFF
    if value == target:
        return value
    diff = s16_signed(target - value)
    step = int(diff / scale)                 # C integer division (truncate toward zero)
    if step > min_step or step < -min_step:
        if step > max_step:
            step = max_step
        if step < -max_step:
            step = -max_step
        return (value + step) & 0xFFFF
    if diff >= 0:
        nv = (value + min_step) & 0xFFFF
        return target if s16_signed(target - nv) <= 0 else nv
    else:
        nv = (value - min_step) & 0xFFFF
        return target if s16_signed(target - nv) >= 0 else nv


class LandState:
    """One Link on flat, wall-free ground, stepped frame by frame. The land analogue of
    SwimState. Carries the two-angle model first-class (travel = current.angle.y velocity
    direction; facing = shape_angle.y visual body direction) even though the on-axis walk
    keeps them fused -- the brakeslide/EBS tiers exercise the split.

    Seed from a live frame-0 snapshot (pos_z, angles, csangle) exactly like run_tests seeds
    SwimState. Step with raw sticks; csangle is a per-frame input (default 0 = free-cam ref).
    """
    # HIO m_HIO->mMove walk constants (d_a_player_HIO_data.inc:8; normal play never mutates
    # HIO, so these are shipped literals, no live dump). See design-note 5b table.
    MAX_NSPEED = f32(17.0)          # mMaxNormalSpeed (= mMove.field_0x18)
    F0 = 3000                       # base angle-turn rate (param_1 to setSpeedAndAngleNormal)
    F4 = 100                        # angle-approach max-delta (cLib_addCalcAngleS clamp)
    F6 = 5                          # angle-approach scale/mode arg
    F14 = f32(3.5)                  # target-speed scale (dVar9 *= field_0x14 * dist^2)
    F1C = f32(2.5)                  # accel rate -> setNormalSpeedF param_3 (cLib maxStep)
    F20 = f32(1.8)                  # decel rate -> setNormalSpeedF param_4 (cLib minStep)
    F24 = f32(0.6)                  # speed cLib scale -> setNormalSpeedF param_2

    # HIO mAtnMove (targeting-move) constants (d_a_player_HIO_data.inc:14, offsets per
    # daPy_HIO_atnMove_c1). Used by setSpeedAndAngleAtn side branch + the DIR_FORWARD->Normal cap.
    ATN_MAX = f32(12.0)             # field_0xC  = mMaxNormalSpeed under attention lock
    ATN_TURN_MAX = 3000             # field_0x0  = travel-chase max step (s16)
    ATN_TURN_MIN = 2000             # field_0x2  = travel-chase min step (s16)
    ATN_TURN_SCALE = 6              # field_0x4  = travel-chase scale (s16)
    ATN_SPD = f32(5.0)             # field_0x8  = target-speed scale (fVar2 = *msd*cos)
    ATN_ACC = f32(7.5)             # field_0x10 = setNormalSpeedF maxStep
    ATN_DEC = f32(4.0)             # field_0x14 = setNormalSpeedF minStep
    ATN_SCL = f32(0.5)             # field_0x18 = setNormalSpeedF cLib scale
    # HIO mAtnMoveB (targeting-move BACKWARD) constants, d_a_player_HIO_data.inc:18. The
    # steady-state brakeslide runs here (facing locked, travel ~180, speed negative bleeding up).
    ATNB_MAX = f32(15.0)            # field_0xC  = mMaxNormalSpeed when DIR_BACKWARD
    ATNB_SPD = f32(2.5)             # field_0x8  = target-speed scale
    ATNB_ACC = f32(8.0)             # field_0x10 = setNormalSpeedF maxStep
    ATNB_DEC = f32(2.0)             # field_0x14 = setNormalSpeedF minStep
    ATNB_SCL = f32(0.5)             # field_0x18 = setNormalSpeedF cLib scale
    ATNB_COS_FWD = f32(0.99)        # field_0x2C = cos(travel-facing) >= this -> DIR_FORWARD
    ATNB_COS_BACK = f32(-0.99)      # field_0x30 = cos(travel-facing) <= this -> DIR_BACKWARD

    # HIO mRoll (forward roll) constants, d_a_player_HIO_data.inc:97 (daPy_HIO_roll_c1). The roll
    # speed is set ONCE at entry from the pre-roll speedF; the anim frame ctrl (ANM_ROLLF) times it.
    ROLL_SPD = f32(1.5)             # field_0x18 = speedF multiplier
    ROLL_ADD = f32(0.5)             # field_0x1C = base add
    ROLL_MIN = f32(5.0)             # field_0x20 = speed floor (standstill roll) + neutral-exit -= this
    ROLL_END = f32(19.0)            # field_0x0 = ANM_ROLLF end frame; anim completes (rate->0) here
    ROLL_RATE = f32(1.1)            # field_0x8 = ANM_ROLLF frame-ctrl rate (mFrameCtrlUnder[MOVE0])
    ROLL_ENTRY_MORF = 2.0           # field_0x14 = setSingleMoveAnime i_morf at roll entry
    MOVE_REENTRY_MORF = 2.4         # mBasic.field_0xC = procMove_init setBlendMoveAnime morf (roll->walk)
    ROLL_EARLY = f32(17.0)          # field_0x10 = getFrame()>this -> checkNextMode(1) moving-stick exit
    # (with a neutral stick checkNextMode(1) is inert -- 4457 returns false when msd<=0.05 and no action
    # button -- so a neutral roll runs to ROLL_END; a held stick exits one frame early, e.g. the roll-EBS.)

    # HIO mTurn (ground reversal turns), d_a_player_HIO_data.inc:22. WaitTurn pivots facing toward the
    # captured stick target; the min step (0x1F40) dominates -> ~8000/frame. (MoveTurn sweep: see its init.)
    TURN_MAX = 0x3CDF               # field_0x0 = cLib_addCalcAngleS max step (WaitTurn facing pivot)
    TURN_MIN = 0x1F40               # field_0x2 = min step
    TURN_SCALE = 30                 # field_0x4 = scale (diff/scale; << min so the min step rules)
    WAIT_TURN_ANIM_RATE = f32(1.0)  # mBasic.field_0x4 = ANM_ROT frame-ctrl rate (pivot pose)
    # HIO mSlip (high-speed reversal skid), d_a_player_HIO_data.inc:106 (daPy_HIO_slip_c1). Entry from a
    # MOVE frame whose speedF/mMaxNormalSpeed exceeds the threshold AND the stick genuinely flipped.
    SLIP_THRESH = f32(0.6)          # field_0x4 = speedF/mMaxNormalSpeed slip-entry threshold
    SLIP_ENTRY = f32(1.1)           # field_0x8 = entry-speed multiplier (mNormalSpeed = speedF * this)
    SLIP_DEC_SCALE = f32(0.6)       # field_0x18 = cLib_addCalc decel scale
    SLIP_DEC_MAX = f32(1.25)        # field_0x10 = cLib_addCalc decel maxStep (~-1.25/frame skid bleed)
    SLIP_DEC_MIN = f32(0.1875)      # field_0x14 = cLib_addCalc decel minStep
    SLIP_ANIM_RATE = f32(0.4)       # field_0xC = ANM_SLIP frame-ctrl rate (skid pose)
    SLIP_MORF = f32(1.7)            # field_0x1C = ANM_SLIP setSingleMoveAnime oldframe-morf
    # MoveTurn slip-exit re-accel seed = mMaxNormalSpeed * this (procSlip 6666); shape nudge = 0x100.
    MT_SLIP_SEED = f32(0.5)

    # HIO mSideStep (targeted sidehop), d_a_player_HIO_data.inc:223. Ballistic launch perp to facing;
    # lands on the first ground-hit frame. Mechanics: knowledge/mechanics/land-movement.md.
    SIDESTEP_ANGLE = 6200          # field_0x2 = s16 launch angle (fed to cM_scos/cM_ssin, >>4 table)
    SIDESTEP_SPEED = f32(30.0)     # field_0x8 = launch speed magnitude
    SIDESTEP_GRAV = f32(-2.4)      # field_0x18 = gravity per frame
    SIDESTEP_LAND_END = f32(5.0)   # field_0x6 = land anim end frame (recovery duration)
    SIDESTEP_LAND_RATE = f32(0.85) # field_0x1C = land anim frame-ctrl rate
    # HIO mBackJump (targeted backflip), d_a_player_HIO_data.inc:102. Ballistic backward launch; lands
    # once ground-hit AND the ROLLB anim finishes. Mechanics: knowledge/mechanics/land-movement.md.
    BACKJUMP_SPEED = f32(22.5)     # field_0x10 = mNormalSpeed (backward horizontal)
    BACKJUMP_VY = f32(19.0)        # field_0x14 = speed.y launch
    BACKJUMP_GRAV = f32(-3.0)      # field_0x18 = gravity per frame
    BACKJUMP_ANIM_START = f32(2.0) # field_0x8 = ROLLB frame-ctrl start
    BACKJUMP_ANIM_END = f32(11.0)  # field_0x0 = ROLLB frame-ctrl end (getRate()<0.01 gates the land)
    BACKJUMP_ANIM_RATE = f32(0.8)  # field_0x4 = ROLLB frame-ctrl rate
    BACKJUMP_LAND_END = f32(5.0)   # field_0x2 = land anim end frame (recovery duration)
    BACKJUMP_LAND_RATE = f32(0.8)  # field_0x24 = land anim frame-ctrl rate
    # Terminal fall velocity (mAutoJump.field_0x10 global default, d_a_player_HIO_data.inc:116): speed.y
    # is clamped to this after gravity each frame (posMoveFromFootPos 2472). Never reached on a flat hop.
    MAX_FALL = f32(-175.0)

    def __init__(self, pos_z=764.079, pos_x=0.0, facing=0, travel=0, csangle=0,
                 state=FREE_WAIT, nspeed=0.0, speedF=0.0, idle_frame=DEFAULT_IDLE_FRAME,
                 use_anim=True, cam_scale=LAND_SCALE, pos_y=0.0, native=True, foot_native=True):
        self.pos_x = float(pos_x)
        self.pos_z = float(pos_z)
        # Vertical state for the ballistic hops. pos_y accumulates in f32; ground_y = the jump-entry
        # height. Seed pos_y from live for a bit-exact airtime (the vertical rounding is magnitude-dependent).
        self.pos_y = f32(pos_y)
        self.speed_y = 0.0             # speed.y (integrated by gravity while airborne)
        self.gravity = 0.0             # per-proc gravity (set at hop entry)
        self.ground_y = f32(pos_y)     # m3688.y flat landing height (reset at hop entry)
        self.ground_hit = True         # mAcch GROUND_HIT (grounded at rest); re-derived each air frame
        self.air_anim = 0.0            # ROLLB frame ctrl during BACK_JUMP (gates the land) / land recovery
        self.facing = int(facing) & 0xFFFF     # shape_angle.y (s16)
        self.travel = int(travel) & 0xFFFF     # current.angle.y (s16)
        self.csangle = int(csangle) & 0xFFFF   # dCam_getControledAngleY (s16); set each frame from _cam
        # LAND camera (predict.CameraManual = dCamera_c::manualCamera, bit-exact); centered C-stick
        # -> frozen. cam_scale = styleParam[24] deg/frame (MM83 land=8.0). See camera.md.
        self._cam = CameraManual(csangle=self.csangle, scale=cam_scale)
        self.target = 0                        # m34E8 (s16), set each frame by setStickData
        self.m34dc = int(facing) & 0xFFFF      # stick want-angle pre-csangle (m34E8 = m34dc + csangle)
        self.m34ea = int(facing) & 0xFFFF      # PREVIOUS frame's m34dc (slip stick-flip detector, 11289)
        self.m34de = int(facing) & 0xFFFF      # PREVIOUS frame's shape_angle.y (11287; WAIT idle-anim turn-step)
        self.state = int(state)                # link_state / mCurProc
        self.nspeed = f32(nspeed)              # mNormalSpeed (potential_speed) -- bit-exact
        self.speedF = f32(speedF)              # position-integrating speed
        self.msd = 0.0                         # mStickDistance
        self.max_nspeed = f32(self.MAX_NSPEED) # mMaxNormalSpeed (switches 17/15/12 under ATN)
        self.direction = DIR_NONE              # mDirection (ATN physics branch selector)
        self.m34E6 = int(facing) & 0xFFFF      # facing lock captured on attention-lock engage
        self._l_prev = False                   # attention-lock (L) held last frame (rising edge)
        self.visited = set()                   # every proc state this run passed through (path assertions)
        self.roll_frame = 0.0                  # ANM_ROLLF frame ctrl during FRONT_ROLL (times the exit)
        self._roll_entered = False             # entry frame: don't advance the anim ctrl yet
        self.turn_target = 0                   # mProcVar2.m34D4 (WaitTurn facing-pivot target)
        self.turn_shape_scale = 0              # MoveTurn shape-sweep cLib params (m34D0/m34D4/m34D6)
        self.turn_shape_max = 0
        self.turn_shape_min = 0
        self._anim_nspeed = None               # 1-frame anim/integrate speed split (procMoveTurn_init halving)
        self._pos_fallback = False             # a turn proc (ANM_ROT/SLIP/turn-blend unported) was entered
        #                                        -> position uses the calibrated chase, not asserted bit-exact
        # 2-frame controller-input buffer (index 0 = oldest = the input acted on this frame).
        # Tuple = (stickX, stickY, buttons, triggerL, csx, csy) -- L/target AND the C-stick are
        # delivered through the same controller pipe, so all are delayed like the main stick.
        self._inbuf = [(128, 128, 0, 0, 128, 128)] * INPUT_DELAY
        # Anim-driven speedF: the ported posMoveFromFootPos chain (bit-exact position). None when
        # disabled or the keyframe data is absent -> fall back to the SPEEDF_CHASE stand-in.
        self._foot = None
        if use_anim:
            try:
                from ..core.anim.foot_speedf import FootSpeedF
                self._foot = FootSpeedF(idle_frame=float(idle_frame), pos_x=self.pos_x,
                                        pos_z=self.pos_z, facing=self.facing, native=foot_native)
            except (FileNotFoundError, OSError, ImportError):
                self._foot = None
        # Native land physics: when the fused C engine is present, the whole per-frame step runs in one
        # LandCore call (delegated below); absent -> the bit-identical pure-Python body. See fp-faithfulness.md.
        # `native=False` forces the Python path (still bit-exact via `_foot`) -- REQUIRED for the ballistic
        # hops (sidehop/backflip), which the C twin does not yet implement. The setup finder uses it.
        self._core = self._build_core() if native else None

    def _build_core(self):
        """Build the native LandCore over the fused PoseEngine, seeded from this LandState's current
        (rest) fields. Returns None when the fused engine is absent -> the Python step path is used."""
        foot = self._foot
        if foot is None or getattr(foot, "_core", None) is None:
            return None
        from ..core.anim import _anmc as _N
        _N.land_init_consts(_LAND_CONSTS)
        core = _N.LandCore()
        core.setup(foot._core, self.pos_x, self.pos_z, self.facing, self.travel,
                   self.csangle, self.state, self.nspeed, self.speedF, float(self._cam.scale))
        return core

    def clone(self):
        s = LandState.__new__(LandState)
        s.__dict__.update(self.__dict__)
        s._inbuf = list(self._inbuf)
        s._cam = self._cam.clone()          # s16-integer camera: clone so A* nodes never alias one
        # State-copy the stateful anim engine so the clone continues BIT-EXACTLY even MID-WALK (the
        # old path rebuilt fresh at rest, valid only pre-walk). FootSpeedF.clone carries the toe stream.
        if self._foot is not None:
            s._foot = self._foot.clone()
        # The native LandCore aliases the SAME PoseEngine as the clone's _foot; copy its physics +
        # camera state over that state-copied engine (was rebuilt fresh -> mid-walk anim was lost).
        if self._core is not None and s._foot is not None and getattr(s._foot, "_core", None) is not None:
            s._core = self._core.clone(s._foot._core)
        else:
            s._core = None
        return s

    def _sync_from_core(self):
        """Copy the LandCore's post-step public fields back onto this LandState (for tests/planners
        reading pos/state/etc.) and record the visited proc."""
        c = self._core
        self.pos_x = c.pos_x
        self.pos_z = c.pos_z
        self.facing = c.facing
        self.travel = c.travel
        self.csangle = c.csangle
        self.state = c.state
        self.nspeed = c.nspeed
        self.speedF = c.speedF
        self.msd = c.msd
        self.max_nspeed = c.max_nspeed
        self.direction = c.direction
        self.visited.add(self.state)

    # --- stick layer (setStickData, 10530) -------------------------------------------------
    def _set_stick_data(self, sx, sy):
        """mStickDistance + m34E8 world target from a raw stick. mStickDistance uses the /54
        deadzoned magnitude (PADClamp / JUTGamePad CStick), capped at 1. m34E8 = m34DC(stick)
        + csangle, with m34DC = stickAngle + 0x8000 (up = away = forward)."""
        self.msd = min(math.hypot(_deadzone(sx), _deadzone(sy)) / 54.0, 1.0)
        sa = stick_angle_deg(sx, sy)            # decomp convention: 0=down .. 180=up
        if sa is None:
            self.target = self.travel           # neutral: no want -> hold (irrelevant, gated)
        else:
            self.m34dc = (deg_to_s16(sa) + 0x8000) & 0xFFFF
            self.target = (self.m34dc + self.csangle) & 0xFFFF

    # --- setNormalSpeedF (2301), walk path -------------------------------------------------
    def _set_normal_speed_f(self, param_1, param_2, param_3, param_4):
        """The accel/decel integrator. Flat wall-free ground => no event/heavy/grab (dVar10 =
        msd * (max*msd)), no slide polygon, no wall deflect. dVar10 is the speed cap this
        frame; below it the cLib_addCalc chases up (param_1 injects the accel step directly),
        above it (release) it cLib-decays down."""
        dVar10 = f32(self.msd * f32(self.max_nspeed * self.msd))   # target/cap speed
        if dVar10 < self.nspeed:                # decelerating toward the (lower) cap
            temp_f0 = f32(self.nspeed - dVar10)
            temp_f3 = param_3 if temp_f0 > param_3 else temp_f0
            if temp_f3 < param_4:
                temp_f3 = param_4
            param_1 = 0.0
            dVar6 = dVar10
        else:
            temp_f3 = param_3
            dVar6 = 0.0
        if not _is_zero(param_1):               # accel: inject dVar9 straight in, clamp to cap
            self.nspeed = f32(self.nspeed + param_1)
            if self.nspeed > dVar10:
                self.nspeed = dVar10
        else:                                   # cLib chase toward dVar6 (0 on release)
            self.nspeed = cLib_addCalc(self.nspeed, dVar6, param_2, temp_f3, param_4)

    # --- setSpeedAndAngleNormal (2751), walk path ------------------------------------------
    def _set_speed_and_angle_normal(self, param_1, attention_lock=False):
        """Compute the target-speed scalar dVar9 from the stick + the facing/travel-vs-target
        angle, chase the two angles toward m34E8, then hand dVar9 to setNormalSpeedF. Walk
        path (+ the ATN DIR_FORWARD sub-case). The near-reversal branch (2763) and the facing
        chase (2834) are both guarded by !checkAttentionLock() in the decomp, so `attention_lock`
        (L held) suppresses them -- the ATN-forward call keeps facing frozen (set by the caller
        to m34E6) and never takes the reversal/slip branch. No MOVE_TURN/event/heavy/grab."""
        if self.msd > 0.05:
            bVar2 = False
            dVar11 = f32(self.msd * self.msd)
            # >0x7800 near-reversal branch (2763), skipped under attention lock or during MOVE_TURN.
            if (not attention_lock and _dist_angle_s(self.target, self.travel) > 0x7800
                    and self.state != MOVE_TURN):
                # ModeFlg_00000001 (WAIT/FREE_WAIT/WAIT_TURN): a reversal is INERT while idle -- return
                # with speed/angles untouched so checkNextMode sees the full reversal -> procWaitTurn (2766).
                if self.state in (WAIT, FREE_WAIT, WAIT_TURN):
                    return
                if self.state == MOVE:
                    sp_ratio = f32(self.speedF / self.max_nspeed)
                    # fast + a genuine stick flip -> leave everything for checkNextMode -> procSlip (2770).
                    if (sp_ratio > self.SLIP_THRESH
                            and self._get_dir_from_angle(s16_signed(self.m34ea - self.m34dc)) == DIR_BACKWARD):
                        return
                    # slow -> chase travel toward the reverse (dropping the dist below 0x7800) and
                    # return; checkNextMode then routes via the DIR_BACKWARD branch -> procMoveTurn (2775).
                    if sp_ratio <= self.SLIP_THRESH:
                        self.travel = cLib_addCalcAngleS(self.travel, self.target, self.F6, param_1, self.F4)
                        return
                    bVar2 = True             # fast + not a flip: skip the speed scale, keep sliding
                else:
                    self.travel = cLib_addCalcAngleS(self.travel, self.target, self.F6, param_1, self.F4)
            else:
                # sVar6/sVar7 are s16 = (f32 product) truncated (decomp 2792/2796): quantize before
                # int() -- an f64 product can truncate 1 unit off at a boundary, drifting the travel angle.
                sVar6 = int(f32(param_1 * dVar11))
                if sVar6 < 10:
                    sVar6 = 10
                sVar7 = int(f32(self.F4 * dVar11))
                if sVar7 < 1:
                    sVar7 = 1
                self.travel = cLib_addCalcAngleS(self.travel, self.target, self.F6, sVar6, sVar7)
            if not bVar2:
                dVar9 = cM_scos_s16(s16_signed(self.target - self.travel))
                if self.nspeed > f32(0.5 * self.max_nspeed):
                    if dVar9 < 0.7:
                        dVar9 = f32(0.7)
                elif dVar9 < 0.0:
                    dVar9 = 0.0
                dVar10 = f32(0.5 - f32(0.5 * abs(f32(self.nspeed / self.max_nspeed))))
                if self.msd > dVar10:
                    dVar9 = f32(dVar9 * f32(self.F14 * dVar11))
                else:
                    dVar9 = 0.0
        else:
            dVar9 = 0.0
        # facing (shape_angle.y) chases m34E8 at DOUBLE the travel rate (<<1); if the chase
        # crosses travel it snaps onto it. On-axis walk: no-op. Skipped under attention lock
        # (facing is frozen to m34E6 by the ATN caller) and during MOVE_TURN (its own body sweeps
        # facing toward travel instead). (2834-2845)
        if not attention_lock and self.state != MOVE_TURN and self.msd > 0.05:
            sVar6 = self.facing
            self.facing = cLib_addCalcAngleS(self.facing, self.target, self.F6,
                                             (param_1 << 1) & 0xFFFF, (self.F4 << 1) & 0xFFFF)
            temp = s16_signed(sVar6 - self.travel)
            temp2 = s16_signed(self.facing - self.travel)
            if temp * temp2 <= 0:
                self.facing = self.travel
        self._set_normal_speed_f(dVar9, self.F24, self.F1C, self.F20)

    # --- setSpeedAndAngleAtn (2851): the targeting-move dispatch ----------------------------
    def _get_dir_from_angle(self, angle):
        """getDirectionFromAngle (2278): bucket a signed s16 heading delta into a direction."""
        a = s16_signed(angle)
        if abs(a) > 0x6000:
            return DIR_BACKWARD
        if a >= 0x2000:
            return DIR_LEFT
        if a <= -0x2000:
            return DIR_RIGHT
        return DIR_FORWARD

    def _set_speed_and_angle_atn(self):
        """procAtnMove speed/angle. Branches on mDirection: FORWARD reuses the Normal walk path
        (with attention lock -> facing frozen); BACKWARD is the steady brakeslide (setSpeedAndAngleAtnBack,
        mAtnMoveB constants); the side branch chases travel toward the stick and snaps facing to the
        captured lock m34E6. The BACKWARD-flip (getDirectionFromCurrentAngle) reflects travel by 0x8000
        and negates mNormalSpeed so a backward slide is represented as a negative speed on a flipped
        heading -- the sign convention that makes the brake a slow positive accel toward 0. (2851)"""
        if self.direction == DIR_FORWARD:
            return self._set_speed_and_angle_normal(self.F0, attention_lock=True)
        if self.direction == DIR_BACKWARD:
            return self._set_speed_and_angle_atn_back()
        # side (DIR_LEFT / DIR_RIGHT)
        if self.msd > 0.05:
            if self._get_dir_from_angle(self.target - self.travel) == DIR_BACKWARD:
                self.travel = (self.travel + 0x8000) & 0xFFFF
                self.nspeed = f32(self.nspeed * -1.0)
            old = self.travel
            self.travel = cLib_addCalcAngleS(self.travel, self.target, self.ATN_TURN_SCALE,
                                             self.ATN_TURN_MAX, self.ATN_TURN_MIN)
            fVar2 = f32(f32(self.ATN_SPD * self.msd) * cM_scos_s16(s16_signed(self.travel - old)))
        else:
            fVar2 = 0.0
        self.facing = self.m34E6                 # shape_angle.y = m34E6 (facing lock)
        self._set_normal_speed_f(fVar2, self.ATN_SCL, self.ATN_ACC, self.ATN_DEC)

    def _set_speed_and_angle_atn_back(self):
        """setSpeedAndAngleAtnBack (2882): the steady brakeslide. Same shape as the side branch
        but with the mAtnMoveB constants (cap 15, speed scale 2.5, cLib 0.5/8.0/2.0). Facing stays
        locked at m34E6; travel chases the (backward) stick target; the negative speed bleeds toward
        0 via the accel-inject branch of setNormalSpeedF (~-0.14/frame observed)."""
        if self.msd > 0.05:
            if self._get_dir_from_angle(self.target - self.travel) == DIR_BACKWARD:
                self.travel = (self.travel + 0x8000) & 0xFFFF
                self.nspeed = f32(self.nspeed * -1.0)
            old = self.travel
            self.travel = cLib_addCalcAngleS(self.travel, self.target, self.ATN_TURN_SCALE,
                                             self.ATN_TURN_MAX, self.ATN_TURN_MIN)
            f1 = f32(f32(self.ATNB_SPD * self.msd) * cM_scos_s16(s16_signed(self.travel - old)))
        else:
            f1 = 0.0
        self.facing = self.m34E6
        self._set_normal_speed_f(f1, self.ATNB_SCL, self.ATNB_ACC, self.ATNB_DEC)

    def _update_atn_direction(self):
        """setBlendAtnMoveAnime's mDirection state machine (3280), the flat/no-lock-on subset.
        Runs AFTER checkNextMode each ATN frame (and at ATN entry) to pick next frame's direction
        from cos/sin(travel - facing): within ~8deg of facing -> FORWARD, of the opposite -> BACKWARD,
        else a side (sin sign). Also sets mMaxNormalSpeed for the chosen direction (17/15/12)."""
        iVar6 = s16_signed(self.travel - self.facing)   # current.angle.y - shape_angle.y
        f2 = _cM_ssin_s16(iVar6)
        fVar4 = S.cM_scos_s16(iVar6)
        uVar1 = self.direction
        if self.msd > 0.05:
            if fVar4 <= self.ATNB_COS_BACK or fVar4 >= self.ATNB_COS_FWD:
                self.direction = DIR_BACKWARD if fVar4 <= self.ATNB_COS_BACK else DIR_FORWARD
            else:
                if uVar1 in (DIR_BACKWARD, DIR_FORWARD):
                    self.direction = DIR_RIGHT
                    self.max_nspeed = self.ATN_MAX
                if f2 > 0.0:
                    self.direction = DIR_LEFT
                elif f2 < 0.0:
                    self.direction = DIR_RIGHT
        if self.direction == DIR_BACKWARD:
            self.max_nspeed = self.ATNB_MAX
        elif self.direction == DIR_FORWARD:
            self.max_nspeed = f32(self.MAX_NSPEED)
        elif self.direction not in (DIR_RIGHT, DIR_LEFT):
            self.direction = DIR_RIGHT

    def _check_next_mode(self, l_held):
        """checkNextMode (4424) transition arbiter, flat/no-enemy subset: sets mMaxNormalSpeed from
        the attention state, then picks next frame's proc. r24 (L held) -> ATN_MOVE while moving,
        WAIT when stopped. The non-attention branch (4483) is the full ground-reversal machine:
          * stopped + >0x7800 stick reversal -> procWaitTurn (pivot in place)
          * already MOVE_TURN with facing!=travel -> stay MOVE_TURN (init is a no-op, 6612)
          * moving + >0x7800 reversal -> procSlip (fast + genuine stick flip) else procMoveTurn(1)
          * moving + the (post-travel-chase) heading now reads BACKWARD -> procMoveTurn(1)
          * otherwise procMove.
        The reversal-branch travel chase in setSpeedAndAngleNormal runs BEFORE this, so a slow MOVE
        reversal arrives here already below 0x7800 and routes via the DIR_BACKWARD branch instead."""
        cur = self.state                                  # mCurProc (dispatch-time proc)
        if l_held:                                        # r24: checkAttentionLock (no lock-on actor)
            self.max_nspeed = self.ATN_MAX
            self.state = WAIT if abs(self.nspeed) <= 0.001 else ATN_MOVE
            return
        self.max_nspeed = f32(self.MAX_NSPEED)
        self.direction = DIR_NONE
        dist = _dist_angle_s(self.target, self.travel)
        if abs(self.nspeed) <= 0.001:
            if dist > 0x7800 and self.msd > 0.05:
                self._proc_wait_turn_init()
            else:
                # changeWaitProc -> procWait_init: a no-op while already idle (FREE_WAIT keeps
                # playing its rest anim, 6062), so a resting stand stays FREE_WAIT rather than WAIT.
                self.state = self.state if self.state in (WAIT, FREE_WAIT) else WAIT
        elif cur == MOVE_TURN and self.travel != self.facing:
            self.state = MOVE_TURN                        # procMoveTurn_init(0) no-op: keep sweeping
        elif dist > 0x7800 and self.msd > 0.05:
            if (f32(self.speedF / self.max_nspeed) > self.SLIP_THRESH
                    and self._get_dir_from_angle(s16_signed(self.m34ea - self.m34dc)) == DIR_BACKWARD):
                self._proc_slip_init()
            else:
                self._proc_move_turn_init(1)
        elif (self._get_dir_from_angle(s16_signed(self.target - self.travel)) == DIR_BACKWARD
              and self.msd > 0.05):
            self._proc_move_turn_init(1)                  # getDirectionFromCurrentAngle == BACKWARD
        else:
            self.state = MOVE

    # --- roll (procFrontRoll_init 6817 / procFrontRoll 6851) -------------------------------
    def _roll_init(self):
        """A-button forward roll entry. Speed is set ONCE from the pre-roll speedF (true_speed):
        clamp(speedF*1.5 + 0.5, 5.0, cap) where cap = 0.5 + mMaxNormalSpeed*1.5 = 26. Facing snaps
        to the stick target (shape_angle.y = m34E8, set by the caller when moving), and travel
        follows facing (current.angle.y = shape_angle.y, 6837). Anim frame ctrl starts at 0."""
        v = f32(f32(self.speedF * self.ROLL_SPD) + self.ROLL_ADD)
        if v < self.ROLL_MIN:
            v = f32(self.ROLL_MIN)
        else:
            cap = f32(self.ROLL_ADD + f32(self.MAX_NSPEED * self.ROLL_SPD))
            if v > cap:
                v = cap
        self.nspeed = v
        self.facing = self.target                # shape_angle.y = m34E8 (already snapped when moving)
        self.travel = self.facing                # current.angle.y = shape_angle.y (6837)
        self.state = FRONT_ROLL
        self.roll_frame = 0.0
        self._roll_entered = True
        # setSingleMoveAnime(ANM_ROLLF, ...): the foot engine poses rollf through the roll (m34C3=0)
        # so the toe stream is warm for the post-roll walk tail. morf = mRoll.field_0x14 = 2.0.
        if self._foot is not None:
            self._foot.enter_roll(morf=self.ROLL_ENTRY_MORF)

    def _proc_roll(self, l_held):
        """One FRONT_ROLL frame (procFrontRoll 6851): speed is constant momentum (position uses
        speedF = mNormalSpeed, NO foot-plant), the ANM_ROLLF frame ctrl advances at ROLL_RATE from 0.
        Two exits: (a) the anim completes (getRate()<0.01, frame reaches ROLL_END) -> if the stick is
        neutral, mNormalSpeed -= field_0x20 (the 26->21 drop, 6862), then checkNextMode(0); (b) with a
        PUSHED stick the getFrame()>field_0x10 early-turn fires checkNextMode(1) one frame sooner (no
        -field_0x20), routing to ATN_MOVE while L is held -- the roll-EBS that catches the full 26
        before the decel. checkNextMode picks the next proc (ATN if L else MOVE). Entry frame: no advance."""
        if self._roll_entered:                   # entry frame: ctrl stays at 0, no exit check
            self._roll_entered = False
            return
        self.roll_frame = f32(self.roll_frame + self.ROLL_RATE)
        if self.roll_frame >= self.ROLL_END:     # getRate()<0.01: anim complete
            if self.msd <= 0.05:
                self.nspeed = f32(self.nspeed - self.ROLL_MIN)
            self._roll_exit(l_held)
        elif self.roll_frame > self.ROLL_EARLY and self.msd > 0.05:
            # getFrame()>field_0x10 with a pushed stick: checkNextMode(1) is NOT inert -> exit early.
            self._roll_exit(l_held)

    def _roll_exit(self, l_held):
        """The roll's checkNextMode transition. -> ATN_MOVE if L held (procAtnMove_init), else MOVE
        (procMove_init). On the MOVE path arm the walk re-entry morf; the walk blend re-inits its
        frame ctrl to 0 because the roll left m34C3==0 (see enter_roll)."""
        self._check_next_mode(l_held)            # sets state (MOVE/ATN_MOVE) + mMaxNormalSpeed
        if self.state == MOVE and self._foot is not None:
            self._foot._pending_morf = self.MOVE_REENTRY_MORF

    # --- ground-reversal turn procs (WaitTurn 23 / MoveTurn 24 / Slip 25) ------------------
    def _proc_wait_turn_init(self):
        """procWaitTurn_init (6569): pivot in place. Capture the stick target (mProcVar2.m34D4 = m34E8)
        as the fixed pivot goal, snap travel onto facing (current.angle.y = shape_angle.y), reset the
        (ANM_ROT) anim. mNormalSpeed is already ~0. Position is frozen (speedF 0) through the pivot."""
        self.state = WAIT_TURN
        self.turn_target = self.target
        self.travel = self.facing
        # setSingleMoveAnime(ANM_ROT, mBasic.field_0x4, 0, -1, mBasic.field_0xC) (6574): pose the pivot
        # anim through WAIT_TURN so the toe stream is warm for the WAIT idle-proc re-pose + walk-off.
        if self._foot is not None:
            self._foot.enter_single('rot', self.MOVE_REENTRY_MORF, rate=self.WAIT_TURN_ANIM_RATE)
        else:
            self._pos_fallback = True         # no anim data: WAIT_TURN position uses the cLib chase

    def _proc_wait_turn(self, l_held):
        """procWaitTurn (6584): bleed mNormalSpeed toward 0, pivot facing toward the captured target at
        the mTurn rate (min step ~0x1F40 rules -> ~8000/frame), keep travel == facing. When the pivot
        residual reaches 0 -> checkNextMode(0): the stick is now aligned so it hands off to WAIT (then
        MOVE next frame). No translation while pivoting (speedF 0)."""
        self.nspeed = cLib_addCalc(self.nspeed, 0.0, self.F24, self.F1C, self.F20)
        self.facing = cLib_addCalcAngleS(self.facing, self.turn_target,
                                         self.TURN_SCALE, self.TURN_MAX, self.TURN_MIN)
        self.travel = self.facing
        if s16_signed(self.turn_target - self.facing) == 0:   # sVar1 == 0 (pivot complete)
            self._check_next_mode(l_held)

    def _proc_move_turn_init(self, param_1):
        """procMoveTurn_init (6611): set up the facing sweep. param_1!=0 (the 1 path, low-speed reversal):
        snap travel to the stick target (current.angle.y = m34E8), halve mNormalSpeed, sweep params
        (scale 2, max F0*4+0x4A56, min F0*2). param_1==0 (the slip-exit path): travel already flipped by
        procSlip; sweep params (scale 3, max F0*2, min F0). The body then re-accelerates while facing
        catches up to the (reversed) travel."""
        self.state = MOVE_TURN
        # procMoveTurn_init calls setBlendMoveAnime(mBasic.field_0xC) -> re-triggers the oldframe-morf
        # (same 2.4 as the roll->walk re-entry), so the walk blend re-warms from the pre-turn pose.
        if self._foot is not None:
            self._foot._pending_morf = self.MOVE_REENTRY_MORF
        if param_1 != 0:
            self.turn_shape_max = (self.F0 * 4 + 0x4A56) & 0xFFFF
            self.turn_shape_min = (self.F0 * 2) & 0xFFFF
            self.turn_shape_scale = 2
            self.travel = self.target
            # setBlendMoveAnime (6616) poses the walk anim at the PRE-halving speed; 6623 then halves
            # what posMoveFromFootPos integrates with (pose at _anim_nspeed, integrate at the halved).
            self._anim_nspeed = self.nspeed
            self.nspeed = f32(self.nspeed * 0.5)
        else:
            self.turn_shape_max = (self.F0 * 2) & 0xFFFF
            self.turn_shape_min = self.F0 & 0xFFFF
            self.turn_shape_scale = 3

    def _proc_move_turn(self, l_held):
        """procMoveTurn (6632): setSpeedAndAngleNormal re-accelerates along the (fixed) reversed travel
        (its reversal + facing-chase branches are both suppressed while mCurProc==MOVE_TURN), then sweep
        facing toward travel via cLib_addCalcAngleS(scale/max/min from init). checkNextMode keeps us in
        MOVE_TURN until facing == travel, then routes to MOVE. Position is walk-anim driven (fallback)."""
        self._set_speed_and_angle_normal(self.F0, attention_lock=l_held)
        self.facing = cLib_addCalcAngleS(self.facing, self.travel,
                                         self.turn_shape_scale, self.turn_shape_max, self.turn_shape_min)
        self._check_next_mode(l_held)
        # MOVE_TURN -> MOVE exit routes through procMove_init, which re-triggers the oldframe-morf
        # (setBlendMoveAnime(field_0xC), 6215) -- the walk re-warms from the turn's final pose.
        if self.state == MOVE and self._foot is not None:
            self._foot._pending_morf = self.MOVE_REENTRY_MORF

    def _proc_slip_init(self):
        """procSlip_init (6642): the skid seed. mNormalSpeed = speedF * mSlip.field_0x8 (1.1); field_0x0==0
        so no cap clamp -> the skid speed can exceed mMaxNormalSpeed (e.g. 17 -> 18.7). The skid is pure
        momentum (speedF == mNormalSpeed); ANM_SLIP is posed each frame to warm the toe stream, which feeds
        the MoveTurn walk tail bit-exact (ANM_SLIP scales jnt37 -> the FK now applies scale, see foot_fk)."""
        self.state = SLIP
        self.nspeed = f32(self.speedF * self.SLIP_ENTRY)
        # setSingleMoveAnime(ANM_SLIP, rate=mSlip.field_0xC, morf=mSlip.field_0x1C) (6646): pose the
        # skid anim through the slip so the toe stream is warm for the MoveTurn/walk tail.
        if self._foot is not None:
            self._foot.enter_single('slip', self.SLIP_MORF, rate=self.SLIP_ANIM_RATE)
        else:
            self._pos_fallback = True         # no anim data: SLIP tail uses the calibrated chase

    def _proc_slip(self, l_held):
        """procSlip (6658): bleed mNormalSpeed toward 0 at the mSlip decel (~-1.25/frame) while travel is
        held (skids FORWARD). When |mNormalSpeed| reaches ~0: with the stick still pushed, flip travel by
        0x8000, nudge facing +0x100, re-seed mNormalSpeed = mMaxNormalSpeed*0.5, and hand to procMoveTurn(0);
        with a neutral stick, checkNextMode(0). Flat/wall-free: the wall-hit branches are omitted."""
        self.nspeed = cLib_addCalc(self.nspeed, 0.0, self.SLIP_DEC_SCALE, self.SLIP_DEC_MAX, self.SLIP_DEC_MIN)
        if abs(self.nspeed) <= 0.001:                    # fabsf(0 - mNormalSpeed) <= 0.001 (6662)
            if self.msd > 0.05:
                self.travel = (self.facing + 0x8000) & 0xFFFF
                self.facing = (self.facing + 0x100) & 0xFFFF
                self.nspeed = f32(self.max_nspeed * self.MT_SLIP_SEED)
                self._proc_move_turn_init(0)
            else:
                self._check_next_mode(l_held)

    # --- targeted ballistic hops (procSideStep 6313 / procBackJump 7003) -------------------
    def _side_step_init(self, direction):
        """procSideStep_init (6313): a ballistic sidehop PERPENDICULAR to facing. current.angle.y =
        shape_angle.y +-0x4000; a fixed launch speed splits by the launch angle into horizontal
        (mNormalSpeed = cM_scos*speed) and vertical (speed.y = cM_ssin*speed). Pure momentum in air
        (m3598==0). ground_y = the launch height (m3688.y on flat ground). No lock-on actor here, so
        procSideStep's per-frame re-aim (6336) leaves travel constant."""
        self.state = SIDE_STEP
        self.direction = direction
        self.travel = ((self.facing + 0x4000) if direction == DIR_LEFT
                       else (self.facing - 0x4000)) & 0xFFFF
        self.nspeed = f32(S.cM_scos_s16(self.SIDESTEP_ANGLE) * self.SIDESTEP_SPEED)
        self.speed_y = f32(_cM_ssin_s16(self.SIDESTEP_ANGLE) * self.SIDESTEP_SPEED)
        self.gravity = self.SIDESTEP_GRAV
        self.ground_y = f32(self.pos_y)
        self.ground_hit = False
        self.air_anim = 0.0

    def _back_jump_init(self):
        """procBackJump_init (7003): a ballistic backflip. mNormalSpeed / speed.y are set DIRECTLY (no
        trig); current.angle.y = shape_angle.y + 0x8000 (backward). Lands only once BOTH ground-hit AND
        the ROLLB frame ctrl (start 2 -> end 11 @0.8) has run out (getRate()<0.01, procBackJump 7028) --
        so the horizontal momentum can slide along the ground for the frames between contact and anim-end."""
        self.state = BACK_JUMP
        self.direction = DIR_BACKWARD
        self.travel = (self.facing + 0x8000) & 0xFFFF
        self.nspeed = f32(self.BACKJUMP_SPEED)
        self.speed_y = f32(self.BACKJUMP_VY)
        self.gravity = self.BACKJUMP_GRAV
        self.ground_y = f32(self.pos_y)
        self.ground_hit = False
        self.air_anim = f32(self.BACKJUMP_ANIM_START)

    def _ballistic_anim_done(self):
        """getRate()<0.01 for the airborne anim: sidehop has no anim gate (lands on the first ground hit);
        backflip needs the ROLLB frame ctrl to have reached its end frame."""
        return self.state == SIDE_STEP or self.air_anim >= self.BACKJUMP_ANIM_END

    def _proc_ballistic(self, l_held):
        """procSideStep (6335) / procBackJump (7026), flat/no-item subset. The ground-hit + anim-rate
        tests read LAST frame's state (execute order: proc -> posMove -> CrrPos / anim update), so the
        land is detected one frame after pos.y crosses the floor. Flat ground + no bow/leaf/jump-cut ->
        pure ballistic. Advances the backflip ROLLB frame ctrl for next frame's land gate."""
        if self.ground_hit and self._ballistic_anim_done():
            self._ballistic_land_init()
            return
        if self.state == BACK_JUMP and self.air_anim < self.BACKJUMP_ANIM_END:
            self.air_anim = f32(self.air_anim + self.BACKJUMP_ANIM_RATE)
            if self.air_anim > self.BACKJUMP_ANIM_END:      # J3DFrameCtrl clamps to end, rate->0
                self.air_anim = f32(self.BACKJUMP_ANIM_END)

    def _ballistic_land_init(self):
        """procSideStepLand_init (6365) / procBackJumpLand_init (7042): mNormalSpeed = 0, backflip snaps
        current.angle.y = shape_angle.y (7056), pose the land recovery anim. Position is frozen through
        the recovery; when it completes checkNextMode routes to WAIT."""
        if self.state == SIDE_STEP:
            self.state = SIDE_STEP_LAND
        else:
            self.state = BACK_JUMP_LAND
            self.travel = self.facing
        self.nspeed = 0.0
        self.speed_y = 0.0
        self.air_anim = 0.0

    def _proc_ballistic_land(self, l_held):
        """The land recovery: the land anim frame ctrl runs to its end (position frozen at the floor),
        then checkNextMode(l_held) hands to WAIT (neutral) / ATN_MOVE (L). Duration affects the block's
        frame COST only -- position does not move (mNormalSpeed 0)."""
        if self.state == SIDE_STEP_LAND:
            end, rate = self.SIDESTEP_LAND_END, self.SIDESTEP_LAND_RATE
        else:
            end, rate = self.BACKJUMP_LAND_END, self.BACKJUMP_LAND_RATE
        self.air_anim = f32(self.air_anim + rate)
        if self.air_anim >= end:
            self._check_next_mode(l_held)

    # --- proc dispatch + per-frame step ----------------------------------------------------
    # --- SUBJECTIVITY freeze (B-cancel chained-freeze): C-up -> WAITS/WALK blend (m34C3=2) -> B-cancel
    # -> resume with the anim phase carried. Live 0-ULP. Decomp/why: knowledge/mechanics/land-movement.md.
    def enter_freeze(self):
        """procSubjectivity_init (d_a_player_main.cpp:5948): mNormalSpeed=0 (freeze) + the WAITS/WALK
        idle blend with the walk phase preserved. Call AFTER the approach has decelerated Link to the
        freeze position (the reach_freeze cancel tail leaves it there). Position holds from here.
        Runs natively (fused LandCore) when present -- the chained-freeze planner searches at C speed."""
        if self._foot is None:
            raise RuntimeError("enter_freeze needs the anim foot engine")
        if self._core is not None:
            self._core.enter_freeze()
            self._sync_from_core()
            return
        self.nspeed = 0.0
        self.speedF = 0.0
        self.state = SUBJECTIVITY
        self._foot.enter_subjectivity(self.msd)
        self.visited.add(self.state)

    def hold_freeze(self):
        """One SUBJECTIVITY (or post-B WAIT) hold frame: position frozen, the WAITS anim advances at
        1.1/frame (procSubjectivity only setBodyAngleToCamera). Each hold frame shifts the carried
        resume phase -- the chained planner's lever for tuning the re-walk-from-rest trajectory."""
        if self._core is not None:
            self._core.hold_freeze()
            self._sync_from_core()
            return
        self.speedF = 0.0
        self._foot.step_subjectivity(self.msd)

    def resume_walk(self):
        """Exit the freeze into MOVE (procMove_init, 6210): setBlendMoveAnime re-triggers the
        oldframe-morf and, because m34C3=2, PRESERVES the carried WAITS phase. After this, step() with
        a forward stick walks from rest bit-exactly (the 2-frame input latency still applies)."""
        if self._core is not None:
            self._core.resume_walk()
            self._sync_from_core()
            return
        self.state = MOVE
        self.nspeed = 0.0
        self._foot._pending_morf = self.MOVE_REENTRY_MORF

    def step(self, sx, sy, buttons=0, triggerL=0, csx=128, csy=128):
        """Advance one frame with a raw main stick (sx, sy) + optional L-target (buttons 0x40 or
        analog triggerL) + raw C-stick (csx, csy) steering the camera. Returns (d_pos, tag).
        csangle is driven per-frame from the shared camera; a centered C-stick (csx=128, the
        free-cam default) holds it frozen at the seed, matching straight superswims."""
        if self._core is not None:               # native LandCore: one C call/frame, then sync
            d = self._core.step(int(sx), int(sy), int(buttons), int(triggerL), int(csx), int(csy))
            self._sync_from_core()
            return d, _STATE_TAG.get(self.state, "?")
        # 2-frame controller latency: act on the input (stick, L AND C-stick) delivered INPUT_DELAY
        # frames ago -- the whole controller poll is delivered together.
        self._inbuf.append((int(sx), int(sy), int(buttons), int(triggerL), int(csx), int(csy)))
        asx, asy, abtn, atrig, acsx, acsy = self._inbuf.pop(0)
        # setStickData reads the camera value as of the START of the frame (the camera integrator
        # advances LATER in the frame): m34E8 = m34DC(stick) + csangle[f-1]. Mirror swim_predict.
        self.csangle = self._cam.csangle
        self._set_stick_data(asx, asy)
        l_held = bool(abtn & 0x40) or atrig >= 200      # checkAttentionLock proxy (digital/analog L)
        a_pressed = bool(abtn & 0x100)                   # doTrigger: A = the "do"/roll button

        moving = self.msd > 0.05
        # Attention-lock engage: capture the facing lock (m34E6 = shape_angle.y, 2067) on the rising
        # edge; it stays frozen because the ATN path writes shape_angle.y = m34E6 every frame.
        if l_held and not self._l_prev:
            self.m34E6 = self.facing
        # doTrigger (A) dispatch (checkNextActionFromButton 4309): L held -> JUMP (sidehop L/R, backflip
        # back; no forward); L off + moving -> ATTACK roll. Input mapping: land-movement.md (a gotcha).
        grounded = self.state in (WAIT, FREE_WAIT, MOVE, ATN_MOVE)
        if a_pressed and grounded:
            if l_held:
                jdir = self._get_dir_from_angle(s16_signed(self.target - self.facing))
                if jdir in (DIR_LEFT, DIR_RIGHT):
                    self._side_step_init(jdir)
                elif jdir == DIR_BACKWARD:
                    self._back_jump_init()
            elif moving and self.state in (MOVE, ATN_MOVE):
                self.facing = self.target
                self._roll_init()

        # dispatch the active proc body. WAIT/FREE_WAIT/MOVE/ATN_MOVE run their speed/angle update then
        # checkNextMode (the arbiter: starts locomotion from idle, routes reversals to the turn procs).
        proc = self.state                        # dispatch-time proc (mCurProc; may transition below)
        if proc in (WAIT, FREE_WAIT):
            if l_held:                           # attention lock from a standstill -> procAtnMove path
                self.state = ATN_MOVE
                self._set_speed_and_angle_atn()
            else:
                self._set_speed_and_angle_normal(self.F0, attention_lock=False)
            self._check_next_mode(l_held)
        elif proc == MOVE:
            self._set_speed_and_angle_normal(self.F0, attention_lock=l_held)
            self._check_next_mode(l_held)
        elif proc == ATN_MOVE:
            self._set_speed_and_angle_atn()
            self._check_next_mode(l_held)
        elif proc == WAIT_TURN:
            self._proc_wait_turn(l_held)         # checkNextMode when the pivot completes
        elif proc == MOVE_TURN:
            self._proc_move_turn(l_held)         # checkNextMode after the facing sweep
        elif proc == SLIP:
            self._proc_slip(l_held)              # checkNextMode / hand to MoveTurn when the skid dies
        elif proc == FRONT_ROLL:
            self._proc_roll(l_held)              # checkNextMode on its exit frame
        elif proc in (SIDE_STEP, BACK_JUMP):
            self._proc_ballistic(l_held)         # lands on the (1-frame-late) ground hit
        elif proc in (SIDE_STEP_LAND, BACK_JUMP_LAND):
            self._proc_ballistic_land(l_held)    # recovery anim -> WAIT

        # setBlendAtnMoveAnime's direction update for a (possibly just-entered) ATN frame. Capture the
        # pre-update mDirection (uVar1, 3291): the anim re-triggers the oldframe-morf when it changes.
        prev_dir = self.direction
        if self.state == ATN_MOVE:
            self._update_atn_direction()
        # ATN -> MOVE (L released): the next frame is procMove_init, which re-triggers the oldframe-morf
        # (setBlendMoveAnime(mBasic.field_0xC), 6215) -- the walk re-warms from the ATN strafe pose.
        if proc == ATN_MOVE and self.state == MOVE and self._foot is not None:
            self._foot._pending_morf = self.MOVE_REENTRY_MORF

        # Before posing, set Link's CURRENT (pre-integration) world pos + shape_angle.y: the foot FK runs
        # from worldBase(pos) to carry world-magnitude quantization. See knowledge/model/sim.md.
        if self._foot is not None:
            self._foot.set_pos(self.pos_x, self.pos_z, facing=self.facing)
        # speedF -> position. ROLL/SLIP = momentum; WAIT_TURN frozen; MOVE + MOVE_TURN tail + ATN_MOVE use
        # the anim engine (only the SLIP tail keeps the fallback); single-anim procs pose to warm the stream.
        if self.state in (SIDE_STEP, BACK_JUMP):
            # Airborne ballistic: horizontal momentum (shared bottom advances pos.x/z); vertical integrates
            # speed.y by gravity, then CrrPos snaps to the floor + flags GROUND_HIT. See land-movement.md.
            self.speedF = 0.0 if abs(self.nspeed) < 0.05 else self.nspeed
            self.speed_y = f32(self.speed_y + self.gravity)
            if self.speed_y < self.MAX_FALL:
                self.speed_y = f32(self.MAX_FALL)
            self.pos_y = f32(self.pos_y + self.speed_y)
            if self.pos_y <= self.ground_y:
                self.pos_y = f32(self.ground_y)
                self.ground_hit = True
            else:
                self.ground_hit = False
        elif self.state in (SIDE_STEP_LAND, BACK_JUMP_LAND):
            self.speedF = 0.0                     # land recovery: mNormalSpeed 0, position frozen
        elif self.state == WAIT_TURN:
            if self._foot is not None:
                self._foot.step_single_anim(self.nspeed, self.msd)   # pose ANM_ROT, warm the toe stream
            self.speedF = 0.0
        elif proc == WAIT_TURN and self.state == WAIT and self._foot is not None:
            # Pivot done -> WAIT: procWait_init's idle-proc setBlendMoveAnime, facing != m34DE turn-step
            # arm (WAITS/ANM_ATNW{L,R}S, ratio clamp(0.5+0.001|dfacing|,0,1)) -- see land-movement.md.
            r3 = s16_signed(self.facing - self.m34de)
            r27 = 'atnwls' if r3 > 0 else 'atnwrs'
            ratio = min(f32(f32(0.5) + f32(0.001 * abs(r3))), 1.0)
            self._foot.enter_wait_idle(ratio, r27, self.MOVE_REENTRY_MORF, self.msd)
            self.speedF = 0.0
        elif self.state in (FRONT_ROLL, SLIP):
            if self._foot is not None:
                self._foot.step_single_anim(self.nspeed, self.msd)   # warm the toe stream
            # m3598==0 here so speedF == mNormalSpeed, but posMoveFromFootPos still snaps |speedF|<0.05
            # to 0 (d_a_player_main.cpp:2418) -- the slip decel tail. See land-sim.md (slip-skid tail).
            self.speedF = 0.0 if abs(self.nspeed) < 0.05 else self.nspeed
        elif self.state == ATN_MOVE and self._foot is not None:
            # ATN_MOVE: setBlendAtnMoveAnime poses the strafe/back anim. f31 = |nspeed*cos(m34E2)|/max
            # (cos=1 on flat); the pose warms the toe stream so an EBS-release MOVE rejoins bit-exact.
            f31 = f32(abs(self.nspeed) / self.max_nspeed)
            atn_morf = (self.MOVE_REENTRY_MORF if (proc != ATN_MOVE or self.direction != prev_dir)
                        else None)
            self.speedF = self._foot.step_atn(self.nspeed, self.msd, self.direction, f31, atn_morf)
        elif self._foot is not None:
            # walk anim engine (bit-exact for a clean MOVE; the MOVE_TURN tail rejoins it too). On the
            # procMoveTurn_init(1) frame the anim is posed at the pre-halving speed (_anim_nspeed).
            self.speedF = self._foot.step(self.nspeed, self.msd, anim_nspeed=self._anim_nspeed)
            self._anim_nspeed = None
        else:
            sc, mx, mn = SPEEDF_CHASE
            self.speedF = cLib_addCalc(self.speedF, self.nspeed, sc, mx, mn)
            if self.nspeed == 0.0 and abs(self.speedF) < 0.5:
                self.speedF = 0.0                # snap to a clean standstill at the WAIT edge
        # world motion is speedF along travel: speed.z = speedF*cos, x = speedF*sin. pos.{x,z} are f32
        # fields (cXyz) re-rounded each frame -> accumulate in f32, not an f64 sum. See knowledge/model/sim.md.
        d = self.speedF
        self.pos_x = f32(self.pos_x + f32(d * _cM_ssin_s16(self.travel)))
        self.pos_z = f32(self.pos_z + f32(d * S.cM_scos_s16(self.travel)))
        self.m34de = self.facing                 # m34DE = shape_angle.y (end-of-frame, 11287): last facing
        self.m34ea = self.m34dc                  # m34EA = m34DC (end-of-frame, 11289): last stick want
        # advance the shared camera for NEXT frame (its own 1-frame internal lag stacks on the
        # controller delay above); csangle[f] read at the top of the next step.
        self._cam.step(acsx, acsy)
        self.visited.add(self.state)
        self._l_prev = l_held
        return d, _STATE_TAG.get(self.state, "?")


def _is_zero(x):
    # cM3d_IsZero: |x| < 0.00001 (c_m3d.cpp). Only the exact-0 dVar9 (release) matters here.
    return abs(x) < 1.0e-5


def _dist_angle_s(a, b):
    # cLib_distanceAngleS: |signed s16 difference| (magnitude of the shortest turn).
    return abs(s16_signed(int(a) - int(b)))


# Single-sourced HIO/tuning constants handed to the native LandCore (_anmc.land_init_consts). Keeps
# land.py the one canonical home for the walk/atn/roll/turn/slip constants; the C twin never restates them.
_LAND_CONSTS = {n: getattr(LandState, n) for n in (
    'MAX_NSPEED', 'F14', 'F1C', 'F20', 'F24', 'F0', 'F4', 'F6',
    'ATN_MAX', 'ATN_SPD', 'ATN_ACC', 'ATN_DEC', 'ATN_SCL',
    'ATN_TURN_MAX', 'ATN_TURN_MIN', 'ATN_TURN_SCALE',
    'ATNB_MAX', 'ATNB_SPD', 'ATNB_ACC', 'ATNB_DEC', 'ATNB_SCL', 'ATNB_COS_FWD', 'ATNB_COS_BACK',
    'ROLL_SPD', 'ROLL_ADD', 'ROLL_MIN', 'ROLL_END', 'ROLL_RATE', 'ROLL_ENTRY_MORF',
    'MOVE_REENTRY_MORF', 'ROLL_EARLY',
    'TURN_MAX', 'TURN_MIN', 'TURN_SCALE', 'WAIT_TURN_ANIM_RATE',
    'SLIP_THRESH', 'SLIP_ENTRY', 'SLIP_DEC_SCALE', 'SLIP_DEC_MAX', 'SLIP_DEC_MIN',
    'SLIP_ANIM_RATE', 'SLIP_MORF', 'MT_SLIP_SEED')}


def _cM_ssin_s16(angle):
    # cM_ssin(a) == JMASSin(a): the console SIN table directly, NOT a cos offset (cos[0xC000] != sin[0]).
    # See knowledge/model/fp-faithfulness.md (sin table) + history/resolved-bugs.md (pos_x sine leak).
    return S.cM_ssin_s16(angle)


def run_walk(sticks, csangle=0, **seed):
    """Step a list of raw (sx, sy) sticks from a seed state. Returns per-frame rows.
    `seed` forwards to LandState (pos_z, facing, travel, state, nspeed, speedF)."""
    s = LandState(csangle=csangle, **seed)
    rows = [{"f": 0, "state": s.state, "nspeed": s.nspeed, "speedF": s.speedF,
             "pos_z": s.pos_z, "msd": s.msd}]
    for i, (sx, sy) in enumerate(sticks, 1):
        d, tag = s.step(sx, sy)
        rows.append({"f": i, "state": s.state, "nspeed": s.nspeed, "speedF": s.speedF,
                     "pos_z": s.pos_z, "msd": s.msd, "tag": tag})
    return rows
