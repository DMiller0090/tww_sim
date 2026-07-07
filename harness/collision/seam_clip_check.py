"""Out-of-the-box seam-clip checker: given a REGION (or a single seam), answer "is there a
clippable seam here, and what are the EXACT coordinates that perform the clip?" — accurately, with
NO parameters to get wrong, and fast (region scans complete in seconds, not minutes).

Scope (per the user's redirect): we do **not** compute the minimum-displacement clip for a seam
(that is :func:`gap_search.min_f32_clip`, an O(box²) lattice sweep). We only need to know a clip
**exists** and hand back one exact, physically valid ``(old, new)`` pair that performs it.

Hard requirements enforced here (all decided from the static DZB geometry — NOT from where Link
currently is, so the scan is Dolphin-free and its region is independent of Link):

  * **Existence, not minimum.** :func:`gap_search.find_clip` (continuous, f32-snapped) is the
    trustworthy screen: if it finds no continuous gap along the corner, no f32 clip exists → NO CLIP.
    When it does, we ring-search the f32 lattice out from the gap centre (:func:`first_f32_clip`) and
    return the FIRST clipping ``new`` — early-exit, no full-box enumeration.
  * **Standable, physically valid ``old``.** The returned initial position must be somewhere Link can
    actually stand: a DZB **ground** triangle under its XZ (:func:`seam_scan.floor_ys_at` — not Link's
    Y, not the wall base), the wall must reach that floor height, and ``old`` must be a WallCorrect
    fixed point against the FULL near-wall set (not embedded in / pushed out of any surrounding wall)
    and in front of both incident walls. ``require_standable=False`` (or ``override_link_y=``) skips
    the floor requirement for synthetic geometry (e.g. the self-test).

Self-test (reproduces the known GanonL grand-staircase clip, no hand params):
    python -m harness.collision.seam_clip_check --selftest
Region scan (live from a running Dolphin; needs the stage loaded):
    python -m harness.collision.seam_clip_check box=xmin,xmax,ymin,ymax,zmin,zmax
Offline replay of a captured region (no Dolphin):
    python -m harness.collision.seam_clip_check cache=region.json box=...
"""
import math
import sys

from tww_sim.core.collision import wall_correct
from harness.collision.gap_search import (find_clip, first_f32_clip, settle, bisector_dir,
                                          WALL_H, WALL_R)
from harness.collision.seam_scan import (enumerate_seams, interior_angle_deg, disp_floor, _gather,
                                         floor_ys_at, read_region_tris, load_region_tris,
                                         GROUND_NY_MIN, WALL_NY_MAX)

ROLL_STAB_MAX = 49.2202     # max single-frame roll-stab lunge (roll speedF 26 + CUT root 23.22)


def _wall_yspan(*walls):
    ys = [v[1] for w in walls for v in (w.v0, w.v1, w.v2)]
    return (min(ys), max(ys)) if ys else (None, None)


# find_clip LineCheck-miss SCREEN params (necessary geometry-aware test; narrow offset = cheap).
# Why the screen (not the within-wall fan) decides clippability: knowledge/mechanics/seam-clip.md.
SCREEN_OFF_HALF, SCREEN_OFF_STEP, SCREEN_DIR_HALF, SCREEN_DIR_STEP = 0.0005, 2e-5, 30.0, 1.0

# f32-lattice search (screen-passers only): ``new`` box half-width BOX_WORLD (world u → ULPs, cap
# BOX_ULP_MAX); FWD_TFS forward centres; DIR_*/OLD_SPAN sweep; SEAM_F32_BUDGET caps CrrPos/seam.
BOX_WORLD, BOX_ULP_MAX = 0.08, 300
FWD_TFS = (0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.05)
DIR_HALF, DIR_STEP, OLD_SPAN = 12.0, 2.0, 6.0
SEAM_F32_BUDGET = 250_000


