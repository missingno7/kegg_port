"""Recovered record-sequence stepping for Krypton Egg (pure — no dos_re, no VM).

Unlike the fixed-offset global views in kegg/bridge, this operates on a
pointer-linked array of records, so the recovered rule takes the flat memory
bytearray plus the two pointers the routine is called with.  Still VM-free
(a plain bytearray + ints), so it stays layer-audit clean.
"""
from __future__ import annotations


def _s32(v: int) -> int:
    return v - 0x100000000 if v & 0x80000000 else v


def step_sequence(d: bytearray, counter_ptr: int, cursor_ptr: int) -> int:
    """Advance a ``{value(+0), count(+4)}`` record sequence (recovered from
    0x11b17e).

    ``counter_ptr`` -> a 32-bit countdown; ``cursor_ptr`` -> the address of the
    current 8-byte record.  Each call ticks the countdown; once it reaches 0 it
    steps to the next record and reloads that record's count, and if the
    reloaded count is negative it is a relative LOOP-BACK — jump ``count``
    records (count<0, so backwards) and reload again.  Returns the current
    record's value.  All fields are signed 32-bit.
    """
    def r32(a):
        return int.from_bytes(d[a:a + 4], "little")

    def w32(a, v):
        d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    cnt = (r32(counter_ptr) - 1) & 0xFFFFFFFF     # dec the countdown
    w32(counter_ptr, cnt)
    if _s32(cnt) <= 0:                             # expired -> advance a record
        cursor = (r32(cursor_ptr) + 8) & 0xFFFFFFFF
        w32(cursor_ptr, cursor)
        cnt = r32(cursor + 4)
        w32(counter_ptr, cnt)
        if _s32(cnt) < 0:                          # negative count = loop back
            cursor = (cursor + ((cnt << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
            w32(cursor_ptr, cursor)
            cnt = r32(cursor + 4)
            w32(counter_ptr, cnt)
    return r32(r32(cursor_ptr))                    # the current record's value
