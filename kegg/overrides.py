"""dos_re 3.0 authored overrides for the recovered Krypton Egg routines.

Each recovered routine is one authored override = descriptor + semantic body
(the pure ``kegg.recovered`` function it realizes) + a backend adapter that
marshals it into protected-mode CPU state.  The adapter *is* the port's VM
hook: it installs the register/flag/memory reproduction into
``cpu.replacement_hooks`` at the routine's flat EIP.  Selection and
installation are owned by the execution plan (``plan_execution`` +
``bind_execution_plan``), not by eager ``install_*_hooks``.

The catalog is data-driven: :data:`_OVERRIDES` lists every recovered routine as
an :class:`_Override`.  The adapter and the body encode the same rule; the
differential oracle keeps them in step.  The whole port is declared here — the
plan carries all of it, and the interpreted original ASM runs everything not
listed.
"""
from __future__ import annotations

from typing import NamedTuple, Callable

from dos_re.execution import (BackendAdapter, INTERPRETED_CPU_CARRIER,
                              ImplementationCatalog, ImplementationDescriptor,
                              ImplementationEntry, ImplementationOrigin,
                              OverrideCategory, ProgramCoverage, RecoveryLevel,
                              plan_execution, profile_configuration)

from kegg.identity import PROGRAM, function_id

# --- the recovered semantic bodies (pure; stay dos_re-free) ------------------
from kegg.recovered.anim import (build_draw_list, load_current_object,
                                  setup_sprite_rect, update_anim_timers,
                                  update_frame_timers)
from kegg.recovered.collision import process_brick_list, remove_list_element
from kegg.recovered.effects import spawn_effect
from kegg.recovered.physics import rects_overlap, swap_ball_y
from kegg.recovered.present import (set_clip_rect, set_draw_params,
                                    swap_display_pages)
from kegg.recovered.rle_blit import decode_plane_pass
from kegg.recovered.sequence import step_sequence

# --- the CPU adapters (the port's existing VM hooks) -------------------------
from kegg.composition_hooks import (process_brick_list_114085,
                                     remove_list_element_114291)
from kegg.logic_hooks import (anim_timers_118345, build_draw_list_1183b1,
                              load_object_1195ee, rects_overlap_11b5df,
                              set_clip_rect_11b57a, set_draw_params_11b541,
                              spawn_effect_117e62, sprite_bounds_118004,
                              step_sequence_11b17e, swap_ball_y_11eda0,
                              swap_display_pages_11c886,
                              update_frame_timers_119e54)
from kegg.render_hooks import blit_1222d1, blit2_1225ff

# Property tags carried on every faithful DOS-memory-backed override.
_FAITHFUL = frozenset({"cpu-adapted", "dos-memory-backed"})
# Composed (non-leaf) routines call other routines through ``cpu.call_through``
# (a 3.0 *hook* = temporary cross-owner interception); their adapter reproduces
# only the observable memory effect the caller consumes.
_COMPOSED = _FAITHFUL | {"composed", "call-through"}


class _Override(NamedTuple):
    eip: int                 # the routine's flat protected-mode entry
    body: Callable           # the pure recovered function it realizes (semantic)
    adapter: Callable        # the CPU adapter installed at the seam (the VM hook)
    name: str                # stable override id
    properties: frozenset    # descriptor property tags
    category: OverrideCategory


def _leaf(eip, body, adapter, name):
    return _Override(eip, body, adapter, name, _FAITHFUL, OverrideCategory.FAITHFUL)


def _composed(eip, body, adapter, name):
    return _Override(eip, body, adapter, name, _COMPOSED, OverrideCategory.FAITHFUL)


