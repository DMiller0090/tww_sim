"""Build the native (Cython) accelerators in-place:
  tww_sim/core/_fpc.pyx        -- single-precision (f32) fused ops
  tww_sim/core/anim/_anmc.pyx  -- land-walk anim hot loop (matrix/quat/Hermite)

Both are OPTIONAL: when a .pyd is absent the pure-Python fallbacks run (same result). Run:
    python _build_native.py            # build both
    python _build_native.py _anmc      # build only the anim accelerator
"""
import sys
from setuptools import setup
from Cython.Build import cythonize

_SOURCES = {
    "_fpc": "tww_sim/core/_fpc.pyx",
    "_anmc": "tww_sim/core/anim/_anmc.pyx",
}

sel = [a for a in sys.argv[1:] if a in _SOURCES]
srcs = [_SOURCES[k] for k in (sel or _SOURCES)]
# strip our own args so setuptools only sees build_ext
sys.argv = [sys.argv[0], "build_ext", "--inplace"]
setup(name="tww_sim_native", ext_modules=cythonize(srcs, language_level=3))
