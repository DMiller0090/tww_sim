"""**THE CLIP IS ON CONSOLE.** `genuine` is a measured number now, not a modelled one.

`test_clip_console.py` gates session 86's delivery, where the handover was bit-exact and the lunge did
not thread the seam. Session 87 named the two unpriced terms and closed them; session 88 found a third
gate the model never had (`test_attack_threshold.py`) and then delivered the frame-minimal survivor of
the re-confirmed list. At the cut frame the console is BIT-IDENTICAL to the prediction -- 49.8582 u off
`old`, out through the seam -- and five frames later Link is in `daPyProc_FALL_e`, off the courtyard
floor, which is what a seam clip is.

Two things this file also pins, because both were paid for:

  * **The cross-engine agreement is a property of the CANDIDATE, not of the engines.** Session 87 made
    `ShoveCtx` and the composite agree for one hit and gated that. Run the same diff over the
    candidate list and 4 of 19 disagree -- two of them because the composite BLOCKS the very lunge
    `ShoveCtx` calls genuine. The frame-minimal candidate was one of those two, so agreement is now a
    pre-flight for spending a delivery.
  * **Nothing past the cut frame is claimed.** The composite is a flat-ground engine; the console has
    left the floor. That divergence is scope, and the fixture says so.

`fixtures/courtyard_clip_s88_console.json` is LOCKED. Offline -- replays the locked log on the wired
`FreeRun` plus one `ShoveCtx` build, no Dolphin.
"""
import json
import math
import os
import struct
import warnings

import pytest

from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_search as ES
from harness.tetrapush import seeds
from tww_sim.core.mathlib import main_stick_decode
from tww_sim.land.land import CUT_F, FRONT_ROLL, LandState


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_clip_s88_console.json')))
HITS = json.load(open(_fx('courtyard_entry_s88_hits.json')))
SAMPLES = {s['i']: s for s in FIX['samples']}
HIT, PRED = FIX['hit'], FIX['prediction']
CUT_I, ENTRY_I = FIX['plan']['cut_i'], FIX['plan']['entry_i']
#: Schedule step k of the `ShoveCtx` roll is plan frame ROLL_F0 + k (step 0 is the roll's SECOND
#: frame -- `entry_search.roll_entry`).
ROLL_F0 = ENTRY_I + 1


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
                            m351C=int(run.link.m351C) & 0xFFFF, nspeed=float(run.link.nspeed),
                            tx=float(run.tx), tz=float(run.tz))
    return snaps


@pytest.fixture(scope="module")
def swept():
    """The SEARCH engine's own run of this hit, Tetra seeded where the console froze her."""
    ctx, sch, resid = ES.build_fast(HIT['facing'], HIT['m351C'], HIT['thrust'],
                                   (HIT['entry'][0], HIT['entry'][1]), nspeed=HIT.get('nspeed'))
    tx, tz = ES.console_seed()['tetra']
    res, tr = ctx.run_trace(tx, tz, 0)
    res['resid'] = resid((res['genuine'], res['old'][0], res['old'][1], res['new'][0],
                          res['new'][1], res['push'][0], res['push'][1]))
    res['cut_step'] = sch['cut_step']
    return res, tr


# ------------------------------------------------------------------------ what the console did

def test_the_console_clipped():
    """**THE ONE THAT MATTERS.** At the cut frame Link stands where the razor said, to the bit, ~50 u
    out through a seam he was braced against the frame before."""
    s = SAMPLES[CUT_I]['link']
    assert s['proc'] == CUT_F and s['facing'] == HIT['facing']
    assert _bits(s['x']) == _bits(PRED['new'][0])
    assert _bits(s['z']) == _bits(PRED['new'][1])
    moved = math.hypot(s['x'] - PRED['old'][0], s['z'] - PRED['old'][1])
    assert moved == pytest.approx(PRED['lunge'], abs=1e-6) and moved > 45.0


def test_the_clip_holds_and_link_leaves_the_floor():
    """Five frames on, the console is in `daPyProc_FALL_e` (0x27) -- he is off the courtyard floor,
    which is the clip and not a one-frame excursion. The flat-ground composite cannot model this and
    the fixture records it as scope, so nothing here is diffed against the sim."""
    last = FIX['samples'][-1]
    assert last['i'] > CUT_I
    assert last['link']['proc'] == 0x27 == FIX['post_cut']['proc']
    assert FIX['post_cut']['proc_name'] == 'daPyProc_FALL_e'


