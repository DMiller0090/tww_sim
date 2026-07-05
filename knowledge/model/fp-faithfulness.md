# Floating-point faithfulness — reproducing Gekko (GameCube) FP bit-exactly

**Answers:** Why does the sim run everything in f32/ctypes? Why does op *order* matter? What is
`_F32_PI` / why is `M_PI` single-precision in cos args? Why does `cM_rad2s` truncate? Why bake the
console cosine/sine tables? Which matrix/quaternion ops are FMA-**fused** and which are **non-fused**?
What is the `PSMTXQuat` `fres`+Newton reciprocal and the `_FRES` table?
**Status:** validated bit-exact against live console (RAM disasm of TWW JP + per-op live oracles).
**Source:** `tww_sim/core/fp.py` (+ `_fpc.pyx` Cython), `tww_sim/core/mathlib.py`,
`tww_sim/core/anim/{quat,fk,foot_speedf}.py`; decomp + live calibration. History:
[history/resolved-bugs](../history/resolved-bugs.md).

---

This is the **engine-wide** floating-point contract every component (swim, land, and the coming
[collision](#forward-note-collision) work) sits on. The GameCube CPU (Gekko/PowerPC 750) is
single-precision with a fused multiply-add; to be bit-exact the sim must reproduce both the width
and the fusion of every op the game executes. The rules below are each pinned to a decomp site and a
live oracle.

## Everything runs in f32 (and op *order* matters)

The sim uses `f32(...)` (`ctypes.c_float`, or the Cython `_fpc` fast path — bit-identical) for every
arithmetic step. f64 is *more* precise than the hardware and drifts the wrong way: ~0.013 anim /
0.004 v over ~480 swim frames (enough to land the wrong [exit phase](../mechanics/neutral.md)), and
~2.5 ULP over a ~115-frame land walk.

`fmuls`/`fadds`/`fsubs`/`fdivs` (PowerPC opcode 59) are single: compute in f64, round once to f32 —
modeled as `f32(a*b)` etc. `fmul`/`fadd` (opcode 63) are true f64. **Op order is part of the
contract:** `af_drag` and `release_ess_speed` use *different* f32 orderings (two different decomp
expressions); sharing one ordering left a ~2 ULP error that the
[x598 scramble](../mechanics/pumps.md#the-x598-scramble) amplified into a 0.07 speed jump at pump
exits.

## `M_PI` in a cos/sin arg is SINGLE precision (`_F32_PI`)

The compiler emits `f32_expr * M_PI` as `lfs f, M_PI; fmuls` — a **float** constant load + a
single-precision multiply, not a double multiply. So the argument is `f32(f32(pi) * x)` with
`f32(pi) = 3.1415927410125732` (~1 ULP above double π). Use `mathlib._F32_PI`, never `math.pi`, in
any argument fed to a console `cM_fcos`/`cM_scos`. Verified sites: the neutral-release cos
(`procSwimWait_init`) and the head-bob cos (`posMoveFromFootPos`). This 1-ULP-of-π difference flips a
truncated cos-table cell at knife-edge angles — it **was** the pump-300k desync (dip 43 cell 2003 vs
live 2004, x598-amplified). Order within the arg matters too: the console computes `getFrame/getEnd`
first (`fdivs`) *then* `*pi` (`fmuls`), i.e. `f32(f32(anim/23) * f32(pi))`, not `(pi*anim)/23`.

Pure geometry (world x/z bearings; facing via the s16 `cM_scos_s16`, which takes no π) and
display/heuristic metrics do **not** need `_F32_PI` — only args that reach a console `cM_fcos`.

## `cM_rad2s` truncates (round-toward-zero)

`cM_rad2s = (s16)(fmod(rad, 2π_f64) * 10430.3779296875)` with **truncation** (`fctiwz`, opcode
`0xfc00001e`), not round-to-nearest. The `fmod` and scale multiply are f64; the s16 result then
indexes `JMASCos = cosTable[(u16)v >> 4]` (low 4 bits dropped → 4096-entry table).

## Console cosine and sine tables

`cM_scos` indexes the **real console cosine table** dumped live from `jmaCosTable @ 0x80498168`, not
`math.cos`: a PowerPC-libm-built table differs from an x86 recompute at **2964/4096 entries** (max
4.17e−7). x598-amplified, that 1 ULP was a 0.07 speed jump at pump exits. It is 4096 entries indexed
by the s16 angle with the low 4 bits truncated (`index >> 4`, no interpolation).

`JMAEulerToQuat` uses `JMASSin`/`JMASCos` off a **separate** console `jmaSinTable`
(`jmaCosTable = jmaSinTable + 1024`, `jmaSinShift = 4`, size 4096) — **not** a −1024 view of the
cosine table; the old wrap-around reconstruction was 1 ULP off at 816/4096 entries. Both baked tables
(`core/tables/cos_table.bin`, `sin_table.bin`; `mathlib._COS_TABLE`/`_SIN_TABLE`) were re-verified
against the live console (`jmaSinTable` ptr @ `0x803EAE28`): **0 mismatches** across all 4096 sin AND
cos entries. The tables are not a source of any remaining residual.

Related: `J3DFrameCtrl::update` is replicated as a **repeated f32 subtraction loop** (not a single
modulo) so post-x598 the anim loops down with the console's exact rounding.

## FMA fusion vs. non-fusion (the load-bearing distinction)

A single-precision fused multiply-add computes `a·b ± c·d` with **one** rounding; a non-fused
sequence rounds each product first. Whether a given expression fuses depends on how the game's code
was compiled — and it varies op by op. Getting this wrong is a 1-ULP error that pos/anim accumulation
can amplify. `core/fp.py` provides the faithful primitives (`fmadds`/`fmsubs`/`fnmsubs`/`fnmadds` +
the plain `fmuls`/`fadds`/`fsubs`/`fdivs`); a single FMA via one f64 intermediate is provably the
correctly-rounded single FMA (2·24+2 = 50 ≤ 53 mantissa bits).

**Fused** (verified op-for-op against the paired-single asm):
- **`PSMTXConcat`** — `ab[i][j] = fmadds(a_i2, b_2j, fmadds(a_i1, b_1j, fmuls(a_i0, b_0j)))`, `+a_i3`
  on the translate column via `fmadds(1, a_i3, accum) == fadds`.
- **`PSMTXMultVec`** — `dst = (m0·sx + m2·sz) + (m1·sy + m3)`, two `fmadds` partials joined by
  `ps_sum0`/`fadds`.
- **`cXyz::absXZ`** — `f31_2 = sqrtf(abs2XZ)` with `abs2XZ = fmadds(dz, dz, fmuls(dx, dx))` (one
  fused round), and `sqrtf` = `frsqrte` seed + 3 Newton refines in double then `f32(x·guess)`.
  Ported as `foot_speedf._absxz` — use this, **not** `math.hypot`.

**Non-fused** (each product separately f32-rounded, then combined):
- **`JMAEulerToQuat`** (`JMath.cpp:41`) — each quaternion component is `(a·b) ± (c·d)` with BOTH
  products separately rounded. Fusing `x`/`y` here put the planted-foot jnt34 quat 1 ULP off.
- **Blend translate/scale** — `mDoExt_MtxCalcAnmBlendTblOld::calc` (`m_Do_ext.cpp:1183`) blends
  `info1.mTranslate·f30 + info2.mTranslate·ratio` (`f30 = 1−ratio`) **without** FMA contraction; a
  fused `fmadds` put blend-frame joint translates 1 ULP off (e.g. jnt31.z). The oldframe-morf blend
  was already non-fused.

## PSMTXQuat reciprocal and the FRES table

`mDoMtx_quat` is retail **`PSMTXQuat`** (paired single), NOT `C_MTXQuat`: the off-diagonals are
**fused then scaled** — `m[0][1] = (x·y − z·w)·s` via `ps_msub`. The scale `s = 2/denom`
(`denom = w²+x²+y²+z²`) is computed with the console's **`fres` reciprocal estimate + a Newton
refine**, exactly as the asm (`quat._recip2_of`, `scale_mode='newton'`, the default). The `_fres`
emulation must match Dolphin's `fres_expected` table byte-for-byte: `_FRES_BASE` (32-entry base/dec
table; `interp = base − (dec·frac + 1) >> 1`) had **8 wrong high-index entries** (idx 22/24/26–31),
so the seed was ~1 ULP low **for `denom < 1`**.

This only bit the **WALK↔DASH blend** poses: `JMAQuatLerp` does not renormalize, so a lerped quat's
`denom` drops just below 1 → the high table indices; single-anim poses have `denom ≈ 1` → index 0
(always correct), which is why non-blend frames looked fine with the broken table. `'newton'` is the
right mode: at a single-axis joint's half-ULP division midpoint (`denom = 1 − 2⁻²⁴`) the console lands
`fdivs − 1 ULP` (round-to-even); raw `fdivs` is +1 ULP and the plain `_fres` table is −7. With the
corrected table + Newton, the leg chain jnt0..jnt33 is bit-exact vs the live `anmMtx`. See
[anim-engine](anim-engine.md) for how these feed the foot FK.

## Cython fast path

`core/_fpc.pyx` (`cpdef inline <float>`) is a drop-in, **bit-identical** replacement for the ctypes
f32 ops (`fp.py` imports it, falls back to ctypes) — ~2.4× on the swim planner. Build with the
scratch `_build_fpc.py`. Compiling the whole anim stack (`fk`/`quat`/`j3d_eval`) was faster still but
a 32-bit-C overflow in `quat._fres` (`1<<52`) broke it — kept in ctypes for now.

## Forward note (collision)

The upcoming seam-clip / collision work is a boolean knife-edge decided by `fmadds`/`frsqrte`
rounding — the same FP contract, one step more sensitive (a single flipped ULP flips the clip). The
fused primitives and `frsqrte` seed above are the on-ramp; `core/fp.py` is the home for the collision
math when it lands.

## See also

- [Anim engine](anim-engine.md) (how the fused/non-fused rules assemble the foot FK) ·
  [Swim sim](swim-sim.md) · [Land sim](land-sim.md) · [Pumps / x598](../mechanics/pumps.md) ·
  [history/resolved-bugs](../history/resolved-bugs.md).
