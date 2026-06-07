# ABOUTME: Samples the camera's view of the infinite world into an RGB grid.
# ABOUTME: Combines fbm height, directional hillshade, and biome coloring.

import numpy as np

from .noise import fbm
from .palette import colorize


class World:
    """A seeded, infinite terrain that can be sampled for any camera window."""

    def __init__(self, seed: int = 1337, octaves: int = 5):
        from .noise import make_perm

        self.perm = make_perm(seed)
        self.octaves = octaves
        self.shade_strength = 9.0

    def sample(
        self, width: int, height: int, cam_x: float, cam_y: float, scale: float
    ) -> np.ndarray:
        """Render a (height, width, 3) uint8 grid for the given camera window.

        cam_x / cam_y are offsets in pixel units; scale is noise units per pixel.
        """
        xs = (np.arange(width) + cam_x) * scale
        ys = (np.arange(height) + cam_y) * scale
        gx, gy = np.meshgrid(xs, ys)

        h = fbm(gx, gy, self.perm, self.octaves)
        h = (h + 1.0) * 0.5  # [-1,1] -> [0,1]

        rgb = colorize(h)
        rgb = self._shade(h, rgb)
        return np.clip(rgb, 0, 255).astype(np.uint8)

    def _shade(self, h: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """Brighten slopes facing the light and darken those away from it."""
        dy, dx = np.gradient(h)
        illum = (-dx - dy) * self.shade_strength
        factor = np.clip(1.0 + illum, 0.55, 1.45)[..., None]
        return rgb * factor
