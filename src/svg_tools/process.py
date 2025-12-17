"""SVG processing pipeline module.

This module provides unified processing pipeline combining:
- align: Validate and fix shape alignments
- relabel: Assign coordinate-based labels
- add_text: Add text elements

The pipeline processes in order: align -> relabel -> add_text
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

import yaml

from .add_text import (
    AddTextReport,
    AddTextRule,
    TextLineRule,
    FontConfig,
    TextFormatConfig,
    add_text_to_svg_tree,
)
from .align import (
    AlignmentReport,
    AlignmentRule,
    GroupRule,
    GridRule,
    SizeRule,
    ArcRule,
    ToleranceConfig,
    validate_svg_tree,
)
from .relabel import (
    RelabelReport,
    RelabelRule,
    RelabelGroupRule,
    GridConfig,
    OriginConfig,
    AxisConfig,
    IndexConfig,
    FormatConfig,
    SortConfig,
    relabel_svg_tree,
)
from .utils import register_namespaces


# Step names
StepName = Literal["align", "relabel", "add_text"]
ALL_STEPS: list[StepName] = ["align", "relabel", "add_text"]


@dataclass
class ProcessRule:
    """Complete processing rule configuration.

    Each section is optional. If a section is None, that step will be skipped.
    """

    align: AlignmentRule | None = None
    relabel: RelabelRule | None = None
    add_text: AddTextRule | None = None


@dataclass
class ProcessReport:
    """Complete processing report."""

    file_path: Path
    align_report: AlignmentReport | None = None
    relabel_report: RelabelReport | None = None
    add_text_report: AddTextReport | None = None
    skipped_steps: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any step has errors."""
        if self.align_report and self.align_report.has_errors:
            return True
        if self.relabel_report and self.relabel_report.has_errors:
            return True
        if self.add_text_report and self.add_text_report.has_errors:
            return True
        return False

    @property
    def executed_steps(self) -> list[str]:
        """List of steps that were executed."""
        steps = []
        if self.align_report is not None:
            steps.append("align")
        if self.relabel_report is not None:
            steps.append("relabel")
        if self.add_text_report is not None:
            steps.append("add_text")
        return steps


def parse_align_section(data: dict) -> AlignmentRule:
    """Parse align section from YAML data.

    Args:
        data: Align section dictionary.

    Returns:
        Parsed AlignmentRule.

    Raises:
        ValueError: If the format is invalid.
    """
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
            raise ValueError("Each align group must have 'name' and 'shape' fields")

        shape = group_data["shape"]
        if shape not in ("rect", "arc", "path"):
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
                start=float(arc_data.get("start", 0.0)),
                end=float(arc_data.get("end", 6.283185307179586)),
            )

        groups.append(
            GroupRule(name=group_data["name"], shape=shape, grid=grid, size=size, arc=arc)
        )

    return AlignmentRule(groups=groups, tolerance=tolerance)


def parse_relabel_section(data: dict) -> RelabelRule:
    """Parse relabel section from YAML data.

    Args:
        data: Relabel section dictionary.

    Returns:
        Parsed RelabelRule.

    Raises:
        ValueError: If the format is invalid.
    """
    groups: list[RelabelGroupRule] = []
    for group_data in data.get("groups", []):
        # Required fields
        if "name" not in group_data:
            raise ValueError("Each relabel group must have 'name' field")
        if "shape" not in group_data:
            raise ValueError("Each relabel group must have 'shape' field")
        if "label_template" not in group_data:
            raise ValueError("Each relabel group must have 'label_template' field")
        if "grid" not in group_data:
            raise ValueError("Each relabel group must have 'grid' field")

        shape = group_data["shape"]
        if shape not in ("rect", "arc"):
            raise ValueError(f"Unsupported shape type for relabel: {shape}")

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
                fmt.x_type = fmt_data["x_type"]
            if "y_type" in fmt_data:
                fmt.y_type = fmt_data["y_type"]
            if "x_padding" in fmt_data:
                fmt.x_padding = int(fmt_data["x_padding"])
            if "y_padding" in fmt_data:
                fmt.y_padding = int(fmt_data["y_padding"])
            if "custom_x" in fmt_data:
                fmt.custom_x = [str(item) for item in fmt_data["custom_x"]]
            if "custom_y" in fmt_data:
                fmt.custom_y = [str(item) for item in fmt_data["custom_y"]]

        # Sort (optional)
        sort = SortConfig()
        if "sort" in group_data:
            sort_data = group_data["sort"]
            if "by" in sort_data:
                sort.by = sort_data["by"]
            if "x_order" in sort_data:
                sort.x_order = sort_data["x_order"]
            if "y_order" in sort_data:
                sort.y_order = sort_data["y_order"]

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


