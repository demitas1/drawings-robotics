"""Tests for svg_tools.utils module."""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from svg_tools.utils import (
    SVG_NAMESPACES,
    DRAWING_ELEMENTS,
    get_local_name,
    get_group_name,
    is_drawing_element,
    GroupStats,
    SVGStats,
    collect_group_stats,
    analyze_svg,
    iter_all_groups,
    parse_svg,
)


class TestGetLocalName:
    """Tests for get_local_name function."""

    def test_with_namespace(self):
        assert get_local_name("{http://www.w3.org/2000/svg}rect") == "rect"

    def test_with_inkscape_namespace(self):
        tag = "{http://www.inkscape.org/namespaces/inkscape}label"
        assert get_local_name(tag) == "label"

    def test_without_namespace(self):
        assert get_local_name("rect") == "rect"

    def test_empty_namespace(self):
        assert get_local_name("{}rect") == "rect"

    def test_complex_local_name(self):
        assert get_local_name("{http://example.com}my-element") == "my-element"


class TestGetGroupName:
    """Tests for get_group_name function."""

    def test_group_with_inkscape_label(self):
        elem = ET.Element(
            f"{{{SVG_NAMESPACES['svg']}}}g",
            {f"{{{SVG_NAMESPACES['inkscape']}}}label": "my-layer"},
        )
        assert get_group_name(elem) == "my-layer"

    def test_group_with_id_only(self):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}g", {"id": "group-001"})
        assert get_group_name(elem) == "group-001"

    def test_group_with_both_prefers_label(self):
        elem = ET.Element(
            f"{{{SVG_NAMESPACES['svg']}}}g",
            {
                f"{{{SVG_NAMESPACES['inkscape']}}}label": "label-name",
                "id": "id-name",
            },
        )
        assert get_group_name(elem) == "label-name"

    def test_group_without_name(self):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}g")
        assert get_group_name(elem) is None

    def test_non_group_element(self):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}rect", {"id": "rect-001"})
        assert get_group_name(elem) is None

    def test_group_without_namespace(self):
        elem = ET.Element("g", {"id": "plain-group"})
        assert get_group_name(elem) == "plain-group"


class TestIsDrawingElement:
    """Tests for is_drawing_element function."""

    @pytest.mark.parametrize("elem_name", list(DRAWING_ELEMENTS))
    def test_drawing_elements(self, elem_name):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}{elem_name}")
        assert is_drawing_element(elem) is True

    def test_group_is_not_drawing(self):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}g")
        assert is_drawing_element(elem) is False

    def test_defs_is_not_drawing(self):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}defs")
        assert is_drawing_element(elem) is False

    def test_svg_is_not_drawing(self):
        elem = ET.Element(f"{{{SVG_NAMESPACES['svg']}}}svg")
        assert is_drawing_element(elem) is False


class TestGroupStats:
    """Tests for GroupStats dataclass."""

    def test_empty_group(self):
        stats = GroupStats(name="empty", depth=0)
        assert stats.total_elements == 0
        assert stats.total_elements_recursive == 0

    def test_group_with_elements(self):
        stats = GroupStats(
            name="shapes",
            depth=0,
            element_counts={"rect": 3, "circle": 2},
        )
        assert stats.total_elements == 5
        assert stats.total_elements_recursive == 5

    def test_group_with_children(self):
        child = GroupStats(
            name="child",
            depth=1,
            element_counts={"path": 10},
        )
        parent = GroupStats(
            name="parent",
            depth=0,
            element_counts={"rect": 2},
            children=[child],
        )
        assert parent.total_elements == 2
        assert parent.total_elements_recursive == 12

    def test_nested_children(self):
        grandchild = GroupStats(name="grandchild", depth=2, element_counts={"text": 1})
        child = GroupStats(
            name="child", depth=1, element_counts={"circle": 3}, children=[grandchild]
        )
        parent = GroupStats(
            name="parent", depth=0, element_counts={"rect": 2}, children=[child]
        )
        assert parent.total_elements_recursive == 6

    def test_to_dict_simple(self):
        stats = GroupStats(name="test", depth=0, element_counts={"rect": 1})
        d = stats.to_dict()
        assert d["name"] == "test"
        assert d["depth"] == 0
        assert d["element_counts"] == {"rect": 1}
        assert d["total_elements"] == 1
        assert "children" not in d

    def test_to_dict_with_children(self):
        child = GroupStats(name="child", depth=1, element_counts={"path": 2})
        parent = GroupStats(name="parent", depth=0, children=[child])
        d = parent.to_dict()
        assert "children" in d
        assert len(d["children"]) == 1
        assert d["children"][0]["name"] == "child"


