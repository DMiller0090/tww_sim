"""Isolate the EXIT-FROM-CHARGE case (handoff open residual #1).

Seed speed -> ESS warm+cruise -> a short CHARGE burst -> NEUTRAL exit straight
from the charge state -> hold neutral. Reads potential_speed (mNormalSpeed),
true_speed (speedF), stick_distance, link_state across the transition and
compares to superswim_sim.SwimState frame-by-frame.

The point: on the held-exit frame the stick is NEUTRAL (stickDist<=0.05), so the
decomp's setSpeedAndAngleSwim computes fVar1=0 and setNormalSpeedF takes the
cLib_addCalc branch -- it does NOT apply a charge gain. The sim currently applies
the preceding charge's pending gain on that frame. This harness shows the truth.

Low charge density (burst is short, speed is written) so input drops are rare.

Usage: python calib_chgexit.py [speed] [burst]
"""
import sys, struct
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)
import dolphin_mem as D
from superswim import sim as S

ESS=(128,110); NEU=(128,128); CHG_UP=(128,255); CHG_DN=(128,0)

def adv(sx,sy): D.control_pipe_quiet("advancewith",{"stickX":sx,"stickY":sy,"substickY":0,"frames":1})
def wn(h,m,n,v):
    e=D.NAMED_ADDRS[n];a=D.resolve_chain(h,m,e["base"],e["offsets"]);t=e["type"];fmt,sz=D.FMT[t]
    d=struct.pack(fmt,float(v)) if t in("f32","f64") else struct.pack(">"+{1:"B",2:"H",4:"I",8:"Q"}[sz],int(v)&((1<<(sz*8))-1))
    D.write_bytes(h,m,a,d)
def r(h,m,n): return D.read_named(h,m,n)

def run(speed, burst, cruiseN=6, holdN=4):
    D.cmd_control_pipe("savestate",{"action":"load","slot":10})
    h,m=D.attach(); adv(*NEU); h,m=D.attach()
    wn(h,m,"air",900); wn(h,m,"potential_speed",speed)
    sim=S.SwimState(v=r(h,m,"potential_speed"),anim=r(h,m,"anim_frame"),air=r(h,m,"air"))
    sim.state=54; sim._entry_tax=False
    # 1-lag ESS entry + cruise, charge burst, then neutral exit-from-charge + hold
    acts=['ess']*(1+cruiseN)+['chg']*burst+['neu']*(1+holdN)
    chg_i=0; rows=[]
    for i,a in enumerate(acts,1):
        if a=='chg':
            adv(*(CHG_UP if chg_i%2==0 else CHG_DN)); chg_i+=1
        elif a=='ess': adv(*ESS)
        else: adv(*NEU)
        sim.step(a)
        rows.append((i,a,
                     r(h,m,"potential_speed"), sim.v,
                     r(h,m,"true_speed"),
                     r(h,m,"anim_frame"), sim.anim,
                     r(h,m,"stick_distance"),
                     r(h,m,"link_state"), sim.state))
    return rows, burst, cruiseN

def show(label, rows, burst, cruiseN):
    print(f"\n=== {label} ===")
    print("f   act | pot_live  pot_sim   d_pot | true_live | an_live  an_sim | sd    | st L/S")
    exit_f = 1+cruiseN+burst+1   # the held-exit frame (state 55 -> schedules 54)
    for (i,a,pl,ps,tl,al,ans,sd,st,sts) in rows:
        mark=""
        if i==1+cruiseN+burst: mark=" <-- last charge"
        elif i==exit_f: mark=" <-- EXIT frame (neutral stick)"
        print(f"{i:<3} {a:<3} | {pl:8.3f} {ps:8.3f} {pl-ps:+6.3f} | {tl:9.3f} | {al:7.3f} {ans:7.3f} | {sd:5.3f} | {st}/{sts}{mark}")

if __name__=="__main__":
    speed=float(sys.argv[1]) if len(sys.argv)>1 else -600.0
    burst=int(sys.argv[2]) if len(sys.argv)>2 else 3
    rows,b,c=run(speed,burst)
    show(f"EXIT-FROM-CHARGE  speed={speed} burst={burst}", rows, b, c)
    D.cmd_control_pipe("clearinput")
