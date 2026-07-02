"""Generalized, pipe-artifact-free DTM runner.

Give it a per-frame INPUT sequence (raw sticks, or an ess/chg/neu action list) and an
optional EXPECTED endpoint; it handles the rest: author a clean-cadence DTM, copy the
savestate anchor, (re)launch Dolphin to a stopped game list, play the movie, read the
live endpoint, and compare. This is the trustworthy live check (movie playback flips
WantDeterminism on and polls at the game's natural cadence -- no advanceseq pipe jitter,
see pt-21 / SUPERSWIM_KNOWLEDGE bug#2).

Generalizes harness/validate/validate_dtm.py, which was hardwired to action-seq files, the
cold anchor, and a SwimState compare. Here:
  - inputs are universal per-frame sticks (action lists convert via actions.acts_to_seq),
  - the anchor / template / expected are all parameters,
  - boot is detected by a readable charged/neutral slate (state 54/55), NOT the playing
    flag (which a short movie can flip before detection stabilizes), and
  - the end state is read once the movie exhausts and the emulator pauses at the last frame
    (PauseMovie, ensured by dolphin_env) -- exact and fast, no per-frame pipe stepping.

Programmatic:
    from harness.dtm.run_dtm import run_dtm, sticks_from_actions
    end = run_dtm(sticks, expected={'v': -812.3, 'anim': 4.1, 'air': 870, 'state': 55},
                  game=ISO, anchor=ANCHOR)

CLI:
    python run_dtm.py seq=plan3k_exact_seq.txt [game=<iso>] [anchor=<.sav>]
                      [expect_v=..] [expect_anim=..] [expect_air=..] [expect_state=..]
                      [tol=0.02] [norelaunch=0]
"""
import sys, os, time, math, json, shutil, subprocess
# >>> repo bootstrap: locate superswim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path: sys.path.append(_tb)
import glob
import dolphin_mem as D
from superswim import actions as A
from superswim import sim as S
import dtm_make as DM
from harness import dolphin_env as ENV

# --- environment (machine paths come from harness.dolphin_env: env -> dolphin.local.json) ------
# Test-owned anchors (not save slots): "<test>@<isokey>.sav"; isokey -> <isos_dir>/<key>.iso so
# the runner pulls the right image automatically. See tests/dolphin/anchors/README.md.
ANCHOR_DIR = os.path.join(_rb, "tests", "dolphin", "anchors")
_GEN = os.path.join(_rb, "_generated")
DEFAULT_TEMPLATE = os.path.join(_GEN, "cruise_pump300k_rec.dtm")  # iso-agnostic header clone
DEFAULT_ANCHOR = os.path.join(ANCHOR_DIR, "cruise_cold@twwgz.sav")  # cold start v0/state54
X0, Z0 = 42222.0, -158781.0          # slate origin (net is a sanity scalar only)
FACING_TOL_DEG = 2.0                 # default facing compare tolerance (game u16 -> deg)


def resolve_anchor(anchor):
    """Accept a bare anchor name or a path; return its absolute .sav path."""
    if os.path.isabs(anchor) or os.sep in anchor or '/' in anchor:
        return anchor
    cand = os.path.join(ANCHOR_DIR, anchor)
    return cand if cand.endswith('.sav') else cand + '.sav'


def iso_for_anchor(anchor):
    """Parse the '@<isokey>.sav' suffix and resolve <isos_dir>/<isokey>.iso via dolphin_env.

    The iso the anchor was captured on is baked into its filename, so the runner never has
    to be told which image to boot. Raises if the name lacks a key or the iso isn't found.
    """
    base = os.path.basename(anchor)
    if base.endswith('.dtm.sav'):
        base = base[:-len('.dtm.sav')]
    elif base.endswith('.sav'):
        base = base[:-len('.sav')]
    if '@' not in base:
        raise SystemExit(f"anchor '{base}' has no '@<isokey>' iso tag; "
                         f"name it e.g. mytest@twwgz.sav")
    return ENV.iso_path(base.rsplit('@', 1)[1])


# --- input adapters -------------------------------------------------------------------
def sticks_from_actions(acts):
    """ess/chg/neu action list -> per-frame stick dicts (chg alternates up/down)."""
    return A.acts_to_seq(acts)


def sticks_from_seq_file(path):
    return sticks_from_actions(A.expand(open(path).read()))


