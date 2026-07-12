"""Probe: boot KE.EXE's LE image on CPU386 + DOS4GWHost and run until it stops.

Reports where execution halts — the first unimplemented opcode / INT / DOS
service — which is the next thing to build (charter: fail loud, grow from the
observed call).

    python -m kegg.probes.run_startup [max_instructions]
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "dos_re")]

from kegg.runtime import create_game_runtime  # noqa: E402


def main(argv) -> int:
    exe = ROOT / "assets" / "KE.EXE"
    if not exe.exists():
        print("assets/KE.EXE missing")
        return 0
    limit = int(argv[0]) if argv else 2_000_000
    rt = create_game_runtime(exe)
    cpu = rt.cpu
    print(f"entry eip=0x{cpu.eip:X} esp=0x{cpu.r[4]:X}")

    # Ring buffer of recent (eip) so a fail-loud stop shows how we got there.
    trace = [0] * 40
    ti = [0]
    _orig_step = cpu.step

    def traced_step():
        trace[ti[0] % 40] = cpu.eip
        ti[0] += 1
        _orig_step()
    cpu.step = traced_step

    try:
        rt.cpu.run(limit)
        print(f"ran {cpu.instruction_count} instructions; halted={cpu.halted} "
              f"exit_code={rt.dos.exit_code}")
    except Exception as e:  # noqa: BLE001
        print(f"\nSTOPPED after {cpu.instruction_count} instructions at eip=0x{cpu.eip:X}")
        print(f"  eax=0x{cpu.r[0]:08X} ebx=0x{cpu.r[1]:08X} ecx=0x{cpu.r[2]:08X} edx=0x{cpu.r[3]:08X}")
        print(f"  esi=0x{cpu.r[6]:08X} edi=0x{cpu.r[7]:08X} ebp=0x{cpu.r[5]:08X} esp=0x{cpu.r[4]:08X}")
        print(f"  {type(e).__name__}: {e}")
        n = ti[0]
        recent = [trace[(n - k) % 40] for k in range(min(n, 16), 0, -1)]
        print("  recent eips: " + " ".join(f"0x{a:X}" for a in recent))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
