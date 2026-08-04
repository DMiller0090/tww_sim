"""A PASS IS PRICED AGAINST THE DRAWS ALREADY HELD (session 97).

`entry_score`'s header lists three times this search counted copies as discoveries -- a lean-0 band, a
camera priced at 8.00x, 118 genuine scorings that were 23 draws. Each was fixed at the level it
happened, and the fix stopped at the pass boundary every time. This is the fourth level: two passes,
each honest inside itself, whose populations OVERLAP.

It is not a hypothetical. Session 96 measured three shapes at 0.127 / 0.087 / 0.045 draws per second
and handed the next session an instruction to buy the first and skip the third. In NEW draws -- the
only currency `lottery` is additive in -- the ranking REVERSES: the local camera neighbourhood is 6 new
of 31, because a neighbourhood of a productive camera is enriched in that camera's OWN draws.

These gates pin:

* the ARITHMETIC -- a draw already in the ledger is not a new draw, and the rows sum to the union;
* the MEASUREMENT -- the session-96 numbers, off a tracked extract rather than gitignored pass output;
* the SATURATION -- the axis's marginal yield per camera, which is the shape of the curve and the
  reason a whole-alphabet sweep is not repeatable at its own average rate;
* the PREMISE `lottery` rests on -- residuals locally uniform across the window, which the population
  can test for free and which holds;
* the TRAP -- a ledger's opening pass is 100% new by construction, so its rate is not one anything can
  be budgeted at. That is the arithmetic shape of how session 96 got 0.157 draws/s.

Offline, off `fixtures/courtyard_draw_ledger_s97.json`. No Dolphin, no fan, ~1 s.
"""
import json
import os

from harness.tetrapush import entry_ledger as EL
from harness.tetrapush import entry_score as SC


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', name)


EXTRACT = _fx('courtyard_draw_ledger_s97.json')


def _row(walk, lean, gap, width=2.8125e-05, facing=40841, thrust=15, nspeed=26.0):
    return (gap, dict(walk=list(walk), m351C=lean, facing=facing, thrust=thrust, nspeed=nspeed,
                      width=width))


# ------------------------------------------------------------------------------- the arithmetic

def test_a_draw_already_held_is_not_a_new_draw():
    """`novel` keys on `entry_score.draw_key`, so the SAME endpoint reached by a different camera is a
    copy however different the input that reached it was. That is the whole point: a ticket is the
    entry, not the C-stick path that walked to it."""
    a = [_row((1.5, 2.5), 64761, 1e-3), _row((3.5, 4.5), 64761, 2e-3)]
    b = [_row((1.5, 2.5), 64761, 5e-4),                      # same draw, tighter gap
         _row((3.5, 4.5), 65281, 2e-3)]                      # same walk, DIFFERENT lean -> new
    held = EL.draw_ids(a)
    fresh = EL.novel(b, held)
    assert len(fresh) == 1
    assert fresh[0][1]['m351C'] == 65281
    # and a draw is not made new by being reported twice inside the same pass
    assert len(EL.novel(b + b, held)) == 1


def test_the_ledger_rows_sum_to_the_union():
    """E[hits] is a SUM over draws, so it is additive only over the ones nothing before contributed.
    The ledger's per-pass `new_expected_hits` must therefore add up to the union's E[hits] exactly --
    if they did not, the row numbers could not be quoted next to each other."""
    led = EL.ledger_of(EXTRACT)
    p = led.price()
    assert abs(sum(r['new_expected_hits'] for r in led.rows) - p['total_expected_hits']) < 1e-12
    assert sum(r['n_new'] for r in led.rows) == p['total_draws']
    # and the union is strictly smaller than the pooled count the three passes report separately
    assert p['total_draws'] < sum(r['n_draws'] for r in led.rows)


