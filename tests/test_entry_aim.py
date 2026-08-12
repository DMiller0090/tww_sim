"""Gates for `harness.tetrapush.entry_aim` -- the razor's target in u of Link's entry (s160).

Everything here is exact: identities, bit patterns and booleans, never a tolerance
(`[[zero-ulp-tests-only]]`). The load-bearing ones are

  * both DELIVERED rows price at ``offset_u == 0`` -- the control the whole module rests on;
  * `aim` DISPLACED 0.5 u off a known clip walks back onto a genuine one, so the tool finds a clip from a
    state where one exists (`[[search-must-rediscover-known-answer]]`);
  * the band is SUFFICIENT ALONG THE ENTRY AXIS -- in-band and genuine are the SAME set of rows, which is
    what licenses pricing a row by its residual at all; and
  * `walk_end_for` inverts `entry_search.roll_entry` onto the locked fixture's own recorded walk endpoint,
    bit for bit -- the conversion the planner steers on.
"""
import math
import struct

import pytest

from harness.tetrapush import admit_map as AM
from harness.tetrapush import entry_aim as EA
from harness.tetrapush import entry_search as ES
from harness.tetrapush import razor_band as RB

CONFIGS = [AM.CONSOLE, AM.ACCEPTED]
IDS = [c['tag'] for c in CONFIGS]

#: `fixtures/courtyard_clip_s90_console.json`'s own ``hit['walk']``, restated so the inverse is checked
#: against the LOCKED fixture -- exact f32 values, never rounded (`[[full-fp-precision-coords]]`).
CONSOLE_WALK_END = (-1513.0206298828125, -763.112548828125)


def bits32(v):
    return struct.unpack('<I', struct.pack('<f', float(v)))[0]


@pytest.fixture(scope='module')
def built():
    """One ctx per configuration -- a ShoveCtx copies the whole collision mesh, so this is the fixture
    every test here shares rather than paying 1.5 ms and a schedule bake each."""
    out = {}
    for cfg in CONFIGS:
        ctx, sch, resid = ES.build_fast(cfg['facing'], cfg['lean'] & 0xFFFF, cfg['thrust'])
        band = EA.band_for(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'],
                           ctx=ctx, sch=sch, resid=resid)
        out[cfg['tag']] = (ctx, sch, resid, band)
    return out


@pytest.mark.parametrize('cfg', CONFIGS, ids=IDS)
def test_a_delivered_row_prices_at_zero_offset(cfg, built):
    """**THE CONTROL.** Each row this work has actually delivered is genuine, inside its own band, and
    therefore exactly 0 u of entry from clipping."""
    ctx, sch, resid, band = built[cfg['tag']]
    p = EA.price(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'], band=band,
                 ctx=ctx, sch=sch, resid=resid)
    assert p['genuine'] is True
    assert p['band_sufficient'] is True
    assert RB.in_band(band, p['resid']) is True
    assert p['band_distance'] == 0.0
    assert p['offset_u'] == 0.0
    assert p['in_contact'] is True
    assert p['strip_u'] > 0.0


@pytest.mark.parametrize('cfg', CONFIGS, ids=IDS)
def test_the_aim_walks_a_displaced_entry_back_onto_a_clip(cfg, built):
    """**THE REDISCOVERY GATE.** 0.5 u off each delivered entry -- thousands of strip-widths -- `aim`
    returns an entry the SIM calls genuine, and it is a clip, not a converged residual."""
    ctx, sch, resid, band = built[cfg['tag']]
    off = (cfg['entry'][0] + 0.5, cfg['entry'][1] - 0.5)
    before = EA.price(cfg['facing'], cfg['lean'], cfg['thrust'], off, cfg['tetra'], band=band,
                      ctx=ctx, sch=sch, resid=resid)
    assert before['genuine'] is False, 'the displaced start must not already be a clip'
    got = EA.aim(cfg['facing'], cfg['lean'], cfg['thrust'], off, cfg['tetra'], band=band, ctx=ctx,
                 sch=sch, resid=resid)
    assert got['ok'] is True and got['genuine'] is True and got['reason'] == ''
    assert got['moved'] > 0.1
    # and the entry it returns is genuine when re-swept from scratch, not just inside the Newton
    row = ctx.sweep_par([(cfg['tetra'][0], cfg['tetra'][1], got['entry'][0], got['entry'][1])], 0,
                        extra=True)[0]
    assert bool(row[0]) is True
    # NOT `in_band`: the band DRIFTS with the entry (7% of a width at 0.70 u, so the drift is bounded
    # rather than absent) -- knowledge/model/entry-strip.md, "Two traps, both measured".
    assert abs(RB.band_distance(band, resid(row))) < band['width']


