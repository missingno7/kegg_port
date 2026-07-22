"""The recovered GIF87a LZW decoder (0x121DF8) — pure decode + override chain.

`test_decode_gif_pure` drives the pure `kegg.recovered.gif.decode_gif` on a
hand-built minimal GIF (no KE.EXE) and checks the decoded pixels, descriptor,
and 6-bit palette.

`test_gif_override_chain_verifies` places the same GIF in a real KE runtime,
binds the authored override, and proves it byte-exact against the interpreted
ASM at 0x121DF8 with the focused PMHookVerifier (whole-machine diff) — the same
rigor as test_override_slice, but for the asset unpacker.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
GIF_EIP = 0x121DF8


def _lzw_pack(codes, width=9):
    """Pack LZW codes LSB-first (GIF order). A tiny image never grows past the
    initial 9-bit width, so a fixed width is faithful here."""
    out = bytearray()
    buf = cnt = 0
    for c in codes:
        buf |= c << cnt
        cnt += width
        while cnt >= 8:
            out.append(buf & 0xFF)
            buf >>= 8
            cnt -= 8
    if cnt:
        out.append(buf & 0xFF)
    return bytes(out)


def _make_gif(pixels, width, height):
    """A minimal 256-colour GIF87a KE's decoder accepts: full 256-entry GCT,
    one image, LZW = clear + literal pixels + EOI."""
    gct = bytes(((i * 3) & 0xFF, (i * 5) & 0xFF, (i * 7) & 0xFF)[k]
                for i in range(256) for k in range(3))
    clear, eoi = 256, 257
    lzw = _lzw_pack([clear, *pixels, eoi], width=9)
    sub = bytes([len(lzw)]) + lzw + b"\x00"          # one sub-block + terminator
    return (b"GIF87a"
            + bytes([width & 0xFF, width >> 8, height & 0xFF, height >> 8,
                     0xF7, 0, 0])                     # screen desc, packed=GCT/256
            + gct
            + b"\x2C" + bytes([0, 0, 0, 0,            # image sep + left/top
                               width & 0xFF, width >> 8, height & 0xFF, height >> 8,
                               0x00])                 # image packed (no LCT/interlace)
            + bytes([8])                              # LZW min code size
            + sub + b"\x3B")


def test_decode_gif_pure():
    from kegg.recovered.gif import decode_gif
    pixels = [10, 20, 30, 40, 50, 60]
    gif = _make_gif(pixels, width=6, height=1)

    # The decoder writes fixed globals up at 0x148314.. and 0x14E2BC, so the
    # buffer must span them; keep the buffers below that band.
    SRC, DST, DESC, SCR = 0x1000, 0x8000, 0x9000, 0x10000
    data = bytearray(0x150000)
    data[SRC:SRC + len(gif)] = gif

    status, _ecx, _al = decode_gif(data, 0, SRC, DST, DESC, SCR)
    assert status == 0
    # decoded pixels land at dst
    assert list(data[DST:DST + len(pixels)]) == pixels
    # descriptor: [dst, dst_end_even, width, height, 3, 256]
    def r32(a):
        return int.from_bytes(data[a:a + 4], "little")
    n = len(pixels)
    assert r32(DESC) == DST
    assert r32(DESC + 4) == DST + (n & ~1)
    assert r32(DESC + 8) == 6            # width
    assert r32(DESC + 0xC) == 1          # height
    assert r32(DESC + 0x10) == 3
    assert r32(DESC + 0x14) == 256
    # palette: 768 GCT bytes, 8-bit -> 6-bit, right after the (even) pixels
    pal = DST + (n & ~1)
    assert data[pal] == (0 >> 2)
    assert data[pal + 3] == ((1 * 3) >> 2)   # GCT[1].r = 3 -> 0


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_gif_override_chain_verifies():
    from dos_re.player import GameFrontend
    from dos_re.pm_verification import (PMHookVerifierConfig,
                                        PMHookVerifyDivergence,
                                        install_pm_hook_verifier)
    from kegg.identity import function_id, image_identity
    from kegg.overrides import authored_plan
    from kegg.runtime import create_game_runtime

    rt = create_game_runtime(str(EXE), install_replacements=False)
    cpu, mem = rt.cpu, rt.cpu.mem
    assert GIF_EIP not in cpu.replacement_hooks

    image = image_identity(str(EXE))
    plan = authored_plan(image)
    by_id = {b.implementation_id: b for b in plan.bindings}
    assert "gif_decode_121df8" in by_id
    assert by_id["gif_decode_121df8"].target == function_id(image, GIF_EIP)

    GameFrontend(ROOT).bind_execution_plan(rt, plan)
    assert cpu.replacement_hooks.get(GIF_EIP) is not None
    assert cpu.hook_names.get(GIF_EIP) == "gif_decode_121df8"

    # place a minimal GIF + call frame in free high RAM
    pixels = [7, 11, 13, 17, 19, 23, 29, 31]
    gif = _make_gif(pixels, width=8, height=1)
    SRC, DST, DESC, SCR = 0x600000, 0x620000, 0x630000, 0x640000
    SP, RET = 0x660000, 0x660100
    assert len(mem.data) > 0x661000
    mem.data[SRC:SRC + len(gif)] = gif
    mem.w32(SP, RET)
    mem.w32(SP + 4, SRC)
    mem.w32(SP + 8, DST)
    mem.w32(SP + 0xC, DESC)
    mem.w32(SP + 0x10, SCR)
    cpu.r[4] = SP
    cpu.eip = GIF_EIP

    install_pm_hook_verifier(rt, PMHookVerifierConfig(samples=None))
    try:
        cpu.step()                       # the seam fires -> verified byte-exact
    except PMHookVerifyDivergence as exc:  # pragma: no cover
        raise AssertionError(f"gif override diverged from the oracle: {exc}")

    assert cpu.eip == RET
    assert cpu.r[0] == 0                  # status word (success)
    assert list(mem.data[DST:DST + len(pixels)]) == pixels
