"""THE TERMINAL CONFIGURATION in the zero-walk-away shape (session 124).

Dereck's re-aim at the end of s123: the herd's LAST ROLL *is* the clip roll, Link never leaves her, and
the open unknown was the razor -- "the clip wants ~1.23 u of overlap at the cut and a herd roll's depth
is whatever the plow produces". These gates pin what the measurement answered:

  * the best case EXISTS -- Link touching her at the roll entry, contact never breaking, and the cut
    genuine through the seam;
  * **the depth is NOT the herd's to produce.** The corner washes the handoff out: over handoffs 50-245 u
    apart the final overlaps converge to 1.127-1.132 u, her cut-frame position to a 0.054 x 0.205 u box
    and Link's braced point to 0.001 u. The razor asks for ALIGNMENT, never for depth;
  * the body lean SHIFTS that alignment and never closes it -- `entry_search`'s "m351C 64 already does
    not clip" is a statement about a fixed entry, not about feasibility;
  * and the search box provably contains the one configuration known to clip
    (`[[search-space-contains-human]]`).

Every value is an exact pinned model output (`[[zero-ulp-tests-only]]`): the razor is re-solved by a
deterministic bisection and the cut endpoint is compared BY BITS, never within a tolerance. A tolerance
here would hide exactly the drift these gates exist to catch -- the acceptance band is ~5e-5 u wide.
"""
import math
import struct
import warnings

import pytest

from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_depth as RD
from harness.tetrapush import seeds as SD
from harness.tetrapush import terminal as TM

warnings.simplefilter('ignore')


def _bits(v):
    return struct.pack('>f', v).hex()


#: Three ZERO-WALK-AWAY configurations (touching at entry, contact unbroken), razor and cut endpoint
#: pinned EXACTLY: handoffs 50/55/85 u, she starts 180/135/115 u out, endpoints agree to 0.003 u.
PINNED = (
    # runway along  lat (solved)      overlap        new_x bits  new_z bits
    (190, 55, 1.0929938124629284, 1.1318276335986894, 'c4d7e587', 'c4779da4'),
    (200, 85, 3.1382660877822643, 1.1323940505245247, 'c4d7e589', 'c4779da8'),
    (230, 50, 0.5736280624080731, 1.1267960751194153, 'c4d7e575', 'c4779d7f'),
)


@pytest.fixture(scope='module')
def fr():
    return TM.RollFrame(ES.TAB_FACING, 14, 0)


def test_the_scan_box_contains_the_tabulated_clip(fr):
    """`[[search-space-contains-human]]` -- a search whose range does not intrinsically contain the
    known-good reference is broken. The reference here is the recorded roll entry plus the 288 genuine
    coords it was swept at, and the handoff box must hold every one of them."""
    e = ES.TAB_ENTRY
    er = (e[0] - fr.brace[0], e[1] - fr.brace[1])
    runway = -(er[0] * fr.m[0] + er[1] * fr.m[1])
    assert TM.RUNWAY[0] <= runway <= TM.RUNWAY[-1]

    rows, _hdr = SD.load_placements()
    assert len(rows) == 288
    for r in rows:
        d = (r['x'] - e[0], r['z'] - e[1])
        along = d[0] * fr.m[0] + d[1] * fr.m[1]
        lat = d[0] * fr.q[0] + d[1] * fr.q[1]
        assert TM.ALONG[0] <= along <= TM.ALONG[-1]
        assert abs(lat) <= TM.LAT_SPAN

    # and the engine the box is swept with reproduces the reference clip itself
    o = fr.ctx.sweep_par([(rows[0]['x'], rows[0]['z'], e[0], e[1])], 0, extra=True)[0]
    assert bool(o[0]) is True


@pytest.mark.parametrize('runway,along,lat,overlap,bx,bz', PINNED)
def test_a_zero_walk_away_terminal_configuration_is_genuine(fr, runway, along, lat, overlap, bx, bz):
    """The best case, pinned: re-solve the razor from the coarse bracket and demand the SAME lateral,
    the same overlap and a BIT-EXACT cut endpoint. The bisection is deterministic, so this is an
    equality and not an approximation."""
    hits = TM.solve_cell(fr, runway, along)
    assert len(hits) == 1
    h = hits[0]
    assert h['lat'] == lat
    assert h['overlap'] == overlap
    c = TM.classify(fr, h)
    assert c['genuine_confirmed'] is True
    assert _bits(c['new'][0]) == bx
    assert _bits(c['new'][1]) == bz


@pytest.mark.parametrize('runway,along,lat,overlap,bx,bz', PINNED)
def test_link_never_separates_from_her_through_the_whole_roll(fr, runway, along, lat, overlap, bx, bz):
    """The defining property of the zero-walk-away shape: he is ALREADY touching her when the roll
    starts and the contact does not break for a single frame up to the cut. A configuration that
    separated would be the old shape wearing new coordinates."""
    _res, _steps, ov = fr.overlaps(runway, along, lat)
    assert ov[0] > 0.0
    assert min(ov[:fr.cut_step]) > 0.0


