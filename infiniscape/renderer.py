# ABOUTME: Turns an RGB pixel grid into an ANSI half-block frame string.
# ABOUTME: Each cell stacks two pixels via foreground/background truecolor.

import numpy as np

_UPPER_HALF = "▀"  # the half block; fg paints top pixel, bg paints bottom


def render(rgb: np.ndarray) -> str:
    """Build a full-frame string from an (H, W, 3) uint8 grid (H even).

    Top pixels come from even rows, bottom pixels from odd rows, so the visible
    resolution is the terminal's columns by twice its rows.
    """
    top = rgb[0::2].tolist()
    bottom = rgb[1::2].tolist()

    out = ["\x1b[H"]
    for r, (trow, brow) in enumerate(zip(top, bottom)):
        out.append(f"\x1b[{r + 1};1H")
        out.append(
            "".join(
                f"\x1b[38;2;{t[0]};{t[1]};{t[2]};48;2;{b[0]};{b[1]};{b[2]}m{_UPPER_HALF}"
                for t, b in zip(trow, brow)
            )
        )
    out.append("\x1b[0m")
    return "".join(out)
