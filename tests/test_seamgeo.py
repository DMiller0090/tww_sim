"""SeamGeo: the roll/wall-clip geometry abstraction derives F + the cut lunge from the seam,
instead of pasting them. Gates the session-45 generalization kickoff (Phases 1-2, standard-roll
path only -- the Tetra push clip stays a standalone solver and is NOT covered here).

  * F is COMPUTED from the interior bisector + camera yaw (bit-exact == the old by-inspection 33295).
  * the cut endpoint is COMPUTED per candidate from the CUT_F root translate at F (bit-identical to
    the real LandState.enter_cut) -- there is no frozen per-`old` LUNGE literal to reproduce.
  * geometry.py (the kaze shim) is instance-backed by SeamGeo, so its whole `G` surface is unchanged.
"""
import os, sys
_rb = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _rb not in sys.path:
    sys.path.insert(0, _rb)

import json
from tww_sim.core.fp import f32 as _f
from tww_sim.land.land import LandState
from tww_sim.land.constants import CUT_F
from harness.rollstab.seamgeo import SeamGeo, derive_F
from harness.rollstab import geometry as G

_GEO = json.load(open(os.path.join(_rb, 'fixtures', 'kaze_r11_geo.json')))
_KAZE_CSANGLE = 29883                       # the kaze roll seam's frozen camera yaw


def test_F_derived_bit_exact():
    """F == the closest-reachable bisector decode, NOT a pasted literal (kaze: csangle 29883)."""
    assert derive_F(_GEO['bisector_deg'], _KAZE_CSANGLE) == 33295
    assert SeamGeo(_GEO, _KAZE_CSANGLE).F == 33295


def test_F_is_camera_dependent():
    """F is genuinely derived (a function of csangle), not hardcoded: a different camera yaw yields
    a different roll facing. (Guards against someone reintroducing a pasted `F = 33295`.)"""
    other = derive_F(_GEO['bisector_deg'], (_KAZE_CSANGLE + 4096) & 0xFFFF)
    assert other != 33295


def test_cut_new_matches_enter_cut_bit_exact():
    """The derived cut endpoint == the real sim CUT_F entry (LandState.enter_cut), 0-ULP, at several
    olds spanning the seam band -- so the lunge is computed from the CUT anim, not a stored delta."""
    seam = SeamGeo(_GEO, _KAZE_CSANGLE)
    for old in [(9072.208984375, 308.028076171875), (9071.5, 302.6), (0.0, 0.0), (9072.7, 305.1)]:
        st = LandState(native=False)
        st.pos_x, st.pos_z = _f(old[0]), _f(old[1])
        st.facing = seam.F
        st.travel = seam.F
        st.nspeed = seam.roll_speedf
        st.speedF = seam.roll_speedf
        st.enter_cut(CUT_F)
        real = (st.pos_x, st.pos_z)
        assert seam.cut_new((_f(old[0]), _f(old[1]))) == real, old


def test_shim_is_instance_backed():
    """geometry.py exports come straight from a fresh SeamGeo built on the same fixture+csangle:
    the `G` surface is exactly the abstraction, nothing pasted alongside it."""
    seam = SeamGeo(_GEO, _KAZE_CSANGLE)
    assert G.F == seam.F == 33295
    assert G.LUNGE == seam.LUNGE
    assert G.S == seam.S and G.LINK_Y == seam.LINK_Y and len(G.TRIS) == len(seam.TRIS)
    # acceptance verdicts identical across the whole dust band the drill ranker probes
    zz = 302.6
    while zz <= 308.2:
        xx = 9071.5
        while xx <= 9072.7:
            o = (_f(xx), _f(zz))
            assert G.pred_genuine(o) == seam.pred_genuine(o)
            xx += 0.05
        zz += 0.2


def test_lunge_magnitude_is_roll_reach():
    """The derived lunge magnitude is the roll-stab reach (~49.2202u) thrust_scan keys off."""
    seam = SeamGeo(_GEO, _KAZE_CSANGLE)
    mag = (seam.LUNGE[0] ** 2 + seam.LUNGE[1] ** 2) ** 0.5
    assert abs(mag - 49.2202) < 1e-3
