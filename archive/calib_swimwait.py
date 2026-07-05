"""Calibrate the parallel SWIMWAIT controller's advance rate during STATE 55 (ESS).

Theory (HANDOFF): the post-exit neutral display anim is NOT a function of the
pre-exit SWIMING anim. It comes from a SWIMWAIT controller that runs in parallel
the whole swim. During state 54 it advances at neutral_anim_rate(air). During
state 55 (ESS) it advances at some rate r55 we must measure here.

Method: fix the entry sequence (so SWIMWAIT-at-entry is identical every run),
vary K = number of ESS-hold frames, exit to neutral, read the post-exit neutral
display anim. post_exit_anim(K) reveals r55.

Usage: python calib_swimwait.py [speed] [Kmax]
"""
import sys, struct, math
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)
import dolphin_mem as D

def loadstate(slot):
    D.cmd_control_pipe("savestate", {"action": "load", "slot": slot})

def adv(h, mem1, sx, sy):
    D.control_pipe_quiet("advancewith", {"stickX": sx, "stickY": sy,
                                         "substickY": 0, "frames": 1})

def wnamed(h, mem1, name, value):
    e = D.NAMED_ADDRS[name]
    addr = D.resolve_chain(h, mem1, e["base"], e["offsets"])
    t = e["type"]; fmt, sz = D.FMT[t]
    if t in ("f32", "f64"):
        data = struct.pack(fmt, float(value))
    else:
        data = struct.pack(">" + {1:"B",2:"H",4:"I",8:"Q"}[sz],
                           int(value) & ((1 << (sz*8)) - 1))
    D.write_bytes(h, mem1, addr, data)

def r(h, mem1, name):
    return D.read_named(h, mem1, name)

def nfmod(a, n):
    return a - math.floor(a / n) * n

ESS = (128, 110)
NEU = (128, 128)

def seed(h, mem1, speed):
    wnamed(h, mem1, "air", 900)
    wnamed(h, mem1, "potential_speed", speed)
    return r(h, mem1, "potential_speed"), r(h, mem1, "air"), r(h, mem1, "link_state")

# Settle frames in neutral before entering ESS (fixes SWIMWAIT-at-entry).
SETTLE = 2

def run_K(speed, K, verbose=False):
    """Returns dict with the post-exit neutral anim trace for a K-frame ESS hold."""
    loadstate(10)
    h, mem1 = D.attach()
    adv(h, mem1, *NEU)            # settle 1 frame in neutral after loadstate
    h, mem1 = D.attach()         # re-attach
    seed(h, mem1, speed)
    # fixed settle in neutral
    for _ in range(SETTLE):
        adv(h, mem1, *NEU)
    anim_preEntry = r(h, mem1, "anim_frame")    # SWIMWAIT display just before entry input
    # ENTER ESS: input ESS. Transition lags 1 frame (input frame = s54, next = s55).
    swiming = []
    states_in = []
    for i in range(K):
        adv(h, mem1, *ESS)
        swiming.append(r(h, mem1, "anim_frame"))
        states_in.append(r(h, mem1, "link_state"))
    air_atExit = r(h, mem1, "air")
    v_atExit = r(h, mem1, "potential_speed")
    # EXIT to neutral: input NEU. Read several frames of post-exit display anim.
    post = []
    states_out = []
    for i in range(6):
        adv(h, mem1, *NEU)
        post.append(r(h, mem1, "anim_frame"))
        states_out.append(r(h, mem1, "link_state"))
    return {
        "K": K, "anim_preEntry": anim_preEntry, "swiming": swiming,
        "states_in": states_in, "post": post, "states_out": states_out,
        "air_atExit": air_atExit, "v_atExit": v_atExit,
    }

def main():
    speed = float(sys.argv[1]) if len(sys.argv) > 1 else -800.0
    Kmax = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    print(f"# SWIMWAIT calib speed={speed} SETTLE={speed and SETTLE}")
    print(f"# states_in / states_out show the 1-frame transition lag")
    rows = []
    for K in range(2, Kmax + 1):
        d = run_K(speed, K)
        rows.append(d)
        print(f"\nK={K} preEntry={d['anim_preEntry']:.5f} "
              f"air@exit={d['air_atExit']} v@exit={d['v_atExit']:.2f}")
        print(f"  states_in ={d['states_in']}")
        print(f"  swiming   =" + " ".join(f"{x:.4f}" for x in d['swiming']))
        print(f"  states_out={d['states_out']}")
        print(f"  post      =" + " ".join(f"{x:.5f}" for x in d['post']))
    # Summary table: pick the first post-exit frame that is truly in state 54
    print("\n# SUMMARY  K  preEntry  firstNeutAnim(state54)  air@exit")
    for d in rows:
        neut = None
        for a, st in zip(d['post'], d['states_out']):
            if st == 54:
                neut = a; break
        print(f"{d['K']}\t{d['anim_preEntry']:.5f}\t"
              f"{('%.5f'%neut) if neut is not None else 'NA'}\t{d['air_atExit']}")
    D.cmd_control_pipe("clearinput")

if __name__ == "__main__":
    main()
