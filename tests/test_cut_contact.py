"""**THE CUT FRAME'S FREE VARIABLE IS TETRA, NOT THE ENTRY** (`harness.tetrapush.cut_contact`, s157).

Session 156 handed the next session a prefilter recipe -- predict contact from ``entry + sum(dx, dz)``
and prune the 97% of evaluations that are out of contact at the cut. These gates pin what measuring it
found instead:

  * the arithmetic free path is NOT the roll (the wall corrects it), so a contact test built on it keeps
    none of the rows that are really in contact -- the recipe's own premise, refuted;
  * inside the reachable entry box an untouched roll has no freedom left: ``old``, the Co centre,
    ``new`` and the residual come back BIT-IDENTICAL over the whole box, and the invariance is a
    property of that box (at radius 150 u the same probe returns many);
  * so the razor is a function of one 2-D variable, where Tetra stands on the contact frame, and
    `cut_slice` reads it off the native sim at any entry, entry-invariantly;
  * the ring `target_ring` finds on s154's accepted-101 bearing lands 0.046 u from where the console's
    own herd actually left her -- an AIM, not a plan, which is what the pinned ``old`` can support;
  * `zero_bearing` refuses a residual JUMP as a crossing (a blind bisection across the band returns one,
    at ``resid`` +20).

Offline: the native `ShoveCtx` through `entry_search.build_fast` (no Dolphin). Every number is a
MEASUREMENT of deterministic offline code, so it is pinned exactly.
"""
import math
import struct

import pytest

from harness.tetrapush import cut_contact as CC
from harness.tetrapush import entry_search as ES
from tww_sim.core.fp import f32, fadds

# s154's accepted 101 -- genuine, confirmed, deliverable. Inlined rather than read from the gitignored
# `_notes/` run that produced it (same constants as `tests/test_entry_dust.py`).
FACING, LEAN, THRUST = 40727, 104, 15
TETRA = (-1654.9884033203125, -923.457763671875)
ENTRY = (-1591.7647705078125, -848.5638427734375)
WALK = (-1573.807861328125, -829.7609252929688)
#: where the console's herd left her ON THE CONTACT FRAME, and its polar form off the braced Co centre
HER_CUT = (-1621.0395507812500, -939.8941040039062)
HER_BEARING, HER_DIST = 13903, 76.78111


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


@pytest.fixture(scope='module')
def built():
    ctx, sch, resid = ES.build_fast(FACING, LEAN, THRUST)
    br = CC.braced_row(FACING, LEAN, THRUST, ctx=ctx, sch=sch, resid=resid)
    return ctx, sch, resid, br


# --------------------------------------------------------- the recipe s156 proposed, refuted

def test_the_arithmetic_free_path_is_not_the_roll(built):
    """s156's prefilter premise. ``entry + sum(dx, dz)`` ignores the wall correction, so it puts Link
    hundreds of u past where the roll actually ends -- and a contact test on it is not conservative,
    it is simply wrong."""
    ctx, sch, resid, br = built
    lx, lz = f32(ENTRY[0]), f32(ENTRY[1])
    for k in range(sch['cut_step']):                     # steps 0 .. cut_step-1, the contact step
        lx = fadds(lx, sch['dx'][k])
        lz = fadds(lz, sch['dz'][k])
    assert math.hypot(lx - br['old'][0], lz - br['old'][1]) > 150.0


# ------------------------------------------------- the brace pins the whole cut frame, bit-exactly

def test_the_untouched_roll_is_one_row_over_the_whole_reachable_entry_box(built):
    """THE FINDING THE MODULE STANDS ON. Every entry a plan can reach drives the roll into the same
    wall, and the wall absorbs the difference -- one distinct ``old``, Co centre, ``new`` and residual
    for the whole box, counted on BIT PATTERNS."""
    inv = CC.braced_invariance(FACING, LEAN, THRUST, ENTRY, n=13)
    assert inv['entries'] == 169 and inv['radius'] == ES.reach_radius()
    assert (inv['distinct_old'], inv['distinct_co'], inv['distinct_new'],
            inv['distinct_resid']) == (1, 1, 1, 1)
    assert inv['invariant'] and inv['genuine'] == 0


def test_the_invariance_is_the_boxs_and_the_probe_says_so_outside_it(built):
    """The claim is about the REACHABLE box, not about the arithmetic: four times that radius and the
    roll no longer reaches the wall from every corner, so the rows differ. A gate that did not measure
    this would be pinning a coincidence."""
    inv = CC.braced_invariance(FACING, LEAN, THRUST, ENTRY, radius=400.0, n=13)
    assert not inv['invariant']
    assert inv['distinct_old'] > 20


def test_the_braced_row_is_what_a_far_tetra_returns_and_it_does_not_clip(built):
    """The bare roll-stab at this seam: out of contact the residual is a fixed -0.861 and nothing
    crosses. This is the row every out-of-contact candidate of the configuration gets."""
    ctx, sch, resid, br = built
    assert br['genuine'] is False
    assert br['resid'] == pytest.approx(-0.8609402, abs=1e-6)
    assert br['push'] == (0.0, 0.0)
    assert br['overlap'] < -1000.0                       # she is parked out of the courtyard
    off = CC.braced_row(FACING, LEAN, THRUST, ctx=ctx, sch=sch, resid=resid,
                        entry=(ENTRY[0] + 40.0, ENTRY[1] - 30.0))
    assert (_bits(off['old'][0]), _bits(off['old'][1])) == (_bits(br['old'][0]),
                                                            _bits(br['old'][1]))


