# Krypton Egg — symbol / address ledger

Flat linear addresses in the LE image (obj1 code @0x10000, obj2 @0x30000,
obj3 data/stack @0x40000). Status ladder: GUESS → OBSERVED → RECOVERED →
ASM_MATCHED → VERIFIED → CANONICAL.

| Address | What | Status | Evidence |
|---|---|---|---|
| 0x242d8 | LE entry point | VERIFIED | LE header EIP=obj1+0x142d8; `jmp 0x24352` over version string |
| 0x24352 | C-runtime startup (`__CMain`/cstart) | OBSERVED | `sti`/`and esp,-4`/store SP globals/`int21 AH=30h` get-DOS-version |
| 0x4f610 | initial ESP (top of obj3) | VERIFIED | LE header ESP=obj3+0xf610 |
| 0x484a0,0x484b4 | saved initial ESP globals | OBSERVED | stored at 0x24358/0x2435e |
| 0x484ac | stored selector 0x24 (flat DS?) | OBSERVED | `mov ax,0x24; mov [0x484ac],ax` @0x24364 |
| 0x484d7/8 | DOS major/minor version | OBSERVED | stored from AL/AH after int21 AH=30h @0x24379 |

## Notes

- Fixup census: 6292 × off32 (SRC_OFFSET32=0x07), 4 × sel16 (SRC_SELECTOR16=0x02).
  The 4 selector fixups are where flat CS/DS selectors get written; find and
  cross-check against DOS/4GW's real selector values when the CPU lands.
- Constant `0x50484152` ("RAPH") loaded at 0x2436e before the version check —
  likely a DOS/4GW / extender API signature. Confirm when tracing startup.
