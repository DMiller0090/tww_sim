"""Gates for the realizable camera-steered reposition primitives (session 39).

STRUCTURAL / behavioural gates on the already-0-ULP `from_f0.FreeRun` (fidelity is `test_from_f0`'s,
like `test_reposition`) -- they pin the VALIDATED facts the frame-minimal search is built from so a
future change that breaks them is caught:

  * the camera yaw is a bounded, C-stick-commanded channel (neutral FREEZES csangle; full stick
    drives it a few hundred BAM/frame) -- so csangle is steerable, not free;
  * the camera controls FACING, not lateral POSITION (armed-state lat/lead invariant across the
    reachable `target_cs`);
  * the on-line plow-roll self-stabilises (the recorded 2-roll human window stays behind Tetra).
"""
import warnings

import pytest

from harness.tetrapush import seeds
from harness.tetrapush import steered_reposition as R
from harness.tetrapush.reposition import HerdLine


@pytest.fixture(scope="module")
def env():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return seeds.load_env()


def test_camera_neutral_freezes_full_stick_steers(env):
    """Neutral substickX (128) holds csangle DEAD frozen (manualCamera hold); full stick drives it
    a bounded few-hundred BAM/frame in each direction. This is why csangle must be STEERED (during
    the free locked-roll frames), not injected."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        auth = R.camera_authority(env, frames=10)
    # neutral: every per-frame drift is exactly 0
    assert all(d == 0 for d in auth[128]), "neutral substickX did not freeze csangle: %s" % auth[128]
    # full-left / full-right: steady-state drift is nonzero, bounded, and opposite-signed
    left_ss = auth[0][-1]
    right_ss = auth[255][-1]
    assert left_ss < -100 and right_ss > 100, "full stick barely steered (%d / %d)" % (left_ss, right_ss)
    assert abs(left_ss) < 1200 and abs(right_ss) < 1200, "steering rate implausibly large"
    # ~16-frame roll gives several thousand BAM of authority (enough to reach an in-window target)
    assert abs(sum(auth[0])) > 3000, "camera authority over the window too small to steer a turnaround"


def test_camera_sets_facing_not_position(env):
    """Across the whole reachable `target_cs`, the armed-state lateral offset + lead are INVARIANT
    (the camera moves csangle_exit, not Link's position). Position is the main-stick's job."""
    hl = HerdLine.from_env(env)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        geos = []
        cs_exits = set()
        for tcs in (None, 26000, 36000, 46000):
            run = R._steered_cyc1(env, tcs)
            g = R.armed_geometry(run, hl)
            geos.append(g)
            cs_exits.add(round(run.csangle))
    # csangle_exit genuinely varies with the steer target ...
    assert len(cs_exits) >= 2, "steering did not move csangle_exit at all: %s" % cs_exits
    # ... but lateral + lead do not (camera != position)
    lats = [g['lateral'] for g in geos]
    leads = [g['lead'] for g in geos]
    assert max(lats) - min(lats) < 1.0, "lateral moved with the camera target (%s)" % lats
    assert max(leads) - min(leads) < 1.0, "lead moved with the camera target (%s)" % leads


def test_online_plow_roll_self_stabilises(env):
    """Dereck's self-stabilization: the ground-truth 2-roll human window stays on-line (Link behind
    Tetra every frame) -- so an on-line cycle self-sustains and the off-line landing is a one-time
    bootstrap artifact."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _hl, m = R.recorded_online_metrics(env)
    assert m['on_line'], "recorded window is not on-line -- self-stabilization premise broken"
    assert m['worst_lead'] < 0, "Link overtook Tetra in the recorded window (worst_lead %.1f)" % m['worst_lead']
    assert m['per_frame'] > 10.0, "recorded human herd rate implausibly low (%.2f u/f)" % m['per_frame']
