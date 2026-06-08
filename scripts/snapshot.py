# ABOUTME: Renders composed frames to PNG so the world can be viewed off-terminal.
# ABOUTME: Emulates the half-block cells plus sprite glyphs with a monospace font.

import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from infiniscape.scene import compose
from infiniscape.world import World

CW, CH = 8, 16  # cell pixel size in the image; CH//2 keeps half-block pixels square
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_png(path: str, **kw) -> None:
    cols = kw.pop("cols")
    rows = kw.pop("rows")
    seed = kw.pop("seed", 1337)
    rgb, chars, fg = compose(World(seed), cols, rows, **kw)

    half = CH // 2
    base = np.repeat(np.repeat(rgb, half, axis=0), CW, axis=1)
    img = Image.fromarray(base, "RGB")

    if chars is not None:
        draw = ImageDraw.Draw(img)
        font = _font(13)
        top, bottom = rgb[0::2], rgb[1::2]
        for r in range(rows):
            for c in range(cols):
                g = chars[r, c]
                if not g:
                    continue
                x0, y0 = c * CW, r * CH
                t, b = top[r, c].astype(int), bottom[r, c].astype(int)
                bg = tuple(((t + b) // 2).tolist())
                draw.rectangle([x0, y0, x0 + CW - 1, y0 + CH - 1], fill=bg)
                draw.text(
                    (x0 + CW / 2, y0 + CH / 2),
                    g,
                    fill=tuple(int(v) for v in fg[r, c]),
                    font=font,
                    anchor="mm",
                )
    img.save(path)
    print("wrote", path, img.size)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    # full-lit overview so every biome and sprite is visible
    render_png(
        f"{out}/01_overview.png",
        cols=220,
        rows=64,
        seed=7,
        cam_x=0,
        cam_y=0,
        scale=0.012,
        sea_level=0.0,
        light_radius=2000.0,
        features=True,
        minimap=True,
    )
    # the actual play view: a torch around the player
    render_png(
        f"{out}/02_torch.png",
        cols=160,
        rows=48,
        seed=7,
        cam_x=0,
        cam_y=0,
        scale=0.018,
        sea_level=0.0,
        light_radius=30.0,
        features=True,
        minimap=True,
    )
    # raised sea level: an archipelago
    render_png(
        f"{out}/03_flooded.png",
        cols=220,
        rows=64,
        seed=7,
        cam_x=0,
        cam_y=0,
        scale=0.012,
        sea_level=0.16,
        light_radius=2000.0,
        features=True,
        minimap=True,
    )
    # a different world
    render_png(
        f"{out}/04_seed42.png",
        cols=220,
        rows=64,
        seed=42,
        cam_x=500,
        cam_y=300,
        scale=0.012,
        sea_level=-0.04,
        light_radius=2000.0,
        features=True,
        minimap=True,
    )
