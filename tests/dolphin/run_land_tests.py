"""LAND-movement regression: ALL 5 cases are SIM-vs-LIVE (walk + the 4 ATN-tier techs).

Each case seeds a `superswim.land.LandState` from the live frame-0 snapshot, steps the sim over
the input burst (stick + L-target), and compares the END state against the game replayed via one
race-free `advanceseq`. mNormalSpeed (signed potential_speed), the proc state machine, facing
(shape_angle.y) and travel (current.angle.y) are all BIT-EXACT. Position (pos_z) is checked
bit-exact via the ported anim engine ONLY for the on-axis walk (which stays in MOVE); any run that
visits ATN_MOVE uses the calibrated position fallback (the ANM_ATN* anims are not ported) and pos
is not asserted there. On top of the sim-vs-live core, each ATN case layers its characteristic tech
assertions (L-held targeting slide with facing locked; L-released extended slide; camera-relative
speed preservation; facing/travel decouple) -- these document the mechanic + guard the anchor.

Determinism: the anchor + inputs are fixed and advanceseq is race-free, so end-state is
reproducible and can be locked tight, exactly like the swim run_tests baselines. These are the
land analogue of the immutable swim syncs -- do not loosen a check to make a run pass; a real
change means the sim (or tech, or anchor) changed, which is a finding, not a test edit.

Free cam: C-stick full DOWN every frame (substickY=0) so csangle stays 0 (the reference).
L-target uses digital L (buttons 0x40) + analog triggerL=255. ESS = (128,110); ESS-left =
(110,128), ESS-right = (146,128) at the same off-center magnitude.

Requires Dolphin running with twwgz booted. Loads land_flatwalk@twwgz.sav BY PATH.
Usage:
  python run_land_tests.py            # assert locked expectations (exit 0 iff all pass)
  python run_land_tests.py record=1   # print end-states to (re)lock after a DELIBERATE change
"""
import os, sys  # >>> repo bootstrap: locate superswim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path: sys.path.append(_tb)
import dolphin_mem as D
from harness.dtm.run_dtm import resolve_anchor
from superswim.land import LandState

ANCHOR = resolve_anchor("land_flatwalk@twwgz")
READS = ["link_state", "potential_speed", "true_speed", "shape_angle_y",
         "travel_angle", "csangle", "pos_x", "pos_z", "anim_frame"]


def hold(sx, sy, n, buttons=0, triggerL=0):
    """n one-frame advanceseq elements at (sx,sy), C-stick full down (free cam)."""
    return [{"stickX": sx, "stickY": sy, "substickX": 128, "substickY": 0,
             "buttons": buttons, "triggerL": triggerL, "frames": 1} for _ in range(n)]


L_DOWN = hold(128, 0, 1, buttons=0x40, triggerL=255)   # L-target + full down, 1 frame
A = 0x100                                              # GC PAD_BUTTON_A (the "do"/roll button)

# --- the discovered sequences ---------------------------------------------------------
def seq_walk():        return hold(128, 255, 30) + hold(128, 128, 20)                  # run -> standstill
def seq_brakeslide():  return hold(128, 255, 10) + L_DOWN + hold(128, 110, 10, 0x40, 255)  # L HELD -> targeting slide
def seq_ebs():         return hold(128, 255, 10) + L_DOWN + hold(128, 110, 30)          # L released -> extended slide
def seq_face_left():   return hold(128, 255, 10) + L_DOWN + hold(128, 110, 1) + hold(110, 128, 60)
def seq_brake_right(): return hold(128, 255, 10) + L_DOWN + hold(128, 110, 1) + hold(146, 128, 60)

