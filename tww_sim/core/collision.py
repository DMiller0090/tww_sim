"""FP-faithful port of TWW's player WALL collision resolution.

Ports the horizontal-blocking parts of `dBgS_Acch::CrrPos` — the two barriers that stop or
redirect Link's XZ movement each frame:

  * **LineCheck** (swept): tests Link's centre-line ``old -> new`` against each wall triangle via
    ``cM3d_Cross_LinTri`` = plane crossing (``cM3d_Cross_LinPla``) + projected point-in-triangle
    (``cM3d_CrossX/Y/Z_Tri``). Front-to-back only (``frontFlag=1``). Runs only when the horizontal
    displacement exceeds the wall radius.
  * **WallCorrect** (static): pushes Link's wall cylinder (radius 35) out of any wall it overlaps at
    the NEW position (``dBgW::RwgWallCorrect`` + ``positionWallCorrect`` / ``cM2d_CrossCirLin``).

Given ``old_pos`` and the intended ``new_pos`` (= old + one frame of velocity), :func:`crr_pos_walls`
returns the position the game would resolve to. If it stays at ``new_pos`` the move "clipped"
(collision didn't interfere); otherwise Link was blocked / pushed.

**Bit-exact vs the console.** Arithmetic uses the fused-multiply-add single-precision ops in
:mod:`tww_sim.core.fp`. The one fused op in this path that a naive separate-rounding port gets
wrong is the plane function's dot product: ``PSVECDotProduct`` (paired-single) computes
``dot = fadds(fmadds(nx,px, fmuls(ny,py)), fmuls(nz,pz))`` — ``nx*px + ny*py`` is fused (rounds
once). ``cM3d_VectorProduct2d`` and the crossing interpolation (``cM3d_InDivPos1/2``) are NOT fused
in the compiled code, so they use separate rounds. Validated live on GZLJ01 (GanonL grand-staircase
seam): reproduces the game's per-triangle crossing points to f32 and every hit/miss (24/24 live
cases). See ``knowledge/mechanics/seam-clip.md``.

**Plane normals must be the game's STORED per-triangle planes.** Each triangle stores an
independently-normalised plane (``cM3d_CalcPla``: ``normalize(cross(v1-v0, v2-v0))``, ``d=-dot(n,v0)``).
The two triangles of one wall quad differ in the last bits, and that difference is exactly what
opens the seam gap — so feed :class:`Tri` the stored ``(n, d)`` (read from ``cBgW.pm_tri``, stride
0x18) rather than recomputing, or the razor-edge cases land on the wrong side. :func:`calc_pla`
reproduces the compute path for reference but is not bit-identical to the console's rsqrt-normalise.

Decomp refs: ``src/SSystem/SComponent/c_m3d.cpp`` (``cM3d_Cross_Lin*``, ``cM3d_CrossX/Y/Z_Tri``),
``c_m2d.cpp`` (``cM2d_CrossCirLin``), ``src/d/d_bg_w.cpp`` (``RwgWallCorrect``), ``src/d/d_bg_s_acch.cpp``
(``CrrPos``/``LineCheck``). Pure stdlib + ``core.fp``; no Dolphin dependency.
"""
import math

from .fp import f32 as _f, fadds, fsubs, fmuls, fdivs, fmadds

# cM3d_IsZero threshold (kZero, c_m3d.h). Distinct from the point-in-triangle 20.0 area tolerance.
G_CM3D_F_ABS_MIN = 1.0e-5


def is_zero(x):
    return abs(_f(x)) < G_CM3D_F_ABS_MIN


def fsqrt(a):
    return _f(math.sqrt(_f(a)))


# --------------------------------------------------------------------------- plane
class Plane:
    """A wall triangle's plane: unit-ish normal (nx,ny,nz) + offset d, matching the game's stored
    ``cM3dGPla``. ``func(p) = d + n.p`` reproduces ``getPlaneFunc`` via ``PSVECDotProduct``."""
    __slots__ = ("nx", "ny", "nz", "d")

    def __init__(self, nx, ny, nz, d):
        self.nx = _f(nx); self.ny = _f(ny); self.nz = _f(nz); self.d = _f(d)

    def func(self, p):
        ny_py = fmuls(self.ny, p[1])
        nz_pz = fmuls(self.nz, p[2])
        dot = fadds(fmadds(self.nx, p[0], ny_py), nz_pz)   # nx*px + ny*py FUSED (ps_madd lane)
        return fadds(self.d, dot)


