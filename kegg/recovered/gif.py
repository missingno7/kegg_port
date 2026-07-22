"""Faithful native GIF87a LZW image decoder — Krypton Egg's 0x121DF8.

The recovered semantic body of the asset unpacker.  KE stores its title/menu/
score screens as 256-colour GIF87a and decodes them with a hand-rolled LZW
decoder at flat 0x121DF8 — the single hottest asset-load routine (~3.86M
interpreted instructions to unpack the 71 KB title image, ~5 s on CPython).

This reproduces that routine's EXACT observable memory effect so it verifies
byte-for-byte against the ASM oracle (``pm_verification.PMHookVerifier`` diffs
the whole machine): the decoded 8-bit pixels, the 6-bit VGA palette appended
after them, the result descriptor, the ``[0x14E2BC]`` size accumulator, the
in-place de-blocked LZW source, and the decoder's private scratch — the LZW
string tables and the reversal stack — in their final (high-water) state.

It stays ``dos_re``-free: it operates on a raw ``bytearray`` (the flat machine
memory) plus the four call arguments.  The CPU adapter in ``kegg.gif_hooks``
marshals the stack args and the pushad/popad register frame around it.

Layout (from the lifted body ``kegg/graph_full/lift_121df8.py``):
  scratch base P0 = arg ``scratch``; P1 = P0+0x1400 (prefix table, words);
  P2 = P0+0x3C00 (suffix/char table, bytes); P0.. = string reversal stack.
  Globals live at 0x148314..0x14835F (see the constants below).
"""
from __future__ import annotations

# Decoder scratch globals (flat, ds-relative; the adapter adds the ds base).
G_314 = 0x148314   # cleared to 0
G_316 = 0x148316   # last normal code processed
G_318 = 0x148318   # image width
G_31A = 0x14831A   # image height
G_31C = 0x14831C   # global-colour-table present flag (0/1)
G_31D = 0x14831D   # colour resolution + 1 (byte)
G_31E = 0x14831E   # GCT size exponent + 1 (word) == 8
G_320 = 0x148320   # P0: scratch base / string reversal stack
G_324 = 0x148324   # P1: prefix table base (= P0 + 0x1400)
G_328 = 0x148328   # P2: suffix/char table base (= P0 + 0x3C00)
G_32C = 0x14832C   # current LZW code width (bits)
G_32E = 0x14832E   # min code size + 1 (set once)
G_330 = 0x148330   # first assignable code (clear + 2, set once)
G_332 = 0x148332   # next code to assign
G_334 = 0x148334   # code-width bump threshold
G_336 = 0x148336   # 1 << (min+1) (set once)
G_338 = 0x148338   # code mask ((1<<width)-1)
G_33A = 0x14833A   # pixel value mask (0xFF)
G_33C = 0x14833C   # previous string's first char (prev_char)
G_33D = 0x14833D   # bit buffer (dword)
G_341 = 0x148341   # bit count (word)
G_343 = 0x148343   # previous code (prev_code / cur)
G_349 = 0x148349   # clear code
G_34B = 0x14834B   # end-of-information code
G_34D = 0x14834D   # destination output pointer (set once)
G_351 = 0x148351   # LZW source cursor (saved on refill)
G_355 = 0x148355   # status / progress word (0 == success)
G_357 = 0x148357   # global colour table byte size (768)
G_35B = 0x14835B   # pointer to the global colour table
G_2BC = 0x14E2BC   # decoded-size accumulator (pixels(even) + 768)

_GIF8 = 0x38464947   # "GIF8"
_87A = 0x6137        # "7a"


