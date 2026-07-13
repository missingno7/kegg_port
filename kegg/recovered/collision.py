"""Recovered ball/brick collision logic for Krypton Egg (pure — no dos_re, no VM).

These are *composed* routines (they call other routines in the original), so
they are proven with the observable-state composition verifier rather than the
strict full-machine diff — see dos_re/pm_composition.py.

Operates on the flat memory bytearray plus the global addresses the routine
uses; VM-free.
"""
from __future__ import annotations

# The "active list" the collision loop compacts: an array of 0x12-byte records.
L_BASE = 0x14DDA4          # pointer to the current record
L_INDEX = 0x14DDBC         # current index
L_COUNT = 0x14DDC0         # live record count
L_STRIDE = 0x12            # record size (18 bytes)


def remove_list_element(d: bytearray, base_ptr: int = L_BASE,
                        index_ptr: int = L_INDEX, count_ptr: int = L_COUNT,
                        stride: int = L_STRIDE) -> None:
    """Remove the current record from the active list (recovered from 0x114291).

    Decrement the count; unless the current record was the last one, shift the
    tail down one slot (an overlapping forward copy — the original's memcpy at
    0x123f76); then decrement the index so the loop revisits the record now
    occupying the freed slot.
    """
    def r32(a):
        return int.from_bytes(d[a:a + 4], "little")

    def w32(a, v):
        d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    count = (r32(count_ptr) - 1) & 0xFFFFFFFF
    w32(count_ptr, count)
    if r32(index_ptr) != count:
        nbytes = ((count - r32(index_ptr)) & 0xFFFFFFFF) * stride
        base = r32(base_ptr)
        d[base:base + nbytes] = d[base + stride:base + stride + nbytes]
    w32(index_ptr, (r32(index_ptr) - 1) & 0xFFFFFFFF)
