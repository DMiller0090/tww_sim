#!/usr/bin/env python3
"""_CutMixin: the sword-thrust cuts (CUT_F 0x42 forward thrust / CUT_A 0x41 vertical slash).

The "roll stab": a cut dispatched out of a roll carries the roll's speedF into a first-frame lunge
= foot term (m3598==0 -> speedF) + the ANM_CUT joint-0 root translate (m3700). procCutF/procCutA
(d_a_player_sword.inc 660/430/690) + the J3D keyframe eval for m3700. The 49.22u lunge: KB roll-stab.
"""
from __future__ import annotations
from ...core import mathlib as S
from ...core.mathlib import f32, cLib_addCalc
from ..constants import WAIT, CUT_F, _cM_ssin_s16, cLib_addCalcAngleS, _dist_angle_s

# Module-level cache of the parsed cut anims (immutable dev data): loaded once per process, so a fresh
# search clone's first enter_cut never re-walks the tree for pyproject.toml nor re-reads the JSON.
_ANIM_CACHE = None


def _load_cut_anims():
    global _ANIM_CACHE
    if _ANIM_CACHE is None:
        from ...core.anim import j3d_eval as _J
        import os as _os
        rb = _os.path.dirname(_os.path.abspath(__file__))
        while rb != _os.path.dirname(rb) and not _os.path.exists(_os.path.join(rb, 'pyproject.toml')):
            rb = _os.path.dirname(rb)
        path = _os.path.join(rb, '_generated', 'anim', 'link_anim_cuts.json')
        _ANIM_CACHE = _J.load_anim(path)
    return _ANIM_CACHE


