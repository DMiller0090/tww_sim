"""Capture the Courtyard Tetra-push GROUND TRUTH from savestate slot 2 (mid-playback of the real
any% TAS DTM 28_Courtyard_TetraPush) -- Link + Tetra per-frame RAM, movie-driven.

Loads slot 2, locates Tetra (find_tetra), then single-steps the PLAYING movie N frames, logging both
actors + the delivered pad each frame. The push is held-stick roll/EBS (jitter-safe to single-step;
a lone button EDGE would need free-run per bug#2, but this capture is for the trajectory/speed/facing
ground truth the sim is validated against, not for delivering inputs).

This is a VALIDATION capture: the sim itself takes NO live input. Reads/writes RAM via dolphin_mem
(../../tools) only -- self-contained (mirrors harness/rollstab/capture_*.py).

    python -m harness.tetrapush.capture_push                    # 60 frames -> default fixture
    python -m harness.tetrapush.capture_push frames=120 out=<path> slot=2

Fields (JP GZLJ01):
  Link  daPy_lk_c this = [0x803AD860];  fopAc base = this - 0xD8
    proc [this+0x3100] s32 (daPyProc: 6=MOVE 7=ATN_MOVE 8=ATN_ACTOR_WAIT 9=ATN_ACTOR_MOVE 30=ROLL)
    current.pos [fopAc+0x1F8]  travel(current.angle.y) [+0x206]  facing(shape_angle.y) [+0x20E]
    speedF [+0x254]   anim frame ctrl [this+0x2F64]   mRate [this+0x2F60]
  Tetra daNpc_Zl1_c: current.pos +0x1F8, travel +0x206, facing +0x20E, speedF +0x254,
    stt field_0x84B, type field_0x84F (==5 following variant)
  Pad   g_mDoCPd_cpadInfo[0] @0x80398308: px +0x00, py +0x04, value +0x08, angle(s16) +0x0C
"""
import json
import math
import os
import struct
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

from harness.tetrapush.find_tetra import find_tetra_instance   # noqa: E402

DEFAULT_OUT = os.path.join(_rb, 'fixtures', 'courtyard_push_state2.json')

LINK_PTR_ADDR = 0x803AD860
CPAD = 0x80398308
ZL1_TYPE_OFF = 0x84F
ZL1_STT_OFF = 0x84B

# Link body Co cylinder centre (the animated setCollision root/neck midpoint = the actual Tetra-plow
# centre, NOT current.pos) + csangle (dCam_getControledAngleY). Provenance/offsets: README ## Addresses.
LINK_CYL_C = 0x4064
CAM_ROOT = 0x803AD380
CAM_OFF1 = 0x34
CAM_OFF2 = 0x2B0

PROC = {1: "SUBJ", 4: "WAIT", 5: "FREE_WAIT", 6: "MOVE", 7: "ATN_MOVE", 8: "ATN_ACTOR_WAIT",
        9: "ATN_ACTOR_MOVE", 15: "CRAWL_START", 23: "WAIT_TURN", 24: "MOVE_TURN", 25: "SLIP",
        30: "FRONT_ROLL", 31: "ROLL_CRASH", 0x22: "BACK_JUMP", 0x24: "AUTO_JUMP", 0x27: "FALL",
        0x41: "CUT_A", 0x42: "CUT_F", 0x5A: "CUT_REVERSE"}


def _rdr(D):
    h, mem1 = D.attach()

    class R:
        def f32(self, a):
            return struct.unpack('>f', D.read_bytes(h, mem1, a, 4))[0]

        def u16(self, a):
            return struct.unpack('>H', D.read_bytes(h, mem1, a, 2))[0]

        def s32(self, a):
            return struct.unpack('>i', D.read_bytes(h, mem1, a, 4))[0]

        def s8(self, a):
            return struct.unpack('>b', D.read_bytes(h, mem1, a, 1))[0]

        def u8(self, a):
            return struct.unpack('>B', D.read_bytes(h, mem1, a, 1))[0]

        def u32(self, a):
            return struct.unpack('>I', D.read_bytes(h, mem1, a, 4))[0]

        def s16(self, a):
            v = self.u16(a)
            return v - 0x10000 if v >= 0x8000 else v
    return R()


def _csangle(r):
    """dCam_getControledAngleY (csangle) via the pointer chain [[0x803AD380]+0x34]+0x2B0 (u16)."""
    p1 = r.u32(CAM_ROOT)
    p2 = r.u32(p1 + CAM_OFF1)
    return r.u16(p2 + CAM_OFF2)


