"""LAND-movement regression: walk_run is SIM-vs-LIVE; the other 4 are live-behavior locks.

`walk_run` is the first LAND sim-vs-live gate (the swim run_tests analogue): it seeds a
`superswim.land.LandState` from the live frame-0 snapshot, steps the sim over the walk seq,
and compares the END potential_speed / state / position against the game replayed via one
race-free `advanceseq`. potential_speed (mNormalSpeed) and the state machine are BIT-EXACT;
position is a CALIBRATED foot-plant stand-in (see superswim/land.py) so it is checked to a
+-3 tolerance, not to the ULP.

The other 4 (brakeslide / EBS / facing decouple / brake) are still LIVE-BEHAVIOR LOCKS -- no
sim yet (they need the ATN_MOVE proc + the facing/travel decouple, the next tier). Each
replays a fixed input burst from the land_flatwalk anchor and asserts the GAME's
characteristic END-STATE (the discovered tech: L-held targeting slide with facing locked;
L-released extended slide; camera-relative speed preservation; facing/travel decouple). They
also guard the anchor + capture harness against drift.

Determinism: the anchor + inputs are fixed and advanceseq is race-free, so end-state is
reproducible and can be locked tight, exactly like the swim run_tests baselines. These locks
are the land analogue of the immutable swim syncs -- do not loosen a check to make a run
pass; a real change means the tech (or anchor) changed, which is a finding, not a test edit.

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
         "travel_angle", "csangle", "pos_x", "pos_z"]


def hold(sx, sy, n, buttons=0, triggerL=0):
    """n one-frame advanceseq elements at (sx,sy), C-stick full down (free cam)."""
    return [{"stickX": sx, "stickY": sy, "substickX": 128, "substickY": 0,
             "buttons": buttons, "triggerL": triggerL, "frames": 1} for _ in range(n)]


L_DOWN = hold(128, 0, 1, buttons=0x40, triggerL=255)   # L-target + full down, 1 frame

# --- the discovered sequences ---------------------------------------------------------
def seq_walk():        return hold(128, 255, 30) + hold(128, 128, 20)                  # run -> standstill
def seq_brakeslide():  return hold(128, 255, 10) + L_DOWN + hold(128, 110, 10, 0x40, 255)  # L HELD -> targeting slide
def seq_ebs():         return hold(128, 255, 10) + L_DOWN + hold(128, 110, 30)          # L released -> extended slide
def seq_face_left():   return hold(128, 255, 10) + L_DOWN + hold(128, 110, 1) + hold(110, 128, 60)
def seq_brake_right(): return hold(128, 255, 10) + L_DOWN + hold(128, 110, 1) + hold(146, 128, 60)


def deg(a):
    return (int(a) % 65536) * 360.0 / 65536.0


def sdiff_deg(a, b):
    d = (int(a) - int(b)) % 65536
    if d > 32768:
        d -= 65536
    return d * 360.0 / 65536.0


def replay(seq):
    D.control_pipe_quiet("clearinput")   # persistent override would leak a stale button
    D.control_pipe_quiet("savestate", {"action": "load", "path": ANCHOR.replace('\\', '/')})
    h, m = D.attach()
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq})
    h, m = D.attach()
    e = {k: D.read_named(h, m, k) for k in READS}
    e["v"] = abs(e["potential_speed"])
    e["facing"] = deg(e["shape_angle_y"])
    e["travel"] = deg(e["travel_angle"])
    e["face_trav"] = abs(sdiff_deg(e["shape_angle_y"], e["travel_angle"]))
    return e


def replay_sim_vs_live(seq):
    """SIM-vs-LIVE for the walk. Load the anchor, read the resting frame-0 seed, seed a
    LandState, step it over the seq, and replay the same seq live via one advanceseq.
    Returns (sim_state, live_end) for comparison. Mirrors swim run_tests.run_one.

    NOTE: read the seed DIRECTLY after loadstate (no settle frame). A stray `advancewith`
    neutral frame before the advanceseq perturbs the live walk by ~5 units (advancewith vs
    advanceseq pipe artifact -- bug#2); the clean advanceseq-from-load result is 1278.25."""
    D.control_pipe_quiet("clearinput")
    D.control_pipe_quiet("savestate", {"action": "load", "path": ANCHOR.replace('\\', '/')})
    h, m = D.attach()
    seed = {k: D.read_named(h, m, k) for k in READS}   # anchor's deterministic rest state
    sim = LandState(pos_z=seed["pos_z"], facing=int(seed["shape_angle_y"]),
                    travel=int(seed["travel_angle"]), csangle=int(seed["csangle"]),
                    state=int(seed["link_state"]), nspeed=seed["potential_speed"])
    for el in seq:                                # C-stick full down => free cam, csangle 0
        for _ in range(el.get("frames", 1)):
            sim.step(el["stickX"], el["stickY"])
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq})
    h, m = D.attach()
    live = {k: D.read_named(h, m, k) for k in READS}
    return sim, live


# SIM-vs-LIVE checks for walk_run: potential_speed (mNormalSpeed) + state are BIT-EXACT
# (tight tol); position is the calibrated foot-plant stand-in (+-3, see superswim/land.py).
def walk_checks(sim, live):
    dv = abs(sim.nspeed - live["potential_speed"])
    return [
        (sim.state == int(live["link_state"]),
         f"state sim/live {sim.state}/{int(live['link_state'])} (both idle 4)"),
        (dv <= 0.02, f"potential_speed bit-exact  dv={dv:.5f}  "
                     f"(sim {sim.nspeed:.3f} / live {live['potential_speed']:.3f})"),
        (abs(sim.pos_z - live["pos_z"]) < 3.0,
         f"pos_z within 3 (calibrated)  sim {sim.pos_z:.2f} / live {live['pos_z']:.2f}"),
    ]


# check(end) -> list of (ok, description) -- the LOCKED characteristic assertions per case.
# walk_run is SIM-vs-LIVE (handled specially in main via walk_checks); the rest are live locks.
CASES = [
    ("walk_run", seq_walk, "SIM-vs-LIVE: run accel to cap 17 then decel to standstill", None),
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


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    record = o.get('record', '0') in ('1', 'true', 'yes')
    only = o.get('only')
    npass = nfail = 0
    for label, seqfn, note, check in CASES:
        if only and only != label:
            continue
        if check is None:                        # walk_run: SIM-vs-LIVE
            sim, live = replay_sim_vs_live(seqfn())
            if record:
                print(f"{label:<12} SIM st={sim.state} v={sim.nspeed:.3f} pos_z={sim.pos_z:.2f}  "
                      f"| LIVE st={int(live['link_state'])} v={live['potential_speed']:.3f} "
                      f"pos_z={live['pos_z']:.2f}  # {note}")
                continue
            checks = walk_checks(sim, live)
        else:                                    # live-behavior lock
            end = replay(seqfn())
            if record:
                print(f"{label:<12} st={end['link_state']} v={end['v']:.3f} "
                      f"face={end['facing']:.1f} trav={end['travel']:.1f} "
                      f"face-trav={end['face_trav']:.1f} pos=({end['pos_x']:.1f},{end['pos_z']:.1f})  # {note}")
                continue
            checks = check(end)
        ok = all(c[0] for c in checks)
        npass += ok
        nfail += (not ok)
        print(f"{'PASS' if ok else 'FAIL'} {label:<12} ({note})")
        for passed, desc in checks:
            print(f"     {'ok ' if passed else 'X  '}{desc}")
    if not record:
        print(f"\n{npass} passed, {nfail} failed")
        sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
