"""The A-press TALK-EAT gate: does the plan's A start a conversation instead of the roll?

Session 168c proved LIVE that a confirm-ALL-GREEN plan can be a conversation on console: the
delivered A landed 78.675 u from Tetra with Link's walk-end facing 5872 BAM off her bearing, and
the console spent the A on ``daPyProc_DEMO_TALK_e`` (proc 170) -- the FRONT_ROLL never dispatched.
Nothing in the acceptance stack modelled it. This module is that model: a pure, decomp-derived
predicate over the WALK-END state, validated against both ground truths (the s168c talk AND the
banked console-101 roll, which also lands within 300 u yet rolls).

THE DECOMP CHAIN (US GZLE line comments; the logic and literals are version-invariant, see
``[[jp-vs-us-decomp-addresses]]``). All files under ``../tww/src/``:

1. Every frame the scene proc rebuilds the attention lists: ``dScnPly_Execute`` ->
   ``dComIfGp_getAttention().Run(-1)`` (``d/d_s_play.cpp:1056``). With no lock-on
   (``LockState_NONE`` -- these plans never press L, and cap-entry conversion killed the
   untarget) that is ``stockAttention`` -> ``makeList``/``SelectAttention`` per actor
   (``d/d_attention.cpp:519-537, 466-486``): no hysteresis, the ACTION list is rebuilt from
   scratch each frame.
2. Tetra (``Zl1``) enters the ACTION list iff ``calcWeight('A', ...)`` > 0
   (``d_attention.cpp:326-378``):
   - flag mask: ``player.attention_info.flags & ACTION_SPEAK & tetra.flags`` -- the player's
     mask is ``~0`` under normal control (``d/actor/d_a_player_main.cpp:11231``) and Tetra's
     ``createInit`` sets ``LOCKON_TALK | ACTION_SPEAK`` (``d/actor/d_a_npc_zl1.cpp:396``);
   - event gate: ``check_event_condition`` (``d_attention.cpp:229-250``) zero-weights her
     unless her ``eventInfo`` has ``dEvtCnd_CANTALK_e`` set THIS frame -- her ``eventOrder``
     asserts it while ``field_0x84A`` is 1 or 2 (``d_a_npc_zl1.cpp:1053-1058``, called
     per-frame from ``_execute`` at ``:2833``);
   - front cone: ``check_flontofplayer`` (``d_attention.cpp:254-291``) with her row's bits
     ``0x0004`` rejects iff ``|angle1| > 0x4000`` where ``angle1 = bearing(player->tetra
     attention pos) - player.shape_angle.y`` as s16 (``SelectAttention``,
     ``d_attention.cpp:472-474``) -- the bearing being ``cSGlobe.U()``, the table atan2s
     round-tripped through f32 radians (``attn_yaw_bam``: ``cM_atan2f`` c_math.cpp:162-165 x
     ``Radian_to_SAngle`` c_angle.h:68), +-1 BAM off the raw table at ~18% of bearings;
   - region: ``check_distace`` (``d_attention.cpp:310-323``) with ``dist_table[0xAB]``
     (``d/d_att_dist.cpp:181`` -- both her ``distances[TALK]`` and ``distances[SPEAK]`` are
     0xAB, ``d_a_npc_zl1.cpp:403-404``, so the ACTION region == the lock-on region):
     ``dy = tetra_attn.y - link_attn.y`` strictly inside (-300, 300) and XZ distance <= 300
     inclusive (``mDistXZAngleAdjust`` is 0 for row 0xAB, so no angle widening).
3. The player reads the list early in his execute -- ``setAtnList``
   (``d_a_player_main.cpp:11322 -> 2039-2089``): with no lock-on,
   ``mpAttnEntryA = mpAttention->getActionBtnB()`` (``d_attention.cpp:139-161``), the
   weight-sorted first SPEAK entry without ``TALKFLAG_NOTALK`` (Tetra has no NOTALK bit).
4. The walk proc's button dispatch (``checkNextActionFromButton``,
   ``d_a_player_main.cpp:4147-4153``) runs ``setDoStatus`` -> ``setTalkStatus``
   (``:2139-2163``): entry type SPEAK -> doStatus ``SPEAK`` -- then ``orderTalk``
   (``:4029-4037``) fires on ``talkTrigger()`` (= BTN_A, ``d_a_player_main.h:1901``) and
   returns true: THE A IS EATEN, ``fopAcM_orderTalkEvent`` -> DEMO_TALK. The roll dispatch
   (doStatus ``ATTACK`` -> ``procFrontRoll_init``, ``:4309-4323``) sits BELOW ``orderTalk``
   in the same function and is never reached. The roll's stick snap
   (``shape_angle.y = m34E8``, ``:4319-4321``) happens only on the roll path, AFTER the talk
   check -- which is why the WALK-END facing is the cone input, not the roll's aim facing.

WHY THE WALK-END STATE IS THE INPUT (the frame-order proof, from the two ground truths alone):
the console-101 roll dispatches at facing 40841, only 495 BAM off Tetra's bearing (40346) --
INSIDE the cone. Had the game judged the dispatch-frame aim facing, the console 101 would have
talked; it rolled. Its walk-end facing 17734 is 22612 BAM off her bearing -- outside. The s168c
talk's walk-end facing 34187 is 5872 off -- inside. Both verdicts follow from the walk-end
state and neither follows from the aim facing.

SCOPE (the tetrapush terminal regime): Link mid-walk on the ground (proc 6), no lock-on, no
grab/bow/boomerang/rope anime, normal control (attention flags ~0), Tetra the only
action-listable actor considered. Other action-type actors (the courtyard DOORs are TYPE_DOOR)
have their own rows/regions and would eat the A as ``dActStts_OPEN_e`` instead -- out of scope
here, a separate keep-out if a plan ever walks the door region.

The region geometry is ``tww_sim.core.npc_zl1.zl1_attention_active`` (reused, not restated).
One decomp ambiguity, resolved CONSERVATIVELY: at a face error of exactly 0x8000 (dead behind),
``check_flontofplayer``'s s16 negation of -32768 overflows; whether the compiled game re-narrows
(``extsh`` -> passes the reject, Tetra stays listed -> talk) or not (rejects -> roll) is not
decidable from the C source. ``talk_eats_a`` returns True there (refuse the plan) so the
ambiguity can never admit a plan that talks on console.
"""

