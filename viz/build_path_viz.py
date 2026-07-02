import json, math
import os, sys  # >>> repo bootstrap: locate superswim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)

from superswim import sim as S
from superswim import actions as A
from viz.gen_viz_data import runs


def trace(acts):
    seed = S.SwimState(v=0.0, anim=0.06392288208007812, air=900)
    seed.state = 54; seed._entry_tax = False
    st = seed.clone()
    rows = []
    for a in acts:
        d, tag = st.step(a)
        rows.append({
            "a": a, "prog": round(-st.x, 1), "z": round(st.z, 1),
            "v": round(abs(st.v), 1), "anim": round(st.anim, 2),
            "air": st.air, "step": round(abs(d), 1),
            "eff": round(0.6 + 0.4 * abs(math.cos(math.pi * st.anim / 23.0)), 4),
        })
    return rows


def classify(acts):
    rr = runs(acts)
    build_end = 0
    for (a, s, l) in rr:
        if a == 'chg' and l >= 10:
            build_end = s + l
    # Terminal dash = last long neutral run, tolerating a short trailing tail (e.g. "neu,48;ess,1");
    # scan back, stop at a charge. Short neu runs (dips) aren't the dash -> stay marked as pumps.
    DASH_MIN = 5
    dash_start = len(acts)
    for (a, s, l) in reversed(rr):
        if a == 'neu' and l >= DASH_MIN:
            dash_start = s
            break
        if a == 'chg':
            break
    phase = []
    for f, a in enumerate(acts):
        if f < build_end:
            phase.append('build')
        elif f >= dash_start:
            phase.append('dash')
        elif a == 'chg':
            phase.append('reboost')
        elif a == 'neu':
            phase.append('pump')
        else:
            phase.append('ess')
    reboosts = [s for (a, s, l) in rr if a == 'chg' and build_end <= s < dash_start]
    pumps = [s for (a, s, l) in rr if a == 'neu' and s < dash_start]
    return phase, build_end, dash_start, reboosts, pumps


def build(fn, label, color, net):
    acts = A.expand(open(fn).read())
    rows = trace(acts)
    phase, build_end, dash_start, reboosts, pumps = classify(acts)
    return {
        "label": label, "color": color, "frames": len(acts), "live_net": net,
        "rows": rows, "phase": phase, "build_end": build_end,
        "dash_start": dash_start, "reboosts": reboosts, "pumps": pumps,
    }


def main():
    traces = [
        build('ab_nopump_seq.txt', 'No-pump baseline', '#5aa9e6', 200583),
        build('ab_synced_seq.txt', 'Pump plan (live-synced)', '#2fc6a4', 200128),
    ]
    payload = json.dumps(traces, separators=(',', ':'))
    html = TEMPLATE.replace('__DATA__', payload)
    open('superswim_path_ab.html', 'w', encoding='utf-8').write(html)
    print('wrote superswim_path_ab.html', len(html), 'bytes;',
          'frames', [t['frames'] for t in traces],
          'reboosts', [len(t['reboosts']) for t in traces],
          'pumps', [len(t['pumps']) for t in traces])