def calc_pla(v0, v1, v2):
    """``cM3d_CalcPla`` reference (NOT console-bit-exact: uses libm sqrt, not Gekko frsqrte).
    Prefer the stored plane. normalize(cross(v1-v0, v2-v0)); d = -dot(n, v0)."""
    ax, ay, az = fsubs(v1[0], v0[0]), fsubs(v1[1], v0[1]), fsubs(v1[2], v0[2])
    bx, by, bz = fsubs(v2[0], v0[0]), fsubs(v2[1], v0[1]), fsubs(v2[2], v0[2])
    nx = fsubs(fmuls(ay, bz), fmuls(az, by))
    ny = fsubs(fmuls(az, bx), fmuls(ax, bz))
    nz = fsubs(fmuls(ax, by), fmuls(ay, bx))
    t = fsqrt(fadds(fadds(fmuls(nx, nx), fmuls(ny, ny)), fmuls(nz, nz)))
    if abs(t) >= 0.02:
        nx = fdivs(nx, t); ny = fdivs(ny, t); nz = fdivs(nz, t)
        d = _f(-(fadds(fadds(fmuls(nx, v0[0]), fmuls(ny, v0[1])), fmuls(nz, v0[2]))))
        return Plane(nx, ny, nz, d)
    return Plane(0.0, 0.0, 0.0, 0.0)


class Tri:
    """Wall triangle: three world verts + a plane. Pass ``plane=Plane(*n, d)`` with the game's
    STORED plane for bit-exact results; otherwise :func:`calc_pla` is used (reference only)."""
    __slots__ = ("v0", "v1", "v2", "pla")

    def __init__(self, v0, v1, v2, plane=None):
        self.v0 = tuple(_f(c) for c in v0)
        self.v1 = tuple(_f(c) for c in v1)
        self.v2 = tuple(_f(c) for c in v2)
        self.pla = plane if plane is not None else calc_pla(self.v0, self.v1, self.v2)


# ------------------------------------------------------------------ line vs plane
def indiv_pos2(v0, v1, scale):
    """cM3d_InDivPos2/1: v0 + (v1-v0)*scale, per component (VECSubtract, VECScale, VECAdd — each
    a separate round; not fused)."""
    return (fadds(v0[0], fmuls(fsubs(v1[0], v0[0]), scale)),
            fadds(v0[1], fmuls(fsubs(v1[1], v0[1]), scale)),
            fadds(v0[2], fmuls(fsubs(v1[2], v0[2]), scale)))


def cross_lin_pla(start, end, pla, a=True, b=False):
    """cM3d_Cross_LinPla -> (crossed, point). a=frontFlag, b=backFlag."""
    sv = pla.func(start)
    ev = pla.func(end)
    if fmuls(sv, ev) > 0.0:
        return False, end
    if sv >= 0.0 and ev <= 0.0:        # front -> back
        if a:
            return _cross_proc(sv, ev, start, end)
    else:                               # back -> front
        if b:
            return _cross_proc(sv, ev, start, end)
    return False, end


def _cross_proc(a, b, pA, pB):
    if is_zero(fsubs(a, b)):
        return False, pB
    return True, indiv_pos2(pA, pB, fdivs(a, fsubs(a, b)))


# ------------------------------------------------------ projected point-in-triangle
def vprod2d(x1, y1, x2, y2, x3, y3):
    """cM3d_VectorProduct2d = (x2-x1)*(y3-y1) - (y2-y1)*(x3-x1). Separate rounds (not fused)."""
    return fsubs(fmuls(fsubs(x2, x1), fsubs(y3, y1)), fmuls(fsubs(y2, y1), fsubs(x3, x1)))


def incl_box2d(ax, ay, bx, by, cx, cy, px, py):
    """cM3d_InclusionCheckPosIn3PosBox2d: point within the AABB of the 3 projected verts (strict)."""
    if ax < bx: f31, f30 = ax, bx
    else:       f31, f30 = bx, ax
    if f31 > cx: f31 = cx
    elif f30 < cx: f30 = cx
    if f31 > px or f30 < px: return False
    if ay < by: f31, f30 = ay, by
    else:       f31, f30 = by, ay
    if f31 > cy: f31 = cy
    elif f30 < cy: f30 = cy
    if f31 > py or f30 < py: return False
    return True


