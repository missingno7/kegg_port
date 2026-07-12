"""play.py — the human entry point of this game port.  ADAPT ME.

This is the standard play runner every port ships: run the (hybrid) game in a
live viewer, resume/save snapshots, record/replay input demos, take
screenshots — the artifacts the human owner hands to the AI during reverse
engineering.  The game-agnostic 90% lives in ``dos_re.player`` (the unified
CLI, the viewer loop + hotkeys, headless replay, crash snapshots); this file
holds ONLY the game-specific frontend.  Read ``dos_re/dos_re/player.py``'s
docstring for the full CLI contract before changing anything here.

Usage (the standard surface — identical across every port):
    python scripts/play.py                                # live viewer (hybrid runtime)
    python scripts/play.py --headless --steps 1000000 --save-snapshot   # snapshot for study
    python scripts/play.py --snapshot artifacts/snap_x    # resume a snapshot
    python scripts/play.py --record-demo NAME             # record from launch (F11 toggles)
    python scripts/play.py --play-demo artifacts/demos/demo_x            # watch a replay
    python scripts/play.py --play-demo artifacts/demos/demo_x --headless # fast deterministic replay
    python scripts/play.py --play-demo artifacts/demos/demo_x --demo-continue  # play on after it ends
    python scripts/play.py --no-replacements              # ORACLE mode: pure original ASM

Viewer hotkeys: F10 screenshot, F11 demo-record toggle, F12 snapshot.

Adapting to your game (every GAME-SPECIFIC block below):
 1. Point ``default_exe``/``default_game_root`` at your assets and set ``name``.
 2. Wire ``create_runtime``/``load_snapshot_runtime`` to YOUR adapter package's
    ``create_<game>_runtime``/``load_<game>_snapshot`` once it exists (that is
    what installs your hooks); until then the generic runtime is fine.
 3. Tune the pacing defaults.  Start with the simple deterministic model
    (fixed --steps-per-frame + --timer-irqs-per-frame; the frame index IS the
    demo clock).  Only replace ``advance_frame`` when your game's timing
    demands it — and then extend ``demo_metadata``/``apply_demo_metadata`` so
    replays restore your knobs (see the cookbook's play-runner entry).
 4. Override ``decode_frame`` only if your game uses video modes the default
    decoder lacks (CGA / Tandy / text — overkill_port is the worked example).
 5. As hook tiers appear, override ``apply_hook_mode`` to honour
    --safe-hooks / --verify-hooks / --trace-hooks instead of failing loud.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))              # your adapter package (mygame/)
sys.path.insert(0, str(ROOT / "dos_re"))   # the dos_re submodule's repo root

from dos_re import player  # noqa: E402

# GAME-SPECIFIC: once your adapter package exists, import its runtime builders:
# from mygame.runtime import create_mygame_runtime, load_mygame_snapshot  # noqa: E402


class Frontend(player.GameFrontend):
    # GAME-SPECIFIC: identity + asset locations -------------------------------
    name = "mygame"
    default_exe = str(ROOT / "assets" / "GAME.EXE")
    default_game_root = str(ROOT / "assets")
    default_dos_args = ""

    # GAME-SPECIFIC: pacing (the simple deterministic model's knobs) ----------
    # steps-per-frame: VM instructions per displayed/simulated frame; raise it
    # until the game feels right in the viewer, then freeze it — demos record it.
    default_steps_per_frame = 40_000
    # Games that idle on the PIT ISR (INT 08h) hang forever at 0 — set 1 the
    # moment the title screen sits in a timer wait (skyroads_port hit this).
    default_timer_irqs_per_frame = 0
    default_present_hz = 60

    # GAME-SPECIFIC: boot through YOUR adapter so your hooks install ----------
    # def create_runtime(self, args):
    #     return create_mygame_runtime(args.exe, game_root=args.game_root,
    #                                  command_tail=args.dos_args)
    #
    # def load_snapshot_runtime(self, args, snapshot_dir):
    #     return load_mygame_snapshot(args.exe, snapshot_dir,
    #                                 game_root=args.game_root)

    # GAME-SPECIFIC: extra flags (never rename the standard set) --------------
    # def add_arguments(self, parser):
    #     parser.add_argument("--boot-intro", action="store_true",
    #                         help="run the full intro instead of skipping to the menu")


def main(argv: list[str] | None = None) -> int:
    return player.main(Frontend(ROOT), argv, description=__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
