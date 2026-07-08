"""Stage-wide seam-clip scanner — find every clippable wall seam in a region and its MINIMUM
one-frame displacement, live from a running Dolphin.

This is the trustworthy rebuild of the earlier scratchpad scanner (which false-negated a known
live clip and false-positived phantoms — see the 2026-07-06f handoff). Two rules make it reliable:

  * **f32-lattice truth.** Clip/no-clip is decided by :func:`gap_search.min_f32_clip`, a direct
    enumeration of f32-representable ``new`` positions against a settled f32 ``old`` — Link's
    position is f32 (``cXyz``), so continuous/double-precision "gaps" are meaningless (they
    false-positive). No aliasing, no phantom clips.
  * **Y-aware, edge-distance tri gather.** For each seam we gather every region WALL triangle whose
    XZ *edge* distance to the seam vertex S is < ``GATHER_R`` AND whose Y-span overlaps Link's
    cylinder band ``[Yf-5, Yf+H_max+5]``. Centroid-distance gathering (the old bug) grabbed a corner
    stacked overhead or dropped the seam's own huge triangles; edge-distance + Y-overlap fixes both.

**Seam definition.** A seam is a shared *vertical* edge (two verts at ~equal XZ, differing Y) whose
incident triangles carry ≥2 distinct plane normals — i.e. two non-coplanar vertical walls meeting at
that edge (a convex/concave corner). Coplanar (flat/180°) shared edges are skipped: they are
unclippable (the coplanar quads tile the wall; see ``knowledge/mechanics/seam-clip.md``).

**The hard displacement floor.** ``old`` (= ``pm_old_pos``) is always a settled WallCorrect fixed
point, so it clears both wall cylinders (radius 35) — on the corner bisector that puts it
``wall_r / sin(halfangle)`` from S (``halfangle`` = half the *interior* corner angle). Since ``new``
is on the far side of S, the one-frame displacement can never beat that floor: ~49.3 u for a 90.6°
corner, ~37.6 u for a 137° corner. A more obtuse corner has a lower floor but a narrower f32 gap.

Grounded in decomp: positions f32 (``cXyz``, ``pm_pos``/``pm_old_pos`` = ``cXyz*``, d_bg_s_acch.h);
model = ``tww_sim.core.collision`` (bit-exact ``CrrPos``). Live geometry via ``collision_geo``
(imported by file path — see DOLPHIN_CONTROL.md) + stored planes at ``[cBgW+0x88] + poly*0x18``.
"""
import importlib.util
import math
import os
import struct
import sys

# locate tools/ (dolphin_mem lives there, not in this repo — see the parent speedrunning/CLAUDE.md)
_TOOLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools"))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from tww_sim.core.collision import Tri, Plane, wall_correct
from tww_sim.core.fp import f32 as _f
from harness.collision.gap_search import min_f32_clip, WALL_H, WALL_R

GATHER_R = 60.0        # XZ edge-distance radius for gathering interfering wall tris around a seam
WALL_NY_MAX = 0.03     # |ny| below this == a vertical wall (the seam-clip verticality requirement)


# --------------------------------------------------------------------- pure geometry
def _seg_xz_dist(px, pz, x0, z0, x1, z1):
    dx, dz = x1 - x0, z1 - z0
    l2 = dx * dx + dz * dz
    if l2 < 1e-9:
        return math.hypot(px - x0, pz - z0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (pz - z0) * dz) / l2))
    return math.hypot(px - (x0 + t * dx), pz - (z0 + t * dz))


def _tri_xz_edge_dist(vv, px, pz):
    return min(_seg_xz_dist(px, pz, vv[i][0], vv[i][2], vv[(i + 1) % 3][0], vv[(i + 1) % 3][2])
               for i in range(3))