def _pad(r):
    """Full interface_of_controller_pad @ CPAD: main + C stick, analog L, and the decoded a/b/l
    button-hold bits (the input timeline for the push). Raw hold bytes kept for provenance."""
    hold0 = r.u8(CPAD + 0x30)
    hold1 = r.u8(CPAD + 0x31)
    return dict(px=r.f32(CPAD + 0x00), py=r.f32(CPAD + 0x04),
                value=r.f32(CPAD + 0x08), angle=r.u16(CPAD + 0x0C),
                cpx=r.f32(CPAD + 0x10), cpy=r.f32(CPAD + 0x14),
                cvalue=r.f32(CPAD + 0x18), cangle=r.u16(CPAD + 0x1C),
                trigL=r.f32(CPAD + 0x28),
                hold=(hold0 << 8) | hold1,
                a=bool(hold0 & 0x01), l=bool(hold0 & 0x02), b=bool(hold1 & 0x80))


def _snap(r, tetra, fi):
    lp = r.u32(LINK_PTR_ADDR)
    la = lp - 0xD8
    row = dict(
        f=fi, proc=r.s32(lp + 0x3100),
        link=dict(pos=[r.f32(la + 0x1F8), r.f32(la + 0x1FC), r.f32(la + 0x200)],
                  travel=r.u16(la + 0x206), facing=r.u16(la + 0x20E),
                  speedF=r.f32(la + 0x254), nspeed=r.f32(la + 0x35BC),   # mNormalSpeed (potential speed;
                  #                    speedF LAGS it a frame at a proc transition -- needed for the f0 seed)
                  anim=r.f32(lp + 0x2F64), mrate=r.f32(lp + 0x2F60),
                  # body Co cylinder (the Tetra-plow driver): center + radius + height, and shape.z lean.
                  cyl=[r.f32(lp + LINK_CYL_C), r.f32(lp + LINK_CYL_C + 4), r.f32(lp + LINK_CYL_C + 8)],
                  cyl_r=r.f32(lp + 0x4070), cyl_h=r.f32(lp + 0x4074), shape_z=r.s16(la + 0x210)),
        csangle=_csangle(r),
        tetra=dict(pos=[r.f32(tetra + 0x1F8), r.f32(tetra + 0x1FC), r.f32(tetra + 0x200)],
                   travel=r.u16(tetra + 0x206), facing=r.u16(tetra + 0x20E),
                   speedF=r.f32(tetra + 0x254), stt=r.s8(tetra + ZL1_STT_OFF)),
        # Full pad (_pad): the DECODED input timeline (L/buttons/stick). Byte-exact raw stick for
        # position 0-ULP is the DTM bytes (run_dtm), not this post-octagon-clamp struct.
        pad=_pad(r))
    lp_, tp_ = row['link']['pos'], row['tetra']['pos']
    row['dist_LT'] = math.hypot(lp_[0] - tp_[0], lp_[2] - tp_[2])
    return row


SEED_OUT = os.path.join(_rb, 'fixtures', 'courtyard_push_seed.json')


def _zl1_look_row(r, z):
    """Tetra's hidden LOOK-AT state, in the `fixtures/courtyard_zl1look.json` row shape (the
    `core.npc_zl1_look.Zl1Look.seed_from_row` input; same field map as
    `_notes/tetrapush-zl1look_probe.py`). ``z`` = the Zl1 actor base (find_tetra)."""
    morf_p = r.u32(z + 0x330)
    return dict(
        jnt=dict(angles=[[r.s16(z + 0x290), r.s16(z + 0x292)],
                         [r.s16(z + 0x294), r.s16(z + 0x296)]],
                 trn=r.u8(z + 0x29A),
                 f2c=r.s16(z + 0x2BC), f2e=r.s16(z + 0x2BE),
                 f30=r.s16(z + 0x2C0), f32=r.s16(z + 0x2C2)),
        morf=dict(frame=r.f32(morf_p + 0x68), cur=r.f32(morf_p + 0x74),
                  prev=r.f32(morf_p + 0x78), step=r.f32(morf_p + 0x7C),
                  end=r.s16(morf_p + 0x60), rate=r.f32(morf_p + 0x64)),
        f849=r.s8(z + 0x849), f84d=r.s8(z + 0x84D), stt=r.s8(z + 0x84B),
        f7b8=r.s16(z + 0x7B8), f7ba=r.s16(z + 0x7BA), f7bc=r.s16(z + 0x7BC),
        f7c3=r.s8(z + 0x7C3), mframe=r.f32(z + 0x78C),
        f83c=r.s16(z + 0x83C), f83e=r.s16(z + 0x83E),
        eye=[r.f32(z + 0x260), r.f32(z + 0x264), r.f32(z + 0x268)],
        tattn=[r.f32(z + 0x274), r.f32(z + 0x278), r.f32(z + 0x27C)],
        pos=[r.f32(z + 0x1F8), r.f32(z + 0x1FC), r.f32(z + 0x200)],
        travel=r.u16(z + 0x206), facing=r.u16(z + 0x20E))


