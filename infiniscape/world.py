# ABOUTME: Generates realistic infinite terrain: continents, mountains, rivers.
# ABOUTME: Everything is a pure function of position, so it streams and is stable.

import numpy as np

from .noise import fbm, make_perm, ridged_fbm
from .palette import colorize

_SEA = 0.50  # palette waterline; land sits above this


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class World:
    """A seeded, infinite world sampled into colored terrain for any window."""

    def __init__(self, seed: int = 1337):
        self.seed = seed
        self.perm = make_perm(seed)
        self.shade_strength = 9.0

    def sample(
        self,
        width: int,
        height: int,
        cam_x: float,
        cam_y: float,
        scale: float,
        sea_level: float = 0.0,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Render a window to (rgb, elevation, moisture, temperature).

        cam_x / cam_y are pixel offsets; scale is noise units per pixel; sea_level
        raises (>0, floods) or lowers (<0, exposes) the water. rgb is (h, w, 3).
        """
        xs = ((np.arange(width) + cam_x) * scale).astype(np.float32)
        ys = ((np.arange(height) + cam_y) * scale).astype(np.float32)
        gx, gy = np.meshgrid(xs, ys)

        elev, moist, river, temp = self._terrain(gx, gy)
        elev = np.clip(elev - sea_level, 0.0, 1.0)

        rgb = colorize(elev, moist)
        rgb = self._apply_rivers(rgb, elev, river)
        rgb = self._shade(elev, rgb)
        return np.clip(rgb, 0, 255).astype(np.uint8), elev, moist, temp

    def _terrain(
        self, x: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return (elevation, moisture, river intensity, temperature), each ~[0,1]."""
        p = self.perm

        # domain warp: bend the sampling space so coastlines and ranges meander
        wx = fbm(x * 0.6 + 13.1, y * 0.6 + 7.7, p, octaves=2)
        wy = fbm(x * 0.6 + 91.2, y * 0.6 + 43.3, p, octaves=2)
        xw = x + 2.2 * wx
        yw = y + 2.2 * wy

        # continents: large low-frequency landmasses with fractal detail
        cont = fbm(xw * 0.35, yw * 0.35, p, octaves=5)
        base = (cont + 1.0) * 0.5
        elev = np.clip(0.5 + (base - 0.5) * 2.0 - 0.02, 0.0, 1.0)  # widen the range

        # mountains: ridged crests added only on high ground
        ridges = ridged_fbm(xw * 1.3 + 50.0, yw * 1.3 + 50.0, p, octaves=4)
        elev = np.clip(elev + ridges * _smoothstep(0.55, 0.85, elev) * 0.40, 0.0, 1.0)

        # rivers: connected meandering channels (the zero-set of a warped noise
        # field) but suppressed on convex high ground, so they sit in valleys and
        # drain toward the coast instead of forming closed rings on hilltops.
        channel = fbm(xw * 1.1 + 200.0, yw * 1.1 + 200.0, p, octaves=2)
        width = 0.012 + 0.05 * (1.0 - elev)
        line = 1.0 - _smoothstep(0.0, width, np.abs(channel))

        dd = 0.5

        def hyd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return fbm(a * 0.6 + 500.0, b * 0.6 + 500.0, p, octaves=1)

        depth = (
            0.25
            * (hyd(xw - dd, yw) + hyd(xw + dd, yw) + hyd(xw, yw - dd) + hyd(xw, yw + dd))
            - hyd(xw, yw)
        )
        valley = _smoothstep(-0.02, 0.05, depth)  # 0 on convex hilltops, 1 in valleys
        basins = _smoothstep(
            0.25,
            0.55,
            (fbm(xw * 0.22 + 400.0, yw * 0.22 + 400.0, p, octaves=2) + 1) * 0.5,
        )
        land = _smoothstep(0.515, 0.55, elev) * (1.0 - _smoothstep(0.82, 0.90, elev))
        river = line * valley * basins * land
        # gentle carve for valley shading, but never below the shoreline so the
        # channel stays a river instead of turning into a sea inlet
        elev = np.maximum(elev - river * 0.05, np.minimum(elev, _SEA + 0.02))

        # moisture: its own field, but wetter along the rivers
        moist = (fbm(x * 0.4 + 900.0, y * 0.4 + 900.0, p, octaves=2) + 1) * 0.5
        moist = np.clip((moist - 0.5) * 2.3 + 0.5, 0.0, 1.0)
        moist = np.maximum(moist, river * 0.85)

        # temperature: large warm/cold regions, cooling sharply with altitude
        temp = (fbm(x * 0.13 + 1500.0, y * 0.13 + 1500.0, p, octaves=2) + 1) * 0.5
        temp = np.clip(temp - np.clip(elev - 0.5, 0.0, 1.0) * 0.85, 0.0, 1.0)

        return elev, moist, river, temp

    def _apply_rivers(
        self, rgb: np.ndarray, elev: np.ndarray, river: np.ndarray
    ) -> np.ndarray:
        """Paint river water over land cells, brighter at the channel center."""
        a = (np.clip((river - 0.12) / 0.5, 0.0, 1.0) * (elev > _SEA + 0.015))[..., None]
        shallow = np.array([74, 150, 205], dtype=np.float64)
        deep = np.array([44, 104, 170], dtype=np.float64)
        water = deep + (shallow - deep) * np.clip(river, 0.0, 1.0)[..., None]
        return rgb * (1.0 - a) + water * a

    def _shade(self, elev: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """Brighten slopes facing the light and darken those away from it."""
        dy, dx = np.gradient(elev)
        illum = (-dx - dy) * self.shade_strength
        factor = np.clip(1.0 + illum, 0.55, 1.45)[..., None]
        return rgb * factor
