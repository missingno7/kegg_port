"""build_full_graph.py -- regenerate the full-game lifted-vmless graph.

The reproducible recipe for ``kegg/graph_full/`` (the ``generated-full-graph``
catalog entry): emit EVERY statically-liftable function of KE.EXE as a 32-bit
lifted module, linking direct calls between all-near-ret members so they bypass
the interpreter -- MINUS two exclusion sets:

  * the convergence inventory (environment-wait loops + stack-switch /
    computed-transfer routines that cannot be lift-and-linked), derived by a
    slow differential-verifier pass and recorded in
    ``kegg/graph_full.manifest.json``; and
  * the authored override EIPs (``kegg.overrides.OVERRIDE_EIPS``) -- the
    hand-recovered faithful routines win at their own seams, so the graph stays
    disjoint from them and calls into them fall through to the authored adapter.

    python scripts/build_full_graph.py                  # emit kegg/graph_full/
    python scripts/build_full_graph.py --check          # committed == fresh
    python scripts/build_full_graph.py --write-manifest # recompute graph_eips

The exclusion inventory is re-derivable with (slow, PyPy recommended)::

    pypy dos_re/tools/pmlift.py --exe assets/KE.EXE --auto-entries 5000 \\
        --emit-graph <dir> --verify --steps 80000000 --auto-exclude-waits 20

``kegg/graph_full/`` is gitignored -- ~14 MB of transliterated game code that
anyone with KE.EXE rebuilds in seconds; the small manifest is the committed
contract, and ``--check`` proves the manifest still matches the image.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re"), str(ROOT / "dos_re" / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dos_re.lift.cfg32 import scan_function32                    # noqa: E402
from dos_re.lift.decode import RET                                # noqa: E402
from dos_re.lift.emit32 import EmitUnsupported, emit_function32   # noqa: E402
from pmlift import auto_entries                                   # noqa: E402

from kegg.overrides import (GRAPH_FULL_DIR, MANIFEST_PATH,        # noqa: E402
                            OVERRIDE_EIPS)
from kegg.runtime import create_game_runtime                      # noqa: E402

EXE = ROOT / "assets" / "KE.EXE"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def _excluded(manifest: dict) -> set[int]:
    """Everything kept out of the graph: convergence waits + crashes, and the
    authored override EIPs (authored adapters win at those seams)."""
    runtime = manifest["excluded_waits"] + manifest["excluded_crashes"]
    return {int(x, 16) for x in runtime} | set(OVERRIDE_EIPS)


def _plan(rt, manifest: dict):
    """Resolve the full emission plan from the image + manifest exclusions.

    Mirrors ``pmlift`` emit-graph exactly so a module built here is byte-for-byte
    what the converger emitted: linkable = all-near-RET liftable members not
    excluded; each lifted function links only to linkable callees.  Returns
    ``(scans, liftable, linkable, graph_eips)``.
    """
    read = rt.mem.data.__getitem__
    entries = auto_entries(rt, manifest["auto_entries"])
    scans = {e: scan_function32(read, e) for e in entries}
    liftable = [e for e in entries if scans[e].liftable]
    excluded = _excluded(manifest)
    linkable = {e for e in liftable
                if e not in excluded
                and all(x.kind == RET for x in scans[e].exits)}
    graph_eips = [e for e in liftable if e not in excluded]
    return scans, liftable, linkable, graph_eips


def _emit(rt, scans, graph_eips, linkable) -> dict[str, str]:
    """Emit each graph member as ``lift_<hex>.py`` -- byte-identical to pmlift."""
    out: dict[str, str] = {}
    for e in graph_eips:
        scan = scans[e]
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


def _write(files: dict[str, str]) -> None:
    GRAPH_FULL_DIR.mkdir(exist_ok=True)
    for stale in GRAPH_FULL_DIR.glob("lift_*.py"):
        if stale.name not in files:
            stale.unlink()
    for name, src in files.items():
        (GRAPH_FULL_DIR / name).write_text(src)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true",
                   help="verify the committed manifest (and any emitted "
                        "modules) match a fresh computation; non-zero on drift")
    g.add_argument("--write-manifest", action="store_true",
                   help="recompute liftable_census/graph_functions/graph_eips "
                        "from the image and rewrite the manifest (keeps the "
                        "human-curated exclusion lists)")
    args = ap.parse_args(argv)

    if not EXE.exists():
        raise SystemExit("assets/KE.EXE not present")
    manifest = _load_manifest()
    rt = create_game_runtime(str(EXE), install_replacements=False)
    scans, liftable, linkable, graph_eips = _plan(rt, manifest)
    graph_hex = [f"0x{e:X}" for e in graph_eips]

    if args.write_manifest:
        manifest["liftable_census"] = len(liftable)
        manifest["graph_functions"] = len(graph_eips)
        manifest["graph_eips"] = graph_hex
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"manifest: {len(liftable)} liftable, {len(graph_eips)} graph "
              f"functions ({len(OVERRIDE_EIPS)} authored + "
              f"{len(_excluded(manifest)) - len(OVERRIDE_EIPS)} converged "
              f"excluded) -> {MANIFEST_PATH.name}")
        return 0

    if args.check:
        drift = []
        if manifest.get("liftable_census") != len(liftable):
            drift.append(f"liftable_census {manifest.get('liftable_census')} "
                         f"!= {len(liftable)}")
        if manifest.get("graph_eips") != graph_hex:
            stored = set(manifest.get("graph_eips") or [])
            fresh = set(graph_hex)
            drift.append(f"graph_eips differ (+{len(fresh - stored)} / "
                         f"-{len(stored - fresh)} vs manifest)")
        emitted = {p.name for p in GRAPH_FULL_DIR.glob("lift_*.py")}
        if emitted:  # only when the graph has actually been built on this machine
            fresh = _emit(rt, scans, graph_eips, linkable)
            if emitted != set(fresh):
                drift.append(f"module set differs (+{len(set(fresh) - emitted)} "
                             f"/ -{len(emitted - set(fresh))})")
            for name, src in fresh.items():
                path = GRAPH_FULL_DIR / name
                if not path.is_file() or path.read_text() != src:
                    drift.append(name)
        if drift:
            print("DRIFT: " + "; ".join(map(str, drift[:8]))
                  + (f" (+{len(drift) - 8} more)" if len(drift) > 8 else ""))
            return 1
        built = f", {len(emitted)} modules match" if emitted else " (not built)"
        print(f"OK: manifest matches image -- {len(graph_eips)} graph "
              f"functions{built}")
        return 0

    files = _emit(rt, scans, graph_eips, linkable)
    _write(files)
    print(f"wrote {len(files)} modules -> {GRAPH_FULL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
