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
    RECOVERED native blitter (0x1222D1, unclipped path; clipped variants fall
    back to the interpreter) — ~3.75x over the pure interpreter on the
    gameplay snapshot.  The draw entry at 0x122288 is left un-hooked on
    purpose: its tiny queue-write prologue interprets and falls straight into
    the recovered blitter, so every draw takes the fast path (hooking it with
    the older lifted version would run its own inline blit and bypass this).
    Pass ``False`` for the pure-ASM oracle path (the differential verifier
    boots this way and installs the hook under test itself)."""
    rt = create_pm_runtime(exe_path, game_root=game_root, command_tail=command_tail)
    if install_replacements:
        from kegg.render_hooks import install_render_hooks
        from kegg.logic_hooks import install_logic_hooks
        install_render_hooks(rt.cpu)      # the two recovered Mode X blitters
        install_logic_hooks(rt.cpu)       # recovered per-frame gameplay logic
    return rt