TEMPLATE = r'''<title>Superswim 200k — pumps vs reboosts (path player)</title>
<meta name="description" content="Animated top-down replay of two Wind Waker superswim plans to 200,000 units, with reboost and ESS-pump frames marked distinctly.">
<style>
 :root{
   --sea:#0a1318;--panel:#10212a;--line:#1d3540;--line2:#27444f;
   --ink:#e8f1f3;--mut:#8aa3ac;--mut2:#5f7a84;
   --build:#5e7079;--ess:#2fc6a4;--reboost:#ff9d3c;--pump:#ffd23f;--dash:#a07add;
   --mono:"Cascadia Code","Cascadia Mono",Consolas,ui-monospace,monospace;
   --sans:"Segoe UI",system-ui,-apple-system,sans-serif;
 }
 *{box-sizing:border-box}
 html,body{margin:0;height:100%}
 body{background:var(--sea);color:var(--ink);font-family:var(--sans);font-size:13px}
 #wrap{display:flex;flex-direction:column;height:100vh;min-height:560px}
 #head{padding:14px 20px 10px;border-bottom:1px solid var(--line);
   background:linear-gradient(180deg,#0e1d25,#0b161d)}
 #head h1{font-family:var(--mono);font-size:15px;font-weight:700;margin:0;letter-spacing:.02em}
 #head .sub{color:var(--mut);font-size:12px;margin-top:4px;font-family:var(--mono)}
 #head .sub b{color:var(--ink)} #head .sub .g{color:#7ee08a}
 #top{flex:1;position:relative;min-height:240px}
 canvas{position:absolute;inset:0;width:100%;height:100%}
 #hud{padding:12px 20px 16px;background:#0e1d25;border-top:1px solid var(--line)}
 .row{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
 .row+.row{margin-top:12px}
 button{background:#16303b;color:var(--ink);border:1px solid var(--line2);border-radius:7px;
   padding:6px 14px;cursor:pointer;font-family:var(--mono);font-size:12px}
 button:hover{background:#1c3d4a}
 button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--ess);outline-offset:2px}
 input[type=range]{flex:1;min-width:160px;accent-color:var(--ess)}
 select{background:#16303b;color:var(--ink);border:1px solid var(--line2);border-radius:6px;padding:3px 6px;font-family:var(--mono)}
 #fnum{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--mut);min-width:120px}
 #fnum b{color:var(--ink)}
 .gauges{display:flex;gap:14px;flex-wrap:wrap}
 .gauge{flex:1 1 260px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 13px}
 .gauge .nm{font-family:var(--mono);font-weight:700;font-size:12.5px}
 .gauge .st{font-family:var(--mono);font-size:12px;color:var(--mut);margin-top:5px;font-variant-numeric:tabular-nums;letter-spacing:.01em}
 .gauge .st b{color:var(--ink);font-weight:600}
 .bar{height:7px;background:#0a1a22;border-radius:4px;overflow:hidden;margin-top:7px;border:1px solid var(--line)}
 .bar>div{height:100%;border-radius:4px}
 .legend{display:flex;gap:7px 18px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;color:var(--mut)}
 .lg{display:inline-flex;align-items:center;gap:7px}
 .dot{width:11px;height:11px;border-radius:50%;flex:none}
 .seg{width:15px;height:9px;border-radius:2px;flex:none}
 .vline{width:3px;height:15px;border-radius:1px;flex:none}
 .vline.rb{background:var(--reboost)} .vline.pu{background:var(--pump)}
</style>

<div id="wrap">
 <div id="head">
   <h1>Superswim → 200,000 units · pumps vs. reboosts</h1>
   <div class="sub">Top-down replay, real westward distance. Both cruise in band&nbsp;1 (|v|≈790).
     Baseline maintains with <b style="color:var(--reboost)">reboosts</b>;
     pump plan with <b style="color:var(--pump)">ESS pumps</b> →
     <b>555 fr</b> vs <b>561 fr</b> <span class="g">(−6, live-synced)</span>.</div>
 </div>
 <div id="top"><canvas id="c"></canvas></div>
 <div id="hud">
   <div class="row">
     <button id="play">⏸ pause</button>
     <input id="scrub" type="range" min="0" max="100" value="0" step="0.01">
     <span id="fnum">f 0</span>
     <label style="font-family:var(--mono);color:var(--mut)">speed
       <select id="rate"><option>0.5</option><option>1</option><option selected>2</option><option>4</option><option>8</option></select>×</label>
   </div>
   <div class="row gauges" id="gauges"></div>
   <div class="row legend">
     <span class="lg"><span class="seg" style="background:var(--build)"></span>build</span>
     <span class="lg"><span class="seg" style="background:var(--ess)"></span>ESS cruise</span>
     <span class="lg"><span class="seg" style="background:var(--dash)"></span>neutral dash</span>
     <span class="lg"><span class="vline rb"></span>reboost</span>
     <span class="lg"><span class="vline pu"></span>ESS pump</span>
   </div>
 </div>
</div>

<script>
const DATA = __DATA__;
const C = {build:'#5e7079',ess:'#2fc6a4',reboost:'#ff9d3c',pump:'#ffd23f',dash:'#a07add'};
const N = Math.max(...DATA.map(t=>t.frames));
const TARGET = 200000;
const maxProg = Math.max(...DATA.map(t=>t.rows[t.rows.length-1].prog));
const c=document.getElementById('c'), ctx=c.getContext('2d');
const DPR=()=>Math.min(devicePixelRatio||1,2);
function resize(){c.width=c.clientWidth*DPR();c.height=c.clientHeight*DPR();}
addEventListener('resize',resize);resize();

let frame=0, playing=true, t0=null, lastTs=null;

const PADX=()=>62*DPR(), PADR=()=>34*DPR();
function px(prog){const W=c.width;return PADX()+prog/maxProg*(W-PADX()-PADR());}
function laneY(i){const H=c.height;const top=H*0.30, gap=H*0.34;return top+i*gap;}

function phaseColor(p){return p==='build'?C.build:p==='dash'?C.dash:C.ess;}

function draw(){
  const W=c.width,H=c.height;
  ctx.clearRect(0,0,W,H);
  // target line
  const tx=px(TARGET);
  ctx.strokeStyle='#2a4a55';ctx.lineWidth=1*DPR();ctx.setLineDash([5*DPR(),5*DPR()]);
  ctx.beginPath();ctx.moveTo(tx,H*0.12);ctx.lineTo(tx,H*0.88);ctx.stroke();ctx.setLineDash([]);
  ctx.fillStyle='#7f9aa3';ctx.font=`${11*DPR()}px Consolas,monospace`;ctx.textAlign='center';
  ctx.fillText('200,000',tx,H*0.10);
  // distance ticks
  ctx.textAlign='center';ctx.fillStyle='#3d5a64';
  for(let d=0; d<=maxProg; d+=50000){const x=px(d);
    ctx.strokeStyle='#16282f';ctx.beginPath();ctx.moveTo(x,H*0.12);ctx.lineTo(x,H*0.88);ctx.stroke();
    ctx.fillStyle='#3d5a64';ctx.fillText((d/1000)+'k',x,H*0.95);}

  const fi=Math.floor(frame);
  DATA.forEach((t,i)=>{
    const y=laneY(i), rows=t.rows, upto=Math.min(fi,rows.length-1);
    const lw=Math.max(7*DPR(), H*0.05);
    // full planned track (dim) as phase-colored segments
    drawTrack(t, y, lw, rows.length-1, 0.16);
    // traveled portion (bright) up to head
    drawTrack(t, y, lw, upto, 0.95);
    // lane label
    ctx.textAlign='left';ctx.font=`bold ${12*DPR()}px Consolas,monospace`;ctx.fillStyle=t.color;
    ctx.fillText(t.label, PADX(), y-lw-9*DPR());
    // markers up to head: crisp vertical lines at the exact event frame.
    // reboost = amber line through the TOP of the lane (+tick above);
    // pump = gold line through the BOTTOM of the lane (+tick below).
    const mw=2*DPR(), ext=15*DPR();
    t.reboosts.forEach(f=>{ if(f<=upto){const x=Math.round(px(rows[f].prog)-mw/2);
      ctx.fillStyle=C.reboost;ctx.fillRect(x, y-lw/2-ext, mw, lw/2+ext);}});
    t.pumps.forEach(f=>{ if(f<=upto){const x=Math.round(px(rows[f].prog)-mw/2);
      ctx.fillStyle=C.pump;ctx.fillRect(x, y, mw, lw/2+ext);}});
    // head: small triangle pointing in the current travel/facing direction
    // (flips each charge frame -> watch it flip back and forth during charges/reboosts)
    const hx=px(rows[upto].prog);
    const hdir = upto>0 ? ((rows[upto].prog-rows[upto-1].prog)>=0?1:-1) : 1;
    const hs=lw*0.42;
    ctx.fillStyle=t.color;ctx.strokeStyle='#fff';ctx.lineWidth=1.5*DPR();ctx.lineJoin='round';
    ctx.beginPath();
    ctx.moveTo(hx+hdir*hs, y);
    ctx.lineTo(hx-hdir*hs, y-hs*0.85);
    ctx.lineTo(hx-hdir*hs, y+hs*0.85);
    ctx.closePath();ctx.fill();ctx.stroke();
    // finished flag
    if(upto>=rows.length-1){ctx.fillStyle='#7ee08a';ctx.textAlign='left';
      ctx.font=`${11*DPR()}px Consolas,monospace`;
      ctx.fillText('✓ '+t.frames+'f',hx+lw,y+4*DPR());}
  });
  updateHud();
}

function drawTrack(t,y,lw,upto,alpha){
  if(upto<0)return;const rows=t.rows;
  ctx.globalAlpha=alpha;ctx.lineWidth=lw;ctx.lineCap='round';
  let segStart=0;
  for(let i=1;i<=upto;i++){
    if(t.phase[i]!==t.phase[segStart] || i===upto){
      const end = (i===upto)?i:i;
      ctx.strokeStyle=phaseColor(t.phase[segStart]);
      ctx.beginPath();ctx.moveTo(px(rows[segStart].prog),y);ctx.lineTo(px(rows[end].prog),y);ctx.stroke();
      segStart=i;
    }
  }
  ctx.globalAlpha=1;ctx.lineCap='butt';
}

function updateHud(){
  const g=document.getElementById('gauges');
  const fi=Math.floor(frame);
  let html='';
  DATA.forEach(t=>{const r=t.rows[Math.min(fi,t.frames-1)];
    const reached=Math.min(fi,t.frames-1)>=t.frames-1;
    const pct=Math.min(100,r.prog/TARGET*100);
    html+=`<div class="gauge"><div class="nm" style="color:${t.color}">${t.label}`+
      `${reached?' <span style="color:#7ee08a">✓ '+t.frames+'f</span>':''}</div>`+
      `<div class="st">dist <b>${Math.round(r.prog).toLocaleString()}</b>`+
      ` &nbsp;|v| <b>${r.v.toFixed(0)}</b> &nbsp;anim <b>${r.anim.toFixed(1)}</b>`+
      ` &nbsp;air <b>${r.air}</b> &nbsp;eff <b>${(r.eff*100).toFixed(0)}%</b></div>`+
      `<div class="bar"><div style="width:${pct.toFixed(1)}%;background:${t.color}"></div></div></div>`;
  });
  g.innerHTML=html;
  document.getElementById('fnum').innerHTML=`<b>f ${Math.floor(frame)}</b> / ${N-1}`;
  document.getElementById('scrub').value=(frame/(N-1)*100)||0;
}

const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function tick(ts){
  if(playing){
    if(lastTs===null)lastTs=ts;
    const rate=parseFloat(document.getElementById('rate').value);
    frame=Math.min(N-1, frame + (ts-lastTs)/1000*30*rate);
    lastTs=ts;
    if(frame>=N-1){frame=N-1;playing=false;document.getElementById('play').textContent='↻ replay';}
  } else {lastTs=null;}
  draw();
  requestAnimationFrame(tick);
}
document.getElementById('play').onclick=()=>{
  if(frame>=N-1){frame=0;}
  playing=!playing;lastTs=null;
  document.getElementById('play').textContent=playing?'⏸ pause':'▶ play';
};
document.getElementById('scrub').oninput=e=>{playing=false;lastTs=null;
  frame=e.target.value/100*(N-1);
  document.getElementById('play').textContent='▶ play';draw();};
if(reduce){playing=false;frame=N-1;document.getElementById('play').textContent='↻ replay';}
requestAnimationFrame(tick);
draw();
</script>'''


if __name__ == '__main__':
    main()
