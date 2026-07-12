# kegg/lifted32 — lift proof ledger

Mechanically lifted functions (tools/pmlift-style pipeline over
`lift/decode32|cfg32|emit32`), each proven in situ by the strict PM
differential verifier (`pm_verification.PMHookVerifier`: full-machine diff
against the interpreted original at every sampled call).  Lifted ≠ recovered:
these graduate to `kegg/recovered/` only after refactoring (with the same
oracle keeping the refactor honest).

Runtime (rebased) addresses; link = runtime − 0x100000.

| Entry | Working name | Insts | Status | Evidence |
|---|---|---|---|---|
| 0x1222D1 | blit_sprite_planar — THE hot Mode X RLE sprite blitter (plane-phase setup `edi&3` → rotated 0x11 map mask, `shr edi,2` plane offset, per-row run copy/skip loop at 0x122362) | 256 | **ORACLE_PASSING ×8** (retired at samples cap) | in-situ verify from `artifacts/snapshots/snap_126359171` (in-game), 2026-07-13 |
| 0x122288 | blit_queue_entry — deferred-draw queue writer (bump-allocates 0x14-byte records at [0x148360]) then falls into the blitter | 273 | **ORACLE_PASSING ×8** (retired) | same run |

Dispatch: both reached through draw-function pointers at 0x1483FE/0x148402
(no direct callers — the census's `--auto-entries` sweep can't see them; found
via data-pointer scan).

## Why these are here

The profiler (from the in-game snapshot) puts virtually all gameplay time in
the 0x122362 run loop.  The literal lifts are speed-NEUTRAL (measured: 4.16 →
4.22 M instr/s under pypy) — per-instruction Python either way.  They are the
**correctness baseline** for the next slice: a bulk `recovered/` blitter
(slice writes into `VGASequencer.planes`) installed as the hook, verified by
the same differential oracle, which removes ~all of those interpreted
instructions from the frame cost.
