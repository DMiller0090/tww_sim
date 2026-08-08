"""Gates for `harness.tetrapush.handoff` -- the chain-back frame (session 125).

The module's whole job is to read a DELIVERED (Link, Tetra) pair as a terminal configuration and to
solve, at a Tetra a herd parked, where Link may enter. Three things can silently break that and each
one is gated here rather than trusted:

  * the frame must BE `terminal.RollFrame` at ``side`` 0 (else the two modules answer differently);
  * it must never round-trip a razor-scale position through the coordinates (the console sin/cos
    basis is not orthonormal, and the trip costs more than the whole acceptance band);
  * the ``side`` scan must be centred on HER, not on the brace line, or a herd's own Tetra reads as
    having no contact anywhere and the chain-back reads as infeasible.

Values are pinned from `repr`, never hand-written (`[[zero-ulp-tests-only]]`, and the s124 trap of
padding `%.9f` output with invented digits).
"""
import math
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import entry_search as ES          # noqa: E402
from harness.tetrapush import handoff as H                # noqa: E402
from harness.tetrapush import seeds as SD                 # noqa: E402
from harness.tetrapush import terminal as TM              # noqa: E402

#: Three s124 scan hits, and the rows `terminal.RollFrame` returns for them.
SPECS = [(230, 50, 0.573628), (200, 70, 1.973729), (190, 55, 1.092994)]
ROLLFRAME_ROWS = [
    (True, 8.315698141955023e-05, 1.1267960751194153, 0.563396463006835, 0.21431194181943142),
    (True, 6.825935070755777e-05, 1.1315915313004155, 0.5657959231366003, 0.21406781193013755),
    (True, 5.550275291876146e-05, 1.1318276335986894, 0.5659141917684544, 0.21400677946164132)]

#: The first of those, as world positions, plus what a coordinate ROUND TRIP of it costs.
REF_TETRA = (-1566.1943811382373, -826.8247222108016)
REF_ENTRY = (-1531.6861263773924, -790.6375836020892)
ROUNDTRIP_COORDS = (229.99996304323497, 0.0, 49.999991965920614, 0.5736279078285484)
ROUNDTRIP_ROW = (False, 0.001052132498393048, 1.1302613187537531, 0.5651321547464501,
                 0.21437297429557556)

#: A Tetra the banked s119 herd actually parks (node 16), 68 u off the clip roll's approach line.
HERD_TETRA = (-1616.8218994140625, -780.3568115234375)
HERD_L0 = -68.11412671348236

#: The banked cycle-3 endpoint CLOSEST to the entry curve (s122 require beam node 45, 73 herd frames)
#: -- a real delivered pair on the genuine side, and where the frame price is pinned.
ONSIDE_LINK = (-1621.344482421875, -832.6629638671875)
ONSIDE_TETRA = (-1606.7857666015625, -888.6373291015625)
ONSIDE_L0 = 14.689594181878682

#: `resid_window` at that pair on the 230 rung, and the residual OUTSIDE it -- one number, repeated,
#: which is the whole reason a coarse pass can say where the fine one has anything to find.
ONSIDE_WINDOW = (8.939594181878682, 20.189594181878682)
NO_CONTACT_RESID = -0.3293846608827907
ONSIDE_CROSSINGS = [(9.599594181878679, 9.604594181878689),
                    (11.749594181878685, 11.75459418187868)]


@pytest.fixture(scope='module')
def pf():
    return H.PairFrame(ES.TAB_FACING, 14, 0)


def test_side_zero_is_the_terminal_frame(pf):
    """`PairFrame` at ``side`` 0 IS `terminal.RollFrame` -- bit-identical rows, not merely close."""
    assert pf.at_side(0.0).rows(SPECS) == ROLLFRAME_ROWS
    assert TM.RollFrame(ES.TAB_FACING, 14, 0).rows(SPECS) == ROLLFRAME_ROWS


def test_a_coordinate_round_trip_costs_more_than_the_whole_acceptance(pf):
    """The trap this module exists to avoid: ``m``/``q`` come from the console's f32 sin/cos tables,
    so projecting a world pair into (runway, side, along, lat) and building it back moves the
    residual by an order of magnitude MORE than the acceptance band -- a genuine cell round-trips
    into a dead one. Anything razor-scale must hold the positions (`PairFrame.sweep`)."""
    assert pf.sweep([REF_TETRA + REF_ENTRY])[0] == ROLLFRAME_ROWS[0]
    assert pf.coords(REF_ENTRY, REF_TETRA) == ROUNDTRIP_COORDS
    assert pf.rows([ROUNDTRIP_COORDS]) == [ROUNDTRIP_ROW]
    assert ROLLFRAME_ROWS[0][0] is True and ROUNDTRIP_ROW[0] is False
    assert abs(ROUNDTRIP_ROW[1]) > 10 * abs(ROLLFRAME_ROWS[0][1])


