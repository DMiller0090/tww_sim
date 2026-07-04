#!/usr/bin/env python3
"""
superswim_sim.py - Offline physics sim for TWW superswimming (Phase A + B).

Pure-python reproduction of the swim physics validated live against Dolphin
(see SUPERSWIM_KNOWLEDGE.md). Lets us test reboost / peak-hold theories in
milliseconds before burning Dolphin frames. Mirrors the `seq` and `essloop`
commands in dolphin_mem.py so results are directly A/B-comparable.

Physics (all live-validated to ~0.05%):
  anim increment   incr = |v|/36 + 3/5 + (1 - (air+1)/900)      (mod 23, state 55)
  af_drag(v,anim)  = (2v/5)|cos(pi*anim/23)| + 3v/5             (head-bob drag)
  air_drag(v,air)  = 18000 v / (24300 - 7 air)
  true_disp        = air_drag(af_drag(v, anim), air)            (ESS/charge move dist)
  ESS decay        = clamp((|raw-128|-15)/54, 0, 1) * 3   (ESS-down stick 110 -> 1/6)
  charge gain      = +3 / frame (on-axis full deflection)
  neutral          = decay -2, move == v (drag-free); anim ~0.83/frame mod 26 (approx)

Heading model (Phase B, live-calibrated 2026-06-26):
  Each CHARGE frame schedules a 180-deg facing flip that takes effect on the NEXT
  frame. Movement each frame follows the current facing. So an N-frame charge burst
  yields floor of alternating reversed frames -> the net-vs-path penalty of reboost.
  ESS/neutral never flip facing.

Usage:
  py superswim_sim.py seq "<act,n;act,n;...>" [v=-1630] [air=900] [anim=0] [every=0]
      acts: ess (stick=110), ess:<rawY>, chg, neu     e.g. "ess,150" or
            "ess,20;chg,1;chg,1" (reboost). Mirrors dolphin_mem.py seq.
  py superswim_sim.py essloop frames=N trig=LO,HI [boost=B] [v=..][air=..][anim=..]
      Closed-loop phase-triggered reboost, identical policy to dolphin essloop.
  Add  viz=out.html   to either to emit a self-contained animated movement viewer.
  Add  json=out.json  to dump the raw per-frame trace.

Both print a SUMMARY line matching dolphin_mem.py:  frames path net path/fr net/fr.
"""
import sys, math, json, struct
import numpy as np

MAX_AIR = 900

# The GameCube runs all of this in IEEE-754 SINGLE precision (f32). Python floats are
# f64, so a 480-frame swim accumulates ~0.01 anim drift that the high-speed exit af_drag
# amplifies ~30x. f32() rounds each result to f32 so the REAL game values (potential
# speed, anim) match bit-for-bit. Op ORDER matches the decomp (left-to-right, no FMA).
# PERF: this is the planner's hottest function (~45% of plan_min_frames time, ~60M calls
# for one cold-start DP). `float(np.float32(x))` pays numpy scalar-construction overhead on
# every call. ctypes `c_float` rounds with the SAME IEEE-754 round-half-to-even and SAME
# overflow->inf behaviour (verified bit-identical over 200k random + edge values incl
# inf/overflow/-0.0) at ~2x the speed. Bit-identity keeps every live-validated baseline.
from ctypes import c_float as _c_float
def f32(x):
    return _c_float(x).value

# decomp constants (d_a_player_HIO.h: mSwim field_0x50/54/74 = 0.6/1.1/1.0).
_RATE_SLOPE = f32(f32(1.1) - f32(0.6))           # (0x54 - 0x50) in f32 = 0.5
_MAX_NSPEED = f32(18.0)                            # mMaxNormalSpeed (0.5/18 == 1/36)
_TIMER_K = f32(0.0011111111)                       # getSwimTimerRate per-air coefficient

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

# The game's cosine is cM_scos(cM_rad2s(x)): a 4096-entry table indexed by the s16 angle
# with the low 4 bits TRUNCATED (index >> 4) -- NO interpolation (JMASCos, JMATrigonometric.h:
# jmaCosTable[(u16)v >> jmaSinShift], jmaSinShift=4). That truncation is the ~5e-4 vs math.cos.
# CRITICAL: the table is built ON THE CONSOLE at runtime (JMANewSinTable, JMath.cpp:32-36):
#   jmaSinTable[i] = (f32)sin( ((M_PI*2.0)/4096) * i );  jmaCosTable = jmaSinTable + 1024
# i.e. cosTable[k] = f32(sin(step*(k+1024))). The PowerPC libm sin differs from x86 math.cos
# by 1-2 ULP at 2964/4096 entries (max 4.17e-7). A direct f32(cos(...)) recompute therefore
# mismatched the console at most entries; x598-amplified across pumps that 1 ULP became a
# 0.07 potential-speed jump at exits (cos-table-boundary crossing). FIX: bake the ACTUAL
# console table (dumped live from jmaCosTable @ 0x80498168 -> cos_table.bin) and index it.
import os as _os
with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'tables', 'cos_table.bin'), 'rb') as _f:
    _COS_TABLE = struct.unpack('>4096f', _f.read())   # console-libm values, big-endian f32

# The SIN companion for the quaternion foot-FK: the REAL console jmaSinTable (dumped live @ 0x80497168),
# NOT a -1024 view of cos -- those differ 1 ULP at 816/4096 entries. See knowledge/model/sim.md.
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

def incr(v, air):
    # SWIMING anim rate = setSwimMoveAnime: |v|*(0x54-0x50)/mMaxNormalSpeed + 0x50
    #                     + getSwimTimerRate()*0x74   (all f32, decomp order)
    rate = f32(f32(f32(abs(f32(v))) * _RATE_SLOPE) / _MAX_NSPEED)
    rate = f32(rate + f32(0.6))
    timer = f32(1.0 - f32(f32(air + 1) * _TIMER_K))   # getSwimTimerRate (itemTimeCount=air+1)
    return f32(rate + f32(timer * f32(1.0)))

_F60 = f32(0.4)                 # field_0x60 (HIO mSwim.m.field_0x60)
# Console loads M_PI SINGLE (lfs) then fmuls -> cos args use f32 pi, not double math.pi; the
# 1-ULP diff flips cM_rad2s's truncated cell at knife-edges. Rationale: memory superswim-gekko-fp.
_F32_PI = f32(math.pi)          # 3.1415927410125732 -- what `lfs M_PI` loads

def af_drag(v, anim):
    # head-bob: (speedF*(1-0x60) + 0x60*speedF*|cM_scos(rad2s(pi*moveFrame/moveEnd))|)
    # with field_0x60 = 0.4 -> 0.6*v + 0.4*v*|cM_scos(pi*anim/23)|. (d_a_player_main.cpp:
    # 2424-2428; moveEnd = 23.) Used only for DISPLACEMENT (an ignored wave-affected
    # byproduct), so its exact f32 order is not validated. The v-setting EXIT release uses
    # release_ess_speed below, which matches the (different) procSwimWait_init f32 order.
    # cos arg is SINGLE on console (fdivs anim/23 then fmuls lfs M_PI = _F32_PI; posMoveFromFootPos
    # JP @0x80106134/5c/60). Omits the /(1+0x7C*timerRate) divisor -- see predict/swim_exact.
    c = f32(abs(cM_scos(f32(f32(anim / 23.0) * _F32_PI))))
    return f32(f32(f32(f32(2.0 * v / 5.0)) * c) + f32(3.0 * v / 5.0))

