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


ShapeInfo = RectInfo | ArcInfo
ShapeType = Literal["rect", "arc"]


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
