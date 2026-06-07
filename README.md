# infiniscape

An infinite, procedurally generated world rendered as a smooth colored surface
right in your terminal. Each character cell is split into two pixels using the
upper half-block (`▀`) with truecolor foreground/background, so the picture has
twice the vertical resolution of the text grid and fills whatever terminal size
you give it.

The terrain is fractal Perlin noise (fBm) shaded by slope and colored through an
elevation palette (deep ocean → shallows → sand → grass → forest → rock → snow).
The view auto-drifts across an endless landscape; you can steer, zoom, and pause.

## Run

```sh
uv run infiniscape          # or: uv run python -m infiniscape
uv run infiniscape 42       # optional integer seed for a different world
```

Needs a truecolor-capable terminal (most modern ones: iTerm2, Kitty, Alacritty,
Ghostty, WezTerm, modern Terminal.app, VS Code).

## Controls

| Key | Action |
| --- | --- |
| arrows / `wasd` | pan the camera |
| `+` / `-` | zoom in / out |
| `space` | toggle auto-drift |
| `h` | toggle the heads-up display |
| `q` / `Esc` | quit |

## How it works

- `noise.py` — vectorized 2D Perlin noise and fractal Brownian motion.
- `palette.py` — smooth interpolation between elevation color stops.
- `world.py` — samples the camera window, adds hillshade, applies the palette.
- `renderer.py` — packs the RGB grid into a half-block ANSI frame.
- `app.py` — terminal setup, raw input, camera, and the render loop.
