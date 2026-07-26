"""Deliver a computed Courtyard plan to CONSOLE -- the out-of-band DTM tier-2 confirm (session 54).

The plan is a frame-exact input sequence starting one game-frame after the state-2 seed (F0), so the
movie that delivers it must put the game in the real TAS's exact F0 state and then feed the plan. Both
savestate-anchor routes are DEAD (do not retry):

  * `loadstate 2` + a MODIFIED movie -> crash/hang. The movie-anchored slot-2 savestate is bound to the
    exact recorded movie.
  * a fresh `bFromSaveState=1` movie anchored to `GZLJ01.s02` -> the savestate is welded to the recorded
    90k-frame movie (`currentFrame` 89952), so a short movie is instantly past its end: Link sits frozen
    at the seed and Dolphin raises an input-MISMATCH dialog. (Session 53 read the seed appearing as
    "Strategy B confirmed"; it only ever proved the anchor loads, never that authored inputs PLAY.) A
    clean anchor cannot be minted at the seed either: `recordstart` is a no-op while a movie is playing,
    and no pipe verb ends playback while keeping the game running.

THE WORKING PATH -- splice the tail onto the recorded BOOT movie. Keep game-frames 0..F0 byte-identical
(so the boot replays the real TAS to the courtyard exactly), replace F0+1.. with the plan, and leave
`bFromSaveState=0`. Validated against ground truth: re-appending the RECORDED tail delivers latched
inputs (poll index 2 -- the poll the game latches) with **0/45 mismatch** vs the recording. Because the
tail is byte-aligned to the recorded frames by construction, there is NO savestate alignment padding, so
`rollstab/rest.REST_NOOPS` does not apply here.

TWO header/driving rules, both learned the hard way:

1. **tickCount must be EXTENDED, never maxed.** `Movie::CheckInputEnd` ends playback once
   `GetTicks() > tickCount`, so keeping the recorded value truncates the longer tail (it stopped at the
   RECORDING's frameCount, dropping ~197 of 241 plan frames). But maxing to `0xFFFFFFFFFFFFFFFF` reads
   as signed -1 -- the real cause of session 53's "maxed tickCount crashes State::Load". `tick_mode=
   'extend'` scales the recorded ticks to the longer movie + 10%: full tail AND loadstate-safe.

2. **Skip the ~9.5-minute boot replay with `loadstate 1`, and then DO NOT TOUCH the emulator.** Dereck's
   rule: a savestate whose inputs are a SUBSET of the movie's -- slot 1 is frame 89682, inside the
   byte-identical prefix, BEFORE the splice -- is equivalent to having replayed to that frame, so its
   result must be read as the full playback's. That takes a delivery run from ~9.5 min to ~8 s. Slot 2 is
   NOT usable: it sits AT the splice (it reads plan frame 0) and trips the mismatch dialog. Issue ONLY
   `playmovie` + `savestate load 1`: any `pause`/`resume`/per-frame `advance` of ours makes Dolphin
   re-pause (PauseMovie=True plus frame/tick bookkeeping restored from the savestate) and the run then
   needs manual unpausing, which invalidates it. `PauseMovie` already halts at the movie's last frame,
   which is where the endpoint is read.

TRUNCATE-AND-READ is the diagnostic this buys: author only the first N plan frames and PauseMovie halts
at plan frame N-1, so one plain ~8-s run reads that exact frame for BOTH actors -- a per-frame sim-vs-
console curve with no stepping at all. `divergence_curve` sweeps N.

    from harness.tetrapush.deliver import build_boot_movie, deliver_plan, divergence_curve
    info = build_boot_movie(log, out)                  # splice; offline, no Dolphin
    end  = deliver_plan(log)                           # live: author -> play -> loadstate 1 -> read
    rows = divergence_curve(log, [20, 40, 60], model)  # live: per-N endpoint vs the offline expectation

CLI:
    python -m harness.tetrapush.deliver plan=_notes/node1_full_log.json
    python -m harness.tetrapush.deliver plan=... ns=20,30,40,50,60      # the divergence curve
"""
import json
import math
import os
import struct
import sys
import time

