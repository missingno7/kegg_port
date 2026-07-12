# START_HERE — you are the porting agent

You are an AI agent who has been given this repository and a DOS game to port.
This file is the boot sequence; everything else is reachable from here.
([`AGENTS.md`](AGENTS.md) is the one-page operating card distilled from this —
if you only cache one file, cache that one.)

The human's role is deliberately small: they put the game files in `assets/`,
and when you ask, they record demos, provide saves/screenshots/snapshots, and
playtest. They do **not** reverse-engineer, read ASM, or drive this workflow —
you do. Requests to the human must be concrete (exact command + what to do
in-game + where the artifact lands); the request patterns are in
[`AGENTS.md`](AGENTS.md) §"Requesting things from the human".

## What you are building

A verified, native source port of the game, recovered one proven routine at a
time from the original executable running in this repo's VM. The original
binary is the oracle — the single source of truth. You never guess behaviour;
you trace what the original did and match it, byte-exact, at every step.
Definition of done: the native port replays the whole demo corpus with the VM
disabled in the hot path, and the VM-as-oracle suite confirms frame-and-state
equivalence. ([`docs/lifecycle.md`](docs/lifecycle.md) tells the whole arc.)

## Boot sequence

1. **Read, in order:** [`docs/lifecycle.md`](docs/lifecycle.md) →
   [`docs/ai_porting_charter.md`](docs/ai_porting_charter.md) (the method —
   read all of it, twice for §6) → [`docs/pitfalls.md`](docs/pitfalls.md)
   (the mistakes already made for you) →
   [`docs/porting_new_game.md`](docs/porting_new_game.md) (the checklist you
   will now follow). For each recurring task type, use the ritual in
   [`prompts/`](prompts/README.md) — every task ends with its accountability
   REPORT block, and status claims follow the ladder (never present OBSERVED
   work as VERIFIED).
2. **Check for a port in flight.** `git log` + `docs/<game>/run_status.md` +
   `docs/<game>/blockers.md` are the resume state — a previous session (or a
   previous agent) may already be mid-campaign. Resume from the ledgers; never
   restart bring-up on a repo that has islands.
