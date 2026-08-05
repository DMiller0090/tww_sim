"""THE STATION QUESTION: is there genuine dust where a frame-floor plan can actually PUT the entry?

Sessions 92-98 priced entry candidates against acceptance bands measured by `entry_search.curve_scan`
inside `reach_radius`'s 94 u BOX, and session 98 measured the cost: 100 of 100 draws priced by a band
from a station 14.5-26.4 u away, 0 of 100 with dust at their own. These gates pin the reason -- the
bands were measured OUTSIDE the reachable set -- and they pin the tool that asks the question over the
measured hull instead (`entry_reach.hull_scan`).

A negative is only worth as much as its control, so the control is a gate and not a comment: the
CONSOLE-DELIVERED clip must be found by the identical call, and cell 2553's known dust must be found one
frame up. Values are exact/pinned model outputs (`[[zero-ulp-tests-only]]`) with a stated positional
tolerance only where a station is compared to an independently-measured one.
"""
import json
import os
import warnings

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

from harness.tetrapush import entry_reach as ER          # noqa: E402
from harness.tetrapush import entry_search as ES         # noqa: E402

warnings.simplefilter('ignore')

BANDS = os.path.join(_ROOT, 'fixtures', 'courtyard_lean_bands_s94.json')
HITS = os.path.join(_ROOT, 'fixtures', 'courtyard_entry_s90_hits.json')
LEDGER = os.path.join(_ROOT, 'fixtures', 'courtyard_draw_ledger_s97.json')

#: The delivered clip's configuration -- cell 2552, and the (thrust, lean) `courtyard_lean_bands_s94`
#: records as ``delivered``.
DELIVERED = dict(facing=40841, thrust=15, lean=64761)
#: The only objective-positive cell at the frame floor (+9 BAM of exit angle over the delivered one).
TARGET = dict(facing=40850, thrust=15, lean=65281)


def _tetra():
    return ES.console_seed()['tetra']


def _rows(cell, thrust=15, productive=True):
    d = json.load(open(BANDS))
    return [r for r in d['rows'] if r['cell'] == cell and r['thrust'] == thrust
            and (not productive or (r['productive'] and r['width'] > 0))]


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _signed(poly, p):
    """Signed distance to a CCW polygon: positive inside, negative outside by that many units."""
    best = float('inf')
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ex, ez = b[0] - a[0], b[1] - a[1]
        n = (ex * ex + ez * ez) ** 0.5
        if n:
            best = min(best, ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / n)
    return best


# ------------------------------------------------------------------ the hull, both directions of it

def test_the_entry_hull_is_the_walk_hull_translated_by_the_roll_step():
    """`reachable` translates the QUERY and `entry_hull` translates the REGION; a scan needs the
    second and the two must be the same factorisation, bit-for-bit."""
    hulls = ER.load()
    walk = [tuple(p) for p in hulls[4]['hull']]
    for facing in (DELIVERED['facing'], TARGET['facing']):
        ox, oz = ES.roll_entry((0.0, 0.0), facing, None)
        got = ER.entry_hull(facing, 4, None, hulls)
        assert len(got) == len(walk)
        for (gx, gz), (wx, wz) in zip(got, walk):
            assert gx == wx + ox and gz == wz + oz


def test_reachable_and_the_entry_hull_agree_on_every_band_station():
    """The two directions are one test apart from each other; if they ever disagree, every negative
    argued from `reachable` and every scan bounded by `entry_hull` are about different sets."""
    hulls = ER.load()
    for cell in (2551, 2552, 2553):
        for r in _rows(cell):
            a = ER.reachable(tuple(r['entry']), r['facing'], frames=4, hulls=hulls, margin=0.0)
            b = ER.contains(ER.entry_hull(r['facing'], 4, None, hulls), tuple(r['entry']), 0.0)
            assert a == b, (cell, r['lean'])


def test_the_console_delivered_entry_is_inside_the_frame_floor_hull():
    """The reachability control. The 4-frame hull is a MODEL output and the delivered clip is a
    CONSOLE fact, so this is the one direction of the test that can falsify the hull itself."""
    row = json.load(open(HITS))['rows'][0]
    assert row['frames'] == 4 and row['facing'] == DELIVERED['facing']
    hulls = ER.load()
    assert ER.reachable(tuple(row['entry']), row['facing'], frames=4, hulls=hulls, margin=0.0)
    assert _signed(ER.entry_hull(row['facing'], 4, None, hulls), tuple(row['entry'])) > 1.0


# --------------------------------------------------- what the lottery's bands were measured outside of

