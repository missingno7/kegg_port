"""The recovered VGA palette fade (0x123A48) — pure stream + override chain.

KE runs this once per frame through every title/menu fade: it programs the DAC
write index, then streams `entries*3` components, each `src[i] - fade` clamped
to 0..0x3F.  It was the largest interpreted cost left in the image-display path
after the GIF decoder was recovered.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
FADE_EIP = 0x123A48


def test_fade_palette_stream_clamps_both_ends():
    from kegg.recovered.present import fade_palette_stream

    src = bytes([0, 1, 5, 0x20, 0x3F, 0x80, 0xFF])
    # no fade: values above 0x3F clamp down, nothing clamps low
    out, low, _ = fade_palette_stream(src, 0, len(src), 0, 0)
    assert list(out) == [0, 1, 5, 0x20, 0x3F, 0x3F, 0x3F]
    assert low is False

    # fade of 8: small values clamp to 0, the rest shift down
    out, _, _ = fade_palette_stream(src, 0, len(src), 8, 0)
    assert list(out) == [0, 0, 0, 0x18, 0x37, 0x3F, 0x3F]

    # a fade past everything blacks the whole ramp out
    out, low, _ = fade_palette_stream(src, 0, len(src), 0xFF, 0)
    assert set(out) == {0}
    # ...and `low` reports the LAST component's branch: 0xFF-0xFF lands on
    # exactly 0 (non-negative), while stopping one short ends on 0x80-0xFF < 0.
    assert low is False
    _, low_neg, _ = fade_palette_stream(src, 0, len(src) - 1, 0xFF, 0)
    assert low_neg is True


def test_fade_palette_stream_respects_offset_and_count():
    from kegg.recovered.present import fade_palette_stream

    src = bytes(range(32))
    out, _, _ = fade_palette_stream(src, 8, 4, 2, 0)
    assert list(out) == [6, 7, 8, 9]          # src[8..11] - 2


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_palette_fade_override_chain_verifies():
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
    assert "palette_fade_123a48" in by_id
    assert by_id["palette_fade_123a48"].target == function_id(image, FADE_EIP)

    GameFrontend(ROOT).bind_execution_plan(rt, plan)
    assert cpu.hook_names.get(FADE_EIP) == "palette_fade_123a48"

    # a 16-entry ramp that exercises both clamps, faded by 4
    SRC, SP, RET = 0x600000, 0x660000, 0x660100
    assert len(mem.data) > 0x661000
    entries = 16
    ramp = bytes(((i * 9) & 0xFF) for i in range(entries * 3))
    mem.data[SRC:SRC + len(ramp)] = ramp
    mem.w32(SP, RET)
    mem.w32(SP + 4, SRC)          # src
    mem.w32(SP + 8, 0)            # DAC start index
    mem.w32(SP + 0xC, entries)    # entries (x3 components)
    mem.w32(SP + 0x10, 4)         # fade
    cpu.r[4] = SP
    cpu.eip = FADE_EIP

    install_pm_hook_verifier(rt, PMHookVerifierConfig(samples=None))
    try:
        cpu.step()                # byte-exact vs the interpreted ASM, incl. DAC state
    except PMHookVerifyDivergence as exc:  # pragma: no cover
        raise AssertionError(f"palette fade diverged from the oracle: {exc}")

    assert cpu.eip == RET
    # the DAC received the faded, clamped ramp
    dac = rt.dos.dac
    assert dac[0] == max(0, ramp[0] - 4)
    assert all(v <= 0x3F for v in dac[:entries * 3])
