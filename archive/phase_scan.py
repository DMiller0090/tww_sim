"""For each lone-neu pump in the fixture, log the SWIMING anim phase on the neu
frame (state-55, just before exit) vs the measured wait-frame count. Isolates the
real gate (SWIMING anim phase at exit) with no air/cadence confound -- each pump is
measured in its own natural fixture context.

Usage: python phase_scan.py [seq=test_pumptrans_seq.txt] [slot=10]
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


def step(inp):
    D.control_pipe_quiet("advancewith", inp); return D.attach()


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10'))
    acts = A.expand(open(o.get('seq', 'test_pumptrans_seq.txt')).read())
    seq = A.acts_to_seq(acts); N = len(acts)
    lone = [i + 1 for i in range(1, N - 1)
            if acts[i] == 'neu' and acts[i - 1] != 'neu' and acts[i + 1] != 'neu']
    print(f"# {len(lone)} lone-neu pumps. SWIMING anim@neu (state55) vs wait")
    print("  neu@  swiming_anim  v       air  wait")
    for n in lone:
        D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
        h, m = step(dict(stickX=128, stickY=128, substickY=0, frames=1))
        L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
        # replay to the neu frame n (1-indexed) -> read SWIMING anim ON the neu frame
        D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq[:n]}); h, m = D.attach()
        st = D.read_named(h, m, "link_state")
        anim = D.read_named(h, m, "anim_frame"); v = D.read_named(h, m, "potential_speed")
        air = D.read_named(h, m, "air")
        # continue with the fixture's post-neu inputs; count consecutive 54s
        wait = 0
        for j in range(n, min(n + 5, N)):
            h, m = step({"stickX": seq[j]["stickX"], "stickY": seq[j]["stickY"],
                         "substickY": 0, "frames": 1})
            if D.read_named(h, m, "link_state") == 54:
                wait += 1
            else:
                break
        tag = "  <-- WAIT2" if wait >= 2 else ""
        print(f"  {n:<4}  {anim:11.4f}  {v:7.1f}  {air:>3}  {wait}{tag}")
    D.control_pipe_quiet("clearinput")


if __name__ == "__main__":
    main()
