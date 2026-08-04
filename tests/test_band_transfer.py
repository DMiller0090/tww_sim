"""THE BAND A DRAW IS PRICED WITH WAS MEASURED SOMEWHERE ELSE (session 98).

`entry_score`'s header lists three levels at which this search counted copies as discoveries; session
97 found the fourth, at the pass boundary (`entry_ledger`). This is the fifth, and it is the one that
decides whether the other four were measuring anything: **the acceptance band `lottery` prices a draw
at is not measured at that draw.**

`BandTable` keys a band on (facing, thrust, lean, nspeed) and reuses it for every candidate carrying
that key. Since session 94 the band may be found by `curve_scan`, which marches ALONG the locus until
it finds a station with genuine dust -- a fix for real false negatives, and the reason cell 2553 has a
priced population at all. What it introduced is a transfer assumption nobody stated: the width belongs
to a station the draw is not standing at.

Measured on the 450-draw union of the session 95-98 passes: **100 of 100 sampled draws are priced by
the `curve` rung**, whose station sits **14.5 to 26.4 u away** (median 20.9), and **0 of those 100 have
any genuine point at their own station** -- inside a transverse window ~35x the band's own width, so
the miss is not a resolution artifact.

And the population's single realization of the event `lottery` counts agrees. Across 450 draws E[hits]
reached 1.0971 and exactly one draw landed INSIDE its band (`window_gap` 0.0, the only zero this corner
has ever produced). It is not genuine, bit-for-bit reproducibly.

These gates pin that draw and the mechanism behind it, because it is the one datum that says what
E[hits] on this axis has been counting. ~10 s: two engine evaluations and two band measurements.
"""
import math

from harness.tetrapush import entry_score as SC
from harness.tetrapush import entry_search as ES

#: The one draw in the 450-draw union whose residual landed inside its own quoted band -- camera
#: [16,1,128], pick 5 of the session-98 buy. Kept as literals so the gate needs no `_generated/` pass.
DRAW = dict(facing=40850, m351C=65215, thrust=15, nspeed=26.0,
            walk=(-1511.52392578125, -760.6244506835938),
            entry=(-1529.710205078125, -779.20556640625),
            resid=0.00015499084302434402)


def test_the_only_in_band_draw_this_corner_has_produced_is_not_genuine():
    """THE SESSION-98 RESULT, at the single point that tests it.

    `window_gap` returns 0.0 only for a residual INSIDE the measured acceptance window, so this draw is
    the event `lottery` prices every other draw by its probability of reaching. The engine's `genuine`
    flag is ground truth (`stream_search`: "a band is a measurement of the neighbourhood and never a
    veto on a real hit") and it says no -- so the implication the estimate rests on, band => clip, is
    false at the only place it has ever been tested."""
    seed = ES.console_seed()
    ctx, _sch, resid = ES.CtxPool().get(DRAW['facing'], DRAW['m351C'], DRAW['thrust'],
                                        nspeed=DRAW['nspeed'])
    e = ES.roll_entry(DRAW['walk'], DRAW['facing'], DRAW['nspeed'])
    assert e == DRAW['entry']                       # the entry is a pure function of the walk endpoint
    o = ctx.sweep_par([(seed['tetra'][0], seed['tetra'][1], e[0], e[1])], 0)[0]
    assert resid(o) == DRAW['resid']                # 0-ULP, not a tolerance
    assert bool(o[0]) is False                      # ground truth: NOT a clip

    band = SC.BandTable().get(DRAW['facing'], DRAW['thrust'], DRAW['m351C'], DRAW['nspeed'])
    assert band['productive'] and band['n_genuine'] > 0
    assert band['lo'] <= DRAW['resid'] <= band['hi']            # inside the window it is priced by
    assert ES.window_gap(DRAW['resid'], band) == 0.0


def test_that_bands_station_is_tens_of_units_from_the_draw_it_prices():
    """THE MECHANISM. The band is real -- 43 genuine samples -- and it belongs to a station
    `curve_scan` marched to, not to the draw. At the draw's OWN station there is no genuine dust at
    any residual, so the width it is priced at is not a target it can reach.

    The transverse sweep is +-0.006 u against a gradient of ~0.167 per u, i.e. a residual range ~35x
    the band's own width: a barren answer there is a measurement, not a resolution artifact."""
    seed = ES.console_seed()
    band = SC.BandTable().get(DRAW['facing'], DRAW['thrust'], DRAW['m351C'], DRAW['nspeed'])
    assert band['seed'] == 'curve' and band['escalated']
    away = math.hypot(DRAW['entry'][0] - band['entry'][0], DRAW['entry'][1] - band['entry'][1])
    assert away > 10.0                                          # measured 14.52 u

    own = ES.configuration_band(seed['tetra'], DRAW['facing'], DRAW['thrust'], DRAW['m351C'],
                                DRAW['entry'], nspeed=DRAW['nspeed'])
    assert own['productive'] is False
    assert own['reason'] == 'no genuine on the residual zero'
    assert own['n_genuine'] == 0
    # and the window that answer was taken over really does span the band many times over
    assert 0.006 * band['grad'] > 30 * band['width']
