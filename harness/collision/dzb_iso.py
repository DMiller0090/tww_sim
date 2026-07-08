"""Read a room's collision (DZB) straight from the extracted game disc, with NO Dolphin and no need to
load the room in-game. Feeds the same ``region_tris`` the live reader (``seam_scan.read_region_tris``)
produces, so the seam-clip scanner runs on any room offline.

Pipeline: RARC archive (Yaz0-decompress if needed) -> ``room.dzb`` -> vertices + triangles ->
world-transform by the stage ``MULT`` room placement (translation + Y-rotation) -> per-triangle planes
via the bit-exact :func:`tww_sim.core.collision.calc_pla` (the DZB stores NO planes; the game computes
them at load with the same ``cM3d_CalcPla``, so calc_pla reproduces the RAM planes exactly).

Disc layout (extracted): ``<extract>/files/res/Stage/<Stage>/Room<N>.arc`` (collision ``room.dzb``)
and ``Stage.arc`` (``stage.dzs``, the ``MULT`` room-placement chunk). The extract dir is read from
``dolphin.local.json`` (``tww_extract_dir``).

    python -m harness.collision.dzb_iso stage=M_Dai room=18            # scan a room for clips
    python -m harness.collision.dzb_iso stage=M_Dai room=18 no-standable
"""
import json
import math
import os
import struct
import sys

from tww_sim.core.collision import Tri, calc_pla

WALL_NY_MAX = 0.03
GROUND_NY_MIN = 0.5


def yaz0_decompress(src):
    """Yaz0 (Nintendo LZ) decompress; returns ``src`` unchanged if not Yaz0-tagged."""
    if src[:4] != b"Yaz0":
        return src
    n = struct.unpack_from(">I", src, 4)[0]
    p, dst = 16, bytearray()
    while len(dst) < n:
        code = src[p]; p += 1
        for i in range(8):
            if len(dst) >= n:
                break
            if code & (0x80 >> i):
                dst.append(src[p]); p += 1
            else:
                b1, b2 = src[p], src[p + 1]; p += 2
                dist = ((b1 & 0xF) << 8) | b2
                cnt = b1 >> 4
                if cnt == 0:
                    cnt = src[p] + 0x12; p += 1
                else:
                    cnt += 2
                r = len(dst) - dist - 1
                for _ in range(cnt):
                    dst.append(dst[r]); r += 1
    return bytes(dst)


def read_rarc(path):
    """Parse a RARC archive (Yaz0-aware) into ``{filename: bytes}`` (files only, flat by name)."""
    b = yaz0_decompress(open(path, "rb").read())
    if b[:4] != b"RARC":
        raise ValueError("not a RARC: %s" % path)
    info = struct.unpack_from(">I", b, 8)[0]                 # header size == info-block start
    data_off = struct.unpack_from(">I", b, 0x0C)[0]
    _, _, n_files, file_off, _, str_off = struct.unpack_from(">IIIIII", b, info)
    file_off += info; str_off += info
    out = {}
    for i in range(n_files):
        idx, _, tn, doff, dsize = struct.unpack_from(">HHIII", b, file_off + i * 0x14)
        end = b.index(b"\x00", str_off + (tn & 0xFFFFFF))
        nm = b[str_off + (tn & 0xFFFFFF):end].decode("shift_jis", "replace")
        if idx != 0xFFFF:                                   # 0xFFFF == subdirectory entry
            out[nm] = b[0x20 + data_off + doff:0x20 + data_off + doff + dsize]
    return out


def parse_dzb(data):
    """DZB (== in-RAM ``cBgD``) -> ``(verts, tris)``. Header: v_num@0, v_off@4, t_num@8, t_off@0xC;
    vertex = 3x f32 (12 B); triangle = ``u16 v0,v1,v2, plane_id, group`` (10 B). All big-endian."""
    v_num, v_off, t_num, t_off = struct.unpack_from(">IIII", data, 0)
    verts = [struct.unpack_from(">fff", data, v_off + i * 12) for i in range(v_num)]
    tris = [struct.unpack_from(">5H", data, t_off + i * 10) for i in range(t_num)]
    return verts, tris


