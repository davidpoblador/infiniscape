# ABOUTME: Turns an RGB pixel grid into an ANSI half-block frame string.
# ABOUTME: Coalesces repeated colors and draws optional sprite glyphs.

import numpy as np

_UPPER_HALF = "▀"  # fg paints the top pixel, bg paints the bottom pixel


def render(
    rgb: np.ndarray, chars: np.ndarray | None = None, fg: np.ndarray | None = None
) -> str:
    """Build a full-frame string from an (H, W, 3) uint8 grid (H even).

    Each cell is the usual two-pixel half block, or, where chars[r, c] is set, a
    glyph in fg[r, c] over the cell's terrain color. The color escape is emitted
    only when it changes from the previous cell, so flat runs (e.g. the dark area
    outside the player's light) collapse to bare glyphs.
    """
    top = rgb[0::2].tolist()
    bottom = rgb[1::2].tolist()
    has_sprites = chars is not None
    chars_l = chars.tolist() if has_sprites else None
    fg_l = fg.tolist() if has_sprites else None

    out = ["\x1b[H"]
    for r in range(len(top)):
        out.append(f"\x1b[{r + 1};1H")
        trow, brow = top[r], bottom[r]
        crow = chars_l[r] if has_sprites else None
        frow = fg_l[r] if has_sprites else None
        parts = []
        prev = None  # last emitted (fr, fg, fb, br, bg, bb)
        for x in range(len(trow)):
            t, b = trow[x], brow[x]
            if has_sprites and crow[x]:
                f = frow[x]
                key = (
                    f[0],
                    f[1],
                    f[2],
                    (t[0] + b[0]) // 2,
                    (t[1] + b[1]) // 2,
                    (t[2] + b[2]) // 2,
                )
                glyph = crow[x]
            else:
                key = (t[0], t[1], t[2], b[0], b[1], b[2])
                glyph = _UPPER_HALF
            if key == prev:
                parts.append(glyph)
            else:
                parts.append(
                    f"\x1b[38;2;{key[0]};{key[1]};{key[2]};48;2;{key[3]};{key[4]};{key[5]}m{glyph}"
                )
                prev = key
        out.append("".join(parts))
    out.append("\x1b[0m")
    return "".join(out)
