"""Probe: run KE to the title screen and render the framebuffer to PNG.

Thin game wrapper over the promoted framework pieces
(`dos_re.dos4gw.render_pm_frame` + `dos_re.frame_verify.write_rgb_png`);
the generic CLI is `python dos_re/tools/pm_boot.py`.  Writes
artifacts/title_frame.png.

    python -m kegg.probes.render_title [steps]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "dos_re")]

from dos_re.dos4gw import render_pm_frame       # noqa: E402
from dos_re.frame_verify import write_rgb_png   # noqa: E402
from kegg.runtime import create_game_runtime    # noqa: E402


def main(argv) -> int:
    exe = ROOT / "assets" / "KE.EXE"
    if not exe.exists():
        print("assets/KE.EXE missing")
        return 0
    steps = int(argv[0]) if argv else 20_000_000
    rt = create_game_runtime(exe)
    rt.dos.key_queue.append(0x20)      # the boot screen's "press SPACE" prompt
    try:
        rt.cpu.run(steps)
    except Exception as e:  # noqa: BLE001
        print(f"stopped: {type(e).__name__}: {e} at eip=0x{rt.cpu.eip:X}")
    print(f"instr={rt.cpu.instruction_count} mode={getattr(rt.dos, 'video_mode', None):#x} "
          f"chain4={rt.dos.vga.chain4} display_start=0x{rt.dos.vga.display_start:x}")
    out = ROOT / "artifacts" / "title_frame.png"
    out.parent.mkdir(exist_ok=True)
    rgb, w, h = render_pm_frame(rt.dos)
    write_rgb_png(out, rgb, width=w, height=h)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
