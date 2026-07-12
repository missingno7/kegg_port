"""Probe: run KE to the title screen and render the framebuffer to PNG.

Renders through the planar model when the game has unchained (Mode X);
otherwise linear mode 13h.  Writes artifacts/title_frame.png.

    python -m kegg.probes.render_title [steps]
"""
from __future__ import annotations

import sys
import zlib
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "dos_re")]

from kegg.runtime import create_game_runtime  # noqa: E402


def write_png(path: Path, pixels: bytes, dac: bytes, width: int, height: int) -> None:
    raws = b""
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            c = pixels[y * width + x]
            row += bytes((dac[c * 3] << 2, dac[c * 3 + 1] << 2, dac[c * 3 + 2] << 2))
        raws += row

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raws))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def main(argv) -> int:
    exe = ROOT / "assets" / "KE.EXE"
    if not exe.exists():
        print("assets/KE.EXE missing")
        return 0
    steps = int(argv[0]) if argv else 20_000_000
    rt = create_game_runtime(exe)
    rt.dos.key_queue.append(0x20)
    try:
        rt.cpu.run(steps)
    except Exception as e:  # noqa: BLE001
        print(f"stopped: {type(e).__name__}: {e} at eip=0x{rt.cpu.eip:X}")
    print(f"instr={rt.cpu.instruction_count} mode={getattr(rt.dos, 'video_mode', None):#x} "
          f"chain4={rt.dos.vga.chain4} display_start=0x{rt.dos.vga.display_start:x}")
    out = ROOT / "artifacts" / "title_frame.png"
    out.parent.mkdir(exist_ok=True)
    if rt.dos.vga.chain4:
        pixels = bytes(rt.mem.data[0xA0000:0xA0000 + 64000])
        write_png(out, pixels, rt.dos.dac, 320, 200)
    else:
        pixels = rt.dos.vga.render_mode_x(320, 240)
        write_png(out, pixels, rt.dos.dac, 320, 240)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
