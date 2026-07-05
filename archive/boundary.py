"""Pin the (|v|, air) boundary of the wait=2 pump-transition anomaly (bug #2).

Controlled isolation: from the slot-10 slate, reach state-55 ESS cruise, then WRITE
the exact (potential_speed, air) test point, settle a few ESS frames, then do a lone
neu pump (neu, then ESS...) and count the wait frames (consecutive state-54 frames
before re-entry to 55). Sweeps air for each requested |v|.

Per-frame uses advancewith (race-free emu-thread path; no charge density here).

Usage: python boundary.py [v=780] [alo=490] [ahi=520] [slot=10] [settle=5]
   or  python boundary.py vsweep=600,700,780,850
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

ESS = dict(stickX=128, stickY=110, substickY=0, frames=1)
NEU = dict(stickX=128, stickY=128, substickY=0, frames=1)
CHG_U = dict(stickX=128, stickY=255, substickY=0, frames=1)
CHG_D = dict(stickX=128, stickY=0, substickY=0, frames=1)


def step(inp):
    D.control_pipe_quiet("advancewith", inp)
    return D.attach()


def measure(v, air, slot, settle):
    """Return (wait, anim_at_exit, v_at_exit, air_at_exit)."""
    D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
    h, m = step(NEU)
    # reach state 55 ESS cruise (entry tax: 1st ess stays 54)
    for _ in range(4):
        h, m = step(ESS)
    # write the exact test point now that we're cruising in 55
    import run_tests as R
    L.wnamed(h, m, "potential_speed", -abs(v)); L.wnamed(h, m, "air", int(air))
    # settle a few ess frames so the SWIMING anim reaches its cruise (strobo) phase
    for _ in range(settle):
        h, m = step(ESS)
    st = D.read_named(h, m, "link_state")
    if st != 55:
        return (-1, 0, 0, 0)  # never reached cruise
    ax = D.read_named(h, m, "air"); vx = D.read_named(h, m, "potential_speed")
    anx = D.read_named(h, m, "anim_frame")
    # lone neu pump: exit
    h, m = step(NEU)
    # now hold ESS and count consecutive state-54 frames before re-entry to 55
    wait = 0
    for _ in range(5):
        h, m = step(ESS)
        if D.read_named(h, m, "link_state") == 54:
            wait += 1
        else:
            break
    return (wait, anx, vx, ax)


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10')); settle = int(o.get('settle', '5'))
    alo, ahi = int(o.get('alo', '490')), int(o.get('ahi', '520'))
    vs = [int(x) for x in o['vsweep'].split(',')] if 'vsweep' in o else [int(o.get('v', '780'))]
    if 'phase' in o:
        # sweep exit-anim phase via settle count, holding air-at-exit ~constant by
        # pre-writing air = target + settle (each settle ess frame burns 1 air).
        v = int(o.get('v', '780')); aexit = int(o.get('aexit', '503'))
        print(f"# phase sweep |v|={v} air_exit~{aexit}")
        print("  settle  wait  anim_exit  v_exit  air_exit")
        for s in range(int(o.get('slo', '0')), int(o.get('phase', '24'))):
            wait, anx, vx, ax = measure(v, aexit + s, slot, s)
            tag = "  <-- WAIT2" if wait >= 2 else ""
            print(f"  {s:>5}  {wait:>5}  {anx:8.3f}  {vx:7.1f}  {ax:>4}{tag}")
        D.control_pipe_quiet("clearinput"); return
    print(f"# wait-frame boundary  airs {ahi}..{alo}  settle={settle}")
    for v in vs:
        print(f"## |v|={v}")
        print("  air   wait  anim     v_exit   air_exit")
        for air in range(ahi, alo - 1, -2):
            wait, anx, vx, ax = measure(v, air, slot, settle)
            tag = "  <-- flip" if wait >= 2 else ""
            print(f"  {air:>4}  {wait:>4}  {anx:7.3f}  {vx:8.2f}  {ax:>4}{tag}")
    D.control_pipe_quiet("clearinput")


if __name__ == "__main__":
    main()
