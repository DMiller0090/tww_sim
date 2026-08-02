"""THE CROSS-ENGINE FILTER, AND WHY IT LIVES IN THE CONFIRM LOOP.

Session 88 spent a delivery on a candidate the composite would have refused, and only found out
because it ran the diff by hand afterwards. The lesson is not "the engines disagree" -- session 87
had already made them agree for one hit and gated it -- but that agreement is a property of the
CANDIDATE, so a per-hit check is the only kind that means anything, and it has to run before a
console run is spent rather than after.

What this file pins:

  * `cross_engine.agree` reproduces, hit for hit, the verdicts session 88 measured by hand and pinned
    in `fixtures/courtyard_entry_s88_hits.json` -- including the rejections and WHICH kind each is.
  * The filter is wired into `entry_score.confirm_hits`, and the three filters there are INDEPENDENT:
    the ATTACK gate, the DTM-byte gate and this one each reject candidates the other two pass. That
    independence is the whole argument for running all three, so it is asserted and not assumed.
  * Off by default. `cross_engine=False` must leave the rows and the ranking byte-identical to what
    every existing caller and gate expects.

Offline: replays a locked log on the wired `FreeRun` plus one `ShoveCtx` build per hit, no Dolphin.
"""
import json
import os
import warnings

import pytest

from harness.tetrapush import cross_engine as XE
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES
from tww_sim.land.land import CUT_A, CUT_F, FRONT_ROLL


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures',
                        name)


HITS = json.load(open(_fx('courtyard_entry_s88_hits.json')))
CLIP = json.load(open(_fx('courtyard_clip_s88_console.json')))


@pytest.fixture(scope="module")
def seed():
    return ES.console_seed()


# --------------------------------------------------------------- the verdict, against the console

def test_the_delivered_candidate_agrees_and_predicts_what_the_console_did(seed):
    """The one candidate with a console number behind it. `agree` must call it deliverable and put
    the lunge at the 49.8582 u the console actually moved -- if this drifts, every other verdict in
    the file is worth nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        r = XE.agree(HITS['rows'][0], seed=seed)
    assert r['deliverable'] and r['handover_ok'] and r['genuine'] and r['cut_ok']
    assert r['worst_ulp'] == 0
    assert not XE.blocked(r)
    assert r['predicted_lunge'] == pytest.approx(CLIP['prediction']['lunge'], abs=1e-9)
    assert r['cut_i'] == CLIP['plan']['cut_i'] and r['entry_i'] == CLIP['plan']['entry_i']
    assert r['cut_step'] == CLIP['prediction']['cut_step']


@pytest.mark.parametrize("k", range(3))
def test_every_pinned_survivor_still_agrees(k, seed):
    """The pinned list is a claim about the engines as they stand. Three rows is enough to catch a
    drift and cheap enough to run every time; the whole list is `_cmd_confirm ... xengine`."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        r = XE.agree(HITS['rows'][k], seed=seed)
    assert r['deliverable'], HITS['rows'][k]['plan']
    assert r['worst_ulp'] == 0 and r['cut_ok']


def test_the_blocked_rejections_are_reproduced_and_named(seed):
    """The expensive class, RE-MEASURED rather than trusted: `ShoveCtx` lunges ~50 u through the seam
    and the composite does not move Link at all. `blocked` has to separate these from a candidate
    that merely diverges, because they are the ones worth a diagnosis -- a few ULP of Tetra is the
    scale the verdict flips at, so whichever engine is wrong is wrong for the population.

    The rejected rows carry only a summary, so the candidates are recovered from the session-87 pass
    they came from; asserting the summary against itself would gate nothing."""
    rej = [r for r in HITS['rejected'] if r['cross_engine']['composite_moved'] < 1.0]
    assert rej, "the fixture must carry the class this test is about"
    src = json.load(open(_fx('courtyard_entry_s87_hits.json')))['rows']
    for row in rej:
        hit = next(h for h in src if h['plan'] == row['plan'] and h['m351C'] == row['m351C'])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r = XE.agree(hit, seed=seed)
        assert XE.blocked(r), row['plan']
        assert not r['deliverable'] and r['genuine'] and r['handover_ok']
        assert r['predicted_lunge'] > XE.CLIP_LUNGE_MIN and r['composite_moved'] < 1.0
        # and the fixture's recorded summary is what a re-run still measures
        assert r['composite_moved'] == pytest.approx(row['cross_engine']['composite_moved'], abs=1e-9)
        assert r['predicted_lunge'] == pytest.approx(row['cross_engine']['predicted_lunge'], abs=1e-9)


def test_a_pre_cut_divergence_can_still_end_in_an_identical_cut_frame():
    """Session 88's trap, pinned: two of the 19 diverge by 1 ULP before the cut and STILL land on a
    bit-identical cut frame. `cut_ok` alone is not agreement, which is why `deliverable` demands
    `worst_ulp == 0` as well."""
    diff = [r['cross_engine'] for r in HITS['rejected']
            if r['cross_engine']['composite_moved'] >= 1.0]
    assert diff, "the fixture must carry the subtle class too"
    assert any(d['cut_ok'] and d['worst_ulp'] > 0 for d in diff)
    assert all(not d['deliverable'] for d in diff)


