"""THE CAMERA IS A FREE INPUT CHANNEL INSIDE THE ENTRY PLAN (session 95).

Session 83 priced a camera slew at zero and was right about the half it measured -- the AIM alphabet is
quantized to the console sine cell and the frozen camera already reached both cells of the window it
was measured against. It also priced the WALK half, and there it used the wrong grid: the whole stick
alphabet at ``msd_min=0``, 3612 of 4096 direction cells, when the fan keeps only endpoints at the
speedF 17 cap and so can hold only the CAP-magnitude sticks -- 1736 of 4096, 42.4%. A camera offset
slides that 42% subset across the circle, so two cameras 16 BAM apart command largely different world
directions and therefore a different discrete entry set. That is the axis session 94's family pass ran
out of (2.4x the candidates, a bit-identical argmin).

These gates pin the four things a camera claim rests on:

* the PRICE -- the console entry plan holds a neutral C-stick on every frame, so a slew there costs no
  frame (rule 13, priced before the pass);
* the TRAIL -- the csangle a held byte delivers is a pure function of the byte, and the value the fan
  INJECTS is the one the wired `LandCamera` integrates, 0-ULP;
* the DELIVERY -- a camera hit is only worth anything if a real A-press at that camera reproduces it,
  and if the byte survives `dtm_make.cal`;
* the COUNTING -- two bytes with one trail are one draw, and the frozen camera through the new code
  path is bit-for-bit the pass every session before this one ran.

Offline: the native fan + the wired Python camera, no Dolphin.
"""
import json
import os

import pytest

from tww_sim.core.anim import _anmc as N
from tww_sim.land.plan_land._primitives import main_stick_decode
from harness.tetrapush import entry_camera as EC
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', name)


SMALL_FAN = dict(base_frames=(0,), s1_stride=64, j1=(2,), s2_stride=64, j2max=2)


# ------------------------------------------------------------------------------- the price

def test_the_entry_plan_holds_a_neutral_c_stick_on_every_frame():
    """**THE PRICE, off the locked console fixture rather than an argument.**

    `fixtures/courtyard_entry_s86_console.json` is the delivered herd + entry plan + A-press. The herd
    ends at log row 77 (the escape atom's last frame); every row after it -- the walk-in, the A-press
    and the roll -- carries ``substickX == 128``. The channel a camera slew would spend is IDLE there,
    so the slew cannot cost a frame; what bounds it is the camera's own rate (`reach`)."""
    log = json.load(open(_fx('courtyard_entry_s86_console.json')))['log']
    entry = log[78:]
    assert len(entry) >= 6
    assert {int(r.get('substickX', 128)) for r in entry} == {EC.NEUTRAL}
    assert {int(r.get('substickY', 0)) for r in entry} == {0}
    # and the A-press really is in that idle window -- otherwise the price is about the wrong frames
    assert any(int(r.get('buttons', 0)) & 0x100 for r in entry)


def test_the_reach_is_bounded_and_fine():
    """What the idle channel buys by the 4th entry frame: several hundred BAM either way, on a ladder
    fine enough that the sine cell (16 BAM) is not the limiting resolution."""
    r = EC.reach(4)
    assert r['lo'] < -300 and r['hi'] > 300           # ~+-2 deg at least, measured -821..+714
    assert r['n_distinct'] > 40                       # far more than the 16 sub-cell offsets
    assert r['per_byte'][EC.NEUTRAL] == 0             # neutral freezes it, by definition of frozen
    # monotone in the byte: a bigger deflection never slews less
    offs = [r['per_byte'][b] for b in sorted(r['per_byte'])]
    assert offs == sorted(offs)


# ------------------------------------------------------------------------------- the trail

def test_the_trail_is_a_pure_function_of_the_c_stick_byte():
    """`knowledge/mechanics/land-camera.md`: the yaw target moves ONLY with C-stick X and Link's motion
    moves only the camera CENTRE. That is what lets ONE trail serve a whole fan, so it is gated rather
    than assumed -- three held main sticks, bit-identical csangle."""
    seed = ES.console_seed()
    for subx in (EC.NEUTRAL, 254, 1, 200):
        trails = set()
        for stick in ((195, 164), (85, 182), (240, 60)):
            hold = dict(seed['log'][-1], buttons=0, substickX=subx, substickY=0,
                        stickX=stick[0], stickY=stick[1])
            _run, rows = ES.continue_walk([hold] * 5)
            trails.add(tuple(int(r['csangle']) & 0xFFFF for r in rows))
        assert len(trails) == 1, "trail depends on the main stick at subx %d" % subx
        assert trails.pop()[:len(EC.cam_trail(subx, 5))] == EC.cam_trail(subx, 5)


