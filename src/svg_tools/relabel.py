"""SVG shape relabeling module."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal
from xml.etree import ElementTree as ET

import yaml

from .geometry import (
    ShapeInfo,
    ShapeType,
    parse_arc,
    parse_rect,
)
from .utils import (
    find_group_by_label,
    get_element_label,
    register_namespaces,
    set_element_label,
)


# Format types
FormatType = Literal["number", "letter", "letter_upper", "custom"]

# Sort types
SortBy = Literal["none", "x_then_y", "y_then_x"]
SortOrder = Literal["ascending", "descending"]


@dataclass
class GridConfig:
    """Grid configuration."""

    x: float
    y: float


@dataclass
class OriginConfig:
    """Origin configuration."""

    x: float
    y: float


@dataclass
class AxisConfig:
    """Axis direction configuration."""

    x_direction: Literal["positive", "negative"] = "positive"
    y_direction: Literal["positive", "negative"] = "positive"


@dataclass
class IndexConfig:
    """Index start configuration."""

    x_start: int = 1
    y_start: int = 1


@dataclass
class FormatConfig:
    """Label format configuration."""

    x_type: FormatType = "number"
    y_type: FormatType = "letter"
    x_padding: int = 0
    y_padding: int = 0
    custom_x: list[str] | None = None
    custom_y: list[str] | None = None


@dataclass
class SortConfig:
    """Sort configuration for elements within a group."""

    by: SortBy = "none"
    x_order: SortOrder = "ascending"
    y_order: SortOrder = "ascending"


@dataclass
class RelabelGroupRule:
    """Relabeling rules for a group."""

    name: str
    shape: ShapeType
    label_template: str
    grid: GridConfig
    origin: OriginConfig | None = None
    axis: AxisConfig = field(default_factory=AxisConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    format: FormatConfig = field(default_factory=FormatConfig)
    sort: SortConfig = field(default_factory=SortConfig)


@dataclass
class RelabelRule:
    """Complete relabel rule configuration."""

    groups: list[RelabelGroupRule] = field(default_factory=list)


@dataclass
class LabelChange:
    """Record of a label change."""

    element_id: str
    old_label: str | None
    new_label: str
    center_x: float
    center_y: float
    grid_x: int
    grid_y: int


@dataclass
class GroupRelabelResult:
    """Result of relabeling a group."""

    group_name: str
    shape_type: ShapeType
    origin: tuple[float, float]
    grid: tuple[float, float]
    sort: SortConfig | None = None
    changes: list[LabelChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed_count(self) -> int:
        """Count of elements with changed labels."""
        return sum(1 for c in self.changes if c.old_label != c.new_label)

    @property
    def unchanged_count(self) -> int:
        """Count of elements with unchanged labels."""
        return sum(1 for c in self.changes if c.old_label == c.new_label)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0


@dataclass
class RelabelReport:
    """Complete relabeling report."""

    file_path: Path
    group_results: list[GroupRelabelResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any groups have errors."""
        return any(g.has_errors for g in self.group_results)

    @property
    def total_elements(self) -> int:
        """Total number of elements processed."""
        return sum(len(g.changes) for g in self.group_results)

    @property
    def total_changed(self) -> int:
        """Total number of elements with changed labels."""
        return sum(g.changed_count for g in self.group_results)


def to_letter(n: int, upper: bool = False) -> str:
    """Convert 1-based index to letter representation.

    Args:
        n: 1-based index (1='a', 26='z', 27='aa', etc.)
        upper: If True, return uppercase letters.

    Returns:
        Letter representation.

    Examples:
        >>> to_letter(1)
        'a'
        >>> to_letter(26)
        'z'
        >>> to_letter(27)
        'aa'
        >>> to_letter(1, upper=True)
        'A'
    """
    if n < 1:
        raise ValueError(f"Index must be >= 1, got {n}")

    result = []
    while n > 0:
        n -= 1
        result.append(chr(ord("a") + (n % 26)))
        n //= 26
    text = "".join(reversed(result))
    return text.upper() if upper else text


