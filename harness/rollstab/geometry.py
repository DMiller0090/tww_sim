"""Seam geometry + clip acceptance for the kaze r11 roll-stab sandbox.

Loads the corner geometry (fixtures/kaze_r11_geo.json: the two incident wall tris, the barrier
set, link_y, the vertex S) and provides the EXACT acceptance tests every solver stage uses:

  * genuine_clip(old, new)   -- the cut segment old->new crosses the seam: CrrPos NOT blocked,
                                old in front of both wall planes, new behind at least one.
  * seg_blocked(a, b)        -- a roll-approach segment fires the game's wall collision.
  * pred_genuine(old)        -- genuine_clip with the REAL enter_cut lunge added to `old`
                                (bit-identical to the sim's cut `new`; verified) -- the pure-
                                geometry dust test used by maps/rankers.

Anchor seeds live next to their savestates as tests/dolphin/anchors/<anchor>.seed.json.
Sandbox constants (F, the aim stick) are derived from the seed csangle; the roll facing 33295 is
the closest-to-bisector reachable decode at csangle 29883 ([[knowledge/strategy/seam-clip-solver]]).
"""
import os, json, math
# >>> repo bootstrap: locate tww_sim/ package root
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
import sys
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.core.collision import Tri, Plane, crr_pos_walls
from tww_sim.core.fp import f32 as _f
import tww_sim.core.mathlib as M
from tww_sim.land.procs.cut import _cM_ssin_s16

GEO = json.load(open(os.path.join(_rb, 'fixtures', 'kaze_r11_geo.json')))
ANCHOR_DIR = os.path.join(_rb, 'tests', 'dolphin', 'anchors')

A_BTN, B_BTN = 0x100, 0x200
KROLL = 15                     # aim frames between the A roll init and the single B edge
F = 33295                      # roll facing (closest-to-bisector reachable decode, csangle 29883)
# REAL enter_cut lunge at F (extracted from the sim's cut; new == f32(old + LUNGE) bit-exact)
LUNGE = (-2.3203125, -49.165496826171875)


def _mk(t):
    return Tri(t["v"][0], t["v"][1], t["v"][2],
               plane=Plane(t["n"][0], t["n"][1], t["n"][2], t["d"]))


wA, wB = _mk(GEO["wallA"]), _mk(GEO["wallB"])
BARRIER = [_mk(t) for t in GEO["barrier"]]
TRIS = [wA, wA, wB] + BARRIER
LINK_Y = GEO["link_y"]
S = (GEO["S"][0], GEO["S"][2])

_r = F / 65536.0 * 2 * math.pi
DIRX, DIRZ = math.sin(_r), math.cos(_r)
PX, PZ = -DIRZ, DIRX           # perp(F) axis (plan_search convention)


def load_seed(anchor):
    """The anchor's frame-0 rest snapshot (tests/dolphin/anchors/<anchor>.seed.json)."""
    return json.load(open(os.path.join(ANCHOR_DIR, anchor + '.seed.json')))


def p32(x, z):
    return (_f(x), LINK_Y, _f(z))


def in_front(p):
    return wA.pla.func(p) > 0 and wB.pla.func(p) > 0


def seg_blocked(a, b):
    _, info = crr_pos_walls(p32(a[0], a[1]), p32(b[0], b[1]), TRIS)
    return info["line_hit"] or info["wall_hit"]


def genuine_clip(old, new):
    po, pn = p32(old[0], old[1]), p32(new[0], new[1])
    _, info = crr_pos_walls(po, pn, TRIS)
    if info["line_hit"] or info["wall_hit"]:
        return False
    if not in_front(po):
        return False
    return wA.pla.func(pn) < 0 or wB.pla.func(pn) < 0


def pred_genuine(old):
    nw = (_f(old[0] + LUNGE[0]), _f(old[1] + LUNGE[1]))
    return genuine_clip(old, nw)


def perp(p):
    return (p[0] - S[0]) * PX + (p[1] - S[1]) * PZ


def along(p):
    return (p[0] - S[0]) * DIRX + (p[1] - S[1]) * DIRZ