# --- roll (FRONT_ROLL, state 30) sequences: A while moving -> forward roll. Roll speed set at entry
# from the PRE-roll speedF = clamp(speedF*1.5+0.5, 5, 26); these end MID-ROLL to read that speed. ---
def seq_roll_run():    return hold(128, 255, 15) + hold(128, 255, 1, A) + hold(128, 128, 5)   # full run -> roll @ cap 26
def seq_roll_slow():   return hold(128, 255, 2) + hold(128, 255, 1, A) + hold(128, 128, 5)    # barely moving -> roll near floor
def seq_roll_settle(): return hold(128, 255, 15) + hold(128, 255, 1, A) + hold(128, 128, 40)  # roll played to a full stop
# Frame-perfect EBS out of a roll: HOLD L+down through the roll (17 frames) -> it exits straight to
# ATN at 26; release L into ESS-down -> flip preserves ~-23 (one-frame window). See land-movement.md.
def seq_roll_ebs():  return hold(128, 255, 15) + hold(128, 255, 1, A) + hold(128, 0, 17, 0x40, 255) + hold(128, 110, 14)


def deg(a):
    return (int(a) % 65536) * 360.0 / 65536.0


def sdiff_deg(a, b):
    d = (int(a) - int(b)) % 65536
    if d > 32768:
        d -= 65536
    return d * 360.0 / 65536.0


def replay_sim_vs_live(seq):
    """SIM-vs-LIVE. Load the anchor, read the resting frame-0 seed, seed a LandState, step it
    over the seq (stick + L-target via buttons/triggerL), and replay the same seq live via one
    advanceseq. Returns (sim_state, live_end) for comparison. Mirrors swim run_tests.run_one.

    NOTE: read the seed DIRECTLY after loadstate (no settle frame). A stray `advancewith`
    neutral frame before the advanceseq perturbs the live walk by ~5 units (advancewith vs
    advanceseq pipe artifact -- bug#2); the clean advanceseq-from-load result is 1278.25."""
    D.control_pipe_quiet("clearinput")
    D.control_pipe_quiet("savestate", {"action": "load", "path": ANCHOR.replace('\\', '/')})
    h, m = D.attach()
    seed = {k: D.read_named(h, m, k) for k in READS}   # anchor's deterministic rest state
    sim = LandState(pos_z=seed["pos_z"], facing=int(seed["shape_angle_y"]),
                    travel=int(seed["travel_angle"]), csangle=int(seed["csangle"]),
                    state=int(seed["link_state"]), nspeed=seed["potential_speed"],
                    idle_frame=seed["anim_frame"])
    for el in seq:                                # C-stick full down => free cam, csangle 0
        for _ in range(el.get("frames", 1)):
            sim.step(el["stickX"], el["stickY"],
                     buttons=el.get("buttons", 0), triggerL=el.get("triggerL", 0))
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq})
    h, m = D.attach()
    live = {k: D.read_named(h, m, k) for k in READS}
    return sim, live


def replay_live(seq):
    """LIVE-ONLY (no sim yet). Load the anchor, replay the seq via one race-free advanceseq, and
    return the live end-state as an `e` dict (v/facing/travel/face_trav). For techs whose sim is not
    built -- currently the roll (FRONT_ROLL) tier -- these are immutable live-behavior locks, exactly
    like the ATN cases were pre-sim; flip them to sim-vs-live once superswim.land models the roll."""
    D.control_pipe_quiet("clearinput")
    D.control_pipe_quiet("savestate", {"action": "load", "path": ANCHOR.replace('\\', '/')})
    h, m = D.attach()
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq})
    h, m = D.attach()
    live = {k: D.read_named(h, m, k) for k in READS}
    return {"link_state": int(live["link_state"]), "v": abs(live["potential_speed"]),
            "pot": live["potential_speed"], "facing": deg(live["shape_angle_y"]),
            "travel": deg(live["travel_angle"]),
            "face_trav": abs(sdiff_deg(live["shape_angle_y"], live["travel_angle"])),
            "pos_z": live["pos_z"]}


