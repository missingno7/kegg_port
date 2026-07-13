"""Recovered gameplay-logic hooks for Krypton Egg (the VM bridge).

Thin adapters over `kegg.recovered` pure logic + `kegg.bridge` typed views:
each reads VM state, runs the recovered rule against a bridge view of
`cpu.mem.data`, and reproduces the routine's exact register/flag exit so it
verifies byte-exact against the ASM oracle (pm_verification.PMHookVerifier).
"""
from __future__ import annotations

from kegg.bridge.game_state import (GameState, ObjectView, SpriteView, Rect,
                                     OBJ_STRIDE, SPRITE_STRIDE, G_TABLE,
                                     G_CUR_OBJ, G_CUR_Y_OFF)
from kegg.bridge.ball_state import BallState, B_Y_TEMP
from kegg.recovered.anim import (update_anim_timers, build_draw_list,
                                  load_current_object, setup_sprite_rect, _sar4)
from kegg.recovered.physics import swap_ball_y, rects_overlap
from kegg.recovered.sequence import step_sequence

ANIM = 0x118345
DRAW_LIST = 0x1183B1
LOAD_OBJ = 0x1195EE
SPRITE_BOUNDS = 0x118004
BALL_Y_SWAP = 0x11EDA0
RECTS_OVERLAP = 0x11B5DF
STEP_SEQ = 0x11B17E


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


def swap_ball_y_11eda0(cpu):
    mem = cpu.mem
    r = cpu.r
    e = r[4]
    state = BallState(mem.data)
    swap_ball_y(state)                     # temp=y0; y0=y1; y1=temp

    # Exit registers: the epilogue restores ebx/esi/edi/ebp; only eax's low
    # word is touched (the final `mov ax,[0x147b16]` — the scratch, now holding
    # the old front Y).  The prologue's `sub esp,0` is the only flag op.
    r[0] = (r[0] & 0xFFFF0000) | mem.r16(B_Y_TEMP)
    mem.w32(e - 4, r[3]); mem.w32(e - 8, r[6])
    mem.w32(e - 12, r[7]); mem.w32(e - 16, r[5])
    v = (e - 16) & 0xFFFFFFFF
    cpu._flags_sub(v, 0, v, 32)
    cpu.eip = cpu.pop(4)


# The four short-circuit compares of 0x11b5df, in order: (arg0 field, arg1
# field, "the branch that exits with 'no overlap'").  'g' = jg (a>b exits),
# 'l' = jl (a<b exits).  a.left>b.right, a.top>b.bottom, a.right<b.left,
# a.bottom<b.top.
_OVERLAP_CHECKS = ((0x0, 0x8, 'g'), (0x4, 0xC, 'g'),
                   (0x8, 0x0, 'l'), (0xC, 0x4, 'l'))


def rects_overlap_11b5df(cpu):
    mem = cpu.mem
    r = cpu.r
    e = r[4]
    a = mem.r32(e + 4)                      # arg0 rect ptr
    b = mem.r32(e + 8)                      # arg1 rect ptr

    # Walk the compares exactly as the ASM: each loads edx = arg0.field and
    # `cmp edx, arg1.field`; the first that satisfies its exit branch returns
    # 0 (miss), otherwise all pass and it returns -1 (hit).  edx and the flags
    # end as those of the *deciding* compare (or the last, on a hit).
    result = 0xFFFFFFFF
    edx = m = 0
    for a_off, b_off, jk in _OVERLAP_CHECKS:
        edx = mem.r32(a + a_off)
        m = mem.r32(b + b_off)
        se = edx - 0x100000000 if edx & 0x80000000 else edx
        sm = m - 0x100000000 if m & 0x80000000 else m
        if (jk == 'g' and se > sm) or (jk == 'l' and se < sm):
            result = 0
            break

    r[0] = result                          # eax = [ebp-4] = the -1/0 result
    r[2] = edx                             # edx = last arg0 field loaded
    cpu._flags_sub(edx, m, edx - m, 32)    # flags of the deciding `cmp`

    # Stack scratch: four saved regs + the frame local [ebp-4] (the result).
    mem.w32(e - 4, r[3]); mem.w32(e - 8, r[6])
    mem.w32(e - 12, r[7]); mem.w32(e - 16, r[5])
    mem.w32(e - 20, result)
    cpu.eip = cpu.pop(4)


def _s32(v):
    return v - 0x100000000 if v & 0x80000000 else v


def step_sequence_11b17e(cpu):
    mem = cpu.mem
    r = cpu.r
    e = r[4]
    counter_ptr = mem.r32(e + 4)           # arg0
    cursor_ptr = mem.r32(e + 8)            # arg1
    edx = r[2]                             # unchanged on the early-out path

    # Mirror the ASM branch-by-branch so eax/edx/flags and the memory writes
    # all match; the clean statement of the same rule is recovered.sequence.
    cnt = (mem.r32(counter_ptr) - 1) & 0xFFFFFFFF     # dec [arg0]
    mem.w32(counter_ptr, cnt)
    if _s32(cnt) > 0:
        cpu._flags_sub(cnt, 0, cnt, 32)               # cmp [arg0],0 (jg)
    else:
        cur_prev = mem.r32(cursor_ptr)
        cursor = (cur_prev + 8) & 0xFFFFFFFF          # add [arg1],8
        mem.w32(cursor_ptr, cursor)
        cpu._flags_add(cur_prev, 8, cur_prev + 8, 32)
        cnt1 = mem.r32(cursor + 4)                    # [arg0] = [[arg1]+4]
        mem.w32(counter_ptr, cnt1)
        edx = cnt1
        if _s32(cnt1) >= 0:
            # test eax,eax preserves AF -> the surviving AF is the add's above
            cpu._flags_logic(cnt1, 32)                # test eax,eax (jge)
        else:
            shifted = (cnt1 << 3) & 0xFFFFFFFF        # edx = [arg0]<<3
            cur_before = mem.r32(cursor_ptr)
            cur2_raw = cur_before + shifted
            mem.w32(cursor_ptr, cur2_raw & 0xFFFFFFFF)   # add [arg1],edx
            cpu._flags_add(cur_before, shifted, cur2_raw, 32)
            cnt2 = mem.r32((cur2_raw & 0xFFFFFFFF) + 4)   # [arg0] = [[arg1]+4]
            mem.w32(counter_ptr, cnt2)
            edx = cnt2

    result = mem.r32(mem.r32(cursor_ptr))             # eax = [[arg1]]
    r[0] = result
    r[2] = edx
    mem.w32(e - 4, r[3]); mem.w32(e - 8, r[6])
    mem.w32(e - 12, r[7]); mem.w32(e - 16, r[5])
    mem.w32(e - 20, result)                           # [ebp-4] frame local
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
    cpu.replacement_hooks[BALL_Y_SWAP] = swap_ball_y_11eda0
    cpu.hook_names[BALL_Y_SWAP] = "swap_ball_y_11eda0"
    cpu.replacement_hooks[RECTS_OVERLAP] = rects_overlap_11b5df
    cpu.hook_names[RECTS_OVERLAP] = "rects_overlap_11b5df"
    cpu.replacement_hooks[STEP_SEQ] = step_sequence_11b17e
    cpu.hook_names[STEP_SEQ] = "step_sequence_11b17e"
    return 7
