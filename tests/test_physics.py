"""Recovered ball-physics logic — pure unit test + in-demo oracle check."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.bridge.ball_state import BallState, B_Y_TEMP, B_Y0, B_Y1  # noqa: E402
from kegg.recovered.physics import swap_ball_y, rects_overlap  # noqa: E402


class _R:
    """A minimal {left,top,right,bottom} rect for the pure overlap test."""
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


def test_rects_overlap_pure():
    a = _R(10, 10, 20, 20)
    assert rects_overlap(a, _R(15, 15, 25, 25)) is True    # corner overlap
    assert rects_overlap(a, _R(20, 20, 30, 30)) is True    # edge-touch counts
    assert rects_overlap(a, _R(21, 10, 30, 20)) is False   # b fully right
    assert rects_overlap(a, _R(0, 21, 5, 30)) is False     # b fully below
    assert rects_overlap(a, _R(0, 0, 9, 5)) is False       # b fully left+above
    # signed edges: negative coords behave like any other
    assert rects_overlap(_R(-20, -20, -10, -10), _R(-15, -15, -5, -5)) is True


def _w16(d, a, v):
    d[a:a + 2] = (v & 0xFFFF).to_bytes(2, "little")


def _r16(d, a):
    return int.from_bytes(d[a:a + 2], "little")


def test_swap_ball_y_pure():
    d = bytearray(0x200000)
    _w16(d, B_Y0, 111)          # front Y
    _w16(d, B_Y1, 222)          # back Y
    _w16(d, B_Y_TEMP, 999)      # scratch (overwritten)

    swap_ball_y(BallState(d))

    assert _r16(d, B_Y0) == 222        # slots swapped
    assert _r16(d, B_Y1) == 111
    assert _r16(d, B_Y_TEMP) == 111    # scratch left holding the old front Y


def test_step_sequence_pure():
    from kegg.recovered.sequence import step_sequence
    d = bytearray(0x4000)
    # three 8-byte {value,count} records; rec2's count is a -2 loop-back to rec0
    for addr, val, cnt in ((0x1000, 100, 5), (0x1008, 200, 3), (0x1010, 300, -2)):
        _w16(d, addr, val & 0xFFFF)
        d[addr:addr + 4] = (val & 0xFFFFFFFF).to_bytes(4, "little")
        d[addr + 4:addr + 8] = (cnt & 0xFFFFFFFF).to_bytes(4, "little")
    CUR, CNT = 0x2000, 0x2004

    def setup(cursor, counter):
        d[CUR:CUR + 4] = cursor.to_bytes(4, "little")
        d[CNT:CNT + 4] = counter.to_bytes(4, "little")

    def r32(a):
        v = int.from_bytes(d[a:a + 4], "little")
        return v - 0x100000000 if v & 0x80000000 else v

    # path A: countdown not expired -> just decrements, returns current value
    setup(0x1000, 5)
    assert step_sequence(d, CNT, CUR) == 100
    assert r32(CNT) == 4 and r32(CUR) == 0x1000

    # path B: expires -> advance to rec1, reload its (positive) count
    setup(0x1000, 1)
    assert step_sequence(d, CNT, CUR) == 200
    assert r32(CUR) == 0x1008 and r32(CNT) == 3

    # path C: expires -> rec2's count is negative -> loop back 2 records to rec0
    setup(0x1008, 1)
    assert step_sequence(d, CNT, CUR) == 100
    assert r32(CUR) == 0x1000 and r32(CNT) == 5


DEMO = ROOT / "artifacts" / "demos" / "demo_167343187"


@pytest.mark.skipif(not DEMO.exists(), reason="level-2 demo bundle not present")
def test_ball_y_swap_verifies_against_oracle():
    """Replay the tens-of-balls level-2 demo with the differential verifier
    focused on the ball-Y swap; every call must be byte-exact."""
    from dos_re.pm_snapshot import load_pm_snapshot
    from dos_re.pm_input_demo import PMInputDemo, FrameClock, FramePaced
    from dos_re.pm_player import send_key
    from dos_re.pm_verification import (install_pm_hook_verifier,
                                        PMHookVerifierConfig)
    from kegg.render_hooks import install_render_hooks
    from kegg.logic_hooks import install_logic_hooks, BALL_Y_SWAP

    demo = PMInputDemo.load(str(DEMO))
    rt = load_pm_snapshot(str(ROOT / "assets" / "KE.EXE"), str(DEMO / "snapshot"))
    install_render_hooks(rt.cpu)
    install_logic_hooks(rt.cpu)
    cpu, dos = rt.cpu, rt.dos
    for k in list(cpu.replacement_hooks):
        if k != BALL_Y_SWAP:
            cpu.hook_verifier_passthrough.add(k)
    v = install_pm_hook_verifier(rt, PMHookVerifierConfig(samples=None))
    by_frame = demo.by_frame()

    def on_frame(f):
        for kind, payload in by_frame.get(f, ()):
            if kind == "key":
                send_key(dos, payload[1], payload[0])
            elif kind == "mouse":
                dos.set_mouse_norm(payload[0], payload[1])
                dos.mouse_buttons = payload[2]

    clock = FrameClock(cpu, 0x119D40, on_frame)
    while clock.frame < demo.total_frames and not cpu.halted:
        clock.stop_at = clock.frame + 1
        try:
            cpu.run(4_000_000)
        except FramePaced:
            pass
    assert v.calls_per_hook.get(BALL_Y_SWAP, 0) > 100   # exercised + byte-exact
