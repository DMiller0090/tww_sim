"""The clip roll's inputs and its REAL frame cost (`harness.tetrapush.clip_roll`, session 143).

Every ranking in the tetra-push stack has priced the clip roll as ``PairFrame.cut_step``. These gate
the two facts that says is wrong -- the cut lands on roll frame ``cut_step + 2``, and the roll's entry
frame is `entry_search.roll_entry`'s one full step -- against the SIMULATOR rather than against the
arithmetic that produced them, plus the two dispatch traps a herd endpoint walks into.

0-ULP throughout (`[[zero-ulp-tests-only]]`): the entry-position assertion is ``_bits``-exact.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from harness.rollstab import fast_shove as FS
from harness.rollstab import turnaround as TA
from harness.tetrapush import clip_roll as CR
from harness.tetrapush import entry_search as ES
from harness.tetrapush import search as S
from harness.tetrapush import two_roll as TR
from tww_sim.land.constants import ATN_ACTOR_MOVE, CUT_F, FRONT_ROLL, MOVE
from tww_sim.land.land import LandState

FACING = 40660
GROUND_Y = -6.0


def _walker(facing=FACING, speedF=17.0):
    """A LandState cruising at the walk cap -- the state a herd's roll chain dispatches from."""
    return LandState(pos_x=0.0, pos_z=0.0, pos_y=GROUND_Y, facing=facing, travel=facing,
                     state=MOVE, nspeed=speedF, speedF=speedF, use_anim=True, native=False,
                     sword_drawn=True)


def _run(cut_step, aim, facing=FACING, speedF=17.0):
    """Fire `clip_stream` at a cruising walker; return (rows, entry_idx, cut_idx, entry_pos, walk)."""
    lk = _walker(facing, speedF)
    rows, entry_i, cut_i, entry, walk = [], None, None, None, None
    for k, d in enumerate(CR.clip_stream(aim, cut_step)):
        if lk.state == MOVE and entry_i is None:
            # the pre-entry walk endpoint, refreshed until it rolls: `_roll_init` reads the speedF
            # the PREVIOUS frame left, and `roll_entry` steps from the position it left
            walk = (lk.pos_x, lk.pos_z, lk.speedF)
        lk.step(d['stickX'], d['stickY'], d['buttons'], d['triggerL'],
                d['substickX'], d['substickY'])
        rows.append((k, int(lk.state)))
        if lk.state == FRONT_ROLL and entry_i is None:
            entry_i, entry = k, (lk.pos_x, lk.pos_z)
        if lk.state == CUT_F and cut_i is None:
            cut_i = k
    return rows, entry_i, cut_i, entry, walk


def test_the_stream_is_one_a_press_and_one_b_rising_edge_at_cut_step_plus_one():
    """The shape `build_sticks` delivered live: A at 0, neutral through the roll, ONE UP+B."""
    st = CR.clip_stream((90, 184), 15)
    b = [k for k, d in enumerate(st) if d['buttons'] & CR.PAD_B]
    a = [k for k, d in enumerate(st) if d['buttons'] & S.PAD_A]
    assert b == [CR.b_index(15)] == [16], b
    assert a == [0, 1], a
    assert (st[b[0]]['stickX'], st[b[0]]['stickY']) == CR.CUT_STICK
    # the stick MUST be neutral through the roll or `_roll_exit` fires before the thrust
    assert all((d['stickX'], d['stickY']) == CR.NEUTRAL for k, d in enumerate(st)
               if 1 <= k < b[0]), 'a pushed mid-roll stick exits the roll without a cut'
    # `build_sticks`' own b_step is measured from the frame AFTER the A press -- the same index
    assert CR.b_index(TA.THRUST + 2) == TA.B_STEP + 1


@pytest.mark.parametrize('cut_step', list(range(*(lambda w: (w[0], w[1] + 1))(ES.cut_step_window()))))
def test_the_cut_lands_on_roll_frame_cut_step_plus_two(cut_step):
    """**The correction.** Simulated, not asserted from the schedule that produced the number."""
    aim = CR.aim_bytes_for(FACING, 0)['bytes']
    _rows, entry_i, cut_i, _e, _w = _run(cut_step, aim)
    assert entry_i is not None and cut_i is not None, 'the stream did not roll-and-cut'
    assert cut_i - entry_i + 1 == cut_step + 2
    assert CR.roll_frames(cut_step) == cut_step + 2


