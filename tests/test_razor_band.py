"""**THE RAZOR IS A POSITIVE RESIDUAL INTERVAL THAT EXCLUDES ZERO** (`harness.tetrapush.razor_band`, s158).

Every zero-seeking instrument in this work -- the sweep's ``best_resid_in_contact``, `entry_dust`'s march,
`cut_contact.target_ring`, s157's ``gap`` -- prices a herd by its distance to ``resid = 0``. These gates
pin what full-fidelity measurement says instead, on BOTH rows that are known to clip:

  * the console's own delivered clip and s154's accepted 101 each sit inside their OWN configuration's
    genuine interval, and neither interval contains zero;
  * inside an interval ``resid`` is SUFFICIENT -- every row whose residual lands there is genuine;
  * the two intervals are DIFFERENT, so the band is per-configuration and may not be hard-coded;
  * `cut_contact.cut_slice`'s ``genuine`` is a FALSE NEGATIVE on the delivered placement, which is why
    the band has to be read at full fidelity and the slice stays an aim.

Offline: the native `ShoveCtx` through `entry_search.build_fast` (no Dolphin). Every number is a
measurement of deterministic offline code, so it is pinned exactly.
"""
import struct

import pytest

from harness.tetrapush import cut_contact as CC
from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_band as RB

#: s154's accepted 101 -- genuine, confirmed, deliverable (`tests/test_cut_contact.py`'s constants).
A_FACING, A_LEAN, A_THRUST = 40727, 104, 15
A_TETRA = (-1654.9884033203125, -923.457763671875)
A_ENTRY = (-1591.7647705078125, -848.5638427734375)
A_RESID = 0.0001966530830767074

#: The CONSOLE's own clip off the locked fixture: herd 78, walk 4, cell 2552. Its ``m351C`` is ALREADY
#: the roll lean -- `lean_at_roll` on it again gives 65032 and a row 8.8e-02 off the fixture.
C_FACING, C_LEAN, C_THRUST = 40841, 64761, 15
C_TETRA = (-1629.101806640625, -893.7962036132812)
C_ENTRY = (-1531.178466796875, -781.7215576171875)
C_RESID = 6.24293879321751e-05


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def _row(facing, lean, thrust, entry, tetra):
    ctx, _sch, resid = ES.build_fast(facing, lean, thrust)
    o = ctx.sweep_par([(tetra[0], tetra[1], entry[0], entry[1])], 0, extra=True)[0]
    return bool(o[0]), resid(o)


@pytest.fixture(scope='module')
def accepted_band():
    return RB.genuine_band(A_FACING, A_LEAN, A_THRUST, A_ENTRY, A_TETRA)


@pytest.fixture(scope='module')
def console_band():
    return RB.genuine_band(C_FACING, C_LEAN, C_THRUST, C_ENTRY, C_TETRA)


# ------------------------------------------------------------------ the two controls reproduce

def test_both_known_clips_reproduce_their_own_residual_bit_exactly():
    """The instrument is only worth its output if it reproduces the rows that DID clip. Both do, at
    full fidelity and 0-ULP against their recorded residual -- the console's off the locked fixture."""
    ga, ra = _row(A_FACING, A_LEAN, A_THRUST, A_ENTRY, A_TETRA)
    gc, rc = _row(C_FACING, C_LEAN, C_THRUST, C_ENTRY, C_TETRA)
    assert ga and gc
    assert _bits(ra) == _bits(A_RESID) and _bits(rc) == _bits(C_RESID)


def test_each_clip_sits_inside_its_own_measured_band(accepted_band, console_band):
    """THE FINDING. Each delivered row's residual lands inside the interval its own configuration's
    genuine placements span -- so the band is where the clips are, and it is found without being told
    where to look."""
    assert RB.in_band(accepted_band, A_RESID)
    assert RB.in_band(console_band, C_RESID)
    assert accepted_band['genuine'] > 100 and console_band['genuine'] > 50


def test_neither_band_contains_zero_which_is_where_every_tool_aims(accepted_band, console_band):
    """The headline, and the reason a barren sweep can report ``|resid| = 3e-06`` beside 0 genuine:
    ``resid = 0`` is refused at both configurations, and it is the target every existing instrument
    marches toward."""
    assert RB.zero_is_outside(accepted_band) and RB.zero_is_outside(console_band)
    assert accepted_band['lo'] > 0.0 and console_band['lo'] > 0.0
    assert accepted_band['lo'] == pytest.approx(1.627852e-04, abs=1e-9)
    assert console_band['lo'] == pytest.approx(5.795767e-05, abs=1e-9)


def test_inside_the_band_the_residual_is_sufficient_not_merely_necessary(accepted_band,
                                                                        console_band):
    """What makes the interval usable as an objective: no row lands inside it and fails. Measured per
    call and returned, never assumed -- `in_band` is only a verdict while this holds."""
    assert accepted_band['sufficient'] is True and console_band['sufficient'] is True


def test_the_two_bands_are_different_so_the_band_may_not_be_hard_coded(accepted_band, console_band):
    """Per-configuration, not a seam constant: cell 2545 sits about three times further from zero than
    cell 2552, and the intervals do not overlap. A search has to solve it, not carry a number."""
    assert accepted_band['lo'] > console_band['hi']
    for b in (accepted_band, console_band):
        assert 2.0e-05 < b['width'] < 6.0e-05
        assert 2 <= b['values'] <= 12          # a handful of reachable rungs, not a continuum


# ------------------------------------------------------------------ what it replaces