def test_the_opening_pass_of_a_ledger_is_not_a_rate():
    """THE TRAP, as arithmetic. The first pass into an empty ledger is 100% new whatever it measured,
    so quoting its rate as the price of another pass is the mistake in its purest form. `price` reports
    a marginal rate over the passes that actually faced a non-empty ledger, and None when there are
    none."""
    led = EL.Ledger()
    led.add('first', [dict(near_detail=[dict(_row((1.5, 2.5), 64761, 1e-3)[1], gap=1e-3)])],
            seconds=10.0)
    assert led.rows[0]['against'] == 0
    assert led.rows[0]['new_share'] == 1.0
    assert led.price()['marginal_per_second'] is None       # nothing here can be budgeted at
    led.add('second', [dict(near_detail=[dict(_row((1.5, 2.5), 64761, 1e-3)[1], gap=1e-3)])],
            seconds=10.0)
    assert led.rows[1]['against'] == 1 and led.rows[1]['n_new'] == 0
    assert led.price()['marginal_per_second'] == 0.0         # measured zero, not absent


# ------------------------------------------------------------- the session-96 measurement, tracked

def test_the_camera_neighbourhood_re_draws_its_parent_pass():
    """**THE SESSION-97 RESULT.** Session 96 found a local camera neighbourhood returning 0.127 draws
    per second against 0.087 for the whole alphabet, called it a 1.46x enrichment, and made it the next
    session's buy. Measured against the population it was run after: **6 of its 31 draws are new**.

    The enrichment is real and it is enrichment in the PARENT's draws -- neighbouring cameras command
    ~94% of the same walk directions, so they reach the same entries. A rate measured on a pass's own
    population always over-reports by exactly the overlap it does not look for."""
    led = EL.ledger_of(EXTRACT)
    rows = {r['label']: r for r in led.rows}
    nb, dn = rows['neighbourhood'], rows['densify']
    assert (nb['n_draws'], nb['n_new']) == (31, 6)
    assert nb['new_share'] < 0.25
    assert (dn['n_draws'], dn['n_new']) == (40, 29)
    assert dn['new_share'] > 0.70
    # THE OBVIOUS OBJECTION, closed: the box contains its own centre, so drop that camera's rows and
    # the answer does not move. Different cameras reach the same entries, which is the claim.
    rows = [(r['gap'], r) for r in json.load(open(EXTRACT))['rows']
            if r['source'] == 'neighbourhood' and r['camera'] != '16,32,128']
    parent = EL.draw_ids(EL.from_extract(EXTRACT, 'walk16'))
    assert len(SC.dedupe_near(rows)) == 31 and len(EL.novel(rows, parent)) == 6
    cams = {r['camera'] for _g, r in EL.from_extract(EXTRACT, 'neighbourhood')}
    assert len(cams) == 35
    assert len(cams & {r['camera'] for _g, r in EL.from_extract(EXTRACT, 'walk16')}) == 1


def test_the_session_96_ranking_of_the_three_shapes_inverts():
    """The ranking is the actionable half, and it reverses. Reported: neighbourhood 0.127 > alphabet
    0.087 > camera x paying shape 0.045, so session 96 said buy the neighbourhood and skip the product.
    In new draws per second the product is FIRST and the neighbourhood LAST, and the three sit within
    35% of each other rather than spanning 2.8x."""
    led = EL.ledger_of(EXTRACT)
    rows = {r['label']: r for r in led.rows}
    reported = {k: rows[k]['reported_per_second'] for k in rows}
    new = {k: rows[k]['new_per_second'] for k in rows}
    assert reported['neighbourhood'] > reported['walk16'] > reported['densify']      # as published
    assert new['densify'] > new['neighbourhood']                                     # inverted
    assert max(new.values()) / min(new.values()) < 4.0
    # and the number a budget uses is the marginal one, which is the product's
    assert led.price()['marginal_per_second'] == new['densify']


