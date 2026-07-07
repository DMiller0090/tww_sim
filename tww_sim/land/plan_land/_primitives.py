#!/usr/bin/env python3
"""plan_land/_primitives.py - shared geometry + freeze primitives for the land planner.

The world-bearing <-> full-deflection-stick inverse (`stick_for_bearing`/`world_angle_s16`), the
freeze-position read (`_freeze_pos`), and the small bit/seq helpers used across the reach modules.

COORDINATES (from state.py's position integration -- the single source of truth):
    pos_x += speedF * sin(travel);  pos_z += speedF * cos(travel)   (travel = s16 current.angle.y)
so travel is an s16 angle measured FROM +z TOWARD +x. The world bearing to a target displacement
(dx, dz) is therefore `atan2(dx, dz)` -> s16 (see `world_angle_s16`). To WALK toward a world
bearing theta we want the walk want-target `m34E8 == theta`; since `m34E8 = m34DC(stick) + csangle`
and `m34DC = stickAngle + 0x8000`, the inverse full-deflection stick is `stick_for_bearing`.

LIVE-FAITHFUL STICKS (hard-won): full deflection (255/1) and neutral (128,128) are bit-exact; a genuine
partial magnitude (msd 0.3-0.7) is bit-exact; but the sim's msd = min(hypot/54, 1) CAPS, so near-full
raw sticks (e.g. 128,197) read 1.0 in the sim while live PADClamp gives ~0.96 -- NEVER emit that
ambiguous cap-boundary cell. `stick_for_bearing` emits the true corner for msd>=1 and msd*54 below it.
"""
from __future__ import annotations
import math
import struct

from ...core.mathlib import deg_to_s16, ARROW_STICK_DEADZONE

# Dead-zoned deflection magnitude (per axis) before the 15-unit dead zone is added back per axis (see
# stick_for_bearing). _STICK_R + DZ == 127 -> cardinals hit the full corners (255/1). See land-movement.md.
_STICK_R = 112.0
NEUTRAL = (128, 128)

# The C-up speed cancel locks position FREEZE_LATENCY frames after the neutral+C-up input (2-frame
# latency + 1 cLib decel, then link_state->1); the sim reads it with zero new code. land-movement.md.
FREEZE_LATENCY = 3


def _f32_bits(x):
    """The float32 bit pattern of `x` -- for bit-exact (0-ULP) freeze-position equality checks."""
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def world_angle_s16(dx, dz):
    """World bearing of a displacement (dx, dz) as an s16 travel angle (0 = +z, 0x4000 = +x).
    Matches state.py's `pos_x += d*sin(travel); pos_z += d*cos(travel)`."""
    return deg_to_s16(math.degrees(math.atan2(dx, dz)) % 360.0)


def dist2d(state, tx, tz):
    return math.hypot(tx - state.pos_x, tz - state.pos_z)


def stick_for_bearing(theta_s16, csangle=0, msd=1.0):
    """Inverse of the walk want-target: an (sx, sy) whose camera-relative walk target
    `m34E8 = m34DC + csangle` equals the world bearing `theta_s16`. With a frozen camera
    (csangle held) this points the walk at world angle theta (see state.py `_set_stick_data`).

    `msd` (0..1) sets the target mStickDistance = min(hypot(dz)/54, 1): 1.0 = full deflection
    (walk cap 17); a small msd creeps (the speed cap is msd*(17*msd) = 17*msd^2, so msd~0.06 is
    ~0.06 u/frame) -- used by `reach_precise` for the sub-unit final approach. The dead-zoned
    magnitude is msd*54; the dead zone (15) is added back per axis so `_deadzone` recovers it."""
    m34dc = (int(theta_s16) - int(csangle)) & 0xFFFF          # m34E8 = m34dc + csangle
    stick_s16 = (m34dc - 0x8000) & 0xFFFF                     # m34dc = stickAngle + 0x8000
    phi = math.radians(stick_s16 / 65536.0 * 360.0)          # stick_angle_deg convention
    # Dead-zoned magnitude for a target mStickDistance: full (msd>=1) -> the true corner (255/1);
    # partial (msd<1) -> msd*54. LIVE-VALID only for Y<=191 or 255 (sim /54 over-reads Y192-254; land-movement.md).
    if msd >= 1.0:
        r = _STICK_R
    else:
        r = min(max(msd, 0.0), 1.0) * 54.0
    ax = r * math.sin(phi)                                   # desired dead-zoned x  (_deadzone(sx))
    ay = -r * math.cos(phi)                                  # desired dead-zoned y  (_deadzone(sy))
    # Add the dead zone back per axis so _deadzone recovers (ax, ay) and the bearing is preserved.
    # Snap the near-zero axis to center (a cardinal bearing -> sin/cos 180 is ~1e-14, not 0).
    dz = ARROW_STICK_DEADZONE
    sx = 128.0 + (math.copysign(abs(ax) + dz, ax) if abs(ax) > 1e-6 else 0.0)
    sy = 128.0 + (math.copysign(abs(ay) + dz, ay) if abs(ay) > 1e-6 else 0.0)
    return (max(0, min(255, int(round(sx)))), max(0, min(255, int(round(sy)))))


def _freeze_pos(state):
    """The FLOAT-PERFECT freeze position if the C-up speed cancel is issued from a mid-walk `state`:
    the sim position FREEZE_LATENCY neutral frames on (clone -> 3 neutrals -> read pos), where the
    real cancel locks link_state. Leaves `state` untouched. See knowledge/mechanics/land-movement.md."""
    c = state.clone()
    for _ in range(FREEZE_LATENCY):
        c.step(*NEUTRAL)
    return c


def seq_string(seq):
    """Compact per-frame stick string (matches the dolphin seq convention): 'sx,sy' per frame,
    run-length collapsed as 'sx,sy xN'. Roll plans carry a 3rd button element -- 'sx,sy+A' for the
    A-press (roll) frames (buttons & 0x100)."""
    out = []
    for st in seq:
        tok = f"{st[0]},{st[1]}"
        if len(st) > 2 and st[2] & 0x100:
            tok += "+A"
        if out and out[-1][0] == tok:
            out[-1][1] += 1
        else:
            out.append([tok, 1])
    return " ".join(t if n == 1 else f"{t} x{n}" for t, n in out)