# >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

from harness.tetrapush import dtm_inputs as DI       # noqa: E402

_GEN = os.path.join(_rb, '_generated')
REC = DI.DTM_DEFAULT              # the recorded boot movie beside slot 2 (GZLJ01.s02.dtm)
HDR = 256
ROW = 8
PREFIX_SLOT = 1                   # the subset savestate: inside the identical prefix, before the splice
SEED_XZ = (-1329.4236, 39.8988)   # F0 (fixtures/courtyard_push_dtm.json frames[0].live) -- the landmark


def _cal(v):
    """dtm_make's getMainStickValue calibration: every authored DTM delivers 255 as 254 and 0 as 1."""
    return {255: 254, 0: 1}.get(int(v), int(v))


def _port0_row(d, base_flags):
    """A plan frame -> an 8-byte port0 ControllerState row, inverting `dtm_inputs.frame_input`.

    Buttons use the PAD convention `LandState.step`/`frame_input` speak: A=0x100 -> flag 0x02,
    B=0x200 -> 0x04, L=0x40 -> 0x400 (plus the analog trigger byte). `dtm_make.pad_to_cs` cannot emit
    L at all, which is why authoring goes through here for a plan that soft-locks."""
    b = d.get('buttons', 0)
    fl = base_flags
    if b & 0x100:
        fl |= 0x02
    if b & 0x200:
        fl |= 0x04
    if b & 0x40:
        fl |= 0x400
    tl = 255 if (b & 0x40) else int(d.get('triggerL', 0))
    return struct.pack('<H6B', fl, tl, 0,
                       _cal(d.get('stickX', 128)), _cal(d.get('stickY', 128)),
                       _cal(d.get('substickX', 128)), _cal(d.get('substickY', 0)))


