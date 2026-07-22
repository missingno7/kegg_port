"""Krypton Egg adapter runtime wiring (DOS/4GW protected-mode).

Game knowledge only: the EXE name and, optionally, binding the recovered
override plan.  The 386/DPMI machinery is the framework's
(``dos_re.runtime.create_pm_runtime``); installation is owned by the execution
plan (``kegg.overrides``), not by eager per-module hook installers.
"""
from __future__ import annotations

from pathlib import Path

from dos_re.runtime import PMRuntime, create_pm_runtime

EXE_NAME = "KE.EXE"


def create_game_runtime(exe_path: str | Path, *, game_root: str | Path | None = None,
                        command_tail: bytes | str = b"",
                        install_replacements: bool = True) -> PMRuntime:
    """Boot a fresh runtime.

    ``install_replacements=True`` (the default, for play) binds the authored
    override plan (``kegg.overrides.bind_overrides``): every recovered routine
    installs through its backend adapter — the plan owns installation.  Pass
    ``False`` for the pure interpreted oracle path (the differential verifier
    boots this way and binds the override under test itself; the player boots
    this way and binds the plan through ``bind_execution_plan``).
    """
    rt = create_pm_runtime(exe_path, game_root=game_root, command_tail=command_tail)
    if install_replacements:
        from kegg.overrides import bind_overrides
        bind_overrides(rt, str(exe_path))
    return rt
