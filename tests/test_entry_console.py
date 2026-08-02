"""THE COMPOSITE ON CONSOLE: the herd, the entry plan, and a real A-press roll (session 86).

`tests/test_plan_console.py` gates the HERD half on the console -- the s73 plan, 22 samples, 0-ULP on
both actors. This gates the half that had never been delivered at all. The entry search's result is
stitched from two engines: the wall-less courtyard `FreeRun` walks Link on from the console's own
endpoint and hands over a roll entry, and the walled `ShoveCtx` decides `genuine` from that entry.
Sessions 79-85 confirmed 49 entries by replaying a real A-press OFFLINE; nothing had ever put the two
halves on the real game end to end, which the session-85 handoff called the only unpaid risk left.

So the frame-minimal deliverable hit of the 49 was appended to the s78 console log and delivered:
`_generated/s81/hits_seg2_a2_j1-2_s1_j6_b2_confirmed.json[0]` -- plan `[0,200,144,1,195,164,3]`, aim
`[85,182]`, 4 walk frames then the A-press. Nine truncate-and-read deliveries (n=78 the control, the
frame `courtyard_plan_s73_console.json` already measured, then every entry frame) each halt at plan
frame n-1 and read both actors. **All nine are 0-ULP on Link x/z, `proc`, `facing`, `travel`,
`speedF`, `m351C` and `nspeed`, and on Tetra x/z** -- so the console rolls from the entry the walled
engine was scored at, to the bit, with the lean and the momentum a `ShoveCtx` is only valid for.

`fixtures/courtyard_entry_s86_console.json` is LOCKED like every clean-DTM capture: for a fixed input
log the console is ground truth and never moves, so a disagreement here is the sim's to fix.

Offline: replays the locked log on the 0-ULP wired `FreeRun` (no Dolphin), ~0.3 s.
"""
import json
import os
import struct
import warnings

import pytest

from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES
from harness.tetrapush import seeds
from tww_sim.land.land import FRONT_ROLL


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_entry_s86_console.json')))
SAMPLES = {s['n']: s for s in FIX['samples']}
HIT = FIX['hit']
ENTRY_N = FIX['plan']['entry_n']
N_CONSOLE = FIX['plan']['n_console']


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulp(a, b):
    return abs(_bits(a) - _bits(b))


@pytest.fixture(scope="module")
def rollout():
    """One wired replay of the locked composite log, snapshotting every sampled frame.

    A truncated delivery keeps frames 0..n-1 byte-identical, so the state after `step(log[n-1])` is
    what the n-frame movie halts on -- the same convention `test_plan_console` runs under. WIRED
    (`seeds.make_freerun`), because that is the configuration the console runs."""
    env = seeds.load_env()
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    snaps = {}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, d in enumerate(FIX['log'][:max(SAMPLES)]):
            run.step(d)
            if (i + 1) in SAMPLES:
                L = run.link
                snaps[i + 1] = dict(x=float(L.pos_x), z=float(L.pos_z), facing=int(L.facing) & 0xFFFF,
                                    travel=int(L.travel) & 0xFFFF, proc=int(L.state) & 0xFF,
                                    speedF=float(L.speedF), nspeed=float(L.nspeed),
                                    m351C=int(L.m351C) & 0xFFFF, tx=float(run.tx), tz=float(run.tz))
    return snaps


