"""CPU386 + DOS4GWHost bring-up smoke test.

Boots KE.EXE's LE image on the flat 386 core and runs the Watcom C-runtime
startup.  Guards the progress frontier: the boot must execute at least this many
instructions before hitting the next unimplemented service, so a regression in
the CPU/host is caught.  Raise the floor as more of startup is implemented.

Skips when assets/ is absent (CI has no game files).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")

def test_startup_runs_c_runtime():
    from kegg.runtime import create_game_runtime
    rt = create_game_runtime(EXE)
    # LE entry, rebased above 1 MB by the loader (link base 0x242D8).
    assert rt.cpu.eip == 0x1242D8
    # The whole first million instructions must execute without a fail-loud
    # stop (startup runs the full detection screen and beyond).
    rt.cpu.run(1_000_000)
    assert rt.cpu.instruction_count == 1_000_000
    assert not rt.cpu.halted
