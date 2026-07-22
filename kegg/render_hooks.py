"""Recovered rendering-island CPU adapters for Krypton Egg.

These functions are the *backend adapters* of the rendering overrides declared
in ``kegg.overrides``; the execution plan installs them into
``cpu.replacement_hooks`` via ``bind_execution_plan`` (there is no eager
install).  Each is the thin adapter over ``kegg.recovered.rle_blit``: it
marshals VM state into the pure RLE decoder and reproduces the blitter's full
observable effect (planes, registers, sequencer, scratch globals, stack
scratch) so it verifies byte-exact against the ASM oracle
(``pm_verification.PMHookVerifier``).

The blitter at 0x1222D1 has three variants (docs/kegg/rendering_island.md).
UNCLIPPED and HORIZONTAL-CLIP are recovered natively here; VERTICAL-CLIP falls
back to the interpreter until it is recovered in turn.
"""
from __future__ import annotations

from kegg.recovered.rle_blit import (decode_plane_pass,
                                      decode_plane_pass_leftclip, NO_CLIP)

BLIT = 0x1222D1

# Scratch globals (runtime flat addresses; ds base 0).
G_376 = 0x148376   # per-plane offset-table index (steps -2/pass)
G_378 = 0x148378   # preamble skip-row count
G_380 = 0x148380   # vertical-clip flag / left shift (>>2 at v-clip entry)
G_388 = 0x148388   # horizontal-clip width (current pass)
G_38C = 0x14838C   # v-clip plane phase (0..3, indexes the offset table)
G_390 = 0x148390   # h-clip working width (steps -1/pass)
G_36C = 0x14836C   # row stride
G_3A4 = 0x1483A4   # rotating map mask
G_3A5 = 0x1483A5   # mask start copy (loop terminator)
SCREEN_W = 0x14E35E
APERTURE = 0xA0000

BLIT2 = 0x1225FF   # RLE masked page-to-page copy (restore background under sprites)
BLIT_QUEUE = 0x122288   # deferred-draw queue writer, falls into the blitter
G_2E0 = 0x14E2E0   # source page base (logical)
G_2E4 = 0x14E2E4   # dest page base (logical)
G_370 = 0x148370   # page delta (source - dest), added before the /4 addressing


def _sar(v, n):
    """Arithmetic right shift of a 32-bit value read unsigned."""
    if v & 0x80000000:
        v -= 0x100000000
    return v >> n


def _skip_rows(src, esi, nrows):
    """Preamble: advance esi past `nrows` rows' copy-run source.  Returns
    (esi, last al) — the last byte loaded, which the ASM leaves in AL."""
    al = 0
    for _ in range(nrows):
        segn = src[esi]; esi += 1
        for _ in range(segn):
            al = src[esi]; esi += 1
            if not (al & 0x80):
                esi += al
    return esi, al


