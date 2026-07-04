"""quat.py - the quaternion path Link's cl LOWER BODY (PART_UNDER: waist/legs/feet) uses to build
each joint's local matrix. This is NOT the euler J3DGetTranslateRotateMtx path -- the foot chain is
posed by mDoExt_MtxCalcAnmBlendTblOld::calc (m_Do_ext.cpp:1164), which for EVERY joint (even single
anim) does: euler s16 -> quaternion (JMAEulerToQuat) -> [blend via JMAQuatLerp] -> matrix (mDoMtx_quat
= PSMTXQuat) -> scale+translate applied (mDoExt_setJ3DData). So fk.tr_matrix (euler->mtx direct) is
only right for direct-J3DMtxCalcMaya joints; the foot chain must use this module.

Specs (tww/):
  JMAEulerToQuat (JMath.cpp:41): half-angle via s16/2 (integer div, truncates), JMASCos/JMASSin.
    w = cos0*c1c2 + sin0*s1s2 ; x = sin0*c1c2 - cos0*s1s2 ;
    y = cos2*(cos0*sin1) + sin2*(sin0*cos1) ; z = sin2*(cos0*cos1) - cos2*(sin0*sin1).
  JMAQuatLerp (JMath.cpp:59): dot in f32 (fmadds chain); if dot<0 negate b; then the lerp
    out.c = (1.0-t)*a.c + (f64)t*temp.c is computed in DOUBLE, stored to f32 (NO normalization).
  MTXQuat==PSMTXQuat (mtx.c:1016) — C_MTXQuat (mtx.c:970) gives the math:
    s = 2/(w²+z²+x²+y²); m00=1-(yy+zz) etc. IMPORTANT: the retail PS version computes s via `fres`
    (reciprocal estimate) + one Newton step + *2, NOT an fdivs -> can differ from 2/denom by ~1 ULP.
    This module has scale='fres' (bit-faithful) and scale='fdivs' (simple) modes; default fres.

fres emulation follows the PPC 750CL algorithm (12-bit table estimate + 1 Newton-Raphson refine),
matching Dolphin's Interpreter fres. See _fres below.
"""
import struct

from superswim import fp
from superswim import sim as S


# JMACos/JMASin on s16 BAM from SEPARATE baked console tables (sin is not a wrap-around view of cos;
# 816/4096 entries differ 1 ULP -> foot-toe.z error). See sim.py _SIN_TABLE, knowledge/model/sim.md.
def _cos(a):
    return S._COS_TABLE[(int(a) & 0xFFFF) >> 4]

def _sin(a):
    return S._SIN_TABLE[(int(a) & 0xFFFF) >> 4]


def euler_to_quat(rx, ry, rz):
    """(w,x,y,z) quaternion from s16 euler (JMAEulerToQuat). C `s16/2` truncates toward zero."""
    def half(a):
        a = int(a)
        return a // 2 if a >= 0 else -((-a) // 2)
    c0, c1, c2 = _cos(half(rx)), _cos(half(ry)), _cos(half(rz))
    s0, s1, s2 = _sin(half(rx)), _sin(half(ry)), _sin(half(rz))
    c1c2 = fp.fmuls(c1, c2)
    s1s2 = fp.fmuls(s1, s2)
    w = fp.fmadds(s0, s1s2, fp.fmuls(c0, c1c2))
    x = fp.fnmsubs(c0, s1s2, fp.fmuls(s0, c1c2))          # sin0*c1c2 - cos0*s1s2
    y = fp.fmadds(s2, fp.fmuls(s0, c1), fp.fmuls(c2, fp.fmuls(c0, s1)))
    z = fp.fnmsubs(c2, fp.fmuls(s0, s1), fp.fmuls(s2, fp.fmuls(c0, c1)))  # sin2*(c0c1) - cos2*(s0s1)
    return (w, x, y, z)


