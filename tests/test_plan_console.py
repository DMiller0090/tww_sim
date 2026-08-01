"""THE TIER-2 CONFIRM OF THE SHIPPED PLAN: the console plays it, 0-ULP on both actors (session 78).

`tests/test_objective.py::test_the_shipped_plan_passes_the_whole_objective_from_its_input_log_alone`
gates milestone 2 in the SIM. This gates it on the CONSOLE: the same plan, spliced onto the recorded
boot movie and played on the real game, with Link and Tetra read at a truncate-and-read halt for each
sample N (`harness/tetrapush/deliver.py`, ~8 s per sample). Every one of the 22 samples -- the first
frames after state 2, all three herd cycles, the arrival, and every frame of the escape atom -- is
bit-exact on both actors' positions, and on `proc`, `facing`, `travel` and `speedF` besides.

The headline the fixture carries: at the plan's SCORED frame the console's own Tetra sits
**0.4321 u from genuine coord 274**, the number the objective claims, computed from the console read
rather than from the sim. Milestone 2 is a console measurement now, not a simulation result.

`fixtures/courtyard_plan_s73_console.json` is LOCKED, like every clean-DTM console capture: for a
fixed input log the console is ground truth and never moves, so a disagreement is the sim's to fix
(`tests/dolphin/README.md#locked-tests-are-immutable-hard-rule`). Nothing here is xfailed -- unlike
node 1's curve, this plan has no open frontier: it stays inside the stt-3 plow regime and clear of the
walls by construction, which is exactly what `objective`'s rules 4 and the regime prune buy.

One model correction is gated here too. The escape atom is scored on a camera-DETACHED clone
(`away_walk._clone_for_atom`) commanding the arrival's LIVE csangle, on the premise that a neutral
C-stick freezes it there. A neutral C-stick does freeze it -- but not at that value: the plan's last
roll slews the C-stick to 255 and the view-cache cushion still owes 144 BAM of chase when it goes
neutral, so the atom's FIRST frame collects the remainder (34181 -> 34330 -> 34325, frozen after).
The console read at the scored frame is the WIRED facing (2099), not the detached one (2070). It
costs the objective nothing -- Tetra, every push frame and every acceptance term are bit-identical
either way, gated below -- but the arrival's live csangle is not the camera the escape runs at.

Offline: replays the locked log on the 0-ULP `FreeRun` (no Dolphin).
"""
import json
import math
import os
import struct
import warnings

import pytest

from harness.tetrapush import objective as O
from harness.tetrapush import seeds


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_plan_s73_console.json')))
PLAN = json.load(open(_fx('courtyard_plan_s73.json')))
SAMPLES = {s['n']: s for s in FIX['samples']}
SCORED = FIX['plan']['scored_frames']
HERD = FIX['plan']['herd_frames']


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulp(a, b):
    return abs(_bits(a) - _bits(b))


@pytest.fixture(scope="module")
def env():
    return seeds.load_env()


@pytest.fixture(scope="module")
def rollout(env):
    """Replay the locked delivered log once and snapshot every sampled frame.

    One rollout serves all samples: the sim is deterministic and a truncated delivery keeps frames
    0..n-1 byte-identical (`test_tetrapush_deliver.py::test_truncating_the_plan_leaves_alignment_
    untouched`), so the state after `step(log[n-1])` is what the n-frame movie halts on. The camera
    is WIRED (`seeds.make_freerun`) because that is the configuration the console runs."""
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    snaps = {}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, d in enumerate(FIX['log'][:max(SAMPLES)]):
            run.step(d)
            if (i + 1) in SAMPLES:
                L = run.link
                snaps[i + 1] = dict(x=float(L.pos_x), z=float(L.pos_z), facing=int(L.facing) & 0xFFFF,
                                    travel=int(L.travel) & 0xFFFF, proc=int(L.state),
                                    speedF=float(L.speedF), tx=float(run.tx), tz=float(run.tz))
    return snaps