def test_every_band_the_lottery_priced_against_sits_outside_the_frame_floor_hull():
    """THE SESSION-99 FINDING. All 20 of cell 2553's acceptance bands -- the ones `lottery` priced 450
    draws against over sessions 95-98 -- are measured at stations 10-19 u OUTSIDE the set a 4-frame
    plan can reach, and inside the 5-frame one. The emptiness was never Poisson luck and never a
    resolution limit: no draw in that population could clip at any width."""
    hulls = ER.load()
    rows = _rows(2553)
    assert len(rows) == 20
    out = [_signed(ER.entry_hull(r['facing'], 4, None, hulls), tuple(r['entry'])) for r in rows]
    assert max(out) <= -10.195, max(out)        # the CLOSEST is still 10.1956 u outside
    assert min(out) >= -19.400, min(out)        # the furthest, 19.3996
    # One frame up they come inside -- 13 of 20 strictly, 19 of 20 at `reachable`'s own 1 u margin.
    # The margin matters at 5 frames and is irrelevant at 4, which is the shape of the finding.
    up = [_signed(ER.entry_hull(r['facing'], 5, None, hulls), tuple(r['entry'])) for r in rows]
    assert sum(1 for v in up if v > 0.0) == 13
    assert sum(1 for v in up if v > -1.0) == 19


def test_the_held_draws_are_inside_the_hull_that_their_bands_are_outside_of():
    """The two halves of session 98's 21 u transfer distance are ONE fact: the draws are in the
    reachable set and the bands are not. Argued off the LOCKED ledger, not a `_generated/` pass."""
    hulls = ER.load()
    rows = json.load(open(LEDGER))['rows']
    inside = 0
    for r in rows:
        e = ES.roll_entry(tuple(r['walk']), r['facing'], r['nspeed'])
        if _signed(ER.entry_hull(r['facing'], 4, r['nspeed'], hulls), e) >= 0.0:
            inside += 1
    assert inside == len(rows), '%d of %d draws inside' % (inside, len(rows))


# -------------------------------------------------------------------------------- the scan itself

def test_hull_seeds_are_all_leverage_points():
    """`curve_seeds` brackets resid SIGN CHANGES; inside the hull ~93% of the field is a flat plateau
    (the plowed Tetra is out of Co range at the cut), so a sign change there is a JUMP and Newton
    returns `no leverage` from it. Seeding off leverage is what makes the scan able to find anything."""
    tetra = _tetra()
    f = ER.hull_field(tetra, frames=4, **DELIVERED)
    seeds = ER.hull_seeds(tetra, frames=4, sep=6.0, field=f, **DELIVERED)
    assert seeds
    at = {p: g for p, g in zip(f['pts'], f['grad'])}
    for s in seeds:
        assert at[s] >= ER.LEVERAGE_MIN
    assert 0 < f['n_leverage'] < len(f['pts']) // 2       # a thin band, not the whole hull


