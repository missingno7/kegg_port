"""dos_re 3.0 authored overrides for recovered Krypton Egg routines.

Each recovered routine is one authored override = descriptor + semantic body
(the pure `kegg.recovered` function) + a backend adapter that marshals it into
protected-mode CPU state.  The adapter *is* the port's existing VM hook: it
installs the register/flag/memory reproduction into `cpu.replacement_hooks` at
the routine's flat EIP.  Selection and installation are owned by the execution
plan (`plan_execution` + `bind_execution_plan`), not by eager `install_*_hooks`.

Stage 0 migrates one routine end-to-end (`rects_overlap`, 0x11B5DF) to prove the
chain; the remaining 15 follow the same shape.
"""
from __future__ import annotations

from dos_re.execution import (BackendAdapter, INTERPRETED_CPU_CARRIER,
                              ImplementationCatalog, ImplementationDescriptor,
                              ImplementationEntry, ImplementationOrigin,
                              OverrideCategory, ProgramCoverage, RecoveryLevel,
                              plan_execution, profile_configuration)

from kegg.identity import PROGRAM, function_id
from kegg.logic_hooks import RECTS_OVERLAP, rects_overlap_11b5df
from kegg.recovered.physics import rects_overlap

# (eip, semantic body, cpu adapter (the existing VM hook), override id).  The
# adapter and the body encode the same rule; the oracle keeps them in step.
_OVERRIDES = (
    (RECTS_OVERLAP, rects_overlap, rects_overlap_11b5df, "rects_overlap"),
)


def _authored_entry(image, eip: int, body, cpu_adapter, name: str) -> ImplementationEntry:
    target = function_id(image, eip)

    def activate(runtime, targets):
        # The backend adapter marshals the semantic body into machine state:
        # it installs the CPU adapter at the routine's flat EIP.  A selected
        # implementation with no adapter for the carrier is a hard error, so
        # this is the only install path.
        runtime.cpu.replacement_hooks[eip] = cpu_adapter
        runtime.cpu.hook_names[eip] = name

    return ImplementationEntry(
        descriptor=ImplementationDescriptor(
            implementation_id=name,
            targets=frozenset({target}),
            origin=ImplementationOrigin.AUTHORED,
            category=OverrideCategory.FAITHFUL,
            recovery_level=RecoveryLevel.AUTHORED_NATIVE,
            properties=frozenset({"cpu-adapted", "dos-memory-backed"}),
            implementation_digest=f"{name}:v1",
        ),
        implementation=body,
        adapters=(BackendAdapter(
            f"{name}/interpreted", INTERPRETED_CPU_CARRIER, activate,
            f"{name}:adapter",
        ),),
    )


def authored_entries(image) -> list[ImplementationEntry]:
    """The authored overrides for this image, one per recovered routine."""
    return [_authored_entry(image, eip, body, adapter, name)
            for eip, body, adapter, name in _OVERRIDES]


def authored_ids() -> tuple[str, ...]:
    return tuple(name for _, _, _, name in _OVERRIDES)


def authored_catalog(image) -> ImplementationCatalog:
    return ImplementationCatalog(tuple(authored_entries(image)))


def authored_plan(image):
    """A minimal ExecutionPlan selecting exactly the authored overrides.

    Coverage roots are the override targets themselves; the interpreted CPU
    carries everything else while these run as verified seams.  This is the
    development-profile slice the focused verifier proves.
    """
    catalog = authored_catalog(image)
    targets = frozenset(next(iter(e.descriptor.targets))
                        for e in catalog_entries(catalog))
    coverage = ProgramCoverage(
        roots=tuple(sorted(targets)),
        reachable=targets,
        evidence_identity="krypton-egg-authored",
    )
    config = profile_configuration(
        "development",
        program_identity=str(PROGRAM),
        selected_overrides=authored_ids(),
    )
    return plan_execution(config, coverage, catalog)


def catalog_entries(catalog: ImplementationCatalog):
    """The ImplementationEntry objects behind a catalog's descriptors."""
    return [catalog.entry(d.implementation_id) for d in catalog.implementations]