def parse_add_text_section(data: dict) -> AddTextRule:
    """Parse add_text section from YAML data.

    Args:
        data: Add text section dictionary.

    Returns:
        Parsed AddTextRule.

    Raises:
        ValueError: If the format is invalid.
    """
    groups: list[TextLineRule] = []
    for group_data in data.get("groups", []):
        if "name" not in group_data:
            raise ValueError("Each add_text group must have 'name' field")

        # Determine layout direction
        has_horizontal = "y" in group_data and "x_start" in group_data
        has_vertical = "x" in group_data and "y_start" in group_data

        if has_horizontal and has_vertical:
            raise ValueError(
                f"Group '{group_data['name']}': Cannot specify both layouts"
            )
        if not has_horizontal and not has_vertical:
            raise ValueError(
                f"Group '{group_data['name']}': Must specify layout fields"
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
                fmt.type = fmt_data["type"]
            if "padding" in fmt_data:
                fmt.padding = int(fmt_data["padding"])
            if "start" in fmt_data:
                fmt.start = int(fmt_data["start"])
            if "custom" in fmt_data:
                fmt.custom = [str(item) for item in fmt_data["custom"]]

        # Align (optional)
        align = group_data.get("align", "bbox_center")

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
        else:
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


def parse_process_rule_file(rule_path: Path) -> ProcessRule:
    """Parse a unified YAML rule file.

    The file can contain optional sections: align, relabel, add_text.
    Sections that are not present will be None in the returned ProcessRule.

    Args:
        rule_path: Path to the YAML rule file.

    Returns:
        Parsed ProcessRule.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the rule format is invalid.
    """
    with open(rule_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Rule file must be a YAML dictionary")

    result = ProcessRule()

    if "align" in data:
        result.align = parse_align_section(data["align"])

    if "relabel" in data:
        result.relabel = parse_relabel_section(data["relabel"])

    if "add_text" in data:
        result.add_text = parse_add_text_section(data["add_text"])

    return result


def process_svg_tree(
    tree: ET.ElementTree,
    rule: ProcessRule,
    steps: list[StepName] | None = None,
    apply: bool = False,
) -> ProcessReport:
    """Process an existing ElementTree through the pipeline.

    Args:
        tree: ElementTree to process (modified in-place if apply=True).
        rule: Processing rules.
        steps: Steps to execute (default: all available steps).
        apply: Whether to apply changes to the SVG.

    Returns:
        ProcessReport with results from all executed steps.
    """
    if steps is None:
        steps = ALL_STEPS

    report = ProcessReport(file_path=Path(""))

    # Step 1: Align
    if "align" in steps:
        if rule.align is not None:
            report.align_report = validate_svg_tree(tree, rule.align, fix=apply)
            # Stop if align has errors
            if report.align_report.has_errors:
                return report
        else:
            report.skipped_steps.append("align (no rule)")
    else:
        report.skipped_steps.append("align (not requested)")

    # Step 2: Relabel
    if "relabel" in steps:
        if rule.relabel is not None:
            report.relabel_report = relabel_svg_tree(tree, rule.relabel, apply=apply)
            # Stop if relabel has errors
            if report.relabel_report.has_errors:
                return report
        else:
            report.skipped_steps.append("relabel (no rule)")
    else:
        report.skipped_steps.append("relabel (not requested)")

    # Step 3: Add text
    if "add_text" in steps:
        if rule.add_text is not None:
            report.add_text_report = add_text_to_svg_tree(tree, rule.add_text, apply=apply)
        else:
            report.skipped_steps.append("add_text (no rule)")
    else:
        report.skipped_steps.append("add_text (not requested)")

    return report


def process_svg(
    svg_path: Path,
    rule: ProcessRule,
    steps: list[StepName] | None = None,
    apply: bool = False,
) -> tuple[ET.ElementTree, ProcessReport]:
    """Process an SVG file through the pipeline.

    Pipeline order: align -> relabel -> add_text

    Args:
        svg_path: Path to SVG file.
        rule: Processing rules.
        steps: Steps to execute (default: all available steps).
        apply: Whether to apply changes to the SVG.

    Returns:
        Tuple of (ElementTree, ProcessReport).
    """
    register_namespaces()
    tree = ET.parse(svg_path)
    report = process_svg_tree(tree, rule, steps, apply)
    report.file_path = svg_path
    return tree, report


def format_process_report(report: ProcessReport) -> str:
    """Format processing report as text.

    Args:
        report: Processing report.

    Returns:
        Formatted text.
    """
    lines: list[str] = []
    lines.append(f"File: {report.file_path}")
    lines.append("")

    # Skipped steps
    if report.skipped_steps:
        lines.append("Skipped steps:")
        for step in report.skipped_steps:
            lines.append(f"  - {step}")
        lines.append("")

    # Align report
    if report.align_report is not None:
        lines.append("=" * 60)
        lines.append("ALIGN STEP")
        lines.append("=" * 60)
        lines.append(f"Total elements checked: {report.align_report.total_elements}")
        lines.append(f"Errors: {report.align_report.total_errors}")
        lines.append(f"Fixable: {report.align_report.total_fixable}")
        lines.append("")

        for group_result in report.align_report.group_results:
            lines.append(f"Group: {group_result.group_name} ({group_result.shape_type})")
            lines.append(
                f"  OK: {group_result.ok_count}, "
                f"Fixable: {group_result.fixable_count}, "
                f"Errors: {group_result.error_count}"
            )

            for elem_result in group_result.element_results:
                if not elem_result.is_ok:
                    status_str = "ERROR" if elem_result.has_errors else "FIXABLE"
                    lines.append(f"  [{status_str}] {elem_result.element_id}")
                    for issue in elem_result.issues:
                        if issue.status != "ok":
                            lines.append(f"    - {issue.message}")
            lines.append("")

    # Relabel report
    if report.relabel_report is not None:
        lines.append("=" * 60)
        lines.append("RELABEL STEP")
        lines.append("=" * 60)

        for group_result in report.relabel_report.group_results:
            lines.append(f"Group: {group_result.group_name} ({group_result.shape_type})")
            lines.append(f"  Total elements: {len(group_result.changes)}")
            lines.append(f"  Changed: {group_result.changed_count}")
            lines.append(f"  Unchanged: {group_result.unchanged_count}")

            for warning in group_result.warnings:
                lines.append(f"  [WARNING] {warning}")
            for error in group_result.errors:
                lines.append(f"  [ERROR] {error}")
            lines.append("")

    # Add text report
    if report.add_text_report is not None:
        lines.append("=" * 60)
        lines.append("ADD_TEXT STEP")
        lines.append("=" * 60)

        for group_result in report.add_text_report.group_results:
            lines.append(f"Group: {group_result.group_name}")
            lines.append(f"  Elements created: {group_result.element_count}")

            for warning in group_result.warnings:
                lines.append(f"  [WARNING] {warning}")
            for error in group_result.errors:
                lines.append(f"  [ERROR] {error}")
            lines.append("")

    # Summary
    lines.append("=" * 60)
    lines.append("SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Executed steps: {', '.join(report.executed_steps) or 'none'}")

    if report.has_errors:
        lines.append("")
        lines.append("*** ERRORS DETECTED - Output file will not be generated ***")
    else:
        lines.append("All steps completed successfully.")

    return "\n".join(lines)
