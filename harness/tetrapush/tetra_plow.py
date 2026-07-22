"""The Courtyard Tetra-plow LAW -- the per-frame push that herds Tetra, live-derived + decomp-grounded.

Measured live (slot 2, single-stepped, 2026-07-22): on EVERY push frame Tetra's displacement equals
the Co-cylinder overlap depth EXACTLY (frac = tetra_move / depth = 1.000 for 40 consecutive frames,
both cycles), and reconstructing her whole trajectory from Link's per-frame mCyl centre + this law
tracks the live path to <0.005 u over 40 frames. So:

    depth   = (R_link + R_tetra) - dist(link_co_centre, tetra_feet)        [cM3d_Cross_CylCyl cross_len]
    tetra' += depth * unit(tetra_feet - link_co_centre)                    [Tetra absorbs the FULL depth]

Two live facts this encodes (see harness/tetrapush/README.md "The CC split (Courtyard push)"):
  * **Link's body Co centre is the ANIMATED mCyl centre** (daPy_lk_c::setCollision root/neck joint
    midpoint), NOT current.pos -- it leads the feet 6-28 u through the backslide/roll pose. During a
    FRONT_ROLL it is `body_cyl.roll_co_center` (fed the lagged draw base); the MOVE-phase centre is
    animation+morf-driven and not yet modelled offline (the from-f0 blocker). This module takes the
    centre as an argument so it can be fed the RAM ground truth (fixtures/courtyard_push_cyl.json) OR
    a future `move_co_center`.
  * **Tetra takes 100 % of the overlap** (Link's push share is 0). This is the dCcS rank split when
    Link out-ranks Tetra during her stt-3 "being pushed" state (rank_tbl[hi][lo]=0), the opposite of
    the type-5 FOLLOWING Tetra's 50/50 (see [[tetra-push-model]]). NOTE it is Tetra-only: Link's OWN
    per-frame displacement is separately reduced (Lmove + Tmove ~= Link speed) -- a Link-side CC effect
    still to be decomp-grounded (README open puzzle). This module models the Tetra side, which is what
    the planner predicts.

R_link = 30 (daPy_lk_c FRONT_ROLL/walk Co radius), R_tetra = 50, both live-confirmed. Heights only
gate the (always-true on the flat floor) Y-overlap; XZ is what plows. Pure fp (core.cc_push)."""
from tww_sim.core.cc_push import cyl_cyl_cross_len
from tww_sim.core.collision import is_zero, fsqrt
from tww_sim.core.fp import f32, fsubs, fadds, fmuls, fdivs

LINK_CO_R = 30.0
TETRA_CO_R = 50.0
_CO_H = 140.0            # a height that always overlaps on the flat courtyard floor (gate is inert)


def plow_depth(link_center, tetra_xz):
    """The Co-overlap depth (cM3d_Cross_CylCyl cross_len) between Link's body Co cylinder (centre
    ``link_center`` = (x, z) or (x, y, z)) and Tetra's (centre = her feet ``tetra_xz``). 0.0 if no
    overlap. Y is immaterial on the flat floor -- both cylinders are given the same base y."""
    lx = link_center[0]
    lz = link_center[-1]
    tx, tz = tetra_xz[0], tetra_xz[-1]
    hit, cross = cyl_cyl_cross_len((lx, 0.0, lz), LINK_CO_R, _CO_H,
                                   (tx, 0.0, tz), TETRA_CO_R, _CO_H)
    return float(cross) if hit else 0.0


def plow_step(link_center, tetra_xz):
    """One frame of the Tetra plow: return Tetra's new (x, z) after Link's Co cylinder (centred at
    ``link_center``) shoves her the full overlap depth away from Link's centre. If there is no overlap
    (or the centres coincide) she does not move. fp-faithful (matches SetPosCorrect's push line)."""
    lx = link_center[0]
    lz = link_center[-1]
    tx, tz = f32(tetra_xz[0]), f32(tetra_xz[-1])
    depth = plow_depth(link_center, tetra_xz)
    if depth <= 0.0:
        return tx, tz
    dx = fsubs(tx, f32(lx))                     # objsDist = tetra - link (push Tetra AWAY from Link)
    dz = fsubs(tz, f32(lz))
    dist = fsqrt(fadds(fmuls(dx, dx), fmuls(dz, dz)))
    if is_zero(dist):
        return tx, tz
    f = fdivs(f32(depth), dist)                 # pushFactor = cross_len / dist
    return fadds(tx, fmuls(dx, f)), fadds(tz, fmuls(dz, f))


def reconstruct(link_centers, tetra0_xz):
    """Predict Tetra's trajectory from a sequence of Link Co-cylinder centres (one per frame) and her
    start (x, z). Returns the list of (x, z) AFTER each frame's plow -- ``out[i]`` is her position
    once Link's frame-``i`` centre has pushed her (so it aligns with the live capture's frame ``i+1``).
    This is the whole Courtyard herd as a deterministic function of Link's centre path."""
    tx, tz = tetra0_xz[0], tetra0_xz[-1]
    out = []
    for c in link_centers:
        tx, tz = plow_step(c, (tx, tz))
        out.append((tx, tz))
    return out
