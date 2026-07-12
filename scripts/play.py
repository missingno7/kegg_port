"""play.py — the human entry point of the Krypton Egg port.

A thin game wrapper over ``dos_re.pm_player`` (the standard PM play runner:
live viewer with KBC keyboard / INT 33h mouse / wall-clock vsync pacing,
F10 screenshot, F12 snapshot, ``--snapshot`` resume, ``--headless`` smoke
runs).  Game knowledge only: the EXE, the window title, and the boot
screen's "press SPACE" seed for headless runs.

Usage:
    python scripts/play.py                       # live viewer
    python scripts/play.py --headless --steps N  # deterministic smoke run
    python scripts/play.py --snapshot <dir>      # resume a saved snapshot

CPython runs ~1-2 M instr/s; if the game feels slow, run under pypy
(13-17x, dos_re/docs/performance.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))              # the kegg adapter package
sys.path.insert(0, str(ROOT / "dos_re"))   # the dos_re submodule's repo root

from dos_re.pm_player import main as pm_main   # noqa: E402
from kegg.runtime import create_game_runtime   # noqa: E402


def main(argv=None) -> int:
    return pm_main(
        argv,
        default_exe=str(ROOT / "assets" / "KE.EXE"),
        create_runtime=create_game_runtime,
        title="Krypton Egg — dos_re (hybrid)",
        boot_keys=(0x20,),                 # the boot screen's SPACE prompt
        description=__doc__.splitlines()[0],
        artifacts_dir=ROOT / "artifacts",
    )


if __name__ == "__main__":
    raise SystemExit(main())
