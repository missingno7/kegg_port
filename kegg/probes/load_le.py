"""Probe: load KE.EXE's LE image, apply fixups, disassemble the entry point.

Proves the loader (kegg.le.loader) produces a coherent flat image: the bytes at
the LE entry point must decode as sane 386 code, and a spot-checked fixup must
point where the record says.  Throwaway diagnostic (probes/ are not gameplay).

    python -m kegg.probes.load_le            # from repo root, needs assets/KE.EXE
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dos_re"))

from dos_re.le import load_le  # noqa: E402


def main() -> int:
    exe = ROOT / "assets" / "KE.EXE"
    if not exe.exists():
        print("assets/KE.EXE missing — nothing to probe")
        return 0
    img = load_le(exe)
    print(f"loaded {len(img.objects)} objects, {img.fixup_count} fixups applied, "
          f"image {len(img.mem)} bytes @ flat 0x{img.mem_base:x}")
    names = {0: "byte", 2: "sel16", 3: "ptr16:16", 5: "off16", 6: "ptr16:32", 7: "off32", 8: "selfrel32"}
    print("  fixup census: " + ", ".join(
        f"{names.get(k, hex(k))}={v}" for k, v in sorted(img.fixup_census.items())))
    for obj in img.objects:
        print(f"  obj{obj.index} base=0x{obj.base:06x} vsize=0x{obj.virtual_size:x} "
              f"{'32' if obj.is_32bit else '16'}bit "
              f"{'X' if obj.executable else '-'}{'W' if obj.writable else '-'} "
              f"pages {obj.first_page}..{obj.first_page + obj.page_count - 1}")
    print(f"entry: obj{img.entry_object}+0x{img.entry_offset:x} = flat 0x{img.entry_linear:x}")
    print(f"stack: obj{img.stack_object}+0x{img.stack_offset:x} = flat 0x{img.stack_linear:x}")

    # spot-check fixup record 1: page1 off 0x0f13 must hold flat 0x48428 (obj3+0x8428)
    probe_at = img.objects[0].base + 0x0F13
    val = struct.unpack_from("<I", img.mem, probe_at - img.mem_base)[0]
    print(f"fixup spot-check @0x{probe_at:x}: 0x{val:x} "
          f"({'OK' if val == 0x48428 else 'MISMATCH expected 0x48428'})")

    try:
        import capstone
    except ImportError:
        print("capstone not installed — skipping disassembly")
        return 0
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    off = img.entry_linear - img.mem_base
    print(f"\n--- disassembly at entry 0x{img.entry_linear:x} ---")
    n = 0
    for ins in md.disasm(bytes(img.mem[off:off + 64]), img.entry_linear):
        print(f"  {ins.address:08x}: {ins.mnemonic:<7}{ins.op_str}")
        n += 1
        if n >= 16:
            break
    if n == 0:
        print("  (no instructions decoded — loader or entry wrong)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
