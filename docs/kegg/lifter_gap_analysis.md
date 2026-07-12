# Automatic lifter → 386/DOS4GW: gap analysis (2026-07-12)

Question: can `liftgen`/`liftverify` be leveraged for KE, and what's missing?

**Verdict: the architecture transfers cleanly; every 16-bit-specific layer
needs a 32-bit counterpart. Not usable today; a well-bounded port makes it
usable, and KE is an unusually good lift target once it lands.**

## Layer-by-layer

| Layer | 16-bit state | Gap for KE (32-bit flat) |
|---|---|---|
| `lift/decode.py` (static decoder: lengths, CF class, targets) | 8086/80186 scope **by design**; `0F`/x87 = UNSUPPORTED; no 0x66/0x67 in `PREFIXES` | Needs `decode32`: default-32 operand/address state, 0x66/0x67, ModRM+**SIB**+disp32, imm32, the `0F` map (movzx/movsx, near jcc, setcc, imul, bt-family, shld/shrd — KE uses all of these). The `Inst` dataclass + kind taxonomy reuse as-is. The length cross-check trick (count fetch bytes through one interpreter `step()`) transfers to `CPU386._fetch8`. |
| `lift/cfg.py` (function scan, refusals) | Imports the 16-bit decoder directly | Parametrize by decoder; the walk itself is ISA-agnostic over `Inst.kind`. Small. |
| `lift/emit.py` (literal Python per instruction) | CPU8086-shaped throughout: `s.ax` model, `mem.rw(seg,off)`, `set_add_flags`/`shift`/`condition` helpers, 16-bit `_RM_BASE` table | Needs `emit32`: `r[i]`/`set_reg` model, flat linear addressing (+`sbase` for based selectors), SIB expression emission, CPU386's `_flags_*` helpers. The emitted-hook contract (basic-block dispatch loop, `# (interpreter fallback)` lines, call/INT delegation) transfers unchanged — v1 can be fallback-heavy and still verify, then grow native forms by frequency. Largest chunk. |
| `lift/runtime.py` (emulate_call / emulate_int / interp_one) | Typed to CPU8086 | Mirror for CPU386 (same delegation design). Small-medium. |
| **Hook + differential verifier** (`hooks.py`, `verification.py`) | CPU8086 has `replacement_hooks` dispatch in `step()`; `HookVerifier` clones runtime state and diffs at continuations; snapshots via `snapshot.py` | **CPU386 has no hook surface at all** — no `replacement_hooks`, no verifier, no state clone. `pm_snapshot.py` (landed today) covers the fixture side. This is the true prerequisite — and it is NOT lifter-specific: the frame verifier and the whole oracle-hook method need the same machinery. |
| `tools/liftgen.py` / `liftverify.py` CLIs | Bind 16-bit `load_snapshot`, CS:IP entry addressing | PM mode: `pm_snapshot.load_pm_snapshot`, flat linear entries. Small. |

## Why KE is a *good* lifter target once this lands

- Watcom C code: uniform prologues/epilogues, regular register calling
  convention — clean function boundaries for the CFG scan.
- Flat memory: no segment arithmetic, no seg:off aliasing — the emitter's
  hardest 16-bit problems simply don't exist here.
- The `0F`/x87 refusal class that plagued 16-bit census coverage is just
  "more opcodes to decode" here; the interpreter (CPU386) already executes
  them, so the cross-check keeps decode32 honest from day one.
- Indirect calls (`liftgen`'s main refusal) exist via fixed-up function
  pointers; the census will size that tail.

## Dependency-ordered build plan

1. ~~**CPU386 hook surface**~~ **DONE 2026-07-12** — linear-EIP-keyed
   `replacement_hooks` dispatch in `step()`, same contract as CPU8086.
2. ~~**PM differential verifier**~~ **DONE 2026-07-12** —
   `pm_verification.PMHookVerifier` (strict auto-continuation, full-machine
   diff) over `pm_snapshot.clone_pm_runtime`; proven game-free (correct hook
   passes; wrong result / stray write / stale flags each raise).
3. ~~**`decode32.py`**~~ **DONE 2026-07-12** — `lift/decode32.py`; validated
   by 15 unit shapes + a 400k-instruction length cross-check against CPU386
   on real KE boot execution (zero disagreements). cfg parametrization still
   pending (folds into item 4).
4. **`emit32.py`** + `runtime32` delegation primitives + cfg over Inst32.
5. **CLI PM modes** for liftgen/liftverify.

Sequencing note: porting_new_game.md starts the lifting loop at step 7, after
frame verifier (4), input waits (5), first demo (6). Items 1–2 are shared
with step 4, so they come next regardless; 3–5 can proceed in parallel with
demo-corpus work.
