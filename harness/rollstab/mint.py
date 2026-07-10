"""Mint anchors for the roll-stab sandbox.

Translated anchors: load a base anchor with the emulator PAUSED FIRST (zero frames run, so the
idle anim state is preserved bit-for-bit -- letting the game run even ~2.5s between load and
pause advances the idle/fidget state and desyncs the anchor from its seed json; that bug cost the
idle4..idle11 chain), write link_x/z += delta, save as the new anchor, and copy the seed json
with the new position.

    python -m harness.rollstab.mint base=<anchor> name=<anchor> dx=0.0 dz=0.05
"""
import os, sys, json, time, shutil
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


def mint(base, name, dx, dz):
    ENV.ensure_running()
    src = os.path.join(ANCHOR_DIR, base + '.sav')
    D.control_pipe_quiet('pause')
    time.sleep(0.5)
    D.control_pipe_quiet('savestate', {'action': 'load', 'path': src.replace('\\', '/')})
    time.sleep(1.5)
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
    json.dump(seed, open(os.path.join(ANCHOR_DIR, name + '.seed.json'), 'w'), indent=1)
    print('captured', dst)


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    mint(o['base'], o['name'], float(o.get('dx', 0.0)), float(o.get('dz', 0.0)))