def release_ess_speed(v, rel_anim):
    # ESS->neutral EXIT release v (procSwimWait_init, d_a_player_swim.inc:414-415):
    #   fVar2 = getFrame() / getEnd()            # rel_anim / 23 (SWIMING end), in f32
    #   mNormalSpeed = speedF*(1.0 - field_0x60) + speedF*|cM_fcos(fVar2 * M_PI)|*field_0x60
    # This is a DIFFERENT f32 order than the head-bob af_drag: the cos term is (v*c)*0.4
    # (multiply by |cos| BEFORE the 0.4 coeff), the coeffs are the HIO 0.4 / runtime
    # (1.0-0.4), and fVar2 = rel_anim/23 is taken in f32 BEFORE the *pi. The old af_drag
    # used 2v/5 * c + 3v/5 with pi*anim/23 in f64 -> ~2 ULP (3e-5) low at v~-180; that
    # constant v offset fed incr (~7e-7/frame) and the anim drift x598-amplified at pumps.
    # CRITICAL: `fVar2 * M_PI` compiles to lfs M_PI + fmuls = SINGLE pi (_F32_PI); double pi
    # flips the truncated cos-cell at knife-edges (was the pump-300k desync; memory superswim-gekko-fp).
    fVar2 = f32(rel_anim / 23.0)
    c = f32(abs(cM_scos(f32(fVar2 * _F32_PI))))
    term2 = f32(v * f32(1.0 - _F60))            # speedF * (1.0 - field_0x60)
    term1 = f32(f32(v * c) * _F60)              # speedF * |cos| * field_0x60
    return f32(term2 + term1)

def air_drag(v, air):
    return 18000.0 * v / (24300.0 - 7.0 * air)

def true_disp(v, anim, air):
    return air_drag(af_drag(v, anim), air)

# Charge frames move ~5.3% LESS than ESS at the identical (v,anim,air) — measured
# live (band 2): ESS 1463.60 vs charge 1385.44 at v=-1632,anim=17.66,air=895 ->
# 0.9466. Same heading, pure magnitude reduction (full-deflection stick path).
# Empirical, band-2 only; revalidate across speeds before trusting far from -1630.
CHARGE_DISP_FACTOR = 0.9466

# --- Arrow-swim charge (2-D front-end) — live-validated 2026-06-27 (capture_arrow.py) ---
# Decomp setSpeedAndAngleSwim (d_a_player_swim.inc:41): each charge frame facing SNAPS
# to m34E8 (stick world dir) when |m34E8-facing|>0x6000 (135deg); then
#   speed delta = mStickDistance * 3 * cos(facing_after - facing_before).
# Superswim alternates the stick fully back/forth. Tilting that alternation axis by an
# angle alpha toward the target (e.g. hold Xbias while flipping Y 255/0) makes the
# facing rotate (180-2*alpha) deg each frame instead of 180, so (dist≈1 at full Y):
#   charge_rate(alpha)  = -3*dist*cos(2*alpha)         # alpha=0 -> -3 (pure back)
#   cross_drift(alpha)  = disp * sin(alpha)  per frame # toward target, ACCUMULATES
#   along_move(alpha)   = disp * cos(alpha), sign ALTERNATES (net ~cancels, like charge)
# where disp = CHARGE_DISP_FACTOR * true_disp(v,anim,air). Usable alpha in [0,~20deg];
# past ~xbias 190 the backward-snap dies (DIR no longer BACKWARD) -> tip-over, the stick
# drives a FORWARD release (+speed loss) instead of charging. Live match (v=-300 slate):
#   alpha 0/8/18 deg -> rate -3.00/-2.88/-2.44 (vs -3cos2a = -3.00/-2.88/-2.43); and
#   dz/|move| = sin(alpha) confirmed (xb160 8deg, xb180 18deg). See capture_arrow.py.
def arrow_charge_rate(alpha_deg, dist=1.0):
    return -3.0 * dist * math.cos(2.0 * math.radians(alpha_deg))

def arrow_cross_drift(v, anim, air, alpha_deg, factor=CHARGE_DISP_FACTOR):
    """Per-frame cross-track displacement toward the target (magnitude)."""
    return factor * abs(true_disp(v, anim, air)) * math.sin(math.radians(alpha_deg))

# Tip-over guard: beyond this tilt the backward-snap dies and charging stops paying.
ARROW_ALPHA_MAX_DEG = 20.0
# Arrow-phase SPIN-UP: when alternation begins, facing is ~on the axis so the first
# stick targets are <135deg away -> NON-snap forward frames that LOSE ~+3/fr each until
# the 0<->180 swing establishes. Live-measured ~2 frames (slot-9 capture f5-f6; confirmed
# by spotcheck_frontend 2026-06-27). The planner must charge this so it doesn't pick
# short arrow phases that never pay off. One-time per arrow phase.
ARROW_SPINUP_FRAMES = 2

# --- 2-D arrow + facing stepper (front-end) — live-validated slot-9 2026-06-27 ----------
# Facing is a REAL angle (degrees). The decomp + slot-9 capture pin down:
#   stickAngle = atan2(sx-128, -(sy-128))     # 0=down, 90=right, 180=up, 270=left
#   m34E8 (world stick target) = stickAngle + 180 + camAngle           (all degrees)
#   SNAP: |angdiff(m34E8, facing)| > 135 (0x6000) -> facing := m34E8 (instant turnaround)
#         else gradual cLib turn toward m34E8 at ~ARROW_TURN_RATE deg/frame (no snap)
#   speed delta (potential) = stickDist*3*cos(facing_after - facing_before)
#     snap (~158-180deg)  -> cos<0 -> charges (more negative); pure back = -3
#     non-snap (~small)   -> cos~+1 -> +3 LOSS (the 2-frame arrow spin-up, tip-over)
#   world move bearing = camAngle - facing   (reflection); displacement = |true_disp|
#   BOTH the facing change and the speed delta LAG one frame (input[f-1] -> facing[f]).
# Validated frame-exact vs slot-9 capture: rotation chain 90->305->164->0 and the
# arrow-west drift (alpha~8, charge -2.88/fr, net bearing west). See validate_arrow.py.
ARROW_SNAP_DEG = 135.0      # 0x6000 backward-snap cone half-not: |Δ|>135 snaps
ARROW_TURN_RATE = 7.0       # gradual (non-snap) turn deg/frame (cLib_addCalcAngleS approx)
# Per-axis stick dead-zone: each axis is offset by 15 before the angle/magnitude are
# taken (same 15 as ess_decay). This compresses the MINOR axis on partial deflections,
# so e.g. (0,96) reads alpha~8 (live) not ~14 (raw atan2). Pinned on the slot-9 capture:
# (0,96)/(255,96) span 162.8deg with dz=15 vs live 164 (raw gave 152). Full-deflection
# rotation frames also improve (f2 (255,80) -> 163.6 vs live 164, raw gave 159).
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

def stick_dist(sx, sy, gate=128.0 - ARROW_STICK_DEADZONE):
    """Normalized (dead-zoned) stick magnitude, clamped to 1 (full deflection). The
    clamp is CORRECT for the charge gain: a fixed-alpha live test (fixed_alpha.py)
    found the snap charge is exactly 3*cos(180-2*alpha) with an implied stick distance
    of 1.0000 at alpha=0/10/20 -- the game caps mStickDistance at the gate, so tilt
    changes the COS (snap angle 180-2*alpha), not the magnitude."""
    return min(math.hypot(_deadzone(sx), _deadzone(sy)) / gate, 1.0)

