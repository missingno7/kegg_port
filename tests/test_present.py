"""Recovered present / page-flip logic — pure unit test."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.bridge.game_state import GameState, G_PAGE0, G_PAGE1, G_PAGE_TMP  # noqa: E402
from kegg.recovered.present import swap_display_pages  # noqa: E402


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
