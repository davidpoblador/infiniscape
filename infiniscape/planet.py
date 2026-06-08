# ABOUTME: Procedural spherical planet you walk across; the surface wraps around.
# ABOUTME: An orthonormal frame is rotated so movement sails over the poles.

import math
import os
import select
import signal
import sys
import termios
import time
import tty

import numpy as np

from . import biomes
from .noise import fbm3, make_perm
from .palette import colorize
from .renderer import render

_HIDE, _SHOW = "\x1b[?25l", "\x1b[?25h"
_ALT_ON, _ALT_OFF = "\x1b[?1049h", "\x1b[?1049l"
_ARROWS = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left"}
_ICE = np.array([232, 238, 245], dtype=np.float64)
_MOVES = {
    "up": (0, -1), "w": (0, -1), "down": (0, 1), "s": (0, 1),
    "left": (-1, 0), "a": (-1, 0), "right": (1, 0), "d": (1, 0),
}  # fmt: skip
_COMBINE = 0.07  # seconds: two direction keys within this window make a diagonal


def _sphere(lat: float, lon: float) -> np.ndarray:
    cl = math.cos(lat)
    return np.array([cl * math.cos(lon), cl * math.sin(lon), math.sin(lat)])


def _frame(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Local east and north unit vectors at point p on the unit sphere."""
    k = np.array([0.0, 0.0, 1.0])
    east = np.cross(k, p)
    n = np.linalg.norm(east)
    east = np.array([1.0, 0.0, 0.0]) if n < 1e-6 else east / n
    return east, np.cross(p, east)


def _rot(u: np.ndarray, v: np.ndarray, s: float) -> tuple[np.ndarray, np.ndarray]:
    """Rotate the orthonormal pair (u, v) by angle s within their own plane."""
    cs, sn = math.cos(s), math.sin(s)
    return u * cs + v * sn, -u * sn + v * cs


class PlanetWorld:
    def __init__(self, seed: int = 1337):
        self.perm = make_perm(seed)

    def _terrain3(self, pts: np.ndarray):
        p = self.perm
        px, py, pz = pts[..., 0], pts[..., 1], pts[..., 2]
        h = fbm3(px * 3.2, py * 3.2, pz * 3.2, p, octaves=6)
        elev = np.clip(0.5 + h * 0.95, 0.0, 1.0)
        m = fbm3(px * 2.0 + 10, py * 2.0 + 10, pz * 2.0 + 10, p, octaves=4)
        moist = np.clip(m * 1.7 + 0.5, 0.0, 1.0)
        warmth = 1.0 - np.abs(pz)
        tn = fbm3(px * 1.4 + 50, py * 1.4 + 50, pz * 1.4 + 50, p, octaves=3) * 0.12
        temp = np.clip(warmth * 1.12 - 0.1 + tn - np.maximum(elev - 0.5, 0.0) * 0.7, 0, 1)
        return elev, moist, temp

    def _color(self, elev, moist, temp):
        rgb = colorize(elev, moist)
        ice = np.clip((0.2 - temp) / 0.12, 0.0, 1.0)[..., None]
        land = (elev > 0.50)[..., None]
        return rgb * (1.0 - ice * land) + _ICE * (ice * land)

    def _shade(self, elev, rgb):
        dy, dx = np.gradient(elev)
        factor = np.clip(1.0 + (-dx - dy) * 16.0, 0.6, 1.4)[..., None]
        return np.clip(rgb * factor, 0, 255)

    def sample_patch(self, cols, rows, pos, east, north, fov, sea_level):
        """Local surface patch around pos via the exponential map (east=right, north=up)."""
        h_px, w_px = rows * 2, cols
        dpp = fov / h_px
        sx = (np.arange(w_px) - (w_px - 1) / 2) * dpp
        sy = ((h_px - 1) / 2 - np.arange(h_px)) * dpp
        gx, gy = np.meshgrid(sx, sy)
        theta = np.sqrt(gx * gx + gy * gy)
        scl = np.sinc(theta / np.pi)
        pts = (
            pos[None, None, :] * np.cos(theta)[..., None]
            + (east[None, None, :] * gx[..., None] + north[None, None, :] * gy[..., None])
            * scl[..., None]
        )
        elev, moist, temp = self._terrain3(pts)
        elev = np.clip(elev - sea_level, 0.0, 1.0)
        rgb = self._shade(elev, self._color(elev, moist, temp))
        return rgb.astype(np.uint8), elev, moist, temp

    def globe(self, side, pos, east, north, sea_level):
        """Orthographic disc of the hemisphere around pos; square (side, side, 3)."""
        c = (side - 1) / 2
        u = (np.arange(side) - c) / (side / 2)
        gu, gv = np.meshgrid(u, u)
        gv = -gv  # screen-down is decreasing north
        rr = gu * gu + gv * gv
        inside = rr <= 1.0
        zc = np.sqrt(np.clip(1.0 - rr, 0.0, 1.0))
        pts = (
            east[None, None, :] * gu[..., None]
            + north[None, None, :] * gv[..., None]
            + pos[None, None, :] * zc[..., None]
        )
        elev, moist, temp = self._terrain3(pts)
        elev = np.clip(elev - sea_level, 0.0, 1.0)
        rgb = self._color(elev, moist, temp) * (0.55 + 0.45 * zc[..., None])
        rgb[~inside] = (6, 8, 14)
        return np.clip(rgb, 0, 255).astype(np.uint8)


def _player_color(under: np.ndarray) -> np.ndarray:
    c = under.astype(np.float64)
    inv = 255.0 - c
    lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    chroma = c.max() - c.min()
    flip = 0.9 * (1.0 - chroma / 255.0) * (1.0 - abs(lum - 127.5) / 127.5)
    target = 0.0 if lum > 150.0 else 255.0
    return np.clip(inv * (1.0 - flip) + target * flip, 0, 255).astype(np.uint8)


def _orthonormalize(pos, fwd, right):
    pos = pos / np.linalg.norm(pos)
    fwd = fwd - np.dot(fwd, pos) * pos
    fwd = fwd / np.linalg.norm(fwd)
    right = right - np.dot(right, pos) * pos - np.dot(right, fwd) * fwd
    right = right / np.linalg.norm(right)
    return pos, fwd, right


class PlanetApp:
    def __init__(self, seed: int = 1337, fps: float = 60.0):
        self.world = PlanetWorld(seed)
        pos = _sphere(0.3, 0.0)
        east, north = _frame(pos)
        self.pos, self.fwd, self.right = pos, north, east  # screen up = fwd, right = east
        self.fov = 0.45
        self.sea_level = 0.0
        self.show_globe = True
        self.frame_budget = 1.0 / fps
        self.running = True
        self.tty = -1
        self._opened = False
        self._mx = 0
        self._my = 0
        self._pend_t = 0.0
        self._moving = False

    # input
    def _read(self):
        out = []
        while select.select([self.tty], [], [], 0)[0]:
            d = os.read(self.tty, 64)
            if not d:
                break
            out.append(d.decode("utf-8", "ignore"))
        s = "".join(out)
        toks, i = [], 0
        while i < len(s):
            if s[i : i + 3] in _ARROWS:
                toks.append(_ARROWS[s[i : i + 3]])
                i += 3
            else:
                toks.append(s[i])
                i += 1
        return toks

    def _write(self, text):
        data = text.encode()
        while data:
            data = data[os.write(self.tty, data) :]

    def _step(self, keys, now):
        for k in keys:
            mv = _MOVES.get(k)
            if mv:
                if self._mx == 0 and self._my == 0 and not self._moving:
                    self._pend_t = now
                self._mx = mv[0] or self._mx
                self._my = mv[1] or self._my
            elif k in ("q", "\x03", "\x1b"):
                self.running = False
            elif k in ("+", "="):
                self.fov = max(0.06, self.fov * 0.85)
            elif k in ("-", "_"):
                self.fov = min(1.3, self.fov / 0.85)
            elif k in (".", ">"):
                self.sea_level = min(0.45, self.sea_level + 0.02)
            elif k in (",", "<"):
                self.sea_level = max(-0.45, self.sea_level - 0.02)
            elif k == "g":
                self.show_globe = not self.show_globe
        if self._mx and self._my:
            self._apply(self._mx, self._my)  # diagonal: both axes within the window
        elif self._mx or self._my:
            if self._moving or now - self._pend_t >= _COMBINE:
                self._apply(self._mx, self._my)
        else:
            self._moving = False

    def _apply(self, dx, dy):
        d = self.fov * 0.06  # ground step scales with zoom
        if dx and dy:
            d *= 0.7071  # equal speed on the diagonal
        if dy:  # up (dy=-1) sails forward over the pole
            self.pos, self.fwd = _rot(self.pos, self.fwd, -dy * d)
        if dx:
            self.pos, self.right = _rot(self.pos, self.right, dx * d)
        self.pos, self.fwd, self.right = _orthonormalize(self.pos, self.fwd, self.right)
        self._mx = self._my = 0
        self._pend_t = 0.0
        self._moving = True

    # frame
    def _hud(self, cols, elev, moist, temp):
        lat = math.degrees(math.asin(max(-1.0, min(1.0, self.pos[2]))))
        lon = math.degrees(math.atan2(self.pos[1], self.pos[0]))
        ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
        alt = int((elev - 0.5) * 8000)
        text = (
            f" planet  {abs(lat):.1f}°{ns} {abs(lon):.1f}°{ew}  "
            f"{biomes.name(elev, moist, temp)}  {alt:+d}m  {biomes.celsius(temp):+d}°C  "
            f"[wasd/arrows move (two=diagonal, wraps) · +/- zoom · ,. sea · g globe · q quit] "
        )[:cols]
        return f"\x1b[1;1H\x1b[7m{text}\x1b[0m"

    def _draw(self, cols, rows):
        rgb, elev, moist, temp = self.world.sample_patch(
            cols, rows, self.pos, self.right, self.fwd, self.fov, self.sea_level
        )
        cy, cx = rows, cols // 2
        pe, pm, pt = float(elev[cy, cx]), float(moist[cy, cx]), float(temp[cy, cx])
        rgb[cy, cx] = _player_color(rgb[cy, cx])

        if self.show_globe:
            side = min(cols - 2, rows * 2 - 2, max(16, cols // 4))
            side -= side % 2  # even pixel side -> square on screen, round disc
            if side >= 16:
                disc = self.world.globe(side, self.pos, self.right, self.fwd, self.sea_level)
                r0, c0 = rows * 2 - side - 1, 1
                rgb[r0 : r0 + side, c0 : c0 + side] = disc
                rgb[r0 + side // 2, c0 + side // 2] = (255, 64, 64)

        self._write(render(rgb) + self._hud(cols, pe, pm, pt))

    def run(self):
        try:
            self.tty = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            self._opened = True
        except OSError:
            self.tty = sys.stdin.fileno()
        old = termios.tcgetattr(self.tty)
        signal.signal(signal.SIGWINCH, lambda *_: None)
        try:
            tty.setcbreak(self.tty)
            self._write(_ALT_ON + _HIDE + "\x1b[2J")
            last = None
            while self.running:
                start = time.monotonic()
                self._step(self._read(), time.monotonic())
                cols, rows = os.get_terminal_size(self.tty)
                sig = (
                    tuple(np.round(self.pos, 4)), tuple(np.round(self.fwd, 4)),
                    round(self.fov, 4), self.sea_level, self.show_globe, cols, rows,
                )  # fmt: skip
                if sig != last and cols >= 2 and rows >= 1:
                    self._draw(cols, rows)
                    last = sig
                dt = time.monotonic() - start
                if dt < self.frame_budget:
                    time.sleep(self.frame_budget - dt)
        finally:
            self._write(_SHOW + _ALT_OFF)
            termios.tcsetattr(self.tty, termios.TCSADRAIN, old)
            if self._opened:
                os.close(self.tty)


def main():
    seed = 1337
    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            pass
    PlanetApp(seed=seed).run()


if __name__ == "__main__":
    main()
