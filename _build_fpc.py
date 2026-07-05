from setuptools import setup
from Cython.Build import cythonize
setup(name="fpc", ext_modules=cythonize(["tww_sim/core/_fpc.pyx"], language_level=3),
      script_args=["build_ext", "--inplace"])
