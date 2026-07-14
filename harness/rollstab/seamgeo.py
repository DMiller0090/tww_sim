"""SeamGeo: a per-seam roll/wall-clip geometry + acceptance object, DERIVED from a corner
geometry fixture + the anchor camera yaw (csangle).

This generalizes the STANDARD bare roll-stab clip (formerly the kaze-hardcoded
`harness.rollstab.geometry`) to ANY enumerated seam. The two things that used to be pasted
by-inspection literals -- the roll facing `F` and the cut lunge -- are now COMPUTED from the seam:

  * F      = the roll facing == the closest-reachable full-deflection stick decode to the interior
             bisector at this camera yaw. `stick_for_bearing(bisector, csangle, 1.0)` inverts the
             walk want-target (m34E8) to a byte stick, but the octagon clamp + byte quantization mean
             the reachable decode is the CLOSEST, not the exact, bisector -- so F is that reachable
             want-target (the relationship documented in cornergate.py:10-11, now coded here).
  * cut_new(old) = the CUT_F entry endpoint out of a full-cap roll (speedF `ROLL_SPEEDF`): the ANM_CUT
             joint-0 root translate (m3700 @ frame 4.0, facing-rotated) + the speedF lunge term,
             bit-identical to `LandState.enter_cut` / `walkstab.fast_cut` (verified 0-ULP). No frozen
             per-`old` delta: the endpoint is computed exactly at each candidate, so there is no magic
             extraction point to reproduce ([[no-overtuned-constants]]).

NOT for the Tetra push clip. That corner is a NEEDS-PUSH clip whose acceptance endpoint is the
COUPLED `new = f32(old + push + lunge)` and whose F is target-defined (`world_angle(new-old)`), not
a bisector decode. It is a standalone, single-seam solver (`geometry_tetra.py` / `solver_tetra.py` /
`pushaside.py` / `turnaround.py`) and stays separate.

A seam's geo fixture (reproducibly built by `capture_walls.py` / `make_tetra_geo.py`) supplies:
  wallA, wallB  -- the two incident wall tris (`plane.func(p) > 0` == in front)
  barrier       -- the full CrrPos barrier tri set, in the game's block-grid order
  S             -- the seam vertex [x, y, z]
  bisector_deg  -- the interior bisector world bearing (degrees)
  link_y        -- Link's world Y on the walkable floor at the corner
plus the anchor camera yaw `csangle`. The acceptance tests are exact f32 candidate tests, never a
fitted ribbon ([[knowledge/strategy/seam-clip-solver]]).
"""
import os, sys, math
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.core.collision import Tri, Plane, crr_pos_walls
from tww_sim.core.fp import f32 as _f
import tww_sim.core.mathlib as M
from tww_sim.core.mathlib import deg_to_s16, main_stick_decode
from tww_sim.land.plan_land import stick_for_bearing
from tww_sim.land.procs.cut import _cM_ssin_s16

A_BTN, B_BTN = 0x100, 0x200
KROLL = 15                     # aim frames between the A roll init and the single B edge
ROLL_SPEEDF = 26.0             # the full-cap roll's peak speedF carried into the CUT_F lunge
                               # (capped walk 17 -> roll 26; KB mechanics/roll-stab.md). NOT per-seam.


def _mk(t):
    return Tri(t["v"][0], t["v"][1], t["v"][2],
               plane=Plane(t["n"][0], t["n"][1], t["n"][2], t["d"]))


_CUT_L0 = None


def _cut_root_translate():
    """The CUT_F joint-0 (root) mTranslate at CUT_START (4.0) -- a CONSTANT (m3700_prev==0 in
    _cut_init, m34C2==1), facing-INDEPENDENT. Cached once so a fresh SeamGeo never re-evals the
    J3D tree. (Same value walkstab.cut_lunge_const caches.)"""
    global _CUT_L0
    if _CUT_L0 is None:
        from tww_sim.land.land import LandState
        from tww_sim.land.constants import CUT_F
        s = LandState(native=False)
        _CUT_L0 = s._cut_m3700_at(CUT_F, s.CUT_START)
    return _CUT_L0


