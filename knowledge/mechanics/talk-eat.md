# The A-press talk-eat - when the roll's A becomes a conversation with Tetra

**Answers:** Why did a confirm-ALL-GREEN plan's A press start a conversation on console (proc 170
DEMO_TALK) instead of dispatching the FRONT_ROLL? Which state decides talk-vs-roll - the walk-end
state or the dispatch frame's aim facing? Is the action-button (A) region a different
`dist_table` row/cone than Tetra's lock-on region? What exact bearing does the attention system
compare against the +-90 deg cone?
**Status:** decomp-derived predicate (`harness/tetrapush/talk_gate.py::talk_eats_a`), validated
against BOTH ground truths offline (session 169): the s168c live talk (refused#1, A at 78.675 u /
walk-end facing inside the cone -> console proc 170) and the banked console 101 (A at 174.794 u -
INSIDE the 300 u region - yet rolls, because the walk-end facing is 22606 BAM outside the cone).
Gated `tests/test_talk_gate.py` (boundary cases pinned to the decomp geometry). NOT yet wired into
the acceptance stack (`confirm_entry`/`accept` still do not call it).
**Source:** decomp `setTalkStatus`/`setAtnList`/`setDoStatus`/`orderTalk`/
`checkNextActionFromButton` (`d_a_player_main.cpp:2039-2163, 4029-4323, 11322`),
`dAttention_c::Run`/`getActionBtnB`/`calcWeight`/`check_flontofplayer`/`check_distace`
(`d_attention.cpp`), `dist_table[0xAB]` (`d_att_dist.cpp:181`), `daNpc_Zl1_c::eventOrder`
(`d_a_npc_zl1.cpp:1053`), `cSGlobe`/`cM_atan2f` (`c_angle.cpp`, `c_math.cpp:162`). Live evidence:
`_notes/s168_queue/live_falsify/` (sim_reference.json, live_results.json).

---

The player's A dispatch is a PRIORITY CHAIN, and talking outranks rolling. In
`checkNextActionFromButton` (the walk proc's per-frame button dispatch) `setDoStatus` runs first:
if the attention system handed the player an A-action entry of type SPEAK (`mpAttnEntryA`, from
`getActionBtnB()` when there is no lock-on), `setTalkStatus` sets doStatus SPEAK and `orderTalk`
consumes the A (`fopAcM_orderTalkEvent` -> DEMO_TALK, proc 170). Only when no talk entry exists
does the A fall through to doStatus ATTACK -> `procFrontRoll_init`. So "does the A roll?" reduces
to "is Tetra in the attention ACTION list this frame?".

**The ACTION region is the SAME region as her lock-on region.** Tetra's `createInit` sets
`distances[TALK] = distances[SPEAK] = 0xAB`, so both lists read `dist_table[0xAB]`: XZ <= 300 u
(inclusive - reject is strictly `300 < dist`), |dy| < 300 between attention points (exclusive
bounds), and Link's facing within +-0x4000 of her bearing (inclusive - reject is strictly
`> 0x4000`). Plus one non-geometric gate: her `eventInfo` must assert `dEvtCnd_CANTALK_e` that
frame (`eventOrder`, while her `field_0x84A` is 1 or 2) or `calcWeight` zero-weights her. The
geometry is `zl1_attention_active` ([tetra-follow.md](tetra-follow.md)); the decision chain +
CANTALK gate is `talk_eats_a`.

**The input is the WALK-END state, not the dispatch frame's aim facing.** The two ground truths
prove it by themselves: the console 101's roll facing (40841) sits 501 BAM off Tetra's bearing -
INSIDE the cone - so a gate fed the aim facing would have called the banked reality a talk. Its
walk-end facing (17734) is 22606 BAM off - outside - and it rolled. Mechanically: the attention
lists are rebuilt each frame by the scene proc (`dScnPly_Execute` -> `Run(-1)`, no hysteresis
without a lock-on) from positions/facings the player's proc has not yet moved, and the roll's
stick snap (`shape_angle.y = m34E8`) happens on the roll path AFTER `orderTalk` already had the
A. So feed the predicate the sim row at `a_i` (the last pre-dispatch row).

**The cone's bearing is NOT the raw table atan2s.** `SelectAttention` computes it through
`cSGlobe.U()`: `Radian_to_SAngle(cM_atan2f(dx, dz))`, i.e. the table value round-tripped through
f32 radians (`* 9.58738E-5f`, then `* 10430.378f`, s16 truncation toward zero). That shifts ~18%
of bearings by +-1 BAM - enough to flip a verdict exactly on the cone boundary.
`core/npc_zl1.attn_yaw_bam` is the exact chain and `zl1_attention_active` uses it.

One decomp ambiguity, resolved conservatively: at a face error of exactly 0x8000 (dead behind),
`check_flontofplayer`'s s16 negation of -32768 overflows and the C source does not decide whether
the compiled game re-narrows; `talk_eats_a` treats it as a talk (refuses the plan) so the
ambiguity can never admit a console-talker.

For the acceptance stack this is TWO checks (proposed, unwired): a score-time pre-filter per
(candidate, aim) - the candidate key already carries walk-end `(x, z)` and Tetra `(tx, tz)`, the
walk facing is the herd/walk plan's - and an accept-time authoritative check on `confirm_entry`'s
replayed walk-end row. A plan that talks is not a refused plan, it is a WRONG plan: s168c showed
`confirm_entry` all-green on one.
