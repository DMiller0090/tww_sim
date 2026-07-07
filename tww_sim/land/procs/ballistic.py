#!/usr/bin/env python3
"""_BallisticMixin: the targeted ballistic hops (sidehop SIDE_STEP / backflip BACK_JUMP + lands).

L-held + A + directional stick -> a JUMP proc: pure momentum + gravity, no foot-plant (m3598==0),
so position is scalar-exact without the anim engine. procSideStep/procBackJump (d_a_player_main.cpp
6313/7003) + the recovery lands (6365/7042). The C twin does not implement these -> native=False.
"""
from __future__ import annotations
from ...core import mathlib as S
from ...core.mathlib import f32
from ..constants import (SIDE_STEP, SIDE_STEP_LAND, BACK_JUMP, BACK_JUMP_LAND,
                         DIR_LEFT, DIR_BACKWARD, _cM_ssin_s16)


class _BallisticMixin:
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
