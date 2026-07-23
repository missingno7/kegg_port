"""Recovered asset-unpacker CPU adapters for Krypton Egg.

The backend adapters of the asset-loader overrides declared in
``kegg.overrides``; the execution plan installs them into
``cpu.replacement_hooks`` via ``bind_execution_plan`` (no eager install).

``gif_decode_121df8`` is the adapter over ``kegg.recovered.gif.decode_gif`` —
KE's GIF87a title/menu/score image unpacker, the single hottest asset-load
routine (~3.86M interpreted instructions per screen).  The pure decoder does
every memory effect; the adapter marshals the four cdecl stack arguments and
reproduces the routine's ``pushad``/``popad`` register frame and internal
pushes so the sub-esp stack scratch matches the ASM oracle byte-for-byte
(``pm_verification.PMHookVerifier`` diffs the whole machine).
"""
from __future__ import annotations

from kegg.recovered.gif import decode_gif
from kegg.recovered.present import (DAC_MAX, deinterleave_plane,
                                    fade_palette_stream)

GIF_DECODE = 0x121DF8
PALETTE_FADE = 0x123A48
PLANAR_UPLOAD = 0x122F30

DAC_INDEX_PORT = 0x3C8
DAC_DATA_PORT = 0x3C9
GC_INDEX_PORT = 0x3CE            # graphics controller index/data (16-bit out)
SEQ_INDEX_PORT = 0x3C4           # sequencer index/data (16-bit out)
G_GC_MODE = 0x14E384             # shadow of GC register 5 (skips redundant I/O)
G_MAP_MASK = 0x14E385            # shadow of the sequencer map mask
APERTURE = 0xA0000
APERTURE_END = 0xB0000


def gif_decode_121df8(cpu):
    """Adapter for the GIF decoder at 0x121DF8.

    cdecl(src, dst, result_desc, scratch); the routine ``pushad``s on entry and
    ``popad``s before ``ret``, so every register is restored to its entry value
    and only EAX changes (to the status word).  The stack below the caller's
    return address is decoder scratch: the pushad frame plus a ``push ebp``
    (bb17) and the deepest ``push ecx`` in the decode loop, left dead but
    diffed by the verifier — so we replay them with the real ECX value.
    """
    mem = cpu.mem
    r = cpu.r
    ds = cpu.sbase["ds"]
    esp0 = r[4]
    src = mem.r32(esp0 + 4)
    dst = mem.r32(esp0 + 8)
    desc = mem.r32(esp0 + 0xC)
    scratch = mem.r32(esp0 + 0x10)
    frame = (esp0 - 4) & 0xFFFFFFFF          # ebp = [esp_after_pushad + 0x1C]

    # All memory effects (pixels, 6-bit palette, descriptor, size accumulator,
    # de-blocked source, LZW scratch tables + reversal stack).
    status, ecx_final, last_gct = decode_gif(mem.data, ds, src, dst, desc, scratch)

    # Reproduce the sub-esp stack scratch exactly.  pushad writes the entry
    # registers at [esp0-32, esp0); the deepest live pushes leave ebp (the
    # frame pointer) at [esp0-36) and the final loop ECX at [esp0-40).
    cpu._pusha(4)
    cpu.push(frame, 4)
    cpu.push(ecx_final & 0xFFFFFFFF, 4)
    cpu.pop(4)
    cpu.pop(4)
    cpu._popa(4)                              # restores the entry registers
    # Exit flags == those of the routine's final `shr al,2` in the palette loop;
    # reproduce them with the CPU's own shift for the exact flag model.
    cpu.set_reg(0, 1, last_gct & 0xFF)
    cpu._shift(5, True, 0, 1, 2)              # shr al,2 -> sets ZF/PF/CF/SF
    r[0] = status & 0xFFFFFFFF               # movzx eax, word [0x148355]
    cpu.eip = cpu.pop(4)                      # ret