def test_probe_reads_a_delivered_pair_without_going_through_the_coordinates(pf):
    """The terminal predicate on a DELIVERED state has to sweep the positions it was handed. If it
    ever rebuilt them from (runway, side, along, lat) it would answer ``False`` on the very cell the
    s124 scan calls genuine -- so this pins it against `RollFrame`'s own row, not against a tolerance."""
    p = probe = H.probe(pf, REF_ENTRY, REF_TETRA)
    assert p['genuine'] is True
    assert (p['resid'], p['overlap'], p['push'], p['brace_dist']) == ROLLFRAME_ROWS[0][1:]
    assert (probe['runway'], probe['side'], probe['along'], probe['lat']) == ROUNDTRIP_COORDS


def test_the_side_scan_must_be_centred_on_her_not_on_the_brace_line(pf):
    """A herd parks her tens of units off the approach line, and Link only touches her at the cut
    inside a corridor ~1 u wide sitting at ``side ~ l0``. A brace-centred span therefore reports NO
    CONTACT ANYWHERE at a real herd Tetra -- which reads as infeasible and is not
    (`[[infeasible-needs-proof]]`)."""
    assert H.tetra_lateral(pf, HERD_TETRA) == HERD_L0
    entry = pf.entry_at(230.0)
    brace_centred = [-60 + 0.005 * k for k in range(24001)]
    assert max(r[2] for r in pf.sweep(H._items(pf, HERD_TETRA, entry, brace_centred))) < -1.0
    her_centred = H.side_crossings(pf, HERD_TETRA, entry)
    assert her_centred, 'her-centred span finds the corridor the brace-centred one steps over'


def test_link_lateral_contact_corridor_is_about_one_unit_wide(pf):
    """Why `SIDE_STEP` is 0.005 and not `terminal.LAT_STEP`'s 0.5: at a fixed Tetra the whole
    corridor of Link entries that still touch her at the cut is ~1 u wide, so a half-unit bracket
    step can straddle it entirely."""
    sides = [-2.0 + 0.005 * k for k in range(1601)]
    rs = pf.sweep(H._items(pf, REF_TETRA, REF_ENTRY, sides))
    con = [s for s, r in zip(sides, rs) if r[2] > -1.0]
    assert con and 0.5 < (max(con) - min(con)) < 2.0
    assert H.SIDE_STEP <= 0.1 * (max(con) - min(con))


def test_the_locus_contains_the_recorded_console_confirmed_entry(pf):
    """`[[search-space-contains-human]]`: at the Tetra of tabulated coord 274, `entry_locus` -- which
    knows nothing about the recording -- must SOLVE its way back to the recorded roll entry."""
    rows, _hdr = SD.load_placements()
    tetra = (rows[274]['x'], rows[274]['z'])
    assert pf.sweep([tetra + tuple(ES.TAB_ENTRY)])[0][0] is True
    runway = pf.coords(ES.TAB_ENTRY, tetra)[0]
    loc = H.entry_locus(pf, tetra, runways=(runway,))
    assert len(loc) == 1
    b = loc[0]
    off = math.hypot(b['entry'][0] - ES.TAB_ENTRY[0], b['entry'][1] - ES.TAB_ENTRY[1])
    assert off < 1e-4, 'solved entry %r vs recorded %r' % (b['entry'], ES.TAB_ENTRY)
    assert 0.0 < b['width'] < 1e-3 and not b['clipped']


def test_the_solved_entry_is_a_razor_and_the_band_edges_are_the_edges(pf):
    """`[[full-fp-precision-coords]]`, as a gate. The solved entry clips; the same entry quoted to
    three decimals does NOT (a milliunit is twenty band widths); and the band `side_band` reports is
    the real one -- a hair outside either edge is dead."""
    rows, _hdr = SD.load_placements()
    tetra = (rows[274]['x'], rows[274]['z'])
    runway = pf.coords(ES.TAB_ENTRY, tetra)[0]
    entry0 = pf.entry_at(runway)
    b = H.side_band(pf, tetra, entry0, H.solve_sides(
        pf, tetra, [(entry0,) + H.side_crossings(pf, tetra, entry0)[0]])[0])
    assert pf.sweep([tetra + tuple(b['entry'])])[0][0] is True
    assert pf.sweep([tetra + (round(b['entry'][0], 3), round(b['entry'][1], 3))])[0][0] is False
    inside = [b['side_lo'], b['side_hi']]
    outside = [b['side_lo'] - 1e-5, b['side_hi'] + 1e-5]
    assert all(r[0] for r in pf.sweep(H._items(pf, tetra, entry0, inside)))
    assert not any(r[0] for r in pf.sweep(H._items(pf, tetra, entry0, outside)))


# --------------------------------------------------------------------- the rank (session 126)

