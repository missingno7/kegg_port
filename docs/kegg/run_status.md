# Krypton Egg (KE.EXE) — recovery status

## Summary (for the human)

**The game runs, plays, and its code is being recovered — verified byte-for-byte
against the original.** Krypton Egg boots, shows its title and menu, plays
level 1 with sound and mouse, all inside the new 386 protected-mode VM. Beyond
"it runs", the actual game code is now being turned back into readable source:
the two sprite blitters (the bulk of the on-screen drawing) are **rewritten as
clean native code**, and ~50 more gameplay routines (animation, the draw-list
builder, the object system, the draw dispatcher) are **mechanically recovered
and proven identical to the original** on the real game. Every one is checked
by running the original and the recovered code side by side and comparing the
entire machine — registers, memory, and screen — after each call; so far
**79,500+ blitter calls and ~50 routines, zero mismatches**.

What made it possible: a loader for the game's 32-bit format, a new 386 CPU,
an emulated DOS/4GW environment (VGA Mode X, Sound Blaster, keyboard IRQs,
mouse), and an automatic "lifter" that turns the original machine code back
into verified Python — extended this session so it can also recover the
game's switch-statement dispatchers (100% of the gameplay code is now
recoverable this way).

Next: name the object/struct fields into a clean data model (a couple more
routines will confirm them), then keep converting the verified lifts into
readable named source; reach the routines that only run in other game states
(needs a few more play sessions to capture).

## Where we are

- **Phase:** Lifting loop (charter Phase 1) — the rendering island's two
  blitters recovered as clean source; a broad batch of gameplay logic
  lift-verified. Bring-up (steps 0–6) done except a formal demo corpus.
- **Recovered (clean source):** the whole per-frame render chain — the two
  Mode X sprite blitters (`kegg/recovered/rle_blit.py`) AND the animation
  updater + draw-list builder (`kegg/recovered/anim.py` over the object/sprite
  bridge `kegg/bridge/game_state.py`).  80,187 in-game calls verified
  byte-exact, zero divergence.
- **Data model:** the object system is recovered — a table of 0x18-byte
  animation cells, paired into 0x30-byte sprites; per-frame the accumulators
  advance and drive each sprite's drawn size/position (docs/data_model.md).
- **Lift-verified (scaffold for recovery):** ~50 routines ORACLE_PASSING in
  situ (incl. the draw dispatcher via the new tail-jump lift); 100% of the
  auto-entries census is liftable.
- **Demo corpus:** one gameplay snapshot (snap_126359171). **To recover more
  breadth I need more captured states** — 71 lift targets are NOT_REACHED
  because they only run in the menus / other levels / death / game-over.
  A few `python scripts/play.py` sessions with F12 snapshots at those
  moments would unblock them.
- **Open blockers:** none.

## Recent findings (newest first)

- 2026-07-13 — **The sprite blitter is FULLY RECOVERED as native source** —
  all three variants (unclipped, horizontal-clip, vertical-clip) now run as
  clean native code with NO interpreter fallback.  The vertical-clip variant
  (0x1223b9) uses a left-edge shift model (`decode_row_leftclip`): the sprite
  is shifted left by `[0x148380]>>2` and runs left of the visible edge are
  clipped; its offset-table preamble is indexed by a plane phase `[0x14838c]`
  that advances 0->3 per pass.  **All 27,745 in-game blitter calls verified
  byte-exact against the ASM oracle, zero divergence** (`pm_verification`;
  `tests/test_rle_blit.py`).  This completes the rendering island's core
  decode as recovered source.

- 2026-07-13 — **The sprite blitter's unclipped path is RECOVERED as clean
  native source** — `kegg/recovered/rle_blit.py` (pure RLE decoder) +
  `kegg/render_hooks.py` (the thin VM bridge that reproduces the routine's
  full effect: planes, registers, sequencer, scratch globals, even the
  push/pop stack scratch).  Proven **byte-exact against the interpreted ASM
  oracle over 10,802 in-game calls, zero divergence** (`pm_verification`;
  regression in `tests/test_rle_blit.py`).  `create_game_runtime` installs
  it; the two clipped variants (0x22539 h-clip, 0x223b9 v-clip) fall back to
  the interpreter until recovered next.  This is the first fully-recovered
  gameplay routine (source, not just a lift).


