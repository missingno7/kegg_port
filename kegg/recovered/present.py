"""Recovered present / page-flip logic for Krypton Egg (pure — no dos_re, no VM).

The display double-buffer bookkeeping that runs each frame around the render
pass.  Operates on a `kegg.bridge.game_state.GameState` view; VM-free.
"""
from __future__ import annotations


def swap_display_pages(state) -> None:
    """Swap the two display-page offsets (recovered from 0x11c886).

    ``tmp = page1 ; page1 = page0 ; page0 = tmp`` — the per-frame page flip,
    done through the scratch slot, which is left holding the old back page.
    """
    state.page_tmp = state.page1
    state.page1 = state.page0
    state.page0 = state.page_tmp
