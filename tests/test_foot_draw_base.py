"""THE POSE-STREAM GATE: does the sim draw Link's feet where the console draws them?

`posMoveFromFootPos` turns the last two DRAWN foot poses into `speedF`, so on any frame where the
walk anim owns the speed (m3598 != 0) the toe stream IS the position. Session 58 root-caused the
node-1 frontier to two faults in that stream and this is what pins them:

  1. **The sword-drawn anim pair.** Link's `mEquipItem` is SWORD for the whole courtyard window, so
     `getAnmData` (d_a_player_main.cpp:12950) serves the under-body anims out of
     `mSwordAnmIndexTable`: ANM_WALK -> ANM_WALKS, ANM_DASH -> ANM_DASHS. The table ends at
     ANM_CUTTURNPWLR (0x1A), so ANM_ROLLF (0x32) and the ATN strafe set map to themselves.
  2. **The draw base.** The model is drawn at frame END, from the POST-posMove position, and with NO
     lean on a proc `*_init` frame (`commonProcInit` zeroes shape_angle.z before `setWorldMatrix`).
     The base is cancelled again by m37B4, so this only moves the pose by ULPs -- but those ULPs are
     the whole toe delta, and the toes carry WORLD-magnitude quantization (1.2e-4 u at |x| ~ 1600).

`fixtures/courtyard_node1_foot_s57.json` is the LOCKED live capture (session 57's footscan probe,
deterministic truncate-and-read halts). Immutable: the sim converges to it, never the reverse
(`tests/dolphin/README.md#locked-tests-are-immutable-hard-rule`).
"""
import json
import os
import struct

import pytest

from harness.tetrapush import seeds, from_f0


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


LIVE = json.load(open(_fx('courtyard_node1_foot_s57.json')))
LOG = json.load(open(_fx('courtyard_node1_console.json')))['log']
# foot_fk.step_feet's flat 12-tuple order
KEYS = ('rtoe', 'ltoe', 'rheel', 'lheel')


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope="module")
def poses():
    """The sim's drawn foot pose after each frame of node 1's plan (the stream the compose reads)."""
    run = seeds.make_freerun(seeds.load_env())
    run.pre_seed_input(seeds.dtm_input_at(seeds.load_env())(0))
    out = {}
    want = max(r['n'] for r in LIVE['rows'])
    for i, d in enumerate(LOG[:want]):
        run.step(d)
        out[i + 1] = tuple(run.link._foot.t1)
    return out


@pytest.mark.parametrize("row", LIVE['rows'], ids=lambda r: "n%d" % r['n'])
def test_the_drawn_foot_pose_matches_the_console_in_xz(row, poses):
    """0-ULP on every model-local x and z of both toes and both heels.

    X/Z only: Y additionally carries `m35B8`, footBgCheck's draw-base Y shift (-5.198 at the state-2
    seed), which this replay does not model. That shift is XZ-irrelevant by construction -- the base
    is a Y-rotation, so its translation Y never enters the x/z rows -- and `posMoveFromFootPos` reads
    only x and z of the planted toe. The live Y is kept in the fixture so the gap stays visible.
    """
    sim = poses[row['n'] - 1]          # live mFootData at n == the pose drawn on frame n-1
    for k, key in enumerate(KEYS):
        for ax, name in ((0, 'x'), (2, 'z')):
            assert _bits(sim[k * 3 + ax]) == _bits(row[key][ax]), \
                "%s.%s at n=%d off %d ULP" % (key, name, row['n'],
                                              _bits(sim[k * 3 + ax]) - _bits(row[key][ax]))


def test_the_courtyard_link_has_his_sword_drawn(poses):
    """The seed carries mEquipItem == SWORD, so the walk/dash codes are the WALKS/DASHS pair. Pinned
    structurally as well as through the pose above, because flipping it back would look like a
    plausible simplification (dash and dashs are identical at joints 0-4/14 -- only the FEET differ,
    which is exactly what this stream is)."""
    assert from_f0.SWORD_DRAWN is True
    run = seeds.make_freerun(seeds.load_env())
    st = run.link._foot.st
    assert run.link._foot.sword is True
    assert (st._walk, st._dash) == ('walks', 'dashs')


def test_the_courtyard_foot_draws_at_frame_end():
    """The deferred draw is armed by the seed (and `LandState.step` completes it after integration
    with the proc-init lean rule). Without it the pose is taken at the PRE-posMove base, which the
    live capture above rejects by 32-128 ULP per component."""
    run = seeds.make_freerun(seeds.load_env())
    assert run.link._foot.defer_draw is True
