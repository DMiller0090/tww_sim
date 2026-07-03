"""anim_state.py - port of Link's under-body movement anim STATE MACHINE, driven by mNormalSpeed.

Reproduces, offline and bit-faithfully, the per-frame animation blend state that the game computes
in daPy_lk_c::setBlendMoveAnime -> setMoveAnime -> J3DFrameCtrl::update (d_a_player_main.cpp:2966,
12723; J3DAnimation.cpp:143). Output per game frame: which anims occupy MOVE0/MOVE1, the two
frame-controller frame values + rates, the blend ratio (getRatio(1)), and m3598 (the WALK<->DASH
speedF blend). Feed the frame/ratio into the FK (fk.foot_toe_blend) to get the model-local toe,
then posMoveFromFootPos -> f31_2 -> speedF. This is the offline replacement for reading the live
frame controllers, so the land route planner can predict transient walk position with no Dolphin.

SCOPE: the normal flat, on-axis, free (non-attention/heavy/grab/slope/ice) walk. The regime
selection picks r28=WAITS, r27=WALK, r26=DASH; the observed arc is FREEB(entry)->WAITS->WALK->DASH
and back. Other movement modes (attention strafe, heavy boots, slopes, ice slip) take other branches
of setBlendMoveAnime and are out of scope here.

Everything hand-verified bit-exact vs a live flat-walk arc (see tests): the rate formula
f27r = f28 + f27*((f25*f3/f26) - f28), rate1 = f27r*f26/f3, phase preservation frame = (old/oldMax)*newMax,
and the m3598 closed forms all match the live capture to the value.

HIO tuning constants (daPy_HIO_move_c0::m, d_a_player_HIO_data.inc) used here:
  field_0x18 (mMaxNormalSpeed src) = 17.0 ; field_0x2C = 0.5 (WAITS<->WALK thresh);
  field_0x30 = 1.0 (WALK<->DASH thresh); field_0x38 = 1.1 ; field_0x40 (f29) = 0.8 ;
  field_0x48 = 2.3 (DASH cruise rate) ; field_0x60 (f28 free) = 1.0.
Anim frame maxima are plain metadata (not copyrighted keyframe data).
"""
from superswim import fp

# --- J3DFrameCtrl attribute modes (J3DAnimation.h) -----------------------------------------------
EMode_NONE, EMode_RESET, EMode_LOOP, EMode_REVERSE, EMode_LOOP_REVERSE = 0, 1, 2, 3, 4

# anim metadata (frameMax, attribute) -- from parse_bck; small integers, not copyrighted data.
ANIM_META = {
    'freeb': (244, EMode_NONE),
    'waits': (60, EMode_LOOP),
    'walk':  (32, EMode_LOOP),
    'dash':  (32, EMode_LOOP),
}

# HIO daPy_HIO_move_c0::m constants (the flat free-walk subset).
H_MAXSPEED = 17.0     # mMaxNormalSpeed
H_2C = 0.5            # WAITS<->WALK regime threshold (field_0x2C)
H_30 = 1.0           # WALK<->DASH regime threshold (field_0x30)
H_38 = 1.1           # field_0x38 (regime-1 f28)
H_40 = 0.8           # field_0x40 (f29)
H_48 = 2.3           # field_0x48 (DASH cruise rate / regime-2 f25)
H_60 = 1.0           # field_0x60 (free-walk f28)


class FrameCtrl:
    """J3DFrameCtrl: frame + rate + [start,end) + loop mode. update() = J3DAnimation.cpp:143."""
    __slots__ = ('attribute', 'start', 'end', 'loop', 'rate', 'frame')

    def __init__(self):
        self.attribute = EMode_LOOP
        self.start = 0.0
        self.end = 1.0
        self.loop = 0.0
        self.rate = 0.0
        self.frame = 0.0

    def set(self, attribute, start, end, rate, frame):
        """daPy_lk_c::setFrameCtrl (12938): loop = start if rate>=0 else end."""
        self.attribute = attribute
        self.end = float(end)
        self.rate = float(rate)
        self.start = float(start)
        self.frame = float(frame)
        self.loop = float(start) if rate >= 0.0 else float(end)

    def update(self):
        """J3DFrameCtrl::update: mFrame += mRate then wrap/clamp per attribute (f32 throughout)."""
        self.frame = fp.fadds(self.frame, self.rate)
        a = self.attribute
        if a == EMode_NONE:
            if self.frame < self.start:
                self.frame = self.start; self.rate = 0.0
            if self.frame >= self.end:
                self.frame = fp.fsubs(self.end, 0.001); self.rate = 0.0
        elif a == EMode_RESET:
            if self.frame < self.start:
                self.frame = self.start; self.rate = 0.0
            if self.frame >= self.end:
                self.frame = self.start; self.rate = 0.0
        elif a == EMode_LOOP:
            while self.frame < self.start:
                if self.loop - self.start <= 0.0:
                    break
                self.frame = fp.fadds(self.frame, fp.fsubs(self.loop, self.start))
            while self.frame >= self.end:
                if self.end - self.loop <= 0.0:
                    break
                self.frame = fp.fsubs(self.frame, fp.fsubs(self.end, self.loop))
        elif a == EMode_REVERSE:
            if self.frame >= self.end:
                self.frame = fp.fsubs(self.end, 0.001); self.rate = -self.rate
            if self.frame < self.start:
                self.frame = self.start; self.rate = 0.0
        elif a == EMode_LOOP_REVERSE:
            if self.frame >= self.end:
                self.frame = fp.fsubs(self.end, 0.001); self.rate = -self.rate
            if self.frame < self.start:
                self.frame = self.start; self.rate = -self.rate


