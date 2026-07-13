"""Typed view over Krypton Egg's ball-physics globals (the ONE place these
offsets live, for the physics island — cf. bridge/game_state.py for the
render/anim island).

Recovered from the oracle-verified ball routines (docs/kegg/control_flow.md):
the ball's position lives in a small block of 16-bit globals around 0x147b14,
with the Y coordinate double-buffered across two slots and a scratch word used
as swap temp / previous value.  Like the other bridge, this knows the memory
layout but holds no gameplay decisions — the rules live in kegg/recovered/.

No dos_re import: the view wraps a plain bytearray (cpu.mem.data), so the
recovered physics that uses it stays VM-free and layer-audit clean.
"""
from __future__ import annotations

# Ball-state globals (runtime; link = − 0x100000).  All 16-bit words.
B_Y_TEMP = 0x147B16        # scratch / previous Y (the Y-swap's temp slot)
B_X = 0x147B18             # ball X
B_Y0 = 0x147B20            # ball Y (front of the double buffer)
B_Y1 = 0x147B22            # ball Y (back of the double buffer)


class BallState:
    """The ball's position globals as named 16-bit fields."""
    __slots__ = ("_d",)

    def __init__(self, d: bytearray):
        self._d = d

    def _r16(self, addr: int) -> int:
        return int.from_bytes(self._d[addr:addr + 2], "little")

    def _w16(self, addr: int, v: int) -> None:
        self._d[addr:addr + 2] = (v & 0xFFFF).to_bytes(2, "little")

    @property
    def x(self) -> int:
        return self._r16(B_X)

    @x.setter
    def x(self, v: int) -> None:
        self._w16(B_X, v)

    @property
    def y0(self) -> int:
        return self._r16(B_Y0)

    @y0.setter
    def y0(self, v: int) -> None:
        self._w16(B_Y0, v)

    @property
    def y1(self) -> int:
        return self._r16(B_Y1)

    @y1.setter
    def y1(self, v: int) -> None:
        self._w16(B_Y1, v)

    @property
    def y_temp(self) -> int:
        return self._r16(B_Y_TEMP)

    @y_temp.setter
    def y_temp(self, v: int) -> None:
        self._w16(B_Y_TEMP, v)
