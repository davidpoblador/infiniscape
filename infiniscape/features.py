# ABOUTME: Scatters biome-appropriate sprite glyphs across the terrain.
# ABOUTME: Placement is a deterministic hash of world cell, so it is stable.

import numpy as np


def _hash01(ix: np.ndarray, iy: np.ndarray, salt: int) -> np.ndarray:
    """Stable pseudo-random value in [0,1) per integer world cell."""
    h = (
        ix.astype(np.int64) * np.int64(374761393)
        + iy.astype(np.int64) * np.int64(668265263)
        + np.int64(salt) * np.int64(362437)
    )
    h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
    return (h & np.int64(0xFFFFFF)).astype(np.float64) / 0xFFFFFF


def build_features(
    elevation: np.ndarray, moisture: np.ndarray, base_x: int, base_y: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return (chars, fg) cell grids: a glyph ('' = none) and its color per cell.

    elevation / moisture are per-cell fields in [0,1]; base_x / base_y are the
    world-cell coordinates of the top-left cell (x in pixels, y in 2px cells), so
    sprites stay locked to the world as the camera scrolls in either axis.
    """
    rows, cols = elevation.shape
    ix = base_x + np.arange(cols)
    iy = base_y + np.arange(rows)
    gx, gy = np.meshgrid(ix, iy)
    r1 = _hash01(gx, gy, 1)
    r2 = _hash01(gx, gy, 2)

    chars = np.full((rows, cols), "", dtype=object)
    fg = np.zeros((rows, cols, 3), dtype=np.uint8)

    def place(mask: np.ndarray, glyph: str, color: tuple[int, int, int]) -> None:
        m = mask & (chars == "")
        chars[m] = glyph
        fg[m] = color

    e, mo = elevation, moisture

    # ripples on open water
    place((e < 0.47) & (r1 < 0.05), "~", (120, 178, 212))

    # forests on vegetated slopes, denser where it is wetter
    veg = (e >= 0.55) & (e < 0.84)
    density = np.where(
        mo > 0.62, 0.34, np.where(mo > 0.42, 0.16, np.where(mo > 0.24, 0.04, 0.0))
    )
    wooded = veg & (r1 < density)
    place(wooded & (r2 < 0.5), "♠", (28, 74, 38))
    place(wooded & (r2 >= 0.5), "♣", (40, 96, 50))

    # sparse scrub on dry lowland
    place((e >= 0.55) & (e < 0.72) & (mo < 0.30) & (r1 < 0.07), "Y", (132, 138, 70))

    # grass tufts on the remaining low meadows
    place((e >= 0.55) & (e < 0.66) & (r1 < 0.12), '"', (96, 138, 64))

    # rocks high up, snowy peaks at the top
    place((e >= 0.84) & (e < 0.97) & (r1 < 0.10), "•", (78, 74, 64))
    place((e >= 0.97) & (r1 < 0.07), "▲", (228, 228, 232))

    return chars, fg
