# ABOUTME: Vectorized Perlin gradient noise and fractal Brownian motion.
# ABOUTME: Produces the continuous, infinite height field sampled by the world.

import numpy as np

# Eight unit-ish gradient directions selected by a hashed corner value.
_GRADS = np.array(
    [(1, 1), (-1, 1), (1, -1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)],
    dtype=np.float64,
)


def make_perm(seed: int) -> np.ndarray:
    """Return a 512-long permutation table (256 shuffled, then repeated)."""
    rng = np.random.default_rng(seed)
    p = np.arange(256, dtype=np.int32)
    rng.shuffle(p)
    return np.concatenate([p, p])


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    return a + t * (b - a)


def _dot(h: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    g = _GRADS[h & 7]
    return g[..., 0] * x + g[..., 1] * y


def perlin(x: np.ndarray, y: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Classic 2D Perlin noise over float coordinate grids, range ~[-1, 1]."""
    xi = np.floor(x).astype(np.int32)
    yi = np.floor(y).astype(np.int32)
    xf = x - xi
    yf = y - yi
    xi &= 255
    yi &= 255

    u = _fade(xf)
    v = _fade(yf)

    aa = perm[perm[xi] + yi]
    ab = perm[perm[xi] + yi + 1]
    ba = perm[perm[xi + 1] + yi]
    bb = perm[perm[xi + 1] + yi + 1]

    x1 = _lerp(_dot(aa, xf, yf), _dot(ba, xf - 1, yf), u)
    x2 = _lerp(_dot(ab, xf, yf - 1), _dot(bb, xf - 1, yf - 1), u)
    return _lerp(x1, x2, v)


def fbm(
    x: np.ndarray,
    y: np.ndarray,
    perm: np.ndarray,
    octaves: int = 5,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
) -> np.ndarray:
    """Sum several Perlin octaves into smooth terrain, normalized to ~[-1, 1]."""
    total = np.zeros_like(x)
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += amp * perlin(x * freq, y * freq, perm)
        norm += amp
        amp *= persistence
        freq *= lacunarity
    return total / norm
