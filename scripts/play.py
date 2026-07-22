"""play.py — the Krypton Egg entry point over the dos_re 3.0 player.

A thin protected-mode game wrapper: it hands the port's
:class:`kegg.frontend.KryptonEggFrontend` (a ``dos_re.pm_backend.PMFrontend``
carrying the authored override catalog) only the game knowledge — the
executable + assets, window title, the "press SPACE" boot seed, the Sound
Blaster config KE probes, and the per-frame tick address.  The player resolves
the execution plan, binds the recovered overrides through it, and drives the
live viewer / headless / replay lifecycle.

Usage:
    python scripts/play.py                        # live viewer
    python scripts/play.py --headless --steps N   # deterministic smoke run
    python scripts/play.py --plan-only            # print the bound override plan
    python scripts/play.py --snapshot <dir>       # resume a saved snapshot
    python scripts/play.py --record-replay NAME   # record a ReplayArtifact
    python scripts/play.py --play-replay <dir>    # replay it deterministically

Run under PyPy: the 386 interpreter reaches ~11 Minstr/s under PyPy (>1x real
time, smooth audio) versus ~0.8 Minstr/s under CPython (~0.08x — the Sound
Blaster PCM starves and stutters).  Invoked with plain ``python`` (CPython),
this script re-execs itself under PyPy when one is on PATH; set
``KEGG_NO_REEXEC=1`` to stay on the current interpreter.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ensure_pypy() -> None:
    """Re-exec under PyPy for real-time speed (smooth audio) when launched on
    CPython.  A no-op under PyPy, when opted out, or when no PyPy is found."""
    if platform.python_implementation() == "PyPy" or os.environ.get("KEGG_NO_REEXEC"):
        return
    pypy = shutil.which("pypy3.11") or shutil.which("pypy3") or shutil.which("pypy")
    if not pypy:
        print("NOTE: running under CPython (~0.08x real time — audio will stutter). "
              "Install PyPy 3.11 for smooth play.", file=sys.stderr)
        return
    os.environ["KEGG_NO_REEXEC"] = "1"          # guard against a re-exec loop
    print(f"[play] re-exec under PyPy for real-time speed: {pypy}", file=sys.stderr)
    os.execv(pypy, [pypy, str(Path(__file__).resolve()), *sys.argv[1:]])


sys.path.insert(0, str(ROOT))              # the kegg adapter package
sys.path.insert(0, str(ROOT / "dos_re"))   # the dos_re submodule's repo root

from dos_re import player                       # noqa: E402
from kegg.frontend import KryptonEggFrontend    # noqa: E402
from kegg.runtime import create_game_runtime    # noqa: E402


def _create_runtime(exe_path):
    # The plan owns installation: boot the pure interpreted oracle and let
    # bind_execution_plan install the recovered overrides through their adapters.
    return create_game_runtime(exe_path, game_root=str(ROOT / "assets"),
                               install_replacements=False)


def main(argv=None) -> int:
    frontend = KryptonEggFrontend(
        ROOT,
        default_exe=str(ROOT / "assets" / "KE.EXE"),
        create_runtime=_create_runtime,
        title="Krypton Egg — dos_re 3.0",
        boot_keys=(0x20,),                 # the boot screen's SPACE prompt
        sound_blaster=(0x210, 7, 1),       # KE's config probes DSP base $210
        frame_tick_addr=0x119D40,          # per-frame update entry (replay clock)
    )
    return player.main(frontend, argv, description=__doc__.splitlines()[0])


if __name__ == "__main__":
    _ensure_pypy()
    raise SystemExit(main())
