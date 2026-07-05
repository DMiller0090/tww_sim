import struct, math
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)
import dolphin_mem as D
from superswim import sim as S
ESS=(128,110); NEU=(128,128)
def adv(sx,sy): D.control_pipe_quiet("advancewith",{"stickX":sx,"stickY":sy,"substickY":0,"frames":1})
def r(h,m,n): return D.read_named(h,m,n)
def wnamed(h,m,name,value):
    e=D.NAMED_ADDRS[name]; addr=D.resolve_chain(h,m,e["base"],e["offsets"])
    t=e["type"]; fmt,sz=D.FMT[t]
    data=struct.pack(fmt,float(value)) if t in("f32","f64") else struct.pack(">"+{1:"B",2:"H",4:"I",8:"Q"}[sz],int(value)&((1<<(sz*8))-1))
    D.write_bytes(h,m,addr,data)
for alpha in [0,10,20]:
    D.cmd_control_pipe("savestate",{"action":"load","slot":10})
    h,m=D.attach(); adv(*NEU); h,m=D.attach()
    wnamed(h,m,"air",900); wnamed(h,m,"potential_speed",-120.0)
    for _ in range(6): adv(*ESS)
    chain=S.reorient_chain(90.0,0.0,270.0) or []
    for sx,sy in chain: adv(sx,sy)
    pair=S.arrow_sticks(alpha,True)
    vs=[]; faces=[]
    for i in range(16):
        adv(*pair[i%2])
        vs.append(r(h,m,"potential_speed")); faces.append(r(h,m,"facing")*360.0/65536.0)
    # steady gains = consecutive dv over last frames
    gains=[vs[i+1]-vs[i] for i in range(len(vs)-1)]
    steady=gains[-6:]
    snapdelta=abs(((faces[-1]-faces[-2]+180)%360)-180)
    g=sum(steady)/len(steady)
    print(f"alpha={alpha:2}  steady dv/fr={g:7.3f}  snapdelta(live)~{snapdelta:6.1f}  "
          f"3cos(d)={3*math.cos(math.radians(snapdelta)):6.3f}  "
          f"impl_dist={g/(3*math.cos(math.radians(snapdelta))):6.4f}")
    D.cmd_control_pipe("clearinput")
