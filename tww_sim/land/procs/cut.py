#!/usr/bin/env python3
"""_CutMixin: the sword-thrust cuts (CUT_F 0x42 forward thrust / CUT_A 0x41 vertical slash).

The "roll stab": a cut dispatched out of a roll carries the roll's speedF into a first-frame lunge
= foot term (m3598==0 -> speedF) + the ANM_CUT joint-0 root translate (m3700). procCutF/procCutA
(d_a_player_sword.inc 660/430/690) + the J3D keyframe eval for m3700. The 49.22u lunge: KB roll-stab.
"""
from __future__ import annotations
from ...core import mathlib as S
from ...core.mathlib import f32, cLib_addCalc
from ..constants import WAIT, CUT_F, _cM_ssin_s16


class _CutMixin:
    # --- sword-thrust cut procs (CUT_F 0x42 forward thrust / CUT_A 0x41 vertical slash) --------
    def _cut_anim(self, cut_type):
        """The parsed cutf/cuta BCK (core.anim.j3d_eval). Lazy + cached on the instance. The joint-0
        translate track is the CUT's root-motion lunge (m3700). Dev-supplied keyframe data (gitignored
        _generated/anim/link_anim_cuts.json); regenerate with harness/anim/parse_bck.py (cutf,cuta)."""
        if self._cut_anim_cache is None:
            from ...core.anim import j3d_eval as _J
            import os as _os
            here = _os.path.dirname(_os.path.abspath(__file__))
            rb = here
            while rb != _os.path.dirname(rb) and not _os.path.exists(_os.path.join(rb, 'pyproject.toml')):
                rb = _os.path.dirname(rb)
            path = _os.path.join(rb, '_generated', 'anim', 'link_anim_cuts.json')
            self._cut_anim_cache = _J.load_anim(path)
        return self._cut_anim_cache[self.CUT_ANIM[cut_type]]

    def _cut_m3700_at(self, cut_type, frame):
        """m3700 = the CUT anim's joint-0 (root) mTranslate at `frame`, via the J3D keyframe eval
        (posMove reads getAnmTransform(0).getTransform(0); MOVE1 is NULL for a setSingleMoveAnime cut,
        so there is no blend). Bit-exact vs the live m3700 (0 ULP)."""
        from ...core.anim import j3d_eval as _J
        t = _J.calc_transform(self._cut_anim(cut_type), 0, frame)['translate']
        return (f32(t[0]), f32(t[1]), f32(t[2]))

    def _cut_init(self, cut_type):
        """procCutF_init / procCutA_init (d_a_player_sword.inc:660/430): setSingleMoveAnime(ANM_CUT*,
        rate=1.2, start=4.0, ...); m3700 = 0; m34C2 = 1. mNormalSpeed keeps the entry value (the roll's
        carried speedF) this frame. current.angle.y = shape_angle.y (travel snaps to facing)."""
        self.state = cut_type
        self.cut_frame = self.CUT_START
        self._cut_entered = True
        self._cut_m3700 = (0.0, 0.0, 0.0)        # m3700 = cXyz::Zero in init
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

    def enter_cut(self, cut_type=CUT_F):
        """Programmatic roll-stab: run the CUT's ENTRY frame from the current state (mirrors the game's
        procCut*_init frame, dispatched out of a roll). Carries the current speedF into the first-frame
        lunge = speedF (foot term, m3598==0) + the ANM_CUT joint-0 root translate at frame 4.0 (m3700,
        reset to 0 in init) -- the ~49.22u single-frame move that reaches the seam-clip floor. Advance the
        rest of the animation with step() (which dispatches _proc_cut) until it returns to WAIT (idle).
        Returns the entry-frame (dx, dz). Requires native=False (the cut is a Python-path proc)."""
        if self._core is not None:
            raise RuntimeError("enter_cut is a Python-path proc; construct LandState(native=False)")
        self._cut_init(cut_type)                     # state=CUT*, cut_frame=4.0, m3700_prev=0, travel=facing
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