def interior_angle_deg(nA, nB):
    """Interior corner angle (deg) from two wall face-normals (XZ components)."""
    c = max(-1.0, min(1.0, nA[0] * nB[0] + nA[2] * nB[2]))
    return 180.0 - math.degrees(math.acos(c))


def disp_floor(interior_deg, wall_r=WALL_R):
    """Hard lower bound on the one-frame displacement = ``wall_r / sin(interior/2)`` (settled-old
    cylinder clearance on the bisector). ``inf`` for a ~flat corner."""
    half = math.radians(interior_deg / 2.0)
    return wall_r / math.sin(half) if half > 1e-3 else float("inf")


GROUND_NY_MIN = 0.5    # ny >= this == a ground/floor triangle (matches cBgW ground classify)


def _bary_xz(v0, v1, v2, x, z):
    """XZ-projected barycentric: (inside, interpolated_y) for point (x,z) in triangle v0v1v2. Used
    only for a coarse standable-floor lookup, so plain doubles (not f32) are fine."""
    det = (v1[2] - v2[2]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[2] - v2[2])
    if abs(det) < 1e-9:
        return False, None
    a = ((v1[2] - v2[2]) * (x - v2[0]) + (v2[0] - v1[0]) * (z - v2[2])) / det
    b = ((v2[2] - v0[2]) * (x - v2[0]) + (v0[0] - v2[0]) * (z - v2[2])) / det
    c = 1.0 - a - b
    eps = 1e-3
    if a < -eps or b < -eps or c < -eps:
        return False, None
    return True, a * v0[1] + b * v1[1] + c * v2[1]


def floor_ys_at(region_tris, x, z):
    """All DZB ground-triangle heights under XZ point (x,z), sorted ascending. A seam is only a
    reachable clip if Link can STAND next to it, and standability is a property of the static DZB
    geometry (the ground mesh) — NOT of where Link currently is. Empty list == no floor here."""
    ys = []
    for t in region_tris:
        if t["n"][1] < GROUND_NY_MIN:
            continue
        inside, y = _bary_xz(t["v"][0], t["v"][1], t["v"][2], x, z)
        if inside:
            ys.append(y)
    return sorted(ys)


# Corner walls need NOT store a bit-identical seam vertex (observed 0.09u XZ offset), so CLUSTER
# vertical edges within this XZ tol instead of exact bucketing. See seam-clip-scanner.md "Enumeration".
SEAM_XZ_TOL = 0.5


