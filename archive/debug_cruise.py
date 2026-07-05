"""Isolate the cruise/neutral-dash model error from the prefix anim-seed error.

Runs the full front-end prefix live (to reach a real state-55 hand-off), then for the
CRUISE suffix steps the live game and TWO SwimStates in parallel:
  - sim_plan: seeded from the PLANNER's predicted hand-off (v,anim,air)
  - sim_live: seeded from the LIVE hand-off (v,anim,air) read off the game
both replaying the SAME cruise action sequence. If sim_live tracks live but sim_plan
doesn't, the cruise model is correct and the residual is purely the prefix anim drift.

Usage: python debug_cruise.py [v=-120] [air=900] [dest=20000] [slot=10]
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
from tests.dolphin.spotcheck_frontend import build_sticks, adv, wnamed, r, ESS, NEU, SETTLE


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

    plan = P.plan_with_frontend(dest, v0, anim0, air0, facing0=facing0,
                                target_bearing=180.0, cam_deg=cam, verbose=False)
    seq = build_sticks(plan, facing0, cam)
    x0 = r(h, mem1, "link_x")
    n_pref = plan['prefix_frames']

    # replay the PREFIX live (no parallel sim needed here)
    for stick, tag in seq[:n_pref]:
        adv(*stick)
    # hand-off: live values
    lv = r(h, mem1, "potential_speed"); lan = r(h, mem1, "anim_frame")
    lair = r(h, mem1, "air"); lprog = -(r(h, mem1, "link_x") - x0)
    pv, pan, pair = plan['prefix_end']
    print(f"hand-off  live: v={lv:.2f} anim={lan:.3f} air={lair} prog={lprog:.0f}")
    print(f"          plan: v={pv:.2f} anim={pan:.3f} air={pair} prog(pred)={plan['progress']:.0f}")

    sim_plan = S.SwimState(v=pv, anim=pan, air=pair)
    sim_live = S.SwimState(v=lv, anim=lan, air=lair)
    cruise_acts = plan['cruise']['actions']
    xh = r(h, mem1, "link_x")          # progress origin at hand-off
    print("\nf    act  | live: prog    v      an   | simLIVE prog  v      an  | simPLAN prog  v      an")
    for i, a in enumerate(seq[n_pref:], 1):
        stick, tag = a
        sim_live.step(cruise_acts[i - 1]); sim_plan.step(cruise_acts[i - 1])
        adv(*stick)
        prog = -(r(h, mem1, "link_x") - xh)
        vl = r(h, mem1, "potential_speed"); an = r(h, mem1, "anim_frame")
        spl = -(sim_live.x); spp = -(sim_plan.x)
        if i % 10 == 0 or i == len(cruise_acts):
            print(f"{i:<3} {cruise_acts[i-1]:<4} | {prog:7.0f} {vl:8.1f} {an:5.2f} "
                  f"| {spl:7.0f} {sim_live.v:8.1f} {sim_live.anim:5.2f} "
                  f"| {spp:7.0f} {sim_plan.v:8.1f} {sim_plan.anim:5.2f}")
    print(f"\ncruise: live={prog:.0f}  simLIVE={spl:.0f} ({100*spl/prog:.1f}%)  "
          f"simPLAN={spp:.0f} ({100*spp/prog:.1f}%)")
    D.cmd_control_pipe("clearinput")


if __name__ == "__main__":
    main()
