"""Recovered per-frame gameplay logic for Krypton Egg (pure — no dos_re, no VM).

Each function operates on a `kegg.bridge.game_state.GameState` view and
reproduces one original routine byte-for-byte (proven by the differential
oracle in the installing hook).
"""
from __future__ import annotations


def update_anim_timers(state) -> None:
    """Advance every object's animation accumulator (recovered from 0x118345).

    Bumps the frame tick, then per object: once the tick reaches the object's
    threshold, snap the accumulator back to its reset value; otherwise advance
    it by the object's step.  All fields are signed 32-bit; the tick/threshold
    comparison is signed (ASM `jl`).
    """
    state.tick = state.tick + 1
    tick = state.tick
    for obj in state.objects():
        if tick >= obj.threshold:
            obj.accumulator = obj.reset_value
        else:
            obj.accumulator = obj.accumulator + obj.step
