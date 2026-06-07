# ABOUTME: Maps terrain elevation and moisture to smooth RGB biome colors.
# ABOUTME: Bilinearly blends a 2D table; ocean/rock/snow ignore moisture.

import numpy as np

# Each row is an elevation stop with four moisture variants:
#   column 0 arid, 1 dry, 2 moist, 3 wet.
# Ocean, shore, rock, and snow are moisture-independent (identical columns).
# The "moist" column is the original elevation palette, so a temperate biome
# looks exactly like the world did before biomes existed.
_MOIST_LEVELS = 4

_ROWS = [
    (0.000, [(10, 24, 64)] * 4),  # deep ocean
    (0.380, [(24, 64, 130)] * 4),  # ocean
    (0.470, [(42, 120, 196)] * 4),  # water
    (0.500, [(70, 170, 210)] * 4),  # shallows
    (0.515, [(224, 214, 158)] * 4),  # beach
    (
        0.550,
        [(214, 196, 132), (190, 196, 120), (148, 184, 96), (104, 182, 96)],
    ),  # low veg
    (0.660, [(176, 150, 96), (150, 168, 96), (92, 150, 70), (54, 134, 74)]),  # mid veg
    (0.760, [(138, 120, 86), (104, 124, 74), (58, 110, 52), (38, 96, 58)]),  # high veg
    (0.840, [(110, 102, 84)] * 4),  # rock
    (0.920, [(150, 142, 132)] * 4),  # high rock
    (0.970, [(208, 206, 204)] * 4),  # snow line
    (1.000, [(252, 252, 255)] * 4),  # peak snow
]

_E = np.array([r[0] for r in _ROWS])
_TABLE = np.array([r[1] for r in _ROWS], dtype=np.float64)  # (n_elev, 4, 3)


def colorize(height: np.ndarray, moisture: np.ndarray) -> np.ndarray:
    """Blend the (elevation, moisture) table into an (..., 3) float RGB grid."""
    ei = np.clip(np.searchsorted(_E, height, side="right") - 1, 0, len(_E) - 2)
    e0 = _E[ei]
    e1 = _E[ei + 1]
    fe = np.clip((height - e0) / (e1 - e0), 0.0, 1.0)[..., None]

    m = np.clip(moisture, 0.0, 1.0) * (_MOIST_LEVELS - 1)
    mi = np.clip(np.floor(m).astype(np.int32), 0, _MOIST_LEVELS - 2)
    fm = (m - mi)[..., None]

    c00 = _TABLE[ei, mi]
    c10 = _TABLE[ei + 1, mi]
    c01 = _TABLE[ei, mi + 1]
    c11 = _TABLE[ei + 1, mi + 1]
    top = c00 + (c01 - c00) * fm
    bot = c10 + (c11 - c10) * fm
    return top + (bot - top) * fe
