"""Recovered rendering-island hooks for Krypton Egg.

The thin adapter over kegg.recovered.rle_blit: marshals VM state into the pure
RLE decoder and reproduces the blitter's full observable effect (planes,
registers, sequencer, scratch globals) so it verifies byte-exact against the
ASM oracle (pm_verification.PMHookVerifier).

The blitter at 0x1222D1 has three variants (see docs/kegg/rendering_island.md).
This installs the UNCLIPPED variant natively; the two clipped variants fall
back to the interpreter (correct, just not yet accelerated) until they are
recovered in turn.
"""
from __future__ import annotations

from kegg.recovered.rle_blit import decode_plane_pass, NO_CLIP

BLIT = 0x1222D1

# Scratch globals (runtime flat addresses; ds base 0).
G_376 = 0x148376   # per-plane offset-table index (steps -2/pass)
G_378 = 0x148378   # preamble skip-row count
G_380 = 0x148380   # vertical-clip flag
G_388 = 0x148388   # horizontal-clip width
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
            if not (al & 0x80):            # copy run: skip its source
                esi += al
    return esi, al


def blit_1222d1(cpu):
    mem = cpu.mem
    r = cpu.r
    d = mem.data
    if mem.r32(G_380) != 0 or (mem.r32(G_388) & 0xFFFF) != 0:
        _run_original(cpu)                 # clipped variants -> interpreter
        return

    entry_edi, entry_ebx, entry_ebp, entry_esi = r[7], r[3], r[5], r[6]
    phase = entry_edi & 3
    edi_flat = entry_edi >> 2
    mask0 = (0x11 << phase) & 0xFF          # rol(0x11, phase); phase<4 never wraps
    d[G_3A4] = mask0
    d[G_3A5] = mask0
    rows = entry_ebp                        # neg ebp then inc-to-zero => rows == ebp
    d[G_376] = 0x0A                          # low byte; the ASM writes the word 0x000A
    d[G_376 + 1] = 0x00
    src = d

    mask = mask0
    ebx = entry_ebx
    eax = 0
    ecx = 0
    stride = 0
    passes = 0
    ebp_neg = (-entry_ebp) & 0xFFFFFFFF
    while True:
        # The ASM saves ebx/ebp/esi/edi on the stack each pass and restores
        # them after; the pushed bytes remain below esp (the oracle diffs
        # them).  Reproduce the push/pop so the scratch stack matches.
        cpu.push(ebx, 4); cpu.push(ebp_neg, 4)
        cpu.push(entry_esi, 4); cpu.push(edi_flat, 4)
        # sequencer map mask for this plane
        cpu.mem.vga.map_mask = mask & 0x0F
        cpu.mem.vga.seq_index = 2
        # preamble: index the per-plane offset table, advance esi to this plane
        idx = mem.r16(G_376)
        esi = (entry_esi - idx) & 0xFFFFFFFF
        ax = (idx + mem.r16(esi)) & 0xFFFF
        esi = (esi + ax) & 0xFFFFFFFF
        mem.w16(G_376, (mem.r16(G_376) - 2) & 0xFFFF)
        # preamble skip
        skip = mem.r32(G_378)
        eax = 0
        if skip:
            esi, eax = _skip_rows(src, esi, skip)
        # main decode into this plane
        stride = (mem.r32(SCREEN_W) - ebx) >> 2
        mem.w32(G_36C, stride)
        plane = cpu.mem.vga.planes[(mask & 0x0F).bit_length() - 1]
        off = edi_flat - APERTURE
        _, _, ecx = decode_plane_pass(plane, src, esi, off, rows, stride,
                                      NO_CLIP, accumulate=True)
        passes += 1
        for _ in range(4):                 # pop edi/esi/ebp/ebx (restore esp)
            cpu.pop(4)
        # epilogue: dec ebx; rotate mask; carry bumps the column
        ebx = (ebx - 1) & 0xFFFFFFFF
        carry = mask >> 7
        mask = ((mask << 1) | carry) & 0xFF
        edi_flat = (edi_flat + carry) & 0xFFFFFFFF
        d[G_3A4] = mask
        if mask == mask0:
            break

    # exit registers (see docs/kegg/rendering_island.md)
    r[0] = eax & 0xFFFFFFFF                                  # eax: last preamble al
    r[1] = ecx & 0xFFFFFFFF                                  # ecx: last run residual
    r[2] = (stride & 0xFFFFFF00) | mask0                     # edx: stride, dl<-final mask
    r[3] = ebx                                               # ebx: entry - passes
    r[5] = (-entry_ebp) & 0xFFFFFFFF                         # ebp: negated row count
    r[6] = entry_esi                                         # esi: restored
    r[7] = edi_flat                                          # edi: flat ptr + carries
    cpu._flags_sub(mask0, mask0, 0, 8)                       # flags: the final equal cmp
    cpu.eip = cpu.pop(4)                                     # RET


def install_render_hooks(cpu) -> int:
    cpu.replacement_hooks[BLIT] = blit_1222d1
    cpu.hook_names[BLIT] = "blit_1222d1"
    return 1