from tww_sim.core.fp import fsubs, f32 as _f
from tww_sim.core.npc_zl1 import zl1_attention_active, attn_yaw_bam, _s16


def talk_eats_a(link_x, link_z, link_facing, tetra_x, tetra_z, *,
                link_y=0.0, tetra_y=0.0, cantalk=True):
    """True = the A press at this WALK-END state is consumed by the attention talk
    (``orderTalk`` -> DEMO_TALK, console proc 170); the FRONT_ROLL never dispatches.
    False = the A falls through ``orderTalk`` to the doStatus-ATTACK roll dispatch.

    Inputs are the state at the END OF THE LAST WALK FRAME (the sim row at ``a_i``, the frame
    before the roll would dispatch): Link's position and ``shape_angle.y`` == walk facing/travel
    (s16/u16), and Tetra's position. ``link_y``/``tetra_y`` default to the same-floor courtyard
    case (the Y gate compares attention points, Tetra's at ``pos.y + 140`` vs Link's at
    ``92.5 + model root`` (``setAttentionPos``, ``d_a_player_main.cpp:10271``) -- a ~47 u ``dy``
    on a shared floor, far inside the (-300, 300) gate, so feet Y is an adequate stand-in;
    pass real attention Ys only if the actors ever leave a shared floor).

    ``cantalk`` = Tetra's ``dEvtCnd_CANTALK_e`` this frame (her ``eventOrder``,
    ``d_a_npc_zl1.cpp:1053-1058``). The s168c live talk proves it ON at the courtyard herd's
    walk-end; True is also the conservative acceptance-side default (a False here can only
    over-refuse, never admit a talker). Pass False only off a modelled/measured Zl1 state.

    Necessary-and-sufficient within the module scope (see header): with A pressed, doStatus
    resolution is deterministic and ``orderTalk`` precedes the roll dispatch, so listed == eaten.
    """
    if not cantalk:
        # check_event_condition (d_attention.cpp:229-250): no CANTALK -> weight 0 -> not listed.
        return False
    lp = (_f(link_x), _f(link_y), _f(link_z))
    tp = (_f(tetra_x), _f(tetra_y), _f(tetra_z))
    if zl1_attention_active(lp, link_facing, tp):
        return True
    # Decomp-ambiguous dead-behind edge (face error -0x8000): conservative talk IF the dist/Y
    # gates pass, tested through the SAME region code at face error 0 -- see talk-eat.md.
    dx = fsubs(_f(tetra_x), _f(link_x))
    dz = fsubs(_f(tetra_z), _f(link_z))
    bearing = attn_yaw_bam(dx, dz)
    if _s16(bearing - _s16(link_facing)) == -0x8000 and zl1_attention_active(lp, bearing, tp):
        return True
    return False
