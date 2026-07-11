"""body_cyl.py - Link's body **Co** cylinder centre from the animated skeleton, a decomp-faithful
port of ``daPy_lk_c::setCollision`` (d_a_player_main.cpp:9748) for the seam-clip / Tetra-push model.

``setCollision`` places Link's Co cylinder (the one ``cM3d_Cross_CylCyl`` tests against other actors)
at the **horizontal midpoint of the root and neck joints**, read from the *world* anim matrices::

    spD0.x = 0.5 * (root_jnt_mtx[0][3] + neck_jnt_mtx[0][3])
    spD0.z = 0.5 * (root_jnt_mtx[2][3] + neck_jnt_mtx[2][3])

(the ``[0..2][3]`` translation columns of ``getAnmMtx(joint)`` = ``worldBase * localChain(joint)``).
This is **animation-driven** and can lead the feet by 10-30 u during a FRONT_ROLL lunge, so using
``current.pos`` (the feet) as the cylinder centre - as the first tetra_clip pass did - is wrong by
that much. This module runs the same world-space FK the walk foot chain uses (fk.world_base +
fk.mtx_concat + Q.psmtx_quat, all live-validated bit-exact) to joints 0 (CL_JNT_LINK_ROOT_e) and
14 (CL_JNT_NECK_JNT_e), and returns the midpoint.

**Live-validated bit-exact** (GZLJ01, Link rolling pinned at a wall so pos/facing were constant and
only the pose moved the centre): with the ``shape_z`` body lean fed in (below), ``roll_co_center``
reproduces the game's ``mCyl`` centre to **0 ULP on every settled roll frame** (validated 2026-07-10
against ``fixtures/hyrule_roll_lean.json`` -- roll frames 2..15, pos frozen). The early-frame residual
of the older clean-only port was NOT the oldframe-morf: it was the missing ``setWorldMatrix`` base
z-tilt by ``shape_angle.z`` (the MOVE turn lean ``m351C>>1``, decaying ~35%/frame through the roll).
Feed the PREVIOUS frame's ``shape_z`` (the setWorldMatrix/setMoveSlantAngle one-frame lag) via the
``shape_z`` arg and the residual vanishes. Two frames still miss and are out of scope for the push
solve (both before the push overlap converges at roll frame ~6): roll frame 0 -- the oldframe-morf
(``initOldFrameMorf(mRoll.field_0x14=2.0, 0, 0x2A)``) blends one frame toward the pre-roll pose, which
this clean-pose port does not reproduce (needs the FootFK-style morf driver seeded with the pre-roll
pose, see foot_fk.py); and roll frame 1 -- still mid-approach when captured, so its drawn pos is not
yet frozen. See knowledge/mechanics/actor-push.md and tests/test_body_cyl.py.

FRONT_ROLL cylinder: R = 30 (``SetR(50)`` only under ``checkGrabWear``), H = 81.25, centre.y =
current.pos.y (d_a_player_main.cpp:9778-9780). Reads gitignored _generated anim/skeleton data.
"""
from .. import fp
from . import j3d_eval
from . import fk
from . import quat as Q

# CL_JNT enum (assets/GZLJ01/res/Object/Link.h): root=0x0, neck=0xE. These are also the skeleton
# joint indices in _generated/anim/link_skeleton.json (link_root / neck_jnt).
CL_JNT_LINK_ROOT = 0
CL_JNT_NECK_JNT = 14

# FRONT_ROLL Co cylinder (d_a_player_main.cpp:9762/9778-9780). Duplicated in
# harness/collision/tetra_clip.py + knowledge/reference/constants.md#collision-actor-co-push.
FRONT_ROLL_R = 30.0
FRONT_ROLL_H = 81.25

_CACHE = None


def _chains():
    """(root_chain, neck_chain) joint-index FK paths, cached with the loaded skeleton."""
    global _CACHE
    if _CACHE is None:
        anm, sk = fk.load()
        parent = {j['index']: j['parent'] for j in sk['joints']}

        def path(idx):
            p = []
            while idx != -1:
                p.append(idx)
                idx = parent[idx]
            return list(reversed(p))
        _CACHE = (anm, path(CL_JNT_LINK_ROOT), path(CL_JNT_NECK_JNT))
    return _CACHE


def _local_mtx(anm, jidx, frame):
    """Single-anim local joint matrix via the quat path (mDoMtx_quat = PSMTXQuat); scale==1 on this
    chain, so it is just the rotation with the animated translate in the last column."""
    tr = j3d_eval.calc_transform(anm, jidx, frame)
    m = Q.psmtx_quat(Q.euler_to_quat(*tr['rotation']))
    m[0][3] = fp.f32(tr['translate'][0])
    m[1][3] = fp.f32(tr['translate'][1])
    m[2][3] = fp.f32(tr['translate'][2])
    return m


def _world_jnt(anm, chain, frame, base):
    """World anim matrix getAnmMtx(joint) = worldBase * localChain(joint), fused (fk.mtx_concat)."""
    cur = [row[:] for row in base]
    for j in chain:
        cur = fk.mtx_concat(cur, _local_mtx(anm, j, frame))
    return cur


def roll_co_center(pos_x, pos_z, facing, frame, shape_z=0):
    """The FRONT_ROLL body Co cylinder centre (x, z) at rollf animation ``frame``, Link standing at
    world (``pos_x``, ``pos_z``) facing ``facing`` (s16 BAM), with body lean ``shape_z``. Port of
    ``setCollision`` spD0.x/z for the FRONT_ROLL branch: the horizontal midpoint of the root & neck
    world joint matrices.

    ``shape_z`` is ``shape_angle.z`` (the MOVE turn-lean ``m351C>>1``) fed to the ``setWorldMatrix``
    base ``ZXYrotM`` z-tilt. It is the lean from the PREVIOUS frame -- ``setWorldMatrix`` (which builds
    the pose base) runs BEFORE ``setMoveSlantAngle`` updates the lean (d_a_player_main.cpp:11551 vs
    :11561), the same one-frame lag the foot draw uses. This is the ONLY body-lean term that reaches
    the root/neck xz midpoint: the ``jointBeforeCB`` root tilt (``m34F2``/``m34F4``) is 0 outside
    damage/ice-slip, and its ``body_chn`` rotation (``-mBodyAngle.z``) contributes nothing to the
    centre (verified live: base-lean-only is 0 ULP on every settled roll frame; adding the body_chn
    quat breaks it). The lean decays ~35%/frame during a roll, so on a straight-approach roll (lean 0)
    this is a no-op and the clean pose is already exact. Live-gated by ``tests/test_body_cyl.py`` +
    ``fixtures/hyrule_roll_lean.json``.

    ``pos``/``facing`` feed ``worldBase`` exactly as the game does (the FK accumulates at world
    magnitude, so the base matters); py is immaterial to x/z. Clean single-anim pose otherwise (no
    roll-entry oldframe-morf, which touches only roll frame 0; see the module docstring). Returns f32
    (cx, cz)."""
    anm, ch_root, ch_neck = _chains()
    roll = anm['rollf']
    base, _ = fk.world_base(pos_x, 0.0, pos_z, facing, shape_z)
    mr = _world_jnt(roll, ch_root, frame, base)
    mn = _world_jnt(roll, ch_neck, frame, base)
    cx = fp.fmuls(0.5, fp.fadds(mr[0][3], mn[0][3]))
    cz = fp.fmuls(0.5, fp.fadds(mr[2][3], mn[2][3]))
    return cx, cz


def available():
    """True iff the generated anim + skeleton data is present."""
    try:
        fk.load()
        return True
    except (FileNotFoundError, OSError):
        return False