def test_band_distance_ranks_a_row_by_the_thing_that_decides_it(accepted_band):
    """``|resid|`` calls a row at zero the closest one; `band_distance` calls it SHORT of the band by
    the band's own distance from zero. The sweep's own best in-contact residuals were exactly there."""
    assert RB.band_distance(accepted_band, A_RESID) == 0.0
    assert RB.band_distance(accepted_band, 0.0) == pytest.approx(-accepted_band['lo'], abs=1e-12)
    # s155's best in-contact row of the whole barren sweep, at walk 12 / thrust 13
    assert RB.band_distance(accepted_band, 3.1116561371971056e-06) < -1.5e-04
    assert RB.band_distance(accepted_band, accepted_band['hi'] + 1e-05) == pytest.approx(1e-05,
                                                                                         abs=1e-12)


def test_an_empty_window_reports_tested_rather_than_a_verdict():
    """``genuine == 0`` is a statement about the WINDOW: move the entry well off the one that clips and
    the same scan finds nothing while the band itself is unchanged. The count tested comes back so the
    caller cannot read it as 'this configuration cannot clip'."""
    b = RB.genuine_band(A_FACING, A_LEAN, A_THRUST, (A_ENTRY[0] + 1.0, A_ENTRY[1]), A_TETRA)
    assert b['genuine'] == 0 and b['tested'] > 10000
    assert b['lo'] is None and b['sufficient'] is None
    assert RB.in_band(b, A_RESID) is False and RB.band_distance(b, A_RESID) is None


def test_the_slice_cannot_decide_genuine_and_this_is_why_the_band_is_read_at_full_fidelity():
    """`cut_contact.cut_slice` pins ``old`` at the brace, which moves its residual ~1e-02 -- 300 times
    the band's width. On the very placement that delivered it therefore reports NOT genuine, and a ring
    built on it reports no genuine dust anywhere. The band must be read with her plow history intact."""
    ctx, sch, resid = ES.build_fast(A_FACING, A_LEAN, A_THRUST)
    real = ctx.sweep_par([(A_TETRA[0], A_TETRA[1], A_ENTRY[0], A_ENTRY[1])], 0, extra=True)[0]
    sl = CC.cut_slice(A_FACING, A_LEAN, A_THRUST, [(real[12], real[13])], ctx=ctx, sch=sch,
                      resid=resid)[0]
    assert bool(real[0]) is True and sl['genuine'] is False
    assert abs(sl['resid'] - resid(real)) > 100.0 * 3.4e-05


# ------------------------------------------------------------------ the admissibility screen

#: w10_t15's own best row off the s155 sweep: the CONSOLE'S OWN cell 2552 and thrust 15, at a different
#: lean and entry -- and barren on every axis swept (7.1 M placements of hers, 6561 entries, 16384 leans).
B_FACING, B_LEAN, B_THRUST = 40839, 0, 15
B_TETRA = (-1642.8582763671875, -911.8379516601562)
B_ENTRY = (-1599.9014892578125, -862.4032592773438)


def test_the_screen_fires_on_both_configurations_that_clip():
    """`admits` is only a screen if it never misses a live configuration at its own entry. Both known
    clips come back positive, bracketed, and the residual it finds sits inside that configuration's own
    band -- so the cheap detector and the expensive scan are measuring the same thing."""
    a = RB.admits(A_FACING, A_LEAN, A_THRUST, A_ENTRY, A_TETRA)
    c = RB.admits(C_FACING, C_LEAN, C_THRUST, C_ENTRY, C_TETRA)
    assert a['genuine'] > 0 and c['genuine'] > 0
    assert a['bracketed'] and c['bracketed']
    assert RB.in_band(RB.genuine_band(A_FACING, A_LEAN, A_THRUST, A_ENTRY, A_TETRA), a['lo'])


def test_the_screen_agrees_with_the_full_scan_over_the_window_it_shares():
    """Priced against `genuine_band` either side of the console's entry, at the ``half`` the screen's
    own reach justifies: same verdict inside the admitting region and outside it. The screen walks the
    gradient out to `LOCATE_SPAN`, so it is NOT bounded by a tighter scan box -- compared against the
    default +-0.02 u window it reports genuine where that window has none, which is the screen being
    right and the box being small."""
    for de in (0.0, 1.0):
        e = (C_ENTRY[0] + de, C_ENTRY[1])
        scr = RB.admits(C_FACING, C_LEAN, C_THRUST, e, C_TETRA)
        band = RB.genuine_band(C_FACING, C_LEAN, C_THRUST, e, C_TETRA, half=0.03, step=5.0e-4)
        assert bool(scr['genuine']) == bool(band['genuine']), de


def test_a_barren_configuration_is_refused_on_the_axis_the_search_can_move():
    """The negative this session rests on, pinned: the barren item shares the console's cell and thrust
    and admits nothing at its own entry -- and not at any lean either, which is the axis a walk can
    actually steer. Swept at 512 BAM here to stay a one-second gate; the session swept 16384 at 4 BAM."""
    assert RB.admits(B_FACING, B_LEAN, B_THRUST, B_ENTRY, B_TETRA)['genuine'] == 0
    assert not any(RB.admits(B_FACING, k, B_THRUST, B_ENTRY, B_TETRA)['genuine']
                   for k in range(0, 65536, 512))


def test_the_screen_costs_a_plane_scan_divided_by_two_hundred():
    """What makes it a screen rather than a measurement: `genuine_band` reads ~161k placements, this
    reads ~806, so a configuration SPACE is affordable where a plane scan per point is not."""
    assert RB.admits(A_FACING, A_LEAN, A_THRUST, A_ENTRY, A_TETRA)['tested'] < 1000
