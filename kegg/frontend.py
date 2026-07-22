"""The Krypton Egg protected-mode frontend (dos_re 3.0).

A thin :class:`dos_re.pm_backend.PMFrontend` subclass that declares the port's
execution plan: the authored override catalog (``kegg.overrides``), coverage
over exactly those recovered routines, and a configuration that selects them
all.  ``dos_re.player.main`` resolves this into an immutable ``ExecutionPlan``
before boot and binds it (``bind_execution_plan``) — the plan owns installation,
so the runtime boots the pure interpreted oracle and the seams arrive through
the bound adapters.  Everything the catalog does not cover runs as the
untouched original ASM.
"""
from __future__ import annotations

from dataclasses import replace

from dos_re.execution import ImplementationCatalog, ProgramCoverage
from dos_re.pm_backend import PMFrontend

from kegg.identity import PROGRAM, image_identity
from kegg.overrides import (authored_catalog, authored_coverage, authored_ids)


class KryptonEggFrontend(PMFrontend):
    """PM frontend whose plan carries the recovered override catalog."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._image_cache: tuple[str, object] | None = None

    def _image(self, args):
        # image_identity content-addresses KE.EXE; cache per exe path so
        # resolve/plan-only/launch don't re-hash the file each call.
        exe = str(args.exe)
        if self._image_cache is None or self._image_cache[0] != exe:
            self._image_cache = (exe, image_identity(exe))
        return self._image_cache[1]

    # --- execution planning --------------------------------------------------

    def program_identity(self, args) -> str:
        return str(PROGRAM)

    def execution_implementations(self, args) -> ImplementationCatalog:
        return authored_catalog(self._image(args))

    def execution_coverage(self, args) -> ProgramCoverage:
        return authored_coverage(self._image(args))

    def execution_configuration(self, args):
        # Keep the base configuration (bootstrap provider, requested
        # capabilities, profile policy) and add our override selection.
        config = super().execution_configuration(args)
        return replace(config, selected_overrides=authored_ids())