def test_the_injected_trail_reproduces_the_wired_camera_0_ulp():
    """THE LICENCE FOR INJECTING A CAMERA AT ALL. The fan runs the stripped native config with csangle
    injected; the plan it authors will run on a console that integrates the camera. So the injected
    trail must reproduce the wired one exactly -- position, lean and speedF, `_bits`-equal, never a
    tolerance (`[[zero-ulp-tests-only]]`).

    It also pins the ALIGNMENT, which a constant injection cannot see: frame k decodes against
    ``trail[k]``, the value `continue_walk` reports for frame k, not the one committed after it."""
    seed = ES.console_seed()
    for subx in (254, 1, 200):
        trail = EC.cam_trail(subx, 6)
        for stick in ((195, 164), (240, 60)):
            hold = dict(seed['log'][-1], buttons=0, substickX=EC.delivered_byte(subx), substickY=0,
                        stickX=stick[0], stickY=stick[1])
            _run, rows = ES.continue_walk([hold] * 6)
            wired = [(r['x'], r['z'], r['m351C'], r['speedF']) for r in rows]

            base, _run0 = EF.base_core(0, seed=seed, hold=dict(hold, stickX=seed['log'][-1]['stickX'],
                                                               stickY=seed['log'][-1]['stickY']))
            core = base.clone(base.pe.clone_state())
            fleet = N.CourtyardFleet([core], 1)
            got = []
            for k in range(6):
                fleet.set_schedule([[(stick[0], stick[1], 0, int(hold.get('triggerL', 0)),
                                      int(trail[k]))]])
                fleet.run_par(1, 0)
                got.append((core.pos_x, core.pos_z, int(core.m351C) & 0xFFFF, core.speedF))
            assert got == wired, "subx %d stick %s diverges from the wired camera" % (subx, stick)


# ------------------------------------------------------------------------- the counting

def test_the_camera_alphabet_is_deduped_on_the_trail():
    """Two bytes that deliver the same csangle sequence are ONE camera draw. Counting them separately
    is exactly how the aim axis priced at 8.00x (`strategy/clip-lottery-draws.md`,
    `history/entry-search-s81-camera-lever.md`), one axis over."""
    alpha = EC.camera_alphabet()
    trails = [t for _b, t in alpha]
    assert len(set(trails)) == len(trails)
    assert len(alpha) < len(EC.deliverable_bytes())          # there ARE duplicate bytes to collapse
    assert EC.NEUTRAL in {b for b, _t in alpha}


def test_every_alphabet_byte_survives_dtm_delivery():
    """`dtm_make.cal` clamps a C-stick 255 to 254 and 0 to 1 exactly as it does the main stick
    (`[[octagon-clamp-decode-bug]]`), so an alphabet built on raw bytes would author trails the console
    never runs. The alphabet is the delivered set."""
    for b, _t in EC.camera_alphabet():
        assert EC.delivered_byte(b) == b
        assert EC.cam_trail(b) == EC.cam_trail(EC.delivered_byte(b))
    assert EC.delivered_byte(255) == 254 and EC.delivered_byte(0) == 1


def test_the_walk_alphabet_a_camera_re_indexes_is_the_cap_magnitude_one():
    """The claim the whole axis rests on, measured against a REAL fan instead of the speed law: every
    stick a fan candidate holds decodes at msd 1.0, so the grid a camera slides is the 2280-angle
    cap-magnitude one (1736 of 4096 cells), not the 7032-angle whole grid session 83 priced."""
    seen = set()
    for k, plan in EF.capped(EF.iter_fan2(**SMALL_FAN), 4):
        for i in range(1, len(plan), 3):
            seen.add((plan[i], plan[i + 1]))
    assert seen, "the small fan produced no candidates"
    msds = {main_stick_decode(sx, sy)[1] for sx, sy in seen}
    assert msds == {1.0}, "a sub-cap stick survived the cap prune: %s" % sorted(msds)
    assert len(EC.walk_alphabet()) == 2280
    assert len(EC.walk_cells()) == 1736