def test_the_razor_asks_for_alignment_and_not_for_depth(fr):
    """THE OPEN UNKNOWN THE s123 HANDOFF NAMED, ANSWERED. "A herd roll's depth is whatever the plow
    produces" is true and turns out not to matter: the corner washes the handoff out. Over handoffs
    50-85 u and starting distances 115-180 u from the corner -- with the roll plowing her 66 u in one
    case and 126 u in another -- the cut-frame overlap agrees to 0.006 u and Link's braced point to
    0.001 u. So the depth is the CORNER's, and what the herd must deliver is the lateral alignment."""
    ovs, braces, plows = [], [], []
    for runway, along, lat, _ov, _bx, _bz in PINNED:
        rows = fr.rows([(runway, along, lat)])
        ovs.append(rows[0][2])
        braces.append(rows[0][4])
        plows.append(TM.classify(fr, dict(runway=runway, along=along, lat=lat))['plowed'])
    assert max(ovs) - min(ovs) < 0.01
    assert max(braces) - min(braces) < 0.002
    assert max(plows) - min(plows) > 50.0          # the handoffs really are far apart


def test_her_cut_frame_position_is_an_attractor(fr):
    """The consequence a planner spends frames on: the last roll PARKS her, so the herd does not have
    to place her. Pinned as a box rather than a point because the residual spread is real."""
    xs, zs = [], []
    for runway, along, lat, _ov, _bx, _bz in PINNED:
        c = TM.classify(fr, dict(runway=runway, along=along, lat=lat))
        xs.append(c['tetra_at_cut'][0])
        zs.append(c['tetra_at_cut'][1])
    assert max(xs) - min(xs) < 0.10
    assert max(zs) - min(zs) < 0.25


def test_the_lean_shifts_the_razor_but_does_not_close_it():
    """OVERTURNS the reading that some body leans cannot clip. `entry_search`'s "m351C 0 and 1 clip, 64
    already does not (resid 1.1e-2)" is measured at a FIXED entry, where 1.1e-2 is a hundred window
    widths -- so it says the lean must be RE-SOLVED, not that it is a bar. Re-solving the lateral finds
    a genuine configuration at every lean tried, including the +64 that reads dead at a fixed entry and
    the -191 a replayed herd actually hands over."""
    for lean in (64, (-191) & 0xFFFF, (-160) & 0xFFFF):
        f = TM.RollFrame(ES.TAB_FACING, 14, lean)
        found = []
        for runway in (200, 220, 240, 260):
            for along in (55, 70, 85, 100, 115):
                found += TM.solve_cell(f, runway, along)
                if found:
                    break
            if found:
                break
        assert found, "lean %d admits no terminal configuration" % lean
        assert TM.classify(f, found[0])['genuine_confirmed'] is True


def test_the_bracketing_grid_reads_a_clipping_cell_as_empty(fr):
    """THE METHODOLOGY GATE -- why `solve_razor` bisects instead of sweeping, kept honest by measurement.

    The acceptance band at the first pinned cell is **5.13e-5 u** wide against a residual gradient of
    ~4 /u, so the module's OWN 281-sample bracketing grid finds nothing at a cell that clips: the grid's
    only job is to bracket the sign change. Any future "swept it, found nothing" claim about this corner
    has to clear this bar first -- a sweep is a lottery here whatever its step, and the odds are the
    band width over the step."""
    runway, along, lat = PINNED[0][0], PINNED[0][1], PINNED[0][2]
    n = int(2 * TM.LAT_SPAN / TM.LAT_STEP) + 1
    xs = [-TM.LAT_SPAN + TM.LAT_STEP * i for i in range(n)]
    assert not any(r[0] for r in fr.rows([(runway, along, x) for x in xs]))
    assert fr.rows([(runway, along, lat)])[0][0] is True

    band = TM.solve_cell(fr, runway, along)[0]
    assert band['width'] < 1e-4 and band['clipped'] is False
    assert band['width'] / TM.LAT_STEP < 1e-3            # the sweep-vs-bisect odds, stated as a number

    # The residual gradient is O(1) /u at every pinned cell (6.42, 4.00, 14.30), so band width and
    # lateral precision are the same number to an order of magnitude -- hence bisect, never sweep.
    for rw, al, lt, _ov, _bx, _bz in PINNED:
        d = 0.01
        lo = fr.rows([(rw, al, lt - d)])[0][1]
        hi = fr.rows([(rw, al, lt + d)])[0][1]
        assert 2.0 < abs(hi - lo) / (2 * d) < 25.0
