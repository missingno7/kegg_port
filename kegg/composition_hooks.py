"""Recovered *composed* (non-leaf) CPU adapters for Krypton Egg.

These functions are the *backend adapters* of the composed overrides in
`kegg.overrides` (carrying the {composed, call-through} properties); the plan
installs them into `cpu.replacement_hooks` via `bind_execution_plan`.  They
call other routines in the original, so they are verified by the
observable-state composition verifier (dos_re/pm_composition.py), not the
strict full-machine diff.  Each is installed only where the original's result
registers are dead at the call site, so the adapter only has to reproduce the
routine's memory effects and return; the transient stack frame and scratch
registers are left alone.

Kept separate from `logic_hooks` (the strict, leaf adapters) so the strict
verifier never tries to full-diff a composed routine.
"""
from __future__ import annotations

from kegg.recovered.collision import remove_list_element, process_brick_list

REMOVE_LIST_ELEM = 0x114291
PROCESS_BRICKS = 0x114085


def process_brick_list_114085(cpu):
    # The ball-vs-brick loop: composed pure logic + the per-type handler
    # delegated to the interpreter (Watcom register ABI is irrelevant — the
    # handlers read globals we maintain, not caller registers).
    process_brick_list(cpu.mem.data, lambda h: cpu.call_through(h, ()))
    cpu.eip = cpu.pop(4)


def remove_list_element_114291(cpu):
    # The caller discards this routine's result registers (it reloads its loop
    # state from memory), so we only reproduce the observable memory effect and
    # return; scratch regs/frame are irrelevant (proven by the composition
    # verifier).
    remove_list_element(cpu.mem.data)
    cpu.eip = cpu.pop(4)