def test_a_camera_offset_commands_directions_the_frozen_one_cannot():
    """The mechanism, as a number: one sine cell of camera moves ~half the walk grid onto cells the
    frozen camera cannot reach at all. This is why a camera is a fresh draw and not more of the same
    one."""
    c = EC.cell_census([-16, -1, 1, 16])
    assert c['n_frozen'] == 1736
    by = {r['off']: r for r in c['rows']}
    assert by[16]['n_new_vs_frozen'] > 800 and by[-16]['n_new_vs_frozen'] > 800
    assert 0 < by[1]['n_new_vs_frozen'] < 200        # neighbours are ~94% correlated, not identical
    assert c['n_union'] > 1.5 * c['n_frozen']


# --------------------------------------------------------------------------- the aim side

def test_the_roll_facing_latches_one_frame_after_the_a_press():
    """WHERE THE CAMERA IS NOT FREE, measured by firing the roll and reading the facing back rather
    than by reasoning about the delay (`_notes/s95_aim_frame.py`).

    The A-press sits on trail index ``frames``; the target is computed when the input is ACTED, one
    frame later, so the roll's facing is ``decoded_aim + 0x8000 + trail[frames + 1]``. The camera is
    still RAMPING there, which is why a hard slew re-indexes the whole aim alphabet -- the aim that
    reaches cell 2551 frozen rolls into cell 2640 at subx 249."""
    from tww_sim.land.plan_land._primitives import main_stick_decode
    ang, _msd = main_stick_decode(85, 182)
    seed = ES.console_seed()
    for subx in (207, 249):
        cand = next(((k, p) for k, p in EF.capped(EC.fan_cam(subx, frames=4, **SMALL_FAN), 4)
                     if EF.plan_frames(p) == 4), None)
        assert cand is not None
        k, plan = cand
        hit = dict(plan=list(plan), aim=[85, 182], facing=0, m351C=ES.lean_at_roll(k[2]),
                   walk=[k[0], k[1]], entry=[0.0, 0.0], substickX=subx)
        got = ES.confirm_entry(hit, seed=seed)['measured']['facing']
        trail = EC.cam_trail(subx, 12)
        assert got == (ang + 0x8000 + trail[EC.aim_frame(4)]) & 0xFFFF
        # and the neighbouring indices are not merely close -- they are cells away
        for h in (EC.aim_frame(4) - 1, EC.aim_frame(4) + 1):
            assert got != (ang + 0x8000 + trail[h]) & 0xFFFF


def test_a_camera_that_cannot_aim_the_cell_is_not_a_camera_for_that_cell():
    """The bound on the axis, and the one thing that could have made it a phantom: the residual is a
    property of the facing CELL and camera-independent, but the BYTES that reach the cell are not. So
    a camera draw only counts if `aim_at` finds an aim -- cell 2553 survives at 64 of the 82 draws,
    and a pass skips the rest instead of scoring plans no A-press can deliver."""
    alpha = [b for b, _t in EC.camera_alphabet()]
    ok = EC.aimable_cameras(2553, alpha, frames=4)
    assert 40 < len(ok) < len(alpha)
    for b, a in ok:
        # the aim really does resolve to the cell at THIS camera's dispatch csangle
        from tww_sim.land.plan_land._primitives import main_stick_decode
        ang, msd = main_stick_decode(*a['aim'])
        assert ES.aim_cell((ang + 0x8000 + a['csangle']) & 0xFFFF) == 2553
        assert msd > 0.75                       # deep enough to dispatch (the s88 ATTACK gate)
    # `[[search-space-contains-human]]`: at the frozen camera the delivered clip's OWN cell must be
    # aimable, by the very bytes the console rolled (the representative or one of its siblings)
    delivered = json.load(open(_fx('courtyard_facing_window_s92.json')))['delivered']
    frozen = EC.aim_at(delivered['cell'], EC.NEUTRAL, 4)
    assert frozen is not None
    assert delivered['aim'] in [frozen['aim']] + [list(s) for s in frozen['siblings']]


# --------------------------------------------------------------------------- the fan path

