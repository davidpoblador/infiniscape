# ABOUTME: Samples the camera's view of the infinite world into an RGB grid.
# ABOUTME: Combines fbm elevation, a moisture field, hillshade, and biomes.

import numpy as np

from .noise import fbm, make_perm
from .palette import colorize


class World:
    """A seeded, infinite terrain that can be sampled for any camera window."""

    def __init__(self, seed: int = 1337, octaves: int = 5):
        self.perm = make_perm(seed)
        self.moist_perm = make_perm(seed + 7919)  # independent biome moisture
        self.octaves = octaves
        self.shade_strength = 9.0

    def sample(
        self,
        width: int,
        height: int,
        cam_x: float,
        cam_y: float,
        scale: float,
        sea_level: float = 0.0,
    ) -> np.ndarray:
        """Render a (height, width, 3) uint8 grid for the given camera window.

        cam_x / cam_y are offsets in pixel units; scale is noise units per pixel.
        sea_level raises (>0, floods land) or lowers (<0, exposes land) the water.
        """
        xs = np.arange(width) + cam_x
        ys = np.arange(height) + cam_y

        gx, gy = np.meshgrid(xs * scale, ys * scale)
        h = fbm(gx, gy, self.perm, self.octaves)
        h = (h + 1.0) * 0.5  # [-1,1] -> [0,1]
        h = np.clip(h - sea_level, 0.0, 1.0)  # shift terrain against the waterline

        # Moisture varies over much larger regions, so biomes span many tiles.
        mscale = scale * 0.4
        mgx, mgy = np.meshgrid(xs * mscale, ys * mscale)
        moist = fbm(mgx, mgy, self.moist_perm, octaves=3)
        moist = (moist + 1.0) * 0.5
        moist = np.clip((moist - 0.5) * 1.5 + 0.5, 0.0, 1.0)  # widen biome range

        rgb = colorize(h, moist)
        rgb = self._shade(h, rgb)
        return np.clip(rgb, 0, 255).astype(np.uint8)

    def _shade(self, h: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """Brighten slopes facing the light and darken those away from it."""
        dy, dx = np.gradient(h)
        illum = (-dx - dy) * self.shade_strength
        factor = np.clip(1.0 + illum, 0.55, 1.45)[..., None]
        return rgb * factor