def capture_seed(out=SEED_OUT, slot=2):
    """Capture the COMPLETE state-2 seed (f0) in ONE deterministic read -- no single-stepping, so no
    bug#2 edge jitter. This is the from-f0 replay's seed AND the planner's initial condition: it adds
    the HIDDEN fields the cyl/dtm fixtures never logged, above all **mNormalSpeed** (la+0x35BC). At f0
    (mid-transition out of the prior cycle's untarget) speedF LAGS mNormalSpeed by a frame (speedF
    -24.574, mNormalSpeed -24.982), so seeding `nspeed = speedF` -- as the replay did -- leaves f1-f2
    off; seeding `nspeed` from mNormalSpeed makes the whole from-f0 chain bit-exact. Also records the
    attention state (lock/actor) + mDirection/m34E6 for provenance (all match the sim defaults at this
    seed: mDir DIR_NONE, no lock -- confirmed live, session 12). Session 20 adds the **Zl1 LOOK
    block** (`zl1`): Tetra's hidden look-at state -- the dNpc_JntCtrl_c angles/targets, the McaMorf
    frame ctrl + morfs, the look timers (f7B8/f7BA/f7BC), the anim number, the half-angle twists,
    and her eyePos -- the `core.npc_zl1_look.Zl1Look.seed_from_row` seed (needs `find_tetra`, so
    the seed capture now does the _execute-trap + reload dance the frame capture does)."""
    import dolphin_mem as D
    D.control_pipe_quiet("pause")
    D.control_pipe_quiet("savestate", {"action": "load", "slot": int(slot)})
    tetra = find_tetra_instance(D, reload_slot=int(slot))
    r = _rdr(D)
    lp = r.u32(LINK_PTR_ADDR)
    la = lp - 0xD8
    attn = r.u32(lp + 0x33A8)
    # m_old_fdata (header 0x31B4 -> lp+0x30DC): the per-joint OLD-POSE store (post-morf pre-twist)
    # + morf counters -- the general-correctness f0 pose seed (README ## Addresses, session 16).
    ofd = r.u32(lp + 0x30DC)
    joints = []
    for j in range(42):                       # all CL joints; the body_co/foot chains read a subset
        ti = r.u32(ofd + 0x1C) + j * 0x20     # J3DTransformInfo: scale +0, rot(s16x3) +0xC, trans +0x14
        qp = r.u32(ofd + 0x20) + j * 0x10     # Quaternion: x,y,z,w f32
        joints.append(dict(
            scale=[r.f32(ti + 0x0), r.f32(ti + 0x4), r.f32(ti + 0x8)],
            rot=[r.s16(ti + 0xC), r.s16(ti + 0xE), r.s16(ti + 0x10)],
            trans=[r.f32(ti + 0x14), r.f32(ti + 0x18), r.f32(ti + 0x1C)],
            quat=[r.f32(qp + 0x0), r.f32(qp + 0x4), r.f32(qp + 0x8), r.f32(qp + 0xC)]))
    old_pose = dict(
        flg=r.u8(ofd + 0x0), counter=r.f32(ofd + 0x4), f8=r.f32(ofd + 0x8),
        rate=r.f32(ofd + 0xC), f10=r.f32(ofd + 0x10), f14=r.f32(ofd + 0x14),
        start_joint=r.u16(ofd + 0x18), end_joint=r.u16(ofd + 0x1A), joints=joints)
    seed = dict(
        stage="Hyrule", slot=int(slot), proc=r.s32(lp + 0x3100),
        link=dict(pos=[r.f32(la + 0x1F8), r.f32(la + 0x1FC), r.f32(la + 0x200)],
                  travel=r.u16(la + 0x206), facing=r.u16(la + 0x20E),
                  speedF=r.f32(la + 0x254), nspeed=r.f32(la + 0x35BC),
                  max_nspeed=r.f32(la + 0x2A8), mdir=r.u8(la + 0x34B8),
                  m34E6=r.u16(la + 0x34E6), csangle=_csangle(r),
                  # m3564 (csXyz s16): the head-look twist residual -- the NeckLook f0 seed
                  # (land.neck_look; at THIS f0 it is mid-decay from the prior cycle's look).
                  m3564=[r.s16(la + 0x3564), r.s16(la + 0x3566), r.s16(la + 0x3568)]),
        # attention residual (session 12: NONE / no actor at f0 -> the sim's default AttentionLock)
        atn=dict(lock_state=(r.u8(attn + 0x18) if attn else -1),
                 actor_lock=r.u32(lp + 0x30C4)),
        old_pose=old_pose,
        zl1=_zl1_look_row(r, tetra))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(seed, f, indent=1)
    lk = seed['link']
    print("seed f0 (%s slot %d, proc %s): pos (%.4f, %.4f, %.4f)" % (
        seed['stage'], seed['slot'], PROC.get(seed['proc'], seed['proc']),
        lk['pos'][0], lk['pos'][1], lk['pos'][2]))
    print("  speedF=%.9f  mNormalSpeed=%.9f  (lag %.4f)  mDir=%d  lock=%d  actor=0x%08x"
          % (lk['speedF'], lk['nspeed'], lk['nspeed'] - lk['speedF'], lk['mdir'],
             seed['atn']['lock_state'], seed['atn']['actor_lock']))
    print("wrote seed -> %s" % out)
    return 0


