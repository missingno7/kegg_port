"""Pure recovered game logic for Krypton Egg.

Layer rule (enforced by dos_re/tools/audit_layers.py): NOTHING here imports
dos_re, and nothing here knows segment:offset or VM state — these are plain
functions over plain data (bytes/bytearrays/ints).  Hooks in the adapter
marshal VM state into and out of them.
"""
