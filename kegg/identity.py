"""Stable dos_re 3.0 identities for the Krypton Egg port.

One `ProgramIdentity`, one `ImageIdentity` per original executable, and a
`function_id(image, eip)` helper that produces the opaque `FunctionIdentity`
string used as an override target, a coverage-reachable id, and an Atlas key.
Addresses only *seed* an identity; the string stays opaque (`dos_re/identity.py`).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from dos_re.identity import (FunctionIdentity, ImageIdentity, ProgramIdentity,
                             flat_address)

PROGRAM = ProgramIdentity("krypton-egg:1")
IMAGE_LABEL = "KE.EXE"
ADDRESS_SPACE = "protected-mode"


def image_identity(exe_path: str | Path) -> ImageIdentity:
    """The content-addressed identity of the original executable."""
    digest = hashlib.sha256(Path(exe_path).read_bytes()).hexdigest()
    return ImageIdentity(PROGRAM, IMAGE_LABEL, "sha256", digest)


def function_id(image: ImageIdentity, eip: int) -> str:
    """Stable identity string for a recovered function at flat protected-mode EIP."""
    return str(FunctionIdentity(image, ADDRESS_SPACE, flat_address(eip)))
