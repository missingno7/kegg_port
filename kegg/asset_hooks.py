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
from kegg.recovered.present import DAC_MAX, fade_palette_stream

GIF_DECODE = 0x121DF8
PALETTE_FADE = 0x123A48

DAC_INDEX_PORT = 0x3C8
DAC_DATA_PORT = 0x3C9


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
