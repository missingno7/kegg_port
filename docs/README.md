# template_dos_port documentation

**Audience: the AI porting agent.** Everything under `docs/` (and `prompts/`)
is the agent's operating manual; a human only needs the repo
[README](../README.md) and the `docs/<game>/run_status.md` the agent writes.

Start at [`../AGENTS.md`](../AGENTS.md) (the operating card) →
[`../START_HERE.md`](../START_HERE.md) (the boot sequence) if you haven't.
Reading order: `lifecycle.md` → `ai_porting_charter.md` → `pitfalls.md` →
`porting_new_game.md`.

| Doc | What it covers |
|---|---|
| [`pitfalls.md`](pitfalls.md) | **The real mistakes** the source ports made — naming, hook bloat, verification narrowing, state-capture timing, determinism traps, SMC, layering, AI hallucination, premature presentation work — each with the consequence and the rule that fixed it. |
| [`cookbook.md`](cookbook.md) | **Problem-indexed techniques** that could not be promoted as code but exist as worked examples in the source repos: timing fast-forward, shadow caches, boot-data extraction, staticizing patched code, layered audio recovery, tick-demo proofs, overnight loops, deployment. Consult it the moment your game hits a wall. |
| [`lifecycle.md`](lifecycle.md) | **The story in order**: EXE-in-VM → hot-path islands → gameplay recovery → islands merge into subsystems → complete faithful VM-less game → VM retires into the oracle seat → enhanced presentation layer last. Defines the shared vocabulary (oracle, island, golden, hybrid, native) — full table in [`dos_re/docs/glossary.md`](../dos_re/docs/glossary.md). |
| [`ai_porting_charter.md`](ai_porting_charter.md) | **The method, complete.** VM-as-oracle, the two invariants, the lifting loop, the proof spine, the determinism trap, the phased roadmap, the rules of engagement. Written for the AI agent given this framework and a DOS game. |
| [`methodology.md`](methodology.md) | The naming/altitude discipline: evidence ladder, status ladder (GUESS → CANONICAL), crystallization pyramid, hook lifecycle, fail-fast over guessed fallback. |
| [`porting_new_game.md`](porting_new_game.md) | The concrete bring-up checklist for a new game, step 0 → the lifting loop, plus the endgame steps and the code-heavy vs data-driven game styles. |
| [`enhancements.md`](enhancements.md) | The enhanced layer as the ENDGAME (sequencing rule + the audio exception), the faithful/enhanced boundary, the parity gate, and the widescreen / pixel-aspect lessons. |
| [`post_endgame.md`](post_endgame.md) | **GATED — read only after the flip.** The post-endgame playbook, sterile core only: native-product-only enhancements, the tab accuracy taxonomy (presentation / **Experimental** quarantine / debug), the human taste loop, the fps-first-interpolation-second ladder, `dos_re.overlay_menu`. |
| [`roadmap.md`](roadmap.md) | What's next, what waits for the next port, long-term shape, and decided non-goals. |

Related, outside `docs/`:

- [`../MIGRATION.md`](../MIGRATION.md) — where every file in this ecosystem
  came from (pre2_port / overkill_port → `dos_re`; `dos_re` → `dos_re` +
  `template_dos_port` + `pynuked_opl3`), what was deliberately excluded, and
  what still needs cleanup.
- [`../prompts/`](../prompts/README.md) — the ritual for each recurring task
  type, ending in an accountability REPORT block.
- [`../examples/adapter_skeleton/`](../examples/adapter_skeleton/README.md) —
  the template for a new game adapter.
- [`../examples/ledgers/`](../examples/ledgers/README.md) — the ledger
  templates (`run_status`, `blockers`, `symbol_ledger`, `demo_manifest`)
  copied into `docs/<game>/` at port start.
- The framework's own reference manual lives in the submodule:
  [`../dos_re/docs/README.md`](../dos_re/docs/README.md) (architecture, hook
  and frame verification mechanics, demos/snapshots, state mirrors, hardware
  support) and [`../dos_re/AGENTS.md`](../dos_re/AGENTS.md) (rules for working
  on the framework itself, as opposed to your adapter).
