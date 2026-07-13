"""Recovered effect-list logic — pure unit test."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.recovered.effects import (spawn_effect, EFFECT_ARRAY, EFFECT_COUNT,  # noqa: E402
                                    EFFECT_PTR, EFFECT_MAX, EFFECT_STRIDE)


def _r32(d, a):
    return int.from_bytes(d[a:a + 4], "little")


def _w32(d, a, v):
    d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")


def test_spawn_effect_appends_record_and_packs_flags():
    d = bytearray(0x200000)
    _w32(d, EFFECT_COUNT, 0)
    # flags: bit4 set (picks the 0x3e80 branch), low bits 0b0_1101 = 0x0D
    spawn_effect(d, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x1D)  # 0x1D = 0b11101
    rec = EFFECT_ARRAY
    assert _r32(d, EFFECT_PTR) == rec
    assert _r32(d, EFFECT_COUNT) == 1
    assert [_r32(d, rec + o) for o in (0, 4, 8, 0xC, 0x10)] == [0x11, 0x22, 0x33, 0x44, 0x55]
    assert _r32(d, rec + 0x14) == 0x3E80         # bit 4 set -> 0x3e80
    assert _r32(d, rec + 0x18) == 0x66           # bit 4 set -> a5 verbatim
    # flags 0x1D = 0b11101: (>>4&f)=1 -> bits1..4=1; (>>3&1)=1 -> bit5; (>>2&1)=1 -> bit6;
    # (>>1&1)=0 -> bit7=0; (&1)=1 -> +1d bit0
    assert d[rec + 0x1C] == (1 << 1) | (1 << 5) | (1 << 6)   # 0x62
    assert d[rec + 0x1D] & 1 == 1


def test_spawn_effect_no_bit4_uses_alt_fields():
    d = bytearray(0x200000)
    _w32(d, EFFECT_COUNT, 3)                       # append at slot 3
    spawn_effect(d, 1, 2, 3, 4, 5, 100, 0x00)      # bit4 clear
    rec = EFFECT_ARRAY + 3 * EFFECT_STRIDE
    assert _r32(d, EFFECT_PTR) == rec
    assert _r32(d, rec + 0x14) == 0                # bit4 clear -> 0
    assert _r32(d, rec + 0x18) == 100 - 8          # bit4 clear -> a5 - 8
    assert _r32(d, EFFECT_COUNT) == 4


def test_spawn_effect_full_array_is_noop():
    d = bytearray(0x200000)
    _w32(d, EFFECT_COUNT, EFFECT_MAX)              # full
    _w32(d, EFFECT_PTR, 0xDEAD)
    spawn_effect(d, 1, 2, 3, 4, 5, 6, 7)
    assert _r32(d, EFFECT_COUNT) == EFFECT_MAX     # unchanged
    assert _r32(d, EFFECT_PTR) == 0xDEAD           # untouched
