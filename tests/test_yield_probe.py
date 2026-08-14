"""**THE YIELD PROBE'S OWN GATES** (session 164) -- `harness/tetrapush/yield_probe.py`.

Two claims carry the tool, and each is gated here:

  * **the locate's regime split is the right predicate.** The entry-plane ``resid = 0`` set mixes
    the strip (gentle, ~0.3/u, where genuine lives) with quantization-oscillating discontinuities
    (~650/u, never genuine); `gentle_brackets` must keep the first and refuse the second, or the
    probe walks cliffs and reports fiction.
  * **the probe rediscovers the known answer** (`[[search-must-rediscover-known-answer]]`): at
    s163's console-w04 -- the one item where the genuine plans are KNOWN -- the probe's top draws
    must be exactly the two that produced all 8 of them. The ~50 s run is BANKED
    (`fixtures/courtyard_yield_probe_console_w04.json`, minted by
    ``python -m harness.tetrapush.yield_probe item console-w04 incumbent=102 out=...``) and
    asserted against its artefact, per `[[slow-offline-tests]]`.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.tetrapush import yield_probe as YP

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'fixtures', 'courtyard_yield_probe_console_w04.json')

#: The two draws that produced all 8 genuine plans of the s163 closed-loop run
#: (`_generated/overnight/s163-console-w04`; `knowledge/model/fan-containment-gap.md`).
GENUINE_DRAWS = {(2551, 15), (2552, 15)}


# ------------------------------------------------------------------ the regime classifier is pure

def test_gentle_bracket_kept():
    lats = [0.0, 0.5, 1.0, 1.5]
    resids = [-0.4, -0.1, 0.2, 0.6]
    assert YP.gentle_brackets(lats, resids) == [(1, 2)]


def test_cliff_bracket_refused():
    # the measured shape at a discontinuity component: +-50 swing across one 0.5 u step
    lats = [0.0, 0.5, 1.0]
    resids = [61.3, -58.9, -49.9]
    assert YP.gentle_brackets(lats, resids) == []


def test_flat_profile_yields_nothing():
    # the braced regime: a dead-constant residual has no crossing at all (a == b is skipped,
    # so a constant-zero profile does not fabricate brackets either)
    assert YP.gentle_brackets([0.0, 0.5, 1.0], [0.7, 0.7, 0.7]) == []
    assert YP.gentle_brackets([0.0, 0.5, 1.0], [0.0, 0.0, 0.0]) == []


def test_gentle_bound_is_the_split():
    # endpoints straddling zero but one past GENTLE: that is a cliff shoulder, not the strip
    resids = [-0.2, YP.GENTLE + 1.0]
    assert YP.gentle_brackets([0.0, 0.5], resids) == []


# ------------------------------------------------------- the banked rediscovery, console-w04 (s163)

def _fixture():
    with open(FIX) as f:
        return json.load(f)


def test_probe_rediscovers_the_genuine_draws():
    """Every draw that produced a genuine plan admits, IN REACH -- the probe's whole claim."""
    fx = _fixture()
    by_draw = {(d['cell'], d['thrust']): d for d in fx['draws']}
    for key in GENUINE_DRAWS:
        d = by_draw[key]
        assert d['n_admit'] > 0, 'genuine draw %s reads barren' % (key,)
        assert d['in_reach'] > 0, 'genuine draw %s admits only out of reach' % (key,)


def test_genuine_draws_rank_top_two():
    """The ranking key (in-reach stations, then stations) puts the two productive draws first --
    what makes the probe a SCHEDULER and not just a screen."""
    fx = _fixture()
    ranked = sorted(fx['draws'], key=lambda d: (-d['in_reach'], -d['n_admit']))
    assert {(d['cell'], d['thrust']) for d in ranked[:2]} == GENUINE_DRAWS


def test_probe_is_selective():
    """The value is concentration: most draws read zero (129/135 at the banked run), so the score
    separates items. A fixture where half the draws admit is a broken locate, not a rich item."""
    fx = _fixture()
    barren = sum(1 for d in fx['draws'] if d['n_admit'] == 0)
    assert barren >= 0.8 * fx['n_draws']
    assert fx['score'] == sum(d['in_reach'] for d in fx['draws'])


def test_fixture_provenance():
    """The fixture is the probe's own output at the s163 item, derived leans, admissible reach."""
    fx = _fixture()
    assert fx['item'] == 'console-w04' and fx['walk'] == 4 and fx['ok']
    assert fx['n_draws'] == len(fx['draws']) == 135
    assert fx['reach'] == YP.AF.MAX_STEP * (fx['walk'] + 1)
    assert len(fx['leans']) == 3


# ------------------------------------------------------------ the kept-edge reach anchor (s164 late)

def test_kept_edge_extrapolation_is_admissible():
    """One added walk frame buys at most one cap step -- the anchor plus MAX_STEP per frame."""
    assert YP.kept_edge_reach(74.1, 5, 5) == 74.1
    assert YP.kept_edge_reach(74.1, 5, 7) == 74.1 + 2 * YP.AF.MAX_STEP


def test_run_kept_edge_reads_the_cloud_edge(tmp_path):
    """The measured edge is `best_overlap_row`'s endpoint distance from the herd end -- the number
    the rung05-w05 post-mortem was built on (74.1 u vs the probe's 100.7 u station)."""
    import json as J
    d = tmp_path / 'run'
    d.mkdir()
    row = dict(best_overlap_row=dict(walk=[3.0, 4.0]))
    (d / 'progress.jsonl').write_text(J.dumps(row) + '\n')
    assert YP.run_kept_edge(str(d), (0.0, 0.0)) == 5.0
    assert YP.run_kept_edge(str(tmp_path / 'missing'), (0.0, 0.0)) is None
