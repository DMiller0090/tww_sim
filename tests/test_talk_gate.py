"""The A-press talk-eat gate (``harness/tetrapush/talk_gate.py``) vs its two ground truths.

The predicate must reproduce BOTH banked realities from the walk-end state alone:

* **TALKS** -- s168c live falsification: the refused#1 plan's A became a conversation on console
  (proc 170 DEMO_TALK), the roll never dispatched.
* **ROLLS** -- the banked console 101 (``fixtures/courtyard_clip_s90_console.json``): its A also
  lands within 300 u of Tetra, and dispatches FRONT_ROLL on console.

Both A-frame states are banked below as literals (no engine replay at test time), so this file is
pure-function fast. Mechanics + decomp citations: ``knowledge/mechanics/talk-eat.md``. Provenance:

* ``GT1_TALKS`` = ``_notes/s168_queue/live_falsify/sim_reference.json`` ``sim.dlv_walled`` row 79
  (the ``a_i`` row) of the s168c refused#1 delivery (plan (2,90,178,0,1,173,190,0,2), thrust 15,
  aim (87,191), CONVERTED rung06-w05 herd with rows 72/73 overridden to stickX=128, stickY=255).
  That replay is LIVE-BIT-EXACT (matched console at N=74 and N=80 on x/z/facing/travel/speedF/proc;
  f32 bits xb=3301549064 zb=3294364150 txb=3301963769 tzb=3295350876). Console verdict
  (``live_results.json``): the A became proc 170 DEMO_TALK -- no roll, no clip.
* ``GT2_ROLLS`` = the banked console 101 (``fixtures/courtyard_clip_s90_console.json``, LOCKED,
  a_i=82, entry_i=83), walk-end state minted 2026-08-16 by replaying the fixture's own log[:83] on
  the WALLED engine (``SD.wall_for_terminal(SD.make_freerun(env, native=True))`` +
  ``pre_seed_input(SD.dtm_input_at(env)(0))``, the s168 closed-loop seeding). Identity checks vs
  the fixture: row-82 x/z == ``hit.walk``, row-82 m351C 64345 == ``hit.m351C_walk``, roll
  dispatched at row 83 (proc 30, facing 40841 == ``hit.facing``). The A lands 174.794 u from
  Tetra -- INSIDE the 300 u region -- yet the console rolled: the walk-end facing 17734 sits
  22606 BAM off her bearing (40340), outside the +-0x4000 cone.
"""

import pytest

from harness.tetrapush.talk_gate import talk_eats_a
from tww_sim.core.npc_zl1 import zl1_attention_active


# --------------------------------------------------------------------------- ground truth 1: TALKS
# s168c refused#1 walk-end state, live-bit-exact -- provenance in the module docstring.
GT1_TALKS = dict(
    link_x=-1613.1259765625, link_z=-880.0306396484375,   # Link walk-end pos (f32-exact)
    link_facing=34187,                                     # walk-end shape_angle.y == travel
    tetra_x=-1663.7491455078125, tetra_z=-940.255615234375,  # Tetra (south-wall braced)
)

# --------------------------------------------------------------------------- ground truth 2: ROLLS
# The banked console 101's walk-end state off its own walled replay -- provenance in the docstring.
GT2_ROLLS = dict(
    link_x=-1513.0206298828125, link_z=-763.112548828125,
    link_facing=17734,
    tetra_x=-1629.101806640625, tetra_z=-893.7962036132812,
)


def test_gt1_the_s168c_live_talk_is_predicted_as_a_talk():
    assert talk_eats_a(**GT1_TALKS) is True


def test_gt2_the_banked_console_101_is_predicted_as_a_roll():
    assert talk_eats_a(**GT2_ROLLS) is False


def test_gt2_would_have_talked_at_the_rolls_own_aim_facing():
    """The frame-order proof: the console 101's ROLL facing (40841, `hit.facing`) is only 501 BAM
    off Tetra's bearing -- inside the cone. Had the game judged the dispatch-frame aim facing, the
    console 101 would have talked; it rolled. So the walk-end facing is the input, and a gate fed
    the aim facing would call the banked reality wrong."""
    assert talk_eats_a(**dict(GT2_ROLLS, link_facing=40841)) is True


def test_cantalk_off_zero_weights_her_out_of_the_list():
    """check_event_condition (d_attention.cpp:229-250): without dEvtCnd_CANTALK_e the weight is
    0 and she never enters the ACTION list, whatever the geometry says."""
    assert talk_eats_a(**GT1_TALKS, cantalk=False) is False


# -------- synthetic boundaries: pinned to dist_table[0xAB] via check_distace/check_flontofplayer
# (citations: talk-eat.md); Tetra dead ahead on +z from the origin, all values f32-exact.

