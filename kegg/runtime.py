"""Krypton Egg adapter runtime wiring (DOS/4GW protected-mode).

Game knowledge only: the EXE name and which recovered/lifted hooks to install.
The 386/DPMI machinery is the framework's (dos_re.runtime.create_pm_runtime).
"""
from __future__ import annotations

from pathlib import Path

from dos_re.runtime import PMRuntime, create_pm_runtime

EXE_NAME = "KE.EXE"


def create_game_runtime(exe_path: str | Path, *, game_root: str | Path | None = None,
                        command_tail: bytes | str = b"",
                        install_replacements: bool = True) -> PMRuntime:
    """Boot a fresh runtime.

    ``install_replacements=True`` (the default, for play) installs the
    verified lifted hooks — a ~2.5x speedup on the render-heavy inner loop,
    each guarding its own entry signature.  Pass ``False`` for the pure-ASM
    oracle path (the differential verifier boots this way and installs the
    hook under test itself)."""
    rt = create_pm_runtime(exe_path, game_root=game_root, command_tail=command_tail)
    if install_replacements:
        from kegg.lifted32 import install_lifted32
        install_lifted32(rt.cpu)
    return rt
