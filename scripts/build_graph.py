"""build_graph.py — regenerate the committed lifted-vmless hot-set graph.

The reproducible recipe for ``kegg/graph_hot/`` (the ``generated-hot-graph``
catalog entry): emit each function in ``kegg.overrides.GRAPH_HOT_EIPS`` as a
32-bit lifted module, linking direct calls between all-near-ret members so they
bypass the interpreter.  The modules are byte-exact against the ASM oracle
(proven by the differential PM verifier over the ball-heavy snapshot); this
script just rebuilds them deterministically from KE.EXE.

    python scripts/build_graph.py            # rewrite kegg/graph_hot/
    python scripts/build_graph.py --check    # verify committed == freshly emitted

Run it after changing GRAPH_HOT_EIPS or the 32-bit emitter; the committed
modules also self-check their entry signature at call time, so a stale image
fails loud rather than running the wrong bytes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dos_re.lift.cfg32 import scan_function32                 # noqa: E402
from dos_re.lift.decode import RET                             # noqa: E402
from dos_re.lift.emit32 import EmitUnsupported, emit_function32  # noqa: E402

from kegg.overrides import GRAPH_HOT_DIR, GRAPH_HOT_EIPS       # noqa: E402
from kegg.runtime import create_game_runtime                   # noqa: E402

EXE = ROOT / "assets" / "KE.EXE"


def _emit_all() -> dict[str, str]:
    rt = create_game_runtime(str(EXE), install_replacements=False)
    read = rt.mem.data.__getitem__
    scans = {e: scan_function32(read, e) for e in GRAPH_HOT_EIPS}
    # only all-near-RET-exit members are safe to LINK (call_linked32's
    # returned-to-ret_ip contract); the rest stay emulate_call32.
    linkable = {e for e in GRAPH_HOT_EIPS
                if scans[e].liftable and all(x.kind == RET for x in scans[e].exits)}
    out: dict[str, str] = {}
    for e in GRAPH_HOT_EIPS:
        scan = scans[e]
        if not scan.liftable:
            raise SystemExit(f"0x{e:X} is no longer liftable: {scan.refusals}")
        targets = sorted(t for t in scan.calls_near if t in linkable and t != e)
        link_map = {t: f'LINKS["0x{t:X}"]' for t in targets}
        link_imports = (
            ("LINKS = {%s}  # filled by resolve_links32"
             % ", ".join(f'"0x{t:X}": None' for t in targets),)
            if link_map else ())
        try:
            src = emit_function32(scan, f"lift_{e:x}",
                                  signature=bytes(rt.mem.data[e:e + 8]),
                                  link_map=link_map, link_imports=link_imports)
        except EmitUnsupported as exc:
            raise SystemExit(f"0x{e:X} no longer emits: {exc}")
        out[f"lift_{e:x}.py"] = src
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify committed modules match a fresh emission "
                         "(non-zero exit if they drift); does not write")
    args = ap.parse_args(argv)

    if not EXE.exists():
        raise SystemExit("assets/KE.EXE not present")
    fresh = _emit_all()

    if args.check:
        drift = []
        committed = {p.name for p in GRAPH_HOT_DIR.glob("lift_*.py")}
        if committed != set(fresh):
            drift.append(f"module set differs: committed {sorted(committed)} "
                         f"vs fresh {sorted(fresh)}")
        for name, src in fresh.items():
            path = GRAPH_HOT_DIR / name
            if not path.is_file() or path.read_text() != src:
                drift.append(name)
        if drift:
            print("DRIFT (run without --check to regenerate): " + ", ".join(map(str, drift)))
            return 1
        print(f"OK: all {len(fresh)} kegg/graph_hot modules match a fresh emission")
        return 0

    GRAPH_HOT_DIR.mkdir(exist_ok=True)
    for stale in GRAPH_HOT_DIR.glob("lift_*.py"):
        if stale.name not in fresh:
            stale.unlink()
    for name, src in fresh.items():
        (GRAPH_HOT_DIR / name).write_text(src)
    print(f"wrote {len(fresh)} modules -> {GRAPH_HOT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