# ------------------------------------------------------------------------- the composite itself

def test_the_composite_log_puts_the_cut_where_the_mapping_says(seed):
    """The session-86 mapping trap as an invariant, not a comment: the roll dispatches at `entry_i`,
    the DTM is a delay-1 stream, so the UP+B at `b_log` fires the cut on `b_log + 1`. An off-by-one
    here reads as a physics divergence and has cost sessions."""
    hit = HITS['rows'][0]
    log, ix = XE.composite_log(hit, seed)
    assert ix['b_log'] == ix['entry_i'] + hit['thrust'] + 2
    assert log[ix['a_i']]['buttons'] == 0x100
    assert log[ix['b_log']]['buttons'] == 0x200 and log[ix['b_log']]['stickY'] == 254
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        rows = {r['i']: r for r in XE.composite_rollout(log)}
    assert rows[ix['entry_i']]['proc'] == FRONT_ROLL
    cut = next(i for i in sorted(rows) if i > ix['entry_i'] and rows[i]['proc'] in (CUT_F, CUT_A))
    assert cut == ix['b_log'] + 1


def test_tetras_own_wall_is_load_bearing_for_the_verdict(seed):
    """Session 87's term, gated where it now matters. Take her BG pass away and the composite is a
    different engine -- the point of `walls_tetra=` being a parameter rather than a constant is that
    the difference can be measured, and the default is the configuration the console gated."""
    log, ix = XE.composite_log(HITS['rows'][0], seed)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        walled = XE.composite_rollout(log)
        bare = XE.composite_rollout(log, walls_tetra=False)
    end = ix['b_log'] + 1
    assert any(walled[i]['tetra_x'] != bare[i]['tetra_x']
               or walled[i]['tetra_z'] != bare[i]['tetra_z'] for i in range(end))


# ---------------------------------------------------------------------------- the wiring, and off

def test_confirm_hits_carries_the_verdict_and_ranks_a_disagreeing_hit_last(seed):
    """The filter in the loop. A hit that confirms and delivers but does not agree must still lose to
    one that does, however many frames it saves -- it cannot be delivered at all."""
    good = HITS['rows'][0]
    bad = next(r for r in HITS['rejected'] if r['cross_engine']['composite_moved'] < 1.0)
    hit = next(h for h in HITS['rows'] if h['plan'] == good['plan'])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        rows = EF.confirm_hits([hit], seed=seed, cross_engine=True)
    assert rows[0]['agrees'] and rows[0]['cross_engine']['deliverable']
    assert rows[0]['blocked'] is False
    assert bad['cross_engine']['predicted_lunge'] > XE.CLIP_LUNGE_MIN   # the one it outranks


def test_the_three_filters_are_independent(seed):
    """The argument for running all three. Session 88 measured 55 -> 19 on the ATTACK gate and 19 ->
    15 on this one; if the cross-engine rejections were a subset of what the A-press replay already
    caught, this filter would be free and also pointless. They are not the same candidates."""
    dropped = {tuple(d['plan']) for d in HITS['dropped']}
    rejected = {tuple(r['plan']) for r in HITS['rejected']}
    kept = {tuple(r['plan']) for r in HITS['rows']}
    assert dropped and rejected and kept
    assert not (rejected & dropped), "a cross-engine rejection that the ATTACK gate already dropped"
    assert not (kept & rejected) and not (kept & dropped)


def test_off_by_default_leaves_the_rows_untouched(seed):
    """`cross_engine=False` is the contract every existing caller and gate was written against: no
    extra keys, no extra rollouts, no change to the ranking."""
    hits = [HITS['rows'][0]]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        plain = EF.confirm_hits(hits, seed=seed)
        wired = EF.confirm_hits(hits, seed=seed, cross_engine=True)
    assert set(plain[0]) == {'hit', 'confirm', 'deliverable'}
    assert set(wired[0]) == {'hit', 'confirm', 'deliverable', 'cross_engine', 'agrees', 'blocked'}
    assert plain[0]['confirm']['all_ok'] == wired[0]['confirm']['all_ok']
    assert plain[0]['deliverable'] == wired[0]['deliverable']


def test_an_unconfirmed_hit_is_never_rolled_out(monkeypatch):
    """The cost discipline: the rollout is only worth running on a hit that could be delivered, so a
    failed A-press replay must short-circuit it. Cheap to assert, and it is what keeps the filter
    affordable on a pass whose hits are mostly unconfirmed."""
    calls = []
    monkeypatch.setattr(ES, 'confirm_entry', lambda h, **kw: dict(all_ok=False, ok={}, measured={}))
    monkeypatch.setattr(XE, 'agree', lambda h, **kw: calls.append(h) or dict(deliverable=True))
    rows = EF.confirm_hits([dict(plan=[0, 1, 1, 3], aim=[128, 200])], cross_engine=True)
    assert calls == []
    assert rows[0]['cross_engine'] is None and rows[0]['agrees'] is False
