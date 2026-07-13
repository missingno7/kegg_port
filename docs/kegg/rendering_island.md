# The rendering island — recovery map

All gameplay time is one routine: the Mode X sprite blitter at link
**0x22362 / 0x22539 / 0x223b9** (runtime +0x100000).  It draws a sprite in
four passes (one per plane), RLE-decoding a per-plane byte stream into that
plane's linear space.  Dispatched via draw-function pointers at 0x1483FE/
0x148402 (no direct callers).

## Status

- **Literal lift installed** (`kegg/lifted32/`): +2.5x, ORACLE_PASSING, shipped
  and on by default in `create_game_runtime`.
- **Core primitive recovered** (`kegg/recovered/rle_blit.py`): `decode_row` /
  `decode_plane_pass` — pure native RLE decode, unit-tested and validated
  byte-for-byte against the interpreted blitter on the gameplay snapshot
  (`tests/test_rle_blit.py`).
- **Next slice:** compose the full recovered blitter behind a hook (below).

## The RLE stream format (shared by all variants)

A sprite is stored as four plane streams (a small per-plane offset table at
the sprite header; the blitter's preamble indexes it with [0x148376], which
steps 0x0A -> 8 -> 6 -> 4 across the four passes).  Each plane stream is a
sequence of ROWS; each row = a one-byte segment count then that many
segments.  A segment's count byte `c`:
  * bit 7 set  -> SKIP `(-c)&0xFF` destination pixels (transparent), no source.
  * bit 7 clear -> COPY `c` source bytes (word-aligned movsb/movsw/movsb; the
    alignment is a speed trick, the net effect is `c` contiguous bytes),
    right-clipped at `clip_w` columns from the row start.

Rows do not carry the destination between them: each row restarts at
`row_start + row*stride` (`mov edi,edx` in the ASM).  `stride = ([0x14e35e]
- ebx) >> 2` (unclipped) or `[0x14e35e] >> 2` (clipped) — the per-plane row
pitch (screen width / 4).

## The three variants (dispatch in entry block 0x1222D1)

| Selector | Path | What differs |
|---|---|---|
| `[0x148380] != 0` | vertical-clip (0x223b9) | preamble skips leading off-top rows; row count from clipped height |
| `[0x148380]==0 && [0x148388]!=0` | horizontal-clip (0x22539) | per-run right clip at `[0x148388]` columns; clipped-tail source consumed but not written (`decode_row`'s `clip_w`) |
| both 0 | unclipped (0x22305) | no clip (`clip_w = infinity`); fastest inner loop (0x122362) |

All three: entry packs `edi = (VGA_flat_ptr << 2) | phase`; `phase = edi & 3`;
map mask = `rol(0x11, phase)` stored at [0x1483A4]/[0x1483A5]; four passes
rotate the mask (2->4->8->1) with `adc edi,0` bumping the byte column on wrap;
`ebp` = negated row count; esi/edi are pushed/popped around each plane pass
(so final esi == entry esi).

## Scratch globals the oracle diffs (a full hook must reproduce these)

0x148376 (per-plane offset index, steps -2/pass), 0x148378 (preamble skip
count), 0x148380 (v-clip flag), 0x148388/0x148390 (h-clip width + working
copy), 0x14836C (row stride), 0x14838C (v-clip scanline counter, 4-pass wrap),
0x1483A4/0x1483A5 (rotating mask + its start copy), 0x148360 (draw-queue
cursor, for the 0x122288 entry).

## Composing the recovered hook (the next slice)

A `kegg/` hook (dos_re-aware) that: reads the entry state, dispatches on the
two flags, runs the preamble + four `decode_plane_pass` calls against
`cpu.mem.vga.planes` (map-mask -> plane index), then writes back the final
register values, the sequencer state, and every scratch global above.  Verify
with `pm_verification.PMHookVerifier`; iterate on any diverging global.  Risk
is the global bookkeeping, not the pixels (the pixels are proven) — so build
it flag-path by flag-path, each verified before the next, falling back to the
interpreter for any path not yet reproduced.

## The second blitter — 0x1225FF (masked page-to-page copy)

The sprite-erase pass (~61% of gameplay after the main blitter is hooked):
copies non-transparent runs from the source page to the dest page in Mode X
logical addressing (aperture offset = logical>>2), gated by the same RLE
mask.  Reads a sprite descriptor at `ebx`: +2 height, +6 source RLE stream,
+0xa dest offset, +0x12 preamble-skip count.  Pages come from [0x14e2e0]
(source) / [0x14e2e4] (dest); the delta [0x148370] = source - dest is added
before the >>2.  No sequencer writes — it copies through the ambient map mask
(the pixel copies go through cpu.mem so the plane/latch semantics are exact).

Register exit subtleties: edx keeps its entry high 16 bits (`mov dx` writes
only the low half; dl/dh both reach 0); esi/edi end as the last run's aperture
addresses (src/dst + run bytes); ecx = last dest logical; ebx = final source
cursor; ebp = last row base + screen width.

RECOVERED in `kegg/render_hooks.py::blit2_1225ff`.
