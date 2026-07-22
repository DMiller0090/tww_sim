"""Extract the REAL per-frame raw controller inputs for the Courtyard push from the any% TAS movie
(``GZLJ01.s02.dtm``, the companion DTM beside savestate slot 2) and bake them, alongside the
session-2 live ground-truth states, into a self-contained repo fixture.

Why the DTM and not the captured pad struct: the sim's ``LandState.step`` takes RAW stick bytes
(0..255) and runs its OWN octagon decode -- the octagon clamp IS part of the physics -- so a 0-ULP
replay needs the raw bytes, not the game's post-decode ``g_mDoCPd_cpadInfo`` floats (lossy). The DTM
holds exactly the bytes the game received.

Frame alignment (verified 2026-07-21, session 3): the s02 DTM is a real recording -- controllers=3
(ports 0+1 interleaved, port0 = odd row indices), 4 port0 polls per game frame (boundary at poll
index == 0 mod 4 near the movie end), the 4 polls of a frame are uniform. State 2 is the frame whose
delivered stick == the captured pad frame-for-frame; the anchor is the cycle-2 roll-trigger A-run.
With ``F0 = 44974`` (DTM game-frame == captured f0) the delivered decode matches the session-2
capture EXACTLY every frame (buttons + magnitude + angle, 0 mismatch over the 45 movie frames). The
movie ends at DTM group 45019 (== captured f45); captured f46+ is free-run holding the last input
(stick 111,111). This alignment is re-derived at runtime (the two A-runs, 26 frames apart) so it does
not silently rot if the DTM changes.

CAUTION: the session-2 capture is a SINGLE-STEPPED playing movie, so its per-frame reads are +-1-frame
ambiguous for button/proc EDGES ([[run-dtm-1frame-jitter]]). Held/settled scalars (the -25.727 /
-25.743 proc-9 flip magnitudes, a settled backslide speedF) ARE trustworthy; the EXACT frame of an
edge (the proc-9 init frame, the roll-exit frame) is NOT -- pin those with a jitter-free capture.

    python -m harness.tetrapush.dtm_inputs                 # regenerate fixtures/courtyard_push_dtm.json
    python -m harness.tetrapush.dtm_inputs check           # print the alignment table (no write)
"""
import json
import os
import struct
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

from tww_sim.core.mathlib import main_stick_decode   # noqa: E402

# The recorded movie beside slot 2 (machine path via dolphin_env's User/StateSaves).
DTM_DEFAULT = os.path.join(
    os.path.dirname(_rb), 'Dolphin-Zelda-TAS-Edition', 'Binary', 'x64', 'Release',
    'User', 'StateSaves', 'GZLJ01.s02.dtm')
OUT_DEFAULT = os.path.join(_rb, 'fixtures', 'courtyard_push_dtm.json')


def load_port0(dtm=DTM_DEFAULT):
    """Return the port0 (real controller) poll rows of a controllers=3 DTM as a list of
    (flags, stickX, stickY, cStickX, cStickY, triggerL) tuples, one per poll."""
    d = open(dtm, 'rb').read()
    assert d[0:4] == b'DTM\x1a', "not a DTM"
    assert d[11] == 3, "expected controllers=3 (ports 0+1)"
    data = d[256:]
    nrows = len(data) // 8
    port0 = []
    for i in range(1, nrows, 2):                 # port0 = odd row indices (port1 blanks are even)
        off = i * 8
        fl = struct.unpack_from('<H', data, off)[0]
        tl, tr, sx, sy, cx, cy = struct.unpack_from('<6B', data, off + 2)
        port0.append((fl, sx, sy, cx, cy, tl))
    return port0


def find_f0(port0):
    """Locate captured-f0 (state 2) = the DTM game-frame that begins the push. The push is two
    roll cycles 26 frames apart; each cycle's roll trigger is an 8-poll (2-frame) A-run. Anchor on
    the LAST A-run (cycle 2's, captured f28) so f0 = that group - 28. Returns the game-frame index.

    A game frame = 4 port0 polls (boundary at poll index % 4 == 0 near the movie end)."""
    ngf = len(port0) // 4
    a_runs = []                                  # game-frame indices whose group presses A
    for g in range(ngf):
        if port0[g * 4][0] & 0x02:               # A bit (ControllerState bit1)
            a_runs.append(g)
    # collapse consecutive frames into run-starts; keep the last two run-starts (the two cycles)
    starts = [g for k, g in enumerate(a_runs) if k == 0 or g != a_runs[k - 1] + 1]
    if len(starts) < 2:
        raise RuntimeError("expected >=2 A-runs (the two push roll triggers); found %d" % len(starts))
    cyc2_A = starts[-1]                           # captured f28 (cycle-2 roll trigger)
    return cyc2_A - 28


