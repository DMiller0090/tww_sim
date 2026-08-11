"""**THE SEARCH SPACE MUST CONTAIN THE CONSOLE SOLUTION** -- the 101 fed back through the search's own
configuration, phase by phase.

`[[search-space-contains-human]]`: a search whose range does not intrinsically contain the known-good
reference input is broken, and the way to know is to gate it rather than to reason about it. Session
149 found out the hard way that it was not gated here. `seeds.make_freerun` -- what every planner
stage builds from -- wired NEITHER actor's `dBgS_Acch::CrrPos`, so Tetra had no BG collision at all
and the searches leaned on `objective.frame_is_wall_free`, a prune that forbids her from APPROACHING a
wall, to stand in for the missing pass. Measured against the locked console delivery, that
configuration **refuses the console's own clip from frame 90 of 107** -- seven frames into the clip
roll, and every frame after it including the cut. The best plan in the repo was outside the search's
own range, and nothing said so.

The fix is that the wall pass is a PHASE SETTING, not a fidelity knob (Dereck, session 149): OFF for
the herd, where the prune IS the constraint (`objective`'s rule 4 -- a herd that shoves her into
geometry is not one we want), and ON for the FINAL ROLL + THRUST, where the clip happens with her
wedged in the corner and her brace is the mechanic. These gates hold that split against the console:

  * the incumbent constant is the locked log's own cut frame, not a floating literal;
  * the HERD phase contains the human -- the prune refuses no frame of it;
  * the UNWALLED configuration demonstrably does NOT contain the human's clip (the regression that
    would have caught session 149's bug on the session it was introduced);
  * the PHASE-CORRECT configuration reproduces the console at the cut, bit-exact, both actors;
  * and switching the phase cannot perturb the herd, because the pass is provably inert until the
    frame the roll first wedges her.

Every number is read out of `fixtures/courtyard_clip_s90_console.json` (LOCKED: for a fixed input log
the console is ground truth and never moves) -- none is restated here.
"""
import json
import os
import struct
import warnings

import pytest

from harness.tetrapush import objective as O
from harness.tetrapush import seeds as SD

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLE = os.path.join(_REPO, 'fixtures', 'courtyard_clip_s90_console.json')

with open(CONSOLE) as _fh:
    FIX = json.load(_fh)
PLAN = FIX['plan']
LOG = FIX['log']
#: the roll dispatches here, so this is the latest the terminal phase may begin
ENTRY_I = PLAN['entry_i']
CUT_I = PLAN['cut_i']


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _replay(walls_from=None):
    """The console log on the SEARCH's own factory. ``walls_from`` = the frame index the terminal
    phase begins (None = never, the herd configuration the searches actually ran).

    Returns one row per frame: both actors, the proc, and whether the search's own guard
    (`objective.frame_ok`, which reads the run) would have kept the frame."""
    walls = O.courtyard_walls()
    env = SD.load_env()
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, d in enumerate(LOG):
            if walls_from is not None and i == walls_from:
                SD.wall_for_terminal(run)
            run.step(d)
            rows.append(dict(i=i, x=float(run.link.pos_x), z=float(run.link.pos_z),
                             facing=int(run.link.facing) & 0xFFFF, speedF=float(run.link.speedF),
                             proc=int(run.link.state) & 0xFF, tx=float(run.tx), tz=float(run.tz),
                             ok=bool(O.frame_ok(run, walls))))
    return rows


@pytest.fixture(scope='module')
def herd_config():
    """The configuration every planner stage actually ran: walls never wired."""
    return _replay(walls_from=None)


@pytest.fixture(scope='module')
def phase_config():
    """The phase-correct configuration: herd unwalled, terminal walled from the roll dispatch."""
    return _replay(walls_from=ENTRY_I)


def test_the_incumbent_is_the_locked_logs_own_cut_frame():
    """`objective.TOTAL_INCUMBENT` is the bar every bound is quoted against, so it may not drift away
    from the delivery it was measured from."""
    assert O.TOTAL_INCUMBENT == CUT_I, (
        'TOTAL_INCUMBENT %d should be the console cut frame %d from %s'
        % (O.TOTAL_INCUMBENT, CUT_I, os.path.basename(CONSOLE)))


