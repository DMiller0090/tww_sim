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
from . import sim as S
from .sim import f32, cLib_addCalc, cM_scos_s16, deg_to_s16, s16_signed, _deadzone, stick_angle_deg

# link_state / daPyProc values (d_a_player_main.h). Walk trio + the targeting-move proc.
WAIT = 4          # daPyProc_WAIT_e         (idle standstill)
FREE_WAIT = 5     # daPyProc_FREE_WAIT_e    (anchor's resting proc)
MOVE = 6          # daPyProc_MOVE_e         (ground locomotion)
ATN_MOVE = 7      # daPyProc_ATN_MOVE_e     (targeting move: brakeslide / L-held slide)

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

    def __init__(self, pos_z=764.079, pos_x=0.0, facing=0, travel=0, csangle=0,
                 state=FREE_WAIT, nspeed=0.0, speedF=0.0, idle_frame=DEFAULT_IDLE_FRAME,
                 use_anim=True):
        self.pos_x = float(pos_x)
        self.pos_z = float(pos_z)
        self.facing = int(facing) & 0xFFFF     # shape_angle.y (s16)
        self.travel = int(travel) & 0xFFFF     # current.angle.y (s16)
        self.csangle = int(csangle) & 0xFFFF   # dCam_getControledAngleY (s16)
        self.target = 0                        # m34E8 (s16), set each frame by setStickData
        self.state = int(state)                # link_state / mCurProc
        self.nspeed = f32(nspeed)              # mNormalSpeed (potential_speed) -- bit-exact
        self.speedF = f32(speedF)              # position-integrating speed
        self.msd = 0.0                         # mStickDistance
        self.max_nspeed = f32(self.MAX_NSPEED) # mMaxNormalSpeed (switches 17/15/12 under ATN)
        self.direction = DIR_NONE              # mDirection (ATN physics branch selector)
        self.m34E6 = int(facing) & 0xFFFF      # facing lock captured on attention-lock engage
        self._l_prev = False                   # attention-lock (L) held last frame (rising edge)
        self._visited_atn = False              # did this run ever enter ATN_MOVE (ATN anims unported)
        # 2-frame controller-input buffer (index 0 = oldest = the input acted on this frame).
        # Tuple = (stickX, stickY, buttons, triggerL) -- L/target is delayed like the stick.
        self._inbuf = [(128, 128, 0, 0)] * INPUT_DELAY
        # Anim-driven speedF: the ported posMoveFromFootPos chain (bit-exact position). None when
        # disabled or the keyframe data is absent -> fall back to the SPEEDF_CHASE stand-in.
        self._foot = None
        if use_anim:
            try:
                from .anim.foot_speedf import FootSpeedF
                self._foot = FootSpeedF(idle_frame=float(idle_frame))
            except (FileNotFoundError, OSError, ImportError):
                self._foot = None

    def clone(self):
        s = LandState.__new__(LandState)
        s.__dict__.update(self.__dict__)
        s._inbuf = list(self._inbuf)
        # FootSpeedF is stateful; a shallow copy would alias it. Clones share nothing, so clone
        # cannot preserve mid-walk anim state -- only clone at rest (pre-walk) where seeding matches.
        if self._foot is not None and (s._foot is None or s._foot is self._foot):
            from .anim.foot_speedf import FootSpeedF
            try:
                s._foot = FootSpeedF(idle_frame=self._foot.idle_frame)
            except (FileNotFoundError, OSError, ImportError):
                s._foot = None
        return s

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
            m34dc = (deg_to_s16(sa) + 0x8000) & 0xFFFF
            self.target = (m34dc + self.csangle) & 0xFFFF

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
            dVar11 = f32(self.msd * self.msd)
            # Aligned branch (walk): m34E8 within 0x7800 of travel -> chase travel + keep the
            # cM_scos speed scale. The >0x7800 near-reversal branch (skipped under attention).
            if not attention_lock and _dist_angle_s(self.target, self.travel) > 0x7800:
                # near-reversal: chase and skip the speed-scale (bVar2). Rare in steady walk.
                self.travel = cLib_addCalcAngleS(self.travel, self.target, self.F6, param_1, self.F4)
                dVar9 = 0.0
                bVar2 = True
            else:
                sVar6 = int(param_1 * dVar11)
                if sVar6 < 10:
                    sVar6 = 10
                sVar7 = int(self.F4 * dVar11)
                if sVar7 < 1:
                    sVar7 = 1
                self.travel = cLib_addCalcAngleS(self.travel, self.target, self.F6, sVar6, sVar7)
                bVar2 = False
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
        # (facing is frozen to m34E6 by the ATN caller). (2834-2845)
        if not attention_lock and self.msd > 0.05:
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
        WAIT when stopped; else the MOVE branch -> MOVE while moving, WAIT when stopped. The
        MOVE_TURN / WaitTurn / Slip sub-procs (reversal turns) are not modelled -- the aligned walk
        and the brakeslide/EBS tests never enter them (a reversal in a MOVE frame is flagged)."""
        if l_held:                                        # r24: checkAttentionLock (no lock-on actor)
            self.max_nspeed = self.ATN_MAX
            self.state = WAIT if abs(self.nspeed) <= 0.001 else ATN_MOVE
        else:
            self.max_nspeed = f32(self.MAX_NSPEED)
            self.direction = DIR_NONE
            self.state = WAIT if abs(self.nspeed) <= 0.001 else MOVE

    # --- proc dispatch + per-frame step ----------------------------------------------------
    def step(self, sx, sy, buttons=0, triggerL=0):
        """Advance one frame with a raw stick (sx, sy) + optional L-target (buttons 0x40 or analog
        triggerL). Returns (d_pos, tag). csangle is held in self.csangle (set it before stepping to
        steer the camera-relative target)."""
        # 2-frame controller latency: act on the input (stick AND L) delivered INPUT_DELAY frames ago.
        self._inbuf.append((int(sx), int(sy), int(buttons), int(triggerL)))
        asx, asy, abtn, atrig = self._inbuf.pop(0)
        self._set_stick_data(asx, asy)
        l_held = bool(abtn & 0x40) or atrig >= 200      # checkAttentionLock proxy (digital/analog L)

        moving = self.msd > 0.05
        # Attention-lock engage: capture the facing lock (m34E6 = shape_angle.y, 2067) on the rising
        # edge; it stays frozen because the ATN path writes shape_angle.y = m34E6 every frame.
        if l_held and not self._l_prev:
            self.m34E6 = self.facing
        # idle -> move entry (procFreeWait/procWait push a stick): start the locomotion proc.
        if self.state in (WAIT, FREE_WAIT) and moving:
            self.state = ATN_MOVE if l_held else MOVE

        # dispatch the active proc's speed/angle update
        if self.state == MOVE:
            self._set_speed_and_angle_normal(self.F0, attention_lock=l_held)
        elif self.state == ATN_MOVE:
            self._visited_atn = True
            self._set_speed_and_angle_atn()
        # WAIT/FREE_WAIT: idle, nspeed stays put.

        # checkNextMode: transition arbiter (runs after the proc). Then setBlendAtnMoveAnime's
        # direction update for the next ATN frame (also fires at ATN entry).
        if self.state in (MOVE, ATN_MOVE):
            self._check_next_mode(l_held)
        if self.state == ATN_MOVE:
            self._update_atn_direction()

        # speedF -> position: the bit-exact WALK anim engine drives state MOVE; ATN_MOVE falls back to
        # a cLib chase (ANM_ATN* anims unported; ATN position not validated to ULP). See land-movement.md.
        if self.state != ATN_MOVE and self._foot is not None:
            self.speedF = self._foot.step(self.nspeed, self.msd)
        else:
            sc, mx, mn = SPEEDF_CHASE
            self.speedF = cLib_addCalc(self.speedF, self.nspeed, sc, mx, mn)
            if self.nspeed == 0.0 and abs(self.speedF) < 0.5:
                self.speedF = 0.0                # snap to a clean standstill at the WAIT edge
        # world motion is speedF along travel (current.angle.y): speed.z = speedF*cos, x = speedF*sin.
        d = self.speedF
        self.pos_x += f32(d * _cM_ssin_s16(self.travel))
        self.pos_z += f32(d * S.cM_scos_s16(self.travel))
        self._l_prev = l_held
        return d, {MOVE: "MOVE", ATN_MOVE: "ATN", WAIT: "WAIT", FREE_WAIT: "WAIT"}.get(self.state, "?")


def _is_zero(x):
    # cM3d_IsZero: |x| < 0.00001 (c_m3d.cpp). Only the exact-0 dVar9 (release) matters here.
    return abs(x) < 1.0e-5


def _dist_angle_s(a, b):
    # cLib_distanceAngleS: |signed s16 difference| (magnitude of the shortest turn).
    return abs(s16_signed(int(a) - int(b)))


def _cM_ssin_s16(angle):
    # cM_ssin on an s16 angle: sin(a) = cos(a - 0x4000). Reuses sim's baked console cos table.
    return S.cM_scos_s16((int(angle) - 0x4000) & 0xFFFF)


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
