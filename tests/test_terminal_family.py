"""The terminal family measured at the state a herd actually delivers (session 144).

Session 124 scanned the family ONCE -- facing 40835, thrust 14, lean 0 -- and every number the
endgame is priced against came out of that one scan. Two of its three axes are not the delivered ones,
and the session-143 handoff's items 0 and 0b asked for exactly this: does the family survive the
delivery state, and what do the other realizable thrusts hold.

These gate the answers, off the banked `fixtures/courtyard_terminal_family.json` rather than by
re-scanning (a functionality test does not take a second -- `tests/conftest.py`); the one test that
does re-scan is marked slow and exists to keep the fixture honest.

The load-bearing distinction is `clipping_family`'s: **a thrust that DISPATCHES the cut is not a
thrust that CLIPS**. `entry_search.thrust_window` is a property of the roll's animation; whether the
cut reaches the seam is a property of the corner, and thrust 13 satisfies the first and fails the
second everywhere in the box.
"""
import json

import pytest

from harness.tetrapush import entry_search as ES
from harness.tetrapush import terminal as TM

#: The state every banked herd rung hands over (`fixtures/...['delivery']`), named once here so a
#: reader can see which numbers below are the DELIVERED ones and which are session 124's.
DELIVERED_LEAN = 648
SCANNED_LEAN = 0


@pytest.fixture(scope='module')
def fam():
    with open(TM.FAMILY_FIXTURE) as fh:
        return json.load(fh)


def _rec(fam, facing, thrust, lean):
    return next(r for r in fam['records']
                if (r['facing'], r['thrust'], r['lean']) == (facing, thrust, lean))


# --------------------------------------------------------------- the positive control

def test_the_banked_reference_reproduces_session_124s_scan(fam):
    """Nothing below is comparable unless the reference row is the one the endgame was priced on.

    Re-scanned in session 144 from the same box and it came back identical -- 51 genuine, 13 with
    contact unbroken, `plowed` 24.70..125.88 u -- which is what licenses reading the other rows as
    differences rather than as noise."""
    r = _rec(fam, ES.TAB_FACING, 14, SCANNED_LEAN)
    assert (r['genuine'], r['unbroken']) == (51, 13)
    assert r['plowed'] == pytest.approx([24.70, 125.88], abs=0.01)
    assert r['tetra_from_corner'] == [10, 180]
    assert r['un_tetra_from_corner'] == [100, 180]


# --------------------------------------------------- dispatchable is not the same as clipping

def test_a_dispatchable_thrust_is_not_a_clipping_thrust(fam):
    """Thrust 13 is INSIDE the dispatch window and clips nowhere in the box, at either lean.

    Session 143 derived `cut_step_window` and then priced thrust 13's 17-frame roll as the cheapest
    deliverable clip roll -- on the strength of the dispatch window alone, which answers a different
    question. The corner's answer is 0."""
    assert 13 in ES.THRUSTS and ES.thrust_window()[0] == 13          # it dispatches
    for lean in (SCANNED_LEAN, DELIVERED_LEAN):
        r = _rec(fam, ES.TAB_FACING, 13, lean)
        assert r['genuine'] == 0 and r['unbroken'] == 0
        # ...and it is ABSENT geometry, not a thin scan: the razor crosses zero thousands of times
        # and not one crossing has a genuine f32 neighbourhood (`[[infeasible-needs-proof]]`)
        assert r['roots'] > 2000
        assert r['cells_with_a_crossing'] > 1400


def test_the_conversion_rate_is_the_thrusts_own_and_the_scan_is_not_the_variable(fam):
    """Roots are near-constant across the three thrusts; what changes is how many of them clip.

    2390 -> 0, 2513 -> 40, 2613 -> 107 at the delivered lean. A scan that under-sampled would show it
    in the ROOT count, and it does not."""
    got = [(t, _rec(fam, ES.TAB_FACING, t, DELIVERED_LEAN)) for t in (13, 14, 15)]
    roots = [r['roots'] for _t, r in got]
    assert max(roots) - min(roots) < 0.10 * min(roots)               # within 10% of one another
    assert [r['genuine'] for _t, r in got] == [0, 40, 107]


def test_clipping_thrusts_excludes_the_one_that_only_dispatches():
    assert TM.clipping_thrusts(ES.TAB_FACING, DELIVERED_LEAN) == (14, 15)
    assert TM.clipping_thrusts(ES.TAB_FACING, SCANNED_LEAN) == (14, 15)


def test_the_zero_walk_away_family_is_thrust_14_alone_at_the_delivered_lean(fam):
    """Session 123's shape needs contact UNBROKEN for the whole roll. At the delivered lean only
    thrust 14 has any: 15 scans 107 genuine and not one of them keeps contact."""
    assert TM.clipping_thrusts(ES.TAB_FACING, DELIVERED_LEAN, unbroken=True) == (14,)
    assert _rec(fam, ES.TAB_FACING, 15, DELIVERED_LEAN)['unbroken'] == 0
    assert _rec(fam, ES.TAB_FACING, 14, DELIVERED_LEAN)['unbroken'] == 8


