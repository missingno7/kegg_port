"""kegg.recovered.rle_blit — the Mode X sprite RLE decoder.

Two tiers: a self-contained unit test of the copy/skip/clip logic (always
runs), and a ground-truth test that decodes a real in-game sprite and checks
the planes byte-for-byte against the interpreted blitter (skips without the
gameplay snapshot).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

from kegg.recovered.rle_blit import decode_row


def test_copy_skip_clip_semantics():
    plane = bytearray(64)
    # src: [nseg=3][copy 4: 'ABCD'][skip 2][copy 3: 'EFG']
    src = bytes([3, 4]) + b"ABCD" + bytes([0xFE]) + bytes([3]) + b"EFG"
    esi, dst, _ = decode_row(plane, src, 0, 0, 0, clip_w=1000)
    assert bytes(plane[:9]) == b"ABCD\x00\x00EFG"   # 4 copied, 2 skipped, 3 copied
    assert dst == 9
    assert esi == len(src)


def test_right_clip_truncates_and_consumes_source():
    plane = bytearray(64)
    # clip at 3: a single 8-byte copy is truncated to 3 written, all 8 consumed
    src = bytes([1, 8]) + b"01234567"
    esi, dst, _ = decode_row(plane, src, 0, 0, 0, clip_w=3)
    assert bytes(plane[:8]) == b"012\x00\x00\x00\x00\x00"
    assert dst == 3
    assert esi == len(src)          # whole run's source consumed


def test_run_entirely_past_clip_is_dropped():
    plane = bytearray(64)
    # first copy fills to the clip, second run is entirely past it
    src = bytes([2, 4]) + b"WXYZ" + bytes([4]) + b"____"
    esi, dst, _ = decode_row(plane, src, 0, 0, 0, clip_w=4)
    assert bytes(plane[:8]) == b"WXYZ\x00\x00\x00\x00"
    assert esi == len(src)


SNAP = ROOT / "artifacts" / "snapshots" / "snap_126359171"


@pytest.mark.skipif(not SNAP.exists(), reason="gameplay snapshot not present")
def test_matches_interpreted_blitter_in_game():
    from dos_re.pm_snapshot import load_pm_snapshot
    rt = load_pm_snapshot(str(ROOT / "assets" / "KE.EXE"), str(SNAP))
    cpu = rt.cpu
    orig = cpu.step

    def brk():
        if cpu.eip == 0x1222D1:
            raise StopIteration
        orig()
    cpu.step = brk
    try:
        cpu.run(8_000_000)
    except StopIteration:
        pass
    cpu.step = orig

    G = lambda a: int.from_bytes(cpu.mem.data[a:a + 4], "little")
    ret = G(cpu.r[4])
    tgt = cpu.r[4] + 4
    init = [bytearray(p) for p in cpu.mem.vga.planes]
    passes = []
    n = 0
    while not (cpu.eip == ret and cpu.r[4] >= tgt):
        if cpu.eip == 0x122539 and (not passes or passes[-1][1] != cpu.r[7]):
            passes.append((cpu.r[6], cpu.r[7], cpu.r[2], cpu.mem.vga.map_mask,
                           G(0x148388)))
        cpu.step(); n += 1
        assert n < 1_000_000
    want = [bytes(p) for p in cpu.mem.vga.planes]
    src = bytes(cpu.mem.data)

    got = init
    for esi, edi, edx, mask, clip in passes:
        base = (edx - 0xA0000) & 0xFFFF
        decode_row(got[mask.bit_length() - 1], src, esi, base, base, clip)
    assert [bytes(p) for p in got] == want


@pytest.mark.skipif(not SNAP.exists(), reason="gameplay snapshot not present")
def test_recovered_override_verifies_against_oracle():
    """The recovered blitter override (unclipped native + clipped fallback) must
    reproduce the original routine byte-exact — every call diffed against the
    interpreted ASM by the strict differential verifier.  The plan binds the
    whole override catalog; the verifier proves each call as it fires."""
    from dos_re.pm_snapshot import load_pm_snapshot
    from dos_re.pm_verification import install_pm_hook_verifier
    from kegg.overrides import bind_overrides
    exe = str(ROOT / "assets" / "KE.EXE")
    rt = load_pm_snapshot(exe, str(SNAP))
    bind_overrides(rt, exe)                 # plan-owned install of every override
    v = install_pm_hook_verifier(rt)
    v.config.samples = None                # verify EVERY call, no retirement
    rt.cpu.run(4_000_000)
    assert v.total_verified >= 100         # the run really exercised it
