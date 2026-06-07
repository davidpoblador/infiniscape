# infiniscape

An infinite, procedurally generated world rendered as a smooth colored surface
right in your terminal. Each character cell is split into two pixels using the
upper half-block (`▀`) with truecolor foreground/background, so the picture has
twice the vertical resolution of the text grid and fills whatever terminal size
you give it.

You play an explorer standing at the center of the view, drawn as a single
half-block pixel so the marker sits exactly on its world coordinate. Its color
is a contrast-guaranteed negative of the terrain beneath it, so it always pops.
You carry a light that reveals only the area around you; walk in any direction
and the endless landscape scrolls beneath you, fading to darkness at sight's edge.

The terrain is fractal Perlin noise (fBm) shaded by slope. Colors come from a
2D **biome** table indexed by elevation and a separate, larger-scale moisture
field: dry regions turn to ochre deserts and savanna, wet regions to lush
forest and jungle, with temperate greens in between, plus beaches, rock, and
snow by altitude.

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
| arrows / `wasd` | move the player |
| `+` / `-` | zoom in / out |
| `[` / `]` | shrink / grow the light radius |
| `space` | toggle auto-walk |
| `h` | toggle the heads-up display |
| `q` / `Esc` | quit |

## How it works

- `noise.py` — vectorized 2D Perlin noise and fractal Brownian motion.
- `palette.py` — bilinear blend over an elevation × moisture biome table.
- `world.py` — samples elevation and moisture, adds hillshade, applies biomes.
- `renderer.py` — packs the RGB grid into a half-block ANSI frame.
- `app.py` — terminal setup, input, the player, the light mask, render loop.