def _tri_in_2d(ax, ay, bx, by, cx, cy, px, py):
    """Shared body of CrossX/Y/Z_Tri: AABB gate + signed-area edge tests with a +/-20 area tolerance
    on BOTH windings."""
    if not incl_box2d(ax, ay, bx, by, cx, cy, px, py):
        return False
    f12 = vprod2d(ax, ay, bx, by, px, py)
    if (f12 <= 20.0
            and vprod2d(bx, by, cx, cy, px, py) <= 20.0
            and vprod2d(cx, cy, ax, ay, px, py) <= 20.0):
        return True
    if (f12 >= -20.0
            and vprod2d(bx, by, cx, cy, px, py) >= -20.0
            and vprod2d(cx, cy, ax, ay, px, py) >= -20.0):
        return True
    return False


def crossX_tri(tri, pos):
    if is_zero(tri.pla.nx): return False
    v0, v1, v2 = tri.v0, tri.v1, tri.v2
    return _tri_in_2d(v0[1], v0[2], v1[1], v1[2], v2[1], v2[2], pos[1], pos[2])


def crossY_tri(tri, pos):
    if is_zero(tri.pla.ny): return False
    v0, v1, v2 = tri.v0, tri.v1, tri.v2
    return _tri_in_2d(v0[2], v0[0], v1[2], v1[0], v2[2], v2[0], pos[2], pos[0])


def crossZ_tri(tri, pos):
    if is_zero(tri.pla.nz): return False
    v0, v1, v2 = tri.v0, tri.v1, tri.v2
    return _tri_in_2d(v0[0], v0[1], v1[0], v1[1], v2[0], v2[1], pos[0], pos[1])


def cross_lin_tri(start, end, tri, a=True, b=False):
    """cM3d_Cross_LinTri -> (hit, point). Plane crossing + point-in-triangle in the projections
    whose normal component is significant (|n_axis| >= 0.008)."""
    crossed, dst = cross_lin_pla(start, end, tri.pla, a, b)
    if not crossed:
        return False, dst
    n = tri.pla
    okx = (abs(n.nx) < 0.008) or crossX_tri(tri, dst)
    oky = (abs(n.ny) < 0.008) or crossY_tri(tri, dst)
    okz = (abs(n.nz) < 0.008) or crossZ_tri(tri, dst)
    return (okx and oky and okz), dst


# --------------------------------------------------------------------- LineCheck
def line_check(old_pos, new_pos, tris, wall_h):
    """dBgS_Acch::LineCheck over the wall cylinders. Returns (hit, snapped_new_pos). For a vertical
    wall the XZ crossing is height-independent, but all cylinder heights are run for fidelity."""
    pos = list(new_pos)
    hit_any = False
    for h in wall_h:
        start = (old_pos[0], fadds(old_pos[1], h), old_pos[2])
        end = (pos[0], fadds(pos[1], h), pos[2])
        cur_end = end
        hit_here = False
        for tri in tris:                          # LineCross: nearest front crossing shrinks the line
            crossed, pt = cross_lin_tri(start, cur_end, tri, a=True, b=False)
            if crossed:
                cur_end = pt
                hit_here = True
        if hit_here:
            hit_any = True
            pos[0] = cur_end[0]
            pos[2] = cur_end[2]
            pos[1] = fsubs(cur_end[1], h)
    return hit_any, tuple(pos)


# ------------------------------------------------------------------- WallCorrect
def len2dsq(x0, y0, x1, y1):
    return fadds(fmuls(fsubs(x0, x1), fsubs(x0, x1)), fmuls(fsubs(y0, y1), fsubs(y0, y1)))


