# Krypton Egg (KE.EXE) — recovery status

## Summary (for the human)

Krypton Egg is a 1994 commercial break-out game built with Watcom C and the
DOS/4GW extender — it runs in **32-bit protected mode**, which the dos_re VM
(a 16-bit real-mode CPU) did not understand. So bring-up started one layer
lower than usual: we had to load the 32-bit program image and build a 386
protected-mode CPU plus the DOS/4GW services the game calls.

Progress so far — a lot for one session:
1. **LE loader** (`dos_re/le.py`): unpacks the executable into a flat 32-bit
   memory image; all 6296 internal fixups apply cleanly; the entry code
   disassembles as genuine Watcom startup. Verified by tests.
2. **A new 386 protected-mode CPU** (`dos_re/cpu386.py`) + a **DOS/4GW host**
   (`dos_re/dos4gw.py`). Together they now **boot the game and execute ~15,000
   instructions of its startup** — through the entire Watcom C runtime, the
   FPU/CPU detection, and VGA detection — before reaching the first thing not
   yet built (DPMI memory allocation). Everything runs against the original
   binary as the oracle; no behaviour is guessed.

Next: DPMI memory allocation (needs a small selector-base decision, below), then
setting the video mode and drawing the first frame.

## Where we are

- **Phase:** Bring-up, step 1 (load & run) — **booting; ~15k startup
  instructions execute**; frontier = DPMI INT 31h AX=0100 (alloc DOS memory)
- **Native %:** n/a (bring-up)
- **Demo corpus:** none yet
- **Open blockers:** B1 resolved (CPU built); B2 open = selector-base model
  for DPMI DOS memory (design choice) — see blockers.md

## Recent findings (newest first)

- 2026-07-12 — **CPU386 + DOS4GWHost boot KE to ~15,111 instructions.**
  Built a flat-model 386 interpreter (32-bit regs, ModRM+SIB, ALU/shift/rotate,
  string ops, seg push/pop, x87 FPU ported from `CPU8086.execute_fpu`, bit ops,
  SHLD/SHRD, SMSW/SIDT, CR access) and a DOS/4GW host (INT 21h/2Fh/10h + the
  extender probes). Startup path exercised, each service recovered from the ASM:
  extender probe (INT21 FF00 → native path), FPU infinity probe (`fld1;fldz;
  fdivp` needs masked 1/0=+inf), sbrk (INT21 ED/4A), IOCTL device-info (44/00),
  VGA detect (INT10 1A00), XMS absent (INT2F 4300), DPMI probe (INT2F 1687).
  Proven by: `tests/test_cpu386_boot.py` (floor 15k) + `kegg.probes.run_startup`.
  Framework suite still green (288 tests), lint clean.
- 2026-07-12 — **LE loader written and verified** (now `dos_re/le.py`, promoted
  from the adapter). 3 objects, 38×4 KB pages, 0 imports, flat model; fixup
  census 6292 off32 + 4 sel16. Proven by `tests/test_le_loader.py`.

## Risks / unknowns

- **Selector-base model (B2).** The flat CPU treats every segment as base 0.
  That holds for the LE's own flat CS/DS/SS/ES, but DPMI DOS-memory blocks
  (INT 31h AX=0100) return a *based* selector (base = para×16). Deciding how the
  CPU resolves selector→base is the next design step (blockers.md B2).
- **DPMI + VGA mapping.** File I/O for assets (.BOB/.DIG/.PAL) and VGA access at
  linear 0xA0000 still ahead; the heap/DOS-memory layout must not collide with
  the 0xA0000 VGA aperture.
- The startup's extender/DPMI probes were answered to select the DOS/4GW-native
  path; these are bootstrap (no oracle for the extender itself), the game code
  is the oracle from `main()` onward.

## Next targets

1. **Decide the selector-base model** (blockers.md B2) and implement DPMI
   INT 31h AX=0100 (+ 0101/0006/0200-ish as they appear).
2. Continue the boot: reach `INT 10h AX=0013` (set mode 13h) and the first VGA
   write; render the first frame with `tools/render_frame.py` (or an adapter
   rasterizer over the flat 0xA0000 region).
3. Wire file I/O so the game loads its assets; find the frame boundary /
   input-wait loop; record the first demo.
