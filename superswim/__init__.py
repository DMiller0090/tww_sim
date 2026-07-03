"""superswim — bit-exact offline simulation + route planner for TWW (GZLJ01/JP) superswimming.

Pure-Python, live-validated physics (no Dolphin dependency). See SUPERSWIM_KNOWLEDGE.md for the
mechanics. The live-Dolphin validation harness lives under ``harness/`` (separate, optional).

Typical use::

    from superswim import SwimState, plan_min_frames
    st = SwimState(v=0.0, anim=0.06392288208007812, air=900)
    for a in ("chg",) * 60: st.step(a)
    print(st.v, st.anim)
"""
from .sim import SwimState, run_trace, run_arrow, ArrowState
from .land import LandState, run_walk
from .plan import plan_min_frames, plan_hierarchical
from .optimize import beam_search, beam_search_to_dest
from .actions import expand, acts_to_seq, animdiff, ESS, NEU, CHG_UP, CHG_DN

__version__ = "0.1.0"

__all__ = [
    "SwimState", "run_trace", "run_arrow", "ArrowState",
    "LandState", "run_walk",
    "plan_min_frames", "plan_hierarchical",
    "beam_search", "beam_search_to_dest",
    "expand", "acts_to_seq", "animdiff", "ESS", "NEU", "CHG_UP", "CHG_DN",
]
