"""Tests for svg_tools.strip module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import SVG_NAMESPACES
from svg_tools.strip import (
    StripRule,
    StripGroupResult,
    StripReport,
    strip_svg_tree,
    strip_svg,
    format_strip_report,
)


def _make_svg(labels: list[str]) -> ET.ElementTree:
    """Create an SVG ElementTree with top-level groups for each label."""
    svg_ns = SVG_NAMESPACES["svg"]
    inkscape_ns = SVG_NAMESPACES["inkscape"]

    root = ET.Element(f"{{{svg_ns}}}svg")
    for label in labels:
        g = ET.SubElement(root, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": label})
        ET.SubElement(g, f"{{{svg_ns}}}rect", {"id": f"rect-{label}", "x": "0", "y": "0",
                                                "width": "10", "height": "10"})
    return ET.ElementTree(root)


class TestStripReport:
    """Tests for StripReport dataclass."""

    def test_total_removed(self):
        report = StripReport(group_results=[
            StripGroupResult(name="_ref", removed_count=2),
            StripGroupResult(name="guide", removed_count=1),
        ])
        assert report.total_removed == 3

    def test_not_found(self):
        report = StripReport(group_results=[
            StripGroupResult(name="_ref", removed_count=1),
            StripGroupResult(name="nonexistent", removed_count=0),
        ])
        assert report.not_found == ["nonexistent"]

    def test_all_found(self):
        report = StripReport(group_results=[
            StripGroupResult(name="_ref", removed_count=1),
        ])
        assert report.not_found == []


class TestStripSvgTree:
    """Tests for strip_svg_tree function."""

    def test_remove_single_group(self):
        tree = _make_svg(["_ref", "content", "labels"])
        rule = StripRule(groups=["_ref"])

        report = strip_svg_tree(tree, rule)

        assert report.total_removed == 1
        assert report.group_results[0].name == "_ref"
        assert report.group_results[0].removed_count == 1

        # Verify group is gone from the tree
        root = tree.getroot()
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        labels = [
            g.get(f"{{{inkscape_ns}}}label")
            for g in root
            if g.get(f"{{{inkscape_ns}}}label")
        ]
        assert "_ref" not in labels
        assert "content" in labels
        assert "labels" in labels

    def test_remove_multiple_groups(self):
        tree = _make_svg(["_ref", "guide", "content"])
        rule = StripRule(groups=["_ref", "guide"])

        report = strip_svg_tree(tree, rule)

        assert report.total_removed == 2

        root = tree.getroot()
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        labels = [
            g.get(f"{{{inkscape_ns}}}label")
            for g in root
            if g.get(f"{{{inkscape_ns}}}label")
        ]
        assert "_ref" not in labels
        assert "guide" not in labels
        assert "content" in labels

    def test_remove_inkscape_duplicate_groups(self):
        # "_ref" and "_ref 1" both exist (Inkscape duplicate naming)
        tree = _make_svg(["_ref", "_ref 1", "content"])
        rule = StripRule(groups=["_ref"])

        report = strip_svg_tree(tree, rule)

        assert report.total_removed == 2
        assert report.group_results[0].removed_count == 2

        root = tree.getroot()
        inkscape_ns = SVG_NAMESPACES["inkscape"]
        labels = [
            g.get(f"{{{inkscape_ns}}}label")
            for g in root
            if g.get(f"{{{inkscape_ns}}}label")
        ]
        assert "_ref" not in labels
        assert "_ref 1" not in labels
        assert "content" in labels

    def test_not_found_group_recorded(self):
        tree = _make_svg(["content"])
        rule = StripRule(groups=["nonexistent"])

        report = strip_svg_tree(tree, rule)

        assert report.total_removed == 0
        assert report.group_results[0].removed_count == 0
        assert "nonexistent" in report.not_found

    def test_empty_rule_removes_nothing(self):
        tree = _make_svg(["_ref", "content"])
        rule = StripRule(groups=[])

        report = strip_svg_tree(tree, rule)

        assert report.total_removed == 0
        assert len(report.group_results) == 0

    def test_nested_group_removal(self):
        """Remove a group that is nested inside a parent group."""
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        root = ET.Element(f"{{{svg_ns}}}svg")
        layer = ET.SubElement(root, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "Layer 1"})
        ref = ET.SubElement(layer, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "_ref"})
        ET.SubElement(ref, f"{{{svg_ns}}}rect", {"id": "r1"})
        content = ET.SubElement(layer, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "content"})
        ET.SubElement(content, f"{{{svg_ns}}}rect", {"id": "r2"})

        tree = ET.ElementTree(root)
        rule = StripRule(groups=["_ref"])

        report = strip_svg_tree(tree, rule)

        assert report.total_removed == 1

        # _ref should be gone from layer's children
        children_labels = [
            g.get(f"{{{inkscape_ns}}}label") for g in layer
        ]
        assert "_ref" not in children_labels
        assert "content" in children_labels

    def test_children_removed_with_group(self):
        """Removing a group also removes all its children."""
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        root = ET.Element(f"{{{svg_ns}}}svg")
        ref = ET.SubElement(root, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "_ref"})
        ET.SubElement(ref, f"{{{svg_ns}}}rect", {"id": "child1"})
        ET.SubElement(ref, f"{{{svg_ns}}}path", {"id": "child2"})

        tree = ET.ElementTree(root)
        rule = StripRule(groups=["_ref"])

        strip_svg_tree(tree, rule)

        # No child elements should remain
        all_ids = [elem.get("id") for elem in root.iter() if elem.get("id")]
        assert "child1" not in all_ids
        assert "child2" not in all_ids


class TestStripSvg:
    """Tests for strip_svg function with actual SVG files."""

    @pytest.fixture
    def sample_svg(self, tmp_path) -> Path:
        """Create a sample SVG file with _ref layer."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="100" height="100">
  <g inkscape:label="_ref">
    <rect id="ref-rect" x="0" y="0" width="50" height="50"/>
  </g>
  <g inkscape:label="content">
    <rect id="content-rect" x="10" y="10" width="20" height="20"/>
  </g>
</svg>"""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(svg_content)
        return svg_file

    def test_strip_from_file(self, sample_svg):
        rule = StripRule(groups=["_ref"])
        tree, report = strip_svg(sample_svg, rule)

        assert report.total_removed == 1

        root = tree.getroot()
        ids = [elem.get("id") for elem in root.iter() if elem.get("id")]
        assert "ref-rect" not in ids
        assert "content-rect" in ids

    def test_file_not_found(self, tmp_path):
        rule = StripRule(groups=["_ref"])
        with pytest.raises(FileNotFoundError):
            strip_svg(tmp_path / "nonexistent.svg", rule)


class TestFormatStripReport:
    """Tests for format_strip_report function."""

    def test_format_with_removed(self):
        report = StripReport(group_results=[
            StripGroupResult(name="_ref", removed_count=2),
        ])
        text = format_strip_report(report)
        assert "Total groups removed: 2" in text
        assert "Removed" in text
        assert "_ref" in text

    def test_format_with_not_found(self):
        report = StripReport(group_results=[
            StripGroupResult(name="nonexistent", removed_count=0),
        ])
        text = format_strip_report(report)
        assert "WARNING" in text
        assert "nonexistent" in text

    def test_format_empty(self):
        report = StripReport()
        text = format_strip_report(report)
        assert "Total groups removed: 0" in text
