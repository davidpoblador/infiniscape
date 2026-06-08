# ABOUTME: Player-centered view masks and the contrast-safe player color.
# ABOUTME: Shared by the live app and the offline snapshot renderer.

import numpy as np


def view_masks(
    h: int,
    w: int,
    light_radius: float,
    shadow_radius: float,
    shadow_depth: float,
    cx: float | None = None,
    cy: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (brightness, halo) masks centered on the player.

    Brightness fades the world to black at the edge of sight and digs a dark well
    around the player; halo strength (1 at the player, 0 past the shadow radius)
    drives a desaturation toward neutral grey so the shadow carries no terrain hue.
    """
    if cx is None:
        cx = w / 2
    if cy is None:
        cy = h / 2
    yy, xx = np.ogrid[0:h, 0:w]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    falloff = light_radius * 0.45
    lt = np.clip((light_radius - dist) / falloff + 1.0, 0.0, 1.0)
    light = lt * lt * (3.0 - 2.0 * lt)

    st = np.clip(dist / shadow_radius, 0.0, 1.0)
    halo = 1.0 - st * st * (3.0 - 2.0 * st)

    bright = light * (1.0 - (1.0 - shadow_depth) * halo)
    return bright[..., None], halo[..., None]


def player_color(under: np.ndarray) -> np.ndarray:
    """A contrast-guaranteed 'negative' of the pixel beneath the player.

    Colorful terrain keeps the true inverse (hue alone makes it pop); grayish
    mid-tone terrain, whose inverse would look nearly identical, is pushed to the
    opposite luminance extreme so the player never blends in.
    """
    c = under.astype(np.float64)
    inv = 255.0 - c
    lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    chroma = c.max() - c.min()
    grayness = 1.0 - chroma / 255.0
    midness = 1.0 - abs(lum - 127.5) / 127.5
    flip = 0.9 * grayness * midness
    target = 0.0 if lum > 150.0 else 255.0
    player = inv * (1.0 - flip) + target * flip
    return np.clip(player, 0, 255).astype(np.uint8)
