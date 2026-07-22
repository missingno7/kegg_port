"""The detached entrypoint: capture a boot image, then resume + play EXE-free.

Proves end-to-end that Krypton Egg runs without KE.EXE once captured: the
EXE-free resume is byte-identical to the EXE-loaded resume, and `play` advances
the machine with no executable loaded.  Needs KE.EXE to capture, so it skips in
CI (the mechanism itself is covered game-free by dos_re/tests/test_pm_detached).
"""
import argparse
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "dos_re")):
    if p not in sys.path:
        sys.path.insert(0, p)

EXE = ROOT / "assets" / "KE.EXE"


@pytest.mark.skipif(not EXE.exists(), reason="assets/KE.EXE not present")
def test_capture_verify_and_play_detached(tmp_path, monkeypatch):
    import scripts.detached as d
    monkeypatch.setattr(d, "SNAP", tmp_path / "boot")

    assert d.cmd_capture(argparse.Namespace(
        boot_steps=800_000, replay="", frames=250)) == 0
    assert (tmp_path / "boot" / "pm_state.json").exists()

    # the EXE-free resume matches the EXE-loaded resume byte-for-byte
    assert d.cmd_verify(argparse.Namespace(steps=200_000)) == 0

    # and it plays detached -- load_snapshot_headless builds image=None, no EXE
    assert d.cmd_play(argparse.Namespace(
        steps=200_000, full_graph=False, png="")) == 0
