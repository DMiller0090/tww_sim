"""Mint anchors for the roll-stab sandbox.

Translated anchors: load a base anchor with the emulator PAUSED FIRST (zero frames run, so the
idle anim state is preserved bit-for-bit -- letting the game run even ~2.5s between load and
pause advances the idle/fidget state and desyncs the anchor from its seed json; that bug cost the
idle4..idle11 chain), write link_x/z += delta, save as the new anchor, and copy the seed json
with the new position.

The seed json also carries the REST_* fields rest.rest_state seeds the from-rest-exact sim
with, all read from RAM at the paused anchor:
  * the WAIT(4) blend frame ctrls (d/w frame + rate, player +0x2F64/+0x2F78/+0x2F60/+0x2F74),
  * the posMoveFromFootPos smoothing state (m359C/m35B4, +0x34C4/+0x34DC),
  * the STORED delayed foot poses t2 (mFootData[i] 018/00C: rtoe +0x3CF8, ltoe +0x3E10, rheel
    +0x3CEC, lheel +0x3E04 on JP) and t1 (the same fields after ONE paused frame-advance -- the
    advanced frame's execute stores the pose the anchor's matrices held). These carry the BASE
    anchor's position rounding noise, which a translated anchor's re-posed stream cannot.

    python -m harness.rollstab.mint base=<anchor> name=<anchor> dx=0.0 dz=0.05
"""
import os, sys, json, time, struct
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

import dolphin_mem as D
from harness import dolphin_env as ENV
from harness.rollstab.geometry import ANCHOR_DIR
from tww_sim.core.fp import f32 as _f

_FOOT_OFF = dict(rtoe=0x3CF8, ltoe=0x3E10, rheel=0x3CEC, lheel=0x3E04)  # JP mFootData 018/00C


def _player(h, m):
    return struct.unpack('>I', D.read_bytes(h, m, 0x803AD860, 4))[0]


def _f32_at(h, m, addr):
    return struct.unpack('>f', D.read_bytes(h, m, addr, 4))[0]


def _foot_tuple(h, m, Pp):
    out = []
    for key in ('rtoe', 'ltoe', 'rheel', 'lheel'):
        out += list(struct.unpack('>3f', D.read_bytes(h, m, Pp + _FOOT_OFF[key], 12)))
    return out


def _load_paused(path):
    D.control_pipe_quiet('pause')
    time.sleep(0.5)
    D.control_pipe_quiet('savestate', {'action': 'load', 'path': path.replace('\\', '/')})
    time.sleep(1.5)


def capture_rest(src):
    """Read the rest_* seed fields from an anchor savestate (leaves the anchor re-loaded)."""
    _load_paused(src)
    h, m = D.attach()
    Pp = _player(h, m)
    rest = dict(rest_d_frame=_f32_at(h, m, Pp + 0x2F64),
                rest_w_frame=_f32_at(h, m, Pp + 0x2F78),
                rest_d_rate=_f32_at(h, m, Pp + 0x2F60),
                rest_w_rate=_f32_at(h, m, Pp + 0x2F74),
                rest_m359C=_f32_at(h, m, Pp + 0x34C4),
                rest_m35B4=_f32_at(h, m, Pp + 0x34DC),
                rest_t2=_foot_tuple(h, m, Pp))
    # ONE paused frame-advance: the advanced frame's execute stores the anchor's held pose into
    # mFootData (the t1 the from-rest sim composes with at its first real row).
    d0 = rest['rest_d_frame']
    for _ in range(3):
        D.control_pipe_quiet('advance', {'frames': 1})
        time.sleep(0.3)
        if _f32_at(h, m, Pp + 0x2F64) != d0:
            break
    rest['rest_t1'] = _foot_tuple(h, m, Pp)
    _load_paused(src)          # restore: the advance must never leak into the minted anchor
    return rest


