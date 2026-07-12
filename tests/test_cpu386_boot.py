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

# Frontier floor: startup currently reaches DPMI DOS-memory allocation.
BOOT_FLOOR = 15_000


def test_startup_runs_c_runtime():
    from kegg.runtime import create_game_runtime
    rt = create_game_runtime(EXE)
    assert rt.cpu.eip == 0x242D8            # LE entry
    try:
        rt.cpu.run(1_000_000)
    except (NotImplementedError, Exception):  # noqa: BLE001 — any fail-loud stop is fine
        pass
    assert rt.cpu.instruction_count >= BOOT_FLOOR, (
        f"startup regressed: only {rt.cpu.instruction_count} instructions "
        f"(floor {BOOT_FLOOR})")
