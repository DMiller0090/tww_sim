"""The Courtyard Tetra-plow law, live-gated against the RAM ground truth.

`harness/tetrapush/tetra_plow` encodes the measured push law -- Tetra's per-frame displacement is the
FULL Co-cylinder overlap depth computed from Link's animated mCyl centre (Tetra takes 100 %, Link's
share 0). This gate feeds the law the RAM-captured Link Co centres (fixtures/courtyard_push_cyl.json,
single-stepped from slot 2) and asserts:

  * frac = tetra_move / depth == 1.0 (Tetra absorbs the full overlap), every push frame; and
  * reconstructing her whole trajectory from Link's centre path + her seed tracks the live capture to
    <0.01 u over the full push.

This isolates the Tetra side of the coupled dynamics (the plow) from Link's own physics, and is the
predictor the planner uses once Link's mCyl-centre path is modelled offline. The Link Co centre is the
RAM ground truth here; a `move_co_center` model would replace it. See harness/tetrapush/README.md.
"""
import json
import math
import os

import pytest

from harness.tetrapush.tetra_plow import plow_depth, plow_step, reconstruct

_FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'fixtures', 'courtyard_push_cyl.json')


def _dedup(frames):
    """Drop single-step DOUBLE-READ frames (the capture re-sampling one game frame -- e.g. cyc2
    f44==f45, [[run-dtm-1frame-jitter]]): a frame bit-identical to its predecessor in BOTH Link's Co
    centre and Tetra's pos is the same game frame read twice, not a real (0-displacement) frame."""
    out = [frames[0]]
    for f in frames[1:]:
        p = out[-1]
        if f['link']['cyl'] == p['link']['cyl'] and f['tetra']['pos'] == p['tetra']['pos']:
            continue
        out.append(f)
    return out


@pytest.fixture(scope='module')
def cyl():
    if not os.path.exists(_FIX):
        pytest.skip("courtyard_push_cyl.json not captured (needs a live slot-2 capture)")
    d = json.load(open(_FIX))
    d['frames'] = _dedup(d['frames'])
    return d


def _push_frames(frames):
    """Frames where Link's Co cylinder overlaps Tetra (depth > 0) AND she is being plowed (stt 3,
    speedF 0 -- no self-locomotion), so her move is pure plow. That is the whole state-2 push."""
    out = []
    for i in range(len(frames) - 1):
        f = frames[i]
        if f['tetra']['stt'] != 3 or abs(f['tetra']['speedF']) > 1e-6:
            continue
        if plow_depth(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2])) > 0.1:
            out.append(i)
    return out


def test_tetra_absorbs_full_overlap(cyl):
    """frac = tetra_move / depth == 1.0 on every push frame: Tetra takes the FULL Co overlap depth
    (Link's push share is 0), the opposite of the 50/50 following-Tetra split. This is the core
    live finding; a 50/50 split would read ~0.5 here."""
    frames = cyl['frames']
    push = _push_frames(frames)
    assert len(push) >= 30, "expected the full ~40-frame push, got %d plow frames" % len(push)
    for i in push:
        f, n = frames[i], frames[i + 1]
        depth = plow_depth(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]))
        move = math.hypot(n['tetra']['pos'][0] - f['tetra']['pos'][0],
                          n['tetra']['pos'][2] - f['tetra']['pos'][2])
        frac = move / depth
        assert abs(frac - 1.0) < 0.01, "frame %d: Tetra frac %.4f != 1.0 (depth %.3f move %.3f)" % (
            i, frac, depth, move)


def test_plow_step_matches_live_each_frame(cyl):
    """One plow step from each frame's live Tetra pos + Link centre reproduces the NEXT frame's live
    Tetra pos (isolates the law from any drift accumulation)."""
    frames = cyl['frames']
    for i in _push_frames(frames):
        f, n = frames[i], frames[i + 1]
        tx, tz = plow_step(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]))
        err = math.hypot(tx - n['tetra']['pos'][0], tz - n['tetra']['pos'][2])
        assert err < 0.01, "frame %d: plow_step off by %.4f u" % (i, err)


def test_reconstruct_whole_push(cyl):
    """Reconstruct Tetra's ENTIRE trajectory from ONLY Link's per-frame Co centres + her seed. The
    herd is a deterministic function of Link's centre path -- exactly what the planner predicts."""
    frames = cyl['frames']
    n = len(frames) - 1
    centers = [frames[i]['link']['cyl'] for i in range(n)]
    t0 = (frames[0]['tetra']['pos'][0], frames[0]['tetra']['pos'][2])
    recon = reconstruct(centers, t0)
    maxerr = 0.0
    for i in range(n):
        # only compare while Tetra is still being plowed (stt 3, no self-motion)
        if frames[i]['tetra']['stt'] != 3 or abs(frames[i]['tetra']['speedF']) > 1e-6:
            break
        live = frames[i + 1]['tetra']['pos']
        maxerr = max(maxerr, math.hypot(recon[i][0] - live[0], recon[i][1] - live[2]))
    assert maxerr < 0.02, "trajectory reconstruction drifted %.4f u from live" % maxerr
