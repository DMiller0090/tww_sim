"""TWO IMPLEMENTATIONS OF LINK'S Co CENTRE, AND NOTHING GATES THEM AGAINST EACH OTHER.

Session 88 left the cross-engine rejections as "a property of the candidate". Session 89 root-caused
them to ONE code seam: the composite and the search compute the point the plow pushes Tetra from by
two different routes --

  * `from_f0._computed_center` -> `FootFK.body_co_center`: rebuilt from the pose driver's STORED OLD
    POSE (local quat/trans/scale -> matrix -> chain);
  * `entry_search.fast_schedule` -> `body_cyl.roll_co_chain_consts`: the `rollf` anim sampled at
    `roll_frame` DIRECTLY, baked into position-independent constants the native `ShoveCtx` sweeps.

They agree to 1-2 ULP. At the razor that is the whole verdict -- session 86 measured one f32 step of
Tetra's x flipping `genuine` -- so every cross-engine rejection in the population is this seam, and
swapping the composite onto the other centre makes all four agree.

WHICH ONE IS RIGHT IS NOT SETTLED, and these tests are written so that they do not pretend otherwise.
Both console captures fall on candidates where the two paths agree, so neither discriminates; the
last test pins exactly that, because it is the reason no engine was changed. `body_cyl` is
console-gated 0-ULP for the courtyard roll leans (session 87) while `_computed_center` is live-pinned
only to a ~1-ULP TOLERANCE, which is suggestive and is not evidence.

If a future session settles it -- by delivering a BLOCKED candidate, where the two centres predict
49.8582 u and 0.1534 u -- the losing implementation goes and these tests go with it. Until then this
file exists to stop the seam being rediscovered a third time.

`fixtures/courtyard_centre_seam_s89.json` is a MODEL output; regenerate with
`_notes/s89_centre_seam.py`. Offline.
"""
import json
import os

import pytest

from harness.tetrapush import from_f0 as F0
from tww_sim.core.anim import body_cyl, foot_fk


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures',
                        name)


SEAM = json.load(open(_fx('courtyard_centre_seam_s89.json')))
CENSUS = SEAM['census']
BY = SEAM['by_class']


def test_the_two_centre_paths_are_different_code():
    """The premise, asserted rather than described: these are two implementations, and the composite
    uses the one the search does not."""
    assert F0._computed_center.__module__ == 'harness.tetrapush.from_f0'
    assert callable(foot_fk.FootFK.body_co_center) and callable(body_cyl.roll_co_center)
    assert body_cyl.roll_co_center is not foot_fk.FootFK.body_co_center


def test_every_cross_engine_rejection_sits_on_a_disagreeing_frame():
    """The correlation, and it is total. 4 of 4 rejected candidates have a roll frame where the two
    centres differ; 0 of 36 ATTACK-gate drops do. A rejection is not bad luck in a candidate, it is
    this seam being crossed."""
    assert BY['rejected']['n'] == BY['rejected']['n_disagree'] > 0
    assert BY['dropped']['n_disagree'] == 0 and BY['dropped']['n'] > 0
    assert all(r['n_disagree'] > 0 for r in CENSUS if r['cls'] == 'rejected')
    assert all(r['n_disagree'] == 0 for r in CENSUS if r['cls'] == 'dropped')


def test_the_disagreement_is_one_or_two_ulp_on_isolated_frames():
    """The scale, pinned. If this ever reads large the diagnosis is wrong and something else broke:
    the seam is a rounding difference between two routes to the same quantity, not a modelling gap."""
    hit = [r for r in CENSUS if r['n_disagree']]
    assert hit, "the fixture must carry the class these tests are about"
    assert all(r['worst_ulp'] <= 2 for r in hit)
    assert all(r['n_disagree'] <= 2 for r in hit)


def test_swapping_the_centre_makes_every_rejection_agree():
    """The CAUSAL test, and the one that turns a correlation into a root cause. Put the composite on
    the search's centre and all four rejections agree bit-for-bit -- two of them flipping from the
    composite refusing to move Link at all to the identical 49.8582 u lunge."""
    cau = SEAM['causal']
    assert len(cau) == BY['rejected']['n']
    assert all(r['body_cyl']['cut_is_prediction'] for r in cau)
    blocked = [r for r in cau if not r['footfk']['cut_is_prediction']]
    assert blocked, "the expensive class: the composite blocking a lunge ShoveCtx scores genuine"
    for r in blocked:
        assert r['footfk']['moved'] < 1.0 < 45.0 < r['predicted_lunge']
        assert r['body_cyl']['moved'] == pytest.approx(r['predicted_lunge'], abs=1e-4)


def test_the_seam_costs_candidates_but_not_the_frame_floor():
    """What it is worth, so a future session can judge whether settling it is on the critical path.
    On this population it is 4 candidates and zero frames -- the objective's answer does not move,
    which is why it did not stop the session."""
    a, b = SEAM['cost']['footfk'], SEAM['cost']['body_cyl']
    assert a['n_confirmed'] == b['n_confirmed']
    assert b['n_deliverable'] > a['n_deliverable']
    assert b['n_deliverable'] == b['n_confirmed']
    assert a['frame_floor'] == b['frame_floor']


def test_the_console_captures_cannot_decide_which_centre_is_right():
    """THE REASON NO ENGINE WAS CHANGED. On the session-86 console roll the two centres produce a
    byte-identical composite, so the capture is silent on the question -- and the session-88 one is
    silent for the same reason. Inferring a winner from a gate that cannot see the difference is the
    exact mistake session 88 recorded as razor rule 8; the fix needs a delivery, not an argument."""
    assert SEAM['undecided']['n_frames_changed'] == 0
    assert SEAM['undecided']['samples']
