"""Logo module for remote.py CLI with gradient rendering."""

import importlib.metadata

from rich.console import Console
from rich.text import Text

# Fire palette: yellow -> orange -> pink -> purple
FIRE_PALETTE = [
    "#ffbe0b",  # Yellow
    "#fb5607",  # Orange
    "#ff006e",  # Pink
    "#8338ec",  # Purple
]

# ANSI Shadow style block letters spelling "REMOTE"
LOGO = r"""
██████╗ ███████╗███╗   ███╗ ██████╗ ████████╗███████╗   ██████╗ ██╗   ██╗
██╔══██╗██╔════╝████╗ ████║██╔═══██╗╚══██╔══╝██╔════╝   ██╔══██╗╚██╗ ██╔╝
██████╔╝█████╗  ██╔████╔██║██║   ██║   ██║   █████╗     ██████╔╝ ╚████╔╝
██╔══██╗██╔══╝  ██║╚██╔╝██║██║   ██║   ██║   ██╔══╝     ██╔═══╝   ╚██╔╝
██║  ██║███████╗██║ ╚═╝ ██║╚██████╔╝   ██║   ███████╗██╗██║        ██║
╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝╚═╝        ╚═╝
"""


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def interpolate_color(
    color1: tuple[int, int, int],
    color2: tuple[int, int, int],
    factor: float,
) -> tuple[int, int, int]:
    """Interpolate between two RGB colors.

    Args:
        color1: Starting RGB color tuple
        color2: Ending RGB color tuple
        factor: Interpolation factor (0.0 = color1, 1.0 = color2)

    Returns:
        Interpolated RGB color tuple
    """
    return (
        int(color1[0] + (color2[0] - color1[0]) * factor),
        int(color1[1] + (color2[1] - color1[1]) * factor),
        int(color1[2] + (color2[2] - color1[2]) * factor),
    )


def get_color_for_line(line_index: int, total_lines: int, palette: list[str]) -> str:
    """Calculate the interpolated color for a given line.

    Args:
        line_index: Index of the current line
        total_lines: Total number of lines
        palette: List of hex color strings

    Returns:
        Hex color string for this line
    """
    if total_lines <= 1:
        return palette[0]

    rgb_colors = [_hex_to_rgb(c) for c in palette]
    factor = line_index / (total_lines - 1)

    # Find which color segment we're in
    segment = factor * (len(rgb_colors) - 1)
    idx = int(segment)
    local_factor = segment - idx

    if idx >= len(rgb_colors) - 1:
        color = rgb_colors[-1]
    else:
        color = interpolate_color(rgb_colors[idx], rgb_colors[idx + 1], local_factor)

    return f"rgb({color[0]},{color[1]},{color[2]})"


def get_version() -> str:
    """Get the current package version."""
    try:
        version = importlib.metadata.version("remotepy")
        # Handle deprecated implicit None return (will become KeyError in future)
        return version if version is not None else "0.0.0"
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def print_logo(show_version: bool = False) -> None:
    """Print the logo with gradient colors.

    Args:
        show_version: If True, display version info below the logo
    """
    console = Console()
    lines = LOGO.strip().split("\n")
    total_lines = len(lines)

    styled_text = Text()
    for i, line in enumerate(lines):
        color = get_color_for_line(i, total_lines, FIRE_PALETTE)
        styled_text.append(line + "\n", style=color)

    console.print(styled_text, end="")

    if show_version:
        version = get_version()
        console.print(f"  [dim]v{version}[/dim]")
        console.print()
