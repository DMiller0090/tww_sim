# The Co-centre "two ports" seam - open sessions 88-89, settled on console session 90

**status: historical.** Superseded by [model/anim-frame-is-f32.md](../model/anim-frame-is-f32.md) (the
root cause) and the settled section of
[mechanics/link-co-centre.md](../mechanics/link-co-centre.md#the-two-ports-and-what-was-actually-between-them).
Kept because the diagnosis was right about the correlation and wrong about the LAYER, and that is a
reusable mistake.

## What was claimed, and when

**Session 88.** The cross-engine pre-flight rejected 4 of 19 confirmed candidates. Two of them had the
composite refusing a 49.86 u lunge that `ShoveCtx` scored genuine (0.15 u), and one of those two was
the frame-minimal survivor. Recorded as *"agreement is a property of the CANDIDATE"* -- razor rule 7 --
and promoted from a diagnostic to a filter.

**Session 89.** Traced all four to one code seam: `from_f0._computed_center` -> `FootFK.body_co_center`
(rebuilt from the pose driver's stored old pose) against `entry_search.fast_schedule` ->
`body_cyl.roll_co_chain_consts` (the `rollf` anim sampled directly), agreeing only to **1-2 ULP**.
Census: 4 of 4 rejections sit on a frame where the two differ, 0 of 36 ATTACK-gate drops do, 1 of 15
kept does. Causal: swap the composite onto the search's centre and all four agree, two flipping to the
identical 49.8582 u lunge. Cost measured at 4 candidates and **zero frames**.

Session 89 deliberately changed neither engine and recorded the question as OPEN, because both console
captures in hand (s86, s88) fell on candidates where the two paths agree -- measured, 0 frames changed
on the s86 roll -- so neither discriminated. `roll_co_center` was console-gated 0-ULP for the courtyard
leans; `body_co_center` was live-pinned only to a `<=6.1e-5 u` **tolerance**, about 1 ULP at those
magnitudes. Suggestive, not evidence. That restraint was right: picking the tighter-sounding gate would
have been razor rule 8 again.

## What overturned it

Session 90 delivered a blocked candidate (`rejected[0]` of the s89 pass: plan `[0,186,98,1,200,108,4]`,
m351C 64915) at three truncate-and-read samples. The console clipped -- 49.8582 u off `old`, bit-
identical to `body_cyl`, on the cut frame and on two pre-cut controls, both actors.

Then the ULP-level diff moved the answer one layer down: **neither port was wrong.** They were sampling
`rollf` at two different f32 frames, because `FrameCtrl` stored the Python double `1.1` that
`enter_roll` passes where `J3DFrameCtrl::mRate` is f32, and at roll frame 2.2 -> 3.3 the true f32 sum is
an exact tie. Fixed at the `FrameCtrl` boundary, the two ports agree bit-for-bit, the default composite
reproduces the capture 0-ULP, and all four rejections deliver -- 55 of 55, frame floor unchanged at 4.

## What to carry forward

- **"A property of the candidate" was a code seam not yet named** (razor rule 9, correct). **And a code
  seam can itself be a symptom**: two implementations that disagree may both be faithful, and be fed
  different inputs. Ask what each one is *given* before asking which one is right.
- **The measured cost was accurate and the reason it was small was not.** "4 candidates, zero frames" was
  read as evidence the seam was peripheral. It was one f32 tie in the shared anim engine.
- **The experiment design is the transferable part.** With every capture in hand blind to the question,
  the move was not a better argument -- it was finding the candidate where the two answers are 49.9665 u
  apart instead of 1 ULP, so a single run could not come back ambiguous.
- The pre-fix numbers survive in `fixtures/courtyard_centre_seam_s90_console.json` (`the_split`), and
  `fixtures/courtyard_entry_s89_hits.json` is the same pass as the pre-fix engine filtered it.
