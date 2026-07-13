"""Recovered gameplay-logic hooks for Krypton Egg (the VM bridge).

Thin adapters over `kegg.recovered` pure logic + `kegg.bridge` typed views:
each reads VM state, runs the recovered rule against a bridge view of
`cpu.mem.data`, and reproduces the routine's exact register/flag exit so it
verifies byte-exact against the ASM oracle (pm_verification.PMHookVerifier).
"""
from __future__ import annotations

from kegg.bridge.game_state import (GameState, ObjectView, SpriteView,
                                     OBJ_STRIDE, SPRITE_STRIDE, G_TABLE,
                                     G_CUR_OBJ, G_CUR_Y_OFF)
from kegg.recovered.anim import (update_anim_timers, build_draw_list,
                                  load_current_object, setup_sprite_rect, _sar4)

ANIM = 0x118345
DRAW_LIST = 0x1183B1
LOAD_OBJ = 0x1195EE
SPRITE_BOUNDS = 0x118004


def anim_timers_118345(cpu):
    mem = cpu.mem
    r = cpu.r
    entry_edx = r[2]
    state = GameState(mem.data)
    count = state.object_count
    table = state._u32(G_TABLE)

    update_anim_timers(state)              # the recovered rule mutates the objects

    # Exit-register reproduction (the routine is cdecl; ebx/esi/edi/ebp/esp
    # are restored by its epilogue, so only the scratch eax/edx and flags need
    # setting).  eax ends as the final loop index; edx as the last object's
    # step or reset_value (whichever branch it took); the flags come from the
    # loop's final `cmp index, count`.
    tick = state.tick
    if count > 0:
        last = ObjectView(mem.data, table + (count - 1) * OBJ_STRIDE)
        r[2] = (last.step if tick < last.threshold else last.reset_value) & 0xFFFFFFFF
        final_i = count
    else:
        r[2] = entry_edx
        final_i = 0
    r[0] = final_i & 0xFFFFFFFF
    cpu._flags_sub(final_i & 0xFFFFFFFF, count & 0xFFFFFFFF,
                   (final_i - count) & 0xFFFFFFFF, 32)

    # Stack scratch the oracle leaves below the return address: the prologue's
    # four saved regs (read back but not erased by the epilogue pops) and the
    # two frame locals ([ebp-4] final object cursor, [ebp-8] final index).
    e = r[4]
    mem.w32(e - 4, r[3]); mem.w32(e - 8, r[6])
    mem.w32(e - 12, r[7]); mem.w32(e - 16, r[5])
    mem.w32(e - 20, (table + final_i * OBJ_STRIDE) & 0xFFFFFFFF)
    mem.w32(e - 24, final_i & 0xFFFFFFFF)
    cpu.eip = cpu.pop(4)


def build_draw_list_1183b1(cpu):
    mem = cpu.mem
    r = cpu.r
    entry_edx = r[2]
    state = GameState(mem.data)
    table = state._u32(G_TABLE)
    half = state.sprite_count              # cell count >> 1

    build_draw_list(state)                 # the recovered rule fills the draw list

    # Exit registers: eax = the sprite index at loop end (== half); edx = the
    # last sprite's coord_b>>4 (sign-extended, full 32-bit) or the entry edx if
    # no sprites; flags from the loop's final `cmp half, index`.
    if half > 0:
        last = SpriteView(mem.data, table + (half - 1) * SPRITE_STRIDE)
        r[2] = _sar4(last.coord_b) & 0xFFFFFFFF
    else:
        r[2] = entry_edx
    r[0] = half & 0xFFFFFFFF
    cpu._flags_sub(half & 0xFFFFFFFF, half & 0xFFFFFFFF, 0, 32)

    e = r[4]
    mem.w32(e - 4, r[3]); mem.w32(e - 8, r[6])
    mem.w32(e - 12, r[7]); mem.w32(e - 16, r[5])
    mem.w32(e - 20, (table + half * SPRITE_STRIDE) & 0xFFFFFFFF)
    mem.w32(e - 24, half & 0xFFFFFFFF)
    cpu.eip = cpu.pop(4)


