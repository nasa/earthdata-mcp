"""Colormaps as evenly spaced hex stops (matplotlib reference colors).

Kept server-side so the map runtime and the legend use the same stops, and so
tool inputs can be validated against a fixed list.
"""

from __future__ import annotations

COLORMAPS: dict[str, list[str]] = {
    "viridis": ["#440154", "#482878", "#3e4989", "#31688e", "#26828e",
                "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
    "plasma": ["#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786",
               "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921"],
    "inferno": ["#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60",
                "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4"],
    "magma": ["#000004", "#180f3d", "#440f76", "#721f81", "#9e2f7f",
              "#cd4071", "#f1605d", "#fd9668", "#feca8d", "#fcfdbf"],
    "turbo": ["#30123b", "#4662d7", "#36aaf9", "#1ae4b6", "#72fe5e",
              "#c8ef34", "#faba39", "#f66b19", "#ca2a04", "#7a0403"],
    # Diverging, blue (low) to red (high): anomalies, differences.
    "rdbu_r": ["#053061", "#2166ac", "#4393c3", "#92c5de", "#d1e5f0",
               "#f7f7f7", "#fddbc7", "#f4a582", "#d6604d", "#b2182b", "#67001f"],
    "blues": ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6",
              "#4292c6", "#2171b5", "#08519c", "#08306b"],
    "greens": ["#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476",
               "#41ab5d", "#238b45", "#006d2c", "#00441b"],
    "gray": ["#000000", "#ffffff"],
}

COLORMAP_NAMES: list[str] = sorted(COLORMAPS)


def colormap_rgb(name: str, reverse: bool = False) -> list[list[int]]:
    """Stops as [[r, g, b], ...]."""
    stops = [[int(h[i : i + 2], 16) for i in (1, 3, 5)] for h in COLORMAPS[name]]
    return stops[::-1] if reverse else stops
