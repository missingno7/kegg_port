"""Krypton Egg adapter runtime wiring (DOS/4GW protected-mode).

Game knowledge only: the EXE name and command tail.  The 386/DPMI machinery is
the framework's (dos_re.runtime.create_pm_runtime).
"""
from __future__ import annotations

from pathlib import Path

from dos_re.runtime import PMRuntime, create_pm_runtime

EXE_NAME = "KE.EXE"


def create_game_runtime(exe_path: str | Path, *, game_root: str | Path | None = None,
                        command_tail: bytes | str = b"") -> PMRuntime:
    return create_pm_runtime(exe_path, game_root=game_root, command_tail=command_tail)