def sim_checks(sim, live, note):
    """SIM-vs-LIVE core checks (ALL cases): state exact; mNormalSpeed (signed) bit-exact; facing +
    travel bit-exact (s16). pos_z is bit-exact via the anim engine ONLY for the on-axis walk (state
    MOVE throughout) -- runs that visit ATN_MOVE use the calibrated position fallback (ANM_ATN* anims
    unported) so pos is not asserted there. See superswim/land.py step() + knowledge/land-movement.md."""
    dv = abs(sim.nspeed - live["potential_speed"])         # signed: brakeslide/EBS go negative
    dfac = abs(sdiff_deg(sim.facing, live["shape_angle_y"]))
    dtrav = abs(sdiff_deg(sim.travel, live["travel_angle"]))
    visited_atn = getattr(sim, "_visited_atn", False)
    checks = [
        (sim.state == int(live["link_state"]),
         f"state sim/live {sim.state}/{int(live['link_state'])}"),
        (dv <= 0.02, f"potential_speed bit-exact  dv={dv:.5f}  "
                     f"(sim {sim.nspeed:.3f} / live {live['potential_speed']:.3f})"),
        (dfac < 0.1, f"facing bit-exact  d={dfac:.4f}deg  "
                     f"(sim {deg(sim.facing):.2f} / live {deg(live['shape_angle_y']):.2f})"),
        (dtrav < 0.1, f"travel bit-exact  d={dtrav:.4f}deg  "
                      f"(sim {deg(sim.travel):.2f} / live {deg(live['travel_angle']):.2f})"),
    ]
    if not visited_atn and sim._foot is not None:          # on-axis walk: position is bit-exact
        dpos = abs(sim.pos_z - live["pos_z"])
        checks.append((dpos < 0.05,
                       f"pos_z BIT-EXACT (anim)  d={dpos:.4f}  "
                       f"sim {sim.pos_z:.3f} / live {live['pos_z']:.3f}"))
    return checks


# extra_check(live) -> the characteristic tech assertions (documents the mechanic + guards the
# anchor). ALL cases are now SIM-vs-LIVE (sim_checks) with the tech assertions layered on top.
CASES = [
    ("walk_run", seq_walk, "run accel to cap 17 then decel to standstill", None),
    ("brakeslide", seq_brakeslide, "L held -> targeting slide, facing locked", lambda e: [
        (e["link_state"] == 7, f"state 7 (ATN_MOVE)  [{e['link_state']}]"),
        (e["facing"] < 5 or e["facing"] > 355, f"facing locked ~0  [{e['facing']:.1f}]"),
        (14.0 < e["v"] < 17.5, f"still sliding  [{e['v']:.2f}]"),
    ]),
    ("ebs", seq_ebs, "L released -> extended slide, slow bleed", lambda e: [
        (e["link_state"] == 6, f"state 6 (MOVE)  [{e['link_state']}]"),
        (16.0 < e["v"] < 17.0, f"speed preserved  [{e['v']:.2f}]"),
        (e["face_trav"] < 5, f"facing~travel aligned  [{e['face_trav']:.1f}]"),
    ]),
    ("face_left", seq_face_left, "facing DECOUPLES to ~90 while slide holds + speed preserved", lambda e: [
        (e["link_state"] == 6, f"state 6 (MOVE)  [{e['link_state']}]"),
        (abs(e["facing"] - 90.0) < 8, f"facing turned ~90  [{e['facing']:.1f}]"),
        (e["face_trav"] > 60, f"facing DECOUPLED from travel  [{e['face_trav']:.1f}]"),
        (e["v"] > 16.0, f"speed preserved  [{e['v']:.2f}]"),
    ]),
    ("brake_right", seq_brake_right, "ESS toward anti-cam brakes to a full stop", lambda e: [
        (e["link_state"] == 4, f"state 4 (idle/stopped)  [{e['link_state']}]"),
        (e["v"] < 0.5, f"|v|~0 braked  [{e['v']:.2f}]"),
    ]),
]


