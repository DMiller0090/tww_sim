# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""Differential 0-ULP gate for the native `_anmc.co_center` (session 35).

The native fold of `FootFK.body_co_center` (the setCollision root/neck midpoint) must be BIT-FOR-BIT
identical to the pure-Python loop it replaces -- across leans, body-leans (the BODY_CHN twist), and
positions, on a REALISTIC stored old pose (a mid-rollout dash pose, whose neck SSC scales are
non-identity). If the .pyd is absent this whole module is a no-op (nothing to compare)."""
import struct
import warnings

import pytest

from tww_sim.core.anim import foot_fk


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.mark.skipif(foot_fk._N is None, reason="native _anmc not built")
def test_body_co_center_native_matches_python_bit_exact():
    from harness.tetrapush import seeds
    warnings.simplefilter('ignore')
    env = seeds.load_env()
    run = seeds.make_freerun(env)
    inp = dict(stickX=128, stickY=110, buttons=0, triggerL=0, substickX=128, substickY=128)
    run.pre_seed_input(inp)
    # Step a handful of frames so the stored old pose is a real dash pose (non-identity neck SSC).
    for _ in range(12):
        run.step(inp)
    ff = run.link._foot.ff
    assert ff.body_co and ff.world

    checked = 0
    # Sweep base pos / facing / draw-lean / body-lean (the BODY_CHN twist) over the stored old pose.
    for px, pz in ((-1400.0, -40.0), (-1517.13, -765.9), (12.0, 3000.0)):
        for facing in (0, 4705, 12386, 37552, 0xC000):
            for lean in (0, 300, -700 & 0xFFFF):
                for body_lean in (None, 0, 640, -1200 & 0xFFFF):
                    nat = ff.body_co_center(px, 0.1633, pz, facing, lean=lean,
                                            body_lean=body_lean)
                    ref = ff.body_co_center(px, 0.1633, pz, facing, lean=lean,
                                            body_lean=body_lean, _force_py=True)
                    assert _bits(nat[0]) == _bits(ref[0]), (px, pz, facing, lean, body_lean, 'cx')
                    assert _bits(nat[1]) == _bits(ref[1]), (px, pz, facing, lean, body_lean, 'cz')
                    checked += 1
    assert checked >= 100