def enumerate_seams(region_tris, box):
    """Find differing-normal vertical seam corners in ``box`` = (xmin,xmax,ymin,ymax,zmin,zmax).

    ``region_tris`` = list of ``dict(poly, v=[v0,v1,v2], n=(nx,ny,nz))`` (stored plane normal).
    Returns a list of ``dict(S, polys, interior, floor, test_y)`` sorted by ``floor`` (most promising
    first). Vertical wall edges are clustered by XZ proximity (``SEAM_XZ_TOL``, y-span overlap) so a
    corner whose two walls store slightly-offset seam vertices is still paired (see ``SEAM_XZ_TOL``).
    """
    xmin, xmax, ymin, ymax, zmin, zmax = box
    walls = [t for t in region_tris if abs(t["n"][1]) < WALL_NY_MAX]
    # every vertical wall edge as [x, z, ylo, yhi, lo_vertex, tri]
    ve = []
    for t in walls:
        v = t["v"]
        for i in range(3):
            a, b = v[i], v[(i + 1) % 3]
            if abs(a[0] - b[0]) < 0.05 and abs(a[2] - b[2]) < 0.05 and abs(a[1] - b[1]) > 1.0:
                lo = a if a[1] < b[1] else b
                ve.append([lo[0], lo[2], min(a[1], b[1]), max(a[1], b[1]), lo, t])
    # cluster edges within SEAM_XZ_TOL in XZ with overlapping y-span (union-find; O(n) via a grid of
    # cell = tolerance, so a point's SEAM_XZ_TOL neighbourhood is within the 3x3 surrounding cells).
    n = len(ve)
    parent = list(range(n))

    def find(i):
        r = i
        while parent[r] != r:
            r = parent[r]
        while parent[i] != r:
            parent[i], i = r, parent[i]
        return r

    grid = {}
    for i, e in enumerate(ve):
        grid.setdefault((int(math.floor(e[0] / SEAM_XZ_TOL)), int(math.floor(e[1] / SEAM_XZ_TOL))),
                        []).append(i)
    for i, ei in enumerate(ve):
        gx, gz = int(math.floor(ei[0] / SEAM_XZ_TOL)), int(math.floor(ei[1] / SEAM_XZ_TOL))
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for j in grid.get((gx + dx, gz + dz), ()):
                    if j <= i:
                        continue
                    ej = ve[j]
                    if (abs(ei[0] - ej[0]) <= SEAM_XZ_TOL and abs(ei[1] - ej[1]) <= SEAM_XZ_TOL
                            and ei[2] <= ej[3] and ej[2] <= ei[3]):
                        ri, rj = find(i), find(j)
                        if ri != rj:
                            parent[ri] = rj
    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(ve[i])

    seams = []
    for members in clusters.values():
        groups = {}
        for e in members:
            groups.setdefault((round(e[5]["n"][0], 4), round(e[5]["n"][2], 4)), []).append(e[5])
        if len(groups) < 2:
            continue                    # single-normal edge cluster -> flat / free edge, not a corner
        rep = min(members, key=lambda e: e[2])          # deepest edge is the representative seam vert
        S = rep[4]
        ylo = min(e[2] for e in members)
        yhi = max(e[3] for e in members)
        # keep if the corner's vertical span overlaps the region Y (verticality makes the XZ gap
        # height-invariant, so a tall wall based below ymin still clips at a height in-region).
        if not (xmin <= S[0] <= xmax and zmin <= S[2] <= zmax and yhi >= ymin and ylo <= ymax):
            continue
        gk = sorted(groups, key=lambda k: -len(groups[k]))
        interior = interior_angle_deg(groups[gk[0]][0]["n"], groups[gk[1]][0]["n"])
        test_y = min(max(ylo, ymin), ymax)             # edge base if in-region, else the region floor
        seams.append(dict(S=tuple(S), polys=sorted({e[5]["poly"] for e in members}),
                          interior=round(interior, 3), floor=round(disp_floor(interior), 3),
                          test_y=test_y))
    seams.sort(key=lambda s: s["floor"])
    return seams


def _gather(region_tris, S, link_y):
    """Wall Tri objects near S (edge dist < GATHER_R) whose Y-span overlaps the cylinder band."""
    lo, hi = link_y - 5.0, link_y + WALL_H[-1] + 5.0
    out = []
    for t in region_tris:
        if abs(t["n"][1]) >= WALL_NY_MAX:
            continue
        ys = [c[1] for c in t["v"]]
        if max(ys) < lo or min(ys) > hi:
            continue
        if _tri_xz_edge_dist(t["v"], S[0], S[2]) < GATHER_R:
            out.append(t["T"])
    return out


def _bisector(nA, nB):
    return math.atan2(-(nA[0] + nB[0]), -(nA[2] + nB[2]))


