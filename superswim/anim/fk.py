"""fk.py - forward kinematics for Link's cl skeleton, bit-faithful to the console, producing the
model-local foot toe position spB0 that drives the walk speedF foot term.

Chain of specs (all in tww/):
  - Per-joint TRS at frame f: j3d_eval.calc_transform (Hermite + calcTransform).
  - Local joint matrix: J3DMtxCalcMaya::calcTransform (J3DJoint.cpp:140) -- Link's cl.bdl is Maya
    (INF1 flags&0xF==2). For the WALK foot chain every joint has scale==1 (no animated scale),
    so the scale-branch and scaleCompensate 1/parentS are both no-ops (parentS stays 1) -> the
    local matrix is exactly J3DGetTranslateRotateMtx(info) (J3DTransform.cpp:166).
  - Concat down the tree: MTXConcat==PSMTXConcat (retail) -- fused accumulation, decoded from the
    paired-single asm (mtx.c:119): ab[i][j] = fmadds(a[i][2],b[2][j], fmadds(a[i][1],b[1][j],
    fmuls(a[i][0],b[0][j]))) for j<3; ab[i][3] adds +a[i][3].
  - Toe: PSMTXMultVec (mtxvec.c:21): dst = (m0.*.sx + m2.*.sz) + (m1.*.sy + m3), grouped as two
    fmadds partials joined by a ps_sum0 (fadds). l_toe_pos={6,3.25,0}, l_heel_pos={-6,3.25,0}
    (d_a_player_main_data.inc:18-19).

WHY FK-from-identity == the game's model-local spB0 (for the XZ that f31_2 uses):
  posMoveFromFootPos (d_a_player_main.cpp:2372) does spB0 = (m37B4 * anmMtx(FOOT)) * l_toe_pos.
  anmMtx(FOOT) = worldBase * localChain(FOOT) (FK starts at setBaseTRMtx(worldBase), :9580);
  m37B4 = inverse(worldBase) (:9581-82) with only m37B4[1][3]-=m35B8 (:8796) tweaking the Y row.
  f31_2 = absXZ(spB0) uses rows 0 and 2 only -> the Y tweak is irrelevant, and inverse*worldBase
  cancels, leaving localChain(FOOT)*toe = FK from IDENTITY (including link_root's own local TR).
  (Assumes baseScale==1 -- true for standing Link. If inverse*worldBase isn't bit-exact identity,
  the residual shows up here vs live; escalate to full worldBase+PSMTXInverse replication.)

Reads gitignored _generated anim/skeleton data (dev-supplied).
"""
import os, sys, json

from superswim import fp
from superswim import sim as S

from . import j3d_eval
from . import quat as Q

# l_toe/l_heel in Lfoot-joint local space (mirror x for the right foot? posMoveFromFootPos uses
# the SAME l_toe_pos for both feet -- the mtx handles the side). d_a_player_main_data.inc:18-19.
L_TOE = (6.0, 3.25, 0.0)
L_HEEL = (-6.0, 3.25, 0.0)

# JMACos/JMASin on s16 BAM from SEPARATE baked console tables (see sim.py _SIN_TABLE). tr_matrix/euler
# path is unused for the foot chain but kept faithful.
def jma_cos(a):
    return S._COS_TABLE[(int(a) & 0xFFFF) >> 4]

def jma_sin(a):
    return S._SIN_TABLE[(int(a) & 0xFFFF) >> 4]


def tr_matrix(rot, trans):
    """J3DGetTranslateRotateMtx(info) -> 3x4 Mtx (list of 3 rows of 4). rot=(rx,ry,rz) s16 BAM,
    trans=(tx,ty,tz) f32. Element ops fused per MWCC FMA codegen."""
    rx, ry, rz = rot
    sx, cx = jma_sin(rx), jma_cos(rx)
    sy, cy = jma_sin(ry), jma_cos(ry)
    sz, cz = jma_sin(rz), jma_cos(rz)
    m = [[0.0]*4 for _ in range(3)]
    m[2][0] = fp.f32(-sy)
    m[0][0] = fp.fmuls(cz, cy)
    m[1][0] = fp.fmuls(sz, cy)
    m[2][1] = fp.fmuls(cy, sx)
    m[2][2] = fp.fmuls(cy, cx)
    cxsz = fp.fmuls(cx, sz)
    sxcz = fp.fmuls(sx, cz)
    m[0][1] = fp.fmsubs(sxcz, sy, cxsz)      # sxcz*sy - cxsz
    m[1][2] = fp.fmsubs(cxsz, sy, sxcz)      # cxsz*sy - sxcz
    sxsz = fp.fmuls(sx, sz)
    cxcz = fp.fmuls(cx, cz)
    m[0][2] = fp.fmadds(cxcz, sy, sxsz)      # cxcz*sy + sxsz
    m[1][1] = fp.fmadds(sxsz, sy, cxcz)      # sxsz*sy + cxcz
    m[0][3] = fp.f32(trans[0])
    m[1][3] = fp.f32(trans[1])
    m[2][3] = fp.f32(trans[2])
    return m


