# ABOUTME: Diagnostic that logs the raw bytes a terminal sends for key presses.
# ABOUTME: Use it to see whether two keys held at once are both reported.

import os
import select
import sys
import termios
import time
import tty

_ARROWS = {"\x1b[A": "Up", "\x1b[B": "Down", "\x1b[C": "Right", "\x1b[D": "Left"}
_KITTY_ON = "\x1b[>1u"  # push the kitty keyboard progressive-enhancement flag
_KITTY_OFF = "\x1b[<u"


def _decode(data: str) -> list[str]:
    keys, i = [], 0
    while i < len(data):
        if data[i : i + 3] in _ARROWS:
            keys.append(_ARROWS[data[i : i + 3]])
            i += 3
        elif data[i] == " ":
            keys.append("Space")
            i += 1
        else:
            keys.append(repr(data[i]))
            i += 1
    return keys


def main() -> None:
    try:
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        opened = True
    except OSError:
        fd, opened = sys.stdin.fileno(), False
    old = termios.tcgetattr(fd)

    def w(s: str) -> None:
        os.write(fd, s.encode())

    kitty = False
    w(
        "\r\n  key probe — press keys (try two arrows AT ONCE, and hold two keys).\r\n"
        "  each line is one read() from the terminal.\r\n"
        "  'k' toggles the kitty keyboard protocol (press/release events).\r\n"
        "  Ctrl-C to quit.\r\n\r\n"
    )
    try:
        tty.setcbreak(fd)
        last = time.monotonic()
        while True:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            data = os.read(fd, 256).decode("utf-8", "ignore")
            if not data:
                continue
            if "\x03" in data:
                break
            if data == "k":
                kitty = not kitty
                w(_KITTY_ON if kitty else _KITTY_OFF)
                w(f"  >> kitty keyboard protocol {'ENABLED' if kitty else 'disabled'}\r\n")
                continue
            now = time.monotonic()
            gap = (now - last) * 1000
            last = now
            keys = _decode(data)
            hexs = " ".join(f"{ord(c):02x}" for c in data)
            note = ""
            distinct = {k for k in keys if k in ("Up", "Down", "Left", "Right")}
            if len(distinct) >= 2:
                note = "   <-- TWO directions in one read!"
            w(f"  +{gap:6.0f}ms  bytes=[{hexs}]  keys={keys}{note}\r\n")
    finally:
        if kitty:
            w(_KITTY_OFF)
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if opened:
            os.close(fd)


if __name__ == "__main__":
    main()
