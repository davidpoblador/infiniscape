# ABOUTME: Names the biome at a point from elevation, moisture, and temperature.
# ABOUTME: Used for the heads-up display; bands line up with the color palette.


def name(elev: float, moist: float, temp: float) -> str:
    """Return a short biome label for the given normalized fields."""
    if elev < 0.50:
        return "Ocean" if elev < 0.45 else "Shallows"
    if elev < 0.55:
        return "Beach"
    if elev >= 0.97:
        return "Snow"
    if elev >= 0.84:
        return "Alpine" if temp < 0.35 else "Mountains"
    if temp < 0.28:
        return "Tundra"
    if moist < 0.25:
        return "Desert"
    if moist < 0.45:
        return "Savanna" if temp > 0.5 else "Shrubland"
    if moist < 0.68:
        return "Grassland"
    if temp < 0.42:
        return "Taiga"
    return "Rainforest" if temp > 0.72 else "Forest"


def celsius(temp: float) -> int:
    """Map a normalized temperature [0,1] to a rough Celsius value."""
    return int(round(-12 + temp * 46))
