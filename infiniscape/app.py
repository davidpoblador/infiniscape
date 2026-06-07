# ABOUTME: Interactive terminal loop: terminal setup, input, camera, drawing.
# ABOUTME: Drives the infinite world render and handles pan, zoom, and drift.

import os
import select
import signal
import sys
import termios
import time
import tty

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
        self.drift_x = 0.6  # pixels per frame of gentle auto-scroll
        self.drift_y = 0.0
        self.drifting = True
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

    def _handle(self, key: str, cols: int, rows: int) -> None:
        pan = max(2.0, cols * 0.06)  # pan speed scales with view size
        if key in ("q", "\x03", "\x1b"):
            self.running = False
        elif key in ("left", "a"):
            self.cam_x -= pan
        elif key in ("right", "d"):
            self.cam_x += pan
        elif key in ("up", "w"):
            self.cam_y -= pan
        elif key in ("down", "s"):
            self.cam_y += pan
        elif key in ("+", "="):
            self._zoom(0.85, cols, rows)
        elif key in ("-", "_"):
            self._zoom(1.0 / 0.85, cols, rows)
        elif key == " ":
            self.drifting = not self.drifting
        elif key == "h":
            self.show_hud = not self.show_hud

    def _zoom(self, ratio: float, cols: int, rows: int) -> None:
        """Zoom about the view center so the focus point stays put."""
        cx = self.cam_x + cols / 2
        cy = self.cam_y + rows
        self.scale = min(max(self.scale * ratio, 0.0008), 0.2)
        self.cam_x = cx - cols / 2
        self.cam_y = cy - rows

    # --- frame -------------------------------------------------------------
    def _hud(self, cols: int) -> str:
        state = "drift" if self.drifting else "still"
        text = (
            f" infiniscape  pos {int(self.cam_x):+d},{int(self.cam_y):+d}  "
            f"zoom {1 / self.scale:6.0f}  {state}  "
            f"[wasd/arrows move  +/- zoom  space drift  h hud  q quit] "
        )[:cols]
        return f"\x1b[1;1H\x1b[7m{text}\x1b[0m"

    def _draw(self) -> tuple[int, int]:
        cols, rows = os.get_terminal_size()
        if cols < 2 or rows < 1:  # nothing sane to draw on a degenerate window
            return cols, rows
        rgb = self.world.sample(cols, rows * 2, self.cam_x, self.cam_y, self.scale)
        frame = render(rgb)
        if self.show_hud:
            frame += self._hud(cols)
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
                if self.drifting:
                    self.cam_x += self.drift_x
                    self.cam_y += self.drift_y
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
