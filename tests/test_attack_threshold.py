"""THE A-PRESS IS ONLY A ROLL ABOVE A STICK THRESHOLD -- the gate the model did not have.

`setDoStatusBasic` (d_a_player_main.cpp:2220) sets `dActStts_ATTACK_e` only for
``mStickDistance > m_HIO->mBasic.m.field_0x1C``, and that status is the ONLY one
`checkNextActionFromButton` (4318) turns into `procFrontRoll_init`. At or below it the same press is
`dActStts_PUT_AWAY_e` (2218) and Link SHEATHES the sword. `daPy_HIO_basic_c0::m`
(d_a_player_HIO_data.inc:4) puts the value at **0.75**.

The model gated the roll on the 0.05 LOCOMOTION floor instead, which let the entry search score --
and `confirm_entry` "confirm with a real A-press" -- candidates whose aim can never roll on console.
Session 88 spent a delivery on one: the plan went out exactly as authored and Link never entered
FRONT_ROLL, with Tetra bit-identical to her pre-roll position because he never reached her. Session
86's delivery, aim msd 0.889, rolled. Two console runs, one on each side of 0.75.

Fixtures: `courtyard_attack_gate_s88_console.json` (LOCKED, the press that sheathed) and the s86 entry
capture (the press that rolled). Offline -- no Dolphin.
"""
import json
import os

import pytest

from harness.tetrapush import entry_score as SC
from harness.tetrapush import entry_search as ES
from harness.tetrapush import two_roll as TR
from tww_sim.core.mathlib import main_stick_decode
from tww_sim.land.land import FRONT_ROLL, INPUT_DELAY, LandState, MOVE


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


GATE = json.load(open(_fx('courtyard_attack_gate_s88_console.json')))
T = float(LandState.ATTACK_MSD_MIN)


def _walk_to_speed(**kw):
    """A LandState walking at the cap on a wall-free floor, ready for an A-press."""
    s = LandState(use_anim=False, native=False, sword_drawn=True, **kw)
    for _ in range(30):
        s.step(128, 255)                      # full forward: the walk reaches mMaxNormalSpeed
    return s


def _press_a(msd_bytes):
    """Walk up, then hold `msd_bytes` with A. Returns the state after the press has been acted."""
    s = _walk_to_speed()
    sx, sy = msd_bytes
    for _ in range(INPUT_DELAY + 1):
        s.step(sx, sy, buttons=0x100)
    return s


# --------------------------------------------------------------------------- the decomp value

def test_the_threshold_is_the_shipped_hio_value():
    """0.75 is `mBasic.field_0x1C`, read off the shipped HIO block -- not a fitted number."""
    assert T == 0.75
    assert float(LandState.ATTACK_MSD_HEAVY) == 0.5      # mMove.field_0x80, the carrying scale
    assert GATE['threshold']['value'] == T
    assert GATE['threshold']['hio'] == 'm_HIO->mBasic.m.field_0x1C'


# --------------------------------------------------------------------------- the model gates on it

@pytest.mark.parametrize("byts,rolls", [((85, 182), True), ((95, 168), False)])
def test_the_press_rolls_above_the_threshold_and_is_refused_below_it(byts, rolls):
    """The two aims the console measured, on the model: one dispatches FRONT_ROLL, the other leaves
    Link walking and latches the planner-rejection flag."""
    msd = main_stick_decode(*byts)[1]
    assert (msd > T) is rolls, "the fixture's own bracket"
    s = _press_a(byts)
    assert (s.state == FRONT_ROLL) is rolls
    assert s.attack_blocked is (not rolls)
    if not rolls:
        assert s.state == MOVE, "the refused press leaves the walk running (it sheathes, unmodeled)"


def test_the_boundary_splits_adjacent_byte_pairs_and_the_flag_is_sticky():
    """The threshold cuts BETWEEN two deliverable byte pairs, 4.6e-4 of stick apart -- (181, 157) at
    0.749943 and (74, 102) at 0.750400 -- so it is a real edge in the input alphabet and not a
    formality. No pair decodes to exactly 0.75, which is why the strictness of `>` is untestable by
    delivery and is taken from the decomp. The flag latches, like `sidle_blocked`."""
    below, above = (181, 157), (74, 102)
    assert main_stick_decode(*below)[1] < T < main_stick_decode(*above)[1]
    assert not any(main_stick_decode(sx, sy)[1] == T for sx in range(256) for sy in range(256))
    hi = _press_a(above)
    assert hi.state == FRONT_ROLL and not hi.attack_blocked
    lo = _press_a(below)
    assert lo.attack_blocked and lo.state != FRONT_ROLL
    for _ in range(5):
        lo.step(128, 255)
    assert lo.attack_blocked, "sticky, like sidle_blocked"


