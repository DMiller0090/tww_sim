"""THE BAND WAS A NEGATIVE ARGUED FROM ONE STATION, and the entry lean is what exposed it (session 94).

`entry_score.configuration_band` Newtons the entry onto the residual zero from a SEED, and `BandTable`
handed it one seed for every key -- the single global `ref_entry`. The locus MOVES with the entry lean,
so that seed can be on the curve at lean 0 and off it entirely at lean 64761. It is precisely the
failure fixed at the QUALIFICATION twice (s90 `escalate` -> `locus_scan`, s92 `curve` -> `curve_scan`)
and never fixed one level down at the band.

What it cost: session 93 ran the frame floor at cell 2553, put **180 candidates inside `BAND_PROBE`**,
converted none, and concluded that every one sat at a lean whose band had no usable width. Re-run with
the ladder, the SAME 779130 candidates report **34 near-misses and E[hits] 0.079** -- a live, priced
lottery where the pass had reported a dead cell. A dead band never suppressed a clip (`stream_search`
reports `genuine` from the sweep), but it silences the whole near-miss population, which is the only
thing `lottery` is computed from and therefore the only thing that says whether a cell is worth density.

These gates pin the licence (the old table called the console-delivered clip's OWN configuration dead),
the recovery, the ladder's order-independence, the cache hygiene that stops a stale negative surviving
the fix, and the scoping contract.

Offline: the native fan + analytic schedules, no Dolphin.
"""
import json
import os

import pytest

from harness.tetrapush import entry_lean as EL
from harness.tetrapush import entry_score as SC
from harness.tetrapush import entry_search as ES


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', name)


def _clip():
    """The console-delivered clip's own hit row -- facing 40841 (cell 2552), thrust 15, lean 64761."""
    return json.load(open(_fx('courtyard_clip_s90_console.json')))['hit']


def _quals():
    return json.load(open(_fx('courtyard_qualified_s92.json')))['quals']


def _measurement():
    if not os.path.exists(EL.LEAN_FIXTURE):
        pytest.skip("no lean measurement at %s -- run `entry_lean bands`" % EL.LEAN_FIXTURE)
    return EL.load()


# ------------------------------------------------------------------------------ the licence

@pytest.mark.slow
def test_the_old_band_table_called_the_delivered_clips_own_configuration_dead():
    """**THE LICENCE, and it is the harshest form of `[[search-space-contains-human]]`.**

    The clip at `fixtures/courtyard_clip_s90_console.json` was delivered to console and clipped. Ask the
    session-93 table -- one seed, no ladder -- for the band at that clip's own (facing, thrust, lean) and
    it answers `no genuine on the residual zero`. A scoring whose ranking says the known-good,
    console-confirmed input has no band is broken, whatever it then says about anything else.

    The ladder answers PRODUCTIVE at the same key, off the same code, having only been given somewhere
    else on the same curve to start from."""
    h = _clip()
    seed = ES.console_seed()
    fac, thr, lean = h['facing'], h['thrust'], h['m351C']
    old = SC.BandTable(seed, path=None, escalate=False)
    new = SC.BandTable(seed, path=None, quals=_quals())

    b_old = old.get(fac, thr, lean)
    assert not b_old['productive'], "the s93 table must be reproduced, not assumed"
    assert b_old['reason'] == 'no genuine on the residual zero', b_old['reason']

    b_new = new.get(fac, thr, lean)
    assert b_new['productive'], "the ladder must find the delivered configuration's own band"
    assert b_new['n_genuine'] > 0 and b_new['escalated'] and b_new['seed'] == 'curve'


@pytest.mark.slow
def test_the_console_clip_scores_genuine_through_stream_search_with_one_escalated_band():
    """END TO END, on the one candidate whose answer is known from console.

    Stream the delivered clip's own (walk endpoint, m351C) as a one-candidate fan at its own
    configuration: `stream_search` must return it GENUINE at the fixture's exact entry and residual, and
    must have escalated a band to do the scoring. That last clause is the regression that matters -- it
    is what fails if a refactor stops handing the quals to the table and the ladder loses its second
    rung."""
    h = _clip()
    seed = ES.console_seed()
    quals = SC.select_quals(SC.qualified(seed), cells=(ES.aim_cell(h['facing']),),
                            thrusts=(h['thrust'],))
    pairs = [((h['walk'][0], h['walk'][1], h['m351C_walk']), tuple(h['plan']))]
    r = SC.stream_search(pairs, seed=seed, quals=quals,
                         bands=SC.BandTable(seed, quals=quals, path=None))

    assert r['n_hit_draws'] == 1 and r['n_dead_lean'] == 0
    hit = r['hits'][0]
    assert hit['entry'] == h['entry']                 # 0-ULP: the same f32 pair, not "close"
    assert hit['resid'] == h['resid']
    assert (hit['facing'], hit['thrust'], hit['m351C']) == (h['facing'], h['thrust'], h['m351C'])
    assert r['n_bands_escalated'] >= 1, "the ladder must be live inside a real pass"