def test_outside_contact_the_residual_is_one_number(pf):
    """The claim the coarse window rests on, as a gate rather than an assumption: a roll that never
    reaches her runs the same trajectory whatever ``side`` is, so its residual is BIT-IDENTICAL
    everywhere outside contact. That is what makes a 561-sample pass able to say where the 28001-
    sample one has anything to find -- and it is an equality, not a tolerance."""
    entry = pf.entry_at(230.0)
    assert H.resid_window(pf, ONSIDE_TETRA, entry) == ONSIDE_WINDOW
    far = [ONSIDE_L0 - 70.0, ONSIDE_L0 - 50.0, ONSIDE_WINDOW[0] - 1e-6,
           ONSIDE_WINDOW[1] + 1e-6, ONSIDE_L0 + 50.0, ONSIDE_L0 + 70.0]
    rs = pf.sweep(H._items(pf, ONSIDE_TETRA, entry, far))
    assert [r[1] for r in rs] == [NO_CONTACT_RESID] * len(far)
    assert (ONSIDE_WINDOW[1] - ONSIDE_WINDOW[0]) < 0.1 * 2 * H.SIDE_SPAN, 'the saving is the point'


def test_the_windowed_scan_is_the_full_span_scan(pf):
    """Same brackets, exactly. The fine samples are taken on the full span's own lattice, so the two
    paths evaluate bit-identical positions -- at a 1e-4 u acceptance, agreeing to within a step would
    not be agreeing at all."""
    entry = pf.entry_at(230.0)
    assert H.side_crossings(pf, ONSIDE_TETRA, entry, window_step=None) == ONSIDE_CROSSINGS
    assert H.side_crossings(pf, ONSIDE_TETRA, entry) == ONSIDE_CROSSINGS
    # ...and at the s124 reference cell, whose contact corridor is ~1 u wide rather than ~11
    assert (H.side_crossings(pf, REF_TETRA, pf.entry_at(230.0), window_step=None)
            == H.side_crossings(pf, REF_TETRA, pf.entry_at(230.0)))


def test_the_root_curve_is_a_bound_and_says_so(pf):
    """`entry_roots` skips the f32 band walk, so it can be non-empty where the GENUINE curve is empty
    -- a bisected root is only a sign change, and whether its neighbourhood clips is what the walk
    decides. That makes the cheap curve an under-estimate of the gap (what a prune needs) and never a
    claim about a clip, so the record carries ``roots`` and a quoted plan owes an `entry_locus`
    confirmation (`[[banded-proxy-needs-its-newton]]`)."""
    rungs = (230.0,)
    gr = H.node_gap(pf, ONSIDE_LINK, ONSIDE_TETRA, roots=True, runways=rungs)
    gl = H.node_gap(pf, ONSIDE_LINK, ONSIDE_TETRA, runways=rungs)
    assert gr['roots'] is True and gl['roots'] is False
    assert gr['n'] == 2 and gl['n'] == 0
    assert gr['gap'] <= gl['gap']
    # every genuine entry IS a root, so the banded curve can only be a subset of the cheap one
    full = H.entry_locus(pf, ONSIDE_TETRA)
    roots = H.entry_roots(pf, ONSIDE_TETRA)
    assert 0 < len(full) <= len(roots)
    for b in full:
        assert min(abs(b['side'] - r['side']) for r in roots) <= H.BAND_HALF


def test_an_endpoint_is_priced_in_frames_and_the_wrong_side_is_refused_free(pf):
    """The last cycle's rank. ``bound`` is the herd frames spent plus the fewest that could still
    close the gap at the walk cap plus the clip roll's own ``cut_step`` -- admissible on every term,
    so a beam ranked on it is frame-minimal by construction. And the side prune has to be FREE: an
    endpoint that parked her on the wrong side is refused on one dot product, without solving a
    razor, or the rank cannot run at beam scale."""
    rungs = (230.0,)
    e = H.endpoint(pf, ONSIDE_LINK, ONSIDE_TETRA, 73, runways=rungs)
    assert e['onside'] is True and e['l0'] == ONSIDE_L0 and e['n'] == 2
    assert e['bound'] == 73 + e['gap'] / H.WALK_CAP + pf.cut_step
    assert H.WALK_CAP == 17.0 and pf.cut_step == 16
    off = H.endpoint(pf, ONSIDE_LINK, HERD_TETRA, 73, runways=rungs)
    assert off['refused'] == 'offside' and off['l0'] == HERD_L0
    assert off['bound'] == float('inf') and off['n'] == 0 and 'locus' not in off


def test_the_search_keep_reads_only_fields_this_module_promises():
    """Anti-drift across the module boundary: `full_herd.extend_cycle`'s ``handoff_keep`` sorts on
    ``bound``, tie-breaks on ``l0``, shares a keep by ``gap`` and reports ``onside``/``n``. A rename
    here would silently REORDER a beam rather than fail, which is the worst way for a rank to break."""
    import inspect
    from harness.tetrapush import full_herd as FH

    sig = inspect.signature(FH.extend_cycle).parameters
    for kw in ('handoff_keep', 'handoff_pf', 'handoff_rungs', 'handoff_roots', 'handoff_sign'):
        assert kw in sig, kw
    assert FH._HO() is H
    rec = H.endpoint(H.PairFrame(ES.TAB_FACING, 14, 0), ONSIDE_LINK, HERD_TETRA, 73)
    assert {'bound', 'l0', 'gap', 'n', 'onside', 'frames'} <= set(rec)
