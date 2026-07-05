"""build_land_render.py - render data for a full land input sequence: run the LAND SIM, pose the
FULL 42-joint skeleton each frame (piggy-backing on the sim's own anim-blend state), place it in
world space at the sim's per-frame position + facing, and reconstruct the in-game (free) camera.

Emits JSON for the self-contained HTML viewer (viz/land_render.html):
  per frame: world joint positions [42][xyz], the two validated toe points, Link's pos/facing/travel,
  the proc state, mNormalSpeed, and the camera eye+target.

HOW THE FULL-BODY POSE IS OBTAINED (and its honesty caveat)
-----------------------------------------------------------
The sim (tww_sim.land.land) already computes, every frame, the exact under-body anim-blend state
(move0/move1 anims, the two frame-controller frames, the blend ratio, the oldframe-morf) and feeds
it to tww_sim.core.anim.foot_fk.FootFK.step_feet -- but only for the FOOT chain, because that's all
posMoveFromFootPos needs. We wrap that call and, with the *same* arguments and a parallel MorfState,
pose ALL 42 joints (identity-space FK). So the skeleton's motion is driven by the sim's real,
bit-exact anim state.

CAVEAT: only the foot toe is console-validated. The under-body movement anim (walk/dash/rollf/atn...)
does drive the whole lower/mid body, but the upper body has its own layered anims in-game (sword arm,
look-at, etc.) that this does NOT model -- and the FK here is the identity-space visual path, not the
bit-exact world path. This is a faithful visualization, not an oracle. The camera is a RECONSTRUCTED
free/follow cam (fixed world yaw with a lagged position), not the bit-exact dCamera_c spring.

Requires the gitignored _generated/anim keyframe data (dev-supplied).
"""
import os, sys, json, math

# >>> repo bootstrap
_here = os.path.dirname(os.path.abspath(__file__))
_rb = _here
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
# <<< repo bootstrap

from tww_sim.core import fp
from tww_sim.land import land as L
from tww_sim.core.anim import fk
from tww_sim.core.anim.foot_fk import FootFK

TAU = math.pi * 2.0

# --- input sequences (match tests/dolphin/run_land_tests.py) ---------------------------------------
A = 0x100  # PAD_BUTTON_A (roll)
def hold(sx, sy, n, buttons=0, triggerL=0):
    return [dict(sx=sx, sy=sy, buttons=buttons, triggerL=triggerL) for _ in range(n)]
L_DOWN = hold(128, 0, 1, buttons=0x40, triggerL=255)   # L-target + full down, 1 frame

def seq_roll_ebs():
    return (hold(128, 255, 15)                       # run up to speed
            + hold(128, 255, 1, A)                   # A: forward roll
            + hold(128, 0, 17, 0x40, 255)            # L held + full down THROUGH the roll -> exit to ATN@26
            + hold(128, 110, 14))                    # release L into ESS-down: EBS slide, ~-23 preserved

def seq_face_left():
    return (hold(128, 255, 10)                       # run up to speed
            + L_DOWN                                 # L-target + down: enter targeting slide
            + hold(128, 110, 1)                      # release L: EBS
            + hold(110, 128, 60))                    # hold ESS-left: facing DECOUPLES to ~90, slide preserved

# name -> (seqfn, title). Add any seq_* from run_land_tests here to expose it in the viewer.
CLIPS = {
    'roll_ebs':  (seq_roll_ebs,  'Frame-perfect EBS out of a roll'),
    'face_left': (seq_face_left, 'Facing decouples ~90° during an EBS slide'),
}


class FullBodyFK(FootFK):
    """FootFK that poses every joint (identity space), fed the sim's real per-frame blend state."""
    def __init__(self, anms, sk):
        super().__init__(anms, sk, world=False)
        self.order = [j['index'] for j in sorted(sk['joints'], key=lambda j: j['index'])]

    def pose_all(self, move0, move1, f0, f1, ratio, i_morf=-1.0):
        if i_morf >= 0.0:
            self.morf.init_morf(i_morf)
        rate = self.morf.rate
        local = {}
        for jnt in self.order:
            q3, trans, scale = self._blend_joint(move0, move1, f0, f1, ratio, jnt, rate)
            m = self.quatfn(q3)
            for i in range(3):
                m[i][0] = fp.fmuls(m[i][0], scale[0])
                m[i][1] = fp.fmuls(m[i][1], scale[1])
                m[i][2] = fp.fmuls(m[i][2], scale[2])
            m[0][3] = fp.f32(trans[0]); m[1][3] = fp.f32(trans[1]); m[2][3] = fp.f32(trans[2])
            local[jnt] = m
        world = {}
        for jnt in self.order:
            par = self.parent[jnt]
            world[jnt] = local[jnt] if par == -1 else fk.mtx_concat(world[par], local[jnt])
        self.morf.dec()
        pos = [[world[j][0][3], world[j][1][3], world[j][2][3]] for j in self.order]
        ltoe = list(fk.mtx_mult_vec(world[34], fk.L_TOE))
        rtoe = list(fk.mtx_mult_vec(world[39], fk.L_TOE))
        return pos, ltoe, rtoe


