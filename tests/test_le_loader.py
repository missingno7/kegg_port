"""LE loader bring-up tests.  Skip when assets/ is absent (CI has no game files)."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXE = ROOT / "assets" / "KE.EXE"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")

from dos_re.le import load_le  # noqa: E402


def test_objects_and_entry():
    img = load_le(EXE)
    assert [o.index for o in img.objects] == [1, 2, 3]
    assert img.objects[0].base == 0x10000 and img.objects[0].is_32bit
    assert img.objects[2].writable and img.objects[2].is_32bit
    assert img.entry_linear == 0x242D8
    assert img.stack_linear == 0x4F610


def test_fixups_applied():
    img = load_le(EXE)
    # 6292 32-bit-offset + 4 selector fixups, verified against the raw records.
    assert img.fixup_count == 6296
    assert img.fixup_census.get(0x07) == 6292
    # Record 1: obj1+0x0f13 holds a flat pointer to obj3+0x8428 = 0x48428.
    val = struct.unpack_from("<I", img.mem, 0x10F13 - img.mem_base)[0]
    assert val == 0x48428


def test_entry_is_startup_code():
    img = load_le(EXE)
    capstone = pytest.importorskip("capstone")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    off = img.entry_linear - img.mem_base
    ins = next(md.disasm(bytes(img.mem[off:off + 8]), img.entry_linear))
    assert ins.mnemonic == "jmp"  # entry jumps over the embedded version string
