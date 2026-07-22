"""The generated (lifted-vmless) hot-set graph as a plan-selected implementation.

Locks task #12: the ``generated-hot-graph`` catalog entry is selectable through
the execution plan, binds all its lifted seams through the same
bind_execution_plan path as the authored overrides, and stays disjoint from
them.  Byte-exactness of the lifted bodies is proven separately by the
differential PM verifier over the ball-heavy snapshot (not reproduced here --
that needs the snapshot asset); this guards the catalog/plan/bind wiring.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"


def test_graph_modules_are_committed_and_named():
    from kegg.overrides import GRAPH_HOT_DIR, GRAPH_HOT_EIPS
    present = {int(p.stem[len("lift_"):], 16) for p in GRAPH_HOT_DIR.glob("lift_*.py")}
    assert present == set(GRAPH_HOT_EIPS), (
        "committed kegg/graph_hot modules must match GRAPH_HOT_EIPS exactly")


def test_graph_is_disjoint_from_authored_overrides():
    from kegg.overrides import GRAPH_HOT_EIPS, OVERRIDE_EIPS
    assert not (set(GRAPH_HOT_EIPS) & set(OVERRIDE_EIPS)), (
        "the generated graph must not target authored-override EIPs")


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_plan_selects_and_binds_the_generated_graph():
    from dos_re.player import GameFrontend
    from kegg.identity import function_id, image_identity
    from kegg.overrides import (GENERATED_GRAPH_ID, GRAPH_HOT_EIPS,
                                authored_plan)
    from kegg.runtime import create_game_runtime

    image = image_identity(str(EXE))

    # default plan: authored only, no generated graph
    plain = authored_plan(image)
    assert GENERATED_GRAPH_ID not in {b.implementation_id for b in plain.bindings}

    # generated_graph=True: the graph is selected, covering all 10 targets
    plan = authored_plan(image, generated_graph=True)
    graph_targets = {b.target for b in plan.bindings
                     if b.implementation_id == GENERATED_GRAPH_ID}
    assert graph_targets == {function_id(image, e) for e in GRAPH_HOT_EIPS}

    # binding installs every lifted seam on the interpreted-cpu carrier
    rt = create_game_runtime(str(EXE), install_replacements=False)
    GameFrontend(ROOT).bind_execution_plan(rt, plan)
    for eip in GRAPH_HOT_EIPS:
        assert rt.cpu.replacement_hooks.get(eip) is not None, hex(eip)
        assert rt.cpu.hook_names[eip] == f"lift_{eip:x}"
