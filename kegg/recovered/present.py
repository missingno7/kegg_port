"""Recovered present / page-flip logic for Krypton Egg (pure — no dos_re, no VM).

The display double-buffer bookkeeping that runs each frame around the render
pass.  Operates on a `kegg.bridge.game_state.GameState` view; VM-free.
"""
from __future__ import annotations


def set_draw_params(state, p0: int, p1: int, flag: int, p3: int, p4: int) -> None:
    """Store the draw-parameter block at [0x14e200] (recovered from 0x11b541).

    A flat copy of the five arguments into the packed
    ``{p0:dword, p1:dword, flag:byte, p3:dword, p4:dword}`` record the
    0x11bxxx anim/draw routines read back."""
    state.write_draw_params(p0, p1, flag, p3, p4)


def set_clip_rect(state, x0: int, y0: int, x1: int, y1: int) -> None:
    """Normalize a two-corner box and store it as the clip rect (0x11b57a).

    Orders each pair so ``x0 <= x1`` and ``y0 <= y1`` (signed), then writes the
    four clip-bound globals as ``{x0, x1, y0, y1}``.
    """
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    state.clip_x0 = x0
    state.clip_x1 = x1
    state.clip_y0 = y0
    state.clip_y1 = y1


def swap_display_pages(state) -> None:
    """Swap the two display-page offsets (recovered from 0x11c886).

    ``tmp = page1 ; page1 = page0 ; page0 = tmp`` — the per-frame page flip,
    done through the scratch slot, which is left holding the old back page.
    """
    state.page_tmp = state.page1
    state.page1 = state.page0
    state.page0 = state.page_tmp


# Clamp ceiling for a VGA DAC component (6-bit).
DAC_MAX = 0x3F


def fade_palette_stream(src, src_off: int, count: int, fade: int, eax_in: int):
    """The DAC byte stream of the palette fade at 0x123A48.

    Each component is ``src[i] - fade`` clamped to 0..0x3F, written to the DAC
    data port.  Returns ``(stream, clamped_low, last_value)``:

    * ``stream`` — the ``count`` bytes to send to the DAC;
    * ``clamped_low`` — whether the LAST component took the negative branch
      (``sub eax,eax``) rather than the ``cmp eax,0x3F`` branch;
    * ``last_value`` — the pre-clamp 32-bit EAX of the last component.

    The caller needs the last two to reproduce the routine's exit flags.

    Faithful detail: EAX is 32-bit and ``lodsb`` replaces only AL, so the high
    bytes of the incoming EAX (the DAC start index) take part in the first
    subtract until a clamp zeroes them — exactly as the ASM behaves.  For the
    start indices KE uses (< 256) those high bytes are already zero.
    """
    out = bytearray(count)
    eax = eax_in & 0xFFFFFFFF
    low = False
    val = eax
    for i in range(count):
        eax = (eax & 0xFFFFFF00) | src[src_off + i]
        eax = (eax - fade) & 0xFFFFFFFF
        val = eax
        signed = eax - 0x100000000 if eax & 0x80000000 else eax
        if signed < 0:
            eax = 0                      # sub eax,eax
            low = True
        else:
            low = False
            if signed > DAC_MAX:
                eax = DAC_MAX            # mov eax,ebp
        out[i] = eax & 0xFF
    return out, low, val