def test_the_native_twin_refuses_the_same_press():
    """The C LandCore dispatches the roll too, so the gate has to be in both or the search and the
    reference disagree about which candidates exist."""
    for byts, rolls in (((85, 182), True), ((95, 168), False)):
        s = LandState(use_anim=True, native=True, sword_drawn=True)
        for _ in range(30):
            s.step(128, 255)
        for _ in range(INPUT_DELAY + 1):
            s.step(byts[0], byts[1], buttons=0x100)
        assert (s.state == FRONT_ROLL) is rolls, byts


# --------------------------------------------------------------------------- the search owes it too

def test_the_aim_alphabet_only_offers_aims_that_dispatch():
    """`roll_aim_fan` is the alphabet's real membership test. Deduping the byte grid by decoded angle
    keeps the FIRST pair in grid order, which is often too shallow to roll -- so the pre-session-88
    alphabet offered aims that sheathe."""
    for _f, byts in ES.aim_alphabet():
        assert main_stick_decode(*byts)[1] > T, byts
    old = {tuple(b) for _f, b in ES.aim_alphabet(msd_min=0.0)}
    assert (95, 168) in old, "the falsified alphabet is still reachable for diagnostics"
    assert (95, 168) not in {tuple(b) for _f, b in ES.aim_alphabet()}


def test_every_angle_keeps_a_representative_that_can_roll_where_one_exists():
    """The gate is not a narrowing of the aim SET: an angle drops out only when no byte pair reaching
    it clears the threshold at all. Session 88's failed aim is such an angle -- which is why its 36
    candidates are dead rather than re-representable."""
    full = TR.reachable_stick_fan(msd_min=0.0)
    deep = dict(TR.roll_aim_fan())
    assert len(deep) < len(full)
    ang = main_stick_decode(95, 168)[0]
    assert ang not in deep
    assert all(main_stick_decode(sx, sy)[1] <= T
               for sx in range(256) for sy in range(256)
               if main_stick_decode(sx, sy)[0] == ang), "no deep member of that angle exists"


def test_the_gate_reaches_the_PASS_and_not_only_the_alphabet(tmp_path):
    """**THE FIX HAS TO CROSS THE CACHE, and session 89 spent 5000 s learning that it did not.**

    `entry_score.qualified` is the only thing a pass consults for which (facing, thrust) is worth
    spending candidates on AND for the aim bytes that reach each one, and it is cached to disk. The
    key validated `cells`/`csangle`/`thrusts` -- nothing about the threshold -- so the session-89
    re-run silently re-used a qualification written before the gate existed and came back
    BIT-IDENTICAL to the pass before it: 2 of its 3 configurations carried aim `[95,168]`, msd
    0.5705, the exact aim of the delivery that sheathed the sword.

    So: a cache at the wrong threshold is refused, and every configuration a pass is handed can
    actually roll. The general rule is razor rule 10 -- every input to a cached derivation belongs in
    its key."""
    p = str(tmp_path / 'qualified.json')
    live = SC.qualified(path=p)
    assert live, "the qualification must be non-empty or this gate proves nothing"
    for q in live:
        assert q['aim'] is None or main_stick_decode(*q['aim'])[1] > T, q
    assert json.load(open(p))['msd_min'] == T

    stale = json.load(open(p))
    stale['msd_min'] = 0.0                       # a cache written before the gate existed
    stale['quals'] = [dict(stale['quals'][0], facing=1, aim=[95, 168])]
    json.dump(stale, open(p, 'w'))
    again = SC.qualified(path=p)
    assert [q['facing'] for q in again] != [1], "a pre-gate cache was silently re-used"
    assert json.load(open(p))['msd_min'] == T, "and the refusal must rewrite it"


def test_confirm_entry_now_rejects_the_candidate_the_console_falsified():
    """The check that WOULD have caught it, on the engine as it stands: `confirm_entry` replays the
    plan and a real A-press, and the session-87 frame-minimal hit no longer rolls at all."""
    hit = GATE['hit']
    c = ES.confirm_entry(hit)
    assert c['ok']['rolled'] is False and c['all_ok'] is False


# --------------------------------------------------------------------------- what the console said

def test_the_console_bracket_straddles_the_threshold():
    """Two deliveries, one each side, and the fixture records which rolled -- so the value is
    console-bracketed and not only decomp-read."""
    rolled = {b['rolled']: b for b in GATE['console_bracket']}
    assert rolled[True]['msd'] > T > rolled[False]['msd']
    assert rolled[False]['msd'] == pytest.approx(0.570479, rel=1e-5)
    assert rolled[True]['msd'] == pytest.approx(0.889082, rel=1e-5)


def test_the_console_never_entered_the_roll_and_never_touched_tetra():
    """The symptom, from the locked capture: MOVE at the sampled frame, and Tetra bit-identical to
    where the herd left her -- so this is a press that did nothing, not a roll that went wrong."""
    s = GATE['samples'][0]
    assert s['link']['proc'] == MOVE
    assert GATE['model_of_the_day']['proc'] != MOVE, "the model predicted a cut here"
    seed = ES.console_seed()
    assert s['tetra']['x'] == seed['tetra'][0] and s['tetra']['z'] == seed['tetra'][1]
    assert s['tetra']['stt'] == 3