def scan_seam(region_tris, seam, link_y=None,
              dir_half_deg=6.0, dir_step_deg=1.0, dist_lo=46.0, dist_hi=54.0, dist_step=0.5,
              box_ulps=45):
    """Empirical MIN one-frame displacement clip for one seam, via the reliable f32-lattice search.
    Sweeps approach direction (bisector ± ``dir_half_deg``) and settled-old distance, and for each
    settled ``old`` runs :func:`min_f32_clip` on an f32 box of ``new`` just past S. Returns
    ``dict(min_disp, old, new, rel_deg, old_dist)`` or ``None`` if the seam has no reachable clip.

    ``link_y`` defaults to the seam vertex Y (the wall base) — the vertical wall makes the XZ gap
    height-invariant, so this is representative; pass Link's real floor Y for a specific setup."""
    S = seam["S"]
    ly = (seam.get("test_y", S[1]) if link_y is None else link_y)
    tris = _gather(region_tris, S, ly)
    # the two seam walls (dominant normals among the incident tris)
    inc = [t for t in region_tris if t["poly"] in seam["polys"]]
    groups = {}
    for t in inc:
        groups.setdefault((round(t["n"][0], 4), round(t["n"][2], 4)), []).append(t)
    gk = sorted(groups, key=lambda k: -len(groups[k]))
    if len(gk) < 2:
        return None
    nA, nB = groups[gk[0]][0]["n"], groups[gk[1]][0]["n"]
    base = _bisector(nA, nB)

    def settle(x, z):
        p = (_f(x), _f(ly), _f(z))
        for _ in range(8):
            p, _ = wall_correct(p, 0.0, tris, WALL_H, WALL_R)
            p = (_f(p[0]), _f(p[1]), _f(p[2]))
        _, hit = wall_correct(p, 0.0, tris, WALL_H, WALL_R)
        return p if not hit else None

    best = None
    nrel = int(2 * dir_half_deg / dir_step_deg) + 1
    ndist = int((dist_hi - dist_lo) / dist_step) + 1
    for ir in range(nrel):
        rel = -dir_half_deg + ir * dir_step_deg
        ang = base + math.radians(rel)
        dx, dz = math.sin(ang), math.cos(ang)
        for idd in range(ndist):
            dist = dist_lo + idd * dist_step
            old = settle(S[0] - dist * dx, S[2] - dist * dz)
            if old is None:
                continue
            new_center = (S[0] + 0.4 * dx, S[2] + 0.4 * dz)
            r = min_f32_clip(tris, old, new_center, ly, box_ulps=box_ulps)
            if r is not None and (best is None or r["disp"] < best["min_disp"]):
                best = dict(min_disp=r["disp"], old=r["old"], new=r["new"],
                            rel_deg=round(rel, 3), old_dist=round(dist, 3))
    return best


# --------------------------------------------------------------------- live reading
def _load_collision_geo():
    ww = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tww-python-scripts", "ww",
                      "collision_geo.py")
    spec = importlib.util.spec_from_file_location("collision_geo", os.path.abspath(ww))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_region_tris(box, expand=GATHER_R + 5.0):
    """Read the static room mesh from a running Dolphin and return the region's wall+near tris as
    ``dict(poly, v, n, T)`` (T = a :class:`Tri` with the STORED plane). Reads geometry via
    ``collision_geo`` and per-triangle planes from ``[cBgW+0x88] + poly*0x18``. Needs Dolphin up
    (target with ``DOLPHIN_PID``); imports ``dolphin_mem`` via the repo/tools bootstrap on sys.path."""
    import dolphin_mem as dm
    cg = _load_collision_geo()
    h, mem1 = dm.attach()

    class _R:
        def read_bytes(self, a, n):
            return dm.read_bytes(h, mem1, a, n)
    rd = _R()

    def u32(a):
        return struct.unpack(">I", rd.read_bytes(a, 4))[0]

    def f32(a):
        return struct.unpack(">f", rd.read_bytes(a, 4))[0]

    snap = cg.read_collision(rd)
    bg = max((b for b, mm in snap["meshes"].items() if mm["is_global"]),
             key=lambda b: snap["meshes"][b]["t_num"])
    m = snap["meshes"][bg]
    bgw = m["bgw"]
    pm_tri = u32(bgw + 0x88)
    verts, tris = m["verts"], m["tris"]
    xmin, xmax, ymin, ymax, zmin, zmax = box
    out = []
    for poly, (a, b, c, tid, grp) in enumerate(tris):
        vv = [verts[a], verts[b], verts[c]]
        # AABB-overlap, NOT vertex-in-box: a large FLOOR tri can span the region with all verts
        # outside it (GanonL floor poly 273) and get dropped, leaving the seam no standable floor.
        txmin = min(v[0] for v in vv); txmax = max(v[0] for v in vv)
        tzmin = min(v[2] for v in vv); tzmax = max(v[2] for v in vv)
        if (txmax < xmin - expand or txmin > xmax + expand
                or tzmax < zmin - expand or tzmin > zmax + expand):
            continue
        if min(v[1] for v in vv) > ymax + WALL_H[-1] + 10:
            continue
        base = pm_tri + poly * 0x18
        n = (f32(base), f32(base + 4), f32(base + 8))
        d = f32(base + 12)
        out.append(dict(poly=poly, v=vv, n=n,
                        T=Tri(vv[0], vv[1], vv[2], plane=Plane(n[0], n[1], n[2], d))))
    return out, snap["stage"]


