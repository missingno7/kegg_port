"""atlas.py -- the Krypton Egg Execution Atlas workflow over recorded replays.

Turns ordinary gameplay recordings into structured, persistent evidence:

    observe   <replay...>   oracle pass: replay 0..end once, record function
                            visits + observed transfers into the artifact
    validate  <replay...>   full-range oracle validation (makes it trusted)
    ingest    <replay...>   import the evidence into the Execution Atlas
    coverage  <function>    per-replay first-entry/last-exit/count + best replay
    verify-fn <function> <replay>
                            interval verification of just that function's
                            observed range (cached-boundary restore; run twice
                            to see cache reuse)
    report                  corpus overview: replays, functions, overlap

The Atlas lives in kegg/atlas/ (commit-friendly JSON evidence).  Function
identities come from kegg.identity; the observed function set is the lift
census (direct near-call targets) plus the authored override entries.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dos_re.atlas import ExecutionAtlas                      # noqa: E402
from dos_re.replay import ReplayArtifact, ReplayExecutionIdentity  # noqa: E402
from dos_re.pm_replay_evidence import (                       # noqa: E402
    observe_pm_replay, validate_pm_replay, PMReplayDriver)
from dos_re.lift.decode32 import decode32                     # noqa: E402

from kegg.identity import PROGRAM, function_id, image_identity  # noqa: E402
from kegg.overrides import OVERRIDE_EIPS                       # noqa: E402
from kegg.runtime import create_game_runtime                   # noqa: E402

EXE = ROOT / "assets" / "KE.EXE"
ATLAS_DIR = ROOT / "kegg" / "atlas"


def _bare_runtime():
    """A fresh interpreted runtime shell; the continuation replaces its state."""
    return create_game_runtime(str(EXE), game_root=str(ROOT / "assets"),
                               install_replacements=False)


def _function_map() -> dict[int, str]:
    """Flat EIP -> stable FunctionIdentity for every known function entry.

    The static lift census (direct near-call targets over the code object)
    plus the authored override entries.  Indirect-only functions join as
    runtime discovery lands.
    """
    rt = _bare_runtime()
    image = image_identity(str(EXE))
    read = rt.mem.data.__getitem__
    entries: set[int] = set(OVERRIDE_EIPS)
    for obj in rt.image.objects:
        if not obj.executable or not obj.is_32bit:
            continue
        ip = obj.base
        end = obj.base + obj.virtual_size
        while ip < end:
            try:
                inst = decode32(read, ip)
            except ValueError:
                ip += 1
                continue
            if inst.kind == "call" and inst.target is not None \
                    and obj.base <= inst.target < end:
                entries.add(inst.target)
            ip += inst.length
    return {eip: function_id(image, eip) for eip in sorted(entries)}


def _profiles(artifact_path: str):
    """(oracle, deterministic-candidate) profiles compatible with the capture.

    Machine identity fields (image/runtime/devices/schemas) are copied from
    the capture profile -- same interpreter runtime, same devices -- with
    distinct ids/roles: the oracle observes and anchors evidence; the
    candidate is a second interpreted replay proving the timeline
    deterministic (the validation `trusted` requires).
    """
    capture = ReplayArtifact.open(artifact_path).capture_profile()

    def derived(profile_id: str, role: str, implementation: str):
        return ReplayExecutionIdentity(
            profile_id=profile_id, role=role, implementation=implementation,
            image=capture.image, runtime=capture.runtime,
            devices=capture.devices,
            continuation_schema=capture.continuation_schema,
            projection_schema=capture.projection_schema,
        )

    oracle = derived("protected-mode-oracle-interpreted-v1", "oracle",
                     f"interpreted-original:{capture.runtime}")
    candidate = derived("protected-mode-candidate-interpreted-v1", "candidate",
                        f"interpreted-original-rerun:{capture.runtime}")
    return oracle, candidate


def _atlas() -> ExecutionAtlas:
    if (ATLAS_DIR / "manifest.json").exists():
        return ExecutionAtlas.open(ATLAS_DIR)
    return ExecutionAtlas.create(ATLAS_DIR, program=PROGRAM)


def cmd_observe(args) -> int:
    fmap = _function_map()
    print(f"observing with {len(fmap)} known function entries")
    for replay in args.replays:
        oracle, _ = _profiles(replay)
        t0 = time.monotonic()
        recorder = observe_pm_replay(replay, oracle, _bare_runtime, fmap,
                                     provenance={"tool": "kegg/scripts/atlas.py",
                                                 "pass": "oracle-observation-v5"})
        visits = recorder.visits.records()
        complete = sum(1 for v in visits if not v.incomplete)
        calls = sum(v.invocation_count for v in visits)
        print(f"  {replay}: {len(visits)} functions visited "
              f"({complete} complete), {calls} invocations, "
              f"{time.monotonic() - t0:.1f}s")
    return 0


def cmd_validate(args) -> int:
    for replay in args.replays:
        oracle, candidate = _profiles(replay)
        t0 = time.monotonic()
        result = validate_pm_replay(replay, oracle, candidate,
                                    _bare_runtime, _bare_runtime)
        artifact = ReplayArtifact.open(replay)
        print(f"  {replay}: equivalent={result.equivalent} "
              f"trusted={artifact.trusted} ({time.monotonic() - t0:.1f}s)")
        if not result.equivalent:
            for line in result.comparison.differences[:6]:
                print(f"    {line}")
            return 1
    return 0


def cmd_ingest(args) -> int:
    atlas = _atlas()
    for replay in args.replays:
        report = atlas.ingest_replay_with_report(replay)
        print(f"  {report.artifact_label}: "
              f"{len(report.visited_function_ids)} functions, "
              f"{report.invocation_count} invocations, "
              f"{len(report.observed_edges)} observed edges "
              f"(+{len(report.new_node_ids)} new nodes, "
              f"+{len(report.new_edges)} new edges)")
    return 0


def cmd_coverage(args) -> int:
    atlas = _atlas()
    node = atlas.resolve(args.function)
    print(f"function: {node.identity}")
    rows = atlas.replay_coverage(node.identity)
    if not rows:
        print("  no replay evidence")
        return 0
    labels = {r["replay_id"]: r["artifact"]["label"]
              for r in atlas._indexes()[1]["replays"]}
    for row in rows:
        span = ("?" if not row.complete else
                f"{row.first_entry.ordinal}..{row.last_exit.ordinal}")
        cached = (None if row.cached_at_or_before_entry is None
                  else row.cached_at_or_before_entry.ordinal)
        print(f"  {labels.get(row.replay_id, row.replay_id)}: "
              f"frames {span}, {row.invocation_count} calls, "
              f"cached<=entry at {cached}"
              f"{' (incomplete)' if row.incomplete else ''}")
    best = atlas.best_replay(node.identity)
    print(f"  best: {labels.get(best.replay_id, best.replay_id)} "
          f"frames {best.first_entry.ordinal}..{best.last_exit.ordinal}")
    callers = [e.source for e in atlas.callers(node.identity)]
    callees = [e.target for e in atlas.callees(node.identity)]
    print(f"  callers observed: {len(callers)}; callees observed: {len(callees)}")
    for e in atlas.callers(node.identity)[:4]:
        print(f"    <- {e.source.rsplit(':', 1)[-1]} x{e.observation_count}")
    for e in atlas.callees(node.identity)[:4]:
        print(f"    -> {e.target.rsplit(':', 1)[-1]} x{e.observation_count}")
    return 0


def cmd_verify_fn(args) -> int:
    from dos_re.replay import verify_interval
    atlas = _atlas()
    node = atlas.resolve(args.function)
    artifact = ReplayArtifact.open(args.replay)
    first, last = artifact.function_interval(node.identity)
    oracle_p, candidate_p = _profiles(args.replay)
    frame_tick = int(artifact.metadata["frame_tick_addr"])
    print(f"interval for {node.label or node.identity}: "
          f"frames {first.ordinal}..{last.ordinal} "
          f"(of {artifact.metadata['end_point']['ordinal']})")
    oracle = PMReplayDriver(oracle_p, _bare_runtime,
                            frame_tick_addr=frame_tick,
                            timeline_id=artifact.timeline_id)
    candidate = PMReplayDriver(candidate_p, _bare_runtime,
                               frame_tick_addr=frame_tick,
                               timeline_id=artifact.timeline_id)
    restored_from = artifact.nearest_cached(oracle_p, first)
    t0 = time.monotonic()
    result = verify_interval(artifact, oracle, candidate, first, last)
    dt = time.monotonic() - t0
    print(f"  restored from cached frame {restored_from.ordinal}; "
          f"verified {first.ordinal}..{last.ordinal}: "
          f"equivalent={result.equivalent} in {dt:.1f}s")
    if not result.equivalent:
        for line in result.comparison.differences[:6]:
            print(f"    {line}")
        return 1
    return 0


def cmd_report(args) -> int:
    atlas = _atlas()
    _, replays = atlas._indexes()
    per_replay: dict[str, set[str]] = {}
    for row in replays["coverage"]:
        per_replay.setdefault(row["replay_id"], set()).add(row["function_id"])
    labels = {r["replay_id"]: r["artifact"]["label"] for r in replays["replays"]}
    all_fns: set[str] = set()
    print("corpus report:")
    for rid, fns in sorted(per_replay.items(), key=lambda kv: labels.get(kv[0], "")):
        new = fns - all_fns
        print(f"  {labels.get(rid, rid)}: {len(fns)} functions "
              f"({len(new)} unique so far)")
        all_fns |= fns
    print(f"  total distinct functions observed: {len(all_fns)}")
    multi = [
        fn for fn in sorted(all_fns)
        if sum(1 for fns in per_replay.values() if fn in fns) > 1
    ]
    print(f"  observed in more than one replay: {len(multi)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name, fn, replay_args in (
        ("observe", cmd_observe, True), ("validate", cmd_validate, True),
        ("ingest", cmd_ingest, True),
    ):
        p = sub.add_parser(name)
        p.add_argument("replays", nargs="+")
        p.set_defaults(fn=fn)
    p = sub.add_parser("coverage")
    p.add_argument("function")
    p.set_defaults(fn=cmd_coverage)
    p = sub.add_parser("verify-fn")
    p.add_argument("function")
    p.add_argument("replay")
    p.set_defaults(fn=cmd_verify_fn)
    p = sub.add_parser("report")
    p.set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
