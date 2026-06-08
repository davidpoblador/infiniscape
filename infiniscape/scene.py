# ABOUTME: Composes a full frame: terrain, light, player, sprites, and minimap.
# ABOUTME: Shared by the live TUI and the offline PNG snapshot renderer.

import math

import numpy as np

from .features import build_features
from .masks import player_color, view_masks
from .world import World

_mask_cache: dict = {}
_minimap_cache: dict = {}


def _masks(h, w, lr, sr, cx, cy):
    key = (h, w, lr, sr, cx, cy)
    if key not in _mask_cache:
        if len(_mask_cache) > 4:
            _mask_cache.clear()
        _mask_cache[key] = view_masks(h, w, lr, sr, cx, cy)
    return _mask_cache[key]


def compose(
    world: World,
    cols: int,
    rows: int,
    cam_x: float,
    cam_y: float,
    scale: float,
    sea_level: float = 0.0,
    light_radius: float = 26.0,
    shadow_radius: float = 5.5,
    shadow_depth: float = 0.40,
    features: bool = True,
    minimap: bool = True,
    minimap_factor: float = 12.0,
    player_px: int | None = None,
    player_py: int | None = None,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None, tuple]:
    """Return (rgb pixels, sprite chars, sprite colors) for one frame.

    rgb is (rows*2, cols, 3); chars/fg are (rows, cols) cell grids or None.
    """
    h_px, w_px = rows * 2, cols
    rgb, elev, moist, temp = world.sample(w_px, h_px, cam_x, cam_y, scale, sea_level)

    px = cols // 2 if player_px is None else player_px
    py = (
        rows if player_py is None else player_py
    )  # player's pixel (top/bottom of its cell)
    light, halo = _masks(h_px, w_px, light_radius, shadow_radius, px, py)

    # The shadow well is a darkened shade of the player's own color, so the marker
    # and its halo read as one consistent element on any terrain. The light
    # vignette is applied separately so the well keeps that color (not the terrain).
    pcol = player_color(rgb[py, px].copy()).astype(np.float64)
    f = rgb.astype(np.float64) * (1.0 - halo) + (pcol * shadow_depth) * halo
    disp = np.clip(f * light, 0, 255).astype(np.uint8)
    disp[py, px] = pcol.astype(np.uint8)

    chars = fg = None
    if features:
        chars, fg = build_features(
            elev[0::2], moist[0::2], math.floor(cam_x), math.floor(cam_y / 2)
        )
        cell_vis = (light * (1.0 - halo))[0::2, :, 0]
        fg = np.clip(fg.astype(np.float64) * cell_vis[..., None], 0, 255).astype(
            np.uint8
        )
        chars[cell_vis < 0.08] = ""  # hide sprites in the dark or in the well
        chars[py // 2, px] = ""  # never cover the player

    if minimap:
        _draw_minimap(
            disp,
            chars,
            world,
            cols,
            rows,
            cam_x,
            cam_y,
            scale,
            sea_level,
            minimap_factor,
        )

    stats = (float(elev[py, px]), float(moist[py, px]), float(temp[py, px]))
    return disp, chars, fg, stats


def _draw_minimap(
    disp: np.ndarray,
    chars: np.ndarray | None,
    world: World,
    cols: int,
    rows: int,
    cam_x: float,
    cam_y: float,
    scale: float,
    sea_level: float,
    factor: float,
) -> None:
    """Composite a coarse, always-lit overview into the bottom-left, if it fits."""
    mm_cols = min(40, max(20, cols // 4))
    mm_rows = min(14, max(8, rows // 4))
    if cols < mm_cols + 6 or rows < mm_rows + 4:
        return  # not enough room; skip the map

    w_mm, h_mm = mm_cols, mm_rows * 2
    mm_scale = scale * factor
    # center the map on the player, snapped to whole minimap-pixels so the coarse
    # sampling sits on a stable lattice and the map does not shimmer as you move
    mm_cam_x = round((cam_x + cols / 2) / factor - w_mm / 2)
    mm_cam_y = round((cam_y + rows) / factor - h_mm / 2)
    mkey = (
        world.seed,
        w_mm,
        h_mm,
        mm_cam_x,
        mm_cam_y,
        round(mm_scale, 6),
        round(sea_level, 4),
    )
    if mkey not in _minimap_cache:
        _minimap_cache.clear()
        # supersample and box-average so each map pixel is a smooth regional
        # average instead of a single aliased sample point
        ss = 3
        hi = world.sample(
            w_mm * ss, h_mm * ss, mm_cam_x * ss, mm_cam_y * ss, mm_scale / ss, sea_level
        )[0]
        _minimap_cache[mkey] = (
            hi.reshape(h_mm, ss, w_mm, ss, 3).mean(axis=(1, 3)).astype(np.uint8)
        )
    mrgb = _minimap_cache[mkey]

    h_px = rows * 2
    r0 = h_px - h_mm - 1  # 1px bottom margin
    c0 = 1  # 1px left margin
    border = (12, 12, 16)
    disp[r0 - 1 : r0 + h_mm + 1, c0 - 1] = border
    disp[r0 - 1 : r0 + h_mm + 1, c0 + w_mm] = border
    disp[r0 - 1, c0 - 1 : c0 + w_mm + 1] = border
    disp[r0 + h_mm, c0 - 1 : c0 + w_mm + 1] = border
    disp[r0 : r0 + h_mm, c0 : c0 + w_mm] = mrgb
    disp[r0 + h_mm // 2, c0 + w_mm // 2] = (255, 64, 64)  # player marker

    if chars is not None:
        chars[(r0 - 1) // 2 :, 0 : c0 + w_mm + 1] = ""  # no sprites over the map