def frame_input(port0, g):
    """The (stickX, stickY, buttons, triggerL, cStickX, cStickY) for DTM game-frame g, clamped to
    the last frame past the movie end (free-run holds the final input). buttons in the PAD_BUTTON
    convention LandState.step expects: A=0x100, B=0x200, L=0x40."""
    ngf = len(port0) // 4
    fl, sx, sy, cx, cy, tl = port0[min(g, ngf - 1) * 4]
    btn = (0x100 if fl & 0x02 else 0) | (0x200 if fl & 0x04 else 0) | (0x40 if fl & 0x400 else 0)
    return dict(stickX=sx, stickY=sy, buttons=btn, triggerL=tl, substickX=cx, substickY=cy)


def build(dtm=DTM_DEFAULT, cap_path=None, out=OUT_DEFAULT, nframes=56, write=True):
    """Bake fixtures/courtyard_push_dtm.json: {F0, seed, frames:[{f, inp, live, tetra}]}.

    ``cap_path`` = the session-2 full-pad live capture (push_full.json) supplying the ground-truth
    per-frame Link/Tetra states; if None, only the inputs are baked (no ground truth to validate)."""
    port0 = load_port0(dtm)
    f0 = find_f0(port0)
    cap = json.load(open(cap_path))['frames'] if cap_path else None
    frames = []
    for i in range(nframes):
        row = dict(f=i, inp=frame_input(port0, f0 + i))
        if cap is not None and i < len(cap):
            c = cap[i]
            row['live'] = dict(proc=c['proc'], speedF=c['link']['speedF'], facing=c['link']['facing'],
                               travel=c['link']['travel'], pos=c['link']['pos'], anim=c['link'].get('anim'),
                               # Link Co-cyl centre (Tetra-plow driver) + csangle -- the from-f0 replay
                               # ground truth (see README ## The CC split / ## Addresses).
                               cyl=c['link'].get('cyl'), csangle=c.get('csangle'))
            row['tetra'] = dict(pos=c['tetra']['pos'], stt=c['tetra']['stt'], speedF=c['tetra']['speedF'])
        frames.append(row)
    seed = None
    if cap is not None:
        s = cap[0]
        seed = dict(proc=s['proc'], link=s['link'], tetra=s['tetra'])
    fix = dict(source=os.path.basename(dtm), F0=f0, nframes=nframes,
               note="cap f == DTM game-frame F0+f; delivered decode == captured pad (0 mismatch f0..f45); "
                    "movie ends at group %d (f45), f46+ free-run holds stick 111,111. Edge frames are "
                    "+-1 jitter-ambiguous (single-stepped capture); flip MAGNITUDES are jitter-safe." % (
                        len(port0) // 4 - 1),
               seed=seed, frames=frames)
    if write:
        with open(out, 'w') as f:
            json.dump(fix, f, indent=1)
        print("wrote %d frames (F0=%d) -> %s" % (nframes, f0, out))
    return fix


def check(dtm=DTM_DEFAULT, cap_path=None, nframes=48):
    """Print the delivered-input vs captured-pad alignment table (no write)."""
    port0 = load_port0(dtm)
    f0 = find_f0(port0)
    cap = json.load(open(cap_path))['frames'] if cap_path else None
    print("F0 (cap f0 == DTM game-frame) =", f0, " total game-frames:", len(port0) // 4)
    print(" f | inp sx,sy A L tl | decode(ang,msd) | cap pad(val,ang,a,l) | match")
    nmis = 0
    for i in range(nframes):
        inp = frame_input(port0, f0 + i)
        r = main_stick_decode(inp['stickX'], inp['stickY'])
        ang, msd = r if isinstance(r, tuple) else (r, 0.0)
        line = "%2d | %3d,%3d %d %d %3d | %5s %.3f" % (
            i, inp['stickX'], inp['stickY'], int(bool(inp['buttons'] & 0x100)),
            int(bool(inp['buttons'] & 0x40)), inp['triggerL'],
            ('%5d' % ang) if ang is not None else ' None', msd)
        if cap and i < len(cap):
            p = cap[i]['pad']
            ok = (int(bool(inp['buttons'] & 0x40)) == int(p['l'])
                  and int(bool(inp['buttons'] & 0x100)) == int(p['a']) and abs(msd - p['value']) < 0.01)
            nmis += not ok
            line += " | %.3f %5d %d %d | %s" % (p['value'], p['angle'], int(p['a']), int(p['l']),
                                                'ok' if ok else 'MIS')
        print(line)
    if cap:
        print("mismatches:", nmis, "/", nframes)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    kw = dict(a.split('=', 1) for a in args if '=' in a)
    capp = kw.get('cap')
    if args and args[0] == 'check':
        check(dtm=kw.get('dtm', DTM_DEFAULT), cap_path=capp, nframes=int(kw.get('n', 48)))
    else:
        build(dtm=kw.get('dtm', DTM_DEFAULT), cap_path=capp, out=kw.get('out', OUT_DEFAULT),
              nframes=int(kw.get('n', 56)))
