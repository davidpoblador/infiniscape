# ABOUTME: Generates realistic infinite terrain in physical metres (1 cell = 1 m).
# ABOUTME: Multi-scale octaves keep per-metre slopes gentle and believable.

import numpy as np

from .noise import make_perm, perlin
from .palette import colorize

_SEA = 0.50  # palette waterline; elevation 0.5 == sea level (0 m)

# Elevation octaves as (wavelength_m, amplitude_m). Amplitude grows with
# wavelength so the slope each octave adds (~amp/wavelength) stays small: gentle
# rolling ground at 1 m per cell, with continents over many kilometres.
_OCTAVES = [
    (16000.0, 380.0),
    (6000.0, 170.0),
    (2200.0, 90.0),
    (800.0, 46.0),
    (280.0, 20.0),
    (100.0, 8.0),
    (34.0, 3.0),
    (12.0, 1.1),
]
_HEIGHT_SPAN = 1024.0  # metres mapped across the [0,1] palette (sea at the middle)


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class World:
    """A seeded, infinite world sampled into colored terrain for any window."""

    def __init__(self, seed: int = 1337):
        self.seed = seed
        self.perm = make_perm(seed)
        self.shade_strength = 0.7  # tuned for metre-scale height gradients

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

        cam_x / cam_y are pixel offsets; scale is metres per pixel (1.0 live).
        sea_level raises (>0, floods) or lowers (<0, exposes) the water.
        """
        xs = ((np.arange(width) + cam_x) * scale).astype(np.float32)
        ys = ((np.arange(height) + cam_y) * scale).astype(np.float32)
        gx, gy = np.meshgrid(xs, ys)

        elev, moist, river, temp, hm = self._terrain(gx, gy)
        elev = np.clip(elev - sea_level, 0.0, 1.0)

        rgb = colorize(elev, moist)
        rgb = self._apply_rivers(rgb, elev, river)
        rgb = self._shade(hm, rgb)
        return np.clip(rgb, 0, 255).astype(np.uint8), elev, moist, temp

    def _terrain(
        self, x: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return (elevation[0,1], moisture, river, temperature, height_m)."""
        p = self.perm

        # gentle domain warp (km scale) so coastlines and ranges meander
        wx = perlin(x / 9000.0 + 11.0, y / 9000.0 + 11.0, p)
        wy = perlin(x / 9000.0 + 71.0, y / 9000.0 + 71.0, p)
        xw = x + 1600.0 * wx
        yw = y + 1600.0 * wy

        # metres between adjacent cells; used to drop sub-pixel detail so coarse
        # views (minimap, overview) stay smooth instead of aliasing into speckle
        pitch = float(abs(x[0, 1] - x[0, 0])) if x.shape[1] > 1 else 1.0

        # elevation in metres: sum of physically scaled octaves
        hm = np.zeros_like(x)
        for i, (wl, amp) in enumerate(_OCTAVES):
            aa = amp * float(_smoothstep(2.0, 5.0, np.array(wl / pitch)))
            if aa <= 0.0:
                continue
            o = i * 37.0
            hm = hm + aa * perlin(xw / wl + o, yw / wl + o, p)
        elev = np.clip(0.5 + hm / _HEIGHT_SPAN, 0.0, 1.0)

        # rivers: local streams that settle in valleys (the distant sea is off-map)
        channel = perlin(xw / 420.0 + 200.0, yw / 420.0 + 200.0, p)
        width = 0.03 + 0.07 * (1.0 - elev)
        line = 1.0 - _smoothstep(0.0, width, np.abs(channel))
        dd = 500.0

        def hyd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return perlin(a / 1600.0 + 500.0, b / 1600.0 + 500.0, p)

        depth = (
            0.25
            * (hyd(xw - dd, yw) + hyd(xw + dd, yw) + hyd(xw, yw - dd) + hyd(xw, yw + dd))
            - hyd(xw, yw)
        )
        valley = _smoothstep(-0.02, 0.05, depth)
        basins = _smoothstep(
            0.25, 0.55, (perlin(xw / 8000.0 + 400.0, yw / 8000.0 + 400.0, p) + 1) * 0.5
        )
        land = _smoothstep(0.515, 0.55, elev) * (1.0 - _smoothstep(0.82, 0.90, elev))
        river = line * valley * basins * land
        river *= float(_smoothstep(2.0, 5.0, np.array(420.0 / pitch)))  # anti-alias

        # moisture: broad climate bands with some regional variation
        moist = 0.6 * perlin(x / 5200.0 + 900.0, y / 5200.0 + 900.0, p)
        moist += 0.4 * perlin(x / 1500.0 + 950.0, y / 1500.0 + 950.0, p)
        moist = np.clip((moist) * 1.6 + 0.5, 0.0, 1.0)
        moist = np.maximum(moist, river * 0.85)

        # temperature: large warm/cold regions, cooling with altitude
        temp = 0.5 + 0.45 * perlin(x / 12000.0 + 1500.0, y / 12000.0 + 1500.0, p)
        temp = np.clip(temp - np.maximum(hm, 0.0) / 1600.0, 0.0, 1.0)

        return elev, moist, river, temp, hm

    def _apply_rivers(
        self, rgb: np.ndarray, elev: np.ndarray, river: np.ndarray
    ) -> np.ndarray:
        """Paint river water over land cells, brighter at the channel center."""
        a = (np.clip((river - 0.12) / 0.5, 0.0, 1.0) * (elev > _SEA + 0.015))[..., None]
        shallow = np.array([74, 150, 205], dtype=np.float64)
        deep = np.array([44, 104, 170], dtype=np.float64)
        water = deep + (shallow - deep) * np.clip(river, 0.0, 1.0)[..., None]
        return rgb * (1.0 - a) + water * a

    def _shade(self, hm: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """Hillshade from the metre-scale height gradient (light from top-left)."""
        dy, dx = np.gradient(hm)
        illum = (-dx - dy) * self.shade_strength
        factor = np.clip(1.0 + illum, 0.55, 1.45)[..., None]
        return rgb * factor
