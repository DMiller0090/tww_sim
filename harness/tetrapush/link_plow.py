"""Link's OWN push slowdown at the Courtyard -- the MIRROR of the Tetra plow, live-derived.

Session 8 posed "model Link's own push slowdown" as the from-f0 blocker; session 9 measured it. On
EVERY push frame Link's recoil is the **full** Co-cylinder overlap depth, directed AWAY from Tetra
along the centre-to-centre line (`recoil / depth == 1.000`, `recoil.dir == tetra->Link bearing`,
measured off `fixtures/courtyard_push_cyl.json`). So Link and Tetra BOTH eject the full `cross_len`
(total separation 2*depth per frame -- which is why the live Link<->Tetra feet distance OSCILLATES
41-85 u, the chase-and-plow), and Link's net ground move each push frame is his foot term MINUS the
full depth away from Tetra:

    depth  = (R_link + R_tetra) - dist(link_co_centre, tetra_feet)      [cM3d_Cross_CylCyl cross_len]
    link' += depth * unit(link_co_centre - tetra_feet)                  [full-depth recoil, AWAY from Tetra]

This is the exact mirror of `tetra_plow` (which pushes Tetra `depth * unit(tetra - link_centre)`), so
the two together are the coupled Courtyard herd as a function of Link's Co-centre path.

Decomp grounding (`d_cc_s.cpp:180`, `dCcS::SetPosCorrect`): with Link as obj1 his move is
`cross_len * obj2Weight` along `(link - tetra)`. Live the NET `m_cc_move` delivered to Link is the
FULL `cross_len` (measured `obj2Weight == 1.0`) -- the mirror of Tetra's full-depth push. NOTE the
naive single-call rank-5/rank-5 split (Link 120, Tetra `temp=0x8C`=140) is 50/50; live BOTH actors
move the full depth (2x that). The source of the doubling is not yet pinned in the static decomp (the
open puzzle in README "The CC split"); the LAW here is the live-measured NET recoil, DERIVED from the
cyl-cyl geometry (no tuned constant), and it reconstructs Link's whole roll+backslide feet path to
<0.01 u vs live. Distinct from the FOLLOWING-Tetra sandbox (`cc_stepper`/`co_move_pair`, which is a
gated 50/50) -- this being-pushed (stt-3) open-floor split is Courtyard-specific.

Reuses `tetra_plow.plow_depth` (same `cross_len`) + `core.cc_push` fp. Pure stdlib, no Dolphin."""
from tww_sim.core.collision import is_zero, fsqrt
from tww_sim.core.fp import f32, fsubs, fadds, fmuls, fdivs
from harness.tetrapush.tetra_plow import plow_depth, LINK_CO_R, TETRA_CO_R


def recoil(link_center, tetra_xz):
    """Link's per-frame CC recoil ``(dx, dz)``: the FULL Co-overlap depth directed AWAY from Tetra,
    from Link's animated Co centre ``link_center`` (x, z or x, y, z) toward Tetra's feet ``tetra_xz``.
    ``(0.0, 0.0)`` if the cylinders don't overlap (or the centres coincide). This is ADDED to Link's
    foot move (speedF along ``current.angle.y``) each push frame. fp-faithful (the ``SetPosCorrect``
    push line, Link/obj1 side, with the live-measured full share)."""
    lx = f32(link_center[0])
    lz = f32(link_center[-1])
    tx = f32(tetra_xz[0])
    tz = f32(tetra_xz[-1])
    depth = plow_depth(link_center, tetra_xz)
    if depth <= 0.0:
        return f32(0.0), f32(0.0)
    dx = fsubs(lx, tx)                          # objsDist = link - tetra (recoil AWAY from Tetra)
    dz = fsubs(lz, tz)
    dist = fsqrt(fadds(fmuls(dx, dx), fmuls(dz, dz)))
    if is_zero(dist):
        return f32(0.0), f32(0.0)
    ff = fdivs(f32(depth), dist)                # pushFactor = cross_len / dist
    return fmuls(dx, ff), fmuls(dz, ff)


def recoil_step(link_center, tetra_xz, link_feet_xz):
    """Apply the recoil to Link's feet: return his ``(x, z)`` after the full-depth eject away from
    Tetra. ``link_center`` = his Co centre (drives the depth+direction); ``link_feet_xz`` = his
    ``current.pos`` (what the recoil is added to). No overlap -> feet unchanged."""
    fx = f32(link_feet_xz[0])
    fz = f32(link_feet_xz[-1])
    rx, rz = recoil(link_center, tetra_xz)
    return fadds(fx, rx), fadds(fz, rz)