def test_the_roll_entry_frame_is_one_full_roll_step_0_ulp():
    """`entry_search.roll_entry` is the razor's ``entry``; this is the frame that produces it.

    Exact equality on the f32 values, no tolerance (`[[zero-ulp-tests-only]]`)."""
    aim = CR.aim_bytes_for(FACING, 0)
    _rows, _ei, _ci, entry, walk = _run(15, aim['bytes'])
    want = ES.roll_entry(walk[:2], aim['facing'], ES.roll_nspeed(walk[2]))
    assert entry == (want[0], want[1])


def test_the_analytic_schedule_refuses_exactly_what_the_simulator_refuses():
    """**The gate that would have caught the thrust-11 terminal.**

    `entry_search.fast_schedule` computes ``cut_step = thrust + 2`` in closed form and used to accept
    any thrust; `turnaround.extract_schedule_at` runs the roll and RAISES when no CUT is ever
    dispatched. Session 136 read a thrust-11 family off the analytic form and carried its
    ``cut_step`` 13 -- three frames under thrust 14's -- into every bound after it. The old fidelity
    gate only ever swept `ES.THRUSTS`, i.e. exactly where the two already agreed."""
    for thrust in range(9, 19):
        try:
            TA.extract_schedule_at(ES.TAB_ENTRY, ES.TAB_FACING, 0, TA.GROUND_Y,
                                   FS.make_inputs(thrust))
            sim_ok = True
        except ValueError:
            sim_ok = False
        try:
            ES.fast_schedule(ES.TAB_FACING, 0, thrust)
            fast_ok = True
        except ValueError:
            fast_ok = False
        assert sim_ok == fast_ok, 'thrust %d: simulated %s, analytic %s' % (thrust, sim_ok, fast_ok)
    assert tuple(range(*(lambda w: (w[0], w[1] + 1))(ES.thrust_window()))) == ES.THRUSTS


def test_the_untarget_flip_cannot_carry_the_clip_roll():
    """The trap the banked ladder sits in: one frame past the roll exit the momentum is gone.

    `_roll_init` clamps the roll's whole momentum off the PRE-ROLL speedF, so the untarget flip's
    -25.72 gives `ROLL_MIN`, a 5 u/frame roll -- against a handoff runway grid starting at 160."""
    lk = _walker()
    lk.speedF = -25.727313995361328              # the measured cycle-1 untarget flip
    d = CR.dispatchable(lk)
    assert d['nspeed'] == 5.0 and not d['at_cap']
    lk.speedF = 26.0                             # the roll-exit frame, one frame earlier
    assert CR.dispatchable(lk)['nspeed'] == ES.ROLL_NSPEED == 26.0


def test_the_roll_exit_proc_refuses_the_dispatch():
    """A herd roll exits into ATN_ACTOR_MOVE while the lock is live, and that proc rolls out of
    nothing -- `LandState.step`'s roll arm re-tests ``state in ROLL_FROM``."""
    lk = _walker()
    lk.state = ATN_ACTOR_MOVE
    assert not CR.dispatchable(lk)['ok']
    lk.state = MOVE
    assert CR.dispatchable(lk)['ok']


def test_the_aim_inverts_the_alphabet_onto_the_wanted_sine_cell():
    """`aim_bytes_for` is `entry_search.aim_alphabet`'s map inverted; the schedule is quantized to
    `aim_cell`, so landing the right CELL is the claim, and the residual BAM error is reported."""
    for cs in (0, 34325, 35660):
        got = CR.aim_bytes_for(FACING, cs)
        assert abs(got['err']) <= ES.SIN_CELL_BAM // 2, got
        assert got['cell_ok'], got
        assert (got['facing'] - 0x8000 - cs) & 0xFFFF in {a for a, _b in TR.roll_aim_fan()}
