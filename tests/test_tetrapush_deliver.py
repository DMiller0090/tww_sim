"""Gates for the tier-2 DELIVERY encoder (harness/tetrapush/deliver.py, session 54).

Offline only -- the splice is pure byte authoring, so its fidelity is checkable without Dolphin. The
live playback path (loadstate 1, truncate-and-read) cannot be unit-gated; its correctness argument is
the ground-truth run recorded in the tetrapush README.

These need the RECORDED movie (`GZLJ01.s02.dtm`), which lives beside the emulator and is NOT in the
repo, so they skip cleanly on a machine without it.
"""
import os
import struct

import pytest

from harness.tetrapush import deliver as DV
from harness.tetrapush import dtm_inputs as DI

_HAVE_REC = os.path.exists(DV.REC)
pytestmark = pytest.mark.skipif(not _HAVE_REC, reason="recorded GZLJ01.s02.dtm not present")

# a tiny plan exercising every channel the encoder must invert, incl. the L soft-lock dtm_make cannot emit
PLAN = [
    dict(stickX=193, stickY=243, buttons=0x40, triggerL=255, substickX=128, substickY=0),   # L held
    dict(stickX=165, stickY=196, buttons=0x100, triggerL=0, substickX=0, substickY=0),      # A (roll)
    dict(stickX=128, stickY=110, buttons=0x200, triggerL=0, substickX=255, substickY=0),    # B
    dict(stickX=255, stickY=0, buttons=0, triggerL=0, substickX=128, substickY=0),          # cal extremes
]


def _build(tmp_path, log, **kw):
    out = str(tmp_path / "spliced.dtm")
    return DV.build_boot_movie(log, out, **kw), out


def test_splice_round_trips_and_keeps_the_prefix_byte_identical(tmp_path):
    """The delivered tail must read back as the plan, and game-frames 0..F0 must be untouched."""
    info, out = _build(tmp_path, PLAN)
    assert info['rt_mismatch'] == 0
    assert info['prefix_ok']
    rec = open(DV.REC, 'rb').read()
    mine = open(out, 'rb').read()
    keep = DV.HDR + ((info['F0'] + 1) * 8) * DV.ROW      # header + game-frames 0..F0
    assert mine[DV.HDR:keep] == rec[DV.HDR:keep], "recorded prefix diverged from the recording"
    assert mine[12] == 0, "must stay a bFromSaveState=0 BOOT movie"


def test_latched_input_matches_the_recording_when_the_recorded_tail_is_reappended(tmp_path):
    """The ground-truth fidelity property: re-authoring the RECORDED tail through the encoder delivers
    the same LATCHED input (poll index 2 -- the poll the game actually reads) as the recording itself.
    Raw byte equality is NOT required; the other three polls are never latched."""
    port0 = DI.load_port0(DV.REC)
    F0 = DI.find_f0(port0)
    log = [DI.frame_input(port0, F0 + 1 + i) for i in range(40)]
    _info, out = _build(tmp_path, log)
    mine = DI.load_port0(out)
    for i in range(40):
        assert DI.frame_input(mine, F0 + 1 + i) == DI.frame_input(port0, F0 + 1 + i), \
            "latched input differs at tail frame %d" % i


def test_l_soft_lock_survives_the_encode(tmp_path):
    """`dtm_make.pad_to_cs` cannot emit L (0x40) at all; the plan encoder must, with the analog trigger."""
    _info, out = _build(tmp_path, PLAN)
    port0 = DI.load_port0(out)
    F0 = DI.find_f0(DI.load_port0(DV.REC))
    got = DI.frame_input(port0, F0 + 1)
    assert got['buttons'] & 0x40, "L was dropped"
    assert got['triggerL'] == 255, "analog trigger must mirror the L press"
    assert DI.frame_input(port0, F0 + 2)['buttons'] & 0x100      # A
    assert DI.frame_input(port0, F0 + 3)['buttons'] & 0x200      # B


def test_sticks_are_delivered_cal_clamped(tmp_path):
    """dtm_make delivers 255 as 254 and 0 as 1, so plans must be simulated on the DELIVERED bytes
    ([[octagon-clamp-decode-bug]]). The encoder writes the clamped values."""
    _info, out = _build(tmp_path, PLAN)
    port0 = DI.load_port0(out)
    F0 = DI.find_f0(DI.load_port0(DV.REC))
    got = DI.frame_input(port0, F0 + 4)                  # authored raw 255 / 0
    assert (got['stickX'], got['stickY']) == (254, 1)


def test_tick_extend_exceeds_the_recorded_ticks_without_wrapping_negative(tmp_path):
    """tickCount governs Movie::CheckInputEnd: keeping the recorded value truncates a longer tail, but
    the maxed 0xFFFF... reads as signed -1 and crashes State::Load. 'extend' must land strictly between."""
    rec_tick = struct.unpack_from('<Q', open(DV.REC, 'rb').read(DV.HDR), 237)[0]
    ext, _ = _build(tmp_path, PLAN, tick_mode='extend')
    assert ext['tickCount'] > rec_tick, "extended ticks must outlast the recording"
    assert struct.unpack('<q', struct.pack('<Q', ext['tickCount']))[0] > 0, "must not read as negative"
    keep, _ = _build(tmp_path, PLAN, tick_mode='keep')
    assert keep['tickCount'] == rec_tick
    mx, _ = _build(tmp_path, PLAN, tick_mode='max')
    assert struct.unpack('<q', struct.pack('<Q', mx['tickCount']))[0] == -1, \
        "the maxed value is the State::Load crash -- pinned here so nobody 'fixes' extend into it"


def test_truncating_the_plan_leaves_alignment_untouched(tmp_path):
    """Truncate-and-read relies on a shorter movie delivering the SAME frames at the same game-frames."""
    full, out_f = _build(tmp_path, PLAN)
    part, out_p = DV.build_boot_movie(PLAN[:2], str(tmp_path / "short.dtm")), str(tmp_path / "short.dtm")
    assert part['F0'] == full['F0']
    a, b = DI.load_port0(out_f), DI.load_port0(out_p)
    for i in range(2):
        assert DI.frame_input(a, full['F0'] + 1 + i) == DI.frame_input(b, part['F0'] + 1 + i)
    assert part['frameCount'] < full['frameCount']