def capture(out=DEFAULT_OUT, frames=60, slot=2):
    import dolphin_mem as D
    # canonical start
    D.control_pipe_quiet("pause")
    D.control_pipe_quiet("savestate", {"action": "load", "slot": int(slot)})
    tetra = find_tetra_instance(D, reload_slot=int(slot))   # traps _execute, then reloads slot
    r = _rdr(D)
    if r.s8(tetra + ZL1_TYPE_OFF) != 5:
        raise RuntimeError("actor at 0x%08x is not the type-5 following Tetra" % tetra)

    rows = [_snap(r, tetra, 0)]
    for i in range(1, frames + 1):
        D.control_pipe_quiet("advance", {"frames": 1})
        rows.append(_snap(r, tetra, i))

    seed = rows[0]
    fix = dict(stage="Hyrule", slot=int(slot), tetra_base="0x%08x" % tetra,
               link_ptr="0x803AD860", proc_names=PROC, seed=seed, frames=rows)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(fix, f, indent=1)

    # compact table
    print("f  proc            lx       lz     lsF  ltrav lface anim |    tx       tz     tsF stt | dLT")
    for row in rows:
        lk, tt = row['link'], row['tetra']
        print("%3d %-14s %8.2f %8.2f %6.2f %5d %5d %5.1f | %8.2f %8.2f %5.2f %d | %5.1f" % (
            row['f'], PROC.get(row['proc'], str(row['proc'])), lk['pos'][0], lk['pos'][2],
            lk['speedF'], lk['travel'], lk['facing'], lk['anim'],
            tt['pos'][0], tt['pos'][2], tt['speedF'], tt['stt'], row['dist_LT']))
    print("seed: Link (%.4f, %.4f, %.4f) speedF=%.5f proc=%s | Tetra (%.4f, %.4f) type5"
          % (seed['link']['pos'][0], seed['link']['pos'][1], seed['link']['pos'][2],
             seed['link']['speedF'], PROC.get(seed['proc']),
             seed['tetra']['pos'][0], seed['tetra']['pos'][2]))
    print("wrote %d frames -> %s" % (len(rows), out))
    return 0


if __name__ == '__main__':
    kw = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
    if 'seed' in sys.argv[1:]:            # `python -m harness.tetrapush.capture_push seed` -> the f0 seed
        sys.exit(capture_seed(out=kw.get('out', SEED_OUT), slot=int(kw.get('slot', 2))))
    sys.exit(capture(out=kw.get('out', DEFAULT_OUT),
                     frames=int(kw.get('frames', 60)), slot=int(kw.get('slot', 2))))
