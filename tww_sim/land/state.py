#!/usr/bin/env python3
"""state.py - the LandState class: one Link on flat, wall-free ground, stepped frame by frame.

Pure-offline transcription of the on-ground locomotion procs, validated bit-exact vs the live game
for `mNormalSpeed` (potential_speed) and the state machine on a flat, wall-free floor. LandState
carries the HIO constant block + the per-frame `step` dispatcher + position integration; the proc
bodies live in procs/* as mixins it multi-inherits (`_MoveMixin` first, the MRO base). Constants +
leaf helpers are in constants.py. See land.py (shim) for the preserved public import surface.

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
  (core.anim: the BCK keyframe eval + reduced foot-chain FK + two-anim blend + oldframe-morf,
  all FMA-faithful). core.anim.foot_speedf.FootSpeedF is that chain; LandState drives it each
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
from .constants import *  # noqa: F401,F403  (proc enums, DIR_*, gates -- also re-exported by land.py)
from .constants import _STATE_TAG, _cM_ssin_s16
from .procs.move import _MoveMixin
from .procs.atn import _AtnMixin
from .procs.roll import _RollMixin
from .procs.cut import _CutMixin
from .procs.turn import _TurnMixin
from .procs.ballistic import _BallisticMixin
from .procs.freeze import _FreezeMixin


class LandState(_MoveMixin, _AtnMixin, _RollMixin, _CutMixin, _TurnMixin, _BallisticMixin, _FreezeMixin):
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

    # HIO mCut sword-thrust cuts (roll stab). d_a_player_HIO_data.inc:31/27, procCutF/A sword.inc:660/430;
    # the roll-stab lunge model + why 49.22u: knowledge/mechanics/land-movement.md + reference/constants.md.
    CUT_ANIM = {CUT_F: 'cutf', CUT_A: 'cuta'}
    CUT_RATE = f32(1.2)             # field_0x4  = ANM_CUT frame-ctrl rate (mFrameCtrlUnder[MOVE0])
    CUT_START = f32(4.0)            # field_0x8  = setSingleMoveAnime start frame (fc begins here)
    CUT_END = f32(19.0)            # bck frameMax (EMode_NONE end); rate->0 clamp at end-0.001
    CUT_PASS = f32(6.0)            # field_0x28 = checkPass frame -> set mNormalSpeed launch
    CUT_LAUNCH_MUL = f32(0.2)      # field_0x10 = mNormalSpeed = |speedF|*this + <add>
    CUT_DEC_SCALE = f32(0.7)       # field_0x20 = cLib_addCalc decel scale
    CUT_DEC_MIN = f32(0.5)         # field_0x1C = cLib_addCalc decel minStep
    # per-cut fields: field_0xC (getFrame()> -> checkNextMode(1) exit) / field_0x14 (add) / field_0x18 (max)
    CUT_EARLY = {CUT_F: f32(17.0), CUT_A: f32(16.0)}   # field_0xC
    CUT_LAUNCH_ADD = {CUT_F: f32(8.0), CUT_A: f32(10.0)}  # field_0x14
    CUT_DEC_MAX = {CUT_F: f32(0.95), CUT_A: f32(2.6)}     # field_0x18
    # Diagonal-thrust aim turn: procCutF/A snap shape=travel to the latched m34D4 aim on the 1st cut
    # proc frame (cLib min-step 0x1F40 >> any in-range diff). See knowledge/mechanics/roll-stab.md.
    CUT_TURN_SCALE = 30            # mTurn.field_0x4 (cLib_addCalcAngleS scale)
    CUT_TURN_MAX = 0x3CDF          # mTurn.field_0x0 (maxStep)
    CUT_TURN_MIN = 0x1F40          # mTurn.field_0x2 (minStep; >> any in-range diff -> 1-frame snap)
    CUT_DIR_FWD = 0x2000          # getDirectionFromAngle FORWARD band: |aim - facing| < this stays CUT_F

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
                 use_anim=True, cam_scale=LAND_SCALE, pos_y=0.0, native=True, foot_native=True,
                 sword_drawn=False):
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
        self._subj_arm = False                 # C-up gesture seen -> enter SUBJECTIVITY next frame
        self._subj_ended = False               # B/A/L/C-DOWN ended the freeze (checkSubjectEnd) -> stick re-walks
        self._subj_frames = 0                  # body frames since the freeze locked (C-DOWN camera floor)
        self._cdown_run = 0                    # consecutive acted C-down frames (0x2000 subject-exit arming)
        self._abtn_prev = 0                    # acted buttons last frame (for the A/B mItemTrigger edge)
        self.visited = set()                   # every proc state this run passed through (path assertions)
        self.roll_frame = 0.0                  # ANM_ROLLF frame ctrl during FRONT_ROLL (times the exit)
        self._roll_entered = False             # entry frame: don't advance the anim ctrl yet
        # Sword-thrust cut (CUT_F / CUT_A) state -- the "roll stab". sword_drawn gates the roll->cut
        # trigger (a cut only fires out of a roll if the sword is out; a bare roll routes to MOVE).
        self.sword_drawn = bool(sword_drawn)   # gates the roll->cut trigger; see land-movement.md (roll stab)
        self._b_held = False                   # swordButton() (B mItemButton, HELD) this frame
        self._b_trig = False                   # swordTrigger() (B mItemTrigger, RISING EDGE) this frame -- the
        #                                        actual roll->cut trigger (a HELD B never re-fires the edge)
        self.cut_frame = 0.0                   # mFrameCtrlUnder[MOVE0] frame during a cut (times the lunge/exit)
        self._cut_entered = False              # cut entry frame: no ctrl advance, nspeed carried, m3700_prev=0
        self._cut_m3700 = (0.0, 0.0, 0.0)      # previous frame's m3700 (anim joint-0 translate); reset 0 at init
        self._cut_add = (0.0, 0.0)             # this frame's rotated root-translate delta, added after the shared bottom
        self._cut_anim_cache = None            # loaded cutf/cuta anim dict (j3d_eval), lazy
        self.cut_target = None                 # mProcVar2.m34D4: the latched thrust aim (shape snaps here
        #                                        on the 1st cut proc frame). None -> straight (== roll facing).
        self.turn_target = 0                   # mProcVar2.m34D4 (WaitTurn facing-pivot target)
        self.turn_shape_scale = 0              # MoveTurn shape-sweep cLib params (m34D0/m34D4/m34D6)
        self.turn_shape_max = 0
        self.turn_shape_min = 0
        self._anim_nspeed = None               # 1-frame anim/integrate speed split (procMoveTurn_init halving)
        # 2-frame controller-input buffer (index 0 = oldest = the input acted on this frame). Tuple =
        # (stickX,stickY,buttons,triggerL,csx,csy): L/target AND the C-stick share the pipe, all delayed.
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
        # Native land physics: fused C engine present -> the whole per-frame step is one LandCore call;
        # absent (or native=False, REQUIRED for the ballistic hops the C twin lacks) -> bit-identical Python.
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

    @property
    def anim_fc0(self):
        """The walk-anim frame-ctrl phase (`J3DFrameCtrl` frame of MOVE slot 0). At the 17u speed cap
        this advances a fixed +2.3/frame and the freeze coast is a pure function of it — the observable
        the fewest-frame freeze planner (`plan_land.reach_freeze(min_frames=True)`) uses to predict a
        start crawl's full-speed freeze. Reads whichever backend is active (native core / Python foot)."""
        if self._core is not None:
            return self._core.pe_phase[0]
        if self._foot is not None:
            return self._foot.st.fc0.frame
        return 0.0

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

    # --- proc dispatch + per-frame step ----------------------------------------------------
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
        self._b_held = bool(abtn & 0x200)                # swordButton (B mItemButton, HELD)
        # mItemTrigger RISING EDGE (on the delivered/delayed input): a HELD B misses it -> no exit. See KB.
        # ab_edge = combined A|B (freeze checkSubjectEnd 5698); _b_trig = B-only (roll->cut swordTrigger 4203).
        ab_edge = ((abtn & ~self._abtn_prev) & 0x300) != 0
        self._b_trig = ((abtn & ~self._abtn_prev) & 0x200) != 0
        self._abtn_prev = abtn

        moving = self.msd > 0.05
        # --- SUBJECTIVITY freeze (C-up cancel), fully input-driven (no enter_freeze/hold/resume API).
        # Full state machine + decomp cites: knowledge/mechanics/land-movement.md (subjectivity freeze).
        posy = self._cstick_posy(acsx, acsy)
        cup_now = (self.msd < CUP_MAIN_MAX and posy > CUP_POSY)   # C-up still requested this frame
        if self._subj_arm:                       # armed last frame by the C-up gesture -> init the freeze
            self._subj_arm = False
            self.state = SUBJECTIVITY
            self.nspeed = 0.0
            self.speedF = 0.0
            self._subj_ended = False
            self._subj_frames = 0
            self._cdown_run = 0
            if self._foot is not None:
                self._foot.enter_subjectivity(self.msd)   # procSubjectivity_init: WAITS/WALK blend, phase kept
            self.m34de = self.facing
            self.m34ea = self.m34dc
            self._cam.step(acsx, acsy)
            self.visited.add(SUBJECTIVITY)
            self._l_prev = l_held
            return 0.0, "SUBJ"
        if self.state == SUBJECTIVITY:
            self._subj_frames += 1
            # exit-to-WAIT is its OWN hold frame -> resume only if ALREADY ended on a PRIOR frame
            # (changeWaitProc->WAIT one frame, THEN checkNextMode->MOVE); matters when exit + fwd coincide.
            was_ended = self._subj_ended
            if cup_now:
                # C-up still held -> camera re-requests subjectivity; prior exit void, stay frozen (re-enter cup-cam).
                self._subj_ended = False
                self._cdown_run = 0
            else:
                if ab_edge or l_held:            # A/B mItemTrigger edge | L held (mItemButton) -- no floor
                    self._subj_ended = True
                if posy < CDOWN_POSY:            # C-DOWN -> camera 0x2000, but only past the SUBJ_VIEW_IN floor
                    self._cdown_run += 1
                    if self._cdown_run >= CDOWN_RUN and self._subj_frames >= SUBJ_CAM_FLOOR:
                        self._subj_ended = True
                else:
                    self._cdown_run = 0
            if was_ended and not cup_now and self.msd > 0.05:
                # procMove_init on WAIT->MOVE: re-enter the walk with the carried WAITS phase (m34C3=2).
                # Fall through to the MOVE dispatch below so this frame is the first re-walk step.
                self.state = MOVE
                self.nspeed = 0.0
                if self._foot is not None:
                    self._foot._pending_morf = self.MOVE_REENTRY_MORF
            else:                                # hold: freeze position, advance the WAITS anim (warm phase)
                self.speedF = 0.0
                if self._foot is not None:
                    self._foot.step_subjectivity(self.msd)
                self.m34de = self.facing
                self.m34ea = self.m34dc
                self._cam.step(acsx, acsy)
                self.visited.add(SUBJECTIVITY)
                self._l_prev = l_held
                return 0.0, "SUBJ"
        elif self.state in (MOVE, WAIT, FREE_WAIT, ATN_MOVE) and cup_now:
            self._subj_arm = True                # C-up from a grounded MOVE/WAIT -> freeze NEXT frame
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
            self._proc_roll(l_held)              # checkNextMode on its exit frame (-> CUT if B buffered)
        elif proc in (CUT_F, CUT_A):
            self._proc_cut(l_held)               # sword-thrust lunge; exits to WAIT when the anim passes field_0xC
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
        elif self.state in (CUT_F, CUT_A):
            # Sword-thrust lunge: speedF (==nspeed, m3598==0) + posMove m34C2==1 root-translate delta
            # (rotated by shape); entry frame m3700_prev==0 -> full root translate stacks (~49.22). See KB.
            self.speedF = 0.0 if abs(self.nspeed) < 0.05 else self.nspeed
            m3700 = self._cut_m3700_at(self.state, self.cut_frame)
            sp5c = (f32(m3700[0] - self._cut_m3700[0]), f32(m3700[1] - self._cut_m3700[1]),
                    f32(m3700[2] - self._cut_m3700[2]))
            self._cut_m3700 = m3700
            s = _cM_ssin_s16(self.facing); c = S.cM_scos_s16(self.facing)   # rotate by shape_angle.y
            self._cut_add = (f32(f32(sp5c[2] * s) + f32(sp5c[0] * c)),
                             f32(f32(sp5c[2] * c) - f32(sp5c[0] * s)))
        elif proc in (CUT_F, CUT_A):
            # The cut EXITED to WAIT this frame (checkNextMode(1) set mNormalSpeed=0) -> position freezes.
            self.speedF = 0.0
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
        px0, pz0 = self.pos_x, self.pos_z
        self.pos_x = f32(self.pos_x + f32(d * _cM_ssin_s16(self.travel)))
        self.pos_z = f32(self.pos_z + f32(d * S.cM_scos_s16(self.travel)))
        # Sword-cut root-translate lunge (posMove m34C2==1) on top of the foot term, zeroed except on a
        # CUT frame; the returned displacement is then the TRUE single-frame move (foot + lunge, ~49.22).
        if self.state in (CUT_F, CUT_A):
            self.pos_x = f32(self.pos_x + self._cut_add[0])
            self.pos_z = f32(self.pos_z + self._cut_add[1])
            d = math.hypot(self.pos_x - px0, self.pos_z - pz0)
        self._cut_add = (0.0, 0.0)
        self.m34de = self.facing                 # m34DE = shape_angle.y (end-of-frame, 11287): last facing
        self.m34ea = self.m34dc                  # m34EA = m34DC (end-of-frame, 11289): last stick want
        # advance the shared camera for NEXT frame (its own 1-frame internal lag stacks on the
        # controller delay above); csangle[f] read at the top of the next step.
        self._cam.step(acsx, acsy)
        self.visited.add(self.state)
        self._l_prev = l_held
        return d, _STATE_TAG.get(self.state, "?")


# Single-sourced HIO/tuning constants handed to the native LandCore (_anmc.land_init_consts). Keeps
# state.py the one canonical home for the walk/atn/roll/turn/slip constants; the C twin never restates them.
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
