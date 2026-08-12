"""Gates for `harness.tetrapush.admit_map` -- the admitting-set screen over configuration space (s159).

Every assertion here is exact: bit patterns, counts, and booleans, never a tolerance
(`[[zero-ulp-tests-only]]`). The three that carry the session's findings are

  * the LEAN HAS CELLS -- 1042 reachable leans bake 129 distinct schedules, and the partition is a
    property of the lean and not of the (cell, thrust) it was measured at, which is what turns the map
    from a sampled grid into an enumeration;
  * the SCREEN REDISCOVERS BOTH KNOWN CLIPS from a seed it locates itself
    (`[[search-must-rediscover-known-answer]]`); and
  * the ENTRY IS THE SEPARATING AXIS -- the barren item's own lean admits at the console's entry, and the
    console's own lean does not admit at the barren entry.

Kept inside the per-test budget by pinning the arc on the expensive negative and by leaning on
`lean_runs`'s cache; the wide-arc measurements live in `_notes/s159_*.py` and the KB.
"""
import struct

import pytest

from harness.tetrapush import admit_map as AM
from harness.tetrapush import entry_search as ES

#: `_notes/s155_sweep/w10_t15.json`'s own best-residual row -- the barren item on the console's OWN cell
#: 2552 and thrust 15, restated so a gate does not have to read a probe's output.
BARREN = dict(facing=40833, lean=0, thrust=15, entry=(-1599.9014892578125, -862.4032592773438))

#: Her delivered placement's residual at the console's configuration (+6.242939e-05), as its f64 pattern
#: -- so the ladder is checked against a value and not against itself.
CONSOLE_RESID_BITS = 0x3F105D90_B7C913F7


def bits(v):
    """The f64 bit pattern -- `resid` is a double built from f32 sim outputs, so an f32 round would
    throw away the very digits a razor test is about (`[[zero-ulp-tests-only]]`)."""
    return struct.unpack('<Q', struct.pack('<d', v))[0]


def test_the_lean_has_cells_the_way_the_aim_does():
    """1042 reachable leans -> 129 schedules. The atom of the lean axis, same argument as `aim_cell`."""
    runs = AM.lean_runs()
    ls = AM.reachable_leans()
    assert (ls[0], ls[-1]) == (-775, 266)
    assert len(ls) == 1040                      # -1 and +1 are unreachable: `lean_at_roll`'s decay branch
    assert -1 not in ls and 1 not in ls
    assert len(runs) == 129
    assert min(b - a + 1 for a, b in runs) == 1
    assert max(b - a + 1 for a, b in runs) == 32
    # a partition: contiguous, no gaps, no overlaps, covering the whole hull
    assert runs[0][0] == -775 and runs[-1][1] == 266
    assert all(runs[i][1] + 1 == runs[i + 1][0] for i in range(len(runs) - 1))
    assert sum(b - a + 1 for a, b in runs) == 266 - (-775) + 1
    assert len(AM.lean_classes()) == 129
    assert AM.lean_cell(-775) == 0 and AM.lean_cell(-769) == 0 and AM.lean_cell(-768) == 1
    assert AM.lean_cell(64761) == 0             # the console's own lean, as the game stores it
    assert AM.lean_cell(-776) is None and AM.lean_cell(267) is None


def test_a_lean_run_bakes_one_bit_identical_schedule():
    """The claim under the runs: inside one, every lean is the SAME draw; across one, it is not."""
    fp = AM.schedule_fingerprint
    for lo, hi in AM.lean_runs()[:6]:
        ref = fp(ES.fast_schedule(ES.TAB_FACING, lo & 0xFFFF, 15, ES.TAB_ENTRY))
        for ln in range(lo, hi + 1):
            assert fp(ES.fast_schedule(ES.TAB_FACING, ln & 0xFFFF, 15, ES.TAB_ENTRY)) == ref
        after = fp(ES.fast_schedule(ES.TAB_FACING, (hi + 1) & 0xFFFF, 15, ES.TAB_ENTRY))
        assert after != ref, 'lean %d..%d does not end at %d' % (lo, hi, hi)