def dump_region_tris(region, stage, path):
    """Serialise a region (from :func:`read_region_tris`) to JSON so the SCAN can run with no Dolphin
    at all — capture once live, scan/replay offline. Stores raw fields (verts, stored plane), not the
    :class:`Tri` objects."""
    import json
    rows = [dict(poly=t["poly"], v=[list(v) for v in t["v"]], n=list(t["n"]),
                 d=t["T"].pla.d) for t in region]
    with open(path, "w") as f:
        json.dump({"stage": stage, "tris": rows}, f)


def load_region_tris(path):
    """Inverse of :func:`dump_region_tris` — rebuild ``(region_tris, stage)`` from JSON, NO Dolphin."""
    import json
    with open(path) as f:
        data = json.load(f)
    out = []
    for r in data["tris"]:
        vv = [tuple(v) for v in r["v"]]
        n = tuple(r["n"])
        out.append(dict(poly=r["poly"], v=vv, n=n,
                        T=Tri(vv[0], vv[1], vv[2], plane=Plane(n[0], n[1], n[2], r["d"]))))
    return out, data["stage"]


def main(argv):
    box = (-1800.0, 1800.0, -160.0, 160.0, -1100.0, 0.0)   # default: the Hyrule test region
    target = None
    for a in argv:
        if a.startswith("box="):
            box = tuple(float(x) for x in a[4:].split(","))
        elif a.startswith("target="):
            target = float(a[7:])
    region, stage = read_region_tris(box)
    seams = enumerate_seams(region, box)
    print(f"stage={stage} region={box}")
    print(f"{len(seams)} differing-normal vertical seam corners; "
          f"floor = wall_r/sin(interior/2) is the hard displacement lower bound:\n")
    print(f"  {'seam vertex (x,y,z)':<34} {'interior':>9} {'floor':>8}  {'min_disp (f32)':>14}")
    overall = None
    for s in seams:
        r = scan_seam(region, s)
        md = r["min_disp"] if r else None
        tag = ""
        if md is not None:
            if overall is None or md < overall[0]:
                overall = (md, s, r)
            if target is not None and md < target:
                tag = f"  <== < {target}"
        sv = "(%.2f, %.2f, %.2f)" % s["S"]
        print(f"  {sv:<34} {s['interior']:>8.2f}° {s['floor']:>8.3f}  "
              f"{(('%.4f' % md) if md is not None else 'NO CLIP'):>14}{tag}")
    if overall:
        md, s, r = overall
        print(f"\nregional minimum: {md:.4f} u at S={tuple(round(x,3) for x in s['S'])} "
              f"(interior {s['interior']}°, floor {s['floor']})")
        print(f"  old={tuple(round(x,5) for x in r['old'])}  new={tuple(round(x,5) for x in r['new'])}")
        if target is not None:
            print(f"  target < {target}: {'MET' if md < target else 'NOT reachable in this region'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
