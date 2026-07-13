# Krypton Egg — symbol / address ledger

**Link addresses** in the LE image (obj1 code @0x10000, obj2 @0x30000,
obj3 data/stack @0x40000). **The runtime rebases +0x100000** (image above
1 MB, like real DOS/4G) — a runtime eip of 0x1242D8 is link 0x242D8. All
entries below are link addresses. Status ladder: GUESS → OBSERVED →
RECOVERED → ASM_MATCHED → VERIFIED → CANONICAL.

| Address | What | Status | Evidence |
|---|---|---|---|
| 0x242d8 | LE entry point | VERIFIED | LE header EIP=obj1+0x142d8; `jmp 0x24352` over version string |
| 0x24352 | C-runtime startup (`__CMain`/cstart) | OBSERVED | `sti`/`and esp,-4`/store SP globals/`int21 AH=30h` get-DOS-version |
| 0x4f610 | initial ESP (top of obj3) | VERIFIED | LE header ESP=obj3+0xf610 |
| 0x484a0,0x484b4 | saved initial ESP globals | OBSERVED | stored at 0x24358/0x2435e |
| 0x484ac | stored selector 0x24 (flat DS?) | OBSERVED | `mov ax,0x24; mov [0x484ac],ax` @0x24364 |
| 0x484d7/8 | DOS major/minor version | OBSERVED | stored from AL/AH after int21 AH=30h @0x24379 |

| 0x19e35 | **frame boundary: vsync wait** (`in al,3DAh; test al,8`) with spin counter | OBSERVED | hot-loop profile + disasm; the game's present cadence |
| 0x4e1a8 | vsync spin counter (calibration) | OBSERVED | `inc [0x4e1a8]` in the 3DA wait |
| 0x23fad | `in al,dx` port-read helper (callee of waits) | OBSERVED | disasm |
| 0x23fa3 | `out dx,al` port-write helper | OBSERVED | disasm |
| 0x1cf40 | keyboard-driver command sender: writes cmd byte to [0x47db3], calls 0x21420, waits [0x4e2f4] with 50000-spin timeout | OBSERVED | disasm + KBC bring-up |
| 0x47db3 | pending keyboard command byte | OBSERVED | ^ |
| 0x4e2f4 | keyboard ACK-wait flag (cleared by INT 9 ISR) | OBSERVED | ^ |
| 0x1ff5c | hardware ISR entry (pushal + all segs, cld, calls) — INT 9 handler body | OBSERVED | pm_vectors[9] = obj1+0xff5c region; disasm |
| 0x256ea | register-block INT dispatcher (Watcom intdosx-style) | OBSERVED | disasm; caller 0x245ad |
| 0x25722 | dispatcher trampoline selector (lea over `int NN; ret` table @0x257c8) | OBSERVED | disasm |
| 0x4e56c | C heap free-list head | OBSERVED | crash analysis of the A000h heap collision |
| 0x264fc | heap free-list walk (malloc path) | OBSERVED | ^ |
| — | game installs PM vectors 9, A, B, D, F, 71, 72 (no INT 8!) | OBSERVED | pm_vectors dump after boot |
| — | SPACE make/break 0x39/0xB9 via KBC advances title → gameplay; page flip display_start 0x0→0x4000 | OBSERVED | after_space.png |

## Per-frame logic island (recovered native, oracle-exact)

| Address | What | Status | Evidence |
|---|---|---|---|
| 0x118345 | `update_anim_timers` — bump frame tick, per object snap/advance accumulator | VERIFIED | `kegg/recovered/anim.py`; PMHookVerifier byte-exact |
| 0x1183b1 | `build_draw_list` — emit one draw command per sprite (X, W=coord_a>>4, H=coord_b>>4) | VERIFIED | `kegg/recovered/anim.py`; PMHookVerifier byte-exact |
| 0x1195ee | `load_current_object` — latch [0x14e158] sprite-def geometry (w/h/x/y) into draw-path globals | VERIFIED | `kegg/recovered/anim.py`; single-call + 40/40 full-run oracle-exact |
| 0x118004 | `setup_sprite_rect(out, def)` — place sprite def as current object (calls 0x1195ee), fold signed x/y offsets into out rect, derive right/bottom edges (w/h − 2) | VERIFIED | `kegg/recovered/anim.py`; single-call + 60/60 full-run oracle-exact |
| 0x11eda0 | `swap_ball_y` — flip the ball-Y double buffer ([0x147b20]↔[0x147b22] via scratch [0x147b16]) | VERIFIED | `kegg/recovered/physics.py`; 390/390 oracle-exact over the level-2 demo |
| 0x11b5df | `rects_overlap(a,b)` — AABB overlap test (4 signed edge compares → −1 hit / 0 miss); the collision primitive | VERIFIED | `kegg/recovered/physics.py`; 2364/2364 oracle-exact over the level-2 demo |
| 0x11b17e | `step_sequence(counter,cursor)` — tick a `{value,count}` record sequence; advance/reload on expiry, negative count = relative loop-back | VERIFIED | `kegg/recovered/sequence.py`; 2337/2337 oracle-exact over the level-2 demo |
| 0x11c886 | `swap_display_pages` — per-frame page flip ([0x14e2d4]↔[0x14e2d8] via scratch [0x14e2e8]) | VERIFIED | `kegg/recovered/present.py`; 390/390 oracle-exact over the level-2 demo |
| 0x11b57a | `set_clip_rect(x0,y0,x1,y1)` — normalize a two-corner box (signed order) → clip globals [0x14e219..0x14e225] | VERIFIED | `kegg/recovered/present.py`; 390/390 oracle-exact over the level-2 demo |
| 0x114291 | `remove_list_element` — compact the active brick list (dec count, shift tail down one 0x12 slot, dec index); calls memcpy 0x123f76 | VERIFIED (composition) | `kegg/recovered/collision.py`; 61/61 observable-state over the demo (non-leaf → composition verifier) |
| 0x147b16/18/20/22 | ball scratch-Y / X / Y-front / Y-back (16-bit) | RECOVERED | `kegg/bridge/ball_state.py`; 0x11eda0 + control_flow.md |
| 0x14e148 | live cell count (2× sprite count) | RECOVERED | data_model.md |
| 0x14e14c | frame tick | RECOVERED | ^ |
| 0x14e150 | object/cell table base | RECOVERED | ^ |
| 0x14e154 | world-X offset added to each sprite position | RECOVERED | ^ |
| 0x14e158 | current sprite-definition pointer | RECOVERED | 0x1195ee cross-ref (def +2 w, +4 h, +0xa x, +0xc y) |
| 0x14e15c/e, 0x14e160/2 | latched cur x_off / y_off / width / height (draw-path working globals) | RECOVERED | 0x1195ee |
| 0x14e2ec | draw-command output cursor (stride 0xA) | RECOVERED | 0x1183b1 |

## Notes

- Fixup census: 6292 × off32 (SRC_OFFSET32=0x07), 4 × sel16 (SRC_SELECTOR16=0x02).
  The 4 selector fixups are where flat CS/DS selectors get written; find and
  cross-check against DOS/4GW's real selector values when the CPU lands.
- Constant `0x50484152` ("RAPH") loaded at 0x2436e before the version check —
  likely a DOS/4GW / extender API signature. Confirm when tracing startup.
