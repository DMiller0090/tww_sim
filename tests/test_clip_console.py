"""THE CLIP ON CONSOLE -- and the two terms that made the search's verdict a false positive.

`test_entry_console.py` gates the handover: the console rolls from the entry the walled engine was
scored at, bit for bit. This gates what happens for the REST of that roll, which is the half of the
composite the entry search had never delivered.

**The console did not clip.** Everything up to the cut is right -- Link's pre-cut brace point is
BIT-IDENTICAL to `ShoveCtx`'s own `old`, and the cut dispatches on the predicted frame at the
predicted facing -- and then the lunge does not thread the seam: Link ends 0.16 u from `old` where
the s86 prediction puts him 49.97 u away, out through the gap.

WHAT THAT NAMED. `entry_search`'s own docstring says the entry matters ONLY through the CUT-FRAME
PUSH, so the razor's inputs are Link's brace point (console-exact all along) and TETRA'S POSITION AT
THE CUT FRAME -- a simulated quantity, since the clip roll plows her ~100 u. Two things were measured
about it in session 86: she braces on the back wall (z pins at -940.25561523 = the plane -990.255615
plus her 50 u radius) and **the verdict flips at ONE f32 ULP of her**, while the best model of her was
0.15 u out. Session 87 closed both terms and they were different bugs in different engines:

  1. **The courtyard tracking gave her no BG collision at all**, so `from_f0` drove her 53 u THROUGH
     the wall. She now runs the same `mObjAcch.CrrPos` pass `npc_zl1` models (`FreeRun(walls_tetra=)`).
  2. **The SEARCH engine's baked Co centre dropped the `body_chn` counter-twist.** `ShoveCtx` bakes
     `body_cyl.roll_co_chain_consts`, which applied the `setWorldMatrix` base lean and not the
     `jointBeforeCB` twist by the POST-update lean -- worth up to 0.35 u of centre on a roll that
     carries a real turn lean, which is exactly what an entry off the herd does. It compounds through
     the plow into the 0.15 u at the cut frame. See `body_cyl.co_leans`.

With both closed the two engines and the console agree on every frame of the roll, `genuine` is
decidable, and this hit -- the frame-minimal one of the 49 -- re-scores **False**, which is what the
real game did.

`fixtures/courtyard_clip_s86_console.json` is LOCKED; its `prediction` block records the s86
prediction being judged, not a value to reproduce.

Offline: replays the locked log on the wired `FreeRun` (no Dolphin), plus one `ShoveCtx` build.
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
from tww_sim.land.land import CUT_F, FRONT_ROLL


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_clip_s86_console.json')))
SAMPLES = {s['i']: s for s in FIX['samples']}
HIT, PRED, WALL = FIX['hit'], FIX['prediction'], FIX['tetra_wall']
CUT_I, ENTRY_I = FIX['plan']['cut_i'], FIX['plan']['entry_i']
#: Schedule step k of the `ShoveCtx` roll is plan frame ROLL_F0 + k (the roll dispatches at ENTRY_I,
#: so step 0 is its second frame -- `entry_search.roll_entry`).
ROLL_F0 = ENTRY_I + 1


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _rollout(walls_tetra):
    """The composite in ONE engine: the wired delay-1 `FreeRun` the console runs, with the same
    culled courtyard mesh `turnaround` uses attached to BOTH actors. No schedule-step mapping --
    plan frame i is plan frame i."""
    env = seeds.load_env()
    run = seeds.make_freerun(env)
    run.link._walls = TA.WALLS
    run.walls_tetra = TA.WALLS if walls_tetra else None
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    snaps = {}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, d in enumerate(FIX['log']):
            run.step(d)
            snaps[i] = dict(x=float(run.link.pos_x), z=float(run.link.pos_z),
                            proc=int(run.link.state) & 0xFF, facing=int(run.link.facing) & 0xFFFF,
                            tx=float(run.tx), tz=float(run.tz))
    return snaps


@pytest.fixture(scope="module")
def rollout():
    return _rollout(True)


@pytest.fixture(scope="module")
def swept():
    """The SEARCH engine's own run of this hit: one `ShoveCtx` at the hit's configuration, Tetra
    seeded where the console froze her. Returns (result, per-step trace)."""
    ctx, sch, resid = ES.build_fast(HIT['facing'], HIT['m351C'], HIT['thrust'],
                                    (HIT['entry'][0], HIT['entry'][1]),
                                    nspeed=HIT.get('nspeed'))
    tx, tz = ES.console_seed()['tetra']
    res, tr = ctx.run_trace(tx, tz, 0)
    res['resid'] = resid((res['genuine'], res['old'][0], res['old'][1], res['new'][0],
                          res['new'][1], res['push'][0], res['push'][1]))
    return res, tr


# ----------------------------------------------------------------- what the console established

def test_the_console_braces_tetra_on_the_courtyard_back_wall():
    """A position that repeats to the BIT across frames is a WallCorrect pin, and the brace distance
    identifies the radius (the session-60 rule, applied to the other actor). Hers is the back wall
    plus 50 u -- `[[tetra-follow-model]]`'s BG WallCorrect R, arriving here as a measurement."""
    braced = [s for i, s in SAMPLES.items() if i in (91, 93, 98)]
    assert len({_bits(s['tetra']['z']) for s in braced}) == 1, "not a pin -- z moves between frames"
    assert _bits(braced[0]['tetra']['z']) == _bits(WALL['plane_z'] + WALL['radius'])
    zs = [v[2] for t in TA.WALLS for v in (t.v0, t.v1, t.v2)]
    assert any(_bits(z) == _bits(WALL['plane_z']) for z in zs), "the plane is in the mesh"


