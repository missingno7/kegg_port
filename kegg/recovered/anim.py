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


# Second per-frame timer table (0x119e54): 12-byte records at 0x14e168 with
# {counter:+0, threshold:+4, accumulator:+8}, count in the word [0x1473cc],
# advanced by the dword step [0x1473ac].  A word counter [0x14e1be] ticks once
# per frame while the word at [[0x1473b4]] is zero.
T2_TABLE = 0x14E168
T2_COUNT = 0x1473CC
T2_STEP = 0x1473AC
T2_GLOBAL_CTR = 0x14E1BE
T2_GATE_PTR = 0x1473B4


def update_frame_timers(d: bytearray) -> None:
    """Advance the second animation-timer table (recovered from 0x119e54).

    Ticks the gated global counter, then for each record accumulates the step
    and, once the accumulator reaches the record's threshold (unsigned), wraps
    it down and bumps the record's counter.
    """
    def r32(a):
        return int.from_bytes(d[a:a + 4], "little")

    def w32(a, v):
        d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    def r16(a):
        return int.from_bytes(d[a:a + 2], "little")

    gate = r32(T2_GATE_PTR)
    if r16(gate) == 0:
        d[T2_GLOBAL_CTR:T2_GLOBAL_CTR + 2] = ((r16(T2_GLOBAL_CTR) + 1) & 0xFFFF).to_bytes(2, "little")
    count = r16(T2_COUNT)
    step = r32(T2_STEP)
    for i in range(count):
        rec = T2_TABLE + i * 12
        acc = (r32(rec + 8) + step) & 0xFFFFFFFF
        w32(rec + 8, acc)
        thr = r32(rec + 4)
        if acc >= thr:                     # unsigned; ASM `jb` skips the wrap
            w32(rec + 8, (acc - thr) & 0xFFFFFFFF)
            w32(rec + 0, (r32(rec + 0) + 1) & 0xFFFFFFFF)


def load_current_object(state) -> None:
    """Latch the current sprite definition's geometry into the working globals
    the draw path reads (recovered from 0x1195ee): width, height, and the x/y
    offsets of [0x14e158]'s sprite def."""
    obj = state.current_object
    state.cur_width = obj.width
    state.cur_height = obj.height
    state.cur_x_offset = obj.x_offset
    state.cur_y_offset = obj.y_offset


def setup_sprite_rect(state, out_ptr: int, sprite_def_ptr: int) -> None:
    """Turn a seed point into a sprite's screen bounding box (recovered from
    0x118004).

    Places `sprite_def_ptr` as the current object, latches its geometry (via
    the 0x1195ee rule), then folds the sprite's signed x/y offsets into the
    caller's rect and derives the far edges:

        left  += x_offset
        top   += y_offset
        right  = left + width  - 2
        bottom = top  + height - 2

    `out_ptr` is a 4-dword rect {left, top, right, bottom}; the caller seeds
    left/top with the base position and this accumulates the sprite's offset.
    """
    state.current_object_ptr = sprite_def_ptr
    load_current_object(state)
    rect = state.rect_at(out_ptr)
    rect.left = rect.left + state.cur_x_offset_s
    rect.top = rect.top + state.cur_y_offset_s
    rect.right = rect.left + state.cur_width_s - 2
    rect.bottom = rect.top + state.cur_height_s - 2


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