def _stage_dir(stage, extract_dir=None):
    if extract_dir is None:
        cfg = os.path.join(os.path.dirname(__file__), "..", "..", "dolphin.local.json")
        extract_dir = json.load(open(cfg))["tww_extract_dir"]
    return os.path.join(extract_dir, "files", "res", "Stage", stage)


def room_world_transform(stage, room, extract_dir=None):
    """The room's world placement ``(tx, tz, angY_deg)`` from the stage ``MULT`` chunk (identity if
    absent). Dungeon rooms are commonly identity; sea/overworld rooms carry a real translate+rotate."""
    st = read_rarc(os.path.join(_stage_dir(stage, extract_dir), "Stage.arc"))
    dzs = next(st[k] for k in st if k.lower().endswith(".dzs"))
    nch = struct.unpack_from(">I", dzs, 0)[0]
    for i in range(nch):
        tag, cnt, off = struct.unpack_from(">4sII", dzs, 4 + i * 12)
        if tag == b"MULT":
            for j in range(cnt):
                tx, tz, ang, rm, _ = struct.unpack_from(">ffhBB", dzs, off + j * 0xC)
                if rm == room:
                    return tx, tz, ang * 360.0 / 65536.0
    return 0.0, 0.0, 0.0


def load_room_region(stage, room, extract_dir=None, transform=True):
    """Return ``(region_tris, box, stage)`` for a room's collision, world-transformed and Dolphin-free.
    ``region_tris`` matches ``seam_scan.read_region_tris``: ``dict(poly, v, n, T)`` with ``T`` carrying
    the bit-exact calc_pla plane and ``n`` its normal. ``box`` is the room's XZ/Y AABB."""
    sdir = _stage_dir(stage, extract_dir)
    arc = read_rarc(os.path.join(sdir, "Room%d.arc" % room))
    dzb = next(arc[k] for k in arc if k.lower().endswith(".dzb"))
    verts, tris = parse_dzb(dzb)
    if transform:
        tx, tz, ang = room_world_transform(stage, room, extract_dir)
        if tx or tz or ang:
            c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            verts = [(x * c + z * s + tx, y, -x * s + z * c + tz) for (x, y, z) in verts]
    region = []
    for poly, (a, b, c, _tid, _grp) in enumerate(tris):
        v0, v1, v2 = verts[a], verts[b], verts[c]
        T = Tri(v0, v1, v2)                                 # plane via bit-exact calc_pla
        region.append(dict(poly=poly, v=[v0, v1, v2], n=(T.pla.nx, T.pla.ny, T.pla.nz), T=T))
    xs = [c for t in region for c in (t["v"][0][0], t["v"][1][0], t["v"][2][0])]
    ys = [c for t in region for c in (t["v"][0][1], t["v"][1][1], t["v"][2][1])]
    zs = [c for t in region for c in (t["v"][0][2], t["v"][1][2], t["v"][2][2])]
    box = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    return region, box, stage


def main(argv):
    from harness.collision.seam_clip_check import scan_region
    stage, room, standable = "M_Dai", 18, True
    for a in argv:
        if a.startswith("stage="):
            stage = a[6:]
        elif a.startswith("room="):
            room = int(a[5:])
        elif a == "no-standable":
            standable = False
    region, box, _ = load_room_region(stage, room)
    walls = sum(1 for t in region if abs(t["n"][1]) < WALL_NY_MAX)
    grounds = sum(1 for t in region if t["n"][1] >= GROUND_NY_MIN)
    print("stage=%s room=%d: %d tris (%d walls, %d ground) box=%s"
          % (stage, room, len(region), walls, grounds,
             tuple(round(x, 1) for x in box)), flush=True)
    scan_region(region, box, require_standable=standable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
