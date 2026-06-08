# infiniscape

An infinite, procedurally generated world rendered as a smooth colored surface
right in your terminal. Each character cell is split into two pixels using the
upper half-block (`▀`) with truecolor foreground/background, so the picture has
twice the vertical resolution of the text grid and fills whatever terminal size
you give it.

It is a showcase of how much world fits in a terminal before building an actual
game on top: realistic terrain with continents, seas, mountain ranges and
rivers; biomes driven by moisture and temperature; sprite glyphs for trees and
terrain; a player with a torch; a day/night clock and calendar; and a minimap.

## Run

From a checkout:

```sh
uv run infiniscape          # or: uv run python -m infiniscape
uv run infiniscape 42       # optional integer seed for a different world
```

Straight from GitHub, no clone needed:

```sh
uv run --from git+https://github.com/davidpoblador/infiniscape infiniscape
uv run --from git+https://github.com/davidpoblador/infiniscape infiniscape 42
```

Needs a truecolor-capable terminal (most modern ones: iTerm2, Kitty, Alacritty,
Ghostty, WezTerm, modern Terminal.app, VS Code).

## Controls

| Key | Action |
| --- | --- |
| arrows / `wasd` | move (press two keys together for a diagonal) |
| `,` / `.` | lower / raise the sea level |
| `[` / `]` | shrink / grow the light radius |
| `f` | toggle sprites |
| `m` | toggle the minimap |
| `h` | open / close the help modal |
| `q` / `Esc` | quit |

The status bar shows your coordinates, the current biome and temperature, and a
clock and date (one real second is one in-game minute). You start at the world
origin `(0,0)`; coordinates go negative in every direction.

## The world

- **Elevation** is domain-warped fractal noise: low-frequency continents with a
  contrast curve for real oceans and plains.
- **Mountains** are ridged multifractal noise added on high ground, giving sharp
  ridgelines that catch the light, with snow on the peaks.
- **Rivers** follow the zero-set of a warped noise channel, gated to land,
  widening toward the coast, and carved into the height so they run through
  shaded valleys to the sea. Everything is a pure function of position, so it
  streams infinitely and stays stable as you move.
- **Biomes** come from elevation plus separate moisture and temperature fields:
  deserts, savanna, grassland, forest, rainforest, taiga, tundra, and alpine.

## Snapshots

`scripts/snapshot.py` renders composed frames to PNG (half-block cells plus
sprite glyphs via a monospace font), for sharing the world off-terminal:

```sh
uv run python scripts/snapshot.py /path/to/output_dir
```

## How it works

- `noise.py` — vectorized Perlin fBm and ridged multifractal noise.
- `world.py` — the terrain pipeline: continents, mountains, rivers, biomes.
- `palette.py` — bilinear blend over an elevation × moisture biome table.
- `features.py` — scatters biome-appropriate sprite glyphs by a stable hash.
- `biomes.py` — names the biome at a point for the status bar.
- `masks.py` — the player-centered light/shadow masks and player color.
- `scene.py` — composes a frame: terrain, light, player, sprites, minimap.
- `renderer.py` — packs the result into a half-block ANSI frame.
- `app.py` — terminal setup, input, the player, status bar, and help modal.