# LIVE-ONLY locks (no sim yet): the roll (FRONT_ROLL) tier -- immutable characteristic end-states,
# same as the ATN cases were pre-sim. Roll = state 30 for ~18 anim frames (const speed), then exits.
ROLL_SETTLE_POSZ = 1524.69   # full-run roll total pos_z at standstill (locked from advanceseq record)
LIVE_CASES = [
    ("roll_run", seq_roll_run, "full-run roll: state 30 at the 26 cap (mid-roll)", lambda e: [
        (e["link_state"] == 30, f"state 30 (FRONT_ROLL)  [{e['link_state']}]"),
        (abs(e["v"] - 26.0) < 0.05, f"roll speed at cap 26  [{e['v']:.3f}]"),
    ]),
    ("roll_slow", seq_roll_slow, "barely-moving roll: low speedF -> near the 5.0 floor (mid-roll)", lambda e: [
        (e["link_state"] == 30, f"state 30 (FRONT_ROLL)  [{e['link_state']}]"),
        (5.0 <= e["v"] < 8.0, f"roll speed near floor (speedF-scaled)  [{e['v']:.3f}]"),
    ]),
    ("roll_settle", seq_roll_settle, "full-run roll played to standstill: total distance + clean stop", lambda e: [
        (e["link_state"] == 4, f"state 4 (idle/stopped)  [{e['link_state']}]"),
        (e["v"] < 0.5, f"|v|~0 stopped  [{e['v']:.2f}]"),
        (abs(e["pos_z"] - ROLL_SETTLE_POSZ) < 0.5, f"roll distance pos_z~{ROLL_SETTLE_POSZ:.1f}  [{e['pos_z']:.2f}]"),
    ]),
    ("roll_ebs", seq_roll_ebs, "frame-perfect EBS out of a roll: 26 flipped/preserved as ~-23", lambda e: [
        (e["link_state"] == 6, f"state 6 (MOVE/EBS)  [{e['link_state']}]"),
        (abs(e["pot"] - (-23.109)) < 0.05, f"~-23 preserved (frame-perfect)  [{e['pot']:.3f}]"),
        (e["face_trav"] < 5, f"facing~travel aligned (EBS)  [{e['face_trav']:.1f}]"),
    ]),
]


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    record = o.get('record', '0') in ('1', 'true', 'yes')
    only = o.get('only')
    npass = nfail = 0
    for label, seqfn, note, extra_check in CASES:
        if only and only != label:
            continue
        sim, live = replay_sim_vs_live(seqfn())
        if record:
            e = {"link_state": int(live["link_state"]), "v": abs(live["potential_speed"]),
                 "facing": deg(live["shape_angle_y"]), "travel": deg(live["travel_angle"])}
            print(f"{label:<12} SIM st={sim.state} v={sim.nspeed:.3f} face={deg(sim.facing):.1f} "
                  f"trav={deg(sim.travel):.1f} pos_z={sim.pos_z:.2f}  | LIVE st={e['link_state']} "
                  f"v={live['potential_speed']:.3f} face={e['facing']:.1f} trav={e['travel']:.1f} "
                  f"pos_z={live['pos_z']:.2f}  # {note}")
            continue
        checks = sim_checks(sim, live, note)
        if extra_check is not None:              # layer the characteristic tech assertions on top
            e = {"link_state": int(live["link_state"]), "v": abs(live["potential_speed"]),
                 "facing": deg(live["shape_angle_y"]), "travel": deg(live["travel_angle"]),
                 "face_trav": abs(sdiff_deg(live["shape_angle_y"], live["travel_angle"]))}
            checks += extra_check(e)
        ok = all(c[0] for c in checks)
        npass += ok
        nfail += (not ok)
        print(f"{'PASS' if ok else 'FAIL'} {label:<12} (SIM-vs-LIVE: {note})")
        for passed, desc in checks:
            print(f"     {'ok ' if passed else 'X  '}{desc}")

    for label, seqfn, note, check in LIVE_CASES:   # roll tier: live-only locks (no sim yet)
        if only and only != label:
            continue
        e = replay_live(seqfn())
        if record:
            print(f"{label:<12} st={e['link_state']} pot={e['pot']:.3f} v={e['v']:.3f} "
                  f"face={e['facing']:.1f} trav={e['travel']:.1f} pos_z={e['pos_z']:.2f}  # {note}")
            continue
        checks = check(e)
        ok = all(c[0] for c in checks)
        npass += ok
        nfail += (not ok)
        print(f"{'PASS' if ok else 'FAIL'} {label:<12} (LIVE-LOCK: {note})")
        for passed, desc in checks:
            print(f"     {'ok ' if passed else 'X  '}{desc}")
    if not record:
        print(f"\n{npass} passed, {nfail} failed")
        sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
