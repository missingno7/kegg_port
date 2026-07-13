"""Recovered present / page-flip logic — pure unit test."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.bridge.game_state import (GameState, G_PAGE0, G_PAGE1, G_PAGE_TMP,  # noqa: E402
                                    G_CLIP_X0, G_CLIP_X1, G_CLIP_Y0, G_CLIP_Y1,
                                    G_DRAW_PARAMS)
from kegg.recovered.present import (swap_display_pages, set_clip_rect,  # noqa: E402
                                    set_draw_params)


def _w32(d, a, v):
    d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")


def _r32(d, a):
    return int.from_bytes(d[a:a + 4], "little")


def test_swap_display_pages_pure():
    d = bytearray(0x200000)
    _w32(d, G_PAGE0, 0x0000)       # front page
    _w32(d, G_PAGE1, 0x4000)       # back page
    _w32(d, G_PAGE_TMP, 0x9999)    # scratch (overwritten)

    swap_display_pages(GameState(d))

    assert _r32(d, G_PAGE0) == 0x4000    # pages swapped
    assert _r32(d, G_PAGE1) == 0x0000
    assert _r32(d, G_PAGE_TMP) == 0x4000  # scratch left holding the old back page (page1)


def test_set_clip_rect_pure():
    def clip(d):
        return (_r32(d, G_CLIP_X0), _r32(d, G_CLIP_X1),
                _r32(d, G_CLIP_Y0), _r32(d, G_CLIP_Y1))

    d = bytearray(0x200000)
    set_clip_rect(GameState(d), 10, 20, 30, 40)     # already ordered
    assert clip(d) == (10, 30, 20, 40)

    set_clip_rect(GameState(d), 30, 20, 10, 40)     # x needs swapping
    assert clip(d) == (10, 30, 20, 40)

    set_clip_rect(GameState(d), 10, 40, 30, 20)     # y needs swapping
    assert clip(d) == (10, 30, 20, 40)

    set_clip_rect(GameState(d), 30, 40, 10, 20)     # both swap
    assert clip(d) == (10, 30, 20, 40)


def test_set_draw_params_pure():
    d = bytearray(0x200000)
    set_draw_params(GameState(d), 0x11223344, 0x55667788, 0x9A, 0xDEADBEEF, 0xCAFEF00D)
    b = G_DRAW_PARAMS
    assert _r32(d, b) == 0x11223344          # +0
    assert _r32(d, b + 4) == 0x55667788      # +4
    assert d[b + 8] == 0x9A                  # +8 byte
    assert _r32(d, b + 9) == 0xDEADBEEF      # +9 (unaligned)
    assert _r32(d, b + 13) == 0xCAFEF00D     # +d
