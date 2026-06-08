# ABOUTME: Minimal dependency-free PNG writer for 8-bit RGB numpy arrays.
# ABOUTME: Lets the app export images without pulling in an image library.

import struct
import zlib

import numpy as np


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_png(path: str, rgb: np.ndarray) -> None:
    """Write an (H, W, 3) uint8 array to a PNG file (truecolor, no filtering)."""
    h, w, _ = rgb.shape
    arr = np.ascontiguousarray(rgb, dtype=np.uint8).reshape(h, w * 3)
    raw = np.zeros((h, w * 3 + 1), dtype=np.uint8)  # leading 0 = "no filter" per row
    raw[:, 1:] = arr
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit, color type 2 (RGB)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", zlib.compress(raw.tobytes(), 6)))
        f.write(_chunk(b"IEND", b""))
