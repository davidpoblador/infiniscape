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
uvx --from git+https://github.com/davidpoblador/infiniscape infiniscape
uvx --from git+https://github.com/davidpoblador/infiniscape infiniscape 42
```

Needs a truecolor-capable terminal (most modern ones: iTerm2, Kitty, Alacritty,
Ghostty, WezTerm, modern Terminal.app, VS Code).

## Controls

| Key | Action |
| --- | --- |
| arrows / `wasd` | move (one cardinal step at a time) |
| `,` / `.` | lower / raise the sea level |
| `[` / `]` | shrink / grow the light radius |
| `f` | toggle sprites |
| `m` | toggle the minimap |
| `p` | save a smooth high-res PNG of the location and open it in Preview |
| `h` | open / close the help modal |
| `q` / `Esc` | quit |

Movement is cardinal (terminals can't reliably report two keys at once). The status bar shows your coordinates, the current biome and temperature, and a
clock and date (one real second is one in-game minute). You start at the world
origin `(0,0)`; coordinates go negative in every direction.

## The world

The world is **metric: one cell is one metre**. Terrain is built from physically
scaled noise octaves (wavelengths from metres to kilometres, amplitudes chosen so
per-metre slopes stay realistic), so what you see on screen is ~150 m of gentle
rolling ground — believable hillsides, not noise cliffs. Heights in the status
bar are real metres relative to sea level.

Because a real continent is tens of kilometres across, coastlines, mountain
ranges and the open sea are usually off-screen; a single view is mostly one
biome with subtle elevation. The **minimap** is your regional overview (hundreds
of metres per cell), where landmasses, seas and your position show up. Moisture
and temperature vary over kilometres and set the biome (desert, savanna,
grassland, forest, rainforest, taiga, tundra, alpine); rivers are local streams
that settle in valleys. Coarse views fade out sub-cell detail so they stay smooth
instead of aliasing.

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
