# Krypton Egg — emerging data model (from the verified logic routines)

Derived from the oracle-verified gameplay-logic lifts (kegg/lifted32).
Runtime addresses (link = runtime − 0x100000).  These are working names to
be confirmed as more routines are recovered; they are what the byte-exact
lifts demonstrably read/write.

## The per-frame object system

| Global | Role | Evidence |
|---|---|---|
| 0x14e148 | object count (loop bound) | loop limits in 0x118345, 0x1183b1 |
| 0x14e14c | frame counter (++/frame) | `inc` in 0x118345 |
| 0x14e150 | object table base pointer | iterated as [ebp-4] in 0x118345/0x1183b1 |
| 0x14e154 | world X offset (added to object X) | 0x1183b1 draw-list build |
| 0x14e158 | current object pointer | 0x1195ee latches its fields |
| 0x14e15c / 15e / 160 / 162 | working geometry latched from current object (+0xa/+0xc/+2/+4) | 0x1195ee |
| 0x14e2ec | draw-command output cursor | 0x1183b1 writes commands here |

## Object struct fields (offsets seen)

| Offset | Use | Evidence |
|---|---|---|
| +0x02, +0x04 | latched to 0x14e160 / 0x14e162 | 0x1195ee |
| +0x08 | animation accumulator (`+= [+0xc]`, reset to `[+0x4]` at `[+0x10]`) | 0x118345 |
| +0x0a, +0x0c | latched to 0x14e15c / 0x14e15e; +0xc also `>>4` into a draw cmd | 0x1195ee, 0x1183b1 |
| +0x10 | animation reset threshold | 0x118345 (RECOVERED) |
| +0x14 | X position (+ [0x14e154] into the draw cmd) | 0x1183b1 |
| +0x20 | (read into draw build) | 0x1183b1 |

## The per-frame pipeline (routines, in call order)

1. **0x118345** update_anim_timers — bump the frame counter; advance/reset
   each object's animation accumulator.
2. **0x1183b1** build_draw_list — for each (half the) objects, emit a draw
   command (position from +0x14 + world offset, size from +0x08>>4) to
   [0x14e2ec].
3. **0x1195ee** load_object_fields — latch the current object's geometry into
   the working globals for the draw path.
4. The draw list is consumed by the compositor (0x122b..) → the dispatcher
   (0x122d5f) → the recovered blitters.

Refactoring these lifts into `kegg/recovered/` with a `bridge/` typed view of
the object struct is the next source-recovery step once the field meanings
are confirmed by a couple more routines.

## Struct size: 0x18 (24 bytes) — confirmed by 0x118345's `add [ebp-4],0x18` stride.

First recovered logic: `update_anim_timers` (0x118345) -> `kegg/recovered/anim.py` over `kegg/bridge/game_state.py` (GameState/ObjectView).  79,853 calls verified byte-exact.
