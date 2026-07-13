"""Recovered ball/brick collision logic for Krypton Egg (pure — no dos_re, no VM).

These are *composed* routines (they call other routines in the original), so
they are proven with the observable-state composition verifier rather than the
strict full-machine diff — see dos_re/pm_composition.py.

Operates on the flat memory bytearray plus the global addresses the routine
uses; VM-free.
"""
from __future__ import annotations

# The "active list" the collision loop compacts: an array of 0x12-byte records.
L_BASE = 0x14DDA4          # pointer to the current record
L_INDEX = 0x14DDBC         # current index
L_COUNT = 0x14DDC0         # live record count
L_STRIDE = 0x12            # record size (18 bytes)


# Play-field bounds and globals used by the ball-vs-brick loop (0x114085).
G_BALL = 0x14DEE4          # pointer to the ball object
G_BALL_RECT = 0x14E24C     # ball sprite rect {l,t,r,b}
G_BRICK_RECT = 0x14E22C    # scratch brick rect for the overlap test
BRICK_LIST = 0x14A990      # active brick-list base
G_ANIM_FLAG = 0x14E142     # if nonzero, bricks advance twice per frame
G_FRAME_BASE = 0x14DF34    # base added to the brick's animation value
G_DRAW_PARAM = 0x148DB4    # computed sprite-def / draw dword for the brick
G_HANDLER_IDX = 0x148E20   # per-type handler table index
G_HANDLER = 0x148DB8       # resolved per-type handler pointer
G_TYPE = 0x14DDB8          # hit brick's type + 1
HANDLER_TABLE = 0x146160   # dword table of per-type handlers
G_SCORE_OBJ = 0x14DDDC     # pointer to the score/energy object (+0x14 field)
G_DRAW_CURSOR = 0x14E2EC   # draw-command output cursor
FIELD_R = 0x140            # play-field right / bottom bounds (signed)
FIELD_B = 0xD8
NO_COLLIDE_Y = 0xC3        # bricks at/below this Y are drawn but not tested


def _emit_draw(d: bytearray, brick: int) -> None:
    """Emit the brick's 10-byte draw command and advance to the next record."""
    cur = int.from_bytes(d[G_DRAW_CURSOR:G_DRAW_CURSOR + 4], "little")
    d[cur:cur + 4] = d[G_DRAW_PARAM:G_DRAW_PARAM + 4]   # dword: the draw param
    d[cur + 4:cur + 6] = d[brick:brick + 2]             # word: brick x
    d[cur + 6:cur + 8] = d[brick + 4:brick + 6]         # word: brick y
    d[cur + 8:cur + 10] = b"\x00\x00"                   # word: flags
    d[G_DRAW_CURSOR:G_DRAW_CURSOR + 4] = (cur + 0xA).to_bytes(4, "little")
    d[L_BASE:L_BASE + 4] = (brick + L_STRIDE).to_bytes(4, "little")


def process_brick_list(d: bytearray, invoke_handler) -> None:
    """Ball-vs-brick collision + draw loop (recovered from 0x114085) — composed.

    Build the ball's sprite rect, then walk the active brick list: per brick,
    advance its animation counter; despawn it if it left the play field;
    otherwise test overlap with the ball — on a hit run the per-type handler
    (``invoke_handler``, delegated to the interpreter), award score and remove
    the brick; on a miss (or a brick below the collide line) emit a draw
    command and advance.
    """
    from kegg.bridge.game_state import GameState, Rect
    from kegg.recovered.anim import setup_sprite_rect
    from kegg.recovered.sequence import step_sequence
    from kegg.recovered.physics import rects_overlap
    M = 0xFFFFFFFF

    def r32(a):
        return int.from_bytes(d[a:a + 4], "little")

    def w32(a, v):
        d[a:a + 4] = (v & M).to_bytes(4, "little")

    def s32(v):
        return v - 0x100000000 if v & 0x80000000 else v

    state = GameState(d)

    # the ball's sprite rect (seed left/top with the ball position, then fold)
    ball = r32(G_BALL)
    w32(G_BALL_RECT, r32(ball))
    w32(G_BALL_RECT + 4, r32(ball + 4))
    setup_sprite_rect(state, G_BALL_RECT, r32(ball + 0x78))

    w32(L_BASE, BRICK_LIST)
    w32(L_INDEX, 0)
    while s32(r32(L_INDEX)) < s32(r32(L_COUNT)):
        brick = r32(L_BASE)
        w32(brick + 4, r32(brick + 4) + 1)              # advance the counter
        if d[G_ANIM_FLAG] != 0:
            w32(brick + 4, r32(brick + 4) + 1)          # ...twice this frame
        val = step_sequence(d, brick + 8, brick + 0xC)  # advance its animation
        w32(G_DRAW_PARAM, val + r32(G_FRAME_BASE))
        bx = s32(r32(brick))
        by = s32(r32(brick + 4))
        if bx > FIELD_R or bx < 0 or by > FIELD_B or by < 0:
            remove_list_element(d)                      # left the field -> despawn
        elif by >= NO_COLLIDE_Y:
            _emit_draw(d, brick)                        # below the collide line
        else:
            w32(G_BRICK_RECT, r32(brick))
            w32(G_BRICK_RECT + 4, r32(brick + 4))
            setup_sprite_rect(state, G_BRICK_RECT, r32(G_DRAW_PARAM))
            if rects_overlap(Rect(d, G_BALL_RECT), Rect(d, G_BRICK_RECT)):
                w32(G_TYPE, d[brick + 0x10] + 1)
                w32(G_HANDLER_IDX, d[brick + 0x11])
                if s32(r32(G_HANDLER_IDX)) >= 0x1C:
                    w32(G_HANDLER_IDX, r32(G_HANDLER_IDX) - 0x1C)
                handler = r32(HANDLER_TABLE + r32(G_HANDLER_IDX) * 4)
                w32(G_HANDLER, handler)
                invoke_handler(handler)                 # the per-type effect
                score = r32(G_SCORE_OBJ)
                shift = d[r32(G_BALL) + 0x24] & 0x1F
                w32(score + 0x14, r32(score + 0x14) + (2 << shift))
                remove_list_element(d)                  # remove the hit brick
            else:
                _emit_draw(d, brick)
        w32(L_INDEX, r32(L_INDEX) + 1)                  # index++ (loop tail)


def remove_list_element(d: bytearray, base_ptr: int = L_BASE,
                        index_ptr: int = L_INDEX, count_ptr: int = L_COUNT,
                        stride: int = L_STRIDE) -> None:
    """Remove the current record from the active list (recovered from 0x114291).

    Decrement the count; unless the current record was the last one, shift the
    tail down one slot (an overlapping forward copy — the original's memcpy at
    0x123f76); then decrement the index so the loop revisits the record now
    occupying the freed slot.
    """
    def r32(a):
        return int.from_bytes(d[a:a + 4], "little")

    def w32(a, v):
        d[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    count = (r32(count_ptr) - 1) & 0xFFFFFFFF
    w32(count_ptr, count)
    if r32(index_ptr) != count:
        nbytes = ((count - r32(index_ptr)) & 0xFFFFFFFF) * stride
        base = r32(base_ptr)
        d[base:base + nbytes] = d[base + stride:base + stride + nbytes]
    w32(index_ptr, (r32(index_ptr) - 1) & 0xFFFFFFFF)
