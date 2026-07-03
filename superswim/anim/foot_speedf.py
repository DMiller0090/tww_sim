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
from .anim_state import UnderAnimState, ANIM_META

IDLE_ANIM = 'freeb'
# posMoveFromFootPos rest offset used only when oldFrameFlg==false (Link never posed the walk yet).
# Not reached from a standing anchor (flag already true); kept for provenance.
REST_TOE = ((-14.05, 0.0, 5.02), (14.05, 0.0, 5.02))   # [right, left]


def _f32(x):
    return fp.f32(float(x))


def _plant_of(feet):
    """m34BC on flat ground: index (0=right jnt39, 1=left jnt34) of the lower toe/heel midpoint Y."""
    midY = [_f32((feet['toe'][k][1] + feet['heel'][k][1]) * 0.5) for k in (0, 1)]
    return 0 if midY[0] < midY[1] else 1


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

    def __init__(self, idle_frame=70.0, idle_anim=IDLE_ANIM):
        self.anm, self.sk = fk.load()                 # raises if the data is absent
        self.idle_anim = idle_anim
        self.idle_frame = float(idle_frame)
        self.idle_end = float(ANIM_META[idle_anim][0])
        self.st = UnderAnimState(move0_anim=idle_anim, move0_frame=self.idle_frame, m34C3=0)
        from .foot_fk import FootFK
        self.ff = FootFK(self.anm, self.sk)
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

    def _shift(self, cur, f312, msd):
        self.m35B4 = _f32(msd)
        self.t2 = self.t1
        self.t1 = cur
        self.prev_f312 = f312

    def step(self, nspeed, msd):
        """Advance one frame. `nspeed` = mNormalSpeed (bit-exact from LandState), `msd` =
        mStickDistance (the acted-on/latency-delayed stick magnitude). Returns speedF."""
        nspeed = _f32(nspeed)
        msd = _f32(msd)

        if not self.started:
            if nspeed <= 0.0:
                # input-latency / standing frame: keep drawing the idle so its drift is carried
                # into the toe stream; the game's m3598 here is 0 so speedF is 0 regardless.
                self.idle_frame = fp.fadds(self.idle_frame, 1.0)
                cur = self.ff.step_feet(self.idle_anim, self.idle_anim,
                                        self.idle_frame, self.idle_frame, 0.0, -1.0)
                self._shift(cur, 0.0, msd)
                return 0.0
            self.started = True
            morf = 2.4                                # oldframe-morf triggers at walk-proc entry
        elif nspeed <= 0.0:
            # MOVE proc is exiting (speed bled to 0): position update stops, speedF = 0.
            self.stopped = True
            self.m35B4 = msd
            return 0.0
        else:
            morf = -1.0

        state = self.st.step(nspeed)
        cur = self.ff.step_feet(state['move0'], state['move1'], state['f0'], state['f1'],
                                state['ratio'], i_morf=morf)
        # spB0 = the toe DRAWN last frame (1-frame delay) = t1; prevStored = t2.
        plant = _plant_of(self.t1)
        dx = _f32(self.t1['toe'][plant][0] - self.t2['toe'][plant][0])
        dz = _f32(self.t1['toe'][plant][2] - self.t2['toe'][plant][2])
        f312 = _f32(math.hypot(dx, dz))
        m = state['m3598']
        # recursive smoothing, gated by m3598<1 AND |prev_msd - msd| < 0.2 (stick-mag steady).
        if m < 1.0 and abs(_f32(self.m35B4 - msd)) < 0.2:
            f312 = _f32(_f32(f312 * 0.3) + _f32(0.7 * self.prev_f312))
        spz = _f32(nspeed * _f32(1.0 - m))
        spz = _f32(spz + _f32(f312 * m)) if nspeed >= 0.0 else _f32(spz - _f32(f312 * m))
        speedF = 0.0 if abs(spz) < 0.05 else spz
        self._shift(cur, f312, msd)
        return speedF