def m34e8_deg(sx, sy, cam_deg):
    sa = stick_angle_deg(sx, sy)
    if sa is None:
        return None
    return (sa + 180.0 + cam_deg) % 360.0

class ArrowState:
    """2-D arrow/charge front-end stepper. Tracks facing (deg), world x/z, and the
    charge speed. Mirrors SwimState's 1-frame-lag discipline for the facing snap and
    the charge gain. Reuses true_disp() for the per-frame displacement magnitude.

    cam_deg = camera (csangle) in degrees; slates 9/10 use 270 (west). facing_deg
    default 90 (east) = the slot-9/10 start. Step takes a raw (sx, sy) stick."""
    def __init__(self, v=-300.0, anim=0.0, air=900, facing_deg=90.0, cam_deg=270.0):
        self.v = float(v)
        self.anim = float(anim)
        self.air = int(air)
        self.facing = float(facing_deg) % 360.0
        self.cam = float(cam_deg) % 360.0
        self.x = 0.0
        self.z = 0.0
        self._pending_facing = None   # facing snaps/turns land next frame
        self._pending_gain = None     # speed delta lands next frame (replaces decay)

    def clone(self):
        s = ArrowState.__new__(ArrowState)
        s.__dict__.update(self.__dict__)
        return s

    def move_bearing(self):
        return (self.cam - self.facing) % 360.0

    def step(self, sx, sy):
        """Advance one frame with raw stick (sx, sy). Returns (dx, dz, tag)."""
        # apply the lagged facing change + speed delta scheduled last frame
        if self._pending_facing is not None:
            self.facing = self._pending_facing % 360.0
            self._pending_facing = None
        v_pre = self.v                         # pre-update v: the anim RATE lags 1 frame
        if self._pending_gain is not None:     # (matches SwimState._advance_anim_55 and
            self.v += self._pending_gain       #  the real game) -> use v_pre for incr below,
            self._pending_gain = None          #  not the post-gain v (else anim drifts
        # decide this frame's facing change + speed delta from the stick (land next frame)
        m = m34e8_deg(sx, sy, self.cam)
        dist = stick_dist(sx, sy)
        if m is None:                          # neutral stick: coast, no turn/charge
            d_turn = 0.0
            tag = 'COAST'
        else:
            d = angdiff_deg(m, self.facing)
            if abs(d) > ARROW_SNAP_DEG:        # instant turnaround snap
                d_turn = d
                self._pending_facing = self.facing + d
                tag = 'SNAP'
            else:                              # gradual turn (no snap) -> forward/tip-over
                d_turn = max(-ARROW_TURN_RATE, min(ARROW_TURN_RATE, d))
                self._pending_facing = self.facing + d_turn
                tag = 'TURN'
            self._pending_gain = dist * 3.0 * math.cos(math.radians(d_turn))
        # Advance anim BEFORE computing displacement, exactly like SwimState (state 55:
        # _advance_anim_55 then true_disp(self.anim)). The anim RATE still lags 1 frame
        # (uses v_pre), but the displacement samples the ADVANCED anim of THIS frame, not
        # the stale pre-advance value -- live-pinned: pre-advance over-predicted disp ~20%
        # on the first prefix frame (live 70 vs 88).
        self.anim = nfmod(self.anim + incr(v_pre, self.air), 23.0)   # pre-update v (lag)
        # move this frame along the CURRENT facing (the snap/gain land next frame)
        mag = CHARGE_DISP_FACTOR * abs(true_disp(self.v, self.anim, self.air))
        brg = math.radians(self.move_bearing())
        dx, dz = mag * math.cos(brg), mag * math.sin(brg)
        self.x += dx
        self.z += dz
        self.air -= 1
        return dx, dz, tag

def run_arrow(sticks, v=-300.0, anim=0.0, air=900, facing_deg=90.0, cam_deg=270.0):
    """sticks: iterable of (sx, sy). Returns per-frame rows (facing, x/z, v, bearing)."""
    s = ArrowState(v=v, anim=anim, air=air, facing_deg=facing_deg, cam_deg=cam_deg)
    rows = []
    x0, z0 = s.x, s.z
    for i, (sx, sy) in enumerate(sticks):
        dx, dz, tag = s.step(sx, sy)
        net = math.hypot(s.x - x0, s.z - z0)
        nb = math.degrees(math.atan2(s.z - z0, s.x - x0)) % 360.0 if net else 0.0
        mb = math.degrees(math.atan2(dz, dx)) % 360.0 if (dx or dz) else 0.0
        rows.append({"f": i + 1, "stick": (sx, sy), "facing": s.facing, "v": s.v,
                     "anim": s.anim, "air": s.air, "x": s.x, "z": s.z, "dx": dx,
                     "dz": dz, "tag": tag, "move_brg": mb, "net": net, "net_brg": nb})
    return rows

# --- Facing BFS: find a turnaround-chain that rotates facing onto a target axis -------
# Nodes = facing (bucketed to FACING_BUCKET deg). Edges = full-deflection sticks that
# SNAP (|angdiff(m34E8, facing)| > 135) -> land at m34E8. The drift axis we want to
# arrow-swim is PERPENDICULAR to the charge axis, and the charge axis is the facing
# line, so to drift toward bearing `target_bearing` we want facing on the axis
# perpendicular... actually: arrow drift is +/- the charge (facing) axis tilted; the
# clean tech is to put facing on the N-S/E-W line whose alternation drifts toward the
# target. We reach ANY desired facing; caller picks it. Returns a list of (sx, sy).
FACING_GATE = 15.0          # facing-graph resolution (deg per node)

def stick_for_m34e8(target_deg, cam_deg=270.0, R=127.0):
    """Inverse of m34e8_deg: a full-deflection (sx, sy) whose world stick target is
    ~target_deg. stickAngle = target - 180 - cam; ax=R*sin, -ay=R*cos."""
    sa = math.radians((target_deg - 180.0 - cam_deg) % 360.0)
    sx = int(round(128.0 + R * math.sin(sa)))
    sy = int(round(128.0 - R * math.cos(sa)))
    return (max(0, min(255, sx)), max(0, min(255, sy)))

def snap_deltas(chain, facing_start, cam_deg=270.0):
    """Replay a reorient chain's facings and return the per-snap Δfacing (deg).
    Each snap sets facing := m34E8, so the charge it pays is 3·dist·cos(Δfacing)
    (decomp). Lets the planner price reorient speed-build exactly instead of assuming
    a full -3/frame. Non-snapping steps (shouldn't occur in a BFS chain) give 0."""
    f = facing_start % 360.0
    out = []
    for (sx, sy) in chain:
        m = m34e8_deg(sx, sy, cam_deg)
        if m is None or abs(angdiff_deg(m, f)) <= ARROW_SNAP_DEG:
            out.append(0.0)
            continue
        d = angdiff_deg(m, f)
        out.append(d)
        f = m % 360.0
    return out