def test_the_camera_axis_saturates_on_draws():
    """WHY THE OVERLAP IS STRUCTURAL AND NOT AN ARTIFACT OF WHERE THE NEIGHBOURHOOD WAS CENTRED.

    Averaged over random orderings of the 196 cameras, the marginal yield falls from **~4.3 draws at
    the first camera to ~0.23 over the last quarter** -- an ~18x decay, the coupon-collector shape of
    sampling a population much smaller than the sample count. An axis whose cameras drew independently
    would hold that rate flat, and the supply table (196 / 709 / 2394 / 5300 clouds) bounds TICKETS
    with no claim on draws.

    Stated as a rate: 0.23 draws over 7.46 s a camera is **0.031 new draws per second at the end of the
    sweep**, which is where all three shapes land."""
    a = EL.accumulation(EL.extract_cameras(EXTRACT, 'walk16'), trials=12, seed=1)
    assert a['n_cameras'] == 196
    assert a['total'] == 127.0                                   # the deduped union, exactly
    assert 3.5 < a['first'] < 5.0
    assert 0.15 < a['marginal_last_quarter'] < 0.35
    assert a['first'] / a['marginal_last_quarter'] > 10.0
    # monotone and concave: every camera adds something, and never more than the one before on average
    c = a['curve']
    assert all(c[i + 1] >= c[i] for i in range(a['n_cameras']))
    assert (c[196] - c[98]) < (c[98] - c[1])


def test_the_lottery_premise_holds_so_e_hits_is_proportional_to_draws():
    """`lottery` prices each draw at ``width / (2 * near_gap)`` on the premise that its residual is
    locally UNIFORM across the window. The population tests that for free, and it holds: observed
    counts run 1.00 to 1.18 of the uniform expectation from 3e-3 down to 1e-4.

    So there is no hidden crowding toward zero to be harvested, E[hits] is proportional to the distinct
    draw count, and buying draws is the only thing that moves it."""
    u = EL.uniformity(EL.from_extract(EXTRACT, 'walk16'))
    assert u['n_draws'] == 127
    deep = [r for r in u['rows'] if 1e-4 <= r['under'] <= 3e-3]
    assert len(deep) >= 3
    for r in deep:
        assert 0.8 < r['ratio'] < 1.5, "residuals are not uniform at %g: %s" % (r['under'], r['ratio'])
    # the record approach is one order statistic, not a trend: ~4x the expectation at the deepest
    # threshold is what 127 uniform draws produce about a tenth of the time
    assert u['rows'][0]['observed'] == 1


def test_the_band_width_ceiling_is_small_so_there_is_no_width_lever():
    """The other factor in E[hits] is the band width, and it is nearly pinned. The draws land at
    2.61e-05 and 2.81e-05, and the widest band ANY lean carries at cell 2553 is 3.25e-05 -- so perfect
    lean steering is worth **1.26x**, against the 3.0x the draw-count axis was thought to hold.

    Which is what makes this cell's arithmetic simple, and worth stating rather than re-deriving: the
    only lever on E[hits] here is the number of distinct draws."""
    rows = json.load(open(_fx('courtyard_lean_bands_s94.json')))['rows']
    at_2553 = [r for r in rows if r['cell'] == 2553 and r.get('width')]
    widest = max(r['width'] for r in at_2553)
    assert 3.0e-05 < widest < 3.6e-05
    drawn = sorted({round(r['width'], 12) for _g, r in EL.from_extract(EXTRACT, 'walk16')})
    assert widest / max(drawn) < 1.30
    # `lottery` sums over the rows it is HANDED, so it must be fed draws and not reported near-misses:
    # the 816 rows of this pass are 127 draws, and pricing the raw rows reads 6.4x high
    ded = SC.dedupe_near(EL.from_extract(EXTRACT, 'walk16'))
    assert len(ded) == 127
    per_draw = SC.lottery(ded, SC.BAND_PROBE) / float(len(ded))
    assert 0.0024 < per_draw < 0.0028


def test_the_extract_is_the_passes_it_was_taken_from():
    """The fixture exists because a pass writes to the gitignored `_generated/`, so a finding argued off
    one is not reproducible from a clone. It is only worth that if it is faithful: the per-source
    reported counts and clocks are the passes' own."""
    d = json.load(open(EXTRACT))
    by = {s['label']: s for s in d['sources']}
    assert by['walk16']['n_cameras'] == 196 and by['walk16']['n_reported'] == 816
    assert by['densify']['n_cameras'] == 1 and by['densify']['n_reported'] == 40
    assert abs(by['walk16']['seconds'] - 1461.5) < 1.0
    assert d['near_gap'] == SC.BAND_PROBE
    assert len(d['rows']) == sum(s['n_reported'] for s in d['sources'])
    for r in d['rows'][:50]:
        assert set(EL.IDENT_FIELDS) <= set(r)                 # `draw_key` can be taken of every row
