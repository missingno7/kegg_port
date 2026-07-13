# Krypton Egg — control-flow architecture (traced from the gameplay snapshot)

The per-frame call chain, recovered by walking the call stack at the vsync
wait and disassembling each frame.  Runtime addresses (link = − 0x100000).

## The main loop and frame

```
0x110078  main loop            (enter 0x14e4 — big frame-locals function)
  -> 0x11c14b                  (per-frame setup, arg [0x14dd44])
  -> 0x113203  frame driver    (returns eax; loop continues while nonzero)
       -> 0x1211de             (arg [0x14746c])
       -> 0x11ed38
       -> 0x119d40  per-frame update (arg 1)   [indirect: call [0x1473b8]]
       -> 0x123b72
  -> 0x113406, 0x11c3ab, 0x1160e5, 0x1161a6, ...
  -> (render: compositor 0x122b.. -> dispatcher 0x122d5f -> blitters)
  -> vsync wait (0x119e29 spin on 3DAh, counter [0x14e1a8])
```

## The per-frame update -> subsystem dispatch

`0x119d40` calls the current **mode handler** through `[0x1473b8]`
(gameplay handler = **0x11fb17**; other modes for title/menu swap this
pointer).  The gameplay handler is a **bit-dispatched subsystem table** keyed
on the game-state flags word `[0x147b34]`:

| flag bit | subsystem | notes |
|---|---|---|
| 0x80 | 0x11fe6a | |
| 0x01 | 0x11fbc0 | state toggle; calls [0x147b3f]/[0x147b43] indirect handlers |
| 0x02 | 0x11fc1e | |
| 0x04 | 0x11fb92 | **launch trigger** — if a key slot == 0x20 (space), set [0x147b3d]=0xffff |
| 0x10 | 0x11fd3b | |
| 0x20 | 0x11fd7b | key-toggle state machine (F-key slots 0x45/0x46) |
| 0x40 | ... | |

## The input surface

The subsystems read a **key-state table** at `~0x14e460..0x14e490` (slots
like [0x14e48d]/[0x14e48f] compared to scancodes 0x20/0x45/0x46).  This is the
table the emulated 8042 KBC + the game's INT 9 ISR fill; the state machines
translate key edges into game-flag transitions (launch, pause, toggles).

## What this means for recovery

- The **render pipeline is fully recovered** (anim -> draw-list -> blitters).
- The **game rules are these small input-driven state machines** — each
  liftable/verifiable (0x11fd7b already ORACLE_PASSING), recovered one at a
  time against the key-state bridge.  They are interdependent through the
  [0x147b34] flags and the key table, so a `bridge/` view of both is the
  foundation for recovering them as clean named source.
- Ball/brick **physics** proper (position integration, bounce, collision) is
  reached from these when the ball is active; locating the exact routine is
  the next structural step (this snapshot appears to be ball-on-paddle, so the
  launch trigger is the live subsystem).


## Verification status of the gameplay layer (this snapshot)

Lift-verified ORACLE_PASSING in situ from snap_126359171:
0x119d40 (per-frame update), 0x11fb17 (gameplay handler), 0x11fd3b (the
active input->action subsystem, bit 0x10), 0x11ed38.

**NOT_REACHED in this snapshot** (their [0x147b34] flag bits are clear):
0x11fb92 (launch trigger, 0x04), 0x11fbc0 (0x01), 0x11fc1e (0x02),
0x11fe6a (0x80, an Enter/name-entry handler).  0x11fd3b dispatches actions
through [0x147b47]; the ball-motion/collision code is reached only when the
ball-active subsystems run.

### CONFIRMED: the ball physics needs a ball-in-flight capture

This snapshot is a ball-on-paddle waiting state — the launch trigger and the
ball-active subsystems don't execute, so the physics/collision routines are
NOT_REACHED and cannot be verified here.  A `scripts/play.py` snapshot (F12)
taken **while the ball is bouncing** (and one mid-brick-hit) would exercise
and unlock them.  Until then the game-rule recovery is capped at the input/
dispatch layer above.


## Ball-in-flight state (from snap_157569453 — the launched-ball capture)

With the ball launched, [0x147b34] = 0xBB, so the ball-active subsystems run
and now VERIFY ORACLE_PASSING (they were NOT_REACHED in the ball-on-paddle
snapshot): 0x11fbc0 (0x01), 0x11fc1e (0x02), 0x11fe6a (0x80), plus 0x11fd3b/
0x11fd7b.  The launch trigger 0x11fb92 (0x04) is now inactive (already fired).

### Ball state and handlers

- `0x11fbc0` (bit 0x01) dispatches the ball through `[0x147b3f]` = **0x112c72**
  and `[0x147b43]` = **0x11353f** (the two ball-state handlers).
- Ball position globals: **[0x147b18]** (X), **[0x147b20]/[0x147b22]** (Y,
  double-buffered), **[0x147b14]/[0x147b16]** (scratch/prev).  0x11353f draws
  the ball via `0x122f9c` at ([0x147b18], [0x147b20]) and ([0x147b18],
  [0x147b22]).
- **0x11eda0** — a clean 17-instruction leaf that swaps the two ball-Y slots
  ([0x147b20] <-> [0x147b22] via temp [0x147b16]): the Y double-buffer flip.
  The velocity integration / wall+brick collision is the larger routine above
  it in the 0x112c72 / 0x11fc1e chain (next to locate precisely).

The physics LAYER is now reached and oracle-verifiable from this snapshot —
recovering the integration/collision as clean source is the next slice.
