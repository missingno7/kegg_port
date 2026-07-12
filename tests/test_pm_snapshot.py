"""PM snapshot resume-determinism proof.

The obligation from dos_re/pm_snapshot.py: resuming a snapshot must produce
the same execution as never having stopped.  Runs KE's boot, snapshots
mid-flight, runs on; then reloads and runs the same distance — CPU state and
full memory must match byte-exactly.  Skips without assets.
"""
from __future__ import annotations

import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")


def _digest(rt) -> tuple:
    cpu = rt.cpu
    return (tuple(cpu.r), cpu.eip, cpu.eflags, tuple(sorted(cpu.seg.items())),
            cpu.instruction_count,
            zlib.crc32(bytes(rt.mem.data)),
            zlib.crc32(b"".join(rt.dos.vga.planes)))


def test_snapshot_resume_matches_uninterrupted_run(tmp_path):
    from kegg.runtime import create_game_runtime
    from dos_re.pm_snapshot import save_pm_snapshot, load_pm_snapshot

    rt = create_game_runtime(EXE)
    rt.dos.key_queue.append(0x20)
    rt.cpu.run(2_000_000)                      # boot into the detection screen
    save_pm_snapshot(rt, tmp_path / "snap")
    rt.cpu.run(1_000_000)                      # the uninterrupted continuation
    want = _digest(rt)

    rt2 = load_pm_snapshot(EXE, tmp_path / "snap")
    assert _digest(rt2)[:5] == ( tuple(rt2.cpu.r), rt2.cpu.eip, rt2.cpu.eflags,
                                 tuple(sorted(rt2.cpu.seg.items())),
                                 rt2.cpu.instruction_count)  # sanity: digest is stable
    rt2.cpu.run(1_000_000)                     # the resumed continuation
    assert _digest(rt2) == want
