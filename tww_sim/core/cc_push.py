"""FP-faithful port of TWW's actor-vs-actor "Co" collision push (the cylinder-cylinder shove).

This is the mechanism behind a **Tetra (NPC Zl1) nudge**: when Link's body cylinder overlaps
another actor's Co cylinder, the mass/priority system accumulates a horizontal push into Link's
``mStts.m_cc_move``, which Link consumes on the *next* frame in ``daPy_lk_c::posMove`` (``current.pos
+= *mStts.GetCCMoveP()``) — **before** that frame's own movement (roll/thrust) and **before**
``dBgS_Acch::CrrPos`` (the wall check). So a well-placed Tetra adds a small extra displacement toward
a wall corner on the clip frame, on top of the roll/thrust, which is exactly the lever a seam clip
needs when the roll+thrust displacement alone falls just short of the corner's f32 minimum.

Chain (all decomp-grounded, GZLJ01):
  1. **Overlap depth** — ``cM3d_Cross_CylCyl`` (``c_m3d.cpp:1553``, the ``f32*`` variant):
     two vertical cylinders (center = feet, radius, height). Gate on XZ distance (``dist² > Σr²``)
     and Y overlap (``c1.y+h1 < c2.y  ||  c1.y > c2.y+h2``); depth ``= Σr − √(dx²+dz²)``.
  2. **Push split** — ``cCcS::SetPosCorrect`` (``c_cc_s.cpp:254``), fed each cylinder's Co center
     (``GetCoCP()``) and the depth. A deadzone ``|depth| < 1/125`` skips it. The two actors share
     the depth by weight *type* (``cCcS::GetWt``: ``0xFF→Type0``, ``0xFE→Type1``, else ``Type2``):
     each actor is moved by ``depth × (the OTHER actor's assigned weight)`` along the horizontal
     center-to-center line, away from the partner. Link is moved by ``depth × partner_weight``.
  3. **Consumption** — ``cCcD_Stts::PlusCcMove`` (``c_cc_d.cpp:207``) accumulates it; Link applies it
     next frame in ``posMove`` (``d_a_player_main.cpp:2558``), then clears it (``:2609``).

Weights (GZLJ01): Link ``mStts.SetWeight(120)`` (``d_a_player_main.cpp:11233``) → Type2, mass 120.
Tetra ``daNpc_Zl1_c::createInit`` sets weight ``0xFF`` (Type0, immovable) by default, or ``0x8C``
(140, Type2) for the ``field_0x84F == 5`` variant (``d_a_npc_zl1.cpp:391/428``). **Live-confirmed
(2026-07-06, Hyrule): the Tetra in the flooded-Hyrule scene is the Type2, weight-140 variant**
(read her ``mStts.m_weight`` = 0x8C). So Link takes ``depth × 140/260 ≈ 0.538`` (NOT the full depth
an immovable Type0 would give) and **Tetra recoils** by ``depth × 120/260 ≈ 0.462``. This corrects
the earlier assumption that she was immovable. Re-confirm the live weight for any other scene.

FP note: ``dist²`` is fused (``fmadds(dz,dz, fmuls(dx,dx))``) like ``PSVECMag``; the ``√`` is a plain
``sqrtf``. Push magnitude precision (~1 ULP) is far below the f32 *position* ULP (~2e-4 u at coord
1700) that decides the clip, so a correctly-rounded ``fsqrt`` suffices here (unlike the plane
normalise in :mod:`.collision`, which needs ``frsqrte``). Pure stdlib + ``core.fp``; no Dolphin dep.
"""
from .fp import f32 as _f, fadds, fsubs, fmuls, fdivs, fmadds
from .collision import fsqrt, is_zero

# Weight-type thresholds — cCcS::GetWt (c_cc_s.h:29). 0xFF is immovable.
WEIGHT_LINK = 120          # daPy_lk_c setBgCheckParam SetWeight(120) -> Type2, mass 120
WEIGHT_TETRA_DEFAULT = 0xFF  # daNpc_Zl1_c::createInit default -> Type0 (immovable)
WEIGHT_TETRA_V5 = 0x8C       # 140, field_0x84F==5 variant -> Type2, mass 140

CO_DEADZONE = _f(1.0 / 125.0)   # SetPosCorrect: |cross_len| < 1/125 -> no correction (c_cc_s.cpp:275)


def weight_type(w):
    """cCcS::GetWt (c_cc_s.h:29): 0xFF->0 (immovable), 0xFE->1, else 2 (mass = the value)."""
    if w == 0xFF:
        return 0
    if w == 0xFE:
        return 1
    return 2