def test_the_frozen_camera_through_the_camera_path_is_the_pass_everyone_else_ran():
    """THE REGRESSION THAT MATTERS: the neutral byte's trail is the constant frozen csangle, so a
    camera fan at ``subx=128`` must reproduce the default fan KEY AND VALUE, bit for bit. If the
    injection path drifted, every pre-session-95 number would stop being comparable."""
    ref = dict(EF.iter_fan2(**SMALL_FAN))
    got = dict(EC.fan_cam(EC.NEUTRAL, **SMALL_FAN))
    assert got == ref


def test_a_slewing_hold_without_a_trail_is_refused():
    """The base replay is WIRED and the fan is INJECTED, so a C-stick in one and not the other is a
    plan no controller delivers. It raises instead of quietly running two cameras."""
    seed = ES.console_seed()
    with pytest.raises(ValueError):
        next(EF.iter_fan2(hold=dict(seed['log'][-1], buttons=0, substickX=254), **SMALL_FAN))


def test_the_camera_moves_the_reachable_entry_set():
    """End of the mechanism: a slewed camera's fan does not merely re-label the frozen one's endpoints,
    it reaches points the frozen fan does not -- which is the only way the closest approach to a
    residual zero can improve once the family axis has saturated."""
    frozen = {(k[0], k[1]) for k, _p in EC.fan_cam(EC.NEUTRAL, frames=4, **SMALL_FAN)}
    slewed = {(k[0], k[1]) for k, _p in EC.fan_cam(254, frames=4, **SMALL_FAN)}
    assert frozen and slewed
    assert len(slewed - frozen) > 0.5 * len(slewed), "the slewed fan is mostly the frozen one"


def test_cameras_a_fan_cannot_tell_apart_are_one_pass():
    """THE AXIS'S OWN BUDGET RULE, measured (session 95). A segmented alphabet of 137 cameras carried
    only 49 distinct 4-frame walk trails: the rest differ only AFTER the walk, which re-aims the same
    cloud instead of drawing a new one. Scoring them separately spent 2.8x the clock for the same
    draws.

    The key is `fan_steps` and NOT the plan's frame cap, because the fan records the endpoint after
    ``j + 1`` steps and runs the second segment to ``j2max`` -- 8 of those 49 groups really did report
    different draws, which is what a too-short key would have thrown away."""
    steps = EC.fan_steps(**SMALL_FAN)
    assert steps > 4                                   # the fan steps past a 4-frame plan
    # two cameras that only differ after `steps` frames are one pass; before it, two
    late = [EC.NEUTRAL] * steps + [1]
    early = [EC.NEUTRAL] * 2 + [1]
    assert len(EC.dedupe_cameras([EC.NEUTRAL, late], steps)) == 1
    assert len(EC.dedupe_cameras([EC.NEUTRAL, early], steps)) == 2
    # and the collapse is exactly what makes the fans identical
    a = dict(EC.fan_cam(EC.NEUTRAL, frames=4, **SMALL_FAN))
    b = dict(EC.fan_cam(late, frames=4, **SMALL_FAN))
    assert a == b


# --------------------------------------------------- the SHAPE of the axis (session 96)

def test_the_walk_side_channel_carries_exactly_two_bytes():
    """**THE AXIS'S SUPPLY LAW.** The 4-frame walk trail is a function of the C-stick bytes on entry
    frames 0 and 1 and of nothing later -- measured over every 4-byte path at stride 32 (4096 of them):
    0 disagree with their 2-byte prefix, while 3584 disagree with their 1-byte prefix.

    This is why session 95's second switch point bought nothing: it multiplied the C-stick paths 8x and
    the `fan_steps` trails 7.7x and left the distinct walk trails bit-identical (64 -> 64 at stride 32,
    196 -> 196 at stride 16). Walk supply is (deliverable bytes)^2, not (bytes)^frames -- and it is also
    the mechanism behind the s95 observation that had none: 41 of 49 walk groups reported a bit-identical
    draw set because those cameras differ only in bytes the walk cannot see."""
    assert EC.walk_channel(frames=4, step=32, sample=200) == EC.WALK_CHANNEL == 2


def test_a_tail_byte_moves_the_aim_and_leaves_the_walk_trail_alone():
    """The DECOUPLING the supply law buys, which is the session-96 lever: a byte after the walk channel
    changes the trail at `aim_frame` -- and so which cells are aimable -- while leaving the walk trail
    bit-for-bit. Held bytes cannot do this: one byte has to serve both jobs, which is the whole reason
    session 95 had to skip 18 of its 82 cameras as "not aimable"."""
    walk = [128, 160]
    base = EC.cam_trail(walk, EC.TRAIL_FRAMES)
    aims = set()
    for tail in EC.deliverable_bytes(32):
        t = EC.cam_trail(walk + [tail], EC.TRAIL_FRAMES)
        assert t[:4] == base[:4], "a tail byte moved the walk trail"
        aims.add(t[EC.aim_frame(4)])
    assert len(aims) > 4, "the tail byte does not move the aim frame either -- then it is inert"