def test_tetra_stays_frozen_and_stt_3_through_the_whole_delivery():
    """The premise the entry search rests on, measured at both sampled frames."""
    for s in FIX['samples']:
        assert s['tetra']['stt'] == 3
    a, b = FIX['samples'][0]['tetra'], FIX['samples'][-1]['tetra']
    assert _bits(a['x']) == _bits(b['x']) and _bits(a['z']) == _bits(b['z'])


# ------------------------------------------------------------------------ what the model must do

@pytest.mark.parametrize("i", sorted(SAMPLES))
def test_the_composite_reproduces_every_console_sample_up_to_the_cut(i, rollout):
    """Both actors, 0 ULP, at every sample the flat-ground model covers -- i.e. through the cut."""
    s, sim = SAMPLES[i], rollout[i]
    if i > CUT_I:
        pytest.skip("past the cut the console has left the floor; see post_cut in the fixture")
    assert _bits(sim['x']) == _bits(s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z'])


def test_the_composite_rolls_from_the_entry_the_hit_was_scored_at(rollout):
    """The handover, re-asserted on this candidate's own log: a hit is only meaningful if the roll
    dispatches from its scored entry at its scored lean and momentum."""
    e = rollout[ENTRY_I]
    assert e['proc'] == FRONT_ROLL
    assert _bits(e['x']) == _bits(HIT['entry'][0]) and _bits(e['z']) == _bits(HIT['entry'][1])
    assert e['facing'] == HIT['facing'] and e['m351C'] == HIT['m351C']
    assert _bits(e['nspeed']) == _bits(HIT['nspeed'])


def test_the_two_engines_agree_frame_for_frame_on_this_candidate(rollout, swept):
    """The pre-flight that earned the delivery: every schedule step diffed against its plan frame on
    both actors, 0 ULP, through the cut."""
    _res, tr = swept
    for k, row in enumerate(tr):
        i = ROLL_F0 + k
        if i > CUT_I:
            break
        assert _bits(row[0]) == _bits(rollout[i]['x']), "link x, step %d" % k
        assert _bits(row[1]) == _bits(rollout[i]['z']), "link z, step %d" % k
        assert _bits(row[2]) == _bits(rollout[i]['tx']), "tetra x, step %d" % k
        assert _bits(row[3]) == _bits(rollout[i]['tz']), "tetra z, step %d" % k


def test_the_search_predicted_the_clip_and_the_residual_has_not_moved(swept):
    """`genuine` True, at the residual the pass recorded, with `old` and `new` bit-stable -- so the
    engine cannot drift under the one candidate the console has confirmed."""
    res, _tr = swept
    assert res['genuine'] is True
    assert _bits(res['resid']) == _bits(HIT['resid'])
    assert _bits(res['old'][0]) == _bits(PRED['old'][0])
    assert _bits(res['new'][0]) == _bits(PRED['new'][0])
    assert res['cut_step'] == PRED['cut_step']


# ------------------------------------------------------------------- what the delivery cost to learn

def test_the_delivered_aim_clears_the_attack_threshold():
    """The gate session 88's FIRST delivery bought: this candidate's aim rolls, and the one before it
    in frame-minimal order did not."""
    assert main_stick_decode(*HIT['aim'])[1] > float(LandState.ATTACK_MSD_MIN)
    gate = json.load(open(_fx('courtyard_attack_gate_s88_console.json')))
    assert main_stick_decode(*gate['hit']['aim'])[1] <= float(LandState.ATTACK_MSD_MIN)


def test_the_cross_engine_gate_rejects_candidates_and_names_why():
    """Agreement is per-candidate: the pinned list carries the rejections, and the two worst are the
    composite refusing a lunge `ShoveCtx` scored genuine. A future pass must run this filter."""
    rej = HITS['rejected']
    assert rej and all(not r['cross_engine']['deliverable'] for r in rej)
    blocked = [r for r in rej if r['cross_engine']['composite_moved'] < 1.0]
    assert blocked, "the expensive class: genuine per ShoveCtx, blocked in the composite"
    assert all(r['cross_engine']['predicted_lunge'] > 45.0 for r in blocked)
    assert all(r['cross_engine']['deliverable'] for r in HITS['rows'])
    assert HITS['rows'][0]['plan'] == HIT['plan'], "the delivered hit is the list's own frame-minimal"