def len2dsq_pnt_seg(xp, yp, x0, y0, x1, y1):
    """cM3d_Len2dSqPntAndSegLine -> (on_segment, outx, outy, seg_sqdist)."""
    xd = fsubs(x1, x0); yd = fsubs(y1, y0)
    dot = fadds(fmuls(xd, xd), fmuls(yd, yd))
    if is_zero(dot):
        return False, x0, y0, 0.0
    mag = fdivs(fadds(fmuls(xd, fsubs(xp, x0)), fmuls(yd, fsubs(yp, y0))), dot)
    on = (0.0 <= mag <= 1.0)
    outx = fadds(x0, fmuls(xd, mag))
    outy = fadds(y0, fmuls(yd, mag))
    return on, outx, outy, len2dsq(outx, outy, xp, yp)


def cross_cir_lin(cx, cy, r, x0, y0, dirx, diry):
    """cM2d_CrossCirLin -> (px, py): furthest intersection of the ray (x0,y0)+t*(dirx,diry) with the
    circle (cx,cy,r)."""
    fv1 = fsubs(x0, cx); fv15 = fsubs(y0, cy)
    d13 = fadds(fmuls(dirx, dirx), fmuls(diry, diry))
    d14 = fmuls(2.0, fadds(fmuls(dirx, fv1), fmuls(diry, fv15)))
    c = fsubs(fadds(fmuls(fv1, fv1), fmuls(fv15, fv15)), fmuls(r, r))
    t = 0.0
    if is_zero(d13):
        if not is_zero(d14):
            t = fdivs(_f(-c), d14)
    else:
        disc = fsubs(fmuls(d14, d14), fmuls(fmuls(4.0, d13), c))
        if is_zero(disc):
            t = fdivs(_f(-d14), fmuls(2.0, d13))
        elif disc < 0.0:
            t = 0.0
        else:
            k = fdivs(1.0, fmuls(2.0, d13))
            s = fsqrt(disc)
            r1 = fmuls(k, fadds(_f(-d14), s))
            r2 = fmuls(k, fsubs(_f(-d14), s))
            t = r1 if r1 > r2 else r2
    if is_zero(t):
        return x0, y0
    return fadds(x0, fmuls(t, dirx)), fadds(y0, fmuls(t, diry))


