"""Isolate the WARM pump entry scramble for ESS re-entry vs CHARGE re-entry.

Identical preamble (seed speed -> ESS warm+cruise -> neu exit -> hold neutral),
then re-enter via ESS in one run and via CHG in another, read the post-scramble
anim full precision. No dense charging (speed is written), so no input drops.

Usage: python calib_pumpentry.py [speed]
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

ESS=(128,110); NEU=(128,128); CHG_UP=(128,255); CHG_DN=(128,0)

def adv(sx,sy): D.control_pipe_quiet("advancewith",{"stickX":sx,"stickY":sy,"substickY":0,"frames":1})
def wn(h,m,n,v):
    e=D.NAMED_ADDRS[n];a=D.resolve_chain(h,m,e["base"],e["offsets"]);t=e["type"];fmt,sz=D.FMT[t]
    d=struct.pack(fmt,float(v)) if t in("f32","f64") else struct.pack(">"+{1:"B",2:"H",4:"I",8:"Q"}[sz],int(v)&((1<<(sz*8))-1))
    D.write_bytes(h,m,a,d)
def r(h,m,n): return D.read_named(h,m,n)

def run(speed, entry, holdN=3, cruiseN=6):
    """entry in {'ess','chg'}. Returns (preamble rows, scramble frame data)."""
    D.cmd_control_pipe("savestate",{"action":"load","slot":10})
    h,m=D.attach(); adv(*NEU); h,m=D.attach()
    wn(h,m,"air",900); wn(h,m,"potential_speed",speed)
    sim=S.SwimState(v=r(h,m,"potential_speed"),anim=r(h,m,"anim_frame"),air=r(h,m,"air"))
    sim.state=54; sim._entry_tax=False
    acts=['ess']*(1+cruiseN)+['neu']*(1+holdN)         # enter ESS (1 lag +cruise), exit+hold
    acts+=[entry,entry,entry]                          # re-enter (lag + scramble + settle)
    chg_i=0; rows=[]
    for i,a in enumerate(acts,1):
        if a=='chg':
            adv(*(CHG_UP if chg_i%2==0 else CHG_DN)); chg_i+=1   # chg#1=UP (match replay/sim)
        elif a=='ess': adv(*ESS)
        else: adv(*NEU)
        sim.step(a)
        al=r(h,m,"anim_frame"); vl=r(h,m,"potential_speed"); air=r(h,m,"air"); st=r(h,m,"link_state")
        rows.append((i,a,vl,sim.v,al,sim.anim,air,sim.air,st,sim.state))
    return rows

def show(label, rows):
    print(f"\n=== {label} ===")
    print("f   act | v_live    v_sim    | an_live(raw)  an_sim   | air L/S | st L/S")
    n=len(rows)
    for (i,a,vl,vs,al,ans,air,airs,st,sts) in rows:
        mark=" <-- scramble" if i==n-1 else (" <-- entry-trigger" if i==n-2 else "")
        print(f"{i:<3} {a:<3} | {vl:8.3f} {vs:8.3f} | {al:11.4f} {ans:8.4f} | {air}/{airs} | {st}/{sts}{mark}")

if __name__=="__main__":
    speed=float(sys.argv[1]) if len(sys.argv)>1 else -300.0
    show("ESS re-entry", run(speed,'ess'))
    show("CHG re-entry", run(speed,'chg'))
    D.cmd_control_pipe("clearinput")
