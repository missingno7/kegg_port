"""Krypton Egg Mode X sprite RLE decode — the rendering island's core.

Recovered from the sprite blitter at (link) 0x22362/0x22539/0x223b9 — a
Mode X planar blitter that draws each sprite in four passes (one per plane),
RLE-decoding a per-plane byte stream into that plane's linear space.

The stream is a sequence of ROWS.  Each row: a one-byte segment count, then
that many SEGMENTS.  A segment's count byte ``c``:
  * bit 7 set  -> SKIP: advance the destination by ``(-c) & 0xFF`` pixels
    (transparent gap), consuming no source.
  * bit 7 clear -> COPY: ``c`` source bytes to the destination, optionally
    right-clipped at ``clip_w`` columns from the row start.

Pure: operates on a plane bytearray + the source bytes.  The adapter hook
supplies the plane, source offset, per-row destination offset/stride and the
clip width; here there is no VM, no segment:offset, no dos_re.
"""
from __future__ import annotations


def decode_row(plane: bytearray, src, esi: int, dst: int, row_x0: int,
               clip_w: int) -> tuple[int, int]:
    """Decode one sprite row into ``plane``.

    ``dst``/``row_x0`` are plane-relative byte offsets (dst == row_x0 at the
    row start); ``clip_w`` right-clips copies at ``row_x0 + clip_w`` (use a
    large value for the unclipped variant).  Returns (new esi, dst past row).
    """
    nseg = src[esi]
    esi += 1
    for _ in range(nseg):
        c = src[esi]
        esi += 1
        if c & 0x80:                       # SKIP run (transparent)
            dst += (-c) & 0xFF
            continue
        over = (dst - row_x0) - clip_w      # >=0 once we're at/right of the clip
        if over >= 0:                       # whole run past the right edge
            esi += c
            continue
        over += c
        if over < 0:                        # run fits entirely before the clip
            over = 0
        else:                               # partial: copy up to the clip
            c -= over
        plane[dst:dst + c] = src[esi:esi + c]
        dst += c
        esi += c + over                     # source: c copied + over clipped away
    return esi, dst


def decode_plane_pass(plane: bytearray, src, esi: int, dst0: int, rows: int,
                      stride: int, clip_w: int) -> int:
    """Decode ``rows`` rows into one plane, stepping ``stride`` bytes per row.

    ``dst0`` is the plane-relative offset of the first row.  Returns the new
    source offset.  (The dest never carries between rows — each row restarts
    from ``dst0 + row*stride`` — matching the ASM's ``mov edi,edx``.)
    """
    for row in range(rows):
        base = dst0 + row * stride
        esi, _ = decode_row(plane, src, esi, base, base, clip_w)
    return esi