def arrow_sticks(alpha_deg, drift_down=True):
    """Synthesize the two alternating arrow sticks for the N-S charge axis (facing 0/180,
    the slate's reoriented arrow axis): alternate X full (left/right -> snap facing 0<->180)
    with a Y-bias that tilts each snap by alpha toward the drift side. Inverse of the
    dead-zoned stick model: tan(alpha) = (|bias-128| - 15)/(128-15). drift_down=True biases
    Y down (the live-validated WEST drift on the slate). Returns [(sx,sy),(sx,sy)] to
    alternate. alpha=0 -> Y centered (pure charge). Validated vs the slot-9 capture:
    alpha=8 -> bias ~97 == the live (0,96)/(255,96)."""
    g = 128.0 - ARROW_STICK_DEADZONE
    off = 0.0 if alpha_deg <= 0 else ARROW_STICK_DEADZONE + g * math.tan(math.radians(alpha_deg))
    b = int(round(128 - off if drift_down else 128 + off))
    b = max(0, min(255, b))
    return [(0, b), (255, b)]

def reorient_chain(facing_start, facing_goal, cam_deg=270.0, tol=10.0, max_depth=6):
    """BFS over facing for a turnaround-snap chain from facing_start to within `tol`
    of facing_goal. A single snap can reach any facing >135deg away (the backward cone),
    so the graph nodes are facings (every FACING_GATE deg) and each edge is a synthesized
    full-deflection stick that snaps there. Every edge CHARGES. Returns the (sx, sy)
    list (or [] if already aligned, None if unreachable). Generalizes to any start/axis
    — DON'T hardcode the inputs (KNOWLEDGE §5.3)."""
    start = round(facing_start % 360.0 / FACING_GATE) * FACING_GATE % 360.0
    if abs(angdiff_deg(start, facing_goal)) <= tol:
        return []
    gates = [g * FACING_GATE for g in range(int(360.0 / FACING_GATE))]
    from collections import deque
    seen = {start: []}
    q = deque([start])
    while q:
        f = q.popleft()
        path = seen[f]
        if len(path) >= max_depth:
            continue
        for g in gates:
            if abs(angdiff_deg(g, f)) <= ARROW_SNAP_DEG:   # must be a >135deg snap
                continue
            stick = stick_for_m34e8(g, cam_deg)
            land = m34e8_deg(*stick, cam_deg)              # actual landing (gate-rounded)
            nf = round(land % 360.0 / FACING_GATE) * FACING_GATE % 360.0
            if nf in seen:
                continue
            seen[nf] = path + [stick]
            if abs(angdiff_deg(nf, facing_goal)) <= tol:
                return seen[nf]
            q.append(nf)
    return None

def ess_decay(rawY):
    # potential-speed decay magnitude for a cardinal stick offset (raw 0..255), f32.
    return f32(min(max(f32(f32(abs(rawY - 128) - 15) / f32(54.0)), 0.0), 1.0) * f32(3.0))

def neutral_anim_rate(air):
    # neutral (state 54) SWIMWAIT anim rate/frame, mod 26 = procSwimWait setRate
    # (d_a_player_swim.inc:478): getSwimTimerRate()*field_0x70 + field_0x40, with
    # field_0x70=2.5, field_0x40=0.5. getSwimTimerRate (inc:283) is
    #   f32(1.0 - itemTimeCount * 0.0011111111f)  [itemTimeCount = air+1]
    # -- a MULTIPLY by the f32 1/900 constant, NOT a divide by 900. It is the SAME
    # getSwimTimerRate incr() uses (the *_TIMER_K term). The old divide-by-900 form
    # rounded 1 ULP HIGH at certain air (e.g. air=615: 3fa4fa50 vs decomp 3fa4fa4f);
    # since the warm-pump oldframe = fc_update(anim, this_rate, 26) is then *598-
    # scrambled, that 1 ULP compounded across pump cycles into a bad-phase exit
    # (HANDOFF pt17). Rounding structure mirrors incr() (product f32'd, then +0.5).
    timer = f32(1.0 - f32(f32(air + 1) * _TIMER_K))     # getSwimTimerRate()
    return f32(f32(0.5) + f32(f32(2.5) * timer))

