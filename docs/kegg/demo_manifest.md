# Krypton Egg — demo corpus manifest

Demos are self-contained bundles: a start snapshot + input keyed to the game's
per-frame counter (0x119D40), plus optional per-frame **digests** (a full-VM
fingerprint) so a replay self-verifies against its recording.

## Determinism contract (READ before recording)

A demo replays byte-identically ONLY if the recording and the replay share the
same emulated clock.  The steering input is the **Sound Blaster block-complete
IRQ**: its ISR runs mid-frame, and where it lands changes the instruction
stream enough to make a replay diverge — or crash.  So every reproducible path
(record, replay, headless) keeps the SB on the DETERMINISTIC instruction-count
clock (`instruction_count / EMULATED_IPS`); only a casual live viewer (not
recording) uses wall-clock audio pacing.

- **Record** and **replay** run deterministically.  `--play-demo <dir>` prints
  `demo VERIFIED` (all fingerprinted frames matched) or `demo DIVERGED at
  frame N` (with the exact frame), so a bad demo is caught immediately.
- Demos recorded BEFORE this fix (under wall-clock audio) are NOT reproducible
  and must be re-recorded.
- Record on pypy where possible: the deterministic clock ties audio cadence to
  instruction count, so on a slow interpreter the recording's audio stretches
  (the demo is still valid; only the live sound during capture is affected).

| Demo | Covers | Verified | Notes |
|---|---|---|---|
| — | — | — | pre-fix demos superseded; re-record with the deterministic clock |
