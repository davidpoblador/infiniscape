# ABOUTME: Interactive terminal loop: terminal setup, input, camera, drawing.
# ABOUTME: Centers a player pixel, lights its surroundings, draws the world.

import os
import select
import signal
import sys
import termios
import time
import tty

import numpy as np

from .renderer import render
from .world import World

_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_ALT_SCREEN_ON = "\x1b[?1049h"
_ALT_SCREEN_OFF = "\x1b[?1049l"

_ARROWS = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left"}


class App:
    def __init__(self, seed: int = 1337, fps: float = 30.0):
        self.world = World(seed=seed)
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.scale = 0.018  # noise units per pixel; smaller = more zoomed in
        self.vx = 0  # current heading, in pixels per frame (-1, 0, or 1)
        self.vy = 0
        self.show_hud = True
        self.light_radius = 26.0  # lit radius around the player, in pixels
        self.shadow_radius = 4.0  # dark halo hugging the player, in pixels
        self.shadow_depth = 0.35  # darkest the halo gets (1.0 = no shadow)
        self.frame_budget = 1.0 / fps
        self.running = True
        self._masks = None
        self._mask_key = None

    # --- input -------------------------------------------------------------
    def _read_keys(self) -> list[str]:
        chunks: list[str] = []
        while select.select([sys.stdin], [], [], 0)[0]:
            data = os.read(sys.stdin.fileno(), 64)
            if not data:
                break
            chunks.append(data.decode("utf-8", "ignore"))
        return self._tokenize("".join(chunks))

    @staticmethod
    def _tokenize(data: str) -> list[str]:
        tokens: list[str] = []
        i = 0
        while i < len(data):
            if data[i : i + 3] in _ARROWS:
                tokens.append(_ARROWS[data[i : i + 3]])
                i += 3
            else:
                tokens.append(data[i])
                i += 1
        return tokens

    def _handle(self, key: str, cols: int, rows: int) -> None:
        # Movement keys set a persistent heading per axis, so going left and
        # then pressing up keeps the leftward motion and turns it diagonal.
        # Tapping the current direction again cancels that axis.
        if key in ("q", "\x03", "\x1b"):
            self.running = False
        elif key in ("left", "a"):
            self.vx = 0 if self.vx == -1 else -1
        elif key in ("right", "d"):
            self.vx = 0 if self.vx == 1 else 1
        elif key in ("up", "w"):
            self.vy = 0 if self.vy == -1 else -1
        elif key in ("down", "s"):
            self.vy = 0 if self.vy == 1 else 1
        elif key in ("+", "="):
            self._zoom(0.85, cols, rows)
        elif key in ("-", "_"):
            self._zoom(1.0 / 0.85, cols, rows)
        elif key == "[":
            self.light_radius = max(8.0, self.light_radius - 4.0)
        elif key == "]":
            self.light_radius = min(400.0, self.light_radius + 4.0)
        elif key == " ":
            self.vx = self.vy = 0  # stop

    def _zoom(self, ratio: float, cols: int, rows: int) -> None:
        """Zoom about the player (view center) so their spot stays put."""
        cx = self.cam_x + cols / 2
        cy = self.cam_y + rows
        self.scale = min(max(self.scale * ratio, 0.0008), 0.2)
        self.cam_x = cx - cols / 2
        self.cam_y = cy - rows

    # --- visibility --------------------------------------------------------
    def _view_masks(self, h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
        """Cached (brightness, halo) masks centered on the player.

        Brightness fades the world to black at the edge of sight and digs a dark
        well right around the player. Halo strength (1 at the player, 0 past the
        shadow radius) is used to desaturate that well toward neutral grey, so the
        shadow carries no terrain hue and the vivid player pixel never clashes.
        """
        key = (h, w, self.light_radius, self.shadow_radius, self.shadow_depth)
        if key == self._mask_key:
            return self._masks
        yy, xx = np.ogrid[0:h, 0:w]
        dist = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2)

        falloff = self.light_radius * 0.45
        lt = np.clip((self.light_radius - dist) / falloff + 1.0, 0.0, 1.0)
        light = lt * lt * (3.0 - 2.0 * lt)  # smoothstep edge to darkness

        st = np.clip(dist / self.shadow_radius, 0.0, 1.0)
        halo = 1.0 - st * st * (3.0 - 2.0 * st)  # 1 at player, 0 past the radius

        bright = light * (1.0 - (1.0 - self.shadow_depth) * halo)
        self._masks = (bright[..., None], halo[..., None])
        self._mask_key = key
        return self._masks

    # --- player ------------------------------------------------------------
    @staticmethod
    def _player_color(under: np.ndarray) -> np.ndarray:
        """A contrast-guaranteed 'negative' of the pixel beneath the player.

        Colorful terrain keeps the true inverse (hue alone makes it pop); grayish
        mid-tone terrain, whose inverse would look nearly identical, is pushed to
        the opposite luminance extreme so the player never blends in.
        """
        c = under.astype(np.float64)
        inv = 255.0 - c
        lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        chroma = c.max() - c.min()
        grayness = 1.0 - chroma / 255.0
        midness = 1.0 - abs(lum - 127.5) / 127.5
        flip = 0.9 * grayness * midness  # only gray AND mid-tone needs a flip
        target = 0.0 if lum > 150.0 else 255.0
        player = inv * (1.0 - flip) + target * flip
        return np.clip(player, 0, 255).astype(np.uint8)

    # --- frame -------------------------------------------------------------
    _HEADINGS = {
        (0, 0): "·",
        (-1, 0): "←",
        (1, 0): "→",
        (0, -1): "↑",
        (0, 1): "↓",
        (-1, -1): "↖",
        (1, -1): "↗",
        (-1, 1): "↙",
        (1, 1): "↘",
    }

    def _hud(self, cols: int, rows: int) -> str:
        heading = self._HEADINGS[(self.vx, self.vy)]
        px = int(self.cam_x + cols / 2)
        py = int(self.cam_y + rows)  # player sits at the view center
        text = (
            f" infiniscape  @ {px:+d},{py:+d}  {heading}  zoom {1 / self.scale:5.0f}  "
            f"light {int(self.light_radius)}  "
            f"[wasd/arrows steer  space stop  +/- zoom  [ ] light  h hud  q quit] "
        )[:cols]
        return f"\x1b[1;1H\x1b[7m{text}\x1b[0m"

    def _draw(self) -> tuple[int, int]:
        cols, rows = os.get_terminal_size()
        if cols < 2 or rows < 1:  # nothing sane to draw on a degenerate window
            return cols, rows
        rgb = self.world.sample(cols, rows * 2, self.cam_x, self.cam_y, self.scale)

        py, px = rows, cols // 2  # player occupies one half-block pixel
        under = rgb[py, px].copy()  # true terrain color, before the shadow halo

        bright, halo = self._view_masks(rows * 2, cols)
        f = rgb.astype(np.float64)
        grey = (0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2])[..., None]
        f = f * (1.0 - halo) + grey * halo  # neutral, hue-free shadow near player
        rgb = np.clip(f * bright, 0, 255).astype(np.uint8)
        rgb[py, px] = self._player_color(under)

        frame = render(rgb)
        if self.show_hud:
            frame += self._hud(cols, rows)
        sys.stdout.write(frame)
        sys.stdout.flush()
        return cols, rows

    def run(self) -> None:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        signal.signal(signal.SIGWINCH, lambda *_: None)  # interrupt select on resize
        try:
            tty.setcbreak(fd)
            sys.stdout.write(_ALT_SCREEN_ON + _HIDE_CURSOR + "\x1b[2J")
            sys.stdout.flush()
            cols, rows = os.get_terminal_size()
            while self.running:
                start = time.monotonic()
                for key in self._read_keys():
                    self._handle(key, cols, rows)
                self.cam_x += self.vx
                self.cam_y += self.vy
                cols, rows = self._draw()
                elapsed = time.monotonic() - start
                if elapsed < self.frame_budget:
                    time.sleep(self.frame_budget - elapsed)
        finally:
            sys.stdout.write(_SHOW_CURSOR + _ALT_SCREEN_OFF)
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main() -> None:
    seed = 1337
    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            pass
    App(seed=seed).run()
