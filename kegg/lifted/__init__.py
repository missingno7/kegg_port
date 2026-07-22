"""Generated-baseline lifted functions for Krypton Egg — installable as a fleet.

Each module here is a mechanically lifted 32-bit function (dos_re.lift
pipeline) that PASSED the strict PM differential verifier in situ (see
manifest.md).  These are the generated baseline the hand-recovered ``kegg/
recovered`` overrides grew from; the live port installs the overrides through
the execution plan (``kegg.overrides``), not these.  ``install_lifted``
registers them on a CPU386 by their entry address for evidence/benchmark runs;
every one self-checks its entry signature at call time, so a wrong image (or
self-modified code) fails loud rather than running a stale replacement.

These are literal lifts — per-original-instruction Python — but they skip the
interpreter's fetch/decode/dispatch, a ~2.5x speedup over the pure interpreter
for the render-heavy inner loop they cover (measured on the gameplay
snapshot).  Refactoring them into bulk ``recovered/`` code is the next lever;
until then, installing them is a free, oracle-proven win.
"""
from __future__ import annotations

from . import lift_1222d1, lift_122288

_MODULES = (lift_1222d1, lift_122288)


def install_lifted(cpu) -> int:
    """Register every verified lifted function on ``cpu``.  Returns the count."""
    for mod in _MODULES:
        entry = mod.ENTRY
        name = next(n for n in dir(mod) if n.startswith("lift_"))
        cpu.replacement_hooks[entry] = getattr(mod, name)
        cpu.hook_names[entry] = name
    return len(_MODULES)
