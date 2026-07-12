# Krypton Egg (KE.EXE) — recovery status

## Summary (for the human)

**The game runs — and it's in-game.** In one session the port went from "the
VM cannot load this executable at all" to Krypton Egg booting through its whole
hardware-detection screen, animating its title, responding to a key press, and
rendering **level-1 gameplay** (bricks, paddle, ball, score bar) — all executed
by the original game code inside the new 386 protected-mode VM, with correct
colors and screen layout (verified against the player's reference screenshot).

What made it possible: a loader for the game's 32-bit executable format, a new
386 CPU interpreter, an emulated DOS/4GW environment (DOS services, DPMI
memory, VGA including the "Mode X" trick the game uses for its 70 fps
rendering, a keyboard controller with real interrupts, and a mouse driver).
Sound Blaster is not emulated yet — the game politely warns and continues.

Next: drive the menus properly (keyboard input works now), wire the standard
play runner with a live window, get file I/O exercised (the game hasn't opened
its data files yet in our runs — title/gameplay assets appear to be loaded…
investigate), and start the demo corpus.

## Where we are

- **Phase:** Bring-up, steps 1–3 done (load & run ✓, see output ✓, frame
  boundary found ✓ — the 3DAh retrace wait at link 0x19e35). Step 2½ (live
  viewer/input wiring) and steps 4–6 (frame verifier, input-wait registry,
  first demo) are next.
- **Native %:** n/a (bring-up)
- **Demo corpus:** none yet
- **Open blockers:** none open (B1, B2 resolved — see blockers.md)

## Recent findings (newest first)

- 2026-07-12 — **GAMEPLAY RENDERS.** After SPACE at the title (scancode via the
  new 8042 KBC + IRQ1 delivery into the game's INT 9 handler), the game
  page-flips (display_start 0x4000) into level-1 attract/play. Proven by:
  `artifacts/after_space.png` vs the player's reference screenshot.
- 2026-07-12 — **VGA write mode 1** (latched plane copy) implemented for the
  title→game transition; latches load on every planar read.
- 2026-07-12 — **LE images must be rebased above 1 MB** (like real DOS/4G):
  loaded at the link base, the Watcom heap grew into the A000h aperture and
  planar writes shredded the heap free-list (crash at link 0x2650f with a heap
  block at 0xa5004). `load_le(rebase=0x100000)` in the runtime; analysis tools
  keep link addresses. **Runtime eip = link address + 0x100000.**
- 2026-07-12 — **Mode X planar model** (`VGASequencer` + FlatMemory aperture
  routing): the game unchains chain-4 after mode 13h; the linear render's
  "4 copies" artifact resolved into the correct title frame.
- 2026-07-12 — **IRQ delivery into protected mode**: `CPU386.deliver_interrupt`
  (32-bit frame, IF/TF clear, IRET-compatible) + `idt` shared with the host's
  AH=25 vectors; 8042 KBC with per-byte IRQ1 (identify/rate/LED command
  protocol recovered from the game's driver at link 0x1cf40).
- 2026-07-12 — Mouse detection = a flat read of real-mode IVT[0x33] (linear
  0xCC), not INT 33h: `seed_low_memory` populates BIOS/DOS/mouse/IRQ vector
  ranges only (a non-null 67h sent the game probing VCPI — narrowed).
- 2026-07-12 — Boot screen printed via INT 21h AH=40 to stdout: CPU/DOS/VGA/
  B-MEM/X-MEM (4 MB accepted)/mouse all detected; INT 33h services 0000/0024/
  001B etc. answered as MS driver 8.20.
- 2026-07-12 — CPU386 + DOS4GWHost boot the C runtime (~15k instructions,
  earlier frontier); LE loader verified. (Details: git history.)

## Risks / unknowns

- ~~No file opens observed~~ **resolved**: the earlier spy read the wrong
  register (r[3]=EBX, not EDX). Verified opens: `ke_tit.gif` at boot;
  `ke_menu.gif`, `ke_menu.bob`, `ke_all.pal` after SPACE — the post-SPACE
  screen is the **menu** (its background is an attract-level scene).
  Case-insensitive name resolution works.
- **Timer IRQ0 not exercised**: pacing so far rides the deterministic retrace
  toggle. The game installed no INT 8 vector in observed runs (checked
  pm_vectors) — its 70 fps loop may be pure vsync. Confirm before demos.
- **Sound Blaster absent**: game warns and continues. SB (port 0x210 probing
  observed) comes later via dos_re's SoundBlaster model.
- x87 doubles vs 80-bit: documented precision caveat, same as CPU8086.
- The KBC "identify" flow uses polling + IRQ mix; scancode → game key mapping
  unverified beyond SPACE (0x39/0xB9 worked).

## Next targets

1. **Human playtest** of the live viewer (`python scripts/play.py`) — controls,
   menu navigation, whether gameplay starts and feels right; note speed (CPython
   ~1-2 M instr/s; pypy is the fast path).
2. Snapshot support for PMRuntime (FlatMemory + CPU386 + host state) —
   unlocks F12/resume, demo recording, and the frame verifier.
3. Input-wait registry + first recorded demo (menus → gameplay), then the
   frame verifier over the retrace boundary.
4. Sound Blaster detection (game probes DSP at port 0x210/0x21C/0x21E) via
   dos_re's SoundBlaster model, so the game boots with sound enabled.

Done since: live play runner (`scripts/play.py`, PM viewer: wall-clock vsync
pacing, KBC scancodes incl. E0 arrows, INT 33h mouse, F10 screenshot,
--headless smoke); file I/O verified.
