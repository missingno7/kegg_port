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

import json
from typing import NamedTuple, Callable

from pathlib import Path

from dos_re.execution import (BackendAdapter, INTERPRETED_CPU_CARRIER,
                              ImplementationCatalog, ImplementationDescriptor,
                              ImplementationEntry, ImplementationOrigin,
                              OverrideCategory, ProgramCoverage, RecoveryLevel,
                              bind_plan_implementations, plan_execution,
                              profile_configuration)
from dos_re.lift.install import activate_generated_graph32

from kegg.identity import PROGRAM, function_id, image_identity

# --- the recovered semantic bodies (pure; stay dos_re-free) ------------------
from kegg.recovered.anim import (build_draw_list, load_current_object,
                                  setup_sprite_rect, update_anim_timers,
                                  update_frame_timers)
from kegg.recovered.collision import process_brick_list, remove_list_element
from kegg.recovered.effects import spawn_effect
from kegg.recovered.physics import rects_overlap, swap_ball_y
from kegg.recovered.present import (deinterleave_plane, fade_palette_stream,
                                    set_clip_rect, set_draw_params,
                                    swap_display_pages)
from kegg.recovered.gif import decode_gif
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
from kegg.render_hooks import (blit_1222d1, blit2_1225ff,
                               blit_queue_entry_122288)
from kegg.asset_hooks import (gif_decode_121df8, palette_fade_123a48,
                              planar_upload_122f30)

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
    # the queue-writer entry that falls into the blitter: one native op per
    # draw (the interpreted prologue was the largest CPython frame cost)
    _leaf(0x122288, decode_plane_pass, blit_queue_entry_122288,
          "blit_queue_entry_122288"),
    # asset unpacker: the GIF87a LZW image decoder (title/menu/score screens) —
    # the hottest load routine (~3.86M interpreted instr per screen on CPython)
    _leaf(0x121DF8, decode_gif, gif_decode_121df8, "gif_decode_121df8"),
    # the VGA palette fade that follows each image load (per-frame during
    # title/menu fades -- the biggest interpreted cost left in that path)
    _leaf(0x123A48, fade_palette_stream, palette_fade_123a48, "palette_fade_123a48"),
    # linear -> Mode X planar upload: what puts a decoded image on screen
    _leaf(0x122F30, deinterleave_plane, planar_upload_122f30, "planar_upload_122f30"),
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

# --- the generated (lifted-vmless) hot-set graph ----------------------------
# The measured worst-case hot game-logic functions (~92% of interpreted work
# once the render overrides are in) lifted to per-instruction Python that skips
# the interpreter's fetch/decode/dispatch — the CPython/mobile accelerator.
# Disjoint from the authored EIPs; runs on the same interpreted-cpu carrier
# (the lifted functions install into cpu.replacement_hooks like the authored
# adapters).  Proven byte-exact against the ASM oracle over the ball-heavy
# gameplay snapshot.
GRAPH_HOT_DIR = Path(__file__).resolve().parent / "graph_hot"
# NB: 0x121DF8 (the GIF decoder) was a member until it became an authored
# override (gif_decode_121df8); authored EIPs and the generated graphs must
# stay disjoint, so it is intentionally absent here.
GRAPH_HOT_EIPS: tuple[int, ...] = (
    0x1185A4, 0x122D5F, 0x1191A3, 0x117BF4, 0x118066,
    0x122A9C, 0x122B94, 0x11B1DF, 0x1230B7,
)
GENERATED_GRAPH_ID = "generated-hot-graph"

# --- the generated full-game graph (whole-program lifted-vmless) -------------
# Every statically-liftable KE function lifted and linked, MINUS the convergence
# exclusions (environment waits + stack-switch/computed-transfer routines) and
# the authored EIPs above (authored adapters win -- calls into them fall through
# to emulate_call32).  The superset of the hot-set graph; the CPython/mobile
# accelerator at whole-game scope and the evidence base for a future detached
# build.  The module bodies (~14 MB) are gitignored and rebuilt from KE.EXE by
# scripts/build_full_graph.py; graph_full.manifest.json is the committed
# reproducibility contract and the source of GRAPH_FULL_EIPS.
GRAPH_FULL_DIR = Path(__file__).resolve().parent / "graph_full"
MANIFEST_PATH = Path(__file__).resolve().parent / "graph_full.manifest.json"
GENERATED_FULL_GRAPH_ID = "generated-full-graph"


def _load_full_graph_eips() -> tuple[int, ...]:
    """The full-graph target EIPs from the committed manifest (empty until
    ``scripts/build_full_graph.py --write-manifest`` has populated it)."""
    try:
        data = json.loads(MANIFEST_PATH.read_text())
    except FileNotFoundError:
        return ()
    return tuple(int(x, 16) for x in data.get("graph_eips", ()))


GRAPH_FULL_EIPS: tuple[int, ...] = _load_full_graph_eips()


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