def test_the_console_stands_exactly_where_the_walled_engine_says_before_the_cut():
    """The roll, every wall brace along it and the whole 17-frame slide land Link on `ShoveCtx`'s own
    `old` BIT-EXACT. Whatever went wrong at the cut, it is not the point the cut fires from."""
    s = SAMPLES[CUT_I - 1]['link']
    assert s['proc'] == FRONT_ROLL
    assert _bits(s['x']) == _bits(PRED['old'][0])
    assert _bits(s['z']) == _bits(PRED['old'][1])


def test_the_cut_dispatches_where_predicted_and_then_does_not_lunge():
    """Right frame, right proc, right facing -- and 0.16 u of travel where the SESSION-86 prediction
    has 49.97 u through the seam. That prediction is what the fixture records, and it was a false
    positive on the real game."""
    s = SAMPLES[CUT_I]['link']
    assert s['proc'] == CUT_F and s['facing'] == HIT['facing']
    moved = math.hypot(s['x'] - PRED['old'][0], s['z'] - PRED['old'][1])
    lunge = math.hypot(PRED['new'][0] - PRED['old'][0], PRED['new'][1] - PRED['old'][1])
    assert PRED['genuine'] is True, "the fixture records what the search predicted"
    assert moved < 1.0 and lunge > 45.0
    assert math.hypot(s['x'] - PRED['new'][0], s['z'] - PRED['new'][1]) > 45.0


def test_the_verdict_differs_between_adjacent_f32_positions_of_tetra():
    """**THE PRICE OF HER, and it is the sharpest form of it.** ONE f32 step of her x -- the finest
    move she can make -- takes `genuine` from True to False. So the razor is thinner than her own
    representable grid, and nothing about her may be modelled to less than the bit."""
    u = FIX['tetra_ulp']
    assert u['ulp'] == pytest.approx(1.221e-4, rel=1e-3)
    assert FIX['prediction']['genuine'] is True and u['genuine'] is False
    sens = {r['d_tetra']: r for r in FIX['sensitivity']}
    assert sens[1e-5]['resid'] == sens[0.0]['resid'], "1e-5 rounds to the same f32 -- same verdict"
    assert all(not r['genuine'] for r in FIX['sensitivity'] if r['d_tetra'] >= 1e-4)
    # monotone once the offset is representable: a razor, not a speckle
    far = [r['resid'] for r in sorted(FIX['sensitivity'], key=lambda r: r['d_tetra'])
           if r['d_tetra'] >= 1e-4]
    assert all(a > b for a, b in zip(far, far[1:]))


