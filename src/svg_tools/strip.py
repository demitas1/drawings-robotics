"""SVG group stripping module.

Removes specified groups (layers) from SVG files by inkscape:label.
Matching follows the same rules as find_all_groups_by_label:
exact match and Inkscape duplicate suffixes (e.g., "_ref", "_ref 1").
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from .utils import find_all_groups_by_label, register_namespaces


@dataclass
class StripGroupResult:
    """Result for a single group label."""

    name: str
    removed_count: int


@dataclass
class StripReport:
    """Report for the strip step."""

    group_results: list[StripGroupResult] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        """Total number of group elements removed."""
        return sum(r.removed_count for r in self.group_results)

    @property
    def not_found(self) -> list[str]:
        """Labels that matched no groups."""
        return [r.name for r in self.group_results if r.removed_count == 0]


@dataclass
class StripRule:
    """Rule for the strip step."""

    groups: list[str] = field(default_factory=list)


def parse_strip_rule_file(rule_path: Path) -> StripRule:
    """Parse a YAML rule file containing only a strip section.

    Args:
        rule_path: Path to the YAML rule file.

    Returns:
        Parsed StripRule.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the rule format is invalid.
    """
    with open(rule_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Rule file must be a YAML dictionary")

    return _parse_strip_section(data)


def _parse_strip_section(data: dict) -> StripRule:
    """Parse strip section from YAML data.

    Args:
        data: Dictionary with optional 'groups' key.

    Returns:
        Parsed StripRule.
    """
    groups = [str(name) for name in data.get("groups", [])]
    return StripRule(groups=groups)


def strip_svg_tree(
    tree: ET.ElementTree,
    rule: StripRule,
) -> StripReport:
    """Remove specified groups from an existing ElementTree in-place.

    Args:
        tree: ElementTree to modify in-place.
        rule: Strip rules specifying which groups to remove.

    Returns:
        StripReport with results for each group label.
    """
    root = tree.getroot()
    # Build parent map before any removals
    parent_map: dict[ET.Element, ET.Element] = {
        child: parent for parent in root.iter() for child in parent
    }

    report = StripReport()

    for name in rule.groups:
        groups = find_all_groups_by_label(root, name)
        removed = 0
        for group in groups:
            parent = parent_map.get(group)
            if parent is not None:
                parent.remove(group)
                removed += 1
        report.group_results.append(StripGroupResult(name=name, removed_count=removed))

    return report


def strip_svg(
    svg_path: Path,
    rule: StripRule,
) -> tuple[ET.ElementTree, StripReport]:
    """Remove specified groups from an SVG file.

    Args:
        svg_path: Path to SVG file.
        rule: Strip rules.

    Returns:
        Tuple of (modified ElementTree, StripReport).
    """
    register_namespaces()
    tree = ET.parse(svg_path)
    report = strip_svg_tree(tree, rule)
    return tree, report


def format_strip_report(report: StripReport) -> str:
    """Format strip report as text.

    Args:
        report: Strip report.

    Returns:
        Formatted text.
    """
    lines: list[str] = []
    lines.append(f"Total groups removed: {report.total_removed}")
    lines.append("")

    for result in report.group_results:
        if result.removed_count > 0:
            lines.append(f"  Removed: '{result.name}' ({result.removed_count} group(s))")
        else:
            lines.append(f"  [WARNING] Not found: '{result.name}'")

    return "\n".join(lines)
