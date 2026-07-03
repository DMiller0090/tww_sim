"""Live-behavior regression locks for LAND movement tech (brakeslide / EBS / facing).

There is no land SIM yet, so these are NOT sim-vs-live. Each case replays a fixed input
sequence from the land_flatwalk anchor via ONE race-free `advanceseq` and asserts the
GAME's characteristic END-STATE -- the *discovered tech*: clean run accel, the brakeslide
(L held -> targeting slide, facing locked), the EBS (L released -> extended slide), the
camera-relative speed preservation (ESS toward csangle holds speed ~forever; ESS toward
csangle+180 brakes to a stop), and the facing/travel DECOUPLING (facing turns while the
slide direction holds). They also guard the anchor + capture harness against drift.

Determinism: the anchor + inputs are fixed and advanceseq is race-free, so end-state is
reproducible and can be locked tight, exactly like the swim run_tests baselines. Upgrade
to sim-vs-live (or DTM-gold via run_dtm) once a land sim exists. These locks are the land
analogue of the immutable swim syncs -- do not loosen a check to make a run pass; a real
change means the tech (or anchor) changed, which is a finding, not a test edit.

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


# check(end) -> list of (ok, description) -- the LOCKED characteristic assertions per case.
CASES = [
    ("walk_run", seq_walk, "run to max then standstill", lambda e: [
        (e["link_state"] == 4, f"state 4 (idle)  [{e['link_state']}]"),
        (abs(e["pos_z"] - 1278.25) < 3.0, f"pos_z~1278.25  [{e['pos_z']:.2f}]"),
        (e["v"] < 0.5, f"|v|~0 stopped  [{e['v']:.2f}]"),
    ]),
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