# --------------------------------------------- the razor as a function of where she stands

def test_placing_her_on_the_contact_step_reproduces_the_delivered_push(built):
    """`cut_slice` pins ``old`` at the brace and varies only Tetra. Handed the position the console's
    own herd left her in, it reproduces that row's push to 1.5e-03 and its residual to 1e-02 -- the
    ``old`` wobble (0.0127 u, an earlier frame's push) is the whole difference, and it is why a ring
    point is an aim rather than a plan."""
    ctx, sch, resid, br = built
    real = ctx.sweep_par([(TETRA[0], TETRA[1], ENTRY[0], ENTRY[1])], 0, extra=True)[0]
    assert bool(real[0]) and (real[12], real[13]) == HER_CUT
    sl = CC.cut_slice(FACING, LEAN, THRUST, [HER_CUT], ctx=ctx, sch=sch, resid=resid)[0]
    assert math.hypot(sl['push'][0] - real[5], sl['push'][1] - real[6]) < 2e-3
    assert abs(sl['resid'] - resid(real)) < 1.1e-2
    assert math.hypot(real[1] - br['old'][0], real[2] - br['old'][1]) == pytest.approx(0.012696,
                                                                                       abs=1e-5)


def test_the_slice_is_the_same_from_any_entry_in_the_box(built):
    """The slice inherits the brace's invariance, which is what lets one map serve a whole fan: the
    same placement from two entries 50 u apart returns bit-identical push, residual and verdict."""
    ctx, sch, resid, br = built
    a = CC.cut_slice(FACING, LEAN, THRUST, [HER_CUT], ctx=ctx, sch=sch, resid=resid)[0]
    b = CC.cut_slice(FACING, LEAN, THRUST, [HER_CUT], ctx=ctx, sch=sch, resid=resid,
                     entry=(ENTRY[0] + 30.0, ENTRY[1] + 40.0))[0]
    assert (_bits(a['push'][0]), _bits(a['push'][1])) == (_bits(b['push'][0]), _bits(b['push'][1]))
    assert _bits(a['resid']) == _bits(b['resid']) and a['genuine'] == b['genuine']


def test_the_ring_on_her_own_bearing_lands_where_the_console_left_her(built):
    """THE AIM, priced against the only known-good answer: on the bearing the console's herd used, the
    residual's outermost zero sits 0.046 u from where she actually stood. The aim is good to ~5e-02 u
    and the razor is 1e-04 wide, so a ring point says WHERE TO PUT HER and never that a plan clips."""
    ctx, sch, resid, br = built
    bear = int(round(math.atan2(HER_CUT[0] - br['co'][0],
                                HER_CUT[1] - br['co'][1]) / (2 * math.pi) * 65536)) & 0xFFFF
    assert bear == HER_BEARING
    assert math.hypot(HER_CUT[0] - br['co'][0],
                      HER_CUT[1] - br['co'][1]) == pytest.approx(HER_DIST, abs=1e-4)
    z = CC.zero_bearing(FACING, LEAN, THRUST, bear, ctx=ctx, sch=sch, resid=resid, braced=br)
    assert z['bracketed'] and abs(z['resid']) < CC.JUMP_RESID
    assert z['dist'] == pytest.approx(76.73543, abs=1e-4)
    assert abs(z['dist'] - HER_DIST) < 0.05


def test_a_residual_jump_is_not_reported_as_a_crossing(built):
    """Deep inside the overlap the residual STEPS, so a sign change there is a discontinuity and not a
    target -- a blind bisection across the whole band converged on one and called it dist 34.93 at
    ``resid`` +20.5. The scan-then-refine form rejects it on its own residual."""
    ctx, sch, resid, br = built
    z = CC.zero_bearing(FACING, LEAN, THRUST, 36864, ctx=ctx, sch=sch, resid=resid, braced=br)
    assert all(abs(c['resid']) <= CC.JUMP_RESID for c in z['crossings'])
    assert z['dist'] is None or abs(z['dist'] - 34.931) > 0.5


def test_the_ring_is_mostly_a_grazing_contact_and_says_where_it_is_not(built):
    """Where the ring lives, measured rather than assumed: at 16 bearings, 6 bracket a zero at all, and
    5 of those 6 sit within a few u of the contact edge -- the regime the brace absorbs, and where the
    console's own +1.2259 (`overnight.CLIP_TARGET`) is. The sixth is a DEEP crossing at 54 u of overlap,
    kept because it is a real zero of the residual and not a jump; a caller that wants the grazing ring
    reads ``overlap``."""
    ctx, sch, resid, br = built
    ring = CC.target_ring(FACING, LEAN, THRUST, step=4096, ctx=ctx, sch=sch, resid=resid, braced=br)
    tops = [p['crossings'][0] for p in ring['points']]
    assert (ring['bearings'], len(tops)) == (16, 6)
    assert all(c['overlap'] > 0.0 and abs(c['resid']) <= CC.JUMP_RESID for c in tops)
    grazing = [c for c in tops if c['overlap'] < 5.0]
    assert len(grazing) == 5
    deep = [c for c in tops if c['overlap'] >= 5.0]
    assert len(deep) == 1 and deep[0]['overlap'] == pytest.approx(54.30, abs=0.01)