class SwimState:
    """One Link, stepped frame by frame. Tracks 2D position so we can draw it.
    heading is the movement direction (radians); absolute orientation is arbitrary
    (we init 0) since net/path are rotation-invariant — only the 180 flips matter."""
    def __init__(self, v=-1630.0, anim=0.0, air=900, heading=0.0):
        self.v = float(v)
        self.anim = float(anim)
        self.air = int(air)
        self.x = 0.0
        self.z = 0.0
        self.heading = heading      # radians
        self.state = 55             # 55 = moving (ESS/charge), 54 = neutral
        self._pending_flip = False  # set by a charge frame; applied next frame start
        self._pending_gain = 0.0    # charge +3 lags 1 frame; lands on (and replaces the
                                    # decay of) the NEXT frame, even if that frame is ESS
        # The first held-ESS frame after a charge->hold entry (e.g. writename speed then
        # hold ESS, as in the Dolphin test slate) shows a one-time -3 facing-flip transient
        # instead of the normal decay. Set entry_tax=True to replicate that exactly.
        self._entry_tax = False
        # Air refill (opt-in): while forward progress -x <= _refill_until, air is pinned to
        # 900 (the "refill before cruising" tech). Default off -> baselines unchanged.
        self._refill_air = False
        self._refill_until = 0.0
        # state 54<->55 transitions lag 1 frame: the first input frame runs the OLD
        # state's physics, the transition (and its release/scramble effect) lands next.
        self._pending_state = None
        self._just_released = False
        self._skip_advance = False  # scramble frame loads anim directly at ess_start
        # oldFrame for the next neutral->ESS scramble = the MOVE0 (SWIMWAIT) controller frame
        # at setSwimMoveAnime time. TWO cases (live-pinned, both bit-exact):
        #  - COLD START (first swim, fresh/rested controller): the swim-INITIATION frame
        #    advances MOVE0 by exactly +1.0, so oldFrame = (display anim at the trigger
        #    frame START) + 1.0. Stashed in _scramble_oldframe at the trigger frame.
        #  - WARM PUMP (re-entry mid-swim, running controller): procSwimWait runs one more
        #    neutral update() on the landing frame before procSwimMove_init, so
        #    oldFrame = (display anim after the trigger frame, = self.anim at landing start)
        #    + neutral_anim_rate(self.air). No stash needed.
        # setSwimMoveAnime then does setFrame(oldFrame*26*23) -> anim = 598*oldFrame.
        self._scramble_oldframe = None
        self._warm = False          # True once the swim has been in state 55 (=> pumps, not
                                    # the cold-start initiation, drive subsequent entries).
        # FACING (shape_angle.y) — tracked per decomp so the charge gain SIGN is exact.
        # setSpeedAndAngleSwim (d_a_player_swim.inc:27-41): each swim frame with stick,
        #   if |m34E8 - facing| > 0x6000 (135 deg):  facing SNAPS to m34E8
        #   else:                                     facing turns gradually toward m34E8
        #   gain = mStickDistance * 3 * cM_scos(facing_new - facing_old)
        # So a charge whose stick OPPOSES facing snaps (cos~-1 -> -3 gain) and one ALIGNED
        # with facing turns ~0 (cos~+1 -> +3 LOSS = the spin-up). The blind "-3 every chg"
        # was only right when the charge snaps; warm pump re-entries can be aligned -> +3.
        # Tracked in s16 (the game's shape_angle.y units) for bit-exact cM_scos at the
        # cardinal angles. Slate: facing 16384 (east), csangle 49152 (west).
        self.facing = 16384           # shape_angle.y, s16
        self.cam = 49152              # csangle, s16
        self._pending_facing = None   # facing snap/turn lands next frame (1-frame lag)
        self._chg_count = 0           # charge up/down parity (replay: chg#1=UP=odd)
        # Post-burst facing transient: when an ESS frame's own facing-snap gain is
        # preempted by a landing charge gain (the frame a charge burst ends), that
        # transient is not lost -- it lands the NEXT frame (1-frame lag, like charges),
        # matching live setSpeedAndAngleSwim. For EVEN bursts facing is already
        # re-aligned so the carried value == +1/6 == the next frame's own gain (no-op,
        # keeps the 200k/even baselines bit-exact); for ODD bursts it carries the -1/6
        # opposed transient that the old code dropped (the t_chgexit -1/3 residual).
        self._post_burst_transient = None

    def clone(self):
        s = SwimState.__new__(SwimState)
        s.__dict__.update(self.__dict__)
        return s

    def _advance_anim_55(self):
        # SWIMING controller: end=23. Faithful loop-subtract (fc_update) so the post-scramble
        # raw mFrame (~15232) loops down with the GAME's f32 rounding, not nfmod's f64 modulo.
        self.anim = fc_update(self.anim, incr(self.v, self.air), 23.0)

    def _swim_facing(self, sx, sy):
        """Decomp facing update for a swim-input frame (setSpeedAndAngleSwim, s16 math).
        Schedules the snap/gradual facing change for NEXT frame (1-frame lag) and returns
        the speed gain = mStickDistance*3*cM_scos(d_turn). Caller decides whether to use
        the gain (charge) or keep its own decay (ESS). All angles s16:
          m34E8 = stickAngle + 0x8000 + camAngle;  snap iff |m34E8 - facing| > 0x6000."""
        sa = stick_angle_deg(sx, sy)
        if sa is None:                             # neutral stick: no swim input, no turn
            return 0.0
        m = (deg_to_s16(sa) + 0x8000 + self.cam) & 0xFFFF      # m34E8 (s16)
        d = s16_signed(m - self.facing)            # signed s16 difference
        if abs(d) > 0x6000:                        # 135 deg backward cone -> instant snap
            d_turn = d
        else:                                      # aligned -> gradual chase (cardinal: 0)
            cap = deg_to_s16(ARROW_TURN_RATE)
            d_turn = max(-cap, min(cap, d))
        self._pending_facing = (self.facing + d_turn) & 0xFFFF
        # mStickDistance uses the /54 gate (== ess_decay's normalization): ESS(110)=0.0556,
        # full charge deflection (0/255) clamps to 1.0. (NOT stick_dist's /113 gate, which
        # would give 0.991 for a full charge -> -2.97 instead of the live-exact -3.0.)
        mag = math.hypot(_deadzone(sx), _deadzone(sy))   # _deadzone already removed the 15
        md = min(mag / 54.0, 1.0)
        return f32(md * 3.0 * cM_scos_s16(d_turn))

    def _chg_stick(self, up_raw=None):
        """The concrete charge stick for this charge frame, matching the replay parity
        (verify_state/spotcheck: chg#1=UP, then alternating). UP=(128,255), DN=(128,0).
        PARTIAL charge ('chg:<up_raw>'): the UP stroke is (128, up_raw) and the DOWN stroke
        mirrors it about 128 -> (128, 256-up_raw), so a deflection shallower than full still
        snaps (same on-axis direction) but gains less than 3 via the /54 law. up_raw=None
        keeps the full-charge sticks BIT-EXACT (default path, baselines untouched)."""
        self._chg_count += 1
        if up_raw is None:
            return (128, 255) if (self._chg_count % 2 == 1) else (128, 0)
        return (128, up_raw) if (self._chg_count % 2 == 1) else (128, 256 - up_raw)

    def _move(self, dist):
        self.x += dist * math.cos(self.heading)
        self.z += dist * math.sin(self.heading)
        return dist

    def _move(self, dist):
        self.x += dist * math.cos(self.heading)
        self.z += dist * math.sin(self.heading)
        return dist

    def step(self, action):
        """action: 'ess' | 'ess:<rawY>' | 'chg' | 'neu'. Returns (step_dist, tag).
        State 54 (neutral) <-> 55 (ESS/charge) transitions lag 1 frame (live-pinned):
        the first input frame runs the OLD state; the new state + its effect land next.
        - ESS->neutral: on the 54 frame, v := release_ess_speed = af_drag(v, anim+incr).
        - neutral->ESS (pump): 1-frame neutral tax, then ESS with a scrambled anim start."""
        if action not in ('chg', 'neu') and not action.startswith(('ess', 'chg:')):
            raise ValueError(f"unknown action {action!r}")
        # PARTIAL charge: 'chg:<up_raw>' charges with a shallower on-axis deflection (still
        # snaps/flips, gains <3 via /54). chg_up=None -> full charge (existing 'chg', exact).
        chg_up = int(action[4:]) if action.startswith('chg:') else None
        is_chg = (action == 'chg') or (chg_up is not None)
        # 180-deg turnaround flip (charge), applied at frame start
        if self._pending_flip:
            self.heading += math.pi
            self._pending_flip = False
        if self._pending_facing is not None:      # facing snap/turn lands now (1-frame lag)
            self.facing = self._pending_facing
            self._pending_facing = None
        # pending 54<->55 state transition (1-frame lag), with its one-time effect
        if self._pending_state is not None:
            if self._pending_state == 54:        # ESS -> neutral exit: release_ess_speed
                # procSwimWait_init(TRUE) (d_a_player_swim.inc:406-424): fVar2 =
                # getFrame()/getEnd (SWIMING end=23); release speed = af_drag(|cos(pi*fVar2)|),
                # THEN the SAME MOVE0 controller is re-scaled to SWIMWAIT (end 26):
                # setFrame(fVar2 * 26). So the post-exit neutral DISPLAY anim =
                # (swiming/23)*26 -- the exact mirror of the entry's *598 scramble, NOT a
                # separate parallel controller. swiming = the SWIMING frame advanced one more
                # step on the transition frame (= self.anim + incr, wrapped mod 23; getFrame()
                # is the looped frame in [0,23)). |cos| is mod-23 periodic so the wrap leaves
                # the release v bit-identical.
                rel_anim = fc_update(self.anim, incr(self.v, self.air), 23.0)
                self.v = release_ess_speed(self.v, rel_anim)
                # setFrame(fVar2 * getEnd()), fVar2 = getFrame()/getEnd (procSwimWait_init,
                # d_a_player_swim.inc:415,421): DIVIDE-then-multiply in f32, i.e.
                # f32(f32(rel_anim/23.0) * 26.0) -- NOT a precomputed f32(26/23) multiply
                # (different f32 rounding). Feeds oldframe for the next x598 scramble, so the
                # 1-ULP difference is amplified ~600x across pump cycles.
                self.anim = f32(f32(rel_anim / 23.0) * 26.0)
                self._just_released = True
            else:                                # neutral -> ESS pump: anim scramble
                # DECOMP-DERIVED (setSwimMoveAnime, d_a_player_swim.inc:264 +
                # J3DFrameCtrl, J3DAnimation.h:853-860). The pump re-inits the move
                # controller:
                #   endFrame = oldFrame * oldEnd       # oldEnd = getEnd() = 26 (ANM_SWIMWAIT)
                #   <load ANM_SWIMING: mEnd <- 23, mFrame <- start=0>
                #   setFrame(endFrame * getEnd())      # mFrame = oldFrame*26*23 = oldFrame*598
                # setFrame is a RAW float store (no wrap). Drag samples |cos(pi*mFrame/23)|,
                # period 23, and 598 = 26*23 ≡ 0 (mod 23) -> only frac(oldFrame) survives,
                # scaled x598 (the hypersensitivity). Then the first ESS update() adds one
                # mRate = incr(v,air) BEFORE the drag read, so the displayed start is:
                #   anim_ESS_start = (oldFrame*598 + incr(v,air)) mod 23
                # oldFrame = the MOVE0 (SWIMWAIT) controller frame at the instant
                # setSwimMoveAnime runs. procSwimWait runs ONE MORE neutral update() on the
                # landing frame BEFORE procSwimMove_init fires, so getFrame = (display anim
                # after the trigger frame, = self.anim here at the landing-frame START) +
                # one more neutral step. This is the UNIFIED rule for BOTH cold-start and
                # pump entries (the old "+1.0 from trigger-frame-start" only COINCIDENTALLY
                # matched cold start: 0.064+1.0 == display_after_f1 + neutral_rate; it broke
                # for pumps where neutral_rate != 0.5). Live-pinned on the pump cycle:
                # f93 display 24.716 -> oldFrame 24.716+0.756 = 25.472 -> 598*25.472 mod 23
                # = live raw 15232.17 / 598. The +incr lands the NEXT frame (skip_advance).
                if self._scramble_oldframe is not None:   # COLD START: stashed start+1.0
                    oldframe = self._scramble_oldframe
                    self._scramble_oldframe = None
                else:                                     # WARM PUMP: display_after + neut rate
                    # procSwimWait's update() runs (and LOOPS mod 26) before procSwimMove_init
                    # reads getFrame(), so oldframe is the LOOPED SWIMWAIT frame -- fc_update,
                    # not a raw add. If the sum exceeds 26 a raw add would *598 a value 26
                    # larger; 26*598 == 0 (mod 23) so v is unaffected, but the RAW magnitude
                    # (and thus the faithful f32 loop-down) would differ -> anim drift.
                    oldframe = fc_update(self.anim, neutral_anim_rate(self.air), 26.0)
                # setSwimMoveAnime (d_a_player_swim.inc:265,275): endFrame = getFrame()*getEnd()
                # (oldEnd=26, SWIMWAIT still loaded) THEN setFrame(endFrame * getEnd()) with the
                # NEW end=23 (SWIMING). So it is TWO sequential f32 multiplies x26 then x23 --
                # NOT f32(598*oldframe). f32(f32(x*26)*23) != f32(x*598) by ~1 ULP at this
                # magnitude (~15232); that ULP carried forward and re-amplified x598 each pump.
                self.anim = f32(f32(oldframe * 26.0) * 23.0)   # RAW setFrame -- stays raw
                # (~15232) like the live mFrame; the next _advance_anim_55 loops it down with
                # the game's f32 repeated-subtraction (fc_update), NOT an nfmod single modulo.
                self._skip_advance = True                  # +incr lands NEXT frame via the
                #   normal update() advance, NOT baked into the scramble. Live-pinned:
                #   frame2 = 598*oldFrame mod 23 (no incr); frame3 = +incr.
            trans_to = self._pending_state
            self.state = self._pending_state
            self._pending_state = None
            if trans_to == 55:                    # now swimming -> subsequent entries are
                self._warm = True                 # WARM pumps, not the cold-start initiation.
            if trans_to == 54:                    # ESS->neutral EXIT wipes stale charge
                self._pending_gain = 0.0          # gain; the neutral->ESS pump KEEPS a
                                                  # freshly-scheduled cold-start charge.
        desired = 54 if action == 'neu' else 55

        if self.state == 54:                      # NEUTRAL physics (drag-free)
            if desired == 55 and not self._warm:  # COLD-START initiation frame: stash
                self._scramble_oldframe = f32(self.anim + 1.0)  # oldFrame = display(start)+1.0
            if self._just_released:               # exit-release frame: display anim was just
                self._just_released = False        # set to (swiming/23)*26 by the exit branch;
                                                  # the neutral rate lands NEXT frame (live-
                                                  # pinned: post[1] == rescaled value exactly,
                                                  # no neutral advance) and v keeps the release.
            else:
                self.anim = fc_update(self.anim, neutral_anim_rate(self.air), 26.0)  # SWIMWAIT end=26
                # NEUTRAL speed decay = setNormalSpeedF's cLib_addCalc chase toward 0
                # (d_a_player_main.cpp:2348, swim.inc:81 with param_1==0): NOT a flat -2.
                # cLib_addCalc(v, 0, scale=0.02, maxStep=2.0, minStep=0.5): |v|>100 -> step 2.0
                # (the old flat-2, so 200k/high-speed dash unchanged), 25<|v|<100 -> 0.02*|v|
                # (proportional), |v|<25 -> snaps 0.5/frame to 0. Live-pinned (scale 0.02 exact,
                # maxStep 2.0, minStep 0.5, reaches 0 with no overshoot). HIO mSwim field_0x18/
                # 1C/20. The old flat -2 was right only above |v|=100 -> wrong on the low-speed
                # tail and after many pumps bleed v, where it x598-compounded into divergence.
                self.v = cLib_addCalc(self.v, 0.0, 0.02, 2.0, 0.5)
            if is_chg:                            # charging FROM neutral (cold start / pump
                self._pending_gain = self._swim_facing(*self._chg_stick(chg_up))  # decomp gain:
                self._pending_flip = True         # snap (opposing facing) -> -3, aligned ->
                                                  # +3 (the warm-pump spin-up). gain+flip land
                                                  # next frame (when state has become 55).
            d = self._move(self.v)                # move == potential (|step| == |v|)
            tag = 'NEU'
        else:                                     # STATE 55: ESS / charge
            # action 'neu' here = the held ESS exit frame; is_chg/chg_up computed above.
            rawY = int(action.split(':')[1]) if action.startswith('ess') and ':' in action else 110
            if self._skip_advance:                # scramble frame: anim already = ess_start
                self._skip_advance = False
            else:
                self._advance_anim_55()           # anim rate lags 1 frame: uses pre-update v
            # Compute this frame's facing-based swim gain (= mStickDistance*3*cM_scos(d_turn),
            # setSpeedAndAngleSwim) and schedule the facing snap/turn. ESS aligned -> +1/6;
            # ESS just after a snapping charge (facing not yet re-aligned) -> -1/6 (the live
            # transient the old fixed +1/6 ess_decay missed). A 'neu' held-exit frame has a
            # neutral stick -> no swim input -> facing frozen.
            if is_chg:
                swim_gain = self._swim_facing(*self._chg_stick(chg_up))
            elif action.startswith('ess'):
                swim_gain = self._swim_facing(128, rawY)
            else:                                 # 'neu' held-exit frame (neutral stick)
                swim_gain = ess_decay(rawY)       # validated exit-frame decay (facing frozen)
            # setSpeedAndAngleSwim gain lags ONE frame UNIFORMLY for ESS and charge (lands
            # next frame via _pending_gain). See history/resolved-bugs.md#bug3.
            if self._pending_gain:                # gain scheduled last frame lands now,
                self.v = f32(self.v + self._pending_gain)   # replacing this frame's decay
                self._pending_gain = 0.0
            elif self._entry_tax and not is_chg:  # one-time -3 facing-flip transient (slate)
                self.v = f32(self.v - 3.0)
                self._entry_tax = False
            elif is_chg:                          # 1st charge of a cold burst: no pending
                self.v = f32(self.v + ess_decay(rawY))   # gain yet; this frame still decays
            elif self._post_burst_transient is not None:  # legacy carry (now unused; kept
                self.v = f32(self.v + self._post_burst_transient)   # for safety/no-op)
                self._post_burst_transient = None
            else:
                self.v = f32(self.v + swim_gain)  # 1st ESS of a cold burst (no pending): the
                #   facing-based gain lands this frame (no prior frame scheduled one).
            if action.startswith('ess') or is_chg:   # schedule THIS frame's gain for next
                self._pending_gain = swim_gain        # frame (uniform 1-frame lag, decomp).
            if is_chg:
                self._pending_flip = True         # charge facing flip also lands next frame
            fac = CHARGE_DISP_FACTOR if is_chg else 1.0
            d = self._move(fac * true_disp(self.v, self.anim, self.air))
            tag = 'CHG' if is_chg else 'ESS'

        if desired != self.state:                 # schedule the lagged transition
            self._pending_state = desired
        # AIR REFILL (opt-in, default off so baselines are untouched): while the swim has
        # not yet committed forward progress (distance to dest still == initial, i.e. the
        # in-place charge build), air is refilled to 900 -- modelling the real "air refill
        # before cruising" so the ESS cruise/pumps run at low drag (high air). Free reset
        # (user-specified model). Once -x passes refill_until (cruise begins), air depletes.
        if self._refill_air and (-self.x) <= self._refill_until:
            self.air = 900
        else:
            self.air -= 1
        return d, tag

