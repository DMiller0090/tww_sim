# Link's Co cylinder centre - animation-driven, and it takes the turn lean twice

**Answers:** Where is the cylinder that pushes other actors, and why is it not Link's feet? Which
lean(s) tilt it, and which frame's value does each read? Why does a roll off a curved approach push
differently from a straight one? My Co centre is 0-ULP against a live roll capture and still wrong -
how?
**Status:** validated live, with ONE open question. The midpoint port is bit-exact vs the game's
`mCyl` on a pinned roll (`fixtures/hyrule_roll_lean.json`) and the **two-lean** form is bit-exact vs
the courtyard console across a whole clip roll at leans an order of magnitude larger
(`fixtures/courtyard_clip_s86_console.json`). OPEN: the two ports below disagree by 1-2 ULP on
isolated frames and no capture yet discriminates - see
[the two engines](#the-two-engines-and-the-1-2-ulp-between-them). The push that consumes it is
[actor-push.md](actor-push.md).
**Source:** `daPy_lk_c::setCollision` (`d_a_player_main.cpp:9748-9754`), `setWorldMatrix` (`:11551`),
`setMoveSlantAngle` (`:11561`), `mpCLModel->calc()` (`:11591`), `jointBeforeCB` (`:350-357`).
Code: [`tww_sim/core/anim/body_cyl.py`](../../tww_sim/core/anim/body_cyl.py) (`roll_co_center`,
`roll_co_chain_consts`, `co_leans`) and
[`foot_fk.body_co_center`](../../tww_sim/core/anim/foot_fk.py) (every pose, not just rolls).

---

## Where the centre is

`setCollision` puts Link's Co cylinder at the **horizontal midpoint of the root and neck joints**,
read from the *world* anim matrices:

    spD0.x = 0.5 * (getAnmMtx(root)[0][3] + getAnmMtx(neck)[0][3])        # same for z with [2][3]

So it is **animation-driven**, not feet-centred: it sways ~16-22 u from `current.pos` while walking
and **leads the feet by 10-31 u during a FRONT_ROLL lunge** (peaking around roll frame 5-6). Using
the feet as a proxy is wrong by that much, which is enough to decide a seam clip.

Vertical is the lower toe joint (`= current.pos.y` in FRONT_ROLL). Radius/height:
[reference/constants-npc.md](../reference/constants-npc.md#collision-actor-co-push).

## The two body leans

The MOVE turn lean `m351C` reaches that midpoint through **two** terms, and they read the value on
**different frames**. Both are needed; either alone is exact only while the lean is small.

| term | what it is | which lean |
|------|-----------|-----------|
| base tilt | `setWorldMatrix`'s `ZXYrotM` z-tilt on `worldBase` (`:11551`) | the **DRAW** lean - the value before this frame's update (`LandState._draw_lean`) |
| `body_chn` twist | `jointBeforeCB` post-multiplies `CL_JNT_BODY_CHN`'s quat by `Rx(-mBodyAngle.z)` (`:350-357`) | the **POST-update** lean (`m351C >> 1`), because `setMoveSlantAngle` (`:11561`) runs before `mpCLModel->calc()` (`:11591`) |

The base is one lean-update BEHIND the twist -- `setWorldMatrix` builds the base before
`setMoveSlantAngle` moves `m351C`, and the callback runs after both. `body_cyl.co_leans(link)`
returns the pair off a just-stepped `LandState`; feed them as
`roll_co_center(..., shape_z=base, body_lean=twist)`, and the same to `roll_co_chain_consts` so the
baked chain the native `ShoveCtx` sweeps carries it too. The other `jointBeforeCB` root tilt
(`m34F2`/`m34F4`) is 0 outside damage/ice-slip.

`m351C` decays ~35%/frame, so on a straight-approach roll (lean 0) both terms are no-ops and the
clean pose is already exact. That is why the lean showed up as an "early roll frames" residual.

## How big the twist is, and the trap in measuring it

`euler_to_quat` halves the angle and reads `jmaSinTable[(u16)angle >> 4]`, so **below roughly 30 BAM
of lean the twist rounds to the identity and is a bit-exact no-op**. Above it, it grows fast: at
`m351C >> 1` = **-388** (what a roll off a curved approach carries) it moves the centre ~**0.35 u**,
which is ~0.17 u of push per frame and then compounds through the plow.

That bucket is the trap. The purpose-made live lean capture never exceeds 28 BAM past its exempt
entry frames, so it cannot decide the term in either direction -- and for a year it was recorded as
ruled out on the strength of that capture, while the search engine that consumes the baked chain
scored every candidate at the wrong centre. See
[history/co-centre-body-chn-twist.md](../history/co-centre-body-chn-twist.md).

**Rule:** record the REGIME a capture covers next to the claim it proves. `tests/test_body_cyl.py`
asserts the lean bound of its own fixture, so a capture with a real lean makes the gate demand the
term rather than quietly permitting it.

## The two engines, and the 1-2 ULP between them

Two ports compute this, and they are **not** the same arithmetic:

- [`foot_fk.body_co_center`](../../tww_sim/core/anim/foot_fk.py) - **every** pose the anim driver
  produces (walk/dash blends, ATN strafes, rolls including the entry oldframe-morf), rebuilt from
  the stored old pose: local quat/trans/scale -> matrix -> chain. This is what the courtyard
  composite runs (`from_f0._computed_center`).
- [`body_cyl.roll_co_center`](../../tww_sim/core/anim/body_cyl.py) - the clean single-anim `rollf`
  pose sampled directly at `roll_frame`, plus `roll_co_chain_consts`, its exact decomposition into
  position-independent per-level f32 adds. This is what the native `ShoveCtx` bakes. It does not
  model the roll-frame-0 oldframe-morf (`initOldFrameMorf(mRoll.field_0x14=2.0, 0, 0x2A)`).

Same quantity, two routes, and they part company by **1-2 ULP on isolated frames**. At the razor
that is the entire verdict. Over the session-88 candidate population every cross-engine rejection
(4 of 4) has a roll frame where the two centres differ and no ATTACK-gate drop (0 of 36) does; put
the composite on the search's centre and all four agree, two of them flipping from the composite
refusing to move Link at all (0.1534 u) to the identical **49.8582 u** lunge. The rejections were
never a property of the candidates - they are this seam, crossed.

**Which port is right is OPEN.** Neither console capture can decide it: on both the two paths agree
on every frame, so the composite is byte-identical either way. `roll_co_center` is console-gated
0-ULP for the courtyard roll leans; `body_co_center` is live-pinned only to a **<=6.1e-5 u
tolerance**, which is about 1 ULP at the magnitudes involved - suggestive, not evidence. The
experiment that settles it is a delivery on one of the two **blocked** candidates, where the two
centres predict 49.8582 u and 0.1534 u; one console run separates them for the whole population.

On this population the seam is worth 4 candidates and **zero frames** (the frame floor is 5 either
way), which is why it is recorded rather than chased.

Gates: `tests/test_centre_seam.py` (the census, the causal swap, and the fact that the captures
cannot decide) + `fixtures/courtyard_centre_seam_s89.json`. `tests/test_clip_console.py` diffs the
two frame for frame against a console log - on a candidate where they agree, which is precisely why
it never saw this.

## See also

- [actor-push.md](actor-push.md) - the push this centre feeds (cyl-cyl overlap, the rank split).
- [push-magnitude.md](push-magnitude.md) - how far a push moves an actor per frame.
- [../strategy/razor-prices-every-term.md](../strategy/razor-prices-every-term.md) - why a 0.35 u
  centre error decided a clip verdict.
