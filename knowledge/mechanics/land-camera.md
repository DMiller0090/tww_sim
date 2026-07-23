# Land camera (manualCamera / csangle on land)

**Answers:** What drives `csangle` while walking/rolling on land? Is the land camera a follow
spring chasing Link? How do the C-stick, L-target presses, and Link's position each move the
camera? What did the courtyard Tetra-push planner need modeled, and where is the port?
**Status:** LIVE-VALIDATED 0-ULP (2026-07-23). `tww_sim/core/camera/land_cam.LandCamera`
reproduces a fully-chained 120-frame live capture bit-exactly - every committed `csangle`, the
whole view-cache globe (radius/elevation/yaw), the center chase, and the work springs - across
settled manual camera, active C-stick orbit, four followCamera blip frames, and two lock-on
windows (gate `tests/test_land_cam.py`, oracle `fixtures/courtyard_cam_oracle.json`).
**Source:** JP Ghidra decompiles (TWW_JP_NEW3/main.dol): `manualCamera` @ `8017527c`,
`followCamera` @ `80166bd4`, `nextMode` @ `80160ed8`, `Run` @ `80160260`,
`limited_range_addition` @ `80161f70`; style table read from the live JP binary
(`0x803485ac + idx*0x84`). The zeldaret `d_camera.cpp` is Nonmatching/empty for exactly these
functions (`manualCamera` has no body) - see the gotchas below.

---

## The structural fact: land camera yaw is INPUT, not emergent

On land, `csangle` (`dCam_getControledAngleY` = `Inv(mDirection.inc)`) is owned by
**`manualCamera`** (camera mode 12), not by a follow spring chasing Link:

- The yaw **target** (`mWork` globe `m3A8.inc`) moves ONLY with **C-stick X**:
  `rationalBezierRatio`-shaped ratio × `styleParam[24]` (= 8°/frame for the courtyard style
  MM03), integrated in degrees and re-truncated to s16 each frame
  ([`cam_bezier.step_cam_target`](../../tww_sim/core/camera/cam_bezier.py)).
- The view-cache globe **chases** that target at fixed cushions (yaw 0.66/frame, elevation
  0.66-or-0.33, radius 0.66-or-0.33 - `styleParam[21]`/`[20]`).
- **Link's motion moves only the camera CENTER** (and hence the eye position): a per-axis
  cushioned chase of `attentionPos + (0, m398, 0)`, cushions `m3B0/m3B4` springing to
  0.7/0.25. The center chase never touches the yaw.

So with a neutral C-stick, land `csangle` is (asymptotically) **constant** no matter what Link
does - the "camera chases the backslide at up to 116 BAM/frame" reading of the courtyard
captures (session 17) was WRONG: those swings were the TAS's **own C-stick inputs** held
through the window. For a planner this turns the camera from a coupled dynamic into a directly
commanded input channel. C-stick Y moves the center height (`m398`, `limited_range_addition`
clamped), the orbit radius (rate `styleParam[14]`, clamp `[p11, p12]`), the elevation (rate
`p19` deg, clamp `[p16, p17]`), and the fovy - all springs with the same 0.66/0.33 cushions.

## Mode sequencing (why mode 12 persists)

`nextMode` keeps `m144 = 0` while the C-stick is deflected downward (`cy <= 0` and
`cval > 0.3`), and `m144 == 0` routes to mode 12 **before** the lock-on branches - so the
manual camera persists through L-target windows (lock-on only re-aims the CENTER, below).
Once in mode 12, it exits only on an L rising edge (`m19B`, analog trigger > 0.2, delay-free)
or when the C-stick is neutral AND the radius has recentered (< 60 u - never, at ~400 u).
Each L press therefore produces a **1-frame mode-0 (followCamera) blip**: the follow INIT
recomputes the view globe from `eye − center` (a globe→xyz→globe round-trip that shifts the
yaw a few BAM) and runs one frame of its 5-frame approach ramp; the next frame re-enters
mode 12 (`onStyleChange` zeroes `m11C` → manual re-init).