def test_the_herd_phase_contains_the_console_solution(herd_config):
    """Up to the roll dispatch, the search's own prune must refuse NOTHING the human did.

    This is the half that was always fine, and it is worth pinning: it is what makes the herd prune a
    constraint rather than a bug. If a change starts refusing the human's herd, the search can no
    longer contain the best known plan and this fails first."""
    refused = [r['i'] for r in herd_config[:ENTRY_I] if not r['ok']]
    assert not refused, (
        'the search prune refuses the console solution during the HERD phase at frames %s -- the '
        'search can no longer reach the best known plan' % refused[:12])


def test_the_unwalled_configuration_does_not_contain_the_consoles_clip(herd_config):
    """**The regression for session 149's bug.** With no wall pass wired, the prune that stands in for
    it refuses the console's own clip roll -- so the searches were hunting inside a space that
    excluded the best plan in the repo, and every "this rung is dead" read off that prune was
    unproven (`[[infeasible-needs-proof]]`).

    The refusal starts INSIDE the roll, not at the herd: it is the roll that wedges her."""
    refused = [r['i'] for r in herd_config if not r['ok']]
    assert refused, 'expected the unwalled prune to refuse the console clip -- it is why walls exist'
    assert refused[0] > ENTRY_I, (
        'the refusal should begin inside the clip roll (dispatch %d), not before it' % ENTRY_I)
    assert CUT_I in refused, (
        'the CUT frame %d must be among the refused frames -- that is the whole defect' % CUT_I)
    assert herd_config[CUT_I]['proc'] == FIX['samples'][0]['model']['proc'], (
        'the unwalled run still reaches the cut proc; what it gets wrong is Tetra, and the prune '
        'then throws the frame away')


def test_the_phase_correct_configuration_keeps_every_frame(phase_config):
    """Walled from the roll dispatch, the search's guard keeps the whole console solution."""
    refused = [r['i'] for r in phase_config if not r['ok']]
    assert not refused, (
        'the phase-correct configuration still refuses the console solution at %s' % refused[:12])


def test_the_phase_correct_configuration_reproduces_the_console_cut(phase_config):
    """Both actors bit-exact at the cut frame, against the locked console sample.

    0-ULP, not a tolerance (`[[zero-ulp-tests-only]]`): the sample the fixture marks ``all_exact`` is
    a clean-DTM console read, so a disagreement is the sim's."""
    smp = next(s for s in FIX['samples'] if s['i'] == CUT_I)
    assert smp['all_exact'], 'gating against a sample the fixture does not call exact'
    got = phase_config[CUT_I]
    for key, ref in (('x', smp['link']['x']), ('z', smp['link']['z']),
                     ('speedF', smp['link']['speedF']),
                     ('tx', smp['tetra']['x']), ('tz', smp['tetra']['z'])):
        assert _bits(got[key]) == _bits(ref), (
            '%s at the cut frame %d: got %r, console %r' % (key, CUT_I, got[key], ref))
    assert got['facing'] == (smp['link']['facing'] & 0xFFFF)


def test_switching_the_phase_cannot_perturb_the_herd(herd_config, phase_config):
    """The two configurations must agree bit-for-bit until the frame the roll first wedges her.

    This is what licenses the phase setting: turning the pass on for the terminal may not re-base a
    single frame of the herd that every banked reference was measured on."""
    first = next((a['i'] for a, b in zip(herd_config, phase_config)
                  if (_bits(a['x']), _bits(a['z']), _bits(a['tx']), _bits(a['tz']))
                  != (_bits(b['x']), _bits(b['z']), _bits(b['tx']), _bits(b['tz']))), None)
    assert first is not None, 'the wall pass changed nothing at all -- it should change the clip'
    assert first > ENTRY_I, (
        'the wall pass diverges at frame %s, at or before the roll dispatch %d -- then the phase '
        'boundary is in the wrong place and the herd is not safe' % (first, ENTRY_I))
    for a, b in zip(herd_config[:first], phase_config[:first]):
        assert (_bits(a['x']), _bits(a['z']), _bits(a['tx']), _bits(a['tz'])) == \
               (_bits(b['x']), _bits(b['z']), _bits(b['tx']), _bits(b['tz']))
