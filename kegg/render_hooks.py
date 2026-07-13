"""Recovered rendering-island hooks for Krypton Egg.

The thin adapter over kegg.recovered.rle_blit: marshals VM state into the pure
RLE decoder and reproduces the blitter's full observable effect (planes,
registers, sequencer, scratch globals, stack scratch) so it verifies
byte-exact against the ASM oracle (pm_verification.PMHookVerifier).

The blitter at 0x1222D1 has three variants (docs/kegg/rendering_island.md).
UNCLIPPED and HORIZONTAL-CLIP are recovered natively here; VERTICAL-CLIP falls
back to the interpreter until it is recovered in turn.
"""
from __future__ import annotations

from kegg.recovered.rle_blit import decode_plane_pass, NO_CLIP

BLIT = 0x1222D1

# Scratch globals (runtime flat addresses; ds base 0).
G_376 = 0x148376   # per-plane offset-table index (steps -2/pass)
G_378 = 0x148378   # preamble skip-row count
G_380 = 0x148380   # vertical-clip flag
G_388 = 0x148388   # horizontal-clip width (current pass)
G_390 = 0x148390   # h-clip working width (steps -1/pass)
G_36C = 0x14836C   # row stride
G_3A4 = 0x1483A4   # rotating map mask
G_3A5 = 0x1483A5   # mask start copy (loop terminator)
SCREEN_W = 0x14E35E
APERTURE = 0xA0000


def _run_original(cpu):
    """Interpreter fallback: run the real routine to its RET, hook removed."""
    hook = cpu.replacement_hooks.pop(BLIT, None)
    try:
        ret = cpu.mem.r32(cpu.r[4])
        tgt = cpu.r[4] + 4
        while not (cpu.eip == ret and cpu.r[4] >= tgt):
            cpu.step()
    finally:
        if hook is not None:
            cpu.replacement_hooks[BLIT] = hook


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
        _run_original(cpu)                  # vertical-clip -> interpreter (not yet recovered)
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


def install_render_hooks(cpu) -> int:
    cpu.replacement_hooks[BLIT] = blit_1222d1
    cpu.hook_names[BLIT] = "blit_1222d1"
    return 1
