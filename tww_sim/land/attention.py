#!/usr/bin/env python3
"""AttentionLock: the dAttention_c hold-mode lock-on state machine (the untarget-latency model).

This is the piece the Courtyard Tetra-push needed (`harness/tetrapush`): why releasing L mid-roll
does NOT untarget immediately, so the roll keeps exiting into the actor-lock proc (ATN_ACTOR_MOVE,
proc 9) for a few frames, retaining ~-25.7 EBS instead of the plain-roll-EBS -23.5.

Decomp: `d_attention.cpp` hold mode (`getOptAttentionType()==0` -> `judgementStatusHd`, 804-844).
The state is `mLockOnState in {NONE, LOCK, RELEASE}`. `checkAttentionLock()` (daPy_lk_c) is
`mpAttention->Lockon()` = `LockonTruth() || flag`, and `LockonTruth()` (1049) is
`LOCK || (RELEASE && LockonTarget)`. So a target stays "locked" (drives proc 8/9 in
`checkNextMode`) through the whole RELEASE, which ends only when the lock-on reticle fade-out anim
(dRes YJ_DELETE) completes -- when `runDrawProc` clears `AttnFlag_40000000` (653-698). That
animation length is the untarget latency (`FADE_FRAMES`), an ANIMATION constant, not a tuned knob.

Purely additive to the land sim: with no locked target (`target_present=False` every frame -- every
existing single-actor land golden) the machine can never leave NONE, so `locked` is always False and
the dispatch/`checkNextMode` behaviour is byte-identical to before this file existed.
"""
from __future__ import annotations

# mLockOnState values (dAttention_c). RELEASE = L let go but the reticle is still fading out.
NONE, LOCK, RELEASE = 0, 1, 2

# = the reticle YJ_DELETE fade-out anim length (end=10/rate=1.0), live-measured session 6; the
# session-5 "10 vs 11" was a single-step capture double-read. Anim constant, not a knob. See README.
DEFAULT_FADE_FRAMES = 10

# chaseAttention front-of-player cone half-angle (check_flontofplayer ang_table[0], ftp bit 0x04): a
# lock-on target is chaseable only within +-0x4000 of shape_angle.y. See knowledge/mechanics/tetra-follow.md.
FRONT_CONE_HALF = 0x4000


class AttentionLock:
    """The per-frame hold-mode lock state. Feed it the (delayed) L input + whether a lock-on target
    exists this frame; read ``locked`` (== ``mpAttnActorLockOn != NULL`` == the ``checkNextMode``
    attention gate, which routes a moving exit to ATN_ACTOR_MOVE and a stopped one to ATN_ACTOR_WAIT).

    ``field_0x01a`` (judgementButton, d_attention.cpp:714): 1 on the FIRST L-held frame (rising edge),
    2 while held, 0 when released. Only ``==1`` (rising) and ``==0`` (released) gate the transitions,
    so we derive them from ``l_held`` + the previous frame's ``l_held`` rather than store the counter.
    """

    def __init__(self, fade_frames=DEFAULT_FADE_FRAMES):
        self.state = NONE
        self.FADE_FRAMES = int(fade_frames)
        self._fade = 0            # frames left in the RELEASE reticle fade (AttnFlag_40000000 timer)
        self._l_prev = False
        # GetLockonList(0) != NULL -- the stocked lock-on CANDIDATE list (setNeckAngle's unlocked
        # look-target source). Stock/free timing: knowledge/mechanics/link-head-look.md.
        self.list_present = False

    @property
    def locked(self):
        """``LockonTruth()`` for a present target = ``mpAttnActorLockOn != NULL`` = the attention
        gate ``checkNextMode`` uses to pick the ATN_ACTOR procs (LOCK, or RELEASE while fading)."""
        return self.state in (LOCK, RELEASE)

    def update(self, l_held, target_present):
        """Advance one frame (judgementButton + judgementStatusHd). ``l_held`` is the delayed L
        input already used for the ATN gate; ``target_present`` is whether a chaseable lock-on actor
        exists (the harness supplies Tetra's presence). Returns ``self`` for chaining."""
        rising = bool(l_held) and not self._l_prev        # field_0x01a == 1 (first held frame)
        prev_state = self.state
        if self.state == NONE:
            # NONE: judgementTriggerProc on the L rising edge acquires a chaseable target (747).
            if rising and target_present:
                self.state = LOCK
        elif self.state == LOCK:
            # LOCK: lost target -> NONE (judgementLostCheck 816); else L released -> RELEASE (817-819).
            if not target_present:
                self.state = NONE
            elif not l_held:                              # field_0x01a == 0 (L let go)
                self.state = RELEASE
                self._fade = self.FADE_FRAMES
        elif self.state == RELEASE:
            # RELEASE: L re-pressed -> re-lock (825-829); else end when the target is gone OR the
            # reticle fade-out anim completes -- AttnFlag_40000000 cleared (837-840).
            if rising:
                self.state = LOCK if target_present else NONE
            else:
                if self._fade > 0:
                    self._fade -= 1
                if not target_present or self._fade <= 0:
                    self.state = NONE
        self._l_prev = bool(l_held)
        # The lock-on list, as of THIS Run: kept while locked; freed (not restocked) on the
        # transition-to-NONE Run; NONE->NONE restocks from the chaseable-target gate.
        if self.state in (LOCK, RELEASE):
            self.list_present = True
        elif prev_state != NONE:
            self.list_present = False           # freeAttention on the transition Run
        else:
            self.list_present = bool(target_present)   # stockAttention every NONE-state Run
        return self

    def clone(self):
        """A per-branch copy. REQUIRED by `LandState.clone`: this machine is mutated every frame and
        it routes the roll exit (proc 9 vs 6), so a shared instance silently couples search branches
        to each other -- and to their parent -- long after they diverge."""
        c = AttentionLock.__new__(AttentionLock)
        c.state = self.state
        c.FADE_FRAMES = self.FADE_FRAMES
        c._fade = self._fade
        c._l_prev = self._l_prev
        c.list_present = self.list_present
        return c
