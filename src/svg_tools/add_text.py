"""SVG text element auto-generation module."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

import yaml

from .relabel import format_index, FormatType
from .utils import register_namespaces, SVG_NAMESPACES


# Default font metrics ratios (approximate values for most fonts)
DEFAULT_CAP_HEIGHT_RATIO = 0.72  # Cap height relative to font size
DEFAULT_CHAR_WIDTH_RATIO = 0.55  # Average character width relative to font size


@dataclass
class FontConfig:
    """Font configuration for text elements."""

    family: str = "Noto Sans CJK JP"
    size: float = 1.41111  # px
    color: str = "#000000"


@dataclass
class TextFormatConfig:
    """Text label format configuration."""

    type: FormatType = "number"
    padding: int = 0
    start: int = 1
    custom: list[str] = field(default_factory=list)


@dataclass
class TextLineRule:
    """Rule for a single line of text elements."""

    name: str  # Group name to create
    y: float  # Y coordinate (mm)
    x_start: float  # Start X coordinate (mm)
    x_end: float  # End X coordinate (mm)
    x_interval: float  # X interval (mm)
    font: FontConfig = field(default_factory=FontConfig)
    format: TextFormatConfig = field(default_factory=TextFormatConfig)


@dataclass
class AddTextRule:
    """Complete text addition rule configuration."""

    groups: list[TextLineRule] = field(default_factory=list)


@dataclass
class TextElementInfo:
    """Information about a created text element."""

    element_id: str
    text: str
    grid_x: float  # Grid center X (mm)
    grid_y: float  # Grid center Y (mm)
    text_x: float  # Actual text X (mm) - adjusted for centering
    text_y: float  # Actual text Y (mm) - adjusted for centering


@dataclass
class GroupAddResult:
    """Result of adding text elements to a group."""

    group_name: str
    y: float
    x_start: float
    x_end: float
    x_interval: float
    elements: list[TextElementInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def element_count(self) -> int:
        """Number of elements created."""
        return len(self.elements)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0


@dataclass
class AddTextReport:
    """Complete text addition report."""

    file_path: Path
    group_results: list[GroupAddResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any groups have errors."""
        return any(g.has_errors for g in self.group_results)

    @property
    def total_elements(self) -> int:
        """Total number of elements created."""
        return sum(g.element_count for g in self.group_results)


def calculate_text_offset(
    font_size_px: float,
    text: str,
    cap_height_ratio: float = DEFAULT_CAP_HEIGHT_RATIO,
    char_width_ratio: float = DEFAULT_CHAR_WIDTH_RATIO,
) -> tuple[float, float]:
    """Calculate offset to center text bounding box at origin.

    SVG text element x,y attributes specify the baseline left position.
    This function calculates the offset needed to center the bounding box.

    Args:
        font_size_px: Font size in pixels.
        text: Text content.
        cap_height_ratio: Cap height as ratio of font size (default: 0.72).
        char_width_ratio: Character width as ratio of font size (default: 0.55).

    Returns:
        Tuple of (offset_x, offset_y) in pixels.
        Add these to grid center to get text x,y attributes.
    """
    # Estimate text width (character count * average width)
    text_width = len(text) * font_size_px * char_width_ratio

    # Estimate cap height (height of capital letters)
    cap_height = font_size_px * cap_height_ratio

    # Offset to center horizontally: move left by half width
    offset_x = -text_width / 2

    # Offset to center vertically: baseline is at bottom of cap height
    # To center, we need to move baseline down by half cap height
    offset_y = cap_height / 2

    return (offset_x, offset_y)


def px_to_mm(px: float, dpi: float = 96.0) -> float:
    """Convert pixels to millimeters.

    Args:
        px: Value in pixels.
        dpi: Dots per inch (default: 96 for SVG).

    Returns:
        Value in millimeters.
    """
    return px * 25.4 / dpi


def mm_to_px(mm: float, dpi: float = 96.0) -> float:
    """Convert millimeters to pixels.

    Args:
        mm: Value in millimeters.
        dpi: Dots per inch (default: 96 for SVG).

    Returns:
        Value in pixels.
    """
    return mm * dpi / 25.4


