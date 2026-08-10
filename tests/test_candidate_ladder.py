"""The tracked Courtyard candidate ladder is the project's fallback list -- gate its shape.

Every rung cost node-hours to find (s141 7892 s, s142 23563 s) and until s142 they lived only in
gitignored `_generated/`, so a rung that did not survive assembly had no recorded successor. This
gates the fixture's structure and LOCKS the top rung's numbers exactly (0-ULP, no tolerances --
`[[zero-ulp-tests-only]]`), so a corrupted or silently-rewritten ladder fails here rather than in a
session that trusts it.

Structure only in the default gate: the replay lives in
`test_the_top_rung_replays_to_its_banked_numbers`, slow-marked, because a functionality test does not
take a second (`tests/conftest.py`'s budget gate). Every rung was replay-verified when the fixture was
built (`_notes/s142_ladder.py` -- all 49 reproduce their banked bound/gap exactly).
"""
import json
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LADDER = os.path.join(_ROOT, 'fixtures', 'courtyard_candidate_ladder.json')


@pytest.fixture(scope='module')
def ladder():
    with open(LADDER) as fh:
        return json.load(fh)


def test_the_ladder_is_ranked_and_every_rung_carries_its_inputs(ladder):
    cands = ladder['candidates']
    assert len(cands) >= 49, 'the ladder lost rungs'
    assert [c['rank'] for c in cands] == list(range(1, len(cands) + 1))
    assert all(a['bound'] <= b['bound'] for a, b in zip(cands, cands[1:])), 'not ranked by bound'
    for c in cands:
        # the log IS the plan: a rung without one is not a fallback, it is a number
        assert c['log'], 'rung %d has no input log' % c['rank']
        assert len(c['log']) == c['herd'], 'rung %d: log is %d frames, herd says %d' % (
            c['rank'], len(c['log']), c['herd'])


def test_the_top_rung_is_locked_exactly(ladder):
    """s142 node 12, replay-verified to <1e-9 on a fresh native FreeRun (`_notes/s142_verify.py`)."""
    top = ladder['candidates'][0]
    assert (top['session'], top['node'], top['herd']) == ('s142', 12, 72)
    assert top['bound'] == 85.21796368214332
    assert top['gap'] == 3.7053825964363734
    assert top['l0'] == 51.223320736271575
    assert top['cut'] == 13 == ladder['terminal']['cut_step']
    assert top['viable'] and top['wall_ok'] and top['regime_ok'] and top['terminal_ok']
    assert top['bound'] < ladder['incumbent']


@pytest.mark.slow
def test_the_top_rung_replays_to_its_banked_numbers(ladder):
    """The banked scalars are only worth what the LOG reproduces: replay it on a fresh native
    `FreeRun` and recompute `handoff.endpoint`. Exact equality, no tolerance."""
    import warnings

    from harness.tetrapush import beam_io as BIO
    from harness.tetrapush import handoff as HO
    from harness.tetrapush import seeds as SD
    from harness.tetrapush.reposition import HerdLine

    top = ladder['candidates'][0]
    t = ladder['terminal']
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        env = SD.load_env()
        hl = HerdLine.from_env(env)
        rec = dict(cycles=[[dict(log=top['log'], frames=top['herd'])]])
        run = BIO.rebuild_beam(env, rec, cycle=1, hl=hl)[0]['run']
        pf = HO.PairFrame(facing=t['facing'], thrust=t['thrust'])
        h = HO.endpoint(pf, (run.link.pos_x, run.link.pos_z), (run.tx, run.tz), top['herd'],
                        runways=tuple(t['runways']))
    assert h['bound'] == top['bound']
    assert h['gap'] == top['gap']
    assert HO.tetra_lateral(pf, (run.tx, run.tz)) == top['l0']
    assert h['onside'] and h['n'] == top['entry_points']


def test_the_ladder_cannot_be_read_as_a_ranked_shortlist(ladder):
    """``viable`` does NOT include the terminal confirm, and s142 measured that no rung passes it.
    The warning is the only thing standing between a future session and a plan whose clip never
    fires, so it is gated rather than trusted to survive an edit."""
    w = ladder['CONFIRMATION_WARNING']
    assert 'roots=True' in w and 'UNCONFIRMED' in w
    assert ladder['confirmed_tested'] == {'rung_1': 0, 'rung_2': 0, 'rung_4': 0, 'rung_7': 0}
    lo, hi = ladder['genuine_region']['l0']
    assert lo < hi <= 13.0, 'the confirmable band moved -- re-derive it before trusting the ladder'
    assert all(c['l0'] > hi for c in ladder['candidates'][:4]), \
        'a top rung now sits inside the confirmable band -- CONFIRM it and re-rank'


def test_viability_is_the_conjunction_the_header_claims(ladder):
    """``viable`` is what a session reads to pick a fallback, so it must not drift from its own
    definition -- and rung 3 is the reason the flag exists: it beats the reference on ``bound`` and
    FAILS rule 3, which a bound-only ladder would have hidden until assembly."""
    edges = (ladder['terminal']['runways'][0], ladder['terminal']['runways'][-1])
    for c in ladder['candidates']:
        assert c['viable'] == bool(c['wall_ok'] and c['regime_ok'] and c['terminal_ok']
                                   and c['l0'] > 0.0 and c['runway'] not in edges)
    viable = [c for c in ladder['candidates'] if c['viable']]
    assert len(viable) >= 2, 'a ladder with one viable rung is not a fallback list'
    assert [c['rank'] for c in viable][:3] == [1, 2, 4], 'the known rank-3 rule-3 failure moved'
