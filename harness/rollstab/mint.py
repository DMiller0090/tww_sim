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
    mint(o['base'], o['name'], float(o.get('dx', 0.0)), float(o.get('dz', 0.0)))