def cyl_cyl_cross_len(c1, r1, h1, c2, r2, h2):
    """``cM3d_Cross_CylCyl`` (c_m3d.cpp:1553, the ``f32*`` overlap-depth variant).

    ``c1``/``c2`` = (x, y, z) cylinder centers (at the feet); ``r*``/``h*`` = radius/height.
    Returns ``(hit: bool, cross_len: f32)`` where ``cross_len`` is the overlap depth (``Σr − dist``),
    or ``(False, 0.0)`` if the XZ circles miss or the height ranges don't overlap.
    """
    dx = fsubs(c1[0], c2[0])
    dz = fsubs(c1[2], c2[2])
    dist_sq = fmadds(dz, dz, fmuls(dx, dx))          # dx*dx + dz*dz, fused like PSVECMag
    radius_sum = fadds(r1, r2)
    if dist_sq > fmuls(radius_sum, radius_sum):
        return False, _f(0.0)
    # Y-overlap gate: c1.y + h1 < c2.y  ||  c1.y > c2.y + h2
    if fadds(c1[1], h1) < c2[1] or c1[1] > fadds(c2[1], h2):
        return False, _f(0.0)
    return True, fsubs(radius_sum, fsqrt(dist_sq))


def _split_weights(t1, w1, t2, w2):
    """``cCcS::SetPosCorrect`` weight branch (c_cc_s.cpp:286-325). Returns ``(obj1W, obj2W)`` or
    ``None`` (no correction). ``obj_i`` is moved by ``cross_len × obj_(other)W``. ``t*`` = weight
    type, ``w*`` = raw weight value (used as mass only for the Type2/Type2 case)."""
    src1, src2 = _f(w1), _f(w2)
    combined = fadds(src1, src2)
    if is_zero(combined):
        src1 = src2 = _f(1.0)
        combined = _f(2.0)
    inv = fdivs(_f(1.0), combined)
    if t1 == 0:
        if t2 == 0:
            return None                     # both immovable
        return _f(1.0), _f(0.0)             # obj1 immovable, obj2 takes full
    if t1 == 1:
        if t2 == 0:
            return _f(0.0), _f(1.0)
        if t2 == 1:
            return _f(0.5), _f(0.5)
        return _f(1.0), _f(0.0)             # Type1 immovable vs Type2
    # t1 == 2
    if t2 == 2:
        return fmuls(src1, inv), fmuls(src2, inv)   # mass-proportional
    return _f(0.0), _f(1.0)                 # Type2 moves fully vs Type0/Type1


def co_push_link(link_c, link_r, link_h, other_c, other_r, other_h,
                 link_w=WEIGHT_LINK, other_w=WEIGHT_TETRA_DEFAULT):
    """Link's accumulated ``m_cc_move`` from one Co overlap with ``other`` (e.g. Tetra).

    Ports ``cM3d_Cross_CylCyl`` (overlap depth) + ``cCcS::SetPosCorrect`` (weight split, horizontal
    push away from the partner). ``*_c`` = (x, y, z) Co cylinder centers (feet); ``*_r/*_h`` =
    radius/height; ``*_w`` = raw weight value. Returns the ``(dx, dy, dz)`` push that Link's next
    ``posMove`` adds to ``current.pos`` (``dy = 0`` — the cylinder path is horizontal, ``correctY``
    is false for two cylinders). ``(0, 0, 0)`` if no overlap or inside the deadzone.

    Link is treated as obj1 (WLOG — the split is symmetric under obj1/obj2 swap, and Link's push
    always uses the partner's weight). ``dist`` is recomputed from the Co centers exactly as
    ``SetPosCorrect`` does.
    """
    hit, cross_len = cyl_cyl_cross_len(link_c, link_r, link_h, other_c, other_r, other_h)
    if not hit:
        return _f(0.0), _f(0.0), _f(0.0)
    if abs(cross_len) < CO_DEADZONE:            # fabsf(cross_len) < 1/125
        return _f(0.0), _f(0.0), _f(0.0)

    weights = _split_weights(weight_type(link_w), link_w, weight_type(other_w), other_w)
    if weights is None:
        return _f(0.0), _f(0.0), _f(0.0)
    obj1W, obj2W = weights                       # Link = obj1; Link moves by cross_len * obj2W

    # SetPosCorrect (!correctY): objsDist = pos2 - pos1 = other - link (XZ); scale to cross_len;
    # vec1 (Link) = -objsDist * obj2W  ==  (link - other) direction, magnitude cross_len*obj2W.
    dx = fsubs(other_c[0], link_c[0])
    dz = fsubs(other_c[2], link_c[2])
    dist = fsqrt(fmadds(dz, dz, fmuls(dx, dx)))
    if not is_zero(dist):
        f = fdivs(cross_len, dist)               # pushFactor = cross_len / objDistLen
        return fmuls(fmuls(dx, f), fsubs(_f(0.0), obj2W)), _f(0.0), fmuls(fmuls(dz, f), fsubs(_f(0.0), obj2W))
    # degenerate: centers coincident -> push along +x by cross_len (or unit)
    mag = cross_len if not is_zero(cross_len) else _f(1.0)
    return fmuls(fsubs(_f(0.0), mag), obj2W), _f(0.0), _f(0.0)