def wall_correct(new_pos, speed_y, tris, wall_h, wall_r):
    """dBgW::RwgWallCorrect over all tris x cylinders (static cylinder at ``new_pos``). Assumes no
    ground-find (GetWallAddY == 0) and ChkWallHDirect false. Returns (corrected_pos, wall_hit)."""
    pos = list(new_pos)
    wrr = fmuls(wall_r, wall_r)
    hit = False
    for tri in tris:
        n = tri.pla
        sp68 = fsqrt(fadds(fmuls(n.nx, n.nx), fmuls(n.nz, n.nz)))
        if is_zero(sp68):
            continue
        sp6C = fdivs(1.0, sp68)
        for h in wall_h:
            sp78 = fmuls(sp6C, wall_r)
            sp50x = fmuls(sp78, n.nx); sp50z = fmuls(sp78, n.nz)
            sp7C = fsubs(fadds(0.0, fadds(pos[1], h)), speed_y)
            s0 = fsubs(tri.v0[1], sp7C)
            s1 = fsubs(tri.v1[1], sp7C)
            s2 = fsubs(tri.v2[1], sp7C)
            if (s0 > 0.0 and s1 > 0.0 and s2 > 0.0) or (s0 < 0.0 and s1 < 0.0 and s2 < 0.0):
                continue
            zc = is_zero(s0) + is_zero(s1) + is_zero(s2)
            if zc == 1:
                continue
            if (s0 > 0.0 and s1 <= 0.0 and s2 <= 0.0) or (s0 < 0.0 and s1 >= 0.0 and s2 >= 0.0):
                i0, i1, i2 = 0, 1, 2
            elif (s1 > 0.0 and s0 <= 0.0 and s2 <= 0.0) or (s1 < 0.0 and s0 >= 0.0 and s2 >= 0.0):
                i0, i1, i2 = 1, 0, 2
            else:
                i0, i1, i2 = 2, 0, 1
            s = (s0, s1, s2)
            sp90 = fsubs(s[i0], s[i1]); sp94 = fsubs(s[i0], s[i2])
            if is_zero(sp90) or is_zero(sp94):
                continue
            sp98 = fdivs(_f(-s[i1]), sp90); sp9C = fdivs(_f(-s[i2]), sp94)
            V = (tri.v0, tri.v1, tri.v2)
            vx = [V[0][0], V[1][0], V[2][0]]; vz = [V[0][2], V[1][2], V[2][2]]
            if i0 == 0:
                cx0 = fadds(vx[1], fmuls(sp98, fsubs(vx[0], vx[1]))); cy0 = fadds(vz[1], fmuls(sp98, fsubs(vz[0], vz[1])))
                cx1 = fadds(vx[2], fmuls(sp9C, fsubs(vx[0], vx[2]))); cy1 = fadds(vz[2], fmuls(sp9C, fsubs(vz[0], vz[2])))
            elif i0 == 1:
                cx0 = fadds(vx[0], fmuls(sp98, fsubs(vx[1], vx[0]))); cy0 = fadds(vz[0], fmuls(sp98, fsubs(vz[1], vz[0])))
                cx1 = fadds(vx[2], fmuls(sp9C, fsubs(vx[1], vx[2]))); cy1 = fadds(vz[2], fmuls(sp9C, fsubs(vz[1], vz[2])))
            else:
                cx0 = fadds(vx[0], fmuls(sp98, fsubs(vx[2], vx[0]))); cy0 = fadds(vz[0], fmuls(sp98, fsubs(vz[2], vz[0])))
                cx1 = fadds(vx[1], fmuls(sp9C, fsubs(vx[2], vx[1]))); cy1 = fadds(vz[1], fmuls(sp9C, fsubs(vz[2], vz[1])))
            cx0o = fadds(cx0, sp50x); cy0o = fadds(cy0, sp50z)
            cx1o = fadds(cx1, sp50x); cy1o = fadds(cy1, sp50z)
            on, ccx, ccy, seg = len2dsq_pnt_seg(pos[0], pos[2], cx0o, cy0o, cx1o, cy1o)
            d4 = fsubs(ccx, pos[0]); d8 = fsubs(ccy, pos[2])
            if seg > wrr or fadds(fmuls(d4, sp50x), fmuls(d8, sp50z)) < 0.0:
                continue
            if on:
                move = fmuls(sp6C, fsqrt(seg))
                pos[0] = fadds(pos[0], fmuls(move, n.nx))
                pos[2] = fadds(pos[2], fmuls(move, n.nz))
                hit = True
            else:
                e0 = len2dsq(cx0, cy0, pos[0], pos[2])
                e1 = len2dsq(cx1, cy1, pos[0], pos[2])
                onx = _f(-n.nx); ony = _f(-n.nz)
                if e0 < e1:
                    if e0 > wrr or abs(fsubs(e0, wrr)) < 0.008:
                        continue
                    fx, fy = cross_cir_lin(pos[0], pos[2], wall_r, cx0, cy0, onx, ony)
                    pos[0] = fadds(pos[0], fsubs(cx0, fx)); pos[2] = fadds(pos[2], fsubs(cy0, fy))
                    hit = True
                else:
                    if e1 > wrr or abs(fsubs(e1, wrr)) < 0.008:
                        continue
                    fx, fy = cross_cir_lin(pos[0], pos[2], wall_r, cx1, cy1, onx, ony)
                    pos[0] = fadds(pos[0], fsubs(cx1, fx)); pos[2] = fadds(pos[2], fsubs(cy1, fy))
                    hit = True
    return tuple(pos), hit


# --------------------------------------------------------------------- CrrPos
def crr_pos_walls(old_pos, new_pos, tris, wall_h=(30.1, 89.9, 125.0), wall_r=35.0, speed_y=0.0):
    """Wall-relevant part of dBgS_Acch::CrrPos. Returns (corrected_pos, info)."""
    dxz2 = len2dsq(old_pos[0], old_pos[2], new_pos[0], new_pos[2])
    ran_line = dxz2 > fmuls(wall_r, wall_r)
    pos = tuple(new_pos)
    line_hit = False
    if ran_line:
        line_hit, pos = line_check(old_pos, pos, tris, wall_h)
    pos, wall_hit = wall_correct(pos, speed_y, tris, wall_h, wall_r)
    if wall_hit and ran_line:
        lh2, pos = line_check(old_pos, pos, tris, wall_h)
        line_hit = line_hit or lh2
    return pos, {"line_hit": line_hit, "wall_hit": wall_hit, "ran_line": ran_line}