- 2026-07-13 — **Rendering island: core RLE primitive recovered as clean
  native code.** `kegg/recovered/rle_blit.py` (`decode_row`/`decode_plane_pass`,
  pure — no dos_re, layer-audit clean) reproduces the interpreted blitter's
  plane output **byte-for-byte** on the gameplay snapshot
  (`tests/test_rle_blit.py`, 4 tests incl. the in-game oracle match).  The
  full 3-variant blitter is mapped in
  [`rendering_island.md`](rendering_island.md); composing the recovered hook
  (reproducing the preamble + sequencer + scratch globals the oracle diffs)
  is the next slice, built flag-path by flag-path with interpreter fallback.


- 2026-07-13 — **The rendering island is located, lifted and oracle-proven.**
  From the human's in-game snapshot (snap_126359171): virtually all gameplay
  time is one routine — the Mode X RLE sprite blitter at 0x1222D1 (runtime;
  dispatched via draw-pointers at 0x1483FE/0x148402, hot loop 0x122362).
  Both it and the deferred-draw queue writer (0x122288) lift mechanically and
  pass the strict differential verifier in-game (ORACLE_PASSING ×8 each) —
  `kegg/lifted32/` + manifest.  Literal lifts are speed-neutral (measured);
  the speedup slice is the bulk `recovered/` blitter next.
- 2026-07-13 — **Interpreter speed paths** (equivalence-tested): bulk forward
  REP MOVS/STOS as slice ops incl. planar map-mask scatter, plane->RAM
  gather, and write-mode-1 plane-to-plane block copy (8 randomized
  equivalence cases vs the per-unit loop); IRQ-source polling decimated to
  every 16 instructions (~10% of the whole interpreter, measured).  In-game:
  CPython 0.65 M instr/s, pypy 4.6 M instr/s (original 386 ≈ 10 MIPS — the
  human's "runs slow" is real; the recovered blitter is the lever).
- 2026-07-13 — SB audio end-to-end + AH=35 default-vector fix + mouse
  virtual-range mapping (see git log for the three-layer audio onion).



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

## Next targets (updated 2026-07-13)

1. **The bulk recovered blitter** — refactor lifted 0x1222D1 into
   `kegg/recovered/` bulk plane-slice operations behind a thin hook; prove
   with the differential verifier + a frame render compare; measure the
   speedup from the snapshot.  This is the "lift the rendering island" plan's
   speed payoff.
2. **PM input-demo engine** — DONE.  F11 records a self-contained demo
   *bundle* directory (a start snapshot + an input manifest keyed to the
   game's own frame clock); `--play-demo <dir>` boots from the bundle's own
   snapshot and re-injects the input at the same frame boundaries, so a
   mid-game demo replays deterministically.  Same shape as the real-mode
   player's demos — the snapshot is an internal detail the user never wires up.
3. More lifting from the gameplay snapshot (pmlift --snapshot now reaches
   gameplay functions).

## Older targets

1. **Human playtest** of the live viewer (`python scripts/play.py`) — controls,
   menu navigation, whether gameplay starts and feels right; note speed (CPython
   ~1-2 M instr/s; pypy is the fast path).
2. **Start the real lifting loop** — the full 386 lifter pipeline is DONE and
   proven on KE (census 98% liftable; 13 functions ORACLE_PASSING in situ,
   zero divergences — [`lifter_gap_analysis.md`](lifter_gap_analysis.md)).
   Next: snapshot at the menu/gameplay, `pmlift --verify` from there to reach
   the gameplay functions, promote passing lifts into `kegg/lifted32/` with
   the manifest ledger.
3. Input-wait registry + first recorded demo (menus → gameplay), then the
   frame verifier over the retrace boundary (same clone/diff machinery).
4. Sound Blaster detection (game probes DSP at port 0x210/0x21C/0x21E) via
   dos_re's SoundBlaster model, so the game boots with sound enabled.

Done since: live play runner (viewer, KBC keys, mouse, F10/F12, --snapshot
resume); PM snapshots + resume-determinism proof; CPU386 hook surface +
strict differential verifier; decode32 (400k-instruction cross-check);
**the complete 32-bit lifter (cfg32/emit32/runtime32 + pmlift CLI) with
first real lifts verified against the oracle in the running game**.
