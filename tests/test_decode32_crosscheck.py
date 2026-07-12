"""decode32 vs CPU386: length cross-check over real KE execution.

The lifter's honesty gate (lifting_design §4) applied to the 32-bit decoder:
every instruction the interpreter executes during KE's boot is also decoded
statically, and the decoded length must equal the number of bytes the
interpreter actually fetched.  Any disagreement is a decoder bug (or an
interpreter bug) — either way, a lift blocker caught before it can lie.

Skips without assets.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")

WINDOW = 400_000     # boot instructions to cross-check (covers cstart, FPU, video init)


def test_lengths_match_interpreter():
    from kegg.runtime import create_game_runtime
    from dos_re.lift.decode32 import decode32

    rt = create_game_runtime(EXE, install_replacements=False)  # test the pure interpreter
    cpu = rt.cpu
    read = cpu.mem.data.__getitem__

    state = {"first": None, "count": 0}
    orig_fetch8 = cpu._fetch8

    def counting_fetch8():
        if state["first"] is None:
            state["first"] = cpu.eip
        state["count"] += 1
        return orig_fetch8()
    cpu._fetch8 = counting_fetch8

    # _fetch16/_fetch32 bypass _fetch8 in CPU386 — route them through it so
    # the count covers every encoded byte.
    def fetch16():
        return counting_fetch8() | (counting_fetch8() << 8)

    def fetch32():
        v = fetch16()
        return v | (fetch16() << 16)
    cpu._fetch16 = fetch16
    cpu._fetch32 = fetch32

    mismatches = []
    checked = 0
    for _ in range(WINDOW):
        state["first"] = None
        state["count"] = 0
        cpu.step()
        first, nbytes = state["first"], state["count"]
        if first is None or nbytes == 0:
            continue                      # hook/IRQ-only step
        checked += 1
        try:
            inst = decode32(read, first)
        except ValueError as e:
            mismatches.append((first, nbytes, f"decode refused: {e}"))
        else:
            if inst.length != nbytes:
                mismatches.append((first, nbytes, f"decoded {inst.length} ({inst.mnemonic})"))
        if len(mismatches) >= 10:
            break

    assert not mismatches, (
        f"{len(mismatches)} length disagreements in {checked} instructions; first: "
        + "; ".join(f"0x{a:X}: fetched {n}, {msg}" for a, n, msg in mismatches[:5]))
    assert checked >= WINDOW * 0.99       # the window really was exercised