def decode_gif(data: bytearray, base: int, src: int, dst: int,
               desc: int, scratch: int) -> tuple[int, int, int]:
    """Decode the GIF at ``src`` into ``dst`` (indices) + palette; fill the
    descriptor at ``desc``.  Mutates ``data`` exactly as flat 0x121DF8 does.

    Returns ``(status, ecx_final, last_gct)``: ``status`` is the word left in AX
    ([0x148355], 0 on success); ``ecx_final`` is the value ECX holds at the
    routine's last internal ``push ecx`` (the final code width); ``last_gct`` is
    the last palette byte fed to the routine's final ``shr al,2``.  The adapter
    needs the latter two to reproduce the sub-esp stack scratch and the exit
    flags byte-for-byte.

    ``base`` is the ds/es segment base (0 in KE's flat model); every flat
    address below is taken relative to it.
    """
    def r8(a): return data[base + a]
    def r16(a): return data[base + a] | (data[base + a + 1] << 8)
    def w8(a, v): data[base + a] = v & 0xFF

    def w16(a, v):
        v &= 0xFFFF
        data[base + a] = v & 0xFF
        data[base + a + 1] = (v >> 8) & 0xFF

    def w32(a, v):
        v &= 0xFFFFFFFF
        data[base + a] = v & 0xFF
        data[base + a + 1] = (v >> 8) & 0xFF
        data[base + a + 2] = (v >> 16) & 0xFF
        data[base + a + 3] = (v >> 24) & 0xFF

    p0 = scratch
    p1 = (scratch + 0x1400) & 0xFFFFFFFF
    p2 = (scratch + 0x3C00) & 0xFFFFFFFF
    w32(G_320, p0)
    w32(G_324, p1)
    w32(G_328, p2)
    w16(G_32C, 0xC)
    w32(G_34D, dst)
    w16(G_314, 0)

    s = src                                    # source cursor (esi)

    # --- header: "GIF87a" -------------------------------------------------
    magic = r16(s) | (r16(s + 2) << 16); s += 4
    w16(G_355, 0x901)
    if magic != _GIF8:
        return r16(G_355), 0, 0
    ver = r16(s); s += 2
    w16(G_355, 0x902)
    if ver != _87A:
        return r16(G_355), 0, 0

    # --- logical screen descriptor ---------------------------------------
    scr_w = r16(s); s += 2
    scr_h = r16(s); s += 2
    w16(G_318, scr_w)
    w16(G_31A, scr_h)
    flags = data[base + s]; s += 1
    w8(G_31C, 1 if (flags & 0x80) else 0)      # GCT present
    w8(G_31D, ((flags >> 4) & 7) + 1)          # colour resolution + 1
    w16(G_355, 0x905)
    if ((flags & 7) + 1) != 8:                 # KE requires a 256-entry GCT
        return r16(G_355), 0, 0
    w16(G_31E, 8)
    s += 2                                      # background index + aspect ratio
    # global colour table: 256 * 3 bytes
    gct_bytes = 768
    w32(G_357, gct_bytes)
    gct_ptr = s
    w32(G_35B, gct_ptr)
    s += gct_bytes

    # --- image descriptor -------------------------------------------------
    sep = data[base + s]; s += 1
    w16(G_355, 0x906)
    if sep != 0x2C:
        return r16(G_355), 0, 0
    s += 2                                      # image left
    s += 2                                      # image top
    img_w = r16(s); s += 2
    if scr_w == 0:
        w16(G_318, img_w)
    w16(G_355, 0x903)
    img_h = r16(s); s += 2
    if scr_h == 0:
        w16(G_31A, img_h)
    w16(G_355, 0x904)
    # The packed image field (1 byte) and the LZW min-code-size (1 byte) are
    # read together as a word (the ASM's `lodsw`): low byte = packed fields,
    # high byte = min code size; the cursor now sits at the first sub-block.
    img_flags = r16(s); s += 2
    w16(G_355, 0x907)
    if img_flags & 0x80:                        # local colour table unsupported
        return r16(G_355), 0, 0
    min_code_size = (img_flags >> 8) & 0xFF

    # --- de-block the LZW sub-blocks into a contiguous stream in place -----
    w16(G_355, 0x908)
    img_data_start = s                          # first sub-block length byte here
    read = img_data_start
    write = img_data_start
    length = data[base + read]; read += 1
    while length != 0:
        for _ in range(length):
            data[base + write] = data[base + read]
            write += 1
            read += 1
        length = data[base + read]; read += 1
    # LZW data now contiguous at [img_data_start, write); cursor restarts there.
    s = img_data_start

    # --- LZW decode -------------------------------------------------------
    clear = 1 << min_code_size
    eoi = clear + 1
    first = clear + 2
    w16(G_32E, min_code_size + 1)
    w16(G_349, clear)
    w16(G_34B, eoi)
    w16(G_330, first)
    w16(G_332, first)
    w16(G_336, 1 << (min_code_size + 1))
    pixel_mask = (1 << 8) - 1
    w16(G_33A, pixel_mask)

    code_width = min_code_size + 1
    code_limit = 1 << (min_code_size + 1)
    code_mask = code_limit - 1
    bitbuf = 0
    bitcnt = 0
    src_saved = s                               # [0x148351] lags: saved on refill

    # active tables (reset by CLEAR) drive decoding; the *_mem dicts remember
    # the last value ever written to each slot (survives CLEAR) so the scratch
    # memory image matches the ASM's high-water content.
    prefix = {}                                 # code -> prefix code (active)
    suffix = {}                                 # code -> first-char suffix (active)
    prefix_mem: dict[int, int] = {}
    suffix_mem: dict[int, int] = {}
    stack_hw = bytearray()                      # reversal-stack high-water image

    out = bytearray()                           # decoded pixel indices
    prev_code = 0
    prev_char = 0
    last_code = r16(G_316)                       # [0x148316] survives across calls
    next_code = first
    ecx_final = code_width                       # ECX at the last `push ecx` (bb38)

    def decode_string(code):
        """Return the pixel list for ``code`` using the active tables."""
        chars = []
        c = code
        while c > pixel_mask:
            chars.append(suffix[c])
            c = prefix[c]
        chars.append(c)
        chars.reverse()
        return chars

    def push_stack(seq):
        """Mirror the reversal stack writes (reversed(seq[1:])) into the
        high-water image; the ASM overwrites [P0..] a prefix at a time."""
        depth = len(seq) - 1
        for j in range(depth):
            ch = seq[len(seq) - 1 - j]
            if j < len(stack_hw):
                stack_hw[j] = ch
            else:
                stack_hw.append(ch)

    while True:
        # fetch next code (refill up to two bytes, exactly like the ASM)
        refilled = False
        while bitcnt < code_width:
            byte = data[base + s]; s += 1
            bitbuf = (bitbuf + (byte << bitcnt)) & 0xFFFFFFFF
            bitcnt += 8
            refilled = True
        if refilled:
            src_saved = s
        code = bitbuf & code_mask
        bitbuf >>= code_width
        bitcnt -= code_width

        if code == eoi:
            break
        if code == clear:
            code_width = 9
            code_limit = 0x200
            next_code = 0x102
            code_mask = 0x1FF
            prefix.clear()
            suffix.clear()
            # first code after clear: a literal, output directly, no table entry
            refilled = False
            while bitcnt < code_width:
                byte = data[base + s]; s += 1
                bitbuf = (bitbuf + (byte << bitcnt)) & 0xFFFFFFFF
                bitcnt += 8
                refilled = True
            if refilled:
                src_saved = s
            code = bitbuf & code_mask
            bitbuf >>= code_width
            bitcnt -= code_width
            prev_code = code
            prev_char = code & 0xFF
            out.append(code & 0xFF)
            continue

        last_code = code
        if code < next_code:
            seq = decode_string(code)
        else:                                   # code == next_code: KwKwK
            seq = decode_string(prev_code)
            seq = seq + [seq[0]]
        out.extend(seq)
        push_stack(seq)
        ecx_final = code_width                   # ECX at this code's `push ecx`

        first_char = seq[0]
        prefix[next_code] = prev_code
        suffix[next_code] = first_char
        prefix_mem[next_code] = prev_code
        suffix_mem[next_code] = first_char
        prev_code = code
        prev_char = first_char
        next_code += 1
        if next_code == code_limit and code_width < 12:
            code_width += 1
            code_limit <<= 1
            code_mask = code_limit - 1

    # --- write the decoded pixels + persist LZW state ---------------------
    n = len(out)
    data[base + dst:base + dst + n] = out
    edi = (dst + n) & 0xFFFFFFFF

    w16(G_316, last_code)
    w16(G_32C, code_width)
    w16(G_332, next_code)
    w16(G_334, code_limit)
    w16(G_338, code_mask)
    w8(G_33C, prev_char)
    w32(G_33D, bitbuf)
    w16(G_341, bitcnt)
    w16(G_343, prev_code)
    w32(G_351, src_saved)
    # prefix table words at [P1 + code*2]; suffix bytes at [P2 + code].
    for code, pv in prefix_mem.items():
        a = base + p1 + code * 2
        data[a] = pv & 0xFF
        data[a + 1] = (pv >> 8) & 0xFF
    for code, cv in suffix_mem.items():
        data[base + p2 + code] = cv & 0xFF
    if stack_hw:
        data[base + p0:base + p0 + len(stack_hw)] = stack_hw

    # --- descriptor + size accumulator + 6-bit palette --------------------
    size = n
    even = size & ~1
    edi_even = (dst + even) & 0xFFFFFFFF
    w32(G_2BC, (even + gct_bytes) & 0xFFFFFFFF)

    w32(desc, dst)
    w32(desc + 4, edi_even)
    w32(desc + 8, r16(G_318))
    w32(desc + 0xC, r16(G_31A))
    w32(desc + 0x14, 0x100)
    w32(desc + 0x10, 3)

    # palette: 768 GCT bytes, 8-bit -> 6-bit, appended after the (even) pixels
    o = base + edi_even
    for i in range(gct_bytes):
        data[o + i] = (data[base + gct_ptr + i] >> 2) & 0xFF
    last_gct = data[base + gct_ptr + gct_bytes - 1]   # AL into the routine's last `shr al,2`

    w16(G_355, 0)
    return 0, ecx_final, last_gct