@pytest.mark.parametrize("n", sorted(SAMPLES))
def test_the_sim_predicts_the_console_bit_exact_on_both_actors(n, rollout):
    """0-ULP on both positions at every console-measured frame -- no tolerance
    (`[[zero-ulp-tests-only]]`; the rows are deterministic PauseMovie halts, not single-steps)."""
    s, sim = SAMPLES[n], rollout[n]
    assert _bits(sim['x']) == _bits(s['link']['x']), "Link x off %d ULP" % _ulp(sim['x'], s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z']), "Link z off %d ULP" % _ulp(sim['z'], s['link']['z'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x']), "Tetra x off %d ULP" % _ulp(sim['tx'], s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z']), "Tetra z off %d ULP" % _ulp(sim['tz'], s['tetra']['z'])


@pytest.mark.parametrize("n", sorted(SAMPLES))
def test_the_whole_state_matches_not_just_the_positions(n, rollout):
    """The dispatched proc, the attention-driven facing, the EBS travel angle and speedF agree too,
    and Tetra never leaves the stt-3 plow regime the model is defined on -- so the agreement is the
    state, not two coordinates that happen to coincide."""
    s, sim = SAMPLES[n], rollout[n]
    assert sim['proc'] == s['link']['proc']
    assert sim['facing'] == s['link']['facing']
    assert sim['travel'] == s['link']['travel']
    assert _bits(sim['speedF']) == _bits(s['link']['speedF'])
    assert s['tetra']['stt'] == 3, "console row left the stt-3 plow regime (a SCOPE break, not a bug)"


def test_the_console_lands_tetra_on_the_genuine_coord_the_plan_claims():
    """**MILESTONE 2, MEASURED ON CONSOLE.** At the plan's scored frame the console's own Tetra is
    `placement_dist` from the genuine coord the objective names -- computed from the console read,
    not from the sim, so the claim no longer rests on the forward model being right.

    The coord is one of the 288 dense samples of the clippable thread, and the distance is inside
    `PLACEMENT_BAND` (the sampling's own 0.166 u spacing, not a fudge)."""
    s = SAMPLES[SCORED]
    rows = seeds.load_placements()[0]
    near = min(rows, key=lambda p: math.hypot(p['x'] - s['tetra']['x'], p['z'] - s['tetra']['z']))
    pd = math.hypot(near['x'] - s['tetra']['x'], near['z'] - s['tetra']['z'])
    assert near['idx'] == FIX['plan']['placement_idx']
    assert pd == pytest.approx(FIX['plan']['placement_dist'], abs=1e-9)
    assert pd <= O.PLACEMENT_BAND


def test_the_delivered_log_is_the_shipped_plan_plus_its_own_escape_atom():
    """The delivered sequence traces to the shipped plan: its first `herd_frames` frames ARE that
    fixture's log, and the rest are the escape atom's own inputs -- which `objective.score_plan`
    probes on a clone, so they are not in the plan file. The scored end is herd + `freeze_f`; the
    atom's remaining frames are Link's escape, delivered so the console measures those too."""
    assert FIX['log'][:HERD] == PLAN['log']
    assert HERD == len(PLAN['log'])
    assert SCORED == HERD + FIX['plan']['freeze_f']
    assert len(FIX['log']) > SCORED, "the atom's post-freeze frames are part of the delivery"
    assert SCORED in SAMPLES and HERD in SAMPLES and len(FIX['log']) in SAMPLES


def test_the_calibration_the_dtm_applies_does_not_move_this_plan(env):
    """What licenses scoring the plan on its RAW bytes: an authored DTM delivers 255 as 254 and 0 as
    1 (`[[octagon-clamp-decode-bug]]`), and this log carries substickY 0 on every frame plus
    substickX 0/255 on 43 of them -- so every delivered frame differs from the scored one. The
    C-stick deltas land inside the camera's own deadzone, and the trajectory is bit-identical.

    This is a MEASUREMENT, not an assumption: a plan whose main stick reached the extremes would
    move, and this test is where that would surface."""
    from harness.tetrapush import deliver as DV
    raw = FIX['log']
    cal = [dict(d, stickX=DV._cal(d.get('stickX', 128)), stickY=DV._cal(d.get('stickY', 128)),
                substickX=DV._cal(d.get('substickX', 128)), substickY=DV._cal(d.get('substickY', 0)))
           for d in raw]
    assert sum(1 for a, b in zip(raw, cal) if a != b) == len(raw), "no channel is calibrated at all?"

    def replay(log):
        run = seeds.make_freerun(env)
        run.pre_seed_input(seeds.dtm_input_at(env)(0))
        out = []
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            for d in log:
                r = run.step(d)
                out.append((r['sim_link'], r['sim_tetra'], r['sim_facing'], r['speedF']))
        return out

    assert replay(raw) == replay(cal)


def test_the_console_confirms_the_wired_camera_over_the_detached_atom_clone(env):
    """The atom's camera detachment is a CONVENIENCE, and the console says which run is real.

    `away_walk._clone_for_atom` drops the wired camera so the arrival's LIVE csangle sticks, on the
    premise that the atom's neutral C-stick freezes it there. The freeze is real; the VALUE is not.
    The plan's last roll holds the C-stick at 255, so when it returns to neutral the view-cache is
    still chasing a target 144 BAM away, and the atom's first frame collects the rest of that chase
    (34181 -> 34330 -> 34325, constant from then on). Link's path parts company from the third frame
    -- the input delay -- by 0.12 -> 0.65 u, and the console read at the scored frame matches the
    WIRED facing, not the detached one.

    And it costs the objective nothing, which is why the detached convention is kept rather than
    ripped out: TETRA is bit-identical on every atom frame either way, so the placement, the freeze
    and every push frame are unaffected. What moves is Link's own escape path, and that belongs to
    the separate entry search (Dereck, s60)."""
    from harness.tetrapush import away_walk as AW
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in FIX['log'][:HERD]:
            run.step(d)
        atom_log = FIX['log'][HERD:]
        wired, detached = run.clone(), AW._clone_for_atom(run)
        rows_w = [wired.step(d) for d in atom_log]
        rows_d = [detached.step(d) for d in atom_log]

    # Tetra -- everything the objective reads -- is bit-identical on every atom frame
    for i, (a, b) in enumerate(zip(rows_w, rows_d)):
        assert _bits(a['sim_tetra'][0]) == _bits(b['sim_tetra'][0]), "Tetra x moved at atom frame %d" % i
        assert _bits(a['sim_tetra'][1]) == _bits(b['sim_tetra'][1]), "Tetra z moved at atom frame %d" % i
    # Link does not, and the console picks the wired one
    scored_atom = SCORED - HERD - 1
    assert rows_w[scored_atom]['sim_facing'] != rows_d[scored_atom]['sim_facing'], \
        "the two configurations no longer differ -- re-derive before trusting this gate"
    assert rows_w[scored_atom]['sim_facing'] == SAMPLES[SCORED]['link']['facing']
    assert rows_d[scored_atom]['sim_facing'] != SAMPLES[SCORED]['link']['facing']
    assert int(wired.csangle) != int(detached.csangle)