# --- Dolphin lifecycle ----------------------------------------------------------------
def _status():
    try:
        return json.loads(D.control_pipe_quiet("status"))
    except Exception:
        return {}


def relaunch(verbose=True):
    exe = ENV.dolphin_exe()
    subprocess.run(["taskkill", "/F", "/IM", "Dolphin.exe"], capture_output=True)
    time.sleep(1.5)
    ENV.ensure_pause_at_end(exe, verbose=verbose)   # exhaust reads require pausing at movie end
    subprocess.Popen([exe], cwd=os.path.dirname(exe))
    for _ in range(40):
        if _status().get("ok"):
            if verbose: print("Dolphin relaunched (stopped game list)")
            return
        time.sleep(1.0)
    raise SystemExit("Dolphin did not come up after relaunch")


def _attach_slate(min_air):
    """Return (h, mem1, state) if MEM1 is mapped and Link is on a swim slate, else None."""
    try:
        # D.attach() prints "Could not locate emulated MEM1" + sys.exits while MEM1 is unmapped
        # mid-boot; that's expected on early poll attempts, so swallow its stdout + the exit.
        _saved = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            h, m = D.attach()
        finally:
            sys.stdout.close(); sys.stdout = _saved
    except BaseException:
        return None
    try:
        st = D.read_named(h, m, "link_state")
        air = D.read_named(h, m, "air")
    except BaseException:
        return None
    if st in (54, 55) and air >= min_air:
        return h, m, st
    return None


def _read_end(h, m):
    end = {k: D.read_named(h, m, k) for k in
           ("potential_speed", "anim_frame", "air", "link_state", "link_x", "link_z",
            "facing")}
    end["facing_deg"] = end["facing"] * 360.0 / 65536.0
    end["net"] = math.hypot(end["link_x"] - X0, end["link_z"] - Z0)
    return end


# --- the engine -----------------------------------------------------------------------
def run_dtm(sticks, expected=None, *, game=None, anchor=DEFAULT_ANCHOR,
            template=DEFAULT_TEMPLATE, out=None, relaunch_dolphin=True,
            polls=4, seed=1, bootsecs=180, playsecs=360,
            min_air=800, tol=0.02, facing_tol=FACING_TOL_DEG, verbose=True):
    """Author -> play -> read -> compare. Returns an endpoint dict (see module docstring).

    sticks   : list of {stickX, stickY, substickX?, substickY?} (one per game frame).
    expected : optional dict, any of {v, anim, air, state, facing} (facing in DEGREES);
               v/anim/state/air compared within tol, facing cyclically within facing_tol.
    game     : iso path; if None, derived from the anchor's '@<isokey>' tag.
    The end state is read at movie exhaustion: the movie free-runs and is read once playback
    stops, which is exact because the emulator PAUSES at the last movie frame (PauseMovie, ensured
    by relaunch via dolphin_env). No per-frame pipe stepping -- that paid ControlPipe's per-frame
    DoFrameStep wait and ran ~100x slower.
    """
    anchor = resolve_anchor(anchor)
    game = (game or iso_for_anchor(anchor)).replace('\\', '/')
    sticks = list(sticks)
    nframes = len(sticks)
    if out is None:
        out = os.path.join(_GEN, "run_dtm_tmp.dtm")
    info = DM.build_dtm_from_sticks(sticks, out, template, polls, seed)
    shutil.copyfile(anchor, out + ".sav")
    if verbose:
        print(f"authored {os.path.basename(out)}: {info['frames']} fr, "
              f"{info['rows']} rows; anchor={os.path.basename(anchor)}")

    if relaunch_dolphin:
        relaunch(verbose)
    D.control_pipe_quiet("playmovie", {"path": out.replace('\\', '/'), "game": game})
    if verbose: print(f"playmovie {os.path.basename(out)}")

    # boot: wait for a readable swim slate (movie loaded the anchor). NOT the playing flag.
    t0 = time.time(); slate = None
    while time.time() - t0 < bootsecs:
        slate = _attach_slate(min_air)
        if slate:
            if verbose: print(f"booted after {time.time()-t0:.1f}s (state={slate[2]})")
            break
        time.sleep(1.0)
    if not slate:
        raise SystemExit("never reached a booted swim slate")
    armed = bool(_status().get("playing"))
    # start-of-movie controllable values (frame 0, before any input) -- lets a caller seed
    # its prediction to the ACTUAL anchor instead of assuming a fixed cold-start seed.
    h0, m0, _ = slate
    start = {k: D.read_named(h0, m0, k) for k in
             ("potential_speed", "anim_frame", "air", "link_state")}

    # Read at exhaustion: free-run, read once playback stops. Exact because the emulator PAUSES at
    # the last movie frame (PauseMovie, ensured by relaunch); no slow per-frame pipe stepping.
    D.control_pipe_quiet("resume")
    t1 = time.time(); ended = False
    while time.time() - t1 < playsecs:
        if not _status().get("playing"):
            ended = True; break
        time.sleep(0.3)
    D.control_pipe_quiet("pause")
    advanced = None

    h, m = D.attach()
    end = _read_end(h, m)
    end.update(ended=ended, armed=armed, frames=nframes, advanced=advanced, start=start)

    if expected:
        end["compare"] = _compare(end, expected, tol, facing_tol)
    if verbose:
        _print_end(end, expected)
    return end


