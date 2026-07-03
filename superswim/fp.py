"""fp.py - FMA-faithful PowerPC 750CL single-precision (f32) float ops.

The GameCube's Gekko/Broadway (PPC 750CL) does single-precision arithmetic with a FUSED
multiply-add: `fmadds`/`fmsubs`/`fnmadds`/`fnmsubs` compute a*c(+/-)b to full internal width
and round ONCE to single. The plain sim (superswim/sim.py `f32`) rounds every op separately
(no FMA) -- correct for the swim physics as the decomp writes it (left-to-right adds/muls),
but the J3D animation Hermite eval is written with genuine fmadds/fnmsubs (J3DAnimation.cpp
inline asm), so a faithful port needs the fused ops here.

Why the f64 intermediate is EXACT for single FMA:
  inputs are f32 (24-bit mantissa), exactly representable in f64 (53-bit). The product a*b
  has <=48 mantissa bits -> exact in f64. Rounding the exact a*b+c first to f64 then to f32
  equals rounding once to f32 *provided* the intermediate carries >= 2p+2 bits (Boldo/Melquiond):
  here p=24, 2p+2=50 <= 53. So `f32((a*b)+c)` in Python f64 == the hardware's correctly-rounded
  single fmadds, bit-for-bit. (Requires callers feed f32 values -- true throughout a single-op
  chain, since PPC FPRs hold the lfs-loaded exact-f32 as f64 and single ops don't round inputs.)

Rounding: Python f64 and ctypes c_float both use IEEE round-half-to-even, matching Gekko's
default FPSCR RN. Negation is exact, so fnmsub == -(fmsub) bit-for-bit.

Extends the rules in memory `superswim-gekko-fp`. Reused later for the collision core.
"""
from ctypes import c_float as _c_float


def f32(x):
    """Round an f64 result to f32 (round-half-to-even), like a single-precision store/round."""
    return _c_float(x).value


def fmuls(a, b):
    """single a*b, rounded once."""
    return _c_float(a * b).value


def fadds(a, b):
    return _c_float(a + b).value


def fsubs(a, b):
    return _c_float(a - b).value


def fdivs(a, b):
    return _c_float(a / b).value


def fmadds(a, b, c):
    """fused a*b + c, single. One rounding of the exact product-sum (f64 intermediate exact)."""
    return _c_float(a * b + c).value


def fmsubs(a, b, c):
    """fused a*b - c, single."""
    return _c_float(a * b - c).value


def fnmadds(a, b, c):
    """fused -(a*b + c), single. Negation is exact -> == -fmadds(a,b,c)."""
    return _c_float(-(a * b + c)).value


def fnmsubs(a, b, c):
    """fused -(a*b - c) == c - a*b, single. Negation is exact -> == -fmsubs(a,b,c)."""
    return _c_float(-(a * b - c)).value