def _floor_at(ground_tris, x, z, yspan):
    """Top-most ground height under (x,z) that lies within the wall's vertical span ``yspan``
    (so the seam wall actually reaches the floor Link would stand on). None if no such floor."""
    ylo, yhi = yspan
    cands = [y for y in floor_ys_at(ground_tris, x, z)
             if ylo is None or (ylo - 2.0 <= y <= yhi + 2.0)]
    return max(cands) if cands else None


def _valid_initial(trilist, ground_tris, p, wallA, wallB, yspan, require_standable):
    """Is ``p=(x,y,z)`` a physically valid initial position? Not embedded in any wall (a WallCorrect
    fixed point against the full near-wall set), in front of both incident walls, and — when
    ``require_standable`` — standing on a DZB ground triangle at its feet (not in the air)."""
    q, hit = wall_correct(p, 0.0, trilist, WALL_H, WALL_R)
    if hit or ((q[0] - p[0]) ** 2 + (q[2] - p[2]) ** 2) ** 0.5 > 1e-3:
        return False                                   # inside / pushed out of a wall
    if wallA.pla.func(p) <= 0 or wallB.pla.func(p) <= 0:
        return False                                   # behind a wall, not on the approach side
    if not require_standable:
        return True
    return _floor_at(ground_tris, p[0], p[2], yspan) is not None


def clip_check(barrier_tris, ground_tris, S, wallA, wallB,
               require_standable=True, override_link_y=None, roll_stab=ROLL_STAB_MAX):
    """Decide whether a single seam clips and, if so, return the exact coords that perform it.

    ``barrier_tris`` = ALL near wall :class:`Tri` (the CrrPos barrier set); ``ground_tris`` = the
    region's ground-triangle dicts (for the standable-floor lookup); ``S`` = seam vertex (x,z);
    ``wallA``/``wallB`` = the two incident wall Tri (their planes give the bisector).

    Returns ``dict(clips, old, new, link_y, interior, floor, disp, standable, reachable_rollstab,
    needs_push, reason)``. ``old``/``new`` are full (x,y,z) world coords; ``reachable_rollstab`` =
    the found clip's displacement ``<= roll_stab`` (a bare roll-stab reaches it; else a Tetra push
    is needed). We sweep the settled-old distance from the cylinder floor upward and stop at the
    first standable f32 clip, so ``disp`` is near-minimal (existence + performable coords, NOT the
    exact minimum)."""
    interior = interior_angle_deg((wallA.pla.nx, 0.0, wallA.pla.nz),
                                  (wallB.pla.nx, 0.0, wallB.pla.nz))
    floor = disp_floor(interior)
    yspan = _wall_yspan(wallA, wallB)

    def nore(reason):
        return dict(clips=False, old=None, new=None, link_y=override_link_y,
                    interior=round(interior, 3), floor=round(floor, 3), disp=None,
                    standable=None, needs_push=None, reachable_rollstab=False, reason=reason)

    if not math.isfinite(floor):
        return nore("flat corner (interior ~180) — unclippable")

    base = bisector_dir([wallA, wallA, wallB])          # front->back travel dir (into the wall)

    # link_y = the standable floor height under the corner approach (NOT the wall base / Link's Y).
    if override_link_y is not None:
        link_y = override_link_y
    else:
        bx, bz = math.sin(base), math.cos(base)
        link_y = _floor_at(ground_tris, S[0] - floor * bx, S[1] - floor * bz, yspan)
        if link_y is None:
            return nore("no standable floor next to the seam at the wall's height")

    trilist = [wallA, wallA, wallB] + list(barrier_tris)

    # SCREEN: does the swept line ever miss LineCheck near this corner? (necessary; geometry-aware —
    # see SCREEN_* above.) Cheap; rejects unclippable seams before the heavier f32 search.
    screened, _ = find_clip(trilist, S, link_y, D=min(floor + 8.0, 54.0),
                            dir_half_deg=SCREEN_DIR_HALF, dir_step_deg=SCREEN_DIR_STEP,
                            off_half=SCREEN_OFF_HALF, off_step=SCREEN_OFF_STEP, physical=False)
    if not screened:
        return nore("no LineCheck miss along the corner — unclippable geometry")

    # f32 ``new`` box = fixed world window (±BOX_WORLD u) -> ULPs (grows near origin). Positives
    # early-exit in the first rings; detection must NOT be ULP-coarsened (see seam-clip.md).
    ulp = max(abs(S[0]), abs(S[1]), 1.0) * 2 ** -23
    box_ulps = max(24, min(BOX_ULP_MAX, int(BOX_WORLD / ulp)))

    # Sweep direction (bisector-out), settled-old distance (floor up), forward ``new``; first standable
    # f32 clip wins (near-minimal, performable). budget bounds a screen-passer with no f32 clip.
    budget = SEAM_F32_BUDGET
    rels = [0.0]
    r = DIR_STEP
    while r <= DIR_HALF:
        rels += [r, -r]
        r += DIR_STEP
    for rel in rels:
        ang = base + math.radians(rel)
        dx, dz = math.sin(ang), math.cos(ang)
        d = floor
        while d <= floor + OLD_SPAN:
            ox, oz = S[0] - d * dx, S[1] - d * dz
            ly = override_link_y if override_link_y is not None else \
                _floor_at(ground_tris, ox, oz, yspan)
            if ly is not None:
                old = settle(trilist, (ox, oz), ly)
                if _valid_initial(trilist, ground_tris, old, wallA, wallB, yspan, require_standable):
                    for tf in FWD_TFS:
                        hit, used = first_f32_clip(trilist, old, (S[0] + tf * dx, S[1] + tf * dz),
                                                   ly, box_ulps=box_ulps, max_calls=budget)
                        budget -= used
                        if hit is not None:
                            new = (hit["new"][0], ly, hit["new"][1])
                            disp = ((new[0] - old[0]) ** 2 + (new[2] - old[2]) ** 2) ** 0.5
                            return dict(clips=True, old=old, new=new, link_y=ly,
                                        interior=round(interior, 3), floor=round(floor, 3),
                                        disp=round(disp, 4), standable=(require_standable or None),
                                        needs_push=disp > roll_stab,
                                        reachable_rollstab=disp <= roll_stab, reason="clip")
                        if budget <= 0:
                            return nore("screen passed but no reachable f32 clip within budget "
                                        "(sub-ULP gap — unclippable in practice)")
            d += 0.5
    return nore("no standable f32-representable clip (sub-ULP gap or no standable approach floor)")