def build_boot_movie(log, out, rec=REC, tick_mode='extend'):
    """Splice `log` onto the recorded BOOT movie and write it to `out`. Offline (no Dolphin).

    Game-frames 0..F0 stay BYTE-IDENTICAL; the tail is rebuilt so `log[i]` lands on game-frame F0+1+i
    (the offline `pre_seed_input(dtm(0)); step(log[i])` convention), 4 uniform port0 polls each, and the
    movie is truncated right after `log[-1]` so PauseMovie halts there. `bFromSaveState` stays 0.

    tick_mode: 'extend' (recorded ticks scaled to the longer movie + 10% -- the correct choice, see the
    module docstring), 'max' (0xFFFF...; ONLY without a loadstate -- it reads as signed -1 and crashes
    State::Load), or 'keep' (recorded value; truncates a longer tail -- diagnostic only).

    Returns an info dict including a `rt_mismatch` round-trip count and `prefix_ok`; both must be
    0/True before a movie is trusted."""
    rec_b = bytearray(open(rec, 'rb').read())
    assert rec_b[0:4] == b'DTM\x1a' and rec_b[0x0B] == 3, "not a controllers=3 DTM"
    assert rec_b[12] == 0, "recorded movie is not bFromSaveState=0 (a boot movie)"
    data = rec_b[HDR:]
    port0 = DI.load_port0(rec)
    F0 = DI.find_f0(port0)

    blank_p1 = bytes(data[0:ROW])                       # the recorded blank port1 row (even rows)
    tmpl_p0 = bytearray(data[(F0 * 8 + 1) * ROW:(F0 * 8 + 1) * ROW + ROW])
    base_flags = struct.unpack_from('<H', tmpl_p0)[0] & ~0x0406   # keep connected/origin bits; clear A/B/L

    prefix = data[:((F0 + 1) * 8) * ROW]                # game-frames 0..F0 inclusive
    tail = bytearray()
    for d in log:
        r = _port0_row(d, base_flags)
        for _ in range(4):
            tail += blank_p1                            # even row = port1 blank
            tail += r                                   # odd row  = port0 (load_port0's convention)
    new_data = bytes(prefix) + bytes(tail)
    n_rows = len(new_data) // ROW
    n_gframes = n_rows // 8

    rec_gf = len(port0) // 4
    rec_fc = struct.unpack_from('<Q', rec_b, 0x0D)[0]
    rec_tick = struct.unpack_from('<Q', rec_b, 237)[0]
    new_fc = rec_fc + 2 * (n_gframes - rec_gf)          # +2 VI frames per extra game frame
    hdr = bytearray(rec_b[:HDR])
    struct.pack_into('<Q', hdr, 0x15, n_rows)           # inputCount = total ControllerState rows
    struct.pack_into('<Q', hdr, 0x0D, new_fc)           # frameCount
    if tick_mode == 'max':
        struct.pack_into('<Q', hdr, 0x1D, 0)
        struct.pack_into('<Q', hdr, 237, 0xFFFFFFFFFFFFFFFF)
    elif tick_mode == 'extend':
        struct.pack_into('<Q', hdr, 237, int(new_fc * (rec_tick / float(rec_fc)) * 1.10))
    elif tick_mode != 'keep':
        raise ValueError("tick_mode must be 'extend', 'max' or 'keep'")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(bytes(hdr) + new_data)

    # round-trip the tail through the same reader the recorded ground truth uses
    p0b = DI.load_port0(out)
    mism = 0
    for i, d in enumerate(log):
        got = DI.frame_input(p0b, F0 + 1 + i)
        exp_tl = 255 if (d.get('buttons', 0) & 0x40) else int(d.get('triggerL', 0))
        if not (got['stickX'] == _cal(d.get('stickX', 128))
                and got['stickY'] == _cal(d.get('stickY', 128))
                and got['substickX'] == _cal(d.get('substickX', 128))
                and got['substickY'] == _cal(d.get('substickY', 0))
                and got['buttons'] == d.get('buttons', 0) and got['triggerL'] == exp_tl):
            mism += 1
    prefix_ok = DI.frame_input(p0b, F0) == DI.frame_input(port0, F0)
    return dict(out=out, F0=F0, tail=len(log), game_frames=n_gframes, frameCount=new_fc,
                tickCount=struct.unpack_from('<Q', hdr, 237)[0], tick_mode=tick_mode,
                bytes=HDR + len(new_data), rt_mismatch=mism, prefix_ok=prefix_ok)


# --- live delivery (needs Dolphin + ../tools/dolphin_mem) ---
def _dolphin():
    import dolphin_mem as D
    from harness.dtm import run_dtm as RD
    from harness import dolphin_env as ENV
    return D, RD, ENV


def _attach_safe(D):
    """`D.attach()` prints "Could not locate emulated MEM1" and sys.exit()s while MEM1 is unmapped
    mid-boot; SystemExit is not an Exception, so a plain try/except lets it kill the caller. Swallow
    both it and the print (the same guard `run_dtm._attach_ready` uses)."""
    saved = sys.stdout
    try:
        sys.stdout = open(os.devnull, 'w')
        try:
            return D.attach()
        finally:
            sys.stdout.close()
            sys.stdout = saved
    except BaseException:
        sys.stdout = saved
        return None