class UnderAnimState:
    """The under-body (foot chain) two-anim blend state. step(nspeed) advances one game frame and
    returns the per-frame render state. Start it at the anchor with the live MOVE0 anim + frame."""

    def __init__(self, move0_anim='waits', move0_frame=0.0, move1_anim=None, m34C3=1):
        self.fc0 = FrameCtrl()
        self.fc1 = FrameCtrl()
        self.move0 = move0_anim
        self.move1 = move1_anim
        self.m34C3 = m34C3          # current blend-anim state id (0 = single, else the r29)
        self.ratio = 0.0            # getRatio(1) = walk-slot weight
        self.m3598 = 0.0
        self.fc0.frame = float(move0_frame)
        self.fc0.end = float(ANIM_META[move0_anim][0])
        self.fc0.attribute = ANIM_META[move0_anim][1]

    def _set_move_anime(self, f27, f28, f25, r27, r28, r29, i_morf):
        """daPy_lk_c::setMoveAnime (12723): r27->MOVE0, r28->MOVE1, ratio f27->MOVE1 (1-f27->MOVE0).
        Preserves anim phase across a swap and computes the two frame-ctrl rates. Returns (i_morf>=0)
        so the caller can trigger oldframe-morf. f31 (phase) uses the CURRENT MOVE0 anim's frame."""
        if self.m34C3 in (0, 9, 10):
            f31 = 0.0
        else:
            f31 = fp.fdivs(self.fc0.frame, float(ANIM_META[self.move0][0]))
        self.ratio = f27
        f3 = float(ANIM_META[r27][0])          # new MOVE0 frameMax
        f26 = float(ANIM_META[r28][0])         # new MOVE1 frameMax
        f30 = fp.fdivs(1.0, f3)
        # f27 = f28 + f27*((f25*f3/f26) - f28)   -- the new MOVE0 rate
        f27r = fp.fadds(f28, fp.fmuls(f27, fp.fsubs(fp.fdivs(fp.fmuls(f25, f3), f26), f28)))
        attr0 = ANIM_META[r27][1]
        attr1 = ANIM_META[r28][1]
        self.fc0.set(attr0, 0, f3, f27r, fp.fmuls(f31, f3))
        self.fc1.set(attr1, 0, f26, fp.fmuls(f30, fp.fmuls(f27r, f26)), fp.fmuls(f31, f26))
        self.move0, self.move1, self.m34C3 = r27, r28, r29
        return i_morf >= 0.0

    def _set_blend_move_anime(self, nspeed, m34E2_cos=1.0, i_morf=-1.0):
        """daPy_lk_c::setBlendMoveAnime (2966), flat free-walk path. Returns whether morf triggered."""
        f30 = fp.fdivs(abs(fp.fmuls(nspeed, m34E2_cos)), H_MAXSPEED)
        morf = False
        if f30 < H_2C:                                   # regime 1: WAITS <-> WALK
            f25_2 = fp.fdivs(f30, H_2C)
            self.m3598 = fp.fsubs(1.0, fp.fmuls(fp.fsubs(1.0, H_60), f25_2))
            morf = self._set_move_anime(f25_2, H_38, H_40, 'waits', 'walk', 1, i_morf)
        elif f30 < H_30:                                 # regime 2: WALK <-> DASH
            f1 = fp.fdivs(fp.fsubs(f30, H_2C), fp.fsubs(H_30, H_2C))
            morf = self._set_move_anime(f1, H_40, H_48, 'walk', 'dash', 1, i_morf)
            self.m3598 = fp.fmuls(H_60, fp.fsubs(1.0, f1))
        else:                                            # regime 3: DASH cruise
            morf = self._set_move_anime(1.0, H_48, H_48, 'dash', 'dash', 1, i_morf)
            self.m3598 = 0.0
        return morf

    def step(self, nspeed, m34E2_cos=1.0, i_morf=-1.0):
        """Advance one game frame at the given (already bit-exact) mNormalSpeed. Returns the render
        state for THIS game frame: move0/move1 anim names, f0/f1 the frame-ctrl frames the model
        DRAWS with this frame, ratio, m3598, morf. Order matches the game: the frame controllers
        advance at frame start (J3DFrameCtrl::update), THEN setBlendMoveAnime re-poses at the new
        phase; the register value the game exposes (and draws with) is the post-setBlendMoveAnime
        value. posMoveFromFootPos consumes the PREVIOUS frame's drawn toe, so f31_2 at frame N pairs
        the toe from f0 here with the toe from the prior step()."""
        self.fc0.update()
        self.fc1.update()
        morf = self._set_blend_move_anime(nspeed, m34E2_cos, i_morf)
        return dict(move0=self.move0, move1=self.move1, f0=self.fc0.frame, f1=self.fc1.frame,
                    ratio=self.ratio, m3598=self.m3598, morf=morf)