def test_the_lean_partition_belongs_to_the_lean_not_the_configuration():
    """Re-derived at another cell and another thrust it is the same partition -- so the map may cache it."""
    lo, hi = -775, -600
    ref = AM.lean_runs(facing=ES.TAB_FACING, thrust=15, leans=range(lo, hi + 1))
    for facing, thrust in ((AM.CONSOLE['facing'], 13), (AM.ACCEPTED['facing'], 14)):
        assert AM.lean_runs(facing=facing, thrust=thrust, leans=range(lo, hi + 1)) == ref


def test_out_of_contact_there_is_no_gradient_to_newton_along():
    """WHY THE LOCATE IS A RAY FAN AND NOT A NEWTON: 5 u off her own row the razor stops depending on
    her at all, so ``mag`` is exactly zero and no descent direction exists."""
    c = AM.CONSOLE
    ctx, _s, rf = ES.build_fast(c['facing'], c['lean'], c['thrust'])
    _gx, _gz, mag, _r, _o = AM.resid_grad(ctx, rf, c['entry'], c['tetra'])
    assert mag > 0.0
    far = (c['tetra'][0] + 5.0, c['tetra'][1] - 3.0)
    _gx, _gz, mag_far, _r, _o = AM.resid_grad(ctx, rf, c['entry'], far)
    assert mag_far == 0.0
    _p, _r, _m, ok = AM.newton_to_zero(ctx, rf, c['entry'], far)
    assert ok is False


def test_the_corrector_cannot_use_an_absolute_tolerance():
    """The residual is QUANTIZED, so a 1e-8 target is unreachable and rejects every station after the
    seed -- the bug that read a 116 u curve as 1 u long. `CORRECT_TOL` is reachable."""
    c = AM.CONSOLE
    ctx, _s, rf = ES.build_fast(c['facing'], c['lean'], c['thrust'])
    off = (c['tetra'][0] + 0.02, c['tetra'][1] + 0.02)
    _p, r, _m, ok = AM.newton_to_zero(ctx, rf, c['entry'], off, tol=AM.CORRECT_TOL)
    assert ok is True and abs(r) < AM.CORRECT_TOL
    _p, _r, _m, ok8 = AM.newton_to_zero(ctx, rf, c['entry'], off, tol=1e-8)
    assert ok8 is False


def test_the_station_ladder_finds_the_console_band_at_her_own_placement():
    """The ladder, run at her delivered placement, returns a band that CONTAINS her own residual --
    checked against the pinned bit pattern, not against the ladder's own output."""
    c = AM.CONSOLE
    ctx, _s, rf = ES.build_fast(c['facing'], c['lean'], c['thrust'])
    gx, gz, mag, r0, _o = AM.resid_grad(ctx, rf, c['entry'], c['tetra'])
    assert bits(r0) == CONSOLE_RESID_BITS
    b = AM.station_band(ctx, rf, c['entry'], c['tetra'], gx, gz, mag, r0)
    assert b['genuine'] > 0
    assert b['lo'] <= r0 <= b['hi']
    assert b['lo'] > 0.0, 'the band is strictly positive -- resid = 0 is the value the razor refuses'


def test_the_screen_rediscovers_both_known_clips():
    """**THE REDISCOVERY GATE.** Both delivered configurations, from their own entries, with HER SEED
    FOUND BY THE SCREEN's own ray fan rather than handed in."""
    for cfg in (AM.CONSOLE, AM.ACCEPTED):
        r = AM.screen(cfg['facing'], cfg['lean'], cfg['thrust'], entry=cfg['entry'],
                      first_only=True)
        assert r['admits'] is True, cfg
        assert r['admitting'] >= 1 and r['stations'] >= 1
        assert r['lo'] is not None and r['lo'] > 0.0
        assert r['reason'] == ''
        assert r['cell'] == ES.aim_cell(cfg['facing'])