class TestSVGStats:
    """Tests for SVGStats dataclass."""

    def test_empty_svg(self):
        stats = SVGStats(file_path=Path("test.svg"))
        assert stats.total_elements == 0

    def test_ungrouped_only(self):
        stats = SVGStats(
            file_path=Path("test.svg"),
            ungrouped_counts={"rect": 5, "circle": 3},
        )
        assert stats.total_elements == 8

    def test_groups_only(self):
        group = GroupStats(name="layer", depth=0, element_counts={"path": 10})
        stats = SVGStats(file_path=Path("test.svg"), root_groups=[group])
        assert stats.total_elements == 10

    def test_mixed(self):
        group = GroupStats(name="layer", depth=0, element_counts={"path": 10})
        stats = SVGStats(
            file_path=Path("test.svg"),
            root_groups=[group],
            ungrouped_counts={"rect": 2},
        )
        assert stats.total_elements == 12

    def test_to_dict(self):
        group = GroupStats(name="layer", depth=0, element_counts={"rect": 1})
        stats = SVGStats(
            file_path=Path("test.svg"),
            root_groups=[group],
            ungrouped_counts={"circle": 2},
        )
        d = stats.to_dict()
        assert d["file"] == "test.svg"
        assert d["total_elements"] == 3
        assert len(d["groups"]) == 1
        assert d["ungrouped"] == {"circle": 2}


class TestCollectGroupStats:
    """Tests for collect_group_stats function."""

    def test_named_group_with_elements(self):
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        group = ET.Element(f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "shapes"})
        ET.SubElement(group, f"{{{svg_ns}}}rect")
        ET.SubElement(group, f"{{{svg_ns}}}rect")
        ET.SubElement(group, f"{{{svg_ns}}}circle")

        stats = collect_group_stats(group)
        assert stats is not None
        assert stats.name == "shapes"
        assert stats.element_counts == {"rect": 2, "circle": 1}

    def test_anonymous_group_returns_none(self):
        svg_ns = SVG_NAMESPACES["svg"]
        group = ET.Element(f"{{{svg_ns}}}g")
        ET.SubElement(group, f"{{{svg_ns}}}rect")

        stats = collect_group_stats(group)
        assert stats is None

    def test_nested_named_groups(self):
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        parent = ET.Element(f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "parent"})
        child = ET.SubElement(
            parent, f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "child"}
        )
        ET.SubElement(parent, f"{{{svg_ns}}}rect")
        ET.SubElement(child, f"{{{svg_ns}}}path")
        ET.SubElement(child, f"{{{svg_ns}}}path")

        stats = collect_group_stats(parent)
        assert stats is not None
        assert stats.name == "parent"
        assert stats.element_counts == {"rect": 1}
        assert len(stats.children) == 1
        assert stats.children[0].name == "child"
        assert stats.children[0].element_counts == {"path": 2}
        assert stats.children[0].depth == 1

    def test_anonymous_nested_group_merges_elements(self):
        svg_ns = SVG_NAMESPACES["svg"]
        inkscape_ns = SVG_NAMESPACES["inkscape"]

        parent = ET.Element(f"{{{svg_ns}}}g", {f"{{{inkscape_ns}}}label": "parent"})
        anonymous = ET.SubElement(parent, f"{{{svg_ns}}}g")
        ET.SubElement(anonymous, f"{{{svg_ns}}}rect")
        ET.SubElement(anonymous, f"{{{svg_ns}}}rect")

        stats = collect_group_stats(parent)
        assert stats is not None
        assert stats.element_counts == {"rect": 2}
        assert len(stats.children) == 0


