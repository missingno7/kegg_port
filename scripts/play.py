"""play.py — the human entry point of the Krypton Egg port.

Runs KE.EXE live in the flat 386 protected-mode runtime (dos_re.cpu386 +
dos4gw): a pygame window presenting the VGA screen (chained 13h or unchained
Mode X), keyboard delivered as set-1 scancodes through the emulated 8042 KBC,
mouse through the INT 33h driver state, pacing by wall-clock vsync (the
game's own 3DAh retrace waits run at ~70 Hz real time).

NOTE: this is the PM (DOS/4GW) counterpart of the standard play runner.  The
16-bit ports front ``dos_re.player``; PMRuntime does not yet have snapshot /
input-demo engines, so this file keeps the standard *surface* (flags,
hotkeys) and will grow onto those engines as they land.  CPython is ~1-2 M
instr/s — if the game feels slow, run under pypy (13-17x, docs/performance.md).

Usage:
    python scripts/play.py                       # live viewer
    python scripts/play.py --headless --steps N  # deterministic smoke run
Viewer hotkeys: F10 screenshot -> artifacts/screenshots/.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))              # the kegg adapter package
sys.path.insert(0, str(ROOT / "dos_re"))   # the dos_re submodule's repo root

from dos_re.dos4gw import DosInputExhausted, render_pm_frame   # noqa: E402
from dos_re.frame_verify import write_rgb_png                  # noqa: E402
from kegg.runtime import create_game_runtime                   # noqa: E402

# pygame key name -> set-1 scancode (make code; break = make | 0x80).
# Extended keys (arrows...) are (0xE0, code) tuples.
_SC = {
    "escape": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B, "-": 0x0C,
    "=": 0x0D, "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15,
    "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19, "[": 0x1A, "]": 0x1B,
    "return": 0x1C, "left ctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23,
    "j": 0x24, "k": 0x25, "l": 0x26, ";": 0x27, "'": 0x28, "`": 0x29,
    "left shift": 0x2A, "\\": 0x2B,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30, "n": 0x31,
    "m": 0x32, ",": 0x33, ".": 0x34, "/": 0x35, "right shift": 0x36,
    "left alt": 0x38, "space": 0x39, "caps lock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43,
    "up": (0xE0, 0x48), "down": (0xE0, 0x50),
    "left": (0xE0, 0x4B), "right": (0xE0, 0x4D),
}


def _send_key(dos, name: str, make: bool) -> None:
    sc = _SC.get(name)
    if sc is None:
        return
    if isinstance(sc, tuple):
        dos.press_scancode(sc[0])
        dos.press_scancode(sc[1] | (0x00 if make else 0x80))
    else:
        dos.press_scancode(sc | (0x00 if make else 0x80))


def run_viewer(rt, args) -> int:
    import pygame

    pygame.init()
    scale = args.scale
    win = pygame.display.set_mode((320 * scale, 200 * scale))
    pygame.display.set_caption("Krypton Egg — dos_re (hybrid)")

    dos, cpu = rt.dos, rt.cpu
    dos.time_source = time.monotonic       # 3DAh retrace advances at 70 Hz real time
    shots = ROOT / "artifacts" / "screenshots"

    # DOS console reads (the boot screen's "press SPACE") block until a real
    # key arrives: on an empty queue we idle-pump events until the next
    # KEYDOWN character lands in dos.key_queue, then resume the CPU.
    waiting_console = False
    next_present = time.monotonic()
    running = True
    while running:
        if not waiting_console:
            try:
                cpu.run(20_000)
            except DosInputExhausted:
                waiting_console = True
            except Exception as e:  # noqa: BLE001 — the fail-loud frontier
                print(f"STOP at eip=0x{cpu.eip:X}: {type(e).__name__}: {e}")
                running = False
            if cpu.halted:
                print(f"program exited (code {dos.exit_code})")
                running = False

        now = time.monotonic()
        if now < next_present:
            continue
        next_present = now + 1 / 70.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type in (pygame.KEYDOWN, pygame.KEYUP):
                make = ev.type == pygame.KEYDOWN
                name = pygame.key.name(ev.key)
                if make and name == "f10":
                    shots.mkdir(parents=True, exist_ok=True)
                    rgb, w, h = render_pm_frame(dos)
                    out = shots / f"shot_{int(now * 1000)}.png"
                    write_rgb_png(out, rgb, width=w, height=h)
                    print(f"screenshot -> {out}")
                    continue
                _send_key(dos, name, make)
                if make and waiting_console:
                    ch = ev.unicode
                    if ch:
                        dos.key_queue.append(ord(ch[0]) & 0xFF)
                        waiting_console = False
            elif ev.type == pygame.MOUSEMOTION:
                mx, my = ev.pos
                dos.mouse_x = min(639, mx * 2 // scale)   # MS driver: 0-639 virtual x
                dos.mouse_y = min(199, my // scale)
            elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                down = ev.type == pygame.MOUSEBUTTONDOWN
                bit = {1: 1, 3: 2}.get(ev.button, 0)
                cur = getattr(dos, "mouse_buttons", 0)
                dos.mouse_buttons = (cur | bit) if down else (cur & ~bit)

        rgb, w, h = render_pm_frame(dos)
        frame = pygame.image.frombuffer(rgb, (w, h), "RGB").convert(win)
        pygame.transform.scale(frame, win.get_size(), win)
        pygame.display.flip()
    pygame.quit()
    return 0


def run_headless(rt, args) -> int:
    rt.dos.key_queue.append(0x20)          # boot prompt
    try:
        rt.cpu.run(args.steps)
    except Exception as e:  # noqa: BLE001
        print(f"STOP after {rt.cpu.instruction_count} at eip=0x{rt.cpu.eip:X}: "
              f"{type(e).__name__}: {e}")
        return 1
    print(f"ran {rt.cpu.instruction_count} instructions; halted={rt.cpu.halted}")
    if args.png:
        rgb, w, h = render_pm_frame(rt.dos)
        write_rgb_png(Path(args.png), rgb, width=w, height=h)
        print(f"wrote {args.png}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", default=str(ROOT / "assets" / "KE.EXE"))
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--steps", type=int, default=20_000_000,
                    help="instruction budget (headless)")
    ap.add_argument("--png", default="", help="headless: render the final screen")
    ap.add_argument("--scale", type=int, default=3, help="window scale factor")
    args = ap.parse_args(argv)

    rt = create_game_runtime(args.exe)
    if args.headless:
        return run_headless(rt, args)
    return run_viewer(rt, args)


if __name__ == "__main__":
    raise SystemExit(main())
