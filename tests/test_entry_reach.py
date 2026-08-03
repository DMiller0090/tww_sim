"""WHAT A PLAN OF N FRAMES CAN REACH, and the claim session 92 made over the wrong set (session 93).

`entry_search.reach_radius` is a RADIUS -- four walk frames at the cap plus the roll's own entry step,
94 u -- and `curve_seeds` uses it as a square box around `ref_entry`. That is a deliberate
over-approximation, but the whole session-92 productive set was measured inside it, so "cell 2562 carries
genuine dust at a walkable entry" became, silently, "a plan at the frame floor can clip at cell 2562".
Link enters the window at the speedF 17 cap on a fixed heading and four held-stick frames can only turn
him so far, so the real reachable set is a small curved cloud.

Measured (session 93): a frame-capped pass at the whole aimable second lobe -- 779130 candidates, 7.0 M
evaluations -- returns 0 genuine, 0 near and 0 dead-tail, and the residual stays 71x to 375x outside
`BAND_PROBE` at every right cell. These gates pin the reachability half of that: the hull is a real convex
hull, it CONTAINS the console-delivered clip's own entry (the licence -- a reachable set that excludes
the known-good input is broken), and the far right cells' stations sit outside it.

Offline: the native fan + a stdlib hull, no Dolphin.
"""
import json
import os

import pytest

from harness.tetrapush import entry_reach as ER
from harness.tetrapush import entry_score as EC
from harness.tetrapush import entry_search as ES


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', name)


def _hulls():
    if not os.path.exists(ER.HULL_FIXTURE):
        pytest.skip("no measured walk hull at %s -- run `entry_reach hull`" % ER.HULL_FIXTURE)
    return ER.load()


# ------------------------------------------------------------------ the hull primitive

def test_the_hull_is_a_convex_hull():
    """Andrew's monotone chain, counter-clockwise, interior points dropped. Pure stdlib because the
    harness has no scipy dependency -- so it owes the ordinary correctness tests."""
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.5, 0.5)]
    h = ER.hull(square)
    assert len(h) == 4 and (0.5, 0.5) not in h
    # counter-clockwise: every consecutive triple turns left
    for i in range(len(h)):
        a, b, c = h[i], h[(i + 1) % len(h)], h[(i + 2) % len(h)]
        assert ER._cross(a, b, c) > 0.0, (a, b, c)
    # collinear points on an edge are not vertices
    assert len(ER.hull([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 1.0)])) == 3
    assert ER.hull([(1.0, 1.0)]) == [(1.0, 1.0)]
    assert ER.hull([]) == []