def palette_fade_123a48(cpu):
    """Adapter for the VGA palette fade at 0x123A48.

    cdecl(src, start_index, entries, fade): programs the DAC write index, then
    streams ``entries*3`` components, each ``src[i] - fade`` clamped to 0..0x3F,
    to the DAC data port.  KE runs this once per frame through a title/menu
    fade, so it is the largest interpreted cost left in the image-display path.

    Like the GIF decoder it is a pushad/popad routine with no internal pushes,
    so every register is restored and only the stack's pushad frame and the
    exit flags need reproducing.
    """
    mem = cpu.mem
    r = cpu.r
    ds = cpu.sbase["ds"]
    esp0 = r[4]
    src = mem.r32(esp0 + 4)
    start = mem.r32(esp0 + 8)
    entries = mem.r32(esp0 + 0xC)
    fade = mem.r32(esp0 + 0x10)

    count = (entries * 3) & 0xFFFFFFFF        # edi=arg2; ebx+=ebx; edi+=ebx => 3*arg2
    stream, low, last = fade_palette_stream(mem.data, ds + src, count, fade, start)

    write = cpu.port_writer
    if write is not None:
        write(cpu, DAC_INDEX_PORT, start & 0xFF, 8)
        for b in stream:
            write(cpu, DAC_DATA_PORT, b, 8)

    # Stack scratch: pushad only (no pushes inside the loop).
    cpu._pusha(4)
    cpu._popa(4)
    # Exit flags come from the LAST component's compare: the negative branch
    # ends on `sub eax,eax`, otherwise on `cmp eax,0x3F`.
    if count:
        if low:
            cpu._flags_sub(last, last, 0, 32)
        else:
            # NB: the raw (unmasked) difference — _flags_sub derives CF from it
            # going negative, exactly as the emitted `cmp` bodies pass it.
            cpu._flags_sub(last, DAC_MAX, last - DAC_MAX, 32)
    cpu.eip = cpu.pop(4)                      # ret


def planar_upload_122f30(cpu):
    """Adapter for the linear -> Mode X planar upload at 0x122F30.

    cdecl(src, dst, count): de-interleaves ``count`` linear bytes into the four
    VGA planes at aperture address ``dst`` — plane ``p`` takes source bytes
    ``p, p+4, p+8, ...``, ``count>>2`` of them.  This is what puts a decoded
    image (e.g. the GIF title screen) on screen, so it runs right after every
    image load.

    Faithful details beyond the pixels: the GC mode and map-mask writes are
    gated on shadow bytes (the original skips redundant port I/O), the routine
    INCREMENTS the caller's ``src`` argument slot once per plane (ending at
    ``src+4``), and it restores the map mask to 0x0F on the way out.
    """
    mem = cpu.mem
    r = cpu.r
    ds = cpu.sbase["ds"]
    data = mem.data
    esp0 = r[4]
    arg0 = esp0 + 4                           # the slot the routine increments
    src = mem.r32(arg0)
    dst = mem.r32(esp0 + 8)
    count = mem.r32(esp0 + 0xC)
    n = (count >> 2) & 0xFFFFFFFF             # bytes per plane
    write = cpu.port_writer

    # GC register 5 (mode) = 0x40, only when the shadow says it isn't already.
    if mem.r8(ds + G_GC_MODE) != 0x40:
        mem.w8(ds + G_GC_MODE, 0x40)
        if write is not None:
            write(cpu, GC_INDEX_PORT, 0x4005, 16)

    vga = mem.vga
    doff = dst - APERTURE
    # One slice per plane instead of `count` aperture writes: with write mode 0
    # and a single-plane map mask, a byte written through the aperture lands in
    # exactly that plane, so the strided gather is equivalent (and the oracle
    # proves it).  Anything outside the aperture falls back to exact per-byte
    # writes through the memory model.
    fast = (vga is not None and n and APERTURE <= dst
            and dst + n <= APERTURE_END)
    for p in range(4):
        mask = 1 << p
        mem.w8(ds + G_MAP_MASK, mask)
        if write is not None:
            write(cpu, SEQ_INDEX_PORT, (mask << 8) | 0x02, 16)
        s = ds + ((src + p) & 0xFFFFFFFF)
        if fast:
            vga.planes[p][doff:doff + n] = deinterleave_plane(data, s, n, 0)
        else:
            for i in range(n):
                mem.w8((dst + i) & 0xFFFFFFFF, data[s + 4 * i])
        mem.w32(arg0, (src + p + 1) & 0xFFFFFFFF)      # inc dword [ebp+8]

    # Restore the map mask (gated on its shadow, like the original).
    last_mask = mem.r8(ds + G_MAP_MASK)       # == 8 after the four planes
    if last_mask != 0x0F:
        mem.w8(ds + G_MAP_MASK, 0x0F)
        if write is not None:
            write(cpu, SEQ_INDEX_PORT, 0x0F02, 16)

    cpu._pusha(4)                             # pushad frame (no inner pushes)
    cpu._popa(4)
    # Exit flags: the `cmp byte [map-mask shadow], 0x0F` that gated the restore.
    cpu._flags_sub(last_mask, 0x0F, last_mask - 0x0F, 8)
    cpu.eip = cpu.pop(4)                      # ret
