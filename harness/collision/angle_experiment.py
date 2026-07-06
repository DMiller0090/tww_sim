"""Clippable corner-angle sweep on SYNTHETIC seams — enabled by the bit-exact cM3d_CalcPla in
tww_sim.core.collision (frsqrte port). Fix wall A (vertical); pivot wall B about the shared vertical
seam edge by turn angle alpha (B stays vertical); build each triangle's plane with calc_pla (bit-exact
to what the game would compute for those vertices), then search for genuine clips per angle.

Findings (see knowledge/mechanics/seam-clip.md):
  * Near-90 corners DO clip (interior 80-137 all clippable), matching live confirmation.
  * There is NO clean geometric angle cutoff: clippability at a given angle is governed by the
    per-triangle plane FAN (a sub-ULP property of the exact vertices), so exactly-90.0 can miss while
    88/92 clip. Whether a *specific* real seam clips depends on its exact coordinates.
  * Reflex/concave corners (turn the other way) clip over a wider range.
  * Earlier "cutoff" results were a fixed-start-position artifact; starts must be placed in front of
    the rotated corner (front bisector), or heavily-rotated walls get spuriously marked unclippable.

    python -m harness.collision.angle_experiment
"""
import math

from tww_sim.core.collision import Tri, crr_pos_walls

A_FAR = (-513.3269653320312, -37420.58203125)
S = (-847.6320190429688, -37336.61328125)
YB, YT = 5834.38037109375, 7334.38134765625
LINK_Y = 5852.66
_B_FAR0 = (-1085.3291015625, -36967.18359375)
_L = math.hypot(_B_FAR0[0]-S[0], _B_FAR0[1]-S[1])
_vA = (S[0]-A_FAR[0], S[1]-A_FAR[1]); _m = math.hypot(*_vA)
_uA = (_vA[0]/_m, _vA[1]/_m)


def build_angle(alpha_deg):
    """Wall A (fixed) + wall B pivoted by alpha about the seam. alpha=0 -> B straight-continues A."""
    a = math.radians(alpha_deg)
    dx = _uA[0]*math.cos(a) - _uA[1]*math.sin(a)
    dz = _uA[0]*math.sin(a) + _uA[1]*math.cos(a)
    bf = (S[0] + _L*dx, S[1] + _L*dz)
    A_up = ((A_FAR[0], YB, A_FAR[1]), (A_FAR[0], YT, A_FAR[1]), (S[0], YT, S[1]))
    A_lo = ((A_FAR[0], YB, A_FAR[1]), (S[0], YT, S[1]),         (S[0], YB, S[1]))
    B1 = ((S[0], YB, S[1]), (S[0], YT, S[1]), (bf[0], YT, bf[1]))
    B2 = ((S[0], YB, S[1]), (bf[0], YT, bf[1]), (bf[0], YB, bf[1]))
    return [Tri(*A_up), Tri(*A_lo), Tri(*B1), Tri(*B2)]


def _seg_dist_to_S(ax, az, bx, bz):
    dx, dz = bx-ax, bz-az; dd = dx*dx + dz*dz
    if dd < 1e-9:
        return math.hypot(ax-S[0], az-S[1])
    t = max(0.0, min(1.0, ((S[0]-ax)*dx + (S[1]-az)*dz) / dd))
    return math.hypot(ax + t*dx - S[0], az + t*dz - S[1])


def clippable(alpha_deg):
    """True if a genuine clip exists for this corner (adaptive front-bisector starts). Returns
    (clippable, sample_displacement)."""
    tris = build_angle(alpha_deg); pA = tris[1].pla; pB = tris[2].pla
    fA = lambda x, z: pA.d + pA.nx*x + pA.ny*LINK_Y + pA.nz*z
    fB = lambda x, z: pB.d + pB.nx*x + pB.ny*LINK_Y + pB.nz*z
    bx, bz = pA.nx+pB.nx, pA.nz+pB.nz; bm = math.hypot(bx, bz); bx, bz = bx/bm, bz/bm
    tx, tz = -bz, bx
    for fd in (32, 42):
        for lat in (-8, 0, 8):
            ix = S[0]+fd*bx+lat*tx; iz = S[1]+fd*bz+lat*tz
            if not (fA(ix, iz) > 0 and fB(ix, iz) > 0):
                continue
            base = math.atan2(S[0]-ix, S[1]-iz)
            for ai in range(81):
                ang = base + math.radians(-20 + ai*0.5); sdx, sdz = math.sin(ang), math.cos(ang)
                D = 36.0
                while D <= 64:
                    ex, ez = ix + D*sdx, iz + D*sdz
                    if _seg_dist_to_S(ix, iz, ex, ez) <= 4 and fA(ex, ez) < 0 and fB(ex, ez) < 0:
                        _, info = crr_pos_walls((ix, LINK_Y, iz), (ex, LINK_Y, ez), tris)
                        if not info["line_hit"] and not info["wall_hit"]:
                            return True, round(D, 0)
                    D += 1.0
    return False, None


if __name__ == "__main__":
    print(f"{'turn':>6} {'interior':>9} {'clippable':>10}")
    for alpha in (43.1, 60, 75, 85, 88, 90, 92, 95, 100, -43.1, -90):
        ok, D = clippable(alpha)
        print(f"{alpha:+6.1f} {180-alpha:9.1f} {str(ok):>10}" + (f"  (D~{D})" if ok else ""))
