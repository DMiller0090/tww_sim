"""THE CLIP ON CONSOLE -- and the razor's second razor-thin term (session 86).

`test_entry_console.py` gates the handover: the console rolls from the entry the walled engine was
scored at, bit for bit. This gates what happens for the REST of that roll, which is the half of the
composite the entry search had never delivered.

**The console did not clip.** Everything up to the cut is right -- Link's pre-cut brace point is
BIT-IDENTICAL to `ShoveCtx`'s own `old`, and the cut dispatches on the predicted frame at the
predicted facing and roll phase -- and then the lunge does not thread the seam: Link ends 0.16 u from
`old` where the prediction puts him 49.97 u away, out through the gap.

WHAT THAT NAMES. `entry_search`'s own docstring says the entry matters ONLY through the CUT-FRAME
PUSH, so the razor's inputs are Link's brace point (console-exact here) and TETRA'S POSITION AT THE
CUT FRAME. The clip roll plows her ~100 u into the courtyard back wall, so that position is not the
measured constant the search seeds from -- it is a simulated one. Two things were measured about it:

  1. **She braces on the wall, and the console says so to the bit.** Her z pins at
     -940.25561523 for five straight frames = the wall plane -990.255615 plus her 50 u radius. The
     rollstab coupled engine reproduces that pin exactly; the courtyard `from_f0` tracks her as a
     bare XZ plow point with NO BG collision and drives her 53 u THROUGH the wall by plan frame 100.
  2. **The verdict flips at 1e-4 u of her.** `sensitivity` walks her seed away from the console's
     measurement: 1e-4 u already reads `genuine` False. The best available model of her cut-frame
     position is 0.15 u off the console -- 1500x that.

So `genuine` is not decidable at the current Tetra fidelity, and this hit -- the frame-minimal one of
the 49, every other term of it console-exact -- read False on the real game. The open work is Tetra
through the clip roll to the same standard the herd got, starting with the BG wall she is missing in
the engine that hands the composite over.

`fixtures/courtyard_clip_s86_console.json` is LOCKED. The model gaps are `xfail(strict=True)`, so
closing one XPASSes and fails the suite until it is taken off the open list.

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
#: Console frames the courtyard engine does not yet predict -- it gives Tetra no BG collision.
OPEN_TETRA = (91, 93, 98, 99, 100, 101)


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope="module")
def rollout():
    """The composite in ONE engine: the wired delay-1 `FreeRun` the console runs, with the same
    culled courtyard mesh `turnaround` uses attached to Link (`_walls` is a plain attribute on the
    Python path). No schedule-step mapping -- plan frame i is plan frame i."""
    env = seeds.load_env()
    run = seeds.make_freerun(env)
    run.link._walls = TA.WALLS
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
    """**THE VERDICT.** Right frame, right proc, right facing -- and 0.16 u of travel where the
    prediction has 49.97 u through the seam. `genuine` was a false positive on the real game."""
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
    representable grid, and a cut-frame position that is 0.15 u (about 1200 ULP) off, which is the
    best either engine manages, cannot decide it either way."""
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


# --------------------------------------------------- what the sim gets right, and what it does not

@pytest.mark.parametrize("i", [i for i in sorted(SAMPLES) if i not in OPEN_TETRA])
def test_the_free_flight_of_the_roll_is_bit_exact_on_both_actors(i, rollout):
    """Before Tetra touches the wall, the composite engine predicts the console exactly -- both
    actors, through the plow. The roll itself is not in question."""
    s, sim = SAMPLES[i], rollout[i]
    assert _bits(sim['x']) == _bits(s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z'])


@pytest.mark.parametrize("i", OPEN_TETRA)
@pytest.mark.xfail(strict=True, reason="the courtyard engine gives Tetra no BG collision, so the "
                                       "clip roll plows her through the back wall (session 86)")
def test_the_walled_roll_is_bit_exact_on_both_actors(i, rollout):
    """The open frontier, contiguous from the frame Tetra reaches the wall. Giving her the
    `npc_zl1` WallCorrect the rollstab engine already applies should XPASS these."""
    s, sim = SAMPLES[i], rollout[i]
    assert _bits(sim['tx']) == _bits(s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z'])
    assert _bits(sim['x']) == _bits(s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z'])


def test_the_open_frontier_is_a_contiguous_suffix():
    """The exact region must stay a PREFIX of the roll, so the frontier cannot be faked by excusing
    an awkward frame in the middle."""
    exact = [i for i in sorted(SAMPLES) if i not in OPEN_TETRA]
    assert exact == sorted(SAMPLES)[:len(exact)]
    assert min(OPEN_TETRA) > max(exact)


@pytest.mark.xfail(strict=True, reason="Tetra's cut-frame position is 0.15 u off the console and the "
                                       "verdict needs 1e-4 u (session 86)")
def test_the_search_predicts_whether_the_console_clips():
    """The one that matters: `genuine` should say what the real game does. Until Tetra through the
    clip roll is modelled to the razor's own precision, it does not."""
    s = SAMPLES[CUT_I]['link']
    clipped = math.hypot(s['x'] - PRED['new'][0], s['z'] - PRED['new'][1]) < 1e-3
    assert clipped == PRED['genuine']


def test_the_clip_log_extends_the_locked_entry_log_without_touching_it():
    """The clip delivery is the entry delivery plus a tail: everything through the A-press is the
    same bytes, so the entry confirm still covers the first 83 frames of this one."""
    entry = json.load(open(_fx('courtyard_entry_s86_console.json')))['log']
    assert FIX['log'][:ENTRY_I] == entry[:ENTRY_I]
    assert FIX['log'][FIX['plan']['b_log']]['buttons'] == 0x200
    assert all(d['buttons'] == 0 for i, d in enumerate(FIX['log'])
               if i > ENTRY_I and i != FIX['plan']['b_log'])
