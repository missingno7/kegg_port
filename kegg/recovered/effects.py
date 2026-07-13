"""Recovered effect-list logic for Krypton Egg (pure — no dos_re, no VM).

The game keeps a fixed array of 32-byte effect records (particles / brick-break
bursts) and appends to it until full.  Like kegg/recovered/sequence.py this
operates on the flat memory bytearray plus the array constants, so it stays
VM-free and layer-audit clean.
"""
from __future__ import annotations

EFFECT_ARRAY = 0x1494B8    # base of the 32-byte-record array
EFFECT_COUNT = 0x14DD84    # live record count (append index)
EFFECT_PTR = 0x14DD6C      # scratch: pointer to the record just appended
EFFECT_MAX = 0x32          # array capacity (50)
EFFECT_STRIDE = 0x20       # 32-byte records


def spawn_effect(d: bytearray, a0: int, a1: int, a2: int, a3: int,
                 a4: int, a5: int, flags: int) -> None:
    """Append a 32-byte effect record (recovered from 0x117e62).

    No-op once the array is full (count >= 50).  Copies the six data words into
    the record, picks a fixed field from bit 4 of ``flags``, and packs the low
    5 bits of ``flags`` into the record's flag bytes at +0x1c/+0x1d
    (read-modify-write — the other bits of those bytes are preserved).
    """
    def r32(a):
        return int.from_bytes(d[a:a + 4], "little")

    def w32(a, v):
        d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    count = r32(EFFECT_COUNT)
    if count >= EFFECT_MAX:
        return
    rec = (EFFECT_ARRAY + count * EFFECT_STRIDE) & 0xFFFFFFFF
    w32(EFFECT_PTR, rec)
    w32(rec + 0x0, a0)
    w32(rec + 0x4, a1)
    w32(rec + 0x8, a2)
    w32(rec + 0xC, a3)
    if flags & 0x10:
        w32(rec + 0x14, 0x3E80)
        w32(rec + 0x18, a5)
    else:
        w32(rec + 0x14, 0)
        w32(rec + 0x18, (a5 - 8) & 0xFFFFFFFF)
    w32(rec + 0x10, a4)
    b1c = d[rec + 0x1C]
    b1c = (b1c & 0xE1) | (((flags >> 4) & 0xF) << 1)
    b1c = (b1c & 0xDF) | (((flags >> 3) & 1) << 5)
    b1c = (b1c & 0xBF) | (((flags >> 2) & 1) << 6)
    b1c = (b1c & 0x7F) | (((flags >> 1) & 1) << 7)
    d[rec + 0x1C] = b1c
    d[rec + 0x1D] = (d[rec + 0x1D] & 0xFE) | (flags & 1)
    w32(EFFECT_COUNT, count + 1)
