"""foot_fk.py - STATEFUL foot forward-kinematics driver with the oldframe-morf blend.

fk.foot_toe_blend poses one frame in isolation. But at a walk-proc ENTRY the game morphs the new
pose toward the PREVIOUS frame's stored pose over a couple of frames (mDoExt_MtxCalcOldFrame, the
oldframe-morf), so the transient foot toe is only bit-exact if we carry per-joint old pose + the morf
counter across frames. This driver does that: feed it the per-frame anim-blend state
(from anim_state.UnderAnimState.step) and it returns the model-local toe for both feet, applying morf.

Timeline of the morf rate the FOOT joints (34/39, before the last joint 41) see, verified vs live:
  trigger frame: initOldFrameMorf(2.4) does dec#1 -> rate 0.583 (foot uses this); the per-frame
  last-joint dec then -> 0.286. next frame: foot uses 0.286; last-joint dec -> 0. So exactly 2 foot
  draw frames are morphed. Per joint (m_Do_ext.cpp:1195): quat3 = JMAQuatLerp(oldQuat, blendedQuat,
  1-rate); trans = blendedTrans*(1-rate) + oldTrans*rate; then oldQuat/oldTrans <- the posed result.

Seed the old pose with the FREEB (rest) pose at the entry frame before the first walk step, matching
the game (which stores old every frame, standing included).
Reads gitignored _generated anim/skeleton data (dev-supplied).
"""
from .. import fp
from . import j3d_eval
from . import quat as Q
from . import fk

# union of both foot chains, in joint-index (calc) order; each processed once per frame.
CHAIN_JOINTS = [0, 1, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39]
MORF_START, MORF_END = 0, 0x2A          # initOldFrameMorf(2.4, 0, 0x2A) joint range


class MorfState:
    """mDoExt_MtxCalcOldFrame morf counter (m_Do_ext.cpp:1226,1246). rate is what joints read."""
    __slots__ = ('counter', 'f8', 'rate', 'f10', 'f14')

    def __init__(self):
        self.counter = self.f8 = self.rate = self.f10 = self.f14 = 0.0

    def init_morf(self, i_morf):
        # mOldFrameMorfCounter/i_morf are f32 in-game; f64 2.4 rounds the morf rate 1 ULP low ->
        # jnt0.z entry-morf +5 ULP. Quantize to f32. See knowledge/history/resolved-bugs.md.
        i_morf = fp.f32(i_morf)
        if i_morf > 0.0:
            self.counter = i_morf
            self.f8 = fp.fdivs(1.0, i_morf)
            self.rate = 1.0
            self.f10 = 1.0
            self.f14 = 1.0
            self.dec()
        else:
            self.counter = self.f8 = self.rate = self.f10 = self.f14 = 0.0

    def dec(self):
        if not (self.counter > 0.0):
            return
        self.counter = fp.fsubs(self.counter, 1.0)
        if self.counter <= 0.0:
            self.counter = 0.0; self.f8 = 0.0; self.rate = 0.0
        self.f14 = self.f10
        self.f10 = fp.fmuls(self.counter, self.f8)
        if self.f14 > 0.0:
            self.rate = fp.fsubs(1.0, fp.fdivs(fp.fsubs(self.f14, self.f10), self.f14))
        else:
            self.rate = 0.0