def test_one_aimable_camera_per_walk_trail_beats_enumerating_paths():
    """WHAT A PASS SHOULD BUY. `walk_cameras` picks the walk pair first and then searches a TAIL byte
    that keeps the scope aimable, so every camera it returns is a distinct walk cloud AND deliverable.

    Against session 95's path enumeration at the same byte stride this is strictly better on both terms
    at once -- more distinct walk clouds from fewer passes -- because the paths it drops were aim
    variants of clouds already in the list, and the clouds it adds are ones no single held byte could
    aim. Measured at stride 32: 64 clouds from 64 passes, against 49 clouds from 137."""
    keep, dead = EC.walk_cameras(2553, frames=4, step=32)
    assert not dead, "a walk trail no tail byte can aim: %s" % dead[:4]
    trails = {EC.cam_trail(seq, EC.TRAIL_FRAMES)[:4] for seq, _t in keep}
    assert len(trails) == len(keep), "two cameras in the list share a walk cloud"
    for seq, _t in keep:
        assert EC.aim_at(2553, seq, 4) is not None
    seg = [s for s, _t in EC.segmented_alphabet(2553, frames=4, step=32)]
    seg_trails = {EC.cam_trail(s, EC.TRAIL_FRAMES)[:4] for s in seg}
    assert len(trails) > len(seg_trails)               # more supply...
    assert len(keep) < len(seg)                        # ...from fewer passes


def test_a_pass_reports_the_dedup_key_and_thrust_scope_it_ran_under():
    """A pass's own budget choices are part of its result, exactly as `cell_scope` is: session 95's
    "2x cheaper" number came from a dedup key that `dedupe_cameras` was never called with, and no pass
    output said which key it used. Now every pass carries both knobs."""
    res = EC.search([2553], [EC.NEUTRAL], frames=4, fan=SMALL_FAN, thrusts=(15,))
    assert len(res) == 1
    assert res[0]['group_steps'] == EC.fan_steps(**SMALL_FAN)     # the lossless default
    assert res[0]['thrusts'] == [15]
    tight = EC.search([2553], [EC.NEUTRAL], frames=4, fan=SMALL_FAN, thrusts=(15,), group_steps=4)
    assert tight[0]['group_steps'] == 4
    # narrowing the thrust scope drops configurations without touching the ones it keeps
    wide = EC.search([2553], [EC.NEUTRAL], frames=4, fan=SMALL_FAN)
    assert wide[0]['n_configurations_aimable'] > res[0]['n_configurations_aimable']
    assert {nd['thrust'] for nd in res[0].get('near_detail', [])} <= {15}


def test_the_scope_right_of_the_delivered_cell_is_cell_2553_alone():
    """THE NEGATIVE THAT KILLED A 2.9x (session 96). Adding cell 2551 to a camera pass costs the same
    clock as the thrust-14 configuration it replaces and buys 3.1x the draws -- and it is worth NOTHING,
    because 2551 is LEFT of the console-delivered cell 2552 and the objective term is the exit angle as
    far RIGHT as possible (`strategy/clip-exit-angle.md`). A rate measured in the search's own currency
    can read 2.9x on a prize the objective refuses.

    So the scope is not a free knob: right of the delivered cell there is 2553, then a measured-dead
    2554-2559, then a second lobe no frame-floor plan reaches. Cell 2553 is the whole target."""
    w = EF.facing_window()
    assert w['delivered']['cell'] == 2552
    right = EF.parse_cell_spec('right')
    assert min(right) == 2553
    reachable = [c for c in right if c in {ES.aim_cell(q['facing']) for q in EF.qualified()}]
    assert 2553 in reachable
    # everything else on the right is the second lobe, which session 93 measured out of frame-floor reach
    assert all(c >= 2560 for c in reachable if c != 2553)


# ------------------------------------------------------------------------- the delivery

