# ABOUTME: Maps normalized terrain height to smooth RGB biome colors.
# ABOUTME: Interpolates between elevation color stops for a continuous surface.

import numpy as np

# Elevation stops from deep ocean to snow peaks: (height in [0,1], (r, g, b)).
_STOPS = [
    (0.00, (10, 24, 64)),
    (0.38, (24, 64, 130)),
    (0.47, (42, 120, 196)),
    (0.50, (70, 170, 210)),
    (0.515, (224, 214, 158)),
    (0.55, (148, 184, 96)),
    (0.66, (92, 150, 70)),
    (0.76, (58, 110, 52)),
    (0.84, (110, 102, 84)),
    (0.92, (150, 142, 132)),
    (0.97, (208, 206, 204)),
    (1.00, (252, 252, 255)),
]

_THRESH = np.array([s[0] for s in _STOPS])
_COLORS = np.array([s[1] for s in _STOPS], dtype=np.float64)


def colorize(height: np.ndarray) -> np.ndarray:
    """Convert a [0,1] height grid into an (..., 3) float RGB grid (0-255)."""
    idx = np.searchsorted(_THRESH, height, side="right") - 1
    idx = np.clip(idx, 0, len(_STOPS) - 2)
    t0 = _THRESH[idx]
    t1 = _THRESH[idx + 1]
    frac = np.clip((height - t0) / (t1 - t0), 0.0, 1.0)[..., None]
    c0 = _COLORS[idx]
    c1 = _COLORS[idx + 1]
    return c0 + (c1 - c0) * frac
