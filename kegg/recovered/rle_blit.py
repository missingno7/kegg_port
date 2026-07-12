"""Krypton Egg Mode X sprite RLE decode -- the rendering island's core.

Recovered from the sprite blitter at (link) 0x22362/0x22539/0x223b9 -- a
Mode X planar blitter that draws each sprite in four passes (one per plane),
RLE-decoding a per-plane byte stream into that plane's linear space.

The stream is a sequence of ROWS.  Each row: a one-byte segment count, then
that many SEGMENTS.  A segment's count byte `c`:
  * bit 7 set  -> SKIP: advance the destination by `(-c) & 0xFF` pixels
    (transparent gap), consuming no source.
  * bit 7 clear -> COPY: `c` source bytes to the destination, optionally
    right-clipped at `clip_w` columns from the row start.

Pure: operates on a plane bytearray + the source bytes.  The adapter hook
supplies the plane, source offset, per-row destination offset/stride and the
clip width; here there is no VM, no segment:offset, no dos_re.

`decode_row` also returns the final `ecx` the ASM inner loop leaves (the last
segment's residual run length), which the hook needs to reproduce the
blitter's exit registers byte-exactly.
"""
from __future__ import annotations

NO_CLIP = 1 << 30      # clip_w for the unclipped variant (never truncates)


def decode_row(plane, src, esi, dst, row_x0, clip_w):
    """Decode one sprite row into `plane`.

    `dst`/`row_x0` are plane-relative byte offsets (dst == row_x0 at the row
    start); `clip_w` right-clips copies at `row_x0 + clip_w`.  Returns
    (new esi, dst past row, last ecx).
    """
    nseg = src[esi]
    esi += 1
    ecx = 0
    for _ in range(nseg):
        c = src[esi]
        esi += 1
        if c & 0x80:                       # SKIP run (transparent)
            skip = (-c) & 0xFF
            dst += skip
            ecx = skip
            continue
        over = (dst - row_x0) - clip_w      # >=0 once we are at/right of the clip
        if over >= 0:                       # whole run past the right edge
            esi += c
            ecx = c
            continue
        over += c
        if over < 0:                        # run fits entirely before the clip
            over = 0
        else:                               # partial: copy up to the clip
            c -= over
        plane[dst:dst + c] = src[esi:esi + c]
        dst += c
        esi += c + over                     # source: c copied + over clipped away
        ecx = 0                             # rep movsw exhausts CX
    return esi, dst, ecx


def decode_plane_pass(plane, src, esi, dst0, rows, stride, clip_w, accumulate):
    """Decode `rows` rows into one plane.

    `accumulate` picks the row-stepping model: True (unclipped variant) walks
    the destination forward `+= stride` after each row's segments
    (`add edi,edx`); False (clipped variants) restarts each row at
    `dst0 + row*stride` (`mov edi,edx`).  Returns (new esi, final dst,
    last ecx).
    """
    ecx = 0
    dst = dst0
    for row in range(rows):
        if accumulate:
            base = dst
        else:
            base = dst0 + row * stride
            dst = base
        esi, dst, ecx = decode_row(plane, src, esi, dst, base, clip_w)
        if accumulate:
            dst += stride
    return esi, dst, ecx