def read_link(D):
    """Link's endpoint off the fixed player pointer (0x803AD860) -- no breakpoint, so nothing is
    perturbed. None while MEM1/the player object is not readable yet."""
    hm = _attach_safe(D)
    if hm is None:
        return None
    h, m = hm
    lp = struct.unpack('>I', D.read_bytes(h, m, 0x803AD860, 4))[0]
    if lp < 0x80000000:
        return None
    la = lp - 0xD8
    return dict(lp=lp,
                x=struct.unpack('>f', D.read_bytes(h, m, la + 0x1F8, 4))[0],
                z=struct.unpack('>f', D.read_bytes(h, m, la + 0x200, 4))[0],
                speedF=struct.unpack('>f', D.read_bytes(h, m, la + 0x254, 4))[0],
                facing=struct.unpack('>H', D.read_bytes(h, m, la + 0x20E, 2))[0],
                travel=struct.unpack('>H', D.read_bytes(h, m, la + 0x206, 2))[0],
                proc=struct.unpack('>i', D.read_bytes(h, m, lp + 0x3100, 4))[0])


def read_tetra(D):
    """Tetra's endpoint via `find_tetra.tetra_scan` (RAM scan, breakpoint-free) -- her `_execute`
    breakpoint cannot trap on a halted movie, which silently yields no reads at all."""
    from harness.tetrapush.find_tetra import tetra_scan
    z = tetra_scan(D, verbose=False)
    if not z:
        return None
    hm = _attach_safe(D)
    if hm is None:
        return None
    h, m = hm
    return dict(this=z,
                x=struct.unpack('>f', D.read_bytes(h, m, z + 0x1F8, 4))[0],
                z=struct.unpack('>f', D.read_bytes(h, m, z + 0x200, 4))[0],
                stt=struct.unpack('b', D.read_bytes(h, m, z + 0x84B, 1))[0])


def play_spliced(movie, frameCount, slot=PREFIX_SLOT, playsecs=150, bootsecs=240,
                 want_tetra=True, verbose=True, say=print):
    """Play a spliced boot movie and read both actors at the halt.

    Issues exactly TWO emulation commands -- `playmovie` and `savestate load <slot>` -- then leaves the
    emulator alone (see the module docstring: our own pause/resume/advance makes Dolphin re-pause and
    forces manual unpausing). Gates the loadstate on playback actually RUNNING: firing it at frame 0 /
    `state:other` kills Dolphin outright, while waiting for MEM1 to map costs a needless ~13 s."""
    D, RD, ENV = _dolphin()
    iso = ENV.iso_path('TWW-JP')

    def status():
        try:
            return json.loads(D.control_pipe_quiet("status"))
        except Exception:
            return {}

    RD.relaunch(verbose=verbose)
    D.control_pipe_quiet("playmovie", {"path": movie.replace('\\', '/'), "game": iso.replace('\\', '/')})
    t0 = time.time()
    while time.time() - t0 < bootsecs:
        st = status()
        if not st.get("ok"):
            raise SystemExit("Dolphin gone during boot: %s" % st)
        if st.get("state") == "running" and st.get("playing"):
            if verbose:
                say("  playback running @%.1fs (frame %s) -- loadstate %d" % (time.time() - t0, st.get('frame'), slot))
            break
        time.sleep(0.1)
    else:
        raise SystemExit("playback never started within %ds" % bootsecs)
    D.control_pipe_quiet("savestate", {"action": "load", "slot": int(slot)})

    t1 = time.time(); last = None; stable = 0; ended = False
    while time.time() - t1 < playsecs:
        st = status()
        if not st.get("ok"):
            raise SystemExit("Dolphin gone during playback")
        fr = st.get("frame")
        stable = stable + 1 if fr == last else 0
        last = fr
        if isinstance(fr, int) and fr >= frameCount - 4 and stable >= 3:
            ended = True
            break
        if (not st.get("playing")) and stable >= 8:
            if verbose:
                say("  playback stopped early at frame %s (target %d)" % (fr, frameCount))
            ended = True
            break
        time.sleep(0.25)
    link = read_link(D)
    tetra = read_tetra(D) if want_tetra else None
    if verbose:
        say("  END frame %s/%d Link(%.4f,%.4f) face %d proc %d%s"
            % (status().get('frame'), frameCount, link['x'], link['z'], link['facing'], link['proc'],
               ("  Tetra(%.4f,%.4f) stt %d" % (tetra['x'], tetra['z'], tetra['stt'])) if tetra else ""))
    return dict(link=link, tetra=tetra, ended=ended, frameCount=frameCount)