# The whole recovered set, one row per routine.  ``body`` names the pure
# semantic function; where the recovered algorithm still lives inline in the
# adapter (the two Mode X blitters), ``body`` points at its closest pure
# decoder / the adapter itself, pending a clean ``recovered/`` extraction.
_OVERRIDES: tuple[_Override, ...] = (
    # rendering island (Mode X planar sprite blitters)
    _leaf(0x1222D1, decode_plane_pass, blit_1222d1, "blit_planar_1222d1"),
    _leaf(0x1225FF, blit2_1225ff, blit2_1225ff, "blit_erase_1225ff"),
    # gameplay-logic leaves
    _leaf(0x118345, update_anim_timers, anim_timers_118345, "anim_timers_118345"),
    _leaf(0x1183B1, build_draw_list, build_draw_list_1183b1, "build_draw_list_1183b1"),
    _leaf(0x1195EE, load_current_object, load_object_1195ee, "load_object_1195ee"),
    _leaf(0x118004, setup_sprite_rect, sprite_bounds_118004, "sprite_bounds_118004"),
    _leaf(0x11EDA0, swap_ball_y, swap_ball_y_11eda0, "swap_ball_y_11eda0"),
    _leaf(0x11B5DF, rects_overlap, rects_overlap_11b5df, "rects_overlap"),
    _leaf(0x11B17E, step_sequence, step_sequence_11b17e, "step_sequence_11b17e"),
    _leaf(0x11C886, swap_display_pages, swap_display_pages_11c886, "swap_display_pages_11c886"),
    _leaf(0x11B57A, set_clip_rect, set_clip_rect_11b57a, "set_clip_rect_11b57a"),
    _leaf(0x11B541, set_draw_params, set_draw_params_11b541, "set_draw_params_11b541"),
    _leaf(0x117E62, spawn_effect, spawn_effect_117e62, "spawn_effect_117e62"),
    _leaf(0x119E54, update_frame_timers, update_frame_timers_119e54, "update_frame_timers_119e54"),
    # composed (non-leaf) routines — verified by observable memory effect
    _composed(0x114085, process_brick_list, process_brick_list_114085, "process_brick_list_114085"),
    _composed(0x114291, remove_list_element, remove_list_element_114291, "remove_list_element_114291"),
)

#: The flat EIPs the port overrides — the plan's coverage roots.
OVERRIDE_EIPS: tuple[int, ...] = tuple(o.eip for o in _OVERRIDES)


def _authored_entry(image, override: _Override) -> ImplementationEntry:
    target = function_id(image, override.eip)
    eip, adapter, name = override.eip, override.adapter, override.name

    def activate(runtime, targets):
        # The backend adapter marshals the semantic body into machine state: it
        # installs the CPU adapter at the routine's flat EIP.  A selected
        # implementation with no adapter for the carrier is a hard error, so
        # this is the only install path.
        runtime.cpu.replacement_hooks[eip] = adapter
        runtime.cpu.hook_names[eip] = name

    return ImplementationEntry(
        descriptor=ImplementationDescriptor(
            implementation_id=name,
            targets=frozenset({target}),
            origin=ImplementationOrigin.AUTHORED,
            category=override.category,
            recovery_level=RecoveryLevel.AUTHORED_NATIVE,
            properties=override.properties,
            implementation_digest=f"{name}:v1",
        ),
        implementation=override.body,
        adapters=(BackendAdapter(
            f"{name}/interpreted", INTERPRETED_CPU_CARRIER, activate,
            f"{name}:adapter",
        ),),
    )


def authored_entries(image) -> list[ImplementationEntry]:
    """The authored overrides for this image, one per recovered routine."""
    return [_authored_entry(image, o) for o in _OVERRIDES]


def authored_ids() -> tuple[str, ...]:
    return tuple(o.name for o in _OVERRIDES)


def authored_catalog(image) -> ImplementationCatalog:
    return ImplementationCatalog(tuple(authored_entries(image)))


def authored_coverage(image) -> ProgramCoverage:
    """Coverage whose roots are the override targets themselves; the
    interpreted CPU carries everything else while these run as verified seams."""
    targets = frozenset(function_id(image, o.eip) for o in _OVERRIDES)
    return ProgramCoverage(
        roots=tuple(sorted(targets)),
        reachable=targets,
        evidence_identity="krypton-egg-authored",
    )


def authored_plan(image, *, profile: str = "development"):
    """A minimal ExecutionPlan selecting exactly the authored overrides.

    The development-profile slice the differential verifier proves; the whole
    catalog binds through ``bind_execution_plan`` with no eager installation.
    """
    config = profile_configuration(
        profile,
        program_identity=str(PROGRAM),
        selected_overrides=authored_ids(),
    )
    return plan_execution(config, authored_coverage(image), authored_catalog(image))


def catalog_entries(catalog: ImplementationCatalog):
    """The ImplementationEntry objects behind a catalog's descriptors."""
    return [catalog.entry(d.implementation_id) for d in catalog.implementations]