def run_trace(actions, v, anim, air, entry_tax=True):
    """actions: iterable of action strings. Returns list of per-frame dict rows."""
    s = SwimState(v=v, anim=anim, air=air)
    s._entry_tax = entry_tax
    rows = []
    x0, z0 = s.x, s.z
    path = 0.0
    for i, act in enumerate(actions):
        d, tag = s.step(act)
        path += abs(d)
        net = math.hypot(s.x - x0, s.z - z0)
        rows.append({"f": i + 1, "x": s.x, "z": s.z, "v": s.v, "anim": s.anim,
                     "air": s.air, "state": s.state, "step": d, "tag": tag,
                     "path": path, "net": net,
                     "eff": 0.6 + 0.4 * abs(math.cos(math.pi * s.anim / 23.0))})
    return rows

def parse_seq(spec):
    acts = []
    for part in spec.split(';'):
        part = part.strip()
        if not part:
            continue
        a, n = part.rsplit(',', 1)
        acts.extend([a.strip()] * int(n))
    return acts

def essloop_actions(frames, lo, hi, boost):
    """Replicates dolphin essloop: hold ESS, fire a `boost`-frame charge burst when
    anim enters [lo,hi] (wraps if lo>hi), with cooldown (must leave window to refire)."""
    def in_win(a):
        return (lo <= a <= hi) if lo <= hi else (a >= lo or a <= hi)
    return _ClosedLoop(frames, in_win, boost)