def _compare(end, expected, tol, facing_tol):
    cyc = 26.0 if end["link_state"] == 54 else 23.0
    res = {"ok": True, "tol": tol}
    if "v" in expected:
        dv = end["potential_speed"] - expected["v"]
        res["dv"] = dv; res["ok"] &= abs(dv) <= max(tol, abs(expected["v"]) * 1e-4)
    if "anim" in expected:
        dan = A.animdiff(end["anim_frame"], expected["anim"], cyc)
        res["dan"] = dan; res["ok"] &= dan <= tol
    if "air" in expected:
        res["air_ok"] = (end["air"] == expected["air"]); res["ok"] &= res["air_ok"]
    if "state" in expected:
        res["state_ok"] = (end["link_state"] == expected["state"]); res["ok"] &= res["state_ok"]
    if "facing" in expected:
        dfac = abs(S.angdiff_deg(end["facing_deg"], expected["facing"]))
        res["dfac"] = dfac; res["ok"] &= dfac <= facing_tol
    return res


def _print_end(end, expected):
    print(f"  LIVE: v={end['potential_speed']:.3f} anim={end['anim_frame']:.4f} "
          f"air={end['air']} st={end['link_state']} face={end['facing_deg']:.1f} "
          f"net={end['net']:.0f} armed={end['armed']} advanced={end['advanced']}"
          + ("" if end["ended"] else " [TIMEOUT]"))
    c = end.get("compare")
    if c:
        bits = []
        if "dv" in c: bits.append(f"dv={c['dv']:+.3f}")
        if "dan" in c: bits.append(f"dan={c['dan']:.3f}")
        if "air_ok" in c: bits.append(f"air={'ok' if c['air_ok'] else 'X'}")
        if "state_ok" in c: bits.append(f"state={'ok' if c['state_ok'] else 'X'}")
        if "dfac" in c: bits.append(f"dface={c['dfac']:.2f}deg")
        print(("  PASS " if c["ok"] else "  FAIL ") + " ".join(bits))


# --- CLI ------------------------------------------------------------------------------
def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    if 'seq' in o:
        seqpath = o['seq'] if os.path.exists(o['seq']) else os.path.join(
            _rb, 'fixtures', o['seq'])
        sticks = sticks_from_seq_file(seqpath)
        label = os.path.basename(seqpath)
    elif 'sticks' in o:
        sticks = DM.parse_seq(open(o['sticks']).read()); label = o['sticks']
    else:
        raise SystemExit("pass seq=<action file> or sticks=<raw csv file>")

    expected = {}
    if 'expect_v' in o: expected['v'] = float(o['expect_v'])
    if 'expect_anim' in o: expected['anim'] = float(o['expect_anim'])
    if 'expect_air' in o: expected['air'] = int(o['expect_air'])
    if 'expect_state' in o: expected['state'] = int(o['expect_state'])
    if 'expect_facing' in o: expected['facing'] = float(o['expect_facing'])

    print(f"=== run_dtm: {label} ({len(sticks)} frames) ===")
    run_dtm(sticks, expected or None,
            game=o.get('game'),                 # default: derived from anchor's @isokey tag
            anchor=o.get('anchor', DEFAULT_ANCHOR),
            template=o.get('template', DEFAULT_TEMPLATE),
            tol=float(o.get('tol', '0.02')),
            relaunch_dolphin=o.get('norelaunch', '0') not in ('1', 'true', 'yes'),
            bootsecs=int(o.get('bootsecs', '180')))


if __name__ == "__main__":
    main()