class FootFK:
    """Stateful driver. `anms` = {name: parsed bck}, `sk` = skeleton. Carries per-joint old pose."""

    def __init__(self, anms, sk, world=True):
        self.anms = anms
        self.sk = sk
        self.parent = {j['index']: j['parent'] for j in sk['joints']}
        self.morf = MorfState()
        self.old_quat = {}          # jnt -> (w,x,y,z) posed quat last frame
        self.old_trans = {}         # jnt -> (x,y,z) posed translate last frame
        self.old_scale = {}         # jnt -> (x,y,z) posed scale last frame (morf blends it too)
        # World-space FK (the game's real path): FK from worldBase (world-magnitude quantization) then
        # remove the base with m37B4. world=False = legacy identity FK. See knowledge/model/sim.md.
        self.world = world
        self.quatfn = Q.psmtx_quat if world else Q.mtx_quat   # foot chain uses PSMTXQuat (=mDoMtx_quat)
        self.base = None            # worldBase 3x4 (set each frame by set_pos)
        self.m37b4 = None           # PSMTXInverse(worldBase)

    def set_pos(self, px, pz, py=0.0, facing=0):
        """Set Link's world pose for the frame about to be posed. Only X/Z (and facing) affect the
        foot toe f31_2; py is immaterial (Y column unused). No-op when world FK is disabled."""
        if self.world:
            self.base, self.m37b4 = fk.world_base(px, py, pz, facing)

    def _blend_joint(self, move0, move1, f0, f1, ratio, jnt, rate):
        """Blended (quat, trans, scale) for one joint, then oldframe-morf toward the stored old pose.
        Scale is blended linearly like translate; almost every foot-chain joint is identity-scale (so
        this is a no-op vs the old R-only path), but ANM_SLIP scales jnt37.x by 1.2 -> it moves the
        right-foot toe, so scale must be carried into the matrix (see _pose_frame)."""
        i0 = j3d_eval.calc_transform(self.anms[move0], jnt, f0)
        i1 = j3d_eval.calc_transform(self.anms[move1], jnt, f1)
        q0 = Q.euler_to_quat(*i0['rotation'])
        q1 = Q.euler_to_quat(*i1['rotation'])
        q3 = Q.quat_lerp(q0, q1, ratio)
        r30 = fp.fsubs(1.0, ratio)
        # translate/scale blend is NON-fused (m_Do_ext.cpp:1183, like JMAEulerToQuat) -- both products
        # separately f32-rounded then added; a fused fmadds is 1 ULP off on blend frames. See sim.md.
        trans = tuple(fp.fadds(fp.fmuls(i0['translate'][k], r30), fp.fmuls(i1['translate'][k], ratio))
                      for k in range(3))
        scale = tuple(fp.fadds(fp.fmuls(i0['scale'][k], r30), fp.fmuls(i1['scale'][k], ratio))
                      for k in range(3))
        if rate > 0.0 and MORF_START <= jnt < MORF_END and jnt in self.old_quat:
            f31 = fp.fsubs(1.0, rate)
            q3 = Q.quat_lerp(self.old_quat[jnt], q3, f31)
            ot = self.old_trans[jnt]
            trans = tuple(fp.fadds(fp.fmuls(trans[k], f31), fp.fmuls(ot[k], rate)) for k in range(3))
            os_ = self.old_scale[jnt]
            scale = tuple(fp.fadds(fp.fmuls(scale[k], f31), fp.fmuls(os_[k], rate)) for k in range(3))
        self.old_quat[jnt] = q3
        self.old_trans[jnt] = trans
        self.old_scale[jnt] = scale
        return q3, trans, scale

    def _pose_frame(self, move0, move1, f0, f1, ratio, rate):
        """Pose all chain joints once, return {jnt: local 3x4 matrix}."""
        local = {}
        for jnt in CHAIN_JOINTS:
            q3, trans, scale = self._blend_joint(move0, move1, f0, f1, ratio, jnt, rate)
            m = self.quatfn(q3)                      # 3x3 rotation, trans column 0 (PSMTXQuat in world mode)
            for i in range(3):                       # M = R * diag(scale): scale column j by scale[j]
                m[i][0] = fp.fmuls(m[i][0], scale[0])
                m[i][1] = fp.fmuls(m[i][1], scale[1])
                m[i][2] = fp.fmuls(m[i][2], scale[2])
            m[0][3] = fp.f32(trans[0]); m[1][3] = fp.f32(trans[1]); m[2][3] = fp.f32(trans[2])
            local[jnt] = m
        return local

    def _toe(self, local, foot_jnt, toe):
        chain = []
        j = foot_jnt
        while j != -1:
            chain.append(j); j = self.parent[j]
        chain.reverse()
        if self.world and self.base is not None:
            # World-space FK: start at worldBase, accumulate local chain (world-magnitude quantization),
            # then anmMtx-to-model via m37B4 (posMoveFromFootPos: spB0 = m37B4 * anmMtx(FOOT) * toe).
            cur = [row[:] for row in self.base]
            for jnt in chain:
                cur = fk.mtx_concat(cur, local[jnt])
            cur = fk.mtx_concat(self.m37b4, cur)
        else:
            cur = None
            for jnt in chain:
                cur = local[jnt] if cur is None else fk.mtx_concat(cur, local[jnt])
        return fk.mtx_mult_vec(cur, toe)

    def seed(self, move0, f0):
        """Populate old pose from a single anim (e.g. FREEB rest) before the first walk step."""
        self._pose_frame(move0, move0, f0, f0, 0.0, 0.0)

    def step(self, move0, move1, f0, f1, ratio, i_morf=-1.0, toe=fk.L_TOE):
        """Advance one frame; return (Ltoe, Rtoe) model-local. i_morf>=0 triggers oldframe-morf."""
        if i_morf >= 0.0:
            self.morf.init_morf(i_morf)
        rate = self.morf.rate                        # rate the foot joints see this frame
        local = self._pose_frame(move0, move1, f0, f1, ratio, rate)
        lt = self._toe(local, 34, toe)
        rt = self._toe(local, 39, toe)
        self.morf.dec()                              # the per-frame "last joint" decrement
        return lt, rt

    def step_feet(self, move0, move1, f0, f1, ratio, i_morf=-1.0):
        """Advance one frame; return dict with model-local toe+heel (x,y,z) for both feet, keyed as
        spB0/sp98 in posMoveFromFootPos: index 0 = RIGHT foot (jnt 39), index 1 = LEFT foot (jnt 34).
        posMoveFromFootPos uses the SAME l_toe_pos/l_heel_pos for both feet (the joint mtx mirrors)."""
        if i_morf >= 0.0:
            self.morf.init_morf(i_morf)
        rate = self.morf.rate
        local = self._pose_frame(move0, move1, f0, f1, ratio, rate)
        out = {
            'toe': [self._toe(local, 39, fk.L_TOE), self._toe(local, 34, fk.L_TOE)],
            'heel': [self._toe(local, 39, fk.L_HEEL), self._toe(local, 34, fk.L_HEEL)],
        }
        self.morf.dec()
        return out