class _ClosedLoop:
    """Lazy action generator that needs to see live anim — handled in run_closed."""
    def __init__(self, frames, in_win, boost):
        self.frames, self.in_win, self.boost = frames, in_win, boost

def run_closed(cl, v, anim, air, entry_tax=True):
    s = SwimState(v=v, anim=anim, air=air)
    s._entry_tax = entry_tax
    rows = []
    x0, z0 = s.x, s.z
    path = 0.0
    armed = True
    nboost = 0
    while len(rows) < cl.frames:
        if cl.boost and armed and cl.in_win(s.anim):
            for _ in range(cl.boost):
                if len(rows) >= cl.frames:
                    break
                d, tag = s.step('chg')
                path += abs(d)
                rows.append(_row(s, len(rows) + 1, d, tag, path, x0, z0))
            nboost += 1
            armed = False
            continue
        d, tag = s.step('ess')
        path += abs(d)
        rows.append(_row(s, len(rows) + 1, d, tag, path, x0, z0))
        if not armed and not cl.in_win(s.anim):
            armed = True
    return rows, nboost

def _row(s, f, d, tag, path, x0, z0):
    return {"f": f, "x": s.x, "z": s.z, "v": s.v, "anim": s.anim, "air": s.air,
            "state": s.state, "step": d, "tag": tag, "path": path,
            "net": math.hypot(s.x - x0, s.z - z0),
            "eff": 0.6 + 0.4 * abs(math.cos(math.pi * s.anim / 23.0))}

def summarize(rows, extra=""):
    n = len(rows)
    path = rows[-1]["path"]
    net = rows[-1]["net"]
    last = rows[-1]
    print(f"SUMMARY frames={n} path={path:.2f} net={net:.2f} "
          f"path/fr={path/n:.3f} net/fr={net/n:.3f} "
          f"v={last['v']:.5g} air={last['air']} anim={last['anim']:.4g} {extra}")

def emit_viz(path_html, traces):
    """traces: list of {name,color,rows}. Writes a self-contained animated viewer."""
    payload = json.dumps([{"name": t["name"], "color": t["color"],
                           "rows": [{k: r[k] for k in ("x", "z", "v", "anim", "air", "step", "tag", "eff")}
                                    for r in t["rows"]]} for t in traces])
    html = _VIZ_TEMPLATE.replace("__DATA__", payload)
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {path_html}")

