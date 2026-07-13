"""Recovered composed collision logic — pure unit test + observable-state check."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.recovered.collision import remove_list_element  # noqa: E402


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
