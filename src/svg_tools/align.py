"""SVG shape validation and alignment module."""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal
from xml.etree import ElementTree as ET

import yaml

from .geometry import (
    ArcInfo,
    RectInfo,
    ShapeInfo,
    ShapeType,
    check_grid_alignment,
    check_value_match,
    parse_arc,
    parse_rect,
    snap_to_grid,
    update_arc,
    update_rect,
)
from .utils import SVG_NAMESPACES, get_local_name, register_namespaces

# Default values
DEFAULT_TOLERANCE = 0.001  # mm or rad
DEFAULT_ERROR_THRESHOLD = 0.1  # 10%
DEFAULT_ARC_START = 0.0
DEFAULT_ARC_END = 2 * math.pi  # 6.283185307179586


@dataclass
class GridRule:
    """Grid alignment rule."""

    x: float
    y: float


@dataclass
class SizeRule:
    """Size specification rule."""

    width: float
    height: float


@dataclass
class ArcRule:
    """Arc-specific rule."""

    start: float = DEFAULT_ARC_START
    end: float = DEFAULT_ARC_END


@dataclass
class GroupRule:
    """Validation rules for a group."""

    name: str
    shape: ShapeType
    grid: GridRule | None = None
    size: SizeRule | None = None
    arc: ArcRule | None = None


@dataclass
class ToleranceConfig:
    """Tolerance configuration."""

    acceptable: float = DEFAULT_TOLERANCE
    error_threshold: float = DEFAULT_ERROR_THRESHOLD


@dataclass
class AlignmentRule:
    """Complete alignment rule configuration."""

    groups: list[GroupRule] = field(default_factory=list)
    tolerance: ToleranceConfig = field(default_factory=ToleranceConfig)


IssueStatus = Literal["ok", "fixable", "error"]


@dataclass
class Issue:
    """A single validation issue."""

    element_id: str
    field: str
    status: IssueStatus
    actual: float
    expected: float
    deviation: float
    message: str


