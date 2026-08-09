#!/usr/bin/env python3
"""The junction's arming bar is the ROLL CLAMP'S KNEE, not a tuned constant (session 138).

`two_roll.junction_gates` refuses an endpoint whose 1-frame probe reads
``speedF < min_preroll = 17.0``. That number is not free: `_roll_init` (procFrontRoll_init 6817) sets
the roll from the pre-roll speed as ``clamp(speedF * ROLL_SPD + ROLL_ADD, ROLL_MIN, cap)`` with
``cap = ROLL_ADD + MAX_NSPEED * ROLL_SPD``, so ``min_preroll`` is exactly the speed at which that
clamp SATURATES -- and one unit below it costs exactly ``ROLL_SPD`` u/frame of roll.

Session 138's census turns on both halves (`knowledge/strategy/
the-biggest-death-counter-was-the-alphabet.md`): the bar refuses 5677 children whose rolls are at
most 5.8% weaker, so the price of relaxing it is this slope and nothing else. Pin it, so a session
that wants to move ``min_preroll`` has to see the knee it is standing on -- and so a change to the
roll constants cannot silently make the bar mean something different.

Offline, no Dolphin, no anim: constructs `LandState` directly and calls the proc.
"""
# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
import inspect

from harness.tetrapush import two_roll as T
from tww_sim.core.mathlib import f32
from tww_sim.land import LandState


def _roll_speed(pre):
    """The roll `_roll_init` fires from a pre-roll ``speedF``, through the real proc."""
    s = LandState(native=False, use_anim=False)
    s.speedF = f32(pre)
    s._roll_init()
    return s.nspeed


def test_the_arming_bar_is_the_roll_clamp_knee():
    """``min_preroll`` is the exact speed at which the roll clamp saturates."""
    s = LandState(native=False, use_anim=False)
    bar = inspect.signature(T.junction_gates).parameters['min_preroll'].default
    cap = f32(s.ROLL_ADD + f32(s.MAX_NSPEED * s.ROLL_SPD))

    assert _roll_speed(bar) == cap, 'the bar must reach the full clamp'
    # ...and it is the LOWEST such speed: one ULP under the bar is already under the cap.
    import struct
    below = struct.unpack('<f', struct.pack('<I', struct.unpack(
        '<I', struct.pack('<f', bar))[0] - 1))[0]
    assert _roll_speed(below) < cap, 'the bar is not the knee -- a lower speedF also clamps'


def test_one_unit_of_arming_deficit_costs_exactly_one_roll_slope():
    """Below the knee the roll is affine in the pre-roll speed, at ``ROLL_SPD`` u/frame per unit.

    This is what prices any proposal to relax the bar: the census' 5677 refusals in [16, 17) fire a
    24.50-26.00 roll, at most 5.8% under the clamp."""
    s = LandState(native=False, use_anim=False)
    bar = inspect.signature(T.junction_gates).parameters['min_preroll'].default
    cap = f32(s.ROLL_ADD + f32(s.MAX_NSPEED * s.ROLL_SPD))

    for deficit in (0.5, 1.0, 2.0, 5.0):
        got = _roll_speed(bar - deficit)
        want = f32(f32(f32(bar - deficit) * s.ROLL_SPD) + s.ROLL_ADD)
        assert got == want, 'roll is not affine below the knee at deficit %.1f' % deficit
        # the slope, stated the way the KB page states it
        assert abs((cap - got) - deficit * s.ROLL_SPD) < 1e-4

    # the census' own band, in the units it quotes
    assert abs(_roll_speed(bar - 1.0) - 24.5) < 1e-6
    assert _roll_speed(bar - 1.0) / cap > 0.94                # <= 5.8% weaker


def test_the_floor_is_the_weak_graze_not_zero():
    """Far below the knee the clamp floors at ``ROLL_MIN`` -- the '+5 graze' the gate exists to
    avoid, which is why the bar is a gate at all and not merely a rank."""
    s = LandState(native=False, use_anim=False)
    assert _roll_speed(0.0) == f32(s.ROLL_MIN)
    assert _roll_speed(-25.7) == f32(s.ROLL_MIN)              # a backslide rolls at the graze
