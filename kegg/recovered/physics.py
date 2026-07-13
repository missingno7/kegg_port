"""Recovered ball-physics logic for Krypton Egg (pure — no dos_re, no VM).

Each function operates on a `kegg.bridge.ball_state.BallState` view and
reproduces one original routine byte-for-byte (proven by the differential
oracle in the installing hook).
"""
from __future__ import annotations


def swap_ball_y(state) -> None:
    """Flip the ball's Y double-buffer (recovered from 0x11eda0).

    Swaps the two Y slots through the scratch global, exactly as the ASM:
    ``temp = y0 ; y0 = y1 ; y1 = temp``.  The scratch word (the previous-Y
    slot) is left holding the old front value — a real side effect the draw
    path reads, so it is reproduced here, not elided.
    """
    state.y_temp = state.y0
    state.y0 = state.y1
    state.y1 = state.y_temp
