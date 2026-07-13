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
