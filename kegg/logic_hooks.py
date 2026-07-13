"""Recovered gameplay-logic hooks for Krypton Egg (the VM bridge).

Thin adapters over `kegg.recovered` pure logic + `kegg.bridge` typed views:
each reads VM state, runs the recovered rule against a bridge view of
`cpu.mem.data`, and reproduces the routine's exact register/flag exit so it
verifies byte-exact against the ASM oracle (pm_verification.PMHookVerifier).
"""
from __future__ import annotations

from kegg.bridge.game_state import GameState, ObjectView, OBJ_STRIDE, G_TABLE
from kegg.recovered.anim import update_anim_timers

ANIM = 0x118345


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


def install_logic_hooks(cpu) -> int:
    cpu.replacement_hooks[ANIM] = anim_timers_118345
    cpu.hook_names[ANIM] = "anim_timers_118345"
    return 1
