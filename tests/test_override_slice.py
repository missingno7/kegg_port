"""Stage 0 proof: one recovered routine migrated to the dos_re 3.0 override chain.

Exercises the whole 3.0 path for `rects_overlap` (0x11B5DF):
identity -> ImplementationCatalog -> coverage -> ExecutionConfiguration ->
plan_execution -> bind_execution_plan -> the adapter installs the CPU seam ->
the focused oracle verifier proves it byte-exact against the interpreted ASM.

No demo/snapshot needed: the routine is a pure leaf, so a synthetic call frame
(two rects on a scratch stack) drives one verified invocation.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
RECTS_OVERLAP_EIP = 0x11B5DF


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_rects_overlap_override_chain_binds_and_verifies():
    from dos_re.player import GameFrontend
    from dos_re.pm_verification import (PMHookVerifierConfig,
                                        PMHookVerifyDivergence,
                                        install_pm_hook_verifier)
    from kegg.identity import function_id, image_identity
    from kegg.overrides import authored_plan
    from kegg.runtime import create_game_runtime

    # 1. boot the interpreted oracle WITHOUT eager hooks — the plan owns install
    rt = create_game_runtime(str(EXE), install_replacements=False)
    assert RECTS_OVERLAP_EIP not in rt.cpu.replacement_hooks

    # 2. the 3.0 plan selects the authored overrides for this image; rects_overlap
    #    is one of the full recovered catalog, bound to its stable target id.
    image = image_identity(str(EXE))
    plan = authored_plan(image)
    target = function_id(image, RECTS_OVERLAP_EIP)
    by_id = {b.implementation_id: b for b in plan.bindings}
    assert "rects_overlap" in by_id
    assert by_id["rects_overlap"].target == target

    # 3. binding the plan runs the backend adapters -> installs every CPU seam
    GameFrontend(ROOT).bind_execution_plan(rt, plan)
    assert rt.cpu.replacement_hooks.get(RECTS_OVERLAP_EIP) is not None
    assert rt.cpu.hook_names.get(RECTS_OVERLAP_EIP) == "rects_overlap"

    # 4. drive one synthetic call and prove it byte-exact vs the interpreted ASM
    cpu, mem = rt.cpu, rt.cpu.mem
    assert len(mem.data) > 0x520000
    RA, RB, SP, RET = 0x500000, 0x500010, 0x510000, 0x510100

    def rect(base, l, t, r, b):
        for off, v in ((0, l), (4, t), (8, r), (0xC, b)):
            mem.w32(base + off, v & 0xFFFFFFFF)

    rect(RA, 10, 10, 20, 20)
    rect(RB, 15, 15, 25, 25)          # overlaps RA -> expect -1
    mem.w32(SP, RET)                  # return address (cdecl)
    mem.w32(SP + 4, RA)              # arg0
    mem.w32(SP + 8, RB)             # arg1
    cpu.r[4] = SP                     # esp
    cpu.eip = RECTS_OVERLAP_EIP

    # the focused verifier clones, runs the override + the original ASM to the
    # same continuation, and diffs full machine state; a mismatch raises.
    install_pm_hook_verifier(rt, PMHookVerifierConfig(samples=None))
    try:
        cpu.step()                    # the seam fires -> verified this call
    except PMHookVerifyDivergence as exc:  # pragma: no cover - would fail the test
        raise AssertionError(f"override diverged from the oracle: {exc}")

    assert cpu.eip == RET             # returned through the recovered epilogue
    assert cpu.r[0] == 0xFFFFFFFF     # AABB overlap result (-1)