@pytest.mark.parametrize('cfg', CONFIGS, ids=IDS)
def test_the_entry_gradient_does_not_die_out_of_contact_but_hers_does(cfg, built):
    """**THE TWO AXES ARE NOT SYMMETRIC**, which is why `entry_grad`'s ``mag`` is not a contact test.

    `admit_map.resid_grad` returns EXACTLY 0 once she leaves Co range -- the razor stops depending on her.
    Displace LINK'S ENTRY by the same 400 u and the gradient is still order 1, because ``resid`` is the
    cut RAY's offset from the seam vertex and his entry always moves the ray."""
    ctx, sch, resid, _band = built[cfg['tag']]
    far = (cfg['entry'][0] + 400.0, cfg['entry'][1] + 400.0)
    _gx, _gz, mag, _r, row = EA.entry_grad(ctx, resid, cfg['tetra'], far)
    assert bool(row[0]) is False
    assert mag > 0.1, 'the entry axis keeps its leverage far from contact'
    her_far = (cfg['tetra'][0] + 400.0, cfg['tetra'][1] + 400.0)
    _gx, _gz, her_mag, _r, _o = AM.resid_grad(ctx, resid, cfg['entry'], her_far)
    assert her_mag == 0.0, 'hers dies -- the asymmetry this test exists to pin'


@pytest.mark.parametrize('cfg', CONFIGS, ids=IDS)
def test_the_band_is_sufficient_along_the_entry_axis_too(cfg, built):
    """s158 measured ``resid in band <=> genuine`` sweeping HER plane. It holds sweeping LINK'S ENTRY as
    well -- the two sets are IDENTICAL over the window, which is what makes `offset_u` a distance to a
    clip rather than to a residual. The window is quoted (s158's discipline) and small enough to gate."""
    ctx, sch, resid, band = built[cfg['tag']]
    half, step = 0.005, 1.0e-4
    n = int(2.0 * half / step) + 1
    pts = [(cfg['entry'][0] - half + i * step, cfg['entry'][1] - half + j * step)
           for i in range(n) for j in range(n)]
    rows = ctx.sweep_par([(cfg['tetra'][0], cfg['tetra'][1], p[0], p[1]) for p in pts], 0,
                         extra=True)
    gen = {i for i, o in enumerate(rows) if o[0]}
    inb = {i for i, o in enumerate(rows) if RB.in_band(band, resid(o))}
    assert gen, 'the window must contain the delivered clip'
    assert gen == inb, 'in-band and genuine disagree on %d of %d rows' % (len(gen ^ inb), len(rows))


def test_offset_u_is_the_band_distance_over_the_gradient(built):
    """The identity, exactly -- so the number can never drift from what it claims to be."""
    cfg = AM.CONSOLE
    ctx, sch, resid, band = built[cfg['tag']]
    e = (cfg['entry'][0] + 0.25, cfg['entry'][1])
    gx, gz, mag, r, _row = EA.entry_grad(ctx, resid, cfg['tetra'], e)
    assert mag == math.hypot(gx, gz)
    assert EA.offset_u(band, r, mag) == RB.band_distance(band, r) / mag
    assert EA.offset_u(band, r, 0.0) is None, 'a dead gradient is not a distance'
    assert EA.offset_u(dict(lo=None), r, mag) is None


def test_a_row_out_of_the_clip_overlap_band_is_priced_but_not_a_clip(built):
    """Contact is the OVERLAP's question, not the gradient's: a far entry still has leverage and still
    gets a price, and it is `aim`'s job -- not the price's -- to say whether a clip is reachable from it."""
    cfg = AM.CONSOLE
    ctx, sch, resid, band = built[cfg['tag']]
    far = (cfg['entry'][0] + 400.0, cfg['entry'][1] + 400.0)
    p = EA.price(cfg['facing'], cfg['lean'], cfg['thrust'], far, cfg['tetra'], band=band, ctx=ctx,
                 sch=sch, resid=resid)
    assert p['genuine'] is False
    assert p['offset_u'] is not None and abs(p['offset_u']) > 1.0
    assert p['cell'] == ES.aim_cell(cfg['facing']) and p['thrust'] == cfg['thrust']


def test_walk_end_for_inverts_the_roll_entry_onto_the_locked_fixture():
    """**THE CONVERSION THE PLANNER STEERS ON**, pinned to the fixture: the console's delivered entry
    inverts to the walk endpoint its own locked ``hit['walk']`` records, bit for bit, and forward
    `roll_entry` round-trips it exactly."""
    cfg = AM.CONSOLE
    w = EA.walk_end_for(cfg['entry'], cfg['facing'])
    assert bits32(w['walk_end'][0]) == bits32(CONSOLE_WALK_END[0])
    assert bits32(w['walk_end'][1]) == bits32(CONSOLE_WALK_END[1])
    assert w['exact'] is True and w['error'] == 0.0
    fwd = ES.roll_entry(CONSOLE_WALK_END, cfg['facing'], ES.ROLL_NSPEED)
    assert bits32(fwd[0]) == bits32(cfg['entry'][0])
    assert bits32(fwd[1]) == bits32(cfg['entry'][1])


def test_the_strip_is_the_band_width_divided_by_the_leverage(built):
    """The razor's target, in u: ~1.2e-04 at the console's configuration and ~6.8e-05 at s154's. Asserted
    as a RANGE of magnitude rather than a pinned float because the FD gradient is the instrument, not the
    finding -- what must not drift is that the strip is sub-milliunit and the leverage is order 1."""
    for cfg in CONFIGS:
        ctx, sch, resid, band = built[cfg['tag']]
        p = EA.price(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'],
                     band=band, ctx=ctx, sch=sch, resid=resid)
        assert 0.1 < p['mag'] < 10.0, 'the entry is a peer axis of hers, not a dead one'
        assert 1e-05 < p['strip_u'] < 1e-03
        assert p['strip_u'] == band['width'] / p['mag']