def test_the_no_leverage_region_is_a_literal_plateau():
    """The claim the seeding change rests on, measured rather than reasoned: where `grad` reads 0 the
    residual does not respond AT ALL, so a sign change across such a region is a jump between two
    plateaus and Newton cannot solve from it. Sampled at 5e-4 u across 0.02 u: a leverage point moves
    smoothly through many distinct residuals, a plateau point returns ONE, bit-identical."""
    tetra = _tetra()
    f = ER.hull_field(tetra, frames=4, **DELIVERED)
    lev = [i for i, g in enumerate(f['grad']) if g >= ER.LEVERAGE_MIN]
    flat = [i for i, g in enumerate(f['grad']) if g < ER.LEVERAGE_MIN]
    assert lev and flat
    ctx, sch, resid = ES.build_fast(DELIVERED['facing'], DELIVERED['lean'], DELIVERED['thrust'],
                                    f['pts'][0])

    def line(p, n=41, dx=5e-4):
        pts = [(tetra[0], tetra[1], p[0] + k * dx, p[1]) for k in range(n)]
        return [resid(o) for o in ctx.sweep_par(pts, 0)]

    plateau = line(f['pts'][flat[len(flat) // 2]])
    assert len(set(plateau)) == 1                       # bit-identical, not merely close
    slope = line(f['pts'][lev[len(lev) // 2]])
    assert len(set(slope)) > 20


def test_the_locus_scan_inside_filter_is_inert_by_default():
    """The one change to `entry_search`: an optional station filter. Additive means BIT-IDENTICAL when
    it is not passed, and total when it rejects everything."""
    tetra = _tetra()
    kw = dict(nspeed=None, span=6.0, step=2.0, half=0.02, n=501)
    a = ES.locus_scan(tetra, DELIVERED['facing'], DELIVERED['thrust'], DELIVERED['lean'],
                      (-1531.1784667969, -781.7215576172), **kw)
    b = ES.locus_scan(tetra, DELIVERED['facing'], DELIVERED['thrust'], DELIVERED['lean'],
                      (-1531.1784667969, -781.7215576172), inside=None, **kw)
    assert a == b
    c = ES.locus_scan(tetra, DELIVERED['facing'], DELIVERED['thrust'], DELIVERED['lean'],
                      (-1531.1784667969, -781.7215576172), inside=lambda q: False, **kw)
    assert (c['stations'], c['live'], c['walkable'], c['live_at']) == (0, 0, 0, [])


def test_hull_scan_finds_the_console_delivered_clip_at_the_frame_floor():
    """THE CONTROL, and the gate that makes every negative below mean something
    (`[[search-space-contains-human]]`). The identical call that reads empty at cell 2553 must find the
    delivered clip's own entry at cell 2552 -- and it lands 0.05 u from the console-delivered one."""
    tetra = _tetra()
    r = ER.hull_scan(tetra, frames=4, sep=6.0, **DELIVERED)
    assert r['live'] > 0 and r['walkable'] > 0, r
    entry = tuple(json.load(open(HITS))['rows'][0]['entry'])
    assert min(_dist(q, entry) for q in r['walkable_at']) < 0.5


def test_cell_2553_has_no_reachable_dust_at_thrust_15():
    """The negative, and note what it is a negative ABOUT: thrust 15, which is what `thrusts=(15,)`
    narrowed every pass to from session 96 on. Measured over all 1040 leans in the slow gate below
    (12823 in-hull stations, 0 live); here the two heaviest leans, which is where the mass is.

    THE NAME MATTERS. Stated of the CELL instead of the configuration this is false - see the
    thrust-14 gate below, which is the same cell at the same frame budget and is alive."""
    tetra = _tetra()
    for lean in (65281, 64761):
        r = ER.hull_scan(tetra, TARGET['facing'], TARGET['thrust'], lean, frames=4, sep=6.0)
        assert r['n_seeds'] > 0 and r['stations'] > 0, r      # the scan looked, and found stations
        assert r['live'] == 0 and r['walkable'] == 0, (lean, r)
        assert r['n_genuine_grid'] == 0


def test_cell_2553_is_alive_at_thrust_14_at_the_same_frame_floor():
    """THE SESSION-99 FINDING THAT OVERTURNED THE CLOSURE, pinned so nobody re-drops the thrust.

    Cell 2553 at thrust 14 carries **918 live walkable stations over 561 of 1040 leans** at the SAME
    4-frame budget where thrust 15 has none (`_generated/s99/thrust14_sweep.json`). The thrust is not a
    frame cost: it selects which roll frame the B edge dispatches the cut on (`cut_step` = thrust + 2),
    and `entry_fan.plan_frames` counts walk holds only - so this is objective-legal at the floor.

    Session 96 dropped thrust 14 on a CLOCK argument ("3.8% of the draws for 24% of the clock") and the
    reachable dust was in it. A scope narrowed for budget became a claim about where the answer is."""
    tetra = _tetra()
    hit = 0
    for lean in (65281, 6, 136, 65151):
        r = ER.hull_scan(tetra, TARGET['facing'], 14, lean, frames=4, sep=6.0)
        assert r['stations'] > 0, (lean, r)
        hit += 1 if r['walkable'] else 0
    assert hit >= 3, 'thrust 14 should be live at most heavy leans, got %d of 4' % hit


def test_the_thrust_14_bands_are_mostly_plateau_which_is_what_the_axis_COSTS():
    """Why a live population is still expensive, and why `lottery` scored it at zero.

    Only 58 of the 918 live stations carry a residual-measurable band; at the rest the residual is FLAT,
    so "is my residual inside the band" is either always or never true and a resid-ranked search cannot
    sample into it. A zero-width band is genuine dust the ranking quantity cannot see - not an absence
    of dust (`clip-band-per-lean.md` is the same mistake on the lean axis)."""
    tetra = _tetra()
    r = ER.hull_scan(tetra, TARGET['facing'], 14, 65151, frames=4, sep=6.0)
    assert r['walkable_at']
    widths = [ES.configuration_band(tetra, TARGET['facing'], 14, 65151, q)['width']
              for q in r['walkable_at']]
    assert any(w > 0.0 for w in widths), widths        # a real band exists at this lean
    assert max(widths) < 1e-4, widths                  # and it is a razor, not a door


def test_cell_2553_dust_appears_one_frame_up():
    """THE COUNTERFACTUAL, which is what localises the negative to the FRAME BUDGET rather than to the
    search. One extra walk frame and the same scan finds dust -- at the station session 94's
    `curve_scan` measured the band at, 0.25 u away."""
    tetra = _tetra()
    r = ER.hull_scan(tetra, TARGET['facing'], TARGET['thrust'], TARGET['lean'], frames=5, sep=6.0)
    assert r['live'] > 0 and r['walkable'] > 0, r
    station = tuple(_rows(2553)[0]['entry'])                  # lean 65281's s94 band station
    assert min(_dist(q, station) for q in r['walkable_at']) < 0.5


@pytest.mark.slow
def test_cell_2553_is_barren_at_thrust_15_across_every_lean_the_fan_reaches():
    """The exhaustive form of the negative: all 1040 leans a frame-floor fan reaches, thrust 15.

    ~28 min. The thrust-14 counterpart is 918 live stations over the same leans, which is why this test
    is named for the thrust and not for the cell."""
    tetra = _tetra()
    leans = [int(k) for k in json.load(open(BANDS))['census']['hist']]
    assert len(leans) == 1040
    live = 0
    for lean in leans:
        live += ER.hull_scan(tetra, TARGET['facing'], TARGET['thrust'], lean, frames=4,
                             sep=6.0)['live']
    assert live == 0