def load_object_1195ee(cpu):
    mem = cpu.mem
    r = cpu.r
    state = GameState(mem.data)
    load_current_object(state)             # the recovered latch

    # Exit registers: eax ends as [0x14e158] with its low word replaced by the
    # last field read (obj +0xc = y_offset); the routine has no stack locals,
    # so only the four saved regs remain as stack scratch.  edx/ecx untouched.
    obj_ptr = mem.r32(G_CUR_OBJ)
    r[0] = (obj_ptr & 0xFFFF0000) | mem.r16(G_CUR_Y_OFF)
    e = r[4]
    mem.w32(e - 4, r[3]); mem.w32(e - 8, r[6])
    mem.w32(e - 12, r[7]); mem.w32(e - 16, r[5])
    # The prologue's `sub esp, 0` (esp = e-16 after the 4 pushes) is the only
    # flag-affecting instruction; the rest are movs.
    v = (e - 16) & 0xFFFFFFFF
    cpu._flags_sub(v, 0, v, 32)
    cpu.eip = cpu.pop(4)


def sprite_bounds_118004(cpu):
    mem = cpu.mem
    r = cpu.r
    e = r[4]                               # entry esp -> [e]=ret, [e+4]=arg0, [e+8]=arg1
    out_ptr = mem.r32(e + 4)               # rect to fill
    sprite_def = mem.r32(e + 8)            # sprite definition pointer

    state = GameState(mem.data)
    setup_sprite_rect(state, out_ptr, sprite_def)

    # Exit registers: the routine restores ebx/esi/edi/ebp via its epilogue
    # pops (untouched here) and only leaves eax = arg0 (the last `mov
    # eax,[ebp+0x14]`) and edx = the bottom edge (`... sub edx,2` then stored).
    bottom = mem.r32(out_ptr + 0xC)        # == top + height - 2 (already written)
    r[0] = out_ptr & 0xFFFFFFFF
    r[2] = bottom
    # flags from the final `sub edx,2`: a = edx before (bottom+2), res unmasked
    # so the borrow (CF) is exact at the wrap boundary.
    a = (bottom + 2) & 0xFFFFFFFF
    cpu._flags_sub(a, 2, a - 2, 32)

    # Stack scratch the oracle leaves below the return address: this routine's
    # own four prologue pushes, then the nested `call 0x1195ee` frame (its
    # return address + the four saved regs 0x1195ee itself pushes, whose ebp
    # slot holds *this* routine's ebp = e-16).
    ebx, ebp, esi, edi = r[3], r[5], r[6], r[7]
    mem.w32(e - 4, ebx); mem.w32(e - 8, esi)
    mem.w32(e - 12, edi); mem.w32(e - 16, ebp)
    mem.w32(e - 20, 0x11801D)              # nested return address
    mem.w32(e - 24, ebx); mem.w32(e - 28, esi)
    mem.w32(e - 32, edi); mem.w32(e - 36, (e - 16) & 0xFFFFFFFF)
    cpu.eip = cpu.pop(4)


def install_logic_hooks(cpu) -> int:
    cpu.replacement_hooks[ANIM] = anim_timers_118345
    cpu.hook_names[ANIM] = "anim_timers_118345"
    cpu.replacement_hooks[DRAW_LIST] = build_draw_list_1183b1
    cpu.hook_names[DRAW_LIST] = "build_draw_list_1183b1"
    cpu.replacement_hooks[LOAD_OBJ] = load_object_1195ee
    cpu.hook_names[LOAD_OBJ] = "load_object_1195ee"
    cpu.replacement_hooks[SPRITE_BOUNDS] = sprite_bounds_118004
    cpu.hook_names[SPRITE_BOUNDS] = "sprite_bounds_118004"
    return 4
