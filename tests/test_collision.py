"""Recovered composed collision logic — pure unit test + observable-state check."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.recovered.collision import (remove_list_element, _emit_draw,  # noqa: E402
                                      G_DRAW_CURSOR, G_DRAW_PARAM, L_BASE, L_STRIDE)


def _w32(d, a, v):
    d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")


def _r32(d, a):
    return int.from_bytes(d[a:a + 4], "little")


def _make_list(index, count, base_at=0x1000):
    """Four 18-byte records, record i filled with byte value i."""
    d = bytearray(0x200000)                # must span the 0x14DDxx list globals
    for i in range(4):
        rec = base_at + i * 0x12
        d[rec:rec + 0x12] = bytes([i]) * 0x12
    _w32(d, 0x14DDA4, base_at + index * 0x12)   # base -> current record
    _w32(d, 0x14DDBC, index)
    _w32(d, 0x14DDC0, count)
    return d


def test_remove_middle_element():
    d = _make_list(index=1, count=4)
    remove_list_element(d)
    assert _r32(d, 0x14DDC0) == 3          # count decremented
    assert _r32(d, 0x14DDBC) == 0          # index decremented (revisit slot)
    # records 2 and 3 shifted down into slots 1 and 2
    assert d[0x1000 + 1 * 0x12] == 2
    assert d[0x1000 + 2 * 0x12] == 3
    assert d[0x1000 + 0 * 0x12] == 0       # slot 0 untouched


def test_remove_last_element():
    d = _make_list(index=3, count=4)
    remove_list_element(d)
    assert _r32(d, 0x14DDC0) == 3          # count decremented
    assert _r32(d, 0x14DDBC) == 2          # index decremented, no shift
    # nothing shifted: slots keep their original content
    for i in range(4):
        assert d[0x1000 + i * 0x12] == i


def test_emit_draw_pure():
    d = bytearray(0x200000)
    brick = 0x1000
    d[brick:brick + 2] = (66).to_bytes(2, "little")       # brick x
    d[brick + 4:brick + 6] = (115).to_bytes(2, "little")  # brick y
    _w32(d, G_DRAW_PARAM, 0xABCD1234)                     # the draw dword
    _w32(d, G_DRAW_CURSOR, 0x2000)                        # cursor
    _w32(d, L_BASE, brick)

    _emit_draw(d, brick)

    assert _r32(d, 0x2000) == 0xABCD1234                  # dword: draw param
    assert int.from_bytes(d[0x2004:0x2006], "little") == 66   # word: x
    assert int.from_bytes(d[0x2006:0x2008], "little") == 115  # word: y
    assert int.from_bytes(d[0x2008:0x200A], "little") == 0    # word: flags
    assert _r32(d, G_DRAW_CURSOR) == 0x2000 + 0xA        # cursor advanced
    assert _r32(d, L_BASE) == brick + L_STRIDE           # brick ptr advanced


DEMO = ROOT / "artifacts" / "demos" / "demo_167343187"


@pytest.mark.skipif(not DEMO.exists(), reason="level-2 demo bundle not present")
def test_remove_list_element_composition_verifies():
    """Replay the demo with the observable-state composition verifier on the
    recovered brick-removal; every call must match the interpreted original
    outside its transient stack frame."""
    from dos_re.pm_snapshot import load_pm_snapshot
    from dos_re.pm_input_demo import PMInputDemo, FrameClock, FramePaced
    from dos_re.pm_player import send_key
    from dos_re.pm_composition import (install_pm_composition_verifier,
                                       PMCompositionConfig)
    from kegg.render_hooks import install_render_hooks
    from kegg.logic_hooks import install_logic_hooks
    from kegg.composition_hooks import install_composition_hooks, REMOVE_LIST_ELEM

    demo = PMInputDemo.load(str(DEMO))
    rt = load_pm_snapshot(str(ROOT / "assets" / "KE.EXE"), str(DEMO / "snapshot"))
    install_render_hooks(rt.cpu)
    install_logic_hooks(rt.cpu)
    install_composition_hooks(rt.cpu)
    # 0x114291's only caller in this demo is 0x114085; leave 0x114085
    # interpreted so it actually reaches (and we can verify) 0x114291.
    from kegg.composition_hooks import PROCESS_BRICKS
    rt.cpu.replacement_hooks.pop(PROCESS_BRICKS, None)
    rt.cpu.hook_names.pop(PROCESS_BRICKS, None)
    cpu, dos = rt.cpu, rt.dos
    by_frame = demo.by_frame()

    def on_frame(f):
        for kind, payload in by_frame.get(f, ()):
            if kind == "key":
                send_key(dos, payload[1], payload[0])
            elif kind == "mouse":
                dos.set_mouse_norm(payload[0], payload[1])
                dos.mouse_buttons = payload[2]

    clock = FrameClock(cpu, 0x119D40, on_frame)
    for k in list(cpu.replacement_hooks):
        if k != REMOVE_LIST_ELEM:
            cpu.hook_verifier_passthrough.add(k)
    v = install_pm_composition_verifier(rt, PMCompositionConfig(samples=None))
    while clock.frame < demo.total_frames and not cpu.halted:
        clock.stop_at = clock.frame + 1
        try:
            cpu.run(4_000_000)
        except FramePaced:
            pass
    assert v.calls_per_hook.get(REMOVE_LIST_ELEM, 0) > 10   # exercised + verified


@pytest.mark.skipif(not DEMO.exists(), reason="level-2 demo bundle not present")
def test_process_brick_list_composition_verifies():
    """The full ball-vs-brick loop, observable-verified over the demo (includes
    the collision-response path with the per-type handler delegated)."""
    from dos_re.pm_snapshot import load_pm_snapshot
    from dos_re.pm_input_demo import PMInputDemo, FrameClock, FramePaced
    from dos_re.pm_player import send_key
    from dos_re.pm_composition import (install_pm_composition_verifier,
                                       PMCompositionConfig)
    from kegg.render_hooks import install_render_hooks
    from kegg.logic_hooks import install_logic_hooks
    from kegg.composition_hooks import install_composition_hooks, PROCESS_BRICKS

    demo = PMInputDemo.load(str(DEMO))
    rt = load_pm_snapshot(str(ROOT / "assets" / "KE.EXE"), str(DEMO / "snapshot"))
    install_render_hooks(rt.cpu)
    install_logic_hooks(rt.cpu)
    install_composition_hooks(rt.cpu)
    cpu, dos = rt.cpu, rt.dos
    by_frame = demo.by_frame()

    def on_frame(f):
        for kind, payload in by_frame.get(f, ()):
            if kind == "key":
                send_key(dos, payload[1], payload[0])
            elif kind == "mouse":
                dos.set_mouse_norm(payload[0], payload[1])
                dos.mouse_buttons = payload[2]

    clock = FrameClock(cpu, 0x119D40, on_frame)
    for k in list(cpu.replacement_hooks):
        if k != PROCESS_BRICKS:
            cpu.hook_verifier_passthrough.add(k)
    v = install_pm_composition_verifier(rt, PMCompositionConfig(samples=None))
    while clock.frame < demo.total_frames and not cpu.halted:
        clock.stop_at = clock.frame + 1
        try:
            cpu.run(4_000_000)
        except FramePaced:
            pass
    assert v.calls_per_hook.get(PROCESS_BRICKS, 0) == demo.total_frames
