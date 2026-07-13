"""Recovered ball-physics logic for Krypton Egg (pure — no dos_re, no VM).

Each function operates on a `kegg.bridge.ball_state.BallState` view and
reproduces one original routine byte-for-byte (proven by the differential
oracle in the installing hook).
"""
from __future__ import annotations


def rects_overlap(a, b) -> bool:
    """Axis-aligned bounding-box overlap test (recovered from 0x11b5df).

    ``a`` and ``b`` are rects exposing signed ``left``/``top``/``right``/
    ``bottom`` (the {+0,+4,+8,+0xc} struct the sprite bounds use).  They
    intersect iff neither lies fully past the other on any axis — the four
    signed compares the ASM short-circuits on (jg/jl):

        a.left <= b.right and a.top <= b.bottom and
        a.right >= b.left and a.bottom >= b.top

    The original returns -1 (all bits) for overlap and 0 for miss.
    """
    if a.left > b.right:
        return False
    if a.top > b.bottom:
        return False
    if a.right < b.left:
        return False
    if a.bottom < b.top:
        return False
    return True


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
