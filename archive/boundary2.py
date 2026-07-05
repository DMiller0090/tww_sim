"""Pin the air boundary of bug#2 by perturbing ONLY air at the natural f395 pump.

Replay the fixture prefix to `pre` (default 394, last ESS before the neu@395 pump,
state-55 cruise), WRITE air=A, then continue the fixture's own remaining inputs and
count the wait frames of the neu@395 pump. This holds |v|, anim phase, and the pump
cadence at their natural fixture values and varies ONLY air -> isolates the air gate.

Usage: python boundary2.py [alo=496] [ahi=560] [pre=394] [npump=395] [slot=10]
"""
import sys
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)
import dolphin_mem as D
from superswim import actions as A
from harness import live as L

ESS = dict(stickX=128, stickY=110, substickY=0, frames=1)
NEU = dict(stickX=128, stickY=128, substickY=0, frames=1)


def step(inp):
    D.control_pipe_quiet("advancewith", inp); return D.attach()


def measure(air, pre, npump, seq, slot):
    D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
    h, m = step(NEU)
    L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
    # replay prefix up to `pre` frames (1-indexed frame `pre`)
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq[:pre]}); h, m = D.attach()
    L.wnamed(h, m, "air", int(air))
    vx = D.read_named(h, m, "potential_speed"); anx = D.read_named(h, m, "anim_frame")
    stx = D.read_named(h, m, "link_state")
    # frame pre+1 .. npump are the inputs leading into and incl the neu pump.
    # Replay through the neu (frame npump), then the exit lands at npump+1.
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq[pre:npump]}); h, m = D.attach()
    # exit frame
    h, m = step(ESS)  # actually next fixture input; use ESS (fixture is ess after neu)
    wait = 0
    if D.read_named(h, m, "link_state") == 54:
        wait = 1
        for _ in range(4):
            h, m = step(ESS)
            if D.read_named(h, m, "link_state") == 54:
                wait += 1
            else:
                break
    return wait, vx, anx, stx, D.read_named(h, m, "air")


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10'))
    pre = int(o.get('pre', '394')); npump = int(o.get('npump', '395'))
    alo, ahi = int(o.get('alo', '496')), int(o.get('ahi', '560'))
    acts = A.expand(open(o.get('seq', 'test_pumptrans_seq.txt')).read())
    seq = A.acts_to_seq(acts)
    print(f"# air-only boundary at fixture pump neu@{npump} (pre={pre}, v/anim/cadence natural)")
    print("  air_set  wait  v@pre   anim@pre  st@pre")
    for air in range(ahi, alo - 1, -2):
        wait, vx, anx, stx, _ = measure(air, pre, npump, seq, slot)
        tag = "  <-- WAIT2" if wait >= 2 else ""
        print(f"  {air:>6}  {wait:>4}  {vx:7.1f}  {anx:7.3f}  {stx}{tag}")
    D.control_pipe_quiet("clearinput")


if __name__ == "__main__":
    main()