def capture_full_seed(h, m):
    """Read the COMPLETE seed json (base state + rest_* fields) from the currently loaded paused
    anchor. Unlike `mint` (translate + inherit the base seed), this reads EVERY field from RAM, so
    it can mint an anchor whose equip/idle/facing differs from any existing base (e.g. a SHEATHED
    roll anchor -- session 36). Assumes the desired paused state is already live + saved to `dst`."""
    Pp = _player(h, m)
    seed = dict(link_x=D.read_named(h, m, 'link_x'), link_z=D.read_named(h, m, 'link_z'),
                link_y=_f32_at(h, m, Pp + 0x124),
                facing=D.read_named(h, m, 'facing') & 0xFFFF,
                shape_angle_y=D.read_named(h, m, 'shape_angle_y') & 0xFFFF,
                travel_angle=D.read_named(h, m, 'travel_angle') & 0xFFFF,
                csangle=D.read_named(h, m, 'csangle') & 0xFFFF,
                link_state=D.read_named(h, m, 'link_state'),
                anim_frame=_f32_at(h, m, Pp + 0x2F64),
                mEquipItem=struct.unpack('>H', D.read_bytes(h, m, Pp + 0x3488, 2))[0])
    seed['sword_drawn'] = (seed['mEquipItem'] == 0x103)
    seed['equip_item'] = seed['mEquipItem']
    return seed


def mint_current(name):
    """Mint the anchor from whatever Link is doing RIGHT NOW (the live, paused state) -- full-seed
    capture, no base inheritance. Set Link up live first (load + press A to sheathe, settle the
    idle, etc.), then call this. Saves the savestate, captures the complete seed json (incl. the
    rest_* fields via capture_rest), and leaves the anchor re-loaded."""
    dst = os.path.join(ANCHOR_DIR, name + '.sav')
    D.control_pipe_quiet('pause')
    time.sleep(0.4)
    D.control_pipe_quiet('savestate', {'action': 'save', 'path': dst.replace('\\', '/')})
    time.sleep(0.8)
    rest = capture_rest(dst)          # loads dst, reads rest_*, t1-advance, reloads dst (paused)
    h, m = D.attach()
    seed = capture_full_seed(h, m)
    seed.update(rest)
    json.dump(seed, open(os.path.join(ANCHOR_DIR, name + '.seed.json'), 'w'), indent=1)
    print('minted %s' % dst)
    print('  pos=(%.6f,%.6f,%.6f) facing=%d csangle=%d state=%d equip=0x%X anim=%.5f' % (
          seed['link_x'], seed['link_y'], seed['link_z'], seed['shape_angle_y'], seed['csangle'],
          seed['link_state'], seed['mEquipItem'], seed['anim_frame']))
    print('  rest d=%.6f w=%.6f d_rate=%.4f w_rate=%.4f m359C=%.6g' % (
          rest['rest_d_frame'], rest['rest_w_frame'], rest['rest_d_rate'], rest['rest_w_rate'],
          rest['rest_m359C']))
    return seed


def mint(base, name, dx, dz):
    ENV.ensure_running()
    src = os.path.join(ANCHOR_DIR, base + '.sav')
    rest = capture_rest(src)
    h, m = D.attach()
    x0 = D.read_named(h, m, 'link_x')
    z0 = D.read_named(h, m, 'link_z')
    nx, nz = _f(x0 + dx), _f(z0 + dz)
    D.cmd_writename('link_x', repr(nx))
    D.cmd_writename('link_z', repr(nz))
    print('pos (%.10f,%.10f) -> (%.10f,%.10f)' % (x0, z0, nx, nz))
    dst = os.path.join(ANCHOR_DIR, name + '.sav')
    D.control_pipe_quiet('savestate', {'action': 'save', 'path': dst.replace('\\', '/')})
    # seed json travels with the anchor
    seed_src = os.path.join(ANCHOR_DIR, base + '.seed.json')
    seed = json.load(open(seed_src))
    seed['link_x'], seed['link_z'] = float(nx), float(nz)
    seed.update(rest)
    json.dump(seed, open(os.path.join(ANCHOR_DIR, name + '.seed.json'), 'w'), indent=1)
    print('captured %s (rest d=%.10f w=%.10f m359C=%.10g)' % (
          dst, rest['rest_d_frame'], rest['rest_w_frame'], rest['rest_m359C']))


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    if 'current' in o:                    # mint the live paused state as a fresh full-seed anchor
        ENV.ensure_running()
        mint_current(o['current'])
    else:
        mint(o['base'], o['name'], float(o.get('dx', 0.0)), float(o.get('dz', 0.0)))
