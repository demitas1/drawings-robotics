"""Geometry utilities for SVG shape validation and alignment."""

from dataclasses import dataclass
from typing import Literal
from xml.etree import ElementTree as ET

from .utils import SVG_NAMESPACES, get_local_name


@dataclass
class BoundingBox:
    """Axis-aligned bounding box."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center_x(self) -> float:
        """X coordinate of the center."""
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        """Y coordinate of the center."""
        return self.y + self.height / 2

    @property
    def center(self) -> tuple[float, float]:
        """Center point (x, y)."""
        return (self.center_x, self.center_y)


@dataclass
class RectInfo:
    """Information extracted from a rect element."""

    element: ET.Element
    id: str
    x: float
    y: float
    width: float
    height: float

    @property
    def bbox(self) -> BoundingBox:
        """Get bounding box."""
        return BoundingBox(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> tuple[float, float]:
        """Center coordinates."""
        return self.bbox.center


@dataclass
class ArcInfo:
    """Information extracted from an arc (path with sodipodi:type=arc) element."""

    element: ET.Element
    id: str
    cx: float
    cy: float
    rx: float
    ry: float
    start: float
    end: float

    @property
    def bbox(self) -> BoundingBox:
        """Get bounding box."""
        return BoundingBox(
            self.cx - self.rx,
            self.cy - self.ry,
            self.rx * 2,
            self.ry * 2,
        )

    @property
    def center(self) -> tuple[float, float]:
        """Center coordinates."""
        return (self.cx, self.cy)

    @property
    def arc_span(self) -> float:
        """Arc span in radians."""
        return abs(self.end - self.start)


@dataclass
class PathInfo:
    """Information extracted from a path element (line segments).

    Supports simple paths with M (move to) and L/H/V (line to) commands.
    Stores start and end points for grid alignment.
    """

    element: ET.Element
    id: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float

    @property
    def bbox(self) -> BoundingBox:
        """Get bounding box."""
        min_x = min(self.start_x, self.end_x)
        min_y = min(self.start_y, self.end_y)
        width = abs(self.end_x - self.start_x)
        height = abs(self.end_y - self.start_y)
        return BoundingBox(min_x, min_y, width, height)

    @property
    def center(self) -> tuple[float, float]:
        """Center coordinates."""
        return self.bbox.center

    @property
    def is_vertical(self) -> bool:
        """Check if path is a vertical line."""
        return abs(self.start_x - self.end_x) < 0.001

    @property
    def is_horizontal(self) -> bool:
        """Check if path is a horizontal line."""
        return abs(self.start_y - self.end_y) < 0.001


ShapeInfo = RectInfo | ArcInfo | PathInfo
ShapeType = Literal["rect", "arc", "path"]


def parse_rect(element: ET.Element) -> RectInfo | None:
    """Parse a rect element.

    Args:
        element: SVG rect element.

    Returns:
        RectInfo or None if parsing fails.
    """
    if get_local_name(element.tag) != "rect":
        return None

    try:
        return RectInfo(
            element=element,
            id=element.get("id", ""),
            x=float(element.get("x", 0)),
            y=float(element.get("y", 0)),
            width=float(element.get("width", 0)),
            height=float(element.get("height", 0)),
        )
    except (ValueError, TypeError):
        return None


def parse_arc(element: ET.Element) -> ArcInfo | None:
    """Parse an arc element (path with sodipodi:type=arc).

    Args:
        element: SVG path element with arc type.

    Returns:
        ArcInfo or None if not an arc or parsing fails.
    """
    if get_local_name(element.tag) != "path":
        return None

    sodipodi_ns = SVG_NAMESPACES["sodipodi"]
    arc_type = element.get(f"{{{sodipodi_ns}}}type")
    if arc_type != "arc":
        return None

    try:
        return ArcInfo(
            element=element,
            id=element.get("id", ""),
            cx=float(element.get(f"{{{sodipodi_ns}}}cx", 0)),
            cy=float(element.get(f"{{{sodipodi_ns}}}cy", 0)),
            rx=float(element.get(f"{{{sodipodi_ns}}}rx", 0)),
            ry=float(element.get(f"{{{sodipodi_ns}}}ry", 0)),
            start=float(element.get(f"{{{sodipodi_ns}}}start", 0)),
            end=float(element.get(f"{{{sodipodi_ns}}}end", 0)),
        )
    except (ValueError, TypeError):
        return None


def parse_path(element: ET.Element) -> PathInfo | None:
    """Parse a path element (simple line paths, not arcs).

    Supports paths with M (moveto) and L/H/V (lineto) commands.
    Both absolute (M, L, H, V) and relative (m, l, h, v) commands are supported.

    Args:
        element: SVG path element.

    Returns:
        PathInfo or None if not a simple line path or parsing fails.
    """
    if get_local_name(element.tag) != "path":
        return None

    # Skip arc elements (handled by parse_arc)
    sodipodi_ns = SVG_NAMESPACES["sodipodi"]
    if element.get(f"{{{sodipodi_ns}}}type") == "arc":
        return None

    d = element.get("d", "")
    if not d:
        return None

    try:
        return _parse_path_d(element, d)
    except (ValueError, IndexError):
        return None


def _parse_path_d(element: ET.Element, d: str) -> PathInfo | None:
    """Parse path d attribute to extract start and end points.

    Args:
        element: SVG path element.
        d: Path data string.

    Returns:
        PathInfo or None if parsing fails.
    """
    # Tokenize: split on command letters while keeping them
    import re
    tokens = re.findall(r'[MmLlHhVvZz]|[-+]?\d*\.?\d+', d)

    if not tokens:
        return None

    current_x = 0.0
    current_y = 0.0
    start_x = 0.0
    start_y = 0.0
    end_x = 0.0
    end_y = 0.0
    has_start = False

    i = 0
    while i < len(tokens):
        cmd = tokens[i]

        if cmd in ('M', 'm'):
            # Moveto command
            i += 1
            x = float(tokens[i])
            i += 1
            y = float(tokens[i])
            i += 1

            if cmd == 'm' and has_start:
                # Relative moveto
                x += current_x
                y += current_y

            current_x = x
            current_y = y

            if not has_start:
                start_x = x
                start_y = y
                has_start = True

            end_x = x
            end_y = y

        elif cmd == 'L':
            # Absolute lineto
            i += 1
            x = float(tokens[i])
            i += 1
            y = float(tokens[i])
            i += 1
            current_x = x
            current_y = y
            end_x = x
            end_y = y

        elif cmd == 'l':
            # Relative lineto
            i += 1
            dx = float(tokens[i])
            i += 1
            dy = float(tokens[i])
            i += 1
            current_x += dx
            current_y += dy
            end_x = current_x
            end_y = current_y

        elif cmd == 'H':
            # Absolute horizontal lineto
            i += 1
            x = float(tokens[i])
            i += 1
            current_x = x
            end_x = x
            end_y = current_y

        elif cmd == 'h':
            # Relative horizontal lineto
            i += 1
            dx = float(tokens[i])
            i += 1
            current_x += dx
            end_x = current_x
            end_y = current_y

        elif cmd == 'V':
            # Absolute vertical lineto
            i += 1
            y = float(tokens[i])
            i += 1
            current_y = y
            end_x = current_x
            end_y = y

        elif cmd == 'v':
            # Relative vertical lineto
            i += 1
            dy = float(tokens[i])
            i += 1
            current_y += dy
            end_x = current_x
            end_y = current_y

        elif cmd in ('Z', 'z'):
            # Close path - end point goes back to start
            end_x = start_x
            end_y = start_y
            current_x = start_x
            current_y = start_y
            i += 1

        else:
            # Unknown command or number (skip)
            i += 1

    if not has_start:
        return None

    return PathInfo(
        element=element,
        id=element.get("id", ""),
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
    )


def parse_shape(element: ET.Element, shape_type: ShapeType) -> ShapeInfo | None:
    """Parse an element as the specified shape type.

    Args:
        element: SVG element to parse.
        shape_type: Expected shape type.

    Returns:
        ShapeInfo or None if parsing fails or type doesn't match.
    """
    if shape_type == "rect":
        return parse_rect(element)
    elif shape_type == "arc":
        return parse_arc(element)
    elif shape_type == "path":
        return parse_path(element)
    return None


def snap_to_grid(value: float, grid_unit: float) -> float:
    """Snap a value to the nearest grid position.

    Args:
        value: Value to snap.
        grid_unit: Grid unit size.

    Returns:
        Snapped value.
    """
    return round(value / grid_unit) * grid_unit


def check_grid_alignment(
    value: float, grid_unit: float, tolerance: float
) -> tuple[bool, float]:
    """Check if a value is aligned to the grid.

    Args:
        value: Value to check.
        grid_unit: Grid unit size.
        tolerance: Acceptable deviation.

    Returns:
        Tuple of (is_aligned, deviation).
    """
    remainder = value % grid_unit
    # Check both remainder and (grid_unit - remainder)
    deviation = min(remainder, grid_unit - remainder)
    return (deviation <= tolerance, deviation)


def check_value_match(
    actual: float, expected: float, tolerance: float, error_threshold: float
) -> tuple[Literal["ok", "fixable", "error"], float]:
    """Check if a value matches expected within tolerances.

    Args:
        actual: Actual value.
        expected: Expected value.
        tolerance: Acceptable deviation (no fix needed).
        error_threshold: Maximum fixable deviation ratio (0.1 = 10%).

    Returns:
        Tuple of (status, deviation).
        - "ok": Within tolerance, no fix needed.
        - "fixable": Deviation exceeds tolerance but within error threshold.
        - "error": Deviation exceeds error threshold, cannot fix.
    """
    deviation = abs(actual - expected)

    if deviation <= tolerance:
        return ("ok", deviation)

    # Calculate deviation ratio
    if expected != 0:
        ratio = deviation / expected
    else:
        ratio = deviation  # If expected is 0, use absolute deviation

    if ratio <= error_threshold:
        return ("fixable", deviation)
    else:
        return ("error", deviation)


def update_rect(
    element: ET.Element,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
) -> None:
    """Update rect element attributes.

    Args:
        element: SVG rect element.
        x: New x value (or None to keep current).
        y: New y value (or None to keep current).
        width: New width (or None to keep current).
        height: New height (or None to keep current).
    """
    if x is not None:
        element.set("x", str(x))
    if y is not None:
        element.set("y", str(y))
    if width is not None:
        element.set("width", str(width))
    if height is not None:
        element.set("height", str(height))


def update_arc(
    element: ET.Element,
    cx: float | None = None,
    cy: float | None = None,
    rx: float | None = None,
    ry: float | None = None,
    start: float | None = None,
    end: float | None = None,
) -> None:
    """Update arc element attributes.

    Note: This updates sodipodi attributes only. The path d attribute
    should be regenerated by Inkscape when the file is opened.

    Args:
        element: SVG path element with arc type.
        cx: New center x (or None to keep current).
        cy: New center y (or None to keep current).
        rx: New radius x (or None to keep current).
        ry: New radius y (or None to keep current).
        start: New start angle (or None to keep current).
        end: New end angle (or None to keep current).
    """
    sodipodi_ns = SVG_NAMESPACES["sodipodi"]

    if cx is not None:
        element.set(f"{{{sodipodi_ns}}}cx", str(cx))
    if cy is not None:
        element.set(f"{{{sodipodi_ns}}}cy", str(cy))
    if rx is not None:
        element.set(f"{{{sodipodi_ns}}}rx", str(rx))
    if ry is not None:
        element.set(f"{{{sodipodi_ns}}}ry", str(ry))
    if start is not None:
        element.set(f"{{{sodipodi_ns}}}start", str(start))
    if end is not None:
        element.set(f"{{{sodipodi_ns}}}end", str(end))


def update_path(
    element: ET.Element,
    start_x: float | None = None,
    start_y: float | None = None,
    end_x: float | None = None,
    end_y: float | None = None,
) -> None:
    """Update path element d attribute with new start/end points.

    Reconstructs the path d attribute based on the line type (H, V, or L).

    Args:
        element: SVG path element.
        start_x: New start x (or None to keep current).
        start_y: New start y (or None to keep current).
        end_x: New end x (or None to keep current).
        end_y: New end y (or None to keep current).
    """
    # Parse current path to get existing values
    info = parse_path(element)
    if info is None:
        return

    # Apply new values
    sx = start_x if start_x is not None else info.start_x
    sy = start_y if start_y is not None else info.start_y
    ex = end_x if end_x is not None else info.end_x
    ey = end_y if end_y is not None else info.end_y

    # Determine path type and construct d attribute
    if abs(sx - ex) < 0.001:
        # Vertical line
        d = f"M {sx},{sy} V {ey}"
    elif abs(sy - ey) < 0.001:
        # Horizontal line
        d = f"M {sx},{sy} H {ex}"
    else:
        # Diagonal line
        d = f"M {sx},{sy} L {ex},{ey}"

    element.set("d", d)
