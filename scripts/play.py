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
    python scripts/play.py --fast                 # + lifted-vmless acceleration
    python scripts/play.py --headless --steps N   # deterministic smoke run
    python scripts/play.py --plan-only            # print the bound override plan
    python scripts/play.py --snapshot <dir>       # resume a saved snapshot
    python scripts/play.py --record-replay NAME   # record a ReplayArtifact
    python scripts/play.py --play-replay <dir>    # replay it deterministically

Runs on whatever interpreter you launch it with — plain CPython is a
first-class target (it is what the mobile/native ports run on; iOS has no PyPy
JIT).  The path to real-time on CPython is native rewriting: the recovered
overrides and the lifted-vmless graph (``--fast``) replace interpreted work
with native code, and the native sound island moves audio off the interpreted
path.  PyPy still gives the fastest pure-interpreter runs if you prefer it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    raise SystemExit(main())