def blit_1222d1(cpu):
    mem = cpu.mem
    r = cpu.r
    d = mem.data
    if mem.r32(G_380) != 0:
        _blit_vclip(cpu)
        return
    hclip = mem.r32(G_388) != 0             # ASM: cmp dword [0x148388],0 (full 32-bit)

    entry_edi, entry_ebx, entry_ebp, entry_esi = r[7], r[3], r[5], r[6]
    phase = entry_edi & 3
    edi_flat = entry_edi >> 2
    mask0 = (0x11 << phase) & 0xFF           # rol(0x11, phase); phase<4 never wraps
    d[G_3A4] = mask0
    d[G_3A5] = mask0
    rows = entry_ebp                         # neg ebp then inc-to-zero => rows == ebp
    d[G_376] = 0x0A
    d[G_376 + 1] = 0x00
    if hclip:
        mem.w32(G_390, mem.r32(G_388))       # working clip width starts at the entry width
    src = d
    screen = mem.r32(SCREEN_W)

    mask = mask0
    ebx = entry_ebx
    ebp_neg = (-entry_ebp) & 0xFFFFFFFF
    eax = ecx = 0
    edx = 0
    while True:
        cpu.push(ebx, 4); cpu.push(ebp_neg, 4)
        cpu.push(entry_esi, 4); cpu.push(edi_flat, 4)
        cpu.mem.vga.map_mask = mask & 0x0F
        cpu.mem.vga.seq_index = 2
        # preamble: index the per-plane offset table, advance esi to this plane
        idx = mem.r16(G_376)
        esi = (entry_esi - idx) & 0xFFFFFFFF
        ax = (idx + mem.r16(esi)) & 0xFFFF
        esi = (esi + ax) & 0xFFFFFFFF
        mem.w16(G_376, (mem.r16(G_376) - 2) & 0xFFFF)
        skip = mem.r32(G_378)
        eax = 0
        if skip:
            esi, eax = _skip_rows(src, esi, skip)
        # per-variant stride + clip
        if hclip:
            # clip = (working_width + 3) >> 2, ASM `add edx,3; sar edx,2` — an
            # ARITHMETIC shift: [0x148390] steps below zero on tall sprites and
            # must sign-extend ((-1+3)>>2 == 0, not (0xFFFFFFFF+3)>>2).
            w390 = mem.r32(G_390)
            if w390 & 0x80000000:
                w390 -= 0x100000000
            clip = (w390 + 3) >> 2
            mem.w32(G_388, clip & 0xFFFFFFFF)
            mem.w32(G_390, (w390 - 1) & 0xFFFFFFFF)
            stride = screen >> 2
            accumulate = False
        else:
            clip = NO_CLIP
            stride = (screen - ebx) >> 2
            accumulate = True
        mem.w32(G_36C, stride)
        off = edi_flat - APERTURE
        _, _, ecx = decode_plane_pass(cpu.mem.vga.planes[(mask & 0x0F).bit_length() - 1],
                                      src, esi, off, rows, stride, clip, accumulate)
        # edx at pass end: the ASM keeps it as the stride (unclipped, accumulate
        # model) or the row cursor one row past the last (reset model).
        edx = stride if accumulate else (APERTURE + off + rows * stride)
        for _ in range(4):
            cpu.pop(4)
        if not hclip:
            ebx = (ebx - 1) & 0xFFFFFFFF      # unclipped decrements ebx per pass
        carry = mask >> 7
        mask = ((mask << 1) | carry) & 0xFF
        edi_flat = (edi_flat + carry) & 0xFFFFFFFF
        d[G_3A4] = mask
        if mask == mask0:
            break

    # eax at exit: the h-clip decode zeroes it (`sub eax,eax` per segment); the
    # unclipped decode leaves the preamble's last byte untouched.
    r[0] = 0 if hclip else (eax & 0xFFFFFFFF)
    r[1] = ecx & 0xFFFFFFFF
    r[2] = (edx & 0xFFFFFF00) | mask0         # dl <- final mask
    r[3] = ebx
    r[5] = ebp_neg
    r[6] = entry_esi
    r[7] = edi_flat
    cpu._flags_sub(mask0, mask0, 0, 8)
    cpu.eip = cpu.pop(4)


