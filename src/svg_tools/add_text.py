"""SVG text element auto-generation module."""

import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

# Layout direction type
LayoutDirection = Literal["horizontal", "vertical"]

# Alignment type for text positioning
AlignType = Literal["bbox_center", "baseline_center"]
from xml.etree import ElementTree as ET

import freetype
import yaml

from .relabel import format_index, FormatType
from .utils import register_namespaces, SVG_NAMESPACES


# Measurement size for accurate font metrics (larger = more accurate)
MEASURE_FONT_SIZE_PT = 100


@dataclass
class FontConfig:
    """Font configuration for text elements."""

    family: str = "Noto Sans CJK JP"
    size: float = 1.0  # mm (not px!)
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
    """Rule for a single line of text elements.

    Supports two layout modes:
    - Horizontal: y fixed, x varies (x_start, x_end, x_interval)
    - Vertical: x fixed, y varies (y_start, y_end, y_interval)

    The layout mode is determined automatically based on which fields are set.
    """

    name: str  # Group name to create
    font: FontConfig = field(default_factory=FontConfig)
    format: TextFormatConfig = field(default_factory=TextFormatConfig)
    align: AlignType = "bbox_center"  # Text alignment mode

    # Horizontal layout (y fixed, x varies)
    y: float | None = None  # Fixed Y coordinate (mm)
    x_start: float | None = None  # Start X coordinate (mm)
    x_end: float | None = None  # End X coordinate (mm)
    x_interval: float | None = None  # X interval (mm)

    # Vertical layout (x fixed, y varies)
    x: float | None = None  # Fixed X coordinate (mm)
    y_start: float | None = None  # Start Y coordinate (mm)
    y_end: float | None = None  # End Y coordinate (mm)
    y_interval: float | None = None  # Y interval (mm)

    @property
    def is_vertical(self) -> bool:
        """Check if this is a vertical layout (x fixed, y varies)."""
        return self.x is not None and self.y_start is not None

    @property
    def is_horizontal(self) -> bool:
        """Check if this is a horizontal layout (y fixed, x varies)."""
        return self.y is not None and self.x_start is not None

    @property
    def fixed_coord(self) -> float:
        """Get the fixed coordinate value."""
        if self.is_vertical:
            return self.x  # type: ignore
        return self.y  # type: ignore

    @property
    def start_coord(self) -> float:
        """Get the start coordinate of the varying axis."""
        if self.is_vertical:
            return self.y_start  # type: ignore
        return self.x_start  # type: ignore

    @property
    def end_coord(self) -> float:
        """Get the end coordinate of the varying axis."""
        if self.is_vertical:
            return self.y_end  # type: ignore
        return self.x_end  # type: ignore

    @property
    def interval(self) -> float:
        """Get the interval of the varying axis."""
        if self.is_vertical:
            return self.y_interval  # type: ignore
        return self.x_interval  # type: ignore


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
    """Result of adding text elements to a group.

    Uses axis-agnostic naming for coordinates:
    - fixed_axis: "x" or "y" - the axis with a fixed coordinate
    - fixed_value: the coordinate value on the fixed axis
    - start/end/interval: range on the varying axis
    """

    group_name: str
    fixed_axis: Literal["x", "y"]  # "x" for vertical, "y" for horizontal
    fixed_value: float  # Value on the fixed axis (mm)
    start: float  # Start coordinate on varying axis (mm)
    end: float  # End coordinate on varying axis (mm)
    interval: float  # Interval on varying axis (mm)
    elements: list[TextElementInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_vertical(self) -> bool:
        """Check if this is a vertical layout (x fixed)."""
        return self.fixed_axis == "x"

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


@dataclass
class TextExtents:
    """Text bounding box extents."""

    x_bearing: float  # Left edge offset from origin
    y_bearing: float  # Top edge offset from baseline (negative = above)
    width: float  # Bounding box width
    height: float  # Bounding box height
    x_advance: float  # Advance width for next character


@lru_cache(maxsize=32)
def find_font_file(font_family: str) -> str | None:
    """Find font file path using fc-match.

    Args:
        font_family: Font family name.

    Returns:
        Path to font file or None if not found.
    """
    try:
        result = subprocess.run(
            ["fc-match", font_family, "-f", "%{file}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


@lru_cache(maxsize=8)
def load_font_face(font_path: str) -> freetype.Face:
    """Load a FreeType font face.

    Args:
        font_path: Path to font file.

    Returns:
        FreeType Face object.
    """
    return freetype.Face(font_path)


def get_text_extents_freetype(
    face: freetype.Face,
    text: str,
    font_size_pt: float,
    dpi: int = 96,
) -> TextExtents:
    """Get text bounding box using FreeType.

    Args:
        face: FreeType face object.
        text: Text to measure.
        font_size_pt: Font size in points.
        dpi: DPI for rendering.

    Returns:
        TextExtents with measurements in font units (relative to font_size_pt).
    """
    # Set font size (in 1/64th of points)
    face.set_char_size(int(font_size_pt * 64), 0, dpi, dpi)

    pen_x = 0
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    for char in text:
        face.load_char(char, freetype.FT_LOAD_RENDER)
        glyph = face.glyph

        left = pen_x + glyph.bitmap_left
        top = glyph.bitmap_top
        width = glyph.bitmap.width
        height = glyph.bitmap.rows

        if width > 0 and height > 0:
            min_x = min(min_x, left)
            max_x = max(max_x, left + width)
            min_y = min(min_y, -top)
            max_y = max(max_y, -top + height)

        pen_x += glyph.advance.x >> 6

    if min_x == float("inf"):
        # Empty or whitespace text
        return TextExtents(0, 0, 0, 0, pen_x)

    return TextExtents(
        x_bearing=min_x,
        y_bearing=min_y,
        width=max_x - min_x,
        height=max_y - min_y,
        x_advance=pen_x,
    )


def calculate_text_offset_freetype(
    font_family: str,
    font_size_mm: float,
    text: str,
    align: AlignType = "bbox_center",
) -> tuple[float, float]:
    """Calculate offset to position text using FreeType.

    Args:
        font_family: Font family name.
        font_size_mm: Font size in mm.
        text: Text content.
        align: Alignment mode - "bbox_center" or "baseline_center".

    Returns:
        Tuple of (offset_x, offset_y) in mm.
        Add these to grid center to get text x,y attributes.
    """
    font_path = find_font_file(font_family)
    if font_path is None:
        # Fallback to estimation if font not found
        return calculate_text_offset_estimated(font_size_mm, text, align)

    try:
        face = load_font_face(font_path)
    except Exception:
        return calculate_text_offset_estimated(font_size_mm, text, align)

    # Measure at large size for accuracy
    extents = get_text_extents_freetype(face, text, MEASURE_FONT_SIZE_PT)

    # Scale from measurement size to target size
    # MEASURE_FONT_SIZE_PT points at 96 DPI = MEASURE_FONT_SIZE_PT * 96/72 px
    measure_size_px = MEASURE_FONT_SIZE_PT * 96 / 72
    # Convert target font size from mm to px at 96 DPI
    font_size_px = font_size_mm * 96 / 25.4
    scale = font_size_px / measure_size_px

    # Calculate offset for centering
    # Text origin (x,y) is at baseline left
    # X direction: center text width at grid point (common for both modes)
    #   grid_x = text_x + x_bearing + width/2
    #   text_x = grid_x - x_bearing - width/2
    #   offset_x = text_x - grid_x = -(x_bearing + width/2)
    offset_x_px = -(extents.x_bearing + extents.width / 2) * scale

    # Y direction: depends on alignment mode
    if align == "baseline_center":
        # Place baseline at grid Y coordinate
        offset_y_px = 0
    else:  # bbox_center
        # Center bbox vertically at grid point
        offset_y_px = -(extents.y_bearing + extents.height / 2) * scale

    # Convert px to mm
    offset_x_mm = offset_x_px * 25.4 / 96
    offset_y_mm = offset_y_px * 25.4 / 96

    return (offset_x_mm, offset_y_mm)


def calculate_text_offset_estimated(
    font_size_mm: float,
    text: str,
    align: AlignType = "bbox_center",
    cap_height_ratio: float = 0.75,
    char_width_ratio: float = 0.50,
) -> tuple[float, float]:
    """Calculate offset using estimated font metrics (fallback).

    Args:
        font_size_mm: Font size in mm.
        text: Text content.
        align: Alignment mode - "bbox_center" or "baseline_center".
        cap_height_ratio: Cap height as ratio of font size.
        char_width_ratio: Character width as ratio of font size.

    Returns:
        Tuple of (offset_x, offset_y) in mm.
    """
    text_width = len(text) * font_size_mm * char_width_ratio
    cap_height = font_size_mm * cap_height_ratio

    offset_x = -text_width / 2

    if align == "baseline_center":
        # Place baseline at grid Y coordinate
        offset_y = 0
    else:  # bbox_center
        # Center cap height vertically at grid point
        offset_y = cap_height / 2

    return (offset_x, offset_y)


def create_text_element(
    grid_x_mm: float,
    grid_y_mm: float,
    text: str,
    font: FontConfig,
    element_id: str,
    align: AlignType = "bbox_center",
) -> tuple[ET.Element, TextElementInfo]:
    """Create a text element positioned at grid position.

    All coordinates and font size are in mm units.

    Args:
        grid_x_mm: Grid center X coordinate in mm.
        grid_y_mm: Grid center Y coordinate in mm.
        text: Text content.
        font: Font configuration (size in mm).
        element_id: ID for the element.
        align: Alignment mode - "bbox_center" or "baseline_center".

    Returns:
        Tuple of (ET.Element, TextElementInfo).
    """
    # Calculate offset using FreeType
    offset_x_mm, offset_y_mm = calculate_text_offset_freetype(
        font.family, font.size, text, align
    )

    # Calculate final text position in mm
    text_x_mm = grid_x_mm + offset_x_mm
    text_y_mm = grid_y_mm + offset_y_mm

    # Create text element
    svg_ns = SVG_NAMESPACES["svg"]
    elem = ET.Element(f"{{{svg_ns}}}text")
    elem.set("id", element_id)
    elem.set("x", f"{text_x_mm:.6f}")
    elem.set("y", f"{text_y_mm:.6f}")
    # In SVG with mm-based viewBox (e.g., "0 0 210 297" with width="210mm"),
    # 1 viewBox unit = 1 mm. Font-size is specified in viewBox units (unitless)
    # so font.size (in mm) directly gives the correct size.
    elem.set(
        "style",
        f"font-family:{font.family};font-size:{font.size};fill:{font.color}",
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
    indent: str = "  ",
    base_indent: int = 0,
) -> tuple[ET.Element, GroupAddResult]:
    """Create a group with text elements according to rule.

    Supports both horizontal (y fixed, x varies) and vertical (x fixed, y varies)
    layouts.

    Args:
        rule: Text line rule.
        id_prefix: Prefix for element IDs.
        indent: Indentation string (default: 2 spaces).
        base_indent: Base indentation level for the group.

    Returns:
        Tuple of (group_element, GroupAddResult).
    """
    svg_ns = SVG_NAMESPACES["svg"]
    inkscape_ns = SVG_NAMESPACES["inkscape"]

    # Create group element
    group = ET.Element(f"{{{svg_ns}}}g")
    group.set("id", rule.name)
    group.set(f"{{{inkscape_ns}}}label", rule.name)

    # Initialize result with axis-agnostic structure
    result = GroupAddResult(
        group_name=rule.name,
        fixed_axis="x" if rule.is_vertical else "y",
        fixed_value=rule.fixed_coord,
        start=rule.start_coord,
        end=rule.end_coord,
        interval=rule.interval,
    )

    # Generate grid positions on the varying axis
    positions = generate_grid_positions(rule.start_coord, rule.end_coord, rule.interval)

    # Indentation for child elements
    child_indent = indent * (base_indent + 1)
    group_indent = indent * base_indent

    # Create text elements
    elements_created = []
    for i, pos in enumerate(positions):
        index = rule.format.start + i

        try:
            label = generate_text_label(index, rule.format)
        except ValueError as e:
            result.errors.append(f"Failed to generate label at index {index}: {e}")
            continue

        element_id = f"{id_prefix}-{i + 1}"

        # Determine coordinates based on layout direction
        if rule.is_vertical:
            grid_x = rule.fixed_coord  # x is fixed
            grid_y = pos  # y varies
        else:
            grid_x = pos  # x varies
            grid_y = rule.fixed_coord  # y is fixed

        elem, info = create_text_element(
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            text=label,
            font=rule.font,
            element_id=element_id,
            align=rule.align,
        )

        elements_created.append(elem)
        result.elements.append(info)

    # Add elements with proper formatting
    if elements_created:
        group.text = "\n" + child_indent
        for i, elem in enumerate(elements_created):
            group.append(elem)
            if i < len(elements_created) - 1:
                elem.tail = "\n" + child_indent
            else:
                elem.tail = "\n" + group_indent
        group.tail = "\n"

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
        # Required field: name
        if "name" not in group_data:
            raise ValueError("Each group must have 'name' field")

        # Determine layout direction based on present fields
        has_horizontal = "y" in group_data and "x_start" in group_data
        has_vertical = "x" in group_data and "y_start" in group_data

        if has_horizontal and has_vertical:
            raise ValueError(
                f"Group '{group_data['name']}': Cannot specify both horizontal "
                "(y, x_start, x_end, x_interval) and vertical "
                "(x, y_start, y_end, y_interval) layout fields"
            )

        if not has_horizontal and not has_vertical:
            raise ValueError(
                f"Group '{group_data['name']}': Must specify either horizontal "
                "(y, x_start, x_end, x_interval) or vertical "
                "(x, y_start, y_end, y_interval) layout fields"
            )

        # Validate required fields for the chosen layout
        if has_horizontal:
            for field in ["y", "x_start", "x_end", "x_interval"]:
                if field not in group_data:
                    raise ValueError(
                        f"Group '{group_data['name']}': Horizontal layout requires "
                        f"'{field}' field"
                    )
        else:  # has_vertical
            for field in ["x", "y_start", "y_end", "y_interval"]:
                if field not in group_data:
                    raise ValueError(
                        f"Group '{group_data['name']}': Vertical layout requires "
                        f"'{field}' field"
                    )

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

        # Align (optional)
        align: AlignType = "bbox_center"
        if "align" in group_data:
            align_val = group_data["align"]
            if align_val not in ("bbox_center", "baseline_center"):
                raise ValueError(
                    f"Group '{group_data['name']}': Invalid align value: {align_val}. "
                    "Must be 'bbox_center' or 'baseline_center'"
                )
            align = align_val

        # Build TextLineRule with appropriate fields
        if has_horizontal:
            groups.append(
                TextLineRule(
                    name=group_data["name"],
                    font=font,
                    format=fmt,
                    align=align,
                    y=float(group_data["y"]),
                    x_start=float(group_data["x_start"]),
                    x_end=float(group_data["x_end"]),
                    x_interval=float(group_data["x_interval"]),
                )
            )
        else:  # has_vertical
            groups.append(
                TextLineRule(
                    name=group_data["name"],
                    font=font,
                    format=fmt,
                    align=align,
                    x=float(group_data["x"]),
                    y_start=float(group_data["y_start"]),
                    y_end=float(group_data["y_end"]),
                    y_interval=float(group_data["y_interval"]),
                )
            )

    return AddTextRule(groups=groups)


def add_text_to_svg_tree(
    tree: ET.ElementTree,
    rule: AddTextRule,
    apply: bool = False,
) -> AddTextReport:
    """Add text elements to an existing ElementTree.

    Args:
        tree: ElementTree to process (modified in-place if apply=True).
        rule: Add text rules.
        apply: Whether to apply changes to the SVG.

    Returns:
        AddTextReport with results.

    Note:
        The file_path in the returned report will be empty Path("").
        Callers should set it if needed.
    """
    root = tree.getroot()
    report = AddTextReport(file_path=Path(""))

    for i, group_rule in enumerate(rule.groups):
        # Use group name as ID prefix
        id_prefix = f"{group_rule.name}-text"

        # base_indent=0 for root-level groups, child elements get indent level 1
        group_elem, group_result = create_text_group(
            group_rule, id_prefix, indent="  ", base_indent=0
        )
        report.group_results.append(group_result)

        if apply and not group_result.has_errors:
            root.append(group_elem)

    return report


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
    report = add_text_to_svg_tree(tree, rule, apply)
    report.file_path = svg_path
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

        # Display layout info based on direction
        if group_result.is_vertical:
            # Vertical layout: x fixed, y varies
            lines.append(f"  Layout: vertical (X fixed)")
            lines.append(f"  X: {group_result.fixed_value:.2f} mm")
            lines.append(
                f"  Y range: {group_result.start:.2f} - {group_result.end:.2f} mm"
            )
            lines.append(f"  Y interval: {group_result.interval:.2f} mm")
        else:
            # Horizontal layout: y fixed, x varies
            lines.append(f"  Layout: horizontal (Y fixed)")
            lines.append(f"  Y: {group_result.fixed_value:.2f} mm")
            lines.append(
                f"  X range: {group_result.start:.2f} - {group_result.end:.2f} mm"
            )
            lines.append(f"  X interval: {group_result.interval:.2f} mm")

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