def test_contains_is_a_margin_test_and_the_margin_is_the_callers_to_state():
    """The hull is measured off a COARSE fan, so an exact edge test would turn "a stick the alphabet
    skipped" into "unreachable". The slack is therefore explicit at the call site, and only the
    OUTSIDE verdict is used as a fact (see `entry_reach`'s docstring)."""
    unit = ER.hull([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    assert ER.contains(unit, (5.0, 5.0))
    assert not ER.contains(unit, (-0.5, 5.0))
    assert ER.contains(unit, (-0.5, 5.0), margin=1.0)      # just outside, inside the slack
    assert not ER.contains(unit, (-2.0, 5.0), margin=1.0)
    assert not ER.contains([(0.0, 0.0), (1.0, 0.0)], (0.5, 0.0))   # a degenerate hull contains nothing


def test_one_hull_serves_every_facing_because_the_entry_is_a_translation():
    """THE FACTORISATION THE WHOLE MODULE RESTS ON. `entry_search.roll_entry` is
    ``walk + nspeed * (sin, cos)(facing)`` -- a pure translation in the walk position -- so the entry
    cloud is the walk cloud shifted by a facing-dependent vector, and ONE facing-independent hull can
    answer every configuration by shifting the query instead. If that ever stops being a translation
    (an entry-frame brake changing nspeed, say) this test is what says so."""
    walk = (-1531.25, -781.5)
    for facing in (40841, 40995, 41296):
        o = ES.roll_entry((0.0, 0.0), facing)
        e = ES.roll_entry(walk, facing)
        # exact to f32 addition: the offset is the same vector wherever it is applied
        assert abs((e[0] - walk[0]) - o[0]) < 1e-3, facing
        assert abs((e[1] - walk[1]) - o[1]) < 1e-3, facing


# ------------------------------------------------------- the measured cloud, and what it excludes

def test_the_reachable_cloud_contains_the_console_delivered_clips_own_entry():
    """**THE LICENCE.** A reachable set that does not contain the known-good input is broken, not a
    measurement (`[[search-space-contains-human]]`). The 4-frame hull therefore has to contain the
    entry of the 4-frame plan that was delivered to console and clipped
    (`fixtures/courtyard_clip_s90_console.json`, plan ``[0,208,110,2,169,192,2]``, cell 2552).

    This is the assertion that makes the negative below worth anything: the same hull, at the same
    budget, that excludes the right cells' stations must include the one plan we know works."""
    hulls = _hulls()
    row = json.load(open(_fx('courtyard_entry_s90_hits.json')))['rows'][0]
    assert row['frames'] == ER.FLOOR_FRAMES, row['frames']
    assert ER.reachable(tuple(row['entry']), row['facing'], frames=ER.FLOOR_FRAMES, hulls=hulls), \
        "the delivered clip's own entry must be inside the measured 4-frame reachable set"


def test_the_second_lobe_is_out_of_reach_at_the_frame_floor():
    """**THE FINDING, and it is gated on the SIGN TEST rather than on the hull.**

    The load-bearing quantity is the CLOSEST APPROACH over the cloud, not the sign counts. Both are
    recorded, but note what the signs do and do not license: `resid`'s gradient is ~1.2 per unit and the
    cloud is ~60 u across, so it spans +-70 there, and "both signs appear" says a boundary is inside the
    sampled set -- it is not a claim that a *zero a plan can land on* is. The hull is the same shape of
    caution one level up: it is a SUPERSET of the sampled cloud, so ``outside the hull`` implies
    unreachable while inside implies nothing.

    So: at <= 4 frames the residual stays 71x to 375x outside `BAND_PROBE` at every second-lobe cell, and
    for 2570 and right it never even changes sign. Which is why the frame-capped pass over all nine
    aimable second-lobe cells -- 779130 candidates, 7.01 M evaluations -- returned 0 genuine, 0 near and
    0 dead-tail."""
    fp = json.load(open(_fx('courtyard_frame_price_s93.json')))
    rows = {r['cell']: r for r in fp['frame_price']['rows']}
    floor = str(ER.FLOOR_FRAMES)
    assert fp['delivered']['frames'] == ER.FLOOR_FRAMES

    # the delivered cell is the control: at the same budget it comes inside the probe
    assert abs(rows[2552]['budgets'][floor]['best_resid']) < EC.BAND_PROBE, "the control must be close"

    for cell in (2561, 2562, 2570, 2581):
        b = rows[cell]['budgets'][floor]
        assert abs(b['best_resid']) > 50 * EC.BAND_PROBE, (cell, b['best_resid'])
    for cell in (2570, 2581):
        b = rows[cell]['budgets'][floor]
        assert not b['crosses'] and (b['neg'] == 0 or b['pos'] == 0), \
            "cell %d must read ONE SIGN over the whole 4-frame cloud" % cell
        assert abs(b['best_resid']) > 1.0, cell
    # and every extra frame buys about an order of magnitude of approach -- monotone, so the axis has a
    # price in frames rather than a wall
    for cell in (2561, 2562):
        best = [abs(rows[cell]['budgets'][str(b)]['best_resid'])
                for b in fp['budgets'] if str(b) in rows[cell]['budgets']]
        assert best == sorted(best, reverse=True), (cell, best)
        assert best[0] / best[-1] > 1000.0, (cell, best)


def test_eighteen_times_the_candidates_moved_the_right_cells_by_nothing():
    """**WHAT RULES OUT DENSITY, and it is a CONTROLLED comparison rather than an argument.**

    A pass returning nothing is ambiguous between "too sparse" and "aimed at empty space". So ask the
    same question at two fan densities: 157291 candidates and 2888346, an 18.4x buy, at the frame floor.

    Cells 2561/2562 come back **bit-identical** -- 0.35417 and 0.430095, the same f64 -- while cell 2553
    sharpens **37x** (1.64e-03 to 4.45e-05) on exactly that extra density. A fan that resolves one cell
    by 37x and another by nothing at all is not short of resolution at the second one. (The right cells'
    minimum is attained at the SAME entry in both fans, i.e. at a point both alphabets already contain.)"""
    fp = json.load(open(_fx('courtyard_frame_price_s93.json')))
    med, full = fp['probe_medium'], fp['probe_full']
    assert full['n_candidates'] > 15 * med['n_candidates']
    m = {(r['cell'], r['thrust']): r for r in med['rows']}
    f = {(r['cell'], r['thrust']): r for r in full['rows']}

    for cell in (2561, 2562):
        k = (cell, 15)
        assert f[k]['min_abs_resid'] == m[k]['min_abs_resid'], cell     # not "close" -- identical
        assert f[k]['entry'] == m[k]['entry'], cell                     # the same candidate, both fans
    near = (2553, 14)
    assert f[near]['min_abs_resid'] < m[near]['min_abs_resid'] / 30.0   # the density DID buy here
    assert f[near]['min_abs_resid'] < 1e-4
    assert f[near]['min_abs_resid'] < f[(2561, 15)]['min_abs_resid'] / 1000.0
    quals = {(q['cell'], q['thrust']) for q in
             json.load(open(_fx('courtyard_qualified_s92.json')))['quals']}
    assert near in quals


def test_the_hull_independently_picks_out_the_two_cells_that_have_ever_been_DELIVERED():
    """**THE MEASUREMENT THAT AGREES WITHOUT BEING TOLD.** The hull knows nothing about residuals: it is
    the fan's walk endpoints and a frame budget. Asked which of session 92's 40 productive
    configurations have a station a 4-frame plan can put the entry on, it answers **cells 2551 and 2552
    only** -- which is exactly, and independently, where the whole 55-candidate console-delivered
    population sits (`courtyard_entry_s90_hits.json`).

    Every cell right of the delivered one, including 2553, is out at the floor. That is the second
    witness to the passes' silence, arrived at from the geometry rather than from the search."""
    hulls = _hulls()
    quals = json.load(open(_fx('courtyard_qualified_s92.json')))['quals']
    rows = ER.reachable_quals(quals, frames=ER.FLOOR_FRAMES, hulls=hulls)
    cells = sorted({r['cell'] for r in rows if r['reachable']})
    assert cells == [2551, 2552], cells

    delivered = json.load(open(_fx('courtyard_entry_s90_hits.json')))['rows']
    assert sorted({ES.aim_cell(r['facing']) for r in delivered}) == cells
    assert all(r['frames'] >= ER.FLOOR_FRAMES for r in delivered)

    # HOW MARGINAL the verdict is decides what it may be quoted for: the delivered stations clear by
    # only ~1.7 u, the second lobe misses by 10-95 u, and the cell NEXT DOOR by 2.26 u.
    h4 = [tuple(p) for p in hulls[ER.FLOOR_FRAMES]['hull']]
    far, near = [], []
    for q in quals:
        ox, oz = ES.roll_entry((0.0, 0.0), q['facing'], q.get('nspeed'))
        p = (q['entry'][0] - ox, q['entry'][1] - oz)
        (far if q['cell'] >= 2561 else near).append(
            min(ER._cross(a, b, p) / (((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
                for a, b in zip(h4, h4[1:] + h4[:1])
                if (b[0] - a[0]) or (b[1] - a[1])))
    assert max(far) < -5.0, "the second-lobe verdict must not be a marginal one: %r" % (max(far),)
    assert all(d > 1.0 for d in near if d > 0), "a station the hull calls reachable must clear its margin"


def test_a_bigger_frame_budget_reaches_strictly_more():
    """The cloud is monotone in the budget -- one more walk frame cannot take reach away -- so the
    hulls have to nest and the reachable-station count cannot fall. Cheap, and it is what catches a
    hull measured off a truncated fan (a clipped `j1` or `base_frames` shrinks the cloud silently)."""
    hulls = _hulls()
    budgets = sorted(hulls)
    if len(budgets) < 2:
        pytest.skip("only one budget measured")
    quals = json.load(open(_fx('courtyard_qualified_s92.json')))['quals']
    counts = []
    for b in budgets:
        rows = ER.reachable_quals(quals, frames=b, hulls=hulls)
        counts.append(sum(1 for r in rows if r['reachable']))
        assert hulls[b]['n_endpoints'] > 0
    assert counts == sorted(counts), dict(zip(budgets, counts))
    # and the endpoint clouds themselves grow with the budget
    assert [hulls[b]['n_endpoints'] for b in budgets] == \
        sorted(hulls[b]['n_endpoints'] for b in budgets)


def test_the_radius_that_was_used_as_the_set_is_far_bigger_than_the_set():
    """`reach_radius` against the cloud it stood in for -- the size of session 92's over-scoping, as a
    number rather than an argument.

    It is not a bug in `reach_radius`: four frames at the cap plus a 26 u roll step really is 94 u, and
    as a BOX for `curve_seeds` to sweep it is the right conservative choice. The error was reading a
    station found inside it as a station a plan can reach."""
    hulls = _hulls()
    h = hulls[ER.FLOOR_FRAMES]
    x0, z0, x1, z1 = h['bbox']
    box = 2.0 * h['reach_radius']
    assert h['reach_radius'] == ES.reach_radius(ER.FLOOR_FRAMES)
    assert (x1 - x0) < box and (z1 - z0) < box
    # the cloud's own bounding box is a small fraction of the box the seeds were swept over
    assert (x1 - x0) * (z1 - z0) < 0.5 * box * box


def test_the_hull_fixture_states_that_only_outside_is_a_claim():
    """The fixture is a MODEL output whose whole point is asymmetric, and a later reader has to be able
    to see that from the file. Same provenance discipline as the pinned qualification."""
    if not os.path.exists(ER.HULL_FIXTURE):
        pytest.skip("no measured walk hull")
    d = json.load(open(ER.HULL_FIXTURE))
    assert 'MODEL OUTPUT' in d['note'] and 'reach_radius' in d['note']
    assert str(ER.FLOOR_FRAMES) in d['hulls']
    for _b, h in d['hulls'].items():
        assert len(h['hull']) >= 3 and h['n_endpoints'] > len(h['hull'])
        # a hull is only as wide as the alphabet that swept it, so the shape is part of the claim
        assert h['fan']['s1_stride'] and h['fan']['s2_stride'] and h['fan']['j1']