def test_front_cone_boundary_is_inclusive_at_0x4000():
    # angle1 = bearing(0) - facing; reject only when STRICTLY beyond 0x4000 (90 deg).
    assert talk_eats_a(0.0, 0.0, 0x4000, 0.0, 100.0) is True       # exactly 90 deg: listed
    assert talk_eats_a(0.0, 0.0, 0x4001, 0.0, 100.0) is False      # one BAM beyond: rejected
    assert talk_eats_a(0.0, 0.0, -0x4000 & 0xFFFF, 0.0, 100.0) is True   # mirror side
    assert talk_eats_a(0.0, 0.0, (-0x4001) & 0xFFFF, 0.0, 100.0) is False


def test_xz_region_boundary_is_inclusive_at_300():
    # check_distace rejects iff adjust < absXZ with adjust == 300 (mDistXZAngleAdjust == 0).
    assert talk_eats_a(0.0, 0.0, 0, 0.0, 300.0) is True            # exactly 300: listed
    assert talk_eats_a(0.0, 0.0, 0, 0.0, 300.0625) is False        # first easy f32 step out


def test_y_gate_bounds_are_exclusive():
    # dy = (tetra_y+140) - link_attn_y, listed strictly inside (-300, 300); the sums are f32-exact.
    assert talk_eats_a(0.0, 0.0, 0, 0.0, 100.0, tetra_y=160.0) is False       # dy == +300: out
    assert talk_eats_a(0.0, 0.0, 0, 0.0, 100.0, tetra_y=159.96875) is True    # just under
    assert talk_eats_a(0.0, 0.0, 0, 0.0, 100.0, tetra_y=-440.0) is False      # dy == -300: out
    assert talk_eats_a(0.0, 0.0, 0, 0.0, 100.0, tetra_y=-439.96875) is True   # just above


def test_cone_uses_the_attention_systems_own_yaw_not_the_raw_table():
    """SelectAttention's bearing is cSGlobe.U() -- the table atan2s ROUND-TRIPPED through f32
    radians (cM_atan2f 9.58738E-5f, c_math.cpp:162-165) and back (Radian_to_SAngle 10430.378f
    s16-trunc, c_angle.h:68) -- which shifts this bearing by +1 BAM vs the raw table: for delta
    (-200, 111) the table gives -11102, the game -11101 (`attn_yaw_bam`). At facing 5283 the
    game's face error is exactly -0x4000 (listed -> talk); a raw-table model computes -0x4001
    and would call it a roll -- a 1-BAM fiction of exactly the s168 class."""
    from tww_sim.core.npc_zl1 import attn_yaw_bam, _s16
    from tww_sim.core import mathlib as S
    from tww_sim.core.fp import f32
    assert _s16(S.cM_atan2s(f32(-200.0), f32(111.0))) == -11102   # the raw table
    assert attn_yaw_bam(-200.0, 111.0) == -11101                  # the game's round trip
    assert talk_eats_a(0.0, 0.0, 5283, -200.0, 111.0) is True     # err == -0x4000: listed
    assert talk_eats_a(0.0, 0.0, 5284, -200.0, 111.0) is False    # err == -0x4001: rejected


def test_dead_behind_edge_is_resolved_conservatively_as_a_talk():
    """Face error exactly -0x8000: check_flontofplayer's s16 negation of -32768 overflows and the
    C source does not decide whether the compiled game re-narrows. talk_gate refuses (True) so the
    ambiguity can never admit a console-talker -- but only inside the distance/Y region."""
    assert talk_eats_a(0.0, 0.0, 0x8000, 0.0, 100.0) is True       # in region: conservative talk
    assert talk_eats_a(0.0, 0.0, 0x8000, 0.0, 301.0) is False      # out of region: still a roll
    # The core keep-out model itself says inactive there (its documented abs() reading); the
    # divergence is exactly this one edge and is deliberate.
    assert zl1_attention_active((0.0, 0.0, 0.0), 0x8000, (0.0, 0.0, 100.0)) is False


def test_gate_agrees_with_the_core_region_model_off_the_edge():
    """Everywhere except the documented -0x8000 edge, talk_eats_a(cantalk=True) IS the core
    zl1_attention_active region -- same code path, no restated geometry to drift."""
    from tww_sim.core.npc_zl1 import _s16, attn_yaw_bam
    checked = 0
    for tx, tz in [(0.0, 100.0), (200.0, 200.0), (-250.0, 100.0), (0.0, 299.0), (0.0, 301.0)]:
        bearing = attn_yaw_bam(tx, tz)
        for facing in range(0, 0x10000, 0x777):
            if _s16(bearing - _s16(facing)) == -0x8000:
                continue
            assert talk_eats_a(0.0, 0.0, facing, tx, tz) is \
                zl1_attention_active((0.0, 0.0, 0.0), facing, (tx, 0.0, tz))
            checked += 1
    assert checked > 100
