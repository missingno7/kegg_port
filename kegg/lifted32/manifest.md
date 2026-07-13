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

## Gameplay-logic batch (2026-07-13) — all ORACLE_PASSING x8 in-game

Lifted + verified from the gameplay snapshot (snap_126359171); working names
from static reading (to be confirmed when refactored into `recovered/`).

| Entry | Working name | Insts | What it does |
|---|---|---|---|
| 0x1183b1 | build_draw_list | 44 | iterates half the object table, emits draw commands ([0x14e2ec]) from object position/size fields |
| 0x118345 | update_anim_timers | 38 | frame-counter [0x14e14c]++; per-object animation timer advance/reset ([+8] += [+0xc] or := [+4] at [+0x10]) |
| 0x1195ee | load_object_fields | 23 | copies current-object fields ([0x14e158]) into the working globals [0x14e15c..0x14e162] |
| 0x118004 | compute_sprite_bounds | 32 | sets [0x14e158]=arg1, calls 0x1195ee, folds signed x/y offsets into the caller's rect, derives right/bottom (= left/top + w/h − 2). **RECOVERED** → `kegg/recovered/anim.setup_sprite_rect`; ORACLE_PASSING (60/60) |
| 0x115381 | (238 insts) | 238 | large leaf — biggest game-logic routine in the hot set |
| 0x114cf2 | (418 insts) | 418 | large routine |
| 0x113702 | (146 insts) | 146 | |
| 0x1185a4 | (622 insts) | 622 | largest lifted routine |
| 0x118004 | (32 insts) | 32 | |
| 0x11c960 | (33 insts) | 33 | |
| 0x11c9ce | (18 insts) | 18 | |
| 0x11ee65 | (27 insts) | 27 | |
| 0x11fd7b | (64 insts) | 64 | |
| 0x122a9c | (56 insts) | 56 | draw-compositor helper (0x122a9c region) |
| 0x122b94 | (66 insts) | 66 | draw-compositor helper |
| 0x1245ad | (16 insts) | 16 | |

Not lifted (hook by hand): 0x119e29 (vsync spin wait — env-coupled),
0x119d40 (frame driver — indirect call), 0x122d5f (draw dispatcher — indirect
`jmp [table]` at 0x1483aa, the type->handler switch).


## Broad coverage sweep (2026-07-13)

With the indirect-jump-as-tail-jump lift, an auto-entries census of the
gameplay code hit **120 / 120 liftable (100%)** — the tail-jump support
removed the last common refusal.  A full lift+verify pass over those 120
from the gameplay snapshot: **49 ORACLE_PASSING (byte-exact in situ, zero
divergence), 71 NOT_REACHED** (need other game states to exercise).

The 49 verified this pass (runtime addrs): 0x1158B0 0x117E62 0x118004
0x118066 0x11843A 0x119D40 0x119E10 0x11B17E 0x11B1DF 0x11B4A7 0x11B541
0x11B57A 0x11B5DF 0x11C14B 0x11C20D 0x11C3AB 0x11C8C0 0x11C9CE 0x11DD01
0x11ED38 0x11EE65 0x11FA42 0x120137 0x120502 0x12065B 0x12085A 0x121420
0x122CBD 0x122F9C 0x1230B7 0x123889 0x123A48 0x123B72 0x123BB6 0x123F0E
0x123F5D 0x123F76 0x123FAD 0x124120 0x1245AD 0x1245D0 0x124609 0x124617
0x124705 0x124713 0x124771 0x124A8C 0x126706 0x1267AC.

Reproduce/emit any of them:
`python dos_re/tools/pmlift.py --exe assets/KE.EXE --snapshot
artifacts/snapshots/snap_126359171 --entry 0xADDR --verify --emit-dir
kegg/lifted32`.  (A whole-image static emit trips region-budget on some
entries the snapshot-context scan accepts — lift from the snapshot.)


## Gameplay control layer (2026-07-13) — verified from the ball-on-paddle snapshot

ORACLE_PASSING x8: 0x119d40 (per-frame update / mode-handler caller),
0x11fb17 (gameplay subsystem dispatcher, keyed on [0x147b34]), 0x11fd3b
(active input->action subsystem), 0x11ed38.  Control-flow map in
docs/kegg/control_flow.md.

NOT_REACHED here (need a ball-in-flight snapshot): 0x11fb92 (launch),
0x11fbc0, 0x11fc1e, 0x11fe6a, and the physics/collision they reach.


## Ball physics layer (2026-07-13) — verified from snap_157569453

The launched-ball snapshot reaches the ball-active subsystems; ORACLE_PASSING
x8: 0x11fbc0, 0x11fc1e, 0x11fe6a (were NOT_REACHED before), + 0x11fd3b.  Ball
state map + handlers (0x112c72, 0x11353f, the Y-swap leaf 0x11eda0) in
docs/kegg/control_flow.md.