def _blit_vclip(cpu):
    """Vertical-clip variant (0x1223B9): left-edge shift model.

    Entry splits the clip word into a plane phase ([0x14838c] = v&3) and a
    left shift ([0x148380] = v>>2, arithmetic); the offset-table preamble is
    indexed by the phase; each pass's rows are shifted left by the shift and
    clipped at the visible edge; the phase advances 0->3 per pass, bumping the
    shift on wrap.  No `dec ebx`; row-reset stride model.
    """
    mem = cpu.mem
    r = cpu.r
    d = mem.data
    entry_edi, entry_ebx, entry_ebp, entry_esi = r[7], r[3], r[5], r[6]
    v380 = mem.r32(G_380)
    mem.w32(G_38C, v380 & 3)
    mem.w32(G_380, _sar(v380, 2) & 0xFFFFFFFF)
    stride = _sar(mem.r32(SCREEN_W), 2)
    mem.w32(G_36C, stride & 0xFFFFFFFF)
    phase = entry_edi & 3
    edi_flat = entry_edi >> 2
    mask0 = (0x11 << phase) & 0xFF
    d[G_3A4] = mask0
    d[G_3A5] = mask0
    rows = entry_ebp
    src = d

    mask = mask0
    ecx = 0
    edx = 0
    while True:
        cpu.push(entry_ebx, 4); cpu.push((-entry_ebp) & 0xFFFFFFFF, 4)
        cpu.push(entry_esi, 4); cpu.push(edi_flat, 4)
        cpu.mem.vga.map_mask = mask & 0x0F
        cpu.mem.vga.seq_index = 2
        # preamble: index the offset table by the plane phase [0x14838c]
        idx = (-5 + mem.r32(G_38C))
        tbl = (entry_esi + ((idx * 2) & 0xFFFFFFFF)) & 0xFFFFFFFF
        esi = (entry_esi + mem.r16(tbl)) & 0xFFFFFFFF
        skip = mem.r32(G_378)
        if skip:
            esi, _ = _skip_rows(src, esi, skip)
        shift = mem.r32(G_380)
        off = edi_flat - APERTURE
        plane = cpu.mem.vga.planes[(mask & 0x0F).bit_length() - 1]
        esi, ecx = decode_plane_pass_leftclip(plane, src, esi, off, rows, stride, shift)
        edx = APERTURE + off + rows * stride
        for _ in range(4):
            cpu.pop(4)
        # per-pass phase advance: 0..3, wrap bumps the shift
        ph = (mem.r32(G_38C) + 1) & 0xFFFFFFFF
        if ph == 4:
            ph = 0
            mem.w32(G_380, (mem.r32(G_380) + 1) & 0xFFFFFFFF)
        mem.w32(G_38C, ph)
        carry = mask >> 7
        mask = ((mask << 1) | carry) & 0xFF
        edi_flat = (edi_flat + carry) & 0xFFFFFFFF
        d[G_3A4] = mask
        if mask == mask0:
            break

    r[0] = 0
    r[1] = ecx & 0xFFFFFFFF
    r[2] = (edx & 0xFFFFFF00) | mask0
    r[3] = entry_ebx
    r[5] = (-entry_ebp) & 0xFFFFFFFF
    r[6] = entry_esi
    r[7] = edi_flat
    cpu._flags_sub(mask0, mask0, 0, 8)
    cpu.eip = cpu.pop(4)


def blit_queue_entry_122288(cpu):
    """Deferred-draw queue writer (0x122288) + the blitter it falls into.

    The original writes a 0x14-byte draw record (bump-allocated at
    [0x148360]) and falls straight into the sprite blitter at 0x1222D1.  The
    old composition left this prologue INTERPRETED on purpose (harmless on
    PyPy); on CPython its ~273 dispatched instructions per blit are the
    single largest remaining frame cost, so the whole entry is one native
    operation now: the record write below (from the oracle-verified
    lift_122288 prologue, 0x122288..0x1222D0), then the recovered blitter,
    which reproduces the full register/flag/memory exit itself.
    """
    mem = cpu.mem
    r = cpu.r
    rec = mem.r32(0x148360)
    mem.w32(0x148360, (rec + 0x14) & 0xFFFFFFFF)
    mem.w16(rec, 0x5)                              # record type
    mem.w16(rec + 0x4, r[3] & 0xFFFF)              # bx
    mem.w16(rec + 0x2, r[5] & 0xFFFF)              # bp
    mem.w32(rec + 0x6, (mem.r16((r[6] - 2) & 0xFFFFFFFF) + r[6]) & 0xFFFFFFFF)
    mem.w32(rec + 0xA, (r[7] - mem.r32(G_2E4)) & 0xFFFFFFFF)
    mem.w16(rec + 0xE, mem.r32(G_380) & 0xFFFF)    # v-clip
    mem.w16(rec + 0x10, mem.r32(G_388) & 0xFFFF)   # h-clip
    mem.w16(rec + 0x12, mem.r32(G_378) & 0xFFFF)   # skip rows
    blit_1222d1(cpu)


