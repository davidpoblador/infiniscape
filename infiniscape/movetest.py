# ABOUTME: Standalone POC to test/tune the two-key->diagonal heuristic only.
# ABOUTME: No map drawing; logs key arrivals, gaps, and each emitted step.

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
_NAME = {(0, -1): "N", (0, 1): "S", (-1, 0): "W", (1, 0): "E",
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

    window = 0.08  # seconds
    x = y = 0
    mx = my = 0
    pend_t = 0.0
    moving = False
    last_key = None

    w(
        "\r\n  diagonal heuristic POC (no map)\r\n"
        "  press two arrows/wasd TOGETHER -> should log a DIAGONAL step.\r\n"
        "  [ / ] shrink/grow the combine window.   r = reset position.   Ctrl-C quits.\r\n"
        f"  window = {window * 1000:.0f} ms\r\n\r\n"
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
                if k == "[":
                    window = max(0.01, window - 0.01)
                    w(f"  window = {window * 1000:.0f} ms\r\n")
                    continue
                if k == "]":
                    window = min(0.5, window + 0.01)
                    w(f"  window = {window * 1000:.0f} ms\r\n")
                    continue
                if k == "r":
                    x = y = 0
                    w("  position reset to 0,0\r\n")
                    continue
                mv = _MOVES.get(k)
                if not mv:
                    continue
                gap = "" if last_key is None else f"  (+{(now - last_key) * 1000:.0f}ms)"
                last_key = now
                w(f"  key {_NAME[mv]:>2}{gap}\r\n")
                if mx == 0 and my == 0 and not moving:
                    pend_t = now
                mx = mv[0] or mx
                my = mv[1] or my

            if mx and my:
                x += mx
                y += my
                w(f"    -> *** DIAGONAL {_NAME[(mx, my)]} ***   pos {x},{y}\r\n")
                mx = my = 0
                moving = True
            elif mx or my:
                if moving or now - pend_t >= window:
                    waited = (now - pend_t) * 1000
                    x += mx
                    y += my
                    tag = "held" if moving else f"waited {waited:.0f}ms"
                    w(f"    -> cardinal {_NAME[(mx, my)]}  ({tag})   pos {x},{y}\r\n")
                    mx = my = 0
                    moving = True
            else:
                moving = False
    except KeyboardInterrupt:
        pass
    finally:
        w("\r\n  done.\r\n")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if opened:
            os.close(fd)


if __name__ == "__main__":
    main()
