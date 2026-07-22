"""The generated full-game graph as a second plan-selected implementation.

Locks task #17: the ``generated-full-graph`` catalog entry (the whole-game
lifted-vmless graph) is manifest-backed, disjoint from the authored overrides,
a superset of the hot-set graph, mutually exclusive with it in selection, and
binds all its lifted seams through the same bind path as the authored overrides.

Reproducibility of the emitted bodies is proven separately by
scripts/build_full_graph.py --check (manifest vs image) and, at runtime, by the
differential PM verifier boot->menu (needs the built graph + KE.EXE); the pure
census/wiring facts here need neither.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"


# --- pure manifest/wiring facts (no image needed) ----------------------------

def test_full_graph_is_manifest_backed_and_nonempty():
    from kegg.overrides import GRAPH_FULL_EIPS
    assert len(GRAPH_FULL_EIPS) > 400, (
        "GRAPH_FULL_EIPS should load the whole-game census from the manifest; "
        "run scripts/build_full_graph.py --write-manifest if it is empty")


def test_full_graph_is_disjoint_from_authored_overrides():
    from kegg.overrides import GRAPH_FULL_EIPS, OVERRIDE_EIPS
    assert not (set(GRAPH_FULL_EIPS) & set(OVERRIDE_EIPS)), (
        "authored overrides win at their seams -- the full graph must exclude "
        "every authored EIP so calls into them fall through to the adapter")


def test_hot_graph_is_a_subset_of_the_full_graph():
    from kegg.overrides import GRAPH_FULL_EIPS, GRAPH_HOT_EIPS
    assert set(GRAPH_HOT_EIPS) <= set(GRAPH_FULL_EIPS), (
        "the full graph is a superset of the hot-set graph")


def test_full_graph_supersedes_hot_in_selection():
    """The two generated graphs share the hot EIPs, so at most one is ever
    selected; full_graph wins over generated_graph."""
    from kegg.overrides import (GENERATED_FULL_GRAPH_ID, GENERATED_GRAPH_ID,
                                _generated_selection, selected_ids)
    impl_id, _ = _generated_selection(generated_graph=True, full_graph=True)
    assert impl_id == GENERATED_FULL_GRAPH_ID
    ids = selected_ids(generated_graph=True, full_graph=True)
    assert GENERATED_FULL_GRAPH_ID in ids and GENERATED_GRAPH_ID not in ids


def test_manifest_exclusions_are_kept_out_of_the_graph():
    """The convergence inventory (waits + stack-switch/computed-transfer) must
    not appear as graph targets."""
    import json
    from kegg.overrides import GRAPH_FULL_EIPS, MANIFEST_PATH
    data = json.loads(MANIFEST_PATH.read_text())
    excluded = {int(x, 16) for x in
                data["excluded_waits"] + data["excluded_crashes"]}
    assert not (excluded & set(GRAPH_FULL_EIPS))


# --- image-backed facts ------------------------------------------------------

@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_manifest_matches_the_image():
    """build_full_graph.py --check: the committed manifest (census size +
    graph_eips) still matches a fresh computation from KE.EXE."""
    import scripts.build_full_graph as bfg
    assert bfg.main(["--check"]) == 0


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_full_graph_entry_fails_loud_when_not_built():
    """A selected full graph whose directory is empty is a hard error, not a
    silent no-op (the modules are gitignored / built on demand)."""
    from kegg.overrides import (GENERATED_FULL_GRAPH_ID,
                                _selected_generated_entry, image_identity)
    entry = _selected_generated_entry(image_identity(str(EXE)),
                                      GENERATED_FULL_GRAPH_ID)
    (adapter,) = entry.adapters

    class _Empty:
        class cpu:
            replacement_hooks: dict = {}
            hook_names: dict = {}
    import tempfile
    from kegg import overrides
    saved = overrides.GRAPH_FULL_DIR
    try:
        overrides.GRAPH_FULL_DIR = Path(tempfile.mkdtemp())  # empty dir
        entry2 = _selected_generated_entry(image_identity(str(EXE)),
                                           GENERATED_FULL_GRAPH_ID)
        with pytest.raises(FileNotFoundError):
            entry2.adapters[0].activate(_Empty(), entry2.descriptor.targets)
    finally:
        overrides.GRAPH_FULL_DIR = saved


@pytest.mark.skipif(
    not EXE.exists() or not any(
        (ROOT / "kegg" / "graph_full").glob("lift_*.py")),
    reason="full graph not built (scripts/build_full_graph.py)")
def test_plan_selects_and_binds_the_full_graph():
    from dos_re.player import GameFrontend
    from kegg.identity import function_id, image_identity
    from kegg.overrides import (GENERATED_FULL_GRAPH_ID, GRAPH_FULL_EIPS,
                                authored_plan)
    from kegg.runtime import create_game_runtime

    image = image_identity(str(EXE))
    plan = authored_plan(image, full_graph=True)
    graph_targets = {b.target for b in plan.bindings
                     if b.implementation_id == GENERATED_FULL_GRAPH_ID}
    assert graph_targets == {function_id(image, e) for e in GRAPH_FULL_EIPS}

    rt = create_game_runtime(str(EXE), install_replacements=False)
    GameFrontend(ROOT).bind_execution_plan(rt, plan)
    for eip in GRAPH_FULL_EIPS:
        assert rt.cpu.replacement_hooks.get(eip) is not None, hex(eip)
        assert rt.cpu.hook_names[eip] == f"lift_{eip:x}"