# ------------------------------------------------------------------- what the ladder recovers

def test_the_ladder_recovers_cell_2553_and_thrust_14_is_the_genuinely_dead_one():
    """**THE FINDING.** Cell 2553 (+9 BAM of exit angle, the whole axis left at the frame floor) reads 0
    of the 24 heaviest fan leans usable under one seed and 20 of 24 under the ladder, at thrust 15 --
    so session 93's "every candidate lands at a lean whose band has no usable width" was a statement
    about the seed and not about the lean.

    Thrust 14 at the same cell is dead at every one of them even escalated, which is worth pinning
    because the s93 handoff pointed the next session at thrust 14 (the fine probe's closest approach,
    4.45e-05, is there). Closest approach and band width are different quantities."""
    fx = _measurement()
    rows = [r for r in fx['rows'] if r['cell'] == 2553]
    assert rows, "the measurement must cover cell 2553"
    t15 = [r for r in rows if r['thrust'] == 15]
    t14 = [r for r in rows if r['thrust'] == 14]
    assert len(t15) >= 20 and len(t14) >= 20

    assert sum(1 for r in t15 if r['usable']) >= 15, \
        "thrust 15 must recover most of its leans: %d of %d" % (
            sum(1 for r in t15 if r['usable']), len(t15))
    assert not any(r['usable'] for r in t14), "thrust 14 is barren at every measured lean"
    # and the recovery is the LADDER's, not a wider sweep: every usable row needed escalating
    assert all(r['escalated'] for r in t15 if r['usable'])
    # the recovered bands are real intervals, the same order as the delivered cells' best
    assert max(r['width'] for r in t15) > 1e-5


def test_width_is_a_ranking_and_never_a_filter():
    """The delivered console clip converted at a band whose width is **0.0** -- 20 genuine samples all
    at one f32 residual. So `usable` (a `MIN_BAND` width test) is False at the one configuration we know
    clips, and a pass that dropped candidates on it would drop the console solution.

    `rank` therefore ORDERS by width x mass and returns everything; nothing in this module filters on
    width. The 0.0 is also why "cell 2553 has zero width" was never the same claim as "cell 2553 cannot
    convert" -- it is odds, not a wall."""
    fx = _measurement()
    d = [r for r in fx['rows']
         if (r['cell'], r['thrust'], r['lean']) == tuple(fx['delivered'])]
    assert len(d) == 1, "the measurement must carry the delivered clip's own row"
    row = d[0]
    assert row['productive'] and row['n_genuine'] > 0
    assert row['width'] == 0.0 and not row['usable']

    ranked = EL.rank(fx['rows'])
    assert len(ranked) == len([r for r in fx['rows'] if r['mass']]), "rank must not drop rows"
    assert row in ranked
    usable = [r['usable'] for r in ranked]
    assert usable == sorted(usable, reverse=True), "usable rows first"


# --------------------------------------------------------------- the ladder's own contracts

def test_the_ladder_is_order_independent():
    """A first cut of the ladder also tried the last station that had paid for the same (facing,
    thrust) at any lean. Free, and it converts keys -- but it makes the table's answer a function of the
    order the keys were REQUESTED, so two passes over one scope can report different widths and any
    gate on a single key is flaky. Both halves are checked: the seed list cannot depend on request
    history, and two tables asked in opposite orders agree bit-for-bit."""
    seed = ES.console_seed()
    quals = _quals()
    fwd = SC.BandTable(seed, path=None, quals=quals)
    rev = SC.BandTable(seed, path=None, quals=quals)
    fac, thr = 40850, 15

    before = fwd._cheap_seeds(fac, thr)
    fwd.get(fac, thr, 65411)
    assert fwd._cheap_seeds(fac, thr) == before, "a measurement must not add a seed for the next one"
    assert [k for k, _s in before] == ['ref', 'qual']

    keys = [(fac, thr, L) for L in (65411, 136, 65476, 71)]
    a = [fwd.get(*k)['width'] for k in keys]
    b = [rev.get(*k)['width'] for k in reversed(keys)][::-1]
    assert a == b, dict(forward=a, reverse=b)


