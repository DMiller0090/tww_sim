"""**THE FRAME-MINIMAL CLIP IS ON CONSOLE** -- a 4-frame walk-up, one frame under session 88's.

`test_clip_delivered.py` gates the delivery that made `genuine` a measured number at all. This gates
the one that makes it a measured number at the FRAME FLOOR, which is what the objective actually asks
for (`harness/tetrapush/objective.py`): row 0 of the session-90 candidate list, delivered in one run,
bit-identical to the prediction at the cut and in `daPyProc_FALL_e` five frames later.

It is here rather than folded into the session-88 file because it is a different claim resting on a
different fixture -- and because of how it became deliverable. This candidate was REJECTED by the
cross-engine filter until session 90 delivered a blocked candidate to console and found the two
Co-centre ports were being handed anim frames one f32 ULP apart (`tests/test_centre_seam.py`). Fixing
that took the pass from 51 of 55 to 55 of 55 and made the frame floor reachable, so this capture is
also the payoff for that one being settled rather than argued.

`fixtures/courtyard_clip_s90_console.json` is LOCKED. Offline -- replays the locked log on the wired
`FreeRun`, no Dolphin.
"""
import json
import math
import os
import struct
import warnings

import pytest

from harness.rollstab import turnaround as TA
from harness.tetrapush import seeds
from tww_sim.core.mathlib import main_stick_decode
from tww_sim.land.land import CUT_F, FRONT_ROLL, LandState


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_clip_s90_console.json')))
HITS = json.load(open(_fx('courtyard_entry_s90_hits.json')))
SAMPLES = {s['i']: s for s in FIX['samples']}
HIT, PRED = FIX['hit'], FIX['prediction']
CUT_I, ENTRY_I = FIX['plan']['cut_i'], FIX['plan']['entry_i']


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope="module")
def rollout():
    """The composite in ONE engine: the wired delay-1 `FreeRun` the console runs, the culled
    courtyard mesh on BOTH actors. Plan frame i is plan frame i, no schedule-step mapping."""
    env = seeds.load_env()
    run = seeds.make_freerun(env)
    run.link._walls = TA.WALLS
    run.walls_tetra = TA.WALLS
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    snaps = {}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, d in enumerate(FIX['log']):
            run.step(d)
            snaps[i] = dict(x=float(run.link.pos_x), z=float(run.link.pos_z),
                            proc=int(run.link.state) & 0xFF, facing=int(run.link.facing) & 0xFFFF,
                            speedF=float(run.link.speedF), tx=float(run.tx), tz=float(run.tz))
    return snaps


def test_the_console_clipped_at_the_frame_floor():
    """**THE ONE THAT MATTERS.** At the cut frame Link stands where the razor said, to the bit,
    ~49.7 u out through a seam he was braced against the frame before -- off a walk-up of FOUR
    frames, which is the floor of the whole pass and one under the delivered session-88 plan."""
    s = SAMPLES[CUT_I]['link']
    assert s['proc'] == CUT_F and s['facing'] == HIT['facing']
    assert _bits(s['x']) == _bits(PRED['new'][0])
    assert _bits(s['z']) == _bits(PRED['new'][1])
    moved = math.hypot(s['x'] - PRED['old'][0], s['z'] - PRED['old'][1])
    assert moved == pytest.approx(PRED['lunge'], abs=1e-6) and moved > 45.0
    assert HIT['frames'] == HITS['frame_floor'] == 4
    s88 = json.load(open(_fx('courtyard_clip_s88_console.json')))
    assert HIT['frames'] < s88['hit']['frames'], "this is supposed to be the cheaper plan"


def test_link_leaves_the_floor_and_tetra_does_not_move_when_he_does():
    """Five frames on the console is in `daPyProc_FALL_e` (0x27) -- off the courtyard floor, so this
    is the clip and not a one-frame excursion. The flat-ground composite cannot model that and the
    fixture records it as scope; what IS gated is Tetra, who is still bit-identical there."""
    post = FIX['post_cut']
    assert post['i'] > CUT_I and post['proc'] == 0x27
    assert post['proc_name'] == 'daPyProc_FALL_e'
    cut_t = SAMPLES[CUT_I]['tetra']
    assert _bits(post['tetra']['x']) == _bits(cut_t['x'])
    assert _bits(post['tetra']['z']) == _bits(cut_t['z'])
    assert post['tetra']['stt'] == cut_t['stt'] == 3


@pytest.mark.parametrize("i", sorted(SAMPLES))
def test_the_composite_reproduces_every_console_sample_up_to_the_cut(i, rollout):
    """Both actors, 0 ULP, at every sample the flat-ground model covers -- i.e. through the cut."""
    if i > CUT_I:
        pytest.skip("past the cut the console has left the floor; see post_cut in the fixture")
    s, sim = SAMPLES[i], rollout[i]
    assert _bits(sim['x']) == _bits(s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z'])
    assert sim['proc'] == s['link']['proc'] and sim['facing'] == s['link']['facing']
    assert _bits(sim['speedF']) == _bits(s['link']['speedF'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z'])


def test_the_delivered_row_is_the_list_it_claims_to_come_from(rollout):
    """The capture is only about the frame floor if the hit really is row 0 of the current list, and
    only about THIS candidate if the composite rolls from its scored entry. Both asserted, because a
    fixture that quotes its own `hit` back at itself would gate nothing."""
    row = HITS['rows'][0]
    for k in ('plan', 'aim', 'facing', 'thrust', 'm351C', 'entry', 'frames'):
        assert row[k] == HIT[k], k
    assert row['confirmed'] and row['deliverable'] and row['cross_engine']['deliverable']
    ent = rollout[ENTRY_I]
    assert ent['proc'] == FRONT_ROLL
    assert _bits(ent['x']) == _bits(HIT['entry'][0])
    assert _bits(ent['z']) == _bits(HIT['entry'][1])
    assert ent['facing'] == HIT['facing']


def test_the_aim_clears_the_attack_threshold_it_had_to_clear():
    """Session 88's gate, on the candidate that was actually delivered: an A-press at or below
    `mStickDistance` 0.75 is `PUT_AWAY` and sheathes the sword instead of rolling."""
    assert main_stick_decode(*HIT['aim'])[1] > float(LandState.ATTACK_MSD_MIN)
