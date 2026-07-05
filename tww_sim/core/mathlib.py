#!/usr/bin/env python3
"""tww_sim.core.mathlib — the console math primitives shared by every component.

Gekko/Broadway (PPC 750CL) faithful f32 trig + helpers, split out of the old swim
``sim.py`` so land, swim, anim, and the future collision core can import ONLY these
(no swim-physics dependency). ``f32`` and the fused ops live in :mod:`tww_sim.core.fp`;
this module owns the console cosine/sine tables, ``cM_scos``/``cM_ssin``, ``cLib_addCalc``,
the ``J3DFrameCtrl`` loop (``fc_update``), the s16 angle helpers, and the stick dead-zone /
angle primitives. All bit-exact vs Dolphin (see knowledge/model/fp-faithfulness.md).
"""
import math, struct
import os as _os

from .fp import f32

def nfmod(a, n):
    return a - math.floor(a / n) * n

def fc_update(frame, rate, end, start=0.0, loop=0.0):
    """Faithful J3DFrameCtrl::update() LOOP mode (J3DAnimation.cpp:143-186): advance by
    mRate, then loop by REPEATED f32 subtraction of (mEnd - mLoop) -- NOT a single modulo.
    For frames already in [start, end+rate) this is one subtraction == nfmod (so the no-pump
    baselines stay bit-exact). It ONLY differs after the x598 pump scramble, where mFrame
    is ~15232 and the game subtracts (end-loop) ~662 times in f32: that accumulated f32
    rounding is the ~0.004 entry residual that compounded across pump cycles under nfmod.
    SWIMING/SWIMWAIT both use mStart=0, mLoop=0 -> the loop subtracts `end` each step."""
    f = f32(frame + rate)
    span_lo = loop - start
    while f < start and span_lo > 0.0:
        f = f32(f + span_lo)
    span_hi = end - loop
    if span_hi <= 0.0:
        return f
    while f >= end:
        f = f32(f - span_hi)
    return f

def cLib_addCalc(value, target, scale, max_step, min_step):
    """Faithful cLib_addCalc (c_lib.cpp): chase `value` toward `target`. step = scale*(target
    -value); if |step|>=min_step clamp to +-max_step and apply; else snap by +-min_step
    (clamped so it doesn't overshoot target). All f32. Used for the neutral speed decay."""
    if value == target:
        return value
    step = f32(scale * f32(target - value))
    if step >= min_step or step <= -min_step:
        if step > max_step:
            step = max_step
        if step < -max_step:
            step = -max_step
        return f32(value + step)
    if step > 0.0:
        if step < min_step:
            nv = f32(value + min_step)
            return target if nv > target else nv
    else:
        ms = -min_step
        if step > ms:
            nv = f32(value + ms)
            return target if nv < target else nv
    return value

# cM_scos indexes the ACTUAL console jmaCosTable (dumped live @ 0x80498168), not f32(cos(x)):
# see knowledge/model/fp-faithfulness.md and history/resolved-bugs.md for why the x86 recompute desynced.
with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'tables', 'cos_table.bin'), 'rb') as _f:
    _COS_TABLE = struct.unpack('>4096f', _f.read())   # console-libm values, big-endian f32

# The SIN companion for the quaternion foot-FK: the REAL console jmaSinTable (dumped live @ 0x80497168),
# NOT a -1024 view of cos -- those differ 1 ULP at 816/4096 entries. See knowledge/model/anim-engine.md.
with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'tables', 'sin_table.bin'), 'rb') as _f:
    _SIN_TABLE = struct.unpack('>4096f', _f.read())   # console-libm jmaSinTable[0:4096], big-endian f32

def cM_ssin_s16(angle):
    """JMASSin: jmaSinTable[(u16)angle >> 4] -- exact console value from the baked sin table."""
    return _SIN_TABLE[(int(angle) & 0xFFFF) >> 4]

_RAD2IDX = 10430.3779296875                 # 65536 / 2pi (cM_rad2s scale)
_GAME_TWOPI = 6.283185482025146             # the f32 2pi the game wraps with
def cM_scos(rad):
    value = rad % _GAME_TWOPI
    index = int(value * _RAD2IDX)
    if index < -32768:
        index += 65536
    elif index > 32767:
        index -= 65536
    index >>= 4                              # 65536 angles -> 4096 entries, low bits dropped
    if index < 0:
        index = 4096 + index
    return _COS_TABLE[index]                  # exact console table value (was f32(cos(...)))

def cM_scos_s16(angle):
    """The game's cM_scos applied DIRECTLY to an s16 angle (no cM_rad2s). This is what
    setSpeedAndAngleSwim uses: cM_scos(shape_angle.y - oldAngleY) where the arg is already
    s16. JMASCos: jmaCosTable[(u16)angle >> 4] -- exact console value from the baked table."""
    index = (int(angle) & 0xFFFF) >> 4          # 65536 angles -> 4096 entries, low bits drop
    return _COS_TABLE[index]

def deg_to_s16(deg):
    return int(round(deg / 360.0 * 65536.0)) & 0xFFFF

def s16_signed(a):
    a &= 0xFFFF
    return a - 65536 if a >= 32768 else a

# Console loads M_PI SINGLE (lfs) then fmuls -> cos args use f32 pi, not double math.pi; the
# 1-ULP diff flips cM_rad2s's truncated cell at knife-edges. Rationale: knowledge/model/fp-faithfulness.md.
_F32_PI = f32(math.pi)          # 3.1415927410125732 -- what `lfs M_PI` loads

# Per-axis stick dead-zone: each axis is offset by 15 before the angle/magnitude are taken
# (same 15 as ess_decay). Shared by swim (arrow/ESS) and land (walk stick). Slot-9 validated.
ARROW_STICK_DEADZONE = 15.0

def angdiff_deg(a, b):
    """Signed minimal a-b in (-180, 180]."""
    return ((a - b + 180.0) % 360.0) - 180.0

def _deadzone(c, dz=ARROW_STICK_DEADZONE):
    """Per-axis: subtract the dead-zone, keep sign, clamp at 0."""
    o = c - 128.0
    m = abs(o) - dz
    return 0.0 if m <= 0 else math.copysign(m, o)

def stick_angle_deg(sx, sy):
    """Stick direction in the decomp convention (deg), or None for neutral.
    0=down, 90=right, 180=up, 270=left. Per-axis dead-zoned. Slot-9 validated.

    Neutral (no swim input) uses the game's actual gate: mStickDistance =
    min(hypot(dz)/54, 1) <= 0.05  (d_a_player_main gates swim on mStickDistance > 0.05f).
    This supersedes the old square-deadzone test (both dz axes 0); they agree everywhere
    except a thin ring just outside the dz-15 square (0 < hypot <= 2.7), where the game
    blocks a tiny gain the square test would let through. Bit-identical to the gold stick
    table's `value <= 0.05` gate on all 65536 cells (verified), so no table dep needed."""
    ax, ay = _deadzone(sx), _deadzone(sy)
    if min(math.hypot(ax, ay) / 54.0, 1.0) <= 0.05:
        return None
    return math.degrees(math.atan2(ax, -ay)) % 360.0
