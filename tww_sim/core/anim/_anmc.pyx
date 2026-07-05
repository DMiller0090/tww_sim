# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""_anmc.pyx - native (Cython) fast path for the land-walk anim hot loop.

Bit-EXACT drop-in replacements for the hottest pure-numeric functions of the foot-FK / quaternion /
Hermite chain (fk.mtx_concat / mtx_mult_vec, quat.euler_to_quat / quat_lerp / psmtx_quat,
j3d_eval.hermite_s16 / hermite_f32). The single-precision arithmetic is inlined as C `<double><float>`
casts -- identical to _fpc.pyx and to fp.py's ctypes path, so no FMA contraction and round-half-to-even
match Dolphin bit-for-bit. Moving the CALLERS of the fp ops into the same translation unit is the whole
point: it collapses millions of per-op Python calls into inline C.

The console cos/sin BAM tables are copied once (init_tables) into C arrays; euler_to_quat and the
quat scale/inverse read them directly. Everything here is a faithful transcription of the pure-Python
originals -- verified against the 0-ULP golden suite + the perf_land fingerprint.

Build: _build_native.py (cythonize --inplace). When the .pyd is absent the Python modules fall back to
their own pure implementations (same result), so this is an optional accelerator, never a dependency.
"""

from libc.stdlib cimport malloc, free
from libc.string cimport memcpy

# ---- single-precision primitives (identical to _fpc.pyx) -------------------------------------
cdef inline double f32(double x) nogil: return <double><float>x
cdef inline double fmuls(double a, double b) nogil: return <double><float>(a * b)
cdef inline double fadds(double a, double b) nogil: return <double><float>(a + b)
cdef inline double fsubs(double a, double b) nogil: return <double><float>(a - b)
cdef inline double fdivs(double a, double b) nogil: return <double><float>(a / b)
cdef inline double fmadds(double a, double b, double c) nogil: return <double><float>(a * b + c)
cdef inline double fmsubs(double a, double b, double c) nogil: return <double><float>(a * b - c)
cdef inline double fnmadds(double a, double b, double c) nogil: return <double><float>(-(a * b + c))
cdef inline double fnmsubs(double a, double b, double c) nogil: return <double><float>(-(a * b - c))

# ---- console BAM cos/sin tables (populated by init_tables from mathlib) -----------------------
cdef double COS_TABLE[4096]
cdef double SIN_TABLE[4096]
cdef bint _TABLES_READY = False


def init_tables(cos_table, sin_table):
    """Copy the console jmaCosTable / jmaSinTable (4096 f32 values each) into C arrays. Idempotent."""
    global _TABLES_READY
    cdef int i
    for i in range(4096):
        COS_TABLE[i] = cos_table[i]
        SIN_TABLE[i] = sin_table[i]
    _TABLES_READY = True


def tables_ready():
    return _TABLES_READY


cdef inline double jma_cos(long long a) nogil:
    return COS_TABLE[(a & 0xFFFF) >> 4]

cdef inline double jma_sin(long long a) nogil:
    return SIN_TABLE[(a & 0xFFFF) >> 4]


# ---- fres: PPC 750CL reciprocal estimate (matches Dolphin ApproximateReciprocal) -------------
cdef unsigned int _FRES_BASE[32]
cdef unsigned int _FRES_DEC[32]
cdef bint _FRES_INIT = False

cdef void _init_fres() nogil:
    global _FRES_INIT
    cdef unsigned int base[32]
    cdef unsigned int dec[32]
    base[0]=0x7ff800; base[1]=0x783800; base[2]=0x70ea00; base[3]=0x6a0800
    base[4]=0x638800; base[5]=0x5d6200; base[6]=0x579000; base[7]=0x520800
    base[8]=0x4cc800; base[9]=0x47ca00; base[10]=0x430800; base[11]=0x3e8000
    base[12]=0x3a2c00; base[13]=0x360800; base[14]=0x321400; base[15]=0x2e4a00
    base[16]=0x2aa800; base[17]=0x272c00; base[18]=0x23d600; base[19]=0x209e00
    base[20]=0x1d8800; base[21]=0x1a9000; base[22]=0x17ae00; base[23]=0x14f800
    base[24]=0x124400; base[25]=0x0fbe00; base[26]=0x0d3800; base[27]=0x0ade00
    base[28]=0x088400; base[29]=0x065000; base[30]=0x041c00; base[31]=0x020c00
    dec[0]=0x3e1; dec[1]=0x3a7; dec[2]=0x371; dec[3]=0x340
    dec[4]=0x313; dec[5]=0x2ea; dec[6]=0x2c4; dec[7]=0x2a0
    dec[8]=0x27f; dec[9]=0x261; dec[10]=0x245; dec[11]=0x22a
    dec[12]=0x212; dec[13]=0x1fb; dec[14]=0x1e5; dec[15]=0x1d1
    dec[16]=0x1be; dec[17]=0x1ac; dec[18]=0x19b; dec[19]=0x18b
    dec[20]=0x17c; dec[21]=0x16e; dec[22]=0x15b; dec[23]=0x15b
    dec[24]=0x143; dec[25]=0x143; dec[26]=0x12d; dec[27]=0x12d
    dec[28]=0x11a; dec[29]=0x11a; dec[30]=0x108; dec[31]=0x106
    cdef int i
    for i in range(32):
        _FRES_BASE[i] = base[i]
        _FRES_DEC[i] = dec[i]
    _FRES_INIT = True

cdef inline unsigned long long _d2u(double x) nogil:
    return (<unsigned long long*>&x)[0]

cdef inline double _u2d(unsigned long long u) nogil:
    return (<double*>&u)[0]

cdef double _fres(double x) nogil:
    """Hardware fres estimate of x (no Newton). Bit-identical to quat._fres."""
    if not _FRES_INIT:
        _init_fres()
    cdef unsigned long long integral = _d2u(x)
    cdef unsigned long long mantissa = integral & ((<unsigned long long>1 << 52) - 1)
    cdef unsigned long long sign = integral & (<unsigned long long>1 << 63)
    cdef unsigned long long exponent = integral & (<unsigned long long>0x7FF << 52)
    cdef unsigned long long i, base, dec, out
    if mantissa == 0 and exponent == 0:
        return _u2d(sign | (<unsigned long long>0x7FF << 52))
    if exponent == (<unsigned long long>0x7FF << 52):
        return _u2d(sign) if mantissa == 0 else 0.0 + x
    if exponent < (<unsigned long long>895 << 52):
        return _u2d(sign | (<unsigned long long>0x7FF << 52))
    if exponent >= (<unsigned long long>1149 << 52):
        return _u2d(sign)
    i = mantissa >> 37
    base = _FRES_BASE[i >> 10]
    dec = _FRES_DEC[i >> 10]
    out = sign
    out |= ((<unsigned long long>0x7FD - (exponent >> 52)) << 52)
    out |= ((base - (dec * (i % 1024) + 1) // 2) << 29)
    return _u2d(out)

cdef inline double _recip2(double denom) nogil:
    """2/denom via fres + one Newton refine + *2 (PSMTXQuat asm)."""
    cdef double est = f32(_fres(denom))
    cdef double r = fmuls(est, fnmsubs(denom, est, 2.0))
    return fmuls(r, 2.0)


# ---- euler s16 -> quaternion (JMAEulerToQuat, non-fused) --------------------------------------
cdef inline long long _half(long long a) nogil:
    # C `s16/2` truncates toward zero (Python's // truncates toward -inf, so replicate that here).
    return a // 2 if a >= 0 else -((-a) // 2)

cdef void _euler_to_quat_c(long long rx, long long ry, long long rz, double* out) nogil:
    """out[0..3] = (w,x,y,z). Bit-exact core of quat.euler_to_quat."""
    cdef double c0 = jma_cos(_half(rx)), c1 = jma_cos(_half(ry)), c2 = jma_cos(_half(rz))
    cdef double s0 = jma_sin(_half(rx)), s1 = jma_sin(_half(ry)), s2 = jma_sin(_half(rz))
    cdef double c1c2 = fmuls(c1, c2)
    cdef double s1s2 = fmuls(s1, s2)
    out[0] = fadds(fmuls(c0, c1c2), fmuls(s0, s1s2))
    out[1] = fsubs(fmuls(s0, c1c2), fmuls(c0, s1s2))
    out[2] = fadds(fmuls(c2, fmuls(c0, s1)), fmuls(s2, fmuls(s0, c1)))
    out[3] = fsubs(fmuls(s2, fmuls(c0, c1)), fmuls(c2, fmuls(s0, s1)))

def euler_to_quat(rx, ry, rz):
    """(w,x,y,z) from s16 euler. Bit-exact port of quat.euler_to_quat."""
    cdef double q[4]
    _euler_to_quat_c(rx, ry, rz, q)
    return (q[0], q[1], q[2], q[3])


# ---- quaternion lerp (JMAQuatLerp: f32 dot, sign-flip, f64 lerp -> f32) ------------------------
cdef void _quat_lerp_c(double* a, double* b, double t, double* out) nogil:
    """out[0..3] = lerp(a,b,t). a/b are (w,x,y,z). Bit-exact core of quat.quat_lerp."""
    cdef double aw = a[0], ax = a[1], ay = a[2], az = a[3]
    cdef double bw = b[0], bx = b[1], by = b[2], bz = b[3]
    cdef double dot = fmadds(aw, bw, fmadds(az, bz, fmadds(ay, by, fmuls(ax, bx))))
    if dot < 0.0:
        bw = -bw; bx = -bx; by = -by; bz = -bz
    cdef double om = 1.0 - t
    out[0] = f32(om * aw + t * bw)
    out[1] = f32(om * ax + t * bx)
    out[2] = f32(om * ay + t * by)
    out[3] = f32(om * az + t * bz)

def quat_lerp(a, b, t):
    cdef double ca[4]
    cdef double cb[4]
    cdef double out[4]
    ca[0] = a[0]; ca[1] = a[1]; ca[2] = a[2]; ca[3] = a[3]
    cb[0] = b[0]; cb[1] = b[1]; cb[2] = b[2]; cb[3] = b[3]
    _quat_lerp_c(ca, cb, t, out)
    return (out[0], out[1], out[2], out[3])


# ---- PSMTXQuat (retail paired-single asm), fres scale mode ------------------------------------
cdef void _psmtx_quat_c(double* q, double* m) nogil:
    """m[0..11] = 3x4 rotation matrix (row-major, trans cols = m[3],m[7],m[11] set to 0) from
    q=(w,x,y,z) via the retail PSMTXQuat asm, fres scale. Line-for-line core of quat.psmtx_quat."""
    cdef double w = q[0], x = q[1], y = q[2], z = q[3]
    cdef double t0a = x, t0b = y, t1a = z, t1b = w
    cdef double t2a = fmuls(t0a, t0a), t2b = fmuls(t0b, t0b)
    cdef double t5a = t0b, t5b = t0a
    cdef double t4a = fmadds(t1a, t1a, t2a), t4b = fmadds(t1b, t1b, t2b)
    cdef double t3a = fmuls(t1a, t1a)
    cdef double denom = fadds(t4a, t4b)
    cdef double t7a = fmuls(t5a, t1b), t7b = fmuls(t5b, t1b)
    cdef double s = _recip2(denom)
    t4b = fadds(t3a, t2b)
    cdef double t6a = fmuls(t1a, t1b), t6b = fmuls(t1b, t1b)
    t2a = fadds(t2a, t2b)
    cdef double t8a = fmadds(t0a, t5a, t6a), t8b = fmadds(t0b, t5b, t6b)
    t6a = fmsubs(t0a, t5a, t6a); t6b = fmsubs(t0b, t5b, t6b)
    t2a = fnmsubs(t2a, s, 1.0)
    t4a = fnmsubs(t4a, s, 1.0); t4b = fnmsubs(t4b, s, 1.0)
    t8a = fmuls(t8a, s); t8b = fmuls(t8b, s)
    t6a = fmuls(t6a, s); t6b = fmuls(t6b, s)
    cdef double m22 = t2a
    t5a = fmadds(t0a, t1a, t7a); t5b = fmadds(t0b, t1a, t7b)
    cdef double m10 = t8a, m11 = t4a
    t7a = fnmsubs(t7a, 2.0, t5a); t7b = fnmsubs(t7b, 2.0, t5b)
    cdef double m00 = t4b, m01 = t6a
    t5a = fmuls(t5a, s); t5b = fmuls(t5b, s)
    t7a = fmuls(t7a, s); t7b = fmuls(t7b, s)
    cdef double m02 = t5a
    cdef double m12 = t7b, m20 = t7a, m21 = t5b
    m[0] = m00; m[1] = m01; m[2] = m02; m[3] = 0.0
    m[4] = m10; m[5] = m11; m[6] = m12; m[7] = 0.0
    m[8] = m20; m[9] = m21; m[10] = m22; m[11] = 0.0


def psmtx_quat(q):
    """3x4 rotation matrix (trans=0) from q=(w,x,y,z) via the retail PSMTXQuat asm, fres scale."""
    cdef double cq[4]
    cdef double m[12]
    cq[0] = q[0]; cq[1] = q[1]; cq[2] = q[2]; cq[3] = q[3]
    _psmtx_quat_c(cq, m)
    return [[m[0], m[1], m[2], m[3]], [m[4], m[5], m[6], m[7]], [m[8], m[9], m[10], m[11]]]


# ---- fused per-joint blend: euler->quat x2 -> lerp -> morf -> psmtx_quat -> scale/trans ---------
def blend_joint(i0, i1, double ratio, double rate, bint apply_morf,
                old_quat, old_trans, old_scale):
    """One foot-chain joint's local 3x4 matrix + its posed (quat, trans, scale) for the old-pose store.
    Fused bit-exact port of foot_fk._blend_joint + _pose_frame's scale-column multiply. i0/i1 are the
    two calc_transform dicts (rotation[3] s16 ints, translate[3]/scale[3] f32). `apply_morf` gates the
    oldframe-morf toward (old_quat, old_trans, old_scale). Returns (mtx3x4, q3, trans, scale)."""
    cdef long long r0x = i0['rotation'][0], r0y = i0['rotation'][1], r0z = i0['rotation'][2]
    cdef long long r1x = i1['rotation'][0], r1y = i1['rotation'][1], r1z = i1['rotation'][2]
    cdef double i0t0 = i0['translate'][0], i0t1 = i0['translate'][1], i0t2 = i0['translate'][2]
    cdef double i1t0 = i1['translate'][0], i1t1 = i1['translate'][1], i1t2 = i1['translate'][2]
    cdef double i0s0 = i0['scale'][0], i0s1 = i0['scale'][1], i0s2 = i0['scale'][2]
    cdef double i1s0 = i1['scale'][0], i1s1 = i1['scale'][1], i1s2 = i1['scale'][2]

    cdef double q0[4]
    cdef double q1[4]
    cdef double q3[4]
    _euler_to_quat_c(r0x, r0y, r0z, q0)
    _euler_to_quat_c(r1x, r1y, r1z, q1)
    _quat_lerp_c(q0, q1, ratio, q3)

    cdef double r30 = fsubs(1.0, ratio)
    # translate/scale blend is NON-fused (m_Do_ext.cpp:1183): each product separately f32-rounded.
    cdef double tr0 = fadds(fmuls(i0t0, r30), fmuls(i1t0, ratio))
    cdef double tr1 = fadds(fmuls(i0t1, r30), fmuls(i1t1, ratio))
    cdef double tr2 = fadds(fmuls(i0t2, r30), fmuls(i1t2, ratio))
    cdef double sc0 = fadds(fmuls(i0s0, r30), fmuls(i1s0, ratio))
    cdef double sc1 = fadds(fmuls(i0s1, r30), fmuls(i1s1, ratio))
    cdef double sc2 = fadds(fmuls(i0s2, r30), fmuls(i1s2, ratio))

    cdef double oq[4]
    cdef double f31
    if apply_morf:
        f31 = fsubs(1.0, rate)
        oq[0] = old_quat[0]; oq[1] = old_quat[1]; oq[2] = old_quat[2]; oq[3] = old_quat[3]
        _quat_lerp_c(oq, q3, f31, q3)
        tr0 = fadds(fmuls(tr0, f31), fmuls(<double>old_trans[0], rate))
        tr1 = fadds(fmuls(tr1, f31), fmuls(<double>old_trans[1], rate))
        tr2 = fadds(fmuls(tr2, f31), fmuls(<double>old_trans[2], rate))
        sc0 = fadds(fmuls(sc0, f31), fmuls(<double>old_scale[0], rate))
        sc1 = fadds(fmuls(sc1, f31), fmuls(<double>old_scale[1], rate))
        sc2 = fadds(fmuls(sc2, f31), fmuls(<double>old_scale[2], rate))

    cdef double m[12]
    _psmtx_quat_c(q3, m)
    # M = R * diag(scale): scale column j by scale[j]; trans column = f32(trans).
    m[0] = fmuls(m[0], sc0); m[1] = fmuls(m[1], sc1); m[2] = fmuls(m[2], sc2); m[3] = f32(tr0)
    m[4] = fmuls(m[4], sc0); m[5] = fmuls(m[5], sc1); m[6] = fmuls(m[6], sc2); m[7] = f32(tr1)
    m[8] = fmuls(m[8], sc0); m[9] = fmuls(m[9], sc1); m[10] = fmuls(m[10], sc2); m[11] = f32(tr2)
    mtx = [[m[0], m[1], m[2], m[3]], [m[4], m[5], m[6], m[7]], [m[8], m[9], m[10], m[11]]]
    return mtx, (q3[0], q3[1], q3[2], q3[3]), (tr0, tr1, tr2), (sc0, sc1, sc2)


# ---- 3x4 matrix concat / mult-vec (PSMTXConcat / PSMTXMultVec) --------------------------------
cdef void _concat_c(double* a, double* b, double* out) nogil:
    """out = a*b (3x4 affine, row-major 12 doubles), fused accumulation. out must not alias a or b."""
    cdef int i, j, r
    for i in range(3):
        r = i * 4
        for j in range(3):
            out[r + j] = fmadds(a[r + 2], b[8 + j], fmadds(a[r + 1], b[4 + j], fmuls(a[r + 0], b[0 + j])))
        out[r + 3] = fadds(
            fmadds(a[r + 2], b[11], fmadds(a[r + 1], b[7], fmuls(a[r + 0], b[3]))), a[r + 3])

cdef void _read_mtx(object m, double* out):
    """Read a 3x4 Python matrix (list of 3 rows of 4) into a row-major double[12]."""
    cdef object row
    cdef int i
    for i in range(3):
        row = m[i]
        out[i*4+0] = row[0]; out[i*4+1] = row[1]; out[i*4+2] = row[2]; out[i*4+3] = row[3]

cdef _mtx_list(double* m):
    return [[m[0], m[1], m[2], m[3]], [m[4], m[5], m[6], m[7]], [m[8], m[9], m[10], m[11]]]

def mtx_concat(a, b):
    """ab = a*b (3x4 affine), fused accumulation. Bit-exact port of fk.mtx_concat."""
    cdef double ca[12]
    cdef double cb[12]
    cdef double out[12]
    _read_mtx(a, ca); _read_mtx(b, cb)
    _concat_c(ca, cb, out)
    return _mtx_list(out)

def chain_concat(base, m37b4, locals_list):
    """World-space foot-chain accumulation in one call: m37b4 * (base * L0 * L1 * ... * Ln).
    `locals_list` = the chain's local 3x4 matrices in root->foot order. Bit-exact fold of the
    per-joint fk.mtx_concat sequence in foot_fk._chain_mtx (base copy -> chain -> m37b4)."""
    cdef double bufA[12]
    cdef double bufB[12]
    cdef double lb[12]
    cdef double* cur = bufA
    cdef double* nxt = bufB
    cdef double* swp
    cdef Py_ssize_t n = len(locals_list), k
    _read_mtx(base, cur)
    for k in range(n):
        _read_mtx(locals_list[k], lb)
        _concat_c(cur, lb, nxt)
        swp = cur; cur = nxt; nxt = swp
    _read_mtx(m37b4, nxt)          # reuse nxt buffer to hold m37b4
    cdef double out[12]
    _concat_c(nxt, cur, out)
    return _mtx_list(out)


def mtx_mult_vec(m, v):
    """dst = (m0*sx + m2*sz) + (m1*sy + m3), per row (ps_sum0 grouping). Bit-exact port."""
    cdef double sx = v[0], sy = v[1], sz = v[2]
    cdef double mi[4]
    cdef object row
    cdef double pa, pb
    cdef double o0, o1, o2
    cdef int i
    cdef double out[3]
    for i in range(3):
        row = m[i]
        mi[0] = row[0]; mi[1] = row[1]; mi[2] = row[2]; mi[3] = row[3]
        pa = fmadds(mi[2], sz, fmuls(mi[0], sx))
        pb = fadds(fmuls(mi[1], sy), mi[3])
        out[i] = fadds(pa, pb)
    return (out[0], out[1], out[2])


# ---- Hermite interpolation (s16 asm path + f32 path) ------------------------------------------
cdef double _hermite_s16_c(double t, double time0, double value0, double tan0,
                           double time1, double value1, double tan1) nogil:
    """s16 rotation Hermite (J3DAnimation.cpp:342-363 asm). Bit-exact core of j3d_eval.hermite_s16."""
    cdef double f0 = time0
    cdef double f3 = time1
    cdef double f2 = value0
    cdef double f4 = fsubs(f3, f0)
    f3 = value1
    cdef double f6 = fsubs(t, f0)
    cdef double fout = tan1
    cdef double f5 = fsubs(f3, f2)
    f6 = fdivs(f6, f4)
    f0 = tan0
    fout = fmadds(fout, f4, f2)
    cdef double f7 = fmuls(f6, f6)
    f5 = fnmsubs(f4, f0, f5)
    fout = fsubs(fout, f3)
    fout = fsubs(fout, f5)
    f3 = fmuls(f7, fout)
    fout = fmadds(f4, f0, f3)
    fout = fmadds(fout, f6, f2)
    fout = fmadds(f5, f7, fout)
    fout = fsubs(fout, f3)
    return fout

cdef double _hermite_f32_c(double frame, double time0, double value0, double tan0,
                           double time1, double value1, double tan1) nogil:
    """f32 scale/translate Hermite (JMAHermiteInterpolation). Bit-exact core of j3d_eval.hermite_f32."""
    cdef double length = fsubs(time1, time0)
    cdef double f9 = fsubs(frame, time0)
    cdef double f1 = fdivs(1.0, length)
    cdef double f2 = fmuls(fmuls(f9, f9), f1)
    cdef double f10 = fmuls(f2, f1)
    cdef double f11 = fmuls(f9, f10)
    cdef double f12 = fmuls(f11, f1)
    cdef double a = fmadds(value0, fadds(1.0, fmsubs(2.0, f12, fmuls(3.0, f10))), 0.0)
    cdef double b = fmuls(value1, fmadds(-2.0, f12, fmuls(3.0, f10)))
    cdef double c = fmuls(tan0, fadds(f9, fnmsubs(2.0, f2, f11)))
    cdef double d = fmuls(tan1, fsubs(f11, f2))
    return fadds(fadds(fadds(a, b), c), d)

def hermite_s16(t, time0, value0, tan0, time1, value1, tan1):
    return _hermite_s16_c(t, time0, value0, tan0, time1, value1, tan1)

def hermite_f32(frame, time0, value0, tan0, time1, value1, tan1):
    return _hermite_f32_c(frame, time0, value0, tan0, time1, value1, tan1)


# ==== full C-resident pose engine ==============================================================
# One call per frame does calc_transform + the 12-joint blend/morf/PSMTXQuat pose + both foot chain
# FKs + the toe/heel PSMTXMultVec, with ALL state (keyframe data, skeleton chains, old pose, morf
# counter) resident in C -- no per-frame Python object churn. Replaces foot_fk._pose_frame/_chain_mtx/
# _toe/_blend_joint + the MorfState on the world-space FK path. Bit-exact port; see fp-faithfulness.md.

# CHAIN_JOINTS (foot_fk): union of both foot chains in calc order; slot s poses joint _CJ[s].
cdef int _CJ[12]
_CJ[0]=0; _CJ[1]=1; _CJ[2]=29; _CJ[3]=30; _CJ[4]=31; _CJ[5]=32
_CJ[6]=33; _CJ[7]=34; _CJ[8]=36; _CJ[9]=37; _CJ[10]=38; _CJ[11]=39

# l_toe / l_heel in Lfoot-joint local space (fk.L_TOE / L_HEEL, d_a_player_main_data.inc:18-19).
cdef double _TOE_X = 6.0, _TOE_Y = 3.25, _HEEL_X = -6.0, _HEEL_Y = 3.25

cdef inline long long _as_s32c(long long x) nogil:
    # (s32) cast: reinterpret the low 32 bits as signed (two's complement), then widen.
    cdef unsigned int u = <unsigned int>x
    return <long long><int>u

cdef double _keyframe_interp_c(double frame, int cnt, int tt, double* data, int base, int is_s16) nogil:
    """Endpoint clamp + bisect + Hermite (J3DGetKeyFrameInterpolation[S]). Bit-exact core of
    j3d_eval._keyframe_interp; `data` holds the flat track (rot values are stored as exact doubles)."""
    cdef int stride = 3 if tt == 0 else 4
    cdef double d0 = data[base]
    if frame < d0:
        return data[base + 1]
    cdef int last = base + stride * (cnt - 1)
    if data[last] <= frame:
        return data[last + 1]
    cdef int p = base, num = cnt, mid
    while num > 1:
        mid = num // 2
        if frame >= data[p + stride * mid]:
            p += stride * mid
            num -= mid
        else:
            num = mid
    if stride == 3:
        if is_s16:
            return _hermite_s16_c(frame, data[p], data[p+1], data[p+2], data[p+3], data[p+4], data[p+5])
        return _hermite_f32_c(frame, data[p], data[p+1], data[p+2], data[p+3], data[p+4], data[p+5])
    if is_s16:
        return _hermite_s16_c(frame, data[p], data[p+1], data[p+3], data[p+4], data[p+5], data[p+6])
    return _hermite_f32_c(frame, data[p], data[p+1], data[p+3], data[p+4], data[p+5], data[p+6])

cdef inline void _mv_c(double* m, double vx, double vy, double vz, double* out) nogil:
    """PSMTXMultVec: out[0..2] = m * (vx,vy,vz) with the ps_sum0 grouping."""
    cdef int i, r
    cdef double pa, pb
    for i in range(3):
        r = i * 4
        pa = fmadds(m[r + 2], vz, fmuls(m[r + 0], vx))
        pb = fadds(fmuls(m[r + 1], vy), m[r + 3])
        out[i] = fadds(pa, pb)


cdef class PoseEngine:
    """C-resident foot-FK pose + toe engine (world-space path). Register the anims once, set the
    two foot chains, then call pose_toe() per frame. Owns the old-pose + morf state internally."""
    cdef int _meta[16][12][3][3][3]     # [anim][slot][track s0/r1/t2][axis][cnt, off, ttype]
    cdef double* _sdata[16]
    cdef double* _rdata[16]
    cdef double* _tdata[16]
    cdef int _dec[16]
    cdef int _chain34[12]
    cdef int _n34
    cdef int _chain39[12]
    cdef int _n39
    cdef double _oldq[12][4]
    cdef double _oldt[12][3]
    cdef double _olds[12][3]
    cdef bint _has_old[12]
    cdef double _m_counter, _m_f8, _m_rate, _m_f10, _m_f14

    def __cinit__(self):
        cdef int i
        for i in range(16):
            self._sdata[i] = NULL; self._rdata[i] = NULL; self._tdata[i] = NULL
        for i in range(12):
            self._has_old[i] = False
        self._m_counter = self._m_f8 = self._m_rate = self._m_f10 = self._m_f14 = 0.0

    def __dealloc__(self):
        cdef int i
        for i in range(16):
            if self._sdata[i] != NULL: free(self._sdata[i])
            if self._rdata[i] != NULL: free(self._rdata[i])
            if self._tdata[i] != NULL: free(self._tdata[i])

    def add_anim(self, int idx, anm):
        """Register a parsed BCK (j3d_eval anm dict) at index `idx`. Copies the keyframe data into C
        arrays (rotation ints stored as exact doubles) + the per-chain-joint track metadata."""
        cdef list sd = anm['scale_data'], rd = anm['rot_data'], td = anm['trans_data']
        cdef int ns = len(sd), nr = len(rd), nt = len(td), i, slot, track, axis, jnt
        self._sdata[idx] = <double*>malloc(ns * sizeof(double))
        self._rdata[idx] = <double*>malloc(nr * sizeof(double))
        self._tdata[idx] = <double*>malloc(nt * sizeof(double))
        for i in range(ns): self._sdata[idx][i] = sd[i]
        for i in range(nr): self._rdata[idx][i] = <double>(<long long>rd[i])
        for i in range(nt): self._tdata[idx][i] = td[i]
        self._dec[idx] = anm['dec_shift']
        cdef list joints = anm['joints']
        cdef list keys = ['s', 'r', 't']
        for slot in range(12):
            jnt = _CJ[slot]
            j = joints[jnt]
            for track in range(3):
                trk = j[keys[track]]
                for axis in range(3):
                    m = trk[axis]
                    self._meta[idx][slot][track][axis][0] = m[0]
                    self._meta[idx][slot][track][axis][1] = m[1]
                    self._meta[idx][slot][track][axis][2] = m[2]

    def set_chains(self, chain34, chain39):
        """The two foot FK chains as JOINT indices (root->foot); stored internally as slot indices."""
        cdef int k, s
        self._n34 = len(chain34)
        self._n39 = len(chain39)
        for k in range(self._n34):
            for s in range(12):
                if _CJ[s] == chain34[k]:
                    self._chain34[k] = s; break
        for k in range(self._n39):
            for s in range(12):
                if _CJ[s] == chain39[k]:
                    self._chain39[k] = s; break

    def reset_old(self):
        cdef int i
        for i in range(12):
            self._has_old[i] = False

    cdef void _init_morf(self, double i_morf) nogil:
        i_morf = f32(i_morf)
        if i_morf > 0.0:
            self._m_counter = i_morf
            self._m_f8 = fdivs(1.0, i_morf)
            self._m_rate = 1.0
            self._m_f10 = 1.0
            self._m_f14 = 1.0
            self._morf_dec()
        else:
            self._m_counter = self._m_f8 = self._m_rate = self._m_f10 = self._m_f14 = 0.0

    cdef void _morf_dec(self) nogil:
        if not (self._m_counter > 0.0):
            return
        self._m_counter = fsubs(self._m_counter, 1.0)
        if self._m_counter <= 0.0:
            self._m_counter = 0.0; self._m_f8 = 0.0; self._m_rate = 0.0
        self._m_f14 = self._m_f10
        self._m_f10 = fmuls(self._m_counter, self._m_f8)
        if self._m_f14 > 0.0:
            self._m_rate = fsubs(1.0, fdivs(fsubs(self._m_f14, self._m_f10), self._m_f14))
        else:
            self._m_rate = 0.0

    cdef void _calc_transform_c(self, int anim, int slot, double frame,
                                double* scale, long long* rot, double* trans) nogil:
        cdef int axis, cnt, off, tt, dec = self._dec[anim]
        cdef double v
        cdef double* sd = self._sdata[anim]
        cdef double* rd = self._rdata[anim]
        cdef double* td = self._tdata[anim]
        for axis in range(3):
            cnt = self._meta[anim][slot][0][axis][0]
            off = self._meta[anim][slot][0][axis][1]
            tt = self._meta[anim][slot][0][axis][2]
            if cnt == 0:
                scale[axis] = 1.0
            elif cnt == 1:
                scale[axis] = f32(sd[off])
            else:
                scale[axis] = _keyframe_interp_c(frame, cnt, tt, sd, off, 0)
            cnt = self._meta[anim][slot][1][axis][0]
            off = self._meta[anim][slot][1][axis][1]
            tt = self._meta[anim][slot][1][axis][2]
            if cnt == 0:
                rot[axis] = 0
            elif cnt == 1:
                rot[axis] = _as_s32c((<long long>rd[off]) << dec)
            else:
                v = _keyframe_interp_c(frame, cnt, tt, rd, off, 1)
                rot[axis] = _as_s32c((<long long>v) << dec)
            cnt = self._meta[anim][slot][2][axis][0]
            off = self._meta[anim][slot][2][axis][1]
            tt = self._meta[anim][slot][2][axis][2]
            if cnt == 0:
                trans[axis] = 0.0
            elif cnt == 1:
                trans[axis] = f32(td[off])
            else:
                trans[axis] = _keyframe_interp_c(frame, cnt, tt, td, off, 0)

    cdef void _chain_fk(self, double* base, double* inv, int* chain, int n,
                        double* local, double* out) nogil:
        """out = inv * (base * local[chain[0]] * ... * local[chain[n-1]]). `local` is 12 slots x 12."""
        cdef double bufA[12]
        cdef double bufB[12]
        cdef double* cur = bufA
        cdef double* nxt = bufB
        cdef double* swp
        cdef int k
        memcpy(cur, base, 12 * sizeof(double))
        for k in range(n):
            _concat_c(cur, local + chain[k] * 12, nxt)
            swp = cur; cur = nxt; nxt = swp
        _concat_c(inv, cur, out)

    def pose_toe(self, int m0, int m1, double f0, double f1, double ratio, double i_morf,
                 base, m37b4):
        """Pose all 12 chain joints (blend m0@f0 with m1@f1, oldframe-morf, PSMTXQuat, scale/trans),
        FK both feet from worldBase, remove the base with m37b4, and return the toe+heel dict exactly
        like foot_fk.step_feet: {'toe':[R,L],'heel':[R,L]} (index 0 = right jnt39, 1 = left jnt34)."""
        cdef double rate
        if i_morf >= 0.0:
            self._init_morf(i_morf)
        rate = self._m_rate

        cdef double local[144]                     # 12 slots x 12 doubles
        cdef double q0[4]
        cdef double q1[4]
        cdef double q3[4]
        cdef double mtx[12]
        cdef double s0[3]
        cdef double t0[3]
        cdef double s1[3]
        cdef double t1[3]
        cdef long long r0[3]
        cdef long long r1[3]
        cdef double tr[3]
        cdef double scl[3]
        cdef int slot, k, base_off
        cdef bint apply_morf
        cdef double r30, f31
        cdef bint morf_on = rate > 0.0

        for slot in range(12):
            self._calc_transform_c(m0, slot, f0, s0, r0, t0)
            self._calc_transform_c(m1, slot, f1, s1, r1, t1)
            _euler_to_quat_c(r0[0], r0[1], r0[2], q0)
            _euler_to_quat_c(r1[0], r1[1], r1[2], q1)
            _quat_lerp_c(q0, q1, ratio, q3)
            r30 = fsubs(1.0, ratio)
            for k in range(3):
                tr[k] = fadds(fmuls(t0[k], r30), fmuls(t1[k], ratio))
                scl[k] = fadds(fmuls(s0[k], r30), fmuls(s1[k], ratio))
            apply_morf = morf_on and self._has_old[slot]   # all chain joints are < MORF_END (0x2A)
            if apply_morf:
                f31 = fsubs(1.0, rate)
                _quat_lerp_c(self._oldq[slot], q3, f31, q3)
                for k in range(3):
                    tr[k] = fadds(fmuls(tr[k], f31), fmuls(self._oldt[slot][k], rate))
                    scl[k] = fadds(fmuls(scl[k], f31), fmuls(self._olds[slot][k], rate))
            _psmtx_quat_c(q3, mtx)
            base_off = slot * 12
            local[base_off + 0] = fmuls(mtx[0], scl[0]); local[base_off + 1] = fmuls(mtx[1], scl[1])
            local[base_off + 2] = fmuls(mtx[2], scl[2]); local[base_off + 3] = f32(tr[0])
            local[base_off + 4] = fmuls(mtx[4], scl[0]); local[base_off + 5] = fmuls(mtx[5], scl[1])
            local[base_off + 6] = fmuls(mtx[6], scl[2]); local[base_off + 7] = f32(tr[1])
            local[base_off + 8] = fmuls(mtx[8], scl[0]); local[base_off + 9] = fmuls(mtx[9], scl[1])
            local[base_off + 10] = fmuls(mtx[10], scl[2]); local[base_off + 11] = f32(tr[2])
            for k in range(4):
                self._oldq[slot][k] = q3[k]
            for k in range(3):
                self._oldt[slot][k] = tr[k]
                self._olds[slot][k] = scl[k]
            self._has_old[slot] = True

        self._morf_dec()

        cdef double base12[12]
        cdef double inv12[12]
        _read_mtx(base, base12)
        _read_mtx(m37b4, inv12)
        cdef double cur39[12]
        cdef double cur34[12]
        self._chain_fk(base12, inv12, self._chain39, self._n39, local, cur39)
        self._chain_fk(base12, inv12, self._chain34, self._n34, local, cur34)

        cdef double rt[3]
        cdef double lt[3]
        cdef double rh[3]
        cdef double lh[3]
        _mv_c(cur39, _TOE_X, _TOE_Y, 0.0, rt)
        _mv_c(cur34, _TOE_X, _TOE_Y, 0.0, lt)
        _mv_c(cur39, _HEEL_X, _HEEL_Y, 0.0, rh)
        _mv_c(cur34, _HEEL_X, _HEEL_Y, 0.0, lh)
        return {'toe': [(rt[0], rt[1], rt[2]), (lt[0], lt[1], lt[2])],
                'heel': [(rh[0], rh[1], rh[2]), (lh[0], lh[1], lh[2])]}
