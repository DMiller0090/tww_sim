"""Link's own push slowdown (the from-f0 blocker), live-gated against the RAM ground truth.

`harness/tetrapush/link_plow` encodes the measured Link recoil -- on every push frame Link ejects the
FULL Co-cylinder overlap depth AWAY from Tetra (the mirror of `tetra_plow`, which ejects Tetra the
full depth away from Link).

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`): this file keeps ONLY the REGIME discriminator
(`recoil / depth == 1.0`, not 0.5 -- Link ejects the FULL depth, not a 50/50 split). It is category
(a) NON-fidelity: a qualitative full-vs-half check where the loose bound is correct and intended, and
it is explicitly NOT a 0-ULP gate. The recoil LAW's 0-ULP FIDELITY lives in test_from_f0.py, against
DETERMINISTIC / self-consistency targets, not the lossy reconstruction this file used to use:
  * `test_full_depth_push_recoil_is_exact_opposite_of_tetra` -- the Newton's-third-law self-consistency
    invariant (recoil == -push bit-for-bit), a pure code check needing no live capture;
  * `test_onestep_pos_bit_exact_from_exact_state` -- Link's coupled one-step position (recoil applied
    on top of the foot term) 0-ULP vs the deterministic capture.
The old per-frame vector/feet gates (recoil vs `feet_delta - speedF*sin/cos(travel)`) were DELETED: the
comparison target was a Python `math.sin/cos` reconstruction, not a console read, so they could never
be a legit 0-ULP gate. See harness/tetrapush/README.md "The CC split (Courtyard push)".
"""
import json
import math
import os

import pytest

from harness.tetrapush.tetra_plow import plow_depth

_FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'fixtures', 'courtyard_push_cyl.json')

_ROLL = 30
_MOVE = 6


def _dedup(frames):
    """Drop single-step DOUBLE-READ frames (the capture re-sampling one game frame -- e.g. cyc2
    f44==f45, [[run-dtm-1frame-jitter]]): bit-identical to its predecessor in BOTH Link's Co centre
    and Tetra's pos == the same game frame read twice, not a real 0-displacement frame."""
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


def _ang(a):
    return (a & 0xFFFF) / 65536.0 * 2.0 * math.pi


def _push_frames(frames):
    """Frames where Link's Co cylinder plows Tetra (depth > 0.1, she is stt-3 / speedF 0) AND Link's
    foot term is the clean pure-``speedF`` case: a FRONT_ROLL, or a hot MOVE backslide (|speedF| > 15,
    excluding the proc-7 re-target frames where speed/facing flip)."""
    out = []
    for i in range(len(frames) - 1):
        f = frames[i]
        if f['tetra']['stt'] != 3 or abs(f['tetra']['speedF']) > 1e-6:
            continue
        if plow_depth(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2])) <= 0.1:
            continue
        proc = f['proc']
        if proc == _ROLL or (proc == _MOVE and f['link']['speedF'] < -15.0):
            out.append(i)
    return out


def _foot_term(f, nxt):
    """Link's foot move for the step f -> nxt: the POST-update speedF (nxt's logged value) along
    frame f's current.angle.y (travel)."""
    a = _ang(f['link']['travel'])
    spF = nxt['link']['speedF']
    return spF * math.sin(a), spF * math.cos(a)


def _actual_recoil(f, nxt):
    """Live recoil vector = (feet delta) - (foot term)."""
    fx, fz = _foot_term(f, nxt)
    return (nxt['link']['pos'][0] - f['link']['pos'][0] - fx,
            nxt['link']['pos'][2] - f['link']['pos'][2] - fz)


def test_link_recoils_full_overlap(cyl):
    """REGIME DISCRIMINATOR (not a fidelity gate, `[[zero-ulp-tests-only]]` category (a)):
    recoil / depth == 1.0 on every push frame, i.e. Link ejects the FULL Co overlap depth away from
    Tetra (NOT the 50/50 split a rank-5/rank-5 SetPosCorrect would give) -- the core session-9 finding
    that BOTH actors resolve the full penetration. This is QUALITATIVE (full vs half); the loose bound
    distinguishing 1.0 from 0.5 is correct and intended, and the recoil measured here uses a lossy
    foot-term reconstruction (`math.sin/cos`), so it is explicitly NOT a 0-ULP gate. The recoil LAW's
    0-ULP fidelity is in test_from_f0.py (self-consistency + the one-step Link position gate)."""
    frames = cyl['frames']
    push = _push_frames(frames)
    assert len(push) >= 25, "expected the full push, got %d clean plow frames" % len(push)
    for i in push:
        f, n = frames[i], frames[i + 1]
        depth = plow_depth(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]))
        rx, rz = _actual_recoil(f, n)
        frac = math.hypot(rx, rz) / depth
        assert abs(frac - 1.0) < 0.01, "frame %d: Link recoil frac %.4f != 1.0 (depth %.3f)" % (
            i, frac, depth)