def create_text_element(
    grid_x_mm: float,
    grid_y_mm: float,
    text: str,
    font: FontConfig,
    element_id: str,
) -> tuple[ET.Element, TextElementInfo]:
    """Create a text element centered at grid position.

    Coordinates are output in mm units to match typical Inkscape SVG files
    where viewBox uses mm-based user units.

    Args:
        grid_x_mm: Grid center X coordinate in mm.
        grid_y_mm: Grid center Y coordinate in mm.
        text: Text content.
        font: Font configuration.
        element_id: ID for the element.

    Returns:
        Tuple of (ET.Element, TextElementInfo).
    """
    # Calculate offset in pixels (font size is in px)
    offset_x_px, offset_y_px = calculate_text_offset(font.size, text)

    # Convert offset from px to mm (SVG uses mm user units)
    offset_x_mm = px_to_mm(offset_x_px)
    offset_y_mm = px_to_mm(offset_y_px)

    # Calculate final text position in mm
    text_x_mm = grid_x_mm + offset_x_mm
    text_y_mm = grid_y_mm + offset_y_mm

    # Create text element
    svg_ns = SVG_NAMESPACES["svg"]
    elem = ET.Element(f"{{{svg_ns}}}text")
    elem.set("id", element_id)
    elem.set("x", f"{text_x_mm:.6f}")
    elem.set("y", f"{text_y_mm:.6f}")
    elem.set(
        "style",
        f"font-family:{font.family};font-size:{font.size}px;fill:{font.color}",
    )
    elem.text = text

    # Create info
    info = TextElementInfo(
        element_id=element_id,
        text=text,
        grid_x=grid_x_mm,
        grid_y=grid_y_mm,
        text_x=text_x_mm,
        text_y=text_y_mm,
    )

    return elem, info


def generate_grid_positions(
    x_start: float, x_end: float, x_interval: float
) -> list[float]:
    """Generate grid positions from start to end with interval.

    Args:
        x_start: Start X coordinate (mm).
        x_end: End X coordinate (mm).
        x_interval: X interval (mm).

    Returns:
        List of X positions.
    """
    if x_interval <= 0:
        return [x_start]

    positions = []
    x = x_start
    # Use a small tolerance for floating point comparison
    tolerance = x_interval * 0.001
    while x <= x_end + tolerance:
        positions.append(x)
        x += x_interval

    return positions


def generate_text_label(
    index: int,
    fmt: TextFormatConfig,
) -> str:
    """Generate text label for a given index.

    Args:
        index: 1-based index.
        fmt: Format configuration.

    Returns:
        Formatted label string.
    """
    return format_index(
        index,
        fmt.type,
        fmt.padding,
        fmt.custom if fmt.custom else None,
    )


def create_text_group(
    rule: TextLineRule,
    id_prefix: str = "text",
) -> tuple[ET.Element, GroupAddResult]:
    """Create a group with text elements according to rule.

    Args:
        rule: Text line rule.
        id_prefix: Prefix for element IDs.

    Returns:
        Tuple of (group_element, GroupAddResult).
    """
    svg_ns = SVG_NAMESPACES["svg"]
    inkscape_ns = SVG_NAMESPACES["inkscape"]

    # Create group element
    group = ET.Element(f"{{{svg_ns}}}g")
    group.set("id", rule.name)
    group.set(f"{{{inkscape_ns}}}label", rule.name)

    # Initialize result
    result = GroupAddResult(
        group_name=rule.name,
        y=rule.y,
        x_start=rule.x_start,
        x_end=rule.x_end,
        x_interval=rule.x_interval,
    )

    # Generate grid positions
    positions = generate_grid_positions(rule.x_start, rule.x_end, rule.x_interval)

    # Create text elements
    for i, x_pos in enumerate(positions):
        index = rule.format.start + i

        try:
            label = generate_text_label(index, rule.format)
        except ValueError as e:
            result.errors.append(f"Failed to generate label at index {index}: {e}")
            continue

        element_id = f"{id_prefix}-{i + 1}"

        elem, info = create_text_element(
            grid_x_mm=x_pos,
            grid_y_mm=rule.y,
            text=label,
            font=rule.font,
            element_id=element_id,
        )

        group.append(elem)
        result.elements.append(info)

    return group, result


