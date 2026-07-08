"""Convert the ``_generated/seam_scan/`` per-DZB seam reports (from :mod:`scan_all_dzb`) into CSVs,
mirroring the stage-by-folder layout, for the in-Dolphin collision viewer to consume.

Each ``<stage>/<Arc>__<dzb>.md`` becomes ``<stage>/<Arc>__<dzb>.csv`` with one row per clippable seam:
    seam_x, seam_y, seam_z, init_x, init_y, init_z, dest_x, dest_y, dest_z, angle_deg
(seam vertex, the standable initial/old position, the clip destination/new position, and the interior
angle between the two walls). Output defaults to the collision viewer's data dir.

    python -m harness.collision.export_seam_csv
    python -m harness.collision.export_seam_csv src=_generated/seam_scan out=/path/to/ww/data/seam_clips
"""
import csv
import os
import re
import sys

_S = re.compile(r"^S=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)\s+interior=([-\d.]+)")
_OLD = re.compile(r"^\s+old=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)")
_NEW = re.compile(r"^\s+new=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)")
HEADER = ["seam_x", "seam_y", "seam_z", "init_x", "init_y", "init_z",
          "dest_x", "dest_y", "dest_z", "angle_deg"]


def parse_md(path):
    """Yield one row (list of 10 strings) per clippable seam in a scan .md file."""
    seam = ang = old = None
    for line in open(path, encoding="utf-8"):
        m = _S.match(line)
        if m:
            seam, ang, old = m.group(1, 2, 3), m.group(4), None
            continue
        m = _OLD.match(line)
        if m and seam:
            old = m.group(1, 2, 3)
            continue
        m = _NEW.match(line)
        if m and seam and old:
            yield list(seam) + list(old) + list(m.group(1, 2, 3)) + [ang]
            seam = old = None


def main(argv):
    here = os.path.dirname(__file__)
    src = os.path.abspath(os.path.join(here, "..", "..", "_generated", "seam_scan"))
    out = os.path.abspath(os.path.join(here, "..", "..", "..", "tww-python-scripts",
                                       "ww", "data", "seam_clips"))
    for a in argv:
        if a.startswith("src="):
            src = os.path.abspath(a[4:])
        elif a.startswith("out="):
            out = os.path.abspath(a[4:])
    n_files = n_rows = 0
    for stage in sorted(os.listdir(src)):
        sdir = os.path.join(src, stage)
        if not os.path.isdir(sdir):
            continue
        for md in sorted(f for f in os.listdir(sdir) if f.endswith(".md")):
            rows = list(parse_md(os.path.join(sdir, md)))
            if not rows:
                continue                                    # skip DZBs with no clips
            odir = os.path.join(out, stage)
            os.makedirs(odir, exist_ok=True)
            with open(os.path.join(odir, md[:-3] + ".csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(HEADER)
                w.writerows(rows)
            n_files += 1
            n_rows += len(rows)
    print("wrote %d CSVs (%d seams) to %s" % (n_files, n_rows, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
