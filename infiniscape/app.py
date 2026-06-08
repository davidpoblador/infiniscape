# ABOUTME: Interactive terminal loop: terminal setup, input, camera, drawing.
# ABOUTME: Steers a player, shows a status bar with clock, and a help modal.

import os
import select
import signal
import sys
import termios
import time
import tty
from datetime import datetime, timedelta, timezone

from . import biomes
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

_HELP_LINES = [
    "  move          w a s d  ·  arrow keys",
    "  sea level     ,  (lower)    .  (raise)",
    "  light         [  (smaller)  ]  (larger)",
    "  trees         f",
    "  minimap       m",
    "  help          h   (close this)",
    "  quit          q   ·   Esc",
]
_HELP_TITLE = " infiniscape — controls "


class App:
    def __init__(self, seed: int = 1337, fps: float = 30.0):
        self.world = World(seed=seed)
        self.px = 0  # player world position in pixels; starts at the origin
        self.py = 0
        self.scale = 0.018  # noise units per pixel (fixed; the main view does not zoom)
        self.sea_level = 0.0  # waterline offset: >0 floods, <0 exposes land
        self.light_radius = 26.0  # lit radius around the player, in pixels
        self.show_features = True
        self.show_minimap = False
        self.show_help = False
        self.frame_budget = 1.0 / fps
        self.start = 0.0
        self.start_dt = datetime.now(timezone.utc)
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
        """Move once per frame. Cardinal only: the last movement key wins."""
        mx = my = 0
        for key in keys:
            move = _MOVES.get(key)
            if move:
                mx, my = move
            else:
                self._handle(key)
        self.px += mx
        self.py += my

    def _handle(self, key: str) -> None:
        if key in ("q", "\x03"):
            self.running = False
        elif key == "\x1b":  # Esc closes the help modal, or quits if it is closed
            if self.show_help:
                self.show_help = False
            else:
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
            self.show_help = not self.show_help

    # --- clock -------------------------------------------------------------
    def _clock(self) -> tuple[int, str, str]:
        """One real second is one in-game minute, counting from today (UTC)."""
        total = int(time.monotonic() - self.start)  # in-game minutes elapsed
        now = self.start_dt + timedelta(minutes=total)
        return total, now.strftime("%H:%M"), now.strftime("%Y-%m-%d")

    # --- frame -------------------------------------------------------------
    def _top_bar(self, cols: int, stats: tuple) -> str:
        elev, moist, temp = stats
        _, clock, date = self._clock()
        height = round((elev - 0.50) * 8000)  # metres relative to the shoreline (sea = 0)
        left = (
            f" @ {int(self.px):+d},{int(self.py):+d}  "
            f"{biomes.name(elev, moist, temp)}  {height:+d}m  {biomes.celsius(temp):+d}°C  "
            f"{clock}  {date} "
        )
        right = "(h)elp "
        pad = max(1, cols - len(left) - len(right) + 1)  # +1: °C is one display column
        bar = (left + " " * pad + right)[:cols]
        return f"\x1b[1;1H\x1b[7m{bar}\x1b[0m"

    def _help_modal(self, cols: int, rows: int) -> str:
        inner = max(len(_HELP_TITLE), max(len(s) for s in _HELP_LINES)) + 2
        body = [
            _HELP_TITLE.center(inner),
            "─" * inner,
            *[s.ljust(inner) for s in _HELP_LINES],
        ]
        box = ["┌" + "─" * inner + "┐"]
        box += [
            ("├" if row == "─" * inner else "│")
            + row
            + ("┤" if row == "─" * inner else "│")
            for row in body
        ]
        box += ["└" + "─" * inner + "┘"]
        if rows < len(box) + 2 or cols < inner + 4:
            return ""  # no room for the modal
        r0 = (rows - len(box)) // 2 + 1
        c0 = (cols - (inner + 2)) // 2 + 1
        style = "\x1b[48;2;26;28;40m\x1b[38;2;236;236;242m"
        return "".join(
            f"\x1b[{r0 + i};{c0}H{style}{row}\x1b[0m" for i, row in enumerate(box)
        )

    def _draw(
        self,
        cols: int,
        rows: int,
        cam_x: int,
        cam_y: int,
        player_px: int,
        player_py: int,
    ) -> None:
        rgb, chars, fg, stats = compose(
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
            player_px=player_px,
            player_py=player_py,
        )
        frame = render(rgb, chars, fg) + self._top_bar(cols, stats)
        if self.show_help:
            frame += self._help_modal(cols, rows)
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
            self.start = time.monotonic()
            self.start_dt = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            last_sig = None
            while self.running:
                loop_start = time.monotonic()
                self._step(self._read_keys())
                cols, rows = os.get_terminal_size()
                # Horizontal cells are 1px: keep the player centered, scroll every step.
                # Vertical cells are 2px: snap the camera down to an even row so the
                # player rides the top/bottom half of its cell, and the world only
                # scrolls when it crosses a whole cell.
                cam_x = self.px - cols // 2
                cam_y = self.py - rows
                cam_y -= cam_y & 1
                player_px = self.px - cam_x  # == cols // 2
                player_py = self.py - cam_y  # rows or rows+1 (top/bottom highlight)
                minute = int(time.monotonic() - self.start)
                sig = (
                    self.px, self.py, self.sea_level, self.light_radius,
                    self.show_features, self.show_minimap, self.show_help,
                    minute, cols, rows,
                )  # fmt: skip
                if sig != last_sig and cols >= 2 and rows >= 1:
                    self._draw(cols, rows, cam_x, cam_y, player_px, player_py)
                    last_sig = sig
                elapsed = time.monotonic() - loop_start
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