def place(pt, px, pz, facing):
    """Rotate a model-local point by shape_angle.y (facing) and translate to world XZ. Same heading
    convention as the sim's position integrator: local +Z maps to world (sin th, cos th)."""
    th = (int(facing) & 0xFFFF) * TAU / 65536.0
    c, s = math.cos(th), math.sin(th)
    x, y, z = pt
    return [px + x * c + z * s, y, pz - x * s + z * c]


def build_clip(seqfn):
    """Run one seq through the sim and return {center, frames} (world-placed pose + camera)."""
    anm, sk = fk.load()

    sim = L.LandState(pos_z=764.0791015625, pos_x=0.0, facing=0, travel=0, csangle=0,
                      state=L.FREE_WAIT, nspeed=0.0, idle_frame=L.DEFAULT_IDLE_FRAME)
    if sim._foot is None:
        raise SystemExit("sim foot engine unavailable")

    # parallel full-body FK, seeded identically to the sim's foot FK (idle rest pose, morf counter 0).
    fb = FullBodyFK(sim._foot.anm, sim._foot.sk)
    idle, idf = sim._foot.idle_anim, sim._foot.idle_frame
    fb.pose_all(idle, idle, idf, idf, 0.0, -1.0)   # seed
    fb.pose_all(idle, idle, idf, idf, 0.0, -1.0)   # draw0

    captured = {'pose': None}
    orig = sim._foot.ff.step_feet
    def wrap(move0, move1, f0, f1, ratio, i_morf=-1.0):
        captured['pose'] = fb.pose_all(move0, move1, f0, f1, ratio, i_morf)
        return orig(move0, move1, f0, f1, ratio, i_morf)
    sim._foot.ff.step_feet = wrap

    frames = []
    last = None
    for el in seqfn():
        sim.step(el['sx'], el['sy'], buttons=el['buttons'], triggerL=el['triggerL'])
        if captured['pose'] is not None:
            last = captured['pose']
            captured['pose'] = None
        if last is None:
            continue
        pose_local, lt, rt = last
        px, pz, fac = sim.pos_x, sim.pos_z, sim.facing
        p = [place(q, px, pz, fac) for q in pose_local]
        frames.append({
            'p': [[round(c, 3) for c in q] for q in p],
            'ltoe': [round(c, 3) for c in place(lt, px, pz, fac)],
            'rtoe': [round(c, 3) for c in place(rt, px, pz, fac)],
            'pos': [round(px, 3), round(pz, 3)],
            'facing': int(fac) & 0xFFFF, 'travel': int(sim.travel) & 0xFFFF,
            'state': int(sim.state), 'nspeed': round(float(sim.nspeed), 3),
        })

    # --- reconstruct the free camera: fixed world yaw (initial facing), lagged follow position ---
    th0 = (frames[0]['facing']) * TAU / 65536.0
    fwd = (math.sin(th0), math.cos(th0))         # Link's initial forward in world XZ
    D, HC, LOOK = 360.0, 165.0, 78.0             # follow distance, eye height, look-at height
    cam_x = frames[0]['pos'][0] - D * fwd[0]
    cam_z = frames[0]['pos'][1] - D * fwd[1]
    LAG = 0.11
    for fr in frames:
        lx, lz = fr['pos']
        ideal_x, ideal_z = lx - D * fwd[0], lz - D * fwd[1]
        cam_x += LAG * (ideal_x - cam_x)
        cam_z += LAG * (ideal_z - cam_z)
        fr['cam'] = {'eye': [round(cam_x, 2), HC, round(cam_z, 2)],
                     'tgt': [round(lx, 2), LOOK, round(lz, 2)]}

    # ground grid center = midpoint of the trajectory (world XZ)
    xs = [fr['pos'][0] for fr in frames]; zs = [fr['pos'][1] for fr in frames]
    center = [round((min(xs) + max(xs)) / 2, 1), round((min(zs) + max(zs)) / 2, 1)]

    return {'center': center, 'frames': frames}


def build_all(which=None):
    """Combine the requested clips (default: all in CLIPS) into one payload sharing names/bones."""
    _, sk = fk.load()
    names = [j['name'] for j in sorted(sk['joints'], key=lambda j: j['index'])]
    bones = [[j['parent'], j['index']] for j in sorted(sk['joints'], key=lambda j: j['index'])
             if j['parent'] != -1]
    keys = which or list(CLIPS.keys())
    clips = {}
    for k in keys:
        seqfn, title = CLIPS[k]
        c = build_clip(seqfn)
        c['title'] = title
        clips[k] = c
    return {'names': names, 'bones': bones, 'clips': clips}


if __name__ == '__main__':
    which = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_rb, '_generated', 'land_render.json')
    data = build_all(which)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(data, open(out, 'w'))
    print("clips=%s joints=%d bones=%d -> %s"
          % (list(data['clips']), len(data['names']), len(data['bones']), out))
    for k, c in data['clips'].items():
        print("  [%s] %s (%d frames)" % (k, c['title'], len(c['frames'])))
        for i, fr in enumerate(c['frames']):
            if i % 8 == 0 or i == len(c['frames']) - 1:
                print("    f%2d state=%2d nspd=%8.3f pos=(%8.2f,%8.2f) facing=%5.1f° travel=%5.1f°"
                      % (i, fr['state'], fr['nspeed'], fr['pos'][0], fr['pos'][1],
                         fr['facing'] * 360 / 65536, fr['travel'] * 360 / 65536))
