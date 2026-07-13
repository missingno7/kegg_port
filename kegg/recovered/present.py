"""Recovered present / page-flip logic for Krypton Egg (pure — no dos_re, no VM).

The display double-buffer bookkeeping that runs each frame around the render
pass.  Operates on a `kegg.bridge.game_state.GameState` view; VM-free.
"""
from __future__ import annotations


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
