"""The recovered linear -> Mode X planar upload (0x122F30).

This is what puts a decoded image on screen: it de-interleaves `count` linear
bytes into the four VGA planes at an aperture address, plane `p` taking source
bytes `p, p+4, p+8, ...`.  It runs right after every image load.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
PLANAR_EIP = 0x122F30
APERTURE = 0xA0000


def test_deinterleave_plane_takes_every_fourth_byte():
    from kegg.recovered.present import deinterleave_plane

    src = bytes(range(32))
    assert list(deinterleave_plane(src, 0, 4, 0)) == [0, 4, 8, 12]
    assert list(deinterleave_plane(src, 0, 4, 1)) == [1, 5, 9, 13]
    assert list(deinterleave_plane(src, 0, 4, 3)) == [3, 7, 11, 15]
    # honours the source offset
    assert list(deinterleave_plane(src, 8, 3, 2)) == [10, 14, 18]


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_planar_upload_override_chain_verifies():
    from dos_re.player import GameFrontend
    from dos_re.pm_verification import (PMHookVerifierConfig,
                                        PMHookVerifyDivergence,
                                        install_pm_hook_verifier)
    from kegg.identity import function_id, image_identity
    from kegg.overrides import authored_plan
    from kegg.runtime import create_game_runtime

    rt = create_game_runtime(str(EXE), install_replacements=False)
    cpu, mem = rt.cpu, rt.cpu.mem
    image = image_identity(str(EXE))
    plan = authored_plan(image)
    by_id = {b.implementation_id: b for b in plan.bindings}
    assert "planar_upload_122f30" in by_id
    assert by_id["planar_upload_122f30"].target == function_id(image, PLANAR_EIP)

    GameFrontend(ROOT).bind_execution_plan(rt, plan)
    assert cpu.hook_names.get(PLANAR_EIP) == "planar_upload_122f30"

    SRC, SP, RET = 0x600000, 0x660000, 0x660100
    assert len(mem.data) > 0x661000
    count = 256                       # 64 bytes per plane
    n = count // 4
    pixels = bytes(((i * 7 + 3) & 0xFF) for i in range(count))
    mem.data[SRC:SRC + count] = pixels
    mem.w32(SP, RET)
    mem.w32(SP + 4, SRC)              # src (the routine increments this slot)
    mem.w32(SP + 8, APERTURE)         # dst — the VGA aperture
    mem.w32(SP + 0xC, count)
    cpu.r[4] = SP
    cpu.eip = PLANAR_EIP

    install_pm_hook_verifier(rt, PMHookVerifierConfig(samples=None))
    try:
        cpu.step()                    # byte-exact vs the ASM, incl. planes + ports
    except PMHookVerifyDivergence as exc:  # pragma: no cover
        raise AssertionError(f"planar upload diverged from the oracle: {exc}")

    assert cpu.eip == RET
    # The pixel destination is DEVICE state whose routing depends on the VGA
    # mode (planes only once unchained Mode X is programmed), so the byte-exact
    # whole-machine diff above -- not a hand-written expectation about where the
    # bytes land -- is this routine's contract. What we can assert directly is
    # the routine's side effect on the caller: it advances the src argument slot
    # by one per plane, and leaves the map mask restored.
    assert mem.r32(SP + 4) == SRC + 4
    assert mem.r8(0x14E385) == 0x0F          # map-mask shadow restored
    assert n == 64
