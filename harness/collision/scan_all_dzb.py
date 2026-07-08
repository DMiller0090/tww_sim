"""Scan EVERY room/collision DZB in the extracted game for clippable seams, one output file per DZB,
mirroring the disc's ``Stage/<stage>/`` folder layout. Streams as it goes (writes each DZB's file the
moment it finishes and prints a progress line) and is resumable (skips DZBs whose output already
exists), so a long full-game run can be interrupted and continued.

For each ``Room<N>.arc`` the DZB is world-transformed by the stage ``MULT`` room placement (validated
identity for dungeons: GanonL via ISO reproduces its 40 live clips; Earth Temple room 18 = 0). Planes
are the bit-exact ``calc_pla`` (the DZB stores none). Non-room DZBs (e.g. ``Stage.arc`` door collision)
have no MULT room, so they are scanned in local coords and flagged; their world placement is unresolved.

    python -m harness.collision.scan_all_dzb                 # all stages
    python -m harness.collision.scan_all_dzb stage=M_Dai     # one stage
    python -m harness.collision.scan_all_dzb no-standable    # include non-standable geometry clips

Output: ``_generated/seam_scan/<stage>/<Arc>__<dzb>.md`` (gitignored, regenerable).
"""
import json
import os
import re
import struct
import sys
import time

from harness.collision.dzb_iso import read_rarc, region_from_dzb
from harness.collision.seam_clip_check import scan_region

WALL_NY_MAX = 0.03
GROUND_NY_MIN = 0.5
_ROOM_RE = re.compile(r"^Room(\d+)$", re.I)


def _extract_dir():
    cfg = os.path.join(os.path.dirname(__file__), "..", "..", "dolphin.local.json")
    return json.load(open(cfg))["tww_extract_dir"]


def _stage_mult(stage_dir):
    """{room_no: (tx, tz, angY_deg)} from the stage's Stage.arc MULT chunk (empty if none)."""
    sa = os.path.join(stage_dir, "Stage.arc")
    if not os.path.exists(sa):
        return {}
    try:
        st = read_rarc(sa)
    except Exception:
        return {}
    dzs = next((st[k] for k in st if k.lower().endswith(".dzs")), None)
    if dzs is None:
        return {}
    out = {}
    nch = struct.unpack_from(">I", dzs, 0)[0]
    for i in range(nch):
        tag, cnt, off = struct.unpack_from(">4sII", dzs, 4 + i * 12)
        if tag == b"MULT":
            for j in range(cnt):
                tx, tz, ang, rm, _ = struct.unpack_from(">ffhBB", dzs, off + j * 0xC)
                out[rm] = (tx, tz, ang * 360.0 / 65536.0)
    return out


def _write(path, stage, arc, dzb, xform, xnote, region, box, seams_n, clips):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = f.write
        walls = sum(1 for t in region if abs(t["n"][1]) < WALL_NY_MAX)
        gnd = sum(1 for t in region if t["n"][1] >= GROUND_NY_MIN)
        w("# %s / %s :: %s\n\n" % (stage, arc, dzb))
        w("world coords: DZB stored in world space, MULT NOT applied  (%s: tx=%.2f tz=%.2f angY=%.2f)\n"
          % (xnote, xform[0], xform[1], xform[2]))
        w("tris=%d walls=%d ground=%d  vertical_seams=%d  clippable=%d\n"
          % (len(region), walls, gnd, seams_n, len(clips)))
        if box:
            w("box=(%.1f, %.1f, %.1f, %.1f, %.1f, %.1f)\n" % box)
        w("\n")
        if not clips:
            w("no clippable seams\n")
            return
        w("## clippable seams (%d)\n\n" % len(clips))
        for r in clips:
            w("S=(%.3f, %.3f, %.3f)  interior=%.2f  disp=%.4f  %s\n"
              % (r["S"][0], r["S"][1], r["S"][2], r["interior"], r["disp"],
                 "ROLL-STAB" if r["reachable_rollstab"] else "NEEDS-PUSH"))
            w("  old=(%.5f, %.5f, %.5f)\n" % tuple(r["old"]))
            w("  new=(%.5f, %.5f, %.5f)\n\n" % tuple(r["new"]))


def main(argv):
    only_stage = None
    require_standable = "no-standable" not in argv
    for a in argv:
        if a.startswith("stage="):
            only_stage = a[6:]
    root = os.path.join(_extract_dir(), "files", "res", "Stage")
    outroot = os.path.join(os.path.dirname(__file__), "..", "..", "_generated", "seam_scan")
    outroot = os.path.abspath(outroot)
    stages = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if only_stage:
        stages = [s for s in stages if s == only_stage]
    # enumerate (stage, arc, dzbname) work items
    work = []
    for stage in stages:
        sdir = os.path.join(root, stage)
        for arc in sorted(f for f in os.listdir(sdir) if f.lower().endswith(".arc")):
            work.append((stage, sdir, arc))
    print("=== scanning %d arcs across %d stages -> %s ===" % (len(work), len(stages), outroot),
          flush=True)
    total_clips = total_dzb = errors = 0
    t0 = time.time()
    for wi, (stage, sdir, arc) in enumerate(work):
        outdir = os.path.join(outroot, stage)
        os.makedirs(outdir, exist_ok=True)
        try:
            files = read_rarc(os.path.join(sdir, arc))
        except Exception as e:
            print("  [%d/%d] %s/%s ARC-ERR %s" % (wi + 1, len(work), stage, arc, e), flush=True)
            errors += 1
            continue
        mult = None
        for dzbname, data in files.items():
            if not dzbname.lower().endswith(".dzb"):
                continue
            out = os.path.join(outdir, "%s__%s.md" % (os.path.splitext(arc)[0],
                                                      os.path.splitext(dzbname)[0]))
            if os.path.exists(out):
                total_dzb += 1
                continue                                    # resume: already done
            m = _ROOM_RE.match(os.path.splitext(arc)[0])
            if m is not None:
                if mult is None:
                    mult = _stage_mult(sdir)
                xform = mult.get(int(m.group(1)), (0.0, 0.0, 0.0))
                xnote = "MULT room %s" % m.group(1)
            else:
                xform, xnote = (0.0, 0.0, 0.0), "identity (assumed; non-room DZB, world placement unresolved)"
            try:
                region, box = region_from_dzb(data, *xform)
                if not region:
                    _write(out, stage, arc, dzbname, xform, xnote, [], None, 0, [])
                    total_dzb += 1
                    continue
                seams_n_holder = {}
                clips = scan_region(region, box, require_standable=require_standable, verbose=False)
                # recover seam count for the header
                from harness.collision.seam_scan import enumerate_seams
                seams_n = len(enumerate_seams(region, box))
                _write(out, stage, arc, dzbname, xform, xnote, region, box, seams_n, clips)
                total_dzb += 1
                total_clips += len(clips)
                tag = ("CLIPS=%d" % len(clips)) if clips else "clips=0"
                print("  [%d/%d] %s/%s::%s tris=%d seams=%d %s"
                      % (wi + 1, len(work), stage, arc, dzbname, len(region), seams_n, tag),
                      flush=True)
            except Exception as e:
                print("  [%d/%d] %s/%s::%s DZB-ERR %s"
                      % (wi + 1, len(work), stage, arc, dzbname, e), flush=True)
                errors += 1
    print("=== done: %d DZBs, %d clippable seams total, %d errors, %.0fs ==="
          % (total_dzb, total_clips, errors, time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