class _CutMixin:
    # --- sword-thrust cut procs (CUT_F 0x42 forward thrust / CUT_A 0x41 vertical slash) --------
    def _cut_anim(self, cut_type):
        """The parsed cutf/cuta BCK (core.anim.j3d_eval). Module-cached (see _load_cut_anims). The
        joint-0 translate track is the CUT's root-motion lunge (m3700). Dev-supplied keyframe data
        (gitignored _generated/anim/link_anim_cuts.json); regenerate harness/anim/parse_bck.py."""
        if self._cut_anim_cache is None:
            self._cut_anim_cache = _load_cut_anims()
        return self._cut_anim_cache[self.CUT_ANIM[cut_type]]

    def _cut_m3700_at(self, cut_type, frame):
        """m3700 = the CUT anim's joint-0 (root) mTranslate at `frame`, via the J3D keyframe eval
        (posMove reads getAnmTransform(0).getTransform(0); MOVE1 is NULL for a setSingleMoveAnime cut,
        so there is no blend). Bit-exact vs the live m3700 (0 ULP)."""
        from ...core.anim import j3d_eval as _J
        t = _J.calc_transform(self._cut_anim(cut_type), 0, frame)['translate']
        return (f32(t[0]), f32(t[1]), f32(t[2]))

    def _cut_init(self, cut_type, aim=None):
        """procCutF_init / procCutA_init (d_a_player_sword.inc:660/430): setSingleMoveAnime(ANM_CUT*,
        rate=1.2, start=4.0, ...); m3700 = 0; m34C2 = 1. mNormalSpeed keeps the entry value (the roll's
        carried speedF) this frame. current.angle.y = shape_angle.y (travel snaps to facing).

        `aim` = mProcVar2.m34D4 (the thrust's latched aim, param_0 in changeCutProc = sVar2 = the stick
        target m34E8 when the stick is pushed & unlocked, else shape_angle.y). None -> straight-forward
        (aim == the roll facing): shape never turns, the classic in-line lunge. A diagonal aim snaps
        shape=travel to it on the FIRST proc frame (see _proc_cut), rotating the whole tail."""
        self.state = cut_type
        self.cut_frame = self.CUT_START
        self._cut_entered = True
        self._cut_m3700 = (0.0, 0.0, 0.0)        # m3700 = cXyz::Zero in init
        self.cut_target = self.facing if aim is None else (int(aim) & 0xFFFF)   # mProcVar2.m34D4
        self.travel = self.facing                # current.angle.y = shape_angle.y (procCutF sets it)
        # No foot-engine pose: the cut anim isn't a foot-chain walk anim and m3598 stays 0 (speedF==nspeed),
        # so position = joint-0 root lunge (_cut_m3700_at) + mNormalSpeed. Toe stream freezes (see the KB).

    def _proc_cut(self, l_held):
        """One CUT_F/CUT_A frame (procCutF/procCutA d_a_player_sword.inc:690/...). The frame ctrl advances
        (+1.2, EMode_NONE), then: getFrame()>field_0xC -> checkNextMode(1) exit to WAIT; checkPass(6.0) ->
        mNormalSpeed = |speedF|*0.2 + add; every frame cLib_addCalc decel. Entry frame: no advance, nspeed
        carried. Position (the root-translate lunge) is applied in the shared pos block via _cut_add."""
        ct = self.state
        # No entry skip: init is dispatched under the roll, so _proc_cut first runs the frame AFTER init
        # (the entry lunge is the pos block on the init frame). Advance the MOVE0 ctrl (EMode_NONE) below.
        fc = f32(self.cut_frame + self.CUT_RATE)
        if fc < self.CUT_START:
            fc = self.CUT_START
        end_clamp = f32(self.CUT_END - 0.001)
        if fc >= self.CUT_END:
            fc = end_clamp
        self.cut_frame = fc
        # exit: getFrame() > field_0xC (early-out; a held sword re-fires, but the neutral tail ends here)
        if fc > self.CUT_EARLY[ct]:
            self.state = WAIT
            self.nspeed = 0.0
            if self._foot is not None:
                self._foot._pending_morf = self.MOVE_REENTRY_MORF
            return
        # Diagonal-thrust aim (procCutF/A, after the exit check): snap shape=travel toward the latched
        # m34D4 (rotates the tail; entry lunge stayed in-line). KB mechanics/roll-stab.md (Steering).
        if self.cut_target is not None and self.cut_target != self.facing:
            self.facing = cLib_addCalcAngleS(self.facing, self.cut_target, self.CUT_TURN_SCALE,
                                             self.CUT_TURN_MAX, self.CUT_TURN_MIN)
        self.travel = self.facing
        # checkPass(field_0x28): launch mNormalSpeed off the pre-cut speedF
        if self._checkpass_none(fc, self.CUT_RATE, self.CUT_START, self.CUT_END, self.CUT_PASS):
            self.nspeed = f32(f32(abs(self.speedF) * self.CUT_LAUNCH_MUL) + self.CUT_LAUNCH_ADD[ct])
        self.nspeed = cLib_addCalc(self.nspeed, 0.0, self.CUT_DEC_SCALE, self.CUT_DEC_MAX[ct], self.CUT_DEC_MIN)

    @staticmethod
    def _checkpass_none(frame, rate, start, end, pass_frame):
        """J3DFrameCtrl::checkPass, EMode_NONE arm (J3DAnimation.cpp:24): true iff pass_frame is crossed
        this update. `frame` is the CURRENT (already-advanced) frame; it recomputes next internally."""
        cur = frame
        nxt = f32(cur + rate)
        if nxt < start:
            nxt = start
        if nxt >= end:
            nxt = f32(end - 0.001)
        if cur <= nxt:
            return cur <= pass_frame and pass_frame < nxt
        return nxt <= pass_frame and pass_frame < cur

    def enter_cut(self, cut_type=CUT_F, aim=None):
        """Programmatic roll-stab: run the CUT's ENTRY frame from the current state (mirrors the game's
        procCut*_init frame, dispatched out of a roll). Carries the current speedF into the first-frame
        lunge = speedF (foot term, m3598==0) + the ANM_CUT joint-0 root translate at frame 4.0 (m3700,
        reset to 0 in init) -- the ~49.22u single-frame move that reaches the seam-clip floor. Advance the
        rest of the animation with step() (which dispatches _proc_cut) until it returns to WAIT (idle).

        `aim` (s16 world angle) = the DIAGONAL-thrust aim (mProcVar2.m34D4 = the stick target m34E8 sampled
        at the thrust frame). None -> a straight in-line thrust (aim == the roll facing). The entry lunge
        always fires along the roll facing; a diagonal aim only rotates the CUT TAIL (shape snaps to it on
        the first proc frame). Fires CUT_F only while |aim - facing| < CUT_DIR_FWD (0x2000 = 45deg); a
        larger aim would dispatch CUT_L / CUT_R instead (getDirectionFromAngle) -- caller must respect that.
        Returns the entry-frame (dx, dz). Requires native=False (the cut is a Python-path proc)."""
        if self._core is not None:
            raise RuntimeError("enter_cut is a Python-path proc; construct LandState(native=False)")
        if aim is not None and _dist_angle_s(int(aim) & 0xFFFF, self.facing) >= self.CUT_DIR_FWD:
            raise ValueError("aim %d is >= 0x2000 off the roll facing %d -> dispatches CUT_L/R, not %s; "
                             "the in-line CUT_F/A range is +-0x2000 (45deg)" % (int(aim) & 0xFFFF,
                             self.facing, "CUT_F" if cut_type == CUT_F else "CUT_A"))
        self._cut_init(cut_type, aim=aim)            # state=CUT*, cut_frame=4.0, m3700_prev=0, travel=facing
        # --- entry frame pos update (mirrors the step() pos-block CUT branch) ---
        self.speedF = 0.0 if abs(self.nspeed) < 0.05 else self.nspeed
        m3700 = self._cut_m3700_at(cut_type, self.cut_frame)
        sp5c = (f32(m3700[0] - self._cut_m3700[0]), f32(m3700[1] - self._cut_m3700[1]),
                f32(m3700[2] - self._cut_m3700[2]))
        self._cut_m3700 = m3700
        s = _cM_ssin_s16(self.facing); c = S.cM_scos_s16(self.facing)
        add_x = f32(f32(sp5c[2] * s) + f32(sp5c[0] * c))
        add_z = f32(f32(sp5c[2] * c) - f32(sp5c[0] * s))
        px0, pz0 = self.pos_x, self.pos_z
        self.pos_x = f32(f32(self.pos_x + f32(self.speedF * _cM_ssin_s16(self.travel))) + add_x)
        self.pos_z = f32(f32(self.pos_z + f32(self.speedF * S.cM_scos_s16(self.travel))) + add_z)
        self.visited.add(cut_type)
        return (f32(self.pos_x - px0), f32(self.pos_z - pz0))
