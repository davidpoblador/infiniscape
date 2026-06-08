# ABOUTME: Interactive terminal loop: terminal setup, input, camera, drawing.
# ABOUTME: Steers a player across the world and composes each frame to draw.

import os
import select
import signal
import sys
import termios
import time
import tty

from .renderer import render
from .scene import compose
from .world import World

_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_ALT_SCREEN_ON = "\x1b[?1049h"
_ALT_SCREEN_OFF = "\x1b[?1049l"

_ARROWS = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left"}
_MOVES = {
    "left": (-1, 0), "a": (-1, 0), "right": (1, 0), "d": (1, 0),
    "up": (0, -1), "w": (0, -1), "down": (0, 1), "s": (0, 1),
}  # fmt: skip
_DIAG = 0.7071067811865476  # 1 / sqrt(2)


class App:
    def __init__(self, seed: int = 1337, fps: float = 30.0):
        self.world = World(seed=seed)
        self.px = 0.0  # player world position in pixels; starts at the origin
        self.py = 0.0
        self.scale = 0.018  # noise units per pixel (fixed; the main view does not zoom)
        self.sea_level = 0.0  # waterline offset: >0 floods, <0 exposes land
        self.light_radius = 26.0  # lit radius around the player, in pixels
        self.show_features = True
        self.show_minimap = True
        self.show_hud = True
        self.frame_budget = 1.0 / fps
        self.running = True

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

    def _step(self, keys: list[str]) -> None:
        """Move once per frame from the keys held this frame.

        Movement keys are summed and clamped to a single pixel per axis, so two
        direction keys pressed together make one diagonal step and a held key
        (auto-repeated by the terminal) moves steadily while down.
        """
        dx = dy = 0
        for key in keys:
            move = _MOVES.get(key)
            if move:
                dx += move[0]
                dy += move[1]
            else:
                self._handle(key)
        sx, sy = max(-1, min(1, dx)), max(-1, min(1, dy))
        if (
            sx and sy
        ):  # normalize so a diagonal step is the same speed as a straight one
            self.px += sx * _DIAG
            self.py += sy * _DIAG
        else:
            self.px += sx
            self.py += sy

    def _handle(self, key: str) -> None:
        if key in ("q", "\x03", "\x1b"):
            self.running = False
        elif key == "[":
            self.light_radius = max(8.0, self.light_radius - 4.0)
        elif key == "]":
            self.light_radius = min(400.0, self.light_radius + 4.0)
        elif key in (".", ">"):
            self.sea_level = min(0.45, self.sea_level + 0.02)
        elif key in (",", "<"):
            self.sea_level = max(-0.45, self.sea_level - 0.02)
        elif key == "f":
            self.show_features = not self.show_features
        elif key == "m":
            self.show_minimap = not self.show_minimap
        elif key == "h":
            self.show_hud = not self.show_hud

    # --- frame -------------------------------------------------------------
    def _hud(self, cols: int, rows: int) -> str:
        text = (
            f" infiniscape  @ {int(self.px):+d},{int(self.py):+d}  "
            f"light {int(self.light_radius)}  sea {self.sea_level:+.2f}  "
            f"[wasd/arrows move (diagonals too) · ,. sea · [] light · f trees · m map · h hud · q quit] "
        )[:cols]
        return f"\x1b[1;1H\x1b[7m{text}\x1b[0m"

    def _signature(self, cols: int, rows: int) -> tuple:
        """Everything that affects the frame; identical -> no need to redraw."""
        return (
            round(self.px, 3),
            round(self.py, 3),
            self.sea_level,
            self.light_radius,
            self.show_features,
            self.show_minimap,
            self.show_hud,
            cols,
            rows,
        )

    def _draw(self, cols: int, rows: int) -> None:
        cam_x = self.px - cols / 2  # center the camera on the player
        cam_y = self.py - rows
        rgb, chars, fg = compose(
            self.world,
            cols,
            rows,
            cam_x,
            cam_y,
            self.scale,
            self.sea_level,
            self.light_radius,
            features=self.show_features,
            minimap=self.show_minimap,
        )
        frame = render(rgb, chars, fg)
        if self.show_hud:
            frame += self._hud(cols, rows)
        sys.stdout.write(frame)
        sys.stdout.flush()

    def run(self) -> None:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        signal.signal(signal.SIGWINCH, lambda *_: None)  # interrupt select on resize
        try:
            tty.setcbreak(fd)
            sys.stdout.write(_ALT_SCREEN_ON + _HIDE_CURSOR + "\x1b[2J")
            sys.stdout.flush()
            last_sig = None
            while self.running:
                start = time.monotonic()
                self._step(self._read_keys())
                cols, rows = os.get_terminal_size()
                sig = self._signature(cols, rows)
                if sig != last_sig and cols >= 2 and rows >= 1:
                    self._draw(cols, rows)
                    last_sig = sig
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
