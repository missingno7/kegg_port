"""play.py — the Krypton Egg entry point over the dos_re 3.0 player.

A thin protected-mode game wrapper: it hands `dos_re.pm_backend.PMFrontend`
(the canonical PM driver — live viewer with KBC keyboard / INT 33h mouse /
deterministic vsync, F10 screenshot / F12 snapshot, `--headless`, `--snapshot`
resume, `--record-replay`/`--play-replay`, `--profile verification`) only the
game knowledge: the executable + assets, window title, the "press SPACE" boot
seed, the Sound Blaster config KE probes, and the per-frame tick address.

Usage:
    python scripts/play.py                        # live viewer
    python scripts/play.py --headless --steps N   # deterministic smoke run
    python scripts/play.py --snapshot <dir>       # resume a saved snapshot
    python scripts/play.py --record-replay NAME   # record a ReplayArtifact
    python scripts/play.py --play-replay <dir>    # replay it deterministically

Recovered routines currently install as the port's existing seams via
`create_game_runtime`; migrating them to plan-selected 3.0 overrides
(`kegg/overrides.py`, proven in `tests/test_override_slice.py`) is in progress.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))              # the kegg adapter package
sys.path.insert(0, str(ROOT / "dos_re"))   # the dos_re submodule's repo root

from dos_re import player                    # noqa: E402
from dos_re.pm_backend import PMFrontend      # noqa: E402
from kegg.runtime import create_game_runtime  # noqa: E402


def _create_runtime(exe_path):
    return create_game_runtime(exe_path, game_root=str(ROOT / "assets"))


def main(argv=None) -> int:
    frontend = PMFrontend(
        ROOT,
        default_exe=str(ROOT / "assets" / "KE.EXE"),
        create_runtime=_create_runtime,
        title="Krypton Egg — dos_re 3.0 (hybrid)",
        boot_keys=(0x20,),                 # the boot screen's SPACE prompt
        sound_blaster=(0x210, 7, 1),       # KE's config probes DSP base $210
        frame_tick_addr=0x119D40,          # per-frame update entry (replay clock)
    )
    return player.main(frontend, argv, description=__doc__.splitlines()[0])


if __name__ == "__main__":
    raise SystemExit(main())