class TestIterAllGroups:
    """Tests for iter_all_groups function."""

    def test_empty_stats(self):
        stats = SVGStats(file_path=Path("test.svg"))
        groups = list(iter_all_groups(stats))
        assert groups == []

    def test_single_group(self):
        group = GroupStats(name="layer", depth=0)
        stats = SVGStats(file_path=Path("test.svg"), root_groups=[group])
        groups = list(iter_all_groups(stats))
        assert len(groups) == 1
        assert groups[0].name == "layer"

    def test_depth_first_order(self):
        grandchild = GroupStats(name="grandchild", depth=2)
        child1 = GroupStats(name="child1", depth=1, children=[grandchild])
        child2 = GroupStats(name="child2", depth=1)
        parent = GroupStats(name="parent", depth=0, children=[child1, child2])
        stats = SVGStats(file_path=Path("test.svg"), root_groups=[parent])

        names = [g.name for g in iter_all_groups(stats)]
        assert names == ["parent", "child1", "grandchild", "child2"]

    def test_multiple_root_groups(self):
        group1 = GroupStats(name="layer1", depth=0)
        group2 = GroupStats(name="layer2", depth=0)
        stats = SVGStats(file_path=Path("test.svg"), root_groups=[group1, group2])

        names = [g.name for g in iter_all_groups(stats)]
        assert names == ["layer1", "layer2"]


class TestAnalyzeSvg:
    """Tests for analyze_svg function with actual SVG file."""

    @pytest.fixture
    def sample_svg(self, tmp_path) -> Path:
        """Create a sample SVG file for testing."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="100" height="100" viewBox="0 0 100 100">
  <rect id="background" x="0" y="0" width="100" height="100"/>
  <g inkscape:label="Layer 1">
    <rect x="10" y="10" width="20" height="20"/>
    <g inkscape:label="shapes">
      <circle cx="50" cy="50" r="10"/>
      <ellipse cx="70" cy="70" rx="5" ry="10"/>
    </g>
    <g>
      <path d="M0,0 L10,10"/>
    </g>
  </g>
  <g id="layer2">
    <text x="0" y="50">Hello</text>
  </g>
</svg>"""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(svg_content)
        return svg_file

    def test_analyze_sample_svg(self, sample_svg):
        stats = analyze_svg(sample_svg)

        assert stats.file_path == sample_svg
        assert stats.total_elements == 6

        # Check ungrouped elements
        assert stats.ungrouped_counts == {"rect": 1}

        # Check root groups
        assert len(stats.root_groups) == 2

        # Check Layer 1
        layer1 = stats.root_groups[0]
        assert layer1.name == "Layer 1"
        assert layer1.element_counts == {"rect": 1, "path": 1}
        assert len(layer1.children) == 1

        # Check nested shapes group
        shapes = layer1.children[0]
        assert shapes.name == "shapes"
        assert shapes.element_counts == {"circle": 1, "ellipse": 1}
        assert shapes.depth == 1

        # Check layer2 (id-based)
        layer2 = stats.root_groups[1]
        assert layer2.name == "layer2"
        assert layer2.element_counts == {"text": 1}

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            analyze_svg(Path("/nonexistent/file.svg"))


class TestParseSvg:
    """Tests for parse_svg function."""

    @pytest.fixture
    def minimal_svg(self, tmp_path) -> Path:
        """Create a minimal SVG file."""
        svg_content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="0" y="0" width="50" height="50"/>
</svg>"""
        svg_file = tmp_path / "minimal.svg"
        svg_file.write_text(svg_content)
        return svg_file

    def test_parse_returns_root_element(self, minimal_svg):
        root = parse_svg(minimal_svg)
        assert get_local_name(root.tag) == "svg"

    def test_parse_invalid_xml(self, tmp_path):
        invalid_file = tmp_path / "invalid.svg"
        invalid_file.write_text("<svg><rect></svg>")

        with pytest.raises(ET.ParseError):
            parse_svg(invalid_file)