def deliver_plan(log, out=None, tick_mode='extend', slot=PREFIX_SLOT, want_tetra=True,
                 verbose=True, say=print):
    """Author `log` as a spliced boot movie and play it -- the whole live delivery in one call."""
    out = out or os.path.join(_GEN, 'tetrapush_deliver.dtm')
    info = build_boot_movie(log, out, tick_mode=tick_mode)
    if info['rt_mismatch'] or not info['prefix_ok']:
        raise SystemExit("movie fidelity check FAILED (rt_mismatch=%d prefix_ok=%s)"
                         % (info['rt_mismatch'], info['prefix_ok']))
    if verbose:
        say("spliced %s: tail=%d frameCount=%d tick=%s" % (os.path.basename(out), info['tail'],
                                                           info['frameCount'], tick_mode))
    end = play_spliced(out, info['frameCount'], slot=slot, want_tetra=want_tetra,
                       verbose=verbose, say=say)
    end['movie'] = info
    return end


def divergence_curve(log, ns, model=None, tick_mode='extend', slot=PREFIX_SLOT, verbose=True, say=print):
    """TRUNCATE-AND-READ: for each N in `ns`, deliver only `log[:N]` and read the endpoint.

    PauseMovie halts at the movie's last frame, which IS plan frame N-1, so each ~8-s run samples the
    live state at that frame for BOTH actors -- a sim-vs-console curve needing no per-frame stepping.
    `model` maps plan-frame index -> {link_x, link_z, tetra_x, tetra_z, ...} (see the offline per-frame
    expectation); when given, each row carries `dl`/`dt` residuals.

    Reading the result: `dl == dt` at every N means the error is equal-and-opposite on both actors --
    the CC push split's signature, i.e. a PUSH-MAGNITUDE error rather than a foot-term error (confirm by
    checking that proc and speedF still match)."""
    rows = []
    for n in ns:
        out = os.path.join(_GEN, 'tetrapush_deliver_n%d.dtm' % n)
        end = deliver_plan(log[:n], out=out, tick_mode=tick_mode, slot=slot,
                           verbose=verbose, say=say)
        row = dict(n=n, link=end['link'], tetra=end['tetra'])
        if model is not None and (n - 1) in model:
            m = model[n - 1]
            row['dl'] = math.hypot(end['link']['x'] - m['link_x'], end['link']['z'] - m['link_z'])
            if end['tetra']:
                row['dt'] = math.hypot(end['tetra']['x'] - m['tetra_x'], end['tetra']['z'] - m['tetra_z'])
            row['model'] = m
            if verbose:
                say("  N=%-4d dLink=%9.4f  dTetra=%9.4f" % (n, row['dl'], row.get('dt', float('nan'))))
        rows.append(row)
    return rows


def _load_plan(path):
    """A plan file is either a bare list of frame dicts or {log: [...], ...} (the node dumps)."""
    o = json.load(open(path))
    return o['log'] if isinstance(o, dict) else o


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    if 'plan' not in o:
        raise SystemExit(__doc__.strip().splitlines()[-2].strip())
    log = _load_plan(o['plan'])
    print("plan %s: %d frames" % (os.path.basename(o['plan']), len(log)))
    if 'ns' in o:
        model = None
        if 'model' in o:
            model = {r['i']: r for r in json.load(open(o['model']))['rows']}
        divergence_curve(log, [int(x) for x in o['ns'].split(',')], model=model,
                         slot=int(o.get('slot', PREFIX_SLOT)))
    else:
        deliver_plan(log, out=o.get('out'), slot=int(o.get('slot', PREFIX_SLOT)))


if __name__ == '__main__':
    main()
