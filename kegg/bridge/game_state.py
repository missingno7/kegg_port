"""Typed views over Krypton Egg's per-frame game state (the ONE place offsets live).

Recovered from the oracle-verified logic routines (docs/kegg/data_model.md).
A `GameState` wraps the flat memory bytearray and exposes the object table and
the frame globals as named fields; an `ObjectView` is one 24-byte entry.  The
bridge knows the memory layout but holds no gameplay decisions — the rules
live in `kegg/recovered/`.

No dos_re import: the view takes a plain bytearray (cpu.mem.data), so the
recovered logic that uses it stays VM-free and layer-audit clean.
"""
from __future__ import annotations

OBJ_STRIDE = 0x18          # animation cell size (24 bytes)
SPRITE_STRIDE = 0x30       # a sprite = a pair of cells (even + odd)

# Frame-global addresses (runtime; link = − 0x100000).
G_TICK = 0x14E14C          # frame tick, incremented once per update
G_COUNT = 0x14E148         # live cell count (2x the sprite count)
G_TABLE = 0x14E150         # object/cell table base pointer
G_WORLD_X = 0x14E154       # world X offset added to each sprite's position
G_DRAW_CURSOR = 0x14E2EC   # output cursor for the draw-command list


def _s32(v: int) -> int:
    return v - 0x100000000 if v & 0x80000000 else v


class ObjectView:
    """One object: a 24-byte struct of signed 32-bit fields."""
    __slots__ = ("_d", "base")

    def __init__(self, d: bytearray, base: int):
        self._d = d
        self.base = base

    def _get(self, off: int) -> int:
        o = self.base + off
        return _s32(int.from_bytes(self._d[o:o + 4], "little"))

    def _set(self, off: int, v: int) -> None:
        o = self.base + off
        self._d[o:o + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    @property
    def reset_value(self) -> int:          # +0x04
        return self._get(0x04)

    @property
    def accumulator(self) -> int:          # +0x08
        return self._get(0x08)

    @accumulator.setter
    def accumulator(self, v: int) -> None:
        self._set(0x08, v)

    @property
    def step(self) -> int:                 # +0x0c
        return self._get(0x0C)

    @property
    def threshold(self) -> int:            # +0x10
        return self._get(0x10)


class SpriteView:
    """A drawable sprite: a pair of animation cells (the draw-list's 0x30 unit).

    `position` is the even cell's +0x14; `coord_a` / `coord_b` are the two
    cells' animated accumulators (even +0x08, odd +0x08 == sprite +0x20)."""
    __slots__ = ("_d", "base")

    def __init__(self, d: bytearray, base: int):
        self._d = d
        self.base = base

    def _get(self, off: int) -> int:
        o = self.base + off
        return _s32(int.from_bytes(self._d[o:o + 4], "little"))

    @property
    def position(self) -> int:             # +0x14
        return self._get(0x14)

    @property
    def coord_a(self) -> int:              # +0x08 (even cell accumulator)
        return self._get(0x08)

    @property
    def coord_b(self) -> int:              # +0x20 (odd cell accumulator)
        return self._get(0x20)


class DrawCommand:
    """One 10-byte draw command: dword X, word W, word H, word flags."""
    __slots__ = ("_d", "base")

    def __init__(self, d: bytearray, base: int):
        self._d = d
        self.base = base

    def _w(self, off: int, size: int, v: int) -> None:
        self._d[self.base + off:self.base + off + size] = \
            (v & ((1 << (size * 8)) - 1)).to_bytes(size, "little")

    @property
    def x(self):  # noqa: D401
        raise AttributeError("write-only view")

    @x.setter
    def x(self, v: int) -> None:
        self._w(0, 4, v)

    def set(self, x: int, w: int, h: int, flags: int) -> None:
        self._w(0, 4, x)
        self._w(4, 2, w)
        self._w(6, 2, h)
        self._w(8, 2, flags)


class GameState:
    """The per-frame object system rooted at the frame globals."""
    __slots__ = ("_d",)

    def __init__(self, d: bytearray):
        self._d = d

    def _u32(self, addr: int) -> int:
        return int.from_bytes(self._d[addr:addr + 4], "little")

    @property
    def world_x(self) -> int:
        return _s32(self._u32(G_WORLD_X))

    @property
    def sprite_count(self) -> int:
        return self.object_count >> 1      # ASM `sar count,1`

    def sprites(self):
        base = self._u32(G_TABLE)
        for i in range(self.sprite_count):
            yield SpriteView(self._d, base + i * SPRITE_STRIDE)

    def alloc_draw_command(self) -> "DrawCommand":
        cur = self._u32(G_DRAW_CURSOR)
        self._d[G_DRAW_CURSOR:G_DRAW_CURSOR + 4] = (cur + 0xA).to_bytes(4, "little")
        return DrawCommand(self._d, cur)

    @property
    def tick(self) -> int:                 # [0x14e14c], read signed for comparisons
        return _s32(self._u32(G_TICK))

    @tick.setter
    def tick(self, v: int) -> None:
        self._d[G_TICK:G_TICK + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    @property
    def object_count(self) -> int:
        return _s32(self._u32(G_COUNT))

    def objects(self):
        base = self._u32(G_TABLE)
        for i in range(self.object_count):
            yield ObjectView(self._d, base + i * OBJ_STRIDE)