@pytest.mark.parametrize("n", sorted(SAMPLES))
def test_the_sim_predicts_the_console_bit_exact_on_both_actors(n, rollout):
    """0-ULP on both positions at every console-measured frame of the entry walk and the roll
    (`[[zero-ulp-tests-only]]`; these are deterministic PauseMovie halts, not single-steps)."""
    s, sim = SAMPLES[n], rollout[n]
    assert _bits(sim['x']) == _bits(s['link']['x']), "Link x off %d ULP" % _ulp(sim['x'], s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z']), "Link z off %d ULP" % _ulp(sim['z'], s['link']['z'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x']), "Tetra x off %d ULP" % _ulp(sim['tx'], s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z']), "Tetra z off %d ULP" % _ulp(sim['tz'], s['tetra']['z'])


@pytest.mark.parametrize("n", sorted(SAMPLES))
def test_the_whole_roll_state_matches_including_the_two_the_ctx_is_keyed_on(n, rollout):
    """Position agreeing is not enough here: a `ShoveCtx` is valid only for the m351C it was built at
    and the momentum its schedule was baked at, so the confirm owes `m351C` and `nspeed` beside the
    proc, facing, travel and speedF."""
    s, sim = SAMPLES[n], rollout[n]
    assert sim['proc'] == s['link']['proc']
    assert sim['facing'] == s['link']['facing']
    assert sim['travel'] == s['link']['travel']
    assert sim['m351C'] == s['link']['m351C']
    assert _bits(sim['speedF']) == _bits(s['link']['speedF'])
    assert _bits(sim['nspeed']) == _bits(s['link']['nspeed'])


def test_the_console_rolls_from_the_entry_the_walled_engine_was_scored_at():
    """**THE HANDOVER, MEASURED.** The hit's `entry`/`facing`/`m351C`/`nspeed` are what `ShoveCtx`
    baked its schedule and its `genuine` verdict on; this is the console standing on them."""
    s = SAMPLES[ENTRY_N]['link']
    assert s['proc'] == FRONT_ROLL, "the console did not roll at the predicted entry frame"
    assert [s['x'], s['z']] == HIT['entry']
    assert s['facing'] == HIT['facing']
    assert s['m351C'] == HIT['m351C']
    assert _bits(s['nspeed']) == _bits(HIT['nspeed'])
    prev = SAMPLES[ENTRY_N - 1]['link']
    assert [prev['x'], prev['z']] == HIT['walk'], "the walk endpoint the entry is predicted from"


def test_tetra_is_the_frozen_constant_the_entry_search_assumes():
    """The whole search treats her as a MEASURED CONSTANT while Link walks on. The console agrees to
    the bit on every entry frame, and never leaves the stt-3 plow regime the model is defined on."""
    ref = SAMPLES[N_CONSOLE]['tetra']
    for n, s in SAMPLES.items():
        assert s['tetra']['stt'] == 3, "console row n=%d left stt 3 (a SCOPE break, not a bug)" % n
        assert _bits(s['tetra']['x']) == _bits(ref['x']), "Tetra moved by n=%d" % n
        assert _bits(s['tetra']['z']) == _bits(ref['z']), "Tetra moved by n=%d" % n


def test_the_delivered_log_is_the_confirmed_hit_appended_to_the_console_log():
    """The composite cannot drift from the two things it is made of: the locked herd log, and
    `confirm_entry`'s own frame construction for this hit (n0 holds, the two held segments, the aim
    A-press, then the neutral tail)."""
    herd = json.load(open(_fx('courtyard_plan_s73_console.json')))['log']
    assert FIX['log'][:N_CONSOLE] == herd
    plan, hold = list(HIT['plan']), dict(herd[-1], buttons=0)
    extra = [hold] * plan[0]
    for i in range(1, len(plan), 3):
        sx, sy, j = plan[i:i + 3]
        extra += [dict(hold, stickX=sx, stickY=sy)] * j
    extra.append(dict(hold, stickX=HIT['aim'][0], stickY=HIT['aim'][1], buttons=0x100))
    extra += [dict(hold, stickX=128, stickY=128)] * 3
    assert FIX['log'][N_CONSOLE:] == extra


def test_every_delivered_byte_reaches_the_console_as_the_physics_it_was_scored_at():
    """`dtm_make` delivers 255 as 254 and 0 as 1, so a plan must sim the DELIVERED bytes
    (`[[octagon-clamp-decode-bug]]`). Here nothing is rewritten at all -- every analog byte in the
    composite is interior -- which is what licensed delivering it as authored."""
    for i, d in enumerate(FIX['log']):
        sx, sy = d.get('stickX', 128), d.get('stickY', 128)
        assert EF.delivered(sx, sy) == (sx, sy), "frame %d main stick is rewritten by delivery" % i
        assert EF.survives_delivery(sx, sy)


def test_the_hit_is_the_frame_minimal_deliverable_one_of_the_confirmed_set():
    """Which of the 49 was spent, pinned so a re-bake cannot quietly deliver a different one. The
    hits file lives under the gitignored `_generated/`, so the cross-check runs only where the pass's
    output survives; the frame count and the deliverability are pinned unconditionally."""
    assert HIT['plan'][0] + sum(HIT['plan'][3::3]) == 4, "the measured frame floor (session 85)"
    assert EF.survives_delivery(*HIT['aim'])
    path = os.path.join(os.path.dirname(os.path.dirname(_fx('.'))), FIX['plan']['hits'])
    if not os.path.exists(path):
        pytest.skip("the session-85 hits pass is not on this clone (_generated/ is gitignored)")
    best = next(h for h in json.load(open(path))
                if h['confirm']['all_ok'] and h.get('deliverable'))
    assert best['hit']['plan'] == HIT['plan'] and best['hit']['aim'] == HIT['aim']


def test_the_offline_confirm_and_the_console_agree_on_the_same_entry():
    """`confirm_entry` is the offline A-press replay every hit owes; the console is the same question
    asked of the real game. Both must name the SAME entry -- otherwise one of them is answering about
    a roll the other never fires."""
    off = FIX['offline_confirm']['measured']
    s = SAMPLES[ENTRY_N]['link']
    assert off['entry'] == [s['x'], s['z']]
    assert off['facing'] == s['facing'] and off['m351C'] == s['m351C']
    assert ES.FRONT_ROLL == s['proc']
    assert FIX['offline_confirm']['all_ok']
