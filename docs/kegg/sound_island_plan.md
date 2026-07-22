# Sound island — native stereo handler plan (dos_re 3.0 region)

Goal: a NATIVE stereo sound/music handler replacing Krypton Egg's whole sound
island — the game's software mixer + Sound Blaster driver — as a first-class
dos_re 3.0 **execution region**, bypassing the emulated SB entirely.  The
faithful contract stays authoritative; stereo/high-rate output is a declared
**enhancement** on top of it.

## What the island is (evidence so far)

- KE plays **digitized 8-bit mono PCM at 7936 Hz**: DSP 2.01, single-cycle
  640-byte DMA blocks, refilled from the game's own mix buffer in its IRQ7 ISR.
- Runtime ISR entry observed at **0x11D252** (a second handler 0x121258 serves
  the detection phase).  The driver re-arms single-cycle DMA per block.
- Music is streamed from the `.DIG` assets (KE_MENU/MAIN/LVL/SCORE/PAUSE/
  END/GO/INFOS.DIG); SFX are mixed over it by the game's software mixer.
- The mix buffer lives in game memory (its overflow once corrupted return
  addresses — see dos4gw.attach_sound_blaster docstring), i.e. mixer state is
  ordinary DOS memory the region will own.

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
