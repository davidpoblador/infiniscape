# ABOUTME: Standalone POC for the sticky-heading diagonal heuristic (no map).
# ABOUTME: A latched direction is sustained by whichever key keeps auto-repeating.

import os
import select
import sys
import termios
import time
import tty

_ARROWS = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left"}
_MOVES = {
    "up": (0, -1), "w": (0, -1), "down": (0, 1), "s": (0, 1),
    "left": (-1, 0), "a": (-1, 0), "right": (1, 0), "d": (1, 0),
}  # fmt: skip
_NAME = {(0, 0): "·", (0, -1): "N", (0, 1): "S", (-1, 0): "W", (1, 0): "E",
         (-1, -1): "NW", (1, -1): "NE", (-1, 1): "SW", (1, 1): "SE"}  # fmt: skip


def _tokens(data):
    out, i = [], 0
    while i < len(data):
        if data[i : i + 3] in _ARROWS:
            out.append(_ARROWS[data[i : i + 3]])
            i += 3
        else:
            out.append(data[i])
            i += 1
    return out


def main():
    try:
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        opened = True
    except OSError:
        fd, opened = sys.stdin.fileno(), False
    old = termios.tcgetattr(fd)

    def w(s):
        os.write(fd, s.encode())

    window = 0.08   # seconds: two keys within this make a diagonal
    release = 0.10  # seconds of silence before the heading clears
    x = y = 0
    hx = hy = 0          # current heading
    last_active = -1.0
    recent = []          # (move, time) within the combine window

    w(
        "\r\n  sticky-heading diagonal POC (no map)\r\n"
        "  press two arrows TOGETHER, then KEEP THEM HELD -> should keep going diagonal.\r\n"
        "  [ / ] window    - / = release    r reset    Ctrl-C quits\r\n"
        f"  window={window * 1000:.0f}ms  release={release * 1000:.0f}ms\r\n\r\n"
    )
    try:
        tty.setcbreak(fd)
        while True:
            select.select([fd], [], [], 0.008)
            now = time.monotonic()
            data = ""
            while select.select([fd], [], [], 0)[0]:
                chunk = os.read(fd, 64)
                if not chunk:
                    break
                data += chunk.decode("utf-8", "ignore")
            for k in _tokens(data):
                if k == "\x03":
                    raise KeyboardInterrupt
                if k in ("[", "]"):
                    window = max(0.02, min(0.3, window + (0.01 if k == "]" else -0.01)))
                    w(f"  window={window * 1000:.0f}ms\r\n")
                    continue
                if k in ("-", "="):
                    release = max(0.1, min(1.0, release + (0.05 if k == "=" else -0.05)))
                    w(f"  release={release * 1000:.0f}ms\r\n")
                    continue
                if k == "r":
                    x = y = 0
                    w("  reset 0,0\r\n")
                    continue
                mv = _MOVES.get(k)
                if not mv:
                    continue
                gap = "" if last_active < 0 else f" (+{(now - last_active) * 1000:.0f}ms)"
                last_active = now
                recent = [(m, t) for m, t in recent if now - t <= window]
                recent.append((mv, now))
                cx = cy = 0
                for m, _ in recent:
                    cx = m[0] or cx
                    cy = m[1] or cy
                if hx == 0 and hy == 0:
                    hx, hy = cx, cy  # start a fresh heading
                else:
                    hx = cx or hx  # a silent axis keeps its latched value -> diagonal holds
                    hy = cy or hy
                x += hx
                y += hy
                w(f"  key {_NAME[mv]:>2}{gap}  ->  {_NAME[(hx, hy)]:>2}  pos {x},{y}\r\n")
            if last_active >= 0 and (hx or hy) and now - last_active >= release:
                hx = hy = 0
                w("  -- released, heading cleared --\r\n")
    except KeyboardInterrupt:
        pass
    finally:
        w("\r\n  done.\r\n")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if opened:
            os.close(fd)


if __name__ == "__main__":
    main()