def blit2_1225ff(cpu):
    """RLE masked page-to-page copy (0x1225FF) — the sprite-erase blitter.

    Reads a sprite descriptor at ebx (+2 height, +6 source RLE stream, +0xa
    dest offset, +0x12 preamble-skip count) and copies its non-transparent
    runs from the source page to the dest page in Mode X logical addressing
    (aperture offset = logical>>2), gated by the RLE mask.  The pixel copies
    run through cpu.mem so the plane/latch/map-mask semantics are identical to
    the interpreter by construction.  Reproduces the full register/global exit.
    """
    mem = cpu.mem
    r = cpu.r
    d = mem.data
    struct_ptr = r[3]
    entry_edx = r[2]                                 # only dx (low 16) is written; high half survives
    page_dst = mem.r32(G_2E4)
    page_src = mem.r32(G_2E0)
    delta = (page_src - page_dst) & 0xFFFFFFFF
    mem.w32(G_370, delta)
    ebp = (mem.r32(struct_ptr + 0xA) + page_dst) & 0xFFFFFFFF
    dl = (-mem.r16(struct_ptr + 2)) & 0xFF          # row counter (inc -> 0)
    esi = mem.r32(struct_ptr + 6)
    screen = mem.r32(SCREEN_W)

    # preamble: skip [ebx+0x12] leading runs (advance the source cursor)
    eax = 0
    for _ in range(mem.r16(struct_ptr + 0x12)):
        eax = d[esi]
        esi = (esi + 1 + eax) & 0xFFFFFFFF

    cur = esi                                        # ebx is reused as the source cursor
    ecx = edi = 0
    while True:                                      # row loop (dl -> 0)
        ecx = ebp
        dh = (-d[cur]) & 0xFF                        # segment count for this row
        cur = (cur + 1) & 0xFFFFFFFF
        while True:                                  # segment loop (dh -> 0)
            al = d[cur]
            cur = (cur + 1) & 0xFFFFFFFF
            if al & 0x80:                            # SKIP run (transparent)
                ecx = (ecx + ((-al) & 0xFF)) & 0xFFFFFFFF
                eax = (-al) & 0xFF
            else:                                    # COPY run through the aperture
                edi = ecx
                n = ((ecx & 3) + al + 3) >> 2
                eax = (al + edi) & 0xFFFFFFFF
                src_ap = ((delta + edi) & 0xFFFFFFFF) >> 2
                dst_ap = edi >> 2
                vga = mem.vga
                if (vga is not None and 0xA0000 <= src_ap and src_ap + n <= 0xB0000
                        and 0xA0000 <= dst_ap and dst_ap + n <= 0xB0000):
                    # One slice op per run instead of n round-trips through the
                    # aperture model — byte-exact (vga.bulk_copy) and the
                    # difference between 5 fps and playable on CPython.
                    vga.bulk_copy(src_ap - 0xA0000, dst_ap - 0xA0000, n)
                else:
                    for i in range(n):
                        mem.w8((dst_ap + i) & 0xFFFFFFFF, mem.r8((src_ap + i) & 0xFFFFFFFF))
                esi = (src_ap + n) & 0xFFFFFFFF
                edi = (dst_ap + n) & 0xFFFFFFFF
                ecx = eax                            # xchg: dest advances by the run
                eax = 0
            dh = (dh + 1) & 0xFF
            if dh == 0:
                break
        ebp = (ebp + screen) & 0xFFFFFFFF
        dl = (dl + 1) & 0xFF
        if dl == 0:
            break

    r[0] = 0
    r[1] = ecx & 0xFFFFFFFF
    r[2] = entry_edx & 0xFFFF0000                    # edx: dl=dh=0, high 16 unchanged from entry
    r[3] = cur
    r[5] = ebp
    r[6] = esi
    r[7] = edi
    cpu._flags_add((dl - 1) & 0xFF, 1, 0, 8)
    cpu.eip = cpu.pop(4)