def _seam_walls(region_tris, seam):
    """The two incident wall Tri (one representative per distinct wall normal) meeting at the seam,
    by VERTEX-incidence (every wall tri with a vertex at the seam XZ). None if fewer than two
    distinct-normal walls meet here. Their planes give the corner bisector."""
    sx, sz = seam["S"][0], seam["S"][2]
    inc = [t for t in region_tris if abs(t["n"][1]) < WALL_NY_MAX
           and any(abs(v[0] - sx) < 0.1 and abs(v[2] - sz) < 0.1 for v in t["v"])]
    groups = {}
    for t in inc:
        groups.setdefault((round(t["n"][0], 4), round(t["n"][2], 4)), []).append(t)
    gk = sorted(groups, key=lambda k: -len(groups[k]))
    if len(gk) < 2:
        return None
    return groups[gk[0]][0]["T"], groups[gk[1]][0]["T"]


def scan_region(region_tris, box, require_standable=True, override_link_y=None, verbose=True):
    """Answer "are there clippable seams in this region?" Enumerate every differing-normal vertical
    seam in ``box`` and run :func:`clip_check` on each. Returns the clippable-seam result dicts (each
    with the seam ``S``), sorted by displacement. Pure geometry — no Dolphin (``region_tris`` may be
    live from :func:`seam_scan.read_region_tris` or offline from :func:`seam_scan.load_region_tris`).
    ``require_standable`` (default) drops seams with no standable floor next to them; set it False (or
    pass ``override_link_y``) to include them anyway."""
    ground = [t for t in region_tris if t["n"][1] >= GROUND_NY_MIN]
    seams = enumerate_seams(region_tris, box)
    if verbose:
        print("%d differing-normal vertical seams in region (%d ground tris)"
              % (len(seams), len(ground)), flush=True)
    clippable = []
    for i, seam in enumerate(seams):
        walls = _seam_walls(region_tris, seam)
        if walls is None:
            continue
        wallA, wallB = walls
        S = (seam["S"][0], seam["S"][2])
        # gather at the standable floor height (fall back to the seam base if no floor)
        gy = _floor_at(ground, S[0], S[1], _wall_yspan(wallA, wallB))
        barrier = _gather(region_tris, seam["S"], gy if gy is not None else seam["S"][1])
        res = clip_check(barrier, ground, S, wallA, wallB,
                         require_standable=require_standable, override_link_y=override_link_y)
        if res["clips"]:
            res["S"] = seam["S"]
            clippable.append(res)
            if verbose:
                print("  CLIP S=(%.1f,%.1f,%.1f) interior=%.2f disp=%.4f %s"
                      % (seam["S"][0], seam["S"][1], seam["S"][2], res["interior"], res["disp"],
                         "ROLL-STAB reachable" if res["reachable_rollstab"] else "needs push"),
                      flush=True)
        if verbose and (i + 1) % 25 == 0:
            print("  ...%d/%d seams scanned, %d clippable" % (i + 1, len(seams), len(clippable)),
                  flush=True)
    clippable.sort(key=lambda r: r["disp"])
    if verbose:
        print("=== %d clippable of %d seams ===" % (len(clippable), len(seams)), flush=True)
    return clippable


