#!/usr/bin/env python3
"""_AtnActorMixin: the actor-lock targeting move (ATN_ACTOR_MOVE / ATN_ACTOR_WAIT, procs 9 / 8).

``setSpeedAndAngleAtnActor`` (d_a_player_main.cpp:2909) is ``setSpeedAndAngleAtn``'s side branch --
same ``mAtnMove`` speed/angle chase and the same DIR_BACKWARD negation gate -- with two differences:
it has NO forward/backward ``mDirection`` dispatch (procs 8/9 ALWAYS run this actor path), and
instead of locking facing to ``m34E6`` it re-aims ``shape_angle.y`` at the locked actor every frame
(``setShapeAngleToAtnActor``, 2625). Facing the actor keeps ``getDirectionFromCurrentAngle()`` reading
DIR_BACKWARD while sliding away from it, so the negation branch (2913: ``travel += 0x8000;
mNormalSpeed *= -1``) stays engaged -- that is the roll's +26 flipping to ~-26 (the untarget
brakeslide), then decaying with the gentle ``mAtnMove`` params instead of eating the roll's -5.0 decel.

The locked actor's world XZ is supplied by the harness as ``self._atn_actor_pos`` (Tetra, from the
coupled stepper). With none set the re-aim no-ops (``mpAttnActorLockOn == NULL`` guard), so this mixin
is inert unless a lock-on actor is actively driven. See knowledge + harness/tetrapush/README.md.
"""
from __future__ import annotations
from ...core import mathlib as S
from ...core.mathlib import f32, cM_scos_s16, s16_signed
from ..constants import DIR_BACKWARD, cLib_addCalcAngleS

# setShapeAngleToAtnActor's cLib_addCalcAngleS knobs (2629): chase shape_angle.y toward the bearing
# to the actor's eyePos at scale 2, maxStep 0x2000, minStep 0x800. Not HIO -- hard-coded in the decomp.
_SHAPE_SCALE, _SHAPE_MAX, _SHAPE_MIN = 2, 0x2000, 0x800


class _AtnActorMixin:
    def _set_shape_angle_to_atn_actor(self):
        """setShapeAngleToAtnActor (2625): chase shape_angle.y toward the bearing to the locked
        actor (cLib_targetAngleY = cM_atan2s(actor.x - pos.x, actor.z - pos.z)). No-op with no actor
        (mpAttnActorLockOn == NULL). eyePos XZ == actor.pos XZ (the head-joint Y offset doesn't turn)."""
        ap = getattr(self, "_atn_actor_pos", None)
        if ap is None:
            return
        target_angle = S.cM_atan2s(f32(ap[0] - self.pos_x), f32(ap[1] - self.pos_z))
        self.facing = cLib_addCalcAngleS(self.facing, target_angle, _SHAPE_SCALE, _SHAPE_MAX, _SHAPE_MIN)

    def _set_speed_and_angle_atn_actor(self):
        """setSpeedAndAngleAtnActor (2909): the ATN side-branch chase with the mAtnMove family, no
        mDirection split, re-aiming facing at the actor. The DIR_BACKWARD negation (travel += 0x8000,
        nspeed *= -1) flips a forward carry (the +26 out of a roll) to a backward slide toward 0."""
        if self.msd > 0.05:
            if self._get_dir_from_angle(self.target - self.travel) == DIR_BACKWARD:
                self.travel = (self.travel + 0x8000) & 0xFFFF
                self.nspeed = f32(self.nspeed * -1.0)
            old = self.travel
            self.travel = cLib_addCalcAngleS(self.travel, self.target, self.ATN_TURN_SCALE,
                                             self.ATN_TURN_MAX, self.ATN_TURN_MIN)
            f1 = f32(f32(self.ATN_SPD * self.msd) * cM_scos_s16(s16_signed(self.travel - old)))
        else:
            f1 = 0.0
        self._set_shape_angle_to_atn_actor()     # shape_angle.y re-aims at the actor (NOT the m34E6 lock)
        self._set_normal_speed_f(f1, self.ATN_SCL, self.ATN_ACC, self.ATN_DEC)