3. **Set up the workspace** (fresh port only). The game's files (EXE + data)
   go in `assets/` (gitignored — original game files are never committed; if
   it's empty, ask the human). Create your adapter package **in this
   repository, at the root, next to the `dos_re/` submodule** — e.g.
   `mygame/` — by copying the shape of
   [`examples/adapter_skeleton/`](examples/adapter_skeleton/README.md).
   Then wire the conventions in: your tests go in `tests/` and **must skip
   when `assets/` is missing** (CI has no game files — copy the pattern from
   `dos_re/tests/test_tiny_frame_game.py`), add `mygame` to
   `dos_re/tools/lint.py`'s `PACKAGE_ROOTS`, and run
   `dos_re/tools/audit_layers.py mygame/recovered` with the suite. Run
   `python dos_re/examples/tiny_frame_game/walkthrough.py` once — it exercises
   the full stack and confirms the framework works on this machine.
   **Import note:** `dos_re/` here is the submodule's repo root, not the
   package — the actual package is `dos_re/dos_re/`. This repo's
   [`pyproject.toml`](pyproject.toml) sets `pythonpath = ["dos_re"]` so
   `pytest` resolves `from dos_re.x import y` correctly for both the
   framework's own tests and yours. A non-pytest entry-point script needs the
   same directory on `sys.path` itself — this repo's
   [`scripts/play.py`](scripts/play.py) (the standard play runner you will
   adapt; a thin `GameFrontend` over `dos_re.player`) already does it —
   copy its `ROOT`/`sys.path` header for any further scripts.
4. **Start the ledgers** — copy the templates from
   [`examples/ledgers/`](examples/ledgers/README.md) into `docs/<game>/`:
   `run_status.md` (current phase + findings — its summary is also the human's
   progress report, keep it readable), `symbol_ledger.md` (addresses →
   evidence), `blockers.md` (see the loop protocol), `demo_manifest.md` (the
   corpus and its blind spots), plus the generated island manifest
   (`dos_re/tools/gen_island_manifest.py` — generated, never hand-edited).
5. **Follow [`docs/porting_new_game.md`](docs/porting_new_game.md)** step by
   step: load & run → see output → find frame boundaries → stand up the frame
   verifier → build the input-wait registry → record the first demo → start
   the lifting loop.
6. **Keep the human in the loop.** `python dos_re/tools/view.py --exe
   assets/<GAME>` is the generic live window (plus
   `dos_re/tools/render_frame.py` for PNG evidence) — use it to show progress
   and gather the human's feedback on how the game *runs*; the oracle judges
   whether the code is *correct*. Those are different jobs, and both matter.

## Mechanical tools first

Never hand-derive what a tool can measure, generate, or prove. The standing
order: **probe → profile → lift → verify**, and only read ASM where the tools
stop. The question→tool table is in [`AGENTS.md`](AGENTS.md); the three that
save the most time:

- **`dos_re/tools/profile_hotspots.py`** before any manual tracing — it finds
  the wait loops (tight backward edges) and the real cost centres (boundary
  crossings), which are your frame boundaries and first lift targets.
- **The automatic lifter** before any hand translation —
  `liftgen.py` censuses which entries are mechanically liftable;
  `liftverify.py` emits a literal Python hook and proves it against the ASM
  oracle every time it runs. You refactor a *verified* artifact into clean
  recovered code; you do not decompile from scratch
  ([`docs/porting_new_game.md`](docs/porting_new_game.md) step 7).
- **Demo replay** before any claim — a change is proven by the corpus
  replaying identically, not by your reading of the diff.

## Phase map

| Phase | You produce | Exit condition |
|---|---|---|
| Bring-up ([`porting_new_game.md`](docs/porting_new_game.md) steps 0–6) | adapter, boot snapshot, rendered frame, frame verifier, input-wait registry, first promoted demo | no-op candidate passes frame verify; the demo replays identically under every driver |
| Lifting loop (step 7, charter Phase 1) | `lifted/` + proof ledger; `recovered/` + `@oracle_link`; goldens | every slice verified vs the ASM oracle; demo suite green at every commit |
| Subsystems (lifecycle stages 3–4, charter Phases 2–4) | state mirror; collapsed hook chains; native tick driver | a subsystem reproduces frame/state from a snapshot **without stepping the VM** |
| The flip (stage 5, charter Phases 5–6) | boot constants; native runner; verification switch; the tick-demo adapter over `dos_re.tick_demo` (seams, ownership mask, sidebands, tick fn — porting guide endgame step 4) | full demo corpus passes native-vs-VM tick-by-tick (`verify_ticks` green on every recording); zero interpreted instructions in the hot path |
| Enhancements (stage 6 — only now) | the enhanced presentation layer ([`docs/post_endgame.md`](docs/post_endgame.md) — agent-executed, human-steered: the taste loop) | parity gate: enhanced-at-neutral ≡ faithful, pixel- and state-exact |

## The loop protocol (how work proceeds, slice by slice)

Proven over months of autonomous recovery on the source ports (for unattended
multi-hour runs, [`scripts/overnight_loop.sh`](scripts/overnight_loop.sh) is
the relaunch harness that enforces this protocol against a standing goal
brief — template: `examples/ledgers/overnight_goal.md`. It belongs to the
lifting phase: deploy only once the game is fully runnable and the demo
corpus spans gameplay — the brief's §0 preconditions):

1. **One slice per iteration** — one routine, one field naming, one raw-offset
   drain; the smallest coherent unit. Not a subsystem.
2. **Never commit red.** Every commit passes lint + the test suite + the demo
   gates. One slice = one focused commit.
3. **Blocked ⇒ revert + log.** If a slice can't be finished byte-exact, or the
   fix would require guessing: revert all its changes immediately, write the
   evidence into `docs/<game>/blockers.md`, and take the next target. A logged
   blocker is progress; a workaround is debt. If a divergence resists ~2
   focused trace attempts, it usually needs a lower layer recovered first.
4. **Never weaken an oracle or test to make a change pass.** Fix the code to
   match the original, or revert.
5. **Fail loud, never fake.** An unrecovered path raises a
   [`HybridGap`](dos_re/dos_re/gaps.py); it never silently falls back to ASM
   or to a plausible guess.
6. **Check for existing mechanisms before building.** The framework and your
   own adapter likely already have the tool (the module map in
   [`docs/architecture.md`](dos_re/docs/architecture.md), the `dos_re/tools/`
   directory) — and for problems the framework does NOT solve in code, check
   [`docs/cookbook.md`](docs/cookbook.md) FIRST: it maps symptoms (busy-wait
   crawl, runtime-patched code, resident audio driver, slow probes, cold-start
   endgame…) to proven worked examples in the source repos. Re-deriving one of
   those from scratch wastes days the previous ports already paid for.
7. **Update the ledgers as you go** — `run_status.md` for state, the island
   manifest for progress, the symbol ledger for evidence. The next agent (or
   the next session of you) resumes from git + these files alone.

## On failure — the routing table

| Symptom | Do this |
|---|---|
| A hook diverges from the oracle | `OK_TRACE_HOOK=CS:IP`, reproduce, read what the original actually did ([`prompts/diagnose_hook_divergence.md`](prompts/diagnose_hook_divergence.md)). After ~2 focused attempts: revert + log the blocker. |
| A demo freezes or deadlocks on replay | You missed a boundary-less input-wait loop — charter §6. Find its canonical head, register it in the adapter's `input_waits.py` (shared by ALL drivers), re-record nothing: the fix is in the driver, not the demo. |
| The VM fails loud (unimplemented opcode / DOS call / port) | The framework is asking to grow. Extend `dos_re/` under [`dos_re/AGENTS.md`](dos_re/AGENTS.md): implement the *observed* behaviour only, match flags for the observed use, add a focused test. |
| Headless runs crawl | [`docs/cookbook.md`](docs/cookbook.md) "Timing and speed" — deterministic fast-forward, walk-shadow cache. Read pitfalls #12–14 before touching timing. |
| `liftgen` refuses an entry | Its census says why (indirect jumps and x87 are the usual refusals). Hand-recover only that piece; keep lifting around it. |
| You can't drive the game past the menus / can't reach a state | Ask the human for a recorded demo — give them the exact `--record-demo` command and what to play. |
| A rebuilt buffer won't match (menu pages, scroll rings) | It's history-dependent state — pitfall #11. Replay the real sequence from a known init or recover the exact invariant; mark it *blocked* rather than guessing a stateless model. |
| A divergence appears minutes into a demo | Suffix repro — resume right before the failure, never from the start: input demos via `InputDemoPlayback.write_suffix`; tick demos via `dos_re.tick_demo.replay_to` + `TickDemo.suffix` (the divergence then reproduces at the suffix's own tick 0). |
| The native runner hits a gap or crashes | It must have written a resumable snapshot + printed the repro command (porting guide endgame step 2 — build that in from the runner's first day). Load the snapshot, reproduce in one step, recover the gap. |
| Verification passes but the game *feels* wrong to the human | Trust both signals: the oracle proves state; the human hears pacing/audio. Check the pacing model and the boundary clock (cookbook "play.py" entry) before doubting the oracle. |

## The framework is a living organism

Your game WILL exercise CPU instructions, DOS services, and hardware behaviour
the previous games didn't. Extending `dos_re/` is part of the job — under its
rules ([`AGENTS.md`](dos_re/AGENTS.md)): stdlib-only, game-agnostic, add only
what your executable *proves* it needs, document the observed register/flag
contract, add a focused test, keep it deterministic by default. When the VM
fails loud on an unimplemented opcode or port, that is the framework asking to
grow — implement the observed behaviour, never a datasheet's generality. If
you build a mechanism that the *next* game would reuse (a new hardware model,
a new verifier capability), promote it into `dos_re/` with an origin note; if
it knows your game's addresses or formats, it stays in your adapter.

## Hard boundaries (violating these voids the work)

- `dos_re/` never learns your game (enforced: `python dos_re/tools/lint.py`).
- Your `recovered/` layer never imports the VM (`dos_re/tools/audit_layers.py
  mygame/recovered` — run it with your tests from day one; pitfall #17).
- One shared definition of "a boundary" and "a wait loop" across all drivers
  ([`docs/demos_and_snapshots.md`](dos_re/docs/demos_and_snapshots.md) — the
  trap that silently voids demo proofs).
- Full-memory diffs by default; narrowing is a temporary, deliberate lever.
- **No enhanced-presentation work until the faithful native game is complete
  and stable** (widescreen, interpolation, enhanced renderers = lifecycle
  Stage 6). The only exception class is an audio-style disruption fix —
  small, separable, justified in the ledger
  ([`docs/enhancements.md`](docs/enhancements.md), pitfall #24).

## Progress is measured, not vibed

- Native % over a demo replay — `dos_re.coverage.CoverageCollector` on
  `cpu.coverage_telemetry`; your adapter supplies only the address→island
  classifier (porting guide step 8). Hooked work is measured in verifier-
  reported ASM-equivalent instructions; the unmeasurable is reported OUTSIDE
  the percentage, never guessed into it.
- The generated island manifest (count × confidence ladder).
- Demo-corpus coverage and pass rate.
- The glue-hook count (falling is good) and the frontier manifest
  (`dos_re/frontier.py`) once coverage converges.

When in doubt: trace it, snapshot it, prove it. The oracle is right there.