def test_a_negative_argued_from_one_station_does_not_survive_in_the_cache(tmp_path):
    """THE HYGIENE THAT MAKES THE FIX STICK. 10360 of the 15968 entries in the s81 band cache were
    negatives of the old kind, and a memo that keeps serving them would carry the bug past its own fix
    silently. So a cached row that is NOT productive and does not say it was escalated is dropped on
    load and re-measured, while a productive one is kept -- a cheap-path positive is a positive whatever
    rung found it. New saves are versioned so the distinction is legible from the file."""
    path = str(tmp_path / 'bands.json')
    key_dead = '40850,14,64761,%d' % SC._f32_bits(ES.ROLL_NSPEED)
    key_live = '40850,15,65411,%d' % SC._f32_bits(ES.ROLL_NSPEED)
    live = dict(productive=True, reason='', grad=1.0, resid=0.0, entry=[0.0, 0.0],
                lo=-1e-5, hi=1e-5, width=2e-5, n_genuine=3)
    dead = dict(productive=False, reason='no leverage', grad=0.0, resid=1.0, entry=[0.0, 0.0],
                lo=None, hi=None, width=0.0, n_genuine=0)
    json.dump({key_dead: dead, key_live: live}, open(path, 'w'))          # the v1 flat format

    t = SC.BandTable(ES.console_seed(), path=path, quals=_quals())
    keys = {k[:3] for k in t.tab}
    assert (40850, 15, 65411) in keys, "a productive cached row must survive"
    assert (40850, 14, 64761) not in keys, "a one-station negative must be re-measured"

    t.save()
    raw = json.load(open(path))
    assert raw['version'] == 2 and key_live in raw['bands']
    # and a v2 file round-trips without the header being mistaken for a key
    again = SC.BandTable(ES.console_seed(), path=path, quals=_quals())
    assert {k[:3] for k in again.tab} == keys


# ------------------------------------------------------------------------ the scoping contract

def test_scoping_by_lean_changes_the_cost_and_never_an_answer():
    """The same contract `entry_fan.capped` and `select_quals` carry: a scope is a budget decision, so
    it must be a pure order-preserving subset of the stream. Anything else and a scoped pass is a
    different experiment rather than a cheaper one."""
    pairs = [((1.0, 2.0, 64345), (0, 1, 2, 2, 3, 4, 1)),
             ((3.0, 4.0, 0), (0, 5, 6, 2, 7, 8, 1)),
             ((5.0, 6.0, 64345), (1, 5, 6, 2, 7, 8, 1))]
    leans = [ES.lean_at_roll(k[2]) for k, _p in pairs]

    assert list(EL.select_by_lean(iter(pairs), None)) == pairs          # off by default
    assert list(EL.select_by_lean(iter(pairs), [])) == pairs
    assert list(EL.select_by_lean(iter(pairs), set(leans))) == pairs    # a covering scope is identity
    one = list(EL.select_by_lean(iter(pairs), [leans[0]]))
    assert one == [pairs[0], pairs[2]]                                  # subset, in the same order
    # the scopes PARTITION the stream: nothing is invented and nothing is lost
    halves = (list(EL.select_by_lean(iter(pairs), [leans[0]]))
              + list(EL.select_by_lean(iter(pairs), [leans[1]])))
    assert sorted(halves) == sorted(pairs)


def test_the_census_lean_is_the_key_the_pass_groups_its_bands_by():
    """A candidate's key carries the WALK's m351C and the band is keyed on the roll ENTRY's, one
    `_set_move_slant_angle` decay step later (`lean_at_roll`). Mixing them up would score every
    candidate at a neighbouring lean's band, so the two conventions are pinned against the console
    clip, which records both."""
    h = _clip()
    assert ES.lean_at_roll(h['m351C_walk']) == h['m351C']
    fx = _measurement()
    assert tuple(fx['delivered']) == EL.DELIVERED
    assert EL.DELIVERED[2] == h['m351C'] and EL.DELIVERED[0] == ES.aim_cell(h['facing'])
    # every measured lean is a lean the fan actually reaches, or the qualification's own control
    hist = {int(k) for k in fx['census']['hist']}
    for r in fx['rows']:
        assert r['lean'] in hist or r['lean'] == 0, r['lean']


def test_parse_lean_spec_resolves_out_of_the_measurement():
    """The named forms are DERIVED, so a re-measure moves every selector with it -- the same discipline
    as `parse_cell_spec` reading its lobes out of the window fixture."""
    fx = _measurement()
    top = [l for l, _n in EL.heaviest(fx['census'], 4)]
    assert EL.parse_lean_spec('top4', fx) == tuple(sorted(top))
    assert EL.parse_lean_spec('65281,136', fx) == (136, 65281)

    paying = EL.parse_lean_spec('paying', fx)
    at2553 = EL.parse_lean_spec('paying:2553', fx)
    assert at2553 and set(at2553) <= set(paying)
    assert set(paying) <= {int(k) for k in fx['census']['hist']} | {0}
    assert set(at2553) == {r['lean'] for r in fx['rows'] if r['usable'] and r['cell'] == 2553}
    # and a mix composes
    assert set(EL.parse_lean_spec('paying:2553,top4', fx)) == set(at2553) | set(top)


def test_the_measurement_records_the_fan_it_was_taken_at():
    """The mass distribution is a property of the FAN, so a census that does not name its own shape
    cannot be read as a ranking of anything -- and the ranking is what a pass is aimed by."""
    fx = _measurement()
    cen = fx['census']
    assert cen['n_candidates'] > 0 and cen['n_leans'] > 100
    for k in ('s1_stride', 's2_stride', 'j1', 'j2max', 'base_frames'):
        assert cen['fan'][k], k
    assert cen['max_frames'] == ES.REACH_FRAMES
    assert sum(cen['hist'].values()) == cen['n_candidates']
    assert 'ladder' in fx['note'] or 'BandTable' in fx['note']
