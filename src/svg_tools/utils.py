"""Utility functions for SVG parsing and analysis."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

# SVG namespace mappings
SVG_NAMESPACES = {
    "svg": "http://www.w3.org/2000/svg",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}

# Drawing elements to count
DRAWING_ELEMENTS = frozenset(
    [
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "path",
        "text",
        "tspan",
        "image",
        "use",
    ]
)


def register_namespaces() -> None:
    """Register SVG namespaces to preserve prefixes when writing."""
    for prefix, uri in SVG_NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def parse_svg(file_path: Path) -> ET.Element:
    """Parse an SVG file and return the root element.

    Args:
        file_path: Path to the SVG file.

    Returns:
        Root element of the parsed SVG.

    Raises:
        FileNotFoundError: If the file does not exist.
        ET.ParseError: If the file is not valid XML.
    """
    register_namespaces()
    tree = ET.parse(file_path)
    return tree.getroot()


def get_local_name(tag: str) -> str:
    """Extract local name from a namespaced tag.

    Args:
        tag: Full tag name, possibly with namespace.

    Returns:
        Local name without namespace prefix.

    Example:
        >>> get_local_name("{http://www.w3.org/2000/svg}rect")
        'rect'
    """
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def get_group_name(element: ET.Element) -> str | None:
    """Get the display name for a group element.

    Prefers inkscape:label, falls back to id attribute.

    Args:
        element: An XML element.

    Returns:
        Group name or None if not a group or no name found.
    """
    local_name = get_local_name(element.tag)
    if local_name != "g":
        return None

    # Try inkscape:label first
    label = element.get(f"{{{SVG_NAMESPACES['inkscape']}}}label")
    if label:
        return label

    # Fall back to id
    return element.get("id")


def is_drawing_element(element: ET.Element) -> bool:
    """Check if an element is a drawing element.

    Args:
        element: An XML element.

    Returns:
        True if the element is a drawing element.
    """
    return get_local_name(element.tag) in DRAWING_ELEMENTS


@dataclass
class GroupStats:
    """Statistics for a single group."""

    name: str
    depth: int
    element_counts: dict[str, int] = field(default_factory=dict)
    children: list["GroupStats"] = field(default_factory=list)

    @property
    def total_elements(self) -> int:
        """Total number of drawing elements in this group (excluding children)."""
        return sum(self.element_counts.values())

    @property
    def total_elements_recursive(self) -> int:
        """Total number of drawing elements including all descendants."""
        total = self.total_elements
        for child in self.children:
            total += child.total_elements_recursive
        return total

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "depth": self.depth,
            "element_counts": self.element_counts,
            "total_elements": self.total_elements,
        }
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result


@dataclass
class SVGStats:
    """Statistics for an entire SVG file."""

    file_path: Path
    root_groups: list[GroupStats] = field(default_factory=list)
    ungrouped_counts: dict[str, int] = field(default_factory=dict)

    @property
    def total_elements(self) -> int:
        """Total number of drawing elements in the SVG."""
        total = sum(self.ungrouped_counts.values())
        for group in self.root_groups:
            total += group.total_elements_recursive
        return total

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file": str(self.file_path),
            "total_elements": self.total_elements,
            "groups": [g.to_dict() for g in self.root_groups],
            "ungrouped": self.ungrouped_counts,
        }


def collect_group_stats(element: ET.Element, depth: int = 0) -> GroupStats | None:
    """Collect statistics for a group element and its descendants.

    Args:
        element: A group element.
        depth: Current nesting depth.

    Returns:
        GroupStats for the group, or None if not a named group.
    """
    name = get_group_name(element)
    if name is None:
        return None

    stats = GroupStats(name=name, depth=depth)

    for child in element:
        if is_drawing_element(child):
            local_name = get_local_name(child.tag)
            stats.element_counts[local_name] = (
                stats.element_counts.get(local_name, 0) + 1
            )
        elif get_local_name(child.tag) == "g":
            child_stats = collect_group_stats(child, depth + 1)
            if child_stats:
                stats.children.append(child_stats)
            else:
                # Anonymous group - collect its elements into parent
                _collect_anonymous_group(child, stats)

    return stats


def _collect_anonymous_group(element: ET.Element, parent_stats: GroupStats) -> None:
    """Collect elements from anonymous groups into parent stats."""
    for child in element:
        if is_drawing_element(child):
            local_name = get_local_name(child.tag)
            parent_stats.element_counts[local_name] = (
                parent_stats.element_counts.get(local_name, 0) + 1
            )
        elif get_local_name(child.tag) == "g":
            child_stats = collect_group_stats(child, parent_stats.depth + 1)
            if child_stats:
                parent_stats.children.append(child_stats)
            else:
                _collect_anonymous_group(child, parent_stats)


def analyze_svg(file_path: Path) -> SVGStats:
    """Analyze an SVG file and collect statistics.

    Args:
        file_path: Path to the SVG file.

    Returns:
        SVGStats containing group hierarchy and element counts.
    """
    root = parse_svg(file_path)
    stats = SVGStats(file_path=file_path)

    for child in root:
        if is_drawing_element(child):
            local_name = get_local_name(child.tag)
            stats.ungrouped_counts[local_name] = (
                stats.ungrouped_counts.get(local_name, 0) + 1
            )
        elif get_local_name(child.tag) == "g":
            group_stats = collect_group_stats(child, depth=0)
            if group_stats:
                stats.root_groups.append(group_stats)
            else:
                # Anonymous root group - collect as ungrouped
                _collect_ungrouped(child, stats)

    return stats


def _collect_ungrouped(element: ET.Element, svg_stats: SVGStats) -> None:
    """Collect elements from anonymous root groups as ungrouped."""
    for child in element:
        if is_drawing_element(child):
            local_name = get_local_name(child.tag)
            svg_stats.ungrouped_counts[local_name] = (
                svg_stats.ungrouped_counts.get(local_name, 0) + 1
            )
        elif get_local_name(child.tag) == "g":
            group_stats = collect_group_stats(child, depth=0)
            if group_stats:
                svg_stats.root_groups.append(group_stats)
            else:
                _collect_ungrouped(child, svg_stats)


def iter_all_groups(stats: SVGStats) -> Iterator[GroupStats]:
    """Iterate over all groups in depth-first order.

    Args:
        stats: SVG statistics.

    Yields:
        Each GroupStats in the hierarchy.
    """

    def _iter_group(group: GroupStats) -> Iterator[GroupStats]:
        yield group
        for child in group.children:
            yield from _iter_group(child)

    for root_group in stats.root_groups:
        yield from _iter_group(root_group)


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


def get_element_label(element: ET.Element) -> str | None:
    """Get the inkscape:label of an element.

    Args:
        element: An XML element.

    Returns:
        The label value or None if not set.
    """
    inkscape_ns = SVG_NAMESPACES["inkscape"]
    return element.get(f"{{{inkscape_ns}}}label")


def set_element_label(element: ET.Element, label: str) -> None:
    """Set the inkscape:label of an element.

    Args:
        element: An XML element.
        label: The label value to set.
    """
    inkscape_ns = SVG_NAMESPACES["inkscape"]
    element.set(f"{{{inkscape_ns}}}label", label)
