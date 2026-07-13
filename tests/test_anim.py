"""Recovered animation logic — pure unit test + in-game oracle check."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.bridge.game_state import GameState, OBJ_STRIDE, G_TICK, G_COUNT, G_TABLE  # noqa: E402
from kegg.recovered.anim import update_anim_timers  # noqa: E402


def _w32(d, a, v):
    d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")


def test_update_anim_timers_pure():
    d = bytearray(0x200000)
    table = 0x101000
    _w32(d, G_TICK, 5)
    _w32(d, G_COUNT, 2)
    _w32(d, G_TABLE, table)
    # obj0: below threshold -> advance (accumulator += step)
    _w32(d, table + 0x04, 100)     # reset_value
    _w32(d, table + 0x08, 30)      # accumulator
    _w32(d, table + 0x0C, 7)       # step
    _w32(d, table + 0x10, 999)     # threshold (tick 6 < 999 -> advance)
    # obj1: at/over threshold -> reset (accumulator = reset_value)
    _w32(d, table + OBJ_STRIDE + 0x04, 42)
    _w32(d, table + OBJ_STRIDE + 0x08, 12345)
    _w32(d, table + OBJ_STRIDE + 0x0C, 1)
    _w32(d, table + OBJ_STRIDE + 0x10, 3)   # tick 6 >= 3 -> reset

    st = GameState(d)
    update_anim_timers(st)

    assert st.tick == 6
    objs = list(st.objects())
    assert objs[0].accumulator == 37       # 30 + 7
    assert objs[1].accumulator == 42       # reset


SNAP = ROOT / "artifacts" / "snapshots" / "snap_126359171"


@pytest.mark.skipif(not SNAP.exists(), reason="gameplay snapshot not present")
def test_anim_hook_verifies_against_oracle():
    from dos_re.pm_snapshot import load_pm_snapshot
    from dos_re.pm_verification import install_pm_hook_verifier
    from kegg.render_hooks import install_render_hooks
    from kegg.logic_hooks import install_logic_hooks
    rt = load_pm_snapshot(str(ROOT / "assets" / "KE.EXE"), str(SNAP))
    install_render_hooks(rt.cpu)
    install_logic_hooks(rt.cpu)
    v = install_pm_hook_verifier(rt)
    v.config.samples = None
    rt.cpu.run(3_000_000)
    assert v.total_verified >= 50


def test_build_draw_list_pure():
    from kegg.bridge.game_state import (SPRITE_STRIDE, G_COUNT, G_TABLE,
                                        G_WORLD_X, G_DRAW_CURSOR)
    from kegg.recovered.anim import build_draw_list
    d = bytearray(0x200000)
    table = 0x101000
    cursor = 0x120000
    _w32(d, G_COUNT, 4)            # 4 cells -> 2 sprites
    _w32(d, G_TABLE, table)
    _w32(d, G_WORLD_X, 1000)
    _w32(d, G_DRAW_CURSOR, cursor)
    # sprite 0 (0x30): position +0x14, coord_a +0x08, coord_b +0x20
    _w32(d, table + 0x14, 5)
    _w32(d, table + 0x08, 0x160)      # >>4 = 0x16
    _w32(d, table + 0x20, 0x320)      # >>4 = 0x32
    # sprite 1 — NEGATIVE coord_b, exercising the arithmetic sar (regression:
    # a naive re-signed sar shifts -18 toward -1e8 instead of -2)
    _w32(d, table + SPRITE_STRIDE + 0x14, 7)
    _w32(d, table + SPRITE_STRIDE + 0x08, 0x800)         # >>4 = 0x80
    _w32(d, table + SPRITE_STRIDE + 0x20, (-18) & 0xFFFFFFFF)   # >>4 = -2 -> 0xFFFE

    GameState(d)
    build_draw_list(GameState(d))

    def r16(a): return int.from_bytes(d[a:a + 2], "little")
    def r32(a): return int.from_bytes(d[a:a + 4], "little")
    # cmd 0 at cursor, cmd 1 at cursor+0xa; cursor advanced by 0x14
    assert r32(cursor) == 1005 and r16(cursor + 4) == 0x16 and r16(cursor + 6) == 0x32
    assert r32(cursor + 0xA) == 1007 and r16(cursor + 0xA + 4) == 0x80
    assert r16(cursor + 0xA + 6) == 0xFFFE               # -2 low word
    assert r32(G_DRAW_CURSOR) == cursor + 0x14


def test_setup_sprite_rect_pure():
    from kegg.bridge.game_state import G_CUR_OBJ, G_CUR_WIDTH
    from kegg.recovered.anim import setup_sprite_rect
    d = bytearray(0x200000)
    sdef = 0x108000
    out = 0x109000
    # sprite def: width(+2), height(+4), x_offset(+0xa), y_offset(+0xc).
    # Use a NEGATIVE x_offset so left goes negative (regression: the fields are
    # read signed `movsx`, and left/top accumulate).
    d[sdef + 0x02:sdef + 0x04] = (10).to_bytes(2, "little")           # width
    d[sdef + 0x04:sdef + 0x06] = (8).to_bytes(2, "little")            # height
    d[sdef + 0x0A:sdef + 0x0C] = ((-3) & 0xFFFF).to_bytes(2, "little")  # x_off
    d[sdef + 0x0C:sdef + 0x0E] = (5).to_bytes(2, "little")           # y_off
    _w32(d, out + 0x00, 100)      # seed left
    _w32(d, out + 0x04, 200)      # seed top

    setup_sprite_rect(GameState(d), out, sdef)

    def s32(a):
        v = int.from_bytes(d[a:a + 4], "little")
        return v - 0x100000000 if v & 0x80000000 else v
    # current object latched, geometry copied
    assert int.from_bytes(d[G_CUR_OBJ:G_CUR_OBJ + 4], "little") == sdef
    assert int.from_bytes(d[G_CUR_WIDTH:G_CUR_WIDTH + 2], "little") == 10
    # left = 100 + (-3) = 97 ; top = 200 + 5 = 205
    assert s32(out + 0x00) == 97 and s32(out + 0x04) == 205
    # right = left + width - 2 = 97 + 10 - 2 = 105 ; bottom = 205 + 8 - 2 = 211
    assert s32(out + 0x08) == 105 and s32(out + 0x0C) == 211
