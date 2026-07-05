"""build_skeleton_render.py - proof-of-concept 3D skeleton render data builder.

Poses ALL 42 joints of Link's cl skeleton (not just the foot chain) with the same bit-faithful
FK machinery the land sim uses for the foot toe (fk.tr_matrix / mtx_concat), and dumps per-frame
model-local joint world positions + the bone (parent->child) list to JSON for a self-contained
HTML canvas viewer.

CAVEAT: only the foot toe is validated bit-exact vs console. The rest of the body uses the same
math and the same bck track data, so it is visually correct but console-UNVERIFIED. This is a
visualization, not a validated oracle -- it renders a stick skeleton, no mesh/skin.

Poses from identity (model-local space) via the euler tr_matrix path -- fine for an orbit view.
Reads the gitignored _generated anim/skeleton data (dev-supplied).
"""
import os, sys, json

# >>> repo bootstrap
_here = os.path.dirname(os.path.abspath(__file__))
_rb = _here
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
# <<< repo bootstrap

from tww_sim.core.anim import fk, j3d_eval


def pose_all_joints(anm, skeleton, frame):
    """World (model-local) matrix for every joint at `frame`, FK from identity in joint-index order.
    Returns {joint_idx: 3x4 matrix}. Joints are stored parent-before-child, so a single forward pass
    over ascending index works (every parent already computed)."""
    world = {}
    for j in skeleton['joints']:
        idx, par = j['index'], j['parent']
        tr = j3d_eval.calc_transform(anm, idx, frame)
        local = fk.tr_matrix(tr['rotation'], tr['translate'])
        world[idx] = local if par == -1 else fk.mtx_concat(world[par], local)
    return world


def joint_pos(world, idx):
    m = world[idx]
    return [m[0][3], m[1][3], m[2][3]]


def build(anim_name='walk', substep=0.5):
    anm_all, sk = fk.load()
    anm = anm_all[anim_name]
    fmax = anm.get('frame_max', 32)

    joints = sorted(sk['joints'], key=lambda j: j['index'])
    names = [j['name'] for j in joints]
    bones = [[j['parent'], j['index']] for j in joints if j['parent'] != -1]

    # foot toe endpoints (the bit-exact validated points) -- draw them too, as leaf markers.
    # jnt 34 = Lfoot, 39 = Rfoot; L_TOE is in foot-joint local space.
    frames = []
    f = 0.0
    while f < fmax:
        world = pose_all_joints(anm, sk, f)
        pts = [joint_pos(world, j['index']) for j in joints]
        ltoe = list(fk.mtx_mult_vec(world[34], fk.L_TOE))
        rtoe = list(fk.mtx_mult_vec(world[39], fk.L_TOE))
        frames.append({'f': round(f, 3), 'p': [[round(c, 3) for c in pt] for pt in pts],
                       'ltoe': [round(c, 3) for c in ltoe], 'rtoe': [round(c, 3) for c in rtoe]})
        f += substep

    return {'anim': anim_name, 'frame_max': fmax, 'names': names, 'bones': bones, 'frames': frames}


if __name__ == '__main__':
    anim = sys.argv[1] if len(sys.argv) > 1 else 'walk'
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_rb, '_generated', 'skeleton_render.json')
    data = build(anim)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as fh:
        json.dump(data, fh)
    nf = len(data['frames'])
    print("anim=%s frames=%d joints=%d bones=%d -> %s" % (anim, nf, len(data['names']), len(data['bones']), out))