def derive_F(bisector_deg, csangle):
    """The roll facing for a seam: the walk want-target (m34E8) of the closest-reachable
    full-deflection stick to the interior bisector at this camera yaw. `stick_for_bearing` inverts
    m34E8 -> a byte stick (clamp-aware); decoding it back and re-adding csangle gives the reachable
    want-target, which the octagon/quantization pin near, not on, the bisector."""
    bis = deg_to_s16(float(bisector_deg) % 360.0)
    stk = stick_for_bearing(bis, int(csangle) & 0xFFFF, 1.0)
    ang, _m = main_stick_decode(*stk)
    return (ang + 0x8000 + (int(csangle) & 0xFFFF)) & 0xFFFF


class SeamGeo:
    """Geometry + exact clip acceptance for one standard roll/wall seam (see module docstring)."""

    A_BTN, B_BTN, KROLL, ROLL_SPEEDF = A_BTN, B_BTN, KROLL, ROLL_SPEEDF

    def __init__(self, geo, csangle, roll_speedf=ROLL_SPEEDF):
        self.geo = geo
        self.csangle = int(csangle) & 0xFFFF
        self.roll_speedf = roll_speedf
        self.wA, self.wB = _mk(geo["wallA"]), _mk(geo["wallB"])
        self.BARRIER = [_mk(t) for t in geo["barrier"]]
        self.TRIS = [self.wA, self.wA, self.wB] + self.BARRIER
        self.LINK_Y = geo["link_y"]
        self.S = (geo["S"][0], geo["S"][2])
        self.F = derive_F(geo["bisector_deg"], self.csangle)
        _r = self.F / 65536.0 * 2 * math.pi
        self.DIRX, self.DIRZ = math.sin(_r), math.cos(_r)
        self.PX, self.PZ = -self.DIRZ, self.DIRX      # perp(F) axis (plan_search convention)

    # --- exact acceptance -----------------------------------------------------------------
    def p32(self, x, z):
        return (_f(x), self.LINK_Y, _f(z))

    def in_front(self, p):
        return self.wA.pla.func(p) > 0 and self.wB.pla.func(p) > 0

    def seg_blocked(self, a, b):
        _, info = crr_pos_walls(self.p32(a[0], a[1]), self.p32(b[0], b[1]), self.TRIS)
        return info["line_hit"] or info["wall_hit"]

    def genuine_clip(self, old, new):
        po, pn = self.p32(old[0], old[1]), self.p32(new[0], new[1])
        _, info = crr_pos_walls(po, pn, self.TRIS)
        if info["line_hit"] or info["wall_hit"]:
            return False
        if not self.in_front(po):
            return False
        return self.wA.pla.func(pn) < 0 or self.wB.pla.func(pn) < 0

    def cut_new(self, old):
        """The CUT_F entry endpoint from `old` out of a full-cap roll -- bit-identical to
        `LandState.enter_cut(CUT_F, aim=None)` / `walkstab.fast_cut` (travel==facing==F, the root
        translate rotated by F + the speedF lunge term; the two component f32 adds, per candidate)."""
        L0 = _cut_root_translate()
        speedF = 0.0 if abs(self.roll_speedf) < 0.05 else self.roll_speedf
        s = _cM_ssin_s16(self.F)
        c = M.cM_scos_s16(self.F)
        add_x = _f(_f(L0[2] * s) + _f(L0[0] * c))
        add_z = _f(_f(L0[2] * c) - _f(L0[0] * s))
        nx = _f(_f(_f(old[0]) + _f(speedF * s)) + add_x)
        nz = _f(_f(_f(old[1]) + _f(speedF * c)) + add_z)
        return (nx, nz)

    def pred_genuine(self, old):
        """genuine_clip against the REAL cut endpoint at `old` (bit-identical to the sim's cut
        `new`) -- the pure-geometry dust test used by maps/rankers."""
        return self.genuine_clip(old, self.cut_new(old))

    def perp(self, p):
        return (p[0] - self.S[0]) * self.PX + (p[1] - self.S[1]) * self.PZ

    def along(self, p):
        return (p[0] - self.S[0]) * self.DIRX + (p[1] - self.S[1]) * self.DIRZ

    @property
    def LUNGE(self):
        """The cut lunge as an origin-referenced (dx, dz) -- a pure function of (F, ROLL_SPEEDF),
        for the roll-stab reach magnitude (~49.2202u). Informational: acceptance uses `cut_new(old)`
        per candidate, so no consumer depends on this being evaluated at a particular `old`."""
        return self.cut_new((0.0, 0.0))
