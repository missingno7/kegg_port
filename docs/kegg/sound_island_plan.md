# Sound island — native stereo handler plan (dos_re 3.0 region)

Goal: a NATIVE stereo sound/music handler replacing Krypton Egg's whole sound
island — the game's software mixer + Sound Blaster driver — as a first-class
dos_re 3.0 **execution region**, bypassing the emulated SB entirely.  The
faithful contract stays authoritative; stereo/high-rate output is a declared
**enhancement** on top of it.

## What the island is (evidence so far)

- KE plays **digitized 8-bit mono PCM at 7936 Hz**: DSP 2.01, single-cycle
  640-byte DMA blocks, refilled from the game's own mix buffer in its IRQ7 ISR.
- Music is streamed from the `.DIG` assets (KE_MENU/MAIN/LVL/SCORE/PAUSE/
  END/GO/INFOS.DIG); SFX are mixed over it by the game's software mixer.
- The mix buffer lives in game memory (its overflow once corrupted return
  addresses — see dos4gw.attach_sound_blaster docstring), i.e. mixer state is
  ordinary DOS memory the region will own.

## S1 RESULTS — the island map (measured, 2026-07-22)

ISR-extent trace (120 IRQ7 deliveries) + static caller/IO sweep + disassembly:

**Layers**
- Hardware primitives (shared, NOT island-private): `0x123FA3 = outb(port,val)`,
  `0x123FAD = inb(port)` — 60/41 call sites across the whole game (vsync waits
  included).  The island uses them; it does not own them.
- **Runtime ISR `0x121258`** (118/120 deliveries; `0x11D252` is the
  DETECTION-phase handler, 2/120 — earlier attribution reversed).  Protocol,
  read from disasm: ack SB (`in base+0xE`) → gate on sound-active flag
  `[0x147458]` → compare block cursor `[0x14744C]` vs end `[0x14745C]` →
  DSP write-ready spin (`in base+0xC & 0x80, loopnz`) → command `0x14` +
  length `0x027F` = re-arm the 640-sample single-cycle block.  SB base port
  variable: `[0x14E2FC]`.  Inlined port I/O (ISR-speed, bypasses the
  primitives).  Switches to a private stack (the observer's per-stack
  tracking exists because of this).
- **Mixer core**: `0x1245D0(a,b,c)` = wrapper (12-byte params via
  `0x125AC8`, then `0x1245AD`); `0x1245AD` = register-convention marshaller
  (args → ebp/esi/edi/ebx) around **`0x1256EA` — THE mix worker** →
  `0x125722`.  `0x1245AD` is already lifted + oracle-verified
  (kegg/lifted/lift_1245ad.py); `0x1256EA/0x125722/0x125AC8/0x121258` are
  prime pmlift targets (`--entry`) for lifted baselines before hand recovery.
- **Driver/management layer `0x11D2xx..0x11E2xx`**: all 17 static callers of
  `0x1245AD` and all 17 of `0x1245D0` live here (init, detection, track/SFX
  control).  The game-facing entry points sit at this layer's rim — the
  region's entry seams (next: sweep callers into 0x11D2xx..0x11E2xx from
  outside).
- Port-I/O concentration: 72 in/out at `0x121xxx` (ISR + DSP protocol), 44 at
  `0x123xxx` (primitives + DSP helpers); the rest is VGA/vsync elsewhere.

**S2 finding — the sound engine is a COROUTINE.**  The "mixer chain" is KE's
context-switch machinery: `0x1256EA` saves the register context into a task
block (eax..esi at +0..+0x14, carry→+0x18, SS:SP into the TCB at +6) and
`0x125722` restores a context block and ``ret``s into a 3-byte-entry
trampoline table at `0x1257C8` (task dispatch).  The sound engine runs as a
TASK on its own stack — which is why the ISR stack-switches (the Atlas
observer's per-stack tracking exists because of this) and why `0x1245D0` is
"build 12-byte params (`0x125AC8`) + switch".  All five context-switch
routines are lifted + oracle-verified (kegg/lifted/lift_1245ad, _1245d0,
_1256ea, _125722, _125ac8; the ISR lift_121258 is emitted but NOT_REACHED in
bare pmlift — no SB attached, a pmlift gap for IRQ-driven code).  The real
mix loop lives in the SOUND TASK's body (entered via the trampoline) — next
step: trace the task-side execution to find and recover it, and map the TCB
table.

**Known globals (symbol-ledger candidates)**: `[0x14E2FC]` SB base port,
`[0x147458]` sound-active flag, `[0x14744C]/[0x14745C]` block cursor/end,
`0x1257C8` task trampoline table.
Atlas corroboration: `0x11FA42` (per-frame wait/poll tick, callers incl. the
menu idle `0x110951`) spins through sound waits at level transitions — the
frame-parked stretches the replay timeline cannot subdivide.

## Why a region, not per-function overrides

The island is a long-lived subsystem with its own state (voice slots, music
cursor, mix buffer, DMA programming) entered through a few stable seams:

- the **ISR entry** (block-complete → mix next block, advance music),
- the **game-facing API** (trigger SFX n, start/stop music track, volume),
- **frame-side sequencing** (if any per-frame sound bookkeeping exists).

dos_re 3.0 models exactly this: `ImplementationDescriptor.region_contract`
(`ExecutionRegionContract`: contained identities, entry/exit edges, state
ownership) + `RegionAdapter` (host carrier → `NATIVE_STATE_CARRIER`) +
`regions.py`'s session dispatcher (create session at the entry seam, advance
at semantic boundaries, return declared exits).  Nothing uses regions yet —
**kegg's sound island becomes the first real region**, which is the point:
validate the machinery on a real subsystem.

