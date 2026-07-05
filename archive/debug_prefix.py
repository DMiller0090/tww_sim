"""Parallel live-vs-ArrowState replay of the front-end PREFIX only, to localize where
the prefix progress / anim diverges. Steps the live game and a sim ArrowState through the
IDENTICAL stick sequence (reorient-in + arrow ramp + reorient-out + settle) and prints
both progress(-x), z, v, anim, facing each frame.

Usage: python debug_prefix.py [v=-120] [air=900] [dest=20000] [slot=10]
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
from superswim import sim as S
from superswim import plan as P

ESS = (128, 110); NEU = (128, 128); SETTLE = 6


def adv(sx, sy):
    D.control_pipe_quiet("advancewith", {"stickX": sx, "stickY": sy,
                                         "substickY": 0, "frames": 1})


def wnamed(h, mem1, name, value):
    e = D.NAMED_ADDRS[name]; addr = D.resolve_chain(h, mem1, e["base"], e["offsets"])
    t = e["type"]; fmt, sz = D.FMT[t]
    data = (struct.pack(fmt, float(value)) if t in ("f32", "f64")
            else struct.pack(">" + {1: "B", 2: "H", 4: "I", 8: "Q"}[sz],
                             int(value) & ((1 << (sz * 8)) - 1)))
    D.write_bytes(h, mem1, addr, data)


def r(h, mem1, name):
    return D.read_named(h, mem1, name)


def main():
    opts = {}
    for tok in sys.argv[1:]:
        k, _, val = tok.partition('='); opts[k] = val
    v = float(opts.get('v', '-120')); air_seed = int(opts.get('air', '900'))
    dest = float(opts.get('dest', '20000')); slot = int(opts.get('slot', '10'))

    D.cmd_control_pipe("savestate", {"action": "load", "slot": slot})
    h, mem1 = D.attach(); adv(*NEU); h, mem1 = D.attach()
    wnamed(h, mem1, "air", air_seed); wnamed(h, mem1, "potential_speed", v)
    for _ in range(SETTLE):
        adv(*ESS)
    v0 = r(h, mem1, "potential_speed"); anim0 = r(h, mem1, "anim_frame")
    air0 = r(h, mem1, "air")
    facing0 = r(h, mem1, "facing") * 360.0 / 65536.0
    cam = r(h, mem1, "csangle") * 360.0 / 65536.0
    print(f"start: v={v0:.2f} anim={anim0:.3f} air={air0} facing={facing0:.0f} cam={cam:.0f}")

    plan = P.plan_with_frontend(dest, v0, anim0, air0, facing0=facing0,
                                target_bearing=180.0, cam_deg=cam, verbose=False)
    # Build prefix sticks (mirror frontend_prefix EXACTLY)
    axis = (cam - 180.0 - 90.0) % 360.0
    cruise_f = (cam - 180.0) % 360.0
    chain_in = S.reorient_chain(facing0, axis, cam) or []
    sched = plan['schedule']
    sim = S.ArrowState(v=v0, anim=anim0, air=air0, facing_deg=facing0, cam_deg=cam)
    seq = [(s, 'R-in') for s in chain_in]
    sim_rows = []
    # build full prefix stick list while replaying sim
    for sx, sy in chain_in:
        sim.step(sx, sy)
    for i, a in enumerate(sched):
        pair = S.arrow_sticks(a, drift_down=P.ARROW_DRIFT_DOWN)
        seq.append((pair[i % 2], f'arw{a:.0f}'))
        sim.step(*pair[i % 2])
    settled = sim._pending_facing if sim._pending_facing is not None else sim.facing
    chain_out = S.reorient_chain(settled, cruise_f, cam) or []
    for s2 in chain_out:
        seq.append((s2, 'R-out'))
    seq.append((ESS, 'settle'))

    # now replay sim FRESH alongside live, recording per frame
    sim = S.ArrowState(v=v0, anim=anim0, air=air0, facing_deg=facing0, cam_deg=cam)
    x0 = r(h, mem1, "link_x"); z0 = r(h, mem1, "link_z")
    sx0, sz0 = sim.x, sim.z
    print("\nf   tag     | live: face  prog    z      v      an   | sim: face  prog    z      v      an")
    for i, (stick, tag) in enumerate(seq, 1):
        # sim step
        if i <= len(chain_in):
            pass
        sim.step(*stick)
        sim_prog = -(sim.x - sx0); sim_z = sim.z - sz0
        # live step
        adv(*stick)
        face = r(h, mem1, "facing") * 360.0 / 65536.0
        vl = r(h, mem1, "potential_speed"); an = r(h, mem1, "anim_frame")
        x = r(h, mem1, "link_x"); z = r(h, mem1, "link_z")
        prog = -(x - x0); zoff = z - z0
        print(f"{i:<3} {tag:<7} | {face:6.0f} {prog:7.0f} {zoff:+6.0f} {vl:8.1f} {an:5.2f} "
              f"| {sim.facing:6.0f} {sim_prog:7.0f} {sim_z:+6.0f} {sim.v:8.1f} {sim.anim:5.2f}")
    print(f"\nprefix end: live prog={prog:.0f} z={zoff:.0f} v={vl:.1f} an={an:.2f}  | "
          f"sim prog={sim_prog:.0f} v={sim.v:.1f} an={sim.anim:.2f}")
    print(f"plan prefix progress pred={plan['progress']:.0f}")
    D.cmd_control_pipe("clearinput")


if __name__ == "__main__":
    main()
