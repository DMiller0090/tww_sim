"""camera.py — the canonical per-frame camera (csangle) engine for the sim.

``LandState`` (land.py) drives this camera integrator so the camera-relative movement target
(``m34E8 = m34DC(stick) + csangle``) is steered from the C-stick with one bit-exact recurrence.
It is a thin top-level re-export of the planner-side predictor
``predict.camera_arbitrary.CameraArbitrary`` (the more complete 2-D ``(csx,csy)`` engine) so the
sim does not reach into ``predict/`` (which is planner-side). ``SwimState`` can adopt the same
``Camera`` when swim-steering is wired; the swim predictors already use ``CameraArbitrary``.

The engine is s16-integer and deterministic. See ``predict/camera_exact.py`` for the recurrence
derivation and ``knowledge/mechanics/camera.md`` for the law + omega table.

Backward-compat (frozen free-cam): ``omega_cmd(128, csy) == 0`` for csy in {0,128}, so any input
that holds the C-stick X centered (csx=128 — the straight-superswim / free-cam convention) leaves
csangle pinned at its seed and the camera contributes nothing, exactly matching the pre-wiring
constant-camera behaviour.
"""
from __future__ import annotations

from .predict.camera_arbitrary import CameraArbitrary as Camera, omega_cmd, has

__all__ = ["Camera", "omega_cmd", "has"]
