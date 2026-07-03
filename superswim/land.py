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

# link_state / daPyProc values (d_a_player_main.h). Only the walk trio is modelled here.
WAIT = 4          # daPyProc_WAIT_e         (idle standstill)
FREE_WAIT = 5     # daPyProc_FREE_WAIT_e    (anchor's resting proc)
MOVE = 6          # daPyProc_MOVE_e         (ground locomotion)

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
        # 2-frame controller-input buffer (index 0 = oldest = the input acted on this frame).
        self._inbuf = [(128, 128)] * INPUT_DELAY
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
        dVar10 = f32(self.msd * f32(self.MAX_NSPEED * self.msd))   # target/cap speed
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
    def _set_speed_and_angle_normal(self, param_1):
        """Compute the target-speed scalar dVar9 from the stick + the facing/travel-vs-target
        angle, chase the two angles toward m34E8, then hand dVar9 to setNormalSpeedF. Walk
        path only: not attention-locked, not MOVE_TURN, no event/heavy/grab."""
        if self.msd > 0.05:
            dVar11 = f32(self.msd * self.msd)
            # Aligned branch (walk): m34E8 within 0x7800 of travel -> chase travel + keep the
            # cM_scos speed scale. The >0x7800 near-reversal branch is a next-tier concern.
            if _dist_angle_s(self.target, self.travel) > 0x7800:
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
                if self.nspeed > f32(0.5 * self.MAX_NSPEED):
                    if dVar9 < 0.7:
                        dVar9 = f32(0.7)
                elif dVar9 < 0.0:
                    dVar9 = 0.0
                dVar10 = f32(0.5 - f32(0.5 * abs(f32(self.nspeed / self.MAX_NSPEED))))
                if self.msd > dVar10:
                    dVar9 = f32(dVar9 * f32(self.F14 * dVar11))
                else:
                    dVar9 = 0.0
        else:
            dVar9 = 0.0
        # facing (shape_angle.y) chases m34E8 at DOUBLE the travel rate (<<1); if the chase
        # crosses travel it snaps onto it. On-axis walk: no-op. (2834-2845)
        if self.msd > 0.05:
            sVar6 = self.facing
            self.facing = cLib_addCalcAngleS(self.facing, self.target, self.F6,
                                             (param_1 << 1) & 0xFFFF, (self.F4 << 1) & 0xFFFF)
            temp = s16_signed(sVar6 - self.travel)
            temp2 = s16_signed(self.facing - self.travel)
            if temp * temp2 <= 0:
                self.facing = self.travel
        self._set_normal_speed_f(dVar9, self.F24, self.F1C, self.F20)

    # --- proc dispatch + per-frame step ----------------------------------------------------
    def step(self, sx, sy):
        """Advance one frame with a raw stick (sx, sy). Returns (d_pos, tag). csangle is held
        in self.csangle (set it before stepping to steer the camera-relative target)."""
        # 2-frame controller latency: act on the input delivered INPUT_DELAY frames ago.
        self._inbuf.append((int(sx), int(sy)))
        asx, asy = self._inbuf.pop(0)
        self._set_stick_data(asx, asy)

        moving = self.msd > 0.05
        # transition arbitration (pre-dispatch): idle + movement stick -> enter procMove.
        if self.state in (WAIT, FREE_WAIT) and moving:
            self.state = MOVE                    # procMove_init
        # dispatch
        if self.state == MOVE:
            self._set_speed_and_angle_normal(self.F0)
            # checkNextMode: stopped (neutral stick, speed bled to 0) -> back to WAIT (idle).
            if not moving and self.nspeed <= 0.0:
                self.state = WAIT
        # else WAIT/FREE_WAIT with no input: nspeed stays 0, no movement.

        # speedF -> position via the bit-exact anim engine (ported posMoveFromFootPos), stepped every
        # frame (advances the standing idle so the entry drift is exact); cLib chase only as fallback.
        if self._foot is not None:
            self.speedF = self._foot.step(self.nspeed, self.msd)
        else:
            sc, mx, mn = SPEEDF_CHASE
            self.speedF = cLib_addCalc(self.speedF, self.nspeed, sc, mx, mn)
            if self.nspeed == 0.0 and self.speedF < 0.5:
                self.speedF = 0.0                # snap to a clean standstill at the WAIT edge
        # world motion is speedF along travel (current.angle.y): speed.z = speedF*cos, x = speedF*sin.
        d = self.speedF
        self.pos_x += f32(d * _cM_ssin_s16(self.travel))
        self.pos_z += f32(d * S.cM_scos_s16(self.travel))
        return d, ("MOVE" if self.state == MOVE else "WAIT")


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
