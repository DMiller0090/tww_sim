# Neutral dip (the cruise "pump")

**Answers:** What is a neutral dip and why does it save speed? When is it effective? How is it
different from an ESS pump?
**Status:** validated (planner uses it; live-confirmed plans).
**Source:** decomp exit-release math; live 2026-06-27; A* planner.

---

## What it is

A **1-frame neutral tap inserted mid-ESS-cruise** — the *inverse* of an [ESS pump](../mechanics/pumps.md).
It exploits the [ESS→neutral exit](../mechanics/neutral.md#ess--neutral-exit-release_ess_speed): the
single state-54 frame is the EXIT frame of the prior ESS, so v is set to `af_drag(v, anim)` —
**lossless at the head-bob peak (|cos| = 1)** — and the flat −2 neutral decay is **skipped** that
frame (you re-enter ESS before sustained neutral begins).

So a dip taken at the anim peak DODGES the −2 loss: that frame costs ~0 potential speed, then you
resume ESS at −1/6. Net ≈ **+0.833 saved** vs two flat-neutral frames. Cost: the −3 facing-flip
transient on re-entry, amortized across many dips.

## When it's effective

**Low speed + high air only.** There ESS displacement ≈ neutral displacement, so a dip is a near-free
win. At [strobo bands](../mechanics/strobo.md) / high speed, ESS is already efficient → dips are NOT
wins (use sustained ESS + [reboost](reboost.md) instead). **Dip at the anim peak.**

Validated on the A*-best 200k plan: every cruise dip lands its *release* frame on the head-bob peak
(`af_drag` retention ≈ 100%, so the exit is near-lossless). But dipping at *every* peak over-dips and
LOSES — the optimizer is selective. The planner's [speed-retention prune](../model/planner.md#search)
encodes exactly this: it drops the off-peak exits (which would cut > 2% of `|v|`) and keeps the
near-peak ones.

## Measured

The A*-best 200k plan interleaves **34+ neutral dips** with ESS → a **6-frame save** over the
no-pump baseline (555 vs 561 frames), live-validated.

## Don't confuse with mid-swim ESS pumps

A neutral dip is a state-54 frame carrying the exit-release speed (re-entry tax amortized across many
dips). Mid-swim **ESS pumps** (neutral→ESS bursts) are off by default: the
[x598 scramble](../mechanics/pumps.md#the-x598-scramble) makes their landed phase hypersensitive
(though the sim models it exactly), and pumps give no cruise payoff — see
[model/planner](../model/planner.md#why-mid-swim-pumps-are-off-by-default).

## See also

- [Neutral](../mechanics/neutral.md) · [Pumps](../mechanics/pumps.md) · [Phase ordering](phase-ordering.md).
