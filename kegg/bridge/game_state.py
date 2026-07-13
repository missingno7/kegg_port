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

# The "current object" being processed, and its geometry latched for the draw
# path (0x1195ee copies the sprite def's fields into these working globals).
G_CUR_OBJ = 0x14E158       # pointer to the current sprite-definition struct
G_CUR_X_OFF = 0x14E15C     # <- def +0xa
G_CUR_Y_OFF = 0x14E15E     # <- def +0xc
G_CUR_WIDTH = 0x14E160     # <- def +0x02
G_CUR_HEIGHT = 0x14E162    # <- def +0x04


def _s32(v: int) -> int:
    return v - 0x100000000 if v & 0x80000000 else v


def _s16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


class Rect:
    """A 4-dword screen rectangle {left(+0), top(+4), right(+8), bottom(+0xc)},
    signed 32-bit fields (the sprite bounds built by 0x118004)."""
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
    def left(self) -> int:            # +0x00
        return self._get(0x00)

    @left.setter
    def left(self, v: int) -> None:
        self._set(0x00, v)

    @property
    def top(self) -> int:             # +0x04
        return self._get(0x04)

    @top.setter
    def top(self, v: int) -> None:
        self._set(0x04, v)

    @property
    def right(self) -> int:           # +0x08
        return self._get(0x08)

    @right.setter
    def right(self, v: int) -> None:
        self._set(0x08, v)

    @property
    def bottom(self) -> int:          # +0x0c
        return self._get(0x0C)

    @bottom.setter
    def bottom(self, v: int) -> None:
        self._set(0x0C, v)


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

    # ---- current sprite definition + its latched geometry -------------------
    def _rw16(self, addr: int) -> int:
        return int.from_bytes(self._d[addr:addr + 2], "little")

    def _ww16(self, addr: int, v: int) -> None:
        self._d[addr:addr + 2] = (v & 0xFFFF).to_bytes(2, "little")

    @property
    def current_object(self) -> "SpriteDef":
        return SpriteDef(self._d, self._u32(G_CUR_OBJ))

    @property
    def current_object_ptr(self) -> int:
        return self._u32(G_CUR_OBJ)

    @current_object_ptr.setter
    def current_object_ptr(self, v: int) -> None:
        self._d[G_CUR_OBJ:G_CUR_OBJ + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    def rect_at(self, addr: int) -> "Rect":
        return Rect(self._d, addr)

    # signed views of the latched geometry (0x118004 reads them `movsx`)
    @property
    def cur_x_offset_s(self) -> int:
        return _s16(self._rw16(G_CUR_X_OFF))

    @property
    def cur_y_offset_s(self) -> int:
        return _s16(self._rw16(G_CUR_Y_OFF))

    @property
    def cur_width_s(self) -> int:
        return _s16(self._rw16(G_CUR_WIDTH))

    @property
    def cur_height_s(self) -> int:
        return _s16(self._rw16(G_CUR_HEIGHT))

    @property
    def cur_x_offset(self) -> int:
        return self._rw16(G_CUR_X_OFF)

    @cur_x_offset.setter
    def cur_x_offset(self, v: int) -> None:
        self._ww16(G_CUR_X_OFF, v)

    @property
    def cur_y_offset(self) -> int:
        return self._rw16(G_CUR_Y_OFF)

    @cur_y_offset.setter
    def cur_y_offset(self, v: int) -> None:
        self._ww16(G_CUR_Y_OFF, v)

    @property
    def cur_width(self) -> int:
        return self._rw16(G_CUR_WIDTH)

    @cur_width.setter
    def cur_width(self, v: int) -> None:
        self._ww16(G_CUR_WIDTH, v)

    @property
    def cur_height(self) -> int:
        return self._rw16(G_CUR_HEIGHT)

    @cur_height.setter
    def cur_height(self, v: int) -> None:
        self._ww16(G_CUR_HEIGHT, v)


class SpriteDef:
    """A sprite-definition struct: 16-bit geometry read by the draw path."""
    __slots__ = ("_d", "base")

    def __init__(self, d: bytearray, base: int):
        self._d = d
        self.base = base

    def _w(self, off: int) -> int:
        return int.from_bytes(self._d[self.base + off:self.base + off + 2], "little")

    @property
    def width(self) -> int:        # +0x02
        return self._w(0x02)

    @property
    def height(self) -> int:       # +0x04
        return self._w(0x04)

    @property
    def x_offset(self) -> int:     # +0x0a
        return self._w(0x0A)

    @property
    def y_offset(self) -> int:     # +0x0c
        return self._w(0x0C)
