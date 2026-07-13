"""Recovered *composed* (non-leaf) routines, installed as VM hooks.

These call other routines in the original, so they are verified by the
observable-state composition verifier (dos_re/pm_composition.py), not the
strict full-machine diff.  Each is installed only where the original's result
registers are dead at the call site, so the hook only has to reproduce the
routine's memory effects and return; the transient stack frame and scratch
registers are left alone.

Kept separate from `logic_hooks` (the strict, leaf hooks) so the strict
verifier never tries to full-diff a composed routine.
"""
from __future__ import annotations

from kegg.recovered.collision import remove_list_element

REMOVE_LIST_ELEM = 0x114291


def remove_list_element_114291(cpu):
    # The caller discards this routine's result registers (it reloads its loop
    # state from memory), so we only reproduce the observable memory effect and
    # return; scratch regs/frame are irrelevant (proven by the composition
    # verifier).
    remove_list_element(cpu.mem.data)
    cpu.eip = cpu.pop(4)


def install_composition_hooks(cpu) -> int:
    cpu.replacement_hooks[REMOVE_LIST_ELEM] = remove_list_element_114291
    cpu.hook_names[REMOVE_LIST_ELEM] = "remove_list_element_114291"
    return 1