def test_the_entry_is_the_separating_axis_not_the_lean():
    """The 2x2 cross: the BARREN item's own lean admits at the console's entry, and the console's own
    lean does not admit at the barren entry -- 106 u away, on the same cell 2552 and thrust 15.

    The negative is pinned to a short arc to stay in the per-test budget; the full-arc measurement
    (155 stations, 7 components, 0 admitting) is in `_notes/s159_cross.py`."""
    assert ES.aim_cell(AM.CONSOLE['facing']) == ES.aim_cell(BARREN['facing']) == 2552
    assert AM.CONSOLE['thrust'] == BARREN['thrust'] == 15
    swap = AM.screen(AM.CONSOLE['facing'], BARREN['lean'], AM.CONSOLE['thrust'],
                     entry=AM.CONSOLE['entry'], first_only=True)
    assert swap['admits'] is True, 'the barren lean admits at an admitting entry'
    dead = AM.screen(AM.CONSOLE['facing'], AM.CONSOLE['lean'], AM.CONSOLE['thrust'],
                     entry=BARREN['entry'], first_only=True, arc=4.0)
    assert dead['admits'] is False
    assert dead['reason'] == 'no_band' and dead['stations'] > 0


def test_a_verdict_quotes_the_window_it_was_read_over():
    """s158's discipline, enforced: a zero from this screen carries the arc, the ray fan and the station
    count it stands on, and names WHICH negative it is."""
    r = AM.screen(AM.CONSOLE['facing'], AM.CONSOLE['lean'], AM.CONSOLE['thrust'],
                  entry=AM.CONSOLE['entry'], first_only=True)
    for k in ('arc', 'arc_neg', 'arc_pos', 'bearings', 'step', 'stations', 'components', 'seeds',
              'tested', 'reason', 'entry', 'co'):
        assert k in r, k
    assert r['reason'] in ('', 'no_curve', 'no_band')
    assert r['bearings'] == AM.SEED_BEARINGS and r['step'] == AM.STATION_STEP


def test_the_screen_is_deterministic():
    """Two screens of one configuration agree BIT-EXACTLY -- no tolerance, and no run-to-run drift from
    the OpenMP fan-out underneath."""
    a = AM.screen(AM.ACCEPTED['facing'], AM.ACCEPTED['lean'], AM.ACCEPTED['thrust'],
                  entry=AM.ACCEPTED['entry'], first_only=True)
    b = AM.screen(AM.ACCEPTED['facing'], AM.ACCEPTED['lean'], AM.ACCEPTED['thrust'],
                  entry=AM.ACCEPTED['entry'], first_only=True)
    assert (a['admits'], a['stations'], a['admitting'], a['components']) == \
           (b['admits'], b['stations'], b['admitting'], b['components'])
    assert bits(a['lo']) == bits(b['lo']) and bits(a['hi']) == bits(b['hi'])


def test_her_seeds_land_on_the_razor_and_in_contact():
    """The locate's contract: every seed it returns is IN Co contact at the cut (so the razor depends on
    her there) and is ON the curve -- a bracket across a residual DISCONTINUITY is dropped, not walked."""
    c = AM.CONSOLE
    ctx, sch, rf = ES.build_fast(c['facing'], c['lean'], c['thrust'])
    from harness.tetrapush import cut_contact as CC
    br = CC.braced_row(c['facing'], c['lean'], c['thrust'], ctx=ctx, sch=sch, resid=rf)
    seeds = AM.her_seeds(ctx, rf, c['entry'], br['co'])
    assert len(seeds) > 0
    for s in seeds:
        _gx, _gz, mag, r, _o = AM.resid_grad(ctx, rf, c['entry'], s)
        assert mag > 0.0, 'a seed out of contact has no razor to walk'
        assert abs(r) < AM.CORRECT_TOL, 'a seed must already be ON the curve, not near a jump'


@pytest.mark.parametrize('lean', [-775, 0, 266])
def test_the_screen_runs_at_every_corner_of_the_reachable_lean_range(lean):
    """No configuration in the map's own lean hull raises, and each returns a well-formed verdict."""
    r = AM.screen(AM.CONSOLE['facing'], lean, AM.CONSOLE['thrust'], entry=AM.CONSOLE['entry'],
                  first_only=True, arc=4.0)
    assert isinstance(r['admits'], bool)
    assert AM.lean_cell(lean) is not None