@pytest.mark.slow
def test_a_camera_candidate_confirms_with_a_real_a_press_at_its_own_camera():
    """The end-to-end check, and the one that makes a camera hit deliverable: take a candidate the
    camera fan predicts, replay the console log with the SAME C-stick byte and a real A-press through
    the WIRED camera, and read the roll entry back. `entry_search.confirm_entry` carries
    ``hit['substickX']`` for exactly this.

    It is also the strongest form of the injection gate -- the fan predicted this entry with an
    injected trail, the confirm reproduces it with an integrated camera."""
    subx = 254
    quals = EF.qualified()
    q = quals[0]
    cand = None
    for k, plan in EC.fan_cam(subx, frames=4, **SMALL_FAN):
        cand = (k, plan)
        break
    assert cand is not None
    k, plan = cand
    entry = ES.roll_entry((k[0], k[1]), q['facing'])
    hit = dict(plan=list(plan), aim=q['aim'], facing=q['facing'], m351C=ES.lean_at_roll(k[2]),
               walk=[k[0], k[1]], entry=[entry[0], entry[1]], substickX=subx)
    res = ES.confirm_entry(hit)
    assert res['ok']['rolled'] and res['ok']['walk_matches'], res


def test_a_sequence_camera_is_deliverable_frame_for_frame():
    """THE HIT THIS PASS IS HUNTING HAS TO BE CONFIRMABLE, and until session 96 it was not: the cameras
    worth searching are 3-byte paths (`walk_cameras`), and `confirm_entry` did ``int(hit['substickX'])``,
    which raises on a sequence. Every camera pass since session 95 could have produced a hit nothing
    could replay.

    The fix has to be frame-for-frame, not merely non-crashing: byte k of the path belongs on replayed
    frame k, the alignment `cam_trail` measures the trail on. So this gate reproduces the whole trail
    through the replay -- a sequence camera's confirm must land on the walk endpoint the fan predicted
    (which is decided by the walk channel) AND on the facing (which is decided by the aim frame, a byte
    the walk cannot see). Holding the first byte throughout passes the first and fails the second.

    Writing it is also what surfaced the second delivery bug: the aim has to be taken at the CANDIDATE's
    own plan length (`plan_frames`), never at the pass's frame cap. One pass carries several lengths, the
    facing latches against ``trail[n + 1]``, and at a slewing camera each n reads a different csangle --
    so a cap-computed aim delivers a facing 12 BAM off for a short plan. Frozen, the trail is constant
    and nothing shows."""
    seq = [1, 160, 128]                         # a hard slew, then a distinct tail for the aim frame
    trail = EC.cam_trail(seq, EC.TRAIL_FRAMES)
    assert trail[:2] != trail[3:5], "this path does not actually slew -- the gate would prove nothing"
    cand = next(iter(EC.fan_cam(seq, frames=4, **SMALL_FAN)), None)
    assert cand is not None
    k, plan = cand
    n = EC.plan_frames(plan)
    aim = EC.aim_at(2553, seq, n)
    assert aim is not None                      # the camera keeps the scope aimable, or it is no camera
    # the bug this pins: the cap's aim is a DIFFERENT facing for this plan, though the same cell
    if n != 4:
        capped = EC.aim_at(2553, seq, 4)
        assert capped is not None and capped['facing'] != aim['facing']
    entry = ES.roll_entry((k[0], k[1]), aim['facing'])
    hit = dict(plan=list(plan), aim=aim['aim'], facing=aim['facing'], m351C=ES.lean_at_roll(k[2]),
               walk=[k[0], k[1]], entry=[entry[0], entry[1]], substickX=seq)
    res = ES.confirm_entry(hit)
    assert res['ok']['rolled'], res
    assert res['ok']['walk_matches'], res        # the walk channel, replayed
    assert res['ok']['facing'], res              # the aim frame, replayed at the right index
    # and the misalignment this gate exists to catch: one held byte is a DIFFERENT camera
    held = ES.confirm_entry(dict(hit, substickX=seq[0]))
    assert not held['all_ok'], "holding the path's first byte reproduced it -- the path is inert"
    # the confirm hands back the frames it replayed, and they carry the path -- `deliver.build_boot_movie`
    # reads `substickX` per row, so this is what makes the camera survive the DTM
    got = [int(r['substickX']) for r in res['frames']]
    assert got[:len(seq)] == seq and set(got[len(seq):]) <= {seq[-1]}, got