While `LockonTruth()` (L-lock incl. the RELEASE fade - same lifetime as the
[attention lock](../../harness/tetrapush/README.md#plan--status)),
the manual center target blends toward `relationalPos(player, target, offset, 0.5)` - the
player↔target midpoint plus a view-yaw-scaled pullback - ramping in/out by 0.05/frame
(`m394`), which is how the L pulses nudge the camera during the untarget cycles.

## The port

| Piece | Where |
|-------|-------|
| Per-frame loop (manual + follow blips + nextMode + Run tail/bumpCheck commit + DMC) | [`tww_sim/core/camera/land_cam.py`](../../tww_sim/core/camera/land_cam.py) |
| fp-faithful `cSAngle`/`cSGlobe`/`cSPolar` (frsqrte-Newton sqrt, `cM_atan2f` round-trip, MSL sin/cos) | [`tww_sim/core/camera/cam_angle.py`](../../tww_sim/core/camera/cam_angle.py) |
| C-stick shaping (`rationalBezierRatio`) + raw-byte C-stick decode | [`tww_sim/core/camera/cam_bezier.py`](../../tww_sim/core/camera/cam_bezier.py) |
| Live oracle + 0-ULP chained gate | `fixtures/courtyard_cam_oracle.json`, [`tests/test_land_cam.py`](../../tests/test_land_cam.py) |

Style parameters are per-room-type: the port carries the two styles the courtyard uses
(MM03 manual, FN02 follow-blip), **read from the live JP binary** - style indices via
`dCamera_c.mCurStyle` (`cam+0x510`), rows at `0x803485ac + idx*0x84` (alg u32, param f32×30,
flags u16 @+0x7C, name @+0x80). No BG collision is modeled (open-floor regime; the oracle
proves no line check fired in the window).

## Gotchas (hard-won)

- **The zeldaret decomp is unusable for these functions.** `manualCamera` is an empty stub;
  `followCamera`/`lockonCamera` are Nonmatching with a *wrong header binding*: the
  `cSGlobe` SETTER `U`/`V` methods are swapped in `include/SSystem/SComponent/c_angle.h`.
  Binary truth (JP fns `cSGlobe::U` @ `800b13d8`, `V` @ `800b4d50`): **U = yaw (+6),
  V = elevation (+4), for getters AND setters** - no swap. Port from the JP Ghidra pseudo-C
  (raw field offsets), never from the decomp source text.
- **The source style table lies.** `d_cam_style.cpp`'s JP-guarded MM03 row (cushion 0.5,
  zoom 27, pitch clamp [-5,30]) does not match the shipped JP binary (0.66, 20, [0,30]).
  Read the rows from the DOL/RAM.
- Style params must be **f32-rounded** before use (`0.7` ≠ f64 0.7 - a 1-ULP spring drift).
- The center-cushion init distance is `PSVECSquareMag` (paired-single, fused `z·z + x·x`)
  - a plain single-precision sum is 1 ULP off.
- `cSAngle::Degree/Val(float)` are trunc-toward-zero s16 conversions; the yaw integration is
  degree-space float, so the s16 target can sit still for small stick values (the
  [swim-camera](camera.md) ω-table quantization, same family).
- Player `mHeight` (heightOf) = **125.0** for Link (`la+0x2AC`), used by the follow-blip
  approach length (`m37C = trunc(3.8·sqrtf(dist/height)) + 1`).

## Open

- The DMC system (frozen-yaw main-stick mode) is ported but never fires in the courtyard
  window (needs `status0` bits) - unvalidated.
- `followCamera`'s main (post-approach) path and `lockonCamera` are NOT ported (they raise);
  no land regime observed so far reaches them (mode 12 wins while the C-stick is held, and
  blips last 1 frame).
- Player status words (`status0/status1`) are inputs, 0 throughout the oracle window; a
  regime that sets them (swim, hang, first-person) needs the override branches filled in.
- Feeding the planner: wire `LandCamera` into `from_f0.FreeRun` in place of the injected
  csangle stream (the [Tetra-push planner](../../harness/tetrapush/README.md#plan--status)).
