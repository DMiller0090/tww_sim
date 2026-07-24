"""The FRAME-MINIMAL reposition primitives (`harness/tetrapush/reposition`) -- the session-33
levers Dereck steered: the past-Tetra prune, the -25.7-retaining L-release, and the 1-frame
csangle turnaround. These gate the PRIMITIVES the reposition optimizer is built from; the forward
model's fidelity is `test_from_f0`'s (every rollout here is a real 0-ULP `FreeRun`).

Structural / discriminator gates (not sim-vs-console fidelity -- that is FreeRun's): each compares
two input variants stepped through the SAME bit-exact sim, or asserts a geometric invariant.
Needs the locked courtyard fixtures (`seeds.load_env`); skipped when absent.
"""
import struct

import pytest

from harness.tetrapush import primitives as P
from harness.tetrapush import reposition as R
from harness.tetrapush import search as S
from harness.tetrapush import seeds

pytestmark = pytest.mark.filterwarnings("ignore:FreeRun:UserWarning")

_FRONT_ROLL = 30


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope='module')
def env():
    try:
        return seeds.load_env()
    except FileNotFoundError as e:
        pytest.skip("planner fixtures not present: %s" % e)


@pytest.fixture(scope='module')
def recs(env):
    return P.window_records(env)


def test_herd_line_human_stays_behind_tetra(env, recs):
    """STEER #1 invariant: the recorded human keeps Link BEHIND Tetra on the herd line EVERY frame
    (`HerdLine.lead < 0` -- he never overtakes her). This grounds the past-Tetra prune: a candidate
    whose lead goes positive has crossed to the corner side and its straight roll shoves her
    sideways (herd freezes), so `on_line_ok` rejects it."""
    hl = R.HerdLine.from_env(env)
    rec = S.rollout_recorded(env, upto=45, recs=recs)
    m = R.rollout_metrics(env, rec, hl)
    assert m['worst_lead'] < 0.0, "human overtook Tetra somewhere (worst_lead %.1f)" % m['worst_lead']
    assert m['on_line'], "human left the on-line-behind band"


def test_on_line_ok_predicate(env):
    """STRUCTURAL: `on_line_ok` accepts Link behind Tetra and rejects Link past her (steer #1)."""
    hl = R.HerdLine.from_env(env)
    tx, tz = -1450.0, -287.0
    behind = (tx - hl.dx * 50.0, tz - hl.dz * 50.0)      # 50 u up-herd of Tetra
    past = (tx + hl.dx * 20.0, tz + hl.dz * 20.0)        # 20 u down-herd (overtaken)
    assert R.on_line_ok(behind[0], behind[1], tx, tz, hl)
    assert not R.on_line_ok(past[0], past[1], tx, tz, hl)


def test_l_release_early_retains_minus_257(env, recs):
    """STEER #2/#3 discriminator: releasing the mid-roll lock-L one frame early makes the untarget
    backslide RETAIN -25.727 (a 1-frame proc-9 tier), where the human's 2-frame tier drops it to
    -25.454. Both variants stepped through the same bit-exact sim; assert the retained backslide
    stays <= -25.7 while the human's first backslide frame is already > -25.5."""
    macro, aim1 = S.canonical_cycle(env, recs)
    early = R.l_release_early(env, macro, aim1, n=1)

    def first_backslide_speedF(mac):
        run = seeds.make_freerun(env)
        run.pre_seed_input(S._frame_input(mac[0], aim1, run.csangle))
        seen9 = False
        for j in range(1, S.CYCLE_PERIOD):
            row = run.step(S._frame_input(mac[j], aim1, run.csangle))
            if row['sim_proc'] == 9:
                seen9 = True
            elif seen9 and row['sim_proc'] == 6:
                return row['speedF']
        return None

    human = first_backslide_speedF(macro)
    retained = first_backslide_speedF(early)
    assert human is not None and retained is not None
    assert retained <= -25.7, "release-early did not retain -25.7 (got %.4f)" % retained
    assert human > -25.5, "human backslide unexpectedly retained (got %.4f)" % human
    assert retained < human, "release-early is not hotter than the human backslide"


def test_turnaround_snaps_180_preserving_speed(env):
    """STEER (session 33): the 1-frame csangle turnaround snaps facing ~180 deg onto travel
    (`move.py:115`, `facing = travel`) with the -25.7 speed PRESERVED, staying in MOVE (proc 6, not
    a MOVE_TURN reversal). There is a workable csangle window (not knife-edge)."""
    run0, _ = R.seed_to_untarget(env)
    entry_face = run0.link.facing
    entry_spF = run0.link.speedF
    assert run0.link.state == 6 and entry_spF <= -25.7, \
        "seed_to_untarget did not land on the -25.7 EBS (proc %d spF %.3f)" % (run0.link.state, entry_spF)

    def s16(v):
        v = int(v) & 0xFFFF
        return v - 0x10000 if v >= 0x8000 else v

    hits = []
    for cs in range(0, 65536, 256):
        c = run0.clone()
        turned = R.turnaround(c, cs)
        if (c.link.state == 6 and turned > 0x4000
                and abs(s16(c.link.facing - c.link.travel)) < 300 and c.link.speedF <= -24.5):
            hits.append(cs)
    assert hits, "no csangle produced a 1-frame turnaround snap"
    # a real window, not a single knife-edge value
    assert max(hits) - min(hits) > 2000, "turnaround window implausibly narrow (%d)" % (max(hits) - min(hits))
    # confirm one snap in detail
    c = run0.clone()
    turned = R.turnaround(c, hits[len(hits) // 2])
    assert turned > 0x4000, "facing did not snap ~180 (turned %d BAM)" % turned
    assert abs(s16(c.link.facing - c.link.travel)) < 300, "facing did not land on travel"
    assert c.link.speedF <= -24.5, "turnaround did not preserve the backslide speed (%.3f)" % c.link.speedF
    assert abs(s16(c.link.facing - entry_face)) > 0x4000, "facing barely moved from entry"


def test_frame_min_reroll_flip_gives_talk_safe_26_roll(env):
    """CAPABILITY (session 33): the tight reposition -- turnaround -> proc-7 flip (2 frames) ->
    A-roll -- fires a FULL +26 roll (the flip lifts the pre-roll speedF positive so `_roll_init`
    clamps to 26, not the +5 graze) and is TALK-SAFE (the A-press fires with facing away from Tetra,
    out of her cone). This is the frame-minimal alternative to the human's ~10-frame reposition."""
    hl = R.HerdLine.from_env(env)
    run, _ = R.seed_to_untarget(env)
    # pick a csangle in the snap window
    cs = None
    for c in range(0, 65536, 256):
        cc = run.clone()
        if R.turnaround(cc, c) > 0x4000 and cc.link.state == 6 and cc.link.speedF <= -24.5:
            cs = c
            break
    assert cs is not None
    res = R.frame_min_reroll(run, hl, csangle=cs, nflip=2)
    assert res['turned'] > 0x4000, "turnaround did not fire in the reroll"
    assert res['rolled'] or any(r['proc'] == _FRONT_ROLL for r in res['rows']), \
        "the reroll never entered FRONT_ROLL"
    roll_spF = max((r['speedF'] for r in res['rows'] if r['proc'] == _FRONT_ROLL), default=0.0)
    assert roll_spF >= 25.0, "the flip did not produce a full ~26 roll (got %.2f) -- the +5 graze" % roll_spF
    assert not res['talk_unsafe'], "the reroll A-press talked (facing was not away from Tetra)"
