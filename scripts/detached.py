"""detached.py -- run Krypton Egg WITHOUT KE.EXE, from a captured boot image.

    python scripts/detached.py capture [--boot-steps N]
        boot KE.EXE ONCE and snapshot the whole machine (memory image + all
        device state) to artifacts/detached_boot/.  This is the only step that
        reads KE.EXE.

    python scripts/detached.py verify [--steps N]
        prove the detach guarantee: resuming the snapshot EXE-FREE
        (load_snapshot_headless) and running N instructions is BYTE-IDENTICAL to
        resuming it with the EXE loaded -- the game does not depend on the
        original binary after capture.

    python scripts/detached.py play [--steps N] [--full-graph]
        run the game detached -- reconstructed from the snapshot with no
        load_le, optionally with the whole-game lifted graph bound.  Never reads
        KE.EXE.

The snapshot IS the game's own code+data image, so artifacts/detached_boot/ is
gitignored and rebuilt by `capture` (like kegg/graph_full/).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dos_re.pm_snapshot import (save_pm_snapshot, load_pm_snapshot,        # noqa: E402
                                load_snapshot_headless)
from dos_re.lift.install import activate_generated_graph32                 # noqa: E402
from dos_re.cpu import HaltExecution                                        # noqa: E402

from kegg.overrides import GRAPH_FULL_DIR                                    # noqa: E402
from kegg.runtime import create_game_runtime                                # noqa: E402

EXE = ROOT / "assets" / "KE.EXE"
ASSETS = ROOT / "assets"
SNAP = ROOT / "artifacts" / "detached_boot"


def _seed_input(rt, n=500):
    for _ in range(n):                    # console reads must not exhaust headless
        rt.dos.key_queue.append(0x20)


def _digest(rt):
    return (hashlib.sha256(bytes(rt.mem.data)).hexdigest()[:16],
            rt.cpu.eip, rt.cpu.instruction_count)


def cmd_capture(args) -> int:
    if not EXE.exists():
        raise SystemExit("assets/KE.EXE not present (capture needs it once)")
    rt = create_game_runtime(str(EXE), install_replacements=False)
    _seed_input(rt)
    rt.cpu.run(args.boot_steps)
    save_pm_snapshot(rt, str(SNAP))
    print(f"captured at instruction {rt.cpu.instruction_count:,} "
          f"(eip=0x{rt.cpu.eip:X}) -> {SNAP}")
    return 0


def cmd_verify(args) -> int:
    if not (SNAP / "pm_state.json").exists():
        raise SystemExit("no snapshot: run `capture` first")
    # EXE-free resume vs EXE-loaded resume, same forward run.
    free = load_snapshot_headless(SNAP, game_root=str(ASSETS))
    assert free.image is None
    free.cpu.run(args.steps)
    b = _digest(free)
    if not EXE.exists():
        print(f"EXE-free resume ran {args.steps:,} instrs: mem={b[0]} "
              f"eip=0x{b[1]:X} (no EXE present to cross-check)")
        return 0
    exe = load_pm_snapshot(str(EXE), SNAP, game_root=str(ASSETS))
    exe.cpu.run(args.steps)
    a = _digest(exe)
    print(f"EXE-loaded : mem={a[0]} eip=0x{a[1]:X} ic={a[2]:,}")
    print(f"EXE-free   : mem={b[0]} eip=0x{b[1]:X} ic={b[2]:,}")
    ok = a == b
    print(f"DETACHED RESUME IS BYTE-IDENTICAL: {ok}")
    return 0 if ok else 1


def cmd_play(args) -> int:
    if not (SNAP / "pm_state.json").exists():
        raise SystemExit("no snapshot: run `capture` first")
    rt = load_snapshot_headless(SNAP, game_root=str(ASSETS))
    assert rt.image is None, "play must not load KE.EXE"
    bound = 0
    if args.full_graph:
        if not any(GRAPH_FULL_DIR.glob("lift_*.py")):
            raise SystemExit("full graph not built: python scripts/build_full_graph.py")
        bound = len(activate_generated_graph32(rt.cpu, GRAPH_FULL_DIR))
    _seed_input(rt)
    start = rt.cpu.instruction_count
    try:
        rt.cpu.run(args.steps)
    except HaltExecution:
        print("game halted")
    ran = rt.cpu.instruction_count - start
    print(f"played DETACHED (no KE.EXE): ran {ran:,} instructions to "
          f"eip=0x{rt.cpu.eip:X}"
          + (f", {bound} lifted-graph functions bound" if bound else ""))
    if args.png:
        from dos_re.pm_backend import render_pm_frame, write_rgb_png
        rgb, w, h = render_pm_frame(rt.dos)
        write_rgb_png(Path(args.png), rgb, width=w, height=h)
        print(f"wrote the detached frame ({w}x{h}) -> {args.png}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--boot-steps", type=int, default=15_000_000)
    c.set_defaults(fn=cmd_capture)
    v = sub.add_parser("verify")
    v.add_argument("--steps", type=int, default=2_000_000)
    v.set_defaults(fn=cmd_verify)
    p = sub.add_parser("play")
    p.add_argument("--steps", type=int, default=2_000_000)
    p.add_argument("--full-graph", action="store_true", dest="full_graph")
    p.add_argument("--png", default="", help="render the final detached frame to this PNG")
    p.set_defaults(fn=cmd_play)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