# ------------------------------------------------------------------------ what the model must do

@pytest.mark.parametrize("i", sorted(SAMPLES))
def test_the_walled_roll_is_bit_exact_on_both_actors(i, rollout):
    """Every console sample of the clip roll, both actors, 0 ULP -- through the plow, through her
    wall brace, and at the cut frame, where the composite blocks the lunge exactly as the game did."""
    s, sim = SAMPLES[i], rollout[i]
    assert _bits(sim['x']) == _bits(s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z'])


def test_tetra_needs_her_bg_pass_or_the_clip_roll_drives_her_through_the_wall():
    """Guard the FIRST of the two session-87 terms by its symptom, so a refactor that drops
    `walls_tetra` fails here rather than silently re-opening the frontier: without it she ends the
    roll PAST the wall plane -- a place a 50 u cylinder cannot be -- and tens of units off the
    console at the frame the razor reads."""
    bare = _rollout(False)
    assert bare[CUT_I]['tz'] < WALL['plane_z'], "expected her driven through the plane"
    assert abs(bare[CUT_I]['tz'] - SAMPLES[CUT_I]['tetra']['z']) > WALL['radius']
    assert _bits(bare[91]['tz']) != _bits(SAMPLES[91]['tetra']['z'])


def test_the_search_engine_and_the_composite_agree_frame_for_frame(rollout, swept):
    """**THE CROSS-ENGINE GATE, the one that was missing.** The 49 were scored by `ShoveCtx` and
    handed to a composite that never re-ran the roll, so a Co-centre term present in one and absent
    from the other could not be seen. Now every schedule step is diffed against its plan frame on
    BOTH actors -- and both are diffed against the console by the test above."""
    _res, tr = swept
    for k, row in enumerate(tr):
        i = ROLL_F0 + k
        if i not in SAMPLES:
            continue
        assert _bits(row[0]) == _bits(rollout[i]['x']), "link x, step %d" % k
        assert _bits(row[1]) == _bits(rollout[i]['z']), "link z, step %d" % k
        assert _bits(row[2]) == _bits(rollout[i]['tx']), "tetra x, step %d" % k
        assert _bits(row[3]) == _bits(rollout[i]['tz']), "tetra z, step %d" % k


def test_the_search_predicts_whether_the_console_clips(swept):
    """**THE ONE THAT MATTERS.** Re-scored on the fixed engine, `genuine` says what the real game
    did -- and it says it quantitatively: the predicted post-CrrPos endpoint is the console's own
    0.16 u nudge off `old`, not a 49.97 u lunge."""
    res, _tr = swept
    s = SAMPLES[CUT_I]['link']
    assert res['genuine'] is False
    assert _bits(res['old'][0]) == _bits(PRED['old'][0])
    assert _bits(res['old'][1]) == _bits(PRED['old'][1])
    assert _bits(res['new'][0]) == _bits(s['x']) and _bits(res['new'][1]) == _bits(s['z'])


def test_the_clip_log_extends_the_locked_entry_log_without_touching_it():
    """The clip delivery is the entry delivery plus a tail: everything through the A-press is the
    same bytes, so the entry confirm still covers the first 83 frames of this one."""
    entry = json.load(open(_fx('courtyard_entry_s86_console.json')))['log']
    assert FIX['log'][:ENTRY_I] == entry[:ENTRY_I]
    assert FIX['log'][FIX['plan']['b_log']]['buttons'] == 0x200
    assert all(d['buttons'] == 0 for i, d in enumerate(FIX['log'])
               if i > ENTRY_I and i != FIX['plan']['b_log'])