def test_an_unmeasured_terminal_returns_none_rather_than_a_neighbours_answer():
    """The defect `handoff.crossing_bar` was written against: a plausible number with no population
    behind it. A facing nobody scanned has no family, and the caller has to say so."""
    assert TM.clipping_family(ES.TAB_FACING, 14, 12345) is None
    assert TM.clipping_thrusts(ES.TAB_FACING, 12345) is None
    assert TM.clipping_family(ES.TAB_FACING, 14, DELIVERED_LEAN) is not None


# ------------------------------------------------------- what the delivered state costs

def test_the_delivered_lean_lowers_the_plow_ceiling_it_does_not_raise_it(fam):
    """Item 0b hoped a re-scan would re-price the "within 180 u of the corner" ceiling upward. At the
    delivered lean it goes the other way -- 180 -> 160 -- which HALVES the banked rungs that clear it
    (8 -> 4), and the longest realizable roll only reaches 165."""
    a = _rec(fam, ES.TAB_FACING, 14, SCANNED_LEAN)
    b = _rec(fam, ES.TAB_FACING, 14, DELIVERED_LEAN)
    assert a['tetra_from_corner'][1] == 180 and b['tetra_from_corner'][1] == 160
    assert b['plowed'][1] < a['plowed'][1]                            # 106.05 vs 125.88 u
    assert _rec(fam, ES.TAB_FACING, 15, DELIVERED_LEAN)['tetra_from_corner'][1] == 165


def test_the_delivered_facings_convert_no_roots_either(fam):
    """The closest facing any banked rung delivers is 11.0 deg below the seam's own window, and over
    the whole box it bisects 2674 roots and clips at none of them. So the herd's AIM is a bar in the
    same population-complete sense the thrust is -- not a near miss to be closed by ranking."""
    for facing in (38782, 34635):
        r = _rec(fam, facing, 14, DELIVERED_LEAN)
        assert r['roots'] > 1000 and r['genuine'] == 0


# ----------------------------------------------- what a herd hands over, and why the seed is right

def test_tetra_is_idle_and_at_rest_at_every_banked_handoff(fam):
    """`fast_schedule` seeds her at rest, and the session-143 handoff flagged that a herd hands over a
    FOLLOWING Tetra. Measured over all 49 rungs it does not: Link never reaches
    `FOLLOW_ENGAGE_DIST`, so she never leaves stt 3 and the historical seed is the delivered one.

    The margin is 8 u, which is why this is a gate and not a note -- a re-pointed herd that crosses
    230 u puts `FreeRun` outside the state it models at all, and its own warning is suppressed by the
    `simplefilter('ignore')` every probe in this module runs."""
    d = fam['delivery']
    assert d['tetra_is_at_rest_at_every_handoff'] is True
    assert d['rungs_reaching_engage'] == 0
    assert d['max_link_tetra_dist'] < d['follow_engage_dist']
    assert d['follow_engage_dist'] - d['max_link_tetra_dist'] < 10.0  # ...by 7.86 u


def test_the_delivered_lean_and_momentum_are_one_value_each(fam):
    """m351C 648 and nspeed 26.0 at every roll entry of every rung -- so "the delivered lean" is a
    single number and the family scanned at 0 was scanned at a state nothing delivers."""
    d = fam['delivery']
    assert d['lean'] == [DELIVERED_LEAN]
    assert d['nspeed'] == [ES.ROLL_NSPEED]


def test_no_banked_rung_aims_its_last_roll_into_the_seam_window(fam):
    """The single cleanest statement of the blocker: 0 of 49. The camera can deliver 27 in-window
    facings (`entry_search.aim_alphabet` at `CSANGLE`), so the aim is free and the herd does not use
    it -- the last roll points AT her, to plow her, and the clip roll must point at the CORNER."""
    d = fam['delivery']
    assert d['rungs_aimed_into_the_seam_window'] == 0
    assert d['last_roll_facing'][1] < d['seam_facing_window'][0]


def test_no_banked_rung_delivers_the_handoff_distance_the_family_needs(fam):
    """The third disjointness, and the one nobody had measured: the unbroken family wants Link
    60..100 u behind her at the roll entry and every rung delivers 42..56."""
    b = _rec(fam, ES.TAB_FACING, 14, DELIVERED_LEAN)
    lo, hi = fam['delivery']['last_roll_along']
    assert hi < b['un_along'][0]                                      # 55.98 < 60
    assert b['un_along'] == [60, 100]


# --------------------------------------------------------------------------------- slow

@pytest.mark.slow
def test_the_banked_family_still_reproduces_a_live_scan(fam):
    """The fixture is a measurement, so it has to stay one: re-scan the delivered terminal and check
    it against what was banked. ~40 s, which is why it is not in the per-session gate."""
    hits, _secs = TM.scan(ES.TAB_FACING, 14, DELIVERED_LEAN)
    r = _rec(fam, ES.TAB_FACING, 14, DELIVERED_LEAN)
    assert len(hits) == r['genuine']
    assert sum(1 for h in hits if h['unbroken']) == r['unbroken']
    assert max(h['plowed'] for h in hits) == pytest.approx(r['plowed'][1], abs=1e-9)