def parse_add_text_rule_file(rule_path: Path) -> AddTextRule:
    """Parse a YAML add-text rule file.

    Args:
        rule_path: Path to the YAML rule file.

    Returns:
        Parsed AddTextRule.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the rule format is invalid.
    """
    with open(rule_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Rule file must be a YAML dictionary")

    groups: list[TextLineRule] = []
    for group_data in data.get("groups", []):
        # Required fields
        if "name" not in group_data:
            raise ValueError("Each group must have 'name' field")
        if "y" not in group_data:
            raise ValueError("Each group must have 'y' field")
        if "x_start" not in group_data:
            raise ValueError("Each group must have 'x_start' field")
        if "x_end" not in group_data:
            raise ValueError("Each group must have 'x_end' field")
        if "x_interval" not in group_data:
            raise ValueError("Each group must have 'x_interval' field")

        # Font (optional)
        font = FontConfig()
        if "font" in group_data:
            font_data = group_data["font"]
            if "family" in font_data:
                font.family = str(font_data["family"])
            if "size" in font_data:
                font.size = float(font_data["size"])
            if "color" in font_data:
                font.color = str(font_data["color"])

        # Format (optional)
        fmt = TextFormatConfig()
        if "format" in group_data:
            fmt_data = group_data["format"]
            if "type" in fmt_data:
                fmt_type = fmt_data["type"]
                if fmt_type not in ("number", "letter", "letter_upper", "custom"):
                    raise ValueError(f"Invalid format.type value: {fmt_type}")
                fmt.type = fmt_type
            if "padding" in fmt_data:
                fmt.padding = int(fmt_data["padding"])
            if "start" in fmt_data:
                fmt.start = int(fmt_data["start"])
            if "custom" in fmt_data:
                custom = fmt_data["custom"]
                if not isinstance(custom, list):
                    raise ValueError("format.custom must be a list")
                fmt.custom = [str(item) for item in custom]

            # Validate custom type requires custom labels
            if fmt.type == "custom" and not fmt.custom:
                raise ValueError("format.custom is required when type is 'custom'")

        groups.append(
            TextLineRule(
                name=group_data["name"],
                y=float(group_data["y"]),
                x_start=float(group_data["x_start"]),
                x_end=float(group_data["x_end"]),
                x_interval=float(group_data["x_interval"]),
                font=font,
                format=fmt,
            )
        )

    return AddTextRule(groups=groups)


def add_text_to_svg(
    svg_path: Path,
    rule: AddTextRule,
    apply: bool = False,
) -> tuple[ET.ElementTree, AddTextReport]:
    """Add text elements to an SVG file.

    Args:
        svg_path: Path to SVG file.
        rule: Add text rules.
        apply: Whether to apply changes to the SVG.

    Returns:
        Tuple of (ElementTree, AddTextReport).
    """
    register_namespaces()
    tree = ET.parse(svg_path)
    root = tree.getroot()

    report = AddTextReport(file_path=svg_path)

    for i, group_rule in enumerate(rule.groups):
        # Use group name as ID prefix
        id_prefix = f"{group_rule.name}-text"

        group_elem, group_result = create_text_group(group_rule, id_prefix)
        report.group_results.append(group_result)

        if apply and not group_result.has_errors:
            root.append(group_elem)

    return tree, report


def format_add_text_report(report: AddTextReport) -> str:
    """Format add-text report as text.

    Args:
        report: Add text report.

    Returns:
        Formatted text.
    """
    lines: list[str] = []
    lines.append(f"File: {report.file_path}")
    lines.append("")

    for group_result in report.group_results:
        lines.append(f"Group: {group_result.group_name}")
        lines.append(f"  Y: {group_result.y:.2f} mm")
        lines.append(
            f"  X range: {group_result.x_start:.2f} - {group_result.x_end:.2f} mm"
        )
        lines.append(f"  X interval: {group_result.x_interval:.2f} mm")
        lines.append(f"  Elements: {group_result.element_count}")
        lines.append("")

        # Warnings
        for warning in group_result.warnings:
            lines.append(f"  [WARNING] {warning}")

        # Errors
        for error in group_result.errors:
            lines.append(f"  [ERROR] {error}")

        if group_result.warnings or group_result.errors:
            lines.append("")

        # Element list
        if group_result.elements:
            lines.append("  Created elements:")
            for elem in group_result.elements:
                lines.append(
                    f'    {elem.element_id}: "{elem.text}" at '
                    f"({elem.grid_x:.2f}, {elem.grid_y:.2f}) mm"
                )
            lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append(f"  Total groups: {len(report.group_results)}")
    lines.append(f"  Total elements: {report.total_elements}")

    if report.has_errors:
        lines.append("")
        lines.append("*** ERRORS DETECTED - Output file will not be generated ***")

    return "\n".join(lines)
