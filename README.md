# template_dos_port — an AI agent ports your DOS game

This repository turns an original DOS game into a **verified, native source
port** — and the porting work is done by an **AI agent**, not by you. It
packages a proven recovery methodology (piloted on Overkill, completed
end-to-end on Prehistorik 2) around the
[`dos_re`](https://github.com/missingno7/dos_re) framework, wired in as a git
submodule at `dos_re/`. The original executable runs inside a VM and serves as
the *oracle*: the agent recovers the game one verified routine at a time, and
nothing ships until it provably matches the original.

## How the work is split

| You (the human) | The AI agent |
|---|---|
| Provide your legally owned game files (EXE + data) in `assets/` | Everything else: boots the game in the VM, probes it, finds boundaries, records proofs, recovers routines, builds and verifies the native port |
| When asked: **play the game** to record a demo, or provide saves / screenshots / snapshots (the agent gives you the exact command) | Asks for those recordings when needed and turns them into regression proofs |
| Playtest the port and say what looks or sounds wrong | Traces the divergence against the original binary and fixes it |

You are **not** expected to reverse-engineer anything: no assembly, no hooks,
no addresses, no internal workflow. If a document in `docs/` reads like a
technical manual, it is — for the agent.

## Quick start

```bash
git clone --recurse-submodules <this repo>
cd template_dos_port
# put your game's files into assets/   (gitignored — original files are never committed)
python dos_re/examples/tiny_frame_game/walkthrough.py   # sanity check: the framework works here
```

Then hand the repository to your AI agent with an instruction like:

> Read `AGENTS.md` and port the game in `assets/`.

The agent takes it from there. Progress lands in `docs/<game>/run_status.md`
(a plain-language status report the agent keeps current), and
`python scripts/play.py` is your window — the same runner the agent uses, with
a live viewer, demo recording, and screenshots.

## What you get at the end

A standalone native port that boots from the original data files alone — no
emulator, no EXE in the hot path — plus the proof that it behaves exactly like
the original: a corpus of recorded demos that replay identically on the
original (in the VM) and on the port, verified byte-exact.

## Which documents are for whom

| For you | For the agent |
|---|---|
| This README | [`AGENTS.md`](AGENTS.md) — the operating card (start here) |
| `docs/<game>/run_status.md` — the progress report the agent writes | [`START_HERE.md`](START_HERE.md) — the boot sequence |
| | [`docs/`](docs/README.md) — the method (charter, lifecycle, pitfalls, cookbook, checklist) |
| | [`prompts/`](prompts/README.md) — task rituals |
| | `dos_re/docs/` — the framework's reference manual |

`MIGRATION.md` records where every file in this ecosystem came from
(maintainer provenance, not workflow).

## License

MIT ([LICENSE](LICENSE)) for the methodology in this repo. The `dos_re/`
submodule and its own `pynuked_opl3/` submodule carry their own licenses (MIT,
and LGPL-2.1-or-later respectively) — see [LICENSE](LICENSE) for details.