def format_index(
    index: int,
    format_type: FormatType,
    padding: int = 0,
    custom_labels: list[str] | None = None,
) -> str:
    """Format an index according to the format type.

    Args:
        index: The index value (1-based).
        format_type: Format type ('number', 'letter', 'letter_upper', 'custom').
        padding: Zero-padding width for numbers.
        custom_labels: Custom label list for 'custom' format type.

    Returns:
        Formatted string.

    Raises:
        ValueError: If format_type is 'custom' but custom_labels is not provided,
                   or if index exceeds the custom_labels length.
    """
    if format_type == "number":
        if padding > 0:
            return str(index).zfill(padding)
        return str(index)
    elif format_type == "letter":
        return to_letter(index, upper=False)
    elif format_type == "letter_upper":
        return to_letter(index, upper=True)
    elif format_type == "custom":
        if custom_labels is None:
            raise ValueError("custom_labels required for 'custom' format type")
        if index < 1 or index > len(custom_labels):
            raise ValueError(
                f"Index {index} out of range for custom labels "
                f"(valid: 1-{len(custom_labels)})"
            )
        label = custom_labels[index - 1]
        if label == "_":
            raise ValueError(
                f"Index {index} maps to reserved skip marker '_' in custom labels"
            )
        return label
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def parse_relabel_rule_file(rule_path: Path) -> RelabelRule:
    """Parse a YAML relabel rule file.

    Args:
        rule_path: Path to the YAML rule file.

    Returns:
        Parsed RelabelRule.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the rule format is invalid.
    """
    with open(rule_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Rule file must be a YAML dictionary")

    groups: list[RelabelGroupRule] = []
    for group_data in data.get("groups", []):
        # Required fields
        if "name" not in group_data:
            raise ValueError("Each group must have 'name' field")
        if "shape" not in group_data:
            raise ValueError("Each group must have 'shape' field")
        if "label_template" not in group_data:
            raise ValueError("Each group must have 'label_template' field")
        if "grid" not in group_data:
            raise ValueError("Each group must have 'grid' field")

        shape = group_data["shape"]
        if shape not in ("rect", "arc"):
            raise ValueError(f"Unsupported shape type: {shape}")

        # Grid (required)
        grid_data = group_data["grid"]
        grid = GridConfig(x=float(grid_data["x"]), y=float(grid_data["y"]))

        # Origin (optional)
        origin = None
        if "origin" in group_data:
            origin_data = group_data["origin"]
            origin = OriginConfig(
                x=float(origin_data["x"]), y=float(origin_data["y"])
            )

        # Axis (optional)
        axis = AxisConfig()
        if "axis" in group_data:
            axis_data = group_data["axis"]
            if "x_direction" in axis_data:
                axis.x_direction = axis_data["x_direction"]
            if "y_direction" in axis_data:
                axis.y_direction = axis_data["y_direction"]

        # Index (optional)
        index = IndexConfig()
        if "index" in group_data:
            index_data = group_data["index"]
            if "x_start" in index_data:
                index.x_start = int(index_data["x_start"])
            if "y_start" in index_data:
                index.y_start = int(index_data["y_start"])

        # Format (optional)
        fmt = FormatConfig()
        if "format" in group_data:
            fmt_data = group_data["format"]
            if "x_type" in fmt_data:
                x_type = fmt_data["x_type"]
                if x_type not in ("number", "letter", "letter_upper", "custom"):
                    raise ValueError(f"Invalid format.x_type value: {x_type}")
                fmt.x_type = x_type
            if "y_type" in fmt_data:
                y_type = fmt_data["y_type"]
                if y_type not in ("number", "letter", "letter_upper", "custom"):
                    raise ValueError(f"Invalid format.y_type value: {y_type}")
                fmt.y_type = y_type
            if "x_padding" in fmt_data:
                fmt.x_padding = int(fmt_data["x_padding"])
            if "y_padding" in fmt_data:
                fmt.y_padding = int(fmt_data["y_padding"])
            if "custom_x" in fmt_data:
                custom_x = fmt_data["custom_x"]
                if not isinstance(custom_x, list):
                    raise ValueError("format.custom_x must be a list")
                fmt.custom_x = [str(item) for item in custom_x]
            if "custom_y" in fmt_data:
                custom_y = fmt_data["custom_y"]
                if not isinstance(custom_y, list):
                    raise ValueError("format.custom_y must be a list")
                fmt.custom_y = [str(item) for item in custom_y]

            # Validate custom type requires custom labels
            if fmt.x_type == "custom" and fmt.custom_x is None:
                raise ValueError(
                    "format.custom_x is required when x_type is 'custom'"
                )
            if fmt.y_type == "custom" and fmt.custom_y is None:
                raise ValueError(
                    "format.custom_y is required when y_type is 'custom'"
                )

        # Sort (optional)
        sort = SortConfig()
        if "sort" in group_data:
            sort_data = group_data["sort"]
            if "by" in sort_data:
                sort_by = sort_data["by"]
                if sort_by not in ("none", "x_then_y", "y_then_x"):
                    raise ValueError(f"Invalid sort.by value: {sort_by}")
                sort.by = sort_by
            if "x_order" in sort_data:
                x_order = sort_data["x_order"]
                if x_order not in ("ascending", "descending"):
                    raise ValueError(f"Invalid sort.x_order value: {x_order}")
                sort.x_order = x_order
            if "y_order" in sort_data:
                y_order = sort_data["y_order"]
                if y_order not in ("ascending", "descending"):
                    raise ValueError(f"Invalid sort.y_order value: {y_order}")
                sort.y_order = y_order

        groups.append(
            RelabelGroupRule(
                name=group_data["name"],
                shape=shape,
                label_template=group_data["label_template"],
                grid=grid,
                origin=origin,
                axis=axis,
                index=index,
                format=fmt,
                sort=sort,
            )
        )

    return RelabelRule(groups=groups)


def iter_shapes_in_group(
    group: ET.Element, shape_type: ShapeType
) -> Iterator[ShapeInfo]:
    """Iterate over shapes of a specific type in a group.

    Args:
        group: Group element to search.
        shape_type: Type of shapes to find.

    Yields:
        ShapeInfo for each matching shape.
    """
    for elem in group.iter():
        if shape_type == "rect":
            info = parse_rect(elem)
        elif shape_type == "arc":
            info = parse_arc(elem)
        else:
            continue

        if info is not None:
            yield info


def calculate_auto_origin(shapes: list[ShapeInfo]) -> tuple[float, float]:
    """Calculate automatic origin from shape positions.

    Uses the minimum center coordinates as origin.

    Args:
        shapes: List of shapes.

    Returns:
        Tuple of (origin_x, origin_y).
    """
    if not shapes:
        return (0.0, 0.0)

    min_x = min(s.center[0] for s in shapes)
    min_y = min(s.center[1] for s in shapes)
    return (min_x, min_y)


def calculate_grid_index(
    center: tuple[float, float],
    origin: tuple[float, float],
    grid: GridConfig,
    axis: AxisConfig,
    index: IndexConfig,
) -> tuple[int, int]:
    """Calculate grid indices for a shape.

    Args:
        center: Shape center coordinates (x, y).
        origin: Origin coordinates (x, y).
        grid: Grid configuration.
        axis: Axis direction configuration.
        index: Index start configuration.

    Returns:
        Tuple of (index_x, index_y).
    """
    # Calculate grid position
    grid_x = round((center[0] - origin[0]) / grid.x)
    grid_y = round((center[1] - origin[1]) / grid.y)

    # Apply axis direction
    if axis.x_direction == "negative":
        grid_x = -grid_x
    if axis.y_direction == "negative":
        grid_y = -grid_y

    # Add start index
    index_x = grid_x + index.x_start
    index_y = grid_y + index.y_start

    return (index_x, index_y)


def generate_label(
    template: str,
    index_x: int,
    index_y: int,
    center_x: float,
    center_y: float,
    fmt: FormatConfig,
) -> str:
    """Generate a label from template and indices.

    Args:
        template: Label template string.
        index_x: X index value.
        index_y: Y index value.
        center_x: Center X coordinate.
        center_y: Center Y coordinate.
        fmt: Format configuration.

    Returns:
        Generated label string.

    Raises:
        ValueError: If custom format type is used but index exceeds custom_labels.
    """
    x_formatted = format_index(index_x, fmt.x_type, fmt.x_padding, fmt.custom_x)
    y_formatted = format_index(index_y, fmt.y_type, fmt.y_padding, fmt.custom_y)

    return template.format(
        x=x_formatted,
        y=y_formatted,
        x_raw=index_x,
        y_raw=index_y,
        cx=f"{center_x:.2f}",
        cy=f"{center_y:.2f}",
    )


def sort_shapes(
    shapes: list[ShapeInfo],
    sort_config: SortConfig,
) -> list[ShapeInfo]:
    """Sort shapes according to sort configuration.

    Args:
        shapes: List of shapes to sort.
        sort_config: Sort configuration.

    Returns:
        Sorted list of shapes.
    """
    if sort_config.by == "none":
        return shapes

    x_reverse = sort_config.x_order == "descending"
    y_reverse = sort_config.y_order == "descending"

    if sort_config.by == "x_then_y":
        # Sort by X first, then by Y for same X values
        return sorted(
            shapes,
            key=lambda s: (
                s.center[0] if not x_reverse else -s.center[0],
                s.center[1] if not y_reverse else -s.center[1],
            ),
        )
    elif sort_config.by == "y_then_x":
        # Sort by Y first, then by X for same Y values
        return sorted(
            shapes,
            key=lambda s: (
                s.center[1] if not y_reverse else -s.center[1],
                s.center[0] if not x_reverse else -s.center[0],
            ),
        )
    else:
        return shapes


def reorder_elements_in_group(
    group: ET.Element,
    shapes: list[ShapeInfo],
) -> None:
    """Reorder elements within a group according to shapes order.

    Args:
        group: Group element containing the shapes.
        shapes: Shapes in the desired order.
    """
    # Build a map of element id to element
    shape_ids = {s.id for s in shapes}
    shape_elements = []
    other_elements = []

    for elem in list(group):
        elem_id = elem.get("id")
        if elem_id in shape_ids:
            shape_elements.append(elem)
            group.remove(elem)
        else:
            other_elements.append(elem)
            group.remove(elem)

    # Re-add other elements first (non-shape elements)
    for elem in other_elements:
        group.append(elem)

    # Create a map from id to element for shape elements
    id_to_elem = {elem.get("id"): elem for elem in shape_elements}

    # Re-add shape elements in sorted order
    for shape in shapes:
        if shape.id in id_to_elem:
            group.append(id_to_elem[shape.id])


def check_grid_deviation(
    center: tuple[float, float],
    origin: tuple[float, float],
    grid: GridConfig,
) -> tuple[float, float]:
    """Check how far a shape is from the nearest grid point.

    Args:
        center: Shape center coordinates.
        origin: Origin coordinates.
        grid: Grid configuration.

    Returns:
        Tuple of (deviation_x, deviation_y) in mm.
    """
    rel_x = center[0] - origin[0]
    rel_y = center[1] - origin[1]

    remainder_x = rel_x % grid.x
    remainder_y = rel_y % grid.y

    dev_x = min(remainder_x, grid.x - remainder_x)
    dev_y = min(remainder_y, grid.y - remainder_y)

    return (dev_x, dev_y)


def relabel_group(
    root: ET.Element,
    rule: RelabelGroupRule,
    apply: bool = False,
) -> GroupRelabelResult:
    """Relabel shapes in a group.

    Args:
        root: Root SVG element.
        rule: Group relabel rule.
        apply: Whether to apply changes to the SVG.

    Returns:
        GroupRelabelResult with changes and any warnings/errors.
    """
    group = find_group_by_label(root, rule.name)

    # Initialize result with default origin
    result = GroupRelabelResult(
        group_name=rule.name,
        shape_type=rule.shape,
        origin=(0.0, 0.0),
        grid=(rule.grid.x, rule.grid.y),
        sort=rule.sort if rule.sort.by != "none" else None,
    )

    if group is None:
        result.warnings.append(f"Group '{rule.name}' not found in SVG")
        return result

    # Collect all shapes
    shapes = list(iter_shapes_in_group(group, rule.shape))

    if not shapes:
        result.warnings.append(f"No {rule.shape} shapes found in group '{rule.name}'")
        return result

    # Sort shapes if configured
    shapes = sort_shapes(shapes, rule.sort)

    if not shapes:
        return result

    # Determine origin
    if rule.origin:
        origin = (rule.origin.x, rule.origin.y)
    else:
        origin = calculate_auto_origin(shapes)

    result.origin = origin

    # Check for off-grid elements and calculate labels
    label_map: dict[str, list[str]] = {}  # label -> [element_ids]
    off_grid_threshold = min(rule.grid.x, rule.grid.y) * 0.5

    for shape in shapes:
        center = shape.center
        old_label = get_element_label(shape.element)

        # Check grid deviation
        dev_x, dev_y = check_grid_deviation(center, origin, rule.grid)
        if dev_x > off_grid_threshold or dev_y > off_grid_threshold:
            result.warnings.append(
                f"Element '{shape.id}' is off-grid by ({dev_x:.3f}, {dev_y:.3f})mm "
                f"(threshold: {off_grid_threshold:.3f}mm)"
            )

        # Calculate indices
        index_x, index_y = calculate_grid_index(
            center, origin, rule.grid, rule.axis, rule.index
        )

        # Generate label
        try:
            new_label = generate_label(
                rule.label_template,
                index_x,
                index_y,
                center[0],
                center[1],
                rule.format,
            )
        except (ValueError, KeyError) as e:
            result.errors.append(
                f"Failed to generate label for '{shape.id}': {e}"
            )
            continue

        # Track for duplicate detection
        if new_label not in label_map:
            label_map[new_label] = []
        label_map[new_label].append(shape.id)

        # Record change
        result.changes.append(
            LabelChange(
                element_id=shape.id,
                old_label=old_label,
                new_label=new_label,
                center_x=center[0],
                center_y=center[1],
                grid_x=index_x,
                grid_y=index_y,
            )
        )

    # Check for duplicates
    for label, element_ids in label_map.items():
        if len(element_ids) > 1:
            result.errors.append(
                f"Duplicate label '{label}' would be assigned to: {', '.join(element_ids)}"
            )

    # Apply changes if no errors and apply is True
    if apply and not result.has_errors:
        for change in result.changes:
            # Find the element and update its label
            for shape in shapes:
                if shape.id == change.element_id:
                    set_element_label(shape.element, change.new_label)
                    break

        # Reorder elements in the group if sorting is enabled
        if rule.sort.by != "none":
            reorder_elements_in_group(group, shapes)

    return result


def relabel_svg(
    svg_path: Path,
    rule: RelabelRule,
    apply: bool = False,
) -> tuple[ET.ElementTree, RelabelReport]:
    """Relabel shapes in an SVG file.

    Args:
        svg_path: Path to SVG file.
        rule: Relabel rules.
        apply: Whether to apply changes to the SVG.

    Returns:
        Tuple of (ElementTree, RelabelReport).
    """
    register_namespaces()
    tree = ET.parse(svg_path)
    root = tree.getroot()

    report = RelabelReport(file_path=svg_path)

    for group_rule in rule.groups:
        group_result = relabel_group(root, group_rule, apply=apply)
        report.group_results.append(group_result)

    return tree, report


def format_relabel_report(report: RelabelReport) -> str:
    """Format relabel report as text.

    Args:
        report: Relabel report.

    Returns:
        Formatted text.
    """
    lines: list[str] = []
    lines.append(f"File: {report.file_path}")
    lines.append("")

    for group_result in report.group_results:
        lines.append(f"Group: {group_result.group_name} ({group_result.shape_type})")
        lines.append(f"  Total elements: {len(group_result.changes)}")
        lines.append(
            f"  Origin: ({group_result.origin[0]:.2f}, {group_result.origin[1]:.2f})"
        )
        lines.append(
            f"  Grid: ({group_result.grid[0]:.2f}, {group_result.grid[1]:.2f})"
        )
        if group_result.sort:
            sort_info = f"  Sort: {group_result.sort.by}"
            if group_result.sort.by != "none":
                sort_info += f" (x:{group_result.sort.x_order}, y:{group_result.sort.y_order})"
            lines.append(sort_info)
        lines.append("")

        # Warnings
        for warning in group_result.warnings:
            lines.append(f"  [WARNING] {warning}")

        # Errors
        for error in group_result.errors:
            lines.append(f"  [ERROR] {error}")

        if group_result.warnings or group_result.errors:
            lines.append("")

        # Label changes
        if group_result.changes:
            lines.append("  Label changes:")
            for change in group_result.changes:
                old = change.old_label if change.old_label else "(none)"
                if change.old_label != change.new_label:
                    lines.append(f'    {change.element_id}: "{old}" -> "{change.new_label}"')
            lines.append("")

        lines.append(f"  Unchanged: {group_result.unchanged_count}")
        lines.append(f"  Changed: {group_result.changed_count}")
        lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append(f"  Total elements: {report.total_elements}")
    lines.append(f"  Total changed: {report.total_changed}")

    if report.has_errors:
        lines.append("")
        lines.append("*** ERRORS DETECTED - Output file will not be generated ***")

    return "\n".join(lines)