def _selftest():
    """Reproduce the known GanonL grand-staircase clip with ZERO hand-set params (synthetic geometry
    from seam_model — no ground mesh, so override the floor Y and skip the standable requirement)."""
    from harness.collision.seam_model import SEAM_TRIS, LINK_Y
    S = (-847.632, -37336.613)
    print("GanonL self-test: seam S=%s (known clip)" % (S,), flush=True)
    res = clip_check(SEAM_TRIS, [], S, SEAM_TRIS[1], SEAM_TRIS[2],
                     require_standable=False, override_link_y=LINK_Y)
    print("  RESULT clips=%s disp=%s reachable_rollstab=%s needs_push=%s (interior %.2f, floor %.2f)"
          % (res["clips"], None if res["disp"] is None else round(res["disp"], 4),
             res["reachable_rollstab"], res["needs_push"], res["interior"], res["floor"]), flush=True)
    if res["clips"]:
        print("  old=%s\n  new=%s" % (tuple(round(c, 4) for c in res["old"]),
                                      tuple(round(c, 4) for c in res["new"])), flush=True)
    assert res["clips"], "SELF-TEST FAILED: scanner did not find the known GanonL clip"
    print("  SELF-TEST PASSED", flush=True)


def main(argv):
    if "--selftest" in argv:
        _selftest()
        return 0
    box = cache = None
    require_standable = "no-standable" not in argv
    for a in argv:
        if a.startswith("box="):
            box = tuple(float(x) for x in a[4:].split(","))
        elif a.startswith("cache="):
            cache = a[6:]
    if box is None:
        print("usage: python -m harness.collision.seam_clip_check --selftest"
              " | box=xmin,xmax,ymin,ymax,zmin,zmax [cache=region.json] [no-standable]")
        return 2
    if cache:
        region, stage = load_region_tris(cache)
    else:
        region, stage = read_region_tris(box)
    print("stage=%s region tris=%d" % (stage, len(region)), flush=True)
    scan_region(region, box, require_standable=require_standable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
