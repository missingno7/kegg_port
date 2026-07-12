# Krypton Egg — blockers

Loop protocol: a slice blocked after ~2 focused attempts ⇒ revert fully, log
here, take the next target. A logged blocker is progress; a workaround is debt.

## Open

(none)

## Resolved

### B2 — Selector→base model for DPMI DOS-memory blocks — RESOLVED 2026-07-12

- Implemented option A: `CPU386.selector_bases` (mini descriptor table, RPL
  masked) + a per-segment-register resolved-base cache (`sbase`) updated on
  every segment load; memory operands honor override prefixes and the SS
  default for EBP/ESP forms. DPMI INT 31h AX=0100 allocates from a
  conventional pool (0x60000–0x9FFFF) and registers the selector. Proven by
  `dos_re/tests/test_cpu386.py::test_selector_base_resolution` + the game
  running through DOS-memory allocation into gameplay.

### B1 — No 386 protected-mode CPU in dos_re — RESOLVED 2026-07-12

- Built `dos_re/cpu386.py` (`CPU386` + `FlatMemory`) as a **new class** (human
  chose option B) + `dos_re/dos4gw.py` (`DOS4GWHost`). Boots KE and runs ~15k
  startup instructions. Framework suite green (288), lint clean.
