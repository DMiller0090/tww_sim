"""Link's own push slowdown (the from-f0 blocker), live-gated against the RAM ground truth.

`harness/tetrapush/link_plow` encodes the measured Link recoil -- on every push frame Link ejects the
FULL Co-cylinder overlap depth AWAY from Tetra (the mirror of `tetra_plow`, which ejects Tetra the
full depth away from Link). This gate feeds the law the RAM-captured Link Co centres + Tetra positions
(fixtures/courtyard_push_cyl.json, single-stepped from slot 2) and asserts, on the pure-foot-term push
frames (FRONT_ROLL + the hot MOVE backslide, where the foot term is exactly `speedF` along
`current.angle.y` -- session-7 fact):

  * Link's actual recoil (feet delta minus the foot term) has magnitude == the overlap depth
    (`recoil / depth == 1.0`); a 50/50 split would read ~0.5 here.
  * `link_plow.recoil()` reproduces that recoil VECTOR (magnitude + direction) to <0.02 u.
  * feet + foot term + `link_plow.recoil()` reconstructs the NEXT frame's live feet to <0.02 u.

Together with `test_tetra_plow`, this locks BOTH sides of the coupled Courtyard herd. The foot term
uses the POST-update `speedF` (frame i+1's logged value) along frame i's `current.angle.y` -- the
off-by-one the live reconstruction pinned. Frames where the speed/facing FLIP mid-frame (the proc-7
roll-setup re-target and the proc-9 untarget-flip entry) are excluded: there the simple `speedF*dir`
foot term does not apply (the sim's real foot/attention engine handles them). See
harness/tetrapush/README.md "The CC split (Courtyard push)".
"""
import json
import math
import os

import pytest

from harness.tetrapush.link_plow import recoil, recoil_step
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


def _roll_frames(frames):
    """The FRONT_ROLL push frames -- the jitter-free subset for a TIGHT per-frame vector check. The
    single-stepped capture holds the roll's per-frame displacement cleanly (the anim ctrl advances a
    dead-constant +1.1/frame), whereas the MOVE-backslide frames carry ~0.05 u single-step jitter (so
    those are gated on the depth MAGNITUDE via `test_link_recoils_full_overlap`, not the tight
    reconstruction)."""
    return [i for i in _push_frames(frames) if frames[i]['proc'] == _ROLL]


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
    """recoil / depth == 1.0 on every push frame: Link ejects the FULL Co overlap depth away from
    Tetra (NOT the 50/50 split a rank-5/rank-5 SetPosCorrect would give). The core session-9 finding
    -- BOTH actors resolve the full penetration."""
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


def test_recoil_matches_live_each_frame(cyl):
    """link_plow.recoil() reproduces the live recoil VECTOR (magnitude + direction) each FRONT_ROLL
    frame -- the jitter-free subset."""
    frames = cyl['frames']
    rolls = _roll_frames(frames)
    assert len(rolls) >= 25, "expected both roll cycles, got %d roll frames" % len(rolls)
    for i in rolls:
        f, n = frames[i], frames[i + 1]
        rx, rz = recoil(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]))
        ax, az = _actual_recoil(f, n)
        err = math.hypot(float(rx) - ax, float(rz) - az)
        assert err < 0.015, "frame %d: recoil vector off by %.4f u" % (i, err)


def test_link_feet_reconstruct_each_frame(cyl):
    """feet + foot term + recoil() reproduces the NEXT frame's live feet on each FRONT_ROLL frame
    (isolates the law from drift accumulation) -- the mirror of test_tetra_plow's per-frame plow_step
    check."""
    frames = cyl['frames']
    for i in _roll_frames(frames):
        f, n = frames[i], frames[i + 1]
        fx, fz = _foot_term(f, n)
        px, pz = recoil_step(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]),
                             (f['link']['pos'][0] + fx, f['link']['pos'][2] + fz))
        err = math.hypot(float(px) - n['link']['pos'][0], float(pz) - n['link']['pos'][2])
        assert err < 0.015, "frame %d: Link feet reconstruction off by %.4f u" % (i, err)
