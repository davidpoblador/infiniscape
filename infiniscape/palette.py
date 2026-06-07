# ABOUTME: Maps normalized terrain height to smooth RGB biome colors.
# ABOUTME: Interpolates between elevation color stops for a continuous surface.

import numpy as np

# Elevation stops from deep ocean to snow peaks: (height in [0,1], (r, g, b)).
# Bands are spaced to blend gently; the shallows->shore band in particular is
# kept wide so coastlines fade rather than snap.
_STOPS = [
    (0.00, (15, 32, 72)),
    (0.32, (28, 72, 134)),
    (0.46, (52, 124, 190)),
    (0.50, (104, 178, 208)),
    (0.55, (206, 200, 160)),
    (0.62, (150, 184, 104)),
    (0.70, (104, 158, 82)),
    (0.80, (70, 122, 64)),
    (0.87, (116, 110, 92)),
    (0.93, (156, 150, 140)),
    (0.97, (206, 204, 202)),
    (1.00, (250, 250, 254)),
]

_THRESH = np.array([s[0] for s in _STOPS])
_COLORS = np.array([s[1] for s in _STOPS], dtype=np.float64)


def _smoothstep(t: np.ndarray) -> np.ndarray:
    """Ease 0->1 so each segment fades in and out instead of ramping linearly."""
    return t * t * (3.0 - 2.0 * t)


def colorize(height: np.ndarray) -> np.ndarray:
    """Convert a [0,1] height grid into an (..., 3) float RGB grid (0-255)."""
    idx = np.searchsorted(_THRESH, height, side="right") - 1
    idx = np.clip(idx, 0, len(_STOPS) - 2)
    t0 = _THRESH[idx]
    t1 = _THRESH[idx + 1]
    frac = np.clip((height - t0) / (t1 - t0), 0.0, 1.0)
    frac = _smoothstep(frac)[..., None]
    c0 = _COLORS[idx]
    c1 = _COLORS[idx + 1]
    return c0 + (c1 - c0) * frac