_VIZ_TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>superswim</title>
<style>
 body{margin:0;background:#0d1117;color:#c9d1d9;font:13px system-ui,sans-serif}
 #wrap{display:flex;flex-direction:column;height:100vh}
 #top{flex:1;position:relative}
 canvas{position:absolute;inset:0;width:100%;height:100%}
 #hud{padding:8px 12px;background:#161b22;border-top:1px solid #30363d}
 .row{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
 .gauge{min-width:120px}
 .bar{height:8px;background:#21262d;border-radius:4px;overflow:hidden;margin-top:3px}
 .bar>div{height:100%}
 button{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:4px 10px;cursor:pointer}
 .leg{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
 input[type=range]{vertical-align:middle}
</style></head>
<body><div id="wrap">
 <div id="top"><canvas id="c"></canvas></div>
 <div id="hud">
   <div class="row">
     <button id="play">⏸ pause</button>
     <input id="scrub" type="range" min="0" max="100" value="0" style="flex:1">
     <span id="fnum">f 0</span>
     <label>speed <select id="rate"><option>0.5</option><option selected>1</option><option>2</option><option>4</option></select>×</label>
   </div>
   <div class="row" id="gauges"></div>
   <div class="row" id="legend"></div>
 </div>
</div>
<script>
const DATA = __DATA__;
const c = document.getElementById('c'), ctx = c.getContext('2d');
const N = Math.max(...DATA.map(t=>t.rows.length));
// world bounds across all traces
let minX=1e18,maxX=-1e18,minZ=1e18,maxZ=-1e18;
for(const t of DATA) for(const r of t.rows){minX=Math.min(minX,r.x);maxX=Math.max(maxX,r.x);minZ=Math.min(minZ,r.z);maxZ=Math.max(maxZ,r.z);}
let frame=0, playing=true, t0=null;
function resize(){c.width=c.clientWidth*devicePixelRatio;c.height=c.clientHeight*devicePixelRatio;}
window.addEventListener('resize',resize);resize();
function tf(x,z){ // world -> screen, fit with margin, keep aspect
  const W=c.width,H=c.height,m=40*devicePixelRatio;
  const sx=(W-2*m)/((maxX-minX)||1), sz=(H-2*m)/((maxZ-minZ)||1), s=Math.min(sx,sz);
  return [m+(x-minX)*s + (W-2*m-(maxX-minX)*s)/2, m+(z-minZ)*s + (H-2*m-(maxZ-minZ)*s)/2];
}
function draw(){
  ctx.clearRect(0,0,c.width,c.height);
  for(const t of DATA){
    const rows=t.rows, upto=Math.min(frame,rows.length-1);
    // trail
    ctx.lineWidth=2*devicePixelRatio;ctx.strokeStyle=t.color;ctx.globalAlpha=0.55;ctx.beginPath();
    for(let i=0;i<=upto;i++){const[px,py]=tf(rows[i].x,rows[i].z);i?ctx.lineTo(px,py):ctx.moveTo(px,py);}
    ctx.stroke();ctx.globalAlpha=1;
    // boost markers
    for(let i=0;i<=upto;i++) if(rows[i].tag==='CHG'){const[px,py]=tf(rows[i].x,rows[i].z);
      ctx.fillStyle='#f0883e';ctx.beginPath();ctx.arc(px,py,3*devicePixelRatio,0,7);ctx.fill();}
    // head
    if(upto>=0){const[hx,hy]=tf(rows[upto].x,rows[upto].z);
      ctx.fillStyle=t.color;ctx.beginPath();ctx.arc(hx,hy,6*devicePixelRatio,0,7);ctx.fill();
      ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(hx,hy,2*devicePixelRatio,0,7);ctx.fill();}
  }
  // gauges + legend
  const g=document.getElementById('gauges');g.innerHTML='';
  for(const t of DATA){const r=t.rows[Math.min(frame,t.rows.length-1)];
    g.innerHTML+=`<div class="gauge"><b style="color:${t.color}">${t.name}</b><br>`+
      `v ${r.v.toFixed(1)} &nbsp; anim ${r.anim.toFixed(2)} &nbsp; air ${r.air}<br>`+
      `eff ${(r.eff*100).toFixed(1)}% step ${r.step.toFixed(0)}`+
      `<div class="bar"><div style="width:${((r.eff-0.6)/0.4*100).toFixed(0)}%;background:${t.color}"></div></div></div>`;}
  const lg=document.getElementById('legend');
  lg.innerHTML=DATA.map(t=>`<span><span class="leg" style="background:${t.color}"></span>${t.name}</span>`).join(' &nbsp; ')+
    ` &nbsp; <span><span class="leg" style="background:#f0883e"></span>boost frame</span>`;
  document.getElementById('fnum').textContent='f '+frame;
  document.getElementById('scrub').value=(frame/(N-1)*100)||0;
}
function tick(ts){
  if(t0===null)t0=ts;
  if(playing){const rate=parseFloat(document.getElementById('rate').value);
    const fps=30*rate; frame=Math.min(N-1,Math.floor((ts-t0)/1000*fps));
    if(frame>=N-1){playing=false;document.getElementById('play').textContent='↻ replay';}}
  draw();requestAnimationFrame(tick);
}
document.getElementById('play').onclick=()=>{
  if(frame>=N-1){frame=0;t0=null;}
  playing=!playing;document.getElementById('play').textContent=playing?'⏸ pause':'▶ play';
  if(playing)t0=null;
};
document.getElementById('scrub').oninput=e=>{playing=false;frame=Math.round(e.target.value/100*(N-1));
  document.getElementById('play').textContent='▶ play';draw();};
requestAnimationFrame(tick);
</script></body></html>"""

def parse_opts(argv):
    opts = {}
    pos = []
    for tok in argv:
        if '=' in tok:
            k, _, v = tok.partition('=')
            opts[k] = v
        else:
            pos.append(tok)
    return pos, opts

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    pos, opts = parse_opts(sys.argv[2:])
    v = float(opts.get('v', '-1630'))
    air = int(opts.get('air', '900'))
    anim = float(opts.get('anim', '0'))
    every = int(opts.get('every', '0'))

    if cmd == 'arrowseq':
        # arrowseq "sx,sy;sx,sy;..." [v=][air=][anim=][facing=90][cam=270]
        sticks = [tuple(int(t) for t in p.split(',')) for p in pos[0].split(';') if p]
        facing = float(opts.get('facing', '90'))
        cam = float(opts.get('cam', '270'))
        rows = run_arrow(sticks, v=v, anim=anim, air=air, facing_deg=facing, cam_deg=cam)
        print("f  stick      facing  tag    v        dx      dz   moveBrg net   netBrg")
        for r in rows:
            print(f"{r['f']:<3}({r['stick'][0]:>3},{r['stick'][1]:<3}) {r['facing']:6.0f}  "
                  f"{r['tag']:<5} {r['v']:8.2f} {r['dx']:+7.0f} {r['dz']:+6.0f} "
                  f"{r['move_brg']:5.0f}  {r['net']:6.0f} {r['net_brg']:5.0f}")
        rl = rows[-1]
        print(f"SUMMARY {len(rows)} frames: net={rl['net']:.0f} bearing={rl['net_brg']:.0f} "
              f"v={rl['v']:.1f} facing={rl['facing']:.0f}")
        return
    if cmd == 'seq':
        rows = run_trace(parse_seq(pos[0]), v, anim, air)
        extra = ""
    elif cmd == 'essloop':
        frames = int(opts.get('frames', '150'))
        lo, hi = (float(x) for x in opts.get('trig', '21,2').split(','))
        boost = int(opts.get('boost', '2'))
        rows, nboost = run_closed(essloop_actions(frames, lo, hi, boost), v, anim, air)
        extra = f"boosts={nboost}"
    elif cmd == 'compare':
        # compare frames=N trig=LO,HI boost=B  -> baseline ESS vs reboost, overlaid
        frames = int(opts.get('frames', '150'))
        lo, hi = (float(x) for x in opts.get('trig', '13,16').split(','))
        boost = int(opts.get('boost', '4'))
        base = run_trace(['ess'] * frames, v, anim, air)
        rb, nboost = run_closed(essloop_actions(frames, lo, hi, boost), v, anim, air)
        print("baseline  ", end=""); summarize(base)
        print(f"reboost   ", end=""); summarize(rb, f"boosts={nboost}")
        out = opts.get('viz', 'superswim_compare.html')
        emit_viz(out, [{"name": "pure ESS", "color": "#58a6ff", "rows": base},
                       {"name": f"reboost b{boost}@{lo:.0f}-{hi:.0f}", "color": "#3fb950", "rows": rb}])
        return
    else:
        print(f"unknown cmd {cmd}"); sys.exit(1)

    if every:
        print("f\tv\tanim\tair\teff\ttag\tstep\tnet")
        for r in rows:
            if r["f"] % every == 0:
                print(f"{r['f']}\t{r['v']:.1f}\t{r['anim']:.3g}\t{r['air']}\t"
                      f"{r['eff']*100:.1f}\t{r['tag']}\t{r['step']:.1f}\t{r['net']:.1f}")
    summarize(rows, extra)

    if 'json' in opts:
        json.dump(rows, open(opts['json'], 'w'))
        print(f"wrote {opts['json']}")
    if 'viz' in opts:
        emit_viz(opts['viz'], [{"name": cmd, "color": "#58a6ff", "rows": rows}])

if __name__ == '__main__':
    main()
