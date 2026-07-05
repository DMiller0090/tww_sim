"""Sample wait vs SWIMING anim phase in the NATURAL cruise: replay the fixture to
frame K (cruise ESS, state 55), inject a lone neu pump, count wait frames. Sweep K
so the exit anim phase drifts finely (strobo ~-0.3/frame) -- maps the anim window
that triggers wait=2, in the real (v,air) regime, no artificial settle.

Usage: python phase_inject.py [klo=378] [khi=396] [slot=10]
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


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10'))
    klo, khi = int(o.get('klo', '378')), int(o.get('khi', '396'))
    asets = [int(x) for x in o['aset'].split(',')] if 'aset' in o else [None]
    acts = A.expand(open(o.get('seq', 'test_pumptrans_seq.txt')).read())
    seq = A.acts_to_seq(acts)
    print("# inject lone-neu pump after cruise frame K; aset=override air before pump")
    print("    K  anim@K   v@K    aset  air  st  wait")
    for K in range(klo, khi + 1):
        for aset in asets:
            D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
            h, m = step(NEU)
            L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
            D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq[:K]}); h, m = D.attach()
            st = D.read_named(h, m, "link_state")
            anim = D.read_named(h, m, "anim_frame"); v = D.read_named(h, m, "potential_speed")
            if aset is not None:
                L.wnamed(h, m, "air", int(aset))
            air = D.read_named(h, m, "air")
            h, m = step(NEU)          # inject the pump (exit next)
            wait = 0
            for _ in range(5):
                h, m = step(ESS)
                if D.read_named(h, m, "link_state") == 54:
                    wait += 1
                else:
                    break
            tag = "  <-- WAIT2" if wait >= 2 else ""
            asv = aset if aset is not None else 0
            print(f"  {K:>3}  {anim:7.3f}  {v:7.1f}  {asv:>4}  {air:>3}  {st}  {wait}{tag}")
    D.control_pipe_quiet("clearinput")


if __name__ == "__main__":
    main()
