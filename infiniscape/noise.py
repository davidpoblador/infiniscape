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


def ridged_fbm(
    x: np.ndarray,
    y: np.ndarray,
    perm: np.ndarray,
    octaves: int = 4,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
) -> np.ndarray:
    """Ridged multifractal noise in ~[0,1]; sharp crests where Perlin crosses 0."""
    total = np.zeros_like(x)
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        r = 1.0 - np.abs(perlin(x * freq, y * freq, perm))
        r *= r
        total += amp * r
        norm += amp
        amp *= persistence
        freq *= lacunarity
    return total / norm


_GRAD3 = np.array(
    [
        (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
        (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
        (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1),
    ],
    dtype=np.float64,
)  # fmt: skip


def perlin3(x: np.ndarray, y: np.ndarray, z: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Classic 3D Perlin noise over float coordinate grids, range ~[-1, 1]."""
    xi = np.floor(x).astype(np.int32) & 255
    yi = np.floor(y).astype(np.int32) & 255
    zi = np.floor(z).astype(np.int32) & 255
    xf = x - np.floor(x)
    yf = y - np.floor(y)
    zf = z - np.floor(z)
    u, v, w = _fade(xf), _fade(yf), _fade(zf)

    a = perm[xi] + yi
    aa, ab = perm[a] + zi, perm[a + 1] + zi
    b = perm[xi + 1] + yi
    ba, bb = perm[b] + zi, perm[b + 1] + zi

    def g(h: np.ndarray, dx: np.ndarray, dy: np.ndarray, dz: np.ndarray) -> np.ndarray:
        gr = _GRAD3[h % 12]
        return gr[..., 0] * dx + gr[..., 1] * dy + gr[..., 2] * dz

    x1 = _lerp(g(perm[aa], xf, yf, zf), g(perm[ba], xf - 1, yf, zf), u)
    x2 = _lerp(g(perm[ab], xf, yf - 1, zf), g(perm[bb], xf - 1, yf - 1, zf), u)
    y1 = _lerp(x1, x2, v)
    x3 = _lerp(g(perm[aa + 1], xf, yf, zf - 1), g(perm[ba + 1], xf - 1, yf, zf - 1), u)
    x4 = _lerp(g(perm[ab + 1], xf, yf - 1, zf - 1), g(perm[bb + 1], xf - 1, yf - 1, zf - 1), u)
    y2 = _lerp(x3, x4, v)
    return _lerp(y1, y2, w)


def fbm3(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    perm: np.ndarray,
    octaves: int = 6,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
) -> np.ndarray:
    """Fractal Brownian motion from 3D Perlin noise, normalized to ~[-1, 1]."""
    total = np.zeros_like(x)
    amp, freq, norm = 1.0, 1.0, 0.0
    for _ in range(octaves):
        total += amp * perlin3(x * freq, y * freq, z * freq, perm)
        norm += amp
        amp *= persistence
        freq *= lacunarity
    return total / norm
