# infiniscape

An infinite, procedurally generated world rendered as a smooth colored surface
right in your terminal. Each character cell is split into two pixels using the
upper half-block (`▀`) with truecolor foreground/background, so the picture has
twice the vertical resolution of the text grid and fills whatever terminal size
you give it.

This is a showcase of how much world you can pack into a terminal before
building an actual game on top of it: smooth biome terrain, scattered sprite
glyphs, a player with a torch, an adjustable sea level, and a live minimap.

You play an explorer drawn as a single half-block pixel (so the marker sits on
its exact world coordinate), colored as a contrast-guaranteed negative of the
terrain and nested in a small neutral shadow so it always stands out. You carry
a light that reveals only the area around you; the rest fades to darkness.

The terrain is fractal Perlin noise (fBm) shaded by slope. Colors come from a 2D
**biome** table indexed by elevation and a separate, larger-scale moisture
field: dry regions turn to ochre desert and savanna, wet regions to lush forest
and jungle, with temperate greens between, plus beaches, rock, and snow by
altitude. Sprite glyphs (`♠ ♣` forest, `"` grass, `Y` scrub, `•` rock, `▲`
peaks, `~` ripples) are scattered deterministically by biome so they stay put as
you move.

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
| arrows / `wasd` | set heading (combine axes for diagonals) |
| `space` | stop |
| `,` / `.` | lower / raise the sea level |
| `[` / `]` | shrink / grow the light radius |
| `f` | toggle sprites |
| `m` | toggle the minimap |
| `h` | toggle the heads-up display |
| `q` / `Esc` | quit |

Movement is a persistent heading: tap a direction to start drifting that way,
tap it again to cancel that axis, or press a key on the other axis to steer
diagonally (e.g. go left, then press up to move up-left).

## Snapshots

`scripts/snapshot.py` renders composed frames to PNG (half-block cells plus
sprite glyphs via a monospace font), handy for sharing the world off-terminal:

```sh
uv run python scripts/snapshot.py /path/to/output_dir
```

## How it works

- `noise.py` — vectorized 2D Perlin noise and fractal Brownian motion.
- `palette.py` — bilinear blend over an elevation × moisture biome table.
- `world.py` — samples elevation and moisture, adds hillshade, applies biomes.
- `features.py` — scatters biome-appropriate sprite glyphs by a stable hash.
- `masks.py` — the player-centered light/shadow masks and player color.
- `scene.py` — composes a frame: terrain, light, player, sprites, minimap.
- `renderer.py` — packs the result into a half-block ANSI frame.
- `app.py` — terminal setup, input, the player, and the render loop.
