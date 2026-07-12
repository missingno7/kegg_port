# Krypton Egg — blockers

Loop protocol: a slice blocked after ~2 focused attempts ⇒ revert fully, log
here, take the next target. A logged blocker is progress; a workaround is debt.

## Open

### B2 — Selector→base model for DPMI DOS-memory blocks (design choice)

- **Symptom:** `CPU386` treats every segment selector as flat base 0 — correct
  for the LE's own CS/DS/SS/ES. But DPMI "Allocate DOS Memory Block" (INT 31h
  AX=0100, KE hits it at 0x2585D) returns a *based* selector whose base =
  paragraph×16, so `[selector:offset]` must resolve to `base+offset`, not
  `offset`. Reached after ~15,111 startup instructions.
- **Options:**
  - (A) **[leaning]** give `CPU386` a `seg_base` map (mini-descriptor table),
    default 0 (flat), with DPMI registering based selectors. Effective address
    = `seg_base.get(sel, 0) + offset`. Mirrors `Memory.sel_base` (the Win16
    trick) with a `sel_min` threshold so the flat hot path stays fast.
  - (B) exploit DOS/4GW's 1:1 low-memory mapping: allocate DOS blocks at linear
    `para×16` and hope the game accesses them via the flat DS + linear address
    rather than the returned selector. Fragile if it keeps the selector.
- **Not blocking other work** — it's the very next step; logged so the model
  choice is explicit before implementing INT 31h memory services.

## Resolved

### B1 — No 386 protected-mode CPU in dos_re — RESOLVED 2026-07-12

- Built `dos_re/cpu386.py` (`CPU386` + `FlatMemory`) as a **new class** (human
  chose option B) + `dos_re/dos4gw.py` (`DOS4GWHost`). Boots KE and runs ~15k
  startup instructions. Framework suite green (288), lint clean.
