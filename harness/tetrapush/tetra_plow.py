"""The Courtyard Co-overlap GEOMETRY -- the cylinder-cylinder push depth + the Link/Tetra radii.

This module owns the shared `cM3d_Cross_CylCyl` overlap-depth primitive (`plow_depth`) and the two
Co radii for the Courtyard push pair. The per-frame PUSH LAW itself lives in
`from_f0.cc_push_pair` (`cc_push.co_move_pair` on Link's EXEC centre -- the decomp 50/50 rank split,
0-ULP vs the deterministic per-op ΔTetra f2..f43; session 27).

The retired derived law (session 8-26; git history is the archive): the earlier `plow_step` /
`reconstruct` shoved Tetra the FULL overlap depth away from Link's animated mCyl centre. Measured
against the SETTLED (pause-boundary) centre it read as frac == tetra_move / depth == 1.000 for 40
consecutive frames (the discriminator `tests/test_tetra_plow.py::test_tetra_absorbs_full_overlap`
still guards that this is the full ejection, not a 50/50 split). But full-depth-from-settled is only
numerically ~1e-5 u equal to the console's half-depth-from-EXEC split (`co_move_pair`), so it was
1-9 ULP off the deterministic ΔTetra -- session-24's "bug #1". The bit-exact law is `cc_push_pair`
on the exec centre; the settled-centre form survives only as the seed-frame (f0->f1) fallback in
`from_f0.full_depth_push` (f0's exec centre is not offline-reconstructable). See
harness/tetrapush/README.md "The CC split (Courtyard push)".

R_link = 30 (daPy_lk_c FRONT_ROLL/walk Co radius), R_tetra = 50, both live-confirmed. Heights only
gate the (always-true on the flat floor) Y-overlap; XZ is what plows. Pure fp (core.cc_push)."""
from tww_sim.core.cc_push import cyl_cyl_cross_len

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