def _generated_graph_entry(image, impl_id, eips, graph_dir,
                           *, require_built=False) -> ImplementationEntry:
    """A lifted-vmless generated graph as one GENERATED implementation.

    Generated implementations use the BASELINE category (they reproduce the
    original, they don't author new behavior).  The backend adapter activates
    the whole graph directory through ``activate_generated_graph32`` — the
    lifted modules install into ``cpu.replacement_hooks`` on the interpreted
    CPU carrier, exactly like the authored adapters, so authored overrides at
    shared EIPs still win (both graph sets are disjoint from the authored EIPs
    by construction).  ``require_built`` fails loud when the graph directory is
    empty (the full graph is gitignored and emitted on demand by
    ``scripts/build_full_graph.py``).
    """
    targets = frozenset(function_id(image, e) for e in eips)

    def activate(runtime, _targets):
        if require_built and not any(graph_dir.glob("lift_*.py")):
            raise FileNotFoundError(
                f"{graph_dir} is empty — build the full graph first: "
                f"python scripts/build_full_graph.py")
        activate_generated_graph32(runtime.cpu, graph_dir)

    return ImplementationEntry(
        descriptor=ImplementationDescriptor(
            implementation_id=impl_id,
            targets=targets,
            origin=ImplementationOrigin.GENERATED,
            category=OverrideCategory.BASELINE,
            recovery_level=RecoveryLevel.GENERATED_VMLESS,
            properties=frozenset({"cpu-adapted", "dos-memory-backed",
                                  "lifted", "linked"}),
            implementation_digest=f"{impl_id}:v1",
        ),
        adapters=(BackendAdapter(
            f"{impl_id}/interpreted", INTERPRETED_CPU_CARRIER,
            activate, f"{impl_id}:adapter",
        ),),
    )


def _generated_selection(*, generated_graph=False, full_graph=False):
    """``(impl_id, eips)`` for the selected generated graph, or ``(None, ())``.

    ``full_graph`` supersedes ``generated_graph``: the full graph is a superset
    of the hot-set graph, and two generated entries cannot both own the shared
    hot EIPs, so at most one generated graph is ever selected.
    """
    if full_graph:
        return GENERATED_FULL_GRAPH_ID, GRAPH_FULL_EIPS
    if generated_graph:
        return GENERATED_GRAPH_ID, GRAPH_HOT_EIPS
    return None, ()


def _selected_generated_entry(image, impl_id) -> ImplementationEntry:
    if impl_id == GENERATED_FULL_GRAPH_ID:
        return _generated_graph_entry(image, impl_id, GRAPH_FULL_EIPS,
                                      GRAPH_FULL_DIR, require_built=True)
    return _generated_graph_entry(image, impl_id, GRAPH_HOT_EIPS, GRAPH_HOT_DIR)


def authored_entries(image) -> list[ImplementationEntry]:
    """The authored overrides for this image, one per recovered routine."""
    return [_authored_entry(image, o) for o in _OVERRIDES]


def authored_ids() -> tuple[str, ...]:
    return tuple(o.name for o in _OVERRIDES)


def authored_catalog(image, *, generated_graph: bool = False,
                     full_graph: bool = False) -> ImplementationCatalog:
    entries = authored_entries(image)
    impl_id, _ = _generated_selection(generated_graph=generated_graph,
                                      full_graph=full_graph)
    if impl_id is not None:
        entries.append(_selected_generated_entry(image, impl_id))
    return ImplementationCatalog(tuple(entries))


def selected_ids(*, generated_graph: bool = False,
                 full_graph: bool = False) -> tuple[str, ...]:
    impl_id, _ = _generated_selection(generated_graph=generated_graph,
                                      full_graph=full_graph)
    ids = authored_ids()
    return ids + (impl_id,) if impl_id is not None else ids


def authored_coverage(image, *, generated_graph: bool = False,
                      full_graph: bool = False) -> ProgramCoverage:
    """Coverage whose roots are the override targets themselves; the
    interpreted CPU carries everything else while these run as verified seams."""
    targets = frozenset(function_id(image, o.eip) for o in _OVERRIDES)
    _, eips = _generated_selection(generated_graph=generated_graph,
                                   full_graph=full_graph)
    targets |= frozenset(function_id(image, e) for e in eips)
    return ProgramCoverage(
        roots=tuple(sorted(targets)),
        reachable=targets,
        evidence_identity="krypton-egg-authored",
    )


def authored_plan(image, *, profile: str = "development",
                  generated_graph: bool = False, full_graph: bool = False):
    """A minimal ExecutionPlan selecting the authored overrides.

    The development-profile slice the differential verifier proves; the whole
    catalog binds through ``bind_execution_plan`` with no eager installation.
    ``generated_graph=True`` additionally selects the lifted-vmless hot-set
    graph (the CPython/mobile accelerator); ``full_graph=True`` selects the
    whole-game graph instead (superset of the hot set).  Both are disjoint from
    the authored EIPs, which always win at their seams.
    """
    config = profile_configuration(
        profile,
        program_identity=str(PROGRAM),
        selected_overrides=selected_ids(generated_graph=generated_graph,
                                        full_graph=full_graph),
    )
    return plan_execution(
        config,
        authored_coverage(image, generated_graph=generated_graph,
                          full_graph=full_graph),
        authored_catalog(image, generated_graph=generated_graph,
                         full_graph=full_graph))


def bind_overrides(rt, exe_path, *, profile: str = "development",
                   generated_graph: bool = False, full_graph: bool = False):
    """Bind the authored override plan onto an already-booted runtime.

    The convenience install path: builds the plan for ``exe_path`` and binds it
    through ``bind_plan_implementations`` (the same seam the player uses), so
    every recovered override installs.  ``create_game_runtime`` and the oracle
    tests call this instead of the retired eager ``install_*_hooks``.
    ``generated_graph=True`` also installs the lifted-vmless hot-set graph;
    ``full_graph=True`` installs the whole-game graph instead.  Returns the
    bound plan.
    """
    plan = authored_plan(image_identity(exe_path), profile=profile,
                         generated_graph=generated_graph, full_graph=full_graph)
    bind_plan_implementations(rt, plan, carrier_id=INTERPRETED_CPU_CARRIER)
    return plan


def catalog_entries(catalog: ImplementationCatalog):
    """The ImplementationEntry objects behind a catalog's descriptors."""
    return [catalog.entry(d.implementation_id) for d in catalog.implementations]