## Plan

### Phase S1 — map the island with the Execution Atlas
Use the replay-evidence Atlas (now live) to enumerate the island:
callers/callees around 0x11D252, the SFX-trigger call sites from gameplay
code, the music-control calls from menu/level transitions, and per-replay
first-entry/last-exit intervals for each island function.  Output: the
island's contained-identity list + entry/exit edge list — the literal content
of its `ExecutionRegionContract`.

### Phase S2 — recover the island semantics (faithful, pure)
`kegg/recovered/sound.py`: the mixer (voice table layout, per-voice sample
cursor/volume, 8-bit mix into the block buffer), the music sequencer (DIG
streaming, looping), and the driver protocol (block re-arm).  Proven the
usual way: focused differential verification per routine + the observable
PCM stream (`sb.pcm_out`) as the island's observable effect — byte-equal
mono 7936 Hz output over corpus replays is the faithful claim.

### Phase S3 — declare the region in the catalog
One `ImplementationEntry` with `region_contract`: contained function ids
(from S1), entry edges (ISR, SFX API, music API), exit edges (IRET back,
API returns), state ownership (mixer globals + mix buffer + DMA/DSP
programming), `RegionVerificationContract` (interior = semantic state;
exits = continuation seams).  Verification uses the region contract, not
full-machine diff (register scratch inside the island is region-private).

### Phase S4 — native handler as the region backend
`kegg/native/sound.py`: loads the `.DIG` assets directly, tracks the same
semantic state (current track, voice slots), mixes in float/16-bit at the
host rate via the existing sounddevice sink.  Two catalog implementations:
- **faithful-native**: mono 7936 Hz downmix must byte-match the recovered
  mixer's output (parity-testable);
- **stereo enhancement** (`OverrideCategory.ENHANCEMENT`, per
  docs/enhancements.md): stereo panning per voice, 44.1 kHz resample of the
  DIG sources, declared excluded-from-parity output domain = the audible
  stream; MUST NOT write authoritative state (enforced by verification —
  replays with the enhancement on must keep game state byte-identical).

### Phase S5 — retire the emulated SB for this composition
With the region selected, the game's OUT/IN to $210 and DMA programming are
region-internal; the emulated SoundBlaster device is no longer attached in
that composition.  The block-complete IRQ becomes a region-owned semantic
boundary (the region yields at block cadence on the deterministic
instruction-count clock, preserving replay identity).

## What's missing / to verify in dos_re (framework work)

1. **Regions are unexercised** — first real user; expect gaps in
   `bind_plan_implementations`'s region path (suppressed_bindings, region
   adapters) and the session dispatcher. Fix in dos_re as found.
2. **PM boundary observation** — the 16-bit emitter has `boundary_heads`
   (observe a boundary with zero interpreted instructions); PM has nothing
   equivalent yet. The region's ISR/API seams need PM boundary hooks
   (the `entry_probes` observation seam is the likely substrate).
3. **Observable-effect verification** — `verify_checkpointed`'s
   `observable_effects` needs driver support (`begin/end_observable_interval`)
   to compare the PCM stream as an ordered effect; PMReplayDriver doesn't
   implement it yet.
4. **Enhancement read-only enforcement** — the parity harness that proves
   "enhancement on == authoritative state unchanged" over a replay interval.

## Order of work

S1 now (Atlas queries over the corpus), S2 next (biggest recovery effort,
fully parallel to other work), S3+S4 together (region + native backend),
S5 last. The stereo enhancement ships as soon as S4's faithful-native parity
holds — stereo is a presentation flag on the same native backend.

**S2 leads (execution sampling, menu music):** the scheduler tick lives at
`0x1202xx` (calls `0x1245D0` at site 0x120217) and runs INSIDE the idle/vsync
loop — cooperative slices, one per iteration; the sound task's top loop
(check-work/yield) is at `~0x125861` (immediately after the trampoline
table); the mix work proper points into the `0x124xxx` page (executed only on
block completion).  Note: both stacks share the 0x14xxxx 64KiB region — the
observer's per-region tags rarely trigger on KE; the esp+4 caller-level
unwind is the load-bearing rule.

**S2 refill chain (DMA write-trap, measured):** the DMA buffer is 1280 bytes
in LOW DOS memory (0x64EFF..0x653FF here; two 640-sample halves).  Exactly one
site writes it: the `rep movsd` of `0x123889` — a GENERIC direction-aware
memcpy(src,dst,len) with VGA-aperture guards (not sound-specific).  The
sound-engine per-block body lives at `0x11C294..0x11C4xx` (reached from the
guarded per-slice tick 0x123B72 when the 'S','S' flags at [0x14E48D]/[0x14E48F]
are set; calls the memcpy at site 0x11C478): stream/mix the next 640 bytes,
copy into the just-played DMA half, coordinate the ISR's DSP re-arm.  NEXT:
lift + read 0x11C294's function to map the voice table and .DIG stream
cursors → recovered/sound.py.