def mtx_concat(a, b):
    """PSMTXConcat: ab = a * b (3x4 affine). Fused accumulation, order [0]->+[1]->+[2](->+trans)."""
    ab = [[0.0]*4 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            ab[i][j] = fp.fmadds(a[i][2], b[2][j], fp.fmadds(a[i][1], b[1][j], fp.fmuls(a[i][0], b[0][j])))
        ab[i][3] = fp.fadds(
            fp.fmadds(a[i][2], b[2][3], fp.fmadds(a[i][1], b[1][3], fp.fmuls(a[i][0], b[0][3]))),
            a[i][3])
    return ab


def mtx_mult_vec(m, v):
    """PSMTXMultVec: dst = (m0.col0*sx + m0.col2*sz) + (m0.col1*sy + m0.col3), per-row, with the
    ps_sum0 grouping (two fmadds partials joined by fadds)."""
    sx, sy, sz = v
    out = [0.0, 0.0, 0.0]
    for i in range(3):
        pa = fp.fmadds(m[i][2], sz, fp.fmuls(m[i][0], sx))   # m_i0*sx + m_i2*sz
        pb = fp.fadds(fp.fmuls(m[i][1], sy), m[i][3])        # m_i1*sy + m_i3
        out[i] = fp.fadds(pa, pb)
    return tuple(out)


# --- quaternion local-matrix path: the CL foot chain uses mDoExt_MtxCalcAnmBlendTblOld::calc ----
# euler->quat (both anims) -> QuatLerp blend -> mDoMtx_quat; translate = blended mTranslate (scale 1).
def local_mtx_quat_single(rot, trans):
    """Single-anim local matrix via the quat path (no blend)."""
    m = Q.mtx_quat(Q.euler_to_quat(*rot))
    m[0][3] = fp.f32(trans[0]); m[1][3] = fp.f32(trans[1]); m[2][3] = fp.f32(trans[2])
    return m

def local_mtx_quat_blend(info0, info1, ratio):
    """Two-anim local matrix: info0=dash(MOVE0), info1=walk(MOVE1), blend toward walk by ratio.
    Rotation via QuatLerp(q_dash,q_walk,ratio); translation linear a*(1-r)+b*r (fmadds)."""
    q0 = Q.euler_to_quat(*info0['rotation'])
    q1 = Q.euler_to_quat(*info1['rotation'])
    q3 = Q.quat_lerp(q0, q1, ratio)
    f30 = fp.fsubs(1.0, ratio)
    m = Q.mtx_quat(q3)
    for k in range(3):
        m[k][3] = fp.fmadds(info1['translate'][k], ratio, fp.fmuls(info0['translate'][k], f30))
    return m


def foot_toe_quat(anm, skeleton, frame, foot_jnt=34, toe=L_TOE):
    """Model-local toe via the QUAT path, single anim at `frame` (the correct path for the foot
    chain; use this, not foot_toe_local, once validated)."""
    chain = build_foot_chains(skeleton)[foot_jnt]
    cur = None
    for jidx in chain:
        tr = j3d_eval.calc_transform(anm, jidx, frame)
        local = local_mtx_quat_single(tr['rotation'], tr['translate'])
        cur = local if cur is None else mtx_concat(cur, local)
    return mtx_mult_vec(cur, toe)


def foot_toe_blend(anm_dash, anm_walk, skeleton, f_dash, f_walk, ratio, foot_jnt=34, toe=L_TOE):
    """Model-local toe of the BLENDED (dash+walk) pose -- the game's actual foot pose.
    f_dash/f_walk = the two frame-controller frames; ratio = getRatio(1) (walk weight)."""
    chain = build_foot_chains(skeleton)[foot_jnt]
    cur = None
    for jidx in chain:
        i0 = j3d_eval.calc_transform(anm_dash, jidx, f_dash)
        i1 = j3d_eval.calc_transform(anm_walk, jidx, f_walk)
        local = local_mtx_quat_blend(i0, i1, ratio)
        cur = local if cur is None else mtx_concat(cur, local)
    return mtx_mult_vec(cur, toe)


def build_foot_chains(skeleton):
    """Return {joint_idx: [ancestor..., joint_idx]} FK paths for LFOOT(34) and RFOOT(39)."""
    parent = {j['index']: j['parent'] for j in skeleton['joints']}
    def path(idx):
        p = []
        while idx != -1:
            p.append(idx)
            idx = parent[idx]
        return list(reversed(p))
    return {34: path(34), 39: path(39)}


def foot_toe_local(anm, skeleton, frame, foot_jnt=34, toe=L_TOE):
    """Model-local toe position of foot_jnt at `frame`, FK from identity through its chain."""
    chains = build_foot_chains(skeleton)
    chain = chains[foot_jnt]
    cur = None   # mCurrentMtx; starts as identity -> first joint's local mtx
    for jidx in chain:
        tr = j3d_eval.calc_transform(anm, jidx, frame)
        local = tr_matrix(tr['rotation'], tr['translate'])
        # NOTE: assumes scale==1 (Maya scale-branch/scaleCompensate no-op) for the foot chain.
        cur = local if cur is None else mtx_concat(cur, local)
    return mtx_mult_vec(cur, toe)


def load():
    anm = j3d_eval.load_anim()
    here = os.path.dirname(os.path.abspath(__file__))
    rb = here
    while rb != os.path.dirname(rb) and not os.path.exists(os.path.join(rb, 'pyproject.toml')):
        rb = os.path.dirname(rb)
    sk = json.load(open(os.path.join(rb, '_generated', 'anim', 'link_skeleton.json')))
    return anm, sk


if __name__ == '__main__':
    anm_all, sk = load()
    anm = anm_all['walk']
    print("model-local Lfoot/Rfoot toe over walk frames (FK from identity):")
    for f in (0.0, 4.0, 8.0, 8.5, 16.0, 24.0, 31.0):
        lt = foot_toe_local(anm, sk, f, 34, L_TOE)
        rt = foot_toe_local(anm, sk, f, 39, L_TOE)
        print("  f=%5.1f  Ltoe=(%.4f, %.4f, %.4f)  Rtoe=(%.4f, %.4f, %.4f)" % (f, *lt, *rt))
