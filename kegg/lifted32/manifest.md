# kegg/lifted32 — lift proof ledger

> **Note:** the blitter (0x1222D1) is now RECOVERED as clean native
> code in `kegg/recovered/rle_blit.py` (+ `kegg/render_hooks.py`), which
> `create_game_runtime` installs instead.  These literal lifts remain as
> the verified baseline / the source for the recovered refactor; the
> queue-writer 0x122288 is left un-hooked so its prologue falls into the
> recovered blitter (see kegg/runtime.py).

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

## Why these are here (and the measured win)

The profiler (from the in-game snapshot) puts virtually all gameplay time in
the 0x122362 run loop.  Installing these two lifts is a **2.5x speedup**
measured on that snapshot (pypy, 20 M in-game instructions retired: 4.18 ->
10.44 M instr/s, blitter called ~9000x) — the lifted Python skips the
interpreter's fetch/decode/dispatch, which is ~60% of per-instruction cost.
`install_replacements=True` (kegg.runtime, the default for play) installs
them; the differential-verify path boots with `install_replacements=False`.

The NEXT lever is a bulk `recovered/` blitter that decodes each RLE run as
native slice writes into `VGASequencer.planes` (collapsing each ~2000-
instruction call to tens of Python ops), verified by the same oracle.  Note
it is a large slice, not a quick refactor: this routine is a self-contained
state machine (0 calls / 0 INTs) with TWO RLE paths (unclipped 0x1222F8+,
edge-clipped 0x1223B9+), programs the VGA sequencer via OUT mid-decode, and
mutates scratch globals (0x148376/80/88, 0x14836C, 0x14838C, 0x1483A4/A5)
the oracle diffs — so the recovered version must reproduce every side effect,
not just the pixels.
