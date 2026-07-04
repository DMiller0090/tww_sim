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
        self._single_entered = False                   # single-anim entry frame: hold the ctrl at start
        self._pending_morf = None                      # morf to apply on the next step (proc/walk entry)

    def enter_single(self, anim, morf, start=0.0, end=None, rate=1.0):
        """setSingleMoveAnime(anim, rate, start, end, morf) (12794): the under-body switches to a single
        anim (m34C3=0), so posMoveFromFootPos keeps posing the foot + updating the toe stream while m3598
        stays frozen (=> speedF stays the proc's own value: roll/slip momentum, WaitTurn frozen at 0).
        Because m34C3==0, the following walk blend re-inits its frame ctrl to 0 on the proc->MOVE exit.
        Shared by procFrontRoll_init (ANM_ROLLF), procWaitTurn_init (ANM_ROT), procSlip_init (ANM_SLIP);
        call step_single_anim() each proc frame. `end` defaults to the anim's frameMax."""
        if end is None:
            end = float(ANIM_META[anim][0])
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
        nspeed = _f32(nspeed)
        msd = _f32(msd)
        an = nspeed if anim_nspeed is None else _f32(anim_nspeed)

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
        speedF = nspeed*(1-m3598) +/- f31_2*m3598. Used by both the walk step() and the roll step_roll()."""
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
