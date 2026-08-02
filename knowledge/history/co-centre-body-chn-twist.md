# "The body_chn rotation contributes nothing to the Co centre" (2026-07-10 -> session 87, 2026-08-02)

> **status: historical** - this records a claim that was measured, written down, gated, and wrong,
> because the only capture available to test it could not see the term. Current truth is
> [mechanics/link-co-centre.md](../mechanics/link-co-centre.md#the-two-body-leans).
> Kept for the lesson, which is about what a live gate proves when the fixture is inside a
> quantization bucket.

## What was claimed

Porting `daPy_lk_c::setCollision`'s root/neck midpoint, the early roll frames read a residual against
the live `mCyl`. It was root-caused to the missing `setWorldMatrix` base z-tilt by `shape_angle.z` --
correctly -- and the fix was gated bit-exact against a purpose-made live capture
(`fixtures/hyrule_roll_lean.json`: Link rolling pinned at a wall so only the pose and the lean moved
the centre). The module then recorded the OTHER lean path as ruled out:

> the `jointBeforeCB` root tilt (`m34F2`/`m34F4`) is 0 outside damage/ice-slip, and its `body_chn`
> rotation (`-mBodyAngle.z`) contributes nothing to the centre (verified live: base-lean-only is 0 ULP
> on every settled roll frame; **adding the body_chn quat breaks it**).

Both halves of that parenthesis are true statements about that capture. Neither generalizes.

## What it actually is

The twist is real (`foot_fk.body_co_center` has run it since session 16, live-gated, and that is why
the courtyard composite was console-exact all along) and it takes the **POST-update** lean, one
update ahead of the base. Adding it with the OLD lean does break the fit -- which is what the
"breaks it" half had measured.

## Why the live gate could not see it

`euler_to_quat` halves the angle and reads `jmaSinTable[(u16)angle >> 4]`, so a small twist rounds to
the identity. Past the two exempt entry frames the lean capture never exceeds **28 BAM**, which is
inside that bucket: feeding the twist there is a bit-exact no-op, in both directions. The capture was
built to isolate the lean and it succeeded -- at a lean an order of magnitude below the one that
matters. A roll off a curved approach carries `m351C >> 1` of **-388**, and there the term is worth
~0.35 u of Co centre.

## What it cost

The twist was absent from `body_cyl.roll_co_chain_consts`, the baked chain the native `ShoveCtx`
sweeps -- so the entry search scored every candidate at a Co centre that was wrong for the first ~5
frames of the roll, by an amount that scales with the candidate's own turn lean. The push error
compounds through the plow (the ~1.35x/contact-frame amplifier), leaving Tetra **0.15 u** off at the
cut frame, against a razor that a **single f32 ULP** of her decides. Session 86 spent a console
delivery on the frame-minimal hit of 49 and it did not clip; session 87 named this term and
re-scored, and **42 of the 49 were false positives**.

## The lessons

- **A live gate proves the model on the fixture's own regime, not past it.** Record the regime the
  capture covers next to the claim -- here, "max lean 28" was the whole caveat and it was not written
  down. `tests/test_body_cyl.py` now asserts the capture's lean bound, so a future capture with a
  real lean makes the gate demand the term directly instead of quietly permitting it.
- **"Adding X breaks it" is a claim about X's inputs too.** The twist was tried and rejected with the
  wrong lean; the rejection was recorded as being about the twist.
- **Two engines that never meet will disagree.** `ShoveCtx` scored the entry and the courtyard
  composite delivered it, and nothing compared their per-frame output, so a term present in one and
  absent from the other was invisible for as long as both were only checked against different things.
  `tests/test_clip_console.py` now diffs them frame for frame against the same console log.
