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


def _sar4(v: int) -> int:
    """Arithmetic right shift by 4 (ASM `sar r,4`).

    ``v`` is an already-signed field (the bridge returns signed dwords), and
    Python's ``>>`` is arithmetic on signed ints — so this is just ``v >> 4``.
    (Do NOT re-apply a sign conversion here: a negative ``v`` would then be
    shifted toward -1e8 instead of the correct small negative.)
    """
    return v >> 4


def build_draw_list(state) -> None:
    """Emit a draw command per sprite (recovered from 0x1183b1).

    For each sprite (a cell pair): screen X = world offset + the sprite's
    position; the two animated cell accumulators (>>4) become the command's
    W and H; flags = 0.  Iterates sprite_count == cell_count >> 1.
    """
    for spr in state.sprites():
        cmd = state.alloc_draw_command()
        cmd.set(state.world_x + spr.position,
                _sar4(spr.coord_a) & 0xFFFF,
                _sar4(spr.coord_b) & 0xFFFF,
                0)