def quat_lerp(a, b, t):
    """JMAQuatLerp: (w,x,y,z). dot in f32; sign-flip b; lerp in f64 -> f32. Not normalized."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    # dot = ax*bx + ay*by + az*bz + aw*bw  (f32, source order x,y,z,w)
    dot = fp.fmadds(aw, bw, fp.fmadds(az, bz, fp.fmadds(ay, by, fp.fmuls(ax, bx))))
    if dot < 0.0:
        bw, bx, by, bz = -bw, -bx, -by, -bz
    td = float(t)
    om = 1.0 - td
    def lerp(ac, tc):
        return fp.f32(om * ac + td * tc)     # computed in f64, rounded to f32
    return (lerp(aw, bw), lerp(ax, bx), lerp(ay, by), lerp(az, bz))


# --- fres: PPC 750CL reciprocal estimate + 1 Newton step (matches Dolphin Interpreter) ----------
_FRES_BASE = [
    0x7ff800, 0x783800, 0x70ea00, 0x6a0800, 0x638800, 0x5d6200, 0x579000, 0x520800,
    0x4cc800, 0x47ca00, 0x430800, 0x3e8000, 0x3a2c00, 0x360800, 0x321400, 0x2e4a00,
    0x2aa800, 0x272c00, 0x23d600, 0x209e00, 0x1d8800, 0x1a9000, 0x17ba00, 0x14f800,
    0x124e00, 0x0fbe00, 0x0d4400, 0x0ae000, 0x089000, 0x065600, 0x043200, 0x022000,
]
_FRES_DEC = [
    0x3e1, 0x3a7, 0x371, 0x340, 0x313, 0x2ea, 0x2c4, 0x2a0,
    0x27f, 0x261, 0x245, 0x22a, 0x212, 0x1fb, 0x1e5, 0x1d1,
    0x1be, 0x1ac, 0x19b, 0x18b, 0x17c, 0x16e, 0x15b, 0x15b,
    0x143, 0x143, 0x12d, 0x12d, 0x11a, 0x11a, 0x108, 0x106,
]

def _bits2d(u):
    return struct.unpack('>d', struct.pack('>Q', u & 0xFFFFFFFFFFFFFFFF))[0]

def _fres(x):
    """Hardware `fres` single-precision reciprocal estimate of x (no Newton). Matches Dolphin's
    Common::ApproximateReciprocal (750CL 5-bit-base + 10-bit-interp table)."""
    integral = struct.unpack('>Q', struct.pack('>d', x))[0]
    mantissa = integral & ((1 << 52) - 1)
    sign = integral & (1 << 63)
    exponent = integral & (0x7FF << 52)
    if mantissa == 0 and exponent == 0:
        return _bits2d(sign | (0x7FF << 52))          # 1/0 -> +-inf
    if exponent == (0x7FF << 52):
        return _bits2d(sign) if mantissa == 0 else 0.0 + x   # 1/inf=+-0; nan->nan
    if exponent < (895 << 52):
        return _bits2d(sign | (0x7FF << 52))          # tiny -> inf
    if exponent >= (1149 << 52):
        return _bits2d(sign)                          # huge -> 0
    i = mantissa >> 37                                 # top 15 mantissa bits
    base = _FRES_BASE[i >> 10]                         # top 5 bits index the base/dec table
    dec = _FRES_DEC[i >> 10]
    out = sign
    out |= ((0x7FD - (exponent >> 52)) << 52)
    out |= ((base - (dec * (i % 1024) + 1) // 2) << 29)
    return _bits2d(out)


def _recip2(denom):
    """2/denom via fres + one Newton refine + *2, matching PSMTXQuat's asm:
       est=fres(denom); r = est*(2 - denom*est); return r*2."""
    est = fp.f32(_fres(denom))
    r = fp.fmuls(est, fp.fnmsubs(denom, est, 2.0))   # est * (2 - denom*est)
    return fp.fmuls(r, 2.0)


def mtx_quat(q, scale_mode='fres'):
    """C_MTXQuat math (mtx.c:970), fused ops. q=(w,x,y,z). Returns 3x4 rotation matrix (trans=0)."""
    w, x, y, z = q
    denom = fp.fadds(fp.fmuls(w, w), fp.fadds(fp.fmuls(z, z), fp.fadds(fp.fmuls(x, x), fp.fmuls(y, y))))
    if scale_mode == 'fdivs':
        s = fp.fdivs(2.0, denom)
    else:
        s = _recip2(denom)
    xs, ys, zs = fp.fmuls(x, s), fp.fmuls(y, s), fp.fmuls(z, s)
    wx, wy, wz = fp.fmuls(w, xs), fp.fmuls(w, ys), fp.fmuls(w, zs)
    xx, xy, xz = fp.fmuls(x, xs), fp.fmuls(x, ys), fp.fmuls(x, zs)
    yy, yz, zz = fp.fmuls(y, ys), fp.fmuls(y, zs), fp.fmuls(z, zs)
    m = [[0.0]*4 for _ in range(3)]
    m[0][0] = fp.fsubs(1.0, fp.fadds(yy, zz))
    m[0][1] = fp.fsubs(xy, wz)
    m[0][2] = fp.fadds(xz, wy)
    m[1][0] = fp.fadds(xy, wz)
    m[1][1] = fp.fsubs(1.0, fp.fadds(xx, zz))
    m[1][2] = fp.fsubs(yz, wx)
    m[2][0] = fp.fsubs(xz, wy)
    m[2][1] = fp.fadds(yz, wx)
    m[2][2] = fp.fsubs(1.0, fp.fadds(xx, yy))
    return m