@dataclass
class ValidationResult:
    """Validation result for a single element."""

    element_id: str
    shape_type: ShapeType
    issues: list[Issue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any issues are errors."""
        return any(issue.status == "error" for issue in self.issues)

    @property
    def has_fixable(self) -> bool:
        """Check if any issues are fixable."""
        return any(issue.status == "fixable" for issue in self.issues)

    @property
    def is_ok(self) -> bool:
        """Check if all issues are ok."""
        return all(issue.status == "ok" for issue in self.issues)


@dataclass
class GroupValidationResult:
    """Validation result for a group."""

    group_name: str
    shape_type: ShapeType
    element_results: list[ValidationResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any elements have errors."""
        return any(r.has_errors for r in self.element_results)

    @property
    def error_count(self) -> int:
        """Count elements with errors."""
        return sum(1 for r in self.element_results if r.has_errors)

    @property
    def fixable_count(self) -> int:
        """Count elements with fixable issues (but no errors)."""
        return sum(
            1 for r in self.element_results if r.has_fixable and not r.has_errors
        )

    @property
    def ok_count(self) -> int:
        """Count elements that are ok."""
        return sum(1 for r in self.element_results if r.is_ok)


@dataclass
class AlignmentReport:
    """Complete alignment report."""

    file_path: Path
    group_results: list[GroupValidationResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any groups have errors."""
        return any(g.has_errors for g in self.group_results)

    @property
    def total_elements(self) -> int:
        """Total number of elements checked."""
        return sum(len(g.element_results) for g in self.group_results)

    @property
    def total_errors(self) -> int:
        """Total number of elements with errors."""
        return sum(g.error_count for g in self.group_results)

    @property
    def total_fixable(self) -> int:
        """Total number of elements with fixable issues."""
        return sum(g.fixable_count for g in self.group_results)


def parse_rule_file(rule_path: Path) -> AlignmentRule:
    """Parse a YAML rule file.

    Args:
        rule_path: Path to the YAML rule file.

    Returns:
        Parsed AlignmentRule.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the rule format is invalid.
    """
    with open(rule_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Rule file must be a YAML dictionary")

    # Parse tolerance
    tolerance = ToleranceConfig()
    if "tolerance" in data:
        tol_data = data["tolerance"]
        if "acceptable" in tol_data:
            tolerance.acceptable = float(tol_data["acceptable"])
        if "error_threshold" in tol_data:
            tolerance.error_threshold = float(tol_data["error_threshold"])

    # Parse groups
    groups: list[GroupRule] = []
    for group_data in data.get("groups", []):
        if "name" not in group_data or "shape" not in group_data:
            raise ValueError("Each group must have 'name' and 'shape' fields")

        shape = group_data["shape"]
        if shape not in ("rect", "arc"):
            raise ValueError(f"Unsupported shape type: {shape}")

        grid = None
        if "grid" in group_data:
            grid_data = group_data["grid"]
            grid = GridRule(x=float(grid_data["x"]), y=float(grid_data["y"]))

        size = None
        if "size" in group_data:
            size_data = group_data["size"]
            size = SizeRule(
                width=float(size_data["width"]), height=float(size_data["height"])
            )

        arc = None
        if "arc" in group_data:
            arc_data = group_data["arc"]
            arc = ArcRule(
                start=float(arc_data.get("start", DEFAULT_ARC_START)),
                end=float(arc_data.get("end", DEFAULT_ARC_END)),
            )

        groups.append(
            GroupRule(name=group_data["name"], shape=shape, grid=grid, size=size, arc=arc)
        )

    return AlignmentRule(groups=groups, tolerance=tolerance)


def find_group_by_label(root: ET.Element, label: str) -> ET.Element | None:
    """Find a group element by inkscape:label.

    Args:
        root: Root SVG element.
        label: inkscape:label value to search for.

    Returns:
        Group element or None if not found.
    """
    inkscape_ns = SVG_NAMESPACES["inkscape"]
    for elem in root.iter():
        if get_local_name(elem.tag) == "g":
            elem_label = elem.get(f"{{{inkscape_ns}}}label")
            if elem_label == label:
                return elem
    return None


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


def validate_rect(
    info: RectInfo,
    rule: GroupRule,
    tolerance: ToleranceConfig,
) -> ValidationResult:
    """Validate a rect element against rules.

    Args:
        info: Rect information.
        rule: Group rule to validate against.
        tolerance: Tolerance configuration.

    Returns:
        Validation result.
    """
    result = ValidationResult(element_id=info.id, shape_type="rect")

    # Check size
    if rule.size:
        # Width
        status, dev = check_value_match(
            info.width,
            rule.size.width,
            tolerance.acceptable,
            tolerance.error_threshold,
        )
        if status != "ok":
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="width",
                    status=status,
                    actual=info.width,
                    expected=rule.size.width,
                    deviation=dev,
                    message=f"width={info.width:.6f} (expected: {rule.size.width})",
                )
            )

        # Height
        status, dev = check_value_match(
            info.height,
            rule.size.height,
            tolerance.acceptable,
            tolerance.error_threshold,
        )
        if status != "ok":
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="height",
                    status=status,
                    actual=info.height,
                    expected=rule.size.height,
                    deviation=dev,
                    message=f"height={info.height:.6f} (expected: {rule.size.height})",
                )
            )

    # Check grid alignment (after size check, using current center)
    if rule.grid:
        center_x, center_y = info.center

        aligned, dev = check_grid_alignment(center_x, rule.grid.x, tolerance.acceptable)
        if not aligned:
            # Check if deviation is within error threshold
            ratio = dev / rule.grid.x if rule.grid.x != 0 else dev
            status: IssueStatus = "fixable" if ratio <= tolerance.error_threshold else "error"
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="center_x",
                    status=status,
                    actual=center_x,
                    expected=snap_to_grid(center_x, rule.grid.x),
                    deviation=dev,
                    message=f"center_x={center_x:.6f} (remainder: {dev:.6f})",
                )
            )

        aligned, dev = check_grid_alignment(center_y, rule.grid.y, tolerance.acceptable)
        if not aligned:
            ratio = dev / rule.grid.y if rule.grid.y != 0 else dev
            status = "fixable" if ratio <= tolerance.error_threshold else "error"
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="center_y",
                    status=status,
                    actual=center_y,
                    expected=snap_to_grid(center_y, rule.grid.y),
                    deviation=dev,
                    message=f"center_y={center_y:.6f} (remainder: {dev:.6f})",
                )
            )

    return result


def validate_arc(
    info: ArcInfo,
    rule: GroupRule,
    tolerance: ToleranceConfig,
) -> ValidationResult:
    """Validate an arc element against rules.

    Args:
        info: Arc information.
        rule: Group rule to validate against.
        tolerance: Tolerance configuration.

    Returns:
        Validation result.
    """
    result = ValidationResult(element_id=info.id, shape_type="arc")

    # Check arc parameters (start/end)
    if rule.arc:
        # Start
        status, dev = check_value_match(
            info.start,
            rule.arc.start,
            tolerance.acceptable,
            tolerance.error_threshold,
        )
        if status != "ok":
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="start",
                    status=status,
                    actual=info.start,
                    expected=rule.arc.start,
                    deviation=dev,
                    message=f"start={info.start:.6f} (expected: {rule.arc.start})",
                )
            )

        # End
        status, dev = check_value_match(
            info.end,
            rule.arc.end,
            tolerance.acceptable,
            tolerance.error_threshold,
        )
        if status != "ok":
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="end",
                    status=status,
                    actual=info.end,
                    expected=rule.arc.end,
                    deviation=dev,
                    message=f"end={info.end:.6f} (expected: {rule.arc.end})",
                )
            )

    # Check size (diameter)
    if rule.size:
        diameter_x = info.rx * 2
        diameter_y = info.ry * 2

        status, dev = check_value_match(
            diameter_x,
            rule.size.width,
            tolerance.acceptable,
            tolerance.error_threshold,
        )
        if status != "ok":
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="diameter_x",
                    status=status,
                    actual=diameter_x,
                    expected=rule.size.width,
                    deviation=dev,
                    message=f"diameter_x={diameter_x:.6f} (expected: {rule.size.width})",
                )
            )

        status, dev = check_value_match(
            diameter_y,
            rule.size.height,
            tolerance.acceptable,
            tolerance.error_threshold,
        )
        if status != "ok":
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="diameter_y",
                    status=status,
                    actual=diameter_y,
                    expected=rule.size.height,
                    deviation=dev,
                    message=f"diameter_y={diameter_y:.6f} (expected: {rule.size.height})",
                )
            )

    # Check grid alignment
    if rule.grid:
        aligned, dev = check_grid_alignment(info.cx, rule.grid.x, tolerance.acceptable)
        if not aligned:
            ratio = dev / rule.grid.x if rule.grid.x != 0 else dev
            status: IssueStatus = "fixable" if ratio <= tolerance.error_threshold else "error"
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="center_x",
                    status=status,
                    actual=info.cx,
                    expected=snap_to_grid(info.cx, rule.grid.x),
                    deviation=dev,
                    message=f"center_x={info.cx:.6f} (remainder: {dev:.6f})",
                )
            )

        aligned, dev = check_grid_alignment(info.cy, rule.grid.y, tolerance.acceptable)
        if not aligned:
            ratio = dev / rule.grid.y if rule.grid.y != 0 else dev
            status = "fixable" if ratio <= tolerance.error_threshold else "error"
            result.issues.append(
                Issue(
                    element_id=info.id,
                    field="center_y",
                    status=status,
                    actual=info.cy,
                    expected=snap_to_grid(info.cy, rule.grid.y),
                    deviation=dev,
                    message=f"center_y={info.cy:.6f} (remainder: {dev:.6f})",
                )
            )

    return result


def validate_shape(
    info: ShapeInfo,
    rule: GroupRule,
    tolerance: ToleranceConfig,
) -> ValidationResult:
    """Validate a shape element against rules.

    Args:
        info: Shape information.
        rule: Group rule to validate against.
        tolerance: Tolerance configuration.

    Returns:
        Validation result.
    """
    if isinstance(info, RectInfo):
        return validate_rect(info, rule, tolerance)
    elif isinstance(info, ArcInfo):
        return validate_arc(info, rule, tolerance)
    else:
        raise ValueError(f"Unknown shape type: {type(info)}")


def fix_rect(
    info: RectInfo,
    result: ValidationResult,
    rule: GroupRule,
) -> None:
    """Fix a rect element based on validation result.

    Order: size first, then position (so center is calculated after size fix).

    Args:
        info: Rect information.
        result: Validation result.
        rule: Group rule.
    """
    new_width = info.width
    new_height = info.height

    # Fix size first
    for issue in result.issues:
        if issue.status != "fixable":
            continue

        if issue.field == "width" and rule.size:
            new_width = rule.size.width
            update_rect(info.element, width=new_width)
        elif issue.field == "height" and rule.size:
            new_height = rule.size.height
            update_rect(info.element, height=new_height)

    # Fix position (recalculate center with new size)
    for issue in result.issues:
        if issue.status != "fixable":
            continue

        if issue.field == "center_x" and rule.grid:
            # Current x + new_width/2 = current_center
            # New center = snapped value
            # New x = new_center - new_width/2
            new_center_x = issue.expected
            new_x = new_center_x - new_width / 2
            update_rect(info.element, x=new_x)
        elif issue.field == "center_y" and rule.grid:
            new_center_y = issue.expected
            new_y = new_center_y - new_height / 2
            update_rect(info.element, y=new_y)


def fix_arc(
    info: ArcInfo,
    result: ValidationResult,
    rule: GroupRule,
) -> None:
    """Fix an arc element based on validation result.

    Order: arc params and size first, then position.

    Args:
        info: Arc information.
        result: Validation result.
        rule: Group rule.
    """
    new_rx = info.rx
    new_ry = info.ry

    # Fix arc params and size first
    for issue in result.issues:
        if issue.status != "fixable":
            continue

        if issue.field == "start" and rule.arc:
            update_arc(info.element, start=rule.arc.start)
        elif issue.field == "end" and rule.arc:
            update_arc(info.element, end=rule.arc.end)
        elif issue.field == "diameter_x" and rule.size:
            new_rx = rule.size.width / 2
            update_arc(info.element, rx=new_rx)
        elif issue.field == "diameter_y" and rule.size:
            new_ry = rule.size.height / 2
            update_arc(info.element, ry=new_ry)

    # Fix position
    for issue in result.issues:
        if issue.status != "fixable":
            continue

        if issue.field == "center_x" and rule.grid:
            update_arc(info.element, cx=issue.expected)
        elif issue.field == "center_y" and rule.grid:
            update_arc(info.element, cy=issue.expected)


def fix_shape(
    info: ShapeInfo,
    result: ValidationResult,
    rule: GroupRule,
) -> None:
    """Fix a shape element based on validation result.

    Args:
        info: Shape information.
        result: Validation result.
        rule: Group rule.
    """
    if isinstance(info, RectInfo):
        fix_rect(info, result, rule)
    elif isinstance(info, ArcInfo):
        fix_arc(info, result, rule)


def validate_and_fix_group(
    root: ET.Element,
    rule: GroupRule,
    tolerance: ToleranceConfig,
    fix: bool = False,
) -> GroupValidationResult:
    """Validate and optionally fix shapes in a group.

    Args:
        root: Root SVG element.
        rule: Group rule.
        tolerance: Tolerance configuration.
        fix: Whether to fix fixable issues.

    Returns:
        Group validation result.
    """
    group = find_group_by_label(root, rule.name)
    result = GroupValidationResult(group_name=rule.name, shape_type=rule.shape)

    if group is None:
        return result

    for info in iter_shapes_in_group(group, rule.shape):
        validation = validate_shape(info, rule, tolerance)
        result.element_results.append(validation)

        if fix and validation.has_fixable and not validation.has_errors:
            fix_shape(info, validation, rule)

    return result


def validate_svg(
    svg_path: Path,
    rule: AlignmentRule,
    fix: bool = False,
) -> tuple[ET.ElementTree, AlignmentReport]:
    """Validate an SVG file against alignment rules.

    Args:
        svg_path: Path to SVG file.
        rule: Alignment rules.
        fix: Whether to fix fixable issues.

    Returns:
        Tuple of (ElementTree, AlignmentReport).
    """
    register_namespaces()
    tree = ET.parse(svg_path)
    root = tree.getroot()

    report = AlignmentReport(file_path=svg_path)

    for group_rule in rule.groups:
        group_result = validate_and_fix_group(
            root, group_rule, rule.tolerance, fix=fix
        )
        report.group_results.append(group_result)

    return tree, report


def format_report(report: AlignmentReport) -> str:
    """Format alignment report as text.

    Args:
        report: Alignment report.

    Returns:
        Formatted text.
    """
    lines: list[str] = []
    lines.append(f"File: {report.file_path}")
    lines.append(f"Total elements checked: {report.total_elements}")
    lines.append(f"Errors: {report.total_errors}")
    lines.append(f"Fixable: {report.total_fixable}")
    lines.append("")

    for group_result in report.group_results:
        lines.append(f"Group: {group_result.group_name} ({group_result.shape_type})")
        lines.append(
            f"  OK: {group_result.ok_count}, "
            f"Fixable: {group_result.fixable_count}, "
            f"Errors: {group_result.error_count}"
        )

        # List elements with issues
        for elem_result in group_result.element_results:
            if not elem_result.is_ok:
                status_str = "ERROR" if elem_result.has_errors else "FIXABLE"
                lines.append(f"  [{status_str}] {elem_result.element_id}")
                for issue in elem_result.issues:
                    if issue.status != "ok":
                        lines.append(f"    - {issue.message}")

        lines.append("")

    if report.has_errors:
        lines.append("*** ERRORS DETECTED - Output file will not be generated ***")
    elif report.total_fixable > 0:
        lines.append("All fixable issues can be corrected.")

    return "\n".join(lines)
