"""The WALL PASS as a PHASE SETTING -- off for the herd, on and required for the final roll + thrust.

`seeds.make_freerun` did not wire either actor's `dBgS_Acch::CrrPos` for ~60 sessions, so every
search carried Tetra as a bare XZ plow point with no BG collision and leaned on
`objective.frame_is_wall_free` -- a prune that forbids her from APPROACHING a wall -- to stand in for
it. That is the right constraint for the HERD (`objective`'s rule 4) and the wrong one for the CLIP,
which happens with her wedged in the corner: applied there it refuses the mechanic, and on the s148
ladder's rung 5 it killed 205600 of 205600 children one frame past the at-cap cloud.

These gates hold the three things that make the phase split safe to rely on:

  * turning the pass on is INERT on the window every 0-ULP gate compares against (both actors stay
    331-337 u from geometry there, so it is a strict no-op) -- asserted bit-for-bit, not to tolerance;
  * a braced Tetra lands on the value the CONSOLE locked, not merely somewhere sensible;
  * and a NATIVE run cannot pretend to be walled, because `LandCore.step_courtyard` has no BG pass.
"""
import json
import os
import struct
import warnings

import pytest

from harness.tetrapush import objective as O
from harness.tetrapush import seeds as SD

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLE = os.path.join(_REPO, 'fixtures', 'courtyard_clip_s86_console.json')
LADDER = os.path.join(_REPO, 'fixtures', 'courtyard_candidate_ladder.json')
NEUTRAL = dict(stickX=128, stickY=128, buttons=0, triggerL=0, substickX=128, substickY=0)


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


@pytest.fixture(scope='module')
def env():
    return SD.load_env()


def test_walls_default_off_and_flagged(env):
    """The herd phase is the DEFAULT, and it says so on the run rather than by omission."""
    herd = SD.make_freerun(env)
    assert herd.walls_tetra is None
    assert herd.walls_modelled is False
    term = SD.make_freerun(env, walls=True)
    assert term.walls_tetra is not None and term.link._walls is not None
    assert term.walls_modelled is True


def test_the_wall_pass_is_inert_on_the_gated_window(env):
    """Wiring it may not move a single bit of the 45-frame window the 0-ULP gates are built on.

    This is what licenses the phase setting existing at all: if it were not a no-op here, turning it
    on for the terminal would silently re-base every banked reference."""
    inp = SD.dtm_input_at(env)
    a = SD.make_freerun(env)
    b = SD.make_freerun(env, walls=True)
    a.pre_seed_input(inp(0))
    b.pre_seed_input(inp(0))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for k in range(45):
            d = inp(k)
            a.step(d)
            b.step(d)
            assert _bits(a.link.pos_x) == _bits(b.link.pos_x), 'Link x diverged at f%d' % (k + 1)
            assert _bits(a.link.pos_z) == _bits(b.link.pos_z), 'Link z diverged at f%d' % (k + 1)
            assert _bits(a.tx) == _bits(b.tx), 'Tetra x diverged at f%d' % (k + 1)
            assert _bits(a.tz) == _bits(b.tz), 'Tetra z diverged at f%d' % (k + 1)


def test_a_braced_tetra_lands_on_the_console_locked_pin(env):
    """Walled, she pins at the wall plane plus her radius -- the value the console locked.

    Unwalled she goes straight through it, which is the defect the phase setting exists for. The
    reference is read out of `fixtures/courtyard_clip_s86_console.json`, never restated here."""
    with open(CONSOLE) as fh:
        con = json.load(fh)
    pins = [s['tetra']['z'] for s in con['samples']
            if abs(s['tetra']['z'] - con['tetra_wall']['brace_z']) < 1e-3]
    assert pins, 'the console fixture holds no braced sample to gate against'
    pin = pins[0]
    assert all(_bits(p) == _bits(pin) for p in pins), (
        'the console holds ONE braced value for consecutive frames -- that is what pinning means')

    with open(LADDER) as fh:
        cand = next(c for c in json.load(fh)['candidates'] if c['rank'] == 5)
    out = {}
    for walled in (False, True):
        run = SD.make_freerun(env, walls=walled)
        run.pre_seed_input(SD.dtm_input_at(env)(0))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            for d in cand['log']:
                run.step(d)
            for _ in range(9):                      # her own handover carries her into the wall
                run.step(NEUTRAL)
        out[walled] = run.tz
    assert _bits(out[True]) == _bits(pin), (
        'walled Tetra should pin at the console-locked %r, got %r' % (pin, out[True]))
    assert out[False] < pin, (
        'unwalled Tetra should pass THROUGH the plane (that is the defect), got %r' % out[False])


def test_a_native_run_cannot_pretend_to_be_walled(env):
    """`LandCore.step_courtyard` has no BG pass, so the mesh must be refused, not silently ignored.

    Assigning it after construction is how a probe gets a Tetra that looks walled and is not, so
    `wall_for_terminal` repeats the constructor's check instead of trusting it."""
    with pytest.raises(ValueError):
        SD.make_freerun(env, native=True, walls=True)
    nat = SD.make_freerun(env, native=True)
    assert nat.walls_modelled is False
    with pytest.raises(ValueError):
        SD.wall_for_terminal(nat)


def test_frame_ok_guards_exactly_the_unmodelled_actors(env):
    """The guard reads the RUN: unwalled it must still refuse her, walled it must not."""
    walls = O.courtyard_walls()
    with open(LADDER) as fh:
        cand = next(c for c in json.load(fh)['candidates'] if c['rank'] == 5)
    herd = SD.make_freerun(env)
    herd.pre_seed_input(SD.dtm_input_at(env)(0))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in cand['log']:
            herd.step(d)
        for _ in range(4):                          # herd+4 is where her guard bites (s149)
            herd.step(NEUTRAL)
    assert not O.clear_of_walls(herd.tx, herd.tz, O.TETRA_WALL_R, walls), (
        'the rung-5 handover should carry her inside her cylinder by herd+4')
    assert O.frame_ok(herd, walls) is False, 'unwalled, her guard must still refuse'
    herd.walls_modelled = True
    assert O.frame_ok(herd, walls) is True, 'walled, the modelled pass must not be refused'
